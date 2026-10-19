# buffon report — PROVISIONAL

**Trust: Dedicated** (host class A). 3 sample(s) waited for the host to quiet down (longest 2 s); adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 3 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting; the run is not labelled quiet dedicated hardware Every measurement is recorded and shown whatever the label. Headline CPU metric: instructions.

**Run notes (4)**: aa_significant_fraction 6.7%, aa_floor_max 36.7%, outlier_fraction 2.3%, hardware (usual ranges: docs/HEALTH.md)

> **PROVISIONAL.** Every number in this report is provisional: at least one run was not on quiet dedicated hardware by the runner's own detection. Do not publish or compare it with another report.
>
> Why:
> - run 1: adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge
> - run 1: 3 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting

| field | value |
|---|---|
| reference arm | pi-node |
| arms | pi-bun, pi-node, pibolt, pig-0.4.1, pig-tip (each with an A/A copy `<id>-b` where the run had one) |
| runs | 1 |
| seed | 20261011 |
| token counts | the mock's usage: prompt tokens = request wire bytes / 4, completion tokens = one per streamed part + 12 per tool call; no tokenizer is pinned (METHODOLOGY section 3) |
| arms.lock sha256 | `549a3d2cc424cd316c5ff3072cf5c0c42bb1d6335775fd7289dd560254e35c33` |
| runner commit / tree | `5b3729fca2f0` / `3943ebd8df99` |
| run 1 | site `smc1-socket1` (local), 12 measured + 1 warm-up rounds, harness CPUs `48,49,50,51,112,113,114,115`, mock CPUs `52,116`, Intel(R) Xeon(R) Platinum 8462Y+, kernel 6.8.0-137-generic, meter cgroup-systemd; load before/after 1.0 / 1.6; calibration: CV 1.7% of cpu_ms (gate 5.0%) passed; hardware **provisional**; host class **A**; isolation **uncontained, not comparable** |
| run 1 CPU cost | **instructions** (user and kernel instructions) are the headline CPU metric; CPU time (user + system) and wall time are separate cells |

## Run notes — PROVISIONAL

4 notes: aa_significant_fraction 6.7%, aa_floor_max 36.7%, outlier_fraction 2.3%, hardware. Run notes describe the conditions of the run. They do not grade it or change a number.

