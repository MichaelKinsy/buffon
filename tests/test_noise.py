# SPDX-License-Identifier: Apache-2.0
"""Sample flags, outliers, drift, the per-run noise view, and dropping flagged rounds."""
import math
import unittest

from buffon.report import cells as cellmath
from buffon.report import noise, thresholds as T
from tests.telemetry_fixtures import clone, facts, quiet_telemetry, run


def sample_with(**over):
    cpu = over.pop("cpu_ms", 100.0)
    return {"arm": "a", "scenario": "s", "api": None, "round": 3, "warmup": False, "cpu_ms": cpu, "telemetry": {"system": quiet_telemetry(cpu, **over)}}


class Flags(unittest.TestCase):
    def test_a_quiet_sample_has_no_flag_and_one_without_telemetry_has_none_at_all(self):
        self.assertEqual(noise.flags(sample_with()), [])
        self.assertIsNone(noise.flags({"arm": "a", "scenario": "s", "round": 0, "warmup": False, "cpu_ms": 1.0}))

    def test_any_throttled_period_flags_the_sample_from_any_source(self):
        self.assertEqual(noise.flags(sample_with(cgroup={"throttled_periods": 0, "throttled_us": 9000})), [], "time without a throttled period is not throttling")
        self.assertEqual(noise.flags(sample_with(cgroup={"throttled_periods": 1})), ["throttled"])
        self.assertEqual(noise.flags(sample_with(cpuset={"session_throttled_periods": 1})), ["throttled"])
        self.assertEqual(noise.flags(sample_with(), ancestor_periods=1), ["throttled"])

    def test_foreign_busy_is_the_cpu_sets_busy_time_the_samples_own_cgroup_does_not_explain(self):
        # capacity = 2 CPUs x 500 ms = 1000 ms; 3% = 30 ms
        self.assertEqual(noise.flags(sample_with(cpuset={"cpuset_busy_ms": 100.0 + 25})), [])
        self.assertEqual(noise.flags(sample_with(cpuset={"cpuset_busy_ms": 100.0 + 60})), ["foreign_busy"])
        # a smaller share on a bigger window is still foreign when it exceeds the tick rounding and 3% of the capacity
        self.assertEqual(noise.flags(sample_with(window_ms=5000.0, cpuset={"cpuset_busy_ms": 100.0 + 400})), ["foreign_busy"])

    def test_tick_rounding_alone_is_not_foreign_busy(self):
        # a 30 ms sample on 8 CPUs: 3% of 240 ms is 7 ms, below the tick rounding of 2 ticks x sqrt(8)
        s = sample_with(cpu_ms=10.0, window_ms=30.0, cpus=8, cpuset={"cpuset_busy_ms": 10.0 + 20.0})
        self.assertEqual(noise.flags(s), [])

    def test_steal_clock_gate_swap_thermal_and_memory_events_flag_but_iowait_never_does(self):
        self.assertEqual(noise.flags(sample_with(cpuset={"cpuset_steal_ms": 2.1})), ["steal"])             # capacity 1000 ms: 0.1% is 1 ms
        self.assertEqual(noise.flags(sample_with(cpuset={"cpuset_steal_ms": 0.9})), [])
        self.assertEqual(noise.flags(sample_with(cpuset={"cpuset_iowait_ms": 900.0})), [], "iowait is recorded and never gated (R9: the kernel documents it as unreliable)")
        self.assertEqual(noise.flags(sample_with(during={"mhz_min": 2000.0, "mhz_max": 2200.0})), ["clock_moved"])     # 10%
        self.assertEqual(noise.flags(sample_with(during={"mhz_min": 2400.0, "mhz_max": 2500.0})), [])                  # 4.2%
        self.assertEqual(noise.flags(sample_with(gate={"status": "waited"})), ["gate_waited"])
        self.assertEqual(noise.flags(sample_with(cpuset={"swap_pages": 1})), ["swap"])
        self.assertEqual(noise.flags(sample_with(cpuset={"thermal_throttle_events": 1})), ["thermal"])
        self.assertEqual(noise.flags(sample_with(cgroup={"memory_events": {"oom_kill": 1}})), ["memory_events"])
        self.assertEqual(noise.flags(sample_with(cgroup={"memory_events": {"low": 5}})), [])

    def test_several_flags_come_in_the_published_order(self):
        f = noise.flags(sample_with(cpuset={"cpuset_steal_ms": 50.0, "swap_pages": 3}, cgroup={"throttled_periods": 2}))
        self.assertEqual(f, ["throttled", "steal", "swap"])
        self.assertEqual(f, sorted(f, key=noise.FLAG_ORDER.index))

    def test_a_sample_without_cgroup_totals_falls_back_to_its_cpu_metric(self):
        s = sample_with(cpuset={"cpuset_busy_ms": 100.0 + 90})
        del s["telemetry"]["system"]["cgroup"]
        self.assertEqual(noise.flags(s), ["foreign_busy"])


