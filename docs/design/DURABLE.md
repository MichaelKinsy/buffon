# Design: the `durable` family (durable agent runtimes)

Status: Phase 1, the native environment, is built (section 11 says what and where it differs from this design). Miniflare and workerd, real Cloudflare, the Wasm core arm and tardigrade are designed here and not built. The sections below are the design as written on 2026-10-18; every number quoted in them is somebody else's measurement or a derivation from one, and the source is in brackets. A claim with no source is marked `[INFERENCE]`. Source keys are listed in "Sources" at the end.

Date of the research: 2026-10-18.

## 0. Summary

- A durable runtime stores a conversation as commits, reopens it after a crash, and builds the model's context from storage. The family measures what a person pays for that, on one scripted model.
- The two arms are Pi Durable (`@earendil-works/pi-durable`, the reference) and PiG Durable (the Go port in `durable/`, and later the Wasm core for Durable Objects). An arm here is a runtime package plus a small host adapter.
- The published benchmark, durable-bench, is a good cold/warm probe of one shape of conversation. It turns compaction off, uses a 10^9-token window, drives one conversation, and its scripted model walks the whole history on every call. It is not a statement about a realistic session.
- The family has two lanes. The `compat` lane runs durable-bench's shape so numbers can be set beside the published ones. The `mixed` lane is the default: compaction on, a 200k-token window, mixed turn shapes, histories from 50 to 10,000 turns.
- Metrics are read at boundaries the runtime does not own: the runner's clock, the process tree's CPU counters, a counting wrapper on the public SQLite facade, kernel I/O counters, the database file, and (on Cloudflare) the platform's own `rowsRead` and `rowsWritten`.
- Nothing is timed before an equivalence gate passes: both arms must leave the same conversation state and send the same model requests, and each must open the other's store.
- Environments in priority order: native SQLite (Node and Go), Miniflare/workerd, real Cloudflare (optional, needs an account).
- The project suites (Pi's `bench:*`, PiG's `BenchmarkStorage*`, durable-bench itself) run unchanged and appear beside Buffon's numbers on the Durable page under "Each project's own durable suites", credited, never inside a cell.
- A minimal first run is under one hour of exclusive machine time. A full run is about 5 to 6 hours for one session, and a headline needs two sessions.

### Owner decisions (2026-10-18). These supersede the open questions in section 9.
- **Arms.** Pi Durable 1.3.0 (the reference), PiG Durable native Go, PiG Durable Wasm core (in Miniflare and on Cloudflare, labelled with its build), and tardigrade as the third runtime. The main branch of Pi is informational only.
- **durable-bench.** We have permission to use our own version of durable-bench. It becomes the `compat` lane in Buffon, with a one-line attribution in NOTICE and on the Durable page: "The compat lane is adapted from durable-bench (github.com/clavia-labs/durable-bench), used with permission." The unchanged upstream run stays as a project suite.
- **No third-party review** of adapters before publication. Everything is FOSS. The adapters are public and hashed by `arms.lock`, and anyone can rerun any cell.
- **Cloudflare.** The owner will provide access. The real-Cloudflare lane is in scope once the token is on the runner host.
- **Headline.** `warm_net_ms` on `mixed-3500`, with compat beside it.

## 1. What a durable runtime is responsible for

Pi Durable describes itself as a harness: storage plus the machinery to run conversations, tools and tasks. Everything it runs is a task, and each step stores a checkpoint before it moves on [PA] [PD]. The responsibilities, and what a user feels when each is slow or wrong:

| Responsibility | What the user feels | Source |
|---|---|---|
| Open a stored conversation | Time to the first answer after a restart, a laptop wake, a container redeploy, or a Durable Object eviction. Pi opens lazily, so the history read moves from `open` into the first turn. "Reopen only" is near constant and misleading; compare open plus first turn. | [DBH] |
| Build the model context | Warm turn time. Pi 1.0.4 re-read and re-derived the whole transcript for every model request. Since 1.1.0 it keeps each conversation's last range and derived view in memory (`contextRetentionMs`, default ten minutes). | [PC] 1.1.0 |
| Commit before show | Write amplification. Every step, partial answer (default every 100 ms) and tool-output progress commit to storage before a client sees them. | [PD] "Watching a Conversation" |
| Store size | Disk used. SQLite file: 237,568 B at 50 turns, 9,265,152 B at 3,500 turns in durable-bench's fixtures. | [BK] section 4 |
| Memory per live conversation | How many conversations one process or one 128 MB isolate holds. Pi keeps the working set (active transcripts, live tasks, pending submissions) in memory and says compaction bounds it. Idle contexts and documents are dropped after `contextRetentionMs` and `documentRetentionMs`. | [PA] "Long runs anywhere", [PD] Settings, [PC] 1.2.0 |
| Crash and resume | No lost or duplicated work. A cut-off model request is sent again. A tool reruns only if declared `replay: "safe"`; otherwise the model is told it was interrupted. A `requestId` makes a submission exactly-once. A task cut off five times in a row is parked (unreleased). | [PA] "Survives crashes", [PD], [PC] Unreleased |
| Compaction | Whether a long conversation keeps working. Background summaries start `backgroundTokens` before the blocking threshold; the conversation waits only when the next request would not fit. | [PD] Compaction |
| Documents and tasks | App state and long work in the same atomic commits as the transcript. Child tasks, task graph, subagents as owned conversations. | [PD] |
| Many conversations | One harness runs many conversations at once. One process owns a storage at a time. | [PA], [PD] Storage |
| Cost on Cloudflare | Rows read, rows written, stored bytes and duration. Rows read cost $0.001 per million beyond 25 billion a month. Rows written cost $1.00 per million beyond 50 million a month. Each `setAlarm()` is one row written, and every index row update counts as a row. Duration is billed at 128 MB per object whatever it uses, while the object is active or not eligible to hibernate. Stored data is $0.20 per GB-month. | [CFP], [CFA] |

PiG Durable is a Go port of the same package: `durable/` (types, session, harness, SQLite storage on pure-Go modernc SQLite, tools, env) [PG]. Its storage benchmark ports Pi's `storage.bench.ts` [PG]. Two further things are being built and are not in the checkout read for this document: native speed-ups (the `durable-perf` lane) and the Wasm core for Durable Objects (TinyGo first, one source for Wasm and native) [MB] entry "22:15 MDT: OWNER APPROVED the production Durable core", [B1] section 3. The owner ruled that no public numbers come from the prototype; the deck renders only from the production core after it passes the contract gate [MB] entry "22:20 MDT". This design keeps that rule (section 9).

## 2. What durable-bench measures, and where it is unrepresentative

### What it does

