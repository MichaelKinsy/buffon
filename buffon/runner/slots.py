# SPDX-License-Identifier: Apache-2.0
"""Slots: several measured sessions at once on disjoint core sets of one host (docs/METHODOLOGY.md, "Slots on one big host").

Opt-in with `[local] slots = N` in the site profile. This module does three things:

  1. `partition` splits the CPUs the runner may use into N slots: whole physical cores (SMT siblings stay together), one NUMA node per slot where the host allows, each
     slot with its own harness CPUs and its own mock CPUs, sized like the site's single session. A partition that would share a core, or leave a slot with fewer harness CPUs
     than the site's session has, is refused (`SlotError`).
  2. `calibrate` runs the reference arm against its A/A copy alone in one slot, then in every slot at the same time. A slot passes when its CV of `cpu_ms` is within the
     gate and the median of the gated metrics did not move past the solo run's A/A floor. The verdict is slots-calibration.json.
  3. `lock_path`, `select` and `passed` give a session its slot: its CPUs, its own lock file, and whether its slot's calibration passed.

Nothing here measures. The sessions are `buffon run` processes the caller starts (buffon/campaign.py); this module reads what they wrote.
"""
import calendar
import json
import math
import os
import threading
import time
from dataclasses import dataclass

from .. import stats
from ..site import format_cpus, parse_cpus

SYS = "/sys/devices/system"
GATED = ("cpu_ms", "wall_ms")     # the metrics a slot's median may not move on: the time metrics that contention moves
CV_METRIC = "cpu_ms"
MIN_OVERLAP = 0.5                 # the concurrent sessions must have run at the same time for at least this share of the shortest one
FILE = "slots-calibration.json"
RUN_DIRS = "slots-calibration"


class SlotError(ValueError):
    """A partition or a slot the runner refuses: the message says what to change."""


# -- topology ---------------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Core:
    cpus: tuple            # the logical CPUs of one physical core (SMT siblings), sorted
    package: object = None  # socket id, None when unknown
    node: object = None     # NUMA node id, None when unknown


class Topology:
    """The physical cores of a host: which logical CPUs form a core, on which socket and NUMA node."""

    def __init__(self, cores):
        self.cores = sorted(cores, key=lambda c: c.cpus[0])

    @property
    def cpus(self):
        return sorted(c for core in self.cores for c in core.cpus)

    def core_of(self, cpu):
        return next((core for core in self.cores if cpu in core.cpus), None)


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def read_topology(root=SYS):
    """The topology from sysfs (`root` is a directory laid out like /sys/devices/system), or None where it cannot be read (macOS, a minimal container)."""
    text = _read(f"{root}/cpu/online")
    if text is None:
        return None
    nodes = {}
    base = f"{root}/node"
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if name.startswith("node") and name[4:].isdigit():
            for cpu in parse_cpus(_read(f"{base}/{name}/cpulist") or ""):
                nodes[cpu] = int(name[4:])
    cores = {}
    for cpu in parse_cpus(text):
        siblings = _read(f"{root}/cpu/cpu{cpu}/topology/thread_siblings_list")
        if siblings is None:
            return None
        package = _read(f"{root}/cpu/cpu{cpu}/topology/physical_package_id")
        cores.setdefault(tuple(parse_cpus(siblings)), (int(package) if package and package.lstrip("-").isdigit() else None, nodes.get(cpu)))
    return Topology([Core(cpus, package, node) for cpus, (package, node) in cores.items()])


# -- partition --------------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Slot:
    id: int
    cpus: tuple          # harness CPUs
    mock_cpus: tuple     # the runner's and the mock's CPUs
    nodes: tuple = ()    # NUMA nodes the slot's cores are on (more than one: the host had no node left to hold the slot)

    def describe(self):
        nodes = [n for n in self.nodes if n is not None]
        where = f"NUMA node {nodes[0]}" if len(nodes) == 1 else f"NUMA nodes {', '.join(map(str, nodes))} (spans nodes)" if nodes else "NUMA node unknown"
        return f"slot {self.id}: harness CPUs {format_cpus(self.cpus)}, mock CPUs {format_cpus(self.mock_cpus)} ({where})"

    def record(self):
        """The slot as campaign.json holds it."""
        return {"id": self.id, "cpus": format_cpus(self.cpus), "mock_cpus": format_cpus(self.mock_cpus)}


