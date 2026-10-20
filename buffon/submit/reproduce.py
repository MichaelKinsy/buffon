# SPDX-License-Identifier: Apache-2.0
"""Reproducing a published run and comparing it with the original, telemetry included (`buffon reproduce`, `buffon compare`).

A reproducer runs the same plan (arms, workloads, APIs, rounds, seed, parameters) on their own host. `compare` then answers two questions: did the numbers reproduce, and was
the reproducer's host noisier or quieter than the original's. The second matters for the first: a difference smaller than the noisier host's floor is not a failure to reproduce.

Rules, published here and in docs/SUBMITTING.md:
  * a cell is *consistent* when the two 95% intervals of the ratio overlap, or the two ratios differ by less than the larger of the two A/A floors;
  * a cell *reproduces* when it is consistent and both runs reach the same verdict;
  * a host is *noisier* than the other when its median A/A floor is more than NOISE_FACTOR times the other's and at least NOISE_MIN_GAP (absolute) higher, *quieter* in the reverse case,
    otherwise *similar*; the calibration CV, flagged share, throttling and the run notes are shown beside it.
"""
import json
import math
import os

from ..report import cellid as cellidlib, cells as cellmath, health as healthlib, noise as noiselib
from ..runner import raw as rawlib
from . import check as checklib

NOISE_FACTOR = 1.5
NOISE_MIN_GAP = 0.005
HOST_FIELDS = ("cpu_model", "logical_cpus", "memory_gib", "kernel", "machine", "smt_active", "fixed_clock", "container", "node", "pinned_cpus", "mock_cpus")


def load(run_dir):
    raw = rawlib.read(run_dir)
    path = os.path.join(run_dir, "facts.json")
    facts = {}
    if os.path.exists(path):
        with open(path) as f:
            facts = json.load(f)
    return raw, facts


def view(run_dir, reference=None, seed=20261011):
    """Everything the comparison needs from one run directory."""
    raw, facts = load(run_dir)
    data = cellmath.build([raw], reference, seed)
    noise = noiselib.build([raw], [facts], data)
    h = healthlib.assess([raw], [facts], data, noise)
    return {"dir": run_dir, "raw": raw, "facts": facts, "data": data, "noise": noise, "health": h, "values": healthlib.values([raw], data, noise)}


def pins_differences(a, b):
    """What differs between two runs' pins: [(what, original, yours)]."""
    out = []
    for label, x, y in (("arms.lock sha256", a["raw"].get("lock_sha256"), b["raw"].get("lock_sha256")),
                        ("runner commit", (a["raw"]["runner"] or {}).get("commit"), (b["raw"]["runner"] or {}).get("commit"))):
        if x != y:
            out.append((label, x, y))
    for arm in sorted(set(a["raw"]["arms"]) | set(b["raw"]["arms"])):
        if arm.startswith("_") or arm.endswith("-b"):
            continue
        x, y = a["raw"]["arms"].get(arm), b["raw"]["arms"].get(arm)
        if x is None or y is None:
            out.append((f"arm {arm}", "present" if x else "absent", "present" if y else "absent"))
            continue
        for key in ("version", "executable_sha256", "install_tree_sha256", "manifest_sha256"):
            if x.get(key) != y.get(key):
                out.append((f"{arm} {key}", x.get(key), y.get(key)))
    return out


def plan_differences(a, b):
    """The run parameters that must match for the runs to be comparable: [(what, original, yours)]."""
    out = []
    for key in ("workloads", "apis", "rounds", "warmup", "aa", "reference", "seed", "params"):
        x, y = a["raw"]["run"].get(key), b["raw"]["run"].get(key)
        if x != y:
            out.append((key, x, y))
    return out


def noise_verdict(a, b):
    """("noisier" | "quieter" | "similar", sentence) for run `b` (the reproducer) against run `a` (the original), by the median A/A floor."""
    fa, fb = a["values"]["aa_floor_median"], b["values"]["aa_floor_median"]
    if fa != fa or fb != fb:
        return "unknown", "one of the runs has no A/A floor, so the hosts' noise cannot be compared"
    if fb > fa * NOISE_FACTOR and fb - fa >= NOISE_MIN_GAP:
        word = "noisier"
    elif fa > fb * NOISE_FACTOR and fa - fb >= NOISE_MIN_GAP:
        word = "quieter"
    else:
        word = "similar"
    ratio = f"{fb / fa:.1f}x" if fa else "n/a"
    how = "about as noisy as the original's" if word == "similar" else f"{word} than the original's"
    return word, f"your host was {how}: median A/A floor {fb:.1%} against {fa:.1%} ({ratio})"


