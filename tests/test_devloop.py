"""devloop workloads: N/A where an arm has no such step, a fresh HOME for the first run, the seed restored afterwards."""
import types
import unittest

from buffon import workloads
from buffon.workloads import devloop
from buffon.workloads.overhead import Skip


def arm(kind, seed="/seed"):
    return types.SimpleNamespace(id="a", install_kind=kind, seed_dir=seed, binary="/b", install_dir="/d", record={}, skip=None)


class Applicability(unittest.TestCase):
    def test_the_three_workloads_are_registered_as_the_devloop_family(self):
        reg = workloads.load_all()
        self.assertEqual({w for w in reg if w.startswith("devloop/")}, {"devloop/install", "devloop/build", "devloop/first-run"})
        self.assertTrue(all(reg[w].family == "devloop" for w in reg if w.startswith("devloop/")))

    def test_an_arm_with_no_install_step_is_not_applicable_to_install_or_build(self):
        for fn in (devloop.one_install, devloop.one_build):
            with self.assertRaisesRegex(Skip, "no install step"):
                fn(types.SimpleNamespace(opts=None, work="/tmp"), arm(None))

    def test_source_arms_are_built_and_the_others_installed_never_both(self):
        ctx = types.SimpleNamespace(opts=types.SimpleNamespace(cache_dir="/nonexistent"), work="/tmp")
        with self.assertRaisesRegex(Skip, "see devloop/build"):
            devloop.one_install(ctx, arm("source"))
        with self.assertRaisesRegex(Skip, "see devloop/install"):
            devloop.one_build(ctx, arm("artifact"))


class FirstRun(unittest.TestCase):
    def test_the_first_run_has_no_seed_and_the_arms_seed_is_restored(self):
        seen = {}

        class Boom(Exception):
            pass

        def harness(a, scenario, **kw):
            seen["seed_at_harness"] = a.seed_dir
            raise Boom()
        a = arm("artifact", seed="/the/seed")
        a.supports_mode = lambda mode: True
        a.supports_api = lambda api: True
        a.cannot_run = {}
        ctx = types.SimpleNamespace(harness=harness, opts=types.SimpleNamespace(timeout=60), supports=lambda arm_, scenario: True)
        with self.assertRaises(Boom):
            devloop.one_first_run(ctx, a)
        self.assertIsNone(seen["seed_at_harness"])
        self.assertEqual(a.seed_dir, "/the/seed")
