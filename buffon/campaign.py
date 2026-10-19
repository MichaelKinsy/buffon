# SPDX-License-Identifier: Apache-2.0
"""`buffon campaign`: one measured campaign on a Kubernetes site, from a plan file (docs/RUNNING.md, "Campaigns").

A campaign is the whole measured part of a cluster window, written down before the window opens, so that it starts as soon as the cluster answers:

    1. check the plan, the site and the bundle (built once into <out>/bundle, or given with --bundle);
    2. wait for the cluster to answer (--wait-cluster), then the noise floor of the nodes: `buffon calibrate` on the plan's [calibrate] workloads;
    3. each [[family]] as its own session (`buffon run --calibration --nodes a,b`): every arm and A/A copy interleaved on one node, and the same session on a second
       node (another CPU model when one is free) as its reproduction; one family after the other, or with --parallel as many at once as there are free node
       pairs, never two sessions on one node;
    4. `buffon verify` of every run directory a family left, and `buffon compare` of its two node runs (<family>/reproduction.md): a comparison is a headline
       only when it reproduces on both nodes (docs/METHODOLOGY.md, "On a cluster").

campaign.json in the campaign directory records the plan's sha256, the bundle, and each step's exit, times, verdicts, nodes (their facts and their own calibration
noise) and reproduction totals; it is rewritten after every step. Running
the same command again resumes: a step that finished with exit 0 is not run again, and a calibration is reused only when it passed.

A local site with `[local] slots = N` (opt-in) runs the families at once on one host instead: the host's cores are split into N disjoint slots, the reference arm against
its A/A copy runs alone in one slot and then in every slot at once (slots-calibration.json), and the families run one per slot that passed, each as its own pinned session
with its own lock file (docs/METHODOLOGY.md, "Slots on one big host"). campaign.json records `slots` and the slot of each family. No passing slot: the families run serially.
"""
import hashlib
import json
import os
import re
import sys
import time
import tomllib

from . import site as sitelib
from .backend import BackendError
from .runner import slots as slotlib

EXIT_USAGE, EXIT_REFUSED = 2, 3
MIN_ROUNDS = 12
_NAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
_TABLES = {"campaign": {"name", "reference", "description"}, "calibrate": {"workloads", "rounds", "apis", "params"},
           "family": {"name", "workloads", "arms", "rounds", "apis", "params", "warmup", "timeout", "adaptive"}}
STATE = "campaign.json"


class PlanError(ValueError):
    pass


def load_plan(path):
    """Read and check a plan file. Returns (plan dict, sha256 of the file)."""
    with open(path, "rb") as f:
        data = f.read()
    try:
        doc = tomllib.loads(data.decode())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise PlanError(f"{path}: {error}") from error
    check_plan(doc)
    return doc, hashlib.sha256(data).hexdigest()


