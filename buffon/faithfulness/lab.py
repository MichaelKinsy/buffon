# SPDX-License-Identifier: Apache-2.0
"""One arm in one probe: a prepared harness (own HOME, project directory and agent directory) against the shared mock, run to completion, and what it did.

The lab only observes. It runs the arm's own manifest modes (print, print_session, rpc) with extra arguments, so a probe needs no knowledge of how an arm is installed."""
import json
import os
import shutil
import subprocess
import threading
import time

from ..mock import Step, scripted_policy
from ..runner.harness import Harness
from ..runner import procio, cgroup, egress
from . import canon

TIMEOUT = 60


class EgressViolation(Exception):
    """A probe's process tree connected to a non-loopback address: the same rule as a benchmark sample, so the probe fails and the run exits non-zero."""

    def __init__(self, remotes):
        super().__init__("egress: the arm connected to " + ", ".join(sorted(remotes)))
        self.remotes = sorted(remotes)


class Skip(Exception):
    """The arm cannot take part in this probe at all (no such mode): the probe scores a mismatch unless the dimension is N/A for the arm."""


class Obs:
    """What one run did, raw (before normalisation)."""

    def __init__(self, arm, setup):
        self.arm, self.setup = arm, setup
        self.exit, self.stdout, self.stderr, self.timed_out = None, "", "", False
        self.requests, self.files, self.records = [], {}, []
        self.sessions = {}


class Setup:
    def __init__(self, harness):
        self.h = harness
        self.cwd, self.home, self.agent_dir, self.session_dir = harness.cwd, harness.home, harness.agent_dir, harness.sessions

    def write(self, rel, content, base="cwd"):
        root = {"cwd": self.cwd, "agent": self.agent_dir, "home": self.home}[base]
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path


class Lab:
    def __init__(self, ws, server, work):
        self.ws, self.server, self.work = ws, server, work
        self.violations = []   # [{arm, remotes}]: probes that connected outside loopback

    def prepare(self, arm, probe_id, api, **harness_kw):
        tag = probe_id.replace("/", "-").replace(":", "-")
        h = Harness(arm, self.work, self.server, api=api, tag=tag, **harness_kw)
        return Setup(h)

    def files_of(self, root, skip=()):
        out = {}
        for base, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in skip)
            for name in sorted(files):
                full = os.path.join(base, name)
                try:
                    with open(full, "rb") as f:
                        out[os.path.relpath(full, root)] = f.read().decode("utf-8", "replace")
                except OSError:
                    pass
        return out

    def check_egress(self, arm):
        """Fail the probe that connected anywhere but loopback; the violation stays on the lab for the run's record."""
        left = egress.take()
        if left:
            self.violations.append({"arm": arm.id, "remotes": sorted(left)})
            raise EgressViolation(left)

    def argv_for(self, arm, setup, mode, extra=(), prompt="", session=None):
        h = setup.h
        if not arm.supports_mode(mode):
            raise Skip(arm.cannot_run.get(mode) or f"it has no {mode} mode")
        base = h.argv(mode, prompt, session)
        return [base[0], *extra, *base[1:]]

    def run(self, arm, setup, argv, steps=None, policy=None, stdin=None, timeout=TIMEOUT, snapshot=True):
        """Run argv in the setup's project directory against the mock (reset with the scripted steps); return an Obs."""
        srv = self.server
        srv.reset(policy=policy or scripted_policy(steps or [Step(text="ok")]))
        before = self.files_of(setup.cwd) if snapshot else {}
        obs = Obs(arm, setup)
        t0 = time.monotonic()
        egress.take()
        meter = cgroup.new_meter()   # every probe is metered: the socket audit reads the process tree's connections while it runs
        try:
            proc = meter.popen(argv, env=setup.h.env, cwd=setup.cwd, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, errors="replace", start_new_session=True)
            try:
                obs.stdout, obs.stderr = proc.communicate(input=stdin, timeout=timeout)
                obs.exit = proc.returncode
            except subprocess.TimeoutExpired:
                obs.timed_out, obs.exit = True, None
                meter.kill()
                obs.stdout, obs.stderr = proc.communicate()
        except OSError as e:
            obs.exit, obs.stderr = 127, str(e)
        finally:
            meter.close()
        obs.wall_s = time.monotonic() - t0
        self.check_egress(arm)
        obs.requests = list(srv.requests)
        after = self.files_of(setup.cwd) if snapshot else {}
        obs.files = {k: v for k, v in after.items() if before.get(k) != v}
        obs.sessions = self.files_of(setup.session_dir)
        return obs

    def run_rpc(self, arm, setup, commands, steps=None, wait=lambda rpc: False, timeout=30, extra=()):
        """Run the arm in rpc mode, send the commands (dicts) one by one, wait for `wait(rpc)` or the timeout; return an Obs with the records."""
        srv = self.server
        srv.reset(policy=scripted_policy(steps or [Step(text="ok")]))
        argv = self.argv_for(arm, setup, "rpc", extra)
        egress.take()
        meter = cgroup.new_meter()
        obs = Obs(arm, setup)
        rpc = procio.Rpc(argv, setup.h.env, setup.cwd, meter)
        try:
            for cmd in commands:
                rpc.send(cmd)
                time.sleep(0.2)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and not wait(rpc):
                time.sleep(0.05)
            obs.timed_out = not wait(rpc)
        finally:
            rpc.close()
            meter.close()
        self.check_egress(arm)
        obs.records = [r for _, r in rpc.records]
        obs.requests = list(srv.requests)
        obs.exit = rpc.proc.poll()
        return obs
