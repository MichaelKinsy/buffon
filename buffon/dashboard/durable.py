# SPDX-License-Identifier: Apache-2.0
"""The Durable section's own data for the site: what its charts draw beyond the cells (the line charts over history length, the crash grid), the attribution, and what its Method block shows
(runtime settings and versions per arm, the equivalence gate's records, the digest of each fixture).

Every number is a cell's (the pages read the cells) or the report's (the crash grid is buffon/report/durable.py). Nothing here computes a statistic."""
import json
import os
import re

from ..report import durable as crash
from . import benchmarks

ATTRIBUTION = "The compat lane is adapted from durable-bench (github.com/clavia-labs/durable-bench), used with permission."
HEADLINE = ("durable/mixed-3500", "warm_net_ms")   # warm_net_ms on mixed-3500 (docs/design/DURABLE.md 7.5)
BARS = ("sql_stmts_per_turn", "sql_commits_per_turn", "rows_returned_per_turn")   # the first page also shows the work a turn costs, on the headline workload
EQUIVALENCE = "equivalence.json"


def rungs(scenarios):
    """[{at, workload}] for workloads named <lane>-<n>: the n of each is its place on the x axis (the same shape as the `rungs` of workloads/tracks.toml)."""
    return [{"at": int(re.search(r"(\d+)$", s).group(1)), "workload": s} for s in scenarios]


COMPAT = rungs([f"durable/compat-{n}" for n in (50, 250, 1000, 3500)])
MIXED = rungs([f"durable/mixed-{n}" for n in (1000, 3500, 10000)])
HISTORY = [{"id": "compat", "name": "compat", "rungs": COMPAT}, {"id": "mixed", "name": "mixed", "rungs": MIXED}]
# One line chart each: a metric of the cells of these workloads, one line per arm and series, x the history length (or the conversations of many-conv), the x axis logarithmic.
LINES = [
    {"id": "warm", "title": "Warm turn against history length", "metric": "warm_turn_ms", "xlabel": "turns in the store →", "series": HISTORY,
     "note": "The median of turns 2 to 10 of a sample. compat is durable-bench's shape (compaction off, eight tool calls a turn); mixed has compaction on and mixed turns."},
    {"id": "cold", "title": "Cold start against history length", "metric": "cold_ms", "xlabel": "turns in the store →", "series": HISTORY,
     "note": "Open the stored conversation and answer the first turn, in a new process. Process start is not in it."},
    {"id": "store", "title": "Store size against history length", "metric": "store_bytes", "xlabel": "turns in the store →", "series": HISTORY,
     "note": "The main file, the log and the index file after a clean close, read by the runner."},
    {"id": "memory", "title": "Memory against live conversations", "metric": "end_rss_mib", "xlabel": "conversations →",
     "series": [{"id": "many", "name": "at the end", "rungs": rungs([f"durable/many-conv-{n}" for n in (1, 8, 32, 128)])}], "slope": "mem_per_conv_mib",
     "note": "Memory of the process tree when N conversations are open, one turn each in turn. The slope of the line is the memory per live conversation."},
]


def key_of(scenario, metric):
    """The id of a workload's metric in the pages (model.metric_key): the slug of the workload and the metric's name."""
    return f"{slug(scenario)}.{metric}"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


def charts():
    """The line charts with the key of every point's metric (the id the pages use for a workload's metric)."""
    out = []
    for c in LINES:
        item = {k: v for k, v in c.items() if k != "series"}
        item["series"] = [{"id": s["id"], "name": s["name"], "rungs": [{"at": r["at"], "key": key_of(r["workload"], c["metric"])} for r in s["rungs"]]} for s in c["series"]]
        if c.get("slope"):
            item["slope_keys"] = [key_of(r["workload"], c["slope"]) for r in c["series"][0]["rungs"]]
        out.append(item)
    return out


