# SPDX-License-Identifier: Apache-2.0
"""`buffon dashboard RUN_DIR... --out site/`: the static results site.

One page (index.html) with an app (assets/app.js) that draws every view from one data file (data/site.js). No server and no build step to view it: it
opens from the folder (file://) as well as from GitHub Pages, and every view has its own link (index.html#/?m=...&h=...&sort=...).

Every number in data/site.js is the report's or a median and its interval from the run's own rounds (model.py); the formulas are set by KaTeX here, at build
time, so the page carries no math script. The site holds its own copy of everything it links: the report files under data/, the repository documents it points
at as pages of the app, and each run directory's raw.json, facts.json, host.json, MANIFEST.sha256 and logs under runs/<run id>/."""
import hashlib
import json
import os
import re
import shutil
import tomllib
from fnmatch import fnmatchcase
from urllib.parse import urlsplit

from ..mock import server as mockserver
from ..workloads import overhead
from . import benchmarks, external_site, formulas as fx, glossary, markdown, mathtex, model, plans, profiles_check, scale as scalelib

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs")
PROFILES = os.path.join(os.path.dirname(os.path.dirname(HERE)), "profiles")
MARKER = ".buffon-dashboard"
RUN_FILES = ("raw.json", "facts.json", "host.json", "MANIFEST.sha256", "promotion.json", "health.json")
OLD_LOOK = ("report.html", "leaderboard.html", "leaderboard.md", "report-card.html", "report-card.md", "grade.json", "plots")
REPORT_FILES = ("report.md", "report.json", "summary.csv", "rounds.csv", "telemetry.csv", "noise.csv", "health.json")
# A metric's name in plain words. A large-write metric starts with kb50_ or kb200_ (the file's size). A streaming metric starts with n_ (an answer of N tokens) or n10_ (an answer ten times longer): ANSWER says which.
METRIC_WORDS = {"cpu_ms": "CPU time", "wall_ms": "time", "instructions": "CPU instructions", "cycles": "CPU cycles", "peak_rss_mib": "peak memory", "rss_mib": "memory",
                "ready_rss_mib": "memory when ready", "pss_mib": "memory (PSS)", "ready_pss_mib": "memory when ready (PSS)", "peak_mem_mib": "peak memory, all processes",
                "first_request_ms": "time to the first request", "first_request_cpu_ms": "CPU time to the first request", "ready_ms": "time until ready", "ready_cpu_ms": "CPU time until ready",
                "turn_wall_ms": "time per turn", "turn_cpu_ms": "CPU time per turn", "turn_cpu_mean_ms": "average CPU time per turn", "turn_harness_added_ms": "time the harness adds per turn",
                "turn_turn_gap_ms": "gap between turns", "turn_gap_ms": "gap between tool calls", "teardown_ms": "time to stop", "request_bytes": "bytes sent in requests", "requests": "requests sent", "request_bytes_per_turn": "request bytes per turn", "side_requests": "side requests",
                "first_request_bytes": "size of the first request",
                "session_growth_bytes": "growth of the session file", "extensions_ready_cpu_ms": "CPU time to load the extensions", "call_to_result_ms": "time from the first byte of the tool call to its result",
                "after_stream_ms": "time from the end of the tool call to its result"}
ANSWER = {"n": "short answer", "n10": "answer 10 times longer"}

FIRST = ("overhead/version", "overhead/print", "overhead/print-tools", "overhead/rpc", "overhead/pty")
LENS_RANK = {"cpu": 0, "wall": 1, "memory": 2, "size": 3, "wire": 4, "other": 5}

