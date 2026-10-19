# SPDX-License-Identifier: Apache-2.0
"""Review guards: the version check runs scrubbed, the installed tree is what ran, and a run without an A/A copy, an egress audit or a clean
checkout is never labelled quiet dedicated hardware."""
import os
import shutil
import tempfile
import types
import unittest

from buffon.arms import install, manifest
from buffon.runner import engine
from buffon.runner.harness import SYSTEM_PATH, Harness, scrubbed_environ


def arm(name, twin_of=None):
    return types.SimpleNamespace(id=name, twin_of=twin_of)


class VersionCheckEnvironment(unittest.TestCase):
    def test_the_operators_agent_dirs_and_keys_never_reach_the_version_check(self):
        root = tempfile.mkdtemp()
        ws = types.SimpleNamespace(root=root)
        a = types.SimpleNamespace(env={"PI_OFFLINE": "1", "PIG_CODING_AGENT_DIR": "{agent_dir}"}, path_dirs=["/opt/node/bin"])
        saved = dict(os.environ)
        os.environ.update(PIG_CODING_AGENT_DIR="/operator/agent", PI_CODING_AGENT_DIR="/operator/pi", OPENAI_API_KEY="sk-real", HTTPS_PROXY="http://proxy",
                          CODEX_HOME="/operator/codex", PI_SESSION_FILE="/operator/s.jsonl")
        try:
            env = install.Workspace.plain_env(ws, a)
        finally:
            os.environ.clear()
            os.environ.update(saved)
        for k in ("PI_CODING_AGENT_DIR", "OPENAI_API_KEY", "HTTPS_PROXY", "CODEX_HOME", "PI_SESSION_FILE"):
            self.assertNotIn(k, env)
        self.assertEqual(env["PIG_CODING_AGENT_DIR"], os.path.join(root, "version-home", ".agent"))
        self.assertEqual(env["HOME"], os.path.join(root, "version-home"))
        self.assertEqual(env["PI_OFFLINE"], "1")
        self.assertEqual(env["PATH"], os.pathsep.join(["/opt/node/bin", *SYSTEM_PATH]))

    def test_scrub_keeps_ordinary_variables(self):
        env = scrubbed_environ({"PATH": "/bin", "LANG": "C", "LC_ALL": "C.UTF-8", "TZ": "UTC", "PI_X": "1", "GOFLAGS": "-x", "MY_TOKEN": "t", "http_proxy": "p"})
        self.assertEqual(env, {"LANG": "C", "LC_ALL": "C.UTF-8", "TZ": "UTC"})

    def test_only_locale_and_time_zone_are_inherited_from_the_operator(self):
        """The lane shell's GOMAXPROCS inflated a Go arm under one-core pinning: tuning variables must never reach an arm, whatever their prefix."""
        env = scrubbed_environ({"GOMAXPROCS": "24", "GOMEMLIMIT": "1GiB", "GOGC": "50", "GODEBUG": "x=1", "NODE_OPTIONS": "--x", "LD_PRELOAD": "/x", "PYTHONPATH": "/p",
                                "MISE_SHELL": "bash", "SSL_CERT_FILE": "/c", "USER": "me", "LANG": "C"})
        self.assertEqual(env, {"LANG": "C"})

    def test_a_harness_gets_no_runtime_tuning_unless_its_manifest_sets_it(self):
        work = tempfile.mkdtemp()
        a = types.SimpleNamespace(id="x", env={"PI_OFFLINE": "1"}, spec={"state": {"dirs": []}}, path_dirs=[], writer_path=lambda: None)
        tuned = types.SimpleNamespace(id="y", env={"PI_OFFLINE": "1", "GOGC": "400"}, spec={"state": {"dirs": []}}, path_dirs=[], writer_path=lambda: None)
        server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
        saved_env, saved_loader = dict(os.environ), Harness.__init__.__globals__["load_writer"]
        os.environ.update(GOMAXPROCS="24", GOMEMLIMIT="1GiB", NODE_OPTIONS="--x", LD_PRELOAD="/x", LANG="C")
        Harness.__init__.__globals__["load_writer"] = lambda arm: (lambda spec: {})
        try:
            plain, manifest_set = Harness(a, work, server), Harness(tuned, work + "/u", server)
            scrubbed = plain.isolation_env()["scrubbed"]     # read while the operator's variables are still set: it names what the harness did not inherit
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
            Harness.__init__.__globals__["load_writer"] = saved_loader
        for env in (plain.env, manifest_set.env):   # neither the operator's GOMAXPROCS nor one of Buffon's own: a Go arm sizes itself by its default
            for k in ("GOMAXPROCS", "GOMEMLIMIT", "NODE_OPTIONS", "LD_PRELOAD"):
                self.assertNotIn(k, env)
            self.assertEqual(env["PI_OFFLINE"], "1")
        self.assertNotIn("GOGC", plain.env)
        self.assertEqual(manifest_set.env["GOGC"], "400")   # what the manifest's [env] sets reaches the arm
        self.assertIn("GOMEMLIMIT", scrubbed)

    # What a harness may hold: the operator's locale and time zone, what the harness sets, and what the arm's manifest names. Nothing else, whatever the operator's shell exports.
    HARNESS_KEYS = {"LANG", "TZ", "PATH", "HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "TMPDIR", "NO_COLOR", "TERM", "NO_PROXY", "no_proxy", "PI_OFFLINE"}

    def test_a_harness_environment_is_the_allow_list_whatever_the_operator_exports(self):
        """Caller variables seen on a Mac run: AGENT, AI_AGENT, ANTHROPIC_*. The harness environment is built from the allow-list on every OS, never from os.environ."""
        work = tempfile.mkdtemp()
        a = types.SimpleNamespace(id="x", env={"PI_OFFLINE": "1"}, spec={"state": {"dirs": []}}, path_dirs=[], writer_path=lambda: None)
        server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
        saved_env, saved_loader = dict(os.environ), Harness.__init__.__globals__["load_writer"]
        os.environ.update(AGENT="codex", AI_AGENT="x", ANTHROPIC_API_KEY="sk-real", ANTHROPIC_BASE_URL="https://example.invalid", OPENAI_API_KEY="sk-real", GITHUB_TOKEN="t",
                          HTTPS_PROXY="http://proxy", GOMEMLIMIT="1GiB", LANG="C", TZ="UTC", LC_ALL="C")
        Harness.__init__.__globals__["load_writer"] = lambda arm: (lambda spec: {})
        try:
            env = Harness(a, work, server).env
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
            Harness.__init__.__globals__["load_writer"] = saved_loader
        self.assertEqual(set(env) - self.HARNESS_KEYS - {"LC_ALL"}, set())
        self.assertEqual((env["LANG"], env["TZ"], env["LC_ALL"]), ("C", "UTC", "C"))


class HarnessPath(unittest.TestCase):
    def test_the_operators_path_never_reaches_an_arm(self):
        """A version-manager shim on the operator's PATH (mise, asdf) downloads fd or rg when Pi probes for them: observed as egress on every PTY sample."""
        work = tempfile.mkdtemp()
        a = types.SimpleNamespace(id="x", env={}, spec={"state": {"dirs": []}}, path_dirs=["/opt/node/bin"], writer_path=lambda: None)
        server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
        saved_path, saved_loader = os.environ.get("PATH"), Harness.__init__.__globals__["load_writer"]
        os.environ["PATH"] = "/operator/.local/share/mise/shims:/usr/bin:/bin"
        Harness.__init__.__globals__["load_writer"] = lambda arm: (lambda spec: {})
        try:
            h = Harness(a, work, server)
        finally:
            os.environ["PATH"] = saved_path
            Harness.__init__.__globals__["load_writer"] = saved_loader
        self.assertEqual(h.env["PATH"], os.pathsep.join(["/opt/node/bin", *SYSTEM_PATH]))


class TreeDigest(unittest.TestCase):
    def tree(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "pkg", "dist"))
        with open(os.path.join(d, "pkg", "dist", "main.js"), "w") as f:
            f.write("console.log(1)\n")
        with open(os.path.join(d, "pkg", "cli.js"), "w") as f:
            f.write("import './dist/main.js'\n")
        os.symlink("pkg/cli.js", os.path.join(d, "pi"))
        return d

    def test_any_change_below_the_entry_script_changes_the_digest(self):
        d = self.tree()
        base = install.tree_sha256(d)
        self.assertEqual(install.tree_sha256(d), base)
        with open(os.path.join(d, "pkg", "dist", "main.js"), "a") as f:
            f.write("// patched\n")
        self.assertNotEqual(install.tree_sha256(d), base)

    def test_mode_symlink_and_new_files_count(self):
        for change in (lambda d: os.chmod(os.path.join(d, "pkg", "cli.js"), 0o755),
                       lambda d: (os.unlink(os.path.join(d, "pi")), os.symlink("pkg/dist/main.js", os.path.join(d, "pi"))),
                       lambda d: open(os.path.join(d, "pkg", "extra.js"), "w").close()):
            d = self.tree()
            base = install.tree_sha256(d)
            change(d)
            self.assertNotEqual(install.tree_sha256(d), base)


