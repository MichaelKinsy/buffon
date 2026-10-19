# SPDX-License-Identifier: Apache-2.0
"""Wait for a child to exit and stamp the exit when the kernel reports it, not when a poll loop next looks.

A loop of wait4(WNOHANG) and sleep(5 ms) delays the stamp by up to the sleep, and a sampler thread that holds the GIL adds more. On a command that runs for 5 ms
the wall time then jumped between 12 and 42 ms from round to round while its CPU time stayed at 8 ms. The kernel can tell us the instant instead:
Linux has a pid file descriptor (pidfd_open, 5.3) that polls readable at exit, macOS has a kqueue process filter (NOTE_EXIT).
The process is not reaped here, so the caller still reaps it with wait4 and keeps the rusage of the whole tree.
"""
import math
import os
import select
import sys
import threading
import time

# The sampler threads wake every few ms. A thread that wakes from poll needs the GIL; with the default 5 ms switch interval a busy sampler can hold it for that long.
SWITCH_INTERVAL_S = 0.0002
_lock = threading.Lock()
_waiting = 0
_saved = None


def supported():
    """The name of the mechanism this host has: "pidfd", "kqueue", or None (callers poll then)."""
    if hasattr(os, "pidfd_open"):
        return "pidfd"
    if sys.platform == "darwin" and hasattr(select, "kqueue"):
        return "kqueue"
    return None


def _ms(remaining):
    return None if remaining is None else max(0, math.ceil(remaining * 1000))


def _pidfd(pid, timeout):
    try:
        fd = os.pidfd_open(pid)
    except OSError:  # ESRCH: already reaped; ENOSYS, EPERM: no pidfd on this kernel or under this seccomp filter
        return None
    try:
        poller = select.poll()
        poller.register(fd, select.POLLIN)
        ready = poller.poll(_ms(timeout))
        stamp = time.perf_counter_ns()
        if not ready:
            raise TimeoutError
        return stamp
    finally:
        os.close(fd)


def _kqueue(pid, timeout):
    try:
        kq = select.kqueue()
    except OSError:
        return None
    try:
        event = select.kevent(pid, select.KQ_FILTER_PROC, select.KQ_EV_ADD | select.KQ_EV_ONESHOT, select.KQ_NOTE_EXIT)
        events = kq.control([event], 1, timeout)
        stamp = time.perf_counter_ns()
        if not events:
            raise TimeoutError
        if events[0].flags & select.KQ_EV_ERROR:  # data is the errno: ESRCH when the process has already exited (a zombie cannot be registered)
            return None
        return stamp
    finally:
        kq.close()


def _fast_switch(on):
    """Shorten the thread switch interval while any thread waits here; the last one out restores it."""
    global _waiting, _saved
    with _lock:
        _waiting += 1 if on else -1
        if on and _waiting == 1:
            _saved = sys.getswitchinterval()
            sys.setswitchinterval(min(_saved, SWITCH_INTERVAL_S))
        elif not on and _waiting == 0:
            sys.setswitchinterval(_saved)


def wait_exit(pid, timeout=None):
    """Block until `pid` exits and return the time.perf_counter_ns() reading taken when the kernel said so.

    Raises TimeoutError after `timeout` seconds. Returns None when this host cannot watch the pid (no mechanism, or the process is already gone): the caller then polls.
    The process stays a zombie until the caller reaps it.
    """
    how = supported()
    if how is None:
        return None
    _fast_switch(True)
    try:
        return (_pidfd if how == "pidfd" else _kqueue)(pid, timeout)
    finally:
        _fast_switch(False)
