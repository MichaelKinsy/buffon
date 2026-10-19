# SPDX-License-Identifier: Apache-2.0
"""Arm manifests (arms/<name>/arm.toml): load, validate and canonicalise.

The format is documented in CONTRIBUTING.md. Validation is strict: an unknown key, a missing required key, an artifact without a sha256 and a
non-held arm without an install form are errors. `operator_terms` marks an arm whose vendor terms the operator must accept (buffon/up/selection.py); `[npm] bin_native` names, per platform, the
executable inside the platform's optional-dependency package when the package's own `bin` is only a stub (npm runs here with --ignore-scripts). Nothing here depends on the machine the runner is on.
"""
import hashlib
import os
import re
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARMS_DIR = os.environ.get("BUFFON_ARMS_DIR") or os.path.join(ROOT, "arms")   # the arm manifests; the variable lets a test (or a fork) point Buffon at another directory
RUNTIMES_FILE = os.path.join(ROOT, "runtimes.toml")

PLATFORMS = ("linux-x64", "linux-arm64", "darwin-x64", "darwin-arm64")
RELATIONS = ("pi-reference", "pi-fork", "pi-port", "pi-compatible", "reference")
APIS = ("openai-completions", "openai-responses", "anthropic-messages")
CLAIMS = ("pi-extensions", "pi-sessions", "pi-rpc")   # what a manifest's `claims` may list (workloads/grade.toml [claims] holds the same list; a test keeps them equal)
EXTENSIONS = ("native", "sidecar", "partial", "none")
MODES = ("version", "print", "print_write", "print_session", "rpc", "rpc_session", "rpc_resume", "pty")
TOP_KEYS = {"claims", "caveat", "previous", "name", "label", "homepage", "relation", "licence", "licence_url", "restrictions", "version", "held", "operator_terms", "artifact", "npm", "source", "runtime", "endpoint",
            "env", "state", "modes", "capabilities", "renderer", "rpc", "cannot_run", "version_check", "notes", "trust", "derive", "extensions", "prepare", "seed", "piglet", "divergence"}
# A derived arm names a base arm (`[derive] base`): it runs from a copy of the base's install tree and inherits the base's scalar fields and these tables, key by key.
INHERITED_SCALARS = ("homepage", "relation", "licence", "licence_url", "restrictions", "version")
INHERITED_TABLES = ("endpoint", "env", "state", "modes", "capabilities", "renderer", "rpc", "cannot_run", "version_check", "runtime")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class ManifestError(ValueError):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


ACCEPT_ENV = "BUFFON_ACCEPT_TERMS"


def accepted_terms(flag=None, environ=None):
    """The set of arm ids whose operator terms the operator accepted: the comma list given with --accept-terms plus BUFFON_ACCEPT_TERMS."""
    environ = os.environ if environ is None else environ
    items = []
    for text in (flag, environ.get(ACCEPT_ENV)):
        items += [t for t in re.split(r"[,\s]+", text or "") if t]
    return set(items)


def terms_refusal(arm):
    """The message for an arm that has operator terms the operator has not accepted: it quotes them and names the flag."""
    return (f"harness {arm.id!r} is installed from its vendor at run time and runs only under the vendor's terms, which you must accept yourself: {arm.operator_terms} "
            f"If you accept them, add `--accept-terms {arm.id}` (or set {ACCEPT_ENV}={arm.id}).")


def slot_name(arm_id):
    """The name of every on-disk path that carries an arm's id: `<id>-a` for an arm, `<id>` (already `<arm>-b`) for its A/A copy. Both have the same length, so the harness sees
    paths, argv and env of one size whichever copy it is."""
    return arm_id if arm_id.endswith("-b") else arm_id + "-a"


