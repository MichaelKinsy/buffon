# buffon report

**Trust: Dedicated** (host class A). adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-9) because their answer was clear; the 12-round minimum applies to the Verified badge; 8 measured rounds in the thinnest cell (the minimum for a headline is 12); uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare) Every measurement is recorded and shown whatever the label. Headline CPU metric: instructions.

**Run notes (7)**: aa_cv_cpu 3.3%, aa_significant_fraction 8.8%, aa_gap_max 156.7%, aa_floor_median 3.4%, aa_floor_max 167.7%, outlier_fraction 4.4%, foreign_cpu_p95 1.7% (usual ranges: docs/HEALTH.md)

> Every run in this report was on quiet dedicated hardware by the runner's own detection (docs/RUNNING.md, "Hardware label").

| field | value |
|---|---|
| reference arm | pi-node |
| arms | pi-bun, pi-node, pibolt, pig-0.4.1, pig-tip (each with an A/A copy `<id>-b` where the run had one) |
| runs | 1 |
| seed | 20261011 |
| token counts | the mock's usage: prompt tokens = request wire bytes / 4, completion tokens = one per streamed part + 12 per tool call; no tokenizer is pinned (METHODOLOGY section 3) |
| arms.lock sha256 | `549a3d2cc424cd316c5ff3072cf5c0c42bb1d6335775fd7289dd560254e35c33` |
| runner commit / tree | `5b3729fca2f0` / `3943ebd8df99` |
| run 1 | site `smc1-socket1` (local), 12 measured + 1 warm-up rounds, harness CPUs `48,49,50,51,112,113,114,115`, mock CPUs `52,116`, Intel(R) Xeon(R) Platinum 8462Y+, kernel 6.8.0-137-generic, meter cgroup-systemd; load before/after 1.4 / 1.1; calibration: CV 1.9% of cpu_ms (gate 5.0%) passed; hardware **quiet-dedicated**; host class **A**; isolation **uncontained, not comparable** |
| run 1 CPU cost | **instructions** (user and kernel instructions) are the headline CPU metric; CPU time (user + system) and wall time are separate cells |

## Run notes

7 notes: aa_cv_cpu 3.3%, aa_significant_fraction 8.8%, aa_gap_max 156.7%, aa_floor_median 3.4%, aa_floor_max 167.7%, outlier_fraction 4.4%, foreign_cpu_p95 1.7%. Run notes describe the conditions of the run. They do not grade it or change a number.

| check | value | usual range | status | meaning |
|---|---:|---:|---|---|
| A/A CV of CPU metrics, median over arms and cells | 3.3% | up to 2.0% | note | How much CPU time varies from round to round for one harness. Lower means a quieter host. streaming/tui-prose chat n10_settle_ms pi-bun: 300.0%; streaming/tui-prose chat n10_settle_ms pi-node: 300.0%; streaming/tui-prose chat n10_settle_ms pig-tip: 300.0% |
| A/A pairs with a significant gap (paired p < 0.05, before Holm) that is also larger than 1% | 8.8% | up to 5.0% | note | Share of harness and copy pairs that differ by more than 1% and also pass a significance test. A gap under 1% on a steady counter is not counted. About 5% can happen by chance. streaming/tui-prose chat n_first_paint_ms pi-node: 156.7%; streaming/tui-prose chat n_settle_ms pibolt: 25.7%; streaming/tui-prose chat peak_mem_mib pi-bun: 11.4% |
| A/A gap between a harness and its own copy, largest cell | 156.7% | up to 5.0% | note | The largest gap between a harness and its identical copy, and the cell where it happened. streaming/tui-prose chat n_first_paint_ms pi-node: 156.7%; streaming/tui-prose chat n_settle_ms pibolt: 25.7%; streaming/tui-prose chat peak_mem_mib pi-bun: 11.4% |
| A/A noise floor, median over scored cells | 3.4% | up to 3.0% | note | The smallest difference the identical copies cannot tell from noise, in the usual cell. Smaller differences than this are not resolved. streaming/tui-prose chat n10_first_paint_ms: 167.7%; streaming/tui-prose chat n_first_paint_ms: 163.3%; streaming/tui-prose chat n10_first_paint_ms: 155.3% |
| A/A noise floor, worst scored cell | 167.7% | up to 15.0% | note | The same floor in the noisiest cell. Comparisons in that cell resolve only larger differences. streaming/tui-prose chat n10_first_paint_ms: 167.7%; streaming/tui-prose chat n_first_paint_ms: 163.3%; streaming/tui-prose chat n10_first_paint_ms: 155.3% |
| Measured values flagged by the MAD rule | 4.4% | up to 2.0% | note | Share of measured values far from the median of their cell. Outliers are counted and never removed. streaming/tui-prose chat n10_first_paint_ms pig-0.4.1: 4; streaming/tui-prose chat n10_first_paint_ms pig-0.4.1-b: 4; streaming/tui-prose chat n10_settle_ms pig-tip-b: 4 |
| Foreign CPU on the pinned CPUs during a sample, p95 over samples, as a share of the sample's CPU time | 1.7% | up to 1.0% | note | CPU time that other processes used on the pinned cores during a sample, as a share of the sample's own CPU time (95th percentile). |
| Calibration: CV of the reference's CPU time between identical runs | 1.9% | up to 2.0% | ok | How much the reference's CPU time varied between identical calibration runs. Lower means a quieter host. |
| A/A gap between a harness and its own copy, median over cells | 0.5% | up to 1.0% | ok | The usual gap between a harness and its identical copy. A real difference between two harnesses should be larger than this. |
| Measured samples with at least one host flag | 0.6% | up to 5.0% | ok | Share of samples where the host showed a disturbance: throttling, foreign CPU, steal, a clock change, swap or a memory event. |
| Measured samples with CFS throttling (arm cgroup, every ancestor, session) | 0 | up to 0 | ok | Samples where the kernel held the process back for a CPU quota. Their time then describes the quota, not the harness. |
| Steal: share of the pinned CPUs' capacity taken by a hypervisor | 0.0% | up to 0.1% | ok | Share of the pinned CPUs' time that a hypervisor took away. It only matters on virtual machines. |
| Samples that waited more than 1 s for the host to quiet down | 0.0% | up to 1.0% | ok | Share of samples that had to wait for the quiet-host gate. A busy host makes the gate wait. |
| Samples for which the host never quieted down | 0 | up to 0 | ok | Samples that did not start because the host stayed busy. They are not in the numbers. |
| Effective clock: largest deviation of a sample's mean MHz from the run median | 0.1% | up to 2.0% | ok | How far a sample's mean CPU clock moved from the run median. A moving clock changes CPU time for the same work. |
| Infrastructure failures (envelope OOM, no process started, runner fault) over measured samples | 0.0% | up to 0.0% | ok | Share of samples that failed because of the host or the runner. They are never charged to a harness. |
| Arm failures over measured samples (a swarm ladder's designed stops are results and not counted) | 0.0% | up to 2.0% | ok | Share of samples where the harness itself failed. A scale sample that stopped because the kernel's limit was reached (stop_cause oom, pids or timeout) is a result and is in neither the failures nor the samples counted; a scale error stop is a failure. |
| Drift: median absolute change over the run of an arm's value, over cells | 0.8% | up to 2.0% | ok | How much a harness's value moved from the start of the run to the end. Drift means the host changed during the run. |
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

**Trust: Dedicated** (host class A). adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-9) because their answer was clear; the 12-round minimum applies to the Verified badge; 8 measured rounds in the thinnest cell (the minimum for a headline is 12); uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare)

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 7.

