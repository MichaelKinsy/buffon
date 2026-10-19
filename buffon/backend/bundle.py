# SPDX-License-Identifier: Apache-2.0
"""Build a bundle: the directory a Kubernetes pod runs from when the site sets `[kubernetes] bundle = true`.

A bundle lets the pod run a session with no network. buffon-cluster copies it into the pod and runs the session with the bundle as `{root}`:

    <tracked files>      the repository at HEAD (git ls-files), so `python3 -m buffon` runs from {root}
    cache/               every artifact and runtime the selected arms need for linux-<arch>, in the content-addressed layout of buffon.arms.install.Cache, and
                         cache/source/<arm>/<commit>/linux-<arch>/: each Go source arm cross-built from its pinned commit with the pinned toolchain (install.prebuilt_dir)
    npm-cache/           a prefilled npm cache for every npm arm, resolved for linux-<arch>, so `npm ci` runs offline in the pod
    bin/buffon-cluster    the pod session, built for linux-<arch> with the pinned Go runtime
    bundle.json          the architecture, the arms carried and skipped, and the commit, tree and dirtiness (dirty, diff_sha256) of Buffon checkout the bundle
                         was built from
    ARTIFACTS.sha256     "<sha256>  <relative path>" for every regular file above; buffon-cluster checks it before it sends the bundle

A bundle is built for one architecture: buffon-cluster refuses a bundle whose Linux programs disagree, and a node of another architecture.
A source arm is carried when its toolchain is Go with CGO off, so that a build on this machine for linux-<arch> is the build the pod would make: the pod installs it offline
from cache/source/ after checking its record against the manifest. Any other source arm, and every derived arm (it prepares from its base's source checkout, which a
bundle does not carry), is reported as skipped, with the reason.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

from ..arms import install, manifest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARCHES = {"amd64": "x64", "arm64": "arm64"}  # Kubernetes/Go architecture -> Buffon's platform suffix and npm's --cpu
PROGRAM = "bin/buffon-cluster"
META = "bundle.json"


class BundleError(RuntimeError):
    pass


def tracked_files(repo, allow_dirty=False, runner=subprocess.run):
    """The repository's tracked files at HEAD. A modified tracked file is refused unless allow_dirty: the bundle would not be the commit it names."""
    if not allow_dirty:
        dirty = runner(["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=True).stdout.strip()
        if dirty:
            raise BundleError(f"{repo} has modified tracked files; commit them or pass allow_dirty:\n{dirty}")
    out = runner(["git", "-C", repo, "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0") if p]


def write_sums(out_dir):
    """Write ARTIFACTS.sha256 over every regular file in out_dir, sorted by path. Symbolic links are not listed."""
    lines = []
    for dirpath, dirnames, filenames in os.walk(out_dir):
        dirnames.sort()
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, out_dir).replace(os.sep, "/")
            if rel == "ARTIFACTS.sha256" or os.path.islink(path) or not os.path.isfile(path):
                continue
            lines.append(f"{manifest.sha256_file(path)}  {rel}")
    lines.sort(key=lambda line: line.split("  ", 1)[1])
    with open(os.path.join(out_dir, "ARTIFACTS.sha256"), "w") as f:
        f.write("".join(line + "\n" for line in lines))
    return len(lines)


def npm_project(arm, dest):
    """Write the npm arm's verified package.json and package-lock.json into dest, as the installer does before `npm ci`."""
    n = arm.spec["npm"]
    lock_path = os.path.join(arm.dir, n["package_lock"])
    if manifest.sha256_file(lock_path) != n["package_lock_sha256"]:
        raise BundleError(f"{arm.id}: {n['package_lock']} differs from the manifest's sha256")
    shutil.copy(lock_path, os.path.join(dest, "package-lock.json"))
    if "package_json" in n:
        if manifest.sha256_file(os.path.join(arm.dir, n["package_json"])) != n["package_json_sha256"]:
            raise BundleError(f"{arm.id}: {n['package_json']} differs from the manifest's sha256")
        shutil.copy(os.path.join(arm.dir, n["package_json"]), os.path.join(dest, "package.json"))
    else:
        with open(os.path.join(dest, "package.json"), "w") as f:
            json.dump({"name": f"arena-arm-{arm.id}", "version": "0.0.0", "private": True, "dependencies": {n["package"]: n["version"]}}, f)


def source_repo(arm, repos=None):
    """Where a source arm's repository is: the caller's, else the manifest's repo_env variable, else its repo_url; "" when none is known."""
    s = arm.spec["source"]
    return (repos or {}).get(arm.id) or os.environ.get(s["repo_env"], "") or s.get("repo_url", "")


def cross_build(ws, arm, cache_dir, arch, platform, repo, runtimes_spec):
    """Build a source arm at its pinned commit for linux-<arch> into the bundle's cache (install.prebuilt_dir) and write its record. The checkout's commit and tree must
    be the manifest's."""
    s = arm.spec["source"]
    with tempfile.TemporaryDirectory(prefix="buffon-src-") as src:
        install.run(["git", "clone", "--quiet", "--no-checkout", repo, src])
        install.run(["git", "checkout", "--quiet", "--detach", s["commit"]], cwd=src)
        if s.get("submodules"):
            install.run(["git", "submodule", "update", "--init", "--recursive", "--quiet"], cwd=src, timeout=1200)
        head = install.run(["git", "rev-parse", "HEAD"], cwd=src).strip()
        tree = install.run(["git", "rev-parse", "HEAD^{tree}"], cwd=src).strip()
        if head != s["commit"] or (s.get("tree") and tree != s["tree"]):
            raise BundleError(f"{arm.id}: checked out {head}/{tree}, the manifest pins {s['commit']}/{s.get('tree')}")
        env = ws.base_env([s["toolchain"]])
        env.update(s.get("env", {}))
        env.update(GOOS="linux", GOARCH=arch)
        name = os.path.basename(s["package"].rstrip("/")) or "arm"
        where = install.prebuilt_dir(cache_dir, arm.id, s["commit"], platform)
        os.makedirs(where, exist_ok=True)
        out = os.path.join(where, name)
        install.run([a.replace("{out}", out).replace("{package}", s["package"]) for a in s["build"]], cwd=src, env=env, timeout=3600)
    record = dict(install.prebuilt_record(arm, platform, runtimes_spec), binary=name, sha256=manifest.sha256_file(out))
    with open(os.path.join(where, install.PREBUILT_RECORD), "w") as f:
        json.dump(record, f, indent=2, sort_keys=True)
    return record


def cross_buildable(arm):
    """Why a source arm cannot be cross-built for the bundle, or None: only a Go build with CGO off gives this machine and the pod the same binary."""
    s = arm.spec["source"]
    if s.get("toolchain") != "go" or s.get("env", {}).get("CGO_ENABLED") != "0":
        return f"built from source with {s.get('toolchain')} (CGO_ENABLED={s.get('env', {}).get('CGO_ENABLED', 'unset')}); a bundle cross-builds only Go with CGO_ENABLED=0"
    return None


def checkout_ids(repo, runner=subprocess.run):
    """Buffon checkout's commit and tree."""
    def rev(what):
        return runner(["git", "-C", repo, "rev-parse", what], capture_output=True, text=True, check=True).stdout.strip()
    return rev("HEAD"), rev("HEAD^{tree}")


def checkout_dirty(repo, runner=subprocess.run):
    """(dirty, diff_sha256): whether a tracked file differs from HEAD, and then the sha256 of `git diff HEAD --binary`, as facts.runner_checkout records for a git
    checkout. A bundle built with allow_dirty carries those files, so its commit alone does not describe the code a pod runs."""
    status = runner(["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=True).stdout.strip()
    if not status:
        return False, None
    diff = runner(["git", "-C", repo, "diff", "HEAD", "--binary"], capture_output=True, check=True).stdout
    return True, hashlib.sha256(diff if isinstance(diff, bytes) else diff.encode()).hexdigest()


def build(out_dir, arch, arm_ids=None, repo=ROOT, host_cache="", allow_dirty=False, runner=subprocess.run, arms_dir=manifest.ARMS_DIR, source_repos=None):
    """Build a bundle for linux-<arch> into out_dir (absent or empty). arm_ids None bundles every arm that is not held.
    host_cache holds the downloads for this machine's own runtimes (the Node that prefills npm, the Go that builds buffon-cluster and the source arms).
    source_repos maps a source arm to its repository (default: the manifest's repo_env variable, else repo_url).
    Returns {"arch", "platform", "arms", "skipped", "files", "commit", "tree", "dirty", "diff_sha256"}; bundle.json holds the same without "files"."""
    if arch not in ARCHES:
        raise BundleError(f"arch {arch!r}: a bundle is built for one of {', '.join(sorted(ARCHES))}")
    platform = f"linux-{ARCHES[arch]}"
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise BundleError(f"{out_dir} is not empty")
    arms = manifest.load_all(arms_dir)
    if arm_ids is not None:
        unknown = sorted(set(arm_ids) - set(arms))
        if unknown:
            raise BundleError(f"unknown arms: {', '.join(unknown)}")
        arms = {i: arms[i] for i in arm_ids}
    os.makedirs(out_dir, exist_ok=True)
    commit, tree = checkout_ids(repo, runner)
    files = tracked_files(repo, allow_dirty, runner)
    dirty, diff_sha256 = checkout_dirty(repo, runner) if allow_dirty else (False, None)
    for rel in files:
        src, dst = os.path.join(repo, rel), os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=False)

    cache = install.Cache(os.path.join(out_dir, "cache"))
    runtimes_spec = manifest.load_runtimes()
    bundled, skipped, runtimes, npm_arms, source_arms = [], {}, set(), [], []
    for arm_id in sorted(arms):
        arm = arms[arm_id]
        if arm.held:
            skipped[arm_id] = f"held: {arm.held}"
            continue
        if getattr(arm, "operator_terms", None):
            skipped[arm_id] = "operator terms: installed from its vendor at run time by the operator who accepts them, never bundled"
            continue
        kind = arm.install_kind
        if kind == "artifact":
            art = arm.spec["artifact"].get(platform)
            if not art:
                skipped[arm_id] = f"no pinned artifact for {platform}"
                continue
            cache.get(art["url"], art["sha256"])
        elif kind == "npm":
            runtimes.add(arm.spec["npm"]["runtime"])
            npm_arms.append(arm)
        elif kind == "source":
            why = cross_buildable(arm)
            where = source_repo(arm, source_repos)
            if why or not where:
                skipped[arm_id] = why or f"no source repository: set {arm.spec['source']['repo_env']} to a clone or URL of the repository holding commit {arm.spec['source']['commit'][:12]}"
                continue
            source_arms.append((arm, where))
        else:
            skipped[arm_id] = f"{kind or 'no install kind'}: derived from {getattr(arm, 'base', None) or 'another arm'}, it prepares from the base's source checkout, which a bundle does not carry"
            continue
        runtimes.update(arm.spec.get("runtime", {}))
        bundled.append(arm_id)
    for name in sorted(runtimes):
        art = runtimes_spec[name].get("artifact", {}).get(platform)
        if not art:
            raise BundleError(f"runtime {name} has no pinned artifact for {platform}")
        cache.get(art["url"], art["sha256"])

    with install.Workspace(install.Cache(host_cache or os.path.join(out_dir, ".host-cache"))) as ws:
        npm_cache = os.path.join(out_dir, "npm-cache")
        for arm in npm_arms:
            n = arm.spec["npm"]
            env = ws.base_env([n["runtime"]])
            env.update(npm_config_cache=npm_cache, npm_config_os="linux", npm_config_cpu=ARCHES[arch], npm_config_update_notifier="false", npm_config_fund="false",
                       npm_config_audit="false")
            with tempfile.TemporaryDirectory() as scratch:
                npm_project(arm, scratch)
                install.run(["npm", "ci", "--ignore-scripts"], cwd=scratch, env=env, timeout=1200)
        # npm writes a debug log into its cache (the builder's home, its .npmrc path, the bundle's absolute path): the bundle carries the package content only
        shutil.rmtree(os.path.join(npm_cache, "_logs"), ignore_errors=True)
        for arm, where in source_arms:
            cross_build(ws, arm, cache.dir, arch, platform, where, runtimes_spec)
        env = ws.base_env(["go"])
        env.update(CGO_ENABLED="0", GOOS="linux", GOARCH=arch, GOFLAGS="-trimpath", GOTOOLCHAIN="local")
        os.makedirs(os.path.join(out_dir, "bin"), exist_ok=True)
        install.run(["go", "build", "-o", os.path.join(out_dir, PROGRAM), "."], cwd=os.path.join(out_dir, "cluster"), env=env, timeout=1200)
    shutil.rmtree(os.path.join(out_dir, ".host-cache"), ignore_errors=True)
    meta = {"arch": arch, "platform": platform, "arms": bundled, "skipped": skipped, "commit": commit, "tree": tree, "dirty": dirty, "diff_sha256": diff_sha256}
    with open(os.path.join(out_dir, META), "w") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
    files = write_sums(out_dir)
    return dict(meta, files=files)


def read_meta(bundle_dir):
    """A built bundle's bundle.json; BundleError when the directory is not a finished bundle (no bundle.json or no ARTIFACTS.sha256)."""
    try:
        with open(os.path.join(bundle_dir, META)) as f:
            meta = json.load(f)
    except (OSError, ValueError) as error:
        raise BundleError(f"{bundle_dir} is not a bundle: {error}") from error
    if not os.path.isfile(os.path.join(bundle_dir, "ARTIFACTS.sha256")):
        raise BundleError(f"{bundle_dir} is not a finished bundle: no ARTIFACTS.sha256")
    return meta


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m buffon.backend.bundle", description="Build a bundle directory for a Kubernetes site with bundle = true.")
    p.add_argument("--out", required=True)
    p.add_argument("--arch", default="amd64", choices=sorted(ARCHES))
    p.add_argument("--arms", nargs="*", default=None, help="arm ids (default: every arm that is not held)")
    p.add_argument("--host-cache", default="", help="download cache for this machine's Node and Go (default: a throwaway one)")
    p.add_argument("--allow-dirty", action="store_true")
    args = p.parse_args(argv)
    try:
        summary = build(os.path.abspath(args.out), args.arch, args.arms, host_cache=args.host_cache, allow_dirty=args.allow_dirty)
    except (BundleError, install.InstallError, subprocess.CalledProcessError) as e:
        print(f"buffon bundle: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
