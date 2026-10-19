# SPDX-License-Identifier: Apache-2.0
"""What each benchmark is, in the reader's terms: the Pi use case it stands for, what Buffon runs, where the clock starts and stops, and why it might matter.

The family texts (measures, why a user cares, scenario, limits) are read from docs/WHAT-WE-MEASURE.md, so the site says what the method says. The workload
figures are drawn from the workload modules' own descriptions (buffon/workloads/*.py)."""
import os
import re
from fnmatch import fnmatchcase

DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "WHAT-WE-MEASURE.md")
SECTIONS = {"core": "Core overhead", "ext10": "Extensions (ext10)", "streaming": "Streaming render", "long-session": "Long session: grow and resume",
            "reliability": "Reliability and faults", "devloop": "Devloop", "large-write": "Large write", "scale": "Scale", "search": "Search"}
FIELDS = (("measures", "Measures"), ("why", "Why a user cares"), ("scenario", "Scenario"), ("limits", "Limits"), ("state", "State"))
NAMES = {"core": "Core", "ext10": "Extensions", "streaming": "Streaming", "long-session": "Long session", "reliability": "Reliability", "devloop": "Dev loop",
         "large-write": "Large write", "scale": "Scale", "search": "Search", "other": "Other cells"}
SHORT_NAMES = {"core": "Core", "ext10": "Extensions", "streaming": "Stream", "long-session": "Sessions", "reliability": "Faults", "devloop": "Dev loop"}
USE = {"core": "Pi in a script, as an editor back end, and in the terminal", "ext10": "Pi with ten extensions", "streaming": "a long answer on the screen", "long-session": "long sessions and sessions that you resume",
       "reliability": "errors from the provider, lost connections and stopped programs", "devloop": "install and first run", "large-write": "a write of one very large file", "scale": "many sessions on one machine",
       "search": "search in large folders", "other": "measured, but not graded"}

