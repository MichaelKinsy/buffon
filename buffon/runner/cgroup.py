# SPDX-License-Identifier: MIT
"""Resource meters: one cgroup v2 per measured process tree on Linux, rusage and /proc or ps elsewhere.

Every harness is started inside its own meter. The meter reports CPU time of the
whole tree (harness, its helpers, extension processes), the peak memory the
kernel charged to the tree, and can kill the tree without matching names.

Modes, chosen by `detect()` and recorded in every result:

  cgroup-direct   mkdir a child under a delegated cgroup that has the memory and cpu controllers
                  (a container or pod with its own cgroup namespace, or BUFFON_CGROUP_ROOT)
  cgroup-systemd  a transient scope from `systemd-run --user --scope` holds the tree; needs a user manager
  rusage          wait4 rusage for CPU and the largest process RSS after exit; while the tree runs, /proc
                  (Linux: CPU from each process's CPU-time clock, peak memory the sum of VmHWM) or ps (macOS)
                  samples. No cgroup, so memory is the sum of RSS. A pod's cgroup is read-only, so a pod run uses this.
"""
import mmap
import os
import signal
import struct
import subprocess
import sys
import threading
import time
import uuid

from . import egress, exitwatch, launch, perfcount, textmaps

CGROUP_ROOT = "/sys/fs/cgroup"
PROC_ROOT = "/proc"

# schedstat totals of the meters closed since the last take_sched(): the runner adds them to the sample that used the meters.
SCHED_CLOSED = []

# the executable-mapping records (textmaps.TextMappings) of the meters closed since the last take_text(): the runner adds them to the sample that used the meters.
TEXT_CLOSED = []
TEXT_INTERVAL_S = 0.2   # the mappings are read at most this often: the tree's code does not move every 25 ms

# CPUs every measured process is pinned to (sched_setaffinity before exec, so the whole tree inherits it). None leaves the scheduler free.
# The runner process itself, with the mock endpoint's threads, is pinned elsewhere (runner/pinning.py), so the harness never shares a core with the mock.
PINNED_CPUS = None

FORK_SLACK_KIB = 4096   # what the forked child of the runner may allocate before exec, on top of the runner's resident set (RusageMeter.max_proc_rss_mib)


# Called with a meter as it closes, while its cgroup (or its rusage) still exists: how a telemetry observer reads the totals of one sample's process tree (docs/TELEMETRY.md).
CLOSE_LISTENERS = []


def notify_closing(meter):
    if getattr(meter, "_close_notified", False):
        return
    meter._close_notified = True
    for listener in list(CLOSE_LISTENERS):
        listener(meter)


def set_pinned_cpus(cpus):
    """Pin every process a meter starts from now on to `cpus` (an iterable of CPU numbers), or stop pinning with None."""
    global PINNED_CPUS
    PINNED_CPUS = frozenset(cpus) if cpus else None


PERF = None   # perfcount.probe() of this run: set by the engine; None (tests, tools) counts nothing


def _with_perf(user_pre):
    """(Session or None, preexec_fn): the counter session of the next process and the child hook that opens its counters between fork and exec, then runs the caller's own hook."""
    session = perfcount.start(PERF) if PERF is not None else None
    if session is None:
        return None, user_pre

    def pre():
        session.child_pre()
        if user_pre:
            user_pre()

    return session, pre


def _with_affinity(user_pre=None):
    """A preexec_fn that applies the pin, then the caller's own preexec_fn."""
    cpus = PINNED_CPUS
    if cpus is None:
        return user_pre

    def pre():
        os.sched_setaffinity(0, cpus)
        if user_pre:
            user_pre()

    return pre


def _read(path):
    with open(path) as f:
        return f.read()


def _own_cgroup():
    try:
        text = _read("/proc/self/cgroup")
    except OSError:      # no /proc (macOS)
        return None
    for line in text.splitlines():
        if line.startswith("0::"):
            return CGROUP_ROOT + line[3:]
    return None


def parse_cpu_stat(text):
    """Return {key: int} from cgroup cpu.stat text."""
    out = {}
    for line in text.splitlines():
        key, _, value = line.partition(" ")
        if value.strip().isdigit():
            out[key] = int(value)
    return out


