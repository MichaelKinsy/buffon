# SPDX-License-Identifier: Apache-2.0
"""The site's "Other suites" section: other projects' benchmarks, run as they are upstream (`buffon external run`) or imported with their provenance (`buffon external import`).

What they print is theirs. The site keeps the suite's own table verbatim (column names, units and cell text as printed), the raw output one click away, and where and when it ran. Nothing here is
read by a cell, a tile, a ratio, the grade or the all-metrics page: this module only turns the directories into the data one section draws, and copies their files so the site holds its own copies.
A directory is an external run when it holds `external-suite.json`, an imported result set when it holds `external.json`; neither has a `raw.json`.
"""
import json
import os
import shlex

from ..external import KIND_RESULTS, KIND_SUITE, results as extresults, suites as extsuites

NOT_COMPARABLE = "Their method, their numbers: not comparable with Buffon's rows"
STDOUT_SHOWN = 24000   # characters of a run's stdout embedded in the page; the whole file is one link away
# The section of the site that shows a suite is the registry's (`Suite.section`), never a guess from its name. The labels are the groups of cards in a section, one for each project.
GROUP_LABELS = {"durable": {"pi": "Pi's durable suites", "pig": "PiG's storage benchmark", "durable-bench": "durable-bench, run unchanged", "other": "Other durable suites"},
                "other": {"pi": "Pi's other suites", "pig": "PiG's other suites", "pi-bolt": "Pi-Bolt's suites", "other": "Other projects"}}
SUITE_FILE, RESULTS_FILE = "external-suite.json", "external.json"


def kind_of(path):
    """The external kind of a directory (KIND_SUITE or KIND_RESULTS), or None for anything else."""
    if os.path.isfile(os.path.join(path, SUITE_FILE)):
        return KIND_SUITE
    if os.path.isfile(os.path.join(path, RESULTS_FILE)):
        return KIND_RESULTS
    return None


