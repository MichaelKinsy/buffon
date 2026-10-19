# Design: the `scale` family (agents working at once)

Status: built for RPC and print-mode agents in one container: `scale/agents-limit` and `scale/print-limit`, each with a twin where every agent loads the ten bench extensions (`scale/agents-ext10`, `scale/print-ext10`). Each sample searches for the exact number of agents one container holds (`buffon/workloads/scale.py`, `buffon/runner/swarm.py`, the swarm mode of the relay in `envelope/relay/swarm.go`, the scripted model `swarm_policy` in `buffon/mock`). Tests use a fake container runtime and fake agents (`tests/test_scale.py`, `tests/fake_swarm.py`, `envelope/relay/swarm_test.go`). Not built: terminal (PTY) agents, the long-context stages, the cluster run (one pod per harness, which holds a group's memory limit as one cgroup, the same shape as the swarm container below). The sections after "Carried over" are the design of those.

## What it measures

How many agents of one harness ONE container of a given size holds, as an exact number, and what each costs. A search doubles N until the kernel (or another limit) stops the agents, then bisects to the largest N whose agents all finished. The question is how many agents one box holds and what each costs, not how fast one agent is.

- `scale/agents-limit`: N long-lived RPC agents (the Pi dialect, `--mode rpc`: arms with an `rpc` mode in `arm.toml`). All are started and every one must answer `get_state`; then `scale_turns` (default 3) turns run in lockstep (send to all, wait for all).
- `scale/print-limit`: N one-shot print-mode agents (`-p`), all started at once, each doing the same task once. Every arm with a `print` mode.
- `scale/agents-ext10` and `scale/print-ext10`: the same, with every agent loading the ten bench extensions (the ext10 fixture set, from the helper the extension sweep uses). Only arms that load Pi extensions (`pi_extensions` native or sidecar) take part; the others are `cannot run` with the reason. An RPC agent is ready when it lists all ten extension commands (Pi answers `get_state` before its extensions are loaded), and a probe that completes must have declared the extension tools on every request, else it fails as an error (the check of `overhead/print-ext10`). The cost of extensions at scale is the gap between the two limits of a harness.

A turn is real agent work from the scripted model (`swarm_policy`): the agent reads its project's `README.md`, writes a file (`swarm-turn-T.txt`), runs one shell command (`wc -c README.md`) and then answers. Each agent has its own HOME and project directory. The model finds which agent is asking from the marker `[agent A turn T]` in the prompt and builds every call from the tool schema the harness declared, as `overhead/print-write` does. A harness without a write tool skips that step; when a write was offered, a sample counts an agent as done only if its file is on disk.

## The swarm container

All N agents of a sample run in one container, started once per sample and removed after it. It is the envelope of [ENVELOPE.md](../ENVELOPE.md), G1-G11 unchanged (`swarm_argv` is built by `build_argv` and linted by `lint` before it runs), with the swarm's limits:

| limit | value |
|---|---|
| memory = memory-swap | `swarm_memory_gib`, default the run's memory tier (4 GiB) |
| cpuset, `--cpus` equal to its size | `swarm_cpus`, default the run's harness CPUs; may not overlap the mock's |
| `--pids-limit` | 64 per agent and 1,024 over (`pids_limit(n)`): a Node, Bun or Go agent has 10 to 30 threads and a pids limit counts threads, so the memory limit, not the process count, is the first limit. A refused fork is still a stop, with cause `pids` |
| network | none; the mock is a mounted unix socket, and the relay in the container bridges `127.0.0.1:<port>` to it (G2, G11) |
| descriptors | `nofile=4096:1048576`: every process starts at the envelope's soft 4096; the relay's own is raised (Go does it at start) because it holds three descriptors per agent and two per connection to the mock |
| HOME | one tmpfs for all homes (`<work>/swarm-homes`), each agent's home seeded into it from a read-only mount when the agent starts, so a home counts in the container's memory per agent; runtime code, caches and sessions are on the disk mount (METHODOLOGY section 4) |

Agents never run outside the container's cgroup: every agent is a process of the relay inside it.

### The launcher

The relay has a swarm mode (`relay -swarm`, `envelope/relay/swarm.go`). The runner holds ONE `docker run -i` and talks to the relay on its standard input and output, one JSON object per line: `start` (argv, exact environment, cwd, seed and home), `send`, `kill`, `stats`, `pss`, `quit`; events `started`, `out`, `exit`, `stats`, `pss`. The relay passes on only the agent output lines that hold a string the runner asked for (`agent_end` and `response` for an RPC agent), and keeps the last 4 KB of each agent's output and error for its `exit` event. A print-mode agent (no lines streamed) writes its output to anonymous files in the container's `/tmp` and the relay reads their end back when the agent has exited; an RPC agent writes to pipes read as the lines come. The first version read a print agent's output through pipes with a 2 s limit at exit, and on the benchmark host at 1024 agents (a launcher starved of CPU by a thousand processes) it sometimes read none of it: 6 to 34 agents that had finished their whole task (the mock saw all four of their requests) were counted as failures with `exited (exit 0)`. A print agent that exits 0 without the final reply now fails the probe only when that is what happened, and the text says so: `6 agents exited 0 without finishing the task: no final reply on their output (N wrote nothing to their output, M had output the launcher had not finished reading); the mock saw 4 requests from each of them (a whole task is 4)`. Every time is the relay's CLOCK_MONOTONIC stamp, and a turn's latency is the difference between the stamp of the runner's `send` reaching the agent's input and the stamp of its `agent_end`, on one clock inside the container.

Costs outside the container, stated: one `docker run` client and one event-reading thread, both on the runner's own CPUs (the mock's, `apply_pinning`); the container runtime's daemon and shim carry the control channel (a few events per agent and turn) and are not pinned by the Buffon. There is no per-agent helper process on the host. The relay's own CPU (its `getrusage`, read through `stats` before and after) is subtracted from the container's `cpu.stat` delta: `cpu_ms` is the agents' and their tools'. The relay's memory per agent (about 20 KB of goroutine stacks and buffers) is in `mem_per_agent_mib`.

