# SPDX-License-Identifier: Apache-2.0
"""A sample measures the harness from its exec to its exit, nothing before.

The runner used to fork from its own (large) address space, join the cgroup, pin and open perf counters in Python, and only then exec. The clock started before all that,
the cgroup and wait4 counted the child's CPU for it, and the cgroup's memory.peak and ru_maxrss counted its pages. A /bin/true that runs for 0.2 ms read 5 to 20 ms of wall and 3 ms
of CPU on a 300 MB runner. These tests run a do-nothing binary through every meter this host has and compare with a direct measurement: spawn, wait4."""
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from buffon.runner import cgroup, launch, perfcount, procio

TRUE = shutil.which("true") or "/usr/bin/true"
ROUNDS = 30
NULL = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
TOLERANCE_MS = 1.0
BIG_RUNNER = [bytearray(1024) for _ in range(160 * 1024)]   # 160 MiB resident: what a fork of the runner has to copy and, at exec, to unmap


def direct():
    """(wall ms, cpu ms) of the same process started with a bare Popen and reaped with wait4."""
    t0 = time.perf_counter()
    child = subprocess.Popen([TRUE], **NULL)
    _, status, usage = os.wait4(child.pid, 0)
    child.returncode = os.waitstatus_to_exitcode(status)
    return (time.perf_counter() - t0) * 1000, (usage.ru_utime + usage.ru_stime) * 1000


def metered(factory):
    meter = factory()
    try:
        result = procio.Batch([TRUE], None, None, meter, timeout=10).run()
        return result["wall_ms"], result["cpu_ms"], result["peak_mem_mib"], result["max_proc_rss_mib"], meter
    finally:
        meter.close()


def cgroup_meter():
    meter = cgroup.new_meter()
    if meter.mode == "rusage":
        meter.close()
        raise unittest.SkipTest("no delegated cgroup on this host")
    return meter


class MeasuredFromExec(unittest.TestCase):
    factory = staticmethod(cgroup.RusageMeter)
    kind = "rusage"

    def run_rounds(self):
        samples, base = [], []
        for _ in range(ROUNDS):   # interleaved, so a busy host slows both
            base.append(direct())
            samples.append(metered(self.factory)[:4])
        return samples, base

    def test_wall_and_cpu_match_a_direct_measurement(self):
        samples, base = self.run_rounds()
        wall, cpu = statistics.median(s[0] for s in samples), statistics.median(s[1] for s in samples)
        direct_wall, direct_cpu = statistics.median(b[0] for b in base), statistics.median(b[1] for b in base)
        self.assertGreater(wall, 0)
        self.assertLessEqual(wall, direct_wall + TOLERANCE_MS, f"{self.kind}: wall {wall:.2f} ms, direct {direct_wall:.2f} ms")
        self.assertLessEqual(cpu, direct_cpu + TOLERANCE_MS, f"{self.kind}: cpu {cpu:.2f} ms, direct {direct_cpu:.2f} ms")

    def test_peak_memory_is_the_tiny_process_not_the_runner(self):
        _, _, peak, rss, _ = metered(self.factory)
        for name, value in (("peak_mem_mib", peak), ("max_proc_rss_mib", rss)):
            if value is not None:   # a process that runs 0.2 ms is not sampled: no reading is right, the runner's size is not
                self.assertLess(value, 8, f"{self.kind} {name} {value} MiB with a {len(BIG_RUNNER) // 1024} MiB runner")

    def test_the_clock_starts_at_the_exec(self):
        before = time.perf_counter_ns()
        meter = self.factory()
        try:
            child = meter.popen([sys.executable, "-c", "import time;time.sleep(0.3)"], **NULL)
            after = time.perf_counter_ns()
            self.assertGreaterEqual(meter.start_ns(), before)
            self.assertLessEqual(meter.start_ns(), after)
            meter.wait(10)
            self.assertGreater(meter.exit_ns - meter.start_ns(), 0.3e9)
            self.assertEqual(child.returncode, 0)
        finally:
            meter.close()


