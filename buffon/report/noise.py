# SPDX-License-Identifier: Apache-2.0
"""The noise report: how noisy a run was, from its raw samples and their telemetry. Nothing here touches a file; every function is deterministic.

  flags(sample)            what a sample's telemetry says went wrong around it (buffon/report/thresholds.py: FLAGS)
  derive(samples)          each sample with its flags and the throttling an ancestor cgroup caused since the previous sample
  cell_noise(values)       per arm and cell: n, CV, MAD-rule outliers (`mad_k` in workloads/health.toml)
  drift(values)            the change of an arm's value over the run (Theil-Sen slope times the rounds)
  build(runs, data)        the whole noise report: per metric, throttling, gate, discarded rounds, flagged samples, host
"""
import collections
import math
import random

from .. import stats
from ..telemetry import probes
from . import cells as cellmath
from . import thresholds as T

FLAG_ORDER = list(T.FLAGS)


def system(sample):
    return ((sample.get("telemetry") or {}).get("system")) or None


def own_cpu_ms(sample, t):
    cg = t.get("cgroup") or {}
    if "cpu_usage_ms" in cg:
        return cg["cpu_usage_ms"]
    v = sample.get("cpu_ms")
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def flags(sample, ancestor_periods=0):
    """The flags of one sample, in FLAG_ORDER, or None when the sample has no telemetry (a failed sample the gate refused to start has none). `ancestor_periods` is how far an
    ancestor cgroup's nr_throttled grew since the previous sample (derive())."""
    t = system(sample)
    if t is None:
        return None
    cs, cg, dur = t.get("cpuset", {}), t.get("cgroup", {}), t.get("during", {})
    out = set()
    if max(cg.get("throttled_periods", 0), cs.get("session_throttled_periods", 0), ancestor_periods) >= T.THROTTLE_PERIODS:
        out.add("throttled")
    cpus, window = cs.get("cpuset_cpus"), cs.get("window_ms")
    if cpus and window:
        capacity = cpus * window
        foreign = foreign_ms(sample, t)
        if foreign is not None and foreign > T.FOREIGN_FRAC * capacity and foreign > allowance_ms(cpus):
            out.add("foreign_busy")
        if cs.get("cpuset_steal_ms", 0) > T.STEAL_FRAC * capacity:
            out.add("steal")
    lo, hi = dur.get("mhz_min"), dur.get("mhz_max")
    if lo and hi and hi / lo - 1 > T.CLOCK_MOVE:
        out.add("clock_moved")
    if (t.get("gate") or {}).get("status") == "waited":
        out.add("gate_waited")
    if cs.get("swap_pages", 0) >= T.SWAP_PAGES:
        out.add("swap")
    if cs.get("thermal_throttle_events", 0) >= T.THERMAL_EVENTS:
        out.add("thermal")
    ev = cg.get("memory_events") or {}
    if any(ev.get(k, 0) for k in ("high", "max", "oom", "oom_kill")):
        out.add("memory_events")
    return [f for f in FLAG_ORDER if f in out]


def allowance_ms(cpus):
    """The busy time /proc/stat's tick resolution can invent on `cpus` CPUs: T.FOREIGN_TICKS ticks per sqrt(CPU)."""
    return T.FOREIGN_TICKS * (1000.0 / probes.USER_HZ) * math.sqrt(cpus)


def foreign_ms(sample, t=None):
    """CPU time spent on the pinned CPUs during the sample that the sample's own cgroup does not explain (milliseconds, may be negative by rounding), or None when unknown."""
    t = t or system(sample)
    cs = (t or {}).get("cpuset") or {}
    own = own_cpu_ms(sample, t) if t else None
    if own is None or "cpuset_busy_ms" not in cs:
        return None
    return cs["cpuset_busy_ms"] - own


STOP_RESULTS = ("oom", "stall", "pids", "timeout")   # a swarm ladder's designed stops (buffon/workloads/scale.py): the kernel's OOM killer, a refused fork, a stage that ran out of time


