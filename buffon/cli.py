# SPDX-License-Identifier: Apache-2.0
"""Buffon command line: `python3 -m buffon <command>`. `python3 -m buffon --help` lists the commands; the list is built from the parser (TopParser.format_help)."""
import argparse
import difflib
import json
import os
import shlex
import sys
import tomllib

from . import site as sitelib
from .site import parse_cpus
from .backend import BackendError
from .arms import lock as locklib
from .arms import manifest
from .runner import slots as slotlib

EXIT_USAGE, EXIT_REFUSED, EXIT_EGRESS = 2, 3, 4
EVERYDAY = ("up", "harnesses", "benches", "report", "rerun", "verify")   # listed first in `buffon --help`
HIDDEN = ("session", "promote", "index", "compare", "sysinfo")           # run by a backend, by CI or by another command: callable, not listed
EXIT_CODES = "Exit codes: 0 success; 1 a check rejected its input or a command failed; 2 usage, input or site-profile error; 3 refused before measuring (gate, pinning, clock); 4 egress violation."
DEFAULT_SEED = 20261011


def add_run_flags(p):
    p.add_argument("--lock-file", default=None, help="Buffon's own exclusive host lock (default: one in the temporary directory): one measurement runs per host")
    p.add_argument("--foreign-lock", action="append", default=[], help="a lock file another benchmark tool holds; the run refuses to start while someone else holds it (repeatable)")
    p.add_argument("--quiet-max-busy", type=float, default=0.10, help="the pinned CPUs may be at most this busy before a sample, else the runner waits")
    p.add_argument("--quiet-timeout", type=float, default=300.0, help="seconds to wait for a quiet host before a sample; then the sample fails")
    p.add_argument("--quiet-max-runnable", type=int, default=0, help="the most other runnable threads allowed on the pinned CPUs before a sample (default 0)")
    p.add_argument("--quiet-max-steal", type=float, default=0.02, help="largest per-CPU steal share allowed on the pinned CPUs before a sample")
    p.add_argument("--quiet-max-psi", type=float, default=10.0, help="CPU pressure (some avg10, percent) allowed before a sample")
    p.add_argument("--observer", action="append", default=[], metavar="MODULE:FACTORY", help="register a runner observer (docs/HOOKS.md); repeatable")
    p.add_argument("--no-telemetry", action="store_true", help="do not record per-sample telemetry (`buffon verify` rejects the run)")
    p.add_argument("--telemetry-interval", type=float, default=0.25, help="seconds between telemetry readings while a sample runs (0: only before and after)")
    p.add_argument("--memory-tier", type=int, choices=[1, 2, 4, 8], default=4, help="--isolation container: the memory limit of every harness container, in GiB (a fixed tier, so races on small and big machines compare; the tier is part of a result's name)")
    p.add_argument("--isolation", choices=["container", "pod-guaranteed", "none"], default=None, help="container: every arm in the shared container envelope (buffon/envelope); pod-guaranteed: the session's Kubernetes pod is the envelope (buffon/envelope/pod.py; a Kubernetes site's default); none (default until the envelope is validated on real runs): uncontained, stamped 'uncontained, not comparable'")
    p.add_argument("--host-claim", choices=["A", "B"], default="B", help="A: the site declares this host dedicated (preflight checks that nothing else runs on the bench CPUs); B: shared")
    p.add_argument("--clock-claim", choices=["hypervisor"], default="", help="the site says this virtual machine's platform fixes the clock and turbo state and exposes no interface to read them (a claim; the report states it)")
    p.add_argument("--require-class", choices=["A", "B"], default=None, help="refuse to run on a host of a lower class (A = dedicated and publishable, B = shared and provisional)")
    p.add_argument("--no-quiet-gate", action="store_true", help="take samples without the quiet-host check (the run is not labelled quiet)")
    p.add_argument("workloads", nargs="*", default=["overhead"], help="workload ids, families or `all` (default: overhead)")
    p.add_argument("--arms", nargs="*", help="arm ids (default: every runnable arm; held arms are never run)")
    p.add_argument("--accept-terms", default="", metavar="IDS", help="arms whose vendor terms you accept (comma separated, or BUFFON_ACCEPT_TERMS); an arm with operator terms runs only when named and accepted")
    p.add_argument("--apis", nargs="*", default=None, help="wire APIs, each a separate variant in the report (default: openai-completions and anthropic-messages, plus openai-responses when an arm speaks only that)")
    p.add_argument("--envs", nargs="*", default=None, help="environments the durable workloads run in (default: native; miniflare and cloudflare are reserved for a later phase and refused)")
    p.add_argument("--rounds", type=int, default=None, help="measured rounds (default 12; 5 for the scale family, whose spread across rounds is its noise). With --adaptive: the most a cell takes. Fewer than 12 are recorded and labelled; they cannot be Verified")
    p.add_argument("--adaptive", action="store_true", help="per cell, stop adding rounds once the interval clears the noise floor or is tight enough to call no measurable difference (at least 6 rounds)")
    p.add_argument("--calibration-rounds", type=int, default=12, help="rounds of the reference-against-its-own-copy calibration (the Noisy label's measurement)")
    p.add_argument("--warmup", type=int, default=1, help="warm-up rounds, kept in the raw data and dropped from the statistics")
    p.add_argument("--aa", default=None, help="A/A copies: all (default; the scale family has none unless this is given), none, or a comma list of arm ids; an arm without a copy makes the run PROVISIONAL")
    p.add_argument("--reference", default="pi-node", help="the reference arm (default pi-node, docs/DESIGN.md section 3); calibration runs on it when it is selected")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--timeout", type=float, default=120, help="per-process timeout, seconds")
    p.add_argument("--rpc-turns", type=int, default=20)
    p.add_argument("--long-turns", type=int, default=1000)
    p.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="workload parameter (see docs/RUNNING.md), repeatable")
    p.add_argument("--no-calibrate", action="store_true", help="skip the calibration gate (the run is then labelled PROVISIONAL)")
    p.add_argument("--allow-noisy", action="store_true", help="(only with --require-class A) continue after a failed calibration gate; without --require-class A nothing refuses and a noisy run is labelled Noisy")
    p.add_argument("--allow-short", action="store_true", help="allow fewer than 12 measured rounds (smoke runs); the run is labelled not a measured run")
    p.add_argument("--allow-frequency-scaling", action="store_true")
    p.add_argument("--out", help="run directory (default: runs/<UTC time>)")


class TopParser(argparse.ArgumentParser):
    """The top-level parser. Its help is built from the registered commands, so the list cannot drift from the code: the everyday commands first, then the rest, never the internal ones."""

    def format_help(self):
        sub = next(a for a in self._actions if isinstance(a, argparse._SubParsersAction))
        summary = {a.dest: a.help for a in sub._choices_actions}
        names = [n for n in EVERYDAY if n in summary] + [n for n in summary if n not in EVERYDAY and n not in HIDDEN]
        width = max(len(n) for n in names) + 2
        rows = lambda group: [f"  {n:<{width}}{summary[n]}" for n in group]
        return "\n".join(["usage: buffon <command> [options]", "", "Buffon command line: python3 -m buffon <command>  (or ./buffon.sh <command>)", "", "everyday:", *rows(n for n in names if n in EVERYDAY), "", "more:", *rows(n for n in names if n not in EVERYDAY), "",
                          "`buffon <command> --help` lists the options of a command.", "", EXIT_CODES, ""])


def command(sub, name, summary, description=None, **kw):
    """Register a command: `summary` is its one line in `buffon --help`, `description` the longer text of `buffon <name> --help`."""
    return sub.add_parser(name, help=summary, description=description or summary, **kw)


class WideHelp(argparse.RawDescriptionHelpFormatter):
    """Help that fits a screen: a wide, shallow layout."""

    def __init__(self, prog):
        super().__init__(prog, max_help_position=26, width=110)


UP_DESCRIPTION = """One command from a fresh clone to a running Buffon: detects this machine, writes its site profile, installs the harnesses, measures, evaluates, builds the
dashboard and opens it. Finished runs and installed harnesses are reused, so running it again is quick."""
UP_EPILOG = """examples:
  buffon up                                   quick suite, default harnesses, open the dashboard
  buffon up --harness pig,pi,pi-bolt --bench standard
  buffon up --bench scale/agents-limit --param swarm_max_agents=64
`buffon harnesses` and `buffon benches` list the choices; with no selection flags on a terminal a picker asks."""


