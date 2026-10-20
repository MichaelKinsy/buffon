# Raw format

Every session leaves a run directory. Two files are the raw record; a report is generated from them and nothing else.

| file | content |
|---|---|
| `raw.json` | the run: what was asked, what ran, every sample, what was skipped. Validated when written and when read (`buffon/runner/raw.py`). |
| `facts.json` | the facts of the machine or pod the session ran on: CPU model and flags, kernel, cpuset, pinning, governors and clocks, SMT, cgroup limits and throttling, load and idle before and after, runner commit and tree. |
| `equivalence.json` | a run with `durable/*` workloads only: the records of the equivalence gate (fixtures built, the requests and state digests of each arm for each gate scenario, cross-open results, differences), see "`durable/*` samples". The dashboard copies it with the run's other files. |
| `raw.partial.json` | the same shape as `raw.json`, rewritten while the session runs; removed when the session finishes. |

The shape is the one current shape. There is no version field and no reader for any other shape: the runner and the report change together.

One exception: `kind` is `buffon-run` in new runs, and the reader also accepts `arena-run`, the value runs published before the project was renamed carry. Nothing else in the files changed with the rename.

## `raw.json`

```json
{
  "kind": "buffon-run",
  "run":        { "started_utc": "...", "finished_utc": "...", "command": ["buffon", "session", "..."], "seed": 20261011,
                  "workloads": ["overhead/print"], "arms": ["pi-node"], "aa": "all", "rounds": 12, "warmup": 1,
                  "apis": ["openai-completions"], "pinning": "required", "reference": "pi-node", "harness_cpus": [2, 3], "mock_cpus": [1], "params": {} },
  "site":       { "name": "...", "backend": "local", "hardware_claim": "dedicated" },
  "hardware":   { "class": "provisional", "quiet_dedicated": false, "reasons": ["CPUs 2-3 were busy with other work before the run (up to 44%)"] },
  "lock_sha256": "...",
  "runner":     { "commit": "...", "tree": "...", "dirty": false, "diff_sha256": null },
  "arms":       { "pi-node": { "version": "<version>", "executable_sha256": "...", "artifact_sha256": "...", "twin_of": null, "runtime_settings": { "env": { "NODE_COMPILE_CACHE": "{install_dir}/node-compile-cache" }, "left_default": ["GOMAXPROCS", "..."], "source": { "NODE_COMPILE_CACHE": "manifest" } }, "divergences": [] }, "pi-node-b": { "twin_of": "pi-node" } },
  "calibration": { "arm": "pi-node", "metric": "cpu_ms", "runs": 12, "cv": { "pi-node": 0.019 }, "max_cv": 0.019, "gate": 0.05, "passed": true, "samples": [] },
  "egress":     { "mode": "socket-audit", "source": "proc", "violations": [] },   // source "lsof" on macOS; mode "none" when the platform has neither (PROVISIONAL, refused by verify)
  "isolation":  { "pi-node": { "set": { "HOME": "<work>/..." }, "scrubbed": ["..."] } },
  "samples":    [ { "arm": "pi-node", "scenario": "overhead/print", "api": "openai-completions", "round": 3, "warmup": false, "cpu_ms": 719.7, "wall_ms": 636.9 } ],
  "skipped":    [ { "arm": "omp", "scenario": "overhead/rpc", "api": "openai-completions", "reason": "..." } ],
  "ok": true
}
```

`ok` is false when the run was refused, an egress violation occurred, or an executable changed during the run. A run refused by the calibration gate (exit 3, only with `--require-class A`) still writes raw.json: `samples` is empty, `calibration` holds its samples, and an extra key `refused` holds the reason.

`run.slot` is present only for a session that ran in one slot of a host that runs several at once (METHODOLOGY section 5, "Slots on one big host"): `{ "id": 2, "of": 4, "cpus": "8-15", "calibration": "<path of slots-calibration.json>" }`. `cpus` are the slot's harness CPUs. `calibration` is the file that passed this slot, or null when none was given or it did not pass the slot (the trust badge then says `slotted`). `run.lock_file` is then the slot's own lock.

