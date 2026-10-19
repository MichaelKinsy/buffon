# SPDX-License-Identifier: Apache-2.0
"""Strictly serial, quiet-host measurement (docs/METHODOLOGY.md, "Serial execution on the host").

`HostLock` makes one buffon measurement at a time per host (an exclusive flock) and refuses to start while another benchmark tool holds a lock file the site names; `QuietGate`
checks, before every sample, that the pinned CPUs are idle and the host is not overloaded, waits when it is not, and returns the readings that go into the sample's record."""
import fcntl
import os
import tempfile
import time

from . import cgroup, cpumon

def default_lock():
    """One lock per host, not per user: `BUFFON_LOCK_FILE`, else /run/lock (host-global, world-writable on the common distributions), else /var/tmp. A host with neither writable (a pod
    whose root file system is read-only) tries /tmp, still host-wide, and then has only its scratch directory: TMPDIR, the one writable place the pod's spec names, and last the platform's
    temporary directory. TMPDIR comes after every host-wide directory: it is per user, and a lock there does not keep another user's run out (the run records `lock_file`)."""
    explicit = os.environ.get("BUFFON_LOCK_FILE")
    if explicit:
        return explicit
    try:
        platform_tmp = tempfile.gettempdir()
    except OSError:   # no temporary directory the platform can use: the lock then names a path the first measurement refuses with a message
        platform_tmp = ""
    for directory in ("/run/lock", "/var/tmp", "/tmp", os.environ.get("TMPDIR") or "", platform_tmp):   # /tmp is host-wide; TMPDIR (per user) only after it
        if directory and os.path.isdir(directory) and os.access(directory, os.W_OK | os.X_OK):
            return os.path.join(directory, "buffon.lock")
    return "/tmp/buffon.lock"


DEFAULT_LOCK = default_lock()


class LockHeld(Exception):
    pass


def _open_paths():
    """The paths of this process's open file descriptors: /proc/self/fd on Linux, fcntl F_GETPATH on macOS (which has no /proc)."""
    try:
        for fd in os.listdir("/proc/self/fd"):
            try:
                yield os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                continue
        return
    except OSError:
        pass
    getpath = getattr(fcntl, "F_GETPATH", None)
    if getpath is None:
        return
    for fd in range(1024):
        try:
            raw = fcntl.fcntl(fd, getpath, b"\0" * 1024)
        except OSError:
            continue
        yield os.fsdecode(raw.split(b"\0", 1)[0])


def _inherited(path):
    """True when this process already holds `path` through a file descriptor it inherited (it runs under the tool that owns that lock, for example a bench-slot wrapper)."""
    real = os.path.realpath(path)
    return any(os.path.realpath(held) == real for held in _open_paths())


