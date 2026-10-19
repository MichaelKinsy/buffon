# Run health

Every report lists run notes: what the host and the run looked like. A run note is information for the reader. It does not grade a run. A note never rejects a run, removes a number or changes one.

Each check has three parts: its measured value, a one-line meaning, and a status. The status is `ok` when the value is inside the usual range. It is `note` when the value is outside. The summary is the list of notes, for example `3 notes: flagged_fraction 91.3%, clock_deviation 7.6%, hardware`. A run with no note says `no notes`.

Use the notes to judge how far to trust a comparison. A host that was busy, throttled or changing its clock adds noise to every number. The reader decides what that means for the question at hand.

The notes are computed from the raw data and the usual ranges below. A reader, a reproducer and CI get the same answer from the same run directory. They are not stored in raw.json. `buffon health <run directory>` prints them. The report, `health.json` and the Runs page of the site show them with the notes first.

## Usual ranges

The ranges are in `workloads/health.toml` (read by `buffon/report/thresholds.py`). They are the same for every run. A change to one is a change of method: every `health.json` carries the sha256 of the file, and `tests/test_health.py` fails when this page and the file differ. Regenerate the tables with `python3 -m buffon health thresholds`.

A value is outside the usual range when it is strictly greater than the number in the table. A check with no data (for example the A/A gap of a run with no scored cell) has no value and no note. A measurement the machine or the run did not provide (steal, foreign CPU, the clock, flagged samples) is a note, so the reader knows it is missing.