class Arm:
    """One validated manifest plus its location. `spec` is the parsed TOML."""

    def __init__(self, name, spec, directory, manifest_sha256):
        self.id, self.spec, self.dir, self.manifest_sha256 = name, spec, directory, manifest_sha256
        self.name = name
        self.label = spec["label"]
        self.version = spec["version"]
        self.held = spec.get("held") or None
        self.operator_terms = spec.get("operator_terms") or None   # vendor terms the operator must accept before the arm runs (it is installed from the vendor at run time, never redistributed)
        self.licence = spec["licence"]
        self.family = spec.get("relation")
        self.caveat = spec.get("caveat")       # a sentence every report row and section for this arm repeats (what its numbers are, when that is not obvious)
        self.previous = spec.get("previous")   # the arm this one replaces: the report shows the change between them (any arm may declare it)
        self.capabilities = spec.get("capabilities", {})
        self.modes = spec.get("modes", {})
        self.apis = spec.get("endpoint", {}).get("apis", [])
        self.env = dict(spec.get("env", {}))
        self.divergences = [dict(d) for d in spec.get("divergence", [])]   # work this arm does differently by its own account: the report does not compare it there (divergence.py)
        self.renderer = spec.get("renderer", {})
        self.rpc_dialect = spec.get("rpc", {})
        self.cannot_run = spec.get("cannot_run", {})
        self.install_kind = "artifact" if "artifact" in spec else "npm" if "npm" in spec else "source" if "source" in spec else "derive" if "derive" in spec else None
        self.base = spec.get("derive", {}).get("base")
        self.extension_spec = spec.get("extensions", {})
        self.writer_dir = directory
        self.vars = {}   # install-time paths an `[env]` value may name as {name}: filled by the installer (a derived arm gets source_dir, the checkout of its base)
        # Filled by the installer.
        self.binary = None
        self.path_dirs = []
        self.skip = None
        self.install_dir = None
        self.record = {}
        self.version_line = None
        self.twin_of = None
        self.seed_dir = None

    @property
    def slot(self):
        return slot_name(self.id)

    @property
    def claims(self):
        """The Pi capabilities the arm claims, for the grade's N/A classes: the manifest's `claims` list, else derived from what the manifest declares (Pi extensions loaded,
        Pi session files read, an RPC mode that can run). A harness that claims a capability Buffon could not drive is not-yet-measurable, never out of scope."""
        if "claims" in self.spec:
            return list(self.spec["claims"])
        out = []
        if self.pi_extensions in ("native", "sidecar", "partial"):
            out.append("pi-extensions")
        if self.pi_session_format:
            out.append("pi-sessions")
        if "rpc" in self.modes and "rpc" not in self.cannot_run:
            out.append("pi-rpc")
        return out

    @property
    def pi_session_format(self):
        return bool(self.capabilities.get("pi_session_format"))

    @property
    def pi_extensions(self):
        return self.capabilities.get("pi_extensions", "none")

    def supports_mode(self, mode):
        return mode in self.modes

    def supports_api(self, api):
        return api in self.apis

    @property
    def runs_by_default(self):
        """False for an extension-matrix arm (`[extensions] default = false`): it runs only when a run names it, because it repeats the base arm with another extension realization.
        Always False for an arm with `operator_terms`: it runs only when named and its terms are accepted."""
        return self.extension_spec.get("default", True) and not self.operator_terms

    def writer_path(self):
        w = self.spec.get("endpoint", {}).get("writer")
        if not w:
            return None
        own = os.path.join(self.dir, w)
        return own if os.path.exists(own) or not self.writer_dir else os.path.join(self.writer_dir, w)

    def loads_template(self):
        """True for an arm that takes the generated bench extensions (buffon/fixtures/benchext.py): no `[extensions] paths` of its own and not built into its executable."""
        return not self.extension_spec.get("embedded") and "paths" not in self.extension_spec

    def extension_paths(self, repo_root=None):
        """The extension sources this arm's own realization lists with `-e`, in order: the manifest's globs (relative to the repository root). An arm that takes the generated bench
        extensions (`loads_template`) lists none here, and one whose extensions are built into its executable (`embedded = true`) loads none."""
        import glob
        if not self.extension_spec.get("paths") or self.extension_spec.get("embedded"):
            return []
        root = repo_root or ROOT
        out = []
        for pattern in self.extension_spec["paths"]:
            out += sorted(glob.glob(os.path.join(root, pattern)))
        return out

    def aux_files(self):
        """Files next to the manifest that the manifest pins by sha256 (npm install pairs)."""
        out = []
        npm = self.spec.get("npm", {})
        for key in ("package_json", "package_lock"):
            if npm.get(key):
                out.append((npm[key], npm.get(key + "_sha256")))
        return out