def failure_kind(sample):
    """`stop` for a ladder's designed stop (a scale sample with `stop_cause` oom, stall, pids or timeout: the harness reached its limit, which is the result), `infra` for a failed sample the arm
    did not cause (the host never quieted down, the runner failed, the kernel killed the cgroup for memory), else `arm`. A scale `error` stop is an arm failure."""
    if sample.get("stop_cause") in STOP_RESULTS:
        return "stop"
    f = sample.get("failure", "")
    ev = (((system(sample) or {}).get("cgroup")) or {}).get("memory_events") or {}
    if sample.get("quiet_gave_up") or f.startswith(("runner error", "the host was not quiet", "the pinned CPUs were not quiet")) or "no process was started" in f or ev.get("oom_kill", 0):
        return "infra"
    return "arm"


Derived = collections.namedtuple("Derived", "sample flags throttled_us throttled_periods")


def derive(samples):
    """[Derived(sample, flags or None, throttled_us, throttled_periods)] in the order given. The throttling of an ancestor cgroup is cumulative, so each sample's share is the
    growth since the previous sample that read the same ancestor chain (the first sample of a chain has no baseline and gets 0)."""
    last, out = {}, []
    for s in samples:
        t = system(s)
        anc = ((t or {}).get("cgroup") or {}).get("ancestors")
        grown_us = grown_n = 0
        if anc and "chain" in anc:
            prev = last.get(anc["chain"])
            if prev is not None:
                grown_us, grown_n = max(0, anc["throttled_us"] - prev[1]), max(0, anc["nr_throttled"] - prev[0])
            last[anc["chain"]] = (anc["nr_throttled"], anc["throttled_us"])
        f = flags(s, grown_n)
        us = n = 0
        if t:
            cg, cs = t.get("cgroup") or {}, t.get("cpuset") or {}
            us = max(cg.get("throttled_us", 0), cs.get("session_throttled_us", 0), grown_us)
            n = max(cg.get("throttled_periods", 0), cs.get("session_throttled_periods", 0), grown_n)
        out.append(Derived(s, f, us, n))
    return out


# -- statistics -------------------------------------------------------------------------------------------------------------------------------


def mad(xs, med=None):
    med = stats.median(xs) if med is None else med
    return stats.median([abs(x - med) for x in xs])


def outliers(values):
    """The values the MAD rule flags (T.OUTLIER_RULE); none with fewer than T.OUTLIER_MIN_N values."""
    xs = list(values)
    if len(xs) < T.OUTLIER_MIN_N:
        return []
    med = stats.median(xs)
    limit = T.MAD_K * 1.4826 * mad(xs, med)
    return [v for v in xs if abs(v - med) > limit]


def theil_sen(xs, ys):
    """Median of the pairwise slopes: a trend estimate that one wild value does not move. nan with fewer than two distinct x."""
    slopes = [(ys[j] - ys[i]) / (xs[j] - xs[i]) for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j] != xs[i]]
    return stats.median(slopes) if slopes else math.nan


def when(key):
    """The position of a round on the time axis. Cells key a round by (run, round), since round 3 of one run directory and round 3 of another are different rounds."""
    return key[0] * 10000.0 + key[1] if isinstance(key, tuple) else float(key)


def drift(values):
    """The change of one arm's value over the run as a fraction of its median: Theil-Sen slope per round times the rounds spanned. nan when there is no trend to estimate."""
    rounds = sorted(values)
    if len(rounds) < 3:
        return math.nan
    ys = [values[r] for r in rounds]
    med = stats.median(ys)
    slope = theil_sen([when(r) for r in rounds], ys)
    return slope * (when(rounds[-1]) - when(rounds[0])) / med if med and slope == slope else math.nan


def cell_noise(cell):
    """{arm: {"n", "cv", "outliers", "drift"}} for one cell, A/A copies included."""
    out = {}
    for arm, vals in cell.values.items():
        xs = list(vals.values())
        out[arm] = {"n": len(xs), "cv": stats.cv(xs), "outliers": len(outliers(xs)), "drift": drift(vals), "iqr": stats.percentile(xs, 75) - stats.percentile(xs, 25) if xs else math.nan}
    return out


