# SPDX-License-Identifier: Apache-2.0
"""The kernel-file readers: parsing, deltas, and what is reported when a source does not exist."""
import os
import unittest

from buffon.telemetry import probes
from tests.fake_kernel import FakeKernel


class Parsers(unittest.TestCase):
    def test_proc_stat_gives_every_cpu_and_the_aggregate(self):
        out = probes.parse_proc_stat("cpu  1 2 3 4 5 6 7 8 9 10\ncpu0 10 0 20 300 4 5 6 7 0 0\ncpu3 1 1 1 1 1 1 1 1\nintr 5\n")
        self.assertEqual(out[0], {"user": 10, "nice": 0, "system": 20, "idle": 300, "iowait": 4, "irq": 5, "softirq": 6, "steal": 7})
        self.assertEqual(sorted(k for k in out if k is not None), [0, 3])
        self.assertEqual(out[None]["steal"], 8)

    def test_a_short_stat_line_is_padded_not_dropped(self):
        self.assertEqual(probes.parse_proc_stat("cpu1 1 2 3 4\n")[1]["steal"], 0)

    def test_schedstat_is_unavailable_when_every_run_delay_is_zero(self):
        self.assertIsNone(probes.parse_schedstat("cpu0 0 0 0 0 0 0 0 0 0\ncpu1 0 0 0 0 0 0 0 0 0\n"))
        self.assertEqual(probes.parse_schedstat("cpu0 0 0 0 0 0 0 5 77 0\n"), {0: 77})

    def test_kv_and_pressure_and_io(self):
        self.assertEqual(probes.parse_kv("usage_usec 5\nnr_throttled 2\nname x\n"), {"usage_usec": 5, "nr_throttled": 2})
        self.assertEqual(probes.parse_pressure("some avg10=1.50 avg60=0 avg300=0 total=1234\nfull avg10=0.00 avg60=0 avg300=0 total=7\n"),
                         {"some": {"avg10": 1.5, "total_us": 1234}, "full": {"avg10": 0.0, "total_us": 7}})
        self.assertIsNone(probes.parse_pressure(None))
        self.assertEqual(probes.parse_io_stat("8:0 rbytes=100 wbytes=50 rios=1\n8:16 rbytes=1 wbytes=2\n"), (101, 52))
        self.assertEqual(probes.parse_loadavg("0.52 0.40 0.30 3/250 999\n"), (0.52, 3))
        self.assertIsNone(probes.parse_loadavg("junk"))
        self.assertEqual(probes.parse_meminfo("MemTotal: 2048 kB\nMemAvailable: 1024 kB\nOther: 1 kB\n"), {"MemTotal": 2.0, "MemAvailable": 1.0})


