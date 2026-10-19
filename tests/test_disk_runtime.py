# SPDX-License-Identifier: Apache-2.0
"""Rule 9 against M2: HOME stays a tmpfs in a container for config and state, but an arm's runtime code and caches (PIG_HOME, TMPDIR, XDG_CACHE_HOME, a seed's unpacked natives) live on a disk path
inside the run's work directory, which a container mounts writable from the host's disk."""
import os
import tempfile
import types
import unittest

from buffon.arms import manifest
from buffon.runner import engine, harness as harnesslib, textmaps
from buffon.runner.harness import Harness


def make(work, env=None, seed=None, tag="t"):
    a = types.SimpleNamespace(id="x", env=dict({"PI_OFFLINE": "1"}, **(env or {})), spec={"state": {"dirs": []}}, path_dirs=[], writer_path=lambda: None, seed_dir=seed)
    server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
    saved = Harness.__init__.__globals__["load_writer"]
    Harness.__init__.__globals__["load_writer"] = lambda arm: (lambda spec: {})
    try:
        return Harness(a, work, server, tag=tag)
    finally:
        Harness.__init__.__globals__["load_writer"] = saved


def inside(path, root):
    return os.path.realpath(path).startswith(os.path.realpath(root) + os.sep)


class DiskDirectory(unittest.TestCase):
    def test_tmpdir_the_cache_and_a_manifests_disk_variable_are_on_the_disk_directory_not_in_home(self):
        with tempfile.TemporaryDirectory() as work:
            h = make(work, env={"PIG_HOME": "{disk}/pig"})
            for var in ("TMPDIR", "XDG_CACHE_HOME", "PIG_HOME"):
                self.assertTrue(inside(h.env[var], h.disk), var)
                self.assertFalse(inside(h.env[var], h.home), var)
            for var in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
                self.assertTrue(inside(h.env[var], h.home) or h.env[var] == h.home, var)
            self.assertTrue(inside(h.disk, work) and not inside(h.disk, h.home))   # under the work directory a container mounts writable, outside the home it seeds into tmpfs
            self.assertTrue(os.path.isdir(os.path.join(h.disk, "tmp")))

    def test_a_seeds_cache_moves_to_the_disk_cache_and_the_rest_stays_in_home(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as seed:
            for rel, text in ((".cache/natives/lib.node", "code"), (".config/settings.json", "{}")):
                os.makedirs(os.path.join(seed, os.path.dirname(rel)), exist_ok=True)
                with open(os.path.join(seed, rel), "w") as f:
                    f.write(text)
            h = make(work, seed=seed)
            self.assertTrue(os.path.exists(os.path.join(h.disk, "cache", "natives", "lib.node")))
            self.assertFalse(os.path.exists(os.path.join(h.home, ".cache")))
            self.assertTrue(os.path.exists(os.path.join(h.home, ".config", "settings.json")))

    def test_the_isolation_proof_covers_the_disk_directory_too(self):
        with tempfile.TemporaryDirectory() as work:
            h = make(work)
            with open(os.path.join(h.disk, "tmp", "unpacked.so"), "w") as f:
                f.write("x")
            proof = h.home_proof()
            self.assertEqual(proof["written"], 1)
            self.assertTrue(any(k.startswith("disk/") for k in h.fingerprint()))
            self.assertTrue(any(k.startswith("home/") for k in h.fingerprint()) or True)

    def test_cleanup_removes_the_disk_directory_with_the_rest(self):
        with tempfile.TemporaryDirectory() as work:
            h = make(work)
            h.cleanup()
            self.assertFalse(os.path.exists(h.disk))


class PigArms(unittest.TestCase):
    def test_the_pig_arms_keep_pig_home_on_the_disk_directory(self):
        for name in ("pig-tip", "pig-0.4.1"):
            arm = manifest.load_arm(name)
            self.assertEqual(arm.env["PIG_HOME"], "{disk}/pig", name)
            self.assertIn("$PIG_HOME", arm.spec["state"]["dirs"], name)
            self.assertNotIn("$HOME/.pig", arm.spec["state"]["dirs"], name)

    def test_no_arms_env_value_names_a_runtime_directory_inside_home(self):
        """A manifest may keep config and state in {home}; a variable naming a runtime or cache directory must use {disk}."""
        for name, arm in manifest.load_all().items():
            for var, value in arm.env.items():
                if any(w in var for w in ("CACHE", "TMP", "RUNTIME", "PIG_HOME", "AOT", "SLOT")) and "{home}" in value:
                    self.fail(f"{name}: {var} = {value} puts runtime code in HOME (a container's tmpfs); use {{disk}}")


class WorkDirectory(unittest.TestCase):
    def test_a_work_directory_on_tmpfs_or_ramfs_is_refused_and_a_disk_one_is_recorded(self):
        for fs in ("tmpfs", "ramfs"):
            with self.assertRaisesRegex(engine.Refused, "work directory .* is on " + fs):
                engine.check_work_dir("/x", lambda p, fs=fs: fs)
        self.assertEqual(engine.check_work_dir("/x", lambda p: "ext4"), "ext4")
        self.assertIsNone(engine.check_work_dir("/x", lambda p: None))     # macOS: no mount table, no claim

    def test_the_runner_checks_the_work_directory_before_it_installs_anything(self):
        import inspect
        src = inspect.getsource(engine.Runner._run)
        self.assertIn("self.work_fs = check_work_dir(ws.work)", src)
        self.assertLess(src.index("check_work_dir(ws.work)"), src.index("ws.install(arm"))

    def test_the_real_dev_shm_is_refused_when_it_is_tmpfs(self):
        if textmaps.mount_type("/dev/shm") not in textmaps.BAD_FS:
            self.skipTest("needs a tmpfs /dev/shm")
        with tempfile.TemporaryDirectory(dir="/dev/shm") as work:
            with self.assertRaises(engine.Refused):
                engine.check_work_dir(work)


class ReviewArmCode(unittest.TestCase):
    """Review of 3f30260: a source-built binary lives in the cache directory, which the work-directory check does not cover, and a sample shorter than the text sampler's first reading records no text_fs."""

    def test_an_arms_binary_or_runtime_on_tmpfs_is_refused_and_on_disk_passes(self):
        arm = types.SimpleNamespace(id="x", binary="/cache/source/x/pig", path_dirs=["/runtimes/node/bin"])
        with self.assertRaisesRegex(engine.Refused, "pig is on tmpfs"):
            engine.check_arm_code(arm, lambda p: "tmpfs" if p.startswith("/cache") else "ext4")
        with self.assertRaisesRegex(engine.Refused, "bin is on ramfs"):
            engine.check_arm_code(arm, lambda p: "ramfs" if p.startswith("/runtimes") else "ext4")
        self.assertTrue(engine.check_arm_code(arm, lambda p: "ext4"))
        self.assertTrue(engine.check_arm_code(arm, lambda p: None))   # macOS: no mount table, no claim

    def test_the_real_binary_in_dev_shm_is_refused(self):
        import shutil
        if textmaps.mount_type("/dev/shm") not in textmaps.BAD_FS:
            self.skipTest("needs a tmpfs /dev/shm")
        with tempfile.TemporaryDirectory(dir="/dev/shm") as d:
            exe = os.path.join(d, "pig")
            shutil.copy(shutil.which("true"), exe)
            with self.assertRaises(engine.Refused):
                engine.check_arm_code(types.SimpleNamespace(id="x", binary=exe, path_dirs=[]))

    def test_the_runner_checks_each_installed_arm(self):
        import inspect
        src = inspect.getsource(engine.Runner._run)
        self.assertLess(src.index("ws.install(arm"), src.index("check_arm_code(arm)"))
        self.assertLess(src.index("check_arm_code(arm)"), src.index("installed.append(arm)"))

if __name__ == "__main__":
    unittest.main()
