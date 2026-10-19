# SPDX-License-Identifier: Apache-2.0
"""M9 provenance: every cell has an id and the exact command that measures it again; `buffon rerun` builds that run from the original's own plan; reports are generated, never edited."""
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

from buffon import cli
from buffon.report import cellid, render
from buffon.submit import reproduce
from buffon.submit import check
from tests.submit_fixtures import make_repo, sealed_dir
from tests.test_report import raw_of, series


def make_run(root, name="run-a", samples=None):
    d = os.path.join(root, name)
    os.makedirs(d)
    raw = raw_of(samples or series(), quiet=False)
    raw["run"].update(workloads=["overhead"], aa="all", arms=["pi-node", "other"], reference="pi-node", apis=["openai-completions"], params={}, command=["buffon", "run", "overhead", "--timeout", "90"])
    with open(os.path.join(d, "raw.json"), "w") as f:
        json.dump(raw, f)
    return d


class Ids(unittest.TestCase):
    def test_a_cell_id_round_trips_and_a_missing_api_is_a_dash(self):
        i = cellid.make("run-a", "overhead/print", "openai-completions", "cpu_ms")
        self.assertEqual(i, "run-a::overhead/print@openai-completions#cpu_ms")
        self.assertEqual(cellid.parse(i), ("run-a", "overhead/print", "openai-completions", "cpu_ms"))
        j = cellid.make("run-a", "devloop/build", None, "wall_ms")
        self.assertEqual(cellid.parse(j), ("run-a", "devloop/build", None, "wall_ms"))
        self.assertEqual(cellid.rerun_command(i), "python3 -m buffon rerun run-a::overhead/print@openai-completions#cpu_ms")

    def test_malformed_ids_are_refused_with_the_expected_shape(self):
        for bad in ("", "overhead/print", "run::print@x#cpu_ms", "run::overhead/print#cpu_ms", "run::overhead/print@x", "a/b::overhead/print@x#m", "::overhead/print@x#m"):
            with self.assertRaises(cellid.CellIdError, msg=bad):
                cellid.parse(bad)


class ReportCarriesIds(unittest.TestCase):
    def test_every_cell_of_report_json_csv_and_md_names_its_id_and_rerun_command(self):
        with tempfile.TemporaryDirectory() as root:
            d = make_run(root)
            out = os.path.join(root, "out")
            render.render([d], out)
            report = json.load(open(os.path.join(out, "report.json")))
            ids = [c["id"] for c in report["cells"]]
            self.assertTrue(ids and all(i.startswith("run-a::overhead/print@openai-completions#") for i in ids))
            self.assertEqual({c["rerun"] for c in report["cells"]}, {cellid.rerun_command(i) for i in ids})
            rows = list(csv.DictReader(open(os.path.join(out, "summary.csv"))))
            self.assertEqual({r["cell_id"] for r in rows}, set(ids))
            self.assertTrue(all(r["rerun"] == cellid.rerun_command(r["cell_id"]) for r in rows))
            md = open(os.path.join(out, "report.md")).read()
            self.assertIn("## Cell ids and rerun commands", md)
            for i in ids:
                self.assertIn(f"`{i}`", md)
            self.assertEqual(list(rows[0])[-1], "label")

    def test_the_id_names_the_run_directory_not_its_path_and_a_pooled_cell_names_the_first_run_that_holds_it(self):
        with tempfile.TemporaryDirectory() as root:
            a = make_run(root, "first")
            b = make_run(root, "second", series() + series(scenario="overhead/rpc"))
            out = os.path.join(root, "o")
            render.render([a, b], out)
            with open(os.path.join(out, "report.json")) as f:
                cells = json.load(f)["cells"]
            by = {c["scenario"]: c["id"].split("::")[0] for c in cells}
            self.assertEqual(by, {"overhead/print": "first", "overhead/rpc": "second"})


