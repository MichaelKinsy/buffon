# SPDX-License-Identifier: Apache-2.0
"""Where the host's CPU goes per turn in each extension realization: a CPU profile of the PiG process (PIG_PROFILE=cpu) over the ten-extension rpc scenario, split by call stack
into the extension boundary (`boundary_s`: samples under the subprocess host's dispatch or the extension SDK's own package) and the rest. The fused arm runs the SDK in the PiG
process, so its boundary also holds the extensions' own SDK work that the other arms spend in their extension processes.

`extensions/sdk/json` is PiG's general JSON package (session entries, agent messages, the RPC output use it too), so JSON is counted only under the boundary
(`share_of_host_cpu_by_part.json`); `json_outside_boundary` is the rest of the host's JSON, which no extension realization changes.

usage: python3 tools/boundary_profile.py --out DIR [--turns 40] [--arms pig-ts-node ...]

A diagnostic, not a measurement: it is not interleaved and has no A/A copy, and the profiler adds its own cost. Shares of one profile are stable; absolute milliseconds come from the
measured run. Needs BUFFON_SOURCE_REPO_PIG_TIP like any run, and writes profiles/<arm>.pprof plus boundary.json."""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buffon.arms import install, manifest  # noqa: E402
from buffon.mock import MockServer  # noqa: E402
from buffon.workloads import overhead  # noqa: E402

# The extension boundary: the subprocess host's dispatch and the extension SDK package (`extensions/sdk.`, not `extensions/sdk/json.`, which every JSON user in PiG calls).
BOUNDARY = r"coding/extension/host/subprocess\.|extensions/sdk\."
JSON = r"extensions/sdk/json\.|encoding/json\."
# The parts of the boundary, each counted only in samples under BOUNDARY (`-focus BOUNDARY -show PART`): the dispatch itself, the JSON it encodes and decodes, and the socket reads and
# writes. A fused arm has no socket, but it still runs the dispatch and the encoding (PiG builds each handler's payload as it would send it), which is why fusing does not remove the cost.
PARTS = {"dispatch": r"coding/extension/host/subprocess\.", "json": JSON, "socket": r"net\.\(\*(UnixConn|conn|netFD)\)|internal/poll\.\(\*FD\)\.(Read|Write)"}
# `Showing nodes accounting for A, P% of T total`: T is the whole profile even under -focus, so the focused CPU is A, with every node shown (no -nodecount or
# -nodefraction drop), not T.
ACCOUNTED = re.compile(r"Showing nodes accounting for ([0-9.]+)(ns|us|ms|s|mins|hrs)\b")
UNIT_S = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0, "mins": 60.0, "hrs": 3600.0}


def accounted_s(top_output):
    """The CPU seconds the shown nodes account for in `go tool pprof -top` output, or 0.0 when the line is missing."""
    m = ACCOUNTED.search(top_output)
    return float(m.group(1)) * UNIT_S[m.group(2)] if m else 0.0


def pprof_argv(go, binary, profile, focus=None, show=None, ignore=None):
    """`go tool pprof -top` with every node shown; `focus` keeps the samples with a matching frame, `ignore` drops them, `show` keeps only the matching frames of what is left (so
    `focus=A, show=B` is the CPU of samples that have both an A frame and a B frame)."""
    flags = [*(["-focus", focus] if focus else []), *(["-show", show] if show else []), *(["-ignore", ignore] if ignore else [])]
    return [os.path.join(go, "go"), "tool", "pprof", "-top", "-nodecount=1000000", "-nodefraction=0", "-edgefraction=0", *flags, binary, profile]


def pprof_total(go, binary, profile, focus=None, show=None, ignore=None):
    argv = pprof_argv(go, binary, profile, focus, show, ignore)
    done = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    return accounted_s(done.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--turns", type=int, default=40)
    ap.add_argument("--arms", nargs="*", default=["pig-ts-node", "pig-ts-bun", "pig-ts-aot", "pig-go-packed", "pig-go-isolated", "pig-go-fused"])
    ap.add_argument("--cache-dir", default=os.path.expanduser("~/.cache/buffon"))
    ap.add_argument("--work-dir", default=None)
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "profiles"), exist_ok=True)
    rows = {}
    with install.Workspace(install.Cache(args.cache_dir), work_dir=args.work_dir) as ws, MockServer() as server:
        go = ws.runtime("go")
        for name in args.arms:
            arm = manifest.load_arm(name)
            ws.install(arm)
            if arm.skip:
                print(f"{name}: {arm.skip}")
                continue

            class Opts:
                timeout, rpc_turns, long_turns = 300, args.turns, 1
                api = arm.apis[0]

            ctx = overhead.Ctx(ws.work, server, Opts)
            h = ctx.harness(arm, "rpc-ext10", extensions=overhead.sweep_extensions(ctx, arm, 10), compaction=None, context_window=128000)
            pdir = os.path.join(ws.root, "prof", name)
            os.makedirs(pdir)
            h.env.update(PIG_PROFILE="cpu", PIG_PROFILE_DIR=pdir)
            sample = overhead.RUNNERS["rpc-ext10"](ctx, arm)
            ctx.release()
            files = [f for f in os.listdir(pdir) if f.endswith(".pprof")]
            if "failure" in sample or not files:
                print(f"{name}: FAILED {sample.get('failure', 'no profile written')}")
                continue
            profile = os.path.join(pdir, files[0])
            dest = os.path.join(args.out, "profiles", f"{name}.pprof")
            with open(profile, "rb") as src, open(dest, "wb") as out:
                out.write(src.read())
            total, boundary = pprof_total(go, arm.binary, profile), pprof_total(go, arm.binary, profile, BOUNDARY)
            parts = {k: round(pprof_total(go, arm.binary, profile, BOUNDARY, show=rx) / total, 4) if total else None for k, rx in PARTS.items()}
            outside = pprof_total(go, arm.binary, profile, JSON, ignore=BOUNDARY)
            rows[name] = {"share_of_host_cpu_by_part": parts, "json_outside_boundary_share": round(outside / total, 4) if total else None, "profile_s": round(total, 3), "boundary_s": round(boundary, 3), "boundary_share_of_host_cpu": round(boundary / total, 4) if total else None,
                          "turn_host_cpu_ms": sample.get("turn_host_cpu_ms"), "turn_extension_cpu_ms": sample.get("turn_extension_cpu_ms"), "turns": args.turns}
            print(name, rows[name], flush=True)
    with open(os.path.join(args.out, "boundary.json"), "w") as f:
        json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
