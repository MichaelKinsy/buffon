# SPDX-License-Identifier: Apache-2.0
"""The steps of `buffon up`: machine, site profile, harness install (side by side), measured runs (one at a time), evals, report and dashboard (side by side), summary.

Only measured samples need quiet; everything else runs in parallel. Every step prints one line with what it is doing and how long it is expected to take, and one with how long it took.
Finished runs are reused: a run directory is named by a hash of everything that decides its result, and a directory with a finished raw.json is not run again."""
import hashlib
import html
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .. import trust as trustlib
from .. import workloads as workloadlib
from ..arms import install, lock as locklib, manifest
from ..report import theme
from . import catalog, estimate, listing, machine, selection, tracks as trackslib

SPECIAL_FAMILIES = ("soak", "reliability")
QUIET_TIMEOUT_S = 10   # `buffon up` waits this long for a quiet host before a sample, then samples anyway and labels the run Noisy
FORWARD = ("settled", "calibration", "host class", "FAILED", "gave up", "cannot run", "refused", "isolation", "installing", "egress")


class UpError(Exception):
    pass


class Options:
    """What the command line adds to a selection: where things go, and switches that are not part of a saved selection."""

    def __init__(self, **kw):
        self.home = kw.get("home") or machine.home()
        self.open_browser = kw.get("open_browser", True)
        self.dedicated = kw.get("dedicated", False)
        self.require_class = kw.get("require_class")
        self.selection_file = kw.get("selection_file")
        self.program = kw.get("program", "python3 -m buffon")
        self.python = kw.get("python", sys.executable)
        self.refresh_probe = kw.get("refresh_probe", False)
        self.pin = kw.get("pin", True)
        self.rerun = kw.get("rerun", False)       # ignore finished runs
        self.dashboard = kw.get("dashboard", True)   # build the dashboard (needs Node); False: the report and a summary page only


class Reporter:
    """One line per step: `buffon up [3/6] installing 3 harnesses, expected 25 s` and then `... done in 21 s`."""

    def __init__(self, total, out=print):
        self.total, self.n, self.out, self.t0 = total, 0, out, None

    def start(self, what, expect=None):
        self.n += 1
        self.t0 = time.monotonic()
        self.out(f"buffon up [{self.n}/{self.total}] {what}" + (f" (expected {selection.format_duration(expect)})" if expect is not None else ""))

    def done(self, text=""):
        took = time.monotonic() - self.t0
        self.out(f"buffon up [{self.n}/{self.total}] done in {selection.format_duration(took)}" + (f": {text}" if text else ""))
        return took

    def note(self, text):
        self.out(f"buffon up       {text}")


# -- identity of a run ------------------------------------------------------------------------------------------------------------------------------

def run_key(group, arms, workloads, sel, reference, arm_objs, params=None):
    """A short hash of everything that decides a run's result: the group, the arms with their manifests, the workloads, the options and the lock."""
    doc = {"group": group, "arms": sorted((a, arm_objs[a].manifest_sha256) for a in arms), "workloads": list(workloads), "apis": sel.apis, "rounds": sel.rounds, "rounds_set": sel.rounds_set, "adaptive": sel.adaptive,
           "calibration_rounds": sel.calibration_rounds, "seed": sel.seed, "reference": reference, "isolation": sel.isolation, "memory_tier": sel.memory_tier_gib if sel.isolation == "container" else None, "params": params or {},
           "lock": locklib.lock_hash() if os.path.exists(locklib.LOCK_FILE) else None}
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:10]


def finished(run_dir):
    """True when the directory holds a complete raw.json of a run that measured something."""
    try:
        with open(os.path.join(run_dir, "raw.json")) as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return False
    return not raw.get("refused") and bool(raw.get("samples")) and not (raw.get("run") or {}).get("partial")


def groups(workload_ids, registry):
    """[(name, [ids])]: the sampled workloads in one run, the soak and the reliability workloads in another, so a failure late in a long one does not lose the short ones."""
    sampled = [w for w in workload_ids if registry[w].family not in SPECIAL_FAMILIES]
    special = [w for w in workload_ids if registry[w].family in SPECIAL_FAMILIES]
    return [(n, ids) for n, ids in (("measured", sampled), ("long", special)) if ids]


