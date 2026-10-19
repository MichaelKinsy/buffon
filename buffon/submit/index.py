# SPDX-License-Identifier: Apache-2.0
"""The results index: results/index.json and results/INDEX.md, generated from the verified run directories under results/.

`build` verifies every directory (as a submission) and lists the accepted ones; a directory that does not verify makes the build fail, so a pull request that adds a bad one cannot
be merged with a green index. `check` compares the committed index with the regenerated one: CI fails when they differ."""
import json
import os
import subprocess
import tomllib

from ..report import cells as cellmath, health as healthlib, noise as noiselib
from ..runner import raw as rawlib
from . import check as checklib, manifest, promote, submission


class IndexProblem(Exception):
    pass


def run_dirs(results):
    return sorted(d for d in (os.path.join(results, n) for n in os.listdir(results)) if os.path.isdir(d) and os.path.exists(os.path.join(d, "raw.json"))) if os.path.isdir(results) else []


def entry(run_dir, repo, reference=None):
    """The index row of one run directory; raises IndexProblem when it does not verify as a submission."""
    result = checklib.verify(run_dir, repo, is_submission=True, reference=reference)
    if not result.accepted:
        raise IndexProblem(checklib.text(result, run_dir))
    raw = rawlib.read(run_dir)
    with open(os.path.join(run_dir, "facts.json")) as f:
        facts = json.load(f)
    sub, _ = submission.load(run_dir)
    data = cellmath.build([raw], reference)
    noise = noiselib.build([raw], [facts], data)
    h = result.health
    v = healthlib.values([raw], data, noise)
    noted = [c["id"] for c in h["checks"] if c["status"] == "note"]
    arms = {a: i.get("version") for a, i in raw["arms"].items() if not a.startswith("_") and not i.get("twin_of")}
    return {"id": os.path.basename(run_dir), "finished_utc": raw["run"].get("finished_utc"), "notes": h["notes"], "hardware": raw["hardware"]["class"],
            "site": {"backend": raw["site"].get("backend"), "name": raw["site"].get("name")}, "cpu_model": facts.get("cpu_model"), "kernel": facts.get("kernel"), "arms": arms,
            "workloads": raw["run"].get("workloads"), "rounds": raw["run"].get("rounds"), "reference": data["reference"], "runner_commit": raw["runner"].get("commit"), "lock_sha256": raw.get("lock_sha256"),
            "manifest_sha256": manifest.digest(run_dir), "calibration_cv": v["calibration_cv"], "aa_floor_median": None if v["aa_floor_median"] != v["aa_floor_median"] else v["aa_floor_median"],
            "operator": sub.get("operator"), "independent": sub.get("independent"), "reproduces": sub.get("reproduces"), "noted_checks": noted,
            "tier": "ci-revalidated" if promote.current(run_dir) else "self-reported"}


def build(results, repo, reference=None):
    rows, errors = [], []
    for d in run_dirs(results):
        try:
            rows.append(entry(d, repo, reference))
        except IndexProblem as error:
            errors.append(str(error))
    if errors:
        raise IndexProblem("\n".join(errors))
    rows.sort(key=lambda r: (r["finished_utc"] or "", r["id"]))
    return classify(rows, results)


def toml_file(results, name):
    path = os.path.join(results, name)
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def reproduced_fully(run_dir):
    """True when the directory holds a reproduction.json in which every comparison reproduced (and there was at least one)."""
    path = os.path.join(run_dir, "reproduction.json")
    if not os.path.exists(path):
        return False
    with open(path) as f:
        t = json.load(f).get("totals", {})
    return t.get("cells", 0) > 0 and t.get("reproduced") == t.get("cells")


def classify(rows, results):
    """Fill `tier`, `headline` and `withdrawn` in place. Tiers: self-reported (the submitter's own run), ci-revalidated (promotion.json names the directory's manifest digest),
    maintainer-reproduced (a ci-revalidated run by a listed maintainer, whose reproduction.json reproduced every comparison of this one). A headline is a run on quiet dedicated
    hardware that CI re-validated and nobody withdrew. Run notes never decide it. A withdrawn run stays listed with its reason."""
    maintainers = set(toml_file(results, "MAINTAINERS.toml").get("operators", []))
    withdrawn = {w["id"]: w.get("reason", "") for w in toml_file(results, "WITHDRAWN.toml").get("withdrawn", [])}
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        r["withdrawn"] = withdrawn.get(r["id"])
    for r in rows:
        src = r.get("reproduces")
        if src in by_id and r["tier"] == "ci-revalidated" and r["operator"] in maintainers and reproduced_fully(os.path.join(results, r["id"])) and by_id[src]["tier"] != "self-reported":
            by_id[src]["tier"] = "maintainer-reproduced"
    for r in rows:
        r["headline"] = r["hardware"] == "quiet-dedicated" and r["tier"] != "self-reported" and r["withdrawn"] is None
    return rows


GOVERNANCE = ("WITHDRAWN.toml", "MAINTAINERS.toml")   # who may reproduce and which runs are withdrawn: changed only by a maintainer's own change, never together with a submission


