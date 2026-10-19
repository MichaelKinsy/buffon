# SPDX-License-Identifier: Apache-2.0
"""Races: how far each harness got on a ladder of growing load, and why it stopped (docs/TRACKS.md, "Races").

A ladder is a list of rungs, each a benchmark that does more work than the one before (0, 10, 50, 100 extensions; 1 prompt, 1k turns, 4.2M tokens). The set finish line
and the limits (the container's memory tier, the CPUs, the deadline) are the same for every harness and are stated once above the race. For each harness this module reads the run's samples and
says: Finished (it crossed the last rung, and when) or Stopped (at which rung, at what elapsed time, and why: OOM, error or timeout); the speed, memory, reliability and resources of the climb.

An OOM, an error and a timeout are results, never a crashed run. Nothing here measures: it reads the samples the engine already recorded, so a race is reproduced from raw.json alone."""
import itertools
import statistics

OOM, ERROR, TIMEOUT, UNSUPPORTED, PIDS, STALL = "oom", "error", "timeout", "unsupported", "pids", "stall"
CHECKPOINTS = (25, 50, 75, 100)
FINISHED, STOPPED = "Finished", "Stopped"


def telemetry_memory_events(sample):
    return ((((sample.get("telemetry") or {}).get("system") or {}).get("cgroup")) or {}).get("memory_events") or {}


def telemetry_memory_peak_mib(sample):
    cg = (((sample.get("telemetry") or {}).get("system") or {}).get("cgroup")) or {}
    for key in ("memory_peak_bytes", "memory.peak"):
        if cg.get(key):
            return cg[key] / 1048576
    return sample.get("peak_mem_mib", sample.get("mem_peak_mib"))


def stop_cause(sample):
    """{"cause": oom|stall|timeout|error, "message", "peak_mib"} for a failed sample. OOM: the cgroup recorded an oom_kill, or the process died of SIGKILL (exit 137) under a memory limit, or its own
    text says out of memory. Timeout: the sample's own deadline. Anything else is an error with its message."""
    text = str(sample.get("failure") or "")
    low = text.lower()
    events = telemetry_memory_events(sample)
    peak = telemetry_memory_peak_mib(sample)
    given = sample.get("stop_cause")   # a swarm sample (scale/*) says its own cause, from the container's kernel counters: oom, stall, timeout, pids or error
    if given in (OOM, STALL, TIMEOUT, ERROR, PIDS):
        return {"cause": given, "message": text[:200], "peak_mib": peak}
    if events.get("oom_kill", 0) or events.get("oom", 0) or "out of memory" in low or "oomkilled" in low or "oom-killed" in low or "exit 137" in low or "exit -9" in low:
        return {"cause": OOM, "message": text[:200], "peak_mib": peak}
    if "timed out" in low or "timeout" in low or "did not settle" in low or "no get_state response" in low or "no get_commands response" in low:
        return {"cause": TIMEOUT, "message": text[:200], "peak_mib": peak}
    return {"cause": ERROR, "message": text[:200], "peak_mib": peak}


def peak_of(sample):
    """The peak memory of a sample: `peak_mem_mib` (one process tree), or `mem_peak_mib` (a swarm container)."""
    return sample.get("peak_mem_mib", sample.get("mem_peak_mib"))


def _median(values):
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return statistics.median(values) if values else None


def rung_result(samples, arm, workload, api):
    """What one harness did on one rung: ok when at least one measured sample succeeded; else the stop cause of its failures; None when it has no sample (it never got there)."""
    mine = [s for s in samples if s.get("arm") == arm and s.get("scenario") == workload and s.get("api") == api and not s.get("warmup")]
    if not mine:
        return None
    good = [s for s in mine if "failure" not in s]
    failed = [s for s in mine if "failure" in s]
    out = {"workload": workload, "samples": len(mine), "failed": len(failed), "ok": bool(good)}
    if good:
        out["wall_s"] = _median([s.get("wall_s") for s in good])
        out["peak_mem_mib"] = max((peak_of(s) for s in good if isinstance(peak_of(s), (int, float))), default=None)
        out["avg_mem_mib"] = _median([peak_of(s) for s in good])
        out["cpu_ms"] = _median([s.get("cpu_ms") for s in good])
        out["wall_ms"] = _median([s.get("wall_ms") for s in good])
    if not good:
        out["stop"] = stop_cause(failed[0])
    return out


