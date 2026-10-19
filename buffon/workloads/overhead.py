# SPDX-License-Identifier: MIT
"""Overhead bench: what the harness itself costs against a scripted model that answers instantly.

No model is called and no money is spent. Each arm runs inside its own meter (a cgroup v2 where the host allows it).
Arms are interleaved across repetitions, so drift in host load hits every arm alike.

Scenarios
  version       `--version`: process start and exit
  print         -p, one prompt, one text reply: time to the first request, total wall, teardown, CPU, memory
  print-tools   -p, one prompt, eight tool-call rounds then text: harness-added latency and CPU per turn
  print-write   -p, one prompt, one `write` tool call whose arguments (a 50 KB and a 200 KB file, one process each) stream in 16-character chunks, then text
  pty           interactive TUI on a PTY: first visible frame, settled, then one prompt
  rpc           --mode rpc: ready time, then turns of one tool call and a reply
  print-ext5    print with five trivial extensions loaded (the first five of the ten)
  rpc-ext5      rpc with five trivial extensions loaded
  print-ext10   print with ten trivial extensions loaded
  rpc-ext10     rpc with ten trivial extensions loaded
  long-session  rpc, 1,000 or more turns with automatic compaction, on one process
"""
import glob
import json
import os
import re
import time

from .. import stats
from ..mock import REPLY, agentic_policy, now_ns, write_policy
from ..mock.shapes import source
from ..runner import cgroup, procio, procs, wire
from ..runner.harness import Harness

PROMPT = "Read README.md and tell me in one sentence what it says."
PROMPT_WRITE = "Write the file big/source.ts."
README = ("Benchmark fixture. " * 90).strip() + "\n"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANSI = re.compile(rb"\x1b\[[0-9;?<>=]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|\x1b[=>78]")

SCENARIOS = ["version", "print", "print-tools", "print-write", "pty", "rpc", "print-ext5", "rpc-ext5", "print-ext10", "rpc-ext10", "long-session"]


class Skip(Exception):
    """A sample the arm cannot take: it sits the variant out for the run."""


class Ctx:
    """What one sample needs: the throwaway work directory, the mock server and the run's options. Harnesses are created per sample and removed after it,
    so every process gets a fresh HOME (methodology.md section 2)."""

    def __init__(self, work, server, opts):
        self.work, self.server, self.opts = work, server, opts
        self._harnesses = {}

    def harness(self, arm, scenario, **kwargs):
        key = (arm.id, scenario)
        if key in self._harnesses and kwargs and self._harnesses[key].options != kwargs:
            raise RuntimeError(f"harness for {key} already created with different options")
        if key not in self._harnesses:
            given = dict(kwargs)
            kwargs.setdefault("api", getattr(self.opts, "api", "openai-completions"))
            h = Harness(arm, self.work, self.server, tag=scenario, **kwargs)
            h.options = given
            with open(os.path.join(h.cwd, "README.md"), "w", newline="\n") as f:  # the read tool returns the same bytes on every host
                f.write(README)
            self._harnesses[key] = h
        return self._harnesses[key]

    def harnesses_for(self, arm):
        return [h for (aid, _), h in self._harnesses.items() if aid == arm.id]

    def release(self):
        """Delete every harness directory created since the last release."""
        for h in self._harnesses.values():
            h.cleanup()
        self._harnesses = {}

    def supports(self, arm, scenario):
        mode = {"print-tools": "print", "print-write": "print"}.get(scenario, scenario)
        return arm.supports_mode(mode)

    def policy(self, arm, tool_turns, scenario):
        return agentic_policy(self._harnesses[(arm.id, scenario)].cwd, tool_turns=tool_turns)

    def main_requests(self, arm):
        """Requests that belong to the scripted turns. Other CLIs send side requests (titles, token counts) without tools."""
        return [r for r in self.server.requests if r.fault is None and (exact_requests(arm) or r.tools)]


def exact_requests(arm):
    """True for arms that send exactly the scripted requests (the Pi family); others add side requests such as titles."""
    return bool(arm.capabilities.get("exact_requests"))


