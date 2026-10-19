# SPDX-License-Identifier: Apache-2.0
"""ContainerMeter: the meter that runs a process tree inside the shared container envelope (buffon/envelope) and measures it from the container's cgroup.

`cgroup.new_meter()` returns one when `cgroup.CONTAINER` is set (the engine does that for --isolation container). The workspace root is bind-mounted at the same absolute path (arm install trees
read-only; the harness work directory the one writable mount) so argv, env and cwd need no translation. The mock endpoint is a unix socket mounted into the network-less container and a relay
(envelope/relay) at the arm's port forwards to it. The container's cgroup disappears when it stops, so the final counters come from the relay, which reads them the instant the child exits;
the relay's own CPU time is subtracted so a reported CPU time is the arm's."""
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field

from ..envelope import Mount, Spec, build_argv
from ..envelope.spec import DEFAULT_ULIMITS
from . import cgroup

RELAY_DIR_IN_CONTAINER = "/buffon/bin"
SOCKET_IN_CONTAINER = "/buffon/mock.sock"
SEED_IN_CONTAINER = "/buffon/seed"


def container_user():
    """The arm runs as the invoking user's uid:gid (never root: G8), so it can traverse the workspace (mode 0700 from mkdtemp), write the one writable mount and own its tmpfs HOME; a root caller gets the unprivileged 65534:65534."""
    uid, gid = os.getuid(), os.getgid()
    return f"{uid}:{gid}" if uid != 0 else "65534:65534"


@dataclass
class ContainerConfig:
    image: str                       # name@sha256:...
    runtime: str                     # docker | podman
    cpuset_cpus: list
    cpuset_mems: str
    memory_mib: int
    ro_paths: list                   # bind-mounted read-only at the same path (the workspace root with the arm install trees)
    rw_dir: str                      # the one writable bind mount (the harness work directory)
    socket_path: str                 # the mock's unix socket on the host
    mock_port: int                   # the port the arm's config names; the relay listens on it inside
    relay_dir: str                   # directory holding the built `relay` binary
    pids: int = 1024
    null_run_ms: float = 0.0         # the envelope's own cost, measured the way an arm is run (docker run behind the relay, /bin/true); reported, never subtracted
    home_mib: int = 1024            # size of the tmpfs HOME (an arm with a large first-start state, omp, needs room)
    extra: dict = field(default_factory=dict)


def container_ulimits():
    """The envelope's explicit ulimits (G7) with nproc set to the invoking user's own limit. RLIMIT_NPROC counts every process of the uid on the host, not of the container, and the arm
    runs as the invoking uid: a fixed 1024 failed every exec (`exec /sbin/docker-init: resource temporarily unavailable`) on a host where that user already runs more than 1024 threads.
    The container's own process count is bounded by --pids-limit (G4)."""
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
    text = lambda v: "-1" if v == resource.RLIM_INFINITY else str(v)
    return dict(DEFAULT_ULIMITS, nproc=f"{text(soft)}:{text(hard)}")


