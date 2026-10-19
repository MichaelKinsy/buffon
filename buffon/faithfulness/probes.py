# SPDX-License-Identifier: Apache-2.0
"""The probe set (v0). A probe is a scripted situation, run identically on the reference and on a harness; its observation is a normalised JSON value, and the harness matches the
reference when the two observations are equal. Each probe cites the Pi source (or `pi --help`) it comes from. F1 probes are generated from the reference's own `--help` (and the
line of Pi's argument parser when a source tree is given), so the set grows with Pi."""
import json
import os
import re
from dataclasses import dataclass, field

from ..mock import MODEL, Step
from . import canon, wire
from .lab import Skip

# Machine-facing dimensions (F2 wire, F4 session, F6 output modes, F7 extensions) weigh more than human-facing ones (F1 CLI text, F8 TUI): scripts, extensions and resumed sessions break on them.
DIMENSIONS = {
    "F1": ("CLI surface", 5),
    "F2": ("Wire fidelity", 25),
    "F3": ("Tool behaviour", 15),
    "F4": ("Session format", 15),
    "F5": ("Config compatibility", 10),
    "F6": ("Output modes", 20),
    "F7": ("Extension compatibility", 10),
    "F8": ("TUI", 0),   # not implemented in v0: listed, weight 0
}
APIS = ("openai-completions", "openai-responses", "anthropic-messages")
EXT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fixtures", "faithfulness", "ext")
SRC = "packages/coding-agent/src"


@dataclass
class Probe:
    id: str
    dim: str
    title: str
    cite: str
    run: object                      # run(ctx, arm) -> JSON-compatible normalised observation; raises Skip when the arm has no such mode
    applies: object = None           # applies(arm) -> reason string when the probe is N/A for the arm, else None
    ref_ok: object = None            # ref_ok(observation) -> False when the reference's own observation shows the probe could not exercise anything (a helper tool Pi needs is absent): the probe is invalid, listed, never scored


# -- helpers ----------------------------------------------------------------------------------------------------------------------------------

def norm_for(ctx, arm, setup):
    names = arm.spec.get("faithfulness", {}).get("names") or [os.path.basename(arm.binary), os.path.basename(arm.binary).capitalize()]
    install = [(arm.install_dir, "<install>"), (os.path.realpath(arm.install_dir), "<install>")] if arm.install_dir else []
    paths = [(setup.cwd, "<cwd>"), (os.path.realpath(setup.cwd), "<cwd>"), (setup.agent_dir, "<agent>"), (setup.home, "<home>"), (os.path.realpath(setup.home), "<home>"),
             (setup.session_dir, "<sessions>"), (ctx.lab.ws.root, "<ws>"), (os.path.realpath(ctx.lab.ws.root), "<ws>"), *install]
    return canon.Normalizer(paths, names, arm.version.split("+")[0], ctx.lab.server.port)


def project_dir(arm):
    return arm.spec.get("faithfulness", {}).get("project_dir", ".pi")


def base_api(arm, api):
    if not arm.supports_api(api):
        raise Skip(f"it does not speak {api}")
    return api


def one_print(ctx, arm, pid, api, steps=None, policy=None, prompt="Say hello.", extra=(), prepare=None, session=None, mode="print", **harness_kw):
    """Prepare a harness, let `prepare(setup)` lay out files, run print mode; returns (obs, norm)."""
    base_api(arm, api)
    setup = ctx.lab.prepare(arm, pid, api, **harness_kw)
    if prepare:
        prepare(setup)
    path = session(setup) if callable(session) else session
    argv = ctx.lab.argv_for(arm, setup, mode, extra, prompt, path)
    obs = ctx.lab.run(arm, setup, argv, steps=steps, policy=policy, timeout=ctx.timeout)
    return obs, norm_for(ctx, arm, setup)


def first_request(obs):
    if not obs.requests:
        raise Skip(f"it sent no request (exit {obs.exit}); stderr: {obs.stderr.strip()[:120]}")
    return obs.requests[0]


# -- F2 wire fidelity ---------------------------------------------------------------------------------------------------------------------------