def read_schedstat(pids, proc=None):
    """{tid: (run_ns, wait_ns, slices)} for every thread of pids, from /proc/<pid>/task/<tid>/schedstat: the nanoseconds the thread ran on a CPU,
    the nanoseconds it was runnable but waited on a run queue, and the number of times it ran. A pid or thread that is gone, or a kernel without
    schedstat (CONFIG_SCHED_INFO), contributes nothing."""
    proc = proc or PROC_ROOT
    out = {}
    for pid in pids:
        try:
            tids = os.listdir(os.path.join(proc, str(pid), "task"))
        except OSError:
            continue
        for tid in tids:
            try:
                fields = _read(os.path.join(proc, str(pid), "task", tid, "schedstat")).split()
                out[int(tid)] = (int(fields[0]), int(fields[1]), int(fields[2]))
            except (OSError, IndexError, ValueError):
                continue
    return out


class SchedAccount:
    """Per-thread schedstat counters of one measured tree, accumulated from the meter's samples (every egress.SAMPLE_INTERVAL_S) and its last reading
    at close. A thread keeps the counters of its last reading after it exits, so for a thread that exited the totals miss at most one sample interval
    of its time; run_ms is therefore at most the meter's cpu_ms. A meter counts the started process from its counters at the launch gate (baseline; when the child forked, from
when popen returns), as its cpu.stat and its rusage baseline count it from the harness's exec. A thread id whose counters went backwards was reused by a new thread: the old
    thread's last counters are kept. Recorded beside the metrics, never a metric: wait_ms is how long the tree's threads were runnable but waited
    for a CPU, a per-sample reading of CPU contention."""

    def __init__(self):
        self.last, self.base, self.retired = {}, {}, [0, 0, 0, 0]
        self.lock = threading.Lock()

    def baseline(self, pids, proc=None):
        """Count the threads of pids from their counters now: what a process ran before it joined the meter's cgroup (fork and pre-exec set-up),
        which the cgroup's cpu.stat does not count either."""
        readings = read_schedstat(pids, proc)
        with self.lock:
            for tid, now in readings.items():
                self.base[tid] = self.last[tid] = now

    def observe(self, pids, proc=None):
        readings = read_schedstat(pids, proc)
        with self.lock:
            for tid, now in readings.items():
                before = self.last.get(tid)
                if before is not None and now[0] < before[0]:
                    old = self.base.pop(tid, (0, 0, 0))
                    for i in range(3):
                        self.retired[i] += before[i] - old[i]
                    self.retired[3] += 1
                self.last[tid] = now

    def totals(self):
        """{"run_ms", "wait_ms", "slices", "threads"} over every thread seen, or None when no thread was seen."""
        with self.lock:
            if not self.last:
                return None
            run, wait, slices = (sum(v[i] - self.base.get(tid, (0, 0, 0))[i] for tid, v in self.last.items()) + self.retired[i] for i in range(3))
            return {"run_ms": round(run / 1e6, 3), "wait_ms": round(wait / 1e6, 3), "slices": slices, "threads": len(self.last) + self.retired[3]}


def take_text(mask=None):
    """The file systems of the executable mappings of the meters closed since the last call ({"fs": {fstype: files}, "bad": [paths]}), or None when no meter read any; clears them."""
    closed = [t for t in TEXT_CLOSED if t.files]
    TEXT_CLOSED.clear()
    if not closed:
        return None
    merged = textmaps.TextMappings()
    for t in closed:
        merged.files.update(t.files)
    return merged.totals(mask)


def take_sched():
    """The schedstat totals of the meters closed since the last call, summed ({"run_ms", "wait_ms", "slices", "threads", "meters"}), or None; clears them."""
    closed = [t for t in SCHED_CLOSED if t]
    SCHED_CLOSED.clear()
    if not closed:
        return None
    out = {k: sum(t[k] for t in closed) for k in ("run_ms", "wait_ms", "slices", "threads")}
    out["run_ms"], out["wait_ms"] = round(out["run_ms"], 3), round(out["wait_ms"], 3)
    out["meters"] = len(closed)
    return out


