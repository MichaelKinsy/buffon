# SPDX-License-Identifier: Apache-2.0
"""What each benchmark is, in the reader's terms: the Pi use case it stands for, what Buffon runs, where the clock starts and stops, and why it might matter.

The family texts (measures, why a user cares, scenario, limits) are read from docs/WHAT-WE-MEASURE.md, so the site says what the method says. The workload
figures are drawn from the workload modules' own descriptions (buffon/workloads/*.py)."""
import os
import re
from fnmatch import fnmatchcase

DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "WHAT-WE-MEASURE.md")
SECTIONS = {"core": "Core overhead", "ext10": "Extensions (ext10)", "streaming": "Streaming render", "long-session": "Long session: grow and resume",
            "reliability": "Reliability and faults", "devloop": "Devloop", "large-write": "Large write", "scale": "Scale", "search": "Search", "durable": "Durable"}
FIELDS = (("measures", "Measures"), ("why", "Why a user cares"), ("scenario", "Scenario"), ("limits", "Limits"), ("state", "State"))
NAMES = {"core": "Core", "ext10": "Extensions", "streaming": "Streaming", "long-session": "Long session", "reliability": "Reliability", "devloop": "Dev loop",
         "large-write": "Large write", "scale": "Scale", "search": "Search", "durable": "Durable", "other": "Other cells"}
SHORT_NAMES = {"core": "Core", "ext10": "Extensions", "streaming": "Stream", "long-session": "Sessions", "reliability": "Faults", "devloop": "Dev loop"}
USE = {"core": "Pi in a script, as an editor back end, and in the terminal", "ext10": "Pi with ten extensions", "streaming": "a long answer on the screen", "long-session": "long sessions and sessions that you resume",
       "reliability": "errors from the provider, lost connections and stopped programs", "devloop": "install and first run", "large-write": "a write of one very large file", "scale": "many sessions on one machine",
       "search": "search in large folders", "durable": "conversations stored as commits, reopened after a restart", "other": "measured, but not graded"}

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


def durable_workload(scenario):
    """The title, the use and the terminal figure of a `durable/<name>` workload (docs/design/DURABLE.md 3.4), or None for a name the table does not know. The size or count in a name is part of the title."""
    name = scenario.split("/", 1)[1] if scenario.startswith("durable/") else ""

    def n(text):
        return f"{int(text):,}"
    marks = [(0, "open", "start"), (0.3, "first turn", "work"), (1, "turn 10", "stop")]
    rows = (
        (r"compat-(\d+)", lambda m: (f"Compat lane, {n(m[1])} turns", f"The shape of durable-bench: one conversation, compaction off, eight tool calls a turn, on a store of {n(m[1])} turns.", m[1])),
        (r"mixed-varied-(\d+)", lambda m: (f"Mixed lane, {n(m[1])} turns, varied words", f"The mixed lane with every word of the history replaced by another of the same length, on {n(m[1])} turns.", m[1])),
        (r"mixed-(\d+)", lambda m: (f"Mixed lane, {n(m[1])} turns", f"The default: a store of {n(m[1])} turns, compaction on, a 200,000-token window and turns of mixed shapes.", m[1])),
        (r"window-(\w+)-3500", lambda m: (f"Window {m[1]}, 3,500 turns", f"The mixed lane on 3,500 turns with a {m[1]}-token context window.", "3500")),
        (r"cold-every-turn-(\d+)", lambda m: (f"Cold every turn, {n(m[1])} turns", f"The store is reopened in a new process before every measured turn, on {n(m[1])} turns.", m[1])),
        (r"stream-(\d+)", lambda m: (f"Streamed answers, {n(m[1])} turns", "Each response streams in chunks, so partial answers are committed while it runs.", m[1])),
        (r"large-output-(\d+)", lambda m: (f"Large tool output, {n(m[1])} turns", "Each turn has one tool result of 32 KB.", m[1])),
        (r"docs-(\d+)", lambda m: (f"{n(m[1])} document edits", f"A warm turn after {n(m[1])} edits of an application document, one commit each.", "1000")),
        (r"tasks-(\d+)", lambda m: (f"{m[1]} child tasks per call", f"A tool creates {m[1]} child tasks and waits for them.", "1000")),
        (r"subagent", lambda m: ("A subagent", "A tool owns a child conversation and waits for its answer.", "1000")),
        (r"many-conv-(\d+)", lambda m: (f"{m[1]} conversation" + ("" if m[1] == "1" else "s"), f"{m[1]} conversation" + (" is" if m[1] == "1" else "s are") + " open in one process, one turn each in turn.", "1000")),
        (r"grow-(\d+)", lambda m: (f"Build a history of {n(m[1])} turns", "The history is built through the runtime's own loop, and the time of each turn is kept.", m[1])),
        (r"crash-(\w+)", lambda m: (f"Crash and resume, {m[1]} turns" if m[1].isdigit() else f"Crash and resume, {m[1]}", "The process is killed after a commit, a new one reopens the store and finishes the turn.", None)),
        (r"compaction-fail", lambda m: ("Failing compaction summaries", "Every summary request fails, on a 32,000-token window.", "3500")),
        (r"floor-host", lambda m: ("Floor: host and adapter", "The same adapter, protocol, scripted model and SQLite file with no durable runtime.", None)),
        (r"floor-sql", lambda m: ("Floor: recorded statements", "The statements of one measured turn replayed through the SQLite facade and driver, with no runtime.", None)),
    )
    for pattern, make in rows:
        m = re.fullmatch(pattern, name)
        if m:
            title, use, turns = make(m)
            history = f"  store of {n(turns)} turns" if turns else "  empty store"
            return {"title": title, "use": use, "lines": ["$ adapter: open the store", history, "→ ten measured turns"], "marks": marks}
    return None


