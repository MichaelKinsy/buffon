# SPDX-License-Identifier: Apache-2.0
"""buffon/envelope/pod.py, the pod-guaranteed isolation: each envelope guarantee P1-P5 read from a fake pod root, the per-sample pod facts, the stamp, raw.json's
shape and what `buffon verify` requires of a pod-guaranteed run."""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from buffon import verify
from buffon.envelope import pod
from buffon.runner import raw as rawlib

DIGEST = "registry.example/python@sha256:" + "a" * 64
MOUNTINFO_RO = "1 0 0:1 / / ro,relatime - overlay overlay ro\n2 1 0:2 / /data rw - ext4 /dev/x rw\n"


class FakePod:
    """A pod root as the session sees it: cgroup files, /proc/self/mountinfo, network interfaces, the pod facts file and the environment."""

    def __init__(self, test, cpuset="4-7", cpu_max="400000 100000", memory_max="17179869184", online="0-63", mountinfo=MOUNTINFO_RO, interfaces=("eth0", "lo"),
                 facts=None, image=DIGEST, connects=False, euid=65532):
        self.root = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.root, True)
        files = {"sys/fs/cgroup/cpuset.cpus.effective": cpuset, "sys/fs/cgroup/cpu.max": cpu_max, "sys/fs/cgroup/memory.max": memory_max,
                 "sys/devices/system/cpu/online": online, "proc/self/mountinfo": mountinfo}
        for rel, body in files.items():
            if body is None:
                continue
            os.makedirs(os.path.dirname(os.path.join(self.root, rel)), exist_ok=True)
            with open(os.path.join(self.root, rel), "w") as f:
                f.write(body + "\n")
        for name in interfaces:
            os.makedirs(os.path.join(self.root, "sys/class/net", name))
        facts_path = os.path.join(self.root, "pod-facts.json")
        with open(facts_path, "w") as f:
            json.dump(facts if facts is not None else {"node": "node-a", "pod": "p", "requestedCpus": 4, "cpuSet": "exclusive", "delivery": "bundle", "artifactsSha256": "b" * 64}, f)
        self.env = {"BUFFON_POD_FACTS": facts_path, "BUFFON_IMAGE_REF": image, "NODE_NAME": "node-a", "POD_NAME": "p", "KUBERNETES_SERVICE_HOST": "api.cluster.invalid",
                    "KUBERNETES_SERVICE_PORT": "443"}
        self.connected = []

        def connect(host, port):
            self.connected.append((host, port))
            return connects
        self.probe = pod.Probe(root=self.root, env=self.env, connect=connect, euid=euid)


