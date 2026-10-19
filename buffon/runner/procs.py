# SPDX-License-Identifier: MIT
"""What a harness's process tree is made of, from /proc (from `ps` where there is none, as on macOS): which process is the harness and which are its extension hosts, and the CPU each has used.

The extension-matrix arms differ in where the extensions run (one Node process, ten, one Go runner, none because they are fused). The sample records the census, and an arm's
`[extensions]` table states what it must be, so an arm that silently fell back to another realization cannot report a number.
"""
import os
import subprocess

TICK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
PAGE_KIB = (os.sysconf("SC_PAGE_SIZE") // 1024) if hasattr(os, "sysconf") else 4


def _ps(pid, fields):
    try:
        done = subprocess.run(["ps", "-o", fields, "-p", str(pid)], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def _stat(pid):
    """(ppid, cpu seconds, rss KiB) of a process, or None when it is gone."""
    if not os.path.isdir("/proc/self"):
        from . import cgroup
        row = cgroup.parse_ps(_ps(pid, "pid=,ppid=,rss=,time=") or "").get(int(pid))
        return None if row is None else (row[0], row[2] / 1000, row[1])
    try:
        with open(f"/proc/{pid}/stat") as f:
            text = f.read()
    except OSError:
        return None
    fields = text[text.rindex(")") + 2:].split()
    return int(fields[1]), (int(fields[11]) + int(fields[12])) / TICK, int(fields[21]) * PAGE_KIB


def _exe(pid):
    if not os.path.isdir("/proc/self"):
        return os.path.basename(_ps(pid, "comm=") or "")
    try:
        return os.path.basename(os.readlink(f"/proc/{pid}/exe"))
    except OSError:
        return ""


def _cmd(pid):
    if not os.path.isdir("/proc/self"):
        return _ps(pid, "command=") or ""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def census(host_pid, pids):
    """[{pid, role, exe, cmd, cpu_ms, rss_mib}] for the live processes of `pids` that are the harness (`host_pid`, role `host`) or descend from it (role `extension`). A meter's own
    holder process (a `sleep` that keeps a systemd scope alive) is in the same cgroup but is nobody's descendant, so it is not counted."""
    stats = {int(p): _stat(int(p)) for p in set(pids) | {host_pid}}
    rows = []
    for pid in sorted(p for p, st in stats.items() if st is not None):
        node, descends = pid, pid == host_pid
        for _ in range(64):
            if descends or stats.get(node) is None:
                break
            node = stats[node][0]
            descends = node == host_pid
            if node not in stats:
                st = _stat(node)
                stats[node] = st
        if not descends:
            continue
        st = stats[pid]
        rows.append({"pid": pid, "role": "host" if pid == host_pid else "extension", "exe": _exe(pid), "cmd": _cmd(pid)[:240], "cpu_ms": st[1] * 1000, "rss_mib": st[2] / 1024})
    return rows


def expected_processes(spec, count=None):
    """The extension processes the arm's `[extensions]` table calls for when it loads `count` extensions. `processes` is declared for the arm's full set (`count`, default 10): a
    realization with one process per extension (processes equal to the set's size, more than one) has `count` of them for a prefix, any other has the declared number."""
    want = spec.get("processes")
    if want is not None and count is not None and want > 1 and want == spec.get("count", 10):
        return count
    return want


def check(rows, spec, count=None):
    """The failure text when the census does not match the arm's `[extensions]` table (`processes`: the number of extension processes, see `expected_processes`; `host`: a substring
    every extension process's executable or command line must contain), else None."""
    ext = [r for r in rows if r["role"] == "extension"]
    want = expected_processes(spec, count)
    if want is not None and len(ext) != want:
        return f"{len(ext)} extension process(es) are running, the arm's realization has {want}: " + ", ".join(sorted({r['exe'] or r['cmd'][:40] for r in ext}))
    host = spec.get("host")
    if host and not all(host in (r["exe"] + " " + r["cmd"]) for r in ext):
        return f"an extension process does not run on {host}: " + ", ".join(sorted({r['exe'] for r in ext}))
    return None
