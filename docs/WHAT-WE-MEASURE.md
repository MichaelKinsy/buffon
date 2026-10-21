# What we measure

This page maps every family of Buffon to what it measures, the metrics it reports, why a user might care, the scenario it runs, and where it stops being informative. It is the first page to read before a number from a report.

Every harness talks to the same scripted mock model, so a number describes the harness and not a model. The mock answers instantly and without network latency, so it also does not describe a real session's end-to-end time. Each family below says what that leaves out.

A family has one of three states.

- **wired**: a workload or probe set exists and a run produces its numbers.
- **partly wired**: some of the listed metrics are produced; the rest are named as not run.
- **not run**: no workload exists yet. The family is listed so the gap is visible, and it counts against coverage in the grade ([GRADE.md](GRADE.md)).

A metric marked *planned* is specified for Buffon and is not produced by the code at this commit.

| family | state | where it is described |
|---|---|---|
| [faithfulness (F1-F8)](#faithfulness-f1-f8) | wired (F8 not probed) | [FAITHFULNESS.md](FAITHFULNESS.md) |
| [core overhead: print, tools, rpc, pty](#core-overhead) | wired | `buffon/workloads/overhead.py` |
| [startup and ready-to-type](#startup-and-ready-to-type) | wired | `buffon/workloads/overhead.py` |
| [streaming render](#streaming-render) | wired | `buffon/workloads/streaming.py` |
| [large write](#large-write) | partly wired (the harness needs a `write` tool) | `buffon/workloads/overhead.py` (`overhead/print-write`); an external suite also exists, [EXTERNAL.md](EXTERNAL.md) |
| [long session: grow and resume](#long-session-grow-and-resume) | wired | `buffon/workloads/longsession.py` |
| [extensions (ext10)](#extensions-ext10) | wired | `buffon/workloads/overhead.py` |
| [reliability and faults](#reliability-and-faults) | wired | `buffon/workloads/reliability.py` |
| [durable](#durable) | wired for the native environment; Miniflare and Cloudflare are reserved | `buffon/durable/`, [DURABLE-ADAPTERS.md](DURABLE-ADAPTERS.md), [design/DURABLE.md](design/DURABLE.md) |
| [idle hygiene](#idle-hygiene) | partly wired | `buffon/workloads/soak.py` |
| [scale](#scale) | wired | [design/SCALE.md](design/SCALE.md) |
| [search](#search) | not run | |
| [devloop](#devloop) | wired | `buffon/workloads/devloop.py` |
| [wire efficiency](#wire-efficiency) | wired (the cache-key stability score is planned) | `buffon/runner/wire.py` |
| [install and footprint](#install-and-footprint) | partly wired | |
| [egress and privacy](#egress-and-privacy) | wired as a run check, not a scored family | `buffon/runner/egress.py` |
| [external suites](#external-suites) | wired, kept out of every aggregate | [EXTERNAL.md](EXTERNAL.md) |
| [agent benchmarks](#agent-benchmarks-and-the-field-track) | protocol only | [AGENT-BENCHMARKS.md](AGENT-BENCHMARKS.md) |
| [field (opt-in)](#agent-benchmarks-and-the-field-track) | planned | [FIELD.md](FIELD.md) |

## Units and kinds

A cell names its unit and its kind. A row never mixes wall time and CPU time.

- **wall**: elapsed time on a monotonic clock, in milliseconds or seconds.
- **CPU time**: user plus system time of the harness's process tree, in milliseconds (`cpu_ms`).
- **instructions and cycles**: the retired instructions and CPU cycles of the whole process tree, where the host has counters (Linux `perf_event_open`, exact; macOS `proc_pid_rusage`, sampled and undercounting). They are the headline CPU metric, with CPU time and wall time beside them as separate cells. A host with no counters reports CPU time only, and the sample says why. **On macOS the count is sampled, not exact:** the meter reads `proc_pid_rusage` about every 165 ms (on the machine audited), so it undercounts, by an amount that depends on how long the process lives (one test loop counted 44% fewer instructions at the default interval than at a 10 ms one; METHODOLOGY section 4, "Measurement caveats by platform"). Linux `perf_event_open` counts exactly. `perf_scope` records which instructions were counted: user and kernel, user only, or sampled (METHODOLOGY section 4).
- **memory**: four named kinds, each its own column. See [the report template](REPORT-TEMPLATE.md) for the columns and the sample times. Today a run reports peak RSS (`peak_rss_mib`) and PSS samples.

Each number is a median over interleaved rounds with its spread. A difference smaller than the A/A floor of the same cell is reported as "no measurable difference". See [METHODOLOGY.md](METHODOLOGY.md) sections 6 and 7.

## Faithfulness (F1-F8)

**Measures.** How closely a harness behaves like the Pi reference arm, probe by probe, with no model and no timing.

**Metric.** A score from 0 to 100 per dimension and overall, plus a list of the probes that differ and a list of the harness's documented intentional divergences.

**Why a user cares.** Scripts, extensions and resumed sessions written for Pi break on a machine-facing difference. A harness that is fast and produces other files or other JSON is a different tool.

**Scenario.** A scripted situation runs on the reference and on the harness against the mock. Buffon reduces what each did to a JSON observation, normalises declared volatile fields, and compares the two. No fuzzy matching and no AI scoring is involved.

**Grade of a probe.** Faithfulness is graded, never pass or fail. A deterministic comparator for the probe's family decides the class.

| class | credit | what it means | example |
|---|---:|---|---|
| identical | 1.0 | the normalised observations are equal | `--mode json` emits the same events in the same order with the same keys |
| equivalent-presentation | 0.9 | a human-facing surface differs, but the same information is shown and the same actions are possible | a harness prints its `--help` with other wording, colours or layout and names the same options, as a harness that deliberately presents itself differently, such as oh-my-pi, can |
| equivalent-semantics | 0.6 | a machine-facing surface differs in form but carries the same meaning | a session record has an extra key or a different key order, an event stream has an extra event between the reference's events, or a tool result differs only in line endings or trailing spaces |
| behaviour-differs | 0.0 | a different result | the tool leaves other files, a request has other tool parameters, an option is missing |

The examples describe the classes. They are not scores of any named harness. A harness's score is whatever its faithfulness run measured.

**Weights.** A dimension's percentage is the mean credit of its scored probes. The overall score is the weighted mean of the dimensions that apply to the harness. Machine-facing dimensions weigh more than human-facing ones, because scripts, extensions and resumed sessions break on them.

| dimension | surface | weight |
|---|---|---:|
| F1 | CLI text and flags (human-facing) | 5 |
| F2 | wire requests (machine-facing) | 25 |
| F3 | tool behaviour | 15 |
| F4 | session file (machine-facing) | 15 |
| F5 | config compatibility | 10 |
| F6 | output modes, print, json, rpc (machine-facing) | 20 |
| F7 | extension compatibility (machine-facing) | 10 |
| F8 | TUI (human-facing) | 0 (not probed in v0) |

A probe a harness cannot take part in is N/A and is left out, and the remaining weights are renormalised. A harness that lacks a mode, crashes or times out on an applicable probe has a mismatch.

**A worked example, with invented numbers.** Suppose a harness has ten scored F6 probes: eight identical, one equivalent-semantics and one behaviour-differs. F6 is (8 x 1.0 + 1 x 0.6 + 1 x 0.0) / 10 = 0.86, shown as 86. Its other dimensions are scored the same way and the weights above combine them.

**How faithfulness meets the speed grade.** Faithfulness is never a weight in the Harness Score. Two rules connect them.

- A correctness failure gates the tool-using families. A tool probe whose files differ or whose result differs beyond line endings and trailing spaces, a crash, a hang, or data loss (a harness that claims Pi sessions writes none) scores `core`, `ext10` and `long-session` as 0 for that harness. A presentation or semantics difference never gates.
- Below the faithfulness floor (90), a harness is ranked in its own table, labelled "not Pi-equivalent". A harness with no faithfulness run is ranked apart, labelled "faithfulness not measured".

**Limits.** Most probes use Chat Completions; F2 covers all three wire APIs. Free-text prompt wording is judged once. F4 has no compaction, fork or tree probes yet, and F5 and F1 have no theme or MCP probes. F8 is listed and not probed. The probes do not time anything, so the host does not matter for this family.

## Core overhead

**Measures.** What the harness itself costs when the model answers instantly: print mode with one prompt, print mode with eight tool-call rounds, an RPC session, and an interactive TUI on a PTY.

**Metrics.** Instructions and cycles (the headline CPU metric where the host counts them), CPU time (`cpu_ms`), peak RSS (`peak_rss_mib`), wall time, and for tool rounds the harness-added latency per turn. The grade uses instructions where a cell has them and leaves the CPU-time cell out of the grade, so one CPU cost is not counted twice (`workloads/grade.toml`). On macOS those instructions are the sampled, undercounting kind, so a macOS grade's CPU cost is less reliable than a Linux one.

**Why a user cares.** CPU and memory are what a harness takes from the machine that runs it, which matters on a laptop, in CI, in a container with a limit, and when many sessions share a host.

**Scenario.** Interleaved rounds start each arm once per scenario with a fresh home directory, in an order rotated each round. The first repetition of each arm is a warm-up and is dropped from the statistics.

**Limits.** The mock replies at once, so network waits, provider latency and model time are absent. A real turn is dominated by those, and the harness cost here is the part left after you remove them. A harness that does less work per turn because it sends less context also does less here; that is part of what is measured and it is not a quality statement. One host and one kernel produce one set of numbers.

## Startup and ready-to-type

**Measures.** How long a process takes to start and to become usable: `--version`, the first visible frame of the TUI, the point where the TUI settles, and RPC ready time.

**Metrics.** Wall time to each point, and CPU time to ready.

**Why a user cares.** A person opens a harness many times a day, and a script may start it once per task.

**Scenario.** `version`, `pty` and `rpc` scenarios of the overhead workload. A warm start follows a start of the same arm in the same round. There is no cold-start row in this family: every start finds the binary in the page cache. The first print run on a fresh home is its own row in [devloop](#devloop).

**Limits.** "First visible frame" is detected from terminal output and is not the same instant as "ready to accept a key". Buffon answers terminal queries the same way for every arm and has two terminal profiles, `xterm-256color` (the default) and a kitty-like one, chosen per run with `--param terminal=xterm|kitty`; a run uses one, the report names it, and a harness may behave differently on a terminal that answers differently.

## Streaming render

**Measures.** The CPU a harness spends rendering an answer that arrives as a stream, by answer shape (prose, code blocks, tables, lists) and size.

**Metrics.** CPU per 1,000 streamed tokens, time from the first streamed byte to the first terminal output that shows the answer (TUI only), wall time to the end of the answer, bytes written to the terminal, and peak RSS.

**Why a user cares.** Rendering a long answer is what an interactive session does most of the time. A harness that burns a core while text scrolls feels slow and drains a battery.

**Scenario.** The mock streams one answer of a given shape in fixed chunks, once at N characters and once at 10N. The TUI variant runs one process through both sizes at a fixed token rate (`stream_rate_tps`, 1,000), because when the chunks arrive changes how a screen redraws. The print variant runs a fresh process per size and gets the chunks as fast as it reads them (`print_stream_rate_tps`, 0 for unpaced): its cost is per chunk, and pacing would only add waiting, 15 s per 60,000-character answer for every harness. Each sample records the rate it used as `stream_rate_tps` (0 is unpaced). A print-mode `wall_ms` is therefore the harness's own time to take in and write out the answer, not the stream's length.

**Limits.** Tokens are characters divided by 4, the mock's own count, and not a provider's tokenizer. Terminal size is fixed (40 rows by 120 columns by default). A different terminal or a different font renderer outside the harness is not measured. Instruction counts depend on the host's counters: user-only at the stricter kernel setting, and sampled on macOS, where a process that exits between two samples loses its last interval. Check a macOS instruction number against a Linux host before relying on it.

## Large write

**Measures.** The cost of a tool call whose arguments are large, such as a 50 KB or a 200 KB file written in one call.

**State.** `overhead/print-write` runs it. Pi-Bolt's `large_write.py` also runs as an external suite, pinned and unchanged, with its own metric names ([EXTERNAL.md](EXTERNAL.md)); that result is kept out of every aggregate.

**Metrics.** Per file size (`kb50_`, `kb200_`): wall time, CPU time, instructions, peak memory (both kinds), bytes on stdout, time from the first byte of the tool call to the request that carries its result (`call_to_result_ms`), and the part of that after the stream ends (`after_stream_ms`).

**Scenario.** Print mode, one prompt, one fresh process per size. The mock answers with one `write` call whose arguments stream 16 characters at a time (`--param write_chunk=16`, `--param write_kb=50,200`), on all three wire APIs, then a text reply. The call is built from each harness's own write tool and its own schema (Pi `path` and `content`, Claude Code `file_path`, OpenCode `filePath`, Copilot `create` with `path` and `file_text`); the project has its `big/` directory already, because Copilot's `create` requires an existing parent. Codex has no such tool: it edits through `apply_patch`, a freeform tool whose input is a patch in its own text format, so the mock streams one `*** Add File: big/source.ts` patch as a `custom_tool_call` (`response.custom_tool_call_input.delta` pieces), and the file Codex makes has a final newline, which that format cannot leave out, so that is the byte string the check expects for it. Codex declares `apply_patch` only for a model whose catalog entry says so; the arm's `print_write` mode loads a one-model catalog (`model_catalog_json`, `buffon/arms/writers/codex.py`) that gives the mock's model what Codex's own models carry, with the fallback's own 17 KB instructions (`arms/codex/base-instructions.md`, the text Codex sends on every other workload), and no other workload loads it. Runs before that file was added carried a one-line instructions text here, so their Codex requests in this test were about 17 KB smaller; the site marks those cells. A sample fails unless the file in the project directory holds exactly the expected bytes. A harness with no write tool, and none of Codex's patch tool, is n/a.

**Why a user cares.** A harness that parses streamed tool arguments badly can take far longer on a big file than on a small one.

**Limits.** An external suite uses its own mock model and its own method, so its numbers are not comparable with Buffon's families.

## Long session: grow and resume

**Measures.** What a harness costs as a conversation grows, and what it costs to resume a long one.

**Metrics.** For grow: first-turn against last-turn CPU, RSS growth, and session bytes on disk. For resume: time and CPU to be ready, memory after resume, and the cost of the first turn on the loaded history.

**Why a user cares.** Real work happens in long sessions. A harness whose cost rises with history becomes slow late in a session, and one that cannot resume a large session cannot continue yesterday's work.

**Scenario.** Grow drives one RPC process through N or 10N live turns (a tool call and a reply each) with automatic compaction on a small context window. Resume loads a generated Pi session of N or 10N turns with compaction off, so the whole history is sent. Only arms that read Pi's session files take part in resume. Resume has a varied twin, `resume-n-varied` and `resume-n10-varied`: the same session with every word replaced (see Limits). The report shows both rows. The twins are not in the grade.

**Limits.** The generated session is synthetic. The plain session draws every word from a vocabulary of 70 and every code block from five template lines, so it compresses about 6.4 to 1 (zlib), and a harness that deduplicates or compresses repeated content gains from it. The varied twin is made from the plain session: the same entries, ids, tool calls, timestamps and usage, the same length for every text, and every run of letters and digits replaced by a pseudo-word of the same length drawn from a seeded generator. So it has the same message count, the same byte size (equal to the byte in the cases measured; the test allows 1%), and no two turns share a sentence; it compresses about 2.1 to 1. Real transcripts lie between the two, so a gain that shows in the plain row and not in the twin is a deduplication gain, and a gain in both is not. The seed is derived from `session_seed` (default 1), so every harness and every run with the same seed reads the same bytes. Each resume sample records `session_variant` (`repeating` or `varied`), `session_seed` and `session_sha256` of the file it loaded. Defaults are 100 turns and 1,000 turns.

## Extensions (ext10)

**Measures.** The cost of loading ten trivial extensions, in print mode and in RPC mode. The extension sweep repeats it with 5, 50 and 100 trivial extensions (`overhead/print-ext5`, `-ext50`, `-ext100`, `rpc-ext5`, `-ext50`, `-ext100`; zero is plain print and rpc), so start-up and per-turn cost can be read against the count. A harness whose extensions are built into its executable cannot take another count and shows as cannot run for it. A harness with its own realization of the extensions loads the first N of its list, and shows as cannot run for a count above the length of its list.

**Metrics.** Instructions (where the host counts them), CPU time and peak RSS.

**Why a user cares.** Extensions are how people customise Pi. The cost of loading them applies to every start.

**Scenario.** The same overhead scenarios with ten trivial extensions loaded. Only harnesses that declare Pi extension support take part; others are N/A by scope. The extensions are copies of one template (`fixtures/extensions/bench-ext.template.ts`) that differ only in their number: a tool `bench_tool_NN`, a command `bench-NN`, and four event handlers (`session_start`, `before_agent_start`, `tool_call`, `turn_end`). `buffon/fixtures/benchext.py` writes N of them into the run's work directory, so the five of `print-ext5` are the first five of the ten, and 50 and 100 come from the same file. Each extension sample records `extensions_count` and `extensions_template_sha256`, and `equivalence.json` holds the same two facts per harness, so a reader can check which extensions ran. A harness with its own realization records the count only.

**Limits.** Ten trivial extensions do not represent a heavy extension that does real work, and they test loading more than runtime behaviour. Extension behaviour is a faithfulness question (F7).

## Reliability and faults

**Measures.** What a harness does when things go wrong: HTTP 429 and 500 that recover on retry, HTTP 429 that does not recover, a connection dropped before a reply or part-way through a stream, keepalive-only streams, a host kill during a tool call with a resume afterwards, and SIGTERM during a stream. Malformed streams are not run.

**Metrics.** The fraction of fault scenarios the harness passes, with the reference's result as the oracle. A pair that disagrees with its own A/A copy is a flaky result, not a pass.

**Why a user cares.** Providers fail and processes get killed. A harness that hangs, prints a crash trace, reports success with no reply, or leaves a session file that does not parse loses work.

**Scenario.** The mock fails chosen requests at a scripted point, identically for every arm. Each fault has invariants every arm must hold (the process ends within the time limit, no crash trace, no success without a reply, a session file that parses) and a signature of what the user observes.

**Limits.** Eight scripted faults are a small sample of real failures. Scoring against the reference means a case where Pi's behaviour is itself debatable is scored as "same as Pi". The family is not run when the reference passed none.

## Durable

**Measures.** What a durable agent runtime costs. It stores a conversation as commits, reopens it after a restart and builds the model's context from storage. Two arms run the same scripted conversations through a small adapter each: Pi Durable 1.3.0 (the reference) and PiG Durable, the Go port. Pi Durable's `main` build may run as an informational arm and is never the reference. The compat lane is adapted from durable-bench (github.com/clavia-labs/durable-bench), used with permission.

**State.** Wired for the native environment: SQLite in the process, Node for Pi and Go for PiG. The Miniflare and Cloudflare environments are reserved. A sample records its `env`, every environment is its own cell, and a native number is never quoted as a Durable Object number.

**Metrics.** Times come from the runner's own clock around the requests it sends to the adapter, never from the adapter. CPU, memory and kernel byte counters come from the process tree. The counts per turn come from a wrapper on the public SQLite facade. The store is read by the runner with its own SQLite. A metric an environment cannot produce is absent, never zero.

- `warm_net_ms` on `durable/mixed-3500` is the headline: the warm turn less the warm turn of `durable/floor-host` of the same arm and round, so it is what the runtime adds to a turn. It is never applied to a cold start. The gross `warm_turn_ms` (the median of turns 2 to 10 of a sample) is always shown beside it.
- `cold_ms` is the open request plus the first measured turn in a new process, with the store copied and read once before the clock starts. `proc_start_ms` (exec to the ready line) is shown beside it and is not part of it; `ready_to_answer_ms` is their sum, what a command-line user waits. A runtime that opens lazily moves the read of the history from `open_ms` into `first_turn_ms`, so compare `cold_ms`.
- `ttfr_ms` is the time from a submit to the scripted model's first request. `model_ms_per_turn` is the time inside the scripted model: it is shown so that the work of the benchmark is visible, and is not scored.
- `warm_instructions`, `warm_cycles` and `warm_cpu_ms` are the CPU of one warm turn; `instructions`, `cycles` and `cpu_ms` are those of the whole sample. Instructions lead where the host counts them.
- `sql_stmts_per_turn`, `sql_commits_per_turn` and `rows_returned_per_turn` are statements, transactions and rows the runtime ran or read in one warm turn. The statement kinds (`sql_read_stmts_per_turn`, `sql_write_stmts_per_turn`, `sql_ddl_stmts_per_turn`, `sql_pragma_stmts_per_turn`) are listed apart and add up to the total; the pragma statements are in it, listed apart because a runtime may read a pragma such as `data_version` often. `wchar_bytes_per_turn` and `rchar_bytes_per_turn` are the kernel's byte counters (Linux only), and `rows_read_per_turn` and `rows_written_per_turn` are the platform's own rows (Miniflare and Cloudflare only).
- `store_bytes` is the main file, the log and the index file after a clean close, and `store_bytes_per_turn` is that over the turns in the store. `peak_rss_mib`, `end_rss_mib` and `pss_mib` are memory; `mem_per_conv_mib` is the slope of the end memory against the number of conversations over the four `many-conv-*` workloads.
- The equivalence margins are in `workloads/margins.toml`: time and CPU within 5%, memory within 5% or 2 MiB, and an exact margin (every paired round has the same value) for `sql_commits_per_turn`, `rows_written_per_turn`, `store_bytes` and `store_bytes_per_turn`, which show either that the work is the same by construction or that it is not.
- A crash workload (`durable/crash-*`) is not a cell. Each point is one kill after a commit, a reopen in a new process, a resume and the same request id again, for each order of writer and resumer. A point passes when the run resumed, no invariant failed, the submission was not duplicated and the outcome equals the reference order's at the same point. The grid shows the passed share of each order with its Wilson 95% interval. An order whose resumer cannot open the writer's store (Pi 1.3.0 opens schema 1 stores and the Go port writes schema 2) is not run and is listed as not possible, never as a failure.

**Why a user cares.** A durable runtime is what keeps a long conversation alive across a restart. How long the first answer takes after a reopen, how much each warm turn costs as the history grows, how many statements and commits it takes, how large the store gets, how much memory a live conversation holds, and whether a crash loses or repeats work are what a person pays for.

**Scenario.** One scripted model and one set of tools, written once as data and implemented in each runtime's own interface; a fixture store built by the reference runtime through its real loop, copied for each sample. The compat lane is durable-bench's shape: one conversation, compaction off, a 10^9-token window, eight tool calls a turn, histories of 50, 250, 1,000 and 3,500 turns. The mixed lane is the default: compaction on, a 200,000-token window, mixed turn shapes, histories of 1,000, 3,500 and 10,000 turns. Further workloads vary the words, the window, a cold start before every turn, streaming, large outputs, document edits, child tasks, a subagent, many conversations, building a history, crashes and failing compaction summaries. Two floors run with no runtime: `durable/floor-host` (the same adapter, protocol, scripted model and SQLite file) and `durable/floor-sql` (the recorded statements of one turn replayed through the facade and the driver). Nothing is timed before an equivalence gate passes: both arms leave the same conversation state and send the same model requests, and the gate records go to `equivalence.json`. The page for the section shows the settings and versions of each arm, the gate records, the digest of each fixture and the floors.

**Limits.** The scripted model costs a little per call and is not a real model: the network and the model are left out. Native SQLite is not a Durable Object: it has no input and output gates, no hibernation, no memory limit of an isolate and no billing. The two SQLite libraries differ (Node's built-in one and the Go port's pure-Go one), and `durable/floor-sql` shows their share. The turn mix of the mixed lane is a synthetic choice, not measured from real traffic. A fixture written by Pi may suit Pi slightly, so the fixture's writer is recorded in every sample. Pi's `main` build writes schema 2 stores, which Pi 1.3.0 cannot open. The projects' own durable suites (Pi's `bench:*`, PiG's storage benchmark, durable-bench unchanged) run unchanged and appear on the same page, credited to their owners and never inside a cell. See [DURABLE-ADAPTERS.md](DURABLE-ADAPTERS.md) and [design/DURABLE.md](design/DURABLE.md).

## Idle hygiene

**Measures.** Whether a harness leaks resources over a long run.

**State.** Partly wired. The soak workload runs scripted turns against one RPC process for minutes with compaction on a small window, and samples processes, threads, file descriptors, resident and proportional memory and CPU of the whole tree at fixed intervals. A series is flat when its second half stays within a declared band. Idle CPU as its own row, wake-ups per second, and disk writes while idle are not run.

**Why a user cares.** A harness left open for days should not grow, and should not use the CPU while nothing happens.

**Limits.** The judgement is a band on the second half of a series, not a model of the leak. A run of minutes cannot show a leak that takes hours.

## Scale

**Measures.** The exact number of agents of one harness that one container holds, found by doubling N until the kernel (or another limit) stops them and then bisecting to the largest N that completes. Four workloads: `scale/agents-limit` (RPC agents, three turns in lockstep), `scale/print-limit` (one-shot print-mode agents), and the same two with every agent loading the ten bench extensions, `scale/agents-ext10` and `scale/print-ext10` (only arms that load Pi extensions; the gap between the two limits is the cost of extensions at scale). The result is the median limit over the rounds with the range, or "at least N (cap)" for a harness that reaches the safety cap (8192). Per probe, which is one N tried: memory of the container and per agent (`memory.peak`, PSS), CPU per agent-turn, p50, p95 and maximum turn latency (RPC) or wall time and makespan (print), agent-turns per second, OOM kills, processes at the peak, throttled periods, and the CPU of the scripted model with a flag where it was saturated.

**Why a user cares.** A team box, a CI host or an agent farm runs many agents at once. Memory per agent decides how many fit in a box of a given size, and what happens at the limit is a result: the kernel's OOM killer, a refused fork or a stage that never finishes.

**Scenario.** All agents of a probe run in one container with a memory limit (`swarm_memory_gib`, default the run's tier), a cpuset and a pids limit; the agents never run outside it. Each agent has its own home and project, and does real work from the scripted model each turn: reads a file, writes one, runs one shell command, answers. A probe that does not complete (not every agent ready and done) is a failure with a cause (oom, stall, timeout, pids, error). Every probe of the search is recorded with its N, outcome and cause, so the curves of memory and CPU against N have the bisection's points too.

**State.** Wired (RPC and print-mode agents, one container on one host, needs `--isolation container`). Terminal agents, the long-context stages and the cluster run are not built. This family is concurrent by design, so it is an exception to the serial rule ([METHODOLOGY.md](METHODOLOGY.md) section 18): one sample at a time, and nothing else on the host. [design/SCALE.md](design/SCALE.md) holds the design.

## Search

**Measures.** `grep` and `find` on trees of 10,000, 100,000 and 1,000,000 files.

**State.** Not run. Pi's own tools need `rg` and `fd`, which the egress rule keeps Buffon from downloading; see the invalid-probe rule in [FAITHFULNESS.md](FAITHFULNESS.md).

## Devloop

**Measures.** What a person pays to get a harness and start it for the first time: clean-host install time, build time of a source-built arm at its pinned commit, and the first print run on a fresh home.

**Metrics.** Wall time for each step, and for the first run the size of the home directory afterwards (`home_mb`).

**Why a user cares.** It is the cost of trying a harness, and of rebuilding one in CI.

**Scenario.** `devloop/install` installs the arm from the verified download cache. `devloop/build` builds a source-built arm with the pinned toolchain. `devloop/first-run` runs once with no first-start seed, so work other families hide (unpacking natives, for example) shows here. A step an arm does not have is N/A with the reason.

**Limits.** The extension edit-to-reload loop and the build times of extension-realization arms are not measured yet. Clone, download and build steps are slow by nature and vary with the network and the host; see [METHODOLOGY.md](METHODOLOGY.md) section 12.

## Wire efficiency

**Measures.** How much a harness sends and whether it keeps the front of its prompt stable.

**State.** Wired for the request rows, and the cache-key stability score is *planned*. The mock logs every request with its wire bytes and full body, and the F2 probes compare requests field by field. The runner counts, for every sample of every workload, the model requests the mock received between the sample's start and its end. Requests that fail or that a fault drops count too. The count is not filtered by tools, so a title request is in it.

**Metrics.** Kind `wire`, lower is better, shown in report cells and never in the grade (`workloads/grade.toml` lists no wire row).

- `requests`: the model requests received during the sample. A sample the mock saw no request in has none of these metrics.
- `request_bytes`: the sum of the request body bytes on the wire.
- `request_bytes_per_turn`: `request_bytes` divided by the workload's turns, where the workload knows them. A turn is one model round for the print workloads (`print`, `print-tools`, `print-write`, `pty`, streaming): the tool rounds plus the reply, or one answer per size. It is one prompt for `rpc`, `rpc-ext10`, the long session and the resumed session, where a prompt is a tool call and a reply.
- `side_requests`: requests beyond the ones the workload scripted, never below 0. The workload scripted 1 or 2 per round or prompt, plus the compaction requests found by their summarisation prompt in the long session. An arm with `exact_requests` in its manifest must send none: a sample of such an arm that sends one fails, except in the long session, where the compactions are the harness's own decision and the count is not fixed. A workload that does not know how many it scripted (the soak, reliability, devloop) has no `side_requests` and no per-turn row.

Earlier runs recorded `request_bytes` as the size of the first request. It is now the sum, so compare it only with runs of the same version.

**Why a user cares.** Request size is token cost, and a changed prefix loses the provider's prompt cache, which costs money directly.

**Limits.** The mock has no cache, so the stability score would count prefix changes and would not measure a provider's hit rate.

## Install and footprint

**Measures.** What a user installs: bytes on disk and file count of the install tree.

**State.** Wired. Size and file count are recorded for each arm and printed in the report's arms table. They are properties of the install and not samples. The first run on a fresh home is measured in [devloop](#devloop).

**Limits.** An npm install tree, a single binary and a container image are different things to count; the report names the install kind beside each number.

## Egress and privacy

**Measures.** Whether a harness opens network connections the run did not expect.

**State.** A check on every run, not a scored family. No request may leave the machine in a no-spend run. In an isolated network namespace egress is impossible by construction. Elsewhere the audit reads the process tree's sockets while the harness runs, and a connected socket whose remote address is not loopback is a violation.

**Limits.** The audit samples every 25 ms on Linux, so a connection that opens and closes inside one interval can be missed, and a strict run should use an isolated namespace. It is not a privacy audit of a harness's behaviour with a real account.

## External suites

**Measures.** Other projects' benchmarks (Pi's durable `bench:*` scripts, Pi's evals, Pi-Bolt's suites), run unchanged at a pinned commit, or published results imported with provenance.

**Metrics.** The suite's own names and units. Buffon does not rename or convert them.

**Why a user cares.** They show whether Buffon's numbers agree with other published work, and they hold workloads Buffon does not have yet.

**Limits.** Each suite has its own model, host and method. External results are kept out of every aggregate and every grade. The import guard refuses a suite that is unpinned or modified. See [EXTERNAL.md](EXTERNAL.md).

## Agent benchmarks and the field track

**Measures.** Whether a harness helps the same real model solve real tasks.

**State.** `buffon agentbench` plans a protocol and computes the paired result from observations an operator supplies ([AGENT-BENCHMARKS.md](AGENT-BENCHMARKS.md)). The opt-in field track, with the user's own API key and a budget cap, is specified in [FIELD.md](FIELD.md) and is *planned*. It never enters the default leaderboard or the Harness Score.

**Limits.** Pass rates on a few tasks have wide intervals. A field result is labelled FIELD with its model id and date.