class CgroupMeasuredFromExec(MeasuredFromExec):
    factory = staticmethod(cgroup_meter)
    kind = "cgroup"

    def test_a_scope_holder_does_not_count(self):
        """A systemd scope has a holder process in the cgroup: its CPU and memory are not the harness's."""
        meter = cgroup_meter()
        holder = subprocess.Popen(["sleep", "infinity"], **NULL)
        try:
            with open(os.path.join(meter.path, "cgroup.procs"), "w") as f:
                f.write(str(holder.pid))
            meter.holder = holder
            result = procio.Batch([TRUE], None, None, meter, timeout=10).run()
            self.assertLess(result["cpu_ms"], 2)
        finally:
            holder.kill()
            holder.wait()
            meter.holder = None
            meter.close()


@unittest.skipUnless(sys.platform.startswith("linux"), "the fork path of the Linux meters")
class ForkedStart(unittest.TestCase):
    """With a preexec_fn (the terminal's controlling tty) the child forks: the clock still starts after exec and its pre-exec CPU is out of the numbers."""

    def test_rusage_meter(self):
        with mock.patch.object(launch, "available", lambda: False):
            walls, cpus = [], []
            for _ in range(10):
                wall, cpu, _, _, meter = metered(cgroup.RusageMeter)
                self.assertFalse(meter.gated)
                walls.append(wall)
                cpus.append(cpu)
            self.assertLess(statistics.median(walls), 5)
            self.assertLess(statistics.median(cpus), 2.5)

    def test_a_preexec_fn_forks_and_runs(self):
        meter = cgroup.RusageMeter()
        try:
            meter.popen([TRUE], preexec_fn=lambda: None, **NULL)
            meter.wait(10)
            self.assertFalse(meter.gated)
            self.assertIsNotNone(meter.start_ns())
        finally:
            meter.close()


