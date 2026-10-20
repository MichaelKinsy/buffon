# SPDX-License-Identifier: Apache-2.0
"""The designed report.html: a hero, the grade and faithfulness of each entry, one card per family with every metric's unit, spread and rerun command, then the whole report and the
limitations. Pure presentation: it takes a plain-data `view` that render.py builds from the same helpers report.md uses, so a number here is the number there. Every character of text
is escaped. The output is one static file with no script and no external resource (theme.py)."""
import html
import os
import re

from . import html as htmllib, theme

HEADLINE = "Many harnesses. One scripted model."
HEADLINE_YOURS = "Rerun it on yours."
LEDE = ("Buffon measures coding-agent harnesses against the same scripted model, so a number describes the harness and not a model. "
        "Every cell carries its unit, its spread and the command that measures it again.")

# What each memory metric is, by name. A memory metric that is not here is shown as "memory (kind not named)" so it cannot pass for a kind it is not.
MEMORY_KINDS = {"peak_rss_mib": "peak RSS", "rss_mib": "RSS", "ready_rss_mib": "RSS at ready", "pss_mib": "PSS", "ready_pss_mib": "PSS at ready",
                "peak_mem_mib": "cgroup peak memory", "max_proc_rss_mib": "largest process RSS",
                "end_rss_mib": "RSS at the end", "mem_per_conv_mib": "RSS per live conversation (the slope of the end RSS against the conversations)",   # a durable sample
                # a swarm container (scale/*): the container's own counters, not one process's
                "mem_peak_mib": "container peak memory (memory.peak)", "mem_per_agent_mib": "container memory per agent", "mem_baseline_mib": "container memory before the agents",
                "mem_ready_mib": "container memory at ready", "pss_mib_per_agent": "PSS per agent"}

LIMITATIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "LIMITATIONS.md")
# The sections of docs/LIMITATIONS.md, for a report viewed where that file is not. tests/test_report_html.py checks this list against the page.
LIMITATION_TITLES = ("A mock model is not a network", "Mock token counts are estimates", "One machine, one kernel", "Memory means different things", "Some metrics favour a design",
                     "Defaults differ and are not equalised", "Buffon's authors also build PiG, and PiG is one of the arms", "Repetitions are few", "Terminals differ",
                     "Platforms differ", "Instruction counts depend on the host's counters", "Faithfulness is graded by probes Buffon wrote", "Not measured")


def esc(x):
    return html.escape("" if x is None else str(x), quote=True)


def memory_kind(metric, kind):
    """The label of a memory metric, or None for a metric that is not memory."""
    if kind != "memory":
        return None
    if metric in MEMORY_KINDS:
        return MEMORY_KINDS[metric]
    if "footprint" in metric:
        return "own footprint"
    if "heap" in metric:
        return "heap in use"
    return None


def direction(verdict):
    """(symbol, css class, words) for a comparison's verdict. The words say where the arm's median sits against the reference's, never whether that is good."""
    v = verdict or ""
    if v == "loss":
        return "\u25b2", "up", "above the reference"
    if v == "win":
        return "\u25bc", "down", "below the reference"
    if v == "no measurable difference":
        return "\u2248", "same", "no measurable difference"
    if v.startswith("inconclusive"):
        return "?", "unsure", "inconclusive"
    return "\u00b7", "unsure", v or "not compared"


def badge(text, cls=""):
    return f'<span class="badge {cls}"><i></i>{esc(text)}</span>'