**The launcher is protected from the OOM killer.** The relay raises each agent's `oom_score_adj` to 500 right after it starts it (an unprivileged raise: only lowering below a minimum needs `CAP_SYS_RESOURCE`; the agent's children inherit it, and the `started` event says whether it took: `oom_adj`). The relay keeps the default 0, so when the container reaches its memory limit the kernel kills an agent before the launcher, as an orchestrator's own processes are protected from the workloads it runs. Before this (envelope A) a kernel kill could take the relay and with it the whole swarm (`256 of 256 agents did not answer`, container exit 137); that case is still recognised as an OOM from the last cgroup reading, and a ladder's stop is now an agent's death, counted in `agents_ok`. Tested in `envelope/relay/swarm_test.go`.

The container's counters are read on the host from its cgroup (`/sys/fs/cgroup/system.slice/docker-<id>.scope`), which a container thrashing at its memory limit cannot hold up; where the host cannot see that path the relay's reading from inside is used.

### The mock must not be the bottleneck

A swarm's scripted model is served by K worker processes (`buffon/mock/prefork.py`; `mock_workers`, default the number of mock CPUs), so that one Python interpreter's lock is not the ceiling (one process served about 350 to 400 agent-turns per second, and pig-tip's rungs from 16 agents up measured the mock). The parent binds ONE unix socket (`swarm-mock.sock` beside the workspace's `mock.sock`, the one socket the container mounts) and each worker, started as `python -m buffon.mock.prefork` with the socket inherited, accepts on it; the kernel gives a connection to whichever worker is free. The workers start with the first swarm sample and stop with the run.

