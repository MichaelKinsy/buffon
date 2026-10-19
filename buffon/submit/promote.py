# SPDX-License-Identifier: Apache-2.0
"""`buffon promote`: the step CI takes after it has re-validated a submission (docs/SUBMITTING.md, "Trust tiers").

It verifies the run directory as a submission, then writes promotion.json next to the sealed files: the manifest digest it verified, the run-notes count it recomputed, the thresholds'
sha256 and who ran the check. With `--to RESULTS` it first copies the sealed files into a buffon-owned results directory under a new id (an existing id is never replaced), so the
record cannot be edited or deleted later by the submitter. Files are made read-only. The index recognises a run as CI-revalidated only while promotion.json still names the
manifest digest the directory has."""
import json
import os
import shutil
import stat

from ..report import render
from . import check as checklib, manifest

NAME = "promotion.json"


class PromotionRefused(Exception):
    pass


def ci_identity(environ=None):
    """Who ran the check: the CI run's identifiers when there are any, else the word `local`."""
    environ = os.environ if environ is None else environ
    keys = ("GITHUB_REPOSITORY", "GITHUB_WORKFLOW", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_REF")
    found = {k.lower().replace("github_", ""): environ[k] for k in keys if environ.get(k)}
    return found or {"runner": "local"}


def read(run_dir):
    path = os.path.join(run_dir, NAME)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def current(run_dir):
    """The promotion record when it still describes this directory (the manifest digest matches), else None."""
    rec = read(run_dir)
    return rec if rec and rec.get("manifest_sha256") == manifest.digest(run_dir) else None


def make_read_only(path):
    for base, dirs, files in os.walk(path):
        for name in files:
            os.chmod(os.path.join(base, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        for name in dirs:
            os.chmod(os.path.join(base, name), stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def copy_sealed(run_dir, dest):
    """Copy the sealed files and submission.toml (nothing a report generated) to a new directory."""
    os.makedirs(dest)
    for rel in manifest.sealed_files(run_dir) + [manifest.NAME, "submission.toml"]:
        src = os.path.join(run_dir, rel)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(os.path.join(dest, rel)), exist_ok=True)
            shutil.copyfile(src, os.path.join(dest, rel))


def promote(run_dir, repo, to=None, run_id=None, environ=None):
    """Verify `run_dir` as a submission and write promotion.json; returns (directory, record). Raises PromotionRefused when it does not verify or the id is taken."""
    result = checklib.verify(run_dir, repo, is_submission=True)
    if not result.accepted:
        raise PromotionRefused(checklib.text(result, run_dir))
    target = run_dir
    if to:
        target = os.path.join(to, run_id or os.path.basename(os.path.normpath(run_dir)))
        if os.path.exists(target):
            raise PromotionRefused(f"{target} already exists: a published run is never replaced (withdraw it in WITHDRAWN.toml and submit a new one)")
        copy_sealed(run_dir, target)
        again = checklib.verify(target, repo, is_submission=True)
        if not again.accepted:
            raise PromotionRefused("the copy does not verify: " + checklib.text(again, target))
    record = {"id": os.path.basename(os.path.normpath(target)), "manifest_sha256": manifest.digest(target), "notes": result.health["notes"], "thresholds_sha256": result.health["thresholds_sha256"],
              "checks": [c["id"] for c in result.checks if c["status"] == "ok"], "ci": ci_identity(environ)}
    if os.path.exists(os.path.join(target, NAME)):
        os.chmod(os.path.join(target, NAME), stat.S_IRUSR | stat.S_IWUSR)
    with open(os.path.join(target, NAME), "w") as f:
        json.dump(record, f, indent=1, sort_keys=True)
        f.write("\n")
    render.render([target], target)           # the report the index links to, regenerated from the sealed data
    make_read_only(target)
    return target, record
