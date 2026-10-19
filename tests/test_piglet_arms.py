# SPDX-License-Identifier: Apache-2.0
"""Piglet arms: manifest validation, identity refusal, build refusal and neutral inheritance (no PiG build runs here; see the dry run in the commit message)."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from buffon.arms import install, manifest, piglet

COMMIT = "a" * 40
SHA = "b" * 64
ZERO = "0" * 64
ROOT = manifest.ROOT


IDENTITY = {"component_plan_digest": SHA}


def piglet_table(**over):
    table = {"name": "bench-lean", "pigpen_commit": COMMIT, "repo_env": "BUFFON_SOURCE_REPO_PIGPEN", "manifest": "piglets/bench-lean/piglet.yaml", "manifest_sha256": SHA, "release_version": "0.1.0", "identity": dict(IDENTITY)}
    table.update(over)
    return table


def spec_with(piglet_over=None, held=False, **top):
    spec = {"name": "x", "label": "x", "homepage": "https://example.invalid", "relation": "reference", "licence": "MIT", "licence_url": "https://example.invalid", "version": "1", "piglet": piglet_table(**(piglet_over or {}))}
    if held:
        spec["held"] = "held for a test"
    else:
        spec["derive"] = {"base": "pig-tip"}
        spec["endpoint"] = {"apis": ["openai-completions"], "writer": "writer.py"}
        spec["modes"] = {"version": ["--version"]}
    spec.update(top)
    return spec


class ManifestValidation(unittest.TestCase):
    def check(self, spec):
        with tempfile.TemporaryDirectory() as d:
            manifest.validate("x", spec, d)

    def test_a_pinned_runnable_piglet_arm_is_accepted(self):
        self.check(spec_with())

    def test_a_short_pigpen_commit_is_refused(self):
        with self.assertRaisesRegex(manifest.ManifestError, "40-hex"):
            self.check(spec_with({"pigpen_commit": "abc"}))

    def test_a_manifest_outside_the_commit_is_refused(self):
        for bad in ("/etc/piglet.yaml", "piglets/../../x.yaml", "piglets/x.json"):
            with self.subTest(bad=bad), self.assertRaises(manifest.ManifestError):
                self.check(spec_with({"manifest": bad}))

    def test_a_runnable_piglet_arm_must_pin_the_component_plan_digest(self):
        with self.assertRaisesRegex(manifest.ManifestError, "pins component_plan_digest"):
            self.check(spec_with({"identity": {}}))

    def test_an_identity_digest_that_is_not_sha256_hex_is_refused(self):
        with self.assertRaisesRegex(manifest.ManifestError, "64 hex"):
            self.check(spec_with({"identity": {"component_plan_digest": "sha256:" + SHA}}))

    def test_a_source_variable_outside_the_buffon_namespace_is_refused(self):
        with self.assertRaisesRegex(manifest.ManifestError, "BUFFON_SOURCE_REPO_"):
            self.check(spec_with({"repo_env": "HOME"}))

    def test_an_unknown_piglet_key_is_refused(self):
        with self.assertRaisesRegex(manifest.ManifestError, "unknown key"):
            self.check(spec_with({"runtime_slot": "bun"}))

    def test_a_held_piglet_arm_may_leave_its_identity_unpinned(self):
        spec = spec_with(held=True)
        del spec["piglet"]["identity"]
        self.check(spec)


class IdentityRefusal(unittest.TestCase):
    pinned = {"name": "bench-lean", "release_version": "0.1.0", **IDENTITY}  # every IDENTITY_KEYS field

    def record(self, **over):
        binary = {"componentPlanDigest": "sha256:" + SHA, "resolutionDigest": "sha256:" + SHA, "graphDigest": "sha256:" + SHA, "resourceClosureDigest": "sha256:" + SHA, "artifact": {"digest": "sha256:" + SHA}}
        binary.update(over)
        return {"kind": "piglet-binary", "piglet": "bench-lean", "releaseVersion": "0.1.0", "binary": binary}

    def test_a_matching_build_is_accepted(self):
        actual = piglet.identity_from_record(self.record())
        self.assertEqual(piglet.check_identity(self.pinned, actual), actual)

    def test_one_drifted_digest_is_refused_and_named(self):
        actual = piglet.identity_from_record(self.record(componentPlanDigest="sha256:" + ZERO))
        with self.assertRaisesRegex(piglet.PigletIdentityError, "component_plan_digest: pinned"):
            piglet.check_identity(self.pinned, actual)

    def test_an_unpinned_digest_that_varies_is_recorded_not_refused(self):
        # Resolution and artifact digests differ between fresh workspaces for one commit (see IDENTITY_KEYS); the pin is component_plan_digest only.
        actual = piglet.identity_from_record(self.record(artifact={"digest": "sha256:" + ZERO}))
        self.assertEqual(piglet.check_identity(self.pinned, actual)["artifact_digest"], ZERO)

    def test_a_record_without_an_artifact_digest_is_refused_not_read_as_empty(self):
        rec = self.record()
        del rec["binary"]["artifact"]
        with self.assertRaises(piglet.PigletIdentityError):
            piglet.identity_from_record(rec)

    def test_the_identity_strips_the_digest_algorithm_prefix(self):
        self.assertEqual(piglet.identity_from_record(self.record())["graph_digest"], SHA)

    def test_the_build_json_result_names_the_record(self):
        self.assertEqual(piglet.record_path_from('{"success": true, "record": "/x/y.record.json"}'), "/x/y.record.json")

    def test_a_build_without_a_record_is_refused(self):
        for bad in ("not json", '{"success": false, "error": "boom"}', '{"success": true}'):
            with self.subTest(bad=bad), self.assertRaises(install.InstallError):
                piglet.record_path_from(bad)


class TargetOfPlatform(unittest.TestCase):
    def test_each_platform_builds_its_own_host_target(self):
        self.assertEqual(piglet.TARGET_OF_PLATFORM["linux-x64"], "linux/amd64")
        self.assertEqual(piglet.TARGET_OF_PLATFORM["darwin-arm64"], "darwin/arm64")

    def test_a_platform_without_a_target_is_an_error_not_a_default(self):
        self.assertNotIn("linux-riscv64", piglet.TARGET_OF_PLATFORM)


class PigpenFixture(unittest.TestCase):
    """A Pigpen clone with one committed manifest, a pig-tip source directory and a fake pig executable."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.pigpen = os.path.join(self.tmp, "pigpen")
        os.makedirs(os.path.join(self.pigpen, "piglets", "bench-lean"))
        with open(os.path.join(self.pigpen, "piglets", "bench-lean", "piglet.yaml"), "w") as f:
            f.write("name: bench-lean\nrelease:\n  version: 0.1.0\nstrip:\n  keep:\n    extensions: []\n")
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q", self.pigpen], check=True)
        subprocess.run(["git", "-C", self.pigpen, "add", "."], check=True)
        subprocess.run(["git", "-C", self.pigpen, "commit", "-q", "-m", "m"], check=True, env=env)
        self.commit = subprocess.run(["git", "-C", self.pigpen, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        self.yaml_sha = manifest.sha256_file(os.path.join(self.pigpen, "piglets", "bench-lean", "piglet.yaml"))
        self.src = os.path.join(self.tmp, "pig-src")
        os.makedirs(os.path.join(self.tmp, "ws", "src", "pig-tip"))
        self.pig = os.path.join(self.tmp, "fake-pig")
        with open(self.pig, "w") as f:
            f.write("#!/bin/sh\necho 'build failed on purpose' >&2\nexit 1\n")
        os.chmod(self.pig, 0o755)
        self.ws = mock.Mock(root=os.path.join(self.tmp, "ws"), runtimes={}, platform="linux-x64")
        self.ws.plain_env = lambda arm: dict(os.environ)
        self.ws.runtime = lambda name: os.path.dirname(self.pig) if name == "go" else ""

    def arm(self, sha=None, commit=None):
        table = piglet_table(pigpen_commit=commit or self.commit, manifest_sha256=sha or self.yaml_sha)
        table["name"] = "bench-lean"
        a = mock.Mock(id="piglet-bench-lean", spec={"piglet": table}, binary=self.pig, install_dir=os.path.join(self.tmp, "inst"), record={}, path_dirs=[])
        a.spec = {"piglet": table}
        return a

    def base(self):
        return mock.Mock(id="pig-tip", spec={"source": {}})


class BuildRefusal(PigpenFixture):
    """A manifest that does not build is refused, and no executable or identity is recorded for it."""

    def test_a_failing_build_is_refused_with_its_output(self):
        staged = mock.patch("buffon.arms.piglet.stage_piglets", side_effect=lambda ws, arm, pigpen, spec: os.path.join(pigpen, spec["manifest"]))
        with mock.patch.dict(os.environ, {"BUFFON_SOURCE_REPO_PIGPEN": self.pigpen}), mock.patch("buffon.arms.piglet.source_dir", return_value=self.src), staged:
            os.makedirs(self.src, exist_ok=True)
            with self.assertRaisesRegex(install.InstallError, "build failed on purpose|failed"):
                piglet.build_piglet(self.ws, self.arm(), self.base())

    def test_a_manifest_whose_bytes_changed_is_refused_before_the_build(self):
        with mock.patch.dict(os.environ, {"BUFFON_SOURCE_REPO_PIGPEN": self.pigpen}), mock.patch("buffon.arms.piglet.source_dir", return_value=self.src):
            os.makedirs(self.src, exist_ok=True)
            with self.assertRaisesRegex(piglet.PigletIdentityError, "refused"):
                piglet.build_piglet(self.ws, self.arm(sha=ZERO), self.base())

    def test_a_checkout_at_another_commit_is_refused(self):
        with mock.patch.dict(os.environ, {"BUFFON_SOURCE_REPO_PIGPEN": self.pigpen}):
            with self.assertRaisesRegex(install.InstallError, "cccc"):
                piglet.pigpen_checkout(self.ws, self.arm(commit="c" * 40), piglet_table(pigpen_commit="c" * 40))

    def test_an_unset_source_variable_is_an_error_naming_the_variable(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(install.InstallError, "BUFFON_SOURCE_REPO_PIGPEN"):
                piglet.pigpen_checkout(self.ws, self.arm(), piglet_table())


class BuildSuccess(PigpenFixture):
    """A build that succeeds: the arm runs the built Piglet Binary, and its record keeps the pinned identity next to the report's view of the Piglet."""

    def fake_pig(self, record):
        rec_path = os.path.join(self.tmp, "fake.record.json")
        with open(rec_path, "w") as f:
            json.dump(record, f)
        self.argv_log = os.path.join(self.tmp, "argv.log")
        with open(self.pig, "w") as f:
            f.write(f"""#!/bin/sh
echo "$@" >> {self.argv_log}
if [ "$2" = build ]; then
  while [ $# -gt 0 ]; do [ "$1" = --out ] && out=$2; shift; done
  printf 'piglet-binary' > "$out"
  printf '{{"success": true, "record": "{rec_path}"}}'
else
  cat {rec_path}
fi
""")
        os.chmod(self.pig, 0o755)

    def build(self, **record_over):
        rec = IdentityRefusal.record(IdentityRefusal())
        rec.update(record_over)
        self.fake_pig(rec)
        arm = self.arm()
        staged = mock.patch("buffon.arms.piglet.stage_piglets", side_effect=lambda ws, arm, pigpen, spec: os.path.join(pigpen, spec["manifest"]))
        with mock.patch.dict(os.environ, {"BUFFON_SOURCE_REPO_PIGPEN": self.pigpen}), mock.patch("buffon.arms.piglet.source_dir", return_value=self.src), staged:
            os.makedirs(self.src, exist_ok=True)
            piglet.build_piglet(self.ws, arm, self.base())
        return arm

    def test_the_built_binary_is_the_arm_and_the_record_keeps_the_identity(self):
        built = self.build()
        out = os.path.join(self.tmp, "inst", "bin", "pig-piglet-bench-lean")
        self.assertEqual(built.binary, out)
        with open(self.argv_log) as f:
            build_argv = f.readline().split()
        self.assertEqual(build_argv[:2], ["piglet", "build"])
        for flag, value in (("--format", "binary"), ("--targets", "linux/amd64"), ("--out", out)):
            self.assertEqual(build_argv[build_argv.index(flag) + 1], value, flag)
        self.assertIn("--json", build_argv)
        pig = built.record["piglet"]
        self.assertEqual((pig["name"], pig["pigpen_commit"], pig["manifest_sha256"], pig["target"]), ("bench-lean", self.commit, self.yaml_sha, "linux/amd64"))
        self.assertEqual(pig["identity"]["component_plan_digest"], SHA)
        self.assertEqual((pig["label"], pig["binary_bytes"]), (piglet.piglet_record.__globals__["PIGLET_LABEL"], len("piglet-binary")))
        self.assertEqual(built.record["piglet_binary_sha256"], manifest.sha256_file(out))

    def test_a_record_of_another_piglet_or_release_is_refused(self):
        for over, field in (({"piglet": "bench-ext10"}, "name"), ({"releaseVersion": "0.2.0"}, "release_version")):
            with self.subTest(field), self.assertRaisesRegex(piglet.PigletIdentityError, field + ": pinned"):
                self.build(**over)

    def test_a_failed_build_result_is_refused_even_with_a_record(self):
        with self.assertRaises(install.InstallError):
            piglet.record_path_from('{"success": false, "record": "/x/y.record.json", "error": "boom"}')


class Staging(unittest.TestCase):
    """The Pigpen staging dependencies come from the commit's own package-lock.json (npm ci), in the workspace's npm cache."""

    def test_staging_installs_the_commits_lock_with_the_workspace_cache(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pigpen = os.path.join(tmp, "pigpen")
        os.makedirs(os.path.join(pigpen, "dist", "staged", "piglets", "bench-lean"))
        open(os.path.join(pigpen, "dist", "staged", "piglets", "bench-lean", "piglet.yaml"), "w").close()
        ws = mock.Mock(root=tmp, npm_cache=None, runtime=lambda name: "/node/bin", base_env=lambda names: {"PATH": "/node/bin:/usr/bin"})
        arm = mock.Mock(id="piglet-bench-lean")
        calls = []
        with mock.patch.object(piglet, "run", lambda argv, cwd=None, env=None, timeout=0: calls.append((argv, env)) or ""):
            with self.assertRaisesRegex(install.InstallError, "no package-lock.json"):
                piglet.stage_piglets(ws, arm, pigpen, piglet_table())
            self.assertEqual(calls, [])
            open(os.path.join(pigpen, "package-lock.json"), "w").close()
            piglet.stage_piglets(ws, arm, pigpen, piglet_table())
        self.assertEqual(calls[0][0], ["/node/bin/npm", "ci", "--ignore-scripts"])
        self.assertEqual(calls[0][1]["npm_config_cache"], os.path.join(tmp, "npm-cache"))
        self.assertEqual(calls[1][0][:2], ["/node/bin/node", os.path.join("scripts", "stage-piglets.mjs")])


class NeutralInheritance(unittest.TestCase):
    """Every Piglet arm runs the same families, inputs and metering as the pig-tip arm it derives from."""

    def test_piglet_arms_inherit_pig_tip_tables(self):
        arms = manifest.load_all()
        base = arms["pig-tip"]
        piglets = [a for a in arms.values() if a.id.startswith("piglet-")]
        self.assertGreaterEqual(len(piglets), 5)
        for a in piglets:
            with self.subTest(arm=a.id):
                if a.held:
                    continue
                self.assertEqual(a.base, "pig-tip")
                for table in ("modes", "endpoint", "env", "renderer", "state"):
                    self.assertEqual(a.spec.get(table), base.spec.get(table), table)
                # capabilities describe what the Binary can do, not the inputs it gets: only pi_extensions may differ (a Piglet that strips the extension runtime)
                strip = lambda c: {k: v for k, v in (c or {}).items() if k != "pi_extensions"}
                self.assertEqual(strip(a.spec.get("capabilities")), strip(base.spec.get("capabilities")))

    def test_a_runnable_piglet_arm_pins_a_full_identity(self):
        for a in manifest.load_all().values():
            if a.id.startswith("piglet-") and not a.held:
                with self.subTest(arm=a.id):
                    self.assertRegex(a.spec["piglet"]["manifest_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(set(a.spec["piglet"]["identity"]), manifest.PIGLET_IDENTITY)



class ReviewCapabilities(unittest.TestCase):
    def test_the_lean_piglet_declares_no_extension_runtime(self):
        # review: bench-lean inherited pig-tip's pi_extensions = "sidecar", so the ext10 workloads ran against a Binary that cannot load extensions
        from buffon.arms import manifest as m
        from buffon.workloads import overhead
        arm = m.load_all()["piglet-bench-lean"]
        self.assertEqual(arm.pi_extensions, "none")
        self.assertNotIn("pi-extensions", arm.claims)
        with self.assertRaises(overhead.Skip):
            overhead.RUNNERS["print-ext10"](overhead.Ctx("/nonexistent", None, type("O", (), {"timeout": 1})), arm)


if __name__ == "__main__":
    unittest.main()
