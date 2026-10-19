# SPDX-License-Identifier: Apache-2.0
"""The swarm samples (`scale/agents-limit`, `scale/print-limit`, `scale/agents-ext10`, `scale/print-ext10`, and the earlier `scale/agents-N`, `scale/print-N`) as the Scale page draws them.

A scale sample holds N agents of one harness that ran at once in one container (the swarm envelope: a memory limit, a cpuset, a pids limit; buffon/workloads/scale.py).
A probe is one N that was tried. A probe is complete when every agent was ready and done. The search doubles N, 1, 2, 4, 8 and so on, until a probe does not complete, then bisects between the
last probe that completed and the first that did not, down to the exact number. One sample of a round is the whole search: `agents_limit` (the largest N that completed), `first_failure`, and
`probes`, every probe in the order run. A harness that completes the cap says "at least N (cap)" (`limit_capped`). The ext10 scenarios run the same search with the ten bench extensions loaded:
only a harness that loads Pi extensions takes part, the others are in `skipped` with the reason.
A stop caused by `oom` (the kernel killed agents) or `stall` (the container sat at its memory limit and nothing made progress) reads, for a person, "did not fit in <limit>": FIT_CAUSES.
The page asks how many agents fit, so the headline of an arm is its `limit`, the median over the measured rounds (the lower middle value for an even number, so that it is a number a round
produced), with the smallest and largest round as `range`.

A run made before the search holds one sample per rung (`scale/agents-N`): a ladder that doubled N until a rung did not complete, every larger rung in `skipped` with the reason
`not reached: stopped at N agents (<cause>)`. Such an arm is not exact: its `max_ok` P is the largest rung that completed in every round and the first stop is F, so the true number is
`between` P and F-1; a ladder that never stopped reads `at_least` its top rung. Never a single number.

The scale samples are kept out of the grid (the grid compares one process of each harness; a swarm is another question). Here they become, for each envelope, each kind (RPC or print,
and the same two with ten extensions: `rpc-ext10`, `print-ext10`) and each harness: one entry per probed N with the median of its measured rounds that probed it (the probes of all rounds
are pooled per N: the bisection of different rounds tries different N), every round of it (the derivation page shows them), and where and why the search stopped.
Nothing here is a number of its own: each value is a field of the sample, the median of that field over the rounds, or (`spread`) its smallest and largest value over the rounds.
A scale run has no A/A copy: the spread across rounds is its noise.

CPU per agent-turn is drawn only for a sample that has `start_cpu_ms_per_agent`, which marks the sample whose `cpu_ms_per_agent_turn` covers the same window as `turns_per_s` (RPC: the turn phase).
An earlier RPC sample took the container's CPU over the whole sample, start-up included: its value is dropped here, and the kind says so (`cpu_legacy`)."""
import re
import statistics

from ..report.cells import direction

KINDS = {"agents": "rpc", "print": "print"}
EXT = "-ext10"
KIND_ORDER = ("rpc", "print", "rpc" + EXT, "print" + EXT)
KIND_TITLE = {"rpc": "RPC agents", "print": "Print-mode agents", "rpc" + EXT: "RPC agents with 10 extensions", "print" + EXT: "Print-mode agents with 10 extensions"}
SCENARIO = re.compile(r"^scale/(agents|print)-(\d+|limit|ext10)$")
NOT_REACHED = re.compile(r"^not reached: stopped at (\d+) agents \((.*)\)$")
CAUSES = ("oom", "stall", "timeout", "pids", "error")
FIT_CAUSES = ("oom", "stall")   # the agents did not fit in the memory limit
# the reader-facing words of each cause: `fit` causes read "did not fit in <limit>", the others as they are; the detail is the second line of a tooltip and the derivation page
CAUSE_WORDS = {"oom": {"word": "did not fit", "fit": True, "detail": "the kernel killed agents"},
               "stall": {"word": "did not fit", "fit": True, "detail": "stalled at the limit, nothing was killed"},
               "timeout": {"word": "timed out", "fit": False, "detail": "the agents did not finish in time"},
               "pids": {"word": "hit the process limit", "fit": False, "detail": "the container could not start more processes"},
               "error": {"word": "failed", "fit": False, "detail": "an agent failed"}}

