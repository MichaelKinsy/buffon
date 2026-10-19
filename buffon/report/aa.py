# SPDX-License-Identifier: Apache-2.0
"""What the A/A copies and the reference arm's own series say about the host (docs/HEALTH.md): their CV, how big the gap between an identical copy and its harness is, how often it looks different, and whether the reference
arm's per-round series has a change point. Pure functions of the report's cells; deterministic for a seed."""
import math
import random
import statistics

from .. import stats
from . import thresholds as T


def pairs(data):
    """[(cell, arm)] for every arm with an A/A copy that shares at least 3 rounds with it in a cell. A cell holds only measured samples that did not fail, so a scale rung that stopped (in one copy
    or both) is not in it, and a gap is computed over the rounds in which both copies completed (`stats.pair_by_round`)."""
    out = []
    for cell in data["cells"]:
        for arm in data["base"]:
            twin = arm + "-b"
            if arm in cell.values and twin in cell.values and len(set(cell.values[arm]) & set(cell.values[twin])) >= 3:
                out.append((cell, arm))
    return out


def cv_cpu(data):
    """The CV of each arm and of its A/A copy in every CPU-metric cell (metrics named cpu_*): a list, empty when there is none."""
    out = []
    for cell, arm in pairs(data):
        if cell.metric.startswith("cpu"):
            for a in (arm, arm + "-b"):
                v = stats.cv(list(cell.values[a].values()))
                if v == v:
                    out.append(v)
    return out


# -- a paired t-test on the log ratio of an A/A pair (cheap enough for every cell of a report) -------------------------------------------------


def _betacf(a, b, x):
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return h


def _betai(a, b, x):
    """The regularized incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_two_sided_p(t, df):
    """Two-sided p-value of Student's t with `df` degrees of freedom."""
    if df <= 0 or t != t:
        return math.nan
    if math.isinf(t):
        return 0.0
    return _betai(df / 2, 0.5, df / (df + t * t))


def paired_p(a, b):
    """Two-sided paired t-test p of the log ratios of two aligned lists (a copy against its arm); nan with fewer than 3 usable pairs; 1.0 when every ratio is exactly 1,
    0.0 when they all differ by the same nonzero amount."""
    d = [math.log(x / y) for x, y in zip(a, b) if x > 0 and y > 0]
    if len(d) < 3:
        return math.nan
    sd = statistics.stdev(d)
    mean = statistics.fmean(d)
    if sd == 0:
        return 1.0 if mean == 0 else 0.0
    return t_two_sided_p(mean / (sd / math.sqrt(len(d))), len(d) - 1)


def gap_of(copy, arm):
    """The gap between a harness and its own copy in one cell: |median(copy) / median(arm) - 1| over the rounds both ran, or nan when the arm's median is not above 0."""
    x, y = stats.pair_by_round(arm, copy)
    mx, my = statistics.median(x), statistics.median(y)
    return abs(my / mx - 1) if mx > 0 else math.nan


def gaps(data):
    """[(gap, cell, arm)] for every harness and its copy in every cell with at least 3 shared rounds; the gap is a fraction (0.02 is 2%)."""
    out = []
    for cell, arm in pairs(data):
        g = gap_of(cell.values[arm + "-b"], cell.values[arm])
        if g == g:
            out.append((g, cell, arm))
    return out


def significant(data, alpha=0.05, min_gap=None):
    """(A/A pairs whose copy differs from the arm at p < alpha before any correction AND by more than `min_gap`, pairs tested). With no real difference about alpha of them should.
    A gap of `min_gap` or less never counts: a systematic 0.3% on a near-deterministic counter is significant to a t-test and does not matter (workloads/health.toml, [aa])."""
    min_gap = T.AA_MIN_GAP if min_gap is None else min_gap
    n = hits = 0
    for cell, arm in pairs(data):
        x, y = stats.pair_by_round(cell.values[arm], cell.values[arm + "-b"])
        p = paired_p(y, x)
        if p == p:
            n += 1
            hits += p < alpha and gap_of(cell.values[arm + "-b"], cell.values[arm]) > min_gap
    return hits, n


