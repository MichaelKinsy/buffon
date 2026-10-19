# SPDX-License-Identifier: Apache-2.0
"""The pod envelope: a Kubernetes session pod as the container envelope (isolation `pod-guaranteed`).

A pod qualifies when it holds, for the whole session, what the container envelope holds for each sample (docs/ENVELOPE.md):

    P1  Guaranteed QoS with exclusive cores. The kubelet's static CPU manager gives exclusive CPUs only to a Guaranteed container with an integer CPU
        request. Seen from inside, the container's cpuset has exactly the requested CPUs, fewer than the node has online, the CFS quota equals them
        (or is off, as the kubelet leaves it for exclusive CPUs with its DisableCPUQuotaWithExclusiveCPUs feature) and memory.max is a limit.
    P2  the image is pinned by digest (the pod's BUFFON_IMAGE_REF; with a bundle, the base image, and the bundle is checked against its ARTIFACTS.sha256)
    P3  read-only root filesystem
    P4  a non-root user
    P5  no network but the mock: the mock listens on loopback in the pod, and a connection to the cluster's API service does not get through (the Job's
        NetworkPolicy, cluster/templates/job.yaml); a cluster that does not enforce the policy fails P5

The session checks P1-P5 before it measures and records the pod facts (node, cpuset, QoS) in every sample. The runner records the API server's view
(node.json: podQosClass, podImageID, cpuManagerPolicy). When any check fails, at the start or in a sample, the run is stamped "uncontained, not
comparable" with the reasons; `buffon verify` rejects a pod-guaranteed run whose samples or node.json disagree with the stamp.
"""
import json
import os
import re
import socket

MODE = "pod-guaranteed"
UNCONTAINED = {"isolation": "none", "comparable": False, "stamp": "uncontained, not comparable"}
_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def parse_cpus(text):
    out = set()
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        out.update(range(int(lo), int(hi or lo) + 1))
    return out


class Probe:
    """What the checks read; tests replace it. root is the filesystem root; env the process environment."""

    def __init__(self, root="/", env=None, connect=None, euid=None):
        self.root, self.env = root, os.environ if env is None else env
        self.connect = connect or _connect
        self.euid = os.geteuid() if euid is None else euid

    def read(self, path):
        return _read(os.path.join(self.root, path.lstrip("/")))

    def interfaces(self):
        try:
            return sorted(os.listdir(os.path.join(self.root, "sys/class/net")))
        except OSError:
            return []


def _connect(host, port, timeout=3.0):
    """True when a TCP connection to host:port gets through within timeout."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def cgroup(probe):
    """The container's own cgroup (v2 under a cgroup namespace): its cpuset, CPU quota and memory limit. On cgroup v1 the files are absent (None), so P1 fails."""
    base = "sys/fs/cgroup"
    return {"cpuset": probe.read(f"{base}/cpuset.cpus.effective"), "cpu_max": probe.read(f"{base}/cpu.max"), "memory_max": probe.read(f"{base}/memory.max"),
            "online": probe.read("sys/devices/system/cpu/online")}


def qos(cg, requested):
    """("Guaranteed", []) when the cgroup shows what only a Guaranteed container with exclusive cores gets, else ("not Guaranteed", reasons)."""
    reasons = []
    cpus = parse_cpus(cg.get("cpuset"))
    online = parse_cpus(cg.get("online"))
    if not requested or len(cpus) != requested:
        reasons.append(f"the cpuset {cg.get('cpuset')} does not hold exactly the {requested} requested CPUs")
    elif len(online) <= requested:
        reasons.append(f"the node has {len(online)} CPUs online, so a cpuset of {requested} does not show exclusive cores")
    # A limit of exactly the requested CPUs; or none at all, which the kubelet sets for a container with exclusive CPUs when its
    # DisableCPUQuotaWithExclusiveCPUs feature gate is on.
    quota, _, period = (cg.get("cpu_max") or "").partition(" ")
    if not (period.isdigit() and int(period) and (quota == "max" or quota.isdigit() and int(quota) == requested * int(period))):
        reasons.append(f"cpu.max {cg.get('cpu_max')!r} is neither a limit of {requested} CPUs nor unlimited")
    if not (cg.get("memory_max") or "").isdigit():
        reasons.append(f"memory.max {cg.get('memory_max')!r} is not a limit")
    return ("Guaranteed" if not reasons else "not Guaranteed"), reasons


def read_only_root(probe):
    for line in (probe.read("proc/self/mountinfo") or "").splitlines():
        fields = line.split()
        if len(fields) > 5 and fields[4] == "/":
            return "ro" in fields[5].split(",")
    return False


