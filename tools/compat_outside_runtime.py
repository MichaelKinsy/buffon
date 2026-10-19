# SPDX-License-Identifier: Apache-2.0
"""Compatibility row: Pi-valid code that runs outside the extension process (rev-issues-verify's programs B2 and B3, fixtures/outside-runtime-probe).

The probe extension starts three children, a detached `node` process, a `child_process.fork` child and a `worker_threads` worker, each of which imports Pi's packages from the host package
root (the layout pi-subagents' background runner resolves) and calls a builtin pi-ai API against a local OpenAI-compatible server. Pi answers `pong` from all three and resolves 192 of the 196
published subpaths from the detached child. PiG must answer `pong` from all three, and the subpaths it does not yet resolve must be exactly KNOWN_GAPS; any other failing subpath, or a
subpath that stops failing without leaving the list, is a difference.

usage: python3 tools/compat_outside_runtime.py --impl NAME=BINARY ... (the first is the oracle)"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import compat_fff as c  # noqa: E402

PROBE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "outside-runtime-probe", "probe-ext.mjs")
# Subpaths a detached child resolves under Pi and not under PiG (the harness peers cover the rest). Each is a package PiG does not ship or a module the vendored runtime does not include.
KNOWN_GAPS = sorted([
    "@earendil-works/pi-coding-agent/rpc-entry", "@earendil-works/chord/bundler", "@earendil-works/chord/node", "@earendil-works/pi-ai/api/google-shared",
    "@earendil-works/pi-mcp/testing", "@earendil-works/pi-telemetry", "@earendil-works/pi-telemetry/testing",
    "typebox/error", "typebox/format", "typebox/guard", "typebox/schema", "typebox/system", "typebox/type",
])


def run_one(binary, timeout=150):
    c.make_project()
    c.write_config("http://127.0.0.1:9/v1")   # the probe talks to its own server; the harness's model is never called
    out = f"{c.ROOT}/probe-out"
    subprocess.run(["rm", "-rf", out])
    os.makedirs(out)
    env = c.env_for(binary, [f"PROBE_DIR={out}"])
    rpc = c.Rpc([binary, "--mode", "rpc", "--no-session", "-e", PROBE], env, c.PROJECT)
    try:
        rpc.call({"type": "get_state"}, 120)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not os.path.exists(f"{out}/ext.json"):
            time.sleep(0.5)
    finally:
        rpc.close()
    rec = {}
    for mode in ("spawn-detached", "fork", "worker"):
        try:
            child = json.load(open(f"{out}/child-{mode}.json"))
        except (OSError, ValueError):
            rec[mode] = {"failure": "no result"}
            continue
        rec[mode] = {"aiCall": child.get("aiCall"), "workerError": child.get("workerError")}
        if mode == "spawn-detached":
            host = child.get("host") or {}
            rec["detached_unresolved"] = sorted(s for s, v in host.items() if not v.get("ok"))
            rec["detached_specifiers"] = len(host)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", action="append", required=True)
    args = ap.parse_args()
    impls = [i.split("=", 1) for i in args.impl]
    recs = {name: run_one(binary) for name, binary in impls}
    failed = False
    for name, rec in recs.items():
        pong = {m: (rec[m].get("aiCall") or {}).get("text") for m in ("spawn-detached", "fork", "worker")}
        print(f"{name:14s} pong {pong}  detached: {rec['detached_specifiers'] - len(rec['detached_unresolved'])}/{rec['detached_specifiers']} resolve")
    oracle_name = impls[0][0]
    oracle = recs[oracle_name]
    for name, rec in recs.items():
        for mode in ("spawn-detached", "fork", "worker"):
            if rec[mode] != oracle[mode]:
                failed = True
                print(f"  {name} {mode}: {json.dumps(rec[mode])[:200]} != {oracle_name} {json.dumps(oracle[mode])[:200]}")
        if name == oracle_name:
            continue
        gaps = sorted(set(rec["detached_unresolved"]) - set(oracle["detached_unresolved"]))
        if gaps != KNOWN_GAPS:
            failed = True
            print(f"  {name}: unresolved subpaths differ from the known gaps: extra {sorted(set(gaps) - set(KNOWN_GAPS))}, now resolving {sorted(set(KNOWN_GAPS) - set(gaps))}")
    print("EQUIVALENT (known gaps listed in KNOWN_GAPS)" if not failed else "DIFFERENCES")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
