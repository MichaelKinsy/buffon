# SPDX-License-Identifier: Apache-2.0
"""A/A statistics and the reference change point (buffon/report/aa.py), and the quota probe."""
import math
import os
import random
import unittest

from buffon.report import aa, cells as cellmath
from buffon.telemetry import probes
from tests.fake_kernel import FakeKernel
from tests.telemetry_fixtures import run


class TTest(unittest.TestCase):
    def test_known_p_values(self):
        self.assertAlmostEqual(aa.t_two_sided_p(2.2010, 11), 0.05, places=3)
        self.assertAlmostEqual(aa.t_two_sided_p(2.0, 1), 0.2952, places=3)
        self.assertEqual(aa.t_two_sided_p(0.0, 5), 1.0)
        self.assertEqual(aa.t_two_sided_p(math.inf, 5), 0.0)
        self.assertTrue(math.isnan(aa.t_two_sided_p(1.0, 0)))

    def test_paired_p_separates_a_constant_ratio_from_noise(self):
        base = [100.0 + i for i in range(12)]
        self.assertLess(aa.paired_p([x * 1.03 + (i % 2) for i, x in enumerate(base)], base), 0.001)
        self.assertGreater(aa.paired_p([x + (-1) ** i for i, x in enumerate(base)], base), 0.2)
        self.assertEqual(aa.paired_p(base, base), 1.0)
        self.assertEqual(aa.paired_p([x * 2 for x in base], base), 0.0, "every ratio exactly 2")
        self.assertTrue(math.isnan(aa.paired_p([1.0, 2.0], [1.0, 2.0])))


class Pairs(unittest.TestCase):
    def test_a_p_between_five_and_fifty_percent_is_not_significant(self):
        base = [100.0 + i for i in range(12)]
        copy = [x * (1.0 + 0.01 * (i % 3 - 1) + 0.001 * i) for i, x in enumerate(base)]
        p = aa.paired_p(copy, base)
        self.assertTrue(0.05 < p < 0.5, p)
        cell = cellmath.Cell("s", None, "cpu_ms")
        cell.values = {"a": dict(enumerate(base)), "a-b": dict(enumerate(copy))}
        self.assertEqual(aa.significant({"cells": [cell], "base": ["a"]}), (0, 1))

    def test_cv_only_over_cpu_metrics_and_significance_counts_pairs(self):
        data = cellmath.build([run()])
        self.assertEqual(len(aa.pairs(data)), 4)
        self.assertEqual(len(aa.cv_cpu(data)), 4, "two arms and their copies in the one cpu_ms cell; wall_ms is not a CPU metric")
        self.assertEqual(aa.significant(data), (0, 4))

        def shift(s):
            if s["arm"] == "other-b" and not s["warmup"]:
                s["cpu_ms"] *= 1.05
        self.assertEqual(aa.significant(cellmath.build([run(mutate=shift)])), (1, 4))


class ScaleLadder(unittest.TestCase):
    """A swarm rung that stopped is a failed sample: it is not a value of its cell, so an A/A gap is computed over the rounds in which both copies completed."""

    def samples(self):
        out = []
        for rnd in range(6):
            for arm, base in (("a", 100.0), ("a-b", 100.0)):
                s = {"arm": arm, "scenario": "scale/print-1024", "api": None, "round": rnd, "warmup": False, "wall_ms_p50": base + rnd, "agents": 1024, "agents_ok": 1024}
                if arm == "a" and rnd in (1, 2):    # one copy stopped (OOM) in two rounds; the other completed them with a very different value
                    s = {k: v for k, v in s.items() if k not in ("wall_ms_p50",)}
                    s.update(failure="out of memory", stop_cause="oom", agents_ok=900)
                if arm == "a-b" and rnd in (1, 2):
                    s["wall_ms_p50"] = 9000.0
                if arm == "a-b" and rnd == 5:
                    s["wall_ms_p50"] = 100.0 + rnd
                out.append(s)
        return out

    def test_a_gap_pairs_only_the_rounds_where_both_copies_completed(self):
        raw = {"samples": self.samples(), "arms": {}, "run": {}}
        data = cellmath.build([raw])
        cell = next(c for c in data["cells"] if c.metric == "wall_ms_p50")
        self.assertEqual(sorted(cell.values["a"]), [(0, 0), (0, 3), (0, 4), (0, 5)])
        self.assertEqual(len(cell.values["a-b"]), 6)
        gaps = aa.gaps(data)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0][0], 0.0)           # the two stopped rounds' 9000 ms never meets a missing value

    def test_runner_cpu_is_not_a_scored_metric(self):
        self.assertFalse(cellmath.scored("runner_cpu_ms"))
        self.assertFalse(cellmath.scored("mock_cpu_ms"))


