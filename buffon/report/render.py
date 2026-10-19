# SPDX-License-Identifier: Apache-2.0
"""report.md, report.json and summary.csv from run directories (`python3 -m buffon report DIR...`).

Every number is labelled PROVISIONAL unless every run directory says quiet dedicated hardware (raw.json hardware.class). Within an arm's section the losses come first. "No measurable
difference" is stated for anything inside the A/A floor. A cell the arm could not run is "cannot run", never a loss, win or tie; each arm has a coverage column.
"""
import csv
import json
import math
import os
import sys

from .. import stats
from ..runner import raw as rawlib
from . import cellid as cellidlib, cells as cellmath, metrics as metricslib
from . import extras, grade as gradelib, grade_inputs, grade_render, health as healthlib, noise as noiselib, races as raceslib

PROVISIONAL = "PROVISIONAL"
VERDICT_ORDER = ["loss", "inconclusive", "no measurable difference", "win", "too few rounds"]


def fmt(x, digits=3):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    if isinstance(x, (int, float)):
        if abs(x) >= 1e6:
            return f"{x / 1e6:.2f}M"
        if abs(x) >= 100:
            return f"{x:,.0f}"
        return f"{x:.{digits}g}" if abs(x) < 10 else f"{x:.1f}"
    return str(x)


def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.1%}"


def floor_pct(f):
    """A floor in natural-log units as the percentage it allows."""
    return "n/a" if f is None or (isinstance(f, float) and math.isnan(f)) else pct(math.expm1(f))


def ratio_text(c):
    if c.not_compared:
        return f"different work: not compared ({c.not_compared})"
    lo, hi = c.ci
    return f"{fmt(c.ratio)} [{fmt(lo)}, {fmt(hi)}]"


def equivalence_text(c):
    """The TOST outcome of a comparison for a table cell: `yes ±5%` or `no ±5%` (the margin the metric declares), `n/a` where no margin is declared."""
    e = c.equivalence
    if not e:
        return "n/a"
    m = e["margin"]
    return f"{'yes' if e['equivalent'] else 'no'} ±{m:.1%}" if m else f"{'yes' if e['equivalent'] else 'no'} exact"


def run_id_of(path):
    """The run directory's name: the part of a cell id that says which run holds the samples."""
    return os.path.basename(os.path.abspath(path if os.path.isdir(path) else os.path.dirname(path)))


def cell_ids(data, run_ids):
    """{(scenario, api, metric): cell id} for every cell of the report: the first run directory that holds a measured sample of the cell names it."""
    first = {}
    for s in data["samples"]:
        first.setdefault((s["scenario"], s.get("api")), s["_run"])
    return {(c.scenario, c.api, c.metric): cellidlib.make(run_ids[first.get((c.scenario, c.api), 0)], c.scenario, c.api, c.metric) for c in data["cells"]}


def load(dirs):
    runs = [rawlib.read(d) for d in dirs]
    facts = []
    for d in dirs:
        path = os.path.join(d if os.path.isdir(d) else os.path.dirname(d), "facts.json")
        facts.append(_json(path) if os.path.exists(path) else {})
    return runs, facts


def _json(path):
    with open(path) as f:
        return json.load(f)


def provisional(runs):
    reasons = []
    for i, r in enumerate(runs):
        if not r["hardware"].get("quiet_dedicated"):
            reasons += [f"run {i + 1}: {x}" for x in r["hardware"].get("reasons", ["not quiet dedicated hardware"])]
    return bool(reasons), reasons


def mixed_runs(runs):
    """What differs between the run directories of one report: a report is one lockfile, one runner and one seed (DESIGN.md section 5)."""
    fields = (("arms.lock", lambda r: r.get("lock_sha256")), ("runner commit", lambda r: (r.get("runner") or {}).get("commit")),
              ("runner diff", lambda r: (r.get("runner") or {}).get("diff_sha256")), ("seed", lambda r: r["run"].get("seed")))
    return [name for name, get in fields if len({get(r) for r in runs}) > 1]


def nodes_of(facts):
    """The distinct Kubernetes nodes the run directories ran on (facts.json `node`), in order; empty off a cluster."""
    out = []
    for f in facts:
        if f.get("node") and f["node"] not in out:
            out.append(f["node"])
    return out


def short_rounds(runs):
    return [r["run"].get("rounds") for r in runs if r["run"].get("rounds", 0) < 12 and any(not s["warmup"] for s in r["samples"] if s["scenario"].split("/")[0] not in ("soak", "reliability"))]


