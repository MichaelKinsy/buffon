# SPDX-License-Identifier: Apache-2.0
"""Host and node facts: what a reader needs to judge whether two runs are comparable. Written to facts.json in every run directory.

Everything is read from /proc, /sys and the cgroup filesystem of the machine the session runs on, so the same code describes a laptop, a bare-metal host
and a pod. Nothing here names a host: node and pod names come from the NODE_NAME and POD_NAME variables the Kubernetes backend sets, when it sets them.
"""
import hashlib
import os
import platform
import subprocess
import time

from ..site import format_cpus

SYS_CPU = "/sys/devices/system/cpu"


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def _cmd(argv, cwd=None):
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=30, cwd=cwd)
        return (out.stdout.strip() or out.stderr.strip()).splitlines()[0] if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return _cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor() or None


def cpu_flags():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith(("flags", "Features")):
                    return line.split(":", 1)[1].split()
    except OSError:
        pass
    return []


def virtual_machine(flags=None, detect=None):
    """The machine's own sign that it is a virtual machine: the CPU's `hypervisor` flag (x86) or `systemd-detect-virt --vm` naming one (any architecture); a string saying which, else None."""
    if "hypervisor" in (cpu_flags() if flags is None else flags):
        return "cpu flag hypervisor"
    kind = (detect or (lambda: _cmd(["systemd-detect-virt", "--vm"])))()
    return f"systemd-detect-virt: {kind}" if kind and kind != "none" else None


def mem_gib():
    text = _read("/proc/meminfo")
    if text:
        return round(int(text.splitlines()[0].split()[1]) / 1048576, 1)
    out = _cmd(["sysctl", "-n", "hw.memsize"])
    return round(int(out) / 2**30, 1) if out and out.isdigit() else None


def allowed_cpus():
    """CPUs this process may run on (the cgroup cpuset and any affinity)."""
    try:
        return sorted(os.sched_getaffinity(0))
    except AttributeError:
        return list(range(os.cpu_count() or 1))


def governor(cpu):
    return _read(f"{SYS_CPU}/cpu{cpu}/cpufreq/scaling_governor")


def cur_mhz(cpu):
    khz = _read(f"{SYS_CPU}/cpu{cpu}/cpufreq/scaling_cur_freq")
    return int(khz) / 1000 if khz and khz.isdigit() else None


def fixed_clock(gov, cpu=None):
    """True when a CPU's clock does not follow load: no cpufreq (a VM or a pod that cannot see it), `performance`, or min == max."""
    if gov is None:
        return None  # unknown: the node does not expose cpufreq
    if gov in ("performance", "userspace"):
        return True
    if cpu is not None:
        lo, hi = _read(f"{SYS_CPU}/cpu{cpu}/cpufreq/scaling_min_freq"), _read(f"{SYS_CPU}/cpu{cpu}/cpufreq/scaling_max_freq")
        if lo and lo == hi:
            return True
    return False


def smt_siblings(cpu):
    text = _read(f"{SYS_CPU}/cpu{cpu}/topology/thread_siblings_list")
    if not text:
        return [cpu]
    from ..site import parse_cpus
    return parse_cpus(text)


