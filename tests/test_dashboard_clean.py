# SPDX-License-Identifier: Apache-2.0
"""Results pages that are clean: no empty row (a chart, a tile or a table draws only the harnesses that have a value, the others are in one line under it), Bars by default, and tables of
at most six main columns, one for each workload, with the other metrics behind "More metrics". Built from the demo run in which demo-gamma has no value for the streaming workloads
(it was not run there) and cannot run the large write (its manifest says so); drawn under Node (see tests/test_dashboard.py)."""
import html as htmlmod
import json
import os
import re
import unittest

from tests.report_demo import demo_raw, with_sweep
from tests.test_dashboard import NODE, ROOT, app, built, metric_tables, render_all
from tests.test_dashboard_scale import AGENTS, plain, site_data, with_swarms, with_write

MAIN_MAX = 6   # docs/design/DASHBOARD.md, "At most six main columns"


def short(name):
    return re.sub(r"\s*\([^)]*\)\s*$", "", name)


def not_in_test(html):
    """[[names]] of every muted "Not in this test" line of a page."""
    return [[n.strip() for n in plain(m).split(": ", 1)[1].rstrip(".").split(", ")] for m in re.findall(r'<p class="notrun notin">Not in this test:.*?</p>', html, re.S)]


def cant_run(html):
    return [m for m in re.findall(r'<p class="notrun cant">.*?</p>', html, re.S)]