def wire_scenarios():
    readme = {"path": "README.md"}
    return {
        "hello": ([Step(text="Hello there.")], "Say hello."),
        "tool": ([Step(tool_calls=[("read", readme)]), Step(text="Done.")], "Read README.md and summarise it."),
    }


def wire_projection(sub, protocol, bodies, norm):
    if sub == "keys":
        return [sorted(canon.key_paths(b)) for b in bodies]
    if sub == "order":
        return [{p: [list(o) for o in orders] for p, orders in canon.key_orders(b).items()} for b in bodies]
    if sub == "scalars":
        return [sorted([list(x) for x in canon.scalars(b, norm)], key=json.dumps) for b in bodies]   # order is the `order` probe's business
    if sub == "system":
        return [norm.text(wire.system_text(protocol, b)) for b in bodies]
    if sub == "tools":
        return [[[norm.text(n), norm.text(d), norm.value(p)] for n, d, p in wire.tool_defs(protocol, b)] for b in bodies]
    if sub == "messages":
        return [[[r, k, norm.value(list(p) if isinstance(p, tuple) else p)] for r, k, p in wire.messages(protocol, b)] for b in bodies]
    raise KeyError(sub)


def wire_probes():
    out = []
    for scenario in wire_scenarios():
        for api in APIS:
            for sub in ("keys", "order", "scalars", "system", "tools", "messages"):
                pid = f"F2.{scenario}.{api.split('-')[-1]}.{sub}"

                def run(ctx, arm, scenario=scenario, api=api, sub=sub, pid=pid):
                    steps, prompt = wire_scenarios()[scenario]
                    obs, norm = one_print(ctx, arm, pid, api, steps=steps, prompt=prompt)
                    first_request(obs)
                    return wire_projection(sub, api, [r.body for r in obs.requests], norm)
                out.append(Probe(pid, "F2", f"request {sub}, {scenario} script, {api}", f"{SRC}/core/agent-session.ts (request assembly); `pi-ai` provider for {api}", run))
    return out


# -- F3 tool behaviour --------------------------------------------------------------------------------------------------------------------

FIXTURE = {"README.md": "Benchmark fixture.\nSecond line.\nThird line.\n", "src/a.txt": "alpha\nbeta\ngamma\n", "src/b.txt": "beta only\n", "docs/notes.md": "# Notes\nBenchmark notes.\n"}
PROP_VALUES = {"path": "README.md", "file_path": "README.md", "filePath": "README.md", "content": "new content\n", "command": "echo hi && ls", "pattern": "beta", "glob": "*.txt",
               "oldText": "Second line.", "newText": "Replaced line.", "old_text": "Second line.", "new_text": "Replaced line.", "oldString": "Second line.", "newString": "Replaced line.",
               "old_string": "Second line.", "new_string": "Replaced line.", "offset": 1, "limit": 2, "timeout": 10, "edits": [{"oldText": "Second line.", "newText": "Replaced line."}]}
TOOL_CASES = {
    "read": {}, "read-range": {"path": "src/a.txt", "offset": 2, "limit": 1}, "read-missing": {"path": "nope.txt"},
    "write": {"path": "out/new.txt", "content": "written\n"},
    "edit": {}, "edit-nomatch": {"edits": [{"oldText": "does not occur", "newText": "x"}], "oldText": "does not occur", "oldString": "does not occur", "old_text": "does not occur", "old_string": "does not occur"},
    "bash": {}, "bash-fail": {"command": "echo out; echo err 1>&2; exit 3"},
    "grep": {"path": "."}, "find": {"pattern": "*.txt", "path": "."}, "ls": {"path": "."},
}


def tool_args(case, schema):
    tool = case.split("-")[0]
    props = (schema or {}).get("properties") or {}
    args = {k: PROP_VALUES[k] for k in props if k in PROP_VALUES and (k in (schema.get("required") or []) or k in ("path", "pattern", "command", "content", "oldText", "newText", "edits"))}
    if tool == "find":
        args.pop("path", None) if "path" not in props else None
    args.update({k: v for k, v in TOOL_CASES[case].items() if not props or k in props or k in ("path",)})
    return args


