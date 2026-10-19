# SPDX-License-Identifier: Apache-2.0
"""Instruction and cycle counts of a measured process tree (M1: instructions are the headline CPU metric; CPU time and wall time sit beside them, never mixed in one row).

Linux: `perf_event_open` (no `perf` binary). A counter is opened *inside the child*, between fork and exec, with `inherit` (it follows every thread and process the tree creates) and
`enable_on_exec` (it starts counting at the exec of the harness, so Buffon's own fork work is never counted); its file descriptor is passed to the runner over a socket pair, and the
runner reads it while the tree runs and after it exits. User and kernel instructions are counted when the host allows it (`perf_event_paranoid` <= 1 or CAP_PERFMON); at paranoid 2 only user-space
instructions are counted and every sample says so (`perf_scope`). A host that allows neither (`perf_event_paranoid` > 2, a seccomp profile that blocks the syscall) has no instruction counts: the
samples carry none, the run facts say why, and the report names CPU time as the headline for that run.

macOS: `proc_pid_rusage` (`ri_instructions`, `ri_cycles`) of every process in the tree, sampled with the meter's own tree sampler; the sum of each process's last reading. A process that exits
between two samples loses its last interval (`perf_scope` is `sampled`).

Nothing here changes how a process runs: the counters only observe."""
import ctypes
import os
import socket
import struct
import sys

PERF_TYPE_HARDWARE = 0
HW_CPU_CYCLES, HW_INSTRUCTIONS = 0, 1
READ_FORMAT_TIMES = 1 | 2          # TOTAL_TIME_ENABLED | TOTAL_TIME_RUNNING
FLAG_DISABLED, FLAG_INHERIT, FLAG_EXCLUDE_USER, FLAG_EXCLUDE_KERNEL, FLAG_EXCLUDE_HV, FLAG_ENABLE_ON_EXEC = 1 << 0, 1 << 1, 1 << 4, 1 << 5, 1 << 6, 1 << 12
PERF_FLAG_FD_CLOEXEC = 8
ATTR_FORMAT = "<IIQQQQQIIQQQQIiQIHH"   # struct perf_event_attr up to PERF_ATTR_SIZE_VER5
ATTR_SIZE = struct.calcsize(ATTR_FORMAT)
SYSCALL_NUMBERS = {"x86_64": 298, "aarch64": 241, "arm64": 241, "riscv64": 241}
EVENTS = (("instructions", HW_INSTRUCTIONS), ("cycles", HW_CPU_CYCLES))
PARANOID_FILE = "/proc/sys/kernel/perf_event_paranoid"

# macOS: struct rusage_info_v4 is a 16-byte uuid followed by uint64 fields; ri_phys_footprint is the 8th and ri_instructions and ri_cycles the 30th and 31st (<sys/resource.h>).
MAC_RUSAGE_INFO_V4 = 4
MAC_RUSAGE_SIZE = 16 + 8 * 40
MAC_OFFSETS = {"phys_footprint": 16 + 8 * 7, "instructions": 16 + 8 * 29, "cycles": 16 + 8 * 30}
MAC_TIME_OFFSETS = (16, 16 + 8)   # ri_user_time and ri_system_time, in Mach absolute-time ticks


def attr_bytes(event, kernel=True, inherit=True, enable_on_exec=True):
    """A packed perf_event_attr counting hardware `event` for the task and everything it creates."""
    flags = FLAG_DISABLED * enable_on_exec | FLAG_INHERIT * inherit | FLAG_ENABLE_ON_EXEC * enable_on_exec
    if not kernel:
        flags |= FLAG_EXCLUDE_KERNEL | FLAG_EXCLUDE_HV
    return struct.pack(ATTR_FORMAT, PERF_TYPE_HARDWARE, ATTR_SIZE, event, 0, 0, READ_FORMAT_TIMES, flags, *([0] * 12))


def scale(value, enabled, running):
    """(count, multiplexed): the counter's value scaled up when the kernel time-shared the hardware counter (running < enabled); 0 when it never ran."""
    if not running:
        return 0, bool(enabled)
    return (int(round(value * enabled / running)), enabled > running) if running < enabled else (int(value), False)


def parse_read(data):
    """(value, enabled, running) from a counter's read with READ_FORMAT_TIMES."""
    if len(data) < 24:
        raise OSError(f"short perf read ({len(data)} bytes)")
    return struct.unpack("<QQQ", data[:24])


def _syscall():
    machine = os.uname().machine
    number = SYSCALL_NUMBERS.get(machine)
    if number is None or not sys.platform.startswith("linux"):
        return None, None
    libc = ctypes.CDLL(None, use_errno=True)
    return libc.syscall, number


def perf_open(event, pid=0, kernel=True, inherit=True, enable_on_exec=True, syscall=None):
    """The counter's file descriptor; OSError (errno from the kernel) when the host refuses."""
    call, number = syscall or _syscall()
    if call is None:
        raise OSError("perf_event_open is not available on this platform")
    attr = ctypes.create_string_buffer(attr_bytes(event, kernel, inherit, enable_on_exec), ATTR_SIZE)
    fd = call(number, attr, pid, -1, -1, PERF_FLAG_FD_CLOEXEC)
    if fd < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return fd