# (scenario glob, title, Pi use case, terminal lines, timeline marks). A mark is (fraction of the line, label, kind): kind start, work, stop, fault.
WORKLOADS = [
    ("overhead/version", "Start-up", "A script asks Pi for its version, many times.", ["$ pi --version", "1.1.0"], [(0, "spawn", "start"), (1, "prints its version, exits", "stop")]),
    ("overhead/print-tools", "One prompt with tools", "A script gives Pi one prompt. Pi makes eight tool calls and then gives the answer.",
     ["$ pi -p \"tidy the README\"", "  ● read  ● edit  ● bash  × 8 rounds", "  done."], [(0, "spawn", "start"), (0.2, "first request", "work"), (0.55, "8 tool calls", "work"), (0.85, "final reply", "work"), (1, "exit", "stop")]),
    ("overhead/print-write", "Large file write", "A script asks Pi to write one very large file in a single tool call.",
     ["$ pi -p \"write the file\"", "  ● write  200 KB  (streamed in small chunks)", "  done."], [(0, "spawn", "start"), (0.2, "request", "work"), (0.4, "tool call streams 200 KB", "work"), (0.75, "result", "work"), (1, "exit", "stop")]),
    *[(f"overhead/print-ext{n}", f"One prompt, {w} extensions", "Each start of a Pi with extensions must load the extensions first.",
       ["$ pi -p \"hello\"", f"  {n} extensions loaded", "  hi."], [(0, "spawn", "start"), (0.45, f"load ×{n}", "work"), (0.7, "request, reply", "work"), (1, "exit", "stop")]) for n, w in ((5, "five"), (50, "fifty"), (100, "a hundred"))],
    *[(f"overhead/rpc-ext{n}", f"Editor session (RPC), {w} extensions", "An editor plugin uses a Pi with extensions through RPC.",
       ["$ pi --mode rpc", f"  {n} extensions loaded", "← {\"type\":\"agent_end\"}"], [(0, "spawn", "start"), (0.4, "ready", "work"), (1, "turns done", "stop")]) for n, w in ((5, "five"), (50, "fifty"), (100, "a hundred"))],
    ("overhead/print*-ext10", "One prompt, ten extensions", "Each start of a Pi with extensions must load the extensions first.",
     ["$ pi -p \"hello\"", "  10 extensions loaded", "  hi."], [(0, "spawn", "start"), (0.45, "load ×10", "work"), (0.7, "request, reply", "work"), (1, "exit", "stop")]),
    ("overhead/rpc-ext10", "Editor session (RPC), ten extensions", "An editor plugin uses a Pi with extensions through RPC.",
     ["$ pi --mode rpc", "  10 extensions loaded", "← {\"type\":\"agent_end\"}"], [(0, "spawn", "start"), (0.4, "ready", "work"), (1, "turns done", "stop")]),
    ("overhead/print", "One prompt", "A script, a CI job or a git hook calls Pi one time and Pi stops.", ["$ pi -p \"say hi\"", "  hi."],
     [(0, "spawn", "start"), (0.3, "first request", "work"), (0.65, "reply streams in", "work"), (1, "exit", "stop")]),
    ("overhead/rpc", "Editor session (RPC)", "An editor or tool keeps Pi running and sends it turns.",
     ["$ pi --mode rpc", "→ {\"type\":\"prompt\", …}", "← {\"type\":\"agent_end\"}"], [(0, "spawn", "start"), (0.3, "ready", "work"), (0.5, "prompt", "work"), (0.75, "reply", "work"), (1, "turns done", "stop")]),
    ("overhead/pty", "Terminal session", "You open Pi in a terminal and type.",
     ["┌ pi ─────────────────────────────┐", "│ > _                             │", "└ ~/project (main) ───────────────┘"],
     [(0, "spawn", "start"), (0.35, "first frame", "work"), (0.7, "settled", "work"), (1, "prompt sent", "stop")]),
    ("overhead/long-session", "Long editor session (RPC)", "A session that continues for many turns.", ["$ pi --mode rpc", "→ turn 1 … turn N"],
     [(0, "spawn", "start"), (1, "turn N", "stop")]),
    ("streaming/tui-*", "Stream into the terminal", "A user sees a long answer move up the terminal screen for most of a session.",
     ["▌ Here is the plan:", "▌ 1. Split parser.go into …", "▌ ```go  func parse(…)"], [(0, "first byte", "start"), (0.2, "first paint", "work"), (1, "final frame", "stop")]),
    ("streaming/print-*", "Stream a long answer", "Pi prints a long answer with pi -p. A script sees this output.",
     ["$ pi -p \"explain the parser\"", "Here is the plan: …", "(N, then 10N characters)"], [(0, "spawn", "start"), (0.25, "first byte", "work"), (1, "exit", "stop")]),
    ("longsession/grow-*", "A growing session", "Real work happens in long sessions. If the cost grows with the history, the late turns are slow.",
     ["turn    1  ▏", "turn  500  ▎▎▎▎  (compacted)", "turn 1000  ▎▎▎▎▎▎"], [(0, "turn 1", "start"), (0.5, "compaction", "work"), (1, "turn N", "stop")]),
    ("longsession/resume-*", "Resume a long session", "A user continues the session of yesterday, which has 1,000 turns.",
     ["$ pi --mode rpc   (a saved session)", "  loaded 1,000 turns", "→ one more prompt"], [(0, "spawn", "start"), (0.6, "ready", "work"), (1, "first turn", "stop")]),
    ("devloop/install", "Install", "A user puts Pi on a clean machine from a checked cache.", ["$ install from cache", "  unpack, npm ci"], [(0, "start", "start"), (1, "installed", "stop")]),
    ("devloop/build", "Build from source", "CI builds a harness from source again.", ["$ go build ./…", "  pinned toolchain"], [(0, "start", "start"), (1, "built", "stop")]),
    ("devloop/first-run", "First run", "A new user does the first print run in the first minute, on a new home directory.", ["$ pi -p \"hello\"   (fresh HOME)", "  first-start work, then hi."],
     [(0, "spawn", "start"), (1, "exit", "stop")]),
    ("reliability/*", "When things go wrong", "Providers fail and programs stop. If Pi hangs or a session breaks, the user loses work.",
     ["← HTTP 429  retry-after: 1", "✕ connection dropped mid-stream", "↻ resumed: the session parses"], [(0, "request", "start"), (0.45, "fault", "fault"), (1, "recovered?", "stop")]),
]