- One conversation in one Durable Object (`getByName("main")`), on Miniflare, SQLite-backed [DB2 src/pi-head.ts, bench/targets.ts].
- A scripted model (pi-ai's faux provider with a response factory) and one `lookup` tool. Seeded histories repeat a one-tool, one-tool, zero-tool pattern at 50, 250, 1,000 and 3,500 turns [DB1].
- Per sample: a fresh Miniflare, `wake`, then ten measured turns of eight tool calls each. Cold is open plus the first turn, excluding runtime start. Warm is the median of the other nine. Three samples per size, a quiet-CPU gate of 8% [DB1] [DB2 bench/run.ts].
- Timing is taken in the Node client around `dispatchFetch`; RSS is the `ps` sum of the process tree; storage is `databaseSize` and per-table row counts [DB2 bench/run.ts, src/serve.ts].
- The badlogic fork adds a `pi-head` target that builds pi-durable from source and opens storage with Pi's own Durable Object adapter. The original used a hand-written facade (`src/pi.ts`) [DB2 README]. The adapter shipped only in Pi 1.1.0 [PC].
- Published, 3,500 turns: Pi cold 365 ms and warm 313 ms, Tardigrade 880 and 123 (Apple M5) [DB1]. Pi main `da866ada`: cold 183 ms, warm 82 ms, on two P-core threads of an i9-13900 [DBP].
- Mario's second benchmark, `harness/`, runs outside Durable Objects on Node and Bun and adds commit latency, reopen, memory, app-state growth, disk, a versioning matrix and a request-equivalence check [DBH].

### What it gets right

- Histories are built through the real agent loop, never by inserting rows [DBP] [DBH].
- A fresh runtime per sample, a fixture copy per sample that is read once before timing, and a CPU-quiet gate [DB2 bench/targets.ts].
- Cold is defined as open plus first turn [DB1].
- It records the SQLite size and rows per table, so storage growth is visible [DB2 src/serve.ts].
- Both runtimes get the same scripted model and tool, and the transcript has a fingerprint [DB2 src/plan.ts].
- It uses the project's own Durable Object adapter in the fork, so what is timed is what ships [DB2 README].
- Raw results are published as JSONL [DBP].

### Where it is unrepresentative

| Issue | Evidence | Effect |
|---|---|---|
| Compaction off, window 10^9 tokens | `settings: { compaction: { enabled: false } }`, `contextWindow: 1e9` [DB2 src/pi-head.ts] | The active range is the whole history. Pi's own claim, that compaction bounds the working set [PA], is not tested. Worst case for any design that avoids rereading history; best case for one that keeps an index. [B1] section 5 item 1 |
| One conversation, one object | `getByName("main")` [DB2 src/pi-head.ts] | No concurrency, no isolate sharing, no memory per conversation. |
| Scripted model costs O(history) per call | The response factory maps every transcript message and `next()` scans the context [DB2 src/pi-head.ts, src/plan.ts]. pi-ai's faux provider also serialises the transcript for its usage estimate [DP]. | Part of each turn is the benchmark's model. Measured at 4.4 to 5.8 ms per call at 3,500 turns, about 7% of a Pi turn [DR] [BK]. Mario's harness benchmark avoids it with an O(1) fake [DBH]. |
| One tool call shape | Eight `lookup` calls per measured turn, result 256 characters, every 97th result 8,192 [DB2 src/plan.ts] | No large tool output, no text-only turns, no mixed shapes. |
| Instant, unstreamed model | Faux with `tokenSize` 10^9 [DB2 src/pi-head.ts] [INFERENCE: one chunk per message, so partial commits are not exercised] | The 100 ms partial and tool-progress commit path is not measured. |
| Only the built-in documents and tasks | Only `lookup`, no user documents, no child tasks, no forks, no subagents [DB2 src/pi-head.ts] | Half of what the package sells is untested. |
| No crash, no resume | Not in the runner [DB2 bench/run.ts] | Correctness under restart is not measured. |
| Miniflare only | `new Miniflare(...)` [DB2 bench/targets.ts] | Local workerd. Its clock advances only at I/O and timers tick at 1 ms [DR] [B1]. No network storage, no real eviction, no billing. |
| Cold is a fresh Miniflare | One start per sample [DB2 bench/run.ts] | Isolate-cold and object-cold are fused. A real object is mostly evicted between user turns, not between processes [CFL]. |
| Ten turns per sample, three samples | `MEASURED_TURNS = 10`, `SAMPLES = 3` [DB2 bench/targets.ts] | Few samples, and each turn adds about 19 entries [DR]. |
| Repetitive payload | `"x".repeat(...)` [DB2 src/plan.ts] | Compresses well. Matters if the store compresses. |
| No licence | The GitHub API reports none for either repository [API check, 2026-10-18] | Run it unchanged. Do not copy code into Buffon. |
| Absolute times depend on the machine | Published M5 and i9-13900 numbers; the same workload ran about 3x slower on a shared Xeon [DR] | Compare shapes and ratios, or calibrate by running the original unchanged on our host. |

Earlier numbers for orientation (different hosts and Pi versions, not comparable with each other): at 3,500 turns Pi 1.0.4 in Miniflare 1,007 ms cold and 838 ms warm on the benchmark host [DR]; Pi main, one pinned benchmark-host core, 386 ms cold and 157 ms warm [MB] entry "18:50 MDT: DURABLE step 1".

## 3. Scenarios

### 3.1 Lanes and defaults

Two lanes share one scenario machinery.

- **`compat`** reproduces durable-bench's shape: one conversation, compaction off, window 10^9 tokens, eight 256-byte tool calls per measured turn, ten measured turns, histories 50, 250, 1,000, 3,500, plus 10,000. It exists so Buffon's numbers can be read beside the published ones. It carries the label "durable-bench shape".
- **`mixed`** is the realistic default: compaction on, 200,000-token window (the window in the bake-off's compaction workload [BK] W4a), Pi's shipped compaction settings (`reserveTokens` 16384, `keepRecentTokens` 20000, `backgroundTokens` 32768 [PD] Compaction), the turn mix of 3.3, histories 1,000, 3,500 and 10,000. Compaction on means the active context stays bounded while storage keeps growing.

The default for any `buffon up --track durable` run is `mixed`. `compat` runs beside it and is never used for a headline on its own.

### 3.2 Parameters

| Parameter | Values | Default | Why |
|---|---|---|---|
| `turns` (history) | 50, 250, 1,000, 3,500, 10,000 | 1,000, 3,500, 10,000 for mixed; 50 to 3,500 for compat (+10,000 optional) | The first four are durable-bench's. 10,000 shows linear against flat growth; Mario skipped it because building takes quadratic time [DBH]. |
| `compaction` | off; on at 32k, 200k, 1M window | off in compat, 200k in mixed | Tests whether cost is bounded by the window or by the history. |
| `shape` | `bench8` (eight 256 B calls); `mixed`; `text`; `tools`; `large` | `bench8` in compat, `mixed` in mixed | See 3.3. |
| `varied` | `repeating` or `varied` twin | both, reported side by side | Same twin idea as Buffon's long session: same ids, structure and lengths, every word replaced [BF sessions.py]. |
| `docs` | 0, 100, 1,000 user-document edits | 0 | The durable-bench harness measures document growth as app-state edits of 88 bytes, one commit each [DBH] axis 2. |
| `tasks` | 0, 8, 64 child tasks per tool call | 0 | Pi benchmarks task fan-out (`bench:scheduler-fanout`) and nested calls [PB]. |
| `conversations` N | 1, 8, 32, 128 | 1 | Memory per live conversation and fairness between conversations. |
| `objects` K | 1, 8, 32 per isolate | 1 | Durable Object memory density against the 128 MB isolate [CFP] footnote 5. |
| `partial_ms` | 100 (shipped), 500 | 100 | Streaming write rate. |
| `storage` | `sqlite` | `sqlite` | JSONL keeps all history in memory [PD] Storage, so it is not a long-session backend. Memory and JSONL appear only in the project suites. |

Not parameters: the pragmas (WAL, `synchronous = NORMAL`, auto-checkpoint 1,000 pages) are equal on both sides [DR] and recorded in each sample.

### 3.3 Turn shapes

All shapes come from one seeded generator. The base turn is Buffon's long-session turn: a user question, a tool call, a 2.5 to 5.5 KB result, a text answer [BF sessions.py]. `[INFERENCE]` The weights below are our synthetic choice. They are not measured from real traffic, and the owner should replace them with measured shares if any exist (section 9).

| Shape | Content | Why |
|---|---|---|
| `bench8` | Eight `lookup` calls, 256 B result, every 97th 8,192 B; histories repeat 1, 1, 0 tool turns | durable-bench's shape [DB2 src/plan.ts] |
| `tools` | 4 to 12 calls per turn, results 0.5 to 8 KB | A coding session |
| `text` | No tool, 300 to 1,500 character answer | A chat thread |
| `large` | One call with a 32 KB result (the bake-off's W4c size [BK]) | The progress and output-limit path [PB] `bench:tool-output` |
| `mixed` | 50% light tool turns (1 to 3 calls), 20% `tools`, 20% `text`, 10% `large` | Default |

Token accounting follows Buffon's mock rule: one token per 4 bytes [BF METHODOLOGY section 3]. At that rule a 4 KB-result turn is about 1,100 tokens, so a 200k window compacts roughly every 150 turns. [INFERENCE: arithmetic from the rule]. That gives about 23 compactions at 3,500 turns and 65 at 10,000.

Summaries are real answers of fixed size (default 2 KB). One of our own benchmark drivers once answered summary requests with a tool call, so every compaction failed and was retried about seven times per turn. That is faithful to Pi but a stress case, not a realistic one [SC] "Frontier tasks" note on R5, which asks for a realistic-summary workload. The family uses a realistic summary and keeps the failing-summary case as its own scenario (`durable/compaction-fail`).

### 3.4 The workloads

Ids follow `durable/<name>`; a size or count is a suffix. `env` (native, miniflare, cloudflare) is a variant axis beside the one the wire API uses today, see section 7. Rounds follow METHODOLOGY (12 measured plus 1 warm-up, A/A on every serial workload).

| Id | Shape | Parameters | Matters because |
|---|---|---|---|
| `durable/compat-{50,250,1000,3500,10000}` | durable-bench's shape | `bench8`, compaction off | Comparison with published numbers |
| `durable/mixed-{1000,3500,10000}` | Default: open the fixture, ten measured turns | `mixed`, 200k window | What a user lives |
| `durable/mixed-varied-{...}` | Twin of the above | `varied` | Removes any deduplication gain |
| `durable/window-{32k,200k,1m}-3500` | Same as `mixed-3500` | window sweep | Cost against window, not history |
| `durable/cold-every-turn-{1000,3500}` | Reopen the store before every measured turn (new process native, new runtime or evicted object on workerd) | `mixed` | Most real turns are cold: an eligible idle object hibernates after 10 s, and a non-hibernatable one is evicted after 70 to 140 s [CFL] |
| `durable/stream-{50,1000}` | Each response streams 40 to 60 chunks over 1 to 2 s | `partial_ms` 100 | Write amplification and first-token overhead [BK] W3 |
| `durable/large-output-{50,1000}` | One 32 KB result per turn | `large` | Record size through scan and partial commits [BK] W4c |
| `durable/docs-{100,1000}` | Warm turn after N document edits | `docs` | Document revision cost [DBH] axis 2 |
| `durable/tasks-{8,64}` | A tool creates N child tasks and waits | `tasks` | Scheduler cost [PC] 1.2.0 |
| `durable/subagent` | A tool owns a child conversation | `tasks` | The subagent pattern [PD] |
| `durable/many-conv-{1,8,32,128}` | N conversations, equal history, one turn each in round robin | `conversations` | Memory per live conversation |
| `durable/many-obj-{1,8,32}` | K stores in one process or isolate | `objects` | Isolate density |
| `durable/grow-{1000,3500}` | Build the history through the arm's own loop, time each turn | none | Cumulative build time, the quadratic term [DBP] |
| `durable/crash-{k}` | Kill the process after commit k, reopen, finish | k sampled | Resume correctness |
| `durable/compaction-fail` | Summaries fail | window 32k | Failure path [PC] 1.2.0 |
| `durable/floor-host`, `durable/floor-sql` | Adapter path with no runtime; recorded statement replay | none | Floors, section 4 |

### 3.5 Fixtures

- A generator, seeded and versioned, writes a conversation script: per turn the user text, the model's responses (text, tool calls with ids, stop reasons, usage) and the tool results. Its sha256 and the seed are recorded in every sample (`fixture_sha256`, `fixture_seed`), as the long session records `session_sha256` [BF RAW-FORMAT].
- The varied twin is made from the repeating script by the long session's rule: same entries, ids, tool calls, usage and lengths; every run of letters and digits replaced by a seeded pseudo-word of the same length [BF sessions.py].
- A store is built once by the reference runtime driving the script through its real loop, cached by sha256, and copied per sample. The copy is read once before timing so page-cache state is equal [DB2 bench/targets.ts `stage`]. The writer is recorded as `fixture_writer`.
- A Pi-written store favours Pi slightly. To measure that, the same script is also built by PiG at the sizes where it finishes in reasonable time (Go seeding was quadratic and too slow at 3,500 in the earlier build [DR]), and the twin rows are reported next to each other. Row counts and file size matched at 50 to 1,000 turns [DR].
- Fixtures with compaction on are built by the runtime with compaction on and the realistic summary. Head markers bound the active range [BK] W4a.

## 4. Metrics

### 4.1 Rules that apply to all

- Time comes from the runner's monotonic clock around adapter requests. The adapter's own timings go to `series` and are never read by the statistics [BF RAW-FORMAT `series`].
- A turn is submit, wait for the submission, wait for the conversation to go idle, as durable-bench's `turn()` does [DB2 src/pi-head.ts].
- Memory, CPU and I/O come from the kernel for the whole process tree: cgroup `cpu.stat`, `memory.peak`, `io.stat`, 25 ms `VmHWM` polls, `perf_event_open` instructions and cycles [BF METHODOLOGY section 4]. On macOS the numbers are provisional and sampled [BF METHODOLOGY section 4 caveats].
- A metric the environment cannot produce is absent, never zero.
- An adapter is never asked for a counter the runtime keeps. Where an adapter does count (statement trace), the count is cross-checked by a layer the adapter does not control (4.3).

### 4.2 Definitions

| Metric | Definition | Read from | Notes |
|---|---|---|---|
| `cold_ms` | Runner sends `open`, adapter answers the first measured turn. Fixture staged and read once. Process start excluded. | Runner clock | Open plus first turn, as durable-bench [DB1]. Also `open_ms` (open only) and `first_turn_ms`. |
| `proc_start_ms` | Exec to adapter ready | Runner clock, launch gate [BF METHODOLOGY section 4] | Node about 1 s unbundled, Go about 20 ms in the earlier harness [DR]. Shown, not part of `cold_ms`, because a Durable Object pays it differently. |
| `ready_to_answer_ms` | `proc_start_ms + cold_ms` | derived | What a CLI-style or container user waits. |
| `warm_turn_ms` | Median of turns 2 to 10 of a sample | Runner clock | |
| `warm_net_ms` | `warm_turn_ms` minus the median `durable/floor-host` turn of the same arm, same round, same env | derived | Never applied to cold [BK] rule 7. Gross is always shown. |
| `ttfr_ms` | `submit` called to the scripted provider receiving its first request | Monotonic timestamps from the runner and from the provider; Node `hrtime` and Go `time.Now` both read CLOCK_MONOTONIC on Linux [INFERENCE] | Runtime overhead before the model. |
| `first_delta_ms` | First delta leaves the scripted provider to a subscriber's callback sees it | same | Commit-before-show latency. `durable/stream` only. |
| `cpu_instr`, `cpu_cycles`, `cpu_ms` | Whole tree, per measured turn, from readings between turns | `perf_event_open`, cgroup `cpu.stat` [BF METHODOLOGY section 4] | CPU is read at the barrier the adapter honours between turns. Both runtimes use more than one thread (CPU over wall 1.4 to 1.8) [DR], which is why instructions lead. |
| `model_ms_per_turn` | Time inside the scripted provider | Adapter timestamps in `series` | Shown so the benchmark's own work is visible. Should be near zero (section 6). |
| `sql_stmts`, `sql_commits` per turn | Statements and transactions through the SQLite facade | Counting wrapper (4.3 A) | Pi 1.0.4: 2,639 statements per 8-tool turn at 3,500 turns, 372 write statements in 77 commits [DR]. |
| `rows_returned`, `bytes_returned` per turn | Rows and column bytes the runtime read | Counting wrapper | Pi 1.0.4: about 212,700 rows and 81 MB per turn at 3,500 turns [B1]. |
| `rows_read`, `rows_written` per turn (Cloudflare units) | The platform's cursor counters, summed per turn | Host shim reads `SqlStorageCursor.rowsRead` and `rowsWritten`; the platform uses the final values for billing [CFA] | Miniflare and Cloudflare only. Includes index rows and alarm rows. |
| `bytes_written`, `bytes_read` per turn | Syscall bytes of the tree | `/proc/<pid>/io` `wchar`, `rchar`, cgroup `io.stat` | Includes WAL. `rchar` counts reads served by the page cache, so it is comparable to `bytes_returned`. |
| `store_bytes` | Main file, WAL and shm after a clean close and `wal_checkpoint(TRUNCATE)` | Runner `stat` | Also `store_bytes_per_turn` and per-table rows, opened by the runner with its own SQLite, not by the arm. On Durable Objects, `sql.databaseSize` [DB2 src/serve.ts]. |
| `peak_rss_mib`, `ready_rss_mib`, `end_rss_mib`, `pss_mib` | Tree peak, at ready, at end | cgroup, 25 ms `VmHWM` polls, PSS at ready [BF METHODOLOGY section 4] | |
| `mem_per_conv_mib` | Slope of `end_rss_mib` against N in `many-conv` | Runner arithmetic over probes | On workerd, the slope against K objects. [BK] M5 used the same idea. |
| `reopen_ms`, `resume_ms` | Adapter start after a kill to ready; to the interrupted submission settled and idle | Runner clock | `durable/crash-*` |
| `resume_ok` | Pass or fail per crash point, see 4.4 | Runner, from the store and a side-effect ledger | Pass rate with Wilson interval |
| `bill_usd_per_1k_turns` | `1000 * (rows_read * 0.001 + rows_written * 1.00) / 1e6` | Derived from measured rows and a dated `pricing.toml` | Marginal price, ignoring the monthly allowance. The price table carries its URL and date [CFP]. |
| `do_gb_s_per_turn` | `warm_turn_ms / 1000 * 0.128` | Derived | Lower bound with an instant model. A real model's wait is added by the user's own latency [CFP] footnote 5. |

### 4.3 Reading rows and bytes without trusting the runtime

Three independent layers, so no single counter decides.

- **A. A counting wrapper on the public SQLite facade.** Both runtimes define the same small `SqliteDatabase` interface (`exec`, `run`, `get`, `all`, `transaction`, `close`) [PG durable/storage/sqlite/database.go] [PS] Pi's `@earendil-works/chord/sqlite`. The adapter wraps it. It counts statements by kind, transactions, bound-parameter bytes, rows returned, and column bytes returned, and records changes for writes. The wrapper is written once in TypeScript and once in Go and tested for equal output on one scripted statement stream. This is what the bundle's `pix.ts` and `capsql` did [CT] section 7.1. The wrapper is adapter code, so layers B and C exist.
- **B. Kernel counters.** `wchar`, `rchar` and cgroup `io.stat`. They see every byte the library wrote to the database and the WAL, whatever the wrapper counted.
- **C. The files.** The runner opens the store after the sample with its own SQLite: row counts per table, page count, freelist, file sizes. Pi's `bench:storage:memory` reads the same quantities [PB].
- **D. On Durable Objects.** The platform's `rowsRead` and `rowsWritten` per cursor [CFA]. On real Cloudflare also the account's billing analytics for a fixed run. Whether Miniflare counts index rows as production does is not verified [B1] item 9 and [RK] V4.

Native SQLite has no billing-equivalent "rows read". The native family reports rows and bytes returned and says so. Cloudflare's rows read is rows scanned, which a return count does not equal [INFERENCE: D1 and DO share a definition by [CFP] footnote 1; scan semantics not read here].

### 4.4 Crash and resume

- Crash injection is in the facade wrapper of each adapter: after the k-th commit returns, the adapter sends itself SIGKILL. The runner records k from the wrapper's barrier, not from the runtime.
- Points: for sizes 50 and 1,000 every commit of one measured turn (about 77 in Pi's 8-tool turn [DR]); at 3,500, ten sampled points including first and last; for `stream`, every partial commit [BK] A3. The orders are the contract's handoff matrix: Pi then Pi (control), Pi then PiG, PiG then Pi, PiG then PiG [CT] section 5.5. `[INFERENCE]` The same points are used for PiG, whose commit grouping is meant to match Pi's [B1] D3.
- After the kill the runner starts a new adapter on the same store. The adapter reopens, calls `resume()`, resubmits the same `requestId`, and waits.
- Pass requires all of:
  1. The final store equals the uncrashed control's at the semantic level of 6.2.
  2. The resubmission returned the existing submission, not a second one [PD] Persist and Resume.
  3. A side-effect ledger, written by the tool outside the database, shows what Pi's contract promises: a `replay: "safe"` tool may appear again; a tool that is not safe appears once, and the model sees an interrupted result [PD] Tools.
  4. No duplicated assistant entry for one request.
- The reference arm's outcome is the oracle, as in Buffon's reliability family. A pair that disagrees with its own A/A copy is a flaky result.
- Earlier PiG evidence, for orientation only: 151 of 162 kill points matched Pi's order after restart at that snapshot [B2]. A change from that snapshot is not assumed.

### 4.5 Empty-runtime floors

- `durable/floor-host`: the same adapter, the same protocol, the same scripted provider and tool, the same SQLite file, and no durable runtime. It runs the full request path and a fixed number of trivial statements. Its turn time is the cost of the host and the harness. On Miniflare it is an empty Durable Object that answers `wake` and `turn` at once; the bake-off measured about 8 ms per turn for it on its host [BK] L0.
- `durable/floor-sql`: replays the statement stream of one measured turn (captured once from the reference, 3,544 statements in 776 transactions for ten turns [DP]) through each side's own facade and driver. It separates SQLite and driver cost from runtime cost. The driver choice was worth under 20% of a floor of about 10 ms per turn [DP]. `[INFERENCE]` The statement stream is data, so one capture serves both arms.

## 5. Environments, in priority order

### 5.1 Native local SQLite

Arms: `pi-durable` on Node with `node:sqlite` (`openNodeSqliteStorage`), and `pig-durable` in Go with modernc SQLite (`durable/storage/sqlite/node`) [PD] Storage [PG]. Both set WAL, `synchronous = NORMAL`, and a 1,000-page auto-checkpoint [DR].

Shows: the runtime's own cost without Cloudflare, cleanly, with perf counters, on a pinned host with the quiet gate. Reproducible and benchmark-host-friendly. The bundle found Pi on `node:sqlite` within about 10% of Pi in Miniflare (warm 830 against 838 ms at 3,500 turns), so it is a fair stand-in for Pi's cost [DR].

Cannot show: Durable Object semantics (input and output gates, hibernation, 128 MB isolate, alarms), the network, platform row accounting, eviction in production, or the Wasm core's compile cost. The two SQLite libraries differ (Node's built-in 3.53.4, modernc 1.53.0) [DR]; `floor-sql` bounds the effect and a same-library control is not available natively `[INFERENCE]`.

### 5.2 Miniflare and workerd

Arms: `pi-durable` through `openDurableObjectSqliteStorage(ctx.storage)` [PC] 1.1.0. `pig-durable` appears here only when the Durable Object product (Wasm core plus a JS host) exists and has passed the contract gate; until then its cell is `cannot run` with that reason, never a native number placed here. A `null` floor is the empty Durable Object.

Shows: Durable Object storage semantics as workerd implements them, the platform's `rowsRead` and `rowsWritten` cursors, object-cold against isolate-cold (K objects staged in one runtime), memory slope per object, and the same workload shape as durable-bench with the runner of our choice. Pin Miniflare (4.20260730.0 and compatibility date 2026-07-30 were used before [DR]).

Cannot show: real eviction timing, code caching across isolates, the 1 s startup limit, network latency, billing, or whether index rows count as in production. workerd's clock advances only at I/O, so time must be taken outside the object [DR]. Storage is a local file.

### 5.3 Real Cloudflare (optional, needs an account)

Needs a Workers Paid account (SQLite-backed Durable Objects, and a free plan's 10 ms CPU per request would distort runs [B1] section 6), a scoped API token kept in a mode-600 file, and a decision on publication (section 9).

Shows: real eviction and hibernation (idle sweeps of the 10 s and 70 to 140 s windows [CFL]), real `rowsRead` and `rowsWritten`, billing analytics against our derived `bill_usd_per_1k_turns`, startup time and Wasm compile on a real isolate, isolate sharing, alarm behaviour, and the 2 MB row limit in practice [CFLim].

Cannot show: class-A hardware, a quiet neighbour, a reproducible CPU. Client time includes the network, so a null Durable Object ping is measured in every round and reported beside each result. Results carry the label `cloud`, are never mixed into native or Miniflare cells, and have no A/A floor in the CPU sense.

Cost of a real run, from the pricing page: at the researcher's 869 rows written per 8-tool turn [B1] section 4.1 (a Miniflare count, not a platform one), 10,000 turns write about 8.7 million rows, which sits inside the 50 million monthly allowance [CFP]. A run's bill is dominated by the plan's minimum. Writes dominate reads, and duration is smaller than both unless a turn lasts about nine minutes, because one row costs $1.00 per million, and a 128 MB object costs $12.50 per million GB-s: $0.00087 of writes per turn equals 543 s of duration. That arithmetic uses the pricing page and the 869 figure and is `[INFERENCE]` about real runs.

## 6. Fairness and correctness gates

Before the first measured sample, `buffon/runner/equivalence.py`'s pattern applies: each arm records a state; the reference is the oracle; a difference refuses the run with exit code 3 and the differing fields; records go to `equivalence.json` [BF equivalence.py].

### 6.1 Same inputs

- **Same scripted model.** A provider-boundary script, written once as data and implemented in each runtime's own provider interface (pi-ai provider in TypeScript, PiG `ai` provider in Go). It looks up the answer by an index in the last user message or tool-result id, so it costs O(1) per call; it reports usage from a counter extended incrementally over appended messages and walks fully only after a compaction or open. This is Mario's design [DBH]: pi's built-in faux provider is not used because its token estimate serialises the whole context on every call. The provider logs every request.
- **Same tool.** `lookup` returns data from the script. A tool written in TypeScript and a tool written in Go must return identical content. PiG's Node sidecar is not used. If a scenario needs a tool PiG cannot host natively, its cell is `cannot run` with the reason.
- **Same transcript fixtures**, generated deterministically (3.5), with the varied twin.
- **Same clock and ids.** Both runtimes take an injected clock (`HarnessOptions.now` and `setTimer` in Pi [PC]). Volatile fields are a short declared list: provider session UUID, `durationMs`, `startedAt` and `endedAt` [PC] 1.1.0.
- **Same settings.** Each runtime at its shipped defaults. Any change is declared in `[env]` or a manifest settings table and recorded as `runtime_settings` [BF METHODOLOGY section 15]. Buffon sets no `GOMAXPROCS`, `GOGC`, `GOMEMLIMIT` or Node options; the CPU set is pinned for both [BF METHODOLOGY section 15].

### 6.2 The equivalence gate

For each fixture size in the plan, each arm runs a short scripted scenario (open, three turns, one compaction when the window is small, a document edit, a child task) and the gate compares:

1. **Conversation state, semantically.** For each conversation, the active transcript as an ordered list of (kind, role, content digest, tool-call ids, stop reason), the document values (parsed JSON, deep equal), task terminal outcomes, submission statuses. Volatile fields are removed by name. Both stores are exported by the runner reading SQLite, not by an arm's API.
2. **Model requests.** The ordered list of requests the scripted provider received: system prompt, messages, tools, and stream options. Equal as parsed JSON.
3. **Compaction boundaries.** The entry ids at which head markers land. Background compaction timing can differ between a goroutine scheduler and Pi's microtask order. If boundaries differ at a size, the row says `different work: not compared` with the reason, using the manifest's divergence mechanism [BF METHODOLOGY section 15]. A blocking variant (`backgroundTokens` 0, declared for both) removes the race and is run beside it. `[INFERENCE]` Whether the race occurs with an instant model is unknown.
4. **Cross-open.** Each runtime opens the other's store and returns the same transcript. Pi-to-Go SQLite cross-reads were done by the `gap-durable` lane [MB] entry "00:44". Pi 1.3.0 opens schema version 1; a Pi build from `main` migrates a store to schema version 2 and 1.3.0 cannot reopen it [PC] Unreleased. Gate runs must use a copy.
5. **Oracle determinism.** Pi against its own A/A copy gives equal state, else the scenario is excluded as flaky [CT] section 5.3 (V11).

Row identity is a reported fact, not a gate: the PiG core targets identical rows and commit grouping (store, commit and context levels in [CT] section 2.1). The runner can diff the two stores' rows byte for byte after the scenario; `row_identical` is `true`, `false` or absent, and a `false` is listed as a run note, not a refusal. The reason: a Pi-compatible runtime may legitimately differ in an unobservable field, and the semantic gate decides whether the timing is of the same work.

### 6.3 Pinning, interleaving, A/A

- Pins: every runtime package and toolchain pinned by sha256 in `arms.lock` (METHODOLOGY section 1). Pi from the npm lock; PiG from a commit and tree with the Go version from `.go-version`; Node, Go, Miniflare, workerd pinned.
- A/A: the reference arm and every arm have a second copy (`<id>-b`) with its own install directory, bundle and compile cache, interleaved in the same rounds. The floor for any difference is the A/A floor [BF METHODOLOGY section 6].
- Interleaving: arms rotate each round per workload (the runner's `rotate`); the first round is warm-up and stays in raw data [BF METHODOLOGY section 5].
- A fresh fixture copy per sample, read once. The cold-start method is named in every report: warm page cache. A `drop_caches` variant is allowed on a dedicated host as its own row [BF METHODOLOGY rule 10].
- Serial: one measured process tree at a time, host lock, quiet gate on the pinned CPUs [BF METHODOLOGY section 5].

### 6.4 Pi's async storage against PiG's synchronous core

The two designs differ by construction, so they are measured only at the shared boundary.

- Both arms are driven through the same public calls: open the harness, get the root conversation, submit, wait for the submission, wait for idle. No arm is timed at an internal hop.
- Pi's storage facade is promise-based; every statement is an await [PD] Storage. PiG's facade is blocking [PG database.go]. Each is measured through its own facade. `floor-sql` shows the facade and driver cost; `floor-host` shows the adapter cost.
- CPU is instructions and cycles of the whole tree, because the Node runtime and the Go collector both use helper threads [DR]. Wall time is shown beside it.
- CPU sets are equal and pinned. The earlier harness found that Go's default parallelism cost a great deal on a large shared host, and that GOMAXPROCS=1 gave different results [DP]. PiG documents its own default, `GOMAXPROCS` unset and capped at min(2, runtime default), and Buffon records it in `runtime_settings` and left it untouched [BF METHODOLOGY section 15]. The report shows the pinned CPU count and notes that at 50 turns PiG lost with the default and tied only with `GOMAXPROCS=1` in the earlier build [B1] section 4.2.
- A cold sample includes first-use costs (JIT for Node, page faults and GC warm-up for both). That is part of cold.

## 7. How it fits Buffon

### 7.1 Arms

An arm here is a runtime package plus a host adapter. The adapter is part of the arm directory, so `arms.lock` hashes it and a change to it changes provenance [BF DASHBOARD "Profiles" on `arms/` hashing]. The ids:

| Arm id | What | Env |
|---|---|---|
| `pi-durable` (reference) | `@earendil-works/pi-durable` 1.3.0, with `pi-ai`, `chord`, `pi-codemode`, `pi-telemetry` 1.3.0 from the committed lock; Node pinned; adapter bundled with esbuild | native, miniflare, cloudflare |
| `pig-durable` | PiG `durable/` at a commit and tree, Go from `.go-version`, CGO off, adapter in Go linking the public `durable` packages | native |
| `pig-durable-do` | The Wasm core plus the JS host, once it passes the contract gate | miniflare, cloudflare |
| `pi-durable-main` (informational) | Pi built from a pinned commit of `main`, schema version 2 | native, miniflare |
| `null-host` | The floor, not an arm in the tables | all |

Version note. Pi 1.3.0 (2026-10-15) is the latest release [PC]. The context-reuse change Mario's `da866ada` carried was released in 1.1.0 [PC] [DB2 / API: commit `da866ada`, 2026-10-06]. So the release already contains it, and the "latest release or main with the fix" choice no longer matters for that fix. `main` adds sleeps, a crash-loop guard and schema version 2, so it is informational. This also matches the reference arm of the other families, `pi-node` at 1.3.0 [BF arms/pi-node/arm.toml]. The external-suites registry still pins Pi 1.1.0 [BF external/suites.py] and needs a bump to stay consistent.

Manifest sketch (not final):

```toml
name = "pi-durable"
label = "Pi Durable 1.3.0 (Node)"
relation = "pi-reference"
version = "1.3.0"

[npm]
package = "@earendil-works/pi-durable"
version = "1.3.0"
integrity = "sha512-..."
package_lock = "install-package-lock.json"
runtime = "node"

[adapter]
protocol = 1
bundle = "adapter/dist/adapter.mjs"      # built from adapter/src, hashed by arms.lock
envs = ["native", "miniflare"]
storage = "sqlite"

[env]
NODE_COMPILE_CACHE = "{install_dir}/node-compile-cache"   # same recorded rule as pi-node

[capabilities]
durable = ["conversations", "documents", "tasks", "compaction", "forks", "subagents"]
```

```toml
name = "pig-durable"
relation = "pi-port"
[source]
repo_env = "BUFFON_SOURCE_REPO_PIG_TIP"
commit = "<40 hex>"
tree = "<40 hex>"
toolchain = "go"
package = "./adapter"
build = ["go", "build", "-trimpath", "-o", "{out}", "{package}"]
[adapter]
protocol = 1
envs = ["native"]
storage = "sqlite"
[capabilities]
durable = ["conversations", "documents", "tasks", "compaction", "forks", "subagents"]
```

The runner needs a new install kind (`[adapter]`), a driver that speaks the protocol, and a variant axis for `env`. These are runner work, not design questions.

### 7.2 What an adapter may and may not do

The adapter speaks a JSON-lines protocol on stdin and stdout: `open`, `turn`, `barrier`, `stats`, `close`, `crash_after`, `resume`, plus `floor` operations. In Miniflare it forwards the same requests to the Durable Object by `dispatchFetch`. The protocol is Buffon's own.

May:
- construct the runtime with the declared settings and the scripted provider and tool;
- open storage through the project's own adapter (`openNodeSqliteStorage`, `openDurableObjectSqliteStorage`, the Go node adapter) wrapped by the counting facade;
- call the public API: open, root, createConversation, submit, wait, waitForIdle, resume, commit, close;
- write the side-effect ledger and answer barriers;
- be small enough to read: about 300 lines for the TypeScript adapter was the aim, and the cap the test enforces is 400 code lines for it and 1,000 for the Go adapter (section 11). The cap is for reviewability; the equivalence gate (6.2) is the fairness control. The adapter is public and meant for review by the project it adapts.

May not:
- keep any cache, index or state that the runtime does not keep (for example hold the transcript, skip a read, batch commits, reuse a context range across processes);
- change the runtime's source, patch a dependency, or set a tuning variable the manifest does not declare;
- read a counter from inside the runtime, or skip the wrapper;
- time itself for any metric the statistics read;
- decide which turn is warm or cold;
- spawn a helper process or thread that does runtime work.

A "kept range across invocations" patch like the bake-off's B2 [BK] is not an arm. Upstream already ships reuse within the Harness [PC].

### 7.3 `raw.json` sample fields

Flat, names end in units [BF RAW-FORMAT]. Identity: `arm`, `scenario`, `env`, `round`, `warmup`. A sample is one fresh adapter process, like a long-session sample.

```json
{
  "arm": "pi-durable", "scenario": "durable/mixed-3500", "env": "native", "round": 3, "warmup": false,
  "fixture_sha256": "...", "fixture_seed": 20261018, "fixture_writer": "pi-durable", "fixture_variant": "repeating",
  "turns": 3500, "window_tokens": 200000, "compaction": "on", "shape": "mixed", "measured_turns": 10,
  "proc_start_ms": 0, "open_ms": 0, "first_turn_ms": 0, "cold_ms": 0, "warm_turn_ms": 0, "warm_net_ms": 0,
  "ttfr_ms": 0, "first_delta_ms": null, "model_ms_per_turn": 0,
  "instructions": 0, "cycles": 0, "cpu_ms": 0,
  "sql_stmts_per_turn": 0, "sql_commits_per_turn": 0, "rows_returned_per_turn": 0, "bytes_returned_per_turn": 0,
  "rows_read_per_turn": null, "rows_written_per_turn": null,
  "wchar_per_turn": 0, "rchar_per_turn": 0,
  "store_bytes": 0, "store_bytes_per_turn": 0, "store_tables": {"entries": 0},
  "peak_rss_mib": 0, "ready_rss_mib": 0, "end_rss_mib": 0, "pss_mib": 0,
  "row_identical": null, "compaction_ids": [], "equivalence": "ok",
  "runtime_versions": {"pi-durable": "1.3.0", "node": "..."},
  "series": {"turn_ms": [], "adapter_turn_ms": []}
}
```

`failure` is set when a sample fails, as for every family. `rows_read_per_turn` and `rows_written_per_turn` exist only where the platform counts. `equivalence.json` in the run directory holds the gate records and digests.

### 7.4 Margins and rounds

Equivalence margins (TOST) in `workloads/margins.toml`: time and CPU follow the existing ±5%; memory ±5% or ±2 MiB [BF METHODOLOGY section 7]. `sql_commits_per_turn`, `rows_written_per_turn` and `store_bytes` are exact, like `*_bytes_per_turn`: they show "same by construction" or reveal the difference. The mixed and compat workloads take the default 12 rounds. Crash and many-conv are special workloads with their own driver, like reliability and scale.

### 7.5 The Durable section of the site

Buffon's site has no score and no ranking. Each section has one tile with a headline metric and a dot plot, and the tile ends with a factual line from the lowest to the highest value [BF DASHBOARD "The hero, the tile line and the spotlight"].

- **Headline:** `warm_net_ms` on `durable/mixed-3500`, ratio to `pi-durable` with its 95% interval, or values. `[INFERENCE]` Net of the floor, because the floor is a property of the host.
- **Tile line:** "from X ms (arm) to Y ms (arm)" on that cell. No "better" or "faster".
- **Charts in the section:**
  1. Line chart: warm turn against history length (log x, 50 to 10,000), two series per arm (compat and mixed), using the extension sweep's Line view and `rungs` mechanism [BF tracks.toml].
  2. Line chart: cold against history length.
  3. Bars: rows read and rows written per turn, then `bill_usd_per_1k_turns`, with the pricing date in the caption.
  4. Line chart: memory per live conversation against N, and per object against K.
  5. Line: store bytes against turns.
  6. A pass or fail grid: crash points by arm, as Reliability shows faults.
  7. Dots and Rounds for every metric, as other sections.
- **Method page:** runtime settings per arm, the gate records, the fixture digests, the floors.
- **Different work:** where the compaction race or a missing capability applies, the label "different work: not compared" with its source.
- Mark every Miniflare cell and every cloud cell with its env, never mixed.

## 8. The project suites

They run unchanged, pinned by commit and file digest, and appear in "External suites", credited as the project's method and the project's numbers. They are never part of a cell, an A/A floor, a tally or a grade [BF EXTERNAL].

| Suite | Owner | What | In Buffon today | Change needed |
|---|---|---|---|---|
| `bench:storage` | Pi | Storage reads, writes, reopen, on memory, SQLite and JSONL, vitest bench [PB] | Registered, pin v1.1.0, target `pi-node` [BF external/suites.py] | Bump pin to the arm's 1.3.0 |
| `BenchmarkStorageRead`, `Write`, `ReopenAndFirstExactRead` | PiG | Port of the above; the same scenario names and the same entry count (1,000) in the timing scale [PG storage_benchmark.go] [PB src/testing/storage-benchmark.ts] | Registered, targets `pig-native`, `pig-tinygo` | Place the two outputs side by side by scenario name |
| `bench:storage:memory` | Pi | Heap, RSS, disk after a seeded dataset, 1k and 10k [PB test/storage-memory.ts] | Registered; no PiG equivalent found | None |
| `bench:tool-output` | Pi | Tool output, progress commits, replay, 1 GiB firehose [PB test/tool-output-bench.ts] | Registered; no PiG equivalent found | None |
| `bench:nested-tools`, `nested-images`, `scheduler-fanout`, `scheduler-memory`, `document-cache`, `document-append`, `codemode` | Pi | Added to the package by 1.2.0 [PC] [PB package.json] | Not registered | Register at the pin |
| durable-bench (clavia-labs, badlogic fork `e9abffab`) | Tardigrade author, Mario Zechner | The workload of section 2, Miniflare | Not registered | See below |
| `harness/` benchmark of that fork | Mario Zechner | Outside Durable Objects, Pi HEAD and Tardigrade [DBH] | Not registered | Same |

Presentation rules:
- Each row names the project, the repository, the commit and the licence. The unit is the suite's own; nothing is renamed or converted [BF EXTERNAL].
- The PiG and Pi storage rows sit beside each other by scenario name. They carry different units (vitest hertz or milliseconds against Go `ns/op`), so Buffon states that they are the two projects' own outputs on two language runtimes and computes no ratio.
- durable-bench, unchanged, runs from a clone fetched at install time and checked by digest, as Pi-Bolt's does [BF EXTERNAL]. It runs on our host for Pi (and Tardigrade if asked). Its published numbers are cited as text with source, host and date. They are not imported: Buffon's rule is that a source whose licence is unclear is cited, not imported [BF EXTERNAL "External results"].
- One calibration line: our unchanged run of durable-bench for Pi against its published figures gives a host factor. The earlier bundle measured about 3x on a shared Xeon [DR]. The factor is the only link between published numbers and Buffon's.
- The PiG storage benchmark's `pig-tinygo` target may fail to build. It is recorded as such, not skipped [BF external/suites.py].

## 9. Risks and open questions for the owner

### Decisions needed

1. **Licence.** durable-bench has no licence (both repositories, API check 2026-10-18). Running it unchanged is allowed; copying its code is not. Options: (a) ask clavia-labs and Mario to add a licence (an issue on each repository), then adopt the exact workload bytes; (b) a clean-room `compat` lane written from the README's public description, with different strings, and labelled "durable-bench shape", not reproduced; its fingerprints will not equal the published ones. Under (b) comparisons with published numbers are by shape and by the unchanged calibration run. `[INFERENCE]` This is not legal advice.
2. **Cloudflare.** An account on Workers Paid, a token on the benchmark host, and permission to publish numbers measured there [B1] section 6 [RK] Q1. Without it, environment 3 does not exist and the Miniflare rows carry "local workerd" in their label.
3. **Which PiG.** The shipped native Go port, the Wasm core for Durable Objects, or both. The owner ruled that no public numbers come from the prototype [MB] 22:20. This design only measures what passes the CONTRACT gate for the Wasm core. The native port is measurable now.
4. **Which Pi Durable version.** Recommendation: the 1.3.0 release as the arm, `main` as an informational arm. The fix of `da866ada` is in every release since 1.1.0 [PC]. Schema version 2 is on `main` only and cannot be rolled back [PC] Unreleased.
5. **Headline.** `warm_net_ms` on `mixed-3500` with compaction on, with compat beside it. The alternative is `cold_ms`. Compat never leads.
6. **Turn-mix weights.** The mix in 3.3 is invented. Supply measured shares (calls per turn, result size) if you have them.
7. **Other runtimes.** Whether Tardigrade enters as a third arm through the same adapter protocol (Buffon invites any harness), and whether comparisons against the benchmark of Tardigrade's author are published [RK] Q7.
8. **Adapter review.** Ask Earendil to review the Pi adapter and the facade wrapper before publication. This is the main defence against adapter bias.
9. **Host class.** A headline needs class A hardware and two sessions [BF METHODOLOGY section 5 and rule 13]. the benchmark host was shared with load 15 to 60 in the earlier runs [DR], so its results would be class B and provisional unless a slot or node is reserved.

### Risks

- **Adapter bias.** Two adapters in two languages can differ in more than the runtime. Controls: size cap, no-cache rule, shared protocol, wrapper conformance test, kernel-level cross-check, `floor-host`, owner review (7.2, 4.3, 4.5).
- **The benchmark flatters PiG if it is the old one.** Compat disables compaction and gives the largest active range, the worst case for a design that rereads history [B1] section 5. The mixed lane exists to test that. The brief's own falsification test: PiG's win is in doubt if Pi with compaction is within about 1.5x on cold and warm [B1] section 5 item 1.
- **Pi keeps moving.** Between 1.0.4 and 1.1.0 the main cause of PiG's lead was removed upstream [PC]. A re-run at each Pi release is part of the plan. `[INFERENCE]` The Pi floor may be near its 50-turn turn time at every size [DR].
- **Fixture bias.** A fixture written by Pi may favour Pi. Twin fixtures (3.5) and `fixture_writer` in each row.
- **Compaction timing diverges.** See 6.2 item 3.
- **Native against Wasm.** `pig-durable` native is not the Durable Object product. Native numbers must not be quoted as Durable Object numbers.
- **Counters differ.** Native has no billing-equivalent rows read (4.3). Miniflare's index-row accounting is unverified [B1] item 9.
- **Dated evidence.** The snapshots in [B1], [B2], [B3] and [MB] are from different builds and moments. None is used as a Buffon result.
- **Buffon's authors also build PiG** [BF LIMITATIONS]. The reference arm is Pi, the gates run against Pi as oracle, and losses are listed first [BF METHODOLOGY section 9].

### What would make PiG look worse than today

These are results to expect and to publish, from the evidence read:

- **Small histories with default parallelism.** At 50 turns PiG tied Pi only with `GOMAXPROCS=1` [B1] section 4.2. With Buffon's pinned CPU set and no tuning, the 50-turn cell may show Pi ahead.
- **Compaction on.** If Pi's re-read shrinks with a bounded window, the gap on warm and cold shrinks. PiG's design hypothesis is flat cold; Pi may be flat too [B1] section 5.
- **Rows written tie by contract.** 869 rows per turn for both [B2] [B1]. Writes dominate the cost on Cloudflare [CFP]. PiG cannot win the dominant line, only reads and duration.
- **Wasm product.** Memory per object and the Wasm floor. At an earlier snapshot, retained memory was 58.9 MB against 13.7 MB for Pi, and four objects exceeded the 128 MB isolate [B2]. Later numbers were 25.9 against 27.9 MB, with four objects at 111 against 79 MB [B3]. Both snapshots are dated and may be stale.
- **Cold CPU.** One snapshot had PiG cold first-turn CPU 1.2x Pi's [B3].
- **Native CPU.** The native build had the best memory and 10x worse CPU until a decode-once fix [B3].
- **Crash order.** 151 of 162 crash points matched Pi's order at the snapshot [B2]. The crash matrix will show any remainder.
- **Tools in TypeScript.** Pi runs TypeScript tools natively; PiG runs them in a Node sidecar. The family's tool is native in both, so this hides a cost PiG users with TypeScript extensions pay. It is stated in the Limits, not measured here.
- **Build quadratic.** The Go history build was quadratic and too slow at 3,500 turns in the earlier build [DR]; `grow` will show it.

## 10. Cost estimate

All estimates are `[INFERENCE]` and built from measured pieces in the bundle and the Buffon docs. benchmark-host-class means the Xeon Platinum 8462Y+ host described in [DR] with CPUs pinned, quiet gate on.

### Unit costs (seconds per sample, both arms averaged, including process start, fixture copy and quiet-gate wait)

| Workload group | Estimate | Basis |
|---|---|---|
| `compat-50/250/1000/3500` | 3, 4, 6, 10 s | Pi main cold 0.4 s and warm 0.15 to 0.18 s at 3,500 on a pinned benchmark-host core [MB] entry "20:47 MDT: DURABLE STEP 2"; PiG about 0.2 s cold and 0.06 s warm in the earlier native build [DP]; one Node start of about 1 s [DR] |
| `compat-10000` | 15 s | Linear extrapolation of the above |
| `mixed-{1000,3500,10000}` | 5, 7, 10 s | Smaller context with compaction on |
| `cold-every-turn` (two sizes) | 30 s | Ten restarts per sample, Node start about 1 s each |
| `stream`, `large-output`, `docs`, `tasks`, `subagent` (about 9 workloads) | 60 s | About 6 to 7 s each |
| `many-conv`, `many-obj` | 80 s | Ladders of N and K, 20 s per rung |
| Miniflare cells (compat four sizes, cold-object, cold-isolate) | 60 s | Miniflare boot about 3 s per sample [INFERENCE] |
| `grow` (3 rounds, no A/A, like scale) | 150 s per size | Pi build 34 s at 3,500 on Mario's host [DBP]; 141 to 176 s on the benchmark host [B2] |

Sum per arm-instance per round for the round-based workloads: about 5 minutes (38 + 22 + 30 + 60 + 80 + 60 s, about 290 s). With two arms, A/A copies (4 instances), 12 measured rounds and 1 warm-up (13 rounds): 52 instance-rounds, about **4 hours**. `grow` adds two sizes times two arms times 3 rounds times 150 s, about 30 minutes. Floors, the equivalence gate and the cross-open check add about 30 minutes. The crash matrix runs once, not in rounds: four orders, about 77 commit points at each of two sizes plus 10 at 3,500, so about 650 runs at 2 to 3 s each, **25 to 35 minutes**. One session: about **5 to 6 hours**.

One-time fixture build, cached by sha256: Pi history build is quadratic with compaction off. 10,000 turns costs about (10,000 / 3,500)^2 times 150 s, roughly 20 minutes. The mixed fixtures and twins add up to 30 to 60 minutes. About **1.5 to 2 hours** once.

A headline needs two independent sessions [BF METHODOLOGY rule 13]: about **9 to 12 hours** of exclusive machine time plus fixtures. Slots on a large host can run sessions side by side if the slot calibration passes [BF METHODOLOGY "Slots on one big host"]. No mock process is needed on the default plane because the model is in-process, so a session uses only the harness CPUs.

Real Cloudflare: wall time of a few hours; money is the plan's minimum, from section 5.3's arithmetic.

### Minimal first run (under one hour)

1. Build the generator and the `compat` and `mixed` fixtures at 1,000 and 3,500 turns (Pi writes them): about 15 minutes.
2. Equivalence gate and cross-open on both fixtures: about 5 minutes.
3. Arms: `pi-durable` 1.3.0 and `pig-durable`, native only.
4. Workloads: `compat-1000`, `compat-3500`, `mixed-1000`, `mixed-3500`, `floor-host`, `floor-sql`.
5. Rounds: 1 warm-up and 6 measured (the sign-flip minimum for one compared arm [BF METHODOLOGY section 18]), A/A on: 31 s per instance-round times 4 instances times 7 rounds, about 15 minutes.
6. Crash matrix at 50 turns, 20 kill points, four orders (80 runs): about 4 minutes.
7. durable-bench unchanged for Pi at 50, 250, 1,000 and 3,500 turns, 3 samples, for the host factor: about 10 minutes.

Output: cold and warm net against history for both arms and both lanes, rows and bytes per turn, store bytes, memory, the crash pass grid, and the host factor. It answers the first question: does PiG's lead survive compaction on and a realistic mix.

## 11. What is built (Phase 1, native)

The protocol, the script format, the counting facade and the rules for adapters are written in [DURABLE-ADAPTERS.md](../DURABLE-ADAPTERS.md); how to run the family is in [RUNNING.md](../RUNNING.md), "The durable family". Where the build differs from the design above:

- **Arms.** `pi-durable` (Pi Durable 1.3.0 on Node, the reference; adapter bundled with esbuild from a committed npm lock) and `pig-durable` (PiG's `durable/` packages at a pinned commit and tree, built with CGO off inside the checkout with the adapter copied in). `pi-durable-main` (Pi built from main at the commit PiG pins, storage schema 2) is informational, runs only when named and is never the reference. `null-host` is not an arm: it is the adapter's floor mode (`durable/floor-host`, section 8 of the adapter document), run by each arm.
- **Adapter size.** The TypeScript adapter is about 350 code lines, the Go adapter about 1,000. Section 7.2 asked for about 300 per arm; the Go port needs more glue for the same protocol, and the cap in the test (400 and 1,000) is for reviewability while the gate is the fairness control. The Method page lists the size of each part.
- **Storage schema.** Pi 1.3.0 writes storage schema version 1. PiG pins a Pi main whose migration 2 adds the `sleeping` task status, so PiG writes version 2, reads 1 and 2, and migrates a version-1 fixture on open. Pi 1.3.0 cannot open a version-2 store, so the cross-open check runs Pi to PiG and records PiG to Pi as not possible, with that reason; the crash matrix lists the orders that need it the same way. Row identity (`row_identical`) is read on the tables both versions share.
- **Order of parallel tool results.** When one round has several tool calls, each result commits as its tool finishes: Pi in the order of the calls (microtask order), Go in the scheduler's order. The gate compares a round's results in a canonical order (and every reference to them), so two runs that made the same calls and stored the same results are the same work; the stored order is a run note.
- **Counters.** Statements are counted by kind (read, write, DDL, pragma); the facade does not count the statements a `barrier` issues. PiG's working set issues `PRAGMA data_version`, which Pi does not, so the pragma count is listed apart in the report.
- **Gate.** A fixture is gated by the scenarios `base` (three turns), `compaction` (an 8,000-token window), and once `documents`, `tasks` and `subagent`; the blocking variant (`background_tokens` 0) runs only where compaction boundaries differ. A capability an arm lacks becomes the workload's `cannot run` reason; boundaries that differ and agree when blocking become a divergence for that arm at that fixture (the manifest mechanism), computed at run time.
- **Fixtures.** Built by the reference through its real loop, cached under the site's cache directory by the sha256 of the script, the fixture's settings and the writer (arm, version, adapter digest), copied per sample and read once. `fixture_sha256` is the script's digest and `fixture_store_sha256` the store's.
- **Not yet built.** `durable/many-obj-{1,8,32}` (needs the Miniflare environment), the Miniflare and Cloudflare environments, `pig-durable-do`, tardigrade, the billing metrics (`bill_usd_per_1k_turns`, `do_gb_s_per_turn`), `rows_read`/`rows_written` in Cloudflare units, a `drop_caches` variant. The environment is a variant axis (`env`: native today; `miniflare` and `cloudflare` are refused with that reason).

## Sources

Keys used above. Local paths are the owner's files; web pages were read 2026-10-18.

- [B1] `~/PiG-launch-newer/DURABLE-RESEARCHER-BRIEF.md` (2026-10-06).
- [B2] `~/PiG-launch-newer/DURABLE-BREAKTHROUGH-BRIEF.md` (2026-10-09 snapshot).
- [B3] `~/PiG-launch-newer/DURABLE-RESEARCH-BRIEF-2.md`.
- [BK] `~/PiG-launch-newer/durable-researcher-bundle/docs/plan/durable-core/BAKEOFF.md`.
- [CT] `.../durable-core/CONTRACT.md`. [RK] `.../durable-core/RISKS-AND-QUESTIONS.md`.
- [DR] `~/PiG-launch-newer/durable-researcher-bundle/bench/durable/README.md`.
- [DP] `~/PiG-launch-newer/durable-researcher-bundle/bench/durableperf/README.md`.
- [MB] `~/PiG-launch-newer/MORNING-BRIEF.md`, by timestamp.
- [SC] `~/PiG-launch-newer/SECOND-COORDINATOR-NOTES.md`.
- [DB1] https://github.com/clavia-labs/durable-bench (README; no licence in the GitHub API).
- [DB2] https://github.com/badlogic/durable-bench (README, `src/plan.ts`, `src/pi-head.ts`, `src/serve.ts`, `bench/run.ts`, `bench/targets.ts`), latest commit `e9abffab`, 2026-10-06.
- [DBH] https://raw.githubusercontent.com/badlogic/durable-bench/main/harness/README.md.
- [DBP] https://raw.githubusercontent.com/badlogic/durable-bench/main/pi-vs-tardigrade/README.md.
- [PD] https://github.com/earendil-works/pi/blob/main/packages/durable/README.md.
- [PC] https://raw.githubusercontent.com/earendil-works/pi/main/packages/durable/CHANGELOG.md. [PS] `packages/durable/docs/spec.md` section 11.2.
- [PB] `packages/durable/package.json` scripts, `test/storage.bench.ts`, `test/storage-memory.ts`, `test/tool-output-bench.ts`, `src/testing/storage-benchmark.ts` in the same repository.
- [PA] https://earendil.com/posts/pi-durable/ (2026-10-01).
- [CFP] https://developers.cloudflare.com/durable-objects/platform/pricing/ (updated 2026-10-18).
- [CFA] https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/.
- [CFL] https://developers.cloudflare.com/durable-objects/concepts/durable-object-lifecycle/.
- [CFLim] https://developers.cloudflare.com/durable-objects/platform/limits/.
- [PG] `~/PiG/durable/` (`doc.go`, `storage/sqlite/database.go`, `storage/storage_bench_test.go`, `durabletest/storage_benchmark.go`) and `~/PiG/CHANGELOG.md`.
- [BF] This repository: `docs/METHODOLOGY.md`, `docs/WHAT-WE-MEASURE.md`, `docs/RAW-FORMAT.md`, `docs/EXTERNAL.md`, `docs/LIMITATIONS.md`, `docs/design/DASHBOARD.md`, `docs/design/SCALE.md`, `workloads/tracks.toml`, `arms/pi-node/arm.toml`, `buffon/runner/equivalence.py`, `buffon/fixtures/sessions.py`, `buffon/external/suites.py`, `buffon/workloads/__init__.py`.
- [API check] GitHub REST API `GET /repos/{clavia-labs,badlogic}/durable-bench` (license: none) and `GET /repos/earendil-works/pi/commits/da866ada` (2026-10-06, "keep each conversation's context in memory; Durable Object SQLite adapter"), read 2026-10-18.
