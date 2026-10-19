# SPDX-License-Identifier: Apache-2.0
"""What a person sees at the command line: one generated command list, one-line errors instead of tracebacks, a Node check before `buffon up` measures, names that are typed the short way, and a warning when a run cannot be submitted."""
import contextlib
import io
import os
import re
import tempfile
import unittest
from unittest import mock

from buffon import cli
from buffon.arms import manifest
from buffon.backend import BackendError
from buffon.up import flow, machine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_main(argv, cwd=None):
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    if cwd:
        os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
    finally:
        os.chdir(old)
    return code, out.getvalue(), err.getvalue()


class TopLevelHelp(unittest.TestCase):
    def listed(self):
        text = cli.build_parser().format_help()
        return text, re.findall(r"(?m)^  (\S+)  ", text)

    def test_every_command_but_the_internal_ones_is_listed_once_everyday_first(self):
        text, listed = self.listed()
        commands = list(cli.build_parser()._subparsers._group_actions[0].choices)
        self.assertEqual(sorted(listed), sorted(c for c in commands if c not in cli.HIDDEN))
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(listed[:len(cli.EVERYDAY)], list(cli.EVERYDAY))

    def test_the_internal_commands_are_hidden_but_still_run(self):
        text, listed = self.listed()
        for name in cli.HIDDEN:
            self.assertNotIn(name, listed)
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            cli.main(["session", "--help"])
        self.assertEqual(stop.exception.code, 0)
        self.assertIn("usage: buffon session", out.getvalue())

    def test_the_exit_codes_line_names_exit_code_one(self):
        self.assertRegex(cli.build_parser().format_help(), r"Exit codes: 0 success; 1 ")

    def test_every_command_has_a_summary_and_no_summary_is_orphaned(self):
        commands = set(cli.build_parser()._subparsers._group_actions[0].choices)
        self.assertEqual(set(cli.SUMMARY), commands)

    def test_the_up_help_names_the_default_harnesses_of_the_catalog(self):
        from buffon.up import catalog
        text = cli.build_parser()._subparsers._group_actions[0].choices["up"].format_help()
        self.assertIn(catalog.DEFAULT_HARNESSES[-1], text)
        self.assertEqual(sum(h in text for h in catalog.DEFAULT_HARNESSES), len(catalog.DEFAULT_HARNESSES))


class OneLineErrors(unittest.TestCase):
    def test_a_missing_run_directory_is_one_line_and_exit_2(self):
        for argv in (["report", "/no/such/run"], ["health", "/no/such/run"], ["compare", "/no/a", "/no/b"], ["reproduce", "/no/such/run"]):
            code, out, err = run_main(argv)
            self.assertEqual(code, 2, argv)
            self.assertEqual(len(err.strip().splitlines()), 1, argv)
            self.assertTrue(err.startswith("buffon: /no/"), err)
            self.assertNotIn("Traceback", err)

    def test_the_traceback_comes_back_with_buffon_debug(self):
        with mock.patch.dict(os.environ, {"BUFFON_DEBUG": "1"}), self.assertRaises(FileNotFoundError):
            run_main(["report", "/no/such/run"])

    def test_a_bad_workload_is_refused_before_a_run_directory_exists(self):
        work = tempfile.mkdtemp()
        code, out, err = run_main(["run", "overhead/prnt", "--site", os.path.join(ROOT, "sites", "example-local.toml")], cwd=work)
        self.assertEqual(code, 2)
        self.assertIn("unknown workload 'overhead/prnt' (did you mean overhead/print", err)
        self.assertEqual(os.listdir(work), [])

    def test_an_unknown_site_says_how_to_make_one(self):
        code, out, err = run_main(["run", "overhead", "--site", "nowhere"])
        self.assertEqual(code, 2)
        self.assertIn("cp sites/example-local.toml sites/nowhere.toml", err)


class ArmNames(unittest.TestCase):
    arms = manifest.load_all()

    def test_the_short_names_of_up_work_in_run_and_session(self):
        self.assertEqual(cli.resolve_arm_names(["pi", "pig", "pi-bolt", "codex"], self.arms), ["pi-node", "pig-tip", "pibolt", "codex"])

    def test_an_unknown_arm_gets_the_nearest_ids(self):
        with self.assertRaises(BackendError) as caught:
            cli.resolve_arm_names(["opencode2"], self.arms)
        self.assertIn("unknown arm 'opencode2' (did you mean opencode", str(caught.exception))
        self.assertIn("`buffon harnesses` lists the arms", str(caught.exception))

    def test_arm_verify_refuses_an_unknown_arm_with_exit_2(self):
        code, out, err = run_main(["arm", "verify", "no-such-arm"])
        self.assertEqual(code, 2)
        self.assertIn("unknown arm 'no-such-arm'", err)