def tool_probes():
    out = []
    for case in TOOL_CASES:
        tool = case.split("-")[0]
        pid = f"F3.{case}"

        def run(ctx, arm, tool=tool, case=case, pid=pid):
            def policy(req):
                if req.index == 0:
                    if tool not in req.tools:
                        return Step(text="no such tool")
                    return Step(tool_calls=[(tool, tool_args(case, req.schemas.get(tool)))])
                return Step(text="Done.")

            def prepare(setup):
                for rel, text in FIXTURE.items():
                    setup.write(rel, text)
            extra = ("--tools", "read,bash,edit,write,grep,find,ls") if tool in ("grep", "find", "ls") else ()  # Pi enables these three only on request (`--tools` in `pi --help`)
            obs, norm = one_print(ctx, arm, pid, "openai-completions", policy=policy, prompt=f"Use the {tool} tool.", prepare=prepare, extra=extra)
            first_request(obs)
            present = tool in obs.requests[0].tools
            result = None
            if len(obs.requests) > 1:
                msgs = wire.messages("openai-completions", obs.requests[1].body)
                result = next((norm.text(p) for r, k, p in reversed(msgs) if r == "tool"), None)
            return {"tool_present": present, "result": result, "files": {norm.text(k): norm.text(v) for k, v in sorted(obs.files.items())}}
        out.append(Probe(pid, "F3", f"built-in tool {case} on the fixture tree", f"{SRC}/core/tools/{tool}.ts", run,
                         ref_ok=lambda o: "is not available" not in (o.get("result") or "")))
    return out


# -- F4 sessions -------------------------------------------------------------------------------------------------------------------------

def session_script():
    return [Step(tool_calls=[("read", {"path": "README.md"})]), Step(text="Done reading.")], "Read README.md."


def session_view(sessions, norm):
    """The structure of the written session files: per record its type, its key set, and for messages the role and content shape."""
    out = []
    for name in sorted(sessions):
        if not name.endswith(".jsonl"):
            continue
        for line in sessions[name].splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                out.append(["<not json>"])
                continue
            shape = [rec.get("type"), sorted(rec)]
            msg = rec.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                kinds = [b.get("type") for b in content] if isinstance(content, list) else type(content).__name__
                shape += [msg.get("role"), sorted(msg), kinds]
            out.append(shape)
    return out


def session_path(setup):
    return os.path.join(setup.session_dir, "s.jsonl")


def written(ctx, arm, pid):
    steps, prompt = session_script()
    return one_print(ctx, arm, pid, "openai-completions", steps=steps, prompt=prompt, mode="print_session", session=session_path,
                     prepare=lambda s: s.write("README.md", FIXTURE["README.md"]))


def resume_view(ctx, arm, pid, file_text):
    """Resume a session file with `arm` and report the history its first request carried."""
    def prepare(setup):
        setup.write("README.md", FIXTURE["README.md"])
        os.makedirs(setup.session_dir, exist_ok=True)
        with open(session_path(setup), "w") as f:
            f.write(file_text)
    obs, norm = one_print(ctx, arm, pid, "openai-completions", steps=[Step(text="Again.")], prompt="And once more.", mode="print_session", session=session_path, prepare=prepare)
    req = first_request(obs)
    return [[r, k, norm.value(list(p) if isinstance(p, tuple) else p)] for r, k, p in wire.messages("openai-completions", req.body)]


def pi_session_text(ctx):
    """The session the reference wrote for the standard script (cached per run)."""
    if "pi_session" not in ctx.cache:
        obs, _ = written(ctx, ctx.ref_arm, "F4.reference-session")
        ctx.cache["pi_session"] = next((v for k, v in sorted(obs.sessions.items()) if k.endswith(".jsonl")), "")
    return ctx.cache["pi_session"]


