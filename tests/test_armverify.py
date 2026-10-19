# SPDX-License-Identifier: Apache-2.0
"""`buffon arm verify` reaches its implementation: the command crashed with an AttributeError after verify.py became the run-directory check."""
import contextlib
import io
import os
import unittest

from buffon import cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ArmVerify(unittest.TestCase):
    def run_cli(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["arm", "verify", *argv, "--site", os.path.join(ROOT, "sites", "example-local.toml")])
        return code, err.getvalue()

    def test_an_unknown_arm_is_named_and_refused(self):
        code, err = self.run_cli("no-such-arm")
        self.assertEqual(code, 2)
        self.assertIn("unknown arm 'no-such-arm'", err)

    def test_a_held_arm_is_refused_without_installing(self):
        code, err = self.run_cli("piglet-combined")
        self.assertEqual(code, 3)
        self.assertIn("is held and never runs", err)


if __name__ == "__main__":
    unittest.main()
