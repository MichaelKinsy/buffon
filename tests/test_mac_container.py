# SPDX-License-Identifier: Apache-2.0
"""macOS with --isolation container: `cpus` are the container VM's CPU ids and reach --cpuset-cpus, while the host cannot pin and the run is labelled PROVISIONAL."""
import os
import tempfile
import types
import unittest
from unittest import mock

from buffon import backend, site
from buffon.arms import install, manifest
from buffon.backend.local import LocalBackend
from buffon.envelope import Mount, Spec, build_argv, lint
from buffon.runner import container as containerlib, engine
from tests.nopin import without_affinity

DIGEST = "debian@sha256:" + "a" * 64


def plan(**kw):
    base = dict(workloads=[], arms=[manifest.load_arm("pi-node")], rounds=12, aa="none", pinning="preferred", out=tempfile.mkdtemp(), calibrate=False, cache_dir=tempfile.mkdtemp(),
                lock_file=os.path.join(tempfile.mkdtemp(), "l"), isolation="container", cpus=[1, 2, 3])
    base.update(kw)
    return engine.Plan(**base)


class VmCpus(unittest.TestCase):
    def test_a_platform_that_cannot_pin_takes_cpus_as_vm_cpus_only_for_a_container_run(self):
        with without_affinity():
            self.assertTrue(plan().vm_cpus)
            self.assertFalse(plan(isolation="none").vm_cpus)
            self.assertFalse(plan(pinning="none").vm_cpus)
            self.assertFalse(plan(cpus=[]).vm_cpus)
            plan(pinning="required", cpus=[1000]).validate()      # a VM's CPU ids are not this host's: not checked against the host's CPUs
            with self.assertRaisesRegex(engine.Refused, "cannot pin"):
                plan(pinning="required", isolation="none").validate()
            with self.assertRaisesRegex(engine.Refused, "not available"):
                plan(isolation="none", cpus=[1000]).validate()
        self.assertEqual(plan().vm_cpus, not hasattr(os, "sched_setaffinity"))

    def test_the_run_is_provisional_and_says_why(self):
        with without_affinity():
            why = engine.run_reasons(plan(), [], [], {"mode": "socket-audit"}, {})
        self.assertEqual(len(why), 1)
        self.assertIn("pinned inside the VM by --cpuset-cpus", why[0])

    def test_the_site_check_accepts_cpus_for_container_isolation_and_refuses_them_otherwise(self):
        b = LocalBackend(site.from_dict({"local": {"cpus": "1-3"}}, env={}))
        with without_affinity():
            b.check(isolation="container")
            with self.assertRaisesRegex(backend.BackendError, "--isolation container"):
                b.check()
            with self.assertRaisesRegex(backend.BackendError, "--isolation container"):
                b.check(isolation="none")
            LocalBackend(site.from_dict({"local": {"cpus": "1-3", "pinning": "required"}}, env={})).check(isolation="container")

    def test_vm_cpu_ids_are_not_checked_against_the_host(self):
        with without_affinity():
            LocalBackend(site.from_dict({"local": {"cpus": "1000-1002"}}, env={})).check(isolation="container")     # the VM's ids, not this host's
            with self.assertRaisesRegex(backend.BackendError, "does not give the runner"):
                LocalBackend(site.from_dict({"local": {"cpus": "1000-1002"}}, env={})).check()

    def test_buffon_run_hands_its_isolation_to_the_site_check(self):
        from buffon import cli
        seen = []

        class Stop(Exception):
            pass

        class Fake:
            def check(self, isolation="none"):
                seen.append(isolation)
                raise Stop

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "mac.toml")
        with open(path, "w") as f:
            f.write('[site]\nbackend = "local"\n[local]\ncpus = "1-3"\n')
        with mock.patch.object(backend, "get_backend", lambda s: Fake()), self.assertRaises(Stop):
            cli.main(["run", "--site", path, "--isolation", "container", "--out", os.path.join(tmp, "out")])
        self.assertEqual(seen, ["container"])

    def test_the_macos_container_example_loads(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        loaded = site.load(os.path.join(root, "sites", "example-macos-container.toml"), env={})
        self.assertEqual((loaded.local.cpus, loaded.local.pinning), ([1, 2, 3], "preferred"))
        with without_affinity():
            LocalBackend(loaded).check(isolation="container")


class RunnerPath(unittest.TestCase):
    """The engine's container branch with a fake runtime: what reaches `docker run`."""

    def run_engine(self, p):
        seen = {}

        def configure(ws, plan_, repo_root, server, sock, cpus, mems, memory_mib=4096):
            seen["cpus"], seen["mems"] = list(cpus), mems
            spec = Spec(image=DIGEST, cpuset_cpus=list(cpus), cpuset_mems=str(mems), memory_mib=1024, env={}, mounts=[Mount("/opt", "/opt")], output=Mount("/out", "/out", False), sockets=[("/run/mock.sock", "/run/buffon/mock.sock")])
            seen["argv"] = build_argv(spec, ["arm"])
            seen["lint"] = lint(seen["argv"])
            return {"cpuset_cpus": list(cpus), "cpuset_mems": str(mems)}

        def fake_install(self, a, source_repos=None):
            a.binary, a.install_dir, a.record, a.version_line = "/bin/sh", tempfile.mkdtemp(), {}, "stub 1"
            return a
        saved = (install.Workspace.install, engine.Runner.measure, engine.Runner.gates, containerlib.configure)
        install.Workspace.install, engine.Runner.measure = fake_install, lambda self, ctx, inst: None
        engine.Runner.gates = lambda self, ctx, installed, instances: ({}, {}, None)
        containerlib.configure = configure
        try:
            try:
                runner = engine.Runner(p, log=lambda *_: None)
                runner.run()
            except engine.Refused as error:
                return seen, str(error), None
            return seen, None, runner
        finally:
            install.Workspace.install, engine.Runner.measure, engine.Runner.gates, containerlib.configure = saved

    def test_vm_cpus_reach_cpuset_cpus_and_the_run_is_labelled_provisional(self):
        with without_affinity():
            seen, refused, runner = self.run_engine(plan())
        self.assertIsNone(refused)
        self.assertEqual((seen["cpus"], seen["mems"]), ([1, 2, 3], 0))
        argv = seen["argv"]
        self.assertEqual((argv[argv.index("--cpuset-cpus") + 1], argv[argv.index("--cpus") + 1]), ("1-3", "3"))
        self.assertEqual(seen["lint"], [])
        with open(os.path.join(runner.plan.out, "raw.json")) as f:
            raw = f.read()
        self.assertIn("pinned inside the VM by --cpuset-cpus", raw)     # the PROVISIONAL reason is in the run's record, so a report can print it
        self.assertIn("provisional", raw.lower())

    def test_a_container_run_without_cpus_is_still_refused_on_a_platform_that_cannot_pin(self):
        with without_affinity():
            seen, refused, _ = self.run_engine(plan(cpus=[]))
        self.assertRegex(refused, "needs pinned CPUs")
        self.assertEqual(seen, {})


if __name__ == "__main__":
    unittest.main()
