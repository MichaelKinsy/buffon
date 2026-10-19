# buffon report — PROVISIONAL

**Trust: Dedicated** (host class A). 1 sample(s) waited for the host to quiet down (longest 2 s); adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 1 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting; the run is not labelled quiet dedicated hardware Every measurement is recorded and shown whatever the label. Headline CPU metric: instructions.

**Run notes (4)**: aa_gap_max 23.4%, aa_floor_max 73.8%, outlier_fraction 2.1%, hardware (usual ranges: docs/HEALTH.md)

> **PROVISIONAL.** Every number in this report is provisional: at least one run was not on quiet dedicated hardware by the runner's own detection. Do not publish or compare it with another report.
>
> Why:
> - run 1: adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge
> - run 1: 1 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting

| field | value |
|---|---|
| reference arm | pi-node |
| arms | pi-bun, pi-node, pibolt, pig-0.4.1, pig-tip (each with an A/A copy `<id>-b` where the run had one) |
| runs | 1 |
| seed | 20261011 |
| token counts | the mock's usage: prompt tokens = request wire bytes / 4, completion tokens = one per streamed part + 12 per tool call; no tokenizer is pinned (METHODOLOGY section 3) |
| arms.lock sha256 | `549a3d2cc424cd316c5ff3072cf5c0c42bb1d6335775fd7289dd560254e35c33` |
| runner commit / tree | `5b3729fca2f0` / `3943ebd8df99` |
| run 1 | site `smc1-socket1` (local), 12 measured + 1 warm-up rounds, harness CPUs `48,49,50,51,112,113,114,115`, mock CPUs `52,116`, Intel(R) Xeon(R) Platinum 8462Y+, kernel 6.8.0-137-generic, meter cgroup-systemd; load before/after 1.5 / 1.4; calibration: CV 1.5% of cpu_ms (gate 5.0%) passed; hardware **provisional**; host class **A**; isolation **uncontained, not comparable** |
| run 1 CPU cost | **instructions** (user and kernel instructions) are the headline CPU metric; CPU time (user + system) and wall time are separate cells |

## Run notes — PROVISIONAL

4 notes: aa_gap_max 23.4%, aa_floor_max 73.8%, outlier_fraction 2.1%, hardware. Run notes describe the conditions of the run. They do not grade it or change a number.

