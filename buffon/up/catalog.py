# SPDX-License-Identifier: Apache-2.0
"""What `buffon up` can run: the presets, the tracks, the default harness set, and for each benchmark what it measures, how it is wired and what a sample costs.

A workload's state is `wired` (registered, runs on the arms that support its mode), `partly wired` (runs, but some arms or rows are N/A or need extra arms), or `not run`
(designed, documented, no code yet: it is listed so nobody wonders where it went)."""
import fnmatch
import math

# Pi, the Pi-compatible builds, and two harnesses unrelated to Pi; each runs what it can, and a workload it cannot run is n/a with the reason. omp is left out by
# default (owner, 2026-10-15): `--harness omp` still runs it.
DEFAULT_HARNESSES = ("pi-node", "pig-tip", "pibolt", "opencode-v2", "codex")
REFERENCE = "pi-node"
# Short names for the arm a person means: `--harness pig,pi,pi-bolt`. A full arm id always wins; a glob matches ids.
SHORT_NAMES = {"pi": "pi-node", "pi-node": "pi-node", "pig": "pig-tip", "pi-bolt": "pibolt", "bolt": "pibolt", "bun": "pi-bun", "pig-latest": "pig-tip", "latest": "pig-tip"}

# name -> the workloads, wire APIs, round cap, whether rounds stop adaptively, the evals, and a one-line description. Order is the order they run in.
PRESETS = {
    "quick": {"workloads": ["overhead/version", "overhead/print"], "apis": ["openai-completions"], "rounds": 12, "adaptive": True, "calibration_rounds": 4, "evals": [],
              "about": "start-up and one turn on one wire API; stops each cell as soon as it is clear"},
    "standard": {"workloads": ["overhead/version", "overhead/print", "overhead/print-tools", "overhead/rpc", "streaming/print-prose", "longsession/resume-n", "reliability/faults"],
                 "apis": ["openai-completions", "anthropic-messages"], "rounds": 12, "adaptive": True, "calibration_rounds": 8, "evals": [],
                 "about": "start-up, turns, tool calls, RPC, streaming, a long session, fault recovery, on two wire APIs"},
    "full": {"workloads": ["overhead", "streaming", "longsession", "reliability", "soak", "devloop"], "apis": ["openai-completions", "anthropic-messages", "openai-responses"], "rounds": 12,
             "adaptive": False, "calibration_rounds": 12, "evals": [],
             "about": "every wired family, three wire APIs, 12 rounds in every cell (what the Verified badge needs) and the soak; takes hours"},
}

# Words people use for a benchmark -> the families or workloads they mean.
ALIASES = {"long-session": ["longsession"], "memory": ["soak"], "startup": ["overhead/version", "overhead/print"], "faults": ["reliability"], "tui": ["streaming/tui-*"],
           "speed": ["overhead/version", "overhead/print", "longsession/resume-n"], "install": ["devloop"], "tools": ["overhead/print-tools"], "large-write": ["overhead/print-write"]}

# Opt-in only (`--evals faithfulness`): no preset or track runs them, and no page ranks by them.
EVALS = {"faithfulness": "the Pi Faithfulness Score: deterministic black-box probes against Pi (docs/FAITHFULNESS.md)",
         "faithfulness-smoke": "a handful of those probes: wire format of one turn on one API"}
SMOKE_PROBES = ["F2.hello.completions.*"]   # glob over probe ids

# Typical seconds for one sample of a workload on an ordinary laptop (one arm, one round, one API). The probe scales it to this machine; history replaces it.
COST_S = {"overhead/print-write": 30.0, "overhead/print-ext5": 1.4, "overhead/rpc-ext5": 4.6, "overhead/print-ext50": 2.5, "overhead/print-ext100": 4.0, "overhead/rpc-ext50": 7.0, "overhead/rpc-ext100": 10.0, "longsession/resume-4m2": 120.0, "overhead/version": 0.2, "overhead/print": 1.2, "overhead/print-tools": 1.8, "overhead/pty": 4.0, "overhead/rpc": 4.0, "overhead/print-ext10": 1.6, "overhead/rpc-ext10": 5.0,
          "streaming/*": 3.0, "longsession/resume-n": 6.0, "longsession/resume-n-varied": 6.0, "longsession/resume-n10": 25.0, "longsession/resume-n10-varied": 25.0, "longsession/grow-n": 40.0, "longsession/grow-n10": 240.0,
          "durable/compat-50": 3.0, "durable/compat-250": 4.0, "durable/compat-1000": 6.0, "durable/compat-3500": 10.0, "durable/compat-10000": 15.0, "durable/mixed-1000": 5.0, "durable/mixed-varied-1000": 5.0,
          "durable/mixed-3500": 7.0, "durable/mixed-varied-3500": 7.0, "durable/window-*": 7.0, "durable/mixed-10000": 10.0, "durable/mixed-varied-10000": 10.0, "durable/cold-every-turn-*": 30.0, "durable/many-conv-*": 20.0,
          "durable/grow-1000": 40.0, "durable/grow-3500": 150.0, "durable/floor-host": 1.0, "durable/floor-sql": 3.0, "durable/compaction-fail": 8.0, "durable/*": 6.0,
          "devloop/install": 20.0, "devloop/build": 120.0, "devloop/first-run": 3.0}