class Meter:
    """Base: start(argv...) -> process, cpu_ms(), peak_mem_mib(), kill(), close()."""

    mode = "none"
    sched = None
    perf_session = None
    exit_ns = None  # time.perf_counter_ns() at the instant the kernel reported the child's exit (see exitwatch), None until wait() saw it
    gated = False  # the last popen() held the process at the launch gate until it was set up (launch.py), else it forked and set the child up in Python
    spawn_ns = None  # time.perf_counter_ns() when the harness started: at its exec (the launch gate's release, launch.py) or, when the child forked, when Popen returned (exec succeeded)

    def start_ns(self):
        """The instant the harness process started (exec done), for the interval clocks of a sample; None before popen()."""
        return self.spawn_ns

    def popen(self, argv, **kwargs):
        raise NotImplementedError

    def _spawn(self, argv, kwargs, gate=None, join=None):
        """Start the harness; returns (Popen, perf Session or None, the child's CPU in ms before its exec or None) and sets spawn_ns to the harness's start.

        Unless the caller has a preexec_fn, the process waits at a gate before its exec (launch.py): `gate(pid)` runs then, from the runner, with the process pinned,
        its counters opened and joined to the cgroup (`join(pid)`) before it runs a single instruction of the harness.
        Otherwise the child is forked and does the same in Python (`join` last, so the cgroup counts only the exec), and the CPU it spent doing so is returned."""
        user_pre = kwargs.pop("preexec_fn", None)
        self.gated = False
        if user_pre is None and launch.available():
            session = perfcount.start(PERF) if PERF is not None else None
            attached = []

            def setup(pid):
                if PINNED_CPUS is not None:
                    os.sched_setaffinity(pid, PINNED_CPUS)
                if gate:
                    gate(pid)
                if join:
                    join(pid)
                if session is not None:
                    attached.append(session.attach(pid))

            child, self.spawn_ns = launch.spawn(argv, setup, **kwargs)
            self.gated = True
            return child, (session if attached and attached[0] else None), None
        session, pre = _with_perf(_with_affinity(user_pre))
        mark = mmap.mmap(-1, 8) if sys.platform.startswith("linux") and (pre is not None or join) else None
        if pre is not None or join:
            inner = pre

            def pre():
                if inner:
                    inner()
                if join:
                    join(os.getpid())
                if mark is not None:   # the forked child's last act writes its CPU time into memory shared with the runner: what it spent before exec is not the harness's
                    struct.pack_into("<Q", mark, 0, time.clock_gettime_ns(time.CLOCK_PROCESS_CPUTIME_ID))

            kwargs["preexec_fn"] = pre
        child = subprocess.Popen(argv, **kwargs)
        self.spawn_ns = time.perf_counter_ns()
        cpu = None
        if mark is not None:
            cpu = struct.unpack_from("<Q", mark, 0)[0] / 1e6
            mark.close()
        return child, (session if session is not None and session.collect() else None), cpu

    def _await_exit(self, timeout):
        """Block until the child has exited, without reaping it, and set exit_ns; raise TimeoutExpired after `timeout` seconds.

        Returns False where the host cannot watch a pid: the caller then polls and exit_ns is the instant a poll saw the exit.
        """
        self.exit_ns = None
        try:
            self.exit_ns = exitwatch.wait_exit(self.child.pid, timeout)
        except TimeoutError:
            raise subprocess.TimeoutExpired(self.child.args, timeout) from None
        return self.exit_ns is not None

    def wait(self, timeout=None):
        """Popen.wait that stamps exit_ns at the kernel's report of the exit instead of at a poll."""
        if self.child.returncode is not None:
            return self.child.returncode
        if not self._await_exit(timeout):
            code = self.child.wait(timeout)
            self.exit_ns = time.perf_counter_ns()
            return code
        return self.child.wait()  # the exit is reported: reaping is immediate

    def perf(self):
        """Instruction and cycle counts of the tree so far ({"instructions", "cycles", "perf_scope"}), or {} where the host gives none: a sample then has no instruction cells and says why in the run facts."""
        return self.perf_session.read() if self.perf_session is not None else {}

    def _close_perf(self):
        """Close the counter descriptors of the tree: each sample opens its own, and a meter that never closed them ran a long session out of descriptors (EMFILE)."""
        if self.perf_session is not None:
            self.perf_session.close()
            self.perf_session = None

    def cpu_ms(self):
        raise NotImplementedError

    def peak_mem_mib(self):
        return None

    def max_proc_rss_mib(self):
        return None

    def pids(self):
        """The pids of the measured tree now (for its current resident set); empty when the meter cannot list them."""
        return []

    def current_pss_mib(self):
        """Proportional set size of the process tree now, in MiB (shared pages divided among their users), or None where /proc has no smaps_rollup."""
        return None

    def snapshot(self):
        """Resource state of the process tree now: processes, threads, open file descriptors, RSS, PSS (MiB) and CPU (ms). None where unsupported."""
        return None

    def kill(self):
        pass

    def close(self):
        pass

    egress = frozenset()


