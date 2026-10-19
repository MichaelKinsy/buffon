# SPDX-License-Identifier: Apache-2.0
"""Views of one request body that is the same situation on the three wire APIs: system prompt, tool definitions, the message sequence. Pure functions over decoded JSON."""
import json


def _blocks_text(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict):
            out.append(b.get("text") if b.get("type") in ("text", "input_text", "output_text") else json.dumps(b, sort_keys=True))
        else:
            out.append(str(b))
    return "\n".join(x for x in out if x is not None)


def system_text(protocol, body):
    if protocol == "openai-completions":
        msgs = body.get("messages") or []
        return "\n".join(_blocks_text(m.get("content")) for m in msgs if m.get("role") in ("system", "developer"))
    if protocol == "openai-responses":
        return _blocks_text(body.get("instructions"))
    return _blocks_text(body.get("system"))


def tool_defs(protocol, body):
    """[(name, description, parameters)] in the order the harness sent them."""
    out = []
    for t in body.get("tools") or []:
        if protocol == "openai-completions":
            f = t.get("function", t)
            out.append((f.get("name"), f.get("description"), f.get("parameters")))
        elif protocol == "openai-responses":
            out.append((t.get("name"), t.get("description"), t.get("parameters")))
        else:
            out.append((t.get("name"), t.get("description"), t.get("input_schema")))
    return out


def messages(protocol, body):
    """[(role, kind, payload)] without the system prompt: user text, assistant text, tool calls (name, arguments) and tool results, on any API."""
    out = []
    if protocol == "openai-completions":
        for m in body.get("messages") or []:
            role = m.get("role")
            if role in ("system", "developer"):
                continue
            if role == "tool":
                out.append(("tool", "result", _blocks_text(m.get("content"))))
                continue
            text = _blocks_text(m.get("content"))
            if text:
                out.append((role, "text", text))
            for c in m.get("tool_calls") or []:
                f = c.get("function", {})
                out.append((role, "call", (f.get("name"), _args(f.get("arguments")))))
    elif protocol == "openai-responses":
        inp = body.get("input")
        items = inp if isinstance(inp, list) else ([{"role": "user", "content": inp}] if inp else [])
        for it in items:
            t = it.get("type")
            if t == "function_call":
                out.append(("assistant", "call", (it.get("name"), _args(it.get("arguments")))))
            elif t == "function_call_output":
                out.append(("tool", "result", _blocks_text(it.get("output"))))
            elif it.get("role") in ("system", "developer"):
                continue
            elif t in (None, "message"):
                out.append((it.get("role"), "text", _blocks_text(it.get("content"))))
            else:
                out.append((it.get("role") or "assistant", t, json.dumps(it, sort_keys=True)))
    else:
        for m in body.get("messages") or []:
            content = m.get("content")
            if isinstance(content, str):
                out.append((m.get("role"), "text", content))
                continue
            for b in content or []:
                t = b.get("type")
                if t == "text":
                    out.append((m.get("role"), "text", b.get("text")))
                elif t == "tool_use":
                    out.append(("assistant", "call", (b.get("name"), _args(b.get("input")))))
                elif t == "tool_result":
                    out.append(("tool", "result", _blocks_text(b.get("content"))))
                else:
                    out.append((m.get("role"), t, json.dumps(b, sort_keys=True)))
    return out


def _args(a):
    if isinstance(a, str):
        try:
            return json.loads(a)
        except ValueError:
            return a
    return a