class ArmRuntime(unittest.TestCase):
    def test_a_sidecar_arm_gets_the_pinned_node_and_a_wrong_version_is_an_error(self):
        pig = manifest.load_arm("pig-0.4.1")
        self.assertEqual(pig.spec["runtime"], {"node": manifest.load_runtimes()["node"]["version"]})
        spec = dict(pig.spec, runtime={"node": "1.0.0"})
        with self.assertRaisesRegex(manifest.ManifestError, "runtimes.toml pins"):
            manifest.validate("pig-0.4.1", spec, pig.dir)
        with self.assertRaisesRegex(manifest.ManifestError, "not pinned"):
            manifest.validate("pig-0.4.1", dict(pig.spec, runtime={"deno": "2"}), pig.dir)

    def test_every_sidecar_arm_declares_node(self):
        for name, a in manifest.load_all().items():
            if a.pi_extensions == "sidecar":
                self.assertIn("node", a.spec.get("runtime", {}), name)


class FactsBeforePinning(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "sched_setaffinity"), "no CPU affinity on this platform")
    def test_cpus_allowed_is_the_sessions_set_not_the_mocks(self):
        allowed = sorted(os.sched_getaffinity(0))
        if len(allowed) < 2:
            self.skipTest("needs two CPUs")
        seen = {}

        class Stop(Exception):
            pass

        def collect(*_a, **_k):
            seen["affinity"] = sorted(os.sched_getaffinity(0))
            raise Stop()
        plan = engine.Plan(workloads=[], arms=[], cpus=allowed[:1], mock_cpus=allowed[1:2], rounds=12, out=tempfile.mkdtemp(), lock_file=os.path.join(tempfile.mkdtemp(), "l"))
        saved = engine.factlib.collect
        engine.factlib.collect = collect
        try:
            with self.assertRaises(Stop):
                engine.Runner(plan, log=lambda *_: None).run()
        finally:
            engine.factlib.collect = saved
            os.sched_setaffinity(0, allowed)
            engine.cgroup.set_pinned_cpus(None)
        self.assertEqual(seen["affinity"], allowed)


