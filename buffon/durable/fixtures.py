# SPDX-License-Identifier: Apache-2.0
"""Fixtures of the durable family (docs/design/DURABLE.md 3.5): a store built once by the reference runtime driving a script through its real loop, cached by what it was built from, copied
for every sample and read once before timing so the page cache is warm for every arm alike.

A fixture is a `specs.Fixture`: a history (kind, turns, variant), the settings it was built under (window, compaction, conversations, document edits). Its identity, `key`, is the sha256 of
those fields, of the script's own sha256 (which holds the generator version, the seed and every byte of every turn) and of the writer: the arm's id, version and executable digest. A different
writer, a different adapter build or a different script is a different store. The store file is checkpointed (`wal_checkpoint(TRUNCATE)` by the runner's own SQLite) and closed, so a copy is one
file. `fixture_writer` in a sample names who built it: a Pi-written store may favour Pi slightly, which is why the same script is also built by the other arm where that finishes in a
reasonable time (`build_by`).

The builder runs outside every sample, before the first measured round (buffon/durable/prepare.py), in its own meter on the harness CPUs."""
import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict

from . import script as scriptlib
from . import specs, store
from .driver import Process
from .host import DurableHost

STORE_FORMAT = 1       # bump when the way a store is built changes (what is driven, in which order)
READ_BLOCK = 1 << 20


class FixtureError(RuntimeError):
    pass


def cache_root(plan):
    """Where fixtures and scripts are kept between runs: under the site's cache directory, next to the downloaded artifacts."""
    return os.path.join(plan.cache_dir, "durable")


def history_script(root, fx, seed):
    """(path, facts) of the script of a fixture's history: turns 0..history-1 and, for a fixture with document edits, the strings the edits append."""
    plan = scriptlib.history_plan(fx.history_kind, fx.history)
    return scriptlib.cached(os.path.join(root, "scripts"), seed, fx.variant, plan, docs=fx.docs)


def measured_script(root, spec, seed, variant, first, count=None):
    """(path, facts) of the script of a workload's measured turns, numbered from `first`."""
    count = spec.measured if count is None else count
    kind = {"bench8": "compat", "mixed": "mixed", "stream": "stream", "large": "large", "fanout": "tasks", "subagent": "subagent", "crash": "crash"}[spec.shape if spec.shape != "tasks" else "fanout"]
    plan = scriptlib.measured_plan(kind, first, count)
    options = {"fanout_n": spec.tasks} if spec.tasks else {}
    return scriptlib.cached(os.path.join(root, "scripts"), seed, variant, plan, **options)


def writer_identity(arm):
    """What makes one arm's stores differ from another's: its id and version and the digests of what ran."""
    rec = getattr(arm, "record", {}) or {}
    return {"arm": arm.id.removesuffix("-b"), "version": arm.version, "executable_sha256": rec.get("adapter_bundle_sha256") or _file_sha(arm.binary), "install": rec.get("package_lock_sha256") or rec.get("commit")}


def _file_sha(path):
    h = hashlib.sha256()
    with open(os.path.realpath(path), "rb") as f:
        for block in iter(lambda: f.read(READ_BLOCK), b""):
            h.update(block)
    return h.hexdigest()


def key_of(fx, script_sha, writer):
    doc = {"store_format": STORE_FORMAT, "fixture": asdict(fx), "script": script_sha, "writer": writer_identity(writer)}
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Built:
    """A fixture's store on disk and what is known about it."""

    def __init__(self, fx, path, facts):
        self.fx, self.path, self.facts = fx, path, facts

    @property
    def sample_fields(self):
        """The `fixture_*` fields every sample of a workload on this fixture carries."""
        f = self.facts
        return {"fixture_sha256": f["script_sha256"], "fixture_seed": f["seed"], "fixture_writer": f["writer"], "fixture_variant": self.fx.variant, "fixture_turns": self.fx.history,
                "fixture_bytes": f["store_bytes"], "fixture_store_sha256": f["store_sha256"]}