def add_up_flags(p):
    p.add_argument("selection", nargs="?", help="a saved selection (TOML written by --save)")
    from .up import catalog
    p.add_argument("--harness", help="names, globs or all (default: " + ", ".join(catalog.DEFAULT_HARNESSES) + ")")
    p.add_argument("--accept-terms", default="", metavar="IDS", help="accept vendor terms of claude-code, copilot (or BUFFON_ACCEPT_TERMS)")
    p.add_argument("--bench", help="quick (default), standard, full, or families/workloads: streaming,memory,...")
    p.add_argument("--track", choices=["common", "pi", "real-world", "all"], metavar="TRACK", help="common, pi, real-world or all, instead of --bench (pi, real-world: containers)")
    p.add_argument("--evals", help="faithfulness, faithfulness-smoke or none (default per preset)")
    p.add_argument("--apis", help="wire APIs, comma separated (default per preset)")
    p.add_argument("--rounds", type=int, help="the most rounds a cell takes (default 12)")
    p.add_argument("--adaptive", action=argparse.BooleanOptionalAction, default=None, help="stop a cell once its answer is clear (on in quick, standard)")
    p.add_argument("--time-budget", metavar="20m", help="fit into this time: fewer rounds, then fewer benchmarks")
    p.add_argument("--offline", action="store_true", help="never download or build; everything must be installed")
    p.add_argument("--memory-tier", type=int, choices=[1, 2, 4, 8], metavar="GIB", help="container memory limit, the same for every harness: 1, 2, 4 (default) or 8")
    p.add_argument("--isolation", choices=["container", "none"], metavar="MODE", help="container (docker or podman) or none: each harness in its own container, or bare")
    p.add_argument("--param", action="append", default=[], metavar="K=V", help="workload parameter (repeatable)")
    p.add_argument("--save", metavar="FILE", help="write this selection to FILE and run it")
    p.add_argument("--plan", action="store_true", help="print the selection and the expected time, run nothing")
    p.add_argument("--no-open", action="store_true", help="do not open a browser")
    p.add_argument("--no-dashboard", action="store_true", help="skip the dashboard (it needs Node 18+): the report and a summary page only")
    p.add_argument("--yes", "-y", action="store_true", help="never ask: use the flags and defaults")
    p.add_argument("--dedicated", action="store_true", help="claim this host is dedicated (checked, then labelled)")
    p.add_argument("--require-class", choices=["A"], help="the old strict rules: refuse a noisy or shared host")
    p.add_argument("--no-pin", action="store_true", help="do not pin processes to CPUs (the run is labelled Shared)")
    p.add_argument("--rerun", action="store_true", help="measure again even where a finished run exists")
    p.add_argument("--home", help="state directory (default $BUFFON_HOME or ~/.local/share/buffon)")


def parse_params(items):
    out = {}
    for item in items:
        key, eq, value = item.partition("=")
        if not eq:
            raise SystemExit(f"--param {item!r}: use KEY=VALUE")
        try:
            out[key] = json.loads(value)
        except ValueError:
            out[key] = value
    return out


def resolve_arm_names(names, arms):
    """Full arm ids for the names a person typed. The short names `buffon up` takes (pi, pig, pi-bolt, ...) are accepted. An unknown name is refused with the nearest ids."""
    from .up import catalog
    out, unknown = [], []
    for n in names:
        if n in arms:
            out.append(n)
        elif catalog.SHORT_NAMES.get(n) in arms:
            out.append(catalog.SHORT_NAMES[n])
        else:
            unknown.append(n)
    if unknown:
        hints = []
        for n in unknown:
            near = difflib.get_close_matches(n, list(arms), n=3, cutoff=0.5)
            hints.append(repr(n) + (f" (did you mean {', '.join(near)}?)" if near else ""))
        raise BackendError(f"unknown arm{'s' if len(unknown) > 1 else ''} {', '.join(hints)}. `buffon harnesses` lists the arms")
    return out


def check_workloads(names):
    """Refuse an unknown workload, family or `all` before anything is created: a typo must not leave a run directory behind."""
    from . import workloads
    for n in names:
        try:
            workloads.resolve([n])
        except KeyError:
            known = sorted(workloads.REGISTRY)
            near = difflib.get_close_matches(n, known + sorted({w.family for w in workloads.REGISTRY.values()}), n=3, cutoff=0.5)
            raise BackendError(f"unknown workload {n!r}" + (f" (did you mean {', '.join(near)}?)" if near else "") + ". `buffon benches` lists the workloads, a family name runs all its workloads") from None


def submission_blockers(args):
    """Why `buffon verify --submission` would reject a run made with these flags or this checkout (docs/SUBMITTING.md). One line each; empty when none."""
    from .runner import facts as factlib
    out = []
    if factlib.runner_checkout(manifest.ROOT)["runner_dirty"]:
        out.append("Buffon checkout has uncommitted changes (commit them first: the run records the commit)")
    if args.no_telemetry:
        out.append("--no-telemetry switches off the telemetry every check reads")
    if args.aa not in (None, "all"):
        out.append(f"--aa {args.aa} leaves arms without an A/A copy, so they have no noise floor")
    return out


def add_local_cache_flags(p):
    """`buffon run` and `buffon calibrate` on a local site: where the verified artifacts and the npm cache are, and never download (what `buffon campaign` passes for a site run from a bundle)."""
    p.add_argument("--cache-dir", default="", help="local site: where verified artifacts are kept (default: the site's cache_dir)")
    p.add_argument("--npm-cache", default="", help="local site: the npm cache npm arms install from (a bundle's npm-cache/); default: an empty one in the workspace")
    p.add_argument("--offline", action="store_true", help="local site: never download or build; every artifact must be in the cache (a bundle's cache/)")


# The one line of each command in `buffon --help` (its longer text is the `help=` of its add_parser call, shown by `buffon <command> --help`).
SUMMARY = {
    "up": "one command from a fresh clone to results and an open dashboard", "harnesses": "list every harness: version, what it needs, installed or not", "benches": "list every benchmark: state, what it measures, expected time",
    "report": "render the report, the grade and the run notes from run directories", "rerun": "measure one cell of a published run again and compare", "verify": "re-validate run directories the way CI does",
    "run": "run a session through the site's backend", "dashboard": "build the static results site from run directories", "grade": "recompute the Pi Harness Score with other weights", "health": "the run notes of run directories, or `thresholds`",
    "reproduce": "repeat a whole run on this site and compare", "perfcheck": "can this host count instructions? exit 0 yes, 3 no", "external": "other projects' benchmarks: import, run, list", "lock": "generate or verify arms.lock",
    "arms": "list the arm manifests", "arm": "install one arm and run it against the mock (arm verify NAME)", "site": "print the site profile schema, or validate a profile",
    "faithfulness": "the Pi Faithfulness Score: black-box probes against Pi", "preflight": "which host class (A dedicated, B shared) this machine gives", "agentbench": "agent benchmarks: plan a protocol, compute the paired result",
    "mock": "serve the mock endpoint (to debug an arm by hand)", "calibrate": "Kubernetes: the noise floor of the site's nodes", "campaign": "Kubernetes or a VPS: a whole measured campaign from a plan file",
    "session": "the executor a backend runs", "promote": "write promotion.json (CI does this after a merge)", "index": "build or check the results index (CI)", "compare": "compare a run with its reproduction", "sysinfo": "write host.json",
}


class Commands:
    """The subparsers of `buffon`. A command's `help=` text becomes the description of its own `--help`; its line in `buffon --help` is SUMMARY[name]."""

    def __init__(self, sub):
        self.sub = sub

    def add_parser(self, name, help=None, **kw):
        kw.setdefault("description", help)
        return self.sub.add_parser(name, help=SUMMARY[name], **kw)

    @property
    def choices(self):
        return self.sub.choices


