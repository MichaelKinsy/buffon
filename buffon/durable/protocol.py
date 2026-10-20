# SPDX-License-Identifier: Apache-2.0
"""The runner's end of the adapter protocol (docs/DURABLE-ADAPTERS.md): start an adapter inside a meter, send one request at a time, time every exchange with the runner's own clock.

The clock is `now_ns()` (the monotonic clock): the statistics read only these stamps. The adapter's own stamps (`mono_ns`, `first_request_mono_ns`, ...) are used for `ttfr_ms` and
`first_delta_ms` alone, and only when the ready line shows the two clocks agree (`ClockCheck`). A request is answered by one response line with the same `id`; lines with an `event`
key (`ready`, `crashing`) are kept with their arrival time. An adapter that exits while a request is open ends the exchange with `Died`, carrying what it said last."""
import json
import os
import subprocess
import tempfile
import threading
import time

from ..mock import now_ns
from ..runner import procio

CLOCK_AGREEMENT_NS = 5_000_000   # the adapter's monotonic clock and the runner's must agree to this much at the ready line for adapter stamps to be used
READY_TIMEOUT_S = 120.0
CALL_TIMEOUT_S = 900.0


class AdapterError(RuntimeError):
    """The adapter broke the protocol, or did not answer in time."""


class Died(AdapterError):
    """The adapter exited while a request was open. `events` are the event lines it wrote, `code` its exit status (negative: the signal)."""

    def __init__(self, message, events=(), code=None):
        super().__init__(message)
        self.events, self.code = list(events), code


class Unsupported(Exception):
    """The adapter answered `unsupported`: the arm cannot do what the request asked. The text is the sentence the report prints as the cell's reason."""


class Failed(AdapterError):
    """The adapter answered `ok: false` with an error."""


class Exchange(dict):
    """One response with the runner's stamps around it: `t_send` and `t_recv` (ns), and `ms` between them."""

    @property
    def ms(self):
        return (self.t_recv - self.t_send) / 1e6


