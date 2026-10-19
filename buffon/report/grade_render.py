# SPDX-License-Identifier: Apache-2.0
"""leaderboard.md and report-card.md (and their HTML) from a grade result. Every score carries the PROVISIONAL watermark when the run was not on quiet dedicated hardware; a provisional
grade is never a public leaderboard row."""
import json
import os

from . import grade as gradelib, html as htmllib

PROVISIONAL = "PROVISIONAL"
TITLES = {"pi-faithful": "Pi-faithful entries (faithfulness 90 or more)", "not-pi-equivalent": "Not Pi-equivalent (faithfulness under 90, ranked apart)",
          "faithfulness-unmeasured": "Faithfulness not measured (ranked apart until it is)", "no-score": "No overall score"}


def fmt_faith(x):
    return "not measured" if x is None else f"{x:.0f}"


def score_cell(e, prov):
    if e["overall"] is None:
        return "no score"
    return f"**{e['overall']} ({e['letter']})**" + (" PROVISIONAL" if prov else "")


def rank_cell(e):
    lo, hi = e["rank_range"]
    return f"{e['rank']}" + ("" if lo == hi else f" ({lo}-{hi})")


def interval(e):
    if not e["ci"]:
        return "n/a"
    return f"{gradelib.round_half_up(e['ci'][0])}-{gradelib.round_half_up(e['ci'][1])}"


def profile_text(e):
    p = e["profiles"]
    if not p:
        return ""
    scores = [v["score"] for k, v in p.items() if k != "default"] or [v["score"] for v in p.values()]
    ranks = [v["rank"] for k, v in p.items() if k != "default"] or [v["rank"] for v in p.values()]
    return f"{min(scores)}-{max(scores)}, rank {min(ranks)}-{max(ranks)}"


def losses(e):
    """[(family, score, ratio)] of the entry's covered families below the reference score, worst first."""
    ref = 70
    out = [(f, r["score"], r["ratio"], r["gate"]) for f, r in e["families"].items() if r["status"] == "scored" and r["score"] is not None and r["score"] < ref]
    return sorted(out, key=lambda x: x[1])


def leaderboard(result):
    prov = result["provisional"]
    tag = f" — {PROVISIONAL}" if prov else ""
    ref = result["reference"]
    out = [f"# Buffon leaderboard: Pi Harness Score{tag}", ""]
    if prov:
        out += [f"> **{PROVISIONAL}.** The run was not on quiet dedicated hardware by the runner's own detection. These grades are for reading, never for publication, and never a public leaderboard row.", ">"]
        out += [f"> - {x}" for x in result["reasons"][:6]] + [""]
    t = result.get("trust")
    if t:
        out += [f"**Trust: {t['badge']}** (host class {t['host_class']}). " + ("; ".join(t["reasons"][:4]) or "Nothing counts against these grades."), ""]
    if result.get("missing"):
        out += ["Graded with what there is. Missing: " + "; ".join(result["missing"]) + ".", ""]
    out += [f"Method version {result['method']['version']} (`{result['method']['sha256'][:12]}`), weights profile `{result['profile']}`, reference `{ref}` = 70 (C-) in every family. "
            "A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score "
            "(A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: " + str(result.get("notes")) + ".", ""]
    for table in gradelib.TABLES:
        rows = [e for e in result["entries"] if e["table"] == table]
        if not rows:
            continue
        out += [f"## {TITLES[table]}{tag}", ""]
        if table == "no-score":
            out += ["| entry | coverage | why there is no overall score | faithfulness |", "|---|---|---|---|"]
            out += [f"| {e['entry']} ({e['label']}) | {e['coverage']} | {e['no_score_reason'].replace('|', '/')} | {fmt_faith(e['faithfulness'])} |" for e in rows]
            out.append("")
            continue
        rows.sort(key=lambda e: (e["rank"], e["entry"]))
        out += ["| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |", "|---|---|---|---:|---|---|---|---|"]
        for e in rows:
            out.append(f"| {rank_cell(e)} | {e['entry']} ({e['label']}) | {score_cell(e, prov)} | {fmt_faith(e['faithfulness'])} | {e['coverage']} | {e['cost'] or 'n/a'} | {interval(e)} | {profile_text(e)} |")
        out.append("")
        tied = [e for e in rows if e["rank_range"][0] != e["rank_range"][1]]
        if tied:
            out += ["Entries whose 95% intervals overlap are tied in rank: a range in brackets is the best and worst rank the interval allows. "
                    "If the rank changes across the four weight profiles (equal, cpu-heavy, memory-heavy, extension-heavy) the last column says so.", ""]
    low = [(e, losses(e)) for e in result["entries"] if e["overall"] is not None or e["covered"]]
    low = [(e, l) for e, l in low if l]
    out += [f"## Below the reference{tag}", ""]
    if low:
        for e, l in low:
            out.append(f"- **{e['entry']}**: " + ", ".join(f"{f} {gradelib.round_half_up(s)} ({gradelib.letter(s)})" + (f" [{g}]" if g else f" at {r:.2f}x the reference's cost" if r else "") for f, s, r, g in l))
    else:
        out.append("No entry scores below the reference in a family it covers.")
    return out + ["", f"*{PROVISIONAL if prov else 'Quiet dedicated hardware'}: Pi Harness Score method {result['method']['version']}; recompute with `buffon grade --weights FILE` from report.json.*", ""]


