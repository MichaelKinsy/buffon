# SPDX-License-Identifier: Apache-2.0
import gzip
import hashlib
import os
import shutil
import tempfile
import unittest

from buffon.arms import install, lock, manifest

ROOT = manifest.ROOT
V0_ARMS = {"pi-node", "octet", "pi-bun", "pig-0.4.1", "pig-tip", "pibolt", "pi-bolt-0.8.5", "omp", "omt", "rpi", "codex", "opencode", "opencode-v2", "nowa-gi", "guanshan-pi-go", "sky-valley-pi", "pulseaiclub-phi", "rcarmo-gi"}
MATRIX_ARMS = {"pig-ts-node", "pig-ts-bun", "pig-ts-aot", "pig-go-packed", "pig-go-isolated", "pig-go-fused", "pig-ts-node-isolated-diag", "pig-standard", "pig-strip-min", "piglet-bench-lean", "piglet-bench-ext10", "piglet-bench-ext10-split", "piglet-bench-ext10-aot", "piglet-combined"}   # extension-matrix arms (tests/test_matrix.py) and Piglet arms (tests/test_piglet_arms.py): run only when named
DURABLE_ARMS = {"pi-durable", "pig-durable", "pi-durable-main"}   # adapter arms (tests/test_durable_adapters.py): the durable workloads select them, no CLI modes
HELD = {"pi-agent-rust"}
OPERATOR_TERMS = {"copilot", "claude-code"}   # installed from the vendor at run time; run only when named and accepted (tests/test_up.py)


