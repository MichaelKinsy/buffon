# SPDX-License-Identifier: Apache-2.0
"""Site profiles: everything that is specific to one machine or cluster.

A profile is a TOML file (`sites/<name>.toml`, or any path given with --site or BUFFON_SITE). Code, arm manifests, workloads and tests never name a
host, user, home directory, core number, registry or cluster; they read it from the profile, from flags, or from BUFFON_* environment variables.
The profile is validated when the runner starts. An unknown key, a value of the wrong type and a value that still holds a `<placeholder>` are
errors, so a typing mistake never silently becomes a default.

The schema is the SCHEMA table below; `python3 -m buffon site schema` prints it as Markdown (sites/SCHEMA.md is that output).
"""
import json
import os
import re
import tomllib
from dataclasses import dataclass, field

BACKENDS = ("local", "kubernetes")
PIN_POLICIES = ("required", "preferred", "none")
HARDWARE_CLAIMS = ("dedicated", "shared")
ARCHES = ("amd64", "arm64")   # Kubernetes node architectures a bundle is built for (buffon/backend/bundle.py)

# (section, key, type, default, description). type is one of: str, int, bool, cpus, list-str, list-table, table, quantity, image.
SCHEMA = [
    ("site", "name", "str", "(file name)", "Name printed in every report."),
    ("site", "backend", "str", "local", "Execution backend: `local` or `kubernetes`."),
    ("site", "hardware", "str", "shared", "What you claim about the machine: `dedicated` (nothing else runs on these cores) or `shared`. A claim never upgrades a run on its own: the runner also detects quietness (governor, load, contention on the pinned cores), and a run is labelled quiet dedicated hardware only when claim and detection agree."),
    ("site", "notes", "str", "", "Free text copied into the report."),
    ("local", "cpus", "cpus", "(none)", "CPUs the harness processes are pinned to, as a list such as `8-11` or `2,4,6`. Required when `pinning = \"required\"`."),
    ("local", "mock_cpus", "cpus", "(none)", "CPUs the runner and the mock endpoint are pinned to. Must not overlap `cpus`. When empty the runner is not pinned."),
    ("local", "pinning", "str", "preferred", "`required`: refuse to run when the harness cannot be pinned; `preferred`: pin when `cpus` is set, otherwise run unpinned and label the run PROVISIONAL; `none`: never pin (labelled PROVISIONAL)."),
    ("local", "cache_dir", "str", "$XDG_CACHE_HOME/buffon", "Where verified artifact downloads are kept. The runner re-verifies each file's sha256 before use."),
    ("local", "work_dir", "str", "$TMPDIR", "Parent of the throwaway directory each run installs arms into."),
    ("local", "lock_files", "list-str", "(none)", "Lock files other benchmark tools on this host hold (for example a host bench slot). The run refuses to start while one is held by someone else; a run inside the holder's wrapper is let through. Buffon also takes its own exclusive lock, so one Buffon measurement runs per host (with `slots`, each slot has its own lock and the host-wide one is held shared)."),
    ("local", "slots", "int", "1", "Opt-in: run this many measured sessions at once on disjoint core sets of this host (`buffon campaign` only; docs/METHODOLOGY.md, \"Slots on one big host\"). `1` is one session at a time, as before. With 2 or more, `cpus` and `mock_cpus` give the size of one slot (how many harness CPUs and mock CPUs a session gets, not which ones); the runner splits the CPUs it may use into that many slots of whole physical cores, one NUMA node each where the host allows, and refuses a split that would share a core. Needs a local site with `cpus` and `mock_cpus`, on Linux."),
    ("local", "quiet_max_busy", "float", "0.10", "Before every sample the pinned CPUs must be at most this busy (a fraction); otherwise the runner waits and records the wait."),
    ("local", "quiet_timeout_s", "float", "300", "How long the runner waits for a quiet host before a sample; after that the sample fails with the readings recorded."),
    ("local", "quiet_max_runnable", "nonneg-int", "0", "The most other runnable threads allowed on the pinned CPUs before a sample (0: none). Only the pinned CPUs count; the load of the rest of the host is recorded but never gated on."),
    ("local", "quiet_max_steal", "float", "0.02", "Before every sample no pinned CPU may lose more than this share of its time to the hypervisor (steal)."),
    ("local", "quiet_max_psi", "float", "10", "Before every sample the CPU pressure (some, avg10, percent) of the runner's cgroup, or of the system when the cgroup has no pressure file, must be at most this. A cgroup that was CPU-throttled during the check also fails it."),
    ("local", "host_claim", "str", "B", "`A`: the site declares this host dedicated (nothing else is scheduled on the benchmark's CPUs); preflight checks the claim and downgrades the run to class B when it does not hold. `B`: shared host, results PROVISIONAL."),
    ("local", "require_class", "str", "(none)", "`A` or `B`: refuse to run on a host of a lower class (A = dedicated and publishable)."),
    ("local", "clock_claim", "str", "(none)", "`hypervisor`: this machine is a virtual machine whose platform fixes the CPU clock and turbo state and shows no cpufreq or turbo interface, so the runner cannot read them. The site says so; the runner does not verify the clock, and it honours the claim only on a machine that shows it is a virtual machine (the CPU's hypervisor flag, or systemd-detect-virt naming one); elsewhere the run records `clock_claim_refused`. With it, an unreadable clock and turbo state no longer keep a run out of class A, the report states the claim, and a governor that is readable and scales the clock still does."),
    ("local", "meter", "str", "auto", "Resource meter: `auto`, `cgroup-direct`, `cgroup-systemd` or `rusage`."),
    ("local", "allow_frequency_scaling", "bool", "false", "Run although a pinned CPU's governor scales its clock. The run is then labelled PROVISIONAL."),
    ("kubernetes", "kubeconfig", "str", "", "Path of the kubeconfig. Empty uses $KUBECONFIG or kubectl's default."),
    ("kubernetes", "context", "str", "", "kubectl context. Empty uses the current context."),
    ("kubernetes", "namespace", "str", "(required)", "Namespace in which the runner creates Jobs and reads pods and logs."),
    ("kubernetes", "image", "image", "(required unless bundle)", "Benchmark image, pinned by digest: `<registry>/<repository>@sha256:<64 hex>`. A tag is refused."),
    ("kubernetes", "bundle", "bool", "false", "Run the pinned `base_image` and copy the repository and the verified artifact cache into it with `kubectl cp` (see docs/RUNNING.md), instead of pulling `image`."),
    ("kubernetes", "base_image", "image", "", "Digest-pinned image a bundle runs on. It needs Python 3.11 or later and the prerequisites listed in docs/RUNNING.md."),
    ("kubernetes", "arch", "str", "amd64", "Architecture of the nodes, `amd64` or `arm64`. `buffon run` builds the bundle for it; a bundle pod on a node of another architecture refuses to start."),
    ("kubernetes", "cpus", "int", "2", "Whole CPUs for the pod. Requests equal limits, so the pod has Guaranteed QoS and a static CPU manager gives it exclusive cores."),
    ("kubernetes", "memory", "quantity", "8Gi", "Memory request and limit."),
    ("kubernetes", "scratch_size", "quantity", "8Gi", "Size limit of the scratch volume the session writes to."),
    ("kubernetes", "node_selector", "table", "{}", "Labels of the dedicated node pool."),
    ("kubernetes", "tolerations", "list-table", "[]", "Tolerations for the pool's taints."),
    ("kubernetes", "node", "str", "", "Pin the pod to one node by name."),
    ("kubernetes", "nodes", "list-str", "[]", "Run the same session on each of these nodes at once (one pod each), or, with `spread`, the nodes it picks from. Excludes `node`."),
    ("kubernetes", "spread", "nonneg-int", "0", "Run the same session at once on this many nodes, the ones with the most free CPU (of `nodes` when given). 0: one node. Excludes `node`."),
    ("kubernetes", "image_pull_secrets", "list-str", "[]", "Names of image pull secrets."),
    ("kubernetes", "service_account", "str", "", "Service account of the pod."),
    ("kubernetes", "deadline_seconds", "int", "21600", "Job deadline."),
    ("kubernetes", "ttl_seconds", "int", "604800", "How long the cluster keeps a finished Job."),
    ("kubernetes", "pin", "str", "auto", "CPUs inside the pod the processes are pinned to: `auto` (the quietest of the allowed cores), `none`, or a list."),
    ("kubernetes", "allow_frequency_scaling", "bool", "false", "Run on a node whose measured cores scale their clock. The run is reported but labelled PROVISIONAL."),
    ("kubernetes", "secret_env", "list-table", "[]", "Environment variables the pod reads from Kubernetes Secrets in `namespace`, each `{ name = \"<VARIABLE>\", secret = \"<secret name>\", key = \"<key in the secret>\" }`. Only the reference reaches the pod spec: a secret value never passes through the profile, the session or the runner, and an entry with any other key is refused."),
    ("kubernetes", "max_cv", "float", "0.05", "Cross-node calibration gate: the largest coefficient of variation a gated metric may have (between 0 and 1). A calibration over the nodes refuses a comparison above it."),
]

