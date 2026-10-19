# SPDX-License-Identifier: Apache-2.0
"""Piglet arms: a Piglet Binary built from a Piglet manifest at a pinned Pigpen commit, with `pig piglet build`.

An arm's `[piglet]` table names the Pigpen commit, the manifest inside it (with its sha256) and the identity that the build record must show: the Piglet's name, its
release version and the source, effective and component-plan digests PiG computes from the manifest. A build whose manifest bytes or identity differ from the pinned
values is refused. Nothing here reads the machine the runner is on, and the Pigpen checkout comes from the environment variable the arm names (a local clone or a URL).
"""
import json
import os
import re
import subprocess

from . import manifest
from .install import InstallError, run
from .prepare_pig import go_env, piglet_record, source_dir, strip_of, yaml_slots

# Pinned identity. The resolution, graph, closure and artifact digests change between builds of one commit and manifest: the Binary embeds its resolution
# record, whose createdAt is the build's wall-clock time and is covered by the resolution digest. They are recorded in identity_from_record but not compared.
IDENTITY_KEYS = ("name", "release_version", "component_plan_digest")
# The PiG target of each platform the manifests name. The native builder builds only the host target, so an arm builds the one target of its own platform.
TARGET_OF_PLATFORM = {"linux-x64": "linux/amd64", "linux-arm64": "linux/arm64", "darwin-x64": "darwin/amd64", "darwin-arm64": "darwin/arm64"}


class PigletIdentityError(InstallError):
    """The build record does not show the identity the arm pins: the manifest, the source or PiG changed since the pin."""


def identity_from_record(record):
    """The identity fields of a Piglet Binary record (`pig piglet show --record <path> --json`). The record's own `digest` covers createdAt, so the
    identity is the binary payload's digests. A missing field is an error, not an empty value."""
    try:
        binary = record["binary"]
        identity = {
            "name": record["piglet"],
            "release_version": record["releaseVersion"],
            "component_plan_digest": binary["componentPlanDigest"],
            "resolution_digest": binary["resolutionDigest"],
            "graph_digest": binary["graphDigest"],
            "resource_closure_digest": binary["resourceClosureDigest"],
            "artifact_digest": binary["artifact"]["digest"],
        }
    except (KeyError, TypeError) as error:
        raise PigletIdentityError(f"the Piglet Binary record lacks {error}: PiG's record format is not the one this arm reads") from error
    return {k: (v.removeprefix("sha256:") if k.endswith("_digest") else v) for k, v in identity.items()}


def check_identity(pinned, actual):
    """Refuse when any pinned identity field differs from the build's. Returns the identity on success."""
    drift = [f"{k}: pinned {pinned[k]!r}, built {actual.get(k)!r}" for k in IDENTITY_KEYS if pinned.get(k) != actual.get(k)]
    if drift:
        raise PigletIdentityError("the Piglet identity drifted from its pin (refused): " + "; ".join(drift))
    return dict(actual)


def stage_piglets(ws, arm, pigpen, spec):
    """Stage the Pigpen commit the way its own `npm run stage` does (scripts/stage-piglets.mjs): each Piglet and the Packages it names are copied under
    dist/staged, so the `local:` paths resolve inside the staged Piglet. The staging script imports `yaml`, a Pigpen devDependency: `npm ci` installs the
    commit's own package-lock.json (versions and integrity pinned by the commit), with the workspace's npm cache, as the installer's npm arms do.
    Returns the staged manifest path."""
    node_dir = ws.runtime("node")
    env = ws.base_env(["node"])
    env.update(npm_config_cache=ws.npm_cache or os.path.join(ws.root, "npm-cache"), npm_config_update_notifier="false", npm_config_fund="false",
               npm_config_audit="false")
    if not os.path.isfile(os.path.join(pigpen, "package-lock.json")):
        raise InstallError(f"{arm.id}: the Pigpen commit {spec['pigpen_commit']} has no package-lock.json to install its staging dependencies from")
    run([os.path.join(node_dir, "npm"), "ci", "--ignore-scripts"], cwd=pigpen, env=env, timeout=1200)
    run([os.path.join(node_dir, "node"), os.path.join("scripts", "stage-piglets.mjs"), pigpen], cwd=pigpen, env=env, timeout=600)
    staged = os.path.join(pigpen, "dist", "staged", "piglets", spec["name"], os.path.basename(spec["manifest"]))
    if not os.path.isfile(staged):
        raise InstallError(f"{arm.id}: staging did not produce {staged}")
    return staged


