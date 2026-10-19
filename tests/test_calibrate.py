# SPDX-License-Identifier: Apache-2.0
"""The calibration gate: the reference arm against its own A/A copy, refused above the CV gate."""
import itertools
import types
import unittest

from buffon.runner import calibrate, engine
from buffon.workloads import overhead


def arm(name, twin_of=None, apis=("openai-completions", "anthropic-messages"), modes=("print",)):
    return types.SimpleNamespace(id=name, label=name, twin_of=twin_of, apis=list(apis), supports_mode=lambda m: m in modes, supports_api=lambda a: a in apis)


class Calibration(unittest.TestCase):
    def run_cal(self, values, instances, reference="pi-node", rounds=12, warmup=1):
        plan = types.SimpleNamespace(warmup=warmup, calibration_rounds=rounds, api="openai-completions", reference=reference)
        session = types.SimpleNamespace(plan=plan, log=lambda *_: None)
        ctx = types.SimpleNamespace(opts=types.SimpleNamespace(api=None), release=lambda: None)
        seen = []
        it = None if callable(values) else iter(values)

        def fake_print(c, a):
            seen.append(a.id)
            return values(a.id) if callable(values) else next(it)
        saved = overhead.RUNNERS["print"]
        overhead.RUNNERS["print"] = fake_print
        try:
            return calibrate.run(session, ctx, instances), seen
        finally:
            overhead.RUNNERS["print"] = saved

    def test_steady_cpu_passes_and_noisy_cpu_fails(self):
        a = [arm("pi-node"), arm("pi-node-b", twin_of="pi-node")]
        steady = ({"cpu_ms": 100.0 + (i % 3)} for i in itertools.count())
        out, _ = self.run_cal(steady, a)
        self.assertTrue(out["passed"])
        self.assertLess(out["max_cv"], engine.CV_GATE)
        noisy = ({"cpu_ms": 100.0 if i % 2 else 130.0} for i in itertools.count())
        out, _ = self.run_cal(noisy, a)
        self.assertFalse(out["passed"])
        self.assertGreater(out["max_cv"], engine.CV_GATE)

    def test_the_gate_is_the_worse_copy(self):
        a = [arm("pi-node"), arm("pi-node-b", twin_of="pi-node")]
        n = {"pi-node": 0, "pi-node-b": 0}

        def by_arm(arm_id):
            n[arm_id] += 1
            return {"cpu_ms": 100.0 if arm_id == "pi-node" or n[arm_id] % 2 else 140.0}
        out, seen = self.run_cal(by_arm, a)
        self.assertEqual(out["cv"]["pi-node"], 0.0)
        self.assertGreater(out["cv"]["pi-node-b"], engine.CV_GATE)
        self.assertEqual(out["max_cv"], out["cv"]["pi-node-b"])
        self.assertFalse(out["passed"])
        self.assertEqual(seen.count("pi-node"), seen.count("pi-node-b"))

    def test_failed_runs_fail_the_gate(self):
        a = [arm("pi-node"), arm("pi-node-b", twin_of="pi-node")]
        out, _ = self.run_cal(({"failure": "boom"} if i % 2 else {"cpu_ms": 100.0} for i in itertools.count()), a)
        self.assertFalse(out["passed"])

    def test_the_reference_arm_is_calibrated_whatever_the_arm_order(self):
        a = [arm("codex", apis=("openai-responses",)), arm("omp"), arm("pi-node"), arm("omp-b", twin_of="omp"), arm("pi-node-b", twin_of="pi-node")]
        out, seen = self.run_cal(({"cpu_ms": 100.0} for _ in itertools.count()), a)
        self.assertEqual(out["arm"], "pi-node")
        self.assertEqual(set(seen), {"pi-node", "pi-node-b"})

    def test_without_the_reference_the_first_eligible_arm_is_used_and_named(self):
        a = [arm("codex", apis=("openai-responses",)), arm("omp"), arm("omp-b", twin_of="omp")]
        out, seen = self.run_cal(({"cpu_ms": 100.0} for _ in itertools.count()), a)
        self.assertEqual(out["arm"], "omp")
        self.assertEqual(set(seen), {"omp", "omp-b"})


if __name__ == "__main__":
    unittest.main()