class Checks(unittest.TestCase):
    def test_a_guaranteed_pod_with_exclusive_cores_and_no_network_is_the_envelope(self):
        p = FakePod(self)
        facts, reasons = pod.check(p.probe)
        self.assertEqual(reasons, [])
        self.assertEqual((facts["node"], facts["qos"], facts["cpuset"], facts["requested_cpus"], facts["image"], facts["read_only_root"], facts["uid"]),
                         ("node-a", "Guaranteed", "4-7", 4, DIGEST, True, 65532))
        self.assertEqual(p.connected, [("api.cluster.invalid", "443")], "P5 is checked against the cluster's API service")
        self.assertEqual(pod.stamp(facts, reasons), {"isolation": "pod-guaranteed", "comparable": True, "pod": facts})

    def test_without_a_cpu_quota_the_exclusive_cores_still_qualify(self):
        self.assertEqual(pod.check(FakePod(self, cpu_max="max 100000").probe)[1], [])

    def test_each_guarantee_that_fails_is_named(self):
        cases = [
            ("shared cpuset", dict(cpuset="0-63"), "P1: the cpuset 0-63 does not hold exactly the 4 requested CPUs"),
            ("node no larger than the pod", dict(online="0-3", cpuset="0-3"), "P1: the node has 4 CPUs online"),
            ("cpu limit", dict(cpu_max="200000 100000"), "P1: cpu.max '200000 100000' is neither a limit of 4 CPUs nor unlimited"),
            ("memory limit", dict(memory_max="max"), "P1: memory.max 'max' is not a limit"),
            ("tag", dict(image="registry.example/python:3.12"), "P2: the image registry.example/python:3.12 is not pinned by digest"),
            ("bundle unchecked", dict(facts={"node": "node-a", "requestedCpus": 4, "delivery": "bundle"}), "P2: the bundle's ARTIFACTS.sha256 was not read"),
            ("writable root", dict(mountinfo="1 0 0:1 / / rw,relatime - overlay overlay rw"), "P3: the root filesystem is writable"),
            ("root user", dict(euid=0), "P4: the session runs as root"),
            ("network", dict(connects=True), "P5: a connection to the cluster's API service api.cluster.invalid:443 got through"),
            ("not in a pod", dict(facts={}), "no pod facts (BUFFON_POD_FACTS)"),
            ("cgroup v1", dict(cpuset=None, cpu_max=None, memory_max=None), "P1: the cpuset None does not hold exactly the 4 requested CPUs"),
        ]
        for name, kw, want in cases:
            with self.subTest(name):
                facts, reasons = pod.check(FakePod(self, **kw).probe)
                self.assertTrue(any(r.startswith(want) for r in reasons), reasons)
                st = pod.stamp(facts, reasons)
                self.assertEqual((st["isolation"], st["comparable"], st["stamp"], st["requested"]), ("none", False, "uncontained, not comparable", "pod-guaranteed"))
                self.assertEqual(st["reasons"], reasons)

    def test_the_stamp_names_five_drifted_samples_and_counts_the_rest(self):
        drift = [f"sample {i} drifted" for i in range(8)]
        st = pod.stamp({"node": "n"}, ["P3: x"], drift)
        self.assertEqual(st["reasons"], ["P3: x"] + drift[:5] + ["and 3 more samples that drifted"])
        self.assertEqual(pod.stamp({"node": "n"}, [], drift[:2])["reasons"], drift[:2])

    def test_interfaces_without_a_cluster_service_cannot_be_shown_closed(self):
        p = FakePod(self)
        del p.env["KUBERNETES_SERVICE_HOST"]
        self.assertTrue(any(r.startswith("P5: the pod has network interfaces (eth0)") for r in pod.check(p.probe)[1]))
        many = FakePod(self, interfaces=("lo",) + tuple(f"eth{i}" for i in range(7)))
        del many.env["KUBERNETES_SERVICE_HOST"]
        self.assertTrue(any("(eth0, eth1, eth2, eth3, eth4 and 2 more)" in r for r in pod.check(many.probe)[1]))
        only_lo = FakePod(self, interfaces=("lo",))
        del only_lo.env["KUBERNETES_SERVICE_HOST"]
        self.assertEqual(pod.check(only_lo.probe)[1], [])


class Samples(unittest.TestCase):
    def test_each_sample_records_the_node_cpuset_and_qos(self):
        p = FakePod(self)
        start, _ = pod.check(p.probe)
        self.assertEqual(pod.sample_facts(start, p.probe), {"node": "node-a", "cpuset": "4-7", "qos": "Guaranteed"})
        moved = FakePod(self, cpuset="0-63")
        self.assertEqual(pod.sample_facts(start, moved.probe)["qos"], "not Guaranteed")

    def test_a_sample_on_another_node_cpuset_or_qos_is_drift(self):
        start = {"node": "node-a", "cpuset": "4-7"}
        ok = {"arm": "a", "scenario": "s", "round": 0, "pod": {"node": "node-a", "cpuset": "4-7", "qos": "Guaranteed"}}
        self.assertEqual(pod.sample_drift(start, [ok]), [])
        for change, want in (({"node": "node-b"}, "node node-b"), ({"cpuset": "0-63"}, "cpuset 0-63"), ({"qos": "not Guaranteed"}, "QoS not Guaranteed")):
            with self.subTest(change):
                bad = dict(ok, pod=dict(ok["pod"], **change))
                self.assertIn(want, pod.sample_drift(start, [ok, bad])[0])
        self.assertIn("has no pod facts", pod.sample_drift(start, [{"arm": "a", "scenario": "s", "round": 1}])[0])

    def test_raw_json_holds_exactly_the_three_pod_facts(self):
        base = {"arm": "a", "scenario": "s", "round": 0, "warmup": False}
        rawlib.check_sample(dict(base, pod={"node": "n", "cpuset": "4-7", "qos": "Guaranteed"}))
        for bad in ({"node": "n", "cpuset": "4-7"}, {"node": "n", "cpuset": "4-7", "qos": "Guaranteed", "x": "y"}, {"node": 1, "cpuset": "4-7", "qos": "Guaranteed"}, "n"):
            with self.subTest(bad), self.assertRaises(rawlib.RawError):
                rawlib.check_sample(dict(base, pod=bad))