class Manifests(unittest.TestCase):
    def test_every_v0_arm_is_present_and_the_held_arms_are_held(self):
        arms = manifest.load_all()
        self.assertEqual(V0_ARMS | HELD | OPERATOR_TERMS | MATRIX_ARMS | DURABLE_ARMS, set(arms))
        self.assertTrue(all(arms[n].held for n in HELD))
        self.assertFalse(any(arms[n].held for n in V0_ARMS | OPERATOR_TERMS))
        self.assertTrue(all(arms[n].operator_terms and not arms[n].runs_by_default for n in OPERATOR_TERMS))
        self.assertFalse(any(arms[n].operator_terms for n in V0_ARMS | MATRIX_ARMS | HELD))

    def test_every_runnable_arm_pins_a_version_check_and_an_endpoint_writer(self):
        for name, arm in manifest.load_all().items():
            if arm.held:
                continue
            self.assertIn("version", arm.modes, name)
            if arm.adapter:   # an adapter arm speaks its own protocol: no wire API, no config writer
                self.assertFalse(arm.runs_by_default, name)
                continue
            self.assertTrue(os.path.exists(arm.writer_path()), name)
            self.assertTrue(arm.apis, name)

    def test_artifacts_are_https_with_sha256_and_a_published_checksum_source(self):
        for name, arm in manifest.load_all().items():
            for plat, a in arm.spec.get("artifact", {}).items():
                self.assertRegex(a["sha256"], r"^[0-9a-f]{64}$", f"{name} {plat}")
                self.assertTrue(a["url"].startswith("https://"))
                if name != "opencode":  # trust-on-first-use arms say so in `trust`
                    self.assertTrue(a.get("checksums"), f"{name} {plat} names no checksum file")

    def test_source_arm_pins_a_full_commit_and_names_no_repository(self):
        s = manifest.load_all()["pig-tip"].spec["source"]
        self.assertRegex(s["commit"], r"^[0-9a-f]{40}$")
        self.assertNotIn("repo", s)
        self.assertTrue(s["repo_env"].startswith("BUFFON_SOURCE_REPO_"))

    def _bad(self, edit, message):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(os.path.join(manifest.ARMS_DIR, "pig-0.4.1"), os.path.join(d, "pig-0.4.1"))
            path = os.path.join(d, "pig-0.4.1", "arm.toml")
            with open(path) as f:
                text = f.read()
            with open(path, "w") as f:
                f.write(edit(text))
            with self.assertRaisesRegex(manifest.ManifestError, message):
                manifest.load_arm("pig-0.4.1", d)

    def test_an_arm_name_may_not_look_like_an_aa_copy(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(os.path.join(manifest.ARMS_DIR, "pig-0.4.1"), os.path.join(d, "pig-b"))
            path = os.path.join(d, "pig-b", "arm.toml")
            with open(path) as f:
                text = f.read()
            with open(path, "w") as f:
                f.write(text.replace('name = "pig-0.4.1"', 'name = "pig-b"', 1))
            with self.assertRaisesRegex(manifest.ManifestError, "may not end in -b"):
                manifest.load_arm("pig-b", d)

    def test_strict_validation(self):
        self._bad(lambda t: "bogus = 1\n" + t, "unknown key")
        self._bad(lambda t: t.replace('relation = "pi-port"', 'relation = "friend"'), "relation")
        self._bad(lambda t: t.replace('sha256 = "3b4de3587cbfb617def483ec62dddcf35827acc3436b1454cc5694c22dcdaf3f"', 'sha256 = "abc"'), "64 hex")
        self._bad(lambda t: t.replace('name = "pig-0.4.1"', 'name = "other"', 1), "must equal the directory name")
        self._bad(lambda t: t.replace("version = [", "versionx = [", 1), "unknown mode")
        self._bad(lambda t: t.replace('url = "https://github.com/MichaelKinsy/PiG/releases/download/v0.4.1/pig-0.4.1-linux-amd64.tar.gz"', 'url = "http://x/y.tar.gz"'), "https")
        self._bad(lambda t: 'operator_terms = "  "\n' + t, "operator_terms")
        self._bad(lambda t: 'operator_terms = 3\n' + t, "operator_terms")
        self._bad(lambda t: 'operator_terms = "terms"\nheld = "x"\n' + t, "not both")


class Lock(unittest.TestCase):
    def test_committed_lock_equals_generated(self):
        self.assertEqual(lock.check(), [])

    def test_generation_is_deterministic_and_covers_every_arm(self):
        a, b = lock.dumps(lock.generate()), lock.dumps(lock.generate())
        self.assertEqual(a, b)
        data = lock.generate()
        self.assertEqual(set(data["arms"]), V0_ARMS | HELD | OPERATOR_TERMS | MATRIX_ARMS | DURABLE_ARMS)
        self.assertIn("node", data["runtimes"])

    def test_a_changed_manifest_changes_the_lock(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(manifest.ARMS_DIR, os.path.join(d, "arms"))
            before = lock.dumps(lock.generate(arms_dir=os.path.join(d, "arms")))
            path = os.path.join(d, "arms", "omp", "arm.toml")
            with open(path, "a") as f:
                f.write("\n# edited\n")
            self.assertNotEqual(before, lock.dumps(lock.generate(arms_dir=os.path.join(d, "arms"))))


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, "artifact.bin")
        with open(self.src, "wb") as f:
            f.write(b"payload")
        self.sha = hashlib.sha256(b"payload").hexdigest()
        self.url = "file://" + self.src

    def test_download_is_verified_and_cached(self):
        cache = install.Cache(os.path.join(self.tmp, "c"))
        path = cache.get(self.url, self.sha)
        self.assertEqual(open(path, "rb").read(), b"payload")
        os.unlink(self.src)  # a second get is served from the cache without the source
        self.assertEqual(cache.get(self.url, self.sha), path)

    def test_wrong_hash_is_refused_and_leaves_nothing_behind(self):
        cache = install.Cache(os.path.join(self.tmp, "c"))
        with self.assertRaisesRegex(install.InstallError, "does not match"):
            cache.get(self.url, "0" * 64)
        self.assertFalse(os.path.exists(cache.path("0" * 64, self.url)))

    def test_a_damaged_cache_entry_is_never_used(self):
        cache = install.Cache(os.path.join(self.tmp, "c"))
        path = cache.get(self.url, self.sha)
        with open(path, "wb") as f:
            f.write(b"tampered")
        self.assertEqual(open(cache.get(self.url, self.sha), "rb").read(), b"payload")

    def test_offline_never_downloads(self):
        with self.assertRaisesRegex(install.InstallError, "offline cache"):
            install.Cache(os.path.join(self.tmp, "c"), offline=True).get(self.url, self.sha)


class OctetWriter(unittest.TestCase):
    def test_the_registry_points_at_the_mock_owner_only_with_a_saved_theme(self):
        import json
        import stat
        from buffon.arms.writers import WriteSpec
        from buffon.arms.writers.octet import write
        with tempfile.TemporaryDirectory() as home:
            spec = WriteSpec(arm=None, home=home, agent_dir=home, cwd=home, base_url="http://127.0.0.1:4242/v1", origin="http://127.0.0.1:4242")
            self.assertEqual(write(spec), {})
            path = os.path.join(home, ".octet", "credentials", "custom.json")
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)   # Octet refuses a registry other users can read
            provider = json.load(open(path))["providers"]["bench"]
            self.assertEqual(provider["base_url"], "http://127.0.0.1:4242/v1/")
            self.assertEqual(provider["auth"], {"kind": "none"})
            self.assertFalse(provider["auto_discover"])   # no GET /models at start-up
            self.assertEqual([m["api_name"] for m in provider["models"]], [spec.model])
            self.assertIn('theme = "', open(os.path.join(home, ".octet", "config.toml")).read())   # without it the first TUI start waits on a picker