class HostLock:
    """Holds Buffon's own exclusive lock for the life of the run; `foreign` lock files must be free (or inherited from the tool that wraps this run). A session in a slot
    (buffon/runner/slots.py) holds its slot's lock as `own` and the host-wide lock as `shared`: any number of slots run together, and neither starts while a serial run holds the host lock."""

    def __init__(self, own=DEFAULT_LOCK, foreign=(), shared=()):
        self.own, self.foreign, self.shared, self.fds = own, list(foreign), list(shared), []

    def holder(self):
        """What the lock file says about its holder (this process, after __enter__)."""
        try:
            with open(self.own) as f:
                return f.read().strip()
        except OSError:
            return None

    def __enter__(self):
        for path, mine, share in [(self.own, True, False)] + [(p, False, True) for p in self.shared] + [(p, False, False) for p in self.foreign]:
            if not mine and not share and _inherited(path):
                continue  # we are the lock holder's child: the slot is ours
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            try:
                fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
            except PermissionError:
                self.__exit__()
                raise LockHeld(f"{path} exists and this user cannot open it; a lock shared by every user of the host must be mode 0666") from None
            except OSError as error:   # a read-only file system, no space: say which file and how to move it
                self.__exit__()
                raise LockHeld(f"cannot create the lock file {path}: {error.strerror or error}; set BUFFON_LOCK_FILE (or --lock-file) to a path on a writable directory") from None
            try:
                os.fchmod(fd, 0o666)   # another user's run must be able to open it to be refused by it
            except OSError:
                pass
            try:
                fcntl.flock(fd, (fcntl.LOCK_SH if share else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                self.__exit__()
                raise LockHeld((f"{path} is held by a serial run on this host, which excludes sessions in slots; this run does not start" if share else
                                f"{path} is held by another benchmark or run on this host; measurements are serial, so this run does not start")) from None
            if mine:
                os.ftruncate(fd, 0)
                os.write(fd, f"pid {os.getpid()} user {os.environ.get('USER') or os.getuid()} since {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n".encode())
            self.fds.append(fd)
        return self

    def __exit__(self, *_):
        for fd in self.fds:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except OSError:
                pass
        self.fds = []


def runnable_now(path="/proc/loadavg"):
    """(1-minute load average, currently runnable tasks including this one): the whole host, recorded but never gated on."""
    try:
        with open(path) as f:
            parts = f.read().split()
    except OSError:      # no /proc (macOS): the load average from the C library; the runnable-task count has no portable source
        return os.getloadavg()[0], None
    return float(parts[0]), int(parts[3].split("/")[0])


def runnable_on(cpus, proc="/proc", me=None):
    """Number of threads (other than this process's own) in state R whose last CPU is one of `cpus`; None when /proc cannot be read."""
    found = foreign_on(cpus, proc, me)
    return None if found is None else len(found)


PF_KTHREAD = 0x00200000   # task flag of a kernel thread (include/linux/sched.h)


class Threads(list):
    """The user-space threads found runnable on the pinned CPUs; `kernel` holds the kernel threads that were runnable there too and were left out (per-CPU workers of the kernel and of the host's security
    and tracing agents: bpfrb/N, evdefer/N, kworker/N, ksoftirqd/N). They cannot be moved off the bench CPUs, and the gate does not wait for them; each reading records how many were ignored."""
    kernel = ()


def is_kernel_thread(pid, ppid, flags):
    """A kernel thread: PF_KTHREAD is set, or it is kthreadd (pid 2) or a child of it."""
    return bool(flags & PF_KTHREAD) or pid == 2 or ppid == 2


def foreign_on(cpus, proc="/proc", me=None):
    """The user-space threads (other than this process's own) in state R whose last CPU is one of `cpus`: [{pid, tid, comm, cpu}]; None when /proc cannot be read. Kernel threads are not in the list: they
    are in its `.kernel` attribute. A gate that waits names who it waits for."""
    me = os.getpid() if me is None else me
    wanted, found, kernel = set(cpus), Threads(), []
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return None
    for pid in pids:
        if int(pid) == me:
            continue
        try:
            tids = os.listdir(f"{proc}/{pid}/task")
        except OSError:
            continue
        for tid in tids:
            try:
                with open(f"{proc}/{pid}/task/{tid}/stat") as f:
                    text = f.read()
            except OSError:
                continue
            rest = text[text.rindex(")") + 2:].split()   # state is rest[0]; processor is field 39 of the full line, rest[36]
            if len(rest) > 36 and rest[0] == "R" and int(rest[36]) in wanted:
                thread = {"pid": int(pid), "tid": int(tid), "comm": text[text.index("(") + 1:text.rindex(")")], "cpu": int(rest[36])}
                if is_kernel_thread(int(pid), int(rest[1]), int(rest[6])):
                    kernel.append(thread)
                else:
                    found.append(thread)
    found.kernel = kernel
    return found


def psi_some_avg10(path):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("some"):
                    return float(dict(kv.split("=") for kv in line.split()[1:])["avg10"])
    except (OSError, KeyError, ValueError):
        pass
    return None


def cgroup_throttled(cgroup_dir):
    try:
        with open(os.path.join(cgroup_dir, "cpu.stat")) as f:
            return cgroup.parse_cpu_stat(f.read()).get("nr_throttled")
    except OSError:
        return None


class QuietGate:
    """The check before every sample, on the benchmark's own CPU set (the pinned CPUs), not on the whole host: another lane's load elsewhere does not matter,
    a task on these CPUs does. Readings (all recorded in the sample): pinned_busy (largest per-CPU busy fraction over `window_s`), pinned_iowait (recorded, never gated: the
    kernel documents it as unreliable, R9) and pinned_steal (largest per-CPU share), cpuset_runnable (other runnable threads whose last CPU is pinned), throttled (cgroup nr_throttled increase over the window, None without
    a cgroup), psi_cpu_some_avg10 (the runner's cgroup, else the system), and host_load1 / host_runnable (whole host, for the record only)."""

    def __init__(self, cpus, max_busy=0.10, timeout_s=300.0, max_runnable=0, window_s=0.25, read=cpumon.read_stat, load=runnable_now, sleep=time.sleep, clock=time.monotonic,
                 max_steal=0.02, max_psi=10.0, detail=cpumon.read_detail, runnable=runnable_on, psi=None, throttled=None, foreign=foreign_on):
        self.cpus, self.max_busy, self.timeout_s, self.max_runnable, self.window_s = list(cpus), max_busy, timeout_s, max_runnable, window_s
        self.max_steal, self.max_psi = max_steal, max_psi
        self.read, self.load, self.sleep, self.clock = read, load, sleep, clock
        self.detail, self.runnable, self.foreign = detail, runnable, foreign
        self.seen = {}   # (pid, comm) -> [number of checks it was runnable on the pinned CPUs, cpus]
        self.kseen = {}  # kernel thread name (per-CPU workers grouped: bpfrb/*) -> [checks it was runnable on the pinned CPUs and ignored, cpus]
        own = cgroup._own_cgroup() if hasattr(cgroup, "_own_cgroup") else None
        self.psi = psi or (lambda: psi_some_avg10(os.path.join(own, "cpu.pressure")) if own and os.path.exists(os.path.join(own, "cpu.pressure")) else psi_some_avg10("/proc/pressure/cpu"))
        self.throttled = throttled or ((lambda: cgroup_throttled(own)) if own else (lambda: None))
        self.waits = 0

    def reading(self):
        busy = iowait = steal = 0.0
        throttled = None
        if self.cpus:
            before, detail_before, thr_before = self.read(), self.detail(), self.throttled()
            self.sleep(self.window_s)
            after, detail_after, thr_after = self.read(), self.detail(), self.throttled()
            fractions = cpumon.busy_fractions(before, after, self.cpus)
            busy = max(fractions.values()) if fractions else 0.0
            iowait, steal = cpumon.share(detail_before, detail_after, self.cpus, 1), cpumon.share(detail_before, detail_after, self.cpus, 2)
            if thr_before is not None and thr_after is not None:
                throttled = thr_after - thr_before
        load1, runnable = self.load()
        found, kernel = None, ()
        if not self.cpus:
            count = 0
        elif self.runnable is runnable_on and self.foreign is foreign_on:   # one /proc walk, not two: on a host with many threads a walk takes about a second
            found = foreign_on(self.cpus)
            count = None if found is None else len(found)
            kernel = getattr(found, "kernel", ())
        else:
            count = self.runnable(self.cpus)
        if count and self.cpus:
            now = {}
            for t in (found if found is not None else self.foreign(self.cpus)) or []:   # one count per check, however many of a process's threads were runnable in it
                now.setdefault((t["pid"], t["comm"]), set()).add(t["cpu"])
            for key, cpus in now.items():
                entry = self.seen.setdefault(key, [0, set()])
                entry[0] += 1
                entry[1] |= cpus
        if kernel:
            now = {}
            for t in kernel:
                now.setdefault(t["comm"].split("/")[0] + "/*" if "/" in t["comm"] else t["comm"], set()).add(t["cpu"])
            for name, cpus in now.items():
                entry = self.kseen.setdefault(name, [0, set()])
                entry[0] += 1
                entry[1] |= cpus
        return {"cpuset_kthreads": None if found is None else len(kernel), "host_load1": load1, "host_runnable": runnable, "pinned_busy": round(busy, 4), "pinned_iowait": round(iowait, 4), "pinned_steal": round(steal, 4),
                "cpuset_runnable": count, "throttled": throttled, "psi_cpu_some_avg10": self.psi()}

    def reasons(self, r):
        """Why a reading is not quiet (empty list: quiet). Unavailable readings (None) never block."""
        why = []
        if r["pinned_busy"] > self.max_busy:
            why.append(f"pinned CPUs {r['pinned_busy']:.0%} busy")
        if r["pinned_steal"] > self.max_steal:
            why.append(f"steal {r['pinned_steal']:.0%}")
        if r["cpuset_runnable"] is not None and r["cpuset_runnable"] > self.max_runnable:
            why.append(f"{r['cpuset_runnable']} other runnable threads on the pinned CPUs")
        if r["throttled"]:
            why.append(f"cgroup throttled {r['throttled']} times")
        if r["psi_cpu_some_avg10"] is not None and r["psi_cpu_some_avg10"] > self.max_psi:
            why.append(f"CPU pressure {r['psi_cpu_some_avg10']:.1f}% (avg10)")
        return why

    def quiet(self, r):
        return not self.reasons(r)

    def wait(self):
        """Block until the pinned CPUs are quiet or the timeout passes. Returns (readings of the last check, waited_ms, ok); the readings are recorded in the sample either way."""
        t0 = self.clock()
        self.seen, self.kseen = {}, {}
        r = self.reading()
        checks = 1
        while not self.quiet(r):
            if self.clock() - t0 >= self.timeout_s:
                return self.named(dict(r, quiet_checks=checks)), round((self.clock() - t0) * 1000), False
            self.sleep(1.0)
            r = self.reading()
            checks += 1
        r = dict(r, quiet_checks=checks)
        waited = round((self.clock() - t0) * 1000)
        if waited > 1000 * self.window_s * 4:
            self.waits += 1
        return self.named(r), waited, True

    def named(self, r):
        """The reading with `foreign_threads` added when anything else was runnable on the pinned CPUs during this wait: the five seen most, as one string `comm[pid] xN on cpu C,...` (raw samples hold scalars; a thread name is not a command line: no path or argument is recorded)."""
        if self.kseen:
            ktop = sorted(self.kseen.items(), key=lambda kv: (-kv[1][0], kv[0]))[:5]
            r = dict(r, ignored_kthreads="; ".join(f"{name} x{n} on cpu {','.join(str(c) for c in sorted(cpus))}" for name, (n, cpus) in ktop))
        if not self.seen:
            return r
        top = sorted(self.seen.items(), key=lambda kv: (-kv[1][0], kv[0]))[:5]
        return dict(r, foreign_threads="; ".join(f"{comm}[{pid}] x{n} on cpu {','.join(str(c) for c in sorted(cpus))}" for (pid, comm), (n, cpus) in top))
