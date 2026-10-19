# SPDX-License-Identifier: Apache-2.0
"""The Pi Harness Score (docs/GRADE.md, method in workloads/grade.toml): pure functions from a grade-inputs document to family scores, the overall score, its letter, its bootstrap
interval and its robustness across weight profiles.

Nothing here reads a run directory or prints. `inputs` is the JSON-able document `grade_inputs.build` writes into report.json, so `buffon grade --weights` recomputes a grade from
report.json alone. The rules (DESIGN-harness-grade, method version 1):

  * the reference arm scores `reference_score` (70) in every family it covers, by construction;
  * a family's cost ratio r_f is the weighted geometric mean of its cells' ratios of medians (arm / reference; reference / arm for a higher-is-better metric), a cell whose ratio is
    inside the A/A floor of the comparison counting as exactly 1; the family score is clamp(70 - 10 log2 r_f, 0, 100);
  * a family in which the entry's measured samples failed (more than `gate_max_failed_fraction`) scores 0: a fast wrong answer is a failure;
  * the overall score is the weighted mean of the family scores of the families the entry has a score in, rounded half up to an integer; NA-missing families score 0, NA-scope and
    not-run families are left out, and the entry gets no overall score when a family is not yet measurable or coverage is under the floor;
  * the interval is a bootstrap over rounds (shared draws across cells), the ranks are ranges that overlap when the intervals do.
"""
import hashlib
import math
import os
import random
import statistics
import tomllib
from fnmatch import fnmatchcase

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "workloads", "grade.toml")

NA_SCOPE, NA_MISSING, NA_UNMEASURABLE, NA_HELD, NOT_RUN = "NA-scope", "NA-missing", "NA-unmeasurable", "NA-held", "not-run"
CLASSES = (NA_SCOPE, NA_MISSING, NA_UNMEASURABLE, NA_HELD, NOT_RUN)
TABLES = ("pi-faithful", "not-pi-equivalent", "faithfulness-unmeasured", "no-score")


class GradeError(ValueError):
    pass


def load_method(path=PATH):
    with open(path, "rb") as f:
        raw = f.read()
    doc = tomllib.loads(raw.decode())
    doc["sha256"] = hashlib.sha256(raw).hexdigest()
    return doc


METHOD = load_method()


def family_ids(method=METHOD):
    return [f["id"] for f in method["family"]]


# -- weights --------------------------------------------------------------------------------------------------------------------------------

def check_weights(weights, method=METHOD):
    """The weights, validated: only the published families and kinds, each a finite non-negative number, at least one family and one kind positive."""
    fams, kinds = set(family_ids(method)), set(method["weights"]["default"]["kinds"])
    if not isinstance(weights, dict) or set(weights) - {"families", "kinds"}:
        raise GradeError("a weights file has only [families] and [kinds] tables: bands, gates and the family list are part of the method version")
    out = {"families": dict(method["weights"]["default"]["families"]), "kinds": dict(method["weights"]["default"]["kinds"])}
    for table, allowed in (("families", fams), ("kinds", kinds)):
        given = weights.get(table, {})
        if not isinstance(given, dict):
            raise GradeError(f"[{table}] must be a table")
        unknown = set(given) - allowed
        if unknown:
            raise GradeError(f"unknown {table}: {', '.join(sorted(unknown))}; the method has {', '.join(sorted(allowed))}")
        for k, v in given.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise GradeError(f"{table}.{k} = {v!r}: a weight is a finite number of at least 0")
            out[table][k] = v
    if not any(v > 0 for v in out["families"].values()) or not any(v > 0 for v in out["kinds"].values()):
        raise GradeError("at least one family and one kind need a positive weight")
    return out


def weights_for(profile="default", file_weights=None, method=METHOD):
    """The named published profile, overridden key by key by a weights file's tables."""
    if profile not in method["weights"]:
        raise GradeError(f"unknown profile {profile!r}; the method has {', '.join(method['weights'])}")
    if file_weights and set(file_weights) - {"families", "kinds"}:
        raise GradeError("a weights file has only [families] and [kinds] tables: bands, gates and the family list are part of the method version")
    base = method["weights"][profile]
    merged = {"families": dict(base["families"]), "kinds": dict(base["kinds"])}
    for table in ("families", "kinds"):
        merged[table].update((file_weights or {}).get(table, {}))
    return check_weights({"families": merged["families"], "kinds": merged["kinds"]}, method)


