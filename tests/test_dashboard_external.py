# SPDX-License-Identifier: Apache-2.0
"""The site's sections for other projects' suites: "Durable" (Buffon's own durable workloads, when there are any, and each project's own durable suites below them) and "Other suites" (everything
else: the registry's `section` decides, never the name). External suites are other projects' benchmarks, run as they are or imported with their provenance, and kept apart from everything Buffon measured.
Built from the demo run plus the demo's external directories (tests/report_demo.py: demo_external), drawn under Node (see tests/test_dashboard.py)."""
import dataclasses
import html as htmlmod
import json
import os
import re
import tempfile
import unittest
from unittest import mock

from buffon import cli
from buffon.dashboard import build as dashboard, external_site
from buffon.external import suites as extsuites
from tests.report_demo import demo_external, demo_raw, with_durable
from tests.telemetry_fixtures import write_dir
from tests.test_dashboard import NODE, app, render_all

NOTE = "Their method, their numbers: not comparable with Buffon's rows"
MARKERS = ("bench:storage:memory", "RSS after seed MiB", "BenchmarkStorage", "benchmark.py", "9,847.5", NOTE, "Pi-Bolt's published", "1 min 24 s")


def site_with(tmp, name, external, src=None):
    src = src or write_dir(os.path.join(tmp, "run"), demo_raw(rounds=4))
    out = os.path.join(tmp, name)
    suites, results = demo_external(os.path.join(tmp, name + "-ext")) if external else ((), ())
    dashboard.build([src], out, external_suites=suites, external_results=results)
    return out, src, suites, results


def data_of(out):
    with open(os.path.join(out, "data", "site.js"), encoding="utf-8") as f:
        return json.loads(f.read()[len("window.BUFFON="):-2])


def section_ids(out):
    return app(out, "console.log(JSON.stringify(A.Index(D).sections.map(s=>s.id)))")


