# SPDX-License-Identifier: Apache-2.0
"""The swarm container: N agents of one harness running at once in ONE container (docs/design/SCALE.md, docs/ENVELOPE.md).

The container is the envelope of buffon/envelope (G1-G11) with the swarm's own limits: memory equal to memory-swap, a cpuset with `--cpus` equal to its size, a pids limit, no network.
The relay inside it (envelope/relay, `-swarm`) is the launcher: the runner starts ONE `docker run -i` and talks to the relay over its standard input and output, one JSON object per
line. Every agent is a process of the relay inside the container's cgroup; none runs outside it. The host has the one `docker run` client (a child of the runner, so on the runner's own
CPUs, the mock's) and an event-reading thread; no per-agent helper process. The runtime's daemon and shim carry the control channel (a few hundred lines per turn: the relay passes on only
the lines the runner asked for) and are not pinned by the buffon.

Every time is the relay's CLOCK_MONOTONIC stamp, so a latency is a difference on one clock inside the container. The container's counters are read from its cgroup on the host
(`/sys/fs/cgroup/system.slice/<runtime>-<id>.scope`), which a container that is thrashing at its memory limit cannot stand in the way of; when the host cannot see that path (a runtime in a
virtual machine) the relay's own reading from inside is used."""
import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field

from ..envelope import Mount, Spec, build_argv, lint
from .container import RELAY_DIR_IN_CONTAINER, SEED_IN_CONTAINER, SOCKET_IN_CONTAINER, container_ulimits, container_user

PIDS_PER_AGENT = 64        # threads count as processes in a pids limit: a Node, Bun or Go agent has 10 to 30 of them, and the tools an agent runs add more
PIDS_BASE = 1024
NOFILE = "4096:1048576"    # the soft limit every process starts with is the envelope's 4096; the relay raises its own to the hard one (Go does at start) because it holds three descriptors per agent and two per connection to the mock
TMPFS_TMP_MIB = 512


def pids_limit(n):
    """The swarm's pids limit: 64 per agent and 1,024 over, so that the memory limit, not the process count, is the first limit a swarm meets."""
    return PIDS_PER_AGENT * n + PIDS_BASE


@dataclass
class SwarmConfig:
    image: str
    runtime: str
    cpus: list                  # the swarm's cpuset: all on one NUMA node
    mems: str
    memory_mib: int
    pids: int
    ro_paths: list              # bind-mounted read-only at the same path (the workspace root with the arm install trees)
    rw_dir: str                 # the one writable bind mount (the run's work directory)
    homes_dir: str              # under rw_dir: every agent's HOME lives here; read-only seed at SEED_IN_CONTAINER and a tmpfs at the same path
    socket_path: str
    mock_port: int
    relay_dir: str
    home_tmpfs_mib: int = 0     # 0: as large as the memory limit (the limit, not the file system's size, bounds what HOMEs can hold)
    cgroup_path: str = None     # the container's cgroup on the host, when known beforehand (tests)
    extra: dict = field(default_factory=dict)

    def record(self):
        """raw.json samples[].swarm."""
        return {"memory_mib": int(self.memory_mib), "cpus": sorted(int(c) for c in self.cpus), "pids_max": int(self.pids)}


def swarm_spec(cfg, name, cidfile):
    """The envelope Spec of a swarm container."""
    mounts = [Mount(p, p) for p in cfg.ro_paths] + [Mount(cfg.relay_dir, RELAY_DIR_IN_CONTAINER), Mount(cfg.homes_dir, SEED_IN_CONTAINER)]
    tmpfs = {"/tmp": TMPFS_TMP_MIB, cfg.homes_dir: cfg.home_tmpfs_mib or int(cfg.memory_mib)}
    ulimits = dict(container_ulimits(), nofile=NOFILE)
    return Spec(image=cfg.image, cpuset_cpus=list(cfg.cpus), cpuset_mems=str(cfg.mems), memory_mib=int(cfg.memory_mib), pids=int(cfg.pids), env={}, mounts=mounts,
                output=Mount(cfg.rw_dir, cfg.rw_dir, False), sockets=[(cfg.socket_path, SOCKET_IN_CONTAINER)], user=container_user(), ulimits=ulimits, workdir=cfg.rw_dir, tmpfs=tmpfs, name=name,
                labels={"buffon": "swarm"}, interactive=True, cidfile=cidfile)


