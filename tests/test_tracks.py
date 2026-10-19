# SPDX-License-Identifier: Apache-2.0
"""The three tracks: the shipped definitions are consistent with the code, `buffon up --track` selects from them, recipes with parameters run apart, and the picker groups by track."""
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from buffon import cli, workloads
from buffon.arms import manifest
from buffon.up import catalog, flow, listing, machine, picker, selection, tracks
from tests import stub_arms
from tests.test_up import PROBE


class Definitions(unittest.TestCase):
    def setUp(self):
        self.tracks = tracks.load()
        self.registry = workloads.load_all()

    def test_the_shipped_definitions_have_no_problem(self):
        self.assertEqual(tracks.check(self.tracks, self.registry, catalog.EVALS), [])

    def test_the_owner_s_questions_are_all_there(self):
        titles = {t: [q["title"] for q in self.tracks[t]["questions"]] for t in ("common", "pi")}
        self.assertEqual(titles["common"], ["Speed", "Memory", "Reliability"])
        self.assertEqual(titles["pi"], ["Runs Pi's interfaces", "Scales with parallel agents", "Scales with extensions", "Scales with session size", "Streaming and wire efficiency"])
        self.assertEqual([r["id"] for r in self.tracks["real-world"]["recipes"]], ["day-of-work", "team-box", "heavy-setup", "cheap-machine"])

    def test_scaling_questions_carry_their_steps_and_the_agents_question_is_a_number(self):
        q = {x["id"]: x for x in self.tracks["pi"]["questions"]}
        self.assertEqual(q["agents"]["chart"], "number")
        self.assertEqual(q["agents"]["workloads"], ["scale/agents-limit", "scale/agents-ext10", "scale/print-limit", "scale/print-ext10"])
        self.assertNotIn("steps", q["agents"])
        self.assertNotIn("rungs", q["agents"])
        self.assertEqual(q["extensions"]["steps"], [0, 5, 10, 50, 100])
        self.assertEqual([r["workload"] for r in q["extensions"]["rungs"]], ["overhead/print", "overhead/print-ext5", "overhead/print-ext10", "overhead/print-ext50", "overhead/print-ext100"])
        self.assertEqual([w for w in q["extensions"]["workloads"] if w.startswith("overhead/print-ext")], ["overhead/print-ext5", "overhead/print-ext10", "overhead/print-ext50", "overhead/print-ext100"])
        self.assertIn("longsession/resume-4m2", {x["id"]: x for x in self.tracks["pi"]["questions"]}["session-size"]["workloads"])
        self.assertEqual(q["session-size"]["steps"], ["1 prompt", "1k turns", "4.2M tokens"])

    def test_every_unbuilt_benchmark_a_track_waits_for_is_listed_as_not_run(self):
        listed = {fam for fam, _w, _s in catalog.NOT_RUN}
        self.assertEqual(set(tracks.NOT_BUILT) - listed, set())

    def test_a_recipe_that_waits_for_an_unbuilt_benchmark_is_coming_not_runnable(self):
        by_id = {r["id"]: r for r in self.tracks["real-world"]["recipes"]}
        self.assertFalse(tracks.runnable(by_id["team-box"]))
        self.assertFalse(tracks.runnable(by_id["day-of-work"]))   # waits for the real extensions
        self.assertTrue(tracks.runnable(by_id["heavy-setup"]))
        self.assertTrue(tracks.runnable(by_id["cheap-machine"]))
        self.assertIn("real-extensions", {c for c, _w, _s in tracks.coming_of(self.tracks, "real-world")})

    def test_a_recipe_adds_no_metric_it_reports_only_what_it_uses(self):
        for r in self.tracks["real-world"]["recipes"]:
            for rep in r["reports"]:
                self.assertIn(rep["from"], r.get("uses", []) + r.get("coming", []))

    def test_check_names_each_kind_of_mistake(self):
        bad = {"common": {"questions": [{"id": "x", "workloads": ["nope/none"], "evals": ["zzz"], "coming": ["warp"], "chart": "pie", "extra": 1}, {"id": "y"}]}, "pi": {"questions": []},
               "real-world": {"recipes": [{"id": "r", "uses": ["nope/none"], "machine": "toaster", "conditions": "wild", "reports": [{"label": "L", "from": "other"}], "stray": 1}, {"id": "s", "machine": "laptop", "conditions": "lab", "uses": []}]}}
        text = "\n".join(tracks.check(bad, self.registry, catalog.EVALS))
        for needle in ("unknown key extra", "workload nope/none is not registered", "eval zzz", "coming warp", "chart pie", "answers nothing", "unknown key stray", "machine 'toaster'", "conditions 'wild'",
                       "takes its number from 'other'", "says no number it reports"):
            self.assertIn(needle, text)


