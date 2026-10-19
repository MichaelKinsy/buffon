# SPDX-License-Identifier: Apache-2.0
"""The run notes of a report: what the host and the run looked like, with the usual range of each check (buffon/report/thresholds.py, docs/HEALTH.md).

Every check has a measured value, a one-line meaning and a status. `ok` means the value is inside the usual range. `note` means it is outside. A note is information for the reader. It
never grades, rejects or hides a run, and there is no overall verdict. The notes are computed from the raw data and the noise report, never stored in raw.json, so a reader or CI
recomputes them and gets the same answer.
A check without data (for example the A/A gap of a run that has no scored cell) has no value and is `ok`: there is nothing to note, and the report says so.
"""
import math

from . import aa as aalib
from . import thresholds as T

MIN_ROUNDS = 12


# A measurement the runner could not take (a pod that cannot see the clock, a run without telemetry) is a note: the reader should know it is missing.
MISSING_IS_NOTE = {"flagged_fraction", "steal_share", "foreign_cpu_p95", "clock_deviation"}


def _missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def _status(value, usual):
    """`note` when the value is above the usual range, else `ok` (also `ok` when there is no value)."""
    return "ok" if _missing(value) or value <= usual else "note"


def _med(xs):
    xs = sorted(x for x in xs if x == x and x is not None)
    if not xs:
        return math.nan
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _worst(xs):
    xs = [x for x in xs if x == x and x is not None]
    return max(xs) if xs else math.nan


def values(runs, data, noise):
    """The measured value of each threshold check."""
    views = noise["views"]
    ok = sum(v["samples"]["ok"] for v in views)
    measured = sum(v["samples"]["measured"] for v in views)
    with_t = sum(v["samples"]["with_telemetry"] for v in views)
    floors = [math.expm1(f) for c in data["cells"] for arm, (f, _) in c.aa.items() if f is not None]
    cells = noise["cells"]
    n_values = sum(r["n"] for r in cells)
    hits, tested = aalib.significant(data)
    gaps = [g for g, _, _ in aalib.gaps(data)]
    stopped = sum(v["samples"].get("stopped", 0) for v in views)
    counted = measured - stopped   # a swarm ladder's designed stop (stop_cause oom, stall, pids or timeout) is a result: it is neither a failure nor a sample the failure fractions count
    return {
        "calibration_cv": max((v["calibration"].get("max_cv") for v in views if v["calibration"].get("max_cv") is not None), default=math.nan),
        "aa_cv_cpu": _med(aalib.cv_cpu(data)),
        "aa_significant_fraction": hits / tested if tested else math.nan,
        "aa_gap_median": _med(gaps), "aa_gap_max": max(gaps, default=math.nan),
        "aa_floor_median": _med(floors), "aa_floor_max": max(floors, default=math.nan),
        "outlier_fraction": sum(r["outliers"] for r in cells) / n_values if n_values else math.nan,
        "flagged_fraction": sum(v["flagged_samples"] for v in views) / with_t if with_t else math.nan,
        "throttled_samples": sum(v["throttled_samples"] for v in views),
        "steal_share": _worst(v["steal_share"] for v in views),
        "foreign_cpu_p95": _worst(v["foreign_p95"] for v in views),
        "gate_slow_fraction": sum(v["gate"]["slow"] for v in views) / measured if measured else math.nan,
        "gate_gave_up": sum(v["gate"]["gave_up"] for v in views),
        "clock_deviation": _worst(v["clock_deviation"] for v in views),
        "infra_failed_fraction": sum(v["samples"]["infra_failed"] for v in views) / counted if counted > 0 else math.nan,
        "arm_failed_fraction": sum(v["samples"]["arm_failed"] for v in views) / counted if counted > 0 else math.nan,
        "drift": _med([abs(r["drift"]) for r in cells if not r["arm"].endswith("-b") and r["drift"] == r["drift"]]),
    }


