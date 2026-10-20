# SPDX-License-Identifier: Apache-2.0
"""arms.lock: one lockfile generated from every arm manifest and runtimes.toml.

`python3 -m buffon lock` writes it; `--check` fails when it differs from what the manifests generate; `--online` also checks each artifact hash against the
checksum file its project publishes (SHA256SUMS, a .sha256 sidecar, nodejs.org's SHASUMS256.txt, go.dev's download list). The sha256 of the file is printed
in every report. The file is canonical JSON (sorted keys, LF), so the same manifests always give the same bytes.
"""
import hashlib
import json
import os
import urllib.request

from . import manifest

LOCK_FILE = os.path.join(manifest.ROOT, "arms.lock")


def generate(arms_dir=manifest.ARMS_DIR, runtimes_file=manifest.RUNTIMES_FILE):
    arms = manifest.load_all(arms_dir)
    runtimes = manifest.load_runtimes(runtimes_file)
    out = {"arms": {}, "runtimes": runtimes}
    for name, arm in arms.items():
        entry = {"manifest_sha256": arm.manifest_sha256, "version": arm.version, "licence": arm.licence, "held": arm.held, "spec": arm.spec}
        entry["files"] = {n: manifest.sha256_file(os.path.join(arm.dir, n)) for n in sorted(os.listdir(arm.dir)) if n != "arm.toml" and os.path.isfile(os.path.join(arm.dir, n)) and not n.endswith(".pyc")}
        if arm.adapter:   # the adapter is part of the arm: every file of its source directory, by path, so a change to it changes provenance
            entry["files"].update(adapter_files(arm))
        out["arms"][name] = entry
    return out


def adapter_files(arm):
    """{path relative to the arm directory: sha256} of every file under the adapter's source directory (node_modules, build output and caches are not source)."""
    root = os.path.join(arm.dir, arm.adapter["source"])
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in ("node_modules", "dist", "__pycache__", ".cache"))
        for name in sorted(files):
            if not name.endswith(".pyc"):
                full = os.path.join(base, name)
                out[os.path.relpath(full, arm.dir).replace(os.sep, "/")] = manifest.sha256_file(full)
    return out


def dumps(data):
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def write(path=LOCK_FILE, **kw):
    with open(path, "w", newline="\n") as f:
        f.write(dumps(generate(**kw)))


def lock_hash(path=LOCK_FILE):
    return manifest.sha256_file(path)


def check(path=LOCK_FILE, **kw):
    """Problems (a list of strings): the lockfile is missing or differs from what the manifests generate."""
    if not os.path.exists(path):
        return [f"{os.path.basename(path)} is missing; run `python3 -m buffon lock`"]
    with open(path) as f:
        have = f.read()
    return [] if have == dumps(generate(**kw)) else [f"{os.path.basename(path)} is out of date with the manifests; run `python3 -m buffon lock` and commit it"]


def _fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 - https URLs from committed manifests
        return r.read()


def published_sha256(checksums_url, name):
    """The sha256 the project publishes for file `name`, from its checksum file; None when the file does not list it."""
    data = _fetch(checksums_url)
    if "go.dev/dl" in checksums_url:
        for release in json.loads(data):
            for f in release["files"]:
                if f["filename"] == name:
                    return f["sha256"]
        return None
    text = data.decode()
    if checksums_url.endswith(".sha256"):  # a sidecar holds one hash
        return text.split()[0]
    for line in text.splitlines():
        digest, _, file = line.strip().partition("  ")
        if file.lstrip("*") == name or file.lstrip("*").endswith("/" + name):
            return digest
    return None


def online(arms_dir=manifest.ARMS_DIR, runtimes_file=manifest.RUNTIMES_FILE):
    """Compare every locked artifact hash with the project's own published checksum. Returns problems."""
    problems = []

    def one(label, url, sha, checksums):
        if not checksums:
            return
        want = published_sha256(checksums, os.path.basename(url))
        if want is None:
            problems.append(f"{label}: {checksums} does not list {os.path.basename(url)}")
        elif want != sha:
            problems.append(f"{label}: manifest sha256 {sha[:12]} differs from the published {want[:12]}")

    for name, arm in manifest.load_all(arms_dir).items():
        for plat, a in arm.spec.get("artifact", {}).items():
            one(f"{name} {plat}", a["url"], a["sha256"], a.get("checksums"))
        n = arm.spec.get("npm", {})
        for key in ("package_json", "package_lock"):  # the install pair is pinned by the project's own checksum file too
            if n.get(key) and n.get("checksums") and n.get(key + "_published"):
                want = published_sha256(n["checksums"], n[key + "_published"])
                if want is None:
                    problems.append(f"{name} {key}: {n['checksums']} does not list {n[key + '_published']}")
                elif want != n[key + "_sha256"]:
                    problems.append(f"{name} {key}: manifest sha256 {n[key + '_sha256'][:12]} differs from the published {want[:12]}")
    rt = manifest.load_runtimes(runtimes_file)
    for name, r in rt.items():
        for plat, a in r.get("artifact", {}).items():
            one(f"runtime {name} {plat}", a["url"], a["sha256"], r.get("checksums"))
    return problems