def recipe_groups(sel, tracks=None):
    """[(group name, [ids], params, recipe)]: each real-world recipe that carries parameters is its own run, so its parameters apply to its benchmarks alone."""
    tracks = tracks if tracks is not None else trackslib.load()
    by_id = {r["id"]: r for r in trackslib.recipes_of(tracks, "real-world")}
    return [(f"recipe-{rid}", list(by_id[rid]["uses"]), {**sel.params, **by_id[rid].get("params", {})}, by_id[rid]) for rid in sel.recipes if rid in by_id]


def resolve_isolation(sel, machine_record, site):
    """(isolation to pass to the run, a note or None). `auto` (the Pi family and real-world tracks) means a container when the machine has a runtime and the site pins CPUs; otherwise bare,
    said so, and the run's isolation stamp reads 'uncontained, not comparable'."""
    if sel.isolation != "auto":
        return sel.isolation, None
    if machine_record["container_runtime"] and site.local.cpus:
        return "container", f"each harness runs in its own {machine_record['container_runtime']} container with the same memory and CPU limits"
    why = "no docker or podman" if not machine_record["container_runtime"] else "no pinned CPUs to give a container (too few cores, or this platform cannot pin)"
    return "none", f"containers are the default for this track, but there is {why}: the harnesses run bare and the run is labelled uncontained"


# -- installing -------------------------------------------------------------------------------------------------------------------------------------

class LockedCache(install.Cache):
    """The download cache for threads: two arms that need the same file (the Node archive) fetch it once, the second waits and finds it."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._locks, self._guard = {}, threading.Lock()

    def get(self, url, sha256):
        with self._guard:
            lock = self._locks.setdefault(sha256, threading.Lock())
        with lock:
            return super().get(url, sha256)


def install_one(arm, paths, offline, cache):
    """Install one arm into a throwaway workspace (this fills the download and npm caches). Returns (ok, reason). Source-built arms are built by the run itself."""
    if arm.install_kind in ("source", "derive"):
        return True, "built at run time"
    try:
        with install.Workspace(cache, work_dir=paths["work"], npm_cache=paths["npm_cache"]) as ws:
            ws.install(arm)
            if arm.skip:
                return False, arm.skip
            return True, arm.version_line or "ok"
    except (install.InstallError, OSError) as error:
        return False, str(error).strip().splitlines()[0][:200]
    except Exception as error:   # a manifest or tool problem on one arm must not stop the others
        return False, f"{type(error).__name__}: {error}"[:200]


def install_all(arm_ids, arms, paths, offline, out):
    """Install every harness side by side. Returns ({id: reason} of the ones that failed, [ids that installed])."""
    cache = LockedCache(paths["cache"], offline=offline)
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(len(arm_ids), 6))) as pool:
        futures = {a: pool.submit(install_one, arms[a], paths, offline, cache) for a in arm_ids}
        for a, f in futures.items():
            results[a] = f.result()
    failed = {a: why for a, (ok, why) in results.items() if not ok}
    for a, (ok, why) in results.items():
        out(f"{'ok  ' if ok else 'FAIL'} {a}: {why}")
    return failed, [a for a, (ok, _) in results.items() if ok]


# -- running ----------------------------------------------------------------------------------------------------------------------------------------

def run_cmd(argv, log_path, out, forward=FORWARD):
    """Run a child process, keep its whole output in log_path, show the lines that matter and a sample counter. Returns the exit code."""
    samples = 0
    with open(log_path, "w") as log, subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
        for line in proc.stdout:
            log.write(line)
            log.flush()
            text = line.rstrip()
            if " round " in text and text.startswith("buffon: ") and "FAILED" not in text:
                samples += 1
                if samples % 25 == 0:
                    out(f"{samples} samples taken")
            elif any(k in text for k in forward):
                out(text.removeprefix("buffon: ")[:180])
        return proc.wait()


def run_argv(opts, paths, sel, arms, reference, workload_ids, out_dir, params=None, arm_objs=None):
    argv = [opts.python, "-m", "buffon", "run", "--site", paths["site_profile"], *workload_ids, "--arms", *arms, "--apis", *sel.apis, *(["--rounds", str(sel.rounds)] if sel.rounds_set else []),
            "--calibration-rounds", str(sel.calibration_rounds), "--reference", reference, "--seed", str(sel.seed), "--out", out_dir, "--cache-dir", paths["cache"],
            "--npm-cache", paths["npm_cache"], "--quiet-timeout", str(QUIET_TIMEOUT_S)]
    terms = selection.terms_of(arms, arm_objs if arm_objs is not None else manifest.load_all(), set(sel.accept_terms))
    if terms:
        argv += ["--accept-terms", ",".join(terms)]
    if sel.adaptive:
        argv.append("--adaptive")
    if sel.offline:
        argv.append("--offline")
    if sel.isolation:
        argv += ["--isolation", sel.isolation, "--memory-tier", str(sel.memory_tier_gib)]
    for k, v in sorted((params or {}).items()):
        argv += ["--param", f"{k}={json.dumps(v)}"]
    if opts.dedicated:
        argv += ["--host-claim", "A"]
    if opts.require_class:
        argv += ["--require-class", opts.require_class]
    return argv


# -- report and site --------------------------------------------------------------------------------------------------------------------------------

def headless(env=None, platform=None):
    """True when there is no display to open a browser on: Linux without X or Wayland, or an SSH session."""
    env = env if env is not None else os.environ
    platform = platform or sys.platform
    if env.get("SSH_CONNECTION") or env.get("SSH_TTY"):
        return True
    return platform.startswith("linux") and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))


def landing_page(summary, report_href):
    """The site's index.html when the dashboard command is not available: the trust badge, what ran, the exact rerun command, and the report. Static, no resource fetched."""
    t = summary["trust"]
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in t["reasons"]) or "<li>none</li>"
    rows = "".join(f"<tr><td>{html.escape(h)}</td></tr>" for h in summary["harnesses"])
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>buffon</title><style>{theme.CSS}</style></head>'
            f'<body><div class="wrap"><div class="top"><a class="brand" href="#">{theme.brand_mark(26)}<span>Buffon</span></a></div><main class="md">'
            f'<h1>Your buffon run</h1><p><strong>Trust: {html.escape(t["badge"])}</strong> (host class {html.escape(t["host_class"])})</p><ul>{reasons}</ul>'
            f'<h2>Harnesses</h2><table><tbody>{rows}</tbody></table><p>Benchmarks: {html.escape(", ".join(summary["benchmarks"]))}</p>'
            f'<p><a href="{html.escape(report_href)}">Open the full report</a></p>'
            f'<h2>Run this yourself</h2><pre><code>{html.escape(summary["command"])}</code></pre></main></div></body></html>')


