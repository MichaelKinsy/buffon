# SPDX-License-Identifier: Apache-2.0
"""One metered adapter process and the turn loop every durable timing sample shares (docs/design/DURABLE.md 4.1 and 4.2).

Time comes from the runner's clock around adapter requests (`Adapter.call`); the adapter's own `adapter_ms` goes to `series.adapter_turn_ms` and no statistic reads it. After each turn the
runner sends `barrier` and `stats` (untimed) and reads the meter: CPU time, instructions and cycles, the kernel's I/O counters. The turn's CPU is the difference of two such readings. A
reading therefore includes the `barrier` and `stats` exchanges that precede it, a constant of a few requests for every arm and every turn.

Definitions (a warm turn is turn 2 to 10 of a sample, the first being cold):
  cold_ms          the runner's clock from sending `open` to the first turn's answer (the process start is not in it; `proc_start_ms` is its own field)
  open_ms          `open`'s own exchange; first_turn_ms the first turn's
  warm_turn_ms     median of the warm turns' exchanges
  ttfr_ms          median over the warm turns of: the provider's first request (adapter stamp, on the runner's clock when the clocks agree) minus the turn's send
  first_delta_ms   median over the warm turns of: first delta seen committed minus first delta emitted (two adapter stamps; stream workloads)
  *_per_turn       the mean over the warm turns of the facade's and the kernel's counts for that turn
"""
import time

from .. import stats
from ..runner import cgroup
from . import kio
from .protocol import Adapter

WARM_FROM = 1   # index of the first warm turn


class TurnFailed(RuntimeError):
    """A turn did not settle `done` where it had to."""


class Process:
    """One adapter in its own meter, from spawn to close. `host` is the sample's DurableHost."""

    def __init__(self, host, arm, timeout):
        self.host, self.arm = host, arm
        self.meter = cgroup.new_meter()
        self.adapter = Adapter(host.argv(), host.env, host.cwd, self.meter, timeout=timeout)
        self.ready_rss_mib = self.ready_pss_mib = None
        self.closed = False

    def wait_ready(self):
        self.adapter.wait_ready()
        self.ready_rss_mib = self.meter.max_proc_rss_mib()
        self.ready_pss_mib = self.meter.current_pss_mib()
        return self.adapter.ready

    def reading(self):
        """The meter's counters now: CPU, instructions, cycles, kernel I/O."""
        perf = self.meter.perf() or {}
        return {"cpu_ms": self.meter.cpu_ms(), "instructions": perf.get("instructions"), "cycles": perf.get("cycles"), "kio": kio.read(self.meter)}

    def settle(self):
        """`barrier`, `stats` with reset, then the meter's reading: the counters of everything since the last settle. Returns (stats response, reading)."""
        self.adapter.call("barrier")
        st = self.adapter.call("stats", reset=True)
        return st, self.reading()

    def end_rss_mib(self):
        snap = self.meter.snapshot()
        return None if snap is None else snap["rss_mib"]

    def close(self, grace=15.0):
        if self.closed:
            return
        self.closed = True
        self.adapter.close(grace)

    def release(self):
        self.close()
        self.meter.close()


KINDS = {"read": ("select", "read"), "write": ("insert", "update", "delete", "write"), "ddl": ("ddl",), "pragma": ("pragma",)}   # the statement kinds a sample reports apart; anything else is `other`


def sql_kinds(st):
    """{read, write, ddl, pragma, other}: the facade's statement counts grouped by kind (the adapters count by the first word of the SQL; docs/DURABLE-ADAPTERS.md 6.1)."""
    stmts = st.get("sql", {}).get("stmts", {})
    out = {k: sum(stmts.get(n, 0) for n in names) for k, names in KINDS.items()}
    out["other"] = sum(v for n, v in stmts.items() if not any(n in names for names in KINDS.values()))
    return out


def sql_totals(st):
    """(statements, commits, rows returned, bytes returned) of a `stats` response."""
    sql = st.get("sql", {})
    return sum(sql.get("stmts", {}).values()), sql.get("commits", 0), sql.get("rows_returned", 0), sql.get("bytes_returned", 0)


