# Runner observer hooks

An observer collects data about a run (telemetry, noise, health) without the runner knowing what it collects. The contract is `buffon/runner/hooks.py`; `tests/test_hooks.py` proves it.

## Registering

`buffon run|session ... --observer package.module:factory` (repeatable). The factory takes no arguments and returns an `buffon.runner.hooks.Observer`. In code, `Plan(observers=[...])`. On the Kubernetes backend the pod's `buffon session` needs the same `--observer` flags: the backend must forward them and the observer's module must be in the bundle.

## Events

| hook | when | may return |
|---|---|---|
| `run_start(run)` | once, after host facts and pinning, before the first sample | dict → `raw.run.telemetry.<name>.start` |
| `sample_begin(window)` | after the quiet gate passed (or waited), before the workload starts any harness process | opaque state for `sample_end` |
| `sample_end(window, state, record)` | after the workload returned, also when it skipped or failed, with the finished record (host readings included) | dict → `sample.telemetry.<name>` |
| `run_end(run, raw)` | once, also for a refused run, before raw.json is written | dict → `raw.run.telemetry.<name>.end` |

`run` (RunInfo) holds `backend` ("local" or "kubernetes"), `cpus` (where harness processes are pinned), `mock_cpus`, `rounds`, `warmup`, `out`, `facts`. `window` holds `run`, `arm`, `scenario`, `api`, `round`, `warmup`, `cpus`, `mock_cpus`, `host` (the quiet gate's reading: `host_load1`, `host_runnable`, `pinned_busy`, `quiet_wait_ms`) and begin timestamps.

## Rules

- Returned data is nested JSON with finite numbers. The raw-data validator accepts it only under `telemetry`; the report does not compare it as a metric.
- A hook that raises never changes the sample. The error goes to `raw.run.telemetry_errors` and the other observers still run.
- A skipped sample still gets `sample_end` (with `{"skipped": reason}` as the record), so a collector that started a thread in `sample_begin` always stops it.
- Collectors run inside the timed window. Sample from `/proc` and cgroup files only, at most a few times a second, on a CPU that is not in `window.cpus` (the runner process already runs on the mock's CPUs), and measure your own cost: an observer that moves the A/A floor is a defect.
- The quiet gate runs before `sample_begin`. A sample the gate refused to start has no window; its record carries the gate's readings and `failure`.
- Observers see plain data, never the runner, the harness or the mock.