def check_api(ctx, arm):
    api = getattr(ctx.opts, "api", "openai-completions")
    if not arm.supports_api(api):
        raise Skip(f"it does not speak {api}")


def skip_unless(ctx, arm, mode):
    """Raise Skip with the manifest's reason when the arm has no such mode or no support for the run's wire API."""
    if not arm.supports_mode(mode):
        raise Skip(arm.cannot_run.get(mode) or arm.cannot_run.get(mode.split("_")[0]) or f"it has no {mode} mode")
    check_api(ctx, arm)


SWEEP = (5, 50, 100)   # extension counts of the sweep besides the ten of ext10 (0 is plain print and rpc)
EXT_COUNTS = tuple(sorted((10, *SWEEP)))
EXT_WORDS = {5: "five", 10: "ten"}


def sweep_extensions(ctx, arm, count):
    """The extension sources an extension scenario with `count` extensions passes with `-e`, in order. An arm that takes the generated bench extensions gets `count` of them
    (buffon/fixtures/benchext.py: one template, numbered, so five are the first five of ten). An arm with its own realization (`[extensions] paths`) gets the first `count` of its list;
    an arm whose extensions are built into its executable passes none, and only for the count it was built with. An arm that cannot take `count` is skipped with the reason."""
    spec = arm.extension_spec
    if spec.get("embedded"):
        built = spec.get("count", 10)
        if count != built:
            raise Skip(f"its extensions are built into the binary, {built} of them: it cannot load {count}")
        return []
    if not arm.loads_template():
        own = arm.extension_paths(REPO_ROOT)
        if len(own) < count:
            raise Skip(f"its own realization lists {len(own)} extensions: it cannot load {count}")
        return own[:count]
    from ..fixtures import benchext
    return benchext.make(os.path.join(os.path.dirname(ctx.work), "fixtures", f"ext{count}"), count)


def extension_facts(arm, count):
    """What a sample with extensions records so a reader can prove which ran: the count, and for an arm that took the generated set the sha256 of the template it came from."""
    from ..fixtures import benchext
    return {"extensions_count": count, **({"extensions_template_sha256": benchext.template_sha256()} if arm.loads_template() else {})}


def cpu_hook(meter):
    def hook(request):
        request.hook_perf = meter.perf()   # the instruction count at the same instant (streaming reports instructions per 1k tokens from it)
        return meter.cpu_ms()
    return hook


def ms(a, b):
    return (b - a) / 1e6


def request_metrics(reqs, t_spawn):
    """Per-request timing common to print runs: first request, gaps between a reply's end and the next request, CPU between requests."""
    out = {"requests": len(reqs)}
    if reqs:
        out["first_request_ms"] = ms(t_spawn, reqs[0].t_recv)
        if reqs[0].hook is not None:
            out["first_request_cpu_ms"] = reqs[0].hook
    gaps = [ms(a.t_end, b.t_recv) for a, b in zip(reqs, reqs[1:]) if a.t_end]
    cpus = [b.hook - a.hook for a, b in zip(reqs, reqs[1:]) if a.hook is not None and b.hook is not None]
    return out, gaps, cpus, reqs


def check_print(res, srv, expect_requests, arm):
    if res["timed_out"] or res["code"] != 0:
        return f"exit {res['code']}{' (timed out)' if res['timed_out'] else ''}: {res['stderr'][-200:].strip()}"
    if exact_requests(arm) and len(srv.requests) != expect_requests:
        return f"expected {expect_requests} requests, saw {len(srv.requests)}"
    if not srv.requests:
        return "no request reached the endpoint"
    if REPLY.split()[0] not in res["stdout"]:
        return "the final reply did not reach stdout"
    return None


def metrics_of(res):
    return {"wall_ms": res["wall_ms"], "cpu_ms": res["cpu_ms"], "peak_mem_mib": res["peak_mem_mib"], "peak_rss_mib": res["max_proc_rss_mib"], "meter": res["meter"], **res.get("perf", {})}