def num(x):
    if x is None or x != x:
        return "n/a"
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:.3g}"


def cell_columns(cell, ref, arm):
    """("CV ref / arm", "IQR ref / arm", "outliers ref / arm") as table text for one comparison row: the dispersion next to the headline ratio."""
    n = cell_noise(cell)
    r, a = n.get(ref), n.get(arm)
    return (f"{pct(r['cv']) if r else 'n/a'} / {pct(a['cv']) if a else 'n/a'}", f"{num(r['iqr']) if r else 'n/a'} / {num(a['iqr']) if a else 'n/a'}",
            f"{r['outliers'] if r else 'n/a'} / {a['outliers'] if a else 'n/a'}")


def aa_gap(cell, arm):
    """|median of the copy / median of the arm - 1| for one arm's A/A pair in a cell, or nan."""
    twin = arm + "-b"
    if arm in cell.values and twin in cell.values:
        a, b = stats.pair_by_round(cell.values[arm], cell.values[twin])
        if len(a) >= 2 and stats.median(a):
            return abs(stats.median(b) / stats.median(a) - 1)
    return math.nan


def _med(xs):
    xs = [x for x in xs if x == x and x is not None]
    return stats.median(xs) if xs else math.nan


def _max(xs):
    xs = [x for x in xs if x == x and x is not None]
    return max(xs) if xs else math.nan


# -- the report -------------------------------------------------------------------------------------------------------------------------------


def by_metric(data):
    """One row per scored metric, over every scenario and API: A/A gap and floor (median, worst), CV (median, worst), outliers, drift."""
    rows = {}
    for cell in data["cells"]:
        r = rows.setdefault(cell.metric, {"metric": cell.metric, "cells": 0, "gap": [], "floor": [], "cv": [], "outliers": 0, "values": 0, "drift": []})
        r["cells"] += 1
        for arm in data["base"]:
            g = aa_gap(cell, arm)
            if g == g:
                r["gap"].append(g)
            f = cell.aa.get(arm, (None,))[0]
            if f is not None:
                r["floor"].append(math.expm1(f))
        for arm, n in cell_noise(cell).items():
            r["cv"].append(n["cv"])
            r["outliers"] += n["outliers"]
            r["values"] += n["n"]
            if not arm.endswith("-b"):
                r["drift"].append(abs(n["drift"]) if n["drift"] == n["drift"] else math.nan)
    out = []
    for m in sorted(rows):
        r = rows[m]
        out.append({"metric": m, "cells": r["cells"], "aa_gap_median": _med(r["gap"]), "aa_gap_max": _max(r["gap"]), "aa_floor_median": _med(r["floor"]), "aa_floor_max": _max(r["floor"]),
                    "cv_median": _med(r["cv"]), "cv_max": _max(r["cv"]), "outliers": r["outliers"], "values": r["values"], "drift_median": _med(r["drift"]), "drift_max": _max(r["drift"])})
    return out


def per_cell(data):
    """Rows for noise.csv: per arm and cell, the noise of its values."""
    rows = []
    for cell in data["cells"]:
        for arm, n in cell_noise(cell).items():
            gap = aa_gap(cell, arm) if not arm.endswith("-b") else math.nan
            floor = cell.aa.get(arm, (None,))[0] if not arm.endswith("-b") else None
            rows.append({"scenario": cell.scenario, "api": cell.api, "metric": cell.metric, "arm": arm, "n": n["n"], "cv": n["cv"], "outliers": n["outliers"], "drift": n["drift"],
                         "aa_gap": gap, "aa_floor": math.expm1(floor) if floor is not None else math.nan})
    return rows


