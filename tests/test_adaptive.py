# SPDX-License-Identifier: Apache-2.0
"""Adaptive stopping: a cell stops when its answer is clear or tightly inside the noise floor, and not before the rounds Holm across its arms needs."""
import random
import unittest

from buffon.runner import adaptive


def series(base, n, spread, seed):
    rng = random.Random(seed)
    return {r: base * (1 + rng.uniform(-spread, spread)) for r in range(n)}


def values(n, ref=100.0, arm=100.0, spread=0.01, aa_spread=0.01):
    return {"ref": series(ref, n, spread, 1), "ref-b": series(ref, n, aa_spread, 2), "arm": series(arm, n, spread, 3), "arm-b": series(arm, n, aa_spread, 4)}


def many(arms, n, arm=150.0, spread=0.01):
    """A reference with its copy and `arms` compared arms, each with a copy, over n rounds."""
    out = {"ref": series(100.0, n, spread, 1), "ref-b": series(100.0, n, spread, 2)}
    for i in range(arms):
        out[f"a{i}"] = series(arm, n, spread, 10 + i)
        out[f"a{i}-b"] = series(arm, n, spread, 50 + i)
    return out


class Minimum(unittest.TestCase):
    def test_the_minimum_is_the_fewest_rounds_where_holm_can_still_reach_significance(self):
        for k in range(1, 40):
            n = adaptive.min_rounds(k)
            self.assertLess(k * 2 / 2 ** n, 0.05, k)             # the smallest Holm-adjusted p the exact test can give is below 0.05 ...
            self.assertGreaterEqual(k * 2 / 2 ** (n - 1), 0.05, k)   # ... and one round fewer cannot reach it
        self.assertEqual([adaptive.min_rounds(k) for k in (1, 2, 4, 8)], [6, 7, 8, 9])
        self.assertEqual(adaptive.MIN_ROUNDS, 6)

    def test_the_bound_is_real_for_the_exact_test_and_holm(self):
        """Six all-one-sided pairs give p = 2/64; Holm over eight arms makes it 0.25, never below 0.05. At nine rounds Holm over eight arms gives 8 * 2/512 = 0.031."""
        from buffon import stats
        for n, reachable in ((8, False), (9, True)):
            p = stats.sign_flip_p([2.0] * n, [1.0] * n)
            self.assertEqual(stats.holm([p] * 8)[0] < 0.05, reachable, n)

    def test_eight_compared_arms_need_nine_rounds_even_when_every_loss_is_obvious(self):
        for n, settled in ((8, False), (9, True)):
            v = many(8, n)
            done, verdicts, _ = adaptive.variant_status(samples_for(v), "overhead/print", "a", "ref", list(v))
            self.assertEqual(done, settled, (n, verdicts))
            self.assertEqual(adaptive.variant_minimum(samples_for(v), "overhead/print", "a", "ref", list(v)), 9)

    def test_a_tight_no_measurable_difference_does_not_settle_before_the_minimum_either(self):
        for n, settled in ((8, False), (9, True)):
            v = many(8, n, arm=100.0, spread=0.004)
            for name in list(v):
                if name.endswith("-b"):
                    v[name] = series(100.0, n, 0.02, sum(map(ord, name)))   # copies noisier than the data: a tight floor around a zero difference
            done, verdicts, _ = adaptive.variant_status(samples_for(v), "overhead/print", "a", "ref", list(v))
            self.assertEqual(done, settled, (n, verdicts))
            if settled:
                self.assertEqual(set(verdicts.values()), {"no measurable difference"})

    def test_arms_without_data_do_not_raise_the_minimum(self):
        v = many(1, 6)
        self.assertEqual(adaptive.variant_minimum(samples_for(v), "overhead/print", "a", "ref", list(v) + [f"ghost{i}" for i in range(7)]), 6)


class Judge(unittest.TestCase):
    def test_nothing_is_settled_before_the_minimum_rounds(self):
        settled, why = adaptive.judge(values(adaptive.MIN_ROUNDS - 1, arm=200.0), "ref", "arm")
        self.assertEqual((settled, why), (False, "too few rounds"))

    def test_a_clear_loss_and_a_clear_win_settle_at_the_minimum(self):
        self.assertEqual(adaptive.judge(values(adaptive.MIN_ROUNDS, arm=150.0), "ref", "arm"), (True, "loss"))
        self.assertEqual(adaptive.judge(values(adaptive.MIN_ROUNDS, arm=60.0), "ref", "arm"), (True, "win"))

    def test_identical_arms_with_a_tight_floor_settle_as_no_measurable_difference(self):
        settled, why = adaptive.judge(values(10, spread=0.004, aa_spread=0.02), "ref", "arm")
        self.assertEqual((settled, why), (True, "no measurable difference"))

    def test_a_difference_inside_noisy_data_keeps_going(self):
        # a 3% difference under 20% run-to-run noise while the copies agree closely: not clear, and too wide to call inside the floor
        settled, why = adaptive.judge(values(8, arm=103.0, spread=0.2, aa_spread=0.002), "ref", "arm")
        self.assertFalse(settled, why)

    def test_when_the_copies_are_as_noisy_as_the_data_a_small_difference_is_inside_the_floor(self):
        self.assertEqual(adaptive.judge(values(8, arm=103.0, spread=0.2, aa_spread=0.2), "ref", "arm"), (True, "no measurable difference"))

    def test_an_arm_with_no_data_is_settled_with_nothing_to_learn(self):
        self.assertEqual(adaptive.judge({"ref": series(100, 8, 0.01, 1)}, "ref", "arm"), (True, "no data"))


