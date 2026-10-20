# SPDX-License-Identifier: Apache-2.0
"""The durable family in the report and on the site, built from the synthetic run of tests/durable_demo.py (invented numbers, the two real arm ids): the cell variant rule (an environment is
its own cell), the metrics and margins of the family, the crash and resume grid, the report that is written, and the Durable section of the dashboard: the tile and its headline, the line charts,
the crash grid, the empty page, the Method block, and no word of ranking."""
import html as htmlmod
import json
import os
import re
import tempfile
import unittest

from buffon import stats
from buffon.dashboard import build as dashboard
from buffon.report import cellid, cells, durable as crash, metrics as metricslib, render
from buffon.runner import raw as rawlib
from buffon.stats import margins
from buffon.submit import reproduce
from tests import durable_demo as demo
from tests.banned_words import pattern
from tests.report_demo import demo_raw
from tests.test_dashboard import NODE, app, metric_tables, visible_text

ROUNDS = 5
HEADLINE = "durable-mixed-3500.warm_net_ms"
BANNED = pattern("claim")
COMPARATIVE = pattern("comparative")


def quick_raw(miniflare=False):
    raw = demo.durable_raw(rounds=ROUNDS, only=demo.QUICK)
    return demo.with_miniflare(raw) if miniflare else raw


class Variant(unittest.TestCase):
    def test_a_samples_variant_is_its_api_else_its_environment_unless_native(self):
        self.assertEqual(cells.variant({"api": "openai-completions", "env": "miniflare"}), "openai-completions")
        self.assertEqual(cells.variant({"api": None, "env": "miniflare"}), "miniflare")
        self.assertIsNone(cells.variant({"api": None, "env": "native"}))
        self.assertIsNone(cells.variant({"env": "native"}))
        self.assertIsNone(cells.variant({}))

    def test_the_cell_id_of_an_environment_cell_parses_back_and_its_rerun_plan_finds_the_samples(self):
        cid = cellid.make("run-1", "durable/mixed-3500", "miniflare", "warm_turn_ms")
        self.assertEqual(cid, "run-1::durable/mixed-3500@miniflare#warm_turn_ms")
        self.assertEqual(cellid.parse(cid), ("run-1", "durable/mixed-3500", "miniflare", "warm_turn_ms"))
        native = cellid.make("run-1", "durable/mixed-3500", None, "warm_turn_ms")
        self.assertEqual(cellid.parse(native)[2], None)
        with tempfile.TemporaryDirectory() as tmp:
            run = demo.write_run(os.path.join(tmp, "run-1"), quick_raw(miniflare=True))
            workloads, apis, arms = reproduce.cell_plan(run, "durable/mixed-3500", "miniflare", "warm_turn_ms")
            self.assertEqual((workloads, apis, arms), (["durable/mixed-3500"], None, ["pi-durable"]), "an environment is not a wire API: the run's own params carry it")
            workloads, apis, arms = reproduce.cell_plan(run, "durable/mixed-3500", None, "warm_turn_ms")
            self.assertEqual(arms, ["pi-durable", "pi-durable-main", "pig-durable"])


