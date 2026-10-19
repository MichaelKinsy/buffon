# SPDX-License-Identifier: MIT
# Adapted from pigbench's reliability.py (bench/evals of the PiG repository): arms come from the runner and the verdict is computed by the report from raw samples.
"""Reliability: faults injected by the mock endpoint and by the host (DESIGN.md axis D).

No model is called. The mock answers a scripted turn but fails chosen requests with HTTP 429 or 500, or drops the connection before a reply or part-way through a stream,
or sends only keepalives; the host kills the harness while a tool call runs, or sends SIGTERM during a stream.

Every fault has invariants that must hold for every arm (the process ends within the time limit, prints no crash trace, never reports success with no reply, leaves a session
file that parses) and a signature of what the user observes (exit class, whether the reply arrived, how many times it printed, and after a kill the message roles the model
receives on resume). The raw sample of each repetition carries `invariants_ok`, `invariant_failures` and `signature` (a JSON string). The report scores an arm against the
reference arm's signature (the oracle: Pi on Node) and an A/A copy against its original: a pair that disagrees is a flaky result, not a pass.

Faults
  http-429-retry        request 0 answers 429 with Retry-After: 0, then the scripted reply
  http-500-retry        request 0 answers 500, then the scripted reply
  http-429-exhausted    every request answers 429
  disconnect-before     the connection drops before any byte of request 0's reply
  disconnect-midstream  request 0's stream ends after 3 events with no terminator
  keepalive-only        request 0 answers 200 and a stream of keepalive comments only, then closes
  kill-mid-tool         SIGKILL of the whole harness tree while a bash tool call runs; then resume the session
  sigterm-midstream     SIGTERM to the harness while a reply streams

Parameters: reliability_reps (default 3 repetitions per fault).
"""
import json
import os
import signal
import subprocess
import time

from ..mock import REPLY, Fault, Step, agentic_policy, scripted_policy
from ..runner import cgroup, egress, procio
from . import Workload, register
from .overhead import Skip, skip_unless
from .streaming import param

FAULTS = ["http-429-retry", "http-500-retry", "http-429-exhausted", "disconnect-before", "disconnect-midstream", "keepalive-only", "kill-mid-tool", "sigterm-midstream"]
SESSION_FAULTS = {"kill-mid-tool", "sigterm-midstream"}
PROMPT = "Say hello."


def fault_plan(name):
    if name == "http-429-retry":
        return {0: Fault(status=429, retry_after=0)}
    if name == "http-500-retry":
        return {0: Fault(status=500)}
    if name == "http-429-exhausted":
        return {i: Fault(status=429, retry_after=0) for i in range(30)}
    if name == "disconnect-before":
        return {0: Fault(drop_before=True)}
    if name == "disconnect-midstream":
        return {0: Fault(drop_after=3)}
    if name == "keepalive-only":
        return {0: Fault(keepalives=25, keepalive_ms=20)}
    return {}


def session_ok(path):
    """A session file is intact when every line parses as JSON and the first line is a session header."""
    try:
        with open(path) as f:
            lines = [ln for ln in f.read().split("\n") if ln]
        records = [json.loads(ln) for ln in lines]
    except (OSError, ValueError):
        return False, 0
    return bool(records) and records[0].get("type") == "session", len(records)


def tool_text(request, index):
    """The text of the index-th message when it is a tool result, in any wire API; None otherwise."""
    body = request.body
    if request.protocol == "openai-completions":
        m = (body.get("messages") or [])[index]
        c = m.get("content")
        return c if isinstance(c, str) else json.dumps(c)
    if request.protocol == "anthropic-messages":
        m = (body.get("messages") or [])[index]
        return json.dumps(m.get("content"))
    items = body.get("input") or []
    return json.dumps(items[index].get("output")) if index < len(items) else ""


def role_signature(request):
    """What the model receives: the normalised role of every message, with tool results marked as errors or not."""
    out = []
    for i, role in enumerate(request.roles):
        if role == "tool":
            text = tool_text(request, i) or ""
            out.append("tool:error" if any(w in text.lower() for w in ("error", "abort", "no result", "interrupt")) else "tool")
        elif role in ("system", "developer"):
            continue
        else:
            out.append(role)
    return out