- State. The policy is stateless across requests: `swarm_policy` reads the agent and turn from the `[agent A turn T]` marker in the prompt, so any worker can answer any request. The parent sends each worker the projects (`{agent: project directory}`) at the start of a sample. There is no fault plan and no request hook in a swarm sample. The serial workloads keep the in-process `MockServer`, which is unchanged (it is now a `Recorder` with listeners; the handler talks to the `Recorder` only).
- Request log. Each worker keeps the requests it served. When the container is gone, the parent collects them from every worker, orders them by arrival (`t_recv` is CLOCK_MONOTONIC, one clock for all the processes), numbers them again from 0 and writes them to the run's `mock-requests` in one call: one complete file per sample, as with one process (`PreforkMock.flush`).
- Saturation. Every sample records `mock_cpu_ms` (the workers' CPU while the agents worked), `mock_cores` (the busiest turn's workers' CPU over its wall time, in CPUs), `mock_worker_max` (the busiest single worker's, in CPUs), `mock_workers` (K) and `runner_cpu_ms` (the runner process, which reads the container's events). `mock_saturated` is true when `mock_cores` is at least 0.9 of K CPUs, or `mock_worker_max` is at least 0.9: a worker is one Python process and cannot use more than about one CPU, so a connection stuck with a full worker waits whatever the others do. A sample with the flag set measured the mock's capacity as much as the harness's.

## The search

One sample is one round's whole search for one harness and kind. A probe is one N: all N agents in one fresh container. A probe completes when every agent is ready and done (the pass rule below); anything else is a failure with a cause.

1. Double. N = 1, 2, 4, ... until the first probe that fails, F, with the last pass P. A harness that completes the cap (`swarm_max_agents`, default 8192) stops there: its limit is "at least the cap" (`limit_capped`), and the sample says so.
2. Bisect. N = (P + F) // 2: a pass moves P up to it, a failure moves F down to it, until F - P is at most `scale_resolution` (default 1, exact). The limit is P, a probe seen to complete, with F = P + 1 a probe seen to fail. A larger resolution stops earlier and the sample records it (`limit_resolution`): the true limit is then in P to F - 1. Exact costs about log2(P) extra probes per round, each at a size near the limit; a failing probe ends at its first OOM kill, so they are cheap.

No pass at N = 1 is a limit of 0 and the sample is a stop (`failure`, `stop_cause`). The search does not assume that the pass rule is monotonic in N: it reports the boundary it found. A flake near the limit moves one round's limit and shows in the range over rounds. Nothing is run twice and nothing is dropped: every probe is in the sample's `probes` with its N, its phase (`double` or `bisect`), its outcome, its cause and its measurements (memory and CPU per agent, turns per second). The bisection adds points to the curves, and the curves pool the probes of all rounds per N.

The ceiling is the envelope, not a number: the memory limit, the pids limit, the CPUs and the clock stop a harness. The cap is a safety net, 8192 so that no harness reached it in a 4 GiB envelope when this was written (pig-tip held about 330 agents), and a harness that reaches it still reports "at least N (cap)" with the reason. Probes are not carried over between rounds: each round searches again from 1, so that the range over rounds is the noise of the limit itself.

The cause of a failed probe is read from the kernel first: `oom` when `memory.events` counted an `oom_kill` during the probe; `pids` when `pids.events` counted a refused fork; `timeout` when a stage ran out of time; else `error`. The failure sentence says it in words ("3 agents exited (signal 9: killed, out of memory?); out of memory: the kernel's OOM killer stopped 3 processes (container peak 1024 MiB of 1024 MiB)"), `race.stop_cause` reads the probe's `stop_cause`, and the sample's `limit_cause` and `limit_failure` are those of the probe at F. A container that hits its memory limit and reclaims without an OOM kill is a `stall` (below), not a timeout.

The headline of a harness is the median over the measured rounds of `agents_limit` (the lower middle value when the count is even, so that it is a number a round produced), with the smallest and largest round beside it.

Runs from before the search hold doubling-only samples (`scale/agents-N`, `scale/print-N`: one sample per N = 1, 2, 4, ... 1024, a stop skipping the larger ones). They still render, as "between P and F - 1" (P the largest N that completed in every round, F the first that did not), never as an exact number; a doubling that never stopped reads "at least 1024".


### When a probe ends

A probe ends as soon as its cause is known, not at the stage timeout. Both rules read the container's counters (the monitor's reading of its cgroup every 50 ms, or the relay's `stats` every second where the host cannot see the cgroup) while the runner waits for the agents:

- `oom`: the first `oom_kill` after the probe began. The runner takes its last readings, then kills the container (`docker kill`) at once. The agents that had not answered yet are not counted against the probe, so the failure reads "out of memory: the kernel's OOM killer stopped 1 processes", not "100 agents never answered".
- `stall`: no agent made progress (no start, no output line, no exit) for `scale_stall_s` (default 10 s), the container's `memory.current` is within 10% of its limit, and `memory.events max` rose in that time. The kernel is reclaiming at the limit and killing nothing; before this the probe waited for the 120 s timeout (Copilot at 32 agents: 5 million limit hits and 949 s of CPU in reclaim, no kill). A busy container near its limit that still makes progress is not stalled, and an idle one far from its limit is not either: it waits for the timeout.
- `timeout`, `pids` and `error` are as before.

To a reader `oom` and `stall` are one thing: the probe did not fit in the limit. The failure text ("the kernel killed 12 agents", "stalled at the limit, nothing killed") is the detail.

### Rounds and A/A

The family takes 5 measured rounds (and the 1 warm-up) and has no A/A copy: a round's answer is one exact limit, and 13 rounds of two copies of a search cost hours for a scripted model. The spread across rounds, min to max, is its noise. `Workload.rounds` and `Workload.aa` carry the defaults, `buffon run` leaves `--rounds` and `--aa` open until given, and an explicit `--rounds` or `--aa` applies to the family like any other workload. A/A stays for every serial workload. A run of only scale workloads installs no copies and is not provisional for it. `buffon/trust.py` leaves the scale samples out of the thinnest-cell round count.

## Sample fields

See [RAW-FORMAT.md](../RAW-FORMAT.md), `samples[]` of `scale/*`. Memory, latency and CPU are lower is better; `turns_per_s` is higher is better (`buffon.report.cells.direction`). For a print sample a turn is the one task: `turns_per_s` is N over the makespan.

CPU and throughput cover the same window. `cpu_ms_per_agent_turn` is the container's CPU over the turn phase only (RPC: from the last agent ready to the end, less the relay's own CPU of that span) over the agent-turns, so it reads with `turns_per_s`; for a print sample it is the whole sample's CPU over N, one task per agent. The start-up is its own field, `start_cpu_ms_per_agent` (RPC: from before the first start to the last `get_state` answer, over N). Before this, `cpu_ms_per_agent_turn` spanned the whole sample, start-up included, while `turns_per_s` used only the turn phase, so a harness with a heavy start-up and light turns showed more CPU per turn and more turns per second than one with the reverse (Pi-Bolt and PiG 0.5.0 at 32 to 128 agents in envelope A). A sample without `start_cpu_ms_per_agent` has the old window.

