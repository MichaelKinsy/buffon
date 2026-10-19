# SPDX-License-Identifier: Apache-2.0
"""The Kubernetes backend: one pod per session, through the Go `buffon-cluster` (cluster/README.md).

The backend translates the site profile's `[kubernetes]` table into buffon-cluster's site JSON. It writes the session spec with the run directory
replaced by `{out}`, runs `buffon-cluster run`, and moves what the pod handed back into the session's run directory.

The cluster side owns everything that touches the cluster and the pod: Guaranteed QoS, the node pin or pick, the bundle copy and its sha256 check,
pinning the session to the quietest or exclusive cores, the refusal of cores whose clock scales, the cgroup counters, and the run archive's
sha256 on the way back. Its facts are in `cluster-facts.json` (the pod) and `node.json` (the API server's view of the node) beside the session's
own facts.json, and SessionResult.facts carries them as `cluster` and `node_api`.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from . import BackendError, Session, SessionResult, load_result

# buffon-cluster exit codes: 0 ok, 1 error, 2 usage, 3 noise refusal.
EXIT_USAGE, EXIT_NOISE = 2, 3
_NODE_NAME = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")
_DNS = re.compile(r"[^a-z0-9-]+")


def cluster_binary(env=None):
    """buffon-cluster: $BUFFON_CLUSTER_BIN, else cluster/buffon-cluster in this checkout, else on PATH."""
    env = os.environ if env is None else env
    if env.get("BUFFON_CLUSTER_BIN"):
        return env["BUFFON_CLUSTER_BIN"]
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cluster", "buffon-cluster")
    if os.access(here, os.X_OK):
        return here
    found = shutil.which("buffon-cluster")
    if not found:
        raise BackendError("buffon-cluster is not built: run `go build -o buffon-cluster .` in cluster/, or set BUFFON_CLUSTER_BIN")
    return found


def run_name(run_dir, now=None):
    """A Job name for the session: buffon-<run directory name>-<UTC time>, a DNS label of at most 52 characters."""
    base = _DNS.sub("-", os.path.basename(os.path.normpath(run_dir)).lower()).strip("-")[:24].strip("-") or "session"
    return f"buffon-{base}-{time.strftime('%Y%m%dt%H%M%S', time.gmtime(now))}"


def site_json(kube, bundle=None, cpus=0):
    """buffon-cluster's site JSON from a KubeSite. Secrets appear only as references (secret_env: name, secret, key)."""
    out = {
        "kubeconfig": kube.kubeconfig, "kubeContext": kube.context, "namespace": kube.namespace,
        "cpus": cpus or kube.cpus, "memory": kube.memory, "scratchSize": kube.scratch_size,
        "nodeSelector": dict(kube.node_selector), "tolerations": list(kube.tolerations), "node": kube.node,
        "imagePullSecrets": list(kube.image_pull_secrets), "serviceAccountName": kube.service_account,
        "deadlineSeconds": kube.deadline_seconds, "ttlSecondsAfterFinished": kube.ttl_seconds,
        "allowFrequencyScaling": kube.allow_frequency_scaling, "maxCv": kube.max_cv,
        # Only the reference is copied, whatever else an entry holds: the cluster renders it as a secretKeyRef.
        "secretEnv": [{"name": e["name"], "secret": e["secret"], "key": e["key"]} for e in kube.secret_env],
    }
    if kube.bundle:
        if not bundle:
            raise BackendError("the site runs a bundle (bundle = true) but the session names no bundle directory")
        out["bundle"], out["baseImage"] = os.path.abspath(bundle), kube.base_image
    else:
        out["image"] = kube.image
    return {k: v for k, v in out.items() if v not in ("", None, [], {})}