class Adapter:
    """One adapter process in a meter. `argv` is the arm's executable (`arm.binary`) with no arguments: it serves the protocol."""

    def __init__(self, argv, env, cwd, meter, timeout=CALL_TIMEOUT_S):
        self.meter, self.timeout = meter, timeout
        self.lines, self.events = [], []   # (t_ns, response dict) and (t_ns, event dict), in arrival order
        self.cond = threading.Condition()
        self.stderr = tempfile.TemporaryFile()
        self._next = 0
        self.closed = False
        self.t_spawn_request = now_ns()
        self.proc = meter.popen(argv, env=env, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True)
        self.t_spawn = procio.spawn_instant(meter) or self.t_spawn_request
        self.eof = False
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.ready = None
        self.t_ready = None

    # -- reading ------------------------------------------------------------------------------------------------------------------------------

    def _read(self):
        for raw in self.proc.stdout:
            t = now_ns()
            try:
                doc = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(doc, dict):
                continue
            with self.cond:
                (self.events if "event" in doc else self.lines).append((t, doc))
                self.cond.notify_all()
        with self.cond:
            self.eof = True
            self.cond.notify_all()

    def tail(self, n=600):
        """The tail of the adapter's stderr (free text for people), read without moving the child's write offset."""
        try:
            size = os.fstat(self.stderr.fileno()).st_size
            return os.pread(self.stderr.fileno(), n, max(0, size - n)).decode(errors="replace").strip()
        except OSError:
            return ""

    def diagnosis(self):
        return procio.diagnosis(self.proc, lambda: self.tail().encode())

    def _wait(self, predicate, timeout, what):
        """Block until `predicate()` (called with the lock held) is true; Died when the adapter exited first, AdapterError on timeout."""
        deadline = time.monotonic() + timeout
        with self.cond:
            while True:
                got = predicate()
                if got is not None:
                    return got
                if self.eof:
                    self.proc.poll()
                    raise Died(f"the adapter exited while the runner waited for {what}{self.diagnosis()}", [e for _, e in self.events], self.proc.returncode)
                left = deadline - time.monotonic()
                if left <= 0:
                    raise AdapterError(f"the adapter did not answer {what} within {timeout:.0f} s{self.diagnosis()}")
                self.cond.wait(min(left, 0.25))

    def wait_ready(self, timeout=READY_TIMEOUT_S):
        """The ready event: sets `ready`, `t_ready`. `proc_start_ms` is `t_ready` minus `t_spawn`."""
        t, doc = self._wait(lambda: next(((t, e) for t, e in self.events if e.get("event") == "ready"), None), timeout, "the ready line")
        if doc.get("protocol") != 1:
            raise AdapterError(f"the adapter speaks protocol {doc.get('protocol')!r}, this runner speaks 1")
        self.ready, self.t_ready = doc, t
        return doc

    @property
    def proc_start_ms(self):
        return (self.t_ready - self.t_spawn) / 1e6

    @property
    def clock_offset_ns(self):
        """Adapter clock minus runner clock at the ready line, or None before it. Adapter stamps are converted with it; `clock_ok` says whether they may be used."""
        if not self.ready or "mono_ns" not in self.ready:
            return None
        return self.ready["mono_ns"] - self.t_ready

    @property
    def clock_ok(self):
        """True when the adapter's monotonic stamps and the runner's are on one clock: the ready line's stamp is within CLOCK_AGREEMENT_NS of the runner's receipt of it (the line is written, then read at once)."""
        off = self.clock_offset_ns
        return off is not None and abs(off) <= CLOCK_AGREEMENT_NS

    # -- requests -----------------------------------------------------------------------------------------------------------------------------

    def send(self, op, **fields):
        """Write a request; returns (id, t_send_ns)."""
        self._next += 1
        doc = dict(fields, id=self._next, op=op)
        data = (json.dumps(doc, separators=(",", ":")) + "\n").encode()
        t = now_ns()
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (OSError, ValueError) as error:
            raise Died(f"the adapter's stdin closed while the runner sent {op}: {error}{self.diagnosis()}", [e for _, e in self.events], self.proc.poll()) from None
        return self._next, t

    def receive(self, ident, op="request", timeout=None):
        """The response to request `ident` and the instant it arrived. Raises Unsupported or Failed for an adapter that said so."""
        t, doc = self._wait(lambda: next(((t, d) for t, d in self.lines if d.get("id") == ident), None), timeout or self.timeout, f"the answer to {op}")
        if not doc.get("ok"):
            if doc.get("unsupported"):
                raise Unsupported(str(doc["unsupported"]))
            raise Failed(f"{op}: {doc.get('error', 'no reason given')}")
        return t, doc

    def call(self, op, timeout=None, **fields):
        """One exchange: send, wait for the answer. Returns an Exchange (the response's fields) with t_send and t_recv."""
        ident, t_send = self.send(op, **fields)
        t_recv, doc = self.receive(ident, op, timeout)
        ex = Exchange({k: v for k, v in doc.items() if k not in ("id", "ok")})
        ex.t_send, ex.t_recv = t_send, t_recv
        return ex

    def to_runner_clock(self, adapter_ns):
        """An adapter stamp on the runner's clock, or None when the two clocks are not shown to agree or the adapter gave none."""
        off = self.clock_offset_ns
        return None if adapter_ns is None or off is None or not self.clock_ok else adapter_ns - off

    # -- end ----------------------------------------------------------------------------------------------------------------------------------

    def wait_exit(self, timeout=30.0):
        """Wait for the process to exit (after a crash_after or a closed stdin); True if it did. The exit status is then `proc.returncode`."""
        return procio.wait(self.meter, self.proc, timeout)

    def crash_events(self):
        return [e for _, e in self.events if e.get("event") == "crashing"]

    def close(self, grace=10.0):
        """Close stdin and let the adapter exit; kill the tree when it does not. Safe to call twice."""
        if self.closed:
            return
        self.closed = True
        try:
            self.proc.stdin.close()
        except (OSError, ValueError):
            pass
        if not procio.wait(self.meter, self.proc, grace):
            self.meter.kill()
            procio.wait(self.meter, self.proc, 10)
        self.reader.join(timeout=2)
        try:
            self.proc.stdout.close()
        except (OSError, ValueError):
            pass
        self.stderr_text = self.tail(4000)
        self.stderr.close()
