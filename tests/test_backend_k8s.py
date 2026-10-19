# SPDX-License-Identifier: Apache-2.0
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

from buffon import backend, site
from buffon.backend import k8s

DIGEST = "@sha256:" + "a" * 64


def kube_site(**kube):
    data = {"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "buffon", "image": "registry.example/buffon" + DIGEST, "cpus": 2}}
    data["kubernetes"].update(kube)
    return site.from_dict(data, env={})


class FakeCluster:
    """Stands in for buffon-cluster: records each call, and for `run` writes what a pod would hand back. With -nodes or -spread choosing more than one node it lays the
    results out as cluster/main.go runCluster and cluster/run.go runSpread do: <out>/<run>/<run>-n<i>/ per node, <out>/<run>/spread.json, and <out>/<run>-nodes.json for a pick.
    `calibrate` and `check` answer with tool_exit."""

    def __init__(self, exit_code=0, session_exit=0, hand_back=True, node_exits=None, tool_exit=0, node_names=None):
        self.calls, self.exit_code, self.session_exit, self.hand_back = [], exit_code, session_exit, hand_back
        self.node_exits, self.tool_exit, self.node_names = node_exits or {}, tool_exit, node_names

    def hand_back_to(self, back, node, session_exit):
        os.makedirs(os.path.join(back, "logs"))
        for name, body in {
            "raw.json": {"samples": {}},
            "facts.json": {"node": node},
            "cluster-facts.json": {"node": node, "cpuSet": "exclusive", "pin": {"cpus": "4,5", "fixedClock": True}, "session": {"exit": session_exit, "throttledUsec": 12}},
            "node.json": {"node": node, "cpuManagerPolicy": "static"},
        }.items():
            with open(os.path.join(back, name), "w") as f:
                json.dump(body, f)

    def __call__(self, argv, env, capture_output, text):
        if argv[1] in ("calibrate", "check"):
            self.calls.append(types.SimpleNamespace(command=argv[1], argv=argv, env=env))
            return types.SimpleNamespace(returncode=self.tool_exit, stdout=f"{argv[1]} verdict\n", stderr="")
        args = dict(zip(argv[2::2], argv[3::2]))
        with open(args["-site"]) as f:
            st = json.load(f)
        with open(args["-session"]) as f:
            spec = json.load(f)
        self.calls.append(types.SimpleNamespace(command=argv[1], argv=argv, site=st, session=spec, env=env))
        if argv[1] != "run":
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        listed = args["-nodes"].split(",") if "-nodes" in args else []
        spread = int(args.get("-spread", 0))
        nodes = (listed or [f"node-{i + 1}" for i in range(max(spread, 1))])[:spread or None] if (listed or spread) else ["node-a"]
        if spread:
            os.makedirs(args["-out"], exist_ok=True)
            with open(os.path.join(args["-out"], spec["run"] + "-nodes.json"), "w") as f:
                json.dump([{"node": n, "freeMilliCpu": 4000} for n in nodes], f)
        if len(nodes) == 1:
            back = os.path.join(args["-out"], spec["run"])
            if self.hand_back:
                self.hand_back_to(back, nodes[0], self.session_exit)
            out = [{"run": spec["run"], "node": nodes[0], "ok": self.exit_code == 0}]
            return types.SimpleNamespace(returncode=self.exit_code, stdout=json.dumps(out), stderr="buffon-cluster: progress\n")
        out = []
        for i, node in enumerate(nodes):
            run = f"{spec['run']}-n{i + 1}"
            reported = (self.node_names or {}).get(node, node)
            self.hand_back_to(os.path.join(args["-out"], spec["run"], run), reported, self.node_exits.get(node, 0))
            out.append({"run": run, "node": reported, "runDir": os.path.join(args["-out"], spec["run"], run), "ok": not self.node_exits.get(node)})
        with open(os.path.join(args["-out"], spec["run"], "spread.json"), "w") as f:
            json.dump({"run": spec["run"], "nodes": nodes, "sessions": out}, f)
        code = 1 if any(self.node_exits.values()) else 0
        return types.SimpleNamespace(returncode=code, stdout=json.dumps(out), stderr="buffon-cluster: progress\n")


class K8sBackendTests(unittest.TestCase):
    def setUp(self):
        self.env = {"BUFFON_CLUSTER_BIN": "/opt/buffon-cluster", "BUFFON_K8S_NAMESPACE": "leaks", "PATH": "/usr/bin"}

    def test_factory_selects_the_kubernetes_backend(self):
        self.assertIsInstance(backend.get_backend(kube_site()), k8s.K8sBackend)

    def test_run_translates_the_session_and_brings_the_run_directory_back(self):
        fake = FakeCluster()
        run_dir = os.path.join(tempfile.mkdtemp(), "pod-run")
        b = k8s.K8sBackend(kube_site(node_selector={"pool": "bench"}, pin="auto"), runner=fake, env=self.env, now=0)
        session = backend.Session(argv=["python3", "-m", "buffon", "session", "--out", run_dir, "--seed=1"], run_dir=run_dir, deadline_s=600, env={"BUFFON_SEED": "1"})
        result = b.run(session)
        call = fake.calls[0]
        self.assertEqual(call.command, "run")
        self.assertEqual(call.session["argv"], ["python3", "-m", "buffon", "session", "--out", "{out}", "--seed=1"])
        self.assertEqual(call.session["run"], "buffon-pod-run-19700101t000000")
        self.assertEqual((call.session["cpus"], call.session["pin"], call.session["timeoutSeconds"], call.session["env"]), (2, "auto", 600, {"BUFFON_SEED": "1"}))
        self.assertEqual(call.site["image"], "registry.example/buffon" + DIGEST)
        self.assertEqual(call.site["nodeSelector"], {"pool": "bench"})
        self.assertNotIn("BUFFON_K8S_NAMESPACE", call.env, "the profile, not a stray environment variable, decides the cluster values")
        for name in ("raw.json", "facts.json", "cluster-facts.json", "node.json", "logs", "cluster-outcome.json"):
            self.assertTrue(os.path.exists(os.path.join(run_dir, name)), name)
        self.assertEqual((result.exit_code, result.pinned_cpus, result.throttled_usec), (0, [4, 5], 12))
        self.assertEqual(result.facts["cluster"]["cpuSet"], "exclusive")
        self.assertEqual(result.facts["node_api"]["cpuManagerPolicy"], "static")

    def test_a_failed_session_still_returns_its_facts_and_exit(self):
        fake = FakeCluster(exit_code=1, session_exit=3)
        run_dir = tempfile.mkdtemp()
        result = k8s.K8sBackend(kube_site(), runner=fake, env=self.env).run(backend.Session(argv=["buffon", run_dir], run_dir=run_dir))
        self.assertEqual(result.exit_code, 3)
        self.assertTrue(os.path.exists(os.path.join(run_dir, "raw.json")))
        fake = FakeCluster(exit_code=1, hand_back=False)
        result = k8s.K8sBackend(kube_site(), runner=fake, env=self.env).run(backend.Session(argv=["buffon", run_dir + "/x"], run_dir=run_dir + "/x"))
        self.assertEqual((result.exit_code, result.facts["cluster"]), (1, {}))

    def test_the_runners_interpreter_path_becomes_the_pods_python3(self):
        fake = FakeCluster()
        run_dir = tempfile.mkdtemp()
        k8s.K8sBackend(kube_site(), runner=fake, env=self.env).run(backend.Session(argv=["/opt/homebrew/bin/python3.12", "-m", "buffon", "session", "--out", run_dir], run_dir=run_dir))
        self.assertEqual(fake.calls[0].session["argv"][:3], ["python3", "-m", "buffon"])
        # Only an interpreter is replaced: a program the session names by its absolute path in the pod stays as it is.
        fake = FakeCluster()
        k8s.K8sBackend(kube_site(), runner=fake, env=self.env).run(backend.Session(argv=["/opt/buffon/bin/buffon-session", "--out", run_dir], run_dir=run_dir))
        self.assertEqual(fake.calls[0].session["argv"][0], "/opt/buffon/bin/buffon-session")

    def test_argv_must_name_the_run_directory(self):
        run_dir = tempfile.mkdtemp()
        with self.assertRaisesRegex(backend.BackendError, "never names its run directory"):
            k8s.K8sBackend(kube_site(), runner=FakeCluster(), env=self.env).run(backend.Session(argv=["buffon", "session"], run_dir=run_dir))

    def test_a_bundle_site_needs_the_sessions_bundle(self):
        s = kube_site(image="", bundle=True, base_image="python" + DIGEST)
        run_dir = tempfile.mkdtemp()
        with self.assertRaisesRegex(backend.BackendError, "names no bundle directory"):
            k8s.K8sBackend(s, runner=FakeCluster(), env=self.env).run(backend.Session(argv=["buffon", run_dir], run_dir=run_dir))
        fake = FakeCluster()
        k8s.K8sBackend(s, runner=fake, env=self.env).run(backend.Session(argv=["buffon", run_dir], run_dir=run_dir, bundle="/b"))
        self.assertEqual((fake.calls[0].site["bundle"], fake.calls[0].site["baseImage"]), ("/b", "python" + DIGEST))
        self.assertNotIn("image", fake.calls[0].site)
        # A bundle pod has no network: the session installs offline from the bundle's caches, never from a cache path of the operator's machine.
        fake = FakeCluster()
        argv = ["buffon", "session", "--cache-dir", "/var/cache/buffon", "--out", run_dir, "--cache-dir=/x", "--offline", "--npm-cache", "/n", "--npm-cache=/m"]
        k8s.K8sBackend(s, runner=fake, env=self.env).run(backend.Session(argv=argv, run_dir=run_dir, bundle="/b"))
        self.assertEqual(fake.calls[0].session["argv"], ["buffon", "session", "--out", "{out}", "--offline", "--cache-dir", "{root}/cache", "--npm-cache", "{root}/npm-cache"])
        # An image pod keeps the argv as it is.
        fake = FakeCluster()
        k8s.K8sBackend(kube_site(), runner=fake, env=self.env).run(backend.Session(argv=argv, run_dir=run_dir))
        self.assertEqual(fake.calls[0].session["argv"][2:4], ["--cache-dir", "/var/cache/buffon"])

    def test_the_run_directory_may_be_a_flag_value(self):
        fake = FakeCluster()
        run_dir = os.path.join(tempfile.mkdtemp(), "run")
        k8s.K8sBackend(kube_site(), runner=fake, env=self.env).run(backend.Session(argv=["buffon", "session", "--out=" + run_dir, "--note=" + run_dir + "x"], run_dir=run_dir))
        self.assertEqual(fake.calls[0].session["argv"], ["buffon", "session", "--out={out}", "--note=" + run_dir + "x"])

    def test_a_refused_session_is_an_error_not_a_result(self):
        fake = FakeCluster(exit_code=k8s.EXIT_USAGE, hand_back=False)
        run_dir = tempfile.mkdtemp()
        with self.assertRaisesRegex(backend.BackendError, "refused the session"):
            k8s.K8sBackend(kube_site(), runner=fake, env=self.env).run(backend.Session(argv=["buffon", run_dir], run_dir=run_dir))

    def test_secrets_reach_the_site_only_as_references(self):
        kube = kube_site().kube
        kube.secret_env = [{"name": "API_KEY", "secret": "buffon-keys", "key": "api", "value": "leaked"}]
        kube.max_cv = 0.03
        st = k8s.site_json(kube)
        self.assertEqual(st["secretEnv"], [{"name": "API_KEY", "secret": "buffon-keys", "key": "api"}])
        self.assertNotIn("leaked", json.dumps(st))
        self.assertEqual(st["maxCv"], 0.03)

    def test_the_profile_secret_env_and_max_cv_reach_the_cluster_site(self):
        ref = {"name": "API_KEY", "secret": "buffon-keys", "key": "api"}
        st = k8s.site_json(kube_site(secret_env=[ref], max_cv=0.03).kube)
        self.assertEqual((st["secretEnv"], st["maxCv"]), ([ref], 0.03))
        st = k8s.site_json(kube_site().kube)
        self.assertEqual(st["maxCv"], 0.05)   # the site's default, which is buffon-cluster's default too
        self.assertNotIn("secretEnv", st)

    def test_check_renders_without_the_cluster(self):
        fake = FakeCluster()
        k8s.K8sBackend(kube_site(), runner=fake, env=self.env).check()
        self.assertEqual(fake.calls[0].command, "render")


class SpreadTests(unittest.TestCase):
    """One session on several nodes at once: the site's `nodes` and `spread`, or a calibration's nodes, choose them; each node's run directory comes back under its name."""

    def setUp(self):
        self.env = {"BUFFON_CLUSTER_BIN": "/opt/buffon-cluster", "PATH": "/usr/bin"}

    def run_on(self, s, fake, nodes=None):
        run_dir = os.path.join(tempfile.mkdtemp(), "run")
        result = k8s.K8sBackend(s, runner=fake, env=self.env, now=0).run(backend.Session(argv=["buffon", "session", "--out", run_dir], run_dir=run_dir, nodes=nodes))
        return run_dir, result, fake.calls[0]

    def node_flags(self, call):
        argv = call.argv
        return {flag: argv[argv.index(flag) + 1] for flag in ("-nodes", "-spread") if flag in argv}

    def test_the_site_or_the_session_chooses_the_nodes(self):
        self.assertEqual(self.node_flags(self.run_on(kube_site(), FakeCluster())[2]), {})
        self.assertEqual(self.node_flags(self.run_on(kube_site(spread=2), FakeCluster())[2]), {"-spread": "2"})
        self.assertEqual(self.node_flags(self.run_on(kube_site(nodes=["a", "b"]), FakeCluster())[2]), {"-nodes": "a,b"})
        self.assertEqual(self.node_flags(self.run_on(kube_site(nodes=["a", "b", "c"], spread=2), FakeCluster())[2]), {"-spread": "2", "-nodes": "a,b,c"})
        # A calibration's nodes replace the site's choice, and the site's single-node pin.
        _, _, call = self.run_on(kube_site(node="pinned"), FakeCluster(), nodes=["a", "b"])
        self.assertEqual(self.node_flags(call), {"-nodes": "a,b"})
        self.assertNotIn("node", call.site)
        _, _, call = self.run_on(kube_site(spread=3, nodes=["a", "b", "c"]), FakeCluster(), nodes=["b", "c"])
        self.assertEqual(self.node_flags(call), {"-nodes": "b,c"})

    def test_each_node_hands_back_its_own_run_directory(self):
        run_dir, result, _ = self.run_on(kube_site(spread=2), FakeCluster())
        self.assertEqual(sorted(os.listdir(run_dir)), ["cluster-nodes.json", "cluster-outcome.json", "node-1", "node-2", "spread.json"])
        for node in ("node-1", "node-2"):
            for name in ("raw.json", "facts.json", "cluster-facts.json", "node.json", "logs"):
                self.assertTrue(os.path.exists(os.path.join(run_dir, node, name)), (node, name))
            with open(os.path.join(run_dir, node, "cluster-facts.json")) as f:
                self.assertEqual(json.load(f)["node"], node)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual([(n["node"], n["run_dir"], n["exit_code"], n["node_class"]) for n in result.facts["nodes"]],
                         [("node-1", os.path.join(run_dir, "node-1"), 0, "B"), ("node-2", os.path.join(run_dir, "node-2"), 0, "B")])
        self.assertEqual(result.throttled_usec, 24)
        with open(os.path.join(run_dir, "cluster-outcome.json")) as f:
            self.assertEqual([o["dir"] for o in json.load(f)["outcomes"]], ["node-1", "node-2"])

    def test_a_pick_of_one_node_keeps_the_single_layout(self):
        run_dir, result, _ = self.run_on(kube_site(spread=1), FakeCluster())
        self.assertTrue(os.path.exists(os.path.join(run_dir, "raw.json")))
        self.assertTrue(os.path.exists(os.path.join(run_dir, "cluster-nodes.json")))
        self.assertNotIn("nodes", result.facts)

    def test_a_node_that_failed_fails_the_session(self):
        _, result, _ = self.run_on(kube_site(nodes=["a", "b", "c"]), FakeCluster(node_exits={"b": 3, "c": 4}))
        self.assertEqual([n["exit_code"] for n in result.facts["nodes"]], [0, 3, 4])
        self.assertEqual(result.exit_code, 3)   # the first failure in node order

    def test_a_node_name_that_is_not_a_directory_name_or_repeats_falls_back_to_the_run_name(self):
        run_dir, result, _ = self.run_on(kube_site(nodes=["a", "b", "c"]), FakeCluster(node_names={"b": "../escape", "c": "a"}))
        names = sorted(os.listdir(run_dir))
        self.assertIn("a", names)
        self.assertEqual(len([n for n in names if n.endswith(("-n2", "-n3"))]), 2, names)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(run_dir), "escape")))
        self.assertEqual(len({n["run_dir"] for n in result.facts["nodes"]}), 3)

    def test_calibrate_and_check_call_the_cluster_tool_with_the_sites_gate(self):
        fake = FakeCluster()
        b = k8s.K8sBackend(kube_site(max_cv=0.03), runner=fake, env=dict(self.env, BUFFON_K8S_NAMESPACE="leaks"))
        self.assertEqual(b.calibrate(["/r/a", "/r/b"], "/r/calibration.json"), (0, "calibrate verdict"))
        self.assertEqual(fake.calls[0].argv[1:], ["calibrate", "-max-cv", "0.03", "-o", "/r/calibration.json", "/r/a", "/r/b"])
        self.assertNotIn("BUFFON_K8S_NAMESPACE", fake.calls[0].env)
        self.assertEqual(b.check_calibration("/r/calibration.json", ["a", "b"])[0], 0)
        self.assertEqual(fake.calls[1].argv[1:], ["check", "-calibration", "/r/calibration.json", "-nodes", "a,b"])
        fake.tool_exit = 3
        self.assertEqual(b.calibrate(["/r/a"], "/r/c.json")[0], 3)
        self.assertEqual(b.check_calibration("/r/c.json", ["a"])[0], 3)
        fake.tool_exit = 1
        with self.assertRaisesRegex(backend.BackendError, "buffon-cluster calibrate"):
            b.calibrate(["/r/a"], "/r/c.json")
        with self.assertRaisesRegex(backend.BackendError, "buffon-cluster check"):
            b.check_calibration("/r/c.json", ["a"])