# -- score arithmetic -----------------------------------------------------------------------------------------------------------------------

def round_half_up(x):
    return int(math.floor(x + 0.5))


def letter(score, method=METHOD):
    """School band of a rounded score; + for the top `edge` points of a band and - for the bottom `edge` (F has neither)."""
    b = method["bands"]
    s = round_half_up(score)
    for name in ("A", "B", "C", "D"):
        lo = b[name]
        if s >= lo:
            hi = 100 if name == "A" else lo + 9
            if s >= hi - b["edge"] + 1:
                return name + "+"
            if s <= lo + b["edge"] - 1:
                return name + "-"
            return name
    return "F"


def score_of_ratio(r, method=METHOD):
    """clamp(70 - 10 log2 r, 0, 100): each halving of cost adds 10 points, each doubling takes 10."""
    m = method["method"]
    return min(100.0, max(0.0, m["reference_score"] - m["points_per_halving"] * math.log2(r)))


def is_tie(ratio, floor):
    """True when the ratio lies inside the A/A floor (natural-log units) of its comparison: no measurable difference."""
    return (floor is not None and isinstance(floor, (int, float)) and math.isfinite(floor) and isinstance(ratio, (int, float)) and math.isfinite(ratio) and ratio > 0
            and abs(math.log(ratio)) <= floor)


def cell_ratio(ratio, floor, direction="lower"):
    """The cost ratio a cell contributes: 1 inside the A/A floor, 1/ratio for a higher-is-better metric, None when the ratio is not a positive finite number."""
    if ratio is None or not isinstance(ratio, (int, float)) or not math.isfinite(ratio) or ratio <= 0:
        return None
    if is_tie(ratio, floor):
        return 1.0
    return 1.0 / ratio if direction == "higher" else ratio


def geomean(rs, ws):
    tw = sum(ws)
    if not rs or tw <= 0:
        return None
    return math.exp(sum(w * math.log(r) for r, w in zip(rs, ws)) / tw)


def spec_of(scenario, metric, method=METHOD):
    """(family id, kind, direction) of a cell, or None when the method does not score it."""
    for fam in method["family"]:
        for row in fam["metric"]:
            if fnmatchcase(scenario, row["scenario"]) and fnmatchcase(metric, row["metric"]):
                return fam["id"], row["kind"], row.get("direction", "lower")
    return None


# -- classification -------------------------------------------------------------------------------------------------------------------------

def classify_na(info, family, skips, method=METHOD):
    """(class, reason) for a family an entry has no score in, from its manifest facts and the run, never by hand at report time."""
    if info.get("held"):
        return NA_HELD, str(info["held"])
    fam = next(f for f in method["family"] if f["id"] == family)
    if "claims" not in info:   # the run's manifest facts carry no claims: grade with what there is, assume the arm claims what the family needs, and the grade lists the gap (missing_facts)
        info = dict(info, claims=list(fam["needs"]))
    missing = [n for n in fam["needs"] if n not in info["claims"]]
    cl = method["claims"]
    if missing:
        core = [n for n in missing if n in cl["core"]]
        if core and info.get("relation") in cl["pi_harness_relations"]:
            return NA_MISSING, f"a {info['relation']} harness without {', '.join(core)}: a core Pi capability cannot be declared out of scope"
        return NA_SCOPE, f"does not claim {', '.join(missing)}"
    why = "; ".join(sorted(set(skips)))[:300] if skips else "Buffon produced no sample for it"
    return NA_UNMEASURABLE, f"claims {', '.join(fam['needs']) or 'the capabilities'} but Buffon could not drive it: {why}"


# -- one entry ------------------------------------------------------------------------------------------------------------------------------

def median_of(xs):
    return statistics.median(xs)


