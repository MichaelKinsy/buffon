# SPDX-License-Identifier: Apache-2.0
"""How busy the machine was: per-CPU busy fraction from /proc/stat.

`idle_check` measures the pinned CPUs (and their SMT siblings) while the runner is not running anything, so any load it sees belongs to someone else.
`Monitor` samples the pinned CPUs and the whole host every second while a run is going and keeps a summary for the report.
"""
import threading
import time


def read_stat(path="/proc/stat"):
    """{cpu number: (busy ticks, total ticks)} plus key None for the whole host."""
    out = {}
    with open(path) as f:
        for line in f:
            if not line.startswith("cpu"):
                continue
            name, *vals = line.split()
            vals = [int(v) for v in vals]
            idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
            total = sum(vals[:8])
            out[None if name == "cpu" else int(name[3:])] = (total - idle, total)
    return out


def read_detail(path="/proc/stat"):
    """{cpu number: (total ticks, iowait ticks, steal ticks)} for the per-CPU lines."""
    out = {}
    with open(path) as f:
        for line in f:
            if line.startswith("cpu") and line[3:4].isdigit():
                name, *vals = line.split()
                vals = [int(v) for v in vals] + [0] * 8
                out[int(name[3:])] = (sum(vals[:8]), vals[4], vals[7])
    return out


def share(before, after, cpus, index):
    """Largest per-CPU share of `index` (1 iowait, 2 steal) of the ticks between two read_detail() results."""
    worst = 0.0
    for cpu in cpus:
        if cpu in before and cpu in after:
            dt = after[cpu][0] - before[cpu][0]
            if dt > 0:
                worst = max(worst, (after[cpu][index] - before[cpu][index]) / dt)
    return worst


def busy_fractions(before, after, cpus=None):
    """{cpu: busy fraction} between two read_stat() results; cpus None means every CPU."""
    out = {}
    for cpu in (cpus if cpus is not None else [c for c in after if c is not None]):
        if cpu in before and cpu in after:
            dt = after[cpu][1] - before[cpu][1]
            out[cpu] = (after[cpu][0] - before[cpu][0]) / dt if dt else 0.0
    return out


def idle_check(cpus, seconds=3.0, read=read_stat, sleep=time.sleep):
    """Busy fraction of each CPU in `cpus` over `seconds` with nothing of ours running."""
    before = read()
    sleep(seconds)
    return busy_fractions(before, read(), list(cpus))


class Monitor:
    """Samples the pinned CPUs and the host every `interval` seconds on a thread."""

    def __init__(self, cpus, interval=1.0, read=read_stat):
        self.cpus, self.interval, self.read = list(cpus), interval, read
        self.samples = []  # (t_s, pinned mean busy, host busy)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self.t0 = time.monotonic()
        self._prev = self.read()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def _loop(self):
        while not self._stop.wait(self.interval):
            now = self.read()
            pinned = busy_fractions(self._prev, now, self.cpus) if self.cpus else {}
            host = busy_fractions(self._prev, now, [None]).get(None)
            self.samples.append((round(time.monotonic() - self.t0, 1), sum(pinned.values()) / len(pinned) if pinned else None, host))
            self._prev = now

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(self.interval + 1)
        return self.summary()

    def summary(self):
        pinned = [s[1] for s in self.samples if s[1] is not None]
        host = [s[2] for s in self.samples if s[2] is not None]
        return {"samples": len(self.samples), "pinned_busy_mean": sum(pinned) / len(pinned) if pinned else None, "pinned_busy_max": max(pinned) if pinned else None,
                "host_busy_mean": sum(host) / len(host) if host else None}
