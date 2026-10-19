# SPDX-License-Identifier: Apache-2.0
"""The Large writes and Agent swarming sections of the results site, built from synthetic swarm samples (tests/scale_demo.py): the large-write table has a value or the recorded
reason for every harness, the Agent swarming section (#/r/agent-swarming) has the skeleton of every section (a picker, a VIEW control, one primary chart, the table of every metric), states the envelope once, draws one metric per chart, says the exact number of agents each harness held (the median of the
rounds, with their range; "at least N (cap)" at the cap; 0 when one did not fit), draws the same harness with the ten extensions as a second bar and says where and why each search
stopped, every mark has a tooltip and a derivation page, every new term is in the glossary, a run made before the search reads as a range and never as a false exact number,
and a site without a scale run has no Agent swarming section."""
import html as htmlmod
import json
import math
import os
import re
import statistics
import unittest

from buffon.dashboard import scale as scalelib
from tests.report_demo import ARMS, demo_raw
from tests.scale_demo import demo_ladders, demo_swarms, ladder, search
from tests.test_dashboard import metric_tables, NODE, WORDS_OK, app, built, render_all, visible_text
from tests.test_report import sample, wobble

WRITE = {"kb50_wall_ms": 2400.0, "kb50_cpu_ms": 2700.0, "kb50_peak_mem_mib": 260.0, "kb200_wall_ms": 36000.0, "kb200_cpu_ms": 37000.0, "kb200_peak_mem_mib": 550.0}


def with_write(raw):
    """The demo run plus the large write for every harness but demo-gamma, which has no write tool."""
    for rnd in range(raw["run"]["rounds"] + 1):
        for arm, shift, scale in ARMS:
            if arm.startswith("demo-gamma"):
                continue
            vals = {k: v * (1 if k.endswith("_mib") else scale) * (1 + wobble(rnd + shift) / 200.0) for k, v in WRITE.items()}
            raw["samples"].append(sample(arm, "overhead/print-write", rnd, warmup=rnd == 0, **vals))
    raw["skipped"].append({"arm": "demo-gamma", "scenario": "overhead/print-write", "api": "openai-completions", "reason": "its tool set has no write tool: the call is built from the arm's own tool schema"})
    return raw


def with_swarms(raw, second=False):
    """The demo run plus the search samples (tests/scale_demo.py demo_swarms); `second` adds a second envelope."""
    samples, skipped = demo_swarms()
    if second:
        samples += search("pi-node", "rpc", per_agent_mib=190, limit_mib=2048, cpus=(40, 41, 42, 43), cap=64)
    raw["samples"] += samples
    raw["skipped"] += skipped
    return raw


def with_ladders(raw, second=False):
    """The demo run plus the doubling ladders of a run made before the search (the legacy fixture)."""
    samples, skipped = demo_ladders()
    if second:
        s2, k2 = ladder("pi-node", "rpc", per_agent_mib=190, limit_mib=2048, cpus=(40, 41, 42, 43), cap=64)
        samples += s2
        skipped += k2
    raw["samples"] += samples
    raw["skipped"] += skipped
    return raw


def plain(html):
    """All the text of a piece of HTML, links included."""
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def site_data(out):
    with open(os.path.join(out, "data", "site.js"), encoding="utf-8") as f:
        return json.loads(f.read()[len("window.BUFFON="):-2])


AGENTS = "#/r/agent-swarming"
KINDS4 = ("rpc", "print", "rpc-ext10", "print-ext10")
PER_N = ("mem_per_agent_mib", "turns_per_s", "cpu_ms_per_agent_turn", "mem_peak_mib")


def agent_route(kind="rpc", metric="fit", view=None, env=None):
    """The address of the Agent swarming page with one cell of its picker chosen. A per-N metric is asked for as the line chart unless a view is given: the page's own default is Bars (default_view)."""
    q = [f"e={env}"] if env else []
    q.append(f"m={kind}.{metric}")
    if view or metric != "fit":
        q.append(f"view={view or 'line'}")
    return AGENTS + "?" + "&".join(q)


# every cell of the picker that the tests read, rendered once with the rest of the site
AGENT_ROUTES = [agent_route(k, m) for k in KINDS4 for m in ("fit",) + PER_N] + [agent_route("rpc", m, "bars") for m in PER_N]
DEFAULT_VIEW = [AGENTS + f"?m=rpc.{m}" for m in PER_N]   # no `view`: the page's own default, Bars


def main_card(page):
    """The one primary chart card of the Agent swarming page."""
    return re.search(r'<section class="card small" id="agents-main"[^>]*>.*?</section>', page, re.S).group(0)


def fit_rows(page):
    """({harness slug: html of its bar row}, html of the card) of the primary card of a page that has the agents that fit chosen."""
    card = main_card(page)
    rows = {}
    for r in card.split('<div class="brow ')[1:]:
        if r.startswith("baxis"):
            continue
        hit = re.search(r'href="#/harness/([^"]+)"', r)
        rows[hit.group(1)] = r
    return rows, card


def span_top(*entries):
    """The largest number on the bars of an answer card: the end of the whisker of each arm, at least 2."""
    top = 2
    for entry in entries:
        for a in entry["arms"].values():
            if "rungs" in a:
                top = max(top, a["range"][1] if a["exact"] else a["between"][1] if "between" in a else a["at_least"])
    return top


