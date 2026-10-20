# SPDX-License-Identifier: Apache-2.0
"""The isolated place one durable sample runs in: a fresh HOME and disk directory, the arm's scrubbed environment, and the sample directory that holds the staged store, the script, the
ledger and the request log. It has the shape the engine expects of a harness (`home_proof`, `isolation_env`, `cleanup`), so a sample's home is proven fresh like every other family's.

Nothing here tunes a runtime: the environment is the operator's locale and time zone, HOME and the XDG variables inside the throwaway tree, PATH (the arm's runtime directory, then the
system's) and whatever the arm's manifest declares in `[env]`."""
import os
import re

from ..arms.manifest import slot_name
from ..arms.writers import DUMMY_KEY
from ..runner import harness as harnesslib
from ..runner.harness import SYSTEM_PATH, confine, scrubbed_environ


class DurableHost:
    """One arm prepared for one sample. `sample_dir` is the adapter's working directory."""

    def __init__(self, arm, work, tag=""):
        self.arm, self.work = arm, work
        name = slot_name(arm.id) + (f"-{tag}" if tag else "")
        base = os.path.join(work, name)
        self.stale = os.path.exists(base)
        if self.stale:
            harnesslib._rmtree(base)
        self.home = os.path.join(base, "home")
        self.disk = os.path.join(base, "disk")
        self.sample_dir = self.cwd = os.path.join(base, "sample")
        for d in (self.home, self.sample_dir, os.path.join(self.disk, "tmp"), os.path.join(self.disk, "cache")):
            os.makedirs(d, exist_ok=True)
        self.base = base
        self.store = os.path.join(self.sample_dir, "store.sqlite")
        self.script = os.path.join(self.sample_dir, "script.json")
        self.ledger = os.path.join(self.sample_dir, "ledger.txt")
        self.request_log = os.path.join(self.sample_dir, "requests.jsonl")
        self.capture = os.path.join(self.sample_dir, "capture.jsonl")
        env = scrubbed_environ()
        env["PATH"] = os.pathsep.join(list(arm.path_dirs) + list(SYSTEM_PATH))
        env.update({"HOME": self.home, "XDG_CONFIG_HOME": os.path.join(self.home, ".config"), "XDG_DATA_HOME": os.path.join(self.home, ".local", "share"),
                    "XDG_CACHE_HOME": os.path.join(self.disk, "cache"), "XDG_STATE_HOME": os.path.join(self.home, ".local", "state"), "TMPDIR": os.path.join(self.disk, "tmp"),
                    "NO_COLOR": "1", "NO_PROXY": "127.0.0.1,localhost,::1", "no_proxy": "127.0.0.1,localhost,::1"})
        subs = {"home": self.home, "disk": self.disk, "agent_dir": os.path.join(self.home, ".agent"), "dummy_key": DUMMY_KEY, "install_dir": getattr(arm, "install_dir", None), **getattr(arm, "vars", {})}
        for k, v in arm.env.items():
            env[k] = re.sub(r"\{(\w+)\}", lambda m: subs.get(m.group(1), m.group(0)), v)
        confine(env, [work, getattr(arm, "vars", {}).get("shared_dir")], [("sample", self.sample_dir)])
        self.env = env
        self.home_pre = self.fingerprint()

    def argv(self):
        """The adapter's command: the arm's executable, serving the protocol (a Node bundle has a shebang, a Go adapter is native)."""
        return [self.arm.binary]

    def fingerprint(self):
        out = {"home/" + k: v for k, v in harnesslib.fingerprint(self.home).items()}
        out.update({"disk/" + k: v for k, v in harnesslib.fingerprint(self.disk).items()})
        return out

    def home_proof(self):
        return harnesslib.home_record(self.home_pre, self.fingerprint(), self.stale)

    def isolation_env(self):
        out = {}
        for k, v in sorted(self.env.items()):
            if os.environ.get(k) != v:
                out[k] = "<dummy key>" if v == DUMMY_KEY else v.replace(self.work, "<work>")
        return {"set": out, "scrubbed": sorted(k for k in os.environ if k not in self.env), "inherited": sorted(k for k in harnesslib.KEEP_VARS if k in os.environ)}

    def cleanup(self):
        harnesslib._rmtree(self.base)


def host_for(ctx, arm, tag):
    """The sample's host for `arm`, registered with the context so the engine proves its home and removes it after the sample (`ctx.release()`)."""
    key = (arm.id, tag)
    if key not in ctx._harnesses:
        ctx._harnesses[key] = DurableHost(arm, ctx.work, tag)
    return ctx._harnesses[key]
