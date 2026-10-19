# SPDX-License-Identifier: MIT
# Adapted from pigbench's soak.py (bench/evals of the PiG repository): the arms come from the runner, the result is a flat sample per arm.
"""Soak: scripted turns against one RPC process per arm for minutes, with the process tree's resources sampled at a fixed interval (DESIGN.md axis D, leaks).

Every arm (and its A/A copy) runs at the same time on the same machine, each in its own cgroup against its own mock endpoint, so all see the same load. Each interval
the workload records processes, threads, open file descriptors, resident and proportional memory and CPU of the whole tree. Compaction on a small context window keeps
the transcript bounded, so growth in any of these is a leak, not the work. After the run a series is judged flat when its second half stays within a declared band:
descriptors, threads and processes within max(2, 5% of the median), resident memory within 10% of the median; a second half with fewer than 3 samples is `undecided`.

  soak/realistic   a person's pace: a pause of `soak_think_ms` (default 2,000) between turns
  soak/stress      no pause between turns: the harness is never idle

Parameters: soak_minutes (default 12), soak_interval_s (15), soak_think_ms (2000, realistic only). A soak runs once per session; repeat sessions to replicate.
"""
import threading
import time

from .. import stats
from ..mock import MockServer, agentic_policy
from . import Workload, register
from .overhead import Ctx, drive_turns, start_rpc, wait_ready, skip_unless, Skip
from .streaming import param

FLAT_COUNT_BAND = (2, 0.05)  # absolute floor, fraction of the median
FLAT_RSS_BAND = 0.10
COMPACTION = {"enabled": True, "reserveTokens": 8000, "keepRecentTokens": 6000}