def partition(topology, harness, mock, slots, allowed=None, housekeeping=1):
    """`slots` disjoint slots of `harness` harness CPUs and (at least) `mock` mock CPUs each, from the whole physical cores of `topology` that lie wholly inside `allowed`.

    The lowest `housekeeping` core(s) stay out of every slot, for the kernel, the shell and the campaign itself. A slot's harness CPUs are whole cores, so a harness CPU count that
    does not fill whole cores is refused (a session of 3 CPUs on 2-way SMT would have a core's sibling to spare, and a changed size is a changed measurement); the mock gets whole
    cores too (its sibling threads are its own). Slots are placed one node at a time, the node with the most room first, so each lies on one NUMA node while any node has room for
    it; a slot is spread over nodes only when none has. Raises SlotError when that cannot be done."""
    if slots < 2:
        raise SlotError(f"slots = {slots}: a partition has at least 2 slots (1 is the single session of today)")
    if harness < 1 or mock < 1:
        raise SlotError("a slot needs harness CPUs and mock CPUs: give the site `cpus` and `mock_cpus` (their counts are the size of one slot)")
    allowed = set(topology.cpus if allowed is None else allowed)
    usable = [c for c in topology.cores if set(c.cpus) <= allowed]
    widths = {len(c.cpus) for c in usable}
    if not usable:
        raise SlotError("no whole physical core is inside the CPUs this runner may use")
    if len(widths) > 1:
        raise SlotError(f"the cores have different numbers of SMT threads ({', '.join(map(str, sorted(widths)))}): a slot cannot be sized in whole cores")
    width = widths.pop()
    if harness % width:
        raise SlotError(f"the site's session has {harness} harness CPUs, which does not fill whole cores of {width} threads: a slot would share a core. Use a multiple of {width}")
    harness_cores, mock_cores = harness // width, -(-mock // width)
    per = harness_cores + mock_cores
    pool = usable[housekeeping:]
    need = slots * per
    if len(pool) < need:
        raise SlotError(f"{slots} slots of {harness} harness and {mock} mock CPUs need {need} whole cores ({per} each, {width} threads per core) and {housekeeping} more for the host; "
                        f"this host has {len(usable)} usable")
    by_node = {}
    for core in pool:
        by_node.setdefault(core.node, []).append(core)
    order = sorted(by_node, key=lambda n: (n is None, n if n is not None else 0))
    placed = []
    for _ in range(slots):
        best = max(order, key=lambda n: (len(by_node[n]) // per, -order.index(n)))
        if len(by_node[best]) < per:
            break
        placed.append((by_node[best][:per], (best,)))
        del by_node[best][:per]
    spare = [c for n in order for c in by_node[n]]
    for _ in range(slots - len(placed)):
        cores, spare = spare[:per], spare[per:]
        placed.append((cores, tuple(sorted({c.node for c in cores}, key=lambda n: (n is None, n if n is not None else 0)))))
    made = []
    for cores, nodes in sorted(placed, key=lambda p: p[0][0].cpus[0]):
        made.append(Slot(len(made) + 1, tuple(sorted(c for core in cores[:harness_cores] for c in core.cpus)),
                         tuple(sorted(c for core in cores[harness_cores:] for c in core.cpus)), nodes))
    check_partition(made, topology, harness, allowed)
    return made


def check_partition(slots, topology, harness, allowed=None):
    """Raise SlotError when the slots share a CPU or a core (an SMT sibling in another slot, or left out), name a CPU the runner may not use, or give a slot fewer than
    `harness` harness CPUs. `partition` ends with it; a campaign that resumes runs it on the slots it recorded."""
    allowed = None if allowed is None else set(allowed)
    owner = {}
    for slot in slots:
        if len(slot.cpus) < harness:
            raise SlotError(f"slot {slot.id} has {len(slot.cpus)} harness CPUs, fewer than the {harness} the site's session has")
        if set(slot.cpus) & set(slot.mock_cpus):
            raise SlotError(f"slot {slot.id}: the harness and the mock share CPUs {format_cpus(set(slot.cpus) & set(slot.mock_cpus))}")
        for cpu in (*slot.cpus, *slot.mock_cpus):
            if cpu in owner:
                raise SlotError(f"CPU {cpu} is in slot {owner[cpu]} and in slot {slot.id}: slots share a core")
            if allowed is not None and cpu not in allowed:
                raise SlotError(f"slot {slot.id} names CPU {cpu}, which this runner may not use")
            owner[cpu] = slot.id
    for cpu, slot_id in owner.items():
        core = topology.core_of(cpu)
        if core is None:
            raise SlotError(f"slot {slot_id} names CPU {cpu}, which this host does not have")
        stray = [c for c in core.cpus if owner.get(c) != slot_id]
        if stray:
            raise SlotError(f"slot {slot_id} holds CPU {cpu} but not its SMT sibling {format_cpus(stray)}: the slot would share a core")


def partition_site(site, topology=None, allowed=None):
    """The slots of a local site with `[local] slots` of at least 2: the host's cores split by the size of the site's single session (its `cpus` and `mock_cpus` counts)."""
    from . import facts as factlib
    local = site.local
    if topology is None:
        topology = read_topology()
        if topology is None:
            raise SlotError("slots need the host's CPU topology (/sys/devices/system/cpu/cpuN/topology), which this machine does not show: use a Linux host")
    return partition(topology, len(local.cpus), len(local.mock_cpus), local.slots, factlib.allowed_cpus() if allowed is None else allowed)


def lock_path(base, slot_id):
    """The lock file of one slot: its own, beside the host-wide one. Only slot mode uses it."""
    return f"{base}.slot{slot_id}"


def select(site, slot_id, calibration=None, topology=None, allowed=None):
    """Give a local site the CPUs of slot `slot_id` (its `cpus`, `mock_cpus` and `slot` are replaced; `slots` stays) and return the Slot. `calibration` is the path of a
    slots-calibration.json; a slot that file does not pass is refused. Raises SlotError."""
    if site.backend != "local" or site.local.slots < 2:
        raise SlotError("--slot needs a local site with `[local] slots` of at least 2")
    made = partition_site(site, topology, allowed)
    if not 1 <= slot_id <= len(made):
        raise SlotError(f"--slot {slot_id}: this site has slots 1 to {len(made)}")
    slot = made[slot_id - 1]
    if calibration is not None and not passed(calibration, slot_id):
        raise SlotError(f"the slot calibration {calibration} does not pass slot {slot_id}: a failed slot is not used")
    others = sorted(c for s in made if s.id != slot_id for c in (*s.cpus, *s.mock_cpus))
    site.local.cpus, site.local.mock_cpus = list(slot.cpus), list(slot.mock_cpus)
    site.local.slot = {"id": slot_id, "of": len(made), "cpus": format_cpus(slot.cpus), "mock_cpus": format_cpus(slot.mock_cpus), "others": others,
                       "calibration": os.path.abspath(calibration) if calibration else None}
    return slot


def passed(path, slot_id):
    """True when the slots-calibration.json at `path` lists `slot_id` as usable."""
    try:
        with open(path) as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and slot_id in (doc.get("usable") or [])


# -- calibration ------------------------------------------------------------------------------------------------------------------------------

def _per_round(samples, reference):
    """{(scenario, api): (reference rounds, copy rounds)} where each is {metric: {round: value}}, from measured, non-failed samples."""
    from ..report import cells
    twin = reference + "-b"
    keys = sorted({(s["scenario"], s.get("api")) for s in samples if s["arm"] == reference and not s["warmup"] and "failure" not in s}, key=lambda k: (k[0], k[1] or ""))
    return {key: tuple({m: cells.per_round(samples, key[0], key[1], arm, m) for m in GATED} for arm in (reference, twin)) for key in keys}


def read_samples(run_dir):
    """The samples of a session's raw.json and its start and end (UTC seconds), or (None, None, None) when it left no usable raw.json."""
    try:
        with open(os.path.join(run_dir, "raw.json")) as f:
            raw = json.load(f)
        run = raw.get("run") or {}
        return raw["samples"], _utc(run.get("started_utc")), _utc(run.get("finished_utc"))
    except (OSError, ValueError, KeyError):
        return None, None, None


def _utc(text):
    try:
        return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")) if text else None
    except ValueError:
        return None


def _cells_of(samples, reference, rounds):
    """{(scenario, api, metric): {"a": [...], "b": [...], "cv": cv of cpu_ms (max of the copies)}} aligned by round; None where fewer than rounds - 1 measured rounds exist."""
    out, problems = {}, []
    for (scenario, api), (a, b) in _per_round(samples, reference).items():
        for metric in GATED:
            keys = sorted(set(a[metric]) & set(b[metric]))
            where = f"{scenario}{'@' + api if api else ''} {metric}"
            if len(keys) < max(3, rounds - 1):
                problems.append(f"{where}: {len(keys)} usable rounds of {rounds}")
                continue
            x, y = [a[metric][k] for k in keys], [b[metric][k] for k in keys]
            out[(scenario, api, metric)] = {"a": x, "b": y, "cv": max(stats.cv(x), stats.cv(y)) if metric == CV_METRIC else None}
    return out, problems


def _overlap(windows):
    """The share of the shortest window during which every window was open (0 to 1); None when a start or an end is missing."""
    if not windows or any(a is None or b is None for a, b in windows):
        return None
    shortest = min(b - a for a, b in windows)
    return max(0.0, min(b for _, b in windows) - max(a for a, _ in windows)) / shortest if shortest > 0 else 1.0


def judge(solo, concurrent, reference, max_cv, rounds, overlap=None):
    """The verdict of a slot calibration, from samples only.

    `solo`: the samples of the reference arm and its A/A copy run alone in one slot. `concurrent`: {slot id: samples, or None when its session left none}. For every cell and
    gated metric the solo run's A/A floor is the largest deviation from 1 of the copies' own ratio of medians (buffon/report/cells.py floor_of). A slot passes when
      - its CV of cpu_ms (the larger of the two copies, any cell) is at most `max_cv`, and
      - the median of every gated metric (both copies together) differs from the solo median by no more than that floor.
    A solo run that is itself above `max_cv` or has no floor judges nothing: no slot passes. `overlap` is the share of time the concurrent sessions ran together; below
    MIN_OVERLAP they were not concurrent and no slot passes."""
    from ..report import cells as cellmod
    out = {"max_cv": max_cv, "gated": list(GATED), "overlap": overlap, "min_overlap": MIN_OVERLAP, "solo": {"problems": [], "cells": []}, "slots": [], "usable": []}
    solo_cells, problems = _cells_of(solo, reference, rounds) if solo is not None else ({}, ["the solo session left no samples"])
    base = {}
    for (scenario, api, metric), c in solo_cells.items():
        floor, _ = cellmod.floor_of(c["a"], c["b"])
        median = stats.median(c["a"] + c["b"])
        row = {"scenario": scenario, "api": api, "metric": metric, "median": median, "floor": floor, "cv": c["cv"]}
        out["solo"]["cells"].append(row)
        if floor is None:
            problems.append(f"{scenario}{'@' + api if api else ''} {metric}: the solo run has no A/A floor to judge against")
        elif c["cv"] is not None and not c["cv"] <= max_cv:
            problems.append(f"{scenario}{'@' + api if api else ''} {metric}: the solo run's CV is {c['cv']:.1%}, above the gate of {max_cv:.0%}")
        else:
            base[(scenario, api, metric)] = (median, floor)
    if not solo_cells and solo is not None:
        problems.append("the solo run has no measured cell of the reference arm and its copy")
    if overlap is not None and overlap < MIN_OVERLAP:
        problems.append(f"the sessions ran together for only {overlap:.0%} of the shortest (at least {MIN_OVERLAP:.0%} counts as concurrent)")
    elif overlap is None and concurrent:
        problems.append("the sessions' start and end times are missing, so that they ran together cannot be shown")
    out["solo"]["problems"] = problems
    for slot_id in sorted(concurrent):
        samples, mine = concurrent[slot_id], list(problems)
        row = {"id": slot_id, "cv": None, "cells": [], "problems": mine, "pass": False}
        out["slots"].append(row)
        if samples is None:
            mine.append("the session left no samples")
            continue
        cells, short = _cells_of(samples, reference, rounds)
        mine += short
        cvs = [c["cv"] for c in cells.values() if c["cv"] is not None]
        row["cv"] = max(cvs) if cvs else None
        if not cvs:
            mine.append(f"no CV of {CV_METRIC} could be computed")
        elif not row["cv"] <= max_cv:
            mine.append(f"CV of {CV_METRIC} is {row['cv']:.1%}, above the gate of {max_cv:.0%}")
        for key, (median, floor) in sorted(base.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2])):
            scenario, api, metric = key
            where = f"{scenario}{'@' + api if api else ''} {metric}"
            c = cells.get(key)
            if c is None:
                mine.append(f"{where}: no samples to compare")
                continue
            mine_median = stats.median(c["a"] + c["b"])
            shift = math.log(mine_median / median) if median > 0 and mine_median > 0 else math.inf
            ok = abs(shift) <= floor
            row["cells"].append({"scenario": scenario, "api": api, "metric": metric, "solo_median": median, "median": mine_median, "shift": shift, "floor": floor, "within": ok})
            if not ok:
                mine.append(f"{where}: the median moved {math.expm1(shift):+.1%} from the solo run's, past its A/A floor of {math.expm1(floor):.1%}")
        row["pass"] = not mine
        if row["pass"]:
            out["usable"].append(slot_id)
    return out


