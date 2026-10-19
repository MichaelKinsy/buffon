# Limitations

What a Buffon number can and cannot tell you. Read this page before you compare two numbers. Each limitation says what is limited, how it changes the way to read a number, and what the report does about it.

None of these makes a result wrong. They say what question a result answers. [WHAT-WE-MEASURE.md](WHAT-WE-MEASURE.md) gives the limits specific to each family, and [METHODOLOGY.md](METHODOLOGY.md) says how the numbers are produced.

## 1. A mock model is not a network

The mock model replies at once, with no network latency and no provider variance. A real turn is dominated by model time and network time.

*Reading a number:* it describes what the harness adds to a turn, and not the time a person waits.
*Where a real model is used:* only in the opt-in [field track](FIELD.md), which is planned and is kept out of the grade.

## 2. Mock token counts are estimates

The mock reports prompt tokens as the request's wire bytes divided by 4, and completion tokens from the stream. They are not a provider's counts. A harness that sends a larger request sees a larger count and compacts earlier. That is part of what is measured.

*Reading a number:* a difference in compaction behaviour can come from request size and does not show a difference in how well a harness compacts.
*The report:* records the wire bytes of every request, so a reader can see the size that drove a count.

## 3. One machine, one kernel

A run comes from one host, with one CPU model, kernel, frequency governor and terminal. Another host can give other values.

*Reading a number:* it holds for the host in the report. The A/A floor and the minimum detectable effect state how noisy this run was on this host, and neither removes the host.
*The report:* records the host and labels a run that is not on quiet dedicated hardware PROVISIONAL. An independent rerun on a second host is required before any public release.

*Slots (opt-in):* with `[local] slots`, several sessions share one host and one kernel. The slot calibration shows that the reference arm's CPU and wall time did not move on its workloads; it does not show the same for a family that stresses the shared last-level cache, memory bandwidth or disk harder. Each session's own A/A floor and quiet check are where such interference would show. A slotted run is one more reason to rerun on a host that runs one session at a time before a public release.

## 4. Memory means different things

"Memory" names four readings, and each answers a different question. A report gives each its own column and names it.

| kind | what it counts |
|---|---|
| own footprint | memory this process holds that no other process shares |
| RSS | the pages of this process that are in RAM now, shared libraries and shared pages included |
| peak RSS | the largest RSS the process reached |
| heap in use | what the runtime itself reports using, where the arm exposes it |

Footprint can sit far below RSS, because RSS counts shared pages. A runtime with a lazy garbage collector can hold memory it no longer needs, and a reading right after an answer differs from the reading at rest. So each sampled kind is read at fixed times after the last answer (30 ms, 2 s and 10 s), and a report names the kind and the time of every memory column ([REPORT-TEMPLATE.md](REPORT-TEMPLATE.md)). Today a run reports peak RSS and PSS samples. Own footprint, heap in use and the three times are planned.

### Why a macOS footprint depends on the allocator

On macOS, own footprint is `ri_phys_footprint`, read through `proc_pid_rusage`. It is a figure the kernel keeps per process. On Linux the matching figure is `Private_Dirty` from `smaps_rollup`, the private pages the process has modified. Pages of a file on a memory-backed file system (tmpfs, `/dev/shm`) are shared memory, and a mapping of one counts as dirty: an executable, a runtime image or a cache that runs from a tmpfs directory adds its whole text to `Private_Dirty`. A footprint number is like-for-like only when every arm's code runs from disk; the container envelope's HOME and TMPDIR are tmpfs (METHODOLOGY Run Rule 9), so a footprint column must state where each arm's executable and runtime images were mapped from. Both aim at "memory only this process holds", through different kernel accounting, so they are not the same quantity.

An allocator on macOS can tell the kernel that it has finished with pages (`MADV_FREE_REUSABLE`) and later that it uses them again (`MADV_FREE_REUSE`). The footprint of a process can depend on whether the allocator makes the second call. A comment in the allocator mimalloc, in the fork kept by the `oven-sh` organisation, explains why that fork does not make it:

