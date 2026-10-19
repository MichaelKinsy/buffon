# SPDX-License-Identifier: Apache-2.0
"""buffon/backend/bundle.py: what a bundle carries for one architecture, with downloads, npm and go replaced by recorders."""
import os
import tempfile
import types
import unittest
from unittest import mock

from buffon.arms import install
from buffon.backend import bundle


class FakeWorkspace:
    def __init__(self, cache, **_):
        self.cache = cache

    def __enter__(self):
        # The real Workspace downloads this machine's Node and Go into its cache: host programs that must not reach the bundle.
        os.makedirs(self.cache.dir, exist_ok=True)
        with open(os.path.join(self.cache.dir, "host-go.tar.gz"), "w") as f:
            f.write("host")
        return self

    def __exit__(self, *_):
        pass

    def base_env(self, runtime_names=()):
        return {"PATH": "/usr/bin", "RUNTIMES": ",".join(runtime_names)}


class BuildTests(unittest.TestCase):
    def setUp(self):
        saved = os.environ.pop("BUFFON_SOURCE_REPO_PIG_TIP", None)
        if saved is not None:
            self.addCleanup(os.environ.__setitem__, "BUFFON_SOURCE_REPO_PIG_TIP", saved)

    def build(self, arch, arms, source_repos=None, checkout=None):
        out = os.path.join(tempfile.mkdtemp(), "bundle")
        gets, runs = [], []

        def get(cache, url, sha256):
            gets.append((url, sha256, cache.dir))
            path = cache.path(sha256, url)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(url)
            return path

        def run(argv, cwd=None, env=None, timeout=0):
            runs.append((argv, cwd, env))
            if argv[:2] == ["npm", "ci"]:
                self.assertTrue(os.path.exists(os.path.join(cwd, "package-lock.json")))
                os.makedirs(env["npm_config_cache"], exist_ok=True)
                with open(os.path.join(env["npm_config_cache"], "index"), "w") as f:
                    f.write("npm")
                os.makedirs(os.path.join(env["npm_config_cache"], "_logs"), exist_ok=True)   # what npm leaves: a debug log naming the builder's home
                with open(os.path.join(env["npm_config_cache"], "_logs", "debug-0.log"), "w") as f:
                    f.write("verbose logfile <builder home>/.npmrc")
            if argv[:2] == ["go", "build"]:
                with open(argv[argv.index("-o") + 1], "w") as f:
                    f.write("elf " + env.get("GOARCH", ""))
            if argv[:2] == ["git", "rev-parse"]:
                return (checkout or {}).get(argv[2], "")
            return ""

        with mock.patch.object(install.Cache, "get", get), mock.patch.object(install, "run", run), mock.patch.object(install, "Workspace", FakeWorkspace):
            summary = bundle.build(out, arch, arms, allow_dirty=True, source_repos=source_repos)
        return out, summary, gets, runs

    def test_an_arm64_bundle_carries_only_linux_arm64_artifacts_and_runtimes(self):
        out, summary, gets, runs = self.build("arm64", ["pig-0.4.1", "pi-node", "pig-tip", "claude-code"])
        self.assertEqual(summary["platform"], "linux-arm64")
        self.assertEqual(summary["arms"], ["pi-node", "pig-0.4.1"])
        self.assertIn("no source repository: set BUFFON_SOURCE_REPO_PIG_TIP", summary["skipped"]["pig-tip"])
        self.assertTrue(summary["skipped"]["claude-code"].startswith("operator terms"))   # installed from the vendor by the operator who accepts its terms, never bundled
        urls = [u for u, _, _ in gets]
        self.assertTrue(urls and all("arm64" in u for u in urls), urls)
        self.assertTrue(any("node-v" in u for u in urls), "the npm arm's Node runtime is in the bundle")
        npm = [r for r in runs if r[0][0] == "npm"]
        self.assertEqual(len(npm), 1)
        self.assertEqual((npm[0][2]["npm_config_os"], npm[0][2]["npm_config_cpu"], npm[0][2]["npm_config_cache"]), ("linux", "arm64", os.path.join(out, "npm-cache")))
        go = [r for r in runs if r[0][0] == "go"][0]
        self.assertEqual((go[2]["GOOS"], go[2]["GOARCH"], go[2]["CGO_ENABLED"], go[1]), ("linux", "arm64", "0", os.path.join(out, "cluster")))
        with open(os.path.join(out, "ARTIFACTS.sha256")) as f:
            listed = [line.split("  ", 1)[1] for line in f.read().splitlines()]
        self.assertEqual(listed, sorted(listed))
        for rel in ("bin/buffon-cluster", "buffon/cli.py", "npm-cache/index"):
            self.assertIn(rel, listed)
        # review: npm's debug log (the builder's home and paths) shipped in the ticket 1 bundle
        self.assertFalse(any("/_logs/" in r for r in listed))
        self.assertFalse(os.path.exists(os.path.join(out, "npm-cache", "_logs")))
        self.assertTrue(any(r.startswith("cache/") for r in listed))
        self.assertFalse(any(r.startswith(".host-cache") for r in listed))
        self.assertFalse(os.path.exists(os.path.join(out, ".host-cache")), "this machine's runtimes stay out of the bundle")

    def test_an_amd64_bundle_names_x64(self):
        _, summary, gets, _ = self.build("amd64", ["pig-0.4.1"])
        self.assertEqual(summary["platform"], "linux-x64")
        # PiG's Node sidecar runtime ([runtime] in its arm.toml) comes along.
        self.assertEqual([u.rsplit("/", 1)[1] for u, _, _ in gets], ["pig-0.4.1-linux-amd64.tar.gz", "node-v24.19.0-linux-x64.tar.xz"])

    def test_a_go_source_arm_is_cross_built_from_its_pinned_commit_into_the_cache(self):
        from buffon.arms import manifest
        pinned = manifest.load_arm("pig-tip").spec["source"]
        out, summary, gets, runs = self.build("arm64", ["pig-tip"], {"pig-tip": "/clones/pig"}, {"HEAD": pinned["commit"], "HEAD^{tree}": pinned["tree"]})
        self.assertEqual(summary["arms"], ["pig-tip"])
        self.assertEqual(summary["skipped"], {})
        git = [r[0] for r in runs if r[0][0] == "git"]
        self.assertEqual(git[0][:4], ["git", "clone", "--quiet", "--no-checkout"])
        self.assertEqual(git[0][4], "/clones/pig")
        self.assertEqual(git[1], ["git", "checkout", "--quiet", "--detach", pinned["commit"]])
        builds = [r for r in runs if r[0][:2] == ["go", "build"]]
        self.assertEqual(len(builds), 2, "the arm and buffon-cluster")
        argv, cwd, env = builds[0]
        where = install.prebuilt_dir(os.path.join(out, "cache"), "pig-tip", pinned["commit"], "linux-arm64")
        self.assertEqual(argv[argv.index("-o") + 1], os.path.join(where, "pig"))
        self.assertEqual((env["GOOS"], env["GOARCH"], env["CGO_ENABLED"], env["GOTOOLCHAIN"], env["RUNTIMES"]), ("linux", "arm64", "0", "local", "go"))
        self.assertEqual(argv[-1], "./cmd/pig")
        self.assertNotEqual(cwd, os.path.join(out, "cluster"))
        with open(os.path.join(where, install.PREBUILT_RECORD)) as f:
            rec = __import__("json").load(f)
        self.assertEqual((rec["arm"], rec["commit"], rec["tree"], rec["platform"], rec["binary"], rec["build"]), ("pig-tip", pinned["commit"], pinned["tree"], "linux-arm64", "pig", pinned["build"]))
        self.assertEqual(rec["sha256"], manifest.sha256_file(os.path.join(where, "pig")))
        with open(os.path.join(out, "ARTIFACTS.sha256")) as f:
            listed = [line.split("  ", 1)[1] for line in f.read().splitlines()]
        rel = os.path.relpath(where, out)
        self.assertIn(rel + "/pig", listed)
        self.assertIn(rel + "/record.json", listed)
        self.assertIn("bundle.json", listed)
        # PiG's Node sidecar runtime comes along for the source arm too.
        self.assertTrue(any("node-v" in u for u, _, _ in gets))

    def test_a_checkout_that_is_not_the_pinned_commit_refuses_the_bundle(self):
        with self.assertRaisesRegex(bundle.BundleError, "the manifest pins"):
            self.build("amd64", ["pig-tip"], {"pig-tip": "/clones/pig"}, {"HEAD": "0" * 40, "HEAD^{tree}": "1" * 40})

    def test_a_source_arm_that_is_not_cgo_free_go_and_a_derived_arm_are_skipped(self):
        src = {"source": {"repo_env": "X_REPO", "commit": "c" * 40, "toolchain": "rust", "package": ".", "build": ["cargo"], "env": {}}}
        cgo = {"source": {"repo_env": "X_REPO", "commit": "c" * 40, "toolchain": "go", "package": ".", "build": ["go", "build"], "env": {"CGO_ENABLED": "1"}}}
        with self.fake_arms({"r": ("source", src), "c": ("source", cgo), "d": ("derive", {"derive": {"base": "r"}})}, {}):
            _, summary, _, runs = self.build("amd64", ["r", "c", "d"], {"r": "/x", "c": "/x"})
        self.assertEqual(summary["arms"], [])
        self.assertIn("a bundle cross-builds only Go with CGO_ENABLED=0", summary["skipped"]["r"])
        self.assertIn("CGO_ENABLED=1", summary["skipped"]["c"])
        self.assertIn("prepares from the base's source checkout", summary["skipped"]["d"])
        self.assertFalse([r for r in runs if r[0][0] == "git"])

    def test_bundle_json_names_the_checkout_and_the_arms(self):
        out, summary, _, _ = self.build("amd64", ["pig-0.4.1"])
        meta = bundle.read_meta(out)
        self.assertEqual(meta["arms"], ["pig-0.4.1"])
        self.assertEqual(meta["arch"], "amd64")
        self.assertRegex(meta["commit"], "^[0-9a-f]{40}$")
        self.assertRegex(meta["tree"], "^[0-9a-f]{40}$")
        self.assertEqual({k: summary[k] for k in meta}, meta)
        os.unlink(os.path.join(out, "ARTIFACTS.sha256"))
        with self.assertRaisesRegex(bundle.BundleError, "not a finished bundle"):
            bundle.read_meta(out)
        with self.assertRaisesRegex(bundle.BundleError, "is not a bundle"):
            bundle.read_meta(tempfile.mkdtemp())

    def test_refusals(self):
        with self.assertRaisesRegex(bundle.BundleError, "arch 'x86'"):
            bundle.build(tempfile.mkdtemp(), "x86")
        full = tempfile.mkdtemp()
        open(os.path.join(full, "x"), "w").close()
        with self.assertRaisesRegex(bundle.BundleError, "is not empty"):
            bundle.build(full, "amd64")
        with self.assertRaisesRegex(bundle.BundleError, "unknown arms: nope"):
            bundle.build(tempfile.mkdtemp(), "amd64", ["nope"])

    def fake_arms(self, arms, runtimes):
        """Patch the manifests: arms maps an id to (install kind, spec); runtimes is load_runtimes()'s value."""
        loaded = {i: types.SimpleNamespace(id=i, held=None, install_kind=kind, spec=spec, dir="/arms/" + i, base=spec.get("derive", {}).get("base")) for i, (kind, spec) in arms.items()}
        return mock.patch.multiple(bundle.manifest, load_all=lambda _dir: loaded, load_runtimes=lambda: runtimes)

    def test_an_arm_without_an_artifact_for_the_platform_is_skipped(self):
        art = {"linux-x64": {"url": "https://example.invalid/a-linux-x64.tar.gz", "sha256": "0" * 64}}
        with self.fake_arms({"a": ("artifact", {"artifact": art})}, {}):
            _, summary, gets, _ = self.build("arm64", ["a"])
        self.assertEqual((summary["arms"], gets), ([], []))
        self.assertIn("no pinned artifact for linux-arm64", summary["skipped"]["a"])

    def test_a_runtime_without_an_artifact_for_the_platform_is_refused(self):
        npm = {"npm": {"runtime": "node", "package": "p", "version": "1.0.0", "package_lock": "package-lock.json", "package_lock_sha256": "0" * 64}}
        runtimes = {"node": {"artifact": {"linux-x64": {"url": "https://example.invalid/node-linux-x64.tar.xz", "sha256": "0" * 64}}}}
        with self.fake_arms({"a": ("npm", npm)}, runtimes), self.assertRaisesRegex(bundle.BundleError, "runtime node has no pinned artifact for linux-arm64"):
            self.build("arm64", ["a"])

    def test_an_npm_lock_that_differs_from_the_manifest_is_refused(self):
        arm_dir, dest = tempfile.mkdtemp(), tempfile.mkdtemp()
        with open(os.path.join(arm_dir, "package-lock.json"), "w") as f:
            f.write("{}")
        arm = types.SimpleNamespace(id="a", dir=arm_dir, spec={"npm": {"package_lock": "package-lock.json", "package_lock_sha256": "0" * 64, "package": "p", "version": "1.0.0"}})
        with self.assertRaisesRegex(bundle.BundleError, "differs from the manifest's sha256"):
            bundle.npm_project(arm, dest)
        self.assertFalse(os.path.exists(os.path.join(dest, "package-lock.json")))

    def test_the_sums_list_regular_files_only(self):
        out = tempfile.mkdtemp()
        os.makedirs(os.path.join(out, "bin"))
        with open(os.path.join(out, "bin", "tool"), "w") as f:
            f.write("x")
        os.symlink("tool", os.path.join(out, "bin", "link"))
        self.assertEqual(bundle.write_sums(out), 1)
        with open(os.path.join(out, "ARTIFACTS.sha256")) as f:
            self.assertEqual([line.split("  ", 1)[1] for line in f.read().splitlines()], ["bin/tool"])

    def test_a_modified_tracked_file_is_refused(self):
        def runner(argv, **_):
            return mock.Mock(stdout=" M buffon/cli.py\\n")
        with self.assertRaisesRegex(bundle.BundleError, "modified tracked files"):
            bundle.tracked_files("/repo", runner=runner)