# How one number is made: (title, one sentence, [more], [(formula label, formula)]). Each step opens to its detail; docs/METHODOLOGY.md has the rest.
METHOD_STEPS = [
    ("Pinned build", "Each harness is one exact version, checked against a checksum.",
     ["A package comes from its lockfile. A source build comes from one commit with a pinned toolchain.", "The runner checks that the program did not change during the run, and every self-update is off."], []),
    ("Its own empty home", "Each run starts in a new, empty home folder.",
     ["No file from an earlier run is in it. The run records what the folder held before and after, for every sample.", "The runner removes the variables from your shell that a harness reads."], []),
    ("The same scripted model", "Every harness talks to the same scripted model on the same machine.",
     ["The model answers at once, with no network, and gives the same answer each time. So a number describes the harness and not a model.",
      "It also leaves out the network time and the model time that a real model adds."], []),
    ("Rounds in turn, after a warm-up", "The harnesses take turns in rounds, and the order shifts each round. The first round is a warm-up and is dropped.",
     ["A round is one sample of every harness. A slow moment on the machine then affects every harness in that round.", "The warm-up round fills caches and does first-start work, so those costs do not count."], []),
    ("Median and 95% interval", "A cell is the median of the measured rounds. A ratio to a baseline comes with a 95% interval from resampling the rounds.",
     ["The median is the middle value, so a few slow rounds do not move it much.", "A ratio is the median of the harness divided by the median of the baseline, over the rounds both ran. The interval is the middle 95% of the ratios of many resampled sets of those rounds.",
      "Where a metric has an equivalence margin (workloads/margins.toml), the measurement page also says whether the ratio is shown to be within that margin of 1. The test uses the 90% interval of the ratio, found from the same paired rounds. The ratio is within ±m% only when the whole 90% interval is inside 1 ± m%. A wide interval that crosses the edge says \"not shown to be within\". It does not say the two differ.",
      "A harness that did different work in a workload (its manifest has a divergence entry) shows its own median there and the label \"different work: not compared\". It has no ratio, no interval and no p-value for that cell. The reason is on the measurement page."],
     [("Median", fx.MEDIAN), ("Ratio", fx.RATIO), ("Interval", fx.INTERVAL)]),
    ("A copy of itself", "Each harness also runs against an identical copy of itself. The gap between the copies is the noise floor.",
     ["A difference smaller than the noise floor can be noise. A measurement page shows the floor of the harness and of the baseline."], [("Noise floor", fx.FLOOR)]),
]
METHOD_LINKS = ("METHODOLOGY", "WHAT-WE-MEASURE", "LIMITATIONS", "HEALTH")
# The repository documents the site carries as pages of the app (#/doc/<name>): (name, source path under the repository, title, what it is for)
DOC_PAGES = [("README", "README.md", "About Buffon", "What Buffon is, how to run it, and why it has that name."),
             ("CONTRIBUTING", "CONTRIBUTING.md", "Contributing", "How to add a harness, a benchmark or a fix."),
             ("SUBMITTING", "docs/SUBMITTING.md", "Submitting and reproducing results", "How a run becomes a published result, and how to reproduce one."),
             ("METHODOLOGY", "docs/METHODOLOGY.md", "Methodology", "How every number is made."),
             ("WHAT-WE-MEASURE", "docs/WHAT-WE-MEASURE.md", "What we measure", "What each benchmark measures and where it stops being informative."),
             ("LIMITATIONS", "docs/LIMITATIONS.md", "Limitations", "What a number cannot tell you."),
             ("HEALTH", "docs/HEALTH.md", "Run notes", "What each run-health check measures and its usual range."),
             ("GETTING-STARTED", "docs/GETTING-STARTED.md", "Getting started", "From a fresh clone to your own run and site."),
             ("RAW-FORMAT", "docs/RAW-FORMAT.md", "Raw format", "The files of a run and every field in them."),
             ("EXTERNAL", "docs/EXTERNAL.md", "External suites and results", "How other projects' benchmarks are run or imported, and why they are kept apart."),
             ("DURABLE", "docs/design/DURABLE.md", "The durable family: the plan", "What the Durable section will measure, on which runtimes, and how it is kept fair.")]


# What a meter cannot do (docs/METHODOLOGY.md, "Measurement caveats by platform"). Shown on the Runs page and on every cell it touches.
LIVE_CPU = ("ready_cpu_ms", "turn_cpu_ms", "first_request_cpu_ms", "extensions_ready_cpu_ms")
CAVEATS = {
    "sampled-instructions": "Instructions here were sampled, not counted (macOS, perf_scope \"sampled\"). The meter reads each process about every 0.1 s. It loses the last part "
                            "of a process that stops, so the count is low, more so for short processes. Use the CPU time of this task instead.",
    "rusage-live": "This CPU value was read while the harness ran, with the rusage meter (macOS, or Linux without a cgroup). It counts only the processes that run at that "
                   "moment. The CPU time of child processes that already stopped is missing, so the value can be low.",
}


def caveats_of(metric, run):
    """The caveats that apply to one cell of one run, as keys of CAVEATS."""
    out = []
    if ("instructions" in metric or "cycles" in metric) and "sampled" in run.get("perf_scopes", []):
        out.append("sampled-instructions")
    if "rusage" in run.get("meters", []) and (metric in LIVE_CPU or ("_per_1k_tokens" in metric and "cpu_ms" in metric)):
        out.append("rusage-live")
    return out


class DashboardError(ValueError):
    pass