class Derive(unittest.TestCase):
    def anc(self, n, us=0, chain="app.slice"):
        return {"cgroup": {"ancestors": {"chain": chain, "nr_throttled": n, "throttled_us": us}}}

    def test_an_ancestors_throttling_counts_only_its_growth_since_the_previous_sample(self):
        a, b, c = (sample_with(**self.anc(n, n * 100)) for n in (5, 5, 9))
        d = noise.derive([a, b, c])
        self.assertEqual([x.throttled_periods for x in d], [0, 0, 4])      # the first sample of a chain has no baseline
        self.assertEqual([x.throttled_us for x in d], [0, 0, 400])
        self.assertEqual([x.flags for x in d], [[], [], ["throttled"]])

    def test_each_chain_keeps_its_own_baseline(self):
        a, b, c = sample_with(**self.anc(1, chain="x")), sample_with(**self.anc(100, chain="y")), sample_with(**self.anc(3, chain="x"))
        self.assertEqual([x.throttled_periods for x in noise.derive([a, b, c])], [0, 0, 2])

    def test_a_limited_chain_without_throttle_counters_does_not_break_the_baseline(self):
        s = sample_with()
        s["telemetry"]["system"]["cgroup"]["ancestors"] = {"limited": ["lane.slice"]}
        self.assertEqual(noise.derive([s])[0].flags, [])

    def test_failures_are_classified_as_infrastructure_or_arm(self):
        for failure, kind in (("exit 1: boom", "arm"), ("the host was not quiet within 300 s", "infra"), ("runner error: OSError()", "infra"), ("the pinned CPUs were not quiet within 300 s", "infra"),
                              ("no process was started", "infra"), ("timeout", "arm")):
            self.assertEqual(noise.failure_kind({"failure": failure}), kind, failure)
        self.assertEqual(noise.failure_kind({"failure": "killed", "quiet_gave_up": True}), "infra")
        oom = {"failure": "exit 137", "telemetry": {"system": {"cgroup": {"memory_events": {"oom_kill": 1}}}}}
        self.assertEqual(noise.failure_kind(oom), "infra")


