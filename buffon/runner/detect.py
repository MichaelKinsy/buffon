# SPDX-License-Identifier: Apache-2.0
"""Quiet dedicated hardware: the runner's own detection, never just the site profile's word.

A run is labelled quiet dedicated hardware only when every condition holds. The reasons list says which one failed; a report prints them under the PROVISIONAL label.

  1. the site profile claims `dedicated` hardware;
  2. the harness is pinned (an explicit CPU list on a local host; an exclusive cpuset in a pod, where the allowed CPUs equal the requested count);
  3. every pinned CPU has a fixed clock (governor `performance`, or min = max frequency, or no cpufreq visible at all in a pod that cannot see it);
  4. the pinned CPUs and their SMT siblings were idle outside the runner's own processes, before and after the run (busy fraction below IDLE_BUSY_MAX);
  5. no CFS throttling happened in the session's cgroup;
  6. the calibration gate passed.
"""
from . import facts as factlib
from ..site import format_cpus, parse_cpus

IDLE_BUSY_MAX = 0.03


def assess(site, facts, idle_before=None, idle_after=None, throttled=None, calibration=None, requested_cpus=None, clock_claim=""):
    """(quiet_dedicated, reasons). `idle_*` map cpu -> busy fraction measured with nothing of ours running."""
    reasons = []
    if site.hardware != "dedicated":
        reasons.append("the site profile does not claim dedicated hardware")
    pinned = facts.get("pinned_cpus")
    if not pinned:
        reasons.append("the harness is not pinned to CPUs")
    elif facts.get("container") == "kubernetes" and requested_cpus is not None:
        # With the static CPU manager a Guaranteed pod's cpuset has exactly the requested cores; anything larger is the shared pool.
        if len(parse_cpus(facts.get("cpus_allowed", ""))) != requested_cpus:
            reasons.append(f"the pod's cpuset ({facts.get('cpus_allowed')}) is not the {requested_cpus} exclusive CPUs requested (no static CPU manager)")
    if pinned and facts.get("fixed_clock") is False:
        scaling = [f"{c} ({g})" for c, g in facts.get("governors", {}).items() if g and g not in ("performance", "userspace")]
        reasons.append(f"a pinned CPU scales its clock with load: {', '.join(scaling) or 'unknown'}")
    elif pinned and all(g is None for g in facts.get("governors", {}).values()) and facts.get("container") != "kubernetes" and clock_claim != "hypervisor":
        reasons.append("the clock policy of the pinned CPUs is unknown (no cpufreq interface), so a fixed clock cannot be confirmed")
    for label, idle in (("before", idle_before), ("after", idle_after)):
        if idle is None:
            reasons.append(f"no idle check of the pinned CPUs {label} the run")
            continue
        busy = {c: b for c, b in idle.items() if b > IDLE_BUSY_MAX}
        if busy:
            reasons.append(f"CPUs {format_cpus(busy)} were busy with other work {label} the run (up to {max(busy.values()):.0%})")
    if throttled:
        reasons.append(f"CFS throttled the session for {throttled} us")
    if calibration is None:
        reasons.append("no calibration ran before measuring")
    elif not calibration.get("passed"):
        reasons.append(f"the calibration gate failed (max CV {calibration.get('max_cv', float('nan')):.1%} > {calibration.get('gate', 0.05):.0%})")
    return (not reasons), reasons


def sibling_cpus(cpus):
    """The pinned CPUs plus their SMT siblings, for the idle check."""
    out = set(cpus)
    for c in cpus:
        out.update(factlib.smt_siblings(c))
    return sorted(out)
