# SPDX-License-Identifier: Apache-2.0
"""Report math: raw samples -> cells -> comparisons against the reference arm, with the A/A noise floor.

Nothing here reads a file or prints. Every function is deterministic for a seed. The rules (METHODOLOGY.md sections 6 and 7):

  * a cell is (scenario, variant, metric): the arms' per-round values, warm-up rounds and failed samples excluded. The variant is the wire API a sample names, else its environment (`env`)
    when that is not "native", else None: a sample of another environment never joins a cell of the native one (`variant`);
  * the comparison of an arm with the reference is paired by round (a round is a run directory's round: several runs pool as more rounds): the ratio of medians
    with a 95% bootstrap interval that resamples rounds, a sign-flip p-value, Holm across arms;
  * the A/A noise floor of a pair of copies is the largest deviation from 1 their own ratio-of-medians interval allows, on the log scale (a ratio of 2 and of 0.5 are the same
    distance from 1): max(|ln ratio|, ln upper, -ln lower). It is shown as a percentage, exp(floor) - 1. The floor used against the reference is the larger of the reference's own
    floor and the arm's own floor (an arm with no copy uses the reference's alone);
  * a difference inside the floor (|ln ratio| <= floor) is "no measurable difference", whatever the medians say; a difference outside it whose interval excludes 1 is a win or a loss
    (lower is better for every scored metric but `HIGHER_IS_BETTER`) only when the Holm-adjusted sign-flip p is also below 0.05; one outside the floor whose interval includes 1, or whose test does not
    support it, is "inconclusive"; without any floor nothing can be called equal and the verdict says so;
  * every cell also carries its minimum detectable effect at 80% power, from the reference's A/A pair;
  * where workloads/margins.toml declares a margin for the metric, the comparison also carries the equivalence test (TOST on the paired ratio, 90% interval inside the margin). It is a claim
    of its own: "no measurable difference" says the gap is inside the noise, "equivalent" says the gap is provably inside the declared margin.
"""
import math
from dataclasses import dataclass, field

from .. import stats
from ..stats import margins
from . import metrics as metricslib
from ..divergence import reason_for

IDENTITY = {"_run", "arm", "scenario", "api", "env", "round", "warmup", "t_utc", "failure", "series", "twin_of", "wall_s", "meter", "traceback", "terminal", "tty", "renderer"}
# Echoes of the workload's own parameters and counts: identical for every arm by construction, so they are not scored.
DESCRIPTORS = {"quiet_wait_ms", "host_load1", "host_runnable", "pinned_busy", "pinned_iowait", "pinned_steal", "cpuset_runnable", "throttled", "psi_cpu_some_avg10", "turns", "requests", "compactions", "soak_minutes", "think_ms", "stream_rate_tps", "history_bytes", "history_entries", "history_messages", "series_samples",
               "records_after_kill", "seconds_to_exit",
               # a durable sample's configuration and the facts of its fixture (docs/RAW-FORMAT.md, "durable"): echoes of the workload, identical for every arm by construction, or a count the runner derives, not a cost
               "fixture_bytes", "fixture_seed", "fixture_turns", "window_tokens", "measured_turns", "conversations", "stmts_replayed", "commits_replayed", "compaction_failures", "failed_requests", "failed_turns", "k", "commits_total", "kill_event_commit",
               # time inside the scripted provider: shown, so the benchmark's own work is visible, and not scored (docs/design/DURABLE.md 4.2)
               "model_ms_per_turn",
               # a swarm sample's context: what the container held before the agents and the cost of the launcher and the scripted model, not the harness's
               "mem_baseline_mib", "mem_ready_mib", "mock_cpu_ms", "launcher_cpu_ms", "runner_cpu_ms"}
HIGHER_IS_BETTER = ("turns_per_s",)   # every other scored metric is lower is better


def direction(metric):
    """`higher` for a metric where more is better (the turns a swarm finishes in a second), else `lower`."""
    return "higher" if metric in HIGHER_IS_BETTER else "lower"
SPECIAL_FAMILIES = ("soak", "reliability")
SPECIAL_SCENARIOS = ("durable/crash-",)   # one sample for each (order, kill point): a pass or fail grid of its own, not a cell (dashboard/durable.py)
LEVEL = 0.95


