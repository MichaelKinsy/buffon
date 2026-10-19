# SPDX-License-Identifier: Apache-2.0
"""buffon/campaign.py: the plan check, the steps a campaign runs and in which order, resuming, the cluster wait and the bundle it runs from. The cluster and the
sessions are replaced by recorders; tests/test_backend_k8s.py covers the backend calls against the real buffon-cluster binary."""
import argparse
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

from buffon import backend, campaign
from buffon.backend import BackendError
from buffon.backend import bundle as bundlelib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUIET = os.path.join(ROOT, "campaigns", "quiet-v1.toml")

PLAN = """
[campaign]
name = "t1"
[calibrate]
workloads = ["overhead/version"]
rounds = 12
[[family]]
name = "ov"
workloads = ["overhead/version", "overhead/print"]
arms = ["pi-node", "pig-0.4.1"]
rounds = 13
apis = ["openai-completions"]
params = { session_n = 50, label = "x" }
[[family]]
name = "st"
workloads = ["streaming"]
arms = ["pi-node"]
"""


class PlanChecks(unittest.TestCase):
    def check(self, text):
        import tomllib
        campaign.check_plan(tomllib.loads(text))

    def test_the_committed_quiet_plan_is_valid(self):
        plan, sha = campaign.load_plan(QUIET)
        self.assertEqual(plan["campaign"]["name"], "quiet-v1")
        self.assertRegex(sha, "^[0-9a-f]{64}$")
        self.assertEqual(campaign.plan_arms(plan), ["pi-node", "pi-bun", "pibolt", "pig-tip", "pig-0.4.1", "rpi"])

    def test_the_ticket_1_plan_names_the_four_ticket_arms_and_every_arm_exists(self):
        from buffon.arms import manifest
        plan, _ = campaign.load_plan(os.path.join(ROOT, "campaigns", "ticket1.toml"))
        self.assertEqual(plan["campaign"]["name"], "ticket1")
        self.assertEqual(campaign.plan_arms(plan), ["pi-node", "pig-tip", "pig-0.4.1", "pi-bolt-0.8.5"])
        self.assertEqual(campaign.plan_arms(plan), [a for a in campaign.plan_arms(plan) if a in manifest.load_all()])
        self.assertEqual([f["name"] for f in plan["family"]], ["overhead", "ext10", "streaming", "longsession"])

    def test_refusals(self):
        cases = [
            ("unknown table", PLAN + "[extra]\n", "unknown table"),
            ("no calibrate", PLAN.replace('[calibrate]\nworkloads = ["overhead/version"]\nrounds = 12\n', ""), r"no \[calibrate\]"),
            ("no family", PLAN.split("[[family]]")[0], r"no \[\[family\]\]"),
            ("unknown key", PLAN.replace('rounds = 13', 'rounds = 13\nrepeat = 2'), "unknown key"),
            ("bad name", PLAN.replace('name = "ov"', 'name = "Ov_1"'), "family name"),
            ("reserved name", PLAN.replace('name = "ov"', 'name = "calibrate"'), "family name"),
            ("duplicate", PLAN.replace('name = "st"', 'name = "ov"'), "share the name"),
            ("short", PLAN.replace("rounds = 13", "rounds = 11"), "at least 12"),
            ("short calibrate", PLAN.replace("rounds = 12", "rounds = 3"), "at least 12"),
            ("bool rounds", PLAN.replace("rounds = 13", "rounds = true"), "at least 12"),
            ("unknown arm", PLAN.replace('arms = ["pi-node"]', 'arms = ["nope"]'), "nope is not a runnable arm"),
            ("held arm", PLAN.replace('arms = ["pi-node"]', 'arms = ["pi-agent-rust"]'), "pi-agent-rust is not a runnable arm"),
            ("no arms", PLAN.replace('arms = ["pi-node"]', 'arms = []'), "at least one arm"),
            ("unknown workload", PLAN.replace('workloads = ["streaming"]', 'workloads = ["nope/x"]'), "unknown workload"),
            ("campaign name", PLAN.replace('name = "t1"', 'name = "T 1"'), r"\[campaign\] name"),
            ("reference", PLAN.replace('name = "t1"', 'name = "t1"\nreference = "nope"'), "reference 'nope'"),
            ("params", PLAN.replace('params = { session_n = 50, label = "x" }', 'params = 3'), "params must be a table"),
            ("adaptive not a bool", PLAN.replace("rounds = 13", "rounds = 13\nadaptive = 1"), "adaptive is true or false"),
            ("adaptive on calibrate", PLAN.replace('[calibrate]\nworkloads = ["overhead/version"]\nrounds = 12\n', '[calibrate]\nworkloads = ["overhead/version"]\nrounds = 12\nadaptive = true\n'), "unknown key"),
        ]
        self.check(PLAN)
        for name, text, message in cases:
            with self.subTest(name), self.assertRaisesRegex(campaign.PlanError, message):
                self.check(text)

    def test_family_argv(self):
        import tomllib
        plan = tomllib.loads(PLAN)
        argv = campaign.family_argv("run", plan["family"][0], "pool", "/c/ov", "pi-node", "/c/bundle", "/c/calibrate/calibration.json")
        self.assertEqual(argv, ["run", "overhead/version", "overhead/print", "--out", "/c/ov", "--rounds", "13", "--reference", "pi-node", "--site", "pool",
                                "--arms", "pi-node", "pig-0.4.1", "--apis", "openai-completions", "--param", "label=x", "--param", "session_n=50",
                                "--calibration", "/c/calibrate/calibration.json", "--bundle", "/c/bundle"])
        self.assertEqual(campaign.family_argv("calibrate", plan["calibrate"], "", "/c/calibrate", "pi-node", None),
                         ["calibrate", "overhead/version", "--out", "/c/calibrate", "--rounds", "12", "--reference", "pi-node"])
        adaptive = dict(plan["family"][0], adaptive=True)
        self.assertIn("--adaptive", campaign.family_argv("run", adaptive, "", "/c/ov", "pi-node", None))
        self.assertNotIn("--adaptive", argv, "a family without the key takes every round")