def one_version(ctx, arm):
    skip_unless(ctx, arm, "version")
    h = ctx.harness(arm, "version")
    meter = cgroup.new_meter()
    try:
        res = procio.Batch(h.argv("version"), h.env, h.cwd, meter, 60).run()
    finally:
        meter.close()
    if res["code"] != 0:
        return {"failure": f"exit {res['code']}: {res['stderr'][-200:]}"}
    return metrics_of(res)


def skip_without_extensions(arm):
    """Raise Skip, with the manifest's own reason (`[cannot_run] extensions`) when it gives one, for an arm that does not load Pi extensions fully."""
    if arm.pi_extensions not in ("native", "sidecar"):
        raise Skip(arm.cannot_run.get("extensions") or ("it does not load Pi extensions" if arm.pi_extensions == "none" else "it loads only part of Pi's extensions"))


def one_print(ctx, arm, tools=0, ext=False, scenario="print", count=10):
    if ext:
        skip_without_extensions(arm)
    skip_unless(ctx, arm, "print")
    h = ctx.harness(arm, scenario, extensions=sweep_extensions(ctx, arm, count) if ext else ())
    srv = ctx.server
    srv.reset(policy=ctx.policy(arm, tools, scenario))
    meter = cgroup.new_meter()
    srv.on_request = cpu_hook(meter)
    try:
        res = procio.Batch(h.print_argv(PROMPT), h.env, h.cwd, meter, ctx.opts.timeout).run()
    finally:
        meter.close()
        srv.on_request = None
    bad = check_print(res, srv, tools + 1, arm)
    if bad:
        return {"failure": bad}
    if ext and len(srv.requests[0].tools) < 4 + count:
        return {"failure": f"extensions did not load: the first request declared {len(srv.requests[0].tools)} tools"}
    sample = metrics_of(res)
    if ext:
        sample.update(extension_facts(arm, count))
    extra, gaps, cpus, reqs = request_metrics(ctx.main_requests(arm), res["t_spawn"])
    sample.update(extra)
    sample["teardown_ms"] = ms(reqs[-1].t_end, res["t_exit"]) if reqs and reqs[-1].t_end else None
    if gaps:
        sample["turn_gap_ms"] = stats.median(gaps)
        sample["_series"] = {"gap_ms": gaps, "cpu_turn_ms": cpus}
    if cpus:
        sample["turn_cpu_ms"] = stats.median(cpus)
    return wire.declare(sample, tools + 1, tools + 1)   # a round is one request the model answers: a tool call per tool round, then the reply


WRITE_FILE = os.path.join("big", "source.ts")   # where the scripted write call puts the file, under the project directory (Pi-Bolt's large_write.py uses the same path)


def write_param(ctx, name, default):
    return getattr(ctx.opts, "params", {}).get(name, default)


def write_sizes(ctx):
    """((label, KB), ...) from --param write_kb (default 50,200): a list "50,200" or one number."""
    kbs = [int(k) for k in str(write_param(ctx, "write_kb", "50,200")).split(",")]
    return tuple((f"kb{k}", k) for k in kbs)


def wrong_file(path, want):
    """None when the file at `path` holds exactly the bytes `want`, else why it does not."""
    try:
        with open(path, "rb") as f:
            got = f.read()
    except OSError as error:
        return f"the file was not written: {error.strerror or error}"
    if got == want:
        return None
    if len(got) != len(want):
        return f"the file holds {len(got)} bytes, expected {len(want)}"
    at = next(i for i, (a, b) in enumerate(zip(got, want)) if a != b)
    return f"the file differs from the expected bytes at offset {at}"


