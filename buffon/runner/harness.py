# SPDX-License-Identifier: MIT
# Adapted from pigbench's harness.py (bench/evals of the PiG repository): the per-family branches became arm manifests and writers.
"""Isolated runtime for one arm in one sample: a fresh HOME, the arm's config written by its writer, a dummy key, the mock endpoint, and argv builders.

No buffon run gives a harness a live key or a vendor login. Every arm gets a dummy key value and a HOME that holds no credentials. The manifest names
the environment that turns off telemetry and updates, its state directories and its modes; nothing about an arm is decided here.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil

from ..arms.manifest import slot_name
from ..arms.writers import DUMMY_KEY, MODEL, WriteSpec
from .tuning import is_tuning
from ..mock import MODEL as MOCK_MODEL  # noqa: F401  (the writers and the mock must agree on the model id)

# The PATH every arm runs with, after its own runtime directories. Never the operator's PATH: a harness looks for helper programs on it (Pi probes
# `fd` and `rg`), so whatever the host has installed would change the arm's code path from host to host, and a version-manager shim (mise, asdf) on
# it downloads the tool on first use, which the egress audit then fails.
SYSTEM_PATH = ("/usr/bin", "/bin")


KEEP_VARS = ("LANG", "TZ")
KEEP_PREFIXES = ("LC_",)


def scrubbed_environ(environ=None):
    """The environment a harness inherits from the operator: locale and time zone only. Everything else (credentials, proxies, runtime tuning such as GOMAXPROCS, GOMEMLIMIT,
    NODE_OPTIONS, LD_PRELOAD, PYTHONPATH, a version manager's variables) is dropped, so an arm runs the same on every host and every operator shell. The harness sets no runtime tuning of its own
    (runner/tuning.py): a Go arm sizes itself by its own default. What an arm needs, the
    harness sets (HOME, XDG_*, TMPDIR, PATH, TERM) or the arm's manifest names in `[env]`, and the run records it (`isolation`)."""
    environ = os.environ if environ is None else environ
    return {k: v for k, v in environ.items() if k in KEEP_VARS or k.startswith(KEEP_PREFIXES)}


STATE_VAR = re.compile(r"(^|_)(HOME|AGENT_DIR|SESSION_DIR|SESSIONS_DIR|DATA_DIR|CONFIG_DIR|CACHE_DIR|STATE_DIR|TMPDIR|TEMP|TMP)$")


class Unconfined(RuntimeError):
    """A harness's HOME, agent directory or other state directory is outside the run's throwaway tree: the run refuses to start, because the harness (or an arm's first-start work, a pre-run cleanup) would read and write somebody else's state."""


def confine(env, roots, extra_paths=()):
    """Raise Unconfined unless every state directory the harness will see lies inside one of `roots` (real paths, so a symlink out is caught). State directories are the variables HOME, XDG_*_HOME, TMPDIR and anything named like *_HOME, *_AGENT_DIR, *_SESSION_DIR, *_DATA_DIR, *_CONFIG_DIR, *_CACHE_DIR, *_STATE_DIR, plus `extra_paths` (name, path)."""
    real = [os.path.realpath(r) for r in roots if r]
    bad = []
    items = [(k, v) for k, v in env.items() if STATE_VAR.search(k) and isinstance(v, str) and v] + list(extra_paths)
    for name, path in items:
        if not os.path.isabs(path):   # a relative or ~ path resolves against whatever cwd or HOME the arm has: it cannot be shown to be inside
            bad.append(f"{name}={path} (not an absolute path)")
            continue
        where = os.path.realpath(path)
        if not any(where == r or where.startswith(r + os.sep) for r in real):
            bad.append(f"{name}={path}")
    if "HOME" not in env:
        bad.append("HOME is not set")
    if bad:
        raise Unconfined("not starting: " + ", ".join(bad) + f" is outside the run's throwaway tree ({', '.join(real)})")


def load_writer(arm):
    path = arm.writer_path()
    spec = importlib.util.spec_from_file_location(f"buffon_writer_{arm.id.replace('-', '_').replace('.', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.write


def _rmtree(path):
    def writable(function, target, _):  # a Go module cache is read-only, and `rmtree` cannot delete what it cannot write
        os.chmod(os.path.dirname(target), 0o700)
        os.chmod(target, 0o700)
        function(target)
    shutil.rmtree(path, onerror=writable) if os.path.isdir(path) else None


CONTENT_LIMIT = 256 * 1024   # files up to this size are hashed by content in a home fingerprint; larger ones by size alone


def fingerprint(root):
    """{relative path: (kind, size, sha256 of the content)} of everything under `root`: a listing a later fingerprint can be compared with. A symlink is recorded by its target and never followed; a file over
    CONTENT_LIMIT by its size only (sha256 None)."""
    out = {}
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files) + [d for d in dirs if os.path.islink(os.path.join(base, d))]:
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root)
            try:
                if os.path.islink(path):
                    out[rel] = ("link", 0, hashlib.sha256(os.readlink(path).encode()).hexdigest())
                    continue
                size = os.path.getsize(path)
                if size > CONTENT_LIMIT:
                    out[rel] = ("file", size, None)
                    continue
                with open(path, "rb") as f:
                    out[rel] = ("file", size, hashlib.sha256(f.read()).hexdigest())
            except OSError:
                out[rel] = ("unreadable", 0, None)
    for base, dirs, _ in os.walk(root):
        for d in dirs:
            rel = os.path.relpath(os.path.join(base, d), root)
            if not os.path.islink(os.path.join(base, d)) and not os.listdir(os.path.join(base, d)):
                out[rel + "/"] = ("emptydir", 0, None)
    return out


