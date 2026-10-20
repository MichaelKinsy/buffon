# SPDX-License-Identifier: Apache-2.0
"""Before the first measured sample of a durable run: build the fixtures, run the equivalence gate and the cross-open check, capture the statement stream of the floor-sql workload.

A run whose gate fails times nothing and says why (exit code 3, `equivalence.json` in the run directory). A fixture the reference could not build, or one the oracle disagrees with its own
A/A copy about, is not a refusal: the workloads on it are skipped with that reason, as a capability an arm lacks is (`State.skip_reason`)."""
import json
import os
import time

from . import fixtures, gate as gatelib, script as scriptlib, specs, store
from .driver import Process
from .host import DurableHost
from .protocol import AdapterError


class State:
    """What the durable workloads of one run share: set as `ctx.durable`."""

    def __init__(self, runner, ctx, arms, oracle, twin):
        self.runner, self.ctx, self.arms, self.oracle, self.twin = runner, ctx, arms, oracle, twin
        self.root = fixtures.cache_root(ctx.opts)
        self.seed = specs.SEED
        self.built, self.failed = {}, {}
        self.gate = None
        self.floor_stream = None
        self.floor_error = None
        self.keep = os.path.join(ctx.work, "gate-keep")
        os.makedirs(self.keep, exist_ok=True)

    def skip_reason(self, arm, spec):
        """Why `arm` cannot take workload `spec`, or None: the fixture is missing or excluded, or the arm lacks a capability."""
        fx = spec.fixture
        if fx is not None:
            if fx in self.failed:
                return self.failed[fx]
        g = self.gate
        base = arm.id.removesuffix("-b")
        for cap in spec.needs:
            why = (g.capabilities.get(base) or {}).get(cap) if g else None
            if why:
                return f"{base} cannot run this: {why}"
            if g and cap in (g.capabilities.get(self.oracle.id) or {}) and (g.capabilities[self.oracle.id][cap]):
                return f"the reference {self.oracle.id} cannot run this: {g.capabilities[self.oracle.id][cap]}"
        return None


def run(runner, ctx, installed, instances):
    """(prepared dict, refusal text or None). The dict holds `state`, `gate` (the document of equivalence.json) and `summary` (what raw.json's run.durable keeps)."""
    p = runner.plan
    chosen = [specs.SPECS[w.id] for w in p.workloads if w.id in specs.SPECS]
    arms = [a for a in installed if a.adapter]
    if not arms:
        return {"summary": {}, "gate": None}, "no durable arm is selected: the durable workloads run on arms with an adapter (pi-durable, pig-durable)"
    oracle = next((a for a in arms if a.id == p.reference), arms[0])
    arms = [oracle] + [a for a in arms if a is not oracle]
    twin = next((i for i in instances if i.twin_of == oracle.id), None)
    state = State(runner, ctx, arms, oracle, twin)
    ctx.durable = state
    log = runner.log
    for fx in specs.fixtures_of(chosen):
        try:
            state.built[fx] = fixtures.ensure(ctx, fx, oracle, state.seed, log)
        except fixtures.FixtureError as error:
            state.failed[fx] = f"the fixture {fx.label} could not be built by the reference {oracle.id}: {error}"
            log(f"buffon: {state.failed[fx]}")
    g = state.gate = gatelib.Gate(state, log)
    g.run(list(state.built.values()), oracle, arms, twin)
    for label in g.flaky:
        for fx, built in list(state.built.items()):
            if fx.label == label:
                state.failed[fx] = f"excluded: the reference {oracle.id} disagrees with its own A/A copy at {label} (equivalence.json), so the scenario is flaky and nothing on this fixture is timed"
    inject_divergences(state, g, chosen, arms, instances)
    if any(s.flavor == "floor-sql" for s in chosen):
        capture_floor_stream(state, chosen, log)
    doc = g.document(oracle)
    doc["fixtures"] = {"scenarios": doc["fixtures"], "built": {fx.label: {k: b.facts.get(k) for k in ("script_sha256", "store_sha256", "writer", "build_s", "store_bytes", "turns", "cached")} for fx, b in state.built.items()},
                       "failed": {fx.label: why for fx, why in state.failed.items()}}
    os.makedirs(p.out, exist_ok=True)
    with open(os.path.join(p.out, "equivalence.json"), "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    summary = {"env": "native", "oracle": oracle.id, "passed": doc["passed"], "failures": doc["failures"], "fixtures": doc["fixtures"]["built"], "failed_fixtures": doc["fixtures"]["failed"],
               "flaky": doc["flaky"], "different_work": doc["different_work"], "capabilities": doc["capabilities"], "row_identical": doc["row_identical"], "seed": state.seed, "generator": scriptlib.GENERATOR,
               "cold_start": "warm page cache: every sample's store is a fresh copy read once before timing"}
    out = {"state": state, "gate": doc, "summary": summary}
    if g.failures:
        return out, ("the arms do not do the same work, so their timings are not comparable: " + "; ".join(g.failures[:4]) + (f" (and {len(g.failures) - 4} more)" if len(g.failures) > 4 else "") + ". The records are in equivalence.json")
    return out, None


def inject_divergences(state, g, chosen, arms, instances):
    """A fixture where an arm's compaction boundaries differ from the oracle's (and agree when compaction blocks) is different work: the report shows medians and no ratio. The divergence
    mechanism is the manifest's (`[[divergence]]`, buffon/divergence.py); the gate adds its findings to the arm's list for this run, and the run's arm facts carry them."""
    for aid, per_fixture in g.different_work.items():
        for label, reason in per_fixture.items():
            ids = sorted(s.id for s in chosen if s.fixture is not None and s.fixture.label == label)
            if not ids:
                continue
            for inst in instances:
                if inst.id.removesuffix("-b") == aid:
                    inst.divergences.append({"workloads": ids, "reason": reason, "source": "docs/design/DURABLE.md"})


def capture_floor_stream(state, chosen, log):
    """The statement stream of the measured turns of floor-sql, recorded once from the reference through its own facade (`capture`), then replayed by every arm."""
    spec = next(s for s in chosen if s.flavor == "floor-sql")
    built = state.built.get(spec.fixture)
    if built is None:
        return
    oracle = state.oracle
    spath, _ = fixtures.measured_script(state.root, spec, state.seed, spec.fixture.variant, spec.fixture.history)
    host = DurableHost(oracle, state.ctx.work, tag="capture")
    proc = Process(host, oracle, timeout=1800)
    try:
        fixtures.stage(built, host)
        proc.wait_ready()
        ad = proc.adapter
        ad.call("open", store=host.store, script=spath, ledger=host.ledger, mode="runtime", conversations=1, create=False, window_tokens=spec.fixture.window_tokens,
                compaction={"enabled": spec.fixture.compaction, "background_tokens": None}, partial_interval_ms=None, summary_fails=False, request_log=None, capture=host.capture)
        for n in range(spec.fixture.history, spec.fixture.history + spec.measured):
            ad.call("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
            ad.call("barrier")
        ad.call("close")
    except AdapterError as error:
        state.floor_error = f"the statement stream could not be captured from {oracle.id}: {error}"
        log(f"buffon: {state.floor_error}")
        return
    finally:
        proc.release()
    dest = os.path.join(state.keep, "floor-sql-stream.jsonl")
    os.replace(host.capture, dest)
    state.floor_stream = dest
    host.cleanup()
    with open(dest) as f:
        lines = sum(1 for _ in f)
    log(f"buffon: floor-sql: captured {lines} statements of {spec.measured} turns from {oracle.id}")
