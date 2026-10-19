# SPDX-License-Identifier: Apache-2.0
"""The trust badge: every reason, every badge, and that a failed gate is a label and never a discard."""
import os
import tempfile
import unittest

from buffon import trust


def raw(cls="A", calibration=True, rounds=12, quiet=True, perf=True, isolation_comparable=True, gate=None, reasons=(), cal_cv=0.01):
    samples = [{"scenario": "overhead/print", "api": "x", "arm": "a", "round": r, "warmup": r == 0} for r in range(rounds + 1)]
    return {"run": {"host_class": cls, "preflight": {"reasons": list(reasons)}, "perf": {"available": perf, "reason": "perf_event_open refused"}, "quiet_gate": gate or {},
                    "isolation": {"comparable": isolation_comparable}},
            "hardware": {"quiet_dedicated": quiet, "reasons": []}, "calibration": {"passed": calibration, "max_cv": cal_cv, "gate": 0.05} if calibration is not None else None, "samples": samples}


class Badges(unittest.TestCase):
    def test_a_dedicated_host_that_was_reproduced_and_meets_every_rule_is_verified(self):
        b = trust.badge(raw(), reproduced=True)
        self.assertEqual((b["badge"], b["strict_problems"]), ("Verified", []))

    def test_a_dedicated_host_not_reproduced_is_dedicated_and_says_so(self):
        b = trust.badge(raw())
        self.assertEqual(b["badge"], "Dedicated")
        self.assertTrue(any("not yet reproduced" in r for r in b["reasons"]))

    def test_a_shared_host_is_shared_with_its_reasons_even_when_reproduced(self):
        b = trust.badge(raw(cls="B", quiet=False, reasons=["other tasks may be scheduled on the bench CPUs", "SMT siblings [5] of the bench CPUs are online"]), reproduced=True)
        self.assertEqual(b["badge"], "Shared")
        self.assertIn("SMT siblings [5] of the bench CPUs are online", b["reasons"])

    def test_a_calibration_above_the_limit_is_noisy_whatever_the_host_class(self):
        for cls in ("A", "B"):
            b = trust.badge(raw(cls=cls, calibration=False, cal_cv=0.056), reproduced=True)
            self.assertEqual(b["badge"], "Noisy")
            self.assertTrue(any("5.6%" in r and "5%" in r for r in b["reasons"]))

    def test_a_quiet_gate_that_gave_up_is_noisy(self):
        b = trust.badge(raw(gate={"timeouts": 2, "waits": 4, "max_wait_ms": 9000}))
        self.assertEqual(b["badge"], "Noisy")
        self.assertTrue(any("gave up waiting" in r for r in b["reasons"]))

    def test_waits_alone_are_a_reason_not_a_downgrade(self):
        b = trust.badge(raw(gate={"timeouts": 0, "waits": 3, "max_wait_ms": 4000}))
        self.assertEqual(b["badge"], "Dedicated")
        self.assertTrue(any("waited for the host" in r for r in b["reasons"]))

    def test_missing_counters_are_a_reason_and_cpu_time_is_the_named_headline(self):
        b = trust.badge(raw(perf=False))
        self.assertEqual((b["headline"], b["badge"]), ("CPU time", "Dedicated"))
        self.assertTrue(any("no instruction counters" in r for r in b["reasons"]))
        self.assertEqual(trust.badge(raw(perf=True))["headline"], "instructions")

    def test_each_strict_rule_denies_verified_and_is_listed(self):
        cases = {"measured rounds in the thinnest": raw(rounds=8), "not labelled quiet": raw(quiet=False), "no calibration": raw(calibration=None), "uncontained": raw(isolation_comparable=False)}
        for what, r in cases.items():
            b = trust.badge(r, reproduced=True)
            self.assertEqual(b["badge"], "Dedicated", what)
            self.assertTrue(any(what in p for p in b["strict_problems"]), (what, b["strict_problems"]))

    def test_realised_rounds_counts_the_thinnest_cell_without_warm_up_or_failures(self):
        r = raw(rounds=10)
        r["samples"].append({"scenario": "overhead/version", "api": None, "arm": "a", "round": 1, "warmup": False})
        r["samples"].append({"scenario": "overhead/version", "api": None, "arm": "a", "round": 2, "warmup": False, "failure": "x"})
        self.assertEqual(trust.realised_rounds(r), 1)
        self.assertIsNone(trust.realised_rounds({"samples": []}))

    def test_the_worst_badge_of_several_runs_wins(self):
        self.assertEqual(trust.worst(["Verified", "Noisy", "Shared"]), "Noisy")
        self.assertEqual(trust.worst(["Verified", "Dedicated"]), "Dedicated")

    def test_a_line_names_the_badge_the_class_and_the_first_reasons(self):
        line = trust.line(trust.badge(raw(cls="B", quiet=False, reasons=["a", "b", "c", "d"])))
        self.assertTrue(line.startswith("Shared (host class B): a; b; c"))
        self.assertIn("more", line)


class InTheReport(unittest.TestCase):
    def render(self, tmp, name):
        from buffon.report import render
        from buffon.runner import raw as rawlib
        from tests.test_report import raw_of, series
        run = os.path.join(tmp, "run")
        if not os.path.exists(run):
            rawlib.write(raw_of(series()), run)
        with open(render.render([run], os.path.join(tmp, name))) as f:
            return f.read()

    def test_the_report_leads_with_the_trust_badge_and_every_measurement_stays(self):
        text = self.render(tempfile.mkdtemp(), "out")
        self.assertIn("**Trust: ", text.split("\n", 4)[2])
        self.assertIn("Every measurement is recorded and shown whatever the label", text)

    def test_a_reproduction_file_never_changes_the_generated_report(self):
        # buffon verify regenerates the report from raw.json and compares; a reproduction added later must not make the report differ
        tmp = tempfile.mkdtemp()
        before = self.render(tmp, "a")
        with open(os.path.join(tmp, "run", "reproduction.json"), "w") as f:
            f.write('{"totals": {"cells": 1, "reproduced": 1}}')
        self.assertEqual(before, self.render(tmp, "b"))


if __name__ == "__main__":
    unittest.main()
