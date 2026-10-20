# SPDX-License-Identifier: Apache-2.0
"""A synthetic raw.json of the durable family for the report and dashboard tests and for design screenshots: invented numbers, the two real arm ids (`pi-durable`, the reference, and `pig-durable`)
and their A/A copies. The numbers grow with history length the way the design expects and are not a measurement of either runtime: the run says so in `run.synthetic`.

The fields are the ones the driver writes (docs/RAW-FORMAT.md, "durable"): identity (`env` is native), configuration facts, timings, CPU, the SQL facade's per-turn counts, the store, memory,
`series`, the crash grid of `durable/crash-50` and one skipped workload with its reason."""
import hashlib
import json
import os

from tests.test_report import raw_of, wobble

REFERENCE = "pi-durable"
ARMS = (("pi-durable", 0), ("pi-durable-b", 3), ("pig-durable", 1), ("pig-durable-b", 5), ("pi-durable-main", 2), ("pi-durable-main-b", 6))
LABELS = {"pi-durable": "Pi Durable 1.3.0 (Node)", "pig-durable": "PiG Durable (Go, native)", "pi-durable-main": "Pi Durable main (informational)"}
VERSIONS = {"pi-durable": "1.3.0", "pig-durable": "0.1.0", "pi-durable-main": "main 1402973a"}
SCHEMA = {"pi-durable": 1, "pig-durable": 2, "pi-durable-main": 2}   # the store schema each arm writes (Pi 1.3.0 opens schema 1 only)
SIZES = (50, 250, 1000, 3500)
MIXED = (1000, 3500, 10000)
# the workloads of docs/design/DURABLE.md 3.4 that the native environment runs, in the order the site meets them
SKIP_ARM, SKIP_SCENARIO = "pig-durable", "durable/subagent"
SKIP_REASON = "the Go port has no subagent ownership: a tool cannot create a child conversation owned by its calling task"
BASE_ARMS = ("pi-durable", "pig-durable", "pi-durable-main")
ORDERS = tuple(f"{w}>{r}" for w in BASE_ARMS for r in BASE_ARMS)
NOT_POSSIBLE = {order: f"{order.split('>')[1]} opens schema 1 stores and {order.split('>')[0]} writes schema 2" for order in ("pig-durable>pi-durable", "pi-durable-main>pi-durable")}
CRASH_COMMITS = 77
CRASH_KS = sorted({1 + round(i * (CRASH_COMMITS - 1) / 19) for i in range(20)})   # the driver's default: 20 kill points spaced evenly from the first to the last commit
FAILING_KS = (CRASH_KS[8], CRASH_KS[9])
QUICK = ("durable/compat-50", "durable/compat-3500", "durable/mixed-1000", "durable/mixed-3500", "durable/mixed-10000", "durable/many-conv-1", "durable/many-conv-8", "durable/subagent",
         "durable/crash-50", "durable/floor-host", "durable/floor-sql")


