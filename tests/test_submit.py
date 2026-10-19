# SPDX-License-Identifier: Apache-2.0
"""The submission path: sealing, verification, the results index, and what each rejection looks like."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from buffon import cli
from buffon.submit import check, index, manifest, submission
from tests.submit_fixtures import make_repo, sealed_dir, submit_raw
from tests.telemetry_fixtures import write_dir


def status(result, cid):
    return [c["status"] for c in result.checks if c["id"] == cid]


class Seal(unittest.TestCase):
    def test_a_sealed_directory_checks_clean_and_generated_files_are_not_sealed(self):
        d = tempfile.mkdtemp()
        write_dir(d, submit_raw(make_repo()))
        os.makedirs(os.path.join(d, "mock-requests"))
        with open(os.path.join(d, "mock-requests", "1.jsonl.gz"), "wb") as f:
            f.write(b"x")
        self.assertEqual(manifest.write(d), 3)
        self.assertEqual(manifest.check(d), [])
        for name in ("report.md", "rounds.csv", "health.json", "submission.toml"):
            with open(os.path.join(d, name), "w") as f:
                f.write("anything")
        os.makedirs(os.path.join(d, "plots"))
        with open(os.path.join(d, "plots", "a.svg"), "w") as f:
            f.write("<svg/>")
        self.assertEqual(manifest.check(d), [])

    def test_an_edited_removed_or_added_file_is_found(self):
        d = tempfile.mkdtemp()
        write_dir(d, submit_raw(make_repo()))
        manifest.write(d)
        with open(os.path.join(d, "raw.json"), "a") as f:
            f.write(" ")
        self.assertIn("raw.json differs", manifest.check(d)[0])
        os.unlink(os.path.join(d, "facts.json"))
        self.assertTrue(any("facts.json is listed" in p for p in manifest.check(d)))
        with open(os.path.join(d, "extra.log"), "w") as f:
            f.write("x")
        self.assertTrue(any("extra.log is not listed" in p for p in manifest.check(d)))

    def test_an_unsealed_directory_says_so(self):
        d = tempfile.mkdtemp()
        write_dir(d, submit_raw(make_repo()))
        self.assertIn("never sealed", manifest.check(d)[0])


class Verify(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def verify(self, raw=None, submission=True, **kw):
        d = sealed_dir(self.repo, raw)
        return check.verify(d, self.repo, is_submission=submission, **kw), d

    def errors(self, result):
        return {c["id"] for c in result.checks if c["status"] == "error"}

    def test_a_good_run_is_accepted_with_every_check_ok(self):
        result, d = self.verify()
        self.assertTrue(result.accepted, check.text(result, d))
        self.assertEqual(self.errors(result), set())
        self.assertEqual((result.health["notes"], result.health["summary"]), (0, "no notes"))
        self.assertEqual([c for c in result.checks if c["status"] == "warning"], [])
        self.assertIn("ACCEPTED, no notes", check.text(result, d))

    def test_a_run_changed_after_sealing_is_rejected(self):
        d = sealed_dir(self.repo)
        with open(os.path.join(d, "raw.json")) as f:
            raw = json.load(f)
        raw["samples"][5]["cpu_ms"] = 1.0
        with open(os.path.join(d, "raw.json"), "w") as f:
            json.dump(raw, f)
        self.assertEqual(self.errors(check.verify(d, self.repo, is_submission=True)), {"seal"})

    def test_shared_hardware_is_a_listed_note_for_a_check_and_for_a_submission(self):
        raw = submit_raw(self.repo)
        raw["hardware"] = {"class": "provisional", "quiet_dedicated": False, "reasons": ["the site profile does not claim dedicated hardware"]}
        for submission in (False, True):
            r, d = self.verify(raw, submission=submission)
            self.assertTrue(r.accepted, check.text(r, d))
            self.assertEqual(status(r, "hardware"), ["warning"])
            self.assertEqual(self.errors(r), set())

    def test_a_gate_that_was_bypassed_is_listed_and_does_not_reject_the_run(self):
        for flag in ("--allow-noisy", "--allow-short", "--no-calibrate", "--no-quiet-gate", "--allow-frequency-scaling"):
            raw = submit_raw(self.repo)
            raw["run"]["command"] = ["buffon", "session", "overhead", flag]
            r, d = self.verify(raw)
            self.assertTrue(r.accepted, (flag, check.text(r, d)))
            self.assertEqual(status(r, "gates"), ["warning"], flag)
            self.assertIn(flag, [c["message"] for c in r.checks if c["id"] == "gates"][0])

    def test_a_run_made_without_telemetry_or_without_its_copies_is_rejected(self):
        raw = submit_raw(self.repo)
        raw["run"]["command"] = ["buffon", "session", "overhead", "--no-telemetry"]
        self.assertIn("flags", self.errors(self.verify(raw)[0]))
        raw = submit_raw(self.repo)
        raw["run"]["aa"] = "none"
        self.assertIn("flags", self.errors(self.verify(raw)[0]))

    def test_a_short_run_and_a_quiet_host_gate_that_was_off_or_gave_up_are_listed_not_rejected(self):
        for mutate, want in ((lambda r: r["run"].update(rounds=11), "rounds"), (lambda r: r["run"]["quiet_gate"].update(enabled=False), "quiet_gate"),
                             (lambda r: r["run"]["quiet_gate"].update(timeouts=2), "quiet_gate"), (lambda r: r["run"]["quiet_gate"].update(max_busy=0.5), "quiet_gate")):
            raw = submit_raw(self.repo)
            mutate(raw)
            r, d = self.verify(raw)
            self.assertTrue(r.accepted, (want, check.text(r, d)))
            self.assertIn("warning", status(r, want), want)

    def test_a_refused_run_one_that_is_not_ok_and_a_dirty_runner_are_rejected(self):
        for mutate, want in ((lambda r: r.update(refused="calibration"), "run"), (lambda r: r.update(ok=False), "run"), (lambda r: r["runner"].update(dirty=True), "runner")):
            raw = submit_raw(self.repo)
            mutate(raw)
            self.assertIn(want, self.errors(self.verify(raw)[0]), want)

    def test_a_run_whose_platform_had_no_egress_audit_is_rejected(self):
        raw = submit_raw(self.repo)
        raw.setdefault("egress", {})["mode"] = "none"
        self.assertIn("egress", self.errors(self.verify(raw)[0]))
        raw["egress"]["mode"] = "socket-audit"
        self.assertNotIn("egress", self.errors(self.verify(raw)[0]))
        del raw["egress"]   # no record at all: the raw.json schema refuses it
        self.assertIn("raw", self.errors(self.verify(raw)[0]))

    def test_a_run_without_telemetry_is_rejected(self):
        self.assertIn("telemetry", self.errors(self.verify(submit_raw(self.repo, telemetry=False))[0]))

    def test_a_run_in_noisy_conditions_verifies_with_notes_and_lists_each_one(self):
        def mutate(s):
            if not s["warmup"] and s["arm"].startswith("other"):
                s["telemetry"]["system"]["cgroup"].update(throttled_us=9000, throttled_periods=3)
        raw = submit_raw(self.repo, mutate=mutate, calibration_cv=0.06)
        raw["hardware"] = {"class": "provisional", "quiet_dedicated": False, "reasons": ["shared host"]}
        raw["run"]["rounds"] = 11
        raw["run"]["command"] += ["--allow-noisy", "--no-quiet-gate"]
        raw["run"]["quiet_gate"].update(enabled=False)
        r, d = self.verify(raw)
        self.assertTrue(r.accepted, check.text(r, d))
        self.assertEqual(self.errors(r), set())
        self.assertGreaterEqual(r.health["notes"], 3)
        listed = {c["id"] for c in r.checks if c["status"] == "warning"}
        self.assertTrue({"throttled_samples", "calibration_cv", "hardware", "rounds", "gates", "quiet_gate"} <= listed, listed)
        text = check.text(r, d)
        self.assertIn("ACCEPTED", text)
        self.assertIn(f"{r.health['notes']} notes", text)
        self.assertIn("throttled_samples", [c["message"] for c in r.checks if c["id"] == "throttled_samples"][0])
        self.assertEqual(status(r, "health"), ["ok"])

    def test_a_noisy_run_is_listed_in_the_results_index_with_its_notes(self):
        results = tempfile.mkdtemp()
        sealed_dir(self.repo, submit_raw(self.repo, calibration_cv=0.06), name="noisy", base=results)
        rows = index.write(results, self.repo)
        self.assertEqual(len(rows), 1)
        self.assertGreaterEqual(rows[0]["notes"], 1)
        self.assertIn("calibration_cv", rows[0]["noted_checks"])
        self.assertNotIn("health", rows[0])
        with open(os.path.join(results, "INDEX.md")) as f:
            text = f.read()
        self.assertIn("| run notes |", text)
        self.assertIn("notes: ", text)

    def test_a_tampered_run_is_still_rejected_whatever_its_notes(self):
        d = sealed_dir(self.repo, submit_raw(self.repo, calibration_cv=0.06))
        with open(os.path.join(d, "facts.json"), "a") as f:
            f.write(" ")
        r = check.verify(d, self.repo, is_submission=True)
        self.assertFalse(r.accepted)
        self.assertEqual(self.errors(r), {"seal"})
        self.assertIn("facts.json differs", [c["message"] for c in r.checks if c["id"] == "seal"][0])
        self.assertIn("REJECTED", check.text(r, d))

    def test_a_missing_submission_toml_is_rejected_next_to_a_clean_run(self):
        d = sealed_dir(self.repo, submission=False)
        r = check.verify(d, self.repo, is_submission=True)
        self.assertEqual(self.errors(r), {"submission"})

    def test_pins_must_be_the_locks(self):
        for mutate, text in ((lambda r: r["arms"]["pi-node"].update(version="1.2.0"), "version 1.2.0"), (lambda r: r["arms"]["pi-node"].update(artifact_sha256="ff" * 32), "not a locked artifact"),
                             (lambda r: r["arms"]["other"].update(commit="9" * 40), "built from"), (lambda r: r["arms"]["other"].update(tree="9" * 40), "source tree"),
                             (lambda r: r["arms"]["pi-node"].update(manifest_sha256="00" * 32), "manifest sha256 differs"), (lambda r: r["arms"].pop("pi-node"), None),
                             (lambda r: r["arms"]["pi-node"].pop("executable_sha256"), "no executable digest")):
            raw = submit_raw(self.repo)
            mutate(raw)
            r, _ = self.verify(raw)
            msgs = " ".join(c["message"] for c in r.checks if c["id"] == "arms")
            if text:
                self.assertIn("arms", self.errors(r), text)
                self.assertIn(text, msgs)

    def test_a_pin_left_out_of_the_record_is_not_a_pass(self):
        """Review: each pin was compared only when the run recorded it, so a raw.json without the field (an arm built locally, or an edited and resealed run) was accepted."""
        cases = (("artifact", lambda r: r["arms"]["pi-node"].pop("artifact_sha256"), "no artifact digest"),
                 ("commit", lambda r: r["arms"]["other"].pop("commit"), "no source commit"),
                 ("tree", lambda r: r["arms"]["other"].pop("tree"), "no source tree"),
                 ("arm record", lambda r: r["arms"].pop("pi-node"), "pi-node: measured, but the run records no arm entry"),
                 ("arm hidden as a copy", lambda r: r["arms"]["pi-node"].update(twin_of="pi-node-b", version="9.9.9"), "which is not an arm of the run"),
                 ("copy of another build", lambda r: r["arms"]["pi-node-b"].update(executable_sha256="ff" * 32), "executable_sha256 differ"))
        for name, mutate, text in cases:
            with self.subTest(name):
                raw = submit_raw(self.repo)
                mutate(raw)
                r, _ = self.verify(raw)
                self.assertIn("arms", self.errors(r))
                self.assertIn(text, " ".join(c["message"] for c in r.checks if c["id"] == "arms"))

    def test_a_runner_tree_that_is_not_its_commits_tree_is_rejected(self):
        """Review: the tree check had no test (a mutant that skipped it survived)."""
        raw = submit_raw(self.repo)
        raw["runner"]["tree"] = "9" * 40
        r, _ = self.verify(raw)
        self.assertIn("runner", self.errors(r))
        self.assertIn("is not the tree of commit", " ".join(c["message"] for c in r.checks if c["id"] == "runner"))

    def test_an_abbreviated_gate_flag_is_refused_by_the_parser_and_caught_in_an_old_record(self):
        """argparse took `--allow-noi` for --allow-noisy and the run recorded the abbreviation, which the flag check did not match."""
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["session", "overhead/version", "--allow-noi"])
        for token in ("--allow-noi", "--no-cal", "--allow-freq"):
            raw = submit_raw(self.repo)
            raw["run"]["command"].append(token)
            r, _ = self.verify(raw)
            self.assertEqual(status(r, "gates"), ["warning"], token)
        raw = submit_raw(self.repo)
        raw["run"]["command"].append("--no-tel")
        self.assertIn("flags", self.errors(self.verify(raw)[0]), "an abbreviation of --no-telemetry is still the flag")
        raw = submit_raw(self.repo)
        raw["run"]["command"].append("--al")
        r, _ = self.verify(raw)
        self.assertEqual((status(r, "gates"), self.errors(r)), ([], set()), "two letters name no flag")

    def test_a_lock_that_is_neither_the_current_one_nor_the_one_at_the_commit_is_rejected(self):
        raw = submit_raw(self.repo)
        raw["lock_sha256"] = "00" * 32
        r, _ = self.verify(raw)
        self.assertIn("lock", self.errors(r))

    def test_the_run_may_be_older_than_the_checkout_when_its_commit_is_in_history(self):
        raw = submit_raw(self.repo)
        with open(os.path.join(self.repo, "arms.lock"), "a") as f:
            f.write("\n")
        from tests.submit_fixtures import sh
        sh(self.repo, "git", "commit", "-q", "-am", "newer pins")
        r, d = self.verify(raw)
        self.assertTrue(r.accepted, check.text(r, d))
        self.assertIn("lock at runner commit", [c["message"] for c in r.checks if c["id"] == "lock"][0])

    def test_a_runner_commit_that_is_not_in_the_repository_is_rejected(self):
        raw = submit_raw(self.repo)
        raw["runner"]["commit"] = "1" * 40
        with open(os.path.join(self.repo, "arms.lock"), "a") as f:
            f.write("\n")
        self.assertIn("lock", self.errors(self.verify(raw)[0]))

    def test_a_forged_health_file_or_report_is_rejected(self):
        d = sealed_dir(self.repo)
        with open(os.path.join(d, "health.json"), "w") as f:
            json.dump({"notes": 0, "summary": "no notes", "checks": []}, f)
        self.assertIn("health.json", self.errors(check.verify(d, self.repo, is_submission=True)))

    def test_a_health_file_written_by_the_report_is_accepted(self):
        from buffon.report import render
        d = sealed_dir(self.repo)
        render.render([d], d)
        r = check.verify(d, self.repo, is_submission=True)
        self.assertTrue(r.accepted, check.text(r, d))
        self.assertEqual(status(r, "health.json"), ["ok"])
        self.assertEqual(status(r, "report.json"), ["ok"])

    def test_a_report_written_by_buffon_report_passes_the_generated_check_including_report_html(self):
        """Regression: run_id_in matched `<tr><td>...<code>RUN` in report.html (a run with one arm has no rerun cards, so the cell-id table comes first), and the regeneration comparison then rewrote the wrong text and rejected a plain run."""
        from buffon.report import render
        from tests.report_demo import demo_raw
        raw = demo_raw()
        raw["samples"] = [s for s in raw["samples"] if s["arm"] in ("pi-node", "pi-node-b")]
        d = os.path.join(tempfile.mkdtemp(), "run")
        write_dir(d, raw)
        render.render([d], d)
        manifest.write(d)
        with open(os.path.join(d, "report.html")) as f:
            self.assertRegex(f.read(), r"</thead><tbody>\n<tr><td>[^<]*</td><td>[^<]*</td><td>[^<]*</td><td><code>run::")
        r = check.verify(d, self.repo, is_submission=False)
        self.assertEqual(status(r, "generated"), ["ok"], check.text(r, d))
        self.assertEqual(check.run_id_in("<tr><td>x</td><td><code>my-run::overhead/print@openai-completions#cpu_ms</code></td></tr>"), "my-run")
        self.assertEqual(check.run_id_in("| overhead/print | chat | `my-run::overhead/print@openai-completions#cpu_ms` |"), "my-run")

    def test_submission_toml_is_validated_strictly(self):
        d = sealed_dir(self.repo, submission=False)
        self.assertIn("submission", self.errors(check.verify(d, self.repo, is_submission=True)))
        for text, why in (('operator = "x"\n', "required"), ('operator = "A. Person"\nhardware = "h h h"\nindependent = "yes"\n', "must be bool"),
                          ('operator = "A. Person"\nhardware = "h h h"\nindependent = true\nextra = 1\n', "unknown key"), ('operator = ""\nhardware = "h h h"\nindependent = true\n', "empty"),
                          ("operator = ", "not valid TOML")):
            with open(os.path.join(d, "submission.toml"), "w") as f:
                f.write(text)
            _, problems = submission.load(d)
            self.assertTrue(any(why in p for p in problems), (text, problems))


class Index(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.results = tempfile.mkdtemp()

    def add(self, name, **kw):
        sealed_dir(self.repo, submit_raw(self.repo, **kw), name=name, base=self.results)

    def test_the_index_lists_every_accepted_run_and_check_matches_it(self):
        self.add("2026-10-11-a")
        self.add("2026-10-12-b")
        rows = index.write(self.results, self.repo)
        self.assertEqual([r["id"] for r in rows], ["2026-10-11-a", "2026-10-12-b"])
        self.assertEqual((rows[0]["notes"], rows[0]["noted_checks"]), (0, []))
        self.assertEqual(rows[0]["arms"], {"other": "2.0.0", "pi-node": "1.1.0"})
        self.assertEqual(rows[0]["operator"], "A. Person")
        self.assertEqual(index.check(self.results, self.repo), [])
        with open(os.path.join(self.results, "INDEX.md")) as f:
            self.assertIn("| [2026-10-11-a](2026-10-11-a/report.md) |", f.read())

    def test_a_stale_or_missing_index_fails_the_check(self):
        self.add("a")
        self.assertTrue(any("index.json is missing" in p for p in index.check(self.results, self.repo)))
        index.write(self.results, self.repo)
        self.add("b")
        self.assertTrue(any("out of date" in p for p in index.check(self.results, self.repo)))

    def test_one_bad_directory_stops_the_index_and_is_named(self):
        self.add("good")
        self.add("bad", telemetry=False)
        with self.assertRaises(index.IndexProblem) as caught:
            index.build(self.results, self.repo)
        self.assertIn("bad: REJECTED", str(caught.exception))
        self.assertNotIn("good: REJECTED", str(caught.exception))
        self.assertTrue(index.check(self.results, self.repo))

    def test_an_empty_results_directory_has_an_empty_index(self):
        index.write(self.results, self.repo)
        self.assertIn("no accepted results yet", open(os.path.join(self.results, "INDEX.md")).read())


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_verify_exit_codes_and_json(self):
        repo = make_repo()
        good, bad = sealed_dir(repo), sealed_dir(repo, submit_raw(repo, telemetry=False))
        rc, out, _ = self.run_cli("verify", good, "--repo", repo, "--submission")
        self.assertEqual(rc, 0, out)
        self.assertIn("ACCEPTED, no notes", out)
        rc, out, _ = self.run_cli("verify", bad, "--repo", repo, "--submission")
        self.assertEqual(rc, 1)
        self.assertIn("REJECTED", out)
        rc, out, _ = self.run_cli("verify", good, bad, "--repo", repo, "--submission", "--json")
        self.assertEqual(rc, 1)
        self.assertEqual([r["accepted"] for r in json.loads(out)], [True, False])

    def test_index_and_health_commands(self):
        repo = make_repo()
        results = tempfile.mkdtemp()
        sealed_dir(repo, name="r1", base=results)
        rc, out, _ = self.run_cli("index", results, "--repo", repo)
        self.assertEqual(rc, 0, out)
        rc, out, _ = self.run_cli("index", results, "--repo", repo, "--check")
        self.assertEqual((rc, out.strip()), (0, "results index ok"))
        rc, out, _ = self.run_cli("health", os.path.join(results, "r1"))
        self.assertEqual(rc, 0)
        self.assertIn("Run notes (0)**: none", out)
        rc, out, _ = self.run_cli("health", "thresholds")
        self.assertIn("calibration_cv", out)

    def test_a_session_seals_its_run_directory(self):
        d = tempfile.mkdtemp()
        write_dir(d, submit_raw(make_repo()))
        cli.seal(d)
        self.assertEqual(manifest.check(d), [])
        empty = tempfile.mkdtemp()
        cli.seal(empty)
        self.assertFalse(os.path.exists(os.path.join(empty, manifest.NAME)))


if __name__ == "__main__":
    unittest.main()
