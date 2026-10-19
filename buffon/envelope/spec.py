# SPDX-License-Identifier: Apache-2.0
"""Spec -> argv, and the lint that holds any argv to the envelope's guarantees (docs/ENVELOPE.md)."""
import re
from dataclasses import dataclass, field

DIGEST = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")

GUARANTEES = {
    "G1": "the image is pinned by digest (name@sha256:...), never by a tag",
    "G2": "no network: --network none; the mock is a mounted unix socket",
    "G3": "a cpuset and a memory node (--cpuset-cpus, --cpuset-mems) with --cpus equal to the cpuset size",
    "G4": "--memory equals --memory-swap, and --pids-limit is set",
    "G5": "a read-only root filesystem with tmpfs HOME and TMPDIR",
    "G6": "an init process (--init)",
    "G7": "explicit ulimits (nofile, nproc, core)",
    "G8": "a non-root user, all capabilities dropped, no-new-privileges",
    "G9": "an explicit environment: variables named on the command line, never an env file",
    "G10": "nothing privileged: no --privileged, --cap-add, --device, --sysctl, host pid/ipc/network/uts, no bind of /proc, /sys, /dev or the container socket",
    "G11": "bind mounts are read-only except the declared output directory",
}

DEFAULT_ULIMITS = {"nofile": "4096:4096", "nproc": "1024:1024", "core": "0:0"}
FORBIDDEN_FLAGS = ("--privileged", "--cap-add", "--device", "--sysctl", "--security-opt=seccomp=unconfined", "--security-opt=apparmor=unconfined", "--userns=host", "--cgroupns=host")
FORBIDDEN_HOST = ("--pid", "--ipc", "--network", "--net", "--uts")
FORBIDDEN_BIND_PREFIXES = ("/proc", "/sys", "/dev", "/var/run/docker.sock", "/run/docker.sock", "/run/podman")


class EnvelopeError(ValueError):
    pass


@dataclass
class Mount:
    src: str
    dst: str
    ro: bool = True


@dataclass
class Spec:
    image: str                                   # name@sha256:<digest>
    cpuset_cpus: list                            # CPU numbers, all on one NUMA node
    cpuset_mems: str                             # the NUMA node the cpuset is on, "1"
    memory_mib: int
    pids: int = 512
    user: str = "65534:65534"
    env: dict = field(default_factory=dict)      # the whole environment of the process
    mounts: list = field(default_factory=list)   # [Mount]
    output: Mount = None                         # the one writable bind mount, if any
    tmpfs: dict = field(default_factory=lambda: {"/buffon/home": 512, "/tmp": 512})   # path -> MiB; HOME and TMPDIR live here (mode exec: runtimes unpack and run code from HOME)
    sockets: list = field(default_factory=list)  # [(host unix socket, container path)]: the mock
    workdir: str = "/buffon/home"
    ulimits: dict = field(default_factory=lambda: dict(DEFAULT_ULIMITS))
    name: str = None
    labels: dict = field(default_factory=dict)
    interactive: bool = False                    # -i: stdin stays open (an RPC pipe)
    tty: bool = False                            # -t: a terminal (the TUI workloads); needs a terminal on the caller's stdin
    cidfile: str = None                          # where the runtime writes the container id (the cgroup is found from it)

    def tmpfs_owner(self):
        """`,uid=U,gid=G` for a numeric user: a tmpfs is root-owned unless told otherwise, and the arm must be able to write its own HOME and TMPDIR."""
        uid, _, gid = self.user.partition(":")
        return f",uid={uid},gid={gid or uid}" if uid.isdigit() and (not gid or gid.isdigit()) else ""

    def validate(self):
        if not DIGEST.match(self.image or ""):
            raise EnvelopeError(f"G1: the image must be pinned by digest (name@sha256:<64 hex>), got {self.image!r}")
        if not self.cpuset_cpus:
            raise EnvelopeError("G3: a cpuset is required")
        if str(self.cpuset_mems).strip() == "":
            raise EnvelopeError("G3: cpuset_mems (the NUMA node) is required")
        if self.memory_mib < 64:
            raise EnvelopeError("G4: memory_mib must be at least 64")
        if self.pids < 16:
            raise EnvelopeError("G4: pids must be at least 16")
        uid = self.user.split(":")[0]
        if uid in ("0", "root", ""):
            raise EnvelopeError("G8: the process must not run as root")
        for key in ("nofile", "nproc", "core"):
            if key not in self.ulimits:
                raise EnvelopeError(f"G7: ulimit {key} must be explicit")
        for m in list(self.mounts) + ([self.output] if self.output else []):
            for prefix in FORBIDDEN_BIND_PREFIXES:
                if m.src == prefix or m.src.startswith(prefix + "/"):
                    raise EnvelopeError(f"G10: {m.src} must not be bind-mounted")
        for m in self.mounts:
            if not m.ro:
                raise EnvelopeError(f"G11: {m.src} is mounted writable; only the declared output directory may be")
        if self.output is not None and self.output.ro:
            raise EnvelopeError("G11: the output mount is writable by definition")
        return self