def workloads():
    """[(scenario, spec)]: every durable workload of the design table. `kind` picks the cost model, `n` is the history length in the store."""
    out = [(f"durable/compat-{n}", {"kind": "compat", "n": n, "shape": "bench8", "window": 1_000_000_000, "compaction": "off"}) for n in SIZES]
    out += [(f"durable/mixed-{n}", {"kind": "mixed", "n": n, "shape": "mixed", "window": 200_000, "compaction": "on"}) for n in MIXED]
    out += [(f"durable/mixed-varied-{n}", {"kind": "mixed", "n": n, "shape": "mixed", "window": 200_000, "compaction": "on", "variant": "varied"}) for n in MIXED]
    out += [(f"durable/window-{w}-3500", {"kind": "window", "n": 3500, "shape": "mixed", "window": {"32k": 32_000, "200k": 200_000, "1m": 1_000_000}[w], "compaction": "on", "w": w}) for w in ("32k", "200k", "1m")]
    out += [(f"durable/cold-every-turn-{n}", {"kind": "cold", "n": n, "shape": "mixed", "window": 200_000, "compaction": "on"}) for n in (1000, 3500)]
    out += [(f"durable/stream-{n}", {"kind": "stream", "n": n, "shape": "stream", "window": 200_000, "compaction": "on"}) for n in (50, 1000)]
    out += [(f"durable/large-output-{n}", {"kind": "large", "n": n, "shape": "large", "window": 200_000, "compaction": "on"}) for n in (50, 1000)]
    out += [(f"durable/docs-{n}", {"kind": "docs", "n": 1000, "docs": n, "shape": "mixed", "window": 200_000, "compaction": "on"}) for n in (100, 1000)]
    out += [(f"durable/tasks-{n}", {"kind": "tasks", "n": 1000, "tasks": n, "shape": "tools", "window": 200_000, "compaction": "on"}) for n in (8, 64)]
    out += [("durable/subagent", {"kind": "tasks", "n": 1000, "tasks": 1, "shape": "tools", "window": 200_000, "compaction": "on"})]
    out += [(f"durable/many-conv-{n}", {"kind": "many", "n": 1000, "conversations": n, "shape": "mixed", "window": 200_000, "compaction": "on"}) for n in (1, 8, 32, 128)]
    out += [(f"durable/grow-{n}", {"kind": "grow", "n": n, "shape": "mixed", "window": 200_000, "compaction": "on"}) for n in (1000, 3500)]
    out += [("durable/crash-50", {"kind": "crash", "n": 50}), ("durable/compaction-fail", {"kind": "fail", "n": 3500, "shape": "mixed", "window": 32_000, "compaction": "on"}),
            ("durable/floor-host", {"kind": "floor", "n": 0}), ("durable/floor-sql", {"kind": "floor-sql", "n": 0})]
    return out


# warm turn in ms of the reference arm: base + slope * history
WARM = {"compat": (35.0, 0.085), "mixed": (38.0, 0.021), "window": (36.0, 0.006), "cold": (62.0, 0.140), "stream": (1480.0, 0.02), "large": (58.0, 0.02), "docs": (44.0, 0.012),
        "tasks": (70.0, 0.01), "many": (40.0, 0.25), "grow": (36.0, 0.020), "fail": (150.0, 0.02), "floor": (8.0, 0.0), "floor-sql": (11.0, 0.0)}
COLD = {"compat": (120.0, 0.12), "mixed": (85.0, 0.05), "window": (80.0, 0.02), "cold": (95.0, 0.06), "stream": (1600.0, 0.05), "large": (95.0, 0.04), "docs": (90.0, 0.03), "tasks": (110.0, 0.03),
        "many": (90.0, 0.05), "grow": (85.0, 0.05), "fail": (200.0, 0.05), "floor": (14.0, 0.0), "floor-sql": (18.0, 0.0)}


def warm_floor(arm, rnd):
    """The warm turn of durable/floor-host of one arm and round: what the runner subtracts to get warm_net_ms."""
    return (8.0 if arm.startswith("pi-durable") else 5.4) * (1 + wobble(rnd + dict(ARMS)[arm]) / 200.0)


def own(arm):
    """True for the Node arms (the reference and the main build): the baseline constants of the costs below."""
    return arm.startswith("pi-durable")


def is_main(arm):
    return arm.startswith("pi-durable-main")


def scale(arm, n, family):
    """The arm's share of the reference's cost: the Go arm is nearer the reference at a short history and further from it at a long one (invented)."""
    if is_main(arm):
        return {"time": 0.62, "cpu": 0.8, "memory": 0.9, "count": 0.92}[family]
    if own(arm):
        return 1.0
    return {"time": 0.42 + 0.55 / (1 + n / 200.0), "cpu": 0.5 + 0.35 / (1 + n / 300.0), "memory": 0.58, "count": 0.8}[family]


def sample(arm, scenario, rnd, spec, **fields):
    shift = dict(ARMS)[arm]
    s = {"arm": arm, "scenario": scenario, "api": None, "env": "native", "round": rnd, "warmup": rnd == 0, "t_utc": f"2026-10-20T10:{rnd:02d}:{shift:02d}Z"}
    if arm.endswith("-b"):
        s["twin_of"] = arm[:-2]
    s.update(fields)
    return s


def digest_of(scenario):
    return hashlib.sha256(f"fixture:{scenario}".encode()).hexdigest()