def family_texts(path=DOC):
    """{family id: {measures, why, scenario, limits, state}} from docs/WHAT-WE-MEASURE.md; {} when the document is not on disk."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}
    out = {}
    for fam, title in SECTIONS.items():
        m = re.search(r"^## " + re.escape(title) + r"\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if not m:
            continue
        body = m.group(1)
        entry = {}
        for key, label in FIELDS:
            f = re.search(r"\*\*" + re.escape(label) + r"\.\*\*\s*(.*?)(?=\n\n|\Z)", body, re.S)
            if f:
                entry[key] = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", " ".join(f.group(1).split()))
        out[fam] = entry
    return out


def workload_of(scenario):
    """(title, use, lines, marks) for a scenario, or a plain fallback naming it."""
    for pattern, title, use, lines, marks in WORKLOADS:
        if fnmatchcase(scenario, pattern):
            return {"title": title, "use": use, "lines": lines, "marks": marks}
    return {"title": scenario, "use": "", "lines": [f"$ {scenario}"], "marks": [(0, "start", "start"), (1, "stop", "stop")]}


# What each metric is: (one sentence, KaTeX of the number one sample gives or None). The names are Buffon's own (docs/RAW-FORMAT.md); the sentences follow the code
# in buffon/workloads/overhead.py and the meters in buffon/runner/cgroup.py. A metric not named here gets a sentence made from its name and unit (build.py metric_about).
# In a formula, p is a process of the harness's process tree and t is a clock reading.
METRICS = {
    "cpu_ms": ("The CPU time that the harness and every process it starts use, from start to exit.", r"c = \sum_{p}\bigl(t^{\mathrm{user}}_{p} + t^{\mathrm{sys}}_{p}\bigr)"),
    "wall_ms": ("The time from the start of the process to its exit, on a monotonic clock.", r"w = t_{\mathrm{exit}} - t_{\mathrm{start}}"),
    "instructions": ("The CPU instructions that the harness and every process it starts retire.", r"I = \sum_{p} I_{p}"),
    "cycles": ("The CPU cycles that the harness and every process it starts use.", r"Y = \sum_{p} Y_{p}"),
    "peak_rss_mib": ("The most memory that the harness and its processes hold in RAM at one moment (RSS), read about every 25 ms.", r"M = \max_{t}\ \sum_{p}\mathrm{RSS}_{p}(t)"),
    "peak_mem_mib": ("The peak memory that the kernel counts for the whole control group of the harness.", r"M = \texttt{memory.peak}"),
    "ready_ms": ("The time from the start of the process until the harness is ready to take a prompt.", r"r = t_{\mathrm{ready}} - t_{\mathrm{start}}"),
    "ready_cpu_ms": ("The CPU time that the harness uses from the start of the process until it is ready.", r"c_{\mathrm{ready}} = \mathrm{CPU}(t_{\mathrm{ready}})"),
    "ready_rss_mib": ("The memory (RSS) that the harness holds when it is ready.", r"M_{\mathrm{ready}} = \max_{t \le t_{\mathrm{ready}}}\ \sum_{p}\mathrm{RSS}_{p}(t)"),
    "ready_pss_mib": ("The memory that the harness holds when it is ready, with pages that processes share counted once (PSS).", r"M_{\mathrm{ready}} = \sum_{p}\mathrm{PSS}_{p}(t_{\mathrm{ready}})"),
    "first_request_ms": ("The time from the start of the process until the first request reaches the scripted model.", r"f = t_{\mathrm{request}_1} - t_{\mathrm{start}}"),
    "first_request_cpu_ms": ("The CPU time that the harness uses from the start of the process until the first request reaches the scripted model.", r"c_{\mathrm{request}_1} = \mathrm{CPU}(t_{\mathrm{request}_1})"),
    "turn_cpu_ms": ("The CPU time of one turn: the CPU that the harness uses between the end of one turn and the end of the next, as a median over the turns.",
                    r"c_k = \mathrm{CPU}(t_k) - \mathrm{CPU}(t_{k-1}),\quad \operatorname{median}_k(c_k)"),
    "turn_cpu_mean_ms": ("The CPU time of one turn, as the mean over the turns.", r"\bar{c} = \frac{1}{K}\sum_{k=1}^{K}\bigl(\mathrm{CPU}(t_k) - \mathrm{CPU}(t_{k-1})\bigr)"),
    "turn_wall_ms": ("The time of one turn: from the prompt to the end of the turn, as a median over the turns.", r"w_k = t_{\mathrm{end},k} - t_{\mathrm{prompt},k}"),
    "turn_harness_added_ms": ("The time that the harness adds to a turn: from the end of the last reply of the scripted model to the end of the turn.", r"a_k = t_{\mathrm{end},k} - t_{\mathrm{reply\ end},k}"),
    "turn_gap_ms": ("The time that the harness takes between the end of a reply of the scripted model and its next request (its own work between tool calls).", r"g = t_{\mathrm{request}_{j+1}} - t_{\mathrm{reply\ end},j}"),
    "turn_turn_gap_ms": ("The time that the harness takes between the end of a reply of the scripted model and its next request, as a median over the turns.", r"g = t_{\mathrm{request}_{j+1}} - t_{\mathrm{reply\ end},j}"),
    "teardown_ms": ("The time from the end of the last reply, or from the close command, until the process exits.", r"d = t_{\mathrm{exit}} - t_{\mathrm{last\ reply}}"),
    "request_bytes": ("The sum of the sizes in bytes of the request bodies that the harness sends to the scripted model during the sample.", r"B = \sum_i \lvert \mathrm{request}_i \rvert"),
    "requests": ("The number of requests that the scripted model receives during the sample.", r"N = \lvert \{\mathrm{request}_i\} \rvert"),
    "request_bytes_per_turn": ("The request bytes divided by the turns of the workload.", r"B / n_{\mathrm{turns}}"),
    "side_requests": ("The requests beyond the ones that the workload scripts, such as a title request.", r"\max(0,\ N - N_{\mathrm{scripted}})"),
    "first_request_bytes": ("The size in bytes of the first request body that the harness sends to the scripted model. Runs made before the wire metrics recorded only this.", r"B_1 = \lvert \mathrm{request}_1 \rvert"),
}