class CgroupMeter(Meter):
    def __init__(self, path, holder=None, mode="cgroup-direct"):
        self.path, self.holder, self.mode = path, holder, mode
        self._last_cpu = 0
        self._cpu_base_usec = 0  # usage_usec of the cgroup before the child joined it: what a systemd scope's holder had used
        self._rss_peak_kib = 0
        self.egress = set()  # non-loopback remotes the tree connected to (see egress.py)
        self._sampling = False
        self.has_memory_peak = os.path.exists(os.path.join(path, "memory.peak"))
        self.sched = SchedAccount()
        self.text, self._text_at = textmaps.TextMappings(PROC_ROOT), 0.0

    def _read_usage_usec(self):
        try:
            return parse_cpu_stat(_read(os.path.join(self.path, "cpu.stat"))).get("usage_usec")
        except OSError:
            return None

    def popen(self, argv, **kwargs):
        """Start the harness in this cgroup, with the clock, the CPU and the memory counted from its exec (see _spawn and launch.py).

        Nothing of the child is in the cgroup before it joins, so the cgroup's usage just before the start (a systemd scope's holder has used a little) is the CPU baseline;
        the cgroup's memory.peak starts empty of the runner's pages for the same reason."""
        usage = self._read_usage_usec()
        if usage is not None:
            self._cpu_base_usec = usage
        procs = os.open(os.path.join(self.path, "cgroup.procs"), os.O_WRONLY | os.O_CLOEXEC)
        try:
            self.child, session, _ = self._spawn(argv, kwargs, gate=lambda pid: self.sched.baseline([pid]), join=lambda pid: os.write(procs, b"%d" % pid))
        finally:
            os.close(procs)
        if session is not None:
            self._close_perf()
            self.perf_session = session
        if not self.gated:
            self.sched.baseline([self.child.pid])
        if not self._sampling:
            self.start_sampler()
        return self.child

    def pids(self):
        try:
            return _read(os.path.join(self.path, "cgroup.procs")).split()
        except OSError:
            return []

    def _sample_rss(self):
        """Sum of per-process peak RSS (VmHWM) over the cgroup's members now; processes that already exited are lost."""
        try:
            pids = _read(os.path.join(self.path, "cgroup.procs")).split()
        except OSError:
            return
        try:
            self.egress |= egress.scan(pids)
        except (OSError, ValueError):
            pass
        # A systemd scope's holder process is in the cgroup but not in the measured tree, and its counters include its own start before it joined.
        self.sched.observe([p for p in pids if self.holder is None or p != str(self.holder.pid)])
        now = time.monotonic()
        if now - self._text_at >= TEXT_INTERVAL_S:
            self._text_at = now
            self.text.observe([p for p in pids if self.holder is None or p != str(self.holder.pid)])
        self._rss_peak_kib = max(self._rss_peak_kib, status_kib(pids, "VmHWM"))

    def start_sampler(self, interval=egress.SAMPLE_INTERVAL_S):
        """Sample the tree's resident set in a thread until close(); the cgroup's memory.peak cannot split anonymous from file pages."""
        self._sampling = True

        def loop():
            while self._sampling:
                self._sample_rss()
                time.sleep(interval)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def max_proc_rss_mib(self):
        self._sample_rss()
        return self._rss_peak_kib / 1024

    def snapshot(self):
        try:
            pids = _read(os.path.join(self.path, "cgroup.procs")).split()
        except OSError:
            return None
        threads = fds = rss_kib = alive = 0
        for pid in pids:
            try:
                status = _read(f"/proc/{pid}/status")
                for line in status.splitlines():
                    if line.startswith("Threads:"):
                        threads += int(line.split()[1])
                    elif line.startswith("VmRSS:"):
                        rss_kib += int(line.split()[1])
                fds += len(os.listdir(f"/proc/{pid}/fd"))
                alive += 1
            except (OSError, ValueError):
                pass
        return {"processes": alive, "threads": threads, "fds": fds, "rss_mib": rss_kib / 1024, "pss_mib": self.current_pss_mib(), "cpu_ms": self.cpu_ms()}

    def current_pss_mib(self):
        try:
            pids = _read(os.path.join(self.path, "cgroup.procs")).split()
        except OSError:
            return None
        total, seen = 0, False
        for pid in pids:
            try:
                for line in _read(f"/proc/{pid}/smaps_rollup").splitlines():
                    if line.startswith("Pss:"):
                        total += int(line.split()[1])
                        seen = True
            except (OSError, ValueError):
                pass
        return total / 1024 if seen else None

    def cpu_ms(self):
        """CPU of the tree since the harness's exec: the cgroup's usage_usec less what it had used when popen() returned."""
        usage = self._read_usage_usec()
        if usage is not None:
            self._last_cpu = usage
        return max(0, self._last_cpu - self._cpu_base_usec) / 1000

    def peak_mem_mib(self):
        try:
            return int(_read(os.path.join(self.path, "memory.peak"))) / 1048576
        except (OSError, ValueError):
            return None

    def pids_peak(self):
        try:
            return int(_read(os.path.join(self.path, "pids.peak")))
        except (OSError, ValueError):
            return None

    def kill(self):
        try:
            with open(os.path.join(self.path, "cgroup.kill"), "w") as f:
                f.write("1")
        except OSError:
            child = getattr(self, "child", None)
            if child and child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except OSError:
                    pass

    def close(self):
        self._sampling = False
        self._sample_rss()
        notify_closing(self)
        egress.OBSERVED |= self.egress
        SCHED_CLOSED.append(self.sched.totals())
        TEXT_CLOSED.append(self.text)
        self.kill()
        self._close_perf()
        if self.holder is not None:
            self.holder.terminate()
            try:
                self.holder.wait(10)
            except subprocess.TimeoutExpired:
                self.holder.kill()
        elif os.path.isdir(self.path):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.rmdir(self.path)
                    break
                except OSError:
                    time.sleep(0.05)