def header(runs, facts, prov, reasons, data):
    tag = f" — {PROVISIONAL}" if prov else ""
    out = [f"# buffon report{tag}", ""]
    if prov:
        out += [f"> **{PROVISIONAL}.** Every number in this report is provisional: at least one run was not on quiet dedicated hardware by the runner's own detection. Do not publish or compare it with another report.", ">", "> Why:"]
        out += [f"> - {x}" for x in reasons]
        out += [""]
    else:
        out += ["> Every run in this report was on quiet dedicated hardware by the runner's own detection (docs/RUNNING.md, \"Hardware label\").", ""]
    mixed = mixed_runs(runs)
    if mixed:
        out += [f"> **Mixed runs.** The run directories differ in {', '.join(mixed)}; their rounds are pooled as more rounds of one comparison. The header below names only the first "
                "run's lock and runner: check each run directory before reading a pooled number.", ""]
    nodes = nodes_of(facts)
    if len(nodes) > 1:
        out += [f"> **Several nodes.** The runs here ran on {len(nodes)} nodes ({', '.join(f'`{n}`' for n in nodes)}). Each ratio pairs rounds within one run, so within one node, "
                "but the pooled ratio mixes nodes. Render one report per node, and take a headline only from a comparison that reproduces on both nodes of the pair "
                "(`buffon compare`; docs/METHODOLOGY.md, \"On a cluster\").", ""]
    elif len(nodes) == 1:
        out += [f"> **One node.** Every run here ran on node `{nodes[0]}`. A comparison is a headline only when it reproduces on a second node (`buffon compare`; docs/METHODOLOGY.md, \"On a cluster\").", ""]
    shorts = short_rounds(runs)
    if shorts:
        out += [f"> **Not a measured run.** A run here has fewer than 12 measured rounds ({', '.join(map(str, shorts))}); its intervals are wide and its floor is unreliable.", ""]
    first = runs[0]
    out += ["| field | value |", "|---|---|"]
    out += [f"| reference arm | {data['reference']} |", f"| arms | {', '.join(a for a in data['base'])} (each with an A/A copy `<id>-b` where the run had one) |",
            f"| runs | {len(runs)} |", f"| seed | {first['run'].get('seed')} |", "| token counts | the mock's usage: prompt tokens = request wire bytes / 4, completion tokens = one per streamed part + 12 per tool call; no tokenizer is pinned (METHODOLOGY section 3) |", f"| arms.lock sha256 | `{first.get('lock_sha256')}` |",
            f"| runner commit / tree | `{(first['runner'].get('commit') or '')[:12]}` / `{(first['runner'].get('tree') or '')[:12]}`{' (dirty)' if first['runner'].get('dirty') else ''} |"]
    for i, (r, f) in enumerate(zip(runs, facts), 1):
        run = r["run"]
        cal = r.get("calibration") or {}
        out.append(f"| run {i} | site `{r['site'].get('name')}` ({r['site'].get('backend')}){', node `' + f['node'] + '`' if f.get('node') else ''}, {run.get('rounds')} measured + {run.get('warmup')} warm-up rounds, harness CPUs `{fmt_cpus(run.get('harness_cpus'))}`, "
                   f"mock CPUs `{fmt_cpus(run.get('mock_cpus'))}`, {f.get('cpu_model')}, kernel {f.get('kernel')}, meter {meter_of(r)}; "
                   f"load before/after {fmt_load(f.get('load_before'))} / {fmt_load(f.get('load_after'))}; calibration: CV {pct(cal.get('max_cv'))} of {cal.get('metric')} "
                   f"(gate {pct(cal.get('gate'))}) {'passed' if cal.get('passed') else 'FAILED or not run'}; hardware **{r['hardware']['class']}**; host class **{run.get('host_class', 'not recorded')}**; "
                   f"isolation **{(run.get('isolation') or {}).get('stamp') or (run.get('isolation') or {}).get('isolation', 'not recorded')}** |")
        out.append(f"| run {i} CPU cost | {perf_text(run.get('perf'), r.get('samples', []))} |")
        if run.get("clock_claim"):
            out.append(f"| run {i} clock | the site claims a virtual machine whose platform fixes the CPU clock and turbo state ({run['clock_claim']}); the machine shows neither, so the runner could not verify it |")
    return out


def perf_text(perf, samples=()):
    """What the run's CPU cost is measured in: instructions where the host counted them (the headline), else CPU time, and why. Samples whose counts the kernel scaled
    (a multiplexed counter: an estimate, not a count) are counted here, so a reader sees how many instruction numbers are estimates."""
    if not perf:
        return "CPU time only (no instruction-counter record in this run)"
    if perf.get("available"):
        scope = {"user+kernel": "user and kernel instructions", "user": "user-space instructions only", "sampled": "instructions sampled from proc_pid_rusage"}.get(perf.get("scope"), str(perf.get("scope")))
        extra = f" ({perf['reason']})" if perf.get("reason") else ""
        counted = [s for s in samples if "instructions" in s and not s.get("warmup")]
        scaled = sum(1 for s in counted if s.get("perf_multiplexed"))
        mux = f"; **{scaled} of {len(counted)} measured samples' counts were scaled** (the kernel multiplexed the counter: those numbers are estimates)" if scaled else ""
        return f"**instructions** ({scope}) are the headline CPU metric; CPU time (user + system) and wall time are separate cells{extra}{mux}"
    return f"**CPU time** (user + system) is the headline CPU metric: instruction counts are unavailable ({perf.get('reason') or 'no reason recorded'})"


def fmt_cpus(c):
    return ",".join(map(str, c)) if c else "none"


def fmt_load(x):
    return "n/a" if not x else f"{x[0]:.1f}"


def meter_of(r):
    for s in r["samples"]:
        if s.get("meter"):
            return s["meter"]
    return "n/a"