class Selections(unittest.TestCase):
    def test_each_track_selects_its_wired_benchmarks_and_evals(self):
        common, pi, real = (selection.from_track(t) for t in ("common", "pi", "real-world"))
        self.assertIn("reliability/faults", common.workloads)
        self.assertEqual(common.evals, [])
        self.assertIn("overhead/print-ext10", pi.workloads)
        self.assertTrue({"scale/agents-limit", "scale/agents-ext10", "scale/print-limit", "scale/print-ext10"} <= set(pi.workloads))
        self.assertEqual(pi.evals, [], "no track runs the faithfulness probes")
        self.assertEqual(set(real.workloads), {"overhead/version", "overhead/print", "longsession/resume-n", "overhead/rpc-ext50", "longsession/resume-4m2"})   # only the recipes that are built
        self.assertEqual(len(selection.from_track("all").workloads), len(set(selection.from_track("all").workloads)))

    def test_containers_are_the_default_for_the_pi_family_and_real_world_only(self):
        self.assertEqual([selection.from_track(t).isolation for t in ("common", "pi", "real-world", "all")], ["", "auto", "auto", "auto"])

    def test_unknown_track_is_refused(self):
        with self.assertRaisesRegex(selection.SelectionError, "unknown track"):
            selection.from_track("fast")

    def test_the_command_line_and_a_saved_file_carry_the_track(self):
        sel = selection.from_track("pi").clone(harnesses=["pi-node"])
        self.assertEqual(selection.command(sel), "python3 -m buffon up --harness pi-node --track pi")
        path = os.path.join(tempfile.mkdtemp(), "t.toml")
        selection.save(sel, path)
        with open(path) as f:
            self.assertIn('track = "pi"', f.read())
        self.assertEqual(selection.load(path), sel)
        self.assertIn("--isolation none", selection.command(sel.clone(isolation="none")))

    def parse(self, *argv):
        return cli.build_selection(cli.build_parser().parse_args(["up", *argv]))

    def test_up_track_selects_and_explicit_flags_still_override(self):
        sel = self.parse("--track", "pi", "--harness", "pig", "--evals", "faithfulness", "--rounds", "9")
        self.assertEqual((sel.track, sel.harnesses, sel.evals, sel.rounds), ("pi", ["pig-tip"], ["faithfulness"], 9))

    def test_track_and_bench_together_are_refused(self):
        with self.assertRaisesRegex(selection.SelectionError, "give one"):
            self.parse("--track", "pi", "--bench", "quick")

    def test_up_plan_with_a_track_prints_the_track_command(self):
        out = io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch.dict(os.environ, {"BUFFON_HOME": tempfile.mkdtemp()}):
            self.assertEqual(cli.main(["up", "--plan", "--track", "common", "--yes"]), 0)
        self.assertIn("--track common", out.getvalue())

    def test_the_bench_listing_says_which_tracks_each_benchmark_is_in(self):
        rows = {r["id"]: r for r in listing.bench_rows(PROBE)}
        self.assertEqual(rows["overhead/print-tools"]["tracks"], ["common"])
        self.assertIn("pi", rows["overhead/rpc-ext10"]["tracks"])
        self.assertEqual(rows["real-extensions"]["tracks"], ["pi", "real-world"])
        self.assertEqual(rows["scale/agents-limit"]["state"], "partly wired")
        self.assertIn("pi", rows["overhead/print-ext100"]["tracks"])


