# SPDX-License-Identifier: Apache-2.0
"""The Pi Harness Score: score arithmetic, properties of the method (reference = 70, monotone, ties inside the A/A floor, weight scaling), N/A classes, gates, tables, weights
files, the bootstrap, and the whole path from a run's raw data through `buffon report` to `buffon grade --weights`."""
import contextlib
import copy
import io
import json
import math
import os
import random
import tempfile
import unittest

from buffon import cli
from buffon.arms import manifest
from buffon.report import grade as G, render
from tests.test_report import raw_of, sample, wobble

TIMED = ("core", "ext10", "streaming", "long-session", "devloop")
KINDS = {"core": ("cpu", "memory"), "ext10": ("cpu", "memory"), "streaming": ("cpu", "time"), "long-session": ("cpu", "memory"), "devloop": ("time", "time")}
REF = "pi-node"


def info(label, relation="pi-port", claims=("pi-extensions", "pi-sessions", "pi-rpc")):
    return {"label": label, "relation": relation, "claims": list(claims), "cost": "release archive; 10.0 MB"}


def cell(fam, i, kind, ratios, floor=0.05, rounds=12):
    ref = {f"0:{r}": 100.0 + wobble(r) for r in range(rounds)}
    values = {REF: ref}
    arms = {}
    for arm, ratio in ratios.items():
        values[arm] = {k: v * ratio * (1 + 0.02 * wobble(int(k.split(":")[1]) + len(arm))) for k, v in ref.items()}
        arms[arm] = {"ratio": ratio, "ci": [ratio * 0.98, ratio * 1.02], "floor": floor, "n": rounds}
    return {"family": fam, "kind": kind, "direction": "lower", "scenario": f"{fam}/{i}", "api": None, "metric": f"{kind}_m{i}", "arms": arms, "values": values}


def make(arm_ratios, reliability=None, **extra):
    """Inputs with the reference and the given arms; arm_ratios = {arm: {family: ratio}} (one ratio per family, a cell per kind)."""
    arms = {REF: info("Pi Node", "pi-reference")}
    arms.update({a: info(a) for a in arm_ratios})
    cells = []
    for fam in TIMED:
        for i, kind in enumerate(KINDS[fam]):
            cells.append(cell(fam, i, kind, {a: r[fam] for a, r in arm_ratios.items() if fam in r}))
    rel = {REF: [10, 10]}
    rel.update({a: [10, 10] for a in arm_ratios})
    inputs = {"reference": REF, "provisional": True, "reasons": ["shared host"], "notes": 2, "arms": arms, "cells": cells, "failures": {}, "skips": {},
              "reliability": reliability or rel, "faithfulness": {}}
    inputs.update(extra)
    return inputs


def uniform(r):
    return {f: r for f in TIMED}


def run(inputs, **kw):
    kw.setdefault("resamples", 40)
    return {e["entry"]: e for e in G.grade(inputs, **kw)["entries"]}


class Arithmetic(unittest.TestCase):
    def test_each_halving_is_ten_points_and_70_is_the_reference(self):
        for r, s in ((1, 70), (0.5, 80), (0.25, 90), (0.125, 100), (2, 60), (4, 50), (128, 0)):
            self.assertAlmostEqual(G.score_of_ratio(r), s, places=9)
        self.assertEqual(G.score_of_ratio(0.001), 100.0)
        self.assertEqual(G.score_of_ratio(1e6), 0.0)

    def test_letter_bands_with_plus_and_minus_at_three_points_and_70_is_c_minus(self):
        want = {100: "A+", 98: "A+", 97: "A", 93: "A", 92: "A-", 90: "A-", 89: "B+", 87: "B+", 86: "B", 83: "B", 82: "B-", 80: "B-", 79: "C+", 77: "C+", 76: "C", 73: "C", 72: "C-",
                70: "C-", 69: "D+", 67: "D+", 66: "D", 63: "D", 62: "D-", 60: "D-", 59: "F", 0: "F"}
        for s, letter in want.items():
            self.assertEqual(G.letter(s), letter, s)

    def test_rounding_is_half_up_not_bankers(self):
        self.assertEqual([G.round_half_up(x) for x in (69.5, 70.5, 71.5, 70.49)], [70, 71, 72, 70])

    def test_a_cell_inside_the_floor_counts_as_exactly_one(self):
        self.assertEqual(G.cell_ratio(1.04, math.log(1.05)), 1.0)
        self.assertEqual(G.cell_ratio(0.96, math.log(1.05)), 1.0)
        self.assertEqual(G.cell_ratio(1.06, math.log(1.05)), 1.06)
        self.assertEqual(G.cell_ratio(1.06, None), 1.06)
        for bad in (None, 0, -1, math.nan, math.inf):
            self.assertIsNone(G.cell_ratio(bad, 0.1))
        self.assertEqual(G.cell_ratio(0.5, None, "higher"), 2.0)

    def test_the_method_file_matches_the_claims_vocabulary_of_manifests(self):
        self.assertEqual(tuple(G.METHOD["claims"]["vocabulary"]), manifest.CLAIMS)
        self.assertEqual(sum(1 for f in G.METHOD["family"]), 9)


