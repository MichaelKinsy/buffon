# SPDX-License-Identifier: MIT
"""Egress audit for no-spend benches: no request may leave the machine.

Only task-completion benches may use a live API key. Every other bench points each CLI at the local mock endpoint with
a dummy key value and an isolated HOME that holds no credentials. This module checks that nothing else leaves the
host in two ways:

  isolated network namespace   when the bench runs with no non-loopback interface or no default route (a container
                               with `--network none`, or `unshare --net`), egress is impossible by construction.
  socket audit (Linux)         while a harness runs, its process tree's sockets are read from /proc every 25 ms; any
                               connected socket whose remote address is not loopback is a violation. A connection
                               that opens and closes inside one sampling interval can be missed, which is why the
                               report states the interval, and why a strict run should use an isolated namespace.
  socket audit (lsof)          where there is no /proc (macOS), `lsof -nP -i` lists the tree's network sockets on each
                               sample; the rule and the gap are the same, and one lsof call costs tens of milliseconds,
                               so the sampling interval is longer. An lsof call that fails or times out records
                               `unaudited(lsof <error>)`, which fails the sample like a non-loopback remote. Without /proc
                               and without lsof there is no audit: the run is labelled PROVISIONAL and `buffon verify`
                               refuses it.

A violation fails the sample and the bench (non-zero exit).
"""
import ipaddress
import os
import shutil
import subprocess

NET_FILES = ("tcp", "tcp6", "udp", "udp6")
SAMPLE_INTERVAL_S = 0.025
LSOF_INTERVAL_S = 0.1
LSOF_TIMEOUT_S = 15     # -b and -w keep lsof from stat()ing every mount and warning about the ones it cannot; a starved host still needs seconds


def has_proc():
    return os.path.isdir("/proc/net")


def lsof_path():
    return shutil.which("lsof")


def sample_interval():
    """Seconds between samples of a tree: /proc reads are cheap, an lsof process is not."""
    return SAMPLE_INTERVAL_S if has_proc() or not lsof_path() else LSOF_INTERVAL_S


def _hex_ip(hexa):
    raw = bytes.fromhex(hexa)
    if len(raw) == 4:
        return str(ipaddress.IPv4Address(raw[::-1]))
    words = [raw[i:i + 4][::-1] for i in range(0, 16, 4)]
    return str(ipaddress.IPv6Address(b"".join(words)))


def parse_proc_net(text):
    """Return {inode: (remote_ip, remote_port)} for connected sockets in a /proc/net/{tcp,udp}[6] dump (remote 0 means not connected)."""
    out = {}
    for line in text.splitlines()[1:]:
        f = line.split()
        if len(f) < 10:
            continue
        try:
            ip, port = f[2].split(":")
            remote = _hex_ip(ip)
            out[int(f[9])] = (remote, int(port, 16))
        except (ValueError, IndexError):
            continue
    return out


def is_local(ip):
    addr = ipaddress.ip_address(ip)
    if addr.is_unspecified:
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_loopback


def socket_inodes(pid):
    inodes = set()
    try:
        for fd in os.listdir(f"/proc/{pid}/fd"):
            try:
                target = os.readlink(f"/proc/{pid}/fd/{fd}")
            except OSError:
                continue
            if target.startswith("socket:["):
                inodes.add(int(target[8:-1]))
    except OSError:
        pass
    return inodes


def _read_net(name):
    with open(f"/proc/net/{name}") as f:
        return f.read()


def parse_lsof(text):
    """The remotes ('ip', port) of the connected sockets in `lsof -F n` output: a name is `local->remote` for a connected socket (TCP or connected UDP) and `local` alone for a listener or an unconnected one."""
    out = []
    for line in text.splitlines():
        if not line.startswith("n") or "->" not in line:
            continue
        host, _, port = line.split("->", 1)[1].rpartition(":")
        host = host.strip("[]")
        if not host or host == "*" or not port.isdigit():
            continue
        out.append((host, int(port)))
    return out


def scan_lsof(pids):
    """The 'ip:port' strings that `pids` are connected to outside the loopback, from lsof (where /proc does not exist)."""
    ids = [str(p) for p in pids]
    exe = lsof_path()
    if not ids or not exe:
        return set()
    try:
        done = subprocess.run([exe, "-nP", "-b", "-w", "-a", "-p", ",".join(ids), "-i", "-F", "n"], capture_output=True, text=True, timeout=LSOF_TIMEOUT_S)   # exit 1 means no socket matched
    except (OSError, subprocess.SubprocessError) as error:   # review: an audit that did not run is not a clean audit; the marker fails the sample like a remote would
        return {f"unaudited(lsof {type(error).__name__})"}
    found = set()
    for host, port in parse_lsof(done.stdout):
        try:
            if not is_local(host):
                found.add(f"{host}:{port}")
        except ValueError:
            found.add(f"{host}:{port}")      # an address that does not parse is not known to be local
    return found


def scan(pids, read=None):
    """Return the set of 'ip:port' strings that member processes are connected to outside the loopback."""
    if read is None and not has_proc():
        return scan_lsof(pids)
    read = read or _read_net
    inodes = set()
    for pid in pids:
        inodes |= socket_inodes(pid)
    if not inodes:
        return set()
    found = set()
    for name in NET_FILES:
        try:
            table = parse_proc_net(read(name))
        except OSError:
            continue
        for inode in inodes:
            if inode in table and not is_local(table[inode][0]):
                found.add(f"{table[inode][0]}:{table[inode][1]}")
    return found


def netns_isolated():
    """True when this network namespace has no interface besides loopback and no route: nothing can leave."""
    try:
        with open("/proc/net/route") as f:
            routes = [ln for ln in f.read().splitlines()[1:] if ln.strip()]
        with open("/proc/net/dev") as f:
            ifaces = [ln.split(":")[0].strip() for ln in f.read().splitlines()[2:] if ":" in ln]
    except OSError:
        return False
    return not routes and all(i == "lo" for i in ifaces)


def describe():
    """How this run is protected, for the report."""
    if netns_isolated():
        return {"mode": "isolated-network-namespace", "note": "no non-loopback interface and no route: egress is impossible"}
    if has_proc():
        return {"mode": "socket-audit", "source": "proc", "interval_ms": int(SAMPLE_INTERVAL_S * 1000), "note": "connected non-loopback sockets of each harness tree are sampled; a connection shorter than the interval can be missed"}
    if lsof_path():
        return {"mode": "socket-audit", "source": "lsof", "interval_ms": int(LSOF_INTERVAL_S * 1000), "note": "connected non-loopback sockets of each harness tree are listed with lsof between samples (an lsof call takes tens of milliseconds); a connection shorter than the interval can be missed"}
    return {"mode": "none", "note": "egress audit unavailable on this OS (no /proc, no lsof): run refused for publication; dummy keys and an isolated HOME only"}


OBSERVED = set()  # remotes seen by meters that have been closed since the last take()


def take():
    """Return and clear the non-loopback remotes observed since the last call."""
    seen = set(OBSERVED)
    OBSERVED.clear()
    return seen