def swarm_argv(cfg, name, cidfile):
    """`docker run -i ... relay -swarm`: built by the envelope's builder, which lints it against G1-G11 (and so does anything that reads it)."""
    command = [f"{RELAY_DIR_IN_CONTAINER}/relay", "-swarm", "-listen", f"127.0.0.1:{cfg.mock_port}", "-unix", SOCKET_IN_CONTAINER]
    return build_argv(swarm_spec(cfg, name, cidfile), command, runtime=cfg.runtime)


def parse_kv(text):
    out = {}
    for line in text.splitlines():
        key, _, value = line.partition(" ")
        value = value.strip()
        if value.lstrip("-").isdigit():
            out[key] = int(value)
    return out


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def read_cgroup(path):
    """The counters of a cgroup directory: {"memory.current", "memory.peak", "pids.current", "pids.peak", "cpu.stat": {...}, "memory.events": {...}, "pids.events": {...}}; None when unreadable."""
    stat = _read(os.path.join(path, "cpu.stat"))
    if stat is None:
        return None
    out = {"cpu.stat": parse_kv(stat)}
    for name in ("memory.current", "memory.peak", "pids.current", "pids.peak"):
        text = _read(os.path.join(path, name))
        if text is not None and text.strip().isdigit():
            out[name] = int(text)
    for name in ("memory.events", "pids.events"):
        text = _read(os.path.join(path, name))
        out[name] = parse_kv(text) if text is not None else {}
    return out


class Watch:
    """Ends a rung as soon as its cause is known, instead of at the stage timeout (docs/design/SCALE.md). Fed the container's counters and the count of events the agents produced:
    `oom` at the first OOM kill since the rung began; `stall` when no agent made progress for `stall_s` seconds, the container is within 10% of its memory limit, and its `memory.events max`
    counter rose in that time (the kernel is reclaiming at the limit and killing nothing). Returns None while neither holds."""

    AT_LIMIT = 0.9

    def __init__(self, base, limit_bytes, stall_s, clock=time.monotonic):
        events = (base or {}).get("memory.events") or {}
        self.kills0, self.hits0 = events.get("oom_kill", 0), events.get("max", 0)
        self.limit, self.stall_s, self.clock = limit_bytes, float(stall_s), clock
        self.progress, self.since, self.hits = None, clock(), self.hits0

    def check(self, reading, progress):
        events = (reading or {}).get("memory.events") or {}
        if events.get("oom_kill", 0) > self.kills0:
            return "oom"
        now = self.clock()
        if progress != self.progress:
            self.progress, self.since, self.hits = progress, now, events.get("max", self.hits)
            return None
        current = (reading or {}).get("memory.current")
        if now - self.since >= self.stall_s and events.get("max", 0) > self.hits and current is not None and self.limit and current >= self.AT_LIMIT * self.limit:
            return "stall"
        return None


class AgentState:
    def __init__(self, i):
        self.id = i
        self.records = []        # [(t, sent, record)]: the lines the relay passed on, parsed
        self.cursor = 0
        self.started = None      # relay clock, ns
        self.exit = None         # the relay's exit event
        self.ready = None        # ns of the get_state answer
        self.turns = 0           # turns answered
        self.lat_ms = []         # per turn
        self.last_t = None

    def dead(self):
        return self.exit is not None


