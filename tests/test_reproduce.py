# SPDX-License-Identifier: Apache-2.0
"""Reproducing a run and comparing it with the original: pins, plan, the host's noise, and each comparison."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from buffon import cli
from buffon.submit import reproduce
from tests.submit_fixtures import make_repo, sealed_dir, submit_raw


class Compare(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def run_dir(self, **kw):
        mutate = kw.pop("mutate", None)
        return sealed_dir(self.repo, submit_raw(self.repo, mutate=mutate, **kw))

    def test_the_same_run_twice_reproduces_everywhere_and_the_hosts_are_similar(self):
        c = reproduce.compare(self.run_dir(), self.run_dir())
        self.assertEqual(c["totals"], {"cells": 2, "reproduced": 2, "consistent_only": 0, "not_reproduced": 0})
        self.assertEqual(c["noise"]["verdict"], "similar")
        self.assertEqual((c["pins"], c["plan"]), ([], []))
        self.assertEqual(c["notes"], {"original": 0, "yours": 0})

    def test_a_noisier_host_is_called_noisier_with_the_numbers_beside_it(self):
        def noisy(s):
            if not s["warmup"]:
                k = (-1) ** s["round"] * (3 + s["round"] % 4)
                s["cpu_ms"] += k * (4 if s["arm"].endswith("-b") else 7)
                s["wall_ms"] += k * 3
        c = reproduce.compare(self.run_dir(), self.run_dir(mutate=noisy))
        self.assertEqual(c["noise"]["verdict"], "noisier")
        self.assertIn("your host was noisier than the original's", c["noise"]["sentence"])
        self.assertIn("about as noisy as", reproduce.compare(self.run_dir(), self.run_dir())["noise"]["sentence"])
        self.assertGreater(c["noise"]["yours"]["aa_floor_median"], 1.5 * c["noise"]["original"]["aa_floor_median"])
        back = reproduce.compare(self.run_dir(mutate=noisy), self.run_dir())
        self.assertEqual(back["noise"]["verdict"], "quieter")

    def test_a_slightly_noisier_host_is_still_similar(self):
        def a_bit_noisier(s):
            if not s["warmup"] and s["arm"].endswith("-b"):
                s["cpu_ms"] += 3.0 * (-1) ** s["round"]
        c = reproduce.compare(self.run_dir(), self.run_dir(mutate=a_bit_noisier))
        f0, f1 = c["noise"]["original"]["aa_floor_median"], c["noise"]["yours"]["aa_floor_median"]
        self.assertGreater(f1, f0)
        self.assertLess(f1, 1.5 * f0)
        self.assertEqual(c["noise"]["verdict"], "similar")

    def test_a_real_difference_does_not_reproduce(self):
        def slower(s):
            if s["arm"].startswith("other"):
                s["cpu_ms"] *= 1.3
        c = reproduce.compare(self.run_dir(), self.run_dir(mutate=slower))
        row = next(r for r in c["cells"] if r["metric"] == "cpu_ms")
        self.assertFalse(row["consistent"])
        self.assertFalse(row["reproduced"])
        self.assertEqual(c["totals"]["not_reproduced"], 1)
        text = "\n".join(reproduce.lines(c))
        self.assertIn("1 of 2 comparisons reproduce", text)
        self.assertIn("| overhead/print | openai-completions | cpu_ms | other |", text)

    def test_overlapping_intervals_or_a_gap_inside_the_floor_count_as_consistent(self):
        def noisy_and_slightly_slower(s):
            if s["arm"].startswith("other") and not s["warmup"]:
                s["cpu_ms"] = s["cpu_ms"] * 1.02 + (6 if s["round"] % 2 else -6)
        c = reproduce.compare(self.run_dir(), self.run_dir(mutate=noisy_and_slightly_slower))
        row = next(r for r in c["cells"] if r["metric"] == "cpu_ms")
        self.assertTrue(row["consistent"])

    def test_a_gap_inside_the_floor_is_consistent_even_when_the_intervals_do_not_overlap(self):
        def wild_copy(s):
            if s["arm"] == "other-b" and not s["warmup"]:
                s["cpu_ms"] += 14.0 * (-1) ** s["round"]
        def and_slower(s):
            wild_copy(s)
            if s["arm"] == "other":
                s["cpu_ms"] *= 1.05
        c = reproduce.compare(self.run_dir(mutate=wild_copy), self.run_dir(mutate=and_slower))
        row = next(r for r in c["cells"] if r["metric"] == "cpu_ms")
        self.assertGreater(row["yours"]["ci"][0], row["original"]["ci"][1], "the intervals do not overlap")
        self.assertTrue(row["consistent"])
        self.assertTrue(row["reproduced"])

    def test_consistent_ratios_with_different_verdicts_do_not_count_as_reproduced(self):
        # 'other' is 5% slower in both runs; with a wild A/A copy the first run cannot call it (inside its floor), the second run's quiet copies call it a loss
        def wild_copy(s):
            if s["arm"] == "other-b" and not s["warmup"]:
                s["cpu_ms"] += 14.0 * (-1) ** s["round"]
        c = reproduce.compare(self.run_dir(arm=105.0, mutate=wild_copy), self.run_dir(arm=105.0))
        row = next(r for r in c["cells"] if r["metric"] == "cpu_ms")
        self.assertTrue(row["consistent"])
        self.assertFalse(row["same_verdict"])
        self.assertFalse(row["reproduced"])
        self.assertEqual(c["totals"]["consistent_only"], 1)

    def test_a_different_verdict_with_consistent_ratios_is_reported_as_such(self):
        # same ratio, but the reproducer has no A/A copies of 'other', so its floor differs: the verdict can differ while the ratios agree
        orig, yours = self.run_dir(), None
        raw = submit_raw(self.repo)
        raw["samples"] = [s for s in raw["samples"] if s["arm"] != "other-b"]
        yours = sealed_dir(self.repo, raw)
        c = reproduce.compare(orig, yours)
        for r in c["cells"]:
            self.assertTrue(r["consistent"])
        self.assertEqual(c["totals"]["cells"], 2)

    def test_pin_and_plan_differences_are_listed(self):
        a = self.run_dir()
        raw = submit_raw(self.repo)
        raw["arms"]["pi-node"]["executable_sha256"] = "99" * 32
        raw["run"]["rounds"] = 24
        raw["run"]["seed"] = 5
        c = reproduce.compare(a, sealed_dir(self.repo, raw))
        self.assertIn(("pi-node executable_sha256", "e1" * 32, "99" * 32), c["pins"])
        self.assertEqual({p[0] for p in c["plan"]}, {"rounds", "seed"})
        self.assertIn("What differs between the runs", "\n".join(reproduce.lines(c)))

    def test_write_produces_markdown_and_json_from_the_same_data(self):
        c = reproduce.compare(self.run_dir(), self.run_dir())
        out = tempfile.mkdtemp()
        reproduce.write(c, out)
        with open(os.path.join(out, "reproduction.json")) as f:
            back = json.load(f)
        with open(os.path.join(out, "reproduction.md")) as f:
            md = f.read()
        self.assertEqual(back["totals"], c["totals"])
        self.assertIn("**2 of 2 comparisons reproduce**", md)
        self.assertIn("Telemetry: was your host noisier?", md)


class RunPlan(unittest.TestCase):
    def test_the_reproduction_repeats_the_plan_and_takes_the_machine_from_the_site(self):
        repo = make_repo()
        raw = submit_raw(repo)
        raw["run"].update({"command": ["buffon", "session", "overhead", "--timeout", "90", "--rpc-turns", "7", "--cpus", "4-9"], "params": {"session_n": 100, "label": "x"}, "arms": ["pi-node", "other"],
                           "workloads": ["overhead/print", "overhead/rpc"]})
        d = sealed_dir(repo, raw)
        argv = reproduce.run_argv(d, "mysite", "/out/dir")
        self.assertEqual(argv[:3], ["run", "overhead/print", "overhead/rpc"])
        for pair in (("--site", "mysite"), ("--out", "/out/dir"), ("--rounds", "12"), ("--warmup", "1"), ("--aa", "all"), ("--reference", "pi-node"), ("--seed", "7"), ("--timeout", "90"), ("--rpc-turns", "7"),
                     ("--param", "session_n=100"), ("--param", 'label="x"')):
            self.assertIn(pair, list(zip(argv, argv[1:])), pair)
        self.assertNotIn("--cpus", argv, "CPU numbers belong to the site profile, not to the reproduction")
        self.assertNotIn("--site", reproduce.run_argv(d, None, "/o"))

    def test_the_run_argv_parses_as_an_buffon_run(self):
        repo = make_repo()
        d = sealed_dir(repo)
        args = cli.build_parser().parse_args(reproduce.run_argv(d, "s", "/o"))
        self.assertEqual((args.cmd, args.rounds, args.aa, args.arms, args.site), ("run", 12, "all", ["pi-node", "other"], "s"))
        self.assertEqual(args.workloads, ["overhead/print"])


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_compare_writes_the_report_next_to_your_run(self):
        repo = make_repo()
        a, b = sealed_dir(repo), sealed_dir(repo)
        rc, out, _ = self.run_cli("compare", a, b)
        self.assertEqual(rc, 0)
        self.assertIn("2 of 2 comparisons reproduce", out)
        self.assertTrue(os.path.exists(os.path.join(b, "reproduction.md")))

    def test_reproduce_refuses_when_this_checkouts_pins_are_not_the_runs(self):
        repo = make_repo()
        d = sealed_dir(repo)
        rc, _, err = self.run_cli("reproduce", d, "--site", "x", "--out", tempfile.mkdtemp())
        self.assertEqual(rc, cli.EXIT_REFUSED)
        self.assertIn("not the one the run used", err)


if __name__ == "__main__":
    unittest.main()
