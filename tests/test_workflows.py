# SPDX-License-Identifier: Apache-2.0
"""The results workflows carry the rules the code enforces: a merge job that promotes, and a governance path that is the only user of --allow-governance."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


class Workflows(unittest.TestCase):
    def test_a_merge_job_promotes_every_run_directory_without_a_promotion_record(self):
        text = read(".github", "workflows", "results-merge.yml")
        self.assertRegex(text, r"branches: \[main\]")
        self.assertIn("promotion.json", text)
        self.assertIn("python3 -m buffon promote", text)
        self.assertIn("python3 -m buffon index results", text)
        self.assertIn("contents: write", text)

    def test_only_the_protected_governance_job_passes_allow_governance(self):
        text = read(".github", "workflows", "results.yml")
        jobs = re.split(r"\n  (?=[a-z]+:\n)", text[text.index("jobs:"):])
        flagged = [j.split(":", 1)[0].strip() for j in jobs if "--allow-governance" in j]
        self.assertEqual(flagged, ["governance"])
        governance = [j for j in jobs if j.startswith("governance:")][0]
        self.assertIn("environment: results-maintainers", governance)
        self.assertIn("needs.changes.outputs.governance == 'true'", governance)
        revalidate = [j for j in jobs if j.startswith("revalidate:")][0]
        self.assertIn("needs.changes.outputs.governance == 'false'", revalidate)

    def test_one_always_run_job_passes_only_when_the_needed_path_passed(self):
        # review: a skipped required job counts as passed on GitHub, so revalidate/governance cannot be the required checks themselves
        text = read(".github", "workflows", "results.yml")
        jobs = re.split(r"\n  (?=[a-z]+:\n)", text[text.index("jobs:"):])
        result = [j for j in jobs if j.startswith("result:")][0]
        self.assertIn("needs: [changes, revalidate, governance]", result)
        self.assertIn("if: always()", result)
        self.assertIn("success/false/success/skipped|success/true/skipped/success) echo \"ok\" ;;", result)
        self.assertIn("exit 1", result)
        self.assertIn("`result`", read("docs", "SUBMITTING.md"))

    def test_codeowners_names_both_governance_files(self):
        text = read(".github", "CODEOWNERS")
        for path in ("/results/MAINTAINERS.toml", "/results/WITHDRAWN.toml"):
            self.assertRegex(text, re.escape(path) + r"\s+@")

    def test_results_checks_run_the_base_branch_code_and_never_the_pull_requests(self):
        # review: with `pull_request` a submission could edit buffon/ or this workflow in the same change and be checked by its own code
        text = read(".github", "workflows", "results.yml")
        self.assertRegex(text, r"\non:\n  pull_request_target:\n")
        self.assertNotRegex(text, r"\n  pull_request:\n")
        perms = text[text.index("\npermissions:\n"):text.index("\njobs:")]
        self.assertEqual([x.strip() for x in perms.strip().splitlines()], ["permissions:", "contents: read"])
        steps = re.split(r"\n      - ", text[text.index("jobs:"):])
        buffon_steps = [s for s in steps if "python3 -m buffon" in s]
        self.assertTrue(buffon_steps)
        for s in buffon_steps:
            self.assertIn("working-directory: base", s, s)
        checkouts = [s for s in steps if s.startswith("uses: actions/checkout")]
        self.assertTrue(checkouts)
        for s in checkouts:
            self.assertIn("persist-credentials: false", s, s)
        for s in (s for s in checkouts if "path: pr" in s):
            self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", s)
        for s in (s for s in checkouts if "path: base" in s):
            self.assertIn("ref: ${{ github.event.pull_request.base.sha }}", s)
        self.assertNotIn("${{ github.head_ref }}", text)   # a branch name is the submitter's text; only shas and env reach a shell

    def test_the_manifest_attestation_runs_after_the_merge_not_on_a_pull_request(self):
        self.assertNotIn("attest", read(".github", "workflows", "results.yml"))
        merge = read(".github", "workflows", "results-merge.yml")
        self.assertIn("actions/attest-build-provenance", merge)
        self.assertIn("id-token: write", merge)

    def test_codeowners_review_covers_every_file(self):
        self.assertRegex(read(".github", "CODEOWNERS"), r"(?m)^\*\s+@\S+")

    def test_a_pull_request_job_checks_that_every_commit_is_signed_off(self):
        text = read(".github", "workflows", "tests.yml")
        job = text[text.index("\n  signoff:"):]
        self.assertIn("if: github.event_name == 'pull_request'", job)
        self.assertIn("fetch-depth: 0", job)
        self.assertIn("git rev-list \"$BASE..$HEAD\"", job)   # every commit of the pull request, merge commits included (rev-list does not skip them)
        self.assertIn("Signed-off-by", job)
        self.assertIn("git rebase --signoff", job)             # the message says how to fix it

    def test_a_step_name_with_a_colon_is_quoted_or_the_workflow_is_not_yaml(self):
        for name in ("tests", "results", "results-merge", "pages"):
            text = read(".github", "workflows", name + ".yml")
            self.assertEqual(re.findall(r"(?m)^\s*- name: (?![\"']).*: .*$", text), [], name)


if __name__ == "__main__":
    unittest.main()
