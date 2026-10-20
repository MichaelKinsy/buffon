# SPDX-License-Identifier: Apache-2.0
"""The runner: one interleaved session on the machine it runs on.

What the engine enforces, whatever the workload (METHODOLOGY.md sections 2, 5 and 6):

  * a fresh process, a fresh HOME and a fresh work directory for every sample;
  * an A/A copy of every arm (`<id>-b`: the same executable, installed once, run as its own arm in the same rounds);
  * at least MIN_ROUNDS measured rounds, after WARMUP_ROUNDS warm-up rounds that stay in the raw data but not in the statistics;
  * each round runs every variant once with the arm order rotated, so drift lands on every arm equally;
  * the harness pinned to the site's CPUs and the runner and mock pinned elsewhere;
  * a calibration (the reference arm against its A/A copy) that must pass a CV gate before anything is measured;
  * the egress audit on every sample: any connection to a non-loopback address fails the sample and the run;
  * host facts, idle checks before and after, executable hashes before and after.

A backend decides where `run_session` runs; nothing in this module names a host.
"""
import copy
import os
import time
import traceback
from dataclasses import dataclass, field

from . import adaptive as adaptivelib
from . import container as containerlib
from . import equivalence as equivlib
from . import cgroup, cpumon, detect, egress, facts as factlib, hooks, perfcount, textmaps, preflight as preflightlib, quiet as quietlib, raw as rawlib, sysinfo, tuning, wire
from .. import workloads
from ..arms import install, lock, manifest
from ..mock import MockServer, reqlog
from .. import envelope
from ..envelope import pod as podlib
from ..site import parse_cpus
from ..workloads.overhead import Ctx, Skip, sweep_extensions

MIN_ROUNDS = 12
WARMUP_ROUNDS = 1
CV_GATE = 0.05
GIVE_UP_AFTER = 3       # consecutive failures of one arm in one variant, then it sits out the remaining rounds (every attempt stays in the raw data)
APIS = ("openai-completions", "anthropic-messages")
RESPONSES = "openai-responses"


class Refused(Exception):
    """The run is refused before measuring (exit code 3): the message says what to change."""


