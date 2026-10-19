# SPDX-License-Identifier: Apache-2.0
"""Normalisation of observations: what differs between two harnesses for reasons that are not behaviour (their name, their config directory, the temporary paths of the run)
is replaced by a placeholder, so equal behaviour compares equal. Pure functions; no I/O."""
import json
import re

UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?Z?)?")
CALL_ID = re.compile(r"\b(?:call|toolu|fc|msg|resp|chatcmpl)[_-][A-Za-z0-9_-]+")
EPOCH_MS = re.compile(r"\b1[67]\d{11}\b")
TEXT_KEYS = {"text", "content", "description", "instructions", "system", "arguments", "partial_json", "input_text"}


class Normalizer:
    """Replacements for one arm in one probe: its paths, its program name and config directory, the mock's address."""

    def __init__(self, paths=(), names=(), version="", origin_port=None):
        self.paths = sorted({(p, tag) for p, tag in paths if p}, key=lambda pt: -len(pt[0]))
        self.names = sorted({n for n in names if n}, key=lambda n: -len(n))
        self.version = version
        self.port = origin_port

    def text(self, s):
        if not isinstance(s, str):
            return s
        for path, tag in self.paths:
            s = s.replace(path, tag)
        if self.port:
            s = re.sub(rf"127\.0\.0\.1:{self.port}", "127.0.0.1:<port>", s)
        for name in self.names:
            s = re.sub(rf"(?<![\w-])({re.escape(name)})(?![\w-])", "<bin>", s)
        if self.version:
            s = s.replace(self.version, "<version>")
        s = UUID.sub("<uuid>", s)
        s = DATE.sub("<date>", s)
        s = CALL_ID.sub("<id>", s)
        return EPOCH_MS.sub("<epoch-ms>", s)

    def value(self, v):
        if isinstance(v, str):
            return self.text(v)
        if isinstance(v, list):
            return [self.value(x) for x in v]
        if isinstance(v, dict):
            return {self.text(k): self.value(x) for k, x in v.items()}
        return v


def canonical(obj):
    """A stable text form of a JSON-compatible value: sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def key_paths(obj, prefix=""):
    """The set of key paths of a JSON value; list positions collapse to []."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            out.add(p)
            out |= key_paths(v, p)
    elif isinstance(obj, list):
        for v in obj:
            out |= key_paths(v, prefix + "[]")
    return out


def key_orders(obj, prefix=""):
    """{path: sorted set of the key orders seen at that path}: the order objects list their keys in, which a strict server or a cache can depend on."""
    out = {}

    def walk(o, p):
        if isinstance(o, dict):
            out.setdefault(p or "$", set()).add(tuple(o))
            for k, v in o.items():
                walk(v, f"{p}.{k}" if p else k)
        elif isinstance(o, list):
            for v in o:
                walk(v, p + "[]")
    walk(obj, prefix)
    return {k: sorted(v) for k, v in sorted(out.items())}


def scalars(obj, norm, prefix="", skip_text=True):
    """[(path, value)] of the short leaves: numbers, booleans, null and strings that are not free text. Free text (message content, descriptions) has probes of its own."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if skip_text and k in TEXT_KEYS and isinstance(v, str):
                continue
            out += scalars(v, norm, p, skip_text)
    elif isinstance(obj, list):
        for v in obj:
            out += scalars(v, norm, prefix + "[]", skip_text)
    else:
        out.append((prefix, norm.text(obj) if isinstance(obj, str) else obj))
    return out