def cgroup_files():
    """cpu.max, memory.max, cpuset.cpus.effective and cpu.stat of this process's cgroup (v2)."""
    path = None
    for line in (_read("/proc/self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            path = "/sys/fs/cgroup" + line[3:]
    out = {}
    for name in ("cpu.max", "memory.max", "cpuset.cpus.effective"):
        for base in (path, "/sys/fs/cgroup"):
            if base and (v := _read(os.path.join(base, name))) is not None:
                out[name] = v
                break
    for base in (path, "/sys/fs/cgroup"):
        if base and (stat := _read(os.path.join(base, "cpu.stat"))):
            out["cpu.stat"] = {k: int(v) for k, _, v in (ln.partition(" ") for ln in stat.splitlines()) if v.strip().isdigit()}
            break
    return out


def container():
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
        return "container"
    return None


# A bundle (buffon/backend/bundle.py) carries the checkout's files without .git; these top-level entries are its cache and programs, not the runner's files.
BUNDLE_PAYLOAD = ("cache/", "npm-cache/", "bin/")


def runner_checkout(runner_repo):
    """The runner's commit, tree and whether its files differ from them. A git checkout answers with git; a bundle (no .git, a bundle.json) answers with the commit and
    tree it was built from, and is dirty when it was built from a dirty checkout or a file of the checkout differs from its ARTIFACTS.sha256 or is missing;
    runner_bundle_sha256 then names the bundle."""
    if not os.path.exists(os.path.join(runner_repo, ".git")) and os.path.isfile(os.path.join(runner_repo, "bundle.json")):
        return bundle_checkout(runner_repo)
    dirty = bool(_cmd(["git", "status", "--porcelain", "--untracked-files=no"], cwd=runner_repo))
    diff_sha256 = None
    if dirty:  # the commit alone does not describe the code that ran: record what differs from it
        try:
            diff = subprocess.run(["git", "diff", "HEAD", "--binary"], capture_output=True, timeout=60, cwd=runner_repo).stdout
            diff_sha256 = hashlib.sha256(diff).hexdigest()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"runner_commit": _cmd(["git", "rev-parse", "HEAD"], cwd=runner_repo), "runner_tree": _cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=runner_repo),
            "runner_dirty": dirty, "runner_diff_sha256": diff_sha256}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def bundle_checkout(root):
    import json
    out = {"runner_commit": None, "runner_tree": None, "runner_dirty": True, "runner_diff_sha256": None, "runner_bundle_sha256": None}
    try:
        with open(os.path.join(root, "bundle.json")) as f:
            meta = json.load(f)
        sums = os.path.join(root, "ARTIFACTS.sha256")
        with open(sums) as f:
            lines = f.read().splitlines()
        out["runner_bundle_sha256"] = _sha256(sums)
    except (OSError, ValueError):
        return out
    out["runner_commit"], out["runner_tree"] = meta.get("commit"), meta.get("tree")
    differs = []
    for line in lines:
        digest, sep, rel = line.partition("  ")
        if not sep or rel.startswith(BUNDLE_PAYLOAD):
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path) or _sha256(path) != digest:
            differs.append(rel)
    # A bundle built from a dirty checkout (allow_dirty) carries files that are not its commit's; one whose bundle.json does not say it was clean is dirty too.
    out["runner_diff_sha256"] = meta.get("diff_sha256")
    out["runner_dirty"] = bool(differs) or not (out["runner_commit"] and out["runner_tree"]) or meta.get("dirty") is not False
    if differs:
        out["runner_differs"] = differs[:20]
    return out


def collect(runner_repo, pinned_cpus=(), mock_cpus=(), extra=None):
    """The facts block. `runner_repo` is Buffon checkout, for its commit and tree."""
    allowed = allowed_cpus()
    measured = list(pinned_cpus) or allowed
    govs = {c: governor(c) for c in measured}
    smt = _read(f"{SYS_CPU}/smt/active")
    facts = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "os": f"{platform.system()} {platform.release()}",
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpu_model": cpu_model(),
        "cpu_flags": " ".join(cpu_flags()),
        "logical_cpus": os.cpu_count(),
        "cpus_allowed": format_cpus(allowed),
        "pinned_cpus": format_cpus(pinned_cpus) if pinned_cpus else None,
        "mock_cpus": format_cpus(mock_cpus) if mock_cpus else None,
        "memory_gib": mem_gib(),
        "smt_active": None if smt is None else smt == "1",
        "governors": {str(c): g for c, g in govs.items()},
        "fixed_clock": all(fixed_clock(g, c) is not False for c, g in govs.items()) if pinned_cpus or govs else None,
        "mhz": {str(c): cur_mhz(c) for c in measured[:16]},
        "turbo_disabled": _read(f"{SYS_CPU}/intel_pstate/no_turbo"),
        "boost": _read(f"{SYS_CPU}/cpufreq/boost"),
        "cgroup": cgroup_files(),
        "container": container(),
        "node": os.environ.get("NODE_NAME"),
        "pod": os.environ.get("POD_NAME"),
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        "python": platform.python_version(),
        "go": _cmd(["go", "version"]),
        "node_js": _cmd(["node", "--version"]),
        **runner_checkout(runner_repo),
    }
    if extra:
        facts.update(extra)
    return facts