def split(dirs):
    """(run directories, external suite directories, imported result directories) among the arguments of `buffon dashboard`."""
    runs, suites, results = [], [], []
    for d in dirs:
        {KIND_SUITE: suites, KIND_RESULTS: results}.get(kind_of(d), runs).append(d)
    return runs, suites, results


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def read_rows(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def owner_of(key, profiles):
    """{project, owner, owner_url, repo_url} of a checkout key (pi, pig, pi-bolt, durable-bench) from the profile of the same name, else from the registry's repository table (buffon/external/suites.py REPOSITORIES); empty strings for any other key."""
    for p in profiles:
        if p["slug"] == key:
            return {"project": p["project"], "owner": p["maker"], "owner_url": p["maker_url"], "repo_url": (p["links"] or {}).get("repo", "")}
    repo = extsuites.REPOSITORIES.get(key)   # a project the registry knows and the site has no profile for: its repository and owner as the registry records them
    if repo:
        return {"project": key, "owner": repo["owner"], "owner_url": repo["url"], "repo_url": repo["url"]}
    return {"project": key, "owner": "", "owner_url": "", "repo_url": ""}


def project_of_repo(repo, profiles):
    """The checkout key whose profile repository is `repo` ("owner/name" or a URL), else "other"."""
    want = repo.lower().replace("https://github.com/", "").strip("/").removesuffix(".git")
    for p in profiles:
        link = ((p["links"] or {}).get("repo") or "").lower().replace("https://github.com/", "").strip("/").removesuffix(".git")
        if link and link == want:
            return p["slug"]
    return "other"


def host_of(doc):
    host = doc.get("host") or {}
    if not isinstance(host, dict):
        return {}
    keep = ("cpu_model", "memory_gib", "kernel", "machine")
    return {k: host[k] for k in keep if host.get(k) not in (None, "")}


def titles_of(doc):
    """(the registry's title of the run's target or None, the title of the suite family without markup). PiG's Go benchmark is not Pi's vitest one, so the target has a title of its own."""
    suite = extsuites.SUITES.get(doc.get("suite"))
    target = suite.targets.get(doc.get("target")) if suite else None
    family = (suite.title if suite else doc.get("title") or doc.get("suite", "")).replace("`", "")
    return (target.title or None) if target else None, family


def suite_run(path, harness_ids, slug):
    """One external suite run as the section draws it, and the files to copy: ([(source, site-relative destination)])."""
    with open(os.path.join(path, SUITE_FILE), encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("kind") != KIND_SUITE:
        raise ValueError(f"{path} is not an external suite run")
    stdout = read_text(os.path.join(path, "stdout.txt")) or ""
    rows = read_rows(os.path.join(path, "rows.jsonl"))
    parser = doc.get("table") == "console-table"
    copies, files = [], {}
    for name, key in (("stdout.txt", "stdout"), ("stderr.txt", "stderr"), ("rows.jsonl", "rows"), (SUITE_FILE, "record")):
        if os.path.isfile(os.path.join(path, name)):
            dest = f"external/{slug}/{name}"
            copies.append((os.path.join(path, name), dest))
            files[key] = dest
    error = doc.get("rows_error") or ("no table in the output" if parser and not rows else None)
    run = {"target": doc["target"], "arm": doc.get("arm"), "harness": doc.get("arm") if doc.get("arm") in harness_ids else None, "command": " ".join(shlex.quote(a) for a in doc.get("argv") or []),
           "cwd": doc.get("cwd"), "started_utc": doc.get("started_utc"), "wall_s": doc.get("wall_s"), "exit": doc.get("exit"), "timed_out": bool(doc.get("timed_out")), "egress": doc.get("egress") or [],
           "host": host_of(doc), "has_parser": parser, "parsed": bool(rows), "table_error": error if parser and not rows else None, "units": doc.get("units") or {},
           "stdout": stdout[:STDOUT_SHOWN], "stdout_cut": len(stdout) > STDOUT_SHOWN, "stdout_chars": len(stdout), "files": files}
    return doc, run, rows or [], copies


def tables_of(runs):
    """The tables of a suite card. Runs whose own columns match (the same names in the same order, one row for each label of the first column) share one table with a column for each target under every
    column name; any other run has a table of its own. {targets, head: [{name, target}], rows: [[text]]}; cell text is as the suite printed it."""
    parsed = [r for r in runs if r["rows"]]
    columns = lambda r: list(r["rows"][0])

    def matching(group):
        names = columns(group[0])
        if len(names) < 2 or any(columns(r) != names or any(list(row) != names for row in r["rows"]) for r in group):
            return False
        return all(len({row[names[0]] for row in r["rows"]}) == len(r["rows"]) for r in group)
    if len(parsed) >= 2 and matching(parsed):
        names, targets = columns(parsed[0]), [r["target"] for r in parsed]
        labels = []
        for r in parsed:
            labels += [row[names[0]] for row in r["rows"] if row[names[0]] not in labels]
        by = [{row[names[0]]: row for row in r["rows"]} for r in parsed]
        head = [{"name": names[0], "target": None}] + [{"name": c, "target": t} for c in names[1:] for t in targets]
        rows = [[label] + [by[i].get(label, {}).get(c, "") for c in names[1:] for i in range(len(parsed))] for label in labels]
        return [{"targets": targets, "head": head, "rows": rows}]
    return [{"targets": [r["target"]], "head": [{"name": c, "target": None} for c in columns(r)], "rows": [[row.get(c, "") for c in columns(r)] for row in r["rows"]]} for r in parsed]


def results_card(path, profiles, slug):
    doc = extresults.load(path)
    summary = extresults.summarise(path, doc)
    cell = lambda e, m: f"{e[m]['median']:.1f}" if m in e else "-"
    head = [{"name": n, "target": None} for n in ("file", "scenario", "build", "n", "failed", "wall ms (median)", "cpu ms (median)", "peak MB (median)")]
    rows = [[name, scenario, build, str(e["n"]), str(e["failed"]), cell(e, "wall_ms"), cell(e, "cpu_ms"), cell(e, "peak_mb")]
            for (name, build, scenario), e in sorted(summary.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][1]))]
    copies, files = [], []
    for name, info in sorted(doc["files"].items()):
        dest = f"external/{slug}/files/{name}"
        copies.append((os.path.join(path, "files", name), dest))
        files.append({"name": name, "sha256": info["sha256"], "rows": info.get("rows"), "href": dest})
    copies.append((os.path.join(path, RESULTS_FILE), f"external/{slug}/{RESULTS_FILE}"))
    key = project_of_repo(doc["repo"], profiles)
    return key, {"kind": "results", "id": slug, "title": doc["title"], **owner_of(key, profiles), "licence": doc["licence"], "repo": doc["repo"], "commit": doc["commit"], "source_url": doc["source_url"],
                 "published": doc["published"], "imported_utc": doc.get("imported_utc"), "version": doc["version"], "host": doc["host"], "files": files, "record": f"external/{slug}/{RESULTS_FILE}",
                 "tables": [{"targets": [], "head": head, "rows": rows}] if rows else []}, copies