class CodexWriteCatalog(unittest.TestCase):
    def test_the_large_write_mode_loads_a_catalog_that_gives_the_mock_model_apply_patch_and_no_other_mode_does(self):
        import json
        from buffon.arms.writers import WriteSpec
        from buffon.arms.writers.codex import write
        arm = manifest.load_all()["codex"]
        self.assertFalse(any("model_catalog_json" in part for part in arm.modes["print"]))
        self.assertIn('model_catalog_json="{home}/.codex/write-catalog.json"', arm.modes["print_write"])
        with tempfile.TemporaryDirectory() as home:
            write(WriteSpec(arm=arm, home=home, agent_dir=home, cwd=home, base_url="http://127.0.0.1:4242/v1", origin="http://127.0.0.1:4242"))
            self.assertNotIn("model_catalog_json", open(os.path.join(home, ".codex", "config.toml")).read())
            (entry,) = json.load(open(os.path.join(home, ".codex", "write-catalog.json")))["models"]
            self.assertEqual((entry["slug"], entry["apply_patch_tool_type"]), ("bench-1", "freeform"))
            # The entry's instructions are the ones Codex 0.162.1 sends on every other workload: the first developer message of a published print request.
            sample = os.path.join(manifest.ROOT, "results", "2026-10-19-smc1-launch-core", "mock-requests", "00067-codex-overhead_print-openai-responses-r0.jsonl.gz")
            with gzip.open(sample, "rt", encoding="utf-8") as f:
                sent = json.loads(f.readline())["body"]["input"][0]["content"][0]["text"]
            self.assertEqual(entry["base_instructions"], sent)


if __name__ == "__main__":
    unittest.main()


