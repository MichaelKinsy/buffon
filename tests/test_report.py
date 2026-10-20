# SPDX-License-Identifier: Apache-2.0
import json
import math
import os
import re
import tempfile
import unittest

from buffon import stats
from buffon.report import cells, render
from buffon.runner import raw as rawlib


def sample(arm, scenario, rnd, api="openai-completions", warmup=False, **metrics):
    s = {"arm": arm, "scenario": scenario, "api": api, "round": rnd, "warmup": warmup}
    s.update(metrics)
    return s


def wobble(i):
    return (1, -1, 2, -2, 0, 1, -1, 0, 2, -2, 1, -1, 0, 1)[i % 14]


def series(scenario="overhead/print", rounds=12, ref=100.0, arm=150.0, metric="cpu_ms", extra=()):
    """pi-node, its copy, an arm and its copy over `rounds` rounds, with a deterministic wobble that differs between the copies."""
    out = []
    for r in range(rounds):
        for name, base, shift in (("pi-node", ref, 0), ("pi-node-b", ref, 3), ("other", arm, 1), ("other-b", arm, 5)):
            out.append(sample(name, scenario, r, **{metric: base + wobble(r + shift)}))
    return out + list(extra)


def raw_of(samples, quiet=False, rounds=12, skipped=(), egress=(), reasons=("the site profile does not claim dedicated hardware",)):
    return {"kind": "buffon-run", "run": {"rounds": rounds, "warmup": 1, "seed": 7, "harness_cpus": [1, 2], "mock_cpus": [3]}, "site": {"name": "t", "backend": "local"},
            "hardware": {"class": "quiet-dedicated" if quiet else "provisional", "quiet_dedicated": quiet, "reasons": [] if quiet else list(reasons)},
            "lock_sha256": "0" * 64, "runner": {"commit": "a" * 40, "tree": "b" * 40, "dirty": False}, "arms": {}, "calibration": {"max_cv": 0.01, "gate": 0.05, "metric": "cpu_ms", "passed": True},
            "egress": {"mode": "test", "violations": list(egress)}, "isolation": {}, "samples": samples, "skipped": list(skipped), "ok": True}


class Floor(unittest.TestCase):
    def test_a_ratio_far_outside_a_wide_floor_is_a_win_not_a_tie(self):
        # regression: with an additive floor a 0.11 ratio sat "inside" a 105% floor (|0.11 - 1| < 1.05).
        floor = math.log(2.05)
        self.assertEqual(cells.classify(0.11, (0.095, 0.18), floor), "win")
        self.assertEqual(cells.classify(9.0, (5.5, 10.5), floor), "loss")

    def test_the_floor_is_symmetric_on_the_log_scale(self):
        floor = math.log(1.25)
        self.assertEqual(cells.classify(1.25, (1.1, 1.4), floor), "no measurable difference")
        self.assertEqual(cells.classify(0.8, (0.7, 0.9), floor), "no measurable difference")
        self.assertEqual(cells.classify(1.26, (1.2, 1.4), floor), "loss")
        self.assertEqual(cells.classify(0.79, (0.7, 0.8), floor), "win")

    def test_verdicts(self):
        self.assertEqual(cells.classify(1.5, (0.9, 2.0), 0.1), "inconclusive")
        self.assertEqual(cells.classify(1.5, (1.2, 1.8), None), "loss")
        self.assertEqual(cells.classify(0.6, (0.5, 0.9), None), "win")
        self.assertEqual(cells.classify(1.5, (0.9, 2.0), None), "inconclusive (no A/A floor)")
        self.assertEqual(cells.classify(1.0, (math.nan, math.nan), 0.1), "too few rounds")
        self.assertEqual(cells.classify(math.inf, (2.0, math.inf), 0.1), "loss")

    def test_floor_of_a_pair_needs_rounds_and_is_never_negative(self):
        self.assertEqual(cells.floor_of([1, 2], [1, 2]), (None, None))
        floor, detail = cells.floor_of([100 + wobble(i) for i in range(12)], [100 + wobble(i + 3) for i in range(12)])
        self.assertGreaterEqual(floor, abs(math.log(detail["ratio"])))
        self.assertGreaterEqual(floor, math.log(detail["ci"][1]))
        self.assertGreaterEqual(floor, -math.log(detail["ci"][0]))
        self.assertEqual(cells.floor_of([0, 0, 0, 0], [1, 2, 3, 4]), (None, None))