def tables_of(html):
    """Every `table.grid` of a page: [(id, [class of each cell of each row], number of heading cells)]."""
    out = []
    for m in re.finditer(r'<table class="data grid" id="t-([^"]+)"[^>]*>(.*?)</table>', html, re.S):
        rows = [re.findall(r'<td class="([^"]*)"', tr) for tr in re.findall(r'<tr class="h-[^"]*"[^>]*>.*?</tr>', m.group(2), re.S)]
        out.append((m.group(1), rows, len(re.findall(r'<th scope="col" class="num mcol"', m.group(2)))))
    return out


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Clean(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = with_swarms(with_write(with_sweep(demo_raw(rounds=4))))
        raw["samples"] = [s for s in raw["samples"] if not (s["arm"].startswith("demo-gamma") and s["scenario"].startswith("streaming/"))]   # demo-gamma was not run on streaming
        cls.out = built(raw, faith=False)
        cls.data = site_data(cls.out)
        cls.sections = app(cls.out, "console.log(JSON.stringify(A.Index(D).sections.filter(s=>!s.empty).map(s=>({id:s.id,kind:s.kind,head:s.head||null,keys:s.keys||[]}))))")
        cls.ids = [s["id"] for s in cls.sections]
        cls.routes = ["#/", "#/all", AGENTS] + [f"#/r/{i}" for i in cls.ids] + [f"#/r/{i}?view={v}" for i in ("streaming", "large-writes", "extensions") for v in ("dots", "rounds", "bars")] + \
            ["#/r/extensions?view=line", "#/r/streaming?v=values", "#/?view=dots", "#/?h=demo-gamma", "#/r/streaming?h=demo-gamma", "#/r/large-writes?h=demo-gamma", "#/all?s=streaming&h=demo-gamma", "#/all?h=demo-gamma",
             "#/r/start-up?h=demo-gamma,pi-node", "#/r/agent-swarming?h=demo-gamma&m=rpc.mem_per_agent_mib", "#/r/reliability"]
        cls.views = render_all(cls.out, [r for r in cls.routes if r not in ("#/", "#/all", AGENTS)])
        cls.pages = {r: cls.views[r] for r in cls.routes}

    def cell(self, key):
        return next(c for c in self.data["cells"] if c["key"] == key and c["api_short"] in ("-", "chat"))

    def missing(self, key):
        """The names of the harnesses that have no value in the cell of a metric."""
        stats = self.cell(key)["stats"]
        return sorted(short(h["name"]) for h in self.data["harnesses"] if h["id"] not in stats)

    def head(self, sid):
        return next(s["head"] for s in self.sections if s["id"] == sid)

    # (a) no n/a row anywhere; the muted line names exactly the harnesses that were not measured there
    def test_no_chart_tile_or_table_draws_an_n_a_row_and_no_page_says_n_a(self):
        for route, page in self.pages.items():
            self.assertNotIn("n/a", plain(page), route)
            self.assertNotRegex(page, r'class="brow [^"]*\bna\b', route)
            self.assertNotIn("can't run</span></td>", page, route)

    def test_a_chart_of_a_section_where_a_harness_has_no_value_has_no_row_for_it_and_one_line_that_names_exactly_those_harnesses(self):
        key = self.head("streaming")
        want = self.missing(key)
        self.assertEqual(want, ["demo-gamma"], "the fixture: demo-gamma has no streaming value")
        for view in ("bars", "dots", "rounds"):
            page = self.pages[f"#/r/streaming?view={view}"] if view != "bars" else self.pages["#/r/streaming"]
            card = re.search(r'<section class="card small" id="p-' + re.escape(key) + r'".*?</section>', page, re.S).group(0)
            self.assertNotIn("demo-gamma</a>", card, view)
            self.assertNotRegex(card, r'(class="dl"|class="bn")[^>]*>[^<]*demo-gamma', view)
            self.assertEqual(not_in_test(card), [want], view)
            self.assertEqual(cant_run(card), [], view)
            # every other harness that has a value has its row
            have = {short(h["name"]) for h in self.data["harnesses"] if h["id"] in self.cell(key)["stats"]}
            self.assertEqual(len(re.findall(r'href="#/harness/', card)) if view == "bars" else len(have), len(have), view)

    def test_a_tile_has_no_row_for_a_harness_without_a_value_and_names_it_under_the_chart(self):
        key = self.head("streaming")
        tile = re.search(r'<a class="card tile" href="#/r/streaming[^"]*">.*?</a>', self.pages["#/"], re.S).group(0)
        self.assertEqual(not_in_test(tile), [self.missing(key)])
        self.assertNotRegex(tile, r'<span class="bn">[^<]*demo-gamma')
        self.assertIn('class="bars', tile)
        self.assertNotIn("<svg", tile)
        have = len(self.cell(key)["stats"])
        self.assertEqual(len(re.findall(r'<div class="brow h-', tile)), have)
        self.assertEqual(len(re.findall(r'<a ', tile)), 1, "a tile is one link")

    def test_a_table_has_no_row_for_a_harness_without_a_value_in_the_workload_and_its_line_says_so(self):
        page = self.pages["#/r/streaming"]
        tables = metric_tables(page, "all-streaming")
        self.assertTrue(tables)
        for t in tables:
            self.assertNotIn("demo-gamma", [slug for slug, _ in t["rows"]], t["id"])
            self.assertTrue(t["rows"])
        lines = not_in_test(page)
        self.assertTrue(lines)
        self.assertTrue(all(l == ["demo-gamma"] for l in lines), lines)
        # one workload's table names it once; where every workload misses it, once above them all
        self.assertEqual(len(not_in_test(re.search(r'<section class="card" id="all-streaming".*?</section>', page, re.S).group(0))), 1)

    def test_a_harness_that_cannot_run_is_in_the_can_t_run_line_with_its_reason_and_never_in_the_other_line(self):
        page = self.pages["#/r/large-writes"]
        line = cant_run(page)
        self.assertTrue(line)
        self.assertIn("Can't run: ", plain(line[0]))
        self.assertIn("demo-gamma", plain(line[0]))
        self.assertIn("(its tool set has no write tool)", plain(line[0]))
        self.assertEqual(not_in_test(page), [])
        for t in metric_tables(page, "all-large-writes"):
            self.assertNotIn("demo-gamma", [slug for slug, _ in t["rows"]])
        # the same on the home page and on the page of every metric of the section
        tile = re.search(r'<a class="card tile" href="#/r/large-writes[^"]*">.*?</a>', self.pages["#/"], re.S).group(0)
        self.assertIn("Can't run: ", plain(tile))
        self.assertNotIn("Not in this test", tile)

    def test_a_card_where_no_selected_harness_has_a_value_says_so_in_one_line_and_draws_no_chart_and_no_table(self):
        page = self.pages["#/r/streaming?h=demo-gamma"]
        card = re.search(r'<section class="card small" id="p-[^"]*".*?</section>', page, re.S).group(0)
        self.assertIn('<p class="empty">No selected harness has a value here.</p>', card)
        self.assertNotRegex(card, r'class="bars|<svg class="chart"|<g class="series')
        self.assertEqual(metric_tables(page, "all-streaming"), [])
        self.assertIn("No selected harness has a value here.", re.search(r'<section class="card" id="all-streaming".*?</section>', page, re.S).group(0))
        home = self.pages["#/?h=demo-gamma"]
        tile = re.search(r'<a class="card tile" href="#/r/streaming[^"]*">.*?</a>', home, re.S).group(0)
        self.assertIn("No selected harness has a value here.", tile)
        self.assertNotIn('class="bars', tile)
        self.assertIn("No selected harness has a value here.", self.pages["#/all?s=streaming&h=demo-gamma"].split("</nav>", 1)[1])

    # (b) Bars by default; an explicit view in the URL wins
    def test_bars_are_the_default_view_wherever_bars_are_offered_and_a_view_in_the_url_wins(self):
        state = lambda route: app(self.out, f"console.log(JSON.stringify(A.stateOf(A.Index(D),A.parse({json.dumps(route)})).view))")
        self.assertEqual(state("#/"), "bars")
        self.assertEqual(state("#/r/streaming"), "bars")
        self.assertEqual([state(f"#/r/streaming?view={v}") for v in ("dots", "bars", "rounds", "line")], ["dots", "bars", "rounds", "line"])
        self.assertEqual(state("#/r/streaming?view=bogus"), "bars")
        pressed = lambda page: re.findall(r'<button type="button" data-href="([^"]*)" aria-pressed="true">([^<]+)</button>', re.search(r'<div class="viewbar">.*?</div></div>', page, re.S).group(0))
        for sid in ("streaming", "large-writes", "extensions", "start-up"):
            page = self.pages[f"#/r/{sid}"] if sid in self.ids else self.render(f"#/r/{sid}")
            self.assertEqual([p[1] for p in pressed(page)], ["Bars"], sid)
            self.assertIn('class="bars', page, sid)
            self.assertNotIn('<svg class="chart"', page.split('class="viewbar"')[1].split('id="all-')[0], sid)
        # the choice is in the URL; the default is not
        page = self.pages["#/r/streaming"]
        self.assertIn('<button type="button" data-href="#/r/streaming" aria-pressed="true">Bars</button>', page)
        self.assertIn('<button type="button" data-href="#/r/streaming?view=dots" aria-pressed="false">Dots</button>', page)
        self.assertIn('<button type="button" data-href="#/r/streaming?view=rounds" aria-pressed="false">Rounds</button>', page)
        self.assertEqual([p[1] for p in pressed(self.pages["#/r/streaming?view=dots"])], ["Dots"])
        self.assertRegex(self.pages["#/r/streaming?view=dots"], r'<g class="series h-\w+"><text class="dl"')
        self.assertEqual([p[1] for p in pressed(self.pages["#/r/streaming?view=rounds"])], ["Rounds"])
        self.assertIn('<circle class="rd"', self.pages["#/r/streaming?view=rounds"])
        self.assertEqual([p[1] for p in pressed(self.pages["#/r/extensions?view=line"])], ["Line"])
        self.assertIn('id="sweep-0"', self.pages["#/r/extensions?view=line"])

    def render(self, route):
        return app(self.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(route)},{{width:1200}}).html))")

    def test_the_home_tiles_are_bars_by_default_and_dots_when_the_url_says_so(self):
        for tile in re.findall(r'<a class="card tile" href="#/r/(?:start-up|streaming|large-writes|extensions)[^"]*">.*?</a>', self.pages["#/"], re.S):
            self.assertIn('class="bars', tile)
        for tile in re.findall(r'<a class="card tile" href="#/r/(?:start-up|streaming|large-writes|extensions)[^"]*">.*?</a>', self.pages["#/?view=dots"], re.S):
            self.assertIn('<svg class="chart"', tile)
            self.assertNotIn('class="bars', tile)

    # (c) no row and no column of any table is empty
    def test_no_table_has_a_row_or_a_column_that_is_empty(self):
        seen = 0
        for route, page in self.pages.items():
            for tid, rows, heads in tables_of(page):
                seen += 1
                self.assertTrue(rows, (route, tid))
                for r in rows:
                    self.assertTrue(any(" na" not in " " + c for c in r), (route, tid, "a row with no value"))
                    self.assertEqual(len(r), heads or len(r), (route, tid))
                for j in range(len(rows[0])):
                    self.assertTrue(any(" na" not in " " + r[j] for r in rows), (route, tid, j, "a column with no value"))
        self.assertGreater(seen, 40)

    # (d) at most MAIN_MAX main columns; headings of at most two lines; the other metrics behind "More metrics"
    def test_a_default_table_has_at_most_six_columns_and_the_rest_is_behind_more_metrics(self):
        for route, page in self.pages.items():
            for tid, rows, heads in tables_of(page):
                self.assertLessEqual(heads, MAIN_MAX, (route, tid))
        # a few columns in each table, the rest behind a closed disclosure
        page = self.pages["#/r/prompts-and-tools"]
        main = [t for t in metric_tables(page, "all-prompts-and-tools") if not re.search(r"-m\d+$", t["id"])]
        more = [t for t in metric_tables(page, "all-prompts-and-tools") if re.search(r"-m\d+$", t["id"])]
        self.assertTrue(main and more)
        keys = [k for t in main + more for k in t["keys"]]
        self.assertEqual(sorted(keys), sorted(next(s for s in self.sections if s["id"] == "prompts-and-tools")["keys"]))   # every metric is in a table
        for m in re.finditer(r'<details class="more"><summary>More metrics \((\d+)\)</summary>(.*?)</details>', page, re.S):
            self.assertEqual(len(re.findall(r'<a class="info" href="#/metric/', m.group(2))), int(m.group(1)))
        self.assertNotIn('<details class="more" open', page)

    def test_a_column_heading_is_a_short_name_at_most_two_lines_and_a_variant_is_a_group_heading(self):
        for route, page in self.pages.items():
            for m in re.finditer(r'<span class="mw">(.*?) <i class="arrow">', page):
                self.assertLessEqual(len(htmlmod.unescape(m.group(1))), 40, (route, m.group(1)))
            for m in re.finditer(r'<span class="mw">([^<]*)</span>', page):
                self.assertLessEqual(len(htmlmod.unescape(m.group(1))), 40, (route, m.group(1)))
        page = self.pages["#/r/large-writes"]
        self.assertEqual(re.findall(r'<th scope="colgroup" colspan="\d+" class="grp">([^<]*)</th>', page)[:2], ["200 KB file", "50 KB file"])
        self.assertNotIn("200 KB file</span>", page)   # not repeated in a column heading

    def test_the_download_csv_is_one_for_all_the_metrics_of_the_page_and_its_tables_are_in_the_group(self):
        for route, group in (("#/r/extensions", "all-extensions"), ("#/r/prompts-and-tools", "all-prompts-and-tools"), ("#/all", "all-metrics"), (AGENTS, "all-agent-swarming")):
            page = self.pages[route] if route in self.pages else self.render(route)
            self.assertEqual(page.count(f'data-csv="{group}"'), 1, route)
            tables = re.findall(r'<table class="data grid" id="t-[^"]*"([^>]*)>', page)
            self.assertTrue(tables, route)
            self.assertTrue(all(f'data-csv-group="{group}"' in t for t in tables), route)
        # every value of a table links to its derivation
        for t in metric_tables(self.pages["#/r/extensions"], "all-extensions"):
            for tr in re.findall(r'<tr class="h-.*?</tr>', t["text"], re.S):
                for td in re.findall(r'<td class="num[^"]*"[^>]*>(.*?)</td>', tr, re.S):
                    if "<b>" in td:
                        self.assertRegex(td, r'<a href="#/cell/')

    def test_a_picker_has_at_most_eight_columns_and_the_other_metrics_are_behind_more_metrics(self):
        for route, page in self.pages.items():
            for picker in re.findall(r'<table class="mtx">.*?</table>', page, re.S):
                self.assertLessEqual(len(re.findall(r'<button type="button" class="mxcol"', picker)), 8, route)
        page = self.pages["#/r/prompts-and-tools"]
        self.assertRegex(page, r'<details class="more mxmore"><summary>More metrics \(\d+\)</summary>')   # closed: nothing in it is chosen
        by = {m["key"]: m for m in self.data["metrics"]}
        keys = next(s for s in self.sections if s["id"] == "prompts-and-tools")["keys"]
        self.assertEqual(len(re.findall(r'class="mcell"', page)), len({(by[k]["workload"], by[k]["lens"], by[k]["word"]) for k in keys}))   # every metric of the section can be chosen from one of the pickers

    def test_two_workloads_with_one_title_are_told_apart_in_the_tables_and_the_picker(self):
        page = app(self.out, "D.metrics.forEach(m=>{if(/^longsession-/.test(m.workload)) m.title='Same title'});console.log(JSON.stringify(A.render(D,'#/r/sessions',{width:1200}).html))")
        titles = re.findall(r'<h3 class="wlh">([^<]*)', page)
        self.assertEqual(len(titles), 2)
        self.assertEqual(len(set(titles)), 2, titles)
        rows = re.findall(r'class="mxrow"[^>]*>([^<]+)</button>', page)
        self.assertEqual(len(set(rows)), len(rows), rows)

    def test_the_docs_say_the_number_of_main_columns(self):
        with open(os.path.join(ROOT, "docs", "design", "DASHBOARD.md"), encoding="utf-8") as f:
            self.assertIn("**At most six main columns**", f.read())
        self.assertEqual(app(self.out, "console.log(JSON.stringify(A.MAIN_MAX))"), MAIN_MAX)


if __name__ == "__main__":
    unittest.main()
