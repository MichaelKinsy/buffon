# SPDX-License-Identifier: Apache-2.0
"""Run the probe set: install the arms, run every probe on the reference, on a second copy of the reference (the determinism check) and on each harness; write faithfulness.json."""
import fnmatch
import json
import os
import time
import traceback

from ..arms import install, lock, manifest
from ..mock import MockServer
from ..runner import egress, facts as factlib
from . import PROBE_SET_VERSION, probes as probelib, score
from .lab import EgressViolation, Lab, Skip


class Context:
    def __init__(self, lab, ref_arm, timeout):
        self.lab, self.ref_arm, self.timeout, self.cache = lab, ref_arm, timeout, {}
        self._help = {}

    def help_text(self, arm):
        if arm.id not in self._help:
            setup = self.lab.prepare(arm, "help", "openai-completions")
            obs = self.lab.run(arm, setup, [arm.binary, "--help"], timeout=20, snapshot=False)
            self._help[arm.id] = obs.stdout + obs.stderr
        return self._help[arm.id]


def run_probe(ctx, probe, arm):
    reason = probe.applies(arm) if probe.applies else None
    if reason:
        return {"status": "na", "reason": reason}
    t0 = time.monotonic()
    try:
        obs = probe.run(ctx, arm)
    except Skip as why:
        return {"status": "skip", "reason": str(why)}
    except EgressViolation as why:   # the same rule as a benchmark sample: a connection outside loopback fails the probe
        return {"status": "error", "reason": str(why), "egress": why.remotes}
    except Exception as error:  # a probe that crashes is recorded, never dropped
        return {"status": "error", "reason": f"{error!r}", "traceback": "".join(traceback.format_exception(error))[-600:]}
    return {"status": "ok", "hash": score.digest(obs), "obs": obs, "wall_s": round(time.monotonic() - t0, 2)}


def run(arm_ids, reference="pi-node", out="faith", source_dir=None, only=None, cache_dir=None, work_dir=None, timeout=60, log=print, offline=False):
    arms = {a: manifest.load_arm(a) for a in dict.fromkeys([reference, *arm_ids])}
    os.makedirs(out, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with install.Workspace(install.Cache(cache_dir or os.path.join(os.path.expanduser("~"), ".cache", "buffon"), offline=offline), work_dir=work_dir) as ws:
        for arm in arms.values():
            log(f"buffon: installing {arm.id} {arm.version}")
            ws.install(arm)
            if arm.skip:
                log(f"buffon: {arm.id} cannot run: {arm.skip}")
        ref = arms[reference]
        if ref.skip:
            raise SystemExit(f"the reference {reference} cannot run: {ref.skip}")
        twin = ws.clone(ref, reference + "-b")
        twin.twin_of = reference
        runnable = [a for a in arms.values() if not a.skip and a.id != reference]
        with MockServer() as server:
            lab = Lab(ws, server, ws.work)
            ctx = Context(lab, ref, timeout)
            help_text = ctx.help_text(ref)
            probe_list = probelib.all_probes(help_text, source_dir)
            if only:
                probe_list = [p for p in probe_list if any(fnmatch.fnmatch(p.id, pat) for pat in only)]
            log(f"buffon: {len(probe_list)} probes (set {PROBE_SET_VERSION}), reference {reference} {ref.version}")
            results = {}
            for arm in [ref, twin, *runnable]:
                results[arm.id] = {}
                for i, p in enumerate(probe_list, 1):
                    results[arm.id][p.id] = run_probe(ctx, p, arm)
                    if i % 20 == 0:
                        log(f"buffon: {arm.id} {i}/{len(probe_list)}")
                log(f"buffon: {arm.id} done")
            arm_info = {a.id: {"caveat": a.caveat, "version": a.version, "version_line": a.version_line, "licence": a.licence, "pi_extensions": a.pi_extensions, "twin_of": a.twin_of,
                               "executable_sha256": manifest.sha256_file(os.path.realpath(a.binary)), "install_tree_sha256": install.tree_sha256(ws.installed_tree(a))} for a in [ref, twin, *runnable]}
    unstable = sorted(p.id for p in probe_list if results[reference][p.id].get("hash") != results[twin.id][p.id].get("hash") and results[reference][p.id]["status"] == "ok")
    rules = score.load_intentional()
    scores = {a.id: score.score_arm(probe_list, results[a.id], results[reference], unstable, rules, a.id) for a in [twin, *runnable]}
    ref_row = score.score_arm(probe_list, results[reference], results[reference], unstable, rules, reference)
    doc = {"kind": "buffon-faithfulness", "probe_set_version": PROBE_SET_VERSION, "started_utc": started, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "reference": {"arm": reference, "version": ref.version, "version_line": ref.version_line}, "arms": arm_info, "lock_sha256": lock.lock_hash() if os.path.exists(lock.LOCK_FILE) else None,
           "runner": runner_identity(),
           "probes": [{"id": p.id, "dim": p.dim, "title": p.title, "cite": p.cite} for p in probe_list], "unstable": unstable,
           "egress": {"violations": lab.violations, "audit": egress.describe()},
           "results": results, "scores": scores, "reference_scores": ref_row, "twin": twin.id}
    with open(os.path.join(out, "faithfulness.json"), "w") as f:
        json.dump(doc, f, indent=1, default=lambda x: sorted(x) if isinstance(x, set) else str(x))
    return doc


def runner_identity():
    try:
        f = factlib.collect(manifest.ROOT)
    except Exception:  # identity is best effort here; the benchmark runner records it strictly
        return {}
    return {"commit": f.get("runner_commit"), "tree": f.get("runner_tree"), "dirty": f.get("runner_dirty")}