@unittest.skipUnless(shutil.which("go") or os.environ.get("BUFFON_CLUSTER_BIN"), "needs Go to build cluster/ (or BUFFON_CLUSTER_BIN)")
class K8sBackendWithTheRealClusterBinaryTests(unittest.TestCase):
    """The site and session the backend writes are what buffon-cluster accepts: rendered, never submitted."""

    @classmethod
    def setUpClass(cls):
        cls.bin = os.environ.get("BUFFON_CLUSTER_BIN")
        if not cls.bin:
            cls.tmp = tempfile.mkdtemp()
            cls.bin = os.path.join(cls.tmp, "buffon-cluster")
            root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cluster")
            done = subprocess.run(["go", "build", "-o", cls.bin, "."], cwd=root, capture_output=True, text=True)
            if done.returncode:
                out = (done.stderr or done.stdout).strip()
                # A Go that is older than cluster/go.mod (it would download a newer toolchain) or a platform without a pinned toolchain is a missing prerequisite, not a defect: skip with the reason. On Linux with the pinned Go a failed build fails the test.
                if sys.platform != "linux" or re.search(r"toolchain|requires go", out):
                    raise unittest.SkipTest("cannot build cluster/ with this Go (" + (out.splitlines() or ["no output"])[-1][:200] + "); install a Go that satisfies cluster/go.mod or set BUFFON_CLUSTER_BIN")
                raise AssertionError("go build ./cluster failed:\n" + out)

    def test_check_passes_a_valid_site_and_refuses_an_invalid_one(self):
        env = {"BUFFON_CLUSTER_BIN": self.bin, "PATH": os.environ.get("PATH", "")}
        k8s.K8sBackend(kube_site(node_selector={"pool": "bench"}, tolerations=[{"key": "dedicated", "operator": "Equal", "value": "bench", "effect": "NoSchedule"}]), env=env).check()
        k8s.K8sBackend(kube_site(image="", bundle=True, base_image="python" + DIGEST), env=env).check()
        with self.assertRaisesRegex(backend.BackendError, "is not a node name"):
            k8s.K8sBackend(kube_site(node="Not_A_Node"), env=env).check()

    def fake_kubectl(self, nodes_json=None):
        """A kubectl on PATH that answers `get nodes` and `get pods` (nodes_json None: it cannot reach the cluster, as without the VPN)."""
        d = tempfile.mkdtemp()
        script = os.path.join(d, "kubectl")
        with open(script, "w") as f:
            if nodes_json is None:
                f.write('#!/bin/sh\necho "Unable to connect to the server: dial tcp: i/o timeout" >&2\nexit 1\n')
            else:
                with open(os.path.join(d, "nodes.json"), "w") as n:
                    json.dump(nodes_json, n)
                f.write(f'#!/bin/sh\necho "$*" >> {d}/calls\ncase "$*" in *" nodes "*) cat {d}/nodes.json ;; *) echo \'{{"items": []}}\' ;; esac\n')
        os.chmod(script, 0o755)
        return {"BUFFON_CLUSTER_BIN": self.bin, "PATH": d + os.pathsep + os.environ.get("PATH", "")}, d

    def test_nodes_asks_the_cluster_with_the_sites_kubectl_settings(self):
        node = {"metadata": {"name": "bench-1", "labels": {"pool": "bench"}}, "spec": {}, "status": {"allocatable": {"cpu": "16", "memory": "64Gi", "pods": "110"},
                                                                                                    "conditions": [{"type": "Ready", "status": "True"}]}}
        env, d = self.fake_kubectl({"items": [node]})
        for k in (kube_site(node_selector={"pool": "bench"}), kube_site(image="", bundle=True, base_image="python" + DIGEST, node="bench-1")):
            code, ranking = k8s.K8sBackend(k, env=env).nodes()
            self.assertEqual(code, 0, ranking)
            self.assertEqual([n["name"] for n in ranking["nodes"]], ["bench-1"])
        with open(os.path.join(d, "calls")) as f:
            self.assertIn("--namespace buffon", f.read())
        env, _ = self.fake_kubectl(None)
        code, text = k8s.K8sBackend(kube_site(), env=env).nodes()
        self.assertNotEqual(code, 0)
        self.assertIn("Unable to connect", text)

    def node_dir(self, root, node, cpu_ms):
        """A run directory as a calibration pod hands it back: cluster-facts.json and Buffon's raw.json with the reference arm and its A/A copy."""
        d = os.path.join(root, node)
        os.makedirs(d)
        with open(os.path.join(d, "cluster-facts.json"), "w") as f:
            json.dump({"node": node, "cpuSet": "exclusive", "pin": {"cpus": "4,5", "fixedClock": True}, "session": {"exit": 0}}, f)
        samples = [{"arm": arm, "scenario": "overhead/print", "api": "openai-completions", "round": i, "warmup": False, "cpu_ms": v, "wall_ms": v}
                   for arm in ("pi-node", "pi-node-b") for i, v in enumerate(cpu_ms)]
        with open(os.path.join(d, "raw.json"), "w") as f:
            json.dump({"samples": samples}, f)
        return d

    def test_calibrate_and_check_with_the_real_cluster_binary(self):
        env = {"BUFFON_CLUSTER_BIN": self.bin, "PATH": os.environ.get("PATH", "")}
        root = tempfile.mkdtemp()
        quiet = [100.0 + (i % 3) for i in range(12)]          # CV about 0.8%
        noisy = [100.0 + 20 * (i % 2) for i in range(12)]     # CV about 9.5%
        dirs = [self.node_dir(root, "node-a", quiet), self.node_dir(root, "node-b", quiet), self.node_dir(root, "node-c", noisy)]
        b = k8s.K8sBackend(kube_site(max_cv=0.05), env=env)
        path = os.path.join(root, "calibration.json")
        code, text = b.calibrate(dirs[:2], path)
        self.assertEqual(code, 0, text)
        with open(path) as f:
            cal = json.load(f)
        self.assertEqual((cal["maxCv"], [n["node"] for n in cal["nodes"]], cal["pass"]), (0.05, ["node-a", "node-b"], True))
        self.assertEqual(b.check_calibration(path, ["node-a", "node-b"])[0], 0)
        self.assertEqual(b.check_calibration(path, ["node-a", "node-x"])[0], 3)   # a node the calibration never judged
        # One noisy node of three: the median passes, the node is named, and a comparison on it is refused.
        code, text = b.calibrate(dirs, os.path.join(root, "one-noisy.json"))
        self.assertEqual(code, 0, text)
        self.assertIn("node node-c (exclusive cores): noisy", text)
        self.assertEqual(b.check_calibration(os.path.join(root, "one-noisy.json"), ["node-a", "node-c"])[0], 3)
        self.assertEqual(b.check_calibration(os.path.join(root, "one-noisy.json"), ["node-a", "node-b"])[0], 0)
        # Two noisy nodes of three: the median fails.
        dirs.append(self.node_dir(root, "node-d", noisy))
        code, text = b.calibrate([dirs[0], dirs[2], dirs[3]], os.path.join(root, "noisy.json"))
        self.assertEqual(code, 3, text)
        # The site's max_cv is the gate: 0.10 lets the same nodes through.
        self.assertEqual(k8s.K8sBackend(kube_site(max_cv=0.10), env=env).calibrate([dirs[0], dirs[2], dirs[3]], os.path.join(root, "loose.json"))[0], 0)

    def test_a_secret_reaches_the_pod_as_a_secret_key_ref(self):
        env = {"BUFFON_CLUSTER_BIN": self.bin, "PATH": os.environ.get("PATH", "")}
        rendered = []

        def runner(argv, **kw):
            done = subprocess.run(argv, **kw)
            rendered.append(done.stdout)
            return done

        k8s.K8sBackend(kube_site(secret_env=[{"name": "API_KEY", "secret": "buffon-keys", "key": "api"}], max_cv=0.03), runner=runner, env=env).check()
        self.assertRegex(rendered[0], r'- name: "API_KEY"\s+valueFrom:\s+secretKeyRef:\s+name: "buffon-keys"\s+key: "api"\n')


if __name__ == "__main__":
    unittest.main()