class Build(unittest.TestCase):
    def data(self, samples):
        return cells.build([{"samples": samples}], seed=1)

    def cell(self, data, metric="cpu_ms", scenario="overhead/print"):
        return next(c for c in data["cells"] if c.metric == metric and c.scenario == scenario)

    def test_a_consistent_loss_is_a_loss_with_a_floor_and_a_small_mde(self):
        c = self.cell(self.data(series()))
        comp = c.comparisons["other"]
        self.assertEqual(comp.verdict, "loss")
        self.assertAlmostEqual(comp.ratio, 1.5, delta=0.03)
        self.assertEqual(comp.n, 12)
        self.assertLess(comp.floor, 0.2)
        self.assertLess(c.mde, 0.2)
        self.assertIn("pi-node", c.aa)
        self.assertNotIn("pi-node", c.comparisons)
        self.assertNotIn("other-b", c.comparisons)

    def test_an_identical_arm_is_inside_the_floor(self):
        comp = self.cell(self.data(series(arm=100.0))).comparisons["other"]
        self.assertEqual(comp.verdict, "no measurable difference")

    def test_the_reference_is_pi_node_when_present_else_the_first_arm_or_the_requested_one(self):
        d = self.data(series())
        self.assertEqual(d["reference"], "pi-node")
        s = [x for x in series() if not x["arm"].startswith("pi-node")]
        self.assertEqual(self.data(s)["reference"], "other")
        self.assertEqual(cells.build([{"samples": series()}], reference="other")["reference"], "other")

    def test_warm_up_failed_and_special_samples_and_descriptors_are_left_out(self):
        extra = [sample("other", "overhead/print", 0, warmup=True, cpu_ms=99999.0), sample("other", "overhead/print", 99, cpu_ms=99999.0, failure="boom"),
                 sample("other", "soak/stress", 0, rss_mib=5.0), sample("other", "reliability/faults", 0, seconds_ms=5.0)]
        base = self.data(series())
        d = self.data(series(extra=extra, metric="cpu_ms"))
        self.assertEqual(self.cell(d).comparisons["other"].ratio, self.cell(base).comparisons["other"].ratio)
        self.assertFalse([c for c in d["cells"] if c.scenario.startswith(("soak", "reliability"))])
        d2 = self.data(series(extra=[sample("other", "overhead/print", r, turns=3, requests=2) for r in range(12)]))
        self.assertFalse([c for c in d2["cells"] if c.metric in ("turns",)])

    def test_per_round_values_exclude_warm_up_and_failed_samples(self):
        samples = [sample("a", "w", 0, cpu_ms=10.0), sample("a", "w", 0, warmup=True, cpu_ms=9999.0), sample("a", "w", 1, cpu_ms=20.0, failure="boom"), sample("a", "w", 2, cpu_ms=30.0),
                   sample("a", "w", 3, api="anthropic-messages", cpu_ms=40.0), sample("b", "w", 2, cpu_ms=50.0), sample("a", "w", 4, turns=3)]
        self.assertEqual(cells.per_round(samples, "w", "openai-completions", "a", "cpu_ms"), {(0, 0): 10.0, (0, 2): 30.0})
        self.assertEqual(cells.per_round(samples, "w", "openai-completions", "a", "wall_ms"), {})

    def test_the_floor_against_the_reference_is_the_larger_of_the_two_copies_floors(self):
        s = []
        for r in range(12):
            s += [sample("pi-node", "w", r, cpu_ms=100.0 + wobble(r)), sample("pi-node-b", "w", r, cpu_ms=100.0 + wobble(r + 3)),
                  sample("other", "w", r, cpu_ms=150.0 + 20 * wobble(r)), sample("other-b", "w", r, cpu_ms=150.0 + 20 * wobble(r + 5))]
        c = self.cell(self.data(s), scenario="w")
        f_ref, f_arm = c.aa["pi-node"][0], c.aa["other"][0]
        self.assertGreater(f_arm, f_ref)
        self.assertEqual(c.comparisons["other"].floor, max(f_ref, f_arm))

    def test_rounds_are_paired_so_a_missing_round_drops_from_both_sides(self):
        s = [x for x in series() if not (x["arm"] == "other" and x["round"] in (3, 4))]
        comp = self.cell(self.data(s)).comparisons["other"]
        self.assertEqual(comp.n, 10)

    def test_without_copies_there_is_no_floor_and_nothing_is_called_equal(self):
        s = [x for x in series(arm=100.0) if not x["arm"].endswith("-b")]
        comp = self.cell(self.data(s)).comparisons["other"]
        self.assertTrue(math.isnan(comp.floor))
        self.assertIn("no A/A floor", comp.note)
        self.assertNotEqual(comp.verdict, "no measurable difference")

    def test_holm_adjusts_the_p_values_of_one_cell(self):
        s = series() + [sample("third", "overhead/print", r, cpu_ms=170.0 + wobble(r)) for r in range(12)]
        c = self.cell(self.data(s))
        for comp in c.comparisons.values():
            self.assertGreaterEqual(comp.p_holm, comp.p)

    def test_scored_metrics_are_costs_only(self):
        for m in ("cpu_ms", "wall_ms", "peak_rss_mib", "request_bytes", "n10_cpu_ms_per_1k_tokens", "first_paint_ms", "requests", "side_requests", "request_bytes_per_turn"):
            self.assertTrue(cells.scored(m), m)
        for m in ("turns", "stream_rate_tps", "fds_flat", "rss_mib_slope_per_h", "think_ms", "history_bytes"):
            self.assertFalse(cells.scored(m), m)

    def test_tally_and_coverage(self):
        d = self.data(series() + [sample("other", "streaming/tui-prose", 0, cpu_ms=1.0)])
        t = cells.tally(d["cells"], "other")
        self.assertEqual(t["overhead"]["loss"], 1)
        have, total = cells.coverage([], "other", d["cells"])
        self.assertEqual((have, total), (len(d["cells"]), len(d["cells"])))