### Pi-faithful entries (faithfulness 90 or more)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

### Faithfulness not measured (ranked apart until it is)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pibolt (Pi-Bolt) | **93 (A)** | not measured | 1/9 (8 not run) | release archive; 267.5 MB; linux-x64 | 93-93 | 93-95, rank 1-2 |
| 2 | pig-tip (PiG 0.5.0) | **92 (A-)** | not measured | 1/9 (8 not run) | source build; 70.2 MB; linux-x64 | 91-92 | 92-97, rank 1-2 |
| 3 | pig-0.4.1 (PiG 0.4.1) | **73 (C)** | not measured | 1/9 (8 not run) | release archive; 63.8 MB; linux-x64 | 72-73 | 73-73, rank 3-3 |
| 4 | pi-bun (Pi on Bun) | **66 (D)** | not measured | 1/9 (8 not run) | release archive; 114.5 MB; linux-x64 | 65-66 | 62-66, rank 4-4 |

### Below the reference

- **pi-bun**: streaming 66 (D) at 1.34x the reference's cost

*Quiet dedicated hardware: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*


## Summary by axis

Counts of cells where the arm is measurably worse (loss), inconclusive, inside the A/A floor (no measurable difference) or measurably better (win) than the reference `pi-node`. A "cannot run" cell is never counted. Coverage is the cells the arm produced values for out of all cells in the report.

| arm | coverage | family | losses | inconclusive | no measurable difference | wins |
|---|---|---|---:|---:|---:|---:|
| pi-bun | 31/31 | streaming | 11 | 0 | 7 | 9 |
| pibolt | 31/31 | streaming | 2 | 0 | 1 | 8 |
| pig-0.4.1 | 31/31 | streaming | 8 | 0 | 8 | 11 |
| pig-tip † | 31/31 | streaming | 0 | 0 | 6 | 21 |

† `pig-tip`: This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

## pi-bun against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/tui-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 127 | 2,049 | 16.1 [15.8, 18.3] | 9.4% | 5.9% | 7.3% / 2.4% | 13.6 / 67.8 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/tui-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1045.58M | 16746.36M | 16.0 [15.7, 18.0] | 10.3% | 6.7% | 6.9% / 2.3% | 101,247,745 / 712,235,615 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | instructions | CPU | instructions | 9 | 20777.77M | 274661.28M | 13.2 [13.0, 14.6] | 7.9% | 5.0% | 5.4% / 2.2% | 1,640,315,253 / 10,290,816,815 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#instructions` |
| streaming/tui-prose | chat | cycles | CPU | cycles | 9 | 7927.96M | 96250.86M | 12.1 [11.8, 13.3] | 8.3% | 4.6% | 5.3% / 2.3% | 731,372,969 / 2,780,611,075 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cycles` |
| streaming/tui-prose | chat | cpu_ms | CPU | ms of CPU time | 9 | 2,850 | 34,511 | 12.1 [11.8, 13.3] | 8.2% | 4.6% | 5.3% / 2.3% | 260 / 1,000 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cpu_ms` |
| streaming/tui-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1400.12M | 9470.15M | 6.76 [6.57, 7.26] | 6.1% | 1.6% | 2.0% / 4.2% | 38,279,219 / 458,201,039 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 262 | 1,595 | 6.08 [5.93, 6.41] | 5.8% | 2.0% | 2.1% / 4.0% | 8.52 / 64.6 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/tui-prose | chat | n10_first_paint_ms | wall | ms | 9 | 8.17 | 12.1 | 1.48 [1.25, 1.71] | 34.2% | 57.0% | 31.4% / 3.9% | 2.01 / 0.767 | 1 / 0 | 0.0352 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_first_paint_ms` |
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 137 | 157 | 1.14 [1.05, 1.18] | 12.9% | 1.4% | 1.2% / 5.5% | 2.38 / 8.65 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.1 | 11.2 | 1.11 [1.02, 1.2] | 8.5% | 5.7% | 4.6% / 4.5% | 0.806 / 0.593 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 141 | 1.03 [1.02, 1.05] | 1.9% | 1.7% | 1.4% / 0.7% | 1.61 / 1.21 | 0 / 0 | 0.0312 | yes ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_peak_rss_mib` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#requests` |
| streaming/tui-prose | chat | n10_wall_ms | wall | ms | 9 | 46,103 | 45,316 | 0.983 [0.95, 1.02] | 3.6% | 1.9% | 2.1% / 2.6% | 1,635 / 1,842 | 0 / 0 | 0.117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_wall_ms` |
| streaming/tui-prose | chat | n_first_paint_ms | wall | ms | 9 | 8.34 | 11.6 | 1.39 [0.507, 1.46] | 163.3% | 72.1% | 51.6% / 2.3% | 13.9 / 0.127 | 4 / 0 | 1 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_first_paint_ms` |
| streaming/tui-prose | chat | n_wall_ms | wall | ms | 9 | 2,545 | 2,580 | 1.01 [0.962, 1.08] | 8.7% | 5.0% | 3.1% / 4.3% | 130 / 162 | 0 / 0 | 0.688 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_wall_ms` |
| streaming/tui-prose | chat | peak_mem_mib | memory | MiB | 9 | 113 | 133 | 1.18 [0.984, 1.22] | 18.3% | 13.1% | 10.2% / 4.5% | 16.8 / 4.39 | 2 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_mem_mib` |
| streaming/tui-prose | chat | peak_rss_mib | memory | MiB | 9 | 165 | 175 | 1.06 [0.934, 1.08] | 12.1% | 8.8% | 6.7% / 3.5% | 16.1 / 5.85 | 2 / 0 | 0.262 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_rss_mib` |
| streaming/tui-prose | chat | requests | wire | count | 9 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.28M | 44.77M | 0.825 [0.814, 0.83] | 2.8% | 0.4% | 0.2% / 1.6% | 171,273 / 436,320 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.6 | 56.6 | 0.826 [0.762, 0.883] | 17.7% | 5.3% | 3.7% / 9.0% | 0.725 / 4.94 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.8 | 29.5 | 0.529 [0.492, 0.573] | 13.1% | 1.5% | 1.0% / 6.7% | 0.298 / 2.41 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.86M | 91.18M | 0.32 [0.292, 0.323] | 9.7% | 0.5% | 0.3% / 4.5% | 1,047,346 / 2,921,176 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.6 | 23.9 | 0.446 [0.434, 0.46] | 7.7% | 2.1% | 2.0% / 4.5% | 1.19 / 0.588 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_wall_ms` |
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 11,812 | 0.978 [0.978, 0.978] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 5,906 | 0.978 [0.978, 0.978] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| streaming/tui-prose | chat | request_bytes | wire | bytes | 9 | 18,232 | 17,972 | 0.986 [0.986, 0.986] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0117 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes` |
| streaming/tui-prose | chat | request_bytes_per_turn | wire | bytes per turn | 9 | 9,116 | 8,986 | 0.986 [0.986, 0.986] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0117 | no exact |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes_per_turn` |