def measured_limits(raw, arm, scenario):
    return [s["agents_limit"] for s in sorted(raw["samples"], key=lambda s: s["round"]) if s["arm"] == arm and s["scenario"] == scenario and not s["warmup"]]


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Swarms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = with_swarms(with_write(demo_raw(rounds=4)))
        cls.out = built(cls.raw, faith=False)
        cls.views = render_all(cls.out, AGENT_ROUTES)
        cls.data = site_data(cls.out)
        cls.page = cls.views["#/r/agent-swarming"]
        cls.env = cls.data["scale"]["envelopes"][0]

    def arm(self, kind, arm):
        return self.env["kinds"][kind]["arms"][arm]

    def rows(self, kind, ext=False):
        """The bar rows of the agents that fit, in RPC or print mode, without or with the ten extensions: one page of the picker for each."""
        return fit_rows(self.views[agent_route(kind + ("-ext10" if ext else ""))])

    def chart(self, kind, metric, view=None):
        return main_card(self.views[agent_route(kind, metric, view)])

    def test_the_scale_samples_are_not_cells_of_the_grid(self):
        self.assertFalse([c for c in self.data["cells"] if c["scenario"].startswith("scale/")])
        self.assertFalse([m for m in self.data["metrics"] if m["scenario"].startswith("scale/")])

    def test_the_page_has_the_section_skeleton_and_states_the_envelope_once(self):
        self.assertEqual(len(self.data["scale"]["envelopes"]), 1)
        largest = max(p["pids_max"] for s in self.raw["samples"] if "probes" in s for p in s["probes"])
        self.assertEqual((self.env["memory_mib"], self.env["cores"], self.env["pids_max"]), (4096, 8, largest))
        self.assertEqual(self.env["cpus"], [40, 41, 42, 43, 44, 45, 46, 47])
        text = visible_text(self.page)
        self.assertEqual(text.count("Memory and swap are the same number"), 1)
        self.assertEqual(self.page.count('id="envelope"'), 1)
        self.assertLess(self.page.index('id="agents-main"'), self.page.index('id="envelope"'))   # the answer first, the envelope after
        self.assertLess(self.page.index('id="all-agent-swarming"'), self.page.index('id="envelope"'))
        self.assertIn("8 cores", plain(self.page))
        self.assertIn("64 for each agent and 1,024 more", text)
        self.assertIn(f"The largest probe set {largest:,} processes", text)
    def test_a_search_arm_has_the_exact_limit_the_median_of_the_measured_rounds_and_their_range(self):
        a = self.arm("rpc", "pi-node")
        limits = measured_limits(self.raw, "pi-node", "scale/agents-limit")
        self.assertEqual(len(limits), 5)
        self.assertEqual(a["limits"], limits)
        self.assertEqual((a["exact"], a["limit"], a["max_ok"], a["range"], a["capped"], a["cap"], a["resolution"]), (True, statistics.median_low(limits), statistics.median_low(limits), [min(limits), max(limits)], False, 8192, 1))
        self.assertNotIn("between", a)
        self.assertEqual(a["skipped"], [])
        self.assertTrue(a["probe_count"] > 6)

    def test_a_harness_that_stopped_says_where_and_why(self):
        a = self.arm("rpc", "pi-node")
        self.assertEqual((a["stop"]["n"], a["first_failure"], a["stop"]["cause"], a["cause"], a["stop"]["oom_kills"]), (a["limit"] + 1, a["limit"] + 1, "oom", "oom", 3))
        self.assertIn("out of memory", a["failure"])
        g = self.arm("rpc", "demo-gamma")
        self.assertEqual((g["limit"], g["stop"]["n"], g["stop"]["cause"]), (63, 64, "timeout"))
        rows, card = self.rows("rpc")
        pi = htmlmod.unescape(rows["pi-node"])
        self.assertIn("did not fit in 4 GiB", pi)   # the reader-facing words, in the tooltip
        self.assertIn("the kernel killed 3 agents", pi)   # the cause detail is secondary: tooltip only
        self.assertNotIn("kernel killed", plain(card.replace('data-tip="', 'x="')))
        self.assertIn("64 agents timed out", plain(rows["demo-gamma"]))   # a stop that is not a fit shows its own words beside the bar

    def test_the_bar_says_the_exact_number_and_its_tooltip_the_range_over_the_rounds_and_no_page_says_or_more(self):
        rows, _ = self.rows("rpc")
        a = self.arm("rpc", "pi-node")
        self.assertIn(f"<b>{a['limit']}</b>", rows["pi-node"])
        tip = htmlmod.unescape(rows["pi-node"])
        self.assertIn(f"{a['limit']} agents fit in 4 GiB.", tip)
        self.assertIn(f"{a['range'][0]} to {a['range'][1]} over 5 rounds.", tip)
        self.assertIn('class="bw"', rows["pi-node"])   # the whisker: the lowest to the highest round
        beta = self.rows("print")[0]["demo-beta"]   # the stall comes at 32 agents in every round: one limit, no range to draw
        self.assertNotIn('class="bw"', beta)
        self.assertIn("The same in 5 rounds.", htmlmod.unescape(beta))
        for route, html in self.views.items():
            if route in ("#/r/agent-swarming", "#/") or route.startswith(("#/swarm/", "#/harness/")):
                self.assertNotRegex(htmlmod.unescape(html), r"\bor more\b", route)

    def test_an_arm_that_completes_the_cap_reads_at_least_with_the_cap_and_the_bar_is_full(self):
        a = self.arm("print", "demo-gamma")
        self.assertEqual((a["limit"], a["capped"], a["cap"], a["or_more"], a["stop"], a["first_failure"], a["cause"]), (8192, True, 8192, True, None, None, None))
        rows, card = self.rows("print")
        self.assertIn("<b>at least 8192 (cap)</b>", rows["demo-gamma"])
        self.assertIn("--f:1.0000", rows["demo-gamma"])
        self.assertIn("At least 8192 agents fit in 4 GiB: the search stopped at its cap.", htmlmod.unescape(rows["demo-gamma"]))

    def test_a_limit_of_zero_says_not_even_one_agent_finished(self):
        a = self.arm("print-ext10", "demo-alpha")
        self.assertEqual((a["limit"], a["max_ok"], a["first_failure"], a["stop"]["n"], a["stop"]["cause"], a["capped"], a["range"]), (0, 0, 1, 1, "oom", False, [0, 0]))
        rows, _ = self.rows("print", True)
        row = rows["demo-alpha"]
        self.assertIn("<b>0</b>", row)
        self.assertNotIn('class="bf"', row)
        self.assertIn("Not even one agent finished.", htmlmod.unescape(row))
        self.assertIn("323 fewer", plain(row))   # against the 323 without the extensions
        derivation = self.views["#/swarm/4g-8c/print-ext10/demo-alpha/1"]
        self.assertIn("1 agent did not fit in 4 GiB", plain(derivation))
        self.assertIn("with 10 extensions)", plain(self.views["#/harness/demo-alpha"]))

    def test_a_stall_reads_like_an_oom_kill_and_says_in_the_detail_that_nothing_was_killed(self):
        a = self.arm("print", "demo-beta")
        self.assertEqual((a["limit"], a["stop"]["n"], a["stop"]["cause"]), (31, 32, "stall"))
        self.assertEqual(self.data["scale"]["causes"]["stall"]["word"], self.data["scale"]["causes"]["oom"]["word"])
        rows, card = self.rows("print")
        tip = htmlmod.unescape(rows["demo-beta"])
        self.assertIn("32 agents did not fit in 4 GiB: stalled at the limit, nothing was killed.", tip)
        self.assertNotIn("stall", plain(re.sub(r'data-tip="[^"]*"', "", rows["demo-beta"])))
        derivation = self.views["#/swarm/4g-8c/print/demo-beta/32"]
        self.assertIn("32 agents did not fit in 4 GiB: stalled at the limit, nothing was killed.", plain(derivation))
        for r in ("#/r/agent-swarming", "#/"):
            self.assertNotIn("out of memory", visible_text(self.views[r]), r)

    def test_a_harness_without_an_rpc_mode_is_one_not_run_line_with_the_recorded_reason(self):
        b = self.arm("rpc", "demo-beta")
        self.assertIn("no Pi-dialect RPC mode", b["cannot"])
        rows, card = self.rows("rpc")
        self.assertNotIn("demo-beta", rows)
        self.assertEqual(plain(card).count("Can't run: "), 1)
        self.assertIn("Can't run: demo-beta (no Pi-dialect RPC mode).", plain(card))
        self.assertNotIn("n/a:", plain(card))
        self.assertIn("its own protocol is not Pi", htmlmod.unescape(card))   # the reason in full, in the tooltip
        self.assertNotIn("demo-beta", self.rows("rpc", True)[0])   # nor does it have a second line for the extensions: it has no first

    def test_the_headline_has_one_bar_per_harness_in_the_site_order_with_its_number_on_the_bar_and_a_labelled_log_axis(self):
        order = [h["slug"] for h in self.data["harnesses"]]
        for kind in ("rpc", "print"):
            rows, card = self.rows(kind)
            arms = self.env["kinds"][kind]["arms"]
            have = [h for h in self.data["harnesses"] if h["id"] in arms and "rungs" in arms[h["id"]]]
            self.assertEqual(list(rows), [h["slug"] for h in have], kind)
            self.assertEqual(list(rows), [s for s in order if s in rows])
            top = span_top(self.env["kinds"][kind], self.env["kinds"].get(kind + "-ext10", {"arms": {}}))
            for h in have:
                a = arms[h["id"]]
                self.assertIn(f"<b>{a['max_ok'] if not a['capped'] else 'at least ' + str(a['max_ok']) + ' (cap)'}", rows[h["slug"]], (kind, h["id"]))
                f = float(re.search(r"--f:([\d.]+)", rows[h["slug"]]).group(1))
                self.assertAlmostEqual(f, math.log2(a["max_ok"]) / math.log2(top) if a["max_ok"] > 1 else 0, places=3, msg=(kind, h["id"]))   # the length is proportional to log2 of the count
            labels = re.findall(r'<span class="tl" style="--f:([\d.]+)">(\d+)</span>', card)
            self.assertEqual([int(n) for _, n in labels][:3], [1, 4, 16], kind)
            self.assertLessEqual(int(labels[-1][1]), top)   # a tick is a power of 4: the axis does not end at the largest number
            for f, n in labels:
                self.assertAlmostEqual(float(f), math.log2(int(n)) / math.log2(top), places=3)
            self.assertIn("agents, log scale", card)
            self.assertNotIn("data-view-switch=", card)   # no Chart/Table switch: the full table is below
            self.assertEqual(len(re.findall(r"<svg", card)), 0)   # the bars are HTML: one component, the same on the Overview tile
        self.assertNotIn("data-view-switch=", self.page)

    def test_the_workload_with_the_ten_extensions_is_a_row_of_the_picker_on_the_same_axis_with_the_gap_to_the_one_without(self):
        for kind in ("rpc", "print"):
            x = self.env["kinds"][kind + "-ext10"]
            self.assertTrue(x["title"].endswith("with 10 extensions"))
            self.assertIn(f'aria-label="{x["title"]}: Agents that fit"', self.views[AGENTS])
            plain_rows, _ = self.rows(kind)
            ext_rows, card = self.rows(kind, True)
            self.assertIn("pi-node", ext_rows)
            self.assertIn(x["title"] + ": Agents that fit", plain(card))
            top = span_top(self.env["kinds"][kind], x)
            for slug, row in ext_rows.items():
                h = next(h for h in self.data["harnesses"] if h["slug"] == slug)["id"]
                a, b = x["arms"][h], self.env["kinds"][kind]["arms"][h]
                self.assertTrue(a["exact"] and a["extensions"] == 10 and a["scenario"].endswith("-ext10"), (kind, h))
                self.assertIn(f"<b>{a['limit']}</b>", row)
                f = float(re.search(r"--f:([\d.]+)", row).group(1))
                self.assertAlmostEqual(f, math.log2(a["limit"]) / math.log2(top) if a["limit"] > 1 else 0, places=3)   # the same axis as the page without the extensions
                self.assertLess(a["limit"], b["limit"])   # the extensions cost agents
                self.assertIn(f"{b['limit'] - a['limit']} fewer", plain(row))
                self.assertEqual(card.count(f'href="#/harness/{slug}"'), 1)   # the harness is named once
            self.assertNotIn("<svg", card)
    def test_a_harness_that_does_not_load_pi_extensions_is_one_muted_line_with_the_reason(self):
        self.assertEqual(self.arm("rpc-ext10", "demo-gamma")["cannot"], "it does not load Pi extensions")
        self.assertEqual(self.arm("print-ext10", "demo-beta")["cannot"], "it loads only part of Pi's extensions")
        rows, card = self.rows("print", True)
        self.assertEqual(list(rows), ["pi-node", "demo-alpha"])   # the second has a limit of 0: it ran
        text = plain(card)
        self.assertIn("Can't run: demo-gamma (it does not load Pi extensions).", text)
        self.assertIn("Can't run: demo-beta (it loads only part of Pi's extensions).", text)
        self.assertIn("it does not load Pi extensions", htmlmod.unescape(card))   # the reason in full, in the tooltip too
    def test_a_derivation_page_of_the_extension_bar_names_the_scenario_and_the_extensions(self):
        a = self.arm("rpc-ext10", "pi-node")
        route = f"#/swarm/4g-8c/rpc-ext10/pi-node/{a['limit']}"
        text = plain(self.views[route])
        self.assertIn("RPC agents with 10 extensions", text)
        self.assertIn("scale/agents-ext10", text)
        self.assertIn("This is the limit the page shows", text)
        self.assertIn(f'href="{route}"', self.rows("rpc", True)[0]["pi-node"])

    def test_every_rung_is_marked_ok_or_stopped_from_every_measured_round_and_pools_the_probes_of_the_rounds(self):
        mixed = partial = 0
        for kind, entry in self.env["kinds"].items():
            for arm, a in entry["arms"].items():
                for r in a.get("rungs", []):
                    self.assertEqual(r["status"] == "ok", all(x["ok"] for x in r["rounds"]), (arm, kind, r["n"]))
                    self.assertTrue(all(not x["warmup"] for x in r["rounds"]))
                    mixed += any(x["ok"] for x in r["rounds"]) and not all(x["ok"] for x in r["rounds"])
                    partial += len(r["rounds"]) < len(a["limits"])
        self.assertGreater(mixed, 0)    # a bisection tries the number between in some rounds only, and a round may pass where another failed
        self.assertGreater(partial, 0)
        a = self.arm("rpc", "pi-node")
        self.assertEqual([r["n"] for r in a["rungs"]], sorted({p["n"] for s in self.raw["samples"] if s["arm"] == "pi-node" and s["scenario"] == "scale/agents-limit" and not s["warmup"] for p in s["probes"]}))
        self.assertEqual(self.env["kinds"]["rpc"]["ns"], sorted({r["n"] for x in self.env["kinds"]["rpc"]["arms"].values() for r in x.get("rungs", [])}))
        r = next(r for r in a["rungs"] if r["n"] == 4)
        raw = [p for s in self.raw["samples"] if s["arm"] == "pi-node" and s["scenario"] == "scale/agents-limit" and not s["warmup"] for p in s["probes"] if p["n"] == 4]
        self.assertEqual(len(raw), 5)
        self.assertAlmostEqual(r["med"]["mem_per_agent_mib"], statistics.median(p["mem_per_agent_mib"] for p in raw))
        self.assertAlmostEqual(r["med"]["mem_peak_mib"], statistics.median(p["mem_peak_mib"] for p in raw))
        rare = next(r for r in a["rungs"] if len(r["rounds"]) < 5)
        text = plain(self.views[f"#/swarm/4g-8c/rpc/pi-node/{rare['n']}"])
        self.assertIn("Rounds that tried this number: " + ", ".join(str(x["round"]) for x in rare["rounds"]) + " of 5.", text)
        self.assertIn("Every round tried this number.", plain(self.views["#/swarm/4g-8c/rpc/pi-node/4"]))

    def test_every_per_agent_metric_is_a_line_over_the_number_of_agents_in_one_axis_style(self):
        self.assertNotRegex(self.page, r'id="sc-')   # no chart for each metric any more: the picker chooses one
        for kind in ("rpc", "print"):
            for key in ("mem_per_agent_mib", "turns_per_s", "cpu_ms_per_agent_turn"):
                card = self.chart(kind, key)
                self.assertEqual(len(re.findall(r"<svg", card)), 1, (kind, key))
                self.assertIn('viewBox="0 0 ', card)
                self.assertRegex(card, r'<text class="axl"[^>]*>agents →</text>')
                self.assertNotIn("data-view-switch", card)
                log = "log scale" in re.search(r'<text class="unit"[^>]*>([^<]*)</text>', card).group(1)
                self.assertEqual(log, key in ("mem_per_agent_mib", "cpu_ms_per_agent_turn"), key)   # memory and CPU on a log axis, throughput on a linear one
        table = " ".join(re.findall(r'<table class="data grid" id="t-all-agent-swarming-.*?</table>', self.page, re.S))
        self.assertIn("Memory of the whole container", table)   # the full name of a column is its tooltip
        self.assertRegex(table, r"95th percentile of a turn or a task")
    def test_the_x_axis_of_a_chart_is_labelled_at_powers_of_two_however_many_numbers_were_probed(self):
        card = self.chart("rpc", "mem_per_agent_mib")
        labels = [int(x) for x in re.findall(r'<text class="xl"[^>]*>(\d+)</text>', card)]
        self.assertEqual(labels[:3], [1, 2, 4])
        self.assertTrue(all(n & (n - 1) == 0 for n in labels), labels)

    def test_a_log_axis_has_decade_ticks_and_a_line_name_at_the_end_of_each_line(self):
        card = self.chart("rpc", "mem_per_agent_mib")
        ticks = [float(t.replace(",", "")) for t in re.findall(r'<text class="yl"[^>]*>([\d.,]+)</text>', card)]
        self.assertGreaterEqual(len(ticks), 3)
        ratios = [b / a for a, b in zip(ticks, ticks[1:])]
        self.assertTrue(all(r > 1.5 for r in ratios), ticks)
        names = re.findall(r'<text class="elabel"[^>]*><title>([^<]+)</title>', card)
        want = [h["name"] for h in self.data["harnesses"] if any(r["status"] == "ok" for r in self.env["kinds"]["rpc"]["arms"].get(h["id"], {}).get("rungs", []))]
        self.assertEqual(sorted(names), sorted(want))
        ys = sorted(float(y) for y in re.findall(r'<text class="elabel" x="[\d.]+" y="([\d.]+)"', card))
        self.assertTrue(all(b - a >= 11.9 for a, b in zip(ys, ys[1:])), ys)   # names are pushed apart

    def test_the_rpc_throughput_chart_marks_where_every_cpu_is_busy(self):
        card = self.chart("rpc", "turns_per_s")
        self.assertIn('class="level"', card)
        self.assertIn("turns per second with all CPUs busy", plain(card))
        prt = self.chart("print", "turns_per_s")
        self.assertNotIn('class="level"', prt)

    def test_the_cpu_and_throughput_charts_share_the_window_and_print_says_tasks(self):
        self.assertEqual({m["key"]: m["title"] for m in self.data["scale"]["metrics"]["print"]}["turns_per_s"], "Tasks per second")
        self.assertEqual({m["key"]: m["title"] for m in self.data["scale"]["metrics"]["print"]}["cpu_ms_per_agent_turn"], "CPU per task")
        self.assertEqual({m["key"]: m["title"] for m in self.data["scale"]["metrics"]["rpc"]}["cpu_ms_per_agent_turn"], "CPU per agent-turn")
        self.assertIn("turn phase only", plain(self.chart("rpc", "cpu_ms_per_agent_turn")))
        self.assertIn("whole sample", plain(self.chart("print", "cpu_ms_per_agent_turn")))
        self.assertFalse(self.env["kinds"]["rpc"]["cpu_legacy"])
        self.assertFalse(self.env["kinds"]["rpc-ext10"]["cpu_legacy"])
        r = next(r for r in self.arm("rpc", "pi-node")["rungs"] if r["n"] == 8)
        self.assertIn("start_cpu_ms_per_agent", r["med"])

    def test_the_first_number_that_did_not_finish_is_a_cross_on_the_axis_with_its_cause_in_the_tooltip(self):
        card = self.chart("rpc", "turns_per_s")
        svg = card[card.index("<svg"):card.index("</svg>")]
        stops = [a for a in self.env["kinds"]["rpc"]["arms"].values() if a.get("stop")]
        self.assertEqual(len(re.findall(r'class="stopx"', svg)), len(stops))
        self.assertIn("did not fit in 4 GiB", htmlmod.unescape(svg))
        self.assertIn("the kernel killed 3 agents", htmlmod.unescape(svg))
        self.assertIn("timed out", svg)
        ticks = [float(t.replace(",", "")) for t in re.findall(r'<text class="yl"[^>]*>([\d.,]+)</text>', svg)]
        done = [r["med"]["turns_per_s"] for a in self.env["kinds"]["rpc"]["arms"].values() for r in a.get("rungs", []) if r["status"] == "ok"]
        self.assertLessEqual(max(ticks), max(done) * 1.2)   # a stop's own timing does not set the scale
        self.assertEqual(min(ticks), 0)

    def test_the_spread_across_rounds_is_a_whisker_on_each_point_that_more_than_one_round_probed(self):
        r = next(r for r in self.arm("rpc", "pi-node")["rungs"] if r["n"] == 8)
        lo, hi = r["spread"]["turns_per_s"]
        self.assertLess(lo, r["med"]["turns_per_s"] + 1e-9)
        self.assertGreaterEqual(hi, r["med"]["turns_per_s"] - 1e-9)
        card = self.chart("rpc", "turns_per_s")
        self.assertGreater(card.count('class="whisker"'), 10)
        self.assertIn("rounds ", htmlmod.unescape(card))
        single = next(r for a in self.env["kinds"]["rpc"]["arms"].values() for r in a.get("rungs", []) if len(r["rounds"]) == 1 and r["status"] == "ok")   # only one round tried this number
        self.assertNotIn("turns_per_s", single["spread"])

    def test_every_mark_has_a_tooltip_and_opens_a_derivation_page_with_one_row_for_each_value(self):
        marks = re.findall(r'<a href="(#/swarm/[^"]+)" aria-label="[^"]*">(.*?)</a>', "".join(self.views[r] for r in AGENT_ROUTES), re.S)
        self.assertGreater(len(marks), 100)
        for href, inner in marks[:400]:
            self.assertIn('data-tip="', inner)
        sample_href = htmlmod.unescape(marks[0][0])
        page = app(self.out, f"console.log(JSON.stringify(A.render(D,{json.dumps(sample_href)},{{width:1200}}).html))")
        self.assertIn("This number of agents, value by value", page)
        self.assertIn('<table class="data" id="t-swarm-', page)
        self.assertIn("Smallest to largest round", page)
        self.assertNotRegex(page, r"Round 1</button>")   # no column for each round: a median, a range and a dot for each round
        self.assertEqual(page.count('<svg class="mini"') > 5, True)
        for route, text in self.views.items():
            if route.startswith("#/swarm/"):
                self.assertNotIn("<h1>Not found</h1>", text, route)
        text = plain(self.views["#/swarm/4g-8c/rpc/pi-node/32"])
        self.assertIn("32 agents did not fit in 4 GiB: the kernel killed 3 agents. Every round tried this number.", text)
        self.assertNotIn("larger steps were not tried", text)   # a search tries the numbers in between
        self.assertIn("workload scale/agents-limit", text)
    def test_the_memory_of_a_probe_is_worked_out_in_one_line_for_the_median_round(self):
        text = plain(self.views["#/swarm/4g-8c/rpc/pi-node/8"])
        self.assertEqual(len(re.findall(r"Round \d+ has the median value", text)), 1)
        self.assertRegex(text, r"Round \d+ has the median value: \(\d[\d.,]* (MiB|GiB) - 120 MiB\) / 8 = [\d.,]+ MiB per agent")

    def test_the_mock_saturation_flag_is_shown_on_the_headline_the_chart_and_the_probe(self):
        self.assertIn("The scripted model was saturated", self.page)
        self.assertIn("⚠", self.page)
        self.assertTrue(self.arm("print", "demo-alpha")["rungs"][-1]["mock_saturated"])
        self.assertFalse(self.arm("print", "pi-node")["rungs"][0]["mock_saturated"])

    def test_the_new_terms_are_in_the_glossary_and_every_link_to_one_resolves(self):
        slugs = {g["slug"] for g in self.data["glossary"]}
        for slug in ("swarm", "envelope", "rung", "agent-turn", "oom-kill", "stall", "fit", "makespan", "turns-per-second", "p95", "mock-saturated", "cpuset", "pids-limit", "lockstep"):
            self.assertIn(slug, slugs)
            self.assertIn(f'id="g-{slug}"', self.views["#/glossary"])
        for route, text in self.views.items():
            if route in ("#/r/agent-swarming", "#/") or route.startswith("#/swarm/"):
                for slug in re.findall(r'data-term="([^"]+)"', text):
                    self.assertIn(slug, slugs, route)
                loose = {w for w in re.findall(r"(?<![\w/.-])([A-Z][A-Z0-9]+(?:/[A-Z]+)?)(?![\w-])", visible_text(text)) if w not in WORDS_OK}
                self.assertEqual(loose, set(), route)
        for term in ("envelope", "rung", "agent-turn", "lockstep", "p95", "cpuset", "pids-limit", "mock-saturated"):
            self.assertIn(f'data-term="{term}"', self.page)
        by = {g["slug"]: g for g in self.data["glossary"]}
        self.assertEqual(by["rung"]["term"], "probe")
        self.assertNotIn("stops at once", by["rung"]["text"])
        self.assertNotRegex(by["fit"]["text"], r"or more")

    def test_metric_directions_are_declared(self):
        want = {"turns_per_s": "higher", "mem_per_agent_mib": "lower", "mem_peak_mib": "lower", "latency_ms_p95": "lower", "cpu_ms_per_agent_turn": "lower", "wall_ms_p95": "lower", "makespan_ms": "lower"}
        for kind in ("rpc", "print"):
            got = {m["key"]: m["direction"] for m in self.data["scale"]["metrics"][kind]}
            for k, d in want.items():
                if k in got:
                    self.assertEqual(got[k], d)
        self.assertIn("higher is better", self.chart("rpc", "turns_per_s"))
        self.assertIn("lower is better", self.chart("rpc", "mem_per_agent_mib"))

    def test_the_overview_has_one_many_agents_tile_with_the_same_numbers_as_the_pages_of_the_section(self):
        home = self.views["#/"]
        tiles = re.findall(r'<a class="card tile" href="#/r/agent-swarming">.*?</a>', home, re.S)
        self.assertEqual(len(tiles), 1)
        tile = tiles[0]
        labels = lambda html: re.findall(r'<b>([^<]+)</b></(?:a|span)></span>', html)
        self.assertEqual(sorted(labels(tile)), sorted(labels(self.rows("rpc")[1]) + labels(self.rows("rpc", True)[1])))   # the tile pairs what the section draws on two pages
        self.assertIn("with 10 extensions", plain(tile))   # the pair is on the tile
        self.assertNotIn("<svg", tile)
        self.assertIn("Can't run: demo-beta (no Pi-dialect RPC mode).", plain(tile))
        self.assertIn("Can't run with 10 extensions: demo-gamma (it does not load Pi extensions).", plain(tile))
    def test_the_harness_page_says_how_many_agents_fit_with_and_without_the_extensions(self):
        page = plain(self.views["#/harness/pi-node"])
        rpc, prt = self.arm("rpc", "pi-node"), self.arm("print", "pi-node")
        x, y = self.arm("rpc-ext10", "pi-node"), self.arm("print-ext10", "pi-node")
        self.assertIn(f"{rpc['limit']} RPC ({x['limit']} with 10 extensions)", page)
        self.assertIn(f"{prt['limit']} print-mode ({y['limit']} with 10 extensions)", page)
        gamma = plain(self.views["#/harness/demo-gamma"])
        self.assertIn("63 RPC", gamma)
        self.assertIn("at least 8192 (cap) print-mode", gamma)
        self.assertIn("Agent swarming, RPC, 10 extensions", gamma)   # the workload it did not run, with its reason
        self.assertIn("it does not load Pi extensions", gamma)


    def test_the_harness_page_does_not_list_a_rung_not_reached_as_a_workload_it_cannot_run(self):
        page = self.views["#/harness/pi-node"]
        self.assertNotIn("not reached", page)
        gamma = self.views["#/harness/demo-gamma"]
        self.assertIn("its tool set has no write tool", gamma)

    def test_no_em_dash_and_no_ranking_words_on_the_scale_views(self):
        for route, text in self.views.items():
            if route in ("#/r/agent-swarming", "#/") or route.startswith("#/swarm/"):
                shown = visible_text(text)
                self.assertNotIn("\u2014", shown, route)
                self.assertNotRegex(shown, r"(?i)\bfastest|best harness|\bscore\b|\bgrade\b|leaderboard", route)


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Ladders(unittest.TestCase):
    """A run made before the search: one sample for each rung, and `not reached` skips. It must read as a range, never as a false exact number."""

    @classmethod
    def setUpClass(cls):
        raw = with_ladders(with_write(demo_raw(rounds=4)))
        cls.out = built(raw, faith=False)
        cls.views = render_all(cls.out, AGENT_ROUTES)
        cls.data = site_data(cls.out)
        cls.page = cls.views["#/r/agent-swarming"]
        cls.env = cls.data["scale"]["envelopes"][0]

    def arm(self, kind, arm):
        return self.env["kinds"][kind]["arms"][arm]

    def rows(self, kind, ext=False):
        return fit_rows(self.views[agent_route(kind + ("-ext10" if ext else ""))])

    def test_a_ladder_that_stopped_is_the_range_between_its_last_complete_rung_and_the_one_before_the_first_stop(self):
        a = self.arm("rpc", "pi-node")
        self.assertEqual((a["exact"], a["max_ok"], a["between"], a["stop"]["n"], a["stop"]["cause"]), (False, 16, [16, 31], 32, "oom"))
        self.assertNotIn("at_least", a)
        self.assertNotIn("limit", a)
        self.assertEqual([x["n"] for x in a["skipped"]], [64, 128, 256])
        self.assertTrue(all(x["reason"] == "not reached: stopped at 32 agents (out of memory)" for x in a["skipped"]))
        rows, card = self.rows("rpc")
        self.assertIn("<b>16 to 31</b>", rows["pi-node"])
        self.assertIn("Between 16 and 31 agents fit in 4 GiB.", htmlmod.unescape(rows["pi-node"]))
        self.assertIn("did not fit in 4 GiB", htmlmod.unescape(rows["pi-node"]))
        self.assertIn("3 larger steps not tried.", htmlmod.unescape(rows["pi-node"]))
        top = span_top(self.env["kinds"]["rpc"])
        self.assertIn('class="bw"', rows["pi-node"])   # the bar ends at 16 and the whisker reaches 31
        f = float(re.search(r"--f:([\d.]+)", rows["pi-node"]).group(1))
        self.assertAlmostEqual(f, math.log2(16) / math.log2(top), places=3)
        self.assertIn("--b:" + format(math.log2(31) / math.log2(top), ".4f"), rows["pi-node"])

    def test_a_ladder_that_never_stopped_reads_at_least_its_top_and_never_or_more(self):
        a = self.arm("print", "demo-alpha")   # 12 MiB for each agent: the ladder reaches its top of 256
        self.assertEqual((a["exact"], a["max_ok"], a["at_least"], a["stop"]), (False, 256, 256, None))
        self.assertNotIn("between", a)
        rows, _ = self.rows("print")
        self.assertRegex(htmlmod.unescape(rows["demo-alpha"]), r"<b>at least 256 \(the ladder's top\)[^<]*</b>")
        self.assertIn("At least 256 agents fit in 4 GiB: the ladder ended there.", htmlmod.unescape(rows["demo-alpha"]))
        for route, html in self.views.items():
            if route in ("#/r/agent-swarming", "#/") or route.startswith(("#/swarm/", "#/harness/")):
                self.assertNotRegex(htmlmod.unescape(html), r"\bor more\b", route)

    def test_a_harness_that_timed_out_is_a_range_and_says_so_beside_the_bar(self):
        g = self.arm("rpc", "demo-gamma")
        self.assertEqual((g["max_ok"], g["between"], g["stop"]["n"], g["stop"]["cause"]), (32, [32, 63], 64, "timeout"))
        rows, _ = self.rows("rpc")
        self.assertIn("64 agents timed out", plain(rows["demo-gamma"]))

    def test_the_rungs_of_a_ladder_still_have_their_derivation_pages_and_say_the_larger_steps_were_not_tried(self):
        text = plain(self.views["#/swarm/4g-8c/rpc/pi-node/32"])
        self.assertIn("32 agents did not fit in 4 GiB: the kernel killed 3 agents. The larger steps were not tried.", text)
        self.assertIn("Not tried: 64, 128, 256", text)
        self.assertIn("workload scale/agents-32", text)
        self.assertIn("All 8 agents finished, in every one of 3 rounds that tried it.", plain(self.views["#/swarm/4g-8c/rpc/pi-node/8"]))
        for route, html in self.views.items():
            if route.startswith("#/swarm/"):
                self.assertNotIn("<h1>Not found</h1>", html, route)

    def test_a_run_without_the_ten_extensions_has_no_pair(self):
        self.assertEqual(sorted(self.env["kinds"]), ["print", "rpc"])
        self.assertNotIn("ext10", self.page)   # no row in the picker, no cell in the table
        self.assertNotIn("with 10 extensions", plain(self.page))

    def test_a_run_that_predates_the_cpu_window_draws_no_rpc_cpu_chart_and_labels_the_whole_sample_row_instead_of_a_box(self):
        raw = demo_raw(rounds=4)
        samples, skipped = ladder("pi-node", "rpc", per_agent_mib=190, legacy=True)
        raw["samples"] += samples
        raw["skipped"] += skipped
        out = built(raw, faith=False)
        views = render_all(out, [agent_route("rpc", "mem_per_agent_mib")])
        data = site_data(out)["scale"]["envelopes"][0]
        self.assertTrue(data["kinds"]["rpc"]["cpu_legacy"])
        self.assertFalse([r for r in data["kinds"]["rpc"]["arms"]["pi-node"]["rungs"] if "cpu_ms_per_agent_turn" in r["med"]])
        page = views["#/r/agent-swarming"]
        self.assertNotIn("m=rpc.cpu_ms_per_agent_turn", page)   # the picker has no cell for it
        self.assertEqual(plain(page).count("CPU per agent-turn is not drawn for RPC agents in this run"), 1)
        derivation = views["#/swarm/4g-8c/rpc/pi-node/8"]
        self.assertNotIn("CPU per agent-turn", plain(derivation))   # no box, no row: the whole-sample row says what it is
        self.assertNotIn('class="caveat"', derivation)
        self.assertIn("CPU of the container, whole sample, start-up included", derivation)

    def test_a_stopped_rung_is_a_cross_on_the_axis_and_the_pids_limit_is_the_runs_own(self):
        svg = re.search(r"<svg.*?</svg>", main_card(self.views[agent_route("rpc", "turns_per_s")]), re.S).group(0)
        self.assertEqual(len(re.findall(r'class="stopx"', svg)), len([a for a in self.env["kinds"]["rpc"]["arms"].values() if a.get("stop")]))
        self.assertEqual(self.env["pids_max"], 32768)
        self.assertIn("The largest probe set 32,768 processes", plain(self.page))

    def test_the_tile_and_the_harness_page_work_for_an_earlier_run(self):
        home = self.views["#/"]
        tile = re.search(r'<a class="card tile" href="#/r/agent-swarming">.*?</a>', home, re.S).group(0)
        self.assertIn("<b>16 to 31</b>", tile)
        harness = plain(self.views["#/harness/pi-node"])
        self.assertIn("16–31 RPC", harness)
        self.assertIn("16–31 print-mode", harness)
        self.assertNotIn("Agent swarming, RPC, 10 extensions", harness)


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class MixedRuns(unittest.TestCase):
    def test_an_arm_with_search_samples_is_shown_by_them_and_one_with_only_rungs_by_its_ladder(self):
        raw = demo_raw(rounds=4)
        raw["samples"] += search("pi-node", "rpc", per_agent_mib=190)
        samples, skipped = ladder("demo-alpha", "rpc", per_agent_mib=28)
        raw["samples"] += samples
        raw["skipped"] += skipped
        data = site_data(built(raw, faith=False))["scale"]["envelopes"][0]["kinds"]["rpc"]["arms"]
        self.assertTrue(data["pi-node"]["exact"])
        self.assertFalse(data["demo-alpha"]["exact"])
        self.assertEqual(data["demo-alpha"]["between"], [128, 255])


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Write(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = built(with_write(demo_raw(rounds=4)), faith=False)
        cls.data = site_data(cls.out)
        cls.page = app(cls.out, "console.log(JSON.stringify(A.render(D,'#/r/large-writes?v=values',{width:1200}).html))")
        cls.tables = metric_tables(cls.page, "all-large-writes")
        cls.table = cls.tables[0]["text"]   # the main table of the one workload

    def rows(self):
        return {re.search(r'href="#/harness/([^"]+)"', r).group(1): r for r in re.findall(r'<tr class="h-[^"]*">.*?</tr>', self.table, re.S)}

    def keys(self):
        return re.findall(r'<a class="info" href="#/metric/([^"?]+)', self.table)

    def column(self, metric):
        return [k.rsplit(".", 1)[1] for k in self.keys()].index(metric)

    def test_the_section_has_the_time_cpu_and_peak_memory_of_writing_a_200_kb_file_in_one_table_with_the_50_kb_file_beside_it(self):
        names = [k.rsplit(".", 1)[1] for k in self.keys()]
        for want in ("kb200_wall_ms", "kb200_cpu_ms", "kb200_peak_mem_mib", "kb50_wall_ms", "kb50_cpu_ms", "kb50_peak_mem_mib"):
            self.assertIn(want, names)
        self.assertEqual(len(re.findall(r'<th scope="col" class="num mcol" aria-sort="none" data-csv-label="', self.table)), len(names))
        self.assertEqual(re.findall(r'<th scope="colgroup" colspan="(\d+)" class="grp">([^<]*)</th>', self.table), [("3", "200 KB file"), ("3", "50 KB file")])   # the file size is a group heading, not repeated in each column
        self.assertEqual(re.findall(r'<span class="mw">([^<]*?) <i', self.table), ["CPU time", "Time", "Peak memory, all processes", "CPU time", "Time", "Peak memory, all processes"])
        self.assertNotIn("More metrics", self.page)   # the demo has six metrics for the workload: all of them are main

    def test_measured_harnesses_are_in_the_site_order_and_the_others_are_named_in_one_line_with_the_reason(self):
        cells = {c["key"]: c for c in self.data["cells"] if c["scenario"] == "overhead/print-write"}
        stats = cells["overhead-print-write.kb200_wall_ms"]["stats"]
        rows, col = self.rows(), self.column("kb200_wall_ms")
        self.assertEqual(list(rows), [h["slug"] for h in self.data["harnesses"] if h["id"] in stats])
        for slug, row in rows.items():
            h = next(h for h in self.data["harnesses"] if h["slug"] == slug)
            self.assertAlmostEqual(float(re.findall(r'data-csv-value="([^"]*)"', row)[1 + col]), stats[h["id"]]["median"])
            self.assertIn('href="#/cell/', row)
        missing = [h for h in self.data["harnesses"] if h["id"] not in stats]
        self.assertTrue(missing)
        line = re.search(r'<p class="notrun cant">.*?</p>', self.page, re.S).group(0)
        for h in missing:
            self.assertIn(">" + h["name"] + "</span>", line)
        self.assertIn("its tool set has no write tool", htmlmod.unescape(line))

    def test_a_time_of_one_second_or_more_is_in_seconds_and_a_shorter_one_in_ms(self):
        col = self.column("kb200_wall_ms")
        for row in self.rows().values():
            if 'data-csv-value="n/a"' in row:
                continue
            value = float(re.findall(r'data-csv-value="([^"]*)"', row)[1 + col])
            text = plain(re.findall(r'<span class="cv">(.*?)</span>', row)[col])
            self.assertTrue(text.endswith(" s") if value >= 1000 else text.endswith(" ms"), text)

    def test_the_table_has_a_csv(self):
        self.assertEqual(self.page.count('data-csv="all-large-writes"'), 1)
        self.assertTrue(all('data-csv-group="all-large-writes"' in t["text"] for t in self.tables))   # the main table and the More metrics tables are one CSV

    def test_a_run_without_the_large_write_lists_large_writes_and_many_agents_as_not_run_yet_and_draws_no_number_for_them(self):
        out = built(demo_raw(rounds=4), faith=False)
        views = render_all(out)
        for sid in ("large-writes", "agent-swarming"):
            self.assertIn(f'<a class="card tile off" href="#/r/{sid}">', views["#/"])
            page = views[f"#/r/{sid}"]
            self.assertIn("Not run yet", page)
            self.assertNotIn("<table", page)
            self.assertNotIn('<svg class="chart"', page)


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class NoScale(unittest.TestCase):
    def test_a_site_without_a_scale_run_has_a_many_agents_section_that_says_not_run_yet_and_the_old_address_leads_to_it(self):
        out = built(demo_raw(rounds=4), faith=False)
        views = render_all(out)
        self.assertIsNone(site_data(out)["scale"])
        page = views["#/r/agent-swarming"]
        self.assertIn("Not run yet", page)
        self.assertIn("What it measures", page)
        self.assertNotIn("<table", page)
        self.assertNotIn('id="envelope"', page)
        self.assertEqual(app(out, "console.log(JSON.stringify(A.render(D,'#/scale',{width:1200}).redirect))"), "#/r/agent-swarming")
        self.assertEqual(app(out, "console.log(JSON.stringify(A.render(D,'#/swarm/x/rpc/pi-node/4',{width:1200}).html.indexOf('Not found')>=0))"), True)


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Envelopes(unittest.TestCase):
    def test_two_envelopes_have_one_tile_and_a_choice_on_the_page(self):
        out = built(with_swarms(demo_raw(rounds=4), second=True), faith=False)
        views = render_all(out)
        data = site_data(out)
        self.assertEqual([e["id"] for e in data["scale"]["envelopes"]], ["2g-4c", "4g-8c"])
        tiles = re.findall(r'<a class="card tile" href="#/r/agent-swarming">.*?</a>', views["#/"], re.S)
        self.assertEqual(len(tiles), 1)
        self.assertIn("2 GiB", plain(tiles[0]))   # the first envelope
        self.assertNotIn("4 GiB", plain(tiles[0]))
        self.assertIn('data-href="#/r/agent-swarming?e=2g-4c"', views["#/r/agent-swarming"])
        self.assertIn('data-href="#/r/agent-swarming?e=4g-8c"', views["#/r/agent-swarming"])
        second = views["#/r/agent-swarming?e=4g-8c"]
        self.assertIn("4 GiB", main_card(second))   # the card is of the envelope that was chosen
        self.assertIn('id="envelope"', second)
        self.assertEqual(len(re.findall(r'aria-pressed="true">4 GiB of memory, 8 cores', second)), 1)
        self.assertEqual(len(re.findall(r'aria-pressed="true">2 GiB of memory, 4 cores', views["#/r/agent-swarming"])), 1)   # no choice in the URL: the first envelope
        self.assertEqual(len(re.findall(r'aria-pressed="true">2 GiB of memory, 4 cores', views["#/r/agent-swarming?e=2g-4c"])), 1)
        self.assertEqual(len(re.findall(r'id="envelope"', second)), 1)


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class AgentsPage(unittest.TestCase):
    """The Agent swarming page is a section page like the others: the same parts in the same order, one choice in the URL, and no control that does nothing."""

    @classmethod
    def setUpClass(cls):
        cls.raw = with_swarms(with_write(demo_raw(rounds=4)))
        cls.out = built(cls.raw, faith=False)
        cls.views = render_all(cls.out, AGENT_ROUTES + DEFAULT_VIEW + [agent_route("rpc", "fit", "line"), AGENTS + "?m=bogus&view=bogus", "#/r/start-up"])
        cls.page = cls.views[AGENTS]
        cls.data = site_data(cls.out)

    def pressed(self, page):
        return re.findall(r'class="mcell" aria-pressed="true" aria-label="([^"]*)"', page)

    def view(self, page):
        bar = re.search(r'<div class="viewbar">.*?</div></div>', page, re.S).group(0)
        return re.findall(r'<button type="button" data-href="[^"]*" aria-pressed="(true|false)">([^<]+)</button>', bar)

    def test_it_has_the_parts_of_a_section_page_in_the_same_order(self):
        page = self.page
        order = [page.index(x) for x in ('<div class="ctlbar">', '<div class="pagehead">', 'class="card mxcard"', '<div class="viewbar">', 'id="agents-main"', 'id="all-agent-swarming"')]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(page.count('id="agents-main"'), 1)   # one primary chart card
        self.assertEqual(len(re.findall(r'<section class="card small" id="[^"]*"', page)), 1)
        self.assertEqual(page.count('<div class="viewbar">'), 1)
        self.assertEqual(page.count('class="card mxcard"'), 1)
        start = self.views["#/r/start-up"]
        for part in ('<div class="pagehead">', '<div class="ctlbar">', 'class="card mxcard"', '<div class="viewbar">', '<a class="how" href="#/method">How it works</a>'):
            self.assertIn(part, start)
            self.assertIn(part, page)
        card = main_card(page)
        self.assertRegex(card, r'<h2>RPC agents: Agents that fit</h2><p class="sub">[^<]+</p>')
        self.assertIn('<a class="info"', card)
        self.assertEqual(page.count("<h1>"), 1)

    def test_the_table_of_every_metric_is_open_and_every_value_links_to_its_derivation(self):
        self.assertNotRegex(self.page, r"<details[^>]*>\s*<summary>All metrics")
        card = self.page[self.page.index('<section class="card" id="all-agent-swarming"'):]   # the card holds a section for each workload
        n = len(re.findall(r'<th scope="col" class="num mcol"', card))
        self.assertIn(f"All metrics in this section ({n})", card)   # a column for each metric of each workload that has a value
        self.assertEqual(card.count('data-csv="all-agent-swarming"'), 1)   # one Download CSV
        tables = re.findall(r'<table class="data grid" id="t-all-agent-swarming-([^"]+)" data-csv-group="all-agent-swarming" data-csv-workload="([^"]*)"[^>]*>(.*?)</table>', card, re.S)
        self.assertEqual([t[0] for t in tables], list(KINDS4))   # one table for each workload
        linked = 0
        for _, _, table in tables:
            self.assertLessEqual(len(re.findall(r'<th scope="col" class="num mcol"', table)), 6)
            for row in re.findall(r"<tr class=\"h-.*?</tr>", table, re.S):
                for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S):
                    if re.search(r"\d", plain(c)) and "Not even one agent finished" not in c:   # a limit of zero has no probe that finished to open
                        self.assertRegex(c, r'href="#/swarm/[^"]+"')
                        linked += 1
        self.assertGreater(linked, 30)
        self.assertNotIn('id="fit-', self.page)   # the separate tables and charts are gone: the picker and this table reach their data
        self.assertNotIn('class="smalls"', self.page)

    def test_the_picker_has_a_row_for_each_workload_and_a_column_for_each_metric_under_its_kind(self):
        matrix = re.search(r'<table class="mtx">.*?</table>', self.page, re.S).group(0)
        rows = re.findall(r'<th scope="row" class="rh">([^<]*)</th>', matrix)
        self.assertEqual(rows, [self.data["scale"]["envelopes"][0]["kinds"][k]["title"] for k in ("rpc", "print", "rpc-ext10", "print-ext10")])
        self.assertEqual(re.findall(r'<th scope="colgroup" colspan="\d+" class="kind">([^<]*)</th>', matrix), ["Capacity", "CPU", "Time", "Memory"])
        self.assertEqual(len(re.findall(r'class="mcell"', matrix)), 24)
        self.assertEqual(self.pressed(self.page), ["RPC agents: Agents that fit"])   # one cell chosen, by default the agents that fit in RPC mode
        self.assertNotIn('class="mxrow"', matrix)   # one metric at a time: no whole row or column to choose
        self.assertNotIn('class="lnk"', matrix)

    def test_the_choice_is_in_the_url_and_comes_back_from_it(self):
        for kind in KINDS4:
            for metric in ("fit",) + PER_N:
                want = f"{self.data['scale']['envelopes'][0]['kinds'][kind]['title']}: "
                got = self.pressed(self.views[agent_route(kind, metric)])
                self.assertEqual(len(got), 1, (kind, metric))
                self.assertTrue(got[0].startswith(want), (got, want))
                self.assertIn(f'<h2>{got[0]}</h2>', main_card(self.views[agent_route(kind, metric)]).replace("&amp;", "&"))
        # every cell links to the address that chooses it; the default is no parameter
        hrefs = dict(zip(re.findall(r'aria-label="([^"]*)" data-href="[^"]*" data-tip', self.page), re.findall(r'class="mcell" aria-pressed="\w+" aria-label="[^"]*" data-href="([^"]*)"', self.page)))
        self.assertEqual(hrefs["RPC agents: Agents that fit"], "#/r/agent-swarming")
        self.assertEqual(hrefs["Print-mode agents: Memory per agent"], "#/r/agent-swarming?m=print.mem_per_agent_mib")
        self.assertEqual(self.views[AGENTS + "?m=bogus&view=bogus"].count('aria-pressed="true" aria-label="RPC agents: Agents that fit"'), 1)   # a choice that is not in the data is the default
        self.assertEqual(app(self.out, "console.log(JSON.stringify(A.parse('#/r/agent-swarming?m=print.turns_per_s&view=bars').params))"), {"m": ["print.turns_per_s"], "view": "bars"})

    def test_the_view_control_offers_only_the_views_that_work_for_the_chosen_metric(self):
        self.assertEqual(self.view(self.page), [("true", "Bars")])   # the agents that fit are bars with their ranges
        self.assertIn('class="bars', main_card(self.page))
        self.assertEqual(self.view(self.views[AGENTS + "?m=rpc.mem_per_agent_mib"]), [("true", "Bars"), ("false", "Line")])   # Bars is the default where it is offered
        self.assertEqual(self.view(self.views[agent_route("rpc", "mem_per_agent_mib")]), [("false", "Bars"), ("true", "Line")])   # and view=line in the URL wins
        line, bars = self.views[agent_route("rpc", "turns_per_s")], self.views[AGENTS + "?m=rpc.turns_per_s"]
        self.assertIn('<svg class="chart"', main_card(line))
        self.assertIn('class="bars', main_card(bars))
        self.assertNotIn("<svg", main_card(bars))
        self.assertEqual(self.view(bars), [("true", "Bars"), ("false", "Line")])
        self.assertIn('data-href="#/r/agent-swarming?m=rpc.turns_per_s"', line)   # Bars is no parameter
        self.assertIn('data-href="#/r/agent-swarming?m=rpc.turns_per_s&amp;view=line"', bars)
        rows = re.findall(r'<div class="brow ', main_card(bars))
        self.assertGreaterEqual(len(rows), 3)
        self.assertIn("the most that every harness here finished", plain(main_card(bars)))
        # a view that does not work for the metric is not drawn: the agents that fit are not a line
        self.assertNotIn("<svg", main_card(self.views[agent_route("rpc", "fit", "line")]))
        self.assertEqual(self.view(self.views[agent_route("rpc", "fit", "line")]), [("true", "Bars")])

    def test_it_has_no_control_that_does_nothing(self):
        bar = re.search(r'<div class="ctlbar">.*?</div></div>', self.page, re.S).group(0)
        self.assertEqual(len(re.findall(r'class="chip ', bar)), len(self.data["harnesses"]))   # the harness chips are the one control of the bar
        self.assertNotIn(">Values<", bar)
        self.assertNotIn(">Ratio<", bar)
        self.assertNotIn("Baseline", bar)
        self.assertNotIn("Wire API", bar)
        start = re.search(r'<div class="ctlbar">.*?</div></div>', self.views["#/r/start-up"], re.S).group(0)
        self.assertIn(">Ratio<", start)   # the other sections keep theirs

    def test_the_harness_chips_choose_the_harnesses_of_the_chart_and_of_the_table(self):
        page = app(self.out, "console.log(JSON.stringify([\"#/r/agent-swarming?h=pi-node\",\"#/r/agent-swarming?h=pi-node&m=rpc.mem_per_agent_mib&view=line\"].map(r=>A.render(D,r,{width:1200}).html)))")
        fit, line = main_card(page[0]), main_card(page[1])
        self.assertEqual(re.findall(r'href="#/harness/([^"]+)"', fit), ["pi-node"])
        self.assertEqual(len(re.findall(r'<text class="elabel"', line)), 1)
        tables = re.findall(r'<table class="data grid" id="t-all-agent-swarming-.*?</table>', page[0], re.S)
        self.assertTrue(tables)
        self.assertEqual({h for t in tables for h in re.findall(r'href="#/harness/([^"]+)"', t)}, {"pi-node"})
        self.assertNotIn("Not in this test: pi-node", page[0])

    def test_provisional_is_said_once_by_a_badge_in_the_page_head_and_nowhere_else_on_the_page(self):
        self.assertTrue(any(r.get("provisional") for r in self.data["runs"]))   # the demo swarms were run on a loaded host
        for route in [AGENTS] + AGENT_ROUTES:
            page = self.views[route]
            self.assertEqual(len(re.findall(r'<span class="prov"', page)), 1, route)
            self.assertIn('<span class="prov"', re.search(r'<div class="pagehead">.*?</div>', page, re.S).group(0), route)
            for table in re.findall(r'<table class="data grid" id="t-all-agent-swarming-.*?</table>', page, re.S):
                self.assertNotIn('class="prov"', table, route)