class Render(unittest.TestCase):
    def report(self, samples, **kw):
        tmp = tempfile.mkdtemp()
        run = os.path.join(tmp, "run")
        rawlib.write(raw_of(samples, **kw), run)
        path = render.render([run], os.path.join(tmp, "out"))
        with open(path) as f:
            return f.read(), os.path.dirname(path)

    def test_every_heading_and_the_footer_carry_the_provisional_label(self):
        text, out = self.report(series())
        heads = [h for h in text.splitlines() if h.startswith("## ")]
        self.assertGreater(len(heads), 3)
        for h in heads:
            self.assertIn("PROVISIONAL", h)
        self.assertTrue(text.splitlines()[0].endswith("PROVISIONAL"))
        self.assertIn("PROVISIONAL: generated from 1 run directory", text)
        self.assertIn("the site profile does not claim dedicated hardware", text)

    def test_losses_come_before_everything_else_in_an_arm_section(self):
        extra = [sample(a, "overhead/print", r, wall_ms=v + wobble(r + k)) for r in range(12) for k, (a, v) in enumerate((("pi-node", 100.0), ("pi-node-b", 100.0), ("other", 60.0), ("other-b", 60.0)))]
        text, _ = self.report(series() + extra)
        loss, win = text.index("### Losses"), text.index("### Wins")
        self.assertLess(loss, win)
        self.assertRegex(text[loss:win], r"\| overhead/print \| chat \| cpu_ms \| CPU \| ms of CPU time \| 12 \|")
        self.assertRegex(text[win:], r"\| overhead/print \| chat \| wall_ms \| wall \| ms \| 12 \|")

    def test_a_run_made_on_a_site_clock_claim_says_so_in_its_header(self):
        raw = raw_of(series())
        raw["run"]["clock_claim"] = "hypervisor"
        with tempfile.TemporaryDirectory() as d:
            run = os.path.join(d, "r")
            os.makedirs(run)
            with open(os.path.join(run, "raw.json"), "w") as f:
                json.dump(raw, f)
            render.render([run], os.path.join(d, "o"))
            with open(os.path.join(d, "o", "report.md")) as f:
                text = f.read()
        self.assertIn("| run 1 clock | the site claims a virtual machine whose platform fixes the CPU clock and turbo state (hypervisor)", text)
        self.assertNotIn("run 1 clock", self.report(series())[0])

    def test_quiet_dedicated_runs_are_not_labelled_provisional(self):
        text, _ = self.report(series(), quiet=True)
        self.assertNotIn("PROVISIONAL", text)
        self.assertIn("quiet dedicated hardware", text)

    def test_fewer_than_twelve_rounds_say_not_a_measured_run(self):
        text, _ = self.report(series(rounds=4), rounds=4)
        self.assertIn("Not a measured run", text)
        text12, _ = self.report(series())
        self.assertNotIn("Not a measured run", text12)

    def test_a_source_built_arm_is_named_with_the_rebuild_caveat(self):
        raw = raw_of(series())
        raw["arms"] = {"pig-tip": {"version": "dev", "commit": "ac1821d", "install_method": "source build", "licence": "MIT"}, "pig-tip-b": {"commit": "ac1821d"}, "pi-node": {"version": "1.1.0", "install_method": "npm"}}
        tmp = tempfile.mkdtemp()
        rawlib.write(raw, os.path.join(tmp, "run"))
        with open(render.render([os.path.join(tmp, "run")], os.path.join(tmp, "out"))) as f:
            text = f.read()
        self.assertIn("Built from source at a pinned commit: `pig-tip`.", text)
        self.assertIn("private integration branch", text)
        plain = self.report(series())[0]
        self.assertNotIn("Built from source", plain)

    def test_failures_skips_and_egress_are_listed_and_never_a_loss(self):
        s = series() + [sample("other", "overhead/pty", 0, failure="did not start | with pipe"), sample("other", "overhead/pty", 1, failure="again")]
        text, _ = self.report(s, skipped=[{"arm": "rpi", "scenario": "overhead/pty", "api": None, "reason": "no pty mode"}],
                              egress=[{"arm": "omp", "scenario": "overhead/print", "api": "openai-completions", "remotes": ["192.0.2.9:443"]}])
        self.assertRegex(text, r"\| other \| overhead/pty \| chat \| 2/2 \| did not start / with pipe \|")
        self.assertRegex(text, r"\| rpi \| overhead/pty \| - \| no pty mode \|")
        self.assertIn("192.0.2.9:443", text)
        self.assertNotRegex(text, r"\| overhead/pty \| chat \| \w+ \| \d+ \|")

    def test_outputs_csv_and_json_are_written_and_the_csv_has_a_label_column(self):
        _, out = self.report(series())
        with open(os.path.join(out, "summary.csv")) as f:
            rows = [line.rstrip("\n").split(",") for line in f]
        self.assertEqual(rows[0][-1], "label")
        self.assertTrue(all(r[-1] == "PROVISIONAL" for r in rows[1:]))
        with open(os.path.join(out, "report.json")) as f:
            data = json.load(f)
        self.assertTrue(data["provisional"])
        self.assertEqual(data["reference"], "pi-node")
        self.assertEqual(data["cells"][0]["comparisons"]["other"]["verdict"], "loss")

    def test_several_run_directories_merge_and_any_provisional_run_labels_all(self):
        tmp = tempfile.mkdtemp()
        a, b = os.path.join(tmp, "a"), os.path.join(tmp, "b")
        rawlib.write(raw_of(series(), quiet=True), a)
        rawlib.write(raw_of(series(scenario="streaming/tui-prose", metric="n_wall_ms"), quiet=False), b)
        with open(render.render([a, b], os.path.join(tmp, "o"))) as f:
            text = f.read()
        self.assertIn("PROVISIONAL", text.splitlines()[0])
        self.assertIn("run 2: the site profile does not claim dedicated hardware", text)
        self.assertNotIn("run 1: the site", text)
        self.assertIn("| streaming/tui-prose |", text)
        self.assertIn("| overhead/print |", text)


    def test_run_directories_from_two_nodes_name_their_nodes_and_say_one_report_per_node(self):
        tmp = tempfile.mkdtemp()
        dirs = [os.path.join(tmp, n) for n in ("node-a", "node-b")]
        for d in dirs:
            rawlib.write(raw_of(series(), quiet=True), d)
            with open(os.path.join(d, "facts.json"), "w") as f:
                json.dump({"node": os.path.basename(d), "cpu_model": "cpu"}, f)
        with open(render.render(dirs, os.path.join(tmp, "o"))) as f:
            text = f.read()
        self.assertIn("**Several nodes.** The runs here ran on 2 nodes (`node-a`, `node-b`)", text)
        self.assertIn("| run 1 | site `", text)
        self.assertIn(", node `node-b`, ", text)
        with open(render.render(dirs[:1], os.path.join(tmp, "o1"))) as f:
            text = f.read()
        self.assertNotIn("Several nodes", text)
        self.assertIn("**One node.** Every run here ran on node `node-a`. A comparison is a headline only when it reproduces on a second node", text)