class Provenance(unittest.TestCase):
    def test_the_report_prints_every_pin_in_full_and_says_when_one_was_not_recorded(self):
        raw = raw_of(series())
        raw["arms"] = {"pi-node": {"label": "Pi", "version": "1.1.0", "source_url": "https://example.com/pi-1.1.0.tgz", "artifact_sha256": "a" * 64, "install_method": "release archive", "platform": "linux-x64",
                                   "manifest_sha256": "b" * 64, "executable_sha256": "c" * 64},
                       "other": {"label": "Other", "version": "0.1", "commit": "d" * 40, "tree": "e" * 40, "build": "go build -trimpath", "toolchain": "go 1.27.2", "install_method": "source build", "manifest_sha256": "f" * 64, "executable_sha256": "1" * 64}}
        with tempfile.TemporaryDirectory() as root:
            d = os.path.join(root, "r")
            os.makedirs(d)
            with open(os.path.join(d, "raw.json"), "w") as f:
                json.dump(raw, f)
            render.render([d], os.path.join(root, "o"))
            with open(os.path.join(root, "o", "report.md")) as f:
                md = f.read()
        self.assertIn("## Provenance", md)
        self.assertIn("https://example.com/pi-1.1.0.tgz", md)
        self.assertIn("artifact_sha256 `" + "a" * 64 + "`", md)
        self.assertIn("git " + "d" * 40, md)
        self.assertIn("go build -trimpath; toolchain go 1.27.2", md)
        self.assertIn("`" + "c" * 64 + "`", md)


class Rerun(unittest.TestCase):
    def test_the_plan_of_a_cell_is_its_workload_its_api_and_the_arms_that_measured_it_reference_first(self):
        with tempfile.TemporaryDirectory() as root:
            d = make_run(root)
            self.assertEqual(reproduce.cell_plan(d, "overhead/print", "openai-completions", "cpu_ms"), (["overhead/print"], ["openai-completions"], ["pi-node", "other"]))
            with self.assertRaises(cellid.CellIdError):
                reproduce.cell_plan(d, "overhead/print", "openai-completions", "no_such_ms")
            with self.assertRaises(cellid.CellIdError):
                reproduce.cell_plan(d, "overhead/print", "anthropic-messages", "cpu_ms")

    def test_rerun_print_gives_the_originals_plan_restricted_to_the_cell(self):
        with tempfile.TemporaryDirectory() as root:
            make_run(root)
            buf = io.StringIO()
            cwd = os.getcwd()
            os.chdir(root)
            try:
                with contextlib.redirect_stdout(buf):
                    rc = cli.main(["rerun", "run-a::overhead/print@openai-completions#cpu_ms", "--runs-dir", root, "--print", "--site", "mine", "--out", "o"])
            finally:
                os.chdir(cwd)
            self.assertEqual(rc, 0)
            argv = buf.getvalue().split()
            self.assertEqual(argv[:4], ["python3", "-m", "buffon", "run"])
            self.assertEqual(argv[4], "overhead/print")
            for want in (["--site", "mine"], ["--rounds", "12"], ["--seed", "7"], ["--aa", "all"], ["--reference", "pi-node"], ["--arms", "pi-node", "other"], ["--apis", "openai-completions"], ["--timeout", "90"]):
                i = argv.index(want[0])
                self.assertEqual(argv[i:i + len(want)], want, want)

    def test_an_unknown_run_a_malformed_id_and_a_different_arms_lock_are_refused(self):
        with tempfile.TemporaryDirectory() as root:
            make_run(root)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(["rerun", "not-a-cell-id"]), 2)
                with self.assertRaises(SystemExit):
                    cli.main(["rerun", "missing-run::overhead/print@openai-completions#cpu_ms", "--runs-dir", root])
                self.assertEqual(cli.main(["rerun", "run-a::overhead/print@openai-completions#cpu_ms", "--runs-dir", root, "--out", os.path.join(root, "o")]), 3)
            self.assertIn("arms.lock", err.getvalue())
            self.assertIn("not a cell id", err.getvalue())


def status(result, cid):
    return [c["status"] for c in result.checks if c["id"] == cid]