def check_plan(doc):
    """Refuse a plan the campaign could not run as a measured campaign: unknown tables or keys, a missing [campaign] name, no [calibrate] or [[family]], fewer than 12
    rounds, a family name used twice or unfit for a directory and a Job name, an unknown or held arm or an unknown workload."""
    from . import workloads
    from .arms import manifest

    unknown = sorted(set(doc) - set(_TABLES))
    if unknown:
        raise PlanError(f"unknown table(s) {', '.join(unknown)}; a plan has [campaign], [calibrate] and [[family]]")
    for table in ("campaign", "calibrate"):
        if not isinstance(doc.get(table), dict):
            raise PlanError(f"the plan has no [{table}] table")
    families = doc.get("family")
    if not isinstance(families, list) or not families:
        raise PlanError("the plan has no [[family]]")
    arms = manifest.load_all()
    sections = [("campaign", doc["campaign"]), ("calibrate", doc["calibrate"])] + [("family", f) for f in families]
    names = set()
    for table, body in sections:
        extra = sorted(set(body) - _TABLES[table])
        if extra:
            raise PlanError(f"[{table}] has unknown key(s) {', '.join(extra)}")
        where = f"[{table}]" + (f" {body.get('name')!r}" if table == "family" else "")
        if table == "campaign":
            if not isinstance(body.get("name"), str) or not _NAME.match(body["name"]):
                raise PlanError("[campaign] name must be lower-case letters, digits and dashes (at most 32)")
            ref = body.get("reference", "pi-node")
            if ref not in arms or arms[ref].held:
                raise PlanError(f"[campaign] reference {ref!r} is not a runnable arm")
            continue
        if table == "family":
            name = body.get("name")
            if not isinstance(name, str) or not _NAME.match(name) or name in ("bundle", "calibrate", "perfcheck"):
                raise PlanError(f"{where}: a family name is lower-case letters, digits and dashes (at most 32), and not bundle, calibrate or perfcheck")
            if name in names:
                raise PlanError(f"{where}: two families share the name")
            names.add(name)
            wanted = body.get("arms")
            if not isinstance(wanted, list) or not wanted or not all(isinstance(a, str) for a in wanted):
                raise PlanError(f"{where}: arms must name at least one arm")
            bad = [a for a in wanted if a not in arms or arms[a].held]
            if bad:
                raise PlanError(f"{where}: {', '.join(bad)} is not a runnable arm")
        work = body.get("workloads")
        if not isinstance(work, list) or not work or not all(isinstance(w, str) for w in work):
            raise PlanError(f"{where}: workloads must name at least one workload")
        try:
            workloads.resolve(work)
        except KeyError as error:
            raise PlanError(f"{where}: {error.args[0]}") from None
        rounds = body.get("rounds", MIN_ROUNDS)
        if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < MIN_ROUNDS:
            raise PlanError(f"{where}: rounds must be an integer of at least {MIN_ROUNDS}; a campaign is a measured run")
        if "apis" in body and (not isinstance(body["apis"], list) or not all(isinstance(a, str) for a in body["apis"])):
            raise PlanError(f"{where}: apis must be a list of wire API names")
        if "params" in body and not isinstance(body["params"], dict):
            raise PlanError(f"{where}: params must be a table")
        if "adaptive" in body and (table != "family" or not isinstance(body["adaptive"], bool)):
            raise PlanError(f"{where}: adaptive is true or false, on a family only")


def family_argv(cmd, body, site_ref, out, reference, bundle_dir, calibration=None):
    """The `buffon run` / `buffon calibrate` argv for one step of the plan."""
    argv = [cmd, *body["workloads"], "--out", out, "--rounds", str(body.get("rounds", MIN_ROUNDS)), "--reference", reference]
    if site_ref:
        argv += ["--site", site_ref]
    if cmd == "run":
        argv += ["--arms", *body["arms"]]
        if "warmup" in body:
            argv += ["--warmup", str(body["warmup"])]
        if "timeout" in body:
            argv += ["--timeout", str(body["timeout"])]
        if body.get("adaptive"):
            argv += ["--adaptive"]   # rounds is then the most a cell takes; a cell stops once its answer is clear (docs/METHODOLOGY.md section 18)
    if body.get("apis"):
        argv += ["--apis", *body["apis"]]
    for key, value in sorted((body.get("params") or {}).items()):
        argv += ["--param", f"{key}={json.dumps(value) if not isinstance(value, str) else value}"]
    if calibration:
        argv += ["--calibration", calibration]
    if bundle_dir:
        argv += ["--bundle", bundle_dir]
    return argv


def plan_arms(plan):
    """Every arm the plan runs, in first-use order: the reference first (the calibration runs it), then each family's."""
    out = [plan["campaign"].get("reference", "pi-node")]
    for fam in plan["family"]:
        out += [a for a in fam["arms"] if a not in out]
    return out


def dry_run_notes(plan):
    """What `--dry-run` says besides the steps: the vendor terms an arm of the plan needs accepted (a family that names such an arm refuses to start without them) and the expected measuring
    time per family, from the same per-sample costs as `buffon up --plan`. Nothing is measured; the speed probe runs a few process starts (about a second)."""
    from .arms import manifest
    from .up import estimate, machine, selection
    arms = manifest.load_all()
    notes = []
    gated = [a for a in plan_arms(plan) if arms[a].operator_terms]
    if gated:
        missing = [a for a in gated if a not in manifest.accepted_terms()]
        notes.append(f"vendor terms: {', '.join(gated)} run only under their vendors' terms (`python3 -m buffon harnesses` quotes them); "
                     + (f"set {manifest.ACCEPT_ENV}={','.join(missing)} to accept them" if missing else "accepted"))
    paths = machine.paths()
    probe = estimate.cached_probe(paths["probe"])
    est = estimate.estimate_campaign(plan, probe, estimate.load_history(paths["timings"]))
    notes += [f"expected measuring time {name}: {selection.format_duration(seconds)}" for name, seconds in est["families"].items()]
    notes.append(f"expected measuring time, all families: {selection.format_duration(est['total_s'])} on this machine, which the probe finds {probe['speed']:.1f}x the reference laptop's per-process cost (an estimate: every arm is counted in every workload of its family, with its A/A copy; installs and the perf check are not counted)")
    return notes


