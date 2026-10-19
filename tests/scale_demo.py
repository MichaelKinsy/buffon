# SPDX-License-Identifier: Apache-2.0
"""Invented swarm samples for the dashboard tests and for design review. Nothing here is a result of any harness.

`search` makes the samples of the limit search (scale/agents-limit, scale/print-limit and the ext10 pair): one sample for each round, holding every probe. `demo_swarms` is a run of them.
`ladder` and `demo_ladders` are the legacy fixture: the samples of a run made before the search, one sample for each rung (scale/agents-N, scale/print-N) and the skipped entries
`not reached: stopped at N agents (<cause>)`."""
import hashlib

TURNS = 3
CPUS = (40, 41, 42, 43, 44, 45, 46, 47)
NO_EXT = "it does not load Pi extensions"
PART_EXT = "it loads only part of Pi's extensions"
NO_RPC = "no Pi-dialect RPC mode: its own protocol is not Pi's JSONL RPC"


def jitter(*key):
    """A deterministic number in [-1, 1) from a key, so rounds differ a little and a test sees the same data every time."""
    return int(hashlib.sha256(repr(key).encode()).hexdigest()[:8], 16) / 2 ** 31 - 1


def measure(arm, kind, n, rnd, *, per_agent_mib, base_mib, limit_mib, ncpus, stop=None, stall=None, legacy=False, saturate_at=None, salt=()):
    """The fields of one probe or one rung of N agents in round `rnd`, and (N, words) when it did not complete, else None. The container stops at the first N whose memory would pass the limit
    (an OOM kill), or at N == `stop` (a timeout), or at N == `stall` (the container sat at its limit, nothing killed). `legacy` leaves out `start_cpu_ms_per_agent`, as a run made before the CPU window
    was fixed does."""
    j = jitter(arm, kind, n, rnd, *salt)
    per = per_agent_mib * (1 + 0.04 * j)
    peak = base_mib + per * n
    s = {"mem_baseline_mib": base_mib, "mock_cpu_ms": 900.0 * n / 8 + 40, "mock_saturated": saturate_at is not None and n >= saturate_at, "pids_peak": 12 * n + 8,
         "throttled_periods": int(n * 3 * (1 + j / 4)), "oom_kills": 0}
    stopped = None
    if peak > 0.97 * limit_mib:
        s.update({"agents_ok": int(n * 0.6), "mem_peak_mib": float(limit_mib), "oom_kills": 3, "stop_cause": "oom", "failure": f"out of memory: the kernel killed {n - int(n * 0.6)} agents ({n} started)"})
        stopped = (n, "out of memory")
    elif stall is not None and n >= stall:
        s.update({"agents_ok": n - 3, "mem_peak_mib": float(limit_mib), "stop_cause": "stall", "failure": f"stalled at the limit, nothing killed: no agent made progress for 10 s at the {limit_mib} MiB memory limit"})
        stopped = (n, "stalled at the limit, nothing killed")
    elif stop is not None and n >= stop:
        s.update({"agents_ok": n - 1, "mem_peak_mib": peak, "stop_cause": "timeout", "failure": f"timed out after 300 s: {n - 1} of {n} agents answered"})
        stopped = (n, "timeout")
    else:
        s.update({"agents_ok": n, "mem_peak_mib": peak, "mem_per_agent_mib": (peak - base_mib) / n, "pss_mib_per_agent": per * 0.8,
                  "cpu_ms": 380.0 * n * TURNS * (1 + j / 20), "cpu_ms_per_agent_turn": 380.0 * (1 + j / 20), "turns_per_s": n * TURNS / (1.2 + 0.5 * n / ncpus) * (1 + j / 30)})
        if kind.startswith("rpc"):
            if not legacy:
                s["start_cpu_ms_per_agent"] = 220.0 * (1 + j / 20)
            s.update({"ready_ms": 600.0 + 40 * n, "latency_ms_p50": 300.0 + 20 * n, "latency_ms_p95": 420.0 + 45 * n, "latency_ms_max": 500.0 + 60 * n})
        else:
            s.update({"makespan_ms": 1500.0 + 70 * n, "wall_ms_p50": 1200.0 + 30 * n, "wall_ms_p95": 1400.0 + 60 * n})
    if "stop_cause" in s:   # the timing of a stopped probe is not a measurement of work: agents were being killed. It is large, so a chart that plots it loses its scale
        s.update({"latency_ms_p95": 90000.0, "wall_ms_p95": 90000.0, "makespan_ms": 120000.0, "cpu_ms_per_agent_turn": 200000.0, "turns_per_s": 0.2})
    return s, stopped