def one_write(ctx, arm):
    """One process per file size. The scripted model answers with one `write` call whose arguments (the file body inside a JSON object) stream in fixed chunks, then text.
    A sample fails unless the file in the project directory holds exactly the expected bytes (the body, or what the harness's patch tool makes of it: one ends every file with a newline). Metrics are prefixed with the size label (`kb50_`, `kb200_`)."""
    if arm.cannot_run.get("print-write"):
        raise Skip(arm.cannot_run["print-write"])
    skip_unless(ctx, arm, "print")
    chunk = int(write_param(ctx, "write_chunk", 16))
    srv = ctx.server
    sample = {"write_chunk": chunk}
    for label, kb in write_sizes(ctx):
        content = source(kb * 1024)
        h = ctx.harness(arm, f"print-write-{label}")
        os.makedirs(os.path.join(h.cwd, os.path.dirname(WRITE_FILE)), exist_ok=True)   # the project has its `big` directory: a write tool may need the parent to exist (Copilot's `create`: "Parent directories must exist")
        policy = write_policy(h.cwd, WRITE_FILE.replace(os.sep, "/"), content, chunk)
        srv.reset(policy=policy)
        meter = cgroup.new_meter()
        srv.on_request = cpu_hook(meter)
        try:
            res = procio.Batch(h.print_write_argv(PROMPT_WRITE), h.env, h.cwd, meter, max(ctx.opts.timeout, 900)).run()   # PiG 0.4.1 needs about 70 s for 200 KB
        finally:
            meter.close()
            srv.on_request = None
        if policy.missing:
            raise Skip(f"its tools cannot take the call: the first request declared no write tool (it declared {', '.join(policy.missing[0]) or 'none'})")
        bad = check_print(res, srv, 2, arm) or wrong_file(os.path.join(h.cwd, WRITE_FILE), policy.expected.encode())
        if bad:
            return {"failure": f"{label}: {bad}"}
        reqs = ctx.main_requests(arm)
        sample[f"{label}_wall_ms"] = res["wall_ms"]
        sample[f"{label}_cpu_ms"] = res["cpu_ms"]
        sample[f"{label}_peak_mem_mib"] = res["peak_mem_mib"]
        sample[f"{label}_peak_rss_mib"] = res["max_proc_rss_mib"]
        sample[f"{label}_bytes_out"] = len(res["stdout"].encode())
        for key, value in (res.get("perf") or {}).items():
            sample[f"{label}_{key}"] = value
        if len(reqs) > 1 and reqs[0].t_start:
            sample[f"{label}_call_to_result_ms"] = ms(reqs[0].t_start, reqs[1].t_recv)   # first streamed byte of the call to the request that carries its result
            if reqs[0].t_end:
                sample[f"{label}_after_stream_ms"] = ms(reqs[0].t_end, reqs[1].t_recv)   # the stream's end to that request: parse, write the file, send the result
        sample["meter"] = res["meter"]
    return wire.declare(sample, 2 * len(write_sizes(ctx)), 2 * len(write_sizes(ctx)))   # per size: the write call, then the reply


def visible(chunks):
    """Length of the visible text in byte chunks once escape sequences are removed."""
    return len(ANSI.sub(b"", b"".join(chunks)).strip())