class Campaign:
    """One campaign directory and its state file."""

    def __init__(self, out, plan, plan_sha256, plan_path, site_ref, log=print, now=time.time):
        self.out, self.plan, self.plan_sha256, self.plan_path, self.site_ref, self.log, self.now = out, plan, plan_sha256, plan_path, site_ref, log, now
        self.state = self._load()
        import threading
        self.lock = threading.Lock()

    def _load(self):
        path = os.path.join(self.out, STATE)
        if not os.path.exists(path):
            return {"plan": self.plan_path, "plan_sha256": self.plan_sha256, "name": self.plan["campaign"]["name"], "steps": {}}
        with open(path) as f:
            state = json.load(f)
        if state.get("plan_sha256") != self.plan_sha256:
            raise PlanError(f"{self.out} holds a campaign of another plan (sha256 {str(state.get('plan_sha256'))[:12]}); resume it with that plan or use a new --out")
        return state

    def save(self):
        os.makedirs(self.out, exist_ok=True)
        path = os.path.join(self.out, STATE)
        with open(path + ".tmp", "w") as f:
            json.dump(self.state, f, indent=2, sort_keys=True)
        os.replace(path + ".tmp", path)

    def done(self, step):
        return (self.state["steps"].get(step) or {}).get("exit") == 0

    def record(self, step, **fields):
        with self.lock:   # parallel families record from their own threads
            self.state["steps"].setdefault(step, {}).update(fields)
            self.save()


def wait_for_cluster(backend, seconds, log, sleep=None, now=None, every=30.0):
    """Ask the cluster which nodes can take a pod until it answers or `seconds` pass. Returns (True, ranking) or (False, the last error)."""
    sleep, now = sleep or time.sleep, now or time.monotonic
    deadline = now() + seconds
    while True:
        code, answer = backend.nodes()
        if code == 0:
            return True, answer
        left = deadline - now()
        if left <= 0:
            return False, answer
        log(f"buffon campaign: the cluster does not answer yet ({str(answer).splitlines()[-1] if answer else code}); asking again in {min(every, left):.0f} s")
        sleep(min(every, left))


def set_aside(out, name):
    """Move an unfinished attempt's directory (and log) of a family to <name>.attempt-<k>, so that this attempt is verified on what it wrote itself, never on node
    directories the attempt before left. Returns the new path, or None when there was nothing."""
    run_dir = os.path.join(out, name)
    if not os.path.exists(run_dir):
        return None
    k = 1
    while os.path.exists(os.path.join(out, f"{name}.attempt-{k}")):
        k += 1
    aside = os.path.join(out, f"{name}.attempt-{k}")
    os.rename(run_dir, aside)
    if os.path.exists(os.path.join(out, name + ".log")):
        os.rename(os.path.join(out, name + ".log"), os.path.join(aside, "campaign.log"))
    return aside


def verify_dirs(run_dir):
    """The run directories a step left: the node directories of a multi-node run, else the run directory itself, those with a raw.json."""
    path = os.path.join(run_dir, "cluster-outcome.json")
    dirs = []
    if os.path.exists(path):
        with open(path) as f:
            for o in json.load(f).get("outcomes", []):
                if o.get("dir"):
                    dirs.append(os.path.join(run_dir, o["dir"]))
    dirs = dirs or [run_dir]
    return [d for d in dirs if os.path.exists(os.path.join(d, "raw.json"))]


def verify(dirs):
    """`buffon verify` of each directory: {dir: {"accepted", "errors"}}."""
    from .submit import check
    out = {}
    for d in dirs:
        result = check.verify(d)
        out[d] = {"accepted": bool(result.accepted), "errors": [f"{c['id']}: {c['message']}" for c in result.checks if c["status"] == "error"]}
    return out


