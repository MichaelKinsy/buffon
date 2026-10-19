# SPDX-License-Identifier: Apache-2.0
"""The structure of the results site: the nav, the sections of Results (each reachable, none empty, in order), the control bar and its state in the URL, the old addresses that
redirect, no global metric picker, the harness cards made from the profiles' README heads, and the pages that sit under Method and About. Built from the demo run with the
large write, the extension sweep, faults and the exact agent limits; drawn under Node (see tests/test_dashboard.py)."""
import hashlib
import json
import html as htmlmod
import os
import re
import tempfile
import unittest
import struct
import zlib

from buffon.dashboard import build as dashboard
from tests.report_demo import demo_raw, with_sweep
from tests.telemetry_fixtures import write_dir
from tests.test_dashboard import NODE, app, built, metric_tables, render_all, visible_text
from tests.test_dashboard_profiles import GOOD, SVG, make_png, with_logo, with_mark, write_profile
from tests.test_dashboard_scale import site_data, with_swarms, with_write

ORDER = ["start-up", "prompts-and-tools", "large-writes", "streaming", "sessions", "extensions", "agent-swarming", "reliability", "wire"]   # the sections the demo has data for
FULL = ["start-up", "prompts-and-tools", "large-writes", "streaming", "sessions", "durable", "extensions", "agent-swarming", "reliability", "wire", "other-suites"]   # every section, in the spec order


def nav_of(html):
    head = re.search(r'<nav class="main".*?</nav>', html, re.S).group(0)
    return [t for _, t in re.findall(r'<a href="(#/[^"]*)"[^>]*>([^<]+)</a>', head)]


