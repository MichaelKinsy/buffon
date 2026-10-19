# SPDX-License-Identifier: Apache-2.0
"""The default observer: what lands in sample.telemetry.system, that it closes its window on every path, and that the meters hand it their totals."""
import os
import subprocess
import sys
import threading
import time
import types
import unittest

from buffon.runner import cgroup, hooks
from buffon.telemetry import collector, probes
from buffon.workloads.overhead import Skip
from tests.fake_kernel import FakeKernel
from tests.test_hooks import with_gate
from tests.test_quiet import FakeCtx, runner


def kernel():
    k = FakeKernel()
    k.stat({0: (0, 0, 0, 100, 0, 0, 0, 0), 1: (0, 0, 0, 100, 0, 0, 0, 0)})
    k.schedstat({0: 1, 1: 1})
    k.freq(0, 2000000)
    k.freq(1, 2000000)
    k.load(1.0, 2)
    return k


class Collected(unittest.TestCase):
    def run_sample(self, fn, host=None, interval=0):
        k = kernel()
        listeners = []
        obs = collector.SystemTelemetry(interval_s=interval, src=k.src, listeners=listeners)
        r, w = runner(observers=[obs])
        r = with_gate(r)
        r.run_info = hooks.RunInfo(r.plan, {})
        r.run_info.cpus = [0, 1]
        r.plan.cpus = [0, 1]
        r.gate = types.SimpleNamespace(window_s=0.25, wait=lambda: (dict(host or {"host_load1": 1.0, "host_runnable": 2, "pinned_busy": 0.0, "quiet_checks": 1}), 12, True))

        def work(ctx, a):
            k.stat({0: (30, 0, 10, 100, 0, 0, 0, 2), 1: (0, 0, 0, 140, 0, 0, 0, 0)})
            k.freq(0, 1900000)
            return fn(k, listeners)
        w.fn = work
        obs.run_start(r.run_info)
        r.measure(FakeCtx(), [r.plan.arms[0]])
        return r.samples[0], listeners

    def test_the_record_holds_before_after_cpuset_gate_and_the_collectors_own_cost(self):
        s, listeners = self.run_sample(lambda k, l: {"cpu_ms": 5.0})
        t = s["telemetry"]["system"]
        self.assertEqual(t["before"]["mhz_mean"], 2000.0)
        self.assertEqual(t["after"]["mhz_min"], 1900.0)
        self.assertGreater(t["cpuset"]["cpuset_busy_ms"], 0)
        self.assertGreater(t["cpuset"]["cpuset_steal_ms"], 0)
        self.assertEqual(t["gate"], {"status": "passed", "waited_ms": 12, "checks": 1, "pinned_busy": 0.0, "host_load1": 1.0, "host_runnable": 2})
        self.assertIn("proc_stat", t["sources"])
        self.assertEqual(set(t["collector"]), {"thread_cpu_ms", "readings", "end_cpu_ms", "begin_cpu_ms"})
        self.assertEqual(listeners, [], "the meter listener is removed when the window closes")
        self.assertEqual(s["cpu_ms"], 5.0, "telemetry never changes the measurement")

    def test_a_gate_that_waited_says_so_and_for_how_long(self):
        s, _ = self.run_sample(lambda k, l: {"cpu_ms": 1.0}, host={"host_load1": 3.0, "host_runnable": 4, "pinned_busy": 0.02, "quiet_checks": 5})
        self.assertEqual(s["telemetry"]["system"]["gate"]["status"], "waited")
        self.assertEqual(s["telemetry"]["system"]["gate"]["checks"], 5)

    def test_a_meter_closing_inside_the_window_hands_over_its_cgroup_totals(self):
        k = kernel()

        def meter_closes(kern, listeners):
            path = os.path.join(kern.cg, "lane", "buffon-x")
            kern.write(path, "cpu.stat", "usage_usec 7000\nuser_usec 6000\nsystem_usec 1000\nnr_periods 2\nnr_throttled 1\nthrottled_usec 900\n")
            kern.write(path, "memory.peak", str(3 * 1048576))
            for l in list(listeners):
                l(types.SimpleNamespace(path=path))
            return {"cpu_ms": 7.0}

        # the same Sources must serve the listener and the probes
        listeners = []
        obs = collector.SystemTelemetry(interval_s=0, src=k.src, listeners=listeners)
        r, w = runner(observers=[obs])
        r = with_gate(r)
        r.plan.cpus = [0, 1]
        r.run_info.cpus = [0, 1]
        r.gate = None
        w.fn = lambda ctx, a: meter_closes(k, listeners)
        r.measure(FakeCtx(), [r.plan.arms[0]])
        cg = r.samples[0]["telemetry"]["system"]["cgroup"]
        self.assertEqual((cg["cpu_usage_ms"], cg["throttled_us"], cg["memory_peak_mib"], cg["meters"]), (7.0, 900, 3.0, 1))
        self.assertEqual(r.samples[0]["telemetry"]["system"]["gate"], {"status": "disabled"})

    def test_a_skipped_sample_still_removes_its_listener_and_stops_its_thread(self):
        k = kernel()
        listeners = []
        obs = collector.SystemTelemetry(interval_s=0.01, src=k.src, listeners=listeners)
        r, w = runner(observers=[obs])
        r = with_gate(r)

        def skip(ctx, a):
            raise Skip("no such mode")
        w.fn = skip
        before = threading.active_count()
        r.measure(FakeCtx(), [r.plan.arms[0]])
        self.assertEqual(listeners, [])
        self.assertEqual(threading.active_count(), before)

    def test_the_sampler_thread_reads_while_the_sample_runs_and_reports_min_mean_max(self):
        k = kernel()
        obs = collector.SystemTelemetry(interval_s=0.005, src=k.src, listeners=[])
        window = types.SimpleNamespace(cpus=[0, 1], host={})
        state = obs.sample_begin(window)
        deadline = time.monotonic() + 5
        while len(state.readings) < 3 and time.monotonic() < deadline:
            threading.Event().wait(0.005)
        k.freq(1, 3000000)
        k.load(9.0, 7)
        while not any(r.get("load1") == 9.0 for r in state.readings) and time.monotonic() < deadline:
            threading.Event().wait(0.005)
        out = obs.sample_end(window, state, {})
        self.assertGreaterEqual(out["during"]["readings"], 3)
        self.assertEqual((out["during"]["mhz_min"], out["during"]["mhz_max"]), (2000.0, 3000.0))
        self.assertEqual((out["during"]["load1_max"], out["during"]["runnable_max"]), (9.0, 7))
        self.assertGreater(out["collector"]["readings"], 3)

    def test_the_in_sample_readings_are_light_and_never_touch_the_expensive_files(self):
        k = kernel()
        k.schedstat({0: 5})
        reads = []
        real = probes.Sources.p

        def spy(self, rel):
            reads.append(rel)
            return real(self, rel)
        probes.Sources.p = spy
        try:
            light = probes.snapshot(k.src, [0, 1], light=True)
            light_reads, reads[:] = list(reads), []
            full = probes.snapshot(k.src, [0, 1])
        finally:
            probes.Sources.p = real
        self.assertEqual(set(light) - {"cpu", "mhz", "load1", "runnable"}, {"t", "cpus", "sources"})
        self.assertNotIn("runq_ns", light)
        self.assertNotIn("schedstat", light_reads)
        self.assertFalse({"meminfo", "vmstat", "pressure/cpu"} & set(light_reads))
        self.assertIn("runq_ns", full)
        self.assertIn("schedstat", reads)

    def test_the_sampler_thread_reads_light_so_the_counters_are_read_only_at_the_two_ends(self):
        k = kernel()
        reads = []
        real = probes.Sources.p

        def spy(self, rel):
            reads.append(rel)
            return real(self, rel)
        probes.Sources.p = spy
        try:
            obs = collector.SystemTelemetry(interval_s=0.005, src=k.src, listeners=[])
            window = types.SimpleNamespace(cpus=[0, 1], host={})
            state = obs.sample_begin(window)
            deadline = time.monotonic() + 5
            while len(state.readings) < 4 and time.monotonic() < deadline:
                threading.Event().wait(0.005)
            out = obs.sample_end(window, state, {})
        finally:
            probes.Sources.p = real
        self.assertGreaterEqual(out["during"]["readings"], 4)
        self.assertEqual(reads.count("schedstat"), 2, "once at begin, once at end")
        self.assertGreater(reads.count("loadavg"), 4)

    def test_the_begin_cost_is_the_cost_of_the_begin_call_not_the_time_the_sample_ran(self):
        k = kernel()
        obs = collector.SystemTelemetry(interval_s=0, src=k.src, listeners=[])
        window = types.SimpleNamespace(cpus=[0, 1], host={})
        state = obs.sample_begin(window)
        burn = time.thread_time()
        while time.thread_time() - burn < 0.05:
            pass
        out = obs.sample_end(window, state, {})
        self.assertLess(out["collector"]["begin_cpu_ms"], 25, "50 ms of the sample's own work must not be charged to the collector")

    def test_begin_and_end_costs_are_each_their_own_call(self):
        """Review: a begin_cpu_ms that reported the end call's cost survived the test above. Begin burns 30 ms of CPU, end 5 ms: each must be charged to its own call."""
        k = kernel()
        obs = collector.SystemTelemetry(interval_s=0, src=k.src, listeners=[])
        window = types.SimpleNamespace(cpus=[0, 1], host={})
        real, burn = probes.snapshot, {"ms": 30}

        def costly(*a, **kw):
            t = time.thread_time()
            while time.thread_time() - t < burn["ms"] / 1000:
                pass
            return real(*a, **kw)
        probes.snapshot = costly
        try:
            state = obs.sample_begin(window)
            burn["ms"] = 5
            out = obs.sample_end(window, state, {})["collector"]
        finally:
            probes.snapshot = real
        self.assertGreaterEqual(out["begin_cpu_ms"], 30)
        self.assertLess(out["end_cpu_ms"], 25)

    def test_a_probe_that_fails_never_fails_the_sample(self):
        k = kernel()
        obs = collector.SystemTelemetry(interval_s=0, src=probes.Sources(proc=os.path.join(k.root, "missing"), sys=os.path.join(k.root, "missing"), cgroup=k.cg), listeners=[])
        r, w = runner(observers=[obs])
        r = with_gate(r)
        r.measure(FakeCtx(), [r.plan.arms[0]])
        self.assertEqual(r.samples[0]["cpu_ms"], 1.0)
        self.assertNotIn("failure", r.samples[0])
        self.assertEqual(r.samples[0]["telemetry"]["system"]["sources"], [])


