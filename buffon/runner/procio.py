# SPDX-License-Identifier: MIT
"""Start a harness inside a meter and talk to it: batch print runs, JSONL RPC, and a PTY.

The POSIX terminal modules are imported by Pty only, so batch and RPC runs also work on Windows."""
import json
import os
import re
import select
import struct
import subprocess
import tempfile
import threading
import time

from . import cgroup
from ..mock import now_ns


def wait(meter, proc, timeout):
    """Wait for the process; True if it exited before the timeout. A meter stamps the exit (meter.exit_ns) and the rusage meter reaps with wait4."""
    try:
        if isinstance(meter, cgroup.Meter):
            meter.wait(timeout)
        else:
            proc.wait(timeout)
        return True
    except subprocess.TimeoutExpired:
        return False


def diagnosis(proc, tail=lambda: b""):
    """` (exit N; stderr tail: ...)` or ` (process still running; ...)`: the part of a failure message that says what the process did. A container's relay error and a harness's crash text are both here."""
    code = proc.poll()
    try:
        text = tail().decode(errors="replace").strip()
    except OSError:
        text = ""
    state = f"exit {code}" if code is not None else "process still running"
    return f" ({state}" + (f"; stderr tail: {text[-400:]!r}" if text else "") + ")"


def exit_stamp(meter):
    """The instant the last wait() saw the process exit (the kernel's report, see exitwatch), or now where the meter has none."""
    return getattr(meter, "exit_ns", None) or now_ns()


def spawn_instant(meter):
    start = getattr(meter, "start_ns", None)
    return start() if start else None


def exit_instant(meter):
    end = getattr(meter, "end_ns", None)
    return end() if end else None