SPECIAL_S = {"soak/realistic": 780.0, "soak/stress": 780.0, "reliability/faults": 90.0, "durable/crash-50": 240.0, "durable/crash-1000": 300.0, "durable/crash-3500": 120.0, "durable/crash-stream": 200.0}   # total seconds for the whole workload, any number of arms (they run together or briefly)

# A workload's state; anything not listed here that the registry holds is `wired`.
SWEEP_WHY = "arms that load Pi extension sources by path; the rest show as cannot run"
SCALE_IDS = ("scale/agents-limit", "scale/print-limit", "scale/agents-ext10", "scale/print-ext10")   # the four search workloads (buffon/workloads/scale.py)
SCALE_WHY = "how many agents one container holds, found by a search (double N until one fails, then bisect to the exact number) in a container with a memory limit, a cpuset and a pids limit (docs/design/SCALE.md); needs --isolation container; `agents` needs a Pi-dialect RPC mode, `print` a print mode"
SCALE_EXT_WHY = SCALE_WHY + "; with ten extensions: only arms that load Pi extensions take part, the rest show as cannot run"
DURABLE_WHY = "only the durable arms (pi-durable, pig-durable) take part: each runs through its adapter (docs/DURABLE-ADAPTERS.md); a workload on a capability an arm lacks shows as cannot run with the adapter's reason"
PARTLY = {"overhead/print-write": "arms whose tool set has no write tool (the call is built from each arm's own tool schema) show as cannot run", **{w: SCALE_EXT_WHY if w.endswith("-ext10") else SCALE_WHY for w in SCALE_IDS}, "overhead/print-ext5": SWEEP_WHY, "overhead/rpc-ext5": SWEEP_WHY, "overhead/print-ext50": SWEEP_WHY, "overhead/print-ext100": SWEEP_WHY, "overhead/rpc-ext50": SWEEP_WHY, "overhead/rpc-ext100": SWEEP_WHY, "longsession/resume-4m2": "arms that read Pi session files; a stop at this size is a result", "overhead/print-ext10": "needs the extension-realization arms (pig-ts-*, pig-go-*)", "overhead/rpc-ext10": "needs the extension-realization arms (pig-ts-*, pig-go-*)",
          "devloop/build": "only source-built arms have a build step", "overhead/pty": "arms without an interactive mode show as cannot run",
          "streaming/tui-prose": "arms without an interactive mode show as cannot run", "streaming/tui-code": "arms without an interactive mode show as cannot run",
          "streaming/tui-tables": "arms without an interactive mode show as cannot run", "streaming/tui-lists": "arms without an interactive mode show as cannot run"}
NOT_RUN = [           ("real-extensions", "a pinned set of real Pi extensions, beside the trivial ones", "candidates are pinned in fixtures/external (pi-fff 0.11.0, pi-subagents 0.77.0, used by the compatibility rows in docs/COMPAT.md); the workload that loads them is not built"),
           ("agent-benchmarks", "task pass rates with real models", "bookkeeping only (`buffon agentbench`); no run")]



def family_of(workload_id):
    return workload_id.split("/", 1)[0]


def state_of(workload_id):
    if workload_id.startswith("durable/"):
        return "partly wired", DURABLE_WHY
    if workload_id in PARTLY:
        return "partly wired", PARTLY[workload_id]
    return "wired", ""


def cost_of(workload_id):
    """Typical seconds for one sample (None for a special workload, which has its own total). A scale search is not here: what it costs depends on where the harness stops (`scale_search`)."""
    for pattern, seconds in COST_S.items():
        if fnmatch.fnmatchcase(workload_id, pattern):
            return seconds
    return 2.0


