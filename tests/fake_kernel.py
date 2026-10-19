# SPDX-License-Identifier: Apache-2.0
"""A fake /proc, /sys and cgroup tree for the telemetry tests: files written under a temporary directory, rewritable between two readings."""
import os
import tempfile

from buffon.telemetry import probes


class FakeKernel:
    def __init__(self):
        self.root = tempfile.mkdtemp()
        self.proc, self.sys, self.cg = (os.path.join(self.root, d) for d in ("proc", "sys", "cgroup"))
        for d in (self.proc, self.sys, self.cg):
            os.makedirs(d)
        self.src = probes.Sources(self.proc, self.sys, self.cg)
        self.write(self.proc, "self/cgroup", "0::/lane/session\n")
        os.makedirs(os.path.join(self.cg, "lane", "session"))

    def write(self, base, rel, text):
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)

    def stat(self, cpus):
        """cpus: {n: (user, nice, system, idle, iowait, irq, softirq, steal)} in ticks."""
        lines = ["cpu  " + " ".join("0" for _ in range(8))] + [f"cpu{c} " + " ".join(map(str, v)) for c, v in cpus.items()]
        self.write(self.proc, "stat", "\n".join(lines) + "\n")

    def schedstat(self, run_delay_ms):
        lines = ["version 15", "timestamp 1"] + [f"cpu{c} 0 0 0 0 0 0 7 {int(v * 1e6)} 5" for c, v in run_delay_ms.items()]
        self.write(self.proc, "schedstat", "\n".join(lines) + "\n")

    def freq(self, cpu, khz):
        self.write(self.sys, f"devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq", f"{khz}\n")

    def load(self, load1=0.5, runnable=2):
        self.write(self.proc, "loadavg", f"{load1} 0.4 0.3 {runnable}/300 12345\n")

    def cgroup(self, rel, **files):
        for name, text in files.items():
            self.write(self.cg, os.path.join(rel, name.replace("_", ".", 1) if name.count("_") and "." not in name else name), text)
        return os.path.join(self.cg, rel)