class Isolation(unittest.TestCase):
    def site(self, cpus):
        return type("S", (), {"local": type("L", (), {"cpus": cpus})()})()

    def test_auto_means_a_container_where_there_is_a_runtime_and_pinned_cpus(self):
        sel = selection.from_track("pi")
        self.assertEqual(flow.resolve_isolation(sel, {"container_runtime": "docker"}, self.site([2]))[0], "container")

    def test_auto_falls_back_to_bare_and_says_why(self):
        sel = selection.from_track("pi")
        iso, note = flow.resolve_isolation(sel, {"container_runtime": None}, self.site([2]))
        self.assertEqual(iso, "none")
        self.assertIn("no docker or podman", note)
        iso, note = flow.resolve_isolation(sel, {"container_runtime": "podman"}, self.site([]))
        self.assertEqual(iso, "none")
        self.assertIn("no pinned CPUs", note)
        self.assertIn("uncontained", note)

    def test_an_explicit_choice_is_kept(self):
        self.assertEqual(flow.resolve_isolation(selection.from_preset("quick").clone(isolation="container"), {"container_runtime": None}, self.site([]))[0], "container")
        self.assertEqual(flow.resolve_isolation(selection.from_preset("quick"), {"container_runtime": "docker"}, self.site([2])), ("", None))


class RecipeGroups(unittest.TestCase):
    def test_a_recipe_with_parameters_is_its_own_run_with_those_parameters(self):
        recipe = {"id": "demo", "title": "Demo", "sentence": "s", "machine": "laptop", "conditions": "typical", "uses": ["longsession/resume-n"], "params": {"session_n": 50}, "reports": [{"label": "T", "from": "longsession/resume-n", "metric": "wall_ms"}]}
        fake = {"common": {"questions": []}, "pi": {"questions": []}, "real-world": {"recipes": [recipe]}}
        sel = selection.from_preset("quick").clone(recipes=["demo"])
        (name, ids, params, _r), = flow.recipe_groups(sel, fake)
        self.assertEqual((name, ids, params), ("recipe-demo", ["longsession/resume-n"], {"session_n": 50}))
        argv = flow.run_argv(flow.Options(home=tempfile.mkdtemp()), machine.paths(tempfile.mkdtemp()), sel, ["pi-node"], "pi-node", ids, "/out", params)
        self.assertEqual(argv[argv.index("--param") + 1], "session_n=50")

    def test_the_parameters_are_part_of_a_runs_identity(self):
        arms, sel = manifest.load_all(), selection.from_preset("quick")
        a = flow.run_key("g", ["pi-node"], ["overhead/print"], sel, "pi-node", arms, {"session_n": 50})
        self.assertNotEqual(a, flow.run_key("g", ["pi-node"], ["overhead/print"], sel, "pi-node", arms, {"session_n": 51}))
        self.assertNotEqual(a, flow.run_key("g", ["pi-node"], ["overhead/print"], sel, "pi-node", arms))


class PickerGroups(unittest.TestCase):
    items = [("#one", "Track 1", ""), ("a", "A", ""), ("b", "B", ""), ("#two", "Track 2", ""), ("c", "C", "")]

    def test_headings_are_not_choices_in_either_picker(self):
        keys = iter([picker.DOWN, picker.DOWN, picker.SPACE, picker.ENTER])   # from a: b, then past the heading to c
        self.assertEqual(picker.checklist("T", self.items, [], key=lambda: next(keys), out=io.StringIO()), ["c"])
        self.assertEqual(picker.checklist("T", self.items, ["#one", "a"], key=iter([picker.ALL, picker.ENTER]).__next__, out=io.StringIO()), ["a", "b", "c"])
        buf = io.StringIO()
        self.assertEqual(picker.numbered("T", self.items, [], input_fn=lambda _p: "3", out=buf), ["c"])   # numbers skip headings: 1=a 2=b 3=c
        self.assertIn("Track 2", buf.getvalue())

    def test_pick_offers_the_tracks_and_a_track_choice_sets_the_selection(self):
        rows = [{"name": "pi-node", "version": "1", "state": "installed", "available": True}]
        answers = iter(["pi-node", "pi"])
        sel = picker.pick(rows, [], selection.from_preset("quick"), lambda s: 60, input_fn=lambda _p: next(answers), out=io.StringIO(), tty=False)
        self.assertEqual((sel.track, sel.isolation, sel.evals), ("pi", "auto", []))

    def test_pick_individual_groups_the_benchmarks_by_track(self):
        rows = [{"name": "pi-node", "version": "1", "state": "installed", "available": True}]
        bench = [{"id": "overhead/print-tools", "state": "wired", "seconds": 5, "tracks": ["common"]}, {"id": "overhead/rpc-ext10", "state": "wired", "seconds": 5, "tracks": ["pi"]},
                 {"id": "devloop/install", "state": "wired", "seconds": 5, "tracks": []}]
        shown = io.StringIO()
        answers = iter(["pi-node", "pick", "1,3"])
        sel = picker.pick(rows, bench, selection.from_preset("quick"), lambda s: 60, input_fn=lambda _p: next(answers), out=shown, tty=False)
        self.assertEqual(sel.workloads, ["overhead/print-tools", "devloop/install"])
        text = shown.getvalue()
        self.assertLess(text.index("Track 1 - Common ground"), text.index("Track 2 - Pi family"))
        self.assertLess(text.index("Track 2 - Pi family"), text.index("Other benchmarks"))


