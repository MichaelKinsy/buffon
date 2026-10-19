# SPDX-License-Identifier: Apache-2.0
"""The races section of a report: one race per ladder question of the Pi-family track that the run has samples for (buffon/race.py reads them; nothing here measures)."""
from .. import race as racelib
from ..up import tracks as trackslib


def build(raws, data):
    """[race dicts] for every ladder question of the tracks that has at least one rung with a sample in these runs. The harnesses are the run's arms, A/A copies left out."""
    samples = data["samples"]
    skipped = [k for r in raws for k in r.get("skipped", [])]
    present = {s["scenario"] for s in samples if not s.get("warmup")} | {k.get("scenario") for k in skipped}
    limits = racelib.limits_of(raws[0]) if raws else {}
    out = []
    for q in trackslib.load()["pi"]["questions"]:
        rungs = [(r["at"], r["workload"]) for r in q.get("rungs", [])]
        if len([1 for _a, w in rungs if w in present]) < 2:   # a ladder needs more than its base rung: overhead/print alone is not a race
            continue
        rc = racelib.race(samples, skipped, data["base"], rungs, name=q["title"], limits=limits)
        rc.update({"id": q["id"], "sentence": q["sentence"], "tier": racelib.tier_name(limits), "reference": data["reference"]})
        out.append(rc)
    return out


def fmt_mib(v):
    return "-" if v is None else (f"{v / 1024:.2f} GiB" if v >= 1024 else f"{v:.0f} MiB")


def limits_text(limits):
    if limits.get("isolation") == "container":
        return f"every harness in its own container, {limits.get('memory_gib', 0):g} GiB of memory" + (f", {limits['cpus']} CPUs" if limits.get("cpus") else "")
    return "every harness bare (not in a container)" + (f", {limits['cpus']} pinned CPUs" if limits.get("cpus") else "") + ": uncontained, not comparable with a containerised race"


def lines(races, tag=""):
    """report.md lines: the finish line and limits once, then one lane row per harness, then the five facts (outcome, speed, memory, reliability, resources) as columns."""
    if not races:
        return []
    out = [f"## Races{tag}", "",
           "A race climbs a ladder of growing load. Every harness gets the same ladder and the same limits; the line says how far it got and why it stopped. Finished harnesses rank first by time, then stopped ones by how far they got.", ""]
    for rc in races:
        steps = " > ".join(rc["rungs"])
        out += [f"### {rc['name']}: {steps} ({rc['tier']})", "", f"Finish line: {rc['rungs'][-1]}. Limits: {limits_text(rc['limits'])}.", "",
                "| rank | harness | outcome | speed | memory peak / average | reliability | CPU time |", "|---:|---|---|---|---|---|---|"]
        for n, l in enumerate(rc["lanes"], 1):
            cps = ", ".join(f"{q}%: {t:.1f} s" for q, t in l["checkpoints"].items())
            speed = (f"{l['elapsed_s']:.1f} s" + (f" ({cps})" if cps else "")) if l["outcome"] == "Finished" else (f"{l['reached']} of {l['of']} rungs" + (f" ({cps})" if cps else ""))
            mem = f"{fmt_mib(l['memory']['peak_mib'])} / {fmt_mib(l['memory']['avg_mib'])}" + (f"; at the stop {fmt_mib(l['memory']['at_stop_peak_mib'])}" if l["memory"]["at_stop_peak_mib"] and l["outcome"] != "Finished" else "")
            rel = f"{l['reliability']['failed_samples']} of {l['reliability']['samples']} samples failed; lost work {l['reliability']['lost_work']}"
            out.append(f"| {n} | {l['arm']} | {racelib.sentence(l)} | {speed} | {mem} | {rel} | {l['resources']['cpu_ms'] / 1000:.1f} s |")
        out.append("")
    return out
