# SPDX-License-Identifier: Apache-2.0
"""Synthetic runs with telemetry for the noise, health, series and submission tests."""
import copy

from tests.test_report import raw_of, sample, wobble

NAMES = (("pi-node", 0), ("pi-node-b", 3), ("other", 1), ("other-b", 5))


def quiet_telemetry(own_cpu_ms=100.0, window_ms=500.0, cpus=2, **over):
    """A telemetry.system record of a quiet sample on two pinned CPUs: the CPU set was busy with exactly the sample's own CPU time."""
    t = {"cpuset": {"window_ms": window_ms, "cpuset_cpus": cpus, "cpuset_busy_ms": own_cpu_ms, "cpuset_user_ms": own_cpu_ms, "cpuset_system_ms": 0.0, "cpuset_iowait_ms": 0.0, "cpuset_irq_ms": 0.0,
                  "cpuset_steal_ms": 0.0, "cpuset_idle_ms": window_ms * cpus - own_cpu_ms, "session_throttled_periods": 0, "session_throttled_us": 0},
         "before": {"load1": 1.0, "runnable": 2, "mhz_min": 2400.0, "mhz_mean": 2400.0, "mhz_max": 2400.0}, "after": {"load1": 1.0, "runnable": 2, "mhz_min": 2400.0, "mhz_mean": 2400.0, "mhz_max": 2400.0},
         "during": {"readings": 2, "mhz_min": 2400.0, "mhz_mean": 2400.0, "mhz_max": 2400.0, "load1_max": 1.0, "runnable_max": 2, "cpuset_busy_max": 0.2},
         "cgroup": {"mode": "cgroup", "meters": 1, "cpu_usage_ms": own_cpu_ms, "throttled_periods": 0, "throttled_us": 0, "memory_peak_mib": 40.0},
         "gate": {"status": "passed", "waited_ms": 260, "checks": 1, "pinned_busy": 0.0, "host_load1": 1.0, "host_runnable": 2},
         "collector": {"thread_cpu_ms": 0.9, "readings": 4, "end_cpu_ms": 0.4, "begin_cpu_ms": 0.3}, "sources": ["proc_stat", "cpufreq", "loadavg", "cgroup_throttle"]}
    for group, vals in over.items():
        t[group] = dict(t.get(group, {}), **vals)
    return t


def run(rounds=12, ref=100.0, arm=150.0, quiet=True, telemetry=True, mutate=None, scenario="overhead/print", metrics=("cpu_ms", "wall_ms"), calibration_cv=0.01, warmup=1):
    """pi-node, its copy, an arm and its copy over `warmup` + `rounds` rounds, deterministic, with quiet telemetry; `mutate(sample)` edits any sample."""
    samples = []
    for r in range(warmup + rounds):
        for name, shift in NAMES:
            base = ref if name.startswith("pi-node") else arm
            vals = {m: (base if m == "cpu_ms" else base * 4) + wobble(r + shift) for m in metrics}
            s = sample(name, scenario, r, warmup=r < warmup, **vals)
            s["t_utc"] = f"2026-10-11T12:{r:02d}:{shift:02d}Z"
            s.update({"quiet_wait_ms": 260, "quiet_checks": 1, "host_load1": 1.0, "host_runnable": 2, "pinned_busy": 0.0})
            if telemetry:
                s["telemetry"] = {"system": quiet_telemetry(vals["cpu_ms"])}
            if mutate:
                mutate(s)
            samples.append(s)
    raw = raw_of(samples, quiet=quiet, rounds=rounds)
    raw["calibration"] = {"arm": "pi-node", "metric": "cpu_ms", "max_cv": calibration_cv, "gate": 0.05, "passed": calibration_cv <= 0.05, "runs": 12}
    raw["arms"] = {"pi-node": {"version": "1"}, "other": {"version": "2"}}
    raw["run"]["warmup"] = warmup
    return raw


def facts():
    return {"cpu_model": "Test CPU", "kernel": "6.1", "pinned_cpus": "1-2", "mock_cpus": "3", "governors": {"1": "performance", "2": "performance"}, "fixed_clock": True, "throttled_usec": 0,
            "load_before": [0.5, 0.4, 0.3], "load_after": [0.6, 0.4, 0.3], "idle_before": {"1": 0.0, "2": 0.01}, "idle_after": {"1": 0.0, "2": 0.0},
            "cpumon": {"pinned_busy_mean": 0.2, "pinned_busy_max": 0.4, "host_busy_mean": 0.02}, "cgroup": {}, "runner_commit": "a" * 40, "runner_tree": "b" * 40, "runner_dirty": False}


def write_dir(path, raw, f=None):
    import json
    import os
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "raw.json"), "w") as fh:
        json.dump(raw, fh)
    with open(os.path.join(path, "facts.json"), "w") as fh:
        json.dump(f or facts(), fh)
    return path


def clone(raw):
    return copy.deepcopy(raw)
