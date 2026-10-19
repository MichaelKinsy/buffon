# SPDX-License-Identifier: Apache-2.0
"""The results dashboard (`buffon dashboard`), built from the synthetic demo run and drawn by its own app (assets/app.js) under Node for every route the site
has: it opens offline, every chart has a table view, every term and abbreviation is defined, every control's state (harnesses, baseline, values or ratio) survives a
trip through the URL, the page marks no value as lowest or best, a missing value says why, the numbers are the report's or the run's own
medians, and demo data can never pass for a result. The site makes no grade, no score and no ranking: the tests fail if one comes back."""
import html as htmlmod
import itertools
import json
import math
import statistics
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from buffon.dashboard import build as dashboard, glossary
from tests.report_demo import demo_faithfulness_dir, demo_raw
from tests.telemetry_fixtures import write_dir

NODE = shutil.which("node")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "buffon", "dashboard", "assets", "app.js")
WORDS_OK = {"DEMO", "PROVISIONAL", "DATA", "V2"} | set(glossary.COMMON)   # words in capitals, and the abbreviations a programmer knows; V2 is in the manifest of OpenCode 2 that a harness page quotes


def built(raw, faith=True, logs=False):
    tmp = tempfile.mkdtemp()
    src = write_dir(os.path.join(tmp, "run"), raw)
    if logs:
        os.makedirs(os.path.join(src, "logs"))
        with open(os.path.join(src, "logs", "mock.log"), "w") as f:
            f.write("a plain log line\n")
    out = os.path.join(tmp, "site")
    dashboard.build([src], out, faithfulness=[demo_faithfulness_dir(os.path.join(tmp, "faith"))] if faith else [])
    return out


def node(script, timeout=60):
    return json.loads(subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True, timeout=timeout).stdout)


def app(out, body):
    """Run `body` under Node with A = the app's exports and D = the site's data."""
    return node(f"global.window={{}};require({json.dumps(os.path.join(out, 'data', 'site.js'))});const D=window.BUFFON;const A=require({json.dumps(APP_JS)});{body}")


def render_all(out, extra=()):
    return app(out, f"const rs=A.routes(D).concat({json.dumps(list(extra))});const o={{}};rs.forEach(r=>{{o[r]=A.render(D,r,{{width:1200}}).html}});console.log(JSON.stringify(o))")


def visible_text(html):
    """Running text outside links, abbreviations, code, formulas, charts and form controls: where an abbreviation would go unexplained."""
    skip = {"a", "abbr", "code", "pre", "svg", "script", "style", "option", "select", "textarea", "title", "kbd"}
    void = {"br", "img", "input", "hr", "meta", "link", "wbr", "source", "col"}
    out, stack = [], []
    for part in re.split(r"(<[^>]+>)", html):
        if part.startswith("<"):
            m = re.match(r"</?([a-zA-Z][a-zA-Z0-9-]*)", part)
            if not m:
                continue
            tag = m.group(1).lower()
            if part.startswith("</"):
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i][0] == tag:
                        del stack[i:]
                        break
            elif tag not in void and not part.endswith("/>"):
                stack.append((tag, (stack[-1][1] if stack else False) or tag in skip or bool(re.search(r'class="[^"]*\b(katex|raw)\b', part))))
        elif not (stack and stack[-1][1]):
            out.append(htmlmod.unescape(part))
    return " ".join(out)


VIEWS_OK = {"grid", "r", "harnesses", "harness", "metric", "cell", "runs", "method", "glossary", "doc", "about", "logs", "swarm", "fault", "all"}


def metric_tables(html, prefix="all"):
    """Every metric table of a page whose id starts with t-<prefix>, in page order: [{id, keys, rows: [(harness slug, [(class, data-csv-value)])], head, text}]. One table for each workload, then the tables of its "More metrics"."""
    out = []
    for m in re.finditer(r'<table class="data grid" id="t-(' + re.escape(prefix) + r'[^"]*)"[^>]*>(.*?)</table>', html, re.S):
        body = m.group(2)
        rows = [(re.search(r'href="#/harness/([^"]+)"', tr).group(1), re.findall(r'<td class="(num[^"]*)" data-csv-value="([^"]*)"', tr)) for tr in re.findall(r'<tr class="h-[^"]*"[^>]*>.*?</tr>', body, re.S)]
        out.append({"id": m.group(1), "keys": re.findall(r'<a class="info" href="#/metric/([^"?]+)', body), "rows": rows, "head": body[:body.index("<tbody>")], "text": m.group(0)})
    return out


