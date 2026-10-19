# SPDX-License-Identifier: Apache-2.0
"""`host.json`: the platform specification every run carries (Run Rules 5). Every REQUIRED key is present; a value the machine cannot provide is null and its reason is in
`unavailable`. `buffon verify` rejects a run directory whose host.json lacks a key or leaves a null without a reason."""
import glob
import hashlib
import os
import platform
import shutil
import subprocess
import time

from . import facts as factlib

REQUIRED = ("generated_utc", "kernel", "machine", "cpu_model", "microcode", "mitigations", "cpu_mhz_max", "turbo", "smt", "cstates", "thp", "aslr", "numa", "irq", "clocksource",
            "cgroup", "container_runtime", "boot_id", "bench_cpus", "mock_cpus", "memory_gib")
SYS = "/sys/devices/system"


def _read(path):
    return factlib._read(path)


def _microcode():
    for line in (_read("/proc/cpuinfo") or "").splitlines():
        if line.startswith("microcode"):
            return line.partition(":")[2].strip()
    return None


def _mitigations():
    out = {}
    for path in sorted(glob.glob(f"{SYS}/cpu/vulnerabilities/*")):
        value = _read(path)
        if value is not None:
            out[os.path.basename(path)] = value
    return out or None


def _numa(cpus):
    nodes = {}
    for path in glob.glob(f"{SYS}/node/node[0-9]*"):
        text = _read(os.path.join(path, "cpulist"))
        if text:
            from ..site import parse_cpus
            for cpu in parse_cpus(text):
                nodes[cpu] = int(os.path.basename(path)[4:])
    return {"node_of_cpu": {str(c): nodes.get(c) for c in cpus}, "nodes": sorted(set(nodes.values())) or None}


def _cstates(cpu):
    states = []
    for path in sorted(glob.glob(f"{SYS}/cpu/cpu{cpu}/cpuidle/state[0-9]*"), key=lambda p: int(p.rsplit("state", 1)[1])):
        states.append({"name": _read(os.path.join(path, "name")), "disabled": _read(os.path.join(path, "disable"))})
    return states or None


def _cgroup_chain():
    """cpu.max of this process's cgroup and every ancestor: any value but `max` is a quota on the measurement."""
    path = None
    for line in (_read("/proc/self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            path = line[3:]
    if path is None:
        return None
    chain, cur = [], path
    while True:
        chain.append({"path": cur, "cpu.max": _read(f"/sys/fs/cgroup{cur}/cpu.max"), "cpuset.cpus.partition": _read(f"/sys/fs/cgroup{cur}/cpuset.cpus.partition")})
        if cur in ("/", ""):
            break
        cur = os.path.dirname(cur) or "/"
    return chain


def _runtime():
    docker = shutil.which("docker")
    if not docker:
        return None
    try:
        text = subprocess.run([docker, "info", "--format", "{{.ServerVersion}}|{{.CgroupDriver}}|{{.Driver}}|{{.DefaultRuntime}}|{{json .SecurityOptions}}"], capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    parts = text.split("|")
    if len(parts) < 5:
        return None
    return {"runtime": "docker", "version": parts[0], "cgroup_driver": parts[1], "storage_driver": parts[2], "default_runtime": parts[3], "security_options": parts[4]}


def collect(bench_cpus, mock_cpus=()):
    from ..site import parse_cpus  # noqa: F401  (imported for the CPU-list helpers used above)
    cpus = list(bench_cpus)
    first = cpus[0] if cpus else None
    doc = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpu_model": factlib.cpu_model(),
        "microcode": _microcode(),
        "mitigations": _mitigations(),
        "cpu_mhz_max": None if first is None else (lambda v: int(v) // 1000 if v and v.isdigit() else None)(_read(f"{SYS}/cpu/cpu{first}/cpufreq/cpuinfo_max_freq")),
        "turbo": {"intel_no_turbo": _read(f"{SYS}/cpu/intel_pstate/no_turbo"), "cpufreq_boost": _read(f"{SYS}/cpu/cpufreq/boost")},
        "smt": {"active": _read(f"{SYS}/cpu/smt/active"), "siblings": {str(c): factlib.smt_siblings(c) for c in cpus}},
        "cstates": None if first is None else _cstates(first),
        "thp": _read("/sys/kernel/mm/transparent_hugepage/enabled"),
        "aslr": _read("/proc/sys/kernel/randomize_va_space"),
        "numa": _numa(cpus + list(mock_cpus)),
        "irq": {"default_smp_affinity": _read("/proc/irq/default_smp_affinity"), "irqbalance": any(os.path.basename(_read(f"/proc/{p}/comm") or "").strip() == "irqbalance" for p in os.listdir("/proc") if p.isdigit()) if os.path.isdir("/proc") else None},
        "clocksource": _read(f"{SYS}/clocksource/clocksource0/current_clocksource"),
        "cgroup": {"chain": _cgroup_chain(), "mode": "v2" if os.path.exists("/sys/fs/cgroup/cgroup.controllers") else "v1-or-none"},
        "container_runtime": _runtime(),
        "boot_id": hashlib.sha256((_read("/proc/sys/kernel/random/boot_id") or "").strip().encode()).hexdigest()[:16] or None,   # a hash: two runs of one boot are one session
        "bench_cpus": cpus,
        "mock_cpus": list(mock_cpus),
        "memory_gib": factlib.mem_gib(),
    }
    why = {"microcode": "not exposed (virtual machine or non-x86)", "mitigations": "no /sys/devices/system/cpu/vulnerabilities", "cpu_mhz_max": "no cpufreq driver",
           "cstates": "no cpuidle driver", "thp": "no transparent hugepage support", "aslr": "no /proc/sys/kernel/randomize_va_space", "clocksource": "no clocksource0",
           "memory_gib": "no /proc/meminfo and no sysctl hw.memsize",
           "container_runtime": "no docker on PATH or the daemon did not answer; the local backend runs processes directly"}
    doc["unavailable"] = {k: v for k, v in why.items() if doc.get(k) is None}
    if all(v is None for v in doc["turbo"].values()):
        doc["unavailable"]["turbo"] = "no intel_pstate or cpufreq interface: the turbo state cannot be read"
    return doc
