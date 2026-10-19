# SPDX-License-Identifier: Apache-2.0
"""The default observer: a telemetry record for every sample, taken before, during and after it (docs/TELEMETRY.md, docs/HOOKS.md).

For each sample, in `sample.telemetry.system`:

  before / after   gauges of the machine just before the workload starts and just after it returns: load, runnable tasks, available memory, the clock of the pinned CPUs
  during           a sampler thread reads the gauges a few times a second while the sample runs (never on a pinned CPU): min / mean / max clock, the highest load and runnable count
  cpuset           what the pinned CPUs did between begin and end, by kind: busy, iowait, steal, irq, run-queue wait, and CFS throttling of the session's cgroup
  cgroup           the sample's own cgroup read just before its meter removed it: CPU time, throttling, peak memory, pids, IO bytes, page faults, pressure (or rusage where there is
                   no cgroup)
  gate             what the quiet-host gate did before this sample: passed at once, waited (and how long), or gave up
  collector        the observer's own cost: CPU time of its thread and the number of readings, so a reader can see that it is small

Only /proc, /sys and cgroup files are read, a few times a second, by a thread that runs on the runner's CPUs. A source the machine does not have is absent from the record
and from `sources`, never a zero.
"""
import os
import threading
import time

from ..runner import cgroup, facts, hooks
from . import probes

DEFAULT_INTERVAL_S = 0.25


class State:
    """What one open sample window holds."""

    def __init__(self, before, finals, thread, stop, readings, begin_ms, listener):
        self.before, self.finals, self.thread, self.stop, self.readings, self.begin_ms, self.listener = before, finals, thread, stop, readings, begin_ms, listener


class MeterListener:
    """Called by a meter as it closes (buffon.runner.cgroup.CLOSE_LISTENERS), while its cgroup still exists: keeps the meter's final totals for the open sample."""

    def __init__(self, src, finals):
        self.src, self.finals = src, finals

    def __call__(self, meter):
        try:
            if getattr(meter, "mode", None) == "container":      # the container's cgroup is gone by now: the relay read it when the arm exited
                self.finals.append(probes.container_final(meter._load_final(), getattr(meter, "start_usage_usec", 0), getattr(meter, "relay_cpu_ms", 0.0)))
            elif hasattr(meter, "path"):
                self.finals.append(probes.cgroup_final(self.src, meter.path))
            elif getattr(meter, "rusage", None) is not None:
                self.finals.append(probes.rusage_final(meter.rusage))
        except Exception:                      # a meter that cannot be read leaves a gap in the record, never a failed sample
            pass


