# SPDX-License-Identifier: Apache-2.0
"""Observations in, a paired result out. An observation is {"case", "arm", "model", "run", "passed": bool|null, "error": str|null, and optional numeric telemetry
(tokens, cost_usd, wall_s) where null means unavailable}. A pair is (case, model, run) with both arms; a pair with a missing, duplicate or errored arm is BLOCKED, and any
blocked pair withholds the headline (Pi's packages/evals rule)."""
import json
import math

from ..stats import core
from .protocol import expected_runs


def ingest(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def sem_overlap(a, b):
    """Harbor's criterion for two repeated measurements: the mean +- SEM intervals overlap. Needs at least two values each; otherwise None (unknown, not overlap)."""
    def interval(values):
        n = len(values)
        if n < 2:
            return None
        mean = sum(values) / n
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
        return mean - sd / math.sqrt(n), mean + sd / math.sqrt(n)
    ia, ib = interval(a), interval(b)
    if ia is None or ib is None:
        return None
    return ia[0] <= ib[1] and ib[0] <= ia[1]


def paired_result(protocol, observations):
    """{"protocol_digest", "reference", "arm", "pairs", "blocked": [...], "headline": {...}|None, "unavailable": {...}}; one entry per non-reference arm in "results"."""
    protocol.validate()
    reference, others = protocol.arms[0], protocol.arms[1:]
    cells = {}
    for o in observations:
        cells.setdefault((o["case"], o["model"], o["run"]), {}).setdefault(o["arm"], []).append(o)
    expected = {(r["case"], r["model"], r["run"]) for r in expected_runs(protocol)}
    results = {}
    for arm in others:
        blocked, pairs = [], []
        for key in sorted(expected):
            got = cells.get(key, {})
            reason = None
            for name in (reference, arm):
                rows = got.get(name, [])
                if not rows:
                    reason = f"{name} has no observation"
                elif len(rows) > 1:
                    reason = f"{name} has {len(rows)} observations"
                elif rows[0].get("error") or rows[0].get("passed") is None:
                    reason = f"{name} errored: {rows[0].get('error') or 'no verdict'}"
                if reason:
                    break
            if reason:
                blocked.append({"case": key[0], "model": key[1], "run": key[2], "reason": reason})
            else:
                pairs.append((key, bool(got[reference][0]["passed"]), bool(got[arm][0]["passed"])))
        unavailable = {}
        for metric in ("tokens", "cost_usd", "wall_s"):
            unavailable[metric] = sum(1 for o in observations if o["arm"] in (reference, arm) and o.get(metric) is None)
        headline = None
        if not blocked and pairs:
            both = sum(1 for _, r, a in pairs if r and a)
            only_ref = sum(1 for _, r, a in pairs if r and not a)
            only_arm = sum(1 for _, r, a in pairs if a and not r)
            n = len(pairs)
            ref_ok, arm_ok = both + only_ref, both + only_arm
            headline = {"pairs": n, "reference_pass": ref_ok, "arm_pass": arm_ok, "reference_rate": ref_ok / n, "arm_rate": arm_ok / n, "lift": (arm_ok - ref_ok) / n,
                        "only_reference": only_ref, "only_arm": only_arm, "mcnemar_p": core.mcnemar_exact(only_ref, only_arm),
                        "reference_ci": core.wilson(ref_ok, n), "arm_ci": core.wilson(arm_ok, n)}
        results[arm] = {"pairs": len(pairs), "blocked": blocked, "headline": headline, "unavailable": unavailable}
    return {"protocol_digest": protocol.digest(), "reference": reference, "results": results}
