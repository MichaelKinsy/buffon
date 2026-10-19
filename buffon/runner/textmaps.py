# SPDX-License-Identifier: Apache-2.0
"""Where a measured process's executable code lives (docs/METHODOLOGY.md section 4, memory).

A file on tmpfs, ramfs or in shared memory that a process maps as code is memory the footprint metric (private-dirty) counts as the process's own, so a harness whose executable, runtime image or
unpacked native library sits on tmpfs would look 40 MB bigger than the same harness run from disk. Buffon runs every arm's binaries and runtime caches from disk and checks it: while a sample runs, the
executable mappings (`/proc/<pid>/maps`, permission `x`, a file behind them) of every process of the tree are looked up in that process's own mount table (`/proc/<pid>/mountinfo`), and the file system of each is
recorded in the sample (`text_fs`). A mapping on tmpfs, ramfs or in shared memory (`/dev/shm`, `memfd:`, SysV shm) fails the sample.

Anonymous executable memory (a JIT's code) has no file and is not text in this sense; it is never flagged."""
import os
import re

BAD_FS = {"tmpfs", "ramfs", "devtmpfs", "shmem"}
BAD_PATH = re.compile(r"^(/dev/shm/|/memfd:|/SYSV)")
MAPS_LINE = re.compile(r"^[0-9a-f]+-[0-9a-f]+ (\S{4}) [0-9a-f]+ ([0-9a-f]+):([0-9a-f]+) (\d+)\s*(.*)$")


def parse_mountinfo(text):
    """{(major, minor): (fstype, mount point)} from a mountinfo table."""
    out = {}
    for line in text.splitlines():
        head, sep, tail = line.partition(" - ")
        fields, rest = head.split(), tail.split()
        if not sep or len(fields) < 5 or not rest:
            continue
        try:
            major, minor = (int(x) for x in fields[2].split(":"))
        except ValueError:
            continue
        out[(major, minor)] = (rest[0], fields[4])
    return out


def mount_points(text):
    """[(mount point, fstype)] of every mount in a mountinfo table (several mounts can share one device)."""
    out = []
    for line in text.splitlines():
        head, sep, tail = line.partition(" - ")
        fields, rest = head.split(), tail.split()
        if sep and len(fields) >= 5 and rest:
            out.append((fields[4].replace("\\040", " "), rest[0]))
    return out


def parse_maps(text):
    """[(path, (major, minor), inode)] of the file-backed executable mappings in a maps table, one per file."""
    seen, out = set(), []
    for line in text.splitlines():
        m = MAPS_LINE.match(line)
        if not m or "x" not in m.group(1):
            continue
        perms, major, minor, inode, path = m.groups()[0], int(m.group(2), 16), int(m.group(3), 16), int(m.group(4)), m.group(5).strip()
        if not path or path.startswith("[") or (inode == 0 and not path.startswith("/memfd:")):
            continue   # [vdso], [stack], anonymous code
        key = (path, major, minor, inode)
        if key not in seen:
            seen.add(key)
            out.append((path, (major, minor), inode))
    return out


def classify(path, dev, mounts):
    """(fstype, bad): the file system a mapped file is on (from the process's own mount table) and whether code there counts as shared memory."""
    fstype = (mounts.get(dev) or ("unknown", None))[0]
    return fstype, fstype in BAD_FS or bool(BAD_PATH.match(path))


def read(path):
    with open(path) as f:
        return f.read()


class TextMappings:
    """Collects the file systems of the executable mappings of a process tree over a sample."""

    def __init__(self, proc="/proc"):
        self.proc = proc
        self.files = {}      # (path, dev) -> (fstype, bad)
        self.mounts = {}     # pid -> mount table, read once per process

    def observe(self, pids):
        for pid in pids:
            try:
                if pid not in self.mounts:
                    self.mounts[pid] = parse_mountinfo(read(f"{self.proc}/{pid}/mountinfo"))
                entries = parse_maps(read(f"{self.proc}/{pid}/maps"))
            except (OSError, ValueError):
                continue
            for path, dev, _inode in entries:
                if (path, dev) not in self.files:
                    self.files[(path, dev)] = classify(path, dev, self.mounts[pid])

    def totals(self, mask=None):
        """{"fs": {fstype: files}, "bad": [paths]}; `mask` (a directory) is replaced by `<work>` in the paths, so a record never names the host's directories."""
        fs, bad = {}, []
        for (path, _dev), (fstype, is_bad) in sorted(self.files.items()):
            fs[fstype] = fs.get(fstype, 0) + 1
            if is_bad:
                bad.append(path.replace(mask, "<work>") if mask and path.startswith(mask) else path)
        return {"fs": dict(sorted(fs.items())), "bad": bad}


def mount_type(path, table=None):
    """The file system type `path` is on (this process's mount table, the longest mount point that contains it), or None where there is no /proc/self/mountinfo (macOS)."""
    try:
        text = table if table is not None else read("/proc/self/mountinfo")
    except OSError:
        return None
    real = os.path.realpath(path)
    best, kind = "", None
    for point, fstype in mount_points(text):
        if (real == point or real.startswith(point.rstrip("/") + "/")) and len(point) >= len(best):
            best, kind = point, fstype
    return kind