_PLACEHOLDER = re.compile(r"<[^<>\s][^<>]*>")
_DIGEST = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DNS_SUBDOMAIN = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")
_SECRET_KEY = re.compile(r"^[-._a-zA-Z0-9]+$")
SECRET_ENV_KEYS = ("name", "secret", "key")
_QUANTITY = re.compile(r"^[0-9]+(\.[0-9]+)?(m|k|M|G|T|P|E|Ki|Mi|Gi|Ti|Pi|Ei)?$")


class SiteError(ValueError):
    pass


def parse_cpus(text):
    """`8-11,14` -> [8, 9, 10, 11, 14] (sorted, unique). Raises SiteError on anything else."""
    if isinstance(text, (list, tuple)):
        text = ",".join(str(t) for t in text)
    out = set()
    for part in str(text).replace(" ", "").split(","):
        if not part:
            continue
        lo, dash, hi = part.partition("-")
        if not lo.isdigit() or (dash and not hi.isdigit()):
            raise SiteError(f"{text!r} is not a CPU list (use forms such as 8-11,14)")
        a, b = int(lo), int(hi) if dash else int(lo)
        if b < a:
            raise SiteError(f"{text!r}: range {part} runs backwards")
        out.update(range(a, b + 1))
    return sorted(out)


def format_cpus(cpus):
    """[8, 9, 10, 14] -> `8-10,14`."""
    cpus = sorted(cpus)
    parts, i = [], 0
    while i < len(cpus):
        j = i
        while j + 1 < len(cpus) and cpus[j + 1] == cpus[j] + 1:
            j += 1
        parts.append(str(cpus[i]) if i == j else f"{cpus[i]}-{cpus[j]}")
        i = j + 1
    return ",".join(parts)