class RusageMeter(Meter):
    """No cgroup: CPU from wait4 after exit, tree samples while running (/proc on Linux, ps on macOS).

    On Linux a sampler thread reads the tree from /proc every egress.SAMPLE_INTERVAL_S, for its resident set and for the egress audit,
    so a run that falls back to this meter is audited too. A process that leaves the tree (a double fork re-parents it) is not seen;
    a cgroup meter or an isolated network namespace has no such gap.
    """

    mode = "rusage"

    def __init__(self):
        self.child = None
        self.rusage = None
        self._cpu_base_ms = 0.0   # the child's CPU when popen() returned: its fork-to-exec work, which wait4's rusage counts
        self._runner_hwm_kib = 0  # the runner's own peak RSS then: see max_proc_rss_mib
        self._peak_sum = 0.0
        self._landed = False      # a tree sample has seen the harness alive with a resident set: without one the all-processes peak is unknown, not zero
        self._hwm_kib = 0  # sum of the members' VmHWM, as CgroupMeter.max_proc_rss_mib, while the tree runs (Linux)
        self.egress = set()
        self._sampling = False
        self.sched = SchedAccount()
        self.text, self._text_at = textmaps.TextMappings(PROC_ROOT), 0.0
        self.mac = perfcount.MacTree() if sys.platform == "darwin" else None   # macOS: instruction counts are sampled with the tree

    def perf(self):
        if self.perf_session is not None:
            return self.perf_session.read()
        return self.mac.read() if self._counting_on_mac() else {}

    def _counting_on_mac(self):
        """Counters are sampled only where the probe found them (`available`): on a host that refused them the sample carries none, not zeros."""
        return self.mac is not None and PERF is not None and bool(PERF.get("available"))

    def popen(self, argv, **kwargs):
        kwargs.setdefault("start_new_session", True)

        def gate(pid):   # the process is blocked before its exec: what it has used is exactly what the harness did not
            self._cpu_base_ms = process_cpu_ms(pid) or perfcount.mac_cpu_ms(pid) or 0.0
            self.sched.baseline([pid])

        self.child, session, forked_cpu = self._spawn(argv, kwargs, gate=gate)
        if forked_cpu is not None:
            self._cpu_base_ms = forked_cpu
        elif not self.gated:   # macOS: a fork of the runner and an exec, no Python in the child, but the copy of a large runner still costs the child up to a ms; what it has used now is a bound
            self._cpu_base_ms = perfcount.mac_cpu_ms(self.child.pid) or 0.0
        if not self.gated:
            self.sched.baseline([self.child.pid])
        if sys.platform.startswith("linux"):
            self._runner_hwm_kib = status_kib([os.getpid()], "VmHWM")
        if session is not None:
            self._close_perf()
            self.perf_session = session
        if (os.path.isdir("/proc/self") or egress.lsof_path()) and not self._sampling:
            self._sampling = True
            self._thread = threading.Thread(target=self._sample_loop, daemon=True)
            self._thread.start()
        return self.child

    def pids(self):
        if self.child is None or self.child.returncode is not None:
            return []
        return list(_tree_rows(self.child.pid))

    def _sample(self):
        rows = _tree_rows(self.child.pid)
        members = set(rows)
        if self._counting_on_mac():
            self.mac.observe(members)
        now = time.monotonic()
        if now - self._text_at >= TEXT_INTERVAL_S:
            self._text_at = now
            self.text.observe(members)
        self._note_rss(sum(rows[p][1] for p in members if p in rows))
        self._hwm_kib = max(self._hwm_kib, status_kib(members, "VmHWM"))
        try:
            self.egress |= egress.scan(members)
        except (OSError, ValueError):
            pass
        self.sched.observe(members)

    def _note_rss(self, kib):
        """Fold one reading of the tree's summed resident set (KiB) into the peak. A live process always has pages resident, so a reading of 0 is a tree that was already gone: no sample."""
        if kib > 0:
            self._landed = True
            self._peak_sum = max(self._peak_sum, kib)

    def _sample_loop(self):
        # returncode, not poll(): poll() would reap the child and lose the rusage that wait() collects with wait4.
        while self._sampling and self.child.returncode is None:
            self._sample()
            time.sleep(egress.sample_interval())

    def close(self):
        if self._sampling:
            self._sampling = False
            self._thread.join(1)
            if self.child is not None and self.child.returncode is None:
                self._sample()
        notify_closing(self)
        egress.OBSERVED |= self.egress
        SCHED_CLOSED.append(self.sched.totals())
        TEXT_CLOSED.append(self.text)
        self.kill()
        self._close_perf()

    def wait(self, timeout=None):
        """wait4 replacement for Popen.wait so the rusage of the tree is kept."""
        if self.child.returncode is not None:  # already reaped, by an earlier wait() or by Popen.poll()
            return self.child.returncode
        deadline = None if timeout is None else time.monotonic() + timeout
        watched = self._await_exit(timeout)
        while True:
            try:
                # Once the exit is reported the zombie is there to reap: block in wait4 (the macOS report comes just before the process turns into a zombie).
                pid, status, usage = os.wait4(self.child.pid, 0 if watched else os.WNOHANG)
            except ChildProcessError:  # Popen reaped it in another thread; its rusage is gone
                return self.child.wait(0)
            if pid:
                self.child.returncode = os.waitstatus_to_exitcode(status)
                self.rusage = usage
                if not watched:
                    self.exit_ns = time.perf_counter_ns()
                return self.child.returncode
            if deadline is not None and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(self.child.args, timeout)
            time.sleep(0.005)

    def _tree(self):
        return tree_usage(self.child.pid)

    def cpu_ms(self):
        """CPU of the tree since the harness's exec: wait4's rusage (or the live tree) less what the child used between fork and exec."""
        if self.rusage is not None:
            return max(0.0, (self.rusage.ru_utime + self.rusage.ru_stime) * 1000 - self._cpu_base_ms)
        cpu, rss = self._tree()
        self._note_rss(rss)
        return max(0.0, cpu - self._cpu_base_ms)

    def peak_mem_mib(self):
        """The largest sum of the tree's resident sets over the samples taken, in MiB; None when no sample saw the tree alive.

        A tree sample (`ps` on macOS) takes tens to hundreds of ms on a busy host, so a short command can exit before the first one lands, or after a first one that caught it before it
        had touched its pages. That read as a footprint near zero (an OpenCode start-up cell once came out 2121 times below the reference). No sample is now no value, and on macOS the
        peak is never below the largest single process's `ru_maxrss` from wait4: the sum over all processes cannot be smaller than its largest member."""
        if self.rusage is None:
            self._note_rss(self._tree()[1])
        if not self._landed:
            return None
        peak = self._peak_sum
        if self.rusage is not None and sys.platform == "darwin":
            peak = max(peak, self.rusage.ru_maxrss / 1024)   # macOS counts ru_maxrss in bytes
        return peak / 1024

    def max_proc_rss_mib(self):
        if self.rusage is None:
            # While the tree runs: the sum of its members' VmHWM, which is what a cgroup meter reports. No /proc, no value.
            if self.child is None or not os.path.isdir("/proc/self"):
                return None
            if self.child.returncode is None:
                self._sample()
            return self._hwm_kib / 1024 if self._hwm_kib else None
        if sys.platform == "darwin":
            return self.rusage.ru_maxrss / 1048576
        # Linux: a child forked from the runner has the runner's resident set at exec time in its ru_maxrss (exec folds the old address space's peak into the process),
        # so a harness smaller than the runner reads as big as the runner. A value at or below the runner's own peak (plus what the forked child allocates before exec) says nothing
        # about the harness; then the sampled VmHWM of the tree is the best reading there is, and none is no value.
        kib = self.rusage.ru_maxrss
        if kib > self._runner_hwm_kib + FORK_SLACK_KIB:
            return kib / 1024
        return self._hwm_kib / 1024 if self._hwm_kib else None

    def kill(self):
        if self.child and self.child.poll() is None:
            try:
                os.killpg(self.child.pid, signal.SIGKILL)
            except OSError:
                pass