def second_half(values):
    return values[len(values) // 2:]


def slope_per_hour(times, values):
    """Least-squares slope of values over times (seconds), per hour. 0.0 for fewer than two points."""
    n = len(times)
    if n < 2:
        return 0.0
    mt, mv = sum(times) / n, sum(values) / n
    den = sum((t - mt) ** 2 for t in times)
    return 0.0 if den == 0 else 3600 * sum((t - mt) * (v - mv) for t, v in zip(times, values)) / den


def judge(series, metric):
    """{'flat': bool, 'median', 'spread', 'slope_per_h'} for one metric over the second half of a sampled series."""
    rows = [(r["t_s"], r[metric]) for r in series if r.get(metric) is not None]
    half = second_half(rows)
    if len(half) < 3:
        return {"flat": None, "reason": "fewer than 3 samples in the second half"}
    vals = [v for _, v in half]
    med = stats.median(vals)
    spread = max(vals) - min(vals)
    if metric in ("rss_mib", "pss_mib"):
        band = FLAT_RSS_BAND * med
    else:
        band = max(FLAT_COUNT_BAND[0], FLAT_COUNT_BAND[1] * med)
    return {"flat": spread <= band, "median": med, "spread": spread, "band": band, "slope_per_h": slope_per_hour([t for t, _ in half], vals)}


def partial_name(arm_id):
    return f"raw.partial.{arm_id}.json"


def run_arm(arm, ctx, server, opts, stop, out):
    """One arm's soak loop and sampler. Fills out['series'], out['turns'], out['failure'].

    `stop` is an external abort that this function only reads, so one Event may be shared by every arm: an arm that fails or finishes ends only its own run."""
    done = threading.Event()
    ctx.harness(arm, "soak", extensions=(), compaction=COMPACTION, context_window=32000)
    server.reset(policy=agentic_policy(ctx._harnesses[(arm.id, "soak")].cwd, tool_turns=1))
    h, meter, rpc = start_rpc(ctx, arm, "soak", False, COMPACTION, 32000)
    out["series"], out["turns"] = [], 0
    try:
        if wait_ready(rpc) is None:
            out["failure"] = "no get_state response" + rpc.diagnosis()
            return
        t0 = time.monotonic()

        def sampler():
            nxt = t0
            while not done.is_set():
                snap = meter.snapshot()
                if snap is None:
                    out["failure"] = "this host has no per-process /proc accounting for the meter"
                    done.set()
                    return
                out["series"].append(dict(snap, t_s=round(time.monotonic() - t0, 1), turns=out["turns"]))
                nxt += opts.interval
                done.wait(max(0, nxt - time.monotonic()))

        thread = threading.Thread(target=sampler, daemon=True)
        thread.start()
        while not done.is_set() and not stop.is_set() and time.monotonic() - t0 < opts.seconds:
            rows = []
            bad = drive_turns(ctx, rpc, meter, 1, rows)
            if bad:
                out["failure"] = bad
                break
            out["turns"] += 1
            with rpc.cond:  # the reader keeps every record; a soak run must not
                del rpc.records[:]
                rpc.cursor = 0
            if opts.think_ms:
                done.wait(opts.think_ms / 1000)
        done.set()
        thread.join(5)
        rpc.close()
    finally:
        done.set()
        if rpc.proc.poll() is None:
            rpc.close(grace=1)
        meter.close()
        # This meter's own observations: the module-wide egress.OBSERVED is shared by the arms running in parallel threads.
        if getattr(meter, "egress", None):
            out["egress"] = sorted(meter.egress)


REQUIRED = ("processes", "threads", "fds", "rss_mib")  # pss_mib is judged where the host has smaps_rollup


def summarize(out):
    """flat is True only when every required series was judged flat; a series too short to judge leaves the arm undecided (None), never flat."""
    series = out.get("series", [])
    verdict = {m: judge(series, m) for m in REQUIRED + ("pss_mib",)}
    if out.get("failure") or any(verdict[m]["flat"] is False for m in verdict):
        flat = False
    elif any(verdict[m]["flat"] is None for m in REQUIRED):
        flat = None
    else:
        flat = True
    return {"turns": out.get("turns", 0), "samples": len(series), "failure": out.get("failure"), "verdict": verdict, "flat": flat}


def sample_of(arm_id, out):
    """The flat raw sample of one arm's soak: verdicts and slopes as metrics, the series under `series`."""
    s = summarize(out)
    rec = {"turns": s["turns"], "series_samples": s["samples"], "flat": s["flat"] is True, "undecided": s["flat"] is None}
    for metric, v in s["verdict"].items():
        rec[f"{metric}_flat"] = v["flat"]
        if v.get("slope_per_h") is not None:
            rec[f"{metric}_slope_per_h"] = v["slope_per_h"]
            rec[f"{metric}_median"] = v["median"]
            rec[f"{metric}_spread"] = v["spread"]
    if out.get("failure"):
        rec["failure"] = out["failure"]
    if out.get("egress"):
        rec["failure"] = f"egress: the harness connected to {', '.join(out['egress'])}"
    rec["series"] = {"samples": out.get("series", [])}
    return rec


def soak(label, session, ctx, instances):
    p = session.plan
    opts = type("SoakOpts", (), {})()
    opts.seconds = float(param(ctx, "soak_minutes", 12)) * 60
    opts.interval = float(param(ctx, "soak_interval_s", 15))
    opts.think_ms = int(param(ctx, "soak_think_ms", 2000)) if label == "realistic" else 0
    opts.timeout = p.timeout
    opts.api = p.apis[0] if p.apis else "openai-completions"
    opts.params = p.params
    runnable = []
    for arm in instances:
        try:
            skip_unless(ctx, arm, "rpc")
        except Skip as why:
            session.skipped.append({"arm": arm.id, "scenario": f"soak/{label}", "api": opts.api, "reason": str(why)})
            continue
        runnable.append(arm)
    outs = {}
    for arm in runnable:  # strictly serial: one harness process at a time, each arm for the whole soak, after a quiet-host check
        host, ok = session.quiet_wait()
        outs[arm.id] = {"host": host}
        if not ok:
            outs[arm.id]["failure"] = f"the host was not quiet within {p.quiet_timeout_s:.0f} s; no process was started"
            continue
        with MockServer(retain=64) as server:
            arm_ctx = Ctx(ctx.work, server, opts)
            arm_ctx._harnesses = ctx._harnesses
            run_arm(arm, arm_ctx, server, opts, threading.Event(), outs[arm.id])
    ctx.release()
    for arm in runnable:
        rec = {"arm": arm.id, "scenario": f"soak/{label}", "api": opts.api, "round": 0, "warmup": False, "t_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "soak_minutes": opts.seconds / 60, "think_ms": opts.think_ms}
        if arm.twin_of:
            rec["twin_of"] = arm.twin_of
        rec.update(outs[arm.id].get("host", {}))
        rec.update(sample_of(arm.id, outs[arm.id]))
        if "egress" in rec.get("failure", "")[:6]:
            session.violations.append({"arm": arm.id, "scenario": f"soak/{label}", "api": opts.api, "round": 0, "remotes": outs[arm.id].get("egress", [])})
        session.samples.append(rec)


register(Workload(id="soak/realistic", family="soak", apis=("openai-completions",), special=lambda s, c, i: soak("realistic", s, c, i),
                  description="12-minute soak at a person's pace; processes, threads, descriptors and memory judged flat"))
register(Workload(id="soak/stress", family="soak", apis=("openai-completions",), special=lambda s, c, i: soak("stress", s, c, i),
                  description="12-minute soak with no pause between turns"))