<!-- BEGIN THRESHOLDS -->
| id | what is checked | usual range | what it means |
|---|---|---:|---|
| `calibration_cv` | Calibration: CV of the reference's CPU time between identical runs | up to 2.0% | How much the reference's CPU time varied between identical calibration runs. Lower means a quieter host. |
| `aa_cv_cpu` | A/A CV of CPU metrics, median over arms and cells | up to 2.0% | How much CPU time varies from round to round for one harness. Lower means a quieter host. |
| `aa_significant_fraction` | A/A pairs with a significant gap (paired p < 0.05, before Holm) that is also larger than 1% | up to 5.0% | Share of harness and copy pairs that differ by more than 1% and also pass a significance test. A gap under 1% on a steady counter is not counted. About 5% can happen by chance. |
| `aa_gap_median` | A/A gap between a harness and its own copy, median over cells | up to 1.0% | The usual gap between a harness and its identical copy. A real difference between two harnesses should be larger than this. |
| `aa_gap_max` | A/A gap between a harness and its own copy, largest cell | up to 5.0% | The largest gap between a harness and its identical copy, and the cell where it happened. |
| `aa_floor_median` | A/A noise floor, median over scored cells | up to 3.0% | The smallest difference the identical copies cannot tell from noise, in the usual cell. Smaller differences than this are not resolved. |
| `aa_floor_max` | A/A noise floor, worst scored cell | up to 15.0% | The same floor in the noisiest cell. Comparisons in that cell resolve only larger differences. |
| `outlier_fraction` | Measured values flagged by the MAD rule | up to 2.0% | Share of measured values far from the median of their cell. Outliers are counted and never removed. |
| `flagged_fraction` | Measured samples with at least one host flag | up to 5.0% | Share of samples where the host showed a disturbance: throttling, foreign CPU, steal, a clock change, swap or a memory event. |
| `throttled_samples` | Measured samples with CFS throttling (arm cgroup, every ancestor, session) | up to 0 | Samples where the kernel held the process back for a CPU quota. Their time then describes the quota, not the harness. |
| `steal_share` | Steal: share of the pinned CPUs' capacity taken by a hypervisor | up to 0.1% | Share of the pinned CPUs' time that a hypervisor took away. It only matters on virtual machines. |
| `foreign_cpu_p95` | Foreign CPU on the pinned CPUs during a sample, p95 over samples, as a share of the sample's CPU time | up to 1.0% | CPU time that other processes used on the pinned cores during a sample, as a share of the sample's own CPU time (95th percentile). |
| `gate_slow_fraction` | Samples that waited more than 1 s for the host to quiet down | up to 1.0% | Share of samples that had to wait for the quiet-host gate. A busy host makes the gate wait. |
| `gate_gave_up` | Samples for which the host never quieted down | up to 0 | Samples that did not start because the host stayed busy. They are not in the numbers. |
| `clock_deviation` | Effective clock: largest deviation of a sample's mean MHz from the run median | up to 2.0% | How far a sample's mean CPU clock moved from the run median. A moving clock changes CPU time for the same work. |
| `infra_failed_fraction` | Infrastructure failures (envelope OOM, no process started, runner fault) over measured samples | up to 0.0% | Share of samples that failed because of the host or the runner. They are never charged to a harness. |
| `arm_failed_fraction` | Arm failures over measured samples (a swarm ladder's designed stops are results and not counted) | up to 2.0% | Share of samples where the harness itself failed. A scale sample that stopped because the kernel's limit was reached (stop_cause oom, pids or timeout) is a result and is in neither the failures nor the samples counted; a scale error stop is a failure. |
| `drift` | Drift: median absolute change over the run of an arm's value, over cells | up to 2.0% | How much a harness's value moved from the start of the run to the end. Drift means the host changed during the run. |

| id | what is checked | what it means |
|---|---|---|
| `reference_changepoint` | No change point in the reference arm's per-round series | The host's speed did not shift during the run. A shift moves every comparison the same way. |
| `rounds` | At least 12 measured rounds | With fewer rounds the intervals are wide. |
| `aa_copies` | Every arm has an A/A copy | Without a copy there is no noise floor for that harness. |
| `hardware` | Quiet dedicated hardware by the runner's own detection | On shared hardware other work can disturb the numbers. |
| `egress` | No harness connected outside the loopback | A harness that talks to the network is not measured alone. |
| `integrity` | Every executable and install tree unchanged during the run | A changed executable means the arm is not what the lock names. |
| `calibration_ran` | Calibration ran and the reference stayed within its 5% limit | Calibration shows the host's noise before the run. Above 5% the run is labelled Noisy. |
| `telemetry` | Telemetry recorded for every measured sample | Telemetry is how the other checks see the host. |
| `cpu_quota` | No CPU quota (cpu.max) on the arm cgroup or any ancestor | A quota can throttle a sample. |
| `clock_policy` | The pinned CPUs have a fixed clock policy | A clock that scales with load changes CPU time for the same work. |

Flags on a sample:

| flag | rule |
|---|---|
| `throttled` | CFS throttled the sample's cgroup, an ancestor or the session (1 period or more) |
| `foreign_busy` | the pinned CPUs were busy beyond the sample's own CPU time by more than 3% of their capacity (and 2 clock ticks per sqrt(CPU)) |
| `steal` | a hypervisor took more than 0.1% of the pinned CPUs' capacity |
| `clock_moved` | the pinned CPUs' clock moved by more than 5% during the sample |
| `gate_waited` | the quiet-host gate needed more than one reading before the sample started |
| `swap` | the host swapped 1 page or more during the sample |
| `thermal` | the pinned CPUs were thermally throttled 1 time or more during the sample |
| `memory_events` | the kernel reported a memory.high, memory.max or OOM event for the sample's cgroup |

Outliers: a measured value is an outlier when |x - median| > 5 x 1.4826 x MAD of its arm's values in that cell (needs 4 values; with MAD 0, any different value). Outliers are counted, never removed.

Change point: one test on the reference arm's per-round index, alpha 0.01, segments of at least 3 rounds, 999 permutations.

A/A pairs: a pair counts as different when its paired p is below 0.05 and its gap is larger than 1%.
<!-- END THRESHOLDS -->

## How each value is computed

- **Calibration CV**: the larger coefficient of variation of the reference's CPU time over the calibration runs, the reference against its own A/A copy. This is the one noise limit the runner acts on: above 5% (`CV_GATE`) the run is labelled Noisy and goes on, and only `--require-class A` refuses it. The usual range of 2% in the table is a note, not a limit.
- **A/A CV of CPU metrics**: the CV of each arm and of its A/A copy in every cell whose metric is a CPU time (`cpu_*`); the median.
- **A/A gap**: for every arm with a copy and every scored cell, the distance of the copy's median from the arm's median, as a percent. The report shows the median over cells and the largest gap with the cell it happened in.
- **A/A pairs that look different**: a pair counts when a paired t-test on the log ratio of the copy to the arm gives p < 0.05 and the gap is larger than 1%. A steady gap under 1% on a near-deterministic counter is significant to the test but does not matter, so it is not counted. About 5% of pairs can count by chance.
- **A/A noise floor**: per cell, the largest deviation from 1 that the ratio-of-medians interval of an arm against its own identical copy allows, on the log scale (METHODOLOGY section 6). The median and the worst over every scored cell.
- **Outliers**: per arm and cell, a value is flagged when it lies more than 5 robust standard deviations (5 x 1.4826 x MAD) from the median. Outliers are counted and never removed.
- **Flagged samples**: a measured sample carries a flag when its telemetry crosses one of the flag rules below. Flagged samples stay in the statistics. `buffon report --drop-flagged` builds the report again without the rounds that carry one (all arms together, so the interleaving stays symmetric). The noise report says how many comparisons would change if they were dropped.
- **Throttling**: `nr_throttled` read on the sample's own cgroup, on every ancestor above it, and on the session's cgroup. The counters are not hierarchical, so a limit on the pod or the container shows only on that cgroup. An ancestor's counter is cumulative, so each sample gets its growth since the previous sample. A throttled process waits for the next period, so its wall and CPU time then describe the quota.
- **CPU quota**: `cpu.max` of the arm cgroup and every ancestor should be `max`. Without a cgroup meter the session's own cgroup chain counts.
- **Steal**: the steal time on the pinned CPUs over their capacity (window times CPUs), summed over the run (the worst run when several are pooled).
- **Foreign CPU**: during a sample, the busy time of the pinned CPUs (`/proc/stat`) minus the sample's own cgroup CPU time, minus what the clock-tick resolution can invent (2 ticks per square root of the CPUs), as a share of the sample's own CPU time. The 95th percentile over samples.
- **Clock**: the largest deviation of a sample's mean clock on the pinned CPUs from the run's median. A pinned CPU whose clock policy scales with load is a note on `clock_policy`.
- **iowait** is recorded in every sample and never checked: the kernel documents it as unreliable.
- **Gate**: the quiet-host gate's record for each sample: passed at once, waited (how long), or gave up (no process was started). A wait counts as slow above one second.
- **Failures**: a failed sample is an infrastructure failure when the host never quieted down, the runner failed, no process was started or the kernel killed the cgroup for memory. Otherwise it is the arm's. Infrastructure failures are never charged to an arm.
- **Reference change point**: the reference arm's value in each scored cell divided by its median in that cell, averaged geometrically per round, gives one series. The split with the largest Welch t is tested by a seeded permutation test at alpha 0.01. Any change point is a note. The detail shows the shift next to the reference's A/A floor.
- **Drift**: the Theil-Sen trend of an arm's value over the rounds, times the rounds spanned, as a share of its median. The median of the absolute values over every arm and cell.

Not checked: the warm-up position effect, the number of independent sessions behind a headline, and the host-class preflight (exclusive cores, SMT siblings, NUMA). They belong to the runner and the site.

- **Scale limits are results.** A scale search sample (`scale/*-limit`, `scale/*-ext10`) finds the largest number of agents that complete: the probes that fail on the way are inside the sample (`probes`), and a sample with at least one agent is no failure. A sample that carries `failure` because not even one agent finished, with `stop_cause` `oom`, `pids` or `timeout`, is the designed end of the search: the harness's result is a limit of 0 (an old doubling-only run: the rung where it stopped). It is not an arm failure, not an infrastructure failure, and not one of the samples the failure fractions count. A scale stop with `stop_cause` `error` is still an arm failure. The run notes list the number of stops. The A/A checks pair a harness and its copy only in the rounds where both completed (a stopped rung is not a value), and the host-side `runner_cpu_ms` of a swarm sample is a descriptor, not a scored metric. A large gap in a rung near the limit (a thousand agents queueing on a few CPUs) is real variation and stays a note.

## What notes are not

A note is not a grade and a run with no note is not a proof of correctness. No note does not say that the arms were set up fairly, that the workload is representative, or that a difference is large. A note says where to look: the report's noise section names the cells and samples behind each one.

## Submissions

`buffon verify --submission` lists the notes of a run and never rejects a run for them. It rejects integrity problems only (docs/SUBMITTING.md, section 4).