class FakeBackend:
    def __init__(self, answers=(0,)):
        self.answers, self.asked = list(answers), 0

    def check(self):
        pass

    def nodes(self, count=1, candidates=()):
        self.asked += 1
        code = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return (0, {"nodes": [{"name": "n1"}]}) if code == 0 else (code, "Unable to connect to the server")


class Runs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plan = os.path.join(self.tmp, "plan.toml")
        with open(self.plan, "w") as f:
            f.write(PLAN)
        self.out = os.path.join(self.tmp, "c")
        self.calls, self.exits, self.rejected, self.logs = [], {}, set(), []
        self.counted, self.perf_exit = True, None
        self.during_run, self.vouched, self.models, self.compared = None, ("node-1", "node-2", "node-3", "node-4"), {}, []

    def site(self, bundle_mode=False):
        path = os.path.join(self.tmp, "site.toml")
        with open(path, "w") as f:
            f.write(f'[site]\nbackend = "kubernetes"\n[local]\ncache_dir = "{self.tmp}/host-cache"\n[kubernetes]\nnamespace = "n"\narch = "amd64"\n')
            f.write(f'bundle = true\nbase_image = "python@sha256:{"a" * 64}"\n' if bundle_mode else f'image = "reg.example/buffon@sha256:{"a" * 64}"\n')
        return path

    NODES = ("node-1", "node-2", "node-3", "node-4", "node-5")

    def fake_run(self, argv, log_path=None):
        """What `python3 -m buffon run|calibrate` leaves: a calibration.json judging NODES (self.vouched pass) with each node's run directory and CPU model
        (self.models), or a run directory with raw.json, laid out per node (cluster-outcome.json) when the run is on two nodes."""
        self.calls.append(argv)
        self.logs.append(log_path)
        if self.during_run and argv[0] == "run":
            self.during_run(argv)
        out = argv[argv.index("--out") + 1]
        os.makedirs(out, exist_ok=True)
        name = os.path.basename(out)
        if argv[0] == "perfcheck":
            counted = self.counted
            with open(os.path.join(out, "perfcheck-summary.json"), "w") as f:
                json.dump({"nodes": [{"node": n, "counted": counted} for n in self.NODES[:2]], "all_counted": counted, "text": "\n".join(f"{n}: {'instructions counted' if counted else 'NO instruction counts'}" for n in self.NODES[:2])}, f)
            return 0 if counted else campaign.EXIT_REFUSED if self.perf_exit is None else self.perf_exit
        if argv[0] == "calibrate":
            with open(os.path.join(out, "calibration.json"), "w") as f:
                json.dump({"pass": True, "nodes": [{"node": n, "pass": n in self.vouched, "noise": {"wall_ms": {"cv": 0.01 * (i + 1)}}} for i, n in enumerate(self.NODES)]}, f)
            for n in self.NODES:
                os.makedirs(os.path.join(out, n), exist_ok=True)
                with open(os.path.join(out, n, "cluster-facts.json"), "w") as f:
                    json.dump({"node": n, "cpuModel": self.models.get(n, "cpu-a")}, f)
            return self.exits.get(name, 0)
        nodes = argv[argv.index("--nodes") + 1].split(",") if "--nodes" in argv else ["node-1"]
        dirs = [out] if len(nodes) == 1 else [os.path.join(out, n) for n in nodes]
        for d, n in zip(dirs, nodes):
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "raw.json"), "w") as f:
                f.write("{}")
            with open(os.path.join(d, "cluster-facts.json"), "w") as f:
                json.dump({"node": n, "cpuModel": self.models.get(n, "cpu-a"), "cpuSet": "exclusive"}, f)
        if len(nodes) > 1:
            with open(os.path.join(out, "cluster-outcome.json"), "w") as f:
                json.dump({"outcomes": [{"node": n, "dir": n} for n in nodes]}, f)
        return self.exits.get(name, 0)

    def fake_reproduction(self, dirs, run_dir):
        self.compared.append((dirs, run_dir))
        return {"compared": True, "cells": 4, "reproduced": 3, "not_reproduced": 1}

    def fake_verify(self, dirs):
        family = lambda d: os.path.relpath(d, self.out).split(os.sep)[0]
        return {d: {"accepted": family(d) not in self.rejected, "errors": [] if family(d) not in self.rejected else ["seal: x"]} for d in dirs}

    def go(self, site=None, fake=None, **flags):
        args = argparse.Namespace(plan=self.plan, site=site or self.site(), out=self.out, bundle=None, wait_cluster=0, dry_run=False, parallel=False)
        for k, v in flags.items():
            setattr(args, k, v)
        lines = []
        fake = fake or FakeBackend()
        with mock.patch.object(backend, "get_backend", lambda s: fake), mock.patch.object(campaign, "verify", self.fake_verify), \
                mock.patch.object(campaign, "reproduction", self.fake_reproduction), redirect_stderr(io.StringIO()) as err:
            code = campaign.main(args, run=lambda argv, log_path=None: self.fake_run(argv, log_path), log=lines.append)
        self.err = err.getvalue()
        return code, lines

    def state(self):
        with open(os.path.join(self.out, campaign.STATE)) as f:
            return json.load(f)

    def test_the_calibration_runs_first_then_each_family_on_its_nodes(self):
        code, lines = self.go()
        self.assertEqual(code, 0)
        self.assertEqual([a[0] for a in self.calls], ["perfcheck", "calibrate", "run", "run"])
        cal = os.path.join(self.out, "calibrate", "calibration.json")
        self.assertEqual([a[a.index("--out") + 1] for a in self.calls], [os.path.join(self.out, n) for n in ("perfcheck", "calibrate", "ov", "st")])
        for a in self.calls[2:]:
            self.assertEqual(a[a.index("--calibration") + 1], cal)
            self.assertNotIn("--bundle", a)
        self.assertNotIn("--calibration", self.calls[0])
        self.assertNotIn("--calibration", self.calls[1])
        st = self.state()
        self.assertEqual({k: v["exit"] for k, v in st["steps"].items()}, {"perfcheck": 0, "calibrate": 0, "ov": 0, "st": 0})
        self.assertTrue(all(v["verify"][d]["accepted"] for k, v in st["steps"].items() if k not in ("calibrate", "perfcheck") for d in v["verify"]))
        self.assertIn("python3 -m buffon report", "\n".join(lines))

    def nodes_of(self):
        return {os.path.basename(a[a.index("--out") + 1]): a[a.index("--nodes") + 1].split(",") for a in self.calls if a[0] == "run"}

    def test_each_family_runs_on_a_node_pair_and_the_pair_is_compared(self):
        code, lines = self.go()
        self.assertEqual(code, 0)
        self.assertEqual(self.nodes_of(), {"ov": ["node-1", "node-2"], "st": ["node-1", "node-2"]}, "one at a time, each on its node and a reproduction node")
        self.assertEqual(self.logs, [None, None, None, None], "without --parallel every step runs in this process")
        self.assertEqual(self.compared, [([os.path.join(self.out, f, n) for n in ("node-1", "node-2")], os.path.join(self.out, f)) for f in ("ov", "st")])
        st = self.state()["steps"]["ov"]
        self.assertEqual(st["nodes"], ["node-1", "node-2"])
        self.assertEqual([(x["node"], x["cpu_model"], x["calibration"]) for x in st["sessions"]],
                         [("node-1", "cpu-a", {"pass": True, "noise": {"wall_ms": {"cv": 0.01}}}), ("node-2", "cpu-a", {"pass": True, "noise": {"wall_ms": {"cv": 0.02}}})])
        self.assertEqual(st["reproduction"]["reproduced"], 3)
        text = "\n".join(lines)
        for f in ("ov", "st"):
            for n in ("node-1", "node-2"):
                self.assertIn(f"python3 -m buffon report {os.path.join(self.out, f, n)}\n", text + "\n", "one report per node: no report pools two nodes")
            self.assertIn(os.path.join(self.out, f, "reproduction.md"), text)

    def test_the_reproduction_node_has_other_hardware_when_one_is_free(self):
        self.models = {"node-3": "cpu-b"}
        self.go()
        self.assertEqual(self.nodes_of()["ov"], ["node-1", "node-3"])

    def test_parallel_families_run_at_once_on_distinct_node_pairs(self):
        import threading
        both = threading.Barrier(2, timeout=10)   # each family waits here until the other one is running too: the two run at once
        self.during_run = lambda argv: both.wait()
        code, lines = self.go(parallel=True)
        self.assertEqual(code, 0)
        used = [n for pair in self.nodes_of().values() for n in pair]
        self.assertEqual(sorted(used), ["node-1", "node-2", "node-3", "node-4"], "no node holds two sessions; the noisy node-5 is never used")
        self.assertEqual(sorted(p for p in self.logs if p), [os.path.join(self.out, "ov.log"), os.path.join(self.out, "st.log")])
        self.assertIsNone(self.logs[0], "the calibration runs in this process")
        self.assertIn("2 families, up to 2 at once on 4 nodes", "\n".join(lines))

    def test_with_three_calibrated_nodes_parallel_families_take_turns(self):
        import threading
        self.vouched = ("node-1", "node-2", "node-3")
        running, peak, held, lock = [0], [0], set(), threading.Lock()

        def during(argv):
            nodes = set(argv[argv.index("--nodes") + 1].split(","))
            with lock:
                self.assertFalse(nodes & held, "a node lent to two sessions at once")
                held.update(nodes)
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            threading.Event().wait(0.05)   # widens the window in which a second session would overlap
            with lock:
                running[0] -= 1
                held.difference_update(nodes)
        self.during_run = during
        self.exits["ov"] = 4
        code, _ = self.go(parallel=True)
        self.assertEqual((code, peak[0]), (4, 1))
        self.exits.clear()
        self.calls.clear()
        self.assertEqual(self.go(parallel=True)[0], 0)
        self.assertEqual(list(self.nodes_of()), ["ov"], "a resume runs only the family that failed")

    def test_one_calibrated_node_runs_the_families_without_a_reproduction(self):
        self.vouched = ("node-2",)
        code, lines = self.go(parallel=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.nodes_of(), {"ov": ["node-2"], "st": ["node-2"]})
        self.assertEqual(self.compared, [])
        self.assertIn("no comparison can be a headline", "\n".join(lines))
        self.assertFalse(self.state()["steps"]["ov"]["reproduction"]["compared"])

    def test_the_node_pool_lends_a_pair_only_when_two_nodes_are_free(self):
        import threading
        pool = campaign.NodePool(["a", "b", "c"], {"c": "other"})
        first = pool.take()
        self.assertEqual(first, ["a", "c"], "the reproduction node has another CPU model")
        got, done = [], threading.Event()
        t = threading.Thread(target=lambda: (got.append(pool.take()), done.set()))
        t.start()
        self.assertFalse(done.wait(0.2), "one free node is not a pair: the second family waits")
        pool.give(first)
        self.assertTrue(done.wait(10))
        t.join()
        self.assertEqual(got, [["a", "c"]], "the pair comes back whole: the other-model node is preferred again")
        self.assertEqual(campaign.NodePool(["a"], {}).take(), ["a"], "one calibrated node: a family runs alone")

    def test_a_relative_site_path_reaches_every_step_as_an_absolute_path(self):
        """A --parallel family runs `python3 -m buffon` from the repository root, so a site path relative to the operator's directory must not reach it as given:
        there it would name another file, or resolve to sites/<name>.toml."""
        site = self.site()
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(os.path.dirname(site))
        code, _ = self.go(site=os.path.basename(site), parallel=True)
        self.assertEqual(code, 0)
        self.assertEqual({a[a.index("--site") + 1] for a in self.calls}, {site})

    def test_each_unfinished_attempt_is_kept_under_its_own_number_with_its_log(self):
        """Two failed parallel attempts that both wrote output: each is kept (attempt-1, attempt-2) with its own log, and the third attempt starts clean."""
        self.exits["ov"] = 1
        for _ in range(2):
            self.go(parallel=True)
            with open(os.path.join(self.out, "ov.log"), "a") as f:   # what run_buffon appends for a parallel family
                f.write("attempt output\n")
        self.exits.clear()
        self.assertEqual(self.go(parallel=True)[0], 0)
        for k in (1, 2):
            kept = os.path.join(self.out, f"ov.attempt-{k}")
            self.assertTrue(os.path.exists(os.path.join(kept, "node-1", "raw.json")), kept)
            self.assertTrue(os.path.exists(os.path.join(kept, "campaign.log")), "the attempt's own log is kept with it")
        self.assertFalse(os.path.exists(os.path.join(self.out, "ov.attempt-3")))
        self.assertEqual(self.state()["steps"]["ov"]["previous_attempt"], os.path.join(self.out, "ov.attempt-2"))

    def test_a_retried_family_is_judged_on_what_it_wrote_itself(self):
        self.exits["ov"] = 1
        self.go()
        first = os.path.join(self.out, "ov")
        self.assertTrue(os.path.exists(os.path.join(first, "node-1", "raw.json")))
        self.exits.clear()
        real = self.fake_run
        self.fake_run = lambda argv, log_path=None: 0 if argv[0] == "run" and os.path.basename(argv[argv.index("--out") + 1]) == "ov" else real(argv, log_path)   # dies before writing
        code, lines = self.go()
        self.assertEqual(code, 1, "the attempt before's node directories do not make this attempt verified")
        st = self.state()["steps"]["ov"]
        self.assertEqual((st["exit"], st["verify"]), (1, {}))
        self.assertEqual(st["previous_attempt"], os.path.join(self.out, "ov.attempt-1"))
        self.assertTrue(os.path.exists(os.path.join(self.out, "ov.attempt-1", "node-1", "raw.json")), "the earlier attempt is kept")
        self.fake_run = real
        self.assertEqual(self.go()[0], 0)
        self.assertFalse(os.path.exists(os.path.join(self.out, "ov.attempt-2")), "the attempt that wrote nothing left nothing to keep")
        self.assertEqual(self.state()["steps"]["ov"]["exit"], 0)

    def test_no_vouched_node_runs_no_family(self):
        self.vouched = ()
        code, _ = self.go(parallel=True)
        self.assertEqual((code, [a[0] for a in self.calls]), (campaign.EXIT_REFUSED, ["perfcheck", "calibrate"]))

    def test_a_campaign_resumes_where_it_stopped(self):
        self.exits["st"] = 1
        self.rejected.add("ov")
        code, _ = self.go()
        self.assertEqual(code, 1)
        st = self.state()["steps"]
        self.assertEqual((st["calibrate"]["exit"], st["ov"]["exit"], st["st"]["exit"]), (0, 1, 1), "a run that verify rejects did not finish")
        self.exits.clear()
        self.rejected.clear()
        self.calls.clear()
        code, lines = self.go()
        self.assertEqual(code, 0)
        self.assertEqual([os.path.basename(a[a.index("--out") + 1]) for a in self.calls], ["ov", "st"], "the calibration that passed is not run again")
        self.calls.clear()
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(self.calls, [])

    def test_a_failed_calibration_runs_no_family(self):
        self.exits["calibrate"] = 3
        code, _ = self.go()
        self.assertEqual(code, 3)
        self.assertEqual([a[0] for a in self.calls], ["perfcheck", "calibrate"])
        self.assertIn("the calibration did not pass", self.err)
        self.exits.clear()
        self.calls.clear()
        self.assertEqual(self.go()[0], 0)
        self.assertEqual([a[0] for a in self.calls], ["calibrate", "run", "run"], "a failed calibration is run again")

    def test_another_plan_in_the_same_directory_is_refused(self):
        self.go()
        with open(self.plan, "a") as f:
            f.write("rounds = 14\n")
        self.calls.clear()
        code, _ = self.go()
        self.assertEqual((code, self.calls), (2, []))
        self.assertIn("another plan", self.err)

    def test_the_campaign_waits_for_the_cluster(self):
        fake = FakeBackend([1, 1, 0])
        with mock.patch.object(campaign.time, "sleep") as sleep:
            code, lines = self.go(fake=fake, wait_cluster=600)
        self.assertEqual((code, fake.asked, sleep.call_count), (0, 3, 2))
        self.assertIn("does not answer yet (Unable to connect to the server)", lines[0])
        self.calls.clear()
        os.unlink(os.path.join(self.out, campaign.STATE))
        clock = iter([0, 0, 40, 80, 120])
        fake = FakeBackend([1])
        ok, answer = campaign.wait_for_cluster(fake, 100, lambda _: None, sleep=lambda _: None, now=lambda: next(clock))
        self.assertEqual((ok, answer, fake.asked), (False, "Unable to connect to the server", 4))

    def test_a_cluster_that_never_answers_runs_nothing(self):
        with mock.patch.object(campaign, "wait_for_cluster", return_value=(False, "Unable to connect")):
            code, _ = self.go(wait_cluster=60)
        self.assertEqual((code, self.calls), (3, []))
        self.assertIn("did not answer within 60 s", self.err)

    def test_the_perf_preflight_runs_first_through_the_site_and_the_bundle_and_is_recorded(self):
        builds, build = self.fake_build()
        with mock.patch.object(bundlelib, "build", build):
            code, lines = self.go(site=self.site(bundle_mode=True))
        self.assertEqual(code, 0)
        argv = self.calls[0]
        self.assertEqual(argv[0], "perfcheck")
        self.assertEqual(argv[argv.index("--out") + 1], os.path.join(self.out, "perfcheck"))
        self.assertEqual(argv[argv.index("--bundle") + 1], os.path.join(self.out, "bundle"))
        step = self.state()["steps"]["perfcheck"]
        self.assertTrue(step["perfcheck"]["all_counted"])
        self.assertTrue(any("node-1: instructions counted" in ln for ln in lines))

    def test_a_node_that_cannot_count_instructions_is_reported_and_the_campaign_continues(self):
        self.counted = False
        code, lines = self.go()
        self.assertEqual(code, 0)
        self.assertEqual([a[0] for a in self.calls][:3], ["perfcheck", "calibrate", "run"])
        self.assertTrue(any("NO instruction counts" in ln for ln in lines))
        self.assertTrue(any("headlines CPU time" in ln for ln in lines))
        state = self.state()
        self.assertEqual(state["steps"]["perfcheck"]["exit"], campaign.EXIT_REFUSED)
        self.assertFalse(state["steps"]["perfcheck"]["perfcheck"]["all_counted"])

    def test_a_resumed_campaign_runs_the_preflight_again_in_place_and_keeps_no_attempt_directory(self):
        self.counted = False
        self.go()
        self.go()
        self.assertEqual([a[0] for a in self.calls].count("perfcheck"), 2)
        self.assertFalse(os.path.exists(os.path.join(self.out, "perfcheck.attempt-1")))

    def test_a_preflight_that_could_not_run_a_pod_stops_the_campaign_before_the_calibration(self):
        self.perf_exit, self.counted = 1, False
        code, _ = self.go()
        self.assertEqual(code, 1)
        self.assertEqual([a[0] for a in self.calls], ["perfcheck"])

    def test_a_dry_run_prints_the_steps_and_runs_nothing(self):
        fake = FakeBackend()
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        with open(os.path.join(home, "probe.json"), "w") as f:
            json.dump({"speed": 1.0}, f)   # a fresh speed probe: the dry run's estimate spawns nothing and writes nothing outside this directory
        with mock.patch.dict(os.environ, {"BUFFON_HOME": home}):
            code, lines = self.go(fake=fake, dry_run=True)
            self.assertEqual((code, self.calls, fake.asked), (0, [], 0))
            steps = [ln for ln in lines if " step " in ln]
            self.assertEqual([ln.split()[3] for ln in steps], ["perfcheck:", "calibrate:", "ov:", "st:"])
            self.assertTrue(any("expected measuring time, all families" in ln for ln in lines))   # the estimate comes after the steps
            code, lines = self.go(site=self.site(bundle_mode=True), dry_run=True)
        self.assertIn("would build the bundle for linux-amd64 with pi-node, pig-0.4.1", lines[0])
        self.assertTrue(all("--bundle " + os.path.join(self.out, "bundle") in ln for ln in lines[1:] if " step " in ln))
        self.assertFalse(os.path.exists(os.path.join(self.out, "bundle")))

    def fake_build(self, skipped=None):
        builds = []

        def build(out_dir, arch, arm_ids=None, host_cache="", **_):
            builds.append(arm_ids)
            os.makedirs(out_dir)
            meta = {"arch": arch, "platform": "linux-x64", "arms": list(arm_ids), "skipped": skipped or {}, "commit": "c" * 40, "tree": "t" * 40}
            with open(os.path.join(out_dir, "bundle.json"), "w") as f:
                json.dump(meta, f)
            bundlelib.write_sums(out_dir)
            return dict(meta, files=1)
        return builds, build

    def test_a_bundle_site_builds_the_bundle_once_and_every_step_runs_from_it(self):
        builds, build = self.fake_build()
        with mock.patch.object(bundlelib, "build", build):
            code, _ = self.go(site=self.site(bundle_mode=True))
            self.assertEqual(code, 0)
            bundle_dir = os.path.join(self.out, "bundle")
            self.assertEqual(builds, [["pi-node", "pig-0.4.1"]])
            self.assertTrue(all(a[a.index("--bundle") + 1] == bundle_dir for a in self.calls))
            st = self.state()
            self.assertEqual((st["bundle"]["dir"], st["bundle"]["commit"], st["bundle"]["arms"]), (bundle_dir, "c" * 40, ["pi-node", "pig-0.4.1"]))
            with open(os.path.join(bundle_dir, "ARTIFACTS.sha256"), "rb") as f:
                self.assertEqual(st["bundle"]["artifacts_sha256"], __import__("hashlib").sha256(f.read()).hexdigest())
            self.go(site=self.site(bundle_mode=True))
            self.assertEqual(len(builds), 1, "a resumed campaign reuses its bundle")

    def test_a_resume_from_another_bundle_is_refused(self):
        """The finished steps ran from the campaign's bundle; resuming from another one would mix runner commits and arm builds in one campaign."""
        builds, build = self.fake_build()
        self.exits["st"] = 1
        with mock.patch.object(bundlelib, "build", build):
            self.assertEqual(self.go(site=self.site(bundle_mode=True))[0], 1)
        other = os.path.join(self.tmp, "other")
        build(other, "amd64", ["pi-node", "pig-0.4.1"])
        with open(os.path.join(other, "README.md"), "w") as f:
            f.write("another checkout")
        bundlelib.write_sums(other)
        self.exits.clear()
        self.calls.clear()
        code, _ = self.go(site=self.site(bundle_mode=True), bundle=other)
        self.assertEqual((code, self.calls), (2, []))
        self.assertIn("resume with that bundle", self.err)
        self.assertEqual(self.state()["bundle"]["dir"], os.path.join(self.out, "bundle"))
        code, _ = self.go(site=self.site(bundle_mode=True), bundle=os.path.join(self.out, "bundle"))
        self.assertEqual(code, 0)
        self.assertEqual([os.path.basename(a[a.index("--out") + 1]) for a in self.calls], ["st"])

    def test_a_bundle_that_cannot_carry_the_plan_is_refused_before_any_pod(self):
        builds, build = self.fake_build(skipped={"pig-0.4.1": "no pinned artifact"})
        with mock.patch.object(bundlelib, "build", build), self.assertRaisesRegex(BackendError, "pig-0.4.1: no pinned artifact"):
            self.go(site=self.site(bundle_mode=True))
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "bundle")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "bundle.part")))
        given = os.path.join(self.tmp, "given")
        _, build = self.fake_build()
        build(given, "amd64", ["pi-node"])
        with self.assertRaisesRegex(BackendError, "does not carry pig-0.4.1"):
            self.go(site=self.site(bundle_mode=True), bundle=given)
        self.assertEqual(self.calls, [])

    def local_site(self):
        path = os.path.join(self.tmp, "local.toml")
        with open(path, "w") as f:
            f.write('[site]\nbackend = "local"\n[local]\ncpus = "1-3"\nmock_cpus = "0"\n')
        return path

    def local_bundle(self, arms=("pi-node", "pig-0.4.1")):
        given = os.path.join(self.tmp, "lb")
        _, build = self.fake_build()
        build(given, "amd64", list(arms))
        return given

    def test_a_local_site_runs_the_perf_check_then_each_family_one_after_the_other_without_a_calibration_or_a_node_pair(self):
        bundle = self.local_bundle()
        code, lines = self.go(site=self.local_site(), bundle=bundle, wait_cluster=900)
        self.assertEqual(code, 0)
        self.assertEqual([a[0] for a in self.calls], ["perfcheck", "run", "run"])
        for a in self.calls[1:]:
            self.assertNotIn("--nodes", a)
            self.assertNotIn("--bundle", a)
            self.assertNotIn("--calibration", a)
            self.assertEqual(a[a.index("--cache-dir") + 1], os.path.join(bundle, "cache"))
            self.assertEqual(a[a.index("--npm-cache") + 1], os.path.join(bundle, "npm-cache"))
            self.assertIn("--offline", a)
        st = self.state()
        self.assertEqual(sorted(st["steps"]), ["ov", "perfcheck", "st"])
        self.assertTrue(all(st["steps"][f]["verify"] for f in ("ov", "st")))
        self.assertTrue(any("render ov with: python3 -m buffon report" in ln for ln in lines))

    def test_every_command_line_a_campaign_issues_parses_with_the_real_buffon_parser(self):
        """The first real VPS run failed: `buffon run` rejected --offline --cache-dir --npm-cache, which the recording fake accepted without parsing."""
        from buffon import cli
        bundle = self.local_bundle()
        self.go(site=self.local_site(), bundle=bundle)
        self.assertTrue(self.calls)
        for argv in self.calls:
            parsed = cli.build_parser().parse_args(argv)      # SystemExit on an unrecognised argument
            if argv[0] == "run":
                self.assertTrue(parsed.offline)
                self.assertEqual((parsed.cache_dir, parsed.npm_cache), (os.path.join(bundle, "cache"), os.path.join(bundle, "npm-cache")))
        self.calls.clear()
        builds, build = self.fake_build()
        with mock.patch.object(bundlelib, "build", build):
            self.go(site=self.site(bundle_mode=True))
        for argv in self.calls:
            cli.build_parser().parse_args(argv)

    def test_a_local_campaign_asks_the_cluster_nothing_and_a_failed_family_does_not_stop_the_next(self):
        fake = FakeBackend()
        self.exits = {"ov": 1}
        code, _ = self.go(site=self.local_site(), bundle=self.local_bundle(), wait_cluster=900, fake=fake)
        self.assertEqual((fake.asked, code), (0, 1))
        self.assertEqual([os.path.basename(a[a.index("--out") + 1]) for a in self.calls], ["perfcheck", "ov", "st"])

    def test_a_local_bundle_that_lacks_a_planned_arm_or_is_not_a_bundle_is_refused_before_anything_runs(self):
        code, _ = self.go(site=self.local_site(), bundle=self.local_bundle(arms=("pi-node",)))
        self.assertEqual((code, self.calls), (2, []))
        self.assertIn("does not carry pig-0.4.1", self.err)
        code, _ = self.go(site=self.local_site(), bundle=os.path.join(self.tmp, "nope"))
        self.assertEqual((code, self.calls), (2, []))
        self.assertIn("is not a finished bundle", self.err)

    def test_a_local_site_without_a_bundle_runs_as_the_site_says(self):
        code, _ = self.go(site=self.local_site())
        self.assertEqual(code, 0)
        for a in self.calls[1:]:
            self.assertNotIn("--offline", a)

    def test_a_local_dry_run_lists_the_steps_without_a_calibration(self):
        code, lines = self.go(site=self.local_site(), dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual([ln.split()[3] for ln in lines if ln.split()[2] in ("step", "done")], ["perfcheck:", "ov:", "st:"])


class CommandLine(unittest.TestCase):
    def test_the_campaign_command_is_wired(self):
        from buffon import cli
        args = cli.build_parser().parse_args(["campaign", QUIET, "--out", "/x", "--wait-cluster", "900", "--dry-run"])
        self.assertEqual((args.plan, args.wait_cluster, args.dry_run, cli.COMMANDS[args.cmd]), (QUIET, 900.0, True, cli.cmd_campaign))


if __name__ == "__main__":
    unittest.main()
