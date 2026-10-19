# buffon report

**Trust: Dedicated** (host class A). uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare) Every measurement is recorded and shown whatever the label. Headline CPU metric: instructions.

**Run notes (3)**: aa_significant_fraction 18.0%, aa_gap_max 19.8%, aa_floor_max 96.4% (usual ranges: docs/HEALTH.md)

> Every run in this report was on quiet dedicated hardware by the runner's own detection (docs/RUNNING.md, "Hardware label").

| field | value |
|---|---|
| reference arm | pi-node |
| arms | claude-code, codex, copilot, octet, opencode-v2, pi-bun, pi-node, pibolt, pig-0.4.1, pig-tip, rpi (each with an A/A copy `<id>-b` where the run had one) |
| runs | 1 |
| seed | 20261011 |
| token counts | the mock's usage: prompt tokens = request wire bytes / 4, completion tokens = one per streamed part + 12 per tool call; no tokenizer is pinned (METHODOLOGY section 3) |
| arms.lock sha256 | `549a3d2cc424cd316c5ff3072cf5c0c42bb1d6335775fd7289dd560254e35c33` |
| runner commit / tree | `5b3729fca2f0` / `3943ebd8df99` |
| run 1 | site `smc1-socket1` (local), 12 measured + 1 warm-up rounds, harness CPUs `48,49,50,51,112,113,114,115`, mock CPUs `52,116`, Intel(R) Xeon(R) Platinum 8462Y+, kernel 6.8.0-137-generic, meter cgroup-systemd; load before/after 1.3 / 1.0; calibration: CV 1.6% of cpu_ms (gate 5.0%) passed; hardware **quiet-dedicated**; host class **A**; isolation **uncontained, not comparable** |
| run 1 CPU cost | **instructions** (user and kernel instructions) are the headline CPU metric; CPU time (user + system) and wall time are separate cells |

## Run notes

3 notes: aa_significant_fraction 18.0%, aa_gap_max 19.8%, aa_floor_max 96.4%. Run notes describe the conditions of the run. They do not grade it or change a number.

| check | value | usual range | status | meaning |
|---|---:|---:|---|---|
| A/A pairs with a significant gap (paired p < 0.05, before Holm) that is also larger than 1% | 18.0% | up to 5.0% | note | Share of harness and copy pairs that differ by more than 1% and also pass a significance test. A gap under 1% on a steady counter is not counted. About 5% can happen by chance. overhead/print-tools chat teardown_ms pig-tip: 19.8%; overhead/version - wall_ms claude-code: 16.8%; overhead/version - peak_rss_mib opencode-v2: 16.5% |
| A/A gap between a harness and its own copy, largest cell | 19.8% | up to 5.0% | note | The largest gap between a harness and its identical copy, and the cell where it happened. overhead/print-tools chat teardown_ms pig-tip: 19.8%; overhead/version - wall_ms claude-code: 16.8%; overhead/version - peak_rss_mib opencode-v2: 16.5% |
| A/A noise floor, worst scored cell | 96.4% | up to 15.0% | note | The same floor in the noisiest cell. Comparisons in that cell resolve only larger differences. overhead/print-tools chat teardown_ms: 96.4%; overhead/print chat teardown_ms: 41.6%; overhead/rpc chat teardown_ms: 39.5% |
| Calibration: CV of the reference's CPU time between identical runs | 1.6% | up to 2.0% | ok | How much the reference's CPU time varied between identical calibration runs. Lower means a quieter host. |
| A/A CV of CPU metrics, median over arms and cells | 1.6% | up to 2.0% | ok | How much CPU time varies from round to round for one harness. Lower means a quieter host. |
| A/A gap between a harness and its own copy, median over cells | 0.5% | up to 1.0% | ok | The usual gap between a harness and its identical copy. A real difference between two harnesses should be larger than this. |
| A/A noise floor, median over scored cells | 1.8% | up to 3.0% | ok | The smallest difference the identical copies cannot tell from noise, in the usual cell. Smaller differences than this are not resolved. |
| Measured values flagged by the MAD rule | 1.9% | up to 2.0% | ok | Share of measured values far from the median of their cell. Outliers are counted and never removed. |
| Measured samples with at least one host flag | 0.0% | up to 5.0% | ok | Share of samples where the host showed a disturbance: throttling, foreign CPU, steal, a clock change, swap or a memory event. |
| Measured samples with CFS throttling (arm cgroup, every ancestor, session) | 0 | up to 0 | ok | Samples where the kernel held the process back for a CPU quota. Their time then describes the quota, not the harness. |
| Steal: share of the pinned CPUs' capacity taken by a hypervisor | 0.0% | up to 0.1% | ok | Share of the pinned CPUs' time that a hypervisor took away. It only matters on virtual machines. |
| Foreign CPU on the pinned CPUs during a sample, p95 over samples, as a share of the sample's CPU time | 0.0% | up to 1.0% | ok | CPU time that other processes used on the pinned cores during a sample, as a share of the sample's own CPU time (95th percentile). |
| Samples that waited more than 1 s for the host to quiet down | 0.0% | up to 1.0% | ok | Share of samples that had to wait for the quiet-host gate. A busy host makes the gate wait. |
| Samples for which the host never quieted down | 0 | up to 0 | ok | Samples that did not start because the host stayed busy. They are not in the numbers. |
| Effective clock: largest deviation of a sample's mean MHz from the run median | 0.2% | up to 2.0% | ok | How far a sample's mean CPU clock moved from the run median. A moving clock changes CPU time for the same work. |
| Infrastructure failures (envelope OOM, no process started, runner fault) over measured samples | 0.0% | up to 0.0% | ok | Share of samples that failed because of the host or the runner. They are never charged to a harness. |
| Arm failures over measured samples (a swarm ladder's designed stops are results and not counted) | 0.0% | up to 2.0% | ok | Share of samples where the harness itself failed. A scale sample that stopped because the kernel's limit was reached (stop_cause oom, pids or timeout) is a result and is in neither the failures nor the samples counted; a scale error stop is a failure. |
| Drift: median absolute change over the run of an arm's value, over cells | 0.5% | up to 2.0% | ok | How much a harness's value moved from the start of the run to the end. Drift means the host changed during the run. |
| No change point in the reference arm's per-round series | yes | yes | ok | The host's speed did not shift during the run. A shift moves every comparison the same way. |
| At least 12 measured rounds | yes | yes | ok | With fewer rounds the intervals are wide. |
| Every arm has an A/A copy | yes | yes | ok | Without a copy there is no noise floor for that harness. |
| Quiet dedicated hardware by the runner's own detection | yes | yes | ok | On shared hardware other work can disturb the numbers. |
| No harness connected outside the loopback | yes | yes | ok | A harness that talks to the network is not measured alone. |
| Every executable and install tree unchanged during the run | yes | yes | ok | A changed executable means the arm is not what the lock names. |
| Calibration ran and the reference stayed within its 5% limit | yes | yes | ok | Calibration shows the host's noise before the run. Above 5% the run is labelled Noisy. |
| Telemetry recorded for every measured sample | yes | yes | ok | Telemetry is how the other checks see the host. |
| No CPU quota (cpu.max) on the arm cgroup or any ancestor | yes | yes | ok | A quota can throttle a sample. |
| The pinned CPUs have a fixed clock policy | yes | yes | ok | A clock that scales with load changes CPU time for the same work. |

The usual ranges are published in docs/HEALTH.md and are the same for every run. The notes are recomputed from the raw data by `buffon verify`; they are not stored in raw.json.
The A/A rows compare each harness with its own identical copy. A pair counts as different only when its gap is significant and also larger than 1%.

## Buffon leaderboard: Pi Harness Score

**Trust: Dedicated** (host class A). uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare)

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 3.

### Pi-faithful entries (faithfulness 90 or more)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

### Faithfulness not measured (ranked apart until it is)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 (1-2) | pig-tip (PiG 0.5.0) | **100 (A+)** | not measured | 1/9 (8 not run) | source build; 70.2 MB; linux-x64 | 100-100 | 100-100, rank 1-1 |
| 1 (1-2) | rpi (rpi (Rust port of Pi)) | **100 (A+)** | not measured | 1/9 (8 not run) | release archive; 28.6 MB; linux-x64 | 100-100 | 100-100, rank 1-1 |
| 3 | pibolt (Pi-Bolt) | **91 (A-)** | not measured | 1/9 (8 not run) | release archive; 267.5 MB; linux-x64 | 91-91 | 83-98, rank 3-4 |
| 4 | pig-0.4.1 (PiG 0.4.1) | **87 (B+)** | not measured | 1/9 (8 not run) | release archive; 63.8 MB; linux-x64 | 87-87 | 86-89, rank 3-4 |
| 5 | pi-bun (Pi on Bun) | **67 (D+)** | not measured | 1/9 (8 not run) | release archive; 114.5 MB; linux-x64 | 67-67 | 66-68, rank 5-5 |
| 6 | copilot (GitHub Copilot CLI) | **53 (F)** | not measured | 1/9 (8 not run) | npm ci --ignore-scripts; 183.8 MB + node 199 MB; linux-x64 | 53-53 | 51-55, rank 6-6 |

Entries whose 95% intervals overlap are tied in rank: a range in brackets is the best and worst rank the interval allows. If the rank changes across the four weight profiles (equal, cpu-heavy, memory-heavy, extension-heavy) the last column says so.

### No overall score