def ensure(ctx, fx, writer, seed=specs.SEED, log=print):
    """The fixture `fx` built by `writer`: reused when the cache has it, else built now. Returns Built; raises FixtureError."""
    root = cache_root(ctx.opts)
    spath, sfacts = history_script(root, fx, seed)
    key = key_of(fx, sfacts["sha256"], writer)
    path, meta = os.path.join(root, "stores", f"{key}.sqlite"), os.path.join(root, "stores", f"{key}.json")
    if os.path.exists(path) and os.path.exists(meta):
        with open(meta) as f:
            facts = json.load(f)
        if os.path.getsize(path) == facts["store_bytes"] and _file_sha(path) == facts["store_sha256"]:
            return Built(fx, path, dict(facts, cached=True))
        os.unlink(path)   # a damaged cache entry is never used
    return _build(ctx, fx, writer, seed, spath, sfacts, key, path, meta, log)


def _build(ctx, fx, writer, seed, spath, sfacts, key, path, meta, log):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    host = DurableHost(writer, ctx.work, tag=f"fixture-{key[:8]}")
    proc = Process(host, writer, timeout=3600)
    started = time.monotonic()
    commits = 0
    try:
        proc.wait_ready()
        ad = proc.adapter
        ad.call("open", store=host.store, script=spath, ledger=host.ledger, mode="runtime", conversations=fx.conversations, create=True, window_tokens=fx.window_tokens,
                compaction={"enabled": fx.compaction, "background_tokens": fx.background_tokens}, partial_interval_ms=None, summary_fails=False, request_log=None, capture=None)
        done = 0
        total = fx.history * fx.conversations
        for conv in range(fx.conversations):
            for n in range(fx.history):
                ex = ad.call("turn", conv=conv, n=n, request_id=f"t{n}", stream=False)
                if ex.get("status") != "done":
                    raise FixtureError(f"{writer.id} built turn {n} of conversation {conv} as {ex.get('status')!r}: {ex.get('reason')}")
                commits = ad.call("barrier").get("commits", commits)
                done += 1
                if done % 250 == 0:
                    log(f"buffon: fixture {fx.label}: {done}/{total} turns, {time.monotonic() - started:.0f} s")
        if fx.docs:
            ad.call("doc_edit", conv=0, count=fx.docs, payload_bytes=scriptlib.DOC_BYTES, **{"from": 0})
        ad.call("close")
        proc.close()
        if proc.adapter.proc.returncode not in (0, None):
            raise FixtureError(f"{writer.id} exited {proc.adapter.proc.returncode} after close")
        store.checkpoint(host.store)
        inspected = store.inspect(host.store)
        facts = {"key": key, "script_sha256": sfacts["sha256"], "seed": seed, "variant": fx.variant, "writer": writer.id.removesuffix("-b"), "writer_version": writer.version,
                 "fixture": asdict(fx), "turns": fx.history, "conversations": fx.conversations, "docs": fx.docs, "build_s": round(time.monotonic() - started, 2), "commits": commits,
                 "store_bytes": inspected["store_bytes"], "tables": inspected.get("store_tables"), "compaction_ids": store.compaction_entry_ids(host.store), "store_sha256": _file_sha(host.store), "generator": sfacts["generator"]}
        tmp = f"{path}.{os.getpid()}.tmp"
        shutil.copyfile(host.store, tmp)
        os.replace(tmp, path)
        with open(f"{meta}.{os.getpid()}.tmp", "w") as f:
            json.dump(facts, f, indent=1, sort_keys=True)
        os.replace(f"{meta}.{os.getpid()}.tmp", meta)
        log(f"buffon: fixture {fx.label} built by {writer.id}: {fx.history} turns, {facts['store_bytes']} bytes, {facts['build_s']} s")
        return Built(fx, path, dict(facts, cached=False))
    except FixtureError:
        raise
    except Exception as error:   # the adapter died, timed out or said no: the fixture has no store
        raise FixtureError(f"{writer.id} could not build the fixture {fx.label}: {error}") from error
    finally:
        proc.release()
        host.cleanup()


def stage(built, host):
    """Copy the fixture's store to the sample and read it once, so every arm starts with the same page-cache state. Returns the bytes read."""
    shutil.copyfile(built.path, host.store)
    total = 0
    with open(host.store, "rb") as f:
        for block in iter(lambda: f.read(READ_BLOCK), b""):
            total += len(block)
    return total
