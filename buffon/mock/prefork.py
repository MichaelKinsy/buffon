# SPDX-License-Identifier: Apache-2.0
"""A mock served by K worker processes (prefork), so that one Python interpreter's lock is not the ceiling of a swarm of agents (docs/design/SCALE.md).

The parent binds ONE unix socket and listens; K workers are started as `python -m buffon.mock.prefork` with the listening socket inherited, and each accepts on it, so the kernel hands a
connection to whichever worker is free. Each worker serves with the same handler and the same `Recorder` as the single-process mock, with its own policy copy. What that means for state:

  * the policy must be stateless across requests. `swarm_policy` is: it reads the agent and turn from the `[agent A turn T]` marker in the prompt, so any worker can answer any request;
  * the requests a worker received are kept in that worker; `flush` collects them from every worker, puts them in the order they arrived (`t_recv` is CLOCK_MONOTONIC, one clock for all the
    processes), numbers them again from 0 and hands them to the run's request log in one call: one file per sample, complete, as with one process;
  * no fault plan, no request hook: a serial workload keeps using the in-process `MockServer`, which is unchanged.

The parent controls the workers over one duplex pipe each (`multiprocessing.connection`): `policy` (a swarm's projects), `cpu` (the worker's CPU time), `offered`, `tools`, `flush`. A worker that finds its
parent gone exits."""
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

from .server import REPLY, Recorder, make_handler, swarm_marker, swarm_policy

BACKLOG = 4096     # the kernel caps it at net.core.somaxconn


class _Shared(ThreadingHTTPServer):
    """An HTTP server on a unix socket that somebody else bound and listens on."""
    address_family = socket.AF_UNIX
    daemon_threads = True

    def __init__(self, sock, handler):
        socketserver.BaseServer.__init__(self, sock.getsockname(), handler)
        self.socket = sock
        self.server_name, self.server_port = "unix", 0

    def get_request(self):
        conn, _ = self.socket.accept()   # a worker that lost the race for this connection finds none: BlockingIOError, which socketserver ignores
        conn.setblocking(True)
        return conn, ("unix", 0)


def run_worker(sock, ctl, parent_pid):
    """The worker: serve on the shared socket in a thread, answer the parent's commands on the main thread."""
    sock.setblocking(False)
    state = Recorder()
    policy = {"offered": set(), "fewest": [None]}
    httpd = _Shared(sock, type("Worker", (make_handler(state),), {"disable_nagle_algorithm": False}))   # TCP_NODELAY does not exist on a unix socket
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    ctl.send(("ready", os.getpid()))
    while True:
        if not ctl.poll(0.5):
            if os.getppid() != parent_pid:
                return
            continue
        try:
            command, *args = ctl.recv()
        except (EOFError, OSError):
            return
        if command == "policy":
            projects, reply = args
            with state.cond:
                state.requests, state.total, state.logged = [], 0, 0
            state.policy = swarm_policy(projects, reply)
            policy["offered"] = state.policy.offered
            policy["fewest"] = state.policy.fewest_tools
            ctl.send(("ok",))
        elif command == "cpu":
            ctl.send(("cpu", time.process_time()))
        elif command == "seen":
            counts = {}
            with state.cond:
                for r in state.requests:
                    found = swarm_marker(r)
                    if found:
                        counts[found[0]] = counts.get(found[0], 0) + 1
            ctl.send(("seen", counts))
        elif command == "offered":
            ctl.send(("offered", sorted(policy["offered"])))
        elif command == "tools":
            ctl.send(("tools", policy["fewest"][0]))
        elif command == "flush":
            with state.cond:
                got, state.requests, state.total, state.logged = state.requests, [], 0, 0
            ctl.send(("requests", [(r.t_recv, r.protocol, r.body, r.bytes, r.t_start, r.t_end, None if r.fault is None else str(r.fault)) for r in got], sorted(policy["offered"])))
        elif command == "quit":
            ctl.send(("bye",))
            return


def main(argv=None):
    from multiprocessing.connection import Connection
    sock_fd, ctl_fd, parent_pid = (int(x) for x in (argv or sys.argv[1:4]))
    sock = socket.socket(fileno=sock_fd)
    run_worker(sock, Connection(ctl_fd), parent_pid)