@unittest.skipUnless(launch.available(), "needs Linux or macOS")
class LaunchGate(unittest.TestCase):
    def run_gated(self, argv, setup=lambda pid: None, **kwargs):
        kwargs.setdefault("stdin", subprocess.DEVNULL)
        child, stamp = launch.spawn(argv, setup, **kwargs)
        out = b""
        if child.stdout:
            with child.stdout:
                out = child.stdout.read()
        child.wait()
        return child, stamp, out

    def test_the_process_is_set_up_before_it_runs(self):
        seen = []

        def setup(pid):
            seen.append(os.getpid() != pid)
            seen.append(subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout if shutil.which("ps") else open(f"/proc/{pid}/cmdline").read().replace("\0", " "))

        before = time.perf_counter_ns()
        child, stamp, out = self.run_gated([sys.executable, "-c", "print('ran')"], setup, stdout=subprocess.PIPE)
        self.assertEqual(out.strip(), b"ran")
        self.assertIn("-I -S", seen[1])   # while it is gated the process is the shim
        self.assertTrue(before < stamp <= time.perf_counter_ns())
        self.assertEqual(child.returncode, 0)

    def test_the_harness_sees_the_environment_signals_arguments_and_descriptors_of_a_direct_start(self):
        probe = ("import os,signal,sys;print(sorted(os.environ.items()),sys.argv[1:],signal.getsignal(signal.SIGPIPE)==signal.SIG_DFL,"
                 "sorted(int(f) for f in os.listdir('/dev/fd') if f.isdigit() and int(f) > 2) if os.path.isdir('/dev/fd') else None)")
        for env in ({"A": "1", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}, {"A": "1", "LC_CTYPE": "C", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}):
            argv = [sys.executable, "-c", probe, "x y", "z"]
            direct = subprocess.run(argv, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
            _, _, gated = self.run_gated(argv, env=env, stdout=subprocess.PIPE)
            # Python itself adds LC_CTYPE in a C locale, to both; what must match is what the harness gets, so compare the lines without the interpreter's own variables.
            strip = lambda text: [line for line in text.replace("), (", ")\n(").splitlines() if "LC_CTYPE" not in line]
            self.assertEqual(strip(gated.decode()), strip(direct), env)

    def test_the_environment_is_passed_through_untouched(self):
        env = {"A": "1", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        _, _, out = self.run_gated([shutil.which("env")], env=env, stdout=subprocess.PIPE)
        self.assertEqual(sorted(out.decode().splitlines()), sorted(f"{k}={v}" for k, v in env.items()))   # no PWD, no _, no LC_CTYPE

    def test_the_child_is_the_harness_process(self):
        child, _, out = self.run_gated([sys.executable, "-c", "import os;print(os.getpid())"], stdout=subprocess.PIPE)
        self.assertEqual(int(out), child.pid)
        self.assertEqual(child.args[0], sys.executable)

    def test_a_failing_setup_kills_the_process_and_raises(self):
        def setup(pid):
            raise RuntimeError("no cgroup")

        with self.assertRaises(RuntimeError):
            launch.spawn(["sleep", "30"], setup, **NULL)

    def test_a_command_that_cannot_run_raises_as_popen_does(self):
        with self.assertRaises(FileNotFoundError):
            launch.spawn(["/nonexistent/buffon-harness"], lambda pid: None, **NULL)
        with self.assertRaises(FileNotFoundError):
            launch.spawn(["buffon-no-such-harness"], lambda pid: None, **NULL)
        with self.assertRaises(PermissionError):
            launch.spawn(["/etc/hosts"], lambda pid: None, **NULL)
        with self.assertRaises(FileNotFoundError):
            launch.spawn(["./missing"], lambda pid: None, cwd="/tmp", **NULL)


class PerfAttach(unittest.TestCase):
    def test_counters_opened_on_a_gated_process_by_pid(self):
        opened = []

        def opener(event, pid=0, kernel=True, **_):
            opened.append((event, pid))
            r, w = os.pipe()
            os.close(w)
            return r

        session = perfcount.Session(opener=opener)
        self.assertTrue(session.attach(4242))
        self.assertEqual({pid for _, pid in opened}, {4242})
        self.assertEqual(set(session.fds), {name for name, _ in perfcount.EVENTS})
        session.close()

    def test_a_refusal_leaves_no_counters_and_no_descriptors(self):
        def opener(event, pid=0, kernel=True, **_):
            raise OSError(13, "refused")

        session = perfcount.Session(opener=opener)
        self.assertFalse(session.attach(1))
        self.assertEqual(session.fds, {})


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(sys.platform.startswith("linux"), "cgroup.procs")
class JoinProbe(unittest.TestCase):
    """A systemd scope whose cgroup.procs cannot take a process of this runner (a GitHub-hosted runner: the runner's cgroup is under system.slice, the scope under user.slice) is not a meter."""

    def meter_at(self, path):
        return cgroup.CgroupMeter(path, mode="cgroup-systemd")

    def test_a_cgroup_that_takes_the_process_is_joinable(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "cgroup.procs"), "w").close()   # a plain file takes a pid like the kernel's does
            self.assertIsNone(cgroup._join_blocked(self.meter_at(d)))

    def test_a_cgroup_that_refuses_the_process_says_why(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "cgroup.procs"))   # opening it for writing fails, as the kernel's EACCES does for a scope outside the runner's reach
            why = cgroup._join_blocked(self.meter_at(d))
        self.assertIn("cannot be moved into the scope", why)

    def test_a_forced_systemd_meter_names_the_reason_when_the_host_blocks_it(self):
        own = cgroup._own_cgroup()
        with mock.patch.dict(cgroup.SYSTEMD_BLOCKED, {own: "REASON"}), mock.patch.object(cgroup, "_try_direct", lambda root: None), \
                mock.patch.object(cgroup, "CONTAINER", None), mock.patch.object(cgroup.os.path, "exists", lambda p: True), mock.patch.object(cgroup.os.path, "isdir", lambda p: True):
            with self.assertRaisesRegex(RuntimeError, "cgroup-systemd is not available on this host: REASON"):
                cgroup.new_meter("cgroup-systemd")
