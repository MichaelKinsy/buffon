# SPDX-License-Identifier: Apache-2.0
"""schedstat accounting per sample (buffon/runner/cgroup.py SchedAccount, engine.one_sample): per-thread run time, run-queue wait and timeslices of the
measured tree, recorded under the sample's `sched` object and never read as a metric."""
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from buffon.report import cells
from buffon.runner import cgroup, engine, raw as rawlib
from buffon.workloads import Workload
from tests.test_engine import FakeCtx, arm, runner


def proc_tree(tasks):
    """A fixture /proc: {pid: {tid: "run wait slices" text or None for an unreadable file}}."""
    root = tempfile.mkdtemp()
    for pid, threads in tasks.items():
        for tid, text in threads.items():
            d = os.path.join(root, str(pid), "task", str(tid))
            os.makedirs(d)
            if text is not None:
                with open(os.path.join(d, "schedstat"), "w") as f:
                    f.write(text + "\n")
    return root


class ReadSchedstat(unittest.TestCase):
    def test_every_thread_of_every_pid(self):
        root = proc_tree({10: {10: "5000000 2000000 7", 11: "1000000 0 1"}, 20: {20: "3 4 5"}})
        self.addCleanup(shutil.rmtree, root)
        self.assertEqual(cgroup.read_schedstat([10, "20"], proc=root), {10: (5000000, 2000000, 7), 11: (1000000, 0, 1), 20: (3, 4, 5)})

    def test_a_gone_pid_an_unreadable_or_malformed_file_contribute_nothing(self):
        root = proc_tree({10: {10: "1 2 3", 11: None, 12: "garbage", 13: "1 2"}})
        self.addCleanup(shutil.rmtree, root)
        self.assertEqual(cgroup.read_schedstat([10, 99], proc=root), {10: (1, 2, 3)})