def scored(metric):
    """Cost metrics: times, memory, bytes, CPU (lower is better), what a sample put on the wire (metrics.WIRE_METRICS), what a durable runtime did per turn (metrics.COUNT_METRICS), and the swarm's turns per
    second (higher is better: `direction`)."""
    if metric in metricslib.WIRE_METRICS:   # before DESCRIPTORS: `requests` stays listed there because the cross-node gate (cluster/gate.go) mirrors that list and does not judge wire counts
        return True
    if metric in metricslib.COUNT_METRICS:
        return True
    if metric in DESCRIPTORS or metric.endswith(("_flat", "_median", "_spread", "_slope_per_h")):
        return False
    return (metric.endswith(("_ms", "_mib", "_bytes", "_instructions", "_cycles", "_ms_p50", "_ms_p95", "_ms_max")) or "_ms_per_" in metric or "_mib_per_" in metric or "_bytes_per_" in metric or metric.startswith("bytes_") or metric == "mem_per_conv_mib" or "_instructions_per_" in metric
            or metric.startswith("cpu_ms") or metric in ("instructions", "cycles") + HIGHER_IS_BETTER)


def family(scenario):
    return scenario.split("/", 1)[0]


def is_special(scenario):
    """True for a workload that has a driver and a table of its own and makes no cell: the soak and reliability families, and the durable crash grid."""
    return family(scenario) in SPECIAL_FAMILIES or scenario.startswith(SPECIAL_SCENARIOS)


def variant(sample):
    """The axis a cell is split by besides the workload: the wire API the sample names, else its environment when it is set and not "native" (a Miniflare or Cloudflare run of a durable
    workload), else None. A native sample keeps the cell key it always had, so a cell never mixes environments."""
    api = sample.get("api")
    if api:
        return api
    env = sample.get("env")
    return env if env and env != "native" else None


def per_round(samples, scenario, api, arm, metric):
    """{(run, round): value} for the measured (non-warm-up, non-failed) samples of one arm in one cell.

    A round is identified by its run as well as its number: round 3 of one run directory and round 3 of another are different rounds, so pooling several runs
    adds pairs instead of averaging unrelated samples into one. Within one run a round has one sample per arm; a repeat (never written by the runner) averages."""
    out = {}
    for s in samples:
        if s["arm"] == arm and s["scenario"] == scenario and variant(s) == api and not s["warmup"] and "failure" not in s:
            v = s.get(metric)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.setdefault((s.get("_run", 0), s["round"]), []).append(float(v))
    return {r: sum(v) / len(v) for r, v in out.items()}


def floor_of(a, b, seed=0):
    """(floor, detail) of an A/A pair: lists aligned by round; the floor is in natural-log units. None when the pair is too short or degenerate to estimate."""
    if len(a) < 3 or len(b) < 3 or not stats.median(b) or not stats.median(a):
        return None, None
    r = stats.paired_ratio_of_medians(a, b, seed=seed)
    lo, hi = r["ci"]
    if any(map(math.isnan, (lo, hi))) or not r["ratio"] or not math.isfinite(r["ratio"]) or lo <= 0 or not math.isfinite(hi):
        return None, r
    return max(abs(math.log(r["ratio"])), math.log(hi), -math.log(lo), 0.0), r


@dataclass
class Comparison:
    arm: str
    n: int
    arm_median: float
    ref_median: float
    ratio: float
    ci: tuple
    floor: float
    p: float = math.nan
    p_holm: float = math.nan
    verdict: str = ""
    note: str = ""
    equivalence: dict = None   # the TOST against the margin workloads/margins.toml declares for the metric: {margin, low, high, p, equivalent}, or None when it declares none
    not_compared: str = ""                              # the reason the arm does different work in this cell: no ratio, interval or test, only the medians (divergence.py)


@dataclass
class Cell:
    scenario: str
    api: str                                           # the cell's variant: the wire API, else the environment when it is not native (`variant`), else None
    metric: str
    values: dict = field(default_factory=dict)         # arm -> {round: value}
    comparisons: dict = field(default_factory=dict)    # arm -> Comparison (non-twin arms)
    steps: dict = field(default_factory=dict)          # arm -> Comparison of the arm against the arm its manifest names as `previous`, when both have values
    aa: dict = field(default_factory=dict)             # arm -> (floor, ratio dict) for each arm that has a copy
    mde: float = math.nan
    env: str = None                                    # the environment the samples of the cell ran in ("native", "miniflare", ...), None for a workload that names none


ALPHA = 0.05