class Gap(unittest.TestCase):
    def shifted(self, factor):
        def shift(s):
            if s["arm"] == "pi-node-b" and not s["warmup"]:
                s["cpu_ms"] *= factor
        return cellmath.build([run(mutate=shift)])

    def test_a_sub_one_percent_gap_is_significant_to_the_test_but_not_counted(self):
        data = self.shifted(1.009)          # every round of the copy is 0.9% above its arm: a systematic gap, p far below 0.05
        self.assertEqual(aa.significant(data, min_gap=0), (1, 4), "the t-test alone calls it different")
        self.assertEqual(aa.significant(data), (0, 4), "a gap of 1% or less does not count")

    def test_a_gap_above_one_percent_that_is_significant_is_counted(self):
        self.assertEqual(aa.significant(self.shifted(1.011)), (1, 4))

    def test_the_gap_is_the_distance_of_the_copys_median_from_its_arms(self):
        gaps = {(c.metric, arm): g for g, c, arm in aa.gaps(self.shifted(1.03))}
        self.assertAlmostEqual(gaps[("cpu_ms", "pi-node")], 0.03, places=3)
        self.assertEqual(gaps[("cpu_ms", "other")], 0.0)
        self.assertEqual(len(gaps), 4)


class ChangePoint(unittest.TestCase):
    def test_a_step_is_found_at_the_right_split_and_a_stationary_series_is_not(self):
        rng = random.Random(1)
        step = [1.0 + rng.uniform(-0.01, 0.01) + (0.1 if i >= 8 else 0) for i in range(14)]
        cp = aa.changepoint(step, permutations=199)
        self.assertEqual(cp["index"], 8)
        self.assertAlmostEqual(cp["shift"], 0.1, delta=0.02)
        fires = sum(aa.changepoint([1.0 + random.Random(k * 100 + j).uniform(-0.01, 0.01) for j in range(14)], permutations=199, seed=k) is not None for k in range(30))
        self.assertLessEqual(fires, 2, "alpha 0.01 must not fire on stationary noise")
        self.assertIsNone(aa.changepoint([1.0] * 14))
        self.assertIsNone(aa.changepoint([1.0, 1.2, 1.0, 1.2]), "too short for segments of 3")
        self.assertIsNone(aa.changepoint([1.0, 1.0, 1.0, 5.0, 5.0], permutations=199), "5 rounds cannot hold two segments of 3, whatever the step")
        self.assertEqual(aa.changepoint([1.0, 1.01, 0.99, 1.0, 1.0, 5.0, 5.01, 4.99, 5.0, 5.0], permutations=199)["index"], 5)

    def test_the_reference_index_follows_a_host_wide_step_over_every_cell(self):
        def step(s):
            if s["arm"] == "pi-node" and s["round"] >= 7:
                s["cpu_ms"] *= 1.2
                s["wall_ms"] *= 1.2
        idx = {k[1]: v for k, v in aa.reference_index(cellmath.build([run(mutate=step)]))}   # cells key a round by (run, round)
        self.assertGreater(idx[8] / idx[6], 1.15)
        self.assertAlmostEqual(idx[1], idx[2], delta=0.05)

    def test_a_shift_with_no_a_a_floor_is_a_note(self):
        def step(s):
            if s["arm"].startswith("pi-node") and s["round"] >= 7:
                s["cpu_ms"] *= 1.2
                s["wall_ms"] *= 1.2
        raw = run(mutate=step)
        raw["samples"] = [s for s in raw["samples"] if not s["arm"].endswith("-b")]
        r = aa.reference_changepoint(cellmath.build([raw]))
        self.assertEqual((r["floor"], r["status"]), (None, "note"))


class Quota(unittest.TestCase):
    def test_a_cgroup_with_a_cpu_max_is_listed_unlimited_ones_are_not(self):
        k = FakeKernel()
        os.makedirs(os.path.join(k.cg, "a", "b"))
        k.write(k.cg, "a/cpu.max", "200000 100000\n")
        k.write(k.cg, "a/b/cpu.max", "max 100000\n")
        self.assertEqual(probes.quota_limited(k.src, os.path.join(k.cg, "a", "b")), ["a"])
        k.write(k.cg, "a/cpu.max", "max 100000\n")
        self.assertEqual(probes.quota_limited(k.src, os.path.join(k.cg, "a", "b")), [])
        k.write(k.cg, "a/b/cpu.max", "50000 100000\n")
        self.assertEqual(probes.quota_limited(k.src, os.path.join(k.cg, "a", "b")), ["a/b"])

    def test_the_final_record_names_the_limited_ancestors(self):
        k = FakeKernel()
        os.makedirs(os.path.join(k.cg, "lane", "buffon-1"))
        k.write(k.cg, "lane/cpu.max", "100000 100000\n")
        k.write(k.cg, "lane/buffon-1/cpu.stat", "usage_usec 5\n")
        f = probes.cgroup_final(k.src, os.path.join(k.cg, "lane", "buffon-1"))
        self.assertEqual(f["ancestors"]["limited"], ["lane"])
        m = probes.merge_finals([f, dict(f, ancestors={"limited": ["x"]})])
        self.assertEqual(m["ancestors"]["limited"], ["lane", "x"])


if __name__ == "__main__":
    unittest.main()