class PreviousRelation(unittest.TestCase):
    """R9: the change between an arm and the arm it replaces is data in the manifests (`previous`), for any arm; Buffon names no harness."""

    def samples(self, new="pig-tip", old="pig-0.4.1", tip=130.0):
        out = []
        for r in range(12):
            for k, (name, base) in enumerate((("pi-node", 100.0), ("pi-node-b", 100.0), (old, 50.0), (old + "-b", 50.0), (new, tip), (new + "-b", tip))):
                out.append(sample(name, "overhead/print", r, cpu_ms=base + wobble(r + k)))
        return out

    def raw(self, new="pig-tip", old="pig-0.4.1", declared=True, tip=130.0):
        raw = raw_of(self.samples(new, old, tip))
        raw["arms"] = {old: {"version": "1.0"}, new: dict({"version": "2.0+abc"}, **({"previous": old} if declared else {}))}
        return raw

    def test_a_declared_previous_gives_every_cell_a_step_and_the_section_lists_losses_first(self):
        d = cells.build([self.raw()], seed=1)
        c = next(c for c in d["cells"] if c.metric == "cpu_ms")
        self.assertAlmostEqual(c.steps["pig-tip"].ratio, 2.6, delta=0.1)
        self.assertEqual((c.steps["pig-tip"].verdict, c.steps["pig-tip"].arm, c.steps["pig-tip"].n), ("loss", "pig-tip", 12))
        self.assertEqual(d["previous"], {"pig-tip": "pig-0.4.1"})
        tmp = tempfile.mkdtemp()
        rawlib.write(self.raw(), os.path.join(tmp, "run"))
        with open(render.render([os.path.join(tmp, "run")], os.path.join(tmp, "out"))) as f:
            text = f.read()
        self.assertIn("## pig-tip against its previous arm pig-0.4.1: 1.0 → 2.0 (newer / previous) — PROVISIONAL", text)
        self.assertRegex(text, r"\| overhead/print \| chat \| cpu_ms \| 50\.\d* \| 130 \| 2\.\d+ \[.*\] \| .*\| \*\*loss\*\* \|")
        self.assertIn("| 1.0 → 2.0 (newer / previous) |", text)

    def test_any_arm_may_declare_one_nothing_in_the_report_is_specific_to_a_harness(self):
        d = cells.build([self.raw(new="acme-2", old="acme-1")], seed=1)
        self.assertEqual(d["previous"], {"acme-2": "acme-1"})
        self.assertEqual(next(c for c in d["cells"] if c.metric == "cpu_ms").steps["acme-2"].verdict, "loss")
        text = "\n".join(render.version_section(dict(d, versions={"acme-1": "1.0", "acme-2": "2.0"}), True))
        self.assertIn("## acme-2 against its previous arm acme-1", text)
        self.assertNotIn("PiG", text)

    def test_without_a_declaration_there_is_no_step_and_no_section_even_for_pig_arm_names(self):
        d = cells.build([self.raw(declared=False)], seed=1)
        self.assertTrue(all(not c.steps for c in d["cells"]))
        self.assertEqual(d["previous"], {})
        self.assertEqual(render.version_section(d, True), [])

    def test_a_tip_equal_to_the_release_is_no_measurable_difference_and_a_missing_arm_drops_the_step(self):
        d = cells.build([self.raw(tip=50.0)], seed=1)
        self.assertEqual(next(c for c in d["cells"] if c.metric == "cpu_ms").steps["pig-tip"].verdict, "no measurable difference")
        raw = self.raw()
        raw["samples"] = [x for x in raw["samples"] if not x["arm"].startswith("pig-tip")]
        d = cells.build([raw], seed=1)
        self.assertTrue(all(not c.steps for c in d["cells"]))
        self.assertEqual(render.version_section(dict(d, versions={}), True), [])

    def test_the_manifest_key_is_validated_and_carried_and_only_pig_tip_declares_it(self):
        from buffon.arms import manifest
        arms = manifest.load_all()
        self.assertEqual(arms["pig-tip"].previous, "pig-0.4.1")
        self.assertEqual({a for a, m in arms.items() if m.previous}, {"pig-tip"})   # a derived arm does not inherit it