## pibolt against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 15,906 | 1.32 [1.32, 1.32] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 7,953 | 1.32 [1.32, 1.32] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.1 | 4.04 | 0.401 [0.385, 0.419] | 6.8% | 5.7% | 4.6% / 1.6% | 0.806 / 0.0129 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.28M | 19.74M | 0.364 [0.36, 0.365] | 1.2% | 0.4% | 0.2% / 1.1% | 171,273 / 268,988 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 137 | 95.9 | 0.698 [0.692, 0.709] | 1.9% | 1.4% | 1.2% / 0.2% | 2.38 / 0.169 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.6 | 37.1 | 0.542 [0.536, 0.548] | 4.7% | 5.3% | 3.7% / 0.6% | 0.725 / 0.333 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.8 | 6.01 | 0.108 [0.107, 0.109] | 6.3% | 1.5% | 1.0% / 1.5% | 0.298 / 0.107 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.86M | 19.64M | 0.0689 [0.0685, 0.0696] | 1.5% | 0.5% | 0.3% / 1.1% | 1,047,346 / 196,998 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 78.5 | 0.575 [0.57, 0.583] | 1.9% | 1.7% | 1.4% / 0.2% | 1.61 / 0.138 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.6 | 6.22 | 0.116 [0.114, 0.119] | 8.8% | 2.1% | 2.0% / 1.8% | 1.19 / 0.087 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_wall_ms` |

### Different work: not compared (the arm's own account; its median is shown, no ratio)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/tui-prose | chat | cpu_ms | CPU | ms of CPU time | 9 | 2,850 | 925 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 4.6% | 5.3% / 2.7% | 260 / 33.8 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cpu_ms` |
| streaming/tui-prose | chat | cycles | CPU | cycles | 9 | 7927.96M | 2511.50M | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 4.6% | 5.3% / 2.7% | 731,372,969 / 93,673,830 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cycles` |
| streaming/tui-prose | chat | instructions | CPU | instructions | 9 | 20777.77M | 4798.64M | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 5.0% | 5.4% / 1.4% | 1,640,315,253 / 67,956,601 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#instructions` |
| streaming/tui-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 127 | 54.1 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 5.9% | 7.3% / 3.1% | 13.6 / 1.9 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/tui-prose | chat | n10_first_paint_ms | wall | ms | 9 | 8.17 | 11.7 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 57.0% | 31.4% / 28.2% | 2.01 / 0.938 | 1 / 3 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_first_paint_ms` |
| streaming/tui-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1045.58M | 281.22M | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 6.7% | 6.9% / 1.7% | 101,247,745 / 5,277,921 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | n10_settle_ms | wall | ms | 9 | 0 | 0 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | n/a | 300.0% / 198.4% | 0 / 0 | 1 / 2 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_settle_ms` |
| streaming/tui-prose | chat | n10_wall_ms | wall | ms | 9 | 46,103 | 37,848 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 1.9% | 2.1% / 2.3% | 1,635 / 1,681 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_wall_ms` |
| streaming/tui-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 262 | 31.9 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 2.0% | 2.1% / 3.4% | 8.52 / 0.971 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/tui-prose | chat | n_first_paint_ms | wall | ms | 9 | 8.34 | 14.1 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 72.1% | 51.6% / 0.4% | 13.9 / 0.0276 | 4 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_first_paint_ms` |
| streaming/tui-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1400.12M | 181.56M | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 1.6% | 2.0% / 1.8% | 38,279,219 / 2,589,595 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | n_settle_ms | wall | ms | 9 | 0 | 21.3 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | n/a | 264.4% / 17.3% | 0 / 4.87 | 2 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_settle_ms` |
| streaming/tui-prose | chat | n_wall_ms | wall | ms | 9 | 2,545 | 1,907 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 5.0% | 3.1% / 2.6% | 130 / 64.3 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_wall_ms` |
| streaming/tui-prose | chat | peak_mem_mib | memory | MiB | 9 | 113 | 35.8 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 13.1% | 10.2% / 0.6% | 16.8 / 0.234 | 2 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_mem_mib` |
| streaming/tui-prose | chat | peak_rss_mib | memory | MiB | 9 | 165 | 110 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 8.8% | 6.7% / 0.1% | 16.1 / 0.152 | 2 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_rss_mib` |
| streaming/tui-prose | chat | request_bytes | wire | bytes | 9 | 18,232 | 22,066 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes` |
| streaming/tui-prose | chat | request_bytes_per_turn | wire | bytes per turn | 9 | 9,116 | 11,033 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes_per_turn` |
| streaming/tui-prose | chat | requests | wire | count | 9 | 2 | 2 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#requests` |
| streaming/tui-prose | chat | side_requests | wire | count | 9 | 0 | 0 | different work: not compared (Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed) | n/a | n/a | n/a / n/a | 0 / 0 | 0 / 0 | n/a | n/a | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#side_requests` |

## pig-0.4.1 against pi-node