def build_parser():
    ap = TopParser(prog="buffon", description=__doc__, allow_abbrev=False)
    sub = Commands(ap.add_subparsers(dest="cmd", required=True, metavar="command", parser_class=argparse.ArgumentParser))
    p = sub.add_parser("up", help="detect this machine, install the default harnesses, run the quick suite, open the dashboard (one command)", description=UP_DESCRIPTION, epilog=UP_EPILOG,
                       formatter_class=WideHelp, usage="buffon up [selection.toml] [options]")
    add_up_flags(p)
    p = sub.add_parser("harnesses", help="list every harness: version, what it needs, installed or not")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("benches", help="list every benchmark: its state, what it measures, expected time on this machine")
    p.add_argument("--json", action="store_true")
    p.add_argument("--refresh", action="store_true", help="measure this machine's speed again")
    p = sub.add_parser("run", help="run a session through the site's backend")
    add_run_flags(p)
    add_local_cache_flags(p)
    p.add_argument("--site", help="site profile: a path or a name in sites/ (default: $BUFFON_SITE, else a local unpinned site)")
    p.add_argument("--calibration", help="Kubernetes: calibration.json from `buffon calibrate`; the run goes to the calibrated nodes, and is refused before any pod when the calibration does not vouch for them")
    p.add_argument("--bundle", help="Kubernetes bundle site: a bundle built beforehand (python3 -m buffon.backend.bundle); kept after the run (default: build one for this run)")
    p.add_argument("--nodes", help="with --calibration: run on these of the calibrated nodes only (comma-separated); a node the calibration does not vouch for is refused")
    p.add_argument("--slot", type=int, metavar="N", help="local site with `[local] slots`: run in slot N of the host's split into disjoint core sets (its own CPUs and its own lock; `buffon campaign` runs the families this way)")
    p.add_argument("--slot-calibration", metavar="FILE", help="with --slot: slots-calibration.json from `buffon campaign`; a slot it does not pass is refused, and a slot without it is labelled slotted on the trust badge")
    p = sub.add_parser("calibrate", help="Kubernetes: the noise floor of the site's nodes, from the reference arm against its own A/A copy on each")
    add_run_flags(p)
    add_local_cache_flags(p)
    p.add_argument("--site", help="site profile: a path or a name in sites/ (default: $BUFFON_SITE)")
    p.add_argument("--bundle", help="Kubernetes bundle site: a bundle built beforehand; kept after the run")
    p = sub.add_parser("campaign", help="Kubernetes: a whole measured campaign from a plan file: wait for the cluster, calibrate the nodes, run each family on them, verify every run")
    p.add_argument("plan", help="campaign plan (TOML, docs/RUNNING.md 'Campaigns'), e.g. campaigns/quiet-v1.toml")
    p.add_argument("--site", help="site profile: a path or a name in sites/ (default: $BUFFON_SITE)")
    p.add_argument("--out", required=True, help="campaign directory; run it again with the same --out to resume after an interruption")
    p.add_argument("--bundle", help="a bundle built beforehand for a bundle site (default: build one into <out>/bundle once)")
    p.add_argument("--wait-cluster", type=float, default=0, metavar="SECONDS", help="wait up to this long for the cluster to answer before the first pod (default: do not wait)")
    p.add_argument("--dry-run", action="store_true", help="check the plan, the site and the bundle and print the steps; contact no cluster")
    p.add_argument("--parallel", action="store_true", help="run the families at once, one session per calibrated node (each session keeps all its arms interleaved on its node)")
    p = sub.add_parser("session", help="the executor a backend runs")
    add_run_flags(p)
    p.add_argument("--cpus", default="", help="harness CPUs, a list, or `inherit` (this process's allowed CPUs minus the mock's)")
    p.add_argument("--mock-cpus", default="")
    p.add_argument("--pinning", default="preferred", choices=sitelib.PIN_POLICIES)
    p.add_argument("--hardware-claim", default="shared", choices=sitelib.HARDWARE_CLAIMS)
    p.add_argument("--meter", default="auto")
    p.add_argument("--cache-dir", default="")
    p.add_argument("--work-dir", default="")
    p.add_argument("--offline", action="store_true", help="never download: every artifact must be in the cache")
    p.add_argument("--npm-cache", default="", help="the npm cache npm arms install from (a bundle's npm-cache/); default: an empty one in the workspace")
    p.add_argument("--calibrate-only", action="store_true")
    p.add_argument("--slot", default="", metavar="ID/OF", help="this session runs in slot ID of OF (`buffon run --slot` sets it): its own lock file, the other slots' CPUs are not housekeeping")
    p.add_argument("--slot-others", default="", help="the CPUs of the other slots")
    p.add_argument("--slot-calibration", default="", help="the slots-calibration.json that passed this slot")
    p = sub.add_parser("report", help="render report.md from a run directory")
    p.add_argument("dirs", nargs="+")
    p.add_argument("--out")
    p.add_argument("--reference", default=None)
    p.add_argument("--drop-flagged", action="store_true", help="leave out every round that carries a host-flagged sample (docs/TELEMETRY.md); the noise report lists them")
    p.add_argument("--external-results", nargs="*", default=None, help="imported result sets (buffon external import): their own section, never in a cell")
    p.add_argument("--external-suites", nargs="*", default=None, help="external suite run directories (buffon external run): their own section, never in a cell")
    p.add_argument("--faithfulness", nargs="*", default=None, help="faithfulness run directories (buffon faithfulness): they go into the report's grade files; the site does not show them")
    p = sub.add_parser("dashboard", help="the static results site (docs/design/DASHBOARD.md): a grid of harnesses and the metrics you pick, a page for each metric, harness and measurement, the method and the runs; opens from the folder or GitHub Pages")
    p.add_argument("dirs", nargs="+", help="run directories, as for `buffon report` (a directory holding external-suite.json or external.json is an external run: its own section, in no cell)")
    p.add_argument("--out", required=True, help="the site directory: empty, or written by an earlier `buffon dashboard`")
    p.add_argument("--reference", default=None)
    p.add_argument("--faithfulness", nargs="*", default=None, help="faithfulness run directories, as for `buffon report`")
    p.add_argument("--external-results", nargs="*", default=None, help="imported result sets (buffon external import): the section Other suites, never a cell, a tile or a ratio")
    p.add_argument("--external-suites", nargs="*", default=None, help="external suite run directories (buffon external run): the section Other suites. A directory with external.json or external-suite.json among DIRS counts too")
    p = sub.add_parser("grade", help="the Pi Harness Score of a report directory (report.json), recomputed with the published weights or your own (docs/GRADE.md)")
    p.add_argument("dir", help="a report directory (or a report.json) written by `buffon report`")
    p.add_argument("--weights", default=None, help="a TOML file with [families] and/or [kinds] weights replacing the profile's (bands, gates and families are the method's, not yours)")
    p.add_argument("--profile", default="default", help="the published weight profile to start from (default, equal, cpu-heavy, memory-heavy, extension-heavy)")
    p.add_argument("--faithfulness", nargs="*", default=None, help="faithfulness run directories to take scores from (replaces the report's)")
    p.add_argument("--out", default=None, help="where to write grade.json, leaderboard.md and report-card.md (default: print the leaderboard only)")
    p.add_argument("--seed", type=int, default=20261011)
    p.add_argument("--resamples", type=int, default=None)
    p.add_argument("--strict", action="store_true", help="the old refusals: no score when a family cannot be measured, coverage is thin or the reference's manifest facts are missing")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("health", help="the run notes of run directories (each check is ok or a note), or `thresholds` to print the published usual ranges")
    p.add_argument("dirs", nargs="+", help="run directories, or the word `thresholds`")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("verify", help="re-validate run directories the way CI does before the results index accepts them (seal, pins, integrity, telemetry; run notes are listed, never a reason to reject)")
    p.add_argument("dirs", nargs="+")
    p.add_argument("--submission", action="store_true", help="also require submission.toml (what the results index requires); hardware class and run notes are listed, not rejected")
    p.add_argument("--repo", default=None, help="Buffon checkout holding arms.lock and the runner commit (default: this one)")
    p.add_argument("--reference", default=None)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("index", help="build or check the results index of a results directory")
    p.add_argument("results", help="a directory of verified run directories (results/)")
    p.add_argument("--check", action="store_true", help="fail when index.json or INDEX.md differ from what the directories generate")
    p.add_argument("--allow-governance", action="store_true", help="with --immutable-against: check a maintainers change instead: only WITHDRAWN.toml, MAINTAINERS.toml and the index may change (no run directory)")
    p.add_argument("--immutable-against", metavar="GIT_REF", help="fail when anything but a new file inside a new run directory changed against this git ref")
    p.add_argument("--repo", default=None)
    p = sub.add_parser("promote", help="verify a run directory as a submission and write promotion.json (what CI does); --to copies it into a results directory first")
    p.add_argument("run")
    p.add_argument("--to", help="a results directory to copy the sealed run into (an existing id is never replaced)")
    p.add_argument("--id")
    p.add_argument("--repo", default=None)
    p = sub.add_parser("reproduce", help="repeat a run directory's plan on this site, then compare the two runs, telemetry included")
    p.add_argument("original", help="the run directory to reproduce")
    p.add_argument("--site", help="site profile (a path or a name in sites/)")
    p.add_argument("--out", help="run directory for your run (default: runs/<UTC time>)")
    p = sub.add_parser("rerun", help="measure one cell of a published run again: its workload and API, its arms, the original's rounds and seed, then compare (docs/RUNNING.md)")
    p.add_argument("cell", help="a cell id from a report: <run id>::<workload>@<api>#<metric>")
    p.add_argument("--site", help="site profile (a path or a name in sites/)")
    p.add_argument("--out", help="run directory for your run (default: runs/<UTC time>)")
    p.add_argument("--runs-dir", action="append", default=[], help="a directory holding run directories, searched after results/ and runs/ (repeatable)")
    p.add_argument("--print", dest="print_only", action="store_true", help="print the `buffon run` command and exit")
    p = sub.add_parser("perfcheck", help="can this host (or the nodes of a Kubernetes site, one pod each) count instructions? exit 0 yes, 3 no (CPU time is then the headline)")
    p.add_argument("--site", help="site profile (a path or a name in sites/); a Kubernetes site runs the check in one pod per target node")
    p.add_argument("--out", help="where perfcheck.json (and, on a cluster, perfcheck-summary.json) is written")
    p.add_argument("--bundle", help="Kubernetes bundle site: the bundle directory the pods run from")
    p.add_argument("--nodes", help="Kubernetes: comma list of nodes (default: the site's node choice)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--offline", action="store_true", help=argparse.SUPPRESS)           # a bundle pod's session argv always carries these
    p.add_argument("--cache-dir", default=None, help=argparse.SUPPRESS)
    p.add_argument("--npm-cache", default=None, help=argparse.SUPPRESS)
    p = sub.add_parser("compare", help="compare a run directory with its reproduction: pins, plan, host, noise, and every comparison")
    p.add_argument("original")
    p.add_argument("yours")
    p.add_argument("--out", help="where to write reproduction.md and reproduction.json (default: the second directory)")
    p = sub.add_parser("external", help="other people's benchmarks: import published results, run an upstream suite as it is, list suites")
    p.add_argument("action", choices=["suites", "import", "run", "plan"])
    p.add_argument("--out")
    p.add_argument("--family", help="import: a published family (buffon/external/published.py); its provenance and table come from the family")
    p.add_argument("--suite")
    p.add_argument("--target", help="run: the suite's target (pi-node, pig-native, build, ...)")
    p.add_argument("--checkout", help="run: the repository checkout the suite runs in")
    p.add_argument("--commit", default=None, help="run, plan: the commit the checkout must be at, as SHA or REPO=SHA (default: the suite's pin)")
    p.add_argument("--arm")
    p.add_argument("--command", help="run: the arm's command line, for suites that compare builds")
    p.add_argument("--cpus")
    p.add_argument("--live", action="store_true", help="run: allow a suite that needs a real model")
    p.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="run: a variable the suite needs (GOPATH, GOMODCACHE, npm_config_cache ...); the suite gets only PATH, locale, TZ, TERM and a HOME in the run directory otherwise")
    p.add_argument("--foreign-lock", action="append", default=[])
    p.add_argument("--timeout", type=int, default=2700)
    p.add_argument("--meta", help="import: JSON file with the provenance fields (id, title, source_url, repo, commit, version, host, licence, published)")
    p.add_argument("files", nargs="*", help="import: the published files, copied unchanged")
    p = sub.add_parser("lock", help="generate or verify arms.lock")
    p.add_argument("--check", action="store_true")
    p.add_argument("--online", action="store_true", help="also check every artifact hash against the project's published checksums")
    p = sub.add_parser("arms", help="list arm manifests")
    p = sub.add_parser("arm", help="arm commands")
    p.add_argument("action", choices=["verify"])
    p.add_argument("name")
    p.add_argument("--site")
    p = sub.add_parser("site", help="site profile commands")
    p.add_argument("action", choices=["schema", "check", "show"])
    p.add_argument("site", nargs="?")
    p = sub.add_parser("faithfulness", help="the Pi Faithfulness Score: deterministic black-box probes against Pi")
    p.add_argument("action", choices=["run", "report", "probes"])
    p.add_argument("dirs", nargs="*", help="report: run directories or faithfulness.json files")
    p.add_argument("--arms", nargs="*", default=None)
    p.add_argument("--reference", default="pi-node")
    p.add_argument("--out")
    p.add_argument("--pi-source", help="a Pi source tree: probes then cite the line of its argument parser")
    p.add_argument("--only", nargs="*", help="probe id globs")
    p.add_argument("--cache-dir")
    p.add_argument("--work-dir")
    p.add_argument("--timeout", type=float, default=60)
    p.add_argument("--offline", action="store_true")
    p = sub.add_parser("preflight", help="which host class (A dedicated, B shared) can this machine give the benchmark's CPUs")
    p.add_argument("--site")
    p.add_argument("--cpus")
    p.add_argument("--mock-cpus")
    p.add_argument("--host-claim", choices=["A", "B"], default="B")
    p.add_argument("--clock-claim", choices=["hypervisor"], default="")
    p.add_argument("--require-class", choices=["A", "B"], default=None)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("sysinfo", help="write host.json (the platform specification) for the given CPUs")
    p.add_argument("--cpus", required=True)
    p.add_argument("--mock-cpus", default="")
    p.add_argument("--out", default="host.json")
    p = sub.add_parser("agentbench", help="agent benchmarks (task pass rates with real models): plan a protocol, compute the paired result from observations")
    p.add_argument("action", choices=["plan", "result"])
    p.add_argument("protocol", help="a protocol JSON file (benchmark, arms, cases, models, runs, seed, params)")
    p.add_argument("--observations", help="result: observations.jsonl")
    p.add_argument("--out", required=True)
    p = sub.add_parser("mock", help="serve the mock endpoint")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--transcript")
    for p in sub.choices.values():   # the run records its argv and `buffon verify` reads the gate flags from it: `--allow-noi` must not be a silent --allow-noisy
        p.allow_abbrev = False
    return ap