class SoakAndReliability(unittest.TestCase):
    def data(self, samples):
        return cells.build([{"samples": samples}])

    def fault(self, arm, name, sig, rep, bad=None):
        s = sample(arm, f"reliability/{name}", rep, signature=sig, invariants_ok=bad is None)
        if bad:
            s["invariant_failures"] = bad
        return s

    def test_an_arm_passes_when_invariants_hold_and_it_matches_the_reference_signature(self):
        samples = [self.fault(a, "http-429-retry", "S", r) for a in ("pi-node", "pi-node-b", "other", "other-b") for r in range(3)]
        v = render.reliability_verdicts(self.data(samples))[("reliability/http-429-retry", "openai-completions")]
        self.assertTrue(all(ok for ok, _ in v.values()))

    def test_a_different_signature_a_broken_invariant_and_a_disagreeing_copy_each_fail(self):
        samples = [self.fault("pi-node", "x", "S", r) for r in range(3)] + [self.fault("pi-node-b", "x", "S", r) for r in range(3)]
        samples += [self.fault("diff", "x", "T", r) for r in range(3)]
        samples += [self.fault("bad", "x", "S", r, bad="hung") for r in range(3)]
        samples += [self.fault("flaky", "x", "S", 0), self.fault("flaky", "x", "T", 1), self.fault("flaky", "x", "S", 2)]
        samples += [self.fault("twin", "x", "S", r) for r in range(3)] + [self.fault("twin-b", "x", "T", r) for r in range(3)]
        v = render.reliability_verdicts(self.data(samples))[("reliability/x", "openai-completions")]
        self.assertEqual(v["pi-node"], (True, []))
        self.assertIn("differs from pi-node", v["diff"][1])
        self.assertIn("hung", v["bad"][1])
        self.assertIn("outcome differs between repetitions", v["flaky"][1])
        self.assertFalse(v["twin-b"][0])
        self.assertIn("A/A copy disagrees with its original", v["twin-b"][1])

    def test_soak_rows_say_flat_not_flat_undecided_or_failed(self):
        rows = [sample("a", "soak/stress", 0, api=None, flat=True, undecided=False, turns=9, soak_minutes=12.0, think_ms=0), sample("b", "soak/stress", 0, api=None, flat=False, undecided=False, fds_slope_per_h=900.0),
                sample("c", "soak/stress", 0, api=None, flat=False, undecided=True), sample("d", "soak/stress", 0, api=None, failure="boom")]
        text = "\n".join(render.soak_section(self.data(rows), True))
        for arm, verdict in (("a", "flat"), ("b", "NOT FLAT"), ("c", "undecided"), ("d", "failed")):
            self.assertRegex(text, rf"\| soak/stress \| {arm} \|.*\*\*{verdict}\*\*")
        self.assertIn("PROVISIONAL", text.splitlines()[0])


