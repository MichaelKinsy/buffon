# SPDX-License-Identifier: Apache-2.0
"""Readers for the files that describe how loaded a machine, a CPU set and a cgroup are (docs/TELEMETRY.md).

Every reader takes a `Sources` (the roots of /proc, /sys and the cgroup filesystem, so tests point them at a fake tree) and returns plain data or None when the file does
not exist on this machine, a container, a VM or a pod. Nothing here raises for a missing file: a result says which sources it could read (`snapshot()["sources"]`), so a
reader of a result can tell "zero" from "not measured". Counters are cumulative, gauges are instantaneous; `delta()` turns two snapshots into what happened between them.
"""
import os
import time

USER_HZ = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
CPU_FIELDS = ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal")


class Sources:
    """Where the kernel's files are. The defaults are the real ones."""

    def __init__(self, proc="/proc", sys="/sys", cgroup="/sys/fs/cgroup"):
        self.proc, self.sys, self.cgroup = proc, sys, cgroup

    def read(self, *parts):
        try:
            with open(os.path.join(*parts)) as f:
                return f.read()
        except (OSError, ValueError):
            return None

    def p(self, name):
        return self.read(self.proc, name)

    def s(self, name):
        return self.read(self.sys, name)


# -- parsers (pure) ---------------------------------------------------------------------------------------------------------------------------


def parse_proc_stat(text):
    """{cpu number: {field: ticks}} for each cpuN line of /proc/stat, and key None for the aggregate `cpu` line."""
    out = {}
    for line in (text or "").splitlines():
        if not line.startswith("cpu"):
            continue
        name, *vals = line.split()
        try:
            nums = [int(v) for v in vals]
        except ValueError:
            continue
        nums += [0] * (len(CPU_FIELDS) - len(nums))
        out[None if name == "cpu" else int(name[3:])] = dict(zip(CPU_FIELDS, nums[:len(CPU_FIELDS)]))
    return out


def parse_schedstat(text):
    """{cpu: run_delay_ns} from /proc/schedstat: the time tasks spent runnable but waiting for that CPU. None when the kernel does not account it (all zero)."""
    out = {}
    for line in (text or "").splitlines():
        if line.startswith("cpu"):
            f = line.split()
            try:
                out[int(f[0][3:])] = int(f[8])
            except (ValueError, IndexError):
                continue
    return out if any(out.values()) else None


def parse_kv(text):
    """{key: int} for `key value` lines (cpu.stat, memory.stat, memory.events, vmstat)."""
    out = {}
    for line in (text or "").splitlines():
        key, _, value = line.partition(" ")
        value = value.strip()
        if value.lstrip("-").isdigit():
            out[key] = int(value)
    return out


def parse_pressure(text):
    """{"some": {"avg10": f, "total_us": n}, "full": {...}} from a pressure file (PSI); None when absent."""
    if not text:
        return None
    out = {}
    for line in text.splitlines():
        kind, *fields = line.split()
        d = dict(f.split("=", 1) for f in fields if "=" in f)
        try:
            out[kind] = {"avg10": float(d.get("avg10", 0)), "total_us": int(d.get("total", 0))}
        except ValueError:
            continue
    return out or None


def parse_io_stat(text):
    """(read bytes, write bytes) summed over the devices of an io.stat file."""
    rb = wb = 0
    for line in (text or "").splitlines():
        for field in line.split()[1:]:
            k, _, v = field.partition("=")
            if k == "rbytes" and v.isdigit():
                rb += int(v)
            elif k == "wbytes" and v.isdigit():
                wb += int(v)
    return rb, wb


def parse_loadavg(text):
    """(1-minute load, currently runnable tasks including the reader)."""
    try:
        f = (text or "").split()
        return float(f[0]), int(f[3].split("/")[0])
    except (IndexError, ValueError):
        return None


def parse_meminfo(text):
    """{field: MiB} of the fields the telemetry uses."""
    out = {}
    for line in (text or "").splitlines():
        key, _, rest = line.partition(":")
        if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            try:
                out[key] = int(rest.split()[0]) / 1024
            except (ValueError, IndexError):
                pass
    return out


# -- single-file readers ----------------------------------------------------------------------------------------------------------------------


def cpu_mhz(src, cpu):
    """The current clock of a CPU in MHz from cpufreq (kHz), or None where the machine does not expose it."""
    for name in ("scaling_cur_freq", "cpuinfo_cur_freq"):
        v = src.s(f"devices/system/cpu/cpu{cpu}/cpufreq/{name}")
        if v and v.strip().isdigit():
            return int(v) / 1000
    return None


