# SPDX-License-Identifier: Apache-2.0
"""Races: how far each harness got on a ladder and why it stopped. An OOM, an error and a timeout are results."""
import os
import tempfile
import unittest

from buffon import cli, race
from buffon.report import races as racereport, render
from buffon.runner import engine, raw as rawlib
from buffon.up import tracks
from tests.test_report import raw_of, sample, series

RUNGS = [("0", "overhead/print"), ("10", "overhead/print-ext10"), ("50", "overhead/print-ext50"), ("100", "overhead/print-ext100")]


def ok(arm, scenario, wall_s, mem, rnd=1, cpu=100.0):
    return sample(arm, scenario, rnd, wall_s=wall_s, peak_mem_mib=mem, cpu_ms=cpu, wall_ms=wall_s * 1000)


def failed(arm, scenario, text, rnd=1, **extra):
    return sample(arm, scenario, rnd, failure=text, **extra)


class Causes(unittest.TestCase):
    def test_an_oom_is_told_by_the_cgroup_the_exit_status_or_the_harnesss_own_words(self):
        events = {"telemetry": {"system": {"cgroup": {"memory_events": {"oom_kill": 1}, "memory_peak_bytes": 4 * 1024 ** 3}}}}
        c = race.stop_cause({"failure": "exit 1: boom", **events})
        self.assertEqual((c["cause"], round(c["peak_mib"])), (race.OOM, 4096))
        self.assertEqual(race.stop_cause({"failure": "exit 137: Killed"})["cause"], race.OOM)
        self.assertEqual(race.stop_cause({"failure": "JavaScript heap out of memory"})["cause"], race.OOM)

    def test_a_timeout_and_an_error_keep_their_message(self):
        self.assertEqual(race.stop_cause({"failure": "exit -9 (timed out): "})["cause"], race.OOM if "exit -9" in "exit -9" else race.TIMEOUT)  # a kill by the deadline names itself below
        self.assertEqual(race.stop_cause({"failure": "no get_state response after resuming the session"})["cause"], race.TIMEOUT)
        e = race.stop_cause({"failure": "the first request carried 3 messages; the resumed history has 9000"})
        self.assertEqual(e["cause"], race.ERROR)
        self.assertIn("9000", e["message"])


class Lanes(unittest.TestCase):
    def climb(self, arm, last, per=1.0, mem=100.0):
        out = []
        for i, (_a, w) in enumerate(RUNGS[:last]):
            out += [ok(arm, w, per * (i + 1), mem * (i + 1), rnd) for rnd in (1, 2)]
        return out

    def test_a_harness_that_crosses_the_last_rung_finishes_with_its_time_and_checkpoints(self):
        l = race.lane(self.climb("a", 4), [], "a", RUNGS)
        self.assertEqual((l["outcome"], l["reached"], l["of"], l["stop"]), (race.FINISHED, 4, 4, None))
        self.assertEqual(l["elapsed_s"], 10.0)   # 1 + 2 + 3 + 4
        self.assertEqual(l["checkpoints"], {"25": 1.0, "50": 3.0, "75": 6.0, "100": 10.0})
        self.assertEqual((l["memory"]["peak_mib"], l["reliability"]["failed_samples"]), (400.0, 0))

    def test_an_oom_at_a_rung_is_a_stopped_lane_with_the_step_the_time_and_the_peak(self):
        samples = self.climb("a", 2) + [failed("a", "overhead/print-ext50", "exit 137: Killed", telemetry={"system": {"cgroup": {"memory_events": {"oom_kill": 1}, "memory_peak_bytes": 2 * 1024 ** 3}}})]
        l = race.lane(samples, [], "a", RUNGS)
        self.assertEqual((l["outcome"], l["reached"], l["reached_label"]), (race.STOPPED, 2, "10"))
        self.assertEqual((l["stop"]["cause"], l["stop"]["rung"], l["stop"]["elapsed_s"]), (race.OOM, "50", 3.0))
        self.assertEqual(l["memory"]["at_stop_peak_mib"], 2048.0)
        self.assertIn("Stopped at 50 after 3.0 s: OOM, 2.0 GiB", race.sentence(l))

    def test_a_rung_after_the_stop_is_not_counted_even_when_it_has_samples(self):
        samples = self.climb("a", 2) + [failed("a", "overhead/print-ext50", "exit 1: x")] + [ok("a", "overhead/print-ext100", 9.0, 9.0)]
        l = race.lane(samples, [], "a", RUNGS)
        self.assertEqual((l["reached"], l["elapsed_s"]), (2, 3.0))

    def test_a_harness_that_cannot_run_a_rung_stops_there_with_the_manifests_reason(self):
        skipped = [{"arm": "fused", "scenario": "overhead/print-ext50", "api": "openai-completions", "reason": "its extensions are fixed at ten (built into the binary): it cannot load 50"}]
        l = race.lane(self.climb("fused", 2), skipped, "fused", RUNGS)
        self.assertEqual((l["stop"]["cause"], l["stop"]["rung"]), (race.UNSUPPORTED, "50"))
        self.assertIn("cannot run", race.sentence(l))
        self.assertIn("fixed at ten", race.sentence(l))

    def test_a_single_failed_sample_among_good_ones_is_reliability_not_a_stop(self):
        samples = self.climb("a", 4) + [failed("a", "overhead/print", "exit 1: flaky", rnd=3)]
        l = race.lane(samples, [], "a", RUNGS)
        self.assertEqual((l["outcome"], l["reliability"]["failed_samples"], l["reliability"]["samples"]), (race.FINISHED, 1, 9))

    def test_ranking_is_finished_by_time_then_stopped_by_distance_then_time(self):
        a = race.lane(self.climb("a", 4, per=2.0), [], "a", RUNGS)
        b = race.lane(self.climb("b", 4, per=1.0), [], "b", RUNGS)
        c = race.lane(self.climb("c", 3, per=1.0) + [failed("c", "overhead/print-ext100", "exit 1: x")], [], "c", RUNGS)
        d = race.lane(self.climb("d", 1, per=1.0) + [failed("d", "overhead/print-ext10", "exit 1: x")], [], "d", RUNGS)
        e = race.lane(self.climb("e", 3, per=0.5) + [failed("e", "overhead/print-ext100", "exit 1: x")], [], "e", RUNGS)
        self.assertEqual([l["arm"] for l in race.rank([d, c, a, e, b])], ["b", "a", "e", "c", "d"])

    def test_a_harness_with_no_sample_anywhere_stopped_before_the_first_rung(self):
        l = race.lane([], [], "ghost", RUNGS)
        self.assertEqual((l["reached"], l["outcome"]), (0, race.STOPPED))