def wob(rnd, arm, k=1.0):
    return 1 + k * wobble(rnd + dict(ARMS)[arm]) / 200.0


def timing_sample(arm, scenario, rnd, spec):
    kind, n = spec["kind"], spec["n"]
    w, c = WARM[kind], COLD[kind]
    if kind == "docs":
        warm_ref = w[0] + w[1] * spec["docs"]
    elif kind == "tasks":
        warm_ref = w[0] + 4.0 * spec["tasks"]
    elif kind == "many":
        warm_ref = w[0] + w[1] * spec["conversations"]
    else:
        warm_ref = w[0] + w[1] * n
    if kind == "window":
        warm_ref = {"32k": 36.0 + 0.006 * 3500, "200k": 38.0 + 0.021 * 3500 - 12, "1m": 38.0 + 0.05 * 3500}[spec["w"]]
    if spec.get("variant") == "varied":
        warm_ref *= 1.04
    warm = warm_ref * scale(arm, n, "time") * wob(rnd, arm)
    cold = (c[0] + c[1] * n) * scale(arm, n, "time") * wob(rnd, arm, 1.5)
    if kind == "floor":
        warm = warm_floor(arm, rnd)
        cold = (14.0 if own(arm) else 9.0) * wob(rnd, arm)
    open_ms = (18.0 if own(arm) else 6.0) * (0.1 if kind in ("floor", "floor-sql") else 1.0) * wob(rnd, arm, 2.0)
    proc = (920.0 if own(arm) else 22.0) * wob(rnd, arm, 3.0)
    f = {"proc_start_ms": proc, "open_ms": open_ms, "first_turn_ms": cold - open_ms, "cold_ms": cold, "ready_to_answer_ms": proc + cold, "warm_turn_ms": warm}
    if kind not in ("floor", "floor-sql"):
        f["warm_net_ms"] = warm - warm_floor(arm, rnd)
    f["ttfr_ms"] = (3.1 if own(arm) else 1.2) * wob(rnd, arm, 3.0)
    f["model_ms_per_turn"] = (0.62 if own(arm) else 0.48) * wob(rnd, arm, 4.0)
    if kind == "stream":
        f["first_delta_ms"] = (131.0 if own(arm) else 112.0) * wob(rnd, arm, 2.0)
    ccpu = scale(arm, n, "cpu")
    f.update({"instructions": (cold + 9 * warm_ref) * 7.0e6 * ccpu * wob(rnd, arm, 0.5), "cycles": (cold + 9 * warm_ref) * 2.6e6 * ccpu * wob(rnd, arm, 0.5), "cpu_ms": (cold + 9 * warm_ref) * 1.3 * ccpu * wob(rnd, arm),
              "warm_instructions": warm_ref * 7.2e6 * ccpu * wob(rnd, arm, 0.5), "warm_cycles": warm_ref * 2.7e6 * ccpu * wob(rnd, arm, 0.5), "warm_cpu_ms": warm_ref * 1.4 * ccpu * wob(rnd, arm)})
    return f