def cells_agreement(a, b):
    """One row per comparison present in both runs."""
    ca = {(c.scenario, c.api, c.metric): c for c in a["data"]["cells"]}
    cb = {(c.scenario, c.api, c.metric): c for c in b["data"]["cells"]}
    rows = []
    for key in sorted(set(ca) & set(cb), key=lambda k: tuple(str(x) for x in k)):
        for arm in sorted(set(ca[key].comparisons) & set(cb[key].comparisons)):
            x, y = ca[key].comparisons[arm], cb[key].comparisons[arm]
            if x.not_compared or y.not_compared:   # no ratio to reproduce: the arm does different work there
                continue
            floors = [f for f in (x.floor, y.floor) if f == f]
            floor = max(floors) if floors else 0.0
            overlap = x.ci[0] <= y.ci[1] and y.ci[0] <= x.ci[1]
            close = x.ratio > 0 and y.ratio > 0 and math.isfinite(x.ratio) and math.isfinite(y.ratio) and abs(math.log(y.ratio / x.ratio)) <= floor
            consistent = overlap or close
            same = x.verdict.split(" (")[0] == y.verdict.split(" (")[0]
            rows.append({"scenario": key[0], "api": key[1], "metric": key[2], "arm": arm, "original": {"ratio": x.ratio, "ci": list(x.ci), "verdict": x.verdict, "floor": None if x.floor != x.floor else x.floor},
                         "yours": {"ratio": y.ratio, "ci": list(y.ci), "verdict": y.verdict, "floor": None if y.floor != y.floor else y.floor},
                         "consistent": consistent, "same_verdict": same, "reproduced": consistent and same,
                         "gap": abs(math.log(y.ratio / x.ratio)) if x.ratio > 0 and y.ratio > 0 and math.isfinite(x.ratio) and math.isfinite(y.ratio) else math.nan})
    return rows


def compare(original_dir, yours_dir, reference=None, seed=20261011):
    """The comparison as plain data."""
    a, b = view(original_dir, reference, seed), view(yours_dir, reference, seed)
    word, sentence = noise_verdict(a, b)
    rows = cells_agreement(a, b)
    keys = ("calibration_cv", "aa_cv_cpu", "aa_significant_fraction", "aa_gap_median", "aa_gap_max", "aa_floor_median", "aa_floor_max", "outlier_fraction", "flagged_fraction", "throttled_samples", "steal_share", "foreign_cpu_p95",
            "gate_slow_fraction", "clock_deviation", "drift", "infra_failed_fraction", "arm_failed_fraction")
    return {"original": original_dir, "yours": yours_dir, "pins": pins_differences(a, b), "plan": plan_differences(a, b), "noise": {"verdict": word, "sentence": sentence,
            "original": {k: a["values"][k] for k in keys}, "yours": {k: b["values"][k] for k in keys}}, "notes": {"original": a["health"]["notes"], "yours": b["health"]["notes"]},
            "host": {k: [a["facts"].get(k), b["facts"].get(k)] for k in HOST_FIELDS}, "hardware": [a["raw"]["hardware"]["class"], b["raw"]["hardware"]["class"]],
            "cells": rows, "totals": {"cells": len(rows), "reproduced": sum(r["reproduced"] for r in rows), "consistent_only": sum(r["consistent"] and not r["same_verdict"] for r in rows),
                                      "not_reproduced": sum(not r["consistent"] for r in rows)}}


def pct(x):
    return "n/a" if x is None or x != x else f"{x:.1%}"