class Statistics(unittest.TestCase):
    def test_outliers_use_the_mad_rule_and_need_four_values(self):
        self.assertEqual(noise.outliers([1, 2, 100]), [])
        base = [100.0, 101.0, 99.0, 100.5, 99.5, 100.2, 99.8, 100.0]          # with one more value: median 100, MAD 0.5, limit 5 x 1.4826 x 0.5 = 3.71
        self.assertEqual(noise.outliers(base + [103.5]), [])
        self.assertEqual(noise.outliers(base + [104.0]), [104.0])
        self.assertEqual(noise.outliers(base + [96.0]), [96.0])
        self.assertEqual(noise.outliers([5, 5, 5, 5, 6]), [6], "MAD 0: any different value lies outside")

    def test_the_mad_limit_scales_with_the_spread_and_the_constant_is_five_robust_sds(self):
        wide = [100.0, 110.0, 90.0, 105.0, 95.0, 102.0, 98.0, 100.0]          # with one more value: MAD 5, limit 37.07
        self.assertEqual(noise.outliers(wide + [137.0]), [])
        self.assertEqual(noise.outliers(wide + [138.0]), [138.0])

    def test_theil_sen_is_robust_to_one_wild_value(self):
        xs = list(range(10))
        ys = [100 + 2 * x for x in xs]
        ys[4] = 5000
        self.assertEqual(noise.theil_sen([float(x) for x in xs], ys), 2.0)
        self.assertTrue(math.isnan(noise.theil_sen([1.0], [1.0])))

    def test_drift_is_the_trend_over_the_run_as_a_share_of_the_median(self):
        up = {r: 100.0 + r for r in range(11)}              # +10 over 10 rounds around a median of 105
        self.assertAlmostEqual(noise.drift(up), 10 / 105, places=6)
        self.assertEqual(noise.drift({r: 50.0 for r in range(8)}), 0.0)
        self.assertTrue(math.isnan(noise.drift({0: 1.0, 1: 2.0})))


class RunView(unittest.TestCase):
    def view(self, raw):
        return noise.run_view(raw, facts(), 1)

    def test_a_clean_run_has_no_flags_and_counts_its_samples(self):
        v = self.view(run())
        self.assertEqual(v["samples"], {"measured": 48, "ok": 48, "failed": 0, "warmup": 4, "with_telemetry": 48, "infra_failed": 0, "arm_failed": 0, "stopped": 0})
        self.assertEqual((v["flagged_samples"], v["throttled_samples"]), (0, 0))
        self.assertEqual(v["gate"]["passed"], 48)
        self.assertEqual(v["collector_cpu_ms_median"], 1.6)    # sampler thread 0.9 + begin 0.3 + end 0.4: the whole cost of the observer
        self.assertIn("proc_stat", v["sources"])

    def test_throttled_and_flagged_samples_are_listed_with_where_they_were(self):
        def mutate(s):
            if s["arm"] == "other" and s["round"] == 5:
                s["telemetry"]["system"]["cgroup"]["throttled_us"] = 4000
                s["telemetry"]["system"]["cgroup"]["throttled_periods"] = 3
        v = self.view(run(mutate=mutate))
        self.assertEqual((v["flagged_samples"], v["throttled_samples"], v["throttled_us_total"]), (1, 1, 4000))
        self.assertEqual(v["throttle_events"], [{"arm": "other", "scenario": "overhead/print", "api": "openai-completions", "round": 5, "throttled_us": 4000, "periods": 3}])
        self.assertEqual(v["flagged_rounds"], [["overhead/print", "openai-completions", 5]])

    def test_the_gate_counts_passed_waited_and_gave_up(self):
        def mutate(s):
            if s["arm"] == "other" and s["round"] == 2:
                s["telemetry"]["system"]["gate"] = {"status": "waited", "waited_ms": 7000, "checks": 8}
            if s["arm"] == "other" and s["round"] == 3:
                for k in ("telemetry", "cpu_ms", "wall_ms"):
                    s.pop(k)
                s.update({"failure": "the host was not quiet within 300 s", "quiet_gave_up": True})
        v = self.view(run(mutate=mutate))
        self.assertEqual((v["gate"]["waited"], v["gate"]["gave_up"], v["gate"]["waited_ms_max"]), (1, 1, 7000))
        self.assertEqual(v["samples"]["failed"], 1)

    def test_failures_are_grouped_by_reason_in_the_discard_table(self):
        def mutate(s):
            if s["arm"] == "other" and s["round"] in (4, 6) and not s["warmup"]:
                s.pop("telemetry")
                s["failure"] = "exit 1: boom"
        raw = run(mutate=mutate)
        rows = noise.discarded([self.view(raw)])
        self.assertEqual(rows[0][1:], (4, 1))
        self.assertTrue(rows[0][0].startswith("warm-up round"))
        self.assertEqual(rows[1], ("failed sample: exit 1", 2, 2))

    def test_a_run_without_telemetry_says_so_instead_of_inventing_zeros(self):
        v = self.view(run(telemetry=False))
        self.assertEqual(v["samples"]["with_telemetry"], 0)
        self.assertEqual(v["flagged_samples"], 0)
        self.assertEqual(v["sources"], [])
        self.assertTrue(math.isnan(v["collector_cpu_ms_median"]))


