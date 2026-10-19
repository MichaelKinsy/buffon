# SPDX-License-Identifier: Apache-2.0
"""`buffon run` on the Kubernetes backend end to end against a fake cluster (tests/fake_cluster.py): the CLI loads a Kubernetes profile, the backend renders and "runs" the session,
the session really measures arms locally, the run directory comes back, and the report renders. Runs real arms, so it needs the pinned artifacts (network or a warm cache) and takes
minutes: it runs only when BUFFON_E2E_CPUS names at least 3 CPUs, for example BUFFON_E2E_CPUS=150,151,152,153."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPUS = os.environ.get("BUFFON_E2E_CPUS", "")

PROFILE = """[site]
name = "fake-pool"
backend = "kubernetes"
hardware = "shared"

[kubernetes]
namespace = "buffon-test"
image = "registry.example/buffon@sha256:{digest}"
cpus = {cpus}
memory = "8Gi"
scratch_size = "8Gi"
pin = "auto"
"""


@unittest.skipUnless(len([c for c in CPUS.split(",") if c]) >= 3, "set BUFFON_E2E_CPUS=<3 or more CPUs> to run the fake-cluster end-to-end test")
class FakeClusterEndToEnd(unittest.TestCase):
    def test_run_report_through_the_kubernetes_backend(self):
        tmp = tempfile.mkdtemp()
        profile = os.path.join(tmp, "fake-pool.toml")
        n = len([c for c in CPUS.split(",") if c])
        with open(profile, "w") as f:
            f.write(PROFILE.format(digest="0" * 64, cpus=n))
        out = os.path.join(tmp, "run")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BUFFON_K8S_", "BUFFON_SITE"))}
        env.update(BUFFON_CLUSTER_BIN=os.path.join(ROOT, "tests", "fake_cluster.py"), BUFFON_FAKE_CLUSTER_CPUS=CPUS)
        done = subprocess.run([sys.executable, "-m", "buffon", "run", "overhead/version", "overhead/print", "--arms", "pi-node", "pig-0.4.1", "--site", profile, "--allow-noisy", "--out", out],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=1500)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
        for name in ("raw.json", "facts.json", "cluster-facts.json", "node.json", "cluster-outcome.json"):
            self.assertTrue(os.path.exists(os.path.join(out, name)), name)
        with open(os.path.join(out, "raw.json")) as f:
            raw = json.load(f)
        self.assertEqual(raw["run"]["rounds"], 12)
        self.assertEqual(raw["site"]["backend"], "kubernetes")
        self.assertEqual(sorted({s["arm"] for s in raw["samples"]}), ["pi-node", "pi-node-b", "pig-0.4.1", "pig-0.4.1-b"])
        self.assertEqual(raw["hardware"]["class"], "provisional")
        self.assertTrue(os.path.isdir(os.path.join(out, "mock-requests")))
        report = subprocess.run([sys.executable, "-m", "buffon", "report", out], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(report.returncode, 0, report.stderr)
        with open(os.path.join(out, "report.md")) as f:
            text = f.read()
        self.assertTrue(text.splitlines()[0].endswith("PROVISIONAL"))
        self.assertIn("## pig-0.4.1 against pi-node", text)


if __name__ == "__main__":
    unittest.main()


CAMPAIGN_CPUS = os.environ.get("BUFFON_E2E_CAMPAIGN_CPUS", "")
CLUSTER_BIN = os.environ.get("BUFFON_E2E_CLUSTER_BIN", "")
PLAN = """[campaign]
name = "e2e"
[calibrate]
workloads = ["overhead/version"]
rounds = 12
[[family]]
name = "ov"
workloads = ["overhead/version"]
arms = ["pi-node", "pig-0.4.1"]
[[family]]
name = "pr"
workloads = ["overhead/print"]
arms = ["pi-node", "pig-0.4.1"]
"""


@unittest.skipUnless(CAMPAIGN_CPUS.count("=") >= 4 and CLUSTER_BIN, "set BUFFON_E2E_CAMPAIGN_CPUS='node-1=a,b,c;node-2=...;node-3=...;node-4=...' (4 fake nodes, 3 CPUs each) "
                     "and BUFFON_E2E_CLUSTER_BIN=<built buffon-cluster> to run the fake-cluster campaign")
class FakeClusterCampaign(unittest.TestCase):
    def test_a_parallel_campaign_runs_each_family_on_its_own_node_pair_and_compares_the_pair(self):
        tmp = tempfile.mkdtemp()
        nodes = [part.split("=", 1)[0] for part in CAMPAIGN_CPUS.split(";") if part]
        with open(os.path.join(tmp, "plan.toml"), "w") as f:
            f.write(PLAN)
        with open(os.path.join(tmp, "site.toml"), "w") as f:
            # max_cv 0.9: this host is not a quiet node, the calibration must still vouch for every node so that the pairs are scheduled.
            f.write(PROFILE.format(digest="0" * 64, cpus=3).replace("pin = \"auto\"\n", f"pin = \"auto\"\nmax_cv = 0.9\nspread = {len(nodes)}\n"))
        out = os.path.join(tmp, "c")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BUFFON_K8S_", "BUFFON_SITE"))}
        env.update(BUFFON_CLUSTER_BIN=os.path.join(ROOT, "tests", "fake_cluster.py"), BUFFON_FAKE_CLUSTER_REAL=CLUSTER_BIN, BUFFON_FAKE_CLUSTER_NODES=",".join(nodes),
                   BUFFON_FAKE_CLUSTER_CPUS=CAMPAIGN_CPUS, BUFFON_FAKE_CLUSTER_SESSION_ARGS="--quiet-max-busy 0.9 --quiet-max-runnable 64 --quiet-max-psi 100 --quiet-timeout 20 --allow-noisy")   # a busy host fails a session's own calibration gate
        done = subprocess.run([sys.executable, "-m", "buffon", "campaign", os.path.join(tmp, "plan.toml"), "--site", os.path.join(tmp, "site.toml"), "--out", out, "--parallel"],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=3000)
        with open(os.path.join(out, "campaign.json")) as f:
            steps = json.load(f)["steps"]
        self.assertEqual(steps["calibrate"]["exit"], 0, done.stdout[-3000:] + done.stderr[-3000:])
        pairs = [steps[fam]["nodes"] for fam in ("ov", "pr")]
        self.assertEqual(sorted(n for p in pairs for n in p), sorted(nodes), "two families, four distinct nodes")
        a, b = steps["ov"], steps["pr"]
        self.assertTrue(a["started_utc"] < b["finished_utc"] and b["started_utc"] < a["finished_utc"], "the two families ran at the same time")
        for fam, pair in zip(("ov", "pr"), pairs):
            st = steps[fam]
            self.assertEqual([s["node"] for s in st["sessions"]], pair)
            self.assertTrue(all(s["calibration"]["noise"] for s in st["sessions"]), "each session carries its node's own calibration")
            self.assertTrue(st["reproduction"]["compared"], st["reproduction"])
            self.assertGreater(st["reproduction"]["cells"], 0)
            self.assertTrue(os.path.exists(os.path.join(out, fam, "reproduction.md")))
            for n in pair:
                with open(os.path.join(out, fam, n, "facts.json")) as f:
                    self.assertEqual(json.load(f)["node"], n)
                with open(os.path.join(out, fam, n, "raw.json")) as f:
                    self.assertEqual(sorted({s["arm"] for s in json.load(f)["samples"]}), ["pi-node", "pi-node-b", "pig-0.4.1", "pig-0.4.1-b"], "every arm and A/A copy on each node")
                self.assertIn(f"python3 -m buffon report {os.path.join(out, fam, n)}\n", done.stdout + "\n")
