# SPDX-License-Identifier: Apache-2.0
"""`buffon verify RUN_DIR`: re-validate a run directory the way CI does before the results index accepts it.

Every check is recomputed from the sealed files and the repository; nothing a submitter writes next to the run (a report, a health.json) is believed, only compared with the
recomputation. A check is an error (the run is not accepted) or a warning (a run note, listed). Integrity decides acceptance: the seal, raw.json, the pins, the executables, the
provenance, submission.toml, and a run that switched off what makes numbers comparable at all (telemetry, the A/A copies). Noise never decides it: the health notes, the quiet-host
gate, the hardware class, the number of rounds and the gates a run was allowed to bypass are listed as warnings.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile

from ..arms import lock as locklib
from ..report import cells as cellmath, health as healthlib, noise as noiselib, render
from ..runner import raw as rawlib
from . import manifest, submission

MIN_ROUNDS = 12
MAX_QUIET_BUSY = 0.10   # the default of `--quiet-max-busy`
# Flags that switch off a noise gate. A run made with one is listed with a note, never rejected for it.
NOTE_FLAGS = ("--allow-noisy", "--allow-short", "--no-calibrate", "--no-quiet-gate", "--allow-frequency-scaling")
# Flags that switch off what makes numbers comparable at all (the telemetry every other check reads). A run made with one is rejected.
REJECT_FLAGS = ("--no-telemetry",)
BYPASS_FLAGS = NOTE_FLAGS + REJECT_FLAGS


def bypassed(token, flag):
    """`token` sets `flag`: the flag itself, or an abbreviation that names only it (a run recorded before the parser refused abbreviations)."""
    if not (isinstance(token, str) and token.startswith("--") and len(token) > 2):
        return False
    return token == flag or [f for f in BYPASS_FLAGS if f.startswith(token)] == [flag]


class Result:
    def __init__(self):
        self.checks = []        # {"id", "status": ok|error|warning, "message"}

    def add(self, cid, status, message):
        self.checks.append({"id": cid, "status": status, "message": message})

    def ok(self, cid, message):
        self.add(cid, "ok", message)

    def error(self, cid, message):
        self.add(cid, "error", message)

    def warn(self, cid, message):
        self.add(cid, "warning", message)

    @property
    def accepted(self):
        return not any(c["status"] == "error" for c in self.checks)

    def as_dict(self):
        return {"accepted": self.accepted, "checks": self.checks}


def git(repo, *args):
    try:
        out = subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def lock_at(repo, commit):
    """arms.lock as committed at `commit`: (dict, sha256) or (None, None)."""
    blob = git(repo, "show", f"{commit}:arms.lock")
    if blob is None:
        return None, None
    return json.loads(blob), hashlib.sha256(blob).hexdigest()


LOCK_ARCHIVE = "locks"      # locks/<sha256>.json: the exact bytes of an earlier arms.lock that a published run used (docs/SUBMITTING.md, "The lock archive")


def archived_lock(repo, want):
    """(dict, None) for the archived lock whose sha256 is `want`, (None, None) when the archive holds none, (None, problem) when the file under that name is not that lock.
    The name is checked against the file's bytes, so an entry cannot stand for a lock it is not; `want` must be a bare sha256 (it becomes a file name)."""
    if not isinstance(want, str) or not re.fullmatch(r"[0-9a-f]{64}", want):
        return None, None
    path = os.path.join(repo, LOCK_ARCHIVE, want + ".json")
    if not os.path.isfile(path):
        return None, None
    with open(path, "rb") as f:
        blob = f.read()
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        return None, f"{LOCK_ARCHIVE}/{want}.json has sha256 {got[:12]}: an archived lock is named by the sha256 of its bytes"
    try:
        return json.loads(blob), None
    except ValueError as error:
        return None, f"{LOCK_ARCHIVE}/{want}.json is not JSON: {error}"


