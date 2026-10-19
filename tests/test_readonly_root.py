# SPDX-License-Identifier: Apache-2.0
"""A pod's root file system is read-only and only its scratch directory (TMPDIR, HOME) is writable: the host lock and every default path must live there. The first real cluster run failed with
`OSError 30 Read-only file system: '/tmp/buffon.lock'` before any sample."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from buffon.runner import quiet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DefaultLock(unittest.TestCase):
    def pick(self, writable, env):
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(os.path, "isdir", lambda p: p in writable or p in ("/run/lock", "/var/tmp")), \
                mock.patch.object(os, "access", lambda p, mode: p in writable), mock.patch.object(tempfile, "gettempdir", lambda: "/platform/tmp"):
            os.environ.pop("BUFFON_LOCK_FILE", None) if "BUFFON_LOCK_FILE" not in env else None
            return quiet.default_lock()

    def test_the_host_wide_directories_win_when_they_are_writable(self):
        self.assertEqual(self.pick({"/run/lock", "/scratch/tmp"}, {"TMPDIR": "/scratch/tmp"}), "/run/lock/buffon.lock")
        self.assertEqual(self.pick({"/var/tmp", "/scratch/tmp"}, {"TMPDIR": "/scratch/tmp"}), "/var/tmp/buffon.lock")

    def test_a_read_only_root_falls_back_to_the_scratch_directory_the_pod_names_in_tmpdir(self):
        self.assertEqual(self.pick({"/scratch/tmp"}, {"TMPDIR": "/scratch/tmp"}), "/scratch/tmp/buffon.lock")

    def test_a_writable_tmp_wins_over_a_per_user_tmpdir(self):
        # review: a host whose /run/lock and /var/tmp are not writable fell back to TMPDIR (per user), so two users' runs no longer excluded each other
        self.assertEqual(self.pick({"/tmp", "/scratch/tmp"}, {"TMPDIR": "/scratch/tmp"}), "/tmp/buffon.lock")
        self.assertEqual(self.pick({"/scratch/tmp"}, {"TMPDIR": "/scratch/tmp"}), "/scratch/tmp/buffon.lock")

    def test_without_tmpdir_the_platforms_temporary_directory_is_used_and_an_explicit_path_always_wins(self):
        self.assertEqual(self.pick({"/platform/tmp"}, {"TMPDIR": ""}), "/platform/tmp/buffon.lock")
        self.assertEqual(self.pick(set(), {"BUFFON_LOCK_FILE": "/mine/lock"}), "/mine/lock")

    def test_a_lock_that_cannot_be_created_says_which_file_and_how_to_move_it(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(os, "open", side_effect=OSError(30, "Read-only file system")):
                with self.assertRaises(quiet.LockHeld) as caught:
                    quiet.HostLock(os.path.join(d, "x.lock")).__enter__()
        text = str(caught.exception)
        self.assertIn("cannot create the lock file", text)
        self.assertIn("Read-only file system", text)
        self.assertIn("BUFFON_LOCK_FILE", text)


@unittest.skipUnless(shutil.which("bwrap"), "needs bubblewrap to make the root file system read-only")
class EngineOnAReadOnlyRoot(unittest.TestCase):
    """The engine, started in a sandbox whose / is read-only and where only a scratch directory is writable, as in a bundle pod."""

    PROBE = ("import os, sys\nsys.path.insert(0, os.getcwd())\nfrom buffon.runner import engine\n"
             "plan = engine.Plan(workloads=[], arms=[], out=os.path.join(os.environ['TMPDIR'], 'out'), allow_short=True)\n"
             "try:\n    engine.Runner(plan, log=lambda *_: None).run()\nexcept engine.Refused as e:\n    print('REFUSED:', str(e)[:60])\n")

    def sandbox(self, scratch, *cmd, extra=()):
        argv = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--bind", scratch, scratch, "--chdir", ROOT, "--setenv", "TMPDIR", os.path.join(scratch, "tmp"),
                "--setenv", "HOME", os.path.join(scratch, "home"), *extra, *cmd]
        return subprocess.run(argv, capture_output=True, text=True, timeout=300)

    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.scratch, True)
        os.makedirs(os.path.join(self.scratch, "tmp"))
        os.makedirs(os.path.join(self.scratch, "home"))
        probe = self.sandbox(self.scratch, "sh", "-c", "touch /etc/buffon-write-test 2>/dev/null && echo writable || echo readonly")
        if probe.returncode != 0 or "readonly" not in probe.stdout:
            self.skipTest(f"bubblewrap cannot make / read-only here: {probe.stderr.strip()[:100]}")

    def test_the_root_really_is_read_only_and_the_scratch_directory_is_writable(self):
        out = self.sandbox(self.scratch, "sh", "-c", f"touch /tmp/buffon-x 2>/dev/null && echo tmp-writable || echo tmp-readonly; touch {self.scratch}/tmp/ok && echo scratch-writable")
        self.assertIn("tmp-readonly", out.stdout)
        self.assertIn("scratch-writable", out.stdout)

    def test_the_engine_takes_its_lock_and_lays_out_its_workspace_in_the_scratch_directory(self):
        done = self.sandbox(self.scratch, sys.executable, "-c", self.PROBE)
        self.assertEqual(done.returncode, 0, done.stderr[-600:])
        self.assertIn("REFUSED: no arm is available", done.stdout)   # past the host lock and the workspace, at the first thing a session without arms refuses
        self.assertTrue(os.path.exists(os.path.join(self.scratch, "tmp", "buffon.lock")))

    def test_a_read_only_root_without_a_scratch_directory_is_refused_with_the_lock_files_name(self):
        done = self.sandbox(self.scratch, sys.executable, "-c", "from buffon.runner import quiet\nwith quiet.HostLock('/tmp/not-writable.lock'):\n    pass\n", extra=("--unsetenv", "TMPDIR"))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("cannot create the lock file /tmp/not-writable.lock", done.stderr)


if __name__ == "__main__":
    unittest.main()