# What each project says about itself, in profiles/<project>.toml: kept outside arms/ because arms.lock hashes every file of an arm directory, and a profile must not change a
# measurement's provenance. The site shows the words verbatim, each with the page it came from and the day it was read.
PROFILE_REQUIRED = ("project", "harnesses", "maker", "maker_url", "tagline", "tagline_source", "retrieved", "licence")
PROFILE_OPTIONAL = ("licence_note", "readme_url", "readme_ref", "readme_title", "readme_head", "logo", "logo_source", "logo_sha256", "logo_alt",
                    "mark", "mark_source", "mark_ref", "mark_sha256", "mark_crop", "mark_bg", "mark_alt", "mark_note", "monogram")
PROFILE_LINKS = ("home", "repo", "docs", "releases", "changelog", "issues", "licence", "benchmarks")
PROFILE_README = ("readme_url", "readme_ref", "readme_title", "readme_head")   # all or none, with `retrieved`: the head of the project's own README at a pinned ref
PROFILE_LOGO = ("logo", "logo_source", "logo_sha256")                           # all or none: the README's wide picture, for the harness page; the file is in profiles/assets and its hash is checked at every build
PROFILE_MARK = ("mark", "mark_source", "mark_ref", "mark_sha256")               # all or none: the square mark of the card, the same tile for every project; a cropped one also has mark_crop
MARK_PX = 128                                                                  # a cropped mark is a PNG of this many pixels on a side
PROFILE_ASSETS = os.path.join(PROFILES, "assets")
MAX_QUOTES, MAX_QUOTE_WORDS, MAX_README_PARAGRAPHS = 3, 40, 2


def check_profile(data, name, assets=PROFILE_ASSETS):
    """The problems of one parsed profile, as plain sentences: a missing key, a URL that is not https, more than three quotes, a quote of more than 40 words, a README head or a logo
    that breaks its rules (a moving ref, more than two paragraphs, a logo file that is missing, changed, too large or not clean)."""
    bad = []
    for key in PROFILE_REQUIRED:
        if not data.get(key):
            bad.append(f"{name}: missing {key}")
    unknown = sorted(set(data) - set(PROFILE_REQUIRED) - set(PROFILE_OPTIONAL) - {"links", "quotes"})
    bad += [f"{name}: unknown key {k}" for k in unknown]
    if not (isinstance(data.get("harnesses"), list) and all(isinstance(h, str) and h for h in data.get("harnesses") or [])):
        bad.append(f"{name}: harnesses must be a list of arm ids")
    for key in ("maker_url", "tagline_source"):
        if data.get(key) and not str(data[key]).startswith("https://"):
            bad.append(f"{name}: {key} is not an https URL")
    links = data.get("links") or {}
    for key, url in links.items():
        if key not in PROFILE_LINKS:
            bad.append(f"{name}: unknown link {key}")
        elif not str(url).startswith("https://"):
            bad.append(f"{name}: link {key} is not an https URL")
    quotes = data.get("quotes") or []
    if len(quotes) > MAX_QUOTES:
        bad.append(f"{name}: {len(quotes)} quotes, at most {MAX_QUOTES}")
    for i, q in enumerate(quotes, 1):
        for key in ("text", "source", "about"):
            if not q.get(key):
                bad.append(f"{name}: quote {i} has no {key}")
        if len(str(q.get("text", "")).split()) > MAX_QUOTE_WORDS:
            bad.append(f"{name}: quote {i} has more than {MAX_QUOTE_WORDS} words")
        if q.get("source") and not str(q["source"]).startswith("https://"):
            bad.append(f"{name}: quote {i} source is not an https URL")
    bad += check_readme(data, name) + check_logo(data, name, assets) + check_mark(data, name, assets)
    return bad


def check_readme(data, name):
    have = [k for k in PROFILE_README if data.get(k)]
    if 0 < len(have) < len(PROFILE_README):
        return [f"{name}: {', '.join(PROFILE_README)} go together, missing {', '.join(k for k in PROFILE_README if k not in have)}"]
    if not have:
        return []
    bad = []
    if not str(data["readme_url"]).startswith("https://"):
        bad.append(f"{name}: readme_url is not an https URL")
    if not isinstance(data["readme_ref"], str) or profiles_check.branch_name(data["readme_ref"]):
        bad.append(f"{name}: readme_ref {data['readme_ref']} is a branch, pin a tag or a commit")
    head = data["readme_head"]
    if not (isinstance(head, list) and 1 <= len(head) <= MAX_README_PARAGRAPHS and all(isinstance(p, str) and p.strip() for p in head)):
        bad.append(f"{name}: readme_head must be 1 to {MAX_README_PARAGRAPHS} non-empty paragraphs")
    if not isinstance(data["readme_title"], str):
        bad.append(f"{name}: readme_title must be text")
    return bad