def session_probes():
    out = []

    def write_run(view):
        def run(ctx, arm, view=view):
            obs, norm = written(ctx, arm, f"F4.write.{view}")
            full = session_view(obs.sessions, norm)
            if not full:
                if "pi-sessions" in getattr(arm, "claims", ()):   # review: a harness that claims Pi sessions and writes none lost the session (data loss), not n/a
                    return {"session_written": False, "exit": obs.exit}
                raise Skip(f"it wrote no session file (exit {obs.exit})")
            return {"header": full[0], "types": [r[0] for r in full], "records": full}[view]
        return run
    for view, title in (("header", "session header record"), ("types", "record type sequence"), ("records", "record shapes")):
        out.append(Probe(f"F4.write.{view}", "F4", f"a session written by the harness: {title}", f"{SRC}/core/session-manager.ts", write_run(view)))

    def resume_run(ctx, arm):
        return resume_view(ctx, arm, "F4.resume-pi-session", pi_session_text(ctx))
    out.append(Probe("F4.resume-pi-session", "F4", "the harness resumes a session Pi wrote: history sent", f"{SRC}/core/session-manager.ts (loadEntries, buildSessionContext)", resume_run))

    def reverse_run(ctx, arm):
        obs, _ = written(ctx, arm, "F4.reverse.write")
        text = next((v for k, v in sorted(obs.sessions.items()) if k.endswith(".jsonl")), "")
        if not text:
            if "pi-sessions" in getattr(arm, "claims", ()):
                return {"session_written": False, "exit": obs.exit}
            raise Skip("it wrote no session file")
        return resume_view(ctx, ctx.ref_arm, "F4.reverse.resume", text)
    out.append(Probe("F4.pi-resumes-harness-session", "F4", "Pi resumes a session the harness wrote: history sent", f"{SRC}/core/session-manager.ts", reverse_run))
    return out


# -- F5 config ------------------------------------------------------------------------------------------------------------------------------

def sys_probe(pid, title, cite, prepare, extra=(), prompt="Say hello.", view="system", **kw):
    def run(ctx, arm):
        obs, norm = one_print(ctx, arm, pid, "openai-completions", prompt=prompt, prepare=(lambda s: prepare(s, arm)) if prepare else None, extra=extra, **kw)
        req = first_request(obs)
        if view == "system":
            return norm.text(wire.system_text("openai-completions", req.body))
        if view == "messages":
            return [[r, k, norm.value(list(p) if isinstance(p, tuple) else p)] for r, k, p in wire.messages("openai-completions", req.body)]
        return norm.text(req.auth or "")
    return Probe(pid, "F5", title, cite, run)


def marker_view(probe):
    """Reduce a system-prompt probe to where its marker lands: present or not and the line before it, so the whole prompt text is judged only by F2.system."""
    inner = probe.run

    def run(ctx, arm):
        text = inner(ctx, arm)
        lines = text.splitlines()
        hits = [i for i, ln in enumerate(lines) if "CFG-MARK" in ln]
        return {"present": bool(hits), "context": [lines[hits[0] - 1].strip()[:80] if hits and hits[0] else None, lines[hits[0]].strip()[:200] if hits else None]}
    probe.run = run
    return probe


