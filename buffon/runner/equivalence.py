# SPDX-License-Identifier: Apache-2.0
"""Equivalence before timing: every arm that loads the bench extensions must do the same work, or the run is refused.

A time or memory ratio between two realizations of "the same N extensions" means something only if each did the same thing. The gate runs for each extension count the plan's workloads
use (five for `print-ext5` and `rpc-ext5`, ten for `print-ext10` and `rpc-ext10`). Before the first measured sample, each arm that can load that count
(one `rpc` session with its extension set, a scripted model that calls `bench_tool_01` .. `bench_tool_NN` one after another, then answers) records

  * the N `bench-NN` commands it lists (name and description),
  * the bench tools as the model request declares them (name, description, JSON Schema of the parameters),
  * the result of every tool call as the RPC stream reports it (`tool_execution_end`: content and details, byte for byte as canonical JSON, including how many handler events
    the extension had counted when the tool ran), and the tool-result messages the next model request carries,
  * the extension process census (how many processes run the extensions, and on which executable).

The first selected arm with a TypeScript fixture set that is Pi itself (the reference), else the first arm, is the oracle of a count: any other arm whose record differs refuses the run
(exit code 3) and the differing fields are named. The records and their digests go to `equivalence.json` in the run directory, with the count and the sha256 of the bench template
(buffon/fixtures/benchext.py) the generated sets came from.
"""
import hashlib
import json
import os

from ..mock import Step
from . import cgroup, egress, procio, procs

SCENARIOS = {"overhead/print-ext5": 5, "overhead/rpc-ext5": 5, "overhead/print-ext10": 10, "overhead/rpc-ext10": 10}   # workload: how many bench extensions it loads


def counts(plan):
    """The extension counts the plan's workloads load, smallest first; empty when the plan has none of the gated workloads."""
    return sorted({SCENARIOS[w.id] for w in plan.workloads if w.id in SCENARIOS})


def tools_of(count):
    return [f"bench_tool_{i:02d}" for i in range(1, count + 1)]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def policy_of(count):
    """The scripted model for `count` extensions: round k calls bench_tool_(k+1): sequential, so each extension's event counter at the call is the same in every harness that emits the same events."""
    tools = tools_of(count)

    def policy(request):
        k = request.rounds()
        if request.tools and k < len(tools) and tools[k] in request.tools:
            return Step(tool_calls=[(tools[k], {"value": f"equivalence-{k + 1:02d}"})])
        return Step(text=f"{count} bench tools were called.")
    return policy


def declared_tools(request, count=10):
    out = {}
    for name in tools_of(count):
        out[name] = {"description": None, "parameters": request.schemas.get(name)}
    body = request.body
    for t in body.get("tools") or []:
        fn = t.get("function", t)
        if fn.get("name") in out:
            out[fn["name"]]["description"] = fn.get("description")
    return out