def pins(raw, repo, result):
    """The run's lock hash is the current one, one in the lock archive (locks/<sha256>.json), or the one at its runner commit, and each arm's recorded artifact, manifest, version and source commit are the lock's."""
    want, commit = raw.get("lock_sha256"), (raw.get("runner") or {}).get("commit")
    lock = None
    current = os.path.join(repo, "arms.lock")
    archived, bad_entry = archived_lock(repo, want)
    if os.path.exists(current) and manifest.sha256_file(current) == want:
        with open(current) as f:
            lock = json.load(f)
        result.ok("lock", f"arms.lock sha256 {want[:12]} is the repository's lock")
    elif archived is not None:
        lock = archived
        result.ok("lock", f"arms.lock sha256 {want[:12]} is in the lock archive ({LOCK_ARCHIVE}/{want}.json); its runner commit {str(commit)[:12]} need not be in this repository")
    elif bad_entry:
        result.error("lock", bad_entry)
    elif commit:
        lock, got = lock_at(repo, commit)
        if lock is None:
            result.error("lock", f"runner commit {commit[:12]} is not in this repository, and the run's arms.lock ({str(want)[:12]}) is neither the current one nor in the {LOCK_ARCHIVE}/ archive: the pins cannot be checked")
        elif got != want:
            result.error("lock", f"arms.lock at the runner commit has sha256 {got[:12]}, the run says {str(want)[:12]}")
        else:
            result.ok("lock", f"arms.lock sha256 {want[:12]} is the lock at runner commit {commit[:12]}")
    else:
        result.error("lock", "the run records no runner commit and its arms.lock is neither the current one nor in the lock archive")
    if lock is None:
        return
    runner = raw.get("runner") or {}
    if commit and runner.get("tree"):
        tree = git(repo, "rev-parse", f"{commit}^{{tree}}")
        if tree is not None and tree.decode().strip() != runner["tree"]:
            result.error("runner", f"runner tree {runner['tree'][:12]} is not the tree of commit {commit[:12]}")
    bad = []
    used = {s.get("arm") for s in raw.get("samples", []) if s.get("arm")} | {a for a in (raw.get("run") or {}).get("arms") or [] if isinstance(a, str)}
    for arm in sorted(used - set(raw["arms"])):
        bad.append(f"{arm}: measured, but the run records no arm entry for it")
    for arm, info in sorted(raw["arms"].items()):
        if arm.startswith("_"):
            continue
        if info.get("twin_of"):
            base = raw["arms"].get(info["twin_of"])
            if base is None or base.get("twin_of"):
                bad.append(f"{arm}: A/A copy of {info['twin_of']}, which is not an arm of the run")
                continue
            differ = [k for k in ("version", "manifest_sha256", "executable_sha256", "artifact_sha256", "install_tree_sha256", "commit", "tree") if base.get(k) != info.get(k)]
            if differ:
                bad.append(f"{arm}: A/A copy of {info['twin_of']} but its {', '.join(differ)} differ")
            continue
        entry = lock["arms"].get(arm)
        if entry is None:
            bad.append(f"{arm}: not in the lock")
            continue
        if info.get("manifest_sha256") != entry["manifest_sha256"]:
            bad.append(f"{arm}: manifest sha256 differs from the lock")
        if info.get("version") != entry["version"]:
            bad.append(f"{arm}: version {info.get('version')} is not the locked {entry['version']}")
        spec = entry.get("spec", {})
        arts = {a["sha256"] for a in spec.get("artifact", {}).values()}
        if arts and not info.get("artifact_sha256"):
            bad.append(f"{arm}: no artifact digest recorded, the lock pins {len(arts)} artifacts")
        elif info.get("artifact_sha256") and info["artifact_sha256"] not in arts:
            bad.append(f"{arm}: artifact sha256 {info['artifact_sha256'][:12]} is not a locked artifact")
        src = spec.get("source") or {}
        for key, what in (("commit", "built from"), ("tree", "source tree")):
            if src.get(key) and not info.get(key):
                bad.append(f"{arm}: no source {key} recorded, the lock pins {src[key][:12]}")
            elif src.get(key) and info[key] != src[key]:
                bad.append(f"{arm}: {what} {info[key][:12]}, the lock pins {src[key][:12]}")
        if not info.get("executable_sha256"):
            bad.append(f"{arm}: no executable digest recorded")
    result.add("arms", "error" if bad else "ok", "; ".join(bad) if bad else f"{len([a for a in raw['arms'] if not a.startswith('_') and not raw['arms'][a].get('twin_of')])} arms match the lock")


