# SPDX-License-Identifier: Apache-2.0
"""A synthetic sample run for the HTML report: invented numbers, fictional arm names, several families. It exists to render the report in tests and for design review. It is not a result of any harness."""
import os

from tests.telemetry_fixtures import quiet_telemetry
from tests.test_report import raw_of, sample, wobble

REFERENCE = "pi-node"
# (arm, copy offset, scale against the reference per metric family). The names are fictional.
ARMS = (("pi-node", 0, 1.0), ("pi-node-b", 3, 1.0), ("demo-alpha", 1, 0.55), ("demo-alpha-b", 5, 0.55), ("demo-beta", 2, 1.0), ("demo-beta-b", 6, 1.0),
        ("demo-gamma", 4, 1.8), ("demo-gamma-b", 7, 1.8))
# (scenario, {metric: reference value}); memory metrics scale differently below so the memory rows are not a copy of the CPU rows.
WORKLOADS = (("overhead/print", {"cpu_ms": 410.0, "wall_ms": 1250.0, "instructions": 1.9e9, "peak_rss_mib": 118.0, "requests": 2.0, "request_bytes": 5200.0, "request_bytes_per_turn": 2600.0}),
             ("overhead/rpc", {"cpu_ms": 150.0, "wall_ms": 420.0, "instructions": 7.1e8, "peak_rss_mib": 131.0}),
             ("overhead/pty", {"cpu_ms": 820.0, "peak_rss_mib": 164.0}),
             ("overhead/print-ext10", {"cpu_ms": 620.0, "peak_rss_mib": 142.0}),
             ("streaming/tui-prose", {"n_cpu_ms_per_1k_tokens": 38.0, "n_wall_ms": 6100.0}),
             ("longsession/grow-n", {"turn_cpu_ms": 74.0, "peak_rss_mib": 210.0}),
             ("longsession/resume-n", {"ready_cpu_ms": 540.0, "ready_rss_mib": 96.0}),
             ("devloop/first-run", {"wall_ms": 2400.0}))
WIRE_METRICS = ("requests", "request_bytes", "request_bytes_per_turn")   # what the mock received: the same for every demo arm, so they do not scale like cost
NO_PTY = ("demo-gamma", "demo-gamma-b")   # these demo arms have no terminal mode: no sample, and the manifest's reason in `skipped`
NO_PTY_REASON = "no terminal mode: it has no full-screen view to drive"
FAULTS = ("http-429-retry", "disconnect-midstream", "kill-mid-tool")
MEMORY_SCALE = {"demo-alpha": 1.3, "demo-alpha-b": 1.3, "demo-beta": 0.97, "demo-beta-b": 0.97, "demo-gamma": 1.1, "demo-gamma-b": 1.1}