def run_view(raw, facts, index):
    """Per-run facts of the noise report from one raw.json: samples and why some are not in the statistics, flags, throttling, the gate, the host."""
    samples = raw["samples"]
    seq = [s for s in samples if s["scenario"].split("/")[0] not in cellmath.SPECIAL_FAMILIES or "telemetry" in s]
    derived = derive(seq)
    measured = [d for d in derived if not d.sample["warmup"]]
    ok = [d for d in measured if "failure" not in d.sample]
    failed = [d.sample for d in measured if "failure" in d.sample]
    warm = [s for s in samples if s["warmup"]]
    flagged = [(d.sample, d.flags) for d in ok if d.flags]
    counts = {name: sum(1 for _, f in flagged if name in f) for name in FLAG_ORDER}
    with_t = [d for d in ok if d.flags is not None]
    throttle_events = [{"arm": d.sample["arm"], "scenario": d.sample["scenario"], "api": d.sample.get("api"), "round": d.sample["round"], "throttled_us": d.throttled_us, "periods": d.throttled_periods}
                       for d in ok if d.flags and "throttled" in d.flags]
    gate = {"passed": 0, "waited": 0, "gave_up": 0, "disabled": 0, "waited_ms_total": 0, "waited_ms_max": 0, "slow": 0}
    for d in measured:
        s = d.sample
        if s.get("quiet_gave_up"):
            gate["gave_up"] += 1
            continue
        g = (system(s) or {}).get("gate") or {}
        st = g.get("status") or ("waited" if (s.get("quiet_checks") or 1) > 1 else "passed" if "quiet_wait_ms" in s else "disabled")
        gate[st if st in gate else "disabled"] += 1
        w = g.get("waited_ms", s.get("quiet_wait_ms")) or 0
        if st == "waited":
            gate["waited_ms_total"] += w
            gate["waited_ms_max"] = max(gate["waited_ms_max"], w)
        if w > 1000:
            gate["slow"] += 1
    parts = [((system(d.sample) or {}).get("collector") or {}) for d in with_t]
    cost = [sum(c.get(k) or 0 for k in ("thread_cpu_ms", "begin_cpu_ms", "end_cpu_ms")) for c in parts if "thread_cpu_ms" in c]
    srcs = sorted({x for d in with_t for x in (system(d.sample) or {}).get("sources", [])})
    flagged_rounds = sorted({(s["scenario"], s.get("api"), s["round"]) for s, _ in flagged}, key=lambda k: (k[0], str(k[1]), k[2]))
    steal = capacity = 0.0
    foreign, mhz, limited, modes = [], [], set(), set()
    for d in with_t:
        t = system(d.sample)
        cs = t.get("cpuset") or {}
        if cs.get("window_ms") and cs.get("cpuset_cpus") and "cpuset_steal_ms" in cs:
            steal += cs["cpuset_steal_ms"]
            capacity += cs["window_ms"] * cs["cpuset_cpus"]
        own, f = own_cpu_ms(d.sample, t), foreign_ms(d.sample, t)
        if own and f is not None and cs.get("cpuset_cpus"):
            foreign.append(max(0.0, f - allowance_ms(cs["cpuset_cpus"])) / own)
        m = (t.get("during") or {}).get("mhz_mean")
        if m:
            mhz.append(m)
        limited.update(((t.get("cgroup") or {}).get("ancestors") or {}).get("limited", []))
        modes.add((t.get("cgroup") or {}).get("mode"))
    run_t = ((raw["run"].get("telemetry") or {}).get("system") or {}).get("start") or {}
    if not modes & {"cgroup", "container"}:       # without a cgroup meter (a container has its own cgroup, whose quota the sample's throttling counters show) the harness runs inside the session's own cgroup, so its limits apply
        limited.update(run_t.get("quota_limited") or [])
    kinds = collections.Counter(failure_kind(s) for s in failed)
    med_mhz = stats.median(mhz) if mhz else None
    return {"index": index, "rounds": raw["run"].get("rounds"), "warmup_rounds": raw["run"].get("warmup"), "hardware": raw["hardware"].get("class"),
            "samples": {"measured": len(measured), "ok": len(ok), "failed": len(failed), "warmup": len(warm), "with_telemetry": len(with_t), "infra_failed": kinds["infra"], "arm_failed": kinds["arm"], "stopped": kinds["stop"]},
            "failed": [{"arm": s["arm"], "scenario": s["scenario"], "api": s.get("api"), "round": s["round"], "reason": s["failure"][:160], "kind": failure_kind(s)} for s in failed],
            "flag_counts": counts, "flagged_samples": len(flagged), "flagged_rounds": [list(k) for k in flagged_rounds],
            "flagged": [{"arm": s["arm"], "scenario": s["scenario"], "api": s.get("api"), "round": s["round"], "flags": f} for s, f in flagged],
            "throttled_samples": len(throttle_events), "throttled_us_total": sum(e["throttled_us"] for e in throttle_events), "throttle_events": throttle_events,
            "facts_throttled_us": (facts or {}).get("throttled_usec"), "gate": gate, "sources": srcs,
            "steal_share": steal / capacity if capacity else math.nan, "foreign_p95": stats.percentile(foreign, 95) if foreign else math.nan,
            "clock_deviation": max(abs(m / med_mhz - 1) for m in mhz) if mhz else math.nan, "clock_median_mhz": med_mhz, "cpu_quota_limited": sorted(limited),
            "fixed_clock": (facts or {}).get("fixed_clock"),
            "collector_cpu_ms_median": _med(cost), "collector_cpu_ms_max": _max(cost),
            "calibration": {k: (raw.get("calibration") or {}).get(k) for k in ("metric", "max_cv", "gate", "passed", "runs", "arm")},
            "host": {"load_before": (facts or {}).get("load_before"), "load_after": (facts or {}).get("load_after"), "idle_before": (facts or {}).get("idle_before"),
                     "idle_after": (facts or {}).get("idle_after"), "cpumon": (facts or {}).get("cpumon")}}


