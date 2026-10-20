# Durable adapters: the protocol

An arm of the `durable` family is a runtime package plus a small host adapter ([design/DURABLE.md](design/DURABLE.md), sections 7.1 and 7.2). The adapter is a program the runner starts once per sample. It speaks JSON Lines on stdin and stdout, drives the runtime through the runtime's public API and nothing else, and answers the runner's operations one at a time. This page is the contract: the protocol (version 1), the script the scripted model plays, the counting facade, crash injection, the floor operations and the rules an adapter keeps. The runner's side is `buffon/durable/`; the two adapters are `arms/pi-durable/adapter/` (TypeScript, bundled with esbuild) and `arms/pig-durable/adapter/` (Go).

Wording: MUST and MAY have their usual meaning. Sizes are bytes. Times from the adapter are monotonic nanoseconds (`mono_ns`) and are never read by the statistics except where this page says so.

## 1. Process

- Command line. `adapter --version` prints one JSON line, `{"adapter": "<arm id>", "protocol": 1, "version": "<runtime version>", "runtime_versions": {...}}`, and exits 0. With no argument the adapter serves the protocol until stdin closes.
- Environment. The runner gives a scrubbed environment: `HOME`, `TMPDIR` and the XDG variables point into a throwaway directory. No tuning variable is set (no `GOMAXPROCS`, `GOGC`, `GOMEMLIMIT`, `NODE_OPTIONS`). The adapter MUST NOT set one either.
- Working directory. The sample directory. All paths in requests are absolute.
- First line. Before it reads a request the adapter writes one line, the ready event:
  `{"event": "ready", "protocol": 1, "adapter": "pi-durable", "env": "native", "pid": 123, "mono_ns": 1234567890, "runtime_versions": {"pi-durable": "1.3.0", "node": "v24.19.0"}}`.
  The runner's `proc_start_ms` is exec to the receipt of this line. `mono_ns` is the adapter's monotonic clock at the moment of writing; the runner compares it with its own clock at receipt and uses adapter timestamps (`ttfr_ms`, `first_delta_ms`) only when the two clocks agree to within 5 ms. Nothing else is read from it.
- Stderr is free text for people. The runner keeps its tail for failures.
- One request is in flight at a time. The adapter reads a line, does the work, writes one response line. Unsolicited lines are events (`"event"` key) and appear only where this page says so.

## 2. Messages

Request: `{"id": 7, "op": "turn", ...}`. Response: `{"id": 7, "ok": true, ...}` or `{"id": 7, "ok": false, "error": "text"}`. An operation or option the runtime cannot do answers `{"id": 7, "ok": false, "unsupported": "reason"}`: the reason is a sentence the report prints as the cell's `cannot run` reason, so it names the capability and why (for example "the Go port has no subagent ownership"). Never answer `ok: true` for work that was not done.

All integers are JSON numbers; values above 2^53 are not used.

## 3. Operations

### `open`

```json
{"op": "open", "store": "/abs/store.sqlite", "script": "/abs/script.json", "ledger": "/abs/ledger.txt",
 "mode": "runtime", "conversations": 1, "create": false,
 "window_tokens": 200000, "compaction": {"enabled": true, "background_tokens": null},
 "partial_interval_ms": null, "summary_fails": false,
 "request_log": null, "capture": null}
```

