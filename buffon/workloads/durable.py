# SPDX-License-Identifier: Apache-2.0
"""The durable family (docs/design/DURABLE.md 3.4): durable agent runtimes on their native SQLite, each measured through an adapter that speaks docs/DURABLE-ADAPTERS.md.

One workload = one fresh adapter process of one arm per round (a `sample`). The table of what each workload is lives in buffon/durable/specs.py; the fixtures, the equivalence gate and the floor
capture are prepared once before the first round (buffon/durable/prepare.py). Flavors:

  timing           stage the workload's fixture (a copy of a store the reference built, read once), start the adapter, `open`, ten turns; cold, warm, counters, store, memory
  cold-every-turn  a new process for each of the ten turns
  many-conv        N conversations in one store, one turn each in round robin
  grow             no store: the arm builds the history through its own loop, every turn timed
  floor-host       the adapter with no durable runtime (docs/DURABLE-ADAPTERS.md section 8)
  floor-sql        the recorded statement stream of ten turns replayed through the arm's facade and driver
  crash            the crash matrix (a special workload: buffon/durable/crash.py)

Derived after the last round (`finish`): `warm_net_ms` (warm turn less the floor-host turn of the same arm and round) and `mem_per_conv_mib` (the slope of end RSS against N)."""
import os

from .. import stats
from ..durable import driver, fixtures, script as scriptlib, specs, store
from ..durable.host import host_for
from ..durable.protocol import AdapterError, Unsupported
from . import NATIVE, Workload, register
from .overhead import Skip

COLD = "warm page cache"   # the cold-start method named in every report: the store copy is read once before timing (docs/design/DURABLE.md 6.3)


# -- shared pieces -------------------------------------------------------------------------------------------------------------------------------

def call_timeout(ctx):
    return max(float(getattr(ctx.opts, "timeout", 120) or 120), 600.0)


def check(ctx, arm, spec):
    """Skip unless `arm` can take `spec` here: it has an adapter for this environment, and the fixture and the capabilities exist."""
    if not arm.adapter:
        raise Skip("it is not a durable arm: it has no adapter, and the durable workloads drive a runtime through one (docs/DURABLE-ADAPTERS.md)")
    env = getattr(ctx.opts, "env", NATIVE)
    if env not in arm.adapter["envs"]:
        raise Skip(f"its adapter does not run in the {env} environment")
    state = getattr(ctx, "durable", None)
    if state is None:
        raise Skip("the durable family was not prepared (no fixtures, no gate)")
    why = state.skip_reason(arm, spec)
    if why:
        raise Skip(why)
    return state


def open_fields(host, script_path, spec, fx, conversations=1, create=False, mode="runtime"):
    return {"store": host.store, "script": script_path, "ledger": host.ledger, "mode": mode, "conversations": conversations, "create": create, "window_tokens": spec.window,
            "compaction": {"enabled": spec.compaction, "background_tokens": spec.background_tokens if spec.background_tokens is not None else (fx.background_tokens if fx else None)},
            "partial_interval_ms": spec.partial_ms, "summary_fails": spec.summary_fails, "request_log": None, "capture": None}


def base_fields(ctx, spec, proc, opened, built=None):
    out = {"env": getattr(ctx.opts, "env", NATIVE), "window_tokens": spec.window, "compaction": "on" if spec.compaction else "off", "shape": spec.shape, "cold_start": COLD,
           "runtime_versions": (proc.adapter.ready or {}).get("runtime_versions", {}), "runtime_settings": (opened or {}).get("settings", {}), "lane": spec.lane}
    if built is not None:
        out.update(built.sample_fields)
        out["turns"] = built.fx.history
        out["compaction_ids"] = built.facts.get("compaction_ids", [])
        if built.fx.conversations > 1:
            out["conversations"] = built.fx.conversations
    return out


def store_fields(state, host, turns_total):
    """The runner opens the store itself after the adapter closed it: checkpoint, then sizes and rows per table (docs/design/DURABLE.md 4.3 layer C)."""
    store.checkpoint(host.store)
    ins = store.inspect(host.store)
    out = {"store_bytes": ins["store_bytes"], "store_tables": ins["store_tables"]}
    if turns_total:
        out["store_bytes_per_turn"] = ins["store_bytes"] / turns_total
    return out


