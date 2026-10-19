# SPDX-License-Identifier: Apache-2.0
"""The dashboard's data: everything the pages draw, taken from the run directories and the report `buffon report` writes from them.

Nothing here invents a number. Ratios, intervals, floors, p-values and verdicts are the report's (buffon/report/cells.py); the histogram of a ratio's
bootstrap draws comes from the very draws behind the report's 95% interval (buffon.stats.bootstrap_ratios, same seed), and build() checks that those draws
give back the report's interval exactly. The one thing the report does not print is the interval of a harness's own median (the grid's absolute values): it is
the percentile bootstrap of the median over that harness's measured rounds (buffon.stats.bootstrap_ci, same seed). The site makes no grade and no ranking."""
import json
import math
import os
import re

from .. import stats
from ..arms import manifest as manifestlib
from ..report import cellid as cellidlib, cells as cellmath, grade as gradelib, metrics as metricslib, render
from . import scale as scalelib

SEED = 20261011
HIST_BINS = 32
API_SHORT = {"openai-completions": "chat", "anthropic-messages": "anthropic", "openai-responses": "responses"}
KIND_LENS = {metricslib.CPU: "cpu", metricslib.WALL: "wall", metricslib.MEMORY: "memory", metricslib.SIZE: "size", "wire": "wire"}   # "wire": what the mock received (requests, request_bytes)
NOT_COMPARED = "different work: not compared"
WORD = {"loss": "more than Pi", "win": "less than Pi", "no measurable difference": "same as Pi, within noise", "inconclusive": "too close to call", "too few rounds": "too few rounds"}
MEMORY_KINDS = {"peak_rss_mib": "peak RSS", "rss_mib": "RSS", "ready_rss_mib": "RSS at ready", "pss_mib": "PSS", "ready_pss_mib": "PSS at ready", "peak_mem_mib": "cgroup peak memory"}
COLOURS = 8   # site.css defines --h1 to --h8; a ninth harness reuses a colour, and its name is always printed beside its marks


class ModelError(ValueError):
    pass


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


