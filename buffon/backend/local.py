# SPDX-License-Identifier: Apache-2.0
"""The local backend: run the session as a child process on this machine.

Pinning is by sched_setaffinity inside the session (harness CPUs from the site profile, the runner and mock on `mock_cpus`). The session detects the clock
governor and measures idle on the pinned CPUs before and after; this backend refuses early what it can know before starting.
"""
import os
import subprocess

from . import BackendError, Session, SessionResult, load_result
from .. import site as sitelib
from ..runner import facts as factlib


class LocalBackend:
    name = "local"

    def __init__(self, site, popen=subprocess.run):
        self.site, self.popen = site, popen

    def check(self, isolation="none"):
        l = self.site.local
        vm = isolation == "container" and bool(l.cpus) and l.pinning != "none" and not hasattr(os, "sched_setaffinity")   # macOS: `cpus` are the container VM's
        allowed = set(factlib.allowed_cpus())
        missing = sorted((set(l.mock_cpus) if vm else set(l.cpus) | set(l.mock_cpus)) - allowed)
        if missing:
            raise BackendError(f"site {self.site.name!r} names CPUs {missing} that this machine does not give the runner (allowed: {sitelib.format_cpus(allowed)})")
        if l.pinning == "required" and not hasattr(os, "sched_setaffinity") and not vm:
            raise BackendError("this platform cannot pin processes (no sched_setaffinity) and the site requires pinning; use a Linux host or set pinning = \"preferred\"")
        if not hasattr(os, "sched_setaffinity") and l.cpus and not vm:
            raise BackendError("this platform cannot pin processes: remove `cpus` from the site profile (the run is labelled PROVISIONAL), or run with --isolation container, where `cpus` are the container VM's CPUs")

    def run(self, session: Session) -> SessionResult:
        env = dict(os.environ)
        env.update(session.env)
        os.makedirs(session.run_dir, exist_ok=True)
        done = self.popen(session.argv, env=env, timeout=session.deadline_s or None)
        return load_result(session.run_dir, done.returncode)
