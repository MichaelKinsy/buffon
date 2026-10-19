# SPDX-License-Identifier: Apache-2.0
"""Run an upstream suite as it is and keep its output next to the facts a reader needs to judge it.

The run takes the host lock (one measured thing at a time), refuses a checkout that is not at the pinned commit or has tracked changes, refuses a suite that needs a live model without an explicit opt-in,
and runs the suite's own command in the checkout with the host's credentials removed from the environment. It writes `external-suite.json` (command, commit, exit status, times, host.json) plus the
suite's stdout and stderr. It writes no `raw.json`: an external suite's numbers are the suite's, and no buffon cell can be built from them.
"""
import json
import os
import re
import subprocess
import time

from ..runner import quiet, sysinfo
from . import KIND_SUITE, guard, suites
from .rows import parse_console_table

SECRET = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
TAIL = 4000


Refused = guard.Refused


def git(checkout, *args):
    return subprocess.run(["git", "-C", checkout, *args], capture_output=True, text=True, check=False).stdout.strip()


def caller_commit(target, commit):
    """The sha of a caller's --commit, given as SHA or as KEY=SHA (the form the docs and refusals name); a KEY that is not the target's repository is refused."""
    if not commit or "=" not in commit:
        return commit
    key, _, sha = commit.partition("=")
    if key != target.repo:   # review: `--commit pi=<sha>` was compared with HEAD as the literal "pi=<sha>", so the documented form always refused
        raise Refused(f"--commit {commit}: {key!r} is not this target's repository {target.repo!r}")
    return sha


def check_checkout(suite, target, checkout, commit=None):
    pin = caller_commit(target, commit) or suite.pins.get(target.repo)
    if not os.path.isdir(checkout):
        raise Refused(f"checkout {checkout} does not exist")
    head = git(checkout, "rev-parse", "HEAD")
    if not pin:
        raise Refused(f"{suite.id} has no pinned commit for {target.repo}: pass --commit {target.repo}=<sha> (a run without a pin cannot be reproduced)")
    if not re.fullmatch(r"[0-9a-f]{40}", head):   # not a git checkout (rev-parse printed nothing): an empty head used to match every pin
        raise Refused(f"checkout {checkout} is not a git checkout with a commit")
    if not re.fullmatch(r"[0-9a-f]{7,40}", pin.lower()) or not head.startswith(pin.lower()):
        raise Refused(f"checkout {checkout} is at {head[:12]}, the pin is {pin[:12]}")
    if git(checkout, "status", "--porcelain", "--untracked-files=no"):
        raise Refused(f"checkout {checkout} has tracked changes: the suite runs as it is upstream")
    untracked = git(checkout, "status", "--porcelain", "--untracked-files=all")
    if untracked:   # review: an untracked file joins the suite unseen (Pi's bench config includes test/**/*.bench.ts); ignored files (node_modules, build output) are not listed
        raise Refused(f"checkout {checkout} has untracked files ({untracked.splitlines()[0][3:]} ...): an added file can change what the suite runs; remove it or run from a clean checkout")
    return head


PASS_THROUGH = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM")


def clean_env(home, extra=None):
    """The environment an upstream suite sees: a short allow-list (PATH, locale, TZ, TERM), a HOME inside the run directory, and what the caller names with `extra`. Nothing of the operator's PI_*, PIG_*, agent directories, credentials or HOME reaches the suite."""
    env = {k: os.environ[k] for k in PASS_THROUGH if k in os.environ}
    env["HOME"] = home
    env.update({k: v for k, v in (extra or {}).items() if not SECRET.search(k)})
    return env


class Completed:
    def __init__(self, returncode, stdout, stderr):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def metered(argv, cwd, env, timeout, **_):
    """Run argv under a meter so the socket audit reads its process tree: a connection outside loopback is recorded (R10's rule, for suites too). Returns Completed with `.egress`;
    a timeout raises subprocess.TimeoutExpired carrying `.egress` too (a suite that hangs on a remote connection is the case most likely to have one)."""
    from ..runner import cgroup, egress
    egress.take()
    meter = cgroup.new_meter()
    expired = None
    try:
        proc = meter.popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", start_new_session=True)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            meter.kill()
            out, err = proc.communicate()
            expired = subprocess.TimeoutExpired(argv, timeout, output=out, stderr=err)
    finally:
        meter.close()
    left = sorted(egress.take())
    if expired is not None:
        expired.egress = left
        raise expired
    done = Completed(proc.returncode, out, err)
    done.egress = left
    return done