def check_logo(data, name, assets):
    have = [k for k in PROFILE_LOGO if data.get(k)]
    if 0 < len(have) < len(PROFILE_LOGO):
        return [f"{name}: {', '.join(PROFILE_LOGO)} go together, missing {', '.join(k for k in PROFILE_LOGO if k not in have)}"]
    if not have:
        return []
    file, bad = str(data["logo"]), []
    if not str(data["logo_source"]).startswith("https://"):
        bad.append(f"{name}: logo_source is not an https URL")
    if os.path.basename(file) != file or os.path.splitext(file)[1] not in (".svg", ".png", ".webp"):
        return bad + [f"{name}: logo {file} must be a .svg, .png or .webp file name in profiles/assets"]
    path = os.path.join(assets, file)
    if not os.path.isfile(path):
        return bad + [f"{name}: logo file {file} is missing from profiles/assets"]
    with open(path, "rb") as f:
        raw = f.read()
    if hashlib.sha256(raw).hexdigest() != data["logo_sha256"]:
        bad.append(f"{name}: logo file {file} does not match its logo_sha256")
    found = profiles_check.svg_problems(raw) if file.endswith(".svg") else profiles_check.raster_problems(raw)
    return bad + [f"{name}: logo file {file}: {p}" for p in found]


def check_mark(data, name, assets):
    """The problems of a profile's mark: the four keys go together; the file is in profiles/assets with the hash the profile names and is a clean SVG or a PNG or WebP within the caps; a crop is four
    whole numbers of a square and gives a 128 px PNG. A source that is not an https URL names a file the owner supplied, and then mark_note says so: nothing is fetched for it, the hash is the pin."""
    have = [k for k in PROFILE_MARK if data.get(k)]
    extra = [k for k in ("mark_crop", "mark_bg", "mark_alt", "mark_note") if data.get(k)]
    if data.get("monogram") and (not isinstance(data["monogram"], str) or not 1 <= len(data["monogram"]) <= 3):
        return [f"{name}: monogram must be 1 to 3 characters"]
    if not have:
        return [f"{name}: {k} without a mark" for k in extra]
    if len(have) < len(PROFILE_MARK):
        return [f"{name}: {', '.join(PROFILE_MARK)} go together, missing {', '.join(k for k in PROFILE_MARK if k not in have)}"]
    file, bad = str(data["mark"]), []
    if not str(data["mark_source"]).startswith("https://") and not data.get("mark_note"):
        bad.append(f"{name}: a mark_source that is not an https URL needs a mark_note that says who supplied the file")
    if data.get("mark_bg") and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(data["mark_bg"])):
        bad.append(f"{name}: mark_bg must be a #rrggbb colour")
    crop = data.get("mark_crop")
    if crop is not None and not (isinstance(crop, list) and len(crop) == 4 and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in crop) and crop[2] > 0 and crop[2] == crop[3]):
        bad.append(f"{name}: mark_crop must be [x, y, side, side] in pixels of the source")
    if os.path.basename(file) != file or os.path.splitext(file)[1] not in (".svg", ".png", ".webp"):
        return bad + [f"{name}: mark {file} must be a .svg, .png or .webp file name in profiles/assets"]
    path = os.path.join(assets, file)
    if not os.path.isfile(path):
        return bad + [f"{name}: mark file {file} is missing from profiles/assets"]
    with open(path, "rb") as f:
        raw = f.read()
    if hashlib.sha256(raw).hexdigest() != data["mark_sha256"]:
        bad.append(f"{name}: mark file {file} does not match its mark_sha256")
    found = profiles_check.svg_problems(raw) if file.endswith(".svg") else profiles_check.raster_problems(raw)
    bad += [f"{name}: mark file {file}: {p}" for p in found]
    if crop is not None and not file.endswith(".svg") and profiles_check.raster_size(raw) != (MARK_PX, MARK_PX):
        bad.append(f"{name}: a cropped mark is a {MARK_PX} x {MARK_PX} px picture")
    return bad