@dataclass
class Plan:
    workloads: list
    arms: list
    apis: list = field(default_factory=lambda: list(APIS))
    apis_explicit: bool = False          # the operator named the APIs: run exactly those, else add Responses when an arm speaks only that
    rounds: int = MIN_ROUNDS
    rounds_set: bool = True              # the operator gave --rounds: it wins over a workload's own default (the scale family's 5)
    warmup: int = WARMUP_ROUNDS
    aa: str = "all"                      # all | none | comma list of arm ids
    aa_set: bool = True                  # the operator gave --aa: it wins over a workload that has no A/A copy by default (the scale family)
    cpus: list = field(default_factory=list)
    mock_cpus: list = field(default_factory=list)
    pinning: str = "preferred"           # required | preferred | none
    seed: int = 20261011
    timeout: float = 120
    rpc_turns: int = 20
    long_turns: int = 1000
    calibrate: bool = True
    calibration_rounds: int = MIN_ROUNDS
    allow_noisy: bool = False
    allow_short: bool = False
    allow_frequency_scaling: bool = False
    hardware_claim: str = "shared"
    site: dict = field(default_factory=dict)
    out: str = "run"
    command: list = field(default_factory=list)
    params: dict = field(default_factory=dict)   # workload parameters (stream sizes, session turns, soak minutes ...)
    cache_dir: str = ""
    work_dir: str = ""
    offline: bool = False
    npm_cache: str = ""                  # the npm cache an npm arm installs from (a bundle's npm-cache/); empty: a fresh one in the workspace
    meter: str = "auto"
    source_repos: dict = field(default_factory=dict)
    api: str = "openai-completions"      # the wire API of the sample being taken; the engine sets it per variant
    env: str = "native"                  # the environment of the durable sample being taken (a durable workload's variant axis, in place of the wire API); the engine sets it per variant
    envs: list = field(default_factory=lambda: [workloads.NATIVE])   # the environments the durable workloads run in (`--env`); only native is built
    lock_file: str = quietlib.DEFAULT_LOCK  # Buffon's own exclusive host lock: one measurement per host
    lock_files: list = field(default_factory=list)   # locks of other benchmark tools that must be free (or inherited)
    slot: dict = None                    # a session in one slot of a host that runs several at once (buffon/runner/slots.py): {"id", "of", "cpus", "calibration": path or None}
    slot_others: list = field(default_factory=list)  # the CPUs of the other slots: online, busy with other sessions, never housekeeping
    quiet_max_busy: float = 0.10         # the pinned CPUs may be at most this busy before a sample
    quiet_timeout_s: float = 300.0
    quiet_max_runnable: int = 0          # other runnable threads allowed on the pinned CPUs before a sample
    quiet_max_steal: float = 0.02
    quiet_max_psi: float = 10.0          # CPU pressure, some avg10, percent
    quiet_gate: bool = True
    isolation: str = "none"             # "container": every arm runs in the shared envelope (buffon/envelope); "pod-guaranteed": the session's Kubernetes pod is the envelope (buffon/envelope/pod.py); "none": uncontained, stamped not comparable
    clock_claim: str = ""               # "hypervisor": the site says the platform fixes the clock and turbo state (a VM with no cpufreq interface); a claim, not a measurement
    host_claim: str = "B"               # what the site says about the host: "A" = dedicated (preflight checks the claim)
    require_class: str = None             # "A" or "B": refuse when the host is a lower class
    observers: list = field(default_factory=list)   # buffon.runner.hooks.Observer instances (docs/HOOKS.md)
    backend: str = "local"
    reference: str = "pi-node"          # the reference arm (docs/DESIGN.md section 3): calibration runs on it when it is selected
    strict: bool = False                # the old refusals: a noisy calibration, a scaling clock, a preflight refusal, too few rounds stop the run. Off: each becomes a label on the run's trust badge (buffon/trust.py)
    adaptive: bool = False              # per variant, stop taking rounds once the answer is known (buffon/runner/adaptive.py); `rounds` is then the most a variant takes
    adaptive_min: int = adaptivelib.MIN_ROUNDS
    memory_mib: int = 4096              # --isolation container: the memory limit of every harness container (a tier: 1, 2, 4 or 8 GiB); the same for every arm of a run

    @property
    def can_pin(self):
        """Whether this run pins processes: the policy allows it and the platform has sched_setaffinity (macOS has not: such a run is unpinned and labelled PROVISIONAL)."""
        return self.pinning != "none" and hasattr(os, "sched_setaffinity")

    @property
    def vm_cpus(self):
        """True when `cpus` are the CPUs of the container runtime's virtual machine, not of this host: a platform that cannot pin (macOS, where Docker runs in a VM) with
        `--isolation container` hands `cpus` to `--cpuset-cpus`, which pins inside the VM. The host itself still cannot pin, so the run is labelled PROVISIONAL."""
        return self.isolation == "container" and bool(self.cpus) and self.pinning != "none" and not hasattr(os, "sched_setaffinity")

    def rounds_of(self, workload):
        """The measured rounds a workload takes: the run's, unless the workload has a default of its own (`Workload.rounds`) and the operator did not give --rounds."""
        return self.rounds if self.rounds_set or not workload.rounds else min(self.rounds, workload.rounds)

    def wants_aa(self, workload):
        """Whether a workload runs on the A/A copies: it does unless the workload has none by default (`Workload.aa`) and the operator did not give --aa."""
        return self.aa_set or workload.aa

    @property
    def aa_effective(self):
        """`aa`, or `none` when no workload of the plan runs on A/A copies (a scale-only run installs no copies)."""
        return self.aa if any(self.wants_aa(w) for w in self.workloads) else "none"

    def validate(self):
        if self.strict and not self.allow_short and not self.adaptive and self.rounds < MIN_ROUNDS:
            raise Refused(f"{self.rounds} measured rounds is below the minimum of {MIN_ROUNDS}; a smaller run needs --allow-short and is labelled as not a measured run")
        if self.rounds < 1:
            raise Refused("rounds must be at least 1")
        if self.pinning == "required" and not self.cpus:
            raise Refused("this site requires pinning but names no harness CPUs")
        if self.pinning == "required" and not hasattr(os, "sched_setaffinity") and not self.vm_cpus:
            raise Refused("this site requires pinning but this platform cannot pin processes (no sched_setaffinity): use a Linux host or set pinning = \"preferred\"")
        allowed = set(factlib.allowed_cpus())
        missing = sorted(set(self.mock_cpus) - allowed) if self.vm_cpus else sorted((set(self.cpus) | set(self.mock_cpus)) - allowed)   # a VM's CPU ids are not this host's: the runtime refuses ones the VM lacks
        if missing:
            raise Refused(f"CPUs {missing} are not available to this process (allowed: {sorted(allowed)[:8]}...): the site profile names CPUs this machine or pod does not give it")
        if set(self.cpus) & set(self.mock_cpus):
            raise Refused("the harness CPUs and the mock's CPUs overlap")
        if self.aa not in ("all", "none") and not all(self.aa.split(",")):
            raise Refused("--aa takes all, none or arm ids")
        later = [e for e in self.envs if e != workloads.NATIVE]
        if later:
            raise Refused(f"environment {', '.join(later)} is reserved for a later phase of the durable family (docs/design/DURABLE.md section 5): only native runs today")


def with_twins(arms, aa, ws=None):
    """The arms plus an A/A copy `<id>-b` of each selected arm: the same executable, installed as its own copy under its own root (`ws.clone`) and run as its own arm."""
    ids = {a.id for a in arms} if aa == "all" else set() if aa == "none" else set(aa.split(","))
    unknown = ids - {a.id for a in arms}
    if unknown:
        raise Refused(f"--aa names arms that are not selected or installed: {', '.join(sorted(unknown))}")
    out = list(arms)
    for a in arms:
        if a.id in ids:
            twin = ws.clone(a, a.id + "-b") if ws is not None else copy.copy(a)
            twin.id, twin.label, twin.twin_of = a.id + "-b", a.label + " (A/A copy)", a.id
            out.append(twin)
    return out


def run_reasons(plan, installed, instances, egress_mode, facts):
    """What makes this run PROVISIONAL beyond the hardware detection: an arm without an A/A copy, no egress audit, a runner checkout that is not its commit."""
    reasons = []
    missing_aa = sorted(a.id for a in installed if not any(i.twin_of == a.id for i in instances))
    if missing_aa and (plan.aa_set or plan.aa_effective != "none"):
        reasons.append(f"no A/A copy of {', '.join(missing_aa)} (--aa {plan.aa}): those arms have no noise floor in this run")
    if egress_mode.get("mode") == "none":
        reasons.append("egress audit unavailable on this OS (no /proc, no lsof): run refused for publication")
    if getattr(plan, "vm_cpus", False):
        reasons.append("this platform cannot pin processes (no sched_setaffinity): the site's CPUs are the container VM's, pinned inside the VM by --cpuset-cpus; the host's own processes (the runner, the mock) are not pinned")
    elif (getattr(plan, "cpus", None) or getattr(plan, "mock_cpus", None)) and not hasattr(os, "sched_setaffinity"):
        reasons.append("this platform cannot pin processes (no sched_setaffinity): the CPUs the site names were not used")
    if facts.get("runner_dirty"):
        reasons.append("the runner's checkout has uncommitted changes, so its commit does not describe the code that ran")
    return reasons