def run_turns(proc, plan, stream=False, allow_unanswered=False, baseline=None, on_turn=None):
    """Drive `plan` (a list of (conversation index, script turn number)) one turn at a time and return the rows: one dict per turn with the runner's wall time and the counters of that
    turn. `baseline` is the reading and stats to difference the first turn against (taken after `open`). A turn that does not settle `done` raises TurnFailed unless `allow_unanswered`."""
    rows = []
    prev = baseline if baseline is not None else proc.reading()
    ad = proc.adapter
    for conv, n in plan:
        ex = ad.call("turn", conv=conv, n=n, request_id=f"t{n}", stream=bool(stream))
        status = ex.get("status")
        if status != "done" and not allow_unanswered:
            raise TurnFailed(f"turn {n} of conversation {conv} settled {status!r}" + (f": {ex.get('reason')}" if ex.get("reason") else ""))
        st, cur = proc.settle()
        stmts, commits, rows_ret, bytes_ret = sql_totals(st)
        first = ad.to_runner_clock(ex.get("first_request_mono_ns"))
        fd, fs = ex.get("first_delta_mono_ns"), ex.get("delta_seen_mono_ns")
        row = {"n": n, "conv": conv, "status": status, "turn_ms": ex.ms, "adapter_ms": ex.get("adapter_ms"), "ttfr_ms": None if first is None else (first - ex.t_send) / 1e6,
               "first_delta_ms": None if fd is None or fs is None else (fs - fd) / 1e6, "model_ms": None if ex.get("model_ns") is None else ex["model_ns"] / 1e6,
               "cpu_ms": cur["cpu_ms"] - prev["cpu_ms"], "stmts": stmts, "kinds": sql_kinds(st), "commits": commits, "rows_returned": rows_ret, "bytes_returned": bytes_ret,
               "requests": ex.get("requests"), "reason": ex.get("reason")}
        for k in ("instructions", "cycles"):
            row[k] = None if cur[k] is None or prev[k] is None else cur[k] - prev[k]
        d = kio.delta(cur["kio"], prev["kio"])
        row["wchar"], row["rchar"] = d.get("wchar"), d.get("rchar")
        rows.append(row)
        prev = cur
        if on_turn:
            on_turn(row)
    return rows


def _values(rows, key):
    return [r[key] for r in rows if r.get(key) is not None]


def _median(values):
    return stats.median(values) if values else None


def _mean(values):
    return sum(values) / len(values) if values else None


def put(out, key, value):
    """A field is absent when the environment could not produce it, never zero."""
    if value is not None:
        out[key] = value


def turn_fields(rows, open_ms=None, cold_ms=None):
    """The sample fields of a list of turn rows: cold (first row), warm (the others), the per-turn means and the series."""
    out = {}
    warm = rows[WARM_FROM:]
    put(out, "first_turn_ms", rows[0]["turn_ms"] if rows else None)
    put(out, "open_ms", open_ms)
    put(out, "cold_ms", cold_ms)
    put(out, "warm_turn_ms", _median(_values(warm, "turn_ms")))
    put(out, "ttfr_ms", _median(_values(warm, "ttfr_ms")))
    put(out, "first_delta_ms", _median(_values(warm, "first_delta_ms")))
    put(out, "model_ms_per_turn", _mean(_values(warm, "model_ms")))
    put(out, "warm_cpu_ms", _median(_values(warm, "cpu_ms")))
    put(out, "warm_instructions", _median(_values(warm, "instructions")))
    put(out, "warm_cycles", _median(_values(warm, "cycles")))
    put(out, "sql_stmts_per_turn", _mean(_values(warm, "stmts")))
    put(out, "sql_commits_per_turn", _mean(_values(warm, "commits")))
    if warm:
        for kind in ("read", "write", "ddl", "pragma"):
            put(out, f"sql_{kind}_stmts_per_turn", _mean([r["kinds"][kind] for r in warm]))
    put(out, "rows_returned_per_turn", _mean(_values(warm, "rows_returned")))
    put(out, "bytes_returned_per_turn", _mean(_values(warm, "bytes_returned")))
    put(out, "wchar_bytes_per_turn", _mean(_values(warm, "wchar")))
    put(out, "rchar_bytes_per_turn", _mean(_values(warm, "rchar")))
    out["measured_turns"] = len(rows)
    out["series"] = {"turn_ms": [r["turn_ms"] for r in rows], "adapter_turn_ms": [r["adapter_ms"] for r in rows]}
    return out


def process_fields(proc):
    """What the whole process tree used, read after the adapter exited: CPU time, instructions, cycles, peak memory, the process start."""
    out = {"meter": proc.meter.mode}
    put(out, "cpu_ms", proc.meter.cpu_ms())
    perf = proc.meter.perf() or {}
    put(out, "instructions", perf.get("instructions"))
    put(out, "cycles", perf.get("cycles"))
    put(out, "perf_scope", perf.get("perf_scope"))
    put(out, "peak_mem_mib", proc.meter.peak_mem_mib())
    put(out, "peak_rss_mib", proc.meter.max_proc_rss_mib())
    put(out, "ready_rss_mib", proc.ready_rss_mib)
    put(out, "pss_mib", proc.ready_pss_mib)
    put(out, "proc_start_ms", proc.adapter.proc_start_ms)
    return out


def open_and_turns(proc, open_fields, plan, **kw):
    """The cold path of a sample: send `open`, drive `plan`; returns (open exchange, rows, cold_ms). cold_ms is `open`'s exchange plus the first turn's: the runner's clock from the send of
    `open` to the first answer, less the runner's own reading of the meter between the two."""
    opened = proc.adapter.call("open", **open_fields)
    rows = run_turns(proc, plan, baseline=proc.reading(), **kw)
    return opened, rows, (opened.ms + rows[0]["turn_ms"]) if rows else None