class DropFlagged(unittest.TestCase):
    def flagged(self):
        def mutate(s):
            if s["arm"] == "other-b" and s["round"] == 7:
                s["telemetry"]["system"]["cpuset"]["cpuset_steal_ms"] = 80.0
        return run(mutate=mutate)

    def test_a_flagged_round_goes_for_every_arm_and_warm_up_stays(self):
        raw = self.flagged()
        used, dropped = noise.drop_flagged([raw])
        self.assertEqual(dropped, [(1, "overhead/print", "openai-completions", 7, ["steal"])])
        self.assertEqual(len(used[0]["samples"]), len(raw["samples"]) - 4)
        self.assertFalse([s for s in used[0]["samples"] if s["round"] == 7])
        self.assertEqual(len(raw["samples"]), 52, "the input is not modified")

    def test_the_cells_are_built_from_the_remaining_rounds(self):
        raw = self.flagged()
        used, _ = noise.drop_flagged([raw])
        cells = cellmath.build(used)
        self.assertEqual(sorted(cells["cells"][0].values["pi-node"]), [(0, r) for r in range(1, 13) if r != 7])

    def test_sensitivity_reports_how_many_verdicts_change(self):
        raw = self.flagged()
        data = cellmath.build([raw])
        s = noise.sensitivity([raw], data)
        self.assertEqual((s["rounds_dropped"], s["comparisons"]), (1, 2))
        self.assertEqual(s["verdict_changes"], 0)
        self.assertIsNone(noise.sensitivity([run()], cellmath.build([run()])))

    def test_a_round_that_flips_a_verdict_is_reported(self):
        # 'other' and its copy equal the reference except in 7 rounds where a flagged burst (steal) made them slow: the full run calls it a loss, without those rounds it is a tie
        def mutate(s):
            if s["arm"].startswith("other") and 3 <= s["round"] <= 9:
                s["cpu_ms"] = 400.0
            if s["arm"] == "other" and 3 <= s["round"] <= 9:
                s["telemetry"]["system"]["cpuset"]["cpuset_steal_ms"] = 80.0
        raw = run(arm=100.0, mutate=mutate)
        data = cellmath.build([raw])
        s = noise.sensitivity([raw], data)
        self.assertEqual(s["rounds_dropped"], 7)
        self.assertGreaterEqual(s["verdict_changes"], 1)
        self.assertEqual(s["changes"][0]["metric"], "cpu_ms")


class PerMetric(unittest.TestCase):
    def test_per_metric_rows_and_the_comparison_columns(self):
        raw = run()
        data = cellmath.build([raw])
        rows = {r["metric"]: r for r in noise.by_metric(data)}
        self.assertEqual(set(rows), {"cpu_ms", "wall_ms"})
        self.assertEqual(rows["cpu_ms"]["cells"], 1)
        self.assertLess(rows["cpu_ms"]["aa_gap_median"], 0.01)
        self.assertEqual(rows["cpu_ms"]["values"], 48)
        cv, iqr, outl = noise.cell_columns(data["cells"][0], "pi-node", "other")
        self.assertRegex(cv, r"^\d\.\d% / \d\.\d%$")
        self.assertRegex(iqr, r"^[\d.]+ / [\d.]+$")
        self.assertEqual(outl, "0 / 0")
        self.assertEqual(noise.aa_gap(data["cells"][0], "other") < 0.01, True)


if __name__ == "__main__":
    unittest.main()
