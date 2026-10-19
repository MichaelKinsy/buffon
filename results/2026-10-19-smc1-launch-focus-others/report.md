# buffon report

**Trust: Dedicated** (host class A). adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (7-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 7 measured rounds in the thinnest cell (the minimum for a headline is 12); uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare) Every measurement is recorded and shown whatever the label. Headline CPU metric: instructions.

**Run notes (4)**: aa_significant_fraction 5.4%, aa_gap_max 25.1%, aa_floor_max 700.4%, outlier_fraction 2.6% (usual ranges: docs/HEALTH.md)

> Every run in this report was on quiet dedicated hardware by the runner's own detection (docs/RUNNING.md, "Hardware label").

| field | value |
|---|---|
| reference arm | pi-node |
| arms | claude-code, codex, copilot, octet, opencode-v2, pi-node, rpi (each with an A/A copy `<id>-b` where the run had one) |
| runs | 1 |
| seed | 20261011 |
| token counts | the mock's usage: prompt tokens = request wire bytes / 4, completion tokens = one per streamed part + 12 per tool call; no tokenizer is pinned (METHODOLOGY section 3) |
| arms.lock sha256 | `2c7b43d74cd7172acf7e967b44b949816327052605f2926b0cd28beba91fc878` |
| runner commit / tree | `c7fa2263480a` / `50b11e73f725` |
| run 1 | site `smc1-socket1` (local), 12 measured + 1 warm-up rounds, harness CPUs `48,49,50,51,112,113,114,115`, mock CPUs `52,116`, Intel(R) Xeon(R) Platinum 8462Y+, kernel 6.8.0-137-generic, meter cgroup-systemd; load before/after 1.0 / 1.3; calibration: CV 1.4% of cpu_ms (gate 5.0%) passed; hardware **quiet-dedicated**; host class **A**; isolation **uncontained, not comparable** |
| run 1 CPU cost | **instructions** (user and kernel instructions) are the headline CPU metric; CPU time (user + system) and wall time are separate cells |

## Run notes

4 notes: aa_significant_fraction 5.4%, aa_gap_max 25.1%, aa_floor_max 700.4%, outlier_fraction 2.6%. Run notes describe the conditions of the run. They do not grade it or change a number.

| check | value | usual range | status | meaning |
|---|---:|---:|---|---|
| A/A pairs with a significant gap (paired p < 0.05, before Holm) that is also larger than 1% | 5.4% | up to 5.0% | note | Share of harness and copy pairs that differ by more than 1% and also pass a significance test. A gap under 1% on a steady counter is not counted. About 5% can happen by chance. overhead/print-write anthropic kb200_peak_mem_mib rpi: 25.1%; overhead/print-write anthropic kb200_peak_rss_mib rpi: 22.4%; overhead/print-write chat kb50_after_stream_ms opencode-v2: 16.2% |
| A/A gap between a harness and its own copy, largest cell | 25.1% | up to 5.0% | note | The largest gap between a harness and its identical copy, and the cell where it happened. overhead/print-write anthropic kb200_peak_mem_mib rpi: 25.1%; overhead/print-write anthropic kb200_peak_rss_mib rpi: 22.4%; overhead/print-write chat kb50_after_stream_ms opencode-v2: 16.2% |
| A/A noise floor, worst scored cell | 700.4% | up to 15.0% | note | The same floor in the noisiest cell. Comparisons in that cell resolve only larger differences. streaming/print-prose anthropic n10_peak_rss_mib: 700.4%; overhead/print-write anthropic kb200_peak_mem_mib: 38.9%; overhead/print-write chat kb50_after_stream_ms: 37.8% |
| Measured values flagged by the MAD rule | 2.6% | up to 2.0% | note | Share of measured values far from the median of their cell. Outliers are counted and never removed. overhead/print-write chat kb50_cpu_ms pi-node-b: 3; overhead/print-write chat kb50_cycles pi-node-b: 3; overhead/print-write chat kb50_wall_ms pi-node-b: 3 |
| Calibration: CV of the reference's CPU time between identical runs | 1.4% | up to 2.0% | ok | How much the reference's CPU time varied between identical calibration runs. Lower means a quieter host. |
| A/A CV of CPU metrics, median over arms and cells | n/a | up to 2.0% | ok | How much CPU time varies from round to round for one harness. Lower means a quieter host. |
| A/A gap between a harness and its own copy, median over cells | 0.4% | up to 1.0% | ok | The usual gap between a harness and its identical copy. A real difference between two harnesses should be larger than this. |
| A/A noise floor, median over scored cells | 1.8% | up to 3.0% | ok | The smallest difference the identical copies cannot tell from noise, in the usual cell. Smaller differences than this are not resolved. |
| Measured samples with at least one host flag | 2.3% | up to 5.0% | ok | Share of samples where the host showed a disturbance: throttling, foreign CPU, steal, a clock change, swap or a memory event. |
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

**Trust: Dedicated** (host class A). adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (7-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 7 measured rounds in the thinnest cell (the minimum for a headline is 12); uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare)

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 4.

### Pi-faithful entries (faithfulness 90 or more)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

### Faithfulness not measured (ranked apart until it is)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | rpi (rpi (Rust port of Pi)) | **97 (A)** | not measured | 1/9 (8 not run) | release archive; 28.6 MB; linux-x64 | 97-97 | 97-99, rank 1-1 |
| 2 | copilot (GitHub Copilot CLI) | **51 (F)** | not measured | 1/9 (8 not run) | npm ci --ignore-scripts; 183.8 MB + node 199 MB; linux-x64 | 50-51 | 51-52, rank 2-2 |

### No overall score

| entry | coverage | why there is no overall score | faithfulness |
|---|---|---|---|
| claude-code (Claude Code) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak openai-completions; it does not speak open | not measured |
| codex (Codex CLI) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak open | not measured |
| octet (Octet) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak open | not measured |
| opencode-v2 (OpenCode 2) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak open | not measured |

### Below the reference

- **copilot**: streaming 51 (F) at 3.80x the reference's cost

*Quiet dedicated hardware: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*


## Summary by axis

Counts of cells where the arm is measurably worse (loss), inconclusive, inside the A/A floor (no measurable difference) or measurably better (win) than the reference `pi-node`. A "cannot run" cell is never counted. Coverage is the cells the arm produced values for out of all cells in the report.

| arm | coverage | family | losses | inconclusive | no measurable difference | wins |
|---|---|---|---:|---:|---:|---:|
| claude-code | 32/96 | overhead | 2 | 0 | 1 | 16 |
| claude-code | 32/96 | streaming | 7 | 0 | 3 | 1 |
| codex | 32/96 | overhead | 2 | 0 | 1 | 16 |
| codex | 32/96 | streaming | 4 | 0 | 1 | 6 |
| copilot | 96/96 | overhead | 21 | 0 | 3 | 33 |
| copilot | 96/96 | streaming | 30 | 0 | 3 | 0 |
| octet | 32/96 | overhead | 2 | 0 | 1 | 16 |
| octet | 32/96 | streaming | 2 | 0 | 1 | 8 |
| opencode-v2 | 32/96 | overhead | 5 | 0 | 0 | 14 |
| opencode-v2 | 32/96 | streaming | 11 | 0 | 0 | 0 |
| rpi | 96/96 | overhead | 6 | 0 | 3 | 48 |
| rpi | 96/96 | streaming | 6 | 0 | 4 | 23 |

## claude-code against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | anthropic | request_bytes | wire | bytes | 7 | 12,182 | 126,212 | 10.4 [10.4, 10.4] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes` |
| streaming/print-prose | anthropic | request_bytes_per_turn | wire | bytes per turn | 7 | 6,091 | 63,106 | 10.4 [10.4, 10.4] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes_per_turn` |
| streaming/print-prose | anthropic | n10_wall_ms | wall | ms | 7 | 55.2 | 125 | 2.27 [2.19, 2.39] | 6.0% | 3.1% | 3.3% / 2.2% | 1.92 / 4.13 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_wall_ms` |
| streaming/print-prose | anthropic | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 8.21 | 17.9 | 2.19 [2.1, 2.28] | 6.7% | 4.3% | 3.3% / 2.7% | 0.38 / 0.603 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | anthropic | n10_peak_rss_mib | memory | MiB | 7 | 135 | 268 | 1.98 [1.97, 2.03] | 2.7% | 1.2% | 0.3% / 2.4% | 0.395 / 5.02 | 2 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_peak_rss_mib` |
| streaming/print-prose | anthropic | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 42.64M | 82.09M | 1.93 [1.91, 1.96] | 2.1% | 0.2% | 0.3% / 1.6% | 121,396 / 1,479,575 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_instructions_per_1k_tokens` |
| overhead/print-write | anthropic | request_bytes | wire | bytes | 7 | 283,842 | 512,170 | 1.8 [1.8, 1.8] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes` |
| overhead/print-write | anthropic | request_bytes_per_turn | wire | bytes per turn | 7 | 70,960 | 128,042 | 1.8 [1.8, 1.8] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes_per_turn` |
| streaming/print-prose | anthropic | n_peak_rss_mib | memory | MiB | 7 | 132 | 223 | 1.69 [1.68, 1.71] | 3.8% | 3.1% | 1.8% / 0.7% | 1.83 / 2.32 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_peak_rss_mib` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | anthropic | requests | wire | count | 7 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#requests` |
| streaming/print-prose | anthropic | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 49.3 | 52.2 | 1.06 [1.04, 1.11] | 6.7% | 2.6% | 1.7% / 2.6% | 0.936 / 1.34 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | anthropic | n_wall_ms | wall | ms | 7 | 52.5 | 48.9 | 0.931 [0.918, 0.975] | 9.8% | 3.0% | 0.8% / 3.6% | 0.519 / 1.39 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_wall_ms` |
| streaming/print-prose | anthropic | requests | wire | count | 7 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | anthropic | kb200_after_stream_ms | wall | ms | 7 | 33,878 | 220 | 0.00649 [0.00629, 0.00674] | 29.5% | 1.8% | 0.3% / 13.6% | 85.7 / 12.3 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_after_stream_ms` |
| overhead/print-write | anthropic | kb200_call_to_result_ms | wall | ms | 7 | 33,998 | 340 | 0.00999 [0.00976, 0.0103] | 15.5% | 1.8% | 0.3% / 9.1% | 88.4 / 9.27 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_call_to_result_ms` |
| overhead/print-write | anthropic | kb200_cpu_ms | CPU | ms of CPU time | 7 | 35,374 | 1,095 | 0.031 [0.0303, 0.0314] | 8.2% | 1.8% | 0.4% / 6.7% | 175 / 28.4 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cpu_ms` |
| overhead/print-write | anthropic | kb200_cycles | CPU | cycles | 7 | 98748.31M | 2951.91M | 0.0299 [0.0293, 0.0304] | 9.4% | 1.8% | 0.4% / 6.8% | 478,565,006 / 70,784,960 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cycles` |
| overhead/print-write | anthropic | kb200_instructions | CPU | instructions | 7 | 401877.56M | 4872.63M | 0.0121 [0.0121, 0.0122] | 1.5% | 0.1% | 0.1% / 0.6% | 216,546,105 / 42,394,930 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_instructions` |
| overhead/print-write | anthropic | kb200_peak_mem_mib | memory | MiB | 7 | 536 | 187 | 0.349 [0.341, 0.353] | 3.2% | 2.4% | 1.3% / 1.2% | 7.19 / 3.4 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_mem_mib` |
| overhead/print-write | anthropic | kb200_peak_rss_mib | memory | MiB | 7 | 573 | 303 | 0.528 [0.522, 0.536] | 2.0% | 1.8% | 1.1% / 0.9% | 4.22 / 4.03 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_rss_mib` |
| overhead/print-write | anthropic | kb200_wall_ms | wall | ms | 7 | 34,341 | 667 | 0.0194 [0.019, 0.0196] | 8.2% | 1.8% | 0.3% / 6.1% | 87.5 / 15 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_wall_ms` |
| overhead/print-write | anthropic | kb50_after_stream_ms | wall | ms | 7 | 2,041 | 100 | 0.0491 [0.048, 0.0513] | 6.3% | 0.5% | 0.3% / 4.2% | 10.1 / 4.67 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_after_stream_ms` |
| overhead/print-write | anthropic | kb50_call_to_result_ms | wall | ms | 7 | 2,064 | 141 | 0.0684 [0.0669, 0.0699] | 4.4% | 0.4% | 0.3% / 1.9% | 9.9 / 4.72 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_call_to_result_ms` |
| overhead/print-write | anthropic | kb50_cpu_ms | CPU | ms of CPU time | 7 | 2,674 | 688 | 0.257 [0.256, 0.262] | 5.4% | 0.6% | 0.6% / 2.2% | 10.6 / 9.75 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cpu_ms` |
| overhead/print-write | anthropic | kb50_cycles | CPU | cycles | 7 | 7464.82M | 1837.45M | 0.246 [0.245, 0.25] | 4.9% | 0.6% | 0.6% / 2.3% | 28,348,612 / 25,732,475 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cycles` |
| overhead/print-write | anthropic | kb50_instructions | CPU | instructions | 7 | 27914.47M | 2862.14M | 0.103 [0.101, 0.103] | 1.9% | 0.1% | 0.1% / 1.1% | 19,488,914 / 29,071,185 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_instructions` |
| overhead/print-write | anthropic | kb50_peak_mem_mib | memory | MiB | 7 | 262 | 162 | 0.618 [0.611, 0.644] | 5.4% | 0.7% | 0.6% / 2.5% | 1 / 5.12 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_mem_mib` |
| overhead/print-write | anthropic | kb50_peak_rss_mib | memory | MiB | 7 | 310 | 277 | 0.894 [0.885, 0.908] | 2.6% | 0.5% | 0.4% / 1.3% | 0.625 / 4.99 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_rss_mib` |
| overhead/print-write | anthropic | kb50_wall_ms | wall | ms | 7 | 2,384 | 459 | 0.192 [0.19, 0.194] | 3.4% | 0.4% | 0.3% / 1.7% | 8.61 / 5.07 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_wall_ms` |
| streaming/print-prose | anthropic | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 261.15M | 182.49M | 0.699 [0.687, 0.719] | 2.0% | 1.4% | 1.0% / 1.4% | 2,972,842 / 4,536,055 | 2 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_instructions_per_1k_tokens` |

