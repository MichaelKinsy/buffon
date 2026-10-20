# SPDX-License-Identifier: Apache-2.0
"""The equivalence gate of the durable family (docs/design/DURABLE.md 6.2), run before anything is timed.

Every arm runs the same short scripted scenarios on a copy of each fixture, and the reference arm's record is the oracle:

  base        open, three turns of the fixture's measured shape
  compaction  the fixture opened with an 8,000-token window, so the next turns compact (a summary request is answered): only for fixtures built with compaction on
  documents   three application-document edits, then a turn          (once, on the first fixture: a capability scenario)
  tasks       a turn whose tool creates three child tasks            (once)
  subagent    a turn whose tool owns a child conversation            (once)

and compares, with the runner reading the SQLite store itself (buffon/durable/store.py), never an arm's API:

  1. the conversation state, semantically (active transcript, document values, task outcomes, submission statuses; volatile fields removed by name);
  2. the model requests the scripted provider received, as parsed JSON (`request_log`, docs/DURABLE-ADAPTERS.md 4.4);
  3. the compaction boundaries (structural references of the head markers);
  4. cross-open: each arm opens the other arms' final stores (a copy) and `transcript` returns what the writer's own `transcript` returned;
  5. oracle determinism: the oracle against its own A/A copy. A scenario where they differ is flaky: its fixture is excluded, not timed.

A difference in 1, 2 or 4 refuses the run (exit 3) and names the fields. A difference in 3 alone is not decided by timing luck: the scenario is repeated with `background_tokens` 0, the
blocking variant of compaction, for every arm. Where that agrees, the arm does *different work* at that fixture (a goroutine scheduler and Pi's microtask order place a background
summary at different turns): the report shows its medians and no ratio (the manifest's divergence mechanism, buffon/divergence.py) and the gate says why. Where it still differs, the run is refused.
`row_identical` (the two stores' rows byte for byte, volatile columns masked) is a fact, never a refusal. A capability an arm lacks is its adapter's own `unsupported` sentence and becomes the
workload's `cannot run` reason."""
import json
import os
import shutil

from . import fixtures, script as scriptlib, specs, store
from .driver import Process
from .host import DurableHost
from .protocol import AdapterError, Unsupported

SMALL_WINDOW = 8000
SHARED_TABLES = tuple(t for t in store.DURABLE_TABLES if t != "durable_schema")   # row identity is read on the tables both schema versions have, and the version row is the one thing that must differ
CAPABILITIES = {"documents": "documents", "tasks": "tasks", "subagents": "subagent"}   # capability name -> scenario


def gate_script(root, fx, seed):
    """(path, facts) of the gate's script for fixture `fx`: turns h .. h+4 (three of the fixture's measured shape, a fanout of three tasks, a subagent) and three document strings."""
    h = fx.history
    base = "bench8" if fx.history_kind == "compat" else "mixed"
    plan = [(h, base), (h + 1, base), (h + 2, base), (h + 3, "fanout"), (h + 4, "subagent")]
    return scriptlib.cached(os.path.join(root, "scripts"), seed, fx.variant, plan, docs=3, fanout_n=3)


def scenarios(fx, capabilities):
    h = fx.history
    out = [{"name": "base", "steps": [("turns", [h, h + 1, h + 2])]}]
    if fx.compaction:
        out.append({"name": "compaction", "window": SMALL_WINDOW, "steps": [("turns", [h, h + 1])]})
    if capabilities:
        out += [{"name": "documents", "steps": [("docs", 3), ("turns", [h])], "cap": "documents"}, {"name": "tasks", "steps": [("turns", [h + 3])], "cap": "tasks"},
                {"name": "subagent", "steps": [("turns", [h + 4])], "cap": "subagents"}]
    return out