def cpuinfo_mhz(src):
    """{cpu: MHz} from /proc/cpuinfo (the fallback where cpufreq is not exposed, as in many VMs). Read rarely: the file is large on a big host."""
    out, cpu = {}, None
    for line in (src.p("cpuinfo") or "").splitlines():
        key, _, value = line.partition(":")
        key = key.strip()
        if key == "processor":
            cpu = int(value) if value.strip().isdigit() else None
        elif key == "cpu MHz" and cpu is not None:
            try:
                out[cpu] = float(value)
            except ValueError:
                pass
    return out


def thermal_events(src, cpu):
    v = src.s(f"devices/system/cpu/cpu{cpu}/thermal_throttle/core_throttle_count")
    return int(v) if v and v.strip().isdigit() else None


def own_cgroup(src):
    """The cgroup (v2) directory of this process, or None."""
    for line in (src.p("self/cgroup") or "").splitlines():
        if line.startswith("0::"):
            return os.path.normpath(src.cgroup + line[3:])
    return None


def chain(src, path):
    """`path` and its ancestors up to the cgroup filesystem root, nearest first."""
    root = os.path.normpath(src.cgroup)
    out, cur = [], os.path.normpath(path)
    while cur.startswith(root):
        out.append(cur)
        if cur == root:
            break
        cur = os.path.dirname(cur)
    return out


def throttle_of(src, path):
    """(nr_throttled, throttled_usec) summed over a cgroup and its ancestors: any of them limiting the CPU throttles what runs inside."""
    n = us = 0
    seen = False
    for d in chain(src, path):
        kv = parse_kv(src.read(d, "cpu.stat"))
        if "nr_throttled" in kv:
            seen = True
            n += kv["nr_throttled"]
            us += kv.get("throttled_usec", 0)
    return (n, us) if seen else None


def quota_limited(src, path):
    """The cgroups, `path` and its ancestors, that set a CPU quota (cpu.max other than `max`): a measured process under any of them can be throttled by the envelope. Names are
    relative to the cgroup root."""
    out = []
    for d in chain(src, path):
        v = (src.read(d, "cpu.max") or "").split()
        if v and v[0] != "max":
            out.append(os.path.relpath(d, src.cgroup))
    return out


# -- snapshots --------------------------------------------------------------------------------------------------------------------------------


def snapshot(src, cpus, fallback_mhz=False, light=False):
    """Everything that is read about the machine at one instant, for the CPUs a harness is pinned to (`cpus`). Counters are cumulative; `sources` lists what could be read. `light` reads only the gauges the in-sample readings keep: busy ticks, the clock and the load."""
    cpus = sorted(cpus)
    snap = {"t": time.monotonic(), "cpus": cpus, "sources": []}
    stat = parse_proc_stat(src.p("stat"))
    if stat:
        snap["cpu"] = {c: stat[c] for c in cpus if c in stat}
        snap["sources"].append("proc_stat")
    sched = None if light else parse_schedstat(src.p("schedstat"))
    if sched:
        snap["runq_ns"] = {c: sched[c] for c in cpus if c in sched}
        snap["sources"].append("schedstat")
    mhz = {c: v for c in cpus if (v := cpu_mhz(src, c)) is not None}
    if not mhz and fallback_mhz:
        info = cpuinfo_mhz(src)
        mhz = {c: info[c] for c in cpus if c in info}
        if mhz:
            snap["sources"].append("cpuinfo_mhz")
    elif mhz:
        snap["sources"].append("cpufreq")
    if mhz:
        snap["mhz"] = mhz
    thermal = {} if light else {c: v for c in cpus if (v := thermal_events(src, c)) is not None}
    if thermal:
        snap["thermal"] = thermal
        snap["sources"].append("thermal_throttle")
    load = parse_loadavg(src.p("loadavg"))
    if load:
        snap["load1"], snap["runnable"] = load
        snap["sources"].append("loadavg")
    if light:
        return snap
    mem = parse_meminfo(src.p("meminfo"))
    if "MemAvailable" in mem:
        snap["mem_available_mib"] = mem["MemAvailable"]
        snap["sources"].append("meminfo")
    vm = parse_kv(src.p("vmstat"))
    if "pswpin" in vm:
        snap["swap_pages"] = vm["pswpin"] + vm.get("pswpout", 0)
        snap["sources"].append("vmstat")
    psi = {k: parse_pressure(src.p(f"pressure/{k}")) for k in ("cpu", "memory", "io")}
    psi = {k: v["some"]["total_us"] for k, v in psi.items() if v and "some" in v}
    if psi:
        snap["psi_us"] = psi
        snap["sources"].append("pressure")
    own = own_cgroup(src)
    if own:
        th = throttle_of(src, own)
        if th:
            snap["session_throttle"] = th
            snap["sources"].append("cgroup_throttle")
    return snap