class MeterHook(unittest.TestCase):
    def tearDown(self):
        cgroup.CLOSE_LISTENERS.clear()

    def test_a_rusage_meter_notifies_once_with_the_trees_usage(self):
        seen = []
        cgroup.CLOSE_LISTENERS.append(seen.append)
        m = cgroup.RusageMeter()
        p = m.popen([sys.executable, "-c", "sum(range(10**6))"], stdout=subprocess.DEVNULL)
        m.wait(30)
        m.close()
        m.close()
        self.assertEqual(len(seen), 1)
        final = probes.rusage_final(m.rusage)
        self.assertEqual(final["mode"], "rusage")
        self.assertGreater(final["cpu_usage_ms"], 0)

    def test_a_cgroup_meter_notifies_before_it_removes_its_cgroup(self):
        k = FakeKernel()
        path = os.path.join(k.cg, "buffon-1")
        k.write(path, "cpu.stat", "usage_usec 1000\n")
        k.write(path, "memory.peak", "0")
        seen = []
        cgroup.CLOSE_LISTENERS.append(lambda meter: seen.append(os.path.exists(os.path.join(meter.path, "cpu.stat"))))
        m = cgroup.CgroupMeter(path, holder=types.SimpleNamespace(terminate=lambda: None, wait=lambda t: None, kill=lambda: None))
        m.close()
        self.assertEqual(seen, [True])


if __name__ == "__main__":
    unittest.main()