def summary_table(data, prov, runs):
    tag = f" — {PROVISIONAL}" if prov else ""
    cells = data["cells"]
    ref = data["reference"]
    out = [f"## Summary by axis{tag}", "", "Counts of cells where the arm is measurably worse (loss), inconclusive, inside the A/A floor (no measurable difference) or measurably better (win) than the reference "
           f"`{ref}`. A \"cannot run\" cell is never counted. Coverage is the cells the arm produced values for out of all cells in the report.", "",
           "| arm | coverage | family | losses | inconclusive | no measurable difference | wins |", "|---|---|---|---:|---:|---:|---:|"]
    for a in data["base"]:
        if a == ref:
            continue
        have, total = cellmath.coverage(runs, a, cells)
        t = cellmath.tally(cells, a)
        mark = " †" if (data.get("caveats") or {}).get(a) else ""
        for fam in sorted(t):
            row = t[fam]
            out.append(f"| {a}{mark} | {have}/{total} | {fam} | {row.get('loss', 0)} | {row.get('inconclusive', 0)} | {row.get('no measurable difference', 0)} | {row.get('win', 0)} |")
        if not t:
            out.append(f"| {a}{mark} | {have}/{total} | (no comparable cells) | 0 | 0 | 0 | 0 |")
    for a in data["base"]:
        if (data.get("caveats") or {}).get(a):
            out += ["", f"† `{a}`: {data['caveats'][a]}"]
    return out


def arm_section(data, arm, prov):
    tag = f" — {PROVISIONAL}" if prov else ""
    ref = data["reference"]
    rows = []
    for c in data["cells"]:
        comp = c.comparisons.get(arm)
        if comp:
            rows.append((c, comp))
    out = [f"## {arm} against {ref}{tag}", ""]
    if (data.get("caveats") or {}).get(arm):
        out += [f"> **Read this first:** {data['caveats'][arm]}", ""]
    if not rows:
        return out + [f"No cell has both `{arm}` and `{ref}` values.", ""]
    for verdict, title in (("loss", "Losses (measurably worse than the reference)"), ("inconclusive", "Inconclusive (outside the floor, interval includes 1)"),
                           ("no measurable difference", "No measurable difference (inside the A/A floor)"), ("win", "Wins (measurably better than the reference)"),
                           ("too few rounds", "Too few rounds to compare"), ("not compared", "Different work: not compared (the arm's own account; its median is shown, no ratio)")):
        sel = [(c, comp) for c, comp in rows if (comp.verdict.startswith("inconclusive") and verdict == "inconclusive") or comp.verdict == verdict]
        if not sel:
            if verdict == "loss":
                out += [f"### {title}{tag}", "", "None.", ""]
            continue
        sel.sort(key=lambda cc: -(cc[1].ratio if cc[1].ratio == cc[1].ratio and math.isfinite(cc[1].ratio) else 0) if verdict == "loss" else cc[0].scenario)
        pig = arm in (data.get("previous") or {})
        step_head = f" {step_label(data, arm)} |" if pig else ""
        out += [f"### {title}{tag}", "", "| workload | api | metric | kind | unit | n | reference median | arm median | ratio [95% CI] | A/A floor | MDE | CV ref / arm | IQR ref / arm | outliers ref / arm | p (Holm) | equivalent (TOST) | note | cell |" + step_head,
                "|---|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|---|" + ("---|" if pig else "")]
        for c, comp in sel:
            cv, iqr, out_n = noiselib.cell_columns(c, data["reference"], arm)
            out.append(f"| {c.scenario} | {short_api(c.api)} | {c.metric} | {metricslib.describe(c.metric)[0]} | {metricslib.describe(c.metric)[1]} | {comp.n} | {fmt(comp.ref_median)} | {fmt(comp.arm_median)} | {ratio_text(comp)} | {floor_pct(comp.floor)} | {pct(c.mde)} | {cv} | {iqr} | {out_n} | {fmt(comp.p_holm)} | {equivalence_text(comp)} | {comp.note} | `{(data.get('cell_ids') or {}).get((c.scenario, c.api, c.metric), '')}` |"
                       + (f" {step_cell(c, arm)} |" if pig else ""))
        out.append("")
    return out


def rerun_section(data, prov):
    """Every cell's id and the one command that measures it again."""
    tag = f" — {PROVISIONAL}" if prov else ""
    out = [f"## Cell ids and rerun commands{tag}", "", f"Every cell has an id, `<run id>::<workload>@<api>#<metric>`. `{cellidlib.RUN_COMMAND} <cell id> --site <your site profile>` repeats the plan of the run that holds the cell "
           "(its arms, rounds, seed and parameters) for that workload and API only, on your host, and compares your result with the original. The raw samples of every cell are in the run directory's raw.json; "
           "this report is generated from them and from nothing else, and `buffon verify` regenerates it to check that no number was edited.", "", "| workload | api | metric | cell id |", "|---|---|---|---|"]
    for c in data["cells"]:
        out.append(f"| {c.scenario} | {short_api(c.api)} | {c.metric} | `{data['cell_ids'][(c.scenario, c.api, c.metric)]}` |")
    return out + [""]


def version_of(data, arm):
    return (data.get("versions") or {}).get(arm) or arm


def step_label(data, arm):
    old = data["previous"][arm]
    return f"{version_of(data, old).split('+')[0]} → {version_of(data, arm).split('+')[0]} (newer / previous)"


def step_cell(c, arm):
    s = c.steps.get(arm)
    return "n/a" if s is None else f"{ratio_text(s)} {s.verdict}"


def short_api(api):
    return {"openai-completions": "chat", "anthropic-messages": "anthropic", "openai-responses": "responses", None: "-"}.get(api, str(api))