def print_invariants(name, res, replies, timeout):
    """Invariants of a print-mode fault run that hold for every harness, whatever its retry design."""
    inv = []
    if res["timed_out"]:
        inv.append(f"hung: no exit within {timeout:.0f}s")
    if "Traceback" in res["stderr"] or "panic:" in res["stderr"] or "goroutine " in res["stderr"]:
        inv.append("crash trace on stderr")
    # Every request fails, so no reply can reach stdout; exit status 0 would report a failed run as a success (Pi exits 1: print-mode.ts:145-147).
    if name == "http-429-exhausted" and res["code"] == 0 and not replies:
        inv.append("reported success with no reply from the model")
    return inv


def run_print_fault(ctx, arm, name):
    h = ctx.harness(arm, "rel-" + name)
    srv = ctx.server
    srv.reset(policy=agentic_policy(h.cwd, tool_turns=0), faults=fault_plan(name))
    meter = cgroup.new_meter()
    try:
        res = procio.Batch(h.print_argv(PROMPT), h.env, h.cwd, meter, ctx.opts.timeout).run()
    finally:
        meter.close()
    replies = res["stdout"].count(REPLY.split()[0])
    sig = {"ended": not res["timed_out"], "exit": "ok" if res["code"] == 0 else "error", "reply_printed": min(replies, 2),
           "retried": len([r for r in srv.requests if r.fault is None]) >= 1 and len(srv.requests) > 1,
           "attempts": len(srv.requests) if arm.capabilities.get("exact_requests") else None}
    return {"signature": sig, "invariant_failures": print_invariants(name, res, replies, ctx.opts.timeout), "requests": len(srv.requests), "stderr_tail": res["stderr"][-200:]}


def run_kill_mid_tool(ctx, arm):
    """Kill the harness tree while a bash tool call runs, then resume the same session file."""
    h = ctx.harness(arm, "rel-kill")
    srv = ctx.server
    started = os.path.join(h.cwd, "STARTED")
    tool = ("bash", {"command": f"touch {started}; sleep 120"})
    srv.reset(policy=scripted_policy([Step(tool_calls=[tool]), Step(text=REPLY)]))
    session = os.path.join(h.sessions, "kill.jsonl")
    meter = cgroup.new_meter()
    proc = meter.popen(h.argv("print_session", PROMPT, session=session), env=h.env, cwd=h.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       start_new_session=True)
    deadline = time.monotonic() + 60
    while not os.path.exists(started) and time.monotonic() < deadline and proc.poll() is None:
        time.sleep(0.02)
    if not os.path.exists(started):
        meter.close()
        return {"signature": {}, "invariant_failures": ["the tool call never started"], "requests": len(srv.requests)}
    time.sleep(0.3)
    meter.kill()
    procio.wait(meter, proc, 10)
    meter.close()
    ok, records = session_ok(session)
    inv = [] if ok else ["session file is not intact after SIGKILL"]
    srv.reset(policy=scripted_policy([Step(text=REPLY)]))
    meter = cgroup.new_meter()
    try:
        res = procio.Batch(h.argv("print_session", "Continue.", session=session), h.env, h.cwd, meter, ctx.opts.timeout).run()
    finally:
        meter.close()
    sig = {"session_intact_after_kill": ok, "resume_exit": "ok" if res["code"] == 0 else "error", "resume_reply": REPLY.split()[0] in res["stdout"],
           "roles_after_resume": role_signature(srv.requests[0]) if srv.requests else None}
    if res["timed_out"]:
        inv.append("resume hung")
    return {"signature": sig, "invariant_failures": inv, "requests": len(srv.requests), "records_after_kill": records}


