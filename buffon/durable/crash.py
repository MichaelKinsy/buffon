# SPDX-License-Identifier: Apache-2.0
"""The crash matrix (docs/design/DURABLE.md 4.4): kill the process after the k-th commit of one turn, reopen the store in a new process, resume, finish.

For each workload (`durable/crash-50`, `-1000`, `-3500`, `-stream`) and each order of runtimes, the pair (writer, resumer) of the adapter arms: Pi then Pi (the control order), Pi then PiG, PiG then Pi,
PiG then PiG, and Pi then its own A/A copy (a pair that disagrees with its own copy is a flaky result, not a pass).

  1. control: the reference runs the crash turn on a copy of the fixture to its end; the commits the facade counts for the turn are C, the final store is the control's.
  2. kill points: every commit when `crash_points` is `all`, else `crash_points` of them (default 20) spaced evenly from the first to the last. The runner records k from the facade's `crashing`
     event, never from the runtime.
  3. writer: stage the fixture, `open`, `crash_after k`, send the turn: the adapter kills itself after the k-th commit returns.
  4. resumer: a new process opens a copy of the killed store (file and WAL), `resume`, resubmits the same `request_id`, waits.
  5. verdict, `resume_ok`, all of: the request has one submission in the store (the resubmission returned the existing one); no assistant entry beyond the control's count; a tool that is not replay-safe
     (`effect`) appears once in the side-effect ledger at most; and the outcome equals the reference's own outcome at the same k (the oracle, as in the reliability family), which for the control order
     itself means the final store equals the uncrashed control's, unless the runtime reports an interrupted tool (an error result), which the contract allows for a tool that is not replay-safe.

Each (order, k) is one sample: arm is the resuming arm, `crash_writer` the killed one."""
import json
import os
import shutil
import sqlite3
import time

from .. import stats
from ..mock import now_ns
from ..runner import egress
from . import driver, fixtures, gate as gatelib, script as scriptlib, specs, store
from .host import DurableHost
from .protocol import AdapterError, Died, Unsupported
from ..workloads.streaming import param


def points(total, wanted):
    """Kill points 1..total: all, or `wanted` spaced evenly including the first and the last."""
    if wanted == "all" or int(wanted) >= total:
        return list(range(1, total + 1))
    m = max(2, int(wanted))
    return sorted({1 + round(i * (total - 1) / (m - 1)) for i in range(m)})