def finite(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def verdict_key(verdict):
    """'inconclusive (paired test p 0.2 >= 0.05)' -> 'inconclusive'."""
    return (verdict or "").split(" (")[0]


def ordered_rounds(values):
    """{(run, round): v} -> keys in run order: the order rounds were measured."""
    return sorted(values)


def histogram_of(draws, bins=HIST_BINS):
    """[(lo, hi, count)] over log-spaced bins from the 0.2nd to the 99.8th percentile of the draws; the few draws outside count in the end bins."""
    finite_draws = sorted(d for d in draws if d > 0 and math.isfinite(d))
    if not finite_draws:
        return []  # a cell with no positive finite draw (an arm that produced no data) has no histogram
    lo, hi = finite_draws[int(0.002 * (len(finite_draws) - 1))], finite_draws[int(math.ceil(0.998 * (len(finite_draws) - 1)))]
    if hi <= lo:
        lo, hi = lo / 1.001, hi * 1.001
    a, b = math.log(lo), math.log(hi)
    counts = [0] * bins
    for d in finite_draws:
        counts[min(bins - 1, max(0, int((math.log(d) - a) / (b - a) * bins)))] += 1
    return [(math.exp(a + (b - a) * i / bins), math.exp(a + (b - a) * (i + 1) / bins), c) for i, c in enumerate(counts)]


def equivalence_view(eq):
    """The report's equivalence test of one comparison ({margin, low, high, p, equivalent}), with a non-finite number as None; None where no margin is declared."""
    if not isinstance(eq, dict):
        return None
    return {k: (v if k == "equivalent" or finite(v) else None) for k, v in eq.items() if k in ("margin", "low", "high", "p", "equivalent")}


def comparison_view(cell, arm, comp, ref, seed):
    """One comparison of the report with everything its pages draw: the paired rounds and the histogram of the bootstrap draws.
    The comparison says whether the arm did different work (`not_compared`, a reason) and carries the equivalence test.
    A not-compared comparison keeps the arm's own median and has no ratio, interval, p-value or histogram."""
    keys = sorted(set(cell.values[arm]) & set(cell.values[ref]))
    x = [cell.values[arm][k] for k in keys]
    y = [cell.values[ref][k] for k in keys]
    floor = comp.floor if finite(comp.floor) else None
    out = {"arm": arm, "n": comp.n, "ratio": comp.ratio, "ci95": list(comp.ci), "floor_log": floor, "floor": math.expm1(floor) if floor is not None else None,
           "p": comp.p if finite(comp.p) else None, "p_holm": comp.p_holm if finite(comp.p_holm) else None, "verdict": verdict_key(comp.verdict), "verdict_text": comp.verdict,
           "arm_median": comp.arm_median, "ref_median": comp.ref_median, "rounds": [list(k) for k in keys], "x": x, "y": y}
    out["word"] = WORD.get(out["verdict"], out["verdict"])
    out["equivalence"] = equivalence_view(comp.equivalence)
    out["not_compared"] = comp.not_compared or None
    if out["not_compared"]:
        out.update({"ratio": None, "ci95": None, "floor_log": None, "floor": None, "p": None, "p_holm": None, "verdict": "not compared", "verdict_text": NOT_COMPARED, "word": NOT_COMPARED,
                    "hist": [], "resamples": 0, "aa": {}, "equivalence": None})
        return out
    if len(x) >= 2 and finite(comp.ratio) and all(finite(v) for v in comp.ci):
        draws = stats.bootstrap_ratios(x, y, seed=seed)
        if stats.percentile_interval(draws, 0.95) != list(comp.ci):
            raise ModelError(f"{cell.scenario} {cell.metric} {arm}: the bootstrap draws do not give back the report's 95% interval")
        out["hist"] = histogram_of(draws)
        out["resamples"] = len(draws)
    else:
        out["hist"] = []
        out["resamples"] = 0
    out["aa"] = {}
    for who in (ref, arm):
        f, detail = cell.aa.get(who, (None, None))
        if detail:
            out["aa"][who] = {"floor_log": f, "ratio": detail.get("ratio"), "ci": list(detail.get("ci") or [])}
    return out


def harness_list(data, raws, skipped):
    ref = data["reference"]
    order = [ref] + [a for a in data["base"] if a != ref]
    info = {}
    for raw in raws:
        for a, i in raw.get("arms", {}).items():
            if not a.startswith("_"):
                info.setdefault(a, {}).update(i)
    out = []
    for n, a in enumerate(order):
        i = info.get(a, {})
        out.append({"id": a, "name": i.get("label") or ("Pi" if a == ref else a), "slug": slugify(a), "is_ref": a == ref,
                    "colour": "pi" if a == ref else str((n - 1) % COLOURS + 1), "version": i.get("version"), "copy": data["twins"].get(a),
                    "cannot": cannot_run(a, skipped), "caveat": (data.get("caveats") or {}).get(a),
                    "pins": {k: v for k, v in i.items() if k not in ("label",) and isinstance(v, (str, int, float, bool)) and v is not None},
                    "command": command_of(a), "terms": i.get("operator_terms") if i.get("operator_terms_accepted") else None,
                    "runtime_settings": runtime_settings_of(i.get("runtime_settings")), "divergences": list(i.get("divergences") or [])})
    return out


def runtime_settings_of(rs):
    """{"env": {VAR: value}, "left_default": [VAR], "source": {VAR: "manifest"|"buffon"}} as the run recorded it (docs/RAW-FORMAT.md), or None when the run did not record it."""
    if not isinstance(rs, dict):
        return None
    return {"env": {str(k): str(v) for k, v in (rs.get("env") or {}).items()}, "left_default": [str(v) for v in rs.get("left_default") or []],
            "source": {str(k): str(v) for k, v in (rs.get("source") or {}).items()}}


def scope_of(arm, scenarios, ran, cannot):
    """Which workloads `arm` took part in and which it did not, with the reason the runner recorded (the manifest's cannot_run text). `scenarios` are the workloads of the grid in order;
    `ran` is the set of (scenario, arm) with a value. A swarm rung is not in the grid: it is listed, with its reason, only among those not measured, and the page adds the swarm
    ladders the harness did climb from the scale data (app.js scopeCard)."""
    reasons = {}
    for c in cannot:
        reasons.setdefault(c["scenario"], c["reason"])
    return {"measured": [s for s in scenarios if (s, arm) in ran],
            "not_measured": [{"scenario": s, "reason": reasons.get(s) or na_reason([], arm, s, None, False)} for s in scenarios if (s, arm) not in ran] +
                            [{"scenario": s, "reason": r} for s, r in reasons.items() if s not in scenarios]}


def command_of(arm_id):
    """{"bin", "modes": {mode: argv}, "homepage", "notes"} from the arm's manifest: the command line the measurement page shows, and the harness's own docs.
    None when the manifest is not in arms/."""
    try:
        spec = manifestlib.load_arm(arm_id).spec
    except (manifestlib.ManifestError, OSError, KeyError):
        return None
    path = (spec.get("npm") or {}).get("bin") or (spec.get("source") or {}).get("package") or \
        next((v.get("exe") for v in (spec.get("artifact") or {}).values() if isinstance(v, dict) and v.get("exe")), None) or arm_id
    return {"bin": os.path.basename(path), "modes": {k: list(v) for k, v in (spec.get("modes") or {}).items() if isinstance(v, list)}, "homepage": spec.get("homepage"), "notes": spec.get("notes")}


def run_view(path, raw, facts, notes):
    run_id = render.run_id_of(path)
    files = [name for name in ("raw.json", "facts.json", "host.json", "MANIFEST.sha256", "promotion.json", "health.json") if os.path.exists(os.path.join(path, name))]
    logs = os.path.isdir(os.path.join(path, "logs"))
    log_files = sorted(os.listdir(os.path.join(path, "logs"))) if logs else []
    return {"id": run_id, "path": path, "run": raw.get("run", {}), "site": raw.get("site", {}), "hardware": raw.get("hardware", {}), "runner": raw.get("runner", {}),
            "lock_sha256": raw.get("lock_sha256"), "calibration": {k: v for k, v in (raw.get("calibration") or {}).items() if k != "samples"}, "egress": raw.get("egress", {}),
            "arms": {a: i for a, i in raw.get("arms", {}).items() if not a.startswith("_")}, "facts": facts, "notes": notes, "files": files, "logs": logs, "log_files": log_files,
            "provisional": not (raw.get("hardware") or {}).get("quiet_dedicated"), "provisional_reasons": list((raw.get("hardware") or {}).get("reasons") or []),   # the run's own trust label: not on quiet dedicated hardware
            "synthetic": (raw.get("run") or {}).get("synthetic"), "samples": len(raw.get("samples", [])), "skipped": raw.get("skipped", []),
            "meters": sorted({s["meter"] for s in raw.get("samples", []) if s.get("meter")}), "perf_scopes": sorted({s["perf_scope"] for s in raw.get("samples", []) if s.get("perf_scope")})}


def cannot_run(arm, skipped):
    """[{scenario, api_short, reason}] the runner recorded for `arm`: the workloads it cannot run and why, in the order the runner wrote them."""
    out, seen = [], set()
    for s in skipped:
        if s.get("arm") != arm or not s.get("reason") or s["reason"].startswith("not reached"):   # a rung not reached is the end of a ladder, not a workload it cannot run
            continue
        key = (s.get("scenario"), s.get("api"), s["reason"])
        if key not in seen:
            seen.add(key)
            out.append({"scenario": s.get("scenario"), "api_short": API_SHORT.get(s.get("api"), s.get("api") or "-"), "reason": s["reason"]})
    return out


def na_reason(skipped, arm, scenario, api, has_other):
    """Why `arm` has no value in the cell (scenario, api, metric): the runner's recorded reason, else what the data shows."""
    for s in skipped:
        if s.get("arm") == arm and s.get("scenario") == scenario and s.get("api") in (None, api) and s.get("reason"):
            return s["reason"]
    return "it has no value for this measurement in this run" if has_other else "it was not run on this workload in this run"


def metric_key(scenario, metric):
    """The id of a metric in a URL: the workload and the metric's own name, whatever the wire API. `overhead/print` + `cpu_ms` -> `overhead-print.cpu_ms`."""
    return f"{slugify(scenario)}.{metric}"


def value_stats(values, seed):
    """{n, median, ci, q1, q3, min, max} of one harness's measured rounds. `ci` is the percentile bootstrap interval of the median, or None with fewer than two rounds."""
    ci = stats.bootstrap_ci(values, seed=seed)
    return {"n": len(values), "median": stats.median(values), "ci": list(ci) if all(finite(x) for x in ci) else None, "q1": stats.percentile(values, 25), "q3": stats.percentile(values, 75),
            "min": min(values), "max": max(values)}


def faults_of(raws, run_ids, ref, shown, skipped):
    """[{id, scenario, fault, api, api_short, run, ref_signature, arms: {arm: {ok, reasons, reps, signature}}, na: {arm: reason}}]: one entry for each fault and wire API that a run injected,
    with the verdict of each harness as the report states it (render.reliability_verdicts: the invariants held on every repetition and the outcome signature equals the reference's).
    A harness with no sample of the fault has the runner's recorded reason in `na`."""
    samples, run_of = [], {}
    for i, raw in enumerate(raws):
        for s in raw["samples"]:
            if s["scenario"].startswith("reliability/"):
                samples.append(s)
                run_of.setdefault((s["scenario"], s.get("api")), run_ids[i])
    if not samples:
        return []
    verdicts = render.reliability_verdicts({"samples": samples, "reference": ref})
    out = []
    for (scenario, api), by_arm in sorted(verdicts.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        group = [s for s in samples if s["scenario"] == scenario and s.get("api") == api]

        def facts(arm):
            mine = [s for s in group if s["arm"] == arm]
            sigs = {s.get("signature") for s in mine}
            return len(mine), (next(iter(sigs)) if len(sigs) == 1 else None)
        arms = {}
        for arm in shown:
            if arm in by_arm:
                ok, reasons = by_arm[arm]
                reps, sig = facts(arm)
                arms[arm] = {"ok": ok, "reasons": list(reasons), "reps": reps, "signature": sig}
        short = API_SHORT.get(api, api or "-")
        out.append({"id": slugify(f"{scenario}-{short}"), "scenario": scenario, "fault": scenario.split("/", 1)[1], "api": api, "api_short": short, "run": run_of[(scenario, api)],
                    "ref_signature": facts(ref)[1] if ref in by_arm else None, "arms": arms,
                    "na": {arm: na_reason(skipped, arm, scenario, api, False) for arm in shown if arm not in arms}})
    return out


def build(dirs, data_dir, reference=None, faithfulness=(), seed=SEED):
    """Render the report into `data_dir` (report.json and the CSVs the site links), then gather what the pages draw."""
    render.render(dirs, data_dir, reference, seed=seed, faithfulness=faithfulness)
    with open(os.path.join(data_dir, "report.json")) as f:
        report = json.load(f)
    raws, facts = render.load(dirs)
    data = cellmath.build([without_swarms(r) for r in raws], reference, seed)   # a swarm is not a cell of the grid: the Scale page draws it
    ref = data["reference"]
    if ref is None:
        raise ModelError("the run directories hold no measured samples")
    skipped = [s for raw in raws for s in raw.get("skipped", [])]
    harnesses = harness_list(data, raws, skipped)
    run_ids = [render.run_id_of(d) for d in dirs]
    ids = render.cell_ids(data, run_ids)
    runs = [run_view(d, raws[i], facts[i], render.health_of([d], reference, seed)) for i, d in enumerate(dirs)]
    shown = [h["id"] for h in harnesses]
    have = {(x.scenario, x.api, a) for x in data["cells"] for a, v in x.values.items() if v}   # which harness has any value in which workload and API
    cells = []
    for c in data["cells"]:
        kind, unit = metricslib.describe(c.metric)
        spec = gradelib.spec_of(c.scenario, c.metric)   # only to say which family text (docs/WHAT-WE-MEASURE.md) the workload belongs to
        cid = ids[(c.scenario, c.api, c.metric)]
        run_id = cellidlib.parse(cid)[0] if cid else run_ids[0]
        cell = {"id": cid, "slug": cell_slug(c), "key": metric_key(c.scenario, c.metric), "scenario": c.scenario, "workload": slugify(c.scenario),
                "api": c.api, "api_short": API_SHORT.get(c.api, c.api or "-"), "metric": c.metric, "kind": kind, "lens": KIND_LENS.get(kind, "other"), "unit": unit,
                "memory_kind": MEMORY_KINDS.get(c.metric) if kind == metricslib.MEMORY else None, "family": spec[0] if spec else "other",
                "mde": c.mde if finite(c.mde) else None, "run": run_id, "rerun": cellidlib.rerun_command(cid) if cid else "",
                "values": {a: [v[k] for k in ordered_rounds(v)] for a, v in c.values.items()},
                "stats": {a: value_stats([v[k] for k in ordered_rounds(v)], seed) for a, v in c.values.items() if a in shown and v},
                "na": {a: na_reason(skipped, a, c.scenario, c.api, (c.scenario, c.api, a) in have) for a in shown if not c.values.get(a)},
                "comparisons": {a: comparison_view(c, a, comp, ref, seed) for a, comp in c.comparisons.items()}}
        cells.append(cell)
    scenarios = list(dict.fromkeys(c["scenario"] for c in cells))
    ran = {(c["scenario"], a) for c in cells for a in c["stats"]}
    for h in harnesses:
        h["scope"] = scope_of(h["id"], scenarios, ran, h["cannot"])
    families = [{"id": f["id"], "title": f["title"]} for f in gradelib.METHOD["family"]]
    synthetic = [r["synthetic"] for r in runs if r["synthetic"]]
    scale = scalelib.build([(r["id"], raws[i]) for i, r in enumerate(runs)], skipped, shown)
    faults = faults_of(raws, run_ids, ref, shown, skipped)
    return {"reference": ref, "harnesses": harnesses, "cells": cells, "scale": scale, "faults": faults, "families": families, "runs": runs,
            "provisional": report.get("provisional"), "reasons": report.get("reasons") or [],
            "demo": synthetic[0] if synthetic else None, "seed": seed, "report": report}


def without_swarms(raw):
    """The run without its swarm samples (scenario scale/...): the grid's cells are single processes."""
    return dict(raw, samples=[s for s in raw["samples"] if not scalelib.SCENARIO.match(s.get("scenario") or "")])


def cell_slug(c):
    return slugify(f"{c.scenario}-{API_SHORT.get(c.api, c.api)}-{c.metric}")