## What a run costs now

Envelope A (benchmark host, 4 GiB, 8 CPUs, 12 rounds and an A/A copy, `up-3c5957b1c3-measured`, 6 harnesses with an RPC mode and 9 with a print mode, doubling only) took 300 sample-minutes, 190 of them in rungs that had stopped: a stopped rung waited for the survivors to the 120 s timeout, every round tried the next larger failing rung, and every harness ran twice. Since then a probe that does not fit ends at the first OOM kill or after 10 s of stall, the family takes 1 warm-up and 5 measured rounds, and there is no copy. The search adds the bisection, which is about log2(P) probes at sizes near the limit per round, and four workloads instead of two (the ext10 pair has only the harnesses that load Pi extensions).

`buffon up --plan` states the expected time from the real rung timings of envelope A (`buffon/up/catalog.py` `SCALE_LADDER`: per doubling rung, how many harnesses fit it and their mean wall seconds, and how many stopped at it and their mean seconds). A stopped probe is taken as the time to fill the container: twice the wall time of the last rung that fit, plus 10 s where the harness thrashed without a kill. A harness that stops between two rungs pays `ceil(log2(gap / resolution))` more probes, each costed as the mean of a pass at the lower rung and a stop at the upper one. A harness that fits the top row is assumed to stop one doubling above it. In the reference envelope that is about 83 s for one RPC search and about 96 s for one print search per harness, six times each (the warm-up and 5 rounds). The extension variants use the plain timings: no run with extensions has been timed. This is a model, not a measurement of the search: it has not run on the benchmark host. `--param swarm_memory_gib=`, `--param swarm_cpus=` (or `--memory-tier`), `swarm_max_agents` and `scale_resolution` change what it reads (a box with twice the memory holds twice the agents, so the table is read one row up at the same wall time, `catalog.scale_search`).

On a colima VM (linux/arm64, 4 CPUs, 256 MiB container, 8 print agents of which one allocates without end and seven sleep) a probe ended in 1.4 s at the first OOM kill, with the container removed; before, the seven sleepers would have held it to the 120 s timeout. The stall rule has only the unit tests: a thrash at the limit without a kill is not something a small container produces on demand.

## Parameters

`--param KEY=VALUE`: `swarm_memory_gib`, `swarm_cpus` (a cpuset string or a list), `swarm_max_agents` (8192), `scale_resolution` (1), `mock_workers` (the number of mock CPUs), `scale_stage_timeout` (120), `scale_stall_s` (10), `scale_turns` (3), `scale_batch` (agents started per batch, each batch ready before the next; 0, the default, starts all at once), `swarm_pids` (override), `swarm_sample_pss` (agents whose PSS is read, 16).

## What a run costs (measured on the benchmark host, one round, 16 CPUs for the swarm, mock on 8)

