# SPDX-License-Identifier: Apache-2.0
"""The trust badge of a run: what the reader may conclude from its numbers, as a label. Nothing is discarded or refused because of it (docs/METHODOLOGY.md section 18).

  Verified   host class A (dedicated), every strict rule held, and the run was reproduced (reproduction.json: every comparison reproduced)
  Dedicated  host class A, not (yet) reproduced, or a strict rule did not hold (the reasons say which)
  Shared     host class B: the benchmark's CPUs are shared with other work, SMT siblings, a clock the runner cannot fix, no exclusive cores
  Noisy      the calibration (the reference arm against its own A/A copy) is above its limit, or the quiet-host check gave up waiting: read every interval with that in mind

A session that ran in a slot, beside others on one host (buffon/runner/slots.py), carries the reason `slotted` unless its slot passed the slot calibration (`run.slot.calibration` names
the file); such a run is not Verified. A passed slot calibration adds nothing.

Noisy outranks Shared, which outranks Dedicated. `reasons` lists every cause, whatever the badge. The strict rules (docs/METHODOLOGY.md section 11) still decide only the
Verified badge, the headline and the public results index; `--require-class A` keeps the old refusal for people who want it.
"""
from .report import cells as cellmath

MIN_ROUNDS = 12
SLOTTED = "slotted: this session ran beside others on one host, and its slot has no passing slot calibration (buffon campaign writes slots-calibration.json)"
BADGES = ("Verified", "Dedicated", "Shared", "Noisy")
ORDER = {b: i for i, b in enumerate(BADGES)}   # best first


def realised_rounds(raw):
    """The fewest measured (non-warm-up) rounds any scenario/API cell of the run got; None when nothing was measured. A scale sample is left out: the family takes 5 rounds and its rungs above a
    harness's stop have none, and its spread across rounds, not a 12-round floor, is how it is read (docs/METHODOLOGY.md section 18)."""
    rounds = {}
    for s in raw.get("samples", []):
        if not s.get("warmup") and "failure" not in s and s.get("scenario") and not s["scenario"].startswith("scale/"):
            rounds.setdefault((s["scenario"], cellmath.variant(s)), set()).add(s.get("round"))
    return min((len(r) for r in rounds.values()), default=None)


def headline(raw):
    """Which CPU metric leads this run: instructions when the host exposed counters, else CPU time (and why)."""
    perf = (raw.get("run") or {}).get("perf") or {}
    if perf.get("available"):
        return "instructions", "hardware instruction counters"
    return "CPU time", perf.get("reason") or "this host exposes no instruction counters"


def slotted(run):
    """True when the run's session ran in a slot whose calibration did not pass (or was not given)."""
    slot = run.get("slot")
    return bool(slot) and not slot.get("calibration")


def strict_problems(raw):
    """What stops a run from being Verified even on a dedicated host: the strict rules (METHODOLOGY section 11), as sentences."""
    run, out = raw.get("run") or {}, []
    if not (raw.get("hardware") or {}).get("quiet_dedicated"):
        out.append("the run is not labelled quiet dedicated hardware")
    cal = raw.get("calibration")
    if cal is None:
        out.append("no calibration ran")
    rounds = realised_rounds(raw)
    if rounds is not None and rounds < MIN_ROUNDS:
        out.append(f"{rounds} measured rounds in the thinnest cell (the minimum for a headline is {MIN_ROUNDS})")
    if (run.get("isolation") or {}).get("comparable") is False:
        out.append("uncontained: the arms were not run in the container envelope")
    if slotted(run):
        out.append(SLOTTED)
    return out


def badge(raw, reproduced=False):
    """{"badge", "reasons", "headline", "headline_why", "strict_problems", "rounds"} for one raw.json dict."""
    run = raw.get("run") or {}
    reasons = []
    cls = run.get("host_class") or ((raw.get("preflight") or {}).get("class")) or "B"
    reasons += list((run.get("preflight") or {}).get("reasons") or [])
    cal = raw.get("calibration")
    noisy = False
    if cal and not cal.get("passed"):
        noisy = True
        cv = cal.get("max_cv")
        reasons.append(f"calibration above the limit: the reference arm varies by {cv:.1%} between identical runs (limit {cal.get('gate', 0.05):.0%})" if isinstance(cv, float) and cv == cv
                       else f"calibration did not pass: {cal.get('reason') or 'no usable calibration samples'}")
    gate = run.get("quiet_gate") or {}
    if gate.get("timeouts"):
        noisy = True
        reasons.append(f"the quiet-host check gave up waiting before {gate['timeouts']} sample(s): those ran on a busy host or failed")
    elif gate.get("waits"):
        reasons.append(f"{gate['waits']} sample(s) waited for the host to quiet down (longest {gate.get('max_wait_ms', 0) / 1000:.0f} s)")
    if slotted(run):
        reasons.append(SLOTTED)
    which, why = headline(raw)
    if which != "instructions":
        reasons.append(f"no instruction counters ({why}): CPU time is the headline")
    problems = strict_problems(raw)
    for r in (raw.get("hardware") or {}).get("reasons") or []:
        if r not in reasons:
            reasons.append(r)
    if noisy:
        label = "Noisy"
    elif cls != "A":
        label = "Shared"
    elif reproduced and not problems:
        label = "Verified"
    else:
        label = "Dedicated"
    if cls == "A" and label == "Dedicated" and problems:
        reasons += [p for p in problems if p not in reasons]
    if cls == "A" and not reproduced and label == "Dedicated":
        reasons.append("not yet reproduced (buffon reproduce / compare)")
    return {"badge": label, "host_class": cls, "reasons": reasons, "headline": which, "headline_why": why, "strict_problems": problems, "rounds": realised_rounds(raw)}


def worst(badges):
    """The worst badge of several runs (a report that merges runs is as trustworthy as its least trustworthy part)."""
    return max(badges, key=lambda b: ORDER[b]) if badges else "Shared"


def line(info):
    """One line for a terminal or a report: `Shared (class B): reason; reason`."""
    why = "; ".join(info["reasons"][:3]) + (f"; and {len(info['reasons']) - 3} more" if len(info["reasons"]) > 3 else "")
    return f"{info['badge']} (host class {info['host_class']})" + (f": {why}" if why else "")


def of_runs(raws, reproduced=None):
    """The trust of a report that merges several runs: the worst badge, every reason once, the first run's headline. `reproduced` is a list of booleans, one per run."""
    reproduced = reproduced or [False] * len(raws)
    infos = [badge(r, bool(p)) for r, p in zip(raws, reproduced)]
    if not infos:
        return {"badge": "Shared", "host_class": "B", "reasons": ["no run"], "headline": "CPU time", "headline_why": "no run", "strict_problems": [], "rounds": None}
    top = max(infos, key=lambda i: ORDER[i["badge"]])
    reasons = []
    for i in infos:
        reasons += [r for r in i["reasons"] if r not in reasons]
    return dict(top, reasons=reasons, strict_problems=[p for i in infos for p in i["strict_problems"]])
