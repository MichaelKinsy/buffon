# SPDX-License-Identifier: Apache-2.0
"""`buffon up`: selection parsing, saved selections, the picker, the estimates, the machine profile, the listings, and the whole command end to end on stub harnesses in a fresh home."""
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from buffon import cli
from buffon import site as sitelib
from buffon import trust
from buffon.arms import manifest
from buffon.up import catalog, estimate, flow, listing, machine, picker, selection
from tests import stub_arms

PROBE = {"speed": 1.0, "spawn_ms": 20, "loop_ms": 80, "took_s": 0.3}


class Harnesses(unittest.TestCase):
    def test_short_names_globs_and_all(self):
        self.assertEqual(selection.parse_harnesses("pig,pi,pi-bolt"), ["pig-tip", "pi-node", "pibolt"])
        self.assertEqual(selection.parse_harnesses("pig-ts-*")[0], "pig-ts-aot")
        everything = selection.parse_harnesses("all")
        self.assertIn("pi-node", everything)
        self.assertNotIn("claude-code", everything)   # an arm with operator terms never runs unless named and accepted
        self.assertNotIn("copilot", everything)
        self.assertNotIn("pig-go-fused", everything)  # not run by default

    def test_exact_ids_win_and_order_is_kept_without_duplicates(self):
        self.assertEqual(selection.parse_harnesses("pibolt, pi-node pibolt"), ["pibolt", "pi-node"])

    def test_unknown_and_held_harnesses_are_explained(self):
        with self.assertRaisesRegex(selection.SelectionError, "did you mean pi-node"):
            selection.parse_harnesses("pi-nod")
        with self.assertRaisesRegex(selection.SelectionError, "held"):
            selection.parse_harnesses("pi-agent-rust")
        with self.assertRaisesRegex(selection.SelectionError, "no harness selected"):
            selection.parse_harnesses(" , ")


class Benches(unittest.TestCase):
    def test_presets_families_workloads_aliases_and_globs(self):
        self.assertEqual(selection.parse_benches("quick"), (["overhead/version", "overhead/print"], "quick"))
        names, preset = selection.parse_benches("streaming,long-session,memory")
        self.assertEqual(preset, "")
        self.assertIn("streaming/print-prose", names)
        self.assertIn("longsession/grow-n", names)
        self.assertIn("soak/realistic", names)
        self.assertEqual(selection.parse_benches("overhead/print*")[0], ["overhead/print", "overhead/print-tools", "overhead/print-write", "overhead/print-ext5", "overhead/print-ext10", "overhead/print-ext50", "overhead/print-ext100"])
        self.assertEqual(selection.parse_benches("startup")[0], ["overhead/version", "overhead/print"])

    def test_unknown_benchmark_suggests_the_nearest(self):
        with self.assertRaisesRegex(selection.SelectionError, "did you mean"):
            selection.parse_benches("streeming")

    def test_every_preset_workload_exists(self):
        from buffon import workloads
        registry = workloads.load_all()
        for name, preset in catalog.PRESETS.items():
            self.assertTrue(selection._expand(preset["workloads"], registry), name)