def replicate_ratio(cell, arm, ref, draw):
    """Ratio of medians of one cell over drawn (run, round) keys both arms have; None when the draw has none (the caller then keeps the published ratio)."""
    a, b = cell["values"].get(arm, {}), cell["values"].get(ref, {})
    xs, ys = [a[k] for k in draw if k in a and k in b], [b[k] for k in draw if k in a and k in b]
    if not xs:
        return None
    mb = median_of(ys)
    return median_of(xs) / mb if mb else None


def timed_family(inputs, arm, fam, weights, method, draw=None):
    """(r_f, cells used, ties, dropped) of an entry in a timed family, from the published ratios (or, with `draw`, from the resampled rounds)."""
    ref = inputs["reference"]
    rs, ws, ties, dropped, used = [], [], 0, 0, 0
    for c in inputs["cells"]:
        if c["family"] != fam:
            continue
        direction = c.get("direction", "lower")
        if arm == ref:
            if ref in c["values"] or c["arms"]:
                rs.append(1.0), ws.append(weights["kinds"].get(c["kind"], 0))
                used += 1
            continue
        comp = c["arms"].get(arm)
        if comp is None:   # no comparison, or the arm does different work here (`not_compared`): the cell is left out for it
            continue
        ratio = comp["ratio"]
        if draw is not None:
            ratio = replicate_ratio(c, arm, ref, draw) or ratio
        r = cell_ratio(ratio, comp.get("floor"), direction)
        used += 1
        if r is None:
            dropped += 1
            continue
        ties += is_tie(ratio, comp.get("floor"))
        rs.append(r), ws.append(weights["kinds"].get(c["kind"], 0))
    return geomean(rs, ws), used, ties, dropped


def reference_cells(inputs, fam, arm=None):
    """The reference's cells in a family; for `arm`, without the cells where the arm does different work (`not_compared`), so leaving them out does not count against its coverage."""
    ref = inputs["reference"]
    return sum(1 for c in inputs["cells"] if c["family"] == fam and (ref in c["values"] or c["arms"]) and arm not in c.get("not_compared", {}))


def reliability_ratio(inputs, arm):
    """(cost ratio, passed, total): reference pass fraction over the entry's (a higher-is-better metric); 0 passes is ratio None (score 0)."""
    rel = inputs.get("reliability", {})
    got, ref = rel.get(arm), rel.get(inputs["reference"])
    if not got or not got[1] or not ref or not ref[1]:
        return None, 0, 0
    frac, rfrac = got[0] / got[1], ref[0] / ref[1]
    return (rfrac / frac if frac > 0 and rfrac > 0 else None), got[0], got[1]


