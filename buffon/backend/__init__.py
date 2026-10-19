# SPDX-License-Identifier: Apache-2.0
"""Execution backends: where a session runs.

One session is one `python3 -m buffon session ...` invocation: a set of workloads, their arms, A/A copies and rounds, interleaved by the runner, in one fresh process on
pinned CPUs. A backend only decides where that process runs. The workload, runner and report code is the same on every backend; differences live in this package.

    LocalBackend       this machine: CPU pinning by sched_setaffinity, governor and idle detection, and a refusal or PROVISIONAL label when it cannot pin.
    K8sBackend         one Kubernetes pod per session (Guaranteed QoS, exclusive cores, digest-pinned image or bundle): buffon/backend/k8s.py.

The raw result of every session is the run directory it leaves: raw.json (docs/RAW-FORMAT.md) and facts.json.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Session:
    argv: list                                  # Buffon command the backend runs, e.g. ["python3", "-m", "buffon", "session", ...]
    run_dir: str = ""                           # where the session's raw.json and facts.json end up on the caller's machine
    cpus: int = 0                               # whole CPUs the session may use (the pod's request on Kubernetes; the pin list's size locally)
    memory_mib: int = 0
    deadline_s: int = 0
    env: dict = field(default_factory=dict)     # non-secret only: a secret reaches a pod through a Kubernetes secret reference named in the site profile
    bundle: str = None                          # directory holding buffon, the pinned arms' verified cache and runtimes, with a sha list (a pod gets it by kubectl cp)
    nodes: list = None                          # Kubernetes: run the session on each of these nodes (one pod each) instead of the site's node choice (a calibration's nodes)


@dataclass
class SessionResult:
    run_dir: str
    facts: dict
    pinned_cpus: list
    throttled_usec: int
    exit_code: int


class BackendError(RuntimeError):
    pass


class Backend(Protocol):
    name: str

    def check(self, isolation: str = "none") -> None:
        """Refuse early: a missing or invalid site profile, an unpinned image, a CPU that does not exist, no permission. `isolation` is the run's --isolation: a platform that cannot pin accepts `cpus` only for `container`, where they are the container VM's CPUs."""

    def run(self, session: Session) -> SessionResult:
        """Run the session and return where its results are."""


def load_result(run_dir, exit_code):
    """Read facts.json from a session's run directory into a SessionResult; a run that died before writing it gets empty facts."""
    facts = {}
    path = os.path.join(run_dir, "facts.json")
    if os.path.exists(path):
        with open(path) as f:
            facts = json.load(f)
    from ..site import parse_cpus
    pinned = parse_cpus(facts["pinned_cpus"]) if facts.get("pinned_cpus") else []
    return SessionResult(run_dir=run_dir, facts=facts, pinned_cpus=pinned, throttled_usec=int(facts.get("throttled_usec") or 0), exit_code=exit_code)


def get_backend(site):
    """The backend a site profile selects."""
    if site.backend == "local":
        from .local import LocalBackend
        return LocalBackend(site)
    try:
        from .k8s import K8sBackend
    except ImportError as error:
        raise BackendError("the Kubernetes backend (buffon/backend/k8s.py) is not installed in this checkout") from error
    return K8sBackend(site)