def effective_clock_claim(claim, vm=None):
    """(claim the run honours, why a claim was not honoured). `hypervisor` says a virtual machine's platform fixes the clock: it is honoured only on a machine that shows it is a virtual
    machine, because bare metal without a cpufreq driver also reads as "nothing readable" and may run with turbo on."""
    if claim != "hypervisor":
        return claim, None
    sign = (vm or factlib.virtual_machine)()
    if sign:
        return claim, None
    return "", "the site claims a virtual machine (clock_claim = hypervisor) but this machine shows no sign of one (no hypervisor CPU flag, systemd-detect-virt says none): the clock is unverified"


def check_arm_code(arm, mount_type=textmaps.mount_type):
    """Refused when an installed arm's executable (its real path) or a runtime directory on its PATH is on tmpfs or ramfs. The work-directory check does not cover them: a source-built
    binary lives in the site's cache directory, and a sample shorter than the text sampler's first reading records no text_fs at all."""
    for path in [arm.binary, *getattr(arm, "path_dirs", [])]:
        if not path:
            continue
        fs = mount_type(os.path.realpath(path))
        if fs in textmaps.BAD_FS:
            raise Refused(f"{arm.id}: {os.path.basename(path)} is on {fs}: code mapped from memory-backed storage counts as the process's own footprint; put the site's cache_dir and work_dir on disk")
    return True


def check_work_dir(path, mount_type=textmaps.mount_type):
    """The file system type of the work directory (None where it cannot be told); Refused on tmpfs or ramfs: every arm's binaries, HOME and runtime caches are laid out there, and code mapped from
    memory-backed storage counts as the process's own footprint."""
    fs = mount_type(path)
    if fs in textmaps.BAD_FS:
        raise Refused(f"the work directory {path} is on {fs}: every arm's binaries, HOME and runtime caches are laid out there, and code mapped from memory-backed storage counts as the process's own "
                      "footprint. Point [local] work_dir (or TMPDIR) at a disk directory.")
    return fs


def perf_facts(isolation):
    """The run's instruction-counter facts (raw.json run.perf): what this host allows, or why the container envelope gives none. Instructions are the headline CPU metric where available (docs/METHODOLOGY.md)."""
    if isolation == "container":
        return {"available": False, "scope": None, "paranoid": perfcount.paranoid(), "reason": "the container envelope starts the harness through the container runtime: no counter is attached to its tree, so CPU time is the headline for this run"}
    return perfcount.probe()


def home_proof(harnesses):
    """The isolation record of the homes a sample used (one per harness): fresh only when every one was created new, the first one's digests, and how many homes the sample had."""
    proofs = [h.home_proof() for h in harnesses if hasattr(h, "home_proof")]
    if not proofs:
        return None
    first = dict(proofs[0])
    first["fresh"] = all(p["fresh"] for p in proofs)
    first["homes"] = len(proofs)
    return first


class SkipReason(str):
    """Why a sample was skipped; the arm sits the variant out for the rest of the run."""


def units(variants_):
    """[[(workload, api)]]: a variant is a unit of its own."""
    return [[v] for v in variants_]


def rotate(items, k):
    n = len(items)
    return [items[(i + k) % n] for i in range(n)] if n else []


def arm_order(arms, k, rnd):
    """The arms of one variant in one round: arms rotate as units, an arm and its A/A copy stay adjacent, and the copy goes first in odd rounds (so neither copy always runs first, and
    neither is always the one that finds the page cache cold)."""
    units, at = [], {}
    for a in arms:
        base = a.twin_of or a.id
        if base in at:
            units[at[base]].append(a)
        else:
            at[base] = len(units)
            units.append([a])
    out = []
    for unit in rotate(units, k):
        out += sorted(unit, key=lambda a: bool(a.twin_of) != bool(rnd % 2))
    return out


def effective_apis(plan, instances):
    """The wire APIs a run varies over: the operator's list, plus OpenAI Responses when a selected arm speaks neither Chat Completions nor Messages (Codex CLI), so that arm and
    the reference share one API to be compared on. Arms that speak no selected API get a "cannot run" row, never a silent omission."""
    apis = list(plan.apis)
    if not plan.apis_explicit and RESPONSES not in apis:
        if any(not a.twin_of and not any(a.supports_api(x) for x in APIS) and a.supports_api(RESPONSES) for a in instances):
            apis.append(RESPONSES)
    return apis


def variants(plan_workloads, apis, envs=(workloads.NATIVE,)):
    """[(workload, variant)]: a workload runs once per wire API it varies over and the plan selects; a workload whose apis are (None,) does not depend on the API and runs once.
    A durable workload (`envs` set) varies over environments instead: its variant is None for the native environment (the same cell key a workload with no variant has) and the
    environment's name for another, which then lands in a cell of its own (buffon/report/cells.py `variant`)."""
    out = []
    for w in plan_workloads:
        if w.envs:
            out += [(w, None if env == workloads.NATIVE else env) for env in envs if env in w.envs]
            continue
        if w.apis == (None,):
            out.append((w, None))
            continue
        for api in apis:
            if api in w.apis:
                out.append((w, api))
    return out