class RunnerCheckout(unittest.TestCase):
    """A session that runs from a bundle has no .git: the runner's commit and tree come from bundle.json, and the checkout's files are checked against ARTIFACTS.sha256."""

    def bundle_dir(self, meta=None):
        import json
        root = tempfile.mkdtemp()
        for rel, body in (("buffon/cli.py", "code"), ("README.md", "doc"), ("cache/x/a.tar.gz", "artifact"), ("npm-cache/i", "npm"), ("bin/buffon-cluster", "elf")):
            os.makedirs(os.path.dirname(os.path.join(root, rel)) or root, exist_ok=True)
            with open(os.path.join(root, rel), "w") as f:
                f.write(body)
        with open(os.path.join(root, "bundle.json"), "w") as f:
            json.dump({"commit": "c" * 40, "tree": "t" * 40, "arch": "amd64", "arms": [], "dirty": False, "diff_sha256": None, **(meta or {})}, f)
        bundle.write_sums(root)
        return root

    def test_a_bundle_built_from_a_dirty_checkout_is_dirty_in_the_pod(self):
        """bundle.json names HEAD, but an allow_dirty bundle carries the working tree's files, which ARTIFACTS.sha256 then lists: the pod cannot see the
        difference itself, so the bundle must say so, and a bundle.json that does not say it was clean is dirty."""
        from buffon.runner import facts
        got = facts.runner_checkout(self.bundle_dir({"dirty": True, "diff_sha256": "d" * 64}))
        self.assertEqual((got["runner_commit"], got["runner_dirty"], got["runner_diff_sha256"]), ("c" * 40, True, "d" * 64))
        import json
        root = self.bundle_dir()
        with open(os.path.join(root, "bundle.json")) as f:
            meta = json.load(f)
        del meta["dirty"]
        with open(os.path.join(root, "bundle.json"), "w") as f:
            json.dump(meta, f)
        bundle.write_sums(root)
        self.assertTrue(facts.runner_checkout(root)["runner_dirty"])

    def test_build_records_whether_the_checkout_was_dirty(self):
        import hashlib
        import subprocess as sp

        def runner(dirty):
            def run(argv, **kw):
                if argv[3:5] == ["rev-parse", "HEAD"]:
                    out = "c" * 40
                elif argv[3:] == ["rev-parse", "HEAD^{tree}"]:
                    out = "t" * 40
                elif argv[3] == "status":
                    out = " M buffon/cli.py\n" if dirty else ""
                elif argv[3] == "diff":
                    return sp.CompletedProcess(argv, 0, stdout=b"the diff")
                elif argv[3] == "ls-files":
                    out = ""
                else:
                    raise AssertionError(argv)
                return sp.CompletedProcess(argv, 0, stdout=out)
            return run
        with mock.patch.object(install, "Workspace", FakeWorkspace), mock.patch.object(install, "run", lambda *a, **k: ""):
            dirty = bundle.build(os.path.join(tempfile.mkdtemp(), "b"), "amd64", [], allow_dirty=True, runner=runner(True))
            clean = bundle.build(os.path.join(tempfile.mkdtemp(), "b"), "amd64", [], allow_dirty=True, runner=runner(False))
        self.assertEqual((dirty["dirty"], dirty["diff_sha256"]), (True, hashlib.sha256(b"the diff").hexdigest()))
        self.assertEqual((clean["dirty"], clean["diff_sha256"]), (False, None))

    def test_a_bundle_checkout_takes_the_commit_and_tree_from_bundle_json(self):
        from buffon.arms import manifest
        from buffon.runner import engine, facts
        root = self.bundle_dir()
        got = facts.runner_checkout(root)
        self.assertEqual((got["runner_commit"], got["runner_tree"], got["runner_dirty"]), ("c" * 40, "t" * 40, False))
        self.assertEqual(got["runner_bundle_sha256"], manifest.sha256_file(os.path.join(root, "ARTIFACTS.sha256")))
        self.assertEqual(engine.runner_record(got), {"commit": "c" * 40, "tree": "t" * 40, "dirty": False, "diff_sha256": None, "bundle_sha256": got["runner_bundle_sha256"]})
        # The payload (cache, npm cache, programs) is checked by the installer and buffon-cluster, not as the runner's files.
        with open(os.path.join(root, "cache/x/a.tar.gz"), "w") as f:
            f.write("other")
        self.assertFalse(facts.runner_checkout(root)["runner_dirty"])

    def test_a_changed_or_missing_file_makes_the_bundle_checkout_dirty(self):
        from buffon.runner import facts
        root = self.bundle_dir()
        with open(os.path.join(root, "buffon/cli.py"), "a") as f:
            f.write("patched")
        got = facts.runner_checkout(root)
        self.assertTrue(got["runner_dirty"])
        self.assertEqual(got["runner_differs"], ["buffon/cli.py"])
        os.unlink(os.path.join(root, "README.md"))
        self.assertEqual(facts.runner_checkout(root)["runner_differs"], ["README.md", "buffon/cli.py"])
        os.unlink(os.path.join(root, "ARTIFACTS.sha256"))
        got = facts.runner_checkout(root)
        self.assertEqual((got["runner_commit"], got["runner_dirty"]), (None, True))

    def test_a_git_checkout_is_read_with_git(self):
        from buffon.arms import manifest
        from buffon.runner import engine, facts
        got = facts.runner_checkout(manifest.ROOT)
        self.assertRegex(got["runner_commit"], "^[0-9a-f]{40}$")
        self.assertNotIn("runner_bundle_sha256", got)
        self.assertNotIn("bundle_sha256", engine.runner_record(got))