def build_site(opts, paths, run_dirs, faith_dirs, summary, out):
    """The report and the dashboard, built side by side. `python3 -m buffon dashboard` makes the site; when it fails or is skipped (--no-dashboard), a landing page links the report."""
    site = paths["site"]
    os.makedirs(site, exist_ok=True)
    with open(os.path.join(site, "up.json"), "w") as f:   # what a dashboard needs for its "Run this yourself" panel and its header
        json.dump(summary, f, indent=1)
    report_dir = os.path.join(site, "report")
    report_argv = [opts.python, "-m", "buffon", "report", *run_dirs, "--out", report_dir] + (["--faithfulness", *faith_dirs] if faith_dirs else [])
    dash_argv = [opts.python, "-m", "buffon", "dashboard", *run_dirs, "--out", site] + (["--faithfulness", *faith_dirs] if faith_dirs else [])
    with ThreadPoolExecutor(max_workers=2) as pool:
        rep = pool.submit(subprocess.run, report_argv, capture_output=True, text=True)
        dash = pool.submit(subprocess.run, dash_argv, capture_output=True, text=True) if opts.dashboard else None
        rep, dash = rep.result(), dash.result() if dash else None
    with open(os.path.join(site, "build.log"), "w") as f:
        f.write(rep.stdout + rep.stderr + (dash.stdout + dash.stderr if dash else ""))
    dashboard_ok = bool(dash) and dash.returncode == 0 and os.path.exists(os.path.join(site, "index.html"))
    if rep.returncode != 0:
        out(f"the report did not build (exit {rep.returncode}); {os.path.join(site, 'build.log')} has the reason")
    if not dashboard_ok:
        href = "report/report.html"
        with open(os.path.join(site, "index.html"), "w") as f:
            f.write(landing_page(summary, href))
        if not dash:
            out("the dashboard was skipped (--no-dashboard): the site is a summary page that links the report")
        else:
            reason = next((line.strip() for line in reversed((dash.stderr + dash.stdout).splitlines()) if line.strip()), f"exit code {dash.returncode}")
            out(f"the dashboard did not build ({reason[:300]}): the site is a summary page that links the report; {os.path.join(site, 'build.log')} has the full output")
    return os.path.join(site, "index.html"), rep.returncode == 0


