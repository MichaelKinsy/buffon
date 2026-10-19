# Telemetry

Every result carries a picture of the system it ran on. The runner records, for every measured sample, what the machine, the pinned CPUs and the sample's own cgroup were doing before, during and after it. The report turns that into a noise report, the run notes (docs/HEALTH.md) and per-round series, and `buffon reproduce` compares it between two hosts (docs/SUBMITTING.md).

Telemetry is a runner observer (docs/HOOKS.md) that is on by default, in `buffon session`, so a Kubernetes pod records it without any flag. `--no-telemetry` turns it off; `buffon verify` rejects the run, because every other check reads this record. `--telemetry-interval` sets the seconds between readings during a sample (default 0.25, 0 means only before and after).

## What is read

Only `/proc`, `/sys` and cgroup files, a few times a second, by a thread that runs on the runner's CPUs (the mock's), never on a pinned CPU. A source the machine does not have (a pod that cannot see cpufreq, a kernel without PSI, a VM without thermal counters) is absent from the record and from its `sources` list, never a zero.

| group | content | source |
|---|---|---|
| `before`, `after` | load, runnable tasks, available memory, the pinned CPUs' clock (min, mean, max) | `/proc/loadavg`, `/proc/meminfo`, cpufreq, else `/proc/cpuinfo` |
| `during` | the same gauges read while the sample ran: clock min / mean / max, highest load and runnable count, highest pinned-CPU busy share, number of readings | as above, `/proc/stat` |
| `cpuset` | what the pinned CPUs did between begin and end, by kind: busy, user, system, iowait, irq and softirq, steal, idle; run-queue wait; CFS throttling of the session's cgroup chain; pressure (PSI) of cpu, memory and io; swapped pages; thermal throttle events | `/proc/stat`, `/proc/schedstat`, cgroup `cpu.stat`, `/proc/pressure/*`, `/proc/vmstat`, `thermal_throttle` |
| `cgroup` | the sample's own cgroup, read just before its meter removes it: CPU time (user, system), `nr_throttled` and throttled time, peak and current memory, peak pids, IO bytes, page faults (minor and major), pressure, `memory.events` (high, max, oom, oom_kill); the ancestors' cumulative throttling and every ancestor with a CPU quota. Under the rusage meter: CPU time, faults, block IO and context switches from `wait4` | cgroup v2 files, `os.wait4` |
| `gate` | what the quiet-host gate did before the sample: passed at once, waited (how long, how many readings), disabled | the runner |
| `collector` | the observer's own cost: CPU time of its thread, readings taken | the observer |
| `sources` | the sources that could be read | |

`raw["run"]["telemetry"]["system"]` holds the run-level `start` (interval, CPU set, sources, gauges, own cgroup, CPU quota found on its chain) and `end` (gauges).

iowait is recorded and never gated: the kernel documents it as unreliable. The run-queue wait of the pinned CPUs includes a harness's own threads waiting for each other, so it is recorded and not flagged.

## Flags, outliers, throttling

A measured sample carries a flag when its telemetry crosses a rule in `workloads/health.toml`: CFS throttling, foreign CPU on the pinned CPUs, steal, clock movement, a gate that had to wait, swapping, thermal throttling, a memory event. Flagged samples stay in the statistics; `buffon report --drop-flagged` builds the report again without the rounds that carry one, and the noise report says how many comparisons would change verdict. A value is an outlier when it lies more than 5 robust standard deviations (5 x 1.4826 x MAD) from its arm's median in a cell; outliers are counted, never removed.

Throttling counters in cgroup v2 are not hierarchical: a limit on a pod or a container shows only on that cgroup. The runner therefore reads `nr_throttled` on the sample's cgroup, on every ancestor above it, and on the session, and any throttled period of a measured sample is a run note. A CPU quota (`cpu.max`) anywhere on the chain is a run note as well.

## Cost

A full reading (every counter, the sample's cgroup chain, pressure) costs the collector about 14 ms of CPU on a 224-CPU host (measured 2026-10-12 with 31 pinned CPUs: `/proc/stat` and the cgroup `cpu.stat` reads are the slow ones, and they grow with the CPU count and cgroup count). The runner therefore takes the full reading only twice per sample, before and after. The sampler thread inside the sample takes light readings (busy ticks, clock, load), about 1.7 ms each on the same host. The sampler is a Python thread in the runner process. It is affinity-pinned away from the pinned CPUs, but it shares the interpreter lock with the runner's in-process mock: while it parses a reading (about 1.5 ms, four times a second) a mock response can wait for the lock. That effect is not measured yet on a quiet host. `--telemetry-interval 0` removes the thread (readings before and after only) and is the setting to compare against.

The record keeps the collector's own cost per sample: `collector.thread_cpu_ms` (the sampler thread), `begin_cpu_ms` and `end_cpu_ms` (the two full readings). The noise report prints their sum as the observer's cost. A cost that is large next to a short sample is a reason to raise `--telemetry-interval` or pass `--telemetry-interval 0` (readings before and after only). Whether telemetry moves a measurement is an experiment, not an assumption: the same plan run with and without `--no-telemetry` must give A/A floors and medians that agree within the floor (docs/RUNNING.md, "Telemetry cost").

## Per-round series and plots

`rounds.csv` has one row per measured value of a scored metric in the order the samples ran, with the telemetry around it; `telemetry.csv` has one row per sample with every telemetry field; `noise.csv` the noise of each arm in each cell. `plots/` holds one SVG per cell (the arms' rounds, A/A copies dashed, amount axes from zero), one A/A ratio plot per cell, and three host plots (pinned CPUs' busy share, clock, load). `report.html` embeds the headline ones. All of them come from the same data as `report.md` and `report.json`.

## Backends

The local and Kubernetes backends run the same session, so they record the same telemetry. A pod's cgroup is usually read-only and the meter falls back to rusage; the record then says `mode: rusage` and has no cgroup-only fields. A pod that cannot read cpufreq reports no clock, and a missing clock is a run note.

With `--isolation container` the arm runs in its own container cgroup, which is gone when the container stops. The relay reads it the instant the arm exits, and the sample's `cgroup` record has `mode: container` with the arm's CPU (the container's usage after the relay started the arm, less the relay's own CPU, the figure the sample reports as `cpu_ms`), the container's `throttled_periods`, `throttled_us` and `periods`, and the memory and pid peaks. Pressure, IO and memory events are not read, so those fields are absent for a container sample. Any throttled period of a container is RED, as for any cgroup. A container sample is not under the session's CPU quota, so the session's own quota is not judged for it.
