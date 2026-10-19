#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A stand-in for buffon-cluster that runs the session for real on this machine, as a pod would: `render` succeeds, `run` executes the session argv (with {out} replaced by the run
directory the backend collects) pinned to the CPUs named by BUFFON_FAKE_CLUSTER_CPUS (one list, or `node=list;node=list`) with its own TMPDIR, writes the pod-side facts files, and prints the outcome list. No cluster, no kubectl.

Nodes: BUFFON_FAKE_CLUSTER_NODES (comma-separated, default fake-node) are the cluster's nodes. `nodes` ranks them; `run -nodes a,b` or `run -spread N` runs the session once per node,
one after the other, in buffon-cluster's layout (one node: <out>/<run>/; several: <out>/<run>/<run>-n<i>/ with spread.json). `calibrate` and `check` judge local files, so they go to
the real binary named by BUFFON_FAKE_CLUSTER_REAL when it is set.
Used by tests/test_k8s_e2e.py to drive `buffon run` and `buffon campaign` on a Kubernetes profile end to end."""
import json
import os
import subprocess
import sys


def cluster_nodes():
    return [n for n in os.environ.get("BUFFON_FAKE_CLUSTER_NODES", "fake-node").split(",") if n]


def node_cpus(node):
    """The CPUs a node's "pod" runs on: BUFFON_FAKE_CLUSTER_CPUS is a list for every node, or `node=list;node=list` (sessions on two nodes at once then do not share CPUs)."""
    value = os.environ.get("BUFFON_FAKE_CLUSTER_CPUS", "")
    if "=" in value:
        value = dict(part.split("=", 1) for part in value.split(";") if part).get(node, "")
    if value:
        return sorted(int(c) for c in value.split(",") if c)
    return sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else list(range(os.cpu_count() or 1))   # macOS has no affinity API


def run_one(spec, argv_template, run, node, run_dir):
    os.makedirs(run_dir, exist_ok=True)
    allowed = node_cpus(node)
    tmp = os.path.join(os.path.dirname(run_dir), "." + os.path.basename(run_dir) + "-tmp")   # each pod has its own /data/tmp (and the host lock in it)
    os.makedirs(tmp, exist_ok=True)
    # A busy development host stands in for quiet nodes: BUFFON_FAKE_CLUSTER_SESSION_ARGS (for example relaxed --quiet-* gates) is appended to the session's argv.
    session = [a.replace("{out}", run_dir) for a in argv_template] + os.environ.get("BUFFON_FAKE_CLUSTER_SESSION_ARGS", "").split()
    env = {k: v for k, v in os.environ.items() if not k.startswith("BUFFON_FAKE_CLUSTER")}
    # A pod has its own filesystem, so its own host lock: two "pods" here must not share /run/lock/buffon.lock (or another buffon run's).
    env.update(spec.get("env") or {}, NODE_NAME=node, POD_NAME=run + "-pod", TMPDIR=tmp, BUFFON_LOCK_FILE=os.path.join(tmp, "buffon.lock"))
    done = subprocess.run(session, env=env, stdout=sys.stderr, preexec_fn=(lambda: os.sched_setaffinity(0, allowed)) if hasattr(os, "sched_setaffinity") else None)
    with open(os.path.join(run_dir, "cluster-facts.json"), "w") as f:
        json.dump({"node": node, "cpuSet": "exclusive", "pin": {"cpus": ",".join(map(str, allowed[:-1])), "fixedClock": True}, "session": {"exit": done.returncode, "throttledUsec": 0}}, f)
    with open(os.path.join(run_dir, "node.json"), "w") as f:
        json.dump({"node": node, "cpuManagerPolicy": "static"}, f)
    return {"run": run, "node": node, "runDir": run_dir, "ok": done.returncode == 0}


def main(argv):
    command = argv[1]
    if command in ("calibrate", "check"):
        real = os.environ.get("BUFFON_FAKE_CLUSTER_REAL")
        if not real:
            sys.stderr.write("fake-cluster: set BUFFON_FAKE_CLUSTER_REAL to a buffon-cluster binary for calibrate and check\n")
            return 2
        return subprocess.run([real, *argv[1:]]).returncode
    flags = argv[2:]
    args = dict(zip(flags[::2], flags[1::2]))
    if command == "nodes":
        print(json.dumps({"basis": "cluster", "nodes": [{"name": n, "freeCpu": 8.0, "freeMemory": 1 << 34, "allocatableCpu": 8.0, "pods": 0} for n in cluster_nodes()]}))
        return 0
    if command == "render":
        return 0
    with open(args["-session"]) as f:
        spec = json.load(f)
    listed = [n for n in args.get("-nodes", "").split(",") if n]
    spread = int(args.get("-spread", 0))
    nodes = (listed or cluster_nodes())[:spread] if spread else (listed or [cluster_nodes()[0]])
    if spread:
        os.makedirs(args["-out"], exist_ok=True)
        with open(os.path.join(args["-out"], spec["run"] + "-nodes.json"), "w") as f:
            json.dump({"basis": "cluster", "nodes": [{"name": n} for n in nodes]}, f)
    base = os.path.join(args["-out"], spec["run"])
    if len(nodes) == 1:
        outs = [run_one(spec, spec["argv"], spec["run"], nodes[0], base)]
    else:
        outs = [run_one(spec, spec["argv"], f"{spec['run']}-n{i + 1}", n, os.path.join(base, f"{spec['run']}-n{i + 1}")) for i, n in enumerate(nodes)]
        with open(os.path.join(base, "spread.json"), "w") as f:
            json.dump({"run": spec["run"], "nodes": nodes, "sessions": outs}, f)
    print(json.dumps(outs))
    sys.stderr.write("fake-cluster: session finished\n")
    return 0 if all(o["ok"] for o in outs) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