> Deliberately do NOT call MADV_FREE_REUSE. The kernel charges pages to phys_footprint as they are touched, but the explicit REUSE re-charges the ENTIRE range up front -- including OS pages the program never touches again.

The same comment says that issuing the call would have changed a measurement its authors made on a churn workload "24MB -> 161MB", and that libpas and bmalloc, the allocators of WebKit, do not issue it on Darwin for the same reason.

| | |
|---|---|
| repository | `oven-sh/mimalloc` |
| commit | `92ef6587c57b262f6e6abf513f7776a2f8d12aeb` (`92ef658`, 2026-10-04) |
| file and lines | `src/prim/unix/prim.c`, lines 554-567, the function `_mi_prim_reuse` |
| sha256 of those 14 lines | `9c14851be044c9edb60ff077df267511b820a8995bb41374a42d000cfe822fde` |
| checked | 2026-10-13, by fetching the file at that commit |

The quotation is from MIT-licensed source. The figure is one measurement by the allocator's authors on one workload. It is not a general figure, and Buffon has not measured how large the effect is for any arm.

*Reading a number:*

- A macOS footprint compares two runtimes partly through how each one's allocator treats this call, as well as through how much memory each one uses. A difference between two macOS footprints is not by itself a difference in memory use.
- **Linux `Private_Dirty` is the like-for-like figure** for comparing harnesses by own footprint. `MADV_FREE_REUSE` is a macOS call, so this effect is absent there. Linux allocators still differ in how eagerly they return memory, and that remains part of what the column measures.
- Read RSS and peak RSS beside a macOS footprint, and do not compare a macOS number with a Linux number.
- Which allocator a runtime uses is a fact of that runtime and version. Buffon does not assume it from the runtime's name.

### Peak memory of all processes on macOS

The "peak memory, all processes" figure of a macOS run is the largest sum of resident sets over `ps` samples. A sample takes tens to hundreds of milliseconds, so a command that runs for less than that may leave no sample, or only one taken right after its exec. With no sample, the figure is missing and the report has no cell for it. With one, the figure is raised to the largest single process's `ru_maxrss`, so it can still read low for a tree of several processes that peaked together. The largest-process peak (`peak_rss_mib`) comes from `wait4` and does not have this gap. Earlier runs of Buffon printed a near-zero figure for such commands; one start-up cell read 2121 times the reference because of it.

*Reading a number:* a macOS all-processes peak for a command of under a second is a lower bound. Prefer the largest-process peak there, and do not set a macOS cell against a Linux cgroup peak.

*The report:* labels the meter of a run (cgroup or rusage). The planned memory table names the platform in its note and keeps macOS and Linux rows apart ([REPORT-TEMPLATE.md](REPORT-TEMPLATE.md)).

## 5. Some metrics favour a design

A harness that deduplicates repeated content gains on a workload that repeats content, and the long-session workloads repeat a pattern. A harness that defers work until first use looks cheap at start and pays on the first prompt. A harness that sends less context does less work per turn. None of these is a statement about quality.

*Reading a number:* ask what design the metric rewards before you read a difference as a difference in quality.
*Where it is explained:* here, and in the limits of each family in [WHAT-WE-MEASURE.md](WHAT-WE-MEASURE.md). The long-session resume workloads have a varied twin (`longsession/resume-n-varied`, `resume-n10-varied`) with distinct content, the same message structure and the same byte size, so a deduplication gain shows as the difference between the two rows. The other workloads have no twin. A per-row note in the generated report is planned.

## 6. Defaults differ and are not equalised

Arms are configured through their manifests to run the same scenario. Each keeps its own compaction defaults, tool set and system prompt. A different prompt is a different request, and a different request changes what the mock reports.

Runtime tuning is one of those defaults. Buffon pins CPUs but sets no GOMAXPROCS, GOGC, GOMEMLIMIT or NODE_OPTIONS for any arm, so a Go harness sizes itself by its own runtime (PiG documents GOMAXPROCS unset, capped at min(2, the runtime default)). Under a one-core cpuset Go's default follows the cpuset, so the difference shows only on a run with several harness CPUs.

