# SPDX-License-Identifier: Apache-2.0
"""tools/external_ext.py and the pi-subagents row's helpers: a frozen fixture names exact versions with integrity, and a tree that differs from its lockfile is refused."""
import json
import os
import tempfile
import unittest

from tools import compat_subagents, external_ext


class Fixtures(unittest.TestCase):
    def test_every_fixture_pins_exact_versions_with_integrity(self):
        for name in sorted(os.listdir(external_ext.FIXTURES)):
            root = os.path.join(external_ext.FIXTURES, name)
            manifest = json.load(open(os.path.join(root, "package.json")))
            for package, version in manifest["dependencies"].items():
                self.assertRegex(version, r"^\d+\.\d+\.\d+$", f"{name}: {package} is not an exact version")
            lock = json.load(open(os.path.join(root, "package-lock.json")))
            for path, entry in lock["packages"].items():
                if path:
                    self.assertTrue(entry.get("integrity", "").startswith("sha512-"), f"{name}: {path} has no integrity")
            npmrc = open(os.path.join(root, ".npmrc")).read()
            self.assertIn("ignore-scripts=true", npmrc, f"{name}: install scripts must be off")

    def test_a_tree_that_differs_from_the_lockfile_is_refused(self):
        with tempfile.TemporaryDirectory() as dest:
            lock = {"packages": {"": {}, "node_modules/x": {"version": "1.0.0", "integrity": "sha512-a"}}}
            json.dump(lock, open(os.path.join(dest, "package-lock.json"), "w"))
            with self.assertRaisesRegex(RuntimeError, "not installed"):
                external_ext.record(dest)
            os.makedirs(os.path.join(dest, "node_modules", "x"))
            json.dump({"version": "1.0.1"}, open(os.path.join(dest, "node_modules", "x", "package.json"), "w"))
            with self.assertRaisesRegex(RuntimeError, "installed 1.0.1, lockfile 1.0.0"):
                external_ext.record(dest)


class Scrub(unittest.TestCase):
    def test_ids_paths_and_call_ids_are_scrubbed(self):
        text = "run 9c2efbb4-32f0-48ed-a98c-a57f9449577b at /tmp/fffcompat/home/x call_12_0"
        self.assertEqual(compat_subagents.scrub(text), "run <id> at <path> <call>")


if __name__ == "__main__":
    unittest.main()