def one_pty(ctx, arm):
    skip_unless(ctx, arm, "pty")
    h = ctx.harness(arm, "pty")
    srv = ctx.server
    srv.reset(policy=ctx.policy(arm, 0, "pty"))
    meter = cgroup.new_meter()
    srv.on_request = cpu_hook(meter)
    term = procio.Pty(h.tui_argv(), h.env, h.cwd, meter, echo=False)  # first_input_accepted_ms must see the application's echo, not the kernel's
    sample = {}
    try:
        t_first = None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and t_first is None:
            with term.cond:
                term.cond.wait(0.05)
                seen = []
                for t, c in term.chunks:
                    seen.append(c)
                    if visible(seen) > 0:
                        t_first = t
                        break
        if t_first is None:
            return {"failure": "no visible output within 60 s"}
        sample["first_frame_ms"] = ms(term.t_spawn, t_first)
        # First accepted input: the first moment a typed key is echoed. Keys are sent every 40 ms from the first frame on; an arm that ignores them for 20 s fails.
        t_accept, probe_deadline, mark_in = None, time.monotonic() + 20, len(term.chunks)
        while t_accept is None and time.monotonic() < probe_deadline:
            term.type("x")
            with term.cond:
                term.cond.wait(0.04)
                for t, c in term.chunks[mark_in:]:
                    if b"x" in ANSI.sub(b"", c):
                        t_accept = t
                        break
        if t_accept is None:
            return {"failure": "no typed key was echoed within 20 s of the first frame"}
        sample["first_input_accepted_ms"] = ms(term.t_spawn, t_accept)
        term.type("\x15" * 2)  # clear the line (Ctrl-U) before the real prompt
        t_ready = term.wait_quiet(0.6, 60)
        if t_ready is None:
            return {"failure": "the screen never settled"}
        sample["ready_ms"] = ms(term.t_spawn, t_ready)
        sample["ready_cpu_ms"] = meter.cpu_ms()
        sample["ready_rss_mib"] = meter.max_proc_rss_mib()
        sample["ready_pss_mib"] = meter.current_pss_mib()
        mark = len(term.chunks)
        term.type("hello")
        time.sleep(0.15)
        t_input = now_ns()
        term.type("\r")
        if not srv.wait_requests(1, 60):
            return {"failure": "the prompt never reached the endpoint" + term.diagnosis()}
        sample["input_to_request_ms"] = ms(t_input, srv.requests[0].t_recv)
        t_reply = term.wait_text(REPLY.split()[0], 60, since=mark)
        if t_reply is None:
            return {"failure": "the reply never appeared on screen"}
        sample["input_to_reply_visible_ms"] = ms(t_input, t_reply)
        term.wait_quiet(0.6, 30)
        term.type("\x04")
        procio.wait(meter, term.proc, 5)
        sample.update({"cpu_ms": meter.cpu_ms(), "peak_mem_mib": meter.peak_mem_mib(), "peak_rss_mib": meter.max_proc_rss_mib(), "meter": meter.mode, **meter.perf()})
        return wire.declare(sample, 1, 1)
    finally:
        term.close()
        meter.close()
        srv.on_request = None


def start_rpc(ctx, arm, scenario, ext=False, compaction=None, context_window=128000, count=10):
    h = ctx.harness(arm, scenario, extensions=sweep_extensions(ctx, arm, count) if ext else (), compaction=compaction, context_window=context_window)
    meter = cgroup.new_meter()
    ctx.server.on_request = cpu_hook(meter)
    rpc = procio.Rpc(h.rpc_argv(session=scenario == "long-session"), h.env, h.cwd, meter)
    rpc.cursor = 0
    rpc.dialect = arm.spec.get("rpc", {})
    return h, meter, rpc


def wait_ready(rpc):
    ident, _ = rpc.send({"type": "get_state"})
    # Pi names the command in the response; the Rust port rpi answers with only the request id.
    got = rpc.wait_for(lambda r: r.get("type") == "response" and (r.get("command") == "get_state" or r.get("id") == ident), 60)
    if got is not None:
        rpc.cursor = got[2]
    return got


# A prompt sent while automatic compaction runs after agent_end: Pi 1.1.0 refuses it with "Agent is already processing" (agent-session.ts:2014-2018),
# because the run is still active and only manual compaction sets _compactionAbortController (:1986-1990, :2766). PiG's RPC admission answers
# "Cannot submit a prompt while compaction is in progress" instead, because it checks every compaction (coding/cli/rpc_admission.go, promptInput):
# a PiG divergence, not a second Pi message. Both are accepted so the turn can be measured; each turn row records the message it got.
# "Agent is currently compacting" is the third-party Rust port's refusal.
BUSY_MESSAGES = ("Agent is already processing", "Cannot submit a prompt while compaction is in progress", "Agent is currently compacting")


def is_busy_rejection(r):
    return r.get("type") == "response" and r.get("command") == "prompt" and r.get("success") is False and any(m in str(r.get("error", "")) for m in BUSY_MESSAGES)