# -- change point in the reference arm's series -------------------------------------------------------------------------------------------------


def reference_index(data):
    """[(round, index)]: for each round, the geometric mean over every scored cell of the reference arm's value divided by its median in that cell. A host that slows down or
    speeds up halfway through moves every cell, so the index moves; an arm-specific effect in one cell barely does."""
    ref = data["reference"]
    logs, by_round = {}, {}
    for cell in data["cells"]:
        vals = cell.values.get(ref)
        if not vals or len(vals) < 3:
            continue
        med = statistics.median(vals.values())
        if med <= 0:
            continue
        for r, v in vals.items():
            if v > 0:
                by_round.setdefault(r, []).append(math.log(v / med))
    for r, xs in by_round.items():
        logs[r] = math.exp(statistics.fmean(xs))
    return sorted(logs.items())


def _t(a, b):
    na, nb = len(a), len(b)
    va, vb = statistics.variance(a) if na > 1 else 0.0, statistics.variance(b) if nb > 1 else 0.0
    diff = statistics.fmean(b) - statistics.fmean(a)
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return 0.0 if diff == 0 else math.inf
    return abs(diff) / se


def best_split(xs, m):
    """(index, |t|) of the split of xs with the largest Welch t, each side at least m long."""
    best = (None, -1.0)
    for k in range(m, len(xs) - m + 1):
        t = _t(xs[:k], xs[k:])
        if t > best[1]:
            best = (k, t)
    return best


def changepoint(xs, alpha=None, m=None, permutations=None, seed=0):
    """The change point of a series, or None: the split with the largest Welch t, significant at `alpha` by a seeded permutation test of that maximum. Returns a dict with the
    split `index` (the first element of the second segment), `p`, and `shift` (the second segment's median over the first's, minus 1). None for a series shorter than 2*m."""
    alpha, m, permutations = T.CP_ALPHA if alpha is None else alpha, T.CP_MIN_SEGMENT if m is None else m, T.CP_PERMUTATIONS if permutations is None else permutations
    if len(xs) < 2 * m:
        return None
    k, t = best_split(xs, m)
    if k is None:
        return None
    rng = random.Random(seed)
    work = list(xs)
    hits = 0
    for _ in range(permutations):
        rng.shuffle(work)
        if best_split(work, m)[1] >= t - 1e-12:
            hits += 1
    p = (hits + 1) / (permutations + 1)
    if p > alpha:
        return None
    before, after = statistics.median(xs[:k]), statistics.median(xs[k:])
    return {"index": k, "p": p, "t": t, "shift": after / before - 1 if before else math.nan}


def reference_changepoint(data, seed=0):
    """The change-point check of the reference arm: {"tested": bool, "rounds": n, "changepoint": dict or None, "round": the round the second segment starts at, "floor": the median A/A
    floor of the reference as a fraction, "status": ok | note}. Any change point is a note; `floor` says how large the shift is against the reference's A/A floor."""
    series = reference_index(data)
    out = {"tested": False, "rounds": len(series), "changepoint": None, "round": None, "floor": None, "status": "ok"}
    if len(series) < 2 * T.CP_MIN_SEGMENT:
        return out
    out["tested"] = True
    cp = changepoint([v for _, v in series], seed=seed)
    ref = data["reference"]
    floors = [math.expm1(c.aa[ref][0]) for c in data["cells"] if ref in c.aa and c.aa[ref][0] is not None]
    out["floor"] = statistics.median(floors) if floors else None
    if cp:
        key = series[cp["index"]][0]
        out["changepoint"], out["round"] = cp, key[1] if isinstance(key, tuple) else key
        out["status"] = "note"
    return out