class Engine(unittest.TestCase):
    """The runner with isolation pod-guaranteed: every sample records the pod facts it ran with, and the stamp turns uncontained when a sample drifted."""

    def run_plan(self, cpusets):
        import types
        from buffon.runner import engine
        from buffon.workloads import Workload
        p = FakePod(self)
        start, reasons = pod.check(p.probe)
        self.assertEqual(reasons, [])
        seen = iter(cpusets)

        def fn(ctx, a):
            with open(os.path.join(p.root, "sys/fs/cgroup/cpuset.cpus.effective"), "w") as f:
                f.write(next(seen) + "\n")
            return {"cpu_ms": 1.0}
        arm = types.SimpleNamespace(id="a", label="a", twin_of=None, apis=["openai-completions"], capabilities={}, supports_mode=lambda m: True, supports_api=lambda a: True)
        plan = engine.Plan(workloads=[Workload(id="t/w", family="t", fn=fn)], arms=[arm], out=tempfile.mkdtemp(), rounds=2, warmup=0, apis=["openai-completions"],
                           allow_short=True, isolation=pod.MODE)
        r = engine.Runner(plan, log=lambda *_: None)
        r.isolation, r.pod_start = {}, start
        ctx = types.SimpleNamespace(opts=types.SimpleNamespace(api=None), server=types.SimpleNamespace(context={}, flush_log=lambda: None), release=lambda: None,
                                    harnesses_for=lambda a: [])
        with mock.patch.object(pod, "Probe", lambda: p.probe):
            r.measure(ctx, [arm])
        return r

    def test_samples_record_the_pod_and_a_steady_pod_is_comparable(self):
        r = self.run_plan(["4-7", "4-7"])
        self.assertEqual([s["pod"] for s in r.samples], [{"node": "node-a", "cpuset": "4-7", "qos": "Guaranteed"}] * 2)
        st = r.isolation_stamp()
        self.assertEqual((st["isolation"], st["comparable"]), ("pod-guaranteed", True))
        for s in r.samples:
            rawlib.check_sample(s)

    def test_a_sample_on_other_cores_makes_the_run_uncontained(self):
        r = self.run_plan(["4-7", "0-3,8-11"])
        st = r.isolation_stamp()
        self.assertEqual((st["isolation"], st["comparable"], st["requested"]), ("none", False, "pod-guaranteed"))
        self.assertTrue(any("cpuset 0-3,8-11" in why for why in st["reasons"]), st["reasons"])


class Verify(unittest.TestCase):
    def run_dir(self, stamp, samples, node):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        if node is not None:
            with open(os.path.join(d, "node.json"), "w") as f:
                json.dump(node, f)
        return d, {"run": {"isolation": stamp}, "samples": samples}

    def good(self):
        stamp = {"isolation": "pod-guaranteed", "comparable": True, "pod": {"node": "node-a", "cpuset": "4-7", "qos": "Guaranteed"}}
        samples = [{"arm": "a", "scenario": "s", "round": i, "pod": {"node": "node-a", "cpuset": "4-7", "qos": "Guaranteed"}} for i in range(3)]
        node = {"node": "node-a", "podQosClass": "Guaranteed", "podImageID": "registry.example/python@sha256:" + "a" * 64, "cpuManagerPolicy": "static"}
        return stamp, samples, node

    def test_a_pod_guaranteed_run_that_holds_passes(self):
        stamp, samples, node = self.good()
        self.assertEqual(verify.check_isolation(*self.run_dir(stamp, samples, node)), [])
        node["cpuManagerPolicy"] = "unreadable"   # a namespace-scoped account cannot read the kubelet's configz; the pod's own cpuset is the evidence then
        self.assertEqual(verify.check_isolation(*self.run_dir(stamp, samples, node)), [])

    def test_what_contradicts_the_stamp_is_rejected(self):
        cases = [
            ("not comparable", lambda st, sa, no: st.update(comparable=False), "does not record a comparable Guaranteed pod"),
            ("sample drift", lambda st, sa, no: sa[1]["pod"].update(cpuset="0-63"), "1 samples do not match the pod"),
            ("api qos", lambda st, sa, no: no.update(podQosClass="Burstable"), "QoS class as Burstable"),
            ("policy", lambda st, sa, no: no.update(cpuManagerPolicy="none"), "CPU manager policy is none"),
            ("image", lambda st, sa, no: no.update(podImageID="registry.example/python:3.12"), "no image digest"),
            ("no node.json", lambda st, sa, no: no.clear(), "node.json"),
        ]
        for name, change, want in cases:
            with self.subTest(name):
                stamp, samples, node = self.good()
                change(stamp, samples, node)
                problems = verify.check_isolation(*self.run_dir(stamp, samples, node or None))
                self.assertTrue(any(want in p for p in problems), problems)

    def test_an_unknown_isolation_is_rejected(self):
        self.assertIn("pod-guaranteed", verify.check_isolation("/x", {"run": {"isolation": {"isolation": "pod"}}})[0])