def drive_turns(ctx, rpc, meter, turns, series, sample_every=0):
    """Send `turns` prompts one after another and record each. Returns a failure string or None."""
    srv = ctx.server
    last_cpu = meter.cpu_ms()
    for i in range(turns):
        first_req = len(srv.requests)
        _, t_send = rpc.send(prompt_command(rpc, f"Turn {i}. {PROMPT}"))
        got = rpc.wait_for(lambda r: is_turn_end(rpc, r) or is_busy_rejection(r), ctx.opts.timeout, start=rpc.cursor)
        refused = None
        deadline = time.monotonic() + ctx.opts.timeout
        while got is not None and got[1].get("type") == "response":
            refused = refused if refused is not None else str(got[1].get("error", ""))
            # The previous turn's automatic compaction is still running, so the harness refuses a new prompt (Pi: "Agent is already processing").
            # A user would send it again once it ends; the wait is not part of the turn. A harness that reports no compaction event
            # (pi_agent_rust) is retried every 50 ms until the deadline.
            rpc.cursor = got[2]
            if time.monotonic() > deadline:
                return f"turn {i}: the harness stayed busy for {ctx.opts.timeout}s after refusing a prompt"
            done = rpc.wait_for(lambda r: r.get("type") in ("compaction_end", "agent_settled"), 0.2, start=rpc.cursor)
            if done is not None:
                rpc.cursor = done[2]
            else:
                time.sleep(0.05)
            first_req = len(srv.requests)
            _, t_send = rpc.send(prompt_command(rpc, f"Turn {i}. {PROMPT}"))
            got = rpc.wait_for(lambda r: is_turn_end(rpc, r) or is_busy_rejection(r), ctx.opts.timeout, start=rpc.cursor)
        if got is None:
            tail = [{k: r.get(k) for k in ("type", "command", "success", "error") if r.get(k) is not None} for _, r in rpc.records[-6:]]
            return f"turn {i}: no agent_end within {ctx.opts.timeout}s; last records {json.dumps(tail)}"
        t_end, _, rpc.cursor = got
        cpu = meter.cpu_ms()
        mine = [r for r in srv.requests[first_req:] if r.fault is None and r.tools]
        row = {"turn": i, "wall_ms": ms(t_send, t_end), "cpu_ms": cpu - last_cpu, "requests": len(srv.requests) - first_req}
        if refused is not None:
            row["refused_while_busy"] = refused
        if mine and mine[-1].t_end:
            row["harness_added_ms"] = ms(mine[-1].t_end, t_end)
        if len(mine) > 1:
            row["turn_gap_ms"] = stats.median([ms(a.t_end, b.t_recv) for a, b in zip(mine, mine[1:]) if a.t_end])
        if sample_every and i % sample_every == 0:
            row["rss_mib"] = meter.max_proc_rss_mib()
        last_cpu = cpu
        series.append(row)
    return None


def count_events(rpc, kind):
    return sum(1 for _, r in rpc.records if r.get("type") == kind)


def count_compaction_requests(server):
    """Summarisation requests the mock received: no tools and the serialised conversation in the prompt. This is arm-agnostic: an arm may compact without emitting Pi's
    `compaction_end` RPC event (rpi 0.3.19 summarises its context and emits no such event)."""
    return sum(1 for r in server.requests if r.fault is None and not r.tools and "<conversation>" in json.dumps(r.body))


