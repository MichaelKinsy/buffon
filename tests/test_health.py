# SPDX-License-Identifier: Apache-2.0
"""The run notes: each usual range at its boundary (a value above it is a note, never a grade), and that docs/HEALTH.md is the generated table."""
import json
import math
import os
import unittest

from buffon.report import cells as cellmath
from buffon.report import health, noise, thresholds as T
from tests.telemetry_fixtures import facts, run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def assess(*raws, fx=None, **kw):
    raws = list(raws)
    f = fx or facts()
    data = cellmath.build(raws)
    n = noise.build(raws, [f] * len(raws), data)
    return health.assess(raws, [f] * len(raws), data, n)


def status(h, cid):
    return next(c["status"] for c in h["checks"] if c["id"] == cid)


def value(h, cid):
    return next(c["value"] for c in h["checks"] if c["id"] == cid)


def first(n, arm="other", **where):
    """A mutator that applies `edit(sample)` to the first n measured samples of `arm`."""
    seen = []

    def deco(edit):
        def mutate(s):
            if not s["warmup"] and s["arm"] == arm and len(seen) < n:
                seen.append(1)
                edit(s)
        return mutate
    return deco


def tel(s):
    return s["telemetry"]["system"]


class Notes(unittest.TestCase):
    def test_a_clean_quiet_run_has_no_notes(self):
        h = assess(run())
        self.assertEqual((h["notes"], h["summary"]), (0, "no notes"), [c for c in h["checks"] if c["status"] != "ok"])
        self.assertTrue(all(c["status"] == "ok" for c in h["checks"]))
        self.assertEqual(h["thresholds_sha256"], T.SHA256)

    def test_there_is_no_verdict_and_no_grade_word_anywhere_in_the_document(self):
        h = assess(run(quiet=False, calibration_cv=0.2))
        self.assertNotIn("verdict", h)
        self.assertEqual({c["status"] for c in h["checks"]}, {"ok", "note"})
        text = json.dumps(h) + "\n".join(health.lines(h)) + health.thresholds_markdown()
        for word in ("GREEN", "YELLOW", "RED", "red", "yellow"):
            self.assertNotRegex(text, rf"\b{word}\b")

    def test_every_check_has_a_one_line_plain_meaning(self):
        for c in assess(run())["checks"]:
            self.assertTrue(c["meaning"].endswith("."), c["id"])
            self.assertNotIn("\n", c["meaning"])
            self.assertNotIn("\u2014", c["meaning"], "no em dash")

    def test_the_summary_counts_the_notes_and_lists_them_before_the_checks_without_one(self):
        h = assess(run(quiet=False, calibration_cv=0.03))
        self.assertEqual(h["notes"], 2)
        self.assertEqual(h["summary"], "2 notes: calibration_cv 3.0%, hardware")
        self.assertEqual([c["status"] for c in h["checks"]], ["note"] * 2 + ["ok"] * (len(h["checks"]) - 2))
        rows = [r for r in health.lines(h) if r.startswith("| ")][1:]
        self.assertIn("| note |", rows[0])
        self.assertIn("| note |", rows[1])
        self.assertIn("| ok |", rows[2])

    def test_a_provisional_run_has_a_hardware_note_and_nothing_else(self):
        h = assess(run(quiet=False))
        self.assertEqual((h["notes"], status(h, "hardware")), (1, "note"))

    def test_calibration_cv_boundaries(self):
        self.assertEqual(status(assess(run(calibration_cv=0.02)), "calibration_cv"), "ok")
        self.assertEqual(status(assess(run(calibration_cv=0.0201)), "calibration_cv"), "note")
        self.assertEqual(status(assess(run(calibration_cv=0.05)), "calibration_cv"), "note")
        h = assess(run(calibration_cv=0.0501))
        self.assertEqual((status(h, "calibration_cv"), status(h, "calibration_ran")), ("note", "note"))

    def test_the_a_a_cv_of_cpu_metrics_is_two_and_five_percent(self):
        def wobble(amp):
            def mutate(s):
                if not s["warmup"] and s["arm"].endswith("-b") and s["arm"].startswith("pi"):
                    s["cpu_ms"] += amp * (-1) ** s["round"]
            return mutate
        self.assertEqual(status(assess(run(mutate=wobble(0))), "aa_cv_cpu"), "ok")
        # the CV of a series alternating +-x around 100 is about x/100 * sqrt(n/(n-1)); the median over the four pairs' arms (two quiet, two noisy) sits between
        h = assess(run(mutate=wobble(4)))
        self.assertLess(value(h, "aa_cv_cpu"), 0.02)
        noisy = assess(run(arm=100.0, mutate=lambda s: (wobble(5)(s) if True else None) or (s.update(cpu_ms=s["cpu_ms"] + 5 * (-1) ** s["round"]) if (s["arm"] == "other-b" and not s["warmup"]) else None)))
        self.assertGreater(value(noisy, "aa_cv_cpu"), 0.0)

    def test_aa_cv_boundaries_are_strictly_above(self):
        self.assertEqual(health._status(0.02, 0.02), "ok")
        self.assertEqual(health._status(0.0201, 0.02), "note")

    def test_more_than_five_percent_of_a_a_pairs_looking_different_is_a_note(self):
        def shift(s):
            if s["arm"] == "pi-node-b" and not s["warmup"]:
                s["cpu_ms"] *= 1.03          # 1 of 4 A/A pairs (2 arms x 2 metrics) now differs from its arm in every round
        h = assess(run(mutate=shift))
        self.assertEqual((value(h, "aa_significant_fraction"), status(h, "aa_significant_fraction")), (0.25, "note"))
        self.assertEqual(value(assess(run()), "aa_significant_fraction"), 0.0)

    def test_the_a_a_gap_is_reported_with_its_cell_and_a_sub_one_percent_gap_is_no_note(self):
        def shift(factor):
            def mutate(s):
                if s["arm"] == "pi-node-b" and not s["warmup"]:
                    s["cpu_ms"] *= factor
            return mutate
        small = assess(run(mutate=shift(1.009)))
        self.assertEqual((value(small, "aa_significant_fraction"), status(small, "aa_significant_fraction")), (0.0, "ok"))
        self.assertAlmostEqual(value(small, "aa_gap_max"), 0.009, places=3)
        self.assertEqual(status(small, "aa_gap_max"), "ok")
        big = assess(run(mutate=shift(1.08)))
        self.assertEqual((status(big, "aa_gap_max"), status(big, "aa_gap_median")), ("note", "ok"))
        detail = next(c["detail"] for c in big["checks"] if c["id"] == "aa_gap_max")
        self.assertIn("overhead/print", detail)
        self.assertIn("cpu_ms pi-node: 8.0%", detail, "the cell and the harness of the largest gap")
        self.assertIn("A pair counts as different only when its gap is significant and also larger than 1%.", "\n".join(health.lines(big)))

    def test_any_cfs_throttling_of_a_measured_sample_is_a_note(self):
        h = assess(run(mutate=first(1)(lambda s: tel(s)["cgroup"].update(throttled_periods=1, throttled_us=300))))
        self.assertEqual((value(h, "throttled_samples"), status(h, "throttled_samples")), (1, "note"))
        h = assess(run(mutate=first(1)(lambda s: tel(s)["cpuset"].update(session_throttled_periods=2))))
        self.assertEqual(status(h, "throttled_samples"), "note")
        h = assess(run(mutate=first(1)(lambda s: tel(s)["cgroup"].update(throttled_periods=0, throttled_us=900000))))
        self.assertEqual(status(h, "throttled_samples"), "ok", "only a throttled period counts")

    def test_an_ancestors_throttling_is_read_from_its_cumulative_counter(self):
        def ancestor(s):
            tel(s)["cgroup"]["ancestors"] = {"chain": "app.slice", "nr_throttled": 10 + (s["round"] >= 6) * 3, "throttled_us": 1000}
        h = assess(run(mutate=lambda s: ancestor(s) if s["arm"] == "other" else None))
        self.assertEqual(status(h, "throttled_samples"), "note")
        self.assertEqual(value(h, "throttled_samples"), 1, "the growth is charged to the first sample after it")

    def test_steal_above_a_tenth_of_a_percent_is_a_note(self):
        def steal(ms):
            return first(8)(lambda s: tel(s)["cpuset"].update(cpuset_steal_ms=ms))
        self.assertEqual(status(assess(run(mutate=steal(0.0))), "steal_share"), "ok")
        h = assess(run(mutate=first(1)(lambda s: tel(s)["cpuset"].update(cpuset_steal_ms=60.0))))      # 60 ms of 48,000 ms = 0.125%
        self.assertEqual(status(h, "steal_share"), "note")
        self.assertEqual(status(assess(run(mutate=steal(60.0))), "steal_share"), "note")              # 480 ms = exactly 1%

    def test_iowait_is_recorded_and_never_gated(self):
        h = assess(run(mutate=lambda s: tel(s)["cpuset"].update(cpuset_iowait_ms=900.0)))
        self.assertEqual(h["notes"], 0)

    def test_foreign_cpu_is_judged_by_its_p95_against_the_samples_own_cpu_time(self):
        # the 'other' arm's own CPU is 150 ms; the tick allowance on 2 CPUs is 2 x 10 ms x sqrt(2) = 28.3 ms; foreign share = extra / 150
        def extra(ms):
            return first(4)(lambda s: tel(s)["cpuset"].update(cpuset_busy_ms=tel(s)["cgroup"]["cpu_usage_ms"] + 28.3 + ms))
        self.assertEqual(status(assess(run(mutate=extra(0.5))), "foreign_cpu_p95"), "ok")
        self.assertEqual(status(assess(run(mutate=extra(3.0))), "foreign_cpu_p95"), "note")
        self.assertEqual(status(assess(run(mutate=extra(9.0))), "foreign_cpu_p95"), "note")
        self.assertEqual(status(assess(run(mutate=first(2)(lambda s: tel(s)["cpuset"].update(cpuset_busy_ms=tel(s)["cgroup"]["cpu_usage_ms"] + 28.3 + 9.0)))), "foreign_cpu_p95"), "ok", "p95 ignores the two worst of 48")

    def test_the_quiet_gate_counts_slow_waits_and_a_sample_it_gave_up_on(self):
        def slow(n):
            return first(n)(lambda s: tel(s)["gate"].update(status="waited", waited_ms=2500, checks=4))
        self.assertEqual(status(assess(run(mutate=slow(0))), "gate_slow_fraction"), "ok")
        self.assertEqual(status(assess(run(mutate=slow(1))), "gate_slow_fraction"), "note")      # 1 of 48 = 2.1%
        self.assertEqual(status(assess(run(mutate=slow(3))), "gate_slow_fraction"), "note")         # 6.25%
        self.assertEqual(status(assess(run(mutate=first(3)(lambda s: tel(s)["gate"].update(status="waited", waited_ms=900, checks=2)))), "gate_slow_fraction"), "ok", "a wait of one second or less is not slow")

        def gave_up(s):
            for k in ("telemetry", "cpu_ms", "wall_ms"):
                s.pop(k)
            s.update({"failure": "the host was not quiet", "quiet_gave_up": True})
        h = assess(run(mutate=first(1)(gave_up)))
        self.assertEqual(status(h, "gate_gave_up"), "note")

    def test_the_clock_must_stay_within_two_and_five_percent_of_the_run_median(self):
        def clock(f):
            return first(1)(lambda s: tel(s)["during"].update(mhz_mean=2400.0 * f))
        self.assertEqual(status(assess(run(mutate=clock(1.015))), "clock_deviation"), "ok")
        self.assertEqual(status(assess(run(mutate=clock(1.03))), "clock_deviation"), "note")
        self.assertEqual(status(assess(run(mutate=clock(0.94))), "clock_deviation"), "note")

    def test_a_clock_the_machine_does_not_report_is_a_note_not_silently_fine(self):
        def drop(s):
            for k in ("mhz_mean", "mhz_min", "mhz_max"):
                tel(s)["during"].pop(k)
        h = assess(run(mutate=drop))
        self.assertEqual(status(h, "clock_deviation"), "note")
        self.assertIn("not measured", next(c["detail"] for c in h["checks"] if c["id"] == "clock_deviation"))

    def test_infrastructure_failures_are_separate_from_arm_failures(self):
        def fail(kind):
            def edit(s):
                for k in ("telemetry", "cpu_ms", "wall_ms"):
                    s.pop(k)
                s["failure"] = "runner error: OSError()" if kind == "infra" else "exit 1: boom"
            return edit
        h = assess(run(mutate=first(1)(fail("infra"))))
        self.assertEqual((status(h, "infra_failed_fraction"), value(h, "arm_failed_fraction")), ("note", 0.0))     # 1 of 48 = 2.1% > 0%
        self.assertEqual(status(assess(run(rounds=26, mutate=first(1)(fail("infra")))), "infra_failed_fraction"), "note")   # 1 of 104 = 0.96%
        self.assertEqual(status(assess(run(mutate=first(1)(fail("arm")))), "infra_failed_fraction"), "ok")
        h = assess(run(mutate=first(1)(fail("arm"))))
        self.assertEqual((status(h, "arm_failed_fraction"), value(h, "infra_failed_fraction")), ("note", 0.0))   # 2.1% > 2%
        self.assertEqual(status(assess(run(mutate=first(6)(fail("arm")))), "arm_failed_fraction"), "note")

    def test_a_scale_ladder_stop_is_a_result_and_an_error_stop_is_still_a_failure(self):
        def stop(cause):
            def edit(s):
                for k in ("telemetry", "cpu_ms", "wall_ms"):
                    s.pop(k)
                s["failure"] = "3 of 16 agents did not answer a prompt; out of memory"
                s["stop_cause"] = cause
            return edit
        for cause in ("oom", "pids", "timeout"):
            h = assess(run(mutate=first(6)(stop(cause))))            # 6 of 48 samples
            self.assertEqual((status(h, "arm_failed_fraction"), value(h, "arm_failed_fraction"), value(h, "infra_failed_fraction")), ("ok", 0.0, 0.0), cause)
            self.assertEqual(noise.failure_kind({"failure": "x", "stop_cause": cause}), "stop")
        h = assess(run(mutate=first(6)(stop("error"))))
        self.assertEqual(status(h, "arm_failed_fraction"), "note")                                  # an error stop is a failure
        self.assertAlmostEqual(value(h, "arm_failed_fraction"), 6 / 48)

    def test_the_failure_fractions_leave_stopped_samples_out_of_their_denominator_and_the_view_counts_them(self):
        def mixed(s):
            for k in ("telemetry", "cpu_ms", "wall_ms"):
                s.pop(k)
            s["failure"], s["stop_cause"] = ("exit 1: boom", None) if s["round"] % 2 else ("out of memory", "oom")
            if s["stop_cause"] is None:
                del s["stop_cause"]
        raw = run(mutate=first(4)(mixed))
        view = noise.build([raw], [facts()], cellmath.build([raw]))["views"][0]
        self.assertEqual((view["samples"]["stopped"], view["samples"]["arm_failed"]), (2, 2))
        h = assess(raw)
        self.assertAlmostEqual(value(h, "arm_failed_fraction"), 2 / (48 - 2))

    def test_the_arm_failed_check_says_a_scale_stop_is_a_result(self):
        self.assertIn("a result and is in neither the failures", " ".join(m for _id, _t, _u, _us, m in T.HEALTH if _id == "arm_failed_fraction"))

    def test_the_boundary_is_strictly_above_the_usual_range_and_a_missing_value_is_ok(self):
        self.assertEqual(health._status(0.05, 0.05), "ok")
        self.assertEqual(health._status(0.0500001, 0.05), "note")
        self.assertEqual(health._status(0, 0), "ok")
        self.assertEqual(health._status(1, 0), "note")
        self.assertEqual(health._status(math.nan, 0.1), "ok")
        self.assertEqual(health._status(None, 0.1), "ok")

    def test_a_run_without_telemetry_has_notes_because_its_noise_is_unknown(self):
        h = assess(run(telemetry=False))
        self.assertEqual((status(h, "telemetry"), status(h, "flagged_fraction"), status(h, "steal_share")), ("note", "note", "note"))

    def test_flagged_samples_above_five_percent_are_a_note(self):
        def flag(n):
            return first(n, "other-b")(lambda s: tel(s)["cpuset"].update(cpuset_steal_ms=2.0))
        self.assertEqual(status(assess(run(mutate=flag(2))), "flagged_fraction"), "ok")        # 2 of 48 = 4.2%
        self.assertEqual(status(assess(run(mutate=flag(4))), "flagged_fraction"), "note")       # 8.3%

    def test_a_cpu_quota_on_the_arm_cgroup_or_an_ancestor_is_a_note(self):
        h = assess(run(mutate=first(1)(lambda s: tel(s)["cgroup"].update(ancestors={"limited": ["lane.slice/lane.scope"]}))))
        self.assertEqual(status(h, "cpu_quota"), "note")
        self.assertIn("lane.slice/lane.scope", next(c["detail"] for c in h["checks"] if c["id"] == "cpu_quota"))

    def test_without_a_cgroup_meter_the_sessions_own_limits_apply(self):
        raw = run(telemetry=True)
        raw["run"]["telemetry"] = {"system": {"start": {"quota_limited": ["session.scope"]}, "end": {}}}
        self.assertEqual(status(assess(raw), "cpu_quota"), "ok", "the samples' cgroup meter is outside the session's limits")

        def rusage(s):
            tel(s)["cgroup"] = {"mode": "rusage", "cpu_usage_ms": s["cpu_ms"]}
        raw = run(mutate=rusage)
        raw["run"]["telemetry"] = {"system": {"start": {"quota_limited": ["session.scope"]}, "end": {}}}
        self.assertEqual(status(assess(raw), "cpu_quota"), "note")

    def test_a_container_sample_has_its_own_cgroup_so_the_sessions_limits_do_not_apply(self):
        def container(s):
            tel(s)["cgroup"] = {"mode": "container", "cpu_usage_ms": s["cpu_ms"], "throttled_periods": 0, "throttled_us": 0}
        raw = run(mutate=container)
        raw["run"]["telemetry"] = {"system": {"start": {"quota_limited": ["session.scope"]}, "end": {}}}
        self.assertEqual(status(assess(raw), "cpu_quota"), "ok")
        self.assertEqual(status(assess(raw), "throttled_samples"), "ok")

        def throttled(s):
            tel(s)["cgroup"] = {"mode": "container", "cpu_usage_ms": s["cpu_ms"], "throttled_periods": 3, "throttled_us": 900}
        self.assertEqual(status(assess(run(mutate=first(1)(throttled))), "throttled_samples"), "note")        # the container's own CPU limit showing

    def test_a_scaling_clock_policy_is_a_note(self):
        fx = dict(facts(), fixed_clock=False)
        self.assertEqual(status(assess(run(), fx=fx), "clock_policy"), "note")
        self.assertEqual(status(assess(run(), fx=dict(facts(), fixed_clock=None)), "clock_policy"), "ok")

    def test_a_step_in_the_reference_series_is_a_note(self):
        def step(s):
            if s["arm"].startswith("pi-node") and s["round"] >= 7:
                s["cpu_ms"] *= 1.10
                s["wall_ms"] *= 1.10
        h = assess(run(mutate=step))
        c = next(c for c in h["checks"] if c["id"] == "reference_changepoint")
        self.assertEqual(c["status"], "note")
        self.assertIn("from round 7", c["detail"])

    def test_a_step_inside_a_wide_floor_is_a_note_too(self):
        def mutate(s):
            if s["arm"] == "pi-node-b" and not s["warmup"]:
                s["cpu_ms"] += 15.0 * (-1) ** s["round"]
                s["wall_ms"] += 60.0 * (-1) ** s["round"]
            if s["arm"] == "pi-node" and s["round"] >= 7:
                s["cpu_ms"] *= 1.06
                s["wall_ms"] *= 1.06
        c = next(c for c in assess(run(mutate=mutate))["checks"] if c["id"] == "reference_changepoint")
        self.assertEqual(c["status"], "note")

    def test_a_stationary_reference_has_no_change_point_and_a_short_run_is_not_tested(self):
        self.assertEqual(status(assess(run()), "reference_changepoint"), "ok")
        c = next(c for c in assess(run(rounds=4))["checks"] if c["id"] == "reference_changepoint")
        self.assertEqual(c["status"], "ok")
        self.assertIn("too few rounds", c["detail"])

    def test_fewer_than_twelve_rounds_a_missing_copy_egress_and_integrity(self):
        h = assess(run(rounds=11))
        self.assertEqual(status(h, "rounds"), "note")
        raw = run()
        raw["samples"] = [s for s in raw["samples"] if s["arm"] != "other-b"]
        self.assertEqual(status(assess(raw), "aa_copies"), "note")
        raw = run()
        raw["egress"]["violations"] = [{"arm": "other", "scenario": "overhead/print", "remotes": ["203.0.113.5"]}]
        self.assertEqual(status(assess(raw), "egress"), "note")
        raw = run()
        raw["ok"] = False
        self.assertEqual(status(assess(raw), "integrity"), "note")

    def test_drift_over_the_run_is_found(self):
        def mutate(s):
            if not s["warmup"]:
                f = 1 + 0.05 * s["round"] / 12
                s["cpu_ms"] *= f
                s["wall_ms"] *= f
        h = assess(run(mutate=mutate))
        self.assertEqual(status(h, "drift"), "note")      # about +4.6% over the run
        self.assertGreater(value(h, "drift"), 0.02)

    def test_the_outlier_rule_is_five_robust_deviations(self):
        def spike(s):
            if s["arm"] == "other" and s["round"] in (3, 7, 9):
                s["cpu_ms"] += 40.0
        h = assess(run(mutate=spike))
        self.assertEqual(status(h, "outlier_fraction"), "note")      # 3 of 12 values of one arm in one cell: 3 / 96 = 3.1%
        self.assertGreater(value(h, "outlier_fraction"), 0.02)

    def test_two_runs_pool_and_name_the_failing_run(self):
        h = assess(run(), run(rounds=11))
        self.assertEqual(status(h, "rounds"), "note")
        self.assertIn("run 2", next(c["detail"] for c in h["checks"] if c["id"] == "rounds"))

    def test_the_notes_are_a_pure_function_of_the_data(self):
        a, b = assess(run()), assess(run())
        self.assertEqual(a, b)


class Published(unittest.TestCase):
    def test_every_threshold_check_is_in_the_published_table_and_in_the_report(self):
        h = assess(run())
        self.assertEqual([c["id"] for c in h["checks"]], [t[0] for t in T.HEALTH] + [c[0] for c in T.CHECKS])
        self.assertEqual(len(set(c["id"] for c in h["checks"])), len(h["checks"]))
        text = "\n".join(health.lines(h))
        for t in T.HEALTH:
            self.assertIn(t[1], text)

    def test_docs_health_md_contains_the_generated_tables(self):
        with open(os.path.join(ROOT, "docs", "HEALTH.md")) as f:
            doc = f.read()
        self.assertIn(health.thresholds_markdown(), doc, "regenerate with: python3 -m buffon health thresholds")


if __name__ == "__main__":
    unittest.main()
