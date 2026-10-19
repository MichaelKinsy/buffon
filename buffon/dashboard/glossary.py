# SPDX-License-Identifier: Apache-2.0
"""The benchmark and statistics words the dashboard uses, in one or two plain sentences, with a formula where there is one.

The site assumes a reader who programs: CPU, API, RPC, JSON, npm and the like are not explained. TERMS are the method's words. ACRONYMS are the
abbreviations from benchmarking and from the Linux measurement stack: the site wraps each one, wherever it appears in running text, in a tooltip
with its expansion (app.js `explain`). COMMON are abbreviations the site uses without a tooltip. tests/test_dashboard.py fails when a page shows an
abbreviation that is in neither list."""
from . import formulas as fx

# (slug, term, definition, KaTeX source or None)
TERMS = [
    ("harness", "harness", "A harness is the program around a model: the command line or terminal view, the tools, the session files and the extensions. Here every harness talks to the same scripted mock model, so a number describes the harness alone.", None),
    ("mock-model", "mock model", "The mock model is a scripted program on the same machine. It gives every harness the same answer, at once, with no network. It removes the model from the measurement. It also removes real network and model time.", None),
    ("workload", "workload", "A workload is one scripted task that a harness does. For example, overhead/print starts the harness, sends one prompt, prints the answer and stops.", None),
    ("sample", "sample", "A sample is one measured run of one harness in one workload. Buffon writes it to raw.json.", None),
    ("round", "round", "A round is one sample of every harness in a workload. The order moves by one place each round, so no harness always goes first. A slow moment on the host affects all harnesses in that round.", None),
    ("warm-up", "warm-up round", "A warm-up round is one of the first rounds of a workload. Buffon measures it and then drops it, so caches and first-start work do not count.", None),
    ("median", "median", "The median is the middle value of the measured rounds. A cell of the grid shows the median of one harness. A few slow rounds do not move it much.", fx.MEDIAN),
    ("iqr", "middle half", "The middle half is the range from the 25th to the 75th percentile of the rounds. A tooltip in the grid shows it.", None),
    ("paired-ratio", "ratio", "A ratio is the median of one harness divided by the median of the baseline (Pi, unless you pick another), over the rounds both ran. Below 1.00 the harness uses less than the baseline. Above 1.00 it uses more.", fx.RATIO),
    ("ci", "95% interval", "The 95% interval is the middle 95% of the ratios that Buffon finds by resampling (the bootstrap). It takes new random samples of the paired rounds, with replacement, keeps each pair together and finds the ratio each time. For the median of one harness it resamples that harness's rounds. If you repeat the measurement, an interval made this way holds the true value about 95 times in 100.", fx.INTERVAL),
    ("aa-floor", "A/A noise floor", "Each harness also runs against an identical copy of itself (A against A). The gap between the two copies is the noise floor. A difference smaller than the floor can be noise.", fx.FLOOR),
    ("mde", "MDE", "MDE means minimum detectable effect: the smallest change that this run can find 80% of the time at the 5% level, from the spread of the A/A pair alone. A smaller difference is below what the run can show.", fx.MDE),
    ("paired-test", "paired test", "The paired test is a sign-flip test on the log ratio of each round: how often a random change of the signs gives a sum as large as the real sum. Holm p is its p-value, adjusted because several harnesses are compared in the same measurement (Holm's method).", None),
    ("equivalence-margin", "equivalence margin", "The equivalence margin is a distance from 1.00 that Buffon sets for a metric (workloads/margins.toml). A ratio is within ±5% when the whole 90% interval of the ratio lies between 0.95 and 1.05. When it does not, the page says \"not shown to be within ±5%\". That means the run cannot show the two are close. It does not mean they differ.", None),
    ("different-work", "different work", "A harness did different work in a workload when its manifest says so (a divergence entry, with a reason and a source). The site shows its own median there and does not compare it with the baseline: there is no ratio, interval or p-value.", None),
    ("provisional", "PROVISIONAL", "PROVISIONAL means the run was not on quiet, dedicated hardware. The numbers are real, but they are not headline numbers.", None),
    ("notes", "run notes", "Run notes list the conditions of a run: calibration, A/A noise, outliers, throttling and host load. Each check shows its value and the usual range (docs/HEALTH.md). A note means a value is outside the usual range. It does not grade the run or hide a number.", None),
    ("calibration", "calibration", "Before Buffon measures, the reference harness runs against itself several times. If those runs differ too much (CV above the limit), the host is too noisy.", None),
    ("class-a", "class A host", "A class A host is a dedicated machine. No other program uses its benchmark CPUs.", None),
    ("class-b", "class B host", "A class B host is a shared machine. Its runs are PROVISIONAL.", None),
    ("rerun", "rerun", "The rerun is one command that measures a number again, with the same workload, API, harnesses, rounds and seed, and then compares the two results.", None),
    ("swarm", "swarm", "A swarm is N agents of one harness that work at the same time inside one container. The Scale page asks how many agents fit: N doubles, 1, 2, 4, 8 and so on, until the agents stop finishing, and then the search narrows to the exact number.", None),
    ("envelope", "swarm envelope", "The swarm envelope is the container that all agents of a swarm share: one memory limit (memory and swap are the same number), one set of CPU cores and one limit on the number of processes (64 for each agent and 1,024 more). The network is closed except for the link to the scripted model. Every probe runs in the same envelope.", None),
    ("rung", "probe", "A probe is one number of agents N that a harness is asked to run at once, for example 32 agents. A probe is complete when every agent became ready and finished its work. The limit is the largest N whose probe completed. An earlier run climbed a ladder of probes, 1, 2, 4 and so on, one sample for each step, and called each of them a rung: it knows the limit only to between its last complete rung and the one before the first that stopped.", None),
    ("agent-turn", "agent-turn", "An agent-turn is one turn of one agent: a prompt, the tool calls the scripted model asks for, and the final answer. A swarm of N agents that runs K turns completes N times K agent-turns.", None),
    ("oom-kill", "OOM kill", "An OOM kill is the kernel's stop of a process because the memory limit of its container is used up. The count comes from the oom_kill line of memory.events. The first OOM kill ends the probe: it did not fit in the memory limit.", None),
    ("stall", "stall", "A stall is a probe that sat at its memory limit while no agent made progress, for 10 seconds (scale_stall_s), and the kernel killed nothing. The kernel was busy freeing memory. The probe ends then and reads, like an OOM kill, \"did not fit\".", None),
    ("fit", "fit", "N agents fit in a memory limit when a probe of N agents is complete: every agent became ready and finished its work, and the kernel killed none. The limit of a harness is the largest N that fits. Buffon finds it exactly: it doubles N until a probe fails, then halves the gap between the last probe that completed and the first that failed until they are one agent apart. Each round does this search again, and the page shows the median of the rounds with their range. \"At least 8192 (cap)\" means that the probe at the cap, the most agents Buffon tries, completed.", None),
    ("makespan", "makespan", "The makespan is the time from the start of the first agent to the exit of the last agent of a print-mode swarm.", None),
    ("turns-per-second", "turns per second", "Turns per second is the number of agent-turns that the swarm completed, divided by the seconds of the turn phase. CPU per agent-turn uses the same turn phase, so the two read together. A print-mode agent does one task: its numbers are tasks per second and CPU per task. The turns run in lockstep: every agent gets its prompt, and the next turn starts when all agents are done.", None),
    ("p95", "95th percentile (p95)", "The 95th percentile is the value that 95 of 100 measurements do not exceed. Here it is taken over the turns of all agents in a probe. The median is the 50th percentile (p50).", None),
    ("mock-saturated", "saturated scripted model", "A sample is flagged when the CPUs of the scripted model were fully used. Then the model may have slowed the agents, and the numbers of that sample show the model as much as the harness.", None),
    ("cpuset", "cpuset", "A cpuset is the list of CPU cores a container may use. The swarm envelope has one, and its agents never run on other cores.", None),
    ("pids-limit", "pids limit", "The pids limit is the most processes and threads a container may have. Buffon sets it high enough that it is not the first limit that a swarm meets.", None),
    ("lockstep", "lockstep", "Lockstep means every agent gets its next prompt at the same time, and the swarm waits for all of them to finish a turn before it starts the next one.", None),
    ("demo", "DEMO", "DEMO numbers are made-up numbers from tests/report_demo.py. They show what the site looks like. No harness made them.", None),
]