def grid_of(html, section="all"):
    """The metric tables of a section page, merged: {harness slug: {metric key: (class, data-csv-value)}}, read from the page text."""
    rows = {}
    for t in metric_tables(html, section):
        for slug, cells in t["rows"]:
            rows.setdefault(slug, {}).update(dict(zip(t["keys"], cells)))
    return rows


@unittest.skipUnless(NODE, "buffon dashboard renders its formulas and its views with Node")
class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = demo_raw(rounds=6)
        # demo-beta cannot run the editor session: no sample, and the runner's recorded reason
        raw["samples"] = [s for s in raw["samples"] if not (s["arm"] == "demo-beta" and s["scenario"] == "overhead/rpc")]
        raw["skipped"] = [{"arm": "demo-beta", "scenario": "overhead/rpc", "api": "openai-completions", "reason": "no Pi-dialect RPC mode: its own protocol is not Pi's JSONL RPC"}]
        cls.out = built(raw, logs=True)
        cls.views = render_all(cls.out)
        with open(os.path.join(cls.out, "data", "report.json")) as f:
            cls.report = json.load(f)
        with open(os.path.join(cls.out, "data", "site.js"), encoding="utf-8") as f:
            cls.data = json.loads(f.read()[len("window.BUFFON="):-2])

    def test_every_view_of_demo_input_carries_the_demo_banner(self):
        self.assertGreater(len(self.views), 60)
        for route, text in self.views.items():
            self.assertIn('<div class="demo" role="note"><b>Demo data</b>', text, route)

    def test_every_link_resolves_to_a_view_or_a_file_so_the_folder_works_offline(self):
        broken = []
        for route, text in self.views.items():
            for target in re.findall(r'href="([^"]+)"', text):
                target = htmlmod.unescape(target)
                if target.startswith(("http:", "https:", "mailto:")):
                    continue
                if target.startswith("#/"):
                    view = re.match(r"#/([^/?]*)", target).group(1) or "grid"
                    if view not in VIEWS_OK:
                        broken.append((route, target))
                elif not os.path.exists(os.path.join(self.out, target.split("#")[0])):
                    broken.append((route, target))
        self.assertEqual(broken, [])
        targets = {t for text in self.views.values() for t in re.findall(r'href="(#/[^"]+)"', text)}
        rendered = app(self.out, f"console.log(JSON.stringify({json.dumps(sorted(targets))}.filter(r=>A.render(D,r.replace(/&amp;/g,'&'),{{width:1200}}).html.indexOf('<h1>Not found</h1>')>=0)))")
        self.assertEqual(rendered, [])

    def test_the_documents_the_site_points_at_are_pages_of_the_app_in_its_own_frame_and_their_links_work(self):
        names = ("CONTRIBUTING", "SUBMITTING", "METHODOLOGY", "WHAT-WE-MEASURE", "LIMITATIONS", "HEALTH")
        for name in names:
            text = self.views[f"#/doc/{name}"]
            self.assertIn('<header class="top">', text, name)
            self.assertIn('<article class="card doc md raw"', text, name)
            for target in re.findall(r'href="(#/[^"]+)"', text):
                self.assertRegex(htmlmod.unescape(target), r"#/(doc/[A-Z-]+(\?at=[\w-]+)?|about(\?at=[\w-]+)?|glossary|harnesses|runs|method|scale|r/[\w-]+|\?.*|$)", (name, target))
        home = self.views["#/"]
        self.assertIn('href="#/doc/CONTRIBUTING"', home)
        self.assertIn('href="#/doc/SUBMITTING"', home)
        self.assertFalse(os.path.exists(os.path.join(self.out, "docs")), "a document is not a page of another look")
        self.assertEqual({d["slug"] for d in self.data["docs"]} & set(names), set(names))

    def test_a_fenced_block_in_a_document_is_a_code_block_with_a_copy_button_and_a_table_scrolls_in_its_card(self):
        text = self.views["#/doc/SUBMITTING"]
        self.assertRegex(text, r'<div class="codeblock"><button type="button" class="btn small" data-copy-code>Copy</button><pre><code class="lang-sh">python3 -m buffon run overhead')
        self.assertNotIn("```", text)
        self.assertNotRegex(visible_text(text), r"^\s*`")
        self.assertRegex(text, r'<div class="tablewrap"><table class="doc">')
        self.assertNotRegex(re.sub(r'<div class="tablewrap">.*?</div>', "", text, flags=re.S), r"<table")

    def test_every_html_file_of_a_built_site_is_the_one_shell_and_no_file_carries_the_reports_old_look(self):
        html_files = []
        for root, _, files in os.walk(self.out):
            for name in files:
                path = os.path.join(root, name)
                rel = os.path.relpath(path, self.out)
                if name.endswith(".html") and not rel.startswith(os.path.join("assets", "katex")):
                    html_files.append(rel)
                if name.endswith((".html", ".css", ".js", ".svg")) and not rel.startswith(os.path.join("assets", "katex")) and not rel.startswith(os.path.join("runs", "")):
                    with open(path, encoding="utf-8") as f:
                        self.assertNotIn("--mustard", f.read(), rel)   # the report's own palette
        self.assertEqual(html_files, ["index.html"])
        with open(os.path.join(self.out, "index.html")) as f:
            shell = f.read()
        self.assertIn('<link rel="stylesheet" href="assets/app.css">', shell)
        self.assertIn('<script src="assets/app.js">', shell)
        self.assertIn('localStorage.getItem("buffon:theme")', shell)
        want = None
        for route, text in self.views.items():
            head = re.search(r'<header class="top">.*?</header>', text, re.S)
            self.assertIsNotNone(head, route)
            self.assertIn("data-theme-toggle", head.group(0), route)
            nav = re.findall(r'<a href="(#/[^"]*)"[^>]*>([^<]+)</a>', re.search(r'<nav class="main".*?</nav>', head.group(0), re.S).group(0))
            want = want or nav
            self.assertEqual(nav, want, route)
            self.assertEqual([n for _, n in nav], ["Results", "Harnesses", "Method", "About"], route)
            self.assertIn('<footer class="site">', text, route)

    def test_the_log_files_of_a_run_are_listed_by_the_app(self):
        route = next(r for r in self.views if r.startswith("#/logs/"))
        self.assertIn('href="runs/', self.views[route])
        self.assertIn("mock.log", self.views[route])
        self.assertTrue(os.path.exists(os.path.join(self.out, "runs", route.split("/")[2], "logs", "mock.log")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "runs", route.split("/")[2], "logs", "index.html")))

    def test_nothing_is_fetched_from_the_network(self):
        with open(os.path.join(self.out, "index.html")) as f:
            shell = f.read()
        for tag in re.findall(r"<(?:script|link|img|iframe)\b[^>]*>", shell):
            self.assertNotRegex(tag, r'(?:src|href)="(?:https?:)?//', tag)
        for route, text in self.views.items():
            for tag in re.findall(r"<(?:script|link|img|iframe)\b[^>]*>", text):
                self.assertNotRegex(tag, r'(?:src|href)="(?:https?:)?//', f"{route}: {tag}")
        with open(os.path.join(self.out, "assets", "katex", "katex.min.css")) as f:
            self.assertEqual(re.findall(r"url\((?!fonts/[^)]+\.woff2\))[^)]*\)", f.read()), [])

    def test_every_chart_has_a_table_view(self):
        charts = 0
        for route, text in self.views.items():
            for card in re.findall(r'<section class="card[^"]*" id="[^"]*" data-chart-card="1">.*?</section>', text, re.S):
                charts += 1
                self.assertIn('data-view-switch=', card, route)
                self.assertRegex(card, r'<div class="as-table" hidden>.*<table', route)
        self.assertGreater(charts, 30)

    def test_every_term_is_a_glossary_entry_and_every_abbreviation_on_any_view_is_explained(self):
        slugs = {g["slug"] for g in self.data["glossary"]}
        used = set()
        for route, text in self.views.items():
            for slug in re.findall(r'data-term="([^"]+)"', text):
                used.add(slug)
                self.assertIn(slug, slugs, route)
            loose = {w for w in re.findall(r"(?<![\w/.-])([A-Z][A-Z0-9]+(?:/[A-Z]+)?)(?![\w-])", visible_text(text)) if w not in WORDS_OK}
            self.assertEqual(loose, set(), f"{route}: abbreviations without an explanation")
        self.assertGreater(len(used), 0)
        glossary_view = self.views["#/glossary"]
        for g in self.data["glossary"]:
            self.assertIn(f'id="g-{g["slug"]}"', glossary_view)
        self.assertEqual({a for a, *_ in glossary.ACRONYMS} - {g["term"] for g in self.data["glossary"] if g["kind"] == "abbr"}, set())

    def test_every_number_is_the_reports_or_the_medians_of_the_runs_own_rounds(self):
        report = {(c["scenario"], c["api"], c["metric"], arm): comp for c in self.report["cells"] for arm, comp in c["comparisons"].items()}
        shown = {(c["scenario"], c["api"], c["metric"], arm): comp for c in self.data["cells"] for arm, comp in c["comparisons"].items()}
        self.assertEqual(set(shown), set(report))
        for key, comp in shown.items():
            self.assertEqual(comp["ratio"], report[key]["ratio"], key)
            self.assertEqual(comp["ci95"], report[key]["ci"], key)
            self.assertEqual(comp["n"], report[key]["n"], key)
        names = {h["id"] for h in self.data["harnesses"]}
        for c in self.data["cells"]:
            self.assertEqual(set(c["stats"]), {a for a in names if c["values"].get(a)}, c["slug"])
            for arm, st in c["stats"].items():
                self.assertEqual(st["median"], statistics.median(c["values"][arm]), (c["slug"], arm))
                self.assertEqual(st["n"], len(c["values"][arm]))

    def test_every_comparison_has_its_derivation_rerun_command_and_its_numbers_without_a_verdict(self):
        cell_routes = {r: t for r, t in self.views.items() if r.startswith("#/cell/")}
        self.assertEqual(len(cell_routes), sum(len(c["comparisons"]) for c in self.data["cells"]))
        not_compared = {f"#/cell/{c['slug']}/{h['slug']}" for c in self.data["cells"] for h in self.data["harnesses"] if (c["comparisons"].get(h["id"]) or {}).get("not_compared")}
        self.assertTrue(not_compared)
        for route, text in cell_routes.items():
            self.assertNotIn("\x00", text, route)
            self.assertRegex(text, r'<pre class="cmd" id="cmd">python3 -m buffon rerun [^<]+</pre>', route)
            if route in not_compared:
                continue   # no ratio, so no derivation: tests/test_dashboard_scope.py
            self.assertGreaterEqual(text.count('class="katex"'), 3, route)
            facts = re.search(r'<table class="kv facts">(.*?)</table>', text, re.S).group(1)
            self.assertEqual(facts.count("<tr>"), 2 + (3 if "Equivalence margin" in facts else 0), route)   # the interval and the noise floor (and the equivalence margin, its interval and result) are visible; the p-value and the smallest gap are in the math
            self.assertGreater(text.index("Paired test p"), text.index("The math behind this number"), route)
            self.assertLess(text.index("How sure is this number?"), text.index(">What runs<"), route)   # the ratio, how sure, then what runs
            self.assertEqual(text.count('class="raw"'), 0, route)
            self.assertIn(">Data files</a>", text)
            self.assertNotRegex(text, r'class="pill|Is the difference clear', route)

    def test_the_headline_says_what_buffon_measures_and_links_the_method_and_the_name_and_the_frame_carries_no_provisional_badge(self):
        home = self.views["#/"]
        hero = re.search(r'<section class="hero">(.*?)</section>', home, re.S).group(1)
        h1, trust = (re.sub(r"<[^>]+>", "", htmlmod.unescape(m)) for m in (re.search(r"<h1>(.*?)</h1>", hero, re.S).group(1), re.search(r'<p class="trust">(.*?)</p>', hero, re.S).group(1)))
        self.assertNotRegex(h1, r"\d", "the headline says what Buffon measures, not how many harnesses")
        self.assertRegex(trust, r"Measured on .* 6 rounds")
        self.assertNotIn("ranking", trust)
        self.assertIn('href="#/method"', hero)
        self.assertIn('href="#/about?at=why-buffon"', hero)
        self.assertIn('id="why-buffon"', self.views["#/about"])
        for route, text in self.views.items():
            header = text[text.index('<header class="top">'):text.index("</header>")]
            self.assertNotIn("Provisional", header, route)   # the badge is not a part of the frame: a value, a chart or a card of a provisional run carries it
            footer = text[text.index('<footer class="site">'):]
            self.assertIn('href="#/doc/CONTRIBUTING"', footer, route)
            self.assertIn('href="#/doc/SUBMITTING"', footer, route)

    def test_no_grade_score_index_or_verdict_is_shown_anywhere_on_the_site(self):
        for route, text in self.views.items():
            if route == "#/glossary" or route.startswith("#/method/runs"):
                continue
            shown = visible_text(text)
            self.assertNotRegex(shown, r"(?i)harness score|overhead index|overall index|\bgrade\b|\bscore\b|leaderboard|best harness|fastest|\bLowest:|\bHighest:", route)
        self.assertNotIn("entries", self.data)
        self.assertNotIn("answers", self.data)

    def test_the_results_pages_have_no_lowest_mark_no_unit_row_no_remove_button_and_no_copy_link(self):
        for route in ("#/", "#/r/prompts-and-tools"):
            page = self.views[route]
            for gone in ("lowdot", "the lowest value", 'class="drop"', "Remove this column", "data-copy-link", "Copy link", 'class="mu"'):
                self.assertNotIn(gone, page, route)
        self.assertIn('class="cbar"', self.views["#/r/prompts-and-tools"])   # the inline bar stays

    def test_a_cell_in_values_is_the_median_of_the_harnesss_rounds_and_in_ratio_mode_the_ratio_of_medians_over_the_rounds_both_ran(self):
        keys = ["overhead-print.cpu_ms", "overhead-print.peak_rss_mib"]
        page = lambda route: grid_of(app(self.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(route)},{{width:1200}}).html))"))
        absolute = page("#/r/prompts-and-tools?v=values")
        ratio = page("#/r/prompts-and-tools?base=demo-alpha&v=ratio")
        self.assertTrue(absolute and ratio)
        by = {(c["scenario"].replace("/", "-") + "." + c["metric"], c["api_short"]): c for c in self.data["cells"]}
        for key in keys:
            cell = by[(key, "chat")]
            for slug, cols in absolute.items():
                arm = next(h["id"] for h in self.data["harnesses"] if h["slug"] == slug)
                self.assertEqual(float(cols[key][1]), statistics.median(cell["values"][arm]), (slug, key))
            for slug, cols in ratio.items():
                arm = next(h["id"] for h in self.data["harnesses"] if h["slug"] == slug)
                if arm == "demo-alpha":
                    self.assertEqual(float(cols[key][1]), 1.0)
                    continue
                a = cell["comparisons"]["demo-alpha"]
                g = cell["comparisons"][arm] if arm in cell["comparisons"] else a   # Pi, the reference, is the y side of every comparison
                gx = {json.dumps(k): v for k, v in zip(g["rounds"], g["x"] if arm in cell["comparisons"] else g["y"])}
                ax = {json.dumps(k): v for k, v in zip(a["rounds"], a["x"])}
                both = [k for k in gx if k in ax]
                self.assertAlmostEqual(float(cols[key][1]), statistics.median([gx[k] for k in both]) / statistics.median([ax[k] for k in both]), places=9, msg=(slug, key))

    def test_a_harness_that_cannot_run_a_workload_has_no_row_in_it_and_the_line_under_it_says_why(self):
        sec = app(self.out, "console.log(JSON.stringify(A.Index(D).secOf['overhead-rpc.cpu_ms']))")
        page = self.views[f"#/r/{sec}"]
        rpc = [t for t in metric_tables(page) if any(k.startswith("overhead-rpc.") for k in t["keys"])]
        self.assertTrue(rpc)
        for t in rpc:
            self.assertNotIn("demo-beta", [slug for slug, _ in t["rows"]], "no row for a harness that cannot run the workload")
            self.assertTrue(t["rows"], t["id"])
        lines = re.findall(r'<p class="notrun cant">.*?</p>', page, re.S)
        self.assertEqual(len(lines), 1, "one Can't run line for the workload")
        self.assertIn("Can't run: ", lines[0])
        self.assertIn("(no Pi-dialect RPC mode)", lines[0])
        tips = [htmlmod.unescape(t) for t in re.findall(r'data-tip="([^"]*)"', lines[0])]
        self.assertTrue(all("demo-beta: no Pi-dialect RPC mode" in t for t in tips), tips)
        self.assertNotIn("Not in this test: demo-beta", page, "a harness is in one line, never in both")
        self.assertNotIn("can't run</span></td>", page, "no cell of a table says can't run")
        cell = next(c for c in self.data["cells"] if c["scenario"] == "overhead/rpc" and c["metric"] == "cpu_ms")
        self.assertIn("no Pi-dialect RPC mode", cell["na"]["demo-beta"])
        beta = self.data["harnesses"][[h["id"] for h in self.data["harnesses"]].index("demo-beta")]
        self.assertEqual([c["scenario"] for c in beta["cannot"]], ["overhead/rpc"])
        page = self.views["#/harness/demo-beta"]
        self.assertIn("no Pi-dialect RPC mode", page)
        self.assertIn("its own protocol is not Pi's JSONL RPC", htmlmod.unescape(page))
        self.assertIn("Editor session (RPC)", page)
        for text in self.views.values():
            for tip in re.findall(r'<td class="num na"[^>]*><span tabindex="0" data-tip="([^"]*)"', text):
                self.assertRegex(htmlmod.unescape(tip), r"\w+: \w", "an n/a cell names the harness and gives a reason")

    def test_every_other_na_has_a_reason_too(self):
        for c in self.data["cells"]:
            for arm, reason in c["na"].items():
                self.assertTrue(reason, (c["slug"], arm))
                self.assertNotIn(arm, c["stats"])

    def test_the_metric_page_says_what_it_measures_its_unit_and_formula_and_charts_every_harness(self):
        for key in ("overhead-print.cpu_ms", "overhead-print.peak_rss_mib", "overhead-rpc.cpu_ms"):
            text = self.views[f"#/metric/{key}"]
            self.assertGreaterEqual(text.count('class="katex"'), 3, key)
            self.assertIn("how this metric is made", text)
            self.assertRegex(text, r"<th>Unit</th><td>[^<]+</td>")
            self.assertGreater(len(re.sub(r"<[^>]+>", "", re.search(r'<p class="lede">(.*?)</p>', text, re.S).group(1))), 20, key)
            self.assertEqual(text.count('class="brow h-'), len({h for c in self.data["cells"] if c["key"] == key and c["api_short"] in ("chat", "-") for h in c["stats"]}), key)
        self.assertTrue(all(m["about"] for m in self.data["metrics"]))
        self.assertEqual([m["key"] for m in self.data["metrics"] if m["metric"] == "cpu_ms"][0], "overhead-print.cpu_ms")

    def test_the_harness_page_keeps_a_bar_for_each_of_its_measures_behind_a_disclosure_and_what_it_did_not_run(self):
        for h in self.data["harnesses"]:
            text = self.views[f"#/harness/{h['slug']}"]
            mine = {c["key"] for c in self.data["cells"] if c["api_short"] in ("chat", "-") and h["id"] in c["stats"]}
            self.assertEqual(text.count('<a class="hrow"'), len(mine), h["id"])
            self.assertIn("<summary>Every measure</summary>", text)
            self.assertIn("Version, pin and checksum", text)
            if h["cannot"]:
                self.assertIn("Not measured", text, h["id"])
        self.assertIn("This is the baseline", self.views["#/harness/pi-node"])

    def test_the_method_page_is_a_strip_of_six_steps_each_with_its_detail_behind_more(self):
        text = self.views["#/method"]
        self.assertEqual(text.count('<li class="mstep">'), 6)
        self.assertEqual(len(re.findall(r'<details class="why"><summary>More</summary>', text)), 6)
        self.assertGreaterEqual(text.count('class="katex"'), 4)
        self.assertIn('href="#/doc/METHODOLOGY"', text)
        self.assertLess(len(visible_text(text).split()), 900)

    def test_no_em_dash_on_any_view(self):
        for route, text in self.views.items():
            ours = re.sub(r'<div class="md raw">.*?</div></details>', "", text, flags=re.S)
            ours = re.sub(r'<p class="their-words raw[^"]*">.*?</p>', "", ours, flags=re.S)   # a project's own words are quoted as they are
            self.assertNotIn("\u2014", ours, route)

    def test_a_directory_not_written_by_the_dashboard_is_refused(self):
        foreign = tempfile.mkdtemp()
        with open(os.path.join(foreign, "keep.txt"), "w") as f:
            f.write("mine")
        with self.assertRaises(dashboard.DashboardError):
            dashboard.build(["/nonexistent"], foreign)
        self.assertTrue(os.path.exists(os.path.join(foreign, "keep.txt")))


