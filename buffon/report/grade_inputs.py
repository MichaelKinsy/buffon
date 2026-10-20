# SPDX-License-Identifier: Apache-2.0
"""The grade-inputs document: everything the Pi Harness Score needs from one report, JSON-able, written into report.json (`grade_inputs`) so `buffon grade` recomputes a grade
without the run directories. The per-round values of the graded cells are kept so the bootstrap can resample rounds."""
import math

from . import cells as cellmath, grade as gradelib


def _num(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else x


def scenario_family(scenario, method=gradelib.METHOD):
    """The family whose rows name this scenario (by its scenario glob), or the special family of its prefix; None when the method does not grade it."""
    from fnmatch import fnmatchcase
    for fam in method["family"]:
        if any(fnmatchcase(scenario, row["scenario"]) for row in fam["metric"]):
            return fam["id"]
        if fam.get("special") and scenario.startswith(fam["special"] + "/"):
            return fam["id"]
    return None


def cost_line(info):
    parts = []
    if info.get("install_method"):
        parts.append(info["install_method"])
    fp = info.get("footprint") or {}
    if fp.get("bytes"):
        size = f"{fp['bytes'] / 1e6:.1f} MB" + (f" + {fp['runtime']} {fp['runtime_bytes'] / 1e6:.0f} MB" if fp.get("runtime") and fp.get("runtime_bytes") else "")
        parts.append(size)
    if info.get("platform"):
        parts.append(info["platform"])
    return "; ".join(parts)


def instruction_twin(metric):
    """The instruction metric that supersedes a CPU-time metric as the headline CPU cost, or None: cpu_ms -> instructions, X_cpu_ms_per_1k_tokens -> X_instructions_per_1k_tokens."""
    if metric == "cpu_ms":
        return "instructions"
    if metric.endswith("cpu_ms_per_1k_tokens"):
        return metric.replace("cpu_ms_per_1k_tokens", "instructions_per_1k_tokens")
    return None


def build(data, runs, health, prov, reasons, reliability=None, faithfulness=None, method=gradelib.METHOD, correctness=None):
    """The inputs document. `data` is cells.build's result, `runs` the raw run dicts, `reliability` reliability_verdicts(data), `faithfulness` {arm: overall score}."""
    ref = data["reference"]
    arms = {}
    for r in runs:
        for a, i in r["arms"].items():
            if a in data["base"] and a not in arms and isinstance(i, dict):
                arms[a] = {"label": i.get("label", a), "cost": cost_line(i), **{k: i[k] for k in ("relation", "claims") if k in i}}
    cells = []
    have = {(c.scenario, c.api, c.metric) for c in data["cells"] if ref in c.values}
    for c in data["cells"]:
        spec = gradelib.spec_of(c.scenario, c.metric, method)
        if spec is None or ref not in c.values:
            continue
        twin = instruction_twin(c.metric)
        if twin and (c.scenario, c.api, twin) in have and gradelib.spec_of(c.scenario, twin, method):
            continue   # the instruction cell is the headline CPU cost of this workload; CPU time stays in the report, not in the grade
        fam, kind, direction = spec
        comps = {a: {"ratio": _num(x.ratio), "ci": [_num(x.ci[0]), _num(x.ci[1])], "floor": _num(x.floor), "n": x.n} for a, x in c.comparisons.items() if not x.not_compared}
        skipped = {a: x.not_compared for a, x in c.comparisons.items() if x.not_compared}   # different work (arms' [[divergence]]): left out of the grade, for that arm only
        cells.append({"family": fam, "kind": kind, "direction": direction, "scenario": c.scenario, "api": c.api, "metric": c.metric, "arms": comps, **({"not_compared": skipped} if skipped else {}),
                      "values": {a: {f"{k[0]}:{k[1]}": v for k, v in c.values[a].items()} for a in data["base"] if a in c.values}})
    failures, skips = {}, {}
    # review: the reference is never gated, so a sample it fails too (a workload that does not run on this host) must not gate another entry (m4-smoke grow-n failed for both)
    ref_failed = {(s["scenario"], cellmath.variant(s)) for s in data["samples"] if "failure" in s and not s["warmup"] and ref in (s["arm"], s.get("twin_of"))}
    for s in data["samples"]:
        fam = scenario_family(s["scenario"], method)
        if fam is None or s["warmup"] or s["arm"] not in data["base"]:
            continue
        row = failures.setdefault(s["arm"], {}).setdefault(fam, [0, 0])
        row[1] += 1
        row[0] += "failure" in s and (s["arm"] == ref or (s["scenario"], cellmath.variant(s)) not in ref_failed)
    for r in runs:
        for k in r["skipped"]:
            fam = scenario_family(k["scenario"], method)
            if fam and k["arm"] in data["base"]:
                skips.setdefault(k["arm"], {}).setdefault(fam, []).append(k["reason"])
    rel = {}
    for (_fault, _api), by_arm in (reliability or {}).items():
        for a, (ok, _why) in by_arm.items():
            if a in data["base"]:
                row = rel.setdefault(a, [0, 0])
                row[0] += bool(ok)
                row[1] += 1
    return {"method_version": method["method"]["version"], "method_sha256": method["sha256"], "reference": ref, "provisional": prov, "reasons": reasons, "notes": health["notes"],
            "arms": arms, "cells": cells, "failures": failures, "skips": skips, "reliability": rel, "faithfulness": dict(faithfulness or {}), "correctness": {a: list(v) for a, v in (correctness or {}).items() if v}}


def correctness_failures(docs):
    """{arm: [probe ids]} of the faithfulness probes whose failure gates a performance family (later documents win)."""
    out = {}
    for doc in docs:
        for arm, sc in doc.get("scores", {}).items():
            out[arm] = list(sc.get("correctness_failures") or [])
    return out


def faithfulness_scores(docs):
    """{arm: overall} from faithfulness.json documents (later ones win); an arm with no applicable dimension has no score."""
    out = {}
    for doc in docs:
        for arm, sc in doc.get("scores", {}).items():
            if sc.get("overall") is not None:
                out[arm] = sc["overall"]
    return out
