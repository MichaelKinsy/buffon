# Agent benchmarks: task pass rates with real models

The overhead, streaming, long-session and reliability families run against a local mock and never leave the machine. An agent benchmark is the other kind: real tasks, a real model, a verifier, and the question "does arm B solve as many tasks as arm A?". It needs credentials and network, so it is never part of `buffon run`; it has its own protocol, its own run directory and its own report, and it does not share timing claims with the mock families.

## Method (copied from Pi's `packages/evals`, written independently)

- **Paired arms.** Every task runs once per arm and model and repetition; the arm order alternates by task and repetition so an order effect cancels (`expected_runs`).
- **Identical cohorts.** The protocol declares arms, tasks, models, repetitions, seed and parameters (thinking level, turn cap, timeouts) once. `protocol.json` carries its sha256; two result sets are comparable only when the digests match.
- **A blocked pair withholds the headline.** A pair with a missing, duplicate or errored arm (a container that died is not a failed task) blocks; with any blocked pair the report prints no pass rate and lists the blocked pairs.
- **Unavailable is not zero.** Telemetry a harness could not read (tokens, cost, wall time) is null and counted as unavailable.
- **The result** is the paired difference in pass rate with Wilson intervals and the exact McNemar test on the discordant pairs. `sem_overlap` implements Harbor's criterion for repeated measurements (mean ± SEM intervals overlap) for callers that repeat whole runs.

## Commands

```
python3 -m buffon agentbench plan protocol.json --out runs/ab        # protocol.json + expected-runs.json
python3 -m buffon agentbench result protocol.json --observations observations.jsonl --out runs/ab
```

An observation is one JSON line: `{"case", "arm", "model", "run", "passed": true|false|null, "error": null|"...", "tokens", "cost_usd", "wall_s"}`.

## Producing observations with Harbor

[Harbor](https://github.com/harbor-framework/harbor) runs agents on benchmark adapters (Terminal-Bench, SWE-bench) and has a built-in `pi` agent (`harbor run -a pi`, installing the published Pi package). That makes stock Pi runnable on any Harbor benchmark. A Pi-compatible arm needs a custom Harbor agent or adapter that installs and starts that arm's binary. Harbor is Apache-2.0; Buffon does not vendor or copy it, and a Harbor result is converted to `observations.jsonl` by a few lines of the operator's own script. Nothing in this repository runs Harbor. The Harbor invocation, its container runtime and the model credentials are the operator's; record the Harbor version and the model identifiers in `params` so the protocol digest covers them.

The opt-in field track ([FIELD.md](FIELD.md)) is a fixed small protocol on this engine, with the user's own key and a budget cap. It is planned and is never part of the default leaderboard or the Harness Score.

## What this does not claim

Pass rates on a few dozen tasks have wide intervals; the Wilson interval and the McNemar p are printed so that a small difference reads as the noise it usually is.
