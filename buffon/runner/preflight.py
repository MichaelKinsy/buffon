# SPDX-License-Identifier: Apache-2.0
"""`buffon preflight`: which host class can this machine give the benchmark's CPUs, and what stops the next class up (Run Rules 1-4).

Class A: dedicated. The bench CPUs are exclusive (kernel-isolated, or an exclusive cpuset partition, or the whole machine is declared dedicated and nothing else was seen
running on them), whole physical cores, one NUMA node, a housekeeping CPU left over, a fixed clock with turbo off, no CPU quota anywhere above the benchmark. Results are publishable.
Class B: shared. Anything else that still runs the benchmark. Results are PROVISIONAL.
A check with severity `refuse` (a CPU quota) stops the run: the measurement would be an artefact of the quota."""
import os

from . import facts as factlib, quiet as quietlib
from ..site import parse_cpus

SYS = "/sys/devices/system"
ORDER = {"A": 0, "B": 1}


def _online():
    text = factlib._read(f"{SYS}/cpu/online")
    return set(parse_cpus(text)) if text else set(range(os.cpu_count() or 1))


def _isolated():
    text = factlib._read(f"{SYS}/cpu/isolated")
    return set(parse_cpus(text)) if text else set()


def _node_of(cpu):
    for name in os.listdir(f"{SYS}/node") if os.path.isdir(f"{SYS}/node") else []:
        if name.startswith("node") and name[4:].isdigit():
            text = factlib._read(f"{SYS}/node/{name}/cpulist")
            if text and cpu in parse_cpus(text):
                return int(name[4:])
    return None