def cell_text(r):
    st = r["status"]
    if st == "scored":
        s = gradelib.round_half_up(r["score"])
        mark = " LOSS" if r["score"] < 70 else ""
        note = " gate" if r["gate"] else ""
        return f"{s} {gradelib.letter(r['score'])}{mark}{note}"
    return {gradelib.NA_SCOPE: "N/A out of scope", gradelib.NA_MISSING: "0 (N/A missing)", gradelib.NA_UNMEASURABLE: "N/A not yet measurable", gradelib.NA_HELD: "held",
            gradelib.NOT_RUN: "not run"}[st]


def report_card(result):
    prov = result["provisional"]
    tag = f" — {PROVISIONAL}" if prov else ""
    fams = list(result["entries"][0]["families"]) if result["entries"] else []
    out = [f"# buffon report card{tag}", "", "Family scores per entry (reference = 70, C-). Losses against the reference are listed first; a cell marked LOSS scores under 70.", "",
           f"## Losses first{tag}", ""]
    any_loss = False
    for e in result["entries"]:
        for f, s, r, g in losses(e):
            any_loss = True
            out.append(f"- {e['entry']} / {f}: {gradelib.round_half_up(s)} ({gradelib.letter(s)})" + (f", {g}" if g else f", {r:.2f}x the reference's cost" if r else ""))
    if not any_loss:
        out.append("No loss.")
    out += ["", f"## Entry x family{tag}", "", "| entry | " + " | ".join(fams) + " | overall |", "|---|" + "---|" * (len(fams) + 1)]
    for e in result["entries"]:
        out.append(f"| {e['entry']} | " + " | ".join(cell_text(e["families"][f]) for f in fams) + f" | {score_cell(e, prov)} |")
    out += ["", "## Why a cell is not a score", "", "| entry | family | class | reason |", "|---|---|---|---|"]
    n = 0
    for e in result["entries"]:
        for f, r in e["families"].items():
            if r["status"] != "scored":
                n += 1
                out.append(f"| {e['entry']} | {f} | {r['status']} | {r['reason'].replace('|', '/')} |")
    if not n:
        out.append("| (none) | | | |")
    out += ["", "Classes (from the arm manifests and the run, never by hand): NA-scope is excluded from the mean and counts against coverage; NA-missing scores 0; NA-unmeasurable gives the entry no "
            "overall score until Buffon can drive it; NA-held is not listed; not-run is a family with no workload or no reference data in this run.", ""]
    return out


def write_all(result, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    lb, card = leaderboard(result), report_card(result)
    for name, lines, title in (("leaderboard", lb, "buffon leaderboard"), ("report-card", card, "buffon report card")):
        with open(os.path.join(out_dir, name + ".md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(out_dir, name + ".html"), "w") as f:
            f.write(htmllib.page(title + (f" — {PROVISIONAL}" if result["provisional"] else ""), lines))
    with open(os.path.join(out_dir, "grade.json"), "w") as f:
        json.dump(result, f, indent=1, default=lambda x: None if isinstance(x, float) and x != x else x)
    return lb
