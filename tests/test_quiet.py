# SPDX-License-Identifier: Apache-2.0
"""Strictly serial, quiet-host measurement: the host lock, the pre-sample quiet gate, and what the engine records per sample."""
import fcntl
import os
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

from buffon.runner import engine, quiet
from buffon.workloads import Workload, soak


def try_lock_in_other_process(own, foreign=()):
    """What a second buffon process on the host sees: 'ok' or 'held'."""
    code = ("import sys\nfrom buffon.runner import quiet\ntry:\n    with quiet.HostLock(sys.argv[1], sys.argv[2:]):\n        print('ok')\nexcept quiet.LockHeld:\n    print('held')\n")
    done = subprocess.run([sys.executable, "-c", code, own, *foreign], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), timeout=60)
    return done.stdout.strip()


class HostLockTest(unittest.TestCase):
    def path(self, name="a.lock"):
        return os.path.join(tempfile.mkdtemp(), name)

    def test_a_second_run_on_the_host_is_refused_while_the_first_holds_the_lock(self):
        path = self.path()
        with quiet.HostLock(path):
            self.assertEqual(try_lock_in_other_process(path), "held")
            with self.assertRaisesRegex(quiet.LockHeld, "measurements are serial"):   # and a second run in the same process, which has no inherited descriptor for its own lock
                quiet.HostLock(path).__enter__()
        self.assertEqual(try_lock_in_other_process(path), "ok")   # released when the first run ends

    def test_a_lock_another_tool_holds_refuses_the_run_and_releases_what_was_taken(self):
        own, foreign = self.path("own.lock"), self.path("slot.lock")
        holder = subprocess.Popen([sys.executable, "-c", "import fcntl,os,sys,time\nfd=os.open(sys.argv[1],os.O_RDWR|os.O_CREAT)\nfcntl.flock(fd,fcntl.LOCK_EX)\nprint('locked',flush=True)\ntime.sleep(60)", foreign],
                                  stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            self.assertEqual(try_lock_in_other_process(own, [foreign]), "held")
            self.assertEqual(try_lock_in_other_process(own), "ok")   # the own lock was released by the failed start
        finally:
            holder.kill()
            holder.wait()

    @unittest.skipUnless(os.path.isdir("/proc/self/fd") or hasattr(fcntl, "F_GETPATH"), "no way to list this process's descriptors")
    def test_a_run_inside_the_holders_wrapper_is_let_through(self):
        """A bench-slot wrapper locks the file and starts the run as its child: the descriptor is inherited, so the slot is the run's own."""
        foreign = self.path("slot.lock")
        holder = os.open(foreign, os.O_RDWR | os.O_CREAT)
        fcntl.flock(holder, fcntl.LOCK_EX)
        try:
            with quiet.HostLock(self.path("own.lock"), [foreign]):
                pass
        finally:
            os.close(holder)

    def test_without_proc_the_inherited_descriptor_is_found_through_fcntl(self):
        """macOS has no /proc/self/fd: F_GETPATH names what each descriptor is open on."""
        foreign = self.path("slot.lock")
        holder = os.open(foreign, os.O_RDWR | os.O_CREAT)
        fcntl.flock(holder, fcntl.LOCK_EX)
        real_listdir = os.listdir

        def no_proc(p="."):
            if str(p).startswith("/proc"):
                raise FileNotFoundError(p)
            return real_listdir(p)

        def getpath(fd, cmd, buf):
            if fd == holder:
                return os.path.realpath(foreign).encode() + b"\0" * 8
            raise OSError(9, "Bad file descriptor")
        try:
            with mock.patch.object(quiet.os, "listdir", no_proc), mock.patch.object(quiet.fcntl, "F_GETPATH", 50, create=True), mock.patch.object(quiet.fcntl, "fcntl", getpath):
                self.assertTrue(quiet._inherited(foreign))
                self.assertFalse(quiet._inherited(self.path("other.lock")))
            with mock.patch.object(quiet.os, "listdir", no_proc), mock.patch.object(quiet.fcntl, "F_GETPATH", None, create=True):
                self.assertFalse(quiet._inherited(foreign))    # a platform with neither: the lock is simply contended
        finally:
            os.close(holder)

    def test_a_free_foreign_lock_is_taken_for_the_run_and_blocks_others(self):
        foreign = self.path("slot.lock")
        with quiet.HostLock(self.path("own.lock"), [foreign]):
            self.assertEqual(try_lock_in_other_process(self.path("own2.lock"), [foreign]), "held")


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class GateTest(unittest.TestCase):
    def gate(self, busy_by_check, loads=None, **kw):
        clock = Clock()
        checks = iter(busy_by_check)
        stats = {"n": 0}

        def read():
            return {"i": stats}

        def fractions(before, after, cpus):
            return {c: next(checks) for c in cpus}
        quiet_mod = quiet
        saved = quiet_mod.cpumon.busy_fractions
        quiet_mod.cpumon.busy_fractions = fractions
        self.addCleanup(setattr, quiet_mod.cpumon, "busy_fractions", saved)
        loads = iter(loads or [(1.0, 1)] * 100)
        kw.setdefault("detail", lambda: {2: (100, 0, 0), 3: (100, 0, 0)})
        kw.setdefault("runnable", lambda cpus: 0)
        kw.setdefault("psi", lambda: 0.0)
        kw.setdefault("throttled", lambda: None)
        return quiet.QuietGate([2, 3], read=read, load=lambda: next(loads), sleep=clock.sleep, clock=clock.now, **kw), clock

    def test_a_quiet_host_passes_at_once_and_the_readings_are_returned(self):
        g, _ = self.gate([0.02, 0.01])
        reading, waited, ok = g.wait()
        self.assertTrue(ok)
        self.assertEqual(reading, {"host_load1": 1.0, "host_runnable": 1, "pinned_busy": 0.02, "pinned_iowait": 0.0, "pinned_steal": 0.0, "cpuset_runnable": 0, "cpuset_kthreads": None,
                                   "throttled": None, "psi_cpu_some_avg10": 0.0, "quiet_checks": 1})
        self.assertLess(waited, 1000)

    def test_a_busy_host_is_waited_for_and_the_wait_is_recorded(self):
        g, clock = self.gate([0.9, 0.9, 0.5, 0.5, 0.05, 0.05])   # two CPUs per check: busy, busy, quiet
        reading, waited, ok = g.wait()
        self.assertTrue(ok)
        self.assertEqual(reading["pinned_busy"], 0.05)
        self.assertGreaterEqual(waited, 2000)
        self.assertGreaterEqual(clock.now(), 2.0)

    def test_the_gate_gives_up_after_the_timeout_and_says_so(self):
        g, _ = self.gate([0.9] * 1000, timeout_s=5)
        reading, waited, ok = g.wait()
        self.assertFalse(ok)
        self.assertGreaterEqual(waited, 5000)
        self.assertEqual(reading["pinned_busy"], 0.9)

    def test_other_threads_running_on_the_pinned_cpus_hold_a_sample_back(self):
        counts = iter([4, 4, 0])
        g, _ = self.gate([0.0] * 20, runnable=lambda cpus: next(counts), max_runnable=1)
        reading, waited, ok = g.wait()
        self.assertTrue(ok)
        self.assertEqual(reading["cpuset_runnable"], 0)
        self.assertGreaterEqual(waited, 2000)

    def test_the_load_of_the_rest_of_the_host_is_recorded_and_never_blocks(self):
        g, _ = self.gate([0.0] * 4, loads=[(220.0, 190)])
        reading, waited, ok = g.wait()
        self.assertTrue(ok)
        self.assertEqual((reading["host_load1"], reading["host_runnable"]), (220.0, 190))
        self.assertLess(waited, 1000)

    def check_reason(self, kw, expect):
        g, _ = self.gate([0.0] * 1000, timeout_s=3, **kw)
        reading, waited, ok = g.wait()
        self.assertFalse(ok)
        self.assertIn(expect, "; ".join(g.reasons(reading)))

    def test_steal_throttling_and_pressure_each_block(self):
        ticks = {"n": 0}

        def detail():
            ticks["n"] += 1
            n = ticks["n"]
            return {2: (100 * n, 10 * n, 0), 3: (100 * n, 0, 0)}     # 10% iowait on CPU 2
        g, _ = self.gate([0.0] * 4, detail=detail)   # iowait is recorded, never gated (R9 section 8, row 12)
        reading, waited, ok = g.wait()
        self.assertTrue(ok)
        self.assertEqual(reading["pinned_iowait"], 0.1)

        def steal():
            ticks["n"] += 1
            n = ticks["n"]
            return {2: (100 * n, 0, 0), 3: (100 * n, 0, 5 * n)}      # 5% steal on CPU 3
        self.check_reason({"detail": steal}, "steal 5%")
        count = {"n": 0}

        def throttled():
            count["n"] += 3
            return count["n"]
        self.check_reason({"throttled": throttled}, "cgroup throttled 3 times")
        self.check_reason({"psi": lambda: 42.0}, "CPU pressure 42.0%")

    def test_a_reading_that_is_unavailable_never_blocks(self):
        g, _ = self.gate([0.0] * 4, runnable=lambda cpus: None, psi=lambda: None, throttled=lambda: None)
        self.assertTrue(g.wait()[2])

    def test_runnable_on_counts_only_running_threads_on_the_pinned_cpus_and_not_ourselves(self):
        proc = tempfile.mkdtemp()
        def thread(pid, tid, state, cpu):
            d = os.path.join(proc, str(pid), "task", str(tid))
            os.makedirs(d)
            rest = [state] + ["0"] * 35 + [str(cpu)] + ["0"] * 5
            with open(os.path.join(d, "stat"), "w") as f:
                f.write(f"{tid} (we ird) " + " ".join(rest))
        thread(100, 100, "R", 2)       # counts
        thread(100, 101, "R", 3)       # counts (a second thread of the same process)
        thread(100, 102, "S", 2)       # sleeping
        thread(200, 200, "R", 9)       # another CPU
        thread(os.getpid(), os.getpid(), "R", 2)   # ourselves
        self.assertEqual(quiet.runnable_on([2, 3], proc=proc), 2)

    def test_the_busiest_pinned_cpu_decides(self):
        g, _ = self.gate([0.01, 0.4], max_busy=0.1, timeout_s=0)
        self.assertFalse(g.wait()[2])


class FakeCtx:
    def __init__(self):
        self.opts = types.SimpleNamespace(api=None)
        self.server = types.SimpleNamespace(context={}, flush_log=lambda: None)

    def release(self):
        pass

    def harnesses_for(self, arm):
        return []


def runner(**kw):
    out = tempfile.mkdtemp()
    w = Workload(id="t/w", family="t", fn=lambda ctx, a: {"cpu_ms": 1.0})
    plan = engine.Plan(workloads=[w], arms=[types.SimpleNamespace(id="a", twin_of=None, apis=["openai-completions"], supports_api=lambda x: True)], out=out, rounds=1, warmup=0,
                       apis=["openai-completions"], allow_short=True, **kw)
    return engine.Runner(plan, log=lambda *_: None), w


class EngineRecordsTheHost(unittest.TestCase):
    def test_every_sample_carries_the_host_readings_and_the_wait(self):
        r, w = runner()
        r.gate = types.SimpleNamespace(window_s=0.25, wait=lambda: ({"host_load1": 7.5, "host_runnable": 3, "pinned_busy": 0.03}, 40, True))
        r.measure(FakeCtx(), [r.plan.arms[0]])
        s = r.samples[0]
        self.assertEqual((s["host_load1"], s["host_runnable"], s["pinned_busy"], s["quiet_wait_ms"]), (7.5, 3, 0.03, 40))
        self.assertEqual(r.gate_stats["timeouts"], 0)

    def test_a_host_that_never_quiets_is_sampled_anyway_and_labelled_unless_strict(self):
        r, w = runner()
        started = []
        w.fn = lambda ctx, a: started.append(1) or {"cpu_ms": 1.0}
        r.gate = types.SimpleNamespace(window_s=0.25, wait=lambda: ({"host_load1": 90.0, "host_runnable": 80, "pinned_busy": 0.8}, 300000, False), reasons=lambda host: ["pinned CPUs 80% busy"])
        r.measure(FakeCtx(), [r.plan.arms[0]])
        self.assertEqual(started, [1])   # the sample ran: nothing is discarded
        s = r.samples[0]
        self.assertTrue(s["quiet_gave_up"])
        self.assertNotIn("failure", s)
        self.assertIn("sample was taken anyway", s["quiet_note"])
        self.assertEqual(r.gate_stats["timeouts"], 1)   # the trust badge reads this: Noisy

    def test_a_host_that_never_quiets_fails_the_sample_without_starting_a_process(self):
        r, w = runner(strict=True)
        started = []
        w.fn = lambda ctx, a: started.append(1) or {"cpu_ms": 1.0}
        r.gate = types.SimpleNamespace(window_s=0.25, wait=lambda: ({"host_load1": 90.0, "host_runnable": 80, "pinned_busy": 0.8}, 300000, False), reasons=lambda host: ["pinned CPUs 80% busy", "steal 9%"])
        r.measure(FakeCtx(), [r.plan.arms[0]])
        self.assertEqual(started, [])
        self.assertIn("the pinned CPUs were not quiet within 300 s (pinned CPUs 80% busy; steal 9%)", r.samples[0]["failure"])
        self.assertEqual(r.samples[0]["pinned_busy"], 0.8)
        self.assertEqual(r.gate_stats["timeouts"], 1)

    def test_a_run_is_refused_while_another_holds_the_host_lock(self):
        lock = os.path.join(tempfile.mkdtemp(), "x.lock")
        r, _ = runner(lock_file=lock)
        with quiet.HostLock(lock):
            with self.assertRaisesRegex(engine.Refused, "measurements are serial"):
                r.run()


class SoakIsSerial(unittest.TestCase):
    def test_arms_soak_one_after_another_each_after_a_quiet_check(self):
        events = []
        saved = soak.run_arm

        def fake_run_arm(arm, ctx, server, opts, stop, out):
            events.append(("start", arm.id, threading.active_count()))
            out.update(series=[], turns=1)
            events.append(("end", arm.id, threading.active_count()))
        soak.run_arm = fake_run_arm
        try:
            checks = []

            class Session:
                plan = types.SimpleNamespace(apis=["openai-completions"], timeout=10, params={"soak_minutes": 0.01}, quiet_timeout_s=300)
                samples, skipped, violations = [], [], []

                def quiet_wait(self):
                    checks.append(len(events))
                    return {"host_load1": 1.0, "host_runnable": 1, "pinned_busy": 0.0, "quiet_wait_ms": 0}, True
            arms = [types.SimpleNamespace(id=i, twin_of=None, supports_mode=lambda m: True, supports_api=lambda a: True, cannot_run={}) for i in ("a", "b", "c")]
            ctx = types.SimpleNamespace(work=tempfile.mkdtemp(), opts=types.SimpleNamespace(params={}), _harnesses={}, release=lambda: None)
            soak.soak("stress", Session(), ctx, arms)
        finally:
            soak.run_arm = saved
        self.assertEqual([(e[0], e[1]) for e in events], [("start", "a"), ("end", "a"), ("start", "b"), ("end", "b"), ("start", "c"), ("end", "c")])
        self.assertEqual(checks, [0, 2, 4])


if __name__ == "__main__":
    unittest.main()


class ForeignThreadsAreNamed(GateTest):
    """A gate that waits says who it waited for: the threads runnable on the pinned CPUs during the wait, by name and pid (decision 03:54Z)."""

    def test_foreign_on_reads_runnable_threads_with_their_comm_and_last_cpu(self):
        import os as _os
        import tempfile as _tf
        proc = _tf.mkdtemp()
        for pid, tid, comm, state, cpu in ((10, 10, "containerd-shim", "R", 193), (11, 11, "sleeper", "S", 193), (12, 12, "other", "R", 5), (99, 99, "me", "R", 192)):
            d = _os.path.join(proc, str(pid), "task", str(tid))
            _os.makedirs(d)
            fields = ["0"] * 40
            fields[0], fields[36] = state, str(cpu)
            with open(_os.path.join(d, "stat"), "w") as f:
                f.write(f"{tid} ({comm}) " + " ".join(fields))
        found = quiet.foreign_on([192, 193], proc=proc, me=99)
        self.assertEqual(found, [{"pid": 10, "tid": 10, "comm": "containerd-shim", "cpu": 193}])
        self.assertEqual(quiet.runnable_on([192, 193], proc=proc, me=99), 1)

    def write_proc(self, threads):
        import os as _os
        import tempfile as _tf
        proc = _tf.mkdtemp()
        for pid, tid, comm, state, cpu, ppid, flags in threads:
            d = _os.path.join(proc, str(pid), "task", str(tid))
            _os.makedirs(d)
            fields = ["0"] * 40
            fields[0], fields[1], fields[6], fields[36] = state, str(ppid), str(flags), str(cpu)
            with open(_os.path.join(d, "stat"), "w") as f:
                f.write(f"{tid} ({comm}) " + " ".join(fields))
        return proc

    def test_kernel_threads_are_ignored_by_the_flag_by_pid_2_and_by_a_parent_of_2_and_user_threads_still_count(self):
        proc = self.write_proc([(10, 10, "bpfrb/192", "R", 192, 2, quiet.PF_KTHREAD), (11, 11, "evdefer/193", "R", 193, 0, quiet.PF_KTHREAD), (2, 2, "kthreadd", "R", 192, 0, 0),
                                (12, 12, "kworker/u8:1", "R", 193, 2, 0), (20, 20, "containerd-shim", "R", 193, 1, 0), (21, 21, "sleeper", "S", 193, 1, 0), (99, 99, "me", "R", 192, 1, 0)])
        found = quiet.foreign_on([192, 193], proc=proc, me=99)
        self.assertEqual([t["comm"] for t in found], ["containerd-shim"])
        self.assertEqual(sorted(t["comm"] for t in found.kernel), ["bpfrb/192", "evdefer/193", "kthreadd", "kworker/u8:1"])
        self.assertEqual(quiet.runnable_on([192, 193], proc=proc, me=99), 1)

    def test_the_gate_does_not_wait_for_kernel_threads_and_records_how_many_it_ignored_and_which(self):
        kern = [{"pid": 10, "tid": 10, "comm": "bpfrb/192", "cpu": 192}, {"pid": 11, "tid": 11, "comm": "bpfrb/193", "cpu": 193}, {"pid": 12, "tid": 12, "comm": "evdefer/192", "cpu": 192}]

        def walk(cpus, proc="/proc", me=None):
            t = quiet.Threads()
            t.kernel = kern
            return t
        real = quiet.foreign_on
        quiet.foreign_on = walk
        try:
            g, _ = self.gate([0.0] * 30)
            g.runnable, g.foreign = quiet.runnable_on, quiet.foreign_on
            reading, waited, ok = g.wait()
        finally:
            quiet.foreign_on = real
        self.assertTrue(ok)
        self.assertEqual((reading["cpuset_runnable"], reading["cpuset_kthreads"]), (0, 3))
        self.assertEqual(reading["ignored_kthreads"], "bpfrb/* x1 on cpu 192,193; evdefer/* x1 on cpu 192")
        self.assertNotIn("foreign_threads", reading)
        self.assertLess(waited, 1000)

    def test_a_user_thread_still_blocks_while_kernel_threads_are_ignored(self):
        calls = iter([(1, 2), (0, 2), (0, 0)])

        def walk(cpus, proc="/proc", me=None):
            users, kernels = next(calls)
            t = quiet.Threads([{"pid": 7, "tid": 7, "comm": "dockerd", "cpu": 192}] * users)
            t.kernel = [{"pid": 10 + i, "tid": 10 + i, "comm": f"kworker/{i}", "cpu": 192} for i in range(kernels)]
            return t
        real = quiet.foreign_on
        quiet.foreign_on = walk
        try:
            g, _ = self.gate([0.0] * 60)
            g.runnable, g.foreign = quiet.runnable_on, quiet.foreign_on
            reading, waited, ok = g.wait()
        finally:
            quiet.foreign_on = real
        self.assertTrue(ok)
        self.assertGreaterEqual(waited, 1000)   # the first check had a user thread; the kernel threads of the second did not hold it
        self.assertEqual(reading["foreign_threads"], "dockerd[7] x1 on cpu 192")
        self.assertEqual(reading["ignored_kthreads"], "kworker/* x2 on cpu 192")

    def test_each_wait_starts_with_no_ignored_kernel_threads(self):
        calls = iter([2, 0])

        def walk(cpus, proc="/proc", me=None):
            t = quiet.Threads()
            t.kernel = [{"pid": 10 + i, "tid": 10 + i, "comm": f"kworker/{i}", "cpu": 192} for i in range(next(calls))]
            return t
        real = quiet.foreign_on
        quiet.foreign_on = walk
        try:
            g, _ = self.gate([0.0] * 60)
            g.runnable, g.foreign = quiet.runnable_on, quiet.foreign_on
            first, _, _ = g.wait()
            second, _, _ = g.wait()
        finally:
            quiet.foreign_on = real
        self.assertEqual(first["ignored_kthreads"], "kworker/* x1 on cpu 192")
        self.assertNotIn("ignored_kthreads", second)
        self.assertEqual(second["cpuset_kthreads"], 0)

    def test_a_wait_records_who_was_runnable_most_often_and_a_quiet_one_records_nothing(self):
        threads = iter([[{"pid": 7, "tid": 7, "comm": "dockerd", "cpu": 192}], [{"pid": 7, "tid": 7, "comm": "dockerd", "cpu": 193}, {"pid": 8, "tid": 8, "comm": "x", "cpu": 192}], []])
        counts = iter([1, 2, 0])
        g, _ = self.gate([0.0] * 30, runnable=lambda cpus: next(counts), foreign=lambda cpus: next(threads), max_runnable=0)
        reading, waited, ok = g.wait()
        self.assertTrue(ok)
        self.assertEqual(reading["foreign_threads"], "dockerd[7] x2 on cpu 192,193; x[8] x1 on cpu 192")
        g2, _ = self.gate([0.0] * 4)
        reading2, _, _ = g2.wait()
        self.assertNotIn("foreign_threads", reading2)

    def test_a_process_with_several_runnable_threads_counts_once_per_check(self):
        """Review: xN is the number of checks a process was seen in; two runnable threads of one process in one check counted 2."""
        both = [{"pid": 7, "tid": 7, "comm": "java", "cpu": 192}, {"pid": 7, "tid": 70, "comm": "java", "cpu": 193}]
        threads = iter([both, both, []])
        counts = iter([2, 2, 0])
        g, _ = self.gate([0.0] * 30, runnable=lambda cpus: next(counts), foreign=lambda cpus: next(threads), max_runnable=0)
        reading, _, ok = g.wait()
        self.assertTrue(ok)
        self.assertEqual(reading["foreign_threads"], "java[7] x2 on cpu 192,193")

    def test_the_most_seen_come_first_and_each_wait_starts_empty(self):
        """Review: an order by pid and a gate that kept the previous wait's threads both survived the tests."""
        a, b = {"pid": 2, "tid": 2, "comm": "rare", "cpu": 192}, {"pid": 9, "tid": 9, "comm": "often", "cpu": 192}
        threads = iter([[a, b], [b], [], [], []])
        counts = iter([2, 1, 0, 0, 0])
        g, _ = self.gate([0.0] * 30, runnable=lambda cpus: next(counts), foreign=lambda cpus: next(threads), max_runnable=0)
        reading, _, _ = g.wait()
        self.assertEqual(reading["foreign_threads"], "often[9] x2 on cpu 192; rare[2] x1 on cpu 192")
        reading, _, ok = g.wait()
        self.assertTrue(ok)
        self.assertNotIn("foreign_threads", reading, "the next sample's wait saw nobody")

    def test_the_default_gate_walks_proc_once_per_check(self):
        """Review: the count and the names were two walks of /proc (about a second each on the bench host)."""
        walks = []
        real = quiet.foreign_on
        quiet.foreign_on = lambda cpus, proc="/proc", me=None: walks.append(1) or [{"pid": 5, "tid": 5, "comm": "k", "cpu": 192}]
        try:
            g, _ = self.gate([0.0] * 4)
            g.runnable, g.foreign = quiet.runnable_on, quiet.foreign_on
            r = g.reading()
        finally:
            quiet.foreign_on = real
        self.assertEqual((r["cpuset_runnable"], len(walks)), (1, 1))
        self.assertEqual(g.seen, {(5, "k"): [1, {192}]})

    def test_a_refused_wait_names_them_too(self):
        g, _ = self.gate([0.0] * 1000, timeout_s=3, runnable=lambda cpus: 1, foreign=lambda cpus: [{"pid": 3, "tid": 3, "comm": "noisy", "cpu": 192}])
        reading, _, ok = g.wait()
        self.assertFalse(ok)
        self.assertIn("noisy[3]", reading["foreign_threads"])
