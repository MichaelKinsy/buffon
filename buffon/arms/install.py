# SPDX-License-Identifier: Apache-2.0
"""Install arms and runtimes from their manifests into a throwaway workspace; verify every hash and version.

Nothing is installed from a floating source. Every download goes through the artifact cache: a file is used only when its sha256 equals the manifest's, and a
cached file is re-hashed each time. With offline=True (a pod that was given a verified bundle) a missing cache entry is an error, never a download.
"""
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

from . import manifest
from .writers import DUMMY_KEY


class InstallError(RuntimeError):
    pass


def run(argv, cwd=None, env=None, timeout=3600):
    done = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if done.returncode:
        raise InstallError(f"{' '.join(argv)} failed:\n{(done.stdout + done.stderr)[-2000:]}")
    return done.stdout


class Cache:
    """Content-addressed download cache: <dir>/<sha256>/<file name>."""

    def __init__(self, directory, offline=False):
        self.dir, self.offline = directory, offline

    def path(self, sha256, url):
        return os.path.join(self.dir, sha256, os.path.basename(url))

    def get(self, url, sha256):
        path = self.path(sha256, url)
        if os.path.exists(path):
            if manifest.sha256_file(path) == sha256:
                return path
            os.unlink(path)  # a damaged cache entry is never used
        if self.offline:
            raise InstallError(f"{os.path.basename(url)} is not in the offline cache and downloads are off")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        h = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=600) as r, open(tmp, "wb") as f:  # noqa: S310 - https URLs from committed manifests
            for block in iter(lambda: r.read(1 << 20), b""):
                h.update(block)
                f.write(block)
        if h.hexdigest() != sha256:
            os.unlink(tmp)
            raise InstallError(f"{url}: sha256 {h.hexdigest()} does not match the manifest's {sha256}")
        os.replace(tmp, path)
        return path


def unpack(archive, dest):
    os.makedirs(dest, exist_ok=True)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
        for base, _, files in os.walk(dest):
            for name in files:
                os.chmod(os.path.join(base, name), os.stat(os.path.join(base, name)).st_mode | 0o111 if name in ("bun",) else os.stat(os.path.join(base, name)).st_mode)
    elif archive.endswith((".tar.gz", ".tgz", ".tar.xz")):
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")
    else:
        return False
    return True


def tree_size(path):
    total = 0
    for base, _, files in os.walk(path):
        for name in files:
            p = os.path.join(base, name)
            if not os.path.islink(p):
                total += os.path.getsize(p)
    return total


def tree_sha256(path):
    """One digest of an installed tree: every file's relative path, executable bit and content, and every symlink's target, in path order.

    For an npm arm the executable alone is a small entry script; the code that runs is the whole node_modules tree, so that is what a run checks."""
    h = hashlib.sha256()
    entries = []
    for base, dirs, files in os.walk(path):
        dirs.sort()
        for name in sorted(files + [d for d in dirs if os.path.islink(os.path.join(base, d))]):
            entries.append(os.path.join(base, name))
    for full in sorted(entries):
        rel = os.path.relpath(full, path)
        if os.path.islink(full):
            h.update(f"L {rel}\0{os.readlink(full)}\0".encode())
        elif os.path.isfile(full):
            mode = "x" if os.stat(full).st_mode & 0o111 else "-"
            h.update(f"F {rel}\0{mode}\0{manifest.sha256_file(full)}\0".encode())
    return h.hexdigest()


PREBUILT_RECORD = "record.json"


def prebuilt_dir(cache_dir, arm_id, commit, platform):
    """Where an offline cache keeps a source arm's binary built for platform: <cache>/source/<arm>/<commit>/<platform>/ with the binary and record.json."""
    return os.path.join(cache_dir, "source", arm_id, commit, platform)


def prebuilt_record(arm, platform, runtimes_spec):
    """The fields a prebuilt binary's record must hold for a source arm on platform: what the manifest pins (commit, tree, build command, its environment and the
    toolchain's version). The builder adds the binary's file name and sha256."""
    s = arm.spec["source"]
    return {"arm": arm.id, "commit": s["commit"], "tree": s.get("tree"), "package": s["package"], "build": list(s["build"]), "env": dict(s.get("env", {})),
            "toolchain": f"{s['toolchain']} {runtimes_spec[s['toolchain']]['version']}", "platform": platform}