# The values a rung carries, as the samples name them. Lower is better for each one except turns_per_s and the agent counts.
FIELDS = ("agents_ok", "mem_baseline_mib", "mem_peak_mib", "mem_per_agent_mib", "pss_mib_per_agent", "cpu_ms", "cpu_ms_per_agent_turn", "start_cpu_ms_per_agent", "turns_per_s",
          "latency_ms_p50", "latency_ms_p95", "latency_ms_max", "ready_ms", "makespan_ms", "wall_ms_p50", "wall_ms_p95",
          "oom_kills", "pids_peak", "throttled_periods", "mock_cpu_ms")

# (key, title, unit, direction, one sentence, KaTeX or None). The direction is the report's own (buffon/report/cells.py `direction`: turns_per_s is higher is better); the page names it and never ranks by it.
METRICS = [
    ("mem_per_agent_mib", "Memory per agent", "MiB", direction("mem_per_agent_mib"), "The memory that the container holds above its start, divided by the number of agents.",
     r"m = \frac{\texttt{memory.peak} - m_{0}}{N}"),
    ("turns_per_s", "Turns per second", "turns/s", direction("turns_per_s"), "The agent-turns that the swarm finished in one second of the turn phase.", r"v = \frac{N K}{t_{\mathrm{last}} - t_{\mathrm{first}}}"),
    ("cpu_ms_per_agent_turn", "CPU per agent-turn", "ms", direction("cpu_ms_per_agent_turn"),
     "The CPU time of the container during the turn phase, without the relay, divided by the agent-turns. It covers the same window as turns per second.",
     r"c = \frac{\Delta\texttt{cpu.stat}_{\mathrm{turns}} - c_{\mathrm{relay}}}{N K}"),
    ("start_cpu_ms_per_agent", "Start-up CPU per agent", "ms", direction("start_cpu_ms_per_agent"), "The CPU time of the container from the start of the first agent to the last ready, without the relay, divided by the number of agents.",
     r"s = \frac{\Delta\texttt{cpu.stat}_{\mathrm{start}} - c_{\mathrm{relay}}}{N}"),
    ("mem_peak_mib", "Memory of the whole container", "MiB", direction("mem_peak_mib"), "The most memory that the kernel counted for the container at one moment (memory.peak).", r"M = \texttt{memory.peak}"),
    ("latency_ms_p95", "Turn latency, 95th percentile", "ms", direction("latency_ms_p95"), "The time of one turn of one agent, from the prompt to the end of the turn. 19 turns in 20 were as fast as this.",
     r"\ell = P_{95}\bigl(t_{\mathrm{end}} - t_{\mathrm{prompt}}\bigr)"),
    ("wall_ms_p95", "Time to finish, 95th percentile", "ms", direction("wall_ms_p95"), "The time one agent takes from its start to its exit. 19 agents in 20 were as fast as this.", r"w = P_{95}\bigl(t_{\mathrm{exit}} - t_{\mathrm{start}}\bigr)"),
    ("makespan_ms", "Time until all agents finished", "ms", direction("makespan_ms"), "The time from the start of the first agent to the exit of the last.", r"T = \max_{a} t^{\mathrm{exit}}_{a} - \min_{a} t^{\mathrm{start}}_{a}"),
    ("ready_ms", "Time until all agents are ready", "ms", direction("ready_ms"), "The time from the start of the first agent until every agent has answered get_state.", r"r = \max_{a} t^{\mathrm{ready}}_{a} - \min_{a} t^{\mathrm{start}}_{a}"),
    ("pss_mib_per_agent", "Memory per agent (PSS)", "MiB", direction("pss_mib_per_agent"), "The proportional memory of one agent: pages that agents share count once, split between them.", None),
    ("cpu_ms", "CPU of the container, whole sample, start-up included", "ms", direction("cpu_ms"), "The CPU time of the container during the whole sample, start-up included, without the relay.", None),
    ("oom_kills", "OOM kills", "kills", direction("oom_kills"), "How many times the kernel stopped a process of the container for lack of memory.", None),
    ("pids_peak", "Processes at the peak", "processes", direction("pids_peak"), "The most processes that the container had at one moment.", None),
    ("throttled_periods", "Throttled periods", "periods", direction("throttled_periods"), "The scheduler periods in which the container used all of its CPU quota and was paused.", None),
    ("mock_cpu_ms", "CPU of the scripted model", "ms", direction("mock_cpu_ms"), "The CPU time of the scripted model during the sample.", None),
]
METRIC = {m[0]: m for m in METRICS}
# A print-mode agent does one task, not turns: its turns per second are tasks per second, and its CPU is the whole sample over the tasks (the same window).
PRINT_WORDS = {"turns_per_s": ("Tasks per second", "tasks/s", "The tasks that the swarm finished in one second: each agent does one task, from its start to its exit.", None),
               "cpu_ms_per_agent_turn": ("CPU per task", "ms", "The CPU time of the container during the whole sample, without the relay, divided by the number of tasks (one per agent). It covers the same window as tasks per second.",
                                         r"c = \frac{\Delta\texttt{cpu.stat} - c_{\mathrm{relay}}}{N}")}