def workload_of(scenario):
    """(title, use, lines, marks) for a scenario, or a plain fallback naming it."""
    durable = durable_workload(scenario)
    if durable:
        return durable
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
    # the durable family (docs/design/DURABLE.md 4.2): the runner's own clock around each request to the adapter, and the counts of a wrapper on the public SQLite facade
    "warm_turn_ms": ("The time of one warm turn: the median of turns 2 to 10 of a sample, from the submit to the conversation being idle, on the runner's clock.", r"w = \operatorname{median}_{k=2}^{10}\ (t_{\mathrm{idle},k} - t_{\mathrm{submit},k})"),
    "warm_net_ms": ("The warm turn less the warm turn of the floor (an adapter with no durable runtime) of the same arm in the same round. It is the part of a turn that the runtime adds. It is never applied to a cold start.", r"w_{\mathrm{net}} = w - w_{\mathrm{floor}}"),
    "cold_ms": ("The time from sending the open request to the answer of the first measured turn, in a new process. The time to start the process is not in it, and the store is read once before the clock starts.", r"c = t_{\mathrm{open}} + t_{\mathrm{turn}_1}"),
    "proc_start_ms": ("The time from starting the adapter to its ready line. It is shown beside the cold start and is not part of it.", r"s = t_{\mathrm{ready}} - t_{\mathrm{exec}}"),
    "open_ms": ("The time of the open request alone. A runtime that opens lazily moves the read of the history into the first turn.", None),
    "first_turn_ms": ("The time of the first measured turn after the open.", None),
    "ready_to_answer_ms": ("The process start and the cold start together: what a command-line user waits from the command to the first answer.", r"s + c"),
    "ttfr_ms": ("The time from sending a submit to the scripted model receiving its first request, as a median over the warm turns: what the runtime does before it asks the model.", None),
    "first_delta_ms": ("The time from the scripted model emitting its first streamed piece to a subscriber of the runtime seeing it committed.", None),
    "model_ms_per_turn": ("The time spent inside the scripted model in one turn. It is shown so that the work of the benchmark itself is visible, and it is not compared.", None),
    "warm_instructions": ("The CPU instructions of the process tree in one warm turn, from counter readings between turns.", None),
    "warm_cycles": ("The CPU cycles of the process tree in one warm turn.", None),
    "warm_cpu_ms": ("The CPU time of the process tree in one warm turn.", None),
    "sql_stmts_per_turn": ("The SQL statements the runtime ran in one warm turn, counted by a wrapper on the public SQLite facade.", None),
    "sql_read_stmts_per_turn": ("The read statements (SELECT, WITH) in one warm turn, part of the statements per turn.", None),
    "sql_write_stmts_per_turn": ("The write statements (INSERT, UPDATE, DELETE) in one warm turn, part of the statements per turn.", None),
    "sql_ddl_stmts_per_turn": ("The schema statements (CREATE, ALTER, DROP) in one warm turn, part of the statements per turn.", None),
    "sql_pragma_stmts_per_turn": ("The PRAGMA statements in one warm turn, listed apart because a runtime may read a pragma such as data_version often. They are part of the statements per turn.", None),
    "sql_commits_per_turn": ("The transactions the runtime committed in one warm turn, counted by the same wrapper.", None),
    "rows_returned_per_turn": ("The rows the runtime read through the facade in one warm turn.", None),
    "bytes_returned_per_turn": ("The bytes of the column values the runtime read through the facade in one warm turn.", None),
    "wchar_bytes_per_turn": ("The bytes the process tree wrote with system calls in one warm turn, from the kernel's counters (Linux only). It includes the log.", None),
    "rchar_bytes_per_turn": ("The bytes the process tree read with system calls in one warm turn, from the kernel's counters (Linux only). Reads served from the page cache are in it.", None),
    "rows_read_per_turn": ("The rows the platform counts as read in one warm turn (Cloudflare's own unit, Miniflare and Cloudflare only).", None),
    "rows_written_per_turn": ("The rows the platform counts as written in one warm turn (Cloudflare's own unit, Miniflare and Cloudflare only).", None),
    "store_bytes": ("The size of the store after a clean close: the main file, the log and the index file, read by the runner.", None),
    "store_bytes_per_turn": ("The size of the store divided by the turns in it.", r"B / n_{\mathrm{turns}}"),
    "end_rss_mib": ("The memory (RSS) of the process tree at the end of the sample.", None),
    "mem_per_conv_mib": ("The slope of the end memory against the number of conversations, over the four many-conv workloads of one arm in one round.", r"\frac{\Delta M_{\mathrm{end}}}{\Delta N}"),
    "build_ms": ("The time to build the history through the runtime's own loop, summed over its turns.", None),
    "early_turn_ms": ("The median time of the first ten turns of a build.", None),
    "late_turn_ms": ("The median time of the last ten turns of a build.", None),
    "replay_ms_per_turn": ("The time to replay the recorded statements of one turn through the facade and the driver with no runtime.", None),
}