def _need(table, keys, where):
    for k in keys:
        if k not in table:
            raise ManifestError(f"{where}: missing `{k}`")


def validate(name, spec, directory):
    where = f"arms/{name}/arm.toml"
    unknown = set(spec) - TOP_KEYS
    if unknown:
        raise ManifestError(f"{where}: unknown key(s) {', '.join(sorted(unknown))}")
    _need(spec, ("name", "label", "homepage", "relation", "licence", "licence_url", "version"), where)
    if "previous" in spec and (not isinstance(spec["previous"], str) or not spec["previous"] or spec["previous"] == spec["name"]):
        raise ManifestError(f"{where}: previous must name another arm")
    if spec["name"] != name:
        raise ManifestError(f"{where}: name = {spec['name']!r} must equal the directory name {name!r}")
    if name.endswith("-b"):   # review: the report, rerun and grade find an arm's A/A copy as <arm>-b; an arm named like a copy would be counted as one
        raise ManifestError(f"{where}: an arm name may not end in -b (the suffix of an arm's A/A copy)")
    if spec["relation"] not in RELATIONS:
        raise ManifestError(f"{where}: relation = {spec['relation']!r}; use one of {', '.join(RELATIONS)}")
    claims = spec.get("claims")
    if claims is not None and not (isinstance(claims, list) and all(c in CLAIMS for c in claims) and len(set(claims)) == len(claims)):
        raise ManifestError(f"{where}: claims is a list without repeats of {', '.join(CLAIMS)}")
    held = spec.get("held")
    if held is not None and (not isinstance(held, str) or not held.strip()):
        raise ManifestError(f"{where}: `held` is the reason the arm is held, a non-empty string")
    terms = spec.get("operator_terms")
    if terms is not None and (not isinstance(terms, str) or not terms.strip()):
        raise ManifestError(f"{where}: `operator_terms` is the vendor terms the operator must accept (which terms, why, and their URL), a non-empty string")
    if terms is not None and held is not None:
        raise ManifestError(f"{where}: an arm is either `held` (never runs) or has `operator_terms` (runs once accepted), not both")
    forms = [k for k in ("artifact", "npm", "source", "derive") if k in spec]
    if held is None and len(forms) != 1:
        raise ManifestError(f"{where}: a runnable arm declares exactly one of [artifact.*], [npm], [source], [derive] (found {forms or 'none'})")
    if len(forms) > 1:
        raise ManifestError(f"{where}: declare only one install form (found {forms})")
    for plat, a in spec.get("artifact", {}).items():
        if plat not in PLATFORMS:
            raise ManifestError(f"{where}: artifact platform {plat!r}; use one of {', '.join(PLATFORMS)}")
        _need(a, ("url", "sha256", "exe"), f"{where} [artifact.{plat}]")
        if not SHA256.match(a["sha256"]):
            raise ManifestError(f"{where} [artifact.{plat}]: sha256 is not 64 hex digits")
        out_of_tree = os.environ.get("BUFFON_ARMS_DIR") and os.path.realpath(os.environ["BUFFON_ARMS_DIR"]) != os.path.realpath(os.path.join(ROOT, "arms"))
        if not (a["url"].startswith("https://") or (out_of_tree and a["url"].startswith("file://"))):   # a file:// artifact only in an arms directory outside this repository (a test's stubs, a fork's local build)
            raise ManifestError(f"{where} [artifact.{plat}]: url must be https")
    if "seed" in spec:
        sd = spec["seed"]
        if not (isinstance(sd.get("command"), list) and sd["command"] and all(isinstance(x, str) for x in sd["command"])):
            raise ManifestError(f"{where} [seed] command must be a non-empty list of strings")
        unknown_seed = set(sd) - {"command", "timeout", "exclude", "notes"}
        if unknown_seed:
            raise ManifestError(f"{where} [seed] unknown key(s): {', '.join(sorted(unknown_seed))}")
    if "npm" in spec:
        n = spec["npm"]
        _need(n, ("package", "version", "integrity", "package_lock", "package_lock_sha256", "bin", "runtime"), f"{where} [npm]")
        bn = n.get("bin_native", {})
        if not isinstance(bn, dict) or any(p not in PLATFORMS or not isinstance(v, str) or not v or os.path.isabs(v) or ".." in v.split("/") for p, v in bn.items()):
            raise ManifestError(f"{where} [npm] bin_native maps a platform ({', '.join(PLATFORMS)}) to a relative path of the platform package's executable")
        if set(n.get("native_bin", {})) - set(PLATFORMS):
            raise ManifestError(f"{where} [npm] native_bin: platform must be one of {', '.join(PLATFORMS)}")
        for key in ("package_json_sha256", "package_lock_sha256"):
            if key in n and not SHA256.match(n[key]):
                raise ManifestError(f"{where} [npm] {key} is not 64 hex digits")
        if ("package_json" in n) != ("package_json_sha256" in n):
            raise ManifestError(f"{where} [npm] package_json and package_json_sha256 go together")
        for key in [k for k in ("package_json", "package_lock") if k in n]:
            path = os.path.join(directory, n[key])
            if not os.path.exists(path):
                raise ManifestError(f"{where} [npm] {key} = {n[key]}: file missing")
            if sha256_file(path) != n[key + "_sha256"]:
                raise ManifestError(f"{where} [npm] {key}: sha256 differs from the file")
    if "derive" in spec:
        _need(spec["derive"], ("base",), f"{where} [derive]")
    if "piglet" in spec:
        _validate_piglet(spec["piglet"], held is not None, where)
    ext = spec.get("extensions", {})
    unknown_ext = set(ext) - {"paths", "count", "processes", "host", "embedded", "default"}
    if unknown_ext:
        raise ManifestError(f"{where} [extensions]: unknown key(s) {', '.join(sorted(unknown_ext))}")
    if ext.get("embedded") and ext.get("paths"):
        raise ManifestError(f"{where} [extensions]: `embedded` and `paths` exclude each other")
    if "prepare" in spec:
        _need(spec["prepare"], ("script",), f"{where} [prepare]")
        if not os.path.exists(os.path.join(directory, spec["prepare"]["script"])):
            raise ManifestError(f"{where} [prepare] script {spec['prepare']['script']} missing")
    if "source" in spec:
        s = spec["source"]
        _need(s, ("repo_env", "commit", "build", "package", "toolchain"), f"{where} [source]")
        if "repo_url" in s and not str(s["repo_url"]).startswith("https://"):
            raise ManifestError(f"{where} [source] repo_url must be an https URL")
        if not COMMIT.match(s["commit"]):
            raise ManifestError(f"{where} [source] commit must be a full 40-hex commit hash")
    if "runtime" in spec:
        runtimes = load_runtimes()
        for rname, rversion in spec["runtime"].items():
            if rname not in runtimes:
                raise ManifestError(f"{where} [runtime] {rname}: not pinned in runtimes.toml")
            if rversion != runtimes[rname]["version"]:
                raise ManifestError(f"{where} [runtime] {rname} = {rversion!r}, but runtimes.toml pins {runtimes[rname]['version']!r}")
    ep = spec.get("endpoint", {})
    if held is None:
        _need(ep, ("apis", "writer"), f"{where} [endpoint]")
    for api in ep.get("apis", []):
        if api not in APIS:
            raise ManifestError(f"{where}: endpoint api {api!r}; use one of {', '.join(APIS)}")
    if ep.get("writer") and not os.path.exists(os.path.join(directory, ep["writer"])) and "derive" not in spec:
        raise ManifestError(f"{where}: writer {ep['writer']} missing")
    for mode in spec.get("modes", {}):
        if mode not in MODES:
            raise ManifestError(f"{where}: unknown mode {mode!r}; use one of {', '.join(MODES)}")
        if not isinstance(spec["modes"][mode], list) or not all(isinstance(x, str) for x in spec["modes"][mode]):
            raise ManifestError(f"{where}: mode {mode} must be a list of strings")
    _validate_divergences(spec.get("divergence", []), where)
    cap = spec.get("capabilities", {})
    if cap.get("pi_extensions", "none") not in EXTENSIONS:
        raise ManifestError(f"{where}: capabilities.pi_extensions must be one of {', '.join(EXTENSIONS)}")
    if held is None and "version" not in spec.get("modes", {}):
        raise ManifestError(f"{where}: a runnable arm declares the `version` mode (the post-install version check)")
    return spec