- Opens the SQLite file through the project's own storage opener (`openNodeSqliteStorage`'s `NodeSqliteDatabase`, Chord's Go node driver) **wrapped by the counting facade** (section 6), builds the harness with the scripted provider and the tools of section 5, and returns.
- `store`: the database file. `create: true` means the file does not exist yet (a fixture build, a grow run, a floor run); otherwise it is an existing store and the adapter opens it as it is.
- `conversations`: how many conversations the adapter should hold handles for. With `create: true` it creates them (conversation 0 is the root, the others are `createConversation` with `ownership: ownerless`). Without `create` it opens the first N conversations the store holds that no task owns, in id order (the root first; a subagent's child conversation is task-owned and is skipped). The response lists their ids.
- `window_tokens`: the scripted model's `contextWindow`. `compaction.enabled`: `false` turns the runtime's automatic compaction off (the compat lane). `background_tokens`: `null` leaves the runtime's shipped value; a number sets it (`0` is the blocking variant of the gate). Every other setting stays at the runtime's shipped default and the adapter MUST NOT pass one that is not in this request. `partial_interval_ms`: `null` is the shipped 100; a number sets both `progress.partialIntervalMs` and `progress.outputIntervalMs`.
- `summary_fails`: the scripted model fails every compaction summary request (the `compaction-fail` workload).
- `request_log`: a path or `null`. When set the provider appends one line per model request in the form of section 4.4.
- `capture`: a path or `null`. When set the facade appends one line per statement, section 6.3.
- `ledger`: the side-effect ledger file, section 7.
- `mode`: `"runtime"` (the durable runtime) or `"floor"` (section 8).
- Response: `{"ok": true, "conversations": [1, 2, 3], "settings": {...}}` where `settings` echoes what the adapter set (the declared settings, nothing it read from the runtime's internals).
- The runtime MAY open lazily (Pi does): the first `turn` then pays for reading history. That is the measured behaviour. The adapter MUST NOT force a read to make `open` look cheaper or dearer.

### `turn`

```json
{"op": "turn", "conv": 0, "n": 3500, "request_id": "t3500"}
```

One turn: submit the user message of script turn `n` as an `input` submission to conversation `conv` with `requestId` equal to `request_id`, wait for the submission to settle, wait for the conversation to go idle. This is durable-bench's `turn()` and is the only timed unit.

- A `request_id` that already names a submission returns the existing submission (the runtime's exactly-once rule); the adapter does nothing special.
- Response: `{"ok": true, "status": "done"|"unanswered", "reason": null|"text", "submission": 4711, "adapter_ms": 12.3, "first_request_mono_ns": 123, "first_delta_mono_ns": null, "delta_seen_mono_ns": null, "model_ns": 456, "requests": 2}`.
  - `status` is the submission's settled status.
  - `first_request_mono_ns`: the adapter's monotonic clock when the scripted provider received its first request of this turn. `first_delta_mono_ns`: when the provider emitted its first stream delta of the turn; `delta_seen_mono_ns`: when a subscriber of the runtime (`watch` or `viewState`) first saw that delta committed (it lags the emission by up to the partial interval). Both are `null` unless the script turn streams (section 4.3), because watching costs; the adapter subscribes only when `stream` is true in the request (`{"stream": true}`).
  - `model_ns`: total time spent inside the scripted provider in this turn (adapter clock). `requests`: model requests the provider answered.
  - `adapter_ms` goes to `series.adapter_turn_ms` and is never read by a statistic.
- Turn `n` must exist in the script, else `{"ok": false, "error": "script has no turn n"}`.

### `barrier`

`{"op": "barrier"}`. Returns once the harness has no pending work (no submission in flight, no task running, no open transaction) and writes `{"ok": true, "commits": 1234}`: the facade's cumulative commit count since `open`. The runner reads CPU and I/O counters at a barrier, so a counter is never read mid-commit. A background compaction that is still running is pending work: the barrier waits for it. A barrier on a freshly opened store, before any `turn` or `resume`, does nothing and never starts the scheduler. The statements a barrier itself issues (a runtime may inspect storage to see whether it is idle) are not counted by the facade: the adapter pauses counting while it handles `barrier`, so the counters describe the measured work only.

### `stats`

`{"op": "stats", "reset": true}`. Returns the counters of the facade and the provider since `open` (or since the last `reset`) and, with `reset`, zeroes them:

```json
{"ok": true, "sql": {"stmts": {"select": 0, "insert": 0, "update": 0, "delete": 0, "ddl": 0, "pragma": 0, "other": 0},
                     "commits": 0, "rollbacks": 0, "params_bytes": 0, "rows_returned": 0, "bytes_returned": 0},
 "provider": {"requests": 0, "model_ns": 0}}
```

The adapter never reports a counter the runtime keeps (no storage-internal statistics); every number comes from the facade or the scripted provider.

### `transcript`

`{"op": "transcript", "conv": 0}`. Returns `{"ok": true, "messages": [...]}`: the model-visible context of the conversation as the runtime would send it with its next request, in the reduced form of section 4.4, read through the runtime's public API. The cross-open check runs it on one runtime's store opened by the other.

### `doc_edit`

`{"op": "doc_edit", "conv": 0, "count": 100, "payload_bytes": 88, "from": 0}`. Commits `count` edits of an application document (`bench.notes`, conversation scope, `history: "rewindable"`), one commit each. Edit `i` appends the string at script position `from + i` of `script.docs` (a list of fixed strings of `payload_bytes` bytes) to the document's `items` array. The document is defined by the adapter in the runtime's own way and has the same JSON shape in both runtimes: `{"items": ["..."]}`.

### `close`

`{"op": "close"}`. Closes the harness and the storage cleanly (the runtime's `close`) and returns the final `stats`, as the response of `stats` without `reset`. The process stays up until stdin closes; the runner then exits it.

### `crash_after`

`{"op": "crash_after", "k": 12}`. Arms the facade (section 7): after the k-th commit *counted from this call* has returned, the adapter writes the event line `{"event": "crashing", "commit": <cumulative commit count>, "k": 12}` synchronously and sends itself SIGKILL. The response `{"ok": true}` comes at once.

### `resume`

`{"op": "resume"}`. Calls the runtime's `resume()` (start the scheduler and continue any run the last process left unfinished), then waits for idle as `barrier` does. Response: `{"ok": true, "commits": n}`. A `turn` with the same `request_id` that was interrupted then returns the existing submission, which the runtime finishes.

### Floor operations

`open` with `"mode": "floor"` opens the same store through the facade and builds *no* runtime. Then:

- `turn` with the same request as above runs the floor path of section 8.
- `{"op": "floor_sql", "stream_file": "/abs/stream.jsonl", "from_turn": 3500, "turns": 10}` replays the recorded statement stream of turns `from_turn .. from_turn + turns - 1` through the facade and the project's own database driver, one transaction per recorded transaction (a statement recorded with `tx` 0 runs on its own), and returns `{"ok": true, "stmts": n, "commits": m, "per_turn_ns": [..]}`; `commits` is the facade's commit count, as `stats` reports it. The store must be in the state the capture started from (a copy of the fixture, before those turns): replaying over a store that already holds the turns fails with a constraint error.

## 4. The script and the scripted model

### 4.1 The script file

One JSON document (UTF-8, `generator` field names the writer: `buffon-durable-script/1`). It holds a set of turns, not necessarily all of a conversation's: a script given to an adapter holds the turns the adapter will drive (a fixture's own turns are in its store already). Turns are looked up by their number `n`, never by position.

```json
{"format": "buffon-durable-script/1", "seed": 20261018, "variant": "repeating", "shape": "mixed",
 "tool": {"name": "lookup", "description": "Look up a stored record by key.",
          "parameters": {"type": "object", "properties": {"k": {"type": "string"}}, "required": ["k"], "additionalProperties": false}},
 "summary": {"text": "..."},
 "docs": ["88-byte string", "..."],
 "turns": [
  {"n": 3500, "user": "[t3500] Please check the build output.", "shape": "tools",
   "rounds": [
     {"text": "", "calls": [{"id": "c3500.0.0", "name": "lookup", "args": {"k": "c3500.0.0"}, "result": "256 bytes of text"},
                            {"id": "c3500.0.1", "name": "lookup", "args": {"k": "c3500.0.1"}, "result": "..."}]},
     {"text": "The final answer.", "calls": []}],
   "stream": {"chunks": 1, "total_ms": 0}}
 ]}
```

- `user` always begins with the marker `[t<n>] `. A subagent's input begins with `[s<n>.<r>.<j>] `.
- A round is one model response: `text` (may be empty), `calls` (zero or more). The last round of a turn has no calls. A round with calls stops with `toolUse`, the last with `stop`.
- A call is `{id, name, args, result}`. `id` is `c<n>.<r>.<j>`. `args` is `{"k": id}` for `lookup` and `effect`, `{"k": id, "n": 8}` for `fanout`, `{"k": id}` for `subagent`. `result` is the tool's output text: the tool returns exactly this.
- A `subagent` call also has `sub`: `{"user": "[s<n>.<r>.<j>] ...", "rounds": [{"text": "...", "calls": []}]}`, the child conversation's one turn (text only), and its `result` is the text the tool returns to the parent.
- `stream`: how the round's text is delivered, applied to every round of the turn. The text is cut into `chunks` pieces by Unicode code point (chunk `c` is code points `c*L/chunks` up to `(c+1)*L/chunks`, `L` the number of code points, integer division) and emitted as that many text deltas: the first at once, then one every `total_ms / (chunks - 1)`, so the last lands `total_ms` after the first. `chunks` 1 and `total_ms` 0 is an instant, unstreamed answer with one delta.
- `docs`: the strings `doc_edit` appends.
- `summary.text`: the answer to every compaction summary request.

### 4.2 Finding the answer in O(1)

The provider looks at the last message of the request:

- a user message whose text starts with `[t<n>]`: turn `n`, round 0;
- a user message starting `[s<n>.<r>.<j>]`: the subagent's child turn, round 0 of `calls[j].sub`;
- a tool-result message with `toolCallId` `c<n>.<r>.<j>`: turn `n`, next round `r + 1` (several results at the end of the context all name the same round);
- anything else: if the request is a compaction summary request (the adapter recognises it from the runtime's own summary prompt) the answer is `summary.text`; otherwise the provider answers with an error `stopReason` and the message `scripted model: no script entry`.

No lookup scans the context. The provider's only O(context) work is the usage counter below, and only when the counter cannot be extended.

### 4.3 Usage

Each answer carries `usage = {input, output, cacheRead: 0, cacheWrite: 0, totalTokens: input + output, cost: zeros}`.

- Bytes of a message: the sum of the UTF-8 lengths of its text blocks; for an assistant message also, per tool call, the UTF-8 length of `name` plus the UTF-8 length of `id`; for a system message also, per name in `toolsAdded`, the UTF-8 length of the name. Images and thinking do not occur.
- `input` = ceil(total bytes of the request's messages / 4) plus ceil(length of the system prompt text / 4) when the runtime passes one separately. `output` = ceil(bytes of the answer / 4). This is Buffon's mock rule (one token per 4 bytes).
- Other fields of a message (a system message's `sections`, timestamps, usage) are not counted.
- The counter is incremental per `sessionId`: it keeps `{count, first, last, bytes}` for the previous request of that session, where `first` and `last` are `(role, message bytes)` of the first and last message, by the byte rule above. If the new request has at least `count` messages and its message `count - 1` and message 0 match `last` and `first`, the counter adds only the messages from `count` on. Otherwise it walks the whole context (after an open, after a compaction). The state is updated on every request of the session, summary requests included, so the request after a compaction walks the whole context. Both adapters implement this rule identically.

### 4.4 The request log and the reduced form

A message's text is the concatenation of its text blocks. When `request_log` is set, the provider appends one JSON line per request:

```json
{"seq": 0, "kind": "turn", "system": {"n": 120, "h": "<sha256 of the text>"},
 "messages": [{"r": "user", "n": 40, "h": "<sha256>", "p": "[t3500] Please che"}, ...],
 "tools": [{"name": "lookup", "description": "...", "parameters": {...}}],
 "options": {"max_tokens": null, "temperature": null, "reasoning": null, "cache_retention": null, "has_session_id": true}}
```

`kind` is `turn` or `summary`. `system` is the system prompt the runtime passes to the provider separately; a runtime that passes none (Pi puts it in the transcript as a system message) logs `{"n": 0, "h": "<sha256 of the empty string>"}`, in both adapters. A message is reduced to its role and a digest of its text so that logs stay small and equal logs mean equal content:

- user: `{"r": "user", "n": bytes, "h": sha256 hex of the text, "p": first 24 characters}`
- assistant: `{"r": "assistant", "n": bytes of text, "h": ..., "p": ..., "c": [{"id": "c1.0.0", "n": "lookup"}], "s": "stop"|"toolUse"|...}`; `c` is always present (`[]` when the message has no call)
- tool result: `{"r": "tool", "id": "c1.0.0", "n": ..., "h": ..., "p": ..., "e": false}`
- system message in the transcript: `{"r": "system", "n": ..., "h": ..., "p": ..., "add": [tool names], "rem": [tool names]}`; `add` and `rem` are always arrays

`p` is the first 24 code points of the text. `n` is the byte rule of 4.3 minus the call and tool-name parts: the UTF-8 length of the text.

`tools` is sorted by name; `parameters` is the JSON Schema object the adapter passes, identical in both adapters. `options` reports the stream options the runtime passed (`null` where absent). `transcript` returns the same reduced messages. The gate compares logs and transcripts as parsed JSON.

## 5. The tools

All four are defined by the adapter with the runtime's own tool definition API and return exactly the script's `result`.

| Tool | Replay | What it does |
|---|---|---|
| `lookup` | `safe` | Returns `result` of the call. Appends `lookup <id>` to the ledger. |
| `effect` | not safe | Appends `effect <id>` to the ledger, then returns `result`. Used by the crash workloads. |
| `fanout` | `safe` | Creates `args.n` child tasks (one trivial task kind, `bench.child`, that completes in its first phase), waits for all of them (`allSettled`), returns `result`. |
| `subagent` | `safe` | Creates a child conversation owned by the calling task, submits `sub.user` with `requestId` `subagent:<task id>`, waits, returns `result`. |

The tool description and schema of `lookup` are the script's `tool`; the other three use the fixed descriptions `"Apply an effect."`, `"Run child tasks."`, `"Delegate to a subagent."` and the same one-property schema (`fanout` adds integer `n`). An adapter that cannot host a tool answers `unsupported` at `open` or at the first `turn` that calls it, naming the capability.

## 6. The counting facade

Both runtimes define the same `SqliteDatabase` interface (`exec`, `run`, `get`, `all`, `transaction`, `close`). The adapter wraps the project's own database object with a wrapper that implements the interface, forwards every call and counts. The wrapper is adapter code, written once in TypeScript and once in Go, and a test feeds both the same statement stream and compares the counters.

### 6.1 What is counted

- Statement kind: the first word of the SQL text, upper-cased: `SELECT` and `WITH` are `select`; `INSERT` and `REPLACE` are `insert`; `UPDATE`; `DELETE`; `CREATE`, `ALTER`, `DROP` are `ddl`; `PRAGMA`; anything else (`BEGIN`, `COMMIT`, `SAVEPOINT`, ...) is `other`. A call to `exec` is one statement of the kind of its first word, whatever it contains.
- `commits`: a `transaction` call whose callback resolved and committed, plus an autocommit write (`run` or `exec` of kind insert, update, delete or ddl) made outside a transaction. `rollbacks`: a `transaction` call that rolled back.
- `params_bytes`: the sum over bound parameters: string, UTF-8 length; number or bigint, 8; null, 0; byte array, its length.
- `rows_returned`: rows `all` returned plus 1 for each `get` that found a row. `bytes_returned`: the sum over returned rows of the same per-value rule as `params_bytes` (column names are not counted).

### 6.2 Where it sits

Between the storage core and the project's driver: `SqliteStorage.open(wrapper, ...)` in Pi, `sqlite.Open(wrapper, ...)` in Go. A transaction handle the callback receives is wrapped too, so statements inside a transaction are counted. The wrapper keeps no cache and changes no result.

### 6.3 Capture

With `capture` set, each statement is appended as one JSON line before it runs: `{"tx": 17, "turn": 3501, "sql": "...", "params": [...]}` where `tx` numbers transactions from 1 (0 outside a transaction), `turn` is the script turn being driven (set by the `turn` handler; `null` outside one), and a parameter is a JSON string, number or null, or `{"b64": "..."}` for bytes and `{"i": "123"}` for a bigint above 2^53. Capture exists so one reference run can record the stream that `floor-sql` replays on each side.

## 7. Crash injection and the ledger

- The facade counts commits. `crash_after` arms a countdown; when the k-th commit returns the facade writes the `crashing` event (synchronously, flushing stdout) and sends the process SIGKILL (`process.kill(process.pid, "SIGKILL")`, `syscall.Kill(os.Getpid(), syscall.SIGKILL)`). Nothing else in the adapter runs after the commit returns.
- Because SQLite is in WAL mode with `synchronous = NORMAL`, a commit that returned survives the kill of the process.
- The ledger is a text file the tools append to with one `write` of one line (`lookup c1.0.0\n`, `effect c1.0.0\n`), opened in append mode and closed each time (no buffering). It is written outside the database so the runner can see what ran even when the runtime does not remember.

## 8. The floor

`mode: "floor"` is the host with no durable runtime (`durable/floor-host`). The floor `turn` does, for the script turn `n`:

1. for each round of the turn, in order: build the request context the runtime would have sent, as a list of the turn's messages so far, and call the scripted provider directly (the same provider object, the same request log and usage rules), consuming the stream to its end;
2. for each call of the round, run the tool the same way the runtime would (the tool's execute function, the ledger append);
3. per round, one transaction of exactly four statements through the facade: three `INSERT INTO floor_turns (turn, round, k, payload) VALUES (?, ?, ?, ?)` (the table is created at `open`) and one `SELECT count(*) FROM floor_turns WHERE turn = ?`.

It stores nothing else, keeps no conversation and builds no harness. Its time is the cost of the process, the protocol, the provider, the tools and the facade; `warm_net_ms` subtracts it.

## 9. Rules for an adapter

May:
- construct the runtime with the declared settings and the scripted provider and tool;
- open storage through the project's own opener, wrapped by the counting facade;
- call the public API: open, root, createConversation, submit, wait, waitForIdle, resume, commit, close, and the document and task definition APIs;
- write the ledger and answer barriers;
- be small enough to read: the size cap is for reviewability, the equivalence gate is the fairness control. The test (`tests/test_durable_adapters.py`) fails above 400 code lines for the TypeScript adapter and above 1,000 for the Go adapter (gofmt'd; blank lines and comment-only lines, including one-line `/* */` and `/** */` comments, are not counted). Error handling is the language's plain one. The adapter is public and meant for review by the project it adapts.

May not:
- keep any cache, index or state the runtime does not keep (hold the transcript, skip a read, batch commits, reuse a context range across processes);
- change the runtime's source, patch a dependency, or set a tuning variable the manifest does not declare;
- read a counter from inside the runtime, or skip the wrapper;
- time itself for any metric the statistics read;
- decide which turn is warm or cold;
- spawn a helper process or thread that does runtime work.

`buffon/durable/` and `tests/test_durable_adapters.py` check what can be checked: the size cap, no child process of the adapter at ready, the facade's conformance on one statement stream, and the protocol on a scripted conversation.