class RunLabel(unittest.TestCase):
    PLAN = types.SimpleNamespace(aa="all", aa_set=True, aa_effective="all")

    def test_a_clean_audited_run_with_every_copy_adds_no_reason(self):
        inst = [arm("a"), arm("b"), arm("a-b", "a"), arm("b-b", "b")]
        self.assertEqual(engine.run_reasons(self.PLAN, inst[:2], inst, {"mode": "socket-audit"}, {"runner_dirty": False}), [])

    def test_missing_copies_no_audit_and_a_dirty_checkout_are_named(self):
        inst = [arm("a"), arm("b"), arm("a-b", "a")]
        why = engine.run_reasons(types.SimpleNamespace(aa="a", aa_set=True, aa_effective="a"), inst[:2], inst, {"mode": "none"}, {"runner_dirty": True})
        self.assertEqual(len(why), 3)
        self.assertIn("no A/A copy of b", why[0])
        self.assertIn("egress", why[1])
        self.assertIn("uncommitted", why[2])


if __name__ == "__main__":
    unittest.main()


class RefusedRunKeepsItsRecord(unittest.TestCase):
    """METHODOLOGY section 9: a run the calibration gate refuses still writes raw.json with the calibration samples and the reason (finding 16)."""

    def refuse(self, allow_noisy, strict=True):
        out = tempfile.mkdtemp()
        stub_root = tempfile.mkdtemp()

        def fake_install(self, a, source_repos=None):
            a.binary, a.install_dir, a.record, a.version_line = shutil.which("true"), stub_root, {}, "stub 1"
            return a
        calibration = {"metric": "cpu_ms", "scenario": "overhead/print", "api": "openai-completions", "arm": "pi-node", "runs": 2, "cv": {"pi-node": 0.4}, "max_cv": 0.4, "gate": 0.05,
                       "passed": False, "samples": [{"arm": "pi-node", "cpu_ms": 1.0}]}
        plan = engine.Plan(workloads=[], arms=[manifest.load_arm("pi-node")], rounds=12, aa="none", pinning="none", out=out, allow_noisy=allow_noisy, strict=strict, cache_dir=tempfile.mkdtemp(), lock_file=os.path.join(tempfile.mkdtemp(), "l"))
        saved = (install.Workspace.install, engine.Runner.calibrate, engine.Runner.measure)
        install.Workspace.install, engine.Runner.calibrate, engine.Runner.measure = fake_install, lambda self, ctx, inst: calibration, lambda self, ctx, inst: None
        try:
            return out, engine.Runner(plan, log=lambda *_: None)
        finally:
            self.saved = saved

    def run_it(self, allow_noisy, strict=True):
        out, runner = self.refuse(allow_noisy, strict)
        try:
            try:
                runner.run()
                refused = False
            except engine.Refused:
                refused = True
        finally:
            install.Workspace.install, engine.Runner.calibrate, engine.Runner.measure = self.saved
        return out, refused

    def test_the_refusal_leaves_raw_json_with_the_calibration_and_the_reason(self):
        import json
        out, refused = self.run_it(False)
        self.assertTrue(refused)
        with open(os.path.join(out, "raw.json")) as f:
            raw = json.load(f)
        self.assertFalse(raw["ok"])
        self.assertIn("calibration gate failed", raw["refused"])
        self.assertEqual(raw["calibration"]["samples"], [{"arm": "pi-node", "cpu_ms": 1.0}])
        self.assertEqual(raw["samples"], [])

    def test_without_strict_mode_a_noisy_run_is_measured_recorded_and_labelled_noisy(self):
        import json
        from buffon import trust
        out, refused = self.run_it(False, strict=False)
        self.assertFalse(refused)
        with open(os.path.join(out, "raw.json")) as f:
            raw = json.load(f)
        self.assertNotIn("refused", raw)
        self.assertEqual(raw["calibration"]["max_cv"], 0.4)
        self.assertEqual(trust.badge(raw)["badge"], "Noisy")

    def test_allow_noisy_measures_and_records_no_refusal(self):
        import json
        out, refused = self.run_it(True)
        self.assertFalse(refused)
        with open(os.path.join(out, "raw.json")) as f:
            raw = json.load(f)
        self.assertNotIn("refused", raw)
        self.assertEqual(raw["hardware"]["class"], "provisional")


