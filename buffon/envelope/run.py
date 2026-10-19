# SPDX-License-Identifier: Apache-2.0
"""Executing the envelope: docker (then podman), one detached container per run, cgroup counters read while it lives, container start measured separately by a null run."""
import json
import os
import shutil
import subprocess
import tempfile
import time

from .spec import EnvelopeError, build_argv, lint


def find_runtime(prefer=("docker", "podman")):
    for name in prefer:
        path = shutil.which(name)
        if path:
            return name
    raise EnvelopeError("neither docker nor podman is on PATH: the container envelope cannot run (pass --isolation none for an uncontained run, which is stamped not comparable)")


def _cgroup_dir(runtime, cid):
    for path in (f"/sys/fs/cgroup/system.slice/{runtime}-{cid}.scope", f"/sys/fs/cgroup/machine.slice/libpod-{cid}.scope", f"/sys/fs/cgroup/docker/{cid}"):
        if os.path.isdir(path):
            return path
    return None


def _read_stat(path):
    try:
        with open(path) as f:
            return {k: int(v) for k, _, v in (ln.partition(" ") for ln in f.read().splitlines()) if v.strip().isdigit()}
    except OSError:
        return None


def _read_int(path):
    try:
        with open(path) as f:
            text = f.read().strip()
        return int(text) if text.isdigit() else None
    except OSError:
        return None


class Result:
    def __init__(self):
        self.exit = None
        self.stdout = self.stderr = ""
        self.wall_ms = None          # `docker run` to exit: includes the container start
        self.oom_killed = False
        self.cgroup = {}             # last readings while the container lived: cpu.stat (usec, nr_throttled), memory.peak, memory.current, pids.peak
        self.image = None
        self.runtime = None

    def throttled(self):
        """True when the container's CPU limit throttled it: the sample is invalid (nr_throttled > 0)."""
        return bool((self.cgroup.get("cpu.stat") or {}).get("nr_throttled"))


class Envelope:
    def __init__(self, runtime=None, poll_s=0.02, run=subprocess.run):
        self.runtime = runtime or find_runtime()
        self.poll_s = poll_s
        self._run = run

    def _docker(self, *args, timeout=120, check=True):
        done = self._run([self.runtime, *args], capture_output=True, text=True, timeout=timeout)
        if check and done.returncode != 0:
            raise EnvelopeError(f"{self.runtime} {' '.join(args[:2])} failed: {done.stderr.strip()[:300]}")
        return done

    def ensure_image(self, image):
        """Pull the digest-pinned image when it is not present (the only network use of the envelope, outside any measurement)."""
        have = self._docker("image", "inspect", image, check=False)
        if have.returncode != 0:
            self._docker("pull", "--quiet", image, timeout=900)

    def run(self, spec, command, timeout=300):
        """Run `command` in the envelope; returns a Result. The argv is linted again here: a Spec subclass or a patched builder cannot weaken the guarantees."""
        argv = build_argv(spec, command, runtime=self.runtime, detach=True)
        problems = lint(argv)
        if problems:
            raise EnvelopeError("; ".join(problems))
        self.ensure_image(spec.image)
        res = Result()
        res.runtime, res.image = self.runtime, spec.image
        t0 = time.monotonic()
        started = self._run(argv, capture_output=True, text=True, timeout=60)
        if started.returncode != 0:
            raise EnvelopeError(f"{self.runtime} run failed: {started.stderr.strip()[:300]}")
        cid = started.stdout.strip()
        try:
            cgroup = _cgroup_dir(self.runtime, cid)
            deadline = t0 + timeout
            while True:
                if cgroup and os.path.isdir(cgroup):
                    stat = _read_stat(os.path.join(cgroup, "cpu.stat"))
                    if stat is not None:
                        res.cgroup["cpu.stat"] = stat
                        res.cgroup["memory.peak"] = _read_int(os.path.join(cgroup, "memory.peak"))
                        res.cgroup["memory.current"] = _read_int(os.path.join(cgroup, "memory.current"))
                        res.cgroup["pids.peak"] = _read_int(os.path.join(cgroup, "pids.peak"))
                else:
                    cgroup = _cgroup_dir(self.runtime, cid) if not cgroup else None
                state = self._docker("inspect", "-f", "{{.State.Running}}", cid, check=False).stdout.strip()
                if state != "true":
                    break
                if time.monotonic() > deadline:
                    self._docker("kill", cid, check=False)
                    raise EnvelopeError(f"the container did not finish within {timeout} s and was killed")
                time.sleep(self.poll_s)
            res.wall_ms = round((time.monotonic() - t0) * 1000, 1)
            info = json.loads(self._docker("inspect", "-f", "{{json .State}}", cid).stdout)
            res.exit, res.oom_killed = info.get("ExitCode"), bool(info.get("OOMKilled"))
            logs = self._docker("logs", cid, check=False)
            res.stdout, res.stderr = logs.stdout, logs.stderr
        finally:
            self._docker("rm", "-f", cid, check=False)
        return res

    def null_run(self, spec, runs=5):
        """The envelope's own cost: the same envelope running /bin/true. Median wall ms over `runs`; a run's `wall_ms` minus this is the command's own wall time."""
        walls = sorted(self.run(spec, ["/bin/true"]).wall_ms for _ in range(runs))
        return walls[len(walls) // 2]
