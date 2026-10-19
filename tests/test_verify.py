"""Host disclosure and host class in a real run directory (engine -> host.json/raw.json -> buffon verify), and the host-global lock path."""
import json
import os
import shutil
import tempfile
import unittest

from buffon import verify
from buffon.arms import install, manifest
from buffon.runner import engine, quiet, sysinfo


def run_dir(**plan_kw):
    out = tempfile.mkdtemp()
    stub_root = tempfile.mkdtemp()

    def fake_install(self, a, source_repos=None):
        a.binary, a.install_dir, a.record, a.version_line = shutil.which("true"), stub_root, {}, "stub 1"
        return a
    plan = engine.Plan(workloads=[], arms=[manifest.load_arm("pi-node")], rounds=12, aa="none", pinning="none", out=out, calibrate=False, cache_dir=tempfile.mkdtemp(),
                       lock_file=os.path.join(tempfile.mkdtemp(), "l"), **plan_kw)
    saved = (install.Workspace.install, engine.Runner.measure)
    install.Workspace.install, engine.Runner.measure = fake_install, lambda self, ctx, inst: None
    try:
        try:
            engine.Runner(plan, log=lambda *_: None).run()
        except engine.Refused as error:
            return out, str(error)
    finally:
        install.Workspace.install, engine.Runner.measure = saved
    return out, None


class RunDirectory(unittest.TestCase):
    def test_a_run_writes_host_json_with_every_required_key_and_the_class(self):
        out, refused = run_dir()
        self.assertIsNone(refused)
        with open(os.path.join(out, "host.json")) as f:
            host = json.load(f)
        self.assertEqual([k for k in sysinfo.REQUIRED if k not in host], [])
        self.assertEqual(host["host_class"], "B")
        with open(os.path.join(out, "raw.json")) as f:
            raw = json.load(f)
        self.assertEqual((raw["run"]["host_class"], raw["hardware"]["quiet_dedicated"]), ("B", False))
        self.assertIn("host class B", " ".join(raw["hardware"]["reasons"]))
        self.assertIn("pid", raw["run"]["lock_holder"])

    def test_a_class_a_requirement_refuses_a_class_b_host_and_names_the_reasons(self):
        out, refused = run_dir(require_class="A")
        self.assertRegex(refused, r"this host is class B, the run requires class A: ")

    def test_verify_accepts_the_directory_the_engine_wrote_except_for_what_the_stub_run_lacks(self):
        out, _ = run_dir()
        problems = dict(verify.verify(out))
        self.assertEqual((problems["raw"], problems["host-disclosure"], problems["host-class"]), ([], [], []))


class Verify(unittest.TestCase):
    def good(self):
        out, _ = run_dir()
        return out

    def edit(self, out, name, fn):
        path = os.path.join(out, name)
        with open(path) as f:
            doc = json.load(f)
        fn(doc)
        with open(path, "w") as f:
            json.dump(doc, f)

    def test_a_missing_host_json_is_rejected(self):
        out = self.good()
        os.unlink(os.path.join(out, "host.json"))
        self.assertIn("host.json is missing", dict(verify.verify(out))["host-disclosure"][0])
        self.assertEqual(verify.main([out], out=lambda *_: None), 1)

    def test_a_required_key_missing_is_rejected(self):
        out = self.good()
        self.edit(out, "host.json", lambda d: d.pop("microcode"))
        self.assertIn("host.json lacks `microcode`", dict(verify.verify(out))["host-disclosure"])

    def test_a_null_needs_its_reason(self):
        out = self.good()
        self.edit(out, "host.json", lambda d: (d.__setitem__("thp", None), d["unavailable"].pop("thp", None)))
        self.assertIn("host.json has `thp` = null without a reason in `unavailable`", dict(verify.verify(out))["host-disclosure"])
        self.edit(out, "host.json", lambda d: d["unavailable"].__setitem__("thp", "no THP support"))
        self.assertEqual(dict(verify.verify(out))["host-disclosure"], [])

    def test_a_quiet_dedicated_label_on_a_class_b_host_is_rejected(self):
        out = self.good()
        self.edit(out, "raw.json", lambda d: d["hardware"].__setitem__("quiet_dedicated", True))
        self.assertIn("the run is labelled quiet-dedicated but the host is class B", dict(verify.verify(out))["host-class"])

    def test_disagreeing_host_class_between_host_json_and_raw_json_is_rejected(self):
        out = self.good()
        self.edit(out, "host.json", lambda d: d.__setitem__("host_class", "A"))
        self.assertIn("host.json and raw.json disagree about the host class", dict(verify.verify(out))["host-class"])

    def test_a_run_with_no_arm_digest_or_a_dirty_runner_is_rejected(self):
        out = self.good()
        self.edit(out, "raw.json", lambda d: (d.__setitem__("lock_sha256", None), d["runner"].__setitem__("dirty", True)))
        self.assertEqual(len(dict(verify.verify(out))["provenance"]), 2)


class LockPath(unittest.TestCase):
    def test_the_default_lock_is_host_global_and_ignores_tmpdir(self):
        saved = {k: os.environ.pop(k, None) for k in ("BUFFON_LOCK_FILE", "TMPDIR")}
        try:
            os.environ["TMPDIR"] = "/private-tmp-of-one-user"
            path = quiet.default_lock()
            self.assertNotIn("private-tmp-of-one-user", path)
            self.assertIn(os.path.dirname(path), ("/run/lock", "/var/tmp", "/tmp"))
            os.environ["BUFFON_LOCK_FILE"] = "/x/y.lock"
            self.assertEqual(quiet.default_lock(), "/x/y.lock")
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v

    def test_the_lock_file_is_openable_by_every_user_so_a_second_user_is_refused_by_it(self):
        path = os.path.join(tempfile.mkdtemp(), "l")
        with quiet.HostLock(path):
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o666)
            self.assertRegex(quiet.HostLock(path).holder(), r"^pid \d+ user \S+ since \d{4}-")


class Isolation(unittest.TestCase):
    def test_a_run_is_stamped_uncontained_until_the_envelope_is_wired_in_and_verify_requires_the_stamp(self):
        out, refused = run_dir()
        self.assertIsNone(refused)
        with open(os.path.join(out, "raw.json")) as f:
            raw = json.load(f)
        self.assertEqual(raw["run"]["isolation"], {"isolation": "none", "comparable": False, "stamp": "uncontained, not comparable"})
        self.assertEqual(dict(verify.verify(out))["isolation"], [])
        path = os.path.join(out, "raw.json")
        raw["run"]["isolation"]["comparable"] = True
        with open(path, "w") as f:
            json.dump(raw, f)
        self.assertEqual(len(dict(verify.verify(out))["isolation"]), 1)
        del raw["run"]["isolation"]
        with open(path, "w") as f:
            json.dump(raw, f)
        self.assertIn("does not state the isolation", dict(verify.verify(out))["isolation"][0])

    def test_container_isolation_needs_pinned_cpus_a_cpuset_is_part_of_the_envelope(self):
        out, refused = run_dir(isolation="container")
        self.assertRegex(refused, "needs pinned CPUs")
