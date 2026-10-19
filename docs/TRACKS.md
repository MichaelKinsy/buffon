# The three tracks

Buffon groups its benchmarks into three tracks, by the plain question each one asks. A track only chooses what `buffon up` runs. The results site shows no answer per question and no track: it shows the grid of the metrics you pick ([design/DASHBOARD.md](design/DASHBOARD.md)).

**Track 1: Common ground.** Every harness, compared fairly: Pi, the Pi-compatible builds, and harnesses unrelated to Pi (OpenCode, Codex, Claude Code, Copilot CLI). Speed (start-up, one turn, a long session). Memory (idle, and after a long session). Reliability (it recovers from faults and never loses work). A harness runs every row it can; a row it cannot run is n/a with the reason, never a zero.

A Track 1 question reads these cells of the grid: speed is wall time, memory is peak memory, reliability is the faults a harness came through by the rules every harness shares (it ended in time, printed no crash trace, never claimed success without a reply, left a session file that parses, did the same every time, and its A/A copy agreed).

**Track 2: Pi family.** Harnesses that run Pi's extensions, sessions or RPC: Pi on Node and Bun, PiG, Pi-Bolt and other Pi-compatible builds. Runs Pi's interfaces (loads Pi extensions, resumes Pi sessions, speaks Pi RPC: three yes or no facts, each proven by the workload running). It scales with parallel agents (how many agents one container holds, without and with ten extensions, found by a search to the exact number). It scales with extensions (0, 10, 50, 100 trivial ones, plus a set of real ones). It scales with session size (1 prompt, 1k turns, 4.2M tokens). Streaming and wire efficiency (render cost per kind of content).

No track scores how closely a harness behaves like Pi. The faithfulness probes ([FAITHFULNESS.md](FAITHFULNESS.md)) run only when asked: `buffon up --evals faithfulness`.

**Track 3: Real-world.** The obvious combinations of tracks 1 and 2, as a user lives them: a day of work (one agent, a long session, real extensions, a laptop), a team box (8 parallel agents with real extensions and mid-length sessions, on a server), a heavy setup (50 extensions, a 4.2M-token session, a resume), a cheap machine (track 1 speed and memory on a small server next to a laptop). A scenario is a fixed recipe of existing benchmarks. It adds no metric of its own, and says which ones it uses.

The definitions are data: `workloads/tracks.toml` (tracks 1 and 2: each question names the benchmarks that answer it) and `workloads/recipes/*.toml` (track 3). A benchmark that is designed and not built is named under `coming`; a screen shows it as a "coming" chip and never as a number. A recipe that waits for one is coming as a whole.

```sh
buffon up --track common            # every harness, the Track 1 questions
buffon up --track pi                # the Pi family: Pi's interfaces, extensions, session size, streaming
buffon up --track real-world        # the scenarios that are built
buffon up --track all
```

`buffon benches` lists each benchmark with the tracks it is in. With no selection flags on a terminal, the picker offers the tracks and groups individual benchmarks by track.

## Containers

The Pi family and real-world tracks run every harness in its own container (the container envelope, [ENVELOPE.md](ENVELOPE.md)), with the same memory and CPU limit for every harness. That is the default where the machine has docker or podman and the site pins CPUs; otherwise the harnesses run bare, `buffon up` says so, and the run is stamped uncontained. Track 1 may run either way. Containers must not distort the speed numbers: the container's own cost is recorded with an A/A pair (the reference arm bare and in a container), shown once in the method notes.

## Races

A scaling question is read as a race. Every race has a set finish line (the last rung of its ladder) and set limits (the container's memory tier, the CPUs, a deadline), stated once above it. For each harness the report shows:

- **Outcome.** Finished (the time it crossed the line) or Stopped (OOM, error or timeout, at which rung and at what elapsed time).
- **Speed.** Time to finish, or the rungs done until it stopped; the time to each checkpoint (25, 50, 75, 100%).
- **Memory.** Peak and average, and the container's peak at the moment of an OOM.
- **Reliability.** Samples that failed, and lost work (none expected).
- **Resources.** CPU time.

Finished harnesses rank first by time, then stopped ones by how far they got, ties by the time to get there. An OOM is a result, never a crashed run. The races are: extensions (0, 5, 10, 50, 100: `overhead/print` and `overhead/print-ext5|10|50|100`) and session size (1 prompt, 1k turns, 4.2M tokens: `overhead/print`, `longsession/resume-n10`, `longsession/resume-4m2`). How many agents one container holds is not a race: it is a number found by a search (`scale/agents-limit`, `scale/print-limit` and the ten-extension variants), shown on the Scale page. A race reads samples the run already recorded, so it is reproduced from `raw.json` alone. Limits come in fixed tiers (`--memory-tier 1|2|4|8`, GiB) and the tier is part of a result's name (`4GiB`; an uncontained run says `bare` and is not comparable with a container race).

## Recipe files

A recipe is a TOML file in `workloads/recipes/`:

| key | meaning |
|---|---|
| `id`, `title`, `sentence` | the name, and one plain sentence that asks the question |
| `machine` | `laptop`, `vps` or `small-vps`: the machine the scenario is about (a result is labelled by the machine that ran it) |
| `conditions` | `typical` (a laptop, Node, default extensions) or `lab` (pinned quiet cores) |
| `uses` | the registered benchmarks it combines |
| `coming` | benchmarks it needs that are not built yet: `extension-sweep`, `longsession-ladder`, `real-extensions` |
| `params` | parameters for those benchmarks (a recipe with parameters runs as its own group, so they apply to its benchmarks alone) |
| `isolation`, `apis` | what the scenario runs with |
| `[[reports]]` | the numbers it shows: `label`, `from` (a benchmark it uses or waits for) and `metric` |

`tests/test_tracks.py` checks every file: a benchmark that is not registered, a report that takes its number from a benchmark the recipe does not use, an unknown key.