def tool_results(request):
    """The tool-result texts the request carries, in order (Chat Completions `tool` messages, Responses `function_call_output`, Anthropic `tool_result` blocks)."""
    body, out = request.body, []
    for m in body.get("messages") or body.get("input") or []:
        if not isinstance(m, dict):
            continue
        if m.get("role") == "tool":
            out.append(m.get("content"))
        elif m.get("type") == "function_call_output":
            out.append(m.get("output"))
        elif isinstance(m.get("content"), list):
            out += [b.get("content") for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_result"]
    return out


def record_of(ctx, arm, paths, timeout, count=10):
    """One rpc session of `arm` with its `count` extension sources `paths`; returns the arm's equivalence record or {"failure": text}."""
    h = ctx.harness(arm, "equivalence", extensions=paths, compaction=None, context_window=128000)
    ctx.server.reset(policy=policy_of(count))
    meter = cgroup.new_meter()
    rpc = procio.Rpc(h.rpc_argv(session=False), h.env, h.cwd, meter)
    rpc.cursor = 0
    rpc.dialect = arm.spec.get("rpc", {})
    try:
        ident, _ = rpc.send({"type": "get_state"})
        got = rpc.wait_for(lambda r: r.get("type") == "response" and (r.get("command") == "get_state" or r.get("id") == ident), 120)
        if got is None:
            return {"failure": "no get_state response" + rpc.diagnosis()}
        rpc.cursor = got[2]
        import time
        deadline, listed = time.monotonic() + 120, []
        while len(listed) < count and time.monotonic() < deadline:
            rpc.send({"type": "get_commands"})
            cmds = rpc.wait_for(lambda r: r.get("type") == "response" and r.get("command") == "get_commands", 30, start=rpc.cursor)
            if cmds is None:
                return {"failure": "no get_commands response"}
            rpc.cursor = cmds[2]
            listed = sorted((c.get("name"), c.get("description")) for c in (cmds[1].get("data") or {}).get("commands", []) if str(c.get("name", "")).startswith("bench-"))
            if len(listed) < count:
                time.sleep(0.05)
        if len(listed) < count:
            return {"failure": f"{len(listed)} of {count} bench commands listed"}
        rows = procs.census(rpc.proc.pid, meter.pids())
        bad = procs.check(rows, arm.extension_spec, count)
        if bad:
            return {"failure": f"not the realization the arm declares: {bad}"}
        rpc.send({"type": "prompt", "message": "Call every bench tool."})
        end = rpc.wait_for(lambda r: r.get("type") == "agent_end", timeout, start=rpc.cursor)
        if end is None:
            return {"failure": "no agent_end"}
        results = [{k: r.get(k) for k in ("toolName", "args", "result", "isError")} for _, r in rpc.records if r.get("type") == "tool_execution_end"]
        reqs = [r for r in ctx.server.requests if r.fault is None and r.tools]
        if len(results) != count or len(reqs) != count + 1:
            return {"failure": f"{len(results)} tool results and {len(reqs)} model requests, expected {count} and {count + 1}"}
        return {"commands": listed, "declared": declared_tools(reqs[0], count), "results": results, "carried": tool_results(reqs[-1]),
                "census": {"extension_processes": sum(1 for r in rows if r["role"] == "extension"), "executables": sorted({r["exe"] for r in rows if r["role"] == "extension"})}}
    finally:
        rpc.close(grace=1)
        meter.close()
        ctx.release()


def diff(a, b, path=""):
    """Paths at which two JSON values differ, with both values clipped."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k), b.get(k), f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {canonical(a)[:160]} != {canonical(b)[:160]}"]


def candidates_at(arms, count, extensions_of):
    """{arm: extension sources} for every arm that loads `count` bench extensions: it loads Pi extensions and its realization can take that count (an arm that cannot is skipped by
    the workload with its reason, so it has nothing to compare)."""
    from ..workloads.overhead import Skip
    out = {}
    for arm in arms:
        if arm.pi_extensions not in ("native", "sidecar"):
            continue
        try:
            out[arm.id] = (arm, extensions_of(arm, count))
        except Skip:
            continue
    return out


def compare(records, oracle):
    """The differences of every arm's record from the oracle's: {arm: [text, ...]}."""
    ref = records[oracle]
    # The census is a property of the realization, not of the output: it is checked against each arm's own declaration, and left out of the comparison.
    comparable = lambda r: {k: v for k, v in r.items() if k != "census"}   # noqa: E731
    differences = {}
    for arm_id, rec in records.items():
        if "failure" in rec:
            differences[arm_id] = [f"could not record: {rec['failure']}"]
        elif arm_id != oracle and "failure" not in ref:
            d = diff(comparable(ref), comparable(rec))
            if d:
                differences[arm_id] = d[:12]
    return differences


def run(runner, ctx, arms, extensions_of, out_dir, counts=(10,)):
    """Record every arm that loads `count` extensions, for each count, and compare with that count's oracle. `extensions_of(arm, count)` gives an arm's extension sources (it raises
    the workloads' Skip for a count the arm cannot take). Returns {"passed", "template_sha256", "counts": {count: {"oracle", "arms": {id: {digest, census, extensions}}, "differences": {id: [...]}}}},
    or None when no arm loads any of the counts."""
    from ..fixtures import benchext
    by_count, records = {}, {}
    for count in counts:
        candidates = candidates_at(arms, count, extensions_of)
        if not candidates:
            continue
        oracle = next((a for a, _ in candidates.values() if a.family == "pi-reference"), next(iter(candidates.values()))[0])
        recs = {}
        for arm, paths in [candidates[oracle.id], *[c for i, c in candidates.items() if i != oracle.id]]:
            runner.log(f"buffon: equivalence: {arm.id} with {count} extensions")
            ctx.opts.api = arm.apis[0]
            rec = record_of(ctx, arm, paths, ctx.opts.timeout, count)
            left = sorted(egress.take())
            if left:
                rec = {"failure": f"egress: the harness connected to {', '.join(left)}"}
            recs[arm.id] = rec
        differences = compare(recs, oracle.id)
        facts = lambda arm: {"count": count, "template_sha256": benchext.template_sha256() if arm.loads_template() else None}   # noqa: E731
        by_count[str(count)] = {"oracle": oracle.id, "differences": differences,
                                "arms": {i: ({"digest": digest({k: v for k, v in r.items() if k != "census"}), "census": r["census"], "extensions": facts(candidates[i][0])}
                                             if "failure" not in r else {"failure": r["failure"]}) for i, r in recs.items()}}
        records[str(count)] = recs
    if not by_count:
        return None
    doc = {"passed": not any(c["differences"] for c in by_count.values()), "template_sha256": benchext.template_sha256(), "counts": by_count}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "equivalence.json"), "w") as f:
        json.dump({**doc, "records": records}, f, indent=1, sort_keys=True)
    return doc