class Session(unittest.TestCase):
    def test_a_kubernetes_session_asks_for_pod_guaranteed_and_an_explicit_flag_wins(self):
        from buffon import backend, cli
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        site = os.path.join(tmp, "site.toml")
        with open(site, "w") as f:
            f.write(f'[site]\nbackend = "kubernetes"\n[kubernetes]\nnamespace = "n"\nimage = "reg.example/buffon@sha256:{"a" * 64}"\n')
        argvs = []

        class Fake:
            def check(self, isolation="none"):   # Backend.check's signature (cmd_run passes isolation)
                pass

            def run(self, session):
                argvs.append(session.argv)
                return backend.SessionResult(run_dir=session.run_dir, facts={}, pinned_cpus=[], throttled_usec=0, exit_code=0)

        with mock.patch.object(backend, "get_backend", lambda s: Fake()), mock.patch("sys.stdout"):
            cli.main(["run", "--site", site, "--out", os.path.join(tmp, "a")])
            cli.main(["run", "--site", site, "--out", os.path.join(tmp, "b"), "--isolation", "none"])
        parsed = [cli.build_parser().parse_args(a[3:]).isolation for a in argvs]
        self.assertEqual(parsed, ["pod-guaranteed", "none"])
        self.assertEqual([a.count("--isolation") for a in argvs], [1, 1], "the recorded command names one isolation")

    def test_each_node_directory_of_a_run_on_several_nodes_is_sealed(self):
        from buffon import backend, cli
        from buffon.submit import manifest
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        site = os.path.join(tmp, "site.toml")
        with open(site, "w") as f:
            f.write(f'[site]\nbackend = "kubernetes"\n[kubernetes]\nnamespace = "n"\nimage = "reg.example/buffon@sha256:{"a" * 64}"\n')

        class Fake:
            def check(self, isolation="none"):   # Backend.check's signature (cmd_run passes isolation)
                pass

            def run(self, session):
                nodes = []
                for name in ("node-a", "node-b"):
                    d = os.path.join(session.run_dir, name)
                    os.makedirs(d)
                    for f_name in ("raw.json", "cluster-facts.json", "node.json"):
                        with open(os.path.join(d, f_name), "w") as f:
                            f.write("{}")
                    nodes.append({"node": name, "run_dir": d, "exit_code": 0, "node_class": "A"})
                return backend.SessionResult(run_dir=session.run_dir, facts={"nodes": nodes}, pinned_cpus=[], throttled_usec=0, exit_code=0)

        out = os.path.join(tmp, "run")
        with mock.patch.object(backend, "get_backend", lambda s: Fake()), mock.patch("sys.stdout"):
            cli.main(["run", "--site", site, "--out", out])
        for name in ("node-a", "node-b"):
            d = os.path.join(out, name)
            self.assertEqual(manifest.check(d), [], name)
            self.assertIn("cluster-facts.json", manifest.sealed_files(d))


if __name__ == "__main__":
    unittest.main()