def family_result(inputs, arm, fam, weights, method=METHOD):
    """The status of one family for one entry: scored (with its score), or an N/A class with its reason."""
    ref = inputs["reference"]
    info = inputs["arms"].get(arm, {})
    m = method["method"]
    out = {"status": "scored", "score": None, "ratio": None, "cells": 0, "ref_cells": 0, "ties": 0, "dropped": 0, "gate": None, "reason": ""}
    fdef = next(f for f in method["family"] if f["id"] == fam)
    skips = inputs.get("skips", {}).get(arm, {}).get(fam, [])
    if fdef.get("special") == "reliability":
        if reliability_total(inputs, ref) == 0:
            return dict(out, status=NOT_RUN, reason="the reference has no fault results in this run")
        if inputs["reliability"][ref][0] == 0:   # review: with no reference pass there is no ratio; every entry scored 0 (an entry passing all 8 faults included)
            return dict(out, status=NOT_RUN, reason="the reference passed no fault scenario in this run: no ratio")
        r, passed, total = reliability_ratio(inputs, arm) if arm != ref else (1.0, *inputs["reliability"][ref])
        if total == 0:
            cls, why = classify_na(info, fam, skips, method)
            return dict(out, status=cls, reason=why)
        out.update(cells=total, ref_cells=reliability_total(inputs, ref), ratio=r, passed=passed)
        out["score"] = 0.0 if r is None else score_of_ratio(r, method)
        return out
    if not fdef["metric"]:
        return dict(out, status=NOT_RUN, reason="the method has no workload for this family yet")
    if reference_cells(inputs, fam) == 0:
        return dict(out, status=NOT_RUN, reason="the reference has no cells in this family in this run")
    ref_n = reference_cells(inputs, fam, arm)
    if ref_n == 0:
        return dict(out, status=NOT_RUN, reason="different work in every cell of this family (a declared divergence): not compared")
    out["ref_cells"] = ref_n
    wrong = inputs.get("correctness", {}).get(arm)
    if arm != ref and wrong and fam in method["gate"]["correctness_families"]:
        return dict(out, cells=timed_family(inputs, arm, fam, weights, method)[1], score=0.0, gate="correctness failure in the faithfulness probes: " + ", ".join(wrong[:4]) + (" ..." if len(wrong) > 4 else ""))
    failed, attempts = inputs.get("failures", {}).get(arm, {}).get(fam, [0, 0])
    if arm != ref and attempts and failed / attempts > m["gate_max_failed_fraction"]:
        return dict(out, score=0.0, gate=f"{failed} of {attempts} measured samples failed")
    r, used, ties, dropped = timed_family(inputs, arm, fam, weights, method)
    out.update(cells=used, ties=ties, dropped=dropped, ratio=r)
    usable = used - dropped   # review: a cell whose ratio is not a positive finite number is not in the family's score, so it does not count toward its share either
    if r is None or usable / ref_n < m["min_cell_fraction"]:
        cls, why = classify_na(info, fam, skips, method)
        if cls == NA_UNMEASURABLE and used:
            why = f"only {usable} of the reference's {ref_n} cells have a ratio: {why}"
        return dict(out, status=cls, score=None, reason=why)
    out["score"] = score_of_ratio(r, method)
    return out


def reliability_total(inputs, arm):
    return (inputs.get("reliability", {}).get(arm) or [0, 0])[1]


def caveats_of(fams, method=METHOD):
    """What a grade computed from partial data lacks, as sentences: families that could not be measured, coverage under the floor."""
    m = method["method"]
    covered = [f for f, r in fams.items() if r["status"] == "scored"]
    out = []
    unmeasurable = [f for f, r in fams.items() if r["status"] == NA_UNMEASURABLE]
    if unmeasurable:
        out.append("not yet measurable, left out of the mean: " + "; ".join(f"{f} ({fams[f]['reason']})" for f in unmeasurable))
    if len(covered) < m["coverage_floor"]:
        out.append(f"covers {len(covered)} of {len(fams)} families, under the floor of {m['coverage_floor']}: a partial grade")
    return out


def overall_of(fams, weights, method=METHOD, strict=False):
    """(exact overall or None, why not). `fams` is {family: family_result}. By default the grade is computed from what there is (caveats_of lists what is missing); strict keeps the
    old refusals: no score when a family is not measurable or coverage is under the floor."""
    m = method["method"]
    covered = [f for f, r in fams.items() if r["status"] == "scored"]
    if strict:
        unmeasurable = [f for f, r in fams.items() if r["status"] == NA_UNMEASURABLE]
        if unmeasurable:
            return None, "not yet measurable: " + "; ".join(f"{f} ({fams[f]['reason']})" for f in unmeasurable)
        if len(covered) < m["coverage_floor"]:
            return None, f"covers {len(covered)} of {len(fams)} families, under the floor of {m['coverage_floor']}"
    counted = [(f, r["score"]) for f, r in fams.items() if r["status"] == "scored" or r["status"] == NA_MISSING]
    if not counted:
        return None, "no family has a score yet: " + "; ".join(f"{f} ({r['reason']})" for f, r in fams.items() if r.get("reason"))[:300]
    tw = sum(weights["families"].get(f, 0) for f, _ in counted)
    if tw <= 0:
        return None, "every counted family has weight 0"
    return sum(weights["families"].get(f, 0) * (s if s is not None else 0.0) for f, s in counted) / tw, None


def settle(fams):
    """NA-missing families count as 0; the rest keep their status."""
    for r in fams.values():
        if r["status"] == NA_MISSING:
            r["score"] = 0.0
    return fams