def one_rpc(ctx, arm, ext=False, scenario="rpc", count=10):
    if ext:
        skip_without_extensions(arm)
    skip_unless(ctx, arm, "rpc")
    ctx.harness(arm, scenario, extensions=sweep_extensions(ctx, arm, count) if ext else (), compaction=None, context_window=128000)
    ctx.server.reset(policy=ctx.policy(arm, 1, scenario))
    h, meter, rpc = start_rpc(ctx, arm, scenario, ext, count=count)
    try:
        got = wait_ready(rpc)
        if got is None:
            return {"failure": "no get_state response" + rpc.diagnosis()}
        sample = {"ready_ms": ms(rpc.t_spawn, got[0]), "ready_cpu_ms": meter.cpu_ms(), "ready_rss_mib": meter.max_proc_rss_mib(), "ready_pss_mib": meter.current_pss_mib(), "meter": meter.mode}
        if ext:
            # Pi answers get_state before its extensions finish loading; poll get_commands until the extension commands are listed.
            deadline = time.monotonic() + 60
            loaded, cmds = [], None
            while len(loaded) < count and time.monotonic() < deadline:
                rpc.send({"type": "get_commands"})
                cmds = rpc.wait_for(lambda r: r.get("type") == "response" and r.get("command") == "get_commands", 30, start=rpc.cursor)
                if cmds is None:
                    return {"failure": "no get_commands response"}
                rpc.cursor = cmds[2]
                loaded = [c for c in (cmds[1].get("data") or {}).get("commands", []) if str(c.get("name", "")).startswith("bench-")]
                if len(loaded) < count:
                    time.sleep(0.05)
            if len(loaded) < count:
                return {"failure": f"extensions did not load: {len(loaded)} of {count} bench commands listed after 60 s"}
            sample.update(extensions_ready_ms=ms(rpc.t_spawn, cmds[0]), extensions_ready_cpu_ms=meter.cpu_ms(), extensions_ready_rss_mib=meter.max_proc_rss_mib(),
                          extensions_ready_pss_mib=meter.current_pss_mib())
            rows0 = procs.census(rpc.proc.pid, meter.pids())
            bad = procs.check(rows0, arm.extension_spec, count)
            if bad:
                return {"failure": f"not the realization the arm declares: {bad}"}
            sample["extension_processes"] = sum(1 for r in rows0 if r["role"] == "extension")
            sample["extension_exes"] = ",".join(sorted({r["exe"] for r in rows0 if r["role"] == "extension"}))
            sample.update(extension_facts(arm, count))
        series = []
        bad = drive_turns(ctx, rpc, meter, ctx.opts.rpc_turns, series)
        if bad:
            return {"failure": bad}
        if ext:  # the per-turn CPU of the harness process against its extension processes: cumulative CPU of each live process after the turns less what it had used at ready
            rows1 = {r["pid"]: r for r in procs.census(rpc.proc.pid, meter.pids())}
            before = {r["pid"]: r for r in rows0}
            turns = max(1, len(series))
            for role in ("host", "extension"):
                total = sum(r["cpu_ms"] - before.get(pid, {"cpu_ms": 0})["cpu_ms"] for pid, r in rows1.items() if r["role"] == role)
                sample[f"turn_{role}_cpu_ms"] = total / turns
        if ext and len(ctx.server.requests[0].tools) < 4 + count:
            return {"failure": f"extensions did not load: the first request declared {ctx.server.requests[0].tools}"}
        warm = series[2:] if len(series) > 4 else series
        for key in ("wall_ms", "cpu_ms", "harness_added_ms", "turn_gap_ms"):
            vals = [r[key] for r in warm if key in r]
            if vals:
                sample["turn_" + key] = stats.median(vals)
        cpus = [r["cpu_ms"] for r in warm]
        if cpus:  # where CPU time is charged in whole clock ticks (Windows), a turn's median is 0 or one tick; the mean is not
            sample["turn_cpu_mean_ms"] = sum(cpus) / len(cpus)
        sample["peak_rss_mib"] = meter.max_proc_rss_mib()
        t_close = now_ns()
        rpc.close()
        sample["teardown_ms"] = ms(t_close, rpc.t_exit)
        sample["cpu_ms"] = meter.cpu_ms()
        sample.update(meter.perf())
        sample["peak_mem_mib"] = meter.peak_mem_mib()
        sample["_series"] = {"turns": series}
        return wire.declare(sample, ctx.opts.rpc_turns, 2 * ctx.opts.rpc_turns)   # a turn is a prompt: one tool call, then the reply
    finally:
        if rpc.proc.poll() is None:
            rpc.close(grace=1)
        meter.close()
        ctx.server.on_request = None


