# SPDX-License-Identifier: Apache-2.0
"""Compatibility row: @ff-labs/pi-fff 0.11.0, unmodified, on Pi and on PiG.

The extension (MIT) is installed once from npm into one directory; every implementation loads that same `src/index.ts` with `-e`. Each (implementation, mode) runs one `--mode rpc`
session against the scripted mock model in a hermetic home and agent directory at FIXED paths (the extension writes its LMDB databases under PI_CODING_AGENT_DIR and prints paths),
emptied before each run, over a fixed project tree. A session records

  * the commands the extension registers (`get_commands`),
  * the tools the model request declares (name, description, parameter schema),
  * the flags it registers (`--fff-mode` etc.: a run that passes each flag must be accepted),
  * every tool's result as the RPC stream reports it (the model calls each registered fff tool once),
  * the notifications and status the extension raises for /fff-health, /fff-mode, /fff-mode override and /fff-rescan, and the tools declared after the mode change.

The first implementation is the oracle; any other whose record differs is reported field by field. Exit code 1 on a difference.

usage: python3 tools/compat_fff.py --fff DIR --impl NAME=BINARY ... [--modes tools-and-ui tools-only override] [--out DIR]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buffon.mock import MockServer, Step  # noqa: E402

ROOT = "/tmp/fffcompat"
HOME = f"{ROOT}/home"
AGENT = f"{HOME}/.agent"
PROJECT = f"{ROOT}/project"
MODES = ("tools-and-ui", "tools-only", "override")
FFF_TOOLS = ("ffgrep", "fffind", "fff-multi-grep", "grep", "find", "multi_grep")


def make_project():
    shutil.rmtree(PROJECT, ignore_errors=True)
    files = {
        "README.md": "# fixture\nThe needle is in the haystack.\n",
        "src/alpha.ts": "export const alpha = 1;\n// needle in alpha\nexport function haystackAlpha() { return 'needle'; }\n",
        "src/beta.ts": "export const beta = 2;\nexport function beta2() { return 'haystack'; }\n",
        "src/nested/gamma.go": "package nested\n\n// Gamma holds the needle.\nfunc Gamma() string { return \"needle\" }\n",
        "docs/notes.md": "needle\nneedle needle\nnothing here\n",
        "docs/unrelated.txt": "lorem ipsum\n",
    }
    for rel, body in files.items():
        os.makedirs(os.path.dirname(os.path.join(PROJECT, rel)), exist_ok=True)
        with open(os.path.join(PROJECT, rel), "w") as f:
            f.write(body)
    subprocess.run(["git", "init", "-q"], cwd=PROJECT, check=True)
    subprocess.run(["git", "add", "-A"], cwd=PROJECT, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "fixture"], cwd=PROJECT, check=True)


def write_config(base_url):
    shutil.rmtree(ROOT + "/home", ignore_errors=True)
    for d in (AGENT, f"{HOME}/tmp", f"{HOME}/.config", f"{HOME}/.local/share", f"{HOME}/.cache", f"{HOME}/.local/state"):
        os.makedirs(d, exist_ok=True)
    with open(f"{AGENT}/models.json", "w") as f:
        json.dump({"providers": {"bench": {"baseUrl": base_url, "api": "openai-completions", "apiKey": "compat-dummy-key",
                                           "models": [{"id": "bench-1", "name": "Bench 1", "contextWindow": 128000, "maxTokens": 4096}]}}}, f)
    with open(f"{AGENT}/settings.json", "w") as f:
        json.dump({"defaultProvider": "bench", "defaultModel": "bench-1", "quietStartup": True, "collapseChangelog": True}, f)


def env_for(path, extra=()):
    keep = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL") if k in os.environ}
    keep.update({"HOME": HOME, "XDG_CONFIG_HOME": f"{HOME}/.config", "XDG_DATA_HOME": f"{HOME}/.local/share", "XDG_CACHE_HOME": f"{HOME}/.cache",
                 "XDG_STATE_HOME": f"{HOME}/.local/state", "TMPDIR": f"{HOME}/tmp", "NO_COLOR": "1", "TERM": "xterm-256color", "PI_CODING_AGENT_DIR": AGENT,
                 "PIG_CODING_AGENT_DIR": AGENT, "PI_OFFLINE": "1", "PI_SKIP_VERSION_CHECK": "1", "PI_TELEMETRY": "0", "NO_PROXY": "127.0.0.1,localhost",
                 "PIG_HOME": f"{HOME}/.pig"})
    keep.update(dict(e.split("=", 1) for e in extra))
    return keep


class Rpc:
    def __init__(self, argv, env, cwd):
        self.records, self.cond, self.n = [], threading.Condition(), 0
        self.err = open(f"{ROOT}/stderr.txt", "wb+")
        self.proc = subprocess.Popen(argv, env=env, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err, start_new_session=True)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            with self.cond:
                self.records.append(rec)
                self.cond.notify_all()

    def send(self, cmd):
        self.n += 1
        cmd = dict(cmd, id=f"c{self.n}")
        self.proc.stdin.write((json.dumps(cmd) + "\n").encode())
        self.proc.stdin.flush()
        return cmd["id"]

    def wait(self, pred, timeout, start=0):
        end = time.monotonic() + timeout
        with self.cond:
            while True:
                for i in range(start, len(self.records)):
                    if pred(self.records[i]):
                        return i, self.records[i]
                left = end - time.monotonic()
                if left <= 0 or self.proc.poll() is not None and not self.cond.wait(0.2):
                    if self.proc.poll() is not None or left <= 0:
                        return None
                self.cond.wait(min(max(left, 0), 0.2))

    def call(self, cmd, timeout=60):
        ident = self.send(cmd)
        got = self.wait(lambda r: r.get("type") == "response" and r.get("id") == ident, timeout)
        return got[1] if got else None

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
        self.err.seek(0)
        return self.err.read().decode(errors="replace")


def descendants(pid):
    out, todo = [], [pid]
    while todo:
        p = todo.pop()
        kids = subprocess.run(["pgrep", "-P", str(p)], capture_output=True, text=True).stdout.split()
        for k in kids:
            out.append(int(k))
            todo.append(int(k))
    return out


def census(pid):
    exes = []
    for d in descendants(pid):
        try:
            exes.append(os.path.basename(os.readlink(f"/proc/{d}/exe")))
        except OSError:
            pass
    return {"children": len(exes), "executables": sorted(set(exes))}


def scrub(v):
    """Remove what differs between two runs of the same implementation: tool-call ids and timings."""
    if isinstance(v, dict):
        return {k: scrub(x) for k, x in v.items() if k not in ("id", "toolCallId", "timestamp", "durationMs", "elapsedMs", "startedAt")}
    if isinstance(v, list):
        return [scrub(x) for x in v]
    return v


def policy_for(order):
    def policy(request):
        k = request.rounds()
        names = [n for n in order if n in (request.tools or [])]
        if k < len(names):
            n = names[k]
            args = {"patterns": ["needle", "haystack"]} if n in ("fff-multi-grep", "multi_grep") else {"pattern": "needle" if "grep" in n else "alpha"}
            return Step(tool_calls=[(n, args)])
        return Step(text="done")
    return policy


def run_one(name, binary, mode, fff_dir, flags, timeout, extra_env=(), cwd="project", extra_ext=()):
    make_project()
    with MockServer(policy=policy_for(FFF_TOOLS)) as server:
        write_config(server.base_url)
        argv = [binary, "--mode", "rpc", "--provider", "bench", "--model", "bench-1", "--no-session", "-e", f"{fff_dir}/src/index.ts", *[a for e in extra_ext for a in ("-e", e)], "--fff-mode", mode, *flags]
        rpc = Rpc(argv, env_for(binary, extra_env), PROJECT if cwd == "project" else HOME)
        rec = {}
        try:
            st = rpc.call({"type": "get_state"}, 120)
            if st is None:
                return {"failure": "no get_state response", "stderr": rpc.close()[-800:]}
            # the extension's tools are registered at session_start; the commands too. Wait until the fff commands are listed.
            deadline, cmds = time.monotonic() + 60, []
            while time.monotonic() < deadline:
                r = rpc.call({"type": "get_commands"}, 30)
                cmds = sorted((c.get("name"), c.get("description")) for c in ((r or {}).get("data") or {}).get("commands", []) if str(c.get("name", "")).startswith("fff"))
                if len(cmds) >= 3:
                    break
                time.sleep(0.2)
            rec["commands"] = cmds
            rec["startup_ui"] = [scrub({k: r.get(k) for k in ("method", "message", "notifyType", "statusKey", "statusText")}) for r in rpc.records if r.get("type") == "extension_ui_request"]
            rec["census"] = census(rpc.proc.pid)
            start = len(rpc.records)
            rpc.send({"type": "prompt", "message": "Use the search tools."})
            end = rpc.wait(lambda r: r.get("type") == "agent_end", timeout, start)
            if end is None:
                return {"failure": "no agent_end", "stderr": rpc.close()[-800:]}
            reqs = [r for r in server.requests if r.fault is None and r.tools]
            first = reqs[0]
            declared = {}
            for t in first.body.get("tools") or []:
                fn = t.get("function", t)
                declared[fn["name"]] = {"description": fn.get("description"), "parameters": fn.get("parameters")}
            rec["declared_names"] = sorted(declared)
            rec["declared_fff"] = {n: d for n, d in declared.items() if n in FFF_TOOLS and (n.startswith("fff") or n == "ffgrep" or mode == "override")}
            rec["results"] = [scrub({k: r.get(k) for k in ("toolName", "args", "result", "isError")}) for r in rpc.records[start:] if r.get("type") == "tool_execution_end"]
            rec["model_requests"] = len(reqs)
            # commands: /fff-health, /fff-mode (query), /fff-mode override, /fff-mode tools-and-ui, /fff-rescan
            ui = {}
            for label, msg in (("health", "/fff-health"), ("mode", "/fff-mode"), ("mode_bad", "/fff-mode nonsense"), ("mode_override", "/fff-mode override"),
                               ("mode_back", "/fff-mode tools-and-ui"), ("rescan", "/fff-rescan")):
                s = len(rpc.records)
                rpc.call({"type": "prompt", "message": msg}, 60)
                time.sleep(1.0)
                ui[label] = [scrub({k: r.get(k) for k in ("method", "message", "notifyType", "statusKey", "statusText")}) for r in rpc.records[s:]
                             if r.get("type") == "extension_ui_request"]
            rec["ui"] = ui
        finally:
            stderr = rpc.close()
        rec["stderr_has_error"] = [ln for ln in stderr.splitlines() if "rror" in ln][:5]
        return rec


def screens(binary, mode, fff_dir, extra_ext=()):
    """Interactive mode in tmux: type `@alp`, then Tab; the editor and popup lines (blank lines dropped) after each step."""
    make_project()
    with MockServer() as server:
        write_config(server.base_url)
        env = env_for(binary)
        session = "parity-fffcompat-" + hashlib.sha256(binary.encode()).hexdigest()[:8]
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
        cmd = [binary, "--provider", "bench", "--model", "bench-1", "--no-session", "-e", f"{fff_dir}/src/index.ts", *[a for e in extra_ext for a in ("-e", e)], "--fff-mode", mode]
        envs = " ".join(f"{k}={subprocess.list2cmdline([v])}" for k, v in env.items())
        subprocess.run(["tmux", "new-session", "-d", "-s", session, "-x", "100", "-y", "30", "-c", PROJECT, "env -i " + envs + " " + subprocess.list2cmdline(cmd)], check=True)

        def shot():
            out = subprocess.run(["tmux", "capture-pane", "-p", "-t", session], capture_output=True, text=True).stdout
            return [ln.rstrip() for ln in out.splitlines() if ln.strip()]
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and not any("bench-1" in ln for ln in shot()):
                time.sleep(0.3)
            time.sleep(4)   # the finder's first scan settles
            rec = {}
            subprocess.run(["tmux", "send-keys", "-t", session, "-l", "@alp"])
            time.sleep(3)
            rec["typed"] = shot()
            subprocess.run(["tmux", "send-keys", "-t", session, "Tab"])
            time.sleep(2)
            rec["completed"] = shot()
            subprocess.run(["tmux", "send-keys", "-t", session, "C-u"])
            subprocess.run(["tmux", "send-keys", "-t", session, "-l", "/fff-"])
            time.sleep(2)
            rec["slash"] = shot()
            return rec
        finally:
            subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)


def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in sorted(set(a) | set(b)) if k != "census" for d in diff(a.get(k), b.get(k), f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {canonical(a)[:200]} != {canonical(b)[:200]}"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fff", help="the installed @ff-labs/pi-fff package directory; default: the frozen fixture (fixtures/external/pi-fff, npm ci --offline from the cache)")
    ap.add_argument("--cache", default="/tmp/ext-frozen/npm-cache")
    ap.add_argument("--impl", action="append", required=True, help="NAME=BINARY; the first is the oracle")
    ap.add_argument("--modes", nargs="*", default=list(MODES))
    ap.add_argument("--flag", action="append", default=[], help="extra argv passed to every implementation, e.g. --fff-follow-symlinks=true")
    ap.add_argument("--env", action="append", default=[], help="K=V for every implementation")
    ap.add_argument("--extra-ext", action="append", default=[], help="another extension loaded with -e next to pi-fff (packs with it on PiG)")
    ap.add_argument("--skip", action="append", default=[], help="a record field (top or top.sub) left out of the comparison, e.g. results or ui.health")
    ap.add_argument("--autocomplete", action="store_true", help="interactive mode in tmux (the @ file completion and the slash menu) instead of rpc")
    ap.add_argument("--cwd", choices=("project", "home"), default="project")
    ap.add_argument("--out", default=f"{ROOT}/out")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()
    if not args.fff:
        from tools import external_ext
        dest = external_ext.install("pi-fff", "/tmp/ext-frozen/pi-fff", args.cache)
        print("frozen:", ", ".join(f"{n} {i[:19]}" for n, i in external_ext.record(dest) if n.startswith("@ff-labs/pi-fff")))
        args.fff = os.path.join(dest, "node_modules", "@ff-labs", "pi-fff")
    impls = [i.split("=", 1) for i in args.impl]
    os.makedirs(args.out, exist_ok=True)
    failed = False
    for mode in args.modes:
        recs = {}
        for name, binary in impls:
            recs[name] = screens(binary, mode, args.fff, args.extra_ext) if args.autocomplete else run_one(name, binary, mode, args.fff, args.flag, args.timeout, args.env, args.cwd, args.extra_ext)
            with open(f"{args.out}/{mode}-{name}.json", "w") as f:
                json.dump(recs[name], f, indent=1, sort_keys=True)
            print(f"{mode:13s} {name:22s} {hashlib.sha256(canonical(recs[name]).encode()).hexdigest()[:12]}"
                  + (f"  FAILED {recs[name]['failure']}" if "failure" in recs[name] else f"  census {recs[name].get('census')}"), flush=True)
        for rec in recs.values():
            for dotted in args.skip:
                top, _, sub = dotted.partition(".")
                if sub and isinstance(rec.get(top), dict):
                    rec[top].pop(sub, None)
                elif not sub:
                    rec.pop(top, None)
        oracle = impls[0][0]
        for name, _ in impls[1:]:
            d = diff(recs[oracle], recs[name])
            if d:
                failed = True
                print(f"  {mode}: {name} differs from {oracle}:")
                for line in d[:15]:
                    print("    " + line)
    print("EQUIVALENT" if not failed else "DIFFERENCES")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