def cpuset_text(cpus):
    cpus = sorted(set(cpus))
    out, start, prev = [], None, None
    for c in cpus:
        if start is None:
            start = prev = c
        elif c == prev + 1:
            prev = c
        else:
            out.append(f"{start}-{prev}" if prev > start else str(start))
            start = prev = c
    if start is not None:
        out.append(f"{start}-{prev}" if prev > start else str(start))
    return ",".join(out)


def build_argv(spec, command, runtime="docker", detach=False):
    """The `docker run` / `podman run` argument vector for `command` (a list) in the envelope."""
    spec.validate()
    argv = [runtime, "run", "--init", "--network", "none", "--read-only", "--user", spec.user, "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--cpuset-cpus", cpuset_text(spec.cpuset_cpus), "--cpuset-mems", str(spec.cpuset_mems), "--cpus", str(len(set(spec.cpuset_cpus))),
            "--memory", f"{spec.memory_mib}m", "--memory-swap", f"{spec.memory_mib}m", "--pids-limit", str(spec.pids), "--workdir", spec.workdir]
    argv.append("--detach" if detach else "--rm")
    if spec.name:
        argv += ["--name", spec.name]
    if spec.cidfile:
        argv += ["--cidfile", spec.cidfile]
    if spec.interactive:
        argv.append("--interactive")
    if spec.tty:
        argv.append("--tty")
    for key in sorted(spec.ulimits):
        argv += ["--ulimit", f"{key}={spec.ulimits[key]}"]
    for path in sorted(spec.tmpfs):
        argv += ["--tmpfs", f"{path}:rw,exec,nosuid,nodev,size={spec.tmpfs[path]}m{spec.tmpfs_owner()}"]
    for m in spec.mounts:
        argv += ["--mount", f"type=bind,source={m.src},target={m.dst},readonly"]
    if spec.output is not None:
        argv += ["--mount", f"type=bind,source={spec.output.src},target={spec.output.dst}"]
    for host, inside in spec.sockets:
        argv += ["--mount", f"type=bind,source={host},target={inside}"]
    for key in sorted(spec.env):
        argv += ["--env", f"{key}={spec.env[key]}"]
    for key in sorted(spec.labels):
        argv += ["--label", f"{key}={spec.labels[key]}"]
    argv += [spec.image] + list(command)
    problems = lint(argv)
    if problems:   # the builder and the lint must agree; a disagreement is a bug here, not in the caller
        raise EnvelopeError("internal: the built argv violates its own guarantees: " + "; ".join(problems))
    return argv


def _flags(argv):
    """{flag: [values]} for a docker/podman run argv, up to the image; also returns the index of the image."""
    values, i = {}, 2
    takes = {"--network", "--net", "--user", "-u", "--cpuset-cpus", "--cpuset-mems", "--cpus", "--memory", "-m", "--memory-swap", "--pids-limit", "--workdir", "-w", "--name", "--ulimit",
             "--volumes-from", "--gpus", "--runtime", "--tmpfs", "--mount", "-v", "--volume", "--env", "-e", "--env-file", "--label", "-l", "--cap-drop", "--cap-add", "--security-opt", "--device", "--sysctl", "--pid", "--ipc",
             "--uts", "--userns", "--cgroupns", "--entrypoint", "--hostname", "-h", "--platform", "--restart", "--stop-timeout", "--cidfile", "--log-driver", "--log-opt", "--stop-signal", "--pull"}
    while i < len(argv):
        a = argv[i]
        if not a.startswith("-"):
            return values, i
        if "=" in a and a.startswith("--"):
            k, _, v = a.partition("=")
            values.setdefault(k, []).append(v)
        elif a in takes and i + 1 < len(argv):
            values.setdefault(a, []).append(argv[i + 1])
            i += 1
        else:
            values.setdefault(a, []).append(True)
        i += 1
    return values, len(argv)


