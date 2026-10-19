# SPDX-License-Identifier: Apache-2.0
"""Divergences ([[divergence]] in arm.toml) and the runtime-settings record: an arm that does different work by its own account is shown and not compared."""
import copy
import json
import math
import os
import tempfile
import unittest

from buffon import divergence
from buffon.arms import manifest
from buffon.report import cells, grade_inputs, render
from buffon.runner import raw as rawlib
from buffon.runner import tuning
from tests.report_demo import demo_raw
from tests.telemetry_fixtures import write_dir
from tests.test_grade import REF, cell, make, run, uniform

DIV = {"workloads": ["streaming/tui-*"], "reason": "scrolls the rows that only moved", "source": "https://example.org/notes"}


def spec_with(*rows):
    arm = manifest.load_arm("pi-node")
    return arm, {**copy.deepcopy(arm.spec), "divergence": list(rows)}


def demo_with(divs):
    raw = demo_raw(rounds=8)
    raw["arms"]["demo-gamma"] = {"version": "0.3", "divergences": divs}
    return raw


def build(raw):
    return cells.build([raw], "pi-node", 7)


def comparison(data, scenario, metric, arm):
    return next(c for c in data["cells"] if c.scenario == scenario and c.metric == metric).comparisons[arm]


class Matching(unittest.TestCase):
    def test_workload_and_metric_globs_select_and_no_metrics_means_all(self):
        self.assertEqual(divergence.reason_for([DIV], "streaming/tui-prose", "n_wall_ms"), "scrolls the rows that only moved")
        self.assertIsNone(divergence.reason_for([DIV], "streaming/print-prose", "n_wall_ms"))
        self.assertIsNone(divergence.reason_for([DIV], "overhead/rpc", "cpu_ms"))
        only_cpu = dict(DIV, metrics=["*cpu*"])
        self.assertIsNotNone(divergence.reason_for([only_cpu], "streaming/tui-code", "n_cpu_ms_per_1k_tokens"))
        self.assertIsNone(divergence.reason_for([only_cpu], "streaming/tui-code", "n_wall_ms"))
        self.assertIsNone(divergence.reason_for(None, "streaming/tui-code", "n_wall_ms"))


class Manifest(unittest.TestCase):
    def check(self, row):
        arm, spec = spec_with(row)
        return manifest.validate("pi-node", spec, arm.dir)

    def test_a_valid_table_is_accepted(self):
        self.check(DIV)

    def test_a_glob_that_matches_no_registered_workload_is_refused(self):
        with self.assertRaisesRegex(manifest.ManifestError, "matches no registered workload"):
            self.check(dict(DIV, workloads=["streaming/tui-*", "streaming/nope-*"]))

    def test_reason_and_source_are_required_and_not_blank(self):
        for key in ("reason", "source", "workloads"):
            with self.assertRaisesRegex(manifest.ManifestError, key):
                self.check({k: v for k, v in DIV.items() if k != key})
        with self.assertRaisesRegex(manifest.ManifestError, "reason"):
            self.check(dict(DIV, reason="  "))

    def test_an_unknown_key_and_a_source_that_is_not_a_url_or_a_repository_document_are_refused(self):
        with self.assertRaisesRegex(manifest.ManifestError, "unknown key"):
            self.check(dict(DIV, because="x"))
        with self.assertRaisesRegex(manifest.ManifestError, "source"):
            self.check(dict(DIV, source="http://example.org/plain-http"))
        with self.assertRaisesRegex(manifest.ManifestError, "source"):
            self.check(dict(DIV, source="docs/NO-SUCH-DOCUMENT.md"))
        self.check(dict(DIV, source="docs/METHODOLOGY.md"))

    def test_the_pi_bolt_arms_label_their_tui_streaming_and_leave_rpc_and_the_large_write_scored(self):
        for name in ("pibolt", "pi-bolt-0.8.5"):
            arm = manifest.load_arm(name)
            self.assertTrue(arm.divergences, name)
            self.assertIsNotNone(divergence.reason_for(arm.divergences, "streaming/tui-prose", "n_cpu_ms_per_1k_tokens"), name)
            for scored in ("overhead/rpc", "overhead/print", "overhead/print-tools", "overhead/print-write", "overhead/pty", "streaming/print-prose"):
                self.assertIsNone(divergence.reason_for(arm.divergences, scored, "cpu_ms"), f"{name} {scored}")

    def test_no_arm_declares_one_by_the_reference_arms_name(self):
        self.assertEqual(manifest.load_arm("pi-node").divergences, [])


