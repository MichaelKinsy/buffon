# SPDX-License-Identifier: Apache-2.0
"""Promotion: the record CI writes after re-validating a submission, and the immutability it gives."""
import json
import os
import stat
import tempfile
import unittest

import subprocess

from buffon.submit import check, index, manifest, promote
from tests.submit_fixtures import make_repo, sealed_dir, sh, submit_raw


class Promote(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def test_in_place_writes_a_record_that_names_the_manifest_and_makes_files_read_only(self):
        d = sealed_dir(self.repo)
        target, rec = promote.promote(d, self.repo, environ={"GITHUB_RUN_ID": "77", "GITHUB_REPOSITORY": "o/r"})
        self.assertEqual(target, d)
        self.assertEqual((rec["notes"], rec["manifest_sha256"]), (0, manifest.digest(d)))
        self.assertEqual(rec["ci"], {"run_id": "77", "repository": "o/r"})
        self.assertEqual(promote.current(d), rec)
        for name in ("raw.json", "MANIFEST.sha256", "promotion.json", "report.md"):
            self.assertFalse(os.stat(os.path.join(d, name)).st_mode & stat.S_IWUSR, name)
        self.assertEqual(manifest.check(d), [], "promotion.json and the report are not sealed files")

    def test_a_copy_goes_to_the_results_directory_under_a_new_id_and_is_never_replaced(self):
        d = sealed_dir(self.repo, name="mine")
        results = tempfile.mkdtemp()
        target, _ = promote.promote(d, self.repo, to=results)
        self.assertEqual(target, os.path.join(results, "mine"))
        self.assertTrue(check.verify(target, self.repo, is_submission=True).accepted)
        self.assertFalse(os.path.exists(os.path.join(d, "promotion.json")), "the submitter's directory is left alone")
        with self.assertRaises(promote.PromotionRefused) as e:
            promote.promote(d, self.repo, to=results)
        self.assertIn("never replaced", str(e.exception))
        t2, _ = promote.promote(d, self.repo, to=results, run_id="mine-2")
        self.assertTrue(t2.endswith("mine-2"))

    def test_a_run_that_does_not_verify_is_not_promoted_and_leaves_nothing(self):
        d = sealed_dir(self.repo, submit_raw(self.repo, telemetry=False))
        results = tempfile.mkdtemp()
        with self.assertRaises(promote.PromotionRefused):
            promote.promote(d, self.repo, to=results)
        self.assertEqual(os.listdir(results), [])
        self.assertFalse(os.path.exists(os.path.join(d, "promotion.json")))

    def test_a_record_stops_counting_when_the_directory_changes(self):
        d = sealed_dir(self.repo)
        promote.promote(d, self.repo)
        rec = promote.read(d)
        for name in ("raw.json", "MANIFEST.sha256"):
            os.chmod(os.path.join(d, name), 0o644)
        with open(os.path.join(d, "raw.json"), "a") as f:
            f.write(" ")
        manifest.write(d)                                   # even a re-sealed directory has another digest
        self.assertIsNotNone(promote.read(d))
        self.assertIsNone(promote.current(d))
        self.assertEqual(rec["manifest_sha256"], promote.read(d)["manifest_sha256"])

    def test_a_looser_quiet_gate_is_listed_and_does_not_reject_the_run(self):
        raw = submit_raw(self.repo)
        raw["run"]["quiet_gate"]["max_busy"] = 0.25
        r = check.verify(sealed_dir(self.repo, raw), self.repo, is_submission=True)
        self.assertTrue(r.accepted)
        self.assertIn("quiet_gate", {c["id"] for c in r.checks if c["status"] == "warning"})
        raw["run"]["quiet_gate"]["max_busy"] = 0.10
        r = check.verify(sealed_dir(self.repo, raw), self.repo, is_submission=True)
        self.assertEqual((r.accepted, [c for c in r.checks if c["status"] == "warning"]), (True, []), "the default itself is not a note")
        raw["run"]["quiet_gate"]["max_busy"] = 0.02
        self.assertTrue(check.verify(sealed_dir(self.repo, raw), self.repo, is_submission=True).accepted)

    def test_ci_identity_without_ci_is_local(self):
        self.assertEqual(promote.ci_identity({}), {"runner": "local"})


class Tiers(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.results = tempfile.mkdtemp()

    def add(self, name, promoted=True, operator="A. Person", reproduces=None, **kw):
        d = sealed_dir(self.repo, submit_raw(self.repo, **kw), name=name, base=self.results)
        with open(os.path.join(d, "submission.toml"), "w") as f:
            f.write(f'operator = "{operator}"\nhardware = "dedicated bare metal"\nindependent = true\n' + (f'reproduces = "{reproduces}"\n' if reproduces else ""))
        manifest.write(d)
        if promoted:
            promote.promote(d, self.repo)
        return d

    def rows(self):
        return {r["id"]: r for r in index.build(self.results, self.repo)}

    def test_an_unpromoted_run_is_self_reported_and_never_a_headline(self):
        self.add("a", promoted=False)
        r = self.rows()["a"]
        self.assertEqual((r["tier"], r["headline"]), ("self-reported", False))

    def test_a_promoted_run_on_quiet_hardware_is_a_headline(self):
        self.add("a")
        r = self.rows()["a"]
        self.assertEqual((r["tier"], r["headline"], r["notes"]), ("ci-revalidated", True, 0))

    def test_a_run_with_a_note_is_listed_with_its_notes_and_is_still_a_headline(self):
        def steal(s):
            if s["arm"] == "other" and not s["warmup"] and s["round"] == 3:
                s["telemetry"]["system"]["cpuset"]["cpuset_steal_ms"] = 60.0
        self.add("y", mutate=steal)
        r = self.rows()["y"]
        self.assertEqual((r["notes"], r["headline"]), (1, True))
        self.assertIn("steal_share", r["noted_checks"])
        self.assertIn("notes: steal_share", index.markdown(list(self.rows().values())))

    def test_a_throttled_run_is_promoted_and_indexed_with_its_note(self):
        self.add("throttled", mutate=lambda s: s["telemetry"]["system"]["cgroup"].update(throttled_periods=1) if s["arm"] == "other" else None)
        self.assertIn("throttled_samples", self.rows()["throttled"]["noted_checks"])

    def test_a_promoted_run_that_was_edited_falls_back_to_self_reported(self):
        d = self.add("a")
        for name in ("MANIFEST.sha256", "promotion.json"):
            os.chmod(os.path.join(d, name), 0o644)
        os.chmod(os.path.join(d, "raw.json"), 0o644)
        with open(os.path.join(d, "raw.json"), "a") as f:
            f.write(" ")
        manifest.write(d)
        self.assertEqual(self.rows()["a"]["tier"], "self-reported")

    def test_a_maintainer_reproduction_that_reproduced_everything_lifts_the_original(self):
        self.add("orig")
        rep = self.add("repro", operator="M. Tainer", reproduces="orig")
        from buffon.submit import reproduce
        c = reproduce.compare(os.path.join(self.results, "orig"), rep)
        self.assertEqual(c["totals"]["reproduced"], c["totals"]["cells"])
        for name in os.listdir(rep):
            os.chmod(os.path.join(rep, name), 0o644)
        os.chmod(rep, 0o755)
        reproduce.write(c, rep)
        self.assertEqual(self.rows()["orig"]["tier"], "ci-revalidated", "the reproducer is not a listed maintainer yet")
        with open(os.path.join(self.results, "MAINTAINERS.toml"), "w") as f:
            f.write('operators = ["M. Tainer"]\n')
        self.assertEqual(self.rows()["orig"]["tier"], "maintainer-reproduced")
        c["totals"]["reproduced"] -= 1
        reproduce.write(c, rep)
        self.assertEqual(self.rows()["orig"]["tier"], "ci-revalidated", "a reproduction that did not reproduce everything does not count")

    def test_a_withdrawn_run_stays_listed_with_its_reason_and_is_no_headline(self):
        self.add("a")
        with open(os.path.join(self.results, "WITHDRAWN.toml"), "w") as f:
            f.write('[[withdrawn]]\nid = "a"\nreason = "methodology error"\n')
        r = self.rows()["a"]
        self.assertEqual((r["withdrawn"], r["headline"]), ("methodology error", False))
        self.assertIn("WITHDRAWN: methodology error", index.markdown(list(self.rows().values())))


class Immutable(unittest.TestCase):
    def test_a_base_that_moved_after_the_fork_is_not_this_changes_edit(self):
        repo = make_repo()
        res = os.path.join(repo, "results")
        os.makedirs(os.path.join(res, "a"))
        with open(os.path.join(res, "a", "raw.json"), "w") as f:
            f.write("1")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "base")
        fork = sh(repo, "git", "rev-parse", "HEAD")
        trunk = sh(repo, "git", "rev-parse", "--abbrev-ref", "HEAD")
        sh(repo, "git", "checkout", "-q", "-b", "pr")
        os.makedirs(os.path.join(res, "b"))
        with open(os.path.join(res, "b", "raw.json"), "w") as f:
            f.write("submitted")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "pr adds b")
        sh(repo, "git", "checkout", "-q", trunk)
        os.makedirs(os.path.join(res, "c"))
        with open(os.path.join(res, "c", "raw.json"), "w") as f:
            f.write("merged meanwhile")
        with open(os.path.join(res, "WITHDRAWN.toml"), "w") as f:
            f.write("# a maintainer's list edit that landed on the base after the fork\n")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "trunk moves")
        sh(repo, "git", "checkout", "-q", "pr")
        self.assertEqual(index.immutable_problems(res, trunk, repo), [])      # a two-dot diff against the moved base would name c/raw.json and WITHDRAWN.toml
        with open(os.path.join(res, "a", "raw.json"), "w") as f:
            f.write("edited")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "pr edits a")
        self.assertEqual([x.split(":")[0] for x in index.immutable_problems(res, trunk, repo)], ["results/a/raw.json"])
        self.assertNotEqual(fork, sh(repo, "git", "rev-parse", trunk))

    def test_only_added_files_in_run_directories_and_the_index_may_change(self):
        repo = make_repo()
        os.makedirs(os.path.join(repo, "results", "a"))
        for rel in ("results/a/raw.json", "results/index.json"):
            with open(os.path.join(repo, rel), "w") as f:
                f.write("1")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "base")
        base = sh(repo, "git", "rev-parse", "HEAD")
        res = os.path.join(repo, "results")
        os.makedirs(os.path.join(res, "b"))
        with open(os.path.join(res, "b", "raw.json"), "w") as f:
            f.write("new run")
        with open(os.path.join(res, "a", "report.md"), "w") as f:
            f.write("regenerated")
        with open(os.path.join(res, "index.json"), "w") as f:
            f.write("2")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "ok")
        self.assertEqual(index.immutable_problems(res, base, repo), [])
        mid = sh(repo, "git", "rev-parse", "HEAD")
        for d in ("a", "b"):   # review: a pull request that carries promotion.json made its own run ci-revalidated (and headline-eligible)
            with open(os.path.join(res, d, "promotion.json"), "w") as f:
                f.write("{}")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "self-promoted")
        self.assertEqual(sorted(x.split(":")[0] for x in index.immutable_problems(res, mid, repo)), ["results/a/promotion.json", "results/b/promotion.json"])
        sh(repo, "git", "rm", "-q", "results/a/promotion.json", "results/b/promotion.json")
        sh(repo, "git", "commit", "-q", "-m", "unpromoted")
        with open(os.path.join(res, "a", "raw.json"), "w") as f:
            f.write("edited")
        os.unlink(os.path.join(res, "b", "raw.json"))
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "bad")
        p = index.immutable_problems(res, base, repo)
        self.assertEqual(len(p), 1, p)
        self.assertIn("results/a/raw.json: modified", p[0])
        sh(repo, "git", "mv", "results/a/report.md", "results/a/other.md")
        sh(repo, "git", "commit", "-q", "-m", "mv")
        self.assertTrue(any("results/a/raw.json" in x for x in index.immutable_problems(res, base, repo)))

    def test_a_results_change_touches_nothing_outside_the_results_directory(self):
        # CI checks a results pull request with the base branch's code; a change that also edits code or a workflow would otherwise ride along unreviewed.
        repo = make_repo()
        res = os.path.join(repo, "results")
        os.makedirs(os.path.join(repo, "buffon"))
        os.makedirs(res)
        for rel in ("results/index.json", "buffon/verify.py"):
            with open(os.path.join(repo, rel), "w") as f:
                f.write("1")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "base")
        base = sh(repo, "git", "rev-parse", "HEAD")
        os.makedirs(os.path.join(res, "b"))
        with open(os.path.join(res, "b", "raw.json"), "w") as f:
            f.write("new run")
        with open(os.path.join(repo, "buffon", "verify.py"), "w") as f:
            f.write("accept everything")
        os.makedirs(os.path.join(repo, ".github", "workflows"))
        with open(os.path.join(repo, ".github", "workflows", "results.yml"), "w") as f:
            f.write("on: push")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "run plus code")
        for flag in (False, True):
            p = index.immutable_problems(res, base, repo, governance=flag)
            self.assertIn(".github/workflows/results.yml", [x.split(":")[0] for x in p], p)
            self.assertIn("buffon/verify.py", [x.split(":")[0] for x in p], p)
        self.assertEqual([x.split(":")[0] for x in index.immutable_problems(res, base, repo)], [".github/workflows/results.yml", "buffon/verify.py"])

    def test_the_governance_files_change_only_with_the_maintainers_flag(self):
        repo = make_repo()
        res = os.path.join(repo, "results")
        os.makedirs(res)
        with open(os.path.join(res, "index.json"), "w") as f:
            f.write("1")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "base")
        base = sh(repo, "git", "rev-parse", "HEAD")
        for name in ("MAINTAINERS.toml", "WITHDRAWN.toml"):
            with open(os.path.join(res, name), "w") as f:
                f.write("operators = []\n")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "gov")
        p = index.immutable_problems(res, base, repo)
        self.assertEqual(len(p), 2, p)
        self.assertTrue(all("governance file" in x for x in p))
        self.assertEqual(index.immutable_problems(res, base, repo, governance=True), [])
        os.makedirs(os.path.join(res, "sneaked"))   # review: the maintainers' flag must not carry a run directory along
        with open(os.path.join(res, "sneaked", "raw.json"), "w") as f:
            f.write("{}")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-q", "-m", "gov + run")
        p = index.immutable_problems(res, base, repo, governance=True)
        self.assertEqual([x.split(":")[0] for x in p], ["results/sneaked/raw.json"], p)
        self.assertIn("governance change", p[0])

    def test_an_unknown_ref_is_a_problem_not_silence(self):
        repo = make_repo()
        os.makedirs(os.path.join(repo, "results"))
        self.assertTrue(index.immutable_problems(os.path.join(repo, "results"), "no-such-ref", repo)[0].startswith("cannot compare"))


if __name__ == "__main__":
    unittest.main()