class Worker:
    def __init__(self, proc, ctl):
        self.proc, self.ctl = proc, ctl
        self.pid = proc.pid


class PreforkMock:
    """The parent's side: the listening socket, the workers, and the commands to them. `start` returns once every worker answered `ready`; `close` stops them and removes the socket."""

    def __init__(self, path, workers, wait_s=30.0):
        self.path, self.k, self.wait_s = path, max(1, int(workers)), wait_s
        self.workers, self.sock = [], None

    def start(self):
        from multiprocessing.connection import Pipe
        if os.path.exists(self.path):
            os.unlink(self.path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        os.chmod(self.path, 0o666)   # the container's non-root user connects to it
        self.sock.listen(BACKLOG)
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env = dict(os.environ, PYTHONPATH=repo + os.pathsep + os.environ.get("PYTHONPATH", ""))
        for _ in range(self.k):
            mine, theirs = Pipe()
            proc = subprocess.Popen([sys.executable, "-m", "buffon.mock.prefork", str(self.sock.fileno()), str(theirs.fileno()), str(os.getpid())], pass_fds=(self.sock.fileno(), theirs.fileno()), env=env,
                                    cwd=repo, stdin=subprocess.DEVNULL)
            theirs.close()
            self.workers.append(Worker(proc, mine))
        for w in self.workers:
            if not w.ctl.poll(self.wait_s) or w.ctl.recv()[0] != "ready":
                self.close()
                raise RuntimeError(f"a mock worker did not start within {self.wait_s:.0f} s")
        return self

    def _ask(self, *command):
        for w in self.workers:
            w.ctl.send(command)
        out = []
        for w in self.workers:
            if not w.ctl.poll(self.wait_s):
                raise RuntimeError("a mock worker did not answer")
            out.append(w.ctl.recv())
        return out

    def set_policy(self, projects, reply=REPLY):
        """A new sample: every worker forgets its requests and answers by the swarm policy of `projects` ({agent: project directory})."""
        self._ask("policy", dict(projects), reply)

    def cpu_ms(self):
        """[CPU milliseconds of each worker process so far]."""
        return [r[1] * 1000.0 for r in self._ask("cpu")]

    def seen(self):
        """{agent: requests the mock has received from it in this sample}, summed over the workers (an agent's requests may be served by different workers)."""
        out = {}
        for _tag, counts in self._ask("seen"):
            for agent, n in counts.items():
                out[agent] = out.get(agent, 0) + n
        return out

    def offered(self):
        """The tool steps ("read", "write", "shell") the workers have seen a request offer, unioned."""
        return set().union(*[set(r[1]) for r in self._ask("offered")])

    def fewest_tools(self):
        """The smallest tool list any request of this sample declared, over the workers; None when no request carried tools."""
        counts = [r[1] for r in self._ask("tools") if r[1] is not None]
        return min(counts) if counts else None

    def flush(self, context, sink):
        """Collect the requests of every worker, order them by arrival, number them again and write them to `sink` (a `RequestLog`) as one sample's file. Returns the number of requests."""
        merged = []
        for _tag, rows, _offered in self._ask("flush"):
            merged += rows
        merged.sort(key=lambda r: r[0])
        requests = [SimpleNamespace(index=i, protocol=p, t_recv=t, t_start=ts, t_end=te, bytes=n, fault=f, body=b) for i, (t, p, b, n, ts, te, f) in enumerate(merged)]
        if sink is not None and requests:
            sink.write(context, requests)
        return len(requests)

    def close(self):
        for w in self.workers:
            try:
                w.ctl.send(("quit",))
            except (OSError, ValueError):
                pass
        for w in self.workers:
            try:
                w.proc.wait(5)
            except subprocess.TimeoutExpired:
                w.proc.kill()
                w.proc.wait()
            try:
                w.ctl.close()
            except OSError:
                pass
        self.workers = []
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        if os.path.exists(self.path):
            os.unlink(self.path)


if __name__ == "__main__":
    main()