class CloneTest(unittest.TestCase):
    def workspace(self):
        from buffon.arms import install
        tmp = tempfile.mkdtemp()
        return install.Workspace(install.Cache(os.path.join(tmp, "cache"), offline=True), work_dir=os.path.join(tmp, "w"))

    def arm(self, ws):
        from buffon.arms import manifest
        arm = manifest.load_arm("pi-node")
        arm.install_dir = os.path.join(ws.root, "arms", arm.slot)
        os.makedirs(os.path.join(arm.install_dir, "node_modules", "pkg", "bin"))
        with open(os.path.join(arm.install_dir, "node_modules", "pkg", "bin", "cli.js"), "w") as f:
            f.write("console.log(1)\n")
        os.makedirs(os.path.join(arm.install_dir, "node_modules", ".bin"))
        os.symlink("../pkg/bin/cli.js", os.path.join(arm.install_dir, "node_modules", ".bin", "pi"))
        arm.binary = os.path.join(arm.install_dir, "node_modules", ".bin", "pi")
        arm.path_dirs = [os.path.join(arm.install_dir, "node_modules", ".bin"), "/shared/runtime/bin"]
        arm.record = {"install_method": "npm"}
        return arm

    def test_the_copy_has_its_own_root_and_the_same_bytes(self):
        from buffon.arms import install
        with self.workspace() as ws:
            arm = self.arm(ws)
            twin = ws.clone(arm, "pi-node-b")
            self.assertNotEqual(twin.install_dir, arm.install_dir)
            self.assertTrue(twin.binary.startswith(twin.install_dir + os.sep))
            self.assertEqual(twin.path_dirs[1], "/shared/runtime/bin")  # runtimes stay shared
            self.assertTrue(twin.path_dirs[0].startswith(twin.install_dir))
            self.assertEqual(install.tree_sha256(ws.installed_tree(arm)), install.tree_sha256(ws.installed_tree(twin)))
            self.assertEqual(arm.binary.startswith(arm.install_dir), True)
            self.assertTrue(os.path.islink(twin.binary))

    def test_a_copy_that_differs_from_its_original_is_refused(self):
        from buffon.arms import install
        with self.workspace() as ws:
            arm = self.arm(ws)
            os.symlink(os.path.join(arm.install_dir, "node_modules", "pkg"), os.path.join(arm.install_dir, "node_modules", "abs"))  # an absolute link into the original root
            with self.assertRaises(install.InstallError):
                ws.clone(arm, "pi-node-b")