class UpJson(unittest.TestCase):
    def test_up_json_names_the_track_the_conditions_and_what_is_coming(self):
        root = tempfile.mkdtemp()
        arms_dir = stub_arms.make(root)
        home = os.path.join(root, "home")
        with mock.patch.dict(os.environ, {"BUFFON_ARMS_DIR": arms_dir, "BUFFON_HOME": home, "BUFFON_LOCK_FILE": os.path.join(root, "buffon.lock")}):
            sel = selection.from_track("pi").clone(harnesses=["stub-fast", "stub-slow"], workloads=["overhead/print"], evals=[], isolation="none", track="pi", rounds=7)
            summary = flow.up(sel, flow.Options(home=home, open_browser=False, pin=False), out=lambda *_: None, arms=manifest.load_all(arms_dir))
        with open(os.path.join(home, "site", "up.json")) as f:
            up = json.load(f)
        self.assertEqual((up["track"], up["conditions"]), ("pi", "typical"))
        self.assertEqual({c["name"] for c in up["coming"]}, {"real-extensions"})
        self.assertIn("--track pi", summary["command"])


if __name__ == "__main__":
    unittest.main()


class ContainerCost(unittest.TestCase):
    def raw(self, arm, wall, cpu, envelope=None):
        samples = [{"arm": arm, "scenario": "overhead/print", "round": r, "warmup": r == 0, "wall_ms": wall + r, "cpu_ms": cpu + r} for r in range(1, 8)] + [{"arm": arm, "scenario": "overhead/print", "round": 0, "warmup": True, "wall_ms": 999, "cpu_ms": 999}]
        return {"samples": samples, "run": {"isolation": {"envelope": envelope or {}}}}

    def test_the_pair_gives_the_ratio_of_the_arms_medians_bare_and_in_a_container(self):
        out = tracks.container_overhead(self.raw("pi-node", 100, 80), self.raw("pi-node", 110, 88, {"null_run_ms": 700}), "pi-node")
        self.assertEqual((out["metrics"]["wall_ms"]["ratio"], out["metrics"]["cpu_ms"]["ratio"], out["null_run_ms"]), (1.096, 1.095, 700))   # medians 104 -> 114 and 84 -> 92; the warm-up round is left out

    def test_a_pair_without_samples_gives_nothing(self):
        self.assertIsNone(tracks.container_overhead({"samples": []}, self.raw("pi-node", 1, 1), "pi-node"))

    def test_the_flow_step_runs_the_arm_bare_then_in_a_container_and_reports_the_ratio(self):
        import json as jsonlib
        home = tempfile.mkdtemp()
        paths = machine.paths(home)
        os.makedirs(paths["runs"])
        seen = []

        def fake_runner(argv, log, out):
            seen.append(argv[argv.index("--isolation") + 1])
            d = argv[argv.index("--out") + 1]
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "raw.json"), "w") as f:
                jsonlib.dump(self.raw("pi-node", 100 if seen[-1] == "none" else 120, 50), f)
            return 0
        steps = flow.Reporter(9, lambda *_: None)
        sel = selection.from_track("pi").clone(isolation="container")
        out = flow.container_overhead(flow.Options(home=home), paths, sel, "pi-node", steps, runner=fake_runner)
        self.assertEqual(seen, ["none", "container"])
        self.assertAlmostEqual(out["metrics"]["wall_ms"]["ratio"], 1.19, places=2)

    def test_a_failed_run_skips_the_pair_quietly(self):
        home = tempfile.mkdtemp()
        paths = machine.paths(home)
        os.makedirs(paths["runs"])
        out = flow.container_overhead(flow.Options(home=home), paths, selection.from_track("pi"), "pi-node", flow.Reporter(9, lambda *_: None), runner=lambda *a: 1)
        self.assertIsNone(out)