def config_probes():
    mark = "CFG-MARK instructions for the project.\n"
    skill = "---\nname: cfg-skill\ndescription: CFG-MARK skill description\n---\nSkill body.\n"
    out = [
        marker_view(sys_probe("F5.agents-md", "AGENTS.md in the project is added to the system prompt", f"{SRC}/core/resource-loader.ts (context files)", lambda s, a: s.write("AGENTS.md", mark))),
        marker_view(sys_probe("F5.claude-md", "CLAUDE.md in the project is added to the system prompt", f"{SRC}/core/resource-loader.ts (context files)", lambda s, a: s.write("CLAUDE.md", mark))),
        marker_view(sys_probe("F5.global-agents-md", "AGENTS.md in the agent directory is added to the system prompt", f"{SRC}/core/resource-loader.ts", lambda s, a: s.write("AGENTS.md", mark, base="agent"))),
        marker_view(sys_probe("F5.no-context-files", "--no-context-files leaves AGENTS.md out", f"{SRC}/cli/args.ts (--no-context-files)", lambda s, a: s.write("AGENTS.md", mark), extra=("--no-context-files",))),
        marker_view(sys_probe("F5.skill", "a skill in the agent directory is listed in the system prompt", f"{SRC}/core/skills.ts", lambda s, a: s.write("skills/cfg-skill/SKILL.md", skill, base="agent"))),
        marker_view(sys_probe("F5.skill-project", "a project skill is listed once the project is approved (--approve)", f"{SRC}/core/skills.ts", lambda s, a: s.write(f"{project_dir(a)}/skills/cfg-skill/SKILL.md", skill),
                              extra=("--approve",))),
        marker_view(sys_probe("F5.no-skills", "--no-skills leaves the skill out", f"{SRC}/cli/args.ts (--no-skills)", lambda s, a: s.write("skills/cfg-skill/SKILL.md", skill, base="agent"), extra=("--no-skills",))),
        sys_probe("F5.prompt-template", "a prompt template in the agent directory expands from /name", f"{SRC}/core/prompt-templates.ts", lambda s, a: s.write("prompts/hello.md", "Say hello to $1 politely.\n", base="agent"),
                  prompt="/hello world", view="messages"),
        sys_probe("F5.prompt-template-project", "a project prompt template expands once the project is approved (--approve)", f"{SRC}/core/prompt-templates.ts",
                  lambda s, a: s.write(f"{project_dir(a)}/prompts/hello.md", "Say hello to $1 politely.\n"), prompt="/hello world", view="messages", extra=("--approve",)),
        sys_probe("F5.system-prompt-flag", "--system-prompt replaces the default system prompt", f"{SRC}/cli/args.ts (--system-prompt)", None, extra=("--system-prompt", "CFG-MARK only this"), view="system"),
        sys_probe("F5.append-system-prompt-flag", "--append-system-prompt adds text to the system prompt", f"{SRC}/cli/args.ts (--append-system-prompt)", None, extra=("--append-system-prompt", "CFG-MARK appended"),
                  view="system"),
        sys_probe("F5.auth-header", "the apiKey of models.json is sent as the credential", f"{SRC}/core/model-registry.ts", None, view="auth"),
    ]
    out[-3].run = _trim(out[-3].run, "CFG-MARK only this")
    out[-2].run = _trim(out[-2].run, "CFG-MARK appended")
    return out


def _trim(inner, needle):
    """For a system-prompt flag, judge whether the text is there and what surrounds it, not the whole default prompt."""
    def run(ctx, arm):
        text = inner(ctx, arm)
        return {"contains": needle in text, "is_exactly_it": text.strip() == needle, "length_class": "short" if len(text) < 2 * len(needle) + 40 else "long"}
    return run


# -- F6 output modes --------------------------------------------------------------------------------------------------------------------------

def collapse(seq):
    out = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def json_events(stdout, norm):
    events = []
    for line in stdout.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            events.append(["<not json>"])
            continue
        events.append([rec.get("type"), sorted(rec)])
    return events