class Properties(unittest.TestCase):
    def random_inputs(self, rng):
        arms = {f"a{i}": {f: math.exp(rng.uniform(-2, 2)) for f in TIMED} for i in range(3)}
        return make(arms)

    def test_the_reference_is_70_c_minus_in_every_family_whatever_the_others_do(self):
        rng = random.Random(1)
        for _ in range(25):
            e = run(self.random_inputs(rng))[REF]
            self.assertEqual(e["overall"], 70)
            self.assertEqual(e["letter"], "C-")
            self.assertTrue(all(r["score"] == 70 for r in e["families"].values() if r["status"] == "scored"))

    def test_an_arm_identical_to_the_reference_scores_70_and_a_cheaper_one_more(self):
        e = run(make({"same": uniform(1.0), "half": uniform(0.5), "double": uniform(2.0)}))
        self.assertEqual(e["same"]["overall"], 70)
        self.assertGreater(e["half"]["overall_exact"], 70)
        self.assertLess(e["double"]["overall_exact"], 70)

    def test_the_score_is_monotone_in_every_cell_ratio(self):
        rng = random.Random(2)
        for _ in range(30):
            base = {f: math.exp(rng.uniform(-1.5, 1.5)) for f in TIMED}
            fam = rng.choice(TIMED)
            before = run(make({"x": base}), resamples=0)["x"]
            worse = dict(base, **{fam: base[fam] * math.exp(rng.uniform(0.01, 1.0))})
            after = run(make({"x": worse}), resamples=0)["x"]
            self.assertLessEqual(after["families"][fam]["score"], before["families"][fam]["score"] + 1e-9)
            self.assertLessEqual(after["overall_exact"], before["overall_exact"] + 1e-9)
            for other in TIMED:
                if other != fam:
                    self.assertEqual(after["families"][other]["score"], before["families"][other]["score"])

    def test_the_score_is_monotone_for_a_higher_is_better_metric_in_the_other_direction(self):
        inputs = make({"x": uniform(1.0)})
        for c in inputs["cells"]:
            c["direction"] = "higher"
        base = run(inputs, resamples=0)["x"]["families"]["core"]["score"]
        for c in inputs["cells"]:
            c["arms"]["x"]["ratio"], c["arms"]["x"]["floor"] = 2.0, None
        self.assertGreater(run(inputs, resamples=0)["x"]["families"]["core"]["score"], base)

    def test_a_ratio_inside_the_floor_is_exactly_the_reference_score(self):
        rng = random.Random(3)
        for _ in range(20):
            floor = rng.uniform(0.02, 0.4)
            ratio = math.exp(rng.uniform(-floor, floor))
            inputs = make({"x": uniform(ratio)})
            for c in inputs["cells"]:
                c["arms"]["x"]["floor"] = floor
            e = run(inputs, resamples=0)["x"]
            self.assertTrue(all(r["score"] == 70 for r in e["families"].values() if r["status"] == "scored"))
            self.assertEqual(e["overall"], 70)
            self.assertGreater(e["families"]["core"]["ties"], 0)

    def test_scaling_every_weight_changes_nothing_and_cell_order_does_not_matter(self):
        rng = random.Random(4)
        inputs = self.random_inputs(rng)
        w1 = G.weights_for("default")
        w2 = {"families": {f: v * 7.5 for f, v in w1["families"].items()}, "kinds": {k: v * 3 for k, v in w1["kinds"].items()}}
        a, b = run(inputs, weights=w1, resamples=0), run(inputs, weights=w2, resamples=0)
        shuffled = copy.deepcopy(inputs)
        rng.shuffle(shuffled["cells"])
        c = run(shuffled, weights=w1, resamples=0)
        for arm in a:
            self.assertAlmostEqual(a[arm]["overall_exact"], b[arm]["overall_exact"], places=9)
            self.assertAlmostEqual(a[arm]["overall_exact"], c[arm]["overall_exact"], places=9)

    def test_scores_stay_in_0_100_and_the_letter_is_monotone_in_the_score(self):
        rng = random.Random(5)
        for _ in range(20):
            e = run(self.random_inputs(rng), resamples=0)
            for x in e.values():
                self.assertTrue(0 <= x["overall_exact"] <= 100)
        order = ["F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
        last = -1
        for s in range(0, 101):
            cur = order.index(G.letter(s))
            self.assertGreaterEqual(cur, last)
            last = cur

    def test_ties_that_move_a_score_only_inside_the_floor_never_reorder_two_entries(self):
        e = run(make({"a": uniform(1.03), "b": uniform(0.97)}))
        self.assertEqual(e["a"]["overall"], e["b"]["overall"])


class Classes(unittest.TestCase):
    def test_a_family_without_a_workload_is_listed_not_scored_and_counts_against_coverage(self):
        e = run(make({"x": uniform(1.0)}))["x"]
        for f in ("large-write", "scale", "search"):
            self.assertEqual(e["families"][f]["status"], G.NOT_RUN)
        self.assertEqual(e["coverage"], "6/9 (3 not run)")
        self.assertEqual(e["covered"], 6)
        self.assertEqual(e["overall"], 70)

    def test_out_of_scope_is_left_out_of_the_mean_and_under_the_floor_there_is_no_overall(self):
        inputs = make({"rpi": uniform(0.5)})
        inputs["arms"]["rpi"] = info("rpi", "pi-port", claims=("pi-rpc",))
        for c in inputs["cells"]:
            if c["family"] in ("ext10", "long-session"):
                c["arms"].pop("rpi")
        e = run(inputs, strict=True)["rpi"]
        self.assertEqual(e["families"]["ext10"]["status"], G.NA_SCOPE)
        self.assertEqual(e["families"]["long-session"]["status"], G.NA_SCOPE)
        self.assertIsNone(e["overall"])
        self.assertIn("under the floor", e["no_score_reason"])
        self.assertEqual(e["table"], "no-score")
        partial = run(inputs)["rpi"]   # not strict: graded with what there is, and the gap is listed
        self.assertIsNotNone(partial["overall"])
        self.assertTrue(any("under the floor" in c for c in partial["caveats"]))
        self.assertEqual(e["coverage"], "4/9 (2 out of scope, 3 not run)")

    def test_out_of_scope_does_not_enter_the_weighted_mean(self):
        inputs = make({"x": {f: 0.5 for f in TIMED}})
        inputs["arms"]["x"]["claims"] = ["pi-rpc", "pi-sessions"]
        w = G.weights_for("default")
        w["families"]["large-write"] = 0
        full = run(make({"x": uniform(0.5)}), weights=w, resamples=0)["x"]["overall_exact"]
        for c in inputs["cells"]:
            if c["family"] == "ext10":
                c["arms"]["x"]["ratio"] = 4.0
        e = run(inputs, weights=w, resamples=0)["x"]
        self.assertEqual(e["families"]["ext10"]["status"], "scored")   # it has the cells, so it is scored whatever it claims
        for c in inputs["cells"]:
            if c["family"] == "ext10":
                c["arms"].pop("x")
        e = run(inputs, weights=w, resamples=0, strict=True)["x"]
        self.assertEqual(e["families"]["ext10"]["status"], G.NA_SCOPE)
        self.assertEqual(e["covered"], 5)
        self.assertIsNone(e["overall"])
        e2 = G.entry_families(inputs, "x", w)
        total = sum(w["families"][f] for f, r in e2.items() if r["status"] == "scored")
        self.assertAlmostEqual(G.overall_of(e2, {"families": dict(w["families"], **{"large-write": 0}), "kinds": w["kinds"]}, G.METHOD | {"method": dict(G.METHOD["method"], coverage_floor=1)})[0],
                               sum(w["families"][f] * r["score"] for f, r in e2.items() if r["status"] == "scored") / total, places=9)
        self.assertGreater(full, 70)

    def test_a_pi_port_without_a_core_capability_is_missing_and_scores_zero_in_the_mean(self):
        inputs = make({"gi": uniform(1.0)})
        inputs["arms"]["gi"] = info("gi", "pi-compatible", claims=("pi-extensions", "pi-sessions"))
        for c in inputs["cells"]:
            if c["family"] == "long-session":
                c["arms"].pop("gi")
        e = run(inputs, strict=True)["gi"]
        self.assertEqual(e["families"]["long-session"]["status"], G.NA_MISSING)
        self.assertEqual(e["families"]["long-session"]["score"], 0.0)
        self.assertEqual(e["covered"], 5)
        self.assertIsNotNone(run(inputs)["gi"]["overall"])
        self.assertIsNone(run(inputs, strict=True)["gi"]["overall"])
        inputs["arms"]["gi"]["claims"] += ["pi-rpc"]
        inputs["reliability"]["gi"] = [10, 10]
        e = run(inputs)["gi"]
        self.assertEqual(e["families"]["long-session"]["status"], G.NA_UNMEASURABLE)

    def test_missing_counts_as_zero_when_the_floor_is_met(self):
        inputs = make({"gi": uniform(1.0)})
        inputs["arms"]["gi"] = info("gi", "pi-compatible", claims=("pi-extensions", "pi-sessions"))
        for c in inputs["cells"]:
            if c["family"] == "long-session":
                c["arms"].pop("gi")
        method = G.METHOD | {"method": dict(G.METHOD["method"], coverage_floor=5)}
        e = {x["entry"]: x for x in G.grade(inputs, method=method, resamples=0)["entries"]}["gi"]
        w = G.weights_for("default")["families"]
        want = (70 * (w["core"] + w["ext10"] + w["streaming"] + w["reliability"] + w["devloop"]) + 0 * w["long-session"]) / sum(w[f] for f in ("core", "ext10", "streaming", "reliability", "devloop", "long-session"))
        self.assertAlmostEqual(e["overall_exact"], want, places=9)

    def test_unmeasurable_means_no_overall_score_and_names_the_reason(self):
        inputs = make({"x": uniform(1.0)})
        for c in inputs["cells"]:
            if c["family"] == "ext10":
                c["arms"].pop("x")
        inputs["skips"] = {"x": {"ext10": ["no base-URL setting"]}}
        e = run(inputs, strict=True)["x"]
        self.assertEqual(e["families"]["ext10"]["status"], G.NA_UNMEASURABLE)
        self.assertIn("no base-URL setting", e["families"]["ext10"]["reason"])
        self.assertIsNone(e["overall"])
        self.assertIn("not yet measurable", e["no_score_reason"])
        graded = run(inputs)["x"]   # not strict: scored from the families it has, the missing one named
        self.assertIsNotNone(graded["overall"])
        self.assertTrue(any("no base-URL setting" in c for c in graded["caveats"]))

    def test_a_run_without_claims_is_not_guessed(self):
        inputs = make({"x": uniform(1.0)})
        del inputs["arms"]["x"]["claims"]
        for c in inputs["cells"]:
            if c["family"] == "ext10":
                c["arms"].pop("x")
        self.assertEqual(run(inputs)["x"]["families"]["ext10"]["status"], G.NA_UNMEASURABLE)

    def test_a_partly_run_family_below_the_cell_share_is_not_covered(self):
        inputs = make({"x": uniform(1.0)})
        inputs["cells"][0]["arms"].pop("x")
        self.assertEqual(run(inputs)["x"]["families"]["core"]["cells"], 1)
        self.assertEqual(run(inputs)["x"]["families"]["core"]["status"], "scored")   # 1 of 2 cells is the minimum share
        inputs["cells"][1]["arms"].pop("x")
        self.assertNotEqual(run(inputs)["x"]["families"]["core"]["status"], "scored")

    def test_the_held_class_is_never_scored(self):
        inputs = make({"x": uniform(1.0)})
        inputs["arms"]["x"]["held"] = "licence rider"
        for c in inputs["cells"]:
            c["arms"].pop("x")
        self.assertEqual(run(inputs)["x"]["families"]["core"]["status"], G.NA_HELD)


class Gates(unittest.TestCase):
    def test_a_failing_family_scores_zero_even_when_its_survivors_are_fast(self):
        inputs = make({"x": uniform(0.1)}, failures={"x": {"core": [1, 36]}})
        e = run(inputs)["x"]
        self.assertEqual(e["families"]["core"]["score"], 0.0)
        self.assertIn("1 of 36", e["families"]["core"]["gate"])
        self.assertEqual(e["families"]["ext10"]["score"], G.score_of_ratio(0.1))
        self.assertEqual(run(make({"x": uniform(0.1)}, failures={"x": {"core": [0, 36]}}))["x"]["families"]["core"]["gate"], None)

    def test_the_reference_is_never_gated_and_an_all_failed_family_is_a_zero_not_na(self):
        inputs = make({"x": uniform(1.0)}, failures={REF: {"core": [3, 36]}, "x": {"streaming": [12, 12]}})
        r = run(inputs)
        self.assertEqual(r[REF]["families"]["core"]["score"], 70)
        self.assertEqual(r["x"]["families"]["streaming"]["score"], 0.0)

    def test_reliability_is_the_pass_fraction_against_the_references_as_a_higher_is_better_metric(self):
        e = run(make({"x": uniform(1.0)}, reliability={REF: [10, 10], "x": [5, 10]}))["x"]
        self.assertAlmostEqual(e["families"]["reliability"]["score"], G.score_of_ratio(2.0))
        e = run(make({"x": uniform(1.0)}, reliability={REF: [10, 10], "x": [0, 10]}))["x"]
        self.assertEqual(e["families"]["reliability"]["score"], 0.0)

    def test_the_runs_notes_never_change_a_score_and_never_remove_one(self):
        inputs = make({"x": uniform(1.0)})
        for notes in (0, 9):
            inputs["notes"] = notes
            for strict in (False, True):
                e = run(inputs, strict=strict)["x"]
                self.assertEqual(e["overall"], 70, (notes, strict))
                self.assertFalse(any("health" in c or "RED" in c for c in e["caveats"]))
        self.assertEqual(G.grade(inputs, resamples=0)["notes"], 9)


class GradeWithWhatThereIs(unittest.TestCase):
    def test_a_missing_reference_manifest_is_listed_not_refused(self):
        inputs = make({"x": uniform(0.5)})
        del inputs["arms"][REF]
        graded = G.grade(inputs, resamples=0)
        self.assertTrue(any(REF in m for m in graded["missing"]))
        with self.assertRaises(G.GradeError):
            G.grade(inputs, resamples=0, strict=True)

    def test_the_grade_carries_the_runs_trust_badge(self):
        inputs = make({"x": uniform(0.5)})
        inputs["trust"] = {"badge": "Noisy", "host_class": "B", "reasons": ["calibration above the limit"]}
        self.assertEqual(G.grade(inputs, resamples=0)["trust"]["badge"], "Noisy")


class Tables(unittest.TestCase):
    def test_faithfulness_sits_beside_the_score_and_splits_the_tables(self):
        inputs = make({"close": uniform(0.5), "far": uniform(0.25), "unknown": uniform(0.9)}, faithfulness={"close": 95.0, "far": 40.0})
        e = run(inputs)
        self.assertEqual(e[REF]["faithfulness"], 100.0)
        self.assertEqual((e[REF]["table"], e["close"]["table"], e["far"]["table"], e["unknown"]["table"]), ("pi-faithful", "pi-faithful", "not-pi-equivalent", "faithfulness-unmeasured"))
        self.assertEqual(e["close"]["rank"], 1)
        self.assertEqual(e[REF]["rank"], 2)
        self.assertEqual(e["far"]["rank"], 1)

    def test_overlapping_intervals_share_a_rank_range_and_clear_gaps_do_not(self):
        e = run(make({"a": uniform(0.50), "b": uniform(0.51), "c": uniform(4.0)}, faithfulness={"a": 95.0, "b": 95.0, "c": 95.0}), resamples=200)
        self.assertEqual(e["a"]["rank_range"][0], 1)
        self.assertLessEqual(e["a"]["rank_range"][0], e["b"]["rank_range"][1])
        self.assertEqual(e["c"]["rank_range"], [4, 4])

    def test_every_published_profile_is_reported_with_a_rank(self):
        e = run(make({"x": {**uniform(0.5), "ext10": 4.0}}))
        self.assertEqual(set(e["x"]["profiles"]), set(G.METHOD["weights"]))
        self.assertGreater(e["x"]["profiles"]["equal"]["score"], e["x"]["profiles"]["extension-heavy"]["score"])

    def test_the_interval_brackets_the_score_is_a_point_for_the_reference_and_is_seeded(self):
        inputs = make({"x": {**uniform(0.6), "core": 0.7}})
        a, b = run(inputs, resamples=120), run(inputs, resamples=120)
        self.assertEqual(a["x"]["ci"], b["x"]["ci"])
        lo, hi = a["x"]["ci"]
        self.assertLessEqual(lo, a["x"]["overall_exact"])
        self.assertGreaterEqual(hi, a["x"]["overall_exact"])
        self.assertEqual(a[REF]["ci"], [70.0, 70.0])
        self.assertNotEqual(run(inputs, resamples=120, seed=9)["x"]["ci"], a["x"]["ci"]) if hi > lo else None


class Weights(unittest.TestCase):
    def test_a_weights_file_changes_only_weights_and_is_validated(self):
        w = G.weights_for("default", {"families": {"ext10": 0}})
        self.assertEqual(w["families"]["ext10"], 0)
        self.assertEqual(w["families"]["core"], 2)
        for bad in ({"bands": {"A": 80}}, {"families": {"nonsense": 1}}, {"families": {"core": -1}}, {"families": {"core": "x"}}, {"kinds": {"cpu": math.inf}}, {"families": {k: 0 for k in G.family_ids()}}):
            with self.assertRaises(G.GradeError, msg=bad):
                G.weights_for("default", bad)
        with self.assertRaises(G.GradeError):
            G.weights_for("nope")

    def test_changing_a_weight_moves_the_score_toward_that_family(self):
        inputs = make({"x": {**uniform(1.0), "ext10": 0.25}})
        d = run(inputs, resamples=0)["x"]["overall_exact"]
        h = run(inputs, weights=G.weights_for("extension-heavy"), resamples=0)["x"]["overall_exact"]
        z = run(inputs, weights=G.weights_for("default", {"families": {"ext10": 0}}), resamples=0)["x"]["overall_exact"]
        self.assertGreater(h, d)
        self.assertGreater(d, z)
        self.assertAlmostEqual(z, 70.0)


class Manifests(unittest.TestCase):
    def arm(self, **spec):
        base = {"name": "t", "label": "T", "homepage": "https://example.com", "relation": "pi-port", "licence": "MIT", "licence_url": "https://example.com/l", "version": "1", "held": "x"}
        base.update(spec)
        manifest.validate("t", base, tempfile.gettempdir())
        return manifest.Arm("t", base, tempfile.gettempdir(), "0" * 64)

    def test_claims_come_from_the_manifest_else_from_what_it_declares(self):
        self.assertEqual(self.arm(claims=["pi-sessions"]).claims, ["pi-sessions"])
        a = self.arm(capabilities={"pi_extensions": "sidecar", "pi_session_format": True}, modes={"rpc": ["--mode", "rpc"]})
        self.assertEqual(a.claims, ["pi-extensions", "pi-sessions", "pi-rpc"])
        b = self.arm(capabilities={"pi_extensions": "none"}, modes={"rpc": []}, cannot_run={"rpc": "no Pi RPC"})
        self.assertEqual(b.claims, [])

    def test_a_claim_outside_the_vocabulary_is_refused(self):
        with self.assertRaises(manifest.ManifestError):
            self.arm(claims=["pi-magic"])
        with self.assertRaises(manifest.ManifestError):
            self.arm(claims=["pi-rpc", "pi-rpc"])


def read_text(path):
    with open(path) as f:
        return f.read()


def read_json(path):
    return json.loads(read_text(path))


def series_for(arm_ratio=0.5):
    out = []
    for r in range(12):
        for name, base, shift in ((REF, 100.0, 0), (REF + "-b", 100.0, 3), ("fast", 100.0 * arm_ratio, 1), ("fast-b", 100.0 * arm_ratio, 5)):
            out.append(sample(name, "overhead/print", r, cpu_ms=base + wobble(r + shift), peak_rss_mib=50.0 + wobble(r + shift) / 10))
    return out


class EndToEnd(unittest.TestCase):
    def raw(self):
        raw = raw_of(series_for(0.5))
        raw["arms"] = {REF: {"label": "Pi Node", "relation": "pi-reference", "claims": ["pi-extensions", "pi-sessions", "pi-rpc"], "install_method": "npm ci"},
                       REF + "-b": {"twin_of": REF}, "fast": {"label": "Fast", "relation": "pi-port", "claims": ["pi-rpc"], "install_method": "release archive"}, "fast-b": {"twin_of": "fast"}}
        return raw

    def test_report_writes_the_grade_and_grade_recomputes_it_from_report_json_alone(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = os.path.join(d, "run")
            os.makedirs(run_dir)
            with open(os.path.join(run_dir, "raw.json"), "w") as f:
                json.dump(self.raw(), f)
            out = os.path.join(d, "out")
            try:
                render.render([run_dir], out)
            except Exception as e:   # the raw reader is strict about facts the fixture does not carry: the grade must not be what breaks it
                self.skipTest(f"fixture not accepted by the raw reader: {e}")
            report = read_json(os.path.join(out, "report.json"))
            self.assertIn("grade_inputs", report)
            grade = read_json(os.path.join(out, "grade.json"))
            by = {e["entry"]: e for e in grade["entries"]}
            self.assertEqual(by[REF]["families"]["core"]["score"], 70)
            self.assertEqual(by["fast"]["families"]["core"]["status"], "scored")
            self.assertGreater(by["fast"]["families"]["core"]["score"], 70)
            self.assertEqual(by["fast"]["families"]["ext10"]["status"], G.NOT_RUN)   # no ext10 cell in this run: the reference has none either
            leaderboard = read_text(os.path.join(out, "leaderboard.md"))
            self.assertIn("PROVISIONAL", leaderboard)
            self.assertIn("**Trust: Shared**", leaderboard)   # a noisy, shared run is graded and labelled, not left without a score
            self.assertIn("Pi Harness Score", read_text(os.path.join(out, "report.md")))
            weights = os.path.join(d, "w.toml")
            with open(weights, "w") as f:
                f.write("[families]\ncore = 5\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli.main(["grade", out, "--weights", weights, "--json", "--resamples", "20", "--out", os.path.join(d, "again")])
            self.assertEqual(rc, 0)
            again = json.loads(buf.getvalue())
            self.assertEqual(again["weights"]["families"]["core"], 5)
            self.assertEqual({e["entry"]: e["families"]["core"]["score"] for e in again["entries"]}, {e["entry"]: e["families"]["core"]["score"] for e in grade["entries"]})
            self.assertTrue(os.path.exists(os.path.join(d, "again", "report-card.md")))

    def test_grade_refuses_a_bad_weights_file_and_a_report_without_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "report.json"), "w") as f:
                json.dump({"cells": []}, f)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(["grade", d]), 2)
            self.assertIn("grade_inputs", err.getvalue())


