# SPDX-License-Identifier: Apache-2.0
"""Install steps of the PiG extension-matrix arms (arms/pig-*/prepare.py call these): a Bun runtime slot, a warm extension cache, a Piglet Binary with the extensions fused in.

Every step writes only under the arm's install directory, so the A/A copy of an arm gets its own copy of the result and the tree digest covers it.
"""
import json
import os
import re
import shutil
import subprocess
import time

from . import manifest
from .install import InstallError, run

# The state PiG keeps under PIG_HOME that makes a second start cheaper than the first: compiled extension cells (cache) and the staged SDK (state).
WARM_DIRS = ("cache", "state")


PIGLET_LABEL = "base Piglet + slots, one binary"


def yaml_slots(path):
    """The slot names a Piglet YAML declares: `- name: x` under `extensions:`, and the strip lists. A line scan, not a YAML parser: these files are flat by construction."""
    slots, section = [], None
    with open(path) as f:
        for line in f:
            if re.match(r"^\S", line):
                section = line.split(":")[0].strip()
            m = re.match(r"^\s+-\s+name:\s*(\S+)", line)
            if m and section == "extensions":
                slots.append(m.group(1))
    return slots


def piglet_record(arm, slots, binary=None, strip=None, runtime_slot=None):
    """What a report says about a Piglet arm: it is a base Piglet plus slots in one binary; the slot list and the binary's size (the sum of the install tree when there is no single binary)."""
    size = os.path.getsize(binary or arm.binary)
    arm.record["piglet"] = {"label": PIGLET_LABEL, "slots": list(slots), "strip": strip or None, "runtime_slot": runtime_slot, "binary_bytes": size}


def repo_root():
    return manifest.ROOT


def go_env(ws, arm):
    """The environment a toolchain step of a PiG arm runs in: the pinned Go on PATH, the module cache and build cache of the throwaway HOME."""
    env = ws.plain_env(arm)
    env["PATH"] = os.pathsep.join([ws.runtime("go"), *arm.path_dirs, "/usr/bin", "/bin"])
    env.update(GOTOOLCHAIN="local", GOFLAGS="-trimpath -modcacherw", CGO_ENABLED="0")
    cache = os.path.join(ws.root, "go-cache", arm.id)
    os.makedirs(cache, exist_ok=True)
    env.update(GOCACHE=os.path.join(cache, "build"), GOMODCACHE=os.path.join(cache, "mod"))
    return env


def source_dir(ws, base):
    return os.path.join(ws.root, "src", base.id)


def bun_slot(ws, arm, expect_sha256):
    """A runtime slot holding stock Bun, as the Bun Piglet writes it (docs/site/docs/typescript-runtimes.md): <install>/slot/bun/{bun,runtime.json}. PiG runs a Bun
    executable only when its sha256 is in its runtime lock, so the pinned archive's executable is compared with `expect_sha256` first."""
    bindir = ws.runtime("bun")
    exe = os.path.join(bindir, "bun")
    digest = manifest.sha256_file(exe)
    if digest != expect_sha256:
        raise InstallError(f"{arm.id}: the pinned Bun executable has sha256 {digest}, PiG's runtime lock lists {expect_sha256}")
    version = ws.runtimes["bun"]["version"]
    slot = os.path.join(arm.install_dir, "slot", "bun")
    os.makedirs(slot, exist_ok=True)
    shutil.copy2(exe, os.path.join(slot, "bun"))
    with open(os.path.join(slot, "runtime.json"), "w") as f:
        json.dump({"id": "bun", "kind": "bun", "version": version, "platform": ws.platform, "provider": "buffon", "image": {"executable": "bun", "sha256": digest}}, f)
    arm.record.update(ts_runtime="bun", bun_version=version, bun_executable_sha256=digest)
    piglet_record(arm, [], binary=arm.binary, runtime_slot=f"bun {version} (slot/bun)")


def warm_cache(ws, arm, scenario="rpc-ext10", extra_path=()):
    """Start the arm once with its extension set so PiG builds and caches what the set needs, then keep the cache under <install>/warm (laid into every sample's HOME by the
    harness). The arm's ready time is then a warm start: a first start compiles Go cells and materializes the Node runtime, which a user pays once."""
    from ..mock import MockServer
    from ..workloads import overhead

    class Opts:
        timeout, rpc_turns, long_turns = 600, 1, 1
        api = arm.apis[0]

    saved = list(arm.path_dirs)
    arm.path_dirs = [*arm.path_dirs, *extra_path]
    started = time.monotonic()
    try:
        with MockServer() as server:
            ctx = overhead.Ctx(ws.work, server, Opts)
            sample = overhead.RUNNERS[scenario](ctx, arm)
            if "failure" in sample:
                raise InstallError(f"{arm.id}: the warm-up start failed: {sample['failure']}")
            pig_home = ctx.harnesses_for(arm)[0].pig_home
            warm = os.path.join(arm.install_dir, "warm")
            for rel in WARM_DIRS:
                src = os.path.join(pig_home, rel)
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(warm, rel), symlinks=True, dirs_exist_ok=True)
            ctx.release()
    finally:
        arm.path_dirs = saved
    arm.record.update(warm_start_s=round(time.monotonic() - started, 1))


def strip_of(path):
    """The strip block of a Piglet YAML as text (keep or deny mode), or None."""
    with open(path) as f:
        text = f.read()
    m = re.search(r"^strip:\n((?:[ \t]+.*\n?)+)", text, re.M)
    return " ".join(m.group(1).split()) if m else None