class OnlineInstallPair(unittest.TestCase):
    def run_online(self, listing):
        import types
        arm = types.SimpleNamespace(spec={"npm": {"checksums": "https://example.invalid/SHA256SUMS", "package_json": "p.json", "package_json_sha256": "a" * 64, "package_json_published": "pkg-p.json",
                                                  "package_lock": "l.json", "package_lock_sha256": "b" * 64, "package_lock_published": "pkg-l.json"}})
        saved = (lock.manifest.load_all, lock.manifest.load_runtimes, lock._fetch)
        lock.manifest.load_all, lock.manifest.load_runtimes, lock._fetch = (lambda *_: {"pi-node": arm}), (lambda *_: {}), (lambda url: listing.encode())
        try:
            return lock.online()
        finally:
            lock.manifest.load_all, lock.manifest.load_runtimes, lock._fetch = saved

    def test_the_pinned_install_pair_must_match_the_projects_checksum_file(self):
        good = f"{'a' * 64}  pkg-p.json\n{'b' * 64}  pkg-l.json\n"
        self.assertEqual(self.run_online(good), [])
        problems = self.run_online(f"{'c' * 64}  pkg-p.json\n{'b' * 64}  pkg-l.json\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("package_json", problems[0])
        self.assertIn("does not list pkg-l.json", self.run_online(f"{'a' * 64}  pkg-p.json\n")[0])


class ExcludedProjects(unittest.TestCase):
    def test_the_excluded_list_loads_and_every_entry_has_a_reason(self):
        rows = manifest.load_excluded()
        self.assertEqual({r["repo"] for r in rows}, {"chinudotdev/pi-go", "qiz029/pi-agent-go", "rcarmo/go-ai"})
        self.assertTrue(all(len(r["reason"]) > 30 for r in rows))
        self.assertNotIn("excluded", manifest.load_all())   # a file next to the arm directories is not an arm

    def test_an_entry_without_a_reason_is_refused(self):
        path = os.path.join(tempfile.mkdtemp(), "x.toml")
        with open(path, "w") as f:
            f.write('[[excluded]]\nrepo = "a/b"\n')
        with self.assertRaises(manifest.ManifestError):
            manifest.load_excluded(path)

    def test_the_report_lists_what_was_left_out(self):
        from buffon.report import render
        text = "\n".join(render.excluded_section(True))
        self.assertIn("## Not measured — PROVISIONAL", text)
        self.assertIn("| rcarmo/go-ai |", text)


class SourceInstall(unittest.TestCase):
    """_source: a manifest's public repo_url is the clone location when nothing else names one, and a submodule arm checks its submodules out before building."""

    def run_source(self, arm_name, repos=None):
        calls = []
        pinned = manifest.load_arm(arm_name).spec["source"]

        def fake_run(argv, cwd=None, env=None, timeout=3600):
            calls.append(argv)
            if argv[:2] == ["git", "rev-parse"]:
                return (pinned["commit"] if argv[2] == "HEAD" else pinned.get("tree", "t")) + "\n"
            return ""
        saved = install.run
        install.run = fake_run
        self.addCleanup(setattr, install, "run", saved)
        with install.Workspace(install.Cache(tempfile.mkdtemp()), work_dir=tempfile.mkdtemp()) as ins:
            ins.base_env = lambda toolchains: {}
            ins.runtimes_spec = {"go": {"version": "1"}}
            arm = manifest.load_arm(arm_name)
            os.environ.pop("BUFFON_SOURCE_REPO_RCARMO_GI", None)
            ins._source(arm, tempfile.mkdtemp(), repos or {})
        return calls, arm

    def test_the_manifest_url_is_cloned_and_submodules_are_checked_out_after_the_pinned_commit(self):
        calls, arm = self.run_source("rcarmo-gi")
        clone = next(c for c in calls if c[:2] == ["git", "clone"])
        self.assertEqual(clone[-2], "https://github.com/rcarmo/gi")
        order = [c[1] for c in calls if c[0] == "git"]
        self.assertLess(order.index("checkout"), order.index("submodule"))
        self.assertLess(order.index("submodule"), order.index("rev-parse"))
        self.assertIsNone(arm.skip)

    def test_an_explicit_repository_wins_over_the_manifest_url_and_other_arms_do_not_init_submodules(self):
        calls, _ = self.run_source("nowa-gi", {"nowa-gi": "/some/clone"})
        self.assertEqual(next(c for c in calls if c[:2] == ["git", "clone"])[-2], "/some/clone")
        self.assertFalse([c for c in calls if c[:2] == ["git", "submodule"]])


class PrebuiltInstall(unittest.TestCase):
    """_source offline: a bundle pod installs a source arm from the binary the bundle cross-built (cache/source/...), after checking it against the manifest."""

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()
        self.arm = manifest.load_arm("pig-tip")
        self.pinned = self.arm.spec["source"]

    def prebuild(self, **changes):
        import json
        ws = install.Workspace(install.Cache(self.cache_dir), work_dir=tempfile.mkdtemp())
        self.addCleanup(ws.__exit__)
        where = install.prebuilt_dir(self.cache_dir, "pig-tip", self.pinned["commit"], "linux-x64")
        os.makedirs(where, exist_ok=True)
        with open(os.path.join(where, "pig"), "wb") as f:
            f.write(b"\x7fELF pig")
        rec = dict(install.prebuilt_record(self.arm, "linux-x64", ws.runtimes_spec), binary="pig", sha256=manifest.sha256_file(os.path.join(where, "pig")))
        rec.update(changes)
        with open(os.path.join(where, install.PREBUILT_RECORD), "w") as f:
            json.dump(rec, f)
        return where

    def install(self, offline=True):
        calls = self.calls = []
        saved = install.run
        install.run = lambda argv, **_: calls.append(argv) or ""
        self.addCleanup(setattr, install, "run", saved)
        with install.Workspace(install.Cache(self.cache_dir, offline=offline), work_dir=tempfile.mkdtemp(), platform="linux-x64") as ws:
            arm = manifest.load_arm("pig-tip")
            dest = tempfile.mkdtemp()
            ws._source(arm, dest, {"pig-tip": "/some/clone"})
            return arm, dest, calls

    def test_the_prebuilt_binary_is_copied_and_recorded_with_the_pinned_commit(self):
        self.prebuild()
        arm, dest, calls = self.install()
        self.assertEqual(calls, [], "offline: no clone and no build")
        self.assertEqual(arm.binary, os.path.join(dest, "bin", "pig"))
        with open(arm.binary, "rb") as f:
            self.assertEqual(f.read(), b"\x7fELF pig")
        self.assertTrue(os.access(arm.binary, os.X_OK))
        self.assertEqual((arm.record["commit"], arm.record["tree"], arm.record["platform"]), (self.pinned["commit"], self.pinned["tree"], "linux-x64"))
        self.assertEqual(arm.record["install_method"], "source build (cross-built into the bundle)")

    def test_online_installs_build_from_the_clone_even_with_a_prebuilt_binary(self):
        self.prebuild()
        with self.assertRaisesRegex(install.InstallError, "checked out"):   # the recorder clones nothing, so the build stops at the commit check
            self.install(offline=False)
        self.assertEqual(self.calls[0][:2], ["git", "clone"])

    def test_refusals(self):
        with self.assertRaisesRegex(install.InstallError, "holds no binary built from"):
            self.install()
        for field, value in (("commit", "0" * 40), ("tree", "1" * 40), ("build", ["go", "build"]), ("env", {}), ("toolchain", "go 0"), ("platform", "linux-arm64"), ("arm", "x")):
            with self.subTest(field=field):
                self.prebuild(**{field: value})
                with self.assertRaisesRegex(install.InstallError, f"prebuilt binary's {field} differ"):
                    self.install()
        where = self.prebuild()
        with open(os.path.join(where, "pig"), "ab") as f:
            f.write(b"tampered")
        with self.assertRaisesRegex(install.InstallError, "sha256 differs from its record"):
            self.install()
        self.prebuild(binary="../pig")
        with self.assertRaisesRegex(install.InstallError, "missing or its sha256"):
            self.install()


class PigletRecord(unittest.TestCase):
    def test_slots_strip_and_binary_size_are_read_from_the_piglet_yaml(self):
        from buffon.arms import prepare_pig
        d = tempfile.mkdtemp()
        std = os.path.join(d, "std.yaml")
        with open(std, "w") as f:
            f.write("name: pig-standard\nbuild:\n  extensionRealization: fused\n\nextensions:\n  - name: piglogin\n    origins:\n      - local:extensions/piglogin\n  - name: pigrunner\n    origins:\n      - local:x\ndiscovery:\n  extensions: []\n")
        self.assertEqual(prepare_pig.yaml_slots(std), ["piglogin", "pigrunner"])
        self.assertIsNone(prepare_pig.strip_of(std))
        strip = os.path.join(ROOT, "fixtures", "piglets", "pig-min.yaml")
        self.assertEqual(prepare_pig.yaml_slots(strip), [])
        self.assertIn("keep:", prepare_pig.strip_of(strip))
        binary = os.path.join(d, "bin")
        with open(binary, "wb") as f:
            f.write(b"x" * 1234)
        import types
        arm = types.SimpleNamespace(record={}, binary=binary)
        prepare_pig.piglet_record(arm, ["a", "b"], strip="keep: x")
        self.assertEqual(arm.record["piglet"], {"label": "base Piglet + slots, one binary", "slots": ["a", "b"], "strip": "keep: x", "runtime_slot": None, "binary_bytes": 1234})

    def test_the_report_lists_piglet_arms_with_slots_and_size_and_nothing_when_there_are_none(self):
        from buffon.report import render
        run = {"arms": {"pig-standard": {"piglet": {"label": "base Piglet + slots, one binary", "slots": ["piglogin", "pigrunner"], "strip": None, "runtime_slot": "bun 1.4 (slot/bun)", "binary_bytes": 52_000_000}},
                        "pi-node": {}}}
        text = "\n".join(render.piglet_section([run], True))
        self.assertIn("## Piglet arms — PROVISIONAL", text)
        self.assertIn("| pig-standard | base Piglet + slots, one binary | piglogin, pigrunner; runtime slot: bun 1.4 (slot/bun) | 52.0 MB |", text)
        self.assertEqual(render.piglet_section([{"arms": {"pi-node": {}}}], True), [])

class NpmCache(unittest.TestCase):
    """`npm ci` for an npm arm reads the cache the workspace was given (a bundle's npm-cache/), and offline when downloads are off."""

    def install_pi_node(self, npm_cache, offline):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        ws = install.Workspace(install.Cache(os.path.join(tmp, "cache"), offline=offline), work_dir=os.path.join(tmp, "w"), npm_cache=npm_cache)
        self.addCleanup(ws.__exit__)
        arm = manifest.load_arm("pi-node")
        runtime = arm.spec["npm"]["runtime"]
        ws.base_env = lambda names: {"PATH": "/usr/bin"}
        ws.runtime = lambda name: os.path.join(tmp, "runtime")
        ws.runtimes[runtime] = {"version": "v0"}
        dest = os.path.join(tmp, "dest")
        os.makedirs(dest)
        calls = []
        saved = install.run
        install.run = lambda argv, cwd=None, env=None, timeout=0: calls.append((argv, cwd, env))
        try:
            ws._npm(arm, dest)
        finally:
            install.run = saved
        self.assertEqual([c[0] for c in calls], [["npm", "ci", "--ignore-scripts"]])
        return ws, calls[0][2]

    def test_a_given_npm_cache_is_the_one_npm_reads(self):
        given = os.path.join(tempfile.mkdtemp(), "npm-cache")
        _, env = self.install_pi_node(given, offline=True)
        self.assertEqual(env["npm_config_cache"], given)
        self.assertEqual(env["npm_config_offline"], "true")

    def test_a_relative_npm_cache_is_made_absolute_because_npm_runs_in_the_arm_directory(self):
        _, env = self.install_pi_node("npm-cache", offline=True)
        self.assertEqual(env["npm_config_cache"], os.path.abspath("npm-cache"))

    def test_without_one_each_workspace_has_its_own_and_npm_may_download(self):
        ws, env = self.install_pi_node(None, offline=False)
        self.assertEqual(env["npm_config_cache"], os.path.join(ws.root, "npm-cache"))
        self.assertNotIn("npm_config_offline", env)

    def test_the_session_flag_reaches_the_workspace(self):
        from buffon import cli
        from buffon.runner import engine
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        args = cli.build_parser().parse_args(["session", "--arms", "pi-node", "--offline", "--cache-dir", os.path.join(tmp, "c"), "--work-dir", os.path.join(tmp, "w"),
                                              "--npm-cache", os.path.join(tmp, "npm-cache"), "--out", os.path.join(tmp, "out")])
        plan = cli.session_plan(args)
        self.assertEqual(plan.npm_cache, os.path.join(tmp, "npm-cache"))
        with engine.Runner(plan, log=lambda *_: None).workspace() as ws:
            self.assertEqual(ws.npm_cache, os.path.join(tmp, "npm-cache"))
            self.assertTrue(ws.cache.offline)
        args = cli.build_parser().parse_args(["session", "--arms", "pi-node", "--work-dir", os.path.join(tmp, "w"), "--out", os.path.join(tmp, "out")])
        with engine.Runner(cli.session_plan(args), log=lambda *_: None).workspace() as ws:
            self.assertIsNone(ws.npm_cache)
