# SPDX-License-Identifier: Apache-2.0
"""`buffon perfcheck`: can this host count instructions? (docs/METHODOLOGY.md section 4)

Instruction counts need `perf_event_open`, which a kernel (`perf_event_paranoid`), a missing capability (CAP_PERFMON) or a container runtime's seccomp profile can refuse. The check asks
the host what it allows and then proves it: it runs a small process under the same counter session a measured sample uses and reads the instructions back. On a Kubernetes site the
same check runs in one pod per target node (the pod is the measured environment), then stops; a node that cannot count is reported with the reason, and a run on it headlines CPU time."""
import json
import os
import subprocess
import sys

from .runner import cgroup, perfcount

CAP_SYS_ADMIN, CAP_PERFMON = 21, 38
EXIT_NO_COUNTS = 3


def status_fields(path="/proc/self/status"):
    """Seccomp mode and effective capabilities of this process, from /proc: {"seccomp": 0|1|2|None, "cap_eff": int|None}."""
    out = {"seccomp": None, "cap_eff": None}
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("Seccomp:"):
                    out["seccomp"] = int(line.split()[1])
                elif line.startswith("CapEff:"):
                    out["cap_eff"] = int(line.split()[1], 16)
    except (OSError, ValueError, IndexError):
        pass
    return out


def count_once(info):
    """Run a small process under a counter session exactly as a sample does and return what it read ({} when the host gives no counts)."""
    saved = cgroup.PERF
    cgroup.PERF = info if info["available"] else None
    meter = cgroup.RusageMeter()
    try:
        meter.popen([sys.executable, "-c", "sum(range(300000))"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        meter.wait(60)
        return meter.perf()
    finally:
        meter.close()
        cgroup.PERF = saved


def collect(probe=perfcount.probe, count=count_once, status=status_fields):
    """What this host allows and what a counted process read: the record `perfcheck.json` holds."""
    info = probe()
    got = count(info) if info["available"] else {}
    st = status()
    cap = st["cap_eff"]
    counted = bool(got.get("instructions"))
    if counted:
        reason = None if got.get("perf_scope") == "user+kernel" else info.get("reason")
    elif info["available"]:
        reason = "perf_event_open opened a counter but the counted process read no instructions (a virtual machine without a hardware counter, or the counter was not scheduled)"
    else:
        reason = info["reason"]
    return {"counted": counted, "headline": "instructions" if counted else "cpu time", "scope": got.get("perf_scope") if counted else None, "instructions": got.get("instructions"),
            "cycles": got.get("cycles"), "reason": reason, "paranoid": info.get("paranoid"), "seccomp": st["seccomp"],
            "cap_perfmon": None if cap is None else bool(cap >> CAP_PERFMON & 1), "cap_sys_admin": None if cap is None else bool(cap >> CAP_SYS_ADMIN & 1),
            "kernel": os.uname().release, "machine": os.uname().machine}


def summarize(records):
    """{"nodes": [...], "all_counted": bool, "text": one line per node}: `records` is [(node, perfcheck record)]."""
    rows = [dict(r, node=node) for node, r in records]
    lines = []
    for r in rows:
        lines.append(f"{r['node']}: " + (f"instructions counted ({r['scope']}), perf_event_paranoid {r['paranoid']}" + (f"; {r['reason']}" if r.get("reason") else "")
                                           if r["counted"] else f"NO instruction counts, CPU time is the headline: {r['reason']} (perf_event_paranoid {r['paranoid']}, seccomp {r['seccomp']}, CAP_PERFMON {r['cap_perfmon']})"))
    return {"nodes": rows, "all_counted": bool(rows) and all(r["counted"] for r in rows), "text": "\n".join(lines)}


def node_records(out):
    """[(node, record)] a Kubernetes check left under `out`: one run directory per node when several pods ran, else `out` itself."""
    dirs = []
    outcome = os.path.join(out, "cluster-outcome.json")
    if os.path.exists(outcome):
        with open(outcome) as f:
            dirs = [o["dir"] for o in json.load(f).get("outcomes", []) if o.get("dir")]
    dirs = [os.path.join(out, d) for d in dirs] or [out]
    records = []
    for d in dirs:
        path = os.path.join(d, "perfcheck.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            rec = json.load(f)
        node = os.path.basename(d)
        facts = os.path.join(d, "cluster-facts.json")
        if os.path.exists(facts):
            with open(facts) as f:
                node = json.load(f).get("node") or node
        records.append((node, rec))
    return records


def main(args):
    """Local: check this host (and write perfcheck.json under --out). Kubernetes site: one pod per target node runs the same check, then stops."""
    from . import site as sitelib
    from .backend import BackendError, Session, get_backend

    s = sitelib.load(args.site)
    out = os.path.abspath(args.out) if args.out else None
    if s.backend != "kubernetes":
        rec = collect()
        if out:
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "perfcheck.json"), "w") as f:
                json.dump(rec, f, indent=1)
        print(json.dumps(rec, indent=1) if args.json else summarize([("this host", rec)])["text"])
        return 0 if rec["counted"] else EXIT_NO_COUNTS
    if not out:
        raise BackendError("a Kubernetes perfcheck needs --out")
    b = get_backend(s)
    b.check()
    bundle_dir = os.path.abspath(args.bundle) if args.bundle else None
    if s.kube.bundle and not bundle_dir:
        raise BackendError("the site runs a bundle: give the bundle directory with --bundle")
    argv = [sys.executable, "-m", "buffon", "perfcheck", "--out", out]
    session = Session(argv=argv, run_dir=out, cpus=s.kube.cpus, deadline_s=600, bundle=bundle_dir, nodes=args.nodes.split(",") if args.nodes else None)
    result = b.run(session)
    records = node_records(out)
    summary = summarize(records)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "perfcheck-summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(summary["text"] or f"buffon: perfcheck: no pod handed back a perfcheck.json (exit {result.exit_code})")
    if not records:
        return result.exit_code or 1
    return 0 if summary["all_counted"] else EXIT_NO_COUNTS
