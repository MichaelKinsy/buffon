# SPDX-License-Identifier: Apache-2.0
"""The runner's observer hooks: how a collector (telemetry, noise, health) sees a run without the runner knowing about it.

Contract (docs/HOOKS.md): an Observer is told when a run starts, when a sample's window opens and closes, and when the run ends. It returns plain JSON-able
dicts; the runner stores them under `telemetry.<observer.name>` and never lets a failing observer change a measurement, only record that it failed.
"""
import importlib
import time
import traceback


class Observer:
    """Base class with no-op hooks. Subclass and override what you need; `name` keys the observer's data in raw.json."""

    name = "observer"

    def run_start(self, run):
        """`run`: RunInfo. Called once, after pinning and host facts, before the first sample. May return a dict stored in raw["run"]["telemetry"][name]["start"]."""

    def sample_begin(self, window):
        """`window`: Window. Called after the quiet gate passed and before the workload starts any harness process. Return an opaque state handed to sample_end.
        A collector that samples during the window starts its own thread here, on a CPU outside `window.cpus`, and stops it in sample_end."""

    def sample_end(self, window, state, record):
        """Called after the workload returned (also when it failed). `record` is the sample record (read-only by contract). Return a dict stored in
        record["telemetry"][name]; None stores nothing."""

    def run_end(self, run, raw):
        """Called once at the end (also for a refused or failed run). `raw` is the raw.json dict about to be written. Return a dict stored in raw["run"]["telemetry"][name]["end"]."""


class RunInfo:
    """What an observer may know about the run: plain data, no runner objects."""

    def __init__(self, plan, facts, backend="local"):
        self.backend = backend                          # "local" | "kubernetes"
        self.cpus = list(plan.cpus or [])               # the CPUs harness processes are pinned to
        self.mock_cpus = list(plan.mock_cpus or [])
        self.rounds, self.warmup = plan.rounds, plan.warmup
        self.out = plan.out
        self.facts = facts                              # the host facts dict that goes into raw.json


class Window:
    """One sample's window."""

    def __init__(self, info, arm, scenario, api, rnd, warmup, host):
        self.run = info
        self.arm, self.scenario, self.api, self.round, self.warmup = arm, scenario, api, rnd, warmup
        self.cpus, self.mock_cpus = info.cpus, info.mock_cpus
        self.host = host                                # the quiet gate's reading for this sample (host_load1, host_runnable, pinned_busy, quiet_wait_ms)
        self.t_begin = time.monotonic()
        self.t_begin_utc = time.time()


class Observers:
    """Fans each event out to every observer; an observer's exception is recorded, never raised."""

    def __init__(self, observers=()):
        self.observers = list(observers)
        self.errors = []

    def __bool__(self):
        return bool(self.observers)

    def _call(self, observer, hook, *args):
        try:
            return getattr(observer, hook)(*args)
        except Exception as error:
            self.errors.append({"observer": observer.name, "hook": hook, "error": repr(error), "traceback": "".join(traceback.format_exception(error))[-600:]})
            return None

    def run_start(self, run):
        return {o.name: out for o in self.observers if (out := self._call(o, "run_start", run)) is not None}

    def sample_begin(self, window):
        return {o.name: self._call(o, "sample_begin", window) for o in self.observers}

    def sample_end(self, window, states, record):
        out = {}
        for o in self.observers:
            data = self._call(o, "sample_end", window, (states or {}).get(o.name), record)
            if data is not None:
                out[o.name] = data
        return out

    def run_end(self, run, raw):
        return {o.name: out for o in self.observers if (out := self._call(o, "run_end", run, raw)) is not None}


def load(spec):
    """`package.module:factory` -> an Observer instance (the factory is called with no arguments)."""
    module, _, factory = spec.partition(":")
    if not module or not factory:
        raise ValueError(f"observer spec must be 'package.module:factory', got {spec!r}")
    observer = getattr(importlib.import_module(module), factory)()
    if not isinstance(observer, Observer):
        raise TypeError(f"{spec} did not return a buffon.runner.hooks.Observer")
    return observer