def verify(run_dir, repo=None, is_submission=False, reference=None, seed=20261011):
    """Check one run directory. Returns a Result."""
    from ..arms import manifest as armmanifest
    repo = repo or armmanifest.ROOT
    result = Result()
    run_dir = os.path.normpath(run_dir)
    problems = manifest.check(run_dir)
    result.add("seal", "error" if problems else "ok", "; ".join(problems[:6]) if problems else f"{len(manifest.sealed_files(run_dir))} files match {manifest.NAME}")
    try:
        raw = rawlib.read(run_dir)
    except (OSError, ValueError) as error:
        result.error("raw", f"raw.json does not validate: {error}")
        return result
    result.ok("raw", f"raw.json validates: {len(raw['samples'])} samples")
    facts_path = os.path.join(run_dir, "facts.json")
    if not os.path.exists(facts_path):
        result.error("facts", "facts.json is missing")
        return result
    with open(facts_path) as f:
        facts = json.load(f)
    result.ok("facts", f"facts.json: {facts.get('cpu_model')}, kernel {facts.get('kernel')}")

    from .. import verify as rules
    for name, problems in rules.verify(run_dir):       # Run Rules v1: isolation stamp, host disclosure, host class, provenance (buffon/verify.py)
        result.add(f"rules-{name}", "error" if problems else "ok", "; ".join(problems) if problems else f"{name} passes")
    run = raw["run"]
    if raw.get("refused"):
        result.error("run", f"the run was refused: {raw['refused'][:200]}")
    elif not raw.get("ok"):
        result.error("run", "raw.json says the run is not ok (an egress violation, or an executable changed during the run)")
    else:
        result.ok("run", "the run finished ok")
    if (raw.get("egress") or {}).get("mode") == "none":
        result.error("egress", "no egress audit ran on the recording platform (no /proc and no lsof): a run that cannot show it made no non-loopback connection is not published")
    else:
        result.ok("egress", f"egress audit: {(raw.get('egress') or {}).get('mode', 'recorded')}")
    if (run.get("rounds") or 0) < MIN_ROUNDS:
        result.warn("rounds", f"{run.get('rounds')} measured rounds, the usual minimum is {MIN_ROUNDS}")
    else:
        result.ok("rounds", f"{run['rounds']} measured rounds after {run.get('warmup')} warm-up")
    used = lambda flags: [f for f in flags if any(bypassed(tok, f) for tok in (run.get("command") or []))]
    rejected = used(REJECT_FLAGS) + ([f"--aa {run.get('aa')}"] if run.get("aa") != "all" else [])
    if rejected:
        result.error("flags", f"the run was made with {', '.join(rejected)}, which switches off what makes the numbers comparable")
    else:
        result.ok("flags", "telemetry and every A/A copy were on")
    if used(NOTE_FLAGS):
        result.warn("gates", f"the run was made with {', '.join(used(NOTE_FLAGS))}: a noise gate was off or loosened")
    qg = run.get("quiet_gate") or {}
    if qg.get("enabled") and qg.get("max_busy", 0) > MAX_QUIET_BUSY:
        result.warn("quiet_gate", f"the quiet-host gate allowed the pinned CPUs {qg['max_busy']:.0%} busy before a sample, the usual limit is {MAX_QUIET_BUSY:.0%}")
    elif not qg.get("enabled") or qg.get("timeouts"):
        result.warn("quiet_gate", f"the quiet-host gate was {'off' if not qg.get('enabled') else str(qg['timeouts']) + ' samples gave up'}")
    else:
        result.ok("quiet_gate", f"the quiet-host gate ran; {qg.get('waits', 0)} samples waited, longest {qg.get('max_wait_ms', 0) / 1000:.1f} s")
    pins(raw, repo, result)
    if (raw.get("runner") or {}).get("dirty"):
        result.error("runner", "the runner's checkout had uncommitted changes: its commit does not describe the code that ran")
    hw = raw["hardware"]
    if hw.get("quiet_dedicated"):
        result.ok("hardware", "quiet dedicated hardware by the runner's own detection")
    else:
        result.warn("hardware", ("not quiet dedicated hardware: " + "; ".join(hw.get("reasons", [])[:3]))[:400])

    data = cellmath.build([raw], reference, seed)
    noise = noiselib.build([raw], [facts], data)
    h = healthlib.assess([raw], [facts], data, noise)
    telemetry = next(c for c in h["checks"] if c["id"] == "telemetry")
    result.add("telemetry", "ok" if telemetry["status"] == "ok" else "error", telemetry["detail"])
    reported = {c["id"] for c in result.checks}
    noted = [c for c in h["checks"] if c["status"] == "note"]
    for c in noted:
        if c["id"] not in reported:
            result.warn(c["id"], healthlib.describe(c))
    result.ok("health", h["summary"] + (": listed above, none rejects the run" if noted else ""))
    for name in ("health.json", "report.json"):
        path = os.path.join(run_dir, name)
        if os.path.exists(path):
            with open(path) as f:
                shown = json.load(f)
            shown = shown.get("health", shown) if name == "report.json" else shown
            again = json.loads(json.dumps(h, default=lambda x: None if isinstance(x, float) and x != x else x))
            if shown != again:
                result.error(name, f"{name} does not match the run notes recomputed from the raw data ({shown.get('summary')} against {h['summary']}): it was edited or made with other usual ranges")
            else:
                result.ok(name, f"{name} equals the recomputation")
    generated(run_dir, result)
    if is_submission:
        _, problems = submission.load(run_dir)
        result.add("submission", "error" if problems else "ok", "; ".join(problems) if problems else f"{submission.NAME} is complete")
    result.health = h
    return result