def ticks_ms(ticks):
    return ticks * 1000.0 / USER_HZ


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def delta(a, b):
    """What happened between two snapshots `a` (earlier) and `b`: CPU-set time by kind in ms, run-queue wait, throttling, pressure, swap and thermal events, as flat numbers.
    A key is absent when either snapshot lacked its source."""
    out = {"window_ms": round((b["t"] - a["t"]) * 1000, 2)}
    cpus = [c for c in a.get("cpu", {}) if c in b.get("cpu", {})]
    if cpus:
        sums = {f: sum(b["cpu"][c][f] - a["cpu"][c][f] for c in cpus) for f in CPU_FIELDS}
        ms = {f: round(ticks_ms(max(0, v)), 1) for f, v in sums.items()}
        out.update({"cpuset_cpus": len(cpus), "cpuset_busy_ms": round(sum(v for f, v in ms.items() if f != "idle" and f != "iowait"), 1),
                    "cpuset_user_ms": ms["user"] + ms["nice"], "cpuset_system_ms": ms["system"], "cpuset_iowait_ms": ms["iowait"], "cpuset_irq_ms": round(ms["irq"] + ms["softirq"], 1),
                    "cpuset_steal_ms": ms["steal"], "cpuset_idle_ms": ms["idle"]})
    if "runq_ns" in a and "runq_ns" in b:
        out["cpuset_runq_wait_ms"] = round(sum(max(0, b["runq_ns"][c] - a["runq_ns"][c]) for c in a["runq_ns"] if c in b["runq_ns"]) / 1e6, 3)
    if "session_throttle" in a and "session_throttle" in b:
        out["session_throttled_periods"] = max(0, b["session_throttle"][0] - a["session_throttle"][0])
        out["session_throttled_us"] = max(0, b["session_throttle"][1] - a["session_throttle"][1])
    for kind in ("cpu", "memory", "io"):
        if kind in a.get("psi_us", {}) and kind in b.get("psi_us", {}):
            out[f"psi_{kind}_some_us"] = max(0, b["psi_us"][kind] - a["psi_us"][kind])
    if "swap_pages" in a and "swap_pages" in b:
        out["swap_pages"] = max(0, b["swap_pages"] - a["swap_pages"])
    if a.get("thermal") and b.get("thermal"):
        out["thermal_throttle_events"] = sum(max(0, b["thermal"][c] - a["thermal"][c]) for c in a["thermal"] if c in b["thermal"])
    return out


def point(snap):
    """The gauges of one snapshot, flat: load, runnable tasks, clock of the CPU set, available memory."""
    out = {}
    for key in ("load1", "runnable", "mem_available_mib"):
        if key in snap:
            out[key] = round(snap[key], 3) if isinstance(snap[key], float) else snap[key]
    if snap.get("mhz"):
        v = list(snap["mhz"].values())
        out.update({"mhz_min": round(min(v), 1), "mhz_mean": round(sum(v) / len(v), 1), "mhz_max": round(max(v), 1)})
    return out


# -- a sample's cgroup, read just before the meter removes it ---------------------------------------------------------------------------------


def cgroup_final(src, path):
    """The totals of one meter's cgroup, read before it is removed: CPU time and throttling, peak memory, pids, IO bytes, page faults, pressure, memory events.
    The ancestors' cumulative throttling goes in `ancestors` (the report takes differences between samples)."""
    out = {"mode": "cgroup"}
    cpu = parse_kv(src.read(path, "cpu.stat"))
    if cpu:
        out.update({"cpu_usage_ms": round(cpu.get("usage_usec", 0) / 1000, 3), "cpu_user_ms": round(cpu.get("user_usec", 0) / 1000, 3), "cpu_system_ms": round(cpu.get("system_usec", 0) / 1000, 3)})
        if "nr_throttled" in cpu:
            out.update({"throttled_periods": cpu["nr_throttled"], "throttled_us": cpu.get("throttled_usec", 0), "periods": cpu.get("nr_periods", 0)})
    for key, name, scale in (("memory_peak_mib", "memory.peak", 1048576), ("memory_current_mib", "memory.current", 1048576)):
        v = (src.read(path, name) or "").strip()
        if v.isdigit():
            out[key] = round(int(v) / scale, 3)
    v = (src.read(path, "pids.peak") or "").strip()
    if v.isdigit():
        out["pids_peak"] = int(v)
    mem = parse_kv(src.read(path, "memory.stat"))
    if "pgfault" in mem:
        out["page_faults_minor"] = mem["pgfault"] - mem.get("pgmajfault", 0)
        out["page_faults_major"] = mem.get("pgmajfault", 0)
    ev = parse_kv(src.read(path, "memory.events"))
    if ev:
        out["memory_events"] = {k: ev[k] for k in ("low", "high", "max", "oom", "oom_kill") if k in ev}
    io = src.read(path, "io.stat")
    if io is not None:
        out["io_read_bytes"], out["io_write_bytes"] = parse_io_stat(io)
    for kind in ("cpu", "memory", "io"):
        p = parse_pressure(src.read(path, f"{kind}.pressure"))
        if p and "some" in p:
            out[f"psi_{kind}_some_us"] = p["some"]["total_us"]
    th = throttle_of(src, os.path.dirname(path)) if path else None
    if th:
        out["ancestors"] = {"chain": "/".join(os.path.relpath(d, src.cgroup) for d in chain(src, os.path.dirname(path))[:1]), "nr_throttled": th[0], "throttled_us": th[1]}
    limited = quota_limited(src, path)
    if limited:
        out.setdefault("ancestors", {})["limited"] = limited
    return out