def samples_for(v, scenario="overhead/print", api="a", metric="cpu_ms"):
    return [{"scenario": scenario, "api": api, "arm": arm, "round": r, "warmup": False, metric: val} for arm, rounds in v.items() for r, val in rounds.items()]


class Variant(unittest.TestCase):
    def test_a_variant_settles_when_every_arm_is_settled_and_reports_each_verdict(self):
        v = values(adaptive.MIN_ROUNDS, arm=150.0)
        done, verdicts, metric = adaptive.variant_status(samples_for(v), "overhead/print", "a", "ref", list(v))
        self.assertEqual((done, verdicts, metric), (True, {"arm": "loss"}, "cpu_ms"))

    def test_the_headline_metric_is_instructions_then_cpu_time_then_the_first_scored_one(self):
        self.assertEqual(adaptive.metric_of([{"instructions": 1, "cpu_ms": 2, "wall_ms": 3}]), "instructions")
        self.assertEqual(adaptive.metric_of([{"cpu_ms": 2, "wall_ms": 3}]), "cpu_ms")
        self.assertEqual(adaptive.metric_of([{"wall_ms": 3, "first_request_ms": 1}]), "first_request_ms")
        self.assertIsNone(adaptive.metric_of([{"turns": 3}, {"failure": "x", "cpu_ms": 1}]))

    def test_a_variant_with_nothing_scored_is_settled(self):
        self.assertEqual(adaptive.variant_status([{"scenario": "s", "api": None, "arm": "a", "round": 1, "warmup": False, "turns": 3}], "s", None, "ref", ["ref", "a"])[0], True)

    def test_without_a_reference_the_minimum_rounds_are_enough(self):
        v = {"solo": series(100, adaptive.MIN_ROUNDS, 0.01, 1)}
        self.assertEqual(adaptive.variant_status(samples_for(v), "overhead/print", "a", "ref", ["solo"])[0], True)
        v = {"solo": series(100, 3, 0.01, 1)}
        self.assertEqual(adaptive.variant_status(samples_for(v), "overhead/print", "a", "ref", ["solo"])[0], False)


class InTheLoop(unittest.TestCase):
    """The engine's round loop with synthetic samples: a clear variant leaves the loop early, an unclear one runs to the cap, and the raw record says which."""

    def run_loop(self, arm_value, adaptive_on=True, rounds=12, arms=1):
        import tempfile
        from types import SimpleNamespace
        from buffon.runner import engine
        wl = SimpleNamespace(id="overhead/print", special=None, apis=("a",), family="overhead")
        names = [("ref", None), ("ref-b", "ref")] + [x for i in range(arms) for x in ((f"arm{i}" if arms > 1 else "arm", None), (f"arm{i}-b" if arms > 1 else "arm-b", f"arm{i}" if arms > 1 else "arm"))]
        arms_ = [SimpleNamespace(id=i, twin_of=t) for i, t in names]
        plan = engine.Plan(workloads=[wl], arms=[], apis=["a"], apis_explicit=True, rounds=rounds, warmup=1, adaptive=adaptive_on, reference="ref", out=tempfile.mkdtemp())
        r = engine.Runner(plan, log=lambda *_: None)
        rng = random.Random(7)
        taken = []

        def one_sample(ctx, workload, api, arm, rnd):
            base = 100.0 if arm.id.startswith("ref") else arm_value
            taken.append((arm.id, rnd))
            return {"arm": arm.id, "scenario": workload.id, "api": api, "round": rnd, "warmup": rnd < 1, "cpu_ms": base * (1 + rng.uniform(-0.01, 0.01)), "wall_s": 0.0}, None
        r.one_sample = one_sample
        r.checkpoint = lambda force=False: None
        r.measure(None, arms_)
        return r, taken

    def test_a_clear_loss_stops_after_the_minimum_and_is_recorded(self):
        r, taken = self.run_loop(160.0)
        self.assertEqual(max(rnd for _, rnd in taken), adaptive.MIN_ROUNDS)   # the warm-up round plus six
        stop = r.adaptive_stops["overhead/print|a"]
        self.assertEqual((stop["rounds"], stop["verdicts"], stop["min_rounds"]), (adaptive.MIN_ROUNDS, {"arm": "loss"}, adaptive.MIN_ROUNDS))

    def test_eight_arms_stop_no_sooner_than_nine_rounds_and_the_record_says_so(self):
        r, taken = self.run_loop(160.0, arms=8)
        self.assertEqual(max(rnd for _, rnd in taken), 9)   # the warm-up round plus nine
        stop = r.adaptive_stops["overhead/print|a"]
        self.assertEqual((stop["rounds"], stop["min_rounds"]), (9, 9))
        self.assertEqual(r.adaptive_minimum, {"overhead/print|a": 9})

    def test_without_adaptive_every_round_is_taken(self):
        r, taken = self.run_loop(160.0, adaptive_on=False)
        self.assertEqual(max(rnd for _, rnd in taken), 12)
        self.assertEqual(r.adaptive_stops, {})

    def test_a_cell_that_never_clears_runs_to_the_cap(self):
        r, taken = self.run_loop(100.0, rounds=7)   # identical arms with the 1% copies spread: the interval is not inside a zero-width floor on every draw
        self.assertLessEqual(max(rnd for _, rnd in taken), 7)


if __name__ == "__main__":
    unittest.main()