### Losses (measurably worse than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.6 | 143 | 2.08 [2.06, 2.12] | 4.7% | 5.3% | 3.7% / 1.5% | 0.725 / 2.09 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.1 | 19.6 | 1.95 [1.86, 2.06] | 6.8% | 5.7% | 4.6% / 2.1% | 0.806 / 0.455 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.28M | 99.09M | 1.83 [1.8, 1.84] | 1.7% | 0.4% | 0.2% / 1.1% | 171,273 / 1,653,134 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 127 | 140 | 1.1 [1.05, 1.29] | 9.8% | 5.9% | 7.3% / 6.1% | 13.6 / 10.4 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 12,122 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 6,061 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| streaming/tui-prose | chat | request_bytes | wire | bytes | 9 | 18,232 | 18,262 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0117 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes` |
| streaming/tui-prose | chat | request_bytes_per_turn | wire | bytes per turn | 9 | 9,116 | 9,131 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0117 | no exact |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#requests` |
| streaming/tui-prose | chat | instructions | CPU | instructions | 9 | 20777.77M | 18884.65M | 0.909 [0.89, 1.04] | 10.6% | 5.0% | 5.4% / 6.6% | 1,640,315,253 / 1,433,592,902 | 0 / 0 | 0.168 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#instructions` |
| streaming/tui-prose | chat | n10_first_paint_ms | wall | ms | 9 | 8.17 | 10.5 | 1.29 [1.04, 1.53] | 167.7% | 57.0% | 31.4% / 28.3% | 2.01 / 1.01 | 1 / 4 | 0.977 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_first_paint_ms` |
| streaming/tui-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1045.58M | 1115.35M | 1.07 [1.04, 1.26] | 12.2% | 6.7% | 6.9% / 7.4% | 101,247,745 / 98,928,463 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | n10_wall_ms | wall | ms | 9 | 46,103 | 46,790 | 1.01 [0.992, 1.07] | 3.5% | 1.9% | 2.1% / 2.0% | 1,635 / 1,369 | 0 / 0 | 0.117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_wall_ms` |
| streaming/tui-prose | chat | n_first_paint_ms | wall | ms | 9 | 8.34 | 12.6 | 1.51 [0.553, 1.65] | 163.3% | 72.1% | 51.6% / 4.0% | 13.9 / 1.05 | 4 / 3 | 1 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_first_paint_ms` |
| streaming/tui-prose | chat | n_wall_ms | wall | ms | 9 | 2,545 | 2,684 | 1.05 [0.979, 1.14] | 12.4% | 5.0% | 3.1% / 7.1% | 130 / 269 | 0 / 0 | 0.258 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_wall_ms` |
| streaming/tui-prose | chat | requests | wire | count | 9 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#requests` |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 137 | 48.7 | 0.355 [0.352, 0.36] | 1.9% | 1.4% | 1.2% / 0.5% | 2.38 / 0.357 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.8 | 19.8 | 0.355 [0.342, 0.363] | 11.4% | 1.5% | 1.0% / 4.1% | 0.298 / 0.848 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.86M | 87.72M | 0.308 [0.301, 0.311] | 14.2% | 0.5% | 0.3% / 5.5% | 1,047,346 / 2,670,123 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 40.9 | 0.3 [0.297, 0.304] | 1.9% | 1.7% | 1.4% / 0.5% | 1.61 / 0.324 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.6 | 15.9 | 0.297 [0.29, 0.303] | 5.7% | 2.1% | 2.0% / 2.1% | 1.19 / 0.242 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_wall_ms` |
| streaming/tui-prose | chat | cpu_ms | CPU | ms of CPU time | 9 | 2,850 | 2,451 | 0.86 [0.823, 0.956] | 8.3% | 4.6% | 5.3% / 5.3% | 260 / 152 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cpu_ms` |
| streaming/tui-prose | chat | cycles | CPU | cycles | 9 | 7927.96M | 6600.19M | 0.833 [0.796, 0.924] | 8.6% | 4.6% | 5.3% / 5.5% | 731,372,969 / 423,348,355 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cycles` |
| streaming/tui-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 262 | 127 | 0.486 [0.478, 0.51] | 9.1% | 2.0% | 2.1% / 3.9% | 8.52 / 5.06 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/tui-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1400.12M | 904.33M | 0.646 [0.626, 0.662] | 6.0% | 1.6% | 2.0% / 3.7% | 38,279,219 / 30,961,859 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | peak_mem_mib | memory | MiB | 9 | 113 | 37.3 | 0.331 [0.275, 0.34] | 18.3% | 13.1% | 10.2% / 1.7% | 16.8 / 0.68 | 2 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_mem_mib` |
| streaming/tui-prose | chat | peak_rss_mib | memory | MiB | 9 | 165 | 68.8 | 0.418 [0.371, 0.425] | 12.1% | 8.8% | 6.7% / 1.3% | 16.1 / 1.28 | 2 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_rss_mib` |

## pig-tip against pi-node

> **Read this first:** This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

### Losses (measurably worse than the reference)

None.

### No measurable difference (inside the A/A floor)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| streaming/print-prose | chat | requests | wire | count | 8 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#requests` | 1 [1, 1] no measurable difference |
| streaming/tui-prose | chat | n10_first_paint_ms | wall | ms | 9 | 8.17 | 11.6 | 1.41 [1.25, 1.67] | 155.3% | 57.0% | 31.4% / 29.2% | 2.01 / 0.143 | 1 / 3 | 0.922 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_first_paint_ms` | 1.1 [1.08, 1.35] no measurable difference |
| streaming/tui-prose | chat | n10_wall_ms | wall | ms | 9 | 46,103 | 47,153 | 1.02 [1.01, 1.06] | 6.0% | 1.9% | 2.1% / 3.9% | 1,635 / 1,953 | 0 / 0 | 0.117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_wall_ms` | 1.01 [0.986, 1.06] no measurable difference |
| streaming/tui-prose | chat | n_first_paint_ms | wall | ms | 9 | 8.34 | 14.6 | 1.75 [0.642, 1.79] | 163.3% | 72.1% | 51.6% / 2.2% | 13.9 / 0.0104 | 4 / 3 | 1 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_first_paint_ms` | 1.16 [1.07, 1.16] loss |
| streaming/tui-prose | chat | n_wall_ms | wall | ms | 9 | 2,545 | 2,616 | 1.03 [0.984, 1.04] | 8.7% | 5.0% | 3.1% / 1.8% | 130 / 29.9 | 0 / 1 | 0.688 | yes ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_wall_ms` | 0.975 [0.916, 1.01] no measurable difference |
| streaming/tui-prose | chat | requests | wire | count | 9 | 2 | 2 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#requests` | 1 [1, 1] no measurable difference |