def failure(error, proc=None):
    text = f"{type(error).__name__}: {error}"
    if proc is not None and proc.adapter.tail():
        text += f" (adapter stderr: {proc.adapter.tail(300)!r})"
    return {"failure": text}


def finish_sample(sample, proc, rows, opened, spec_turns_total, state, host, extra=None, arm=None, built=None):
    """The fields every timing-style sample ends with."""
    sample.update(driver.turn_fields(rows, opened.ms if opened is not None else None, (opened.ms + rows[0]["turn_ms"]) if opened is not None and rows else None))
    driver.put(sample, "end_rss_mib", proc.end_rss_mib())
    proc.adapter.call("close")
    proc.close()
    sample.update(driver.process_fields(proc))
    if "cold_ms" in sample and "proc_start_ms" in sample:
        sample["ready_to_answer_ms"] = sample["proc_start_ms"] + sample["cold_ms"]
    sample.update(store_fields(state, host, spec_turns_total))
    sample["equivalence"] = "ok"
    if built is not None and arm is not None:
        ident = state.gate.row_identical.get(built.fx.label, {}).get(arm.id.removesuffix("-b")) if state.gate else None
        if ident is not None:
            sample["row_identical"] = ident
    if extra:
        sample.update(extra)
    return sample


def guarded(fn):
    """A sample function whose adapter said `unsupported` is skipped with the adapter's own sentence; one whose adapter died or broke the protocol is a recorded failure."""
    def run(ctx, arm, spec):
        try:
            return fn(ctx, arm, spec)
        except Unsupported as why:
            raise Skip(str(why)) from None
        except (AdapterError, driver.TurnFailed) as error:
            return failure(error, getattr(error, "proc", None))
    return run


def measured_plan(spec, built):
    h = built.fx.history
    return [(0, h + i) for i in range(spec.measured)]


# -- timing --------------------------------------------------------------------------------------------------------------------------------------

def timing(ctx, arm, spec):
    state = check(ctx, arm, spec)
    built = state.built[spec.fixture]
    fx = spec.fixture
    host = host_for(ctx, arm, spec.id.split("/", 1)[1])
    fixtures.stage(built, host)
    spath, sfacts = fixtures.measured_script(state.root, spec, state.seed, fx.variant, fx.history)
    proc = driver.Process(host, arm, call_timeout(ctx))
    try:
        proc.wait_ready()
        opened, rows, cold = driver.open_and_turns(proc, open_fields(host, spath, spec, fx), measured_plan(spec, built), stream=spec.stream, allow_unanswered=spec.summary_fails)
        sample = base_fields(ctx, spec, proc, opened, built)
        sample["measured_script_sha256"] = sfacts["sha256"]
        extra = {}
        if spec.summary_fails:
            failed = [r for r in rows if r["status"] != "done"]
            extra = {"compaction_failures": len(failed), "failed_turns": len(failed)}
        return finish_sample(sample, proc, rows, opened, fx.history * fx.conversations + len(rows), state, host, extra, arm, built)
    except (AdapterError, driver.TurnFailed) as error:
        return failure(error, proc)
    finally:
        proc.release()