def load_profiles(path=PROFILES):
    """[{slug, file, project, harnesses, maker, maker_url, tagline, tagline_source, retrieved, licence, licence_note, links, quotes, readme, logo, logo_source, mark, mark_source, mark_ref, mark_bg, mark_alt, mark_note, mark_pixel, monogram}] from every profiles/*.toml, in file order.
    readme is {url, ref, repo, title, head, retrieved} or None; logo (the README's wide picture) and mark (the square tile of the card) are the site-relative path of the copied file (assets/profiles/<file>) or None, each with its source.
    A profile that breaks the schema, or two that claim one harness, stops the build with every problem named. A missing folder is no profiles."""
    if not os.path.isdir(path):
        return []
    out, bad, seen = [], [], {}
    for name in sorted(os.listdir(path)):
        if not name.endswith(".toml"):
            continue
        with open(os.path.join(path, name), "rb") as f:
            try:
                data = tomllib.load(f)
            except tomllib.TOMLDecodeError as error:
                bad.append(f"{name}: {error}")
                continue
        problems = check_profile(data, name, os.path.join(path, "assets"))
        bad += problems
        if problems:
            continue
        for h in data["harnesses"]:
            if h in seen:
                bad.append(f"{name}: harness {h} is also in {seen[h]}")
            seen[h] = name
        keep = [k for k in PROFILE_REQUIRED + PROFILE_OPTIONAL if k not in PROFILE_README + PROFILE_LOGO + PROFILE_MARK + ("mark_crop", "mark_bg", "mark_alt", "mark_note")]
        readme = {"url": data["readme_url"], "ref": data["readme_ref"], "repo": profile_repo(data), "title": data["readme_title"], "head": list(data["readme_head"]), "retrieved": data["retrieved"]} if data.get("readme_url") else None
        out.append({**{k: data.get(k) for k in keep}, "slug": name[:-5], "file": f"profiles/{name}", "links": dict(data.get("links") or {}),
                    "quotes": [{k: q[k] for k in ("text", "source", "about")} for q in data.get("quotes") or []],
                    "readme": readme, "logo": f"assets/profiles/{data['logo']}" if data.get("logo") else None, "logo_source": data.get("logo_source"),
                    "mark": f"assets/profiles/{data['mark']}" if data.get("mark") else None, "mark_source": data.get("mark_source"), "mark_ref": data.get("mark_ref"), "mark_bg": data.get("mark_bg"),
                    "mark_alt": data.get("mark_alt"), "mark_note": data.get("mark_note"), "mark_pixel": bool(data.get("mark_crop"))})
    if bad:
        raise DashboardError("the profiles are not valid: " + "; ".join(bad))
    return out


def profile_repo(data):
    """owner/name from a profile's repository link ("" when it has none)."""
    path = urlsplit((data.get("links") or {}).get("repo", "")).path
    return re.sub(r"\.git$", "", path.strip("/"))


def copy_profile_logos(profiles, profiles_dir, out):
    """Each logo and mark of the profiles, as stored in profiles/assets, into <out>/assets/profiles/. The build checked its hash; nothing is fetched."""
    logos = [p[k] for p in profiles for k in ("logo", "mark") if p[k]]
    if not logos:
        return
    dest = os.path.join(out, "assets", "profiles")
    os.makedirs(dest, exist_ok=True)
    for logo in logos:
        shutil.copy(os.path.join(profiles_dir, "assets", os.path.basename(logo)), os.path.join(dest, os.path.basename(logo)))


def metric_word(metric):
    """A metric's name in plain words, from Buffon's naming rule (docs/RAW-FORMAT.md: names end in their unit). The exact name is on the measurement's page."""
    name, answer, per = metric, "", ""
    head = name.split("_", 1)[0]
    if head in ANSWER and "_" in name:
        name, answer = name.split("_", 1)[1], ANSWER[head]
    elif re.fullmatch(r"kb\d+", head) and "_" in name:   # large-write: a metric of the file of that many KB
        name, answer = name.split("_", 1)[1], f"{head[2:]} KB file"
    for suffix, word in (("_per_1k_tokens", " per 1,000 tokens"), ("_per_turn", " per turn")):
        if name.endswith(suffix):
            name, per = name[: -len(suffix)], word
    if name in METRIC_WORDS:
        base = METRIC_WORDS[name]
    else:
        base = name.replace("_", " ")
        for suffix, word in (("_cpu_ms", "CPU time"), ("_instructions", "CPU instructions"), ("_cycles", "CPU cycles"), ("_wall_ms", "time"), ("_rss_mib", "memory"),
                             ("_pss_mib", "memory (PSS)"), ("_mem_mib", "memory"), ("_mib", "memory"), ("_bytes", "size"), ("_ms", "time")):
            if name.endswith(suffix):
                base = f"{word}, {name[: -len(suffix)].replace('_', ' ')}"
                break
    return base + per + (f", {answer}" if answer else "")


def prepare(out):
    """An empty output directory, or one a previous build wrote (it carries the marker): anything else is refused rather than overwritten."""
    if os.path.exists(out) and os.listdir(out) and not os.path.exists(os.path.join(out, MARKER)):
        raise DashboardError(f"{out} is not empty and was not written by buffon dashboard: choose an empty directory")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    with open(os.path.join(out, MARKER), "w") as f:
        f.write("written by buffon dashboard; the whole directory is replaced on the next build\n")
    with open(os.path.join(out, ".nojekyll"), "w") as f:
        f.write("")