def session_json(session, run, pin):
    """buffon-cluster's session spec: the argv with the run directory replaced by {out}."""
    run_dir = os.path.normpath(os.path.abspath(session.run_dir))

    def is_run_dir(value):
        return bool(value) and os.path.normpath(os.path.abspath(value)) == run_dir

    argv, named = [], False
    command = list(session.argv)
    # The runner's own interpreter path means nothing in the pod: the pod runs the image's or bundle's python3.
    if command and os.path.isabs(command[0]) and os.path.basename(command[0]).startswith("python"):
        command[0] = "python3"
    for arg in command:
        flag, eq, value = arg.partition("=")
        if is_run_dir(arg):
            argv.append("{out}")
            named = True
        elif eq and flag.startswith("-") and is_run_dir(value):
            argv.append(flag + "={out}")
            named = True
        else:
            argv.append(arg)
    if session.bundle:
        # A bundle pod has no network: the session installs from the bundle's caches (buffon/backend/bundle.py), never from a cache path of this machine.
        kept, skip = [], False
        for arg in argv:
            if skip:
                skip = False
            elif arg in ("--cache-dir", "--npm-cache"):
                skip = True
            elif not arg.startswith(("--cache-dir=", "--npm-cache=")) and arg != "--offline":
                kept.append(arg)
        argv = kept + ["--offline", "--cache-dir", "{root}/cache", "--npm-cache", "{root}/npm-cache"]
    if not named:
        raise BackendError(f"the session's argv never names its run directory {session.run_dir}; the pod's results could not come back")
    spec = {"run": run, "argv": argv, "cpus": session.cpus, "pin": pin, "timeoutSeconds": session.deadline_s or 21600}
    if session.env:
        spec["env"] = dict(session.env)
    return spec