def lint(argv):
    """Guarantee violations of any `docker|podman run` argv ([] when it keeps all of them). Names the guarantee in each message."""
    if len(argv) < 3 or argv[1] != "run":
        return ["not a `run` command"]
    flags, image_at = _flags(argv)
    problems = []
    image = argv[image_at] if image_at < len(argv) else ""
    if not DIGEST.match(image):
        problems.append(f"G1: image {image or '(none)'} is not pinned by digest")
    net = (flags.get("--network") or flags.get("--net") or [None])[-1]
    if net != "none":
        problems.append(f"G2: network is {net or 'the default bridge'}, not none")
    cpus, cpuset, mems = flags.get("--cpus"), flags.get("--cpuset-cpus"), flags.get("--cpuset-mems")
    if not cpuset or not mems:
        problems.append("G3: --cpuset-cpus and --cpuset-mems are both required")
    else:
        from ..site import parse_cpus
        try:
            n = len(set(parse_cpus(cpuset[-1])))
            if not cpus or float(cpus[-1]) != n:
                problems.append(f"G3: --cpus is {cpus[-1] if cpus else 'unset'} but the cpuset has {n} CPUs: it must be equal")
        except ValueError:
            problems.append(f"G3: unreadable cpuset {cpuset[-1]!r}")
    memory, swap = (flags.get("--memory") or flags.get("-m")), flags.get("--memory-swap")
    if not memory or not swap or memory[-1] != swap[-1]:
        problems.append("G4: --memory and --memory-swap must both be set and equal")
    if not flags.get("--pids-limit"):
        problems.append("G4: --pids-limit is required")
    if "--read-only" not in flags:
        problems.append("G5: the root filesystem must be --read-only")
    tmp = [t for t in flags.get("--tmpfs", []) if isinstance(t, str)]
    if not any(t.startswith("/tmp") for t in tmp) or len(tmp) < 2:
        problems.append("G5: tmpfs HOME and TMPDIR are required (at least two --tmpfs, one of them /tmp)")
    if "--init" not in flags:
        problems.append("G6: --init is required")
    ulimits = {u.split("=")[0] for u in flags.get("--ulimit", []) if isinstance(u, str)}
    for key in ("nofile", "nproc", "core"):
        if key not in ulimits:
            problems.append(f"G7: --ulimit {key}=... is required")
    user = (flags.get("--user") or flags.get("-u") or [""])[-1]
    if not user or str(user).split(":")[0] in ("0", "root"):
        problems.append("G8: a non-root --user is required")
    if "ALL" not in (flags.get("--cap-drop") or []):
        problems.append("G8: --cap-drop ALL is required")
    if "no-new-privileges" not in (flags.get("--security-opt") or []) and "no-new-privileges:true" not in (flags.get("--security-opt") or []):
        problems.append("G8: --security-opt no-new-privileges is required")
    if "--env-file" in flags:
        problems.append("G9: --env-file is not allowed: name every variable with --env")
    for value in (flags.get("--env") or []) + (flags.get("-e") or []):
        if isinstance(value, str) and "=" not in value:
            problems.append(f"G9: --env {value} without a value passes the host's variable through: name NAME=value")
    for flag in ("--privileged", "--cap-add", "--device", "--sysctl", "--userns", "--cgroupns", "--volumes-from", "--gpus", "--runtime"):
        if flag in flags:
            problems.append(f"G10: {flag} is not allowed")
    for flag in ("--pid", "--ipc", "--uts"):
        if (flags.get(flag) or [""])[-1] == "host":
            problems.append(f"G10: {flag}=host is not allowed")
    for opt in flags.get("--security-opt", []):
        if isinstance(opt, str) and "unconfined" in opt:
            problems.append(f"G10: --security-opt {opt} is not allowed")
    binds = [v for v in flags.get("--mount", []) if isinstance(v, str) and "type=bind" in v] + [v for f in ("-v", "--volume") for v in flags.get(f, []) if isinstance(v, str)]
    writable = sockets = 0
    for b in binds:
        src = (re.search(r"source=([^,]+)", b) or re.search(r"src=([^,]+)", b) or [None, b.split(":")[0]])[1]
        if any(src == p or src.startswith(p + "/") for p in FORBIDDEN_BIND_PREFIXES):
            problems.append(f"G10: {src} must not be bind-mounted")
        ro = "readonly" in b.split(",") or ",ro" in b or b.endswith(":ro") or "readonly=true" in b
        sock = src.endswith(".sock")
        if sock:
            sockets += 1
        elif not ro:
            writable += 1
    if sockets > 1:
        problems.append(f"G11: {sockets} socket bind mounts; only the mock's one socket is allowed")
    if writable > 1:
        problems.append(f"G11: {writable} writable bind mounts; only the one declared output directory may be writable")
    return problems


def isolation_stamp(mode):
    """What a result carries about its isolation: container is the default; none is explicit and never comparable."""
    if mode == "container":
        return {"isolation": "container", "comparable": True}
    if mode == "none":
        return {"isolation": "none", "comparable": False, "stamp": "uncontained, not comparable"}
    raise EnvelopeError(f"isolation must be container or none, got {mode!r}")
