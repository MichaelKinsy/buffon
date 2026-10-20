# SPDX-License-Identifier: Apache-2.0
"""Calibration: before anything is measured, run the reference arm against its own A/A copy and gate on the CV of its CPU time.

Per-process CPU time (cgroup usage, exact) is the metric: it is the one a noisy host or a scaling clock moves most. The gate is the larger of the two copies'
coefficients of variation over the calibration rounds. CV_GATE (5%, METHODOLOGY.md section 6) is a refusal threshold, not a warning: the engine stops, unless the
caller passes --allow-noisy, in which case the run is labelled PROVISIONAL with the CV in its raw data.
"""
import copy

from .. import stats

METRIC = "cpu_ms"
SCENARIO = "overhead/print"


def run(session, ctx, instances, rounds=None):
    from ..workloads import overhead
    plan = session.plan
    rounds = rounds or plan.calibration_rounds
    durable = bool(getattr(plan, "workloads", None)) and all(getattr(w, "envs", ()) for w in plan.workloads)   # a durable run has no print mode: its calibration is the floor-host sample (docs/design/DURABLE.md 4.5)
    eligible = [a for a in instances if not a.twin_of and (a.adapter if durable else a.supports_mode("print") and a.supports_api(plan.api))]
    # The reference arm when it is selected; otherwise the first eligible arm, named in the result.
    ref = next((a for a in eligible if a.id == getattr(plan, "reference", None)), eligible[0] if eligible else None)
    if ref is None:
        return {"passed": False, "reason": ("no durable arm is selected, so there is nothing to calibrate on" if durable else "no arm can print on this wire API, so there is nothing to calibrate on"), "max_cv": float("nan"), "gate": session_gate(), "runs": 0}
    copies = [ref, next((a for a in instances if a.twin_of == ref.id), None) or _twin(ref)]
    if not durable:
        ctx.opts.api = plan.api if plan.api in ref.apis else ref.apis[0]
    values = {c.id: [] for c in copies}
    raw = []
    for rnd in range(plan.warmup + rounds):
        for c in (copies if rnd % 2 == 0 else copies[::-1]):
            if durable:
                from ..workloads import durable as durable_workloads
                sample = durable_workloads.floor_sample(ctx, c)
            else:
                sample = overhead.RUNNERS["print"](ctx, c)
            ctx.release()
            ok = "failure" not in sample and sample.get(METRIC) is not None
            if rnd >= plan.warmup:
                raw.append({"arm": c.id, "round": rnd - plan.warmup, METRIC: sample.get(METRIC), "ok": ok, **({"failure": sample["failure"]} if not ok else {})})
                if ok:
                    values[c.id].append(sample[METRIC])
    cvs = {k: stats.cv(v) for k, v in values.items() if len(v) >= 2}
    good = all(len(v) >= max(2, rounds - 1) for v in values.values())
    max_cv = max(cvs.values()) if cvs else float("nan")
    gate = session_gate()
    out = {"metric": METRIC, "scenario": "durable/floor-host" if durable else SCENARIO, "api": None if durable else ctx.opts.api, "arm": ref.id, "runs": rounds, "cv": cvs, "max_cv": max_cv, "gate": gate,
           "passed": bool(good and cvs and max_cv <= gate), "samples": raw}
    if not good:
        out["reason"] = "too many failed calibration runs"
    session.log(f"buffon: calibration on {ref.id}: CV of {METRIC} {max_cv:.2%} (gate {gate:.0%}) {'passed' if out['passed'] else 'FAILED'}")
    return out


def session_gate():
    from .engine import CV_GATE
    return CV_GATE


def _twin(arm):
    t = copy.copy(arm)
    t.id, t.twin_of = arm.id + "-b", arm.id
    return t