class K8sBackend:
    name = "kubernetes"

    def __init__(self, site, runner=subprocess.run, env=None, now=None):
        self.site, self.runner, self.env, self.now = site, runner, os.environ if env is None else env, now

    def _bin(self):
        return cluster_binary(self.env)

    def check(self, isolation="none"):
        """Refuse early: buffon-cluster renders a Job for a placeholder session without contacting the cluster, so a site it would refuse fails here."""
        k = self.site.kube
        with tempfile.TemporaryDirectory(prefix="buffon-k8s-check-") as tmp:
            probe = Session(argv=["true", os.path.join(tmp, "run")], run_dir=os.path.join(tmp, "run"), cpus=k.cpus, deadline_s=60)
            site = site_json(k, bundle=tmp)
            if k.bundle:
                # The bundle is a run-time input: check the rest of the site with a pinned placeholder image instead.
                site = {key: v for key, v in site.items() if key not in ("bundle", "baseImage")}
                site["image"] = "registry.invalid/check@sha256:" + "0" * 64
            self._call(tmp, "render", site, session_json(probe, "buffon-check", k.pin), [])

    def _call(self, tmp, command, site, spec, extra):
        site_path, spec_path = os.path.join(tmp, "site.json"), os.path.join(tmp, "session.json")
        with open(site_path, "w") as f:
            json.dump(site, f)
        with open(spec_path, "w") as f:
            json.dump(spec, f)
        argv = [self._bin(), command, "-site", site_path, "-session", spec_path] + extra
        env = {k: v for k, v in self.env.items() if not k.startswith("BUFFON_K8S_")}
        done = self.runner(argv, env=env, capture_output=True, text=True)
        if command != "run" and done.returncode != 0:
            raise BackendError(f"buffon-cluster {command}: {done.stderr.strip() or done.returncode}")
        return done

    def node_flags(self, session):
        """buffon-cluster's node choice: the session's nodes (a calibration's), else the site's `nodes` and `spread`, else none (the site's `node` or the scheduler's)."""
        k = self.site.kube
        if session.nodes:
            return ["-nodes", ",".join(session.nodes)]
        flags = ["-spread", str(k.spread)] if k.spread else []
        return flags + (["-nodes", ",".join(k.nodes)] if k.nodes else [])

    def run(self, session: Session) -> SessionResult:
        """Run the session on one node, or the same session on several nodes at once. On several nodes the run directory holds one run directory per node,
        named after the node, and the result's facts list them under `nodes`."""
        k = self.site.kube
        os.makedirs(session.run_dir, exist_ok=True)
        if not session.cpus:
            session.cpus = k.cpus
        run = run_name(session.run_dir, self.now)
        site = site_json(k, session.bundle, session.cpus)
        if session.nodes:
            site.pop("node", None)
        with tempfile.TemporaryDirectory(prefix="buffon-k8s-") as tmp:
            out = os.path.join(tmp, "out")
            done = self._call(tmp, "run", site, session_json(session, run, k.pin), ["-out", out] + self.node_flags(session))
            if done.returncode == EXIT_USAGE:
                raise BackendError(f"buffon-cluster refused the session: {done.stderr.strip()}")
            try:
                outcomes = json.loads(done.stdout or "[]")
            except json.JSONDecodeError as error:
                raise BackendError(f"buffon-cluster printed no outcome: {done.stderr.strip()}") from error
            # A pick among nodes leaves its ranking beside the run; the cluster names a spread's sessions <run>-n<i>.
            _move(os.path.join(out, run + "-nodes.json"), os.path.join(session.run_dir, "cluster-nodes.json"))
            spread = [o for o in outcomes if o.get("run") != run]
            back = os.path.join(out, run)
            if not spread:
                _move_contents(back, session.run_dir)
            else:
                _move(os.path.join(back, "spread.json"), os.path.join(session.run_dir, "spread.json"))
                names = set()
                for o in spread:
                    name = o.get("node") if _NODE_NAME.match(o.get("node") or "") and o.get("node") not in names else o["run"]
                    names.add(name)
                    o["dir"] = name
                    _move_contents(os.path.join(back, o["run"]), os.path.join(session.run_dir, name))
        with open(os.path.join(session.run_dir, "cluster-outcome.json"), "w") as f:
            json.dump({"exit": done.returncode, "outcomes": outcomes, "stderr": done.stderr[-4096:]}, f, indent=2)
        if not spread:
            return self._result(session.run_dir, done.returncode, outcomes)
        nodes = []
        for o in spread:
            r = self._result(os.path.join(session.run_dir, o["dir"]), 0 if o.get("ok") else (done.returncode or 1), [o])
            nodes.append({"node": o.get("node"), "run_dir": r.run_dir, "exit_code": r.exit_code, "node_class": r.facts["node_class"], "pinned_cpus": r.pinned_cpus,
                          "throttled_usec": r.throttled_usec})
        # The session failed when it failed on any node: the first non-zero exit in node order, else the cluster's own.
        exit_code = next((n["exit_code"] for n in nodes if n["exit_code"]), done.returncode)
        return SessionResult(run_dir=session.run_dir, facts={"nodes": nodes, "outcomes": outcomes}, pinned_cpus=[], throttled_usec=sum(n["throttled_usec"] for n in nodes), exit_code=exit_code)

    def nodes(self, count=1, candidates=()):
        """Ask the cluster which nodes can take a session pod (`buffon-cluster nodes`): (exit code, the ranking or the error text). It contacts the API server, so a
        cluster that cannot be reached (no VPN, a wrong context) answers with a non-zero exit."""
        k = self.site.kube
        with tempfile.TemporaryDirectory(prefix="buffon-k8s-nodes-") as tmp:
            site = {key: v for key, v in site_json(k, bundle=tmp).items() if key not in ("bundle", "baseImage")}
            site.setdefault("image", "registry.invalid/check@sha256:" + "0" * 64)
            site.pop("node", None)
            path = os.path.join(tmp, "site.json")
            with open(path, "w") as f:
                json.dump(site, f)
            extra = ["-nodes", ",".join(candidates)] if candidates else []
            done = self._tool(["nodes", "-site", path, "-n", str(count), *extra])
        if done.returncode:
            return done.returncode, (done.stderr or done.stdout).strip()
        try:
            return 0, json.loads(done.stdout or "{}")
        except json.JSONDecodeError:
            return 1, f"buffon-cluster nodes printed no ranking: {done.stdout.strip()[:200]}"

    def calibrate(self, dirs, out_path):
        """Judge the noise floor over run directories, one per node (`buffon-cluster calibrate`), with the site's max_cv; write calibration.json to out_path.
        Returns (exit code, the verdict text): 0 pass or not judged, 3 noisy."""
        done = self._tool(["calibrate", "-max-cv", repr(self.site.kube.max_cv), "-o", out_path, *dirs])
        if done.returncode not in (0, EXIT_NOISE):
            raise BackendError(f"buffon-cluster calibrate: {done.stderr.strip() or done.returncode}")
        return done.returncode, (done.stdout + done.stderr).strip()

    def check_calibration(self, path, nodes=()):
        """Whether a calibration vouches for a comparison on nodes (`buffon-cluster check`): (exit code, text); 3 when it does not."""
        done = self._tool(["check", "-calibration", path] + (["-nodes", ",".join(nodes)] if nodes else []))
        if done.returncode not in (0, EXIT_NOISE):
            raise BackendError(f"buffon-cluster check: {done.stderr.strip() or done.returncode}")
        return done.returncode, (done.stdout + done.stderr).strip()

    def _tool(self, args):
        env = {k: v for k, v in self.env.items() if not k.startswith("BUFFON_K8S_")}
        return self.runner([self._bin(), *args], env=env, capture_output=True, text=True)

    def _result(self, run_dir, code, outcomes):
        cluster, node_api = _read(run_dir, "cluster-facts.json"), _read(run_dir, "node.json")
        session_line = cluster.get("session") or {}
        exit_code = session_line.get("exit", code if code else 0)
        if code and not exit_code:
            exit_code = code
        result = load_result(run_dir, exit_code)
        node_cls, node_reasons = node_class(node_api)
        result.facts.update(cluster=cluster, node_api=node_api, outcomes=outcomes, node_class=node_cls, node_class_reasons=node_reasons)
        if not result.pinned_cpus and (cluster.get("pin") or {}).get("cpus"):
            from ..site import parse_cpus
            result.pinned_cpus = parse_cpus(cluster["pin"]["cpus"])
        if not result.throttled_usec:
            result.throttled_usec = int(session_line.get("throttledUsec") or 0)
        return result