if __name__ == "__main__":
    unittest.main()


def session_arms(argv):
    """The arm ids of the session's --arms flag; the flag appears at most once."""
    if "--arms" not in argv:
        return None
    assert argv.count("--arms") == 1, argv
    rest = argv[argv.index("--arms") + 1:]
    return [a for a in rest[:next((i for i, a in enumerate(rest) if a.startswith("--")), len(rest))]]


class RunBuildsTheBundle(unittest.TestCase):
    """`buffon run` on a bundle-mode Kubernetes site builds the bundle for the site's architecture, hands it to the backend, and removes it afterwards."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)

    def site(self, bundle_mode=True):
        path = os.path.join(self.tmp, "site.toml")
        with open(path, "w") as f:
            f.write(f'[site]\nbackend = "kubernetes"\n[local]\ncache_dir = "{self.tmp}/host-cache"\n[kubernetes]\nnamespace = "n"\narch = "arm64"\n')
            f.write(f'bundle = true\nbase_image = "python@sha256:{"a" * 64}"\n' if bundle_mode else f'image = "reg.example/buffon@sha256:{"a" * 64}"\n')
        return path

    def run_cli(self, argv, summary=None, error=None, run_error=None):
        from buffon import backend, cli
        builds, sessions = [], []

        def build(out_dir, arch, arm_ids=None, host_cache="", **_):
            builds.append({"out": out_dir, "arch": arch, "arms": arm_ids, "host_cache": host_cache, "empty": not os.listdir(out_dir)})
            if error:
                raise error
            with open(os.path.join(out_dir, "ARTIFACTS.sha256"), "w") as f:
                f.write("")
            return summary

        class FakeBackend:
            def check(self, isolation="none"):
                pass

            def run(self, session):
                sessions.append({"argv": session.argv, "bundle": session.bundle, "present": bool(session.bundle) and os.path.exists(os.path.join(session.bundle, "ARTIFACTS.sha256"))})
                if run_error:
                    raise run_error
                return backend.SessionResult(run_dir=session.run_dir, facts={}, pinned_cpus=[], throttled_usec=0, exit_code=0)

        with mock.patch.object(bundle, "build", build), mock.patch.object(backend, "get_backend", lambda s: FakeBackend()), mock.patch("sys.stderr"), mock.patch("sys.stdout"):
            code = cli.main(["run", "--site", self.site(summary is not False), "--out", os.path.join(self.tmp, "out"), *argv])
        return code, builds, sessions

    def test_the_session_runs_the_arms_the_bundle_carries_from_the_bundle(self):
        from buffon import cli
        from buffon.arms import manifest
        code, builds, sessions = self.run_cli([], summary={"arms": ["pi-node"], "skipped": {"pig-tip": "built from source (source)"}})
        self.assertEqual(code, 0)
        arms = manifest.load_all()
        self.assertEqual(builds[0]["arms"], [n for n in cli.session_arms(None, arms) if not arms[n].held])
        self.assertEqual((builds[0]["arch"], builds[0]["host_cache"], builds[0]["empty"]), ("arm64", os.path.join(self.tmp, "host-cache"), True))
        self.assertEqual(sessions[0]["bundle"], builds[0]["out"])
        self.assertTrue(sessions[0]["present"], "the bundle exists while the backend runs the session")
        self.assertEqual(session_arms(sessions[0]["argv"]), ["pi-node"])
        self.assertFalse(os.path.exists(builds[0]["out"]), "the bundle is removed after the session")

    def test_named_arms_are_kept_and_one_the_bundle_cannot_carry_is_refused(self):
        code, builds, sessions = self.run_cli(["--arms", "pi-node", "pig-0.4.1"], summary={"arms": ["pi-node", "pig-0.4.1"], "skipped": {}})
        self.assertEqual(code, 0)
        self.assertEqual(builds[0]["arms"], ["pi-node", "pig-0.4.1"])
        self.assertEqual(session_arms(sessions[0]["argv"]), ["pi-node", "pig-0.4.1"])
        # A named held arm is never run (the session says so), so the bundle does not carry it.
        code, builds, sessions = self.run_cli(["--arms", "pi-node", "pi-agent-rust"], summary={"arms": ["pi-node"], "skipped": {}})
        self.assertEqual((code, builds[0]["arms"]), (0, ["pi-node"]))
        code, builds, sessions = self.run_cli(["--arms", "pi-node", "pig-tip"], summary={"arms": ["pi-node"], "skipped": {"pig-tip": "built from source (source)"}})
        self.assertEqual((code, sessions), (2, []))
        self.assertFalse(os.path.exists(builds[0]["out"]))

    def test_a_bundle_with_no_arm_or_a_failed_build_runs_nothing_and_leaves_nothing(self):
        code, builds, sessions = self.run_cli([], summary={"arms": [], "skipped": {"pig-tip": "built from source (source)"}})
        self.assertEqual((code, sessions), (2, []))
        self.assertFalse(os.path.exists(builds[0]["out"]))
        code, builds, sessions = self.run_cli([], error=bundle.BundleError("/repo has modified tracked files"))
        self.assertEqual((code, sessions), (2, []))
        self.assertFalse(os.path.exists(builds[0]["out"]))

    def test_the_bundle_is_removed_when_the_backend_fails(self):
        from buffon.backend import BackendError
        code, builds, sessions = self.run_cli([], summary={"arms": ["pi-node"], "skipped": {}}, run_error=BackendError("pod failed"))
        self.assertEqual(code, 2)
        self.assertTrue(sessions[0]["present"])
        self.assertFalse(os.path.exists(builds[0]["out"]))

    def prebuilt(self, arch="arm64", arms=("pi-node", "pig-tip"), finished=True):
        import json
        d = tempfile.mkdtemp(dir=self.tmp)
        with open(os.path.join(d, "bundle.json"), "w") as f:
            json.dump({"arch": arch, "arms": list(arms), "skipped": {"rpi": "no pinned artifact for linux-arm64"}, "commit": "c" * 40, "tree": "t" * 40}, f)
        if finished:
            bundle.write_sums(d)
        return d

    def test_a_prebuilt_bundle_is_used_as_it_is_and_kept(self):
        d = self.prebuilt()
        code, builds, sessions = self.run_cli(["--bundle", d], summary={"arms": [], "skipped": {}})
        self.assertEqual((code, builds), (0, []))
        self.assertEqual(sessions[0]["bundle"], d)
        self.assertEqual(session_arms(sessions[0]["argv"]), ["pi-node", "pig-tip"], "no named arm: the session runs what the bundle carries")
        self.assertTrue(os.path.exists(os.path.join(d, "ARTIFACTS.sha256")), "a bundle given with --bundle is kept")
        code, _, sessions = self.run_cli(["--bundle", d, "--arms", "pig-tip"], summary={"arms": [], "skipped": {}})
        self.assertEqual((code, session_arms(sessions[0]["argv"])), (0, ["pig-tip"]))

    def test_a_prebuilt_bundle_that_does_not_fit_is_refused_before_any_pod(self):
        for name, path, argv, summary in (("arch", self.prebuilt(arch="amd64"), [], {"arms": [], "skipped": {}}),
                                          ("unfinished", self.prebuilt(finished=False), [], {"arms": [], "skipped": {}}),
                                          ("missing arm", self.prebuilt(), ["--arms", "rpi"], {"arms": [], "skipped": {}}),
                                          ("image site", self.prebuilt(), [], False)):
            with self.subTest(name):
                code, builds, sessions = self.run_cli(["--bundle", path, *argv], summary=summary)
                self.assertEqual((code, builds, sessions), (2, [], []))
                self.assertTrue(os.path.exists(os.path.join(path, "bundle.json")))

    def test_an_image_site_builds_no_bundle(self):
        code, builds, sessions = self.run_cli([], summary=False)
        self.assertEqual((code, builds), (0, []))
        self.assertIsNone(sessions[0]["bundle"])
        self.assertIsNone(session_arms(sessions[0]["argv"]))