def calibrate(slots, run, argv_for, out, reference, rounds, max_cv, log=print, now=time.time):
    """Run the slot calibration and write <out>/slots-calibration.json. Returns the verdict dict (`usable`: the slots that passed; empty: serial is the fallback).

    `argv_for(slot_id, run_dir)` is the `buffon run` argv of one calibration session; `run(argv, log_path)` runs it and returns its exit code. The reference arm against its
    A/A copy runs first alone in the first slot, then in every slot at once (one thread each, one `buffon run` process each)."""
    base = os.path.join(out, RUN_DIRS)
    os.makedirs(base, exist_ok=True)
    first = slots[0].id
    solo_dir = os.path.join(base, "solo")
    log(f"buffon campaign: slot calibration: {reference} against its A/A copy alone in slot {first}")
    solo_exit = run(argv_for(first, solo_dir), solo_dir + ".log")
    log(f"buffon campaign: slot calibration: the same in all {len(slots)} slots at once")
    dirs, exits = {s.id: os.path.join(base, f"slot-{s.id}") for s in slots}, {}

    def one(slot):
        exits[slot.id] = run(argv_for(slot.id, dirs[slot.id]), dirs[slot.id] + ".log")
    threads = [threading.Thread(target=one, args=(s,)) for s in slots]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    solo, *_ = read_samples(solo_dir)
    read = {i: read_samples(d) for i, d in dirs.items()}
    concurrent = {i: (r[0] if exits.get(i) == 0 else None) for i, r in read.items()}
    windows = [(r[1], r[2]) for i, r in read.items() if exits.get(i) == 0]
    verdict = judge(solo if solo_exit == 0 else None, concurrent, reference, max_cv, rounds, _overlap(windows) if windows else None)
    for row in verdict["slots"]:
        row["exit"], row["run_dir"] = exits.get(row["id"]), dirs[row["id"]]
        if exits.get(row["id"]) != 0:
            row["problems"].insert(0, f"the session exited {exits.get(row['id'])}")
    verdict["solo"]["exit"], verdict["solo"]["run_dir"], verdict["solo"]["slot"] = solo_exit, solo_dir, first
    if solo_exit != 0:
        verdict["solo"]["problems"].insert(0, f"the solo session exited {solo_exit}")
    verdict.update({"kind": "buffon-slots-calibration", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now())), "reference": reference, "rounds": rounds,
                    "slots": [dict(s.record(), **next(r for r in verdict["slots"] if r["id"] == s.id)) for s in slots],
                    "fallback": None if verdict["usable"] else "serial"})
    path = os.path.join(out, FILE)
    with open(path + ".tmp", "w") as f:
        json.dump(verdict, f, indent=2, sort_keys=True, default=str)
    os.replace(path + ".tmp", path)
    for row in verdict["slots"]:
        log(f"buffon campaign: slot {row['id']}: {'passed' if row['pass'] else 'FAILED, not used'}" + ("" if row["pass"] else "; " + "; ".join(row["problems"][:3])))
    return verdict


def reusable(out, slots):
    """The earlier slots-calibration.json of this campaign directory when it passed for at least one slot and was made for exactly these slots; else None."""
    try:
        with open(os.path.join(out, FILE)) as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    same = [{k: s.get(k) for k in ("id", "cpus", "mock_cpus")} for s in doc.get("slots") or []] == [s.record() for s in slots]
    return doc if same and doc.get("usable") else None