def error_text(error):
    """One line for an input problem: `path: reason` for a file, the message for a name the code does not know."""
    if isinstance(error, OSError) and error.filename:
        return f"{error.filename}: {error.strerror}"
    if isinstance(error, KeyError) and error.args and isinstance(error.args[0], str):
        return error.args[0]
    return str(error)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # progress lines reach a log file as they happen
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](args)
    except sitelib.SiteError as error:
        print(f"buffon: {error}", file=sys.stderr)
        return EXIT_USAGE
    except (manifest.ManifestError, BackendError) as error:
        print(f"buffon: {error}", file=sys.stderr)
        return EXIT_USAGE
    except (OSError, KeyError) as error:   # a missing path or an unknown name: one line, not a traceback (BUFFON_DEBUG=1 shows it)
        if os.environ.get("BUFFON_DEBUG"):
            raise
        print(f"buffon: {error_text(error)}", file=sys.stderr)
        return EXIT_USAGE


def build_selection(args):
    """The selection a `buffon up` command line means: a saved file, then the flags over it, else the quick preset."""
    from .up import estimate, selection
    if args.track and args.bench:
        raise selection.SelectionError("--track and --bench both choose the benchmarks: give one")
    accept = manifest.accepted_terms(args.accept_terms)
    sel = selection.load(args.selection, accept=accept) if args.selection else selection.from_track(args.track) if args.track else selection.from_preset("quick")
    explicit = bool(args.selection) or bool(args.track)
    if args.harness:
        accept |= set(sel.accept_terms)
        sel.harnesses, explicit = selection.parse_harnesses(args.harness, accept=accept), True
        sel.accept_terms = selection.terms_of(sel.harnesses, manifest.load_all(), accept)
    if args.bench:
        names, preset = selection.parse_benches(args.bench)
        sel.workloads, sel.preset = names, preset
        if preset:
            from .up import catalog
            d = catalog.PRESETS[preset]
            sel.apis, sel.rounds, sel.adaptive, sel.calibration_rounds, sel.evals = list(d["apis"]), d["rounds"], d["adaptive"], d["calibration_rounds"], list(d["evals"])
        else:
            sel.spec = selection.bench_spec(args.bench)
            if not args.apis and not args.selection:
                sel.apis = ["openai-completions"]
            if args.evals is None:
                sel.evals = []
        explicit = True
    if args.evals is not None:
        sel.evals, explicit = selection.parse_evals(args.evals), True
    if args.apis:
        sel.apis = [a for a in args.apis.replace(",", " ").split()]
        explicit = True
    if args.rounds:
        if args.rounds < 1:
            raise selection.SelectionError("--rounds must be at least 1")
        sel.rounds, sel.rounds_set, sel.preset, explicit = args.rounds, True, "", True
    if args.adaptive is not None:
        sel.adaptive, sel.preset, explicit = args.adaptive, "", True
    if args.time_budget:
        sel.time_budget_s, explicit = selection.parse_duration(args.time_budget), True
    if args.offline:
        sel.offline = True
    if args.isolation:
        sel.isolation, explicit = args.isolation, True
    elif not sel.isolation and any(w.startswith("scale/") for w in sel.workloads):
        sel.isolation = "auto"   # a swarm is N agents in one container: a container where the machine has a runtime and pinned CPUs
    if args.memory_tier:
        sel.memory_tier_gib, explicit = args.memory_tier, True
    if args.param:
        sel.params.update(parse_params(args.param))
        explicit = True
    args.explicit = explicit
    return sel


def cmd_up(args):
    from .up import catalog, estimate, flow, listing, machine, picker, selection
    try:
        sel = build_selection(args)
        paths = machine.paths(args.home)
        opts = flow.Options(home=args.home, open_browser=not args.no_open, dedicated=args.dedicated, require_class=args.require_class, selection_file=args.save or args.selection,
                            program=os.environ.get("BUFFON_PROGRAM", "python3 -m buffon"), rerun=args.rerun, pin=not args.no_pin, dashboard=not args.no_dashboard)
        problem = None if args.plan or args.no_dashboard else machine.node_problem()
        if problem:   # before anything is installed or measured: the dashboard is the last step, and a missing Node must not cost the whole run
            print(f"buffon up: {problem}. Or run again with --no-dashboard for the report and a summary page.", file=sys.stderr)
            return 1
        if not args.explicit and not args.yes and not args.plan and picker.is_tty():
            probe = estimate.cached_probe(paths["probe"])
            history, marks = estimate.load_history(paths["timings"]), listing.installed_marks(os.path.join(paths["home"], "installed.json"))
            installed = [n for n, a in manifest.load_all().items() if marks.get(n) == a.manifest_sha256]
            try:
                sel = picker.pick(listing.harness_rows(marks=marks), listing.bench_rows(probe, history), sel, lambda x: estimate.estimate(x, probe, history, installed)["total_s"])
            except picker.Aborted:
                print("buffon up: nothing selected, nothing run")
                return 0
        if args.save:
            selection.save(sel, args.save)
            print(f"buffon up: selection saved to {args.save}; run it again with: {os.environ.get('BUFFON_PROGRAM', 'python3 -m buffon')} up {shlex.quote(args.save)}")
        if args.plan:
            probe = estimate.cached_probe(paths["probe"])
            history = estimate.load_history(paths["timings"])
            if sel.time_budget_s:
                sel, notes = estimate.fit_budget(sel, sel.time_budget_s, probe, history)
                for n in notes:
                    print(f"time budget: {n}")
            cpus = None
            if os.path.exists(paths["site_profile"]):
                cpus = len(sitelib.load(paths["site_profile"]).local.cpus) or None   # the swarm's CPUs are the site profile's harness CPUs
            est = estimate.estimate(sel, probe, history, cpus=cpus)
            note = estimate.scale_note(sel, est, cpus)
            rounds = f"rounds     up to {sel.rounds}{' (adaptive)' if sel.adaptive else ''}\n" if sel.rounds_set or any(not w.startswith("scale/") for w in sel.workloads) else ""
            print(f"harnesses  {', '.join(sel.harnesses)}\nbenchmarks {sel.spec or ', '.join(sel.workloads)}\napis       {', '.join(sel.apis)}\n{rounds}"
                  f"evals      {', '.join(sel.evals) or 'none'}\nexpected   {selection.format_duration(est['total_s'])} on this machine" + (f"\n           {note}" if note else "")
                  + f"\ncommand    {selection.command(sel, opts.program, args.save or args.selection)}")
            return 0
        flow.up(sel, opts)
        return 0
    except selection.SelectionError as error:
        print(f"buffon up: {error}", file=sys.stderr)
        return EXIT_USAGE
    except flow.UpError as error:
        print(f"buffon up: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nbuffon up: interrupted. Installed harnesses and finished runs are kept; run the same command again to continue.", file=sys.stderr)
        return 130