@dataclass
class LocalSite:
    cpus: list = field(default_factory=list)
    mock_cpus: list = field(default_factory=list)
    pinning: str = "preferred"
    cache_dir: str = ""
    work_dir: str = ""
    meter: str = "auto"
    allow_frequency_scaling: bool = False
    lock_files: list = field(default_factory=list)
    quiet_max_busy: float = 0.10
    quiet_timeout_s: float = 300.0
    quiet_max_runnable: int = 0
    host_claim: str = "B"
    require_class: str = ""
    clock_claim: str = ""
    quiet_max_steal: float = 0.02
    quiet_max_psi: float = 10.0
    slots: int = 1
    slot: dict = None   # set by buffon.runner.slots.select when a session runs in one slot: {"id", "of", "cpus", "mock_cpus", "others", "calibration"}; never read from a profile


@dataclass
class KubeSite:
    kubeconfig: str = ""
    context: str = ""
    namespace: str = ""
    image: str = ""
    bundle: bool = False
    base_image: str = ""
    arch: str = "amd64"
    cpus: int = 2
    memory: str = "8Gi"
    scratch_size: str = "8Gi"
    node_selector: dict = field(default_factory=dict)
    tolerations: list = field(default_factory=list)
    node: str = ""
    nodes: list = field(default_factory=list)
    spread: int = 0
    image_pull_secrets: list = field(default_factory=list)
    service_account: str = ""
    deadline_seconds: int = 21600
    ttl_seconds: int = 604800
    pin: str = "auto"
    allow_frequency_scaling: bool = False
    secret_env: list = field(default_factory=list)
    max_cv: float = 0.05