def rail_of(html):
    m = re.search(r'<nav class="rail".*?</nav>', html, re.S)
    return re.findall(r'href="#/(?:r/([^"?]+)|(?:\?[^"]*)?)"', m.group(0)) if m else []


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Structure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(with_swarms(with_write(with_sweep(demo_raw(rounds=4)))), faith=False)
        cls.views = render_all(cls.out)
        cls.data = site_data(cls.out)
        cls.sections = app(cls.out, "console.log(JSON.stringify(A.Index(D).sections.map(s=>({id:s.id,title:s.title,kind:s.kind,empty:!!s.empty,keys:s.keys||[],head:s.head||null}))))")

    def test_the_nav_is_results_harnesses_method_about_on_every_view_and_the_footer_has_two_links(self):
        for route, text in self.views.items():
            self.assertEqual(nav_of(text), ["Results", "Harnesses", "Method", "About"], route)
            footer = text[text.index('<footer class="site">'):]
            self.assertEqual(re.findall(r">([^<]+)</a>", footer), ["Add a harness", "Submit a result"], route)

    def test_every_section_is_on_the_overview_and_in_the_rail_in_the_spec_order_and_opens_with_data_or_says_it_has_none(self):
        ids = [s["id"] for s in self.sections]
        self.assertEqual(ids, FULL, "every section is listed, with or without data")
        self.assertEqual([s["id"] for s in self.sections if not s["empty"]], ORDER, "the demo has data for these")
        home = self.views["#/"]
        self.assertEqual(len(re.findall(r'<a class="card tile', home)), len(ids))
        for sid in ids:
            self.assertIn(f'href="#/r/{sid}"', home)
            page = self.views[f"#/r/{sid}"]
            self.assertNotIn("<h1>Not found</h1>", page)
            self.assertEqual(re.findall(r'<nav class="rail".*?</nav>', page, re.S)[0].count("<a "), len(ids) + 2)   # the overview, each section and All metrics
            self.assertIn('aria-current="page">' + next(s["title"] for s in self.sections if s["id"] == sid), page)

    def test_no_section_is_empty_it_has_a_chart_and_a_table_of_values_that_link_to_their_derivation_or_says_what_it_will_measure(self):
        for s in self.sections:
            page = self.views[f"#/r/{s['id']}"]
            if s["empty"]:
                self.assertIn("Not run yet", page, s["id"])
                self.assertIn("What it measures", page, s["id"])
                self.assertNotIn("<table", page, s["id"])   # no number is drawn for a section without data
                self.assertNotIn('<svg class="chart"', page, s["id"])
                continue
            self.assertRegex(page, r'<svg class="chart"|class="bars', s["id"])
            self.assertIn("<table", page, s["id"])
            self.assertTrue(re.search(r'<td class="num[^"]*"(?: data-csv-value="[^"]*")?><a href="#/(cell|swarm|fault)/', page), s["id"])   # a value opens its derivation
            if s["kind"] == "metrics":
                self.assertIn(s["head"], s["keys"], s["id"])

    def test_a_section_without_data_names_its_workloads_and_durable_offers_no_command_that_does_not_fill_it(self):
        durable = self.views["#/r/durable"]
        self.assertIn("durable/mixed-3500", durable)
        self.assertNotIn("campaigns/launch-rerun.toml", durable)   # the launch rerun has no durable family: its command would leave the section empty
        self.assertIn("The plan</a>", durable)
        self.assertIn("#/doc/EXTERNAL", self.views["#/r/other-suites"])

    def test_every_metric_is_in_exactly_one_section(self):
        seen = {}
        for s in self.sections:
            for k in s["keys"]:
                self.assertNotIn(k, seen, k)
                seen[k] = s["id"]
        self.assertEqual(set(seen), {m["key"] for m in self.data["metrics"]})

    def column(self, html, key):
        """[(harness slug, data-csv-value)] of one metric, in the order its table draws the harnesses (every harness that has a value in the workload, and no other)."""
        t = next(t for t in metric_tables(html) if key in t["keys"])
        return [(slug, cells[t["keys"].index(key)][1]) for slug, cells in t["rows"]]

    def render(self, route, width=1200):
        return app(self.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(route)},{{width:{width}}}).html))")

    def test_every_metric_is_a_column_of_the_all_metrics_page_under_its_section_and_the_section_pages_hold_the_same_columns(self):
        page = self.views["#/all"]
        tables = metric_tables(page, "all-metrics")
        keys = [k for t in tables for k in t["keys"]]
        self.assertEqual(sorted(keys), sorted(m["key"] for m in self.data["metrics"]))
        groups = re.findall(r'<section class="secg"><h2><a href="#/r/([^"?]+)[^"]*">[^<]*</a> <small>(\d+) metrics?</small>', page)
        self.assertEqual([g[0] for g in groups], [s["id"] for s in self.sections if s["kind"] == "metrics"])
        for sid, n in groups:
            self.assertEqual(int(n), len(next(s for s in self.sections if s["id"] == sid)["keys"]))
            section = self.views[f"#/r/{sid}"]
            mine = [k for t in metric_tables(section, f"all-{sid}") for k in t["keys"]]
            self.assertEqual(len(mine), int(n))
            self.assertEqual(sorted(mine), sorted(next(s for s in self.sections if s["id"] == sid)["keys"]))
        self.assertEqual(page.count('data-csv="all-metrics"'), 1)   # one CSV for the whole page
        self.assertEqual(len(re.findall(r'<table class="data grid" id="t-all-metrics-[^"]*" data-csv-group="all-metrics"[^>]*>', page)), len(tables))
        self.assertIn('aria-current="page">All metrics', page)
        self.assertEqual(re.findall(r'<nav class="rail".*?</nav>', self.views["#/r/start-up"], re.S)[0].count("<a "), len(FULL) + 2)

    def cells_of(self, keys):
        """The number of matrix cells that the metrics of a section make: one for each workload and metric name under a kind."""
        by = {m["key"]: m for m in self.data["metrics"]}
        return len({(by[k]["workload"], by[k]["lens"], by[k]["word"]) for k in keys})

    def test_every_section_has_chips_for_its_metrics_with_the_headline_chosen_and_one_chart_for_each_chosen_metric(self):
        for s in self.sections:
            if s["kind"] != "metrics":
                continue
            page = self.views[f"#/r/{s['id']}"]
            self.assertEqual(len(re.findall(r'<button type="button" class="mcell" aria-pressed="(?:true|false)" aria-label="[^"]*" data-href="#/r/' + s["id"], page)), self.cells_of(s["keys"]), s["id"])
            self.assertEqual(len(re.findall(r'class="mcell" aria-pressed="true"', page)), 1, s["id"])
            self.assertEqual(len(re.findall(r'<section class="card small" id="p-', page)), 1, s["id"])
            self.assertIn(f'id="p-{s["head"]}"', page)
            self.assertIn(f"All metrics in this section ({len(s['keys'])})", page)
            folded = re.findall(r'<details class="(\w+)"', page[page.index('class="viewbar"'):])
            self.assertLessEqual(set(folded), {"wl", "more"}, s["id"])   # only the metrics beyond the main ones and the workloads beyond the first few are folded away

    def test_the_view_switch_draws_every_chosen_metric_in_dots_bars_and_rounds_and_a_line_only_for_the_sweep(self):
        for s in self.sections:
            if s["kind"] != "metrics":
                continue
            keys = ",".join(s["keys"])
            for view, mark in (("dots", r'<g class="series h-\w+"><text class="dl"'), ("bars", r'<div class="bars'), ("rounds", r'<circle class="rd"')):
                page = self.render(f"#/r/{s['id']}?m={keys}&view={view}")
                cards = re.findall(r'<section class="card small" id="p-([^"]+)"(.*?)</section>', page, re.S)
                self.assertEqual([c[0] for c in cards], s["keys"], (s["id"], view))
                for key, body in cards:
                    self.assertRegex(body, mark, (s["id"], view, key))
            self.assertEqual(len(re.findall(r'class="mcell" aria-pressed="true"', page)), self.cells_of(s["keys"]), s["id"])
            line = self.render(f"#/r/{s['id']}?view=line")
            if s["id"] == "extensions":
                self.assertIn('id="sweep-0"', line)
                self.assertIn(">Line</button>", line)
            else:
                self.assertNotIn('id="sweep-0"', line)
                self.assertNotIn(">Line</button>", line)
                self.assertIn('class="card small"', line)   # it falls back to the dots

    def test_a_column_sorts_both_ways_with_cells_that_have_no_number_last_and_ties_in_the_site_order(self):
        key = "overhead-print.cpu_ms"
        site = [h["slug"] for h in self.data["harnesses"]]
        orders = {}
        for direction in ("asc", "desc"):
            rows = self.column(self.render(f"#/r/prompts-and-tools?v=values&sort={key}:{direction}"), key)
            numbers = [float(v) for _, v in rows if v not in ("n/a", "can't run", "not compared") and not v.endswith("API")]
            self.assertEqual(numbers, sorted(numbers, reverse=direction == "desc"), direction)
            self.assertTrue(numbers)
            tail = [v for _, v in rows][len(numbers):]
            self.assertTrue(all(t in ("n/a", "not compared") or t.endswith("API") for t in tail), (direction, tail))   # no number: last in both directions
            orders[direction] = [r[0] for r in rows]
        self.assertEqual(sorted(orders["asc"]), sorted(orders["desc"]))
        self.assertNotEqual(orders["asc"], orders["desc"])
        # every direction is the data sorted by value with the site order breaking a tie, whatever the column holds
        wire = next(m["key"] for m in self.data["metrics"] if m["key"].endswith(".requests"))
        cell = next(c for c in self.data["cells"] if c["key"] == wire)
        ident = {h["slug"]: h["id"] for h in self.data["harnesses"]}
        value = lambda slug: cell["stats"][ident[slug]]["median"] if ident[slug] in cell["stats"] else None
        for direction in ("asc", "desc"):
            rows = self.column(self.render(f"#/r/wire?v=values&sort={wire}:{direction}"), wire)
            have = [s for s in site if value(s) is not None]
            expected = sorted(have, key=lambda s: (value(s) if direction == "asc" else -value(s), site.index(s)))
            self.assertEqual([r[0] for r in rows], expected, direction)   # a harness with no value has no row to put last
        by_name = [r[0] for r in self.column(self.render("#/r/wire?sort=harness:desc"), wire)]
        self.assertEqual(by_name, sorted(by_name, key=lambda s: next(h["name"] for h in self.data["harnesses"] if h["slug"] == s).lower(), reverse=True))

    def test_the_selected_metrics_the_view_the_sort_and_the_filters_round_trip_through_the_url(self):
        routes = ["#/r/prompts-and-tools?m=overhead-print.cpu_ms,overhead-print.peak_rss_mib&sort=overhead-print.cpu_ms:desc&view=bars",
                  "#/r/prompts-and-tools?m=none", "#/all?k=cpu,wall&s=start-up,wire&sort=harness:asc&v=values", "#/r/extensions?view=line", "#/r/prompts-and-tools?view=dots", "#/?view=dots"]
        self.assertEqual(app(self.out, f"console.log(JSON.stringify({json.dumps(routes)}.map(r=>A.serialize(A.parse(r)))))"), routes)
        st = app(self.out, "const s=A.stateOf(A.Index(D),A.parse('#/r/prompts-and-tools?view=rounds&sort=x.y:desc'));console.log(JSON.stringify({view:s.view,sort:s.sort}))")
        self.assertEqual(st, {"view": "rounds", "sort": {"key": "x.y", "dir": "desc"}})
        self.assertEqual(app(self.out, "console.log(JSON.stringify(A.stateOf(A.Index(D),A.parse('#/')).view))"), "bars")
        # the chips and the header buttons are links to the state they give
        page = self.render("#/r/prompts-and-tools?m=overhead-print.cpu_ms,overhead-print.peak_rss_mib&view=bars")
        self.assertEqual(len(re.findall(r'class="mcell" aria-pressed="true"', page)), 2)
        self.assertIn('data-href="#/r/prompts-and-tools?m=overhead-print.peak_rss_mib&amp;view=bars"', page)   # the cell of a chosen metric takes it out
        self.assertRegex(page, r'<button type="button" class="sortb" data-href="#/r/prompts-and-tools\?m=[^"]*&amp;sort=overhead-print\.cpu_ms:asc&amp;view=bars">')

    def test_the_all_metrics_page_filters_by_section_and_by_kind_and_says_so_when_nothing_matches(self):
        some = self.render("#/all?s=start-up,wire")
        self.assertEqual(re.findall(r'<section class="secg"><h2><a href="#/r/([^"?]+)', some), ["start-up", "wire"])
        cpu = self.render("#/all?k=cpu")
        keys = re.findall(r'<a class="info" href="#/metric/([^"?]+)', cpu)
        self.assertTrue(keys)
        self.assertEqual(set(keys), {m["key"] for m in self.data["metrics"] if m["lens"] == "cpu"})
        self.assertIn("No metric matches", self.render("#/all?s=none"))
        self.assertEqual(len(re.findall(r'class="chip m" aria-pressed="true"', cpu)), len([s for s in self.sections if s["kind"] == "metrics"]) + 1)   # every section, and the one kind

    def test_a_row_header_toggles_a_workload_a_column_header_a_metric_name_and_a_cell_one_metric_and_a_one_workload_section_has_one_row(self):
        by = {m["key"]: m for m in self.data["metrics"]}
        sec = next(s for s in self.sections if s["id"] == "prompts-and-tools")
        page = self.render("#/r/prompts-and-tools")
        rows = re.findall(r'<button type="button" class="mxrow" aria-pressed="false" data-href="([^"]*)">([^<]+)</button>', page)
        cols = re.findall(r'<button type="button" class="mxcol" aria-pressed="false" data-href="([^"]*)">([^<]+)</button>', page)
        titles = {by[k]["title"] for k in sec["keys"]}
        words = {by[k]["word"][:1].upper() + by[k]["word"][1:] for k in sec["keys"]}
        self.assertEqual({t for _, t in rows}, titles)
        self.assertEqual({w for _, w in cols}, words)
        self.assertGreater(len(titles), 1)
        main, more = page.split('<details class="more mxmore"')   # the picker of the main metric words, and the one under "More metrics"
        for picker in (main, more):
            kinds = re.findall(r'<th scope="colgroup" colspan="\d+" class="kind">([^<]+)</th>', picker)
            self.assertEqual(kinds, [k for k in ("CPU", "Time", "Memory", "Size", "Wire", "Other") if k in kinds])   # the kind headers, in order
            self.assertTrue(kinds)
        self.assertIn("<summary>More metrics (", more)

        def charts(href):
            return re.findall(r'<section class="card small" id="p-([^"]+)"', self.render(htmlmod.unescape(href)))
        for href, title in rows:   # a row: every metric of the workload
            self.assertEqual(sorted(charts(href)), sorted({sec["head"]} | {k for k in sec["keys"] if by[k]["title"] == title}), title)   # on top of the headline metric that is chosen
        for href, word in cols:    # a column: every workload's metric of that name
            self.assertEqual(sorted(charts(href)), sorted({sec["head"]} | {k for k in sec["keys"] if by[k]["word"][:1].upper() + by[k]["word"][1:] == word}), word)
        # a cell adds one metric to the chosen one; the row that is all chosen takes its metrics out again
        cell = re.search(r'<button type="button" class="mcell" aria-pressed="false" aria-label="([^"]*)" data-href="([^"]*)"', page)
        self.assertEqual(len(charts(cell.group(2))), 2)
        row = rows[0]
        full = self.render(htmlmod.unescape(row[0]))
        off = re.search(r'<button type="button" class="mxrow" aria-pressed="true" data-href="([^"]*)">' + re.escape(row[1]), full)
        self.assertTrue(off, "a row that is all chosen says so")
        self.assertIn("m=none", htmlmod.unescape(off.group(1)))
        # a section of one workload is one row for each of its variants: the 200 KB and the 50 KB file
        one = self.render("#/r/large-writes")
        self.assertEqual(re.findall(r'<button type="button" class="mxrow" aria-pressed="(?:true|false)" data-href="[^"]*">([^<]+)</button>', one), ["Large file write, 200 KB file", "Large file write, 50 KB file"])

    def test_a_section_with_no_data_is_in_the_rail_muted_and_its_tile_says_not_run_yet(self):
        out = built(with_write(demo_raw(rounds=4)), faith=False)
        secs = app(out, "console.log(JSON.stringify(A.Index(D).sections.map(s=>[s.id,!!s.empty])))")
        empty = {sid for sid, e in secs if e}
        self.assertTrue({"agent-swarming", "durable", "other-suites"} <= empty)
        self.assertEqual([sid for sid, _ in secs], FULL)
        views = render_all(out)
        self.assertRegex(views["#/"], r'<a class="card tile off" href="#/r/agent-swarming"><h2>Agent swarming</h2><p class="tile-m">Not run yet</p>')
        rail = re.search(r'<nav class="rail onhome".*?</nav>', views["#/"], re.S).group(0)
        self.assertIn('<a class="off" href="#/r/agent-swarming">Agent swarming</a>', rail)
        self.assertNotIn("<table", views["#/r/agent-swarming"])
        self.assertNotIn('class="ctlbar"', views["#/r/agent-swarming"])

    def test_the_overview_has_no_other_cards_and_no_metric_picker_anywhere(self):
        home = self.views["#/"]
        self.assertEqual(len(re.findall(r'<(?:section|a) class="card', home)), len(self.sections))
        self.assertNotIn('id="write"', home)
        for route, text in self.views.items():
            self.assertNotIn("Choose metrics", text, route)
            self.assertNotIn('data-toggle-list="m"', text, route)
            self.assertNotIn('class="picker"', text, route)
        self.assertNotIn("defaults", self.data)
        self.assertIn(f'<a href="#/all">All {len(self.data["metrics"])} metrics, by section</a>', home)   # every metric is one click away, organised, not picked from a list

    def test_the_control_bar_is_on_results_pages_only_and_the_api_choice_only_where_the_section_has_more_than_one(self):
        for route, text in self.views.items():
            has = 'class="ctlbar"' in text
            live = route.startswith("#/r/") and not next(s["empty"] for s in self.sections if s["id"] == route[4:].split("?")[0])
            self.assertEqual(has, route == "#/" or route.startswith(("#/?", "#/all")) or live, route)
        home = self.views["#/"]
        self.assertEqual(home.count('data-toggle-list="h"'), len(self.data["harnesses"]))
        self.assertIn('data-param="base"', home)
        self.assertNotIn('data-param="api"', home)
        apis = {s["id"]: set() for s in self.sections}
        for m in self.data["metrics"]:
            sid = next(s["id"] for s in self.sections if m["key"] in s["keys"])
            apis[sid] |= {a for a in m["apis"] if a != "-"}
        for s in self.sections:
            text = self.views[f"#/r/{s['id']}"]
            self.assertEqual('data-param="api"' in text, s["kind"] == "metrics" and len(apis[s["id"]]) > 1, s["id"])
        for sid in ("agent-swarming", "reliability"):
            self.assertNotIn('data-param="base"', self.views[f"#/r/{sid}"])   # a count has no ratio

    def test_the_choice_of_harnesses_baseline_mode_and_api_round_trips_through_the_url(self):
        routes = ["#/r/prompts-and-tools?api=chat&base=demo-alpha&h=demo-beta,demo-gamma&v=values", "#/?h=none", "#/r/agent-swarming?e=4g-8c", "#/r/agent-swarming", "#/r/agent-swarming?m=print.fit&view=bars", "#/method/runs", "#/about?at=why-buffon"]
        out = app(self.out, f"console.log(JSON.stringify({json.dumps(routes)}.map(r=>A.serialize(A.parse(r)))))")
        self.assertEqual(out, routes)
        st = app(self.out, "const I=A.Index(D);const s=A.stateOf(I,A.parse('#/?base=demo-alpha&h=demo-gamma,demo-alpha&v=values'));console.log(JSON.stringify({hs:s.hs.map(h=>h.slug),base:s.base.slug,mode:s.mode}))")
        self.assertEqual(st, {"hs": ["demo-alpha", "demo-gamma"], "base": "demo-alpha", "mode": "values"})
        self.assertEqual(app(self.out, "console.log(JSON.stringify(A.stateOf(A.Index(D),A.parse('#/')).mode))"), "ratio")
        got = app(self.out, "const I=A.Index(D);const h=D.harnesses.map(x=>x.slug);console.log(JSON.stringify([A.toggle(I,A.parse('#/'),h[1]),A.toggle(I,A.parse('#/?h='+h.slice(1).join(',')),h[0]),A.toggle(I,A.parse('#/?h='+h[0]),h[0])]))")
        self.assertEqual(got, ["#/?h=" + ",".join(h["slug"] for i, h in enumerate(self.data["harnesses"]) if i != 1), "#/", "#/?h=none"])
        page = app(self.out, "console.log(JSON.stringify(A.render(D,'#/r/prompts-and-tools?h=demo-alpha&v=values',{width:1200}).html))")
        self.assertEqual(len(re.findall(r'class="chip h-\w+" aria-pressed="true"', page)), 1)
        tables = metric_tables(page, "all-prompts-and-tools")
        self.assertTrue(tables)
        for t in tables:
            self.assertEqual([slug for slug, _ in t["rows"]], ["demo-alpha"], t["id"])

    def test_an_address_of_the_earlier_site_redirects_to_its_new_place(self):
        asks = ["#/scale", "#/scale?e=4g-8c", "#/r/many-agents", "#/r/many-agents?m=print.fit&view=bars", "#/runs", "#/compare", "#/?m=overhead-print.cpu_ms&h=demo-alpha", "#/?m=none", "#/doc/README?at=why-buffon", "#/metric/overhead-print.cpu_ms"]
        got = app(self.out, f"console.log(JSON.stringify({json.dumps(asks)}.map(r=>A.redirectOf(D,r))))")
        self.assertEqual(got, ["#/r/agent-swarming", "#/r/agent-swarming?e=4g-8c", "#/r/agent-swarming", "#/r/agent-swarming?m=print.fit&view=bars", "#/method/runs", "#/", "#/r/prompts-and-tools?h=demo-alpha", "#/", "#/about?at=why-buffon", None])
        page = app(self.out, "console.log(JSON.stringify(A.render(D,'#/scale',{width:1200})))")
        self.assertEqual(page["redirect"], "#/r/agent-swarming")

    def test_the_hero_says_what_buffon_is_then_the_name_and_the_framing_once_and_no_harness_count(self):
        home = self.views["#/"]
        hero = re.search(r'<section class="hero">(.*?)</section>', home, re.S).group(1)
        text = re.sub(r"<[^>]+>", "", hero)
        self.assertLess(text.index("Benchmarks for coding agents built on Pi's use cases."), text.index("Named for Buffon"))
        self.assertIn("Pi is the foundation many coding agents build on.", text)
        self.assertIn("parallel boards", text)
        for false_claim in ("lined paper", "1777 Buffon found"):
            self.assertNotIn(false_claim, text)
        self.assertIn('class="hero-art"', hero)   # the needle drop
        self.assertEqual(hero.count("<svg"), 1)
        self.assertRegex(text, r"Measured on .*, 4 rounds\.")
        self.assertNotRegex(text, r"\b\d+ harnesses\b")
        self.assertIn('href="#/method"', hero)
        self.assertIn('href="#/about?at=why-buffon"', hero)
        for route, page in self.views.items():
            if not route.startswith(("#/?", "#/about", "#/doc/")) and route != "#/":
                self.assertNotIn("not a ranking of agents", visible_text(page), route)

    def test_the_rail_of_the_sections_is_on_every_results_page_the_home_included_beside_the_hero_with_overview_chosen(self):
        for route in ("#/", "#/?v=values", "#/r/start-up", "#/all"):
            page = self.views[route] if route in self.views else self.render(route)
            rails = re.findall(r'<nav class="rail[^"]*" aria-label="Sections">.*?</nav>', page, re.S)
            self.assertEqual(len(rails), 1, route)
            self.assertEqual(rails[0].count("<a "), len(FULL) + 2, route)   # Overview, each section, All metrics
            self.assertEqual(rails[0].count('aria-current="page"'), 1, route)
        home = self.views["#/"]
        rail = re.search(r'<nav class="rail onhome" aria-label="Sections">.*?</nav>', home, re.S).group(0)
        self.assertIn('<a href="#/" aria-current="page">Overview</a>', rail)
        columns = re.search(r'<div class="results onhome">(.*)', home, re.S).group(1)
        self.assertTrue(columns.startswith('<nav class="rail onhome"'))   # the rail is the first column, so it starts beside the hero, and is the tab row under the header on a phone
        self.assertLess(columns.index('<section class="hero">'), columns.index('class="ctlbar"'))
        self.assertLess(columns.index('class="ctlbar"'), columns.index('class="tiles"'))
        self.assertGreater(columns.index('<section class="hero">'), columns.index("</nav>"))
        css = open(os.path.join(os.path.dirname(__file__), "..", "buffon", "dashboard", "assets", "app.css")).read()
        self.assertRegex(css, r"\.rail \{[^}]*position: sticky")   # the rail stays while the content scrolls

    def test_a_tile_has_one_factual_line_from_the_lowest_to_the_highest_value_and_no_verdict(self):
        home = self.views["#/"]
        lines = re.findall(r'<p class="tile-r">(.*?)</p>', home)
        self.assertGreaterEqual(len(lines), 3)
        for line in lines:
            self.assertRegex(htmlmod.unescape(line), r"^from .+ \(.+\) to .+ \(.+\)$")
            self.assertNotIn("×", line, "the line is in values with units, not ratios, even in ratio mode")
            self.assertNotRegex(line, r"\d to \d", "a range in the line is written with an en dash")
            self.assertNotIn("—", line)
            for word in ("best", "worst", "fastest", "slowest", "winner", "better", "worse"):
                self.assertNotIn(word, line.lower())

    def test_the_spotlight_and_the_motion_rules_are_in_the_page(self):
        css = open(os.path.join(os.path.dirname(__file__), "..", "buffon", "dashboard", "assets", "app.css")).read()
        js = open(os.path.join(os.path.dirname(__file__), "..", "buffon", "dashboard", "assets", "app.js")).read()
        self.assertIn(".dim {", css)
        self.assertIn("prefers-reduced-motion: reduce", css)
        self.assertNotIn("@keyframes", css)   # motion is for a change of state only
        for event in ("pointerover", "focusin", "pointerdown"):
            self.assertIn(f'addEventListener("{event}", function (e) {{ ' if event != "focusin" else 'addEventListener("focusin"', js)

    def test_the_readme_says_what_the_spec_says_about_the_name(self):
        readme = open(os.path.join(os.path.dirname(__file__), "..", "README.md")).read()
        self.assertIn("Benchmarks for coding agents built on Pi's use cases.", readme)
        self.assertIn("parallel boards", readme)
        self.assertIn("Buffon asked only for the chance", readme)
        for false_claim in ("lined paper", "In 1777 Buffon found"):
            self.assertNotIn(false_claim, readme)

    def test_no_card_has_a_coloured_edge_and_a_harness_colour_is_a_dot_or_a_mark_only(self):
        css = open(os.path.join(os.path.dirname(__file__), "..", "buffon", "dashboard", "assets", "app.css")).read()
        self.assertNotRegex(css, r"border-(top|left|right|bottom)\s*:\s*\d+px solid var\(--h\)")
        self.assertNotRegex(css, r"\.card[^{]*\{[^}]*border-top:[^}]*var\(--h")

    def test_the_section_page_of_the_extensions_is_a_line_for_each_harness_and_the_agents_page_has_bars(self):
        ext = self.render("#/r/extensions?view=line")
        self.assertIn("by number of extensions", ext)
        self.assertEqual(len(re.findall(r'<text class="elabel"', re.search(r'<svg class="chart".*?</svg>', ext, re.S).group(0))), 4)
        agents = self.views["#/r/agent-swarming"]
        self.assertIn('class="brow h-', agents)
        self.assertIn("with 10 extensions", agents)   # a row of the picker
        self.assertIn('id="agents-main"', agents)
        self.assertIn("Memory per agent", agents)

    def test_the_can_t_run_line_shows_the_short_reason_on_hover_and_the_full_reason_is_on_the_harness_page(self):
        pty = self.views["#/r/start-up"]
        tips = re.findall(r'<p class="notrun cant">.*?<span tabindex="0" data-tip="([^"]*)">demo-gamma</span>', pty, re.S)
        self.assertTrue(tips)
        tip = tips[0].replace("&#39;", "'")
        self.assertIn("no terminal mode", tip)
        self.assertNotIn("\n", tip)
        self.assertNotIn("full-screen view", tip)
        self.assertIn("full-screen view", self.views["#/harness/demo-gamma"])

    def test_the_harness_page_has_a_strip_with_a_row_for_each_section_scope_how_it_ran_and_a_folded_every_measure(self):
        page = self.views["#/harness/demo-alpha"]
        self.assertIn('id="strip-demo-alpha"', page)
        self.assertLess(page.index('id="strip-demo-alpha"'), page.index('id="scope-demo-alpha"'))
        self.assertLess(page.index('id="scope-demo-alpha"'), page.index('id="ran-demo-alpha"'))
        self.assertIn("<summary>Every measure</summary>", page)
        strip = re.search(r'id="strip-demo-alpha".*?</section>', page, re.S).group(0)
        for s in self.sections:
            if s["kind"] == "metrics":
                self.assertIn(f'href="#/r/{s["id"]}"', strip)
        self.assertLessEqual(len(re.findall(r"[.!?](?:\s|<)", re.search(r'<p class="sub">(.*?)</p>', strip, re.S).group(1))), 2)

    def test_runs_and_data_is_under_method_and_the_old_runs_view_is_gone(self):
        self.assertIn("Runs and data", self.views["#/method"])
        self.assertIn("run-checks", self.views["#/method/runs"])
        self.assertNotIn("#/runs", "".join(self.views.values()))
        self.assertIn("Fairness", self.views["#/method"])
        self.assertIn('id="doc-README"', self.views["#/about"])
        self.assertIn('id="why-buffon"', self.views["#/about"])

    def test_a_fault_has_its_verdict_for_each_harness_with_a_derivation_page(self):
        page = self.views["#/r/reliability"]
        self.assertIn("Faults passed", page)
        self.assertTrue(re.search(r'<a href="#/fault/[^"]+"', page))
        fault = next(v for r, v in self.views.items() if r.startswith("#/fault/"))
        self.assertIn("How it was judged", fault)
        self.assertEqual(sum(len(f["arms"]) for f in self.data["faults"]), len([r for r in self.views if r.startswith("#/fault/")]))


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class HarnessCards(unittest.TestCase):
    """The harness index is a preview of each project's own README head, from the profile's stored fields, with one square mark on every card."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        folder = os.path.join(cls.tmp, "profiles")
        os.makedirs(folder)
        words = " ".join(f"w{i}" for i in range(90))
        cls.alpha = with_mark(folder, dict(GOOD, project="Alpha", harnesses=["demo-alpha"], links={"home": "https://a.example", "repo": "https://github.com/o/alpha", "docs": "https://a.example/docs"}), SVG, "alpha-mark.svg")
        cls.alpha.update({"readme_title": "Alpha, a demo", "readme_head": ["First paragraph of the README.", words], "readme_url": "https://github.com/o/alpha/blob/v1.0.0/README.md", "readme_ref": "v1.0.0"})
        write_profile(folder, cls.alpha, "alpha.toml")
        plain = dict(GOOD, project="Beta", harnesses=["demo-beta"], links={"home": "https://b.example", "repo": "https://github.com/o/beta"})
        plain.update({"readme_title": "Beta", "readme_head": ["Beta has no mark."], "readme_url": "https://github.com/o/beta/blob/abcdef0123456789abcdef0123456789abcdef01/README.md", "readme_ref": "abcdef0123456789abcdef0123456789abcdef01"})
        write_profile(folder, plain, "beta.toml")
        cls.wide = with_logo(folder, with_mark(folder, dict(GOOD, project="Pi", harnesses=["pi-node"], links={"home": "https://pi.example", "repo": "https://github.com/o/pi"}), make_png(128, 128), "pi-mark.png", mark_crop=[0, 0, 64, 64]),
                             content=make_png(600, 200), name="pi.png")
        cls.wide.update({"readme_title": "Gamma splash", "readme_head": ["A wide picture opens this README."], "readme_url": "https://github.com/o/pi/blob/v1.0.0/README.md", "readme_ref": "v1.0.0", "logo_alt": "Pi splash screen"})
        write_profile(folder, cls.wide, "pi.toml")
        # a profile for an arm of the registry that no loaded run has data for
        cls.octet = with_mark(folder, dict(GOOD, project="octet", harnesses=["octet"], links={"home": "https://o.example", "repo": "https://github.com/o/octet"}), SVG, "octet-mark.svg")
        cls.octet.update({"readme_title": "Octet README", "readme_head": ["A Rust agent."], "readme_url": "https://github.com/o/octet/blob/v1.0.0/README.md", "readme_ref": "v1.0.0"})
        write_profile(folder, cls.octet, "octet.toml")
        src = write_dir(os.path.join(cls.tmp, "run"), demo_raw(rounds=4))
        cls.out = os.path.join(cls.tmp, "site")
        dashboard.build([src], cls.out, profiles_dir=folder)
        cls.page = cls.route("#/harnesses")

    @classmethod
    def route(cls, hash_):
        return app(cls.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(hash_)},{{width:1200}}).html))")

    def card(self, title):
        return next(c for c in re.findall(r'<article class="card prof">.*?</article>', self.page, re.S) if title in c)

    def test_a_card_leads_with_its_mark_then_the_title_and_shows_the_readme_head_clipped_at_about_sixty_words_the_source_the_versions_the_maker_and_the_links(self):
        c = self.card("Alpha, a demo")
        self.assertTrue(c.startswith('<article class="card prof"><div class="phd1"><a class="pmark fit" href="#/harness/demo-alpha"><img src="assets/profiles/alpha-mark.svg" alt="Alpha logo"></a><h2 class="ptitle"><a href="#/harness/demo-alpha">Alpha, a demo</a></h2></div>'), c[:300])
        head = re.sub(r"<[^>]+>", " ", re.search(r'<div class="phead">(.*?)</div>', c, re.S).group(1))
        self.assertIn(self.alpha["readme_head"][0], head)   # the words are the profile's own
        words = head.split()
        self.assertTrue(55 <= len(words) <= 62, len(words))
        self.assertTrue(head.strip().endswith("…"))
        self.assertIn('README at <a href="https://github.com/o/alpha/blob/v1.0.0/README.md">o/alpha@v1.0.0</a>, read 2026-10-18', c)
        self.assertIn('class="vchip', c)
        self.assertIn("By <a", c)
        self.assertRegex(c, r'Home</a> · <a href="https://github.com/o/alpha">Code</a> · <a href="https://a.example/docs">Docs</a>')

    def test_a_short_readme_head_is_the_profile_text_unchanged(self):
        c = self.card("Beta has no mark")
        self.assertIn('<p class="their-words raw">Beta has no mark.</p>', c)

    def test_every_card_has_exactly_one_mark_and_no_wide_picture(self):
        cards = re.findall(r'<article class="card prof">.*?</article>', self.page, re.S)
        self.assertGreaterEqual(len(cards), 5)
        for c in cards:
            self.assertEqual(len(re.findall(r'class="pmark ', c)), 1, c[:200])
            self.assertLessEqual(len(re.findall(r"<img\b", c)), 1, c[:200])
            self.assertNotIn("pfig", c)
            self.assertNotIn("pstrip", c)

    def test_a_project_without_a_mark_gets_its_initials_in_the_mono_face_and_no_placeholder_picture(self):
        c = self.card("Beta has no mark")
        self.assertNotIn("<img", c)
        self.assertRegex(c, r'<a class="pmark mono" href="#/harness/demo-beta" aria-label="Beta"><span aria-hidden="true">Be</span></a>')
        self.assertIn("o/beta@abcdef0", c)   # a commit ref is short

    def test_a_harness_without_a_profile_is_a_card_with_a_monogram_that_says_so(self):
        c = self.card("demo-gamma")
        self.assertIn("No profile yet.", c)
        self.assertIn('class="pmark mono"', c)

    def test_a_cropped_mark_fills_the_tile_and_keeps_its_pixels_sharp(self):
        c = self.card("Gamma splash")
        self.assertIn('<a class="pmark fill" href="#/harness/pi-node"><img src="assets/profiles/pi-mark.png" alt="Pi logo" class="px"></a>', c)
        css = open(os.path.join(os.path.dirname(__file__), "..", "buffon", "dashboard", "assets", "app.css")).read()
        self.assertRegex(css, r"\.pmark \{[^}]*width: 64px; height: 64px")
        self.assertRegex(css, r"\.pmark\.fill img \{[^}]*image-rendering: pixelated")

    def test_the_readme_picture_is_on_the_harness_page_only_below_the_head_with_its_source_line(self):
        page = self.route("#/harness/pi-node")
        fig = re.search(r'<figure class="pfig">.*?</figure>', page, re.S).group(0)
        self.assertIn("<figcaption>From its README</figcaption>", fig)
        self.assertIn('<img src="assets/profiles/pi.png" alt="Pi splash screen">', fig)
        self.assertRegex(fig, r'<p class="src"><cite>from <a href="https://x\.example/logo">')
        self.assertLess(page.index('class="pmark'), page.index("<figure"))
        self.assertEqual(page.count('class="pmark '), 1)
        self.assertNotIn("pfig", self.route("#/harness/demo-alpha"))   # a project with no README picture has no figure

    def test_the_card_has_no_colour_edge_and_the_harness_page_repeats_the_head(self):
        for c in re.findall(r'<article class="card prof">', self.page):
            self.assertNotIn("border-top", c)
        page = self.route("#/harness/demo-alpha")
        self.assertIn("assets/profiles/alpha-mark.svg", page)
        self.assertIn("README at", page)

    def test_the_site_carries_each_picture_the_profile_hashes_and_nothing_is_fetched(self):
        for data, keys in ((self.alpha, ("mark",)), (self.wide, ("mark", "logo"))):
            for key in keys:
                with open(os.path.join(self.out, "assets", "profiles", data[key]), "rb") as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), data[key + "_sha256"], key)
        for tag in re.findall(r"<img\b[^>]*>", self.page):
            self.assertNotRegex(tag, r'src="(?:https?:)?//')

    def test_a_profiled_arm_with_no_samples_is_on_the_harnesses_page_with_a_not_measured_chip_and_in_no_data_view(self):
        c = self.card("Octet README")
        self.assertIn('<span class="vchip off">Not measured yet</span>', c)
        self.assertNotRegex(c, r'class="vchip(?! off)')   # no version chip, no measured version
        self.assertEqual(len(re.findall(r'class="pmark ', c)), 1)
        self.assertIn('href="#/harness/octet"', c)
        info = app(self.out, "console.log(JSON.stringify([D.harnesses.map(h=>h.id), D.unmeasured.map(h=>h.id), D.cells.some(c=>Object.keys(c.stats).indexOf('octet')>=0), A.routes(D).filter(r=>/octet/.test(r))]))")
        self.assertNotIn("octet", info[0])
        self.assertEqual(info[1], ["octet"])
        self.assertFalse(info[2])
        self.assertEqual(info[3], ["#/harness/octet"])
        for route in ("#/", "#/all", "#/r/prompts-and-tools"):
            self.assertNotIn("octet", self.route(route).lower(), route)

    def test_the_page_of_a_harness_with_no_samples_shows_its_scope_from_the_manifest_and_no_number(self):
        page = self.route("#/harness/octet")
        self.assertNotIn("Not found", page)
        self.assertIn("It can run", page)
        self.assertIn("Can't run (", page)
        self.assertIn("extensions are not loaded", page)   # the manifest's reason for the ten extensions
        self.assertIn("It is in the launch rerun's core family.", page)
        self.assertIn('<span class="vchip off">Not measured yet</span>', page)
        for absent in ("<table", "class=\"hbars", "<svg class=\"chart\"", "×"):
            self.assertNotIn(absent, page)


if __name__ == "__main__":
    unittest.main()