def one_long(ctx, arm):
    skip_unless(ctx, arm, "rpc")
    turns = ctx.opts.long_turns
    compaction = {"enabled": True, "reserveTokens": 8000, "keepRecentTokens": 6000}
    ctx.harness(arm, "long-session", extensions=(), compaction=compaction, context_window=32000)
    ctx.server.reset(policy=ctx.policy(arm, 1, "long-session"))
    h, meter, rpc = start_rpc(ctx, arm, "long-session", compaction=compaction, context_window=32000)
    series = []
    try:
        got = wait_ready(rpc)
        if got is None:
            return {"failure": "no get_state response" + rpc.diagnosis()}
        sample = {"ready_ms": ms(rpc.t_spawn, got[0]), "meter": meter.mode}
        t0 = now_ns()
        bad = drive_turns(ctx, rpc, meter, turns, series, sample_every=50)
        if bad:
            return {"failure": bad, "_series": {"turns": series}}
        sample["total_wall_ms"] = ms(t0, now_ns())
        sample["turns"] = turns
        sample["compaction_events"] = count_events(rpc, "compaction_end")
        sample["compactions"] = count_compaction_requests(ctx.server)
        if sample["compactions"] < 1:
            return {"failure": "no compaction happened, so the run does not exercise compaction", "_series": {"turns": series}}
        edge = max(10, turns // 20)
        for key in ("cpu_ms", "wall_ms", "harness_added_ms"):
            a = [r[key] for r in series[:edge] if key in r]
            b = [r[key] for r in series[-edge:] if key in r]
            if a and b:
                sample[f"first_turn_{key}"] = stats.median(a)
                sample[f"last_turn_{key}"] = stats.median(b)
        sample["peak_rss_mib"] = meter.max_proc_rss_mib()
        sample["cpu_ms"] = meter.cpu_ms()
        sample.update(meter.perf())
        sample["cpu_ms_per_turn"] = sample["cpu_ms"] / turns
        sample["session_bytes"] = sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(h.sessions) for f in fs)
        rpc.close()
        sample["peak_mem_mib"] = meter.peak_mem_mib()
        sample["_series"] = {"turns": series}
        return wire.declare(sample, turns, 2 * turns + sample["compactions"], exact=False)   # the compactions are the harness's own decision, found by their summarisation prompt
    finally:
        if rpc.proc.poll() is None:
            rpc.close(grace=1)
        meter.close()
        ctx.server.on_request = None


RUNNERS = {
    "version": one_version,
    "print": lambda c, a: one_print(c, a, 0, False, "print"),
    "print-tools": lambda c, a: one_print(c, a, 8, False, "print-tools"),
    "print-write": one_write,
    "pty": one_pty,
    "rpc": lambda c, a: one_rpc(c, a, False, "rpc"),
    "long-session": one_long,
    **{f"print-ext{n}": (lambda c, a, n=n: one_print(c, a, 0, True, f"print-ext{n}", n)) for n in EXT_COUNTS},
    **{f"rpc-ext{n}": (lambda c, a, n=n: one_rpc(c, a, True, f"rpc-ext{n}", n)) for n in EXT_COUNTS},
}


def prompt_command(rpc, text):
    """Pi's RPC prompt carries `message`; rpi's carries `content` (rpi-cli modes.rs, rpc_prompt)."""
    return {"type": "prompt", getattr(rpc, "dialect", {}).get("prompt_field", "message"): text}


def is_turn_end(rpc, record):
    return record.get("type") == getattr(rpc, "dialect", {}).get("turn_end", "agent_end")




from . import Workload, register  # noqa: E402

DESCRIPTIONS = {
    "version": ("`--version`: process start and exit", (None,)),
    "print": ("print mode, one prompt, one text reply: time to the first request, wall, CPU, memory", None),
    "print-tools": ("print mode, eight tool-call rounds then text: harness-added latency and CPU per turn", None),
    "print-write": ("print mode, one `write` tool call with a 50 KB and a 200 KB file streamed in 16-character chunks: wall, CPU, memory, and the file must match byte for byte", None),
    "pty": ("interactive TUI on a PTY: first frame, first accepted input, then one prompt", None),
    "rpc": ("`--mode rpc`: ready time, then turns of one tool call and a reply", None),
    **{f"{kind}-ext{n}": (f"{kind} mode with {EXT_WORDS.get(n, n)} trivial extensions loaded" + (" (the extension sweep)" if n in SWEEP else ""), None) for kind in ("print", "rpc") for n in EXT_COUNTS},
}
for _name, (_desc, _apis) in DESCRIPTIONS.items():  # `long-session` is the grow workload of workloads/longsession.py
    register(Workload(id=f"overhead/{_name}", family="overhead", fn=RUNNERS[_name], description=_desc, **({"apis": _apis} if _apis else {})))