def copy_assets(out):
    assets = os.path.join(out, "assets")
    os.makedirs(os.path.join(assets, "katex", "fonts"))
    for name in ("app.css", "app.js", "favicon.svg"):
        shutil.copy(os.path.join(HERE, "assets", name), os.path.join(assets, name))
    with open(os.path.join(HERE, "vendor", "katex", "katex.min.css")) as f:
        css = f.read()
    css = re.sub(r',url\(fonts/[^)]+\.(?:woff|ttf)\) format\("(?:woff|truetype)"\)', "", css)   # only the woff2 files are shipped
    with open(os.path.join(assets, "katex", "katex.min.css"), "w") as f:
        f.write(css)
    shutil.copy(os.path.join(HERE, "vendor", "katex", "LICENSE"), os.path.join(assets, "katex", "LICENSE"))
    for name in os.listdir(os.path.join(HERE, "vendor", "katex", "fonts")):
        shutil.copy(os.path.join(HERE, "vendor", "katex", "fonts", name), os.path.join(assets, "katex", "fonts", name))


def copy_runs(out, runs):
    for r in runs:
        dest = os.path.join(out, "runs", r["id"])
        os.makedirs(dest, exist_ok=True)
        for name in r["files"]:
            shutil.copy(os.path.join(r["path"], name), os.path.join(dest, name))
        if r["logs"]:
            shutil.copytree(os.path.join(r["path"], "logs"), os.path.join(dest, "logs"))   # the app lists them itself (#/logs/<run id>): no page of another look


def workload_rank(scenario):
    """Where the workload sits: the order a person meets them (start-up, one prompt, tools, an editor session), then benchmarks.WORKLOADS in its own order."""
    if scenario in FIRST:
        return FIRST.index(scenario)
    for i, (pattern, *_rest) in enumerate(benchmarks.WORKLOADS):
        if fnmatchcase(scenario, pattern):
            return len(FIRST) + i
    return len(FIRST) + len(benchmarks.WORKLOADS)


def metric_about(metric, word, unit):
    """(sentence, KaTeX or None) for a metric: the one benchmarks.METRICS names, else a sentence made from its name and unit. A streaming metric gives its own sentence."""
    if metric in benchmarks.METRICS:
        return benchmarks.METRICS[metric]
    return f"The {word} of this workload, in {unit or 'its own unit'}.", None


def metric_catalog(cells, m):
    """[{key, ...}] one entry per (workload, metric), whatever the wire API, in the order a person meets them. `cells` maps each API to its cell slug."""
    out = {}
    for c in cells:
        e = out.get(c["key"])
        if e is None:
            word = c["metric_word"]
            about, tex = metric_about(c["metric"], word, c["unit"])
            w = benchmarks.workload_of(c["scenario"])
            e = out[c["key"]] = {"key": c["key"], "scenario": c["scenario"], "metric": c["metric"], "workload": c["workload"], "title": w["title"], "word": word, "unit": c["unit"],
                                 "lens": c["lens"], "family": c["family"], "about": about, "tex": m.tex(tex) if tex else None, "apis": [], "cells": {}}
        e["apis"].append(c["api_short"])
        e["cells"][c["api_short"]] = c["slug"]
    for e in out.values():
        e["apis"].sort()
    return sorted(out.values(), key=lambda e: (workload_rank(e["scenario"]), LENS_RANK.get(e["lens"], 9), e["metric"]))


def doc_data():
    """[{slug, title, about, html}] the repository documents the site carries, converted to the site's own components (markdown.py); the app draws them in its own frame
    (route #/doc/<slug>), so they have the header, the fonts, the colours and the light or dark choice of every other page. A document that is not in this checkout is left out.
    A link to another carried document becomes a route of the site, a link to anything else in the repository becomes plain text, and an in-page link keeps its place."""
    names = {n for n, *_ in DOC_PAGES}
    found = []
    for name, src, title, about in DOC_PAGES:
        path = os.path.join(os.path.dirname(DOCS), src)
        if not os.path.exists(path):
            continue

        def href(url, name=name):
            if url.startswith(("http:", "https:", "mailto:")):
                return url
            target, _, frag = url.partition("#")
            stem = os.path.basename(target)[:-3] if target.endswith(".md") else (name if not target else None)
            return ("#/about" if stem == "README" else f"#/doc/{stem}") + (f"?at={frag}" if frag else "") if stem in names else None

        with open(path, encoding="utf-8") as f:
            found.append({"slug": name, "title": title, "about": about, "html": markdown.convert(f.read(), href)})
    return found