GENERATED = ("report.json", "summary.csv", "report.md", "grade.json", "leaderboard.md", "report-card.md", "report.html", "leaderboard.html", "report-card.html")   # review: the HTML pages are what a reader opens; they are compared too


def run_id_in(text):
    """The run id a generated file's cell ids name (the part before `::`), or None. Markup and quotes end the id, so HTML (`<code>RUN::...`) and quoted commands give the bare id."""
    import re
    m = re.search(r"([^\s`\"'|,<>]+)::[a-z0-9-]+/[a-z0-9-]+@", text)
    return m.group(1) if m else None


def without_external(text):
    """report.md without its External sections (results and suites imported with --external-*, which live outside the run): they sit as one block before the footer."""
    cut = text.find("\n## External")
    foot = text.rfind("\n---\n")
    return text[:cut] + text[foot:] if 0 <= cut < foot else text


def without_external_html(text):
    """report.html without the External sections it embeds from report.md (from their heading to the footer rule)."""
    cut = text.find('<h2 id="external-')
    foot = text.rfind("\n<hr>")
    return text[:cut] + text[foot + 1:] if 0 <= cut < foot else text


def generated(run_dir, result):
    """Reports are generated, never edited: every generated file next to the run equals what `buffon report` writes from the sealed raw data (cell ids renamed to this directory's name, so a run
    copied under another name still verifies). Nothing in a generated file can switch the check off: a report made with --drop-flagged is regenerated with it (the flags are in raw.json);
    one made with --faithfulness is regenerated from the faithfulness scores and correctness failures report.json recorded (those values are compared by `buffon faithfulness`, not here);
    External sections are cut from both sides of report.md."""
    present = [n for n in GENERATED if os.path.exists(os.path.join(run_dir, n))]
    if not present:
        return
    mine = render.run_id_of(run_dir)
    if not os.path.exists(os.path.join(run_dir, "report.json")):
        result.error("generated", f"{', '.join(present)} without report.json: the report cannot be checked")
        return
    with open(os.path.join(run_dir, "report.json")) as f:
        shown = json.load(f)
    gi = shown.get("grade_inputs") or {}
    given = [{"scores": {a: {"overall": v, "correctness_failures": (gi.get("correctness") or {}).get(a, [])} for a, v in (gi.get("faithfulness") or {}).items()}}]
    for a, ids in (gi.get("correctness") or {}).items():
        given[0]["scores"].setdefault(a, {"overall": None, "correctness_failures": ids})
    with tempfile.TemporaryDirectory() as tmp:
        render.render([run_dir], tmp, drop_flagged=bool((shown.get("noise") or {}).get("dropped")), faithfulness_given=given)
        bad = []
        for name in present:
            with open(os.path.join(run_dir, name)) as f:
                have = f.read()
            if name == "report.md":
                have = without_external(have)
            elif name == "report.html":
                have = without_external_html(have)
            old = run_id_in(have)
            if old and old != mine:
                have = have.replace(old + "::", mine + "::")
            with open(os.path.join(tmp, name)) as f:
                want = f.read()
            if have != want:
                bad.append(name)
    if bad:
        result.error("generated", f"{', '.join(bad)} differ from what `buffon report` generates from raw.json: a generated file was edited or made with another version")
    else:
        result.ok("generated", f"{', '.join(present)} equal the regeneration from raw.json")


def text(result, run_dir):
    marks = {"ok": "ok     ", "warning": "warning", "error": "ERROR  "}
    out = [f"{run_dir}: {'ACCEPTED' if result.accepted else 'REJECTED'}" + (f", {result.health['summary']}" if hasattr(result, "health") else "")]
    out += [f"  {marks[c['status']]} {c['id']}: {c['message']}" for c in result.checks]
    return "\n".join(out)