class Account(unittest.TestCase):
    def write(self, root, pid, tid, text):
        d = os.path.join(root, str(pid), "task", str(tid))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "schedstat"), "w") as f:
            f.write(text)

    def test_an_exited_thread_keeps_its_last_reading_and_a_reused_id_is_a_new_thread(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        acc = cgroup.SchedAccount()
        self.assertIsNone(acc.totals())
        self.write(root, 10, 10, "1000000 500000 2")
        self.write(root, 10, 11, "2000000 0 1")
        acc.observe([10], proc=root)
        self.write(root, 10, 10, "4000000 1500000 6")
        shutil.rmtree(os.path.join(root, "10", "task", "11"))          # thread 11 exits after the first reading
        acc.observe([10], proc=root)
        self.assertEqual(acc.totals(), {"run_ms": 6.0, "wait_ms": 1.5, "slices": 7, "threads": 2})
        self.write(root, 10, 10, "250000 250000 1")                     # id 10 now belongs to a new thread: its counters started again
        acc.observe([10], proc=root)
        self.assertEqual(acc.totals(), {"run_ms": 6.25, "wait_ms": 1.75, "slices": 8, "threads": 3})

    def test_a_baseline_is_not_counted_and_does_not_outlive_its_thread(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        acc = cgroup.SchedAccount()
        self.write(root, 10, 10, "30000000 1000000 5")                  # what the process ran before it joined the meter
        acc.baseline([10], proc=root)
        self.assertEqual(acc.totals(), {"run_ms": 0.0, "wait_ms": 0.0, "slices": 0, "threads": 1})
        self.write(root, 10, 10, "32000000 1500000 9")
        self.write(root, 10, 12, "1000000 0 1")                         # a thread started after popen: counted from zero
        acc.observe([10], proc=root)
        self.assertEqual(acc.totals(), {"run_ms": 3.0, "wait_ms": 0.5, "slices": 5, "threads": 2})
        self.write(root, 10, 10, "500000 0 1")                          # id 10 reused: the old thread's counted part retires, the new one counts from zero
        acc.observe([10], proc=root)
        self.assertEqual(acc.totals(), {"run_ms": 3.5, "wait_ms": 0.5, "slices": 6, "threads": 3})

    def test_take_sums_the_meters_closed_since_the_last_take_and_clears(self):
        cgroup.SCHED_CLOSED.clear()
        self.assertIsNone(cgroup.take_sched())
        cgroup.SCHED_CLOSED.extend([{"run_ms": 1.5, "wait_ms": 0.25, "slices": 3, "threads": 2}, None, {"run_ms": 2.0, "wait_ms": 1.0, "slices": 1, "threads": 1}])
        self.assertEqual(cgroup.take_sched(), {"run_ms": 3.5, "wait_ms": 1.25, "slices": 4, "threads": 3, "meters": 2})
        self.assertIsNone(cgroup.take_sched())
        cgroup.SCHED_CLOSED.append(None)                                  # a meter that saw no thread (no /proc, no schedstat)
        self.assertIsNone(cgroup.take_sched())


class CgroupMeterReadsTheTree(unittest.TestCase):
    def test_the_sampler_reads_the_cgroups_members_but_not_a_systemd_scopes_holder(self):
        root = proc_tree({4242: {4242: "3000000 1000000 4", 4243: "2000000 0 2"}, 4300: {4300: "40000000 0 9"}})
        group = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.addCleanup(shutil.rmtree, group)
        with open(os.path.join(group, "cgroup.procs"), "w") as f:
            f.write("4242\n4300\n")
        saved = cgroup.PROC_ROOT
        cgroup.PROC_ROOT = root
        try:
            meter = cgroup.CgroupMeter(group, holder=types.SimpleNamespace(pid=4300), mode="cgroup-systemd")
            meter._sample_rss()
            self.assertEqual(meter.sched.totals(), {"run_ms": 5.0, "wait_ms": 1.0, "slices": 6, "threads": 2})
            meter = cgroup.CgroupMeter(group, holder=None)
            meter._sample_rss()
            self.assertEqual(meter.sched.totals()["threads"], 3)
        finally:
            cgroup.PROC_ROOT = saved


class CgroupMeterBaseline(unittest.TestCase):
    def check(self, fake_spawn):
        # What the process ran before it joined the cgroup (its start-up, and when it forks, its pre-exec set-up) is not in cpu.stat, so it is not in run_ms either.
        root = proc_tree({4242: {4242: "30000000 1000000 5"}})
        group = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.addCleanup(shutil.rmtree, group)
        with open(os.path.join(group, "cgroup.procs"), "w") as f:
            f.write("4242\n")
        saved, saved_popen, saved_scan, saved_spawn = cgroup.PROC_ROOT, cgroup.subprocess.Popen, cgroup.egress.scan, cgroup.launch.spawn
        cgroup.PROC_ROOT = root
        cgroup.subprocess.Popen = lambda argv, **kwargs: types.SimpleNamespace(pid=4242)
        cgroup.launch.spawn = fake_spawn
        cgroup.egress.scan = lambda pids, read=None: set()    # the socket audit is not under test, and on a host without /proc it would run lsof through the faked Popen
        try:
            meter = cgroup.CgroupMeter(group, holder=None)
            meter._sampling = True          # no sampler thread: the test reads the tree itself
            meter.popen(["arm"])
            with open(os.path.join(root, "4242", "task", "4242", "schedstat"), "w") as f:
                f.write("32000000 1500000 9\n")
            meter._sample_rss()
            self.assertEqual(meter.sched.totals(), {"run_ms": 2.0, "wait_ms": 0.5, "slices": 4, "threads": 1})
        finally:
            cgroup.PROC_ROOT, cgroup.subprocess.Popen, cgroup.egress.scan, cgroup.launch.spawn = saved, saved_popen, saved_scan, saved_spawn

    def test_a_forked_child_is_counted_from_its_counters_when_popen_returns(self):
        with mock.patch.object(cgroup.launch, "available", lambda: False):
            self.check(cgroup.launch.spawn)

    def test_a_gated_process_is_counted_from_its_counters_at_the_gate(self):
        def spawn(argv, setup, **kwargs):
            setup(4242)
            return types.SimpleNamespace(pid=4242), 0
        with mock.patch.object(cgroup.launch, "available", lambda: True):
            self.check(spawn)


class PerSample(unittest.TestCase):
    """The engine records the schedstat totals of the meters a sample closed, under `sched`, and drops what a meter closed outside the sample."""

    def test_the_sample_gets_its_own_meters_totals(self):
        cgroup.SCHED_CLOSED.clear()
        n = {"i": 0}

        def fn(ctx, a):
            n["i"] += 1
            cgroup.SCHED_CLOSED.append({"run_ms": float(n["i"]), "wait_ms": 0.5, "slices": 2, "threads": 1})
            return {"cpu_ms": 1.0}

        w = Workload(id="t/w", family="t", fn=fn)
        r = runner([w], [arm("a")], rounds=2, warmup=0, apis=["openai-completions"], allow_short=True)
        cgroup.SCHED_CLOSED.append({"run_ms": 99.0, "wait_ms": 99.0, "slices": 99, "threads": 99})   # left over from before the run
        r.measure(FakeCtx(), engine.with_twins(r.plan.arms, "none"))
        self.assertEqual([s["sched"] for s in r.samples], [{"run_ms": 1.0, "wait_ms": 0.5, "slices": 2, "threads": 1, "meters": 1},
                                                           {"run_ms": 2.0, "wait_ms": 0.5, "slices": 2, "threads": 1, "meters": 1}])

    def test_a_sample_without_schedstat_has_no_sched(self):
        cgroup.SCHED_CLOSED.clear()
        w = Workload(id="t/w", family="t", fn=lambda ctx, a: {"cpu_ms": 1.0})
        r = runner([w], [arm("a")], rounds=1, warmup=0, apis=["openai-completions"], allow_short=True)
        r.measure(FakeCtx(), engine.with_twins(r.plan.arms, "none"))
        self.assertNotIn("sched", r.samples[0])


class NeverAMetric(unittest.TestCase):
    SCHED = {"run_ms": 12.5, "wait_ms": 3.25, "slices": 40, "threads": 9, "meters": 1}

    def sample(self, **extra):
        return dict({"arm": "pi-node", "scenario": "overhead/print", "api": "openai-completions", "round": 0, "warmup": False, "t_utc": "2026-10-12T00:00:00Z", "cpu_ms": 10.0,
                     "sched": dict(self.SCHED)}, **extra)

    def test_raw_format_accepts_exactly_the_documented_object(self):
        rawlib.check_sample(self.sample())
        for bad in ({**self.SCHED, "extra": 1}, {k: v for k, v in self.SCHED.items() if k != "meters"}, {**self.SCHED, "wait_ms": -1}, {**self.SCHED, "slices": float("nan")},
                    {**self.SCHED, "threads": True}, [1, 2]):
            with self.assertRaisesRegex(rawlib.RawError, "sched", msg=bad):
                rawlib.check_sample(self.sample(sched=bad))

    def test_the_report_scores_no_schedstat_cell(self):
        keys = {k for s in [self.sample(), self.sample(arm="pi-node-b", twin_of="pi-node")] for k, v in s.items()
                if k not in cells.IDENTITY and cells.scored(k) and isinstance(v, (int, float)) and not isinstance(v, bool)}
        self.assertEqual(keys, {"cpu_ms"})


@unittest.skipUnless(os.path.exists(f"/proc/self/task/{os.getpid()}/schedstat"), "needs Linux schedstat (CONFIG_SCHED_INFO)")
class LiveMeter(unittest.TestCase):
    """A real process tree under the meter this host gives the runner."""

    def test_a_busy_child_is_accounted(self):
        self.busy_child(None)

    def test_a_busy_child_is_accounted_without_a_cgroup(self):
        self.busy_child("rusage")   # the meter a pod uses: its cgroup is read-only

    def busy_child(self, force):
        # Two threads each spin 120 ms of their own CPU and then wait, alive, until the test has made the meter read them; no timing is assumed.
        cgroup.SCHED_CLOSED.clear()
        meter = cgroup.new_meter(force)
        code = ("import sys,threading,time\n"
                "go,done=threading.Event(),threading.Event()\n"
                "def spin():\n    t=time.thread_time()\n    while time.thread_time()-t<0.12: pass\n"
                "def worker():\n    spin();done.set();go.wait()\n"
                "th=threading.Thread(target=worker);th.start();spin();done.wait()\n"
                "print('spun',flush=True);sys.stdin.read();go.set();th.join()")
        try:
            child = meter.popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            self.assertEqual(child.stdout.readline().strip(), "spun")
            meter.max_proc_rss_mib()          # one sampler reading now, while both threads are alive and idle
            child.stdin.close()
            (meter.wait if hasattr(meter, "wait") else child.wait)(120)
            cpu = meter.cpu_ms()
        finally:
            meter.close()
        sched = cgroup.take_sched()
        self.assertIsNotNone(sched, meter.mode)
        self.assertGreaterEqual(sched["threads"], 2)
        self.assertGreater(sched["slices"], 0)
        self.assertGreaterEqual(sched["run_ms"], 240, (sched, cpu, meter.mode))
        # A thread is seen at most one sample interval late: never more than the meter's own CPU (1 ms of slack for the two clocks' rounding).
        self.assertLessEqual(sched["run_ms"], cpu + 1, (sched, cpu, meter.mode))

if __name__ == "__main__":
    unittest.main()
