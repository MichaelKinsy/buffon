# SPDX-License-Identifier: Apache-2.0
"""Compatibility row: nicobailon/pi-subagents (frozen: fixtures/external/pi-subagents) on Pi and on PiG.

An agent file with `async: true` (a background agent) and one run with `async: false` (foreground) are each called by the scripted model through the `subagent` tool. The background
agent runs in a detached Node process that imports Pi's packages and calls the model from there; the foreground agent runs in the extension process. Each (implementation, agent) records the
tool result the parent gets, the completion message that wakes the parent, how many model requests the parent and the child made, and the run's terminal status. The first implementation is the
oracle; any other whose record differs is reported. Hermetic like tools/compat_fff.py (fixed home, agent dir and project, Buffon's scripted mock model).

usage: python3 tools/compat_subagents.py --impl NAME=BINARY ... [--cache DIR] [--out DIR]"""
import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buffon.mock import MockServer, Step  # noqa: E402
from tools import compat_fff as c  # noqa: E402
from tools import external_ext  # noqa: E402

AGENT = """---
name: {name}
description: test agent
{extra}systemPromptMode: replace
---

Reply with the single word DONE.
"""
SCENARIOS = {"background": ("bg", {}), "foreground": ("fg", {"async": False})}


def scrub(text):
    text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>", text)
    text = re.sub(r"/tmp/\S+", "<path>", text)
    return re.sub(r"call_\d+_\d+", "<call>", text)


def policy_for(agent, extra):
    state = {"called": False}

    def policy(request):
        if "subagent" in (request.tools or []):
            if not state["called"]:
                state["called"] = True
                return Step(tool_calls=[("subagent", {"agent": agent, "task": "say DONE", **extra})])
            return Step(text="parent finished")
        return Step(text="DONE")
    return policy


def record_one(binary, ext_dir, scenario, timeout=120):
    agent, extra = SCENARIOS[scenario]
    c.make_project()
    with MockServer(policy=policy_for(agent, extra)) as server:
        c.write_config(server.base_url)
        os.makedirs(f"{c.AGENT}/agents", exist_ok=True)
        open(f"{c.AGENT}/agents/fg.md", "w").write(AGENT.format(name="fg", extra=""))
        open(f"{c.AGENT}/agents/bg.md", "w").write(AGENT.format(name="bg", extra="async: true\n"))
        argv = [binary, "--mode", "rpc", "--provider", "bench", "--model", "bench-1", "--no-session", "-e", f"{ext_dir}/node_modules/pi-subagents/index.js"]
        rpc = c.Rpc(argv, c.env_for(binary), c.PROJECT)
        out = {}
        try:
            rpc.call({"type": "get_state"}, 120)
            time.sleep(3)
            start = len(rpc.records)
            rpc.send({"type": "prompt", "message": "Delegate."})
            if rpc.wait(lambda r: r.get("type") == "agent_end", timeout, start) is None:
                return {"failure": "no agent_end", "stderr": rpc.close()[-600:]}
            # a background run reports back by waking the parent: wait for that completion message, then for the parent's reply to it
            deadline = time.monotonic() + timeout

            def messages():
                return [r["message"] for r in rpc.records[start:] if r.get("type") == "message_end" and r.get("message", {}).get("role") in ("user", "custom")]
            while scenario == "background" and time.monotonic() < deadline and not any("Background task" in str(m.get("content")) for m in messages()):
                time.sleep(0.3)
            time.sleep(2)
            out["tool_results"] = [scrub(r["result"]["content"][0]["text"]) for r in rpc.records[start:] if r.get("type") == "tool_execution_end"]
            out["wake_messages"] = [scrub(str(m.get("content"))[:400]) for m in messages() if "Background task" in str(m.get("content"))]
            out["parent_requests"] = sum(1 for r in server.requests if r.tools and "subagent" in r.tools)
            out["child_requests"] = sum(1 for r in server.requests if not (r.tools and "subagent" in r.tools))
            out["statuses"] = sorted({json.load(open(p)).get("state") for p in glob.glob(f"{c.HOME}/tmp/pi-subagents-*/async-subagent-runs/*/status.json")})
            out["census"] = c.census(rpc.proc.pid)
        finally:
            out["stderr"] = rpc.close()[-300:]
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", action="append", required=True, help="NAME=BINARY; the first is the oracle")
    ap.add_argument("--cache", default="/tmp/ext-frozen/npm-cache")
    ap.add_argument("--out", default=f"{c.ROOT}/out-subagents")
    args = ap.parse_args()
    ext = external_ext.install("pi-subagents", "/tmp/ext-frozen/pi-subagents", args.cache)
    packages = external_ext.record(ext)
    print("frozen:", ", ".join(f"{n} {i[:19]}" for n, i in packages if n.startswith("pi-subagents")))
    os.makedirs(args.out, exist_ok=True)
    impls = [i.split("=", 1) for i in args.impl]
    failed = False
    for scenario in SCENARIOS:
        recs = {}
        for name, binary in impls:
            recs[name] = record_one(binary, ext, scenario)
            with open(f"{args.out}/{scenario}-{name}.json", "w") as f:
                json.dump(recs[name], f, indent=1, sort_keys=True)
            wake = (recs[name].get("wake_messages") or ["-"])[0].replace("\n", " ")[:80]
            print(f"{scenario:10s} {name:14s} census {recs[name].get('census')} child_requests {recs[name].get('child_requests')} wake: {wake}", flush=True)
        oracle = impls[0][0]
        for name, _ in impls[1:]:
            d = c.diff({k: v for k, v in recs[oracle].items() if k != "stderr"}, {k: v for k, v in recs[name].items() if k != "stderr"})
            if d:
                failed = True
                print(f"  {scenario}: {name} differs from {oracle}:")
                for line in d[:10]:
                    print("    " + line)
        for name, rec in recs.items():
            if scenario == "background" and not rec.get("wake_messages"):
                failed = True
                print(f"  {scenario}: {name} produced no completion message: {rec.get('tool_results')}")
    print("EQUIVALENT" if not failed else "DIFFERENCES")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