class Swarm:
    """One swarm container and the control channel to its relay. `popen` is the process starter (a fake in the tests)."""

    def __init__(self, cfg, popen=subprocess.Popen, clock=time.monotonic, sleep=time.sleep, poll_s=0.05):
        self.cfg, self._popen, self.clock, self.sleep, self.poll_s = cfg, popen, clock, sleep, poll_s
        self.agents = {}
        self.cid = None
        self.cgroup_path = cfg.cgroup_path
        self.proc = None
        self.ready_t = None
        self.bye = False
        self.failed = None
        self._lock = threading.Lock()
        self._replies = {}
        self._req = 0
        self._dir = tempfile.mkdtemp(prefix="buffon-swarm-", dir=cfg.rw_dir)
        self._cidfile = os.path.join(self._dir, "cid")
        self._stderr = open(os.path.join(self._dir, "docker.stderr"), "wb+")
        self.name = f"buffon-swarm-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.argv = None
        self.events = 0
        self.progress = 0           # events that show an agent working: started, output kept, exit
        self.watch = None           # a Watch: wait_until ends early when it names a cause
        self.verdict = None         # the cause the watch named ("oom", "stall"), once
        self._killed = False
        self._asked, self._pending = -1e9, None
        self.last = None            # the newest reading of the container's cgroup: the final one when the container dies, which takes its cgroup with it
        self._stop = False

    # -- the container -------------------------------------------------------------------------------------------------------------------------

    def start(self, timeout=120.0):
        """Start the container and wait for the relay's `ready`. Raises RuntimeError with the runtime's own words when it does not come up."""
        self.argv = swarm_argv(self.cfg, self.name, self._cidfile)
        problems = lint(self.argv)
        if problems:
            raise RuntimeError("the swarm container's command line breaks the envelope: " + "; ".join(problems))
        env_cli = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/")}
        self.proc = self._popen(self.argv, env=env_cli, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr)
        threading.Thread(target=self._read, daemon=True).start()
        deadline = self.clock() + timeout
        while self.ready_t is None:
            if self.proc.poll() is not None and not self.bye and self.ready_t is None:
                self.sleep(0.05)
                if self.ready_t is None:
                    raise RuntimeError("the swarm container did not start" + self.diagnosis())
            if self.clock() > deadline:
                raise RuntimeError(f"the swarm container did not answer within {timeout:.0f} s" + self.diagnosis())
            self.sleep(0.01)
        self._find_cgroup()
        if self.cgroup_path:
            threading.Thread(target=self._monitor, daemon=True).start()

    def _monitor(self, every=0.05):
        """Keep the newest reading of the cgroup. A container killed at its memory limit (the kernel's OOM killer took the relay or the init) disappears with its counters; this is what is left."""
        while not self._stop:
            got = read_cgroup(self.cgroup_path)
            if got is None:
                return
            self.last = got
            self.sleep(every)

    def exited(self):
        """The container's exit status when it is gone on its own (137: killed by the kernel), else None. A container this runner killed (`kill`) did not exit by itself."""
        return None if self._killed else self.proc.poll() if self.proc is not None else None

    def kill(self):
        """Kill the container at once (a rung whose cause is known): `docker kill`. Its cgroup and counters go with it, so read them first."""
        self._killed = True
        for target in ([self.cid] if self.cid else []) + [self.name]:
            try:
                self._popen([self.cfg.runtime, "kill", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait(timeout=20)
            except Exception:
                pass

    def observe(self, every=1.0):
        """The newest reading of the container's counters without waiting for one: the monitor's, or (a runtime whose cgroup the host cannot see) the relay's, asked every `every` seconds and read
        on a later call, so a container thrashing at its memory limit cannot hold the poll up."""
        if self.cgroup_path:
            return self.last
        if self._pending is not None:
            with self._lock:
                reply = self._replies.pop(self._pending, None)
            if reply is not None:
                self._pending = None
                self.last = reply.get("cgroup") or self.last
        now = self.clock()
        if self._pending is None and now - self._asked >= every and self.proc.poll() is None:
            with self._lock:
                self._req += 1
                self._pending = self._req
            self._asked = now
            self._send({"op": "stats", "req": self._pending})
        return self.last

    def diagnosis(self):
        try:
            self._stderr.flush()
            self._stderr.seek(0)
            text = self._stderr.read().decode(errors="replace").strip()[-400:]
        except (OSError, ValueError):
            text = ""
        code = self.proc.poll() if self.proc else None
        return f" (exit {code}" + (f"; {text!r}" if text else "") + ")" if code is not None or text else ""

    def _find_cgroup(self, timeout=5.0):
        if self.cgroup_path:
            return
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            try:
                with open(self._cidfile) as f:
                    self.cid = f.read().strip()
            except OSError:
                self.cid = None
            if self.cid:
                for path in (f"/sys/fs/cgroup/system.slice/{self.cfg.runtime}-{self.cid}.scope", f"/sys/fs/cgroup/machine.slice/libpod-{self.cid}.scope"):
                    if os.path.isdir(path):
                        self.cgroup_path = path
                        return
                return
            self.sleep(0.01)

    def cgroup(self):
        """The container's counters now: from the host's view of its cgroup, else (a runtime the host cannot see into) from the relay."""
        if self.cgroup_path:
            got = read_cgroup(self.cgroup_path)
            if got is not None:
                return got
            if self.last is not None:
                return self.last
        reply = self.request("stats", timeout=20)
        return (reply or {}).get("cgroup") or None

    def relay_cpu_ms(self, timeout=20):
        """The relay's own CPU so far (user + system, every thread), or None when it does not answer."""
        reply = self.request("stats", timeout=timeout)
        return None if reply is None else reply.get("relay_cpu_ms")

    # -- the channel ---------------------------------------------------------------------------------------------------------------------------

    def _read(self):
        try:
            for raw in self.proc.stdout:
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                self.events += 1
                kind = ev.get("ev")
                if kind in ("out", "started", "exit"):
                    self.progress += 1
                if kind == "out":
                    a = self.agents.get(ev.get("id"))
                    if a is not None:
                        try:
                            rec = json.loads(ev.get("line") or "")
                        except ValueError:
                            continue
                        if isinstance(rec, dict):
                            a.records.append((ev.get("t"), ev.get("sent"), rec))
                elif kind == "started":
                    a = self.agents.get(ev.get("id"))
                    if a is not None:
                        a.started = ev.get("t")
                elif kind == "exit":
                    a = self.agents.get(ev.get("id"))
                    if a is not None:
                        a.exit = ev
                elif kind in ("stats", "pss"):
                    with self._lock:
                        self._replies[ev.get("req")] = ev
                elif kind == "ready":
                    self.ready_t = ev.get("t")
                elif kind == "bye":
                    self.bye = True
        except (OSError, ValueError):
            pass

    def _send(self, obj):
        data = (json.dumps(obj, separators=(",", ":")) + "\n").encode()
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (OSError, ValueError):
            self.failed = "the control channel to the container closed"

    def request(self, op, timeout=20, **kw):
        """Ask the relay for `stats` or `pss` and wait for the answer; None on timeout (a container at its memory limit may answer late)."""
        with self._lock:
            self._req += 1
            req = self._req
        self._send(dict(kw, op=op, req=req))
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            with self._lock:
                if req in self._replies:
                    return self._replies.pop(req)
            if self.proc.poll() is not None:
                return None
            self.sleep(0.01)
        return None

    def start_agent(self, i, argv, env, cwd, stdin=False, keep=(), seed=None, home=None):
        self.agents[i] = AgentState(i)
        cmd = {"op": "start", "id": i, "argv": list(argv), "env": dict(env), "cwd": cwd, "stdin": bool(stdin), "keep": list(keep)}
        if seed and home:
            cmd["seed"], cmd["home"] = seed, home
        self._send(cmd)

    def send_line(self, i, obj):
        """Write one JSON line to agent i's standard input."""
        self._send({"op": "send", "id": i, "data": json.dumps(obj, separators=(",", ":")) + "\n"})

    def pss_kb(self, ids, timeout=60):
        """{id: kB} of the proportional memory of the agents' process groups, or {} when unreadable."""
        reply = self.request("pss", timeout=timeout, ids=list(ids))
        return {int(k): v for k, v in ((reply or {}).get("kb") or {}).items()}

    def wait_until(self, done, timeout):
        """Poll `done()` until it is true; False at the timeout, when the container is gone, or when the watch names a cause (`verdict`). The poll is cheap (a scan of the agents still pending), so
        a thousand agents cost nothing."""
        deadline = self.clock() + timeout
        while True:
            if done():
                return True
            if self.verdict is None and self.watch is not None:
                self.verdict = self.watch.check(self.observe(), self.progress)
            if self.verdict is not None:
                return False
            if self.clock() > deadline:
                return False
            if self.proc.poll() is not None and not self.bye:
                self.sleep(0.2)   # the last events may still be in the pipe
                return done()
            self.sleep(self.poll_s)

    def alive_ids(self):
        return [i for i, a in self.agents.items() if not a.dead()]

    # -- teardown ------------------------------------------------------------------------------------------------------------------------------

    def close(self):
        """Kill every agent, stop and remove the container, and delete the control files. Safe to call twice and after a failed start."""
        self._stop = True
        try:
            if self.proc is not None and self.proc.poll() is None:
                self._send({"op": "quit"})
                end = self.clock() + 15
                while self.proc.poll() is None and self.clock() < end:
                    self.sleep(0.05)
        except Exception:
            pass
        names = [self.cid] if self.cid else []
        for target in names + [self.name]:
            try:
                self._popen([self.cfg.runtime, "rm", "-f", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
            except Exception:
                pass
        try:
            if self.proc is not None and self.proc.poll() is None:
                self.proc.kill()
        except Exception:
            pass
        for f in (getattr(self.proc, "stdin", None), getattr(self.proc, "stdout", None), self._stderr):
            try:
                f.close()
            except Exception:
                pass
        import shutil
        shutil.rmtree(self._dir, ignore_errors=True)
