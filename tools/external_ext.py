# SPDX-License-Identifier: Apache-2.0
"""Install a frozen external extension: `fixtures/external/<name>/` holds package.json (exact versions), package-lock.json (integrity of every package) and .npmrc (scripts off, peers
left to the host). `install` fills a local npm cache from the registry once (the fetch step), then runs `npm ci --offline` from that cache into the destination, so the installed tree is the
lockfile's and nothing is fetched while the comparison runs. `record` lists name@version and integrity of every installed package for the report."""
import json
import os
import shutil
import subprocess

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "external")


def install(name, dest, cache):
    """Return `dest`, which holds node_modules installed from the committed lockfile."""
    source = os.path.join(FIXTURES, name)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    for f in ("package.json", "package-lock.json", ".npmrc"):
        shutil.copy(os.path.join(source, f), os.path.join(dest, f))
    base = ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--cache", cache]
    if subprocess.run(base + ["--offline"], cwd=dest, capture_output=True).returncode != 0:
        # The fetch step, the only network access: it fills the cache with the lockfile's tarballs (npm verifies each against its integrity), then the offline install must succeed.
        shutil.rmtree(os.path.join(dest, "node_modules"), ignore_errors=True)
        subprocess.run(base + ["--prefer-online"], cwd=dest, check=True, capture_output=True)
        shutil.rmtree(os.path.join(dest, "node_modules"))
        subprocess.run(base + ["--offline"], cwd=dest, check=True, capture_output=True)
    return dest


def record(dest):
    """[(name@version, integrity)] of the installed tree, from the lockfile npm ci installed; raises if the tree differs from it."""
    lock = json.load(open(os.path.join(dest, "package-lock.json")))
    out = []
    for path, entry in sorted(lock["packages"].items()):
        if not path:
            continue
        manifest = os.path.join(dest, path, "package.json")
        if not os.path.exists(manifest):
            if entry.get("optional"):
                continue
            raise RuntimeError(f"{path} is in the lockfile and not installed")
        installed = json.load(open(manifest))["version"]
        if installed != entry["version"]:
            raise RuntimeError(f"{path}: installed {installed}, lockfile {entry['version']}")
        out.append((f"{path.split('node_modules/')[-1]}@{installed}", entry.get("integrity")))
    return out