def open_in_browser(path, opts, out, env=None, platform=None):
    """Open the site, or say where it is. Returns True when a browser was asked to open it."""
    url = "file://" + os.path.abspath(path)
    if not opts.open_browser or headless(env, platform):
        out(f"open this in a browser: {url}")
        if headless(env, platform):
            out(f"(no display here: copy the folder {os.path.dirname(os.path.abspath(path))} to a machine with a browser, or serve it: cd {shlex.quote(os.path.dirname(os.path.abspath(path)))} && python3 -m http.server)")
        return False
    import webbrowser
    ok = webbrowser.open(url)
    out(f"opened {url}" if ok else f"open this in a browser: {url}")
    return bool(ok)


# -- the whole thing --------------------------------------------------------------------------------------------------------------------------------

def reproduced(run_dir):
    from ..submit import index
    return index.reproduced_fully(run_dir)


def up(sel, opts, out=print, arms=None, registry=None):
    """Run `buffon up` for a selection. Returns the summary dict (also written to <home>/site/up.json); raises UpError when nothing could run."""
    t_start = time.monotonic()
    paths = machine.paths(opts.home)
    arms = arms if arms is not None else manifest.load_all()
    registry = registry if registry is not None else workloadlib.load_all()
    plans = [(n, ids, dict(sel.params), None) for n, ids in groups(sel.workloads, registry)] + recipe_groups(sel)
    steps = Reporter(3 + len(plans) + (1 if sel.evals else 0) + (2 if sel.isolation in ("auto", "container") else 0), out)

    steps.start("detecting this machine and writing its site profile")
    m = machine.detect()
    profile, site, written = machine.ensure_profile(m, paths, opts.pin)
    probe = estimate.cached_probe(paths["probe"], force=opts.refresh_probe)
    steps.note(machine.describe(m))
    steps.note(f"site profile {profile} ({'written' if written else 'reused'}): " + (f"harness CPUs {site.local.cpus}, runner CPUs {site.local.mock_cpus}" if site.local.cpus else "nothing pinned (too few cores, or this platform cannot pin): the run is labelled Shared"))
    iso, iso_note = resolve_isolation(sel, m, site)
    if iso_note:
        steps.note(iso_note)
    sel = sel.clone(isolation=iso)
    if sel.track in ("pi", "real-world", "all") and iso != "container":
        steps.total -= 2   # the container's own cost is only measured when there is a container
    steps.done(f"this machine is {probe['speed']:.1f}x the reference laptop's per-process cost")

    marks = listing.installed_marks(os.path.join(paths["home"], "installed.json"))
    history = estimate.load_history(paths["timings"])
    harnesses = list(sel.harnesses)
    reference = catalog.REFERENCE if catalog.REFERENCE in arms else harnesses[0]
    if reference not in harnesses:
        harnesses.insert(0, reference)
        sel = sel.clone(harnesses=harnesses)
        steps.note(f"{reference} joins the run as the reference every ratio is measured against")
    apis, added = selection.widen_apis(sel.apis, harnesses, arms)
    if added:
        sel = sel.clone(apis=apis)
        for h, api in added:
            steps.note(f"{h} speaks none of the chosen wire APIs, so {api} joins the run; Pi is measured on it too")
    if sel.time_budget_s:
        sel, notes = estimate.fit_budget(sel, sel.time_budget_s, probe, history, [h for h in harnesses if marks.get(h) == arms[h].manifest_sha256], registry)
        harnesses = list(sel.harnesses)
        for n in notes:
            steps.note("time budget: " + n)
    est = estimate.estimate(sel, probe, history, [h for h in harnesses if marks.get(h) == arms[h].manifest_sha256], registry)
    out(f"buffon up       expected total {selection.format_duration(est['total_s'])} on this machine (an estimate)")

    todo = [h for h in harnesses if marks.get(h) != arms[h].manifest_sha256]
    steps.start(f"installing {len(harnesses)} harness(es): {', '.join(harnesses)}" + ("" if todo else " (all already installed)"), est["steps"]["install"] if todo else 0)
    failed, ok = {}, list(harnesses)
    if todo:
        failed, installed_ok = install_all(todo, arms, paths, sel.offline, lambda s: steps.note(s))
        ok = [h for h in harnesses if h not in failed]
        listing.mark_installed(os.path.join(paths["home"], "installed.json"), [arms[h] for h in installed_ok if arms[h].install_kind not in ("source", "derive")])
    if failed and not ok:
        raise UpError("no harness could be installed: " + "; ".join(f"{a}: {w}" for a, w in failed.items()))
    if reference in failed:
        reference = ok[0]
        steps.note(f"the reference is {reference} instead")
    steps.done(f"{len(ok)} ready" + (f", {len(failed)} left out" if failed else ""))

    os.makedirs(paths["runs"], exist_ok=True)
    run_dirs, group_notes = [], []
    for name, ids, params, recipe in plans:
        key = run_key(name, ok, ids, sel, reference, arms, params)
        d = os.path.join(paths["runs"], f"up-{key}-{name}")
        wait = sum(est["per_workload"].get(w, 0) for w in ids) + est["steps"]["calibrate"] / len(plans)
        steps.start(f"measuring {', '.join(ids)} on {len(ok)} harness(es), one sample at a time", wait)
        if finished(d) and not opts.rerun:
            steps.done("a finished run with these settings exists, reused")
            run_dirs.append(d)
            continue
        code = run_cmd(run_argv(opts, paths, sel, ok, reference, ids, d, params, arms), os.path.join(paths["runs"], f"up-{key}-{name}.log"), steps.note)
        if finished(d):
            run_dirs.append(d)
            steps.done("finished" if code == 0 else f"finished (exit code {code}: the run's log says why)")
        else:
            steps.done(f"no result (exit code {code}); the log is {os.path.join(paths['runs'], f'up-{key}-{name}.log')}")
            group_notes.append(f"{name}: no result (exit {code})")
    if not run_dirs:
        raise UpError("no benchmark produced a result: " + "; ".join(group_notes))

    faith_dirs = []
    if sel.evals:
        steps.start("evaluating faithfulness to Pi (not timed)", est["steps"]["evals"])
        e = "faithfulness-smoke" if "faithfulness-smoke" in sel.evals and "faithfulness" not in sel.evals else "faithfulness"
        fkey = hashlib.sha256(json.dumps([e, sorted(ok), reference]).encode()).hexdigest()[:10]
        fdir = os.path.join(paths["runs"], f"up-{fkey}-{e}")
        if os.path.exists(os.path.join(fdir, "faithfulness.json")) and not opts.rerun:
            steps.done("reused")
            faith_dirs.append(fdir)
        else:
            argv = [opts.python, "-m", "buffon", "faithfulness", "run", "--arms", *[a for a in ok if a != reference], "--reference", reference, "--out", fdir, "--cache-dir", paths["cache"], "--work-dir", paths["work"]]
            if e == "faithfulness-smoke":
                argv += ["--only", *catalog.SMOKE_PROBES]
            if sel.offline:
                argv.append("--offline")
            code = run_cmd(argv, fdir.rstrip("/") + ".log", steps.note, forward=("overall", "egress"))
            if os.path.exists(os.path.join(fdir, "faithfulness.json")):
                faith_dirs.append(fdir)
            steps.done("done" if code == 0 else f"exit code {code}")

    overhead = None
    if sel.isolation == "container" and sel.track in ("pi", "real-world", "all"):
        overhead = container_overhead(opts, paths, sel, reference, steps)

    raws = []
    for d in run_dirs:
        with open(os.path.join(d, "raw.json")) as f:
            raws.append(json.load(f))
    estimate.record_history(paths["timings"], raws)
    infos = [trustlib.badge(r, reproduced(d)) for r, d in zip(raws, run_dirs)]
    worst = max(infos, key=lambda i: trustlib.ORDER[i["badge"]])
    reasons = []
    for i in infos:
        reasons += [r for r in i["reasons"] if r not in reasons]
    combined = dict(worst, reasons=reasons)
    cmd = selection.command(sel, opts.program, opts.selection_file)
    summary = {"harnesses": ok, "left_out": failed, "benchmarks": list(sel.workloads), "evals": list(sel.evals), "trust": combined, "run_dirs": run_dirs, "faithfulness_dirs": faith_dirs, "command": cmd,
               "selection": json.loads(json.dumps(sel.__dict__)), "machine": {"os": m["os"], "arch": m["arch"], "cpu_model": m["cpu_model"], "cores": len(m["cores"]), "smt": m["smt"], "mem_gib": m["mem_gib"]},
               "container_overhead": overhead, "headline": worst["headline"], "track": sel.track or None, "conditions": "lab" if combined["host_class"] == "A" else "typical",
               "coming": [{"name": c, "what": w, "for": s} for c, w, s in trackslib.coming_of(trackslib.load(), sel.track)] if sel.track else [], "adaptive": [dict(v, cell=k) for r in raws for k, v in (r.get("run", {}).get("adaptive", {}).get("stopped") or {}).items()], "group_notes": group_notes}

    steps.start("building the report and the dashboard", est["steps"]["report"])
    index_path, report_ok = build_site(opts, paths, run_dirs, faith_dirs, summary, steps.note)
    steps.done(index_path)
    summary["site"], summary["took_s"] = index_path, round(time.monotonic() - t_start, 1)
    with open(os.path.join(paths["site"], "up.json"), "w") as f:
        json.dump(summary, f, indent=1)
    open_in_browser(index_path, opts, out)
    out(final_text(summary, opts))
    return summary