Where a harness does different work by its own account (Pi-Bolt parses a streaming tool call's arguments less often than Pi and scrolls rows in the fullscreen TUI), the report labels the cell "different work: not compared" and the grade leaves it out for that arm.

*Reading a number:* the comparison is between harnesses as they ship, configured to run the same scenario, and not between harnesses with identical settings. A cell labelled "different work: not compared" has no ratio at all.
*The report:* prints the pins, the environment and the runtime settings of every arm, and the declared divergences with their sources.

## 7. Buffon's authors also build PiG, and PiG is one of the arms

*Reading a number:* weigh a PiG result with that in mind.
*The report:* [METHODOLOGY.md](METHODOLOGY.md) section 15 lists what limits the effect: the same code scores every arm, the raw samples ship with every run, the losses are listed first, any cell can be rerun by someone else, and an independent rerun on a second host comes before any public release.

## 8. Repetitions are few

A cell has at least 12 measured repetitions per arm, and more where the A/A floor says the cell is noisy. A cell with few repetitions has a wide interval.

With adaptive stopping a cell can take fewer than 12 rounds, and cannot be Verified. It never takes fewer than the rounds Holm across its compared arms needs for the exact sign-flip test to reach p < 0.05: 6 for one arm, 9 for eight. Few rounds also limit equivalence: the TOST needs a 90% interval inside the margin, which a handful of noisy rounds rarely gives, so a cell can show "no measurable difference" and "not equivalent" together.

*Reading a number:* look at the interval and the A/A floor, and not only at the median.
*The report:* prints the interval, the spread and the minimum detectable effect, and calls a gap inside the floor "no measurable difference".

## 9. Terminals differ

An interactive run uses a fixed PTY size and one of two terminal profiles. A harness can behave differently on a terminal that answers queries differently.

*Reading a number:* an interactive number holds for the profile named in the report.
*The report:* names the profile and reports the two profiles separately.

## 10. Platforms differ

A Linux run measures CPU and memory from a cgroup. A macOS run uses rusage and `ps`, and the report labels it as rusage. It also lacks some cells a Linux run has (RPC and long-session peak RSS) and reads some CPU values from live readings that miss exited helpers; see METHODOLOGY section 4, "Measurement caveats by platform".

On macOS the all-processes peak memory of a short command may be missing or a lower bound (section 4), and its sampler has a longer interval than the Linux one.

*Reading a number:* do not compare a Linux number with a macOS number.
*The report:* labels the meter and keeps the two apart.

## 11. Instruction counts depend on the host's counters

On Linux a strict `perf_event_paranoid` setting counts user-space instructions only, and a time-shared counter gives a scaled estimate. On macOS the count is sampled about every 165 ms (on the machine audited) and undercounts: a process that exits between two samples misses its last interval, and the shortfall depends on how long the process lives (about 44% in one test loop). Where an instruction cell exists the grade uses it instead of CPU time, so a macOS grade inherits the undercount (METHODOLOGY section 4, "Measurement caveats by platform"). A host with no counters reports CPU time only.

*Reading a number:* check which instructions were counted, and check a macOS number against a Linux host before relying on it.
*The report:* each sample records which instructions were counted (`perf_scope`).

## 12. Faithfulness is graded by probes Buffon wrote

The probes cover what [FAITHFULNESS.md](FAITHFULNESS.md) lists and nothing else. A harness can differ from Pi in a way no probe exercises.

*Reading a number:* a faithfulness score is a statement about the probes, and not about every behaviour.
*The report:* lists the probes that differ and the harness's recorded intentional divergences by name.

## 13. Not measured

Real model quality, a real network, Windows, and leaks that take hours to show. Families that have no workload yet are listed in [WHAT-WE-MEASURE.md](WHAT-WE-MEASURE.md) as not run.

*The report:* has a "Not measured" section.