def version_section(data, prov):
    """For every arm whose manifest names a `previous` arm: the same cells, the arm compared with its previous, losses (the newer slower) first. The relation is data in the manifests; the
    buffon names no harness."""
    out = []
    tag = f" — {PROVISIONAL}" if prov else ""
    order = {"loss": 0, "inconclusive": 1, "no measurable difference": 2, "win": 3}
    for arm, old in sorted((data.get("previous") or {}).items()):
        rows = [c for c in data["cells"] if arm in c.steps]
        if not rows:
            continue
        rows.sort(key=lambda c: (order.get(c.steps[arm].verdict.split(" (")[0], 4), c.scenario, c.metric))
        out += [f"## {arm} against its previous arm {old}: {step_label(data, arm)}{tag}", "",
                f"`{old}` is the earlier arm and `{arm}` the later one (declared as `previous` in the manifest; a loss means the later arm is measurably worse, a win measurably better). "
                "The floor is the larger of the two arms' A/A floors; a ratio inside it is no measurable difference.", "",
                f"| workload | api | metric | {old} median | {arm} median | ratio [95% CI] | A/A floor | verdict |", "|---|---|---|---:|---:|---|---:|---|"]
        for c in rows:
            s = c.steps[arm]
            out.append(f"| {c.scenario} | {short_api(c.api)} | {c.metric} | {fmt(s.ref_median)} | {fmt(s.arm_median)} | {ratio_text(s)} | {floor_pct(s.floor)} | **{s.verdict}** |")
        out.append("")
    return out


def floor_section(data, prov):
    tag = f" — {PROVISIONAL}" if prov else ""
    out = [f"## A/A noise floor{tag}", "", "Each arm's A/A copy `<id>-b` is the same executable run in the same rounds. The floor of a cell is the largest deviation from 1 the copy's ratio-of-medians interval allows; "
           "a difference between arms smaller than the floor is reported as no measurable difference. The table gives, per arm and workload, the median and the maximum floor over the scored metrics, "
           "and the reference's minimum detectable effect at 80% power.", "", "| arm | workload | api | cells | median floor | max floor | worst metric |", "|---|---|---|---:|---:|---:|---|"]
    agg = {}
    for c in data["cells"]:
        for arm, (floor, _) in c.aa.items():
            if floor is not None:
                agg.setdefault((arm, c.scenario, c.api), []).append((floor, c.metric))
    for (arm, scenario, api), vals in sorted(agg.items()):
        fl = sorted(v[0] for v in vals)
        worst = max(vals)
        out.append(f"| {arm} | {scenario} | {short_api(api)} | {len(vals)} | {floor_pct(fl[len(fl) // 2])} | {floor_pct(worst[0])} | {worst[1]} |")
    if not agg:
        out.append("| (no A/A copies in these runs) | | | | | | |")
    mdes = [c.mde for c in data["cells"] if c.mde == c.mde]
    if mdes:
        mdes.sort()
        out += ["", f"Minimum detectable effect of the reference's A/A pair over all cells: median {pct(mdes[len(mdes) // 2])}, worst {pct(mdes[-1])}. A difference smaller than the cell's MDE cannot be seen in this run."]
    return out + [""]


def failure_section(runs, prov):
    tag = f" — {PROVISIONAL}" if prov else ""
    fails, skips, egress = {}, {}, []
    attempts = {}
    for r in runs:
        for s in r["samples"]:
            key = (s["arm"], s["scenario"], s.get("api"))
            if s["warmup"]:
                continue
            attempts[key] = attempts.get(key, 0) + 1
            if "failure" in s:
                fails.setdefault(key, []).append(s["failure"])
        for k in r["skipped"]:
            skips[(k["arm"], k["scenario"], k.get("api"))] = k["reason"]
        egress += r["egress"].get("violations", [])
    out = [f"## Failures, cannot-run and egress{tag}", ""]
    out += ["### Failed samples (every attempt is in the raw data; none is dropped)", ""]
    if fails:
        out += ["| arm | workload | api | failed / attempts | first failure |", "|---|---|---|---:|---|"]
        for (arm, scenario, api), msgs in sorted(fails.items()):
            out.append(f"| {arm} | {scenario} | {short_api(api)} | {len(msgs)}/{attempts[(arm, scenario, api)]} | {msgs[0][:160].replace('|', '/')} |")
    else:
        out.append("None.")
    out += ["", "### Cannot run (never counted as a loss, win or tie)", ""]
    if skips:
        out += ["| arm | workload | api | reason |", "|---|---|---|---|"]
        out += [f"| {a} | {s} | {short_api(p)} | {why[:200].replace('|', '/')} |" for (a, s, p), why in sorted(skips.items(), key=lambda kv: tuple(str(x) for x in kv[0]))]
    else:
        out.append("None.")
    out += ["", "### Egress", ""]
    modes = {r["egress"].get("mode") for r in runs}
    out.append(f"Method: {', '.join(sorted(str(m) for m in modes))}. Any connection to a non-loopback address fails the sample and the run.")
    if egress:
        out += ["", "| arm | workload | api | remotes |", "|---|---|---|---|"]
        out += [f"| {v['arm']} | {v['scenario']} | {short_api(v.get('api'))} | {', '.join(v['remotes'])} |" for v in egress]
    else:
        out.append("No harness connected outside the loopback.")
    return out + [""]