class Workspace:
    """A throwaway directory holding installed runtimes and arms, and the per-run homes. Deleted on exit unless keep=True.
    npm_cache is the cache `npm ci` reads and fills (a bundle's prefilled npm-cache/ for an offline install); without it each workspace gets an empty one of its own."""

    def __init__(self, cache, work_dir=None, keep=False, platform=None, npm_cache=None):
        self.cache = cache
        self.npm_cache = os.path.abspath(npm_cache) if npm_cache else None
        self.platform = platform or manifest.host_platform()
        os.makedirs(work_dir or tempfile.gettempdir(), exist_ok=True)
        self.root = tempfile.mkdtemp(prefix="buffon-", dir=work_dir)
        self.work = os.path.join(self.root, "work")
        os.makedirs(self.work)
        self.keep = keep or bool(os.environ.get("BUFFON_KEEP"))
        self.runtimes_spec = manifest.load_runtimes()
        self.runtimes = {}
        self.bases = {}          # arm id -> the installed base arm a derived arm copies (installed once per workspace)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if not self.keep:
            shutil.rmtree(self.root, ignore_errors=True)

    # -- runtimes -----------------------------------------------------------------------------------------------------------------------------

    def runtime(self, name):
        """Install a pinned runtime (node, go) once; returns its bin directory."""
        if name in self.runtimes:
            return self.runtimes[name]["bin"]
        spec = self.runtimes_spec[name]
        art = spec.get("artifact", {}).get(self.platform)
        if not art:
            raise InstallError(f"runtime {name} has no pinned artifact for {self.platform}")
        dest = os.path.join(self.root, "runtimes", name)
        unpack(self.cache.get(art["url"], art["sha256"]), dest)
        bindir = os.path.join(dest, art["root"], spec["bin"])
        self.runtimes[name] = {"bin": bindir, "version": spec["version"], "artifact_sha256": art["sha256"], "url": art["url"]}
        return bindir

    def base_env(self, runtime_names=()):
        env = dict(os.environ)
        dirs = [self.runtime(n) for n in runtime_names]
        env["PATH"] = os.pathsep.join(dirs + [env.get("PATH", "")])
        return env

    # -- arms ---------------------------------------------------------------------------------------------------------------------------------

    def install(self, arm, source_repos=None):
        """Install one arm. Sets arm.binary, arm.path_dirs, arm.record; sets arm.skip instead when this platform has no pinned artifact."""
        if arm.held:
            arm.skip = f"held: {arm.held}"
            return arm
        dest = os.path.join(self.root, "arms", arm.slot)
        os.makedirs(dest, exist_ok=True)
        arm.install_dir = dest
        kind = arm.install_kind
        if kind == "artifact":
            self._artifact(arm, dest)
        elif kind == "npm":
            self._npm(arm, dest)
        elif kind == "source":
            self._source(arm, dest, source_repos or {})
        elif kind == "derive":
            self._derive(arm, dest, source_repos or {})
        if arm.binary:
            for name in sorted(arm.spec.get("runtime", {})):  # a runtime the harness starts itself (PiG's Node sidecar), on the arm's PATH
                bindir = self.runtime(name)
                if bindir not in arm.path_dirs:
                    arm.path_dirs.append(bindir)
                arm.record[f"runtime_{name}"] = self.runtimes[name]["version"]
            if "prepare" in arm.spec:
                self._prepare(arm)
            arm.version_line = self.check_version(arm)
            if arm.spec.get("seed"):
                self._seed(arm)
        return arm

    def _seed(self, arm):
        """First-start state that a real user pays once and every measured sample would otherwise pay again (an unpacked native library, a model catalog cache). The manifest's seed command
        runs once in a scratch HOME with the arm's own environment, outside every measured sample; the resulting tree is copied into each harness HOME before the sample starts.
        Its digest is recorded with the arm."""
        sd = arm.spec["seed"]
        home = os.path.join(self.root, "seeds", arm.id)
        os.makedirs(home, exist_ok=True)
        env = self.plain_env(arm, home=home)
        argv = [arm.binary if part == "{binary}" else part for part in sd["command"]]
        done = subprocess.run(argv, capture_output=True, text=True, timeout=sd.get("timeout", 180), env=env, cwd=self.work)
        if not os.listdir(home) or not any(n != "tmp" for n in os.listdir(home)):
            raise InstallError(f"{arm.id}: the seed command left nothing in its HOME (exit {done.returncode}): {(done.stdout + done.stderr)[-300:]}")
        for name in sd.get("exclude", []):
            shutil.rmtree(os.path.join(home, name), ignore_errors=True)
        arm.seed_dir = home
        arm.record["seed_tree_sha256"] = tree_sha256(home)
        arm.record["seed_command"] = " ".join(sd["command"])

    def _prepare(self, arm):
        """Run the arm's `[prepare] script`: `prepare(ws, arm, base)` finishes the install (a runtime slot, a built Piglet Binary, a warm extension cache). It may change
        arm.binary and add to arm.record; everything it writes lives under arm.install_dir, so the A/A copy and the tree digest cover it."""
        import importlib.util
        path = os.path.join(arm.dir, arm.spec["prepare"]["script"])
        spec = importlib.util.spec_from_file_location(f"buffon_prepare_{arm.id.replace('-', '_')}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.prepare(self, arm, self.bases.get(arm.base))

    def clone(self, arm, new_id):
        """The A/A copy of an installed arm: its own copy of the install tree under its own root (page cache, paths and directory entries are then part of the noise floor).
        Runtimes (Node, Go) stay shared. The copy must be byte-identical to the original."""
        if not arm.binary:
            return None
        twin = copy.copy(arm)
        twin.id = new_id
        dest = os.path.join(self.root, "arms", twin.slot)
        shutil.copytree(arm.install_dir, dest, symlinks=True)
        for base, dirs, files in os.walk(dest):
            for name in dirs + files:
                full = os.path.join(base, name)
                if os.path.islink(full) and os.path.isabs(os.readlink(full)) and (os.readlink(full) + os.sep).startswith(arm.install_dir + os.sep):
                    raise InstallError(f"{new_id}: {os.path.relpath(full, dest)} links into {arm.id}'s install root, so the copy would share it")

        def rebase(path):
            return dest + path[len(arm.install_dir):] if path == arm.install_dir or path.startswith(arm.install_dir + os.sep) else path
        twin.install_dir = dest
        twin.binary = rebase(arm.binary)
        twin.path_dirs = [rebase(d) for d in arm.path_dirs]
        twin.record = dict(arm.record)
        for a, b in ((self.installed_tree(arm), self.installed_tree(twin)),):
            if tree_sha256(a) != tree_sha256(b):
                raise InstallError(f"{new_id}: the copy of {arm.id}'s install tree is not identical to it")
        return twin

    def _artifact(self, arm, dest):
        art = arm.spec["artifact"].get(self.platform)
        if not art:
            arm.skip = f"no pinned artifact for {self.platform}"
            return
        path = self.cache.get(art["url"], art["sha256"])
        if not unpack(path, dest):
            shutil.copy(path, os.path.join(dest, art["exe"]))  # the release asset is the executable itself
        arm.binary = os.path.join(dest, art["exe"])
        if not os.path.exists(arm.binary):
            raise InstallError(f"{arm.id}: {art['exe']} is not in {os.path.basename(art['url'])}")
        os.chmod(arm.binary, 0o755)
        arm.record = {"install_method": "release archive", "source_url": art["url"], "artifact_sha256": art["sha256"], "platform": self.platform}

    def _npm(self, arm, dest):
        n = arm.spec["npm"]
        env = self.base_env([n["runtime"]])
        env.update(npm_config_cache=self.npm_cache or os.path.join(self.root, "npm-cache"), npm_config_update_notifier="false", npm_config_fund="false", npm_config_audit="false")
        lock_path = os.path.join(arm.dir, n["package_lock"])
        if manifest.sha256_file(lock_path) != n["package_lock_sha256"]:
            raise InstallError(f"{arm.id}: {n['package_lock']} differs from the manifest's sha256")
        with open(lock_path) as f:
            plock = json.load(f)
        main = plock["packages"][f"node_modules/{n['package']}"]
        if main["version"] != n["version"] or main.setdefault("integrity", n["integrity"]) != n["integrity"]:
            raise InstallError(f"{arm.id}: the package lock disagrees with the manifest about {n['package']}")
        if "package_json" in n:
            if manifest.sha256_file(os.path.join(arm.dir, n["package_json"])) != n["package_json_sha256"]:
                raise InstallError(f"{arm.id}: {n['package_json']} differs from the manifest's sha256")
            shutil.copy(os.path.join(arm.dir, n["package_json"]), os.path.join(dest, "package.json"))
        else:
            with open(os.path.join(dest, "package.json"), "w") as f:
                json.dump({"name": f"arena-arm-{arm.id}", "version": "0.0.0", "private": True, "dependencies": {n["package"]: n["version"]}}, f)
        with open(os.path.join(dest, "package-lock.json"), "w") as f:
            json.dump(plock, f, indent=2)
        if self.cache.offline:
            env["npm_config_offline"] = "true"
        native = n.get("bin_native", {})   # the package's own `bin` is a stub that only its postinstall script (not run here) replaces: the executable is in the platform package
        if native and self.platform not in native:
            arm.skip = f"no pinned executable for {self.platform}"
            return
        run(["npm", "ci", "--ignore-scripts"], cwd=dest, env=env, timeout=1200)
        adapter = self._bundle_adapter(arm, dest, env) if arm.adapter else {}
        arm.binary = os.path.join(dest, native.get(self.platform, n["bin"]))
        if native and not os.path.isfile(arm.binary):
            raise InstallError(f"{arm.id}: {os.path.relpath(arm.binary, dest)} is not installed (npm skipped the optional dependency for {self.platform})")
        arm.path_dirs = [self.runtime(n["runtime"])]
        real = os.path.realpath(arm.binary)
        want = n.get("native_bin", {}).get(self.platform)
        if want and manifest.sha256_file(real) != want:
            raise InstallError(f"{arm.id}: executable sha256 differs from the manifest's")
        arm.record = {"install_method": "npm ci --ignore-scripts", "package": n["package"], "package_lock_sha256": n["package_lock_sha256"], "integrity": n["integrity"],
                      "platform": self.platform, "node": self.runtimes[n["runtime"]]["version"], **adapter}

    def _bundle_adapter(self, arm, dest, env):
        """A Node adapter (docs/DURABLE-ADAPTERS.md): its source directory is copied beside the installed packages and bundled by the esbuild the lock pins, into the file [npm] `bin` names.
        The bundle is built here, never committed; the record keeps the digest of the source it came from, the argv and the digest of the bundle, so the run shows what ran."""
        a = arm.adapter
        work = os.path.join(dest, "adapter")
        shutil.copytree(os.path.join(arm.dir, a["source"]), work)
        out = os.path.join(dest, arm.spec["npm"]["bin"])
        esbuild = os.path.join(dest, "node_modules", ".bin", "esbuild")
        if not os.path.exists(esbuild):
            raise InstallError(f"{arm.id}: esbuild is not in the installed packages: pin it in {arm.spec['npm']['package_json']}")
        argv = [esbuild, *[x.replace("{out}", out) for x in a["build"][1:]]]
        run(argv, cwd=work, env=env, timeout=600)
        if not os.path.isfile(out):
            raise InstallError(f"{arm.id}: the adapter build wrote no {os.path.basename(out)}")
        os.chmod(out, 0o755)
        return {"adapter_source_sha256": tree_sha256(work), "adapter_build": " ".join(a["build"]), "adapter_bundle_sha256": manifest.sha256_file(out), "adapter_bundle_bytes": os.path.getsize(out),
                "esbuild": run([esbuild, "--version"], env=env).strip()}

    def _source(self, arm, dest, repos):
        s = arm.spec["source"]
        if self.cache.offline:
            self._prebuilt(arm, dest)
            return
        repo = repos.get(arm.id) or os.environ.get(s["repo_env"]) or s.get("repo_url")
        if not repo:
            arm.skip = f"no source repository: set {s['repo_env']} to a clone or URL of the repository holding commit {s['commit'][:12]}"
            return
        src = os.path.join(self.root, "src", arm.id)
        os.makedirs(os.path.dirname(src), exist_ok=True)
        if not os.path.isdir(src):  # a derived arm builds from this checkout too; it is checked out once and verified below each time
            run(["git", "clone", "--quiet", "--no-checkout", repo, src])
            run(["git", "checkout", "--quiet", "--detach", s["commit"]], cwd=src)
            if s.get("submodules"):  # the submodule commits are part of the pinned commit's tree, so they are as pinned as the commit
                run(["git", "submodule", "update", "--init", "--recursive", "--quiet"], cwd=src, timeout=1200)
        head = run(["git", "rev-parse", "HEAD"], cwd=src).strip()
        tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=src).strip()
        if head != s["commit"] or (s.get("tree") and tree != s["tree"]):
            raise InstallError(f"{arm.id}: checked out {head}/{tree}, the manifest pins {s['commit']}/{s.get('tree')}")
        env = self.base_env([s["toolchain"]])
        env.update(s.get("env", {}))
        adapter = self._place_adapter(arm, src) if arm.adapter else {}
        out = os.path.join(dest, "bin", os.path.basename(s["package"].rstrip("/")) or "arm")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        argv = [a.replace("{out}", out).replace("{package}", s["package"]) for a in s["build"]]
        run(argv, cwd=src, env=env, timeout=3600)
        arm.binary = out
        if arm.adapter and os.path.isfile(out):
            adapter.update(adapter_bundle_sha256=manifest.sha256_file(out), adapter_bundle_bytes=os.path.getsize(out))
        arm.record = {"install_method": "source build", "commit": head, "tree": tree, "build": " ".join(argv), "toolchain": f"{s['toolchain']} {self.runtimes_spec[s['toolchain']]['version']}",
                      "platform": self.platform, **adapter}

    def _place_adapter(self, arm, src):
        """A Go adapter (docs/DURABLE-ADAPTERS.md): the pinned commit and tree were verified above, and the adapter's source directory is copied into the checkout at [source] `package`, so it builds inside the
        runtime's own module and links its public packages. The runtime's files are not changed; the digest of the adapter's source goes in the record."""
        package = os.path.join(src, arm.spec["source"]["package"])
        shutil.rmtree(package, ignore_errors=True)
        shutil.copytree(os.path.join(arm.dir, arm.adapter["source"]), package)
        return {"adapter_source_sha256": tree_sha256(package)}

    def _prebuilt(self, arm, dest):
        """An offline install of a source arm: the binary a bundle cross-built from the pinned commit with the pinned toolchain (buffon/backend/bundle.py), checked
        against the manifest's commit, tree, build command and toolchain and against its own sha256. Without it the arm cannot run offline."""
        s = arm.spec["source"]
        where = prebuilt_dir(self.cache.dir, arm.id, s["commit"], self.platform)
        try:
            with open(os.path.join(where, PREBUILT_RECORD)) as f:
                rec = json.load(f)
        except FileNotFoundError:
            raise InstallError(f"{arm.id}: downloads and source builds are off, and the offline cache holds no binary built from {s['commit'][:12]} for {self.platform}") from None
        want = prebuilt_record(arm, self.platform, self.runtimes_spec)
        differs = sorted(k for k in want if rec.get(k) != want[k])
        if differs:
            raise InstallError(f"{arm.id}: the prebuilt binary's {', '.join(differs)} differ from the manifest's")
        src = os.path.join(where, rec["binary"])
        if os.path.basename(rec["binary"]) != rec["binary"] or not os.path.isfile(src) or manifest.sha256_file(src) != rec["sha256"]:
            raise InstallError(f"{arm.id}: the prebuilt binary is missing or its sha256 differs from its record")
        out = os.path.join(dest, "bin", rec["binary"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copyfile(src, out)
        os.chmod(out, 0o755)
        arm.binary = out
        arm.record = {"install_method": "source build (cross-built into the bundle)", "commit": rec["commit"], "tree": rec["tree"], "build": " ".join(rec["build"]),
                      "toolchain": rec["toolchain"], "platform": self.platform}

    def _derive(self, arm, dest, repos):
        """A derived arm runs from its own copy of the base arm's install tree: the base is installed once, and the copy keeps the A/A rule that every arm has its own root."""
        base = self.bases.get(arm.base)
        if base is None:
            base = manifest.load_arm(arm.base)
            self.install(base, repos)
            self.bases[arm.base] = base
        if base.skip:
            arm.skip = f"its base arm {base.id} cannot run: {base.skip}"
            return
        shutil.rmtree(dest)
        shutil.copytree(base.install_dir, dest, symlinks=True)

        def rebase(path):
            return dest + path[len(base.install_dir):] if path == base.install_dir or path.startswith(base.install_dir + os.sep) else path
        arm.binary = rebase(base.binary)
        arm.path_dirs = [rebase(d) for d in base.path_dirs]
        arm.vars["shared_dir"] = os.path.join(self.root, "shared")  # one fixed path for every arm and A/A copy: a generated extension cell's cache key includes the PIG_HOME it was built under
        arm.vars["source_dir"] = os.path.join(self.root, "src", base.id)  # the base's checkout (a source arm), shared by every arm derived from it
        arm.record = dict(base.record, derived_from=base.id, base_executable_sha256=manifest.sha256_file(os.path.realpath(base.binary)))

    def check_version(self, arm, env=None):
        """Run the version mode and require the pinned version in its output."""
        h_env = env or self.plain_env(arm)
        argv = [arm.binary, *arm.modes["version"]]
        done = subprocess.run(argv, capture_output=True, text=True, timeout=120, env=h_env, cwd=self.work)
        text = done.stdout.strip() or done.stderr.strip()
        needle = arm.spec.get("version_check", {}).get("contains", arm.version.split("+")[0])
        line = next((ln for ln in text.splitlines() if needle in ln), None)
        if done.returncode != 0 or line is None:
            raise InstallError(f"{arm.id}: `--version` printed {text[:200]!r}; the manifest pins {needle}")
        return line.strip()

    def plain_env(self, arm, home=None):
        """The version check's environment: the operator's environment scrubbed as for a measured sample (no credentials, no agent or state
        directory of the operator's own), a throwaway HOME and the manifest's offline, telemetry and update settings."""
        from ..runner.harness import SYSTEM_PATH, scrubbed_environ
        home = home or os.path.join(self.root, "version-home")
        os.makedirs(home, exist_ok=True)
        agent_dir = os.path.join(home, ".agent")
        env = scrubbed_environ()
        env.update(HOME=home, XDG_CONFIG_HOME=os.path.join(home, ".config"), XDG_DATA_HOME=os.path.join(home, ".local", "share"),
                   XDG_CACHE_HOME=os.path.join(home, ".cache"), XDG_STATE_HOME=os.path.join(home, ".local", "state"))
        subs = {"home": home, "agent_dir": agent_dir, "dummy_key": DUMMY_KEY, "install_dir": getattr(arm, "install_dir", None), **getattr(arm, "vars", {})}
        for k, v in arm.env.items():
            env[k] = re.sub(r"\{(\w+)\}", lambda m: subs.get(m.group(1), m.group(0)), v)
        env["PATH"] = os.pathsep.join(list(arm.path_dirs) + list(SYSTEM_PATH))
        return env

    def installed_tree(self, arm):
        """The directory holding everything the arm runs: node_modules for an npm arm, the unpacked archive or the single executable otherwise."""
        if not arm.binary:
            return None
        if arm.install_kind == "npm":
            return os.path.join(arm.install_dir, "node_modules")
        return arm.install_dir

    def footprint(self, arm):
        """Bytes a user installs for this arm and the file count of that tree."""
        if not arm.binary:
            return None
        if arm.install_kind == "npm":
            nm = os.path.join(arm.install_dir, "node_modules")
            return {"bytes": tree_size(nm), "runtime": "node", "runtime_bytes": tree_size(os.path.dirname(arm.path_dirs[0])) if arm.path_dirs else None}
        base = os.path.dirname(arm.binary)
        size = tree_size(base) if arm.install_kind == "artifact" and os.path.dirname(os.path.relpath(arm.binary, arm.install_dir)) else os.path.getsize(os.path.realpath(arm.binary))
        return {"bytes": size, "runtime": None, "runtime_bytes": 0}
