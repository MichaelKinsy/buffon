# SPDX-License-Identifier: Apache-2.0
"""Streaming: the CPU a harness spends rendering an answer that arrives as a stream, by answer shape and size (DESIGN.md axis B).

The mock streams one answer of a given shape (prose, code blocks, tables, lists) in fixed-size chunks. The TUI gets them at a fixed token rate, because when chunks arrive
changes how a screen redraws. Print mode gets them as fast as the harness reads them: its cost is per chunk, so pacing would only add waiting (at 1,000 tokens per second a
60,000-character answer waits 15 s whatever the harness). Each answer size runs once at N and once at 10N characters.

  streaming/tui-<shape>     the interactive TUI on a PTY: one process, N then 10N answers in turn (the method of Pi-Bolt's long_answer and PiG's bench/compare stream_shapes)
  streaming/print-<shape>   print mode: one fresh process per size, the answer goes to stdout

Metrics per size label (`n`, `n10`): cpu_ms_per_1k_tokens (CPU between the request's arrival and the answer's end, per 1,000 streamed tokens), first_paint_ms
(first SSE byte sent by the mock to the first terminal output that shows the answer; TUI only), wall_ms (first SSE byte to the answer's end marker),
bytes_out (bytes the harness wrote to the terminal or stdout), peak_rss_mib. Tokens are characters / 4, the mock's own count.

Parameters (--param KEY=VALUE): stream_n (default 6000), stream_rate_tps (the TUI's rate, 1000), print_stream_rate_tps (print mode's rate, 0: unpaced), stream_chunk (24),
tty_rows (40), tty_cols (120), terminal (xterm | kitty). Each sample records the rate it used as `stream_rate_tps` (0 for unpaced).
"""
import re
import time

from ..mock import MockServer, Step, Transcript, now_ns  # noqa: F401
from ..mock.shapes import SHAPES, body
from ..runner import cgroup, procio, wire
from . import Workload, register
from .overhead import ANSI, Skip, cpu_hook, ms, skip_unless

CHARS_PER_TOKEN = 4
PROMPT = "Write the answer."


def param(ctx, name, default):
    return getattr(ctx.opts, "params", {}).get(name, default)


def end_marker(label):
    return f"END-OF-ANSWER-{label.upper()}"


def rate_of(ctx, mode):
    """Tokens per second the mock streams at: the TUI's `stream_rate_tps` (1000), print mode's `print_stream_rate_tps` (0, unpaced)."""
    return float(param(ctx, "stream_rate_tps", 1000)) if mode == "tui" else float(param(ctx, "print_stream_rate_tps", 0))


def answer_step(shape, size, label, ctx, rate):
    chunk = int(param(ctx, "stream_chunk", 24))
    delay = chunk / CHARS_PER_TOKEN / rate * 1000 if rate > 0 else 0
    text = body(shape, size)
    if text.count("```") % 2:
        text += "\n```"  # a size that cuts a code block short still ends with a closed fence, so the marker below is prose
    return Step(text=text + "\n\n" + end_marker(label), chunk_chars=chunk, event_delay_ms=delay)


def needle(shape, size):
    """The first visible words of the answer: its first heading without the Markdown marker."""
    first = body(shape, 40).splitlines()[0]
    return first.lstrip("# ").strip()


def answer_timeout(ctx, size, rate):
    """Seconds an answer may take to appear: the streaming time at the rate, 20 times over, and at least the per-process timeout."""
    return max(float(ctx.opts.timeout), 20 * size / CHARS_PER_TOKEN / rate) if rate > 0 else float(ctx.opts.timeout)


def sizes(ctx):
    n = int(param(ctx, "stream_n", 6000))
    return (("n", n), ("n10", n * 10))


def visible_has(chunks, text):
    return text.encode() in ANSI.sub(b"", b"".join(chunks))