def run_scenario(state, arm, built, spath, sc, background=None, source=None, tag=""):
    """One arm in one scenario on a copy of the fixture (or of `source`, a store to open: the cross-open check). Returns the record: state, request log, transcript, store path (a kept copy)."""
    fx = built.fx
    ctx = state.ctx
    host = DurableHost(arm, ctx.work, tag=f"gate-{sc['name']}{tag}")
    proc = Process(host, arm, timeout=1800)
    rec = {"arm": arm.id, "scenario": sc["name"]}
    try:
        if source:
            shutil.copyfile(source, host.store)
        else:
            fixtures.stage(built, host)
        proc.wait_ready()
        ad = proc.adapter
        bg = background if background is not None else fx.background_tokens
        ad.call("open", store=host.store, script=spath, ledger=host.ledger, mode="runtime", conversations=1, create=False, window_tokens=sc.get("window", fx.window_tokens),
                compaction={"enabled": fx.compaction or "window" in sc, "background_tokens": bg}, partial_interval_ms=None, summary_fails=False, request_log=host.request_log, capture=None)
        statuses = []
        for kind, arg in sc["steps"]:
            if kind == "docs":
                ad.call("doc_edit", conv=0, count=arg, payload_bytes=scriptlib.DOC_BYTES, **{"from": 0})
            else:
                for n in arg:
                    ex = ad.call("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
                    statuses.append(ex.get("status"))
                    ad.call("barrier")
        rec["statuses"] = statuses
        rec["transcript"] = ad.call("transcript", conv=0)["messages"]
        ad.call("barrier")
        ad.call("close")
    except Unsupported as why:
        rec["unsupported"] = str(why)
    except AdapterError as error:
        rec["error"] = str(error)
    finally:
        proc.release()
    if "error" in rec or "unsupported" in rec:
        host.cleanup()
        return rec
    store.checkpoint(host.store)
    rec["state"] = store.export_state(host.store)
    rec["compaction"] = rec["state"]["compaction_ids"]
    rec["requests"] = _read_log(host.request_log)
    keep = os.path.join(state.keep, f"{arm.id}-{sc['name']}{tag}.sqlite")
    shutil.copyfile(host.store, keep)
    rec["store"] = keep
    host.cleanup()
    return rec


def _read_log(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def settle_tools(items, is_tool, key):
    """`items` with every run of consecutive tool results sorted by `key`. Parallel tool calls commit their results as they finish; which finishes first is the scheduler's (microtask order
    in Pi, goroutines in Go), not the work's: two runs that did the same calls and got the same results are the same work, whatever the order the results were stored in."""
    out, run = [], []
    for it in items:
        if is_tool(it):
            run.append(it)
            continue
        out += sorted(run, key=key) + [it]
        run = []
    return out + sorted(run, key=key)


def tool_run_refs(items):
    """{entry ref: canonical entry ref} for the tool results of every run: the run's entries keep the positions they have, and the sorted items take them in order."""
    mapping, run = {}, []

    def flush():
        refs = [i["ref"] for i in run]
        for it, ref in zip(sorted(run, key=_tool_key), refs):
            mapping[it["ref"]] = ref
        run.clear()
    for it in items:
        if it.get("kind") == "pi.tool-result":
            run.append(it)
        elif run:
            flush()
    if run:
        flush()
    return mapping


def _tool_key(i):
    return (i.get("digest") or "", json.dumps(i.get("by_task")))


def remap(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [remap(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: remap(v, mapping) for k, v in value.items()}
    return value


def comparable_state(state):
    """The state without what is not the work: the storage schema version (compared on its own) and the order in which a round's parallel tool results were committed (the results are
    put in a canonical order and every reference to them follows)."""
    mapping = {}
    for c in state["conversations"]:
        mapping.update(tool_run_refs(c["active"]))
    out = {k: v for k, v in state.items() if k != "schema_version"}
    out["conversations"] = [dict(c, active=[{k: v for k, v in i.items() if k != "ref"} for i in settle_tools(c["active"], lambda i: i.get("kind") == "pi.tool-result", _tool_key)]) for c in state["conversations"]]
    for key in ("tasks", "submissions", "head_markers"):
        for c in out["conversations"]:
            c[key] = remap(c[key], mapping)
    out["documents"] = remap(out["documents"], mapping)
    out["compaction_ids"] = remap(out["compaction_ids"], mapping)
    return out


def comparable_messages(messages):
    return settle_tools(messages, lambda m: m.get("r") == "tool", lambda m: m.get("id") or "")


def comparable_requests(requests):
    return [dict(r, messages=comparable_messages(r["messages"])) for r in requests]


def compare(oracle, other):
    """Differences of `other`'s record from the oracle's: {"state": [...], "requests": [...], "transcript": [...], "compaction": [...], "statuses": [...]}."""
    out = {}
    a, b = comparable_state(oracle["state"]), comparable_state(other["state"])
    if a != b:
        out["state"] = store.diff_states(a, b, 12)
    a, b = comparable_requests(oracle["requests"]), comparable_requests(other["requests"])
    if a != b:
        out["requests"] = store.diff_states(a, b, 12)
    a, b = comparable_messages(oracle["transcript"]), comparable_messages(other["transcript"])
    if a != b:
        out["transcript"] = store.diff_states(a, b, 12)
    if oracle["compaction"] != other["compaction"]:
        out["compaction"] = store.diff_states(oracle["compaction"], other["compaction"], 12)
    if oracle["statuses"] != other["statuses"]:
        out["statuses"] = [f"{oracle['statuses']} != {other['statuses']}"]
    return out


def summary_of(rec):
    if "state" not in rec:
        return {k: rec[k] for k in ("unsupported", "error") if k in rec}
    return {"state_sha256": store.state_digest(rec["state"]), "requests": len(rec["requests"]), "requests_sha256": store.state_digest(rec["requests"]), "transcript_messages": len(rec["transcript"]), "schema_version": rec["state"].get("schema_version"),
            "compaction_ids": len(rec["compaction"]), "statuses": rec["statuses"]}


class Gate:
    def __init__(self, state, log):
        self.state, self.log = state, log
        self.records = {}     # fixture label -> {scenario: {arm: summary}}
        self.differences = {}  # fixture label -> {arm: {scenario: {...}}}
        self.flaky = {}       # fixture label -> [scenario]
        self.different_work = {}   # arm -> {fixture label: reason}
        self.capabilities = {}     # arm -> {capability: reason or None}
        self.cross_open = {}
        self.row_identical = {}
        self.failures = []     # sentences: why the run is refused

    def run(self, built_list, oracle, arms, twin):
        """Run the gate over every built fixture. `arms` are the non-twin adapter arms with the oracle first; `twin` is the oracle's A/A copy or None."""
        state = self.state
        first = True
        for built in built_list:
            fx = built.fx
            spath, _ = gate_script(state.root, fx, state.seed)
            for sc in scenarios(fx, capabilities=first):
                self.scenario(built, spath, sc, oracle, arms, twin)
            first = False

    def scenario(self, built, spath, sc, oracle, arms, twin, background=None):
        label, name = built.fx.label, sc["name"]
        self.log(f"buffon: equivalence: {label} {name}" + (" (blocking compaction)" if background == 0 else ""))
        recs = {a.id: run_scenario(self.state, a, built, spath, sc, background) for a in arms}
        ref = recs[oracle.id]
        cap = sc.get("cap")
        out = self.records.setdefault(label, {}).setdefault(name + ("-blocking" if background == 0 else ""), {})
        for aid, rec in recs.items():
            out[aid] = summary_of(rec)
            if cap:
                self.capabilities.setdefault(aid, {})[cap] = rec.get("unsupported") if "unsupported" in rec else (None if "state" in rec else f"the adapter failed in the {name} scenario: {rec.get('error')}")
        if "state" not in ref:
            why = ref.get("unsupported") or ref.get("error")
            if not cap:
                self.failures.append(f"{oracle.id} could not run the {name} scenario at {label}: {why}")
            return
        if twin is not None and not cap and background is None:
            t = run_scenario(self.state, twin, built, spath, sc, background, tag="-b")
            out[twin.id] = summary_of(t)
            if "state" not in t or compare(ref, t):
                self.flaky.setdefault(label, []).append(name)
                self.log(f"buffon: equivalence: {oracle.id} differs from its own A/A copy in {label} {name}: the fixture is excluded")
                self._drop(recs)
                return
        for aid, rec in recs.items():
            if aid == oracle.id or "state" not in rec:
                continue
            diff = compare(ref, rec)
            if name == "base" and background is None:
                self.row_identical.setdefault(label, {})[aid] = store.rows_identical(ref["store"], rec["store"], tables=SHARED_TABLES)
            if not diff:
                continue
            if set(diff) <= {"compaction", "state", "requests", "transcript"} and "compaction" in diff and background is None:
                self.log(f"buffon: equivalence: {aid} places compaction differently from {oracle.id} at {label} {name}: trying the blocking variant")
                self.blocking(built, spath, sc, oracle, arms, twin, aid, diff)
                continue
            self.record_failure(label, name, aid, diff)
        if name == "base":
            self.cross(built, recs, oracle, arms)
        self._drop(recs)

    def blocking(self, built, spath, sc, oracle, arms, twin, aid, first_diff):
        label = built.fx.label
        pair = [oracle, next(a for a in arms if a.id == aid)]
        recs = {a.id: run_scenario(self.state, a, built, spath, sc, 0, tag="-blocking") for a in pair}
        ref, rec = recs[oracle.id], recs[aid]
        self.records[label].setdefault(sc["name"] + "-blocking", {}).update({k: summary_of(v) for k, v in recs.items()})
        if "state" in ref and "state" in rec and not compare(ref, rec):
            reason = (f"compaction boundaries differ from {oracle.id} at {label} with background compaction (a background summary is placed at a different turn) and agree with it when compaction is blocking "
                      f"(background_tokens 0): the arm does different work here, so no ratio is computed (equivalence.json)")
            self.different_work.setdefault(aid, {})[label] = reason
        else:
            self.record_failure(label, sc["name"], aid, first_diff)
        self._drop(recs)

    def record_failure(self, label, name, aid, diff):
        self.differences.setdefault(label, {}).setdefault(aid, {})[name] = diff
        fields = "; ".join(f"{k}: {v[0]}" for k, v in diff.items() if v)
        self.failures.append(f"{aid} differs from the oracle at {label} ({name}): {fields}")

    def cross(self, built, recs, oracle, arms):
        """Each arm opens every other arm's final store (a copy) and reads the same transcript the writer read."""
        label = built.fx.label
        spath, _ = gate_script(self.state.root, built.fx, self.state.seed)
        for writer in arms:
            w = recs.get(writer.id)
            if not w or "state" not in w:
                continue
            version = w["state"].get("schema_version")
            for reader in arms:
                if reader.id == writer.id:
                    continue
                key = f"{writer.id}>{reader.id}"
                reads = reader.adapter.get("schema_reads", [1])
                if version not in reads:   # not a failure: the reader's runtime does not open that schema (a store written by a newer runtime), and says so
                    self.cross_open.setdefault(label, {})[key] = {"ok": None, "possible": False, "why": f"{reader.id}'s runtime opens storage schema version(s) {reads}; the store {writer.id} wrote is version {version}"}
                    continue
                r = run_scenario(self.state, reader, built, spath, {"name": "cross", "steps": []}, source=w["store"], tag=f"-{writer.id}")
                if "state" not in r:
                    self.cross_open.setdefault(label, {})[key] = {"ok": False, "why": r.get("unsupported") or r.get("error")}
                    self.failures.append(f"{reader.id} could not open the store {writer.id} wrote at {label}: {r.get('unsupported') or r.get('error')}")
                    continue
                diff = store.diff_states(comparable_messages(w["transcript"]), comparable_messages(r["transcript"]), 12)
                state_diff = store.diff_states(comparable_state(w["state"]), comparable_state(r["state"]), 12)
                self.cross_open.setdefault(label, {})[key] = {"ok": not diff and not state_diff, "messages": len(r["transcript"])}
                if diff or state_diff:
                    self.failures.append(f"{reader.id} reads the store {writer.id} wrote at {label} differently: {(diff or state_diff)[0]}")
                if r.get("store"):
                    os.unlink(r["store"])

    def _drop(self, recs):
        for rec in recs.values():
            p = rec.get("store")
            if p and os.path.exists(p):
                os.unlink(p)

    def document(self, oracle):
        return {"passed": not self.failures, "oracle": oracle.id, "failures": self.failures, "fixtures": self.records, "differences": self.differences, "flaky": self.flaky,
                "different_work": self.different_work, "capabilities": self.capabilities, "cross_open": self.cross_open, "row_identical": self.row_identical}
