# SPDX-License-Identifier: Apache-2.0
"""One name, one unit and one number format for a metric on every view of the dashboard; one order and one colour for each harness; no control that does nothing; charts that
fit a 390 px screen. Built from the demo run with swarm ladders, drawn under Node (see tests/test_dashboard.py). The layout check at 390 px in a real browser is
tools/shotkit (docs/design/DASHBOARD.md, "Checking the layout")."""
import html as htmlmod
import json
import re
import unittest

from tests.report_demo import demo_raw
from tests.scale_demo import demo_swarms
from tests.test_dashboard import NODE, app, built, metric_tables, render_all
from tests.test_dashboard_scale import AGENTS, agent_route, main_card, plain, site_data, with_swarms, with_write

def with_second_api(raw):
    """The demo run with overhead/print also on the Anthropic wire API (not for demo-gamma, which does not speak it), so a section has two APIs."""
    extra = [{**s, "api": "anthropic-messages"} for s in raw["samples"] if s["scenario"] == "overhead/print" and s["arm"] != "demo-gamma"]
    return {**raw, "samples": raw["samples"] + extra}


def run(out, js):
    return app(out, js)


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class OneFormat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(with_swarms(with_write(demo_raw(rounds=4))), faith=False)
        cls.views = render_all(cls.out, [agent_route("rpc", "mem_per_agent_mib")])
        cls.data = site_data(cls.out)

    def test_the_formatter_has_three_digits_and_switches_unit_at_a_second_and_a_gibibyte(self):
        got = run(self.out, "console.log(JSON.stringify([A.val(1711.2,'ms'),A.val(999.4,'ms'),A.val(420.24,'ms of CPU time'),A.val(6.5612,'ms'),A.val(1024,'MiB'),A.val(1536,'MiB'),A.val(512,'MiB'),"
                            "A.val(4096,'MiB'),A.times(1.5),A.times(0.01634),A.times(152.4),A.val(18500000000,'instructions'),A.val(0.0412,'ms')]))")
        self.assertEqual(got, ["1.71 s", "999 ms", "420 ms", "6.56 ms", "1 GiB", "1.5 GiB", "512 MiB", "4 GiB", "1.50×", "0.0163×", "152×", "18.5 G instr", "0.0412 ms"])

    def test_one_value_is_one_string_in_the_tile_the_table_the_chart_and_the_tooltip(self):
        # a cell of a section: its median in the overview tile, the main table, the primary chart and its table, the bars of the metric page, and in the tooltips
        d = self.data
        key = "overhead-print.cpu_ms"
        cell = next(c for c in d["cells"] if c["key"] == key and c["api_short"] in ("-", "chat"))
        api = "" if cell["api_short"] == "-" else "?api=" + cell["api_short"]
        h = next(h for h in d["harnesses"] if h["id"] in cell["stats"])
        median = cell["stats"][h["id"]]["median"]
        want = run(self.out, f"console.log(JSON.stringify(A.val({median!r},{json.dumps(cell['unit'])})))")
        render = lambda route: run(self.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(route)},{{width:1200}}).html))")
        vq = (api + "&v=values") if api else "?v=values"
        home, section, metric = render("#/" + vq), render("#/r/prompts-and-tools" + vq), render("#/metric/" + key + api)
        main = run(self.out, "console.log(JSON.stringify(A.Index(D).sec['prompts-and-tools'].keys))")
        n, u = want.rsplit(" ", 1) if " " in want else (want, "")
        t = next(t for t in metric_tables(section, "all-prompts-and-tools") if key in t["keys"])
        mine = re.findall(r'<td class="num.*?</td>', re.search(r'<tr class="h-[^"]*"[^>]*><th scope="row" class="hn1"[^>]*>(?:(?!</tr>).)*?href="#/harness/' + h["slug"] + r'".*?</tr>', t["text"], re.S).group(0), re.S)[t["keys"].index(key)]
        self.assertIn(f"<b>{n}</b>", mine)   # the main table
        self.assertIn(f"median {want}", htmlmod.unescape(mine))   # its tooltip
        tile = re.search(r'<a class="card tile" href="#/r/prompts-and-tools[^"]*">.*?</a>', home, re.S).group(0)
        self.assertIn(f"median {want}", htmlmod.unescape(tile))   # the tooltip of the dot in the tile
        primary = re.search(r'<section class="card small" id="p-' + re.escape(key) + r'".*?</section>', section, re.S).group(0)
        self.assertIn(f"median {want}", htmlmod.unescape(primary))   # the tooltip of the dot in the chart
        drawn = render("#/r/prompts-and-tools" + vq + "&view=bars")
        card = re.search(r'<section class="card small" id="p-' + re.escape(key) + r'".*?</section>', drawn, re.S).group(0)
        self.assertIn(f"<b>{want}</b>", card)   # the label of the bar in the Bars view
        self.assertIn(f"median {want}", htmlmod.unescape(card))
        bars = re.search(r'<div class="brow h-[^"]*"[^>]*>(?:(?!<div class="brow).)*?href="#/harness/' + h["slug"] + r'".*?</div>(?=<div class="brow|</div>)', metric, re.S).group(0)
        self.assertIn(f"<b>{want}</b>", bars)   # the label on the bar
        self.assertIn(f"median {want}", htmlmod.unescape(bars))   # its tooltip
        self.assertIn(f">{want}</td>", re.search(r'<div class="as-table" hidden>.*?</table>', metric, re.S).group(0))   # the table view

    def test_a_scale_value_is_one_string_in_the_chart_the_table_and_the_derivation(self):
        env = self.data["scale"]["envelopes"][0]
        r = next(r for r in env["kinds"]["rpc"]["arms"]["pi-node"]["rungs"] if r["n"] == 8)
        want = run(self.out, f"console.log(JSON.stringify(A.val({r['med']['mem_per_agent_mib']!r},'MiB')))")
        card = main_card(self.views[agent_route("rpc", "mem_per_agent_mib")])
        self.assertIn(f"Memory per agent {want}", htmlmod.unescape(card))   # the tooltip of the point
        derivation = next(v for k, v in self.views.items() if k.startswith("#/swarm/4g-8c/rpc/pi-node/8"))
        self.assertIn(f"<b>{want}</b>", derivation)

    def test_no_view_shows_a_time_in_ms_above_a_second_or_a_memory_in_mib_above_a_gibibyte(self):
        found = 0
        for route, text in self.views.items():
            if route.startswith(("#/doc/", "#/glossary", "#/runs")):
                continue
            body = htmlmod.unescape(plain(re.sub(r"<(script|style)>.*?</\1>", "", text, flags=re.S)))
            for number, unit in re.findall(r"(?<![\w.,])(\d[\d,]*(?:\.\d+)?) (ms|MiB)\b", body):
                found += 1
                x = float(number.replace(",", ""))
                self.assertLess(x, 1000 if unit == "ms" else 1024, f"{route}: {number} {unit}")
        self.assertGreater(found, 50)

    def test_a_ratio_has_three_significant_digits_on_every_view(self):
        for route, text in self.views.items():
            if route.startswith("#/doc/"):
                continue
            text = re.sub(r"<svg.*?</svg>", " ", text, flags=re.S)   # an axis tick label is a round number, not a ratio
            for m in re.findall(r"(?<![\w.])(\d+\.\d+)×", htmlmod.unescape(plain(text))):
                digits = m.replace(".", "").lstrip("0")
                self.assertEqual(len(digits), 3, f"{route}: {m}×") if float(m) < 1000 else None


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class OneOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(with_swarms(with_write(demo_raw(rounds=4))), faith=False)
        cls.views = render_all(cls.out)
        cls.data = site_data(cls.out)
        cls.order = [h["slug"] for h in cls.data["harnesses"]]
        cls.colour = {h["slug"]: h["colour"] for h in cls.data["harnesses"]}

    def harnesses_in(self, html, pattern):
        return [m for m in re.findall(pattern, html)]

    def assertInOrder(self, slugs, where):
        self.assertEqual(slugs, [s for s in self.order if s in slugs], where)

    def test_the_harnesses_are_in_the_same_order_in_every_view_that_lists_them(self):
        row = r'<th scope="row" class="hn1"[^>]*><a class="hn" href="#/harness/([^"]+)"'
        listed = 0
        for route, text in self.views.items():
            if route.startswith("#/r/") and "sort=" not in route:   # a reader's sort is the one exception to the site order
                for table in re.findall(r"<table.*?</table>", text, re.S):
                    slugs = re.findall(row, table)
                    self.assertInOrder(slugs, route)
                    listed += len(slugs)
                for card in re.findall(r'<section class="card small" id="agents-main".*?</section>', text, re.S):
                    self.assertInOrder(re.findall(r'href="#/harness/([^"]+)"', card), "fit bars")
            if route.startswith("#/metric/"):
                bars = re.findall(r'<div class="brow h-[^"]*"[^>]*><span class="bn"><a class="hn" href="#/harness/([^"]+)"', text)
                self.assertInOrder(bars, route)
                self.assertGreater(len(bars), 1)
        self.assertGreater(listed, 20)
        names = {h["slug"]: h["name"] for h in self.data["harnesses"]}
        by_name = {v: k for k, v in names.items()}
        for legend in re.findall(r'<div class="legend">(.*?)</div>', self.views["#/r/agent-swarming"] + self.views["#/metric/overhead-print.cpu_ms"], re.S):
            shown = [n for n in re.findall(r'</i>([^<]+)</span>', legend)]
            self.assertInOrder([by_name[n] for n in shown if n in by_name], "legend")

    def test_a_harness_keeps_its_colour_in_every_view(self):
        for route, text in self.views.items():
            if route.startswith("#/doc/"):
                continue
            for cls, slug in re.findall(r'class="(?:brow|hn1|chip)? ?h-(\w+)"[^>]*>.{0,400}?href="#/harness/([^"]+)"', text, re.S):
                if slug in self.colour:
                    self.assertEqual(cls, self.colour[slug], f"{route}: {slug}")
        for h in self.data["harnesses"]:
            self.assertRegex(self.views["#/"], r'class="chip h-' + h["colour"] + r'"[^>]*>(?:<[^>]+>)*' + r'.{0,60}' + re.escape(h["name"].split(" (")[0]))


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class NoIdleControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(with_second_api(with_swarms(with_write(demo_raw(rounds=4)))), faith=False)
        cls.views = render_all(cls.out)
        cls.data = site_data(cls.out)

    def test_a_page_with_no_harness_list_or_ratio_has_no_harness_api_or_baseline_control(self):
        for route, text in self.views.items():
            if route in ("#/method", "#/method/runs", "#/glossary", "#/about") or route.startswith(("#/swarm/", "#/doc/", "#/logs/")):
                self.assertNotIn("data-toggle-list", text, route)
                self.assertNotRegex(text, r'data-param="(api|base)"', route)
                self.assertNotRegex(text, r'data-href="[^"]*[?&]api=', route)

    def test_the_baseline_choice_is_shown_only_where_a_ratio_is(self):
        sections = run(self.out, "console.log(JSON.stringify(A.Index(D).sections.map(s=>({id:s.id,kind:s.kind}))))")
        self.assertIn('data-param="base"', self.views["#/"])
        for s in sections:
            self.assertEqual('data-param="base"' in self.views[f"#/r/{s['id']}"], s["kind"] == "metrics", s["id"])
        for route, text in self.views.items():
            if route.startswith("#/metric/"):
                self.assertIn('data-param="base"', text)   # the ratio chips and the ratio column of the table
                self.assertRegex(text, r'class="chip-r"|<td class="num">1.00×')

    def test_the_api_choice_is_shown_only_where_the_open_section_has_more_than_one_api(self):
        sections = run(self.out, "console.log(JSON.stringify(A.Index(D).sections.map(s=>({id:s.id,kind:s.kind,keys:s.keys||[]}))))")
        apis = {m["key"]: {a for a in m["apis"] if a != "-"} for m in self.data["metrics"]}
        self.assertNotIn('data-param="api"', self.views["#/"])
        shown = 0
        for s in sections:
            if s["kind"] == "metrics":
                multi = len(set().union(*[apis[k] for k in s["keys"]])) > 1
                self.assertEqual('data-param="api"' in self.views[f"#/r/{s['id']}"], multi, s["id"])
                shown += multi
            elif s["kind"] == "agents":
                self.assertNotIn('data-param="api"', self.views[f"#/r/{s['id']}"], s["id"])
        self.assertGreater(shown, 0, "the demo has a section on two APIs")
        for m in self.data["metrics"]:
            text = self.views[f"#/metric/{m['key']}"]
            self.assertEqual(bool(re.search(r'data-href="#/metric/[^"]*api=', text)), len(m["apis"]) > 1, m["key"])

    def test_the_harness_chips_sit_above_the_results_and_there_is_one_for_each_harness(self):
        home = self.views["#/"]
        self.assertLess(home.index('class="ctlbar"'), home.index('class="tiles"'))
        self.assertEqual(home.count("data-toggle-list=\"h\""), len(self.data["harnesses"]))
        page = self.views["#/r/prompts-and-tools"]
        self.assertLess(page.index('class="ctlbar"'), page.index('class="results"'))
        self.assertEqual(page.count("data-toggle-list=\"h\""), len(self.data["harnesses"]))


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class SmallScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(with_swarms(with_write(demo_raw(rounds=4))), faith=False)
        cls.data = site_data(cls.out)

    def test_every_chart_is_drawn_no_wider_than_a_390_px_screen_and_the_line_charts_at_one_height(self):
        views = app(self.out, "const o={};A.routes(D).concat(['#/r/agent-swarming?m=rpc.turns_per_s']).forEach(r=>{o[r]=A.render(D,r,{width:342}).html});console.log(JSON.stringify(o))")
        seen = set()
        for route, text in views.items():
            for svg in re.findall(r'<svg class="chart".*?</svg>', text, re.S):
                w, h = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups()
                self.assertLessEqual(int(w), 342, route)
                if 'class="unit"' in svg:   # a line chart (plotFrame); a dot plot is as tall as its rows
                    seen.add(int(h))
        self.assertEqual(seen, {220}, "the line charts share one height")

    def test_the_page_shell_never_asks_for_more_than_the_screen(self):
        css = open(__file__.replace("tests/test_dashboard_consistency.py", "buffon/dashboard/assets/app.css")).read()
        self.assertRegex(css, r"@media \(max-width: 640px\)[^}]*\{[^@]*table\.kv, table\.kv tbody, table\.kv tr, table\.kv th, table\.kv td \{ display: block")
        self.assertIn(".tablewrap table.data th:first-child", css)   # a table scrolls inside its card with its first column in place
        self.assertRegex(css, r"\.tablewrap \{ overflow-x: auto; \}")