class Model(unittest.TestCase):
    def test_a_stop_only_the_skipped_list_names_still_gives_the_stop(self):
        samples, skipped = ladder("pi-node", "rpc", per_agent_mib=190, cap=64)
        samples = [s for s in samples if s["agents"] < 32]   # the stopping rung has no sample
        data = scalelib.build([("run", {"samples": samples})], skipped, ["pi-node"])
        a = data["envelopes"][0]["kinds"]["rpc"]["arms"]["pi-node"]
        self.assertEqual((a["max_ok"], a["stop"]["n"], a["stop"]["cause"]), (16, 32, "oom"))

    def test_two_measured_rounds_with_different_limits_give_the_lower_one_and_the_range(self):
        samples = search("pi-node", "rpc", per_agent_mib=190, rounds=2)
        limits = [s["agents_limit"] for s in samples if not s["warmup"]]
        self.assertEqual(len(set(limits)), 2)
        a = scalelib.build([("run", {"samples": samples[::-1]})], [], ["pi-node"])["envelopes"][0]["kinds"]["rpc"]["arms"]["pi-node"]   # in any order of the samples
        self.assertEqual((a["limit"], a["limits"], a["range"]), (min(limits), limits, [min(limits), max(limits)]))
        self.assertEqual(a["limit"], statistics.median_low(limits))
        low = next(s for s in samples if s["agents_limit"] == min(limits))
        self.assertEqual((a["first_failure"], a["stop"]["n"], a["cause"], a["failure"]), (low["first_failure"], low["first_failure"], low["limit_cause"], low["limit_failure"]))   # the median round's

    def test_the_median_of_an_odd_number_of_rounds_is_the_middle_one_and_the_warm_up_does_not_count(self):
        samples = search("pi-node", "rpc", per_agent_mib=190, rounds=3)
        for s, v in zip([s for s in samples if not s["warmup"]], (30, 10, 20)):
            s["agents_limit"] = v
        next(s for s in samples if s["warmup"])["agents_limit"] = 999
        a = scalelib.build([("run", {"samples": samples})], [], ["pi-node"])["envelopes"][0]["kinds"]["rpc"]["arms"]["pi-node"]
        self.assertEqual((a["limit"], a["limits"], a["range"]), (20, [30, 10, 20], [10, 30]))

    def test_the_probes_of_the_measured_rounds_are_pooled_for_each_n_and_the_warm_up_probes_are_left_out(self):
        samples = search("pi-node", "rpc", per_agent_mib=190, rounds=4)
        a = scalelib.build([("run", {"samples": samples})], [], ["pi-node"])["envelopes"][0]["kinds"]["rpc"]["arms"]["pi-node"]
        measured = [s for s in samples if not s["warmup"]]
        for r in a["rungs"]:
            tried = [s["round"] for s in measured if any(p["n"] == r["n"] for p in s["probes"])]
            self.assertEqual([x["round"] for x in r["rounds"]], tried, r["n"])
            self.assertEqual(r["status"] == "ok", all(p["ok"] for s in measured for p in s["probes"] if p["n"] == r["n"]), r["n"])
        self.assertEqual(sorted(r["n"] for r in a["rungs"]), sorted({p["n"] for s in measured for p in s["probes"]}))
        only_warmup = {p["n"] for s in samples if s["warmup"] for p in s["probes"]} - {p["n"] for s in measured for p in s["probes"]}
        self.assertTrue(only_warmup.isdisjoint(r["n"] for r in a["rungs"]))

    def test_a_sample_with_the_contract_fields_only_gives_the_limit_and_where_it_stopped(self):
        probes = [{"n": 1, "phase": "double", "ok": True, "agents_ok": 1}, {"n": 2, "phase": "double", "ok": False, "agents_ok": 1, "failure": "timed out after 300 s", "stop_cause": "timeout", "oom_kills": 0}]
        sample = {"arm": "pi-node", "scenario": "scale/print-limit", "api": None, "round": 1, "warmup": False, "swarm": {"memory_mib": 1024, "cpus": [1, 2]}, "agents_limit": 1, "limit_capped": False,
                  "limit_cap": 8192, "limit_resolution": 1, "first_failure": 2, "probe_count": 2, "extensions": 0, "probes": probes}
        a = scalelib.build([("run", {"samples": [sample]})], [], ["pi-node"])["envelopes"][0]["kinds"]["print"]["arms"]["pi-node"]
        self.assertEqual((a["exact"], a["limit"], a["stop"]["n"], a["stop"]["cause"], a["stop"]["failure"], a["capped"], a["cap"]), (True, 1, 2, "timeout", "timed out after 300 s", False, 8192))
        self.assertEqual([(r["n"], r["status"]) for r in a["rungs"]], [(1, "ok"), (2, "stopped")])

    def test_a_coarser_search_says_the_limit_is_between_its_last_complete_probe_and_the_first_failure(self):
        samples = search("pi-node", "rpc", per_agent_mib=28, resolution=8, rounds=1)
        a = scalelib.build([("run", {"samples": samples})], [], ["pi-node"])["envelopes"][0]["kinds"]["rpc"]["arms"]["pi-node"]
        self.assertEqual(a["resolution"], 8)
        self.assertEqual(a["between"], [a["limit"], a["first_failure"] - 1])
        self.assertLessEqual(a["first_failure"] - a["limit"], 8)

    def test_the_ten_extension_kinds_exist_only_when_the_run_has_them(self):
        plain_run = scalelib.build([("run", {"samples": search("pi-node", "rpc", per_agent_mib=190, rounds=1)})], [], ["pi-node"])["envelopes"][0]["kinds"]
        self.assertEqual(sorted(plain_run), ["print", "rpc"])
        samples = search("pi-node", "rpc", per_agent_mib=190, rounds=1) + search("pi-node", "rpc", ext=True, per_agent_mib=230, rounds=1)
        skipped = [{"arm": "demo-gamma", "scenario": "scale/agents-ext10", "api": None, "reason": "it does not load Pi extensions"}]
        kinds = scalelib.build([("run", {"samples": samples})], skipped, ["pi-node", "demo-gamma"])["envelopes"][0]["kinds"]
        self.assertEqual(sorted(kinds), ["print", "rpc", "rpc-ext10"])
        self.assertEqual(kinds["rpc-ext10"]["arms"]["demo-gamma"], {"cannot": "it does not load Pi extensions"})
        self.assertLess(kinds["rpc-ext10"]["arms"]["pi-node"]["limit"], kinds["rpc"]["arms"]["pi-node"]["limit"])
        self.assertNotIn("print-ext10", kinds)

    def test_the_cause_is_the_samples_own_or_read_from_its_words(self):
        self.assertEqual(scalelib.cause_of("x", "pids"), "pids")
        self.assertEqual(scalelib.cause_of("the kernel killed 3 agents: out of memory"), "oom")
        self.assertEqual(scalelib.cause_of("timed out after 300 s"), "timeout")
        self.assertEqual(scalelib.cause_of("fork failed: pids limit"), "pids")
        self.assertEqual(scalelib.cause_of("something else"), "error")

    def test_no_swarm_sample_gives_no_scale_data(self):
        self.assertIsNone(scalelib.build([("run", {"samples": [{"arm": "pi-node", "scenario": "overhead/print"}]})], [], ["pi-node"]))


if __name__ == "__main__":
    unittest.main()