def paranoid():
    try:
        with open(PARANOID_FILE) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def probe(opener=perf_open):
    """What this host allows, once per run: {"available", "scope", "paranoid", "reason"}. Tries user+kernel, then user only."""
    out = {"available": False, "scope": None, "paranoid": paranoid(), "reason": None}
    if sys.platform == "darwin":
        out.update(available=True, scope="sampled", reason=None)
        return out
    if not sys.platform.startswith("linux"):
        out["reason"] = f"no instruction counter on {sys.platform}"
        return out
    last = None
    for kernel, scope in ((True, "user+kernel"), (False, "user")):
        try:
            fd = opener(HW_INSTRUCTIONS, pid=0, kernel=kernel, inherit=False, enable_on_exec=False)
        except OSError as error:
            last = error
            continue
        os.close(fd)
        out.update(available=True, scope=scope)
        if scope == "user":
            out["reason"] = "kernel instructions are not counted: perf_event_paranoid > 1 and no CAP_PERFMON (counts are user-space instructions)"
        return out
    out["reason"] = (f"perf_event_open refused ({last}): perf_event_paranoid is {out['paranoid']}; instruction counts are unavailable and CPU time is the headline for this run" if last else "perf_event_open is not available")
    return out


class Session:
    """The counters of one process tree. `child_pre` runs in the forked child before exec; `collect` runs in the runner after Popen returns."""

    def __init__(self, kernel=True, opener=perf_open):
        self.kernel, self.opener = kernel, opener
        self.parent, self.child = socket.socketpair()
        self.fds = {}
        self.scope = "user+kernel" if kernel else "user"

    def child_pre(self):
        fds = []
        try:
            for _name, event in EVENTS:
                fds.append(self.opener(event, pid=0, kernel=self.kernel))
            socket.send_fds(self.child, [b"p"], fds)
        except OSError:
            self.child.send(b"n")   # the runner sees no descriptors and records no counts
        finally:
            for fd in fds:
                os.close(fd)

    def attach(self, pid):
        """Open the counters on a process that has not exec'd yet (it waits at the launch gate, see launch.py) from the runner; True when they opened. They enable on its exec."""
        self.child.close()
        self.parent.close()
        fds = {}
        try:
            for name, event in EVENTS:
                fds[name] = self.opener(event, pid=pid, kernel=self.kernel)
        except OSError:
            for fd in fds.values():
                os.close(fd)
            return False
        self.fds = fds
        return True

    def collect(self):
        """Receive the descriptors (call once, after Popen returned: the child had exec'd by then)."""
        self.child.close()
        try:
            msg, fds, _flags, _addr = socket.recv_fds(self.parent, 1, len(EVENTS))
        except OSError:
            msg, fds = b"", []
        finally:
            self.parent.close()
        if msg == b"p" and len(fds) == len(EVENTS):
            self.fds = {name: fd for (name, _e), fd in zip(EVENTS, fds)}
        else:
            for fd in fds:
                os.close(fd)
        return bool(self.fds)

    def read(self):
        """{"instructions", "cycles", "perf_scope"} (plus `perf_multiplexed` when the kernel time-shared a counter), or {} without counters."""
        if not self.fds:
            return {}
        out, mux = {}, False
        for name, fd in self.fds.items():
            try:
                value, enabled, running = parse_read(os.read(fd, 24))
            except OSError:
                return {}
            out[name], m = scale(value, enabled, running)
            mux = mux or m
        out["perf_scope"] = self.scope
        if mux:
            out["perf_multiplexed"] = True
        return out

    def close(self):
        for fd in self.fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        self.fds = {}


def start(info=None, opener=perf_open):
    """A Session for the next process when this host allows counting, else None. `info` is the run's probe result (None: probe now)."""
    if not sys.platform.startswith("linux"):
        return None
    info = info or probe()
    if not info["available"]:
        return None
    return Session(kernel=info["scope"] == "user+kernel", opener=opener)


# -- macOS ---------------------------------------------------------------------------------------------------------------------------------------

def _mac_rusage(pid, libproc=None):
    """The raw rusage_info_v4 bytes of one process, or None when it cannot be read."""
    try:
        lib = libproc or ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    except OSError:
        return None
    buf = ctypes.create_string_buffer(MAC_RUSAGE_SIZE)
    if lib.proc_pid_rusage(int(pid), MAC_RUSAGE_INFO_V4, buf) != 0:
        return None
    return buf.raw


def mac_read(pid, libproc=None):
    """{"instructions", "cycles", "phys_footprint"} of one process from proc_pid_rusage, or None when it cannot be read."""
    raw = _mac_rusage(pid, libproc)
    if raw is None:
        return None
    return {k: struct.unpack_from("<Q", raw, off)[0] for k, off in MAC_OFFSETS.items()}


def _mach_ns_per_tick():
    """Nanoseconds per Mach absolute-time tick (1 on Intel, 125/3 on Apple silicon), or None."""
    try:
        lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        info = (ctypes.c_uint32 * 2)()
        if lib.mach_timebase_info(info) != 0 or not info[1]:
            return None
        return info[0] / info[1]
    except (OSError, AttributeError):
        return None


def mac_cpu_ms(pid, libproc=None):
    """User plus system CPU time of one process in ms from proc_pid_rusage (the process's whole life so far, ticks of its exec included), or None where unreadable (not macOS, pid gone)."""
    if sys.platform != "darwin":
        return None
    raw = _mac_rusage(pid, libproc)
    scale = _mach_ns_per_tick()
    if raw is None or scale is None:
        return None
    return sum(struct.unpack_from("<Q", raw, off)[0] for off in MAC_TIME_OFFSETS) * scale / 1e6


class MacTree:
    """The sum over a process tree of each process's last proc_pid_rusage reading (a process that exited keeps its last reading)."""

    def __init__(self, reader=mac_read):
        self.reader, self.last = reader, {}

    def observe(self, pids):
        for pid in pids:
            r = self.reader(pid)
            if r:
                self.last[pid] = r

    def read(self):
        if not self.last:
            return {}
        return {"instructions": sum(r["instructions"] for r in self.last.values()), "cycles": sum(r["cycles"] for r in self.last.values()), "perf_scope": "sampled"}
