"""Preflight: host class A (dedicated, publishable) or B (shared, provisional), whole physical cores, quota refusal."""
import unittest
from unittest import mock

from buffon.runner import preflight


def host(**kw):
    """A dedicated, well-configured host unless a test breaks one thing."""
    args = dict(cpus=[4, 5], mock_cpus=[6], claim="B", online=set(range(16)), isolated={4, 5, 6}, siblings=lambda c: [c], node_of=lambda c: 0, quota=[], partition=False,
                governors={4: "performance", 5: "performance"}, turbo_off=True, runnable=lambda cpus: 0)
    args.update(kw)
    return preflight.run(**args)


def failed(report):
    return {c["name"] for c in report["checks"] if not c["ok"]}


class ClockClaim(unittest.TestCase):
    """A virtual machine shows no cpufreq or turbo interface: only the site's claim can make it class A, and only when nothing is readable."""

    def vm(self, **kw):
        # turbo_off=None makes preflight read this host's own turbo files, and a host that has them (a cloud VM on a boosting CPU) shows "turbo is on": a VM that shows neither is described by hiding them.
        real = preflight.factlib._read
        hidden = (f"{preflight.SYS}/cpu/intel_pstate/no_turbo", f"{preflight.SYS}/cpu/cpufreq/boost")
        with mock.patch.object(preflight.factlib, "_read", lambda path, default=None: default if path in hidden else real(path, default)):
            return host(governors={4: None, 5: None}, turbo_off=None, **kw)

    def test_without_the_claim_an_unreadable_clock_and_turbo_state_is_class_b(self):
        self.assertEqual((self.vm()["class"], "turbo_off" in failed(self.vm())), ("B", True))

    def test_with_the_claim_a_vm_that_shows_neither_is_class_a_and_says_the_claim_is_not_verified(self):
        r = self.vm(clock_claim="hypervisor")
        self.assertEqual((r["class"], r["reasons"]), ("A", []))
        self.assertIn("not verified", next(c["detail"] for c in r["checks"] if c["name"] == "turbo_off"))

    def test_the_claim_never_overrides_a_readable_scaling_governor_or_a_readable_turbo_state(self):
        self.assertEqual(failed(host(governors={4: "powersave", 5: "powersave"}, clock_claim="hypervisor")), {"fixed_clock"})
        self.assertEqual(failed(host(turbo_off=False, clock_claim="hypervisor")), {"turbo_off"})
        self.assertEqual(failed(host(governors={4: "performance", 5: "performance"}, turbo_off=None, clock_claim="hypervisor")), {"turbo_off"})   # a readable governor means the machine is not the blind VM the claim is for

    def test_the_claim_is_not_a_dedicated_claim(self):
        self.assertEqual(self.vm(isolated=set(), clock_claim="hypervisor")["class"], "B")


class Classes(unittest.TestCase):
    def test_an_isolated_whole_core_single_node_fixed_clock_turbo_off_host_is_class_a(self):
        r = host()
        self.assertEqual((r["class"], r["reasons"]), ("A", []))
        self.assertTrue(preflight.satisfies(r, "A"))

    def test_cpus_that_are_not_exclusive_make_class_b_unless_a_dedicated_host_is_claimed_and_idle(self):
        self.assertEqual(failed(host(isolated=set())), {"exclusive_cpus"})
        self.assertEqual(host(isolated=set())["class"], "B")
        self.assertEqual(host(isolated=set(), claim="A")["class"], "A")                       # claimed dedicated and nothing else is running on them
        busy = host(isolated=set(), claim="A", runnable=lambda cpus: 3)
        self.assertEqual(busy["class"], "B")
        self.assertIn("3 foreign thread(s) running now", busy["reasons"][0])
        self.assertEqual(host(isolated=set(), partition=True)["class"], "A")                  # an exclusive cpuset partition counts as isolated

    def test_an_smt_sibling_outside_the_reserved_set_breaks_whole_cores(self):
        r = host(siblings=lambda c: [c, c + 8])
        self.assertEqual(failed(r), {"whole_cores"})
        self.assertIn("[12, 13, 14]", r["reasons"][0])
        self.assertEqual(r["class"], "B")
        self.assertEqual(host(siblings=lambda c: [c, c + 8], online={4, 5, 6, 0, 1, 2, 3})["class"], "A")   # offline siblings are fine

    def test_a_sibling_inside_the_reserved_set_is_fine(self):
        self.assertEqual(host(cpus=[4, 12], mock_cpus=[5], isolated={4, 5, 12}, siblings=lambda c: {4: [4, 12], 12: [4, 12], 5: [5]}[c])["class"], "A")

    def test_no_housekeeping_cpu_left_is_not_class_a(self):
        self.assertEqual(failed(host(online={4, 5, 6})), {"housekeeping"})

    def test_cpus_on_two_numa_nodes_are_not_class_a(self):
        self.assertEqual(failed(host(node_of=lambda c: c % 2)), {"one_numa_node"})
        self.assertEqual(failed(host(node_of=lambda c: None)), {"one_numa_node"})

    def test_scaling_governor_and_turbo_decide_the_clock_checks(self):
        self.assertEqual(failed(host(governors={4: "powersave", 5: "powersave"})), {"fixed_clock"})
        self.assertEqual(failed(host(turbo_off=False)), {"turbo_off"})
        self.assertEqual(failed(host(turbo_off=None)), {"turbo_off"})     # unknown is not off

    def test_a_quota_above_the_cpus_in_use_is_class_b_and_one_below_refuses_the_run(self):
        ok = host(quota=[("/lane.scope", "2400000 100000")])
        self.assertEqual((ok["class"], ok["refusals"], failed(ok)), ("B", [], {"no_cpu_quota"}))
        bad = host(quota=[("/lane.scope", "200000 100000")])        # 2 CPUs for 3 in use
        self.assertEqual(len(bad["refusals"]), 1)
        self.assertFalse(preflight.satisfies(bad, "B"))
        self.assertFalse(preflight.satisfies(bad, "A"))

    def test_no_pinned_cpus_is_class_b(self):
        self.assertEqual(preflight.run([], online={0, 1}, isolated=set(), siblings=lambda c: [c], node_of=lambda c: 0, quota=[], partition=False, governors={}, turbo_off=True)["class"], "B")

    def test_a_class_b_report_does_not_satisfy_a_class_a_requirement(self):
        r = host(isolated=set())
        self.assertTrue(preflight.satisfies(r, "B"))
        self.assertFalse(preflight.satisfies(r, "A"))
