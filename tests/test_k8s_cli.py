# SPDX-License-Identifier: Apache-2.0
"""`buffon calibrate` and `buffon run --calibration` on the Kubernetes backend, with buffon-cluster replaced by the recording fake of tests/test_backend_k8s.py."""
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from buffon import backend, cli
from buffon.backend import k8s
from tests.test_backend_k8s import FakeCluster

PROFILE = '[site]\nbackend = "{backend}"\n[kubernetes]\nnamespace = "buffon"\nimage = "registry.example/buffon@sha256:{digest}"\nmax_cv = 0.04\n{extra}'


class KubernetesCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def site(self, extra="spread = 2\n", backend_name="kubernetes"):
        path = os.path.join(self.tmp, "site.toml")
        with open(path, "w") as f:
            f.write(PROFILE.format(backend=backend_name, digest="a" * 64, extra=extra))
        return path

    def cli(self, argv, fake):
        made = []

        def get_backend(s):
            made.append(k8s.K8sBackend(s, runner=fake, env={"BUFFON_CLUSTER_BIN": "/opt/buffon-cluster", "PATH": "/usr/bin"}, now=0))
            return made[-1]

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(backend, "get_backend", get_backend), redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def runs(self, fake):
        return [c for c in fake.calls if c.command == "run"]

    def tool(self, fake, command):
        return [c.argv[1:] for c in fake.calls if c.command == command]

    def calibration(self, nodes):
        path = os.path.join(self.tmp, "calibration.json")
        with open(path, "w") as f:
            json.dump({"maxCv": 0.04, "pass": all(p for _, p in nodes), "nodes": [{"node": n, "pass": p} for n, p in nodes]}, f)
        return path

    # -- buffon calibrate ---------------------------------------------------------------------------------------------------------------------

    def test_calibrate_runs_the_reference_against_its_copy_on_the_sites_nodes_and_judges_them(self):
        fake = FakeCluster()
        out = os.path.join(self.tmp, "cal")
        code, stdout, _ = self.cli(["calibrate", "overhead/print", "--site", self.site(), "--reference", "pi-node", "--out", out], fake)
        self.assertEqual(code, 0, stdout)
        argv = self.runs(fake)[0].session["argv"]
        self.assertEqual(argv[argv.index("--arms") + 1:argv.index("--arms") + 2], ["pi-node"])
        self.assertEqual(argv[argv.index("--aa") + 1], "pi-node")
        self.assertIn("--no-calibrate", argv)
        self.assertEqual(self.runs(fake)[0].argv[self.runs(fake)[0].argv.index("-spread") + 1], "2")
        self.assertEqual(self.tool(fake, "calibrate"), [["calibrate", "-max-cv", "0.04", "-o", os.path.join(out, "calibration.json"), os.path.join(out, "node-1"), os.path.join(out, "node-2")]])
        self.assertIn("--calibration", stdout)

    def test_the_sites_allow_frequency_scaling_reaches_the_calibration_and_every_run_session(self):
        for command, extra in (("calibrate", []), ("run", ["--calibration", self.calibration([("node-1", True), ("node-2", True)])])):
            for flag, want in (("allow_frequency_scaling = true\n", True), ("", False)):
                fake = FakeCluster()
                out = os.path.join(self.tmp, "out-" + command + str(want))
                self.cli([command, "overhead/print", "--site", self.site("spread = 2\n" + flag), "--out", out, *extra], fake)
                argv = self.runs(fake)[0].session["argv"]
                self.assertEqual("--allow-frequency-scaling" in argv, want, (command, flag))

    def test_an_operators_flag_is_not_repeated_when_the_site_says_it_too(self):
        fake = FakeCluster()
        self.cli(["calibrate", "--site", self.site("spread = 2\nallow_frequency_scaling = true\n"), "--allow-frequency-scaling", "--out", os.path.join(self.tmp, "cal2")], fake)
        self.assertEqual(self.runs(fake)[0].session["argv"].count("--allow-frequency-scaling"), 1)

    def test_a_noisy_calibration_is_refused(self):
        code, _, err = self.cli(["calibrate", "--site", self.site(), "--out", os.path.join(self.tmp, "cal")], FakeCluster(tool_exit=3))
        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("exceeds max_cv 0.04", err)

    def test_calibrate_on_one_node_judges_the_run_directory_itself(self):
        fake = FakeCluster()
        out = os.path.join(self.tmp, "cal")
        self.assertEqual(self.cli(["calibrate", "--site", self.site(extra=""), "--out", out], fake)[0], 0)
        self.assertEqual(self.tool(fake, "calibrate")[0][5:], [out])

    def test_calibrate_refuses_a_local_site_and_another_arm(self):
        code, _, err = self.cli(["calibrate", "--site", self.site(backend_name="local", extra="")], FakeCluster())
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("judges Kubernetes nodes", err)
        fake = FakeCluster()
        code, _, err = self.cli(["calibrate", "--site", self.site(), "--arms", "pig-0.4.1"], fake)
        self.assertEqual((code, fake.calls), (cli.EXIT_USAGE, []))
        self.assertIn("--reference", err)

    def test_a_failed_session_with_nothing_handed_back_is_not_judged(self):
        fake = FakeCluster(exit_code=1, hand_back=False)
        code, _, err = self.cli(["calibrate", "--site", self.site(extra=""), "--out", os.path.join(self.tmp, "cal")], fake)
        self.assertEqual(code, 1)
        self.assertEqual(self.tool(fake, "calibrate"), [])
        self.assertIn("no node handed back", err)

    # -- buffon run --calibration -------------------------------------------------------------------------------------------------------------

    def test_a_comparison_runs_on_the_nodes_the_calibration_vouches_for(self):
        fake = FakeCluster()
        cal = self.calibration([("node-a", True), ("node-b", False), ("node-c", True)])
        out = os.path.join(self.tmp, "run")
        code, stdout, err = self.cli(["run", "overhead/print", "--site", self.site(), "--calibration", cal, "--out", out], fake)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tool(fake, "check"), [["check", "-calibration", cal, "-nodes", "node-a,node-c"]])
        run = self.runs(fake)[0]
        self.assertEqual(run.argv[run.argv.index("-nodes") + 1], "node-a,node-c")
        self.assertNotIn("-spread", run.argv)
        self.assertIn("does not vouch for node-b", err)
        self.assertIn(f"python3 -m buffon report {os.path.join(out, 'node-a')} {os.path.join(out, 'node-c')}", stdout)

    def test_a_comparison_the_calibration_does_not_vouch_for_starts_no_pod(self):
        fake = FakeCluster(tool_exit=3)
        code, _, err = self.cli(["run", "--site", self.site(), "--calibration", self.calibration([("node-a", True)])], fake)
        self.assertEqual((code, self.runs(fake)), (cli.EXIT_REFUSED, []))
        self.assertIn("does not vouch", err)
        fake = FakeCluster()
        code, _, _ = self.cli(["run", "--site", self.site(), "--calibration", self.calibration([("node-a", False)])], fake)
        self.assertEqual((code, fake.calls), (cli.EXIT_REFUSED, [c for c in fake.calls if c.command == "render"]))
        code, _, err = self.cli(["run", "--site", self.site(backend_name="local", extra=""), "--calibration", self.calibration([("node-a", True)])], FakeCluster())
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("runs locally", err)

    def test_nodes_picks_among_the_calibrated_nodes(self):
        fake = FakeCluster()
        cal = self.calibration([("node-a", True), ("node-b", False), ("node-c", True)])
        out = os.path.join(self.tmp, "run")
        code, _, err = self.cli(["run", "overhead/print", "--site", self.site(), "--calibration", cal, "--nodes", "node-c", "--out", out], fake)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.tool(fake, "check"), [["check", "-calibration", cal, "-nodes", "node-c"]])
        run = self.runs(fake)[0]
        self.assertEqual(run.argv[run.argv.index("-nodes") + 1], "node-c")
        for nodes in ("node-b", "node-x", "node-a,node-x", ","):
            with self.subTest(nodes):
                fake = FakeCluster()
                code, _, err = self.cli(["run", "--site", self.site(), "--calibration", cal, "--nodes", nodes, "--out", out], fake)
                self.assertEqual((code, self.runs(fake), self.tool(fake, "check")), (cli.EXIT_REFUSED, [], []))
                self.assertIn("does not vouch for", err)
        fake = FakeCluster()
        code, _, err = self.cli(["run", "--site", self.site(), "--calibration", cal, "--nodes", "node-a,node-a", "--out", out], fake)
        self.assertEqual((code, self.runs(fake), self.tool(fake, "check")), (cli.EXIT_USAGE, [], []))
        self.assertIn("names node-a twice: one session per node", err)
        code, _, err = self.cli(["run", "--site", self.site(), "--nodes", "node-a", "--out", out], FakeCluster())
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertIn("give --calibration too", err)

    def test_a_calibration_without_named_nodes_is_refused_before_any_pod(self):
        for doc in ({}, {"nodes": []}, {"nodes": [{"pass": True}]}, {"nodes": [{"node": "", "pass": True}]}):
            path = os.path.join(self.tmp, "calibration.json")
            with open(path, "w") as f:
                json.dump(doc, f)
            fake = FakeCluster()
            code, _, err = self.cli(["run", "--site", self.site(), "--calibration", path], fake)
            self.assertEqual((code, self.runs(fake), self.tool(fake, "check")), (cli.EXIT_USAGE, [], []), doc)
            self.assertIn("names no calibrated nodes", err)

    def test_a_spread_run_reports_every_node(self):
        fake = FakeCluster(node_exits={"node-2": 3})
        out = os.path.join(self.tmp, "run")
        code, stdout, _ = self.cli(["run", "--site", self.site(), "--out", out], fake)
        self.assertEqual(code, 3)
        self.assertIn("node node-1: exit 0", stdout)
        self.assertIn("node node-2: exit 3", stdout)
        self.assertIn(f"report {os.path.join(out, 'node-1')} {os.path.join(out, 'node-2')}", stdout)


if __name__ == "__main__":
    unittest.main()