| check | value | usual range | status | meaning |
|---|---:|---:|---|---|
| A/A gap between a harness and its own copy, largest cell | 23.4% | up to 5.0% | note | The largest gap between a harness and its identical copy, and the cell where it happened. overhead/print-ext10 chat teardown_ms pibolt: 23.4%; overhead/rpc-ext5 chat teardown_ms pig-tip: 21.1%; overhead/rpc-ext10 chat teardown_ms pi-node: 13.1% |
| A/A noise floor, worst scored cell | 73.8% | up to 15.0% | note | The same floor in the noisiest cell. Comparisons in that cell resolve only larger differences. overhead/rpc-ext5 chat teardown_ms: 73.8%; overhead/rpc-ext10 chat teardown_ms: 57.8%; overhead/rpc-ext10 chat teardown_ms: 51.2% |
| Measured values flagged by the MAD rule | 2.1% | up to 2.0% | note | Share of measured values far from the median of their cell. Outliers are counted and never removed. overhead/print-ext5 chat cpu_ms pi-bun: 3; overhead/print-ext5 chat instructions pi-bun: 3; overhead/pty chat input_to_request_ms pi-node: 3 |
| Quiet dedicated hardware by the runner's own detection | no | yes | note | On shared hardware other work can disturb the numbers. run 1 not on quiet dedicated hardware: adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 1 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting |
| Calibration: CV of the reference's CPU time between identical runs | 1.5% | up to 2.0% | ok | How much the reference's CPU time varied between identical calibration runs. Lower means a quieter host. |
| A/A CV of CPU metrics, median over arms and cells | 1.5% | up to 2.0% | ok | How much CPU time varies from round to round for one harness. Lower means a quieter host. |
| A/A pairs with a significant gap (paired p < 0.05, before Holm) that is also larger than 1% | 4.2% | up to 5.0% | ok | Share of harness and copy pairs that differ by more than 1% and also pass a significance test. A gap under 1% on a steady counter is not counted. About 5% can happen by chance. |
| A/A gap between a harness and its own copy, median over cells | 0.4% | up to 1.0% | ok | The usual gap between a harness and its identical copy. A real difference between two harnesses should be larger than this. |
| A/A noise floor, median over scored cells | 1.7% | up to 3.0% | ok | The smallest difference the identical copies cannot tell from noise, in the usual cell. Smaller differences than this are not resolved. |
| Measured samples with at least one host flag | 3.8% | up to 5.0% | ok | Share of samples where the host showed a disturbance: throttling, foreign CPU, steal, a clock change, swap or a memory event. |
| Measured samples with CFS throttling (arm cgroup, every ancestor, session) | 0 | up to 0 | ok | Samples where the kernel held the process back for a CPU quota. Their time then describes the quota, not the harness. |
| Steal: share of the pinned CPUs' capacity taken by a hypervisor | 0.0% | up to 0.1% | ok | Share of the pinned CPUs' time that a hypervisor took away. It only matters on virtual machines. |
| Foreign CPU on the pinned CPUs during a sample, p95 over samples, as a share of the sample's CPU time | 0.0% | up to 1.0% | ok | CPU time that other processes used on the pinned cores during a sample, as a share of the sample's own CPU time (95th percentile). |
| Samples that waited more than 1 s for the host to quiet down | 0.2% | up to 1.0% | ok | Share of samples that had to wait for the quiet-host gate. A busy host makes the gate wait. |
| Samples for which the host never quieted down | 0 | up to 0 | ok | Samples that did not start because the host stayed busy. They are not in the numbers. |
| Effective clock: largest deviation of a sample's mean MHz from the run median | 0.1% | up to 2.0% | ok | How far a sample's mean CPU clock moved from the run median. A moving clock changes CPU time for the same work. |
| Infrastructure failures (envelope OOM, no process started, runner fault) over measured samples | 0.0% | up to 0.0% | ok | Share of samples that failed because of the host or the runner. They are never charged to a harness. |
| Arm failures over measured samples (a swarm ladder's designed stops are results and not counted) | 0.0% | up to 2.0% | ok | Share of samples where the harness itself failed. A scale sample that stopped because the kernel's limit was reached (stop_cause oom, pids or timeout) is a result and is in neither the failures nor the samples counted; a scale error stop is a failure. |
| Drift: median absolute change over the run of an arm's value, over cells | 0.5% | up to 2.0% | ok | How much a harness's value moved from the start of the run to the end. Drift means the host changed during the run. |
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
> - run 1: adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge
> - run 1: 1 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting

**Trust: Dedicated** (host class A). 1 sample(s) waited for the host to quiet down (longest 2 s); adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 1 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting; the run is not labelled quiet dedicated hardware

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 4.

### Pi-faithful entries (faithfulness 90 or more) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** PROVISIONAL | 100 | 2/9 (7 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

### Faithfulness not measured (ranked apart until it is) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pibolt (Pi-Bolt) | **89 (B+)** PROVISIONAL | not measured | 2/9 (7 not run) | release archive; 267.5 MB; linux-x64 | 89-89 | 82-96, rank 1-1 |
| 2 | pig-tip (PiG 0.5.0) | **76 (C)** PROVISIONAL | not measured | 2/9 (7 not run) | source build; 70.2 MB; linux-x64 | 76-77 | 69-79, rank 2-2 |
| 3 | pi-bun (Pi on Bun) | **67 (D+)** PROVISIONAL | not measured | 2/9 (7 not run) | release archive; 114.5 MB; linux-x64 | 67-67 | 66-68, rank 3-3 |
| 4 | pig-0.4.1 (PiG 0.4.1) | **66 (D)** PROVISIONAL | not measured | 2/9 (7 not run) | release archive; 63.8 MB; linux-x64 | 66-66 | 57-66, rank 4-4 |

### Below the reference — PROVISIONAL

- **pi-bun**: core 66 (D) at 1.28x the reference's cost, ext10 68 (D+) at 1.15x the reference's cost
- **pig-0.4.1**: ext10 47 (F) at 4.89x the reference's cost
- **pig-tip**: ext10 61 (D-) at 1.82x the reference's cost

*PROVISIONAL: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*


## Summary by axis — PROVISIONAL

Counts of cells where the arm is measurably worse (loss), inconclusive, inside the A/A floor (no measurable difference) or measurably better (win) than the reference `pi-node`. A "cannot run" cell is never counted. Coverage is the cells the arm produced values for out of all cells in the report.

| arm | coverage | family | losses | inconclusive | no measurable difference | wins |
|---|---|---|---:|---:|---:|---:|
| pi-bun | 113/113 | overhead | 57 | 1 | 12 | 35 |
| pibolt | 113/113 | overhead | 12 | 0 | 6 | 87 |
| pig-0.4.1 | 113/113 | overhead | 78 | 0 | 7 | 20 |
| pig-tip † | 113/113 | overhead | 52 | 0 | 10 | 43 |

† `pig-tip`: This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

## Races — PROVISIONAL

A race climbs a ladder of growing load. Every harness gets the same ladder and the same limits; the line says how far it got and why it stopped. Finished harnesses rank first by time, then stopped ones by how far they got.

### Scales with extensions: 0 > 5 > 10 > 50 > 100 (bare)

Finish line: 100. Limits: every harness bare (not in a container), 8 pinned CPUs: uncontained, not comparable with a containerised race.

| rank | harness | outcome | speed | memory peak / average | reliability | CPU time |
|---:|---|---|---|---|---|---|
| 1 | pi-bun | Stopped at 0 after 0.0 s: error: no sample was taken at this rung | 0 of 5 rungs | 126 MiB / 121 MiB | 0 of 16 samples failed; lost work 0 | 1.9 s |
| 2 | pi-node | Stopped at 0 after 0.0 s: error: no sample was taken at this rung | 0 of 5 rungs | 107 MiB / 105 MiB | 0 of 16 samples failed; lost work 0 | 1.3 s |
| 3 | pibolt | Stopped at 0 after 0.0 s: error: no sample was taken at this rung | 0 of 5 rungs | 34 MiB / 32 MiB | 0 of 16 samples failed; lost work 0 | 0.2 s |
| 4 | pig-0.4.1 | Stopped at 0 after 0.0 s: error: no sample was taken at this rung | 0 of 5 rungs | 521 MiB / 423 MiB | 0 of 16 samples failed; lost work 0 | 3.6 s |
| 5 | pig-tip | Stopped at 0 after 0.0 s: error: no sample was taken at this rung | 0 of 5 rungs | 242 MiB / 218 MiB | 0 of 16 samples failed; lost work 0 | 1.8 s |

## pi-bun against pi-node — PROVISIONAL

### Losses (measurably worse than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/pty | chat | first_frame_ms | wall | ms | 8 | 296 | 470 | 1.59 [1.57, 1.64] | 3.7% | 3.0% | 2.8% / 0.4% | 9.46 / 1.71 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_frame_ms` |
| overhead/pty | chat | ready_ms | wall | ms | 8 | 332 | 515 | 1.55 [1.54, 1.57] | 2.2% | 2.0% | 1.4% / 0.5% | 4.3 / 3.47 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_ms` |
| overhead/pty | chat | first_input_accepted_ms | wall | ms | 8 | 331 | 511 | 1.54 [1.53, 1.56] | 3.1% | 4.8% | 1.4% / 0.4% | 4 / 2.91 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_input_accepted_ms` |
| overhead/pty | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 454 | 694 | 1.53 [1.51, 1.54] | 2.8% | 2.5% | 1.7% / 0.5% | 9.44 / 3.58 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_cpu_ms` |
| overhead/pty | chat | cpu_ms | CPU | ms of CPU time | 8 | 536 | 815 | 1.52 [1.48, 1.54] | 4.1% | 6.2% | 4.4% / 0.4% | 13.7 / 2.36 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cpu_ms` |
| overhead/rpc-ext10 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 606 | 917 | 1.51 [1.47, 1.55] | 5.3% | 3.0% | 2.0% / 2.7% | 9.15 / 31.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_cpu_ms` |
| overhead/pty | chat | cycles | CPU | cycles | 8 | 1471.27M | 2226.00M | 1.51 [1.47, 1.53] | 4.2% | 6.3% | 4.4% / 0.5% | 37,355,843 / 8,721,196 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cycles` |
| overhead/rpc-ext10 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 605 | 913 | 1.51 [1.46, 1.54] | 5.3% | 3.0% | 2.0% / 2.7% | 9.46 / 31.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.6 | 17.4 | 1.5 [1.44, 1.58] | 7.5% | 5.4% | 4.3% / 5.3% | 0.459 / 1.16 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_ms` |
| overhead/print-ext10 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 647 | 966 | 1.49 [1.44, 1.52] | 5.9% | 2.3% | 1.5% / 2.4% | 10.4 / 40.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_cpu_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 834 | 1.49 [1.45, 1.54] | 5.2% | 1.6% | 1.3% / 2.7% | 10.5 / 36.3 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_cpu_ms` |
| overhead/rpc-ext5 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 829 | 1.48 [1.44, 1.54] | 5.6% | 1.6% | 1.3% / 2.9% | 10.8 / 40.2 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_cpu_ms` |
| overhead/print-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 676 | 995 | 1.47 [1.42, 1.5] | 5.3% | 2.3% | 1.6% / 2.2% | 10.6 / 37.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cpu_ms` |
| overhead/print-ext10 | chat | cycles | CPU | cycles | 8 | 1876.04M | 2732.70M | 1.46 [1.41, 1.49] | 5.4% | 2.3% | 1.6% / 2.3% | 29,682,222 / 103,688,689 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cycles` |
| overhead/rpc-ext5 | chat | ready_ms | wall | ms | 8 | 418 | 605 | 1.45 [1.43, 1.49] | 3.8% | 1.0% | 0.7% / 2.0% | 3.69 / 16.1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_ms | wall | ms | 8 | 421 | 608 | 1.45 [1.43, 1.49] | 3.7% | 1.0% | 0.7% / 2.0% | 3.67 / 15.8 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_ms` |
| overhead/rpc-ext10 | chat | ready_ms | wall | ms | 8 | 441 | 633 | 1.44 [1.41, 1.46] | 3.4% | 1.8% | 1.7% / 2.1% | 7.32 / 13.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_ms` |
| overhead/rpc-ext10 | chat | extensions_ready_ms | wall | ms | 8 | 444 | 637 | 1.43 [1.4, 1.46] | 3.4% | 1.9% | 1.7% / 2.1% | 7.53 / 13.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_ms` |
| overhead/pty | chat | peak_mem_mib | memory | MiB | 8 | 72.7 | 104 | 1.43 [1.42, 1.44] | 2.3% | 2.0% | 0.7% / 0.2% | 0.449 / 0.132 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_mem_mib` |
| overhead/print-ext10 | chat | first_request_ms | wall | ms | 8 | 470 | 670 | 1.43 [1.38, 1.44] | 4.5% | 1.5% | 1.2% / 1.6% | 8.61 / 19.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_ms` |
| overhead/pty | chat | instructions | CPU | instructions | 8 | 2837.83M | 4034.94M | 1.42 [1.42, 1.42] | 1.7% | 4.2% | 2.8% / 0.1% | 6,773,267 / 6,474,607 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#instructions` |
| overhead/print-ext5 | chat | first_request_ms | wall | ms | 8 | 445 | 631 | 1.42 [1.4, 1.44] | 1.9% | 1.7% | 1.4% / 1.3% | 7.57 / 8.44 | 1 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_ms` |
| overhead/print-ext5 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 606 | 858 | 1.42 [1.4, 1.45] | 3.1% | 2.8% | 1.9% / 1.7% | 20 / 11.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_cpu_ms` |
| overhead/rpc-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 950 | 1,338 | 1.41 [1.35, 1.42] | 4.2% | 3.6% | 2.3% / 2.5% | 26.1 / 16.8 | 1 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cpu_ms` |
| overhead/rpc-ext10 | chat | cycles | CPU | cycles | 8 | 2622.26M | 3678.67M | 1.4 [1.35, 1.41] | 4.5% | 3.7% | 2.3% / 2.6% | 69,450,474 / 56,284,432 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cycles` |
| overhead/print-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 633 | 885 | 1.4 [1.38, 1.43] | 3.1% | 2.8% | 1.8% / 1.7% | 20.4 / 8.67 | 0 / 3 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cpu_ms` |
| overhead/print-ext10 | chat | wall_ms | wall | ms | 8 | 495 | 692 | 1.4 [1.36, 1.41] | 4.0% | 1.5% | 1.2% / 1.5% | 8.64 / 17.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#wall_ms` |
| overhead/print-ext5 | chat | wall_ms | wall | ms | 8 | 470 | 654 | 1.39 [1.38, 1.4] | 1.8% | 1.7% | 1.3% / 1.4% | 8.05 / 5.42 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#wall_ms` |
| overhead/print-ext5 | chat | cycles | CPU | cycles | 8 | 1755.56M | 2429.94M | 1.38 [1.37, 1.41] | 3.0% | 2.8% | 1.9% / 1.8% | 56,196,843 / 26,449,710 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cycles` |
| overhead/rpc-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 901 | 1,229 | 1.36 [1.35, 1.43] | 4.4% | 1.3% | 1.1% / 2.8% | 13.2 / 44.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cpu_ms` |
| overhead/rpc-ext5 | chat | cycles | CPU | cycles | 8 | 2479.88M | 3371.03M | 1.36 [1.34, 1.43] | 4.4% | 1.3% | 1.1% / 2.8% | 33,110,128 / 125,692,079 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cycles` |
| overhead/print-ext10 | chat | instructions | CPU | instructions | 8 | 3541.30M | 4732.32M | 1.34 [1.33, 1.34] | 0.3% | 0.3% | 0.2% / 0.5% | 15,071,687 / 7,405,424 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#instructions` |
| overhead/rpc-ext10 | chat | instructions | CPU | instructions | 8 | 4737.77M | 6318.24M | 1.33 [1.32, 1.34] | 1.1% | 0.3% | 0.3% / 0.6% | 10,466,170 / 65,841,200 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#instructions` |
| overhead/rpc-ext5 | chat | instructions | CPU | instructions | 8 | 4464.93M | 5897.57M | 1.32 [1.31, 1.33] | 1.0% | 0.5% | 0.2% / 0.3% | 19,068,014 / 20,073,423 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#instructions` |
| overhead/print-ext5 | chat | instructions | CPU | instructions | 8 | 3366.27M | 4388.41M | 1.3 [1.28, 1.31] | 1.7% | 0.4% | 0.3% / 0.8% | 12,376,272 / 68,359,196 | 0 / 3 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#instructions` |
| overhead/rpc-ext5 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.9 | 15.1 | 1.27 [1.22, 1.42] | 10.3% | 4.1% | 1.5% / 9.4% | 0.119 / 1.4 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_mean_ms | wall | ms | 8 | 13.8 | 17.3 | 1.26 [1.14, 1.32] | 8.5% | 6.5% | 4.6% / 5.1% | 1.11 / 1.52 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc-ext5 | chat | turn_cpu_mean_ms | wall | ms | 8 | 12.9 | 15.9 | 1.23 [1.2, 1.34] | 9.3% | 2.8% | 2.9% / 5.1% | 0.576 / 0.636 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_mean_ms` |
| overhead/pty | chat | ready_rss_mib | memory | MiB | 8 | 121 | 144 | 1.19 [1.18, 1.2] | 1.6% | 0.9% | 0.6% / 0.4% | 0.711 / 0.416 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_rss_mib` |
| overhead/rpc-ext5 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.0 | 19.0 | 1.19 [1.16, 1.24] | 6.7% | 3.6% | 3.1% / 3.6% | 0.25 / 1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_host_cpu_ms` |
| overhead/print-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 106 | 126 | 1.18 [1.17, 1.19] | 1.0% | 1.1% | 0.7% / 0.2% | 0.903 / 0.333 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_mem_mib` |
| overhead/rpc-ext10 | chat | turn_wall_ms | wall | ms | 8 | 8.83 | 10.4 | 1.18 [1.09, 1.3] | 9.7% | 3.6% | 2.8% / 5.8% | 0.396 / 0.714 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_wall_ms` |
| overhead/rpc-ext10 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.8 | 19.8 | 1.18 [1.11, 1.25] | 6.1% | 6.0% | 3.9% / 4.4% | 1.12 / 0.625 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_host_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.89 | 4.59 | 1.18 [1.11, 1.26] | 8.7% | 5.7% | 4.2% / 5.8% | 0.182 / 0.463 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_turn_gap_ms` |
| overhead/rpc-ext5 | chat | turn_wall_ms | wall | ms | 8 | 8.35 | 9.69 | 1.16 [1.13, 1.2] | 8.6% | 2.1% | 0.7% / 4.4% | 0.0553 / 0.402 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_wall_ms` |
| overhead/pty | chat | peak_rss_mib | memory | MiB | 8 | 126 | 144 | 1.15 [1.14, 1.15] | 1.4% | 0.9% | 0.3% / 0.4% | 0.38 / 0.416 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_rss_mib` |
| overhead/print-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 104 | 116 | 1.12 [1.11, 1.12] | 0.9% | 1.0% | 0.6% / 0.3% | 0.879 / 0.354 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_mem_mib` |
| overhead/pty | chat | ready_pss_mib | memory | MiB | 8 | 116 | 124 | 1.08 [1.06, 1.09] | 1.6% | 1.0% | 0.3% / 1.5% | 0.6 / 3.23 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_pss_mib` |
| overhead/rpc-ext10 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 149 | 159 | 1.07 [1.06, 1.07] | 0.6% | 0.5% | 0.4% / 0.2% | 0.742 / 0.257 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_pss_mib` |
| overhead/rpc-ext10 | chat | ready_pss_mib | memory | MiB | 8 | 149 | 158 | 1.06 [1.06, 1.07] | 0.6% | 0.5% | 0.4% / 0.2% | 0.738 / 0.264 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_pss_mib` |
| overhead/rpc-ext10 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 154 | 163 | 1.06 [1.05, 1.06] | 0.6% | 0.5% | 0.3% / 0.2% | 0.742 / 0.247 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext10 | chat | ready_rss_mib | memory | MiB | 8 | 154 | 163 | 1.06 [1.05, 1.06] | 0.6% | 0.5% | 0.3% / 0.2% | 0.738 / 0.254 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_rss_mib` |
| overhead/print-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 156 | 164 | 1.05 [1.05, 1.06] | 1.5% | 1.3% | 0.8% / 0.3% | 1.2 / 0.884 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_rss_mib` |
| overhead/rpc-ext5 | chat | ready_pss_mib | memory | MiB | 8 | 146 | 150 | 1.03 [1.02, 1.05] | 2.6% | 0.5% | 0.3% / 1.1% | 0.485 / 2.39 | 0 / 0 | 0.0312 | yes ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_pss_mib` |
| overhead/rpc-ext5 | chat | ready_rss_mib | memory | MiB | 8 | 151 | 155 | 1.02 [1.01, 1.04] | 2.1% | 0.5% | 0.3% / 1.1% | 0.455 / 2.74 | 0 / 0 | 0.0312 | yes ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_rss_mib` |
| overhead/rpc-ext5 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 151 | 155 | 1.02 [1.01, 1.04] | 2.0% | 0.5% | 0.3% / 1.0% | 0.462 / 2.69 | 0 / 0 | 0.0312 | yes ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext5 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 146 | 149 | 1.02 [1.02, 1.03] | 1.5% | 0.5% | 0.3% / 0.9% | 0.489 / 1.32 | 0 / 0 | 0.0312 | yes ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_pss_mib` |

### Inconclusive (outside the floor, interval includes 1) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 153 | 155 | 1.02 [0.998, 1.04] | 1.4% | 1.4% | 1.0% / 1.1% | 1.62 / 2.02 | 0 / 0 | 0.0625 | yes ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_rss_mib` |

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-ext10 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#requests` |
| overhead/print-ext10 | chat | teardown_ms | wall | ms | 8 | 24.7 | 22.3 | 0.904 [0.873, 0.948] | 20.7% | 2.9% | 3.3% / 4.7% | 0.577 / 1.3 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#teardown_ms` |
| overhead/print-ext5 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#requests` |
| overhead/print-ext5 | chat | teardown_ms | wall | ms | 8 | 24.2 | 21.9 | 0.905 [0.81, 0.922] | 13.1% | 3.4% | 1.7% / 8.5% | 0.438 / 2.47 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#teardown_ms` |
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#requests` |
| overhead/pty | chat | input_to_request_ms | wall | ms | 8 | 33.8 | 37.6 | 1.11 [0.788, 1.14] | 42.4% | 18.0% | 18.7% / 1.3% | 13.9 / 0.448 | 3 / 0 | 0.773 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_request_ms` |
| overhead/pty | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#requests` |
| overhead/rpc-ext10 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#requests` |
| overhead/rpc-ext10 | chat | teardown_ms | wall | ms | 8 | 11.8 | 12.7 | 1.07 [0.957, 1.12] | 27.4% | 16.2% | 7.1% / 8.0% | 1.35 / 1.11 | 2 / 0 | 0.562 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#teardown_ms` |
| overhead/rpc-ext5 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#requests` |
| overhead/rpc-ext5 | chat | teardown_ms | wall | ms | 8 | 13.0 | 12.5 | 0.959 [0.889, 1.03] | 21.3% | 6.5% | 5.9% / 6.2% | 1.36 / 0.709 | 0 / 0 | 0.344 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#teardown_ms` |
| overhead/rpc-ext5 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.86 | 4.18 | 1.08 [1.01, 1.16] | 18.9% | 1.1% | 0.8% / 7.6% | 0.0326 / 0.342 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_turn_gap_ms` |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-ext10 | chat | request_bytes | wire | bytes | 8 | 8,355 | 8,225 | 0.984 [0.984, 0.984] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes` |
| overhead/print-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 8,355 | 8,225 | 0.984 [0.984, 0.984] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes_per_turn` |
| overhead/print-ext5 | chat | request_bytes | wire | bytes | 8 | 7,209 | 7,079 | 0.982 [0.982, 0.982] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes` |
| overhead/print-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 7,209 | 7,079 | 0.982 [0.982, 0.982] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes_per_turn` |
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 33,954 | 23,718 | 0.699 [0.693, 0.703] | 4.5% | 3.0% | 1.6% / 0.6% | 94.9 / 197 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,085 | 23,904 | 0.701 [0.696, 0.705] | 4.5% | 2.8% | 1.6% / 0.6% | 96.4 / 202 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,482 | 31,212 | 0.88 [0.871, 0.891] | 4.3% | 2.7% | 1.6% / 1.2% | 85.1 / 625 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99037.28M | 86048.78M | 0.869 [0.86, 0.881] | 4.3% | 2.7% | 1.6% / 1.2% | 228,928,257 / 1,774,001,635 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402328.61M | 325248.21M | 0.808 [0.803, 0.811] | 0.7% | 0.1% | 0.1% / 0.6% | 190,002,217 / 2,123,033,669 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 543 | 325 | 0.599 [0.572, 0.615] | 9.5% | 27.6% | 31.0% / 3.6% | 4.28 / 10.1 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 366 | 0.634 [0.611, 0.649] | 8.4% | 24.9% | 28.0% / 3.1% | 3.71 / 10.2 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,456 | 24,438 | 0.709 [0.704, 0.714] | 4.4% | 2.8% | 1.6% / 0.6% | 92.3 / 201 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,065 | 1,490 | 0.722 [0.705, 0.733] | 2.9% | 2.5% | 1.0% / 1.5% | 29.5 / 30 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,098 | 1,540 | 0.734 [0.717, 0.744] | 2.9% | 2.4% | 0.9% / 1.5% | 25.8 / 30.8 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,743 | 2,482 | 0.905 [0.88, 0.915] | 3.1% | 1.9% | 0.7% / 1.8% | 14.7 / 56.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7657.92M | 6817.19M | 0.89 [0.865, 0.9] | 3.1% | 1.9% | 0.7% / 1.8% | 41,528,431 / 163,690,618 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28093.14M | 22889.78M | 0.815 [0.81, 0.815] | 0.9% | 0.2% | 0.1% / 0.6% | 21,502,604 / 87,680,951 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 188 | 0.721 [0.696, 0.737] | 3.9% | 1.0% | 0.8% / 3.0% | 1.12 / 8.71 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 228 | 0.74 [0.718, 0.758] | 3.5% | 0.8% | 0.7% / 2.5% | 1.3 / 9.74 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,427 | 2,046 | 0.843 [0.825, 0.851] | 2.2% | 2.0% | 0.8% / 1.1% | 25.1 / 33.1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_wall_ms` |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 285,590 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 71,398 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes_per_turn` |
| overhead/pty | chat | input_to_reply_visible_ms | wall | ms | 8 | 62.0 | 50.5 | 0.815 [0.798, 0.825] | 2.9% | 1.2% | 1.0% / 1.2% | 0.636 / 0.645 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_reply_visible_ms` |
| overhead/pty | chat | request_bytes | wire | bytes | 8 | 6,006 | 5,876 | 0.978 [0.978, 0.978] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes` |
| overhead/pty | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,006 | 5,876 | 0.978 [0.978, 0.978] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 148 | 141 | 0.952 [0.946, 0.958] | 1.5% | 3.4% | 0.4% / 0.7% | 0.893 / 1.42 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_mem_mib` |
| overhead/rpc-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 199 | 183 | 0.92 [0.916, 0.922] | 0.6% | 2.6% | 0.2% / 0.5% | 0.444 / 1.02 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_rss_mib` |
| overhead/rpc-ext10 | chat | request_bytes | wire | bytes | 8 | 1.21M | 1.20M | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes` |
| overhead/rpc-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 60,364 | 60,084 | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext10 | chat | turn_harness_added_ms | wall | ms | 8 | 1.3 | 1.04 | 0.806 [0.737, 0.885] | 14.7% | 9.6% | 6.3% / 7.3% | 0.129 / 0.0789 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_harness_added_ms` |
| overhead/rpc-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 146 | 131 | 0.895 [0.889, 0.907] | 3.7% | 3.5% | 0.6% / 0.6% | 1.55 / 1.3 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_mem_mib` |
| overhead/rpc-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 198 | 174 | 0.879 [0.874, 0.884] | 2.6% | 2.5% | 0.4% / 0.4% | 0.994 / 1.27 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_rss_mib` |
| overhead/rpc-ext5 | chat | request_bytes | wire | bytes | 8 | 1.16M | 1.16M | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes` |
| overhead/rpc-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 58,052 | 57,772 | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext5 | chat | turn_harness_added_ms | wall | ms | 8 | 1.22 | 0.907 | 0.742 [0.713, 0.919] | 14.0% | 3.9% | 3.1% / 10.3% | 0.0638 / 0.0707 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_harness_added_ms` |

## pibolt against pi-node — PROVISIONAL

### Losses (measurably worse than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/pty | chat | request_bytes | wire | bytes | 8 | 6,006 | 7,923 | 1.32 [1.32, 1.32] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes` |
| overhead/pty | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,006 | 7,923 | 1.32 [1.32, 1.32] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes_per_turn` |
| overhead/print-ext5 | chat | request_bytes | wire | bytes | 8 | 7,209 | 9,126 | 1.27 [1.27, 1.27] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes` |
| overhead/print-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 7,209 | 9,126 | 1.27 [1.27, 1.27] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes_per_turn` |
| overhead/print-ext10 | chat | request_bytes | wire | bytes | 8 | 8,355 | 10,272 | 1.23 [1.23, 1.23] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes` |
| overhead/print-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 8,355 | 10,272 | 1.23 [1.23, 1.23] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext5 | chat | request_bytes | wire | bytes | 8 | 1.16M | 1.24M | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes` |
| overhead/rpc-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 58,052 | 61,866 | 1.07 [1.07, 1.07] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext10 | chat | request_bytes | wire | bytes | 8 | 1.21M | 1.28M | 1.06 [1.06, 1.06] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes` |
| overhead/rpc-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 60,364 | 64,178 | 1.06 [1.06, 1.06] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes_per_turn` |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 293,778 | 1.03 [1.03, 1.03] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 73,444 | 1.03 [1.03, 1.03] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-ext10 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#requests` |
| overhead/print-ext5 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#requests` |
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#requests` |
| overhead/pty | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#requests` |
| overhead/rpc-ext10 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#requests` |
| overhead/rpc-ext5 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#requests` |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 676 | 109 | 0.162 [0.16, 0.171] | 7.8% | 2.3% | 1.6% / 3.0% | 10.6 / 3.71 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cpu_ms` |
| overhead/print-ext10 | chat | cycles | CPU | cycles | 8 | 1876.04M | 292.01M | 0.156 [0.154, 0.164] | 6.4% | 2.3% | 1.6% / 3.0% | 29,682,222 / 7,222,837 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cycles` |
| overhead/print-ext10 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 647 | 104 | 0.16 [0.158, 0.169] | 6.6% | 2.3% | 1.5% / 3.0% | 10.4 / 3.05 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_cpu_ms` |
| overhead/print-ext10 | chat | first_request_ms | wall | ms | 8 | 470 | 96.4 | 0.205 [0.202, 0.211] | 5.1% | 1.5% | 1.2% / 1.9% | 8.61 / 1.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_ms` |
| overhead/print-ext10 | chat | instructions | CPU | instructions | 8 | 3541.30M | 490.69M | 0.139 [0.138, 0.139] | 1.0% | 0.3% | 0.2% / 0.1% | 15,071,687 / 938,244 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#instructions` |
| overhead/print-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 106 | 34.2 | 0.322 [0.319, 0.324] | 1.0% | 1.1% | 0.7% / 0.5% | 0.903 / 0.194 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_mem_mib` |
| overhead/print-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 156 | 109 | 0.7 [0.697, 0.705] | 0.9% | 1.3% | 0.8% / 0.3% | 1.2 / 0.213 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_rss_mib` |
| overhead/print-ext10 | chat | teardown_ms | wall | ms | 8 | 24.7 | 5.53 | 0.224 [0.188, 0.233] | 35.3% | 2.9% | 3.3% / 10.9% | 0.577 / 0.989 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#teardown_ms` |
| overhead/print-ext10 | chat | wall_ms | wall | ms | 8 | 495 | 102 | 0.206 [0.203, 0.213] | 6.4% | 1.5% | 1.2% / 2.1% | 8.64 / 2.75 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#wall_ms` |
| overhead/print-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 633 | 87.3 | 0.138 [0.136, 0.141] | 3.1% | 2.8% | 1.8% / 0.6% | 20.4 / 0.867 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cpu_ms` |
| overhead/print-ext5 | chat | cycles | CPU | cycles | 8 | 1755.56M | 231.47M | 0.132 [0.13, 0.135] | 3.0% | 2.8% | 1.9% / 0.6% | 56,196,843 / 1,816,566 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cycles` |
| overhead/print-ext5 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 606 | 82.3 | 0.136 [0.134, 0.139] | 3.1% | 2.8% | 1.9% / 0.5% | 20 / 0.529 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_cpu_ms` |
| overhead/print-ext5 | chat | first_request_ms | wall | ms | 8 | 445 | 75.9 | 0.171 [0.167, 0.171] | 2.2% | 1.7% | 1.4% / 0.5% | 7.57 / 0.557 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_ms` |
| overhead/print-ext5 | chat | instructions | CPU | instructions | 8 | 3366.27M | 375.20M | 0.111 [0.111, 0.112] | 1.0% | 0.4% | 0.3% / 0.1% | 12,376,272 / 299,624 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#instructions` |
| overhead/print-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 104 | 30.2 | 0.291 [0.29, 0.293] | 1.3% | 1.0% | 0.6% / 0.8% | 0.879 / 0.183 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_mem_mib` |
| overhead/print-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 153 | 104 | 0.683 [0.675, 0.687] | 1.4% | 1.4% | 1.0% / 0.2% | 1.62 / 0.368 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_rss_mib` |
| overhead/print-ext5 | chat | teardown_ms | wall | ms | 8 | 24.2 | 4.57 | 0.189 [0.186, 0.222] | 30.0% | 3.4% | 1.7% / 10.7% | 0.438 / 0.559 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#teardown_ms` |
| overhead/print-ext5 | chat | wall_ms | wall | ms | 8 | 470 | 80.9 | 0.172 [0.169, 0.175] | 3.6% | 1.7% | 1.3% / 1.0% | 8.05 / 0.955 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#wall_ms` |
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 33,954 | 3.85 | 0.000113 [0.000111, 0.000116] | 4.5% | 3.0% | 1.6% / 4.3% | 94.9 / 0.0949 | 1 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,085 | 188 | 0.0055 [0.00549, 0.00555] | 4.5% | 2.8% | 1.6% / 0.6% | 96.4 / 1.71 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,482 | 347 | 0.00978 [0.00975, 0.00986] | 4.3% | 2.7% | 1.6% / 0.8% | 85.1 / 2.27 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99037.28M | 883.20M | 0.00892 [0.00887, 0.00897] | 4.3% | 2.7% | 1.6% / 0.7% | 228,928,257 / 6,454,326 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402328.61M | 1761.79M | 0.00438 [0.00437, 0.0044] | 0.8% | 0.1% | 0.1% / 0.6% | 190,002,217 / 9,427,828 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 543 | 47.1 | 0.0868 [0.0858, 0.0879] | 1.6% | 27.6% | 31.0% / 0.4% | 4.28 / 0.246 | 1 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 117 | 0.202 [0.2, 0.203] | 1.4% | 24.9% | 28.0% / 0.1% | 3.71 / 0.192 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,456 | 253 | 0.00733 [0.0073, 0.00745] | 4.4% | 2.8% | 1.6% / 0.9% | 92.3 / 3.17 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,065 | 4.09 | 0.00198 [0.00186, 0.00215] | 13.7% | 2.5% | 1.0% / 6.5% | 29.5 / 0.412 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,098 | 50.0 | 0.0238 [0.0235, 0.0248] | 3.4% | 2.4% | 0.9% / 2.3% | 25.8 / 1.08 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,743 | 131 | 0.0479 [0.0476, 0.0481] | 2.3% | 1.9% | 0.7% / 1.2% | 14.7 / 0.977 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7657.92M | 334.36M | 0.0437 [0.0435, 0.0439] | 3.0% | 1.9% | 0.7% / 1.3% | 41,528,431 / 2,835,584 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28093.14M | 605.43M | 0.0216 [0.0215, 0.0217] | 2.2% | 0.2% | 0.1% / 1.0% | 21,502,604 / 3,571,575 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 35.8 | 0.137 [0.136, 0.138] | 1.2% | 1.0% | 0.8% / 0.7% | 1.12 / 0.352 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 95.8 | 0.31 [0.308, 0.335] | 8.9% | 0.8% | 0.7% / 4.5% | 1.3 / 2.57 | 1 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,427 | 96.2 | 0.0396 [0.0392, 0.0428] | 9.1% | 2.0% | 0.8% / 4.6% | 25.1 / 2.64 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_wall_ms` |
| overhead/pty | chat | cpu_ms | CPU | ms of CPU time | 8 | 536 | 55.1 | 0.103 [0.1, 0.104] | 4.1% | 6.2% | 4.4% / 0.9% | 13.7 / 0.767 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cpu_ms` |
| overhead/pty | chat | cycles | CPU | cycles | 8 | 1471.27M | 139.57M | 0.0949 [0.0932, 0.0961] | 4.2% | 6.3% | 4.4% / 0.7% | 37,355,843 / 1,559,908 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cycles` |
| overhead/pty | chat | first_frame_ms | wall | ms | 8 | 296 | 36.5 | 0.123 [0.122, 0.127] | 3.7% | 3.0% | 2.8% / 0.7% | 9.46 / 0.18 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_frame_ms` |
| overhead/pty | chat | first_input_accepted_ms | wall | ms | 8 | 331 | 37.3 | 0.113 [0.112, 0.114] | 3.1% | 4.8% | 1.4% / 0.7% | 4 / 0.0621 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_input_accepted_ms` |
| overhead/pty | chat | input_to_reply_visible_ms | wall | ms | 8 | 62.0 | 19.5 | 0.315 [0.311, 0.318] | 2.1% | 1.2% | 1.0% / 1.0% | 0.636 / 0.182 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_reply_visible_ms` |
| overhead/pty | chat | input_to_request_ms | wall | ms | 8 | 33.8 | 4.34 | 0.128 [0.0908, 0.133] | 42.4% | 18.0% | 18.7% / 3.6% | 13.9 / 0.137 | 3 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_request_ms` |
| overhead/pty | chat | instructions | CPU | instructions | 8 | 2837.83M | 197.60M | 0.0696 [0.0695, 0.0698] | 1.2% | 4.2% | 2.8% / 0.4% | 6,773,267 / 187,865 | 1 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#instructions` |
| overhead/pty | chat | peak_mem_mib | memory | MiB | 8 | 72.7 | 19.5 | 0.268 [0.267, 0.27] | 2.3% | 2.0% | 0.7% / 0.7% | 0.449 / 0.173 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_mem_mib` |
| overhead/pty | chat | peak_rss_mib | memory | MiB | 8 | 126 | 94.1 | 0.748 [0.747, 0.75] | 1.4% | 0.9% | 0.3% / 0.1% | 0.38 / 0.0654 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_rss_mib` |
| overhead/pty | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 454 | 42.9 | 0.0945 [0.093, 0.0961] | 3.7% | 2.5% | 1.7% / 1.0% | 9.44 / 0.468 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_cpu_ms` |
| overhead/pty | chat | ready_ms | wall | ms | 8 | 332 | 37.6 | 0.113 [0.112, 0.114] | 3.2% | 2.0% | 1.4% / 0.8% | 4.3 / 0.0524 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_ms` |
| overhead/pty | chat | ready_pss_mib | memory | MiB | 8 | 116 | 83.1 | 0.719 [0.716, 0.723] | 1.6% | 1.0% | 0.3% / 0.2% | 0.6 / 0.254 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_pss_mib` |
| overhead/pty | chat | ready_rss_mib | memory | MiB | 8 | 121 | 87.7 | 0.724 [0.72, 0.728] | 1.6% | 0.9% | 0.6% / 0.2% | 0.711 / 0.332 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_rss_mib` |
| overhead/rpc-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 950 | 194 | 0.204 [0.198, 0.206] | 4.2% | 3.6% | 2.3% / 0.8% | 26.1 / 2.76 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cpu_ms` |
| overhead/rpc-ext10 | chat | cycles | CPU | cycles | 8 | 2622.26M | 525.21M | 0.2 [0.194, 0.202] | 4.5% | 3.7% | 2.3% / 0.7% | 69,450,474 / 6,961,312 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cycles` |
| overhead/rpc-ext10 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 606 | 101 | 0.166 [0.163, 0.168] | 4.6% | 3.0% | 2.0% / 0.4% | 9.15 / 0.583 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_cpu_ms` |
| overhead/rpc-ext10 | chat | extensions_ready_ms | wall | ms | 8 | 444 | 94.6 | 0.213 [0.21, 0.215] | 2.5% | 1.9% | 1.7% / 0.2% | 7.53 / 0.262 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_ms` |
| overhead/rpc-ext10 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 149 | 111 | 0.743 [0.741, 0.746] | 0.6% | 0.5% | 0.4% / 0.1% | 0.742 / 0.156 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_pss_mib` |
| overhead/rpc-ext10 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 154 | 115 | 0.745 [0.743, 0.747] | 0.6% | 0.5% | 0.3% / 0.1% | 0.742 / 0.19 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext10 | chat | instructions | CPU | instructions | 8 | 4737.77M | 857.23M | 0.181 [0.18, 0.182] | 0.5% | 0.3% | 0.3% / 0.2% | 10,466,170 / 2,933,040 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#instructions` |
| overhead/rpc-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 148 | 43.8 | 0.297 [0.294, 0.299] | 0.9% | 3.4% | 0.4% / 0.6% | 0.893 / 0.382 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_mem_mib` |
| overhead/rpc-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 199 | 129 | 0.65 [0.648, 0.65] | 0.6% | 2.6% | 0.2% / 0.1% | 0.444 / 0.0664 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_rss_mib` |
| overhead/rpc-ext10 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 605 | 101 | 0.166 [0.163, 0.168] | 4.6% | 3.0% | 2.0% / 0.4% | 9.46 / 0.577 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_cpu_ms` |
| overhead/rpc-ext10 | chat | ready_ms | wall | ms | 8 | 441 | 92.8 | 0.211 [0.207, 0.212] | 2.7% | 1.8% | 1.7% / 0.2% | 7.32 / 0.26 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_ms` |
| overhead/rpc-ext10 | chat | ready_pss_mib | memory | MiB | 8 | 149 | 111 | 0.743 [0.741, 0.746] | 0.6% | 0.5% | 0.4% / 0.1% | 0.738 / 0.158 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_pss_mib` |
| overhead/rpc-ext10 | chat | ready_rss_mib | memory | MiB | 8 | 154 | 115 | 0.745 [0.743, 0.747] | 0.6% | 0.5% | 0.3% / 0.1% | 0.738 / 0.195 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_rss_mib` |
| overhead/rpc-ext10 | chat | teardown_ms | wall | ms | 8 | 11.8 | 4.85 | 0.41 [0.354, 0.437] | 27.4% | 16.2% | 7.1% / 6.6% | 1.35 / 0.453 | 2 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#teardown_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_mean_ms | wall | ms | 8 | 13.8 | 4.04 | 0.294 [0.273, 0.296] | 8.5% | 6.5% | 4.6% / 1.2% | 1.11 / 0.0773 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.6 | 3.62 | 0.312 [0.293, 0.318] | 7.5% | 5.4% | 4.3% / 1.0% | 0.459 / 0.039 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_harness_added_ms | wall | ms | 8 | 1.3 | 0.56 | 0.432 [0.385, 0.456] | 14.7% | 9.6% | 6.3% / 4.3% | 0.129 / 0.0405 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_harness_added_ms` |
| overhead/rpc-ext10 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.8 | 4.5 | 0.269 [0.242, 0.292] | 12.5% | 6.0% | 3.9% / 8.4% | 1.12 / 0.25 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_host_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.89 | 1.74 | 0.446 [0.415, 0.452] | 8.7% | 5.7% | 4.2% / 1.7% | 0.182 / 0.0469 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_turn_gap_ms` |
| overhead/rpc-ext10 | chat | turn_wall_ms | wall | ms | 8 | 8.83 | 4.35 | 0.492 [0.473, 0.504] | 5.7% | 3.6% | 2.8% / 1.4% | 0.396 / 0.0547 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_wall_ms` |
| overhead/rpc-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 901 | 166 | 0.184 [0.183, 0.187] | 3.3% | 1.3% | 1.1% / 1.9% | 13.2 / 3.18 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cpu_ms` |
| overhead/rpc-ext5 | chat | cycles | CPU | cycles | 8 | 2479.88M | 445.83M | 0.18 [0.179, 0.183] | 3.0% | 1.3% | 1.1% / 1.9% | 33,110,128 / 9,325,149 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cycles` |
| overhead/rpc-ext5 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 78.9 | 0.141 [0.138, 0.143] | 2.7% | 1.6% | 1.3% / 1.1% | 10.5 / 0.931 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_cpu_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_ms | wall | ms | 8 | 421 | 74.1 | 0.176 [0.174, 0.178] | 2.6% | 1.0% | 0.7% / 1.3% | 3.67 / 0.743 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 146 | 107 | 0.73 [0.728, 0.731] | 0.8% | 0.5% | 0.3% / 0.1% | 0.489 / 0.126 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_pss_mib` |
| overhead/rpc-ext5 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 151 | 111 | 0.733 [0.73, 0.734] | 0.7% | 0.5% | 0.3% / 0.1% | 0.462 / 0.145 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext5 | chat | instructions | CPU | instructions | 8 | 4464.93M | 683.07M | 0.153 [0.152, 0.153] | 0.8% | 0.5% | 0.2% / 0.2% | 19,068,014 / 1,156,731 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#instructions` |
| overhead/rpc-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 146 | 40.8 | 0.278 [0.276, 0.282] | 3.7% | 3.5% | 0.6% / 0.7% | 1.55 / 0.341 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_mem_mib` |
| overhead/rpc-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 198 | 126 | 0.638 [0.637, 0.642] | 2.6% | 2.5% | 0.4% / 0.1% | 0.994 / 0.107 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_rss_mib` |
| overhead/rpc-ext5 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 78.8 | 0.141 [0.138, 0.143] | 2.7% | 1.6% | 1.3% / 1.1% | 10.8 / 0.938 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_cpu_ms` |
| overhead/rpc-ext5 | chat | ready_ms | wall | ms | 8 | 418 | 72.4 | 0.173 [0.171, 0.175] | 2.3% | 1.0% | 0.7% / 1.3% | 3.69 / 0.731 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_ms` |
| overhead/rpc-ext5 | chat | ready_pss_mib | memory | MiB | 8 | 146 | 107 | 0.73 [0.728, 0.731] | 0.7% | 0.5% | 0.3% / 0.1% | 0.485 / 0.125 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_pss_mib` |
| overhead/rpc-ext5 | chat | ready_rss_mib | memory | MiB | 8 | 151 | 111 | 0.733 [0.73, 0.734] | 0.7% | 0.5% | 0.3% / 0.1% | 0.455 / 0.144 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_rss_mib` |
| overhead/rpc-ext5 | chat | teardown_ms | wall | ms | 8 | 13.0 | 4.77 | 0.366 [0.34, 0.388] | 19.8% | 6.5% | 5.9% / 3.0% | 1.36 / 0.185 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#teardown_ms` |
| overhead/rpc-ext5 | chat | turn_cpu_mean_ms | wall | ms | 8 | 12.9 | 3.92 | 0.303 [0.293, 0.329] | 7.0% | 2.8% | 2.9% / 3.7% | 0.576 / 0.16 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc-ext5 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.9 | 3.27 | 0.274 [0.271, 0.301] | 10.5% | 4.1% | 1.5% / 5.1% | 0.119 / 0.213 | 1 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_ms` |
| overhead/rpc-ext5 | chat | turn_harness_added_ms | wall | ms | 8 | 1.22 | 0.416 | 0.34 [0.327, 0.381] | 9.2% | 3.9% | 3.1% / 5.7% | 0.0638 / 0.0287 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_harness_added_ms` |
| overhead/rpc-ext5 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.0 | 4 | 0.25 [0.246, 0.277] | 12.5% | 3.6% | 3.1% / 7.9% | 0.25 / 0.125 | 0 / 3 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_host_cpu_ms` |
| overhead/rpc-ext5 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.86 | 1.57 | 0.408 [0.403, 0.454] | 7.8% | 1.1% | 0.8% / 5.3% | 0.0326 / 0.116 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_turn_gap_ms` |
| overhead/rpc-ext5 | chat | turn_wall_ms | wall | ms | 8 | 8.35 | 4.04 | 0.484 [0.477, 0.512] | 6.7% | 2.1% | 0.7% / 3.1% | 0.0553 / 0.172 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_wall_ms` |

## pig-0.4.1 against pi-node — PROVISIONAL

### Losses (measurably worse than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/rpc-ext10 | chat | turn_harness_added_ms | wall | ms | 8 | 1.3 | 112 | 86.8 [79.1, 91.0] | 14.7% | 9.6% | 6.3% / 0.6% | 0.129 / 0.962 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_harness_added_ms` |
| overhead/rpc-ext5 | chat | turn_harness_added_ms | wall | ms | 8 | 1.22 | 57.2 | 46.8 [45.5, 48.1] | 6.4% | 3.9% | 3.1% / 0.6% | 0.0638 / 0.449 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_harness_added_ms` |
| overhead/rpc-ext10 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.89 | 131 | 33.8 [31.4, 34.5] | 8.7% | 5.7% | 4.2% / 0.8% | 0.182 / 1.21 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_turn_gap_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.6 | 389 | 33.5 [31.3, 34.1] | 7.5% | 5.4% | 4.3% / 0.5% | 0.459 / 2.42 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_wall_ms | wall | ms | 8 | 8.83 | 269 | 30.5 [29.7, 31.1] | 5.7% | 3.6% | 2.8% / 0.4% | 0.396 / 1.34 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_wall_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_mean_ms | wall | ms | 8 | 13.8 | 384 | 27.9 [25.9, 28.4] | 8.5% | 6.5% | 4.6% / 0.5% | 1.11 / 3.19 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc-ext5 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.86 | 72.4 | 18.7 [18.0, 18.9] | 4.8% | 1.1% | 0.8% / 2.5% | 0.0326 / 2.63 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_turn_gap_ms` |
| overhead/rpc-ext5 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.9 | 209 | 17.6 [17.4, 17.9] | 5.1% | 4.1% | 1.5% / 1.5% | 0.119 / 4.38 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.8 | 294 | 17.6 [16.8, 18.3] | 6.1% | 6.0% | 3.9% / 0.6% | 1.12 / 1.88 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_host_cpu_ms` |
| overhead/rpc-ext5 | chat | turn_wall_ms | wall | ms | 8 | 8.35 | 145 | 17.3 [16.9, 17.5] | 3.0% | 2.1% | 0.7% / 1.6% | 0.0553 / 3.72 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_wall_ms` |
| overhead/rpc-ext5 | chat | turn_cpu_mean_ms | wall | ms | 8 | 12.9 | 206 | 15.9 [15.5, 16.6] | 4.5% | 2.8% | 2.9% / 0.7% | 0.576 / 1.42 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc-ext10 | chat | instructions | CPU | instructions | 8 | 4737.77M | 63851.68M | 13.5 [13.4, 13.5] | 0.4% | 0.3% | 0.3% / 0.3% | 10,466,170 / 171,258,057 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#instructions` |
| overhead/rpc-ext10 | chat | cycles | CPU | cycles | 8 | 2622.26M | 26064.04M | 9.94 [9.58, 10.0] | 4.5% | 3.7% | 2.3% / 0.4% | 69,450,474 / 172,125,599 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cycles` |
| overhead/rpc-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 950 | 9,430 | 9.92 [9.57, 9.97] | 4.2% | 3.6% | 2.3% / 0.4% | 26.1 / 57.6 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cpu_ms` |
| overhead/rpc-ext5 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.0 | 158 | 9.86 [9.55, 10.1] | 4.8% | 3.6% | 3.1% / 0.9% | 0.25 / 1.88 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_host_cpu_ms` |
| overhead/rpc-ext5 | chat | instructions | CPU | instructions | 8 | 4464.93M | 34833.19M | 7.8 [7.76, 7.83] | 0.8% | 0.5% | 0.2% / 0.4% | 19,068,014 / 179,938,015 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#instructions` |
| overhead/rpc-ext5 | chat | cycles | CPU | cycles | 8 | 2479.88M | 14561.32M | 5.87 [5.8, 5.95] | 2.2% | 1.3% | 1.1% / 0.7% | 33,110,128 / 132,874,390 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cycles` |
| overhead/rpc-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 901 | 5,275 | 5.85 [5.79, 5.94] | 2.2% | 1.3% | 1.1% / 0.6% | 13.2 / 42.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cpu_ms` |
| overhead/print-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 106 | 509 | 4.79 [4.7, 4.88] | 5.0% | 1.1% | 0.7% / 1.7% | 0.903 / 15.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_mem_mib` |
| overhead/rpc-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 148 | 595 | 4.03 [4.01, 4.05] | 1.4% | 3.4% | 0.4% / 0.7% | 0.893 / 5.06 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_mem_mib` |
| overhead/rpc-ext10 | chat | ready_rss_mib | memory | MiB | 8 | 154 | 578 | 3.75 [3.7, 3.78] | 2.2% | 0.5% | 0.3% / 1.8% | 0.738 / 9.62 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_rss_mib` |
| overhead/rpc-ext10 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 154 | 578 | 3.75 [3.7, 3.78] | 2.2% | 0.5% | 0.3% / 1.8% | 0.742 / 9.61 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext10 | chat | ready_pss_mib | memory | MiB | 8 | 149 | 549 | 3.69 [3.66, 3.72] | 2.9% | 0.5% | 0.4% / 1.8% | 0.738 / 8.88 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_pss_mib` |
| overhead/rpc-ext10 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 149 | 549 | 3.69 [3.66, 3.72] | 2.9% | 0.5% | 0.4% / 1.8% | 0.742 / 8.88 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_pss_mib` |
| overhead/print-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 156 | 573 | 3.68 [3.62, 3.73] | 4.3% | 1.3% | 0.8% / 1.3% | 1.2 / 9.64 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_rss_mib` |
| overhead/rpc-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 199 | 726 | 3.65 [3.6, 3.73] | 4.5% | 2.6% | 0.2% / 2.5% | 0.444 / 19.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_rss_mib` |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,482 | 123,020 | 3.47 [3.46, 3.48] | 4.3% | 2.7% | 1.6% / 0.2% | 85.1 / 223 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99037.28M | 339743.51M | 3.43 [3.42, 3.44] | 4.3% | 2.7% | 1.6% / 0.3% | 228,928,257 / 726,452,546 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/rpc-ext10 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 606 | 2,076 | 3.43 [3.35, 3.45] | 2.7% | 3.0% | 2.0% / 0.5% | 9.15 / 8.77 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_cpu_ms` |
| overhead/rpc-ext10 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 605 | 2,061 | 3.41 [3.33, 3.43] | 2.7% | 3.0% | 2.0% / 1.2% | 9.46 / 13.6 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_cpu_ms` |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,743 | 9,118 | 3.32 [3.29, 3.33] | 0.9% | 1.9% | 0.7% / 0.2% | 14.7 / 20.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7657.92M | 25088.51M | 3.28 [3.25, 3.28] | 0.9% | 1.9% | 0.7% / 0.2% | 41,528,431 / 51,284,312 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 104 | 338 | 3.26 [3.14, 3.36] | 6.5% | 1.0% | 0.6% / 3.9% | 0.879 / 21.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_mem_mib` |
| overhead/print-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 676 | 2,191 | 3.24 [3.21, 3.32] | 2.5% | 2.3% | 1.6% / 0.9% | 10.6 / 17.3 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cpu_ms` |
| overhead/print-ext10 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 647 | 2,089 | 3.23 [3.19, 3.31] | 2.6% | 2.3% | 1.5% / 1.1% | 10.4 / 20.1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_cpu_ms` |
| overhead/print-ext10 | chat | cycles | CPU | cycles | 8 | 1876.04M | 5981.11M | 3.19 [3.16, 3.27] | 2.5% | 2.3% | 1.6% / 0.9% | 29,682,222 / 51,032,432 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cycles` |
| overhead/print-ext10 | chat | teardown_ms | wall | ms | 8 | 24.7 | 78.6 | 3.19 [3.1, 3.3] | 4.1% | 2.9% | 3.3% / 2.2% | 0.577 / 3.14 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#teardown_ms` |
| overhead/print-ext10 | chat | instructions | CPU | instructions | 8 | 3541.30M | 11157.07M | 3.15 [3.14, 3.17] | 0.7% | 0.3% | 0.2% / 0.7% | 15,071,687 / 63,285,664 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#instructions` |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402328.61M | 1157343.06M | 2.88 [2.87, 2.88] | 0.2% | 0.1% | 0.1% / 0.0% | 190,002,217 / 484,186,655 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28093.14M | 79092.79M | 2.82 [2.81, 2.82] | 0.1% | 0.2% | 0.1% / 0.1% | 21,502,604 / 63,912,728 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/rpc-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 146 | 381 | 2.6 [2.57, 2.67] | 3.7% | 3.5% | 0.6% / 2.3% | 1.55 / 7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_mem_mib` |
| overhead/rpc-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 198 | 513 | 2.59 [2.51, 2.63] | 4.6% | 2.5% | 0.4% / 3.3% | 0.994 / 23.2 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_rss_mib` |
| overhead/print-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 153 | 394 | 2.58 [2.5, 2.65] | 5.1% | 1.4% | 1.0% / 2.9% | 1.62 / 19.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_rss_mib` |
| overhead/rpc-ext5 | chat | ready_rss_mib | memory | MiB | 8 | 151 | 387 | 2.56 [2.53, 2.58] | 3.5% | 0.5% | 0.3% / 2.1% | 0.455 / 6.49 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_rss_mib` |
| overhead/rpc-ext5 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 151 | 387 | 2.56 [2.53, 2.58] | 3.6% | 0.5% | 0.3% / 2.1% | 0.462 / 6.49 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext5 | chat | ready_pss_mib | memory | MiB | 8 | 146 | 371 | 2.55 [2.51, 2.57] | 3.7% | 0.5% | 0.3% / 2.2% | 0.485 / 6.49 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_pss_mib` |
| overhead/rpc-ext5 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 146 | 371 | 2.55 [2.51, 2.57] | 3.7% | 0.5% | 0.3% / 2.2% | 0.489 / 6.49 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_pss_mib` |
| overhead/rpc-ext10 | chat | extensions_ready_ms | wall | ms | 8 | 444 | 1,094 | 2.46 [2.42, 2.49] | 1.5% | 1.9% | 1.7% / 0.7% | 7.53 / 8.09 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_ms` |
| overhead/rpc-ext10 | chat | ready_ms | wall | ms | 8 | 441 | 1,077 | 2.44 [2.4, 2.47] | 1.5% | 1.8% | 1.7% / 0.8% | 7.32 / 7.91 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_ms` |
| overhead/rpc-ext5 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 1,350 | 2.41 [2.36, 2.43] | 2.1% | 1.6% | 1.3% / 0.7% | 10.8 / 8.9 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_cpu_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 1,350 | 2.4 [2.36, 2.43] | 2.2% | 1.6% | 1.3% / 0.7% | 10.5 / 8.87 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_cpu_ms` |
| overhead/print-ext10 | chat | wall_ms | wall | ms | 8 | 495 | 1,176 | 2.38 [2.34, 2.4] | 1.6% | 1.5% | 1.2% / 0.7% | 8.64 / 8.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#wall_ms` |
| overhead/print-ext10 | chat | first_request_ms | wall | ms | 8 | 470 | 1,098 | 2.34 [2.3, 2.36] | 1.6% | 1.5% | 1.2% / 0.7% | 8.61 / 7.88 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,065 | 4,660 | 2.26 [2.23, 2.27] | 1.9% | 2.5% | 1.0% / 0.1% | 29.5 / 7.89 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,098 | 4,693 | 2.24 [2.21, 2.25] | 1.6% | 2.4% | 0.9% / 0.1% | 25.8 / 5.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 633 | 1,415 | 2.24 [2.2, 2.29] | 3.1% | 2.8% | 1.8% / 0.8% | 20.4 / 16.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cpu_ms` |
| overhead/print-ext5 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 606 | 1,353 | 2.24 [2.2, 2.29] | 3.1% | 2.8% | 1.9% / 0.9% | 20 / 14.3 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_cpu_ms` |
| overhead/print-ext5 | chat | cycles | CPU | cycles | 8 | 1755.56M | 3854.62M | 2.2 [2.16, 2.24] | 3.0% | 2.8% | 1.9% / 0.7% | 56,196,843 / 37,667,634 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cycles` |
| overhead/print-ext5 | chat | instructions | CPU | instructions | 8 | 3366.27M | 7118.74M | 2.11 [2.11, 2.12] | 1.1% | 0.4% | 0.3% / 0.3% | 12,376,272 / 25,492,580 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#instructions` |
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 33,954 | 67,409 | 1.99 [1.98, 1.99] | 4.5% | 3.0% | 1.6% / 0.2% | 94.9 / 182 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,085 | 67,599 | 1.98 [1.98, 1.99] | 4.5% | 2.8% | 1.6% / 0.2% | 96.4 / 152 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,456 | 67,662 | 1.96 [1.96, 1.97] | 4.4% | 2.8% | 1.6% / 0.2% | 92.3 / 156 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,427 | 4,738 | 1.95 [1.92, 1.96] | 1.6% | 2.0% | 0.8% / 0.2% | 25.1 / 9.71 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_wall_ms` |
| overhead/print-ext5 | chat | teardown_ms | wall | ms | 8 | 24.2 | 46.0 | 1.9 [1.82, 1.96] | 7.0% | 3.4% | 1.7% / 4.6% | 0.438 / 1.62 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#teardown_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_ms | wall | ms | 8 | 421 | 740 | 1.76 [1.74, 1.77] | 1.4% | 1.0% | 0.7% / 0.5% | 3.67 / 3.78 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_ms` |
| overhead/rpc-ext5 | chat | ready_ms | wall | ms | 8 | 418 | 725 | 1.73 [1.72, 1.75] | 1.4% | 1.0% | 0.7% / 0.6% | 3.69 / 3.92 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_ms` |
| overhead/print-ext5 | chat | wall_ms | wall | ms | 8 | 470 | 778 | 1.66 [1.62, 1.67] | 1.7% | 1.7% | 1.3% / 0.8% | 8.05 / 10.2 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#wall_ms` |
| overhead/print-ext5 | chat | first_request_ms | wall | ms | 8 | 445 | 732 | 1.65 [1.61, 1.66] | 1.7% | 1.7% | 1.4% / 0.8% | 7.57 / 6.84 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_ms` |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 298,791 | 1.04 [1.04, 1.04] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 74,698 | 1.04 [1.04, 1.04] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext10 | chat | request_bytes | wire | bytes | 8 | 1.21M | 1.21M | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes` |
| overhead/rpc-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 60,364 | 60,406 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext5 | chat | request_bytes | wire | bytes | 8 | 1.16M | 1.16M | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes` |
| overhead/rpc-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 58,052 | 58,090 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes_per_turn` |
| overhead/print-ext10 | chat | request_bytes | wire | bytes | 8 | 8,355 | 8,360 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes` |
| overhead/print-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 8,355 | 8,360 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes_per_turn` |
| overhead/print-ext5 | chat | request_bytes | wire | bytes | 8 | 7,209 | 7,212 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes` |
| overhead/print-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 7,209 | 7,212 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes_per_turn` |

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-ext10 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#requests` |
| overhead/print-ext5 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#requests` |
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#requests` |
| overhead/pty | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#requests` |
| overhead/rpc-ext10 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#requests` |
| overhead/rpc-ext10 | chat | teardown_ms | wall | ms | 8 | 11.8 | 8.75 | 0.74 [0.553, 0.902] | 57.8% | 16.2% | 7.1% / 23.3% | 1.35 / 2.99 | 2 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#teardown_ms` |
| overhead/rpc-ext5 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#requests` |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 543 | 29.1 | 0.0536 [0.0525, 0.0563] | 4.8% | 27.6% | 31.0% / 3.3% | 4.28 / 1.47 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 58.4 | 0.101 [0.1, 0.102] | 1.6% | 24.9% | 28.0% / 1.4% | 3.71 / 0.653 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 23.4 | 0.0896 [0.0874, 0.0931] | 6.5% | 1.0% | 0.8% / 3.0% | 1.12 / 1.13 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 51.8 | 0.168 [0.165, 0.171] | 1.4% | 0.8% | 0.7% / 1.1% | 1.3 / 0.602 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/pty | chat | cpu_ms | CPU | ms of CPU time | 8 | 536 | 145 | 0.271 [0.262, 0.274] | 4.1% | 6.2% | 4.4% / 2.7% | 13.7 / 1.66 | 1 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cpu_ms` |
| overhead/pty | chat | cycles | CPU | cycles | 8 | 1471.27M | 380.32M | 0.258 [0.251, 0.262] | 4.2% | 6.3% | 4.4% / 3.3% | 37,355,843 / 5,241,634 | 1 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cycles` |
| overhead/pty | chat | first_frame_ms | wall | ms | 8 | 296 | 34.0 | 0.115 [0.113, 0.12] | 3.7% | 3.0% | 2.8% / 1.1% | 9.46 / 0.532 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_frame_ms` |
| overhead/pty | chat | first_input_accepted_ms | wall | ms | 8 | 331 | 34.8 | 0.105 [0.104, 0.107] | 3.5% | 4.8% | 1.4% / 1.4% | 4 / 0.385 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_input_accepted_ms` |
| overhead/pty | chat | input_to_reply_visible_ms | wall | ms | 8 | 62.0 | 7.16 | 0.115 [0.11, 0.122] | 16.6% | 1.2% | 1.0% / 4.6% | 0.636 / 0.495 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_reply_visible_ms` |
| overhead/pty | chat | input_to_request_ms | wall | ms | 8 | 33.8 | 5.28 | 0.156 [0.106, 0.164] | 42.4% | 18.0% | 18.7% / 5.3% | 13.9 / 0.419 | 3 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_request_ms` |
| overhead/pty | chat | instructions | CPU | instructions | 8 | 2837.83M | 739.60M | 0.261 [0.256, 0.263] | 2.5% | 4.2% | 2.8% / 2.3% | 6,773,267 / 14,029,240 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#instructions` |
| overhead/pty | chat | peak_mem_mib | memory | MiB | 8 | 72.7 | 26.0 | 0.358 [0.355, 0.361] | 3.4% | 2.0% | 0.7% / 2.1% | 0.449 / 0.308 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_mem_mib` |
| overhead/pty | chat | peak_rss_mib | memory | MiB | 8 | 126 | 58.6 | 0.466 [0.464, 0.468] | 1.4% | 0.9% | 0.3% / 1.0% | 0.38 / 0.165 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_rss_mib` |
| overhead/pty | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 454 | 129 | 0.285 [0.281, 0.288] | 7.7% | 2.5% | 1.7% / 3.7% | 9.44 / 1.19 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_cpu_ms` |
| overhead/pty | chat | ready_ms | wall | ms | 8 | 332 | 73.8 | 0.222 [0.22, 0.225] | 2.6% | 2.0% | 1.4% / 1.2% | 4.3 / 0.528 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_ms` |
| overhead/pty | chat | ready_pss_mib | memory | MiB | 8 | 116 | 54.0 | 0.468 [0.461, 0.471] | 1.6% | 1.0% | 0.3% / 0.9% | 0.6 / 0.825 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_pss_mib` |
| overhead/pty | chat | ready_rss_mib | memory | MiB | 8 | 121 | 55.9 | 0.462 [0.455, 0.465] | 1.6% | 0.9% | 0.6% / 0.8% | 0.711 / 0.825 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_rss_mib` |
| overhead/pty | chat | request_bytes | wire | bytes | 8 | 6,006 | 5,995 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes` |
| overhead/pty | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,006 | 5,995 | 0.998 [0.998, 0.998] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext5 | chat | teardown_ms | wall | ms | 8 | 13.0 | 8.82 | 0.677 [0.592, 0.791] | 35.9% | 6.5% | 5.9% / 16.0% | 1.36 / 1.58 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#teardown_ms` |

## pig-tip against pi-node — PROVISIONAL

> **Read this first:** This PiG build (the 0.5.0 release) tracks Pi 1.3.0 (its UpstreamVersion), the same Pi version as the reference arm pi-node.

### Losses (measurably worse than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| overhead/rpc-ext10 | chat | turn_harness_added_ms | wall | ms | 8 | 1.3 | 11.2 | 8.66 [7.82, 9.45] | 14.7% | 9.6% | 6.3% / 5.6% | 0.129 / 0.839 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_harness_added_ms` | 0.0998 [0.0948, 0.105] win |
| overhead/rpc-ext5 | chat | turn_harness_added_ms | wall | ms | 8 | 1.22 | 6.04 | 4.94 [4.78, 5.1] | 6.4% | 3.9% | 3.1% / 3.4% | 0.0638 / 0.253 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_harness_added_ms` | 0.106 [0.101, 0.107] win |
| overhead/rpc-ext10 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.89 | 16.9 | 4.33 [3.99, 4.39] | 8.7% | 5.7% | 4.2% / 5.2% | 0.182 / 0.35 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_turn_gap_ms` | 0.128 [0.122, 0.129] win |
| overhead/rpc-ext10 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.6 | 46.3 | 3.98 [3.72, 4.06] | 7.5% | 5.4% | 4.3% / 3.4% | 0.459 / 0.473 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_ms` | 0.119 [0.117, 0.12] win |
| overhead/rpc-ext10 | chat | turn_wall_ms | wall | ms | 8 | 8.83 | 34.3 | 3.88 [3.64, 4] | 10.4% | 3.6% | 2.8% / 5.4% | 0.396 / 1.76 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_wall_ms` | 0.127 [0.122, 0.13] win |
| overhead/rpc-ext10 | chat | turn_cpu_mean_ms | wall | ms | 8 | 13.8 | 53.3 | 3.87 [3.54, 3.96] | 8.5% | 6.5% | 4.6% / 2.6% | 1.11 / 1.69 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_mean_ms` | 0.139 [0.136, 0.14] win |
| overhead/rpc-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 148 | 421 | 2.85 [2.42, 3.03] | 19.8% | 3.4% | 0.4% / 9.8% | 0.893 / 60.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_mem_mib` | 0.708 [0.601, 0.754] win |
| overhead/rpc-ext5 | chat | turn_turn_gap_ms | wall | ms | 8 | 3.86 | 9.69 | 2.51 [2.48, 2.59] | 8.6% | 1.1% | 0.8% / 3.3% | 0.0326 / 0.237 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_turn_gap_ms` | 0.134 [0.132, 0.141] win |
| overhead/rpc-ext5 | chat | turn_cpu_mean_ms | wall | ms | 8 | 12.9 | 31.2 | 2.41 [2.33, 2.51] | 6.9% | 2.8% | 2.9% / 3.9% | 0.576 / 2.07 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_mean_ms` | 0.151 [0.141, 0.155] win |
| overhead/rpc-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 199 | 480 | 2.41 [2.12, 2.49] | 13.2% | 2.6% | 0.2% / 6.9% | 0.444 / 41.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_rss_mib` | 0.661 [0.584, 0.688] win |
| overhead/rpc-ext5 | chat | turn_wall_ms | wall | ms | 8 | 8.35 | 19.9 | 2.38 [2.24, 2.49] | 9.2% | 2.1% | 0.7% / 4.8% | 0.0553 / 1.25 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_wall_ms` | 0.137 [0.13, 0.145] win |
| overhead/rpc-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 950 | 2,016 | 2.12 [2.04, 2.14] | 4.2% | 3.6% | 2.3% / 1.2% | 26.1 / 19.1 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cpu_ms` | 0.214 [0.212, 0.215] win |
| overhead/rpc-ext10 | chat | instructions | CPU | instructions | 8 | 4737.77M | 10024.49M | 2.12 [2.11, 2.13] | 0.7% | 0.3% | 0.3% / 0.5% | 10,466,170 / 79,166,590 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#instructions` | 0.157 [0.156, 0.158] win |
| overhead/rpc-ext5 | chat | turn_cpu_ms | CPU | ms of CPU time | 8 | 11.9 | 25.2 | 2.11 [2.06, 2.26] | 9.2% | 4.1% | 1.5% / 5.8% | 0.119 / 2.21 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_ms` | 0.12 [0.116, 0.129] win |
| overhead/rpc-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 146 | 309 | 2.11 [1.97, 2.46] | 19.2% | 3.5% | 0.6% / 10.3% | 1.55 / 44 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_mem_mib` | 0.813 [0.75, 0.939] win |
| overhead/print-ext5 | chat | peak_mem_mib | memory | MiB | 8 | 104 | 218 | 2.1 [1.98, 2.24] | 12.0% | 1.0% | 0.6% / 7.5% | 0.879 / 25.2 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_mem_mib` | 0.646 [0.595, 0.69] win |
| overhead/rpc-ext10 | chat | cycles | CPU | cycles | 8 | 2622.26M | 5459.33M | 2.08 [2.01, 2.12] | 4.5% | 3.7% | 2.3% / 1.4% | 69,450,474 / 72,597,741 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cycles` | 0.209 [0.207, 0.212] win |
| overhead/print-ext10 | chat | peak_mem_mib | memory | MiB | 8 | 106 | 217 | 2.04 [1.97, 2.24] | 9.1% | 1.1% | 0.7% / 5.8% | 0.903 / 9.15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_mem_mib` | 0.426 [0.417, 0.462] win |
| overhead/rpc-ext10 | chat | ready_pss_mib | memory | MiB | 8 | 149 | 278 | 1.87 [1.79, 2.06] | 9.2% | 0.5% | 0.4% / 6.4% | 0.738 / 15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_pss_mib` | 0.507 [0.483, 0.564] win |
| overhead/rpc-ext10 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 149 | 278 | 1.87 [1.79, 2.06] | 9.2% | 0.5% | 0.4% / 6.4% | 0.742 / 15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_pss_mib` | 0.507 [0.483, 0.564] win |
| overhead/rpc-ext10 | chat | ready_rss_mib | memory | MiB | 8 | 154 | 286 | 1.85 [1.77, 2.04] | 8.9% | 0.5% | 0.3% / 5.9% | 0.738 / 15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_rss_mib` | 0.494 [0.471, 0.552] win |
| overhead/rpc-ext10 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 154 | 286 | 1.85 [1.77, 2.04] | 8.9% | 0.5% | 0.3% / 5.9% | 0.742 / 15 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_rss_mib` | 0.494 [0.471, 0.552] win |
| overhead/rpc-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 198 | 363 | 1.83 [1.74, 2.09] | 15.2% | 2.5% | 0.4% / 8.6% | 0.994 / 49.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_rss_mib` | 0.708 [0.668, 0.796] win |
| overhead/print-ext5 | chat | peak_rss_mib | memory | MiB | 8 | 153 | 271 | 1.78 [1.67, 1.86] | 10.3% | 1.4% | 1.0% / 6.6% | 1.62 / 25.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_rss_mib` | 0.688 [0.651, 0.721] win |
| overhead/rpc-ext5 | chat | extensions_ready_pss_mib | memory | MiB | 8 | 146 | 256 | 1.75 [1.7, 1.97] | 13.1% | 0.5% | 0.3% / 6.7% | 0.489 / 20.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_pss_mib` | 0.688 [0.665, 0.757] win |
| overhead/rpc-ext5 | chat | ready_pss_mib | memory | MiB | 8 | 146 | 256 | 1.75 [1.7, 1.97] | 13.1% | 0.5% | 0.3% / 6.7% | 0.485 / 20.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_pss_mib` | 0.688 [0.665, 0.757] win |
| overhead/rpc-ext5 | chat | ready_rss_mib | memory | MiB | 8 | 151 | 263 | 1.74 [1.69, 1.94] | 13.9% | 0.5% | 0.3% / 6.5% | 0.455 / 20.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_rss_mib` | 0.68 [0.657, 0.746] win |
| overhead/rpc-ext5 | chat | extensions_ready_rss_mib | memory | MiB | 8 | 151 | 263 | 1.74 [1.69, 1.94] | 13.8% | 0.5% | 0.3% / 6.5% | 0.462 / 20.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_rss_mib` | 0.68 [0.657, 0.746] win |
| overhead/print-ext10 | chat | peak_rss_mib | memory | MiB | 8 | 156 | 269 | 1.73 [1.67, 1.85] | 7.5% | 1.3% | 0.8% / 4.3% | 1.2 / 9.11 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_rss_mib` | 0.47 [0.462, 0.5] win |
| overhead/rpc-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 901 | 1,477 | 1.64 [1.6, 1.68] | 2.2% | 1.3% | 1.1% / 1.9% | 13.2 / 38.4 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cpu_ms` | 0.28 [0.272, 0.285] win |
| overhead/rpc-ext5 | chat | instructions | CPU | instructions | 8 | 4464.93M | 7212.75M | 1.62 [1.61, 1.62] | 1.1% | 0.5% | 0.2% / 0.4% | 19,068,014 / 56,827,549 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#instructions` | 0.207 [0.206, 0.208] win |
| overhead/rpc-ext5 | chat | cycles | CPU | cycles | 8 | 2479.88M | 4002.59M | 1.61 [1.58, 1.66] | 2.3% | 1.3% | 1.1% / 2.0% | 33,110,128 / 128,402,417 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cycles` | 0.275 [0.268, 0.281] win |
| overhead/rpc-ext10 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 605 | 929 | 1.54 [1.51, 1.56] | 2.7% | 3.0% | 2.0% / 1.2% | 9.46 / 16.8 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_cpu_ms` | 0.451 [0.447, 0.458] win |
| overhead/rpc-ext10 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 606 | 929 | 1.53 [1.51, 1.56] | 2.7% | 3.0% | 2.0% / 1.2% | 9.15 / 16.7 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_cpu_ms` | 0.448 [0.443, 0.455] win |
| overhead/rpc-ext5 | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 842 | 1.5 [1.48, 1.52] | 3.0% | 1.6% | 1.3% / 1.6% | 10.8 / 17.1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_cpu_ms` | 0.624 [0.616, 0.632] win |
| overhead/rpc-ext5 | chat | extensions_ready_cpu_ms | CPU | ms of CPU time | 8 | 561 | 842 | 1.5 [1.47, 1.52] | 2.9% | 1.6% | 1.3% / 1.6% | 10.5 / 17.1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_cpu_ms` | 0.624 [0.616, 0.632] win |
| overhead/print-ext10 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 647 | 898 | 1.39 [1.38, 1.42] | 2.6% | 2.3% | 1.5% / 0.8% | 10.4 / 7.96 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_cpu_ms` | 0.43 [0.425, 0.433] win |
| overhead/print-ext10 | chat | cpu_ms | CPU | ms of CPU time | 8 | 676 | 934 | 1.38 [1.37, 1.41] | 2.5% | 2.3% | 1.6% / 1.0% | 10.6 / 9.44 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cpu_ms` | 0.427 [0.422, 0.429] win |
| overhead/print-ext5 | chat | first_request_cpu_ms | CPU | ms of CPU time | 8 | 606 | 823 | 1.36 [1.32, 1.4] | 3.1% | 2.8% | 1.9% / 1.7% | 20 / 18.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_cpu_ms` | 0.608 [0.598, 0.622] win |
| overhead/print-ext10 | chat | cycles | CPU | cycles | 8 | 1876.04M | 2539.86M | 1.35 [1.34, 1.39] | 2.5% | 2.3% | 1.6% / 0.9% | 29,682,222 / 22,025,511 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cycles` | 0.425 [0.421, 0.427] win |
| overhead/print-ext5 | chat | cpu_ms | CPU | ms of CPU time | 8 | 633 | 853 | 1.35 [1.31, 1.39] | 3.2% | 2.8% | 1.8% / 1.8% | 20.4 / 21.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cpu_ms` | 0.603 [0.593, 0.617] win |
| overhead/rpc-ext10 | chat | extensions_ready_ms | wall | ms | 8 | 444 | 592 | 1.33 [1.32, 1.36] | 2.7% | 1.9% | 1.7% / 1.6% | 7.53 / 15.3 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_ms` | 0.541 [0.536, 0.549] win |
| overhead/print-ext5 | chat | cycles | CPU | cycles | 8 | 1755.56M | 2321.27M | 1.32 [1.28, 1.36] | 3.2% | 2.8% | 1.9% / 1.8% | 56,196,843 / 59,104,046 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cycles` | 0.602 [0.592, 0.616] win |
| overhead/rpc-ext10 | chat | ready_ms | wall | ms | 8 | 441 | 579 | 1.31 [1.3, 1.34] | 2.3% | 1.8% | 1.7% / 1.5% | 7.32 / 12.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_ms` | 0.538 [0.533, 0.545] win |
| overhead/rpc-ext5 | chat | extensions_ready_ms | wall | ms | 8 | 421 | 545 | 1.3 [1.29, 1.32] | 3.9% | 1.0% | 0.7% / 1.3% | 3.67 / 12.1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_ms` | 0.737 [0.731, 0.753] win |
| overhead/rpc-ext5 | chat | ready_ms | wall | ms | 8 | 418 | 533 | 1.28 [1.27, 1.3] | 3.7% | 1.0% | 0.7% / 1.4% | 3.69 / 12.6 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_ms` | 0.735 [0.728, 0.752] win |
| overhead/print-ext10 | chat | instructions | CPU | instructions | 8 | 3541.30M | 4432.33M | 1.25 [1.25, 1.25] | 0.9% | 0.3% | 0.2% / 0.1% | 15,071,687 / 5,093,348 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#instructions` | 0.397 [0.394, 0.399] win |
| overhead/print-ext5 | chat | instructions | CPU | instructions | 8 | 3366.27M | 4057.28M | 1.21 [1.19, 1.22] | 1.7% | 0.4% | 0.3% / 0.8% | 12,376,272 / 60,245,598 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#instructions` | 0.57 [0.566, 0.574] win |
| overhead/print-ext10 | chat | first_request_ms | wall | ms | 8 | 470 | 541 | 1.15 [1.13, 1.16] | 1.6% | 1.5% | 1.2% / 0.9% | 8.61 / 6.01 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_ms` | 0.493 [0.487, 0.497] win |
| overhead/print-ext10 | chat | wall_ms | wall | ms | 8 | 495 | 566 | 1.14 [1.13, 1.16] | 1.6% | 1.5% | 1.2% / 1.1% | 8.64 / 8.04 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#wall_ms` | 0.481 [0.476, 0.489] win |
| overhead/print-ext5 | chat | first_request_ms | wall | ms | 8 | 445 | 500 | 1.12 [1.09, 1.14] | 2.2% | 1.7% | 1.4% / 1.6% | 7.57 / 12.3 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_ms` | 0.682 [0.671, 0.696] win |
| overhead/print-ext5 | chat | wall_ms | wall | ms | 8 | 470 | 521 | 1.11 [1.08, 1.13] | 2.6% | 1.7% | 1.3% / 1.7% | 8.05 / 12.5 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#wall_ms` | 0.67 [0.659, 0.684] win |

### No measurable difference (inside the A/A floor) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| overhead/print-ext10 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/print-ext10 | chat | teardown_ms | wall | ms | 8 | 24.7 | 25.7 | 1.04 [1, 1.13] | 6.9% | 2.9% | 3.3% / 6.4% | 0.577 / 2.2 | 1 / 0 | 0.156 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#teardown_ms` | 0.327 [0.311, 0.354] win |
| overhead/print-ext5 | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/print-ext5 | chat | teardown_ms | wall | ms | 8 | 24.2 | 21.8 | 0.904 [0.815, 0.932] | 12.5% | 3.4% | 1.7% / 6.1% | 0.438 / 2.13 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#teardown_ms` | 0.475 [0.431, 0.502] win |
| overhead/print-write | chat | requests | wire | count | 8 | 4 | 4 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/pty | chat | requests | wire | count | 8 | 1 | 1 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/rpc-ext10 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/rpc-ext10 | chat | teardown_ms | wall | ms | 8 | 11.8 | 16.4 | 1.38 [0.863, 1.7] | 51.2% | 16.2% | 7.1% / 35.3% | 1.35 / 7.96 | 2 / 0 | 0.562 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#teardown_ms` | 1.87 [1.09, 2.71] loss |
| overhead/rpc-ext5 | chat | requests | wire | count | 8 | 40.0 | 40.0 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 1 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#requests` | 1 [1, 1] no measurable difference |
| overhead/rpc-ext5 | chat | teardown_ms | wall | ms | 8 | 13.0 | 12.9 | 0.987 [0.822, 1.15] | 73.8% | 6.5% | 5.9% / 20.9% | 1.36 / 3.23 | 0 / 0 | 0.938 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#teardown_ms` | 1.46 [1.26, 1.69] no measurable difference |

### Wins (measurably better than the reference) — PROVISIONAL

| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell | 0.4.1 → 0.5.0 (newer / previous) |
|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| overhead/print-ext10 | chat | request_bytes | wire | bytes | 8 | 8,355 | 8,322 | 0.996 [0.996, 0.996] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes` | 0.995 [0.995, 0.995] win |
| overhead/print-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 8,355 | 8,322 | 0.996 [0.996, 0.996] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes_per_turn` | 0.995 [0.995, 0.995] win |
| overhead/print-ext5 | chat | request_bytes | wire | bytes | 8 | 7,209 | 7,174 | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes` | 0.995 [0.995, 0.995] win |
| overhead/print-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 7,209 | 7,174 | 0.995 [0.995, 0.995] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes_per_turn` | 0.995 [0.995, 0.995] win |
| overhead/print-write | chat | kb200_after_stream_ms | wall | ms | 8 | 33,954 | 13.5 | 0.000398 [0.000387, 0.00043] | 10.0% | 3.0% | 1.6% / 4.9% | 94.9 / 0.957 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_after_stream_ms` | 0.0002 [0.000195, 0.000217] win |
| overhead/print-write | chat | kb200_call_to_result_ms | wall | ms | 8 | 34,085 | 178 | 0.00523 [0.00518, 0.00527] | 4.5% | 2.8% | 1.6% / 0.8% | 96.4 / 2.03 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_call_to_result_ms` | 0.00263 [0.00261, 0.00266] win |
| overhead/print-write | chat | kb200_cpu_ms | CPU | ms of CPU time | 8 | 35,482 | 231 | 0.0065 [0.00643, 0.00681] | 5.5% | 2.7% | 1.6% / 2.8% | 85.1 / 9.8 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cpu_ms` | 0.00188 [0.00186, 0.00197] win |
| overhead/print-write | chat | kb200_cycles | CPU | cycles | 8 | 99037.28M | 601.92M | 0.00608 [0.00602, 0.00627] | 4.3% | 2.7% | 1.6% / 2.1% | 228,928,257 / 18,526,212 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cycles` | 0.00177 [0.00175, 0.00183] win |
| overhead/print-write | chat | kb200_instructions | CPU | instructions | 8 | 402328.61M | 1479.64M | 0.00368 [0.0034, 0.0037] | 8.2% | 0.1% | 0.1% / 4.4% | 190,002,217 / 99,872,192 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_instructions` | 0.00128 [0.00118, 0.00129] win |
| overhead/print-write | chat | kb200_peak_mem_mib | memory | MiB | 8 | 543 | 23.1 | 0.0426 [0.0421, 0.043] | 1.6% | 27.6% | 31.0% / 1.1% | 4.28 / 0.192 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_mem_mib` | 0.795 [0.754, 0.809] win |
| overhead/print-write | chat | kb200_peak_rss_mib | memory | MiB | 8 | 578 | 58.2 | 0.101 [0.0994, 0.102] | 4.7% | 24.9% | 28.0% / 1.7% | 3.71 / 0.702 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_rss_mib` | 0.997 [0.98, 1.01] no measurable difference |
| overhead/print-write | chat | kb200_wall_ms | wall | ms | 8 | 34,456 | 214 | 0.00622 [0.00616, 0.00632] | 4.4% | 2.8% | 1.6% / 1.8% | 92.3 / 3.54 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_wall_ms` | 0.00317 [0.00314, 0.00322] win |
| overhead/print-write | chat | kb50_after_stream_ms | wall | ms | 8 | 2,065 | 7.53 | 0.00365 [0.00357, 0.00368] | 1.9% | 2.5% | 1.0% / 1.1% | 29.5 / 0.0745 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_after_stream_ms` | 0.00162 [0.0016, 0.00162] win |
| overhead/print-write | chat | kb50_call_to_result_ms | wall | ms | 8 | 2,098 | 49.0 | 0.0234 [0.0229, 0.0237] | 3.2% | 2.4% | 0.9% / 1.8% | 25.8 / 1.19 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_call_to_result_ms` | 0.0104 [0.0103, 0.0107] win |
| overhead/print-write | chat | kb50_cpu_ms | CPU | ms of CPU time | 8 | 2,743 | 74.0 | 0.027 [0.0264, 0.0281] | 5.5% | 1.9% | 0.7% / 3.8% | 14.7 / 3.05 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cpu_ms` | 0.00812 [0.00798, 0.00845] win |
| overhead/print-write | chat | kb50_cycles | CPU | cycles | 8 | 7657.92M | 189.66M | 0.0248 [0.0244, 0.0256] | 3.5% | 1.9% | 0.7% / 2.8% | 41,528,431 / 6,785,648 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cycles` | 0.00756 [0.00746, 0.00786] win |
| overhead/print-write | chat | kb50_instructions | CPU | instructions | 8 | 28093.14M | 420.75M | 0.015 [0.0148, 0.0152] | 4.0% | 0.2% | 0.1% / 3.2% | 21,502,604 / 5,861,246 | 0 / 1 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_instructions` | 0.00532 [0.00526, 0.0054] win |
| overhead/print-write | chat | kb50_peak_mem_mib | memory | MiB | 8 | 261 | 16.3 | 0.0625 [0.0617, 0.0627] | 1.6% | 1.0% | 0.8% / 1.5% | 1.12 / 0.122 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_mem_mib` | 0.697 [0.67, 0.719] win |
| overhead/print-write | chat | kb50_peak_rss_mib | memory | MiB | 8 | 309 | 44.2 | 0.143 [0.141, 0.16] | 10.3% | 0.8% | 0.7% / 5.6% | 1.3 / 1.75 | 1 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_rss_mib` | 0.853 [0.846, 0.936] win |
| overhead/print-write | chat | kb50_wall_ms | wall | ms | 8 | 2,427 | 67.8 | 0.0279 [0.0274, 0.0301] | 10.0% | 2.0% | 0.8% / 4.8% | 25.1 / 2.85 | 0 / 2 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_wall_ms` | 0.0143 [0.0141, 0.0156] win |
| overhead/print-write | chat | request_bytes | wire | bytes | 8 | 286,114 | 286,026 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes` | 0.957 [0.957, 0.957] win |
| overhead/print-write | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 71,528 | 71,506 | 1 [1, 1] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes_per_turn` | 0.957 [0.957, 0.957] win |
| overhead/pty | chat | cpu_ms | CPU | ms of CPU time | 8 | 536 | 61.0 | 0.114 [0.111, 0.115] | 4.1% | 6.2% | 4.4% / 1.0% | 13.7 / 0.661 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cpu_ms` | 0.42 [0.419, 0.425] win |
| overhead/pty | chat | cycles | CPU | cycles | 8 | 1471.27M | 158.36M | 0.108 [0.105, 0.109] | 4.2% | 6.3% | 4.4% / 0.7% | 37,355,843 / 1,004,164 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cycles` | 0.416 [0.412, 0.421] win |
| overhead/pty | chat | first_frame_ms | wall | ms | 8 | 296 | 15.2 | 0.0515 [0.0506, 0.0533] | 3.8% | 3.0% | 2.8% / 0.9% | 9.46 / 0.124 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_frame_ms` | 0.447 [0.442, 0.453] win |
| overhead/pty | chat | first_input_accepted_ms | wall | ms | 8 | 331 | 16.0 | 0.0484 [0.048, 0.0497] | 4.5% | 4.8% | 1.4% / 1.8% | 4 / 0.261 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_input_accepted_ms` | 0.46 [0.456, 0.469] win |
| overhead/pty | chat | input_to_reply_visible_ms | wall | ms | 8 | 62.0 | 3.7 | 0.0597 [0.0575, 0.0607] | 6.2% | 1.2% | 1.0% / 2.8% | 0.636 / 0.173 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_reply_visible_ms` | 0.517 [0.486, 0.551] win |
| overhead/pty | chat | input_to_request_ms | wall | ms | 8 | 33.8 | 2.55 | 0.0753 [0.0544, 0.0775] | 42.4% | 18.0% | 18.7% / 3.2% | 13.9 / 0.105 | 3 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_request_ms` | 0.482 [0.455, 0.52] win |
| overhead/pty | chat | instructions | CPU | instructions | 8 | 2837.83M | 338.17M | 0.119 [0.119, 0.119] | 1.0% | 4.2% | 2.8% / 0.3% | 6,773,267 / 1,254,227 | 1 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#instructions` | 0.457 [0.453, 0.464] win |
| overhead/pty | chat | peak_mem_mib | memory | MiB | 8 | 72.7 | 14.5 | 0.2 [0.197, 0.203] | 2.3% | 2.0% | 0.7% / 1.4% | 0.449 / 0.182 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_mem_mib` | 0.559 [0.552, 0.564] win |
| overhead/pty | chat | peak_rss_mib | memory | MiB | 8 | 126 | 53.5 | 0.425 [0.425, 0.427] | 1.4% | 0.9% | 0.3% / 0.4% | 0.38 / 0.272 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_rss_mib` | 0.914 [0.909, 0.919] win |
| overhead/pty | chat | ready_cpu_ms | CPU | ms of CPU time | 8 | 454 | 47.5 | 0.105 [0.103, 0.105] | 2.8% | 2.5% | 1.7% / 1.0% | 9.44 / 0.415 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_cpu_ms` | 0.367 [0.363, 0.373] win |
| overhead/pty | chat | ready_ms | wall | ms | 8 | 332 | 35.5 | 0.107 [0.106, 0.109] | 2.6% | 2.0% | 1.4% / 1.5% | 4.3 / 0.808 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_ms` | 0.482 [0.478, 0.493] win |
| overhead/pty | chat | ready_pss_mib | memory | MiB | 8 | 116 | 50.0 | 0.433 [0.431, 0.435] | 1.6% | 1.0% | 0.3% / 0.6% | 0.6 / 0.247 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_pss_mib` | 0.925 [0.918, 0.938] win |
| overhead/pty | chat | ready_rss_mib | memory | MiB | 8 | 121 | 51.9 | 0.429 [0.426, 0.431] | 1.6% | 0.9% | 0.6% / 0.6% | 0.711 / 0.248 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_rss_mib` | 0.928 [0.921, 0.94] win |
| overhead/pty | chat | request_bytes | wire | bytes | 8 | 6,006 | 5,957 | 0.992 [0.992, 0.992] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes` | 0.994 [0.994, 0.994] win |
| overhead/pty | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 6,006 | 5,957 | 0.992 [0.992, 0.992] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes_per_turn` | 0.994 [0.994, 0.994] win |
| overhead/rpc-ext10 | chat | request_bytes | wire | bytes | 8 | 1.21M | 1.21M | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes` | 0.998 [0.998, 0.998] win |
| overhead/rpc-ext10 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 60,364 | 60,290 | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes_per_turn` | 0.998 [0.998, 0.998] win |
| overhead/rpc-ext10 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.8 | 14.5 | 0.866 [0.8, 0.925] | 10.9% | 6.0% | 3.9% / 4.8% | 1.12 / 0.75 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_host_cpu_ms` | 0.0493 [0.0474, 0.0527] win |
| overhead/rpc-ext5 | chat | request_bytes | wire | bytes | 8 | 1.16M | 1.16M | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | n/a |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes` | 0.998 [0.998, 0.998] win |
| overhead/rpc-ext5 | chat | request_bytes_per_turn | wire | bytes per turn | 8 | 58,052 | 57,974 | 0.999 [0.999, 0.999] | 0.0% | 0.0% | 0.0% / 0.0% | 0 / 0 | 0 / 0 | 0.0312 | no exact |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes_per_turn` | 0.998 [0.998, 0.998] win |
| overhead/rpc-ext5 | chat | turn_host_cpu_ms | CPU | ms of CPU time | 8 | 16.0 | 8.75 | 0.547 [0.523, 0.594] | 5.9% | 3.6% | 3.1% / 6.6% | 0.25 / 1 | 0 / 0 | 0.0312 | no ±5.0% |  | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_host_cpu_ms` | 0.0555 [0.0535, 0.0609] win |

## pig-tip against its previous arm pig-0.4.1: 0.4.1 → 0.5.0 (newer / previous) — PROVISIONAL

`pig-0.4.1` is the earlier arm and `pig-tip` the later one (declared as `previous` in the manifest; a loss means the later arm is measurably worse, a win measurably better). The floor is the larger of the two arms' A/A floors; a ratio inside it is no measurable difference.

| workload | api | metric | pig-0.4.1 median | pig-tip median | ratio [95% CI] | A/A floor | verdict |
|---|---|---|---:|---:|---|---:|---|
| overhead/rpc-ext10 | chat | teardown_ms | 8.75 | 16.4 | 1.87 [1.09, 2.71] | 57.8% | **loss** |
| overhead/print-ext10 | chat | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print-ext5 | chat | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/print-write | chat | kb200_peak_rss_mib | 58.4 | 58.2 | 0.997 [0.98, 1.01] | 4.7% | **no measurable difference** |
| overhead/print-write | chat | requests | 4 | 4 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/pty | chat | requests | 1 | 1 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/rpc-ext10 | chat | requests | 40.0 | 40.0 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/rpc-ext5 | chat | requests | 40.0 | 40.0 | 1 [1, 1] | 0.0% | **no measurable difference** |
| overhead/rpc-ext5 | chat | teardown_ms | 8.82 | 12.9 | 1.46 [1.26, 1.69] | 73.8% | **no measurable difference** |
| overhead/print-ext10 | chat | cpu_ms | 2,191 | 934 | 0.427 [0.422, 0.429] | 1.7% | **win** |
| overhead/print-ext10 | chat | cycles | 5981.11M | 2539.86M | 0.425 [0.421, 0.427] | 2.0% | **win** |
| overhead/print-ext10 | chat | first_request_cpu_ms | 2,089 | 898 | 0.43 [0.425, 0.433] | 1.9% | **win** |
| overhead/print-ext10 | chat | first_request_ms | 1,098 | 541 | 0.493 [0.487, 0.497] | 1.1% | **win** |
| overhead/print-ext10 | chat | instructions | 11157.07M | 4432.33M | 0.397 [0.394, 0.399] | 0.9% | **win** |
| overhead/print-ext10 | chat | peak_mem_mib | 509 | 217 | 0.426 [0.417, 0.462] | 9.1% | **win** |
| overhead/print-ext10 | chat | peak_rss_mib | 573 | 269 | 0.47 [0.462, 0.5] | 7.5% | **win** |
| overhead/print-ext10 | chat | request_bytes | 8,360 | 8,322 | 0.995 [0.995, 0.995] | 0.0% | **win** |
| overhead/print-ext10 | chat | request_bytes_per_turn | 8,360 | 8,322 | 0.995 [0.995, 0.995] | 0.0% | **win** |
| overhead/print-ext10 | chat | teardown_ms | 78.6 | 25.7 | 0.327 [0.311, 0.354] | 6.9% | **win** |
| overhead/print-ext10 | chat | wall_ms | 1,176 | 566 | 0.481 [0.476, 0.489] | 1.4% | **win** |
| overhead/print-ext5 | chat | cpu_ms | 1,415 | 853 | 0.603 [0.593, 0.617] | 3.2% | **win** |
| overhead/print-ext5 | chat | cycles | 3854.62M | 2321.27M | 0.602 [0.592, 0.616] | 3.2% | **win** |
| overhead/print-ext5 | chat | first_request_cpu_ms | 1,353 | 823 | 0.608 [0.598, 0.622] | 3.0% | **win** |
| overhead/print-ext5 | chat | first_request_ms | 732 | 500 | 0.682 [0.671, 0.696] | 2.2% | **win** |
| overhead/print-ext5 | chat | instructions | 7118.74M | 4057.28M | 0.57 [0.566, 0.574] | 1.7% | **win** |
| overhead/print-ext5 | chat | peak_mem_mib | 338 | 218 | 0.646 [0.595, 0.69] | 12.0% | **win** |
| overhead/print-ext5 | chat | peak_rss_mib | 394 | 271 | 0.688 [0.651, 0.721] | 10.3% | **win** |
| overhead/print-ext5 | chat | request_bytes | 7,212 | 7,174 | 0.995 [0.995, 0.995] | 0.0% | **win** |
| overhead/print-ext5 | chat | request_bytes_per_turn | 7,212 | 7,174 | 0.995 [0.995, 0.995] | 0.0% | **win** |
| overhead/print-ext5 | chat | teardown_ms | 46.0 | 21.8 | 0.475 [0.431, 0.502] | 12.5% | **win** |
| overhead/print-ext5 | chat | wall_ms | 778 | 521 | 0.67 [0.659, 0.684] | 2.6% | **win** |
| overhead/print-write | chat | kb200_after_stream_ms | 67,409 | 13.5 | 0.0002 [0.000195, 0.000217] | 10.0% | **win** |
| overhead/print-write | chat | kb200_call_to_result_ms | 67,599 | 178 | 0.00263 [0.00261, 0.00266] | 1.2% | **win** |
| overhead/print-write | chat | kb200_cpu_ms | 123,020 | 231 | 0.00188 [0.00186, 0.00197] | 5.5% | **win** |
| overhead/print-write | chat | kb200_cycles | 339743.51M | 601.92M | 0.00177 [0.00175, 0.00183] | 3.8% | **win** |
| overhead/print-write | chat | kb200_instructions | 1157343.06M | 1479.64M | 0.00128 [0.00118, 0.00129] | 8.2% | **win** |
| overhead/print-write | chat | kb200_peak_mem_mib | 29.1 | 23.1 | 0.795 [0.754, 0.809] | 4.8% | **win** |
| overhead/print-write | chat | kb200_wall_ms | 67,662 | 214 | 0.00317 [0.00314, 0.00322] | 2.1% | **win** |
| overhead/print-write | chat | kb50_after_stream_ms | 4,660 | 7.53 | 0.00162 [0.0016, 0.00162] | 1.8% | **win** |
| overhead/print-write | chat | kb50_call_to_result_ms | 4,693 | 49.0 | 0.0104 [0.0103, 0.0107] | 3.2% | **win** |
| overhead/print-write | chat | kb50_cpu_ms | 9,118 | 74.0 | 0.00812 [0.00798, 0.00845] | 5.5% | **win** |
| overhead/print-write | chat | kb50_cycles | 25088.51M | 189.66M | 0.00756 [0.00746, 0.00786] | 3.5% | **win** |
| overhead/print-write | chat | kb50_instructions | 79092.79M | 420.75M | 0.00532 [0.00526, 0.0054] | 4.0% | **win** |
| overhead/print-write | chat | kb50_peak_mem_mib | 23.4 | 16.3 | 0.697 [0.67, 0.719] | 6.5% | **win** |
| overhead/print-write | chat | kb50_peak_rss_mib | 51.8 | 44.2 | 0.853 [0.846, 0.936] | 10.3% | **win** |
| overhead/print-write | chat | kb50_wall_ms | 4,738 | 67.8 | 0.0143 [0.0141, 0.0156] | 10.0% | **win** |
| overhead/print-write | chat | request_bytes | 298,791 | 286,026 | 0.957 [0.957, 0.957] | 0.0% | **win** |
| overhead/print-write | chat | request_bytes_per_turn | 74,698 | 71,506 | 0.957 [0.957, 0.957] | 0.0% | **win** |
| overhead/pty | chat | cpu_ms | 145 | 61.0 | 0.42 [0.419, 0.425] | 3.6% | **win** |
| overhead/pty | chat | cycles | 380.32M | 158.36M | 0.416 [0.412, 0.421] | 2.3% | **win** |
| overhead/pty | chat | first_frame_ms | 34.0 | 15.2 | 0.447 [0.442, 0.453] | 3.8% | **win** |
| overhead/pty | chat | first_input_accepted_ms | 34.8 | 16.0 | 0.46 [0.456, 0.469] | 4.5% | **win** |
| overhead/pty | chat | input_to_reply_visible_ms | 7.16 | 3.7 | 0.517 [0.486, 0.551] | 16.6% | **win** |
| overhead/pty | chat | input_to_request_ms | 5.28 | 2.55 | 0.482 [0.455, 0.52] | 25.2% | **win** |
| overhead/pty | chat | instructions | 739.60M | 338.17M | 0.457 [0.453, 0.464] | 2.5% | **win** |
| overhead/pty | chat | peak_mem_mib | 26.0 | 14.5 | 0.559 [0.552, 0.564] | 3.4% | **win** |
| overhead/pty | chat | peak_rss_mib | 58.6 | 53.5 | 0.914 [0.909, 0.919] | 1.0% | **win** |
| overhead/pty | chat | ready_cpu_ms | 129 | 47.5 | 0.367 [0.363, 0.373] | 7.7% | **win** |
| overhead/pty | chat | ready_ms | 73.8 | 35.5 | 0.482 [0.478, 0.493] | 2.6% | **win** |
| overhead/pty | chat | ready_pss_mib | 54.0 | 50.0 | 0.925 [0.918, 0.938] | 1.4% | **win** |
| overhead/pty | chat | ready_rss_mib | 55.9 | 51.9 | 0.928 [0.921, 0.94] | 1.3% | **win** |
| overhead/pty | chat | request_bytes | 5,995 | 5,957 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/pty | chat | request_bytes_per_turn | 5,995 | 5,957 | 0.994 [0.994, 0.994] | 0.0% | **win** |
| overhead/rpc-ext10 | chat | cpu_ms | 9,430 | 2,016 | 0.214 [0.212, 0.215] | 2.4% | **win** |
| overhead/rpc-ext10 | chat | cycles | 26064.04M | 5459.33M | 0.209 [0.207, 0.212] | 2.7% | **win** |
| overhead/rpc-ext10 | chat | extensions_ready_cpu_ms | 2,076 | 929 | 0.448 [0.443, 0.455] | 1.6% | **win** |
| overhead/rpc-ext10 | chat | extensions_ready_ms | 1,094 | 592 | 0.541 [0.536, 0.549] | 2.7% | **win** |
| overhead/rpc-ext10 | chat | extensions_ready_pss_mib | 549 | 278 | 0.507 [0.483, 0.564] | 9.2% | **win** |
| overhead/rpc-ext10 | chat | extensions_ready_rss_mib | 578 | 286 | 0.494 [0.471, 0.552] | 8.9% | **win** |
| overhead/rpc-ext10 | chat | instructions | 63851.68M | 10024.49M | 0.157 [0.156, 0.158] | 0.7% | **win** |
| overhead/rpc-ext10 | chat | peak_mem_mib | 595 | 421 | 0.708 [0.601, 0.754] | 19.8% | **win** |
| overhead/rpc-ext10 | chat | peak_rss_mib | 726 | 480 | 0.661 [0.584, 0.688] | 13.2% | **win** |
| overhead/rpc-ext10 | chat | ready_cpu_ms | 2,061 | 929 | 0.451 [0.447, 0.458] | 1.6% | **win** |
| overhead/rpc-ext10 | chat | ready_ms | 1,077 | 579 | 0.538 [0.533, 0.545] | 2.3% | **win** |
| overhead/rpc-ext10 | chat | ready_pss_mib | 549 | 278 | 0.507 [0.483, 0.564] | 9.2% | **win** |
| overhead/rpc-ext10 | chat | ready_rss_mib | 578 | 286 | 0.494 [0.471, 0.552] | 8.9% | **win** |
| overhead/rpc-ext10 | chat | request_bytes | 1.21M | 1.21M | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc-ext10 | chat | request_bytes_per_turn | 60,406 | 60,290 | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc-ext10 | chat | turn_cpu_mean_ms | 384 | 53.3 | 0.139 [0.136, 0.14] | 5.4% | **win** |
| overhead/rpc-ext10 | chat | turn_cpu_ms | 389 | 46.3 | 0.119 [0.117, 0.12] | 4.9% | **win** |
| overhead/rpc-ext10 | chat | turn_extension_cpu_ms | 72.0 | 37.8 | 0.524 [0.507, 0.538] | 5.5% | **win** |
| overhead/rpc-ext10 | chat | turn_harness_added_ms | 112 | 11.2 | 0.0998 [0.0948, 0.105] | 10.5% | **win** |
| overhead/rpc-ext10 | chat | turn_host_cpu_ms | 294 | 14.5 | 0.0493 [0.0474, 0.0527] | 10.9% | **win** |
| overhead/rpc-ext10 | chat | turn_turn_gap_ms | 131 | 16.9 | 0.128 [0.122, 0.129] | 7.2% | **win** |
| overhead/rpc-ext10 | chat | turn_wall_ms | 269 | 34.3 | 0.127 [0.122, 0.13] | 10.4% | **win** |
| overhead/rpc-ext5 | chat | cpu_ms | 5,275 | 1,477 | 0.28 [0.272, 0.285] | 2.2% | **win** |
| overhead/rpc-ext5 | chat | cycles | 14561.32M | 4002.59M | 0.275 [0.268, 0.281] | 2.3% | **win** |
| overhead/rpc-ext5 | chat | extensions_ready_cpu_ms | 1,350 | 842 | 0.624 [0.616, 0.632] | 2.9% | **win** |
| overhead/rpc-ext5 | chat | extensions_ready_ms | 740 | 545 | 0.737 [0.731, 0.753] | 3.9% | **win** |
| overhead/rpc-ext5 | chat | extensions_ready_pss_mib | 371 | 256 | 0.688 [0.665, 0.757] | 13.1% | **win** |
| overhead/rpc-ext5 | chat | extensions_ready_rss_mib | 387 | 263 | 0.68 [0.657, 0.746] | 13.8% | **win** |
| overhead/rpc-ext5 | chat | instructions | 34833.19M | 7212.75M | 0.207 [0.206, 0.208] | 1.1% | **win** |
| overhead/rpc-ext5 | chat | peak_mem_mib | 381 | 309 | 0.813 [0.75, 0.939] | 19.2% | **win** |
| overhead/rpc-ext5 | chat | peak_rss_mib | 513 | 363 | 0.708 [0.668, 0.796] | 15.2% | **win** |
| overhead/rpc-ext5 | chat | ready_cpu_ms | 1,350 | 842 | 0.624 [0.616, 0.632] | 3.0% | **win** |
| overhead/rpc-ext5 | chat | ready_ms | 725 | 533 | 0.735 [0.728, 0.752] | 3.7% | **win** |
| overhead/rpc-ext5 | chat | ready_pss_mib | 371 | 256 | 0.688 [0.665, 0.757] | 13.1% | **win** |
| overhead/rpc-ext5 | chat | ready_rss_mib | 387 | 263 | 0.68 [0.657, 0.746] | 13.9% | **win** |
| overhead/rpc-ext5 | chat | request_bytes | 1.16M | 1.16M | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc-ext5 | chat | request_bytes_per_turn | 58,090 | 57,974 | 0.998 [0.998, 0.998] | 0.0% | **win** |
| overhead/rpc-ext5 | chat | turn_cpu_mean_ms | 206 | 31.2 | 0.151 [0.141, 0.155] | 6.9% | **win** |
| overhead/rpc-ext5 | chat | turn_cpu_ms | 209 | 25.2 | 0.12 [0.116, 0.129] | 9.2% | **win** |
| overhead/rpc-ext5 | chat | turn_extension_cpu_ms | 38.0 | 21.0 | 0.553 [0.526, 0.597] | 8.6% | **win** |
| overhead/rpc-ext5 | chat | turn_harness_added_ms | 57.2 | 6.04 | 0.106 [0.101, 0.107] | 6.0% | **win** |
| overhead/rpc-ext5 | chat | turn_host_cpu_ms | 158 | 8.75 | 0.0555 [0.0535, 0.0609] | 5.9% | **win** |
| overhead/rpc-ext5 | chat | turn_turn_gap_ms | 72.4 | 9.69 | 0.134 [0.132, 0.141] | 8.6% | **win** |
| overhead/rpc-ext5 | chat | turn_wall_ms | 145 | 19.9 | 0.137 [0.13, 0.145] | 9.2% | **win** |

## A/A noise floor — PROVISIONAL

Each arm's A/A copy `<id>-b` is the same executable run in the same rounds. The floor of a cell is the largest deviation from 1 the copy's ratio-of-medians interval allows; a difference between arms smaller than the floor is reported as no measurable difference. The table gives, per arm and workload, the median and the maximum floor over the scored metrics, and the reference's minimum detectable effect at 80% power.

| arm | workload | api | cells | median floor | max floor | worst metric |
|---|---|---|---:|---:|---:|---|
| pi-bun | overhead/print-ext10 | chat | 12 | 4.0% | 20.7% | teardown_ms |
| pi-bun | overhead/print-ext5 | chat | 12 | 1.8% | 13.1% | teardown_ms |
| pi-bun | overhead/print-write | chat | 19 | 2.0% | 9.5% | kb200_peak_mem_mib |
| pi-bun | overhead/pty | chat | 16 | 1.1% | 2.9% | input_to_reply_visible_ms |
| pi-bun | overhead/rpc-ext10 | chat | 23 | 2.9% | 15.0% | teardown_ms |
| pi-bun | overhead/rpc-ext5 | chat | 23 | 3.8% | 21.3% | teardown_ms |
| pi-node | overhead/print-ext10 | chat | 12 | 1.6% | 2.6% | first_request_cpu_ms |
| pi-node | overhead/print-ext5 | chat | 12 | 1.5% | 3.1% | first_request_cpu_ms |
| pi-node | overhead/print-write | chat | 19 | 1.4% | 4.5% | kb200_after_stream_ms |
| pi-node | overhead/pty | chat | 16 | 2.2% | 42.4% | input_to_request_ms |
| pi-node | overhead/rpc-ext10 | chat | 23 | 1.5% | 27.4% | teardown_ms |
| pi-node | overhead/rpc-ext5 | chat | 23 | 1.7% | 12.7% | teardown_ms |
| pibolt | overhead/print-ext10 | chat | 12 | 5.1% | 35.3% | teardown_ms |
| pibolt | overhead/print-ext5 | chat | 12 | 2.2% | 30.0% | teardown_ms |
| pibolt | overhead/print-write | chat | 19 | 1.1% | 13.7% | kb50_after_stream_ms |
| pibolt | overhead/pty | chat | 16 | 1.3% | 5.8% | input_to_request_ms |
| pibolt | overhead/rpc-ext10 | chat | 23 | 2.4% | 13.5% | teardown_ms |
| pibolt | overhead/rpc-ext5 | chat | 23 | 2.6% | 19.8% | teardown_ms |
| pig-0.4.1 | overhead/print-ext10 | chat | 12 | 1.4% | 5.0% | peak_mem_mib |
| pig-0.4.1 | overhead/print-ext5 | chat | 12 | 1.7% | 7.0% | teardown_ms |
| pig-0.4.1 | overhead/print-write | chat | 19 | 0.3% | 6.5% | kb50_peak_mem_mib |
| pig-0.4.1 | overhead/pty | chat | 16 | 2.6% | 25.2% | input_to_request_ms |
| pig-0.4.1 | overhead/rpc-ext10 | chat | 24 | 1.4% | 57.8% | teardown_ms |
| pig-0.4.1 | overhead/rpc-ext5 | chat | 24 | 1.9% | 35.9% | teardown_ms |
| pig-tip | overhead/print-ext10 | chat | 12 | 1.7% | 9.1% | peak_mem_mib |
| pig-tip | overhead/print-ext5 | chat | 12 | 3.0% | 12.5% | teardown_ms |
| pig-tip | overhead/print-write | chat | 19 | 3.5% | 10.3% | kb50_peak_rss_mib |
| pig-tip | overhead/pty | chat | 16 | 1.8% | 9.0% | input_to_request_ms |
| pig-tip | overhead/rpc-ext10 | chat | 24 | 5.5% | 51.2% | teardown_ms |
| pig-tip | overhead/rpc-ext5 | chat | 24 | 6.9% | 73.8% | teardown_ms |

Minimum detectable effect of the reference's A/A pair over all cells: median 1.7%, worst 27.6%. A difference smaller than the cell's MDE cannot be seen in this run.

## Cell ids and rerun commands — PROVISIONAL

Every cell has an id, `<run id>::<workload>@<api>#<metric>`. `python3 -m buffon rerun <cell id> --site <your site profile>` repeats the plan of the run that holds the cell (its arms, rounds, seed and parameters) for that workload and API only, on your host, and compares your result with the original. The raw samples of every cell are in the run directory's raw.json; this report is generated from them and from nothing else, and `buffon verify` regenerates it to check that no number was edited.

| workload | api | metric | cell id |
|---|---|---|---|
| overhead/print-ext10 | chat | cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cpu_ms` |
| overhead/print-ext10 | chat | cycles | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#cycles` |
| overhead/print-ext10 | chat | first_request_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_cpu_ms` |
| overhead/print-ext10 | chat | first_request_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#first_request_ms` |
| overhead/print-ext10 | chat | instructions | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#instructions` |
| overhead/print-ext10 | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_mem_mib` |
| overhead/print-ext10 | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#peak_rss_mib` |
| overhead/print-ext10 | chat | request_bytes | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes` |
| overhead/print-ext10 | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#request_bytes_per_turn` |
| overhead/print-ext10 | chat | requests | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#requests` |
| overhead/print-ext10 | chat | side_requests | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#side_requests` |
| overhead/print-ext10 | chat | teardown_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#teardown_ms` |
| overhead/print-ext10 | chat | wall_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext10@openai-completions#wall_ms` |
| overhead/print-ext5 | chat | cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cpu_ms` |
| overhead/print-ext5 | chat | cycles | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#cycles` |
| overhead/print-ext5 | chat | first_request_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_cpu_ms` |
| overhead/print-ext5 | chat | first_request_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#first_request_ms` |
| overhead/print-ext5 | chat | instructions | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#instructions` |
| overhead/print-ext5 | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_mem_mib` |
| overhead/print-ext5 | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#peak_rss_mib` |
| overhead/print-ext5 | chat | request_bytes | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes` |
| overhead/print-ext5 | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#request_bytes_per_turn` |
| overhead/print-ext5 | chat | requests | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#requests` |
| overhead/print-ext5 | chat | side_requests | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#side_requests` |
| overhead/print-ext5 | chat | teardown_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#teardown_ms` |
| overhead/print-ext5 | chat | wall_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-ext5@openai-completions#wall_ms` |
| overhead/print-write | chat | kb200_after_stream_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_after_stream_ms` |
| overhead/print-write | chat | kb200_call_to_result_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_call_to_result_ms` |
| overhead/print-write | chat | kb200_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cpu_ms` |
| overhead/print-write | chat | kb200_cycles | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_cycles` |
| overhead/print-write | chat | kb200_instructions | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_instructions` |
| overhead/print-write | chat | kb200_peak_mem_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_mem_mib` |
| overhead/print-write | chat | kb200_peak_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_peak_rss_mib` |
| overhead/print-write | chat | kb200_wall_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb200_wall_ms` |
| overhead/print-write | chat | kb50_after_stream_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_after_stream_ms` |
| overhead/print-write | chat | kb50_call_to_result_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_call_to_result_ms` |
| overhead/print-write | chat | kb50_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cpu_ms` |
| overhead/print-write | chat | kb50_cycles | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_cycles` |
| overhead/print-write | chat | kb50_instructions | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_instructions` |
| overhead/print-write | chat | kb50_peak_mem_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_mem_mib` |
| overhead/print-write | chat | kb50_peak_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_peak_rss_mib` |
| overhead/print-write | chat | kb50_wall_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#kb50_wall_ms` |
| overhead/print-write | chat | request_bytes | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes` |
| overhead/print-write | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#request_bytes_per_turn` |
| overhead/print-write | chat | requests | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#requests` |
| overhead/print-write | chat | side_requests | `2026-10-19-smc1-launch-focus-overhead::overhead/print-write@openai-completions#side_requests` |
| overhead/pty | chat | cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cpu_ms` |
| overhead/pty | chat | cycles | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#cycles` |
| overhead/pty | chat | first_frame_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_frame_ms` |
| overhead/pty | chat | first_input_accepted_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#first_input_accepted_ms` |
| overhead/pty | chat | input_to_reply_visible_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_reply_visible_ms` |
| overhead/pty | chat | input_to_request_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#input_to_request_ms` |
| overhead/pty | chat | instructions | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#instructions` |
| overhead/pty | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_mem_mib` |
| overhead/pty | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#peak_rss_mib` |
| overhead/pty | chat | ready_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_cpu_ms` |
| overhead/pty | chat | ready_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_ms` |
| overhead/pty | chat | ready_pss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_pss_mib` |
| overhead/pty | chat | ready_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#ready_rss_mib` |
| overhead/pty | chat | request_bytes | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes` |
| overhead/pty | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#request_bytes_per_turn` |
| overhead/pty | chat | requests | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#requests` |
| overhead/pty | chat | side_requests | `2026-10-19-smc1-launch-focus-overhead::overhead/pty@openai-completions#side_requests` |
| overhead/rpc-ext10 | chat | cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cpu_ms` |
| overhead/rpc-ext10 | chat | cycles | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#cycles` |
| overhead/rpc-ext10 | chat | extensions_ready_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_cpu_ms` |
| overhead/rpc-ext10 | chat | extensions_ready_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_ms` |
| overhead/rpc-ext10 | chat | extensions_ready_pss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_pss_mib` |
| overhead/rpc-ext10 | chat | extensions_ready_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext10 | chat | instructions | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#instructions` |
| overhead/rpc-ext10 | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_mem_mib` |
| overhead/rpc-ext10 | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#peak_rss_mib` |
| overhead/rpc-ext10 | chat | ready_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_cpu_ms` |
| overhead/rpc-ext10 | chat | ready_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_ms` |
| overhead/rpc-ext10 | chat | ready_pss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_pss_mib` |
| overhead/rpc-ext10 | chat | ready_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#ready_rss_mib` |
| overhead/rpc-ext10 | chat | request_bytes | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes` |
| overhead/rpc-ext10 | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext10 | chat | requests | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#requests` |
| overhead/rpc-ext10 | chat | side_requests | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#side_requests` |
| overhead/rpc-ext10 | chat | teardown_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#teardown_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_mean_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc-ext10 | chat | turn_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_extension_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_extension_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_harness_added_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_harness_added_ms` |
| overhead/rpc-ext10 | chat | turn_host_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_host_cpu_ms` |
| overhead/rpc-ext10 | chat | turn_turn_gap_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_turn_gap_ms` |
| overhead/rpc-ext10 | chat | turn_wall_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext10@openai-completions#turn_wall_ms` |
| overhead/rpc-ext5 | chat | cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cpu_ms` |
| overhead/rpc-ext5 | chat | cycles | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#cycles` |
| overhead/rpc-ext5 | chat | extensions_ready_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_cpu_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_ms` |
| overhead/rpc-ext5 | chat | extensions_ready_pss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_pss_mib` |
| overhead/rpc-ext5 | chat | extensions_ready_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#extensions_ready_rss_mib` |
| overhead/rpc-ext5 | chat | instructions | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#instructions` |
| overhead/rpc-ext5 | chat | peak_mem_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_mem_mib` |
| overhead/rpc-ext5 | chat | peak_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#peak_rss_mib` |
| overhead/rpc-ext5 | chat | ready_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_cpu_ms` |
| overhead/rpc-ext5 | chat | ready_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_ms` |
| overhead/rpc-ext5 | chat | ready_pss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_pss_mib` |
| overhead/rpc-ext5 | chat | ready_rss_mib | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#ready_rss_mib` |
| overhead/rpc-ext5 | chat | request_bytes | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes` |
| overhead/rpc-ext5 | chat | request_bytes_per_turn | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#request_bytes_per_turn` |
| overhead/rpc-ext5 | chat | requests | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#requests` |
| overhead/rpc-ext5 | chat | side_requests | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#side_requests` |
| overhead/rpc-ext5 | chat | teardown_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#teardown_ms` |
| overhead/rpc-ext5 | chat | turn_cpu_mean_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_mean_ms` |
| overhead/rpc-ext5 | chat | turn_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_cpu_ms` |
| overhead/rpc-ext5 | chat | turn_extension_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_extension_cpu_ms` |
| overhead/rpc-ext5 | chat | turn_harness_added_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_harness_added_ms` |
| overhead/rpc-ext5 | chat | turn_host_cpu_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_host_cpu_ms` |
| overhead/rpc-ext5 | chat | turn_turn_gap_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_turn_gap_ms` |
| overhead/rpc-ext5 | chat | turn_wall_ms | `2026-10-19-smc1-launch-focus-overhead::overhead/rpc-ext5@openai-completions#turn_wall_ms` |

## Noise report — PROVISIONAL

How noisy this run was, from its own samples and the telemetry taken around each one (docs/TELEMETRY.md). The A/A figures compare each arm with its own identical copy, so they show what the host does to two runs of the same executable.

### Per metric

| metric | cells | A/A gap median | A/A gap worst | A/A floor median | A/A floor worst | CV median | CV worst | outliers / values | drift median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cpu_ms | 5 | 0.8% | 3.1% | 2.9% | 7.8% | 1.5% | 4.4% | 10 / 400 | 0.9% |
| cycles | 5 | 0.7% | 2.2% | 2.6% | 6.4% | 1.5% | 4.4% | 11 / 400 | 0.9% |
| extensions_ready_cpu_ms | 2 | 0.8% | 1.4% | 2.7% | 5.3% | 1.3% | 2.8% | 4 / 160 | 1.1% |
| extensions_ready_ms | 2 | 0.8% | 1.7% | 2.6% | 3.9% | 1.3% | 2.2% | 1 / 160 | 0.5% |
| extensions_ready_pss_mib | 2 | 0.3% | 5.3% | 1.1% | 13.1% | 0.7% | 7.9% | 4 / 160 | 0.4% |
| extensions_ready_rss_mib | 2 | 0.3% | 5.2% | 1.4% | 13.8% | 0.6% | 7.5% | 3 / 160 | 0.3% |
| first_frame_ms | 1 | 1.5% | 2.7% | 3.1% | 3.8% | 1.0% | 3.2% | 2 / 80 | 1.0% |
| first_input_accepted_ms | 1 | 1.2% | 2.8% | 3.1% | 4.5% | 1.4% | 5.2% | 4 / 80 | 0.6% |
| first_request_cpu_ms | 2 | 0.8% | 1.3% | 2.5% | 6.6% | 1.4% | 3.0% | 2 / 160 | 0.7% |
| first_request_ms | 2 | 0.4% | 1.4% | 1.8% | 5.1% | 1.2% | 2.2% | 2 / 160 | 0.9% |
| input_to_reply_visible_ms | 1 | 0.7% | 6.0% | 2.9% | 16.6% | 1.3% | 7.0% | 2 / 80 | 2.5% |
| input_to_request_ms | 1 | 1.7% | 8.7% | 9.0% | 42.4% | 4.5% | 18.7% | 5 / 80 | 2.7% |
| instructions | 5 | 0.1% | 1.1% | 0.9% | 2.5% | 0.3% | 2.8% | 16 / 400 | 0.2% |
| kb200_after_stream_ms | 1 | 0.3% | 1.6% | 2.6% | 10.0% | 1.5% | 4.9% | 5 / 80 | 0.3% |
| kb200_call_to_result_ms | 1 | 0.2% | 0.4% | 1.2% | 4.5% | 0.8% | 2.0% | 3 / 80 | 0.1% |
| kb200_cpu_ms | 1 | 0.2% | 0.4% | 1.9% | 5.5% | 1.1% | 2.8% | 3 / 80 | 0.7% |
| kb200_cycles | 1 | 0.2% | 0.4% | 2.0% | 4.3% | 1.1% | 2.1% | 3 / 80 | 0.3% |
| kb200_instructions | 1 | 0.2% | 0.3% | 0.7% | 8.2% | 0.6% | 4.4% | 1 / 80 | 0.1% |
| kb200_peak_mem_mib | 1 | 0.4% | 1.6% | 1.6% | 9.5% | 1.4% | 31.0% | 2 / 80 | 1.3% |
| kb200_peak_rss_mib | 1 | 0.6% | 1.3% | 1.6% | 8.4% | 1.5% | 28.0% | 1 / 80 | 1.0% |
| kb200_wall_ms | 1 | 0.3% | 1.2% | 2.1% | 4.4% | 1.1% | 2.0% | 3 / 80 | 0.4% |
| kb50_after_stream_ms | 1 | 0.5% | 5.7% | 1.9% | 13.7% | 1.5% | 6.5% | 1 / 80 | 0.8% |
| kb50_call_to_result_ms | 1 | 0.3% | 1.4% | 2.9% | 3.4% | 1.7% | 2.9% | 2 / 80 | 0.7% |
| kb50_cpu_ms | 1 | 0.6% | 1.2% | 2.3% | 5.5% | 1.6% | 3.8% | 1 / 80 | 1.6% |
| kb50_cycles | 1 | 0.0% | 1.2% | 3.0% | 3.5% | 1.7% | 2.8% | 2 / 80 | 0.4% |
| kb50_instructions | 1 | 0.1% | 0.6% | 0.9% | 4.0% | 0.5% | 3.3% | 2 / 80 | 0.9% |
| kb50_peak_mem_mib | 1 | 0.4% | 3.7% | 1.6% | 6.5% | 1.5% | 3.0% | 1 / 80 | 0.9% |
| kb50_peak_rss_mib | 1 | 0.4% | 0.8% | 3.5% | 10.3% | 2.1% | 5.6% | 8 / 80 | 1.6% |
| kb50_wall_ms | 1 | 0.5% | 1.6% | 2.2% | 10.0% | 1.5% | 5.5% | 7 / 80 | 0.1% |
| peak_mem_mib | 5 | 0.5% | 5.7% | 1.5% | 19.8% | 0.7% | 13.0% | 12 / 400 | 0.9% |
| peak_rss_mib | 5 | 0.2% | 5.0% | 1.1% | 15.2% | 0.8% | 9.8% | 12 / 400 | 0.5% |
| ready_cpu_ms | 3 | 0.9% | 2.5% | 2.7% | 7.7% | 1.4% | 3.9% | 8 / 240 | 0.8% |
| ready_ms | 3 | 0.8% | 2.7% | 2.3% | 3.8% | 1.3% | 2.5% | 4 / 240 | 0.5% |
| ready_pss_mib | 3 | 0.2% | 5.3% | 0.8% | 13.1% | 0.8% | 7.9% | 4 / 240 | 0.2% |
| ready_rss_mib | 3 | 0.1% | 5.2% | 1.1% | 13.9% | 0.6% | 7.5% | 3 / 240 | 0.3% |
| request_bytes | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 480 | 0.0% |
| request_bytes_per_turn | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 480 | 0.0% |
| requests | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0 / 480 | 0.0% |
| side_requests | 6 | n/a | n/a | n/a | n/a | n/a | n/a | 0 / 480 | n/a |
| teardown_ms | 4 | 4.9% | 23.4% | 17.4% | 73.8% | 7.2% | 38.3% | 7 / 320 | 5.1% |
| turn_cpu_mean_ms | 2 | 0.9% | 3.6% | 6.1% | 9.3% | 3.2% | 5.5% | 1 / 160 | 2.4% |
| turn_cpu_ms | 2 | 1.9% | 4.0% | 5.8% | 10.5% | 4.1% | 9.4% | 4 / 160 | 1.6% |
| turn_extension_cpu_ms | 2 | 1.3% | 2.6% | 4.5% | 8.6% | 3.1% | 6.5% | 0 / 160 | 2.5% |
| turn_harness_added_ms | 2 | 1.2% | 7.0% | 7.2% | 14.7% | 4.2% | 10.3% | 5 / 160 | 2.0% |
| turn_host_cpu_ms | 2 | 0.1% | 3.4% | 6.0% | 12.5% | 4.0% | 8.4% | 9 / 160 | 1.6% |
| turn_turn_gap_ms | 2 | 1.8% | 4.5% | 7.5% | 18.9% | 3.6% | 8.9% | 4 / 160 | 1.3% |
| turn_wall_ms | 2 | 2.0% | 4.2% | 6.2% | 10.4% | 3.0% | 5.8% | 1 / 160 | 0.9% |
| wall_ms | 2 | 0.4% | 2.2% | 1.7% | 6.4% | 1.2% | 2.2% | 1 / 160 | 1.4% |

A/A gap: the copy's median against the arm's, per cell. A/A floor: the largest deviation from 1 the copy's ratio interval allows (METHODOLOGY section 6). CV: the standard deviation of an arm's rounds over their mean. Outliers: a measured value is an outlier when |x - median| > 5 x 1.4826 x MAD of its arm's values in that cell (needs 4 values; with MAD 0, any different value). Outliers are counted, never removed. Drift: the Theil-Sen trend of an arm's rounds times the rounds spanned, as a share of its median.

### Run 1

- Samples: 480 measured (480 ok, 0 failed), 60 warm-up; telemetry on 480 of 480 ok samples. Sources read: cgroup_throttle, cpufreq, loadavg, meminfo, pressure, proc_stat, schedstat, thermal_throttle, vmstat.
- Calibration: CV 1.5% of cpu_ms on pi-node (gate 5.0%), passed.
- CFS throttling: 0 samples, 0 us in all; the session's cgroup lost 0 us over the whole run.
- Quiet-host gate: 479 passed at once, 1 waited (longest 1.6 s, 1.6 s in all), 0 gave up.
- Steal: 0.000% of the pinned CPUs' capacity. Foreign CPU on the pinned CPUs: p95 0.0% of the sample's CPU time. Clock: largest deviation 0.1% from the median 2800 MHz. iowait is recorded in every sample and never gated.
- Failed samples: 0 arm, 0 infrastructure (the arm is not charged for those); 0 ladder stops (a swarm rung that hit the kernel's limit: a result, not a failure). CPU quota on the arm cgroup or an ancestor: none.
- Flagged samples: 18 of 480 (foreign_busy 1, clock_moved 16, gate_waited 1).
- Telemetry cost: the collector's thread used 10.79 ms median per sample (worst 359.72 ms), on the runner's CPUs, outside the pinned set.
- Host load before / after: 1.5 / 1.4; pinned CPUs busy over the run: mean 16.5%, max 25.7%.

Flagged samples (kept in the statistics unless the report is made with `--drop-flagged`; the first 18 of 18):

| arm | workload | api | round | flags |
|---|---|---|---:|---|
| pi-node | overhead/print-write | openai-completions | 1 | clock_moved |
| pi-bun-b | overhead/print-write | openai-completions | 1 | clock_moved |
| pi-bun | overhead/print-write | openai-completions | 2 | clock_moved |
| pi-bun-b | overhead/print-write | openai-completions | 2 | clock_moved |
| pi-node | overhead/rpc-ext10 | openai-completions | 3 | clock_moved |
| pi-node-b | overhead/print-write | openai-completions | 3 | clock_moved |
| pi-bun-b | overhead/print-write | openai-completions | 3 | clock_moved |
| pi-bun | overhead/print-write | openai-completions | 3 | clock_moved |
| pi-bun | overhead/print-write | openai-completions | 4 | clock_moved |
| pi-bun-b | overhead/print-write | openai-completions | 5 | clock_moved |
| pi-bun | overhead/print-write | openai-completions | 5 | clock_moved |
| pi-bun | overhead/print-write | openai-completions | 6 | clock_moved |
| pi-node | overhead/print-ext10 | openai-completions | 7 | foreign_busy |
| pi-bun-b | overhead/print-ext10 | openai-completions | 7 | gate_waited |
| pi-bun-b | overhead/print-write | openai-completions | 7 | clock_moved |
| pi-bun | overhead/print-write | openai-completions | 7 | clock_moved |
| pi-node-b | overhead/print-write | openai-completions | 7 | clock_moved |
| pi-bun-b | overhead/print-write | openai-completions | 8 | clock_moved |

### Do the flagged rounds change the answer?

The report was built again without the 10 flagged rounds: 128 of 344 comparisons change verdict.

| workload | api | metric | arm | with flagged rounds | without |
|---|---|---|---|---|---|
| overhead/print-ext10 | openai-completions | cpu_ms | pi-bun | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | cpu_ms | pibolt | win | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | cpu_ms | pig-0.4.1 | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | cpu_ms | pig-tip | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | cycles | pi-bun | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | cycles | pibolt | win | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | cycles | pig-0.4.1 | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | cycles | pig-tip | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | first_request_cpu_ms | pi-bun | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | first_request_cpu_ms | pibolt | win | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | first_request_cpu_ms | pig-0.4.1 | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | first_request_cpu_ms | pig-tip | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | first_request_ms | pi-bun | loss | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | first_request_ms | pibolt | win | inconclusive (paired test p 0.062 >= 0.05) |
| overhead/print-ext10 | openai-completions | first_request_ms | pig-0.4.1 | loss | inconclusive (paired test p 0.062 >= 0.05) |

### Samples and rounds not in the statistics

| reason | samples | rounds |
|---|---:|---:|
| warm-up round (kept in the raw data, excluded from the statistics by rule) | 60 | 1 |

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
| pig-tip | 0.5.0+1.3.0 | git 26eaad58e3ec09e25adf74000f79bcd83123aa8c | tree `8b867e1919867ebfc99e50c7a630f27f0ce9be30` | go build -buildvcs=false -trimpath -ldflags -s -w -X github.com/MichaelKinsy/PiG/coding/cli.Build=26eaad58e3ec09e25adf74000f79bcd83123aa8c -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateURL=https://github.com/MichaelKinsy/PiG/releases/latest/download/update.json -X github.com/MichaelKinsy/PiG/internal/codingagent.DefaultUpdateTrustRoot=LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUNvd0JRWURLMlZ3QXlFQVFBdUtJTHRmc0FpbWdabnRpZ2UydzRGRy9QeDFQeU5HampHYXlEalREM0k9Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQo= -X github.com/MichaelKinsy/PiG/coding/pigletbuild.releaseSourceVersion=v0.5.0 -o /local/kinsy/arena/home/work/buffon-nyn5nd13/arms/pig-tip-a/bin/pig ./cmd/pig; toolchain go 1.27.2; linux-x64 | `d0032cdda0e713436aa3f6930bb5cac18491bdd91011ffa362100c5bd6b4526f` | `cc759dbd134406f976bb90fbb8fe5a0c3dc4d76a83b7de26d731daa6ef982b21` |

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
| idle_after | {"48": 0.0, "49": 0.0, "50": 0.0, "51": 0.0, "112": 0.0, "113": 0.0, "114": 0.0, "115": 0.0} |
| load_before | [1.5390625, 1.4228515625, 1.1005859375] |
| load_after | [1.41650390625, 1.76025390625, 1.78271484375] |
| throttled_usec | 0 |
| cpumon | {"samples": 3249, "pinned_busy_mean": 0.16544446029293886, "pinned_busy_max": 0.25687506250625064, "host_busy_mean": 0.014122724373804607} |
| go | null |
| node_js | null |
| python | 3.12.3 |

Variables each harness was started with beyond the host's environment (the throwaway root is `<work>`); credential-looking and proxy variables of the host are removed:

- **pi-bun**: `HOME=<work>/pi-bun-a-pty-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-a-pty-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-a-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-a-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-a-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-a-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-a-pty-openai/home/.local/state`
- **pi-bun-b**: `HOME=<work>/pi-bun-b-pty-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-bun-b-pty-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-bun-b-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-bun-b-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-bun-b-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-bun-b-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-bun-b-pty-openai/home/.local/state`
- **pi-node**: `HOME=<work>/pi-node-a-pty-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-nyn5nd13/arms/pi-node-a/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-nyn5nd13/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-a-pty-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-a-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-a-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-a-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-a-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-a-pty-openai/home/.local/state`
- **pi-node-b**: `HOME=<work>/pi-node-b-pty-openai/home`, `NODE_COMPILE_CACHE=/local/kinsy/arena/home/work/buffon-nyn5nd13/arms/pi-node-b/node-compile-cache`, `PATH=/local/kinsy/arena/home/work/buffon-nyn5nd13/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pi-node-b-pty-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pi-node-b-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pi-node-b-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pi-node-b-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pi-node-b-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pi-node-b-pty-openai/home/.local/state`
- **pibolt**: `HOME=<work>/pibolt-a-pty-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-a-pty-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-a-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-a-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-a-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-a-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-a-pty-openai/home/.local/state`
- **pibolt-b**: `HOME=<work>/pibolt-b-pty-openai/home`, `PATH=/usr/bin:/bin`, `PI_CODING_AGENT_DIR=<work>/pibolt-b-pty-openai/home/.agent`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pibolt-b-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pibolt-b-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pibolt-b-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pibolt-b-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pibolt-b-pty-openai/home/.local/state`
- **pig-0.4.1**: `HOME=<work>/pig-0.4.1-a-pty-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-nyn5nd13/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-a-pty-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-a-pty-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-a-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-a-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-a-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-a-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-a-pty-openai/home/.local/state`
- **pig-0.4.1-b**: `HOME=<work>/pig-0.4.1-b-pty-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-nyn5nd13/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-0.4.1-b-pty-openai/home/.agent`, `PIG_HOME=<work>/pig-0.4.1-b-pty-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-0.4.1-b-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-0.4.1-b-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-0.4.1-b-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-0.4.1-b-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-0.4.1-b-pty-openai/home/.local/state`
- **pig-tip**: `HOME=<work>/pig-tip-a-pty-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-nyn5nd13/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-a-pty-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-a-pty-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-a-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-a-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-a-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-a-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-a-pty-openai/home/.local/state`
- **pig-tip-b**: `HOME=<work>/pig-tip-b-pty-openai/home`, `PATH=/local/kinsy/arena/home/work/buffon-nyn5nd13/runtimes/node/node-v24.19.0-linux-x64/bin:/usr/bin:/bin`, `PIG_CODING_AGENT_DIR=<work>/pig-tip-b-pty-openai/home/.agent`, `PIG_HOME=<work>/pig-tip-b-pty-openai/disk/pig`, `PIG_OFFLINE=1`, `PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, `PI_TELEMETRY=0`, `TMPDIR=<work>/pig-tip-b-pty-openai/disk/tmp`, `XDG_CACHE_HOME=<work>/pig-tip-b-pty-openai/disk/cache`, `XDG_CONFIG_HOME=<work>/pig-tip-b-pty-openai/home/.config`, `XDG_DATA_HOME=<work>/pig-tip-b-pty-openai/home/.local/share`, `XDG_STATE_HOME=<work>/pig-tip-b-pty-openai/home/.local/state`

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
*PROVISIONAL: generated from 1 run directory by `buffon report`; 4 notes: aa_gap_max 23.4%, aa_floor_max 73.8%, outlier_fraction 2.1%, hardware; the raw samples are in each directory's raw.json. The same data as report.html, report.json, summary.csv, rounds.csv, noise.csv and telemetry.csv.*