def main(args, run=None, log=print, topology=None, allowed=None):
    """Run or resume the campaign. `run` takes an argv for `python3 -m buffon` and returns its exit code (tests replace it). `topology` and `allowed` (a
    buffon.runner.slots.Topology and the CPUs the runner may use) replace what a local site with `[local] slots` reads from the host; tests give a fake host."""
    from . import backend as backendlib
    from . import cli

    run = run or run_buffon
    try:
        plan, plan_sha256 = load_plan(args.plan)
    except (OSError, PlanError) as error:
        print(f"buffon campaign: {error}", file=sys.stderr)
        return EXIT_USAGE
    s = sitelib.load(args.site)
    local = s.backend == "local"
    b = backendlib.get_backend(s)
    b.check()
    out = os.path.abspath(args.out)
    site_ref = args.site or os.environ.get("BUFFON_SITE", "")
    if site_ref and os.path.exists(site_ref):
        # A --parallel family runs as `python3 -m buffon` from the repository root: a relative path would name another file there, or fall back to sites/<name>.toml.
        site_ref = os.path.abspath(site_ref)
    try:
        c = Campaign(out, plan, plan_sha256, os.path.abspath(args.plan), site_ref, log)
    except PlanError as error:
        print(f"buffon campaign: {error}", file=sys.stderr)
        return EXIT_USAGE
    reference = plan["campaign"].get("reference", "pi-node")
    arms = plan_arms(plan)
    slot_list = []
    if local and s.local.slots > 1:   # opt-in: several sessions at once on disjoint core sets of this host (docs/METHODOLOGY.md, "Slots on one big host")
        try:
            slot_list = slotlib.partition_site(s, topology, allowed)
        except slotlib.SlotError as error:
            print(f"buffon campaign: refused: slots: {error}", file=sys.stderr)
            return EXIT_REFUSED
    cal_file = os.path.join(out, slotlib.FILE)

    bundle_dir, cache_flags = None, []
    if local and args.bundle:
        # A local site runs the plan on this machine from a bundle directory (cache/ and npm-cache/ prefilled, buffon/bundle.py): nothing is downloaded or built.
        root = os.path.abspath(args.bundle)
        try:
            from .backend import bundle as bundlelib
            meta = bundlelib.read_meta(root)
        except Exception as error:
            print(f"buffon campaign: {args.bundle} is not a finished bundle: {error}", file=sys.stderr)
            return EXIT_USAGE
        missing = [a for a in arms if a not in meta.get("arms", [])]
        if missing:
            print(f"buffon campaign: the bundle does not carry {', '.join(missing)}", file=sys.stderr)
            return EXIT_USAGE
        cache_flags = ["--offline", "--cache-dir", os.path.join(root, "cache"), "--npm-cache", os.path.join(root, "npm-cache")]
        bundle_dir = None
    if not local and s.kube.bundle:
        bundle_dir = os.path.abspath(args.bundle) if args.bundle else os.path.join(out, "bundle")
        if args.bundle or os.path.exists(os.path.join(bundle_dir, "ARTIFACTS.sha256")):
            cli.prebuilt_run_bundle(s, bundle_dir, arms)
        elif args.dry_run:
            log(f"buffon campaign: would build the bundle for linux-{s.kube.arch} with {', '.join(arms)} into {bundle_dir}")
        else:
            build_bundle(s, bundle_dir, arms, log)
        if not args.dry_run:
            from .backend import bundle as bundlelib
            meta = bundlelib.read_meta(bundle_dir)
            with open(os.path.join(bundle_dir, "ARTIFACTS.sha256"), "rb") as f:
                info = {"dir": bundle_dir, "commit": meta.get("commit"), "tree": meta.get("tree"), "arch": meta.get("arch"), "arms": meta.get("arms"),
                        "artifacts_sha256": hashlib.sha256(f.read()).hexdigest()}
            before = c.state.get("bundle")
            if before and c.state["steps"] and before.get("artifacts_sha256") != info["artifacts_sha256"]:
                # The steps that finished ran from the other bundle: a resumed campaign must not mix runner and arm builds across its families.
                print(f"buffon campaign: {out} ran its steps from the bundle {str(before.get('artifacts_sha256'))[:12]} ({before.get('dir')}), not from "
                      f"{info['artifacts_sha256'][:12]} ({bundle_dir}); resume with that bundle or use a new --out", file=sys.stderr)
                return EXIT_USAGE
            c.state["bundle"] = info
            c.save()

    cal_dir = os.path.join(out, "calibrate")
    cal_path = os.path.join(cal_dir, "calibration.json")
    perf_argv = ["perfcheck", "--out", os.path.join(out, "perfcheck")] + (["--site", site_ref] if site_ref else []) + (["--bundle", bundle_dir] if bundle_dir else [])
    steps = [("perfcheck", perf_argv)]
    if not local:   # a local run calibrates itself: its A/A gate runs in every session (docs/METHODOLOGY.md); the nodes of a cluster are calibrated against each other first
        steps.append(("calibrate", family_argv("calibrate", plan["calibrate"], site_ref, cal_dir, reference, bundle_dir)))
    steps += [(fam["name"], family_argv("run", fam, site_ref, os.path.join(out, fam["name"]), reference, bundle_dir, None if local else cal_path) + cache_flags) for fam in plan["family"]]
    if args.dry_run:
        if slot_list:
            log(f"buffon campaign: slots: {len(slot_list)} on this host, each {len(s.local.cpus)} harness CPUs and {len(slot_list[0].mock_cpus)} mock CPUs of whole physical cores")
            for slot in slot_list:
                log(f"buffon campaign:   {slot.describe()}")
        for name, argv in steps:
            if slot_list and name != "perfcheck":
                if name == steps[1][0]:
                    cal = slot_calibration_argv(plan, site_ref, os.path.join(out, slotlib.RUN_DIRS, "slot-<n>"), reference, cache_flags, "<n>")
                    log(f"buffon campaign: {'done' if c.done(SLOT_STEP) else 'step'} {SLOT_STEP}: python3 -m buffon {' '.join(cal)}   (alone in slot 1, then in every slot at once)")
                argv = argv + ["--slot", "<slot>", "--slot-calibration", cal_file]
            log(f"buffon campaign: {'done' if c.done(name) else 'step'} {name}: python3 -m buffon {' '.join(argv)}")
        if slot_list:
            log("buffon campaign: the families run at once, one per slot that passes the slot calibration (a slot that fails is not used); with no passing slot they run one after the other on the site's own CPUs")
        for note in dry_run_notes(plan):
            log(f"buffon campaign: {note}")
        if args.parallel:
            log("buffon campaign: the families run at once, each on a pair of nodes the calibration vouches for (its node and a reproduction node; --nodes <a>,<b>), no node holding two sessions; the rest wait for a free pair")
        return 0

    if args.wait_cluster and not local:
        ok, answer = wait_for_cluster(b, args.wait_cluster, log)
        if not ok:
            print(f"buffon campaign: the cluster did not answer within {args.wait_cluster:.0f} s: {answer}", file=sys.stderr)
            return EXIT_REFUSED
    def step(name, argv, nodes=None, parallel=False, slot=None):
        """Run one step (unless it finished before), verify what it left, record it; returns its exit code. A family runs on `nodes`: its node and, when there is
        a second one, its reproduction node; the two runs are then compared (reproduction.json)."""
        if c.done(name):
            log(f"buffon campaign: {name} finished before (exit 0); not run again")
            return 0
        if nodes:
            argv = argv + ["--nodes", ",".join(nodes)]
        if slot:
            argv = argv + ["--slot", str(slot), "--slot-calibration", cal_file]
        aside = set_aside(out, name) if name not in ("calibrate", "perfcheck") else None
        if aside:
            log(f"buffon campaign: {name}: the unfinished attempt before is kept in {aside}")
        c.record(name, argv=argv, nodes=nodes, slot=slot, started_utc=_utc(c.now()), finished_utc=None, exit=None, previous_attempt=aside)
        log(f"buffon campaign: {name}{' on ' + ', '.join(nodes) if nodes else ''}: python3 -m buffon {' '.join(argv)}")
        code = run(argv, os.path.join(out, name + ".log") if parallel or slot else None)
        if name == "perfcheck":
            summary = _read_json(os.path.join(out, "perfcheck", "perfcheck-summary.json"))
            c.record(name, finished_utc=_utc(c.now()), exit=code, perfcheck=summary)
            log(f"buffon campaign: perfcheck exit {code}" + "".join(f"\nbuffon campaign:   {line}" for line in (summary.get("text") or "").splitlines()))
            return code
        if name == "calibrate":
            c.record(name, finished_utc=_utc(c.now()), exit=code)
            log(f"buffon campaign: calibrate exit {code}")
            return code
        run_dir = os.path.join(out, name)
        dirs = verify_dirs(run_dir)
        verdicts = verify(dirs)
        if code == 0 and (not verdicts or not all(v["accepted"] for v in verdicts.values())):
            code = 1  # a family whose runs `buffon verify` rejects did not finish: run it again on resume
        sessions = session_facts(dirs, cal_path)
        repro = reproduction(dirs, run_dir) if len(dirs) == 2 else {"compared": False, "why": f"{len(dirs)} node run(s); a reproduction pair needs two"}
        c.record(name, finished_utc=_utc(c.now()), exit=code, verify=verdicts, sessions=sessions, reproduction=repro)
        log(f"buffon campaign: {name} exit {code}" + "".join(f"; {os.path.relpath(d, out)} {'verified' if v['accepted'] else 'REJECTED'}" for d, v in verdicts.items())
            + (f"; {repro['reproduced']} of {repro['cells']} comparisons reproduce on both nodes" if repro.get("compared") else f"; no reproduction ({repro['why']})"))
        return code

    code = step(*steps[0])
    if code not in (0, EXIT_REFUSED):   # exit 3: some node cannot count instructions; its runs headline CPU time and say why (docs/METHODOLOGY.md section 4)
        print(f"buffon campaign: the perf preflight could not run (exit {code}); {os.path.join(out, 'perfcheck')} says why", file=sys.stderr)
        return code
    if code == EXIT_REFUSED:
        log("buffon campaign: " + ("this host does not count instructions: its runs headline CPU time" if local else "not every node counts instructions: a run on such a node headlines CPU time") + " (see perfcheck-summary.json); the campaign continues")
    if local and slot_list:
        exit_code = slotted_families(c, plan, slot_list, steps[1:], run, step, site_ref, reference, cache_flags, out, log)
        if exit_code is not None:
            return exit_code
    if local:
        exit_code = 0
        for name, argv in steps[1:]:   # one host: the families run one after the other, each with its own A/A gate; there is no second node to reproduce on
            code = step(name, argv)
            exit_code = exit_code or code
        for fam in plan["family"]:
            for d in verify_dirs(os.path.join(out, fam["name"])):
                log(f"buffon campaign: render {fam['name']} with: python3 -m buffon report {d}")
        return exit_code
    code = step(*steps[1])
    if code:
        print(f"buffon campaign: the calibration did not pass (exit {code}); no family runs on nodes it does not vouch for. {cal_path} says why", file=sys.stderr)
        return code
    families = steps[2:]
    vouched = cli.calibrated_nodes(cal_path)
    if not vouched:
        log("buffon campaign: the calibration vouches for no node; no family runs")
        return EXIT_REFUSED
    pool = NodePool(vouched, node_models(cal_dir, vouched))
    if len(vouched) < 2:
        log(f"buffon campaign: the calibration vouches for one node ({vouched[0]}): no family gets a reproduction node, so no comparison can be a headline")
    exit_code = run_families(families, pool, step, log, args.parallel)
    for fam in plan["family"]:
        dirs = verify_dirs(os.path.join(out, fam["name"]))
        for d in dirs:   # one report per node: every ratio stays within one node
            log(f"buffon campaign: render {fam['name']} on {os.path.basename(d)} with: python3 -m buffon report {d}")
        if len(dirs) == 2:
            log(f"buffon campaign: {fam['name']}: the reproduction pair is compared in {os.path.join(out, fam['name'], 'reproduction.md')}")
    return exit_code