# (abbreviation as printed, expansion, one sentence, glossary slug it shares or None)
ACRONYMS = [
    ("RSS", "resident set size", "The memory pages that a process holds in RAM now. Shared pages count in full.", None),
    ("PSS", "proportional set size", "Like RSS, but processes that share a page also share its size. Linux only.", None),
    ("A/A", "A against A", "A comparison of a harness with an identical copy of itself. It measures noise.", "aa-floor"),
    ("MDE", "minimum detectable effect", "The smallest change that a measurement can find with confidence.", "mde"),
    ("IQR", "interquartile range", "The middle half of the rounds, from the 25th to the 75th percentile.", "iqr"),
    ("CV", "coefficient of variation", "The standard deviation divided by the mean: the spread of repeated measurements as a fraction of their size.", None),
    ("cgroup", "control group", "A Linux kernel feature that limits the memory and CPU of a group of processes and counts their use.", None),
    ("MAD", "median absolute deviation", "A measure of spread that outliers do not change much. A round more than 5 × 1.4826 × MAD from the median is an outlier. Buffon counts outliers but never removes them.", None),
    ("CFS", "Completely Fair Scheduler", "The CPU scheduler of Linux. CFS throttling pauses a group of processes that used all of its CPU quota.", None),
    ("OOM", "out of memory", "An OOM kill happens when the kernel stops a process because no memory is left.", None),
    ("PSI", "pressure stall information", "A Linux measure of how long tasks wait for a resource, such as the CPU.", None),
    ("SMT", "simultaneous multithreading", "Two logical CPUs share one physical core (hyper-threading), so load on one slows the other.", None),
    ("NUMA", "non-uniform memory access", "CPUs and memory are in groups called nodes. Memory on a different node is slower to reach.", None),
    ("IRQ", "interrupt request", "A hardware signal that the kernel handles on a CPU, which takes time from the work on that CPU.", None),
    ("THP", "transparent huge pages", "A Linux memory setting that can change how much memory a process seems to use.", None),
    ("QoS", "quality of service", "The Kubernetes class of a pod. Guaranteed means its resources are fixed and no other pod shares them.", None),
    ("ASLR", "address space layout randomisation", "A kernel setting that changes memory addresses from one run to the next.", None),
]
# the faithfulness dimensions (docs/WHAT-WE-MEASURE.md), named in the benchmark texts; the opt-in faithfulness eval scores each 0 to 100
ACRONYMS += [(f, f"faithfulness dimension {f[1]}", f"One of the eight groups of faithfulness probes (opt-in, `--evals faithfulness`): {what}.", None)
             for f, what in (("F1", "command-line text and flags"), ("F2", "wire requests"), ("F3", "tool behaviour"), ("F4", "session file"), ("F5", "config compatibility"),
                             ("F6", "output modes: print, JSON, RPC"), ("F7", "extension compatibility"), ("F8", "terminal view"))]

