# SPDX-License-Identifier: Apache-2.0
"""report.html, the CSV series, the SVG plots and the whole render from one run directory: all from the same data."""
import csv
import json
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from buffon.report import cells as cellmath
from buffon.report import html as htmllib
from buffon.report import render, series
from tests.telemetry_fixtures import clone, facts, run, write_dir


def read(*parts):
    with open(os.path.join(*parts)) as f:
        return f.read()


def read_csv(*parts):
    with open(os.path.join(*parts), newline="") as f:
        return list(csv.DictReader(f))


class Html(unittest.TestCase):
    def test_tables_lists_quotes_and_inline_markup(self):
        out = htmllib.convert(["# Title", "", "> **warn** `x`", "", "| a | b |", "|---|---:|", "| 1 | 2 |", "", "- one", "- two", "", "para [l](https://example.org/a?b=1&c=2)", "---"])
        self.assertIn('<h1 id="title">Title</h1>', out)
        self.assertIn("<blockquote><p><strong>warn</strong> <code>x</code></p></blockquote>", out)
        self.assertIn("<table><thead><tr><th>a</th><th>b</th></tr></thead>", out)
        self.assertIn("<td class=num>2</td>", out)
        self.assertIn("<li>two</li>", out)
        self.assertIn('href="https://example.org/a?b=1&amp;c=2"', out)
        self.assertIn("<hr>", out)

    def test_nothing_from_the_data_reaches_the_page_unescaped(self):
        out = htmllib.page("t <i>", ["| a |", "|---|", "| <script>alert(1)</script> |", "", "x <img src=x onerror=1> `<b>`"])
        self.assertNotIn("<script>alert", out)
        self.assertNotIn("<img", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<title>t &lt;i&gt;</title>", out)

    def test_the_run_notes_heading_has_no_health_colour(self):
        out = htmllib.convert(["## Run notes"])
        self.assertIn('<h2 id="run-notes">Run notes</h2>', out)
        self.assertNotIn("health-", out)


class Series(unittest.TestCase):
    def data(self, raw):
        return cellmath.build([raw])

    def test_rounds_rows_hold_each_measured_value_with_the_telemetry_around_it(self):
        def mutate(s):
            if s["arm"] == "other" and s["round"] == 5:
                s["telemetry"]["system"]["cgroup"]["throttled_us"] = 4000
                s["telemetry"]["system"]["cgroup"]["throttled_periods"] = 2
        raw = run(mutate=mutate)
        rows = series.rows([raw], self.data(raw))
        self.assertEqual(len(rows), 48 * 2)                       # 4 arms x 12 measured rounds x 2 scored metrics; warm-up excluded
        row = next(r for r in rows if r["arm"] == "other" and r["round"] == 5 and r["metric"] == "cpu_ms")
        self.assertEqual((row["throttled_us"], row["flags"], row["mhz_mean"], row["quiet_wait_ms"]), (4000, "throttled", 2400.0, 260))
        self.assertNotIn(0, {r["round"] for r in rows})

    def test_the_svg_is_well_formed_starts_at_zero_and_draws_the_copy_dashed(self):
        raw = run()
        cell = self.data(raw)["cells"][0]
        arms, svg = series.cell_svg(cell)
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        labels = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
        self.assertIn("0", labels)
        self.assertEqual(len([p for p in root.iter("{http://www.w3.org/2000/svg}polyline")]), 4)
        self.assertEqual(svg.count("stroke-dasharray=\"4 3\""), 2)
        self.assertEqual(arms, ["other", "other-b", "pi-node", "pi-node-b"])
        self.assertTrue(ET.fromstring(series.aa_svg(cell, ["pi-node", "other"])))

    def test_a_cell_without_values_draws_nothing(self):
        self.assertEqual(series.svg("x", {}), "")

    def test_host_plots_follow_the_samples_in_the_order_they_ran(self):
        raw = run()
        busy, mhz, load = series.host_series([raw])
        self.assertEqual(len(busy), len(raw["samples"]))
        self.assertEqual({y for _, y in mhz}, {2400.0})
        self.assertEqual(len(series.host_svgs([raw])), 3)
        self.assertEqual([s for s in series.host_svgs([run(telemetry=False)]) if "mean clock" in s or "busy during" in s], [])

    def test_telemetry_rows_flatten_every_group(self):
        rows = series.telemetry_rows([run(rounds=3)])
        self.assertEqual(len(rows), 16)
        r = rows[0]
        for key in ("cpuset.cpuset_busy_ms", "cgroup.cpu_usage_ms", "gate.status", "during.mhz_mean", "collector.thread_cpu_ms", "before.load1"):
            self.assertIn(key, r)


class WholeReport(unittest.TestCase):
    def render(self, raw):
        d = tempfile.mkdtemp()
        src = write_dir(os.path.join(d, "run"), raw)
        out = os.path.join(d, "out")
        render.render([src], out)
        return out

    def test_every_output_is_written_and_says_the_same_thing(self):
        out = self.render(run())
        for name in ("report.md", "report.html", "report.json", "summary.csv", "rounds.csv", "noise.csv", "telemetry.csv", "health.json"):
            self.assertTrue(os.path.getsize(os.path.join(out, name)) > 0, name)
        md = read(out, "report.md")
        page = read(out, "report.html")
        report = json.loads(read(out, "report.json"))
        health = json.loads(read(out, "health.json"))
        self.assertEqual(report["health"], health)
        self.assertIn(f"**Run notes ({health['notes']})**: ", md)
        self.assertIn("## Run notes", md)
        self.assertNotIn("health-", page)
        self.assertNotIn("verdict", health)
        self.assertEqual(len(re.findall(r"<table>", page)), len(re.findall(r"^\|---", md, re.M)), "every Markdown table is an HTML table")
        self.assertIn("Drift: per-round series", page)
        self.assertTrue(os.listdir(os.path.join(out, "plots")))
        rows = read_csv(out, "rounds.csv")
        self.assertEqual(len(rows), 96)
        self.assertEqual(rows[0]["flags"], "")

    def test_the_arm_tables_carry_cv_and_outlier_columns_next_to_the_headline_ratio(self):
        out = self.render(run())
        md = read(out, "report.md")
        head = next(line for line in md.splitlines() if line.startswith("| workload | api | metric | kind | unit | n | reference median"))
        self.assertIn("CV ref / arm", head)
        self.assertIn("outliers ref / arm", head)
        row = next(line for line in md.splitlines() if line.startswith("| overhead/print | chat | cpu_ms"))
        self.assertRegex(row, r"\| \d\.\d% / \d\.\d% \| [\d.]+ / [\d.]+ \| 0 / 0 \|")

    def test_drop_flagged_changes_the_statistics_and_lists_what_it_dropped(self):
        def mutate(s):
            if s["arm"] == "other" and s["round"] == 7:
                s["telemetry"]["system"]["cpuset"]["cpuset_steal_ms"] = 80.0
        raw = run(mutate=mutate)
        d = tempfile.mkdtemp()
        src = write_dir(os.path.join(d, "run"), raw)
        render.render([src], os.path.join(d, "a"))
        render.render([src], os.path.join(d, "b"), drop_flagged=True)
        a = read(d, "a", "report.md")
        b = read(d, "b", "report.md")
        self.assertIn("Do the flagged rounds change the answer?", a)
        self.assertIn("Rounds dropped with `--drop-flagged`", b)
        self.assertIn("| 1 | overhead/print | openai-completions | 7 | steal |", b)
        self.assertEqual(len(read_csv(d, "b", "rounds.csv")), 88)
        self.assertEqual(len([r for r in read_csv(d, "b", "telemetry.csv") if r["round"] == "7"]), 4, "telemetry.csv keeps every sample as recorded, dropped rounds included")

    def test_a_run_without_telemetry_still_renders_and_has_notes(self):
        out = self.render(run(telemetry=False))
        health = json.loads(read(out, "health.json"))
        self.assertGreater(health["notes"], 0)
        self.assertIn("telemetry", health["summary"])


if __name__ == "__main__":
    unittest.main()