def demo_raw(rounds=12, quiet=False, wire=True, divergence=True):
    """`wire`: the samples of overhead/print carry the wire metrics. `divergence`: demo-beta's manifest declares different work in overhead/print-ext10."""
    samples = []
    for rnd in range(rounds + 1):
        for scenario, metrics in WORKLOADS:
            for arm, shift, scale in ARMS:
                if scenario == "overhead/pty" and arm in NO_PTY:
                    continue
                values = {}
                for metric, base in metrics.items():
                    if metric in WIRE_METRICS and not wire:
                        continue
                    k = MEMORY_SCALE.get(arm, 1.0) if metric.endswith("_mib") else 1.0 if metric in WIRE_METRICS else scale
                    values[metric] = base * k * (1 + wobble(rnd + shift) / 200.0)
                s = sample(arm, scenario, rnd, api="openai-completions", warmup=rnd == 0, **values)
                s["t_utc"] = f"2026-10-11T12:{rnd:02d}:{shift:02d}Z"
                s.update({"quiet_wait_ms": 260, "quiet_checks": 1, "host_load1": 1.0, "host_runnable": 2, "pinned_busy": 0.0})
                s["telemetry"] = {"system": quiet_telemetry(values.get("cpu_ms", 100.0))}
                samples.append(s)
    for fault in FAULTS:
        for rep in range(3):
            for arm, shift, scale in ARMS:
                differs = arm.startswith("demo-gamma") and fault == "kill-mid-tool"
                samples.append(sample(arm, f"reliability/{fault}", rep, api="openai-completions", signature="T" if differs else "S", invariants_ok=True))
    raw = raw_of(samples, quiet=quiet, rounds=rounds)
    raw["run"]["warmup"] = 1
    raw["run"]["synthetic"] = "invented numbers and fictional harness names from tests/report_demo.py"
    raw["calibration"] = {"arm": REFERENCE, "metric": "cpu_ms", "max_cv": 0.01, "gate": 0.05, "passed": True, "runs": 12}
    raw["arms"] = {REFERENCE: {"version": "1.1.0"}, "demo-alpha": {"version": "0.1"}, "demo-beta": {"version": "0.2"}, "demo-gamma": {"version": "0.3"}}
    # runtime settings, a manifest-style divergence (read by buffon/report/cells.py like a real one) and the slot, so every element of the site renders
    raw["arms"][REFERENCE]["runtime_settings"] = {"env": {"NODE_OPTIONS": "--max-old-space-size=2048", "UV_THREADPOOL_SIZE": "4"}, "left_default": ["GOMAXPROCS", "GOGC"], "source": {"NODE_OPTIONS": "manifest", "UV_THREADPOOL_SIZE": "manifest"}}
    raw["arms"]["demo-alpha"]["runtime_settings"] = {"env": {"GOGC": "100"}, "left_default": ["GOMEMLIMIT"], "source": {"GOGC": "manifest"}}
    raw["arms"]["demo-beta"]["runtime_settings"] = {"env": {"BUN_JSC_useJIT": "1"}, "left_default": [], "source": {"BUN_JSC_useJIT": "manifest"}}
    if divergence:
        raw["arms"]["demo-beta"]["divergences"] = [{"workloads": ["overhead/print-ext10"], "metrics": [], "reason": "it loads its own extensions in another form, so the ten-extension task is different work", "source": "docs/METHODOLOGY.md"}]
    raw["arms"]["demo-gamma"]["runtime_settings"] = {"env": {}, "left_default": ["GOMAXPROCS", "GOGC", "GOMEMLIMIT"], "source": {}}
    # demo-gamma has no terminal mode; it also does not speak the Messages API, so that skip is per API and does not make "One prompt" a workload it did not run
    raw["skipped"] = [{"arm": a, "scenario": "overhead/pty", "api": "openai-completions", "reason": NO_PTY_REASON} for a in NO_PTY] + \
        [{"arm": "demo-gamma", "scenario": "overhead/print", "api": "anthropic-messages", "reason": "it does not speak anthropic-messages"}]
    raw["run"]["slot"] = {"id": 2, "of": 4, "cpus": "4-7", "calibration": "slots/2/calibration.json"}
    return raw


def demo_faithfulness_dir(path):
    """A faithfulness.json directory with invented scores: one arm above the floor, one below, one not measured."""
    import json
    os.makedirs(path, exist_ok=True)
    doc = {"reference": {"arm": REFERENCE, "version": "1.1.0"}, "twin": "pi-node-b", "probe_set_version": "sample", "probes": [], "unstable": [],
           "scores": {REFERENCE: {"overall": 100.0}, "demo-alpha": {"overall": 94.0}, "demo-gamma": {"overall": 71.0}}}
    with open(os.path.join(path, "faithfulness.json"), "w") as f:
        json.dump(doc, f)
    return path


def with_sweep(raw):
    """The extension sweep of the print and RPC modes: 5, 50 and 100 extensions beside the ten (print-ext10) and none (print, rpc) the demo already has."""
    for rnd in range(raw["run"]["rounds"] + 1):
        for arm, shift, scale in ARMS:
            for n in (5, 50, 100):
                for mode, metric, base in (("print", "cpu_ms", 410.0), ("rpc", "ready_cpu_ms", 300.0)):
                    if mode == "rpc" and arm.startswith("demo-gamma"):
                        continue
                    v = (base + 22.0 * n) * scale * (1 + wobble(rnd + shift) / 200.0)
                    s = sample(arm, f"overhead/{mode}-ext{n}", rnd, api="openai-completions", warmup=rnd == 0, **{metric: v})
                    s["t_utc"] = f"2026-10-11T13:{rnd:02d}:{shift:02d}Z"
                    raw["samples"].append(s)
    return raw