SLOT_STEP = "slots-calibration"


def slot_calibration_argv(plan, site_ref, run_dir, reference, cache_flags, slot):
    """The `buffon run` argv of one slot calibration session: the reference arm against its own A/A copy on the plan's [calibrate] workloads, without the session's own gate."""
    body = dict(plan["calibrate"], arms=[reference])
    return family_argv("run", body, site_ref, run_dir, reference, None) + cache_flags + ["--aa", reference, "--no-calibrate", "--slot", str(slot)]


def slotted_families(c, plan, slot_list, families, run, step, site_ref, reference, cache_flags, out, log):
    """The families of a local campaign on a site with `[local] slots`: calibrate the slots (reference against its A/A copy alone, then in every slot at once), then run the
    families at once, one per slot that passed. Returns the exit code, or None when no slot passed: the caller then runs the families one after the other, as a site without
    slots does, and says so."""
    from concurrent.futures import ThreadPoolExecutor
    from .runner.engine import CV_GATE

    state = [s.record() for s in slot_list]
    before = c.state.get("slots")
    if before and before != state and c.state["steps"]:
        print(f"buffon campaign: {c.out} ran with other slots ({before}) than this site gives ({state}); resume with that site or use a new --out", file=sys.stderr)
        return EXIT_USAGE
    c.state["slots"] = state
    c.save()
    verdict = slotlib.reusable(c.out, slot_list)
    if verdict:
        log(f"buffon campaign: the slot calibration passed before (slots {', '.join(map(str, verdict['usable']))}); not run again")
    else:
        started = _utc(c.now())
        verdict = slotlib.calibrate(slot_list, run, lambda slot, d: slot_calibration_argv(plan, site_ref, d, reference, cache_flags, slot), out, reference,
                                    plan["calibrate"].get("rounds", MIN_ROUNDS), CV_GATE, log, c.now)
        c.record(SLOT_STEP, started_utc=started, finished_utc=_utc(c.now()))
    usable = verdict["usable"]
    c.record(SLOT_STEP, exit=0 if usable else EXIT_REFUSED, usable=usable)
    if not usable:
        log("buffon campaign: no slot passed the slot calibration: falling back to serial, one session at a time on the site's own CPUs (" + os.path.join(out, slotlib.FILE) + " says why)")
        return None
    lost = [s.id for s in slot_list if s.id not in usable]
    if lost:
        log(f"buffon campaign: slot(s) {', '.join(map(str, lost))} failed the slot calibration and are not used")
    import threading
    free, cond = list(usable), threading.Condition()

    def one(name, argv):
        with cond:
            while not free:
                cond.wait()
            slot = free.pop(0)
        try:
            return step(name, argv, slot=slot)
        finally:
            with cond:
                free.append(slot)
                free.sort()
                cond.notify_all()
    log(f"buffon campaign: {len(families)} families, up to {min(len(usable), len(families))} at once in slots {', '.join(map(str, usable))}, one session per slot")
    with ThreadPoolExecutor(max_workers=len(usable)) as ex:
        codes = [f.result() for f in [ex.submit(one, name, argv) for name, argv in families]]
    for name, _ in families:
        for d in verify_dirs(os.path.join(out, name)):
            log(f"buffon campaign: render {name} with: python3 -m buffon report {d}")
    return next((code for code in codes if code), 0)