def parse_ps(text):
    """Parse `ps -A -o pid=,ppid=,rss=,time=` (macOS cputime M:SS.cc or H:MM:SS) into {pid: (ppid, rss_kib, cpu_ms)}."""
    rows = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        pid, ppid, rss, cpu = parts
        seconds = 0.0
        for piece in cpu.replace("-", ":").split(":"):
            seconds = seconds * 60 + float(piece)
        rows[int(pid)] = (int(ppid), int(rss), seconds * 1000)
    return rows


def _proc_rows():
    """{pid: (ppid, rss_kib, cpu_ms)} for every process, from /proc (Linux) or ps (elsewhere)."""
    rows = {}
    if os.path.isdir("/proc/self"):
        tick = os.sysconf("SC_CLK_TCK")
        page = os.sysconf("SC_PAGE_SIZE") // 1024
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                rows[int(name)] = _stat_row(name, tick, page)
            except (OSError, IndexError, ValueError):
                continue
    else:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss=,time="], capture_output=True, text=True, timeout=10).stdout
        rows = parse_ps(out)
    return rows


def _members(rows, root):
    """`root` and its descendants in `rows`."""
    members, grew = {root}, True
    while grew:
        grew = False
        for pid, (ppid, _, _) in rows.items():
            if ppid in members and pid not in members:
                members.add(pid)
                grew = True
    return members