def text_of(value):
    """A gate field as one short line: a list or a mapping as its entries, else the value; `none` for an empty one."""
    if value in (None, "", [], {}):
        return "none"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {text_of(v)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(text_of(v) for v in value)
    return str(value)


def gate_of(path, raw, run_id):
    """The equivalence gate of one run as the Method page prints it: the run directory's equivalence.json (the full records) when it holds one, else the summary the run records in `run.durable`
    (the same keys but the scenarios' records). None when it has neither."""
    file = os.path.join(path, EQUIVALENCE)
    source = EQUIVALENCE
    doc = None
    if os.path.exists(file):
        with open(file) as f:
            doc = json.load(f)
    else:
        doc, source = (raw.get("run") or {}).get("durable"), "run.durable"
    if not isinstance(doc, dict):
        return None
    fx = doc.get("fixtures") or {}
    built = fx.get("built") if "built" in fx else {k: v for k, v in fx.items()}   # equivalence.json keeps built, failed and scenarios apart; the run's summary is the built ones
    scenarios = []
    for label, by_name in sorted((fx.get("scenarios") or {}).items()):
        for name, by_arm in sorted(by_name.items()):
            scenarios.append({"label": label, "name": name, "arms": {a: {"requests": r.get("requests"), "messages": r.get("transcript_messages")} for a, r in sorted(by_arm.items())}})   # the gate compares them by field, not by digest: the page lists what each arm did and the gate's own verdict
    cross = [{"label": label, "order": order, "ok": v.get("ok"), "why": v.get("why"), "impossible": crash.reason_of(v), "messages": v.get("messages")} for label, orders in sorted((doc.get("cross_open") or {}).items()) for order, v in sorted((orders or {}).items()) if isinstance(v, dict)]
    return {"run": run_id, "source": source, "passed": doc.get("passed"), "oracle": doc.get("oracle"), "failures": [str(f) for f in doc.get("failures") or []],
            "fixtures": [{"label": k, "script_sha256": v.get("script_sha256"), "store_sha256": v.get("store_sha256"), "writer": v.get("writer"), "turns": v.get("turns"), "store_bytes": v.get("store_bytes"), "cached": v.get("cached")}
                         for k, v in sorted(built.items()) if isinstance(v, dict)],
            "scenarios": scenarios, "cross_open": cross, "differences": text_of(doc.get("differences")), "flaky": text_of(doc.get("flaky")),
            "different_work": [{"arm": arm, "label": label, "reason": str(why)} for arm, by_label in sorted((doc.get("different_work") or {}).items()) for label, why in sorted((by_label or {}).items())],
            "capabilities": [{"arm": arm, "capability": cap, "reason": why} for arm, caps in sorted((doc.get("capabilities") or {}).items()) for cap, why in sorted((caps or {}).items())],
            "row_identical": text_of(doc.get("row_identical"))}


def method_of(raws, dirs, run_ids):
    """{settings: [{arm, versions, settings}], fixtures: [{scenario, sha256, writer, variant, seed, turns}], gates: [...]} from the durable samples and run files."""
    settings, fixtures, gates = {}, {}, []   # settings: arm -> {key: value, or the words "varies by workload"}
    for i, raw in enumerate(raws):
        for s in raw["samples"]:
            if not s["scenario"].startswith("durable/") or s["arm"].endswith("-b"):
                continue
            if isinstance(s.get("runtime_settings"), dict) or isinstance(s.get("runtime_versions"), dict):
                a = settings.setdefault(s["arm"], {"arm": s["arm"], "versions": s.get("runtime_versions") or {}, "settings": dict(s.get("runtime_settings") or {}), "envs": []})
                for k, v in (s.get("runtime_settings") or {}).items():   # a setting that differs between workloads (the window) is said to vary, not shown as the first workload's
                    if k in a["settings"] and a["settings"][k] != v:
                        a["settings"][k] = "varies by workload"
                if s.get("env") and s["env"] not in settings[s["arm"]]["envs"]:
                    settings[s["arm"]]["envs"].append(s["env"])
            if s.get("fixture_sha256") and not s["scenario"].startswith("durable/crash-"):
                f = fixtures.setdefault(s["scenario"], {"scenario": s["scenario"], "sha256": [], "writer": s.get("fixture_writer"), "variant": s.get("fixture_variant"), "seed": s.get("fixture_seed"), "turns": s.get("fixture_turns"), "store_sha256": []})
                if s["fixture_sha256"] not in f["sha256"]:
                    f["sha256"].append(s["fixture_sha256"])
                if s.get("fixture_store_sha256") and s["fixture_store_sha256"] not in f["store_sha256"]:
                    f["store_sha256"].append(s["fixture_store_sha256"])
        if any(s["scenario"].startswith("durable/") for s in raw["samples"]):
            g = gate_of(dirs[i], raw, run_ids[i])
            if g:
                gates.append(g)
    return {"settings": list(settings.values()), "fixtures": sorted(fixtures.values(), key=lambda f: f["scenario"]), "gates": gates}


def build(raws, dirs, run_ids, ref, shown, skipped, na_reason):
    """The Durable data of the site: None when no run holds a durable sample (the section then shows its empty page)."""
    present = [i for i, raw in enumerate(raws) if any(s["scenario"].startswith("durable/") for s in raw["samples"])]
    if not present:
        return None
    samples, run_of = [], {}
    not_possible = crash.impossible([raws[i] for i in present])
    for i in present:
        for g in [gate_of(dirs[i], raws[i], run_ids[i])]:   # the full record of the gate also lists the orders it found impossible
            for c in (g or {}).get("cross_open", []):
                if c["impossible"]:
                    not_possible.setdefault(c["order"], c["impossible"])
        for s in raws[i]["samples"]:
            if crash.is_crash(s["scenario"]):
                samples.append(s)
                run_of.setdefault(s["scenario"], run_ids[i])
    grids = crash.verdicts(samples, ref, not_possible)
    for g in grids:
        g["id"] = slug(g["scenario"])
        g["title"] = benchmarks.workload_of(g["scenario"])["title"]
        g["run"] = run_of[g["scenario"]]
        g["na"] = {arm: na_reason(skipped, arm, g["scenario"], None, False) for arm in shown if not any(o["resumer"] == arm for o in g["orders"])}
        for o in g["orders"]:
            o["points"] = {str(k): v for k, v in o["points"].items()}
        g["commits_total"] = {str(k): v for k, v in g["commits_total"].items()}
    envs = sorted({s["env"] for i in present for s in raws[i]["samples"] if s["scenario"].startswith("durable/") and s.get("env")})
    return {"attribution": ATTRIBUTION, "headline": key_of(*HEADLINE), "bars": [key_of(HEADLINE[0], m) for m in BARS], "lines": charts(), "crash": grids, "envs": envs, "method": method_of(raws, dirs, run_ids),
            "floors": [key_of("durable/floor-host", "warm_turn_ms"), key_of("durable/floor-sql", "warm_turn_ms"), key_of("durable/floor-sql", "replay_ms_per_turn")]}
