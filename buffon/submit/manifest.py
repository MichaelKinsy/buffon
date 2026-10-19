# SPDX-License-Identifier: Apache-2.0
"""MANIFEST.sha256: the seal of a run directory.

`write` lists the sha256 of every file the run produced (raw.json, facts.json, the mock's request logs, logs) in `sha256sum` format, so a copy that has been edited, truncated or
added to is detected by `check`. The files a report generates from the raw data (report.*, the CSV series, plots, health.json) are not sealed: they are recomputed from the sealed
ones, and `buffon verify` compares them with the recomputation instead."""
import hashlib
import os

NAME = "MANIFEST.sha256"
GENERATED_FILES = {"report.md", "report.html", "report.json", "grade.json", "leaderboard.md", "leaderboard.html", "report-card.md", "report-card.html", "summary.csv", "rounds.csv", "noise.csv", "telemetry.csv", "health.json", "reproduction.md", "reproduction.json", "raw.partial.json"}
GENERATED_DIRS = {"plots"}
OPERATOR_FILES = {"submission.toml", "promotion.json"}    # written after the run (by the submitter, by CI); validated or recomputed, not sealed


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sealed_files(run_dir):
    """Relative paths (sorted, `/` separated) of every file the manifest covers."""
    out = []
    for base, dirs, files in os.walk(run_dir):
        rel = os.path.relpath(base, run_dir)
        if rel == ".":
            dirs[:] = [d for d in dirs if d not in GENERATED_DIRS]
        for name in files:
            path = os.path.normpath(os.path.join(rel, name))
            if path == NAME or path in GENERATED_FILES or path in OPERATOR_FILES or name.endswith(".tmp"):
                continue
            out.append(path.replace(os.sep, "/"))
    return sorted(out)


def write(run_dir):
    """Seal the run directory: write MANIFEST.sha256. Returns the number of files sealed."""
    files = sealed_files(run_dir)
    with open(os.path.join(run_dir, NAME), "w", newline="\n") as f:
        for rel in files:
            f.write(f"{sha256_file(os.path.join(run_dir, rel))}  {rel}\n")
    return len(files)


def read(run_dir):
    """{relative path: sha256} from the manifest, or None when there is none."""
    path = os.path.join(run_dir, NAME)
    if not os.path.exists(path):
        return None
    out = {}
    with open(path) as f:
        for line in f:
            digest, _, rel = line.rstrip("\n").partition("  ")
            if len(digest) == 64 and rel:
                out[rel] = digest
    return out


def check(run_dir):
    """Problems (list of strings): no manifest, a sealed file that is missing or changed, a file that is not sealed."""
    want = read(run_dir)
    if want is None:
        return [f"{NAME} is missing: the run directory was never sealed (a session writes it when it finishes)"]
    problems = []
    for rel, digest in sorted(want.items()):
        path = os.path.join(run_dir, rel)
        if not os.path.isfile(path):
            problems.append(f"{rel} is listed in {NAME} but missing")
        elif sha256_file(path) != digest:
            problems.append(f"{rel} differs from {NAME}: it was changed after the run")
    for rel in sealed_files(run_dir):
        if rel not in want:
            problems.append(f"{rel} is not listed in {NAME}: it was added after the run")
    return problems


def digest(run_dir):
    """The sha256 of the manifest file itself: one hash that stands for the whole run directory."""
    path = os.path.join(run_dir, NAME)
    return sha256_file(path) if os.path.exists(path) else None