def container_overhead(opts, paths, sel, reference, steps, runner=None):
    """The container's own cost, once per `buffon up` on a container track: the reference arm's print run bare and in a container, six rounds each (buffon/up/tracks.py container_overhead).
    Not a step the reader chose: it is the A/A pair of the isolation, and it is skipped quietly when either run fails."""
    runner = runner or run_cmd
    out = {}
    for mode in ("none", "container"):
        key = hashlib.sha256(json.dumps(["container-overhead", reference, mode, sel.memory_tier_gib, locklib.lock_hash() if os.path.exists(locklib.LOCK_FILE) else None]).encode()).hexdigest()[:10]
        d = os.path.join(paths["runs"], f"up-{key}-overhead-{mode}")
        if not finished(d) or opts.rerun:
            argv = [opts.python, "-m", "buffon", "run", "--site", paths["site_profile"], "overhead/print", "--arms", reference, "--aa", "none", "--apis", sel.apis[0], "--rounds", "6", "--calibration-rounds", "3",
                    "--reference", reference, "--seed", str(sel.seed), "--out", d, "--cache-dir", paths["cache"], "--npm-cache", paths["npm_cache"], "--quiet-timeout", str(QUIET_TIMEOUT_S),
                    "--isolation", mode, "--memory-tier", str(sel.memory_tier_gib)] + (["--offline"] if sel.offline else [])
            steps.start(f"measuring the container's own cost: {reference} {'in a container' if mode == 'container' else 'bare'}", 30)
            runner(argv, d.rstrip("/") + ".log", steps.note)
            steps.done("finished" if finished(d) else "no result")
        if not finished(d):
            return None
        with open(os.path.join(d, "raw.json")) as f:
            out[mode] = json.load(f)
    return trackslib.container_overhead(out["none"], out["container"], reference)


def final_text(summary, opts):
    t = summary["trust"]
    lines = ["", "buffon up: summary",
             f"  harnesses   {', '.join(summary['harnesses'])}" + (f"   (left out: {', '.join(f'{a} ({w[:60]})' for a, w in summary['left_out'].items())})" if summary["left_out"] else ""),
             f"  benchmarks  {', '.join(summary['benchmarks'])}" + (f"; evals {', '.join(summary['evals'])}" if summary["evals"] else ""),
             f"  trust       {trustlib.line(t)}",
             f"  headline    {t['headline']} ({t['headline_why']})"]
    if summary["adaptive"]:
        lines.append(f"  stopped early  {len(summary['adaptive'])} cell(s) once their answer was clear; rounds per cell are in the report")
    lines += [f"  runs        {', '.join(summary['run_dirs'])}", f"  site        {summary['site']}", f"  took        {selection.format_duration(summary['took_s'])}",
              f"  run it again  {summary['command']}   (finished runs and installed harnesses are reused)"]
    return "\n".join(lines)
