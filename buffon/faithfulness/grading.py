# SPDX-License-Identifier: Apache-2.0
"""Graded faithfulness (docs/FAITHFULNESS.md, M8): a probe is never only match or mismatch.

  identical                1.0   the normalised observations are equal
  equivalent-presentation  0.9   a human-facing surface differs (help wording, layout) but carries the same information and allows the same actions
  equivalent-semantics     0.6   a machine-facing surface differs in form (key order, extra keys, whitespace) but carries the same meaning
  behaviour-differs        0.0   a different result

The class is decided by a deterministic comparator per probe family, never by hand: the comparator states what "the same meaning" is for that surface, and a probe with no comparator
is identical or behaviour-differs. A recorded intentional divergence never changes a class; it is listed by name beside the row.

Only a correctness failure gates a performance family (`correctness_failures`): wrong file contents left by a tool, a wrong or missing tool result, a crash, a hang. A presentation or
semantics difference never does."""
import fnmatch
import json
import re

IDENTICAL, PRESENTATION, SEMANTICS, DIFFERS = "match", "presentation", "semantics", "mismatch"
CREDIT = {IDENTICAL: 1.0, PRESENTATION: 0.9, SEMANTICS: 0.6, DIFFERS: 0.0}
NAMES = {IDENTICAL: "identical", PRESENTATION: "equivalent-presentation", SEMANTICS: "equivalent-semantics", DIFFERS: "behaviour-differs"}
HUMAN, MACHINE = "human", "machine"