def _validate_divergences(rows, where):
    """[[divergence]]: workloads (globs that each match a registered workload), optional metrics (globs), the reason and the source of the arm's own statement."""
    from ..workloads import load_all
    from ..divergence import KEYS
    from fnmatch import fnmatchcase
    if not isinstance(rows, list):
        raise ManifestError(f"{where}: divergence is an array of tables, [[divergence]]")
    ids = list(load_all())
    for i, row in enumerate(rows, 1):
        at = f"{where} [[divergence]] #{i}"
        if not isinstance(row, dict):
            raise ManifestError(f"{at}: want a table")
        unknown = set(row) - KEYS
        if unknown:
            raise ManifestError(f"{at}: unknown key(s) {', '.join(sorted(unknown))}")
        for key in ("workloads", "reason", "source"):
            if key not in row:
                raise ManifestError(f"{at}: missing `{key}`")
        for key in ("workloads", "metrics"):
            globs = row.get(key, [])
            if not isinstance(globs, list) or not all(isinstance(g, str) and g for g in globs) or (key == "workloads" and not globs):
                raise ManifestError(f"{at}: `{key}` is a {'non-empty ' if key == 'workloads' else ''}list of glob strings")
        for g in row["workloads"]:
            if not any(fnmatchcase(w, g) for w in ids):
                raise ManifestError(f"{at}: workload glob {g!r} matches no registered workload")
        for key in ("reason", "source"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ManifestError(f"{at}: `{key}` is a non-empty string")
        src = row["source"]
        if not (src.startswith("https://") or (not os.path.isabs(src) and ".." not in src.split("/") and os.path.exists(os.path.join(ROOT, src.split("#")[0])))):
            raise ManifestError(f"{at}: `source` is an https URL or the path of a document in this repository")


# The Piglet Binary record digest a runnable Piglet arm pins (buffon/arms/piglet.py IDENTITY_KEYS).
PIGLET_IDENTITY = {"component_plan_digest"}


def _validate_piglet(p, held, where):
    """[piglet]: a Piglet Binary built from a manifest at a pinned Pigpen commit. A runnable arm pins the identity its build must show."""
    _need(p, ("name", "pigpen_commit", "repo_env", "manifest", "manifest_sha256", "release_version"), f"{where} [piglet]")
    unknown = set(p) - {"name", "pigpen_commit", "repo_env", "manifest", "manifest_sha256", "release_version", "identity"}
    if unknown:
        raise ManifestError(f"{where} [piglet]: unknown key(s) {', '.join(sorted(unknown))}")
    if not COMMIT.match(p["pigpen_commit"]):
        raise ManifestError(f"{where} [piglet] pigpen_commit must be a full 40-hex commit hash")
    if not re.match(r"^BUFFON_SOURCE_REPO_[A-Z0-9_]+$", p["repo_env"]):
        raise ManifestError(f"{where} [piglet] repo_env must name an BUFFON_SOURCE_REPO_* variable")
    m = p["manifest"]
    if not isinstance(m, str) or os.path.isabs(m) or ".." in m.split("/") or not m.endswith(".yaml"):
        raise ManifestError(f"{where} [piglet] manifest must be a relative path to a .yaml inside the Pigpen commit")
    if not SHA256.match(p["manifest_sha256"]):
        raise ManifestError(f"{where} [piglet] manifest_sha256 is not 64 hex digits")
    identity = p.get("identity", {})
    unknown_id = set(identity) - PIGLET_IDENTITY
    if unknown_id:
        raise ManifestError(f"{where} [piglet.identity] unknown key(s) {', '.join(sorted(unknown_id))}")
    if not held and set(identity) != PIGLET_IDENTITY:
        raise ManifestError(f"{where} [piglet.identity]: a runnable Piglet arm pins {', '.join(sorted(PIGLET_IDENTITY))}")
    for key, value in identity.items():
        if not SHA256.match(value):
            raise ManifestError(f"{where} [piglet.identity] {key} is not 64 hex digits")


def load_arm(name, arms_dir=ARMS_DIR):
    directory = os.path.join(arms_dir, name)
    path = os.path.join(directory, "arm.toml")
    with open(path, "rb") as f:
        raw = f.read()
    try:
        spec = tomllib.loads(raw.decode())
    except tomllib.TOMLDecodeError as error:
        raise ManifestError(f"{path}: {error}") from error
    writer_dir = None
    if "derive" in spec:
        base_name = spec["derive"].get("base")
        if base_name == name or not os.path.exists(os.path.join(arms_dir, str(base_name), "arm.toml")):
            raise ManifestError(f"{path}: [derive] base = {base_name!r} is not another arm")
        base = load_arm(base_name, arms_dir)
        if base.install_kind == "derive":
            raise ManifestError(f"{path}: [derive] base {base_name!r} is itself derived; derive from the arm that installs")
        for key in INHERITED_SCALARS:
            spec.setdefault(key, base.spec[key]) if key in base.spec else None
        for key in INHERITED_TABLES:
            if key in base.spec:
                spec[key] = {**base.spec[key], **spec.get(key, {})}
        writer_dir = base.dir
    validate(name, spec, directory)
    arm = Arm(name, spec, directory, hashlib.sha256(raw).hexdigest())
    arm.writer_dir = writer_dir or directory
    return arm


def load_all(arms_dir=ARMS_DIR):
    """{name: Arm} for every arms/<name>/arm.toml, in name order."""
    names = sorted(n for n in os.listdir(arms_dir) if os.path.exists(os.path.join(arms_dir, n, "arm.toml")))
    return {n: load_arm(n, arms_dir) for n in names}


def load_runtimes(path=RUNTIMES_FILE):
    with open(path, "rb") as f:
        return tomllib.load(f)


def host_platform():
    import platform
    system = {"Linux": "linux", "Darwin": "darwin"}.get(platform.system(), platform.system().lower())
    machine = {"x86_64": "x64", "AMD64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine(), platform.machine())
    return f"{system}-{machine}"


EXCLUDED_FILE = os.path.join(ARMS_DIR, "excluded.toml")


def load_excluded(path=EXCLUDED_FILE):
    """[{repo, reason}]: projects deliberately not measured; the report lists them."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        rows = tomllib.load(f).get("excluded", [])
    for r in rows:
        if not (isinstance(r.get("repo"), str) and isinstance(r.get("reason"), str)):
            raise ManifestError(f"{path}: every [[excluded]] needs a repo and a reason")
    return rows