if __name__ == "__main__":
    unittest.main()


def built_two_runs():
    """Run 1: the demo grid on quiet dedicated hardware. Run 2: the swarm ladders only, provisional (not quiet), as the Scale run of a real site can be."""
    import os
    import tempfile
    from buffon.dashboard import build as dashboard
    from tests.telemetry_fixtures import write_dir
    tmp = tempfile.mkdtemp()
    grid = demo_raw(rounds=4, quiet=True)
    swarm = demo_raw(rounds=4, quiet=False)
    samples, skipped = demo_swarms()
    swarm["samples"], swarm["skipped"] = samples, skipped
    out = os.path.join(tmp, "site")
    dashboard.build([write_dir(os.path.join(tmp, "run1"), grid), write_dir(os.path.join(tmp, "run2"), swarm)], out)
    return out


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class ProvisionalBadge(unittest.TestCase):
    """The badge belongs to a value, a chart or a card of a run that was not on quiet dedicated hardware, and nowhere else: not to the frame, and not to a run that was quiet."""

    @classmethod
    def setUpClass(cls):
        cls.out = built_two_runs()
        cls.views = render_all(cls.out)
        cls.data = site_data(cls.out)

    def test_each_run_has_its_own_trust_label(self):
        self.assertEqual([r["provisional"] for r in self.data["runs"]], [False, True])
        self.assertTrue(self.data["runs"][1]["provisional_reasons"])
        self.assertEqual(self.data["runs"][0]["provisional_reasons"], [])

    def test_no_cell_of_the_quiet_run_carries_the_badge_and_the_scale_values_of_the_provisional_run_do(self):
        for route, text in self.views.items():
            if route.startswith(("#/cell/", "#/metric/", "#/harness/")) or route in ("#/", "#/?v=ratio") or (route.startswith("#/r/") and not route.startswith("#/r/agent-swarming")):
                body = text[text.index("<main"):]
                body = re.sub(r'<a class="card tile" href="#/r/agent-swarming[^"]*">.*?</a>', "", body, flags=re.S)   # the Agent swarming tile is the provisional run's
                self.assertNotIn('class="prov"', body, route)
        scale = self.views["#/r/agent-swarming"]
        self.assertEqual(scale.count('<span class="prov"'), 1)   # one badge, in the head of the page
        for route, text in self.views.items():
            if route.startswith("#/swarm/"):
                self.assertIn('class="prov"', text, route)
        tile = re.search(r'<a class="card tile" href="#/r/agent-swarming[^"]*">.*?</a>', self.views["#/"], re.S).group(0)
        self.assertIn('class="prov"', tile)

    def test_the_run_card_says_so_and_the_checks_table_marks_the_column(self):
        runs = self.views["#/method/runs"]
        cards = re.findall(r'<section class="card run">.*?</section>', runs, re.S)
        self.assertEqual([c.count('class="prov"') for c in cards], [0, 1])
        checks = re.search(r'<section class="card" id="run-checks".*?</section>', runs, re.S).group(0)
        self.assertEqual(checks.count('class="prov"'), checks.count("<table"))   # the provisional run's column is marked in each table

    def test_a_site_whose_runs_are_all_quiet_has_no_badge_anywhere(self):
        out = built(with_swarms(with_write(demo_raw(rounds=4, quiet=True))), faith=False)
        for route, text in render_all(out).items():
            self.assertNotIn('class="prov"', text, route)


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class StepOne(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(with_second_api(with_swarms(with_write(demo_raw(rounds=4)))), faith=False)
        cls.views = render_all(cls.out)
        cls.data = site_data(cls.out)

    def test_every_line_chart_names_each_line_at_its_end(self):
        found = 0
        for route, text in self.views.items():
            for svg in re.findall(r'<svg class="chart".*?</svg>', text, re.S):
                lines = len(re.findall(r"<polyline", svg))
                if not lines:
                    continue
                found += 1
                self.assertGreaterEqual(len(re.findall(r'class="elabel"', svg)), lines, route)   # a name for each line (a harness with one point has a name and no polyline)
        self.assertGreater(found, 50)
        svg = re.search(r'<svg class="chart"[^>]*aria-label="every round of[^"]*".*?</svg>', self.views["#/metric/overhead-print.cpu_ms"], re.S).group(0)
        self.assertEqual(len(re.findall(r"<polyline", svg)), len(re.findall(r'class="elabel"', svg)))
        self.assertNotIn('class="legend"', self.views["#/metric/overhead-print.cpu_ms"])   # the names are on the lines: no legend above the chart

    def test_line_end_names_sit_in_a_gutter_outside_the_plot_whole_with_a_leader_from_the_last_point(self):
        checked = 0
        for width in (342, 1200):
            views = app(self.out, f"const o={{}};['#/r/agent-swarming?m=rpc.mem_per_agent_mib&view=line','#/r/extensions?view=line','#/metric/overhead-print.cpu_ms'].forEach(r=>{{o[r]=A.render(D,r,{{width:{width}}}).html}});console.log(JSON.stringify(o))")
            for route, text in views.items():
                for svg in re.findall(r'<svg class="chart".*?</svg>', text, re.S):
                    labels = re.findall(r'<text class="elabel" x="([\d.]+)" y="([\d.]+)"><title>([^<]+)</title>(.*?)</text>', svg, re.S)
                    if not labels:
                        continue
                    right = max(float(m) for m in re.findall(r'<line class="gl" x1="[\d.]+" x2="([\d.]+)"', svg))
                    for x, y, name, body in labels:
                        checked += 1
                        self.assertGreater(float(x), right, (route, width, name))   # outside the plot, never over the data
                        self.assertEqual(" ".join(re.sub(r"<[^>]+>", " ", body).split()), htmlmod.unescape(name), (route, width))   # whole: set on two lines when narrow, never cut
                        self.assertNotIn("…", body)
                        self.assertLessEqual(float(x) + 6.8 * max(len(t) for t in htmlmod.unescape(name).split(" " if width < 460 and len(name) > 11 else "\0")), int(re.search(r'viewBox="0 0 (\d+)', svg).group(1)) + 1, (route, width, name))
                    self.assertEqual(svg.count('class="lead"'), len(labels))   # a thin leader from the last point of each line to its name
        self.assertGreater(checked, 10)

    def test_the_primary_chart_of_the_agents_page_is_drawn_for_the_width_of_its_screen(self):
        route = agent_route("rpc", "mem_per_agent_mib")
        width = lambda w: int(re.search(r'viewBox="0 0 (\d+)', main_card(app(self.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(route)},{{width:{w}}}).html))"))).group(1))
        self.assertLessEqual(width(342), 342)
        self.assertGreater(width(1200), 600)

    def test_the_glossary_shows_the_entries_that_pages_link_and_keeps_the_others_in_a_collapsed_section(self):
        from buffon.dashboard import glossary
        page = self.views["#/glossary"]
        shown = {g["slug"] for g in self.data["glossary"] if g["shown"]}
        self.assertEqual(shown, glossary.SHOWN)
        self.assertLessEqual(len(shown), 27)
        main, rest = page.split('<details class="more" id="other-terms"')
        self.assertEqual({m for m in re.findall(r'id="g-([^"]+)"', main)}, shown)
        self.assertEqual({m for m in re.findall(r'id="g-([^"]+)"', rest)}, {g["slug"] for g in self.data["glossary"]} - shown)
        self.assertNotIn(" open", rest[:40])
        self.assertIn("data-filter-glossary", page)   # the search runs over every entry; app.js opens the section when it has a query
        linked = set()
        for text in self.views.values():
            linked |= set(re.findall(r'data-term="([^"]+)"', text))
        self.assertEqual(linked - shown, set(), "a page links a glossary entry that the Glossary page hides")
        slugs = {g["slug"] for g in self.data["glossary"]}
        for dup in ("bootstrap", "holm", "sign-flip"):
            self.assertNotIn(dup, slugs)

    def test_the_runs_page_has_one_checks_table_with_the_description_once_and_a_feeds_line_for_each_run(self):
        runs = self.views["#/method/runs"]
        self.assertEqual(runs.count('id="run-checks"'), 1)
        card = re.search(r'<section class="card" id="run-checks".*?</section>', runs, re.S).group(0)
        n_runs = len(self.data["runs"])
        for table in re.findall(r"<table.*?</table>", card, re.S):
            self.assertEqual(len(re.findall(r'<th scope="col"', table)), 1 + n_runs)   # a column for each run
        self.assertIn("inside the usual range in every run</summary>", card)   # what is in range everywhere is collapsed
        first = self.data["runs"][0]["notes"]["checks"][0]
        self.assertEqual(plain(runs).count(first["meaning"].strip()), 1)   # a description once, not once for each run
        self.assertEqual(runs.count('<p class="feeds">'), n_runs)
        self.assertLess(runs.rindex('<section class="card run">'), runs.index("against a copy of itself"))   # the noise table after the run cards
        self.assertNotIn("PROVISIONAL: why", runs)

    def test_a_metric_page_has_one_sentence_link_under_the_chart_and_the_api_order_of_compare(self):
        for route, text in self.views.items():
            if route.startswith("#/metric/"):
                self.assertNotIn("Why this can be important to you", text, route)
                self.assertNotIn("What this task does not show", text, route)
                self.assertEqual(plain(text).count("What we measure"), 1, route)
        page = next(t for r, t in self.views.items() if r.startswith("#/r/") and 'data-param="api"' in t)
        compare = re.findall(r'<option value="[^"]*"[^>]*>([^<]+)</option>', re.search(r'<select data-param="api">(.*?)</select>', page, re.S).group(1))
        for m in self.data["metrics"]:
            if len(m["apis"]) > 1:
                names = re.findall(r'aria-pressed="(?:true|false)">((?:OpenAI|Anthropic)[^<]*)</button>', self.views[f"#/metric/{m['key']}"])
                self.assertEqual(names, [n for n in compare if n in names], m["key"])


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class OtherApi(unittest.TestCase):
    """A harness with a value on another wire API is not shown as "can't run": the cell names that API and links to it. "Can't run" is for a harness with a value on none."""
    @classmethod
    def setUpClass(cls):
        raw = with_second_api(demo_raw(rounds=4))
        # demo-alpha is measured on the Messages API only
        raw = {**raw, "samples": [s for s in raw["samples"] if not (s["arm"] == "demo-alpha" and s["scenario"] == "overhead/print" and s["api"] == "openai-completions")]}
        cls.out = built(raw, faith=False)
        cls.data = site_data(cls.out)
        cls.page = app(cls.out, "console.log(JSON.stringify(A.render(D,'#/r/prompts-and-tools?v=values',{width:1200}).html))")

    def row(self, page, slug):
        return re.search(r'<tr class="h-[^"]*"[^>]*><th scope="row" class="hn1"[^>]*>(?:(?!</tr>).)*?href="#/harness/' + slug + r'".*?</tr>', page, re.S).group(0)

    def test_a_harness_measured_on_another_api_has_no_row_and_one_line_names_that_api_and_links_to_it(self):
        print_tables = [t for t in metric_tables(self.page) if "overhead-print.cpu_ms" in t["keys"]]
        self.assertTrue(print_tables)
        for t in print_tables:
            self.assertNotIn("demo-alpha", [slug for slug, _ in t["rows"]])
        lines = re.findall(r'<p class="notrun notin other">.*?</p>', self.page, re.S)
        self.assertTrue(lines, "no line for a harness measured on another API")
        for line in lines:
            m = re.search(r'<a href="([^"]+)" data-tip="([^"]+)">demo-alpha</a> \(Messages API\)', line)
            self.assertTrue(m, line)
            self.assertIn("api=anthropic", m.group(1))
            self.assertIn("measured on Anthropic API; switch the API to compare", htmlmod.unescape(m.group(2)))
            self.assertNotIn("can't run", plain(line).lower())
            self.assertNotIn("Not in this test", plain(line))

    def test_the_tile_the_metric_page_and_the_harness_page_say_the_same(self):
        home = app(self.out, "console.log(JSON.stringify(A.render(D,'#/',{width:1200}).html))")
        tile = re.search(r'<a class="card tile" href="#/r/prompts-and-tools[^"]*">.*?</a>', home, re.S).group(0)
        self.assertIn("Measured with another API: <span data-tip=", tile)   # a tile is one link: the name is no link inside it
        self.assertIn("(Messages API)", tile)
        metric = app(self.out, "console.log(JSON.stringify(A.render(D,'#/metric/overhead-print.cpu_ms',{width:1200}).html))")
        self.assertRegex(metric, r'<a href="#/metric/[^"]*api=anthropic[^"]*"[^>]*>demo-alpha \(Messages API\)</a>')
        harness = app(self.out, "console.log(JSON.stringify(A.render(D,'#/harness/demo-alpha',{width:1200}).html))")
        self.assertIn(">Messages API<", harness)   # its row in the section strip

    def test_can_t_run_is_kept_for_a_harness_with_no_value_on_any_api_and_keeps_its_reason(self):
        start = app(self.out, "console.log(JSON.stringify(A.render(D,'#/r/start-up?v=values',{width:1200}).html))")
        for t in metric_tables(start):
            if any(k.startswith("overhead-pty.") for k in t["keys"]):
                self.assertNotIn("demo-gamma", [slug for slug, _ in t["rows"]])
        line = re.search(r'<p class="notrun cant">.*?</p>', start, re.S).group(0)
        self.assertIn("Can't run: ", line)
        self.assertIn("demo-gamma", line)
        self.assertIn("no terminal mode", htmlmod.unescape(line))