# The scale search is a MODEL here, not a measurement of the search. It is built from the real timings of the old doubling-only runs of envelope A (the benchmark-host run up-3c5957b1c3: 4 GiB, 8 CPUs, 6 harnesses with
# an RPC mode and 9 with a print mode). Per doubling rung: (harnesses that fit it, their mean wall seconds, harnesses that stopped at it, their mean seconds to the stop). A rung that fits takes its wall
# time; a rung that does not fit ends at its first OOM kill, or after `scale_stall_s` of stall, so it takes the time to fill the container (twice the wall time of the last rung that fit, plus the 10 s stall
# where the harness thrashed without a kill).
SCALE_REF_ENVELOPE = (4, 8)    # memory GiB, CPUs
SCALE_CAP = 8192               # swarm_max_agents's default (buffon/workloads/scale.py)
SCALE_LADDER = {
    "agents": (6, {1: (6, 1.0, 0, 0.0), 2: (6, 1.0, 0, 0.0), 4: (6, 1.1, 0, 0.0), 8: (6, 1.3, 0, 0.0), 16: (6, 1.8, 0, 0.0), 32: (6, 2.8, 0, 0.0), 64: (4, 2.2, 2, 9.7), 128: (4, 3.7, 0, 0.0),
                  256: (2, 5.1, 2, 9.1), 512: (1, 8.5, 1, 11.6), 1024: (0, 0.0, 1, 16.9)}),
    "print": (9, {1: (9, 1.1, 0, 0.0), 2: (9, 1.1, 0, 0.0), 4: (9, 1.3, 0, 0.0), 8: (9, 1.7, 0, 0.0), 16: (9, 2.9, 0, 0.0), 32: (7, 2.6, 2, 18.5), 64: (4, 1.4, 3, 9.5), 128: (4, 2.3, 0, 0.0),
                  256: (4, 4.0, 0, 0.0), 512: (4, 8.9, 0, 0.0), 1024: (2, 9.1, 2, 28.4)}),
}


def scale_kind(workload_id):
    """`agents` or `print` for `scale/agents-limit`, `scale/print-ext10` and the like."""
    return workload_id.split("/", 1)[1].split("-", 1)[0]


def scale_has_extensions(workload_id):
    return workload_id.endswith("-ext10")


def scale_search(kind, memory_gib=SCALE_REF_ENVELOPE[0], cpus=SCALE_REF_ENVELOPE[1], resolution=1, cap=SCALE_CAP):
    """Model of the expected seconds of one search sample of one harness that has the mode of `kind`, in a box of `memory_gib` and `cpus`, averaged over the reference harnesses.

    The doubling part is the sum of the rung timings in SCALE_LADDER, each weighted by the share of harnesses that fit the rung (they pay its wall time) or stop at it (they pay the time to the stop).
    The bisection part: a harness that stops at rung F, having passed F/2, pays about ceil(log2((F - F/2) / resolution)) more probes. Each probe is costed as the mean of a pass at F/2 and a stop at F
    (about half of the probes between them pass), because the table has no timing for the sizes between. A harness that fits every rung pays no bisection. A box with twice the memory holds twice the
    agents, so a table row of n agents stands for n * memory / 4 GiB agents there (rows above `cap` are not run); a row's time follows the agents per CPU. The harnesses that fit the top row are
    assumed to stop one doubling above it, which costs the top row's stop time, or twice its wall time where none stopped there; the table has nothing above 1024 agents in 4 GiB. Only the reference
    envelope is measured; the rest is that scaling."""
    harnesses, rows = SCALE_LADDER[kind]
    ref_mem, ref_cpus = SCALE_REF_ENVELOPE
    scale = memory_gib / ref_mem
    slower = scale / (max(1, cpus) / ref_cpus)
    seconds = 0.0
    top = max(rows)
    for row, (fit, wall, stop, stop_wall) in sorted(rows.items()):
        real = max(1, round(row * scale))
        if real > cap:
            break
        seconds += fit * wall + stop * stop_wall
        if stop and real > 1:
            gap = real - real // 2
            probes = math.ceil(math.log2(gap / max(1, resolution))) if gap > max(1, resolution) else 0
            below = rows.get(row // 2)
            pass_wall = below[1] if below and below[1] else wall
            seconds += stop * probes * (pass_wall + stop_wall) / 2
        if row == top and fit and round(row * 2 * scale) <= cap:
            seconds += fit * (stop_wall if stop else 2 * wall)
    return seconds * slower / harnesses


def scale_harness_count(workload_id, harnesses, arms):
    """How many of `harnesses` take part in a scale workload: the harnesses that have its mode (`agents`: an RPC mode, `print`: a print mode) and, for the ten-extension variants, load Pi extensions
    (manifest `pi_extensions` native or sidecar). A name the manifests do not know counts."""
    mode = "rpc" if scale_kind(workload_id) == "agents" else "print"
    ext = scale_has_extensions(workload_id)
    return sum(1 for h in harnesses if h not in arms or (arms[h].supports_mode(mode) and (not ext or arms[h].pi_extensions in ("native", "sidecar"))))


def special_total(workload_id):
    return SPECIAL_S.get(workload_id)