## codex against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | responses | request_bytes | wire | bytes | 7 | 12,002 | 79,036 | 6.59 [6.59, 6.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes` |
| streaming/print-prose | responses | request_bytes_per_turn | wire | bytes per turn | 7 | 6,001 | 39,518 | 6.59 [6.59, 6.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes_per_turn` |
| streaming/print-prose | responses | n_peak_rss_mib | memory | MiB | 7 | 137 | 193 | 1.41 [1.41, 1.43] | 1.7% | 1.3% | 0.7% / 0.2% | 0.932 / 0.611 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_peak_rss_mib` |
| streaming/print-prose | responses | n10_peak_rss_mib | memory | MiB | 7 | 140 | 197 | 1.41 [1.38, 1.44] | 2.7% | 1.2% | 0.7% / 1.6% | 1.23 / 3.53 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_peak_rss_mib` |
| overhead/print-write | responses | request_bytes | wire | bytes | 7 | 285,914 | 351,144 | 1.23 [1.23, 1.23] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes` |
| overhead/print-write | responses | request_bytes_per_turn | wire | bytes per turn | 7 | 71,478 | 87,786 | 1.23 [1.23, 1.23] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | responses | requests | wire | count | 7 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#requests` |
| streaming/print-prose | responses | requests | wire | count | 7 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | responses | kb200_after_stream_ms | wall | ms | 7 | 34,165 | 24.7 | 0.000724 [0.000685, 0.000739] | 5.3% | 2.8% | 2.5% / 1.5% | 1,663 / 0.505 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_after_stream_ms` |
| overhead/print-write | responses | kb200_call_to_result_ms | wall | ms | 7 | 34,275 | 189 | 0.00551 [0.00527, 0.00558] | 5.3% | 2.8% | 2.5% / 0.5% | 1,662 / 1.17 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_call_to_result_ms` |
| overhead/print-write | responses | kb200_cpu_ms | CPU | ms of CPU time | 7 | 35,639 | 488 | 0.0137 [0.0131, 0.0141] | 5.1% | 2.6% | 2.4% / 1.7% | 1,617 / 11.1 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cpu_ms` |
| overhead/print-write | responses | kb200_cycles | CPU | cycles | 7 | 99473.09M | 1223.08M | 0.0123 [0.0118, 0.0125] | 5.1% | 2.6% | 2.4% / 1.0% | 4,489,916,818 / 16,588,940 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cycles` |
| overhead/print-write | responses | kb200_instructions | CPU | instructions | 7 | 402617.50M | 1759.69M | 0.00437 [0.00432, 0.00438] | 1.5% | 0.1% | 0.1% / 0.7% | 524,601,626 / 13,713,748 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_instructions` |
| overhead/print-write | responses | kb200_peak_mem_mib | memory | MiB | 7 | 546 | 53.6 | 0.0981 [0.0974, 0.1] | 2.1% | 17.1% | 0.7% / 1.4% | 3.5 / 1.09 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_mem_mib` |
| overhead/print-write | responses | kb200_peak_rss_mib | memory | MiB | 7 | 581 | 201 | 0.346 [0.343, 0.348] | 1.9% | 15.8% | 0.7% / 0.4% | 3.63 / 0.971 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_rss_mib` |
| overhead/print-write | responses | kb200_wall_ms | wall | ms | 7 | 34,628 | 365 | 0.0105 [0.01, 0.0106] | 5.2% | 2.8% | 2.5% / 1.2% | 1,669 / 5.72 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_wall_ms` |
| overhead/print-write | responses | kb50_after_stream_ms | wall | ms | 7 | 2,067 | 16.0 | 0.00772 [0.00748, 0.00788] | 2.8% | 1.8% | 1.5% / 1.0% | 49.7 / 0.221 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_after_stream_ms` |
| overhead/print-write | responses | kb50_call_to_result_ms | wall | ms | 7 | 2,092 | 57.4 | 0.0274 [0.0265, 0.028] | 5.5% | 1.8% | 1.5% / 2.3% | 52.6 / 1.19 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_call_to_result_ms` |
| overhead/print-write | responses | kb50_cpu_ms | CPU | ms of CPU time | 7 | 2,748 | 310 | 0.113 [0.11, 0.114] | 3.7% | 2.1% | 1.3% / 0.9% | 52.2 / 4.76 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cpu_ms` |
| overhead/print-write | responses | kb50_cycles | CPU | cycles | 7 | 7675.93M | 777.50M | 0.101 [0.099, 0.103] | 3.7% | 2.1% | 1.3% / 1.0% | 144,046,084 / 11,918,310 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cycles` |
| overhead/print-write | responses | kb50_instructions | CPU | instructions | 7 | 28066.00M | 1064.74M | 0.0379 [0.0375, 0.038] | 2.6% | 0.1% | 0.1% / 1.1% | 47,389,679 / 9,011,134 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_instructions` |
| overhead/print-write | responses | kb50_peak_mem_mib | memory | MiB | 7 | 262 | 45.0 | 0.172 [0.169, 0.174] | 2.3% | 0.7% | 0.7% / 1.3% | 2.74 / 0.471 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_mem_mib` |
| overhead/print-write | responses | kb50_peak_rss_mib | memory | MiB | 7 | 310 | 192 | 0.621 [0.614, 0.625] | 1.3% | 0.5% | 0.6% / 0.4% | 2.48 / 1.13 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_rss_mib` |
| overhead/print-write | responses | kb50_wall_ms | wall | ms | 7 | 2,413 | 227 | 0.094 [0.0912, 0.0948] | 5.2% | 1.7% | 1.3% / 1.1% | 53.4 / 2.05 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_wall_ms` |
| streaming/print-prose | responses | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 10.3 | 8.99 | 0.873 [0.863, 0.915] | 12.5% | 3.6% | 2.4% / 5.2% | 0.0274 / 0.326 | 2 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 56.51M | 21.50M | 0.38 [0.37, 0.39] | 5.0% | 0.7% | 0.6% / 4.0% | 381,984 / 682,406 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_instructions_per_1k_tokens` |
| streaming/print-prose | responses | n10_wall_ms | wall | ms | 7 | 73.3 | 54.4 | 0.742 [0.697, 0.762] | 8.8% | 5.8% | 5.2% / 2.6% | 5.98 / 1.4 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_wall_ms` |
| streaming/print-prose | responses | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 57.3 | 30.0 | 0.523 [0.507, 0.547] | 14.0% | 3.1% | 1.8% / 2.4% | 1.33 / 0.794 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 292.81M | 58.26M | 0.199 [0.196, 0.205] | 12.4% | 0.4% | 0.2% / 3.2% | 589,683 / 1,770,496 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_instructions_per_1k_tokens` |
| streaming/print-prose | responses | n_wall_ms | wall | ms | 7 | 53.1 | 24.0 | 0.452 [0.437, 0.463] | 16.1% | 1.9% | 1.7% / 3.1% | 1.45 / 0.741 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_wall_ms` |

## copilot against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | anthropic | n10_wall_ms | wall | ms | 7 | 55.2 | 756 | 13.7 [13.3, 14.3] | 3.8% | 3.1% | 3.3% / 1.6% | 1.92 / 15.6 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_wall_ms` |
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.4 | 751 | 11.0 [10.7, 11.1] | 5.6% | 11.6% | 11.8% / 2.1% | 0.523 / 18.6 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | responses | n10_wall_ms | wall | ms | 7 | 73.3 | 753 | 10.3 [9.73, 10.8] | 8.8% | 5.8% | 5.2% / 1.9% | 5.98 / 16 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_wall_ms` |
| streaming/print-prose | anthropic | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 42.64M | 388.92M | 9.12 [9.07, 9.17] | 0.7% | 0.2% | 0.3% / 0.7% | 121,396 / 2,563,486 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_instructions_per_1k_tokens` |
| streaming/print-prose | anthropic | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 8.21 | 74.1 | 9.03 [8.83, 9.55] | 5.5% | 4.3% | 3.3% / 1.5% | 0.38 / 1.79 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | request_bytes | wire | bytes | 7 | 12,002 | 96,836 | 8.07 [8.07, 8.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes` |
| streaming/print-prose | responses | request_bytes_per_turn | wire | bytes per turn | 7 | 6,001 | 48,418 | 8.07 [8.07, 8.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes_per_turn` |
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 96,578 | 8 [8, 8] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 48,289 | 8 [8, 8] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| streaming/print-prose | anthropic | request_bytes | wire | bytes | 7 | 12,182 | 95,518 | 7.84 [7.84, 7.84] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes` |
| streaming/print-prose | anthropic | request_bytes_per_turn | wire | bytes per turn | 7 | 6,091 | 47,759 | 7.84 [7.84, 7.84] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes_per_turn` |
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.0 | 74.6 | 7.46 [7.27, 7.78] | 5.9% | 9.7% | 10.0% / 2.1% | 0.519 / 1.42 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 10.3 | 74.1 | 7.2 [7.15, 7.34] | 5.0% | 3.6% | 2.4% / 1.5% | 0.0274 / 1.3 | 2 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.25M | 384.18M | 7.08 [7.06, 7.09] | 0.8% | 0.2% | 0.2% / 0.4% | 79,739 / 1,293,610 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | responses | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 56.51M | 385.90M | 6.83 [6.8, 6.93] | 1.0% | 0.7% | 0.6% / 0.9% | 381,984 / 3,967,452 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_instructions_per_1k_tokens` |
| streaming/print-prose | anthropic | n10_peak_rss_mib | memory | MiB | 7 | 135 | 333 | 2.46 [2.44, 2.48] | 1.5% | 1.2% | 0.3% / 0.6% | 0.395 / 3.01 | 2 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_peak_rss_mib` |
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 136 | 333 | 2.45 [2.4, 2.48] | 1.5% | 1.2% | 1.1% / 0.9% | 2.24 / 3.46 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | responses | n10_peak_rss_mib | memory | MiB | 7 | 140 | 332 | 2.38 [2.37, 2.4] | 1.9% | 1.2% | 0.7% / 0.8% | 1.23 / 3.14 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_peak_rss_mib` |
| streaming/print-prose | anthropic | n_peak_rss_mib | memory | MiB | 7 | 132 | 305 | 2.32 [2.3, 2.35] | 3.8% | 3.1% | 1.8% / 0.5% | 1.83 / 1.96 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_peak_rss_mib` |
| streaming/print-prose | responses | n_peak_rss_mib | memory | MiB | 7 | 137 | 306 | 2.24 [2.23, 2.26] | 1.1% | 1.3% | 0.7% / 0.3% | 0.932 / 1.27 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_peak_rss_mib` |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 306 | 2.24 [2.21, 2.26] | 1.8% | 1.9% | 1.3% / 0.4% | 3.42 / 0.846 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | anthropic | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 49.3 | 97.3 | 1.97 [1.92, 2.22] | 13.8% | 2.6% | 1.7% / 7.4% | 0.936 / 7.87 | 0 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | anthropic | n_wall_ms | wall | ms | 7 | 52.5 | 93.9 | 1.79 [1.74, 1.89] | 7.9% | 3.0% | 0.8% / 3.1% | 0.519 / 4.04 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_wall_ms` |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.3 | 95.1 | 1.78 [1.7, 1.82] | 2.4% | 1.4% | 1.6% / 2.0% | 1.13 / 3.04 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_wall_ms` |
| streaming/print-prose | responses | n_wall_ms | wall | ms | 7 | 53.1 | 93.8 | 1.77 [1.69, 1.79] | 3.0% | 1.9% | 1.7% / 2.0% | 1.45 / 2.42 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_wall_ms` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.4 | 97.8 | 1.76 [1.7, 1.8] | 7.7% | 2.6% | 1.8% / 4.4% | 1.46 / 2.78 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 57.3 | 97.9 | 1.71 [1.66, 1.81] | 9.4% | 3.1% | 1.8% / 4.5% | 1.33 / 5.67 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_cpu_ms_per_1k_tokens` |
| overhead/print-write | responses | request_bytes | wire | bytes | 7 | 285,914 | 455,655 | 1.59 [1.59, 1.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes` |
| overhead/print-write | responses | request_bytes_per_turn | wire | bytes per turn | 7 | 71,478 | 113,914 | 1.59 [1.59, 1.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes_per_turn` |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 455,177 | 1.59 [1.59, 1.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 113,794 | 1.59 [1.59, 1.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes_per_turn` |
| overhead/print-write | responses | kb50_peak_mem_mib | memory | MiB | 7 | 262 | 417 | 1.59 [1.56, 1.6] | 1.0% | 0.7% | 0.7% / 1.0% | 2.74 / 3.55 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_mem_mib` |
| overhead/print-write | anthropic | request_bytes | wire | bytes | 7 | 283,842 | 450,495 | 1.59 [1.59, 1.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes` |
| overhead/print-write | anthropic | request_bytes_per_turn | wire | bytes per turn | 7 | 70,960 | 112,624 | 1.59 [1.59, 1.59] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes_per_turn` |
| overhead/print-write | anthropic | kb50_peak_mem_mib | memory | MiB | 7 | 262 | 412 | 1.57 [1.56, 1.58] | 1.5% | 0.7% | 0.6% / 0.7% | 1 / 4.02 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 410 | 1.57 [1.56, 1.59] | 1.7% | 0.7% | 0.3% / 0.8% | 1.16 / 4.43 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| streaming/print-prose | anthropic | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 261.15M | 370.23M | 1.42 [1.4, 1.58] | 12.8% | 1.4% | 1.0% / 6.8% | 2,972,842 / 27,343,195 | 2 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_instructions_per_1k_tokens` |
| overhead/print-write | anthropic | kb50_cpu_ms | CPU | ms of CPU time | 7 | 2,674 | 3,597 | 1.35 [1.31, 1.36] | 3.2% | 0.6% | 0.6% / 1.6% | 10.6 / 73.8 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,734 | 3,583 | 1.31 [1.27, 1.32] | 3.8% | 2.9% | 2.0% / 0.6% | 93.2 / 27.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cpu_ms` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.73M | 372.00M | 1.31 [1.3, 1.32] | 7.6% | 0.3% | 0.4% / 4.2% | 1,527,097 / 3,779,005 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| overhead/print-write | responses | kb50_cpu_ms | CPU | ms of CPU time | 7 | 2,748 | 3,580 | 1.3 [1.27, 1.32] | 3.0% | 2.1% | 1.3% / 1.1% | 52.2 / 35.9 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cpu_ms` |
| overhead/print-write | anthropic | kb50_cycles | CPU | cycles | 7 | 7464.82M | 9694.34M | 1.3 [1.26, 1.31] | 3.3% | 0.6% | 0.6% / 1.6% | 28,348,612 / 192,532,847 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cycles` |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7633.50M | 9682.42M | 1.27 [1.23, 1.27] | 3.8% | 3.0% | 2.0% / 0.6% | 261,498,112 / 64,539,540 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cycles` |
| streaming/print-prose | responses | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 292.81M | 370.78M | 1.27 [1.25, 1.37] | 8.9% | 0.4% | 0.2% / 5.1% | 589,683 / 19,923,122 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_instructions_per_1k_tokens` |
| overhead/print-write | responses | kb50_cycles | CPU | cycles | 7 | 7675.93M | 9669.21M | 1.26 [1.23, 1.27] | 3.0% | 2.1% | 1.3% / 1.1% | 144,046,084 / 86,631,124 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cycles` |
| overhead/print-write | responses | kb50_peak_rss_mib | memory | MiB | 7 | 310 | 353 | 1.14 [1.12, 1.14] | 0.8% | 0.5% | 0.6% / 1.2% | 2.48 / 2.56 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_rss_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 347 | 1.12 [1.12, 1.13] | 1.8% | 0.7% | 0.3% / 0.9% | 0.983 / 4.62 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | anthropic | kb50_peak_rss_mib | memory | MiB | 7 | 310 | 346 | 1.12 [1.11, 1.13] | 2.1% | 0.5% | 0.4% / 0.7% | 0.625 / 3.36 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_rss_mib` |
| overhead/print-write | anthropic | kb50_wall_ms | wall | ms | 7 | 2,384 | 2,622 | 1.1 [1.08, 1.11] | 2.4% | 0.4% | 0.3% / 1.3% | 8.61 / 41.8 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_wall_ms` |
| overhead/print-write | responses | kb50_wall_ms | wall | ms | 7 | 2,413 | 2,613 | 1.08 [1.06, 1.1] | 2.7% | 1.7% | 1.3% / 0.6% | 53.4 / 22.6 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_wall_ms` |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,429 | 2,594 | 1.07 [1.03, 1.08] | 4.4% | 3.6% | 2.2% / 0.7% | 105 / 18 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_wall_ms` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | anthropic | requests | wire | count | 7 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#requests` |
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#requests` |
| overhead/print-write | responses | requests | wire | count | 7 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#requests` |
| streaming/print-prose | anthropic | requests | wire | count | 7 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#requests` |
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#requests` |
| streaming/print-prose | responses | requests | wire | count | 7 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | anthropic | kb200_after_stream_ms | wall | ms | 7 | 33,878 | 6,137 | 0.181 [0.179, 0.186] | 4.5% | 1.8% | 0.3% / 2.5% | 85.7 / 131 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_after_stream_ms` |
| overhead/print-write | anthropic | kb200_call_to_result_ms | wall | ms | 7 | 33,998 | 6,255 | 0.184 [0.182, 0.189] | 4.7% | 1.8% | 0.3% / 2.5% | 88.4 / 135 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_call_to_result_ms` |
| overhead/print-write | anthropic | kb200_cpu_ms | CPU | ms of CPU time | 7 | 35,374 | 10,037 | 0.284 [0.279, 0.291] | 4.1% | 1.8% | 0.4% / 2.1% | 175 / 185 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cpu_ms` |
| overhead/print-write | anthropic | kb200_cycles | CPU | cycles | 7 | 98748.31M | 27019.72M | 0.274 [0.27, 0.28] | 3.9% | 1.8% | 0.4% / 2.0% | 478,565,006 / 511,494,486 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cycles` |
| overhead/print-write | anthropic | kb200_instructions | CPU | instructions | 7 | 401877.56M | 50235.72M | 0.125 [0.124, 0.125] | 0.5% | 0.1% | 0.1% / 0.4% | 216,546,105 / 297,842,532 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_instructions` |
| overhead/print-write | anthropic | kb200_peak_mem_mib | memory | MiB | 7 | 536 | 476 | 0.888 [0.877, 0.888] | 3.3% | 2.4% | 1.3% / 1.2% | 7.19 / 7.72 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_mem_mib` |
| overhead/print-write | anthropic | kb200_peak_rss_mib | memory | MiB | 7 | 573 | 408 | 0.712 [0.7, 0.719] | 3.4% | 1.8% | 1.1% / 1.6% | 4.22 / 8.32 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_rss_mib` |
| overhead/print-write | anthropic | kb200_wall_ms | wall | ms | 7 | 34,341 | 7,819 | 0.228 [0.225, 0.233] | 3.8% | 1.8% | 0.3% / 2.1% | 87.5 / 144 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_wall_ms` |
| overhead/print-write | anthropic | kb50_after_stream_ms | wall | ms | 7 | 2,041 | 1,051 | 0.515 [0.496, 0.523] | 6.5% | 0.5% | 0.3% / 2.4% | 10.1 / 30.2 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_after_stream_ms` |
| overhead/print-write | anthropic | kb50_call_to_result_ms | wall | ms | 7 | 2,064 | 1,079 | 0.523 [0.5, 0.527] | 6.3% | 0.4% | 0.3% / 2.7% | 9.9 / 33.2 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_call_to_result_ms` |
| overhead/print-write | anthropic | kb50_instructions | CPU | instructions | 7 | 27914.47M | 18065.69M | 0.647 [0.646, 0.65] | 1.6% | 0.1% | 0.1% / 0.5% | 19,488,914 / 91,290,475 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_instructions` |
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 34,051 | 6,334 | 0.186 [0.179, 0.188] | 4.7% | 0.3% | 0.4% / 3.4% | 142 / 134 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,183 | 6,477 | 0.189 [0.182, 0.191] | 4.5% | 0.3% | 0.4% / 3.4% | 139 / 142 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,591 | 10,414 | 0.293 [0.285, 0.298] | 3.2% | 0.4% | 0.4% / 2.3% | 169 / 188 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99344.82M | 28104.03M | 0.283 [0.276, 0.287] | 3.1% | 0.4% | 0.4% / 2.3% | 467,008,189 / 486,322,930 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402373.01M | 51289.77M | 0.127 [0.127, 0.128] | 0.5% | 0.1% | 0.1% / 0.3% | 360,657,708 / 207,149,222 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 544 | 480 | 0.884 [0.872, 0.894] | 3.2% | 1.2% | 1.0% / 1.8% | 7.06 / 11.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 413 | 0.715 [0.701, 0.728] | 4.7% | 1.5% | 1.1% / 2.2% | 10.5 / 15.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,550 | 8,054 | 0.233 [0.226, 0.235] | 3.5% | 0.3% | 0.4% / 2.7% | 154 / 131 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,062 | 1,007 | 0.488 [0.462, 0.498] | 4.9% | 4.0% | 2.6% / 1.9% | 100 / 22.1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,097 | 1,042 | 0.497 [0.472, 0.505] | 4.8% | 4.0% | 2.5% / 1.8% | 101 / 18.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28074.90M | 18101.36M | 0.645 [0.642, 0.648] | 0.8% | 0.1% | 0.1% / 0.4% | 41,791,714 / 126,501,248 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | responses | kb200_after_stream_ms | wall | ms | 7 | 34,165 | 6,176 | 0.181 [0.173, 0.186] | 6.7% | 2.8% | 2.5% / 1.3% | 1,663 / 94 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_after_stream_ms` |
| overhead/print-write | responses | kb200_call_to_result_ms | wall | ms | 7 | 34,275 | 6,299 | 0.184 [0.176, 0.189] | 6.3% | 2.8% | 2.5% / 1.3% | 1,662 / 83.9 | 0 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_call_to_result_ms` |
| overhead/print-write | responses | kb200_cpu_ms | CPU | ms of CPU time | 7 | 35,639 | 10,083 | 0.283 [0.269, 0.288] | 5.1% | 2.6% | 2.4% / 1.1% | 1,617 / 150 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cpu_ms` |
| overhead/print-write | responses | kb200_cycles | CPU | cycles | 7 | 99473.09M | 27191.24M | 0.273 [0.26, 0.278] | 5.1% | 2.6% | 2.4% / 1.0% | 4,489,916,818 / 380,034,854 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cycles` |
| overhead/print-write | responses | kb200_instructions | CPU | instructions | 7 | 402617.50M | 50389.90M | 0.125 [0.125, 0.126] | 0.5% | 0.1% | 0.1% / 0.2% | 524,601,626 / 185,440,220 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_instructions` |
| overhead/print-write | responses | kb200_peak_mem_mib | memory | MiB | 7 | 546 | 480 | 0.878 [0.863, 0.891] | 3.0% | 17.1% | 0.7% / 1.4% | 3.5 / 8.15 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_mem_mib` |
| overhead/print-write | responses | kb200_peak_rss_mib | memory | MiB | 7 | 581 | 415 | 0.715 [0.693, 0.719] | 3.4% | 15.8% | 0.7% / 1.5% | 3.63 / 8.67 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_rss_mib` |
| overhead/print-write | responses | kb200_wall_ms | wall | ms | 7 | 34,628 | 7,872 | 0.227 [0.218, 0.233] | 5.2% | 2.8% | 2.5% / 1.0% | 1,669 / 80.1 | 0 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_wall_ms` |
| overhead/print-write | responses | kb50_after_stream_ms | wall | ms | 7 | 2,067 | 1,041 | 0.504 [0.483, 0.514] | 6.0% | 1.8% | 1.5% / 1.5% | 49.7 / 23.9 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_after_stream_ms` |
| overhead/print-write | responses | kb50_call_to_result_ms | wall | ms | 7 | 2,092 | 1,064 | 0.508 [0.489, 0.521] | 6.3% | 1.8% | 1.5% / 1.5% | 52.6 / 24.2 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_call_to_result_ms` |
| overhead/print-write | responses | kb50_instructions | CPU | instructions | 7 | 28066.00M | 18178.05M | 0.648 [0.642, 0.649] | 1.0% | 0.1% | 0.1% / 0.6% | 47,389,679 / 118,142,146 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_instructions` |

## octet against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 15,824 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 7,912 | 1.31 [1.31, 1.31] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 293,503 | 1.03 [1.03, 1.03] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 73,376 | 1.03 [1.03, 1.03] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#requests` |
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 34,051 | 6.75 | 0.000198 [0.000197, 0.000201] | 2.7% | 0.3% | 0.4% / 1.2% | 142 / 0.127 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,183 | 190 | 0.00556 [0.00554, 0.00559] | 0.8% | 0.3% | 0.4% / 0.4% | 139 / 0.58 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,591 | 258 | 0.00725 [0.00722, 0.00731] | 0.7% | 0.4% | 0.4% / 0.5% | 169 / 1.22 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99344.82M | 647.99M | 0.00652 [0.00651, 0.0066] | 1.0% | 0.4% | 0.4% / 0.7% | 467,008,189 / 5,401,122 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402373.01M | 1128.42M | 0.0028 [0.00279, 0.00283] | 1.3% | 0.1% | 0.1% / 0.9% | 360,657,708 / 12,170,572 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 544 | 6.95 | 0.0128 [0.0127, 0.0133] | 2.7% | 1.2% | 1.0% / 2.0% | 7.06 / 0.207 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 29.4 | 0.0509 [0.0502, 0.0516] | 2.5% | 1.5% | 1.1% / 2.1% | 10.5 / 0.305 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,550 | 224 | 0.00649 [0.00645, 0.00653] | 1.2% | 0.3% | 0.4% / 0.9% | 154 / 1.86 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,062 | 3.37 | 0.00164 [0.00156, 0.00167] | 4.9% | 4.0% | 2.6% / 2.3% | 100 / 0.093 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,097 | 47.9 | 0.0228 [0.0219, 0.023] | 4.8% | 4.0% | 2.5% / 0.7% | 101 / 0.322 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,734 | 78.7 | 0.0288 [0.0279, 0.0294] | 3.8% | 2.9% | 2.0% / 1.4% | 93.2 / 1.55 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7633.50M | 199.68M | 0.0262 [0.0253, 0.0264] | 3.8% | 3.0% | 2.0% / 1.0% | 261,498,112 / 3,270,804 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28074.90M | 334.80M | 0.0119 [0.0118, 0.012] | 1.3% | 0.1% | 0.1% / 0.6% | 41,791,714 / 3,451,949 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 5.3 | 0.0203 [0.0194, 0.0212] | 7.9% | 0.7% | 0.3% / 4.4% | 1.16 / 0.43 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 28.8 | 0.0932 [0.0927, 0.103] | 9.0% | 0.7% | 0.3% / 6.0% | 0.983 / 1.23 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,429 | 65.9 | 0.0271 [0.026, 0.0291] | 8.6% | 3.6% | 2.2% / 4.8% | 105 / 4.86 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_wall_ms` |
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.0 | 3.72 | 0.371 [0.355, 0.389] | 6.8% | 9.7% | 10.0% / 2.8% | 0.519 / 0.126 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.25M | 14.95M | 0.276 [0.274, 0.281] | 3.3% | 0.2% | 0.2% / 1.1% | 79,739 / 198,034 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 136 | 28.7 | 0.212 [0.208, 0.214] | 1.5% | 1.2% | 1.1% / 0.8% | 2.24 / 0.341 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.4 | 38.4 | 0.561 [0.553, 0.564] | 5.0% | 11.6% | 11.8% / 0.7% | 0.523 / 0.288 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.4 | 7.03 | 0.127 [0.118, 0.133] | 10.3% | 2.6% | 1.8% / 5.3% | 1.46 / 0.535 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.73M | 23.19M | 0.0814 [0.08, 0.0833] | 3.7% | 0.3% | 0.4% / 1.9% | 1,527,097 / 620,585 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 4.2 | 0.0308 [0.0299, 0.0316] | 6.2% | 1.9% | 1.3% / 2.8% | 3.42 / 0.158 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.3 | 8.05 | 0.151 [0.147, 0.154] | 3.9% | 1.4% | 1.6% / 2.0% | 1.13 / 0.168 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_wall_ms` |

## opencode-v2 against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.0 | 48.2 | 4.82 [4.64, 4.96] | 6.6% | 9.7% | 10.0% / 3.0% | 0.519 / 1.19 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.4 | 228 | 4.11 [3.75, 4.29] | 12.4% | 2.6% | 1.8% / 6.9% | 1.46 / 15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 49,662 | 4.11 [4.11, 4.11] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 24,831 | 4.11 [4.11, 4.11] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.25M | 196.98M | 3.63 [3.54, 3.66] | 2.2% | 0.2% | 0.2% / 2.1% | 79,739 / 3,803,675 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.4 | 242 | 3.54 [3.44, 3.61] | 6.4% | 11.6% | 11.8% / 2.4% | 0.523 / 7.95 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 136 | 425 | 3.13 [3.08, 3.15] | 1.6% | 1.2% | 1.1% / 0.9% | 2.24 / 3.57 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 401 | 2.93 [2.87, 2.97] | 1.8% | 1.9% | 1.3% / 2.0% | 3.42 / 8.76 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.73M | 745.39M | 2.62 [2.57, 2.78] | 6.4% | 0.3% | 0.4% / 5.9% | 1,527,097 / 43,685,112 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.3 | 138 | 2.59 [2.21, 2.65] | 23.3% | 1.4% | 1.6% / 9.0% | 1.13 / 16.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_wall_ms` |
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 4 | 2 [2, 2] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#requests` |
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 6 | 1.5 [1.5, 1.5] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#requests` |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 418 | 1.35 [1.34, 1.37] | 4.1% | 0.7% | 0.3% / 1.4% | 0.983 / 7.68 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 356,349 | 1.25 [1.25, 1.25] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 89,087 | 1.25 [1.25, 1.25] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes_per_turn` |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 290 | 1.11 [1.09, 1.13] | 6.2% | 0.7% | 0.3% / 2.0% | 1.16 / 7.39 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_mem_mib` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 34,051 | 255 | 0.00748 [0.00722, 0.0083] | 37.2% | 0.3% | 0.4% / 8.7% | 142 / 30.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,183 | 408 | 0.0119 [0.0114, 0.0128] | 20.7% | 0.3% | 0.4% / 5.2% | 139 / 30.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,591 | 2,906 | 0.0817 [0.0806, 0.084] | 5.9% | 0.4% | 0.4% / 2.4% | 169 / 80.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99344.82M | 7971.35M | 0.0802 [0.0791, 0.0825] | 6.2% | 0.4% | 0.4% / 2.5% | 467,008,189 / 224,630,937 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402373.01M | 12388.20M | 0.0308 [0.0305, 0.0313] | 2.6% | 0.1% | 0.1% / 1.5% | 360,657,708 / 264,459,150 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 544 | 323 | 0.594 [0.589, 0.605] | 1.8% | 1.2% | 1.0% / 1.6% | 7.06 / 3.3 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 451 | 0.78 [0.768, 0.792] | 1.6% | 1.5% | 1.1% / 1.2% | 10.5 / 4.15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,550 | 1,227 | 0.0355 [0.0348, 0.0364] | 8.6% | 0.3% | 0.4% / 2.2% | 154 / 48.3 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,062 | 151 | 0.0731 [0.064, 0.0804] | 37.8% | 4.0% | 2.6% / 14.3% | 100 / 26.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,097 | 197 | 0.0939 [0.0828, 0.102] | 30.3% | 4.0% | 2.5% / 11.6% | 101 / 27.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,734 | 2,369 | 0.866 [0.81, 0.895] | 8.8% | 2.9% | 2.0% / 4.9% | 93.2 / 189 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7633.50M | 6499.84M | 0.851 [0.796, 0.878] | 8.9% | 3.0% | 2.0% / 4.8% | 261,498,112 / 511,416,674 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28074.90M | 9010.77M | 0.321 [0.314, 0.325] | 1.7% | 0.1% | 0.1% / 1.3% | 41,791,714 / 140,343,022 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,429 | 1,002 | 0.412 [0.389, 0.426] | 11.4% | 3.6% | 2.2% / 5.5% | 105 / 75.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_wall_ms` |

## rpi against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 15,358 | 1.27 [1.27, 1.27] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 7,679 | 1.27 [1.27, 1.27] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| streaming/print-prose | responses | request_bytes | wire | bytes | 7 | 12,002 | 15,020 | 1.25 [1.25, 1.25] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes` |
| streaming/print-prose | responses | request_bytes_per_turn | wire | bytes per turn | 7 | 6,001 | 7,510 | 1.25 [1.25, 1.25] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes_per_turn` |
| streaming/print-prose | anthropic | request_bytes | wire | bytes | 7 | 12,182 | 13,152 | 1.08 [1.08, 1.08] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes` |
| streaming/print-prose | anthropic | request_bytes_per_turn | wire | bytes per turn | 7 | 6,091 | 6,576 | 1.08 [1.08, 1.08] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes_per_turn` |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 292,670 | 1.02 [1.02, 1.02] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 73,168 | 1.02 [1.02, 1.02] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes_per_turn` |
| overhead/print-write | responses | request_bytes | wire | bytes | 7 | 285,914 | 291,934 | 1.02 [1.02, 1.02] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes` |
| overhead/print-write | responses | request_bytes_per_turn | wire | bytes per turn | 7 | 71,478 | 72,984 | 1.02 [1.02, 1.02] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes_per_turn` |
| overhead/print-write | anthropic | request_bytes | wire | bytes | 7 | 283,842 | 285,642 | 1.01 [1.01, 1.01] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes` |
| overhead/print-write | anthropic | request_bytes_per_turn | wire | bytes per turn | 7 | 70,960 | 71,410 | 1.01 [1.01, 1.01] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0469 | no exact |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | anthropic | requests | wire | count | 7 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#requests` |
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#requests` |
| overhead/print-write | responses | requests | wire | count | 7 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#requests` |
| streaming/print-prose | anthropic | n10_peak_rss_mib | memory | MiB | 7 | 135 | 33.5 | 0.248 [0.0304, 0.254] | 700.4% | 1.2% | 0.3% / 57.5% | 0.395 / 15.4 | 2 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_peak_rss_mib` |
| streaming/print-prose | anthropic | requests | wire | count | 7 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#requests` |
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#requests` |
| streaming/print-prose | responses | requests | wire | count | 7 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | anthropic | kb200_after_stream_ms | wall | ms | 7 | 33,878 | 8,865 | 0.262 [0.26, 0.264] | 1.3% | 1.8% | 0.3% / 0.5% | 85.7 / 71.9 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_after_stream_ms` |
| overhead/print-write | anthropic | kb200_call_to_result_ms | wall | ms | 7 | 33,998 | 8,991 | 0.264 [0.262, 0.266] | 1.2% | 1.8% | 0.3% / 0.5% | 88.4 / 68.8 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_call_to_result_ms` |
| overhead/print-write | anthropic | kb200_cpu_ms | CPU | ms of CPU time | 7 | 35,374 | 9,396 | 0.266 [0.263, 0.268] | 1.7% | 1.8% | 0.4% / 0.6% | 175 / 99.3 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cpu_ms` |
| overhead/print-write | anthropic | kb200_cycles | CPU | cycles | 7 | 98748.31M | 26015.74M | 0.263 [0.261, 0.266] | 1.6% | 1.8% | 0.4% / 0.6% | 478,565,006 / 256,343,180 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cycles` |
| overhead/print-write | anthropic | kb200_instructions | CPU | instructions | 7 | 401877.56M | 122116.65M | 0.304 [0.304, 0.304] | 0.1% | 0.1% | 0.1% / 0.0% | 216,546,105 / 29,788,938 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_instructions` |
| overhead/print-write | anthropic | kb200_peak_mem_mib | memory | MiB | 7 | 536 | 136 | 0.254 [0.251, 0.312] | 38.9% | 2.4% | 1.3% / 11.2% | 7.19 / 16.5 | 0 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_mem_mib` |
| overhead/print-write | anthropic | kb200_peak_rss_mib | memory | MiB | 7 | 573 | 147 | 0.256 [0.252, 0.316] | 34.6% | 1.8% | 1.1% / 11.2% | 4.22 / 19.1 | 1 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_rss_mib` |
| overhead/print-write | anthropic | kb200_wall_ms | wall | ms | 7 | 34,341 | 9,038 | 0.263 [0.261, 0.264] | 1.1% | 1.8% | 0.3% / 0.5% | 87.5 / 66.2 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_wall_ms` |
| overhead/print-write | anthropic | kb50_after_stream_ms | wall | ms | 7 | 2,041 | 583 | 0.285 [0.285, 0.287] | 0.7% | 0.5% | 0.3% / 0.7% | 10.1 / 0.678 | 0 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_after_stream_ms` |
| overhead/print-write | anthropic | kb50_call_to_result_ms | wall | ms | 7 | 2,064 | 615 | 0.298 [0.298, 0.299] | 0.7% | 0.4% | 0.3% / 0.8% | 9.9 / 1.6 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_call_to_result_ms` |
| overhead/print-write | anthropic | kb50_cpu_ms | CPU | ms of CPU time | 7 | 2,674 | 710 | 0.266 [0.264, 0.269] | 2.1% | 0.6% | 0.6% / 1.3% | 10.6 / 10.3 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cpu_ms` |
| overhead/print-write | anthropic | kb50_cycles | CPU | cycles | 7 | 7464.82M | 1919.84M | 0.257 [0.256, 0.26] | 2.1% | 0.6% | 0.6% / 1.3% | 28,348,612 / 23,060,563 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cycles` |
| overhead/print-write | anthropic | kb50_instructions | CPU | instructions | 7 | 27914.47M | 8324.88M | 0.298 [0.298, 0.299] | 0.1% | 0.1% | 0.1% / 0.1% | 19,488,914 / 4,688,884 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_instructions` |
| overhead/print-write | anthropic | kb50_peak_mem_mib | memory | MiB | 7 | 262 | 31.6 | 0.121 [0.118, 0.121] | 2.4% | 0.7% | 0.6% / 1.0% | 1 / 0.33 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_mem_mib` |
| overhead/print-write | anthropic | kb50_peak_rss_mib | memory | MiB | 7 | 310 | 44.1 | 0.142 [0.141, 0.143] | 5.4% | 0.5% | 0.4% / 2.1% | 0.625 / 0.289 | 1 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_rss_mib` |
| overhead/print-write | anthropic | kb50_wall_ms | wall | ms | 7 | 2,384 | 627 | 0.263 [0.262, 0.264] | 0.7% | 0.4% | 0.3% / 0.8% | 8.61 / 1.5 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_wall_ms` |
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 34,051 | 9,210 | 0.27 [0.27, 0.272] | 0.5% | 0.3% | 0.4% / 0.3% | 142 / 20.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,183 | 9,345 | 0.273 [0.273, 0.275] | 0.5% | 0.3% | 0.4% / 0.2% | 139 / 19.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,591 | 9,731 | 0.273 [0.273, 0.276] | 0.6% | 0.4% | 0.4% / 0.3% | 169 / 47 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99344.82M | 26956.30M | 0.271 [0.271, 0.274] | 0.6% | 0.4% | 0.4% / 0.2% | 467,008,189 / 88,626,061 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402373.01M | 126375.22M | 0.314 [0.314, 0.314] | 0.1% | 0.1% | 0.1% / 0.1% | 360,657,708 / 91,203,037 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 544 | 130 | 0.239 [0.235, 0.252] | 5.7% | 1.2% | 1.0% / 3.4% | 7.06 / 5.92 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 144 | 0.249 [0.238, 0.256] | 5.8% | 1.5% | 1.1% / 3.6% | 10.5 / 7.31 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,550 | 9,404 | 0.272 [0.271, 0.273] | 0.5% | 0.3% | 0.4% / 0.3% | 154 / 22.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,062 | 572 | 0.277 [0.265, 0.28] | 4.9% | 4.0% | 2.6% / 0.6% | 100 / 4.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,097 | 610 | 0.291 [0.278, 0.294] | 4.8% | 4.0% | 2.5% / 0.8% | 101 / 5.81 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,734 | 703 | 0.257 [0.249, 0.262] | 3.8% | 2.9% | 2.0% / 1.0% | 93.2 / 7.61 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7633.50M | 1896.99M | 0.249 [0.24, 0.252] | 3.8% | 3.0% | 2.0% / 0.8% | 261,498,112 / 17,216,322 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28074.90M | 8133.18M | 0.29 [0.289, 0.29] | 0.2% | 0.1% | 0.1% / 0.1% | 41,791,714 / 9,393,206 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 31.3 | 0.12 [0.117, 0.122] | 3.5% | 0.7% | 0.3% / 1.7% | 1.16 / 0.655 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 43.1 | 0.139 [0.139, 0.144] | 4.2% | 0.7% | 0.3% / 2.6% | 0.983 / 1.06 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,429 | 624 | 0.257 [0.247, 0.26] | 4.4% | 3.6% | 2.2% / 0.8% | 105 / 5.73 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_wall_ms` |
| overhead/print-write | responses | kb200_after_stream_ms | wall | ms | 7 | 34,165 | 9,271 | 0.271 [0.259, 0.274] | 5.3% | 2.8% | 2.5% / 0.6% | 1,663 / 50.2 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_after_stream_ms` |
| overhead/print-write | responses | kb200_call_to_result_ms | wall | ms | 7 | 34,275 | 9,391 | 0.274 [0.262, 0.276] | 5.3% | 2.8% | 2.5% / 0.6% | 1,662 / 55.2 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_call_to_result_ms` |
| overhead/print-write | responses | kb200_cpu_ms | CPU | ms of CPU time | 7 | 35,639 | 9,816 | 0.275 [0.263, 0.277] | 5.1% | 2.6% | 2.4% / 0.7% | 1,617 / 68.8 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cpu_ms` |
| overhead/print-write | responses | kb200_cycles | CPU | cycles | 7 | 99473.09M | 27182.77M | 0.273 [0.261, 0.275] | 5.1% | 2.6% | 2.4% / 0.7% | 4,489,916,818 / 181,744,736 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cycles` |
| overhead/print-write | responses | kb200_instructions | CPU | instructions | 7 | 402617.50M | 126454.97M | 0.314 [0.314, 0.314] | 0.2% | 0.1% | 0.1% / 0.0% | 524,601,626 / 17,153,074 | 0 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_instructions` |
| overhead/print-write | responses | kb200_peak_mem_mib | memory | MiB | 7 | 546 | 253 | 0.462 [0.399, 0.509] | 24.1% | 17.1% | 0.7% / 10.2% | 3.5 / 33.6 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_mem_mib` |
| overhead/print-write | responses | kb200_peak_rss_mib | memory | MiB | 7 | 581 | 264 | 0.454 [0.399, 0.503] | 22.4% | 15.8% | 0.7% / 9.5% | 3.63 / 33.1 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_rss_mib` |
| overhead/print-write | responses | kb200_wall_ms | wall | ms | 7 | 34,628 | 9,439 | 0.273 [0.26, 0.275] | 5.2% | 2.8% | 2.5% / 0.5% | 1,669 / 51.3 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_wall_ms` |
| overhead/print-write | responses | kb50_after_stream_ms | wall | ms | 7 | 2,067 | 580 | 0.28 [0.273, 0.285] | 2.8% | 1.8% | 1.5% / 1.6% | 49.7 / 8.49 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_after_stream_ms` |
| overhead/print-write | responses | kb50_call_to_result_ms | wall | ms | 7 | 2,092 | 612 | 0.293 [0.283, 0.295] | 3.0% | 1.8% | 1.5% / 0.9% | 52.6 / 6.99 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_call_to_result_ms` |
| overhead/print-write | responses | kb50_cpu_ms | CPU | ms of CPU time | 7 | 2,748 | 708 | 0.257 [0.252, 0.259] | 3.0% | 2.1% | 1.3% / 1.1% | 52.2 / 7.87 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cpu_ms` |
| overhead/print-write | responses | kb50_cycles | CPU | cycles | 7 | 7675.93M | 1910.25M | 0.249 [0.244, 0.251] | 3.0% | 2.1% | 1.3% / 1.0% | 144,046,084 / 19,139,599 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cycles` |
| overhead/print-write | responses | kb50_instructions | CPU | instructions | 7 | 28066.00M | 8124.27M | 0.289 [0.289, 0.29] | 0.2% | 0.1% | 0.1% / 0.1% | 47,389,679 / 6,405,055 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_instructions` |
| overhead/print-write | responses | kb50_peak_mem_mib | memory | MiB | 7 | 262 | 40.7 | 0.156 [0.154, 0.16] | 2.2% | 0.7% | 0.7% / 1.6% | 2.74 / 0.914 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_mem_mib` |
| overhead/print-write | responses | kb50_peak_rss_mib | memory | MiB | 7 | 310 | 52.9 | 0.171 [0.168, 0.176] | 4.6% | 0.5% | 0.6% / 2.6% | 2.48 / 1.64 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_rss_mib` |
| overhead/print-write | responses | kb50_wall_ms | wall | ms | 7 | 2,413 | 625 | 0.259 [0.251, 0.261] | 2.7% | 1.7% | 1.3% / 0.9% | 53.4 / 6.51 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_wall_ms` |
| streaming/print-prose | anthropic | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 8.21 | 3.49 | 0.426 [0.414, 0.479] | 11.0% | 4.3% | 3.3% / 5.6% | 0.38 / 0.357 | 0 / 3 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | anthropic | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 42.64M | 13.39M | 0.314 [0.295, 0.315] | 7.1% | 0.2% | 0.3% / 3.3% | 121,396 / 456,240 | 0 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_instructions_per_1k_tokens` |
| streaming/print-prose | anthropic | n10_wall_ms | wall | ms | 7 | 55.2 | 33.4 | 0.606 [0.537, 0.616] | 10.4% | 3.1% | 3.3% / 4.8% | 1.92 / 1.83 | 0 / 2 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_wall_ms` |
| streaming/print-prose | anthropic | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 49.3 | 3.9 | 0.0791 [0.0772, 0.082] | 6.2% | 2.6% | 1.7% / 4.2% | 0.936 / 0.107 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | anthropic | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 261.15M | 13.39M | 0.0513 [0.0506, 0.0523] | 1.7% | 1.4% | 1.0% / 1.8% | 2,972,842 / 138,569 | 2 / 1 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_instructions_per_1k_tokens` |
| streaming/print-prose | anthropic | n_peak_rss_mib | memory | MiB | 7 | 132 | 4.18 | 0.0317 [0.0311, 0.0326] | 4.9% | 3.1% | 1.8% / 1.6% | 1.83 / 0.102 | 1 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_peak_rss_mib` |
| streaming/print-prose | anthropic | n_wall_ms | wall | ms | 7 | 52.5 | 3.86 | 0.0735 [0.073, 0.0741] | 3.3% | 3.0% | 0.8% / 1.0% | 0.519 / 0.0399 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_wall_ms` |
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.0 | 3.61 | 0.361 [0.349, 0.38] | 8.3% | 9.7% | 10.0% / 2.7% | 0.519 / 0.0651 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.25M | 14.41M | 0.266 [0.263, 0.27] | 3.7% | 0.2% | 0.2% / 1.3% | 79,739 / 270,609 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 136 | 32.7 | 0.241 [0.216, 0.246] | 10.4% | 1.2% | 1.1% / 9.2% | 2.24 / 2.11 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.4 | 34.9 | 0.51 [0.501, 0.52] | 5.0% | 11.6% | 11.8% / 1.5% | 0.523 / 0.653 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.4 | 4 | 0.0722 [0.0703, 0.0782] | 10.4% | 2.6% | 1.8% / 6.0% | 1.46 / 0.355 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.73M | 14.25M | 0.0501 [0.0495, 0.0508] | 2.1% | 0.3% | 0.4% / 1.7% | 1,527,097 / 275,850 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 4.17 | 0.0305 [0.0301, 0.031] | 5.6% | 1.9% | 1.3% / 1.3% | 3.42 / 0.0498 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.3 | 4.02 | 0.0755 [0.074, 0.0774] | 5.7% | 1.4% | 1.6% / 1.8% | 1.13 / 0.07 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_wall_ms` |
| streaming/print-prose | responses | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 10.3 | 3.94 | 0.383 [0.376, 0.396] | 12.1% | 3.6% | 2.4% / 2.7% | 0.0274 / 0.138 | 2 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 56.51M | 15.48M | 0.274 [0.272, 0.277] | 7.1% | 0.7% | 0.6% / 2.1% | 381,984 / 168,521 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_instructions_per_1k_tokens` |
| streaming/print-prose | responses | n10_peak_rss_mib | memory | MiB | 7 | 140 | 36.1 | 0.259 [0.253, 0.281] | 16.7% | 1.2% | 0.7% / 5.4% | 1.23 / 2.26 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_peak_rss_mib` |
| streaming/print-prose | responses | n10_wall_ms | wall | ms | 7 | 73.3 | 34.9 | 0.476 [0.446, 0.495] | 8.8% | 5.8% | 5.2% / 1.1% | 5.98 / 0.539 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_wall_ms` |
| streaming/print-prose | responses | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 7 | 57.3 | 5.11 | 0.0891 [0.0829, 0.0915] | 10.8% | 3.1% | 1.8% / 5.0% | 1.33 / 0.355 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 7 | 292.81M | 16.58M | 0.0566 [0.0549, 0.0571] | 4.2% | 0.4% | 0.2% / 2.1% | 589,683 / 486,991 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_instructions_per_1k_tokens` |
| streaming/print-prose | responses | n_peak_rss_mib | memory | MiB | 7 | 137 | 4.19 | 0.0306 [0.0302, 0.0313] | 5.0% | 1.3% | 0.7% / 1.6% | 0.932 / 0.0859 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_peak_rss_mib` |
| streaming/print-prose | responses | n_wall_ms | wall | ms | 7 | 53.1 | 4.05 | 0.0763 [0.0733, 0.0783] | 5.1% | 1.9% | 1.7% / 1.8% | 1.45 / 0.0884 | 0 / 0 | 0.0469 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_wall_ms` |

## A/A noise floor

Each arm's A/A copy `<id>-b` is the same executable run in the same rounds. The floor of a cell is the largest deviation from 1 the copy's ratio-of-medians interval allows; a difference between arms smaller than the floor is reported as no measurable difference. The table gives, per arm and workload, the median and the maximum floor over the scored metrics, and the reference's minimum detectable effect at 80% power.

| arm | workload | api | cells | median floor | max floor | worst metric |
|---|---|---|---:|---:|---:|---|
| claude-code | overhead/print-write | anthropic | 19 | 4.4% | 29.5% | kb200_after_stream_ms |
| claude-code | streaming/print-prose | anthropic | 11 | 2.1% | 9.8% | n_wall_ms |
| codex | overhead/print-write | responses | 19 | 2.2% | 5.5% | kb50_call_to_result_ms |
| codex | streaming/print-prose | responses | 11 | 5.0% | 16.1% | n_wall_ms |
| copilot | overhead/print-write | anthropic | 19 | 3.3% | 6.5% | kb50_after_stream_ms |
| copilot | overhead/print-write | chat | 19 | 2.0% | 4.9% | kb50_after_stream_ms |
| copilot | overhead/print-write | responses | 19 | 2.2% | 6.7% | kb200_after_stream_ms |
| copilot | streaming/print-prose | anthropic | 11 | 0.9% | 13.8% | n_cpu_ms_per_1k_tokens |
| copilot | streaming/print-prose | chat | 11 | 1.2% | 7.7% | n_cpu_ms_per_1k_tokens |
| copilot | streaming/print-prose | responses | 11 | 1.4% | 9.4% | n_cpu_ms_per_1k_tokens |
| octet | overhead/print-write | chat | 19 | 1.3% | 9.0% | kb50_peak_rss_mib |
| octet | streaming/print-prose | chat | 11 | 3.3% | 10.3% | n_cpu_ms_per_1k_tokens |
| opencode-v2 | overhead/print-write | chat | 20 | 6.2% | 37.8% | kb50_after_stream_ms |
| opencode-v2 | streaming/print-prose | chat | 12 | 2.2% | 23.3% | n_wall_ms |
| pi-node | overhead/print-write | anthropic | 19 | 0.6% | 2.2% | kb200_peak_mem_mib |
| pi-node | overhead/print-write | chat | 19 | 0.6% | 4.9% | kb50_after_stream_ms |
| pi-node | overhead/print-write | responses | 19 | 2.7% | 5.3% | kb200_after_stream_ms |
| pi-node | streaming/print-prose | anthropic | 11 | 1.5% | 5.5% | n10_cpu_ms_per_1k_tokens |
| pi-node | streaming/print-prose | chat | 11 | 1.5% | 5.5% | n10_cpu_ms_per_1k_tokens |
| pi-node | streaming/print-prose | responses | 11 | 1.1% | 8.8% | n10_wall_ms |
| rpi | overhead/print-write | anthropic | 19 | 1.2% | 38.9% | kb200_peak_mem_mib |
| rpi | overhead/print-write | chat | 19 | 0.4% | 5.8% | kb200_peak_rss_mib |
| rpi | overhead/print-write | responses | 19 | 0.8% | 24.1% | kb200_peak_mem_mib |
| rpi | streaming/print-prose | anthropic | 11 | 4.9% | 700.4% | n10_peak_rss_mib |
| rpi | streaming/print-prose | chat | 11 | 3.7% | 10.4% | n_cpu_ms_per_1k_tokens |
| rpi | streaming/print-prose | responses | 11 | 5.1% | 16.7% | n10_peak_rss_mib |

Minimum detectable effect of the reference's A/A pair over all cells: median 1.2%, worst 17.1%. A difference smaller than the cell's MDE cannot be seen in this run.

## Cell ids and rerun commands

Every cell has an id, `<run id>::<workload>@<api>#<metric>`. `python3 -m buffon rerun <cell id> --site <your site profile>` repeats the plan of the run that holds the cell (its arms, rounds, seed and parameters) for that workload and API only, on your host, and compares your result with the original. The raw samples of every cell are in the run directory's raw.json; this report is generated from them and from nothing else, and `buffon verify` regenerates it to check that no number was edited.

| workload | api | metric | cell id |
|---|---|---|---|
| overhead/print-write | anthropic | kb200_after_stream_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_after_stream_ms` |
| overhead/print-write | anthropic | kb200_call_to_result_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_call_to_result_ms` |
| overhead/print-write | anthropic | kb200_cpu_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cpu_ms` |
| overhead/print-write | anthropic | kb200_cycles | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_cycles` |
| overhead/print-write | anthropic | kb200_instructions | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_instructions` |
| overhead/print-write | anthropic | kb200_peak_mem_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_mem_mib` |
| overhead/print-write | anthropic | kb200_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_peak_rss_mib` |
| overhead/print-write | anthropic | kb200_wall_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb200_wall_ms` |
| overhead/print-write | anthropic | kb50_after_stream_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_after_stream_ms` |
| overhead/print-write | anthropic | kb50_call_to_result_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_call_to_result_ms` |
| overhead/print-write | anthropic | kb50_cpu_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cpu_ms` |
| overhead/print-write | anthropic | kb50_cycles | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_cycles` |
| overhead/print-write | anthropic | kb50_instructions | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_instructions` |
| overhead/print-write | anthropic | kb50_peak_mem_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_mem_mib` |
| overhead/print-write | anthropic | kb50_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_peak_rss_mib` |
| overhead/print-write | anthropic | kb50_wall_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#kb50_wall_ms` |
| overhead/print-write | anthropic | request_bytes | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes` |
| overhead/print-write | anthropic | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#request_bytes_per_turn` |
| overhead/print-write | anthropic | requests | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#requests` |
| overhead/print-write | anthropic | side_requests | `2026-10-19-smc1-launch-focus-others::overhead/print-write@anthropic-messages#side_requests` |
| overhead/print-write | chat | kb200_after_stream_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_cpu_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-write | chat | kb50_instructions | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | chat | kb50_peak_mem_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | chat | kb50_wall_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#kb50_wall_ms` |
| overhead/print-write | chat | request_bytes | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#request_bytes_per_turn` |
| overhead/print-write | chat | requests | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#requests` |
| overhead/print-write | chat | side_requests | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-completions#side_requests` |
| overhead/print-write | responses | kb200_after_stream_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_after_stream_ms` |
| overhead/print-write | responses | kb200_call_to_result_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_call_to_result_ms` |
| overhead/print-write | responses | kb200_cpu_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cpu_ms` |
| overhead/print-write | responses | kb200_cycles | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_cycles` |
| overhead/print-write | responses | kb200_instructions | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_instructions` |
| overhead/print-write | responses | kb200_peak_mem_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_mem_mib` |
| overhead/print-write | responses | kb200_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_peak_rss_mib` |
| overhead/print-write | responses | kb200_wall_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb200_wall_ms` |
| overhead/print-write | responses | kb50_after_stream_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_after_stream_ms` |
| overhead/print-write | responses | kb50_call_to_result_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_call_to_result_ms` |
| overhead/print-write | responses | kb50_cpu_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cpu_ms` |
| overhead/print-write | responses | kb50_cycles | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_cycles` |
| overhead/print-write | responses | kb50_instructions | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_instructions` |
| overhead/print-write | responses | kb50_peak_mem_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_mem_mib` |
| overhead/print-write | responses | kb50_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_peak_rss_mib` |
| overhead/print-write | responses | kb50_wall_ms | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#kb50_wall_ms` |
| overhead/print-write | responses | request_bytes | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes` |
| overhead/print-write | responses | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#request_bytes_per_turn` |
| overhead/print-write | responses | requests | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#requests` |
| overhead/print-write | responses | side_requests | `2026-10-19-smc1-launch-focus-others::overhead/print-write@openai-responses#side_requests` |
| streaming/print-prose | anthropic | n10_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | anthropic | n10_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_instructions_per_1k_tokens` |
| streaming/print-prose | anthropic | n10_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_peak_rss_mib` |
| streaming/print-prose | anthropic | n10_wall_ms | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n10_wall_ms` |
| streaming/print-prose | anthropic | n_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | anthropic | n_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_instructions_per_1k_tokens` |
| streaming/print-prose | anthropic | n_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_peak_rss_mib` |
| streaming/print-prose | anthropic | n_wall_ms | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#n_wall_ms` |
| streaming/print-prose | anthropic | request_bytes | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes` |
| streaming/print-prose | anthropic | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#request_bytes_per_turn` |
| streaming/print-prose | anthropic | requests | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#requests` |
| streaming/print-prose | anthropic | side_requests | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@anthropic-messages#side_requests` |
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n10_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n10_wall_ms | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | chat | n_wall_ms | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#n_wall_ms` |
| streaming/print-prose | chat | request_bytes | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| streaming/print-prose | chat | requests | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#requests` |
| streaming/print-prose | chat | side_requests | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-completions#side_requests` |
| streaming/print-prose | responses | n10_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n10_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_instructions_per_1k_tokens` |
| streaming/print-prose | responses | n10_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_peak_rss_mib` |
| streaming/print-prose | responses | n10_wall_ms | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n10_wall_ms` |
| streaming/print-prose | responses | n_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | responses | n_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_instructions_per_1k_tokens` |
| streaming/print-prose | responses | n_peak_rss_mib | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_peak_rss_mib` |
| streaming/print-prose | responses | n_wall_ms | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#n_wall_ms` |
| streaming/print-prose | responses | request_bytes | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes` |
| streaming/print-prose | responses | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#request_bytes_per_turn` |
| streaming/print-prose | responses | requests | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#requests` |
| streaming/print-prose | responses | side_requests | `2026-10-19-smc1-launch-focus-others::streaming/print-prose@openai-responses#side_requests` |

## Noise report

How noisy this run was, from its own samples and the telemetry taken around each one (docs/TELEMETRY.md). The A/A figures compare each arm with its own identical copy, so they show what the host does to two runs of the same executable.

### Per metric

| metric | cells | A/A gap median | A/A gap worst | A/A floor median | A/A floor worst | CV median | CV worst | outliers / values | drift median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kb200_after_stream_ms | 3 | 0.4% | 13.6% | 2.8% | 37.2% | 1.5% | 19.7% | 7 / 192 | 0.6% |
| kb200_call_to_result_ms | 3 | 0.3% | 8.5% | 1.2% | 20.7% | 0.7% | 13.4% | 8 / 192 | 0.3% |
| kb200_cpu_ms | 3 | 0.3% | 4.0% | 3.2% | 8.2% | 1.3% | 9.0% | 4 / 192 | 0.6% |
| kb200_cycles | 3 | 0.3% | 4.0% | 2.0% | 9.4% | 1.0% | 9.4% | 4 / 192 | 0.5% |
| kb200_instructions | 3 | 0.1% | 1.4% | 0.5% | 2.6% | 0.2% | 1.5% | 4 / 192 | 0.1% |
| kb200_peak_mem_mib | 3 | 1.2% | 25.1% | 3.0% | 38.9% | 1.5% | 16.9% | 3 / 192 | 1.5% |
| kb200_peak_rss_mib | 3 | 1.1% | 22.4% | 2.5% | 34.6% | 1.5% | 15.5% | 6 / 192 | 0.9% |
| kb200_wall_ms | 3 | 0.3% | 3.8% | 3.5% | 8.6% | 0.9% | 8.2% | 8 / 192 | 0.6% |
| kb50_after_stream_ms | 3 | 0.5% | 16.2% | 3.9% | 37.8% | 1.7% | 15.8% | 9 / 192 | 1.2% |
| kb50_call_to_result_ms | 3 | 0.5% | 12.4% | 4.4% | 30.3% | 1.5% | 11.6% | 5 / 192 | 1.0% |
| kb50_cpu_ms | 3 | 0.6% | 3.0% | 3.0% | 8.8% | 1.3% | 4.9% | 6 / 192 | 1.2% |
| kb50_cycles | 3 | 0.7% | 3.1% | 2.2% | 8.9% | 1.2% | 4.8% | 7 / 192 | 1.2% |
| kb50_instructions | 3 | 0.2% | 2.1% | 0.8% | 2.6% | 0.3% | 1.3% | 1 / 192 | 0.2% |
| kb50_peak_mem_mib | 3 | 0.6% | 2.0% | 2.2% | 7.9% | 1.1% | 5.4% | 6 / 192 | 0.3% |
| kb50_peak_rss_mib | 3 | 0.3% | 0.9% | 2.1% | 9.0% | 1.2% | 6.9% | 9 / 192 | 0.7% |
| kb50_wall_ms | 3 | 0.7% | 3.8% | 2.4% | 11.4% | 1.1% | 6.6% | 10 / 192 | 1.1% |
| n10_cpu_ms_per_1k_tokens | 3 | 2.2% | 3.9% | 6.6% | 12.5% | 2.9% | 12.0% | 11 / 192 | 1.7% |
| n10_instructions_per_1k_tokens | 3 | 0.2% | 2.8% | 2.1% | 7.1% | 1.0% | 4.3% | 2 / 192 | 0.6% |
| n10_peak_rss_mib | 3 | 0.6% | 6.0% | 1.6% | 700.4% | 0.9% | 57.5% | 9 / 192 | 1.7% |
| n10_wall_ms | 3 | 1.1% | 3.4% | 5.6% | 10.4% | 2.1% | 13.6% | 8 / 192 | 2.3% |
| n_cpu_ms_per_1k_tokens | 3 | 1.6% | 8.8% | 9.4% | 14.0% | 4.1% | 9.8% | 5 / 192 | 3.7% |
| n_instructions_per_1k_tokens | 3 | 0.5% | 8.5% | 3.7% | 12.8% | 2.0% | 6.8% | 16 / 192 | 1.9% |
| n_peak_rss_mib | 3 | 0.9% | 3.3% | 1.8% | 6.2% | 1.3% | 7.0% | 3 / 192 | 0.5% |
| n_wall_ms | 3 | 1.4% | 12.2% | 3.9% | 23.3% | 2.0% | 9.4% | 6 / 192 | 2.4% |
| request_bytes | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 384 | 0.0% |
| request_bytes_per_turn | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 384 | 0.0% |
| requests | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 384 | 0.0% |
| side_requests | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 384 | 0.0% |

A/A gap: the copy's median against the arm's, per cell. A/A floor: the largest deviation from 1 the copy's ratio interval allows (METHODOLOGY section 6). CV: the standard deviation of an arm's rounds over their mean. Outliers: a measured value is an outlier when |x - median| > 5 x 1.4826 x MAD of its arm's values in that cell (needs 4 values; with MAD 0, any different value). Outliers are counted, never removed. Drift: the Theil-Sen trend of an arm's rounds times the rounds spanned, as a share of its median.

### Run 1

- Samples: 384 measured (384 ok, 0 failed), 52 warm-up; telemetry on 384 of 384 ok samples. Sources read: cgroup_throttle, cpufreq, loadavg, meminfo, pressure, proc_stat, schedstat, thermal_throttle, vmstat.
- Calibration: CV 1.4% of cpu_ms on pi-node (gate 5.0%), passed.
- CFS throttling: 0 samples, 0 us in all; the session's cgroup lost 0 us over the whole run.
- Quiet-host gate: 384 passed at once, 0 waited (longest 0.0 s, 0.0 s in all), 0 gave up.
- Steal: 0.000% of the pinned CPUs' capacity. Foreign CPU on the pinned CPUs: p95 0.0% of the sample's CPU time. Clock: largest deviation 0.2% from the median 2800 MHz. iowait is recorded in every sample and never gated.
- Failed samples: 0 arm, 0 infrastructure (the arm is not charged for those); 0 ladder stops (a swarm rung that hit the kernel's limit: a result, not a failure). CPU quota on the arm cgroup or an ancestor: none.
- Flagged samples: 9 of 384 (clock_moved 9).
- Telemetry cost: the collector's thread used 19.35 ms median per sample (worst 265.72 ms), on the runner's CPUs, outside the pinned set.
- Host load before / after: 1.0 / 1.3; pinned CPUs busy over the run: mean 13.4%, max 32.7%.

Flagged samples (kept in the statistics unless the report is made with `--drop-flagged`; the first 9 of 9):

| arm | workload | api | round | flags |
|---|---|---|---:|---|
| pi-node | overhead/print-write | anthropic-messages | 1 | clock_moved |
| pi-node | overhead/print-write | openai-responses | 1 | clock_moved |
| pi-node-b | overhead/print-write | openai-completions | 1 | clock_moved |
| pi-node-b | overhead/print-write | anthropic-messages | 2 | clock_moved |
| pi-node-b | overhead/print-write | openai-completions | 3 | clock_moved |
| pi-node-b | overhead/print-write | openai-responses | 3 | clock_moved |
| pi-node | overhead/print-write | openai-responses | 3 | clock_moved |
| pi-node | overhead/print-write | openai-responses | 5 | clock_moved |
| pi-node | overhead/print-write | anthropic-messages | 6 | clock_moved |

### Do the flagged rounds change the answer?

The report was built again without the 8 flagged rounds: 181 of 300 comparisons change verdict.

| workload | api | metric | arm | with flagged rounds | without |
|---|---|---|---|---|---|
| overhead/print-write | anthropic-messages | kb200_after_stream_ms | claude-code | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_after_stream_ms | copilot | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_after_stream_ms | rpi | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_call_to_result_ms | claude-code | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_call_to_result_ms | copilot | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_call_to_result_ms | rpi | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_cpu_ms | claude-code | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_cpu_ms | copilot | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_cpu_ms | rpi | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_cycles | claude-code | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_cycles | copilot | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_cycles | rpi | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_instructions | claude-code | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_instructions | copilot | win | inconclusive (paired test p 0.38 >= 0.05) |
| overhead/print-write | anthropic-messages | kb200_instructions | rpi | win | inconclusive (paired test p 0.38 >= 0.05) |

### Samples and rounds not in the statistics

| reason | samples | rounds |
|---|---:|---:|
| warm-up round (kept in the raw data, excluded from the statistics by rule) | 52 | 1 |

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
| claude-code | overhead/print-write | chat | it does not speak openai-completions |
| claude-code | overhead/print-write | responses | it does not speak openai-responses |
| claude-code | streaming/print-prose | chat | it does not speak openai-completions |
| claude-code | streaming/print-prose | responses | it does not speak openai-responses |
| claude-code-b | overhead/print-write | chat | it does not speak openai-completions |
| claude-code-b | overhead/print-write | responses | it does not speak openai-responses |
| claude-code-b | streaming/print-prose | chat | it does not speak openai-completions |
| claude-code-b | streaming/print-prose | responses | it does not speak openai-responses |
| codex | overhead/print-write | anthropic | it does not speak anthropic-messages |
| codex | overhead/print-write | chat | it does not speak openai-completions |
| codex | streaming/print-prose | anthropic | it does not speak anthropic-messages |
| codex | streaming/print-prose | chat | it does not speak openai-completions |
| codex-b | overhead/print-write | anthropic | it does not speak anthropic-messages |
| codex-b | overhead/print-write | chat | it does not speak openai-completions |
| codex-b | streaming/print-prose | anthropic | it does not speak anthropic-messages |
| codex-b | streaming/print-prose | chat | it does not speak openai-completions |
| octet | overhead/print-write | anthropic | it does not speak anthropic-messages |
| octet | overhead/print-write | responses | it does not speak openai-responses |
| octet | streaming/print-prose | anthropic | it does not speak anthropic-messages |
| octet | streaming/print-prose | responses | it does not speak openai-responses |
| octet-b | overhead/print-write | anthropic | it does not speak anthropic-messages |
| octet-b | overhead/print-write | responses | it does not speak openai-responses |
| octet-b | streaming/print-prose | anthropic | it does not speak anthropic-messages |
| octet-b | streaming/print-prose | responses | it does not speak openai-responses |
| opencode-v2 | overhead/print-write | anthropic | it does not speak anthropic-messages |
| opencode-v2 | overhead/print-write | responses | it does not speak openai-responses |
| opencode-v2 | streaming/print-prose | anthropic | it does not speak anthropic-messages |
| opencode-v2 | streaming/print-prose | responses | it does not speak openai-responses |
| opencode-v2-b | overhead/print-write | anthropic | it does not speak anthropic-messages |
| opencode-v2-b | overhead/print-write | responses | it does not speak openai-responses |
| opencode-v2-b | streaming/print-prose | anthropic | it does not speak anthropic-messages |
| opencode-v2-b | streaming/print-prose | responses | it does not speak openai-responses |

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

Pins of the arms exactly as the run recorded them (arms.lock sha256 `2c7b43d74cd7172acf7e967b44b949816327052605f2926b0cd28beba91fc878`). A third party who checks out the runner commit gets the same pins, and `buffon rerun` repeats a cell with them.

| arm | exact version | source | checksums | build | manifest sha256 | executable sha256 |
|---|---|---|---|---|---|---|
| claude-code | 2.1.296 | @anthropic-ai/claude-code@2.1.296 | integrity `sha512-OX/k/rpcthMqnFKOWcpNcbiLsMKtAjLOpQNJHlYiDCFUznWCIwdRTyl/p9SdHVrsrzZuPMCNqZjnpakIni6upw==`<br>package_lock_sha256 `8024fbbdc141e946abcfb87d71d873f3ac021cbee3b8080df5cdbe7a16622712` | node 24.19.0; linux-x64 | `7af7a5bd60f05a16c83f35d7a403f88723334bdaf99b4d8b2a431dc7fafea28a` | `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de` |
| codex | 0.162.1 | @openai/codex@0.162.1 | integrity `sha512-NWZdi/kxyjv/8EUGFupziGU38YyleugZRM4JXgY5XFH7FUmaFA33NZS2Bmq0HPazf7S3jJQQWsZ/jAK9jsrV3Q==`<br>package_lock_sha256 `a17117b06362c74b63de80e9c4cb525cf8556b5ead9d0d0e250473061365902d` | node 24.19.0; linux-x64 | `72b2eabc3828da3ed2055c7fab4d1d3c9dfb76258d7fdedd5f2a98776fb91d1d` | `61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70` |
| copilot | 1.0.95 | @github/copilot@1.0.95 | integrity `sha512-TAYlgMwjTnHi04ZGRc6Z+41piGeUC6xuA8z7gWVc5qOTqJLi/B3vCVg9ttkwvxnahbTWjX8x0DORwrJMXOQxGg==`<br>package_lock_sha256 `719cc494d4518865e011f319d354b1dcd52250fe4b45124f2b0f781e0620b9f8` | node 24.19.0; linux-x64 | `fed4d99a3a7bb66c5a015567c61bb343f86acb6e19e88b3a83696eee9be9bb78` | `9cf62455c0fef57658c976b737f57ddc4b87c2f513a17864846f2d0e16a18a99` |
| octet | 0.9.4 | https://github.com/skaft-software/octet/releases/download/v0.9.4/octet-0.9.4-x86_64-unknown-linux-gnu.tar.gz | artifact_sha256 `966e75a5551f46627080a4619383dbb402b5a72280a88e658bf2ce36e1059048` | linux-x64 | `a5f57ec6b6af729ca12c9f0e5de5647edd101dcdc5786c1fccc8cf4ac206f699` | `64b98a264669190f883da988452d9820dc23bfc5ccb81ebade4abbdffe0ac293` |
| opencode-v2 | 2.0.29 | @opencode/cli@2.0.29 | integrity `sha512-1ZmbylUtiRvtN8YMLxBEN4u0tqhfKI0AQBPvgdCLYLbB8BS80e6cFnOhzHH6L663o4RVL5bMa/VleLh1hNX+NA==`<br>package_lock_sha256 `afe4ef2f6eb18cd9e783a08b35e86e28a4a3fbd19ee931cf23375ad53b6a4843` | node 24.19.0; linux-x64 | `9d1a1af05b40bf19f6b7035e723b3aea173284161d189d1a6cd9a3fc5ba939cd` | `7e23471f4ebe2313d78baacc9ac96fe9e197ce26d808de4b0fcc37efbe473dad` |
| pi-node | 1.3.0 | @earendil-works/pi-coding-agent@1.3.0 | integrity `sha512-V/WoCjA2hQSe3QLWIUB24cTRdtEdeLiIzkDqU5RMXV6VWuD+KGZnzVBMhglwdnQTySkehZsjt8a3g6Jd2g4nnw==`<br>package_lock_sha256 `65eacda789c30e1c3859a96eee2fd53cf4a18629d27dcf2aa6d7bdb3da02d719` | node 24.19.0; linux-x64 | `17662e8cd8bd784c3f3dd8a8b4e0864387babb4075d66aa52a60b3b02ba56457` | `e79626f2dd6f94aa45d30f3fa63cd84319a6eefcd150b353cfaf274366926774` |
| rpi | 0.3.19 | https://github.com/bigfish1913/pi-rust/releases/download/v0.3.19/rpi-v0.3.19-x86_64-unknown-linux-gnu.tar.gz | artifact_sha256 `c48ef652be3093a28f06076e5a21f2746e155959a181aadd2d17dbdb819991bd` | linux-x64 | `2ed08713cf4168ead42831b40ce7dd9aceaac9c14aa3852edfb3d11f012a64ee` | `a79400a27228370f2995215e2a5e5c82efa6207b07a2002027d01a191206adb1` |

## Arms and environment

| arm | version | version line | executable sha256 | footprint | install | licence |
|---|---|---|---|---|---|---|
| claude-code | 2.1.296 | 2.1.296 (Claude Code) | `24972e3bc859fab2` | 257.3 MB + node 199 MB | npm ci --ignore-scripts (@anthropic-ai/claude-code) | proprietary (Anthropic legal agreements) |
| codex | 0.162.1 | codex-cli 0.162.1 | `61b0194f3bb65344` | 452.5 MB + node 199 MB | npm ci --ignore-scripts (@openai/codex) | Apache-2.0 |
| copilot | 1.0.95 | GitHub Copilot CLI 1.0.95. | `9cf62455c0fef576` | 183.8 MB + node 199 MB | npm ci --ignore-scripts (@github/copilot) | GitHub Copilot CLI License |
| octet | 0.9.4 | octet 0.9.4 | `64b98a264669190f` | 96.3 MB | release archive (https://github.com/skaft-software/octet/releases/download/v0) | MIT |
| opencode-v2 | 2.0.29 | opencode v2.0.29 | `7e23471f4ebe2313` | 845.0 MB + node 199 MB | npm ci --ignore-scripts (@opencode/cli) | MIT |
| pi-node | 1.3.0 | 1.3.0 | `e79626f2dd6f94aa` | 110.6 MB + node 199 MB | npm ci --ignore-scripts (@earendil-works/pi-coding-agent) | MIT |
| rpi | 0.3.19 | rpi 0.3.19 | `a79400a27228370f` | 28.6 MB | release archive (https://github.com/bigfish1913/pi-rust/releases/download/v0.) | MIT |

A/A copies run the same executable as their original (same sha256), installed as their own copy of the install tree.

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
| idle_before | {"48": 0.0, "49": 0.0, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0, "114": 0.0, "115": 0.0} |
| idle_after | {"48": 0.0, "49": 0.01, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0, "114": 0.0, "115": 0.0} |
| load_before | [1.02587890625, 1.86962890625, 2.03564453125] |
| load_after | [1.326171875, 1.4140625, 1.46337890625] |
| throttled_usec | 0 |
| cpumon | {"samples": 3438, "pinned_busy_mean": 0.13423437590672263, "pinned_busy_max": 0.32748067408781695, "host_busy_mean": 0.011067802580892315} |
| go | null |
| node_js | null |
| python | 3.12.3 |

Variables each harness was started with beyond the host's environment (the throwaway root is `<work>`); credential-looking and proxy variables of the host are removed:

- **claude-code**: `ANTHROPIC_API_KEY=<dummy key>`, `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS=128000`, `CLAUDE_CONFIG_DIR=<work>/claude-code-a-print-write-kb50-anthropic/home/.claude`, `DISABLE_AUTOUPDATER=1`, `DISABLE_BUG_COMMAND=1`, `DISABLE_ERROR_REPORTING=1`, `DISABLE_TELEMETRY=1`, `HOME=<work>/claude-code-a-print-write-kb50-anthropic/home`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/claude-code-a-print-write-kb50-anthropic/disk/tmp`, `XDG_CACHE_HOME=<work>/claude-code-a-print-write-kb50-anthropic/disk/cache`, `XDG_CONFIG_HOME=<work>/claude-code-a-print-write-kb50-anthropic/home/.config`, `XDG_DATA_HOME=<work>/claude-code-a-print-write-kb50-anthropic/home/.local/share`, `XDG_STATE_HOME=<work>/claude-code-a-print-write-kb50-anthropic/home/.local/state`
- **claude-code-b**: `ANTHROPIC_API_KEY=<dummy key>`, `ANTHROPIC_BASE_URL=http://127.0.0.1:<port>`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `CLAUDE_CODE_MAX_CONTEXT_TOKENS=128000`, `CLAUDE_CONFIG_DIR=<work>/claude-code-b-print-write-kb50-anthropic/home/.claude`, `DISABLE_AUTOUPDATER=1`, `DISABLE_BUG_COMMAND=1`, `DISABLE_ERROR_REPORTING=1`, `DISABLE_TELEMETRY=1`, `HOME=<work>/claude-code-b-print-write-kb50-anthropic/home`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/claude-code-b-print-write-kb50-anthropic/disk/tmp`, `XDG_CACHE_HOME=<work>/claude-code-b-print-write-kb50-anthropic/disk/cache`, `XDG_CONFIG_HOME=<work>/claude-code-b-print-write-kb50-anthropic/home/.config`, `XDG_DATA_HOME=<work>/claude-code-b-print-write-kb50-anthropic/home/.local/share`, `XDG_STATE_HOME=<work>/claude-code-b-print-write-kb50-anthropic/home/.local/state`
- **codex**: `BENCH_API_KEY=<dummy key>`, `CODEX_HOME=<work>/codex-a-print-write-kb50-openai/home/.codex`, `HOME=<work>/codex-a-print-write-kb50-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/codex-a-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/codex-a-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/codex-a-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/codex-a-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/codex-a-print-write-kb50-openai/home/.local/state`
- **codex-b**: `BENCH_API_KEY=<dummy key>`, `CODEX_HOME=<work>/codex-b-print-write-kb50-openai/home/.codex`, `HOME=<work>/codex-b-print-write-kb50-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/codex-b-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/codex-b-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/codex-b-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/codex-b-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/codex-b-print-write-kb50-openai/home/.local/state`
- **copilot**: `COPILOT_AUTO_UPDATE=false`, `COPILOT_HOME=<work>/copilot-a-print-write-kb50-openai/home/.copilot`, `COPILOT_MODEL=bench-1`, `COPILOT_OFFLINE=true`, `COPILOT_PROVIDER_API_KEY=<dummy key>`, `COPILOT_PROVIDER_BASE_URL=http://127.0.0.1:<port>/v1`, `COPILOT_PROVIDER_MAX_OUTPUT_TOKENS=8192`, `COPILOT_PROVIDER_MAX_PROMPT_TOKENS=128000`, `COPILOT_PROVIDER_TYPE=openai`, `COPILOT_PROVIDER_WIRE_API=completions`, `HOME=<work>/copilot-a-print-write-kb50-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/copilot-a-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/copilot-a-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/copilot-a-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/copilot-a-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/copilot-a-print-write-kb50-openai/home/.local/state`
- **copilot-b**: `COPILOT_AUTO_UPDATE=false`, `COPILOT_HOME=<work>/copilot-b-print-write-kb50-openai/home/.copilot`, `COPILOT_MODEL=bench-1`, `COPILOT_OFFLINE=true`, `COPILOT_PROVIDER_API_KEY=<dummy key>`, `COPILOT_PROVIDER_BASE_URL=http://127.0.0.1:<port>/v1`, `COPILOT_PROVIDER_MAX_OUTPUT_TOKENS=8192`, `COPILOT_PROVIDER_MAX_PROMPT_TOKENS=128000`, `COPILOT_PROVIDER_TYPE=openai`, `COPILOT_PROVIDER_WIRE_API=completions`, `HOME=<work>/copilot-b-print-write-kb50-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/copilot-b-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/copilot-b-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/copilot-b-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/copilot-b-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/copilot-b-print-write-kb50-openai/home/.local/state`
- **octet**: `HOME=<work>/octet-a-print-write-kb50-openai/home`, `OCTET_OFFLINE=true`, `PATH=/usr/bin:/bin`, `TMPDIR=<work>/octet-a-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/octet-a-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/octet-a-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/octet-a-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/octet-a-print-write-kb50-openai/home/.local/state`
- **octet-b**: `HOME=<work>/octet-b-print-write-kb50-openai/home`, `OCTET_OFFLINE=true`, `PATH=/usr/bin:/bin`, `TMPDIR=<work>/octet-b-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/octet-b-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/octet-b-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/octet-b-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/octet-b-print-write-kb50-openai/home/.local/state`
- **opencode-v2**: `BENCH_API_KEY=<dummy key>`, `HOME=<work>/opencode-v2-a-print-write-kb50-openai/home`, `OPENCODE_DISABLE_AUTOUPDATE=true`, `OPENCODE_DISABLE_MODELS_FETCH=true`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/opencode-v2-a-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/opencode-v2-a-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/opencode-v2-a-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/opencode-v2-a-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/opencode-v2-a-print-write-kb50-openai/home/.local/state`
- **opencode-v2-b**: `BENCH_API_KEY=<dummy key>`, `HOME=<work>/opencode-v2-b-print-write-kb50-openai/home`, `OPENCODE_DISABLE_AUTOUPDATE=true`, `OPENCODE_DISABLE_MODELS_FETCH=true`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `TMPDIR=<work>/opencode-v2-b-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/opencode-v2-b-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/opencode-v2-b-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/opencode-v2-b-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/opencode-v2-b-print-write-kb50-openai/home/.local/state`
- **pi-node**: `HOME=<work>/pi-node-a-print-write-kb50-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-rv9hptd4/arms/pi-node-a/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-a-print-write-kb50-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-a-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-a-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-a-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-a-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-a-print-write-kb50-openai/home/.local/state`
- **pi-node-b**: `HOME=<work>/pi-node-b-print-write-kb50-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-rv9hptd4/arms/pi-node-b/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-rv9hptd4/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-b-print-write-kb50-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-b-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-b-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-b-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-b-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-b-print-write-kb50-openai/home/.local/state`
- **rpi**: `HOME=<work>/rpi-a-print-write-kb50-openai/home`, `PATH=/usr/bin:/bin`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `RPI_CODING_AGENT_DIR=<work>/rpi-a-print-write-kb50-openai/home/.agent`, `RPI_DISABLE_UPDATE_CHECK=1`, `TMPDIR=<work>/rpi-a-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/rpi-a-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/rpi-a-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/rpi-a-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/rpi-a-print-write-kb50-openai/home/.local/state`
- **rpi-b**: `HOME=<work>/rpi-b-print-write-kb50-openai/home`, `PATH=/usr/bin:/bin`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `RPI_CODING_AGENT_DIR=<work>/rpi-b-print-write-kb50-openai/home/.agent`, `RPI_DISABLE_UPDATE_CHECK=1`, `TMPDIR=<work>/rpi-b-print-write-kb50-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/rpi-b-print-write-kb50-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/rpi-b-print-write-kb50-openai/home/.config`, `XDG_DATA_HOME=<work>/rpi-b-print-write-kb50-openai/home/.local/share`, `XDG_STATE_HOME=<work>/rpi-b-print-write-kb50-openai/home/.local/state`

### Runtime settings

Buffon pins CPUs but sets no runtime tuning of its own. An arm runs at its harness's shipped default except for the variables its manifest sets:

| arm | set by the manifest | left at the harness default |
|---|---|---|
| claude-code | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| codex | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| copilot | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| octet | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| opencode-v2 | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pi-node | `NODE_COMPILE_CACHE={install_dir}/node-compile-cache` | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| rpi | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |

---
*Quiet dedicated hardware: generated from 1 run directory by `buffon report`; 4 notes: aa_significant_fraction 5.4%, aa_gap_max 25.1%, aa_floor_max 700.4%, outlier_fraction 2.6%; the raw samples are in each directory's raw.json. The same data as report.html, report.json, summary.csv, rounds.csv, noise.csv and telemetry.csv.*