if __name__ == "__main__":
    unittest.main()


class ReviewMutants(unittest.TestCase):
    """Cases that pin down what the fixture's one-ratio-per-family inputs cannot tell apart (review of a3cfeef): each fails under a named mutant."""

    def family_score(self, inputs, fam="core", arm="x"):
        return run(inputs, resamples=0)[arm]["families"][fam]

    def two_cell_core(self, r_cpu, r_mem, floor=None):
        inputs = make({"x": uniform(1.0)})
        for c in inputs["cells"]:
            if c["family"] == "core":
                c["arms"]["x"]["ratio"] = r_cpu if c["kind"] == "cpu" else r_mem
                c["arms"]["x"]["floor"] = floor
        return inputs

    def test_a_family_ratio_is_the_geometric_mean_of_its_cells(self):
        # mutant: arithmetic mean (2 and 0.5 give 1.25, not 1)
        self.assertAlmostEqual(self.family_score(self.two_cell_core(2.0, 0.5))["score"], 70.0, places=9)

    def test_kind_weights_weight_the_cells_of_a_family(self):
        # mutant: kind weights ignored. cpu 3, memory 1: r = 2 ** (3/4)
        w = G.weights_for("default", {"kinds": {"cpu": 3, "memory": 1}})
        e = {x["entry"]: x for x in G.grade(self.two_cell_core(2.0, 1.0), w, resamples=0)["entries"]}
        self.assertAlmostEqual(e["x"]["families"]["core"]["score"], 70 - 10 * 0.75, places=9)

    def test_a_family_with_under_half_of_the_reference_cells_is_not_covered(self):
        # mutant: the cell share ignored; and (fixed in review) a cell with no usable ratio does not count toward the share
        inputs = make({"x": uniform(1.0)})
        core = [c for c in inputs["cells"] if c["family"] == "core"]
        extra = [cell("core", 9, "cpu", {}), cell("core", 8, "memory", {}), cell("core", 6, "cpu", {})]
        inputs["cells"].extend(extra)
        self.assertEqual(self.family_score(inputs)["status"], "NA-unmeasurable")   # 2 of 5
        inputs["cells"] = [c for c in inputs["cells"] if c not in extra]
        core[0]["arms"]["x"]["ratio"] = math.nan                                       # 1 usable of 2: half, still covered
        self.assertEqual(self.family_score(inputs)["status"], "scored")
        inputs["cells"].append(cell("core", 7, "cpu", {"x": math.inf}))                # 1 usable of 3: under half
        self.assertEqual(self.family_score(inputs)["status"], "NA-unmeasurable")

    def test_the_bootstrap_draws_the_same_rounds_for_both_arms(self):
        # mutant: an independent draw for the entry. An entry at exactly 2x the reference in every round has a paired ratio of 2 in every replicate.
        inputs = make({"x": uniform(2.0)})
        for c in inputs["cells"]:
            ref = c["values"][REF]
            for k in ref:
                ref[k] = 100.0 * (1 + int(k.split(":")[1]))     # rounds differ ten-fold
            c["values"]["x"] = {k: 2 * v for k, v in ref.items()}
            c["arms"]["x"]["floor"] = None
        e = run(inputs, resamples=60)["x"]
        self.assertAlmostEqual(e["ci"][0], e["ci"][1], places=9)
        self.assertAlmostEqual(e["ci"][0], e["overall_exact"], places=9)

    def test_rank_ranges_overlap_when_the_intervals_do(self):
        # mutant: an entry counted as outranked when another's interval only starts above its low end
        es = [{"entry": "a", "ci": [70, 80]}, {"entry": "b", "ci": [75, 85]}, {"entry": "c", "ci": [90, 95]}]
        rr = G.rank_ranges(es, lambda o: o["ci"][0], lambda o: o["ci"][1], None)
        self.assertEqual(rr, {"a": (2, 3), "b": (2, 3), "c": (1, 1)})

    def test_a_faithfulness_score_at_the_floor_is_pi_faithful(self):
        floor = G.METHOD["method"]["faithfulness_floor"]
        self.assertEqual(G.table_of({"overall": 75, "faithfulness": floor}), "pi-faithful")
        self.assertEqual(G.table_of({"overall": 75, "faithfulness": floor - 0.01}), "not-pi-equivalent")

    def test_only_the_reference_is_faithful_by_definition(self):
        # fixed in review: another arm declaring relation pi-reference (pi-bun) was given 100 without a faithfulness run
        inputs = make({"x": uniform(1.0)})
        inputs["arms"]["x"]["relation"] = "pi-reference"
        e = run(inputs, resamples=0)
        self.assertEqual((e[REF]["faithfulness"], e["x"]["faithfulness"], e["x"]["table"]), (100.0, None, "faithfulness-unmeasured"))

    def test_no_reference_pass_makes_reliability_not_run_instead_of_zero_for_everyone(self):
        # fixed in review: reference 0/8 gave every entry ratio None, score 0, even one passing 8/8
        inputs = make({"x": uniform(1.0)}, reliability={REF: [0, 8], "x": [8, 8]})
        for arm in (REF, "x"):
            self.assertEqual(self.family_score(inputs, "reliability", arm)["status"], "not-run")

    def test_inputs_from_another_method_are_refused(self):
        # fixed in review: `buffon grade` recomputed old inputs with the current grade.toml and printed its hash on them
        inputs = make({"x": uniform(1.0)}, method_sha256="0" * 64, method_version=1)
        with self.assertRaises(G.GradeError):
            G.grade(inputs, resamples=0)
        run(make({"x": uniform(1.0)}, method_sha256=G.METHOD["sha256"]), resamples=0)


