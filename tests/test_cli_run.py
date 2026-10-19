# SPDX-License-Identifier: Apache-2.0
"""`buffon run` hands the operator's run flags to the session it starts (review: --isolation container, --no-quiet-gate, --observer and --lock-file were dropped)."""
import tempfile
import types
import unittest

from buffon import backend, cli


class RunForwardsEveryRunFlag(unittest.TestCase):
    def session_args(self, extra):
        seen = {}

        class Fake:
            def check(self, isolation="none"):
                pass

            def run(self, session):
                seen["argv"] = session.argv
                return types.SimpleNamespace(exit_code=0, run_dir=session.run_dir, facts={})

        saved = backend.get_backend
        backend.get_backend = lambda site: Fake()
        try:
            args = cli.build_parser().parse_args(["run", "overhead/version", "--out", tempfile.mkdtemp()] + extra)
            self.assertEqual(cli.cmd_run(args), 0)
        finally:
            backend.get_backend = saved
        argv = seen["argv"]
        return cli.build_parser().parse_args(argv[argv.index("session"):])

    def test_flags_the_operator_gave_reach_the_session(self):
        got = self.session_args(["--isolation", "container", "--no-quiet-gate", "--observer", "m:f", "--observer", "n:g", "--lock-file", "/x/lock", "--foreign-lock", "/y/lock",
                                 "--quiet-timeout", "7", "--quiet-max-busy", "0.5", "--host-claim", "A", "--require-class", "A"])
        self.assertEqual((got.isolation, got.no_quiet_gate, got.observer, got.lock_file), ("container", True, ["m:f", "n:g"], "/x/lock"))
        self.assertIn("/y/lock", got.foreign_lock)
        self.assertEqual((got.quiet_timeout, got.quiet_max_busy, got.host_claim, got.require_class), (7.0, 0.5, "A", "A"))

    def test_the_clock_claim_of_a_site_and_of_the_command_line_reaches_the_session(self):
        import os
        site = os.path.join(tempfile.mkdtemp(), "vm.toml")
        with open(site, "w") as f:
            f.write('[site]\nbackend = "local"\n[local]\ncpus = "2-3"\nmock_cpus = "1"\nclock_claim = "hypervisor"\n')
        self.assertEqual(self.session_args(["--site", site]).clock_claim, "hypervisor")
        self.assertEqual(self.session_args(["--clock-claim", "hypervisor"]).clock_claim, "hypervisor")
        self.assertEqual(self.session_args([]).clock_claim, "")

    def test_a_local_runs_offline_cache_flags_reach_the_session_and_override_the_sites_cache(self):
        got = self.session_args(["--offline", "--cache-dir", "/bundle/cache", "--npm-cache", "/bundle/npm-cache"])
        self.assertEqual((got.offline, got.cache_dir, got.npm_cache), (True, "/bundle/cache", "/bundle/npm-cache"))
        plain = self.session_args([])
        self.assertEqual((plain.offline, plain.npm_cache), (False, ""))
        self.assertTrue(plain.cache_dir)   # the site's own cache directory

    def test_a_kubernetes_site_refuses_the_local_cache_flags(self):
        import os
        site = os.path.join(tempfile.mkdtemp(), "k.toml")
        with open(site, "w") as f:
            f.write('[site]\nbackend = "kubernetes"\n[kubernetes]\nnamespace = "n"\nimage = "r.example/a@sha256:' + "a" * 64 + '"\n')
        with self.assertRaises(backend.BackendError):
            self.session_args(["--site", site, "--offline"])

    def test_defaults_stay_the_sites(self):
        got = self.session_args([])
        # No --isolation reaches a local session: it runs uncontained ("none"); a Kubernetes site asks for pod-guaranteed (tests/test_pod_envelope.py).
        self.assertEqual((got.isolation, got.no_quiet_gate, got.observer, got.lock_file), (None, False, [], None))


if __name__ == "__main__":
    unittest.main()