def digest(listing):
    """One sha256 of a fingerprint, in path order."""
    h = hashlib.sha256()
    for rel in sorted(listing):
        h.update(json.dumps([rel, *listing[rel]]).encode() + b"\n")
    return h.hexdigest()


def home_record(pre, post, replaced_stale):
    """What raw.json keeps of one sample's home: it was created fresh, what it held before the process (count and digest), and what it held after (count, digest, files the process wrote or changed)."""
    changed = sorted(p for p in post if pre.get(p) != post[p])
    return {"fresh": not replaced_stale, "pre_files": len(pre), "pre_sha256": digest(pre), "post_files": len(post), "post_sha256": digest(post), "written": len(changed),
            "removed": len([p for p in pre if p not in post])}


class Harness:
    """One arm prepared against one mock endpoint, with its own HOME and project directory."""

    def __init__(self, arm, work, server, api="openai-completions", context_window=128000, compaction=None, retry_base_ms=50, extensions=(), tag="",
                 settings_extra=None, home_root=None):
        self.arm, self.server, self.base_url, self.api = arm, server, server.base_url, api
        name = slot_name(arm.id) + (f"-{tag}" if tag else "") + f"-{api.split('-')[0]}"
        self.home = os.path.join(home_root or work, name, "home")   # `home_root`: the swarm keeps every agent's HOME under one directory, which its container makes a tmpfs
        self.disk = os.path.join(work, name, "disk")   # runtime code and caches (PIG_HOME, TMPDIR, XDG_CACHE_HOME, unpacked natives): on a disk path of the run, never in HOME, which a container keeps on tmpfs
        self.stale = os.path.exists(os.path.dirname(self.home)) or os.path.exists(os.path.dirname(self.disk))   # a leftover from an earlier sample (a failed cleanup): it is removed, and the sample says so
        if self.stale:
            for leftover in {os.path.dirname(self.home), os.path.dirname(self.disk)}:
                _rmtree(leftover)
        self.cwd = os.path.join(work, name, "project")
        self.sessions = os.path.join(work, name, "sessions")
        self.work = work
        if getattr(arm, "seed_dir", None):
            shutil.copytree(arm.seed_dir, self.home, symlinks=True, dirs_exist_ok=True)  # the arm's first-start state (see Workspace._seed)
        for d in (self.home, self.cwd, self.sessions, os.path.join(self.disk, "tmp"), os.path.join(self.disk, "cache")):
            os.makedirs(d, exist_ok=True)
        seeded_cache = os.path.join(self.home, ".cache")
        if getattr(arm, "seed_dir", None) and os.path.isdir(seeded_cache):   # a seed's cache (unpacked natives, a model catalog) is runtime code: it moves to the disk cache directory
            shutil.copytree(seeded_cache, os.path.join(self.disk, "cache"), symlinks=True, dirs_exist_ok=True)
            _rmtree(seeded_cache)
        self.agent_dir = os.path.join(self.home, ".agent")
        self.extensions = list(extensions)
        env = scrubbed_environ()
        env["PATH"] = os.pathsep.join(list(arm.path_dirs) + list(SYSTEM_PATH))
        env.update({"HOME": self.home, "XDG_CONFIG_HOME": os.path.join(self.home, ".config"), "XDG_DATA_HOME": os.path.join(self.home, ".local", "share"),
                    "XDG_CACHE_HOME": os.path.join(self.disk, "cache"), "XDG_STATE_HOME": os.path.join(self.home, ".local", "state"), "TMPDIR": os.path.join(self.disk, "tmp"),
                    "NO_COLOR": "1", "TERM": "xterm-256color", "NO_PROXY": "127.0.0.1,localhost,::1", "no_proxy": "127.0.0.1,localhost,::1"})
        subs = {"home": self.home, "disk": self.disk, "agent_dir": self.agent_dir, "dummy_key": DUMMY_KEY, "install_dir": getattr(arm, "install_dir", None), **getattr(arm, "vars", {})}
        for k, v in arm.env.items():
            env[k] = re.sub(r"\{(\w+)\}", lambda m: subs.get(m.group(1), m.group(0)), v)
        roots = [work, home_root, getattr(arm, "vars", {}).get("shared_dir")]
        confine(env, roots, [("sessions", self.sessions), ("project", self.cwd), ("agent_dir", self.agent_dir)])   # before anything is created or emptied outside the tree
        for d in arm.spec.get("state", {}).get("dirs", []):
            os.makedirs(re.sub(r"\$(\w+)", lambda m: env.get(m.group(1), m.group(0)), d), exist_ok=True)
        # A prepared extension cache (compiled Go cells, a materialized Node cell) is laid into the fresh PIG_HOME so the sample measures a warm start. PIG_HOME is outside HOME
        # for such an arm (`[env] PIG_HOME = "{shared_dir}/pig-home"`), at one path for every sample, because a cell's cache key includes the cache root's path; samples run one
        # at a time, and the directory is emptied before each.
        install_dir = getattr(arm, "install_dir", None)
        warm = os.path.join(install_dir or "", "warm")
        self.pig_home = env.get("PIG_HOME")
        if self.pig_home and not self.pig_home.startswith(self.home + os.sep):
            _rmtree(self.pig_home)
            os.makedirs(self.pig_home)
        if install_dir and os.path.isdir(warm) and self.pig_home:
            shutil.copytree(warm, self.pig_home, symlinks=True, dirs_exist_ok=True)
        spec = WriteSpec(arm=arm, home=self.home, agent_dir=self.agent_dir, cwd=self.cwd, base_url=self.base_url, origin=server.origin, api=api, model=MODEL,
                         context_window=context_window, compaction=compaction, retry_base_ms=retry_base_ms, settings_extra=dict(settings_extra or {}))
        written = load_writer(arm)(spec) or {}
        hidden = sorted(k for k in written if is_tuning(k) and k not in arm.env)
        if hidden:   # the run records an arm's tuning from its manifest (tuning.settings): one a writer sets would go unrecorded
            raise RuntimeError(f"{arm.id}: the writer sets runtime-tuning variable(s) {', '.join(hidden)}; name them in the manifest's [env]")
        env.update(written)
        confine(env, roots, [("sessions", self.sessions), ("project", self.cwd), ("agent_dir", self.agent_dir)])
        self.env = env
        self.home_pre = self.fingerprint()   # what the process starts with: the arm's seeded first-start state and the config the writer laid down, nothing a previous sample left

    def home_proof(self):
        """The isolation record of this sample's home, taken after the process ran (docs/METHODOLOGY.md, per-run isolation)."""
        return home_record(self.home_pre, self.fingerprint(), self.stale)

    def fingerprint(self):
        """The home and the disk directory of this sample, one listing (paths prefixed home/ and disk/)."""
        out = {"home/" + k: v for k, v in fingerprint(self.home).items()}
        out.update({"disk/" + k: v for k, v in fingerprint(self.disk).items()})
        return out

    def isolation_env(self):
        """The variables this harness sets beyond the inherited environment, with the throwaway root masked: part of the configuration under comparison."""
        out = {}
        for k, v in sorted(self.env.items()):
            if os.environ.get(k) != v:
                out[k] = "<dummy key>" if v == DUMMY_KEY else re.sub(r"(127\.0\.0\.1):\d+", r"\1:<port>", v.replace(self.work, "<work>"))
        return {"set": out, "scrubbed": sorted(k for k in os.environ if k not in self.env), "inherited": sorted(k for k in KEEP_VARS if k in os.environ)}

    # -- argv ---------------------------------------------------------------------------------------------------------------------------------

    def argv(self, mode, prompt="", session=None):
        """The command for a mode: the manifest's template with {model}, {prompt}, {session}, {session_dir} and {extensions} filled."""
        out = [self.arm.binary]
        for part in self.arm.modes[mode]:
            if part == "{extensions}":
                for path in self.extensions:
                    out += ["-e", path]
                continue
            out.append(part.replace("{model}", MODEL).replace("{prompt}", prompt).replace("{session_dir}", self.sessions).replace("{session}", session or os.path.join(self.sessions, "s.jsonl")))
        return out

    def print_argv(self, prompt, session=False):
        return self.argv("print_session" if session and self.arm.supports_mode("print_session") else "print", prompt)

    def rpc_resume_argv(self, session):
        return self.argv("rpc_resume", session=session)

    def rpc_argv(self, session=True):
        return self.argv("rpc_session" if session else "rpc")

    def tui_argv(self):
        return self.argv("pty")

    def supports(self, scenario):
        mode = {"version": "version", "print": "print", "print-tools": "print", "print-write": "print", "pty": "pty", "rpc": "rpc"}.get(scenario, scenario)
        return self.arm.supports_mode(mode)

    def cleanup(self):
        for path in {os.path.dirname(self.home), os.path.dirname(self.disk)}:
            _rmtree(path)
        if self.pig_home and not self.pig_home.startswith(self.home + os.sep):
            _rmtree(self.pig_home)