def entry_families(inputs, arm, weights, method=METHOD):
    return settle({f: family_result(inputs, arm, f, weights, method) for f in family_ids(method)})


def coverage_text(fams):
    n = len(fams)
    cov = sum(1 for r in fams.values() if r["status"] == "scored")
    kinds = {"out of scope": NA_SCOPE, "missing": NA_MISSING, "not yet measurable": NA_UNMEASURABLE, "not run": NOT_RUN}
    extra = [f"{sum(1 for r in fams.values() if r['status'] == c)} {label}" for label, c in kinds.items() if any(r["status"] == c for r in fams.values())]
    return f"{cov}/{n}" + (f" ({', '.join(extra)})" if extra else "")


# -- the grade ------------------------------------------------------------------------------------------------------------------------------

def bootstrap(inputs, arm, fams, weights, method, rng, resamples, keys):
    """The (low, high) percentile interval of the overall score over resampled rounds; the statuses, gates, NA zeros and reliability stay as measured."""
    m = method["method"]
    timed = [f for f, r in fams.items() if r["status"] == "scored" and r["gate"] is None and "passed" not in r and r["cells"]]
    point = {f: r["score"] for f, r in fams.items()}
    counted = [f for f, r in fams.items() if r["status"] in ("scored", NA_MISSING)]
    tw = sum(weights["families"].get(f, 0) for f in counted)
    if not timed or not keys or tw <= 0:
        return None
    sums = []
    for _ in range(resamples):
        draw = rng.choices(keys, k=len(keys))
        total = 0.0
        for f in counted:
            s = point[f] or 0.0
            if f in timed:
                r = timed_family(inputs, arm, f, weights, method, draw)[0]
                s = score_of_ratio(r, method) if r else s
            total += weights["families"].get(f, 0) * s
        sums.append(total / tw)
    if not sums:
        return None
    sums.sort()
    a = (1 - m["level"]) / 2
    return sums[int(a * (len(sums) - 1))], sums[int(math.ceil((1 - a) * (len(sums) - 1)))]


def ref_keys(inputs):
    ref = inputs["reference"]
    return sorted({k for c in inputs["cells"] for k in c["values"].get(ref, {})})


def table_of(entry, method=METHOD):
    if entry["overall"] is None:
        return "no-score"
    f = entry["faithfulness"]
    if f is None:
        return "faithfulness-unmeasured"
    return "pi-faithful" if f >= method["method"]["faithfulness_floor"] else "not-pi-equivalent"


def rank_ranges(entries, key_lo, key_hi, key_score):
    """{entry: (best rank, worst rank)} among `entries`: an entry outranks another only when its interval lies entirely above."""
    out = {}
    for e in entries:
        above = sum(1 for o in entries if o is not e and key_lo(o) > key_hi(e))
        below = sum(1 for o in entries if o is not e and key_hi(o) < key_lo(e))
        out[e["entry"]] = (1 + above, len(entries) - below)
    return out


def competition_rank(entries, score):
    return {e["entry"]: 1 + sum(1 for o in entries if score(o) > score(e)) for e in entries}


def faithfulness_of(inputs, arm):
    if arm == inputs["reference"]:   # review: a manifest's relation is self-declared; another arm (pi-bun included) has the score its faithfulness run measured
        return 100.0
    return (inputs.get("faithfulness") or {}).get(arm)


def missing_facts(inputs):
    """What the inputs lack that the grade would like to have, as sentences (the grade carries them; with strict=True the first two refuse)."""
    out = []
    ref = inputs.get("reference")
    if ref not in inputs.get("arms", {}):
        out.append(f"the reference arm's manifest facts ({ref}): its claims are assumed to be the families' needs")
    for a, info in inputs.get("arms", {}).items():
        if "claims" not in info:
            out.append(f"manifest claims of {a} (a run from before method version 1): it is assumed to claim what each family needs")
    return out