class Cells(unittest.TestCase):
    def test_a_diverged_cell_keeps_the_arms_median_and_has_no_ratio_interval_or_test(self):
        data = build(demo_with([DIV]))
        c = comparison(data, "streaming/tui-prose", "n_wall_ms", "demo-gamma")
        self.assertEqual(c.not_compared, DIV["reason"])
        self.assertEqual(c.verdict, "not compared")
        self.assertTrue(all(math.isnan(v) for v in (c.ratio, c.ci[0], c.ci[1], c.p, c.p_holm, c.floor)))
        self.assertAlmostEqual(c.arm_median, 6100.0 * 1.8, delta=6100 * 1.8 * 0.02)   # the demo arm's own median stays
        self.assertAlmostEqual(c.ref_median, 6100.0, delta=6100 * 0.02)

    def test_other_workloads_other_arms_and_the_arms_own_other_cells_are_compared_as_before(self):
        data = build(demo_with([DIV]))
        self.assertFalse(comparison(data, "overhead/rpc", "cpu_ms", "demo-gamma").not_compared)
        self.assertTrue(math.isfinite(comparison(data, "overhead/rpc", "cpu_ms", "demo-gamma").ratio))
        self.assertFalse(comparison(data, "streaming/tui-prose", "n_wall_ms", "demo-alpha").not_compared)

    def test_a_not_compared_arm_does_not_change_the_holm_adjustment_of_the_others(self):
        """Holm runs over the arms compared in a cell: one that is not compared takes no part, so the others' p-values are those of a run without it."""
        with_div = build(demo_with([DIV]))
        raw = demo_with([DIV])
        raw["samples"] = [s for s in raw["samples"] if not s["arm"].startswith("demo-gamma")]
        without = build(raw)
        for arm in ("demo-alpha", "demo-beta"):
            a, b = comparison(with_div, "streaming/tui-prose", "n_wall_ms", arm), comparison(without, "streaming/tui-prose", "n_wall_ms", arm)
            self.assertEqual((a.p, a.p_holm, a.verdict), (b.p, b.p_holm, b.verdict))

    def test_a_metric_glob_leaves_the_arms_other_metrics_of_the_workload_compared(self):
        data = build(demo_with([dict(DIV, metrics=["*cpu*"])]))
        self.assertTrue(comparison(data, "streaming/tui-prose", "n_cpu_ms_per_1k_tokens", "demo-gamma").not_compared)
        self.assertFalse(comparison(data, "streaming/tui-prose", "n_wall_ms", "demo-gamma").not_compared)

    def test_when_the_reference_does_different_work_no_arm_is_compared_there(self):
        raw = demo_raw(rounds=8)
        raw["arms"]["pi-node"] = {"version": "1.1.0", "divergences": [DIV]}
        data = build(raw)
        for arm in ("demo-alpha", "demo-beta", "demo-gamma"):
            c = comparison(data, "streaming/tui-prose", "n_wall_ms", arm)
            self.assertIn("pi-node does different work", c.not_compared)
            self.assertTrue(math.isnan(c.ratio))

    def test_the_summary_counts_no_outcome_for_a_not_compared_cell(self):
        data = build(demo_with([DIV]))
        before = build(demo_with([]))
        n = lambda d: sum(sum(v.values()) for v in cells.tally(d["cells"], "demo-gamma").values())
        self.assertEqual(n(before) - n(data), sum(1 for c in data["cells"] if c.scenario.startswith("streaming/tui-") and "demo-gamma" in c.comparisons))