def lines(c):
    t = c["totals"]
    out = ["# Reproduction", "", f"Original: `{c['original']}`. Yours: `{c['yours']}`.", "",
           f"**{t['reproduced']} of {t['cells']} comparisons reproduce** ({t['consistent_only']} are consistent but reach a different verdict, {t['not_reproduced']} are not consistent). "
           f"**{c['noise']['sentence'][0].upper() + c['noise']['sentence'][1:]}.** Run notes: original {c['notes']['original']}, yours {c['notes']['yours']}.", ""]
    if c["plan"] or c["pins"]:
        out += ["## What differs between the runs", "", "| what | original | yours |", "|---|---|---|"]
        out += [f"| {w} | `{str(x)[:80]}` | `{str(y)[:80]}` |" for w, x, y in c["plan"] + c["pins"]]
        out += ["", "Differing pins or plan mean the runs are not the same experiment; read the table below with that in mind.", ""]
    out += ["## Telemetry: was your host noisier?", "", "| measure | original | yours |", "|---|---:|---:|"]
    labels = {"calibration_cv": "calibration CV of the reference", "aa_cv_cpu": "A/A CV of CPU metrics, median", "aa_significant_fraction": "A/A pairs with a significant gap above 1%", "aa_gap_median": "A/A gap to the copy, median", "aa_gap_max": "A/A gap to the copy, largest cell",
              "aa_floor_median": "A/A floor, median", "aa_floor_max": "A/A floor, worst cell", "outlier_fraction": "outliers (MAD rule)", "flagged_fraction": "host-flagged samples",
              "throttled_samples": "CFS-throttled samples (count)", "steal_share": "steal", "foreign_cpu_p95": "foreign CPU on the pinned CPUs, p95", "gate_slow_fraction": "samples that waited > 1 s for a quiet host",
              "clock_deviation": "clock deviation from the median", "drift": "drift over the run, median", "infra_failed_fraction": "infrastructure failures", "arm_failed_fraction": "arm failures"}
    for k, label in labels.items():
        o, y = c["noise"]["original"][k], c["noise"]["yours"][k]
        out.append(f"| {label} | {o if k == 'throttled_samples' else pct(o)} | {y if k == 'throttled_samples' else pct(y)} |")
    out += ["", "| host | original | yours |", "|---|---|---|"] + [f"| {k} | {x} | {y} |" for k, (x, y) in c["host"].items()] + [f"| hardware class | {c['hardware'][0]} | {c['hardware'][1]} |", ""]
    bad = sorted((r for r in c["cells"] if not r["reproduced"]), key=lambda r: -(r["gap"] if r["gap"] == r["gap"] else 0))
    out += ["## Comparisons that did not reproduce", ""]
    if bad:
        out += ["| workload | api | metric | arm | original ratio [CI] | verdict | your ratio [CI] | verdict | consistent | note |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in bad[:40]:
            o, y = r["original"], r["yours"]
            note = ""
            if y["floor"] is not None and o["floor"] is not None and y["floor"] > NOISE_FACTOR * o["floor"]:
                note = f"your A/A floor is {pct(y['floor'])}, the original's {pct(o['floor'])}"
            out.append(f"| {r['scenario']} | {r['api'] or '-'} | {r['metric']} | {r['arm']} | {o['ratio']:.3g} [{o['ci'][0]:.3g}, {o['ci'][1]:.3g}] | {o['verdict']} | {y['ratio']:.3g} [{y['ci'][0]:.3g}, {y['ci'][1]:.3g}] | {y['verdict']} | "
                       f"{'yes' if r['consistent'] else 'no'} | {note} |")
    else:
        out.append("None: every comparison reproduces.")
    out += ["", "Rules: a comparison is consistent when the two 95% intervals overlap or the ratios differ by less than the larger A/A floor; it reproduces when it is consistent and the verdicts agree. "
            f"A host is noisier when its median A/A floor is more than {NOISE_FACTOR}x the other's and at least {NOISE_MIN_GAP:.1%} higher (buffon/submit/reproduce.py).", ""]
    return out


def write(c, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "reproduction.md"), "w") as f:
        f.write("\n".join(lines(c)) + "\n")
    with open(os.path.join(out_dir, "reproduction.json"), "w") as f:
        json.dump(c, f, indent=1, default=lambda x: None if isinstance(x, float) and x != x else x)
    return os.path.join(out_dir, "reproduction.md")


def run_argv(original_dir, site, out, reference_args=(), workloads=None, apis=None, arms=None):
    """The `buffon run` argv that repeats the original run's plan on `site`: the same arms, workloads, APIs, rounds, warm-up, A/A copies, reference, seed and parameters.
    Everything about the machine comes from the site profile."""
    raw = rawlib.read(original_dir)
    run = raw["run"]
    argv = ["run", *(workloads or run["workloads"]), *(["--site", site] if site else []), "--out", out, "--rounds", str(run["rounds"]), "--warmup", str(run["warmup"]), "--aa", run["aa"], "--reference", run.get("reference") or "pi-node",
            "--seed", str(run["seed"]), "--arms", *(arms or run["arms"])]
    if apis or run.get("apis"):
        argv += ["--apis", *(apis or run["apis"])]
    for k, v in sorted((run.get("params") or {}).items()):
        argv += ["--param", f"{k}={json.dumps(v)}"]
    cmd = run.get("command") or []
    for flag in ("--timeout", "--rpc-turns", "--long-turns"):
        if flag in cmd and cmd.index(flag) + 1 < len(cmd):
            argv += [flag, cmd[cmd.index(flag) + 1]]
    return argv + list(reference_args)


def cell_plan(original_dir, scenario, api, metric, reference=None):
    """(workloads, apis, arms) that measure one cell again: its workload and API, and the arms that have a measured sample of it (the reference always). CellIdError when the run has no such cell."""
    raw = rawlib.read(original_dir)
    ref = reference or (raw["run"].get("reference") or "pi-node")
    mine = [s for s in raw["samples"] if s["scenario"] == scenario and cellmath.variant(s) == api and not s["warmup"] and "failure" not in s and metric in s]
    arms = sorted({s["arm"].removesuffix("-b") for s in mine})
    if not arms:
        raise cellidlib.CellIdError(f"the run {original_dir} has no measured {metric} of {scenario} ({api or 'no API'}); its cells are listed in its report.md")
    wire = api if any(s.get("api") for s in mine) else None   # an environment (a durable cell of Miniflare) is not a wire API: the run's own params carry it (`run_argv`)
    return [scenario], [wire] if wire else None, [ref] + [a for a in arms if a != ref]


def pins_ok(original_dir, repo):
    """Problems that stop a reproduction before it starts: the repository's pins are not the original run's."""
    raw = rawlib.read(original_dir)
    r = checklib.Result()
    checklib.pins(raw, repo, r)
    return [c["message"] for c in r.checks if c["status"] == "error"]