`run.synthetic`, a sentence, is present only on invented sample data (tests/report_demo.py writes it). No runner writes it. `buffon dashboard` puts a DEMO banner on every page of a site built from a run that carries it.

### `arms[<id>].runtime_settings` and `arms[<id>].divergences`

`runtime_settings` records the runtime tuning of an arm, from its manifest:

- `env`: the tuning variables the manifest's `[env]` sets (GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL, any BUN_*), with the value as written in the manifest (`{install_dir}` and the like unexpanded, so no host path).
- `left_default`: the known variables above (not the BUN_ prefix) left at the harness's own default.
- `source`: for each variable of `env`, `"manifest"` or `"buffon"`. Buffon sets no tuning variable of its own and pins CPUs only, so every source is `"manifest"` today.

A variable is in `env` or `left_default`, never both. `buffon verify` and every reader refuse a malformed record. A harness writer may not set a tuning variable the manifest does not name: the harness refuses to start.

`divergences` copies the manifest's `[[divergence]]` tables: `workloads` (globs of workload ids), optional `metrics` (globs, absent or empty means every metric), `reason` and `source` (a URL or a repository document). The report leaves an arm uncompared in the cells they select (METHODOLOGY.md section 15). A run written before these two fields has neither, and the report reads it as an arm with no divergences.

### `samples[]`

A sample is one fresh process of one arm. The record is flat: identity keys, then one key per metric.