def _quota_chain():
    """[(path, cpu.max)] for this process's cgroup and every ancestor that carries a quota."""
    path = None
    for line in (factlib._read("/proc/self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            path = line[3:]
    found = []
    while path:
        value = factlib._read(f"/sys/fs/cgroup{path}/cpu.max")
        if value is not None and not value.startswith("max"):
            found.append((path, value))
        if path in ("/", ""):
            break
        path = os.path.dirname(path) or "/"
    return found


def _partition(cpus):
    """True when this process's cgroup is an exclusive cpuset partition that holds all of `cpus`."""
    path = None
    for line in (factlib._read("/proc/self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            path = line[3:]
    kind = factlib._read(f"/sys/fs/cgroup{path}/cpuset.cpus.partition") if path else None
    effective = factlib._read(f"/sys/fs/cgroup{path}/cpuset.cpus.effective") if path else None
    return bool(kind and kind.split()[0] in ("root", "isolated") and effective and set(cpus) <= set(parse_cpus(effective)))


def run(cpus, mock_cpus=(), claim="B", watch_s=2.0, sleep=None, online=None, isolated=None, siblings=None, node_of=None, quota=None, partition=None, governors=None,
        turbo_off=None, runnable=None, housekeeping_needed=1, clock_claim="", reserved=()):
    """The preflight report: {"class", "claim", "checks": [{"name", "ok", "severity", "detail"}], "reasons": [why not A]}. Every probe of the machine is a parameter so a test can
    describe any host; `claim` is what the site says ("A": the host is dedicated). `reserved` is the CPUs of the other slots of a host that runs several sessions at once
    (buffon/runner/slots.py): they are online and busy with other sessions, so they are not housekeeping CPUs."""
    bench = list(cpus)
    mock = list(mock_cpus)
    used = set(bench) | set(mock)
    online = _online() if online is None else set(online)
    isolated = _isolated() if isolated is None else set(isolated)
    sib = siblings or factlib.smt_siblings
    node = node_of or _node_of
    quota = _quota_chain() if quota is None else quota
    checks = []

    def add(name, ok, detail, severity="class"):
        checks.append({"name": name, "ok": bool(ok), "severity": severity, "detail": detail})

    add("cpus_set", bool(bench), "the benchmark has pinned CPUs" if bench else "no CPUs are pinned: nothing is exclusive", severity="class")
    strays = sorted({s for c in used for s in sib(c) if s in online and s not in used})
    add("whole_cores", not strays, "every SMT sibling of a bench CPU is in the bench or mock set (or the CPU has none)" if not strays
        else f"SMT siblings {strays} of the bench CPUs are online and not reserved: a busy sibling changes every arm's CPU time")
    housekeeping = sorted(online - used - set(reserved))
    add("housekeeping", len(housekeeping) >= housekeeping_needed, f"{len(housekeeping)} online CPUs are left for everything else")
    nodes = {node(c) for c in used}
    add("one_numa_node", len(nodes) == 1 and None not in nodes, f"bench and mock CPUs are on NUMA node(s) {sorted(n for n in nodes if n is not None)}" if None not in nodes else "NUMA node of a CPU is unknown")
    govs = governors if governors is not None else {c: factlib.governor(c) for c in bench}
    fixed = all(factlib.fixed_clock(g, c) is not False for c, g in govs.items()) if govs else False
    add("fixed_clock", fixed, "governor is performance or the clock is fixed" if fixed else f"governor(s) {sorted(set(map(str, govs.values())))} scale the clock")
    if turbo_off is None:
        no_turbo, boost = factlib._read(f"{SYS}/cpu/intel_pstate/no_turbo"), factlib._read(f"{SYS}/cpu/cpufreq/boost")
        turbo_off = True if no_turbo == "1" or boost == "0" else (None if no_turbo is None and boost is None else False)
    unreadable = turbo_off is None and all(factlib.governor(c) is None for c in bench) if governors is None else turbo_off is None and all(g is None for g in govs.values())
    if clock_claim == "hypervisor" and unreadable:
        add("turbo_off", True, "the site claims a virtual machine whose platform fixes the clock and turbo state; the machine shows neither, so the claim is not verified")
    else:
        add("turbo_off", turbo_off is True, {True: "turbo is off", False: "turbo is on", None: "the turbo state cannot be read on this machine"}[turbo_off])
    def cpus_of(value):
        try:
            q, period = value.split()
            return int(q) / int(period)
        except ValueError:
            return float("inf")
    add("no_cpu_quota", not quota, "no cgroup from the benchmark up to the root limits CPU time" if not quota
        else "CPU quota on " + ", ".join(f"{p} ({v})" for p, v in quota) + ": the run is not Class A; every sample's throttling counter must stay at zero")
    small = [(p, v) for p, v in quota if cpus_of(v) < len(used)]
    add("quota_covers_the_cpus", not small, "no quota is smaller than the CPUs the benchmark uses" if not small
        else "CPU quota " + ", ".join(f"{p} ({v})" for p, v in small) + f" is smaller than the {len(used)} CPUs in use: throttling is certain", severity="refuse")
    exclusive = bool(bench) and (set(bench) <= isolated or (partition if partition is not None else _partition(bench)))
    seen = None
    if not exclusive and claim == "A" and bench:
        seen = (runnable or quietlib.runnable_on)(bench)
    if exclusive:
        add("exclusive_cpus", True, "the bench CPUs are kernel-isolated or in an exclusive cpuset partition")
    elif claim == "A" and seen == 0:
        add("exclusive_cpus", True, "the site declares the host dedicated and no other thread was running on the bench CPUs when looked at (a claim, not a guarantee)")
    else:
        add("exclusive_cpus", False, "other tasks may be scheduled on the bench CPUs: they are neither isolated nor in an exclusive partition" + ("" if claim != "A" else f"; {seen} foreign thread(s) running now"))
    reasons = [c["detail"] for c in checks if not c["ok"] and c["severity"] == "class"]
    refusals = [c["detail"] for c in checks if not c["ok"] and c["severity"] == "refuse"]
    return {"class": "A" if not reasons and not refusals else "B", "claim": claim, "checks": checks, "reasons": reasons + refusals, "refusals": refusals}


def satisfies(report, required):
    """True when the report's class is at least `required` ("A" or "B"); a refusal never satisfies."""
    return not report["refusals"] and ORDER[report["class"]] <= ORDER[required]
