# SPDX-License-Identifier: Apache-2.0
"""Long session: what a harness costs as a conversation grows (DESIGN.md axis C).

  longsession/resume-n, resume-n10   resume a generated Pi session of N or 10N turns in RPC mode and answer one prompt: the time and CPU to be ready, the memory after
                                     resume, and the cost of the first turn on the loaded history. Four entries per turn; automatic compaction is off, so the whole history is sent.
  longsession/resume-n-varied, resume-n10-varied
                                     the same, on the varied twin of the session: the same message and tool-call structure and byte size, other words in every turn, so a gain from
                                     deduplicating or compressing repeated content shows as a difference between the two rows. The sample records the seed and the session's sha256.
  longsession/grow-n, grow-n10       one RPC process driven through N or 10N live turns (a tool call and a reply each) with automatic compaction on a small context window:
                                     first-turn against last-turn CPU, RSS growth, session bytes on disk.

Only arms that read Pi's session files take part in the resume workloads. Parameters: session_n (default 100 turns; 10N = 1,000), session_seed (1).
"""
import os

from ..fixtures import sessions
from ..mock import agentic_policy
from ..runner import cgroup, procio, wire
from . import Workload, register
from .overhead import cpu_hook, drive_turns, is_turn_end, ms, one_long, skip_unless, wait_ready  # noqa: F401
from .streaming import param

BIG_CONTEXT = {"context_window": 4_000_000, "compaction": {"enabled": False}}
LADDER_TOKENS = 4_200_000                                                       # the top rung of the session-size ladder: a session of 4.2M tokens
LADDER_CONTEXT = {"context_window": 5_000_000, "compaction": {"enabled": False}}   # declared window above the rung, so no arm compacts before it (docs/design/SCALE.md)


def turns_for_tokens(fixtures, tokens, seed):
    """How many generated turns make a session of about `tokens` tokens (request bytes / 4, the mock's own count): a 100-turn session fixes the bytes per turn."""
    _path, facts = sessions.cached(fixtures, 100, seed)
    return max(1, round(tokens * sessions.BYTES_PER_TOKEN / (facts["bytes"] / 100)))


def turns_for(ctx, label):
    n = int(param(ctx, "session_n", 100))
    if label == "t4m2":
        return turns_for_tokens(os.path.join(os.path.dirname(ctx.work), "fixtures"), int(param(ctx, "ladder_tokens", LADDER_TOKENS)), int(param(ctx, "session_seed", 1)))
    return n * 10 if label == "n10" else n


def resume_sample(ctx, arm, label, variant=sessions.REPEATING):
    skip_unless(ctx, arm, "rpc_resume")
    if not arm.pi_session_format:
        from .overhead import Skip
        raise Skip("it does not read or write Pi session files")
    turns = turns_for(ctx, label)
    fixtures = os.path.join(os.path.dirname(ctx.work), "fixtures")
    src, facts = sessions.cached(fixtures, turns, int(param(ctx, "session_seed", 1)), variant)
    h = ctx.harness(arm, f"resume-{label}" + ("-varied" if variant == sessions.VARIED else ""), **(LADDER_CONTEXT if label == "t4m2" else BIG_CONTEXT))
    path = os.path.join(h.sessions, "resume.jsonl")
    sessions.copy_with_cwd(src, path, h.cwd)
    srv = ctx.server
    srv.reset(policy=agentic_policy(h.cwd, tool_turns=0))
    meter = cgroup.new_meter()
    srv.on_request = cpu_hook(meter)
    rpc = procio.Rpc(h.rpc_resume_argv(path), h.env, h.cwd, meter)
    rpc.cursor = 0
    rpc.dialect = arm.rpc_dialect
    try:
        got = wait_ready(rpc)
        if got is None:
            return {"failure": "no get_state response after resuming the session" + rpc.diagnosis()}
        sample = {"turns": turns, "history_bytes": facts["bytes"], "history_entries": facts["entries"], "session_variant": facts["variant"], "session_seed": facts["seed"], "session_sha256": facts["sha256"], "ready_ms": ms(rpc.t_spawn, got[0]), "ready_cpu_ms": meter.cpu_ms(),
                  "ready_rss_mib": meter.max_proc_rss_mib(), "ready_pss_mib": meter.current_pss_mib(), "meter": meter.mode}
        series = []
        bad = drive_turns(ctx, rpc, meter, 1, series)
        if bad:
            return {"failure": bad}
        main = [r for r in srv.requests if r.fault is None]
        if not main:
            return {"failure": "no request reached the endpoint"}
        if main[0].messages < facts["messages"]:
            return {"failure": f"the first request carried {main[0].messages} messages; the resumed history has {facts['messages']}: the session was not loaded"}
        row = series[0]
        sample.update(turn_wall_ms=row["wall_ms"], turn_cpu_ms=row["cpu_ms"], history_messages=main[0].messages, peak_rss_mib=meter.max_proc_rss_mib())
        rpc.close()
        sample.update(meter.perf(), cpu_ms=meter.cpu_ms(), peak_mem_mib=meter.peak_mem_mib(), session_growth_bytes=os.path.getsize(path) - facts["bytes"])
        return wire.declare(sample, 1, 1)   # one prompt, one reply: the policy runs no tool
    finally:
        if rpc.proc.poll() is None:
            rpc.close(grace=1)
        meter.close()
        srv.on_request = None


def grow_sample(ctx, arm, label):
    turns = turns_for(ctx, label)
    previous = getattr(ctx.opts, "long_turns", None)
    ctx.opts.long_turns = turns
    try:
        return one_long(ctx, arm)
    finally:
        ctx.opts.long_turns = previous


for _label, _desc in (("n", "N turns"), ("n10", "10N turns")):
    register(Workload(id=f"longsession/resume-{_label}", family="longsession", fn=lambda c, a, l=_label: resume_sample(c, a, l),
                      description=f"resume a {_desc} Pi session over RPC and answer one prompt"))
    register(Workload(id=f"longsession/resume-{_label}-varied", family="longsession", fn=lambda c, a, l=_label: resume_sample(c, a, l, sessions.VARIED),
                      description=f"resume the varied twin of a {_desc} Pi session (distinct content, the same size and structure) over RPC and answer one prompt"))
    register(Workload(id=f"longsession/grow-{_label}", family="longsession", fn=lambda c, a, l=_label: grow_sample(c, a, l),
                      description=f"grow one session through {_desc} with compaction"))


register(Workload(id="longsession/resume-4m2", family="longsession", fn=lambda c, a: resume_sample(c, a, "t4m2"),
                  description="resume a 4.2M-token Pi session over RPC and answer one prompt (the top of the session-size ladder; a stop here is a result)"))
