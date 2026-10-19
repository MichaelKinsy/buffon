# SPDX-License-Identifier: Apache-2.0
"""Published results of other projects, imported with their provenance and shown in the report's own table.

An import copies the source files unchanged and records where they came from (repository, commit, URL), what version of each harness they measured, on what host, under what licence and when they were
published. It never converts a row into a buffon sample: Buffon did not measure it, on a host it cannot describe, under rules it did not apply. A source whose licence does not permit copying is cited,
never imported.
"""
import hashlib
import json
import os
import shutil
import statistics
import time

from . import KIND_RESULTS

REQUIRED = ("id", "title", "source_url", "repo", "commit", "version", "host", "licence", "published", "files")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path):
    if not path.endswith(".jsonl"):
        return None
    with open(path) as f:
        return sum(1 for line in f if line.strip())


def validate(doc):
    if doc.get("kind") != KIND_RESULTS:
        raise ValueError(f"not an external result set (kind {doc.get('kind')!r})")
    missing = [k for k in REQUIRED if (k not in doc if k == "files" else not doc.get(k))]
    if missing:
        raise ValueError(f"external result set lacks provenance: {', '.join(missing)}")
    for name, info in doc["files"].items():
        if not info.get("sha256"):
            raise ValueError(f"external result file {name} has no sha256")
    return doc


def import_files(paths, out, meta):
    """Copy `paths` into out/files/ and write out/external.json from `meta` (the provenance fields in REQUIRED, except `files`)."""
    os.makedirs(os.path.join(out, "files"), exist_ok=True)
    files = {}
    for path in paths:
        name = os.path.basename(path)
        dest = os.path.join(out, "files", name)
        shutil.copyfile(path, dest)
        files[name] = {"sha256": sha256_file(dest), "bytes": os.path.getsize(dest), "rows": count_rows(dest)}
    doc = {"kind": KIND_RESULTS, **meta, "files": files, "imported_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    validate(doc)
    with open(os.path.join(out, "external.json"), "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    return doc


def load(directory):
    with open(os.path.join(directory, "external.json")) as f:
        doc = validate(json.load(f))
    for name, info in doc["files"].items():
        path = os.path.join(directory, "files", name)
        if not os.path.exists(path) or sha256_file(path) != info["sha256"]:
            raise ValueError(f"external result file {name} does not match its recorded sha256")
    return doc


def rows(directory, doc):
    for name in sorted(doc["files"]):
        if not name.endswith(".jsonl"):
            continue
        with open(os.path.join(directory, "files", name)) as f:
            for line in f:
                if line.strip():
                    yield name, json.loads(line)


def summarise(directory, doc, metrics=("wall_ms", "cpu_ms", "peak_mb")):
    """{(file, build, scenario): {n, failed, <metric>: {median, min, max}}} over the rows that carry `build` and `scenario`; failed rows (ok false) count but are left out of the statistics."""
    groups = {}
    for name, row in rows(directory, doc):
        if "build" not in row or "scenario" not in row:
            continue
        g = groups.setdefault((name, str(row["build"]), str(row["scenario"])), {"n": 0, "failed": 0, "values": {}})
        g["n"] += 1
        if row.get("ok") is False:
            g["failed"] += 1
            continue
        for m in metrics:
            if isinstance(row.get(m), (int, float)):
                g["values"].setdefault(m, []).append(float(row[m]))
    out = {}
    for key, g in groups.items():
        entry = {"n": g["n"], "failed": g["failed"]}
        for m, v in g["values"].items():
            entry[m] = {"median": statistics.median(v), "min": min(v), "max": max(v)}
        out[key] = entry
    return out


def section(dirs):
    """The report's `External results` section for result-set directories; empty when there are none."""
    docs = [(d, load(d)) for d in dirs]
    if not docs:
        return []
    out = ["## External results (published by others)", "",
           "Imported unchanged from the sources below, with the source's own host and versions. Buffon did not measure these numbers: they are not in any cell, aggregate or verdict above, and are not comparable "
           "with them (different hosts, different harness versions, different rules). A claim becomes a buffon result only when it is reproduced under Buffon's rules.", ""]
    for d, doc in docs:
        out += [f"### {doc['title']}", "", f"- source: {doc['source_url']} (repository {doc['repo']}, commit `{doc['commit']}`)", f"- published: {doc['published']}; licence: {doc['licence']}; imported {doc['imported_utc']}",
                f"- versions measured by the source: {doc['version']}", f"- source host: {doc['host']}",
                "- files: " + ", ".join(f"`{n}` (sha256 `{i['sha256'][:16]}`, {i['rows']} rows)" if i.get("rows") is not None else f"`{n}` (sha256 `{i['sha256'][:16]}`)" for n, i in sorted(doc["files"].items())), ""]
        table = summarise(d, doc)
        if table:
            out += ["| file | scenario | build | n | failed | wall ms (median) | cpu ms (median) | peak MB (median) |", "|---|---|---|---:|---:|---:|---:|---:|"]
            for (name, build, scenario), e in sorted(table.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][1])):
                cell = lambda m: f"{e[m]['median']:.1f}" if m in e else "-"
                out.append(f"| {name} | {scenario} | {build} | {e['n']} | {e['failed']} | {cell('wall_ms')} | {cell('cpu_ms')} | {cell('peak_mb')} |")
            out.append("")
    return out
