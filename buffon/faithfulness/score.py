# SPDX-License-Identifier: Apache-2.0
"""Comparing observations and scoring. Deterministic and graded (grading.py): a probe is identical when the harness's normalised observation equals the reference's, else a per-family
comparator decides equivalent-presentation (0.9), equivalent-semantics (0.6) or behaviour-differs (0.0). No model, no threshold, no fuzzy matching."""
import fnmatch
import hashlib
import os
import tomllib

from . import canon, grading
from .probes import DIMENSIONS

INTENTIONAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intentional.toml")
NA_PREFIX = "it does not speak "


def digest(obs):
    return hashlib.sha256(canon.canonical(obs).encode()).hexdigest()[:16]


def load_intentional(path=INTENTIONAL_FILE):
    """[{arms, probes, divergence, note}]: PiG's recorded divergences (D-records) that explain a mismatch. They are listed beside the score; they never raise it."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        return tomllib.load(f).get("intentional", [])


def intentional_for(rules, arm_id, probe_id):
    for r in rules:
        if any(fnmatch.fnmatch(arm_id, a) for a in r.get("arms", ["*"])) and any(fnmatch.fnmatch(probe_id, p) for p in r["probes"]):
            return r["divergence"]
    return None


def classify(result, ref_result, ref_ok=None, probe_id=""):
    """'match' | 'presentation' | 'semantics' | 'mismatch' | 'na' | 'invalid' for one probe on one arm against the reference's result for the same probe; 'mismatch' is behaviour-differs."""
    if ref_result["status"] != "ok" or (ref_ok is not None and not ref_ok(ref_result["obs"])):
        return "invalid"
    if result["status"] == "na":
        return "na"
    if result["status"] == "skip" and result.get("reason", "").startswith(NA_PREFIX):
        return "na"
    if result["status"] != "ok":
        return "mismatch"
    if result["hash"] == ref_result["hash"]:
        return grading.IDENTICAL
    return grading.grade(probe_id, result.get("obs"), ref_result.get("obs"))


def score_arm(probes, results, ref_results, unstable=(), rules=(), arm_id=""):
    """Per-dimension counts and percentages and the weighted overall score for one arm. Unstable probes (the reference disagreed with its own A/A copy) are left out of everyone's score."""
    dims = {d: {"name": name, "weight": w, "match": 0, "presentation": 0, "semantics": 0, "mismatch": 0, "na": 0, "invalid": 0, "unstable": 0, "intentional": 0} for d, (name, w) in DIMENSIONS.items()}
    rows, verdicts = [], {}
    for p in probes:
        d = dims[p.dim]
        if p.id in unstable:
            d["unstable"] += 1
            rows.append((p.id, "unstable", None))
            continue
        r = results.get(p.id, {"status": "error", "reason": "not run"})
        verdict = classify(r, ref_results[p.id], p.ref_ok, p.id)
        verdicts[p.id] = verdict
        d[verdict] += 1
        why = None
        if verdict in ("mismatch", "presentation", "semantics"):
            why = intentional_for(rules, arm_id, p.id)
            if why:
                d["intentional"] += 1
        rows.append((p.id, verdict, why))
    for d in dims.values():
        scored = d["match"] + d["presentation"] + d["semantics"] + d["mismatch"]
        d["scored"] = scored
        d["credit"] = sum(d[v] * grading.CREDIT[v] for v in grading.CREDIT)
        d["pct"] = 100.0 * d["credit"] / scored if scored else None
    live = [d for d in dims.values() if d["pct"] is not None and d["weight"] > 0]
    total = sum(d["weight"] for d in live)
    overall = sum(d["weight"] * d["pct"] for d in live) / total if total else None
    return {"dimensions": dims, "overall": overall, "weights_used": {k: v["weight"] for k, v in dims.items() if v["pct"] is not None and v["weight"] > 0}, "rows": rows,
            "correctness_failures": grading.correctness_failures(probes, results, ref_results, verdicts)}