| entry | coverage | why there is no overall score | faithfulness |
|---|---|---|---|
| claude-code (Claude Code) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak openai-completions; it does not speak openai-responses; no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC); e | not measured |
| codex (Codex CLI) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-completions; no Pi-dialect RPC mode); ext10 (the reference has no cells in this family in this run); streaming (the reference h | not measured |
| octet (Octet) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 6 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses); ext10 (the reference has no cells in this family in this run); streaming (the reference has no cells in this family | not measured |
| opencode-v2 (OpenCode 2) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses; no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL  | not measured |

### Below the reference

- **copilot**: core 53 (F) at 3.21x the reference's cost
- **pi-bun**: core 67 (D+) at 1.23x the reference's cost

*Quiet dedicated hardware: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*


## Summary by axis

Counts of cells where the arm is measurably worse (loss), inconclusive, inside the A/A floor (no measurable difference) or measurably better (win) than the reference `pi-node`. A "cannot run" cell is never counted. Coverage is the cells the arm produced values for out of all cells in the report.

| arm | coverage | family | losses | inconclusive | no measurable difference | wins |
|---|---|---|---:|---:|---:|---:|
| claude-code | 34/147 | overhead | 15 | 0 | 4 | 13 |
| codex | 34/147 | overhead | 10 | 0 | 3 | 19 |
| copilot | 90/147 | overhead | 78 | 0 | 6 | 0 |
| octet | 53/147 | overhead | 7 | 0 | 3 | 40 |
| opencode-v2 | 34/147 | overhead | 26 | 0 | 0 | 6 |
| pi-bun | 147/147 | overhead | 94 | 0 | 13 | 31 |
| pibolt | 147/147 | overhead | 18 | 0 | 9 | 111 |
| pig-0.4.1 | 147/147 | overhead | 27 | 1 | 11 | 99 |
| pig-tip † | 147/147 | overhead | 0 | 0 | 9 | 129 |
| rpi | 147/147 | overhead | 18 | 0 | 9 | 111 |

† `pig-tip`: This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

## claude-code against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | request_bytes | wire | bytes | 12 | 6,114 | 63,097 | 10.3 [10.3, 10.3] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` |
| overhead/print | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 6,114 | 63,097 | 10.3 [10.3, 10.3] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` |
| overhead/print-tools | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 14,204 | 66,465 | 4.68 [4.68, 4.68] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` |
| overhead/print-tools | anthropic | request_bytes | wire | bytes | 12 | 127,836 | 598,183 | 4.68 [4.68, 4.68] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` |
| overhead/print-tools | anthropic | turn_gap_ms | wall | ms | 12 | 3.7 | 14.6 | 3.94 [3.87, 4.38] | 13.4% | 7.4% | 12.0% / 10.6% | 0.0789 / 1.08 | 1 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` |
| overhead/print-tools | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 8.9 | 24.2 | 2.73 [2.64, 3.14] | 18.1% | 6.7% | 10.2% / 13.2% | 0.219 / 2.82 | 2 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` |
| overhead/print | anthropic | peak_rss_mib | memory | MiB | 12 | 114 | 223 | 1.96 [1.95, 1.98] | 4.2% | 0.8% | 0.8% / 1.4% | 1.16 / 1.92 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` |
| overhead/print | anthropic | teardown_ms | wall | ms | 12 | 17.5 | 32.9 | 1.88 [1.84, 1.91] | 15.2% | 2.4% | 1.5% / 3.3% | 0.274 / 1.19 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | peak_rss_mib | memory | MiB | 12 | 135 | 247 | 1.84 [1.81, 1.85] | 1.6% | 1.0% | 1.2% / 0.7% | 2.82 / 1.43 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` |
| overhead/print | anthropic | peak_mem_mib | memory | MiB | 12 | 62.8 | 108 | 1.72 [1.71, 1.74] | 1.6% | 1.3% | 1.1% / 0.2% | 1.07 / 0.207 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | anthropic | peak_mem_mib | memory | MiB | 12 | 86.0 | 134 | 1.55 [1.54, 1.59] | 1.8% | 1.2% | 1.3% / 0.2% | 1.89 / 0.368 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | anthropic | teardown_ms | wall | ms | 12 | 20.2 | 29.3 | 1.45 [1.36, 1.59] | 15.0% | 12.9% | 7.9% / 3.2% | 2.61 / 1.49 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | wall_ms | wall | ms | 12 | 357 | 457 | 1.28 [1.27, 1.33] | 6.6% | 1.1% | 2.2% / 3.5% | 1.96 / 18.1 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` |
| overhead/print-tools | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 508 | 603 | 1.19 [1.16, 1.26] | 9.4% | 1.4% | 2.6% / 5.9% | 7.39 / 42.5 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` |
| overhead/print-tools | anthropic | cycles | CPU | cycles | 12 | 1406.22M | 1624.91M | 1.16 [1.13, 1.23] | 9.3% | 1.4% | 2.6% / 6.2% | 20,029,746 / 122,422,519 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` |
| overhead/print | anthropic | wall_ms | wall | ms | 12 | 311 | 314 | 1.01 [1.01, 1.02] | 2.8% | 1.2% | 1.3% / 2.0% | 1.83 / 3.27 | 1 / 2 | 0.0415 | yes ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` |
| overhead/print-tools | anthropic | first_request_ms | wall | ms | 12 | 292 | 283 | 0.97 [0.959, 1] | 5.1% | 0.9% | 1.4% / 2.3% | 2.82 / 8.38 | 1 / 0 | 0.00928 | yes ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` |
| overhead/print-tools | anthropic | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 421 | 385 | 0.913 [0.902, 0.929] | 3.6% | 1.5% | 1.1% / 3.5% | 5.92 / 7.02 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` |
| overhead/print | anthropic | cycles | CPU | cycles | 12 | 1167.02M | 1022.08M | 0.876 [0.865, 0.894] | 3.1% | 1.4% | 1.1% / 3.6% | 16,040,830 / 20,310,368 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` |
| overhead/print | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 401 | 349 | 0.868 [0.856, 0.887] | 3.2% | 1.5% | 1.1% / 3.6% | 5.73 / 7.1 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` |
| overhead/print | anthropic | first_request_ms | wall | ms | 12 | 292 | 280 | 0.957 [0.952, 0.97] | 2.5% | 1.2% | 1.3% / 2.1% | 2.25 / 3.29 | 1 / 2 | 0.00342 | yes ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` |
| overhead/print | anthropic | instructions | CPU | instructions | 12 | 2323.75M | 1404.92M | 0.605 [0.603, 0.606] | 1.1% | 0.4% | 0.3% / 0.2% | 7,910,528 / 2,002,726 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` |
| overhead/print-tools | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 398 | 354 | 0.889 [0.868, 0.928] | 7.2% | 1.2% | 1.5% / 4.0% | 5.99 / 14.8 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` |
| overhead/print-tools | anthropic | instructions | CPU | instructions | 12 | 2745.09M | 2127.67M | 0.775 [0.773, 0.777] | 0.9% | 0.2% | 0.2% / 0.2% | 8,283,082 / 4,803,479 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 9.31 | 0.0331 [0.033, 0.0334] | 20.0% | 1.7% | 1.0% / 1.5% | 2.84 / 0.0687 | 0 / 2 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 21.43M | 0.0278 [0.0277, 0.028] | 17.4% | 1.7% | 0.9% / 1.7% | 5,972,803 / 116,750 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 25.37M | 0.0155 [0.0155, 0.0155] | 14.2% | 0.2% | 0.3% / 0.1% | 3,727,566 / 36,262 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 4.73 | 0.0821 [0.0814, 0.0825] | 1.5% | 1.6% | 1.1% / 0.1% | 0.617 / 0.00781 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 5.43 | 0.0506 [0.0484, 0.0514] | 13.3% | 1.3% | 1.1% / 5.2% | 1.61 / 0.27 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 8.85 | 0.0406 [0.0402, 0.0408] | 20.7% | 1.4% | 1.2% / 1.6% | 3.07 / 0.0368 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## codex against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-tools | responses | turn_gap_ms | wall | ms | 12 | 4.05 | 45.9 | 11.3 [10.9, 11.6] | 4.2% | 11.0% | 14.8% / 0.4% | 0.24 / 0.236 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` |
| overhead/print | responses | request_bytes | wire | bytes | 12 | 6,024 | 39,509 | 6.56 [6.56, 6.56] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` |
| overhead/print | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 6,024 | 39,509 | 6.56 [6.56, 6.56] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | responses | request_bytes | wire | bytes | 12 | 125,406 | 432,891 | 3.45 [3.45, 3.45] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` |
| overhead/print-tools | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 13,934 | 48,099 | 3.45 [3.45, 3.45] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 10.1 | 27.0 | 2.66 [2.37, 2.78] | 14.1% | 10.2% | 11.6% / 0.7% | 1.47 / 0.269 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` |
| overhead/print | responses | peak_rss_mib | memory | MiB | 12 | 114 | 196 | 1.72 [1.69, 1.73] | 10.9% | 1.0% | 1.4% / 3.0% | 1.35 / 2.89 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` |
| overhead/print-tools | responses | wall_ms | wall | ms | 12 | 362 | 561 | 1.55 [1.53, 1.56] | 2.6% | 2.4% | 2.8% / 0.5% | 5.7 / 2.38 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` |
| overhead/print-tools | responses | peak_rss_mib | memory | MiB | 12 | 135 | 202 | 1.5 [1.48, 1.5] | 0.9% | 1.1% | 0.9% / 0.4% | 1.29 / 1.02 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` |
| overhead/print-tools | responses | teardown_ms | wall | ms | 12 | 16.9 | 20.3 | 1.2 [1.06, 1.26] | 16.7% | 11.8% | 14.1% / 2.2% | 2.81 / 0.4 | 0 / 0 | 0.0083 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | responses | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` |
| overhead/print | responses | teardown_ms | wall | ms | 12 | 20.8 | 19.6 | 0.945 [0.918, 0.993] | 16.6% | 1.6% | 0.8% / 4.1% | 0.104 / 1.51 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` |
| overhead/print-tools | responses | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | responses | cpu_ms | CPU | ms of CPU time | 12 | 425 | 238 | 0.56 [0.553, 0.566] | 3.8% | 2.9% | 1.4% / 1.2% | 6.78 / 3.33 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` |
| overhead/print | responses | cycles | CPU | cycles | 12 | 1178.05M | 603.05M | 0.512 [0.505, 0.52] | 3.5% | 2.9% | 1.4% / 1.4% | 17,455,521 / 13,558,381 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` |
| overhead/print | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 203 | 0.505 [0.499, 0.51] | 3.2% | 3.0% | 1.4% / 1.0% | 6.78 / 3.04 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` |
| overhead/print | responses | first_request_ms | wall | ms | 12 | 295 | 153 | 0.519 [0.509, 0.524] | 4.3% | 2.5% | 1.5% / 1.1% | 6.14 / 2.93 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` |
| overhead/print | responses | instructions | CPU | instructions | 12 | 2351.19M | 791.82M | 0.337 [0.336, 0.338] | 2.6% | 0.4% | 0.4% / 0.6% | 4,128,707 / 4,613,962 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` |
| overhead/print | responses | peak_mem_mib | memory | MiB | 12 | 63.5 | 44.4 | 0.699 [0.691, 0.711] | 2.0% | 0.8% | 0.9% / 1.9% | 0.704 / 0.875 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` |
| overhead/print | responses | wall_ms | wall | ms | 12 | 316 | 173 | 0.549 [0.539, 0.553] | 4.6% | 2.4% | 1.4% / 1.0% | 6.06 / 2.3 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` |
| overhead/print-tools | responses | cpu_ms | CPU | ms of CPU time | 12 | 522 | 471 | 0.904 [0.889, 0.91] | 2.5% | 2.5% | 3.3% / 0.6% | 9.6 / 2.19 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` |
| overhead/print-tools | responses | cycles | CPU | cycles | 12 | 1445.29M | 1234.03M | 0.854 [0.842, 0.859] | 2.4% | 2.6% | 3.2% / 0.6% | 25,635,734 / 4,333,167 | 2 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` |
| overhead/print-tools | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 203 | 0.505 [0.501, 0.508] | 3.5% | 1.4% | 1.4% / 0.8% | 5.71 / 2.05 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` |
| overhead/print-tools | responses | first_request_ms | wall | ms | 12 | 295 | 153 | 0.519 [0.511, 0.525] | 4.7% | 1.6% | 1.6% / 1.3% | 5.1 / 2.92 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` |
| overhead/print-tools | responses | instructions | CPU | instructions | 12 | 2792.76M | 1906.04M | 0.682 [0.682, 0.684] | 1.3% | 0.2% | 0.2% / 0.3% | 6,452,716 / 5,495,242 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` |
| overhead/print-tools | responses | peak_mem_mib | memory | MiB | 12 | 86.0 | 55.3 | 0.643 [0.629, 0.651] | 1.8% | 1.2% | 0.9% / 1.8% | 1.16 / 1.26 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 43.1 | 0.153 [0.151, 0.159] | 9.5% | 1.7% | 1.0% / 4.9% | 2.84 / 2.39 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 110.74M | 0.144 [0.142, 0.148] | 7.5% | 1.7% | 0.9% / 5.2% | 5,972,803 / 4,850,259 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 165.74M | 0.101 [0.101, 0.103] | 4.2% | 0.2% | 0.3% / 2.7% | 3,727,566 / 3,950,382 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 20.1 | 0.348 [0.344, 0.351] | 1.5% | 1.6% | 1.1% / 0.9% | 0.617 / 0.191 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 50.2 | 0.469 [0.46, 0.475] | 3.1% | 1.3% | 1.1% / 6.4% | 1.61 / 1.3 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 39.1 | 0.179 [0.176, 0.185] | 8.7% | 1.4% | 1.2% / 5.3% | 3.07 / 1.62 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## copilot against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | responses | request_bytes | wire | bytes | 12 | 6,024 | 48,425 | 8.04 [8.04, 8.04] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` |
| overhead/print | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 6,024 | 48,425 | 8.04 [8.04, 8.04] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` |
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 48,296 | 7.97 [7.97, 7.97] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 48,296 | 7.97 [7.97, 7.97] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print | anthropic | request_bytes | wire | bytes | 12 | 6,114 | 47,766 | 7.81 [7.81, 7.81] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` |
| overhead/print | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 6,114 | 47,766 | 7.81 [7.81, 7.81] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` |
| overhead/print | anthropic | peak_mem_mib | memory | MiB | 12 | 62.8 | 368 | 5.86 [5.83, 5.94] | 1.6% | 1.3% | 1.1% / 0.2% | 1.07 / 0.593 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` |
| overhead/print | responses | peak_mem_mib | memory | MiB | 12 | 63.5 | 368 | 5.8 [5.77, 5.84] | 0.8% | 0.8% | 0.9% / 0.1% | 0.704 / 0.521 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 368 | 5.79 [5.77, 5.82] | 1.0% | 1.8% | 1.3% / 0.1% | 0.479 / 0.724 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 294 | 5.09 [5.04, 5.12] | 4.8% | 1.6% | 1.1% / 2.4% | 0.617 / 1.44 | 0 / 2 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/print-tools | anthropic | first_request_ms | wall | ms | 12 | 292 | 1,477 | 5.07 [5.04, 5.11] | 1.0% | 0.9% | 1.4% / 0.8% | 2.82 / 13.3 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 1,482 | 5.06 [5.03, 5.09] | 1.6% | 1.6% | 1.3% / 0.6% | 2.5 / 7.65 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print | anthropic | first_request_ms | wall | ms | 12 | 292 | 1,477 | 5.05 [5.02, 5.08] | 1.3% | 1.2% | 1.3% / 0.5% | 2.25 / 6.49 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 1,483 | 5.04 [5.01, 5.08] | 1.5% | 2.1% | 1.7% / 0.6% | 3.48 / 9.83 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print | responses | first_request_ms | wall | ms | 12 | 295 | 1,481 | 5.03 [4.93, 5.07] | 2.7% | 2.5% | 1.5% / 0.4% | 6.14 / 9.6 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` |
| overhead/print-tools | responses | first_request_ms | wall | ms | 12 | 295 | 1,480 | 5.02 [4.95, 5.05] | 2.8% | 1.6% | 1.6% / 0.6% | 5.1 / 7.97 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 1,981 | 4.96 [4.92, 4.99] | 2.2% | 1.4% | 0.9% / 0.9% | 2.98 / 14.5 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print-tools | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 398 | 1,976 | 4.96 [4.89, 5.01] | 1.2% | 1.2% | 1.5% / 1.0% | 5.99 / 24.1 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` |
| overhead/print | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 1,982 | 4.94 [4.88, 4.97] | 2.0% | 3.0% | 1.4% / 0.7% | 6.78 / 9.88 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` |
| overhead/print | anthropic | wall_ms | wall | ms | 12 | 311 | 1,532 | 4.93 [4.91, 4.98] | 1.2% | 1.2% | 1.3% / 1.4% | 1.83 / 11.1 | 1 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` |
| overhead/print | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 401 | 1,976 | 4.92 [4.86, 4.94] | 2.3% | 1.5% | 1.1% / 0.9% | 5.73 / 10.3 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` |
| overhead/print-tools | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 1,973 | 4.91 [4.85, 4.93] | 1.9% | 1.4% | 1.4% / 0.7% | 5.71 / 9.52 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 1,984 | 4.9 [4.86, 4.98] | 2.6% | 1.9% | 1.6% / 1.0% | 10.4 / 20.7 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 1,537 | 4.87 [4.84, 4.91] | 1.7% | 2.0% | 1.6% / 1.4% | 4.4 / 10.9 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/print | responses | wall_ms | wall | ms | 12 | 316 | 1,537 | 4.87 [4.77, 4.9] | 2.5% | 2.4% | 1.4% / 1.1% | 6.06 / 9.04 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` |
| overhead/print | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 421 | 2,047 | 4.86 [4.8, 4.94] | 2.2% | 1.5% | 1.1% / 1.6% | 5.92 / 29.4 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` |
| overhead/print | responses | cpu_ms | CPU | ms of CPU time | 12 | 425 | 2,057 | 4.84 [4.79, 4.88] | 2.3% | 2.9% | 1.4% / 1.3% | 6.78 / 20.3 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` |
| overhead/print | anthropic | cycles | CPU | cycles | 12 | 1167.02M | 5623.17M | 4.82 [4.77, 4.9] | 2.2% | 1.4% | 1.1% / 1.5% | 16,040,830 / 91,425,284 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` |
| overhead/print | responses | cycles | CPU | cycles | 12 | 1178.05M | 5651.08M | 4.8 [4.75, 4.84] | 2.2% | 2.9% | 1.4% / 1.3% | 17,455,521 / 54,038,490 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` |
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 2,049 | 4.79 [4.72, 4.85] | 3.0% | 1.9% | 1.6% / 1.8% | 12.1 / 25.1 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 5629.29M | 4.74 [4.69, 4.81] | 2.7% | 1.8% | 1.6% / 1.7% | 29,576,145 / 63,303,930 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print-tools | anthropic | wall_ms | wall | ms | 12 | 357 | 1,676 | 4.7 [4.68, 4.73] | 1.0% | 1.1% | 2.2% / 0.7% | 1.96 / 13.2 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` |
| overhead/print-tools | responses | wall_ms | wall | ms | 12 | 362 | 1,683 | 4.65 [4.58, 4.67] | 2.6% | 2.4% | 2.8% / 0.6% | 5.7 / 8.2 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 1,677 | 4.64 [4.61, 4.68] | 1.2% | 2.0% | 1.8% / 0.7% | 4.8 / 10.5 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/print-tools | anthropic | turn_gap_ms | wall | ms | 12 | 3.7 | 17.0 | 4.6 [4.51, 4.64] | 2.1% | 7.4% | 12.0% / 0.8% | 0.0789 / 0.151 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` |
| overhead/print-tools | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 508 | 2,257 | 4.45 [4.37, 4.49] | 1.4% | 1.4% | 2.6% / 1.2% | 7.39 / 30.1 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` |
| overhead/print-tools | anthropic | cycles | CPU | cycles | 12 | 1406.22M | 6187.62M | 4.4 [4.33, 4.45] | 1.4% | 1.4% | 2.6% / 1.2% | 20,029,746 / 92,782,400 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 2,258 | 4.36 [4.33, 4.41] | 1.7% | 2.0% | 1.8% / 1.2% | 6.54 / 31.7 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print | anthropic | instructions | CPU | instructions | 12 | 2323.75M | 10123.19M | 4.36 [4.34, 4.38] | 1.0% | 0.4% | 0.3% / 1.7% | 7,910,528 / 61,607,504 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` |
| overhead/print-tools | responses | peak_mem_mib | memory | MiB | 12 | 86.0 | 374 | 4.35 [4.32, 4.39] | 1.5% | 1.2% | 0.9% / 0.1% | 1.16 / 0.562 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` |
| overhead/print-tools | anthropic | peak_mem_mib | memory | MiB | 12 | 86.0 | 374 | 4.35 [4.32, 4.43] | 1.8% | 1.2% | 1.3% / 0.2% | 1.89 / 0.636 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 373 | 4.32 [4.3, 4.33] | 1.3% | 1.0% | 0.7% / 0.1% | 0.521 / 0.382 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/print-tools | responses | cpu_ms | CPU | ms of CPU time | 12 | 522 | 2,253 | 4.32 [4.25, 4.36] | 2.5% | 2.5% | 3.3% / 1.3% | 9.6 / 11.6 | 2 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 10138.36M | 4.32 [4.31, 4.36] | 1.6% | 0.2% | 0.4% / 1.8% | 7,542,734 / 143,625,494 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 6189.09M | 4.32 [4.28, 4.37] | 1.6% | 2.1% | 1.8% / 1.2% | 17,345,646 / 81,990,976 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print | responses | instructions | CPU | instructions | 12 | 2351.19M | 10142.22M | 4.31 [4.3, 4.34] | 0.7% | 0.4% | 0.4% / 1.4% | 4,128,707 / 74,388,334 | 1 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` |
| overhead/print-tools | responses | cycles | CPU | cycles | 12 | 1445.29M | 6175.48M | 4.27 [4.21, 4.31] | 2.4% | 2.6% | 3.2% / 1.3% | 25,635,734 / 38,032,700 | 2 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` |
| overhead/print-tools | responses | turn_gap_ms | wall | ms | 12 | 4.05 | 17.3 | 4.27 [4.08, 4.37] | 4.2% | 11.0% | 14.8% / 1.1% | 0.24 / 0.229 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 16.8 | 4.19 [4.07, 4.46] | 8.5% | 13.7% | 12.9% / 0.9% | 0.278 / 0.0911 | 1 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | anthropic | instructions | CPU | instructions | 12 | 2745.09M | 11188.89M | 4.08 [4.05, 4.11] | 1.0% | 0.2% | 0.2% / 1.2% | 8,283,082 / 155,739,308 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` |
| overhead/print-tools | responses | request_bytes | wire | bytes | 12 | 125,406 | 508,041 | 4.05 [4.05, 4.05] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` |
| overhead/print-tools | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 13,934 | 56,449 | 4.05 [4.05, 4.05] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 11171.34M | 4.01 [4, 4.07] | 1.1% | 0.3% | 0.2% / 1.3% | 5,500,458 / 196,179,916 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 507,564 | 4 [4, 4] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 56,396 | 4 [4, 4] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/print-tools | responses | instructions | CPU | instructions | 12 | 2792.76M | 11162.48M | 4 [3.99, 4.02] | 1.4% | 0.2% | 0.2% / 1.2% | 6,452,716 / 52,135,274 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` |
| overhead/print-tools | anthropic | request_bytes | wire | bytes | 12 | 127,836 | 502,146 | 3.93 [3.93, 3.93] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` |
| overhead/print-tools | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 14,204 | 55,794 | 3.93 [3.93, 3.93] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 818 | 3.74 [3.7, 3.77] | 1.6% | 1.4% | 1.2% / 0.6% | 3.07 / 3.98 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 2682.92M | 3.48 [3.45, 3.53] | 2.0% | 1.7% | 0.9% / 1.3% | 5,972,803 / 37,341,438 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 974 | 3.46 [3.44, 3.51] | 2.3% | 1.7% | 1.0% / 1.3% | 2.84 / 11.3 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/print-tools | responses | teardown_ms | wall | ms | 12 | 16.9 | 55.7 | 3.28 [2.89, 3.44] | 16.7% | 11.8% | 14.1% / 1.6% | 2.81 / 1.19 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` |
| overhead/print | anthropic | teardown_ms | wall | ms | 12 | 17.5 | 53.0 | 3.03 [3, 3.11] | 3.4% | 2.4% | 1.5% / 32.8% | 0.274 / 1.51 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 8.9 | 25.4 | 2.86 [2.8, 2.91] | 2.8% | 6.7% | 10.2% / 12.6% | 0.219 / 0.458 | 2 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 54.9 | 2.85 [2.69, 3.07] | 14.4% | 12.4% | 9.6% / 2.0% | 2.05 / 1.58 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | anthropic | teardown_ms | wall | ms | 12 | 20.2 | 55.2 | 2.74 [2.61, 3] | 15.0% | 12.9% | 7.9% / 1.6% | 2.61 / 0.664 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` |
| overhead/print | anthropic | peak_rss_mib | memory | MiB | 12 | 114 | 303 | 2.67 [2.66, 2.69] | 0.8% | 0.8% | 0.8% / 0.2% | 1.16 / 0.467 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` |
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 25.4 | 2.66 [2.51, 2.76] | 9.9% | 12.1% | 10.8% / 15.8% | 0.84 / 0.316 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print | responses | peak_rss_mib | memory | MiB | 12 | 114 | 303 | 2.66 [2.63, 2.67] | 1.1% | 1.0% | 1.4% / 0.3% | 1.35 / 1.05 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 303 | 2.66 [2.65, 2.67] | 0.5% | 0.5% | 0.4% / 0.2% | 0.556 / 0.892 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 53.3 | 2.63 [2.56, 2.67] | 4.2% | 3.3% | 3.9% / 30.0% | 0.437 / 1.16 | 2 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 4311.73M | 2.63 [2.63, 2.68] | 2.9% | 0.2% | 0.3% / 1.5% | 3,727,566 / 69,520,210 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/print | responses | teardown_ms | wall | ms | 12 | 20.8 | 53.0 | 2.55 [2.53, 2.64] | 6.5% | 1.6% | 0.8% / 32.1% | 0.104 / 2.16 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` |
| overhead/print-tools | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 10.1 | 25.9 | 2.55 [2.29, 2.66] | 14.1% | 10.2% | 11.6% / 14.2% | 1.47 / 0.179 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 251 | 2.35 [2.33, 2.37] | 1.5% | 1.3% | 1.1% / 0.9% | 1.61 / 0.626 | 0 / 4 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/print-tools | anthropic | peak_rss_mib | memory | MiB | 12 | 135 | 310 | 2.3 [2.27, 2.32] | 1.6% | 1.0% | 1.2% / 0.2% | 2.82 / 0.734 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` |
| overhead/print-tools | responses | peak_rss_mib | memory | MiB | 12 | 135 | 310 | 2.3 [2.28, 2.31] | 0.9% | 1.1% | 0.9% / 0.2% | 1.29 / 0.623 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 310 | 2.29 [2.28, 2.3] | 1.0% | 1.0% | 0.9% / 0.2% | 1.46 / 0.548 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` |
| overhead/print | chat | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print | responses | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` |
| overhead/print-tools | anthropic | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |
| overhead/print-tools | responses | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` |

## octet against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 7,919 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 7,919 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 148,926 | 1.17 [1.17, 1.17] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 16,547 | 1.17 [1.17, 1.17] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/rpc | chat | turn_harness_added_ms | wall | ms | 12 | 0.874 | 0.959 | 1.1 [1.08, 1.15] | 5.3% | 3.2% | 3.7% / 1.7% | 0.0447 / 0.0234 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_harness_added_ms` |
| overhead/rpc | chat | request_bytes | wire | bytes | 12 | 1.11M | 1.21M | 1.09 [1.09, 1.09] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes` |
| overhead/rpc | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 55,652 | 60,653 | 1.09 [1.09, 1.09] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | chat | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |
| overhead/rpc | chat | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 12.6 | 0.0295 [0.029, 0.03] | 4.5% | 1.9% | 1.6% / 0.7% | 12.1 / 0.11 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 30.87M | 0.026 [0.0257, 0.0264] | 3.6% | 1.8% | 1.6% / 1.0% | 29,576,145 / 243,963 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 7.46 | 0.0184 [0.0182, 0.0188] | 4.0% | 1.9% | 1.6% / 1.1% | 10.4 / 0.124 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 7.21 | 0.0245 [0.0243, 0.027] | 18.8% | 2.1% | 1.7% / 9.4% | 3.48 / 0.807 | 0 / 2 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 42.56M | 0.0181 [0.018, 0.0182] | 4.5% | 0.2% | 0.4% / 1.4% | 7,542,734 / 385,260 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 4.03 | 0.0634 [0.0614, 0.0638] | 5.3% | 1.8% | 1.3% / 2.2% | 0.479 / 0.127 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 4.13 | 0.0362 [0.0358, 0.0367] | 2.2% | 0.5% | 0.4% / 1.4% | 0.556 / 0.084 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 5.15 | 0.255 [0.249, 0.257] | 7.2% | 3.3% | 3.9% / 1.4% | 0.437 / 0.0716 | 2 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 12.8 | 0.0406 [0.0402, 0.0427] | 10.6% | 2.0% | 1.6% / 5.5% | 4.4 / 0.736 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 24.2 | 0.0468 [0.046, 0.0473] | 1.7% | 2.0% | 1.8% / 1.3% | 6.54 / 0.442 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 61.98M | 0.0432 [0.0424, 0.0436] | 1.9% | 2.1% | 1.8% / 1.4% | 17,345,646 / 1,182,682 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 7.54 | 0.0189 [0.0187, 0.0192] | 4.6% | 1.4% | 0.9% / 1.6% | 2.98 / 0.184 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 7.79 | 0.0266 [0.0246, 0.0284] | 17.8% | 1.6% | 1.3% / 7.4% | 2.5 / 1.09 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 87.73M | 0.0315 [0.0313, 0.0317] | 2.1% | 0.3% | 0.2% / 1.1% | 5,500,458 / 879,666 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 4.57 | 0.0529 [0.052, 0.055] | 3.5% | 1.0% | 0.7% / 3.9% | 0.521 / 0.251 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 4.14 | 0.0306 [0.0303, 0.0311] | 2.2% | 1.0% | 0.9% / 1.2% | 1.46 / 0.082 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 5.42 | 0.282 [0.267, 0.302] | 14.4% | 12.4% | 9.6% / 1.9% | 2.05 / 0.127 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 1.34 | 0.141 [0.13, 0.147] | 9.9% | 12.1% | 10.8% / 2.7% | 0.84 / 0.0504 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 1.4 | 0.35 [0.337, 0.373] | 8.5% | 13.7% | 12.9% / 1.4% | 0.278 / 0.0204 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 27.2 | 0.0751 [0.0731, 0.0768] | 5.0% | 2.0% | 1.8% / 2.7% | 4.8 / 1.19 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/rpc | chat | cpu_ms | CPU | ms of CPU time | 12 | 676 | 88.0 | 0.13 [0.129, 0.132] | 4.5% | 2.5% | 2.5% / 1.1% | 13.2 / 1.11 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cpu_ms` |
| overhead/rpc | chat | cycles | CPU | cycles | 12 | 1863.43M | 234.82M | 0.126 [0.125, 0.128] | 4.3% | 2.5% | 2.5% / 1.1% | 34,831,120 / 2,687,305 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cycles` |
| overhead/rpc | chat | instructions | CPU | instructions | 12 | 3343.17M | 402.54M | 0.12 [0.119, 0.121] | 1.2% | 0.4% | 0.3% / 1.1% | 10,954,495 / 4,479,018 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#instructions` |
| overhead/rpc | chat | peak_mem_mib | memory | MiB | 12 | 89.1 | 5.71 | 0.0641 [0.063, 0.065] | 4.3% | 0.9% | 0.8% / 2.4% | 0.892 / 0.158 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_mem_mib` |
| overhead/rpc | chat | peak_rss_mib | memory | MiB | 12 | 142 | 31.9 | 0.224 [0.223, 0.226] | 1.0% | 0.5% | 0.4% / 0.7% | 0.7 / 0.276 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_rss_mib` |
| overhead/rpc | chat | ready_cpu_ms | CPU | ms of CPU time | 12 | 369 | 6.71 | 0.0182 [0.0179, 0.0184] | 4.8% | 1.6% | 1.8% / 2.2% | 8.23 / 0.108 | 0 / 2 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_cpu_ms` |
| overhead/rpc | chat | ready_ms | wall | ms | 12 | 263 | 6.76 | 0.0257 [0.0237, 0.0284] | 23.3% | 1.3% | 1.5% / 9.9% | 4.82 / 1.15 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_ms` |
| overhead/rpc | chat | ready_pss_mib | memory | MiB | 12 | 107 | 21.3 | 0.2 [0.195, 0.202] | 3.2% | 1.1% | 0.6% / 1.6% | 0.724 / 0.676 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_pss_mib` |
| overhead/rpc | chat | ready_rss_mib | memory | MiB | 12 | 112 | 25.5 | 0.227 [0.223, 0.229] | 2.5% | 1.0% | 0.5% / 1.3% | 0.777 / 0.622 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_rss_mib` |
| overhead/rpc | chat | teardown_ms | wall | ms | 12 | 8.62 | 7.42 | 0.861 [0.767, 0.867] | 15.9% | 9.6% | 7.7% / 1.7% | 1.05 / 0.159 | 4 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#teardown_ms` |
| overhead/rpc | chat | turn_cpu_mean_ms | wall | ms | 12 | 11.9 | 3.7 | 0.312 [0.306, 0.314] | 4.3% | 5.9% | 4.2% / 1.2% | 0.206 / 0.0365 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.2 | 3.72 | 0.332 [0.328, 0.342] | 3.5% | 3.9% | 3.0% / 1.4% | 0.472 / 0.0493 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_ms` |
| overhead/rpc | chat | turn_turn_gap_ms | wall | ms | 12 | 3.25 | 1.55 | 0.477 [0.469, 0.482] | 4.4% | 2.4% | 3.0% / 1.4% | 0.0711 / 0.0277 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_turn_gap_ms` |
| overhead/rpc | chat | turn_wall_ms | wall | ms | 12 | 7.32 | 4.6 | 0.628 [0.618, 0.642] | 3.3% | 2.8% | 2.3% / 1.6% | 0.196 / 0.0737 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_wall_ms` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 1.81 | 0.00643 [0.00637, 0.00651] | 3.2% | 1.7% | 1.0% / 1.8% | 2.84 / 0.027 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 3.52M | 0.00457 [0.00453, 0.00462] | 3.2% | 1.7% | 0.9% / 1.5% | 5,972,803 / 53,654 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 4.29M | 0.00262 [0.00261, 0.00263] | 1.9% | 0.2% | 0.3% / 0.3% | 3,727,566 / 18,873 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 1.51 | 0.0262 [0.0259, 0.0263] | 1.5% | 1.6% | 1.1% / 0.3% | 0.617 / 0.00488 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 4.14 | 0.0386 [0.0384, 0.0393] | 1.7% | 1.3% | 1.1% / 1.4% | 1.61 / 0.0645 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 1.36 | 0.00624 [0.00616, 0.00629] | 3.5% | 1.4% | 1.2% / 1.3% | 3.07 / 0.0175 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## opencode-v2 against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 81.9 | 8.57 [7.96, 9.36] | 17.8% | 12.1% | 10.8% / 10.3% | 0.84 / 10.8 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 32.1 | 8.01 [7.14, 9.27] | 25.5% | 13.7% | 12.9% / 12.0% | 0.278 / 8.41 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 2,435 | 4.7 [4.61, 4.87] | 7.6% | 2.0% | 1.8% / 4.4% | 6.54 / 125 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 6690.74M | 4.67 [4.58, 4.84] | 7.7% | 2.1% | 1.8% / 4.4% | 17,345,646 / 338,030,672 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 83.2 | 4.12 [3.9, 4.5] | 15.0% | 3.3% | 3.9% / 7.7% | 0.437 / 10.6 | 2 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 24,861 | 4.1 [4.1, 4.1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 24,861 | 4.1 [4.1, 4.1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 1,752 | 4.09 [4, 4.16] | 4.2% | 1.9% | 1.6% / 3.1% | 12.1 / 33.9 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 260 | 4.09 [4.03, 4.19] | 5.1% | 1.8% | 1.3% / 3.8% | 0.479 / 10.4 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 4791.87M | 4.04 [3.96, 4.12] | 4.4% | 1.8% | 1.6% / 3.2% | 29,576,145 / 96,657,757 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 76.2 | 3.96 [3.73, 4.41] | 14.4% | 12.4% | 9.6% / 12.6% | 2.05 / 11.3 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 1,572 | 3.94 [3.85, 4.07] | 6.9% | 1.4% | 0.9% / 3.7% | 2.98 / 70 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 1,551 | 3.83 [3.73, 3.91] | 5.0% | 1.9% | 1.6% / 3.1% | 10.4 / 49.6 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 385 | 3.37 [3.31, 3.44] | 4.8% | 0.5% | 0.4% / 2.9% | 0.556 / 13 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 285 | 3.3 [3.24, 3.38] | 4.2% | 1.0% | 0.7% / 2.8% | 0.521 / 11.9 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 9165.88M | 3.29 [3.26, 3.34] | 3.0% | 0.3% | 0.2% / 1.5% | 5,500,458 / 197,368,363 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 411 | 3.04 [3, 3.09] | 3.3% | 1.0% | 0.9% / 2.0% | 1.46 / 12.8 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 1,097 | 3.04 [2.88, 3.15] | 13.5% | 2.0% | 1.8% / 5.7% | 4.8 / 79.3 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 6736.06M | 2.87 [2.84, 2.88] | 1.9% | 0.2% | 0.4% / 1.2% | 7,542,734 / 76,617,944 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 787 | 2.49 [2.39, 2.55] | 7.0% | 2.0% | 1.6% / 4.2% | 4.4 / 45.1 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 720 | 2.46 [2.36, 2.52] | 10.4% | 1.6% | 1.3% / 4.7% | 2.5 / 31.9 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 702 | 2.39 [2.27, 2.44] | 7.0% | 2.1% | 1.7% / 4.1% | 3.48 / 40.4 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 281,359 | 2.22 [2.22, 2.22] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 31,262 | 2.22 [2.22, 2.22] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/print | chat | requests | wire | count | 12 | 1 | 2 | 2 [2, 2] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 10.0 | 1.11 [1.11, 1.11] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 125 | 0.443 [0.437, 0.454] | 4.7% | 1.7% | 1.0% / 1.7% | 2.84 / 4.16 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 326.58M | 0.423 [0.417, 0.432] | 4.1% | 1.7% | 0.9% / 1.8% | 5,972,803 / 9,904,822 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 464.27M | 0.284 [0.283, 0.284] | 1.4% | 0.2% | 0.3% / 0.2% | 3,727,566 / 1,304,054 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 46.5 | 0.806 [0.797, 0.81] | 1.5% | 1.6% | 1.1% / 0.6% | 0.617 / 0.479 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 88.3 | 0.824 [0.818, 0.833] | 20.2% | 1.3% | 1.1% / 0.4% | 1.61 / 0.563 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 82.2 | 0.377 [0.372, 0.379] | 4.6% | 1.4% | 1.2% / 0.9% | 3.07 / 0.937 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## pi-bun against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 389 | 1.78 [1.76, 1.79] | 1.6% | 1.4% | 1.2% / 1.0% | 3.07 / 1.54 | 0 / 1 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |
| overhead/rpc | chat | ready_ms | wall | ms | 12 | 263 | 449 | 1.7 [1.69, 1.72] | 2.2% | 1.3% | 1.5% / 0.4% | 4.82 / 2.94 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_ms` |
| overhead/rpc | anthropic | ready_ms | wall | ms | 12 | 264 | 449 | 1.7 [1.69, 1.71] | 1.5% | 2.1% | 1.4% / 0.5% | 2.27 / 2.81 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_ms` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 477 | 1.69 [1.66, 1.72] | 2.3% | 1.7% | 1.0% / 2.2% | 2.84 / 11.7 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 1303.99M | 1.69 [1.67, 1.72] | 2.3% | 1.7% | 0.9% / 2.3% | 5,972,803 / 31,745,749 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/rpc | responses | ready_ms | wall | ms | 12 | 265 | 448 | 1.69 [1.68, 1.69] | 2.0% | 1.1% | 0.8% / 0.3% | 1.84 / 1.48 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_ms` |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 479 | 1.63 [1.62, 1.65] | 1.6% | 1.6% | 1.3% / 0.4% | 2.5 / 3.52 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print-tools | anthropic | first_request_ms | wall | ms | 12 | 292 | 476 | 1.63 [1.62, 1.64] | 1.0% | 0.9% | 1.4% / 0.4% | 2.82 / 1.97 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` |
| overhead/print | anthropic | first_request_ms | wall | ms | 12 | 292 | 476 | 1.63 [1.62, 1.64] | 1.3% | 1.2% | 1.3% / 0.5% | 2.25 / 3.81 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 478 | 1.63 [1.61, 1.64] | 1.5% | 2.1% | 1.7% / 0.3% | 3.48 / 2.4 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print | responses | first_request_ms | wall | ms | 12 | 295 | 477 | 1.62 [1.59, 1.63] | 2.7% | 2.5% | 1.5% / 0.4% | 6.14 / 1.39 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` |
| overhead/print-tools | responses | first_request_ms | wall | ms | 12 | 295 | 477 | 1.62 [1.6, 1.63] | 2.8% | 1.6% | 1.6% / 0.3% | 5.1 / 1.23 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 2609.71M | 1.59 [1.57, 1.62] | 2.9% | 0.2% | 0.3% / 1.5% | 3,727,566 / 74,722,446 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/print | anthropic | wall_ms | wall | ms | 12 | 311 | 491 | 1.58 [1.58, 1.6] | 1.2% | 1.2% | 1.3% / 0.6% | 1.83 / 3.44 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` |
| overhead/print | responses | wall_ms | wall | ms | 12 | 316 | 498 | 1.58 [1.55, 1.58] | 2.5% | 2.4% | 1.4% / 0.4% | 6.06 / 2.18 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 497 | 1.58 [1.56, 1.59] | 1.7% | 2.0% | 1.6% / 0.3% | 4.4 / 2.24 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/rpc | anthropic | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 583 | 1.57 [1.54, 1.59] | 2.6% | 1.7% | 1.6% / 1.1% | 9.15 / 6.52 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_cpu_ms` |
| overhead/rpc | chat | ready_cpu_ms | CPU | ms of CPU time | 12 | 369 | 580 | 1.57 [1.54, 1.58] | 1.7% | 1.6% | 1.8% / 0.9% | 8.23 / 4.97 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_cpu_ms` |
| overhead/rpc | responses | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 581 | 1.56 [1.54, 1.58] | 1.8% | 1.5% | 1.3% / 0.9% | 6.56 / 4.79 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_cpu_ms` |
| overhead/print | anthropic | peak_mem_mib | memory | MiB | 12 | 62.8 | 97.0 | 1.54 [1.54, 1.57] | 1.6% | 1.3% | 1.1% / 0.8% | 1.07 / 0.435 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 616 | 1.54 [1.53, 1.56] | 2.2% | 1.4% | 0.9% / 0.9% | 2.98 / 7.77 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 98.1 | 1.54 [1.54, 1.55] | 2.1% | 1.8% | 1.3% / 0.8% | 0.479 / 0.578 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/print | responses | peak_mem_mib | memory | MiB | 12 | 63.5 | 97.9 | 1.54 [1.54, 1.55] | 0.8% | 0.8% | 0.9% / 1.7% | 0.704 / 0.889 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` |
| overhead/print-tools | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 398 | 612 | 1.54 [1.52, 1.55] | 1.2% | 1.2% | 1.5% / 0.9% | 5.99 / 4.53 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` |
| overhead/print | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 615 | 1.53 [1.51, 1.55] | 1.8% | 3.0% | 1.4% / 1.2% | 6.78 / 7.71 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` |
| overhead/print-tools | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 615 | 1.53 [1.51, 1.54] | 1.9% | 1.4% | 1.4% / 1.4% | 5.71 / 8.12 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` |
| overhead/print | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 401 | 613 | 1.53 [1.51, 1.55] | 2.3% | 1.5% | 1.1% / 1.2% | 5.73 / 8.22 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 617 | 1.52 [1.51, 1.55] | 2.6% | 1.9% | 1.6% / 0.7% | 10.4 / 4.19 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | responses | cpu_ms | CPU | ms of CPU time | 12 | 425 | 643 | 1.51 [1.49, 1.53] | 1.7% | 2.9% | 1.4% / 1.0% | 6.78 / 6.59 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` |
| overhead/print | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 421 | 635 | 1.51 [1.49, 1.52] | 2.2% | 1.5% | 1.1% / 1.2% | 5.92 / 4.47 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` |
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 644 | 1.5 [1.48, 1.53] | 3.0% | 1.9% | 1.6% / 0.8% | 12.1 / 3.82 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | responses | cycles | CPU | cycles | 12 | 1178.05M | 1759.45M | 1.49 [1.47, 1.51] | 1.7% | 2.9% | 1.4% / 1.1% | 17,455,521 / 12,956,749 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` |
| overhead/print | anthropic | cycles | CPU | cycles | 12 | 1167.02M | 1736.06M | 1.49 [1.47, 1.5] | 2.2% | 1.4% | 1.1% / 1.1% | 16,040,830 / 15,870,025 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 536 | 1.48 [1.47, 1.5] | 1.2% | 2.0% | 1.8% / 0.4% | 4.8 / 3.22 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/print-tools | responses | wall_ms | wall | ms | 12 | 362 | 535 | 1.48 [1.46, 1.49] | 2.6% | 2.4% | 2.8% / 0.4% | 5.7 / 3.35 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 1754.50M | 1.48 [1.46, 1.51] | 2.7% | 1.8% | 1.6% / 0.6% | 29,576,145 / 12,116,716 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print-tools | anthropic | wall_ms | wall | ms | 12 | 357 | 526 | 1.48 [1.47, 1.48] | 1.0% | 1.1% | 2.2% / 0.5% | 1.96 / 2.6 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 83.2 | 1.44 [1.42, 1.46] | 3.3% | 1.6% | 1.1% / 1.6% | 0.617 / 2.12 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/rpc | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 637 | 918 | 1.44 [1.41, 1.45] | 2.0% | 2.9% | 3.3% / 1.7% | 12.7 / 13.5 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cpu_ms` |
| overhead/rpc | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.08 | 13.0 | 1.44 [1.39, 1.52] | 9.2% | 4.8% | 4.1% / 4.9% | 0.466 / 0.694 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_ms` |
| overhead/rpc | anthropic | cycles | CPU | cycles | 12 | 1756.48M | 2509.71M | 1.43 [1.4, 1.44] | 2.1% | 2.9% | 3.3% / 1.6% | 34,415,458 / 38,812,445 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cycles` |
| overhead/rpc | anthropic | instructions | CPU | instructions | 12 | 3209.13M | 4548.81M | 1.42 [1.4, 1.42] | 1.5% | 0.3% | 0.2% / 0.9% | 7,831,587 / 74,148,225 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#instructions` |
| overhead/print | anthropic | instructions | CPU | instructions | 12 | 2323.75M | 3290.68M | 1.42 [1.41, 1.42] | 1.3% | 0.4% | 0.3% / 1.0% | 7,910,528 / 5,796,790 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` |
| overhead/print | responses | instructions | CPU | instructions | 12 | 2351.19M | 3326.62M | 1.41 [1.41, 1.42] | 0.4% | 0.4% | 0.4% / 1.0% | 4,128,707 / 5,468,128 | 1 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 3321.46M | 1.41 [1.41, 1.42] | 2.4% | 0.2% | 0.4% / 0.7% | 7,542,734 / 1,133,308 | 0 / 2 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/rpc | chat | instructions | CPU | instructions | 12 | 3343.17M | 4606.21M | 1.38 [1.37, 1.38] | 0.7% | 0.4% | 0.3% / 0.6% | 10,954,495 / 30,515,779 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#instructions` |
| overhead/rpc | chat | cpu_ms | CPU | ms of CPU time | 12 | 676 | 931 | 1.38 [1.36, 1.4] | 4.5% | 2.5% | 2.5% / 1.0% | 13.2 / 15.8 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cpu_ms` |
| overhead/rpc | responses | cpu_ms | CPU | ms of CPU time | 12 | 680 | 937 | 1.38 [1.36, 1.39] | 1.8% | 1.7% | 1.3% / 1.2% | 12.3 / 9.81 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cpu_ms` |
| overhead/rpc | responses | instructions | CPU | instructions | 12 | 3379.56M | 4648.68M | 1.38 [1.37, 1.38] | 0.9% | 0.3% | 0.2% / 0.7% | 10,393,734 / 19,028,553 | 0 / 3 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#instructions` |
| overhead/rpc | responses | cycles | CPU | cycles | 12 | 1874.58M | 2566.52M | 1.37 [1.35, 1.38] | 1.8% | 1.6% | 1.2% / 1.2% | 31,582,812 / 32,467,071 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cycles` |
| overhead/rpc | chat | cycles | CPU | cycles | 12 | 1863.43M | 2548.29M | 1.37 [1.35, 1.39] | 4.3% | 2.5% | 2.5% / 1.0% | 34,831,120 / 39,066,008 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cycles` |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 705 | 1.36 [1.34, 1.37] | 1.7% | 2.0% | 1.8% / 0.8% | 6.54 / 5.97 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print-tools | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 508 | 689 | 1.36 [1.34, 1.37] | 1.4% | 1.4% | 2.6% / 0.9% | 7.39 / 7.17 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` |
| overhead/print-tools | responses | cpu_ms | CPU | ms of CPU time | 12 | 522 | 703 | 1.35 [1.33, 1.36] | 2.5% | 2.5% | 3.3% / 1.3% | 9.6 / 7.83 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 1926.37M | 1.34 [1.32, 1.35] | 1.6% | 2.1% | 1.8% / 0.8% | 17,345,646 / 19,901,273 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print-tools | anthropic | cycles | CPU | cycles | 12 | 1406.22M | 1883.12M | 1.34 [1.32, 1.35] | 1.4% | 1.4% | 2.6% / 1.1% | 20,029,746 / 20,630,108 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` |
| overhead/print-tools | responses | cycles | CPU | cycles | 12 | 1445.29M | 1926.73M | 1.33 [1.31, 1.34] | 2.4% | 2.6% | 3.2% / 1.2% | 25,635,734 / 16,430,630 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` |
| overhead/rpc | anthropic | turn_cpu_mean_ms | wall | ms | 12 | 10.3 | 13.5 | 1.31 [1.26, 1.33] | 5.9% | 5.6% | 6.7% / 4.4% | 0.232 / 0.798 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_mean_ms` |
| overhead/rpc | anthropic | peak_mem_mib | memory | MiB | 12 | 86.2 | 112 | 1.3 [1.29, 1.31] | 1.3% | 1.1% | 1.0% / 0.7% | 1.05 / 1.12 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_mem_mib` |
| overhead/rpc | anthropic | turn_wall_ms | wall | ms | 12 | 6.79 | 8.78 | 1.29 [1.24, 1.32] | 5.5% | 2.1% | 2.9% / 3.8% | 0.159 / 0.385 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_wall_ms` |
| overhead/print-tools | responses | instructions | CPU | instructions | 12 | 2792.76M | 3565.20M | 1.28 [1.26, 1.28] | 2.4% | 0.2% | 0.2% / 1.1% | 6,452,716 / 43,612,317 | 0 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` |
| overhead/print-tools | anthropic | instructions | CPU | instructions | 12 | 2745.09M | 3500.28M | 1.28 [1.26, 1.28] | 1.0% | 0.2% | 0.2% / 1.0% | 8,283,082 / 22,708,978 | 0 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 3541.26M | 1.27 [1.27, 1.28] | 0.5% | 0.3% | 0.2% / 0.9% | 5,500,458 / 18,089,256 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/rpc | chat | teardown_ms | wall | ms | 12 | 8.62 | 10.8 | 1.26 [1.07, 1.32] | 15.9% | 9.6% | 7.7% / 9.3% | 1.05 / 1.34 | 4 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#teardown_ms` |
| overhead/rpc | anthropic | teardown_ms | wall | ms | 12 | 8.72 | 10.9 | 1.26 [1.04, 1.31] | 15.2% | 9.4% | 5.4% / 9.6% | 0.698 / 1.88 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#teardown_ms` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 133 | 1.24 [1.22, 1.26] | 2.2% | 1.3% | 1.1% / 1.6% | 1.61 / 2.59 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/rpc | anthropic | turn_turn_gap_ms | wall | ms | 12 | 3.03 | 3.75 | 1.24 [1.14, 1.29] | 17.9% | 2.7% | 2.6% / 6.6% | 0.0798 / 0.394 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_turn_gap_ms` |
| overhead/rpc | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.2 | 13.8 | 1.23 [1.2, 1.29] | 7.6% | 3.9% | 3.0% / 5.5% | 0.472 / 0.45 | 0 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_ms` |
| overhead/rpc | chat | peak_mem_mib | memory | MiB | 12 | 89.1 | 110 | 1.23 [1.22, 1.24] | 0.9% | 0.9% | 0.8% / 0.8% | 0.892 / 1.06 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_mem_mib` |
| overhead/rpc | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.0 | 13.5 | 1.23 [1.16, 1.37] | 10.4% | 8.7% | 7.4% / 6.6% | 1.2 / 1.45 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_ms` |
| overhead/rpc | chat | ready_rss_mib | memory | MiB | 12 | 112 | 137 | 1.22 [1.21, 1.24] | 2.4% | 1.0% | 0.5% / 1.3% | 0.777 / 2.02 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_rss_mib` |
| overhead/rpc | responses | peak_mem_mib | memory | MiB | 12 | 90.6 | 111 | 1.22 [1.21, 1.23] | 1.4% | 1.3% | 1.1% / 0.7% | 0.707 / 0.936 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_mem_mib` |
| overhead/rpc | responses | ready_rss_mib | memory | MiB | 12 | 112 | 137 | 1.22 [1.21, 1.23] | 1.1% | 0.5% | 0.7% / 1.1% | 1.06 / 1.24 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_rss_mib` |
| overhead/rpc | responses | ready_pss_mib | memory | MiB | 12 | 107 | 131 | 1.22 [1.21, 1.23] | 1.0% | 0.6% | 0.8% / 0.7% | 1.06 / 0.904 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_pss_mib` |
| overhead/rpc | chat | ready_pss_mib | memory | MiB | 12 | 107 | 130 | 1.22 [1.21, 1.23] | 0.9% | 1.1% | 0.6% / 0.8% | 0.724 / 1.11 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_pss_mib` |
| overhead/rpc | anthropic | ready_rss_mib | memory | MiB | 12 | 113 | 137 | 1.22 [1.21, 1.23] | 1.6% | 0.8% | 0.7% / 1.5% | 0.591 / 1.69 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_rss_mib` |
| overhead/rpc | chat | turn_wall_ms | wall | ms | 12 | 7.32 | 8.88 | 1.21 [1.18, 1.24] | 5.1% | 2.8% | 2.3% / 4.6% | 0.196 / 0.335 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_wall_ms` |
| overhead/rpc | anthropic | ready_pss_mib | memory | MiB | 12 | 107 | 130 | 1.21 [1.2, 1.22] | 1.3% | 0.8% | 0.7% / 0.8% | 0.59 / 1.68 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_pss_mib` |
| overhead/print | anthropic | peak_rss_mib | memory | MiB | 12 | 114 | 137 | 1.21 [1.2, 1.23] | 2.1% | 0.8% | 0.8% / 1.4% | 1.16 / 2.07 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 137 | 1.2 [1.2, 1.21] | 2.0% | 0.5% | 0.4% / 1.0% | 0.556 / 0.41 | 0 / 3 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print | responses | peak_rss_mib | memory | MiB | 12 | 114 | 137 | 1.2 [1.19, 1.22] | 1.2% | 1.0% | 1.4% / 2.0% | 1.35 / 1.93 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` |
| overhead/rpc | responses | turn_wall_ms | wall | ms | 12 | 7.46 | 8.95 | 1.2 [1.18, 1.22] | 4.0% | 3.1% | 2.1% / 4.3% | 0.175 / 0.232 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_wall_ms` |
| overhead/print-tools | responses | peak_mem_mib | memory | MiB | 12 | 86.0 | 101 | 1.18 [1.16, 1.19] | 1.8% | 1.2% | 0.9% / 0.9% | 1.16 / 1.3 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` |
| overhead/print-tools | anthropic | peak_mem_mib | memory | MiB | 12 | 86.0 | 100 | 1.17 [1.15, 1.19] | 1.8% | 1.2% | 1.3% / 1.5% | 1.89 / 1.22 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 100 | 1.16 [1.16, 1.17] | 1.3% | 1.0% | 0.7% / 0.7% | 0.521 / 0.895 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/rpc | chat | turn_cpu_mean_ms | wall | ms | 12 | 11.9 | 13.8 | 1.16 [1.13, 1.18] | 4.8% | 5.9% | 4.2% / 4.5% | 0.206 / 0.597 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc | responses | turn_cpu_mean_ms | wall | ms | 12 | 12.1 | 13.9 | 1.15 [1.12, 1.2] | 3.3% | 3.0% | 2.5% / 4.8% | 0.453 / 0.438 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_mean_ms` |
| overhead/rpc | responses | turn_turn_gap_ms | wall | ms | 12 | 3.29 | 3.72 | 1.13 [1.05, 1.21] | 12.7% | 2.8% | 1.5% / 10.2% | 0.0715 / 0.467 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_turn_gap_ms` |
| overhead/rpc | anthropic | peak_rss_mib | memory | MiB | 12 | 139 | 154 | 1.11 [1.11, 1.12] | 0.7% | 0.6% | 0.7% / 0.5% | 0.745 / 1.14 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_rss_mib` |
| overhead/rpc | chat | peak_rss_mib | memory | MiB | 12 | 142 | 152 | 1.06 [1.06, 1.07] | 0.9% | 0.5% | 0.4% / 0.6% | 0.7 / 1.41 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_rss_mib` |
| overhead/rpc | responses | peak_rss_mib | memory | MiB | 12 | 144 | 153 | 1.06 [1.06, 1.07] | 0.7% | 0.7% | 0.6% / 0.5% | 0.756 / 0.827 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_rss_mib` |
| overhead/print-tools | responses | peak_rss_mib | memory | MiB | 12 | 135 | 143 | 1.06 [1.05, 1.07] | 1.5% | 1.1% | 0.9% / 0.7% | 1.29 / 1.41 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 142 | 1.05 [1.04, 1.06] | 1.1% | 1.0% | 0.9% / 0.7% | 1.46 / 1.54 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |
| overhead/print-tools | anthropic | peak_rss_mib | memory | MiB | 12 | 135 | 139 | 1.03 [1.02, 1.05] | 1.6% | 1.0% | 1.2% / 1.5% | 2.82 / 1.39 | 0 / 0 | 0.00342 | yes ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` |
| overhead/print | chat | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 18.4 | 0.911 [0.876, 0.942] | 19.2% | 3.3% | 3.9% / 5.4% | 0.437 / 1.32 | 2 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/print | responses | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` |
| overhead/print | responses | teardown_ms | wall | ms | 12 | 20.8 | 19.3 | 0.931 [0.908, 0.963] | 8.9% | 1.6% | 0.8% / 4.9% | 0.104 / 0.974 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` |
| overhead/print-tools | anthropic | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |
| overhead/print-tools | responses | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` |
| overhead/rpc | anthropic | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#requests` |
| overhead/rpc | chat | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#requests` |
| overhead/rpc | chat | turn_turn_gap_ms | wall | ms | 12 | 3.25 | 3.57 | 1.1 [1.05, 1.19] | 24.9% | 2.4% | 3.0% / 11.9% | 0.0711 / 0.312 | 1 / 2 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_turn_gap_ms` |
| overhead/rpc | responses | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#requests` |
| overhead/rpc | responses | teardown_ms | wall | ms | 12 | 9.51 | 10.6 | 1.11 [1.03, 1.21] | 12.0% | 9.0% | 7.4% / 6.1% | 1.33 / 0.528 | 0 / 3 | 0.0132 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#teardown_ms` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | request_bytes | wire | bytes | 12 | 6,114 | 5,984 | 0.979 [0.979, 0.979] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` |
| overhead/print | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 6,114 | 5,984 | 0.979 [0.979, 0.979] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` |
| overhead/print | anthropic | teardown_ms | wall | ms | 12 | 17.5 | 14.3 | 0.819 [0.792, 0.859] | 19.8% | 2.4% | 1.5% / 7.4% | 0.274 / 0.922 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` |
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 5,929 | 0.979 [0.979, 0.979] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 5,929 | 0.979 [0.979, 0.979] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print | responses | request_bytes | wire | bytes | 12 | 6,024 | 5,894 | 0.978 [0.978, 0.978] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` |
| overhead/print | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 6,024 | 5,894 | 0.978 [0.978, 0.978] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | anthropic | request_bytes | wire | bytes | 12 | 127,836 | 126,630 | 0.991 [0.991, 0.991] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` |
| overhead/print-tools | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 14,204 | 14,070 | 0.991 [0.991, 0.991] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` |
| overhead/print-tools | anthropic | teardown_ms | wall | ms | 12 | 20.2 | 11.4 | 0.563 [0.524, 0.611] | 15.0% | 12.9% | 7.9% / 5.6% | 2.61 / 1.27 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 8.9 | 6.43 | 0.723 [0.68, 0.761] | 11.8% | 6.7% | 10.2% / 7.1% | 0.219 / 0.531 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` |
| overhead/print-tools | anthropic | turn_gap_ms | wall | ms | 12 | 3.7 | 3.13 | 0.847 [0.808, 0.915] | 13.1% | 7.4% | 12.0% / 7.1% | 0.0789 / 0.367 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 125,595 | 0.99 [0.99, 0.99] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 13,955 | 0.99 [0.99, 0.99] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 12.5 | 0.649 [0.589, 0.701] | 16.5% | 12.4% | 9.6% / 9.2% | 2.05 / 1.01 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 6.78 | 0.71 [0.621, 0.745] | 12.2% | 12.1% | 10.8% / 6.9% | 0.84 / 0.806 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 3.29 | 0.821 [0.783, 0.898] | 8.8% | 13.7% | 12.9% / 3.6% | 0.278 / 0.229 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | responses | request_bytes | wire | bytes | 12 | 125,406 | 124,200 | 0.99 [0.99, 0.99] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` |
| overhead/print-tools | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 13,934 | 13,800 | 0.99 [0.99, 0.99] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | responses | teardown_ms | wall | ms | 12 | 16.9 | 13.1 | 0.774 [0.671, 0.833] | 16.7% | 11.8% | 14.1% / 6.6% | 2.81 / 0.944 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` |
| overhead/print-tools | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 10.1 | 6.26 | 0.617 [0.537, 0.654] | 14.1% | 10.2% | 11.6% / 6.3% | 1.47 / 0.41 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` |
| overhead/print-tools | responses | turn_gap_ms | wall | ms | 12 | 4.05 | 3.24 | 0.8 [0.765, 0.841] | 9.5% | 11.0% | 14.8% / 4.5% | 0.24 / 0.154 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` |
| overhead/rpc | anthropic | request_bytes | wire | bytes | 12 | 1.13M | 1.13M | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes` |
| overhead/rpc | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 56,537 | 56,257 | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes_per_turn` |
| overhead/rpc | anthropic | turn_harness_added_ms | wall | ms | 12 | 0.686 | 0.543 | 0.791 [0.743, 0.844] | 10.7% | 3.0% | 3.6% / 18.5% | 0.0182 / 0.0702 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_harness_added_ms` |
| overhead/rpc | chat | request_bytes | wire | bytes | 12 | 1.11M | 1.11M | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes` |
| overhead/rpc | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 55,652 | 55,372 | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes_per_turn` |
| overhead/rpc | chat | turn_harness_added_ms | wall | ms | 12 | 0.874 | 0.683 | 0.782 [0.758, 0.823] | 11.2% | 3.2% | 3.7% / 6.6% | 0.0447 / 0.038 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_harness_added_ms` |
| overhead/rpc | responses | request_bytes | wire | bytes | 12 | 1.14M | 1.13M | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes` |
| overhead/rpc | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 57,018 | 56,738 | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes_per_turn` |
| overhead/rpc | responses | turn_harness_added_ms | wall | ms | 12 | 0.885 | 0.753 | 0.851 [0.766, 0.92] | 17.1% | 3.4% | 3.9% / 14.3% | 0.0234 / 0.112 | 1 / 0 | 0.00439 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_harness_added_ms` |

## pibolt against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 7,976 | 1.32 [1.32, 1.32] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 7,976 | 1.32 [1.32, 1.32] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print | responses | request_bytes | wire | bytes | 12 | 6,024 | 7,915 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` |
| overhead/print | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 6,024 | 7,915 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` |
| overhead/print | anthropic | request_bytes | wire | bytes | 12 | 6,114 | 8,031 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` |
| overhead/print | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 6,114 | 8,031 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 144,018 | 1.14 [1.14, 1.14] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 16,002 | 1.14 [1.14, 1.14] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/print-tools | responses | request_bytes | wire | bytes | 12 | 125,406 | 142,389 | 1.14 [1.14, 1.14] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` |
| overhead/print-tools | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 13,934 | 15,821 | 1.14 [1.14, 1.14] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | anthropic | request_bytes | wire | bytes | 12 | 127,836 | 145,053 | 1.13 [1.13, 1.13] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` |
| overhead/print-tools | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 14,204 | 16,117 | 1.13 [1.13, 1.13] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` |
| overhead/rpc | chat | request_bytes | wire | bytes | 12 | 1.11M | 1.19M | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes` |
| overhead/rpc | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 55,652 | 59,466 | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes_per_turn` |
| overhead/rpc | anthropic | request_bytes | wire | bytes | 12 | 1.13M | 1.21M | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes` |
| overhead/rpc | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 56,537 | 60,351 | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes_per_turn` |
| overhead/rpc | responses | request_bytes | wire | bytes | 12 | 1.14M | 1.22M | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes` |
| overhead/rpc | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 57,018 | 60,780 | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` |
| overhead/print | chat | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print | responses | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` |
| overhead/print-tools | anthropic | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |
| overhead/print-tools | responses | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` |
| overhead/rpc | anthropic | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#requests` |
| overhead/rpc | chat | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#requests` |
| overhead/rpc | responses | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 421 | 43.5 | 0.103 [0.102, 0.104] | 3.0% | 1.5% | 1.1% / 0.8% | 5.92 / 0.36 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` |
| overhead/print | anthropic | cycles | CPU | cycles | 12 | 1167.02M | 112.06M | 0.096 [0.0949, 0.0964] | 2.3% | 1.4% | 1.1% / 0.6% | 16,040,830 / 743,954 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` |
| overhead/print | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 401 | 39.4 | 0.0982 [0.097, 0.0986] | 2.3% | 1.5% | 1.1% / 0.6% | 5.73 / 0.305 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` |
| overhead/print | anthropic | first_request_ms | wall | ms | 12 | 292 | 35.9 | 0.123 [0.122, 0.123] | 2.5% | 1.2% | 1.3% / 0.5% | 2.25 / 0.276 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` |
| overhead/print | anthropic | instructions | CPU | instructions | 12 | 2323.75M | 171.21M | 0.0737 [0.0734, 0.0738] | 1.6% | 0.4% | 0.3% / 0.3% | 7,910,528 / 569,631 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` |
| overhead/print | anthropic | peak_mem_mib | memory | MiB | 12 | 62.8 | 18.3 | 0.291 [0.29, 0.296] | 1.6% | 1.3% | 1.1% / 1.0% | 1.07 / 0.128 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` |
| overhead/print | anthropic | peak_rss_mib | memory | MiB | 12 | 114 | 78.5 | 0.691 [0.689, 0.697] | 1.1% | 0.8% | 0.8% / 0.1% | 1.16 / 0.141 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` |
| overhead/print | anthropic | teardown_ms | wall | ms | 12 | 17.5 | 3.17 | 0.181 [0.179, 0.187] | 15.7% | 2.4% | 1.5% / 3.1% | 0.274 / 0.109 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` |
| overhead/print | anthropic | wall_ms | wall | ms | 12 | 311 | 39.6 | 0.127 [0.127, 0.128] | 3.2% | 1.2% | 1.3% / 0.4% | 1.83 / 0.146 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` |
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 44.3 | 0.104 [0.102, 0.106] | 4.4% | 1.9% | 1.6% / 1.2% | 12.1 / 0.669 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 113.75M | 0.0959 [0.0946, 0.0973] | 2.7% | 1.8% | 1.6% / 0.8% | 29,576,145 / 671,742 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 40.2 | 0.0994 [0.0979, 0.101] | 3.3% | 1.9% | 1.6% / 1.1% | 10.4 / 0.768 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 36.2 | 0.123 [0.122, 0.124] | 2.4% | 2.1% | 1.7% / 0.6% | 3.48 / 0.201 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 173.31M | 0.0738 [0.0736, 0.0741] | 1.6% | 0.2% | 0.4% / 0.3% | 7,542,734 / 627,771 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 18.9 | 0.297 [0.293, 0.299] | 2.4% | 1.8% | 1.3% / 1.2% | 0.479 / 0.276 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 78.6 | 0.688 [0.687, 0.69] | 1.0% | 0.5% | 0.4% / 0.2% | 0.556 / 0.0947 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 3.37 | 0.167 [0.163, 0.174] | 19.3% | 3.3% | 3.9% / 5.1% | 0.437 / 0.148 | 2 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 40.0 | 0.127 [0.126, 0.128] | 3.4% | 2.0% | 1.6% / 0.8% | 4.4 / 0.26 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/print | responses | cpu_ms | CPU | ms of CPU time | 12 | 425 | 44.0 | 0.104 [0.102, 0.104] | 2.8% | 2.9% | 1.4% / 0.6% | 6.78 / 0.271 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` |
| overhead/print | responses | cycles | CPU | cycles | 12 | 1178.05M | 113.97M | 0.0967 [0.0957, 0.0973] | 2.3% | 2.9% | 1.4% / 0.5% | 17,455,521 / 660,502 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` |
| overhead/print | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 40.2 | 0.1 [0.0989, 0.101] | 2.5% | 3.0% | 1.4% / 0.6% | 6.78 / 0.302 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` |
| overhead/print | responses | first_request_ms | wall | ms | 12 | 295 | 36.4 | 0.124 [0.121, 0.125] | 3.0% | 2.5% | 1.5% / 0.5% | 6.14 / 0.113 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` |
| overhead/print | responses | instructions | CPU | instructions | 12 | 2351.19M | 174.18M | 0.0741 [0.0739, 0.0742] | 1.5% | 0.4% | 0.4% / 0.3% | 4,128,707 / 550,901 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` |
| overhead/print | responses | peak_mem_mib | memory | MiB | 12 | 63.5 | 18.5 | 0.292 [0.291, 0.294] | 0.9% | 0.8% | 0.9% / 0.7% | 0.704 / 0.0186 | 0 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` |
| overhead/print | responses | peak_rss_mib | memory | MiB | 12 | 114 | 78.5 | 0.688 [0.68, 0.692] | 1.1% | 1.0% | 1.4% / 0.1% | 1.35 / 0.102 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` |
| overhead/print | responses | teardown_ms | wall | ms | 12 | 20.8 | 3.29 | 0.159 [0.156, 0.16] | 14.0% | 1.6% | 0.8% / 1.5% | 0.104 / 0.0762 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` |
| overhead/print | responses | wall_ms | wall | ms | 12 | 316 | 40.2 | 0.127 [0.125, 0.128] | 3.7% | 2.4% | 1.4% / 0.4% | 6.06 / 0.135 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` |
| overhead/print-tools | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 508 | 54.8 | 0.108 [0.106, 0.108] | 2.9% | 1.4% | 2.6% / 1.1% | 7.39 / 0.237 | 1 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` |
| overhead/print-tools | anthropic | cycles | CPU | cycles | 12 | 1406.22M | 142.73M | 0.101 [0.1, 0.102] | 2.4% | 1.4% | 2.6% / 0.5% | 20,029,746 / 432,099 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` |
| overhead/print-tools | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 398 | 39.5 | 0.0992 [0.0979, 0.0996] | 2.8% | 1.2% | 1.5% / 0.6% | 5.99 / 0.318 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` |
| overhead/print-tools | anthropic | first_request_ms | wall | ms | 12 | 292 | 36.0 | 0.123 [0.122, 0.124] | 3.5% | 0.9% | 1.4% / 0.6% | 2.82 / 0.309 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` |
| overhead/print-tools | anthropic | instructions | CPU | instructions | 12 | 2745.09M | 205.33M | 0.0748 [0.0745, 0.0749] | 1.5% | 0.2% | 0.2% / 0.3% | 8,283,082 / 685,116 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` |
| overhead/print-tools | anthropic | peak_mem_mib | memory | MiB | 12 | 86.0 | 21.0 | 0.244 [0.243, 0.249] | 1.8% | 1.2% | 1.3% / 0.9% | 1.89 / 0.268 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | anthropic | peak_rss_mib | memory | MiB | 12 | 135 | 78.5 | 0.583 [0.575, 0.588] | 1.6% | 1.0% | 1.2% / 0.1% | 2.82 / 0.0977 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` |
| overhead/print-tools | anthropic | teardown_ms | wall | ms | 12 | 20.2 | 3.09 | 0.153 [0.145, 0.167] | 15.8% | 12.9% | 7.9% / 2.7% | 2.61 / 0.0301 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 8.9 | 1.3 | 0.146 [0.143, 0.148] | 2.8% | 6.7% | 10.2% / 1.7% | 0.219 / 0.0148 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` |
| overhead/print-tools | anthropic | turn_gap_ms | wall | ms | 12 | 3.7 | 1.09 | 0.296 [0.291, 0.3] | 2.6% | 7.4% | 12.0% / 1.0% | 0.0789 / 0.0165 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` |
| overhead/print-tools | anthropic | wall_ms | wall | ms | 12 | 357 | 52.0 | 0.146 [0.145, 0.146] | 3.4% | 1.1% | 2.2% / 0.5% | 1.96 / 0.296 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 56.4 | 0.109 [0.108, 0.111] | 3.0% | 2.0% | 1.8% / 1.7% | 6.54 / 0.89 | 1 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 146.76M | 0.102 [0.101, 0.104] | 2.6% | 2.1% | 1.8% / 1.5% | 17,345,646 / 2,173,610 | 1 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 40.2 | 0.101 [0.1, 0.102] | 2.5% | 1.4% | 0.9% / 1.4% | 2.98 / 0.364 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 36.4 | 0.124 [0.123, 0.125] | 2.6% | 1.6% | 1.3% / 1.1% | 2.5 / 0.292 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 210.26M | 0.0756 [0.0754, 0.0758] | 1.4% | 0.3% | 0.2% / 0.3% | 5,500,458 / 590,617 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 21.7 | 0.251 [0.249, 0.253] | 1.3% | 1.0% | 0.7% / 0.8% | 0.521 / 0.275 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 78.5 | 0.58 [0.576, 0.583] | 1.1% | 1.0% | 0.9% / 0.2% | 1.46 / 0.0703 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 3.23 | 0.168 [0.157, 0.183] | 16.3% | 12.4% | 9.6% / 11.4% | 2.05 / 0.122 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 1.41 | 0.148 [0.139, 0.154] | 9.9% | 12.1% | 10.8% / 3.3% | 0.84 / 0.0379 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 1.19 | 0.296 [0.285, 0.314] | 8.5% | 13.7% | 12.9% / 3.1% | 0.278 / 0.0258 | 1 / 2 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 53.3 | 0.147 [0.147, 0.15] | 3.0% | 2.0% | 1.8% / 1.8% | 4.8 / 0.742 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/print-tools | responses | cpu_ms | CPU | ms of CPU time | 12 | 522 | 56.9 | 0.109 [0.107, 0.11] | 3.4% | 2.5% | 3.3% / 0.8% | 9.6 / 0.535 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` |
| overhead/print-tools | responses | cycles | CPU | cycles | 12 | 1445.29M | 148.01M | 0.102 [0.101, 0.103] | 2.4% | 2.6% | 3.2% / 0.5% | 25,635,734 / 726,464 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` |
| overhead/print-tools | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 40.3 | 0.1 [0.099, 0.101] | 3.7% | 1.4% | 1.4% / 1.1% | 5.71 / 0.423 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` |
| overhead/print-tools | responses | first_request_ms | wall | ms | 12 | 295 | 36.5 | 0.124 [0.122, 0.125] | 3.4% | 1.6% | 1.6% / 0.6% | 5.1 / 0.288 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` |
| overhead/print-tools | responses | instructions | CPU | instructions | 12 | 2792.76M | 212.01M | 0.0759 [0.0757, 0.076] | 1.2% | 0.2% | 0.2% / 0.2% | 6,452,716 / 502,511 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` |
| overhead/print-tools | responses | peak_mem_mib | memory | MiB | 12 | 86.0 | 21.8 | 0.254 [0.251, 0.256] | 1.6% | 1.2% | 0.9% / 1.2% | 1.16 / 0.237 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` |
| overhead/print-tools | responses | peak_rss_mib | memory | MiB | 12 | 135 | 78.5 | 0.582 [0.577, 0.584] | 1.3% | 1.1% | 0.9% / 0.2% | 1.29 / 0.269 | 0 / 4 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` |
| overhead/print-tools | responses | teardown_ms | wall | ms | 12 | 16.9 | 3.19 | 0.189 [0.167, 0.198] | 16.7% | 11.8% | 14.1% / 2.0% | 2.81 / 0.049 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` |
| overhead/print-tools | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 10.1 | 1.45 | 0.143 [0.129, 0.15] | 14.1% | 10.2% | 11.6% / 0.6% | 1.47 / 0.00737 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` |
| overhead/print-tools | responses | turn_gap_ms | wall | ms | 12 | 4.05 | 1.18 | 0.29 [0.278, 0.297] | 4.2% | 11.0% | 14.8% / 1.4% | 0.24 / 0.00955 | 2 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` |
| overhead/print-tools | responses | wall_ms | wall | ms | 12 | 362 | 53.6 | 0.148 [0.146, 0.149] | 3.4% | 2.4% | 2.8% / 0.5% | 5.7 / 0.335 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` |
| overhead/rpc | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 637 | 104 | 0.164 [0.16, 0.164] | 2.0% | 2.9% | 3.3% / 1.5% | 12.7 / 0.991 | 2 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cpu_ms` |
| overhead/rpc | anthropic | cycles | CPU | cycles | 12 | 1756.48M | 276.12M | 0.157 [0.154, 0.158] | 2.1% | 2.9% | 3.3% / 1.4% | 34,415,458 / 1,664,058 | 2 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cycles` |
| overhead/rpc | anthropic | instructions | CPU | instructions | 12 | 3209.13M | 382.64M | 0.119 [0.119, 0.119] | 0.7% | 0.3% | 0.2% / 0.2% | 7,831,587 / 1,100,380 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#instructions` |
| overhead/rpc | anthropic | peak_mem_mib | memory | MiB | 12 | 86.2 | 29.2 | 0.339 [0.334, 0.342] | 2.0% | 1.1% | 1.0% / 1.2% | 1.05 / 0.521 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_mem_mib` |
| overhead/rpc | anthropic | peak_rss_mib | memory | MiB | 12 | 139 | 101 | 0.725 [0.723, 0.727] | 0.7% | 0.6% | 0.7% / 0.2% | 0.745 / 0.25 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_rss_mib` |
| overhead/rpc | anthropic | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 37.1 | 0.0999 [0.0984, 0.101] | 2.7% | 1.7% | 1.6% / 1.4% | 9.15 / 0.291 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_cpu_ms` |
| overhead/rpc | anthropic | ready_ms | wall | ms | 12 | 264 | 33.2 | 0.126 [0.125, 0.127] | 2.8% | 2.1% | 1.4% / 1.0% | 2.27 / 0.147 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_ms` |
| overhead/rpc | anthropic | ready_pss_mib | memory | MiB | 12 | 107 | 80.9 | 0.754 [0.751, 0.757] | 1.3% | 0.8% | 0.7% / 0.1% | 0.59 / 0.0776 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_pss_mib` |
| overhead/rpc | anthropic | ready_rss_mib | memory | MiB | 12 | 113 | 85.2 | 0.756 [0.754, 0.759] | 1.2% | 0.8% | 0.7% / 0.1% | 0.591 / 0.082 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_rss_mib` |
| overhead/rpc | anthropic | teardown_ms | wall | ms | 12 | 8.72 | 3.8 | 0.436 [0.407, 0.451] | 14.3% | 9.4% | 5.4% / 3.9% | 0.698 / 0.179 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#teardown_ms` |
| overhead/rpc | anthropic | turn_cpu_mean_ms | wall | ms | 12 | 10.3 | 2.99 | 0.29 [0.286, 0.293] | 2.3% | 5.6% | 6.7% / 1.9% | 0.232 / 0.0215 | 2 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_mean_ms` |
| overhead/rpc | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.08 | 2.64 | 0.29 [0.286, 0.302] | 6.2% | 4.8% | 4.1% / 2.9% | 0.466 / 0.0392 | 0 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_ms` |
| overhead/rpc | anthropic | turn_harness_added_ms | wall | ms | 12 | 0.686 | 0.114 | 0.166 [0.161, 0.171] | 4.0% | 3.0% | 3.6% / 13.8% | 0.0182 / 0.00399 | 1 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_harness_added_ms` |
| overhead/rpc | anthropic | turn_turn_gap_ms | wall | ms | 12 | 3.03 | 1.17 | 0.386 [0.377, 0.391] | 3.3% | 2.7% | 2.6% / 2.6% | 0.0798 / 0.0257 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_turn_gap_ms` |
| overhead/rpc | anthropic | turn_wall_ms | wall | ms | 12 | 6.79 | 3.31 | 0.488 [0.481, 0.495] | 2.6% | 2.1% | 2.9% / 1.3% | 0.159 / 0.0587 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_wall_ms` |
| overhead/rpc | chat | cpu_ms | CPU | ms of CPU time | 12 | 676 | 108 | 0.16 [0.158, 0.162] | 4.5% | 2.5% | 2.5% / 0.9% | 13.2 / 0.937 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cpu_ms` |
| overhead/rpc | chat | cycles | CPU | cycles | 12 | 1863.43M | 286.63M | 0.154 [0.152, 0.156] | 4.3% | 2.5% | 2.5% / 0.8% | 34,831,120 / 1,658,293 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cycles` |
| overhead/rpc | chat | instructions | CPU | instructions | 12 | 3343.17M | 396.04M | 0.118 [0.118, 0.119] | 0.7% | 0.4% | 0.3% / 0.2% | 10,954,495 / 1,168,297 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#instructions` |
| overhead/rpc | chat | peak_mem_mib | memory | MiB | 12 | 89.1 | 30.1 | 0.337 [0.335, 0.339] | 0.9% | 0.9% | 0.8% / 0.7% | 0.892 / 0.241 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_mem_mib` |
| overhead/rpc | chat | peak_rss_mib | memory | MiB | 12 | 142 | 102 | 0.714 [0.713, 0.716] | 0.5% | 0.5% | 0.4% / 0.1% | 0.7 / 0.165 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_rss_mib` |
| overhead/rpc | chat | ready_cpu_ms | CPU | ms of CPU time | 12 | 369 | 37.0 | 0.1 [0.0983, 0.101] | 1.9% | 1.6% | 1.8% / 0.4% | 8.23 / 0.233 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_cpu_ms` |
| overhead/rpc | chat | ready_ms | wall | ms | 12 | 263 | 33.2 | 0.126 [0.125, 0.127] | 2.3% | 1.3% | 1.5% / 0.9% | 4.82 / 0.273 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_ms` |
| overhead/rpc | chat | ready_pss_mib | memory | MiB | 12 | 107 | 80.9 | 0.757 [0.755, 0.76] | 0.8% | 1.1% | 0.6% / 0.1% | 0.724 / 0.0679 | 0 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_pss_mib` |
| overhead/rpc | chat | ready_rss_mib | memory | MiB | 12 | 112 | 85.2 | 0.759 [0.757, 0.762] | 0.8% | 1.0% | 0.5% / 0.1% | 0.777 / 0.111 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_rss_mib` |
| overhead/rpc | chat | teardown_ms | wall | ms | 12 | 8.62 | 3.96 | 0.46 [0.402, 0.486] | 23.7% | 9.6% | 7.7% / 8.2% | 1.05 / 0.477 | 4 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#teardown_ms` |
| overhead/rpc | chat | turn_cpu_mean_ms | wall | ms | 12 | 11.9 | 3.14 | 0.265 [0.258, 0.266] | 4.3% | 5.9% | 4.2% / 1.5% | 0.206 / 0.033 | 1 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.2 | 2.78 | 0.248 [0.245, 0.256] | 3.5% | 3.9% | 3.0% / 1.8% | 0.472 / 0.0183 | 0 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_ms` |
| overhead/rpc | chat | turn_harness_added_ms | wall | ms | 12 | 0.874 | 0.207 | 0.237 [0.232, 0.247] | 5.3% | 3.2% | 3.7% / 5.6% | 0.0447 / 0.0025 | 0 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_harness_added_ms` |
| overhead/rpc | chat | turn_turn_gap_ms | wall | ms | 12 | 3.25 | 1.31 | 0.403 [0.392, 0.407] | 4.4% | 2.4% | 3.0% / 1.8% | 0.0711 / 0.0275 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_turn_gap_ms` |
| overhead/rpc | chat | turn_wall_ms | wall | ms | 12 | 7.32 | 3.36 | 0.459 [0.453, 0.471] | 3.3% | 2.8% | 2.3% / 2.2% | 0.196 / 0.0627 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_wall_ms` |
| overhead/rpc | responses | cpu_ms | CPU | ms of CPU time | 12 | 680 | 110 | 0.162 [0.16, 0.166] | 3.4% | 1.7% | 1.3% / 1.8% | 12.3 / 2.23 | 0 / 3 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cpu_ms` |
| overhead/rpc | responses | cycles | CPU | cycles | 12 | 1874.58M | 293.45M | 0.157 [0.154, 0.16] | 2.7% | 1.6% | 1.2% / 1.8% | 31,582,812 / 4,893,925 | 0 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cycles` |
| overhead/rpc | responses | instructions | CPU | instructions | 12 | 3379.56M | 405.91M | 0.12 [0.12, 0.12] | 0.7% | 0.3% | 0.2% / 0.2% | 10,393,734 / 547,194 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#instructions` |
| overhead/rpc | responses | peak_mem_mib | memory | MiB | 12 | 90.6 | 29.9 | 0.331 [0.328, 0.334] | 1.4% | 1.3% | 1.1% / 0.9% | 0.707 / 0.398 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_mem_mib` |
| overhead/rpc | responses | peak_rss_mib | memory | MiB | 12 | 144 | 102 | 0.709 [0.707, 0.712] | 0.7% | 0.7% | 0.6% / 0.1% | 0.756 / 0.204 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_rss_mib` |
| overhead/rpc | responses | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 37.0 | 0.0997 [0.0985, 0.101] | 3.0% | 1.5% | 1.3% / 1.6% | 6.56 / 0.523 | 0 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_cpu_ms` |
| overhead/rpc | responses | ready_ms | wall | ms | 12 | 265 | 33.2 | 0.125 [0.124, 0.127] | 2.9% | 1.1% | 0.8% / 1.3% | 1.84 / 0.333 | 0 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_ms` |
| overhead/rpc | responses | ready_pss_mib | memory | MiB | 12 | 107 | 80.9 | 0.756 [0.751, 0.758] | 0.8% | 0.6% | 0.8% / 0.1% | 1.06 / 0.0759 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_pss_mib` |
| overhead/rpc | responses | ready_rss_mib | memory | MiB | 12 | 112 | 85.1 | 0.757 [0.753, 0.76] | 0.8% | 0.5% | 0.7% / 0.1% | 1.06 / 0.0703 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_rss_mib` |
| overhead/rpc | responses | teardown_ms | wall | ms | 12 | 9.51 | 3.81 | 0.4 [0.366, 0.442] | 15.9% | 9.0% | 7.4% / 7.8% | 1.33 / 0.201 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#teardown_ms` |
| overhead/rpc | responses | turn_cpu_mean_ms | wall | ms | 12 | 12.1 | 3.26 | 0.269 [0.265, 0.279] | 2.8% | 3.0% | 2.5% / 2.1% | 0.453 / 0.0668 | 0 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_mean_ms` |
| overhead/rpc | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.0 | 2.92 | 0.266 [0.257, 0.289] | 10.4% | 8.7% | 7.4% / 2.7% | 1.2 / 0.0641 | 0 / 3 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_ms` |
| overhead/rpc | responses | turn_harness_added_ms | wall | ms | 12 | 0.885 | 0.123 | 0.139 [0.134, 0.145] | 8.3% | 3.4% | 3.9% / 14.1% | 0.0234 / 0.00695 | 1 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_harness_added_ms` |
| overhead/rpc | responses | turn_turn_gap_ms | wall | ms | 12 | 3.29 | 1.28 | 0.389 [0.385, 0.399] | 2.9% | 2.8% | 1.5% / 2.0% | 0.0715 / 0.0335 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_turn_gap_ms` |
| overhead/rpc | responses | turn_wall_ms | wall | ms | 12 | 7.46 | 3.51 | 0.47 [0.463, 0.475] | 3.0% | 3.1% | 2.1% / 1.2% | 0.175 / 0.0305 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_wall_ms` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 10.9 | 0.0387 [0.0383, 0.0389] | 6.8% | 1.7% | 1.0% / 1.6% | 2.84 / 0.198 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 26.04M | 0.0338 [0.0336, 0.034] | 5.1% | 1.7% | 0.9% / 0.8% | 5,972,803 / 263,176 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 35.04M | 0.0214 [0.0214, 0.0215] | 2.8% | 0.2% | 0.3% / 0.1% | 3,727,566 / 54,032 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 6.5 | 0.113 [0.112, 0.113] | 1.5% | 1.6% | 1.1% / 0.3% | 0.617 / 0.00391 | 0 / 2 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 5.08 | 0.0474 [0.0468, 0.0478] | 1.5% | 1.3% | 1.1% / 2.4% | 1.61 / 0.0508 | 0 / 3 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 9.8 | 0.0449 [0.0444, 0.0452] | 6.8% | 1.4% | 1.2% / 0.9% | 3.07 / 0.133 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## pig-0.4.1 against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/rpc | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.08 | 17.7 | 1.95 [1.91, 2.05] | 6.2% | 4.8% | 4.1% / 3.8% | 0.466 / 1.12 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_ms` |
| overhead/rpc | anthropic | turn_cpu_mean_ms | wall | ms | 12 | 10.3 | 19.2 | 1.86 [1.83, 1.88] | 2.3% | 5.6% | 6.7% / 1.4% | 0.232 / 0.384 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_mean_ms` |
| overhead/rpc | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.0 | 20.3 | 1.85 [1.74, 2.01] | 10.4% | 8.7% | 7.4% / 5.5% | 1.2 / 2 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_ms` |
| overhead/rpc | anthropic | turn_wall_ms | wall | ms | 12 | 6.79 | 11.7 | 1.72 [1.69, 1.76] | 2.6% | 2.1% | 2.9% / 1.4% | 0.159 / 0.239 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_wall_ms` |
| overhead/rpc | anthropic | turn_turn_gap_ms | wall | ms | 12 | 3.03 | 5.19 | 1.72 [1.67, 1.74] | 3.3% | 2.7% | 2.6% / 1.5% | 0.0798 / 0.106 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_turn_gap_ms` |
| overhead/rpc | responses | turn_cpu_mean_ms | wall | ms | 12 | 12.1 | 20.1 | 1.66 [1.62, 1.7] | 2.8% | 3.0% | 2.5% / 1.3% | 0.453 / 0.379 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_mean_ms` |
| overhead/rpc | responses | turn_wall_ms | wall | ms | 12 | 7.46 | 12.3 | 1.65 [1.62, 1.68] | 3.0% | 3.1% | 2.1% / 2.2% | 0.175 / 0.401 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_wall_ms` |
| overhead/rpc | responses | turn_turn_gap_ms | wall | ms | 12 | 3.29 | 5.32 | 1.62 [1.59, 1.66] | 3.0% | 2.8% | 1.5% / 2.0% | 0.0715 / 0.132 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_turn_gap_ms` |
| overhead/rpc | chat | turn_wall_ms | wall | ms | 12 | 7.32 | 11.8 | 1.62 [1.6, 1.65] | 3.3% | 2.8% | 2.3% / 1.8% | 0.196 / 0.244 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_wall_ms` |
| overhead/rpc | chat | turn_turn_gap_ms | wall | ms | 12 | 3.25 | 5.25 | 1.61 [1.56, 1.65] | 4.4% | 2.4% | 3.0% / 2.5% | 0.0711 / 0.208 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_turn_gap_ms` |
| overhead/rpc | chat | turn_cpu_mean_ms | wall | ms | 12 | 11.9 | 18.9 | 1.59 [1.56, 1.61] | 4.3% | 5.9% | 4.2% / 1.1% | 0.206 / 0.292 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.2 | 17.7 | 1.58 [1.54, 1.63] | 3.5% | 3.9% | 3.0% / 3.0% | 0.472 / 0.612 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_ms` |
| overhead/rpc | anthropic | turn_harness_added_ms | wall | ms | 12 | 0.686 | 0.829 | 1.21 [1.18, 1.24] | 4.2% | 3.0% | 3.6% / 2.6% | 0.0182 / 0.036 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_harness_added_ms` |
| overhead/rpc | responses | turn_harness_added_ms | wall | ms | 12 | 0.885 | 0.949 | 1.07 [1.05, 1.11] | 3.9% | 3.4% | 3.9% / 2.5% | 0.0234 / 0.021 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_harness_added_ms` |
| overhead/rpc | chat | turn_harness_added_ms | wall | ms | 12 | 0.874 | 0.928 | 1.06 [1.04, 1.11] | 5.3% | 3.2% | 3.7% / 3.0% | 0.0447 / 0.0426 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_harness_added_ms` |
| overhead/print-tools | anthropic | request_bytes | wire | bytes | 12 | 127,836 | 128,007 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` |
| overhead/print-tools | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 14,204 | 14,223 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` |
| overhead/print-tools | responses | request_bytes | wire | bytes | 12 | 125,406 | 125,523 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` |
| overhead/print-tools | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 13,934 | 13,947 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 126,918 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 14,102 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/rpc | anthropic | request_bytes | wire | bytes | 12 | 1.13M | 1.13M | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes` |
| overhead/rpc | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 56,537 | 56,567 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes_per_turn` |
| overhead/rpc | chat | request_bytes | wire | bytes | 12 | 1.11M | 1.11M | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes` |
| overhead/rpc | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 55,652 | 55,670 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes_per_turn` |
| overhead/rpc | responses | request_bytes | wire | bytes | 12 | 1.14M | 1.14M | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes` |
| overhead/rpc | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 57,018 | 57,036 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes_per_turn` |

### Inconclusive (outside the floor, interval includes 1)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-tools | anthropic | turn_gap_ms | wall | ms | 12 | 3.7 | 4.06 | 1.1 [1.06, 1.15] | 7.2% | 7.4% | 12.0% / 5.8% | 0.0789 / 0.258 | 1 / 0 | 0.0664 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` |
| overhead/print | chat | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print | responses | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` |
| overhead/print-tools | anthropic | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 4.13 | 1.03 [0.989, 1.09] | 8.5% | 13.7% | 12.9% / 3.6% | 0.278 / 0.185 | 1 / 0 | 0.736 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | responses | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` |
| overhead/print-tools | responses | turn_gap_ms | wall | ms | 12 | 4.05 | 4.23 | 1.05 [0.98, 1.08] | 5.5% | 11.0% | 14.8% / 4.0% | 0.24 / 0.173 | 2 / 0 | 0.991 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` |
| overhead/rpc | anthropic | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#requests` |
| overhead/rpc | chat | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#requests` |
| overhead/rpc | responses | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 421 | 63.5 | 0.151 [0.141, 0.155] | 6.9% | 1.5% | 1.1% / 4.6% | 5.92 / 5.07 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` |
| overhead/print | anthropic | cycles | CPU | cycles | 12 | 1167.02M | 162.15M | 0.139 [0.129, 0.141] | 6.0% | 1.4% | 1.1% / 4.4% | 16,040,830 / 12,413,129 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` |
| overhead/print | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 401 | 57.9 | 0.144 [0.135, 0.146] | 6.9% | 1.5% | 1.1% / 4.1% | 5.73 / 4.23 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` |
| overhead/print | anthropic | first_request_ms | wall | ms | 12 | 292 | 33.3 | 0.114 [0.112, 0.116] | 4.2% | 1.2% | 1.3% / 1.8% | 2.25 / 0.663 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` |
| overhead/print | anthropic | instructions | CPU | instructions | 12 | 2323.75M | 264.75M | 0.114 [0.106, 0.115] | 6.5% | 0.4% | 0.3% / 4.2% | 7,910,528 / 20,401,230 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` |
| overhead/print | anthropic | peak_mem_mib | memory | MiB | 12 | 62.8 | 16.4 | 0.261 [0.258, 0.266] | 2.2% | 1.3% | 1.1% / 1.3% | 1.07 / 0.257 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` |
| overhead/print | anthropic | peak_rss_mib | memory | MiB | 12 | 114 | 40.9 | 0.36 [0.358, 0.364] | 1.2% | 0.8% | 0.8% / 1.4% | 1.16 / 0.413 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` |
| overhead/print | anthropic | request_bytes | wire | bytes | 12 | 6,114 | 6,113 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` |
| overhead/print | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 6,114 | 6,113 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` |
| overhead/print | anthropic | teardown_ms | wall | ms | 12 | 17.5 | 3.03 | 0.173 [0.164, 0.183] | 16.0% | 2.4% | 1.5% / 8.3% | 0.274 / 0.3 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` |
| overhead/print | anthropic | wall_ms | wall | ms | 12 | 311 | 36.8 | 0.119 [0.116, 0.12] | 4.2% | 1.2% | 1.3% / 2.0% | 1.83 / 1.07 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` |
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 63.4 | 0.148 [0.145, 0.152] | 3.2% | 1.9% | 1.6% / 2.9% | 12.1 / 2.05 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 162.46M | 0.137 [0.135, 0.139] | 2.7% | 1.8% | 1.6% / 3.2% | 29,576,145 / 2,011,546 | 0 / 2 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 56.0 | 0.138 [0.131, 0.145] | 9.5% | 1.9% | 1.6% / 5.3% | 10.4 / 5.15 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 32.9 | 0.112 [0.109, 0.114] | 2.8% | 2.1% | 1.7% / 2.4% | 3.48 / 1.22 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 264.84M | 0.113 [0.112, 0.114] | 1.2% | 0.2% | 0.4% / 3.3% | 7,542,734 / 3,478,673 | 0 / 2 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 16.5 | 0.26 [0.254, 0.263] | 4.1% | 1.8% | 1.3% / 2.2% | 0.479 / 0.523 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 40.9 | 0.358 [0.356, 0.361] | 0.9% | 0.5% | 0.4% / 0.8% | 0.556 / 0.511 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 6,052 | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 6,052 | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 3.15 | 0.156 [0.137, 0.189] | 41.6% | 3.3% | 3.9% / 17.7% | 0.437 / 0.933 | 2 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 36.4 | 0.115 [0.115, 0.117] | 1.7% | 2.0% | 1.6% / 1.6% | 4.4 / 0.329 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/print | responses | cpu_ms | CPU | ms of CPU time | 12 | 425 | 64.2 | 0.151 [0.149, 0.155] | 5.4% | 2.9% | 1.4% / 2.3% | 6.78 / 1.81 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` |
| overhead/print | responses | cycles | CPU | cycles | 12 | 1178.05M | 164.11M | 0.139 [0.137, 0.142] | 3.0% | 2.9% | 1.4% / 2.4% | 17,455,521 / 4,016,226 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` |
| overhead/print | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 58.3 | 0.145 [0.143, 0.149] | 4.4% | 3.0% | 1.4% / 2.9% | 6.78 / 2.02 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` |
| overhead/print | responses | first_request_ms | wall | ms | 12 | 295 | 33.6 | 0.114 [0.111, 0.116] | 4.2% | 2.5% | 1.5% / 1.9% | 6.14 / 0.971 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` |
| overhead/print | responses | instructions | CPU | instructions | 12 | 2351.19M | 267.17M | 0.114 [0.113, 0.114] | 1.5% | 0.4% | 0.4% / 1.8% | 4,128,707 / 1,056,944 | 1 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` |
| overhead/print | responses | peak_mem_mib | memory | MiB | 12 | 63.5 | 16.4 | 0.259 [0.257, 0.263] | 4.0% | 0.8% | 0.9% / 2.1% | 0.704 / 0.312 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` |
| overhead/print | responses | peak_rss_mib | memory | MiB | 12 | 114 | 40.9 | 0.359 [0.354, 0.362] | 1.2% | 1.0% | 1.4% / 0.6% | 1.35 / 0.22 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` |
| overhead/print | responses | request_bytes | wire | bytes | 12 | 6,024 | 6,017 | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` |
| overhead/print | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 6,024 | 6,017 | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` |
| overhead/print | responses | teardown_ms | wall | ms | 12 | 20.8 | 3.19 | 0.153 [0.145, 0.16] | 23.9% | 1.6% | 0.8% / 7.3% | 0.104 / 0.239 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` |
| overhead/print | responses | wall_ms | wall | ms | 12 | 316 | 37.5 | 0.119 [0.115, 0.119] | 5.1% | 2.4% | 1.4% / 1.7% | 6.06 / 1.08 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` |
| overhead/print-tools | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 508 | 118 | 0.233 [0.227, 0.237] | 2.9% | 1.4% | 2.6% / 3.0% | 7.39 / 3.37 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` |
| overhead/print-tools | anthropic | cycles | CPU | cycles | 12 | 1406.22M | 309.69M | 0.22 [0.216, 0.222] | 1.4% | 1.4% | 2.6% / 2.0% | 20,029,746 / 5,733,470 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` |
| overhead/print-tools | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 398 | 58.6 | 0.147 [0.145, 0.149] | 2.6% | 1.2% | 1.5% / 3.2% | 5.99 / 0.663 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` |
| overhead/print-tools | anthropic | first_request_ms | wall | ms | 12 | 292 | 33.3 | 0.114 [0.113, 0.117] | 3.3% | 0.9% | 1.4% / 1.7% | 2.82 / 0.772 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` |
| overhead/print-tools | anthropic | instructions | CPU | instructions | 12 | 2745.09M | 561.03M | 0.204 [0.204, 0.206] | 1.0% | 0.2% | 0.2% / 1.3% | 8,283,082 / 3,656,512 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` |
| overhead/print-tools | anthropic | peak_mem_mib | memory | MiB | 12 | 86.0 | 18.2 | 0.212 [0.209, 0.216] | 3.4% | 1.2% | 1.3% / 1.6% | 1.89 / 0.408 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | anthropic | peak_rss_mib | memory | MiB | 12 | 135 | 47.1 | 0.35 [0.346, 0.352] | 1.6% | 1.0% | 1.2% / 0.6% | 2.82 / 0.453 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` |
| overhead/print-tools | anthropic | teardown_ms | wall | ms | 12 | 20.2 | 3.24 | 0.161 [0.139, 0.193] | 32.0% | 12.9% | 7.9% / 16.4% | 2.61 / 0.983 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 8.9 | 6.55 | 0.736 [0.717, 0.763] | 3.5% | 6.7% | 10.2% / 18.8% | 0.219 / 0.303 | 2 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` |
| overhead/print-tools | anthropic | wall_ms | wall | ms | 12 | 357 | 73.1 | 0.205 [0.203, 0.207] | 1.7% | 1.1% | 2.2% / 1.4% | 1.96 / 1.13 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 118 | 0.229 [0.226, 0.232] | 2.3% | 2.0% | 1.8% / 2.0% | 6.54 / 2.57 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 309.89M | 0.216 [0.213, 0.218] | 1.6% | 2.1% | 1.8% / 1.6% | 17,345,646 / 4,986,840 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 58.5 | 0.147 [0.137, 0.149] | 4.8% | 1.4% | 0.9% / 4.2% | 2.98 / 3.85 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 33.4 | 0.114 [0.113, 0.116] | 2.7% | 1.6% | 1.3% / 2.4% | 2.5 / 0.586 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 563.05M | 0.202 [0.2, 0.203] | 1.3% | 0.3% | 0.2% / 1.5% | 5,500,458 / 5,905,750 | 0 / 3 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 18.1 | 0.209 [0.207, 0.213] | 1.9% | 1.0% | 0.7% / 1.8% | 0.521 / 0.327 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 47.1 | 0.348 [0.345, 0.351] | 1.0% | 1.0% | 0.9% / 0.7% | 1.46 / 0.514 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 3.35 | 0.174 [0.166, 0.195] | 35.2% | 12.4% | 9.6% / 15.8% | 2.05 / 0.528 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 6.64 | 0.694 [0.651, 0.723] | 9.9% | 12.1% | 10.8% / 2.8% | 0.84 / 0.142 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 73.6 | 0.204 [0.202, 0.206] | 1.7% | 2.0% | 1.8% / 1.1% | 4.8 / 0.848 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/print-tools | responses | cpu_ms | CPU | ms of CPU time | 12 | 522 | 120 | 0.229 [0.224, 0.232] | 2.5% | 2.5% | 3.3% / 1.7% | 9.6 / 1.49 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` |
| overhead/print-tools | responses | cycles | CPU | cycles | 12 | 1445.29M | 312.78M | 0.216 [0.213, 0.218] | 2.4% | 2.6% | 3.2% / 1.5% | 25,635,734 / 3,502,681 | 2 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` |
| overhead/print-tools | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 58.9 | 0.146 [0.144, 0.148] | 3.4% | 1.4% | 1.4% / 0.9% | 5.71 / 0.935 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` |
| overhead/print-tools | responses | first_request_ms | wall | ms | 12 | 295 | 33.6 | 0.114 [0.113, 0.115] | 2.9% | 1.6% | 1.6% / 1.2% | 5.1 / 0.541 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` |
| overhead/print-tools | responses | instructions | CPU | instructions | 12 | 2792.76M | 569.63M | 0.204 [0.203, 0.205] | 0.6% | 0.2% | 0.2% / 1.2% | 6,452,716 / 4,562,555 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` |
| overhead/print-tools | responses | peak_mem_mib | memory | MiB | 12 | 86.0 | 18.1 | 0.21 [0.209, 0.212] | 1.5% | 1.2% | 0.9% / 1.5% | 1.16 / 0.216 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` |
| overhead/print-tools | responses | peak_rss_mib | memory | MiB | 12 | 135 | 47.0 | 0.349 [0.346, 0.35] | 0.9% | 1.1% | 0.9% / 0.7% | 1.29 / 0.326 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` |
| overhead/print-tools | responses | teardown_ms | wall | ms | 12 | 16.9 | 3.48 | 0.205 [0.175, 0.22] | 20.0% | 11.8% | 14.1% / 8.0% | 2.81 / 0.339 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` |
| overhead/print-tools | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 10.1 | 6.65 | 0.655 [0.58, 0.692] | 14.1% | 10.2% | 11.6% / 12.3% | 1.47 / 0.234 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` |
| overhead/print-tools | responses | wall_ms | wall | ms | 12 | 362 | 74.9 | 0.207 [0.204, 0.211] | 3.4% | 2.4% | 2.8% / 1.6% | 5.7 / 1.27 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` |
| overhead/rpc | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 637 | 438 | 0.687 [0.673, 0.691] | 2.4% | 2.9% | 3.3% / 1.0% | 12.7 / 5.55 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cpu_ms` |
| overhead/rpc | anthropic | cycles | CPU | cycles | 12 | 1756.48M | 1181.85M | 0.673 [0.66, 0.676] | 2.1% | 2.9% | 3.3% / 1.0% | 34,415,458 / 11,304,635 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cycles` |
| overhead/rpc | anthropic | instructions | CPU | instructions | 12 | 3209.13M | 2282.06M | 0.711 [0.708, 0.713] | 1.3% | 0.3% | 0.2% / 0.7% | 7,831,587 / 14,752,343 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#instructions` |
| overhead/rpc | anthropic | peak_mem_mib | memory | MiB | 12 | 86.2 | 21.3 | 0.247 [0.244, 0.249] | 3.2% | 1.1% | 1.0% / 1.2% | 1.05 / 0.341 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_mem_mib` |
| overhead/rpc | anthropic | peak_rss_mib | memory | MiB | 12 | 139 | 50.5 | 0.364 [0.363, 0.366] | 1.0% | 0.6% | 0.7% / 0.5% | 0.745 / 0.285 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_rss_mib` |
| overhead/rpc | anthropic | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 51.0 | 0.138 [0.135, 0.141] | 3.0% | 1.7% | 1.6% / 1.6% | 9.15 / 1.05 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_cpu_ms` |
| overhead/rpc | anthropic | ready_ms | wall | ms | 12 | 264 | 29.8 | 0.113 [0.112, 0.114] | 3.4% | 2.1% | 1.4% / 0.9% | 2.27 / 0.303 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_ms` |
| overhead/rpc | anthropic | ready_pss_mib | memory | MiB | 12 | 107 | 41.4 | 0.386 [0.383, 0.388] | 1.3% | 0.8% | 0.7% / 1.0% | 0.59 / 0.325 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_pss_mib` |
| overhead/rpc | anthropic | ready_rss_mib | memory | MiB | 12 | 113 | 43.3 | 0.384 [0.382, 0.386] | 1.2% | 0.8% | 0.7% / 1.0% | 0.591 / 0.324 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_rss_mib` |
| overhead/rpc | anthropic | teardown_ms | wall | ms | 12 | 8.72 | 3.56 | 0.408 [0.357, 0.479] | 23.5% | 9.4% | 5.4% / 19.6% | 0.698 / 0.778 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#teardown_ms` |
| overhead/rpc | chat | cpu_ms | CPU | ms of CPU time | 12 | 676 | 433 | 0.641 [0.63, 0.648] | 4.5% | 2.5% | 2.5% / 1.1% | 13.2 / 5.39 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cpu_ms` |
| overhead/rpc | chat | cycles | CPU | cycles | 12 | 1863.43M | 1169.37M | 0.628 [0.617, 0.639] | 4.3% | 2.5% | 2.5% / 1.3% | 34,831,120 / 24,288,238 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cycles` |
| overhead/rpc | chat | instructions | CPU | instructions | 12 | 3343.17M | 2264.75M | 0.677 [0.67, 0.682] | 1.3% | 0.4% | 0.3% / 1.0% | 10,954,495 / 34,523,214 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#instructions` |
| overhead/rpc | chat | peak_mem_mib | memory | MiB | 12 | 89.1 | 21.4 | 0.24 [0.236, 0.242] | 1.4% | 0.9% | 0.8% / 1.9% | 0.892 / 0.455 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_mem_mib` |
| overhead/rpc | chat | peak_rss_mib | memory | MiB | 12 | 142 | 50.7 | 0.356 [0.354, 0.358] | 0.8% | 0.5% | 0.4% / 0.8% | 0.7 / 0.456 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_rss_mib` |
| overhead/rpc | chat | ready_cpu_ms | CPU | ms of CPU time | 12 | 369 | 50.4 | 0.137 [0.134, 0.14] | 2.4% | 1.6% | 1.8% / 1.5% | 8.23 / 1.16 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_cpu_ms` |
| overhead/rpc | chat | ready_ms | wall | ms | 12 | 263 | 29.5 | 0.112 [0.111, 0.113] | 2.6% | 1.3% | 1.5% / 0.8% | 4.82 / 0.308 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_ms` |
| overhead/rpc | chat | ready_pss_mib | memory | MiB | 12 | 107 | 41.6 | 0.389 [0.386, 0.393] | 0.9% | 1.1% | 0.6% / 1.1% | 0.724 / 0.469 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_pss_mib` |
| overhead/rpc | chat | ready_rss_mib | memory | MiB | 12 | 112 | 43.5 | 0.388 [0.384, 0.391] | 0.9% | 1.0% | 0.5% / 1.0% | 0.777 / 0.428 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_rss_mib` |
| overhead/rpc | chat | teardown_ms | wall | ms | 12 | 8.62 | 3.62 | 0.42 [0.328, 0.486] | 39.5% | 9.6% | 7.7% / 21.9% | 1.05 / 1.26 | 4 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#teardown_ms` |
| overhead/rpc | responses | cpu_ms | CPU | ms of CPU time | 12 | 680 | 456 | 0.67 [0.658, 0.675] | 1.8% | 1.7% | 1.3% / 1.5% | 12.3 / 7.93 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cpu_ms` |
| overhead/rpc | responses | cycles | CPU | cycles | 12 | 1874.58M | 1232.14M | 0.657 [0.645, 0.66] | 1.8% | 1.6% | 1.2% / 1.3% | 31,582,812 / 23,536,394 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cycles` |
| overhead/rpc | responses | instructions | CPU | instructions | 12 | 3379.56M | 2391.81M | 0.708 [0.701, 0.711] | 1.2% | 0.3% | 0.2% / 0.9% | 10,393,734 / 27,677,151 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#instructions` |
| overhead/rpc | responses | peak_mem_mib | memory | MiB | 12 | 90.6 | 21.3 | 0.235 [0.233, 0.237] | 2.5% | 1.3% | 1.1% / 1.0% | 0.707 / 0.346 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_mem_mib` |
| overhead/rpc | responses | peak_rss_mib | memory | MiB | 12 | 144 | 50.6 | 0.352 [0.351, 0.355] | 1.1% | 0.7% | 0.6% / 0.6% | 0.756 / 0.449 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_rss_mib` |
| overhead/rpc | responses | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 51.3 | 0.138 [0.135, 0.14] | 3.1% | 1.5% | 1.3% / 2.1% | 6.56 / 1.14 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_cpu_ms` |
| overhead/rpc | responses | ready_ms | wall | ms | 12 | 265 | 29.5 | 0.111 [0.11, 0.113] | 2.6% | 1.1% | 0.8% / 2.2% | 1.84 / 0.701 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_ms` |
| overhead/rpc | responses | ready_pss_mib | memory | MiB | 12 | 107 | 41.3 | 0.386 [0.383, 0.389] | 2.3% | 0.6% | 0.8% / 1.0% | 1.06 / 0.399 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_pss_mib` |
| overhead/rpc | responses | ready_rss_mib | memory | MiB | 12 | 112 | 43.2 | 0.384 [0.381, 0.387] | 2.2% | 0.5% | 0.7% / 1.0% | 1.06 / 0.353 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_rss_mib` |
| overhead/rpc | responses | teardown_ms | wall | ms | 12 | 9.51 | 3.79 | 0.398 [0.35, 0.493] | 30.0% | 9.0% | 7.4% / 19.5% | 1.33 / 1.08 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#teardown_ms` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 17.6 | 0.0624 [0.061, 0.0645] | 5.0% | 1.7% | 1.0% / 6.9% | 2.84 / 0.956 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 37.62M | 0.0488 [0.0479, 0.0499] | 4.5% | 1.7% | 0.9% / 2.5% | 5,972,803 / 1,383,640 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 63.68M | 0.0389 [0.0386, 0.0391] | 2.2% | 0.2% | 0.3% / 1.5% | 3,727,566 / 869,970 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 8.85 | 0.154 [0.149, 0.156] | 4.1% | 1.6% | 1.1% / 2.6% | 0.617 / 0.323 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 6.45 | 0.0601 [0.059, 0.0616] | 8.6% | 1.3% | 1.1% / 2.3% | 1.61 / 0.207 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 11.7 | 0.0537 [0.0524, 0.055] | 6.2% | 1.4% | 1.2% / 2.8% | 3.07 / 0.463 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## pig-tip against pi-node

> **Read this first:** This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

### Losses (measurably worse than the reference)

None.

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| overhead/print | anthropic | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` | 1 [1, 1] no measurable difference |
| overhead/print | chat | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/print | responses | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` | 1 [1, 1] no measurable difference |
| overhead/print-tools | anthropic | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` | 1 [1, 1] no measurable difference |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/print-tools | responses | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` | 1 [1, 1] no measurable difference |
| overhead/rpc | anthropic | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#requests` | 1 [1, 1] no measurable difference |
| overhead/rpc | chat | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/rpc | responses | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#requests` | 1 [1, 1] no measurable difference |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| overhead/print | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 421 | 15.9 | 0.0377 [0.0372, 0.0385] | 5.7% | 1.5% | 1.1% / 2.7% | 5.92 / 0.327 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` | 0.25 [0.243, 0.266] win |
| overhead/print | anthropic | cycles | CPU | cycles | 12 | 1167.02M | 38.18M | 0.0327 [0.0324, 0.0332] | 2.9% | 1.4% | 1.1% / 1.2% | 16,040,830 / 656,015 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` | 0.235 [0.231, 0.253] win |
| overhead/print | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 401 | 13.5 | 0.0337 [0.0329, 0.0348] | 5.8% | 1.5% | 1.1% / 3.4% | 5.73 / 0.463 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` | 0.234 [0.228, 0.25] win |
| overhead/print | anthropic | first_request_ms | wall | ms | 12 | 292 | 11.6 | 0.0396 [0.0393, 0.04] | 3.2% | 1.2% | 1.3% / 1.1% | 2.25 / 0.176 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` | 0.348 [0.342, 0.352] win |
| overhead/print | anthropic | instructions | CPU | instructions | 12 | 2323.75M | 54.81M | 0.0236 [0.0234, 0.0237] | 1.9% | 0.4% | 0.3% / 0.6% | 7,910,528 / 480,471 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` | 0.207 [0.203, 0.222] win |
| overhead/print | anthropic | peak_mem_mib | memory | MiB | 12 | 62.8 | 7.03 | 0.112 [0.111, 0.114] | 5.1% | 1.3% | 1.1% / 2.1% | 1.07 / 0.0537 | 0 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` | 0.429 [0.424, 0.434] win |
| overhead/print | anthropic | peak_rss_mib | memory | MiB | 12 | 114 | 6.98 | 0.0614 [0.0613, 0.0619] | 3.6% | 0.8% | 0.8% / 0.8% | 1.16 / 0.00488 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` | 0.171 [0.17, 0.172] win |
| overhead/print | anthropic | request_bytes | wire | bytes | 12 | 6,114 | 6,075 | 0.994 [0.994, 0.994] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` | 0.994 [0.994, 0.994] win |
| overhead/print | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 6,114 | 6,075 | 0.994 [0.994, 0.994] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` | 0.994 [0.994, 0.994] win |
| overhead/print | anthropic | teardown_ms | wall | ms | 12 | 17.5 | 1.76 | 0.101 [0.095, 0.111] | 19.1% | 2.4% | 1.5% / 10.0% | 0.274 / 0.281 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` | 0.581 [0.534, 0.667] win |
| overhead/print | anthropic | wall_ms | wall | ms | 12 | 311 | 13.9 | 0.0447 [0.0438, 0.045] | 4.5% | 1.2% | 1.3% / 1.6% | 1.83 / 0.368 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` | 0.377 [0.367, 0.386] win |
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 15.6 | 0.0365 [0.0361, 0.038] | 6.3% | 1.9% | 1.6% / 3.8% | 12.1 / 0.789 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` | 0.247 [0.241, 0.259] win |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 38.17M | 0.0322 [0.0317, 0.0328] | 4.3% | 1.8% | 1.6% / 1.9% | 29,576,145 / 768,967 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` | 0.235 [0.232, 0.24] win |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 13.5 | 0.0334 [0.033, 0.0349] | 5.6% | 1.9% | 1.6% / 4.4% | 10.4 / 0.634 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` | 0.242 [0.231, 0.261] win |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 11.7 | 0.0397 [0.0394, 0.04] | 3.5% | 2.1% | 1.7% / 1.7% | 3.48 / 0.0823 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` | 0.355 [0.348, 0.363] win |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 54.26M | 0.0231 [0.023, 0.0233] | 1.3% | 0.2% | 0.4% / 0.8% | 7,542,734 / 719,985 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` | 0.205 [0.203, 0.207] win |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 6.82 | 0.107 [0.106, 0.111] | 2.9% | 1.8% | 1.3% / 3.3% | 0.479 / 0.255 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` | 0.413 [0.406, 0.427] win |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 6.97 | 0.0611 [0.0609, 0.0613] | 1.8% | 0.5% | 0.4% / 0.7% | 0.556 / 0.00781 | 0 / 3 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` | 0.171 [0.169, 0.172] win |
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 6,014 | 0.993 [0.993, 0.993] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` | 0.994 [0.994, 0.994] win |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 6,014 | 0.993 [0.993, 0.993] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` | 0.994 [0.994, 0.994] win |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 1.62 | 0.0803 [0.0787, 0.0812] | 8.3% | 3.3% | 3.9% / 2.1% | 0.437 / 0.0379 | 2 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` | 0.516 [0.425, 0.582] win |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 13.7 | 0.0433 [0.0431, 0.0437] | 3.1% | 2.0% | 1.6% / 1.6% | 4.4 / 0.116 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` | 0.376 [0.373, 0.378] win |
| overhead/print | responses | cpu_ms | CPU | ms of CPU time | 12 | 425 | 15.9 | 0.0374 [0.0367, 0.039] | 6.1% | 2.9% | 1.4% / 3.2% | 6.78 / 0.726 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` | 0.247 [0.241, 0.258] win |
| overhead/print | responses | cycles | CPU | cycles | 12 | 1178.05M | 38.63M | 0.0328 [0.0324, 0.0332] | 3.1% | 2.9% | 1.4% / 1.2% | 17,455,521 / 445,314 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` | 0.235 [0.232, 0.238] win |
| overhead/print | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 13.5 | 0.0337 [0.0331, 0.0355] | 7.5% | 3.0% | 1.4% / 3.9% | 6.78 / 0.671 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` | 0.232 [0.225, 0.244] win |
| overhead/print | responses | first_request_ms | wall | ms | 12 | 295 | 11.7 | 0.0397 [0.0388, 0.04] | 3.6% | 2.5% | 1.5% / 0.8% | 6.14 / 0.156 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` | 0.348 [0.343, 0.353] win |
| overhead/print | responses | instructions | CPU | instructions | 12 | 2351.19M | 55.49M | 0.0236 [0.0235, 0.0238] | 1.7% | 0.4% | 0.4% / 0.5% | 4,128,707 / 481,624 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` | 0.208 [0.207, 0.209] win |
| overhead/print | responses | peak_mem_mib | memory | MiB | 12 | 63.5 | 6.99 | 0.11 [0.106, 0.112] | 7.2% | 0.8% | 0.9% / 3.2% | 0.704 / 0.316 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` | 0.425 [0.408, 0.43] win |
| overhead/print | responses | peak_rss_mib | memory | MiB | 12 | 114 | 6.98 | 0.0612 [0.0605, 0.0616] | 3.6% | 1.0% | 1.4% / 11.3% | 1.35 / 0.0264 | 0 / 4 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` | 0.171 [0.17, 0.171] win |
| overhead/print | responses | request_bytes | wire | bytes | 12 | 6,024 | 5,979 | 0.993 [0.993, 0.993] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` | 0.994 [0.994, 0.994] win |
| overhead/print | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 6,024 | 5,979 | 0.993 [0.993, 0.993] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` | 0.994 [0.994, 0.994] win |
| overhead/print | responses | teardown_ms | wall | ms | 12 | 20.8 | 1.71 | 0.0822 [0.0813, 0.0833] | 7.1% | 1.6% | 0.8% / 5.4% | 0.104 / 0.0328 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` | 0.536 [0.512, 0.571] win |
| overhead/print | responses | wall_ms | wall | ms | 12 | 316 | 13.9 | 0.044 [0.0433, 0.0443] | 3.8% | 2.4% | 1.4% / 0.7% | 6.06 / 0.158 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` | 0.371 [0.368, 0.381] win |
| overhead/print-tools | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 508 | 28.1 | 0.0554 [0.0544, 0.0568] | 4.5% | 1.4% | 2.6% / 1.9% | 7.39 / 0.81 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` | 0.238 [0.234, 0.246] win |
| overhead/print-tools | anthropic | cycles | CPU | cycles | 12 | 1406.22M | 71.50M | 0.0508 [0.0499, 0.0511] | 2.1% | 1.4% | 2.6% / 1.0% | 20,029,746 / 849,739 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` | 0.231 [0.229, 0.233] win |
| overhead/print-tools | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 398 | 13.6 | 0.034 [0.0332, 0.0354] | 7.6% | 1.2% | 1.5% / 3.4% | 5.99 / 0.758 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` | 0.231 [0.226, 0.241] win |
| overhead/print-tools | anthropic | first_request_ms | wall | ms | 12 | 292 | 11.6 | 0.0396 [0.0392, 0.04] | 3.5% | 0.9% | 1.4% / 1.7% | 2.82 / 0.184 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` | 0.347 [0.34, 0.35] win |
| overhead/print-tools | anthropic | instructions | CPU | instructions | 12 | 2745.09M | 100.65M | 0.0367 [0.0365, 0.0367] | 1.1% | 0.2% | 0.2% / 0.5% | 8,283,082 / 371,453 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` | 0.179 [0.178, 0.18] win |
| overhead/print-tools | anthropic | peak_mem_mib | memory | MiB | 12 | 86.0 | 10.8 | 0.126 [0.124, 0.129] | 4.2% | 1.2% | 1.3% / 2.3% | 1.89 / 0.317 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` | 0.593 [0.584, 0.608] win |
| overhead/print-tools | anthropic | peak_rss_mib | memory | MiB | 12 | 135 | 6.98 | 0.0518 [0.0511, 0.0525] | 1.8% | 1.0% | 1.2% / 2.1% | 2.82 / 0.0615 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` | 0.148 [0.148, 0.15] win |
| overhead/print-tools | anthropic | request_bytes | wire | bytes | 12 | 127,836 | 127,593 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` | 0.997 [0.997, 0.997] win |
| overhead/print-tools | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 14,204 | 14,177 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` | 0.997 [0.997, 0.997] win |
| overhead/print-tools | anthropic | teardown_ms | wall | ms | 12 | 20.2 | 1.75 | 0.0867 [0.0816, 0.1] | 22.7% | 12.9% | 7.9% / 31.5% | 2.61 / 0.209 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` | 0.54 [0.457, 0.649] win |
| overhead/print-tools | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 8.9 | 1.05 | 0.118 [0.114, 0.12] | 4.2% | 6.7% | 10.2% / 2.8% | 0.219 / 0.0366 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` | 0.16 [0.153, 0.165] win |
| overhead/print-tools | anthropic | turn_gap_ms | wall | ms | 12 | 3.7 | 0.939 | 0.254 [0.246, 0.258] | 3.3% | 7.4% | 12.0% / 2.5% | 0.0789 / 0.0362 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` | 0.231 [0.22, 0.24] win |
| overhead/print-tools | anthropic | wall_ms | wall | ms | 12 | 357 | 27.2 | 0.0763 [0.0756, 0.0771] | 2.8% | 1.1% | 2.2% / 2.6% | 1.96 / 0.363 | 1 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` | 0.372 [0.369, 0.375] win |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 28.1 | 0.0543 [0.0536, 0.0552] | 2.6% | 2.0% | 1.8% / 2.4% | 6.54 / 0.588 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` | 0.237 [0.233, 0.243] win |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 71.32M | 0.0497 [0.0495, 0.0502] | 2.1% | 2.1% | 1.8% / 1.2% | 17,345,646 / 1,203,856 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` | 0.23 [0.228, 0.234] win |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 13.4 | 0.0336 [0.0331, 0.0351] | 4.8% | 1.4% | 0.9% / 4.1% | 2.98 / 0.673 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` | 0.229 [0.224, 0.252] win |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 11.5 | 0.0394 [0.039, 0.0402] | 3.7% | 1.6% | 1.3% / 1.6% | 2.5 / 0.325 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` | 0.345 [0.339, 0.354] win |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 100.13M | 0.036 [0.0358, 0.0362] | 1.4% | 0.3% | 0.2% / 0.8% | 5,500,458 / 950,159 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` | 0.178 [0.177, 0.18] win |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 10.9 | 0.126 [0.123, 0.128] | 3.7% | 1.0% | 0.7% / 2.7% | 0.521 / 0.457 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` | 0.602 [0.585, 0.616] win |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 6.97 | 0.0515 [0.0512, 0.0518] | 2.9% | 1.0% | 0.9% / 0.7% | 1.46 / 0.00879 | 0 / 4 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` | 0.148 [0.147, 0.149] win |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 126,504 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` | 0.997 [0.997, 0.997] win |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 14,056 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` | 0.997 [0.997, 0.997] win |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 1.86 | 0.0969 [0.0782, 0.149] | 96.4% | 12.4% | 9.6% / 44.2% | 2.05 / 0.942 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` | 0.556 [0.433, 0.862] no measurable difference |
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 1.08 | 0.113 [0.106, 0.12] | 9.9% | 12.1% | 10.8% / 4.4% | 0.84 / 0.0584 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` | 0.163 [0.158, 0.168] win |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 0.955 | 0.238 [0.231, 0.26] | 8.5% | 13.7% | 12.9% / 5.4% | 0.278 / 0.0766 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` | 0.231 [0.223, 0.246] win |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 27.4 | 0.0758 [0.0753, 0.0795] | 6.3% | 2.0% | 1.8% / 4.2% | 4.8 / 1.35 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` | 0.372 [0.367, 0.391] win |
| overhead/print-tools | responses | cpu_ms | CPU | ms of CPU time | 12 | 522 | 30.2 | 0.0578 [0.0562, 0.0583] | 3.5% | 2.5% | 3.3% / 2.0% | 9.6 / 0.842 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` | 0.252 [0.246, 0.255] win |
| overhead/print-tools | responses | cycles | CPU | cycles | 12 | 1445.29M | 75.54M | 0.0523 [0.0512, 0.0528] | 2.4% | 2.6% | 3.2% / 1.8% | 25,635,734 / 1,397,720 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` | 0.242 [0.24, 0.246] win |
| overhead/print-tools | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 13.6 | 0.0339 [0.033, 0.0354] | 6.6% | 1.4% | 1.4% / 3.7% | 5.71 / 0.848 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` | 0.231 [0.226, 0.241] win |
| overhead/print-tools | responses | first_request_ms | wall | ms | 12 | 295 | 11.6 | 0.0394 [0.0383, 0.04] | 2.8% | 1.6% | 1.6% / 2.1% | 5.1 / 0.33 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` | 0.345 [0.338, 0.351] win |
| overhead/print-tools | responses | instructions | CPU | instructions | 12 | 2792.76M | 112.13M | 0.0402 [0.0401, 0.0405] | 0.8% | 0.2% | 0.2% / 0.7% | 6,452,716 / 583,846 | 0 / 2 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` | 0.197 [0.196, 0.199] win |
| overhead/print-tools | responses | peak_mem_mib | memory | MiB | 12 | 86.0 | 11.5 | 0.134 [0.132, 0.137] | 2.1% | 1.2% | 0.9% / 2.3% | 1.16 / 0.305 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` | 0.637 [0.628, 0.649] win |
| overhead/print-tools | responses | peak_rss_mib | memory | MiB | 12 | 135 | 6.98 | 0.0518 [0.0514, 0.0519] | 2.7% | 1.1% | 0.9% / 0.3% | 1.29 / 0.00391 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` | 0.148 [0.148, 0.149] win |
| overhead/print-tools | responses | request_bytes | wire | bytes | 12 | 125,406 | 125,109 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` | 0.997 [0.997, 0.997] win |
| overhead/print-tools | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 13,934 | 13,901 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` | 0.997 [0.997, 0.997] win |
| overhead/print-tools | responses | teardown_ms | wall | ms | 12 | 16.9 | 1.75 | 0.103 [0.0901, 0.123] | 25.2% | 11.8% | 14.1% / 23.8% | 2.81 / 0.212 | 0 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` | 0.502 [0.479, 0.613] win |
| overhead/print-tools | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 10.1 | 1.25 | 0.123 [0.111, 0.129] | 14.1% | 10.2% | 11.6% / 1.7% | 1.47 / 0.0224 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` | 0.188 [0.184, 0.192] win |
| overhead/print-tools | responses | turn_gap_ms | wall | ms | 12 | 4.05 | 1.1 | 0.272 [0.261, 0.279] | 4.2% | 11.0% | 14.8% / 1.2% | 0.24 / 0.0164 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` | 0.26 [0.255, 0.27] win |
| overhead/print-tools | responses | wall_ms | wall | ms | 12 | 362 | 28.8 | 0.0796 [0.078, 0.0817] | 2.8% | 2.4% | 2.8% / 2.5% | 5.7 / 0.765 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` | 0.385 [0.379, 0.395] win |
| overhead/rpc | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 637 | 69.4 | 0.109 [0.107, 0.109] | 2.0% | 2.9% | 3.3% / 1.4% | 12.7 / 0.839 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cpu_ms` | 0.159 [0.157, 0.16] win |
| overhead/rpc | anthropic | cycles | CPU | cycles | 12 | 1756.48M | 182.88M | 0.104 [0.102, 0.105] | 2.1% | 2.9% | 3.3% / 0.8% | 34,415,458 / 1,969,272 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cycles` | 0.155 [0.153, 0.156] win |
| overhead/rpc | anthropic | instructions | CPU | instructions | 12 | 3209.13M | 251.97M | 0.0785 [0.0782, 0.0789] | 0.9% | 0.3% | 0.2% / 0.7% | 7,831,587 / 1,975,463 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#instructions` | 0.11 [0.11, 0.111] win |
| overhead/rpc | anthropic | peak_mem_mib | memory | MiB | 12 | 86.2 | 21.0 | 0.243 [0.238, 0.246] | 2.8% | 1.1% | 1.0% / 1.6% | 1.05 / 0.459 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_mem_mib` | 0.987 [0.967, 1] no measurable difference |
| overhead/rpc | anthropic | peak_rss_mib | memory | MiB | 12 | 139 | 56.6 | 0.408 [0.406, 0.41] | 0.7% | 0.6% | 0.7% / 0.5% | 0.745 / 0.248 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_rss_mib` | 1.12 [1.11, 1.12] loss |
| overhead/rpc | anthropic | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 13.3 | 0.036 [0.0354, 0.0371] | 6.3% | 1.7% | 1.6% / 3.4% | 9.15 / 0.544 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_cpu_ms` | 0.262 [0.256, 0.271] win |
| overhead/rpc | anthropic | ready_ms | wall | ms | 12 | 264 | 25.9 | 0.0979 [0.0975, 0.0984] | 1.5% | 2.1% | 1.4% / 8.9% | 2.27 / 0.27 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_ms` | 0.87 [0.861, 0.878] win |
| overhead/rpc | anthropic | ready_pss_mib | memory | MiB | 12 | 107 | 38.5 | 0.359 [0.356, 0.361] | 1.3% | 0.8% | 0.7% / 0.8% | 0.59 / 0.315 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_pss_mib` | 0.93 [0.922, 0.937] win |
| overhead/rpc | anthropic | ready_rss_mib | memory | MiB | 12 | 113 | 40.4 | 0.358 [0.356, 0.361] | 1.3% | 0.8% | 0.7% / 0.8% | 0.591 / 0.315 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_rss_mib` | 0.933 [0.925, 0.94] win |
| overhead/rpc | anthropic | request_bytes | wire | bytes | 12 | 1.13M | 1.13M | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes` | 0.998 [0.998, 0.998] win |
| overhead/rpc | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 56,537 | 56,451 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes_per_turn` | 0.998 [0.998, 0.998] win |
| overhead/rpc | anthropic | teardown_ms | wall | ms | 12 | 8.72 | 2.05 | 0.235 [0.216, 0.246] | 13.7% | 9.4% | 5.4% / 5.6% | 0.698 / 0.117 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#teardown_ms` | 0.576 [0.49, 0.631] win |
| overhead/rpc | anthropic | turn_cpu_mean_ms | wall | ms | 12 | 10.3 | 2.51 | 0.244 [0.24, 0.246] | 2.3% | 5.6% | 6.7% / 1.1% | 0.232 / 0.0217 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_mean_ms` | 0.131 [0.13, 0.133] win |
| overhead/rpc | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.08 | 2.32 | 0.255 [0.251, 0.265] | 6.2% | 4.8% | 4.1% / 1.3% | 0.466 / 0.0139 | 0 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_ms` | 0.131 [0.125, 0.133] win |
| overhead/rpc | anthropic | turn_harness_added_ms | wall | ms | 12 | 0.686 | 0.227 | 0.331 [0.326, 0.342] | 5.4% | 3.0% | 3.6% / 3.7% | 0.0182 / 0.00929 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_harness_added_ms` | 0.274 [0.266, 0.289] win |
| overhead/rpc | anthropic | turn_turn_gap_ms | wall | ms | 12 | 3.03 | 1.02 | 0.338 [0.332, 0.342] | 3.3% | 2.7% | 2.6% / 1.6% | 0.0798 / 0.0219 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_turn_gap_ms` | 0.197 [0.193, 0.201] win |
| overhead/rpc | anthropic | turn_wall_ms | wall | ms | 12 | 6.79 | 3 | 0.441 [0.435, 0.451] | 2.6% | 2.1% | 2.9% / 1.5% | 0.159 / 0.0681 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_wall_ms` | 0.256 [0.253, 0.262] win |
| overhead/rpc | chat | cpu_ms | CPU | ms of CPU time | 12 | 676 | 70.1 | 0.104 [0.102, 0.106] | 4.5% | 2.5% | 2.5% / 1.4% | 13.2 / 1.23 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cpu_ms` | 0.162 [0.16, 0.164] win |
| overhead/rpc | chat | cycles | CPU | cycles | 12 | 1863.43M | 184.48M | 0.099 [0.0976, 0.1] | 4.3% | 2.5% | 2.5% / 1.4% | 34,831,120 / 1,660,951 | 1 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cycles` | 0.158 [0.156, 0.16] win |
| overhead/rpc | chat | instructions | CPU | instructions | 12 | 3343.17M | 251.94M | 0.0754 [0.075, 0.0757] | 0.7% | 0.4% | 0.3% / 0.6% | 10,954,495 / 1,673,062 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#instructions` | 0.111 [0.11, 0.112] win |
| overhead/rpc | chat | peak_mem_mib | memory | MiB | 12 | 89.1 | 20.8 | 0.234 [0.232, 0.239] | 2.9% | 0.9% | 0.8% / 2.0% | 0.892 / 0.542 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_mem_mib` | 0.973 [0.969, 0.99] no measurable difference |
| overhead/rpc | chat | peak_rss_mib | memory | MiB | 12 | 142 | 56.9 | 0.399 [0.398, 0.402] | 0.6% | 0.5% | 0.4% / 0.4% | 0.7 / 0.335 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_rss_mib` | 1.12 [1.12, 1.13] loss |
| overhead/rpc | chat | ready_cpu_ms | CPU | ms of CPU time | 12 | 369 | 13.2 | 0.0356 [0.0347, 0.0363] | 2.3% | 1.6% | 1.8% / 3.8% | 8.23 / 0.379 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_cpu_ms` | 0.261 [0.254, 0.266] win |
| overhead/rpc | chat | ready_ms | wall | ms | 12 | 263 | 25.9 | 0.0983 [0.0972, 0.0994] | 2.2% | 1.3% | 1.5% / 0.5% | 4.82 / 0.148 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_ms` | 0.878 [0.873, 0.886] win |
| overhead/rpc | chat | ready_pss_mib | memory | MiB | 12 | 107 | 38.4 | 0.359 [0.358, 0.362] | 0.8% | 1.1% | 0.6% / 0.6% | 0.724 / 0.306 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_pss_mib` | 0.922 [0.915, 0.932] win |
| overhead/rpc | chat | ready_rss_mib | memory | MiB | 12 | 112 | 40.3 | 0.359 [0.358, 0.361] | 0.8% | 1.0% | 0.5% / 0.6% | 0.777 / 0.306 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_rss_mib` | 0.925 [0.919, 0.935] win |
| overhead/rpc | chat | request_bytes | wire | bytes | 12 | 1.11M | 1.11M | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes` | 0.998 [0.998, 0.998] win |
| overhead/rpc | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 55,652 | 55,554 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes_per_turn` | 0.998 [0.998, 0.998] win |
| overhead/rpc | chat | teardown_ms | wall | ms | 12 | 8.62 | 1.98 | 0.23 [0.189, 0.246] | 26.0% | 9.6% | 7.7% / 16.6% | 1.05 / 0.285 | 4 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#teardown_ms` | 0.547 [0.435, 0.715] win |
| overhead/rpc | chat | turn_cpu_mean_ms | wall | ms | 12 | 11.9 | 2.55 | 0.215 [0.211, 0.216] | 4.3% | 5.9% | 4.2% / 1.9% | 0.206 / 0.0198 | 1 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_mean_ms` | 0.135 [0.134, 0.136] win |
| overhead/rpc | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.2 | 2.34 | 0.209 [0.205, 0.217] | 3.5% | 3.9% | 3.0% / 1.9% | 0.472 / 0.0365 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_ms` | 0.132 [0.13, 0.136] win |
| overhead/rpc | chat | turn_harness_added_ms | wall | ms | 12 | 0.874 | 0.264 | 0.303 [0.298, 0.313] | 5.3% | 3.2% | 3.7% / 2.9% | 0.0447 / 0.00573 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_harness_added_ms` | 0.285 [0.275, 0.292] win |
| overhead/rpc | chat | turn_turn_gap_ms | wall | ms | 12 | 3.25 | 1.06 | 0.327 [0.32, 0.33] | 4.4% | 2.4% | 3.0% / 1.5% | 0.0711 / 0.02 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_turn_gap_ms` | 0.203 [0.197, 0.208] win |
| overhead/rpc | chat | turn_wall_ms | wall | ms | 12 | 7.32 | 2.91 | 0.397 [0.395, 0.412] | 3.3% | 2.8% | 2.3% / 2.4% | 0.196 / 0.0742 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_wall_ms` | 0.246 [0.242, 0.253] win |
| overhead/rpc | responses | cpu_ms | CPU | ms of CPU time | 12 | 680 | 81.1 | 0.119 [0.118, 0.12] | 1.8% | 1.7% | 1.3% / 1.0% | 12.3 / 1.13 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cpu_ms` | 0.178 [0.177, 0.181] win |
| overhead/rpc | responses | cycles | CPU | cycles | 12 | 1874.58M | 214.98M | 0.115 [0.113, 0.115] | 1.8% | 1.6% | 1.2% / 0.8% | 31,582,812 / 2,224,037 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cycles` | 0.174 [0.174, 0.177] win |
| overhead/rpc | responses | instructions | CPU | instructions | 12 | 3379.56M | 362.31M | 0.107 [0.107, 0.107] | 0.3% | 0.3% | 0.2% / 0.2% | 10,393,734 / 1,302,526 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#instructions` | 0.151 [0.151, 0.153] win |
| overhead/rpc | responses | peak_mem_mib | memory | MiB | 12 | 90.6 | 21.4 | 0.236 [0.234, 0.24] | 1.9% | 1.3% | 1.1% / 1.3% | 0.707 / 0.482 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_mem_mib` | 1 [0.993, 1.03] no measurable difference |
| overhead/rpc | responses | peak_rss_mib | memory | MiB | 12 | 144 | 57.2 | 0.398 [0.397, 0.401] | 0.8% | 0.7% | 0.6% / 0.6% | 0.756 / 0.426 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_rss_mib` | 1.13 [1.12, 1.14] loss |
| overhead/rpc | responses | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 13.2 | 0.0356 [0.0351, 0.0362] | 2.9% | 1.5% | 1.3% / 2.9% | 6.56 / 0.288 | 0 / 1 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_cpu_ms` | 0.258 [0.254, 0.264] win |
| overhead/rpc | responses | ready_ms | wall | ms | 12 | 265 | 25.8 | 0.0974 [0.0966, 0.0976] | 2.0% | 1.1% | 0.8% / 8.6% | 1.84 / 0.145 | 0 / 2 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_ms` | 0.876 [0.858, 0.88] win |
| overhead/rpc | responses | ready_pss_mib | memory | MiB | 12 | 107 | 38.5 | 0.359 [0.354, 0.362] | 1.2% | 0.6% | 0.8% / 1.0% | 1.06 / 0.581 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_pss_mib` | 0.931 [0.92, 0.938] win |
| overhead/rpc | responses | ready_rss_mib | memory | MiB | 12 | 112 | 40.4 | 0.359 [0.354, 0.362] | 1.1% | 0.5% | 0.7% / 1.0% | 1.06 / 0.581 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_rss_mib` | 0.934 [0.924, 0.94] win |
| overhead/rpc | responses | request_bytes | wire | bytes | 12 | 1.14M | 1.14M | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes` | 0.998 [0.998, 0.998] win |
| overhead/rpc | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 57,018 | 56,920 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes_per_turn` | 0.998 [0.998, 0.998] win |
| overhead/rpc | responses | teardown_ms | wall | ms | 12 | 9.51 | 2.05 | 0.216 [0.19, 0.265] | 15.5% | 9.0% | 7.4% / 12.7% | 1.33 / 0.439 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#teardown_ms` | 0.542 [0.462, 0.635] win |
| overhead/rpc | responses | turn_cpu_mean_ms | wall | ms | 12 | 12.1 | 3.12 | 0.257 [0.254, 0.265] | 2.8% | 3.0% | 2.5% / 1.1% | 0.453 / 0.0291 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_mean_ms` | 0.155 [0.155, 0.158] win |
| overhead/rpc | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.0 | 3.01 | 0.275 [0.262, 0.299] | 10.4% | 8.7% | 7.4% / 1.7% | 1.2 / 0.0654 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_ms` | 0.149 [0.141, 0.155] win |
| overhead/rpc | responses | turn_harness_added_ms | wall | ms | 12 | 0.885 | 0.211 | 0.238 [0.217, 0.258] | 10.5% | 3.4% | 3.9% / 10.1% | 0.0234 / 0.0317 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_harness_added_ms` | 0.222 [0.204, 0.24] win |
| overhead/rpc | responses | turn_turn_gap_ms | wall | ms | 12 | 3.29 | 1.32 | 0.4 [0.393, 0.411] | 2.9% | 2.8% | 1.5% / 2.1% | 0.0715 / 0.0299 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_turn_gap_ms` | 0.248 [0.242, 0.251] win |
| overhead/rpc | responses | turn_wall_ms | wall | ms | 12 | 7.46 | 3.75 | 0.502 [0.493, 0.51] | 3.0% | 3.1% | 2.1% / 1.7% | 0.175 / 0.0643 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_wall_ms` | 0.304 [0.299, 0.311] win |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 5.24 | 0.0186 [0.0178, 0.0203] | 18.1% | 1.7% | 1.0% / 9.3% | 2.84 / 0.52 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` | 0.298 [0.287, 0.325] win |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 11.14M | 0.0144 [0.0142, 0.0149] | 6.9% | 1.7% | 0.9% / 2.8% | 5,972,803 / 531,954 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` | 0.296 [0.29, 0.306] win |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 14.14M | 0.00864 [0.00857, 0.00909] | 7.5% | 0.2% | 0.3% / 3.0% | 3,727,566 / 778,764 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` | 0.222 [0.22, 0.234] win |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 3.98 | 0.069 [0.0646, 0.0732] | 12.6% | 1.6% | 1.1% / 6.2% | 0.617 / 0.463 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` | 0.45 [0.428, 0.472] win |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 6.97 | 0.065 [0.0642, 0.0656] | 1.5% | 1.3% | 1.1% / 1.7% | 1.61 / 0.0674 | 0 / 2 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` | 1.08 [1.06, 1.1] no measurable difference |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 4.21 | 0.0193 [0.0188, 0.0199] | 8.8% | 1.4% | 1.2% / 3.0% | 3.07 / 0.242 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` | 0.359 [0.348, 0.374] win |

## rpi against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | chat | request_bytes | wire | bytes | 12 | 6,059 | 7,702 | 1.27 [1.27, 1.27] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 6,059 | 7,702 | 1.27 [1.27, 1.27] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print | responses | request_bytes | wire | bytes | 12 | 6,024 | 7,533 | 1.25 [1.25, 1.25] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` |
| overhead/print | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 6,024 | 7,533 | 1.25 [1.25, 1.25] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | chat | request_bytes | wire | bytes | 12 | 126,801 | 141,444 | 1.12 [1.12, 1.12] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 14,089 | 15,716 | 1.12 [1.12, 1.12] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00391 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/print-tools | responses | request_bytes | wire | bytes | 12 | 125,406 | 138,843 | 1.11 [1.11, 1.11] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` |
| overhead/print-tools | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 13,934 | 15,427 | 1.11 [1.11, 1.11] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` |
| overhead/print | anthropic | request_bytes | wire | bytes | 12 | 6,114 | 6,599 | 1.08 [1.08, 1.08] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` |
| overhead/print | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 6,114 | 6,599 | 1.08 [1.08, 1.08] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` |
| overhead/rpc | chat | request_bytes | wire | bytes | 12 | 1.11M | 1.17M | 1.05 [1.05, 1.05] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes` |
| overhead/rpc | chat | request_bytes_per_turn | wire | bytes per turn | 12 | 55,652 | 58,383 | 1.05 [1.05, 1.05] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00293 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes_per_turn` |
| overhead/rpc | responses | request_bytes | wire | bytes | 12 | 1.14M | 1.19M | 1.04 [1.04, 1.04] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes` |
| overhead/rpc | responses | request_bytes_per_turn | wire | bytes per turn | 12 | 57,018 | 59,367 | 1.04 [1.04, 1.04] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | anthropic | request_bytes | wire | bytes | 12 | 127,836 | 131,561 | 1.03 [1.03, 1.03] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` |
| overhead/print-tools | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 14,204 | 14,618 | 1.03 [1.03, 1.03] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00342 | no exact |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` |
| overhead/rpc | anthropic | request_bytes | wire | bytes | 12 | 1.13M | 1.14M | 1.01 [1.01, 1.01] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes` |
| overhead/rpc | anthropic | request_bytes_per_turn | wire | bytes per turn | 12 | 56,537 | 56,890 | 1.01 [1.01, 1.01] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.00244 | no exact |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` |
| overhead/print | chat | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print | responses | requests | wire | count | 12 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` |
| overhead/print-tools | anthropic | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` |
| overhead/print-tools | chat | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |
| overhead/print-tools | responses | requests | wire | count | 12 | 9 | 9 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` |
| overhead/rpc | anthropic | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#requests` |
| overhead/rpc | chat | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#requests` |
| overhead/rpc | responses | requests | wire | count | 12 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 421 | 6.56 | 0.0156 [0.0154, 0.0157] | 6.8% | 1.5% | 1.1% / 4.2% | 5.92 / 0.117 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` |
| overhead/print | anthropic | cycles | CPU | cycles | 12 | 1167.02M | 14.52M | 0.0124 [0.0123, 0.0126] | 6.1% | 1.4% | 1.1% / 1.4% | 16,040,830 / 331,140 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` |
| overhead/print | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 401 | 4.67 | 0.0116 [0.0114, 0.0116] | 6.5% | 1.5% | 1.1% / 6.0% | 5.73 / 0.0647 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` |
| overhead/print | anthropic | first_request_ms | wall | ms | 12 | 292 | 3.75 | 0.0128 [0.0127, 0.0129] | 5.2% | 1.2% | 1.3% / 1.1% | 2.25 / 0.0551 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` |
| overhead/print | anthropic | instructions | CPU | instructions | 12 | 2323.75M | 14.55M | 0.00626 [0.0062, 0.00632] | 4.8% | 0.4% | 0.3% / 1.2% | 7,910,528 / 261,312 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` |
| overhead/print | anthropic | peak_mem_mib | memory | MiB | 12 | 62.8 | 3.35 | 0.0533 [0.0497, 0.0569] | 9.1% | 1.3% | 1.1% / 6.3% | 1.07 / 0.399 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` |
| overhead/print | anthropic | peak_rss_mib | memory | MiB | 12 | 114 | 4.21 | 0.037 [0.0366, 0.0374] | 2.6% | 0.8% | 0.8% / 1.4% | 1.16 / 0.0684 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` |
| overhead/print | anthropic | teardown_ms | wall | ms | 12 | 17.5 | 0.896 | 0.0512 [0.0502, 0.0529] | 12.6% | 2.4% | 1.5% / 3.5% | 0.274 / 0.0405 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` |
| overhead/print | anthropic | wall_ms | wall | ms | 12 | 311 | 5.09 | 0.0164 [0.0162, 0.0165] | 6.3% | 1.2% | 1.3% / 1.0% | 1.83 / 0.072 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` |
| overhead/print | chat | cpu_ms | CPU | ms of CPU time | 12 | 428 | 6.55 | 0.0153 [0.015, 0.0156] | 8.8% | 1.9% | 1.6% / 2.7% | 12.1 / 0.317 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | chat | cycles | CPU | cycles | 12 | 1186.64M | 14.30M | 0.0121 [0.0119, 0.0125] | 8.8% | 1.8% | 1.6% / 3.2% | 29,576,145 / 652,012 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 405 | 4.65 | 0.0115 [0.0113, 0.0117] | 7.7% | 1.9% | 1.6% / 2.4% | 10.4 / 0.188 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | first_request_ms | wall | ms | 12 | 294 | 3.72 | 0.0127 [0.0125, 0.0128] | 5.9% | 2.1% | 1.7% / 2.1% | 3.48 / 0.0671 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print | chat | instructions | CPU | instructions | 12 | 2347.91M | 14.19M | 0.00604 [0.00599, 0.00611] | 4.3% | 0.2% | 0.4% / 1.5% | 7,542,734 / 191,196 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/print | chat | peak_mem_mib | memory | MiB | 12 | 63.5 | 3.38 | 0.0533 [0.049, 0.0558] | 9.0% | 1.8% | 1.3% / 6.1% | 0.479 / 0.38 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/print | chat | peak_rss_mib | memory | MiB | 12 | 114 | 4.16 | 0.0364 [0.0361, 0.0369] | 2.4% | 0.5% | 0.4% / 1.2% | 0.556 / 0.0781 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print | chat | teardown_ms | wall | ms | 12 | 20.2 | 0.974 | 0.0482 [0.0455, 0.0488] | 17.0% | 3.3% | 3.9% / 4.5% | 0.437 / 0.052 | 2 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/print | chat | wall_ms | wall | ms | 12 | 316 | 5.07 | 0.016 [0.0158, 0.0163] | 6.8% | 2.0% | 1.6% / 2.1% | 4.4 / 0.117 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/print | responses | cpu_ms | CPU | ms of CPU time | 12 | 425 | 6.67 | 0.0157 [0.0154, 0.0162] | 7.1% | 2.9% | 1.4% / 3.2% | 6.78 / 0.277 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` |
| overhead/print | responses | cycles | CPU | cycles | 12 | 1178.05M | 14.89M | 0.0126 [0.0123, 0.0131] | 8.0% | 2.9% | 1.4% / 3.7% | 17,455,521 / 779,828 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` |
| overhead/print | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 4.62 | 0.0115 [0.0112, 0.0119] | 7.2% | 3.0% | 1.4% / 3.4% | 6.78 / 0.208 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` |
| overhead/print | responses | first_request_ms | wall | ms | 12 | 295 | 3.7 | 0.0126 [0.0122, 0.0128] | 6.1% | 2.5% | 1.5% / 2.7% | 6.14 / 0.123 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` |
| overhead/print | responses | instructions | CPU | instructions | 12 | 2351.19M | 14.88M | 0.00633 [0.00623, 0.00634] | 4.2% | 0.4% | 0.4% / 2.5% | 4,128,707 / 232,511 | 1 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` |
| overhead/print | responses | peak_mem_mib | memory | MiB | 12 | 63.5 | 3.37 | 0.0531 [0.0501, 0.0553] | 9.6% | 0.8% | 0.9% / 6.1% | 0.704 / 0.275 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` |
| overhead/print | responses | peak_rss_mib | memory | MiB | 12 | 114 | 4.17 | 0.0366 [0.0362, 0.0368] | 1.5% | 1.0% | 1.4% / 2.6% | 1.35 / 0.0391 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` |
| overhead/print | responses | teardown_ms | wall | ms | 12 | 20.8 | 0.913 | 0.044 [0.0429, 0.045] | 11.9% | 1.6% | 0.8% / 5.9% | 0.104 / 0.0367 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` |
| overhead/print | responses | wall_ms | wall | ms | 12 | 316 | 5.1 | 0.0161 [0.0158, 0.0166] | 7.3% | 2.4% | 1.4% / 2.6% | 6.06 / 0.195 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` |
| overhead/print-tools | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 508 | 15.0 | 0.0295 [0.0291, 0.0299] | 2.8% | 1.4% | 2.6% / 1.9% | 7.39 / 0.345 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` |
| overhead/print-tools | anthropic | cycles | CPU | cycles | 12 | 1406.22M | 36.85M | 0.0262 [0.0258, 0.0266] | 2.1% | 1.4% | 2.6% / 2.1% | 20,029,746 / 962,763 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` |
| overhead/print-tools | anthropic | first_request_cpu_ms | CPU | ms of CPU time | 12 | 398 | 4.67 | 0.0117 [0.0115, 0.012] | 5.9% | 1.2% | 1.5% / 3.2% | 5.99 / 0.178 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` |
| overhead/print-tools | anthropic | first_request_ms | wall | ms | 12 | 292 | 3.73 | 0.0128 [0.0127, 0.0129] | 4.6% | 0.9% | 1.4% / 2.2% | 2.82 / 0.0458 | 1 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` |
| overhead/print-tools | anthropic | instructions | CPU | instructions | 12 | 2745.09M | 45.74M | 0.0167 [0.0165, 0.0168] | 1.0% | 0.2% | 0.2% / 1.1% | 8,283,082 / 651,479 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` |
| overhead/print-tools | anthropic | peak_mem_mib | memory | MiB | 12 | 86.0 | 5.18 | 0.0602 [0.0574, 0.0646] | 8.9% | 1.2% | 1.3% / 5.9% | 1.89 / 0.552 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | anthropic | peak_rss_mib | memory | MiB | 12 | 135 | 4.2 | 0.0312 [0.0306, 0.0315] | 2.5% | 1.0% | 1.2% / 1.5% | 2.82 / 0.0947 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` |
| overhead/print-tools | anthropic | teardown_ms | wall | ms | 12 | 20.2 | 1.18 | 0.0584 [0.0557, 0.0675] | 19.6% | 12.9% | 7.9% / 16.5% | 2.61 / 0.114 | 0 / 3 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 8.9 | 0.913 | 0.103 [0.0989, 0.104] | 3.6% | 6.7% | 10.2% / 2.8% | 0.219 / 0.034 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` |
| overhead/print-tools | anthropic | turn_gap_ms | wall | ms | 12 | 3.7 | 0.692 | 0.187 [0.179, 0.19] | 3.8% | 7.4% | 12.0% / 3.7% | 0.0789 / 0.0247 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` |
| overhead/print-tools | anthropic | wall_ms | wall | ms | 12 | 357 | 14.0 | 0.0394 [0.039, 0.0397] | 1.9% | 1.1% | 2.2% / 2.0% | 1.96 / 0.209 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` |
| overhead/print-tools | chat | cpu_ms | CPU | ms of CPU time | 12 | 518 | 14.3 | 0.0277 [0.0273, 0.028] | 2.6% | 2.0% | 1.8% / 1.1% | 6.54 / 0.243 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print-tools | chat | cycles | CPU | cycles | 12 | 1434.20M | 34.90M | 0.0243 [0.024, 0.0247] | 2.3% | 2.1% | 1.8% / 1.2% | 17,345,646 / 741,829 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print-tools | chat | first_request_cpu_ms | CPU | ms of CPU time | 12 | 399 | 4.63 | 0.0116 [0.0113, 0.0117] | 5.7% | 1.4% | 0.9% / 1.7% | 2.98 / 0.127 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print-tools | chat | first_request_ms | wall | ms | 12 | 293 | 3.66 | 0.0125 [0.0124, 0.0126] | 5.0% | 1.6% | 1.3% / 1.0% | 2.5 / 0.0591 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print-tools | chat | instructions | CPU | instructions | 12 | 2782.51M | 42.98M | 0.0154 [0.0153, 0.0156] | 1.6% | 0.3% | 0.2% / 1.0% | 5,500,458 / 750,266 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/print-tools | chat | peak_mem_mib | memory | MiB | 12 | 86.3 | 5.29 | 0.0613 [0.0576, 0.062] | 7.6% | 1.0% | 0.7% / 4.5% | 0.521 / 0.355 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/print-tools | chat | peak_rss_mib | memory | MiB | 12 | 135 | 4.19 | 0.031 [0.0308, 0.0313] | 2.0% | 1.0% | 0.9% / 2.8% | 1.46 / 0.0557 | 0 / 1 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |
| overhead/print-tools | chat | teardown_ms | wall | ms | 12 | 19.2 | 1.25 | 0.065 [0.0617, 0.0732] | 20.3% | 12.4% | 9.6% / 6.2% | 2.05 / 0.112 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.56 | 0.84 | 0.0879 [0.0815, 0.0913] | 9.9% | 12.1% | 10.8% / 2.4% | 0.84 / 0.0247 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print-tools | chat | turn_gap_ms | wall | ms | 12 | 4.01 | 0.628 | 0.157 [0.15, 0.167] | 8.5% | 13.7% | 12.9% / 2.8% | 0.278 / 0.0153 | 1 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | chat | wall_ms | wall | ms | 12 | 361 | 13.5 | 0.0373 [0.0369, 0.0379] | 2.7% | 2.0% | 1.8% / 1.3% | 4.8 / 0.261 | 0 / 0 | 0.00391 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/print-tools | responses | cpu_ms | CPU | ms of CPU time | 12 | 522 | 15.2 | 0.0291 [0.0286, 0.0297] | 2.8% | 2.5% | 3.3% / 1.9% | 9.6 / 0.308 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` |
| overhead/print-tools | responses | cycles | CPU | cycles | 12 | 1445.29M | 37.32M | 0.0258 [0.0254, 0.0264] | 2.6% | 2.6% | 3.2% / 1.9% | 25,635,734 / 783,662 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` |
| overhead/print-tools | responses | first_request_cpu_ms | CPU | ms of CPU time | 12 | 402 | 4.65 | 0.0116 [0.0113, 0.0118] | 6.2% | 1.4% | 1.4% / 3.0% | 5.71 / 0.183 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` |
| overhead/print-tools | responses | first_request_ms | wall | ms | 12 | 295 | 3.68 | 0.0125 [0.0123, 0.0126] | 4.4% | 1.6% | 1.6% / 2.5% | 5.1 / 0.0637 | 0 / 1 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` |
| overhead/print-tools | responses | instructions | CPU | instructions | 12 | 2792.76M | 46.14M | 0.0165 [0.0165, 0.0166] | 1.9% | 0.2% | 0.2% / 0.7% | 6,452,716 / 375,754 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` |
| overhead/print-tools | responses | peak_mem_mib | memory | MiB | 12 | 86.0 | 5.2 | 0.0605 [0.0593, 0.0629] | 9.8% | 1.2% | 0.9% / 4.3% | 1.16 / 0.254 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` |
| overhead/print-tools | responses | peak_rss_mib | memory | MiB | 12 | 135 | 4.17 | 0.031 [0.0304, 0.0313] | 3.1% | 1.1% | 0.9% / 1.6% | 1.29 / 0.0996 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` |
| overhead/print-tools | responses | teardown_ms | wall | ms | 12 | 16.9 | 1.23 | 0.0724 [0.0636, 0.0791] | 16.7% | 11.8% | 14.1% / 5.8% | 2.81 / 0.13 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` |
| overhead/print-tools | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 10.1 | 0.933 | 0.0919 [0.083, 0.0962] | 14.1% | 10.2% | 11.6% / 2.7% | 1.47 / 0.0304 | 0 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` |
| overhead/print-tools | responses | turn_gap_ms | wall | ms | 12 | 4.05 | 0.646 | 0.16 [0.152, 0.164] | 4.2% | 11.0% | 14.8% / 3.0% | 0.24 / 0.0256 | 2 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` |
| overhead/print-tools | responses | wall_ms | wall | ms | 12 | 362 | 13.8 | 0.038 [0.0373, 0.0382] | 2.6% | 2.4% | 2.8% / 1.6% | 5.7 / 0.178 | 1 / 0 | 0.00342 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` |
| overhead/rpc | anthropic | cpu_ms | CPU | ms of CPU time | 12 | 637 | 94.3 | 0.148 [0.144, 0.149] | 2.4% | 2.9% | 3.3% / 1.1% | 12.7 / 1.7 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cpu_ms` |
| overhead/rpc | anthropic | cycles | CPU | cycles | 12 | 1756.48M | 236.76M | 0.135 [0.132, 0.136] | 2.7% | 2.9% | 3.3% / 1.3% | 34,415,458 / 4,356,419 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cycles` |
| overhead/rpc | anthropic | instructions | CPU | instructions | 12 | 3209.13M | 324.83M | 0.101 [0.101, 0.102] | 0.8% | 0.3% | 0.2% / 0.5% | 7,831,587 / 2,313,204 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#instructions` |
| overhead/rpc | anthropic | peak_mem_mib | memory | MiB | 12 | 86.2 | 8.8 | 0.102 [0.1, 0.105] | 4.2% | 1.1% | 1.0% / 3.4% | 1.05 / 0.345 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_mem_mib` |
| overhead/rpc | anthropic | peak_rss_mib | memory | MiB | 12 | 139 | 23.7 | 0.171 [0.17, 0.172] | 1.3% | 0.6% | 0.7% / 0.8% | 0.745 / 0.182 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_rss_mib` |
| overhead/rpc | anthropic | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 4.17 | 0.0112 [0.0111, 0.0115] | 4.7% | 1.7% | 1.6% / 2.3% | 9.15 / 0.0935 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_cpu_ms` |
| overhead/rpc | anthropic | ready_ms | wall | ms | 12 | 264 | 3.09 | 0.0117 [0.0116, 0.0119] | 4.2% | 2.1% | 1.4% / 1.5% | 2.27 / 0.0561 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_ms` |
| overhead/rpc | anthropic | ready_pss_mib | memory | MiB | 12 | 107 | 11.5 | 0.107 [0.107, 0.109] | 2.3% | 0.8% | 0.7% / 1.1% | 0.59 / 0.245 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_pss_mib` |
| overhead/rpc | anthropic | ready_rss_mib | memory | MiB | 12 | 113 | 15.6 | 0.139 [0.138, 0.14] | 1.8% | 0.8% | 0.7% / 0.8% | 0.591 / 0.227 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_rss_mib` |
| overhead/rpc | anthropic | teardown_ms | wall | ms | 12 | 8.72 | 1.61 | 0.184 [0.164, 0.196] | 29.5% | 9.4% | 5.4% / 11.1% | 0.698 / 0.211 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#teardown_ms` |
| overhead/rpc | anthropic | turn_cpu_mean_ms | wall | ms | 12 | 10.3 | 4.4 | 0.428 [0.418, 0.432] | 2.3% | 5.6% | 6.7% / 1.2% | 0.232 / 0.0818 | 2 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_mean_ms` |
| overhead/rpc | anthropic | turn_cpu_ms | CPU | ms of CPU time | 12 | 9.08 | 4.37 | 0.481 [0.47, 0.503] | 6.2% | 4.8% | 4.1% / 1.7% | 0.466 / 0.112 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_ms` |
| overhead/rpc | anthropic | turn_harness_added_ms | wall | ms | 12 | 0.686 | 0.491 | 0.716 [0.691, 0.746] | 4.4% | 3.0% | 3.6% / 4.3% | 0.0182 / 0.0336 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_harness_added_ms` |
| overhead/rpc | anthropic | turn_turn_gap_ms | wall | ms | 12 | 3.03 | 1.09 | 0.359 [0.35, 0.365] | 6.0% | 2.7% | 2.6% / 2.8% | 0.0798 / 0.0231 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_turn_gap_ms` |
| overhead/rpc | anthropic | turn_wall_ms | wall | ms | 12 | 6.79 | 3.36 | 0.494 [0.484, 0.502] | 2.6% | 2.1% | 2.9% / 2.3% | 0.159 / 0.0683 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_wall_ms` |
| overhead/rpc | chat | cpu_ms | CPU | ms of CPU time | 12 | 676 | 90.0 | 0.133 [0.131, 0.136] | 4.5% | 2.5% | 2.5% / 1.5% | 13.2 / 2.38 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cpu_ms` |
| overhead/rpc | chat | cycles | CPU | cycles | 12 | 1863.43M | 224.13M | 0.12 [0.119, 0.123] | 4.3% | 2.5% | 2.5% / 1.6% | 34,831,120 / 6,285,380 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cycles` |
| overhead/rpc | chat | instructions | CPU | instructions | 12 | 3343.17M | 304.36M | 0.091 [0.0908, 0.0914] | 0.5% | 0.4% | 0.3% / 0.6% | 10,954,495 / 1,516,616 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#instructions` |
| overhead/rpc | chat | peak_mem_mib | memory | MiB | 12 | 89.1 | 8.22 | 0.0922 [0.091, 0.0945] | 3.4% | 0.9% | 0.8% / 2.5% | 0.892 / 0.297 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_mem_mib` |
| overhead/rpc | chat | peak_rss_mib | memory | MiB | 12 | 142 | 23.2 | 0.163 [0.162, 0.164] | 1.4% | 0.5% | 0.4% / 0.7% | 0.7 / 0.227 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_rss_mib` |
| overhead/rpc | chat | ready_cpu_ms | CPU | ms of CPU time | 12 | 369 | 4.22 | 0.0114 [0.0111, 0.0116] | 5.7% | 1.6% | 1.8% / 7.4% | 8.23 / 0.127 | 0 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_cpu_ms` |
| overhead/rpc | chat | ready_ms | wall | ms | 12 | 263 | 3.11 | 0.0118 [0.0117, 0.012] | 5.0% | 1.3% | 1.5% / 2.7% | 4.82 / 0.0364 | 0 / 1 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_ms` |
| overhead/rpc | chat | ready_pss_mib | memory | MiB | 12 | 107 | 11.7 | 0.109 [0.108, 0.11] | 2.0% | 1.1% | 0.6% / 1.3% | 0.724 / 0.23 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_pss_mib` |
| overhead/rpc | chat | ready_rss_mib | memory | MiB | 12 | 112 | 15.8 | 0.141 [0.139, 0.142] | 1.5% | 1.0% | 0.5% / 1.0% | 0.777 / 0.208 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_rss_mib` |
| overhead/rpc | chat | teardown_ms | wall | ms | 12 | 8.62 | 1.62 | 0.188 [0.148, 0.197] | 28.9% | 9.6% | 7.7% / 15.3% | 1.05 / 0.445 | 4 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#teardown_ms` |
| overhead/rpc | chat | turn_cpu_mean_ms | wall | ms | 12 | 11.9 | 4.16 | 0.351 [0.342, 0.358] | 4.3% | 5.9% | 4.2% / 1.5% | 0.206 / 0.109 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc | chat | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.2 | 4.19 | 0.374 [0.36, 0.39] | 3.5% | 3.9% | 3.0% / 2.1% | 0.472 / 0.159 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_ms` |
| overhead/rpc | chat | turn_harness_added_ms | wall | ms | 12 | 0.874 | 0.483 | 0.553 [0.539, 0.584] | 5.3% | 3.2% | 3.7% / 5.0% | 0.0447 / 0.0259 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_harness_added_ms` |
| overhead/rpc | chat | turn_turn_gap_ms | wall | ms | 12 | 3.25 | 1 | 0.308 [0.295, 0.312] | 5.5% | 2.4% | 3.0% / 3.5% | 0.0711 / 0.0397 | 1 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_turn_gap_ms` |
| overhead/rpc | chat | turn_wall_ms | wall | ms | 12 | 7.32 | 3.07 | 0.42 [0.412, 0.432] | 4.7% | 2.8% | 2.3% / 2.7% | 0.196 / 0.0925 | 0 / 0 | 0.00293 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_wall_ms` |
| overhead/rpc | responses | cpu_ms | CPU | ms of CPU time | 12 | 680 | 99.6 | 0.146 [0.144, 0.148] | 2.5% | 1.7% | 1.3% / 1.3% | 12.3 / 2.28 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cpu_ms` |
| overhead/rpc | responses | cycles | CPU | cycles | 12 | 1874.58M | 251.22M | 0.134 [0.132, 0.136] | 2.5% | 1.6% | 1.2% / 1.4% | 31,582,812 / 5,771,088 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cycles` |
| overhead/rpc | responses | instructions | CPU | instructions | 12 | 3379.56M | 344.35M | 0.102 [0.101, 0.102] | 0.8% | 0.3% | 0.2% / 0.6% | 10,393,734 / 3,040,526 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#instructions` |
| overhead/rpc | responses | peak_mem_mib | memory | MiB | 12 | 90.6 | 8.42 | 0.093 [0.0911, 0.094] | 2.4% | 1.3% | 1.1% / 2.3% | 0.707 / 0.175 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_mem_mib` |
| overhead/rpc | responses | peak_rss_mib | memory | MiB | 12 | 144 | 23.3 | 0.162 [0.162, 0.163] | 0.8% | 0.7% | 0.6% / 0.5% | 0.756 / 0.14 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_rss_mib` |
| overhead/rpc | responses | ready_cpu_ms | CPU | ms of CPU time | 12 | 371 | 4.22 | 0.0114 [0.0112, 0.0115] | 5.1% | 1.5% | 1.3% / 1.7% | 6.56 / 0.0965 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_cpu_ms` |
| overhead/rpc | responses | ready_ms | wall | ms | 12 | 265 | 3.1 | 0.0117 [0.0116, 0.0118] | 4.8% | 1.1% | 0.8% / 1.3% | 1.84 / 0.0574 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_ms` |
| overhead/rpc | responses | ready_pss_mib | memory | MiB | 12 | 107 | 11.6 | 0.109 [0.108, 0.11] | 1.3% | 0.6% | 0.8% / 1.1% | 1.06 / 0.195 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_pss_mib` |
| overhead/rpc | responses | ready_rss_mib | memory | MiB | 12 | 112 | 15.7 | 0.14 [0.139, 0.141] | 0.8% | 0.5% | 0.7% / 0.8% | 1.06 / 0.158 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_rss_mib` |
| overhead/rpc | responses | teardown_ms | wall | ms | 12 | 9.51 | 1.48 | 0.156 [0.139, 0.174] | 20.5% | 9.0% | 7.4% / 12.1% | 1.33 / 0.285 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#teardown_ms` |
| overhead/rpc | responses | turn_cpu_mean_ms | wall | ms | 12 | 12.1 | 4.66 | 0.384 [0.378, 0.395] | 2.8% | 3.0% | 2.5% / 1.3% | 0.453 / 0.109 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_mean_ms` |
| overhead/rpc | responses | turn_cpu_ms | CPU | ms of CPU time | 12 | 11.0 | 4.62 | 0.421 [0.403, 0.459] | 10.4% | 8.7% | 7.4% / 2.0% | 1.2 / 0.116 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_ms` |
| overhead/rpc | responses | turn_harness_added_ms | wall | ms | 12 | 0.885 | 0.436 | 0.492 [0.464, 0.511] | 9.0% | 3.4% | 3.9% / 5.7% | 0.0234 / 0.0359 | 1 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_harness_added_ms` |
| overhead/rpc | responses | turn_turn_gap_ms | wall | ms | 12 | 3.29 | 1.07 | 0.327 [0.319, 0.336] | 3.6% | 2.8% | 1.5% / 4.1% | 0.0715 / 0.0435 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_turn_gap_ms` |
| overhead/rpc | responses | turn_wall_ms | wall | ms | 12 | 7.46 | 3.41 | 0.458 [0.449, 0.467] | 3.0% | 3.1% | 2.1% / 2.3% | 0.175 / 0.0663 | 0 / 0 | 0.00244 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_wall_ms` |
| overhead/version | - | cpu_ms | CPU | ms of CPU time | 12 | 282 | 3.41 | 0.0121 [0.0115, 0.0124] | 8.9% | 1.7% | 1.0% / 4.5% | 2.84 / 0.214 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | CPU | cycles | 12 | 771.20M | 7.05M | 0.00915 [0.00865, 0.00941] | 9.7% | 1.7% | 0.9% / 5.1% | 5,972,803 / 537,735 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | CPU | instructions | 12 | 1636.72M | 6.56M | 0.00401 [0.00394, 0.00405] | 3.6% | 0.2% | 0.3% / 1.6% | 3,727,566 / 164,687 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | memory | MiB | 12 | 57.7 | 2.51 | 0.0435 [0.0431, 0.0478] | 9.9% | 1.6% | 1.1% / 5.1% | 0.617 / 0.252 | 0 / 5 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | memory | MiB | 12 | 107 | 4.12 | 0.0384 [0.0381, 0.039] | 2.0% | 1.3% | 1.1% / 1.2% | 1.61 / 0.0566 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | wall | ms | 12 | 218 | 1.98 | 0.00908 [0.00883, 0.00924] | 6.8% | 1.4% | 1.2% / 3.0% | 3.07 / 0.0755 | 0 / 0 | 0.00488 | no ±5.0% |  | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## pig-tip against its previous arm pig-0.4.1: 0.4.1 → 0.5.0 (newer / previous)

`pig-0.4.1` is the earlier arm and `pig-tip` the later one (declared as `previous` in the manifest; a loss means the later arm is measurably worse, a win measurably better). The floor is the larger of the two arms' A/A floors; a ratio inside it is no measurable difference.

| workload | api | metric | pig-0.4.1 median | pig-tip median | ratio [95% CI] | A/A floor | verdict |
|---|---|---|---:|---:|---|---:|---|
| overhead/rpc | anthropic | peak_rss_mib | 50.5 | 56.6 | 1.12 [1.11, 1.12] | 1.0% | **loss** |
| overhead/rpc | chat | peak_rss_mib | 50.7 | 56.9 | 1.12 [1.12, 1.13] | 0.8% | **loss** |
| overhead/rpc | responses | peak_rss_mib | 50.6 | 57.2 | 1.13 [1.12, 1.14] | 1.1% | **loss** |
| overhead/print | anthropic | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print | chat | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print | responses | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print-tools | anthropic | requests | 9 | 9 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print-tools | chat | requests | 9 | 9 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print-tools | responses | requests | 9 | 9 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print-tools | chat | teardown_ms | 3.35 | 1.86 | 0.556 [0.433, 0.862] | 96.4% | **no measurable difference** |
| overhead/rpc | anthropic | peak_mem_mib | 21.3 | 21.0 | 0.987 [0.967, 1] | 3.2% | **no measurable difference** |
| overhead/rpc | chat | peak_mem_mib | 21.4 | 20.8 | 0.973 [0.969, 0.99] | 2.9% | **no measurable difference** |
| overhead/rpc | responses | peak_mem_mib | 21.3 | 21.4 | 1 [0.993, 1.03] | 2.5% | **no measurable difference** |
| overhead/rpc | anthropic | requests | 40.0 | 40.0 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/rpc | chat | requests | 40.0 | 40.0 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/rpc | responses | requests | 40.0 | 40.0 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/version | - | peak_rss_mib | 6.45 | 6.97 | 1.08 [1.06, 1.1] | 8.6% | **no measurable difference** |
| overhead/print | anthropic | cpu_ms | 63.5 | 15.9 | 0.25 [0.243, 0.266] | 6.9% | **win** |
| overhead/print | chat | cpu_ms | 63.4 | 15.6 | 0.247 [0.241, 0.259] | 6.3% | **win** |
| overhead/print | responses | cpu_ms | 64.2 | 15.9 | 0.247 [0.241, 0.258] | 6.1% | **win** |
| overhead/print | anthropic | cycles | 162.15M | 38.18M | 0.235 [0.231, 0.253] | 6.0% | **win** |
| overhead/print | chat | cycles | 162.46M | 38.17M | 0.235 [0.232, 0.24] | 4.3% | **win** |
| overhead/print | responses | cycles | 164.11M | 38.63M | 0.235 [0.232, 0.238] | 3.1% | **win** |
| overhead/print | anthropic | first_request_cpu_ms | 57.9 | 13.5 | 0.234 [0.228, 0.25] | 6.9% | **win** |
| overhead/print | chat | first_request_cpu_ms | 56.0 | 13.5 | 0.242 [0.231, 0.261] | 9.5% | **win** |
| overhead/print | responses | first_request_cpu_ms | 58.3 | 13.5 | 0.232 [0.225, 0.244] | 7.5% | **win** |
| overhead/print | anthropic | first_request_ms | 33.3 | 11.6 | 0.348 [0.342, 0.352] | 4.2% | **win** |
| overhead/print | chat | first_request_ms | 32.9 | 11.7 | 0.355 [0.348, 0.363] | 3.5% | **win** |
| overhead/print | responses | first_request_ms | 33.6 | 11.7 | 0.348 [0.343, 0.353] | 4.2% | **win** |
| overhead/print | anthropic | instructions | 264.75M | 54.81M | 0.207 [0.203, 0.222] | 6.5% | **win** |
| overhead/print | chat | instructions | 264.84M | 54.26M | 0.205 [0.203, 0.207] | 1.3% | **win** |
| overhead/print | responses | instructions | 267.17M | 55.49M | 0.208 [0.207, 0.209] | 1.7% | **win** |
| overhead/print | anthropic | peak_mem_mib | 16.4 | 7.03 | 0.429 [0.424, 0.434] | 5.1% | **win** |
| overhead/print | chat | peak_mem_mib | 16.5 | 6.82 | 0.413 [0.406, 0.427] | 4.1% | **win** |
| overhead/print | responses | peak_mem_mib | 16.4 | 6.99 | 0.425 [0.408, 0.43] | 7.2% | **win** |
| overhead/print | anthropic | peak_rss_mib | 40.9 | 6.98 | 0.171 [0.17, 0.172] | 3.6% | **win** |
| overhead/print | chat | peak_rss_mib | 40.9 | 6.97 | 0.171 [0.169, 0.172] | 1.8% | **win** |
| overhead/print | responses | peak_rss_mib | 40.9 | 6.98 | 0.171 [0.17, 0.171] | 3.6% | **win** |
| overhead/print | anthropic | request_bytes | 6,113 | 6,075 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/print | chat | request_bytes | 6,052 | 6,014 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/print | responses | request_bytes | 6,017 | 5,979 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/print | anthropic | request_bytes_per_turn | 6,113 | 6,075 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/print | chat | request_bytes_per_turn | 6,052 | 6,014 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/print | responses | request_bytes_per_turn | 6,017 | 5,979 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/print | anthropic | teardown_ms | 3.03 | 1.76 | 0.581 [0.534, 0.667] | 19.1% | **win** |
| overhead/print | chat | teardown_ms | 3.15 | 1.62 | 0.516 [0.425, 0.582] | 41.6% | **win** |
| overhead/print | responses | teardown_ms | 3.19 | 1.71 | 0.536 [0.512, 0.571] | 23.9% | **win** |
| overhead/print | anthropic | wall_ms | 36.8 | 13.9 | 0.377 [0.367, 0.386] | 4.5% | **win** |
| overhead/print | chat | wall_ms | 36.4 | 13.7 | 0.376 [0.373, 0.378] | 3.1% | **win** |
| overhead/print | responses | wall_ms | 37.5 | 13.9 | 0.371 [0.368, 0.381] | 5.1% | **win** |
| overhead/print-tools | anthropic | cpu_ms | 118 | 28.1 | 0.238 [0.234, 0.246] | 4.5% | **win** |
| overhead/print-tools | chat | cpu_ms | 118 | 28.1 | 0.237 [0.233, 0.243] | 2.6% | **win** |
| overhead/print-tools | responses | cpu_ms | 120 | 30.2 | 0.252 [0.246, 0.255] | 3.5% | **win** |
| overhead/print-tools | anthropic | cycles | 309.69M | 71.50M | 0.231 [0.229, 0.233] | 2.1% | **win** |
| overhead/print-tools | chat | cycles | 309.89M | 71.32M | 0.23 [0.228, 0.234] | 2.1% | **win** |
| overhead/print-tools | responses | cycles | 312.78M | 75.54M | 0.242 [0.24, 0.246] | 1.3% | **win** |
| overhead/print-tools | anthropic | first_request_cpu_ms | 58.6 | 13.6 | 0.231 [0.226, 0.241] | 7.6% | **win** |
| overhead/print-tools | chat | first_request_cpu_ms | 58.5 | 13.4 | 0.229 [0.224, 0.252] | 4.8% | **win** |
| overhead/print-tools | responses | first_request_cpu_ms | 58.9 | 13.6 | 0.231 [0.226, 0.241] | 6.6% | **win** |
| overhead/print-tools | anthropic | first_request_ms | 33.3 | 11.6 | 0.347 [0.34, 0.35] | 3.5% | **win** |
| overhead/print-tools | chat | first_request_ms | 33.4 | 11.5 | 0.345 [0.339, 0.354] | 3.7% | **win** |
| overhead/print-tools | responses | first_request_ms | 33.6 | 11.6 | 0.345 [0.338, 0.351] | 2.9% | **win** |
| overhead/print-tools | anthropic | instructions | 561.03M | 100.65M | 0.179 [0.178, 0.18] | 1.1% | **win** |
| overhead/print-tools | chat | instructions | 563.05M | 100.13M | 0.178 [0.177, 0.18] | 1.4% | **win** |
| overhead/print-tools | responses | instructions | 569.63M | 112.13M | 0.197 [0.196, 0.199] | 0.8% | **win** |
| overhead/print-tools | anthropic | peak_mem_mib | 18.2 | 10.8 | 0.593 [0.584, 0.608] | 4.2% | **win** |
| overhead/print-tools | chat | peak_mem_mib | 18.1 | 10.9 | 0.602 [0.585, 0.616] | 3.7% | **win** |
| overhead/print-tools | responses | peak_mem_mib | 18.1 | 11.5 | 0.637 [0.628, 0.649] | 2.1% | **win** |
| overhead/print-tools | anthropic | peak_rss_mib | 47.1 | 6.98 | 0.148 [0.148, 0.15] | 1.8% | **win** |
| overhead/print-tools | chat | peak_rss_mib | 47.1 | 6.97 | 0.148 [0.147, 0.149] | 2.9% | **win** |
| overhead/print-tools | responses | peak_rss_mib | 47.0 | 6.98 | 0.148 [0.148, 0.149] | 2.7% | **win** |
| overhead/print-tools | anthropic | request_bytes | 128,007 | 127,593 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| overhead/print-tools | chat | request_bytes | 126,918 | 126,504 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| overhead/print-tools | responses | request_bytes | 125,523 | 125,109 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| overhead/print-tools | anthropic | request_bytes_per_turn | 14,223 | 14,177 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| overhead/print-tools | chat | request_bytes_per_turn | 14,102 | 14,056 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| overhead/print-tools | responses | request_bytes_per_turn | 13,947 | 13,901 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| overhead/print-tools | anthropic | teardown_ms | 3.24 | 1.75 | 0.54 [0.457, 0.649] | 32.0% | **win** |
| overhead/print-tools | responses | teardown_ms | 3.48 | 1.75 | 0.502 [0.479, 0.613] | 25.2% | **win** |
| overhead/print-tools | anthropic | turn_cpu_ms | 6.55 | 1.05 | 0.16 [0.153, 0.165] | 4.2% | **win** |
| overhead/print-tools | chat | turn_cpu_ms | 6.64 | 1.08 | 0.163 [0.158, 0.168] | 3.9% | **win** |
| overhead/print-tools | responses | turn_cpu_ms | 6.65 | 1.25 | 0.188 [0.184, 0.192] | 14.0% | **win** |
| overhead/print-tools | anthropic | turn_gap_ms | 4.06 | 0.939 | 0.231 [0.22, 0.24] | 7.2% | **win** |
| overhead/print-tools | chat | turn_gap_ms | 4.13 | 0.955 | 0.231 [0.223, 0.246] | 6.3% | **win** |
| overhead/print-tools | responses | turn_gap_ms | 4.23 | 1.1 | 0.26 [0.255, 0.27] | 5.5% | **win** |
| overhead/print-tools | anthropic | wall_ms | 73.1 | 27.2 | 0.372 [0.369, 0.375] | 2.8% | **win** |
| overhead/print-tools | chat | wall_ms | 73.6 | 27.4 | 0.372 [0.367, 0.391] | 6.3% | **win** |
| overhead/print-tools | responses | wall_ms | 74.9 | 28.8 | 0.385 [0.379, 0.395] | 3.4% | **win** |
| overhead/rpc | anthropic | cpu_ms | 438 | 69.4 | 0.159 [0.157, 0.16] | 2.4% | **win** |
| overhead/rpc | chat | cpu_ms | 433 | 70.1 | 0.162 [0.16, 0.164] | 2.2% | **win** |
| overhead/rpc | responses | cpu_ms | 456 | 81.1 | 0.178 [0.177, 0.181] | 1.8% | **win** |
| overhead/rpc | anthropic | cycles | 1181.85M | 182.88M | 0.155 [0.153, 0.156] | 1.9% | **win** |
| overhead/rpc | chat | cycles | 1169.37M | 184.48M | 0.158 [0.156, 0.16] | 1.9% | **win** |
| overhead/rpc | responses | cycles | 1232.14M | 214.98M | 0.174 [0.174, 0.177] | 1.6% | **win** |
| overhead/rpc | anthropic | instructions | 2282.06M | 251.97M | 0.11 [0.11, 0.111] | 1.3% | **win** |
| overhead/rpc | chat | instructions | 2264.75M | 251.94M | 0.111 [0.11, 0.112] | 1.3% | **win** |
| overhead/rpc | responses | instructions | 2391.81M | 362.31M | 0.151 [0.151, 0.153] | 1.2% | **win** |
| overhead/rpc | anthropic | ready_cpu_ms | 51.0 | 13.3 | 0.262 [0.256, 0.271] | 6.3% | **win** |
| overhead/rpc | chat | ready_cpu_ms | 50.4 | 13.2 | 0.261 [0.254, 0.266] | 2.4% | **win** |
| overhead/rpc | responses | ready_cpu_ms | 51.3 | 13.2 | 0.258 [0.254, 0.264] | 3.1% | **win** |
| overhead/rpc | anthropic | ready_ms | 29.8 | 25.9 | 0.87 [0.861, 0.878] | 3.4% | **win** |
| overhead/rpc | chat | ready_ms | 29.5 | 25.9 | 0.878 [0.873, 0.886] | 2.6% | **win** |
| overhead/rpc | responses | ready_ms | 29.5 | 25.8 | 0.876 [0.858, 0.88] | 2.6% | **win** |
| overhead/rpc | anthropic | ready_pss_mib | 41.4 | 38.5 | 0.93 [0.922, 0.937] | 1.3% | **win** |
| overhead/rpc | chat | ready_pss_mib | 41.6 | 38.4 | 0.922 [0.915, 0.932] | 0.9% | **win** |
| overhead/rpc | responses | ready_pss_mib | 41.3 | 38.5 | 0.931 [0.92, 0.938] | 2.3% | **win** |
| overhead/rpc | anthropic | ready_rss_mib | 43.3 | 40.4 | 0.933 [0.925, 0.94] | 1.3% | **win** |
| overhead/rpc | chat | ready_rss_mib | 43.5 | 40.3 | 0.925 [0.919, 0.935] | 0.9% | **win** |
| overhead/rpc | responses | ready_rss_mib | 43.2 | 40.4 | 0.934 [0.924, 0.94] | 2.2% | **win** |
| overhead/rpc | anthropic | request_bytes | 1.13M | 1.13M | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc | chat | request_bytes | 1.11M | 1.11M | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc | responses | request_bytes | 1.14M | 1.14M | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc | anthropic | request_bytes_per_turn | 56,567 | 56,451 | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc | chat | request_bytes_per_turn | 55,670 | 55,554 | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc | responses | request_bytes_per_turn | 57,036 | 56,920 | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc | anthropic | teardown_ms | 3.56 | 2.05 | 0.576 [0.49, 0.631] | 23.5% | **win** |
| overhead/rpc | chat | teardown_ms | 3.62 | 1.98 | 0.547 [0.435, 0.715] | 39.5% | **win** |
| overhead/rpc | responses | teardown_ms | 3.79 | 2.05 | 0.542 [0.462, 0.635] | 30.0% | **win** |
| overhead/rpc | anthropic | turn_cpu_mean_ms | 19.2 | 2.51 | 0.131 [0.13, 0.133] | 2.0% | **win** |
| overhead/rpc | chat | turn_cpu_mean_ms | 18.9 | 2.55 | 0.135 [0.134, 0.136] | 2.2% | **win** |
| overhead/rpc | responses | turn_cpu_mean_ms | 20.1 | 3.12 | 0.155 [0.155, 0.158] | 2.3% | **win** |
| overhead/rpc | anthropic | turn_cpu_ms | 17.7 | 2.32 | 0.131 [0.125, 0.133] | 5.0% | **win** |
| overhead/rpc | chat | turn_cpu_ms | 17.7 | 2.34 | 0.132 [0.13, 0.136] | 3.0% | **win** |
| overhead/rpc | responses | turn_cpu_ms | 20.3 | 3.01 | 0.149 [0.141, 0.155] | 9.5% | **win** |
| overhead/rpc | anthropic | turn_harness_added_ms | 0.829 | 0.227 | 0.274 [0.266, 0.289] | 5.4% | **win** |
| overhead/rpc | chat | turn_harness_added_ms | 0.928 | 0.264 | 0.285 [0.275, 0.292] | 4.6% | **win** |
| overhead/rpc | responses | turn_harness_added_ms | 0.949 | 0.211 | 0.222 [0.204, 0.24] | 10.5% | **win** |
| overhead/rpc | anthropic | turn_turn_gap_ms | 5.19 | 1.02 | 0.197 [0.193, 0.201] | 3.0% | **win** |
| overhead/rpc | chat | turn_turn_gap_ms | 5.25 | 1.06 | 0.203 [0.197, 0.208] | 3.4% | **win** |
| overhead/rpc | responses | turn_turn_gap_ms | 5.32 | 1.32 | 0.248 [0.242, 0.251] | 3.0% | **win** |
| overhead/rpc | anthropic | turn_wall_ms | 11.7 | 3 | 0.256 [0.253, 0.262] | 2.3% | **win** |
| overhead/rpc | chat | turn_wall_ms | 11.8 | 2.91 | 0.246 [0.242, 0.253] | 2.9% | **win** |
| overhead/rpc | responses | turn_wall_ms | 12.3 | 3.75 | 0.304 [0.299, 0.311] | 2.4% | **win** |
| overhead/version | - | cpu_ms | 17.6 | 5.24 | 0.298 [0.287, 0.325] | 18.1% | **win** |
| overhead/version | - | cycles | 37.62M | 11.14M | 0.296 [0.29, 0.306] | 6.9% | **win** |
| overhead/version | - | instructions | 63.68M | 14.14M | 0.222 [0.22, 0.234] | 7.5% | **win** |
| overhead/version | - | peak_mem_mib | 8.85 | 3.98 | 0.45 [0.428, 0.472] | 12.6% | **win** |
| overhead/version | - | wall_ms | 11.7 | 4.21 | 0.359 [0.348, 0.374] | 8.8% | **win** |

## A/A noise floor

Each arm's A/A copy `<id>-b` is the same executable run in the same rounds. The floor of a cell is the largest deviation from 1 the copy's ratio-of-medians interval allows; a difference between arms smaller than the floor is reported as no measurable difference. The table gives, per arm and workload, the median and the maximum floor over the scored metrics, and the reference's minimum detectable effect at 80% power.

| arm | workload | api | cells | median floor | max floor | worst metric |
|---|---|---|---:|---:|---:|---|
| claude-code | overhead/print | anthropic | 12 | 2.8% | 15.2% | teardown_ms |
| claude-code | overhead/print-tools | anthropic | 14 | 6.6% | 18.1% | turn_cpu_ms |
| claude-code | overhead/version | - | 6 | 17.4% | 20.7% | wall_ms |
| codex | overhead/print | responses | 12 | 3.5% | 16.6% | teardown_ms |
| codex | overhead/print-tools | responses | 14 | 1.8% | 12.7% | teardown_ms |
| codex | overhead/version | - | 6 | 7.5% | 9.5% | cpu_ms |
| copilot | overhead/print | anthropic | 12 | 0.9% | 3.4% | teardown_ms |
| copilot | overhead/print | chat | 12 | 1.3% | 4.2% | teardown_ms |
| copilot | overhead/print | responses | 12 | 1.5% | 6.5% | teardown_ms |
| copilot | overhead/print-tools | anthropic | 14 | 0.9% | 4.5% | teardown_ms |
| copilot | overhead/print-tools | chat | 14 | 0.9% | 4.9% | teardown_ms |
| copilot | overhead/print-tools | responses | 14 | 1.3% | 2.2% | teardown_ms |
| copilot | overhead/version | - | 6 | 2.3% | 4.8% | peak_mem_mib |
| octet | overhead/print | chat | 12 | 4.5% | 18.8% | first_request_ms |
| octet | overhead/print-tools | chat | 14 | 2.2% | 17.8% | first_request_ms |
| octet | overhead/rpc | chat | 18 | 1.8% | 23.3% | ready_ms |
| octet | overhead/version | - | 6 | 3.2% | 3.5% | wall_ms |
| opencode-v2 | overhead/print | chat | 13 | 4.4% | 15.0% | teardown_ms |
| opencode-v2 | overhead/print-tools | chat | 15 | 6.9% | 25.5% | turn_gap_ms |
| opencode-v2 | overhead/version | - | 6 | 4.6% | 20.2% | peak_rss_mib |
| pi-bun | overhead/print | anthropic | 12 | 1.2% | 19.8% | teardown_ms |
| pi-bun | overhead/print | chat | 12 | 2.0% | 19.2% | teardown_ms |
| pi-bun | overhead/print | responses | 12 | 0.8% | 8.9% | teardown_ms |
| pi-bun | overhead/print-tools | anthropic | 14 | 1.0% | 13.4% | teardown_ms |
| pi-bun | overhead/print-tools | chat | 14 | 1.1% | 16.5% | teardown_ms |
| pi-bun | overhead/print-tools | responses | 14 | 1.8% | 12.9% | teardown_ms |
| pi-bun | overhead/rpc | anthropic | 18 | 1.6% | 17.9% | turn_turn_gap_ms |
| pi-bun | overhead/rpc | chat | 18 | 1.5% | 24.9% | turn_turn_gap_ms |
| pi-bun | overhead/rpc | responses | 18 | 1.1% | 17.1% | turn_harness_added_ms |
| pi-bun | overhead/version | - | 6 | 2.3% | 3.3% | peak_mem_mib |
| pi-node | overhead/print | anthropic | 12 | 1.3% | 2.3% | first_request_cpu_ms |
| pi-node | overhead/print | chat | 12 | 1.5% | 3.0% | cpu_ms |
| pi-node | overhead/print | responses | 12 | 1.1% | 2.7% | first_request_ms |
| pi-node | overhead/print-tools | anthropic | 14 | 1.4% | 15.0% | teardown_ms |
| pi-node | overhead/print-tools | chat | 14 | 1.6% | 14.4% | teardown_ms |
| pi-node | overhead/print-tools | responses | 14 | 2.4% | 16.7% | teardown_ms |
| pi-node | overhead/rpc | anthropic | 18 | 2.0% | 11.9% | teardown_ms |
| pi-node | overhead/rpc | chat | 18 | 2.2% | 15.9% | teardown_ms |
| pi-node | overhead/rpc | responses | 18 | 1.8% | 12.0% | teardown_ms |
| pi-node | overhead/version | - | 6 | 1.5% | 1.6% | wall_ms |
| pibolt | overhead/print | anthropic | 12 | 2.0% | 15.7% | teardown_ms |
| pibolt | overhead/print | chat | 12 | 2.4% | 19.3% | teardown_ms |
| pibolt | overhead/print | responses | 12 | 2.3% | 14.0% | teardown_ms |
| pibolt | overhead/print-tools | anthropic | 14 | 2.4% | 15.8% | teardown_ms |
| pibolt | overhead/print-tools | chat | 14 | 2.6% | 16.3% | teardown_ms |
| pibolt | overhead/print-tools | responses | 14 | 3.4% | 15.6% | teardown_ms |
| pibolt | overhead/rpc | anthropic | 18 | 1.6% | 14.3% | teardown_ms |
| pibolt | overhead/rpc | chat | 18 | 1.2% | 23.7% | teardown_ms |
| pibolt | overhead/rpc | responses | 18 | 2.6% | 15.9% | teardown_ms |
| pibolt | overhead/version | - | 6 | 5.1% | 6.8% | cpu_ms |
| pig-0.4.1 | overhead/print | anthropic | 12 | 4.2% | 16.0% | teardown_ms |
| pig-0.4.1 | overhead/print | chat | 12 | 1.7% | 41.6% | teardown_ms |
| pig-0.4.1 | overhead/print | responses | 12 | 4.0% | 23.9% | teardown_ms |
| pig-0.4.1 | overhead/print-tools | anthropic | 14 | 2.6% | 32.0% | teardown_ms |
| pig-0.4.1 | overhead/print-tools | chat | 14 | 1.9% | 35.2% | teardown_ms |
| pig-0.4.1 | overhead/print-tools | responses | 14 | 1.0% | 20.0% | teardown_ms |
| pig-0.4.1 | overhead/rpc | anthropic | 18 | 2.3% | 23.5% | teardown_ms |
| pig-0.4.1 | overhead/rpc | chat | 18 | 1.9% | 39.5% | teardown_ms |
| pig-0.4.1 | overhead/rpc | responses | 18 | 2.3% | 30.0% | teardown_ms |
| pig-0.4.1 | overhead/version | - | 6 | 5.0% | 8.6% | peak_rss_mib |
| pig-tip | overhead/print | anthropic | 12 | 3.6% | 19.1% | teardown_ms |
| pig-tip | overhead/print | chat | 12 | 3.1% | 8.3% | teardown_ms |
| pig-tip | overhead/print | responses | 12 | 3.6% | 7.5% | first_request_cpu_ms |
| pig-tip | overhead/print-tools | anthropic | 14 | 3.3% | 22.7% | teardown_ms |
| pig-tip | overhead/print-tools | chat | 14 | 3.7% | 96.4% | teardown_ms |
| pig-tip | overhead/print-tools | responses | 14 | 2.1% | 25.2% | teardown_ms |
| pig-tip | overhead/rpc | anthropic | 18 | 1.4% | 13.7% | teardown_ms |
| pig-tip | overhead/rpc | chat | 18 | 1.2% | 26.0% | teardown_ms |
| pig-tip | overhead/rpc | responses | 18 | 1.3% | 15.5% | teardown_ms |
| pig-tip | overhead/version | - | 6 | 8.8% | 18.1% | cpu_ms |
| rpi | overhead/print | anthropic | 12 | 6.1% | 12.6% | teardown_ms |
| rpi | overhead/print | chat | 12 | 6.8% | 17.0% | teardown_ms |
| rpi | overhead/print | responses | 12 | 7.1% | 11.9% | teardown_ms |
| rpi | overhead/print-tools | anthropic | 14 | 2.8% | 19.6% | teardown_ms |
| rpi | overhead/print-tools | chat | 14 | 2.7% | 20.3% | teardown_ms |
| rpi | overhead/print-tools | responses | 14 | 2.7% | 16.2% | teardown_ms |
| rpi | overhead/rpc | anthropic | 18 | 2.4% | 29.5% | teardown_ms |
| rpi | overhead/rpc | chat | 18 | 2.4% | 28.9% | teardown_ms |
| rpi | overhead/rpc | responses | 18 | 2.5% | 20.5% | teardown_ms |
| rpi | overhead/version | - | 6 | 8.9% | 9.9% | peak_mem_mib |

Minimum detectable effect of the reference's A/A pair over all cells: median 1.4%, worst 13.7%. A difference smaller than the cell's MDE cannot be seen in this run.

## Cell ids and rerun commands

Every cell has an id, `<run id>::<workload>@<api>#<metric>`. `python3 -m buffon rerun <cell id> --site <your site profile>` repeats the plan of the run that holds the cell (its arms, rounds, seed and parameters) for that workload and API only, on your host, and compares your result with the original. The raw samples of every cell are in the run directory's raw.json; this report is generated from them and from nothing else, and `buffon verify` regenerates it to check that no number was edited.

| workload | api | metric | cell id |
|---|---|---|---|
| overhead/print | anthropic | cpu_ms | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cpu_ms` |
| overhead/print | anthropic | cycles | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#cycles` |
| overhead/print | anthropic | first_request_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_cpu_ms` |
| overhead/print | anthropic | first_request_ms | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#first_request_ms` |
| overhead/print | anthropic | instructions | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#instructions` |
| overhead/print | anthropic | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_mem_mib` |
| overhead/print | anthropic | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#peak_rss_mib` |
| overhead/print | anthropic | request_bytes | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes` |
| overhead/print | anthropic | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#request_bytes_per_turn` |
| overhead/print | anthropic | requests | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#requests` |
| overhead/print | anthropic | side_requests | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#side_requests` |
| overhead/print | anthropic | teardown_ms | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#teardown_ms` |
| overhead/print | anthropic | wall_ms | `2026-10-19-smc1-launch-core::overhead/print@anthropic-messages#wall_ms` |
| overhead/print | chat | cpu_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cpu_ms` |
| overhead/print | chat | cycles | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#cycles` |
| overhead/print | chat | first_request_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_cpu_ms` |
| overhead/print | chat | first_request_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#first_request_ms` |
| overhead/print | chat | instructions | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#instructions` |
| overhead/print | chat | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_mem_mib` |
| overhead/print | chat | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#peak_rss_mib` |
| overhead/print | chat | request_bytes | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes` |
| overhead/print | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#request_bytes_per_turn` |
| overhead/print | chat | requests | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#requests` |
| overhead/print | chat | side_requests | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#side_requests` |
| overhead/print | chat | teardown_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#teardown_ms` |
| overhead/print | chat | wall_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-completions#wall_ms` |
| overhead/print | responses | cpu_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cpu_ms` |
| overhead/print | responses | cycles | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#cycles` |
| overhead/print | responses | first_request_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_cpu_ms` |
| overhead/print | responses | first_request_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#first_request_ms` |
| overhead/print | responses | instructions | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#instructions` |
| overhead/print | responses | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_mem_mib` |
| overhead/print | responses | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#peak_rss_mib` |
| overhead/print | responses | request_bytes | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes` |
| overhead/print | responses | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#request_bytes_per_turn` |
| overhead/print | responses | requests | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#requests` |
| overhead/print | responses | side_requests | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#side_requests` |
| overhead/print | responses | teardown_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#teardown_ms` |
| overhead/print | responses | wall_ms | `2026-10-19-smc1-launch-core::overhead/print@openai-responses#wall_ms` |
| overhead/print-tools | anthropic | cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cpu_ms` |
| overhead/print-tools | anthropic | cycles | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#cycles` |
| overhead/print-tools | anthropic | first_request_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_cpu_ms` |
| overhead/print-tools | anthropic | first_request_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#first_request_ms` |
| overhead/print-tools | anthropic | instructions | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#instructions` |
| overhead/print-tools | anthropic | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_mem_mib` |
| overhead/print-tools | anthropic | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#peak_rss_mib` |
| overhead/print-tools | anthropic | request_bytes | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes` |
| overhead/print-tools | anthropic | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#request_bytes_per_turn` |
| overhead/print-tools | anthropic | requests | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#requests` |
| overhead/print-tools | anthropic | side_requests | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#side_requests` |
| overhead/print-tools | anthropic | teardown_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#teardown_ms` |
| overhead/print-tools | anthropic | turn_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_cpu_ms` |
| overhead/print-tools | anthropic | turn_gap_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#turn_gap_ms` |
| overhead/print-tools | anthropic | wall_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@anthropic-messages#wall_ms` |
| overhead/print-tools | chat | cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cpu_ms` |
| overhead/print-tools | chat | cycles | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#cycles` |
| overhead/print-tools | chat | first_request_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_cpu_ms` |
| overhead/print-tools | chat | first_request_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#first_request_ms` |
| overhead/print-tools | chat | instructions | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#instructions` |
| overhead/print-tools | chat | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_mem_mib` |
| overhead/print-tools | chat | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#peak_rss_mib` |
| overhead/print-tools | chat | request_bytes | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes` |
| overhead/print-tools | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#request_bytes_per_turn` |
| overhead/print-tools | chat | requests | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#requests` |
| overhead/print-tools | chat | side_requests | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#side_requests` |
| overhead/print-tools | chat | teardown_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#teardown_ms` |
| overhead/print-tools | chat | turn_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_cpu_ms` |
| overhead/print-tools | chat | turn_gap_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#turn_gap_ms` |
| overhead/print-tools | chat | wall_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-completions#wall_ms` |
| overhead/print-tools | responses | cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cpu_ms` |
| overhead/print-tools | responses | cycles | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#cycles` |
| overhead/print-tools | responses | first_request_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_cpu_ms` |
| overhead/print-tools | responses | first_request_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#first_request_ms` |
| overhead/print-tools | responses | instructions | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#instructions` |
| overhead/print-tools | responses | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_mem_mib` |
| overhead/print-tools | responses | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#peak_rss_mib` |
| overhead/print-tools | responses | request_bytes | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes` |
| overhead/print-tools | responses | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#request_bytes_per_turn` |
| overhead/print-tools | responses | requests | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#requests` |
| overhead/print-tools | responses | side_requests | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#side_requests` |
| overhead/print-tools | responses | teardown_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#teardown_ms` |
| overhead/print-tools | responses | turn_cpu_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_cpu_ms` |
| overhead/print-tools | responses | turn_gap_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#turn_gap_ms` |
| overhead/print-tools | responses | wall_ms | `2026-10-19-smc1-launch-core::overhead/print-tools@openai-responses#wall_ms` |
| overhead/rpc | anthropic | cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cpu_ms` |
| overhead/rpc | anthropic | cycles | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#cycles` |
| overhead/rpc | anthropic | instructions | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#instructions` |
| overhead/rpc | anthropic | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_mem_mib` |
| overhead/rpc | anthropic | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#peak_rss_mib` |
| overhead/rpc | anthropic | ready_cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_cpu_ms` |
| overhead/rpc | anthropic | ready_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_ms` |
| overhead/rpc | anthropic | ready_pss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_pss_mib` |
| overhead/rpc | anthropic | ready_rss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#ready_rss_mib` |
| overhead/rpc | anthropic | request_bytes | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes` |
| overhead/rpc | anthropic | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#request_bytes_per_turn` |
| overhead/rpc | anthropic | requests | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#requests` |
| overhead/rpc | anthropic | side_requests | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#side_requests` |
| overhead/rpc | anthropic | teardown_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#teardown_ms` |
| overhead/rpc | anthropic | turn_cpu_mean_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_mean_ms` |
| overhead/rpc | anthropic | turn_cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_cpu_ms` |
| overhead/rpc | anthropic | turn_harness_added_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_harness_added_ms` |
| overhead/rpc | anthropic | turn_turn_gap_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_turn_gap_ms` |
| overhead/rpc | anthropic | turn_wall_ms | `2026-10-19-smc1-launch-core::overhead/rpc@anthropic-messages#turn_wall_ms` |
| overhead/rpc | chat | cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cpu_ms` |
| overhead/rpc | chat | cycles | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#cycles` |
| overhead/rpc | chat | instructions | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#instructions` |
| overhead/rpc | chat | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_mem_mib` |
| overhead/rpc | chat | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#peak_rss_mib` |
| overhead/rpc | chat | ready_cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_cpu_ms` |
| overhead/rpc | chat | ready_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_ms` |
| overhead/rpc | chat | ready_pss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_pss_mib` |
| overhead/rpc | chat | ready_rss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#ready_rss_mib` |
| overhead/rpc | chat | request_bytes | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes` |
| overhead/rpc | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#request_bytes_per_turn` |
| overhead/rpc | chat | requests | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#requests` |
| overhead/rpc | chat | side_requests | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#side_requests` |
| overhead/rpc | chat | teardown_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#teardown_ms` |
| overhead/rpc | chat | turn_cpu_mean_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc | chat | turn_cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_cpu_ms` |
| overhead/rpc | chat | turn_harness_added_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_harness_added_ms` |
| overhead/rpc | chat | turn_turn_gap_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_turn_gap_ms` |
| overhead/rpc | chat | turn_wall_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-completions#turn_wall_ms` |
| overhead/rpc | responses | cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cpu_ms` |
| overhead/rpc | responses | cycles | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#cycles` |
| overhead/rpc | responses | instructions | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#instructions` |
| overhead/rpc | responses | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_mem_mib` |
| overhead/rpc | responses | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#peak_rss_mib` |
| overhead/rpc | responses | ready_cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_cpu_ms` |
| overhead/rpc | responses | ready_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_ms` |
| overhead/rpc | responses | ready_pss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_pss_mib` |
| overhead/rpc | responses | ready_rss_mib | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#ready_rss_mib` |
| overhead/rpc | responses | request_bytes | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes` |
| overhead/rpc | responses | request_bytes_per_turn | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#request_bytes_per_turn` |
| overhead/rpc | responses | requests | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#requests` |
| overhead/rpc | responses | side_requests | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#side_requests` |
| overhead/rpc | responses | teardown_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#teardown_ms` |
| overhead/rpc | responses | turn_cpu_mean_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_mean_ms` |
| overhead/rpc | responses | turn_cpu_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_cpu_ms` |
| overhead/rpc | responses | turn_harness_added_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_harness_added_ms` |
| overhead/rpc | responses | turn_turn_gap_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_turn_gap_ms` |
| overhead/rpc | responses | turn_wall_ms | `2026-10-19-smc1-launch-core::overhead/rpc@openai-responses#turn_wall_ms` |
| overhead/version | - | cpu_ms | `2026-10-19-smc1-launch-core::overhead/version@-#cpu_ms` |
| overhead/version | - | cycles | `2026-10-19-smc1-launch-core::overhead/version@-#cycles` |
| overhead/version | - | instructions | `2026-10-19-smc1-launch-core::overhead/version@-#instructions` |
| overhead/version | - | peak_mem_mib | `2026-10-19-smc1-launch-core::overhead/version@-#peak_mem_mib` |
| overhead/version | - | peak_rss_mib | `2026-10-19-smc1-launch-core::overhead/version@-#peak_rss_mib` |
| overhead/version | - | wall_ms | `2026-10-19-smc1-launch-core::overhead/version@-#wall_ms` |

## Noise report

How noisy this run was, from its own samples and the telemetry taken around each one (docs/TELEMETRY.md). The A/A figures compare each arm with its own identical copy, so they show what the host does to two runs of the same executable.

### Per metric

| metric | cells | A/A gap median | A/A gap worst | A/A floor median | A/A floor worst | CV median | CV worst | outliers / values | drift median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cpu_ms | 10 | 0.9% | 16.0% | 2.5% | 20.0% | 1.6% | 12.2% | 49 / 1920 | 0.9% |
| cycles | 10 | 0.8% | 14.3% | 2.2% | 17.4% | 1.4% | 10.0% | 48 / 1920 | 0.8% |
| first_request_cpu_ms | 6 | 1.4% | 4.0% | 3.3% | 9.5% | 1.6% | 6.0% | 21 / 1200 | 0.9% |
| first_request_ms | 6 | 1.4% | 7.7% | 2.9% | 18.8% | 1.4% | 11.0% | 14 / 1200 | 0.6% |
| instructions | 10 | 0.5% | 12.4% | 1.3% | 14.2% | 0.7% | 4.2% | 75 / 1920 | 0.3% |
| peak_mem_mib | 10 | 0.5% | 3.9% | 1.8% | 12.6% | 1.3% | 7.2% | 28 / 1920 | 0.7% |
| peak_rss_mib | 10 | 0.5% | 16.5% | 1.1% | 20.2% | 0.7% | 11.3% | 70 / 1920 | 0.4% |
| ready_cpu_ms | 3 | 1.5% | 3.7% | 2.7% | 6.3% | 1.7% | 7.4% | 16 / 456 | 0.8% |
| ready_ms | 3 | 1.3% | 4.0% | 2.3% | 23.3% | 1.2% | 10.7% | 13 / 456 | 0.5% |
| ready_pss_mib | 3 | 0.1% | 2.2% | 1.0% | 3.2% | 0.8% | 1.6% | 2 / 456 | 0.4% |
| ready_rss_mib | 3 | 0.2% | 1.7% | 1.1% | 2.5% | 0.8% | 1.7% | 1 / 456 | 0.7% |
| request_bytes | 9 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 1656 | 0.0% |
| request_bytes_per_turn | 9 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 1656 | 0.0% |
| requests | 9 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 1656 | 0.0% |
| side_requests | 9 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 1656 | 0.0% |
| teardown_ms | 9 | 6.7% | 19.8% | 15.5% | 96.4% | 7.8% | 44.2% | 53 / 1656 | 2.5% |
| turn_cpu_mean_ms | 3 | 0.4% | 2.4% | 2.3% | 5.9% | 1.5% | 6.7% | 16 / 456 | 0.9% |
| turn_cpu_ms | 6 | 0.7% | 7.6% | 3.7% | 18.1% | 3.4% | 20.6% | 48 / 1056 | 1.8% |
| turn_gap_ms | 3 | 0.7% | 6.1% | 3.8% | 25.5% | 3.1% | 14.8% | 17 / 600 | 1.3% |
| turn_harness_added_ms | 3 | 0.9% | 3.5% | 4.6% | 17.1% | 3.8% | 18.5% | 8 / 456 | 3.2% |
| turn_turn_gap_ms | 3 | 0.6% | 3.6% | 3.0% | 24.9% | 2.5% | 13.5% | 5 / 456 | 1.6% |
| turn_wall_ms | 3 | 0.5% | 3.1% | 2.4% | 5.5% | 2.2% | 4.6% | 1 / 456 | 0.9% |
| wall_ms | 7 | 1.2% | 16.8% | 2.8% | 20.7% | 1.4% | 6.5% | 27 / 1464 | 0.7% |

A/A gap: the copy's median against the arm's, per cell. A/A floor: the largest deviation from 1 the copy's ratio interval allows (METHODOLOGY section 6). CV: the standard deviation of an arm's rounds over their mean. Outliers: a measured value is an outlier when |x - median| > 5 x 1.4826 x MAD of its arm's values in that cell (needs 4 values; with MAD 0, any different value). Outliers are counted, never removed. Drift: the Theil-Sen trend of an arm's rounds times the rounds spanned, as a share of its median.

### Run 1

- Samples: 1920 measured (1920 ok, 0 failed), 160 warm-up; telemetry on 1920 of 1920 ok samples. Sources read: cgroup_throttle, cpufreq, loadavg, meminfo, pressure, proc_stat, schedstat, thermal_throttle, vmstat.
- Calibration: CV 1.6% of cpu_ms on pi-node (gate 5.0%), passed.
- CFS throttling: 0 samples, 0 us in all; the session's cgroup lost 0 us over the whole run.
- Quiet-host gate: 1920 passed at once, 0 waited (longest 0.0 s, 0.0 s in all), 0 gave up.
- Steal: 0.000% of the pinned CPUs' capacity. Foreign CPU on the pinned CPUs: p95 0.0% of the sample's CPU time. Clock: largest deviation 0.2% from the median 2800 MHz. iowait is recorded in every sample and never gated.
- Failed samples: 0 arm, 0 infrastructure (the arm is not charged for those); 0 ladder stops (a swarm rung that hit the kernel's limit: a result, not a failure). CPU quota on the arm cgroup or an ancestor: none.
- Flagged samples: 0 of 1920.
- Telemetry cost: the collector's thread used 5.54 ms median per sample (worst 18.70 ms), on the runner's CPUs, outside the pinned set.
- Host load before / after: 1.3 / 1.0; pinned CPUs busy over the run: mean 7.8%, max 28.9%.

### Samples and rounds not in the statistics

| reason | samples | rounds |
|---|---:|---:|
| warm-up round (kept in the raw data, excluded from the statistics by rule) | 160 | 1 |

Flags (buffon/report/thresholds.py):

- `throttled`: CFS throttled the sample's cgroup, an ancestor or the session (1 period or more)
- `foreign_busy`: the pinned CPUs were busy beyond the sample's own CPU time by more than 3% of their capacity (and 2 clock ticks per sqrt(CPU))
- `steal`: a hypervisor took more than 0.1% of the pinned CPUs' capacity
- `clock_moved`: the pinned CPUs' clock moved by more than 5% during the sample
- `gate_waited`: the quiet-host gate needed more than one reading before the sample started
- `swap`: the host swapped 1 page or more during the sample
- `thermal`: the pinned CPUs were thermally throttled 1 time or more during the sample
- `memory_events`: the kernel reported a memory.high, memory.max or OOM event for the sample's cgroup

## Failures, cannot-run and egress

### Failed samples (every attempt is in the raw data; none is dropped)

None.

### Cannot run (never counted as a loss, win or tie)

| arm | workload | api | reason |
|---|---|---|---|
| claude-code | overhead/print | chat | it does not speak openai-completions |
| claude-code | overhead/print | responses | it does not speak openai-responses |
| claude-code | overhead/print-tools | chat | it does not speak openai-completions |
| claude-code | overhead/print-tools | responses | it does not speak openai-responses |
| claude-code | overhead/rpc | anthropic | no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC |
| claude-code | overhead/rpc | chat | no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC |
| claude-code | overhead/rpc | responses | no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC |
| claude-code-b | overhead/print | chat | it does not speak openai-completions |
| claude-code-b | overhead/print | responses | it does not speak openai-responses |
| claude-code-b | overhead/print-tools | chat | it does not speak openai-completions |
| claude-code-b | overhead/print-tools | responses | it does not speak openai-responses |
| claude-code-b | overhead/rpc | anthropic | no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC |
| claude-code-b | overhead/rpc | chat | no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC |
| claude-code-b | overhead/rpc | responses | no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC |
| codex | overhead/print | anthropic | it does not speak anthropic-messages |
| codex | overhead/print | chat | it does not speak openai-completions |
| codex | overhead/print-tools | anthropic | it does not speak anthropic-messages |
| codex | overhead/print-tools | chat | it does not speak openai-completions |
| codex | overhead/rpc | anthropic | no Pi-dialect RPC mode |
| codex | overhead/rpc | chat | no Pi-dialect RPC mode |
| codex | overhead/rpc | responses | no Pi-dialect RPC mode |
| codex-b | overhead/print | anthropic | it does not speak anthropic-messages |
| codex-b | overhead/print | chat | it does not speak openai-completions |
| codex-b | overhead/print-tools | anthropic | it does not speak anthropic-messages |
| codex-b | overhead/print-tools | chat | it does not speak openai-completions |
| codex-b | overhead/rpc | anthropic | no Pi-dialect RPC mode |
| codex-b | overhead/rpc | chat | no Pi-dialect RPC mode |
| codex-b | overhead/rpc | responses | no Pi-dialect RPC mode |
| copilot | overhead/rpc | anthropic | no Pi-dialect RPC mode: `--acp` and `--output-format json` are Copilot's own protocols, not Pi's JSONL RPC |
| copilot | overhead/rpc | chat | no Pi-dialect RPC mode: `--acp` and `--output-format json` are Copilot's own protocols, not Pi's JSONL RPC |
| copilot | overhead/rpc | responses | no Pi-dialect RPC mode: `--acp` and `--output-format json` are Copilot's own protocols, not Pi's JSONL RPC |
| copilot-b | overhead/rpc | anthropic | no Pi-dialect RPC mode: `--acp` and `--output-format json` are Copilot's own protocols, not Pi's JSONL RPC |
| copilot-b | overhead/rpc | chat | no Pi-dialect RPC mode: `--acp` and `--output-format json` are Copilot's own protocols, not Pi's JSONL RPC |
| copilot-b | overhead/rpc | responses | no Pi-dialect RPC mode: `--acp` and `--output-format json` are Copilot's own protocols, not Pi's JSONL RPC |
| octet | overhead/print | anthropic | it does not speak anthropic-messages |
| octet | overhead/print | responses | it does not speak openai-responses |
| octet | overhead/print-tools | anthropic | it does not speak anthropic-messages |
| octet | overhead/print-tools | responses | it does not speak openai-responses |
| octet | overhead/rpc | anthropic | it does not speak anthropic-messages |
| octet | overhead/rpc | responses | it does not speak openai-responses |
| octet-b | overhead/print | anthropic | it does not speak anthropic-messages |
| octet-b | overhead/print | responses | it does not speak openai-responses |
| octet-b | overhead/print-tools | anthropic | it does not speak anthropic-messages |
| octet-b | overhead/print-tools | responses | it does not speak openai-responses |
| octet-b | overhead/rpc | anthropic | it does not speak anthropic-messages |
| octet-b | overhead/rpc | responses | it does not speak openai-responses |
| opencode-v2 | overhead/print | anthropic | it does not speak anthropic-messages |
| opencode-v2 | overhead/print | responses | it does not speak openai-responses |
| opencode-v2 | overhead/print-tools | anthropic | it does not speak anthropic-messages |
| opencode-v2 | overhead/print-tools | responses | it does not speak openai-responses |
| opencode-v2 | overhead/rpc | anthropic | no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL RPC |
| opencode-v2 | overhead/rpc | chat | no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL RPC |
| opencode-v2 | overhead/rpc | responses | no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL RPC |
| opencode-v2-b | overhead/print | anthropic | it does not speak anthropic-messages |
| opencode-v2-b | overhead/print | responses | it does not speak openai-responses |
| opencode-v2-b | overhead/print-tools | anthropic | it does not speak anthropic-messages |
| opencode-v2-b | overhead/print-tools | responses | it does not speak openai-responses |
| opencode-v2-b | overhead/rpc | anthropic | no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL RPC |
| opencode-v2-b | overhead/rpc | chat | no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL RPC |
| opencode-v2-b | overhead/rpc | responses | no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL RPC |

### Egress

Method: socket-audit. Any connection to a non-loopback address fails the sample and the run.
No harness connected outside the loopback.

## Not measured

Projects that resemble Pi implementations and were left out, with the reason:

| project | reason |
|---|---|
| chinudotdev/pi-go | a Go library for building agents, not a runnable coding agent: there is no command to start, so there is nothing to put through a workload |
| qiz029/pi-agent-go | a Go SDK (client) for Pi's RPC protocol: it drives a Pi process, it is not an implementation of Pi; measuring it would measure Pi |
| rcarmo/go-ai | an inference API library (the model layer under rcarmo/gi), not a coding agent |

## Provenance

Pins of the arms exactly as the run recorded them (arms.lock sha256 `549a3d2cc424cd316c5ff3072cf5c0c42bb1d6335775fd7289dd560254e35c33`). A third party who checks out the runner commit gets the same pins, and `buffon rerun` repeats a cell with them.

| arm | exact version | source | checksums | build | manifest sha256 | executable sha256 |
|---|---|---|---|---|---|---|
| claude-code | 2.1.296 | @anthropic-ai/claude-code@2.1.296 | integrity `sha512-OX/k/rpcthMqnFKOWcpNcbiLsMKtAjLOpQNJHlYiDCFUznWCIwdRTyl/p9SdHVrsrzZuPMCNqZjnpakIni6upw==`<br>package_lock_sha256 `8024fbbdc141e946abcfb87d71d873f3ac021cbee3b8080df5cdbe7a16622712` | node 24.19.0; linux-x64 | `7af7a5bd60f05a16c83f35d7a403f88723334bdaf99b4d8b2a431dc7fafea28a` | `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de` |
| codex | 0.162.1 | @openai/codex@0.162.1 | integrity `sha512-NWZdi/kxyjv/8EUGFupziGU38YyleugZRM4JXgY5XFH7FUmaFA33NZS2Bmq0HPazf7S3jJQQWsZ/jAK9jsrV3Q==`<br>package_lock_sha256 `a17117b06362c74b63de80e9c4cb525cf8556b5ead9d0d0e250473061365902d` | node 24.19.0; linux-x64 | `8f6e750426be308d9e377ae0e01e0fbfc7835643f9b2b74878e759042f7b1b12` | `61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70` |
| copilot | 1.0.95 | @github/copilot@1.0.95 | integrity `sha512-TAYlgMwjTnHi04ZGRc6Z+41piGeUC6xuA8z7gWVc5qOTqJLi/B3vCVg9ttkwvxnahbTWjX8x0DORwrJMXOQxGg==`<br>package_lock_sha256 `719cc494d4518865e011f319d354b1dcd52250fe4b45124f2b0f781e0620b9f8` | node 24.19.0; linux-x64 | `fed4d99a3a7bb66c5a015567c61bb343f86acb6e19e88b3a83696eee9be9bb78` | `9cf62455c0fef57658c976b737f57ddc4b87c2f513a17864846f2d0e16a18a99` |
| octet | 0.9.4 | https://github.com/skaft-software/octet/releases/download/v0.9.4/octet-0.9.4-x86_64-unknown-linux-gnu.tar.gz | artifact_sha256 `966e75a5551f46627080a4619383dbb402b5a72280a88e658bf2ce36e1059048` | linux-x64 | `a5f57ec6b6af729ca12c9f0e5de5647edd101dcdc5786c1fccc8cf4ac206f699` | `64b98a264669190f883da988452d9820dc23bfc5ccb81ebade4abbdffe0ac293` |
| opencode-v2 | 2.0.29 | @opencode/cli@2.0.29 | integrity `sha512-1ZmbylUtiRvtN8YMLxBEN4u0tqhfKI0AQBPvgdCLYLbB8BS80e6cFnOhzHH6L663o4RVL5bMa/VleLh1hNX+NA==`<br>package_lock_sha256 `afe4ef2f6eb18cd9e783a08b35e86e28a4a3fbd19ee931cf23375ad53b6a4843` | node 24.19.0; linux-x64 | `9d1a1af05b40bf19f6b7035e723b3aea173284161d189d1a6cd9a3fc5ba939cd` | `7e23471f4ebe2313d78baacc9ac96fe9e197ce26d808de4b0fcc37efbe473dad` |
| pi-bun | 1.3.0 | https://github.com/earendil-works/pi/releases/download/v1.3.0/pi-linux-x64.tar.gz | artifact_sha256 `24f5be328b66d4da36876296989501974f43ab8434fbb57c35c523a3ea505ded` | linux-x64 | `c88c8ca00f64b4f9ea566de62b8a6d8826ef41f96a733e592e84bbc300c7ac6a` | `c2415d6e6f7c67b0a55744c5ace5054936e252fcc3cf56ce087bc314061315ca` |
| pi-node | 1.3.0 | @earendil-works/pi-coding-agent@1.3.0 | integrity `sha512-V/WoCjA2hQSe3QLWIUB24cTRdtEdeLiIzkDqU5RMXV6VWuD+KGZnzVBMhglwdnQTySkehZsjt8a3g6Jd2g4nnw==`<br>package_lock_sha256 `65eacda789c30e1c3859a96eee2fd53cf4a18629d27dcf2aa6d7bdb3da02d719` | node 24.19.0; linux-x64 | `17662e8cd8bd784c3f3dd8a8b4e0864387babb4075d66aa52a60b3b02ba56457` | `e79626f2dd6f94aa45d30f3fa63cd84319a6eefcd150b353cfaf274366926774` |
| pibolt | 0.9.3 | https://github.com/opensec-git/Pi-Bolt/releases/download/bolt-v0.9.3/pi-bolt-linux-x64.tar.gz | artifact_sha256 `333f44ab2a1f602dbeb36228927bcafabd3e132da32be1d6a7deb54bd09e90ce` | linux-x64 | `db1434d8b8ede5b781e9b6cbb7f166bf33c5f8ec6592d3f11e8ebfd3b0047227` | `fe2572130b036a6981b2dcedf3e96e464dcd1749953c9bec47fc8353f0a66c1e` |
| pig-0.4.1 | 0.4.1 | https://github.com/MichaelKinsy/PiG/releases/download/v0.4.1/pig-0.4.1-linux-amd64.tar.gz | artifact_sha256 `3b4de3587cbfb617def483ec62dddcf35827acc3436b1454cc5694c22dcdaf3f` | linux-x64 | `a51378256ee5fdb0af8f190268b7b5e3f6c0d19da03d90b607eaa70efd58a161` | `110ab2ece63f0ac5a70b6bd8901ff0c740ab7172ecbeef33e94aa95e213c7179` |
| pig-tip | 0.5.0+1.3.0 | git 26eaad58e3ec09e25adf74000f79bcd83123aa8c | tree `8b867e1919867ebfc99e50c7a630f27f0ce9be30` | go build -buildvcs=false -trimpath -ldflags -s -w -X github.com/MichaelKinsy/PiG/coding/cli.Build=26eaad58e3ec09e25adf74000f79bcd83123aa8c -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateURL=https://github.com/MichaelKinsy/PiG/releases/latest/download/update.json -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateTrustRoot=LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUNvd0JRWURLMlZ3QXlFQVFBdUtJTHRmc0FpbWdabnRpZ2UydzRGRy9QeDFQeU5HampHYXlEalREM0k9Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQo= -X github.com/MichaelKinsy/PiG/coding/pigletbuild.releaseSourceVersion=v0.5.0 -o /local/kinsy/arena/home/work/buffon-gxdlew55/arms/pig-tip-a/bin/pig ./cmd/pig; toolchain go 1.27.2; linux-x64 | `d0032cdda0e713436aa3f6930bb5cac18491bdd91011ffa362100c5bd6b4526f` | `cc759dbd134406f976bb90fbb8fe5a0c3dc4d76a83b7de26d731daa6ef982b21` |
| rpi | 0.3.19 | https://github.com/bigfish1913/pi-rust/releases/download/v0.3.19/rpi-v0.3.19-x86_64-unknown-linux-gnu.tar.gz | artifact_sha256 `c48ef652be3093a28f06076e5a21f2746e155959a181aadd2d17dbdb819991bd` | linux-x64 | `2ed08713cf4168ead42831b40ce7dd9aceaac9c14aa3852edfb3d11f012a64ee` | `a79400a27228370f2995215e2a5e5c82efa6207b07a2002027d01a191206adb1` |

## Arms and environment

| arm | version | version line | executable sha256 | footprint | install | licence |
|---|---|---|---|---|---|---|
| claude-code | 2.1.296 | 2.1.296 (Claude Code) | `24972e3bc859fab2` | 257.3 MB + node 199 MB | npm ci --ignore-scripts (@anthropic-ai/claude-code) | proprietary (Anthropic legal agreements) |
| codex | 0.162.1 | codex-cli 0.162.1 | `61b0194f3bb65344` | 452.5 MB + node 199 MB | npm ci --ignore-scripts (@openai/codex) | Apache-2.0 |
| copilot | 1.0.95 | GitHub Copilot CLI 1.0.95. | `9cf62455c0fef576` | 183.8 MB + node 199 MB | npm ci --ignore-scripts (@github/copilot) | GitHub Copilot CLI License |
| octet | 0.9.4 | octet 0.9.4 | `64b98a264669190f` | 96.3 MB | release archive (https://github.com/skaft-software/octet/releases/download/v0) | MIT |
| opencode-v2 | 2.0.29 | opencode v2.0.29 | `7e23471f4ebe2313` | 845.0 MB + node 199 MB | npm ci --ignore-scripts (@opencode/cli) | MIT |
| pi-bun | 1.3.0 | 1.3.0 | `c2415d6e6f7c67b0` | 114.5 MB | release archive (https://github.com/earendil-works/pi/releases/download/v1.3.) | MIT |
| pi-node | 1.3.0 | 1.3.0 | `e79626f2dd6f94aa` | 110.6 MB + node 199 MB | npm ci --ignore-scripts (@earendil-works/pi-coding-agent) | MIT |
| pibolt | 0.9.3 | 1.3.0 (Pi-Bolt 0.9.3, linux-x64, JIT off) | `fe2572130b036a69` | 267.5 MB | release archive (https://github.com/opensec-git/Pi-Bolt/releases/download/bol) | MIT |
| pig-0.4.1 | 0.4.1 | 0.4.1+1.0.3 | `110ab2ece63f0ac5` | 63.8 MB | release archive (https://github.com/MichaelKinsy/PiG/releases/download/v0.4.1) | MIT |
| pig-tip | 0.5.0+1.3.0 | 0.5.0+1.3.0.1402973a | `cc759dbd134406f9` | 70.2 MB | source build (26eaad58e3ec09e25adf74000f79bcd83123aa8c) | MIT |
| rpi | 0.3.19 | rpi 0.3.19 | `a79400a27228370f` | 28.6 MB | release archive (https://github.com/bigfish1913/pi-rust/releases/download/v0.) | MIT |

**pig-tip:** This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

A/A copies run the same executable as their original (same sha256), installed as their own copy of the install tree.

Built from source at a pinned commit: `pig-tip`. A third party can rebuild such an arm only when its commit is public; the pinned commit of `pig-tip` is a merge on a private integration branch, so its result needs an independent reproduction before it is final (docs/DESIGN.md section 10).

### Run 1 facts

| field | value |
|---|---|
| cpu_model | Intel(R) Xeon(R) Platinum 8462Y+ |
| logical_cpus | 128 |
| pinned_cpus | 48-51,112-115 |
| mock_cpus | 52,116 |
| governors | {"48": "performance", "49": "performance", "50": "performance", "51": "performance", "112": "performance", "113": "performance", "114": "performance", "115": "performance"} |
| fixed_clock | true |
| smt_active | true |
| cpus_allowed | 32-63,96-127 |
| container | null |
| node | null |
| pod | null |
| kernel | 6.8.0-137-generic |
| memory_gib | 2015.5 |
| idle_before | {"48": 0.0, "49": 0.0, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0167, "114": 0.0, "115": 0.0} |
| idle_after | {"48": 0.0, "49": 0.0, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0, "114": 0.0, "115": 0.0} |
| load_before | [1.28125, 1.72607421875, 1.466796875] |
| load_after | [0.98681640625, 1.009765625, 1.13623046875] |
| throttled_usec | 0 |
| cpumon | {"samples": 1513, "pinned_busy_mean": 0.07753912132206553, "pinned_busy_max": 0.28942251623121495, "host_busy_mean": 0.008752875639689902} |
| go | null |
| node_js | null |
| python | 3.12.3 |

Variables each harness was started with beyond the host's environment (the throwaway root is `<work>`); credential-looking and proxy variables of the host are removed:

- **claude-code**: `ANTHROPIC_API_KEY=<dummy key>`, `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS=128000`, `CLAUDE_CONFIG_DIR=<work>/claude-code-a-version-anthropic/home/.claude`, `DISABLE_AUTOUPDATER=1`, `DISABLE_BUG_COMMAND=1`, `DISABLE_ERROR_REPORTING=1`, `DISABLE_TELEMETRY=1`, `HOME=<work>/claude-code-a-version-anthropic/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/claude-code-a-version-anthropic/disk/tmp`, `XDG_CACHE_HOME=<work>/claude-code-a-version-anthropic/disk/cache`, `XDG_CONFIG_HOME=<work>/claude-code-a-version-anthropic/home/.config`, `XDG_DATA_HOME=<work>/claude-code-a-version-anthropic/home/.local/share`, `XDG_STATE_HOME=<work>/claude-code-a-version-anthropic/home/.local/state`
- **claude-code-b**: `ANTHROPIC_API_KEY=<dummy key>`, `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS=128000`, `CLAUDE_CONFIG_DIR=<work>/claude-code-b-version-anthropic/home/.claude`, `DISABLE_AUTOUPDATER=1`, `DISABLE_BUG_COMMAND=1`, `DISABLE_ERROR_REPORTING=1`, `DISABLE_TELEMETRY=1`, `HOME=<work>/claude-code-b-version-anthropic/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/claude-code-b-version-anthropic/disk/tmp`, `XDG_CACHE_HOME=<work>/claude-code-b-version-anthropic/disk/cache`, `XDG_CONFIG_HOME=<work>/claude-code-b-version-anthropic/home/.config`, `XDG_DATA_HOME=<work>/claude-code-b-version-anthropic/home/.local/share`, `XDG_STATE_HOME=<work>/claude-code-b-version-anthropic/home/.local/state`
- **codex**: `BENCH_API_KEY=<dummy key>`, `CODEX_HOME=<work>/codex-a-version-openai/home/.codex`, `HOME=<work>/codex-a-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/codex-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/codex-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/codex-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/codex-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/codex-a-version-openai/home/.local/state`
- **codex-b**: `BENCH_API_KEY=<dummy key>`, `CODEX_HOME=<work>/codex-b-version-openai/home/.codex`, `HOME=<work>/codex-b-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/codex-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/codex-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/codex-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/codex-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/codex-b-version-openai/home/.local/state`
- **copilot**: `COPILOT_AUTO_UPDATE=false`, `COPILOT_HOME=<work>/copilot-a-version-openai/home/.copilot`, `COPILOT_MODEL=bench-1`, `COPILOT_OFFLINE=true`, `COPILOT_PROVIDER_API_KEY=<dummy key>`, `COPILOT_PROVIDER_BASE_URL=http://127.0.0.1:<port>/v1`, `COPILOT_PROVIDER_MAX_OUTPUT_TOKENS=8192`, `COPILOT_PROVIDER_MAX_PROMPT_TOKENS=128000`, `COPILOT_PROVIDER_TYPE=openai`, `COPILOT_PROVIDER_WIRE_API=completions`, `HOME=<work>/copilot-a-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/copilot-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/copilot-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/copilot-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/copilot-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/copilot-a-version-openai/home/.local/state`
- **copilot-b**: `COPILOT_AUTO_UPDATE=false`, `COPILOT_HOME=<work>/copilot-b-version-openai/home/.copilot`, `COPILOT_MODEL=bench-1`, `COPILOT_OFFLINE=true`, `COPILOT_PROVIDER_API_KEY=<dummy key>`, `COPILOT_PROVIDER_BASE_URL=http://127.0.0.1:<port>/v1`, `COPILOT_PROVIDER_MAX_OUTPUT_TOKENS=8192`, `COPILOT_PROVIDER_MAX_PROMPT_TOKENS=128000`, `COPILOT_PROVIDER_TYPE=openai`, `COPILOT_PROVIDER_WIRE_API=completions`, `HOME=<work>/copilot-b-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/copilot-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/copilot-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/copilot-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/copilot-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/copilot-b-version-openai/home/.local/state`
- **octet**: `HOME=<work>/octet-a-version-openai/home`, `OCTET_OFFLINE=true`, `PATH=/usr/bin:/bin`, `TMPDIR=<work>/octet-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/octet-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/octet-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/octet-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/octet-a-version-openai/home/.local/state`
- **octet-b**: `HOME=<work>/octet-b-version-openai/home`, `OCTET_OFFLINE=true`, `PATH=/usr/bin:/bin`, `TMPDIR=<work>/octet-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/octet-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/octet-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/octet-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/octet-b-version-openai/home/.local/state`
- **opencode-v2**: `BENCH_API_KEY=<dummy key>`, `HOME=<work>/opencode-v2-a-version-openai/home`, `OPENCODE_DISABLE_AUTOUPDATE=true`, `OPENCODE_DISABLE_MODELS_FETCH=true`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/opencode-v2-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/opencode-v2-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/opencode-v2-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/opencode-v2-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/opencode-v2-a-version-openai/home/.local/state`
- **opencode-v2-b**: `BENCH_API_KEY=<dummy key>`, `HOME=<work>/opencode-v2-b-version-openai/home`, `OPENCODE_DISABLE_AUTOUPDATE=true`, `OPENCODE_DISABLE_MODELS_FETCH=true`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/opencode-v2-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/opencode-v2-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/opencode-v2-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/opencode-v2-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/opencode-v2-b-version-openai/home/.local/state`
- **pi-bun**: `HOME=<work>/pi-bun-a-version-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-a-version-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-a-version-openai/home/.local/state`
- **pi-bun-b**: `HOME=<work>/pi-bun-b-version-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-b-version-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-b-version-openai/home/.local/state`
- **pi-node**: `HOME=<work>/pi-node-a-version-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-gxdlew55/arms/pi-node-a/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-a-version-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-a-version-openai/home/.local/state`
- **pi-node-b**: `HOME=<work>/pi-node-b-version-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-gxdlew55/arms/pi-node-b/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-b-version-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-b-version-openai/home/.local/state`
- **pibolt**: `HOME=<work>/pibolt-a-version-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-a-version-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-a-version-openai/home/.local/state`
- **pibolt-b**: `HOME=<work>/pibolt-b-version-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-b-version-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-b-version-openai/home/.local/state`
- **pig-0.4.1**: `HOME=<work>/pig-0.4.1-a-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-a-version-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-a-version-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-a-version-openai/home/.local/state`
- **pig-0.4.1-b**: `HOME=<work>/pig-0.4.1-b-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-b-version-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-b-version-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-b-version-openai/home/.local/state`
- **pig-tip**: `HOME=<work>/pig-tip-a-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-a-version-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-a-version-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-a-version-openai/home/.local/state`
- **pig-tip-b**: `HOME=<work>/pig-tip-b-version-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-gxdlew55/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-b-version-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-b-version-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-b-version-openai/home/.local/state`
- **rpi**: `HOME=<work>/rpi-a-version-openai/home`, `PATH=/usr/bin:/bin`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `RPI_CODING_AGENT_DIR=<work>/rpi-a-version-openai/home/.agent`, `RPI_DISABLE_UPDATE_CHECK=1`, `TMPDIR=<work>/rpi-a-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/rpi-a-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/rpi-a-version-openai/home/.config`, `XDG_DATA_HOME=<work>/rpi-a-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/rpi-a-version-openai/home/.local/state`
- **rpi-b**: `HOME=<work>/rpi-b-version-openai/home`, `PATH=/usr/bin:/bin`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `RPI_CODING_AGENT_DIR=<work>/rpi-b-version-openai/home/.agent`, `RPI_DISABLE_UPDATE_CHECK=1`, `TMPDIR=<work>/rpi-b-version-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/rpi-b-version-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/rpi-b-version-openai/home/.config`, `XDG_DATA_HOME=<work>/rpi-b-version-openai/home/.local/share`, `XDG_STATE_HOME=<work>/rpi-b-version-openai/home/.local/state`

### Runtime settings

Buffon pins CPUs but sets no runtime tuning of its own. An arm runs at its harness's shipped default except for the variables its manifest sets:

| arm | set by the manifest | left at the harness default |
|---|---|---|
| claude-code | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| codex | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| copilot | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| octet | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| opencode-v2 | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pi-bun | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pi-node | `NODE_COMPILE_CACHE={install_dir}/node-compile-cache` | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pibolt | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pig-0.4.1 | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pig-tip | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| rpi | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |

### Declared divergences

Where an arm does different work by its own account, its median is shown and not compared (no ratio, no grade):

| arm | workloads | metrics | reason | source |
|---|---|---|---|---|
| pibolt | `streaming/tui-*` | all | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | https://github.com/opensec-git/Pi-Bolt/blob/bolt-v0.9.3/packages/tui/src/tui-alt-screen.ts |

---
*Quiet dedicated hardware: generated from 1 run directory by `buffon report`; 3 notes: aa_significant_fraction 18.0%, aa_gap_max 19.8%, aa_floor_max 96.4%; the raw samples are in each directory's raw.json. The same data as report.html, report.json, summary.csv, rounds.csv, noise.csv and telemetry.csv.*