class GeneratedOnly(unittest.TestCase):
    """No hand-edited numbers anywhere: `buffon verify` regenerates the report from raw.json and compares every generated file."""

    def setUp(self):
        self.repo = make_repo()
        self.d = sealed_dir(self.repo)
        render.render([self.d], self.d)

    def edit(self, name, old, new):
        path = os.path.join(self.d, name)
        with open(path) as f:
            text = f.read()
        self.assertIn(old, text)
        with open(path, "w") as f:
            f.write(text.replace(old, new, 1))

    def test_an_untouched_report_verifies(self):
        r = check.verify(self.d, self.repo, is_submission=True)
        self.assertEqual(status(r, "generated"), ["ok"], check.text(r, self.d))

    def test_an_edited_number_in_any_generated_file_is_rejected(self):
        for name, old, new in (("summary.csv", "overhead/print", "overhead/printX"), ("report.md", "# buffon report", "# buffon report (edited)"), ("grade.json", '"reference"', '"referenceX"')):
            with self.subTest(name=name):
                self.edit(name, old, new)
                r = check.verify(self.d, self.repo, is_submission=True)
                self.assertEqual(status(r, "generated"), ["error"], name)
                self.assertIn(name, [c["message"] for c in r.checks if c["id"] == "generated"][0])
                self.edit(name, new, old)
        report = json.load(open(os.path.join(self.d, "report.json")))
        report["cells"][0]["comparisons"] = {}
        with open(os.path.join(self.d, "report.json"), "w") as f:
            json.dump(report, f)
        self.assertEqual(status(check.verify(self.d, self.repo, is_submission=True), "generated"), ["error"])

    def test_a_run_copied_under_another_name_still_verifies(self):
        import shutil
        other = os.path.join(os.path.dirname(self.d), "renamed-run")
        shutil.copytree(self.d, other)
        self.assertEqual(status(check.verify(other, self.repo, is_submission=True), "generated"), ["ok"])


class ReviewNoSwitchOff(unittest.TestCase):
    """Review of e1e3523: nothing inside a generated file may switch the regeneration check off."""

    def setUp(self):
        self.repo = make_repo()
        self.d = sealed_dir(self.repo)
        render.render([self.d], self.d)

    def read(self, name):
        with open(os.path.join(self.d, name)) as f:
            return f.read()

    def write(self, name, text):
        with open(os.path.join(self.d, name), "w") as f:
            f.write(text)

    def gen(self):
        return status(check.verify(self.d, self.repo, is_submission=True), "generated")

    def test_an_external_heading_does_not_exempt_an_edited_report(self):
        md = self.read("report.md")
        foot = md.rfind("\n---\n")
        block = "\n## External suites (run as they are upstream)\n\n| suite | target |\n|---|---|\n| x | y |\n"
        self.write("report.md", md[:foot] + block + md[foot:])
        self.assertEqual(self.gen(), ["ok"], "a genuine External block before the footer still verifies")
        self.write("report.md", md.replace("# buffon report", "# buffon report (edited)", 1)[:foot] + block + md[foot:])
        self.assertEqual(self.gen(), ["error"])

    def test_a_faithfulness_key_does_not_exempt_an_edited_report(self):
        report = json.loads(self.read("report.json"))
        report["grade_inputs"]["faithfulness"] = {"pi-node": 100.0}
        self.write("report.json", json.dumps(report))
        self.write("summary.csv", self.read("summary.csv").replace("overhead/print", "overhead/printX", 1))
        self.assertEqual(self.gen(), ["error"])

    def test_a_report_made_with_faithfulness_scores_regenerates_from_the_recorded_values(self):
        given = [{"scores": {"pi-node": {"overall": 100.0, "correctness_failures": []}, "other": {"overall": 87.5, "correctness_failures": ["F3.write"]}}}]
        render.render([self.d], self.d, faithfulness_given=given)
        self.assertEqual(json.loads(self.read("report.json"))["grade_inputs"]["faithfulness"], {"pi-node": 100.0, "other": 87.5})
        self.assertEqual(self.gen(), ["ok"])


