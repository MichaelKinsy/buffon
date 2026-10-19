# SPDX-License-Identifier: Apache-2.0
"""Round-paired comparisons: arms run in interleaved rounds, so round i of one arm is paired with round i of another.

Every function is seeded and deterministic. Resampling is by round, never by trial inside a round.
"""
import math
import random
import statistics


def cv(values):
    """Coefficient of variation (sample standard deviation over the mean); nan for fewer than 2 values or a zero mean."""
    if len(values) < 2:
        return math.nan
    mean = statistics.fmean(values)
    return statistics.stdev(values) / abs(mean) if mean else math.nan


def pair_by_round(a, b):
    """a and b map round -> value. The rounds both have, as two aligned lists."""
    rounds = sorted(set(a) & set(b))
    return [a[r] for r in rounds], [b[r] for r in rounds]


def _ratio(x, y):
    if y:
        return x / y
    return math.inf if x else None


def bootstrap_ratios(a, b, resamples=4000, seed=0):
    """The sorted bootstrap draws behind paired_ratio_of_medians: median(a) / median(b) over `resamples` resamples of the rounds, a pair moving together.
    A resample with no ratio (both medians 0) is left out; one whose b median alone is 0 is infinite."""
    rng = random.Random(seed)
    n = len(a)
    ratios = []
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        r = _ratio(statistics.median(a[i] for i in idx), statistics.median(b[i] for i in idx))
        if r is not None:
            ratios.append(r)
    ratios.sort()
    return ratios


def percentile_interval(draws, level=0.95):
    """The percentile interval of sorted draws at `level`: the same indices every interval in Buffon uses."""
    alpha = (1 - level) / 2
    return [draws[int(alpha * (len(draws) - 1))], draws[int(math.ceil((1 - alpha) * (len(draws) - 1)))]]


def paired_ratio_of_medians(a, b, level=0.95, resamples=4000, seed=0, draws=None):
    """median(a) / median(b) over rounds paired by position, with a percentile bootstrap interval that resamples rounds (a pair moves together).

    A resample whose b median is 0 has an infinite ratio when its a median is positive; a resample where both are 0 has no ratio and is left out.
    Needs at least two pairs; with fewer the interval is nan. `draws` are the sorted draws of bootstrap_ratios(a, b, resamples, seed), when the caller has them already."""
    if len(a) != len(b):
        raise ValueError("paired samples must have the same length")
    n = len(a)
    point = _ratio(statistics.median(a), statistics.median(b)) if n else None
    if n < 2:
        return {"ratio": point, "ci": [math.nan, math.nan], "n": n}
    ratios = bootstrap_ratios(a, b, resamples, seed) if draws is None else draws
    if not ratios:
        return {"ratio": point, "ci": [math.nan, math.nan], "n": n}
    return {"ratio": point, "ci": percentile_interval(ratios, level), "n": n}


def tost_ratio(a, b, margin, alpha=0.05, resamples=4000, seed=0, draws=None):
    """Equivalence of the paired ratio median(a) / median(b) within +/- margin (a fraction of b), by two one-sided tests on the log ratio at `alpha`.

    The rounds are paired and resampled together, as in paired_ratio_of_medians (`draws` are its sorted bootstrap draws, when the caller has them). Equivalence holds when the
    (1 - 2 alpha) percentile interval, 90% at alpha 0.05, lies inside log(1/(1+margin)) .. log(1+margin); the ratio's interval is the exponential of the log ratio's, so low and high are ratios.
    p is the larger of the two one-sided bootstrap p-values: the share of draws at or beyond a bound.
    A margin of 0 is exact: equivalent only when every pair is equal (p is then 0, otherwise 1). Needs at least two pairs and a non-zero median of b; otherwise None."""
    if len(a) != len(b):
        raise ValueError("paired samples must have the same length")
    if len(a) < 2 or not statistics.median(b):
        return None
    if draws is None:
        draws = bootstrap_ratios(a, b, resamples, seed)
    if not draws:
        return None
    low, high = percentile_interval(draws, 1 - 2 * alpha)
    if margin <= 0:
        same = all(x == y for x, y in zip(a, b))
        return {"margin": 0.0, "low": low, "high": high, "p": 0.0 if same else 1.0, "equivalent": same}
    upper, lower = 1 + margin, 1 / (1 + margin)
    p = max(sum(r <= lower for r in draws), sum(r >= upper for r in draws)) / len(draws)
    return {"margin": margin, "low": low, "high": high, "p": p, "equivalent": low > lower and high < upper}


def sign_flip_p(a, b, resamples=20000, seed=0):
    """Two-sided paired sign-flip test that the mean log ratio is zero (the statistic is the absolute sum of the log ratios). Exact for up to 16 pairs. Pairs with a non-positive value are left out."""
    diffs = [math.log(x / y) for x, y in zip(a, b) if x > 0 and y > 0]
    n = len(diffs)
    if n == 0:
        return math.nan
    observed = abs(sum(diffs))
    if n <= 16:
        hits = sum(abs(sum(d if mask >> i & 1 else -d for i, d in enumerate(diffs))) >= observed - 1e-12 for mask in range(1 << n))
        return hits / (1 << n)
    rng = random.Random(seed)
    hits = sum(abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= observed - 1e-12 for _ in range(resamples))
    return (hits + 1) / (resamples + 1)


def mde_ratio(aa_a, aa_b, alpha=0.05, power=0.8):
    """Minimum detectable ratio change at 80% power from an A/A pair: (z(1-alpha/2) + z(power)) * sd(log ratio) / sqrt(n), as a fraction (0.05 = 5%).

    nan when the pair has fewer than 3 usable rounds."""
    logs = [math.log(x / y) for x, y in zip(aa_a, aa_b) if x > 0 and y > 0]
    if len(logs) < 3:
        return math.nan
    z = statistics.NormalDist().inv_cdf
    return math.expm1((z(1 - alpha / 2) + z(power)) * statistics.stdev(logs) / math.sqrt(len(logs)))