class Markdown(unittest.TestCase):
    def test_a_fenced_block_with_a_language_is_pre_code_with_a_copy_button_and_its_text_is_escaped(self):
        from buffon.dashboard import markdown
        out = markdown.convert("Run it:\n\n```sh\npython3 -m buffon run <x> && echo \"hi\"\n  indented\n```\n\nAfter.")
        self.assertIn('<div class="codeblock"><button type="button" class="btn small" data-copy-code>Copy</button><pre><code class="lang-sh">python3 -m buffon run &lt;x&gt; &amp;&amp; echo "hi"\n  indented</code></pre></div>', out)
        self.assertEqual(out.count("<p>"), 2)
        self.assertNotIn("`", out)

    def test_nested_and_numbered_lists_and_tables_and_links(self):
        from buffon.dashboard import markdown
        out = markdown.convert("1. one\n2. two\n   - inner `code`\n\n| a | b |\n|---|---:|\n| [x](Y.md#z) | 2 |\n", lambda url: "#/doc/Y?at=z" if url == "Y.md#z" else None)
        self.assertIn("<ol><li>one</li><li>two<ul><li>inner <code>code</code></li></ul></li></ol>", out)
        self.assertIn('<div class="tablewrap"><table class="doc">', out)
        self.assertIn('<a href="#/doc/Y?at=z">x</a>', out)
        self.assertIn("<td class=num>2</td>", out)
        self.assertNotIn("<a", markdown.convert("[gone](Z.md)", lambda url: None))