# the charts of each kind, in order: memory, throughput, CPU, each against N. The other metrics are in the table view and the derivation of a rung.
CHARTS = {"rpc": ("mem_per_agent_mib", "turns_per_s", "cpu_ms_per_agent_turn"), "print": ("mem_per_agent_mib", "turns_per_s", "cpu_ms_per_agent_turn")}
# the few words that say which phase a chart covers, after its unit
NOTES = {("rpc", "cpu_ms_per_agent_turn"): "turn phase only", ("print", "cpu_ms_per_agent_turn"): "whole sample"}
# the metrics each kind has in its table and in the derivation of a rung
KIND_KEYS = {"rpc": ("mem_per_agent_mib", "mem_peak_mib", "latency_ms_p95", "turns_per_s", "cpu_ms_per_agent_turn", "start_cpu_ms_per_agent", "ready_ms", "pss_mib_per_agent", "cpu_ms", "oom_kills", "pids_peak", "throttled_periods", "mock_cpu_ms"),
             "print": ("mem_per_agent_mib", "mem_peak_mib", "wall_ms_p95", "makespan_ms", "turns_per_s", "cpu_ms_per_agent_turn", "pss_mib_per_agent", "cpu_ms", "oom_kills", "pids_peak", "throttled_periods", "mock_cpu_ms")}


def metrics_for(kind):
    """[(key, title, unit, direction, about, tex)] of one kind of swarm, in the order of its table."""
    out = []
    for key in KIND_KEYS[kind]:
        k, title, unit, d, about, tex = METRIC[key]
        if kind == "print" and key in PRINT_WORDS:
            title, unit, about, new_tex = PRINT_WORDS[key]
            tex = new_tex or tex
        out.append((k, title, unit, d, about, tex))
    return out


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf")


def cause_of(text, given=None):
    """The stop cause as one of CAUSES: the sample's own `stop_cause`, else read from the words."""
    if given in CAUSES:
        return given
    low = str(text or "").lower()
    if "stall" in low:
        return "stall"
    if "oom" in low or "out of memory" in low or "did not fit" in low:
        return "oom"
    if "pid" in low or "process limit" in low:
        return "pids"
    if "timeout" in low or "timed out" in low:
        return "timeout"
    return "error"


def envelope_key(swarm):
    swarm = swarm or {}
    return swarm.get("memory_mib"), len(swarm.get("cpus") or [])


def envelope_id(memory_mib, cores):
    if memory_mib is None:
        return "unrecorded"
    gib = memory_mib / 1024
    return f"{gib:g}g-{cores}c"


def envelope_label(memory_mib, cores):
    if memory_mib is None:
        return "an envelope the run does not record"
    return f"{memory_mib / 1024:g} GiB of memory, {cores} {'core' if cores == 1 else 'cores'}"


