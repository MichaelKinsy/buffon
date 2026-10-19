# SPDX-License-Identifier: Apache-2.0
"""The designed report.html, rendered from a synthetic sample run (tests/report_demo.py): one static file in Buffon's dark Pi theme, with the grade and faithfulness, one card per family,
every cell's unit, spread, memory kind and rerun command, the limitations, and the same numbers as report.md and report.json."""
import html as htmlmod
import json
import os
import re
import tempfile
import unittest

from buffon.report import cards, html as htmllib, render, theme
from tests.report_demo import REFERENCE, demo_faithfulness_dir, demo_raw
from tests.telemetry_fixtures import write_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Words that state a verdict. The front of the report uses arrows and "above" and "below the reference"; the grade method names its own letters.
VERDICT_WORDS = re.compile(r"\b(fastest|slowest|best|winner|wins?|loss(?:es)?|loses?|beats?|better|worse|outperform\w*|superior)\b", re.I)
MEMORY_METRICS = {"peak_rss_mib": "peak RSS", "ready_rss_mib": "RSS at ready", "rss_mib": "RSS", "pss_mib": "PSS", "ready_pss_mib": "PSS at ready", "peak_mem_mib": "cgroup peak memory"}


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rendered(raw=None, faith=True):
    tmp = tempfile.mkdtemp()
    src = write_dir(os.path.join(tmp, "run"), raw or demo_raw())
    out = os.path.join(tmp, "out")
    render.render([src], out, faithfulness=[demo_faithfulness_dir(os.path.join(tmp, "faith"))] if faith else [])
    return out


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = rendered()
        cls.page = read(cls.out, "report.html")
        cls.md = read(cls.out, "report.md")
        cls.report = json.loads(read(cls.out, "report.json"))
        cls.front = cls.page[cls.page.index("<body"):cls.page.index('<details class="panel" id="full-report"')]

    # -- one static file ----------------------------------------------------------------------------------------------------------------

    def test_the_page_fetches_nothing_when_it_is_viewed(self):
        for pattern in (r"<script", r"<link\b", r"@import", r"@font-face", r"<img\b", r"<iframe", r"<object", r"<embed", r"url\(", r"\ssrc\s*="):
            self.assertIsNone(re.search(pattern, self.page, re.I), pattern)
        self.assertNotIn("<style>@", self.page)
        self.assertEqual(len(re.findall(r"<style>", self.page)), 1)

    def test_the_fonts_are_the_systems_serif_sans_and_monospace(self):
        for stack in (theme.SERIF, theme.SANS, theme.MONO):
            self.assertIn(stack, self.page)
        self.assertTrue(theme.SERIF.endswith("serif"))
        self.assertTrue(theme.SANS.endswith("sans-serif"))
        self.assertTrue(theme.MONO.endswith("monospace"))
        self.assertRegex(self.page, r"\.hero h1\{font:italic 400 [^}]*var\(--serif\)")

    def test_the_other_html_outputs_share_the_theme(self):
        for name in ("leaderboard.html", "report-card.html"):
            text = read(self.out, name)
            self.assertIn(theme.CSS, text, name)
            self.assertIn('class="mark"', text, name)
            self.assertIsNone(re.search(r"<script|<link\b|@import|url\(", text), name)

    # -- the look ------------------------------------------------------------------------------------------------------------------------

    def test_the_palette_is_the_owners_and_the_page_is_dark(self):
        self.assertEqual(theme.PALETTE, {"bg": "#1b1f27", "grid": "#232833", "text": "#d4d6db", "coral": "#e2928a", "steel": "#6599bf", "mustard": "#e8c06e", "yours": "#7aa3d1"})
        for colour in theme.PALETTE.values():
            self.assertIn(colour, self.page)
        self.assertIn("color-scheme:dark", self.page)
        self.assertIn("linear-gradient(var(--grid) 1px,transparent 1px)", self.page)

    def test_the_brand_mark_is_three_colours_of_pixel_blocks(self):
        mark = re.search(r'<svg class="mark".*?</svg>', self.front, re.S).group(0)
        fills = re.findall(r'fill="(#[0-9a-f]{6})"', mark)
        self.assertEqual(sorted(set(fills)), sorted([theme.PALETTE["coral"], theme.PALETTE["steel"], theme.PALETTE["mustard"]]))
        self.assertEqual(len(fills), len(theme.BLOCKS))
        self.assertIn("crispEdges", mark)
        self.assertEqual(len(re.findall(r"<rect", mark)), 6)

    def test_the_headline_is_the_serif_italic_display_line_with_the_accent_on_the_reader(self):
        self.assertIn('<h1>Many harnesses. One scripted model. <span class="yours">Rerun it on yours.</span></h1>', self.front)
        self.assertIn(".hero h1 .yours{color:var(--yours)}", self.page)

    def test_text_and_accents_are_readable_on_the_dark_ground(self):
        p = theme.PALETTE
        self.assertGreaterEqual(contrast(p["text"], p["bg"]), 7.0)
        for name in ("coral", "steel", "mustard", "yours"):
            self.assertGreaterEqual(contrast(p[name], p["bg"]), 4.5, name)
        for muted, panel in (("#949baa", "#202530"), ("#949baa", "#272d3a")):
            self.assertGreaterEqual(contrast(muted, panel), 4.5, muted)

    def test_the_page_scales_to_a_phone_and_prints(self):
        self.assertIn('name="viewport"', self.page)
        self.assertIn("@media(max-width:640px)", self.page)
        self.assertIn("@media print", self.page)

    # -- the badges, the grade and faithfulness -----------------------------------------------------------------------------------------

    def test_a_provisional_run_carries_the_badge_and_the_reasons(self):
        self.assertIn('<span class="badge prov"><i></i>PROVISIONAL</span>', self.front)
        self.assertIn("Do not publish or compare it as a result.", self.front)
        self.assertIn("the site profile does not claim dedicated hardware", self.front)

    def test_a_quiet_run_has_no_provisional_badge(self):
        out = rendered(demo_raw(quiet=True))
        front = read(out, "report.html")
        front = front[front.index("<body"):front.index('<details class="panel" id="full-report"')]
        self.assertNotIn("PROVISIONAL", front)
        self.assertIn("Quiet dedicated hardware", front)

    def test_the_run_notes_badge_is_the_note_count_of_health_json_and_has_no_health_colour(self):
        notes = json.loads(read(self.out, "health.json"))["notes"]
        self.assertIn(f'<span class="badge "><i></i>Run notes: {notes}</span>', self.front)
        self.assertNotIn("health-", self.front)

    def test_every_graded_entry_has_a_card_with_its_score_and_its_faithfulness(self):
        graded = json.loads(read(self.out, "grade.json"))
        entries = {e["label"]: e for e in graded["entries"]}
        self.assertGreaterEqual(len(entries), 3)
        cards_html = dict(re.findall(r'<article class="entry"><h3>([^<]+)</h3>(.*?)</article>', self.front, re.S))
        self.assertEqual(set(cards_html), set(entries))
        for label, e in entries.items():
            card = cards_html[label]
            if e["overall"] is not None:
                self.assertIn(f'<b>{e["overall"]}</b><span>{e["letter"]}</span>', card)
            if e["faithfulness"] is None:
                self.assertIn("Faithfulness to Pi: <b>not measured</b>", card)
            else:
                self.assertIn(f'Faithfulness to Pi: <b>{e["faithfulness"]:.0f}</b> / 100', card)
                self.assertIn(f'<u style="left:{theme_floor()}%"></u>', card)
        self.assertEqual({label: e["faithfulness"] for label, e in entries.items() if e["faithfulness"] is not None}, {REFERENCE: 100.0, "demo-alpha": 94.0, "demo-gamma": 71.0})

    # -- the family cards ---------------------------------------------------------------------------------------------------------------

    def rows(self):
        """{(arm, cell id): the text of its table row} from the family cards."""
        out, arm = {}, None
        for chunk in re.findall(r"<tr.*?</tr>", self.front, re.S):
            if "<th" in chunk:
                continue
            head = re.match(r'<tr class="armhead"><td colspan="7">(.*?)</td>', chunk)
            if head:
                arm = htmlmod.unescape(head.group(1))
                continue
            code = re.search(r"<code>python3 -m buffon rerun ([^<]+)</code>", chunk)
            self.assertIsNotNone(code, chunk[:200])
            out[(arm, htmlmod.unescape(code.group(1)))] = chunk
        return out

    def test_there_is_one_card_per_family_with_the_title_of_the_grade_method(self):
        from buffon.report import grade
        titles = {f["id"]: f["title"] for f in grade.METHOD["family"]}
        found = re.findall(r'<section class="card fam" id="family-([a-z0-9-]+)"><header><h3>([^<]+)</h3>', self.front)
        self.assertEqual([i for i, _ in found], ["core", "ext10", "streaming", "long-session", "devloop", "other"])
        for fam_id, title in found:
            self.assertEqual(htmlmod.unescape(title), titles.get(fam_id, "Cells the grade does not score"))

    def test_every_comparison_of_report_json_is_a_row_with_its_unit_its_spread_and_its_rerun_command(self):
        rows = self.rows()
        expected = {(arm, c["id"]): c for c in self.report["cells"] for arm in c["comparisons"]}
        self.assertEqual(set(rows), set(expected))
        self.assertGreater(len(rows), 40)
        for (arm, cell_id), row in rows.items():
            cell = expected[(arm, cell_id)]
            self.assertIn(f'<span class="tag kind-{cell["kind"]}">{cell["kind"]}</span>', row)
            self.assertIn(f'<span class="tag">{htmlmod.escape(cell["unit"])}</span>', row)
            self.assertIn("IQR ref / arm", row)
            self.assertIn("CV ", row)
            self.assertIn("A/A floor", row)
            self.assertIn(htmlmod.escape(cell["rerun"]), row)

    def test_the_numbers_of_a_row_are_the_numbers_of_the_markdown_row(self):
        rows, arm, header, checked = self.rows(), None, None, 0
        for line in self.md.splitlines():
            if m := re.match(r"## (.+?) against ", line):
                arm = m.group(1)
            if line.startswith("| workload | api | metric | kind | unit | n | reference median"):
                header = [c.strip() for c in line.strip("|").split("|")]
                continue
            if header and line.startswith("|---"):
                continue
            if header and line.startswith("| "):
                cols = dict(zip(header, [c.strip() for c in line.strip("|").split("|")]))
                cell_id = cols["cell"].strip("`")
                row = re.sub(r"<[^>]+>", " ", rows[(arm, cell_id)])
                for key in ("reference median", "arm median", "ratio [95% CI]", "IQR ref / arm", "n"):
                    self.assertIn(htmlmod.escape(cols[key]).replace("&amp;", "&"), htmlmod.unescape(row), f"{arm} {cell_id} {key}")
                checked += 1
            elif header and not line.strip():
                header = None
        self.assertEqual(checked, len(rows))

    def test_memory_rows_name_their_kind_and_no_other_row_does(self):
        seen = set()
        for (arm, cell_id), row in self.rows().items():
            metric = re.search(r'<span class="mn">([^<]+)</span>', row).group(1)
            kind = re.search(r'<span class="tag kind-(\w+)">', row).group(1)
            labels = re.findall(r'<span class="tag mem[^"]*">([^<]+)</span>', row)
            if kind == "memory":
                self.assertEqual(labels, [MEMORY_METRICS[metric]], metric)
                seen.add(metric)
            else:
                self.assertEqual(labels, [], metric)
        self.assertEqual(seen, {"peak_rss_mib", "ready_rss_mib"})

    def test_the_cards_say_where_a_median_sits_and_never_whether_that_is_good(self):
        self.assertEqual(self.front.count('<span class="dir up" aria-hidden'), len(re.findall(r"above the reference</td>", self.front)))
        for words in ("above the reference", "below the reference", "no measurable difference"):
            self.assertIn(words, self.front)
        self.assertEqual(re.findall(VERDICT_WORDS, re.sub(r"<[^>]+>", " ", self.front.split('<section id="families">')[0] + self.front.split('<section id="families">')[1])), [])

    def test_the_sections_of_the_page_are_the_ones_the_report_template_describes(self):
        template = read(ROOT, "docs", "REPORT-TEMPLATE.md")
        described = re.findall(r"^\d+\. (?:A header|\*\*([^*]+)\*\*)", template.split("## The HTML report")[1].split("## A row of a table")[0], re.M)
        self.assertEqual([d for d in described if d], ["The grade and faithfulness", "Families", "Full report", "Limitations"])
        for title in ("The grade and faithfulness", "Families"):
            self.assertIn(f'<h2 class="sec">{title}</h2>', self.front)
        for title in ("Full report", "Limitations"):
            self.assertIn(f"<summary>{title}<small>", self.page)
        self.assertLess(self.page.index('<h2 class="sec">The grade and faithfulness</h2>'), self.page.index('<h2 class="sec">Families</h2>'))
        self.assertLess(self.page.index('<h2 class="sec">Families</h2>'), self.page.index("<summary>Full report"))
        self.assertLess(self.page.index("<summary>Full report"), self.page.index("<summary>Limitations"))

    # -- the limitations ---------------------------------------------------------------------------------------------------------------

    def test_the_limitations_are_in_the_page_and_in_the_navigation(self):
        self.assertIn('<a href="#limitations">Limitations</a>', self.front)
        panel = self.page[self.page.index('id="limitations"'):]
        for title in cards.LIMITATION_TITLES:
            self.assertIn(htmlmod.escape(title, quote=False), panel)
        self.assertIn("Why a macOS footprint depends on the allocator", panel)

    def test_the_list_of_titles_equals_the_headings_of_the_limitations_page(self):
        headings = re.findall(r"^## \d+\. (.+)$", read(ROOT, "docs", "LIMITATIONS.md"), re.M)
        self.assertEqual(list(cards.LIMITATION_TITLES), headings)

    def test_the_embedded_page_links_only_inside_the_report_or_out_to_the_web(self):
        panel = self.page[self.page.index('id="limitations"'):]
        for href in re.findall(r'<a href="([^"]*)"', panel):
            self.assertTrue(href.startswith(("#", "https://", "http://")), href)

    def test_without_the_page_on_disk_the_titles_and_the_pointer_remain(self):
        text = cards.limitations_section(doc_lines=[])
        self.assertIn("The full text is <code>docs/LIMITATIONS.md</code>", text)
        for title in cards.LIMITATION_TITLES:
            self.assertIn(htmlmod.escape(title), text)

    # -- the same report ---------------------------------------------------------------------------------------------------------------

    def test_the_whole_markdown_report_is_still_in_the_page(self):
        full = self.page[self.page.index('id="full-report"'):self.page.index('id="limitations"')]
        self.assertEqual(len(re.findall(r"<table>", full)), len(re.findall(r"^\|---", self.md, re.M)))
        self.assertIn("Drift: per-round series", full)
        for heading in re.findall(r"^## (.+?)(?: \u2014 PROVISIONAL)?$", self.md, re.M):
            self.assertIn(htmlmod.escape(heading.replace("**", ""), quote=False).split(":")[0], full)

    def test_a_hostile_label_and_reason_are_escaped_everywhere(self):
        raw = demo_raw()
        raw["arms"]["demo-alpha"]["label"] = "<img src=x onerror=alert(1)>"
        raw["hardware"]["reasons"] = ["<script>alert(2)</script>"]
        page = read(rendered(raw), "report.html")
        self.assertNotIn("<img src=x", page)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)


