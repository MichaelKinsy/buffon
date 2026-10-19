# SPDX-License-Identifier: Apache-2.0
"""Workload registry.

A sampled workload is a function `fn(ctx, arm) -> dict` that runs ONE fresh process of one arm and returns the sample's metrics (or {"failure": text}, or raises
overhead.Skip when the arm cannot run it). The engine calls it round after round, interleaving arms; a workload never loops over arms or rounds itself.
Soak and reliability are different in shape (arms in parallel for minutes; pass/fail cells) and register as `special` workloads with their own driver.
"""
from dataclasses import dataclass, field

REGISTRY = {}


@dataclass
class Workload:
    id: str                       # family/name, e.g. overhead/print
    family: str                   # axis family: overhead, streaming, longsession, soak, reliability
    fn: object = None
    apis: tuple = ("openai-completions", "anthropic-messages", "openai-responses")   # wire APIs the workload varies over, each a separate variant in the report; (None,) = does not depend on the API
    special: object = None        # driver for workloads that are not one-sample-per-arm
    description: str = ""
    params: dict = field(default_factory=dict)
    rounds: int = 0               # the measured rounds this workload takes by default (0: the run's); an explicit --rounds wins
    aa: bool = True               # whether it runs on the A/A copies by default; an explicit --aa wins


def register(workload):
    if workload.id in REGISTRY:
        raise ValueError(f"workload {workload.id} registered twice")
    REGISTRY[workload.id] = workload
    return workload


def load_all():
    """Import every workload module (each registers itself) and return the registry."""
    from . import overhead, streaming, longsession, soak, reliability, devloop, scale  # noqa: F401
    return REGISTRY


def resolve(names):
    """Expand names: a workload id, a family name (all its workloads) or `all`."""
    reg = load_all()
    out = []
    for name in names:
        if name == "all":
            out += [w for w in reg.values()]
        elif name in reg:
            out.append(reg[name])
        else:
            family = [w for w in reg.values() if w.family == name]
            if not family:
                raise KeyError(f"unknown workload {name!r}; known: {', '.join(sorted(reg))} (or a family: {', '.join(sorted({w.family for w in reg.values()}))})")
            out += family
    seen, uniq = set(), []
    for w in out:
        if w.id not in seen:
            seen.add(w.id)
            uniq.append(w)
    return uniq