def output_probes():
    out = []

    def text_run(steps, prompt, pid):
        def run(ctx, arm):
            obs, norm = one_print(ctx, arm, pid, "openai-completions", steps=steps, prompt=prompt, prepare=lambda s: s.write("README.md", FIXTURE["README.md"]))
            return {"exit": obs.exit, "stdout": norm.text(obs.stdout)}
        return run
    out.append(Probe("F6.print-text", "F6", "print mode: stdout and exit code of a text answer", f"{SRC}/modes/print-mode.ts", text_run([Step(text="Hello there.")], "Say hello.", "F6.print-text")))
    out.append(Probe("F6.print-tool", "F6", "print mode: stdout and exit code after a tool call", f"{SRC}/modes/print-mode.ts",
                     text_run([Step(tool_calls=[("read", {"path": "README.md"})]), Step(text="Read it.")], "Read README.md.", "F6.print-tool")))

    def json_run(view):
        def run(ctx, arm, view=view):
            steps = [Step(tool_calls=[("read", {"path": "README.md"})]), Step(text="Read it.")]
            obs, norm = one_print(ctx, arm, f"F6.json.{view}", "openai-completions", steps=steps, prompt="Read README.md.", extra=("--mode", "json"), prepare=lambda s: s.write("README.md", FIXTURE["README.md"]))
            ev = json_events(obs.stdout, norm)
            if not ev:
                raise Skip(f"no event stream (exit {obs.exit}); stderr: {obs.stderr.strip()[:100]}")
            if view == "types":
                return collapse([e[0] for e in ev])
            if view == "keys":
                return {t: sorted({tuple(e[1]) for e in ev if e[0] == t}) for t in sorted({e[0] for e in ev if e[0]})}
            return {"exit": obs.exit}
        return run
    for view, title in (("types", "event type sequence"), ("keys", "key set of every event type"), ("exit", "exit code")):
        out.append(Probe(f"F6.json.{view}", "F6", f"--mode json: {title}", f"{SRC}/modes/print-mode.ts (json output)", json_run(view)))

    def rpc_run(view):
        def run(ctx, arm, view=view):
            setup = ctx.lab.prepare(arm, f"F6.rpc.{view}", "openai-completions")
            setup.write("README.md", FIXTURE["README.md"])
            prompt = {"type": "prompt", "message": "Say hello."}
            if arm.rpc_dialect.get("prompt_field"):
                prompt = {"type": "prompt", arm.rpc_dialect["prompt_field"]: "Say hello."}
            obs = ctx.lab.run_rpc(arm, setup, [{"type": "get_state"}, prompt], steps=[Step(text="Hello there.")], wait=lambda rpc: any(r.get("type") == "agent_end" for _, r in rpc.records))
            if obs.timed_out and not obs.records:
                raise Skip("no rpc output")
            recs = obs.records
            if view == "events":
                return collapse([r.get("type") for r in recs if r.get("type") != "response"])
            if view == "responses":
                return [[r.get("command"), r.get("success"), sorted(r.get("data") or {}) if isinstance(r.get("data"), dict) else None] for r in recs if r.get("type") == "response"]
            return {t: sorted({tuple(sorted(r)) for r in recs if r.get("type") == t}) for t in sorted({r.get("type") for r in recs if r.get("type") not in (None, "response")})}
        return run
    for view, title in (("events", "event type sequence for one prompt"), ("responses", "command responses (command, success, data keys)"), ("keys", "key set of every event type")):
        out.append(Probe(f"F6.rpc.{view}", "F6", f"--mode rpc: {title}", f"{SRC}/modes/rpc/rpc-mode.ts", rpc_run(view)))
    return out


# -- F7 extensions ----------------------------------------------------------------------------------------------------------------------------

def ext_na(arm):
    kind = arm.pi_extensions
    return None if kind in ("native", "sidecar") else ("it loads no Pi extensions" if kind == "none" else "it loads only part of Pi's extensions; probes need the full API")


def ext_probes():
    out = []
    path = lambda n: os.path.join(EXT_DIR, n)

    def mk(pid, title, ext, steps, prompt, view):
        def run(ctx, arm):
            obs, norm = one_print(ctx, arm, pid, "openai-completions", steps=steps, prompt=prompt, extra=("-e", path(ext)), prepare=lambda s: s.write("README.md", FIXTURE["README.md"]))
            if view == "command":
                last = obs.requests[-1].body if obs.requests else {}
                users = [norm.text(p) for r, k, p in wire.messages("openai-completions", last) if r == "user"][-1:]
                return {"requests": len(obs.requests), "user": users, "exit": obs.exit}
            req = first_request(obs)
            if view == "tools":
                return [[norm.text(n), norm.text(d), norm.value(p)] for n, d, p in wire.tool_defs("openai-completions", req.body) if n and "fx" in n]
            if view == "system":
                sys_text = norm.text(wire.system_text("openai-completions", req.body))
                return {"marker": "FX-MARK-SYSTEM" in sys_text}
            if view == "toolresult":
                msgs = wire.messages("openai-completions", obs.requests[1].body) if len(obs.requests) > 1 else []
                return next((norm.text(p) for r, k, p in reversed(msgs) if r == "tool"), None)
        return Probe(pid, "F7", title, "packages/coding-agent/examples/extensions/ (ExtensionAPI: registerTool, on, registerCommand)", run, applies=ext_na)
    out.append(mk("F7.register-tool", "an extension tool appears in the tool list with its schema", "fx-tool.ts", [Step(text="ok")], "hi", "tools"))
    out.append(mk("F7.tool-result", "an extension tool runs and its result reaches the model", "fx-tool.ts", [Step(tool_calls=[("fx_tool", {"value": "x"})]), Step(text="ok")], "use it", "toolresult"))
    out.append(mk("F7.tool-call-block", "a tool_call handler can block a call", "fx-block.ts", [Step(tool_calls=[("read", {"path": "README.md"})]), Step(text="ok")], "read", "toolresult"))
    out.append(mk("F7.system-prompt-hook", "before_agent_start can extend the system prompt", "fx-system.ts", [Step(text="ok")], "hi", "system"))
    out.append(mk("F7.slash-command", "a registered slash command runs and can send a user message", "fx-command.ts", [Step(text="ok")], "/fx now", "command"))
    return out