if __name__ == "__main__":
    unittest.main()


class ArmCaveat(unittest.TestCase):
    """R7: a manifest's `caveat` is repeated wherever its arm appears: summary, arm section, environment table."""

    def run_dir(self):
        raw = raw_of([sample(n, "overhead/print", r, cpu_ms=b + wobble(r + k)) for r in range(12) for k, (n, b) in enumerate((("pi-node", 100.0), ("pi-node-b", 100.0), ("omp", 90.0), ("omp-b", 90.0)))])
        raw["arms"] = {"omp": {"version": "18", "caveat": "its catalog refresh fails on every start"}, "omp-b": {"version": "18", "caveat": "its catalog refresh fails on every start"}, "pi-node": {"version": "1.1"}}
        tmp = tempfile.mkdtemp()
        rawlib.write(raw, os.path.join(tmp, "run"))
        with open(render.render([os.path.join(tmp, "run")], os.path.join(tmp, "out"))) as f:
            return f.read()

    def test_the_caveat_is_on_the_summary_row_the_arm_section_and_the_environment_table(self):
        text = self.run_dir()
        self.assertIn("| omp † |", text)
        self.assertIn("† `omp`: its catalog refresh fails on every start", text)
        self.assertIn("> **Read this first:** its catalog refresh fails on every start", text)
        self.assertIn("**omp:** its catalog refresh fails on every start", text)

    def test_an_arm_without_a_caveat_carries_none_and_the_omp_manifest_states_the_failure_path(self):
        self.assertNotIn("pi-node †", self.run_dir())
        from buffon.arms import manifest
        arms = manifest.load_all()
        self.assertIn("failure path", arms["omp"].caveat)
        self.assertEqual({a for a, m in arms.items() if m.caveat}, {"omp", "pig-tip", "pig-durable", "pi-durable-main"})   # the two durable arms say what their numbers are not (native SQLite, not a Durable Object; the main build is informational)