class Keys(unittest.TestCase):
    def test_a_metric_has_one_key_whatever_the_wire_api(self):
        from buffon.dashboard import model
        self.assertEqual(model.metric_key("overhead/print", "cpu_ms"), "overhead-print.cpu_ms")


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Controls(unittest.TestCase):
    """What a reader chooses (harnesses, baseline, API, values or ratio) changes the view, and the choice lives in the URL."""

    @classmethod
    def setUpClass(cls):
        cls.out = built(demo_raw())

    def test_the_choice_of_harnesses_baseline_values_or_ratio_round_trips_through_the_url(self):
        routes = ["#/?api=chat&base=demo-alpha&h=demo-beta,demo-gamma&v=values", "#/?h=none", "#/r/prompts-and-tools?api=chat&base=demo-gamma&v=ratio",
                  "#/metric/overhead-print.cpu_ms?api=chat&base=demo-gamma", "#/harness/demo-alpha?api=chat&base=demo-beta",
                  "#/cell/overhead-print-chat-cpu-ms/demo-alpha", "#/method", "#/method/runs", "#/about", "#/"]
        out = app(self.out, f"console.log(JSON.stringify({json.dumps(routes)}.map(r=>A.serialize(A.parse(r)))))")
        self.assertEqual(out, routes)

    def test_the_route_sets_the_rows_the_baseline_and_the_mode(self):
        route = "#/r/prompts-and-tools?base=demo-gamma&h=demo-gamma,demo-alpha&v=ratio"
        st = app(self.out, f"const I=A.Index(D);const s=A.stateOf(I,A.parse({json.dumps(route)}));console.log(JSON.stringify({{hs:s.hs.map(h=>h.slug),base:s.base.slug,mode:s.mode,api:s.api}}))")
        self.assertEqual(st, {"hs": ["demo-alpha", "demo-gamma"], "base": "demo-gamma", "mode": "ratio", "api": "chat"})
        html = app(self.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(route)},{{width:1200}}).html))")
        rows = grid_of(html)
        self.assertEqual(set(rows), {"demo-alpha", "demo-gamma"})
        self.assertEqual(float(rows["demo-gamma"]["overhead-print.cpu_ms"][1]), 1.0, "the baseline is 1 against itself")

    def test_toggling_a_harness_changes_the_list_and_a_list_equal_to_its_start_leaves_the_url(self):
        out = app(self.out, """const I=A.Index(D);const t=(r,v)=>A.toggle(I,A.parse(r),v);const h=D.harnesses.map(x=>x.slug);
          console.log(JSON.stringify({h:h,drop:t('#/',h[1]),restored:t(t('#/',h[1]),h[1]),inSection:t('#/r/start-up?v=values',h[1]),none:t('#/?h='+h[0],h[0])}))""")
        h = out["h"]
        self.assertEqual(out["drop"], "#/?h=" + ",".join(x for i, x in enumerate(h) if i != 1))
        self.assertEqual(out["restored"], "#/")
        self.assertEqual(out["inSection"], "#/r/start-up?h=" + ",".join(x for i, x in enumerate(h) if i != 1) + "&v=values")
        self.assertEqual(out["none"], "#/?h=none")

    def test_against_another_harness_each_ratio_is_the_ratio_of_medians_over_the_rounds_both_ran(self):
        data = app(self.out, "console.log(JSON.stringify(D.cells))")
        html = app(self.out, "console.log(JSON.stringify(A.render(D,'#/r/prompts-and-tools?base=demo-alpha&h=demo-gamma&v=ratio',{width:1200}).html))")
        shown = float(grid_of(html)["demo-gamma"]["overhead-print.cpu_ms"][1])
        c = next(c for c in data if c["slug"] == "overhead-print-chat-cpu-ms")
        median = lambda v: statistics.median(v)
        g, a = c["comparisons"]["demo-gamma"], c["comparisons"]["demo-alpha"]
        gx, ax = {json.dumps(k): v for k, v in zip(g["rounds"], g["x"])}, {json.dumps(k): v for k, v in zip(a["rounds"], a["x"])}
        both = [k for k in gx if k in ax]
        self.assertAlmostEqual(shown, median([gx[k] for k in both]) / median([ax[k] for k in both]), places=9)

    def test_a_label_is_escaped_everywhere(self):
        raw = demo_raw(rounds=4)
        del raw["run"]["synthetic"]
        raw["arms"]["demo-alpha"]["label"] = "<img src=x onerror=alert(1)>"
        out = built(raw, faith=False)
        views = render_all(out)
        for route, text in views.items():
            self.assertNotIn('class="demo"', text, route)
            self.assertNotIn("<img src=x", text, route)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", views["#/"])

    def test_a_cell_measured_by_a_meter_that_cannot_see_it_says_so(self):
        raw = demo_raw(rounds=4)
        for s in raw["samples"]:
            s["meter"], s["perf_scope"] = "rusage", "sampled"
        out = built(raw, faith=False)
        views = render_all(out)
        instr = [t for r, t in views.items() if r.startswith("#/cell/") and "-instructions/" in r]
        self.assertTrue(instr)
        for text in instr:
            self.assertIn("Instructions here were sampled, not counted", text)
        cpu = [t for r, t in views.items() if r.startswith("#/cell/") and "-cpu-ms/" in r and "turn" not in r and "ready" not in r and "1k" not in r]
        for text in cpu:
            self.assertNotIn('class="caveat"', text)
        self.assertIn("rusage", views["#/method/runs"])