@dataclass
class Site:
    name: str
    backend: str = "local"
    hardware: str = "shared"
    notes: str = ""
    local: LocalSite = field(default_factory=LocalSite)
    kube: KubeSite = field(default_factory=KubeSite)
    path: str = ""

    def describe(self):
        """The site as recorded in run.json: no secrets, nothing the profile did not say."""
        out = {"name": self.name, "backend": self.backend, "hardware_claim": self.hardware, "notes": self.notes, "profile": os.path.basename(self.path) or None}
        if self.backend == "local":
            out["local"] = {"cpus": format_cpus(self.local.cpus), "mock_cpus": format_cpus(self.local.mock_cpus), "pinning": self.local.pinning, "meter": self.local.meter,
                            "allow_frequency_scaling": self.local.allow_frequency_scaling}
            if self.local.slots > 1:
                out["local"]["slots"] = self.local.slots
            if self.local.slot:
                out["local"]["slot"] = {k: self.local.slot[k] for k in ("id", "of")}
        else:
            k = self.kube
            out["kubernetes"] = {"namespace": k.namespace, "image": k.image, "bundle": k.bundle, "base_image": k.base_image, "arch": k.arch, "cpus": k.cpus, "memory": k.memory,
                                 "node_selector": k.node_selector, "node": k.node, "nodes": k.nodes, "spread": k.spread, "pin": k.pin, "allow_frequency_scaling": k.allow_frequency_scaling,
                                 "secret_env": [e["name"] for e in k.secret_env], "max_cv": k.max_cv}
        return out