def classify(ratio, ci, floor, p=None, higher=False):
    """Verdict for lower-is-better metrics. `floor` is the A/A floor in natural-log units, or None when no A/A pair exists. `p` is the comparison's sign-flip
    p-value (Holm-adjusted across arms when several arms are compared): a win or a loss needs the interval to exclude 1 AND p < ALPHA (METHODOLOGY.md section 7),
    so a percentile interval from a handful of rounds cannot call a difference the paired test does not support."""
    lo, hi = ci
    if any(map(math.isnan, (lo, hi))) or ratio is None:
        return "too few rounds"
    if floor is not None and ratio > 0 and math.isfinite(ratio) and abs(math.log(ratio)) <= floor:
        return "no measurable difference"
    side = "loss" if lo > 1 else "win" if hi < 1 else None
    if higher and side:   # more is better: a ratio above 1 is a win
        side = "win" if side == "loss" else "loss"
    if side and p is not None and not (p < ALPHA):
        return f"inconclusive (paired test p {p:.2g} >= {ALPHA})"
    if floor is None:
        return side or "inconclusive (no A/A floor)"
    return side or "inconclusive"


def build(raw_runs, reference=None, seed=0):
    """Cells for every scored metric of every sampled (non-special) scenario, from one or more raw.json dicts."""
    samples = [dict(s, _run=i) for i, raw in enumerate(raw_runs) for s in raw["samples"]]
    arms = sorted({s["arm"] for s in samples}, key=lambda a: (a.endswith("-b"), a))
    base = [a for a in arms if not a.endswith("-b")]
    twins = {a: a + "-b" for a in base if a + "-b" in arms}
    previous = previous_of(raw_runs)
    divergences = divergences_of(raw_runs)
    named = next((r for r in ((raw.get("run") or {}).get("reference") for raw in raw_runs) if r in base), None)   # the reference a run names (a family whose reference is not pi-node, durable's pi-durable)
    ref = reference if reference in base else (named or ("pi-node" if "pi-node" in base else (base[0] if base else None)))
    keys, envs = {}, {}
    for s in samples:
        if is_special(s["scenario"]) or "failure" in s or s["warmup"]:
            continue
        if s.get("env"):
            envs.setdefault((s["scenario"], variant(s)), set()).add(s["env"])
        for k, v in s.items():
            if k not in IDENTITY and scored(k) and isinstance(v, (int, float)) and not isinstance(v, bool):
                keys.setdefault((s["scenario"], variant(s), k), None)
    cells = []
    for scenario, api, metric in sorted(keys, key=lambda k: (k[0], k[1] or "", k[2])):
        cell = Cell(scenario, api, metric, env=",".join(sorted(envs.get((scenario, api), ()))) or None)
        for a in arms:
            vals = per_round(samples, scenario, api, a, metric)
            if vals:
                cell.values[a] = vals
        if ref in cell.values:
            for a, t in twins.items():
                if a in cell.values and t in cell.values:
                    x, y = stats.pair_by_round(cell.values[t], cell.values[a])
                    cell.aa[a] = floor_of(x, y, seed)
            if ref in cell.aa and cell.aa[ref][1] is not None:
                x, y = stats.pair_by_round(cell.values[ref + "-b"], cell.values[ref])
                cell.mde = stats.mde_ratio(x, y)
            compare(cell, ref, base, seed, previous, divergences)
        cells.append(cell)
    return {"samples": samples, "arms": arms, "base": base, "twins": twins, "reference": ref, "cells": cells, "previous": {a: o for a, o in previous.items() if a in base and o in base}, "caveats": caveats_of(raw_runs),
            "divergences": {a: d for a, d in divergences.items() if a in base}}


def make_comparison(cell, ref, a, seed):
    """The paired comparison of arm `a` against `ref` in one cell, or None when they share too few rounds. The floor is the larger of the two arms' A/A floors."""
    if a not in cell.values or ref not in cell.values:
        return None
    x, y = stats.pair_by_round(cell.values[a], cell.values[ref])
    if len(x) < 2 or not stats.median(y):
        return None
    draws = stats.bootstrap_ratios(x, y, seed=seed)
    r = stats.paired_ratio_of_medians(x, y, seed=seed, draws=draws)
    floors = [f for f in (cell.aa.get(ref, (None,))[0], cell.aa.get(a, (None,))[0]) if f is not None]
    floor = max(floors) if floors else None
    c = Comparison(arm=a, n=len(x), arm_median=stats.median(x), ref_median=stats.median(y), ratio=r["ratio"], ci=tuple(r["ci"]), floor=floor if floor is not None else math.nan)
    c.p = stats.sign_flip_p(x, y, seed=seed)
    c.verdict = classify(r["ratio"], c.ci, floor, c.p, higher=cell.metric in HIGHER_IS_BETTER)
    margin = margins.margin_for(cell.metric, c.ref_median)
    if margin is not None:
        c.equivalence = stats.tost_ratio(x, y, margin, seed=seed, draws=draws)
    if floor is None:
        c.note = "no A/A floor"
    return c