def fused_binary(ws, arm, base, piglet_yaml):
    """`pig piglet build --format binary` of the Piglet at `piglet_yaml`, built by the base arm's own executable against the base arm's source checkout with the pinned Go.
    The result replaces the arm's executable; the base's core and the fused extensions are one program."""
    src = source_dir(ws, base)
    if not os.path.isdir(src):
        raise InstallError(f"{arm.id}: the base arm {base.id} left no source checkout to build the Piglet from")
    out_dir = os.path.join(arm.install_dir, "bin")
    out = os.path.join(out_dir, "pig-fused")
    env = go_env(ws, arm)
    env.update(PIG_SOURCE_ROOT=src)
    argv = [arm.binary, "piglet", "build", piglet_yaml, "--format", "binary", "--out", out]
    run(argv, cwd=src, env=env, timeout=3600)
    arm.record.update(piglet_yaml_sha256=manifest.sha256_file(piglet_yaml), fused_binary_sha256=manifest.sha256_file(out), fused_build=" ".join(argv[1:]).replace(arm.install_dir, "<install>"))
    arm.binary = out
    piglet_record(arm, yaml_slots(piglet_yaml), strip=strip_of(piglet_yaml))


def aot_slot(ws, arm, base, bun_sha256):
    """The runtime slot of the compiled TypeScript host (PIG_TS_RUNTIME=aot), built the way the aot Piglet builds it for a user: the Piglet's worker (`go test` of
    piglets/aot/extensions/aotruntime, TestBuildSlotRequests) installs the runtime manifest and the verified compiler, a first start records a build request for the arm's
    extension set (and runs on Bun meanwhile), the worker builds the image, and a second start must run on the compiled host. Bun is in the slot as the fallback.
    The compiler downloads at install time only (the aot Piglet's own pinned release); no sample touches the network."""
    bun_slot(ws, arm, bun_sha256)
    src = source_dir(ws, base)
    worker_dir = os.path.join(src, "piglets", "aot")
    if not os.path.isdir(worker_dir):
        raise InstallError(f"{arm.id}: the base arm's checkout has no piglets/aot")
    slot = os.path.join(arm.install_dir, "slot")
    env = go_env(ws, arm)
    env.update(GOWORK="off", PIG_AOT_BUILD_SLOT=slot, PIG_TS_RUNTIMES_DIR=slot, PIG_AOT_VERBOSE="1")
    for key in ("PIG_TS_RUNTIME", "PIG_OFFLINE", "PI_OFFLINE"):   # the install step downloads the compiler; the arm's samples stay offline
        env.pop(key, None)
    argv = [os.path.join(ws.runtime("go"), "go"), "test", "./extensions/aotruntime", "-run", "TestBuildSlotRequests", "-count=1", "-v", "-timeout", "40m"]
    started = time.monotonic()
    run(argv, cwd=worker_dir, env=env, timeout=3000)        # the manifest and the compiler
    declared = arm.extension_spec
    arm.extension_spec = {k: v for k, v in declared.items() if k != "host"}   # until the image exists the set runs on the fallback runtime, which is the point of this start
    try:
        warm_cache(ws, arm)                                 # a start on Bun that records the build request
    finally:
        arm.extension_spec = declared
    # The request names the runtime tree PiG materialized under PIG_HOME/cache; the worker stages the image from it, so it must exist while the worker runs.
    pig_home = os.path.join(arm.vars["shared_dir"], "pig-home")
    shutil.rmtree(pig_home, ignore_errors=True)
    shutil.copytree(os.path.join(arm.install_dir, "warm"), pig_home, symlinks=True)
    run(argv, cwd=worker_dir, env=env, timeout=3000)        # the image
    shutil.rmtree(pig_home, ignore_errors=True)
    shutil.rmtree(os.path.join(arm.install_dir, "warm"), ignore_errors=True)
    warm_cache(ws, arm)                                     # the start that must run on the compiled host, and the cache every sample starts from
    arm.record.update(ts_runtime="aot", aot_build_s=round(time.monotonic() - started, 1))
    piglet_record(arm, ["aotruntime (compiled TypeScript host)"], binary=arm.binary, runtime_slot="aot image + bun fallback (slot/)")
    manifest_path = os.path.join(slot, "aot", "runtime.json")
    if os.path.exists(manifest_path):
        arm.record["aot_runtime_json_sha256"] = manifest.sha256_file(manifest_path)


def patched_build(ws, arm, base, patch_path):
    """A diagnostic build of the base arm's checkout with one patch applied (arms that are not a configuration a user can select). The checkout is copied, patched with `patch -p1`
    and built with the base manifest's build command; the patch file's sha256 and the built executable's go in the arm's record."""
    src = source_dir(ws, base)
    work = os.path.join(ws.root, "src", arm.id)
    run(["git", "clone", "--quiet", src, work])
    run(["git", "checkout", "--quiet", "--detach", base.record["commit"]], cwd=work)
    run(["patch", "-p1", "--no-backup-if-mismatch", "-i", patch_path], cwd=work)
    s = base.spec["source"]
    out = os.path.join(arm.install_dir, "bin", "pig-patched")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    env = go_env(ws, arm)
    env.update(s.get("env", {}))
    argv = [a.replace("{out}", out).replace("{package}", s["package"]) for a in s["build"]]
    run(argv, cwd=work, env=env, timeout=3600)
    arm.binary = out
    arm.record.update(diagnostic_patch=os.path.basename(patch_path), diagnostic_patch_sha256=manifest.sha256_file(patch_path), patched_executable_sha256=manifest.sha256_file(out))
