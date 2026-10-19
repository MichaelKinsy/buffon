# SPDX-License-Identifier: Apache-2.0
"""Equivalence (TOST) on the paired ratio: declared margins, the test itself, the cells that carry it and the report that shows it."""
import json
import math
import os
import random
import tempfile
import unittest

from buffon import stats
from buffon.report import cells, render
from buffon.stats import margins
from tests.test_report import raw_of, sample, series as report_series

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pairs(n, ratio, spread, seed=1):
    rng = random.Random(seed)
    ref = [100.0 * (1 + rng.uniform(-spread, spread)) for _ in range(n)]
    arm = [r * ratio * (1 + rng.uniform(-spread, spread) / 4) for r in ref]   # paired: the arm follows the reference round by round
    return arm, ref


class Margins(unittest.TestCase):
    def test_the_declared_margins_are_the_ones_methodology_proposes(self):
        t = margins.load()
        self.assertEqual(margins.margin_for("cpu_ms", 80.0, t), 0.05)
        self.assertEqual(margins.margin_for("wall_ms", 80.0, t), 0.05)
        self.assertEqual(margins.margin_for("instructions", 1e9, t), 0.05)
        self.assertEqual(margins.margin_for("cpu_ms_per_turn", 3.0, t), 0.05)
        self.assertEqual(margins.margin_for("request_bytes_per_turn", 5000.0, t), 0.0)
        self.assertEqual(margins.margin_for("input_tokens_per_turn", 5000.0, t), 0.0)
        self.assertEqual(margins.margin_for("pass_rate", 0.5, t), 0.0)

    def test_memory_margin_is_five_percent_or_two_mib_whichever_is_larger(self):
        t = margins.load()
        self.assertEqual(margins.margin_for("peak_rss_mib", 100.0, t), 0.05)    # 5% is 5 MiB: larger than 2 MiB
        self.assertAlmostEqual(margins.margin_for("peak_rss_mib", 10.0, t), 0.2)  # 2 MiB is 20% of 10 MiB
        self.assertAlmostEqual(margins.margin_for("peak_rss_mib", 40.0, t), 0.05)  # 5% of 40 MiB is exactly 2 MiB

    def test_a_metric_with_no_entry_has_no_margin(self):
        self.assertIsNone(margins.margin_for("binary_bytes", 1e6, margins.load()))
        self.assertIsNone(margins.margin_for("cpu_ms", 1.0, []))

    def test_the_first_matching_entry_decides(self):
        table = [{"metrics": ["*_per_turn"], "relative": 0.0, "absolute": None}, {"metrics": ["*_ms*"], "relative": 0.1, "absolute": None}]
        self.assertEqual(margins.margin_for("cpu_ms_per_turn", 1.0, table), 0.0)
        self.assertEqual(margins.margin_for("cpu_ms", 1.0, table), 0.1)

    def test_a_malformed_file_is_refused_with_its_entry_named(self):
        for body, word in (("[[margin]]\nrelative = 0.05\n", "metrics"), ('[[margin]]\nmetrics = ["x"]\nrelative = -1\n', "relative"), ('[[margin]]\nmetrics = ["x"]\n', "relative")):
            with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
                f.write(body)
            with self.assertRaises(ValueError) as cm:
                margins.load(f.name)
            self.assertIn(word, str(cm.exception))


class Tost(unittest.TestCase):
    def test_equivalent_when_the_interval_lies_inside_the_margin(self):
        arm, ref = pairs(12, 1.01, 0.01)
        e = stats.tost_ratio(arm, ref, 0.05)
        self.assertTrue(e["equivalent"], e)
        self.assertGreater(e["low"], 1 / 1.05)
        self.assertLess(e["high"], 1.05)
        self.assertLess(e["p"], 0.05)

    def test_not_equivalent_when_the_interval_crosses_the_margin(self):
        arm, ref = pairs(12, 1.03, 0.25)   # a 3% median shift under 25% noise: the 90% interval reaches past +5%
        e = stats.tost_ratio(arm, ref, 0.05)
        self.assertFalse(e["equivalent"], e)
        self.assertTrue(e["low"] <= 1 / 1.05 or e["high"] >= 1.05, e)
        self.assertGreaterEqual(e["p"], 0.05)

    def test_not_equivalent_when_the_shift_is_outside_the_margin_even_if_tight(self):
        arm, ref = pairs(12, 1.10, 0.005)
        e = stats.tost_ratio(arm, ref, 0.05)
        self.assertFalse(e["equivalent"], e)
        self.assertEqual(e["p"], 1.0)

    def test_the_margin_is_symmetric_on_the_log_scale(self):
        ref = [100.0 + i for i in range(12)]
        up = stats.tost_ratio([r * 1.04 for r in ref], ref, 0.05)
        down = stats.tost_ratio([r / 1.04 for r in ref], ref, 0.05)
        self.assertTrue(up["equivalent"] and down["equivalent"])
        self.assertFalse(stats.tost_ratio([r * 1.06 for r in ref], ref, 0.05)["equivalent"])
        self.assertFalse(stats.tost_ratio([r / 1.06 for r in ref], ref, 0.05)["equivalent"])   # 1/1.06 sits below 1/1.05

    def test_a_wider_margin_can_only_turn_not_equivalent_into_equivalent(self):
        arm, ref = pairs(12, 1.03, 0.08)
        verdicts = [stats.tost_ratio(arm, ref, m)["equivalent"] for m in (0.01, 0.03, 0.05, 0.1, 0.3)]
        self.assertEqual(verdicts, sorted(verdicts))
        self.assertTrue(verdicts[-1])

    def test_an_exact_margin_needs_every_pair_equal(self):
        ref = [5000.0] * 8
        self.assertTrue(stats.tost_ratio(list(ref), ref, 0.0)["equivalent"])
        self.assertFalse(stats.tost_ratio(ref[:-1] + [5001.0], ref, 0.0)["equivalent"])

    def test_too_few_pairs_or_a_zero_reference_have_no_answer(self):
        self.assertIsNone(stats.tost_ratio([1.0], [1.0], 0.05))
        self.assertIsNone(stats.tost_ratio([1.0, 2.0], [0.0, 0.0], 0.05))

    def test_reusing_the_ratios_draws_gives_the_same_answer(self):
        arm, ref = pairs(12, 1.02, 0.05)
        draws = stats.bootstrap_ratios(arm, ref, seed=3)
        self.assertEqual(stats.tost_ratio(arm, ref, 0.05, seed=3), stats.tost_ratio(arm, ref, 0.05, seed=3, draws=draws))
        self.assertEqual(stats.paired_ratio_of_medians(arm, ref, seed=3), stats.paired_ratio_of_medians(arm, ref, seed=3, draws=draws))