def cmd_harnesses(args):
    from .up import listing, machine
    marks = listing.installed_marks(os.path.join(machine.home(), "installed.json"))
    rows = listing.harness_rows(marks=marks)
    print(json.dumps(rows, indent=1) if args.json else listing.harness_table(rows))
    return 0


def cmd_benches(args):
    from .up import estimate, listing, machine
    paths = machine.paths()
    rows = listing.bench_rows(estimate.cached_probe(paths["probe"], force=args.refresh), estimate.load_history(paths["timings"]))
    print(json.dumps(rows, indent=1) if args.json else listing.bench_table(rows))
    return 0


def cmd_site(args):
    if args.action == "schema":
        sys.stdout.write(sitelib.schema_markdown())
        return 0
    s = sitelib.load(args.site)
    print(json.dumps(s.describe(), indent=2))
    return 0


def cmd_lock(args):
    if args.check or args.online:
        problems = locklib.check() if args.check else []
        if args.online:
            problems += locklib.online()
        for p in problems:
            print(f"buffon: {p}", file=sys.stderr)
        if not problems:
            print(f"arms.lock ok (sha256 {locklib.lock_hash()})")
        return 1 if problems else 0
    locklib.write()
    print(f"wrote arms.lock (sha256 {locklib.lock_hash()})")
    return 0


def cmd_arms(args):
    for name, arm in manifest.load_all().items():
        state = f"HELD ({arm.held[:60]}...)" if arm.held else f"{arm.install_kind} (operator terms: run with --accept-terms {name})" if arm.operator_terms else arm.install_kind
        print(f"{name:16} {arm.version:14} {arm.spec['relation']:14} {state}")
    return 0


def cmd_mock(args):
    from .mock import MockServer, Transcript
    policy = Transcript(args.transcript).policy() if args.transcript else None
    with MockServer(policy=policy) as srv:
        print(f"mock listening on {srv.origin} (OpenAI /v1/chat/completions, /v1/responses, Anthropic /v1/messages)", flush=True)
        import time
        while True:
            time.sleep(3600)


def session_arms(arm_ids, arms):
    """The arms a session runs: the named ones, else every arm that is not held and runs by default (never an arm with operator terms)."""
    return list(arm_ids) if arm_ids else [n for n, a in arms.items() if not a.held and a.runs_by_default]


def build_run_bundle(s, arm_ids):
    """Build the bundle a bundle-mode Kubernetes session runs from (buffon/backend/bundle.py) into a new temporary directory, for the site's node architecture.
    Returns (directory, the arms in it). A named arm the bundle cannot carry is refused; when no arm was named, such an arm is left out with its reason printed."""
    import shutil
    import subprocess
    import tempfile
    from .arms import install
    from .backend import bundle

    arms = manifest.load_all()
    wanted = [n for n in session_arms(arm_ids, arms) if n not in arms or not arms[n].held]
    tmp = tempfile.mkdtemp(prefix="buffon-bundle-")
    try:
        print(f"buffon: building the bundle for linux-{s.kube.arch} in {tmp}", file=sys.stderr)
        summary = bundle.build(tmp, s.kube.arch, wanted, host_cache=s.local.cache_dir)
        for arm_id, why in sorted(summary["skipped"].items()):
            print(f"buffon: {arm_id} is not in the bundle: {why}", file=sys.stderr)
        if arm_ids and summary["skipped"]:
            raise BackendError(f"the bundle cannot carry the named arm(s) {', '.join(sorted(summary['skipped']))}; name arms installed from a pinned artifact, npm, or a Go source build")
        if not summary["arms"]:
            raise BackendError("no selected arm can run from a bundle")
    except (bundle.BundleError, install.InstallError, subprocess.CalledProcessError) as error:
        shutil.rmtree(tmp, ignore_errors=True)
        raise BackendError(f"bundle: {error}") from error
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return tmp, summary["arms"]


def prebuilt_run_bundle(s, path, arm_ids):
    """A bundle built beforehand: (its absolute path, the arms it carries). Refused when it is not a finished bundle, was built for another architecture than the
    site's nodes, or lacks a named arm."""
    from .backend import bundle
    try:
        meta = bundle.read_meta(path)
    except bundle.BundleError as error:
        raise BackendError(f"bundle: {error}") from error
    if meta.get("arch") != s.kube.arch:
        raise BackendError(f"bundle: {path} is built for {meta.get('arch')}, the site's nodes are {s.kube.arch}")
    missing = [a for a in (arm_ids or []) if a not in meta.get("arms", [])]
    if missing:
        skipped = meta.get("skipped") or {}
        why = "; ".join(f"{a}: {skipped.get(a, 'not built into it')}" for a in missing)
        raise BackendError(f"bundle: {path} does not carry {', '.join(missing)} ({why})")
    if not meta.get("arms"):
        raise BackendError(f"bundle: {path} carries no arm")
    return os.path.abspath(path), list(meta["arms"])


def session_plan(args):
    """Build an engine Plan from `session` flags."""
    from . import workloads
    from .runner import engine, hooks
    from .runner import facts as factlib

    arms = manifest.load_all()
    resolved = workloads.resolve(args.workloads)
    durable_only = bool(resolved) and all(w.envs for w in resolved)   # the durable family: its arms are the adapter arms, and its reference is the Pi Durable arm
    wanted = session_arms(resolve_arm_names(args.arms, arms) if args.arms else None, arms)
    if durable_only and not args.arms:
        wanted = [n for n, a in arms.items() if a.adapter and not a.held and not a.adapter.get("informational")]
    reference = args.reference
    if durable_only and reference == "pi-node" and "pi-node" not in wanted and wanted:
        reference = "pi-durable" if "pi-durable" in wanted else wanted[0]
    held = [n for n in wanted if arms[n].held]
    if held:
        print(f"buffon: held arms are listed but never run: {', '.join(held)}", file=sys.stderr)
    accept = manifest.accepted_terms(args.accept_terms)
    for n in wanted:
        if arms[n].operator_terms and n not in accept:
            raise SystemExit(f"buffon: {manifest.terms_refusal(arms[n])}")
    cpus, mock = args.cpus, parse_cpus(args.mock_cpus)
    if cpus == "inherit":
        allowed = factlib.allowed_cpus() if hasattr(os, "sched_setaffinity") else []   # a platform that cannot pin has no CPUs to inherit
        mock = allowed[-1:] if len(allowed) > 1 else []
        cpus = [c for c in allowed if c not in mock]
    else:
        cpus = parse_cpus(cpus)
    site = json.loads(os.environ.get("BUFFON_SITE_JSON") or "{}")
    slot, lock = None, args.lock_file or engine.quietlib.DEFAULT_LOCK
    if args.slot:
        slot_id, slot_of = (int(n) for n in args.slot.split("/"))
        slot = {"id": slot_id, "of": slot_of, "cpus": sitelib.format_cpus(cpus), "calibration": os.path.abspath(args.slot_calibration) if args.slot_calibration and slotlib.passed(args.slot_calibration, slot_id) else None}
        lock = args.lock_file or slotlib.lock_path(engine.quietlib.DEFAULT_LOCK, slot_id)
    return engine.Plan(workloads=resolved, arms=[arms[n] for n in wanted if not arms[n].held], apis=args.apis or list(engine.APIS), envs=list(args.envs or [workloads.NATIVE]), apis_explicit=args.apis is not None, rounds=args.rounds or engine.MIN_ROUNDS, rounds_set=args.rounds is not None, warmup=args.warmup,
                       aa=args.aa or "all", aa_set=args.aa is not None, reference=reference, cpus=cpus, mock_cpus=mock, pinning=args.pinning, seed=args.seed, timeout=args.timeout, rpc_turns=args.rpc_turns, long_turns=args.long_turns,
                       calibrate=not args.no_calibrate, memory_mib=args.memory_tier * 1024, calibration_rounds=args.calibration_rounds, adaptive=args.adaptive, strict=args.require_class == "A", allow_noisy=args.allow_noisy, allow_short=args.allow_short, allow_frequency_scaling=args.allow_frequency_scaling,
                       hardware_claim=args.hardware_claim, site=site, out=args.out or default_out(), command=["buffon"] + sys.argv[1:], params=parse_params(args.param),
                       lock_file=lock, lock_files=list(args.foreign_lock), slot=slot, slot_others=parse_cpus(args.slot_others), quiet_max_busy=args.quiet_max_busy, quiet_timeout_s=args.quiet_timeout,
                       quiet_max_runnable=args.quiet_max_runnable, host_claim=args.host_claim, clock_claim=args.clock_claim, isolation=args.isolation or "none", require_class=args.require_class, quiet_max_steal=args.quiet_max_steal, quiet_max_psi=args.quiet_max_psi, quiet_gate=not args.no_quiet_gate, observers=telemetry_observers(args) + [hooks.load(spec) for spec in args.observer],
                       cache_dir=args.cache_dir or sitelib.from_dict({}).local.cache_dir, work_dir=args.work_dir, offline=args.offline, npm_cache=args.npm_cache, meter=args.meter)


