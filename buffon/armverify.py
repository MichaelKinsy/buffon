# SPDX-License-Identifier: Apache-2.0
"""`buffon arm verify <name>`: install the arm into a fresh root, check every checksum, write its config, start it against the mock, run one turn in each mode its
manifest declares, and fail if it connects anywhere but the mock (CONTRIBUTING.md).

Its own module: `buffon verify <run dir>` (verify.py) checks a run directory; the arm check lived in verify.py until that file was replaced, and `buffon arm verify`
then failed with an AttributeError."""
import sys

from . import site as sitelib
from .arms import install, manifest
from .mock import MockServer


def arm_verify(args):
    from .runner import egress
    from .workloads import overhead
    s = sitelib.load(args.site)
    arms = manifest.load_all()
    from .cli import resolve_arm_names
    args.name = resolve_arm_names([args.name], arms)[0]   # a short name (pi, pig) is accepted; an unknown one is refused with the nearest ids (exit 2)
    arm = arms[args.name]
    if arm.held:
        print(f"buffon: {arm.id} is held and never runs: {arm.held}", file=sys.stderr)
        return 3
    problems = []
    egress.take()
    with install.Workspace(install.Cache(s.local.cache_dir), work_dir=s.local.work_dir) as ws, MockServer() as server:
        ws.install(arm)
        if arm.skip:
            print(f"buffon: {arm.id} cannot run here: {arm.skip}", file=sys.stderr)
            return 3
        print(f"installed {arm.id}: {arm.version_line}")

        class Opts:
            timeout, rpc_turns, long_turns, api = 120, 2, 20, arm.apis[0]

        ctx = overhead.Ctx(ws.work, server, Opts)
        for api in arm.apis:
            Opts.api = api
            for scenario in ("version", "print", "rpc", "pty"):
                if scenario == "version" and api != arm.apis[0]:
                    continue
                try:
                    sample = overhead.RUNNERS[scenario](ctx, arm)
                except overhead.Skip as why:
                    print(f"  {scenario:8} {api:20} cannot run: {why}")
                    continue
                finally:
                    ctx.release()
                left = sorted(egress.take())
                bad = sample.get("failure") or (f"egress to {', '.join(left)}" if left else None)
                print(f"  {scenario:8} {api:20} {'FAILED: ' + bad if bad else 'ok'}")
                if bad:
                    problems.append(f"{api} {scenario}: {bad}")
    return 1 if problems else 0