def cold_every_turn(ctx, arm, spec):
    state = check(ctx, arm, spec)
    built = state.built[spec.fixture]
    fx = spec.fixture
    host = host_for(ctx, arm, spec.id.split("/", 1)[1])
    fixtures.stage(built, host)
    spath, sfacts = fixtures.measured_script(state.root, spec, state.seed, fx.variant, fx.history)
    rows, cold, opens, starts, cpu, instr, cycles, peaks, rss = [], [], [], [], 0.0, 0, 0, [], []
    sample, have_instr, last = None, True, None
    for i in range(spec.measured):
        proc = driver.Process(host, arm, call_timeout(ctx))
        try:
            proc.wait_ready()
            opened, one, c = driver.open_and_turns(proc, open_fields(host, spath, spec, fx), [(0, fx.history + i)])
            if sample is None:
                sample = base_fields(ctx, spec, proc, opened, built)
                sample["measured_script_sha256"] = sfacts["sha256"]
            rows += one
            cold.append(c)
            opens.append(opened.ms)
            starts.append(proc.adapter.proc_start_ms)
            snap = proc.end_rss_mib()
            proc.adapter.call("close")
            proc.close()
            f = driver.process_fields(proc)
            cpu += f.get("cpu_ms", 0.0)
            if "instructions" in f:
                instr, cycles = instr + f["instructions"], cycles + f.get("cycles", 0)
            else:
                have_instr = False
            peaks.append(f.get("peak_rss_mib"))
            rss.append(snap)
            last = f
        except (AdapterError, driver.TurnFailed) as error:
            return failure(error, proc)
        finally:
            proc.release()
    out = sample
    out.update(driver.turn_fields(rows, None, None))
    for k in ("warm_turn_ms", "warm_cpu_ms", "warm_instructions", "warm_cycles"):
        out.pop(k, None)   # every turn is cold here: there is no warm turn
    out.update({"cold_ms": stats.median(cold), "open_ms": stats.median(opens), "first_turn_ms": stats.median([r["turn_ms"] for r in rows]), "proc_start_ms": stats.median(starts), "cpu_ms": cpu,
                "meter": last["meter"]})
    out["ready_to_answer_ms"] = out["proc_start_ms"] + out["cold_ms"]
    if have_instr and instr:
        out.update(instructions=instr, cycles=cycles)
    peaks = [p for p in peaks if p is not None]
    if peaks:
        out["peak_rss_mib"] = max(peaks)
    rss = [r for r in rss if r is not None]
    if rss:
        out["end_rss_mib"] = stats.median(rss)
    out["series"]["cold_ms"] = cold
    out.update(store_fields(state, host, fx.history + len(rows)))
    out["equivalence"] = "ok"
    return out


def many_conv(ctx, arm, spec):
    state = check(ctx, arm, spec)
    built = state.built[spec.fixture]
    fx = spec.fixture
    host = host_for(ctx, arm, spec.id.split("/", 1)[1])
    fixtures.stage(built, host)
    one = specs.Spec(id=spec.id, description="", fixture=fx, measured=1, shape=spec.shape)
    spath, sfacts = fixtures.measured_script(state.root, one, state.seed, fx.variant, fx.history, 1)
    proc = driver.Process(host, arm, call_timeout(ctx))
    try:
        proc.wait_ready()
        plan = [(i, fx.history) for i in range(fx.conversations)]
        opened, rows, cold = driver.open_and_turns(proc, open_fields(host, spath, spec, fx, conversations=fx.conversations), plan)
        sample = base_fields(ctx, spec, proc, opened, built)
        sample["conversations"] = fx.conversations
        return finish_sample(sample, proc, rows, opened, fx.history * fx.conversations + len(rows), state, host, None, arm, built)
    except (AdapterError, driver.TurnFailed) as error:
        return failure(error, proc)
    finally:
        proc.release()