def telemetry_observers(args):
    """The default observer: per-sample telemetry (docs/TELEMETRY.md). It is on unless --no-telemetry, so a pod session records it without any flag forwarding."""
    if args.no_telemetry:
        return []
    from .telemetry.collector import SystemTelemetry
    return [SystemTelemetry(interval_s=args.telemetry_interval)]


def default_out():
    import time
    return os.path.join("runs", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))


def seal(run_dir):
    """Seal a finished run directory (MANIFEST.sha256, docs/SUBMITTING.md)."""
    from .submit import manifest
    if os.path.exists(os.path.join(run_dir, "raw.json")):
        manifest.write(run_dir)


def cmd_session(args):
    from .runner import engine
    plan = session_plan(args)
    try:
        raw = engine.run_session(plan)
    except engine.Refused as error:
        seal(plan.out)
        print(f"buffon: refused: {error}", file=sys.stderr)
        return EXIT_REFUSED
    seal(plan.out)
    print(f"buffon: run directory {plan.out}: {len(raw['samples'])} samples, hardware {raw['hardware']['class'].upper()}")
    return EXIT_EGRESS if raw["egress"]["violations"] else 0


# `buffon run` builds the session's argv itself; these flags it forwards above, every other run flag the operator gave goes through explicit_run_flags.
RUN_FORWARDED = {"workloads", "arms", "accept_terms", "apis", "envs", "rounds", "warmup", "aa", "reference", "seed", "timeout", "rpc_turns", "long_turns", "param", "out", "no_calibrate", "allow_noisy",
                 "allow_short", "allow_frequency_scaling"}


def explicit_run_flags(args):
    """The run flags given on the command line with a non-default value, as session arguments: without them `buffon run --isolation container` (or --no-quiet-gate,
    --observer, --lock-file, --quiet-*, --host-claim, --require-class) ran a session that never saw the flag."""
    probe = argparse.ArgumentParser(add_help=False)
    add_run_flags(probe)
    out = []
    for action in probe._actions:
        if not action.option_strings or action.dest in RUN_FORWARDED:
            continue
        value = getattr(args, action.dest, action.default)
        if value == action.default:
            continue
        flag = action.option_strings[0]
        if isinstance(action, argparse._StoreTrueAction):
            out.append(flag)
        elif isinstance(action, argparse._AppendAction):
            for item in value:
                out += [flag, str(item)]
        else:
            out += [flag, str(value)]
    return out


def cmd_run(args):
    from . import backend
    s = sitelib.load(args.site)
    if args.slot is not None or args.slot_calibration:
        if args.slot is None:
            print("buffon: --slot-calibration needs --slot", file=sys.stderr)
            return EXIT_USAGE
        try:
            slotlib.select(s, args.slot, args.slot_calibration)
        except slotlib.SlotError as error:
            print(f"buffon: refused: {error}", file=sys.stderr)
            return EXIT_REFUSED
    check_workloads(args.workloads)
    if args.arms:
        args.arms = resolve_arm_names(args.arms, manifest.load_all())
    for blocker in submission_blockers(args):
        print(f"buffon: this run cannot be submitted: {blocker}", file=sys.stderr)
    b = backend.get_backend(s)
    b.check(isolation=args.isolation)
    nodes = None
    if args.nodes and not args.calibration:
        raise BackendError("--nodes picks among the nodes a calibration vouches for; give --calibration too")
    if args.calibration:
        if s.backend != "kubernetes":
            raise BackendError("--calibration vouches for Kubernetes nodes; this site runs locally, where every session calibrates itself")
        nodes = calibrated_nodes(args.calibration)
        if args.nodes:
            wanted = [n for n in args.nodes.split(",") if n]
            outside = [n for n in wanted if n not in nodes]
            twice = sorted({n for n in wanted if wanted.count(n) > 1})
            if twice:
                print(f"buffon: --nodes {args.nodes} names {', '.join(twice)} twice: one session per node", file=sys.stderr)
                return EXIT_USAGE
            if outside or not wanted:
                print(f"buffon: refused: --nodes {args.nodes}: the calibration {args.calibration} does not vouch for {', '.join(outside) or 'an empty list'}", file=sys.stderr)
                return EXIT_REFUSED
            nodes = wanted
        code, text = b.check_calibration(args.calibration, nodes) if nodes else (EXIT_REFUSED, "the calibration passed no node")
        print(text)
        if code:
            print(f"buffon: refused: the calibration {args.calibration} does not vouch for a comparison on {', '.join(nodes) or 'any node'}", file=sys.stderr)
            return EXIT_REFUSED
    out = os.path.abspath(args.out or default_out())
    result = submit(args, s, b, out, nodes)
    reportable = [n["run_dir"] for n in result.facts.get("nodes", [])] or [out]
    if result.exit_code == 0 or any(os.path.exists(os.path.join(d, "raw.json")) for d in reportable):
        print(f"buffon: render the report with: python3 -m buffon report {' '.join(shlex.quote(d) for d in reportable)}")
    return result.exit_code


def calibrated_nodes(path):
    """The nodes a calibration.json vouches for, in its order: the ones that passed on their own. A noisy or unjudged node is left out, and said so."""
    with open(path) as f:
        doc = json.load(f)
    judged = doc.get("nodes") or []
    if not judged or not all(isinstance(n.get("node"), str) and n.get("node") for n in judged):
        raise BackendError(f"{path} names no calibrated nodes; write it with `buffon calibrate`")
    left_out = [n["node"] for n in judged if n.get("pass") is not True]
    if left_out:
        print(f"buffon: the calibration does not vouch for {', '.join(left_out)} (noisy or not judged); the run leaves them out", file=sys.stderr)
    return [n["node"] for n in judged if n.get("pass") is True]


def cmd_calibrate(args):
    """Run the reference arm against its own A/A copy on the site's nodes (one pod each with `nodes` or `spread`), then judge every metric's noise over the nodes with the site's
    max_cv (`buffon-cluster calibrate`). Writes <out>/calibration.json, which `buffon run --calibration` checks before a comparison."""
    from . import backend
    s = sitelib.load(args.site)
    if s.backend != "kubernetes":
        raise BackendError("buffon calibrate judges Kubernetes nodes; a local session calibrates itself (the A/A gate of docs/METHODOLOGY.md)")
    if args.arms and args.arms != [args.reference]:
        raise BackendError(f"buffon calibrate runs the reference arm against its own copy; name it with --reference, not --arms {' '.join(args.arms)}")
    b = backend.get_backend(s)
    b.check()
    # The cross-node gate judges every sample; the session's own A/A gate would stop a noisy node before it measured anything.
    args.arms, args.aa, args.no_calibrate = [args.reference], args.reference, True
    out = os.path.abspath(args.out or default_out())
    result = submit(args, s, b, out, None)
    dirs = [n["run_dir"] for n in result.facts.get("nodes", [])] or [out]
    dirs = [d for d in dirs if os.path.exists(os.path.join(d, "cluster-facts.json"))]
    if not dirs:
        print("buffon: no node handed back a run directory to judge", file=sys.stderr)
        return result.exit_code or 1
    path = os.path.join(out, "calibration.json")
    code, text = b.calibrate(dirs, path)
    print(text)
    if code:
        print(f"buffon: refused: the noise floor exceeds max_cv {s.kube.max_cv}; {path} records which node and metric", file=sys.stderr)
        return EXIT_REFUSED
    print(f"buffon: wrote {path}; compare on these nodes with: python3 -m buffon run ... --site {shlex.quote(args.site or os.environ.get('BUFFON_SITE', ''))} --calibration {shlex.quote(path)}")
    return result.exit_code