def with_durable(raw):
    """A durable/* workload family of Buffon's own (the Durable section picks up any durable/* scenario): `durable/append`, CPU and wall time for every arm."""
    for rnd in range(raw["run"]["rounds"] + 1):
        for arm, shift, scale in ARMS:
            values = {metric: base * scale * (1 + wobble(rnd + shift) / 200.0) for metric, base in (("cpu_ms", 95.0), ("wall_ms", 140.0))}
            s = sample(arm, "durable/append", rnd, api="openai-completions", warmup=rnd == 0, **values)
            s["t_utc"] = f"2026-10-11T14:{rnd:02d}:{shift:02d}Z"
            raw["samples"].append(s)
    return raw


def box_table(columns, rows):
    """What Node's console.table prints for these columns and rows: the box the suites' own parser reads."""
    widths = [max(len(c), *(len(r[i]) for r in rows)) + 2 for i, c in enumerate(columns)]
    line = lambda cells: "│" + "│".join(" " + c.ljust(w - 1) for c, w in zip(cells, widths)) + "│"
    top, mid, bottom = (a + b.join("─" * w for w in widths) + c for a, b, c in (("┌", "┬", "┐"), ("├", "┼", "┤"), ("└", "┴", "┘")))
    return "\n".join([top, line(columns), mid] + [line(r) for r in rows] + [bottom]) + "\n"


