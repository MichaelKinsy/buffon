# SPDX-License-Identifier: Apache-2.0
"""A host without Linux's /proc, cgroups and CPU affinity (macOS): the runner must say what it cannot do instead of failing. Each test removes the Linux facility from this Linux host."""
import os
import unittest
from unittest import mock

from buffon import site
from buffon.runner import cgroup, egress, engine, facts, quiet
from tests import TRUE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoProc(unittest.TestCase):
    def test_the_own_cgroup_is_none_when_proc_self_cgroup_does_not_exist(self):
        with mock.patch.object(cgroup, "_read", side_effect=FileNotFoundError("/proc/self/cgroup")):
            self.assertIsNone(cgroup._own_cgroup())

    def test_the_quiet_gate_builds_and_has_no_throttle_reading_without_a_cgroup(self):
        with mock.patch.object(cgroup, "_read", side_effect=FileNotFoundError("/proc/self/cgroup")):
            gate = quiet.QuietGate([0], read=lambda *_: {}, load=lambda: 0, runnable=lambda *_: 0, psi=lambda: None)
        self.assertIsNone(gate.throttled())

    def test_the_fact_collector_reads_nothing_from_a_missing_cgroup_file(self):
        with mock.patch.object(facts, "_read", return_value=None):
            self.assertEqual(facts.cgroup_files(), {})

    def test_the_allowed_cpus_fall_back_to_every_cpu_without_an_affinity_api(self):
        with mock.patch.object(os, "sched_getaffinity", side_effect=AttributeError, create=True):
            self.assertEqual(facts.allowed_cpus(), list(range(os.cpu_count() or 1)))

    def test_true_is_found_on_the_path_not_at_a_fixed_directory(self):
        self.assertTrue(os.path.exists(TRUE))


class NoAudit(unittest.TestCase):
    def test_a_host_without_proc_net_says_the_audit_is_unavailable_and_the_run_is_refused_for_publication(self):
        with mock.patch.object(egress, "netns_isolated", return_value=False), mock.patch.object(egress, "has_proc", return_value=False), mock.patch.object(egress, "lsof_path", return_value=None):
            mode = egress.describe()
        self.assertEqual(mode["mode"], "none")
        self.assertIn("refused for publication", mode["note"])
        reasons = engine.run_reasons(type("P", (), {"aa": 1})(), [], [], mode, {})
        self.assertTrue(any("egress audit unavailable on this OS" in r for r in reasons), reasons)


class NoPinning(unittest.TestCase):
    def test_a_mac_site_profile_has_no_cpus_and_does_not_pin(self):
        s = site.load(os.path.join(ROOT, "sites", "example-macos.toml"), env={})
        self.assertEqual((s.local.pinning, s.local.cpus, s.local.mock_cpus), ("none", [], []))

    def test_pinning_none_with_cpus_is_still_a_contradiction(self):
        with self.assertRaises(site.SiteError):
            site.from_dict({"site": {"name": "x", "backend": "local"}, "local": {"pinning": "none", "cpus": "1"}}, env={})


if __name__ == "__main__":
    unittest.main()
