# SPDX-License-Identifier: Apache-2.0
"""faithfulness.md from one or more faithfulness.json files: the score table (Pi at 100), per-dimension detail, mismatches with their probe citations, intentional divergences listed
separately, N/A cells with reasons, and the ladder of scores across Pi releases when several runs are given."""
import json
import os

from .probes import DIMENSIONS


def fmt(x):
    return "N/A" if x is None else f"{x:.1f}"


def load(paths):
    docs = []
    for p in paths:
        if os.path.isdir(p):
            p = os.path.join(p, "faithfulness.json")
        with open(p) as f:
            docs.append(json.load(f))
    return docs


def one(doc):
    ref = doc["reference"]
    arms = [a for a in doc["scores"] if a != doc["twin"]]
    out = [f"## Pi {ref['version']} (reference, `{ref['arm']}`), probe set {doc['probe_set_version']}", "",
           f"Pi scores 100 by definition. {len(doc['probes'])} probes; {len(doc['unstable'])} left out because the reference disagreed with its own second copy "
           f"(`{doc['twin']}` scored {fmt(doc['scores'][doc['twin']]['overall'])} against it)." if doc["twin"] in doc["scores"] else "", ""]
    head = "| arm | version | overall | " + " | ".join(f"{d} {DIMENSIONS[d][0]}" for d in DIMENSIONS) + " |"
    out += [head, "|---|---|---:|" + "---:|" * len(DIMENSIONS)]
    out.append(f"| **{ref['arm']}** (reference) | {ref['version']} | **100.0** | " + " | ".join("100.0" if doc["reference_scores"]["dimensions"][d]["pct"] is not None else "N/A" for d in DIMENSIONS) + " |")
    for a in arms:
        sc = doc["scores"][a]
        out.append(f"| {a} | {doc['arms'][a]['version']} | **{fmt(sc['overall'])}** | " + " | ".join(fmt(sc["dimensions"][d]["pct"]) for d in DIMENSIONS) + " |")
    out += ["", "Overall is the weighted mean of the dimensions that apply to the arm (weights: " + ", ".join(f"{d} {w}" for d, (_, w) in DIMENSIONS.items()) +
            "); an N/A dimension is dropped and the weights renormalised, never scored as 0. Machine-facing dimensions (F2, F4, F6, F7) weigh more than human-facing ones (F1, F8). "
            "F8 (TUI) is not implemented in this probe set and has weight 0. A probe is graded, not pass/fail: identical 1.0, equivalent-presentation 0.9, equivalent-semantics 0.6, behaviour-differs 0.0.", ""]
    for a in arms:
        sc = doc["scores"][a]
        out += [f"### {a}", "", "| dimension | identical | equivalent presentation (0.9) | equivalent semantics (0.6) | behaviour differs | of which intentional | N/A | scored | % |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for d, v in sc["dimensions"].items():
            out.append(f"| {d} {v['name']} | {v['match']} | {v.get('presentation', 0)} | {v.get('semantics', 0)} | {v['mismatch']} | {v['intentional']} | {v['na']} | {v['scored']} | {fmt(v['pct'])} |")
        gated = sc.get("correctness_failures") or []
        if gated:
            out += ["", f"**Correctness failures ({len(gated)}): these gate the tool-using performance families:** " + ", ".join(f"`{g}`" for g in gated) + "."]
        graded = [(pid, verdict, why) for pid, verdict, why in sc["rows"] if verdict in ("presentation", "semantics")]
        if graded:
            out += ["", f"Equivalent but not identical ({len(graded)}); each is a deduction, listed by name (a Divergence number marks one a recorded divergence explains):", "",
                    "| probe | class | divergence |", "|---|---|---|"] + [f"| `{pid}` | {'equivalent-presentation' if verdict == 'presentation' else 'equivalent-semantics'} | {why or ''} |" for pid, verdict, why in graded]
        probes = {p["id"]: p for p in doc["probes"]}
        mism = [(pid, why) for pid, verdict, why in sc["rows"] if verdict == "mismatch"]
        if mism:
            out += ["", f"Behaviour differs ({len(mism)}); a Divergence number marks one that a recorded divergence explains, which still counts against the score:", "",
                    "| probe | what it checks | Pi source | divergence | observed |", "|---|---|---|---|---|"]
            for pid, why in mism:
                r = doc["results"][a][pid]
                seen = r.get("reason") or "differs from Pi" if r["status"] != "ok" else "differs from Pi"
                out.append(f"| `{pid}` | {probes[pid]['title']} | {probes[pid]['cite']} | {why or ''} | {seen[:140].replace('|', '/')} |")
        nas = sorted({(doc["results"][a][pid].get("reason") or "")[:100] for pid, verdict, _ in sc["rows"] if verdict == "na"})
        if nas:
            out += ["", "Not applicable (never scored as a miss): " + "; ".join(nas) + ".", ""]
    if doc["unstable"]:
        out += ["### Unstable probes (excluded from every score)", ""] + [f"- `{u}`" for u in doc["unstable"]] + [""]
    return out


def ladder(docs):
    arms = sorted({a for d in docs for a in d["scores"] if a != d["twin"]})
    out = ["## Ladder across Pi releases", "", "| arm | " + " | ".join(f"Pi {d['reference']['version']}" for d in docs) + " |", "|---|" + "---:|" * len(docs)]
    for a in arms:
        out.append(f"| {a} | " + " | ".join(fmt(d["scores"][a]["overall"]) if a in d["scores"] else "-" for d in docs) + " |")
    return out + [""]


def render(paths, out_path=None):
    docs = load(paths)
    docs.sort(key=lambda d: d["started_utc"])
    lines = ["# Pi Faithfulness Score", "", "Deterministic black-box probes against the mock endpoint; no model scores anything. A probe is identical when the harness's normalised observation equals Pi's; otherwise a deterministic comparator grades how it differs. "
             "Hardware does not matter here (probes do not time anything), but Buffon's results-integrity rules for versions, digests and clean checkouts apply: see each run's arms table.", ""]
    if len(docs) > 1:
        lines += ladder(docs)
    for d in reversed(docs):
        lines += one(d)
        lines += [f"**{a}:** {i['caveat']}" for a, i in d["arms"].items() if i.get("caveat")] + [""]
        lines += ["| arm | executable sha256 | install tree sha256 |", "|---|---|---|"] + [f"| {a} | `{i['executable_sha256'][:16]}` | `{i['install_tree_sha256'][:16]}` |" for a, i in d["arms"].items()] + [""]
    text = "\n".join(lines) + "\n"
    out_path = out_path or os.path.join(os.path.dirname(paths[0]) if not os.path.isdir(paths[0]) else paths[0], "faithfulness.md")
    with open(out_path, "w") as f:
        f.write(text)
    return out_path