These are the first measurements, made with the doubling ladder before the search existed and before the rules of "When a probe ends". Seconds for one probe (the whole container run, including the host's time creating the agents' directories), per N:

| N | pig-tip agents | pi-node agents | pig-tip print | pi-node print | claude-code print |
|---|---|---|---|---|---|
| 1 | 0.9 | 1.2 | 0.7 | 1.1 | 1.2 |
| 16 | 1.0 | 1.9 | 0.9 | 1.7 | 1.9 |
| 64 | 1.8 | 4.7 | 1.3 | 4.3 | 6.1 |
| 128 | 3.1 | 9.2 (OOM at 8 GiB) | 1.8 | 7.8 | 14.8 (OOM at 8 GiB) |
| 256 | 5.0 | | 3.0 | 14.8 (OOM at 8 GiB) | |
| 512 | 9.8 | | 5.0 | | |
| 1024 | 18.9 (OOM at 8 GiB) | | 9.9 | | |

A whole doubling to 1024 is about a minute for pig-tip, and under a minute for a harness that stops at 64 agents. A stop by timeout costs `scale_stage_timeout` (120 s). Memory at 4 GiB and 8 GiB: pi-node 78 MiB per agent (OOM between 32 and 64 agents at 4 GiB, between 64 and 128 at 8 GiB), pig-tip 12 MiB (OOM between 256 and 512 agents at 4 GiB; 512 fit in 8 GiB; 1024 did not), claude-code print 85 to 120 MiB per agent. The host's own time is spent creating the agents' directories and is not measured (about 2 s at 1024).

With the mock served by K = 16 workers on 16 CPUs (round 2) `mock_saturated` was false in every probe: the busiest worker used at most 0.27 of a CPU and the workers together at most 2.7 of 16. A fast harness is then limited by the swarm's own 16 CPUs: pig-tip's swarm used 13.4 of its 16 CPUs at 256 agents and reached about 610 agent-turns per second, pi-node 15.3 of 16 at 64 agents. Before the prefork mock the same pig-tip rungs read 350 to 400 turns per second with `mock_saturated` true from 16 agents up.

Parameters from `buffon up`: `--param KEY=VALUE` (repeatable; also saved in a selection file as `params = { ... }`) reaches every run of the selection as `buffon run --param` does. The swarm's CPUs are the site profile's harness CPUs (`cpus` under `[local]`, or `swarm_cpus`), and the mock workers' number is the number of the profile's `mock_cpus` (or `mock_workers`); `buffon up` reuses `<home>/sites/this-machine.toml` when it fits the machine, so an 8-core swarm profile is `cpus = "40-47"` and `mock_cpus = "48-55,112-119"` there.

## Why it is an exception to the serial rule

See METHODOLOGY section 18. One sample at a time on the host, nothing else running, the agents of the sample concurrent by design. Publication runs use a dedicated host with the mock and the swarm on separate CPUs of one NUMA node.

## Carried over from bolt-bench (design of what is not built)

The port is of bolt-bench's `agent_scale.py` and `ctx_scale.py` (MIT, HPE; `bench/compare` of the bolt-bench branch), coordinated with the bolt-bench lane, which then imports Buffon's version instead of keeping its own.

1. **Memory meter.** PSS from `/proc/<pid>/smaps_rollup` of the arm's process tree; RSS alone overstates shared pages (Bun and Node arms differ by 2x). Built: the relay reads the PSS of up to `swarm_sample_pss` agents' process groups at the end of a clean rung.
2. **Context stages (not built).** Samples when the request crosses 100k, 500k, 850k, 1M, 2M and 4M tokens against a declared window of 5,000,000 tokens so no arm compacts before 4M; N agents against three conversation lengths; the scripted long-context policy of `fake_model_ctx.py`. Stage timeout 900 s.
3. **Terminal agents (not built).** N concurrent sessions each in its own pty; the first-paint settle (`idle_settled.py` in bolt-bench) for an arm that keeps Enter in the editor while its start-up is in progress.
4. **Stall handling.** An arm that stalls is recorded with the stage reached and not retried (built: the probe's failure, which ends the doubling).
5. **Pinning and clean environment.** Built: the swarm's cpuset, the exact environment of each agent (Buffon's isolated environment, nothing from the host's shell).
6. **The cluster (not built).** One pod per harness, Guaranteed QoS, static CPU manager with `full-pcpus-only`; the pod's memory limit is one cgroup for all its agents, the shape the swarm container already has on one host. A/A: each arm runs its copy as a second session on a second node of the same class.