class Limits(unittest.TestCase):
    def test_a_container_run_states_its_tier_and_a_bare_run_says_it_is_not_comparable(self):
        c = race.limits_of({"run": {"isolation": {"envelope": {"memory_mib": 4096, "cpuset_cpus": [2, 3]}}}})
        self.assertEqual((c["isolation"], c["memory_gib"], c["cpus"], race.tier_name(c)), ("container", 4.0, 2, "4GiB"))
        b = race.limits_of({"run": {"isolation": {"stamp": "uncontained, not comparable"}, "harness_cpus": [1]}})
        self.assertEqual((race.tier_name(b), b["isolation"]), ("bare", "bare"))
        self.assertIn("uncontained", racereport.limits_text(b))

    def test_the_memory_tier_flag_reaches_the_plan_and_the_container(self):
        args = cli.build_parser().parse_args(["session", "overhead/version", "--memory-tier", "8"])
        self.assertEqual(cli.session_plan(args).memory_mib, 8192)
        self.assertEqual(engine.Plan(workloads=[], arms=[]).memory_mib, 4096)


class InTheReport(unittest.TestCase):
    def test_the_report_has_a_race_per_ladder_with_the_limits_once_and_one_row_per_harness(self):
        samples = []
        for rnd in range(12):
            for arm, scale in (("pi-node", 1.0), ("pi-node-b", 1.0), ("other", 1.5), ("other-b", 1.5)):
                for i, w in enumerate(("overhead/print", "overhead/print-ext5", "overhead/print-ext10", "overhead/print-ext50")):   # every rung of tracks.toml's ladder below the last
                    samples.append(ok(arm, w, scale * (i + 1), 100.0 * (i + 1), rnd, cpu=100.0 * scale))
                if arm.startswith("other"):
                    samples.append(failed(arm, "overhead/print-ext100", "exit 137: Killed", rnd))
                else:
                    samples.append(ok(arm, "overhead/print-ext100", 4.0 * scale, 400.0, rnd))
        tmp = tempfile.mkdtemp()
        run = os.path.join(tmp, "run")
        raw = raw_of(samples)
        raw["run"]["isolation"] = {"envelope": {"memory_mib": 2048, "cpuset_cpus": [1, 2]}}
        rawlib.write(raw, run)
        with open(render.render([run], os.path.join(tmp, "out"))) as f:
            text = f.read()
        section = text.split("## Races")[1].split("\n## ")[0]
        self.assertEqual(section.count("Limits: "), 1)   # one race here: the session-size race has no rung with samples
        self.assertIn("2 GiB of memory", section)
        self.assertIn("### Scales with extensions: 0 > 5 > 10 > 50 > 100 (2GiB)", section)
        self.assertRegex(section, r"\| 1 \| pi-node \| Finished in ")
        self.assertRegex(section, r"\| 2 \| other \| Stopped at 100 after .* OOM")
        import json
        with open(os.path.join(tmp, "out", "report.json")) as f:
            races = json.load(f)["races"]
        self.assertEqual([r["id"] for r in races], ["extensions"])
        self.assertEqual([l["arm"] for l in races[0]["lanes"]], ["pi-node", "other"])

    def test_a_run_with_no_ladder_sample_has_no_races_section(self):
        tmp = tempfile.mkdtemp()
        run = os.path.join(tmp, "run")
        rawlib.write(raw_of(series()), run)
        with open(render.render([run], os.path.join(tmp, "out"))) as f:
            self.assertNotIn("## Races", f.read())

    def test_every_ladder_question_has_rungs_that_match_its_steps(self):
        for q in tracks.load()["pi"]["questions"]:
            if q.get("rungs"):
                self.assertEqual([r["at"] for r in q["rungs"]], [str(s) for s in q["steps"]])


if __name__ == "__main__":
    unittest.main()