class SavedSelections(unittest.TestCase):
    def test_a_selection_round_trips_through_toml(self):
        for sel in (selection.from_preset("quick"), selection.from_preset("standard"), selection.Selection(harnesses=["pi-node"], workloads=selection.parse_benches("streaming")[0], spec="streaming", apis=["openai-completions"], rounds=9, adaptive=False, offline=True, isolation="container", time_budget_s=1200)):
            path = os.path.join(tempfile.mkdtemp(), "s.toml")
            selection.save(sel, path)
            self.assertEqual(selection.load(path), sel)

    def test_unknown_keys_and_missing_benchmarks_are_refused(self):
        with self.assertRaisesRegex(selection.SelectionError, "unknown key"):
            selection.loads('[up]\nharnes = ["pi-node"]\nbench = ["quick"]\n')
        with self.assertRaisesRegex(selection.SelectionError, "names no benchmark"):
            selection.loads('[up]\nharness = ["pi-node"]\n')

    def test_the_command_repeats_the_selection(self):
        self.assertEqual(selection.command(selection.from_preset("quick")), "python3 -m buffon up --harness pi-node,pig-tip,pibolt,opencode-v2,codex --bench quick")
        sel = selection.from_preset("standard").clone(offline=True, time_budget_s=1200)
        self.assertTrue(selection.command(sel, "./buffon.sh").startswith("./buffon.sh up --harness"))
        self.assertIn("--offline --time-budget 1200s", selection.command(sel))
        self.assertEqual(selection.command(sel, "./buffon.sh", "my.toml"), "./buffon.sh up my.toml")

    def test_durations(self):
        self.assertEqual([selection.parse_duration(t) for t in ("90", "90s", "20m", "1h30m")], [90, 90, 1200, 5400])
        with self.assertRaises(selection.SelectionError):
            selection.parse_duration("soon")
        self.assertEqual(selection.format_duration(45), "45 s")
        self.assertEqual(selection.format_duration(1500), "25 min")


class CommandLine(unittest.TestCase):
    def sel(self, *argv):
        args = cli.build_parser().parse_args(["up", *argv])
        return cli.build_selection(args)

    def test_defaults_are_the_quick_preset_with_the_default_harnesses(self):
        sel = self.sel()
        self.assertEqual((sel.preset, sel.harnesses, sel.adaptive), ("quick", list(catalog.DEFAULT_HARNESSES), True))
        self.assertNotIn("omp", sel.harnesses)

    def test_no_preset_runs_an_eval_unless_asked(self):
        for preset in catalog.PRESETS:
            self.assertEqual(self.sel("--bench", preset).evals, [], preset)
        self.assertEqual(self.sel("--bench", "streaming").evals, [])
        self.assertEqual(self.sel("--bench", "standard", "--evals", "faithfulness").evals, ["faithfulness"])

    def test_a_harness_that_speaks_none_of_the_chosen_apis_adds_its_own(self):
        arms = manifest.load_all()
        apis, added = selection.widen_apis(["openai-completions"], ["pi-node", "opencode-v2", "codex"], arms)
        self.assertEqual((apis, added), (["openai-completions", "openai-responses"], [("codex", "openai-responses")]))
        self.assertTrue(all(arms["pi-node"].supports_api(a) for a in apis), "Pi is paired with every harness on that harness's own API")
        self.assertEqual(selection.widen_apis(["openai-completions"], ["pi-node", "opencode-v2"], arms), (["openai-completions"], []))

    def test_flags_override_a_saved_file(self):
        path = os.path.join(tempfile.mkdtemp(), "s.toml")
        selection.save(selection.from_preset("standard"), path)
        sel = self.sel(path, "--harness", "pi", "--no-adaptive", "--rounds", "12", "--isolation", "container")
        self.assertEqual((sel.harnesses, sel.adaptive, sel.isolation, sel.preset), (["pi-node"], False, "container", ""))

    def test_help_fits_a_screen(self):
        text = cli.build_parser()._subparsers._group_actions[0].choices["up"].format_help()
        self.assertLessEqual(len(text.splitlines()), 40)