def work_fields(arm, rnd, spec):
    """What the facade counted per warm turn, the kernel's byte counters (absent on macOS: the demo is a Linux run), the store and memory."""
    kind, n = spec["kind"], spec["n"]
    stmts = ((380 + 0.65 * n) if kind == "compat" else (380 + 0.06 * n + (1500 if kind == "large" else 0))) * (1.0 if arm.startswith("pi-durable") and not is_main(arm) else 0.97) * wob(rnd, arm, 0.1)
    pragma = 3.0 if own(arm) else 42.0   # the Go port reads PRAGMA data_version often: counted apart, and part of the total
    f = {"sql_stmts_per_turn": stmts, "sql_read_stmts_per_turn": stmts * 0.62 - pragma, "sql_write_stmts_per_turn": stmts * 0.38, "sql_ddl_stmts_per_turn": 0.0, "sql_pragma_stmts_per_turn": pragma,
         "sql_commits_per_turn": 77.0,
         "rows_returned_per_turn": (20 + 55 * n if kind == "compat" else 2000 + 12 * n) * (1.0 if own(arm) else 0.9) * wob(rnd, arm, 0.1)}
    f["bytes_returned_per_turn"] = f["rows_returned_per_turn"] * 380
    f["wchar_bytes_per_turn"] = (55_000 + 3 * n) * (1.0 if own(arm) else 1.02) * wob(rnd, arm, 0.5)
    f["rchar_bytes_per_turn"] = (90_000 + 120 * n) * (1.0 if own(arm) else 0.95) * wob(rnd, arm, 0.5)
    turns = n + 10
    store = 237_568 + 2616.8 * (min(n, 3500) - 50) if kind == "compat" else 190_000 + 2850.0 * n
    f["store_bytes"] = float(round(store / 4096) * 4096 * (1.02 if is_main(arm) else 1.0))   # the same rows in the same pages: equal for Pi 1.3.0 and PiG by construction, the main build's schema 2 differs
    f["store_bytes_per_turn"] = f["store_bytes"] / turns
    base = 95 + 0.012 * n
    f.update({"peak_rss_mib": base * 1.18 * scale(arm, n, "memory") * wob(rnd, arm, 0.8), "ready_rss_mib": base * 0.8 * scale(arm, n, "memory") * wob(rnd, arm, 0.8),
              "end_rss_mib": base * 1.05 * scale(arm, n, "memory") * wob(rnd, arm, 0.8), "pss_mib": base * 0.75 * scale(arm, n, "memory") * wob(rnd, arm, 0.8)})
    f["peak_mem_mib"] = f["peak_rss_mib"]
    return f


def facts(arm, scenario, spec):
    n = spec["n"]
    digest = digest_of(scenario)
    f = {"fixture_sha256": digest, "fixture_seed": 20261018, "fixture_writer": REFERENCE, "fixture_variant": spec.get("variant", "repeating"), "fixture_turns": n, "fixture_bytes": 237_568 + 2617 * n,
         "turns": n, "window_tokens": spec.get("window"), "compaction": spec.get("compaction"), "shape": spec.get("shape"), "measured_turns": 10, "equivalence": "ok", "row_identical": True,
         "cold_start": "warm page cache", "meter": "cgroup", "perf_scope": "tree", "compaction_ids": [], "lane": {"compat": "compat", "floor": "floor", "floor-sql": "floor"}.get(spec["kind"], "mixed"),
         "measured_script_sha256": digest_of("measured:" + scenario), "fixture_store_sha256": digest_of("store:" + scenario),
         "runtime_versions": {"pi-durable": "1.3.0", "node": "v24.19.0"} if arm.startswith("pi-durable") and not is_main(arm) else {"pig-durable": "0.1.0", "go": "1.27.2"} if arm.startswith("pig") else {"pi-durable": "main 1402973a", "node": "v24.19.0"},
         "runtime_settings": {"window_tokens": spec.get("window"), "compaction_enabled": spec.get("compaction") == "on", "background_tokens": None, "partial_interval_ms": None}}
    if spec["kind"] in ("floor", "floor-sql"):
        for k in ("fixture_turns", "turns", "fixture_bytes", "compaction_ids"):
            f.pop(k)
        f["fixture_turns"] = 0
    return f