def soak_section(data, prov):
    tag = f" — {PROVISIONAL}" if prov else ""
    rows = [s for s in data["samples"] if s["scenario"].startswith("soak/")]
    if not rows:
        return []
    out = [f"## Soak{tag}", "", "A series is flat when its second half stays within its band (descriptors, threads, processes: max(2, 5% of the median); memory: 10% of the median). "
           "A second half with fewer than 3 samples is undecided, never flat. Slopes are per hour over the second half. A soak runs once per session: replicate with more sessions.", "",
           "| workload | arm | minutes | think ms | turns | verdict | fds slope/h | threads slope/h | rss slope MiB/h | rss median MiB | note |", "|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|"]
    for s in sorted(rows, key=lambda s: (s["scenario"], s["arm"])):
        verdict = "failed" if "failure" in s else "flat" if s.get("flat") else "undecided" if s.get("undecided") else "NOT FLAT"
        out.append(f"| {s['scenario']} | {s['arm']} | {fmt(s.get('soak_minutes'))} | {fmt(s.get('think_ms'))} | {s.get('turns')} | **{verdict}** | {fmt(s.get('fds_slope_per_h'))} | "
                   f"{fmt(s.get('threads_slope_per_h'))} | {fmt(s.get('rss_mib_slope_per_h'))} | {fmt(s.get('rss_mib_median'))} | {str(s.get('failure', ''))[:100]} |")
    return out + [""]


def reliability_verdicts(data):
    """{(fault, api): {arm: (pass, reasons)}}: an arm passes when its invariants hold on every repetition and its stable signature equals the reference's; a copy must agree with its original."""
    rel = [s for s in data["samples"] if s["scenario"].startswith("reliability/")]
    ref = data["reference"]
    groups = {}
    for s in rel:
        groups.setdefault((s["scenario"], s.get("api")), {}).setdefault(s["arm"], []).append(s)
    out = {}
    for key, by_arm in groups.items():
        def stable(runs):
            sigs = {r.get("signature") for r in runs}
            return next(iter(sigs)) if len(sigs) == 1 else None
        want = stable(by_arm[ref]) if ref in by_arm else None
        for arm, runs in by_arm.items():
            reasons = sorted({r["invariant_failures"] for r in runs if r.get("invariant_failures")})
            sig = stable(runs)
            if sig is None:
                reasons.append("outcome differs between repetitions")
            if arm != ref and not arm.endswith("-b") or arm.endswith("-b") and arm[:-2] != ref:
                if want is None:
                    reasons.append(f"no stable {ref} signature to compare with")
                elif sig is not None and sig != want:
                    reasons.append(f"differs from {ref}")
            if arm.endswith("-b") and arm[:-2] in by_arm and stable(by_arm[arm[:-2]]) != sig:
                reasons.append("A/A copy disagrees with its original")
            out.setdefault(key, {})[arm] = (not reasons, reasons)
    return out