def write_suite_run(path, record, stdout, rows=None):
    """An external suite run directory as `buffon external run` writes it (external-suite.json, stdout.txt, stderr.txt and, when the table parsed, rows.jsonl)."""
    import json
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "stdout.txt"), "w", encoding="utf-8") as f:
        f.write(stdout)
    with open(os.path.join(path, "stderr.txt"), "w", encoding="utf-8") as f:
        f.write("")
    if rows is not None:
        with open(os.path.join(path, "rows.jsonl"), "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
    host = {"cpu_model": "Demo CPU (invented)", "memory_gib": 64, "kernel": "6.8.0-demo"}
    doc = {"kind": "external-suite", "licence": "MIT", "cwd": ".", "exit": 0, "timed_out": False, "egress": [], "wall_s": 41.2, "stdout_tail": stdout[-200:], "stderr_tail": "", "notes": "", "host": host,
           "label": "the suite's own numbers, run as it is upstream; not a buffon measurement and in no buffon aggregate", "pin_source": "suite", "units": {}, **record}
    with open(os.path.join(path, "external-suite.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    return path


def demo_external(tmp):
    """(external suite run directories, imported result directories) for the demo's Other suites, written under tmp. Invented numbers, like the rest of the demo:
    a durable-storage-memory console-table run for two targets (their columns match, so one table has a column for each), a Pi-Bolt benchmark.py run (the suite prints a table Buffon does not read),
    a tool-output run whose table did not parse, a PiG storage benchmark run, and an imported Pi-Bolt result set."""
    from buffon.external import results as extresults, suites as extsuites
    columns = ["scenario", "RSS after seed MiB", "heap after GC MiB", "seed time"]
    memory = {"pi-node": [["100k ops", "148.2", "61.4", "0.9 s"], ["1M ops", "1,203.7", "512.0", "8.1 s"], ["10M ops", "9,847.5", "4,311.9", "1 min 24 s"]],
              "demo-alpha": [["100k ops", "91.9", "38.1", "0.6 s"], ["1M ops", "746.3", "317.4", "5.2 s"], ["10M ops", "6,105.4", "2,673.2", "52 s"]]}
    runs = []
    for target, arm in (("pi-node", "pi-node"), ("demo-alpha", "demo-alpha")):
        rows = memory[target]
        stdout = "> bench:storage:memory\n" + box_table(columns, rows)
        record = {"suite": "durable-storage-memory", "title": extsuites.SUITES["durable-storage-memory"].title, "target": target, "arm": arm, "repo": "pi", "commit": extsuites.PI_COMMIT,
                  "argv": ["npm", "run", "bench:storage:memory"], "started_utc": "2026-10-17T09:12:27Z", "table": "console-table", "rows": len(rows)}
        runs.append(write_suite_run(os.path.join(tmp, f"durable-storage-memory-{target}"), record, stdout, [dict(zip(columns, r)) for r in rows]))
    bolt = ("build        scenario            median ms   n\n" "demo-alpha   startup (version)      81.0    8\n" "demo-alpha   headless prompt       262.5    8\n" "demo-alpha   interactive ready    1750.0    8\n")
    runs.append(write_suite_run(os.path.join(tmp, "pi-bolt-benchmark-demo-alpha"), {"suite": "pi-bolt-benchmark", "title": extsuites.SUITES["pi-bolt-benchmark"].title, "target": "build", "arm": "demo-alpha", "repo": "pi-bolt",
                                "commit": extsuites.PI_BOLT_COMMIT, "argv": ["python3", "bench/benchmark.py", "--build", "demo-alpha=demo-alpha --mode json"], "started_utc": "2026-10-17T10:40:02Z", "table": None}, bolt))
    broken = "> bench:tool-output\n│ ms │ liveCommits │ outputSets │ commitP50Ms │\n│ 1200 │ 40 │ 3 │\n"
    runs.append(write_suite_run(os.path.join(tmp, "durable-tool-output-pi-node"), {"suite": "durable-tool-output", "title": extsuites.SUITES["durable-tool-output"].title, "target": "pi-node", "arm": "pi-node", "repo": "pi",
                                "commit": extsuites.PI_COMMIT, "argv": ["npm", "run", "bench:tool-output"], "started_utc": "2026-10-17T09:30:11Z", "table": "console-table", "rows": None,
                                "rows_error": "console table row has 3 cells for 4 columns: '│ 1200 │ 40 │ 3 │'"}, broken))
    gobench = "goos: linux\ngoarch: amd64\nBenchmarkStorageAppend-8   \t  412308\t      2876 ns/op\t     512 B/op\t       4 allocs/op\nBenchmarkStorageReplay-8   \t     318\t   3741920 ns/op\nPASS\n"
    runs.append(write_suite_run(os.path.join(tmp, "durable-storage-pig-native"), {"suite": "durable-storage", "title": extsuites.SUITES["durable-storage"].title, "target": "pig-native", "arm": None, "repo": "pig",
                                "commit": extsuites.PIG_COMMIT, "argv": ["go", "test", "-run", "^$", "-bench", "BenchmarkStorage", "-benchmem", "./durable/storage/"], "started_utc": "2026-10-17T11:05:40Z", "table": None}, gobench))
    files = os.path.join(tmp, "published-files")
    os.makedirs(files)
    with open(os.path.join(files, "headless.jsonl"), "w", encoding="utf-8") as f:
        for build, cpu in (("pibolt", 80.0), ("pi", 800.0)):
            for i in range(3):
                f.write('{"build": "%s", "scenario": "headless", "wall_ms": %.1f, "cpu_ms": %.1f, "peak_mb": 90.0, "ok": true}\n' % (build, cpu * 1.4 + i, cpu + i))
    imported = os.path.join(tmp, "pi-bolt-published-demo")
    extresults.import_files([os.path.join(files, "headless.jsonl")], imported, {"id": "pi-bolt-published-demo", "title": "Pi-Bolt's published headless numbers (demo copy)", "source_url": "https://github.com/opensec-git/Pi-Bolt/tree/pi-bolt/bench/results",
                            "repo": "opensec-git/Pi-Bolt", "commit": extsuites.PI_BOLT_COMMIT, "version": "pibolt 0.8.0, pi 1.0.3", "host": "linux-x64, the source's own machine", "licence": "MIT", "published": "2026-10-11"})
    return runs, [imported]


def build_demo_site(out, rounds=6, external=True):
    """The demo site at `out`, with every section: the large write, the extension sweep, faults, the exact agent limits with and without ten extensions, and the Other suites.
    `python3 -c "from tests.report_demo import build_demo_site as b; b('$HOME/arena-work/site-v2-demo')"`."""
    import tempfile
    from buffon.dashboard import build as dashboard
    from tests.telemetry_fixtures import write_dir
    from tests.test_dashboard_scale import with_swarms, with_write
    tmp = tempfile.mkdtemp()
    raw = with_swarms(with_write(with_sweep(demo_raw(rounds=rounds))))
    src = write_dir(os.path.join(tmp, "run"), raw)
    suites, results = demo_external(os.path.join(tmp, "external")) if external else ((), ())
    dashboard.build([src], out, faithfulness=[demo_faithfulness_dir(os.path.join(tmp, "faith"))], external_suites=suites, external_results=results)
    return out