def passes(runs, data, noise):
    """{id: (status, detail)} for the checks that are met or not; the status is `ok` when met and `note` when not."""
    views = noise["views"]
    out = {}

    def put(cid, met, detail):
        out[cid] = ("ok" if met else "note", detail)

    short = [f"run {i + 1} ({r['run'].get('rounds')})" for i, r in enumerate(runs) if (r["run"].get("rounds") or 0) < MIN_ROUNDS]
    put("rounds", not short, f"fewer than {MIN_ROUNDS} measured rounds: {', '.join(short)}" if short else f"{', '.join(str(r['run'].get('rounds')) for r in runs)} measured rounds")
    arms = {s["arm"] for r in runs for s in r["samples"]}
    base = {a for a in arms if not a.endswith("-b")}
    missing = sorted(a for a in base if a + "-b" not in arms)
    put("aa_copies", not missing, f"no A/A copy of {', '.join(missing)}" if missing else "every arm has its copy")
    prov = [f"run {i + 1}" for i, r in enumerate(runs) if not r["hardware"].get("quiet_dedicated")]
    put("hardware", not prov, f"{', '.join(prov)} not on quiet dedicated hardware: {'; '.join(x for r in runs for x in r['hardware'].get('reasons', [])[:2])[:300]}" if prov else "quiet dedicated hardware")
    viol = [v for r in runs for v in r["egress"].get("violations", [])]
    put("egress", not viol, f"{len(viol)} samples connected outside the loopback" if viol else "no connection outside the loopback")
    bad = [f"run {i + 1}" for i, r in enumerate(runs) if not r.get("ok")]
    put("integrity", not bad, f"{', '.join(bad)}: the run is not ok (an executable changed, an egress violation, or the run was refused)" if bad else "every executable and install tree unchanged")
    uncal = [f"run {i + 1}" for i, r in enumerate(runs) if not (r.get("calibration") or {}).get("passed")]
    put("calibration_ran", not uncal, f"{', '.join(uncal)}: no calibration, or it failed its CV gate" if uncal else "calibration passed in every run")
    miss = sum(v["samples"]["ok"] - v["samples"]["with_telemetry"] for v in views)
    put("telemetry", miss == 0 and sum(v["samples"]["ok"] for v in views) > 0, f"{miss} ok samples have no telemetry" if miss else "every ok sample has telemetry")
    limited = sorted({n for v in views for n in v["cpu_quota_limited"]})
    put("cpu_quota", not limited, f"cpu.max is set on {', '.join(limited)}: the sample could be throttled by the envelope" if limited else "no ancestor of the arm cgroup has a CPU quota")
    scaling = [f"run {i + 1}" for i, v in enumerate(views) if v["fixed_clock"] is False]
    put("clock_policy", not scaling, f"{', '.join(scaling)}: a pinned CPU scales its clock with load" if scaling else "the pinned CPUs have a fixed clock policy (or the machine does not say)")
    cp = aalib.reference_changepoint(data)
    if cp["changepoint"]:
        c = cp["changepoint"]
        out["reference_changepoint"] = (cp["status"], f"the reference's per-round index shifts by {c['shift']:+.1%} from round {cp['round']} (p {c['p']:.3f}); its A/A floor is {(cp['floor'] or 0):.1%}")
    else:
        out["reference_changepoint"] = ("ok", f"no change point in {cp['rounds']} rounds" if cp["tested"] else "too few rounds (or no scored cell) to test for a change point")
    return out


def worst_cells(data, noise, key, n=3):
    """The cells behind a threshold check, for the detail text."""
    if key in ("aa_gap_max", "aa_gap_median", "aa_significant_fraction"):
        rows = sorted(aalib.gaps(data), key=lambda r: -r[0])
        return [f"{c.scenario} {cellmath_api(c.api)} {c.metric} {arm}: {g:.1%}" for g, c, arm in rows[:n]]
    if key in ("aa_floor_max", "aa_floor_median"):
        rows = [(math.expm1(f), c) for c in data["cells"] for arm, (f, _) in c.aa.items() if f is not None]
        rows.sort(key=lambda r: -r[0])
        return [f"{c.scenario} {cellmath_api(c.api)} {c.metric}: {x:.1%}" for x, c in rows[:n]]
    if key in ("aa_cv_cpu", "outlier_fraction", "drift"):
        col = "cv" if key == "aa_cv_cpu" else "drift" if key == "drift" else "outliers"
        rows = [r for r in noise["cells"] if r[col] == r[col]]
        rows.sort(key=lambda r: -abs(r[col]))
        return [f"{r['scenario']} {cellmath_api(r['api'])} {r['metric']} {r['arm']}: {abs(r[col]):.1%}" if col != "outliers" else f"{r['scenario']} {cellmath_api(r['api'])} {r['metric']} {r['arm']}: {r[col]}" for r in rows[:n]]
    return []


def cellmath_api(api):
    return {"openai-completions": "chat", "anthropic-messages": "anthropic", "openai-responses": "responses", None: "-"}.get(api, str(api))


def fmt(unit, v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:.1%}" if unit == "fraction" else f"{v:g}"