class OperatorTerms(unittest.TestCase):
    """An arm with `operator_terms` (Claude Code, Copilot CLI) runs only when named and the operator accepted its terms: the flag, BUFFON_ACCEPT_TERMS, or a saved selection."""

    def setUp(self):
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop(manifest.ACCEPT_ENV, None)

    def sel(self, *argv):
        return cli.build_selection(cli.build_parser().parse_args(["up", *argv]))

    def test_the_manifests_carry_the_terms_and_the_arms_are_not_held(self):
        arms = manifest.load_all()
        for name in ("claude-code", "copilot"):
            self.assertIsNone(arms[name].held, name)
            self.assertIn("https://", arms[name].operator_terms)
            self.assertFalse(arms[name].runs_by_default, name)
            self.assertNotIn(name, catalog.DEFAULT_HARNESSES)

    def test_naming_one_without_accepting_is_refused_with_the_terms_and_the_flag(self):
        for name in ("claude-code", "copilot"):
            with self.assertRaises(selection.SelectionError) as raised:
                selection.parse_harnesses(f"pi-node,{name}")
            text = str(raised.exception)
            self.assertIn(manifest.load_arm(name).operator_terms, text)
            self.assertIn(f"--accept-terms {name}", text)
            self.assertIn("BUFFON_ACCEPT_TERMS", text)

    def test_accepted_by_flag_or_environment(self):
        sel = self.sel("--harness", "pi-node,claude-code", "--accept-terms", "claude-code")
        self.assertEqual((sel.harnesses, sel.accept_terms), (["pi-node", "claude-code"], ["claude-code"]))
        os.environ[manifest.ACCEPT_ENV] = "copilot, claude-code"
        sel = self.sel("--harness", "claude-code,copilot")
        self.assertEqual((sel.harnesses, sel.accept_terms), (["claude-code", "copilot"], ["claude-code", "copilot"]))
        self.assertEqual(self.sel("--harness", "pi-node").accept_terms, [], "acceptance is recorded only for harnesses that are selected")

    def test_accepting_one_arm_does_not_accept_another(self):
        with self.assertRaisesRegex(selection.SelectionError, "--accept-terms copilot"):
            self.sel("--harness", "claude-code,copilot", "--accept-terms", "claude-code")

    def test_never_matched_by_all_a_glob_or_a_prefix_even_when_accepted(self):
        accept = {"claude-code", "copilot"}
        self.assertNotIn("claude-code", selection.parse_harnesses("all", accept=accept))
        self.assertNotIn("copilot", selection.parse_harnesses("all", accept=accept))
        for token in ("claude*", "copil*", "claude"):
            with self.assertRaisesRegex(selection.SelectionError, "only when named in full"):
                selection.parse_harnesses(token, accept=accept)
        self.assertEqual(selection.parse_harnesses("pi-node,claude-code", accept=accept), ["pi-node", "claude-code"])

    def test_a_saved_selection_stores_the_acceptance_and_loads_without_the_flag(self):
        sel = self.sel("--harness", "pi-node,claude-code", "--accept-terms", "claude-code", "--bench", "quick")
        path = os.path.join(tempfile.mkdtemp(), "s.toml")
        selection.save(sel, path)
        with open(path) as f:
            self.assertIn('accept_terms = ["claude-code"]', f.read())
        loaded = selection.load(path)
        self.assertEqual((loaded.harnesses, loaded.accept_terms), (["pi-node", "claude-code"], ["claude-code"]))
        self.assertEqual(self.sel(path).accept_terms, ["claude-code"])
        self.assertIn("--accept-terms claude-code", selection.command(sel))

    def test_the_command_line_exits_non_zero_quoting_the_terms(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            code = cli.main(["up", "--harness", "claude-code", "--plan"])
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn(manifest.load_arm("claude-code").operator_terms, err.getvalue())
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            code = cli.main(["up", "--harness", "claude-code", "--accept-terms", "claude-code", "--plan"])
        self.assertEqual(code, 0)
        self.assertIn("--accept-terms claude-code", out.getvalue())

    def test_a_session_names_an_arm_only_when_its_terms_are_accepted(self):
        argv = ["session", "overhead/version", "--arms", "claude-code", "--out", tempfile.mkdtemp()]
        with self.assertRaisesRegex(SystemExit, "--accept-terms claude-code"):
            cli.session_plan(cli.build_parser().parse_args(argv))
        plan = cli.session_plan(cli.build_parser().parse_args(argv + ["--accept-terms", "claude-code"]))
        self.assertEqual([a.id for a in plan.arms], ["claude-code"])
        everyone = cli.session_plan(cli.build_parser().parse_args(["session", "overhead/version", "--out", tempfile.mkdtemp(), "--accept-terms", "claude-code,copilot"]))
        self.assertFalse({"claude-code", "copilot"} & {a.id for a in everyone.arms})

    def test_the_listing_says_the_terms_are_needed(self):
        rows = {r["name"]: r for r in listing.harness_rows()}
        self.assertIn("--accept-terms claude-code", rows["claude-code"]["needs"])
        self.assertFalse(rows["copilot"]["runs_by_default"])


class Picker(unittest.TestCase):
    items = [("a", "A", ""), ("b", "B", "note"), ("c", "C", "")]

    def keys(self, *k):
        it = iter(k)
        return lambda: next(it)

    def test_checklist_moves_ticks_and_accepts(self):
        got = picker.checklist("T", self.items, ["a"], key=self.keys(picker.DOWN, picker.SPACE, picker.ENTER), out=io.StringIO())
        self.assertEqual(got, ["a", "b"])
        got = picker.checklist("T", self.items, ["a"], key=self.keys(picker.NONE, picker.ENTER, picker.ALL, picker.ENTER), out=io.StringIO())
        self.assertEqual(got, ["a", "b", "c"])   # enter with nothing ticked does not accept

    def test_checklist_quit_aborts(self):
        with self.assertRaises(picker.Aborted):
            picker.checklist("T", self.items, [], key=self.keys(picker.QUIT), out=io.StringIO())

    def test_the_input_fallback_takes_numbers_names_all_and_enter(self):
        for answer, want in (("2,c", ["b", "c"]), ("", ["a"]), ("a", ["a", "b", "c"]), ("b", ["b"])):
            got = picker.numbered("T", self.items, ["a"], input_fn=lambda _p, a=answer: a, out=io.StringIO())
            self.assertEqual(got, want)

    def test_the_input_fallback_asks_again_on_a_bad_name_and_quits_on_q(self):
        answers = iter(["zzz", "1"])
        self.assertEqual(picker.numbered("T", self.items, [], input_fn=lambda _p: next(answers), out=io.StringIO()), ["a"])
        with self.assertRaises(picker.Aborted):
            picker.numbered("T", self.items, [], input_fn=lambda _p: "q", out=io.StringIO())

    def test_choose_uses_the_fallback_without_a_terminal(self):
        self.assertEqual(picker.choose("T", self.items, ["c"], input_fn=lambda _p: "", out=io.StringIO(), tty=False), ["c"])

    def test_pick_walks_harnesses_then_a_preset(self):
        rows = [{"name": "pi-node", "version": "1", "state": "installed", "available": True}, {"name": "pig-0.4.1", "version": "1", "state": "not installed", "available": True},
                {"name": "x", "version": "1", "state": "not on this platform", "available": False}]
        answers = iter(["pi-node", "2"])   # one harness, then preset number 2 (standard)
        sel = picker.pick(rows, [], selection.from_preset("quick"), lambda s: 60, input_fn=lambda _p: next(answers), out=io.StringIO(), tty=False)
        self.assertEqual((sel.harnesses, sel.preset), (["pi-node"], "standard"))


    def test_the_picker_lists_default_harnesses_first_and_leaves_out_experiments(self):
        rows = [{"name": n, "version": "1", "state": "not installed", "available": True, "runs_by_default": d} for n, d in (("zeta", True), ("pi-node", True), ("pig-ts-aot", False), ("alpha", True))]
        shown = io.StringIO()
        answers = iter(["pi-node", "1"])
        picker.pick(rows, [], selection.from_preset("quick").clone(harnesses=["pi-node"]), lambda s: 60, input_fn=lambda _p: next(answers), out=shown, tty=False)
        text = shown.getvalue().split("Benchmarks")[0]
        self.assertNotIn("pig-ts-aot", text)
        self.assertLess(text.index("pi-node"), text.index("alpha"))   # the ticked one first, then alphabetical


class Estimates(unittest.TestCase):
    def test_a_slower_machine_expects_longer_and_history_replaces_the_table(self):
        sel = selection.from_preset("quick")
        fast = estimate.estimate(sel, dict(PROBE, speed=1.0))["total_s"]
        slow = estimate.estimate(sel, dict(PROBE, speed=3.0))["total_s"]
        self.assertGreater(slow, fast)
        known = estimate.estimate(sel, PROBE, {"overhead/print": 0.05, "overhead/version": 0.05})["steps"]["measure"]
        self.assertLess(known, estimate.estimate(sel, PROBE)["steps"]["measure"])

    def test_the_quick_preset_is_expected_to_stay_near_two_minutes(self):
        sel = selection.from_preset("quick").clone(harnesses=["pi-node", "pig-tip", "pibolt"])
        self.assertLess(estimate.estimate(sel, PROBE, installed=sel.harnesses)["total_s"], 150)

    def test_a_time_budget_cuts_rounds_then_evals_then_benchmarks_and_says_so(self):
        sel = selection.from_preset("standard")
        fit, notes = estimate.fit_budget(sel, 300, PROBE)
        self.assertLessEqual(estimate.estimate(fit, PROBE)["total_s"], 300)
        self.assertTrue(notes[0].startswith("rounds capped"))
        self.assertIn("overhead/version", fit.workloads)
        same, none = estimate.fit_budget(sel, 10**6, PROBE)
        self.assertEqual((same, none), (sel, []))

    def test_an_impossible_budget_keeps_the_first_benchmark_and_says_so(self):
        fit, notes = estimate.fit_budget(selection.from_preset("quick"), 1, PROBE)
        self.assertEqual(len(fit.workloads), 1)
        self.assertIn("over the 1 s budget", notes[-1])

    def test_history_records_the_median_wall_time_per_workload(self):
        path = os.path.join(tempfile.mkdtemp(), "t.json")
        raw = {"samples": [{"scenario": "overhead/print", "wall_s": w, "warmup": False} for w in (1.0, 2.0, 9.0)] + [{"scenario": "overhead/print", "wall_s": 99, "warmup": True}]}
        self.assertEqual(estimate.record_history(path, [raw]), {"overhead/print": 2.0})
        self.assertEqual(estimate.load_history(path), {"overhead/print": 2.0})

    def test_the_probe_is_short_and_bounded(self):
        p = estimate.probe(spawns=3)
        self.assertTrue(0.4 <= p["speed"] <= 8.0)
        self.assertLess(p["took_s"], 10)


class Machine(unittest.TestCase):
    def fake(self, cores, can_pin=True, vm=False, governor="performance"):
        return {"os": "Linux", "arch": "x86_64", "platform": "linux-x64", "python": "3.12", "cpu_model": "x", "cpus_total": sum(map(len, cores)), "cpus_allowed": [c for g in cores for c in g], "cores": cores,
                "smt": any(len(g) > 1 for g in cores), "can_pin": can_pin, "mem_gib": 8, "virtual_machine": vm, "governor": governor, "counters": {"available": False, "why": None},
                "container_runtime": None, "git": True, "npm": True}

    def test_whole_cores_from_the_top_one_for_the_harness_one_for_the_runner(self):
        m = self.fake([[0, 4], [1, 5], [2, 6], [3, 7]])
        self.assertEqual(machine.choose_cpus(m), ([2, 6], [3, 7]))

    def test_too_few_cores_or_no_pinning_pins_nothing(self):
        self.assertEqual(machine.choose_cpus(self.fake([[0], [1]])), ([], []))
        self.assertEqual(machine.choose_cpus(self.fake([[0], [1], [2], [3]], can_pin=False)), ([], []))
        self.assertEqual(machine.choose_cpus(self.fake([[0], [1], [2], [3]]), pin=False), ([], []))

    def test_the_written_profile_loads_and_names_no_host(self):
        base = tempfile.mkdtemp()
        paths = machine.paths(base)
        m = self.fake([[0], [1], [2], [3]])
        m["cpus_allowed"] = [0, 1, 2, 3]
        with mock.patch.object(sitelib, "load", wraps=sitelib.load):
            path, site, written = machine.ensure_profile(m, paths)
        self.assertTrue(written)
        self.assertEqual((site.local.cpus, site.local.mock_cpus, site.local.pinning), ([2], [3], "preferred"))
        again = machine.ensure_profile(m, paths)
        self.assertFalse(again[2])   # an existing profile that still fits is kept
        m["cpus_allowed"] = [0, 1]
        self.assertTrue(machine.ensure_profile(m, paths)[2])   # CPUs the process no longer has: detected again

    def test_a_virtual_machine_with_no_clock_interface_claims_the_hypervisor(self):
        text = machine.profile_text(self.fake([[0], [1], [2]], vm=True, governor=None), machine.paths(tempfile.mkdtemp()))
        self.assertIn('clock_claim = "hypervisor"', text)

    def test_the_buffon_home_follows_the_environment(self):
        with mock.patch.dict(os.environ, {"BUFFON_HOME": "/x/y"}):
            self.assertEqual(machine.home(), "/x/y")
        with mock.patch.dict(os.environ, {"BUFFON_HOME": "", "XDG_DATA_HOME": "/d"}):
            self.assertEqual(machine.home(), "/d/buffon")


class Listings(unittest.TestCase):
    def test_harness_rows_say_what_they_need_and_whether_they_are_installed(self):
        arms = manifest.load_all()
        rows = {r["name"]: r for r in listing.harness_rows(arms, {"pi-node": arms["pi-node"].manifest_sha256}, "linux-x64")}
        self.assertEqual(rows["pi-node"]["state"], "installed")
        self.assertEqual(rows["pig-0.4.1"]["state"], "not installed")
        self.assertTrue(rows["pi-node"]["default"])
        self.assertEqual(rows["pi-agent-rust"]["state"], "held")
        self.assertIn("pinned", rows["pi-node"]["needs"])
        self.assertEqual(listing.harness_rows(arms, {}, "linux-riscv")[[r["name"] for r in listing.harness_rows(arms, {}, "linux-riscv")].index("pi-bolt-0.8.5")]["state"], "not on linux-riscv")

    def test_a_changed_manifest_is_not_installed_any_more(self):
        arms = manifest.load_all()
        self.assertEqual({r["name"]: r for r in listing.harness_rows(arms, {"pi-node": "0" * 64}, "linux-x64")}["pi-node"]["state"], "not installed")

    def test_bench_rows_list_every_workload_with_a_time_and_the_unbuilt_families(self):
        rows = {r["id"]: r for r in listing.bench_rows(PROBE)}
        self.assertEqual(rows["overhead/print"]["state"], "wired")
        self.assertEqual(rows["overhead/print-ext10"]["state"], "partly wired")
        self.assertGreater(rows["overhead/print"]["seconds"], 0)
        self.assertEqual(rows["real-extensions"]["state"], "not run")
        self.assertIsNone(rows["real-extensions"]["seconds"])
        self.assertEqual(rows["scale/agents-limit"]["state"], "partly wired")
        self.assertEqual(rows["scale/print-ext10"]["state"], "partly wired")
        self.assertNotIn("scale/agents-32", rows)
        self.assertIn("quick", rows["overhead/print"]["preset"])
        self.assertIn("overhead/print", listing.bench_table(list(rows.values())))

    def test_every_workload_has_a_state_and_the_json_listing_works(self):
        for name in ("harnesses", "benches"):
            out = io.StringIO()
            with mock.patch("sys.stdout", out), mock.patch.dict(os.environ, {"BUFFON_HOME": tempfile.mkdtemp()}):
                self.assertEqual(cli.main([name, "--json"]), 0)
            self.assertTrue(json.loads(out.getvalue()))


class Interrupt(unittest.TestCase):
    def test_ctrl_c_says_what_is_kept_and_exits_130(self):
        err = io.StringIO()
        with mock.patch.object(flow, "up", side_effect=KeyboardInterrupt), mock.patch("sys.stderr", err), mock.patch.dict(os.environ, {"BUFFON_HOME": tempfile.mkdtemp()}):
            self.assertEqual(cli.main(["up", "--yes", "--no-open", "--no-dashboard"]), 130)
        self.assertIn("finished runs are kept", err.getvalue())


class Flow(unittest.TestCase):
    def test_headless_detection(self):
        self.assertTrue(flow.headless({"SSH_CONNECTION": "x"}, "darwin"))
        self.assertTrue(flow.headless({}, "linux"))
        self.assertFalse(flow.headless({"DISPLAY": ":0"}, "linux"))
        self.assertFalse(flow.headless({}, "darwin"))

    def test_without_a_browser_the_site_path_is_printed(self):
        lines = []
        self.assertFalse(flow.open_in_browser("/x/site/index.html", flow.Options(open_browser=True), lines.append, env={}, platform="linux"))
        self.assertIn("file:///x/site/index.html", lines[0])

    def test_the_landing_page_escapes_everything(self):
        summary = {"trust": {"badge": "Shared", "host_class": "B", "reasons": ["<script>x</script>"]}, "harnesses": ["<b>h</b>"], "benchmarks": ["a&b"], "command": "buffon up --x '<y>'"}
        page = flow.landing_page(summary, "report/report.html")
        self.assertNotIn("<script>x", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Run this yourself", page)

    def test_a_run_key_changes_with_anything_that_decides_the_result(self):
        arms = manifest.load_all()
        sel = selection.from_preset("quick")
        base = flow.run_key("measured", ["pi-node"], ["overhead/print"], sel, "pi-node", arms)
        self.assertEqual(base, flow.run_key("measured", ["pi-node"], ["overhead/print"], sel, "pi-node", arms))
        for changed in (flow.run_key("long", ["pi-node"], ["overhead/print"], sel, "pi-node", arms), flow.run_key("measured", ["pi-node", "pig-0.4.1"], ["overhead/print"], sel, "pi-node", arms),
                        flow.run_key("measured", ["pi-node"], ["overhead/version"], sel, "pi-node", arms), flow.run_key("measured", ["pi-node"], ["overhead/print"], sel.clone(rounds=5), "pi-node", arms),
                        flow.run_key("measured", ["pi-node"], ["overhead/print"], sel.clone(apis=["anthropic-messages"]), "pi-node", arms)):
            self.assertNotEqual(base, changed)

    def test_special_workloads_run_apart_from_the_sampled_ones(self):
        from buffon import workloads
        self.assertEqual(flow.groups(["overhead/print", "soak/realistic", "reliability/faults"], workloads.load_all()), [("measured", ["overhead/print"]), ("long", ["soak/realistic", "reliability/faults"])])

    def test_a_directory_is_finished_only_with_a_complete_measured_raw(self):
        d = tempfile.mkdtemp()
        self.assertFalse(flow.finished(d))
        for raw, want in (({"samples": []}, False), ({"samples": [{}], "refused": "x"}, False), ({"samples": [{}], "run": {"partial": True}}, False), ({"samples": [{}], "run": {}}, True)):
            with open(os.path.join(d, "raw.json"), "w") as f:
                json.dump(raw, f)
            self.assertEqual(flow.finished(d), want)


class EndToEnd(unittest.TestCase):
    """`buffon up` on a fresh home with two stub harnesses: install, measure with adaptive stopping, report, site. Nothing is downloaded."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.arms_dir = stub_arms.make(self.root)
        self.home = os.path.join(self.root, "home")
        self.patch = mock.patch.dict(os.environ, {"BUFFON_ARMS_DIR": self.arms_dir, "BUFFON_HOME": self.home, "BUFFON_LOCK_FILE": os.path.join(self.root, "buffon.lock")})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def up(self, **kw):
        lines = []
        sel = selection.from_preset("quick").clone(harnesses=["stub-fast", "stub-slow"], evals=[])
        opts = flow.Options(home=self.home, open_browser=False, pin=False, **kw)
        summary = flow.up(sel, opts, out=lines.append, arms=manifest.load_all(self.arms_dir))
        return summary, lines

    def test_a_fresh_home_runs_end_to_end_and_a_second_run_reuses_everything(self):
        summary, lines = self.up()
        text = "\n".join(lines)
        self.assertEqual(summary["harnesses"], ["stub-fast", "stub-slow"])
        self.assertIn(summary["trust"]["badge"], ("Shared", "Noisy"))   # unpinned: never Dedicated
        self.assertTrue(os.path.exists(summary["site"]))
        self.assertTrue(os.path.exists(os.path.join(self.home, "site", "report", "report.md")))
        self.assertTrue(os.path.exists(os.path.join(self.home, "sites", "this-machine.toml")))
        self.assertIn("buffon up: summary", text)
        self.assertIn("up --harness stub-fast,stub-slow --bench quick", summary["command"])
        with open(os.path.join(self.home, "site", "up.json")) as f:
            up = json.load(f)
        self.assertEqual(up["command"], summary["command"])
        with open(os.path.join(summary["run_dirs"][0], "raw.json")) as f:
            raw = json.load(f)
        self.assertTrue(raw["run"]["adaptive"]["enabled"])
        # Whether a cell is settled before 12 rounds depends on the host's noise: the stubs differ in a sleep, which neither watched metric (instructions, CPU time) sees, so a quiet
        # host settles them at once ("no measurable difference") and a noisy VM runs them to the cap. Stopping on clear and unclear answers is tested with synthetic samples
        # (tests/test_adaptive.py); here the run must say and record exactly what happened, whichever it was.
        stopped = raw["run"]["adaptive"]["stopped"]
        self.assertEqual(sum("settled after" in line for line in lines), len(stopped))
        self.assertEqual(bool(stopped), trust.realised_rounds(raw) < 12)   # a cell stopped early: the run cannot be Verified; none did: every cell took the cap
        self.assertLessEqual(trust.realised_rounds(raw), 12)
        self.assertEqual(trust.badge(raw)["badge"], summary["trust"]["badge"])
        again, lines2 = self.up()
        self.assertIn("a finished run with these settings exists, reused", "\n".join(lines2))
        self.assertEqual(again["run_dirs"], summary["run_dirs"])
        rerun, lines3 = self.up(rerun=True)
        self.assertNotIn("reused", "\n".join(lines3).split("measuring")[1].split("building")[0])
    def test_an_arm_with_operator_terms_runs_only_when_accepted_and_raw_json_records_it(self):
        path = os.path.join(self.arms_dir, "stub-slow", "arm.toml")
        with open(path) as f:
            text = f.read()
        with open(path, "w") as f:
            f.write(text.replace('version = "1.0"\n', 'version = "1.0"\noperator_terms = "Stub vendor terms apply; accept them yourself. https://example.invalid/terms"\n', 1))
        arms = manifest.load_all(self.arms_dir)
        with self.assertRaisesRegex(selection.SelectionError, "https://example.invalid/terms"):
            selection.parse_harnesses("stub-fast,stub-slow", arms, accept=set())
        lines = []
        sel = selection.from_preset("quick").clone(harnesses=["stub-fast", "stub-slow"], evals=[], accept_terms=["stub-slow"])
        summary = flow.up(sel, flow.Options(home=self.home, open_browser=False, pin=False), out=lines.append, arms=arms)
        self.assertEqual(summary["harnesses"], ["stub-fast", "stub-slow"])
        with open(os.path.join(summary["run_dirs"][0], "raw.json")) as f:
            raw = json.load(f)
        self.assertTrue(raw["arms"]["stub-slow"]["operator_terms_accepted"])
        self.assertIn("accept them yourself", raw["arms"]["stub-slow"]["operator_terms"])
        self.assertNotIn("operator_terms", raw["arms"]["stub-fast"])
        self.assertTrue(any(s["arm"] == "stub-slow" and not s["warmup"] and "failure" not in s for s in raw["samples"]))
        self.assertIn("--accept-terms stub-slow", summary["command"])

    def test_a_harness_that_cannot_install_is_left_out_and_said(self):
        os.remove(os.path.join(self.root, "files", "stub-slow"))
        summary, lines = self.up()
        self.assertEqual(summary["harnesses"], ["stub-fast"])
        self.assertIn("stub-slow", summary["left_out"])
        self.assertIn("left out", "\n".join(lines))

    def test_nothing_installable_is_an_error(self):
        for n in ("stub-fast", "stub-slow"):
            os.remove(os.path.join(self.root, "files", n))
        with self.assertRaisesRegex(flow.UpError, "no harness could be installed"):
            self.up()


if __name__ == "__main__":
    unittest.main()