def previous_of(raw_runs):
    """{arm: previous arm id} from the arms' manifest facts: any arm may declare the earlier arm it replaces (`previous` in arm.toml), and the report shows the change between them."""
    out = {}
    for raw in raw_runs:
        for arm, info in (raw.get("arms") or {}).items():
            if isinstance(info, dict) and info.get("previous"):
                out[arm] = info["previous"]
    return out


def divergences_of(raw_runs):
    """{arm: [divergence tables]} from the arms' manifest facts (`[[divergence]]` in arm.toml): where an arm does different work by its own account. A run written before the
    field has none. A later run's entry for an arm replaces an earlier one's."""
    out = {}
    for raw in raw_runs:
        for arm, info in (raw.get("arms") or {}).items():
            if isinstance(info, dict) and info.get("divergences"):
                out[arm.removesuffix("-b")] = info["divergences"]
    return out


def not_compared_reason(divergences, ref, arm, scenario, metric):
    """Why `arm` is not compared with `ref` in this cell, or None. The arm's own divergence covers it; so does the reference's, since then the two do different work."""
    own = reason_for(divergences.get(arm), scenario, metric)
    if own:
        return own
    theirs = reason_for(divergences.get(ref), scenario, metric)
    return f"the reference {ref} does different work here: {theirs}" if theirs else None


def not_compared(cell, ref, a, reason):
    """The row of an arm that does different work in this cell: its own median and the reference's, and the reason; no ratio, interval, floor or test."""
    if a not in cell.values or ref not in cell.values:
        return None
    nan = math.nan
    return Comparison(arm=a, n=len(cell.values[a]), arm_median=stats.median(list(cell.values[a].values())), ref_median=stats.median(list(cell.values[ref].values())), ratio=nan, ci=(nan, nan), floor=nan,
                      verdict="not compared", note=reason, not_compared=reason)


def caveats_of(raw_runs):
    """{arm: caveat sentence} from the arms' manifest facts."""
    out = {}
    for raw in raw_runs:
        for arm, info in (raw.get("arms") or {}).items():
            if isinstance(info, dict) and info.get("caveat"):
                out[arm.removesuffix("-b")] = info["caveat"]
    return out


def compare(cell, ref, base, seed, previous=None, divergences=None):
    order = []
    for a in base:
        if a == ref:
            continue
        reason = not_compared_reason(divergences or {}, ref, a, cell.scenario, cell.metric)
        if reason:   # different work: shown, never compared, never in Holm's family
            c = not_compared(cell, ref, a, reason)
            if c:
                cell.comparisons[a] = c
            continue
        c = make_comparison(cell, ref, a, seed)
        if c:
            cell.comparisons[a] = c
            order.append(a)
    for a, adj in zip(order, stats.holm([cell.comparisons[a].p if cell.comparisons[a].p == cell.comparisons[a].p else 1.0 for a in order])):
        c = cell.comparisons[a]
        c.p_holm = adj
        c.verdict = classify(c.ratio, c.ci, None if c.floor != c.floor else c.floor, adj, higher=cell.metric in HIGHER_IS_BETTER)
    for new, old in (previous or {}).items():
        if old in base and new in base:
            step = make_comparison(cell, old, new, seed)
            if step:
                cell.steps[new] = step


def tally(cells, arm):
    """Counts of verdicts for one arm over cells, by family: {family: {verdict: n}}."""
    out = {}
    for c in cells:
        comp = c.comparisons.get(arm)
        if comp and not comp.not_compared:
            out.setdefault(family(c.scenario), {}).setdefault(comp.verdict if not comp.verdict.startswith("inconclusive") else "inconclusive", 0)
            fam = out[family(c.scenario)]
            key = comp.verdict if not comp.verdict.startswith("inconclusive") else "inconclusive"
            fam[key] += 1
    return out


def coverage(raw_runs, arm, cells):
    """(cells the arm has a value in, cells in the report): the denominator of the coverage column."""
    have = sum(1 for c in cells if arm in c.values)
    return have, len(cells)