def immutable_problems(results, ref, repo, governance=False):
    """Problems with how the repository changed against git ref `ref` (from its merge base with HEAD). A submission's change may only add files inside run directories (and regenerate the index); a
    run directory that is modified, renamed or deleted is a violation, and so is a change to WITHDRAWN.toml or MAINTAINERS.toml. With `governance` (the maintainers' change)
    the opposite holds: only those two lists and the index may change, so a governance change never carries a run. Either way a file outside the results directory
    must not change: CI checks a results change with the base branch's code, and a change that also edits code, workflows or arms belongs in a reviewed code pull
    request of its own. Without git history to compare with, the answer is a problem, not silence."""
    try:
        # The change is measured from the merge base: a base branch that moved after this one forked (a run directory added or a list edited there) is not this change's.
        base = subprocess.run(["git", "merge-base", ref, "HEAD"], cwd=repo, capture_output=True, text=True, timeout=60)
        base = base.stdout.strip() if base.returncode == 0 and base.stdout.strip() else ref
        out = subprocess.run(["git", "diff", "--name-status", "--no-renames", base], cwd=repo, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        return [f"cannot compare with {ref}: {error}"]
    if out.returncode != 0:
        return [f"cannot compare with {ref}: {out.stderr.strip()[:200]}"]
    rel = os.path.relpath(os.path.abspath(results), repo).replace(os.sep, "/")
    allowed_top = {f"{rel}/{n}" for n in ("index.json", "INDEX.md") + (GOVERNANCE if governance else ())}
    problems = []
    for line in out.stdout.splitlines():
        status, _, path = line.partition("\t")
        if not path.startswith(rel + "/"):
            problems.append(f"{path}: outside {rel}/: a results change touches nothing else (send code, workflow or arm changes in their own pull request)")
            continue
        if path in allowed_top:
            continue
        if governance:   # review: a governance change that also adds a run directory would let a maintainer's flag carry a submission past the submission checks
            problems.append(f"{path}: a governance change (--allow-governance) edits only {' and '.join(GOVERNANCE)} and the index; submit a run in its own change")
            continue
        if path in {f"{rel}/{n}" for n in GOVERNANCE}:
            problems.append(f"{path}: governance file: only a maintainer's change may edit it (buffon index --allow-governance, run by the maintainers job)")
            continue
        if path.rsplit("/", 1)[-1] == promote.NAME:   # CI writes it after merge; one in a change is a submitter promoting its own run to ci-revalidated
            problems.append(f"{path}: {promote.NAME} is written by CI after the merge (buffon promote), never by a submission")
            continue
        if status != "A":
            problems.append(f"{path}: {'modified' if status == 'M' else 'deleted' if status == 'D' else status}: a published run is never changed (withdraw it in WITHDRAWN.toml instead)")
    return problems


def dumps(rows):
    return json.dumps({"results": rows}, indent=1, sort_keys=True, default=lambda x: None if isinstance(x, float) and x != x else x) + "\n"


def remark(r):
    if r["withdrawn"] is not None:
        return f"WITHDRAWN: {r['withdrawn'] or 'no reason given'}"
    return ("notes: " + ", ".join(r["noted_checks"])) if r["noted_checks"] else ""


def markdown(rows):
    out = ["# Results index", "", "Generated by `python3 -m buffon index results`; every row is a run directory that `buffon verify --submission` accepts (docs/SUBMITTING.md). A headline is a run on quiet dedicated hardware that CI re-validated. Run notes describe the conditions of a run; they never remove a row. Withdrawn runs stay listed. Do not edit.", "",
           "| id | finished | run notes | tier | headline | hardware | arms | workloads | rounds | calibration CV | A/A floor (median) | operator | independent | reproduces | remarks |", "|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|"]
    pct = lambda x: "n/a" if x is None else f"{x:.1%}"
    for r in rows:
        out.append(f"| [{r['id']}]({r['id']}/report.md) | {r['finished_utc']} | {r['notes']} | {r['tier']} | {'yes' if r['headline'] else 'no'} | {r['hardware']} | {', '.join(f'{a} {v}' for a, v in r['arms'].items())} | {', '.join(r['workloads'] or [])} | "
                   f"{r['rounds']} | {pct(r['calibration_cv'])} | {pct(r['aa_floor_median'])} | {r['operator']} | {'yes' if r['independent'] else 'no'} | {r['reproduces'] or ''} | {remark(r)} |")
    if not rows:
        out.append("| (no accepted results yet) | | | | | | | | | | | | | | |")
    return "\n".join(out) + "\n"


def write(results, repo, reference=None):
    rows = build(results, repo, reference)
    with open(os.path.join(results, "index.json"), "w") as f:
        f.write(dumps(rows))
    with open(os.path.join(results, "INDEX.md"), "w") as f:
        f.write(markdown(rows))
    return rows


def check(results, repo, reference=None):
    """Problems: the committed index files differ from the regenerated ones, or a run directory does not verify."""
    try:
        rows = build(results, repo, reference)
    except IndexProblem as error:
        return [str(error)]
    problems = []
    for name, text in (("index.json", dumps(rows)), ("INDEX.md", markdown(rows))):
        path = os.path.join(results, name)
        if not os.path.exists(path):
            problems.append(f"{name} is missing: run `python3 -m buffon index {results}` and commit it")
        else:
            with open(path) as f:
                if f.read() != text:
                    problems.append(f"{name} is out of date: run `python3 -m buffon index {results}` and commit it")
    return problems