class Grade(unittest.TestCase):
    def test_grade_inputs_leave_the_cell_out_for_that_arm_only(self):
        raw = demo_with([DIV])
        inputs = grade_inputs.build(build(raw), [raw], {"notes": "ok"}, True, [])
        cell = next(c for c in inputs["cells"] if c["scenario"] == "streaming/tui-prose" and c["metric"] == "n_wall_ms")
        self.assertNotIn("demo-gamma", cell["arms"])
        self.assertEqual(cell["not_compared"], {"demo-gamma": DIV["reason"]})
        self.assertIn("demo-alpha", cell["arms"])
        json.dumps(inputs, allow_nan=False)

    def inputs(self, left_out):
        """Four core cells; arm x costs 3x in two of them and the reference's cost in the other two; `left_out` names the cells x does different work in."""
        inputs = make({"x": uniform(1.0)})
        inputs["cells"] = [c for c in inputs["cells"] if c["family"] != "core"]
        for i, (kind, ratio) in enumerate((("cpu", 3.0), ("memory", 3.0), ("cpu", 1.0), ("memory", 1.0))):
            c = cell("core", i, kind, {"x": ratio})
            if i in left_out:
                c["not_compared"] = {"x": "different work"}
                del c["arms"]["x"]
            inputs["cells"].append(c)
        return inputs

    def test_a_cell_left_out_is_not_scored_for_that_arm_and_the_rest_decide(self):
        everything = run(self.inputs(set()), resamples=0)["x"]["families"]["core"]
        kept = run(self.inputs({0, 1}), resamples=0)["x"]["families"]["core"]
        self.assertGreater(everything["ratio"], 1.5)           # the two costly cells count when compared
        self.assertAlmostEqual(kept["ratio"], 1.0, places=6)    # and the grade ignores them once left out
        self.assertEqual(kept["cells"], 2)
        self.assertGreater(kept["score"], everything["score"])

    def test_cells_left_out_do_not_count_against_the_arms_coverage(self):
        """One cell of four kept: under the share of the reference's cells if the left-out ones counted, covered when they are taken out of the denominator."""
        covered = run(self.inputs({0, 1, 2}), resamples=0)["x"]["families"]["core"]
        self.assertEqual((covered["status"], covered["cells"], covered["ref_cells"]), ("scored", 1, 1))
        self.assertEqual(run(self.inputs({0, 1, 2}), resamples=0)[REF]["families"]["core"]["ref_cells"], 4)   # the reference's own count is untouched

    def test_a_family_left_out_in_every_cell_is_not_run_for_the_arm_with_a_reason(self):
        out = run(self.inputs({0, 1, 2, 3}), resamples=0)["x"]["families"]["core"]
        self.assertEqual(out["status"], "not-run")
        self.assertIn("different work", out["reason"])
        self.assertIsNone(out["score"])


class Report(unittest.TestCase):
    def rendered(self, raw):
        d = tempfile.mkdtemp()
        render.render([write_dir(os.path.join(d, "run"), raw)], os.path.join(d, "out"))
        with open(os.path.join(d, "out", "report.json")) as f:
            doc = json.load(f)
        with open(os.path.join(d, "out", "report.md")) as f:
            md = f.read()
        with open(os.path.join(d, "out", "summary.csv")) as f:
            csv = f.read()
        return doc, md, csv

    def test_report_json_md_and_csv_show_the_reason_in_place_of_the_ratio(self):
        doc, md, csv = self.rendered(demo_with([DIV]))
        cell = next(c for c in doc["cells"] if c["scenario"] == "streaming/tui-prose" and c["metric"] == "n_wall_ms")
        gamma = cell["comparisons"]["demo-gamma"]
        self.assertEqual(gamma["not_compared"], DIV["reason"])
        self.assertTrue(all(gamma[k] is None for k in ("ratio", "ci", "p", "p_holm")))
        self.assertGreater(gamma["arm_median"], 0)
        self.assertIsNone(cell["comparisons"]["demo-alpha"]["not_compared"])
        self.assertIsInstance(cell["comparisons"]["demo-alpha"]["ratio"], float)
        self.assertIn(f"different work: not compared ({DIV['reason']})", md)
        row = next(r for r in csv.splitlines() if r.startswith("streaming/tui-prose") and ",n_wall_ms," in r and ",demo-gamma," in r)
        self.assertIn("not compared", row)
        self.assertNotIn("nan", row)
        json.dumps(doc, allow_nan=False)
        grade_cells = doc["grade_inputs"]["cells"]
        self.assertTrue(any("demo-gamma" in c.get("not_compared", {}) for c in grade_cells))

    def test_a_report_without_divergences_has_none_and_the_method_section_lists_runtime_settings(self):
        raw = demo_raw(rounds=8, divergence=False)
        raw["arms"]["pi-node"]["runtime_settings"] = tuning.settings({"NODE_COMPILE_CACHE": "{install_dir}/cache"})
        doc, md, _ = self.rendered(raw)
        for c in doc["cells"]:
            for comp in c["comparisons"].values():
                self.assertIsNone(comp["not_compared"])
        self.assertIn("### Runtime settings", md)
        self.assertIn("`NODE_COMPILE_CACHE={install_dir}/cache`", md)
        self.assertNotIn("different work: not compared", md)