| key | type | meaning |
|---|---|---|
| `arm` | string | arm id; an A/A copy is `<id>-b` and also carries `twin_of` |
| `scenario` | string | workload id, `family/name` |
| `api` | string or null | wire API of the variant (`openai-completions`, `anthropic-messages`, `openai-responses`) |
| `round` | integer >= 0 | the interleaved round |
| `warmup` | boolean | warm-up samples stay in the raw data and are dropped from statistics |
| `t_utc`, `wall_s` | string, number | when the sample started and how long it took in all |
| `failure` | string, optional | present when the sample failed; the other metric keys are then absent. A failed sample is never dropped and retried silently |
| `series` | object, optional | per-turn or per-sample arrays behind the metrics; never read by the statistics |
| `instructions`, `cycles` | numbers, optional | the retired instructions and CPU cycles of the sample's whole process tree (hardware counters, scaled when the kernel time-shared a counter). Absent where the host gives no counters (`run.perf.reason` says why). Streaming samples carry `<label>_instructions_per_1k_tokens` in the same way |
| `perf_scope`, `perf_multiplexed` | string, bool, optional | which instructions were counted (`user+kernel`, `user`, `sampled`) and whether a counter was time-shared (the count is then an estimate scaled by enabled/running time) |
| `text_fs` | object, optional | the file systems of the executable file mappings of the sample's process tree (read from `/proc/<pid>/maps` and the process's own `mountinfo`, at most every 0.2 s): `fs` maps a file system type (`ext4`, `overlay`, `tmpfs`, ...) to a number of mapped files; `bad` lists the mapped files on tmpfs, ramfs, `/dev/shm`, `memfd:` or SysV shared memory (the work directory masked as `<work>`). A sample with a non-empty `bad` has `failure` (docs/METHODOLOGY.md section 4). Absent where the host has no `/proc` (macOS), and absent when the tree ended before the first reading (a sample of a few tens of ms): the run's install-time check, which refuses an arm whose executable or runtime directory is on tmpfs or ramfs, covers those. The run's `run.work_fs` is the work directory's file system type |
| `home` | object | the proof that the sample ran in a fresh home (per-run isolation, docs/METHODOLOGY.md): `fresh` (the harness's directory was created new; false when a leftover of an earlier sample had to be removed), `pre_files` and `pre_sha256` (the home before the process: the arm's seeded first-start state and the config Buffon wrote), `post_files`, `post_sha256`, `written` (files the process created or changed) and `removed` (files it deleted) for the home after the process, `homes` (how many harness homes the sample used). The digests cover each file's path, size and (up to 256 KiB) content. Every sample of a one-sample-per-process workload has it; `buffon verify` rejects a run where one is missing, not fresh, or a round started from another state than its arm's other rounds. Recorded, never a metric |
| `sched` | object, optional | schedstat totals of the measured process trees the sample ran (`/proc/<pid>/task/<tid>/schedstat`, Linux): `run_ms` (time on a CPU), `wait_ms` (time runnable but waiting on a run queue), `slices` (times run), `threads` (threads seen), `meters` (trees measured). Counted from the same start as `cpu_ms` and read every 25 ms and at the end, so a thread that exited is missing at most its last interval and `run_ms` is at most `cpu_ms`; not recorded in a container run or without schedstat. Recorded, never a metric: the report and the gates do not read it |
| `pod` | object, isolation `pod-guaranteed` only | the pod facts the sample ran with: `node`, `cpuset` (the container cgroup's `cpuset.cpus.effective`) and `qos` (`Guaranteed`, or `not Guaranteed` when the cgroup no longer shows exclusive cores and limits), each a string or null. Recorded, never a metric; `buffon verify` rejects a pod-guaranteed run when a sample's node or cpuset differs from the stamp's or its `qos` is not `Guaranteed` |
| `swarm` | object, `scale/*` only | the envelope of a swarm sample: `memory_mib` (memory = memory-swap), `cpus` (the cpuset's CPU numbers) and `pids_max` (the pids limit), exactly these keys. Recorded, never a metric |
| `requests`, `request_bytes`, `request_bytes_per_turn`, `side_requests` | numbers, optional | the wire metrics, kind `wire` (docs/WHAT-WE-MEASURE.md, wire efficiency): the model requests the mock received during the sample, the sum of their body bytes, those bytes per turn of the workload, and the requests beyond the scripted ones. The last two are present only where the workload knows its turns and scripted requests. Runs made before the wire metrics wrote `request_bytes` as the size of the first request only and no `requests`; the reader takes such a value as `first_request_bytes` |
| `session_variant`, `session_seed`, `session_sha256` | string, integer, string; `longsession/resume-*` only | which generated session the sample resumed: `repeating` or `varied` (the twin, docs/WHAT-WE-MEASURE.md), the seed of the generator and the sha256 of the file before its working directory was set. Recorded, never a metric |
| `env` | string, optional | the environment the sample ran in: `native` (SQLite in the process, Node or Go), `miniflare` or `cloudflare`. The report's cell variant is the sample's `api` when it has one, else its `env` when that is not `native`, else none, so a sample of another environment is its own cell and never joins a native one; a native cell keeps the key it always had. A cell id carries the variant after `@` (`<run>::durable/mixed-3500@miniflare#warm_turn_ms`; `-` for native) |
| `runtime_settings`, `runtime_versions`, `store_tables`, `compaction_ids` | object, object, object, list; `durable/*` only | what the arm declared (`window_tokens`, `compaction_enabled`, `background_tokens`, `partial_interval_ms`), the versions it ran, the rows of each table of the store and the ids of the compaction heads. JSON, shown on the Method page and never a metric |
| every other key | number, boolean, string or null | a metric. Names end in their unit (`_ms`, `_mib`, `_bytes`); a number must be finite |

Every sample also carries the host readings taken just before it started (`pinned_busy`, `pinned_iowait`, `pinned_steal`, `cpuset_runnable`, `throttled`, `psi_cpu_some_avg10`, `host_load1`, `host_runnable`, `quiet_wait_ms`): see METHODOLOGY section 5, "Serial execution on the host".

### `durable/*` samples

One sample is one fresh adapter process of one arm in one environment (docs/design/DURABLE.md, docs/DURABLE-ADAPTERS.md). `api` is null and `env` is `native`. A metric the environment cannot produce is absent, never zero: the kernel's byte counters exist on Linux only, and the platform's own rows exist on Miniflare and Cloudflare only.

| key | meaning |
|---|---|
| `fixture_sha256`, `fixture_store_sha256`, `measured_script_sha256`, `fixture_seed`, `fixture_writer`, `fixture_variant`, `fixture_turns`, `fixture_bytes` | the fixture the sample opened: the digest of its script and of the store built from it, the digest of the script of the measured turns, the seed, the arm that built the store, `repeating` or `varied` words, the turns and the bytes in the store. Descriptors, never scored |
| `lane`, `shape`, `turns`, `window_tokens`, `compaction`, `measured_turns`, `conversations`, `cold_start` | the configuration: `compat`, `mixed` or `floor`, the turn shape, the history length, the context window, `on` or `off`, the measured turns (10), the conversations of a `many-conv` workload and the cold-start method. Descriptors |
| `proc_start_ms`, `open_ms`, `first_turn_ms`, `cold_ms`, `ready_to_answer_ms`, `warm_turn_ms`, `warm_net_ms`, `ttfr_ms`, `first_delta_ms` | times on the runner's clock: exec to the ready line, the open request, the first measured turn, `open_ms` plus the first turn, `proc_start_ms` plus `cold_ms`, the median of turns 2 to 10, the warm turn less the median `durable/floor-host` warm turn of the same arm, round and environment (derived at the end of the run and absent without a floor sample; never applied to a cold start), the submit to the scripted model's first request and, for streaming workloads, the first delta to its commit. `cold-every-turn-*` takes `cold_ms` as the median over the measured turns |
| `model_ms_per_turn` | time inside the scripted model. Shown, never scored |
| `warm_instructions`, `warm_cycles`, `warm_cpu_ms`, `instructions`, `cycles`, `cpu_ms` | CPU of the process tree: per warm turn (readings between turns) and over the whole sample |
| `sql_stmts_per_turn`, `sql_read_stmts_per_turn`, `sql_write_stmts_per_turn`, `sql_ddl_stmts_per_turn`, `sql_pragma_stmts_per_turn`, `sql_commits_per_turn`, `rows_returned_per_turn`, `bytes_returned_per_turn` | counts per warm turn from the wrapper on the public SQLite facade. `sql_stmts_per_turn` is the total; the kinds are listed apart (a runtime may read `PRAGMA data_version` often, and the pragma statements are in the total). Kind `count`, lower is better |
| `wchar_bytes_per_turn`, `rchar_bytes_per_turn` | the kernel's byte counters of the process tree per warm turn (Linux only) |
| `rows_read_per_turn`, `rows_written_per_turn` | the platform's own rows, Cloudflare's unit (Miniflare and Cloudflare only) |
| `store_bytes`, `store_bytes_per_turn` | the main file, the log and the index file after a clean close, read by the runner with its own SQLite, and that size over the turns in the store |
| `peak_rss_mib`, `ready_rss_mib`, `end_rss_mib`, `pss_mib`, `peak_mem_mib`, `mem_per_conv_mib` | memory; `mem_per_conv_mib` is the slope of `end_rss_mib` against the conversations over the four `many-conv-*` workloads of one arm and round |
| `build_ms`, `early_turn_ms`, `late_turn_ms` | `grow-*`: the time to build the history and the median of its first and last ten turns |
| `replay_ms_per_turn`, `cpu_ms_replay`, `stmts_replayed`, `commits_replayed` | `durable/floor-sql`: the recorded statements of one turn replayed through the facade and the driver with no runtime |
| `compaction_failures`, `failed_turns`, `failed_requests` | `durable/compaction-fail` |
| `series` | `turn_ms` (the runner's clock for each measured turn), `adapter_turn_ms`, and for `cold-every-turn-*` `cold_ms`. Never read by the statistics |
| `equivalence`, `row_identical` | `ok` when the gate passed; whether the two stores' rows are identical (true, false or absent). Descriptors |

A `durable/crash-*` workload is not a cell. It has one sample for each (order, kill point): `arm` is the resuming arm, `order` is `<writer>><resumer>`, `crash_writer` the killed one, `k` the commit after which it was killed, `commits_total` the commits of the uncrashed control, `kill_event_commit`, `resume_ok`, `invariant_failures` (text, `; ` joined), `signature` (JSON text of the outcome, compared with the reference order's at the same `k`), `duplicated_submission`, `reopen_ms`, `resume_ms` and `ledger` (JSON text). A copy of the resumer carries `twin_of`. The report builds a pass or fail grid from them (`buffon/report/durable.py`): a point passes when the run resumed, no invariant failed, the submission was not duplicated and the outcome equals the reference order's; each order has its passed share with a Wilson 95% interval. An order whose resumer cannot open the writer's store is not run: `run.durable.cross_open` lists it (`{"<fixture>": {"<writer>><reader>": {"ok": false, "why": "..."}}}`) and the grid shows it as `not possible`, never as a failure.

`run.durable` holds the gate's summary (`env`, `oracle`, `passed`, `failures`, the built `fixtures` by label with their digests, `flaky`, `different_work`, `capabilities`, `row_identical`, `cross_open`, `seed`, `generator`, `cold_start`) and `equivalence.json` in the run directory holds the full records (the requests and state digests of each arm for each gate scenario). The site shows both on the Method page.

### `scale/*` samples

How many agents of one harness one container holds (docs/design/SCALE.md). One sample per (arm, round) is a whole search: N doubles (1, 2, 4, ...) until the first probe that fails, then the search bisects between the last pass and that failure to the exact number, up to the cap `swarm_max_agents` (default 8192). A probe starts N agents in one container and passes when every agent is ready and done. The scenario is one of `scale/agents-limit` (RPC agents), `scale/print-limit` (print agents), `scale/agents-ext10` and `scale/print-ext10` (the same with the ten bench extensions loaded; only harnesses whose manifest `pi_extensions` is `native` or `sidecar` take part). `api` is null. Memory, latency and CPU fields are lower is better, `turns_per_s` is higher is better (`buffon/report/cells.py` `direction`).

| key | meaning |
|---|---|
| `agents_limit` | the largest N whose probe completed; 0 when N=1 did not complete |
| `limit_capped` | true when the probe at the cap completed: the limit is "at least `limit_cap`" |
| `limit_cap`, `limit_resolution` | the `swarm_max_agents` used, and `scale_resolution` (1 = exact; r > 1: the true limit is in [`agents_limit`, `first_failure` - 1] and `first_failure` - `agents_limit` <= r) |
| `first_failure` | the smallest N seen to fail, the upper end of the bisection; absent when capped |
| `limit_cause`, `limit_failure` | the `stop_cause` and failure sentence of the probe at `first_failure`; absent when capped |
| `probe_count`, `extensions` | the number of probes, and the extensions loaded (0 or 10) |
| `swarm` | the envelope, above: `memory_mib`, `cpus`, `pids_max`. `pids_max` is the largest probe's: the pids limit is 64 per agent plus 1024, so it depends on N, and each probe records its own |
| `probes` | every probe the search ran, in the order run. Nothing is hidden. Different rounds probe different N while bisecting, so a curve of memory, CPU or turns per second against N pools the probes of all measured rounds per N |
| `failure`, `stop_cause` | only when the limit is 0 (N=1 failed): plain words, and the cause, as for a failed probe below. Otherwise the sample has no `failure` |

Each entry of `probes` has `n`, `phase` (`double` or `bisect`), `ok`, `agents_ok` (the agents that did everything: RPC: ready and every turn answered; print: exit 0 and the final reply; and their file on disk when the harness had a write tool), `pids_max`, and these metrics:

| key | meaning |
|---|---|
| `mem_baseline_mib` | the container's `memory.current` before the first agent started |
| `mem_peak_mib` | `memory.peak` at the end |
| `mem_per_agent_mib` | (`mem_peak_mib` - `mem_baseline_mib`) / N |
| `pss_mib_per_agent` | mean PSS of up to 16 agents' process groups at the end of a clean probe, when `smaps_rollup` is readable |
| `mem_ready_mib` | `memory.current` once every RPC agent was ready |
| `cpu_ms` | the container's `cpu.stat` `usage_usec` delta from before the first agent to the end, less `launcher_cpu_ms` |
| `launcher_cpu_ms` | the relay's own CPU over the same span |
| `cpu_ms_per_agent_turn` | the container's CPU over the same window as `turns_per_s`, over the agent-turns. RPC: the turn phase only (from the last agent ready to the end, less the relay's own CPU of that span), so start-up is not in it. Print: the whole probe over N (one task per agent) |
| `start_cpu_ms_per_agent` | RPC only: the container's CPU from before the first agent started to the last `get_state` answer, less the relay's own CPU of that span, over N |
| `turns_per_s` | agent-turns finished per second of the turn phase (print: N over the makespan) |
| `latency_ms_p50`, `latency_ms_p95`, `latency_ms_max` | RPC: per agent turn, from the prompt reaching the agent to its `agent_end`, on the relay's clock |
| `ready_ms` | RPC: from the first agent's start until every agent answered `get_state` |
| `makespan_ms`, `wall_ms_p50`, `wall_ms_p95` | print: first start to last exit, and per agent start to exit |
| `oom_kills` | the `oom_kill` delta of the container's `memory.events` |
| `pids_peak`, `throttled_periods` | `pids.peak`, and the `nr_throttled` delta of `cpu.stat` |
| `mock_cpu_ms`, `mock_cores`, `mock_worker_max`, `mock_workers`, `mock_saturated` | the scripted model's K worker processes (buffon/mock/prefork.py): their CPU while the agents worked; the busiest turn's CPU over its wall time, in CPUs, for all workers and for the busiest one; K; true when the first is at least 0.9 of K CPUs or the second is at least 0.9, so the model, not the harness, may have limited the probe |
| `runner_cpu_ms` | the runner process's own CPU in the same windows (it reads the container's events), recorded beside the mock's |
| `failure`, `stop_cause` | on a failed probe: plain words, and the cause. `oom`: the kernel killed a process (the probe ends at the first kill and the container is killed at once). `stall`: the container sat within 10% of its memory limit, `memory.events max` rose, no agent made progress for `scale_stall_s` (default 10 s) and nothing was killed. `pids`: a fork was refused. `timeout`: a stage ran out of time (`scale_stage_timeout`, 120 s). `error`: anything else. Read from the kernel's counters first. A reader sees `oom` and `stall` both as "did not fit in <limit>"; the failure text is the detail |
| `work_s`, `prepare_s` | seconds the agents worked, and the host's time creating the agents' directories (not measured) |

The scripted model's request log (the mock-requests file) is written once per probe, not once per sample: its `context` carries `probe` = N, and the probes are listed in `probes`.

Runs made before the search hold doubling-only samples instead: one sample `scale/agents-N` or `scale/print-N` per N = 1, 2, 4, ... with `agents`, `agents_ok`, the metric fields above, and `failure` and `stop_cause` on a stop, and `skipped` entries `not reached: stopped at N agents (<cause>)` for the larger N. The report and the dashboard still read them: the limit is "between P and F-1" (P the largest N that completed in every round, F the first stop), never an exact number, and a run that never stopped reads "at least <top N> (the top of that run)".

`run.rounds` and `run.aa` are what the run was asked for, and `run.rounds_set` and `run.aa_set` say whether the operator gave them. The scale family takes 5 rounds and has no A/A copy unless they were: `run.workload_rounds` lists the workloads whose rounds differ from `run.rounds`, and `run.no_aa_workloads` those that did not run on the A/A copies. Without an A/A copy the noise of a scale cell is the spread of its rounds, min to max.

### `run.adaptive`

Written with every run. `{"enabled": bool, "min_rounds": 6, "min_rounds_by_variant": {"<workload>|<api>": 9}, "max_rounds": 12, "strict": bool, "stopped": {"<workload>|<api>": {"rounds": 9, "min_rounds": 9, "metric": "cpu_ms", "verdicts": {"<arm>": "loss"}, "reason": "answer clear"}}}`. `min_rounds` is the floor for one compared arm. A variant must take at least `min_rounds(k)` rounds, k being the arms it compares with the reference: the smallest n with k * 2 / 2^n < 0.05, so that Holm can still reach p < 0.05 (6 for one arm, 9 for eight). `min_rounds_by_variant` has that figure for every variant checked after a round, whether or not it stopped; `stopped` has the variants that stopped, with the same figure as `min_rounds`.

### `run.isolation`

The isolation the samples ran in. `{"isolation": "container", "comparable": true}`: the container envelope (docs/ENVELOPE.md). `{"isolation": "pod-guaranteed", "comparable": true, "pod": {...}}`: the session's Kubernetes pod is the envelope; `pod` holds the facts it was judged on (node, pod, qos, cpuset, requested CPUs, cpu.max, memory.max, image, delivery, the bundle's ARTIFACTS sha256, read-only root, uid, interfaces). `{"isolation": "none", "comparable": false, "stamp": "uncontained, not comparable"}`: uncontained; when a pod-guaranteed session found its pod short of the envelope it adds `requested: "pod-guaranteed"`, `reasons` (each failed guarantee, P1-P5, or a sample that drifted) and `pod`.

### `hardware`

`class` is `quiet-dedicated` only when the site profile claims dedicated hardware and the runner's own detection agrees (docs/RUNNING.md, "Hardware label"). Otherwise it is `provisional` and `reasons` says why. Every table the report prints repeats the label.

### `skipped[]`

An arm that cannot run a variant gets a row with the reason, never a blank. The report prints it as "cannot run".

### `telemetry`

A sample may carry `telemetry`, nested JSON written by the runner's observers (docs/HOOKS.md); the validator accepts nested finite JSON only there and the report never compares it as a metric. The default observer writes `telemetry.system` with the groups `before`, `after`, `during`, `cpuset`, `cgroup`, `gate`, `collector` and `sources` (docs/TELEMETRY.md). A sample the quiet-host gate refused to start has `quiet_gave_up` and no telemetry. `run.telemetry.system` holds the run-level `start` and `end`.

### `MANIFEST.sha256`

`sha256sum`-format list of every file the run produced, written when a session finishes (and again by `buffon run` after a backend copied the directory back). `buffon verify` rejects a directory whose files differ from it. Generated files (`report.*`, the CSV series, `plots/`, `health.json`) and the files written after the run (`submission.toml`, `promotion.json`) are not listed.

## `facts.json`

Free-form JSON written by `buffon/runner/facts.py`; the keys the report and the hardware detection read are `pinned_cpus`, `mock_cpus`, `cpus_allowed`, `governors`, `fixed_clock`, `smt_active`, `cgroup`, `container`, `node`, `pod`, `idle_before`, `idle_after`, `load_before`, `load_after`, `throttled_usec`, `cpumon`, `runner_commit`, `runner_tree`, `runner_dirty`, `runner_diff_sha256`, `runner_bundle_sha256` (bundle runs) and `cpu_model`.

`runner.dirty` is true when Buffon checkout had uncommitted changes to tracked files; `runner.diff_sha256` is then the sha256 of `git diff HEAD --binary`, so the code that ran can be told apart from the commit. A dirty run is never labelled quiet dedicated hardware. A session that runs from a Kubernetes bundle (no `.git`) takes the commit and tree from the bundle's `bundle.json`, is dirty (with the bundle's `diff_sha256`) when `bundle.json` does not say the checkout it was built from was clean, or when a file of the checkout (everything listed in `ARTIFACTS.sha256` outside `cache/`, `npm-cache/` and `bin/`) is missing or differs, and adds `runner.bundle_sha256`, the sha256 of that `ARTIFACTS.sha256`.

## `mock-requests/`

Every request the mock received, one gzip JSON-lines file per sample (`<n>-<arm>-<workload>-<api>-r<round>.jsonl.gz`; the soak keeps its series instead). A line holds the sample's context (`arm`, `scenario`, `api`, `round`, `warmup`), the request `index`, `protocol`, `t_recv_ns`, `t_reply_start_ns`, `t_reply_end_ns` (monotonic nanoseconds, the clock of the samples), `wire_bytes`, the injected `fault` or null, and the `body`. A request whose message list extends the previous request's list stores `extends_previous` (`key`, `shared`, `tail`) in place of that list; `buffon.mock.reqlog.read(path)` rebuilds the full bodies exactly.

The mock reports usage without a tokenizer: prompt tokens are the request's wire bytes divided by 4, completion tokens are one per streamed part plus 12 per tool call. The numbers are deterministic and equal for arms that send the same request; a report that quotes token counts says so.