def _move(src, dst):
    if os.path.exists(src):
        shutil.move(src, dst)


def _move_contents(src, dst):
    """Move what a pod handed back into a run directory, replacing what is there under the same names."""
    if not os.path.isdir(src):
        return
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        target = os.path.join(dst, name)
        if os.path.isdir(target) and not os.path.islink(target):
            shutil.rmtree(target)
        shutil.move(os.path.join(src, name), target)


def node_class(node_api):
    """("A" | "B", reasons) for the node a pod ran on (Run Rules 4): a Guaranteed pod with integer CPUs gets exclusive CPUs only under the static CPU manager policy, and whole physical
    cores only with its `full-pcpus-only` option; otherwise a sibling thread of a pod CPU may run someone else's work."""
    reasons = []
    policy = (node_api or {}).get("cpuManagerPolicy")
    if policy != "static":
        reasons.append(f"the node's CPU manager policy is {policy or 'unknown'}, not static: the pod's CPUs are not exclusive")
    options = (node_api or {}).get("cpuManagerPolicyOptions") or {}
    if str(options.get("full-pcpus-only", "")).lower() != "true":
        reasons.append("the node's CPU manager lacks the full-pcpus-only option: the pod can share a physical core with another pod")
    return ("A" if not reasons else "B"), reasons


def _read(run_dir, name):
    path = os.path.join(run_dir, name)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)