def run(suite_id, target_name, checkout, out, arm=None, command=None, commit=None, cpus=None, allow_live=False, timeout=2700, foreign_locks=(), env=None, runner=metered):
    """Run the suite's command for the target; returns the written record. `runner` is the subprocess seam for tests."""
    suite = suites.get(suite_id)
    target, argv = suites.argv_for(suite, target_name, arm, command)
    if suite.live and not allow_live:
        raise Refused(f"{suite.id} needs a real model and spends money: run it through `buffon agentbench` and pass --live")
    head = check_checkout(suite, target, checkout, commit)
    verified = guard.verify(checkout, target.manifest, suite.id)
    workdir = os.path.join(checkout, target.cwd)
    if cpus:
        argv = ["taskset", "-c", cpus, *argv]
    os.makedirs(out, exist_ok=True)
    home = os.path.join(os.path.abspath(out), "home")
    os.makedirs(home, exist_ok=True)
    started = time.monotonic()
    with quiet.HostLock(own=quiet.default_lock(), foreign=foreign_locks):
        t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            done = runner(argv, cwd=workdir, env=clean_env(home, env), timeout=timeout)
            code, stdout, stderr, timed_out, left = done.returncode, done.stdout, done.stderr, False, list(getattr(done, "egress", []))
        except subprocess.TimeoutExpired as e:
            code, timed_out, left = None, True, list(getattr(e, "egress", []))
            stdout, stderr = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        except OSError as e:
            code, stdout, stderr, timed_out, left = 127, "", str(e), False, []
    wall = time.monotonic() - started
    for name, text in (("stdout.txt", stdout), ("stderr.txt", stderr)):
        with open(os.path.join(out, name), "w") as f:
            f.write(text)
    try:
        host = sysinfo.collect([int(c) for c in re.split(r"[,\s]+", cpus) if c.isdigit()] if cpus else [])
    except Exception as error:  # the host description is best effort here; a suite's output is still kept
        host = {"unavailable": repr(error)}
    doc = {"kind": KIND_SUITE, "suite": suite.id, "title": suite.title, "licence": suite.licence, "target": target_name, "arm": arm, "repo": target.repo, "commit": head, "argv": argv, "cwd": target.cwd,
           "exit": code, "timed_out": timed_out, "egress": left, "started_utc": t0, "wall_s": round(wall, 3), "stdout_tail": stdout[-TAIL:], "stderr_tail": stderr[-TAIL:], "notes": suite.notes, "host": host,
           "label": "the suite's own numbers, run as it is upstream; not a buffon measurement and in no buffon aggregate"}
    doc.update({"pins": {target.repo: head}, "pin_source": "caller" if commit else "suite", "manifest": verified, "units": dict(target.units), "table": target.table or None})
    if target.table == "console-table":
        try:
            table_rows = parse_console_table(stdout)
        except ValueError as error:   # review: the suite already ran; a table the parser cannot read is recorded, never a lost run
            table_rows, doc["rows_error"] = None, str(error)
        if table_rows is not None:
            with open(os.path.join(out, "rows.jsonl"), "w") as f:
                for row in table_rows:
                    f.write(json.dumps(row) + "\n")
        doc["rows"] = None if table_rows is None else len(table_rows)
    with open(os.path.join(out, "external-suite.json"), "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True, default=str)
    return doc


def plan(suite_id, target_name, checkout, arm=None, command=None, commit=None, allow_live=False):
    """What `run` would do, with nothing started: the argv, the pin, and the state of each named file. `refusals` lists every reason the guard would refuse; it is empty when the run would start."""
    suite = suites.get(suite_id)
    target, argv = suites.argv_for(suite, target_name, arm, command)
    refusals = []
    if suite.live and not allow_live:
        refusals.append(f"{suite.id} needs a real model and spends money: pass --live through `buffon agentbench`")
    try:
        check_checkout(suite, target, checkout, commit)
    except Refused as error:
        refusals.append(str(error))
    files = {}
    if target.manifest and os.path.isdir(checkout):
        files = {rel: {"state": state, "pinned_sha256": pinned, "sha256": actual} for rel, (state, pinned, actual) in guard.status(checkout, target.manifest).items()}
    try:
        guard.verify(checkout, target.manifest, suite.id)
    except Refused as error:
        refusals.append(str(error))
    try:
        pin = caller_commit(target, commit) or suite.pins.get(target.repo)
    except Refused:
        pin = commit
    return {"suite": suite.id, "target": target_name, "repo": target.repo, "argv": argv, "cwd": os.path.join(checkout, target.cwd), "pin": pin,
            "pin_source": "caller" if commit else "suite", "files": files, "started": False, "refusals": refusals, "verdict": "refused" if refusals else "would run"}


def section(dirs):
    """The report's `External suites` section: one row per run directory."""
    docs = []
    for d in dirs:
        with open(os.path.join(d, "external-suite.json")) as f:
            doc = json.load(f)
        if doc.get("kind") != KIND_SUITE:
            raise ValueError(f"{d} is not an external suite run")
        docs.append((d, doc))
    if not docs:
        return []
    out = ["## External suites (run as they are upstream)", "",
           "Each row is one upstream suite, started unchanged from a checkout at the commit shown, on the host in that run directory. The suite's own output (`stdout.txt`) is the result; Buffon computes nothing from it and puts "
           "it in no cell, aggregate or verdict.", "", "| suite | target | arm | commit | exit | wall s | run directory |", "|---|---|---|---|---:|---:|---|"]
    for d, doc in docs:
        status = "timed out" if doc["timed_out"] else doc["exit"]
        if doc.get("egress"):
            status = f"{status}, EGRESS to {', '.join(doc['egress'])}"
        if doc.get("rows_error"):
            status = f"{status}, table not parsed"
        pin = " (caller's commit, not the suite's pin)" if doc.get("pin_source") == "caller" else ""   # review: a commit the caller chose must not read as the registry pin
        out.append(f"| {doc['suite']} | {doc['target']} | {doc.get('arm') or '-'} | `{doc['commit'][:12]}`{pin} | {status} | {doc['wall_s']} | `{os.path.basename(os.path.abspath(d))}` |")
    out.append("")
    return out
