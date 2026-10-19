# SPDX-License-Identifier: Apache-2.0
import json
import os
import tempfile
import types
import unittest

from buffon import backend, site
from buffon.backend.local import LocalBackend
from buffon.runner import facts as factlib
from tests.nopin import without_affinity


class LocalBackendTests(unittest.TestCase):
    def site(self, **local):
        return site.from_dict({"local": local}, env={})

    def test_factory_selects_by_profile(self):
        self.assertIsInstance(backend.get_backend(self.site()), LocalBackend)

    def test_check_refuses_cpus_the_machine_does_not_give(self):
        with self.assertRaisesRegex(backend.BackendError, "does not give the runner"):
            LocalBackend(self.site(cpus="1000000")).check()

    def test_check_passes_for_an_allowed_cpu(self):
        if not hasattr(os, "sched_setaffinity"):
            self.skipTest("a platform that cannot pin refuses a profile that names cpus (next test)")
        LocalBackend(self.site(cpus=str(factlib.allowed_cpus()[0]))).check()

    def test_a_platform_that_cannot_pin_refuses_cpus_and_accepts_none(self):
        with without_affinity():
            with self.assertRaisesRegex(backend.BackendError, "cannot pin"):
                LocalBackend(self.site(cpus="0")).check()
            with self.assertRaisesRegex(backend.BackendError, "requires pinning"):
                LocalBackend(self.site(cpus="0", pinning="required")).check()
            LocalBackend(self.site(pinning="none")).check()
            LocalBackend(self.site()).check()

    def test_run_passes_argv_and_env_and_reads_facts_back(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "facts.json"), "w") as f:
            json.dump({"pinned_cpus": "2-3", "throttled_usec": 7, "node": None}, f)
        seen = {}

        def fake(argv, env, timeout):
            seen.update(argv=argv, env=env, timeout=timeout)
            return types.SimpleNamespace(returncode=0)

        result = LocalBackend(self.site(), popen=fake).run(backend.Session(argv=["x", "y"], run_dir=d, env={"BUFFON_SITE_JSON": "{}"}, deadline_s=5))
        self.assertEqual(seen["argv"], ["x", "y"])
        self.assertEqual(seen["env"]["BUFFON_SITE_JSON"], "{}")
        self.assertEqual(seen["timeout"], 5)
        self.assertEqual((result.pinned_cpus, result.throttled_usec, result.exit_code), ([2, 3], 7, 0))

    def test_a_session_that_died_before_writing_facts_still_returns_its_exit_code(self):
        d = tempfile.mkdtemp()
        result = LocalBackend(self.site(), popen=lambda argv, env, timeout: types.SimpleNamespace(returncode=3)).run(backend.Session(argv=["x"], run_dir=d))
        self.assertEqual((result.exit_code, result.facts, result.pinned_cpus), (3, {}, []))

    def test_a_kubernetes_profile_without_the_backend_module_fails_clearly(self):
        s = site.from_dict({"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "n", "image": "r/a@sha256:" + "b" * 64}}, env={})
        try:
            import buffon.backend.k8s  # noqa: F401
        except ImportError:
            with self.assertRaisesRegex(backend.BackendError, "not installed"):
                backend.get_backend(s)


if __name__ == "__main__":
    unittest.main()