def run_buffon(argv, log_path=None):
    """Run `python3 -m buffon <argv>`: in this process, or (log_path given, for a session that runs beside others) as a child process whose output goes to log_path."""
    if log_path is None:
        from . import cli
        return cli.main(argv)
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(log_path, "a") as f:
        return subprocess.run([sys.executable, "-m", "buffon", *argv], cwd=root, stdout=f, stderr=subprocess.STDOUT).returncode


class NodePool:
    """The calibrated nodes, lent out in pairs: a family's node and its reproduction node, never a node to two sessions at once. The reproduction node is
    one with another CPU model when a free one has it (different hardware), else the next free node."""

    def __init__(self, nodes, models):
        import threading
        self.nodes, self.models, self.free = list(nodes), models, list(nodes)
        self.cond = threading.Condition()
        self.want = min(2, len(self.nodes))

    def take(self):
        with self.cond:
            while len(self.free) < self.want:
                self.cond.wait()
            first = self.free[0]
            others = self.free[1:]
            other = next((n for n in others if self.models.get(n) != self.models.get(first)), others[0] if others else None)
            got = [first] + ([other] if other and self.want == 2 else [])
            for n in got:
                self.free.remove(n)
            return got

    def give(self, nodes):
        with self.cond:
            self.free += [n for n in self.nodes if n in nodes]
            self.free.sort(key=self.nodes.index)
            self.cond.notify_all()


