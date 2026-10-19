# SPDX-License-Identifier: Apache-2.0
"""Developer-loop workloads: what a person pays to get an arm and to start it for the first time. Each is N/A (a Skip with the reason) where an arm has no such step.

devloop/install    clean-host install time: a fresh workspace installs the arm from the verified cache (artifact unpack, npm ci from the cache); source-built arms are `devloop/build`
devloop/build      build time of a source-built arm (go build at the pinned commit with the pinned toolchain)
devloop/first-run  the first print run on a fresh HOME with no first-start seed: what a new user's first minute costs (an arm whose manifest seeds its first start, omp, shows the cost the seed hides)

Binary and install size on disk are in every report's arm table (`footprint`); they are properties of the install, not samples. Extension edit -> reload latency and the Piglet and AOT
build times need the extension-realization arms' own builders (arms pig-go-*, pig-ts-aot) and are not measured here."""
import copy
import os
import shutil
import time

from ..arms import install
from . import Workload, register
from .overhead import Skip, check_print, metrics_of, PROMPT, cgroup, procio, skip_unless


def _fresh_install(ctx, arm, want_source):
    is_source = arm.install_kind == "source"
    if arm.install_kind is None:
        raise Skip("it has no install step")
    if want_source != is_source:
        raise Skip("it is built from source: see devloop/build" if is_source else "it is not built from source: see devloop/install")
    opts = ctx.opts
    twin = copy.copy(arm)
    twin.binary = twin.install_dir = twin.record = twin.skip = twin.seed_dir = None
    t0 = time.monotonic()
    with install.Workspace(install.Cache(getattr(opts, "cache_dir", None), offline=getattr(opts, "offline", False)), work_dir=ctx.work) as ws:
        ws.install(twin, source_repos=getattr(opts, "source_repos", None) or {})
        if twin.skip:
            raise Skip(twin.skip)
        wall = (time.monotonic() - t0) * 1000
        size = ws.footprint(twin) or {}
    return {"wall_ms": round(wall, 1), "install_mb": round((size.get("bytes") or 0) / 1e6, 2), "runtime_mb": round((size.get("runtime_bytes") or 0) / 1e6, 2)}


def one_install(ctx, arm):
    return _fresh_install(ctx, arm, want_source=False)


def one_build(ctx, arm):
    return _fresh_install(ctx, arm, want_source=True)


def one_first_run(ctx, arm):
    skip_unless(ctx, arm, "print")
    seed, arm.seed_dir = getattr(arm, "seed_dir", None), None   # a fresh home: whatever first-start state the manifest seeds is exactly what this measures
    try:
        h = ctx.harness(arm, "first-run")
    finally:
        arm.seed_dir = seed
    srv = ctx.server
    srv.reset(policy=ctx.policy(arm, 0, "first-run"))
    meter = cgroup.new_meter()
    try:
        res = procio.Batch(h.print_argv(PROMPT), h.env, h.cwd, meter, max(ctx.opts.timeout, 120)).run()
    finally:
        meter.close()
    bad = check_print(res, srv, 1, arm)
    if bad:
        return {"failure": bad}
    sample = metrics_of(res)
    sample["home_mb"] = round(sum(os.path.getsize(os.path.join(d, f)) for d, _, files in os.walk(h.home) for f in files if os.path.isfile(os.path.join(d, f))) / 1e6, 2)
    return sample


for _id, _fn, _desc in (("install", one_install, "clean-host install time from the verified cache (artifact and npm arms)"),
                        ("build", one_build, "build time of a source-built arm at its pinned commit"),
                        ("first-run", one_first_run, "first print run on a fresh HOME with no first-start seed")):
    register(Workload(id=f"devloop/{_id}", family="devloop", fn=_fn, apis=(None,) if _id != "first-run" else ("openai-completions",), description=_desc))