def _form(text):
    """Text up to its form only: line endings, trailing spaces of a line and trailing blank lines. Indentation, line breaks and inner spacing are content (a file read back
    with its newlines or indentation changed is a wrong result), so they are kept."""
    if text is None:
        return None
    lines = [line.rstrip() for line in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _canon(x):
    return json.dumps(x, sort_keys=True)


def unordered(a, b):
    """Equal as multisets, at every level: only the order differs."""
    def norm(x):
        if isinstance(x, dict):
            return {k: norm(v) for k, v in x.items()}
        if isinstance(x, list):
            return sorted((norm(v) for v in x), key=_canon)
        return x
    return norm(a) == norm(b)


def keysets_superset(a, b):
    """{type: [keyset, ...]} where the harness's key sets contain the reference's (an addition is not a difference in meaning) and the types are the same."""
    if not isinstance(a, dict) or not isinstance(b, dict) or set(a) != set(b):
        return False
    for t in b:
        got, want = [set(k) for k in a[t]], [set(k) for k in b[t]]
        if not all(any(w <= g for g in got) for w in want):
            return False
    return True


def same_effect(a, b):
    """A flag's effect (F1): the same exit, hang, request change and files; only the printed words differ."""
    return isinstance(a, dict) and isinstance(b, dict) and all(a.get(k) == b.get(k) for k in ("exit", "timed_out", "wire", "files"))


def same_flags(a, b):
    """A command's usage (F1): the same exit and the same set of options named in it."""
    if not isinstance(a, dict) or not isinstance(b, dict) or a.get("exit") != b.get("exit"):
        return False
    tokens = lambda o: {t for line in o.get("stdout") or [] for t in re.findall(r"(?<![\w-])--?[A-Za-z][\w-]*", line)}
    return tokens(a) == tokens(b)


def tools_equivalent(a, b):
    """Tool definitions (F2), one list of [name, description, parameters] per request: the same tools with the same parameters in any order; a description's prose is not compared."""
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
        return False
    strip = lambda rows: sorted(([r[0], r[2]] for r in rows), key=_canon)
    return all(isinstance(x, list) and isinstance(y, list) and strip(x) == strip(y) for x, y in zip(a, b))


def tool_equivalent(a, b):
    """A built-in tool (F3): the files it leaves and whether it exists are identical, its result text differs only in form (line endings, trailing spaces, trailing blank lines)."""
    return isinstance(a, dict) and isinstance(b, dict) and a.get("files") == b.get("files") and a.get("tool_present") == b.get("tool_present") and _form(a.get("result")) == _form(b.get("result"))


def records_equivalent(a, b):
    """Session records (F4): the same record types, roles and content kinds in the same order; extra keys are an addition."""
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
        return False
    core = lambda r: [r[0], *(r[2:3]), *(r[4:5])] if len(r) > 2 else r[:1]
    for x, y in zip(a, b):
        if core(x) != core(y) or not (len(x) < 2 or len(y) < 2 or set(y[1]) <= set(x[1])):
            return False
    return True


def header_equivalent(a, b):
    return isinstance(a, list) and isinstance(b, list) and a[:1] == b[:1] and (len(a) < 2 or len(b) < 2 or set(b[1]) <= set(a[1]))


def marker_present(a, b):
    """A context marker (F5): present in both; where it landed in the prompt is a layout matter."""
    return isinstance(a, dict) and isinstance(b, dict) and a.get("present") == b.get("present") and (a.get("present") is not None)


def prompt_flag(a, b):
    return isinstance(a, dict) and isinstance(b, dict) and a.get("contains") == b.get("contains") and a.get("is_exactly_it") == b.get("is_exactly_it")


def print_output(a, b):
    """Print mode (F6): the same exit code and the same text up to its form (line endings, trailing spaces, trailing blank lines); a script reads the lines."""
    return isinstance(a, dict) and isinstance(b, dict) and a.get("exit") == b.get("exit") and _form(a.get("stdout")) == _form(b.get("stdout"))


def ordered_additions(a, b):
    """An event sequence (F6 json/rpc): the reference's sequence occurs in the harness's in the same order; events the harness adds between them are an addition. A consumer
    reads a stream in order, so a reordering or a missing event is a different result."""
    if not isinstance(a, list) or not isinstance(b, list):
        return False
    it = iter(map(_canon, a))
    return all(any(x == y for x in it) for y in map(_canon, b))


def same_set(a, b):
    return isinstance(a, list) and isinstance(b, list) and {_canon(x) for x in a} == {_canon(x) for x in b}


# (probe id pattern, surface, comparator); the first match decides. A probe matching none has no comparator.
RULES = [
    ("F1.effect.*", HUMAN, same_effect),
    ("F1.command.*", HUMAN, same_flags),
    ("F2.*.order", MACHINE, unordered),
    ("F2.*.tools", MACHINE, tools_equivalent),
    ("F3.*", MACHINE, tool_equivalent),
    ("F4.write.records", MACHINE, records_equivalent),
    ("F4.write.header", MACHINE, header_equivalent),
    ("F5.system-prompt-flag", MACHINE, prompt_flag),
    ("F5.append-system-prompt-flag", MACHINE, prompt_flag),
    ("F5.agents-md", MACHINE, marker_present), ("F5.claude-md", MACHINE, marker_present), ("F5.global-agents-md", MACHINE, marker_present),
    ("F5.no-context-files", MACHINE, marker_present), ("F5.skill", MACHINE, marker_present), ("F5.skill-project", MACHINE, marker_present), ("F5.no-skills", MACHINE, marker_present),
    ("F6.print-*", MACHINE, print_output),
    ("F6.json.types", MACHINE, ordered_additions),
    ("F6.json.keys", MACHINE, keysets_superset),
    ("F6.rpc.events", MACHINE, ordered_additions),
    ("F6.rpc.responses", MACHINE, unordered),
    ("F6.rpc.keys", MACHINE, keysets_superset),
]


def rule_for(probe_id):
    for pattern, surface, fn in RULES:
        if fnmatch.fnmatchcase(probe_id, pattern):
            return surface, fn
    return None


def grade(probe_id, obs, ref_obs):
    """The class of one observation against the reference's: identical, equivalent-presentation, equivalent-semantics or behaviour-differs."""
    if _canon(obs) == _canon(ref_obs):
        return IDENTICAL
    rule = rule_for(probe_id)
    if rule and rule[1](obs, ref_obs):
        return PRESENTATION if rule[0] == HUMAN else SEMANTICS
    return DIFFERS


def correctness_failures(probes, results, ref_results, verdicts):
    """Probe ids where the harness is wrong in a way that gates a performance family: a crash or hang, a tool probe (F3) that is not identical in result and files up to form,
    or data loss (F4: a harness that claims Pi sessions wrote no session file)."""
    out = []
    for p in probes:
        r = results.get(p.id, {"status": "error", "reason": "not run"})
        ref = ref_results.get(p.id, {})
        v = verdicts.get(p.id)
        if ref.get("status") != "ok" or v in ("na", "invalid", "unstable", None):
            continue
        hang = isinstance(r.get("obs"), dict) and r["obs"].get("timed_out") and not (isinstance(ref.get("obs"), dict) and ref["obs"].get("timed_out"))
        lost = p.dim == "F4" and isinstance(r.get("obs"), dict) and r["obs"].get("session_written") is False
        if r.get("status") == "error" or hang or (p.dim == "F3" and v == DIFFERS) or lost:
            out.append(p.id)
    return out