def hero(view):
    badges = [badge("PROVISIONAL", "prov") if view["provisional"] else badge("Quiet dedicated hardware")]
    if view.get("notes") is not None:
        badges.append(badge(f"Run notes: {view['notes']}"))
    badges.append(badge(f"reference: {view['reference']}", "mono"))
    if view.get("method"):
        badges.append(badge(f"grade method {view['method']['version']} \u00b7 {view['method']['sha256'][:10]}", "mono"))
    notice = ""
    if view["provisional"]:
        reasons = "".join(f"<li>{esc(r)}</li>" for r in view.get("reasons", []))
        notice = ('<div class="notice"><strong>PROVISIONAL.</strong> Every number here is provisional: at least one run was not on quiet dedicated hardware by the runner\'s own detection. '
                  f'Do not publish or compare it as a result.{"<ul>" + reasons + "</ul>" if reasons else ""}</div>')
    stats = "".join(f'<div class="stat"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for k, v in view["stats"])
    return (f'<header class="hero"><h1>{esc(HEADLINE)} <span class="yours">{esc(HEADLINE_YOURS)}</span></h1><p class="lede">{esc(LEDE)}</p>'
            f'<div class="badges">{"".join(badges)}</div>{notice}<div class="stats">{stats}</div></header>')


def topbar(view):
    nav = [("Grade", "#grade")] if view.get("grade") else []
    nav += [("Families", "#families"), ("Full report", "#full-report"), ("Limitations", "#limitations")]
    links = "".join(f'<a href="{href}">{esc(text)}</a>' for text, href in nav)
    return f'<div class="top"><a class="brand" href="#top">{theme.brand_mark(26)}<span>Buffon</span></a><nav aria-label="sections">{links}</nav></div>'


def grade_section(view):
    entries = view.get("grade") or []
    if not entries:
        return ""
    floor = view.get("faithfulness_floor", 90)
    cards = []
    for e in entries:
        score = '<small>no overall score</small>' if e["overall"] is None else f'<b>{esc(e["overall"])}</b><span>{esc(e["letter"])}</span>'
        faith = e.get("faithfulness")
        if faith is None:
            faith_html = '<div class="faith">Faithfulness to Pi: <b>not measured</b></div>'
        else:
            faith_html = (f'<div class="faith">Faithfulness to Pi: <b>{esc(f"{faith:.0f}")}</b> / 100</div>'
                          f'<div class="bar" role="img" aria-label="faithfulness {faith:.0f} of 100, floor {floor}"><i style="width:{max(0, min(100, faith)):.0f}%"></i><u style="left:{floor}%"></u></div>'
                          f'<div class="faith">floor {esc(floor)}: below it an entry is ranked in its own table</div>')
        rank = "" if e.get("rank") is None else f'<small>rank {esc(e["rank"])}</small>'
        why = f'<div class="why">{esc(e["no_score_reason"])}</div>' if e["overall"] is None and e.get("no_score_reason") else ""
        sub = " \u00b7 ".join(x for x in (e.get("relation"), e.get("table_title")) if x)
        cards.append(f'<article class="entry"><h3>{esc(e["label"])}</h3><div class="rel">{esc(sub)}</div>'
                     f'<div class="score">{score}{rank}</div>{why}<div class="faith">Coverage {esc(e.get("coverage", ""))}</div>{faith_html}</article>')
    prov = " Every score carries PROVISIONAL until the run is on quiet dedicated hardware." if view["provisional"] else ""
    return ('<section id="grade"><h2 class="sec">The grade and faithfulness</h2>'
            '<p class="sub">One score per entry from the families below, and a separate faithfulness score for how closely it behaves like Pi. '
            'Faithfulness is never a weight in the score. The method is fixed before a run and is the same for every entry.' + esc(prov) + '</p>'
            f'<div class="grade">{"".join(cards)}</div></section>')


def tags(row):
    out = [f'<span class="tag kind-{esc(row["kind"])}">{esc(row["kind"])}</span>']
    if row["unit"]:
        out.append(f'<span class="tag">{esc(row["unit"])}</span>')
    label = memory_kind(row["metric"], row["kind"])
    if row["kind"] == "memory":
        out.append(f'<span class="tag mem">{esc(label)}</span>' if label else '<span class="tag mem unnamed">memory (kind not named)</span>')
    return "".join(out)


def row_html(row):
    sym, cls, words = direction(row["verdict"])
    rerun = (f'<details class="rerun"><summary>rerun this cell</summary><code>{esc(row["rerun"])}</code><span class="hint">add <code>--site</code> and your own site profile</span></details>' if row.get("rerun") else "")
    api = f'<span class="api">{esc(row["api"])}</span>' if row.get("api") and row["api"] != "-" else ""
    return (f'<tr><td><span class="wl">{esc(row["workload"])}{api}</span><span class="mn">{esc(row["metric"])}</span><span class="tags">{tags(row)}</span>{rerun}</td>'
            f'<td class="num">{esc(row["ref_median"])}</td><td class="num">{esc(row["arm_median"])}</td><td class="num">{esc(row["ratio"])}'
            f'<span class="spread">A/A floor {esc(row["floor"])}</span></td>'
            f'<td class="num">{esc(row["iqr"])}<span class="spread">IQR ref / arm</span><span class="spread">CV {esc(row["cv"])}</span></td>'
            f'<td class="vd"><span class="dir {cls}" aria-hidden="true">{sym}</span> {esc(words)}</td><td class="num">{esc(row["n"])}</td></tr>')


def family_card(fam):
    rows = fam["rows"]
    arms = sorted({r["arm"] for r in rows})
    body = []
    for arm in arms:
        body.append(f'<tr class="armhead"><td colspan="7">{esc(arm)}</td></tr>')
        body += [row_html(r) for r in rows if r["arm"] == arm]
    head = ("<thead><tr><th>Workload and metric</th><th class=\"num\">Reference median</th><th class=\"num\">Arm median</th><th class=\"num\">Ratio [95% CI]</th>"
            "<th class=\"num\">Spread</th><th>Against the reference</th><th class=\"num\">n</th></tr></thead>")
    return (f'<section class="card fam" id="family-{esc(fam["id"])}"><header><h3>{esc(fam["title"])}</h3><span class="meta">{len(rows)} comparisons \u00b7 {len(arms)} '
            f'{"arm" if len(arms) == 1 else "arms"}</span></header><div class="scroll"><table class="rows">{head}<tbody>{"".join(body)}</tbody></table></div></section>')


def families_section(view):
    fams = [f for f in view["families"] if f["rows"]]
    legend = ('<div class="legend"><span><span class="dir up">\u25b2</span> the arm\'s median is above the reference\'s</span><span><span class="dir down">\u25bc</span> below</span>'
              '<span><span class="dir same">\u2248</span> inside the A/A floor</span><span><span class="dir unsure">?</span> the interval includes 1</span>'
              '<span>The arrows say where a median sits, not whether that is good. A lower value is a lower cost.</span></div>')
    mem = ('<p class="sub">Memory rows name their kind (peak RSS, RSS, PSS and so on). The kinds are different readings, and on macOS the footprint also depends on the runtime\'s allocator: '
           '<a href="#limitations">read the limitations</a> before comparing two memory numbers.</p>')
    body = "".join(family_card(f) for f in fams) or '<p class="sub">No cell has both an arm and the reference.</p>'
    return f'<section id="families"><h2 class="sec">Families</h2>{legend}{mem}{body}</section>'


def limitations_section(doc_lines=None):
    if doc_lines is None and os.path.exists(LIMITATIONS_PATH):
        with open(LIMITATIONS_PATH, encoding="utf-8") as f:
            doc_lines = f.read().splitlines()
    if doc_lines:
        inner = htmllib.convert_doc(doc_lines)
    else:
        inner = ("<ul>" + "".join(f"<li>{esc(t)}</li>" for t in LIMITATION_TITLES) + "</ul><p>The full text is <code>docs/LIMITATIONS.md</code> in the repository.</p>")
    return (f'<details class="panel" id="limitations"><summary>Limitations<small>what a number cannot tell you</small></summary><div class="body md">{inner}</div></details>')


def report_page(view, md_lines, extra_html="", doc_lines=None):
    """A complete HTML document for `buffon report`: the designed front, then the whole of report.md converted, then the limitations."""
    full = (f'<details class="panel" id="full-report"><summary>Full report<small>every section of report.md, and the drift plots</small></summary>'
            f'<div class="body md">{htmllib.convert(md_lines)}\n{extra_html}</div></details>')
    foot = (f'<footer class="foot"><a class="brand" href="#top">{theme.brand_mark(20)}<span>Buffon</span></a><div>{esc(view.get("footer", ""))}</div></footer>')
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(view["title"])}</title><style>{theme.CSS}</style></head><body id="top"><div class="wrap">{topbar(view)}{hero(view)}{grade_section(view)}'
            f'{families_section(view)}{full}{limitations_section(doc_lines)}{foot}</div></body></html>\n')