# Abbreviations a programmer knows; the site uses them without a tooltip.
COMMON = ("CPU", "API", "RPC", "TUI", "PTY", "CLI", "JSON", "JSONL", "CSV", "HTTP", "SSE", "SHA", "SHA-256", "CI", "MiB", "GiB", "KB", "MB", "GB", "ms", "OS", "VM", "IO",
          "RAM", "URL", "HTML", "LLM", "AOT", "JIT", "MCP", "ACP", "SDK", "UI", "HOME", "SIGTERM", "TOML", "MIT", "AI", "OpenAI", "GPT", "AWS", "BYOK", "PID", "UTC", "GO", "TS", "README")

SLUGS = {slug for slug, *_ in TERMS}


def acronym_slug(abbr):
    return "abbr-" + abbr.lower().replace("/", "").replace("-", "")


# The entries that a page links (a term link or an abbreviation tooltip, somewhere among the routes of the site, mock-saturated only when a scale probe was saturated): the Glossary page shows these.
# The others are in a collapsed section that the search still finds. tests/test_dashboard_consistency.py fails when a page links an entry that is not here.
SHOWN = {"aa-floor", "agent-turn", "ci", "cpuset", "different-work", "envelope", "equivalence-margin", "iqr", "lockstep", "mde", "mock-saturated", "p95", "paired-test", "pids-limit", "rerun", "round", "rung", "swarm", "warm-up"} | \
    {acronym_slug(a) for a in ("A/A", "CFS", "CV", "MAD", "MDE", "OOM", "PSS", "RSS")}


