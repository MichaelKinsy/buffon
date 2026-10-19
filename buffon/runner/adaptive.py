# SPDX-License-Identifier: Apache-2.0
"""Adaptive stopping: a cell stops taking rounds once its answer is known (docs/METHODOLOGY.md section 18).

After each round, per (workload, API) variant, every arm is compared with the reference by the same paired statistics the report uses (buffon/report/cells.py): the ratio of medians
with a bootstrap interval over rounds, the A/A noise floor of the copies, and the sign-flip test. The variant is SETTLED when, for every arm that has data,

  * the verdict is a win or a loss (the interval excludes 1, the difference is outside the floor and the paired test supports it), or
  * the whole interval lies inside the noise floor: "no measurable difference", and it is tight enough to say so.

A variant takes at least `min_rounds(k)` rounds, k being the number of arms compared with the reference: the report corrects k p-values with Holm, so the smallest exact
sign-flip p of 2 / 2**n must still be below 0.05 after it is multiplied by k. No verdict, a tight "no measurable difference" included, settles a variant sooner.

A settled variant leaves the round loop; the others go on, up to the plan's `rounds`. Measured samples stay one at a time and interleaved. Nothing is discarded: the
rounds taken stay in the raw data, and `raw.json` records when and why each variant stopped, and the minimum it had to reach. The 12-round minimum applies to the Verified
badge only (buffon/trust.py).
"""
import math

from .. import stats
from ..report import cells as cellmath

ALPHA = cellmath.ALPHA
RESAMPLES = 400       # a stopping check is cheap; the report recomputes the interval with its own 4000


def min_rounds(compared=1, alpha=ALPHA):
    """The fewest rounds with which Holm across `compared` arms can still reach p < alpha: the smallest n with compared * 2 / 2**n < alpha.
    The smallest p an exact two-sided sign-flip test over n pairs gives is 2 / 2**n, and Holm multiplies the smallest p by the number of arms. One arm needs 6, two need 7, eight need 9."""
    n = 1
    while max(compared, 1) * 2 / 2 ** n >= alpha:
        n += 1
    return n


MIN_ROUNDS = min_rounds(1)   # 6: the smallest n for which one arm's exact sign-flip test can reach p < 0.05 (2 / 2**6)


def metric_of(samples):
    """The metric the stopping rule watches in one variant: instructions when recorded, else CPU time, else the first scored metric; None when there is none."""
    keys = {k for s in samples if "failure" not in s for k, v in s.items() if k not in cellmath.IDENTITY and cellmath.scored(k) and isinstance(v, (int, float)) and not isinstance(v, bool)}
    for name in ("instructions", "cpu_ms"):
        if name in keys:
            return name
    return sorted(keys)[0] if keys else None


def _floor(a, b):
    if len(a) < 3 or len(b) < 3 or not stats.median(a) or not stats.median(b):
        return None
    r = stats.paired_ratio_of_medians(a, b, resamples=RESAMPLES)
    lo, hi = r["ci"]
    if any(map(math.isnan, (lo, hi))) or not r["ratio"] or not math.isfinite(r["ratio"]) or lo <= 0 or not math.isfinite(hi):
        return None
    return max(abs(math.log(r["ratio"])), math.log(hi), -math.log(lo), 0.0)


def judge(values, ref, arm, minimum=MIN_ROUNDS):
    """(settled, verdict) of one arm against the reference from per-round values {arm: {round: value}}. Nothing is settled before `minimum` paired rounds."""
    if ref not in values or arm not in values:
        return True, "no data"
    x, y = stats.pair_by_round(values[arm], values[ref])
    if len(x) < minimum or not stats.median(y):
        return False, "too few rounds"
    floors = [f for f in (_floor(*stats.pair_by_round(values[t], values[a])) for a in (ref, arm) for t in (a + "-b",) if t in values) if f is not None]
    floor = max(floors) if floors else None
    r = stats.paired_ratio_of_medians(x, y, resamples=RESAMPLES)
    lo, hi = r["ci"]
    if any(map(math.isnan, (lo, hi))) or not r["ratio"] or not math.isfinite(r["ratio"]):
        return False, "too few rounds"
    p = stats.sign_flip_p(x, y)
    verdict = cellmath.classify(r["ratio"], (lo, hi), floor, p)
    if verdict in ("win", "loss"):
        return True, verdict
    if floor is not None and lo > 0 and math.isfinite(hi) and abs(math.log(lo)) <= floor and abs(math.log(hi)) <= floor:
        return True, "no measurable difference"
    return False, verdict


def _variant_values(samples, scenario, api, arm_ids):
    """(metric, {arm: {round: value}}, base arms other than the copies) of one variant from the samples taken so far."""
    mine = [s for s in samples if s["scenario"] == scenario and s.get("api") == api]
    metric = metric_of(mine)
    values = {}
    if metric is not None:
        for a in arm_ids:
            v = cellmath.per_round(mine, scenario, api, a, metric)
            if v:
                values[a] = v
    return metric, values, [a for a in arm_ids if not a.endswith("-b")]


def variant_minimum(samples, scenario, api, reference, arm_ids):
    """The rounds this variant must take before it can settle: `min_rounds` of the arms that have data and are compared with the reference."""
    _, values, base = _variant_values(samples, scenario, api, arm_ids)
    return min_rounds(sum(1 for a in base if a != reference and a in values))


def variant_status(samples, scenario, api, reference, arm_ids):
    """(settled, {arm: verdict}, metric) for one variant from the samples taken so far (dicts of the raw.json sample form)."""
    metric, values, base = _variant_values(samples, scenario, api, arm_ids)
    if metric is None:
        return True, {}, None
    base = [a for a in base if a != reference]
    minimum = min_rounds(sum(1 for a in base if a in values))
    if reference not in values or not base:
        return len(next(iter(values.values()), {})) >= minimum, {}, metric   # nothing to compare with: the minimum is enough
    out, settled = {}, True
    for a in base:
        s, why = judge(values, reference, a, minimum)
        out[a] = why
        settled = settled and s
    return settled, out, metric