def grow(ctx, arm, spec):
    if not arm.adapter:
        raise Skip("it is not a durable arm: it has no adapter")
    state = ctx.durable
    n = spec.measured
    host = host_for(ctx, arm, spec.id.split("/", 1)[1])
    spath, sfacts = scriptlib.cached(os.path.join(state.root, "scripts"), state.seed, "repeating", scriptlib.history_plan("mixed", n))
    proc = driver.Process(host, arm, call_timeout(ctx))
    try:
        proc.wait_ready()
        plan = [(0, i) for i in range(n)]
        fields = {"store": host.store, "script": spath, "ledger": host.ledger, "mode": "runtime", "conversations": 1, "create": True, "window_tokens": 200_000,
                  "compaction": {"enabled": True, "background_tokens": None}, "partial_interval_ms": None, "summary_fails": False, "request_log": None, "capture": None}
        opened, rows, cold = driver.open_and_turns(proc, fields, plan)
        sample = {"env": NATIVE, "turns": n, "window_tokens": 200_000, "compaction": "on", "shape": "mixed", "cold_start": "empty store", "fixture_sha256": sfacts["sha256"], "fixture_seed": state.seed,
                  "fixture_writer": arm.id.removesuffix("-b"), "fixture_variant": "repeating", "runtime_versions": (proc.adapter.ready or {}).get("runtime_versions", {}), "runtime_settings": opened.get("settings", {}), "lane": spec.lane}
        times = [r["turn_ms"] for r in rows]
        sample = finish_sample(sample, proc, rows, opened, n, state, host, {"build_ms": sum(times), "early_turn_ms": stats.median(times[:10]), "late_turn_ms": stats.median(times[-10:])}, arm)
        sample["measured_turns"] = len(rows)
        sample["series"] = {"turn_ms": times, "adapter_turn_ms": [r["adapter_ms"] for r in rows]}
        return sample
    except (AdapterError, driver.TurnFailed) as error:
        return failure(error, proc)
    finally:
        proc.release()


# -- floors --------------------------------------------------------------------------------------------------------------------------------------

def floor_host(ctx, arm, spec):
    if not arm.adapter:
        raise Skip("it is not a durable arm: it has no adapter")
    state = getattr(ctx, "durable", None)
    root = state.root if state else fixtures.cache_root(ctx.opts)
    seed = state.seed if state else specs.SEED
    host = host_for(ctx, arm, spec.id.split("/", 1)[1])
    spath, sfacts = scriptlib.cached(os.path.join(root, "scripts"), seed, "repeating", scriptlib.measured_plan("mixed", 0, spec.measured + 10))
    proc = driver.Process(host, arm, call_timeout(ctx))
    try:
        proc.wait_ready()
        fields = {"store": host.store, "script": spath, "ledger": host.ledger, "mode": "floor", "conversations": 1, "create": True, "window_tokens": 200_000,
                  "compaction": {"enabled": True, "background_tokens": None}, "partial_interval_ms": None, "summary_fails": False, "request_log": None, "capture": None}
        opened, rows, cold = driver.open_and_turns(proc, fields, [(0, i) for i in range(spec.measured)])
        sample = {"env": getattr(ctx.opts, "env", NATIVE), "shape": "mixed", "cold_start": "empty store", "fixture_sha256": sfacts["sha256"], "fixture_seed": seed, "runtime_versions": (proc.adapter.ready or {}).get("runtime_versions", {}),
                  "runtime_settings": opened.get("settings", {}), "lane": spec.lane}
        return finish_sample(sample, proc, rows, opened, 0, state, host, None, arm)
    except (AdapterError, driver.TurnFailed) as error:
        return failure(error, proc)
    finally:
        proc.release()


def floor_sql(ctx, arm, spec):
    state = check(ctx, arm, spec)
    if not state.floor_stream:
        raise Skip(state.floor_error or "the statement stream of the measured turns was not captured")
    built = state.built[spec.fixture]
    fx = spec.fixture
    host = host_for(ctx, arm, "floor-sql")
    fixtures.stage(built, host)
    spath, sfacts = fixtures.measured_script(state.root, spec, state.seed, fx.variant, fx.history)
    proc = driver.Process(host, arm, call_timeout(ctx))
    try:
        proc.wait_ready()
        opened = proc.adapter.call("open", **open_fields(host, spath, spec, fx, mode="floor"))
        base = proc.reading()
        ex = proc.adapter.call("floor_sql", stream_file=state.floor_stream, from_turn=fx.history, turns=spec.measured)
        st, cur = proc.settle()
        stmts, commits, rows_ret, bytes_ret = driver.sql_totals(st)
        sample = base_fields(ctx, spec, proc, opened, built)
        n = spec.measured
        sample.update({"replay_ms_per_turn": ex.ms / n, "warm_turn_ms": ex.ms / n, "stmts_replayed": ex.get("stmts"), "commits_replayed": ex.get("commits"),
                       "series": {"adapter_turn_ms": [x / 1e6 for x in ex.get("per_turn_ns", [])]}, "measured_turns": n})
        sample["cpu_ms_replay"] = cur["cpu_ms"] - base["cpu_ms"]
        for key, value in (("sql_stmts_per_turn", stmts / n), ("sql_commits_per_turn", commits / n), ("rows_returned_per_turn", rows_ret / n), ("bytes_returned_per_turn", bytes_ret / n)):
            sample[key] = value
        d = driver.kio.delta(cur["kio"], base["kio"])
        driver.put(sample, "wchar_bytes_per_turn", None if "wchar" not in d else d["wchar"] / n)
        driver.put(sample, "rchar_bytes_per_turn", None if "rchar" not in d else d["rchar"] / n)
        driver.put(sample, "warm_instructions", None if cur["instructions"] is None or base["instructions"] is None else (cur["instructions"] - base["instructions"]) / n)
        proc.adapter.call("close")
        proc.close()
        sample.update(driver.process_fields(proc))
        sample["equivalence"] = "ok"
        return sample
    except (AdapterError, driver.TurnFailed) as error:
        return failure(error, proc)
    finally:
        proc.release()