def med(values):
    values = [v for v in values if num(v)]
    return statistics.median(values) if values else None


def rung_of(n, samples, kind):
    """One rung of one harness: one N, with every probe of it (one for each measured round that tried it: a search probes other N in other rounds). Its status (ok, stopped, from any probed round), the median of each value over those rounds, the smallest and largest of each (`spread`), and every round.
    An RPC sample without `start_cpu_ms_per_agent` took its CPU over the whole sample: its `cpu_ms_per_agent_turn` is not the turn phase's, so it is left out."""
    measured = [s for s in samples if not s.get("warmup")] or samples
    rounds = []
    for s in sorted(measured, key=lambda s: s.get("round", 0)):
        failed = "failure" in s
        agents_ok = s.get("agents_ok", 0 if failed else n)
        ok = not failed and agents_ok == n
        values = {k: s[k] for k in FIELDS if num(s.get(k))}
        if kind.startswith("rpc") and "start_cpu_ms_per_agent" not in values:
            values.pop("cpu_ms_per_agent_turn", None)
        entry = {"round": s.get("round"), "warmup": bool(s.get("warmup")), "ok": ok, "values": values}
        if "mock_saturated" in s:
            entry["mock_saturated"] = bool(s["mock_saturated"])
        if not ok:
            entry["failure"] = str(s.get("failure") or f"{agents_ok} of {n} agents finished")
            entry["cause"] = cause_of(entry["failure"], s.get("stop_cause"))
        rounds.append(entry)
    good = [r for r in rounds if r["ok"]]
    basis = good if len(good) == len(rounds) else rounds   # a rung with any failed round shows the medians of all its rounds, and is a stop
    keys = [k for k in FIELDS if any(k in r["values"] for r in basis)]
    rung = {"n": n, "status": "ok" if len(good) == len(rounds) else "stopped", "rounds": rounds,
            "med": {k: med([r["values"].get(k) for r in basis]) for k in keys},
            "spread": {k: [min(v), max(v)] for k in keys for v in ([x["values"][k] for x in basis if k in x["values"]],) if len(v) > 1},
            "mock_saturated": any(r.get("mock_saturated") for r in rounds), "runs": sorted({s["_run"] for s in measured if "_run" in s})}
    bad = [r for r in rounds if not r["ok"]]
    if bad:
        rung["failure"], rung["cause"] = bad[0]["failure"], bad[0]["cause"]
    return rung


def scenario_of(text):
    """(kind, n, extension) of a scale scenario id: `scale/agents-limit` is ("rpc", None, False), `scale/print-ext10` ("print-ext10", None, True), `scale/agents-8` ("rpc", 8, False). None for another scenario."""
    m = SCENARIO.match(text or "")
    if not m:
        return None
    kind, tail = KINDS[m.group(1)], m.group(2)
    if tail == "ext10":
        return kind + EXT, None, True
    return kind, (int(tail) if tail.isdigit() else None), False


def probes_pooled(measured):
    """{n: [probe as a sample]} of the probes of the measured rounds, in the shape `rung_of` reads: a failed probe has its `failure` words."""
    pooled = {}
    for s in measured:
        for p in s.get("probes") or []:
            n = p.get("n")
            if not isinstance(n, int) or isinstance(n, bool) or n < 1:
                continue
            probe = dict(p, round=s.get("round", 0), warmup=False, _run=s.get("_run"))
            if p.get("ok") is False and not p.get("failure"):
                probe["failure"] = f"{p.get('agents_ok', 0)} of {n} agents finished"
            elif p.get("ok") is not False:
                probe.pop("failure", None)
            pooled.setdefault(n, []).append(probe)
    return pooled