class RunnerRefusesToStartOutsideTheRunTmp(unittest.TestCase):
    """Incident 00:27Z: a shared lane agent directory lost its session directories. A harness whose HOME, agent directory, session directory or any other state directory is outside the run's throwaway tree is refused before anything is created, emptied or started."""

    def start(self, work, env=None, writer=None, shared=None):
        a = types.SimpleNamespace(id="x", env=env or {}, spec={"state": {"dirs": []}}, path_dirs=[], writer_path=lambda: None, vars={"shared_dir": shared} if shared else {})
        server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
        saved = Harness.__init__.__globals__["load_writer"]
        Harness.__init__.__globals__["load_writer"] = lambda arm: (lambda spec: writer or {})
        try:
            return Harness(a, work, server)
        finally:
            Harness.__init__.__globals__["load_writer"] = saved

    def test_a_clean_harness_starts_and_a_shared_dir_inside_the_workspace_is_allowed(self):
        work = tempfile.mkdtemp()
        shared = tempfile.mkdtemp()
        h = self.start(work, env={"PIG_HOME": shared + "/pig-home"}, shared=shared)
        self.assertTrue(h.env["HOME"].startswith(work))

    def test_a_manifest_that_points_an_agent_dir_session_dir_or_home_elsewhere_is_refused(self):
        from buffon.runner.harness import Unconfined
        elsewhere = tempfile.mkdtemp()
        for name in ("PI_CODING_AGENT_DIR", "PIG_CODING_AGENT_DIR", "PIG_HOME", "PI_HOME", "HOME", "XDG_DATA_HOME", "TMPDIR", "PI_SESSION_DIR", "SOME_AGENT_DIR"):
            with self.subTest(name=name), self.assertRaises(Unconfined) as caught:
                self.start(tempfile.mkdtemp(), env={name: elsewhere})
            self.assertIn(name, str(caught.exception))

    def test_a_writer_that_returns_an_outside_directory_is_refused_too(self):
        from buffon.runner.harness import Unconfined
        with self.assertRaises(Unconfined):
            self.start(tempfile.mkdtemp(), writer={"PI_CODING_AGENT_DIR": tempfile.mkdtemp()})

    def test_a_symlink_out_of_the_tree_does_not_count_as_inside(self):
        from buffon.runner.harness import Unconfined
        work, outside = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.symlink(outside, os.path.join(work, "link"))
        with self.assertRaises(Unconfined):
            self.start(work, env={"PI_CODING_AGENT_DIR": os.path.join(work, "link", "agent")})

    def test_a_relative_or_tilde_state_directory_is_refused(self):
        """Review: values not starting with / were skipped, so PIG_HOME=../../x or ~/.pig escaped the check."""
        from buffon.runner.harness import Unconfined
        for value in ("../../outside", "~/.pig", "rel/agent"):
            with self.assertRaises(Unconfined):
                self.start(tempfile.mkdtemp(), env={"PIG_HOME": value})

    def test_nothing_outside_is_created_or_emptied_before_the_refusal(self):
        """The check runs before the shared PIG_HOME is emptied and before the manifest's state directories are made."""
        from buffon.runner.harness import Unconfined
        outside = tempfile.mkdtemp()
        keep = os.path.join(outside, "sessions", "keep.jsonl")
        os.makedirs(os.path.dirname(keep))
        open(keep, "w").write("x")
        with self.assertRaises(Unconfined):
            self.start(tempfile.mkdtemp(), env={"PIG_HOME": outside})
        self.assertTrue(os.path.exists(keep))