def grade(inputs, weights=None, method=METHOD, seed=20261011, resamples=None, profile="default", strict=False):
    """The grade of every entry of `inputs`: {"method", "weights", "entries": [...], "tables": {...}, "provisional"...}. Deterministic for a seed.

    The grade is computed from what the inputs have and lists what they lack (`missing`, each entry's `caveats`), and carries the run's trust badge. strict=True refuses instead: a missing
    reference manifest, a family that cannot be measured, thin coverage."""
    inputs0 = inputs
    if inputs.get("reference") not in inputs.get("arms", {}):
        if strict:
            raise GradeError("the grade needs the reference arm's manifest facts in the inputs")
        inputs = dict(inputs, arms=dict(inputs.get("arms", {}), **{inputs.get("reference", "reference"): {"label": inputs.get("reference", "reference")}}))
    if "method_sha256" in inputs and inputs["method_sha256"] != method["sha256"]:   # review: the inputs' cells were chosen by the method that wrote them; grading them with another would print its hash on them
        raise GradeError(f"the inputs were written by method version {inputs.get('method_version')} (grade.toml sha256 {str(inputs['method_sha256'])[:12]}), this is version "
                         f"{method['method']['version']} ({method['sha256'][:12]}): run `buffon report` again with this method")
    weights = weights or weights_for(profile, None, method)
    resamples = method["method"]["resamples"] if resamples is None else resamples
    keys = ref_keys(inputs)
    entries = []
    for arm in sorted(inputs["arms"], key=lambda a: (a != inputs["reference"], a)):
        info = inputs["arms"][arm]
        fams = entry_families(inputs, arm, weights, method)
        exact, why = overall_of(fams, weights, method, strict)
        e = {"caveats": caveats_of(fams, method) if exact is not None else [], "entry": arm, "label": info.get("label", arm), "relation": info.get("relation"), "cost": info.get("cost", ""), "families": fams, "coverage": coverage_text(fams),
             "covered": sum(1 for r in fams.values() if r["status"] == "scored"), "overall_exact": exact, "overall": None if exact is None else round_half_up(exact),
             "letter": None if exact is None else letter(exact, method), "no_score_reason": why, "faithfulness": faithfulness_of(inputs, arm), "ci": None}
        if exact is not None:
            ci = bootstrap(inputs, arm, fams, weights, method, random.Random(f"{seed}:{arm}"), resamples, keys)
            e["ci"] = [exact, exact] if ci is None else [min(ci[0], exact), max(ci[1], exact)]
        e["table"] = table_of(e, method)
        entries.append(e)
    prof = {}
    for name in method["weights"]:
        w = weights_for(name, None, method)
        for e in entries:
            fams = entry_families(inputs, e["entry"], w, method)
            x, _ = overall_of(fams, w, method, strict)
            prof.setdefault(e["entry"], {})[name] = x
    for table in TABLES[:3]:
        group = [e for e in entries if e["table"] == table]
        rr = rank_ranges(group, lambda o: o["ci"][0], lambda o: o["ci"][1], None) if group else {}
        cr = competition_rank(group, lambda o: o["overall_exact"])
        for e in group:
            e["rank"], e["rank_range"] = cr[e["entry"]], list(rr[e["entry"]])
            scores = {n: prof[e["entry"]][n] for n in prof[e["entry"]] if prof[e["entry"]][n] is not None}
            ranks = {}
            for n in scores:
                ranks[n] = 1 + sum(1 for o in group if prof[o["entry"]].get(n) is not None and prof[o["entry"]][n] > scores[n])
            e["profiles"] = {n: {"score": round_half_up(scores[n]), "rank": ranks[n]} for n in scores}
    for e in entries:
        e.setdefault("profiles", {})
        e.setdefault("rank", None)
        e.setdefault("rank_range", None)
    return {"method": {"version": method["method"]["version"], "sha256": method["sha256"]}, "weights": weights, "profile": profile, "reference": inputs["reference"], "entries": entries,
            "provisional": bool(inputs.get("provisional", True)), "reasons": inputs.get("reasons", []), "notes": inputs.get("notes"), "seed": seed, "resamples": resamples,
            "trust": inputs.get("trust"), "missing": missing_facts(inputs0), "strict": strict}