def lane(samples, skipped, arm, rungs, api=None):
    """One harness's lane: [(label, workload)] rungs in order. Returns {"arm", "outcome", "reached", "reached_label", "rungs", "stop", "elapsed_s", "checkpoints", "memory", "reliability", "resources"}."""
    results, stop, elapsed, clock = [], None, 0.0, {}
    for i, (label, workload) in enumerate(rungs):
        seen = sorted({s.get("api") for s in samples if s.get("scenario") == workload}, key=str)
        use_api = api if api in seen else (seen[0] if seen else api)
        r = rung_result(samples, arm, workload, use_api)
        why = next((k["reason"] for k in skipped if k.get("arm") == arm and k.get("scenario") == workload), None)
        if r is None:
            r = {"workload": workload, "samples": 0, "failed": 0, "ok": False}
            r["stop"] = {"cause": UNSUPPORTED if why else ERROR, "message": why or "no sample was taken at this rung", "peak_mib": None}
        r["label"] = label
        results.append(r)
        if r["ok"] and stop is None:
            elapsed += r.get("wall_s") or 0.0
            clock[i] = elapsed
        elif stop is None:
            stop = dict(r["stop"], rung=label, index=i, elapsed_s=elapsed)
    reached = sum(1 for _ in itertools.takewhile(lambda r: r["ok"], results))
    n = len(rungs)
    done = stop is None and reached == n
    checkpoints = {}
    for q in CHECKPOINTS:
        need = max(1, -(-q * n // 100))   # the rung that is q% of the way, rounded up
        if need <= reached:
            checkpoints[str(q)] = round(clock[need - 1], 2)
    ok_rungs = [r for r in results if r["ok"]]
    return {"arm": arm, "outcome": FINISHED if done else STOPPED, "reached": reached, "of": n, "reached_label": rungs[reached - 1][0] if reached else None, "rungs": results, "stop": stop,
            "elapsed_s": round(elapsed, 2), "checkpoints": checkpoints,
            "memory": {"peak_mib": max((r["peak_mem_mib"] for r in ok_rungs if r.get("peak_mem_mib") is not None), default=None), "avg_mib": _median([r.get("avg_mem_mib") for r in ok_rungs]),
                       "at_stop_peak_mib": (stop or {}).get("peak_mib")},
            "reliability": {"failed_samples": sum(r["failed"] for r in results), "samples": sum(r["samples"] for r in results), "lost_work": 0},
            "resources": {"cpu_ms": round(sum(r.get("cpu_ms") or 0 for r in ok_rungs), 1)}}


def rank(lanes):
    """Finished first, by time; then stopped, by how far they got and, for ties, by the time they took to get there."""
    return sorted(lanes, key=lambda l: (l["outcome"] != FINISHED, l["elapsed_s"] if l["outcome"] == FINISHED else (-l["reached"], l["elapsed_s"])))


def race(samples, skipped, arms, rungs, api=None, limits=None, name=""):
    """The race of `arms` over `rungs`: {"name", "limits", "rungs": [labels], "lanes": ranked lanes}. `limits` is whatever the run recorded (memory tier, CPUs, deadline), stated once."""
    lanes = [lane(samples, skipped, a, rungs, api) for a in arms]
    return {"name": name, "limits": limits or {}, "rungs": [label for label, _w in rungs], "lanes": rank(lanes)}


def sentence(l):
    """`Stopped at 63 agents after 41 s: OOM, 3.9 GiB` / `Finished in 12.4 s`."""
    if l["outcome"] == FINISHED:
        return f"Finished in {l['elapsed_s']:.1f} s"
    s = l["stop"] or {}
    cause = {OOM: "OOM", STALL: "stalled at the memory limit", TIMEOUT: "timeout", PIDS: "process limit", ERROR: "error", UNSUPPORTED: "cannot run"}.get(s.get("cause"), "stopped")
    more = f", {s['peak_mib'] / 1024:.1f} GiB" if s.get("cause") == OOM and s.get("peak_mib") else (f": {s['message'][:80]}" if s.get("message") and s.get("cause") in (ERROR, UNSUPPORTED) else "")
    return f"Stopped at {s.get('rung')} after {s.get('elapsed_s', 0):.1f} s: {cause}{more}"


def limits_of(raw):
    """The limits a run recorded, stated above the race: the container's memory tier and CPUs, or `bare` when uncontained."""
    iso = ((raw.get("run") or {}).get("isolation")) or {}
    env = iso.get("envelope") or {}
    if env:
        return {"isolation": "container", "memory_gib": round(env.get("memory_mib", 0) / 1024, 2) if env.get("memory_mib") else None, "cpus": len(env.get("cpuset_cpus") or []) or None,
                "timeout_s": (raw.get("run") or {}).get("timeout_s")}
    return {"isolation": "bare", "memory_gib": None, "cpus": len((raw.get("run") or {}).get("harness_cpus") or []) or None, "stamp": iso.get("stamp")}


def tier_name(limits):
    """The tier is part of a result's name: `4GiB`, or `bare` for an uncontained run."""
    return f"{limits['memory_gib']:g}GiB" if limits.get("memory_gib") else "bare"
