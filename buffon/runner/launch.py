# SPDX-License-Identifier: Apache-2.0
"""Start a harness so that none of the runner's own start-up work lands in its numbers.

A runner that forks to run Python before exec (join the cgroup, pin, open the perf counters) pays for that work and for the copy of its own address space, which the child
unmaps at exec. On a 300 MB runner this was 3 ms of CPU and 5 to 20 ms of wall in every sample, counted by the cgroup, by wait4 and by the clock.

So the harness starts as a small Python shim (`python -I -S`, about 10 MB, a few ms to start) that stops at a gate:

    1. the shim tells the runner it is ready and blocks reading the go pipe;
    2. the runner joins the cgroup, pins the process and opens its counters from outside, and reads the CPU the shim has used (a baseline), all while it is blocked;
    3. the runner writes go; the shim restores the signal dispositions a direct start has and execs the harness. The pipe it signalled on closes at the exec (it is close-on-exec),
       and the instant the runner sees it close is the harness's start.

Everything before step 3 is the shim's and the runner's, and the cgroup, the rusage baseline and the clock all start after it. What stays in the numbers is the wake-up of the
blocked shim and its exec, about 0.2 ms, which a direct start of the same process pays too (its exec).
"""
import errno
import os
import select
import shutil
import subprocess
import sys
import time

GATE_TIMEOUT_S = 30

# argv: the ready fd, the go fd, the path to exec, then the command. The go pipe first carries the harness's environment as NUL-separated KEY=VALUE entries, then "g" at the gate: the
# interpreter adds variables of its own at start (LC_CTYPE in a C locale, __CF_USER_TEXT_ENCODING on macOS), so the shim execs with the environment the runner gave, not the one it has.
# The environment is read and parsed before the gate, so the work after it is a read, two signal calls and the exec.
SHIM = r"""
import os, signal, sys
ready, go, path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
command = sys.argv[4:]
size = int.from_bytes(os.read(go, 8), "little")
data = b""
while len(data) < size:
    data += os.read(go, size - len(data))
env = dict(entry.split(b"=", 1) for entry in data.split(b"\0") if b"=" in entry)
os.write(ready, b"r")
if os.read(go, 1) != b"g":
    os._exit(1)
os.set_inheritable(ready, False)
os.close(go)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
try:
    os.execve(path, command, env)
except OSError as error:
    os.write(2, ("buffon: cannot start %s: %s\n" % (command[0], error)).encode())
    os._exit(127)
"""


def available():
    """True where the gated start applies: Linux or macOS, and a Python to run the shim."""
    return sys.platform.startswith(("linux", "darwin")) and bool(sys.executable)


def _resolve(argv, kwargs):
    """The path Popen would exec for argv[0]; raises what Popen would raise for a command it cannot run (the shim would only exit 127): FileNotFoundError or PermissionError."""
    command = argv[0]
    if os.sep in command:
        path = os.path.join(kwargs.get("cwd") or "", command)
    else:
        env = kwargs.get("env") if kwargs.get("env") is not None else os.environ
        path = shutil.which(command, path=env.get("PATH", os.defpath))
    if path is None or not os.path.exists(path):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), command)
    if not os.access(path, os.X_OK) or os.path.isdir(path):
        raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), command)
    return path


def _wait_readable(fd, child, what):
    """The byte (or end of file) on fd; RuntimeError when the shim died or took too long."""
    deadline = time.monotonic() + GATE_TIMEOUT_S
    while True:
        ready, _, _ = select.select([fd], [], [], 0.25)
        if ready:
            return os.read(fd, 1)
        if child.poll() is not None:
            raise RuntimeError(f"the launch shim exited with {child.returncode} before {what}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"the launch shim did not reach {what} in {GATE_TIMEOUT_S} s")


def spawn(argv, setup, **kwargs):
    """Popen(argv, **kwargs) held before its exec until setup(pid) has run: (child, perf_counter_ns() at its exec). kwargs must not hold a preexec_fn.

    If setup raises, the process is killed and the error is raised. A command that cannot run raises as Popen does."""
    path = _resolve(argv, kwargs)
    env = kwargs.get("env") if kwargs.get("env") is not None else os.environ
    block = b"\0".join(os.fsencode(k) + b"=" + os.fsencode(v) for k, v in env.items())
    ready_r, ready_w = os.pipe()
    go_r, go_w = os.pipe()
    child = None
    try:
        child = subprocess.Popen([sys.executable, "-I", "-S", "-c", SHIM, str(ready_w), str(go_r), path, *argv], pass_fds=(ready_w, go_r), **kwargs)
        child.args = list(argv)
        os.close(ready_w)
        os.close(go_r)
        ready_w = go_r = -1
        with os.fdopen(go_w, "wb", buffering=0) as pipe:   # the environment may be larger than the pipe buffer: the shim reads while this writes
            go_w = -1
            pipe.write(len(block).to_bytes(8, "little") + block)
            if _wait_readable(ready_r, child, "its gate") != b"r":
                raise RuntimeError("the launch shim did not reach its gate")
            setup(child.pid)
            pipe.write(b"g")
        _wait_readable(ready_r, child, "exec")   # end of file: the descriptor closed at exec
        stamp = time.perf_counter_ns()
        return child, stamp
    except BaseException:
        if child is not None:
            child.kill()
            child.wait()
        raise
    finally:
        for fd in (ready_r, ready_w, go_r, go_w):
            if fd >= 0:
                os.close(fd)
