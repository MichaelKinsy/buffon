# SPDX-License-Identifier: Apache-2.0
"""The wall time of a short command is the time the kernel says it exited, not the time a poll loop next looked.

A wait4(WNOHANG) loop with a 5 ms sleep made the wall time of a 5 ms command jump between 12 and 42 ms from round to round. These tests run a tiny process through the meters
and compare the meter's wall time with a plain perf_counter around subprocess.run."""
import statistics
import subprocess
import sys
import time
import unittest
from unittest import mock

from buffon.runner import cgroup, exitwatch, procio

ARGV = ["/bin/sh", "-c", "exit 0"]
ROUNDS = 30
NULL = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}


class TreeMeter(cgroup.Meter):
    """The part of CgroupMeter that waits (it inherits Meter.wait), without a cgroup to join."""

    mode = "test"

    def cpu_ms(self):
        return 0.0

    def popen(self, argv, **kwargs):
        self.child = subprocess.Popen(argv, **kwargs)
        return self.child


def direct_ms():
    """What a caller sees with no meter at all: spawn, run and reap one process."""
    t0 = time.perf_counter()
    subprocess.run(ARGV, check=True, **NULL)
    return (time.perf_counter() - t0) * 1000


def iqr(values):
    ordered = sorted(values)
    return ordered[len(ordered) * 3 // 4] - ordered[len(ordered) // 4]


def metered_ms(meter_class):
    meter = meter_class()
    try:
        return procio.Batch(ARGV, None, None, meter, timeout=10).run()["wall_ms"]
    finally:
        meter.close()


class ShortCommand(unittest.TestCase):
    def assert_tight(self, meter_class):
        direct, walls = [], []
        for _ in range(ROUNDS):  # interleaved, so a busy host slows both
            direct.append(direct_ms())
            walls.append(metered_ms(meter_class))
        median, base = statistics.median(walls), statistics.median(direct)
        # The meter stops at the exit, so it is no slower than a call that also reaps and returns. Polling put the median 5 ms or more above.
        self.assertLessEqual(median, base + 2, f"meter {median:.2f} ms, direct {base:.2f} ms")
        self.assertLess(median, 30)
        # Polling quantised the wall time in steps of 5 ms or more, so the middle half of the walls spread wider than the same half of the direct calls.
        self.assertLessEqual(iqr(walls), iqr(direct) + 3, f"meter {sorted(walls)}, direct {sorted(direct)}")

    def test_rusage_meter_wall_is_the_kernels_exit_time(self):
        self.assert_tight(cgroup.RusageMeter)

    def test_meter_base_wait_is_the_kernels_exit_time(self):
        self.assert_tight(TreeMeter)

    @unittest.skipIf(exitwatch.supported() is None, "no pid watch on this host")
    def test_the_rusage_meter_still_has_the_rusage_of_the_tree(self):
        meter = cgroup.RusageMeter()
        try:
            meter.popen([sys.executable, "-c", "import subprocess,sys;subprocess.run([sys.executable,'-c','sum(range(3000000))'])"], **NULL)
            meter.wait(30)
            self.assertIsNotNone(meter.rusage)
            self.assertGreater(meter.cpu_ms(), 20)  # the grandchild's CPU is in it
        finally:
            meter.close()


class ExitStamp(unittest.TestCase):
    def run_sleep(self, meter_class, seconds):
        meter = meter_class()
        try:
            before = time.perf_counter_ns()
            meter.popen([sys.executable, "-c", f"import time;time.sleep({seconds})"], **NULL)
            meter.wait(10)
            after = time.perf_counter_ns()
            self.assertIsNotNone(meter.exit_ns)
            self.assertLessEqual(meter.exit_ns, after)
            self.assertGreater(meter.exit_ns, before)
            return meter.exit_ns - before
        finally:
            meter.close()

    def test_the_stamp_is_taken_before_wait_returns(self):
        for meter_class in (cgroup.RusageMeter, TreeMeter):
            self.assertGreater(self.run_sleep(meter_class, 0.2), 200e6)

    def test_batch_uses_the_stamp_for_its_exit(self):
        meter = cgroup.RusageMeter()
        try:
            result = procio.Batch([sys.executable, "-c", "pass"], None, None, meter).run()
            self.assertEqual(result["t_exit"], meter.exit_ns)
        finally:
            meter.close()


class Timeout(unittest.TestCase):
    def test_a_process_that_outlives_the_timeout_raises_and_can_be_waited_again(self):
        for meter_class in (cgroup.RusageMeter, TreeMeter):
            meter = meter_class()
            try:
                meter.popen([sys.executable, "-c", "import time;time.sleep(30)"], **NULL)
                t0 = time.monotonic()
                with self.assertRaises(subprocess.TimeoutExpired):
                    meter.wait(0.3)
                self.assertTrue(0.25 < time.monotonic() - t0 < 2)
                self.assertIsNone(meter.exit_ns)
                self.assertFalse(procio.wait(meter, meter.child, 0.05))
                meter.child.kill()
                meter.wait(10)
                self.assertEqual(meter.child.returncode, -9)
                self.assertIsNotNone(meter.exit_ns)
            finally:
                meter.close()

    def test_batch_reports_the_timeout(self):
        meter = cgroup.RusageMeter()
        try:
            result = procio.Batch([sys.executable, "-c", "import time;time.sleep(30)"], None, None, meter, timeout=0.3).run()
            self.assertTrue(result["timed_out"])
            self.assertLess(result["wall_ms"], 2000)
        finally:
            meter.close()


@unittest.skipIf(exitwatch.supported() is None, "no pid watch on this host")
class WaitExit(unittest.TestCase):
    def test_returns_the_instant_of_the_exit_and_leaves_the_zombie(self):
        child = subprocess.Popen(["/bin/sh", "-c", "sleep 0.1"], **NULL)
        try:
            before = time.perf_counter_ns()
            stamp = exitwatch.wait_exit(child.pid, 10)
            after = time.perf_counter_ns()
            self.assertTrue(before + 90e6 < stamp <= after)
            self.assertIsNone(child.returncode)
            self.assertEqual(child.wait(), 0)  # still there to reap
        finally:
            child.kill()
            child.wait()

    def test_times_out(self):
        child = subprocess.Popen(["/bin/sh", "-c", "sleep 30"], **NULL)
        try:
            with self.assertRaises(TimeoutError):
                exitwatch.wait_exit(child.pid, 0.1)
        finally:
            child.kill()
            child.wait()

    def test_a_pid_that_was_reaped_is_not_watched(self):
        child = subprocess.Popen(["/bin/sh", "-c", "exit 0"], **NULL)
        child.wait()
        self.assertIsNone(exitwatch.wait_exit(child.pid, 1))

    def test_the_switch_interval_is_restored(self):
        before = sys.getswitchinterval()
        child = subprocess.Popen(["/bin/sh", "-c", "exit 0"], **NULL)
        exitwatch.wait_exit(child.pid, 10)
        child.wait()
        self.assertEqual(sys.getswitchinterval(), before)


class PollingFallback(unittest.TestCase):
    """A host with neither pidfd nor kqueue polls, as before, and still stamps the exit."""

    def test_both_meters_wait_by_polling(self):
        with mock.patch.object(exitwatch, "supported", lambda: None):
            for meter_class in (cgroup.RusageMeter, TreeMeter):
                meter = meter_class()
                try:
                    meter.popen([sys.executable, "-c", "import time;time.sleep(0.1)"], **NULL)
                    meter.wait(10)
                    self.assertEqual(meter.child.returncode, 0)
                    self.assertIsNotNone(meter.exit_ns)
                    meter.popen([sys.executable, "-c", "import time;time.sleep(30)"], **NULL)
                    with self.assertRaises(subprocess.TimeoutExpired):
                        meter.wait(0.2)
                    meter.child.kill()
                    meter.wait(10)
                finally:
                    meter.close()


if __name__ == "__main__":
    unittest.main()