def one(arm, scenario, rnd, spec):
    s = sample(arm, scenario, rnd, spec, **facts(arm, scenario, spec), **timing_sample(arm, scenario, rnd, spec))
    if spec["kind"] not in ("floor", "floor-sql"):
        s.update(work_fields(arm, rnd, spec))
    n = spec["n"]
    s["series"] = {"turn_ms": [round(s["warm_turn_ms"] * (1 + wobble(i + rnd) / 100.0), 3) for i in range(10)], "adapter_turn_ms": [round(s["warm_turn_ms"] * 0.97 * (1 + wobble(i + rnd) / 100.0), 3) for i in range(10)]}
    kind = spec["kind"]
    if kind == "many":
        k = spec["conversations"]
        per = (3.1 if own(arm) else 1.4) * wob(rnd, arm, 4.0)
        s["conversations"] = k
        s["end_rss_mib"] = (80.0 if own(arm) else 38.0) * wob(rnd, arm, 0.8) + per * k
        s["mem_per_conv_mib"] = per
    if kind == "grow":
        s.update({"build_ms": (n * (60 + 0.04 * n) / 1.0) * scale(arm, n, "time") * wob(rnd, arm), "early_turn_ms": 30.0 * scale(arm, 50, "time") * wob(rnd, arm), "late_turn_ms": (38.0 + 0.021 * n) * scale(arm, n, "time") * wob(rnd, arm)})
    if kind == "cold":
        s["series"]["cold_ms"] = [round(s["cold_ms"] * (1 + wobble(i + rnd) / 100.0), 3) for i in range(10)]
    if kind == "fail":
        s.update({"compaction_failures": 14, "failed_turns": 0, "failed_requests": 14})
    if kind == "floor-sql":
        s.update({"replay_ms_per_turn": 9.5 * (1.0 if own(arm) else 0.8) * wob(rnd, arm), "stmts_replayed": 354, "commits_replayed": 77, "cpu_ms_replay": 11.0 * (1.0 if own(arm) else 0.8) * wob(rnd, arm)})
    if kind == "floor":
        s["warm_turn_ms"] = warm_floor(arm, rnd)
    s["store_tables"] = {"durable_schema": SCHEMA[arm.removesuffix("-b")], "entries": n * 19, "submissions": n, "tasks": n // 2} if kind not in ("floor", "floor-sql") else {"floor_turns": 40}
    return s


def crash_samples(rnd=1):
    """One sample for each possible (order, kill point) of durable/crash-50, at the driver's 20 evenly spaced points: the reference order passes at every point, as do the orders whose outcome equals its
    own; the Go port writing and resuming ends in another outcome at two points (invented, so that the grid has a failure to show). An order whose resumer cannot open the writer's store is not run."""
    out = []
    for order in ORDERS:
        if order in NOT_POSSIBLE:
            continue
        writer, resumer = order.split(">")
        for k in CRASH_KS:
            differs = order == "pig-durable>pig-durable" and k in FAILING_KS
            s = sample(resumer, "durable/crash-50", rnd, {}, order=order, crash_writer=writer, k=k, commits_total=CRASH_COMMITS, kill_event_commit=k, resume_ok=not differs,
                       invariant_failures="the final state differs from the reference's own outcome at this kill point" if differs else "",
                       signature=json.dumps({"state": f"s{k}", "interrupted": False, "effects": [], "ledger_lookups": k // 3} if not differs else {"state": f"s{k}x", "interrupted": False, "effects": [], "ledger_lookups": k // 3}, sort_keys=True),
                       duplicated_submission=False, reopen_ms=(16.0 if own(resumer) else 5.0) * wob(rnd + k, resumer, 3.0), resume_ms=(45.0 if own(resumer) else 21.0) * wob(rnd + k, resumer, 3.0),
                       ledger=json.dumps({"lookup c1.0.0": 1}))
            s.update({"fixture_sha256": digest_of("durable/crash-50"), "fixture_writer": writer, "turns": 50})
            out.append(s)
    return out


def durable_raw(rounds=12, only=None, quiet=False):
    """The synthetic run. `only`: scenarios to include (QUICK is a short list for tests); None is every workload of the design table."""
    samples = []
    for scenario, spec in workloads():
        if only is not None and scenario not in only:
            continue
        if spec["kind"] == "crash":
            samples += crash_samples()
            continue
        for rnd in range(rounds + 1):
            for arm, _shift in ARMS:
                if scenario == SKIP_SCENARIO and arm.startswith(SKIP_ARM):
                    continue
                samples.append(one(arm, scenario, rnd, spec))
    raw = raw_of(samples, quiet=quiet, rounds=rounds)
    scenarios = [sc for sc, spec in workloads() if (only is None or sc in only) and spec["kind"] not in ("crash", "floor", "floor-sql")]
    raw["run"].update({"reference": REFERENCE, "synthetic": "invented numbers from tests/durable_demo.py: not a measurement of any runtime", "warmup": 1, "aa": "all", "params": {"env": "native"},
                       "durable": gate_summary(scenarios)})
    raw["calibration"] = {"arm": REFERENCE, "metric": "warm_turn_ms", "max_cv": 0.01, "gate": 0.05, "passed": True, "runs": rounds}
    raw["arms"] = {a: {"version": VERSIONS[a], "label": LABELS[a], "runtime_settings": {"env": {}, "left_default": ["GOMAXPROCS", "GOGC", "GOMEMLIMIT"], "source": {}}} for a in BASE_ARMS}
    raw["skipped"] = [{"arm": a, "scenario": SKIP_SCENARIO, "api": None, "reason": SKIP_REASON} for a in (SKIP_ARM, SKIP_ARM + "-b")] if only is None or SKIP_SCENARIO in only else []
    return raw


def label_of(scenario):
    return scenario.split("/", 1)[1]


def gate_summary(scenarios):
    """What the driver records in raw.json `run.durable`: the gate's outcome, the fixtures it built (by label) and the orders of runtimes it could not open across."""
    built = {label_of(sc): {"script_sha256": digest_of(sc), "store_sha256": digest_of("store:" + sc), "writer": REFERENCE, "build_s": 1.5, "store_bytes": 237_568, "turns": dict(workloads())[sc]["n"], "cached": False} for sc in scenarios}
    cross = {label_of(sc): {order: ({"ok": False, "why": NOT_POSSIBLE[order]} if order in NOT_POSSIBLE else {"ok": True, "messages": 202}) for order in ORDERS if order.split(">")[0] != order.split(">")[1]} for sc in scenarios[:2]}
    return {"env": "native", "oracle": REFERENCE, "passed": True, "failures": [], "fixtures": built, "failed_fixtures": {}, "flaky": {}, "different_work": {},
            "capabilities": {"pig-durable": {"documents": None, "tasks": None, "subagents": SKIP_REASON}}, "row_identical": {label_of(sc): True for sc in scenarios[:2]},
            "cross_open": cross, "seed": 20261018, "generator": "buffon-durable-script/1", "cold_start": "warm page cache: every sample's store is a fresh copy read once before timing"}


def equivalence_doc(scenarios=("durable/compat-50", "durable/mixed-3500")):
    """The gate's full record, as the runner writes it to equivalence.json: the run summary and, for each fixture, the scenarios each arm ran with the digests of what it sent and what it left."""
    summary = gate_summary(list(scenarios))
    recs = {}
    for sc in scenarios:
        recs[label_of(sc)] = {name: {arm: {"compaction_ids": 0, "requests": 6, "requests_sha256": digest_of("requests:" + name), "state_sha256": digest_of("state:" + name), "statuses": ["done", "done", "done"],
                                           "transcript_messages": 202} for arm in BASE_ARMS} for name in ("base", "documents", "subagent", "tasks")}
    return {"capabilities": summary["capabilities"], "cross_open": summary["cross_open"], "differences": {}, "different_work": {}, "failures": [], "fixtures": {"built": summary["fixtures"], "failed": {}, "scenarios": recs},
            "flaky": {}, "oracle": REFERENCE, "passed": True, "row_identical": summary["row_identical"]}


def with_miniflare(raw, scenario="durable/mixed-3500"):
    """Samples of one workload from the reference arm in the Miniflare environment: the cell they make has its own key (variant `miniflare`), and the platform's row counters exist."""
    spec = dict(workloads())[scenario]
    for rnd in range(raw["run"]["rounds"] + 1):
        for arm in ("pi-durable", "pi-durable-b"):
            s = one(arm, scenario, rnd, spec)
            for k in ("warm_turn_ms", "cold_ms", "warm_net_ms"):
                s[k] *= 1.9
            s.update({"env": "miniflare", "rows_read_per_turn": 5400.0 * wob(rnd, arm, 0.2), "rows_written_per_turn": 869.0})
            raw["samples"].append(s)
    return raw


def write_run(path, raw=None, **kw):
    """A run directory: raw.json and equivalence.json (what the dashboard's Method page reads)."""
    from buffon.runner import raw as rawlib
    os.makedirs(path, exist_ok=True)
    raw = raw or durable_raw(**kw)
    rawlib.write(raw, path)
    with open(os.path.join(path, "equivalence.json"), "w") as f:
        json.dump(equivalence_doc(["durable/" + label for label in raw["run"]["durable"]["fixtures"]][:2]), f, indent=1)
    return path
