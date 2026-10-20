# SPDX-License-Identifier: Apache-2.0
"""Kernel I/O counters of the measured process tree (docs/design/DURABLE.md 4.3 layer B): `rchar` and `wchar` of `/proc/<pid>/io`, summed over the tree's processes, and the block-layer
bytes of the cgroup's `io.stat` where the meter has a cgroup. They see every byte the library read or wrote to the database and the WAL, whatever the counting facade counted.
`rchar` counts reads the page cache served, so it is comparable to the facade's `bytes_returned`.

A host with no /proc (macOS) or a process tree the runner may not read gives no reading: the sample then has no such field. A reading is a dict; an unreadable one is `{}`, never zeros."""
import os

FIELDS = ("rchar", "wchar")
CGROUP_FIELDS = {"rbytes": "read_bytes", "wbytes": "write_bytes"}


def _proc_io(pid):
    out = {}
    with open(f"/proc/{pid}/io") as f:
        for line in f:
            key, _, value = line.partition(":")
            if key in FIELDS:
                out[key] = int(value)
    return out


def read(meter):
    """{"rchar", "wchar"} summed over the meter's processes now (plus "read_bytes" and "write_bytes" from the cgroup's io.stat when it has one); {} when nothing could be read."""
    total, seen = {k: 0 for k in FIELDS}, False
    for pid in meter.pids():
        try:
            for k, v in _proc_io(pid).items():
                total[k] += v
            seen = True
        except (OSError, ValueError):
            continue
    if not seen:
        return {}
    path = getattr(meter, "path", None)
    if path:
        try:
            with open(os.path.join(path, "io.stat")) as f:
                for line in f:
                    for item in line.split()[1:]:
                        key, _, value = item.partition("=")
                        if key in CGROUP_FIELDS:
                            total[CGROUP_FIELDS[key]] = total.get(CGROUP_FIELDS[key], 0) + int(value)
        except (OSError, ValueError):
            pass
    return total


def delta(after, before):
    """after - before for the keys both have; {} when either reading is empty."""
    if not after or not before:
        return {}
    return {k: max(0, after[k] - before[k]) for k in after if k in before}