def _strings(value):
    """Every string in a value, inside lists and tables too (keys included), so a placeholder in a table is found."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _check_type(section, key, kind, value):
    where = f"[{section}] {key}"
    for text in _strings(value):
        if _PLACEHOLDER.search(text):
            raise SiteError(f"{where} still holds a placeholder ({text}); replace it")
    if kind in ("str", "image", "quantity"):
        if not isinstance(value, str):
            raise SiteError(f"{where} must be a string")
        if kind == "image" and value and not _DIGEST.match(value):
            raise SiteError(f"{where} = {value!r} is not pinned by digest (<registry>/<repository>@sha256:<64 hex>); a tag can move between runs")
        if kind == "quantity" and not _QUANTITY.match(value):
            raise SiteError(f"{where} = {value!r} is not a Kubernetes quantity (for example 8Gi)")
    elif kind == "int":
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise SiteError(f"{where} must be a positive integer")
    elif kind == "nonneg-int":
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SiteError(f"{where} must be a non-negative integer")
    elif kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise SiteError(f"{where} must be a non-negative number")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise SiteError(f"{where} must be true or false")
    elif kind == "cpus":
        if not isinstance(value, (str, list)):
            raise SiteError(f"{where} must be a CPU list string such as \"8-11\"")
    elif kind == "list-str":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise SiteError(f"{where} must be a list of strings")
    elif kind == "list-table":
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            raise SiteError(f"{where} must be a list of tables")
    elif kind == "table":
        if not isinstance(value, dict):
            raise SiteError(f"{where} must be a table")


def _validated(data):
    known = {}
    for section, key, kind, *_ in SCHEMA:
        known.setdefault(section, {})[key] = kind
    for section, body in data.items():
        if section not in known:
            raise SiteError(f"unknown section [{section}]; known: {', '.join(known)}")
        if not isinstance(body, dict):
            raise SiteError(f"[{section}] must be a table")
        for key, value in body.items():
            if key not in known[section]:
                raise SiteError(f"[{section}] has unknown key {key!r}; known: {', '.join(known[section])}")
            _check_type(section, key, known[section][key], value)
    return data


def _expand(path, env):
    return os.path.expanduser(os.path.expandvars(path.replace("$XDG_CACHE_HOME", env.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")).replace("$TMPDIR", env.get("TMPDIR") or "/tmp")))


def _env_value(key, kind, text):
    """An BUFFON_K8S_* override parsed for its schema type: a number as a number, a list or table as JSON. The result is checked like a profile value."""
    try:
        if kind == "bool":
            value = text.lower() in ("1", "true", "yes")
        elif kind in ("int", "nonneg-int"):
            value = int(text)
        elif kind == "float":
            value = float(text)
        elif kind in ("list-str", "list-table", "table"):
            value = json.loads(text)
        else:
            value = text
        _check_type("kubernetes", key, kind, value)
    except (ValueError, SiteError) as error:
        raise SiteError(f"BUFFON_K8S_{key.upper()}={text!r}: {error}") from error
    return value


def _check_secret_env(entry):
    """One secret_env entry: exactly name, secret and key. A value, or any other key, is refused: a profile names a secret, it never holds one."""
    extra = sorted(set(entry) - set(SECRET_ENV_KEYS))
    if extra:
        raise SiteError(f"[kubernetes] secret_env entry {entry.get('name', '?')!r} has {', '.join(extra)}; an entry names a Kubernetes Secret with exactly name, secret and key, and a secret value never goes in a profile")
    missing = [k for k in SECRET_ENV_KEYS if not isinstance(entry.get(k), str) or not entry.get(k)]
    if missing:
        raise SiteError(f"[kubernetes] secret_env entry {entry.get('name', '?')!r} needs {', '.join(missing)} (strings)")
    if not _ENV_NAME.match(entry["name"]):
        raise SiteError(f"[kubernetes] secret_env name {entry['name']!r} is not an environment variable name")
    if not _DNS_SUBDOMAIN.match(entry["secret"]):
        raise SiteError(f"[kubernetes] secret_env {entry['name']}: secret {entry['secret']!r} is not a Kubernetes Secret name")
    if not _SECRET_KEY.match(entry["key"]):
        raise SiteError(f"[kubernetes] secret_env {entry['name']}: key {entry['key']!r} is not a key of a Secret")


def from_dict(data, name="site", path="", env=None):
    """Build a Site from parsed TOML (or an equivalent dict), apply BUFFON_* overrides and validate the result."""
    env = os.environ if env is None else env
    data = _validated({k: dict(v) if isinstance(v, dict) else v for k, v in data.items()})
    s = data.get("site", {})
    site = Site(name=s.get("name", name), backend=s.get("backend", "local"), hardware=s.get("hardware", "shared"), notes=s.get("notes", ""), path=path)
    if site.backend not in BACKENDS:
        raise SiteError(f"[site] backend = {site.backend!r}; use one of {', '.join(BACKENDS)}")
    if site.hardware not in HARDWARE_CLAIMS:
        raise SiteError(f"[site] hardware = {site.hardware!r}; use one of {', '.join(HARDWARE_CLAIMS)}")
    l = data.get("local", {})
    site.local = LocalSite(cpus=parse_cpus(env.get("BUFFON_CPUS", l.get("cpus", ""))), mock_cpus=parse_cpus(env.get("BUFFON_MOCK_CPUS", l.get("mock_cpus", ""))),
                           pinning=l.get("pinning", "preferred"), cache_dir=_expand(env.get("BUFFON_CACHE_DIR", l.get("cache_dir", "$XDG_CACHE_HOME/buffon")), env),
                           work_dir=_expand(env.get("BUFFON_WORK_DIR", l.get("work_dir", "$TMPDIR")), env), meter=l.get("meter", "auto"),
                           allow_frequency_scaling=l.get("allow_frequency_scaling", False), lock_files=[_expand(x, env) for x in l.get("lock_files", [])],
                           quiet_max_busy=float(l.get("quiet_max_busy", 0.10)), quiet_timeout_s=float(l.get("quiet_timeout_s", 300)), quiet_max_runnable=int(l.get("quiet_max_runnable", 0)), host_claim=l.get("host_claim", "B"), require_class=l.get("require_class", ""), clock_claim=l.get("clock_claim", ""),
                           quiet_max_steal=float(l.get("quiet_max_steal", 0.02)), quiet_max_psi=float(l.get("quiet_max_psi", 10)), slots=l.get("slots", 1))
    for key in ("host_claim", "require_class"):
        if getattr(site.local, key) not in (("A", "B") if key == "host_claim" else ("", "A", "B")):
            raise SiteError(f"[local] {key} must be A or B")
    if site.local.clock_claim not in ("", "hypervisor"):
        raise SiteError("[local] clock_claim must be hypervisor (or left out)")
    if not 0 <= site.local.quiet_max_busy <= 1:
        raise SiteError("[local] quiet_max_busy is a fraction between 0 and 1")
    if site.local.pinning not in PIN_POLICIES:
        raise SiteError(f"[local] pinning = {site.local.pinning!r}; use one of {', '.join(PIN_POLICIES)}")
    if site.local.meter not in ("auto", "cgroup-direct", "cgroup-systemd", "rusage"):
        raise SiteError(f"[local] meter = {site.local.meter!r} is not a known meter")
    if site.local.pinning == "required" and not site.local.cpus:
        raise SiteError("[local] pinning = \"required\" needs `cpus` (or BUFFON_CPUS)")
    if site.local.pinning == "none" and site.local.cpus:
        raise SiteError("[local] pinning = \"none\" contradicts `cpus`")
    if set(site.local.cpus) & set(site.local.mock_cpus):
        raise SiteError(f"[local] cpus and mock_cpus overlap on {format_cpus(set(site.local.cpus) & set(site.local.mock_cpus))}: the mock would share cores with the harness")
    if site.local.slots > 1:
        if site.backend != "local":
            raise SiteError("[local] slots applies to a local site; a Kubernetes site runs one session per node")
        if not site.local.cpus or not site.local.mock_cpus:
            raise SiteError("[local] slots needs `cpus` and `mock_cpus`: their counts are the size of one slot")
        if site.local.pinning != "required":
            raise SiteError("[local] slots needs pinning = \"required\": a slot is its own cores")
    k = data.get("kubernetes", {})
    kinds = {key: kind for section, key, kind, *_ in SCHEMA if section == "kubernetes"}
    values = {}
    for key in KubeSite.__dataclass_fields__:
        default = getattr(KubeSite(), key)
        value = k.get(key, default)
        override = env.get("BUFFON_K8S_" + key.upper())
        if override is not None:
            value = _env_value(key, kinds[key], override)
        values[key] = value
    site.kube = KubeSite(**values)
    if site.backend == "kubernetes":
        kube = site.kube
        for required in ("namespace",):
            if not getattr(kube, required):
                raise SiteError(f"[kubernetes] {required} is required")
        if kube.bundle:
            if not kube.base_image:
                raise SiteError("[kubernetes] bundle = true needs base_image, pinned by digest")
        elif not kube.image:
            raise SiteError("[kubernetes] needs image (pinned by digest), or bundle = true with base_image")
        for entry in kube.secret_env:
            _check_secret_env(entry)
        names = [e["name"] for e in kube.secret_env]
        if len(set(names)) != len(names):
            raise SiteError(f"[kubernetes] secret_env names {', '.join(sorted({n for n in names if names.count(n) > 1}))} more than once")
        if not 0 < kube.max_cv < 1:
            raise SiteError(f"[kubernetes] max_cv = {kube.max_cv!r}: a coefficient of variation between 0 and 1, such as 0.05")
        if kube.node and (kube.nodes or kube.spread):
            raise SiteError("[kubernetes] node pins one node; nodes and spread choose several. Set one of them")
        bad = [n for n in kube.nodes if not _DNS_SUBDOMAIN.match(n)]
        if bad:
            raise SiteError(f"[kubernetes] nodes: {', '.join(bad)} is not a node name")
        if len(set(kube.nodes)) != len(kube.nodes):
            raise SiteError("[kubernetes] nodes names a node more than once")
        if kube.spread and kube.nodes and kube.spread > len(kube.nodes):
            raise SiteError(f"[kubernetes] spread = {kube.spread} is more than the {len(kube.nodes)} nodes it picks from")
        if kube.arch not in ARCHES:
            raise SiteError(f"[kubernetes] arch = {kube.arch!r}; use one of {', '.join(ARCHES)}")
        if kube.pin not in ("auto", "none"):
            parse_cpus(kube.pin)
    return site


def load(ref=None, env=None, base_dir=None):
    """Load a profile: `ref` is a path, a bare name resolved to sites/<name>.toml next to the repository, or None to use BUFFON_SITE, then the built-in unpinned local site."""
    env = os.environ if env is None else env
    ref = ref or env.get("BUFFON_SITE")
    if not ref:
        return from_dict({}, name="local-default", env=env)
    path = ref
    if not os.path.exists(path):
        candidate = os.path.join(base_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sites"), ref + ("" if ref.endswith(".toml") else ".toml"))
        if not os.path.exists(candidate):
            raise SiteError(f"site profile {ref!r} not found (looked for it as a path and as {candidate}); make one with: cp sites/example-local.toml sites/{os.path.basename(ref).removesuffix('.toml')}.toml")
        path = candidate
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as error:
            raise SiteError(f"{path}: {error}") from error
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        return from_dict(data, name=name, path=os.path.abspath(path), env=env)
    except SiteError as error:
        raise SiteError(f"{path}: {error}") from error


def schema_markdown():
    """The schema as the Markdown of sites/SCHEMA.md."""
    lines = ["# Site profile schema", "", "Generated by `python3 -m buffon site schema`; do not edit. A profile is a TOML file; every key is optional unless the table says otherwise.", ""]
    section = None
    for sec, key, kind, default, desc in SCHEMA:
        if sec != section:
            section = sec
            lines += [f"## `[{sec}]`", "", "| key | type | default | meaning |", "|---|---|---|---|"]
        lines.append(f"| `{key}` | {kind} | {default} | {desc} |")
        # keep tables contiguous per section
    out, prev = [], None
    for line in lines:
        if line.startswith("## ") and prev is not None and prev != "":
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out) + "\n\nEnvironment overrides: `BUFFON_SITE`, `BUFFON_CPUS`, `BUFFON_MOCK_CPUS`, `BUFFON_CACHE_DIR`, `BUFFON_WORK_DIR`, and `BUFFON_K8S_<KEY>` for every `[kubernetes]` key (for example `BUFFON_K8S_NAMESPACE`, `BUFFON_K8S_IMAGE`). A list or table override is JSON, for example `BUFFON_K8S_NODE_SELECTOR='{\"pool\": \"bench\"}'`; an override is checked like a profile value.\n"