def record_path_from(stdout):
    """The Piglet Binary record of a `pig piglet build --json` result. PiG prints the record path in the JSON result only; without it there is no identity to check."""
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise InstallError(f"pig piglet build --json printed no JSON result: {error}") from error
    if not result.get("success") or not result.get("record"):
        raise InstallError(f"pig piglet build reported no record: {result.get('error') or result}")
    return result["record"]


def build_output(argv, cwd, env):
    """Run a PiG build with --json and return its stdout (the JSON result). Progress goes to stderr; a failed build raises with its tail."""
    done = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=3600)
    if done.returncode:
        raise InstallError(f"{' '.join(argv)} failed:\n{(done.stdout + done.stderr)[-2000:]}")
    return done.stdout


def piglet_spec(arm):
    """The validated [piglet] table of an arm (manifest.validate has checked its shape)."""
    spec = arm.spec.get("piglet")
    if not spec:
        raise InstallError(f"{arm.id}: no [piglet] table")
    return spec


def pigpen_checkout(ws, arm, spec):
    """A checkout of the Pigpen commit the arm names, verified by its HEAD sha. The source is the environment variable's value: a local clone or a URL."""
    source = os.environ.get(spec["repo_env"], "")
    if not source:
        raise InstallError(f"{arm.id}: set {spec['repo_env']} to a Pigpen clone (or URL) that contains {spec['pigpen_commit']}")
    dest = os.path.join(ws.root, "pigpen", spec["pigpen_commit"])
    if not os.path.isdir(dest):
        run(["git", "clone", "--quiet", "--no-checkout", source, dest], timeout=1800)
        run(["git", "checkout", "--quiet", "--detach", spec["pigpen_commit"]], cwd=dest)
    head = run(["git", "rev-parse", "HEAD"], cwd=dest).strip()
    if head != spec["pigpen_commit"]:
        raise InstallError(f"{arm.id}: the Pigpen checkout is at {head}, the arm pins {spec['pigpen_commit']}")
    return dest


def build_piglet(ws, arm, base):
    """Build the arm's Piglet Binary with the base arm's pig executable, from the base's source checkout and the pinned Pigpen manifest; refuse any identity drift.
    On success the arm's executable is the built Piglet Binary and its record (identity, slots, strip) is in arm.record."""
    spec = piglet_spec(arm)
    src = source_dir(ws, base)
    if not os.path.isdir(src):
        raise InstallError(f"{arm.id}: the base arm {base.id} left no source checkout to build the Piglet from")
    pigpen = pigpen_checkout(ws, arm, spec)
    source_yaml = os.path.join(pigpen, spec["manifest"])
    if not os.path.isfile(source_yaml):
        raise InstallError(f"{arm.id}: {spec['manifest']} is not in the Pigpen commit {spec['pigpen_commit']}")
    digest = manifest.sha256_file(source_yaml)
    if digest != spec["manifest_sha256"]:
        raise PigletIdentityError(f"{arm.id}: {spec['manifest']} has sha256 {digest}, the arm pins {spec['manifest_sha256']} (refused)")
    yaml_path = stage_piglets(ws, arm, pigpen, spec)
    target = TARGET_OF_PLATFORM.get(ws.platform)
    if target is None:
        raise InstallError(f"{arm.id}: no PiG build target for platform {ws.platform!r}")
    out_dir = os.path.join(arm.install_dir, "bin")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"pig-piglet-{spec['name']}")
    env = go_env(ws, arm)
    env.update(PIG_SOURCE_ROOT=src)
    argv = [arm.binary, "piglet", "build", yaml_path, "--format", "binary", "--targets", target, "--out", out, "--json"]
    record_path = record_path_from(build_output(argv, cwd=src, env=env))
    shown = run([arm.binary, "piglet", "show", "--record", record_path, "--json"], cwd=src, env=env, timeout=300)
    try:
        record = json.loads(shown)
    except json.JSONDecodeError as error:
        raise PigletIdentityError(f"{arm.id}: pig piglet show --record printed no JSON record: {error}") from error
    actual = check_identity(spec["identity"] | {"name": spec["name"], "release_version": spec["release_version"]}, identity_from_record(record))
    arm.binary = out
    # piglet_record writes the report's view (label, slots, strip, size) into record["piglet"]; the identity is added to it, never replaced by it.
    piglet_record(arm, yaml_slots(yaml_path), strip=strip_of(yaml_path))
    arm.record["piglet"].update(name=spec["name"], pigpen_commit=spec["pigpen_commit"], manifest=spec["manifest"], manifest_sha256=digest, target=target, identity=actual)
    arm.record.update(
        piglet_binary_sha256=manifest.sha256_file(out),
        piglet_build=" ".join(argv[1:]).replace(arm.install_dir, "<install>").replace(pigpen, "<pigpen>"),
    )

