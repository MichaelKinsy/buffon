# SPDX-License-Identifier: Apache-2.0
"""M5: per-run isolation is proven, not claimed. Every sample gets a fresh home, records what the home held before and after the process, and `buffon verify` rejects a run without that proof."""
import copy
import os
import tempfile
import types
import unittest

from buffon import verify
from buffon.runner import engine, harness as harnesslib, raw as rawlib
from buffon.runner.harness import Harness
from tests.test_engine import FakeCtx, arm, runner
from tests.test_report import raw_of, series
from buffon.workloads import Workload


def stub_harness(work, tag="t"):
    a = types.SimpleNamespace(id="x", env={"PI_OFFLINE": "1"}, spec={"state": {"dirs": []}}, path_dirs=[], writer_path=lambda: None)
    server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
    saved = Harness.__init__.__globals__["load_writer"]
    Harness.__init__.__globals__["load_writer"] = lambda arm: (lambda spec: {})
    try:
        return Harness(a, work, server, tag=tag)
    finally:
        Harness.__init__.__globals__["load_writer"] = saved


class Fingerprint(unittest.TestCase):
    def test_the_digest_covers_paths_sizes_and_contents_and_ignores_nothing_a_process_writes(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "a"))
            with open(os.path.join(d, "a", "f"), "w") as f:
                f.write("one")
            before = harnesslib.digest(harnesslib.fingerprint(d))
            self.assertEqual(before, harnesslib.digest(harnesslib.fingerprint(d)))
            with open(os.path.join(d, "a", "f"), "w") as f:
                f.write("two")
            self.assertNotEqual(before, harnesslib.digest(harnesslib.fingerprint(d)))
            with open(os.path.join(d, "a", "f"), "w") as f:
                f.write("one")
            self.assertEqual(before, harnesslib.digest(harnesslib.fingerprint(d)))
            os.makedirs(os.path.join(d, "empty"))
            self.assertNotEqual(before, harnesslib.digest(harnesslib.fingerprint(d)))

    def test_a_large_file_is_recorded_by_size_and_a_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "big"), "wb") as f:
                f.write(b"x" * (harnesslib.CONTENT_LIMIT + 1))
            os.symlink("/nonexistent/target", os.path.join(d, "link"))
            fp = harnesslib.fingerprint(d)
            self.assertEqual(fp["big"], ("file", harnesslib.CONTENT_LIMIT + 1, None))
            self.assertEqual(fp["link"][0], "link")


class FreshHome(unittest.TestCase):
    def test_two_samples_of_one_arm_start_from_the_same_home_and_the_proof_counts_what_the_process_wrote(self):
        with tempfile.TemporaryDirectory() as work:
            h1 = stub_harness(work)
            with open(os.path.join(h1.home, "residue"), "w") as f:
                f.write("a process wrote this")
            proof = h1.home_proof()
            self.assertTrue(proof["fresh"])
            self.assertEqual((proof["written"], proof["removed"]), (1, 0))
            self.assertEqual(proof["post_files"], proof["pre_files"] + 1)
            self.assertNotEqual(proof["pre_sha256"], proof["post_sha256"])
            h1.cleanup()
            h2 = stub_harness(work)
            self.assertEqual(h2.home_proof()["pre_sha256"], proof["pre_sha256"])
            self.assertFalse(os.path.exists(os.path.join(h2.home, "residue")))

    def test_a_leftover_home_from_a_failed_cleanup_is_removed_and_the_sample_says_so(self):
        with tempfile.TemporaryDirectory() as work:
            h1 = stub_harness(work)
            with open(os.path.join(h1.home, "residue"), "w") as f:
                f.write("left behind")           # no cleanup(): the directory survives into the next sample
            h2 = stub_harness(work)
            self.assertFalse(os.path.exists(os.path.join(h2.home, "residue")))
            proof = h2.home_proof()
            self.assertFalse(proof["fresh"])
            h2.cleanup()
            self.assertEqual(proof["pre_sha256"], stub_harness(work).home_proof()["pre_sha256"])

    def test_the_engine_records_the_proof_on_the_sample_and_fresh_needs_every_harness_fresh(self):
        with tempfile.TemporaryDirectory() as work:
            h1, h2 = stub_harness(work, "a"), stub_harness(work, "b")
            h2.stale = True

            class Ctx(FakeCtx):
                def harnesses_for(self, arm):
                    return [h1, h2]
            w = Workload(id="t/w", family="t", fn=lambda ctx, a: {"cpu_ms": 1.0})
            r = runner([w], [arm("a")], rounds=1, warmup=0, apis=["openai-completions"], allow_short=True)
            r.measure(Ctx(), engine.with_twins(r.plan.arms, "none"))
            home = r.samples[0]["home"]
            self.assertEqual((home["fresh"], home["homes"]), (False, 2))
            rawlib._check_home(home, "sample")


class Verify(unittest.TestCase):
    def raw(self):
        raw = raw_of(series())
        for s in raw["samples"]:
            s["home"] = {"fresh": True, "pre_files": 3, "pre_sha256": "a" * 64, "post_files": 4, "post_sha256": "b" * 64, "written": 1, "removed": 0, "homes": 1}
        return raw

    def test_a_run_with_a_proof_on_every_sample_passes(self):
        self.assertEqual(verify.check_home(".", self.raw()), [])

    def test_a_missing_or_malformed_proof_is_a_problem_naming_the_first_sample(self):
        raw = self.raw()
        del raw["samples"][3]["home"]
        raw["samples"][5]["home"] = {"fresh": True}
        problems = verify.check_home(".", raw)
        self.assertEqual(len(problems), 1)
        self.assertIn("2 sample(s) carry no home isolation proof", problems[0])

    def test_a_leftover_home_is_a_problem(self):
        raw = self.raw()
        raw["samples"][2]["home"]["fresh"] = False
        self.assertIn("leftover home", verify.check_home(".", raw)[0])

    def test_a_round_that_started_from_another_state_is_a_problem_and_other_arms_may_differ(self):
        raw = self.raw()
        raw["samples"][0]["home"]["pre_sha256"] = "c" * 64
        problems = verify.check_home(".", raw)
        self.assertEqual(len(problems), 1)
        self.assertIn("differed between samples", problems[0])
        other = self.raw()
        for s in other["samples"]:
            if s["arm"] == "other":
                s["home"]["pre_sha256"] = "d" * 64
        self.assertEqual(verify.check_home(".", other), [])

    def test_soak_reliability_and_a_sample_that_never_started_are_exempt(self):
        raw = self.raw()
        raw["samples"] += [{"arm": "x", "scenario": "soak/realistic", "api": None, "round": 0, "warmup": False}, {"arm": "x", "scenario": "reliability/faults", "api": None, "round": 0, "warmup": False},
                           {"arm": "x", "scenario": "overhead/print", "api": None, "round": 0, "warmup": False, "quiet_gave_up": True, "failure": "not quiet"}]
        self.assertEqual(verify.check_home(".", raw), [])

    def test_raw_validation_rejects_a_malformed_home_record(self):
        good = self.raw()["samples"][0]["home"]
        rawlib._check_home(good, "s")
        for bad in (dict(good, fresh="yes"), dict(good, pre_sha256="xyz"), dict(good, written=-1), {k: v for k, v in good.items() if k != "homes"}, "home"):
            with self.assertRaises(rawlib.RawError):
                rawlib._check_home(bad, "s")


if __name__ == "__main__":
    unittest.main()
