# SPDX-License-Identifier: Apache-2.0
"""The mock's request log: every request a harness sent, with times, wire bytes and the full body, one gzip JSON-lines file per sample in the run directory.

A conversation's request carries the whole history, so bodies grow with the turn count and a long session would write gigabytes. A request whose message list extends the previous
request's list is therefore stored as the new tail plus the count of messages it shares with the previous one (`extends_previous`); `expand` rebuilds the full bodies exactly.
"""
import gzip
import json
import os
import re

LISTS = ("messages", "input")  # Chat Completions and Messages use `messages`, Responses uses `input`


def _key(body):
    return next((k for k in LISTS if isinstance(body.get(k), list)), None)


def delta(body, previous):
    """The stored form of `body` given the previous request's full body of the same sample."""
    key = _key(body)
    if previous is None or key is None or _key(previous) != key:
        return body
    old, new = previous[key], body[key]
    if len(new) < len(old) or new[:len(old)] != old:
        return body
    out = {k: v for k, v in body.items() if k != key}
    out["extends_previous"] = {"key": key, "shared": len(old), "tail": new[len(old):]}
    return out


def expand(records):
    """Full bodies from stored records (an iterable of the dicts `write` produced), in order."""
    previous = None
    for rec in records:
        body = rec["body"]
        ext = body.get("extends_previous")
        if ext is not None:
            full = {k: v for k, v in body.items() if k != "extends_previous"}
            full[ext["key"]] = previous[ext["key"]][:ext["shared"]] + ext["tail"]
            body = full
        previous = body
        yield dict(rec, body=body)


class RequestLog:
    def __init__(self, directory):
        self.directory, self.count = directory, 0

    def write(self, context, requests):
        if not requests:
            return None
        os.makedirs(self.directory, exist_ok=True)
        self.count += 1
        label = "-".join(re.sub(r"[^A-Za-z0-9._-]+", "_", str(context.get(k, ""))) for k in ("arm", "scenario", "api") if context.get(k)) or "unlabelled"
        path = os.path.join(self.directory, f"{self.count:05d}-{label}-r{context.get('round', 0)}.jsonl.gz")
        previous = None
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for r in requests:
                rec = {"context": context, "index": r.index, "protocol": r.protocol, "t_recv_ns": r.t_recv, "t_reply_start_ns": r.t_start, "t_reply_end_ns": r.t_end, "wire_bytes": r.bytes,
                       "fault": None if r.fault is None else str(r.fault), "body": delta(r.body, previous)}
                previous = r.body
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        return path


def read(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return list(expand(json.loads(line) for line in f))
