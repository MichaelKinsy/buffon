# SPDX-License-Identifier: Apache-2.0
"""Wire metrics: every sample counts the requests the mock received and their body bytes; a workload that knows its turns adds bytes per turn and side requests; none of it is graded."""
import fnmatch
import json
import os
import tempfile
import tomllib
import unittest
from unittest import mock

from buffon import mock as mockpkg
from buffon.arms import manifest
from buffon.report import cells, metrics
from buffon.runner import raw as rawlib, wire
from buffon.up import flow, selection
from tests import stub_arms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Arm:
    def __init__(self, exact):
        self.capabilities = {"exact_requests": exact}


class Counters(unittest.TestCase):
    def test_the_marks_survive_a_reset_so_a_workload_that_resets_between_answers_is_counted_whole(self):
        rec = mockpkg.server.Recorder()
        before = wire.mark(rec)
        for size in (100, 250):
            rec.begin("openai-completions", {}, size, 0)
            rec.reset()   # streaming resets the mock once per answer size
        sample = {}
        wire.apply(sample, rec, before, Arm(True))
        self.assertEqual((sample["requests"], sample["request_bytes"]), (2, 350))

    def test_a_sample_counts_only_the_requests_of_its_own_window(self):
        rec = mockpkg.server.Recorder()
        rec.begin("openai-completions", {}, 40, 0)
        before = wire.mark(rec)
        rec.begin("openai-completions", {}, 60, 0)
        sample = {}
        wire.apply(sample, rec, before, Arm(True))
        self.assertEqual((sample["requests"], sample["request_bytes"]), (1, 60))

    def test_a_declaring_workload_gets_bytes_per_turn_and_side_requests_and_the_declaration_is_not_kept(self):
        rec = mockpkg.server.Recorder()
        before = wire.mark(rec)
        for _ in range(5):
            rec.begin("openai-completions", {}, 100, 0)
        sample = wire.declare({"cpu_ms": 1.0}, turns=2, scripted=4)
        wire.apply(sample, rec, before, Arm(False))
        self.assertEqual((sample["request_bytes_per_turn"], sample["side_requests"]), (250, 1))
        self.assertNotIn(wire.KEY, sample)
        self.assertNotIn("failure", sample)

    def test_an_arm_that_promises_exact_requests_fails_on_an_extra_one_unless_the_count_is_not_fixed(self):
        rec = mockpkg.server.Recorder()
        before = wire.mark(rec)
        for _ in range(3):
            rec.begin("openai-completions", {}, 10, 0)
        strict = wire.declare({}, 1, 2)
        wire.apply(strict, rec, before, Arm(True))
        self.assertIn("exact_requests", strict["failure"])
        loose = wire.declare({}, 1, 2, exact=False)
        wire.apply(loose, rec, before, Arm(True))
        self.assertEqual(loose["side_requests"], 1)
        self.assertNotIn("failure", loose)

    def test_fewer_requests_than_scripted_is_zero_side_requests_not_negative(self):
        rec = mockpkg.server.Recorder()
        before = wire.mark(rec)
        rec.begin("openai-completions", {}, 10, 0)
        sample = wire.declare({}, 2, 2)
        wire.apply(sample, rec, before, Arm(False))
        self.assertEqual(sample["side_requests"], 0)

    def test_a_workload_with_no_request_gets_no_wire_metrics(self):
        rec = mockpkg.server.Recorder()
        sample = wire.declare({}, 1, 1)
        wire.apply(sample, rec, wire.mark(rec), Arm(True))
        self.assertEqual(sample, {})

    def test_a_server_that_keeps_no_counters_leaves_the_sample_alone(self):
        sample = wire.declare({"cpu_ms": 1}, 1, 1)
        wire.apply(sample, object(), wire.mark(object()), Arm(True))
        self.assertEqual(sample, {"cpu_ms": 1})


class Kind(unittest.TestCase):
    def test_wire_metrics_have_their_own_kind_and_are_cells(self):
        for name, unit in (("requests", "count"), ("side_requests", "count"), ("request_bytes", "bytes")):
            self.assertEqual(metrics.describe(name), ("wire", unit))
            self.assertTrue(cells.scored(name), name)
        self.assertEqual(metrics.describe("request_bytes_per_turn")[0], "wire")
        self.assertTrue(cells.scored("request_bytes_per_turn"))

    def test_no_grade_row_reads_a_wire_metric(self):
        with open(os.path.join(ROOT, "workloads", "grade.toml"), "rb") as f:
            grade = tomllib.load(f)
        used = {m["metric"] for fam in grade["family"] for m in fam.get("metric", [])}
        self.assertTrue(used)
        for glob in used:
            for name in metrics.WIRE_METRICS:
                self.assertFalse(fnmatch.fnmatch(name, glob), f"{glob} would grade {name}")

    def test_a_run_from_before_the_wire_metrics_reads_its_request_bytes_as_the_first_requests_size(self):
        old = {"samples": [{"scenario": "overhead/print-tools", "request_bytes": 900.0}, {"scenario": "overhead/version"}]}
        new = {"samples": [{"scenario": "overhead/print-tools", "request_bytes": 7200.0, "requests": 8}]}
        self.assertEqual(rawlib.first_request_bytes(old)["samples"], [{"scenario": "overhead/print-tools", "first_request_bytes": 900.0}, {"scenario": "overhead/version"}])
        self.assertEqual(rawlib.first_request_bytes(new)["samples"][0]["request_bytes"], 7200.0, "a sum written with its request count is left alone")
        self.assertEqual(metrics.describe("first_request_bytes"), ("wire", "bytes"))


class EndToEnd(unittest.TestCase):
    """A real run of two stub arms and a third that sends one extra title request before the scripted one."""

    def test_the_samples_and_the_report_carry_the_wire_metrics(self):
        root = tempfile.mkdtemp()
        arms_dir = stub_arms.make(root, delays=(("stub-fast", 0.0), ("stub-title", 0.0)), side={"stub-title": 1})
        home = os.path.join(root, "home")
        with mock.patch.dict(os.environ, {"BUFFON_ARMS_DIR": arms_dir, "BUFFON_HOME": home, "BUFFON_LOCK_FILE": os.path.join(root, "buffon.lock")}):
            sel = selection.from_preset("quick").clone(harnesses=["stub-fast", "stub-title"], workloads=["overhead/print"], evals=[], isolation="none", rounds=4)
            summary = flow.up(sel, flow.Options(home=home, open_browser=False, pin=False), out=lambda *_: None, arms=manifest.load_all(arms_dir))
        run = summary["run_dirs"][0]
        with open(os.path.join(run, "raw.json")) as f:
            samples = [s for s in json.load(f)["samples"] if s["scenario"] == "overhead/print" and "failure" not in s]
        by = {}
        for s in samples:
            by.setdefault(s["arm"], []).append(s)
        self.assertTrue(by["stub-fast"] and by["stub-title"])
        for s in by["stub-fast"]:
            self.assertEqual((s["requests"], s["side_requests"]), (1, 0))
        for s in by["stub-title"]:
            self.assertEqual((s["requests"], s["side_requests"]), (2, 1))
            self.assertGreater(s["request_bytes"], by["stub-fast"][0]["request_bytes"])
            self.assertEqual(s["request_bytes_per_turn"], s["request_bytes"])
        with open(os.path.join(home, "site", "report", "report.json")) as f:
            report = json.load(f)
        seen = {c["metric"] for c in report["cells"]}
        self.assertTrue({"requests", "request_bytes", "side_requests"} <= seen, seen)


if __name__ == "__main__":
    unittest.main()