def submit(args, s, b, out, nodes):
    """Run one session through the backend: build its argv from the run flags and the site, build the bundle a bundle site needs, and report how it ended."""
    from . import backend
    argv = [sys.executable, "-m", "buffon", "session", *args.workloads, *(["--apis", *args.apis] if args.apis else []), *(["--envs", *args.envs] if args.envs else []), *(["--rounds", str(args.rounds)] if args.rounds is not None else []), "--warmup", str(args.warmup), *(["--aa", args.aa] if args.aa is not None else []),
            "--reference", args.reference, "--seed", str(args.seed), "--timeout", str(args.timeout), "--rpc-turns", str(args.rpc_turns), "--long-turns", str(args.long_turns), "--out", out,
            "--pinning", s.local.pinning if s.backend == "local" else "required", "--hardware-claim", s.hardware, "--meter", s.local.meter]
    bundle_dir, prebuilt = None, getattr(args, "bundle", None)
    if s.backend != "local" and (getattr(args, "offline", False) or getattr(args, "cache_dir", "") or getattr(args, "npm_cache", "")):
        raise BackendError("--offline, --cache-dir and --npm-cache are for a local site; a Kubernetes site gets its caches from its image or bundle")
    if prebuilt and not (s.backend == "kubernetes" and s.kube.bundle):
        raise BackendError("--bundle is for a Kubernetes site with bundle = true; this site runs an image or runs locally")
    if prebuilt:
        bundle_dir, bundled = prebuilt_run_bundle(s, prebuilt, args.arms)
        if not args.arms:
            argv += ["--arms", *bundled]
    elif s.backend == "kubernetes" and s.kube.bundle:
        bundle_dir, bundled = build_run_bundle(s, args.arms)
        if not args.arms:
            argv += ["--arms", *bundled]   # the session runs what the bundle carries, never an arm it would have to fetch
    if args.arms:
        argv += ["--arms", *args.arms]
        gated = {n: a for n, a in manifest.load_all().items() if a.operator_terms and n in args.arms}
        accept = manifest.accepted_terms(args.accept_terms)
        for n, a in gated.items():
            if n not in accept:
                raise BackendError(manifest.terms_refusal(a))
        if gated:
            argv += ["--accept-terms", ",".join(gated)]
    for item in args.param:
        argv += ["--param", item]
    argv += ["--telemetry-interval", str(args.telemetry_interval)]
    for flag in ("no_calibrate", "allow_noisy", "allow_short", "allow_frequency_scaling", "no_telemetry"):
        if getattr(args, flag):
            argv.append("--" + flag.replace("_", "-"))
    if s.backend == "local":
        if s.local.cpus:
            argv += ["--cpus", sitelib.format_cpus(s.local.cpus)]
        if s.local.mock_cpus:
            argv += ["--mock-cpus", sitelib.format_cpus(s.local.mock_cpus)]
        argv += ["--cache-dir", getattr(args, "cache_dir", "") or s.local.cache_dir]
        if getattr(args, "offline", False):
            argv.append("--offline")
        if getattr(args, "npm_cache", ""):
            argv += ["--npm-cache", args.npm_cache]
        if s.local.work_dir:
            argv += ["--work-dir", s.local.work_dir]
        if s.local.allow_frequency_scaling and "--allow-frequency-scaling" not in argv:
            argv.append("--allow-frequency-scaling")
        for path in s.local.lock_files:
            argv += ["--foreign-lock", path]
        argv += ["--host-claim", s.local.host_claim] + (["--require-class", s.local.require_class] if s.local.require_class else []) + (["--clock-claim", s.local.clock_claim] if s.local.clock_claim else [])
        argv += ["--quiet-max-busy", str(s.local.quiet_max_busy), "--quiet-timeout", str(s.local.quiet_timeout_s), "--quiet-max-runnable", str(s.local.quiet_max_runnable),
                 "--quiet-max-steal", str(s.local.quiet_max_steal), "--quiet-max-psi", str(s.local.quiet_max_psi)]
        if s.local.slot:
            slot = s.local.slot
            argv += ["--slot", f"{slot['id']}/{slot['of']}", "--slot-others", sitelib.format_cpus(slot["others"])] + (["--slot-calibration", slot["calibration"]] if slot["calibration"] else [])
    else:
        argv += ["--cpus", "inherit"]
        if s.kube.allow_frequency_scaling and "--allow-frequency-scaling" not in argv:   # the site's own statement reaches the session of every step: a calibration on nodes the profile allows to scale their clock is not refused for it
            argv.append("--allow-frequency-scaling")
        if args.isolation is None:   # the pod is the envelope when it holds P1-P5, else the session stamps it uncontained; an --isolation the operator gave goes through below
            argv += ["--isolation", "pod-guaranteed"]
    argv += explicit_run_flags(args)   # last, so a flag the operator gave wins over the site's value
    session = backend.Session(argv=argv, run_dir=out, cpus=s.kube.cpus if s.backend == "kubernetes" else len(s.local.cpus), env={"BUFFON_SITE_JSON": json.dumps(s.describe())}, bundle=bundle_dir,
                              nodes=nodes)
    try:
        result = b.run(session)
    finally:
        if bundle_dir and not prebuilt:
            import shutil
            shutil.rmtree(bundle_dir, ignore_errors=True)
    seal(out)
    for n in result.facts.get("nodes", []):   # a run on several nodes leaves one run directory per node: each is sealed with what the cluster added
        seal(n["run_dir"])
    print(f"buffon: session finished (exit {result.exit_code}); run directory {result.run_dir}")
    for n in result.facts.get("nodes", []):
        print(f"buffon: node {n['node']}: exit {n['exit_code']}, node class {n['node_class']}, run directory {n['run_dir']}")
    return result


def cmd_external(args):
    from .external import results, runner, suites
    if args.action == "suites":
        for s in suites.SUITES.values():
            print(f"{s.id}\t{s.licence}\t{'live' if s.live else 'offline'}\t{','.join(sorted(s.targets))}\t{s.title}")
        return 0
    if args.action == "import" and args.family:
        if not (args.out and args.files):
            print("buffon: external import --family needs --out DIR and the files", file=sys.stderr)
            return 2
        from .external import published
        try:
            doc = published.import_family(args.family, args.files, args.out)
        except (ValueError, OSError) as error:
            print(f"buffon: refused: {error}", file=sys.stderr)
            return 3
        print(f"buffon: imported {len(doc['files'])} file(s) for {args.family} into {args.out}; the table matches the source")
        return 0
    if args.action == "plan":
        if not (args.suite and args.target and args.checkout):
            print("buffon: external plan needs --suite, --target and --checkout", file=sys.stderr)
            return 2
        doc = runner.plan(args.suite, args.target, args.checkout, arm=args.arm, command=args.command, commit=args.commit, allow_live=args.live)
        print(json.dumps(doc, indent=1, sort_keys=True))
        return 0 if doc["verdict"] == "would run" else 3
    if args.action == "import":
        if not (args.meta and args.out and args.files):
            print("buffon: external import needs --meta FILE --out DIR and the files", file=sys.stderr)
            return 2
        try:
            with open(args.meta) as f:
                doc = results.import_files(args.files, args.out, json.load(f))
        except (ValueError, OSError) as error:
            print(f"buffon: {error}", file=sys.stderr)
            return 2
        print(f"buffon: imported {len(doc['files'])} file(s) into {args.out}")
        return 0
    if not (args.suite and args.target and args.checkout and args.out):
        print("buffon: external run needs --suite, --target, --checkout and --out", file=sys.stderr)
        return 2
    try:
        doc = runner.run(args.suite, args.target, args.checkout, args.out, arm=args.arm, command=args.command, commit=args.commit, cpus=args.cpus, allow_live=args.live,
                         timeout=args.timeout, foreign_locks=args.foreign_lock, env=dict(e.split('=', 1) for e in args.env if '=' in e))
    except (runner.Refused, ValueError) as error:
        print(f"buffon: refused: {error}", file=sys.stderr)
        return 3
    print(f"buffon: {doc['suite']} on {doc['target']} exited {doc['exit']} in {doc['wall_s']} s; output in {args.out}")
    if doc["egress"]:
        print(f"buffon: egress violation: the suite connected to {', '.join(doc['egress'])}", file=sys.stderr)
        return 4
    return 0 if doc["exit"] == 0 else 1


def cmd_report(args):
    from .report import render
    return render.main(args)


def cmd_grade(args):
    from .report import grade as gradelib, grade_inputs, grade_render, render
    path = args.dir if args.dir.endswith(".json") else os.path.join(args.dir, "report.json")
    try:
        with open(path) as f:
            inputs = json.load(f).get("grade_inputs")
        if not inputs:
            print(f"buffon: {path} has no grade_inputs: it predates the grade, run `buffon report` again", file=sys.stderr)
            return 2
        file_weights = None
        if args.weights:
            with open(args.weights, "rb") as f:
                file_weights = tomllib.load(f)
        if args.faithfulness is not None:
            docs = render.faithfulness_docs(args.faithfulness)
            inputs["faithfulness"] = grade_inputs.faithfulness_scores(docs)
            inputs["correctness"] = {a: v for a, v in grade_inputs.correctness_failures(docs).items() if v}
        weights = gradelib.weights_for(args.profile, file_weights)
        result = gradelib.grade(inputs, weights, seed=args.seed, resamples=args.resamples, profile=args.profile if not file_weights else args.profile + "+file", strict=args.strict)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
        print(f"buffon: grade: {e}", file=sys.stderr)
        return 2
    lines = grade_render.write_all(result, args.out) if args.out else grade_render.leaderboard(result)
    print(json.dumps(result, indent=1, default=lambda x: None if isinstance(x, float) and x != x else x) if args.json else "\n".join(lines))
    return 0


def cmd_verify(args):
    from .submit import check
    rc = 0
    reports = []
    for d in args.dirs:
        result = check.verify(d, args.repo, is_submission=args.submission, reference=args.reference)
        reports.append(dict(result.as_dict(), dir=d, notes=getattr(result, "health", {}).get("notes")))
        if not args.json:
            print(check.text(result, d))
        rc = rc or (0 if result.accepted else 1)
    if args.json:
        print(json.dumps(reports, indent=1))
    return rc