### Wins (measurably better than the reference)

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 10.1 | 2.6 | 0.259 [0.248, 0.27] | 6.8% | 5.7% | 4.6% / 3.0% | 0.806 / 0.0771 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` | 0.133 [0.129, 0.138] win |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 54.28M | 15.90M | 0.293 [0.266, 0.293] | 8.1% | 0.4% | 0.2% / 5.2% | 171,273 / 1,088,471 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` | 0.16 [0.147, 0.162] win |
| streaming/print-prose | chat | n10_peak_rss_mib | memory | MiB | 8 | 137 | 43.3 | 0.315 [0.313, 0.32] | 1.9% | 1.4% | 1.2% / 0.5% | 2.38 / 0.185 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_peak_rss_mib` | 0.888 [0.882, 0.893] win |
| streaming/print-prose | chat | n10_wall_ms | wall | ms | 8 | 68.6 | 32.2 | 0.47 [0.465, 0.474] | 4.7% | 5.3% | 3.7% / 0.7% | 0.725 / 0.279 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_wall_ms` | 0.225 [0.222, 0.228] win |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 8 | 55.8 | 3.61 | 0.0648 [0.0632, 0.0666] | 6.8% | 1.5% | 1.0% / 3.0% | 0.298 / 0.159 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` | 0.182 [0.175, 0.194] win |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 8 | 284.86M | 14.11M | 0.0495 [0.0461, 0.0498] | 7.0% | 0.5% | 0.3% / 4.4% | 1,047,346 / 792,514 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` | 0.161 [0.15, 0.166] win |
| streaming/print-prose | chat | n_peak_rss_mib | memory | MiB | 8 | 137 | 6.97 | 0.0511 [0.0503, 0.0526] | 5.5% | 1.7% | 1.4% / 1.9% | 1.61 / 0.203 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_peak_rss_mib` | 0.17 [0.169, 0.175] win |
| streaming/print-prose | chat | n_wall_ms | wall | ms | 8 | 53.6 | 4.41 | 0.0823 [0.0802, 0.0857] | 7.1% | 2.1% | 2.0% / 3.4% | 1.19 / 0.13 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_wall_ms` | 0.277 [0.27, 0.287] win |
| streaming/print-prose | chat | request_bytes | wire | bytes | 8 | 12,072 | 12,046 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes` | 0.994 [0.994, 0.994] win |
| streaming/print-prose | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,036 | 6,023 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes_per_turn` | 0.994 [0.994, 0.994] win |
| streaming/tui-prose | chat | cpu_ms | CPU | ms of CPU time | 9 | 2,850 | 403 | 0.141 [0.136, 0.153] | 8.2% | 4.6% | 5.3% / 2.0% | 260 / 7.49 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cpu_ms` | 0.164 [0.155, 0.175] win |
| streaming/tui-prose | chat | cycles | CPU | cycles | 9 | 7927.96M | 990.07M | 0.125 [0.12, 0.135] | 8.3% | 4.6% | 5.3% / 2.2% | 731,372,969 / 27,015,354 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cycles` | 0.15 [0.141, 0.16] win |
| streaming/tui-prose | chat | instructions | CPU | instructions | 9 | 20777.77M | 2042.67M | 0.0983 [0.0975, 0.108] | 7.9% | 5.0% | 5.4% / 1.4% | 1,640,315,253 / 43,902,562 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#instructions` | 0.108 [0.101, 0.117] win |
| streaming/tui-prose | chat | n10_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 127 | 19.8 | 0.156 [0.153, 0.176] | 9.4% | 5.9% | 7.3% / 2.8% | 13.6 / 0.694 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_cpu_ms_per_1k_tokens` | 0.142 [0.132, 0.154] win |
| streaming/tui-prose | chat | n10_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1045.58M | 100.55M | 0.0962 [0.0945, 0.108] | 10.3% | 6.7% | 6.9% / 2.0% | 101,247,745 / 3,167,255 | 0 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_instructions_per_1k_tokens` | 0.0902 [0.0826, 0.099] win |
| streaming/tui-prose | chat | n_cpu_ms_per_1k_tokens | CPU | ms of CPU time per 1k tokens | 9 | 262 | 29.7 | 0.113 [0.111, 0.117] | 4.5% | 2.0% | 2.1% / 3.6% | 8.52 / 0.475 | 0 / 1 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_cpu_ms_per_1k_tokens` | 0.233 [0.218, 0.241] win |
| streaming/tui-prose | chat | n_instructions_per_1k_tokens | CPU | instructions per 1k tokens | 9 | 1400.12M | 152.20M | 0.109 [0.1, 0.112] | 8.1% | 1.6% | 2.0% / 6.6% | 38,279,219 / 1,279,493 | 0 / 3 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_instructions_per_1k_tokens` | 0.168 [0.152, 0.174] win |
| streaming/tui-prose | chat | peak_mem_mib | memory | MiB | 9 | 113 | 18.0 | 0.16 [0.131, 0.164] | 18.3% | 13.1% | 10.2% / 5.1% | 16.8 / 0.484 | 2 / 0 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_mem_mib` | 0.482 [0.47, 0.495] win |
| streaming/tui-prose | chat | peak_rss_mib | memory | MiB | 9 | 165 | 56.8 | 0.345 [0.301, 0.35] | 12.1% | 8.8% | 6.7% / 1.4% | 16.1 / 0.305 | 2 / 1 | 0.0117 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_rss_mib` | 0.825 [0.811, 0.832] win |
| streaming/tui-prose | chat | request_bytes | wire | bytes | 9 | 18,232 | 18,186 | 0.997 [0.997, 0.997] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0117 | n/a |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes` | 0.996 [0.996, 0.996] win |
| streaming/tui-prose | chat | request_bytes_per_turn | wire | bytes per turn | 9 | 9,116 | 9,093 | 0.997 [0.997, 0.997] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0117 | no exact |  | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes_per_turn` | 0.996 [0.996, 0.996] win |

## pig-tip against its previous arm pig-0.4.1: 0.4.1 → 0.5.0 (newer / previous)

`pig-0.4.1` is the earlier arm and `pig-tip` the later one (declared as `previous` in the manifest; a loss means the later arm is measurably worse, a win measurably better). The floor is the larger of the two arms' A/A floors; a ratio inside it is no measurable difference.

| workload | api | metric | pig-0.4.1 median | pig-tip median | ratio [95% CI] | A/A floor | verdict |
|---|---|---|---:|---:|---|---:|---|
| streaming/tui-prose | chat | n_first_paint_ms | 12.6 | 14.6 | 1.16 [1.07, 1.16] | 8.7% | **loss** |
| streaming/print-prose | chat | requests | 2 | 2 | 1 [1, 1] | 0.0% | **no measurable difference** |
| streaming/tui-prose | chat | n10_first_paint_ms | 10.5 | 11.6 | 1.1 [1.08, 1.35] | 167.7% | **no measurable difference** |
| streaming/tui-prose | chat | n10_wall_ms | 46,790 | 47,153 | 1.01 [0.986, 1.06] | 6.0% | **no measurable difference** |
| streaming/tui-prose | chat | n_wall_ms | 2,684 | 2,616 | 0.975 [0.916, 1.01] | 12.4% | **no measurable difference** |
| streaming/tui-prose | chat | requests | 2 | 2 | 1 [1, 1] | 0.0% | **no measurable difference** |
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | 19.6 | 2.6 | 0.133 [0.129, 0.138] | 5.5% | **win** |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | 99.09M | 15.90M | 0.16 [0.147, 0.162] | 8.1% | **win** |
| streaming/print-prose | chat | n10_peak_rss_mib | 48.7 | 43.3 | 0.888 [0.882, 0.893] | 0.8% | **win** |
| streaming/print-prose | chat | n10_wall_ms | 143 | 32.2 | 0.225 [0.222, 0.228] | 2.5% | **win** |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | 19.8 | 3.61 | 0.182 [0.175, 0.194] | 11.4% | **win** |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | 87.72M | 14.11M | 0.161 [0.15, 0.166] | 14.2% | **win** |
| streaming/print-prose | chat | n_peak_rss_mib | 40.9 | 6.97 | 0.17 [0.169, 0.175] | 5.5% | **win** |
| streaming/print-prose | chat | n_wall_ms | 15.9 | 4.41 | 0.277 [0.27, 0.287] | 7.1% | **win** |
| streaming/print-prose | chat | request_bytes | 12,122 | 12,046 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| streaming/print-prose | chat | request_bytes_per_turn | 6,061 | 6,023 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| streaming/tui-prose | chat | cpu_ms | 2,451 | 403 | 0.164 [0.155, 0.175] | 8.3% | **win** |
| streaming/tui-prose | chat | cycles | 6600.19M | 990.07M | 0.15 [0.141, 0.16] | 8.6% | **win** |
| streaming/tui-prose | chat | instructions | 18884.65M | 2042.67M | 0.108 [0.101, 0.117] | 10.6% | **win** |
| streaming/tui-prose | chat | n10_cpu_ms_per_1k_tokens | 140 | 19.8 | 0.142 [0.132, 0.154] | 9.8% | **win** |
| streaming/tui-prose | chat | n10_instructions_per_1k_tokens | 1115.35M | 100.55M | 0.0902 [0.0826, 0.099] | 12.2% | **win** |
| streaming/tui-prose | chat | n_cpu_ms_per_1k_tokens | 127 | 29.7 | 0.233 [0.218, 0.241] | 9.1% | **win** |
| streaming/tui-prose | chat | n_instructions_per_1k_tokens | 904.33M | 152.20M | 0.168 [0.152, 0.174] | 8.1% | **win** |
| streaming/tui-prose | chat | peak_mem_mib | 37.3 | 18.0 | 0.482 [0.47, 0.495] | 4.9% | **win** |
| streaming/tui-prose | chat | peak_rss_mib | 68.8 | 56.8 | 0.825 [0.811, 0.832] | 3.2% | **win** |
| streaming/tui-prose | chat | request_bytes | 18,262 | 18,186 | 0.996 [0.996, 0.996] | 0.0% | **win** |
| streaming/tui-prose | chat | request_bytes_per_turn | 9,131 | 9,093 | 0.996 [0.996, 0.996] | 0.0% | **win** |