class Pieces(unittest.TestCase):
    def test_memory_kind_names_a_memory_metric_and_nothing_else(self):
        for metric, label in MEMORY_METRICS.items():
            self.assertEqual(cards.memory_kind(metric, "memory"), label)
        self.assertEqual(cards.memory_kind("max_proc_rss_mib", "memory"), "largest process RSS")
        self.assertEqual(cards.memory_kind("cpu_ms", "CPU"), None)
        self.assertEqual(cards.memory_kind("footprint_mib", "memory"), "own footprint")
        self.assertEqual(cards.memory_kind("heap_in_use_mib", "memory"), "heap in use")
        self.assertIsNone(cards.memory_kind("mystery_mib", "memory"))

    def test_a_memory_metric_of_no_known_kind_is_shown_as_unnamed(self):
        row = {"metric": "mystery_mib", "kind": "memory", "unit": "MiB"}
        self.assertIn("memory (kind not named)", cards.tags(row))

    def test_every_memory_metric_the_code_names_has_a_kind_label(self):
        # The files that produce sample metrics. runner/container.py is left out: its memory_mib is the container's limit in a config record, not a measurement.
        names = set()
        for directory in ("workloads", "runner"):
            for name in os.listdir(os.path.join(ROOT, "buffon", directory)):
                if name.endswith(".py") and name != "container.py":
                    names |= set(re.findall(r'"([a-z_0-9]*_mib)"', read(ROOT, "buffon", directory, name)))
        self.assertTrue({"peak_rss_mib", "rss_mib", "pss_mib"} <= names)
        names.discard("memory_mib")   # the container's limit, a key of config records (the swarm's `swarm.memory_mib`, a plan's tier), never a measurement
        unlabelled = {n for n in names if cards.memory_kind(n, "memory") is None}
        self.assertEqual(unlabelled, set(), "a memory metric of the code has no label: add it to cards.MEMORY_KINDS")

    def test_direction_words_never_judge(self):
        for verdict in ("loss", "win", "no measurable difference", "inconclusive (outside the floor)", "too few rounds"):
            self.assertEqual(VERDICT_WORDS.findall(cards.direction(verdict)[2]), [], verdict)
        self.assertEqual(cards.direction("loss")[1:], ("up", "above the reference"))
        self.assertEqual(cards.direction("win")[1:], ("down", "below the reference"))

    def test_the_converter_page_is_themed_and_still_escapes(self):
        page = htmllib.page("t <i>", ["| a |", "|---|", "| <script>alert(1)</script> |"])
        self.assertIn(theme.CSS, page)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


def theme_floor():
    from buffon.report import grade
    return grade.METHOD["method"]["faithfulness_floor"]


if __name__ == "__main__":
    unittest.main()