def scale_data(site, m):
    """The swarm limits (the searches and the ladders of earlier runs) for the Scale page, with the definition of each metric of the two kinds, RPC and print (title, unit, which way is better, sentence, formula); the kinds with ten extensions use their kind's. None when no run holds a swarm sample."""
    if not site.get("scale"):
        return None
    metrics = {kind: [{"key": k, "title": t, "unit": u, "direction": d, "about": a, "tex": m.tex(tex) if tex else None} for k, t, u, d, a, tex in scalelib.metrics_for(kind)] for kind in scalelib.KINDS.values()}
    notes = {kind: {k: n for (kk, k), n in scalelib.NOTES.items() if kk == kind} for kind in scalelib.KINDS.values()}
    return {**site["scale"], "metrics": metrics, "notes": notes, "charts": {k: list(v) for k, v in scalelib.CHARTS.items()}, "causes": scalelib.CAUSE_WORDS}


def client_data(site, m, data_dir, docs, profiles=(), external=None):
    """Everything the app draws, in one JSON object. Formulas are placeholders here; Math.fill swaps in KaTeX's HTML."""
    texts = benchmarks.family_texts()
    used_fams = {c["family"] for c in site["cells"]}
    families = [{"id": f["id"], "title": f["title"], "name": benchmarks.NAMES.get(f["id"], f["id"]), "use": benchmarks.USE.get(f["id"], ""), "texts": texts.get(f["id"], {}),
                 "measured": f["id"] in used_fams} for f in site["families"]]
    if "other" in used_fams:
        families.append({"id": "other", "title": "Other cells", "name": benchmarks.NAMES["other"], "use": benchmarks.USE["other"], "texts": {}, "measured": True})
    cells, workloads = [], {}
    covered = {}
    for c in site["cells"]:
        covered.setdefault(c["workload"], set()).update(c["stats"])
    for c in site["cells"]:
        cell = {k: c[k] for k in ("id", "slug", "key", "scenario", "workload", "api", "api_short", "metric", "kind", "lens", "unit", "memory_kind", "family", "mde", "run", "rerun", "values", "stats", "na")}
        cell["metric_word"] = metric_word(c["metric"])
        run = next((r for r in site["runs"] if r["id"] == c["run"]), {})
        cell["caveats"] = [CAVEATS[k] for k in caveats_of(c["metric"], run)]
        cell["comparisons"] = {}
        for arm, comp in c["comparisons"].items():
            out = dict(comp)
            out["aa_floor"] = {who: v.get("floor_log") for who, v in comp["aa"].items()}
            cell["comparisons"][arm] = out
        cells.append(cell)
        if c["workload"] not in workloads:
            workloads[c["workload"]] = {"id": c["workload"], "scenario": c["scenario"], "family": c["family"], **benchmarks.workload_of(c["scenario"]),
                                        "covered": len(covered[c["workload"]]), "of": len(site["harnesses"])}
    catalog = metric_catalog(cells, m)
    of = {a: p["slug"] for p in profiles for a in p["harnesses"]}
    title = lambda scenario: benchmarks.workload_of(scenario)["title"]
    harnesses = [{**h, "profile": of.get(h["id"]), "cannot": [{**c, "title": title(c["scenario"])} for c in h["cannot"]],
                  "scope": {"measured": [{"scenario": s, "title": title(s)} for s in h["scope"]["measured"]], "not_measured": [{**n, "title": title(n["scenario"])} for n in h["scope"]["not_measured"]]}}
                 for h in site["harnesses"]]
    runs = []
    for r in site["runs"]:
        view = {k: v for k, v in r.items() if k != "path"}
        view["caveats"] = ([CAVEATS["sampled-instructions"]] if "sampled" in r["perf_scopes"] else []) + ([CAVEATS["rusage-live"]] if "rusage" in r["meters"] else [])
        runs.append(view)
    gloss = [{"slug": slug, "term": term, "text": text, "tex": m.tex(tex) if tex else None, "kind": "term", "shown": slug in glossary.SHOWN} for slug, term, text, tex in glossary.TERMS]
    gloss += [{"slug": glossary.acronym_slug(a), "term": a, "expands": exp, "text": text, "see": see, "kind": "abbr", "shown": glossary.acronym_slug(a) in glossary.SHOWN} for a, exp, text, see in glossary.ACRONYMS]
    steps = [{"title": t, "line": line, "more": more, "formulas": [{"name": n, "html": m.tex(tex)} for n, tex in eqs]} for t, line, more, eqs in METHOD_STEPS]
    data_files = [f for f in REPORT_FILES if os.path.exists(os.path.join(data_dir, f))]
    return {"meta": {"demo": site["demo"], "provisional": site["provisional"], "reasons": site["reasons"], "seed": site["seed"], "reference": site["reference"],
                     "data_files": data_files, "prompt": overhead.PROMPT, "reply": mockserver.REPLY},
            "harnesses": harnesses, "families": families, "metrics": catalog, "cells": cells, "workloads": workloads, "runs": runs, "profiles": list(profiles), "scale": scale_data(site, m), "faults": site["faults"], "external": external, "plan": plans.load(), "unmeasured": plans.unmeasured(profiles, {h["id"] for h in site["harnesses"]}),
            "glossary": gloss, "method": {"steps": steps, "links": list(METHOD_LINKS)}, "docs": docs,
            "tex": {"median": m.tex(fx.MEDIAN), "ratio": m.tex(fx.RATIO), "interval": m.tex(fx.INTERVAL), "floor": m.tex(fx.FLOOR)}}


SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Buffon</title><meta name="description" content="Benchmarks for coding agents built on Pi's use cases. It measures what each harness costs your machine.">
<script>try{var t=localStorage.getItem("buffon:theme");if(t)document.documentElement.dataset.theme=t;}catch(e){}</script>
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg"><link rel="stylesheet" href="assets/katex/katex.min.css"><link rel="stylesheet" href="assets/app.css"></head>
<body><div id="app"><noscript><p style="padding:24px">This dashboard needs JavaScript. The same numbers are in <a href="data/report.md">data/report.md</a> and <a href="data/report.json">data/report.json</a>.</p></noscript></div>
<div class="tip" id="tip" role="tooltip"></div>
<script src="data/site.js"></script><script src="assets/app.js"></script></body></html>
"""


def copy_external(out, copies):
    """The files of the external suites and results the section links, as the site's own copies under external/."""
    for src, dest in copies:
        path = os.path.join(out, dest)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy(src, path)


def build(dirs, out, reference_arm=None, faithfulness=(), seed=model.SEED, profiles_dir=PROFILES, external_suites=(), external_results=()):
    """`dirs` are Buffon's run directories; a directory among them that holds external-suite.json or external.json is an external one (the same as naming it in `external_suites` or `external_results`).
    External runs get their own section and are read by nothing else."""
    dirs, found_suites, found_results = external_site.split(dirs)
    suite_dirs, result_dirs = list(found_suites) + list(external_suites), list(found_results) + list(external_results)
    if not dirs:
        raise DashboardError("give at least one run directory")
    profiles = load_profiles(profiles_dir)   # first: a bad profile stops the build before the slow part
    prepare(out)
    data_dir = os.path.join(out, "data")
    site = model.build(dirs, data_dir, reference_arm, faithfulness, seed)
    try:
        external, external_copies = external_site.load(suite_dirs, result_dirs, profiles, [h["id"] for h in site["harnesses"]])
    except (OSError, ValueError, KeyError) as error:
        raise DashboardError(f"the external runs are not valid: {error}") from None
    for name in OLD_LOOK:   # the report's own pages and plots have another look, and the grade files are not shown: the site carries none of them
        path = os.path.join(data_dir, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.path.exists(path) and os.remove(path)
    m = mathtex.Math()
    data = client_data(site, m, data_dir, doc_data(), profiles, external)
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    rendered = m.render()
    text = re.sub(r"\\u0000MATH(\d+)\\u0000", lambda mm: json.dumps(rendered[int(mm.group(1))], ensure_ascii=False)[1:-1], text)
    with open(os.path.join(data_dir, "site.js"), "w", encoding="utf-8") as f:
        f.write("window.BUFFON=" + text.replace("</", "<\\/") + ";\n")
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(SHELL)
    copy_assets(out)
    copy_profile_logos(profiles, profiles_dir, out)
    copy_runs(out, site["runs"])
    copy_external(out, external_copies)
    return site, data


def main(args):
    try:
        site, data = build(args.dirs, args.out, args.reference, args.faithfulness or (), model.SEED, external_suites=args.external_suites or (), external_results=args.external_results or ())
    except (DashboardError, model.ModelError, mathtex.MathError) as error:
        print(f"buffon: {error}")
        return 2
    n = sum(len(c["comparisons"]) for c in data["cells"])
    print(f"buffon: wrote the dashboard to {args.out}: {len(data['harnesses'])} harnesses, {len(data['cells'])} cells, {n} comparisons"
          + (" (DEMO data: every view carries the banner)" if site["demo"] else "") + f"; open {os.path.join(args.out, 'index.html')}")
    return 0