def counts(path, request_id):
    """(submissions with the request id, assistant entries, error tool results) of a store, read by the runner's own SQLite."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        subs = con.execute("SELECT count(*) FROM submissions WHERE request_id IN (?, ?)", (request_id, json.dumps(request_id))).fetchone()[0]   # the column holds the id as JSON text
        assistants = con.execute("SELECT count(*) FROM entries WHERE json_extract(record, '$.kind') = 'pi.assistant'").fetchone()[0]
        errors = con.execute("SELECT count(*) FROM entries WHERE record LIKE '%\"isError\":true%' OR record LIKE '%\"isError\": true%'").fetchone()[0]
        return subs, assistants, errors
    finally:
        con.close()


def ledger_counts(path):
    out = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    out[line] = out.get(line, 0) + 1
    return out


def open_args(host, spath, spec, fx, create=False):
    return {"store": host.store, "script": spath, "ledger": host.ledger, "mode": "runtime", "conversations": 1, "create": create, "window_tokens": spec.window,
            "compaction": {"enabled": spec.compaction, "background_tokens": None}, "partial_interval_ms": None, "summary_fails": False, "request_log": None, "capture": None}


def control(state, ctx, arm, built, spath, spec, n, tag):
    """The uncrashed turn: (commits of the turn, the final store path (kept), its state, the counts, the ledger)."""
    host = DurableHost(arm, ctx.work, tag=f"crash-control{tag}")
    fixtures.stage(built, host)
    proc = driver.Process(host, arm, 900)
    try:
        proc.wait_ready()
        ad = proc.adapter
        ad.call("open", **open_args(host, spath, spec, built.fx))
        before = ad.call("barrier")["commits"]
        ex = ad.call("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
        if ex.get("status") != "done":
            raise AdapterError(f"the control turn settled {ex.get('status')!r}: {ex.get('reason')}")
        after = ad.call("barrier")["commits"]
        ad.call("close")
    finally:
        proc.release()
    store.checkpoint(host.store)
    keep = os.path.join(state.keep, f"crash-control-{arm.id}-{n}.sqlite")
    shutil.copyfile(host.store, keep)
    out = (after - before, keep, store.export_state(keep), counts(keep, f"t{n}"), ledger_counts(host.ledger))
    host.cleanup()
    return out


def kill_and_resume(state, ctx, writer, resumer, built, spath, spec, n, k):
    """One (writer, resumer, k): the record of the outcome. Raises AdapterError when the matrix cannot be run at all."""
    fx = built.fx
    hw = DurableHost(writer, ctx.work, tag=f"crash-w-{k}")
    hr = DurableHost(resumer, ctx.work, tag=f"crash-r-{k}")
    rec = {"k": k}
    try:
        fixtures.stage(built, hw)
        pw = driver.Process(hw, writer, 900)
        try:
            pw.wait_ready()
            ad = pw.adapter
            ad.call("open", **open_args(hw, spath, spec, fx))
            ad.call("crash_after", k=k)
            ident, _ = ad.send("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
            try:
                ad.receive(ident, "turn")
                rec["failure"] = f"the turn finished before commit {k}: no kill happened"
                return rec
            except Died as died:
                events = [e for e in died.events if e.get("event") == "crashing"]
                rec["kill_event_commit"] = events[-1].get("commit") if events else None
                rec["killed_by"] = died.code
        finally:
            pw.release()
        if rec.get("kill_event_commit") is None:
            rec["failure"] = "the adapter died without a crashing event"
            return rec
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(hw.store + suffix):
                shutil.copyfile(hw.store + suffix, hr.store + suffix)
        if os.path.exists(hw.ledger):
            shutil.copyfile(hw.ledger, hr.ledger)
        pr = driver.Process(hr, resumer, 900)
        try:
            pr.wait_ready()
            ad = pr.adapter
            opened = ad.call("open", **open_args(hr, spath, spec, fx))
            resumed = ad.call("resume")
            ex = ad.call("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
            rec["reopen_ms"] = pr.adapter.proc_start_ms + opened.ms
            rec["resume_ms"] = resumed.ms + ex.ms
            rec["status"] = ex.get("status")
            ad.call("barrier")
            ad.call("close")
        finally:
            pr.release()
        store.checkpoint(hr.store)
        rec["state"] = store.export_state(hr.store)
        rec["counts"] = counts(hr.store, f"t{n}")
        rec["ledger"] = ledger_counts(hr.ledger)
        return rec
    finally:
        hw.cleanup()
        hr.cleanup()


def verdict(rec, ctl, oracle_rec):
    """(resume_ok, [invariant failures], signature text). `ctl` is the control's (commits, path, state, counts, ledger), `oracle_rec` the reference order's record at the same k (or None for it)."""
    fails = []
    subs, assistants, errors = rec["counts"]
    if subs != 1:
        fails.append(f"{subs} submissions carry the request id after the resubmission (expected 1)")
    if assistants > ctl[3][1]:
        fails.append(f"{assistants} assistant entries, the uncrashed control has {ctl[3][1]}: a duplicated model answer")
    twice = sorted(k for k, v in rec["ledger"].items() if k.startswith("effect ") and v > 1)
    if twice:
        fails.append(f"a tool that is not replay-safe ran more than once: {', '.join(twice)}")
    if rec.get("status") != "done":
        fails.append(f"the resubmitted turn settled {rec.get('status')!r}")
    sig = {"state": store.state_digest(gatelib.comparable_state(rec["state"])), "interrupted": errors > 0, "effects": sorted(k for k in rec["ledger"] if k.startswith("effect ")), "ledger_lookups": sum(v for k, v in rec["ledger"].items() if k.startswith("lookup "))}
    if oracle_rec is None:
        a, b = gatelib.comparable_state(ctl[2]), gatelib.comparable_state(rec["state"])
        if a != b and errors == 0:
            fails.append("the final store differs from the uncrashed control's and no tool reported an interruption: " + "; ".join(store.diff_states(a, b, 3)))
    else:
        osig = oracle_rec["_sig"]
        if osig["state"] != sig["state"]:
            fails.append("the final state differs from the reference's own outcome at this kill point")
        if osig["effects"] != sig["effects"]:
            fails.append(f"the effect ledger differs from the reference's: {sig['effects']} against {osig['effects']}")
    return not fails, fails, json.dumps(sig, sort_keys=True)


def run(runner, ctx, instances, spec):
    """The special workload: every (order, kill point) of `spec`, one sample each."""
    state = getattr(ctx, "durable", None)
    p = runner.plan
    if state is None:
        return
    arms = [a for a in state.arms]
    base_rec = {"scenario": spec.id, "api": None, "round": 0, "warmup": False}

    def skip(arm_id, why):
        runner.skipped.append({"arm": arm_id, "scenario": spec.id, "api": None, "reason": why})

    fx = spec.fixture
    if fx in state.failed:
        for a in arms:
            skip(a.id, state.failed[fx])
        return
    built = state.built[fx]
    n = fx.history
    spath, _ = fixtures.measured_script(state.root, spec, state.seed, fx.variant, n, 1)
    try:
        ctl = {a.id: control(state, ctx, a, built, spath, spec, n, "") for a in arms}
    except (AdapterError, Unsupported) as error:
        for a in arms:
            skip(a.id, f"the control run could not complete: {error}")
        return
    total = ctl[state.oracle.id][0]
    wanted = param(ctx, "crash_points", 20)
    ks = points(total, wanted)
    runner.log(f"buffon: {spec.id}: {total} commits in the turn, {len(ks)} kill points, {len(arms) * len(arms) + 1} orders (those the runtimes' storage schemas allow)")
    orders = []
    for w in arms:
        for r in arms:
            writes, reads = w.adapter.get("schema_writes", 1), r.adapter.get("schema_reads", [1])
            if writes not in reads:   # a store the reader's runtime cannot open: the order cannot be run, and the grid says so rather than count it a failure
                why = f"not possible: {r.id} {r.version} opens {gatelib.schema_words(reads)}; {w.id} writes version {writes}"
                runner.skipped.append({"arm": r.id, "scenario": spec.id, "api": None, "order": f"{w.id}>{r.id}", "reason": why})
                continue
            orders.append((w, r, None))
    twin = state.twin
    if twin is not None:
        orders.append((state.oracle, twin, twin.twin_of))
    oracle_recs = {}
    for k in ks:
        for w, r, twin_of in sorted(orders, key=lambda o: (o[0] is not state.oracle or o[1] is not state.oracle)):   # the reference order first: it is the oracle of the others at this k
            host, quiet_ok = runner.quiet_wait()
            t0 = time.monotonic()
            ctx.server.context = {"arm": r.id, "scenario": spec.id, "api": None, "round": 0, "warmup": False}
            try:
                if not quiet_ok:
                    raise RuntimeError(f"the host was not quiet within {p.quiet_timeout_s:.0f} s; no process was started")
                rec = kill_and_resume(state, ctx, w, r, built, spath, spec, n, k)
            except Unsupported as why:
                skip(r.id, str(why))
                continue
            except Exception as error:   # a crash of the driver is a recorded failure
                rec = {"k": k, "failure": f"runner error: {error!r}"}
            left = sorted(egress.take())
            out = dict(base_rec, arm=r.id, order=f"{w.id}>{r.id}", crash_writer=w.id, k=k, commits_total=total, t_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), env="native", wall_s=round(time.monotonic() - t0, 2), **host)
            if r.twin_of:
                out["twin_of"] = r.twin_of
            if "failure" in rec or left:
                out["failure"] = rec.get("failure") or f"egress: the adapter connected to {', '.join(left)}"
            else:
                is_oracle = w is state.oracle and r is state.oracle
                if not is_oracle and k not in oracle_recs:
                    out["failure"] = f"the reference order {state.oracle.id}>{state.oracle.id} has no outcome at k={k} to compare with"
                    runner.samples.append(out)
                    continue
                ok, fails, sig = verdict(rec, ctl[state.oracle.id], None if is_oracle else oracle_recs[k])
                if is_oracle:
                    rec["_sig"] = json.loads(sig)
                    oracle_recs[k] = rec
                out.update(resume_ok=ok, invariant_failures="; ".join(fails), signature=sig, kill_event_commit=rec["kill_event_commit"], reopen_ms=rec["reopen_ms"], resume_ms=rec["resume_ms"],
                           duplicated_submission=rec["counts"][0] != 1, ledger=json.dumps(rec["ledger"], sort_keys=True))
            runner.samples.append(out)
            runner.log(f"buffon: {spec.id:20} {out['order']:34} k={k:<4} " + (f"FAILED: {out['failure'][:120]}" if "failure" in out else ("ok" if out["resume_ok"] else "FAIL " + out["invariant_failures"][:120])))
            runner.checkpoint()
    for rec in ctl.values():
        if os.path.exists(rec[1]):
            os.unlink(rec[1])