def tui_sample(ctx, arm, shape):
    skip_unless(ctx, arm, "pty")
    h = ctx.harness(arm, f"stream-tui-{shape}")
    srv = ctx.server
    plan = sizes(ctx)
    rate = rate_of(ctx, "tui")
    srv.reset(policy=lambda request: answer_step(shape, plan[min(request.index, len(plan) - 1)][1], plan[min(request.index, len(plan) - 1)][0], ctx, rate))
    meter = cgroup.new_meter()
    srv.on_request = cpu_hook(meter)
    rows, cols = int(param(ctx, "tty_rows", 40)), int(param(ctx, "tty_cols", 120))
    term = procio.Pty(h.tui_argv(), h.env, h.cwd, meter, rows=rows, cols=cols, echo=False, profile=param(ctx, "terminal", "xterm"))
    sample = {"terminal": param(ctx, "terminal", "xterm"), "tty": f"{cols}x{rows}", "renderer": arm.renderer.get("pty", "default"), "stream_rate_tps": rate}
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not any(ANSI.sub(b"", c).strip() for _, c in term.chunks):
            with term.cond:
                term.cond.wait(0.05)
        if not term.chunks:
            return {"failure": "no visible output within 60 s"}
        if term.wait_quiet(0.8, 60) is None:
            return {"failure": "the screen never settled before the prompt"}
        for index, (label, size) in enumerate(plan):
            mark = len(term.chunks)
            term.type(PROMPT)
            time.sleep(0.15)
            term.type("\r")
            if not srv.wait_requests(index + 1, 60):
                return {"failure": f"the prompt for answer {label} never reached the endpoint" + term.diagnosis()}
            req = srv.requests[index]
            word = needle(shape, size)
            t_marker = term.wait_text(end_marker(label), answer_timeout(ctx, size, rate), since=mark, visible=True)
            if t_marker is None:
                return {"failure": f"answer {label} never finished on screen within the time allowed"}
            t_settled = term.wait_quiet(0.4, 30) or t_marker
            cpu_end = meter.cpu_ms()
            instr_end = meter.perf().get("instructions")
            chunks = [(t, c) for t, c in term.chunks[mark:]]
            t_first = term.wait_text(word, 0.01, since=mark, visible=True)  # the heading may arrive split across terminal writes
            tokens = size / CHARS_PER_TOKEN
            sample[f"{label}_cpu_ms_per_1k_tokens"] = (cpu_end - req.hook) / (tokens / 1000)
            start_instr = (getattr(req, "hook_perf", None) or {}).get("instructions")
            if instr_end is not None and start_instr is not None:
                sample[f"{label}_instructions_per_1k_tokens"] = (instr_end - start_instr) / (tokens / 1000)
            sample[f"{label}_wall_ms"] = ms(req.t_start, t_marker)
            if t_first is not None:
                sample[f"{label}_first_paint_ms"] = ms(req.t_start, t_first)
            sample[f"{label}_bytes_out"] = sum(len(c) for _, c in chunks)
            sample[f"{label}_settle_ms"] = ms(t_marker, t_settled)
        term.type("\x04")
        procio.wait(meter, term.proc, 5)
        sample.update(peak_rss_mib=meter.max_proc_rss_mib(), peak_mem_mib=meter.peak_mem_mib(), cpu_ms=meter.cpu_ms(), meter=meter.mode, **meter.perf())
        return wire.declare(sample, len(plan), len(plan))   # one answer per size, one request each
    finally:
        term.close()
        meter.close()
        srv.on_request = None


def print_sample(ctx, arm, shape):
    skip_unless(ctx, arm, "print")
    srv = ctx.server
    rate = rate_of(ctx, "print")
    sample = {"stream_rate_tps": rate}
    for label, size in sizes(ctx):
        h = ctx.harness(arm, f"stream-print-{shape}-{label}")
        srv.reset(policy=lambda request, label=label, size=size: answer_step(shape, size, label, ctx, rate))
        meter = cgroup.new_meter()
        srv.on_request = cpu_hook(meter)
        try:
            res = procio.Batch(h.print_argv(PROMPT), h.env, h.cwd, meter, max(ctx.opts.timeout, 600)).run()
        finally:
            meter.close()
            srv.on_request = None
        if res["timed_out"] or res["code"] != 0:
            return {"failure": f"{label}: exit {res['code']}{' (timed out)' if res['timed_out'] else ''}: {res['stderr'][-200:].strip()}"}
        if end_marker(label) not in res["stdout"]:
            return {"failure": f"{label}: the answer's end marker never reached stdout"}
        req = next((r for r in srv.requests if r.fault is None), None)
        if req is None or req.hook is None:
            return {"failure": f"{label}: no request reached the endpoint"}
        tokens = size / CHARS_PER_TOKEN
        sample[f"{label}_cpu_ms_per_1k_tokens"] = (res["cpu_ms"] - req.hook) / (tokens / 1000)
        start_instr, end_instr = (getattr(req, "hook_perf", None) or {}).get("instructions"), (res.get("perf") or {}).get("instructions")
        if start_instr is not None and end_instr is not None:
            sample[f"{label}_instructions_per_1k_tokens"] = (end_instr - start_instr) / (tokens / 1000)
        sample[f"{label}_wall_ms"] = ms(req.t_start, res["t_exit"])
        sample[f"{label}_bytes_out"] = len(res["stdout"].encode())
        sample[f"{label}_peak_rss_mib"] = res["max_proc_rss_mib"]
    sample["meter"] = res["meter"]
    return wire.declare(sample, len(sizes(ctx)), len(sizes(ctx)))   # one answer per size, one request each


for _shape in SHAPES:
    register(Workload(id=f"streaming/tui-{_shape}", family="streaming", fn=lambda c, a, s=_shape: tui_sample(c, a, s),
                      description=f"streamed {_shape} answer in the interactive TUI, N and 10N characters"))
    register(Workload(id=f"streaming/print-{_shape}", family="streaming", fn=lambda c, a, s=_shape: print_sample(c, a, s),
                      description=f"streamed {_shape} answer in print mode, N and 10N characters"))