class Snapshots(unittest.TestCase):
    def kernel(self):
        k = FakeKernel()
        k.stat({0: (10, 0, 5, 100, 0, 0, 0, 0), 1: (10, 0, 5, 100, 0, 0, 0, 0), 7: (99, 0, 0, 0, 0, 0, 0, 0)})
        k.schedstat({0: 10, 1: 20, 7: 30})
        k.freq(0, 2400000)
        k.freq(1, 2300000)
        k.load(0.5, 2)
        k.write(k.proc, "meminfo", "MemTotal: 4096 kB\nMemAvailable: 2048 kB\n")
        k.write(k.proc, "vmstat", "pswpin 3\npswpout 4\n")
        k.write(k.proc, "pressure/cpu", "some avg10=0.00 avg60=0.00 avg300=0.00 total=1000\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n")
        k.write(k.cg, "lane/cpu.stat", "usage_usec 0\nnr_periods 100\nnr_throttled 1\nthrottled_usec 500\n")
        k.write(k.cg, "lane/session/cpu.stat", "usage_usec 0\nnr_periods 100\nnr_throttled 2\nthrottled_usec 700\n")
        return k

    def test_a_snapshot_reads_only_the_pinned_cpus_and_lists_its_sources(self):
        k = self.kernel()
        s = probes.snapshot(k.src, [0, 1])
        self.assertEqual(sorted(s["cpu"]), [0, 1])
        self.assertEqual(s["mhz"], {0: 2400.0, 1: 2300.0})
        self.assertEqual(s["load1"], 0.5)
        self.assertEqual(s["session_throttle"], (3, 1200))     # the cgroup and its ancestor both count
        for name in ("proc_stat", "schedstat", "cpufreq", "loadavg", "meminfo", "vmstat", "pressure", "cgroup_throttle"):
            self.assertIn(name, s["sources"])

    def test_the_delta_is_what_the_cpu_set_did_between_two_snapshots(self):
        k = self.kernel()
        a = probes.snapshot(k.src, [0, 1])
        k.stat({0: (40, 0, 15, 130, 2, 1, 1, 3), 1: (30, 0, 5, 160, 0, 0, 0, 0), 7: (99, 0, 0, 0, 0, 0, 0, 0)})
        k.schedstat({0: 10 + 2, 1: 20 + 1, 7: 30})
        k.write(k.cg, "lane/session/cpu.stat", "usage_usec 0\nnr_periods 130\nnr_throttled 5\nthrottled_usec 9700\n")
        k.write(k.proc, "pressure/cpu", "some avg10=0.00 avg60=0.00 avg300=0.00 total=4500\n")
        k.write(k.proc, "vmstat", "pswpin 3\npswpout 10\n")
        b = probes.snapshot(k.src, [0, 1])
        b["t"] = a["t"] + 2.0
        d = probes.delta(a, b)
        hz = probes.USER_HZ
        scale = 1000.0 / hz
        self.assertEqual(d["window_ms"], 2000.0)
        self.assertEqual(d["cpuset_cpus"], 2)
        self.assertAlmostEqual(d["cpuset_steal_ms"], 3 * scale, places=1)
        self.assertAlmostEqual(d["cpuset_iowait_ms"], 2 * scale, places=1)
        self.assertAlmostEqual(d["cpuset_user_ms"], 50 * scale, places=1)
        self.assertAlmostEqual(d["cpuset_busy_ms"], (30 + 10 + 0 + 1 + 1 + 3 + 20 + 0) * scale, places=1)   # user+system+irq+softirq+steal, idle and iowait excluded
        self.assertEqual(d["cpuset_runq_wait_ms"], 3.0)
        self.assertEqual((d["session_throttled_periods"], d["session_throttled_us"]), (3, 9000))
        self.assertEqual(d["psi_cpu_some_us"], 3500)
        self.assertEqual(d["swap_pages"], 6)

    def test_a_missing_source_is_absent_never_zero(self):
        k = FakeKernel()
        k.stat({0: (1, 0, 1, 1, 0, 0, 0, 0)})
        s = probes.snapshot(k.src, [0])
        self.assertEqual(s["sources"], ["proc_stat"])
        d = probes.delta(s, dict(s, t=s["t"] + 1))
        for key in ("cpuset_runq_wait_ms", "session_throttled_us", "psi_cpu_some_us", "swap_pages", "thermal_throttle_events"):
            self.assertNotIn(key, d)
        self.assertEqual(probes.point(s), {})

    def test_cpuinfo_is_the_clock_fallback_only_when_asked(self):
        k = FakeKernel()
        k.stat({0: (1, 0, 1, 1, 0, 0, 0, 0)})
        k.write(k.proc, "cpuinfo", "processor\t: 0\ncpu MHz\t\t: 3000.5\n\nprocessor\t: 1\ncpu MHz\t\t: 3100.0\n")
        self.assertNotIn("mhz", probes.snapshot(k.src, [0]))
        s = probes.snapshot(k.src, [0], fallback_mhz=True)
        self.assertEqual(s["mhz"], {0: 3000.5})
        self.assertIn("cpuinfo_mhz", s["sources"])

    def test_thermal_events_are_counted_per_cpu(self):
        k = FakeKernel()
        k.stat({0: (1, 0, 1, 1, 0, 0, 0, 0), 1: (1, 0, 1, 1, 0, 0, 0, 0)})
        for c, n in ((0, 1), (1, 4)):
            k.write(k.sys, f"devices/system/cpu/cpu{c}/thermal_throttle/core_throttle_count", f"{n}\n")
        a = probes.snapshot(k.src, [0, 1])
        k.write(k.sys, "devices/system/cpu/cpu1/thermal_throttle/core_throttle_count", "9\n")
        self.assertEqual(probes.delta(a, dict(probes.snapshot(k.src, [0, 1]), t=a["t"] + 1))["thermal_throttle_events"], 5)