def _stat_row(pid, tick, page):
    fields = _read(f"/proc/{pid}/stat").rsplit(")", 1)[1].split()
    cpu = process_cpu_ms(int(pid))
    if cpu is None:
        cpu = (int(fields[11]) + int(fields[12])) * 1000 / tick
    return int(fields[1]), int(fields[21]) * page, cpu


def process_cpu_ms(pid):
    """The CPU time of process pid (all its threads, live and exited) in ms, from its CPU-time clock, which counts
    nanoseconds; /proc/<pid>/stat counts clock ticks (10 ms), too coarse for a turn's CPU. None when the clock cannot be
    read (the process exited, or not Linux). The clock id is Linux's MAKE_PROCESS_CPUCLOCK(pid, CPUCLOCK_SCHED), what
    glibc's clock_getcpuclockid returns."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        return time.clock_gettime_ns(((~pid) << 3) | 2) / 1e6
    except OSError:
        return None


def status_kib(pids, field):
    """The sum of one /proc/<pid>/status field (VmHWM, VmRSS) in KiB over pids; a pid that is gone counts 0."""
    total = 0
    for pid in pids:
        try:
            for line in _read(f"/proc/{pid}/status").splitlines():
                if line.startswith(field + ":"):
                    total += int(line.split()[1])
        except (OSError, ValueError):
            pass
    return total


def _tree_rows(root):
    """{pid: (ppid, rss_kib, cpu_ms)} for `root` and its descendants. On Linux it follows /proc/<pid>/task/<tid>/children, so the cost is the
    size of the tree, not of the host's process table (a full /proc scan takes hundreds of milliseconds on a busy host)."""
    if not os.path.exists(f"/proc/{os.getpid()}/task/{os.getpid()}/children"):
        rows = _proc_rows()
        return {p: rows[p] for p in _members(rows, root) if p in rows}
    tick, page = os.sysconf("SC_CLK_TCK"), os.sysconf("SC_PAGE_SIZE") // 1024
    rows, queue = {}, [root]
    while queue:
        pid = queue.pop()
        if pid in rows:
            continue
        try:
            rows[pid] = _stat_row(pid, tick, page)
            for tid in os.listdir(f"/proc/{pid}/task"):
                queue.extend(int(c) for c in _read(f"/proc/{pid}/task/{tid}/children").split())
        except (OSError, IndexError, ValueError):
            continue
    return rows


def tree_usage(root):
    """(cpu_ms, rss_kib) summed over `root` and its descendants, now."""
    rows = _tree_rows(root)
    members = set(rows)
    cpu = sum(rows[p][2] for p in members if p in rows)
    rss = sum(rows[p][1] for p in members if p in rows)
    return cpu, rss