class ContainerMeter(cgroup.CgroupMeter):
    mode = "container"

    def __init__(self, config, run=subprocess.Popen, clock=time.monotonic, sleep=time.sleep):
        super().__init__(path="", holder=None, mode="container")
        self.config, self._popen, self.clock, self.sleep = config, run, clock, sleep
        self.cid = None
        self.final = None
        self.start_usage_usec = None
        self.relay_cpu_ms = 0.0
        self.has_memory_peak = True
        self._dir = tempfile.mkdtemp(prefix="buffon-ct-", dir=config.rw_dir)
        self._stats = os.path.join(self._dir, "relay.json")
        self._cidfile = os.path.join(self._dir, "cid")
        self.argv = None

    def popen(self, argv, **kwargs):
        c = self.config
        env = dict(kwargs.pop("env", None) or {})
        cwd = kwargs.pop("cwd", None) or c.rw_dir
        stdin = kwargs.get("stdin")
        tty = False
        try:
            fd = stdin.fileno() if hasattr(stdin, "fileno") else stdin
            tty = isinstance(fd, int) and fd >= 0 and os.isatty(fd)
        except (OSError, ValueError):
            tty = False
        home = env.get("HOME")
        mounts = [Mount(p, p) for p in c.ro_paths] + [Mount(c.relay_dir, RELAY_DIR_IN_CONTAINER)]
        tmpfs = {"/tmp": 512}
        seeding = []
        if not home:
            tmpfs["/buffon/home"] = c.home_mib
        else:   # HOME is a tmpfs at the same path: the harness-written HOME is mounted read-only as a seed and the relay copies it in before the arm starts (Run Rules 9)
            mounts.append(Mount(home, SEED_IN_CONTAINER))
            tmpfs[home] = c.home_mib
            seeding = ["-seed", SEED_IN_CONTAINER, "-home", home]
        spec = Spec(image=c.image, cpuset_cpus=c.cpuset_cpus, cpuset_mems=c.cpuset_mems, memory_mib=c.memory_mib, pids=c.pids, env=env, mounts=mounts, output=Mount(c.rw_dir, c.rw_dir, False),
                    sockets=[(c.socket_path, SOCKET_IN_CONTAINER)], user=container_user(), ulimits=container_ulimits(), workdir=cwd, tmpfs=tmpfs, interactive=stdin is not None, tty=tty, cidfile=self._cidfile)
        command = [f"{RELAY_DIR_IN_CONTAINER}/relay", "-listen", f"127.0.0.1:{c.mock_port}", "-unix", SOCKET_IN_CONTAINER, "-stats", self._stats] + seeding + ["--"] + list(argv)
        self.argv = build_argv(spec, command, runtime=c.runtime)
        for key in ("preexec_fn", "start_new_session", "process_group"):
            kwargs.pop(key, None)
        env_cli = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/")}
        self.child = self._popen(self.argv, env=env_cli, **kwargs)
        self._find_cgroup()
        if self.path and not self._sampling:
            self.start_sampler()
        return self.child

    def start_ns(self):
        """CLOCK_MONOTONIC (host clock: a container has no time namespace) at the instant the relay started the arm, or None before it has. Every interval of a sample runs from here, so the container's creation, which varies per sample by more than the arm's own time, is not in it."""
        try:
            with open(self._stats + ".start") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def end_ns(self):
        """CLOCK_MONOTONIC at the instant the arm exited, from the relay's final stats; None before the container ends."""
        try:
            with open(self._stats) as f:
                value = json.load(f).get("child_end_ns")
            return int(value) if value else None
        except (OSError, ValueError):
            return None

    def _find_cgroup(self, timeout=10.0):
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            try:
                with open(self._cidfile) as f:
                    cid = f.read().strip()
            except OSError:
                cid = ""
            if cid:
                self.cid = cid
                for path in (f"/sys/fs/cgroup/system.slice/{self.config.runtime}-{cid}.scope", f"/sys/fs/cgroup/machine.slice/libpod-{cid}.scope"):
                    if os.path.isdir(path):
                        self.path = path
                        return
            if self.child.poll() is not None:
                return
            self.sleep(0.01)

    def _load_final(self):
        if self.final is not None:
            return self.final
        try:
            with open(self._stats) as f:
                doc = json.load(f)
        except (OSError, ValueError):
            return None
        self.relay_cpu_ms = float(doc.get("user_ms", 0)) + float(doc.get("system_ms", 0))
        self.final = doc.get("cgroup") or {}
        # The container's CPU before the relay started the arm (runtime setup, init, relay start, HOME seeding) is not the arm's: start from the relay's reading at that instant.
        self.start_usage_usec = doc.get("start_cgroup_usage_usec")
        if self.start_usage_usec is not None:
            self.relay_cpu_ms -= float(doc.get("start_relay_cpu_ms", 0))
        return self.final

    def cpu_ms(self):
        final = self._load_final()
        if final and (final.get("cpu.stat") or {}).get("usage_usec") is not None:
            return max(0.0, (final["cpu.stat"]["usage_usec"] - (self.start_usage_usec or 0)) / 1000 - self.relay_cpu_ms)
        return super().cpu_ms() if self.path else 0.0

    def throttled(self):
        """True when the container's CPU limit throttled it (nr_throttled > 0): the sample is invalid."""
        final = self._load_final()
        stat = (final or {}).get("cpu.stat") or (cgroup.parse_cpu_stat(cgroup._read(os.path.join(self.path, "cpu.stat"))) if self.path and os.path.isdir(self.path) else {})
        return bool(stat.get("nr_throttled"))

    def peak_mem_mib(self):
        final = self._load_final()
        if final and final.get("memory.peak") is not None:
            return final["memory.peak"] / 1048576
        return super().peak_mem_mib() if self.path else None

    def pids_peak(self):
        final = self._load_final()
        if final and final.get("pids.peak") is not None:
            return final["pids.peak"]
        return super().pids_peak() if self.path else None

    def kill(self):
        if self.cid:
            self._popen([self.config.runtime, "kill", self.cid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()

    def close(self):
        self._sampling = False
        self._load_final()
        cgroup.notify_closing(self)
        self.kill()
        if self.cid:
            self._popen([self.config.runtime, "rm", "-f", self.cid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
        cgroup.egress.OBSERVED |= self.egress


def _image_for(default_only=True):
    import tomllib
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(here, "images", "images.toml"), "rb") as f:
        return tomllib.load(f)["default"]


def build_relay(ws, repo_root):
    """Compile envelope/relay with the pinned Go toolchain (CGO off, trimpath) into the workspace; returns (directory, sha256 of the binary)."""
    import hashlib
    out_dir = os.path.join(ws.root, "relay")
    os.makedirs(out_dir, exist_ok=True)
    env = ws.base_env(["go"])
    env.update({"CGO_ENABLED": "0", "GOTOOLCHAIN": "local", "GOFLAGS": ""})
    done = subprocess.run(["go", "build", "-trimpath", "-buildvcs=false", "-ldflags", "-s -w", "-o", os.path.join(out_dir, "relay"), "."], cwd=os.path.join(repo_root, "envelope", "relay"),
                          env=env, capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise RuntimeError("building the envelope relay failed: " + done.stderr.strip()[-400:])
    with open(os.path.join(out_dir, "relay"), "rb") as f:
        return out_dir, hashlib.sha256(f.read()).hexdigest()


def measure_null_run(cfg, runs=5, run=subprocess.Popen, clock=time.monotonic):
    """Median wall ms of `/bin/true` started exactly as an arm is (the same ContainerMeter: `docker run` in the foreground behind the relay). Envelope.null_run polls `docker inspect` and has that command's latency as resolution, so it cannot be the figure subtracted from these intervals."""
    walls = []
    for _ in range(runs):
        meter = ContainerMeter(cfg, run=run, clock=clock)
        try:
            t0 = clock()
            proc = meter.popen(["/bin/true"], env={}, cwd=cfg.rw_dir, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait(timeout=120)
            walls.append((clock() - t0) * 1000.0)
        finally:
            meter.close()
    walls.sort()
    return round(walls[len(walls) // 2], 3)


def configure(ws, plan, repo_root, server, socket_path, cpus, mems, memory_mib=4096):
    """Set `cgroup.CONTAINER` for the run and return what raw.json records about the envelope. Raises when the runtime or the image is not available."""
    from ..envelope import Envelope, find_runtime
    runtime = find_runtime()
    image = _image_for()
    env = Envelope(runtime)
    env.ensure_image(image)
    relay_dir, relay_sha = build_relay(ws, repo_root)
    cfg = ContainerConfig(image=image, runtime=runtime, cpuset_cpus=list(cpus), cpuset_mems=str(mems), memory_mib=memory_mib, ro_paths=[ws.root], rw_dir=ws.work,
                          socket_path=socket_path, mock_port=server.port, relay_dir=relay_dir)
    cgroup.CONTAINER = cfg
    record = {"runtime": runtime, "image": image, "cpuset_cpus": list(cpus), "cpuset_mems": str(mems), "memory_mib": memory_mib, "pids": cfg.pids, "relay_sha256": relay_sha,
              "home": "tmpfs seeded from the harness HOME (read-only mount + relay copy)", "network": "none; the mock is a mounted unix socket"}
    record["null_run_ms"] = cfg.null_run_ms = measure_null_run(cfg)
    return record