# -- F1 CLI surface (generated from the reference's help) ---------------------------------------------------------------------------------------

VALUES = {"--provider": "bench", "--model": MODEL, "--api-key": "k", "--system-prompt": "SYS", "--append-system-prompt": "APPEND", "--mode": "json", "--session-id": "abc",
          "--models": MODEL, "--tools": "read", "--exclude-tools": "bash", "--thinking": "high", "--use-theme": "dark", "--name": "n", "--tui-mode": "regular", "--fork": "missing",
          "--skill": "missing-skill", "--prompt-template": "missing-template", "--theme": "missing-theme", "--export": "missing.jsonl", "--session": "{session}", "--session-dir": "{session_dir}",
          "--extension": "{ext}"}
SKIP_EFFECT = {"--help", "--version", "--resume", "--tui-mode", "--use-theme", "--list-models"}  # interactive or covered by their own probes


def parse_help(text):
    """[(flags, takes_value, description)] from the Options block of `--help`, and the command names of the Commands block."""
    flags, commands, section = [], [], None
    for line in text.splitlines():
        if re.match(r"^[A-Z][A-Za-z ]*:\s*$", line):
            section = line.strip().rstrip(":")
            continue
        m = re.match(r"^  (-\S.*?)(?:\s{2,}(.*))?$", line) if section == "Options" else None
        if m:
            spec = m.group(1)
            names = re.findall(r"(?<![\w<\[])(--?[A-Za-z][\w-]*)", re.sub(r"[<\[][^>\]]*[>\]]", "", spec))
            if names:  # the bare `--` line names no flag
                flags.append((names, bool(re.search(r"[<\[]", spec)), (m.group(2) or "").strip()))
        m = re.match(r"^  pi (\w+)\b", line) if section == "Commands" else None
        if m and m.group(1) not in commands:
            commands.append(m.group(1))
    return flags, commands


def cite_flag(flag, source_dir):
    if source_dir:
        path = os.path.join(source_dir, SRC, "cli", "args.ts")
        try:
            with open(path) as f:
                for n, line in enumerate(f, 1):
                    if f'"{flag}"' in line:
                        return f"{SRC}/cli/args.ts:{n}"
        except OSError:
            pass
    return f"`pi --help` ({flag})"


def flag_value(flag, setup, ctx):
    v = VALUES.get(flag, "x")
    return v.replace("{session}", os.path.join(setup.session_dir, "flag.jsonl")).replace("{session_dir}", setup.session_dir).replace("{ext}", os.path.join(EXT_DIR, "fx-tool.ts"))


def wire_effect(req):
    body = req.body
    names = [n for n, _, _ in wire.tool_defs(req.protocol, body)]
    return {"scalars": sorted([list(x) for x in canon.scalars(body, canon.Normalizer())], key=json.dumps), "tools": names, "roles": [r for r, _, _ in wire.messages(req.protocol, body)]}


def wire_delta(req, base):
    """What a request has that the baseline request lacks, and the reverse: scalars, tool names, roles."""
    if req is None or base is None:
        return None if req is None and base is None else "request" if req is not None else "no request"
    now, before = wire_effect(req), wire_effect(base)
    key = lambda x: json.dumps(x)
    added = sorted([x for x in now["scalars"] if x not in before["scalars"]], key=key)
    removed = sorted([x for x in before["scalars"] if x not in now["scalars"]], key=key)
    return {"added": added, "removed": removed, "tools": sorted(set(now["tools"]) ^ set(before["tools"])), "roles": now["roles"] if now["roles"] != before["roles"] else None}