class Batch:
    """One non-interactive process: spawn, wait, collect resources. Output goes to files, so a chatty harness cannot block on a pipe."""

    def __init__(self, argv, env, cwd, meter, timeout=120):
        self.argv, self.env, self.cwd, self.meter, self.timeout = argv, env, cwd, meter, timeout

    def run(self):
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            self.t_spawn = now_ns()
            try:
                self.proc = self.meter.popen(self.argv, env=self.env, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
            except OSError as error:
                return {"code": 127, "timed_out": False, "stdout": "", "stderr": str(error), "t_spawn": self.t_spawn, "t_exit": now_ns()}
            done = wait(self.meter, self.proc, self.timeout)
            self.t_exit = exit_stamp(self.meter)
            if not done:
                self.meter.kill()
                wait(self.meter, self.proc, 10)
            result = self.collect()
            out.seek(0)
            err.seek(0)
            result.update({"timed_out": not done, "stdout": out.read().decode(errors="replace"), "stderr": err.read().decode(errors="replace")[-4000:]})
            return result

    def collect(self):
        meter = self.meter
        t_spawn, t_exit = spawn_instant(meter) or self.t_spawn, exit_instant(meter) or self.t_exit
        return {"code": self.proc.returncode, "t_spawn": t_spawn, "t_exit": t_exit, "wall_ms": (t_exit - t_spawn) / 1e6, "cpu_ms": meter.cpu_ms(),
                "peak_mem_mib": meter.peak_mem_mib(), "max_proc_rss_mib": meter.max_proc_rss_mib(), "meter": meter.mode, "perf": getattr(meter, "perf", dict)()}


class Rpc:
    """A harness in `--mode rpc`: JSON Lines on stdin and stdout, every output record time-stamped on arrival."""

    def __init__(self, argv, env, cwd, meter):
        self.meter = meter
        self.records = []  # (t_ns, dict)
        self.cond = threading.Condition()
        self.stderr = tempfile.TemporaryFile()
        self._t_spawn = now_ns()
        self.proc = meter.popen(argv, env=env, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self._id = 0

    @property
    def t_spawn(self):
        """The instant the arm started: the relay's stamp inside a container (the container's creation is not the arm's time), else the meter's stamp of the harness's exec (the runner's fork and set-up are not the arm's time either), else the instant the runner asked for the process."""
        return spawn_instant(self.meter) or self._t_spawn

    def _read(self):
        for line in self.proc.stdout:
            t = now_ns()
            try:
                record = json.loads(line)
            except ValueError:
                continue
            with self.cond:
                self.records.append((t, record))
                self.cond.notify_all()

    def diagnosis(self):
        """What a failed sample should say about the process: its exit status (or that it is still running) and the tail of its stderr. Reads with pread, so it never moves the child's write offset."""
        return diagnosis(self.proc, lambda: os.pread(self.stderr.fileno(), 600, max(0, os.fstat(self.stderr.fileno()).st_size - 600)))

    def send(self, command):
        self._id += 1
        command = dict(command, id=f"b{self._id}")
        self.proc.stdin.write((json.dumps(command) + "\n").encode())
        self.proc.stdin.flush()
        return command["id"], now_ns()

    def wait_for(self, predicate, timeout, start=0):
        """Return (t_ns, record, next_index) of the first record at or after `start` matching predicate, or None on timeout or exit."""
        deadline = time.monotonic() + timeout
        i = start
        with self.cond:
            while True:
                while i < len(self.records):
                    t, record = self.records[i]
                    i += 1
                    if predicate(record):
                        return t, record, i
                if self.proc.poll() is not None and i >= len(self.records):
                    return None
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self.cond.wait(min(left, 0.25))

    def close(self, grace=10):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        if not wait(self.meter, self.proc, grace):
            self.meter.kill()
            wait(self.meter, self.proc, 10)
        self.t_exit = exit_stamp(self.meter)
        self.stderr.seek(0)
        self.stderr_text = self.stderr.read().decode(errors="replace")[-4000:]
        self.stderr.close()


# Terminal queries a TUI sends at startup and the replies a real terminal gives. Every arm gets the same answers.
QUERIES = [
    (b"\x1b[c", b"\x1b[?62;c"),
    (b"\x1b[>c", b"\x1b[>0;0;0c"),
    (b"\x1b[?u", b"\x1b[?0u"),
    (b"\x1b[6n", b"\x1b[1;1R"),
    (b"\x1b[?2026$p", b"\x1b[?2026;2$y"),
    (b"\x1b[?996n", b"\x1b[?997;1n"),
]


# The second terminal profile (METHODOLOGY.md section 4): a kitty-like terminal that supports the keyboard protocol (flags 1), synchronized output
# (mode 2026 set and reset) and answers the colour and size queries. TERM stays xterm-256color for both so no terminfo entry is needed; only the answers differ.
QUERIES_KITTY = [
    (b"\x1b[c", b"\x1b[?62;c"),
    (b"\x1b[>c", b"\x1b[>1;4000;0c"),
    (b"\x1b[?u", b"\x1b[?1u"),
    (b"\x1b[6n", b"\x1b[1;1R"),
    (b"\x1b[?2026$p", b"\x1b[?2026;1$y"),
    (b"\x1b[?996n", b"\x1b[?997;1n"),
    (b"\x1b]10;?\x07", b"\x1b]10;rgb:cccc/cccc/cccc\x07"),
    (b"\x1b]11;?\x07", b"\x1b]11;rgb:0000/0000/0000\x07"),
    (b"\x1b[14t", b"\x1b[4;800;960t"),
    (b"\x1b[18t", b"\x1b[8;40;120t"),
]
TERMINAL_PROFILES = {"xterm": QUERIES, "kitty": QUERIES_KITTY}


def new_queries(tail, data, query):
    """Occurrences of `query` in tail + data that end inside `data`: a query wholly inside the carried-over tail was answered with the previous chunk."""
    window = tail + data
    n, start = 0, window.find(query)
    while start != -1:
        if start + len(query) > len(tail):
            n += 1
        start = window.find(query, start + 1)
    return n


ANSI_ESCAPES = re.compile(rb"\x1b\[[0-9;?<>=]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|\x1b[=>78]")


class Pty:
    """A harness on a pseudo-terminal of fixed size. A reader thread time-stamps each chunk and answers terminal queries."""

    def __init__(self, argv, env, cwd, meter, rows=40, cols=120, echo=True, profile="xterm"):
        """echo=False starts the terminal without the line discipline's echo: before a TUI enters raw mode the kernel would echo typed keys
        itself, so a key on screen would not prove that the application read it. Raw mode turns echo off anyway, so a TUI sees no difference."""
        import fcntl
        import pty
        import termios
        self.meter = meter
        self.queries = TERMINAL_PROFILES[profile]
        self.chunks = []  # (t_ns, bytes)
        self.cond = threading.Condition()
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        if not echo:
            attrs = termios.tcgetattr(slave)
            attrs[3] &= ~(termios.ECHO | termios.ECHONL)
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
        self.master = master
        env = dict(env, COLUMNS=str(cols), LINES=str(rows))
        env.pop("NO_COLOR", None)

        def controlling_tty():
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        self._t_spawn = now_ns()
        self.proc = meter.popen(argv, env=env, cwd=cwd, stdin=slave, stdout=slave, stderr=slave, start_new_session=True, preexec_fn=controlling_tty)
        os.close(slave)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def diagnosis(self):
        """Exit status and the last output the process wrote to its terminal (a TUI's stderr is on the terminal too)."""
        return diagnosis(self.proc, lambda: re.sub(rb"\x1b\[[0-9;?]*[ -/]*[@-~]", b"", b"".join(c for _, c in self.chunks[-20:]))[-600:])

    @property
    def t_spawn(self):
        """The instant the arm started: the relay's stamp inside a container (the container's creation is not the arm's time), else the meter's stamp of the harness's exec (the runner's fork and set-up are not the arm's time either), else the instant the runner asked for the process."""
        return spawn_instant(self.meter) or self._t_spawn

    def _read(self):
        tail = b""
        while True:
            try:
                ready, _, _ = select.select([self.master], [], [], 0.25)
                if not ready:
                    if self.proc.poll() is not None:
                        return
                    continue
                data = os.read(self.master, 65536)
            except OSError:
                return
            if not data:
                return
            t = now_ns()
            for query, reply in self.queries:
                n = new_queries(tail, data, query)
                if n:
                    try:
                        os.write(self.master, reply * n)
                    except OSError:
                        pass
            tail = data[-16:]
            with self.cond:
                self.chunks.append((t, data))
                self.cond.notify_all()

    def type(self, text):
        os.write(self.master, text.encode() if isinstance(text, str) else text)

    def text(self):
        with self.cond:
            return b"".join(c for _, c in self.chunks).decode(errors="replace")

    def wait_text(self, needle, timeout, since=0, visible=False):
        """Time (ns) at which the output first contained `needle` in chunks from index `since`, or None. `visible` searches the output with terminal escape sequences removed (a
        highlighted code block splits its words with colour codes)."""
        deadline = time.monotonic() + timeout
        with self.cond:
            while True:
                seen = b""
                for t, c in self.chunks[since:]:
                    seen += c
                    if needle.encode() in (ANSI_ESCAPES.sub(b"", seen) if visible else seen):
                        return t
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self.cond.wait(min(left, 0.25))

    def wait_quiet(self, quiet_s, timeout):
        """Time (ns) of the last chunk once no output has arrived for quiet_s seconds; None on timeout."""
        deadline = time.monotonic() + timeout
        with self.cond:
            while True:
                last = self.chunks[-1][0] if self.chunks else None
                if last is not None and (now_ns() - last) / 1e9 >= quiet_s:
                    return last
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self.cond.wait(min(0.05, left))

    def close(self, grace=10):
        if self.proc.poll() is None:
            self.meter.kill()
        wait(self.meter, self.proc, grace)
        try:
            os.close(self.master)
        except OSError:
            pass
