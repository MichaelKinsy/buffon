# SPDX-License-Identifier: Apache-2.0
"""How long a choice will take on THIS machine: a short probe of its speed, a per-sample cost for every workload, and the times earlier runs here actually took.

The probe is a few process starts and a CPU loop (about a second). A workload's expected time is samples x cost; the cost is the table's typical laptop figure scaled by the probe, or, once
this machine has run the workload, the median wall time its samples took (timings.json in Buffon home). Estimates are labelled as such everywhere they are shown."""
import functools
import json
import os
import statistics
import subprocess
import sys
import time

from .. import workloads as workloadlib
from . import catalog

REF_SPAWN_S, REF_LOOP_S = 0.020, 0.080      # what the cost table's laptop does: a Python start, and the CPU loop below
STALL_NOTE_S = 10                            # scale_stall_s's default (buffon/workloads/scale.py STALL_S)
GATE_S = 0.15                                # per sample: the quiet-host check, the mock's request log, the sample's bookkeeping
INSTALL_CACHED_S, INSTALL_FRESH_S = 4.0, 30.0
PROBE_MAX_AGE_S = 6 * 3600


def _loop():
    t = time.perf_counter()
    x = 0
    for i in range(1_500_000):
        x += i * i % 7
    return time.perf_counter() - t