def discarded(views):
    """Why samples are not in the statistics: [(reason, samples, rounds)] over the runs. The warm-up and the failed samples are discarded by rule; a flagged sample is kept (and
    listed) unless the report is made with --drop-flagged."""
    rows = []
    warm = sum(v["samples"]["warmup"] for v in views)
    if warm:
        rows.append(("warm-up round (kept in the raw data, excluded from the statistics by rule)", warm, sum(v["warmup_rounds"] or 0 for v in views)))
    failed = [f for v in views for f in v["failed"]]
    by_reason = {}
    for f in failed:
        by_reason.setdefault(f["reason"].split(":")[0][:90], []).append(f)
    for reason, items in sorted(by_reason.items()):
        rows.append((f"failed sample: {reason}", len(items), len({(f["scenario"], f["api"], f["round"]) for f in items})))
    return rows


def drop_flagged(runs):
    """Copies of the raw runs without the rounds that carry a flagged sample: all arms' samples of one (scenario, API, round), so the interleaving stays symmetric. Returns
    (runs, [(run index, scenario, api, round, flags)])."""
    out, dropped = [], []
    for i, raw in enumerate(runs):
        bad = {}
        for d in derive(raw["samples"]):
            s, f = d.sample, d.flags
            if f and not s["warmup"] and "failure" not in s:
                bad.setdefault((s["scenario"], s.get("api"), s["round"]), set()).update(f)
        kept = [s for s in raw["samples"] if (s["scenario"], s.get("api"), s["round"]) not in bad or s["warmup"]]
        out.append(dict(raw, samples=kept))
        dropped += [(i + 1, k[0], k[1], k[2], sorted(v)) for k, v in sorted(bad.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2]))]
    return out, dropped


def build(runs, facts, data):
    """The noise report as plain data."""
    views = [run_view(raw, facts[i] if i < len(facts) else {}, i + 1) for i, raw in enumerate(runs)]
    return {"views": views, "by_metric": by_metric(data), "discarded": discarded(views), "outlier_rule": T.OUTLIER_RULE, "flag_rules": T.FLAGS, "cells": per_cell(data)}