class Palette(unittest.TestCase):
    """Both themes: text readable on a panel (WCAG 4.5:1), every harness and status mark visible on it (3:1), and the first five harness colours
    (Pi and four others, the common case) still apart for readers with protanopia, deuteranopia or tritanopia. Past five, names carry identity."""

    def test_text_and_marks_meet_wcag_contrast_in_both_themes(self):
        from tools import palette_check as p
        for theme, r in p.report().items():
            for token, ratio in r["text"].items():
                self.assertGreaterEqual(ratio, 4.5, f"{theme} {token}")
            for token, ratio in r["marks"].items():
                self.assertGreaterEqual(ratio, 3.0, f"{theme} {token}")

    def test_the_first_five_harness_colours_stay_apart_under_colour_blindness(self):
        from tools import palette_check as p
        for theme, t in p.themes().items():
            for vision, matrix in [("normal", None)] + list(p.CVD.items()):
                labs = {k: p.lab(p.simulate(t[k], matrix) if matrix else tuple(p.lin(c) for c in p.rgb(t[k]))) for k in p.SERIES[:5]}
                for a, b in itertools.combinations(labs, 2):
                    self.assertGreaterEqual(p.delta(labs[a], labs[b]), 8.0, f"{theme} {vision}: {a} and {b}")


if __name__ == "__main__":
    unittest.main()
