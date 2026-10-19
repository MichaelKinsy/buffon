# SPDX-License-Identifier: Apache-2.0
"""What the dashboard says about scope and fairness: which workloads a harness took part in and why it missed the others, the runtime settings of each harness, a cell where a harness did
different work (its own median and no ratio), the equivalence result beside a ratio, the wire kind of metric, and the slot of a run. The demo data (tests/report_demo.py) carries each field."""
import html as htmlmod
import json
import os
import re
import unittest

from tests.report_demo import NO_PTY, NO_PTY_REASON, WIRE_METRICS, demo_raw
from tests.test_dashboard import NODE, app, built, render_all


def plain(html):
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", html))


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Scope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(demo_raw(rounds=6), faith=False)
        cls.views = render_all(cls.out)
        with open(os.path.join(cls.out, "data", "site.js"), encoding="utf-8") as f:
            cls.data = json.loads(f.read()[len("window.BUFFON="):-2])
        with open(os.path.join(cls.out, "data", "report.json")) as f:
            cls.report = json.load(f)

    def harness(self, hid):
        return next(h for h in self.data["harnesses"] if h["id"] == hid)

    def row(self, html, slug):
        return re.search(r'<tr class="h-[^"]*"><th scope="row" class="hn1"[^>]*><a class="hn" href="#/harness/' + slug + r'".*?</tr>', html, re.S).group(0)

    # ---- scope
    def test_the_scope_of_each_harness_is_the_workloads_it_has_values_in_and_the_rest_with_the_recorded_reason(self):
        scenarios = {c["scenario"] for c in self.data["cells"]}
        for h in self.data["harnesses"]:
            ran = {c["scenario"] for c in self.data["cells"] if h["id"] in c["stats"]}
            self.assertEqual({m["scenario"] for m in h["scope"]["measured"]}, ran, h["id"])
            self.assertEqual({n["scenario"] for n in h["scope"]["not_measured"]}, scenarios - ran, h["id"])
        for arm in NO_PTY[:1]:
            reasons = {n["scenario"]: n["reason"] for n in self.harness(arm)["scope"]["not_measured"]}
            self.assertEqual(reasons, {"overhead/pty": NO_PTY_REASON})
        self.assertEqual({n["scenario"] for n in self.harness("pi-node")["scope"]["not_measured"]}, set())

    def test_the_harness_page_lists_where_it_ran_once_and_folds_what_it_did_not_with_the_reason(self):
        gamma = self.views["#/harness/demo-gamma"]
        self.assertEqual(gamma.count("Measured in"), 1)
        measured = re.search(r'<p class="scope"><b>Measured in</b>(.*?)</p>', gamma, re.S).group(1)
        for m in self.harness("demo-gamma")["scope"]["measured"]:
            self.assertIn(htmlmod.escape(m["title"]), measured)
        folded = re.search(r'<details class="more"><summary>Not measured \((\d+)\)</summary>(.*?)</details>', gamma, re.S)
        self.assertEqual(folded.group(1), "1")
        self.assertIn(NO_PTY_REASON.split(": ")[0], plain(folded.group(2)))
        self.assertNotIn("Not measured", self.views["#/harness/pi-node"])

    def test_a_harness_chip_says_where_it_ran_and_what_it_cannot_run(self):
        chip = re.search(r'<button type="button" class="chip h-\w+" aria-pressed="\w+" data-toggle-list="h" data-value="demo-gamma" data-tip="([^"]*)"', self.views["#/"]).group(1)
        tip = htmlmod.unescape(chip)
        self.assertRegex(tip, r"Took part in \d+ of \d+ workloads")
        self.assertIn("Can't run:", tip)

    # ---- runtime settings
    def test_the_method_page_has_a_runtime_settings_row_for_each_harness_and_the_harness_page_repeats_its_own(self):
        method = self.views["#/method"]
        table = re.search(r'<table class="data" id="t-runtime-settings">.*?</table>', method, re.S).group(0)
        body = table.split("<tbody>")[1]
        self.assertEqual(body.count("<tr>"), len(self.data["harnesses"]))
        self.assertIn("NODE_OPTIONS=--max-old-space-size=2048", plain(body))
        self.assertIn("GOMAXPROCS", plain(body))
        alpha = plain(self.views["#/harness/demo-alpha"])
        self.assertIn("GOGC=100", alpha)
        self.assertRegex(alpha, r"GOGC=100\s+manifest")
        self.assertRegex(alpha, r"Left at the default\s+GOMEMLIMIT")

    # ---- different work
    def cell_of(self, html, slug, harness):
        return re.search(r'<td class="num[^"]*" data-csv-value="[^"]*"><a href="#/cell/' + slug + "/" + harness + r'".*?</td>', html, re.S).group(0)

    def test_a_not_compared_cell_has_its_median_and_the_label_and_no_ratio_mark(self):
        key = "overhead-print-ext10.cpu_ms"
        cell = next(c for c in self.data["cells"] if c["key"] == key)
        comp = cell["comparisons"]["demo-beta"]
        self.assertTrue(comp["not_compared"])
        self.assertTrue(all(comp[k] is None for k in ("ratio", "ci95", "p", "p_holm")))
        self.assertIsNone(comp["equivalence"])
        self.assertEqual(self.report["cells"][[c["id"] for c in self.report["cells"]].index(cell["id"])]["comparisons"]["demo-beta"]["ratio"], None)
        self.assertIsNotNone(comp["arm_median"])
        for route in ("#/r/extensions", "#/r/extensions?v=ratio"):
            html = self.views[route]
            beta = self.cell_of(html, cell["slug"], "demo-beta")
            self.assertIn("different work: not compared", beta)
            self.assertNotIn('class="cbar"', beta)
            self.assertNotIn("×", plain(beta))
            self.assertIn(f"{comp['arm_median']:.3g}".split(".")[0], plain(beta))
            self.assertIn('class="cbar"', self.cell_of(html, cell["slug"], "demo-alpha"), "a harness that did the same work keeps its bar")
        tip = re.search(r'data-tip="([^"]*)"', self.cell_of(self.views["#/r/extensions?v=ratio"], cell["slug"], "demo-beta")).group(1)
        self.assertIn(comp["not_compared"], htmlmod.unescape(tip))

    def test_a_not_compared_cell_is_last_when_a_table_is_sorted_by_ratio_in_both_directions(self):
        from tests.report_demo import with_sweep
        out = built(with_sweep(demo_raw(rounds=4)), faith=False)
        pts = [0, 5, 10, 50, 100]
        col = pts.index(10) + 1
        for direction in ("asc", "desc"):
            ui = f"{{tables:{{}},sort:{{'sweep-0':{{col:{col},dir:'{direction}'}}}}}}"
            html = app(out, f"console.log(JSON.stringify(A.render(D,'#/r/extensions?v=ratio&view=line',{{width:1200,ui:{ui}}}).html))")
            table = re.search(r'<table class="data" id="t-sweep-0">.*?</table>', html, re.S).group(0)
            rows = [[plain(c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)] for r in re.findall(r"<tr>(.*?)</tr>", table.split("<tbody>")[1], re.S)]
            names = [r[0] for r in rows]
            self.assertEqual(rows[names.index("demo-beta")][col], "different work: not compared", direction)
            last_number = max(i for i, r in enumerate(rows) if r[col] not in ("–", "different work: not compared"))
            self.assertLess(last_number, names.index("demo-beta"), direction)

    def test_the_page_of_a_not_compared_cell_gives_the_reason_the_source_and_no_ratio_or_tests(self):
        text = self.views["#/cell/overhead-print-ext10-chat-cpu-ms/demo-beta"]
        shown = plain(text)
        self.assertIn("different work: not compared", shown)
        self.assertIn("its own extensions in another form", shown)
        self.assertIn("docs/METHODOLOGY.md", shown)
        self.assertNotIn("Two tests", shown)
        self.assertNotIn("The ratio", shown)
        self.assertNotIn('<div class="big">1', text)
        other = self.views["#/cell/overhead-print-ext10-chat-cpu-ms/demo-alpha"]
        self.assertIn("demo-beta not compared", plain(other))

    def test_the_harness_page_shows_a_not_compared_measure_without_a_bar(self):
        page = self.views["#/harness/demo-beta"]
        row = re.search(r'<a class="hrow" href="#/cell/overhead-print-ext10-chat-cpu-ms/demo-beta".*?</a>', page, re.S).group(0)
        self.assertNotIn('class="hbar"', row)
        self.assertIn("not compared", row)
        self.assertIn("Different work (1)", page)

    # ---- equivalence
    def test_the_cell_page_shows_the_margin_the_90_percent_interval_and_whether_the_ratio_is_within_it(self):
        beta = plain(self.views["#/cell/overhead-print-chat-cpu-ms/demo-beta"])
        alpha = plain(self.views["#/cell/overhead-print-chat-cpu-ms/demo-alpha"])
        eq = next(c for c in self.data["cells"] if c["key"] == "overhead-print.cpu_ms")["comparisons"]["demo-beta"]["equivalence"]
        self.assertEqual(eq["margin"], 0.05)
        self.assertTrue(eq["equivalent"])
        self.assertRegex(beta, r"Equivalence margin\s+±5%")
        self.assertRegex(beta, r"90%\s+interval\s+of the ratio\s+[\d.]+ to [\d.]+")
        self.assertRegex(beta, r"Result\s+within ±5%")
        self.assertRegex(alpha, r"Result\s+not shown to be within ±5%")
        memory = plain(self.views["#/cell/overhead-print-chat-request-bytes/demo-beta"])
        self.assertIn("How sure is this number?", memory)
        self.assertNotIn("Equivalence margin", memory, "no margin declared, no result")

    # ---- wire kind
    def test_the_wire_section_has_its_own_measures_with_their_units(self):
        wire = [m for m in self.data["metrics"] if m["lens"] == "wire"]
        found = {m["metric"]: m["unit"] for m in wire}
        self.assertEqual(set(found), set(WIRE_METRICS))
        self.assertEqual(found["requests"], "count")
        self.assertEqual(found["request_bytes"], "bytes")
        page = app(self.out, "console.log(JSON.stringify(A.render(D,'#/r/wire?v=values',{width:1200}).html))")
        self.assertNotIn("<h1>Not found</h1>", page)
        self.assertRegex(page, r'href="#/cell/overhead-print-chat-requests/')
        self.assertRegex(page, r'href="#/cell/overhead-print-chat-request-bytes/')
        self.assertIn("5,200", plain(self.row(page, "demo-alpha")))

    def test_a_wire_metric_is_not_in_the_cost_grid_of_other_kinds_and_has_rows_like_any_other(self):
        cell = next(c for c in self.data["cells"] if c["metric"] == "request_bytes")
        self.assertEqual(cell["kind"], "wire")
        page = self.views["#/metric/overhead-print.request_bytes"]
        self.assertIn("Every harness", page)

    # ---- slot
    def test_the_runs_page_shows_the_slot_and_its_calibration(self):
        runs = plain(self.views["#/method/runs"])
        self.assertIn("2 of 4, CPUs 4-7", runs)
        self.assertIn("slots/2/calibration.json", runs)

    def test_a_run_without_a_slot_shows_no_slot_row(self):
        raw = demo_raw(rounds=4)
        del raw["run"]["slot"]
        out = built(raw, faith=False)
        self.assertNotIn("slot calibration", plain(app(out, "console.log(JSON.stringify(A.render(D,'#/method/runs',{width:1200}).html))")))


if __name__ == "__main__":
    unittest.main()