def baseline_run(ctx, arm):
    """The arm's print run with no flag, once per probe context: (observation, normaliser)."""
    cache = ctx.__dict__.setdefault("_f1_baseline", {})
    if arm.id not in cache:
        base_api(arm, "openai-completions")
        setup = ctx.lab.prepare(arm, "F1.baseline", "openai-completions")
        setup.write("README.md", FIXTURE["README.md"])
        argv = ctx.lab.argv_for(arm, setup, "print", (), "Say hello.")
        cache[arm.id] = (ctx.lab.run(arm, setup, argv, steps=[Step(text="Hello there.")], timeout=min(ctx.timeout, 20)), norm_for(ctx, arm, setup))
    return cache[arm.id]


def flag_probes(help_text, source_dir=None):
    flags, commands = parse_help(help_text)
    out = []
    for names, takes_value, desc in flags:
        main = next((n for n in names if n.startswith("--")), names[0])
        slug = main.lstrip("-")
        cite = cite_flag(main, source_dir)

        def advertised(ctx, arm, names=names):
            text = ctx.help_text(arm)
            return all(re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text) for n in names)
        out.append(Probe(f"F1.advertised.{slug}", "F1", f"`{' '.join(names)}` is listed in --help", cite, advertised))
        if main in SKIP_EFFECT:
            continue

        def effect(ctx, arm, main=main, takes_value=takes_value):
            """What the flag changes, measured against the same arm's run without it: an arm whose baseline request differs from Pi's (an F2 matter) is not charged again here."""
            base = baseline_run(ctx, arm)

            def run(extra, name):
                base_api(arm, "openai-completions")
                setup = ctx.lab.prepare(arm, name, "openai-completions")
                setup.write("README.md", FIXTURE["README.md"])
                if extra is not None:
                    extra = (main, flag_value(main, setup, ctx)) if takes_value else (main,)
                argv = ctx.lab.argv_for(arm, setup, "print", extra or (), "Say hello.")
                obs = ctx.lab.run(arm, setup, argv, steps=[Step(text="Hello there.")], timeout=min(ctx.timeout, 20))
                return obs, norm_for(ctx, arm, setup)
            obs, norm = run(True, f"F1.effect.{main.lstrip('-')}")
            bobs, bnorm = base
            out = norm.text(obs.stdout)[:600]
            files = sorted(norm.text(k) for k in obs.files)
            return {"exit": obs.exit, "timed_out": obs.timed_out, "stdout": None if out == bnorm.text(bobs.stdout)[:600] else out,
                    "stderr": (norm.text(obs.stderr).strip().splitlines() or [""])[0][:160],
                    "wire": wire_delta(obs.requests[0] if obs.requests else None, bobs.requests[0] if bobs.requests else None),
                    "files": [f for f in files if f not in sorted(bnorm.text(k) for k in bobs.files)]}
        out.append(Probe(f"F1.effect.{slug}", "F1", f"`{main}` is accepted and has the same effect (exit, output, request)", cite, effect))
    for cmd in commands:
        def sub(ctx, arm, cmd=cmd):
            setup = ctx.lab.prepare(arm, f"F1.command.{cmd}", "openai-completions")
            binary = arm.binary
            obs = ctx.lab.run(arm, setup, [binary, cmd, "--help"], timeout=20, snapshot=False)
            norm = norm_for(ctx, arm, setup)
            lines = [" ".join(ln.split()) for ln in norm.text(obs.stdout).splitlines()]   # column widths and trailing blank lines are layout, not content
            return {"exit": obs.exit, "stdout": [ln for ln in lines if ln][:12]}
        out.append(Probe(f"F1.command.{cmd}", "F1", f"`pi {cmd} --help` exits and prints the same usage", f"`pi --help` (Commands: {cmd})", sub))
    return out


def all_probes(help_text, source_dir=None):
    probes = flag_probes(help_text, source_dir) + wire_probes() + tool_probes() + session_probes() + config_probes() + output_probes() + ext_probes()
    seen = set()
    for p in probes:
        if p.id in seen:
            raise ValueError(f"duplicate probe id {p.id}")
        seen.add(p.id)
    return probes
