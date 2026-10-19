# SPDX-License-Identifier: Apache-2.0
"""What this machine is, and the site profile `buffon up` writes for it. Nothing here names a host: the profile lives in the user's buffon home, never in the repository."""
import json
import os
import platform
import shutil
import sys

from .. import site as sitelib
from ..arms import manifest
from ..runner import facts as factlib, perfcount


def home():
    """Where `buffon up` keeps its profile, caches, runs and the built site: $BUFFON_HOME, else $XDG_DATA_HOME/buffon, else ~/.local/share/buffon."""
    return os.environ.get("BUFFON_HOME") or os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share"), "buffon")


def paths(base=None):
    base = base or home()
    return {"home": base, "site_profile": os.path.join(base, "sites", "this-machine.toml"), "cache": os.path.join(base, "cache"), "npm_cache": os.path.join(base, "npm-cache"),
            "work": os.path.join(base, "work"), "runs": os.path.join(base, "runs"), "site": os.path.join(base, "site"), "timings": os.path.join(base, "timings.json"),
            "machine": os.path.join(base, "machine.json"), "probe": os.path.join(base, "probe.json")}


NODE_MIN = 18


def node_problem(which=shutil.which, run=None):
    """Why the dashboard cannot be built here (it renders its formulas with Node), or None when Node NODE_MIN or newer is on PATH."""
    import subprocess
    node = which("node")
    if not node:
        return f"Node is not installed: install Node {NODE_MIN} or newer (the dashboard needs it)"
    try:
        text = (run or subprocess.run)([node, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        major = int(text.lstrip("v").split(".")[0])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return f"cannot read the version of {node}: install Node {NODE_MIN} or newer (the dashboard needs it)"
    if major < NODE_MIN:
        return f"Node {text} is too old: install Node {NODE_MIN} or newer (the dashboard needs it)"
    return None


def _cores(allowed):
    """The allowed CPUs grouped by physical core: [[cpu, sibling, ...], ...] in CPU order. Without SMT information every CPU is a core."""
    seen, out = set(), []
    for c in allowed:
        if c in seen:
            continue
        group = sorted({c, *[s for s in factlib.smt_siblings(c) if s in allowed]})
        seen.update(group)
        out.append(group)
    return out


def detect(allowed=None):
    """The machine record: OS, CPUs (total, allowed to this process, threads per core), memory, counters, container runtime. Every probe tolerates a platform that lacks it."""
    can_pin = hasattr(os, "sched_setaffinity")
    allowed = list(allowed) if allowed is not None else (factlib.allowed_cpus() if can_pin else list(range(os.cpu_count() or 1)))
    cores = _cores(allowed) if can_pin else [[c] for c in allowed]
    try:
        perf = perfcount.probe()
    except Exception as error:   # a platform without the syscall
        perf = {"available": False, "reason": f"no instruction counters: {error}"}
    runtime = next((n for n in ("docker", "podman") if shutil.which(n)), None)
    try:
        governor = factlib.governor(allowed[0]) if allowed else None
    except Exception:
        governor = None
    return {"os": platform.system(), "arch": platform.machine(), "platform": manifest.host_platform(), "python": platform.python_version(), "cpu_model": factlib.cpu_model(),
            "cpus_total": os.cpu_count() or 1, "cpus_allowed": allowed, "cores": cores, "smt": any(len(c) > 1 for c in cores), "can_pin": can_pin, "mem_gib": factlib.mem_gib(),
            "virtual_machine": bool(factlib.virtual_machine()), "governor": governor, "counters": {"available": bool(perf.get("available")), "why": perf.get("reason")},
            "container_runtime": runtime, "git": bool(shutil.which("git")), "npm": bool(shutil.which("npm"))}


def choose_cpus(machine, pin=True):
    """(harness CPUs, mock CPUs): whole physical cores, from the top of the allowed set (CPU 0 and its neighbours keep the operating system's housekeeping).

    One core for the harness and one for the runner and the mock; with SMT both threads of a core, so no sibling of a bench CPU is left running other work. Fewer than three
    cores, or a platform that cannot pin: nothing is pinned and the run says so (it is labelled Shared)."""
    cores = machine["cores"]
    if not pin or not machine["can_pin"] or len(cores) < 3:
        return [], []
    return sorted(cores[-2]), sorted(cores[-1])


def profile_text(machine, paths_, pin=True):
    harness, mock = choose_cpus(machine, pin)
    pin = "preferred" if harness else "none"
    lines = ["# Written by `buffon up` for this machine. Edit it, or delete it to detect the machine again.", "[site]", 'name = "this-machine"', 'backend = "local"', 'hardware = "shared"',
             'notes = "detected by buffon up"', "", "[local]"]
    if harness:
        lines += [f'cpus = "{sitelib.format_cpus(harness)}"', f'mock_cpus = "{sitelib.format_cpus(mock)}"']
    lines += [f'pinning = "{pin}"', f'cache_dir = "{paths_["cache"]}"', f'work_dir = "{paths_["work"]}"', 'meter = "auto"']
    if machine["virtual_machine"] and machine["governor"] is None:
        lines.append('clock_claim = "hypervisor"')
    return "\n".join(lines) + "\n"


def ensure_profile(machine, paths_, pin=True):
    """Write the site profile for this machine (once): an existing profile that still loads and names only CPUs this process may use is kept. Returns (path, loaded Site, written?)."""
    path = paths_["site_profile"]
    for d in (paths_["home"], os.path.dirname(path), paths_["cache"], paths_["work"], paths_["npm_cache"], paths_["runs"]):
        os.makedirs(d, exist_ok=True)
    if os.path.exists(path):
        try:
            s = sitelib.load(path)
            if set(s.local.cpus) | set(s.local.mock_cpus) <= set(machine["cpus_allowed"]) and (pin or not s.local.cpus):
                return path, s, False
        except sitelib.SiteError:
            pass
    with open(path, "w") as f:
        f.write(profile_text(machine, paths_, pin))
    with open(paths_["machine"], "w") as f:
        json.dump(machine, f, indent=1)
    return path, sitelib.load(path), True


def describe(machine):
    """One line: `Linux x86_64, 16 CPUs (SMT), 31.2 GiB, counters yes, docker`."""
    cpus = f"{len(machine['cores'])} cores" + (f" x {len(machine['cores'][0])} threads (SMT)" if machine["smt"] else "")
    return (f"{machine['os']} {machine['arch']}, {cpus}, {machine['mem_gib']} GiB, instruction counters {'yes' if machine['counters']['available'] else 'no (CPU time is the headline)'}, "
            f"container runtime {machine['container_runtime'] or 'none'}" + (", virtual machine" if machine["virtual_machine"] else ""))