def run_sigterm(ctx, arm):
    h = ctx.harness(arm, "rel-term")
    srv = ctx.server
    srv.reset(policy=scripted_policy([Step(text=" ".join(["streaming"] * 600), event_delay_ms=10)]))
    session = os.path.join(h.sessions, "term.jsonl")
    meter = cgroup.new_meter()
    proc = meter.popen(h.argv("print_session", PROMPT, session=session), env=h.env, cwd=h.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       start_new_session=True)
    try:
        if not srv.wait_requests(1, 60):
            meter.kill()
            return {"signature": {}, "invariant_failures": ["no request reached the endpoint"], "requests": 0}
        time.sleep(1.0)
        t0 = time.perf_counter()
        proc.send_signal(signal.SIGTERM)
        ended = procio.wait(meter, proc, 15)
        took = time.perf_counter() - t0
    finally:
        meter.kill()
        meter.close()
    ok, _ = session_ok(session) if os.path.exists(session) else (True, 0)
    sig = {"exited": ended, "exit_class": "signal" if proc.returncode in (-signal.SIGTERM, 143) else ("ok" if proc.returncode == 0 else "error"), "session_intact": ok}
    inv = [] if ended and ok else (["did not exit on SIGTERM"] if not ended else ["session file is not intact after SIGTERM"])
    return {"signature": sig, "invariant_failures": inv, "requests": len(srv.requests), "seconds_to_exit": round(took, 2)}


def run_fault(ctx, arm, name):
    if name in SESSION_FAULTS:
        skip_unless(ctx, arm, "print_session")
        return run_kill_mid_tool(ctx, arm) if name == "kill-mid-tool" else run_sigterm(ctx, arm)
    skip_unless(ctx, arm, "print")
    return run_print_fault(ctx, arm, name)


def reliability(session, ctx, instances):
    p = session.plan
    reps = int(param(ctx, "reliability_reps", 3))
    from ..runner.engine import effective_apis
    for api in effective_apis(p, instances):
        ctx.opts.api = api
        for rep in range(reps):
            for fi, name in enumerate(FAULTS):
                for arm in instances[(rep + fi) % len(instances):] + instances[:(rep + fi) % len(instances)]:
                    host, quiet_ok = session.quiet_wait()
                    t0 = time.monotonic()
                    ctx.server.context = {"arm": arm.id, "scenario": f"reliability/{name}", "api": api, "round": rep, "warmup": False}
                    try:
                        if not quiet_ok:
                            raise RuntimeError(f"the host was not quiet within {p.quiet_timeout_s:.0f} s; no process was started")
                        cell = run_fault(ctx, arm, name)
                    except Skip as why:
                        if not any(s["arm"] == arm.id and s["scenario"] == f"reliability/{name}" and s.get("api") == api for s in session.skipped):
                            session.skipped.append({"arm": arm.id, "scenario": f"reliability/{name}", "api": api, "reason": str(why)})
                        ctx.server.flush_log()
                        ctx.release()
                        continue
                    except Exception as error:  # a crash of the driver is a recorded failure
                        cell = {"signature": {}, "invariant_failures": [f"runner error: {error!r}"], "requests": 0}
                    ctx.server.flush_log()
                    ctx.release()
                    left = sorted(egress.take())
                    if left:
                        cell["invariant_failures"].append(f"egress to {', '.join(left)}")
                        session.violations.append({"arm": arm.id, "scenario": f"reliability/{name}", "api": api, "round": rep, "remotes": left})
                    rec = {"arm": arm.id, "scenario": f"reliability/{name}", "api": api, "round": rep, "warmup": False, "t_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                           "invariants_ok": not cell["invariant_failures"], "invariant_failures": "; ".join(cell["invariant_failures"]),
                           "signature": json.dumps(cell["signature"], sort_keys=True), "requests": cell.get("requests", 0), "stderr_tail": cell.get("stderr_tail", ""),
                           "wall_s": round(time.monotonic() - t0, 2), **host}
                    if arm.twin_of:
                        rec["twin_of"] = arm.twin_of
                    for k in ("seconds_to_exit", "records_after_kill"):
                        if k in cell:
                            rec[k] = cell[k]
                    session.samples.append(rec)
                    session.log(f"buffon: reliability/{name:22} {arm.id:12} rep {rep + 1}/{reps} {'FAIL ' + rec['invariant_failures'] if not rec['invariants_ok'] else 'ok'}")
                    session.checkpoint()


register(Workload(id="reliability/faults", family="reliability", apis=("openai-completions", "anthropic-messages"), special=reliability,
                  description="HTTP 429/500, dropped and keepalive-only streams, kill mid tool call and resume, SIGTERM mid stream; pass/fail against Pi"))