def cmd_promote(args):
    from .arms import manifest as armmanifest
    from .submit import promote
    try:
        target, record = promote.promote(args.run, args.repo or armmanifest.ROOT, to=args.to, run_id=args.id)
    except promote.PromotionRefused as error:
        print(f"buffon: {error}", file=sys.stderr)
        return 1
    print(f"buffon: promoted {target}: {record['notes']} run notes, manifest {record['manifest_sha256'][:12]}")
    return 0


def cmd_index(args):
    from .arms import manifest as armmanifest
    from .submit import index
    repo = args.repo or armmanifest.ROOT
    if args.immutable_against:
        problems = index.immutable_problems(args.results, args.immutable_against, repo, governance=args.allow_governance)
        for p in problems:
            print(f"buffon: {p}", file=sys.stderr)
        if problems:
            return 1
    if args.check:
        problems = index.check(args.results, repo)
        for p in problems:
            print(f"buffon: {p}", file=sys.stderr)
        print("results index ok" if not problems else f"results index: {len(problems)} problems")
        return 1 if problems else 0
    try:
        rows = index.write(args.results, repo)
    except index.IndexProblem as error:
        print(f"buffon: {error}", file=sys.stderr)
        return 1
    print(f"buffon: indexed {len(rows)} results in {args.results}")
    return 0


def cmd_compare(args):
    from .submit import reproduce
    c = reproduce.compare(args.original, args.yours)
    path = reproduce.write(c, args.out or args.yours)
    print(f"buffon: wrote {path}: {c['totals']['reproduced']} of {c['totals']['cells']} comparisons reproduce; {c['noise']['sentence']}")
    return 0


def cmd_reproduce(args):
    from .submit import reproduce
    from .arms import lock as lockmod
    from .runner import raw as rawlib
    original = rawlib.read(args.original)
    mine = lockmod.lock_hash() if os.path.exists(lockmod.LOCK_FILE) else None
    if original.get("lock_sha256") != mine:
        print(f"buffon: this checkout's arms.lock ({str(mine)[:12]}) is not the one the run used ({str(original.get('lock_sha256'))[:12]}): check out the run's runner commit "
              f"({str((original.get('runner') or {}).get('commit'))[:12]}) first, or the runs would not use the same pins", file=sys.stderr)
        return EXIT_REFUSED
    out = os.path.abspath(args.out or default_out())
    rc = main(reproduce.run_argv(args.original, args.site, out))
    if os.path.exists(os.path.join(out, "raw.json")):
        c = reproduce.compare(args.original, out)
        print(f"buffon: wrote {reproduce.write(c, out)}: {c['totals']['reproduced']} of {c['totals']['cells']} comparisons reproduce; {c['noise']['sentence']}")
    return rc


def find_run(run_id, extra=()):
    """The run directory named `run_id`: a path that exists, else results/<id>, runs/<id> or <dir>/<id> for each --runs-dir."""
    for base in ("", "results", "runs", *extra):
        path = os.path.join(base, run_id) if base else run_id
        if os.path.isfile(os.path.join(path, "raw.json")):
            return path
    raise SystemExit(f"buffon: no run directory {run_id!r} with a raw.json under results/, runs/ or --runs-dir; fetch it from the published results first")


def cmd_rerun(args):
    from .report import cellid
    from .submit import reproduce
    from .arms import lock as lockmod
    from .runner import raw as rawlib
    try:
        run_id, scenario, api, metric = cellid.parse(args.cell)
        original = find_run(run_id, args.runs_dir)
        workloads, apis, arms = reproduce.cell_plan(original, scenario, api, metric)
    except cellid.CellIdError as error:
        print(f"buffon: {error}", file=sys.stderr)
        return EXIT_USAGE
    raw = rawlib.read(original)
    mine = lockmod.lock_hash() if os.path.exists(lockmod.LOCK_FILE) else None
    out = os.path.abspath(args.out or default_out())
    argv = reproduce.run_argv(original, args.site, out, workloads=workloads, apis=apis, arms=arms)
    if args.print_only:
        print(shlex.join(["python3", "-m", "buffon", *argv]))
        return 0
    if raw.get("lock_sha256") != mine:
        print(f"buffon: this checkout's arms.lock ({str(mine)[:12]}) is not the one the run used ({str(raw.get('lock_sha256'))[:12]}): check out the run's runner commit "
              f"({str((raw.get('runner') or {}).get('commit'))[:12]}) first, or the runs would not use the same pins", file=sys.stderr)
        return EXIT_REFUSED
    rc = main(argv)
    if os.path.exists(os.path.join(out, "raw.json")):
        c = reproduce.compare(original, out)
        shown = [r for r in c["cells"] if r["scenario"] == scenario and r["api"] == api and r["metric"] == metric]
        print(f"buffon: wrote {reproduce.write(c, out)}: {sum(r['reproduced'] for r in shown)} of {len(shown)} comparisons of {args.cell} reproduce; {c['noise']['sentence']}")
    return rc


def cmd_perfcheck(args):
    from . import perfcheck
    return perfcheck.main(args)


def cmd_health(args):
    from .report import health, render
    if args.dirs == ["thresholds"]:
        sys.stdout.write(health.thresholds_markdown())
        return 0
    doc = render.health_of(args.dirs)
    if args.json:
        print(json.dumps(doc, indent=1, default=lambda x: None if isinstance(x, float) and x != x else x))
    else:
        print(health.badge(doc))
        for c in doc["checks"]:
            if c["status"] == "note":
                print(f"  note {health.describe(c)}")
    return 0


def cmd_arm(args):
    from . import armverify
    return armverify.arm_verify(args)


def cmd_faithfulness(args):
    from .faithfulness import report, runner
    if args.action == "report":
        print(f"buffon: wrote {report.render(args.dirs, args.out)}")
        return 0
    if args.action == "probes":
        from .faithfulness import probes as probelib
        text = open(args.dirs[0]).read() if args.dirs else sys.stdin.read()
        for p in probelib.all_probes(text, args.pi_source):
            print(f"{p.id}\t{p.dim}\t{p.cite}\t{p.title}")
        return 0
    arms = args.arms if args.arms is not None else [a for a, m in manifest.load_all().items() if not m.held]
    out = os.path.abspath(args.out or default_out().replace("runs", "faithfulness", 1))
    doc = runner.run([a for a in arms if a != args.reference], args.reference, out, args.pi_source, args.only, args.cache_dir, args.work_dir, args.timeout, offline=args.offline)
    report.render([out], os.path.join(out, "faithfulness.md"))
    print(f"buffon: faithfulness run directory {out}")
    for a, sc in doc["scores"].items():
        print(f"buffon: {a:14} overall {report.fmt(sc['overall'])}")
    violations = doc.get("egress", {}).get("violations") or []
    if violations:
        print(f"buffon: egress violations in {len(violations)} probe(s): " + "; ".join(f"{v['arm']} -> {', '.join(v['remotes'])}" for v in violations), file=sys.stderr)
        return 4
    return 0


def cmd_preflight(args):
    from .runner import preflight
    cpus, mock = parse_cpus(args.cpus or ""), parse_cpus(args.mock_cpus or "")
    clock = getattr(args, "clock_claim", "")
    if args.site:
        local = sitelib.load(args.site).local
        cpus, mock, clock = cpus or local.cpus, mock or local.mock_cpus, clock or local.clock_claim
    report = preflight.run(cpus, mock, claim=args.host_claim, clock_claim=clock)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"host class {report['class']} (claim {report['claim']})")
        for c in report["checks"]:
            print(f"  {'ok  ' if c['ok'] else 'FAIL'} {c['name']}: {c['detail']}")
    if args.require_class and not preflight.satisfies(report, args.require_class):
        print(f"buffon: this host is class {report['class']}, class {args.require_class} was required", file=sys.stderr)
        return 3
    return 0


def cmd_sysinfo(args):
    from .runner import sysinfo
    doc = sysinfo.collect(parse_cpus(args.cpus), parse_cpus(args.mock_cpus))
    with open(args.out, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"buffon: wrote {args.out}")
    return 0


def cmd_campaign(args):
    from . import campaign
    return campaign.main(args)


def cmd_agentbench(args):
    from .agentbench import cli as agentcli
    if args.action == "plan":
        agentcli.plan(args.protocol, args.out)
    else:
        if not args.observations:
            raise SystemExit("buffon: agentbench result needs --observations")
        agentcli.result(args.protocol, args.observations, args.out)
    print(f"buffon: agentbench {args.action} written to {args.out}")
    return 0


def cmd_dashboard(args):
    from .dashboard import build
    return build.main(args)


COMMANDS = {"up": cmd_up, "harnesses": cmd_harnesses, "benches": cmd_benches, "grade": cmd_grade, "promote": cmd_promote, "index": cmd_index, "reproduce": cmd_reproduce, "perfcheck": cmd_perfcheck, "rerun": cmd_rerun, "compare": cmd_compare, "health": cmd_health, "preflight": cmd_preflight, "sysinfo": cmd_sysinfo, "verify": cmd_verify, "agentbench": cmd_agentbench, "campaign": cmd_campaign, "faithfulness": cmd_faithfulness, "run": cmd_run, "calibrate": cmd_calibrate, "session": cmd_session, "report": cmd_report, "dashboard": cmd_dashboard, "external": cmd_external, "lock": cmd_lock, "arms": cmd_arms, "arm": cmd_arm, "site": cmd_site, "mock": cmd_mock}