class NodeBeforeMeasuring(unittest.TestCase):
    def test_node_problem_names_what_to_install(self):
        self.assertIn("install Node 18 or newer", machine.node_problem(which=lambda name: None))
        old = machine.node_problem(which=lambda name: "/bin/node", run=lambda *a, **k: mock.Mock(stdout="v16.20.0\n"))
        self.assertIn("v16.20.0 is too old", old)
        self.assertIsNone(machine.node_problem(which=lambda name: "/bin/node", run=lambda *a, **k: mock.Mock(stdout="v24.19.0\n")))

    def test_up_stops_before_installing_when_the_dashboard_cannot_be_built(self):
        err = io.StringIO()
        with mock.patch.object(machine, "node_problem", return_value="Node is not installed: install Node 18 or newer (the dashboard needs it)"), \
                mock.patch.object(flow, "up") as up, mock.patch("sys.stderr", err), mock.patch.dict(os.environ, {"BUFFON_HOME": tempfile.mkdtemp()}):
            self.assertEqual(cli.main(["up", "--yes", "--no-open"]), 1)
        up.assert_not_called()
        self.assertIn("install Node 18 or newer (the dashboard needs it)", err.getvalue())
        self.assertIn("--no-dashboard", err.getvalue())

    def test_no_dashboard_skips_the_node_check_and_a_plan_never_needs_node(self):
        with mock.patch.object(machine, "node_problem", return_value="no node") as check, mock.patch.object(flow, "up", side_effect=KeyboardInterrupt), \
                mock.patch("sys.stderr", io.StringIO()), mock.patch.dict(os.environ, {"BUFFON_HOME": tempfile.mkdtemp()}):
            self.assertEqual(cli.main(["up", "--yes", "--no-open", "--no-dashboard"]), 130)
            with mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(cli.main(["up", "--plan", "--yes"]), 0)
        check.assert_not_called()

    def test_a_failed_dashboard_says_its_own_cause_not_a_missing_command(self):
        home = tempfile.mkdtemp()
        paths = machine.paths(home)
        lines = []

        def fake_run(argv, **kw):
            failing = "dashboard" in argv
            return mock.Mock(returncode=1 if failing else 0, stdout="", stderr="MathError: buffon dashboard renders its formulas with Node: install Node 18 or newer\n" if failing else "")

        opts = flow.Options(home=home)
        summary = {"harnesses": ["pi-node"], "left_out": {}, "benchmarks": [], "evals": [], "trust": {"badge": "Shared", "reasons": [], "headline": "x", "headline_why": "y", "host_class": "B"},
                   "run_dirs": [], "faithfulness_dirs": [], "command": "buffon up", "site": "", "took_s": 1, "adaptive": []}
        with mock.patch.object(flow.subprocess, "run", side_effect=fake_run), mock.patch.object(flow, "landing_page", return_value="<html></html>"):
            flow.build_site(opts, paths, ["/runs/a"], [], summary, lines.append)
        text = " ".join(lines)
        self.assertIn("the dashboard did not build (MathError: buffon dashboard renders its formulas with Node: install Node 18 or newer)", text)
        self.assertNotIn("no dashboard command", text)
        lines.clear()
        with mock.patch.object(flow.subprocess, "run", side_effect=fake_run), mock.patch.object(flow, "landing_page", return_value="<html></html>"):
            flow.build_site(flow.Options(home=home, dashboard=False), paths, ["/runs/a"], [], summary, lines.append)
        self.assertIn("the dashboard was skipped (--no-dashboard)", " ".join(lines))


class SubmissionWarnings(unittest.TestCase):
    def blockers(self, argv):
        args = cli.build_parser().parse_args(["run", *argv])
        with mock.patch("buffon.runner.facts.runner_checkout", return_value={"runner_dirty": False}):
            return cli.submission_blockers(args)

    def test_a_plain_run_has_no_blocker(self):
        self.assertEqual(self.blockers([]), [])
        self.assertEqual(self.blockers(["--aa", "all"]), [])
        self.assertEqual(self.blockers(["--allow-short"]), [])   # a note in `buffon verify`, not a rejection

    def test_each_rejected_flag_and_a_dirty_checkout_is_one_line(self):
        self.assertEqual(len(self.blockers(["--no-telemetry"])), 1)
        self.assertEqual(self.blockers(["--aa", "none"]), ["--aa none leaves arms without an A/A copy, so they have no noise floor"])
        args = cli.build_parser().parse_args(["run", "--no-telemetry", "--aa", "pi-node"])
        with mock.patch("buffon.runner.facts.runner_checkout", return_value={"runner_dirty": True}):
            self.assertEqual(len(cli.submission_blockers(args)), 3)

    def test_run_prints_them_before_it_starts(self):
        from buffon import backend
        seen = io.StringIO()

        class Fake:
            def check(self, isolation="none"):
                pass

            def run(self, session):
                import types
                return types.SimpleNamespace(exit_code=0, run_dir=session.run_dir, facts={})

        with mock.patch.object(backend, "get_backend", lambda site: Fake()), mock.patch("sys.stderr", seen), mock.patch("sys.stdout", io.StringIO()), \
                mock.patch("buffon.runner.facts.runner_checkout", return_value={"runner_dirty": False}):
            cli.main(["run", "overhead/version", "--no-telemetry", "--out", tempfile.mkdtemp()])
        self.assertIn("buffon: this run cannot be submitted: --no-telemetry", seen.getvalue())


if __name__ == "__main__":
    unittest.main()