def reliability_section(data, prov):
    tag = f" — {PROVISIONAL}" if prov else ""
    verdicts = reliability_verdicts(data)
    if not verdicts:
        return []
    arms = [a for a in data["arms"]]
    out = [f"## Reliability{tag}", "", f"Pass means the invariants held on every repetition (the process ended, no crash trace, no false success, the session file parsed) and the arm's observable outcome (its signature) "
           f"equalled `{data['reference']}`'s; an A/A copy that disagrees with its original is a flaky result. `{data['reference']}` itself passes on invariants and stable signature.", "",
           "| fault | api | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]
    fails = []
    for (fault, api), by_arm in sorted(verdicts.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        row = []
        for a in arms:
            if a in by_arm:
                ok, why = by_arm[a]
                row.append("pass" if ok else "**FAIL**")
                if not ok:
                    fails.append(f"- `{a}` {fault} ({short_api(api)}): {'; '.join(why)}")
            else:
                row.append("cannot run")
        out.append(f"| {fault} | {short_api(api)} | " + " | ".join(row) + " |")
    if fails:
        out += ["", "Failures:"] + fails
    return out + [""]


def excluded_section(prov):
    from ..arms import manifest
    rows = manifest.load_excluded()
    if not rows:
        return []
    tag = f" — {PROVISIONAL}" if prov else ""
    return [f"## Not measured{tag}", "", "Projects that resemble Pi implementations and were left out, with the reason:", "", "| project | reason |", "|---|---|"] + \
           [f"| {r['repo']} | {r['reason'].replace('|', '/')} |" for r in rows] + [""]


def piglet_section(runs, prov):
    """Arms that are Piglets: one binary made of a base Piglet plus slots. The slot list and the binary size are what the reader compares with the other arms."""
    rows, seen = [], set()
    for r in runs:
        for a, i in sorted(r["arms"].items()):
            pig = i.get("piglet") if isinstance(i, dict) else None
            if not pig or a in seen or a.endswith("-b"):
                continue
            seen.add(a)
            slots = ", ".join(pig.get("slots") or []) or "none"
            extra = "; ".join(x for x in (f"strip: {pig['strip']}" if pig.get("strip") else "", f"runtime slot: {pig['runtime_slot']}" if pig.get("runtime_slot") else "") if x)
            rows.append(f"| {a} | {pig.get('label')} | {slots}{('; ' + extra) if extra else ''} | {pig.get('binary_bytes', 0) / 1e6:.1f} MB |")
    if not rows:
        return []
    tag = f" — {PROVISIONAL}" if prov else ""
    return [f"## Piglet arms{tag}", "", "Each is one binary: a base Piglet plus the slots listed. The arms they are compared with are in the arm table above.", "",
            "| arm | what it is | slots | binary size |", "|---|---|---|---|"] + rows + [""]


def provenance_section(runs, prov):
    """Every arm's pin, in full: exact version, the source or archive it came from, its checksums, and how it was built. A field the run did not record says so; nothing is rounded or shortened."""
    tag = f" — {PROVISIONAL}" if prov else ""
    out = [f"## Provenance{tag}", "", f"Pins of the arms exactly as the run recorded them (arms.lock sha256 `{runs[0].get('lock_sha256')}`). A third party who checks out the runner commit gets the same pins, "
           "and `buffon rerun` repeats a cell with them.", "", "| arm | exact version | source | checksums | build | manifest sha256 | executable sha256 |", "|---|---|---|---|---|---|---|"]
    seen = set()
    for r in runs:
        for a, i in sorted(r["arms"].items()):
            if a.startswith("_") or a in seen or a.endswith("-b"):
                continue
            seen.add(a)
            source = i.get("source_url") or (f"{i['package']}@{i.get('version')}" if i.get("package") else None) or (f"git {i['commit']}" if i.get("commit") else None) or "not recorded"
            sums = [f"{k} `{i[k]}`" for k in ("artifact_sha256", "integrity", "package_lock_sha256", "tree") if i.get(k)]
            build = "; ".join(x for x in (i.get("build"), f"toolchain {i['toolchain']}" if i.get("toolchain") else "", f"node {i['node']}" if i.get("node") else "", i.get("platform")) if x) or (i.get("install_method") or "not recorded")
            out.append(f"| {a} | {i.get('version')} | {str(source).replace('|', '/')} | {'<br>'.join(sums) or 'not recorded'} | {build.replace('|', '/')} | `{i.get('manifest_sha256')}` | `{i.get('executable_sha256')}` |")
    return out + [""]


def environment_section(runs, facts, prov):
    tag = f" — {PROVISIONAL}" if prov else ""
    out = [f"## Arms and environment{tag}", "", "| arm | version | version line | executable sha256 | footprint | install | licence |", "|---|---|---|---|---|---|---|"]
    seen = set()
    for r in runs:
        for a, i in sorted(r["arms"].items()):
            if a.startswith("_") or a in seen or a.endswith("-b"):
                continue
            seen.add(a)
            fp = i.get("footprint") or {}
            size = f"{fp['bytes'] / 1e6:.1f} MB" + (f" + {fp['runtime']} {fp['runtime_bytes'] / 1e6:.0f} MB" if fp.get("runtime") and fp.get("runtime_bytes") else "") if fp else "n/a"
            out.append(f"| {a} | {i.get('version')} | {i.get('version_line')} | `{(i.get('executable_sha256') or '')[:16]}` | {size} | {i.get('install_method')} "
                       f"({(i.get('source_url') or i.get('commit') or i.get('package') or '')[:60]}) | {i.get('licence')} |")
    for a, text in sorted(cellmath.caveats_of(runs).items()):
        out += ["", f"**{a}:** {text}"]
    out += ["", "A/A copies run the same executable as their original (same sha256), installed as their own copy of the install tree."]
    built = sorted({a for r in runs for a, i in r["arms"].items() if not a.startswith("_") and not a.endswith("-b") and i.get("commit")})
    if built:
        out += ["", "Built from source at a pinned commit: " + ", ".join(f"`{a}`" for a in built) + ". A third party can rebuild such an arm only when its commit is public; the pinned commit of `pig-tip` is a merge on a private integration branch, so its result "
                "needs an independent reproduction before it is final (docs/DESIGN.md section 10)."]
    out.append("")
    for i, (r, f) in enumerate(zip(runs, facts), 1):
        out += [f"### Run {i} facts", "", "| field | value |", "|---|---|"]
        for k in ("cpu_model", "logical_cpus", "pinned_cpus", "mock_cpus", "governors", "fixed_clock", "smt_active", "cpus_allowed", "container", "node", "pod", "kernel", "memory_gib",
                  "idle_before", "idle_after", "load_before", "load_after", "throttled_usec", "cpumon", "go", "node_js", "python"):
            if k in f:
                out.append(f"| {k} | {json.dumps(f[k]) if not isinstance(f[k], str) else f[k]} |")
        iso = r.get("isolation") or {}
        if iso:
            out += ["", "Variables each harness was started with beyond the host's environment (the throwaway root is `<work>`); credential-looking and proxy variables of the host are removed:", ""]
            for a in sorted(iso):
                v = iso[a]
                out.append(f"- **{a}**: " + ", ".join(f"`{k}={val}`" for k, val in v["set"].items() if k not in ("NO_COLOR", "TERM", "NO_PROXY", "no_proxy")))
        out.append("")
    return out + runtime_settings_section(runs)


def runtime_settings_section(runs):
    """Each arm's runtime tuning (docs/METHODOLOGY.md section 15): what its manifest sets, and the known variables left at the harness's own default. Buffon sets none itself."""
    arms = {}
    for r in runs:
        for a, i in r["arms"].items():
            if isinstance(i, dict) and not a.startswith("_") and not a.endswith("-b") and i.get("runtime_settings"):
                arms[a] = i["runtime_settings"]
    if not arms:
        return []
    out = ["### Runtime settings", "", "Buffon pins CPUs but sets no runtime tuning of its own. An arm runs at its harness's shipped default except for the variables its manifest sets:", "",
           "| arm | set by the manifest | left at the harness default |", "|---|---|---|"]
    for a in sorted(arms):
        rs = arms[a]
        out.append(f"| {a} | {', '.join(f'`{k}={v}`' for k, v in rs['env'].items()) or 'none'} | {', '.join(rs['left_default']) or 'none'} |")
    divs = {a: i["divergences"] for r in runs for a, i in r["arms"].items() if isinstance(i, dict) and not a.startswith("_") and not a.endswith("-b") and i.get("divergences")}
    if divs:
        out += ["", "### Declared divergences", "", "Where an arm does different work by its own account, its median is shown and not compared (no ratio, no grade):", "", "| arm | workloads | metrics | reason | source |", "|---|---|---|---|---|"]
        for a in sorted(divs):
            for d in divs[a]:
                out.append(f"| {a} | {', '.join(f'`{g}`' for g in d['workloads'])} | {', '.join(f'`{g}`' for g in d.get('metrics') or []) or 'all'} | {d['reason']} | {d['source']} |")
    return out + [""]


def csv_rows(data, runs):
    yield ["scenario", "api", "metric", "kind", "unit", "arm", "n", "median", "p90", "min", "max", "ratio_to_reference", "ci_low", "ci_high", "floor", "verdict", "cell_id", "rerun", "label"]
    label = PROVISIONAL if provisional(runs)[0] else "quiet-dedicated"
    for c in data["cells"]:
        for arm, vals in c.values.items():
            xs = list(vals.values())
            s = stats.summarize(xs)
            comp = c.comparisons.get(arm)
            yield [c.scenario, c.api, c.metric, *metricslib.describe(c.metric), arm, s["n"], s["median"], s["p90"], s["min"], s["max"], comp.ratio if comp and not comp.not_compared else "", comp.ci[0] if comp and not comp.not_compared else "", comp.ci[1] if comp and not comp.not_compared else "",
                   comp.floor if comp and not comp.not_compared else "", comp.verdict if comp else "", (data.get("cell_ids") or {}).get((c.scenario, c.api, c.metric), ""),
                   cellidlib.rerun_command((data.get("cell_ids") or {}).get((c.scenario, c.api, c.metric), "")) if (data.get("cell_ids") or {}).get((c.scenario, c.api, c.metric)) else "", label]


def faithfulness_docs(paths):
    from ..faithfulness import report as faithreport
    return faithreport.load(list(paths)) if paths else []


def grade_section(graded):
    """The leaderboard as a section of report.md (leaderboard.md and report-card.md carry the full tables)."""
    return [("#" + line if line.startswith("#") else line) for line in grade_render.leaderboard(graded)]


def health_of(dirs, reference=None, seed=20261011):
    """The run notes of run directories, recomputed from their raw data (what `buffon verify` and CI do)."""
    runs, facts = load(dirs)
    data = cellmath.build(runs, reference, seed)
    return healthlib.assess(runs, facts, data, noiselib.build(runs, facts, data))


def html_view(data, graded, prov, reasons, health, runs, title, footer):
    """The plain data behind the designed report.html: the same strings report.md prints, grouped by family. cards.py draws it and computes nothing."""
    ref = data["reference"]
    families = {f["id"]: {"id": f["id"], "title": f["title"], "rows": []} for f in gradelib.METHOD["family"]}
    families["other"] = {"id": "other", "title": "Cells the grade does not score", "rows": []}
    arms = set()
    for c in data["cells"]:
        spec = gradelib.spec_of(c.scenario, c.metric)
        kind, unit = metricslib.describe(c.metric)
        for arm, comp in sorted(c.comparisons.items()):
            cv, iqr, outliers = noiselib.cell_columns(c, ref, arm)
            cell_id = (data.get("cell_ids") or {}).get((c.scenario, c.api, c.metric), "")
            arms.add(arm)
            families[spec[0] if spec else "other"]["rows"].append({
                "arm": arm, "workload": c.scenario, "api": short_api(c.api), "metric": c.metric, "kind": kind, "unit": unit, "n": comp.n, "ref_median": fmt(comp.ref_median),
                "arm_median": fmt(comp.arm_median), "ratio": ratio_text(comp), "floor": floor_pct(comp.floor), "mde": pct(c.mde), "cv": cv, "iqr": iqr, "outliers": outliers,
                "verdict": comp.verdict, "cell_id": cell_id, "rerun": cellidlib.rerun_command(cell_id) if cell_id else ""})
    grade = []
    for e in (graded or {}).get("entries", []):
        grade.append({"label": e["label"], "relation": e.get("relation"), "overall": e["overall"], "letter": e["letter"], "faithfulness": e["faithfulness"], "coverage": e["coverage"],
                      "rank": e.get("rank"), "no_score_reason": e.get("no_score_reason"), "table": e["table"], "table_title": grade_render.TITLES.get(e["table"], e["table"])})
    shown = [f for f in families.values() if f["rows"]]
    return {"title": title, "provisional": prov, "reasons": list(reasons), "notes": health.get("notes"), "reference": ref,
            "method": (graded or {}).get("method"), "faithfulness_floor": gradelib.METHOD["method"]["faithfulness_floor"], "grade": grade, "families": shown,
            "stats": [("runs", len(runs)), ("arms compared", len(arms)), ("families", len(shown)), ("comparisons", sum(len(f["rows"]) for f in shown))], "footer": footer}


def render(dirs, out_dir=None, reference=None, seed=20261011, drop_flagged=False, external_results=(), external_suites=(), faithfulness=(), faithfulness_given=None):
    """`faithfulness_given` is a list of faithfulness documents used instead of reading `faithfulness` directories (buffon verify regenerates a report from the values it recorded)."""
    runs, facts = load(dirs)
    used, dropped = noiselib.drop_flagged(runs) if drop_flagged else (runs, [])
    data = cellmath.build(used, reference, seed)
    data["cell_ids"] = cell_ids(data, [run_id_of(d) for d in dirs])
    data["versions"] = {a: i.get("version") for r in runs for a, i in r["arms"].items() if not a.startswith("_") and i.get("version")}
    noise = noiselib.build(runs, facts, data)
    noise["dropped"] = dropped
    noise["sensitivity"] = None if drop_flagged else noiselib.sensitivity(runs, data, reference, seed)
    health = healthlib.assess(runs, facts, data, noise)
    prov, reasons = provisional(runs)
    tag = f" — {PROVISIONAL}" if prov else ""
    lines = header(runs, facts, prov, reasons, data)
    from .. import trust as trustlib
    trust = trustlib.of_runs(used)   # from the raw data alone, so `buffon verify` regenerates the same report; a reproduction (reproduction.json) lifts Dedicated to Verified in the results index and `buffon up`
    lines[2:2] = [f"**Trust: {trust['badge']}** (host class {trust['host_class']}). " + ("; ".join(trust["reasons"][:4]) if trust["reasons"] else "Nothing counts against these numbers.")
                  + f" Every measurement is recorded and shown whatever the label. Headline CPU metric: {trust['headline']}.", "", healthlib.badge(health) + " (usual ranges: docs/HEALTH.md)", ""]
    lines += [""] + healthlib.lines(health, tag)
    fdocs = faithfulness_given if faithfulness_given is not None else faithfulness_docs(faithfulness)
    grade_in = grade_inputs.build(data, used, health, prov, reasons, reliability_verdicts(data), grade_inputs.faithfulness_scores(fdocs), correctness=grade_inputs.correctness_failures(fdocs))
    grade_in["trust"] = trust
    graded = gradelib.grade(grade_in, seed=seed) if grade_in["arms"] or data["cells"] else None
    if graded:
        lines += grade_section(graded) + [""]
    races = raceslib.build(used, data)
    if data["cells"]:
        lines += summary_table(data, prov, runs) + [""]
        lines += raceslib.lines(races, tag)
        for a in data["base"]:
            if a != data["reference"]:
                lines += arm_section(data, a, prov)
        lines += version_section(data, prov) + floor_section(data, prov) + rerun_section(data, prov)
    lines += noiselib.lines(noise, tag)
    lines += soak_section(data, prov) + reliability_section(data, prov) + failure_section(runs, prov) + excluded_section(prov) + provenance_section(runs, prov) + environment_section(runs, facts, prov) + piglet_section(runs, prov)
    if external_results or external_suites:   # their own sections, after everything Buffon measured; nothing above reads them
        from ..external import results as extresults, runner as extrunner
        lines += extresults.section(list(external_results)) + extrunner.section(list(external_suites))
    lines += [f"---", f"*{PROVISIONAL if prov else 'Quiet dedicated hardware'}: generated from {len(runs)} run director{'y' if len(runs) == 1 else 'ies'} by `buffon report`; {health['summary']}; the raw samples are in each directory's raw.json. "
                      f"The same data as report.html, report.json, summary.csv, rounds.csv, noise.csv and telemetry.csv.*"]
    out_dir = out_dir or (dirs[0] if len(dirs) == 1 else ".")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(out_dir, "summary.csv"), "w", newline="") as f:
        csv.writer(f).writerows(csv_rows(data, runs))
    summary = {"trust": trust, "provisional": prov, "reasons": reasons, "reference": data["reference"], "arms": data["base"], "health": health,
               "noise": {"by_metric": noise["by_metric"], "runs": noise["views"], "discarded": noise["discarded"], "dropped": noise["dropped"], "sensitivity": noise["sensitivity"]},
               "cells": [{"id": data["cell_ids"][(c.scenario, c.api, c.metric)], "rerun": cellidlib.rerun_command(data["cell_ids"][(c.scenario, c.api, c.metric)]), "scenario": c.scenario, "api": c.api, "metric": c.metric,
                          "kind": metricslib.describe(c.metric)[0], "unit": metricslib.describe(c.metric)[1], "mde": None if c.mde != c.mde else c.mde, "aa": {a: (None if f is None else f) for a, (f, _) in c.aa.items()},
                          "comparisons": {a: {"ratio": None if x.not_compared else x.ratio, "ci": None if x.not_compared else list(x.ci), "floor": None if x.floor != x.floor else x.floor, "p": None if x.p != x.p else x.p,
                                              "p_holm": None if x.p_holm != x.p_holm else x.p_holm, "verdict": x.verdict, "n": x.n, "arm_median": x.arm_median, "not_compared": x.not_compared or None,
                                              "equivalence": None if x.not_compared else x.equivalence}
                                          for a, x in c.comparisons.items()}} for c in data["cells"]]}
    summary["grade_inputs"] = grade_in
    summary["races"] = races
    if graded:
        grade_render.write_all(graded, out_dir)
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(summary, f, indent=1, default=lambda x: None if isinstance(x, float) and x != x else x)
    footer = (f"Generated from {len(runs)} run director{'y' if len(runs) == 1 else 'ies'} by `buffon report`; every number is computed from raw.json, and `buffon verify` regenerates this report "
              "to check that none was edited. Rerun any cell with the command beside it.").replace("`", "")
    view = html_view(data, graded, prov, reasons, health, runs, f"buffon report{tag}", footer)
    extras.write_all(out_dir, used, data, noise, health, lines, f"buffon report{tag}", all_runs=runs, view=view)
    return os.path.join(out_dir, "report.md")


def main(args):
    path = render(args.dirs, args.out, args.reference, drop_flagged=getattr(args, "drop_flagged", False), external_results=args.external_results or (), external_suites=args.external_suites or (), faithfulness=getattr(args, "faithfulness", None) or ())
    print(f"buffon: wrote {path}")
    return 0