class Runner:
    """The state of one run: installed arms, the mock, samples, and what the report needs."""

    def __init__(self, plan, repo_root=manifest.ROOT, log=print):
        self.plan, self.repo_root, self.log = plan, repo_root, log
        self.samples, self.skipped, self.violations = [], [], []
        self.isolation = {}
        self.limits = {}
        self.gate, self.gate_stats = None, {"waits": 0, "max_wait_ms": 0, "timeouts": 0}
        self.last_save = 0.0
        self.obs = hooks.Observers(plan.observers)
        self.run_info = None
        self.lock_holder = None
        self.envelope_record = None
        self.preflight = None
        self.sysinfo = None
        self.durable = None        # the durable family's prepared state (fixtures, gate, floors): buffon/durable/prepare.py
        self.adaptive_stops = {}   # "scenario|api" -> {"rounds", "reason", "verdicts"} for each variant adaptive stopping ended early
        self.adaptive_minimum = {}   # "scenario|api" -> the rounds that variant had to take before it could settle (buffon/runner/adaptive.py min_rounds)
        self.pod_start, self.pod_reasons = None, []   # isolation pod-guaranteed: the pod facts at the start and the envelope guarantees that failed

    def workspace(self):
        """The workspace the arms install into: the plan's download cache (offline in a bundle pod) and npm cache."""
        p = self.plan
        return install.Workspace(install.Cache(p.cache_dir, offline=p.offline), work_dir=p.work_dir or None, npm_cache=p.npm_cache or None)

    # -- pinning ------------------------------------------------------------------------------------------------------------------------------

    def apply_pinning(self):
        p = self.plan
        if not p.can_pin:
            cgroup.set_pinned_cpus(None)
            return
        cgroup.set_pinned_cpus(p.cpus or None)
        if p.mock_cpus:
            os.sched_setaffinity(0, p.mock_cpus)  # the runner and the mock's threads; harness processes are pinned by the meters

    # -- run ----------------------------------------------------------------------------------------------------------------------------------

    def run(self):
        """Measure, strictly serially: one buffon run per host (an exclusive lock), one harness process at a time, and a quiet-host check before every sample."""
        self.plan.validate()
        try:
            with quietlib.HostLock(self.plan.lock_file, self.plan.lock_files, shared=[quietlib.DEFAULT_LOCK] if self.plan.slot else ()) as held:
                self.lock_holder = held.holder()
                try:
                    return self._run()
                finally:
                    cgroup.CONTAINER = None
        except quietlib.LockHeld as error:
            raise Refused(str(error)) from None

    def quiet_wait(self):
        """Wait until the pinned CPUs and the host are quiet; returns (fields for the sample record, ok). Without a gate (not started) the fields are empty and ok."""
        gate = getattr(self, "gate", None)
        if gate is None:
            return {}, True
        reading, waited, ok = gate.wait()
        self.gate_stats["waits"] += waited > 1000 * gate.window_s * 4
        self.gate_stats["max_wait_ms"] = max(self.gate_stats["max_wait_ms"], waited)
        self.gate_stats["timeouts"] += not ok
        return dict(reading, quiet_wait_ms=waited), ok

    def _run(self):
        p = self.plan
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        pinned = p.cpus if p.can_pin else []
        # Facts first: after apply_pinning this process runs on the mock's CPUs only, and `cpus_allowed` must be the CPUs the machine or pod gives
        # the session (the Kubernetes exclusive-core check compares it with the requested count).
        facts = factlib.collect(self.repo_root, pinned, p.mock_cpus if pinned else [])
        if p.isolation == podlib.MODE:
            self.pod_start, self.pod_reasons = podlib.check()
            self.log("buffon: isolation pod-guaranteed" + (": the pod is not the envelope: " + "; ".join(self.pod_reasons) if self.pod_reasons else ": the pod holds P1-P5"))
        self.apply_pinning()
        if p.meter != "auto":
            os.environ["BUFFON_METER"] = p.meter
        facts["load_before"] = list(os.getloadavg())
        self.run_info = hooks.RunInfo(p, facts, p.backend)
        self.obs_start = self.obs.run_start(self.run_info) if self.obs else {}
        self.gate_stats = {"waits": 0, "max_wait_ms": 0, "timeouts": 0}
        self.gate = quietlib.QuietGate(pinned, p.quiet_max_busy, p.quiet_timeout_s, p.quiet_max_runnable, max_steal=p.quiet_max_steal, max_psi=p.quiet_max_psi) if p.quiet_gate and pinned else None
        monitored = detect.sibling_cpus(pinned) if pinned else []
        idle_before = cpumon.idle_check(monitored) if monitored else None
        facts["idle_before"] = {str(c): round(b, 4) for c, b in (idle_before or {}).items()}
        throttle0 = facts["cgroup"].get("cpu.stat", {}).get("throttled_usec", 0)
        if facts.get("fixed_clock") is False and pinned and not p.allow_frequency_scaling and p.strict:
            scaling = [f"{c} ({g})" for c, g in facts["governors"].items() if g and g not in ("performance", "userspace")]
            raise Refused(f"the pinned CPUs scale their clock with load: {', '.join(scaling)}. CPU times would follow the clock, not the work. Use cores with a fixed clock, or pass --allow-frequency-scaling for a run that is reported but labelled PROVISIONAL")
        cpuset = pinned or (list(p.cpus) if p.vm_cpus else [])
        if p.isolation == "container" and not cpuset:
            raise Refused("--isolation container needs pinned CPUs (a cpuset): add cpus to your site profile (copy sites/example-local.toml to sites/mine.toml, set cpus, and run with --site mine)")
        self.clock_claim, self.clock_claim_refused = effective_clock_claim(p.clock_claim)
        self.preflight = preflightlib.run(pinned, p.mock_cpus if pinned else [], claim=p.host_claim, clock_claim=self.clock_claim, reserved=p.slot_others)
        self.log("buffon: host class " + self.preflight["class"] + (": " + "; ".join(self.preflight["reasons"]) if self.preflight["reasons"] else ""))
        if self.preflight["refusals"] and not p.allow_noisy and p.strict:
            raise Refused("preflight: " + "; ".join(self.preflight["refusals"]) + ". Pass --allow-noisy for a run that is recorded and labelled PROVISIONAL.")
        if p.require_class and not preflightlib.satisfies(self.preflight, p.require_class):
            raise Refused(f"this host is class {self.preflight['class']}, the run requires class {p.require_class}: " + "; ".join(self.preflight["reasons"]))
        self.sysinfo = sysinfo.collect(pinned, p.mock_cpus if pinned else [])
        self.sysinfo["host_class"] = self.preflight["class"]
        selected = [a for a in p.arms]
        with self.workspace() as ws:
            self.work_fs = check_work_dir(ws.work)
            installed = []
            for arm in selected:
                self.log(f"buffon: installing {arm.id} {arm.version}")
                ws.install(arm, source_repos=p.source_repos)
                if arm.skip:
                    self.log(f"buffon: {arm.id} cannot run: {arm.skip}")
                    self.skipped.append({"arm": arm.id, "scenario": "*", "reason": arm.skip})
                else:
                    check_arm_code(arm)   # review: the binary and runtimes, which the work-dir check and a short sample's text sampler can both miss
                    installed.append(arm)
            if not installed:
                raise Refused("no arm is available on this machine")
            refused = None
            instances = with_twins(installed, p.aa_effective, ws)
            arm_facts = self.arm_facts(ws, installed, instances)
            monitor = cpumon.Monitor(pinned).start() if pinned else None
            self.perf = perf_facts(p.isolation)
            cgroup.PERF = self.perf if self.perf["available"] and p.isolation != "container" else None
            sock = os.path.join(ws.root, "mock.sock") if p.isolation == "container" else None
            with MockServer(sink=reqlog.RequestLog(os.path.join(p.out, "mock-requests")), unix_path=sock) as server:
                if p.isolation == "container":
                    node = {preflightlib._node_of(c) for c in pinned}
                    envelope_record = containerlib.configure(ws, p, self.repo_root, server, sock, cpuset, next(iter(node)) if len(node) == 1 and None not in node else 0, memory_mib=p.memory_mib)
                    self.envelope_record = envelope_record
                ctx = Ctx(ws.work, server, p)
                equivalence, calibration, refused = self.gates(ctx, installed, instances)
                try:
                    if not refused:
                        self.measure(ctx, instances)
                finally:
                    cgroup.PERF = None
            cpu_summary = monitor.stop() if monitor else None
            self.recheck_executables(instances, arm_facts)
        facts["load_after"] = list(os.getloadavg())
        idle_after = cpumon.idle_check(monitored) if monitored else None
        facts["idle_after"] = {str(c): round(b, 4) for c, b in (idle_after or {}).items()}
        throttled = factlib.cgroup_files().get("cpu.stat", {}).get("throttled_usec", 0) - throttle0
        facts["throttled_usec"] = throttled
        facts["cpumon"] = cpu_summary
        quiet, reasons = detect.assess(self.site_obj(), facts, idle_before, idle_after, throttled, calibration, requested_cpus=self.plan.site.get("kubernetes", {}).get("cpus"), clock_claim=getattr(self, "clock_claim", ""))
        if self.preflight["class"] != "A":
            quiet = False
            reasons = list(reasons) + [f"host class B (shared, provisional): {'; '.join(self.preflight['reasons'])}"]
        if p.allow_noisy and calibration and not calibration["passed"]:
            quiet = False
        reasons = list(reasons)
        if p.rounds < MIN_ROUNDS and not p.adaptive:
            quiet = False
            reasons.append(f"only {p.rounds} measured rounds (minimum {MIN_ROUNDS}): not a measured run")
        if self.adaptive_stops:
            thin = sorted({v["rounds"] for v in self.adaptive_stops.values() if v["rounds"] < MIN_ROUNDS})
            if thin:
                reasons.append(f"adaptive stopping: {len([v for v in self.adaptive_stops.values() if v['rounds'] < MIN_ROUNDS])} of {len(self.adaptive_stops)} cells stopped with fewer than {MIN_ROUNDS} rounds ({thin[0]}-{thin[-1]}) because their answer was clear; the 12-round minimum applies to the Verified badge")
        if not p.can_pin or not pinned:
            quiet = False
        if self.gate_stats["waits"] or self.gate_stats["timeouts"]:
            quiet = False
            reasons.append(f"{self.gate_stats['waits']} samples waited for the host to quiet down (longest {self.gate_stats['max_wait_ms'] / 1000:.0f} s) and {self.gate_stats['timeouts']} gave up waiting")
        egress_mode = egress.describe()
        extra = run_reasons(p, installed, instances, egress_mode, facts)
        if extra:
            quiet = False
            reasons += extra
        raw = {"kind": "buffon-run",
               "run": {"started_utc": started, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "command": p.command, "seed": p.seed,
                       "workloads": [w.id for w in p.workloads], "arms": [a.id for a in installed], "aa": p.aa, "aa_set": p.aa_set, "rounds": p.rounds, "rounds_set": p.rounds_set, "workload_rounds": {w.id: p.rounds_of(w) for w in p.workloads if p.rounds_of(w) != p.rounds}, "no_aa_workloads": [w.id for w in p.workloads if not p.wants_aa(w)], "warmup": p.warmup, "apis": p.apis,
                       "adaptive": {"enabled": p.adaptive, "min_rounds": p.adaptive_min, "min_rounds_by_variant": self.adaptive_minimum, "max_rounds": p.rounds, "strict": p.strict, "stopped": self.adaptive_stops},
                       "pinning": p.pinning, "reference": p.reference, "harness_cpus": pinned, "mock_cpus": p.mock_cpus, "params": p.params,
                       "quiet_gate": {"enabled": self.gate is not None, "max_busy": p.quiet_max_busy, "timeout_s": p.quiet_timeout_s, "max_runnable": p.quiet_max_runnable, "max_steal": p.quiet_max_steal, "max_psi": p.quiet_max_psi, **self.gate_stats},
                       "lock_file": p.lock_file, "lock_files": p.lock_files, "lock_holder": self.lock_holder, **({"slot": p.slot} if p.slot else {}), "isolation": self.isolation_stamp(),
                       "host_class": self.preflight["class"], "preflight": self.preflight, "perf": getattr(self, "perf", None), "clock_claim": getattr(self, "clock_claim", "") or None, "clock_claim_refused": getattr(self, "clock_claim_refused", None), "work_fs": getattr(self, "work_fs", None),
                       **({"equivalence": {"passed": equivalence["passed"], "template_sha256": equivalence["template_sha256"], "counts": {n: {"oracle": c["oracle"], "arms": c["arms"]} for n, c in equivalence["counts"].items()}}} if equivalence and "template_sha256" in equivalence else {}),
                       **({"durable": self.durable["summary"], "env": p.envs} if self.durable else {})},
               "site": p.site,
               "hardware": {"class": "quiet-dedicated" if quiet else "provisional", "quiet_dedicated": quiet, "reasons": reasons},
               "lock_sha256": lock.lock_hash() if os.path.exists(lock.LOCK_FILE) else None,
               "runner": runner_record(facts),
               "arms": arm_facts, "calibration": calibration, "egress": dict(egress_mode, violations=self.violations), "isolation": self.isolation,
               "samples": self.samples, "skipped": self.skipped,
               "ok": not refused and not self.violations and not self.limits.get("changed_executables")}
        if self.obs:
            ends = self.obs.run_end(self.run_info, raw)
            raw["run"]["telemetry"] = {name: {"start": self.obs_start.get(name), "end": ends.get(name)} for name in {o.name for o in self.obs.observers}}
            if self.obs.errors:
                raw["run"]["telemetry_errors"] = self.obs.errors
        if refused:
            raw["refused"] = refused  # every attempt stays in the raw data (METHODOLOGY section 9): the calibration samples are in `calibration`
        rawlib.write(raw, p.out)
        import json
        with open(os.path.join(p.out, "facts.json"), "w") as f:
            json.dump(facts, f, indent=1)
        with open(os.path.join(p.out, "host.json"), "w") as f:
            json.dump(self.sysinfo, f, indent=1)
        partial = os.path.join(p.out, "raw.partial.json")
        if os.path.exists(partial):
            os.unlink(partial)
        if refused:
            raise Refused(refused)
        return raw

    def site_obj(self):
        from ..site import Site
        return Site(name=self.plan.site.get("name", "site"), hardware=self.plan.hardware_claim)

    # -- arms ---------------------------------------------------------------------------------------------------------------------------------

    def arm_facts(self, ws, installed, instances):
        out = {}
        trees = {}
        self._trees = {}
        for a in instances:
            path = ws.installed_tree(a)
            self._trees[a.id] = path
            trees[a.id] = install.tree_sha256(path) if path else None
        for a in instances:
            real = os.path.realpath(a.binary)
            out[a.id] = {"label": a.label, "relation": a.family, "claims": a.claims, "previous": a.previous, "caveat": a.caveat, "version": a.version, "twin_of": a.twin_of, "licence": a.licence, "version_line": a.version_line,
                         "executable_sha256": manifest.sha256_file(real), "executable_size": os.path.getsize(real), "footprint": ws.footprint(a),
                         "install_tree_sha256": trees.get(a.id),
                         "manifest_sha256": a.manifest_sha256, "renderer_pin": a.renderer.get("pty"), "runtime_settings": tuning.settings(a.env), "divergences": a.divergences, **a.record,
                         **({"operator_terms": a.operator_terms, "operator_terms_accepted": True} if a.operator_terms else {})}   # an arm only runs once its operator accepted the terms (cli.session_plan), so a report can label it
        out["_runtimes"] = {n: {k: v for k, v in r.items() if k != "bin"} for n, r in ws.runtimes.items()}
        return out

    def recheck_executables(self, installed, arm_facts):
        """After the run every executable, and the whole installed tree it runs from, must be what was verified at install."""
        changed = [a.id for a in installed if manifest.sha256_file(os.path.realpath(a.binary)) != arm_facts[a.id]["executable_sha256"]
                   or (self._trees.get(a.id) and install.tree_sha256(self._trees[a.id]) != arm_facts[a.id]["install_tree_sha256"])]
        if changed:
            self.limits["changed_executables"] = changed
            self.log(f"buffon: the executable of {', '.join(changed)} changed during the run")

    # -- calibration --------------------------------------------------------------------------------------------------------------------------

    def gates(self, ctx, installed, instances):
        """The checks before the first measured sample, in order: (equivalence, calibration, refusal text or None).

        Equivalence before timing: arms that load the same bench extensions (five or ten) must do the same work (buffon/runner/equivalence.py); one that does not refuses the run, and the
        calibration is not run. Then the calibration gate: the reference arm against its own A/A copy."""
        p = self.plan
        counts = equivlib.counts(p)
        equivalence = equivlib.run(self, ctx, installed, lambda arm, count: sweep_extensions(ctx, arm, count), p.out, counts) if counts else None
        if equivalence and not equivalence["passed"]:
            names = "; ".join(f"{arm} with {count} extensions: {d[0]}" for count, c in sorted(equivalence["counts"].items(), key=lambda kv: int(kv[0])) for arm, d in sorted(c["differences"].items()))
            return equivalence, None, f"the arms do not do the same work, so their timings are not comparable ({names}). The records are in equivalence.json"
        if any(w.envs for w in p.workloads):   # the durable family: its fixtures are built and its equivalence gate passes before anything is timed (buffon/durable/prepare.py)
            from ..durable import prepare
            self.durable, refusal = prepare.run(self, ctx, installed, instances)
            if refusal:
                return self.durable.get("gate"), None, refusal
        calibration = self.calibrate(ctx, instances) if p.calibrate else None
        if calibration and not calibration["passed"] and not p.allow_noisy and p.strict:
            return equivalence, calibration, (f"the calibration gate failed: the reference arm's CPU time varies by {calibration['max_cv']:.1%} between identical runs (gate {CV_GATE:.0%}). "
                                              "The host is too noisy to measure on; fix the host (see docs/RUNNING.md) or pass --allow-noisy for a run labelled PROVISIONAL")
        return equivalence, calibration, None

    def isolation_stamp(self):
        """raw.json run.isolation: the container envelope's or none's stamp; for pod-guaranteed, comparable only when the pod held P1-P5 at the start and in every
        sample (buffon/envelope/pod.py)."""
        p = self.plan
        if p.isolation == podlib.MODE:
            return podlib.stamp(self.pod_start or {}, self.pod_reasons, podlib.sample_drift(self.pod_start or {}, self.samples))
        return dict(envelope.isolation_stamp(p.isolation), **({"envelope": self.envelope_record} if self.envelope_record else {}))

    def calibrate(self, ctx, instances):
        """Run the reference arm (plan.reference, else the first arm that can print) against its own A/A copy; the CV of its CPU time must stay under CV_GATE."""
        from . import calibrate
        return calibrate.run(self, ctx, instances)

    # -- measurement ---------------------------------------------------------------------------------------------------------------------------

    def one_sample(self, ctx, workload, api, arm, rnd):
        if workload.envs:
            ctx.opts.env, ctx.opts.api = api or workloads.NATIVE, None   # a durable sample's variant is its environment (variants()); there is no wire API
        else:
            ctx.opts.api = api or arm.apis[0]  # an API-independent workload (--version) runs on the arm's first API
        t0 = time.monotonic()
        ctx.server.context = {"arm": arm.id, "scenario": workload.id, "api": api, "round": rnd, "warmup": rnd < self.plan.warmup}
        host, quiet_ok = self.quiet_wait()
        if not quiet_ok and not self.plan.strict:   # a host that never went quiet: take the sample anyway and label it (trust badge Noisy); only --require-class A refuses
            host = dict(host, quiet_gave_up=True, quiet_note=f"the pinned CPUs were not quiet within {self.plan.quiet_timeout_s:.0f} s ({'; '.join(self.gate.reasons(host)) or 'no reason recorded'}); the sample was taken anyway")
            self.log(f"buffon: {arm.id} {workload.id}: the host was not quiet within {self.plan.quiet_timeout_s:.0f} s; sampling anyway, the run is labelled Noisy")
            quiet_ok = True
        if not quiet_ok:
            rec = {"arm": arm.id, "scenario": workload.id, "api": api, "round": rnd, "warmup": rnd < self.plan.warmup, "t_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "quiet_gave_up": True, "failure": f"the pinned CPUs were not quiet within {self.plan.quiet_timeout_s:.0f} s ({'; '.join(self.gate.reasons(host)) or 'no reason recorded'}); no process was started"}
            rec.update(host)
            if arm.twin_of:
                rec["twin_of"] = arm.twin_of
            if self.pod_start is not None:
                rec["pod"] = podlib.sample_facts(self.pod_start)
            return rec, None
        window = hooks.Window(self.run_info, arm.id, workload.id, api, rnd, rnd < self.plan.warmup, host) if self.obs and self.run_info else None
        states = self.obs.sample_begin(window) if window else None
        cgroup.take_sched()   # a meter closed outside a sample (an arm check, a probe) is not this sample's
        wire_before = wire.mark(ctx.server)
        try:
            sample = workload.fn(ctx, arm)
        except Skip as why:
            if window:
                self.obs.sample_end(window, states, {"skipped": str(why)})
            ctx.release()
            return None, SkipReason(str(why))
        except Exception as error:  # a crash of a workload is a recorded failure, never a silent drop
            sample = {"failure": f"runner error: {error!r}", "traceback": "".join(traceback.format_exception(error))[-800:]}
        finally:
            ctx.server.flush_log()
        if "failure" not in sample:
            wire.apply(sample, ctx.server, wire_before, arm)
        else:
            sample.pop(wire.KEY, None)
        if getattr(ctx, "isolation_capture", True) and ctx.harnesses_for(arm):
            self.isolation.setdefault(arm.id, ctx.harnesses_for(arm)[0].isolation_env())
        home = home_proof(ctx.harnesses_for(arm))
        ctx.release()
        sched = cgroup.take_sched()
        text = cgroup.take_text(getattr(ctx, "work", None))
        left = sorted(egress.take())
        if left:
            note = f"egress: the harness connected to {', '.join(left)}"
            self.violations.append({"arm": arm.id, "scenario": workload.id, "api": api, "round": rnd, "remotes": left})
            sample = {"failure": note}
        if text and text["bad"] and "failure" not in sample:
            sample = {"failure": "shared-memory text: the harness ran code mapped from " + ", ".join(text["bad"][:3]) + (" ..." if len(text["bad"]) > 3 else "")
                      + " (tmpfs, ramfs or shm): the footprint would count it as the process's own memory; every arm runs its binaries and runtime caches from disk"}
        series = sample.pop("_series", None)
        rec = {"arm": arm.id, "scenario": workload.id, "api": api, "round": rnd, "warmup": rnd < self.plan.warmup, "t_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if arm.twin_of:
            rec["twin_of"] = arm.twin_of
        rec.update(sample)
        rec.update(host)
        if home is not None:
            rec["home"] = home   # proof that the sample ran in a fresh home: what it held before and after the process (docs/METHODOLOGY.md)
        if text is not None:
            rec["text_fs"] = text   # the file system of every executable mapping of the sample's process tree
        if sched is not None:
            rec["sched"] = sched   # recorded beside the metrics, never one: the report and the gates read only flat numbers
        if self.pod_start is not None:
            rec["pod"] = podlib.sample_facts(self.pod_start)   # the node, cpuset and QoS this sample ran with
        if series is not None:
            rec["series"] = series
        rec["wall_s"] = round(time.monotonic() - t0, 2)
        if window:
            telemetry = self.obs.sample_end(window, states, rec)
            if telemetry:
                rec["telemetry"] = telemetry
        return rec, None

    def measure(self, ctx, instances):
        p = self.plan
        order = variants([w for w in p.workloads if not w.special], effective_apis(p, instances), p.envs)
        streak, out = {}, set()
        total = p.warmup + p.rounds
        settled = set()   # (workload id, api) variants adaptive stopping has ended
        for rnd in range(total):
            live = [v for v in order if (v[0].id, v[1]) not in settled and rnd < p.warmup + p.rounds_of(v[0])]
            if not live:
                break
            for vi, (workload, api) in enumerate(v for unit in rotate(units(live), rnd) for v in unit):
                alive = [a for a in instances if (a.id, workload.id, api) not in out and (not a.twin_of or p.wants_aa(workload))]
                for arm in arm_order(alive, rnd + vi, rnd):
                    rec, why = self.one_sample(ctx, workload, api, arm, rnd)
                    key = (arm.id, workload.id, api)
                    if rec is None:
                        self.skipped.append({"arm": arm.id, "scenario": workload.id, "api": api, "reason": why})
                        out.add(key)
                        continue
                    self.samples.append(rec)
                    label = f"{workload.id:28} {(api or '-'):20} {arm.id:12} round {rnd + 1}/{p.warmup + p.rounds_of(workload)}{' (warm-up)' if rnd < p.warmup else ''}"
                    if "failure" in rec:
                        streak[key] = streak.get(key, 0) + 1
                        self.log(f"buffon: {label} FAILED: {rec['failure'][:200]}")
                        if streak[key] >= GIVE_UP_AFTER:
                            out.add(key)
                            self.log(f"buffon: {arm.id} gave up on {workload.id} ({api}) after {GIVE_UP_AFTER} consecutive failures")
                    else:
                        streak[key] = 0
                        self.log(f"buffon: {label} {rec['wall_s']:.1f}s")
                    self.checkpoint()
            if p.adaptive and rnd + 1 - p.warmup >= p.adaptive_min and rnd + 1 < total:
                self.settle(live, instances, rnd + 1 - p.warmup, settled, out)
        for workload in [w for w in p.workloads if w.special]:
            self.log(f"buffon: {workload.id}")
            workload.special(self, ctx, instances)
            self.checkpoint(force=True)
        for workload in [w for w in p.workloads if w.finish]:   # metrics that need several samples (buffon/workloads/durable.py)
            workload.finish(self)

    def settle(self, live, instances, taken, settled, out):
        """Adaptive stopping after a round: end every variant whose answer is known (buffon/runner/adaptive.py), and say so."""
        ids = [a.id for a in instances]
        for workload, api in live:
            done, verdicts, metric = adaptivelib.variant_status(self.samples, workload.id, api, self.plan.reference, ids)
            minimum = self.adaptive_minimum[f"{workload.id}|{api}"] = adaptivelib.variant_minimum(self.samples, workload.id, api, self.plan.reference, ids)
            if done:
                settled.add((workload.id, api))
                self.adaptive_stops[f"{workload.id}|{api}"] = {"rounds": taken, "min_rounds": minimum, "metric": metric, "verdicts": verdicts, "reason": "answer clear" if verdicts else "nothing to compare"}
                self.log(f"buffon: {workload.id} ({api or '-'}) settled after {taken} rounds on {metric}: " + (", ".join(f"{a} {v}" for a, v in sorted(verdicts.items())) or "no comparison"))


    def checkpoint(self, force=False):
        now = time.monotonic()
        if not force and now - self.last_save < 20:
            return
        self.last_save = now
        raw = {"kind": "buffon-run", "run": {"partial": True}, "site": self.plan.site, "hardware": {}, "lock_sha256": None, "runner": {}, "arms": {}, "calibration": None,
               "egress": {}, "isolation": {}, "samples": self.samples, "skipped": self.skipped, "ok": False}
        rawlib.write(raw, self.plan.out, "raw.partial.json")


def run_session(plan, repo_root=manifest.ROOT, log=print):
    """Run a whole plan; returns the raw dict (also written to plan.out/raw.json)."""
    return Runner(plan, repo_root, log).run()


def runner_record(facts):
    """raw.json's runner block: the checkout's commit, tree and dirtiness; a run from a bundle adds the sha256 of the bundle's ARTIFACTS.sha256."""
    out = {"commit": facts["runner_commit"], "tree": facts["runner_tree"], "dirty": facts["runner_dirty"], "diff_sha256": facts.get("runner_diff_sha256")}
    if facts.get("runner_bundle_sha256"):
        out["bundle_sha256"] = facts["runner_bundle_sha256"]
    return out