class InCells(unittest.TestCase):
    def build(self, metric, ref, arm, rounds=12, wobble=0.01):
        rng = random.Random(5)
        samples = []
        for r in range(rounds):
            base = ref * (1 + rng.uniform(-wobble, wobble))
            for name, v in (("ref", base), ("ref-b", base * (1 + rng.uniform(-wobble, wobble))), ("x", arm / ref * base), ("x-b", arm / ref * base * (1 + rng.uniform(-wobble, wobble)))):
                samples.append(sample(name, "overhead/print", r, **{metric: v}))
        data = cells.build([raw_of(samples)], reference="ref")
        return next(c for c in data["cells"] if c.metric == metric).comparisons["x"]

    def test_a_cpu_cell_carries_the_test_with_its_margin(self):
        e = self.build("cpu_ms", 100.0, 101.0).equivalence
        self.assertEqual(e["margin"], 0.05)
        self.assertTrue(e["equivalent"])

    def test_a_cell_is_not_equivalent_when_the_arm_is_outside_the_margin(self):
        self.assertFalse(self.build("cpu_ms", 100.0, 120.0).equivalence["equivalent"])

    def test_a_metric_without_a_margin_has_none(self):
        self.assertIsNone(self.build("binary_bytes", 1e6, 1e6).equivalence)

    def test_memory_uses_the_two_mib_floor_for_small_footprints(self):
        small = self.build("peak_rss_mib", 10.0, 11.5).equivalence   # +1.5 MiB: inside 2 MiB although it is 15%
        self.assertAlmostEqual(small["margin"], 0.2, places=1)
        self.assertTrue(small["equivalent"])
        large = self.build("peak_rss_mib", 100.0, 106.0).equivalence   # +6 MiB: outside 5%
        self.assertEqual(large["margin"], 0.05)
        self.assertFalse(large["equivalent"])

    def test_equivalent_and_no_measurable_difference_are_different_claims(self):
        """A noisy pair of copies gives a wide floor: a 20% gap sits inside it ("no measurable difference") and is far outside the 5% margin (not equivalent)."""
        c = self.build("cpu_ms", 100.0, 120.0, wobble=0.35)
        self.assertEqual(c.verdict, "no measurable difference")
        self.assertFalse(c.equivalence["equivalent"])


class InTheReport(unittest.TestCase):
    def test_report_json_and_markdown_show_the_equivalence(self):
        d = tempfile.mkdtemp()
        raw = raw_of(report_series(arm=101.0))
        os.makedirs(os.path.join(d, "run"))
        with open(os.path.join(d, "run", "raw.json"), "w") as f:
            json.dump(raw, f)
        out = os.path.join(d, "out")
        render.render([os.path.join(d, "run")], out)
        with open(os.path.join(out, "report.json")) as f:
            rep = json.load(f)
        comp = next(c for c in rep["cells"] if c["metric"] == "cpu_ms")["comparisons"]["other"]
        self.assertEqual(set(comp["equivalence"]), {"margin", "low", "high", "p", "equivalent"})
        self.assertTrue(comp["equivalence"]["equivalent"])
        self.assertTrue(comp["equivalence"]["low"] < comp["ratio"] < comp["equivalence"]["high"])
        with open(os.path.join(out, "report.md")) as f:
            md = f.read()
        self.assertIn("| equivalent (TOST) |", md)
        self.assertIn("| yes ±5.0% |", md)


if __name__ == "__main__":
    unittest.main()