def search_arm(samples, kind):
    """One harness of one search kind: the limit (the median of the measured rounds, the lower middle one for an even number), the limit of each round and their range, the stop of the median round,
    and the rungs: the probes of every measured round pooled per N."""
    measured = sorted([s for s in samples if not s.get("warmup")] or samples, key=lambda s: s.get("round", 0))
    limits = [int(s["agents_limit"]) if num(s.get("agents_limit")) else 0 for s in measured]
    mid = sorted(range(len(limits)), key=lambda i: (limits[i], i))[(len(limits) - 1) // 2]
    pick, limit = measured[mid], limits[mid]
    rungs = [rung_of(n, ps, kind) for n, ps in sorted(probes_pooled(measured).items())]
    capped = bool(pick.get("limit_capped"))
    own = pick.get("probes") or []
    failed = [p for p in own if p.get("ok") is False and isinstance(p.get("n"), int)]
    first = None if capped else (int(pick["first_failure"]) if num(pick.get("first_failure")) else (min(p["n"] for p in failed) if failed else (1 if limit == 0 else None)))
    at = next((p for p in own if first is not None and p.get("n") == first and p.get("ok") is False), {})
    failure = pick.get("limit_failure") or pick.get("failure") or at.get("failure")
    cause = None if capped or first is None else cause_of(failure, pick.get("limit_cause") or pick.get("stop_cause") or at.get("stop_cause"))
    caps = [s["limit_cap"] for s in measured if num(s.get("limit_cap"))]
    resolution = int(pick["limit_resolution"]) if num(pick.get("limit_resolution")) else 1
    stop = None if first is None else {"n": first, "cause": cause, "failure": failure, "oom_kills": at.get("oom_kills"), "agents_ok": at.get("agents_ok")}
    arm = {"exact": True, "scenario": "scale/" + ("agents" if kind.startswith("rpc") else "print") + ("-ext10" if kind.endswith(EXT) else "-limit"), "extensions": int(pick.get("extensions") or 0),
           "limit": limit, "limits": limits, "range": [min(limits), max(limits)], "capped": capped, "cap": int(pick["limit_cap"]) if num(pick.get("limit_cap")) else (max(caps) if caps else None),
           "resolution": resolution, "cause": cause, "failure": failure, "first_failure": first, "probe_count": pick.get("probe_count", len(own)),
           "max_ok": limit, "or_more": capped, "stop": stop, "rungs": rungs, "skipped": []}
    if resolution > 1 and first is not None and first - limit > 1:
        arm["between"] = [limit, first - 1]   # the bisection stopped at a step of `resolution`: the true limit is in this range
    return arm


def ladder_arm(by_n, reached, kind):
    """One harness of a run made before the search: its rungs, the first stop, and the range the true number lies in. Not exact."""
    rungs = [rung_of(n, by_n[n], kind) for n in sorted(by_n)]
    skips = list({x["n"]: x for x in reached if x["n"] not in {r["n"] for r in rungs}}.values())
    # the stop: the first rung that did not complete (the ladder stops there), else a stop only the skipped list names
    stop = None
    for r in rungs:
        if r["status"] != "ok":
            stop = {"n": r["n"], "cause": r["cause"], "failure": r["failure"], "oom_kills": r["med"].get("oom_kills"), "agents_ok": r["med"].get("agents_ok")}
            break
    if stop is None and skips:
        first = min(skips, key=lambda x: x["from"])
        stop = {"n": first["from"], "cause": first["cause"], "failure": first["words"], "oom_kills": None, "agents_ok": None}
    max_ok = None
    for r in rungs:
        if r["status"] != "ok":
            break
        max_ok = r["n"]
    arm = {"exact": False, "scenario": "scale/" + ("agents" if kind.startswith("rpc") else "print") + "-N", "max_ok": max_ok, "or_more": stop is None, "stop": stop, "rungs": rungs,
           "skipped": [{"n": x["n"], "reason": x["reason"]} for x in sorted(skips, key=lambda x: x["n"])]}
    if stop:
        arm["between"] = [max_ok or 0, stop["n"] - 1]
    else:
        arm["at_least"] = max_ok
    return arm


def build(runs, skipped, arms):
    """`runs` is [(run id, raw dict)], `skipped` the runs' skipped entries, `arms` the harness ids the site shows. None when no run holds a swarm sample.
    An arm that has search samples in an envelope is shown by them; one that has only rung samples (an earlier run) by its ladder."""
    found = {}   # (memory, cores) -> {"swarm": {...}, "runs": set, "pids": [...], "samples": {kind -> arm -> n -> [samples]}, "search": {kind -> arm -> [samples]}}
    for run_id, raw in runs:
        for s in raw.get("samples", []):
            hit = scenario_of(s.get("scenario"))
            if not hit or s.get("arm") not in arms:
                continue
            kind, n, ext = hit
            key = envelope_key(s.get("swarm"))
            env = found.setdefault(key, {"swarm": s.get("swarm") or {}, "runs": set(), "pids": [], "samples": {}, "search": {}})
            env["runs"].add(run_id)
            env["pids"] += [x for x in [(s.get("swarm") or {}).get("pids_max")] + [p.get("pids_max") for p in s.get("probes") or []] if num(x)]
            if n is None:
                env["search"].setdefault(kind, {}).setdefault(s["arm"], []).append(dict(s, _run=run_id))
            else:
                env["samples"].setdefault(kind, {}).setdefault(s["arm"], {}).setdefault(n, []).append(dict(s, _run=run_id))
    if not found:
        return None
    cannot, reached = {}, {}   # (kind, arm) -> reason it cannot run; (kind, arm) -> [(n, cause words)] from the skipped list
    for s in skipped:
        hit = scenario_of(s.get("scenario"))
        if not hit or s.get("arm") not in arms or not s.get("reason"):
            continue
        kind, n, ext = hit
        stopped = NOT_REACHED.match(s["reason"])
        if stopped and n is not None:
            reached.setdefault((kind, s["arm"]), []).append({"n": n, "from": int(stopped.group(1)), "cause": cause_of(stopped.group(2)), "words": stopped.group(2), "reason": s["reason"]})
        elif not stopped:
            cannot.setdefault((kind, s["arm"]), s["reason"])
    envelopes = []
    for (memory, cores), env in sorted(found.items(), key=lambda kv: (kv[0][0] is None, kv[0][0] or 0, kv[0][1])):
        swarm = env["swarm"]
        kinds = {}
        for kind in KIND_ORDER:
            by_arm, searched = env["samples"].get(kind, {}), env["search"].get(kind, {})
            if kind.endswith(EXT) and not searched and not (any((kind, a) in cannot for a in arms) and (env["search"].get(kind[:-len(EXT)]) or env["samples"].get(kind[:-len(EXT)]))):
                continue   # the run has no extension sample, and no harness that was left out of one
            entry = {"title": KIND_TITLE[kind], "arms": {}}
            for arm in arms:
                if arm in searched:
                    entry["arms"][arm] = search_arm(searched[arm], kind)
                elif arm in by_arm:
                    entry["arms"][arm] = ladder_arm(by_arm[arm], reached.get((kind, arm), []), kind)
                elif (kind, arm) in cannot:
                    entry["arms"][arm] = {"cannot": cannot[(kind, arm)]}
            entry["ns"] = sorted({r["n"] for a in entry["arms"].values() for r in a.get("rungs", [])})
            # RPC: the CPU per agent-turn is drawn only where a rung has it (the sample carries `start_cpu_ms_per_agent`); a kind that has CPU samples and no such rung predates the field
            if kind.startswith("rpc"):
                raw = [x for a in by_arm.values() for xs in a.values() for x in xs] + [p for xs in searched.values() for x in xs for p in x.get("probes") or []]
                entry["cpu_legacy"] = any("cpu_ms_per_agent_turn" in x for x in raw) and not any("start_cpu_ms_per_agent" in x for x in raw)
            kinds[kind] = entry
        envelopes.append({"id": envelope_id(memory, cores), "label": envelope_label(memory, cores), "memory_mib": memory, "cpus": list(swarm.get("cpus") or []), "cores": cores,
                          "pids_max": max(env["pids"]) if env["pids"] else swarm.get("pids_max"), "runs": sorted(env["runs"]), "kinds": kinds})
    return {"envelopes": envelopes}