def probe(spawns=10):
    """{"speed": factor >= 0.4 (1.0 = the reference laptop; 2.0 = twice as slow), "spawn_ms", "loop_ms", "took_s"}."""
    t0 = time.perf_counter()
    times = []
    for _ in range(spawns):
        t = time.perf_counter()
        subprocess.run([sys.executable, "-c", "pass"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        times.append(time.perf_counter() - t)
    loop = min(_loop(), _loop())
    spawn = statistics.median(times)
    speed = max(0.4, min(8.0, (spawn / REF_SPAWN_S + loop / REF_LOOP_S) / 2))
    return {"speed": round(speed, 2), "spawn_ms": round(spawn * 1000, 1), "loop_ms": round(loop * 1000, 1), "took_s": round(time.perf_counter() - t0, 2)}


def cached_probe(path, max_age=PROBE_MAX_AGE_S, force=False):
    """The probe of the last `max_age` seconds, else a new one (written next to Buffon home's other state)."""
    try:
        if not force and time.time() - os.path.getmtime(path) < max_age:
            with open(path) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    result = probe()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(result, f)
    except OSError:
        pass
    return result


def load_history(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def record_history(path, raws):
    """Fold the wall time of every measured sample of the finished runs into the history: workload id -> median seconds per sample on this machine."""
    walls = {}
    for raw in raws:
        for s in raw.get("samples", []):
            if not s.get("warmup") and "failure" not in s and isinstance(s.get("wall_s"), (int, float)):
                walls.setdefault(s["scenario"], []).append(s["wall_s"])
    history = load_history(path)
    for wid, values in walls.items():
        history[wid] = round(statistics.median(values), 2)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(history, f, indent=1, sort_keys=True)
    except OSError:
        pass
    return history


def sample_cost(workload_id, speed, history):
    """(seconds for one sample, whether it comes from this machine's history)."""
    if workload_id in history:
        return history[workload_id], True
    return catalog.cost_of(workload_id) * speed, False


def rounds_expected(sel, workload=None):
    """The measured rounds a cell is expected to take: the selection's (at most 7 when it stops adaptively), or a workload's own default (the scale family's 5) unless the operator gave --rounds."""
    rounds = min(sel.rounds, 7) if sel.adaptive else sel.rounds
    own = getattr(workload, "rounds", 0)
    return rounds if getattr(sel, "rounds_set", False) or not own else min(rounds, own)


@functools.lru_cache(maxsize=1)
def _arms():
    from ..arms import manifest
    return manifest.load_all()


def scale_envelope(sel, cpus=None):
    """(memory GiB, CPUs) of the swarm container of a selection: the parameters, else the memory tier and the site's harness CPUs (`cpus`), else the reference envelope's."""
    from ..site import parse_cpus
    given = sel.params.get("swarm_cpus")
    n = len(given) if isinstance(given, (list, tuple)) else len(parse_cpus(str(given))) if given else cpus
    return float(sel.params.get("swarm_memory_gib") or sel.memory_tier_gib), int(n or catalog.SCALE_REF_ENVELOPE[1])


def scale_seconds(workload_id, sel, w, cpus=None):
    """Model of the expected seconds of one scale search workload in a selection: for every harness that takes part, one search sample in every round (the warm-up too), each costed by
    `catalog.scale_search` from the rung timings of the old doubling-only runs plus an allowance for the bisection. The ten-extension variants use the plain timings: no measurement with extensions exists.
    The probe's speed does not scale it: the table is the container's own work, not this laptop's process cost."""
    harnesses = catalog.scale_harness_count(workload_id, list(dict.fromkeys(sel.harnesses)), _arms())
    memory, ncpu = scale_envelope(sel, cpus)
    kind = catalog.scale_kind(workload_id)
    search = catalog.scale_search(kind, memory, ncpu, int(sel.params.get("scale_resolution") or 1), int(sel.params.get("swarm_max_agents") or catalog.SCALE_CAP))
    return harnesses * (1 + rounds_expected(sel, w)) * (search + GATE_S)


def workload_seconds(workload_id, sel, instances, speed, history, registry=None, cpus=None):
    """Expected seconds of one workload in a selection: its samples (a warm-up round and the expected measured rounds, every instance, every API it varies over) or its fixed total."""
    registry = registry if registry is not None else workloadlib.load_all()
    w = registry.get(workload_id)
    if workload_id.startswith("scale/"):
        return scale_seconds(workload_id, sel, w, cpus)
    total = catalog.special_total(workload_id)
    if total is not None:
        if workload_id in history:
            return history[workload_id]
        return total * (instances / 6 if workload_id.startswith("reliability/") else 1)
    if workload_id.startswith("devloop/"):   # one reading per arm, no A/A copy, a few repeats
        return 4 * (instances // 2) * (sample_cost(workload_id, speed, history)[0] + GATE_S)
    apis = 1 if (w is None or w.apis == (None,)) else max(1, len([a for a in sel.apis if a in w.apis]))
    cost, _known = sample_cost(workload_id, speed, history)
    return (1 + rounds_expected(sel, w)) * (instances if getattr(w, "aa", True) else instances // 2) * apis * (cost + GATE_S)


def estimate(sel, probe_result, history=None, installed=(), registry=None, cpus=None):
    """The expected time of a whole `buffon up` for `sel`: {"total_s", "steps": {install, calibrate, measure, evals, report}, "per_workload": {id: s}}, all in seconds, rounded."""
    history = history or {}
    speed = probe_result["speed"]
    harnesses = list(dict.fromkeys(sel.harnesses))
    instances = 2 * len(harnesses)
    install = max([INSTALL_CACHED_S if h in installed else INSTALL_FRESH_S for h in harnesses], default=0) * (1 + 0.15 * speed)   # installs run side by side: the slowest decides
    per = {w: workload_seconds(w, sel, instances, speed, history, registry, cpus) for w in sel.workloads}
    cal_cost = sample_cost("overhead/print", speed, history)[0]
    runs = 1 + (1 if any(w.startswith(("soak/", "reliability/")) for w in sel.workloads) else 0)
    calibrate = runs * (sel.calibration_rounds + 1) * 2 * (cal_cost + GATE_S)
    evals = 0.0
    for e in sel.evals:
        evals += (15 if e == "faithfulness-smoke" else 65 * (len(harnesses) + 1)) * speed
    report = 10 * speed
    steps = {"install": install, "calibrate": calibrate, "measure": sum(per.values()), "evals": evals, "report": report}
    return {"total_s": sum(steps.values()), "steps": steps, "per_workload": per, "speed": speed}


def estimate_campaign(plan, probe_result, history=None, registry=None):
    """The expected measuring time of a campaign plan (buffon/campaign.py), from the same per-sample costs as `buffon up`: {"total_s", "families": {name: seconds}}. Every arm of a family is counted in
    every workload of it with its A/A copy, so an arm that has no mode for a workload makes this an upper bound. Installs, the perf check and the report are not counted."""
    from .. import workloads as workloadlib
    from ..runner import engine
    from .selection import Selection
    registry = registry if registry is not None else workloadlib.load_all()
    reference = plan["campaign"].get("reference", "pi-node")
    out = {}
    for fam in plan["family"]:
        harnesses = list(dict.fromkeys([reference, *fam["arms"]]))
        apis = list(fam["apis"]) if fam.get("apis") else list(engine.APIS)
        arms = _arms()
        if not fam.get("apis") and any(h in arms and not any(arms[h].supports_api(a) for a in engine.APIS) and arms[h].supports_api(engine.RESPONSES) for h in harnesses):
            apis.append(engine.RESPONSES)   # what `buffon run` adds when no API was named and an arm speaks only Responses
        sel = Selection(harnesses=harnesses, workloads=[w.id for w in workloadlib.resolve(fam["workloads"])], apis=apis, rounds=fam.get("rounds", engine.MIN_ROUNDS), rounds_set=True, adaptive=False,
                        evals=[], params=dict(fam.get("params") or {}))
        out[fam["name"]] = estimate(sel, probe_result, history, installed=harnesses, registry=registry)["steps"]["measure"]
    return {"total_s": sum(out.values()), "families": out}


def scale_note(sel, est, cpus=None):
    """The sentence `buffon up --plan` and the run say about the scale searches' share of the time, or "" when the selection has none: what the time is made of and what it was estimated from. It is a model."""
    ids = [w for w in sel.workloads if w.startswith("scale/")]
    if not ids:
        return ""
    registry = workloadlib.load_all()
    rounds = 1 + rounds_expected(sel, registry.get(ids[0]))
    memory, ncpu = scale_envelope(sel, cpus)
    arms, names = _arms(), list(dict.fromkeys(sel.harnesses))
    counts = {w: catalog.scale_harness_count(w, names, arms) for w in ids}
    seconds = sum(est["per_workload"].get(w, 0.0) for w in ids)
    own = (memory, float(ncpu)) == tuple(float(x) for x in catalog.SCALE_REF_ENVELOPE)
    return (f"scale: about {_duration(seconds)} of it (a model, not a measurement), for {' and '.join(f'{n} harnesses on {w}' for w, n in counts.items())} in {memory:g} GiB and {ncpu} CPUs. "
            f"{rounds} searches a harness (the first is warm-up), no A/A copy; a search doubles the agents until one probe fails, which ends at its first OOM kill or after {STALL_NOTE_S} s stalled at the limit, "
            f"then bisects to the exact number. Estimated from the rung timings of the old doubling-only run in 4 GiB and 8 CPUs, plus about log2 of the gap in extra probes for a harness that stops"
            + ("" if own else f", scaled to {memory:g} GiB and {ncpu} CPUs") + ". The ten-extension searches use the plain timings: no run with extensions has been timed.")


def _duration(seconds):
    from .selection import format_duration
    return format_duration(seconds)


def fit_budget(sel, budget_s, probe_result, history=None, installed=(), registry=None):
    """(a selection that fits `budget_s`, notes). Order of the cuts: fewer rounds per cell (never under 6 when adaptive, 12 otherwise is dropped to 6 and says so), then evals,
    then the last benchmarks one by one (the first one named is kept whatever it costs). The selection is returned unchanged when it already fits."""
    notes = []
    cur = sel.clone()
    est = estimate(cur, probe_result, history, installed, registry)
    if est["total_s"] <= budget_s:
        return cur, notes
    if cur.rounds > 6 or not cur.adaptive:
        cur.rounds, cur.rounds_set = (max(6, min(cur.rounds, 8)) if cur.adaptive else 6), True
        cur.adaptive = True
        cur.preset = ""
        notes.append(f"rounds capped at {cur.rounds} and stopped adaptively (a run under 12 rounds cannot be Verified)")
        est = estimate(cur, probe_result, history, installed, registry)
    while est["total_s"] > budget_s and cur.evals:
        notes.append(f"dropped the {cur.evals[-1]} eval")
        cur.evals = cur.evals[:-1]
        est = estimate(cur, probe_result, history, installed, registry)
    while est["total_s"] > budget_s and len(cur.workloads) > 1:
        notes.append(f"dropped {cur.workloads[-1]}")
        cur.workloads = cur.workloads[:-1]
        cur.preset = ""
        est = estimate(cur, probe_result, history, installed, registry)
    if est["total_s"] > budget_s:
        notes.append(f"even the smallest choice is expected to take about {int(est['total_s'])} s, over the {int(budget_s)} s budget")
    return cur, notes