def search(arm, kind, *, per_agent_mib, ext=False, base_mib=120.0, limit_mib=4096, cpus=CPUS, cap=8192, rounds=5, resolution=1, stop=None, stall=None, saturate_at=None):
    """The samples of one harness's limit search, one for each round (round 0 is the warm-up): N doubles, 1, 2, 4, ... up to `cap`, until a probe does not complete; the search then bisects between the
    last probe that completed and the first that did not, down to `resolution` (1 is the exact number). A probe at the cap that completes makes the harness 'at least the cap'.
    `kind` is "rpc" or "print"; `ext` makes it the ext10 scenario (ten extensions loaded: the caller gives the larger per-agent memory)."""
    scenario = ("scale/agents-" if kind == "rpc" else "scale/print-") + ("ext10" if ext else "limit")
    samples = []
    for rnd in range(rounds + 1):
        probes = []

        def probe(n, phase):
            fields, stopped = measure(arm, kind, n, rnd, per_agent_mib=per_agent_mib, base_mib=base_mib, limit_mib=limit_mib, ncpus=len(cpus), stop=stop, stall=stall, saturate_at=saturate_at, salt=("ext",) if ext else ())
            p = {"n": n, "phase": phase, "ok": stopped is None, "agents_ok": fields.pop("agents_ok"), "pids_max": 64 * n + 1024, **fields, "work_s": 20.0 + n * 0.5, "prepare_s": 3.0 + n * 0.1}
            probes.append(p)
            return p["ok"]
        n, last, first = 1, 0, None
        while True:
            if probe(n, "double"):
                last = n
                if n >= cap:
                    break
                n = min(n * 2, cap)
            else:
                first = n
                break
        while first is not None and first - last > resolution:
            mid = (last + first) // 2
            if probe(mid, "bisect"):
                last = mid
            else:
                first = mid
        s = {"arm": arm, "scenario": scenario, "api": None, "round": rnd, "warmup": rnd == 0, "wall_s": sum(p["work_s"] + p["prepare_s"] for p in probes),
             "swarm": {"memory_mib": limit_mib, "cpus": list(cpus), "pids_max": max(p["pids_max"] for p in probes)}, "agents_limit": last, "limit_capped": first is None, "limit_cap": cap,
             "limit_resolution": resolution, "probe_count": len(probes), "extensions": 10 if ext else 0, "probes": probes}
        if first is not None:
            at = next(p for p in probes if p["n"] == first and not p["ok"])
            s.update({"first_failure": first, "limit_cause": at["stop_cause"], "limit_failure": at["failure"]})
            if last == 0:
                s.update({"failure": at["failure"], "stop_cause": at["stop_cause"]})
        samples.append(s)
    return samples