def page_of(out, route):
    return app(out, f"console.log(JSON.stringify(A.render(D,{json.dumps(route)},{{width:1200}}).html))")


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class ProjectSuites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.out, cls.src, cls.suites, cls.results = site_with(cls.tmp, "with", True)
        cls.plain_out = site_with(cls.tmp, "without", False, cls.src)[0]
        cls.data, cls.plain = data_of(cls.out), data_of(cls.plain_out)
        cls.views = render_all(cls.out)
        cls.durable = page_of(cls.out, "#/r/durable")
        cls.other = page_of(cls.out, "#/r/other-suites")

    def cards(self, page):
        return re.findall(r'<section class="card xsuite" id="x-([^"]+)">(.*?)</section>', page, re.S)

    def card(self, page, text):
        return next(body for _, body in self.cards(page) if text in htmlmod.unescape(body))

    # ---- where they are
    def test_durable_follows_sessions_and_other_suites_is_the_last_section_before_all_metrics_and_each_says_not_run_yet_without_external_input(self):
        ids = section_ids(self.out)
        self.assertEqual(ids[ids.index("sessions") + 1], "durable")
        self.assertEqual(ids[-1], "other-suites")
        rail = re.search(r'<nav class="rail[^"]*" aria-label="Sections">.*?</nav>', self.views["#/"], re.S).group(0)
        self.assertLess(rail.index(">Sessions<"), rail.index(">Durable<"))
        self.assertLess(rail.index(">Other suites<"), rail.index(">All metrics<"))
        without = section_ids(self.plain_out)
        self.assertEqual(without[without.index("sessions") + 1], "durable")   # listed with or without external input
        self.assertEqual(without[-1], "other-suites")
        self.assertIsNone(self.plain["external"])
        for route in ("#/r/durable", "#/r/other-suites"):
            page = page_of(self.plain_out, route)
            self.assertIn("Not run yet", page)
            self.assertNotIn("xsuite", page)
        self.assertIn('<a class="card tile off" href="#/r/durable">', render_all(self.plain_out)["#/"])

    def test_the_registry_decides_the_section_of_a_suite_not_its_name(self):
        for sid in ("durable-storage", "durable-storage-memory", "durable-tool-output"):
            self.assertEqual(extsuites.SUITES[sid].section, "durable", sid)
        for sid in ("pi-bolt-benchmark", "pi-bolt-large-write", "pi-bolt-long-session", "pi-bolt-e2e-tools", "pi-evals-offline", "pi-evals"):
            self.assertEqual(extsuites.SUITES[sid].section, "other", sid)
        profiles = dashboard.load_profiles()
        ids = [h["id"] for h in self.data["harnesses"]]
        data, _ = external_site.load(self.suites, self.results, profiles, ids)
        self.assertEqual([c["suite"] for g in data["durable"]["groups"] for c in g["cards"]], ["durable-storage-memory", "durable-tool-output", "durable-storage"])
        moved = dict(extsuites.SUITES, **{"durable-tool-output": dataclasses.replace(extsuites.SUITES["durable-tool-output"], section="other")})
        with mock.patch.dict(extsuites.SUITES, moved, clear=True):
            data, _ = external_site.load(self.suites, self.results, profiles, ids)
        self.assertNotIn("durable-tool-output", [c["suite"] for g in data["durable"]["groups"] for c in g["cards"]])
        self.assertIn("durable-tool-output", [c.get("suite") for g in data["other"]["groups"] for c in g["cards"]])

    def test_the_cards_are_grouped_by_project_with_the_not_comparable_line_on_every_one(self):
        self.assertEqual([htmlmod.unescape(t) for t in re.findall(r'<h2 class="xlabel">([^<]+)</h2>', self.durable)], ["Pi's durable suites", "PiG's storage benchmark"])
        self.assertEqual([htmlmod.unescape(t) for t in re.findall(r'<h2 class="xlabel">([^<]+)</h2>', self.other)], ["Pi-Bolt's suites"])
        self.assertEqual(len(self.cards(self.durable)), 3)   # storage-memory (two targets in one card), tool-output, the PiG storage benchmark
        self.assertEqual(len(self.cards(self.other)), 2)     # the Pi-Bolt benchmark.py run and the imported Pi-Bolt result set
        for page in (self.durable, self.other):
            for _, body in self.cards(page):
                self.assertIn(f'<p class="xnote">{NOTE}.</p>', htmlmod.unescape(body))
        self.assertIn("Each project&#39;s own durable suites", self.durable)   # the page says it once, in its sentence; with Buffon's own metrics above, the suites have a heading of their own
        self.assertNotIn('class="xhead"', self.durable)
        self.assertIn("Pi-Bolt's published headless numbers", htmlmod.unescape(self.card(self.other, "Pi-Bolt's published")))
        self.assertIn("BenchmarkStorage", self.card(self.durable, "BenchmarkStorage"))

    def test_a_card_is_titled_by_its_target_in_plain_text(self):
        titles = [htmlmod.unescape(t) for t in re.findall(r'<h3 class="xtitle">([^<]*)</h3>', self.durable)]
        self.assertEqual(titles, ["Pi durable storage memory benchmark (npm run bench:storage:memory)", "Pi durable tool-output benchmark (npm run bench:tool-output)",
                                  "PiG durable storage benchmark (go test -bench BenchmarkStorage)"])   # PiG's Go benchmark is not Pi's vitest one: the registry has a title for each target
        for page in (self.durable, self.other):
            self.assertNotIn("`", re.sub(r"<pre.*?</pre>", "", page, flags=re.S))
        for suite in extsuites.SUITES.values():
            self.assertNotIn("`", suite.title)
            for target in suite.targets.values():
                self.assertNotIn("`", target.title)
        storage = extsuites.SUITES["durable-storage"]
        self.assertEqual({n: bool(t.title) for n, t in storage.targets.items()}, {"pi-node": True, "pig-native": True, "pig-tinygo": True})

    # ---- apart from everything Buffon measured
    def test_nothing_external_is_in_buffons_cells_ratios_tiles_or_the_all_metrics_page(self):
        for key in ("harnesses", "metrics", "cells", "families", "workloads", "runs", "faults", "scale"):
            self.assertEqual(self.data[key], self.plain[key], key)   # the data Buffon's views draw is the same with and without the external runs
        for route, page in self.views.items():
            if route.startswith(("#/r/durable", "#/r/other-suites", "#/doc/")):   # (docs/EXTERNAL.md names the suites, as a document)
                continue
            for marker in MARKERS:
                self.assertNotIn(marker, htmlmod.unescape(page), route)
        home = self.views["#/"]
        tiles = re.search(r'<div class="tiles">.*?</div><p class="allink">', home, re.S).group(0)
        self.assertNotIn("other-suites", tiles)
        self.assertIn('<a class="card tile" href="#/r/durable"><h2>Durable</h2><p class="tile-m">Project suites: 4 runs</p><p class="tile-r">newest run 2026-10-17</p></a>', tiles)   # a count and a date, no number of theirs
        every = self.views["#/all"].split('<div class="rbody">')[1]
        self.assertNotIn("durable", every.lower().replace("all metrics", ""))
        for rail_text in ("Durable", "Other suites"):
            self.assertIn(f">{rail_text}<", self.views["#/all"])   # the rail lists them; the table does not
        live = app(self.out, "console.log(JSON.stringify(A.Index(D).sections.filter(s=>!s.empty&&s.kind!=='external').length))")
        self.assertEqual(len(re.findall(r'<a class="card tile"', home)), live + 1)   # the sections with data, and Durable's tile of project suites

    def test_a_harness_page_has_no_row_for_them(self):
        page = self.views["#/harness/demo-alpha"]
        self.assertNotIn("durable", re.search(r'id="strip-demo-alpha".*?</section>', page, re.S).group(0))
        self.assertNotIn("other-suites", re.search(r'id="strip-demo-alpha".*?</section>', page, re.S).group(0))

    # ---- what a card shows
    def test_a_card_has_the_suites_owner_the_pin_the_command_the_host_and_when_it_ran(self):
        card = self.card(self.durable, "bench:storage:memory")
        self.assertIn("By <a", card)
        self.assertIn("Earendil Inc.", card)
        self.assertIn("MIT", card)
        self.assertRegex(card, r'pinned at <a href="https://github\.com/earendil-works/pi/tree/71023aec1546d6d677a65669c5665c0927ce0dd0">earendil-works/pi@71023aec1546</a>')
        self.assertIn("<code>npm run bench:storage:memory</code>", card)
        self.assertIn("Ran 2026-10-17 09:12 UTC on Demo CPU (invented), 64 GiB, 6.8.0-demo", card)
        self.assertIn("41.2 s, exit 0", card)

    def test_the_suites_own_table_is_kept_as_printed_and_targets_with_the_same_columns_share_one_table_with_a_column_each(self):
        card = self.card(self.durable, "bench:storage:memory")
        text = htmlmod.unescape(card)
        for printed in ("RSS after seed MiB", "heap after GC MiB", "seed time", "9,847.5", "6,105.4", "1 min 24 s", "100k ops"):
            self.assertIn(printed, text)
        self.assertEqual(len(re.findall(r'<table class="data xtable">', card)), 1)
        self.assertEqual(len(re.findall(r'<th scope="colgroup" colspan="2">', card)), 3)   # each column name, over a column for each of the two targets
        self.assertEqual(len(re.findall(r'<th scope="col" class="tcol h-\w+"><span class="hn">', card)), 6)
        row = re.search(r"<tr><th scope=\"row\">10M ops</th>(.*?)</tr>", card, re.S).group(1)
        self.assertEqual([htmlmod.unescape(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row)], ["9,847.5", "6,105.4", "4,311.9", "2,673.2", "1 min 24 s", "52 s"])

    def test_columns_that_differ_give_a_table_for_each_target_and_a_target_missing_a_row_leaves_it_empty(self):
        run = lambda target, columns, rows: {"target": target, "rows": [dict(zip(columns, r)) for r in rows]}
        apart = external_site.tables_of([run("a", ["x", "y"], [["1", "2"]]), run("b", ["x", "z"], [["1", "3"]])])
        self.assertEqual([t["targets"] for t in apart], [["a"], ["b"]])
        same = external_site.tables_of([run("a", ["x", "y"], [["r1", "1"], ["r2", "2"]]), run("b", ["x", "y"], [["r2", "9"]])])
        self.assertEqual(len(same), 1)
        self.assertEqual(same[0]["rows"], [["r1", "1", ""], ["r2", "2", "9"]])
        twice = external_site.tables_of([run("a", ["x", "y"], [["r", "1"], ["r", "2"]]), run("b", ["x", "y"], [["r", "3"]])])
        self.assertEqual(len(twice), 2)   # a label that repeats cannot line the targets up

    def test_a_table_that_did_not_parse_says_so_and_shows_the_raw_output_open_and_a_suite_with_no_table_shows_its_output_too(self):
        broken = self.card(self.durable, "bench:tool-output")
        self.assertIn("Table not parsed for pi-node: console table row has 3 cells for 4 columns", htmlmod.unescape(broken))
        self.assertNotIn("<table", broken)
        self.assertRegex(broken, r'<details class="more xout" open><summary>Raw output of pi-node</summary><pre class="xpre">')
        self.assertIn("│ 1200 │ 40 │ 3 │", htmlmod.unescape(broken))
        bolt = self.card(self.other, "benchmark.py")
        self.assertIn("The suite prints no table that Buffon reads", bolt)
        self.assertIn("interactive ready    1750.0", htmlmod.unescape(bolt))
        self.assertIn('<details class="more xout" open>', bolt)
        # a parsed table keeps the raw output one click away, closed
        self.assertRegex(self.card(self.durable, "bench:storage:memory"), r'<details class="more xout"><summary>Raw output of pi-node</summary>')
        for run in ("pi-node", "demo-alpha"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, "external", f"durable-storage-memory-{run}", "stdout.txt")))

    def test_an_imported_result_set_shows_its_provenance_its_files_unchanged_and_medians_of_the_sources_rows(self):
        card = self.card(self.other, "Pi-Bolt's published headless numbers")
        self.assertIn("Source host: linux-x64, the source's own machine", htmlmod.unescape(card))
        self.assertIn("pibolt 0.8.0, pi 1.0.3", card)
        self.assertIn("published 2026-10-11", card)
        self.assertRegex(card, r'<a href="external/pi-bolt-published-demo/files/headless\.jsonl">headless\.jsonl</a> <small>sha256 [0-9a-f]{16}, 6 rows</small>')
        self.assertIn("wall ms (median)", card)
        with open(os.path.join(self.out, "external", "pi-bolt-published-demo", "files", "headless.jsonl"), "rb") as copied, open(os.path.join(self.tmp, "with-ext", "published-files", "headless.jsonl"), "rb") as original:
            self.assertEqual(copied.read(), original.read())

    def test_a_target_that_is_an_arm_of_the_site_has_its_colour_so_the_spotlight_works_on_its_columns(self):
        card = self.card(self.durable, "bench:storage:memory")
        classes = set(re.findall(r'<th scope="col" class="tcol (h-\w+)">', card))
        harness = {h["id"]: h["colour"] for h in self.data["harnesses"]}
        self.assertEqual(classes, {f"h-{harness['pi-node']}", f"h-{harness['demo-alpha']}"})
        self.assertEqual(len(re.findall(r'<td class="tcol h-', card)), 3 * 6)   # three rows, a column for each target under each of the three column names
        with open(os.path.join(os.path.dirname(__file__), "..", "buffon", "dashboard", "assets", "app.js"), encoding="utf-8") as f:
            self.assertIn('".series, .brow, tbody tr, .chip, .tcol"', f.read())

    # ---- how they get in
    def test_the_dashboard_takes_external_runs_as_flags_or_among_its_directories(self):
        parsed = cli.build_parser().parse_args(["dashboard", "run", "--out", "site", "--external-suites", "a", "b", "--external-results", "c"])
        self.assertEqual((parsed.external_suites, parsed.external_results), (["a", "b"], ["c"]))
        self.assertEqual(external_site.split([self.src] + self.suites + self.results), ([self.src], self.suites, self.results))
        among = os.path.join(self.tmp, "among")
        dashboard.build([self.src] + self.suites + self.results, among)
        self.assertEqual(data_of(among)["external"], self.data["external"])
        with self.assertRaises(dashboard.DashboardError):
            dashboard.build(self.suites, os.path.join(self.tmp, "only-external"))   # an external run is not a Buffon run: there must be one of those too

    def test_the_site_loads_nothing_from_outside(self):
        for page in (self.durable, self.other):
            self.assertNotRegex(htmlmod.unescape(page), r'(?:src|href)="(?:https?:)?//(?!github\.com)')   # links go to the projects; nothing is fetched


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class DurableWorkloads(unittest.TestCase):
    """Buffon's own durable workloads (any durable/* scenario) make Durable a section of metrics like the others, with the project suites below them."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.src = write_dir(os.path.join(cls.tmp, "run"), with_durable(demo_raw(rounds=4)))
        suites, results = demo_external(os.path.join(cls.tmp, "ext"))
        cls.with_both = os.path.join(cls.tmp, "both")
        dashboard.build([cls.src], cls.with_both, external_suites=suites, external_results=results)
        cls.metrics_only = os.path.join(cls.tmp, "metrics")
        dashboard.build([cls.src], cls.metrics_only)

    def test_a_durable_scenario_makes_the_section_a_metrics_section_with_its_headline_tile_and_the_project_suites_under_the_table(self):
        sections = app(self.with_both, "console.log(JSON.stringify(A.Index(D).sections.filter(s=>s.id==='durable').map(s=>({kind:s.kind,keys:s.keys,head:s.head}))))")
        self.assertEqual(sections[0]["kind"], "metrics")
        self.assertEqual(sorted(sections[0]["keys"]), ["durable-append.cpu_ms", "durable-append.wall_ms"])
        page = page_of(self.with_both, "#/r/durable")
        self.assertIn('id="p-durable-append.cpu_ms"', page)
        self.assertIn('id="all-durable"', page)
        self.assertLess(page.index('id="all-durable"'), page.index("Each project's own durable suites"))
        self.assertEqual(len(re.findall(r'<section class="card xsuite"', page)), 3)
        home = page_of(self.with_both, "#/")
        tile = re.search(r'<a class="card tile" href="#/r/durable">.*?</a>', home, re.S).group(0)
        self.assertNotIn("Project suites", tile)   # Buffon's own headline, not the count of runs
        self.assertIn("durable-append.cpu_ms", page_of(self.with_both, "#/all"))
        self.assertNotIn("bench:storage:memory", page_of(self.with_both, "#/all"))

    def test_without_external_runs_the_durable_section_is_just_buffons_metrics(self):
        page = page_of(self.metrics_only, "#/r/durable")
        self.assertIn('id="p-durable-append.cpu_ms"', page)
        self.assertNotIn("xsuite", page)
        self.assertNotIn("Each project's own durable suites", page)


if __name__ == "__main__":
    unittest.main()