class CgroupFinal(unittest.TestCase):
    def test_the_totals_of_one_meter_cgroup(self):
        k = FakeKernel()
        path = os.path.join(k.cg, "lane", "buffon-1")
        k.write(path, "cpu.stat", "usage_usec 12000\nuser_usec 9000\nsystem_usec 3000\nnr_periods 4\nnr_throttled 1\nthrottled_usec 250\n")
        k.write(path, "memory.peak", str(5 * 1048576))
        k.write(path, "pids.peak", "7")
        k.write(path, "memory.stat", "anon 1\npgfault 100\npgmajfault 3\n")
        k.write(path, "memory.events", "low 0\nhigh 2\nmax 0\noom 0\noom_kill 0\n")
        k.write(path, "io.stat", "8:0 rbytes=4096 wbytes=8192\n")
        k.write(path, "cpu.pressure", "some avg10=0.00 avg60=0.00 avg300=0.00 total=88\n")
        k.write(k.cg, "lane/cpu.stat", "nr_throttled 6\nthrottled_usec 600\n")
        f = probes.cgroup_final(k.src, path)
        self.assertEqual((f["cpu_usage_ms"], f["cpu_user_ms"], f["cpu_system_ms"]), (12.0, 9.0, 3.0))
        self.assertEqual((f["throttled_periods"], f["throttled_us"]), (1, 250))
        self.assertEqual((f["memory_peak_mib"], f["pids_peak"]), (5.0, 7))
        self.assertEqual((f["page_faults_minor"], f["page_faults_major"]), (97, 3))
        self.assertEqual(f["memory_events"]["high"], 2)
        self.assertEqual((f["io_read_bytes"], f["io_write_bytes"]), (4096, 8192))
        self.assertEqual(f["psi_cpu_some_us"], 88)
        self.assertEqual(f["ancestors"]["nr_throttled"], 6)

    def test_several_meters_in_one_sample_add_counters_and_keep_the_largest_peak(self):
        a = {"mode": "cgroup", "cpu_usage_ms": 10.0, "memory_peak_mib": 50.0, "pids_peak": 3, "throttled_us": 5, "memory_events": {"high": 1}}
        b = {"mode": "cgroup", "cpu_usage_ms": 5.5, "memory_peak_mib": 80.0, "pids_peak": 2, "throttled_us": 0, "memory_events": {"high": 2, "oom": 1}}
        m = probes.merge_finals([a, b])
        self.assertEqual((m["meters"], m["cpu_usage_ms"], m["memory_peak_mib"], m["pids_peak"], m["throttled_us"]), (2, 15.5, 80.0, 3, 5))
        self.assertEqual(m["memory_events"], {"high": 3, "oom": 1})
        self.assertIsNone(probes.merge_finals([]))
        self.assertEqual(probes.merge_finals([a])["meters"], 1)

    def test_chain_stops_at_the_cgroup_root(self):
        k = FakeKernel()
        self.assertEqual([os.path.relpath(d, k.cg) for d in probes.chain(k.src, os.path.join(k.cg, "a", "b"))], ["a/b", "a", "."])
        self.assertEqual(probes.chain(k.src, "/elsewhere"), [])