FLAVORS = {"timing": timing, "cold-every-turn": cold_every_turn, "many-conv": many_conv, "grow": grow, "floor-host": floor_host, "floor-sql": floor_sql}


def floor_sample(ctx, arm):
    """The floor-host sample of `arm`: what the calibration of a durable run measures (the reference against its own A/A copy)."""
    ctx.opts.env = NATIVE
    return floor_host(ctx, arm, specs.SPECS["durable/floor-host"])


# -- derived metrics -----------------------------------------------------------------------------------------------------------------------------

def live(sample):
    return "failure" not in sample and sample.get("scenario", "").startswith("durable/")


def finish(runner):
    """After the last round: `warm_net_ms` and `mem_per_conv_mib` on the samples they derive from. Idempotent; the engine calls it once for each workload that names it."""
    if getattr(runner, "_durable_finished", False):
        return
    runner._durable_finished = True
    floors = {}
    for s in runner.samples:
        if live(s) and s["scenario"] == "durable/floor-host" and isinstance(s.get("warm_turn_ms"), (int, float)):
            floors[(s["arm"], s["round"], s.get("env"))] = s["warm_turn_ms"]
    for s in runner.samples:
        if live(s) and s["scenario"] != "durable/floor-host" and isinstance(s.get("warm_turn_ms"), (int, float)) and s.get("lane") != "floor":
            floor = floors.get((s["arm"], s["round"], s.get("env")))
            if floor is not None:
                s["warm_net_ms"] = s["warm_turn_ms"] - floor
    groups = {}
    for s in runner.samples:
        if live(s) and s["scenario"].startswith("durable/many-conv-") and isinstance(s.get("end_rss_mib"), (int, float)):
            groups.setdefault((s["arm"], s["round"]), []).append(s)
    for members in groups.values():
        xs = [m["conversations"] for m in members]
        if len(set(xs)) < 2:
            continue
        mx, my = sum(xs) / len(xs), sum(m["end_rss_mib"] for m in members) / len(members)
        slope = sum((x - mx) * (m["end_rss_mib"] - my) for x, m in zip(xs, members)) / sum((x - mx) ** 2 for x in xs)
        for m in members:
            m["mem_per_conv_mib"] = slope


# -- registration --------------------------------------------------------------------------------------------------------------------------------

def _fn(spec):
    base = FLAVORS.get(spec.flavor)
    return None if base is None else (lambda ctx, arm, s=spec, f=base: guarded(f)(ctx, arm, s))


def _register():
    from ..durable import crash
    for spec in specs.SPECS.values():
        special = (lambda runner, ctx, instances, s=spec: crash.run(runner, ctx, instances, s)) if spec.flavor == "crash" else None
        register(Workload(id=spec.id, family="durable", fn=_fn(spec), apis=(None,), special=special, description=spec.description, rounds=spec.rounds, aa=spec.aa, envs=(NATIVE,), finish=finish))


_register()