## A/A noise floor

Each arm's A/A copy `<id>-b` is the same executable run in the same rounds. The floor of a cell is the largest deviation from 1 the copy's ratio-of-medians interval allows; a difference between arms smaller than the floor is reported as no measurable difference. The table gives, per arm and workload, the median and the maximum floor over the scored metrics, and the reference's minimum detectable effect at 80% power.

| arm | workload | api | cells | median floor | max floor | worst metric |
|---|---|---|---:|---:|---:|---|
| pi-bun | streaming/print-prose | chat | 11 | 7.7% | 17.7% | n10_wall_ms |
| pi-bun | streaming/tui-prose | chat | 16 | 6.9% | 34.2% | n10_first_paint_ms |
| pi-node | streaming/print-prose | chat | 11 | 1.9% | 6.8% | n10_cpu_ms_per_1k_tokens |
| pi-node | streaming/tui-prose | chat | 16 | 8.3% | 163.3% | n_first_paint_ms |
| pibolt | streaming/print-prose | chat | 11 | 1.2% | 8.8% | n_wall_ms |
| pibolt | streaming/tui-prose | chat | 17 | 2.9% | 55.6% | n_settle_ms |
| pig-0.4.1 | streaming/print-prose | chat | 11 | 1.7% | 14.2% | n_instructions_per_1k_tokens |
| pig-0.4.1 | streaming/tui-prose | chat | 16 | 8.6% | 167.7% | n10_first_paint_ms |
| pig-tip | streaming/print-prose | chat | 11 | 5.5% | 8.1% | n10_instructions_per_1k_tokens |
| pig-tip | streaming/tui-prose | chat | 16 | 3.6% | 155.3% | n10_first_paint_ms |

Minimum detectable effect of the reference's A/A pair over all cells: median 2.0%, worst 72.1%. A difference smaller than the cell's MDE cannot be seen in this run.

## Cell ids and rerun commands

Every cell has an id, `<run id>::<workload>@<api>#<metric>`. `python3 -m buffon rerun <cell id> --site <your site profile>` repeats the plan of the run that holds the cell (its arms, rounds, seed and parameters) for that workload and API only, on your host, and compares your result with the original. The raw samples of every cell are in the run directory's raw.json; this report is generated from them and from nothing else, and `buffon verify` regenerates it to check that no number was edited.

| workload | api | metric | cell id |
|---|---|---|---|
| streaming/print-prose | chat | n10_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n10_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n10_peak_rss_mib | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_peak_rss_mib` |
| streaming/print-prose | chat | n10_wall_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n10_wall_ms` |
| streaming/print-prose | chat | n_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/print-prose | chat | n_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/print-prose | chat | n_peak_rss_mib | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_peak_rss_mib` |
| streaming/print-prose | chat | n_wall_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#n_wall_ms` |
| streaming/print-prose | chat | request_bytes | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes` |
| streaming/print-prose | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#request_bytes_per_turn` |
| streaming/print-prose | chat | requests | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#requests` |
| streaming/print-prose | chat | side_requests | `2026-10-19-smc1-launch-focus-streaming::streaming/print-prose@openai-completions#side_requests` |
| streaming/tui-prose | chat | cpu_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cpu_ms` |
| streaming/tui-prose | chat | cycles | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#cycles` |
| streaming/tui-prose | chat | instructions | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#instructions` |
| streaming/tui-prose | chat | n10_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_cpu_ms_per_1k_tokens` |
| streaming/tui-prose | chat | n10_first_paint_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_first_paint_ms` |
| streaming/tui-prose | chat | n10_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | n10_settle_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_settle_ms` |
| streaming/tui-prose | chat | n10_wall_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n10_wall_ms` |
| streaming/tui-prose | chat | n_cpu_ms_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_cpu_ms_per_1k_tokens` |
| streaming/tui-prose | chat | n_first_paint_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_first_paint_ms` |
| streaming/tui-prose | chat | n_instructions_per_1k_tokens | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_instructions_per_1k_tokens` |
| streaming/tui-prose | chat | n_settle_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_settle_ms` |
| streaming/tui-prose | chat | n_wall_ms | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#n_wall_ms` |
| streaming/tui-prose | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_mem_mib` |
| streaming/tui-prose | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#peak_rss_mib` |
| streaming/tui-prose | chat | request_bytes | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes` |
| streaming/tui-prose | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#request_bytes_per_turn` |
| streaming/tui-prose | chat | requests | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#requests` |
| streaming/tui-prose | chat | side_requests | `2026-10-19-smc1-launch-focus-streaming::streaming/tui-prose@openai-completions#side_requests` |

## Noise report

How noisy this run was, from its own samples and the telemetry taken around each one (docs/TELEMETRY.md). The A/A figures compare each arm with its own identical copy, so they show what the host does to two runs of the same executable.

### Per metric

| metric | cells | A/A gap median | A/A gap worst | A/A floor median | A/A floor worst | CV median | CV worst | outliers / values | drift median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cpu_ms | 1 | 1.2% | 2.4% | 6.9% | 8.3% | 3.3% | 7.8% | 0 / 90 | 0.8% |
| cycles | 1 | 1.1% | 2.6% | 6.9% | 8.6% | 3.3% | 8.0% | 0 / 90 | 1.6% |
| instructions | 1 | 1.7% | 3.9% | 7.0% | 10.6% | 2.4% | 9.6% | 0 / 90 | 2.2% |
| n10_cpu_ms_per_1k_tokens | 2 | 0.7% | 3.2% | 6.2% | 9.8% | 3.0% | 8.8% | 2 / 170 | 1.8% |
| n10_first_paint_ms | 1 | 0.3% | 6.6% | 34.2% | 167.7% | 28.2% | 40.6% | 20 / 90 | 1.6% |
| n10_instructions_per_1k_tokens | 2 | 0.5% | 4.8% | 3.1% | 12.2% | 1.8% | 10.7% | 4 / 170 | 1.0% |
| n10_peak_rss_mib | 1 | 0.5% | 0.7% | 0.8% | 12.9% | 0.7% | 6.0% | 0 / 80 | 0.5% |
| n10_settle_ms | 1 | n/a | n/a | n/a | n/a | 300.0% | 300.0% | 15 / 90 | n/a |
| n10_wall_ms | 2 | 0.8% | 2.9% | 3.4% | 17.7% | 2.1% | 9.0% | 2 / 170 | 1.1% |
| n_cpu_ms_per_1k_tokens | 2 | 2.0% | 3.9% | 6.0% | 13.1% | 3.5% | 9.0% | 1 / 170 | 2.5% |
| n_first_paint_ms | 1 | 0.6% | 156.7% | 6.8% | 163.3% | 3.7% | 51.6% | 20 / 90 | 0.6% |
| n_instructions_per_1k_tokens | 2 | 0.3% | 2.6% | 6.1% | 14.2% | 2.5% | 7.3% | 12 / 170 | 1.3% |
| n_peak_rss_mib | 1 | 0.9% | 1.4% | 1.2% | 5.5% | 0.8% | 2.2% | 1 / 80 | 0.6% |
| n_settle_ms | 1 | 25.7% | 25.7% | 55.6% | 55.6% | 199.8% | 264.4% | 17 / 90 | 0.6% |
| n_wall_ms | 2 | 1.8% | 5.9% | 6.6% | 12.4% | 2.6% | 7.1% | 4 / 170 | 1.8% |
| peak_mem_mib | 1 | 2.4% | 11.4% | 4.9% | 18.3% | 3.4% | 11.3% | 9 / 90 | 1.5% |
| peak_rss_mib | 1 | 1.0% | 8.1% | 3.2% | 12.1% | 1.3% | 7.5% | 10 / 90 | 1.5% |
| request_bytes | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 170 | 0.0% |
| request_bytes_per_turn | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 170 | 0.0% |
| requests | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 170 | 0.0% |
| side_requests | 2 | n/a | n/a | n/a | n/a | n/a | n/a | 0 / 170 | n/a |

