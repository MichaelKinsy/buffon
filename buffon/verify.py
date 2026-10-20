# SPDX-License-Identifier: Apache-2.0
"""`buffon verify <run dir>`: the checks a run directory must pass before it is published. Each check is a function (run_dir, raw) -> [problem strings]; `CHECKS` is the registry,
so a new check is one function and one entry. A directory with any problem is rejected (exit 1).

Disclosure (Run Rules 5): host.json carries every key in sysinfo.REQUIRED, and a null value has its reason in `unavailable`. A run without a platform specification is not
a result, whatever its numbers say."""
import json
import os

from .report import cells as cellmath
from .runner import raw as rawlib, sysinfo


def _load(run_dir, name):
    path = os.path.join(run_dir, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def check_raw(run_dir, raw):
    if raw is None:
        return ["raw.json is missing"]
    try:
        rawlib.validate(raw)
    except rawlib.RawError as error:
        return [f"raw.json is invalid: {error}"]
    return []


def check_host_disclosure(run_dir, raw):
    host = _load(run_dir, "host.json")
    if host is None:
        return ["host.json is missing: a run without a platform specification is not a result"]
    problems = [f"host.json lacks `{key}`" for key in sysinfo.REQUIRED if key not in host]
    unavailable = host.get("unavailable") or {}
    for key in sysinfo.REQUIRED:
        if key in host and host[key] is None and key not in unavailable:
            problems.append(f"host.json has `{key}` = null without a reason in `unavailable`")
    if host.get("host_class") not in ("A", "B"):
        problems.append("host.json does not state the host class (A or B)")
    return problems


def check_host_class(run_dir, raw):
    if raw is None:
        return []
    run = raw.get("run", {})
    problems = []
    if run.get("host_class") not in ("A", "B") or not run.get("preflight"):
        problems.append("raw.json does not carry the preflight result and host class")
    elif raw.get("hardware", {}).get("quiet_dedicated") and run["host_class"] != "A":
        problems.append("the run is labelled quiet-dedicated but the host is class B")
    host = _load(run_dir, "host.json")
    if host and run.get("host_class") and host.get("host_class") != run["host_class"]:
        problems.append("host.json and raw.json disagree about the host class")
    return problems


def check_provenance(run_dir, raw):
    if raw is None:
        return []
    problems = []
    if not raw.get("lock_sha256"):
        problems.append("raw.json has no arms.lock digest: the arms are not pinned")
    runner = raw.get("runner", {})
    if not runner.get("commit") or runner.get("dirty"):
        problems.append("the runner checkout is unknown or dirty: record what ran")
    if not raw.get("run", {}).get("lock_file"):
        problems.append("raw.json does not record the host lock")
    return problems


def check_isolation(run_dir, raw):
    if raw is None:
        return []
    stamp = raw.get("run", {}).get("isolation")
    if not stamp or stamp.get("isolation") not in ("container", "pod-guaranteed", "none"):
        return ["raw.json does not state the isolation (container, pod-guaranteed or none)"]
    if stamp["isolation"] == "none" and (stamp.get("comparable") or stamp.get("stamp") != "uncontained, not comparable"):
        return ["an uncontained run must be stamped 'uncontained, not comparable'"]
    if stamp["isolation"] == "pod-guaranteed":
        return check_pod(run_dir, raw, stamp)
    return []


def check_pod(run_dir, raw, stamp):
    """A pod-guaranteed run (buffon/envelope/pod.py): the stamp names a Guaranteed pod, every sample ran on its node and cpuset with QoS Guaranteed, and what the
    API server said about the pod and its node (node.json, written by the runner) does not contradict it."""
    from .envelope import pod as podlib
    start = stamp.get("pod") or {}
    problems = []
    if stamp.get("comparable") is not True or start.get("qos") != "Guaranteed" or not start.get("cpuset") or not start.get("node"):
        problems.append("the pod-guaranteed stamp does not record a comparable Guaranteed pod with its node and cpuset")
    drift = podlib.sample_drift(start, raw.get("samples") or [])
    if drift:
        problems.append(f"{len(drift)} samples do not match the pod the run is stamped with, e.g. {drift[0]}")
    node = _load(run_dir, "node.json") or {}
    if not node:
        problems.append("node.json (the API server's view of the pod and its node) is missing")
    if node and node.get("podQosClass") != "Guaranteed":
        problems.append(f"the API server reports the pod's QoS class as {node.get('podQosClass') or 'unknown'}, not Guaranteed")
    if node.get("cpuManagerPolicy") not in (None, "static", "unreadable"):
        problems.append(f"the node's CPU manager policy is {node['cpuManagerPolicy']}, not static: the pod's cores are not exclusive")
    image = node.get("podImageID") or ""
    if node and "sha256:" not in image:
        problems.append(f"the API server reports no image digest for the pod ({image or 'none'})")
    return problems


HOME_KEYS = ("fresh", "pre_files", "pre_sha256", "post_files", "post_sha256", "written")
HOME_EXEMPT = ("soak", "reliability")   # their own drivers run the arms for minutes; the per-sample home proof is for one-sample-per-process workloads


def check_home(run_dir, raw):
    """Per-run isolation is proven, not claimed: every sample that started a process records that its home was created fresh and what it held before and after the process, and a sample's home
    before the process equals every other round's of the same arm, workload and API (nothing a previous sample left was there)."""
    if raw is None:
        return []
    problems, missing, stale, before = [], [], [], {}
    for s in raw.get("samples", []):
        if s["scenario"].split("/")[0] in HOME_EXEMPT or s.get("quiet_gave_up"):
            continue
        label = f"{s['arm']} {s['scenario']} {cellmath.variant(s) or '-'} round {s['round']}"
        home = s.get("home")
        if not isinstance(home, dict) or any(k not in home for k in HOME_KEYS):
            missing.append(label)
            continue
        if home["fresh"] is not True:
            stale.append(label)
        before.setdefault((s["arm"], s["scenario"], cellmath.variant(s)), {}).setdefault(home["pre_sha256"], []).append(label)
    if missing:
        problems.append(f"{len(missing)} sample(s) carry no home isolation proof (home.fresh, pre_sha256, post_sha256, ...), first: {missing[0]}")
    if stale:
        problems.append(f"{len(stale)} sample(s) found a leftover home from an earlier sample, first: {stale[0]}")
    for (arm, scenario, api), digests in sorted(before.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        if len(digests) > 1:
            problems.append(f"{arm} {scenario} {api or '-'}: the home before the process differed between samples ({len(digests)} different states): a sample did not start from the same fresh home")
    return problems


CHECKS = [("home", check_home), ("isolation", check_isolation), ("raw", check_raw), ("host-disclosure", check_host_disclosure), ("host-class", check_host_class), ("provenance", check_provenance)]


def verify(run_dir):
    """[(check name, [problems])] for one run directory."""
    raw = _load(run_dir, "raw.json")
    return [(name, fn(run_dir, raw)) for name, fn in CHECKS]


def main(run_dirs, out=print):
    bad = 0
    for run_dir in run_dirs:
        results = verify(run_dir)
        failed = [(n, p) for n, p in results if p]
        out(f"{run_dir}: {'REJECTED' if failed else 'ok'}")
        for name, problems in results:
            out(f"  {'FAIL' if problems else 'pass'}  {name}")
            for problem in problems:
                out(f"        {problem}")
        bad += bool(failed)
    return 1 if bad else 0