def run_families(families, pool, step, log, parallel):
    """Run each family on a pair of nodes from the pool: one after the other, or (parallel) at once, as many as there are free pairs. Returns the first non-zero
    exit in family order, else 0."""
    from concurrent.futures import ThreadPoolExecutor

    def one(name, argv):
        nodes = pool.take()
        try:
            return step(name, argv, nodes, parallel)
        finally:
            pool.give(nodes)
    workers = max(1, len(pool.nodes) // max(pool.want, 1)) if parallel else 1
    if parallel:
        log(f"buffon campaign: {len(families)} families, up to {min(workers, len(families))} at once on {len(pool.nodes)} nodes ({', '.join(pool.nodes)}), each on its own node pair")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        codes = [f.result() for f in [ex.submit(one, name, argv) for name, argv in families]]
    return next((code for code in codes if code), 0)


def node_models(cal_dir, nodes):
    """{node: CPU model} from the calibration's per-node run directories (cluster-facts.json), where present."""
    out = {}
    for n in nodes:
        for d in (os.path.join(cal_dir, n), cal_dir):
            path = os.path.join(d, "cluster-facts.json")
            if os.path.exists(path):
                with open(path) as f:
                    facts = json.load(f)
                if facts.get("node") in (None, n):
                    out[n] = facts.get("cpuModel")
                    break
    return out


def session_facts(dirs, cal_path):
    """Per node run of a family: its node facts (cluster-facts.json, node.json) and the node's own calibration (its noise per gated metric) from calibration.json."""
    try:
        with open(cal_path) as f:
            judged = {n.get("node"): n for n in json.load(f).get("nodes", [])}
    except (OSError, ValueError):
        judged = {}
    out = []
    for d in dirs:
        facts = _read_json(os.path.join(d, "cluster-facts.json"))
        api = _read_json(os.path.join(d, "node.json"))
        node = facts.get("node") or api.get("node") or os.path.basename(d)
        cal = judged.get(node) or {}
        out.append({"dir": d, "node": node, "cpu_model": facts.get("cpuModel"), "cpu_set": facts.get("cpuSet"), "pod_qos_class": api.get("podQosClass"),
                    "cpu_manager_policy": api.get("cpuManagerPolicy"), "calibration": {"pass": cal.get("pass"), "noise": cal.get("noise")}})
    return out


def reproduction(dirs, run_dir):
    """Compare a family's two node runs (`buffon compare`): write reproduction.md and reproduction.json in the family directory and return the totals."""
    from .submit import reproduce
    try:
        c = reproduce.compare(dirs[0], dirs[1])
    except (OSError, ValueError, KeyError) as error:
        return {"compared": False, "why": f"the runs could not be compared: {error}"}
    reproduce.write(c, run_dir)
    t = c["totals"]
    return {"compared": True, "original": dirs[0], "reproduction": dirs[1], "cells": t["cells"], "reproduced": t["reproduced"], "not_reproduced": t["not_reproduced"],
            "consistent_only": t["consistent_only"], "noise": c["noise"]["verdict"]}


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def build_bundle(s, bundle_dir, arms, log):
    """Build the campaign's bundle once (the arms of every family) into bundle_dir; a named arm the bundle cannot carry refuses the campaign."""
    import shutil
    from .arms import install
    from .backend import bundle as bundlelib
    import subprocess

    tmp = bundle_dir + ".part"
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"buffon campaign: building the bundle for linux-{s.kube.arch} into {bundle_dir}")
    try:
        summary = bundlelib.build(tmp, s.kube.arch, arms, host_cache=s.local.cache_dir)
    except (bundlelib.BundleError, install.InstallError, subprocess.CalledProcessError) as error:
        shutil.rmtree(tmp, ignore_errors=True)
        raise BackendError(f"bundle: {error}") from error
    if summary["skipped"]:
        shutil.rmtree(tmp, ignore_errors=True)
        raise BackendError("bundle: the plan names arm(s) a bundle cannot carry: " + "; ".join(f"{a}: {why}" for a, why in sorted(summary["skipped"].items())))
    os.replace(tmp, bundle_dir)


def _utc(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