class Cells(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = cells.build([quick_raw(miniflare=True)], seed=1)
        cls.by = {(c.scenario, c.api, c.metric): c for c in cls.data["cells"]}

    def test_the_reference_is_the_one_the_run_names_and_native_cells_keep_api_none_and_say_native(self):
        self.assertEqual(self.data["reference"], "pi-durable")
        c = self.by[("durable/mixed-3500", None, "warm_net_ms")]
        self.assertEqual((c.api, c.env), (None, "native"))
        self.assertIn("pig-durable", c.comparisons)

    def test_an_environment_makes_its_own_cell_and_never_joins_the_native_one(self):
        native, mini = self.by[("durable/mixed-3500", None, "warm_turn_ms")], self.by[("durable/mixed-3500", "miniflare", "warm_turn_ms")]
        self.assertEqual(mini.env, "miniflare")
        self.assertEqual(set(mini.values), {"pi-durable", "pi-durable-b"}, "only the arm that ran in Miniflare has values there")
        self.assertEqual(len(native.values["pi-durable"]), ROUNDS)
        self.assertEqual(len(mini.values["pi-durable"]), ROUNDS)
        self.assertGreater(stats_median(mini.values["pi-durable"]), 1.5 * stats_median(native.values["pi-durable"]))
        self.assertNotIn(("durable/mixed-3500", "miniflare", "sql_commits_per_turn"), {(c.scenario, c.api, c.metric) for c in self.data["cells"] if c.scenario != "durable/mixed-3500"})
        self.assertIn(("durable/mixed-3500", "miniflare", "rows_written_per_turn"), self.by, "the platform's own counters exist only there")
        self.assertNotIn(("durable/mixed-3500", None, "rows_written_per_turn"), self.by, "a metric the environment cannot produce is absent, never zero")

    def test_the_crash_workload_makes_no_cell(self):
        self.assertFalse([c for c in self.data["cells"] if c.scenario.startswith("durable/crash-")])
        self.assertTrue(cells.is_special("durable/crash-1000") and cells.is_special("reliability/x") and not cells.is_special("durable/mixed-3500"))

    def test_descriptors_are_not_scored_and_every_cost_the_family_reports_is(self):
        metrics = {c.metric for c in self.data["cells"]}
        for name in ("fixture_bytes", "fixture_seed", "fixture_turns", "window_tokens", "measured_turns", "turns", "conversations", "model_ms_per_turn", "stmts_replayed", "k", "commits_total", "compaction_failures"):
            self.assertFalse(cells.scored(name), name)
            self.assertNotIn(name, metrics, name)
        scored = ("warm_turn_ms", "warm_net_ms", "cold_ms", "proc_start_ms", "open_ms", "first_turn_ms", "ready_to_answer_ms", "ttfr_ms", "cpu_ms", "instructions", "cycles", "warm_instructions", "warm_cycles", "warm_cpu_ms",
                  "sql_stmts_per_turn", "sql_commits_per_turn", "rows_returned_per_turn", "bytes_returned_per_turn", "wchar_bytes_per_turn", "rchar_bytes_per_turn", "rows_read_per_turn", "rows_written_per_turn",
                  "store_bytes", "store_bytes_per_turn", "peak_rss_mib", "ready_rss_mib", "end_rss_mib", "pss_mib", "mem_per_conv_mib", "replay_ms_per_turn", "build_ms", "early_turn_ms", "late_turn_ms", "first_delta_ms")
        for name in scored:
            self.assertTrue(cells.scored(name), name)
        self.assertIn("warm_net_ms", metrics)
        self.assertIn("mem_per_conv_mib", metrics)

    def test_each_metric_has_its_kind_and_its_words(self):
        self.assertEqual(metricslib.describe("sql_stmts_per_turn"), (metricslib.COUNT, "statements per turn"))
        self.assertEqual(metricslib.describe("sql_commits_per_turn"), (metricslib.COUNT, "commits per turn"))
        self.assertEqual(metricslib.describe("rows_returned_per_turn"), (metricslib.COUNT, "rows per turn"))
        self.assertEqual(metricslib.describe("store_bytes"), (metricslib.SIZE, "bytes"))
        self.assertEqual(metricslib.describe("store_bytes_per_turn"), (metricslib.SIZE, "bytes per turn"))
        self.assertEqual(metricslib.describe("wchar_bytes_per_turn"), (metricslib.SIZE, "bytes per turn"))
        self.assertEqual(metricslib.describe("bytes_returned_per_turn"), (metricslib.SIZE, "bytes per turn"))
        self.assertEqual(metricslib.describe("mem_per_conv_mib"), (metricslib.MEMORY, "MiB per conversation"))
        self.assertEqual(metricslib.describe("warm_net_ms")[0], metricslib.WALL)
        self.assertEqual(metricslib.describe("warm_instructions")[0], metricslib.CPU)

    def test_the_margins_are_the_design_s_time_5_percent_memory_5_percent_or_2_mib_and_four_exact(self):
        for name in ("sql_commits_per_turn", "rows_written_per_turn", "store_bytes", "store_bytes_per_turn"):
            self.assertEqual(margins.margin_for(name, 100.0), 0.0, name)
        for name in ("warm_net_ms", "cold_ms", "warm_instructions", "warm_cpu_ms"):
            self.assertEqual(margins.margin_for(name, 100.0), 0.05, name)
        self.assertEqual(margins.margin_for("end_rss_mib", 100.0), 0.05)
        self.assertAlmostEqual(margins.margin_for("end_rss_mib", 10.0), 0.2)   # 2 MiB of a 10 MiB reference
        self.assertIsNone(margins.margin_for("sql_stmts_per_turn", 100.0))
        c = self.by[("durable/mixed-3500", None, "sql_commits_per_turn")].comparisons["pig-durable"]
        self.assertTrue(c.equivalence["equivalent"] and c.equivalence["margin"] == 0.0, "the same 77 commits in every round are equivalent by construction")
        self.assertEqual(self.by[("durable/mixed-3500", None, "store_bytes")].comparisons["pig-durable"].ratio, 1.0)


def stats_median(values):
    xs = sorted(values.values())
    return xs[len(xs) // 2]


class CrashGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = quick_raw()
        cls.samples = cls.raw["samples"]
        cls.grid = crash.verdicts(cls.samples, "pi-durable")
        cls.possible = sorted(set(demo.ORDERS) - set(demo.NOT_POSSIBLE))

    def test_one_grid_for_the_crash_workload_with_the_reference_order_first(self):
        self.assertEqual([g["scenario"] for g in self.grid], ["durable/crash-50"])
        g = self.grid[0]
        self.assertEqual([o["order"] for o in g["orders"]][0], "pi-durable>pi-durable")
        self.assertTrue(g["orders"][0]["control"])
        self.assertEqual(sorted(o["order"] for o in g["orders"]), self.possible)
        self.assertEqual(g["ks"], demo.CRASH_KS)
        self.assertEqual(g["commits_total"][demo.CRASH_KS[0]], demo.CRASH_COMMITS)

    def test_a_point_passes_when_it_resumed_held_its_invariants_and_equals_the_oracle_and_the_rate_has_a_wilson_interval(self):
        by = {o["order"]: o for o in self.grid[0]["orders"]}
        n = len(demo.CRASH_KS)
        for order in self.possible:
            if order != "pig-durable>pig-durable":
                self.assertEqual((by[order]["passed"], by[order]["of"]), (n, n), order)
        bad = by["pig-durable>pig-durable"]
        self.assertEqual((bad["passed"], bad["of"]), (n - 2, n))
        self.assertEqual([k for k, p in bad["points"].items() if not p["ok"]], list(demo.FAILING_KS))
        self.assertIn("the outcome differs from pi-durable>pi-durable's", bad["points"][demo.FAILING_KS[0]]["reasons"])
        self.assertEqual(bad["ci"], list(stats.wilson(n - 2, n)))
        self.assertTrue(by["pi-durable>pi-durable"]["ci"][0] > 0.8 and by["pi-durable>pi-durable"]["ci"][1] > 0.99)

    def test_an_order_the_gate_found_impossible_is_listed_with_its_reason_and_is_never_a_failure(self):
        found = crash.impossible([self.raw])
        self.assertEqual(found, demo.NOT_POSSIBLE)
        grid = crash.verdicts(self.samples, "pi-durable", found)[0]
        by = {o["order"]: o for o in grid["orders"]}
        for order, why in demo.NOT_POSSIBLE.items():
            self.assertEqual((by[order]["impossible"], by[order]["of"], by[order]["passed"], by[order]["ci"]), (why, 0, 0, None))
        self.assertEqual(len(grid["orders"]), len(demo.ORDERS))
        self.assertEqual([o["order"] for o in grid["orders"] if o["impossible"]], sorted(demo.NOT_POSSIBLE), "listed after the orders that ran")
        self.assertEqual(crash.impossible([{"run": {"durable": {"cross_open": {"x": {"a>b": {"ok": False, "messages": 3}, "c>d": {"ok": True}}}}}}]), {}, "a store read differently is a difference, not an order that cannot run")

    def test_a_failed_resume_a_duplicated_submission_and_a_broken_invariant_each_fail_the_point(self):
        k = demo.CRASH_KS[3]
        s = [dict(x) for x in self.samples if x["scenario"] == "durable/crash-50" and x["k"] == k]
        for field, value, text in (("resume_ok", False, "did not resume"), ("duplicated_submission", True, "duplicated"), ("invariant_failures", "ledger: effect twice", "effect twice"), ("failure", "adapter exited", "failed")):
            mutated = [dict(x, **({field: value} if x["order"] == "pi-durable>pig-durable" else {})) for x in s]
            by = {o["order"]: o for o in crash.verdicts(mutated, "pi-durable")[0]["orders"]}
            point = by["pi-durable>pig-durable"]["points"][k]
            self.assertFalse(point["ok"], field)
            self.assertTrue(any(text in r for r in point["reasons"]), (field, point["reasons"]))
            self.assertTrue(by["pi-durable>pi-durable"]["points"][k]["ok"])

    def test_copies_and_warm_up_samples_are_not_points(self):
        extra = [dict(x, arm=x["arm"] + "-b", twin_of=x["arm"]) for x in self.samples if x["scenario"] == "durable/crash-50"][:5] + [dict(x, warmup=True) for x in self.samples if x["scenario"] == "durable/crash-50"][:5]
        grid = crash.verdicts(self.samples + extra, "pi-durable")
        self.assertEqual([o["of"] for o in grid[0]["orders"]], [o["of"] for o in self.grid[0]["orders"]])


class Written(unittest.TestCase):
    """What `buffon report` writes for a durable run: the crash section, the env marked, and nothing that crashes the grade."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        run = demo.write_run(os.path.join(cls.tmp, "run"), quick_raw(miniflare=True))
        cls.out = os.path.join(cls.tmp, "out")
        render.render([run], cls.out)
        with open(os.path.join(cls.out, "report.md")) as f:
            cls.md = f.read()
        with open(os.path.join(cls.out, "report.json")) as f:
            cls.json = json.load(f)

    def test_the_report_has_a_crash_section_and_marks_the_environment_of_every_cell(self):
        self.assertIn("## Durable crash and resume", self.md)
        n = len(demo.CRASH_KS)
        self.assertIn(f"| pig-durable>pig-durable | {n} | {n - 2} |", self.md)
        self.assertIn(f"- pig-durable>pig-durable at k={demo.FAILING_KS[0]}:", self.md)
        self.assertIn("| pig-durable>pi-durable | not possible: pi-durable opens schema 1 stores and pig-durable writes schema 2 |", self.md)
        self.assertIn("## Durable notes", self.md)
        self.assertIn("`sql_pragma_stmts_per_turn` lists the pragma statements apart", self.md)
        self.assertRegex(self.md, r"\| durable/mixed-3500 \| native \| warm_net_ms \|")
        self.assertRegex(self.md, r"\| durable/mixed-3500 \| miniflare \| warm_turn_ms \|")
        by = {(c["scenario"], c["api"], c["metric"]): c for c in self.json["cells"]}
        self.assertEqual(by[("durable/mixed-3500", None, "warm_net_ms")]["env"], "native")
        self.assertEqual(by[("durable/mixed-3500", "miniflare", "warm_turn_ms")]["env"], "miniflare")
        self.assertTrue(by[("durable/mixed-3500", "miniflare", "warm_turn_ms")]["id"].endswith("@miniflare#warm_turn_ms"))
        self.assertTrue(by[("durable/mixed-3500", None, "warm_net_ms")]["id"].endswith("@-#warm_net_ms"))
        orders = {o["order"]: o for o in self.json["crash"][0]["orders"]}
        self.assertEqual(orders["pig-durable>pig-durable"]["passed"], len(demo.CRASH_KS) - 2)
        self.assertEqual(orders["pig-durable>pi-durable"]["impossible"], demo.NOT_POSSIBLE["pig-durable>pi-durable"])

    def test_no_durable_cell_enters_the_grade(self):
        cells_in_grade = [c for c in self.json["grade_inputs"]["cells"] if c["scenario"].startswith("durable/")]
        self.assertEqual(cells_in_grade, [])
        for fam in self.json["grade_inputs"]["failures"].values():
            self.assertNotIn("durable", fam)
        with open(os.path.join(self.out, "summary.csv")) as f:
            header = f.readline().strip().split(",")
        self.assertEqual(header[-2:], ["env", "label"])

    def test_the_report_names_no_word_of_ranking_in_the_durable_parts(self):
        durable = self.md[self.md.index("## Durable crash and resume"):]
        self.assertFalse(BANNED.search(durable), BANNED.search(durable))

    def test_the_raw_format_accepts_the_nested_fields_of_a_durable_sample_and_refuses_what_is_not_json(self):
        s = quick_raw()["samples"][0]
        for key in rawlib.DURABLE_NESTED:
            self.assertIn(key, s)
        rawlib.check_sample(s)
        for key, bad in (("runtime_settings", {"x": object()}), ("store_tables", {"entries": float("nan")}), ("compaction_ids", [{1, 2}]), ("runtime_versions", {"node": {3, 4}})):
            with self.assertRaises(rawlib.RawError, msg=key):
                rawlib.check_sample(dict(s, **{key: bad}))
        with self.assertRaises(rawlib.RawError):
            rawlib.check_sample(dict(s, some_metric=[1, 2]))   # any other list is still not a metric


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        run = demo.write_run(os.path.join(cls.tmp, "run"), quick_raw(miniflare=True))
        cls.out = os.path.join(cls.tmp, "site")
        dashboard.build([run], cls.out)
        cls.pages = app(cls.out, "const o={};['#/r/durable','#/r/durable?view=line','#/r/durable?view=line&v=values','#/r/durable?api=miniflare','#/','#/method','#/r/durable?view=dots','#/r/durable?view=rounds'].forEach(r=>{o[r]=A.render(D,r,{width:1200}).html});console.log(JSON.stringify(o))")
        cls.data = app(cls.out, "console.log(JSON.stringify({d:D.durable,cells:D.cells.filter(c=>c.family==='durable').map(c=>({k:c.key,api:c.api_short,env:c.env,ev:c.env_variant,m:c.metric})),sections:D.runs.length}))")

    def test_the_durable_tile_has_the_headline_the_env_and_a_line_from_one_value_to_the_other_without_ranking_words(self):
        home = self.pages["#/"]
        tile = re.search(r'<a class="card tile" href="#/r/durable">.*?</a>', home, re.S).group(0)
        self.assertIn("Warm turn net of the floor", tile)
        self.assertIn('class="envchip"', tile)
        self.assertIn(">native<", tile)
        m = re.search(r'<p class="tile-r">from ([\d.,]+ ?m?s) \(([^)]+)\) to ([\d.,]+ ?m?s) \(([^)]+)\)</p>', tile)
        self.assertTrue(m, tile)
        self.assertTrue({m.group(2), m.group(4)} <= {"Pi Durable 1.3.0", "PiG Durable", "Pi Durable main"} and m.group(2) != m.group(4))
        self.assertFalse(BANNED.search(tile) or COMPARATIVE.search(tile))
        headline = app(self.out, "console.log(JSON.stringify(A.Index(D).sec.durable.head))")
        self.assertEqual(headline, HEADLINE)

    def test_the_section_says_the_attribution_and_is_provisional_and_names_native(self):
        page = self.pages["#/r/durable"]
        text = visible_text(page)
        self.assertIn("The compat lane is adapted from durable-bench (github.com/clavia-labs/durable-bench), used with permission.", text)
        self.assertIn('class="prov"', page)
        self.assertIn("Environment", self.pages["#/r/durable"], "the environment is chosen in the control bar when the run has more than one")

    def test_the_first_page_draws_the_headline_and_the_work_a_turn_costs_as_bars(self):
        page = self.pages["#/r/durable"]
        for title in ("Warm turn net of the floor", "Statements per turn", "Commits per turn", "Rows per turn"):
            self.assertRegex(page, r'<section class="card small"[^>]*>.*?<h2>[^<]*' + title, title)
        self.assertIn('class="bars', page)

    def test_the_line_charts_have_a_line_for_each_arm_and_series_and_a_log_x_axis(self):
        page = self.pages["#/r/durable?view=line&v=values"]
        for card in ("durable-warm", "durable-cold", "durable-store", "durable-memory"):
            self.assertIn(f'id="{card}"', page, card)
        warm = re.search(r'<section class="card" id="durable-warm".*?</section>', page, re.S).group(0)
        series = re.findall(r'<g class="series h-(\w+)( alt)?">(?:<polyline|<a)', warm)
        self.assertEqual(sorted((c, bool(alt)) for c, alt in series), sorted([(c, alt) for c in ("pi", "1", "2") for alt in (True, False)]), "compat (dashed) and mixed for each arm")
        for x in ("50", "1,000", "3,500", "10,000"):
            self.assertIn(f">{x}</text>", warm)
        self.assertIn("turns in the store", warm)
        self.assertIn("Pi Durable 1.3.0, compat", warm)
        self.assertIn("PiG Durable, mixed", warm)
        self.assertIn('class="envchip"', warm)
        memory = re.search(r'<section class="card" id="durable-memory".*?</section>', page, re.S).group(0)
        self.assertIn("Memory per live conversation, the slope of the line:", memory)
        ratio = self.pages["#/r/durable?view=line"]
        self.assertIn("log scale", re.search(r'<section class="card" id="durable-warm".*?</section>', ratio, re.S).group(0))

    def test_the_crash_grid_is_drawn_with_a_mark_for_each_point_and_the_rate_of_each_order(self):
        page = self.pages["#/r/durable"]
        grid = re.search(r'<section class="card" id="crash-durable-crash-50".*?</section>', page, re.S).group(0)
        n = len(demo.CRASH_KS)
        self.assertEqual(len(re.findall(r'<i class="cc ok" data-tip', grid)), 6 * n + (n - 2), "six orders passed every point, the seventh all but two")
        self.assertEqual(len(re.findall(r'<i class="cc bad" data-tip', grid)), 2)
        miniflare = self.pages["#/r/durable?api=miniflare"]
        self.assertNotIn("crash-durable-crash-50", miniflare, "the crash grid is native: it is not shown beside the Miniflare cells")
        for text in ("Pi Durable 1.3.0 then Pi Durable 1.3.0", "PiG Durable then PiG Durable", f"{n - 2} of {n}", f"{n} of {n}", "95% interval", "(the oracle)", "the outcome differs from pi-durable>pi-durable"):
            self.assertIn(text, htmlmod.unescape(grid))
        self.assertIn("Wilson", grid)
        self.assertIn("not possible: pi-durable opens schema 1 stores and pig-durable writes schema 2", grid)
        self.assertIn("PiG Durable then Pi Durable 1.3.0", grid, "an order that is not possible is listed with its reason, not as a failure")

    def test_an_environment_has_its_own_cells_and_its_own_page_and_is_never_mixed_with_the_native_one(self):
        d = self.data
        by = {(c["k"], c["api"]): c for c in d["cells"]}
        self.assertTrue(by[(HEADLINE.split(".")[0] + ".warm_turn_ms", "miniflare")]["ev"])
        self.assertFalse(by[(HEADLINE.split(".")[0] + ".warm_turn_ms", "-")]["ev"])
        self.assertEqual(d["d"]["envs"], ["miniflare", "native"])
        mini = self.pages["#/r/durable?api=miniflare"]
        self.assertIn(">miniflare<", mini)
        self.assertNotIn(">native<", re.sub(r'<option[^>]*>[^<]*</option>', "", mini).split('<div class="rbody">')[1], "the Miniflare page holds no native cell")
        self.assertIn("Durable Object storage", mini)

    def test_no_table_has_an_empty_row_and_a_workload_a_harness_cannot_run_names_the_reason(self):
        for route in ("#/r/durable", "#/r/durable?api=miniflare"):
            for t in metric_tables(self.pages[route], "all-durable"):
                for slug, row in t["rows"]:
                    self.assertTrue(any("na" not in c.split() for c, _ in row), (route, t["id"], slug))
        page = self.pages["#/r/durable"]
        self.assertIn("the Go port has no subagent ownership", page.replace("&#39;", "'"))

    def test_the_method_page_has_the_settings_the_gate_the_fixtures_and_the_floors(self):
        page = self.pages["#/method"]
        text = visible_text(page)
        for title in ("Runtime settings per arm", "Equivalence gate", "Fixtures", "Floors"):
            self.assertIn(title, text)
        self.assertIn("compaction_enabled = ", page)
        self.assertIn("background_tokens = the runtime&#39;s own default", page.replace("'", "&#39;"))
        self.assertIn("equivalence.json", text)
        self.assertIn(demo.digest_of("durable/mixed-3500")[:12], page)
        self.assertIn("Floor: host and adapter", page)
        self.assertTrue(os.path.exists(os.path.join(self.out, "runs", "run", "equivalence.json")), "the gate's own file is on the site")

    def test_no_view_of_the_section_has_a_word_of_ranking(self):
        for route, page in self.pages.items():
            if route in ("#/method", "#/"):
                continue
            text = visible_text(page)
            self.assertFalse(BANNED.search(text), (route, BANNED.search(text)))
            self.assertFalse(COMPARATIVE.search(text), (route, COMPARATIVE.search(text)))

    def test_every_view_of_the_section_renders(self):
        for route in ("#/r/durable?view=dots", "#/r/durable?view=rounds"):
            self.assertIn("<h1>Durable", self.pages[route])
            self.assertNotIn("Not found", self.pages[route])


@unittest.skipUnless(NODE, "the dashboard's views are JavaScript")
class Empty(unittest.TestCase):
    """A run with no durable sample: the section says there is none and how to produce one; it no longer says the family is designed and not built."""

    @classmethod
    def setUpClass(cls):
        from tests.test_dashboard import built
        cls.out = built(demo_raw(rounds=4), faith=False)
        cls.page = app(cls.out, "console.log(JSON.stringify(A.render(D,'#/r/durable',{width:1200}).html))")
        cls.home = app(cls.out, "console.log(JSON.stringify(A.render(D,'#/',{width:1200}).html))")

    def test_the_empty_page_says_no_durable_run_is_in_the_results_and_how_to_make_one(self):
        text = visible_text(self.page)
        self.assertIn("No durable run is in the results yet", text)
        self.assertNotIn("designed, not built", self.page.lower())
        self.assertNotIn("not built", self.page.lower())
        self.assertIn("python3 -m buffon run durable/", self.page)
        self.assertIn("--reference pi-durable", self.page)
        self.assertIn("campaigns/durable-native.toml", self.page)
        self.assertIn("Not run yet", self.page)
        self.assertNotIn("not built", self.home.lower())

    def test_the_attribution_belongs_to_a_page_with_durable_data(self):
        self.assertNotIn("durable-bench (github.com/clavia-labs/durable-bench)", self.page)


class DriverShapes(unittest.TestCase):
    """The records the real driver writes for an order that cannot run: a `cross_open` entry `{"ok": null, "possible": false, "why": ...}` and a `skipped[]` entry that names the order."""

    def test_both_records_make_the_order_not_possible_with_its_reason(self):
        why = "pi-durable's runtime opens storage schema version(s) [1]; the store pig-durable wrote is version 2"
        by_gate = {"run": {"durable": {"cross_open": {"mixed-1000": {"pig-durable>pi-durable": {"ok": None, "possible": False, "why": why}, "pi-durable>pig-durable": {"ok": True, "messages": 219}}}}}}
        self.assertEqual(crash.impossible([by_gate]), {"pig-durable>pi-durable": why})
        by_skip = {"run": {}, "skipped": [{"arm": "pi-durable", "scenario": "durable/crash-50", "api": None, "order": "pig-durable>pi-durable", "reason": "not possible: " + why},
                                         {"arm": "pig-durable", "scenario": "durable/subagent", "api": None, "reason": "it has no subagent"}]}
        self.assertEqual(crash.impossible([by_skip]), {"pig-durable>pi-durable": why})



if __name__ == "__main__":
    unittest.main()