class RuntimeSettings(unittest.TestCase):
    def test_no_manifest_sets_gomaxprocs_and_the_record_lists_what_each_arm_sets(self):
        for name, arm in manifest.load_all().items():
            rs = tuning.settings(arm.env)
            self.assertNotIn("GOMAXPROCS", rs["env"], name)
            self.assertIn("GOMAXPROCS", rs["left_default"], name)
            self.assertEqual(set(rs["source"]), set(rs["env"]))
            self.assertFalse(set(rs["env"]) & set(rs["left_default"]))
        self.assertEqual(tuning.settings(manifest.load_arm("pi-node").env)["env"], {"NODE_COMPILE_CACHE": "{install_dir}/node-compile-cache"})
        self.assertEqual(tuning.settings(manifest.load_arm("pi-node").env)["source"], {"NODE_COMPILE_CACHE": "manifest"})

    def test_a_manifest_value_is_recorded_as_manifest_and_the_rest_of_the_known_set_is_left_default(self):
        rs = tuning.settings({"GOGC": "400", "BUN_JSC_x": "1", "PI_OFFLINE": "1"})
        self.assertEqual(rs["env"], {"BUN_JSC_x": "1", "GOGC": "400"})
        self.assertEqual(rs["source"], {"BUN_JSC_x": "manifest", "GOGC": "manifest"})
        self.assertNotIn("GOGC", rs["left_default"])
        self.assertIn("GOMEMLIMIT", rs["left_default"])
        self.assertNotIn("PI_OFFLINE", rs["env"])


class RawChecker(unittest.TestCase):
    def raw(self, **arm):
        raw = demo_raw(rounds=2)
        raw["arms"]["demo-gamma"] = {"version": "0.3", **arm}
        return raw

    def test_the_arms_record_round_trips(self):
        raw = self.raw(runtime_settings=tuning.settings({"GOGC": "400"}), divergences=[DIV])
        rawlib.validate(raw)

    def test_a_malformed_record_is_refused(self):
        good = tuning.settings({"GOGC": "400"})
        for bad in ({**good, "source": {}}, {**good, "source": {"GOGC": "operator"}}, {**good, "left_default": ["GOGC"]}, {"env": {"HOME": "/x"}, "left_default": [], "source": {"HOME": "manifest"}},
                    {"env": {}, "left_default": [], "source": {}, "extra": 1}, {**good, "env": {"GOGC": 400}}):
            with self.assertRaises(rawlib.RawError, msg=str(bad)):
                rawlib.validate(self.raw(runtime_settings=bad))
        for bad in ({"reason": "x", "source": "y"}, dict(DIV, workloads=[]), dict(DIV, reason=""), dict(DIV, metrics="cpu"), dict(DIV, other=1)):
            with self.assertRaises(rawlib.RawError, msg=str(bad)):
                rawlib.validate(self.raw(divergences=[bad]))

if __name__ == "__main__":
    unittest.main()