def demo_swarms(limit_mib=4096):
    """(samples, skipped) of a search run: two harnesses that stop by memory at different sizes (each with the ten-extension pair), one that stops by timeout and one that stalls, one that completes the
    cap, one that has a limit of 0 with the extensions (its first agent does not fit), harnesses that do not load Pi extensions (all of them, or part of them), and one that has no RPC mode."""
    samples, skipped = [], []

    def add(arm, kind, ext=False, **kw):
        samples.extend(search(arm, kind, ext=ext, limit_mib=limit_mib, **kw))

    def cannot(arm, scenario, reason):
        skipped.append({"arm": arm, "scenario": scenario, "api": None, "reason": reason})
    add("pi-node", "rpc", per_agent_mib=190)
    add("pi-node", "rpc", ext=True, per_agent_mib=230)
    add("pi-node", "print", per_agent_mib=150)
    add("pi-node", "print", ext=True, per_agent_mib=175)
    add("demo-alpha", "rpc", per_agent_mib=28)
    add("demo-alpha", "rpc", ext=True, per_agent_mib=37)
    add("demo-alpha", "print", per_agent_mib=12, saturate_at=128)
    add("demo-alpha", "print", ext=True, per_agent_mib=4200)   # with the extensions not even one agent fits
    add("demo-gamma", "rpc", per_agent_mib=60, stop=64)
    add("demo-gamma", "print", per_agent_mib=0.4)   # completes the cap
    cannot("demo-gamma", "scale/agents-ext10", NO_EXT)
    cannot("demo-gamma", "scale/print-ext10", NO_EXT)
    add("demo-beta", "print", per_agent_mib=95, stall=32)
    cannot("demo-beta", "scale/agents-limit", NO_RPC)
    cannot("demo-beta", "scale/agents-ext10", NO_RPC)
    cannot("demo-beta", "scale/print-ext10", PART_EXT)
    return samples, skipped


def ladder(arm, kind, *, per_agent_mib, base_mib=120.0, limit_mib=4096, cpus=CPUS, cap=256, rounds=3, stop=None, stall=None, legacy=False, saturate_at=None, pids_max=32768):
    """(samples, skipped) of one harness's ladder, as a run made before the search has them: N = 1, 2, 4, ... up to `cap`, one sample for each rung and round. The ladder stops at the first N that
    does not complete (see `measure`). Larger rungs are then skipped with the runner's reason."""
    samples, skipped, n = [], [], 1
    scenario = "scale/agents-{}" if kind == "rpc" else "scale/print-{}"
    stopped = None
    while n <= cap:
        if stopped:
            skipped.append({"arm": arm, "scenario": scenario.format(n), "api": "openai-completions", "reason": f"not reached: stopped at {stopped[0]} agents ({stopped[1]})"})
            n *= 2
            continue
        for rnd in range(rounds + 1):
            fields, stop_at = measure(arm, kind, n, rnd, per_agent_mib=per_agent_mib, base_mib=base_mib, limit_mib=limit_mib, ncpus=len(cpus), stop=stop, stall=stall, legacy=legacy, saturate_at=saturate_at)
            samples.append({"arm": arm, "scenario": scenario.format(n), "api": "openai-completions", "round": rnd, "warmup": rnd == 0, "agents": n,
                            "swarm": {"memory_mib": limit_mib, "cpus": list(cpus), "pids_max": pids_max}, **fields})
            stopped = stopped or stop_at
        n *= 2
    return samples, skipped


def demo_ladders(limit_mib=4096):
    """The legacy fixture: two harnesses that stop by memory at different sizes, one that stops by timeout, one that reaches the cap, one that has no RPC mode."""
    samples, skipped = [], []
    for arm, kind, kw in (("pi-node", "rpc", {"per_agent_mib": 190}), ("pi-node", "print", {"per_agent_mib": 150}),
                          ("demo-alpha", "rpc", {"per_agent_mib": 28}), ("demo-alpha", "print", {"per_agent_mib": 12, "saturate_at": 128}),
                          ("demo-gamma", "rpc", {"per_agent_mib": 60, "stop": 64}), ("demo-gamma", "print", {"per_agent_mib": 45}),
                          ("demo-beta", "print", {"per_agent_mib": 95, "stall": 32})):
        s, k = ladder(arm, kind, limit_mib=limit_mib, **kw)
        samples += s
        skipped += k
    skipped.append({"arm": "demo-beta", "scenario": "scale/agents-1", "api": "openai-completions", "reason": NO_RPC})
    return samples, skipped