def pod_facts(probe):
    """The facts buffon-cluster's pod wrote for the session (cluster/pod.go, BUFFON_POD_FACTS), or {}."""
    path = probe.env.get("BUFFON_POD_FACTS")
    text = _read(path) if path else None
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


def check(probe=None):
    """(facts, reasons): the pod facts the stamp records, and every envelope guarantee P1-P5 that does not hold (empty when the pod qualifies)."""
    probe = probe or Probe()
    pf = pod_facts(probe)
    reasons = []
    if not pf:
        reasons.append("no pod facts (BUFFON_POD_FACTS): the session is not running in a buffon-cluster pod")
    requested = int(pf.get("requestedCpus") or 0)
    cg = cgroup(probe)
    klass, why = qos(cg, requested)
    reasons += [f"P1: {w}" for w in why]
    image = probe.env.get("BUFFON_IMAGE_REF") or pf.get("image") or ""
    if not _DIGEST.search(image):
        reasons.append(f"P2: the image {image or '(none)'} is not pinned by digest")
    if pf.get("delivery") == "bundle" and not pf.get("artifactsSha256"):
        reasons.append("P2: the bundle's ARTIFACTS.sha256 was not read")
    if not read_only_root(probe):
        reasons.append("P3: the root filesystem is writable")
    if probe.euid == 0:
        reasons.append("P4: the session runs as root")
    others = [i for i in probe.interfaces() if i != "lo"]
    host, port = probe.env.get("KUBERNETES_SERVICE_HOST"), probe.env.get("KUBERNETES_SERVICE_PORT", "443")
    if others:
        if not host:
            reasons.append(f"P5: the pod has network interfaces ({_some(others)}) and no cluster service to check that they are closed")
        elif probe.connect(host, port):
            reasons.append(f"P5: a connection to the cluster's API service {host}:{port} got through; the pod has a network (the cluster does not enforce the Job's NetworkPolicy)")
    facts = {"node": probe.env.get("NODE_NAME") or pf.get("node"), "pod": probe.env.get("POD_NAME") or pf.get("pod"), "qos": klass, "cpuset": cg.get("cpuset"),
             "requested_cpus": requested, "cpu_max": cg.get("cpu_max"), "memory_max": cg.get("memory_max"), "image": image or None, "delivery": pf.get("delivery"),
             "artifacts_sha256": pf.get("artifactsSha256"), "read_only_root": read_only_root(probe), "uid": probe.euid, "interfaces": probe.interfaces()}
    return facts, reasons


def _some(names, n=5):
    return ", ".join(names[:n]) + (f" and {len(names) - n} more" if len(names) > n else "")


def sample_facts(start, probe=None):
    """The pod facts of one sample: the node, the cpuset and the QoS the cgroup shows now."""
    probe = probe or Probe()
    cg = cgroup(probe)
    return {"node": probe.env.get("NODE_NAME") or start.get("node"), "cpuset": cg.get("cpuset"), "qos": qos(cg, start.get("requested_cpus") or 0)[0]}


def sample_drift(start, samples):
    """Reasons a sample's pod facts differ from the start's: another node, another cpuset, or a QoS that is no longer Guaranteed."""
    out = []
    for s in samples:
        pod = s.get("pod")
        if not isinstance(pod, dict):
            out.append(f"{s.get('arm')} {s.get('scenario')} round {s.get('round')} has no pod facts")
            continue
        for key in ("node", "cpuset"):
            if pod.get(key) != start.get(key):
                out.append(f"{s.get('arm')} {s.get('scenario')} round {s.get('round')} ran with {key} {pod.get(key)}, the session started with {start.get(key)}")
        if pod.get("qos") != "Guaranteed":
            out.append(f"{s.get('arm')} {s.get('scenario')} round {s.get('round')} ran with QoS {pod.get('qos')}")
    return out


def stamp(facts, reasons, drift=()):
    """The run's isolation stamp: pod-guaranteed and comparable when nothing failed at the start (reasons) and no sample drifted, else uncontained with the reasons
    (the first five drifted samples, and how many more)."""
    drift = list(drift)
    reasons = list(reasons) + drift[:5] + ([f"and {len(drift) - 5} more samples that drifted"] if len(drift) > 5 else [])
    if reasons:
        return dict(UNCONTAINED, requested=MODE, reasons=list(reasons), pod=facts)
    return {"isolation": MODE, "comparable": True, "pod": facts}