A/A gap: the copy's median against the arm's, per cell. A/A floor: the largest deviation from 1 the copy's ratio interval allows (METHODOLOGY section 6). CV: the standard deviation of an arm's rounds over their mean. Outliers: a measured value is an outlier when |x - median| > 5 x 1.4826 x MAD of its arm's values in that cell (needs 4 values; with MAD 0, any different value). Outliers are counted, never removed. Drift: the Theil-Sen trend of an arm's rounds times the rounds spanned, as a share of its median.

### Run 1

- Samples: 170 measured (170 ok, 0 failed), 20 warm-up; telemetry on 170 of 170 ok samples. Sources read: cgroup_throttle, cpufreq, loadavg, meminfo, pressure, proc_stat, schedstat, thermal_throttle, vmstat.
- Calibration: CV 1.9% of cpu_ms on pi-node (gate 5.0%), passed.
- CFS throttling: 0 samples, 0 us in all; the session's cgroup lost 0 us over the whole run.
- Quiet-host gate: 170 passed at once, 0 waited (longest 0.0 s, 0.0 s in all), 0 gave up.
- Steal: 0.000% of the pinned CPUs' capacity. Foreign CPU on the pinned CPUs: p95 1.7% of the sample's CPU time. Clock: largest deviation 0.1% from the median 2800 MHz. iowait is recorded in every sample and never gated.
- Failed samples: 0 arm, 0 infrastructure (the arm is not charged for those); 0 ladder stops (a swarm rung that hit the kernel's limit: a result, not a failure). CPU quota on the arm cgroup or an ancestor: none.
- Flagged samples: 1 of 170 (clock_moved 1).
- Telemetry cost: the collector's thread used 220.18 ms median per sample (worst 289.54 ms), on the runner's CPUs, outside the pinned set.
- Host load before / after: 1.4 / 1.1; pinned CPUs busy over the run: mean 2.2%, max 16.6%.

Flagged samples (kept in the statistics unless the report is made with `--drop-flagged`; the first 1 of 1):

| arm | workload | api | round | flags |
|---|---|---|---:|---|
| pi-node-b | streaming/tui-prose | openai-completions | 8 | clock_moved |

### Do the flagged rounds change the answer?

The report was built again without the 1 flagged rounds: 2 of 111 comparisons change verdict.

| workload | api | metric | arm | with flagged rounds | without |
|---|---|---|---|---|---|
| streaming/tui-prose | openai-completions | instructions | pig-0.4.1 | no measurable difference | win |
| streaming/tui-prose | openai-completions | n10_first_paint_ms | pi-bun | loss | inconclusive (paired test p 0.07 >= 0.05) |

### Samples and rounds not in the statistics

| reason | samples | rounds |
|---|---:|---:|
| warm-up round (kept in the raw data, excluded from the statistics by rule) | 20 | 1 |

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

None.

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
| pi-bun | 1.3.0 | https://github.com/earendil-works/pi/releases/download/v1.3.0/pi-linux-x64.tar.gz | artifact_sha256 `24f5be328b66d4da36876296989501974f43ab8434fbb57c35c523a3ea505ded` | linux-x64 | `c88c8ca00f64b4f9ea566de62b8a6d8826ef41f96a733e592e84bbc300c7ac6a` | `c2415d6e6f7c67b0a55744c5ace5054936e252fcc3cf56ce087bc314061315ca` |
| pi-node | 1.3.0 | @earendil-works/pi-coding-agent@1.3.0 | integrity `sha512-V/WoCjA2hQSe3QLWIUB24cTRdtEdeLiIzkDqU5RMXV6VWuD+KGZnzVBMhglwdnQTySkehZsjt8a3g6Jd2g4nnw==`<br>package_lock_sha256 `65eacda789c30e1c3859a96eee2fd53cf4a18629d27dcf2aa6d7bdb3da02d719` | node 24.19.0; linux-x64 | `17662e8cd8bd784c3f3dd8a8b4e0864387babb4075d66aa52a60b3b02ba56457` | `e79626f2dd6f94aa45d30f3fa63cd84319a6eefcd150b353cfaf274366926774` |
| pibolt | 0.9.3 | https://github.com/opensec-git/Pi-Bolt/releases/download/bolt-v0.9.3/pi-bolt-linux-x64.tar.gz | artifact_sha256 `333f44ab2a1f602dbeb36228927bcafabd3e132da32be1d6a7deb54bd09e90ce` | linux-x64 | `db1434d8b8ede5b781e9b6cbb7f166bf33c5f8ec6592d3f11e8ebfd3b0047227` | `fe2572130b036a6981b2dcedf3e96e464dcd1749953c9bec47fc8353f0a66c1e` |
| pig-0.4.1 | 0.4.1 | https://github.com/MichaelKinsy/PiG/releases/download/v0.4.1/pig-0.4.1-linux-amd64.tar.gz | artifact_sha256 `3b4de3587cbfb617def483ec62dddcf35827acc3436b1454cc5694c22dcdaf3f` | linux-x64 | `a51378256ee5fdb0af8f190268b7b5e3f6c0d19da03d90b607eaa70efd58a161` | `110ab2ece63f0ac5a70b6bd8901ff0c740ab7172ecbeef33e94aa95e213c7179` |
| pig-tip | 0.5.0+1.3.0 | git 26eaad58e3ec09e25adf74000f79bcd83123aa8c | tree `8b867e1919867ebfc99e50c7a630f27f0ce9be30` | go build -buildvcs=false -trimpath -ldflags -s -w -X github.com/MichaelKinsy/PiG/coding/cli.Build=26eaad58e3ec09e25adf74000f79bcd83123aa8c -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateURL=https://github.com/MichaelKinsy/PiG/releases/latest/download/update.json -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateTrustRoot=LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUNvd0JRWURLMlZ3QXlFQVFBdUtJTHRmc0FpbWdabnRpZ2UydzRGRy9QeDFQeU5HampHYXlEalREM0k9Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQo= -X github.com/MichaelKinsy/PiG/coding/pigletbuild.releaseSourceVersion=v0.5.0 -o /local/kinsy/arena/home/work/buffon-81l289nz/arms/pig-tip-a/bin/pig ./cmd/pig; toolchain go 1.27.2; linux-x64 | `d0032cdda0e713436aa3f6930bb5cac18491bdd91011ffa362100c5bd6b4526f` | `cc759dbd134406f976bb90fbb8fe5a0c3dc4d76a83b7de26d731daa6ef982b21` |

## Arms and environment

| arm | version | version line | executable sha256 | footprint | install | licence |
|---|---|---|---|---|---|---|
| pi-bun | 1.3.0 | 1.3.0 | `c2415d6e6f7c67b0` | 114.5 MB | release archive (https://github.com/earendil-works/pi/releases/download/v1.3.) | MIT |
| pi-node | 1.3.0 | 1.3.0 | `e79626f2dd6f94aa` | 110.6 MB + node 199 MB | npm ci --ignore-scripts (@earendil-works/pi-coding-agent) | MIT |
| pibolt | 0.9.3 | 1.3.0 (Pi-Bolt 0.9.3, linux-x64, JIT off) | `fe2572130b036a69` | 267.5 MB | release archive (https://github.com/opensec-git/Pi-Bolt/releases/download/bol) | MIT |
| pig-0.4.1 | 0.4.1 | 0.4.1+1.0.3 | `110ab2ece63f0ac5` | 63.8 MB | release archive (https://github.com/MichaelKinsy/PiG/releases/download/v0.4.1) | MIT |
| pig-tip | 0.5.0+1.3.0 | 0.5.0+1.3.0.1402973a | `cc759dbd134406f9` | 70.2 MB | source build (26eaad58e3ec09e25adf74000f79bcd83123aa8c) | MIT |

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
| idle_before | {"48": 0.0, "49": 0.0, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0, "114": 0.0, "115": 0.0} |
| idle_after | {"48": 0.0, "49": 0.0, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0, "114": 0.0, "115": 0.0} |
| load_before | [1.43310546875, 1.74267578125, 1.7763671875] |
| load_after | [1.08984375, 1.19384765625, 1.23583984375] |
| throttled_usec | 0 |
| cpumon | {"samples": 4992, "pinned_busy_mean": 0.022014418578323126, "pinned_busy_max": 0.1664141414141414, "host_busy_mean": 0.009147627403471434} |
| go | null |
| node_js | null |
| python | 3.12.3 |

Variables each harness was started with beyond the host's environment (the throwaway root is `<work>`); credential-looking and proxy variables of the host are removed:

- **pi-bun**: `HOME=<work>/pi-bun-a-stream-tui-prose-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-a-stream-tui-prose-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-a-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-a-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-a-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-a-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-a-stream-tui-prose-openai/home/.local/state`
- **pi-bun-b**: `HOME=<work>/pi-bun-b-stream-tui-prose-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-b-stream-tui-prose-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-b-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-b-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-b-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-b-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-b-stream-tui-prose-openai/home/.local/state`
- **pi-node**: `HOME=<work>/pi-node-a-stream-tui-prose-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-81l289nz/arms/pi-node-a/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-81l289nz/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-a-stream-tui-prose-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-a-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-a-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-a-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-a-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-a-stream-tui-prose-openai/home/.local/state`
- **pi-node-b**: `HOME=<work>/pi-node-b-stream-tui-prose-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-81l289nz/arms/pi-node-b/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-81l289nz/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-b-stream-tui-prose-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-b-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-b-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-b-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-b-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-b-stream-tui-prose-openai/home/.local/state`
- **pibolt**: `HOME=<work>/pibolt-a-stream-tui-prose-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-a-stream-tui-prose-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-a-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-a-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-a-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-a-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-a-stream-tui-prose-openai/home/.local/state`
- **pibolt-b**: `HOME=<work>/pibolt-b-stream-tui-prose-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-b-stream-tui-prose-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-b-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-b-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-b-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-b-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-b-stream-tui-prose-openai/home/.local/state`
- **pig-0.4.1**: `HOME=<work>/pig-0.4.1-a-stream-tui-prose-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-81l289nz/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-a-stream-tui-prose-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-a-stream-tui-prose-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-a-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-a-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-a-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-a-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-a-stream-tui-prose-openai/home/.local/state`
- **pig-0.4.1-b**: `HOME=<work>/pig-0.4.1-b-stream-tui-prose-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-81l289nz/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-b-stream-tui-prose-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-b-stream-tui-prose-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-b-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-b-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-b-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-b-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-b-stream-tui-prose-openai/home/.local/state`
- **pig-tip**: `HOME=<work>/pig-tip-a-stream-tui-prose-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-81l289nz/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-a-stream-tui-prose-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-a-stream-tui-prose-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-a-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-a-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-a-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-a-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-a-stream-tui-prose-openai/home/.local/state`
- **pig-tip-b**: `HOME=<work>/pig-tip-b-stream-tui-prose-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-81l289nz/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-b-stream-tui-prose-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-b-stream-tui-prose-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-b-stream-tui-prose-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-b-stream-tui-prose-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-b-stream-tui-prose-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-b-stream-tui-prose-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-b-stream-tui-prose-openai/home/.local/state`

### Runtime settings

Buffon pins CPUs but sets no runtime tuning of its own. An arm runs at its harness's shipped default except for the variables its manifest sets:

| arm | set by the manifest | left at the harness default |
|---|---|---|
| pi-bun | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pi-node | `NODE_COMPILE_CACHE={install_dir}/node-compile-cache` | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pibolt | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pig-0.4.1 | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |
| pig-tip | none | GOMAXPROCS, GOGC, GOMEMLIMIT, GODEBUG, NODE_OPTIONS, NODE_COMPILE_CACHE, UV_THREADPOOL_SIZE, BUN_GARBAGE_COLLECTOR_LEVEL |

### Declared divergences

Where an arm does different work by its own account, its median is shown and not compared (no ratio, no grade):

| arm | workloads | metrics | reason | source |
|---|---|---|---|---|
| pibolt | `streaming/tui-*` | all | Pi-Bolt's fullscreen TUI scrolls the rows that only moved (a scroll region) and draws only the rows that changed | https://github.com/opensec-git/Pi-Bolt/blob/bolt-v0.9.3/packages/tui/src/tui-alt-screen.ts |

---
*Quiet dedicated hardware: generated from 1 run directory by `buffon report`; 7 notes: aa_cv_cpu 3.3%, aa_significant_fraction 8.8%, aa_gap_max 156.7%, aa_floor_median 3.4%, aa_floor_max 167.7%, outlier_fraction 4.4%, foreign_cpu_p95 1.7%; the raw samples are in each directory's raw.json. The same data as report.html, report.json, summary.csv, rounds.csv, noise.csv and telemetry.csv.*