class ReviewSurvivors(unittest.TestCase):
    """Review of e1e3523: mutants that survived the builder's tests."""

    def test_a_drop_flagged_report_is_regenerated_with_the_flag_and_an_edit_is_still_caught(self):
        from buffon.report import noise
        from tests.submit_fixtures import submit_raw
        repo = make_repo()
        raw = submit_raw(repo)
        s = next(x for x in raw["samples"] if not x["warmup"] and "failure" not in x)
        noise.system(s)["gate"] = {"status": "waited"}
        d = sealed_dir(repo, raw=raw)
        render.render([d], d, drop_flagged=True)
        self.assertTrue(json.load(open(os.path.join(d, "report.json")))["noise"]["dropped"])
        self.assertEqual(status(check.verify(d, repo, is_submission=True), "generated"), ["ok"])
        path = os.path.join(d, "summary.csv")
        text = open(path).read()
        with open(path, "w") as f:
            f.write(text.replace("overhead/print", "overhead/printX", 1))
        self.assertEqual(status(check.verify(d, repo, is_submission=True), "generated"), ["error"])

    def test_a_cell_id_needs_an_api_or_a_dash(self):
        with self.assertRaises(cellid.CellIdError):
            cellid.parse("run-a::overhead/print@#cpu_ms")

    def test_the_plan_leaves_out_an_arm_whose_only_samples_of_the_cell_failed_or_were_warmup(self):
        samples = [dict(s, failure="crash") if s["arm"] in ("other", "other-b") and s["scenario"] == "overhead/print" and not s["warmup"] else s for s in series()]
        samples = [dict(s, warmup=True) if s["arm"] in ("other", "other-b") and s["scenario"] == "overhead/print" and "failure" not in s else s for s in samples]
        with tempfile.TemporaryDirectory() as root:
            d = make_run(root, samples=samples)
            self.assertEqual(reproduce.cell_plan(d, "overhead/print", "openai-completions", "cpu_ms")[2], ["pi-node"])
        warm_only = [dict(s, warmup=True) if s["arm"] in ("other", "other-b") and s["scenario"] == "overhead/print" else s for s in series()]
        with tempfile.TemporaryDirectory() as root:
            d = make_run(root, samples=warm_only)
            self.assertEqual(reproduce.cell_plan(d, "overhead/print", "openai-completions", "cpu_ms")[2], ["pi-node"])


class ReviewHtmlIsGenerated(unittest.TestCase):
    """Review of eb729d4: report.html says `buffon verify` checks it was not edited; verify compared only the Markdown, JSON and CSV files."""

    def setUp(self):
        self.repo = make_repo()
        self.d = sealed_dir(self.repo)

    def gen(self):
        return status(check.verify(self.d, self.repo, is_submission=True), "generated")

    def edit(self, name, old, new):
        path = os.path.join(self.d, name)
        text = open(path).read()
        self.assertIn(old, text)
        with open(path, "w") as f:
            f.write(text.replace(old, new, 1))

    def test_an_edited_html_page_is_rejected(self):
        render.render([self.d], self.d)
        self.assertEqual(self.gen(), ["ok"])
        for name in ("report.html", "leaderboard.html", "report-card.html"):
            with self.subTest(name=name):
                text = open(os.path.join(self.d, name)).read()
                self.edit(name, "</title>", " (edited)</title>")
                self.assertEqual(self.gen(), ["error"])
                with open(os.path.join(self.d, name), "w") as f:
                    f.write(text)

    def test_a_report_with_an_external_section_verifies_and_an_edit_outside_it_does_not(self):
        from unittest import mock
        from buffon.external import runner as extrunner
        block = ["## External suites (run as they are upstream)", "", "| suite | x |", "|---|---|", "| s | 1 |", ""]
        with mock.patch.object(extrunner, "section", lambda dirs: block):
            render.render([self.d], self.d, external_suites=["x"])
        self.assertIn('<h2 id="external-', open(os.path.join(self.d, "report.html")).read())
        self.assertEqual(self.gen(), ["ok"])
        self.edit("report.html", "</title>", " (edited)</title>")
        self.assertEqual(self.gen(), ["error"])

if __name__ == "__main__":
    unittest.main()