def container_final(final, start_usage_usec=0, relay_cpu_ms=0.0):
    """The totals of a container sample, from the relay's reading of the container's own cgroup taken the instant the arm exited (the cgroup is gone once the container stops).
    CPU is the container's usage after the relay started the arm, less the relay's own CPU (as ContainerMeter.cpu_ms); throttling, the memory and pid peaks are the container's own. Pressure, IO and memory events are not read by the relay."""
    out = {"mode": "container"}
    stat = (final or {}).get("cpu.stat") or {}
    if "usage_usec" in stat:
        out["cpu_usage_ms"] = round(max(0.0, (stat["usage_usec"] - (start_usage_usec or 0)) / 1000 - relay_cpu_ms), 3)
    if "nr_throttled" in stat:
        out.update({"throttled_periods": stat["nr_throttled"], "throttled_us": stat.get("throttled_usec", 0), "periods": stat.get("nr_periods", 0)})
    for key, name in (("memory_peak_mib", "memory.peak"), ("memory_current_mib", "memory.current")):
        if isinstance((final or {}).get(name), int):
            out[key] = round(final[name] / 1048576, 3)
    if isinstance((final or {}).get("pids.peak"), int):
        out["pids_peak"] = final["pids.peak"]
    return out


def rusage_final(usage):
    """The totals of a rusage meter's process tree (`os.wait4` resource usage), when the cgroup is not available."""
    return {"mode": "rusage", "cpu_usage_ms": round((usage.ru_utime + usage.ru_stime) * 1000, 3), "cpu_user_ms": round(usage.ru_utime * 1000, 3),
            "cpu_system_ms": round(usage.ru_stime * 1000, 3), "page_faults_minor": usage.ru_minflt, "page_faults_major": usage.ru_majflt,
            "io_read_blocks": usage.ru_inblock, "io_write_blocks": usage.ru_oublock, "ctx_switches_voluntary": usage.ru_nvcsw, "ctx_switches_involuntary": usage.ru_nivcsw}


def merge_finals(finals):
    """One record for a sample that used several meters (an RPC session and a resume): counters add, peaks take the maximum."""
    if not finals:
        return None
    if len(finals) == 1:
        return dict(finals[0], meters=1)
    out = {"meters": len(finals), "mode": finals[0].get("mode")}
    adds = ("cpu_usage_ms", "cpu_user_ms", "cpu_system_ms", "throttled_periods", "throttled_us", "periods", "page_faults_minor", "page_faults_major", "io_read_bytes", "io_write_bytes",
            "io_read_blocks", "io_write_blocks", "ctx_switches_voluntary", "ctx_switches_involuntary", "psi_cpu_some_us", "psi_memory_some_us", "psi_io_some_us")
    peaks = ("memory_peak_mib", "memory_current_mib", "pids_peak")
    for key in adds:
        vals = [f[key] for f in finals if key in f]
        if vals:
            out[key] = round(sum(vals), 3) if isinstance(vals[0], float) else sum(vals)
    for key in peaks:
        vals = [f[key] for f in finals if key in f]
        if vals:
            out[key] = max(vals)
    events = [f["memory_events"] for f in finals if "memory_events" in f]
    if events:
        out["memory_events"] = {k: sum(e.get(k, 0) for e in events) for k in {k for e in events for k in e}}
    anc = [f["ancestors"] for f in finals if "ancestors" in f]
    if anc:
        out["ancestors"] = dict(anc[-1], **({"limited": sorted({n for a in anc for n in a.get("limited", [])})} if any("limited" in a for a in anc) else {}))
    return out