def _controllers(path):
    try:
        return set(_read(os.path.join(path, "cgroup.controllers")).split())
    except OSError:
        return set()


def _try_direct(root):
    if not root or not os.path.isdir(root):
        return None
    path = os.path.join(root, f"buffon-{uuid.uuid4().hex[:12]}")
    try:
        os.mkdir(path)
    except OSError:
        return None
    meter = CgroupMeter(path)
    if not meter.has_memory_peak:
        os.rmdir(path)
        return None
    return meter


SYSTEMD_BLOCKED = {}   # the runner's own cgroup -> why a systemd scope cannot hold the harness from there (see _join_blocked); the probe is not repeated for every meter


def _join_blocked(meter):
    """Why a process of this runner cannot be moved into the meter's cgroup, or None when it can.

    cgroup v2 lets a process be moved only by a writer who can write the cgroup.procs of the destination and of the closest common ancestor of the source and the destination.
    A systemd user scope is owned by the user, but it sits under user@UID.service: a runner that lives elsewhere (a job started by a system service, as on a GitHub-hosted runner)
    has the root cgroup as the common ancestor, and every join fails with EACCES even though cgroup.procs of the scope is writable. A probe child of the runner is moved in to find out."""
    probe = subprocess.Popen(["sleep", "infinity"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(os.path.join(meter.path, "cgroup.procs"), "w") as f:
            f.write(str(probe.pid))
    except OSError as error:
        return f"a process of this runner (cgroup {_own_cgroup()}) cannot be moved into the scope {meter.path}: {error.strerror or error}"
    finally:
        probe.kill()
        probe.wait()
    return None


def _try_systemd():
    own = _own_cgroup()
    if own in SYSTEMD_BLOCKED:
        return None
    if not os.path.exists("/usr/bin/systemd-run") and not any(os.access(os.path.join(p, "systemd-run"), os.X_OK) for p in os.environ.get("PATH", "").split(os.pathsep)):
        return None
    unit = f"buffon-{uuid.uuid4().hex[:12]}"
    holder = subprocess.Popen(["systemd-run", "--user", "--scope", "--quiet", "--collect", f"--unit={unit}", "-p", "MemoryAccounting=yes", "-p", "CPUAccounting=yes",
                               "-p", "TasksAccounting=yes", "sleep", "infinity"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    path = None
    while time.monotonic() < deadline and holder.poll() is None:
        try:
            for line in _read(f"/proc/{holder.pid}/cgroup").splitlines():
                if line.startswith("0::") and line.endswith(f"{unit}.scope"):
                    path = CGROUP_ROOT + line[3:]
        except OSError:
            pass
        if path:
            break
        time.sleep(0.01)
    if not path:
        holder.kill()
        return None
    meter = CgroupMeter(path, holder, "cgroup-systemd")
    blocked = None if meter.has_memory_peak and os.access(os.path.join(path, "cgroup.procs"), os.W_OK) else "no memory.peak or no writable cgroup.procs"
    blocked = blocked or _join_blocked(meter)
    if blocked:
        SYSTEMD_BLOCKED[own] = blocked   # a meter that never held a harness is not closed with close(): it would add an empty reading to what the next sample reports
        holder.terminate()
        holder.wait(10)
        return None
    return meter


def available_mode():
    """The mode `new_meter()` will use on this host, probed once."""
    meter = new_meter()
    mode = meter.mode
    meter.close()
    return mode


CONTAINER = None   # a container.ContainerConfig when the run is in the container envelope


def new_meter(force=None):
    """A fresh meter for one process tree. `force` or BUFFON_METER pins the mode."""
    if CONTAINER is not None:
        from .container import ContainerMeter
        return ContainerMeter(CONTAINER)
    force = force or os.environ.get("BUFFON_METER")
    if force != "rusage" and sys.platform.startswith("linux") and os.path.isdir(CGROUP_ROOT) and os.path.exists(os.path.join(CGROUP_ROOT, "cgroup.controllers")):
        if force in (None, "cgroup-direct"):
            meter = _try_direct(os.environ.get("BUFFON_CGROUP_ROOT") or _own_cgroup())
            if meter:
                return meter
        if force in (None, "cgroup-systemd"):
            meter = _try_systemd()
            if meter:
                return meter
        if force:
            why = SYSTEMD_BLOCKED.get(_own_cgroup()) if force == "cgroup-systemd" else None
            raise RuntimeError(f"meter {force} is not available on this host" + (f": {why}" if why else ""))
    return RusageMeter()
