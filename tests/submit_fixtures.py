# SPDX-License-Identifier: Apache-2.0
"""A throwaway buffon checkout (git repository with an arms.lock) and run directories that match it, for the submission tests."""
import json
import os
import subprocess
import tempfile

from buffon.submit import manifest
from tests.telemetry_fixtures import facts, run, write_dir

LOCK = {"arms": {"pi-node": {"manifest_sha256": "m1" * 32, "version": "1.1.0", "spec": {"artifact": {"linux-x64": {"sha256": "a1" * 32}}}},
                 "other": {"manifest_sha256": "m2" * 32, "version": "2.0.0", "spec": {"source": {"commit": "c" * 40, "tree": "d" * 40}}}}, "runtimes": {}}
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def sh(repo, *argv):
    out = subprocess.run(argv, cwd=repo, capture_output=True, text=True, env={**os.environ, **GIT_ENV})
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def make_repo(lock=None):
    repo = tempfile.mkdtemp()
    sh(repo, "git", "init", "-q")
    with open(os.path.join(repo, "arms.lock"), "w") as f:
        f.write(json.dumps(lock or LOCK, indent=2, sort_keys=True) + "\n")
    sh(repo, "git", "add", "arms.lock")
    sh(repo, "git", "commit", "-q", "-m", "lock")
    return repo


def submit_raw(repo, **kw):
    """A run that passes every check against `repo`."""
    raw = run(quiet=True, **kw)
    raw["run"].update({"aa": "all", "workloads": ["overhead/print"], "apis": ["openai-completions"], "reference": "pi-node", "finished_utc": "2026-10-11T13:00:00Z",
                       "command": ["buffon", "session", "overhead", "--rounds", "12"], "quiet_gate": {"enabled": True, "max_busy": 0.1, "timeout_s": 300, "max_runnable": 0, "waits": 0, "max_wait_ms": 0, "timeouts": 0},
                       "params": {}, "arms": ["pi-node", "other"], "host_class": "A", "preflight": {"ok": True}, "lock_file": "/run/lock/buffon.lock",
                       "isolation": {"isolation": "none", "comparable": False, "stamp": "uncontained, not comparable"}})
    for smp in raw["samples"]:   # the proof that each sample ran in a fresh home (buffon/verify.py check_home)
        smp["home"] = {"fresh": True, "pre_files": 3, "pre_sha256": "a0" * 32, "post_files": 4, "post_sha256": "b1" * 32, "written": 1, "removed": 0, "homes": 1}
    raw["lock_sha256"] = manifest.sha256_file(os.path.join(repo, "arms.lock"))
    raw["runner"] = {"commit": sh(repo, "git", "rev-parse", "HEAD"), "tree": sh(repo, "git", "rev-parse", "HEAD^{tree}"), "dirty": False, "diff_sha256": None}
    raw["arms"] = {"pi-node": {"version": "1.1.0", "manifest_sha256": "m1" * 32, "executable_sha256": "e1" * 32, "artifact_sha256": "a1" * 32, "twin_of": None},
                   "pi-node-b": {"version": "1.1.0", "manifest_sha256": "m1" * 32, "executable_sha256": "e1" * 32, "artifact_sha256": "a1" * 32, "twin_of": "pi-node"},
                   "other": {"version": "2.0.0", "manifest_sha256": "m2" * 32, "executable_sha256": "e2" * 32, "commit": "c" * 40, "tree": "d" * 40, "twin_of": None},
                   "other-b": {"version": "2.0.0", "manifest_sha256": "m2" * 32, "executable_sha256": "e2" * 32, "commit": "c" * 40, "tree": "d" * 40, "twin_of": "other"}}
    return raw


def sealed_dir(repo, raw=None, name="run", submission=True, base=None):
    """A sealed run directory (and submission.toml) under a fresh temp directory."""
    d = os.path.join(base or tempfile.mkdtemp(), name)
    write_dir(d, raw or submit_raw(repo), facts())
    from buffon.runner import sysinfo
    with open(os.path.join(d, "host.json"), "w") as f:
        json.dump({**{k: "x" for k in sysinfo.REQUIRED}, "host_class": "A"}, f)
    if submission:
        with open(os.path.join(d, "submission.toml"), "w") as f:
            f.write('operator = "A. Person"\nhardware = "bare-metal 16 cores, dedicated to benchmarks, nothing else runs"\nindependent = true\n')
    manifest.write(d)
    return d