class TokenMethod(unittest.TestCase):
    def test_the_header_names_the_usage_method(self):
        tmp = tempfile.mkdtemp()
        rawlib.write(raw_of([sample(n, "overhead/print", r, cpu_ms=100.0 + wobble(r)) for r in range(12) for n in ("pi-node", "pi-node-b")]), os.path.join(tmp, "run"))
        with open(render.render([os.path.join(tmp, "run")], os.path.join(tmp, "out"))) as f:
            text = f.read()
        self.assertIn("| token counts | the mock's usage: prompt tokens = request wire bytes / 4", text)


class ReviewGuards(unittest.TestCase):
    """Report math the milestone-5 review found unguarded."""

    def test_the_bootstrap_resamples_rounds_as_pairs(self):
        ref = [10.0 * 1.5 ** i for i in range(12)]          # rounds differ by orders of magnitude
        arm = [x * 1.5 for x in ref]                         # but the arm is exactly 1.5x the reference in every round
        r = stats.paired_ratio_of_medians(arm, ref, seed=1)
        self.assertAlmostEqual(r["ratio"], 1.5)
        self.assertGreater(r["ci"][0], 1.49)
        self.assertLess(r["ci"][1], 1.51)

    def test_a_win_or_loss_needs_the_paired_test_too(self):
        self.assertEqual(cells.classify(2.0, (1.8, 2.2), 0.05, p=0.001), "loss")
        self.assertEqual(cells.classify(0.5, (0.4, 0.6), 0.05, p=0.001), "win")
        self.assertTrue(cells.classify(2.0, (1.8, 2.2), 0.05, p=0.25).startswith("inconclusive"))
        self.assertTrue(cells.classify(2.0, (1.8, 2.2), None, p=0.25).startswith("inconclusive"))
        self.assertEqual(cells.classify(1.01, (0.9, 1.2), 0.05, p=0.001), "no measurable difference")

    def test_three_rounds_never_make_a_verdict(self):
        """With 3 pairs the smallest two-sided sign-flip p is 0.25: whatever the interval says, nothing is a win or a loss."""
        samples = []
        for arm, k in (("ref", 1.0), ("ref-b", 1.0), ("x", 3.0), ("x-b", 3.0)):
            for rnd in range(3):
                samples.append({"arm": arm, "scenario": "w/a", "api": "openai-completions", "round": rnd, "warmup": False, "cpu_ms": k * (100 + rnd)})
        data = cells.build([{"samples": samples}], reference="ref")
        verdicts = {c.comparisons["x"].verdict for c in data["cells"] if "x" in c.comparisons}
        self.assertTrue(verdicts and all(v.startswith("inconclusive") for v in verdicts), verdicts)

    def test_two_runs_are_pooled_as_more_rounds_not_averaged_round_by_round(self):
        def run(offset):
            return {"samples": [{"arm": a, "scenario": "w/a", "api": "openai-completions", "round": rnd, "warmup": False, "cpu_ms": v + offset + rnd}
                                for a, v in (("ref", 100.0), ("x", 200.0)) for rnd in range(4)]}
        data = cells.build([run(0), run(1000)], reference="ref")
        cell = next(c for c in data["cells"] if c.metric == "cpu_ms")
        self.assertEqual(len(cell.values["ref"]), 8)
        self.assertEqual(cell.comparisons["x"].n, 8)

    def test_holm_across_arms_decides_the_verdict(self):
        """6 consistent pairs give a raw sign-flip p of 2/64 = 0.031: a loss for one arm, but Holm over two arms doubles it to 0.0625."""
        def run(arms):
            return {"samples": [{"arm": a, "scenario": "w/a", "api": "openai-completions", "round": rnd, "warmup": False, "cpu_ms": k * (100 + 7 * rnd) + (rnd % 2)}
                                for a, k in arms for rnd in range(6)]}
        base = [("ref", 1.0), ("ref-b", 1.0)]
        one = cells.build([run(base + [("x", 3.0)])], reference="ref")
        two = cells.build([run(base + [("x", 3.0), ("y", 3.0)])], reference="ref")
        c1 = next(c for c in one["cells"] if c.metric == "cpu_ms").comparisons["x"]
        c2 = next(c for c in two["cells"] if c.metric == "cpu_ms").comparisons["x"]
        self.assertEqual(c1.verdict, "loss")
        self.assertAlmostEqual(c2.p_holm, 0.0625)
        self.assertTrue(c2.verdict.startswith("inconclusive"), c2.verdict)

    def test_runs_with_different_locks_or_runners_are_flagged(self):
        a = {"lock_sha256": "1", "runner": {"commit": "c"}, "run": {"seed": 1}}
        self.assertEqual(render.mixed_runs([a, dict(a)]), [])
        self.assertEqual(render.mixed_runs([a, dict(a, lock_sha256="2", runner={"commit": "d"})]), ["arms.lock", "runner commit"])

    def test_runs_from_several_nodes_are_named_and_flagged(self):
        self.assertEqual(render.nodes_of([{"node": "n1"}, {"node": None}, {}, {"node": "n2"}, {"node": "n1"}]), ["n1", "n2"])
        self.assertEqual(render.nodes_of([{"node": "n1"}, {"node": "n1"}]), ["n1"])
        self.assertEqual(render.nodes_of([{}, {}]), [])

    def test_a_short_run_of_series_bearing_samples_still_gets_the_banner(self):
        """rpc, print-tools and long-session samples all carry a `series`; a 3-round run of them alone is still not a measured run."""
        run = {"run": {"rounds": 3}, "samples": [{"arm": "a", "scenario": "overhead/rpc", "round": r, "warmup": False, "series": {"turns": []}} for r in range(3)]}
        self.assertEqual(render.short_rounds([run]), [3])
        self.assertEqual(render.short_rounds([dict(run, run={"rounds": 12})]), [])