class SystemTelemetry(hooks.Observer):
    name = "system"

    def __init__(self, interval_s=DEFAULT_INTERVAL_S, src=None, listeners=None):
        self.interval_s = interval_s
        self.src = src or probes.Sources()
        self.listeners = cgroup.CLOSE_LISTENERS if listeners is None else listeners
        self._cpus = []

    # -- run --------------------------------------------------------------------------------------------------------------------------------

    def cpuset(self, window_cpus):
        """The CPUs whose activity is the harness's environment: the pinned CPUs, else every CPU this process may use."""
        if window_cpus:
            return sorted(window_cpus)
        return facts.allowed_cpus()

    def run_start(self, run):
        self._cpus = self.cpuset(run.cpus)
        snap = probes.snapshot(self.src, self._cpus, fallback_mhz=True)
        return {"interval_s": self.interval_s, "cpuset": self._cpus, "pinned": bool(run.cpus), "sources": snap["sources"], "gauges": probes.point(snap),
                "own_cgroup": os.path.basename(probes.own_cgroup(self.src) or "") or None,
                "quota_limited": probes.quota_limited(self.src, probes.own_cgroup(self.src)) if probes.own_cgroup(self.src) else []}

    def run_end(self, run, raw):
        snap = probes.snapshot(self.src, self._cpus or self.cpuset(run.cpus), fallback_mhz=True)
        return {"gauges": probes.point(snap)}

    # -- sample -----------------------------------------------------------------------------------------------------------------------------

    def sample_begin(self, window):
        cpus = self._cpus or self.cpuset(window.cpus)
        t_cpu0 = time.thread_time()
        before = probes.snapshot(self.src, cpus)
        finals, readings, stop = [], [], threading.Event()
        listener = MeterListener(self.src, finals)
        self.listeners.append(listener)
        thread = None
        if self.interval_s > 0:
            thread = threading.Thread(target=self._sampler, args=(cpus, stop, readings), daemon=True)
            thread.start()
        return State(before, finals, thread, stop, readings, round((time.thread_time() - t_cpu0) * 1000, 3), listener)

    def _sampler(self, cpus, stop, readings):
        """Reads the gauges every interval until stopped (light readings: the counters are read only before and after, because a full reading costs milliseconds of CPU on a many-core host). It keeps its own CPU time so the report can show what the collector cost."""
        self.pin_away(cpus)
        cost0 = time.thread_time()
        n = 0
        while not stop.wait(self.interval_s):
            snap = probes.snapshot(self.src, cpus, light=True)
            readings.append({k: snap[k] for k in ("t", "load1", "runnable", "mhz", "cpu") if k in snap})
            n += 1
        readings.append({"_cost_ms": (time.thread_time() - cost0) * 1000, "_n": n})

    @staticmethod
    def pin_away(cpus):
        """The sampler thread inherits the runner's CPUs (the mock's). If it somehow shares a pinned CPU, move it to the others."""
        try:
            mine = os.sched_getaffinity(0)
            elsewhere = mine - set(cpus)
            if elsewhere and elsewhere != mine:
                os.sched_setaffinity(0, elsewhere)    # affinity 0 is this thread on Linux
        except (AttributeError, OSError):
            pass

    def sample_end(self, window, state, record):
        if state is None:
            return None
        t0 = time.thread_time()
        state.stop.set()
        if state.thread:
            state.thread.join(self.interval_s + 1)
        if state.listener in self.listeners:
            self.listeners.remove(state.listener)
        cpus = self._cpus or self.cpuset(window.cpus)
        after = probes.snapshot(self.src, cpus)
        readings = [r for r in state.readings if "_cost_ms" not in r]
        cost = next((r for r in state.readings if "_cost_ms" in r), {"_cost_ms": 0.0, "_n": 0})
        out = {"cpuset": probes.delta(state.before, after), "before": probes.point(state.before), "after": probes.point(after), "during": self.during(readings, state.before, after, cpus),
               "sources": after["sources"], "gate": self.gate(window.host, record)}
        final = probes.merge_finals(state.finals)
        if final:
            out["cgroup"] = final
        out["collector"] = {"thread_cpu_ms": round(cost["_cost_ms"], 3), "readings": cost["_n"] + 2, "end_cpu_ms": round((time.thread_time() - t0) * 1000, 3),
                            "begin_cpu_ms": state.begin_ms}
        return out

    @staticmethod
    def during(readings, before, after, cpus):
        """min / mean / max of the gauges over the readings taken while the sample ran (the begin and end readings included)."""
        pts = [before] + readings + [after]
        out = {"readings": len(readings)}
        mhz = [v for p in pts for v in p.get("mhz", {}).values()]
        if mhz:
            out.update({"mhz_min": round(min(mhz), 1), "mhz_mean": round(sum(mhz) / len(mhz), 1), "mhz_max": round(max(mhz), 1)})
        for key in ("load1", "runnable"):
            vals = [p[key] for p in pts if key in p]
            if vals:
                out[f"{key}_max"] = max(vals)
        busy = []
        for a, b in zip(pts, pts[1:]):
            if "cpu" in a and "cpu" in b and b["t"] > a["t"]:
                d = probes.delta(dict(a, t=a["t"]), dict(b, t=b["t"]))
                if d.get("cpuset_cpus"):
                    busy.append(d["cpuset_busy_ms"] / (d["window_ms"] * d["cpuset_cpus"]))
        if busy:
            out["cpuset_busy_max"] = round(max(busy), 4)
        return out

    @staticmethod
    def gate(host, record):
        """passed (the first reading was quiet), waited (it took more than one reading) or gave-up; and how long."""
        waited = host.get("quiet_wait_ms") if host else None
        checks = host.get("quiet_checks") if host else None
        if waited is None and checks is None:
            return {"status": "disabled"}
        status = "waited" if (checks or 1) > 1 else "passed"
        return {"status": status, "waited_ms": waited, "checks": checks, "pinned_busy": host.get("pinned_busy"), "host_load1": host.get("host_load1"), "host_runnable": host.get("host_runnable")}


def default():
    return SystemTelemetry()