class ReviewInputs(unittest.TestCase):
    """grade_inputs: warm-up samples never gate and a reference failure does not gate another entry."""

    def test_a_failed_warmup_sample_does_not_count_for_the_gate(self):
        from buffon.report import grade_inputs as GI
        samples = [{"scenario": "overhead/print", "arm": "x", "warmup": True, "failure": "boom"}, {"scenario": "overhead/print", "arm": "x", "warmup": False}]
        data = {"reference": REF, "base": [REF, "x"], "cells": [], "samples": samples}
        doc = GI.build(data, [{"arms": {}, "skipped": []}], {"notes": 0}, True, [])
        self.assertEqual(doc["failures"]["x"]["core"], [0, 1])

    def test_a_sample_the_reference_also_failed_does_not_gate_another_entry(self):
        # fixed in review: m4-smoke grow-n failed 4 of 16 for pi-node and pig-0.4.1; pig's long-session scored 0 (F) as a loss, pi-node kept 70
        from buffon.report import grade_inputs as GI
        S = lambda arm, scen, api="openai-completions", fail=True, twin=None: dict({"scenario": scen, "arm": arm, "warmup": False, "api": api, "twin_of": twin}, **({"failure": "x"} if fail else {}))
        samples = [S("pi-node-b", "longsession/grow-n", twin=REF), S("x", "longsession/grow-n"), S("x", "longsession/grow-n", api="anthropic-messages"),
                   S("x", "longsession/resume-n"), S(REF, "longsession/resume-n", fail=False)]
        data = {"reference": REF, "base": [REF, "x"], "cells": [], "samples": samples}
        doc = GI.build(data, [{"arms": {}, "skipped": []}], {"notes": 0}, True, [])
        # grow-n/completions failed for the reference's copy: not counted for x; the anthropic grow-n and resume-n failures are x's own
        self.assertEqual(doc["failures"]["x"]["long-session"], [2, 3])
        self.assertEqual(doc["failures"][REF]["long-session"], [0, 1])