def load(suite_dirs, result_dirs, profiles, harness_ids):
    """(data for the client, [(source, destination)] to copy) for the external directories, or (None, []) when there are none. A directory that is not what it claims to be raises ValueError."""
    if not suite_dirs and not result_dirs:
        return None, []
    order = {sid: i for i, sid in enumerate(extsuites.SUITES)}
    cards, copies, used = {}, [], set()

    def slug_of(path):
        base = os.path.basename(os.path.abspath(path)) or "run"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        return slug
    for d in suite_dirs:
        doc, run, rows, files = suite_run(d, set(harness_ids), slug_of(d))
        run["rows"] = rows
        copies += files
        own, family = titles_of(doc)
        key = (doc["suite"], doc["commit"])
        if key not in cards:
            owner = owner_of(doc.get("repo") or "other", profiles)
            repo_url = owner["repo_url"]
            cards[key] = {"kind": "suite", "id": f"{doc['suite']}-{doc['commit'][:7]}-{doc['target']}", "suite": doc["suite"], "title": family, "titles": set(), "project_key": doc.get("repo") or "other", **owner, "licence": doc.get("licence"),
                          "commit": doc["commit"], "source_url": f"{repo_url}/tree/{doc['commit']}" if repo_url else None, "caller_commit": doc.get("pin_source") == "caller", "notes": doc.get("notes") or "", "runs": []}
        cards[key]["runs"].append(run)
        if own:
            cards[key]["titles"].add(own)
    placed = {s: {k: [] for k in labels} for s, labels in GROUP_LABELS.items()}

    def place(section, key, card):
        groups = placed[section]
        groups[key if key in groups else "other"].append(card)
    for card in sorted(cards.values(), key=lambda c: (order.get(c["suite"], 99), c["suite"])):
        card["tables"] = tables_of(card["runs"])
        titles = card.pop("titles")
        if len(titles) == 1:
            card["title"] = next(iter(titles))   # every run of the card is of one registered target: its own title; runs of several (or of none) are the family's
        for run in card["runs"]:
            run.pop("rows")
        place(extsuites.SUITES[card["suite"]].section if card["suite"] in extsuites.SUITES else "other", card.pop("project_key"), card)
    for d in result_dirs:
        key, card, files = results_card(d, profiles, slug_of(d))
        copies += files
        place("other", key, card)   # an imported result set has no registry entry: it is shown with the rest
    data = {"note": NOT_COMPARABLE}
    for section, groups in placed.items():
        shown = [{"key": k, "label": GROUP_LABELS[section][k], "cards": cs} for k, cs in groups.items() if cs]
        if shown:
            cards_here = [c for g in shown for c in g["cards"]]
            dates = [d[:10] for c in cards_here for d in ([r["started_utc"] for r in c.get("runs", []) if r.get("started_utc")] or [c.get("imported_utc") or c.get("published") or ""]) if d]
            data[section] = {"groups": shown, "runs": sum(len(c.get("runs", [1])) for c in cards_here), "newest": max(dates) if dates else None}
    return data, copies