def sensitivity(runs, data, reference=None, seed=0):
    """What the flagged rounds change: the report is built again without them and each comparison's verdict compared. None when no round is flagged or too few remain."""
    used, dropped = drop_flagged(runs)
    if not dropped or any(len({s["round"] for s in r["samples"] if not s["warmup"]}) < 4 for r in used):
        return None
    again = cellmath.build(used, reference, seed)
    was = {(c.scenario, c.api, c.metric, a): x.verdict for c in data["cells"] for a, x in c.comparisons.items()}
    now = {(c.scenario, c.api, c.metric, a): x.verdict for c in again["cells"] for a, x in c.comparisons.items()}
    common = sorted(set(was) & set(now), key=lambda k: tuple(str(x) for x in k))
    flips = [{"scenario": k[0], "api": k[1], "metric": k[2], "arm": k[3], "with_flagged": was[k], "without_flagged": now[k]} for k in common if was[k] != now[k]]
    return {"rounds_dropped": len(dropped), "comparisons": len(common), "verdict_changes": len(flips), "changes": flips[:40]}


# -- text -------------------------------------------------------------------------------------------------------------------------------------


def pct(x, digits=1):
    return "n/a" if x is None or x != x else f"{x:.{digits}%}"


def lines(report, prov_tag=""):
    """Markdown for the noise report."""
    out = [f"## Noise report{prov_tag}", "", "How noisy this run was, from its own samples and the telemetry taken around each one (docs/TELEMETRY.md). The A/A figures compare each arm with its own identical copy, "
           "so they show what the host does to two runs of the same executable.", ""]
    out += ["### Per metric", "", "| metric | cells | A/A gap median | A/A gap worst | A/A floor median | A/A floor worst | CV median | CV worst | outliers / values | drift median |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in report["by_metric"]:
        out.append(f"| {r['metric']} | {r['cells']} | {pct(r['aa_gap_median'])} | {pct(r['aa_gap_max'])} | {pct(r['aa_floor_median'])} | {pct(r['aa_floor_max'])} | "
                   f"{pct(r['cv_median'])} | {pct(r['cv_max'])} | {r['outliers']} / {r['values']} | {pct(r['drift_median'])} |")
    if not report["by_metric"]:
        out.append("| (no scored cells) | | | | | | | | | |")
    out += ["", f"A/A gap: the copy's median against the arm's, per cell. A/A floor: the largest deviation from 1 the copy's ratio interval allows (METHODOLOGY section 6). CV: the standard deviation of an arm's rounds over their mean. "
            f"Outliers: {report['outlier_rule']} Drift: the Theil-Sen trend of an arm's rounds times the rounds spanned, as a share of its median.", ""]
    for v in report["views"]:
        out += [f"### Run {v['index']}", ""]
        s, cal = v["samples"], v["calibration"]
        out += [f"- Samples: {s['measured']} measured ({s['ok']} ok, {s['failed']} failed), {s['warmup']} warm-up; telemetry on {s['with_telemetry']} of {s['ok']} ok samples. Sources read: {', '.join(v['sources']) or 'none'}.",
                f"- Calibration: CV {pct(cal.get('max_cv'))} of {cal.get('metric')} on {cal.get('arm')} (gate {pct(cal.get('gate'))}), {'passed' if cal.get('passed') else 'FAILED or not run'}.",
                f"- CFS throttling: {v['throttled_samples']} samples, {v['throttled_us_total']} us in all; the session's cgroup lost {v['facts_throttled_us'] if v['facts_throttled_us'] is not None else 'n/a'} us over the whole run.",
                f"- Quiet-host gate: {v['gate']['passed']} passed at once, {v['gate']['waited']} waited (longest {v['gate']['waited_ms_max'] / 1000:.1f} s, {v['gate']['waited_ms_total'] / 1000:.1f} s in all), {v['gate']['gave_up']} gave up.",
                f"- Steal: {pct(v['steal_share'], 3)} of the pinned CPUs' capacity. Foreign CPU on the pinned CPUs: p95 {pct(v['foreign_p95'])} of the sample's CPU time. Clock: largest deviation {pct(v['clock_deviation'])} from the median "
                f"{'%.0f MHz' % v['clock_median_mhz'] if v['clock_median_mhz'] else 'n/a'}. iowait is recorded in every sample and never gated.",
                f"- Failed samples: {s['arm_failed']} arm, {s['infra_failed']} infrastructure (the arm is not charged for those); {s['stopped']} ladder stops (a swarm rung that hit the kernel's limit: a result, not a failure). CPU quota on the arm cgroup or an ancestor: {', '.join(v['cpu_quota_limited']) or 'none'}.",
                f"- Flagged samples: {v['flagged_samples']} of {s['ok']}" + (" (" + ", ".join(f"{k} {n}" for k, n in v["flag_counts"].items() if n) + ")" if v["flagged_samples"] else "") + ".",
                f"- Telemetry cost: the collector's thread used {v['collector_cpu_ms_median']:.2f} ms median per sample (worst {v['collector_cpu_ms_max']:.2f} ms), on the runner's CPUs, outside the pinned set." if v["collector_cpu_ms_median"] == v["collector_cpu_ms_median"] else "- Telemetry cost: no readings.",
                f"- Host load before / after: {fmt_load(v['host']['load_before'])} / {fmt_load(v['host']['load_after'])}; pinned CPUs busy over the run: mean {pct((v['host']['cpumon'] or {}).get('pinned_busy_mean'))}, max {pct((v['host']['cpumon'] or {}).get('pinned_busy_max'))}.", ""]
        if v["throttle_events"]:
            out += ["Throttling events:", "", "| arm | workload | api | round | throttled us | periods |", "|---|---|---|---:|---:|---:|"]
            out += [f"| {e['arm']} | {e['scenario']} | {e['api'] or '-'} | {e['round']} | {e['throttled_us']} | {e['periods']} |" for e in v["throttle_events"][:20]]
            out.append("")
        if v["flagged"]:
            out += [f"Flagged samples (kept in the statistics unless the report is made with `--drop-flagged`; the first {min(len(v['flagged']), 25)} of {len(v['flagged'])}):", "",
                    "| arm | workload | api | round | flags |", "|---|---|---|---:|---|"]
            out += [f"| {e['arm']} | {e['scenario']} | {e['api'] or '-'} | {e['round']} | {', '.join(e['flags'])} |" for e in v["flagged"][:25]]
            out.append("")
    sens = report.get("sensitivity")
    if sens:
        out += ["### Do the flagged rounds change the answer?", "", f"The report was built again without the {sens['rounds_dropped']} flagged rounds: {sens['verdict_changes']} of {sens['comparisons']} comparisons change verdict."]
        if sens["changes"]:
            out += ["", "| workload | api | metric | arm | with flagged rounds | without |", "|---|---|---|---|---|---|"]
            out += [f"| {c['scenario']} | {c['api'] or '-'} | {c['metric']} | {c['arm']} | {c['with_flagged']} | {c['without_flagged']} |" for c in sens["changes"][:15]]
        out.append("")
    if report.get("dropped"):
        out += [f"### Rounds dropped with `--drop-flagged`", "", f"{len(report['dropped'])} (run, workload, api, round) groups are left out of every statistic above, all arms together:", "",
                "| run | workload | api | round | flags |", "|---:|---|---|---:|---|"]
        out += [f"| {r} | {sc} | {ap or '-'} | {rd} | {', '.join(fl)} |" for r, sc, ap, rd, fl in report["dropped"][:30]] + [""]
    out += ["### Samples and rounds not in the statistics", "", "| reason | samples | rounds |", "|---|---:|---:|"]
    out += [f"| {r} | {n} | {k} |" for r, n, k in report["discarded"]] or ["| none | 0 | 0 |"]
    out += ["", "Flags (buffon/report/thresholds.py):", ""] + [f"- `{k}`: {v}" for k, v in report["flag_rules"].items()] + [""]
    return out


def fmt_load(x):
    return "n/a" if not x else f"{x[0]:.1f}"