def assess(runs, facts, data, noise):
    """{"notes": n, "summary", "checks": [...], "thresholds_sha256"}: each check has id, title, kind, unit, value, usual, status (`ok` or `note`), meaning and a detail. Checks with a note come first."""
    vals = values(runs, data, noise)
    checks = []
    for cid, title, unit, usual, meaning in T.HEALTH:
        v = vals[cid]
        st = _status(v, usual)
        detail = "; ".join(worst_cells(data, noise, cid)) if st == "note" else ""
        if _missing(v) and cid in MISSING_IS_NOTE:
            st, detail = "note", "not measured (the machine or the run did not provide it)"
        elif _missing(v):
            detail = "no calibration ran" if cid == "calibration_cv" else "no data"
        checks.append({"id": cid, "title": title, "kind": "threshold", "unit": unit, "value": None if _missing(v) else v, "usual": usual, "status": st, "meaning": meaning, "detail": detail})
    pf = passes(runs, data, noise)
    for cid, title, meaning in T.CHECKS:
        st, detail = pf[cid]
        checks.append({"id": cid, "title": title, "kind": "pass", "unit": None, "value": st == "ok", "usual": None, "status": st, "meaning": meaning, "detail": detail})
    checks.sort(key=lambda c: c["status"] != "note")
    noted = [c for c in checks if c["status"] == "note"]
    return {"notes": len(noted), "summary": summary(noted), "checks": checks, "thresholds_sha256": T.SHA256}


def label(c):
    """A note in one short phrase: the check id and its value."""
    return f"{c['id']} {fmt(c['unit'], c['value'])}" if c["kind"] == "threshold" and c["value"] is not None else c["id"]


def summary(noted):
    """'3 notes: a 2.0%, b, c' or 'no notes'."""
    if not noted:
        return "no notes"
    return f"{len(noted)} note{'s' if len(noted) != 1 else ''}: " + ", ".join(label(c) for c in noted)


def usual_text(c):
    if c["kind"] == "pass":
        return "yes"
    return f"up to {fmt(c['unit'], c['usual'])}"


def describe(c):
    """A note as one plain line: the value, the usual range, what the check means, and the cells or samples behind it."""
    head = f"{label(c)} (usual range: {usual_text(c)})" if c["kind"] == "threshold" else c["id"]
    return f"{head}. {c['meaning']} {c['detail']}".rstrip()


def lines(health, prov_tag=""):
    """The report section. `prov_tag` is the PROVISIONAL label every heading of a report on shared hardware carries."""
    out = [f"## Run notes{prov_tag}", "", f"{health['summary'][0].upper() + health['summary'][1:]}. Run notes describe the conditions of the run. They do not grade it or change a number.", "",
           "| check | value | usual range | status | meaning |", "|---|---:|---:|---|---|"]
    for c in health["checks"]:
        value = fmt(c["unit"], c["value"]) if c["kind"] == "threshold" else ("yes" if c["value"] else "no")
        text = (c["meaning"] + (" " + c["detail"] if c["status"] == "note" and c["detail"] else "")).replace("|", "/")
        out.append(f"| {c['title']} | {value} | {usual_text(c)} | {c['status']} | {text[:600]} |")
    out += ["", "The usual ranges are published in docs/HEALTH.md and are the same for every run. The notes are recomputed from the raw data by `buffon verify`; they are not stored in raw.json.",
            "The A/A rows compare each harness with its own identical copy. A pair counts as different only when its gap is significant and also larger than 1%.", ""]
    return out


def badge(health):
    """One line for a report's header and the results index."""
    noted = [label(c) for c in health["checks"] if c["status"] == "note"]
    return f"**Run notes ({health['notes']})**: " + (", ".join(noted) if noted else "none")


def thresholds_markdown():
    """docs/HEALTH.md's tables, generated from thresholds.py."""
    out = ["| id | what is checked | usual range | what it means |", "|---|---|---:|---|"]
    for cid, title, unit, usual, meaning in T.HEALTH:
        out.append(f"| `{cid}` | {title} | up to {fmt(unit, usual)} | {meaning} |")
    out += ["", "| id | what is checked | what it means |", "|---|---|---|"]
    out += [f"| `{cid}` | {title} | {meaning} |" for cid, title, meaning in T.CHECKS]
    out += ["", "Flags on a sample:", "", "| flag | rule |", "|---|---|"] + [f"| `{k}` | {v} |" for k, v in T.FLAGS.items()]
    out += ["", f"Outliers: {T.OUTLIER_RULE}", "", f"Change point: one test on the reference arm's per-round index, alpha {T.CP_ALPHA}, segments of at least {T.CP_MIN_SEGMENT} rounds, {T.CP_PERMUTATIONS} permutations.",
            "", f"A/A pairs: a pair counts as different when its paired p is below 0.05 and its gap is larger than {T.AA_MIN_GAP:.0%}."]
    return "\n".join(out) + "\n"