| check | value | usual range | status | meaning |
|---|---:|---:|---|---|
| A/A pairs with a significant gap (paired p < 0.05, before Holm) that is also larger than 1% | 6.7% | up to 5.0% | note | Share of harness and copy pairs that differ by more than 1% and also pass a significance test. A gap under 1% on a steady counter is not counted. About 5% can happen by chance. longsession/resume-n chat turn_cpu_ms pig-tip: 4.9%; longsession/resume-n-varied chat turn_cpu_ms pibolt: 3.2%; longsession/resume-n chat ready_ms pibolt: 2.3% |
| A/A noise floor, worst scored cell | 36.7% | up to 15.0% | note | The same floor in the noisiest cell. Comparisons in that cell resolve only larger differences. longsession/resume-n chat ready_ms: 36.7%; longsession/resume-n-varied chat turn_cpu_ms: 18.3%; longsession/resume-n chat turn_cpu_ms: 17.4% |
| Measured values flagged by the MAD rule | 2.3% | up to 2.0% | note | Share of measured values far from the median of their cell. Outliers are counted and never removed. longsession/resume-n chat instructions pi-bun: 3; longsession/resume-n chat instructions pi-bun-b: 3; longsession/resume-n chat ready_ms pig-tip: 3 |
| Quiet dedicated hardware by the runner's own detection | no | yes | note | On shared hardware other work can disturb the numbers. run 1 not on quiet dedicated hardware: adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 3 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting |
| Calibration: CV of the reference's CPU time between identical runs | 1.7% | up to 2.0% | ok | How much the reference's CPU time varied between identical calibration runs. Lower means a quieter host. |
| A/A CV of CPU metrics, median over arms and cells | 1.7% | up to 2.0% | ok | How much CPU time varies from round to round for one harness. Lower means a quieter host. |
| A/A gap between a harness and its own copy, median over cells | 0.2% | up to 1.0% | ok | The usual gap between a harness and its identical copy. A real difference between two harnesses should be larger than this. |
| A/A gap between a harness and its own copy, largest cell | 4.9% | up to 5.0% | ok | The largest gap between a harness and its identical copy, and the cell where it happened. |
| A/A noise floor, median over scored cells | 1.3% | up to 3.0% | ok | The smallest difference the identical copies cannot tell from noise, in the usual cell. Smaller differences than this are not resolved. |
| Measured samples with at least one host flag | 0.0% | up to 5.0% | ok | Share of samples where the host showed a disturbance: throttling, foreign CPU, steal, a clock change, swap or a memory event. |
| Measured samples with CFS throttling (arm cgroup, every ancestor, session) | 0 | up to 0 | ok | Samples where the kernel held the process back for a CPU quota. Their time then describes the quota, not the harness. |
| Steal: share of the pinned CPUs' capacity taken by a hypervisor | 0.0% | up to 0.1% | ok | Share of the pinned CPUs' time that a hypervisor took away. It only matters on virtual machines. |
| Foreign CPU on the pinned CPUs during a sample, p95 over samples, as a share of the sample's CPU time | 0.0% | up to 1.0% | ok | CPU time that other processes used on the pinned cores during a sample, as a share of the sample's own CPU time (95th percentile). |
| Samples that waited more than 1 s for the host to quiet down | 0.0% | up to 1.0% | ok | Share of samples that had to wait for the quiet-host gate. A busy host makes the gate wait. |
| Samples for which the host never quieted down | 0 | up to 0 | ok | Samples that did not start because the host stayed busy. They are not in the numbers. |
| Effective clock: largest deviation of a sample's mean MHz from the run median | 0.1% | up to 2.0% | ok | How far a sample's mean CPU clock moved from the run median. A moving clock changes CPU time for the same work. |
| Infrastructure failures (envelope OOM, no process started, runner fault) over measured samples | 0.0% | up to 0.0% | ok | Share of samples that failed because of the host or the runner. They are never charged to a harness. |
| Arm failures over measured samples (a swarm ladder's designed stops are results and not counted) | 0.0% | up to 2.0% | ok | Share of samples where the harness itself failed. A scale sample that stopped because the kernel's limit was reached (stop_cause oom, pids or timeout) is a result and is in neither the failures nor the samples counted; a scale error stop is a failure. |
| Drift: median absolute change over the run of an arm's value, over cells | 0.2% | up to 2.0% | ok | How much a harness's value moved from the start of the run to the end. Drift means the host changed during the run. |
| No change point in the reference arm's per-round series | yes | yes | ok | The host's speed did not shift during the run. A shift moves every comparison the same way. |
| At least 12 measured rounds | yes | yes | ok | With fewer rounds the intervals are wide. |
| Every arm has an A/A copy | yes | yes | ok | Without a copy there is no noise floor for that harness. |
| No harness connected outside the loopback | yes | yes | ok | A harness that talks to the network is not measured alone. |
| Every executable and install tree unchanged during the run | yes | yes | ok | A changed executable means the arm is not what the lock names. |
| Calibration ran and the reference stayed within its 5% limit | yes | yes | ok | Calibration shows the host's noise before the run. Above 5% the run is labelled Noisy. |
| Telemetry recorded for every measured sample | yes | yes | ok | Telemetry is how the other checks see the host. |
| No CPU quota (cpu.max) on the arm cgroup or any ancestor | yes | yes | ok | A quota can throttle a sample. |
| The pinned CPUs have a fixed clock policy | yes | yes | ok | A clock that scales with load changes CPU time for the same work. |

The usual ranges are published in docs/HEALTH.md and are the same for every run. The notes are recomputed from the raw data by `buffon verify`; they are not stored in raw.json.
The A/A rows compare each harness with its own identical copy. A pair counts as different only when its gap is significant and also larger than 1%.

## Buffon leaderboard: Pi Harness Score — PROVISIONAL

> **PROVISIONAL.** The run was not on quiet dedicated hardware by the runner's own detection. These grades are for reading, never for publication, and never a public leaderboard row.
>
> - run 1: adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge
> - run 1: 3 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting

**Trust: Dedicated** (host class A). 3 sample(s) waited for the host to quiet down (longest 2 s); adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 3 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting; the run is not labelled quiet dedicated hardware

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 4.

### Pi-faithful entries (faithfulness 90 or more) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** PROVISIONAL | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

### Faithfulness not measured (ranked apart until it is) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pig-tip (PiG 0.5.0) | **90 (A-)** PROVISIONAL | not measured | 1/9 (8 not run) | source build; 70.2 MB; linux-x64 | 90-90 | 86-94, rank 1-2 |
| 2 | pibolt (Pi-Bolt) | **88 (B+)** PROVISIONAL | not measured | 1/9 (8 not run) | release archive; 267.5 MB; linux-x64 | 88-88 | 81-95, rank 1-3 |
| 3 | pig-0.4.1 (PiG 0.4.1) | **86 (B)** PROVISIONAL | not measured | 1/9 (8 not run) | release archive; 63.8 MB; linux-x64 | 86-86 | 84-87, rank 2-3 |
| 4 | pi-bun (Pi on Bun) | **65 (D)** PROVISIONAL | not measured | 1/9 (8 not run) | release archive; 114.5 MB; linux-x64 | 65-65 | 64-66, rank 4-4 |

### Below the reference — PROVISIONAL

- **pi-bun**: long-session 65 (D) at 1.39x the reference's cost

*PROVISIONAL: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*


## Summary by axis — PROVISIONAL

Counts of cells where the arm is measurably worse (loss), inconclusive, inside the A/A floor (no measurable difference) or measurably better (win) than the reference `pi-node`. A "cannot run" cell is never counted. Coverage is the cells the arm produced values for out of all cells in the report.

| arm | coverage | family | losses | inconclusive | no measurable difference | wins |
|---|---|---|---:|---:|---:|---:|
| pi-bun | 32/32 | longsession | 22 | 0 | 2 | 6 |
| pibolt | 32/32 | longsession | 6 | 0 | 2 | 22 |
| pig-0.4.1 | 32/32 | longsession | 2 | 0 | 2 | 26 |
| pig-tip † | 32/32 | longsession | 0 | 0 | 2 | 28 |

† `pig-tip`: This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

## pi-bun against pi-node — PROVISIONAL

### Losses (measurably worse than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | ready_ms | wall | ms | 8 | 268 | 454 | 1.7 [1.68, 1.71] | 1.1% | 0.9% | 0.9% / 0.4% | 3.98 / 1.66 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_ms` |
| longsession/resume-n-varied | chat | ready_ms | wall | ms | 8 | 268 | 453 | 1.69 [1.68, 1.71] | 1.3% | 1.2% | 0.8% / 1.6% | 3.69 / 2.88 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_ms` |
| longsession/resume-n-varied | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 373 | 590 | 1.58 [1.57, 1.6] | 2.0% | 2.0% | 1.1% / 2.6% | 2.94 / 5.91 | 1 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_cpu_ms` |
| longsession/resume-n-varied | chat | cpu_ms | CPU | ms of CPU time | 8 | 442 | 694 | 1.57 [1.56, 1.6] | 2.0% | 1.7% | 0.8% / 2.6% | 4.06 / 7.63 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cpu_ms` |
| longsession/resume-n | chat | cpu_ms | CPU | ms of CPU time | 8 | 443 | 691 | 1.56 [1.54, 1.58] | 2.1% | 1.1% | 0.9% / 1.2% | 3.24 / 15.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cpu_ms` |
| longsession/resume-n-varied | chat | cycles | CPU | cycles | 8 | 1214.93M | 1893.15M | 1.56 [1.55, 1.59] | 2.1% | 1.7% | 0.8% / 2.6% | 11,452,847 / 21,813,258 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cycles` |
| longsession/resume-n | chat | cycles | CPU | cycles | 8 | 1217.23M | 1888.25M | 1.55 [1.53, 1.56] | 2.1% | 1.2% | 1.0% / 1.1% | 9,812,650 / 39,666,629 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cycles` |
| longsession/resume-n | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 377 | 584 | 1.55 [1.52, 1.58] | 3.2% | 1.6% | 1.4% / 1.2% | 6.43 / 14.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_cpu_ms` |
| longsession/resume-n-varied | chat | instructions | CPU | instructions | 8 | 2424.21M | 3713.47M | 1.53 [1.53, 1.53] | 0.4% | 0.3% | 0.2% / 0.8% | 9,261,404 / 2,423,338 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#instructions` |
| longsession/resume-n-varied | chat | peak_mem_mib | memory | MiB | 8 | 68.0 | 104 | 1.52 [1.51, 1.55] | 3.0% | 2.2% | 1.1% / 1.9% | 0.969 / 1.57 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_mem_mib` |
| longsession/resume-n | chat | peak_mem_mib | memory | MiB | 8 | 67.6 | 101 | 1.5 [1.48, 1.54] | 2.1% | 1.5% | 1.4% / 1.2% | 1.44 / 2.17 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_mem_mib` |
| longsession/resume-n | chat | instructions | CPU | instructions | 8 | 2429.22M | 3638.04M | 1.5 [1.49, 1.53] | 2.2% | 0.1% | 0.2% / 1.1% | 3,549,505 / 81,595,096 | 0 / 3 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#instructions` |
| longsession/resume-n | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.0 | 79.9 | 1.45 [1.45, 1.48] | 3.7% | 2.0% | 0.7% / 3.3% | 0.537 / 0.913 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_cpu_ms` |
| longsession/resume-n-varied | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.5 | 79.7 | 1.44 [1.4, 1.5] | 3.9% | 2.6% | 2.1% / 3.2% | 1.77 / 2.4 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_cpu_ms` |
| longsession/resume-n | chat | turn_wall_ms | wall | ms | 8 | 51.0 | 70.9 | 1.39 [1.37, 1.41] | 3.0% | 1.8% | 0.9% / 2.0% | 0.367 / 1.75 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_wall_ms` |
| longsession/resume-n-varied | chat | turn_wall_ms | wall | ms | 8 | 51.8 | 71.2 | 1.37 [1.36, 1.41] | 2.5% | 1.5% | 1.0% / 1.8% | 0.632 / 1.15 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_wall_ms` |
| longsession/resume-n-varied | chat | ready_rss_mib | memory | MiB | 8 | 113 | 143 | 1.27 [1.25, 1.28] | 1.6% | 1.6% | 0.9% / 0.9% | 1.61 / 0.752 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_rss_mib` |
| longsession/resume-n | chat | ready_rss_mib | memory | MiB | 8 | 113 | 141 | 1.25 [1.23, 1.27] | 1.8% | 1.0% | 1.0% / 1.0% | 1.52 / 2.37 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_rss_mib` |
| longsession/resume-n-varied | chat | ready_pss_mib | memory | MiB | 8 | 107 | 134 | 1.25 [1.24, 1.27] | 2.2% | 1.6% | 1.0% / 1.6% | 1.55 / 1.1 | 0 / 3 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_pss_mib` |
| longsession/resume-n | chat | ready_pss_mib | memory | MiB | 8 | 107 | 132 | 1.23 [1.21, 1.25] | 1.8% | 1.1% | 1.1% / 1.0% | 1.53 / 2.16 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_pss_mib` |
| longsession/resume-n-varied | chat | peak_rss_mib | memory | MiB | 8 | 121 | 146 | 1.2 [1.2, 1.22] | 1.6% | 1.1% | 0.6% / 1.3% | 1.2 / 1.31 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_rss_mib` |
| longsession/resume-n | chat | peak_rss_mib | memory | MiB | 8 | 121 | 144 | 1.19 [1.18, 1.21] | 1.6% | 0.6% | 0.8% / 0.8% | 1.35 / 2.03 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_rss_mib` |

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#requests` |
| longsession/resume-n-varied | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#requests` |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | request_bytes | wire | bytes | 8 | 589,979 | 589,849 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes` |
| longsession/resume-n | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,979 | 589,849 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes_per_turn` |
| longsession/resume-n | chat | session_growth_bytes | size | bytes | 8 | 7,169 | 7,038 | 0.982 [0.982, 0.982] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#session_growth_bytes` |
| longsession/resume-n-varied | chat | request_bytes | wire | bytes | 8 | 589,986 | 589,856 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes` |
| longsession/resume-n-varied | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,986 | 589,856 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes_per_turn` |
| longsession/resume-n-varied | chat | session_growth_bytes | size | bytes | 8 | 7,183 | 7,052 | 0.982 [0.982, 0.982] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#session_growth_bytes` |

## pibolt against pi-node — PROVISIONAL

### Losses (measurably worse than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | session_growth_bytes | size | bytes | 8 | 7,169 | 9,022 | 1.26 [1.26, 1.26] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#session_growth_bytes` |
| longsession/resume-n-varied | chat | session_growth_bytes | size | bytes | 8 | 7,183 | 9,036 | 1.26 [1.26, 1.26] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#session_growth_bytes` |
| longsession/resume-n | chat | request_bytes | wire | bytes | 8 | 589,979 | 591,896 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes` |
| longsession/resume-n | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,979 | 591,896 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes_per_turn` |
| longsession/resume-n-varied | chat | request_bytes | wire | bytes | 8 | 589,986 | 591,903 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes` |
| longsession/resume-n-varied | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,986 | 591,903 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#requests` |
| longsession/resume-n-varied | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#requests` |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | cpu_ms | CPU | ms of CPU time | 8 | 443 | 49.6 | 0.112 [0.11, 0.113] | 4.1% | 1.1% | 0.9% / 1.7% | 3.24 / 0.698 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cpu_ms` |
| longsession/resume-n | chat | cycles | CPU | cycles | 8 | 1217.23M | 128.67M | 0.106 [0.104, 0.107] | 4.3% | 1.2% | 1.0% / 1.7% | 9,812,650 / 1,764,014 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cycles` |
| longsession/resume-n | chat | instructions | CPU | instructions | 8 | 2429.22M | 199.70M | 0.0822 [0.082, 0.0826] | 2.0% | 0.1% | 0.2% / 0.4% | 3,549,505 / 727,906 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#instructions` |
| longsession/resume-n | chat | peak_mem_mib | memory | MiB | 8 | 67.6 | 23.5 | 0.347 [0.341, 0.351] | 1.9% | 1.5% | 1.4% / 0.7% | 1.44 / 0.115 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_mem_mib` |
| longsession/resume-n | chat | peak_rss_mib | memory | MiB | 8 | 121 | 94.4 | 0.78 [0.771, 0.784] | 0.7% | 0.6% | 0.8% / 0.2% | 1.35 / 0.276 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_rss_mib` |
| longsession/resume-n | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 377 | 39.6 | 0.105 [0.103, 0.107] | 4.3% | 1.6% | 1.4% / 1.7% | 6.43 / 0.442 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_cpu_ms` |
| longsession/resume-n | chat | ready_ms | wall | ms | 8 | 268 | 35.8 | 0.134 [0.132, 0.135] | 3.6% | 0.9% | 0.9% / 1.2% | 3.98 / 0.386 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_ms` |
| longsession/resume-n | chat | ready_pss_mib | memory | MiB | 8 | 107 | 83.3 | 0.775 [0.765, 0.783] | 1.2% | 1.1% | 1.1% / 0.2% | 1.53 / 0.23 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_pss_mib` |
| longsession/resume-n | chat | ready_rss_mib | memory | MiB | 8 | 113 | 87.6 | 0.776 [0.766, 0.783] | 1.1% | 1.0% | 1.0% / 0.2% | 1.52 / 0.235 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_rss_mib` |
| longsession/resume-n | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.0 | 6.57 | 0.12 [0.117, 0.123] | 3.7% | 2.0% | 0.7% / 2.4% | 0.537 / 0.211 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_cpu_ms` |
| longsession/resume-n | chat | turn_wall_ms | wall | ms | 8 | 51.0 | 7.94 | 0.156 [0.154, 0.158] | 3.0% | 1.8% | 0.9% / 2.5% | 0.367 / 0.186 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_wall_ms` |
| longsession/resume-n-varied | chat | cpu_ms | CPU | ms of CPU time | 8 | 442 | 50.0 | 0.113 [0.112, 0.116] | 4.4% | 1.7% | 0.8% / 1.9% | 4.06 / 1.48 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cpu_ms` |
| longsession/resume-n-varied | chat | cycles | CPU | cycles | 8 | 1214.93M | 129.51M | 0.107 [0.105, 0.11] | 4.2% | 1.7% | 0.8% / 1.9% | 11,452,847 / 4,012,676 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cycles` |
| longsession/resume-n-varied | chat | instructions | CPU | instructions | 8 | 2424.21M | 199.33M | 0.0822 [0.0819, 0.0825] | 1.3% | 0.3% | 0.2% / 0.3% | 9,261,404 / 939,507 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#instructions` |
| longsession/resume-n-varied | chat | peak_mem_mib | memory | MiB | 8 | 68.0 | 23.4 | 0.344 [0.341, 0.351] | 3.0% | 2.2% | 1.1% / 1.1% | 0.969 / 0.344 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_mem_mib` |
| longsession/resume-n-varied | chat | peak_rss_mib | memory | MiB | 8 | 121 | 94.5 | 0.779 [0.775, 0.785] | 1.4% | 1.1% | 0.6% / 0.2% | 1.2 / 0.363 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_rss_mib` |
| longsession/resume-n-varied | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 373 | 39.9 | 0.107 [0.106, 0.109] | 3.7% | 2.0% | 1.1% / 1.4% | 2.94 / 0.855 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_cpu_ms` |
| longsession/resume-n-varied | chat | ready_ms | wall | ms | 8 | 268 | 36.0 | 0.135 [0.132, 0.137] | 3.7% | 1.2% | 0.8% / 1.1% | 3.69 / 0.393 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_ms` |
| longsession/resume-n-varied | chat | ready_pss_mib | memory | MiB | 8 | 107 | 83.3 | 0.777 [0.77, 0.786] | 1.7% | 1.6% | 1.0% / 0.2% | 1.55 / 0.281 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_pss_mib` |
| longsession/resume-n-varied | chat | ready_rss_mib | memory | MiB | 8 | 113 | 87.7 | 0.778 [0.771, 0.787] | 1.6% | 1.6% | 0.9% / 0.2% | 1.61 / 0.311 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_rss_mib` |
| longsession/resume-n-varied | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.5 | 6.54 | 0.118 [0.114, 0.126] | 5.3% | 2.6% | 2.1% / 5.2% | 1.77 / 0.461 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_cpu_ms` |
| longsession/resume-n-varied | chat | turn_wall_ms | wall | ms | 8 | 51.8 | 7.93 | 0.153 [0.151, 0.16] | 2.9% | 1.5% | 1.0% / 2.5% | 0.632 / 0.299 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_wall_ms` |

## pig-0.4.1 against pi-node — PROVISIONAL

### Losses (measurably worse than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n-varied | chat | request_bytes | wire | bytes | 8 | 589,986 | 589,999 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes` |
| longsession/resume-n-varied | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,986 | 589,999 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#requests` |
| longsession/resume-n-varied | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#requests` |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| longsession/resume-n | chat | cpu_ms | CPU | ms of CPU time | 8 | 443 | 137 | 0.308 [0.304, 0.315] | 3.6% | 1.1% | 0.9% / 1.8% | 3.24 / 3.33 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cpu_ms` |
| longsession/resume-n | chat | cycles | CPU | cycles | 8 | 1217.23M | 358.74M | 0.295 [0.291, 0.307] | 4.8% | 1.2% | 1.0% / 2.3% | 9,812,650 / 15,481,418 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cycles` |
| longsession/resume-n | chat | instructions | CPU | instructions | 8 | 2429.22M | 828.74M | 0.341 [0.339, 0.35] | 3.5% | 0.1% | 0.2% / 1.7% | 3,549,505 / 26,476,914 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#instructions` |
| longsession/resume-n | chat | peak_mem_mib | memory | MiB | 8 | 67.6 | 25.3 | 0.374 [0.365, 0.382] | 2.6% | 1.5% | 1.4% / 1.2% | 1.44 / 0.469 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_mem_mib` |
| longsession/resume-n | chat | peak_rss_mib | memory | MiB | 8 | 121 | 54.8 | 0.453 [0.448, 0.456] | 1.1% | 0.6% | 0.8% / 0.4% | 1.35 / 0.317 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_rss_mib` |
| longsession/resume-n | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 377 | 101 | 0.267 [0.26, 0.27] | 3.2% | 1.6% | 1.4% / 2.5% | 6.43 / 1.86 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_cpu_ms` |
| longsession/resume-n | chat | ready_ms | wall | ms | 8 | 268 | 70.2 | 0.262 [0.26, 0.264] | 1.8% | 0.9% | 0.9% / 0.8% | 3.98 / 0.807 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_ms` |
| longsession/resume-n | chat | ready_pss_mib | memory | MiB | 8 | 107 | 44.8 | 0.417 [0.412, 0.423] | 1.6% | 1.1% | 1.1% / 0.9% | 1.53 / 0.654 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_pss_mib` |
| longsession/resume-n | chat | ready_rss_mib | memory | MiB | 8 | 113 | 46.7 | 0.414 [0.409, 0.42] | 1.5% | 1.0% | 1.0% / 0.8% | 1.52 / 0.651 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_rss_mib` |
| longsession/resume-n | chat | request_bytes | wire | bytes | 8 | 589,979 | 589,978 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes` |
| longsession/resume-n | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,979 | 589,978 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes_per_turn` |
| longsession/resume-n | chat | session_growth_bytes | size | bytes | 8 | 7,169 | 7,154 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#session_growth_bytes` |
| longsession/resume-n | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.0 | 32.0 | 0.582 [0.523, 0.636] | 17.4% | 2.0% | 0.7% / 9.3% | 0.537 / 5.24 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_cpu_ms` |
| longsession/resume-n | chat | turn_wall_ms | wall | ms | 8 | 51.0 | 20.0 | 0.391 [0.377, 0.402] | 4.0% | 1.8% | 0.9% / 3.5% | 0.367 / 1.02 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_wall_ms` |
| longsession/resume-n-varied | chat | cpu_ms | CPU | ms of CPU time | 8 | 442 | 137 | 0.309 [0.303, 0.316] | 2.9% | 1.7% | 0.8% / 2.6% | 4.06 / 5.76 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cpu_ms` |
| longsession/resume-n-varied | chat | cycles | CPU | cycles | 8 | 1214.93M | 362.34M | 0.298 [0.293, 0.304] | 4.2% | 1.7% | 0.8% / 2.1% | 11,452,847 / 12,662,222 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cycles` |
| longsession/resume-n-varied | chat | instructions | CPU | instructions | 8 | 2424.21M | 834.77M | 0.344 [0.339, 0.351] | 3.2% | 0.3% | 0.2% / 1.6% | 9,261,404 / 25,090,800 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#instructions` |
| longsession/resume-n-varied | chat | peak_mem_mib | memory | MiB | 8 | 68.0 | 25.2 | 0.37 [0.361, 0.379] | 3.5% | 2.2% | 1.1% / 2.0% | 0.969 / 0.729 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_mem_mib` |
| longsession/resume-n-varied | chat | peak_rss_mib | memory | MiB | 8 | 121 | 54.8 | 0.451 [0.447, 0.458] | 1.5% | 1.1% | 0.6% / 0.8% | 1.2 / 0.582 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_rss_mib` |
| longsession/resume-n-varied | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 373 | 99.9 | 0.268 [0.266, 0.269] | 2.0% | 2.0% | 1.1% / 0.8% | 2.94 / 0.691 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_cpu_ms` |
| longsession/resume-n-varied | chat | ready_ms | wall | ms | 8 | 268 | 69.7 | 0.26 [0.258, 0.263] | 1.3% | 1.2% | 0.8% / 0.6% | 3.69 / 0.486 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_ms` |
| longsession/resume-n-varied | chat | ready_pss_mib | memory | MiB | 8 | 107 | 45.0 | 0.42 [0.415, 0.425] | 1.7% | 1.6% | 1.0% / 0.9% | 1.55 / 0.385 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_pss_mib` |
| longsession/resume-n-varied | chat | ready_rss_mib | memory | MiB | 8 | 113 | 46.9 | 0.416 [0.412, 0.421] | 1.6% | 1.6% | 0.9% / 0.8% | 1.61 / 0.382 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_rss_mib` |
| longsession/resume-n-varied | chat | session_growth_bytes | size | bytes | 8 | 7,183 | 7,182 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#session_growth_bytes` |
| longsession/resume-n-varied | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.5 | 31.8 | 0.573 [0.512, 0.619] | 18.3% | 2.6% | 2.1% / 9.3% | 1.77 / 5.15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_cpu_ms` |
| longsession/resume-n-varied | chat | turn_wall_ms | wall | ms | 8 | 51.8 | 19.7 | 0.381 [0.372, 0.393] | 4.0% | 1.5% | 1.0% / 3.0% | 0.632 / 0.814 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_wall_ms` |

## pig-tip against pi-node — PROVISIONAL

> **Read this first:** This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

### Losses (measurably worse than the reference) — PROVISIONAL

None.

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| longsession/resume-n | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#requests` | 1 [1, 1] no measurable difference |
| longsession/resume-n-varied | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#requests` | 1 [1, 1] no measurable difference |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| longsession/resume-n | chat | cpu_ms | CPU | ms of CPU time | 8 | 443 | 69.1 | 0.156 [0.149, 0.157] | 5.1% | 1.1% | 0.9% / 3.3% | 3.24 / 2.98 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cpu_ms` | 0.505 [0.471, 0.511] win |
| longsession/resume-n | chat | cycles | CPU | cycles | 8 | 1217.23M | 174.09M | 0.143 [0.141, 0.144] | 2.1% | 1.2% | 1.0% / 1.8% | 9,812,650 / 1,112,829 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cycles` | 0.485 [0.467, 0.488] win |
| longsession/resume-n | chat | instructions | CPU | instructions | 8 | 2429.22M | 473.02M | 0.195 [0.194, 0.195] | 0.4% | 0.1% | 0.2% / 1.4% | 3,549,505 / 732,961 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#instructions` | 0.571 [0.556, 0.575] win |
| longsession/resume-n | chat | peak_mem_mib | memory | MiB | 8 | 67.6 | 21.1 | 0.313 [0.304, 0.32] | 3.8% | 1.5% | 1.4% / 2.4% | 1.44 / 0.618 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_mem_mib` | 0.835 [0.81, 0.854] win |
| longsession/resume-n | chat | peak_rss_mib | memory | MiB | 8 | 121 | 56.0 | 0.462 [0.458, 0.465] | 0.9% | 0.6% | 0.8% / 1.2% | 1.35 / 0.216 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_rss_mib` | 1.02 [1.01, 1.02] loss |
| longsession/resume-n | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 377 | 53.9 | 0.143 [0.14, 0.144] | 3.2% | 1.6% | 1.4% / 0.8% | 6.43 / 0.563 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_cpu_ms` | 0.536 [0.531, 0.549] win |
| longsession/resume-n | chat | ready_ms | wall | ms | 8 | 268 | 65.9 | 0.246 [0.179, 0.248] | 36.7% | 0.9% | 0.9% / 13.9% | 3.98 / 12.1 | 0 / 3 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_ms` | 0.939 [0.686, 0.948] no measurable difference |
| longsession/resume-n | chat | ready_pss_mib | memory | MiB | 8 | 107 | 48.1 | 0.448 [0.444, 0.453] | 1.2% | 1.1% | 1.1% / 0.6% | 1.53 / 0.172 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_pss_mib` | 1.07 [1.06, 1.08] loss |
| longsession/resume-n | chat | ready_rss_mib | memory | MiB | 8 | 113 | 50.0 | 0.444 [0.439, 0.448] | 1.2% | 1.0% | 1.0% / 0.6% | 1.52 / 0.175 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_rss_mib` | 1.07 [1.06, 1.08] loss |
| longsession/resume-n | chat | request_bytes | wire | bytes | 8 | 589,979 | 589,940 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes` | 1 [1, 1] win |
| longsession/resume-n | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,979 | 589,940 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes_per_turn` | 1 [1, 1] win |
| longsession/resume-n | chat | session_growth_bytes | size | bytes | 8 | 7,169 | 7,129 | 0.994 [0.994, 0.994] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#session_growth_bytes` | 0.997 [0.997, 0.997] win |
| longsession/resume-n | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.0 | 6.75 | 0.123 [0.119, 0.124] | 9.5% | 2.0% | 0.7% / 3.3% | 0.537 / 0.142 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_cpu_ms` | 0.211 [0.188, 0.233] win |
| longsession/resume-n | chat | turn_wall_ms | wall | ms | 8 | 51.0 | 8.61 | 0.169 [0.167, 0.173] | 4.1% | 1.8% | 0.9% / 2.2% | 0.367 / 0.175 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_wall_ms` | 0.431 [0.418, 0.449] win |
| longsession/resume-n-varied | chat | cpu_ms | CPU | ms of CPU time | 8 | 442 | 69.7 | 0.158 [0.156, 0.159] | 4.7% | 1.7% | 0.8% / 1.2% | 4.06 / 0.795 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cpu_ms` | 0.51 [0.493, 0.523] win |
| longsession/resume-n-varied | chat | cycles | CPU | cycles | 8 | 1214.93M | 175.03M | 0.144 [0.143, 0.145] | 1.7% | 1.7% | 0.8% / 0.5% | 11,452,847 / 886,248 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cycles` | 0.483 [0.472, 0.492] win |
| longsession/resume-n-varied | chat | instructions | CPU | instructions | 8 | 2424.21M | 474.10M | 0.196 [0.195, 0.196] | 0.4% | 0.3% | 0.2% / 0.1% | 9,261,404 / 419,315 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#instructions` | 0.568 [0.558, 0.576] win |
| longsession/resume-n-varied | chat | peak_mem_mib | memory | MiB | 8 | 68.0 | 21.3 | 0.314 [0.311, 0.319] | 3.0% | 2.2% | 1.1% / 0.7% | 0.969 / 0.234 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_mem_mib` | 0.848 [0.84, 0.869] win |
| longsession/resume-n-varied | chat | peak_rss_mib | memory | MiB | 8 | 121 | 56.2 | 0.463 [0.461, 0.467] | 1.4% | 1.1% | 0.6% / 0.3% | 1.2 / 0.251 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_rss_mib` | 1.03 [1.02, 1.03] loss |
| longsession/resume-n-varied | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 373 | 53.4 | 0.143 [0.142, 0.144] | 2.0% | 2.0% | 1.1% / 0.8% | 2.94 / 0.407 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_cpu_ms` | 0.534 [0.532, 0.541] win |
| longsession/resume-n-varied | chat | ready_ms | wall | ms | 8 | 268 | 66.0 | 0.246 [0.209, 0.248] | 16.3% | 1.2% | 0.8% / 11.2% | 3.69 / 2.56 | 0 / 3 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_ms` | 0.946 [0.802, 0.948] no measurable difference |
| longsession/resume-n-varied | chat | ready_pss_mib | memory | MiB | 8 | 107 | 48.4 | 0.452 [0.448, 0.458] | 1.7% | 1.6% | 1.0% / 0.4% | 1.55 / 0.232 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_pss_mib` | 1.08 [1.07, 1.09] loss |
| longsession/resume-n-varied | chat | ready_rss_mib | memory | MiB | 8 | 113 | 50.3 | 0.447 [0.444, 0.453] | 1.6% | 1.6% | 0.9% / 0.4% | 1.61 / 0.229 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_rss_mib` | 1.07 [1.07, 1.08] loss |
| longsession/resume-n-varied | chat | request_bytes | wire | bytes | 8 | 589,986 | 589,961 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes` | 1 [1, 1] win |
| longsession/resume-n-varied | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 589,986 | 589,961 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes_per_turn` | 1 [1, 1] win |
| longsession/resume-n-varied | chat | session_growth_bytes | size | bytes | 8 | 7,183 | 7,157 | 0.996 [0.996, 0.996] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#session_growth_bytes` | 0.997 [0.997, 0.997] win |
| longsession/resume-n-varied | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 55.5 | 6.79 | 0.122 [0.119, 0.125] | 4.3% | 2.6% | 2.1% / 3.3% | 1.77 / 0.129 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_cpu_ms` | 0.214 [0.195, 0.237] win |
| longsession/resume-n-varied | chat | turn_wall_ms | wall | ms | 8 | 51.8 | 8.85 | 0.171 [0.167, 0.176] | 3.2% | 1.5% | 1.0% / 2.4% | 0.632 / 0.229 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_wall_ms` | 0.448 [0.433, 0.464] win |

## pig-tip against its previous arm pig-0.4.1: 0.4.1 → 0.5.0 (newer / previous) — PROVISIONAL

`pig-0.4.1` is the earlier arm and `pig-tip` the later one (declared as `previous` in the manifest; a loss means the later arm is measurably worse, a win measurably better). The floor is the larger of the two arms' A/A floors; a ratio inside it is no measurable difference.

| workload | api | metric | pig-0.4.1 median | pig-tip median | ratio [95% CI] | A/A floor | verdict |
|---|---|---|---:|---:|---|---:|---|
| longsession/resume-n | chat | peak_rss_mib | 54.8 | 56.0 | 1.02 [1.01, 1.02] | 1.1% | **loss** |
| longsession/resume-n | chat | ready_pss_mib | 44.8 | 48.1 | 1.07 [1.06, 1.08] | 1.6% | **loss** |
| longsession/resume-n | chat | ready_rss_mib | 46.7 | 50.0 | 1.07 [1.06, 1.08] | 1.5% | **loss** |
| longsession/resume-n-varied | chat | peak_rss_mib | 54.8 | 56.2 | 1.03 [1.02, 1.03] | 1.5% | **loss** |
| longsession/resume-n-varied | chat | ready_pss_mib | 45.0 | 48.4 | 1.08 [1.07, 1.09] | 0.8% | **loss** |
| longsession/resume-n-varied | chat | ready_rss_mib | 46.9 | 50.3 | 1.07 [1.07, 1.08] | 0.8% | **loss** |
| longsession/resume-n | chat | ready_ms | 70.2 | 65.9 | 0.939 [0.686, 0.948] | 36.7% | **no measurable difference** |
| longsession/resume-n | chat | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| longsession/resume-n-varied | chat | ready_ms | 69.7 | 66.0 | 0.946 [0.802, 0.948] | 16.3% | **no measurable difference** |
| longsession/resume-n-varied | chat | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| longsession/resume-n | chat | cpu_ms | 137 | 69.1 | 0.505 [0.471, 0.511] | 5.1% | **win** |
| longsession/resume-n | chat | cycles | 358.74M | 174.09M | 0.485 [0.467, 0.488] | 4.8% | **win** |
| longsession/resume-n | chat | instructions | 828.74M | 473.02M | 0.571 [0.556, 0.575] | 3.5% | **win** |
| longsession/resume-n | chat | peak_mem_mib | 25.3 | 21.1 | 0.835 [0.81, 0.854] | 3.8% | **win** |
| longsession/resume-n | chat | ready_cpu_ms | 101 | 53.9 | 0.536 [0.531, 0.549] | 2.4% | **win** |
| longsession/resume-n | chat | request_bytes | 589,978 | 589,940 | 1 [1, 1] | 0.0% | **win** |
| longsession/resume-n | chat | request_bytes_per_turn | 589,978 | 589,940 | 1 [1, 1] | 0.0% | **win** |
| longsession/resume-n | chat | session_growth_bytes | 7,154 | 7,129 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| longsession/resume-n | chat | turn_cpu_ms | 32.0 | 6.75 | 0.211 [0.188, 0.233] | 17.4% | **win** |
| longsession/resume-n | chat | turn_wall_ms | 20.0 | 8.61 | 0.431 [0.418, 0.449] | 4.1% | **win** |
| longsession/resume-n-varied | chat | cpu_ms | 137 | 69.7 | 0.51 [0.493, 0.523] | 4.7% | **win** |
| longsession/resume-n-varied | chat | cycles | 362.34M | 175.03M | 0.483 [0.472, 0.492] | 4.2% | **win** |
| longsession/resume-n-varied | chat | instructions | 834.77M | 474.10M | 0.568 [0.558, 0.576] | 3.2% | **win** |
| longsession/resume-n-varied | chat | peak_mem_mib | 25.2 | 21.3 | 0.848 [0.84, 0.869] | 3.5% | **win** |
| longsession/resume-n-varied | chat | ready_cpu_ms | 99.9 | 53.4 | 0.534 [0.532, 0.541] | 1.4% | **win** |
| longsession/resume-n-varied | chat | request_bytes | 589,999 | 589,961 | 1 [1, 1] | 0.0% | **win** |
| longsession/resume-n-varied | chat | request_bytes_per_turn | 589,999 | 589,961 | 1 [1, 1] | 0.0% | **win** |
| longsession/resume-n-varied | chat | session_growth_bytes | 7,182 | 7,157 | 0.997 [0.997, 0.997] | 0.0% | **win** |
| longsession/resume-n-varied | chat | turn_cpu_ms | 31.8 | 6.79 | 0.214 [0.195, 0.237] | 18.3% | **win** |
| longsession/resume-n-varied | chat | turn_wall_ms | 19.7 | 8.85 | 0.448 [0.433, 0.464] | 4.0% | **win** |

## A/A noise floor — PROVISIONAL

Each arm's A/A copy `<id>-b` is the same executable run in the same rounds. The floor of a cell is the largest deviation from 1 the copy's ratio-of-medians interval allows; a difference between arms smaller than the floor is reported as no measurable difference. The table gives, per arm and workload, the median and the maximum floor over the scored metrics, and the reference's minimum detectable effect at 80% power.

| arm | workload | api | cells | median floor | max floor | worst metric |
|---|---|---|---:|---:|---:|---|
| pi-bun | longsession/resume-n | chat | 15 | 1.8% | 2.9% | turn_cpu_ms |
| pi-bun | longsession/resume-n-varied | chat | 15 | 1.6% | 3.9% | turn_cpu_ms |
| pi-node | longsession/resume-n | chat | 15 | 1.1% | 3.7% | turn_cpu_ms |
| pi-node | longsession/resume-n-varied | chat | 15 | 1.4% | 3.7% | turn_cpu_ms |
| pibolt | longsession/resume-n | chat | 15 | 1.2% | 4.3% | ready_cpu_ms |
| pibolt | longsession/resume-n-varied | chat | 15 | 1.0% | 5.3% | turn_cpu_ms |
| pig-0.4.1 | longsession/resume-n | chat | 15 | 1.8% | 17.4% | turn_cpu_ms |
| pig-0.4.1 | longsession/resume-n-varied | chat | 15 | 1.3% | 18.3% | turn_cpu_ms |
| pig-tip | longsession/resume-n | chat | 15 | 1.2% | 36.7% | ready_ms |
| pig-tip | longsession/resume-n-varied | chat | 15 | 0.8% | 16.3% | ready_ms |

Minimum detectable effect of the reference's A/A pair over all cells: median 1.1%, worst 2.6%. A difference smaller than the cell's MDE cannot be seen in this run.

## Cell ids and rerun commands — PROVISIONAL

Every cell has an id, `<run id>::<workload>@<api>#<metric>`. `python3 -m buffon rerun <cell id> --site <your site profile>` repeats the plan of the run that holds the cell (its arms, rounds, seed and parameters) for that workload and API only, on your host, and compares your result with the original. The raw samples of every cell are in the run directory's raw.json; this report is generated from them and from nothing else, and `buffon verify` regenerates it to check that no number was edited.

| workload | api | metric | cell id |
|---|---|---|---|
| longsession/resume-n | chat | cpu_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cpu_ms` |
| longsession/resume-n | chat | cycles | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#cycles` |
| longsession/resume-n | chat | instructions | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#instructions` |
| longsession/resume-n | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_mem_mib` |
| longsession/resume-n | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#peak_rss_mib` |
| longsession/resume-n | chat | ready_cpu_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_cpu_ms` |
| longsession/resume-n | chat | ready_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_ms` |
| longsession/resume-n | chat | ready_pss_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_pss_mib` |
| longsession/resume-n | chat | ready_rss_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#ready_rss_mib` |
| longsession/resume-n | chat | request_bytes | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes` |
| longsession/resume-n | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#request_bytes_per_turn` |
| longsession/resume-n | chat | requests | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#requests` |
| longsession/resume-n | chat | session_growth_bytes | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#session_growth_bytes` |
| longsession/resume-n | chat | side_requests | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#side_requests` |
| longsession/resume-n | chat | turn_cpu_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_cpu_ms` |
| longsession/resume-n | chat | turn_wall_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n@openai-completions#turn_wall_ms` |
| longsession/resume-n-varied | chat | cpu_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cpu_ms` |
| longsession/resume-n-varied | chat | cycles | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#cycles` |
| longsession/resume-n-varied | chat | instructions | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#instructions` |
| longsession/resume-n-varied | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_mem_mib` |
| longsession/resume-n-varied | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#peak_rss_mib` |
| longsession/resume-n-varied | chat | ready_cpu_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_cpu_ms` |
| longsession/resume-n-varied | chat | ready_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_ms` |
| longsession/resume-n-varied | chat | ready_pss_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_pss_mib` |
| longsession/resume-n-varied | chat | ready_rss_mib | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#ready_rss_mib` |
| longsession/resume-n-varied | chat | request_bytes | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes` |
| longsession/resume-n-varied | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#request_bytes_per_turn` |
| longsession/resume-n-varied | chat | requests | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#requests` |
| longsession/resume-n-varied | chat | session_growth_bytes | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#session_growth_bytes` |
| longsession/resume-n-varied | chat | side_requests | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#side_requests` |
| longsession/resume-n-varied | chat | turn_cpu_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_cpu_ms` |
| longsession/resume-n-varied | chat | turn_wall_ms | `2026-10-19-smc1-launch-focus-longsession::longsession/resume-n-varied@openai-completions#turn_wall_ms` |

## Noise report — PROVISIONAL

How noisy this run was, from its own samples and the telemetry taken around each one (docs/TELEMETRY.md). The A/A figures compare each arm with its own identical copy, so they show what the host does to two runs of the same executable.

### Per metric

| metric | cells | A/A gap median | A/A gap worst | A/A floor median | A/A floor worst | CV median | CV worst | outliers / values | drift median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cpu_ms | 2 | 0.5% | 2.1% | 3.2% | 5.1% | 1.7% | 3.6% | 7 / 160 | 0.6% |
| cycles | 2 | 0.4% | 1.8% | 2.1% | 4.8% | 1.4% | 2.6% | 5 / 160 | 0.8% |
| instructions | 2 | 0.1% | 2.0% | 0.8% | 3.5% | 0.3% | 1.9% | 10 / 160 | 0.3% |
| peak_mem_mib | 2 | 0.4% | 1.9% | 2.2% | 3.8% | 1.2% | 2.8% | 1 / 160 | 1.2% |
| peak_rss_mib | 2 | 0.2% | 1.1% | 1.0% | 1.6% | 0.6% | 1.4% | 5 / 160 | 0.3% |
| ready_cpu_ms | 2 | 0.7% | 2.3% | 2.2% | 4.3% | 0.9% | 2.6% | 4 / 160 | 0.4% |
| ready_ms | 2 | 0.3% | 2.3% | 1.6% | 36.7% | 0.9% | 14.0% | 11 / 160 | 0.6% |
| ready_pss_mib | 2 | 0.1% | 1.2% | 1.2% | 2.2% | 0.7% | 1.6% | 5 / 160 | 0.1% |
| ready_rss_mib | 2 | 0.2% | 1.4% | 1.0% | 1.8% | 0.7% | 1.0% | 3 / 160 | 0.2% |
| request_bytes | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 160 | 0.0% |
| request_bytes_per_turn | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 160 | 0.0% |
| requests | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 160 | 0.0% |
| session_growth_bytes | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1 / 160 | 0.0% |
| side_requests | 2 | n/a | n/a | n/a | n/a | n/a | n/a | 0 / 160 | n/a |
| turn_cpu_ms | 2 | 0.7% | 4.9% | 4.1% | 18.3% | 3.2% | 9.6% | 4 / 160 | 1.3% |
| turn_wall_ms | 2 | 0.9% | 2.1% | 3.0% | 4.1% | 2.3% | 28.0% | 4 / 160 | 2.8% |

A/A gap: the copy's median against the arm's, per cell. A/A floor: the largest deviation from 1 the copy's ratio interval allows (METHODOLOGY section 6). CV: the standard deviation of an arm's rounds over their mean. Outliers: a measured value is an outlier when |x - median| > 5 x 1.4826 x MAD of its arm's values in that cell (needs 4 values; with MAD 0, any different value). Outliers are counted, never removed. Drift: the Theil-Sen trend of an arm's rounds times the rounds spanned, as a share of its median.

### Run 1

- Samples: 160 measured (160 ok, 0 failed), 20 warm-up; telemetry on 160 of 160 ok samples. Sources read: cgroup_throttle, cpufreq, loadavg, meminfo, pressure, proc_stat, schedstat, thermal_throttle, vmstat.
- Calibration: CV 1.7% of cpu_ms on pi-node (gate 5.0%), passed.
- CFS throttling: 0 samples, 0 us in all; the session's cgroup lost 0 us over the whole run.
- Quiet-host gate: 160 passed at once, 0 waited (longest 0.0 s, 0.0 s in all), 0 gave up.
- Steal: 0.000% of the pinned CPUs' capacity. Foreign CPU on the pinned CPUs: p95 0.0% of the sample's CPU time. Clock: largest deviation 0.1% from the median 2800 MHz. iowait is recorded in every sample and never gated.
- Failed samples: 0 arm, 0 infrastructure (the arm is not charged for those); 0 ladder stops (a swarm rung that hit the kernel's limit: a result, not a failure). CPU quota on the arm cgroup or an ancestor: none.
- Flagged samples: 0 of 160.
- Telemetry cost: the collector's thread used 5.38 ms median per sample (worst 8.99 ms), on the runner's CPUs, outside the pinned set.
- Host load before / after: 1.0 / 1.6; pinned CPUs busy over the run: mean 5.9%, max 15.4%.

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

## Failures, cannot-run and egress — PROVISIONAL

### Failed samples (every attempt is in the raw data; none is dropped)

None.

### Cannot run (never counted as a loss, win or tie)

None.

### Egress

Method: socket-audit. Any connection to a non-loopback address fails the sample and the run.
No harness connected outside the loopback.

## Not measured — PROVISIONAL

Projects that resemble Pi implementations and were left out, with the reason:

| project | reason |
|---|---|
| chinudotdev/pi-go | a Go library for building agents, not a runnable coding agent: there is no command to start, so there is nothing to put through a workload |
| qiz029/pi-agent-go | a Go SDK (client) for Pi's RPC protocol: it drives a Pi process, it is not an implementation of Pi; measuring it would measure Pi |
| rcarmo/go-ai | an inference API library (the model layer under rcarmo/gi), not a coding agent |

## Provenance — PROVISIONAL

Pins of the arms exactly as the run recorded them (arms.lock sha256 `549a3d2cc424cd316c5ff3072cf5c0c42bb1d6335775fd7289dd560254e35c33`). A third party who checks out the runner commit gets the same pins, and `buffon rerun` repeats a cell with them.

| arm | exact version | source | checksums | build | manifest sha256 | executable sha256 |
|---|---|---|---|---|---|---|
| pi-bun | 1.3.0 | https://github.com/earendil-works/pi/releases/download/v1.3.0/pi-linux-x64.tar.gz | artifact_sha256 `24f5be328b66d4da36876296989501974f43ab8434fbb57c35c523a3ea505ded` | linux-x64 | `c88c8ca00f64b4f9ea566de62b8a6d8826ef41f96a733e592e84bbc300c7ac6a` | `c2415d6e6f7c67b0a55744c5ace5054936e252fcc3cf56ce087bc314061315ca` |
| pi-node | 1.3.0 | @earendil-works/pi-coding-agent@1.3.0 | integrity `sha512-V/WoCjA2hQSe3QLWIUB24cTRdtEdeLiIzkDqU5RMXV6VWuD+KGZnzVBMhglwdnQTySkehZsjt8a3g6Jd2g4nnw==`<br>package_lock_sha256 `65eacda789c30e1c3859a96eee2fd53cf4a18629d27dcf2aa6d7bdb3da02d719` | node 24.19.0; linux-x64 | `17662e8cd8bd784c3f3dd8a8b4e0864387babb4075d66aa52a60b3b02ba56457` | `e79626f2dd6f94aa45d30f3fa63cd84319a6eefcd150b353cfaf274366926774` |
| pibolt | 0.9.3 | https://github.com/opensec-git/Pi-Bolt/releases/download/bolt-v0.9.3/pi-bolt-linux-x64.tar.gz | artifact_sha256 `333f44ab2a1f602dbeb36228927bcafabd3e132da32be1d6a7deb54bd09e90ce` | linux-x64 | `db1434d8b8ede5b781e9b6cbb7f166bf33c5f8ec6592d3f11e8ebfd3b0047227` | `fe2572130b036a6981b2dcedf3e96e464dcd1749953c9bec47fc8353f0a66c1e` |
| pig-0.4.1 | 0.4.1 | https://github.com/MichaelKinsy/PiG/releases/download/v0.4.1/pig-0.4.1-linux-amd64.tar.gz | artifact_sha256 `3b4de3587cbfb617def483ec62dddcf35827acc3436b1454cc5694c22dcdaf3f` | linux-x64 | `a51378256ee5fdb0af8f190268b7b5e3f6c0d19da03d90b607eaa70efd58a161` | `110ab2ece63f0ac5a70b6bd8901ff0c740ab7172ecbeef33e94aa95e213c7179` |
| pig-tip | 0.5.0+1.3.0 | git 26eaad58e3ec09e25adf74000f79bcd83123aa8c | tree `8b867e1919867ebfc99e50c7a630f27f0ce9be30` | go build -buildvcs=false -trimpath -ldflags -s -w -X github.com/MichaelKinsy/PiG/coding/cli.Build=26eaad58e3ec09e25adf74000f79bcd83123aa8c -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateURL=https://github.com/MichaelKinsy/PiG/releases/latest/download/update.json -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateTrustRoot=LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUNvd0JRWURLMlZ3QXlFQVFBdUtJTHRmc0FpbWdabnRpZ2UydzRGRy9QeDFQeU5HampHYXlEalREM0k9Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQo= -X github.com/MichaelKinsy/PiG/coding/pigletbuild.releaseSourceVersion=v0.5.0 -o /local/kinsy/arena/home/work/buffon-iqoi1hbm/arms/pig-tip-a/bin/pig ./cmd/pig; toolchain go 1.27.2; linux-x64 | `d0032cdda0e713436aa3f6930bb5cac18491bdd91011ffa362100c5bd6b4526f` | `cc759dbd134406f976bb90fbb8fe5a0c3dc4d76a83b7de26d731daa6ef982b21` |

## Arms and environment — PROVISIONAL

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
| idle_after | {"48": 0.0, "49": 0.0, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0166, "114": 0.0, "115": 0.0} |
| load_before | [1.001953125, 1.1708984375, 1.2275390625] |
| load_after | [1.55224609375, 1.798828125, 1.486328125] |
| throttled_usec | 0 |
| cpumon | {"samples": 131, "pinned_busy_mean": 0.05882074256425395, "pinned_busy_max": 0.15375179609797715, "host_busy_mean": 0.007511967865316689} |
| go | null |
| node_js | null |
| python | 3.12.3 |

Variables each harness was started with beyond the host's environment (the throwaway root is `<work>`); credential-looking and proxy variables of the host are removed:

- **pi-bun**: `HOME=<work>/pi-bun-a-resume-n-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-a-resume-n-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-a-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-a-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-a-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-a-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-a-resume-n-openai/home/.local/state`
- **pi-bun-b**: `HOME=<work>/pi-bun-b-resume-n-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-b-resume-n-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-b-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-b-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-b-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-b-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-b-resume-n-openai/home/.local/state`
- **pi-node**: `HOME=<work>/pi-node-a-resume-n-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-iqoi1hbm/arms/pi-node-a/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-iqoi1hbm/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-a-resume-n-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-a-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-a-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-a-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-a-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-a-resume-n-openai/home/.local/state`
- **pi-node-b**: `HOME=<work>/pi-node-b-resume-n-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-iqoi1hbm/arms/pi-node-b/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-iqoi1hbm/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-b-resume-n-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-b-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-b-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-b-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-b-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-b-resume-n-openai/home/.local/state`
- **pibolt**: `HOME=<work>/pibolt-a-resume-n-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-a-resume-n-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-a-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-a-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-a-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-a-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-a-resume-n-openai/home/.local/state`
- **pibolt-b**: `HOME=<work>/pibolt-b-resume-n-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-b-resume-n-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-b-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-b-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-b-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-b-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-b-resume-n-openai/home/.local/state`
- **pig-0.4.1**: `HOME=<work>/pig-0.4.1-a-resume-n-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-iqoi1hbm/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-a-resume-n-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-a-resume-n-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-a-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-a-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-a-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-a-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-a-resume-n-openai/home/.local/state`
- **pig-0.4.1-b**: `HOME=<work>/pig-0.4.1-b-resume-n-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-iqoi1hbm/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-b-resume-n-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-b-resume-n-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-b-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-b-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-b-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-b-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-b-resume-n-openai/home/.local/state`
- **pig-tip**: `HOME=<work>/pig-tip-a-resume-n-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-iqoi1hbm/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-a-resume-n-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-a-resume-n-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-a-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-a-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-a-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-a-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-a-resume-n-openai/home/.local/state`
- **pig-tip-b**: `HOME=<work>/pig-tip-b-resume-n-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-iqoi1hbm/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-b-resume-n-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-b-resume-n-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-b-resume-n-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-b-resume-n-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-b-resume-n-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-b-resume-n-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-b-resume-n-openai/home/.local/state`

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
*PROVISIONAL: generated from 1 run directory by `buffon report`; 4 notes: aa_significant_fraction 6.7%, aa_floor_max 36.7%, outlier_fraction 2.3%, hardware; the raw samples are in each directory's raw.json. The same data as report.html, report.json, summary.csv, rounds.csv, noise.csv and telemetry.csv.*
