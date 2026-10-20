# SPDX-License-Identifier: Apache-2.0
"""The durable family's store inspector and semantic exporter: what the runner reads from a store with its own SQLite, never through an arm's API
(design/DURABLE.md, sections 4.2 and 6.2). Pure stdlib `sqlite3`; the runner opens the file after a clean close and `checkpoint`, so no adapter is involved.

A store written by Pi Durable 1.3.0 and one written by the Go port have the same schema (durable_schema.version 1): nine tables, the JSON of a record in a `record` column
(`content` for document revisions) and a few columns repeated beside it for indexes. Every function here reads that layout and nothing runtime-specific, so a store of either
runtime is read the same way.

Functions
  inspect(path)              file sizes, store_bytes, page and freelist counts, journal mode, schema version, rows per durable table (the `store_tables` fact).
  checkpoint(path)           `PRAGMA wal_checkpoint(TRUNCATE)` on the runner's own connection; the last connection to close removes -wal and -shm.
  export_state(path, ...)    the semantic export the equivalence gate compares (below).
  state_digest, diff_states  a sha256 of a state, and the paths at which two states differ.
  compaction_entry_ids       the raw ids of the head markers (the `compaction_ids` fact).
  row_digest, rows_identical, row_differences   the byte-for-byte row comparison behind `row_identical`.

Reading without changing. A store with no live write-ahead log is opened `immutable=1`: SQLite creates no -wal or -shm file, so a read never changes `store_bytes`. A store with
a non-empty -wal is opened `mode=ro` (SQLite must read the log). The sizes are taken before any connection opens.

What `export_state` keeps (docs: how Pi stores a conversation, read from pi-durable 1.3.0's schema and a store written by it)
  * Entries. `entries.record` holds `{kind, model: [messages], data, head, edits, byTaskId, id, conversationId}`. A conversation's *active transcript* is what the model sees:
    the newest entry with a `head` (a compaction summary: `head` is the first kept entry; a reset: `head` is its own id) followed by every entry from `head` on that has no
    `head` of its own, walking the fork chain (`conversations.record.parent = {conversationId, at}`) for forked conversations. `edits` of any entry in that range override the
    contribution of their target (`omit` or `replace`). A subagent's child conversation is a conversation like the others. Each active entry is exported as
    {kind, role, digest, calls, stop, usage, data, by_task, edits, visible}: `role` is the roles of the entry's messages joined with "/", `digest` the sha256 of the
    model-visible content (see MESSAGE_DROP: role, content blocks, tool call and result ids, system tool changes; never time, usage or the provider's names), `calls` the ids of
    the tool calls it makes, `stop` the stop reason of its assistant message, `usage` the four token counts the provider reported, `data` the sha256 of the entry's own data,
    `by_task` a task reference. `visible` is false for an assistant entry the context leaves out (aborted, error, deferred).
  * Documents. Live documents (`retired_at` null) as parsed JSON, materialised from the newest base revision and the deltas after it, with the delta operations of
    @earendil-works/chord's `delta` (`apply_ops`). Deep-equal comparable.
  * Tasks. Every task of the exported conversations with its kind, version, input, owner, background and abort flags and `state` (status and terminal outcome).
  * Submissions. Request id, type, status, reason and the entry and answer they point at.
  * Head markers. Per conversation, every entry that carries a head (not only the newest) and the first entry each keeps; the same list is repeated top-level as `compaction_ids` so the gate can decide
    "different work" before it compares the rest.

Ids. Entry, task, submission and conversation ids are allocated by the database in commit order, and a runtime with another commit grouping may legitimately number differently.
A request id that embeds a task id (a subagent's `subagent:<task id>`) is rewritten with the task's reference. They are kept out of the comparison: a reference is `c<k>` (the k-th conversation by id), `e<k>.<i>` (the i-th entry of conversation k by id), `t<k>.<i>`, `s<k>.<i>`. References
are structural: they change when a runtime writes another number or order of entries, tasks or submissions, which is the difference the gate is looking for. The raw ids appear
only in `compaction_entry_ids`, for the sample's descriptor.

Volatile fields, removed by name (never by position or value):
  VOLATILE_KEYS         `timestamp` (wall clock of a message), `durationMs` (time a call took), `startedAt` and `endedAt` (clock of a task), `createdAt` (a document record's creation
                        stamp: a counter allocated in commit order, like an id). Removed at any depth.
  MESSAGE_DROP          in a message (a dict with a `role`): `usage` (compared as its own field), `api`, `provider`, `model`, `responseId` (names the scripted provider picked: adapter
                        choices, not runtime behaviour), `stopReason` (its own field) and `details` (display data, never sent to the model).
  DOCUMENT_VOLATILE     `pi.provider`'s `sessionId`: a UUIDv7 the runtime draws per conversation (random; present in both runtimes, so its value is masked, its presence is kept).
Not volatile, decided from the data: `usage` (the scripted provider's counter is specified to the byte, so both arms report the same numbers; `usage=False` leaves it out),
the `pi.usage` document (sums of those), `pi.live` and `pi.inbox` (empty at rest), `commit_seq` and `created_at` columns (compared only by `row_digest`: commit grouping is part of
row identity).

Row identity. `row_digest` hashes every row of the durable tables in primary-key order, with the volatile fields removed from JSON columns and nothing else changed: ids, commit
sequence numbers, key order inside a record and every other byte count. `row_identical` is true when both digests agree, and a false is a note, not a refusal (design 6.2).
"""
import bisect
import hashlib
import json
import os
import re
import sqlite3
from urllib.parse import quote

DURABLE_TABLES = ("durable_schema", "durable_metadata", "record_ids", "conversations", "entries", "tasks", "submissions", "documents", "document_revisions")
STATE_FORMAT = "buffon-durable-state/1"
VOLATILE_KEYS = frozenset({"timestamp", "durationMs", "startedAt", "endedAt", "createdAt"})
MESSAGE_DROP = frozenset({"usage", "api", "provider", "model", "responseId", "stopReason", "details"})
DOCUMENT_VOLATILE = {"pi.provider": ("sessionId",)}
MASKED = "<volatile>"
SUBAGENT_REQUEST = re.compile(r"subagent:(\d+)$")
EXCLUDED_STOP_REASONS = frozenset({"aborted", "error", "deferred"})   # assistant messages the runtime leaves out of a model context
USAGE_FIELDS = ("input", "output", "cacheRead", "cacheWrite")
# Integer fields that name a record: field -> the kind of record. Used on tasks, submissions and conversations (never on messages).
ID_FIELDS = {"entryId": "entry", "entry": "entry", "answer": "entry", "assistant": "entry", "head": "entry", "at": "entry", "target": "entry", "byTaskId": "task",
             "taskId": "task", "owner": "task", "submissionId": "submission", "conversationId": "conversation"}


# ---------------------------------------------------------------------------------------------------- small helpers

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _size(path):
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


def _connect(path):
    """A connection that changes nothing on disk: `immutable=1` when there is no live log, else `mode=ro`."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    mode = "mode=ro" if _size(path + "-wal") else "immutable=1"
    con = sqlite3.connect(f"file:{quote(path)}?{mode}", uri=True)
    con.text_factory = str
    return con


def _tables(con):
    return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _journal_mode(path):
    """`wal` or `delete`, from the database header (bytes 18 and 19 are 2 in a WAL database): `immutable` hides it from the pragma."""
    with open(path, "rb") as f:
        header = f.read(20)
    return "wal" if len(header) == 20 and header[18] == 2 and header[19] == 2 else "delete"


# ---------------------------------------------------------------------------------------------------- inspect, checkpoint

def inspect(path):
    """Facts about a store file: sizes of the main file, -wal and -shm, `store_bytes` (their sum), `page_count`, `page_size`, `freelist_count`, `journal_mode`, `schema_version`
    (durable_schema.version, or null) and `store_tables` ({table: rows}, the durable tables present) with `other_tables` for any other table (the floor's `floor_turns`)."""
    path = os.path.abspath(path)
    main, wal, shm = _size(path), _size(path + "-wal"), _size(path + "-shm")   # before a connection opens
    if not main:
        raise FileNotFoundError(path)
    con = _connect(path)
    try:
        one = lambda sql: con.execute(sql).fetchone()[0]
        names = _tables(con)
        counts = {t: one(f"SELECT count(*) FROM {_quote(t)}") for t in names}
        version = one("SELECT version FROM durable_schema WHERE singleton = 1") if "durable_schema" in names and counts["durable_schema"] else None
        types = dict(con.execute("SELECT record_type, count(*) FROM record_ids GROUP BY 1")) if "record_ids" in names else {}
        return {"main_bytes": main, "wal_bytes": wal, "shm_bytes": shm, "store_bytes": main + wal + shm, "page_size": one("PRAGMA page_size"), "page_count": one("PRAGMA page_count"),
                "freelist_count": one("PRAGMA freelist_count"), "journal_mode": con.execute("PRAGMA journal_mode").fetchone()[0] if wal else _journal_mode(path),
                "schema_version": version, "user_version": one("PRAGMA user_version"),
                "store_tables": {t: counts[t] for t in DURABLE_TABLES if t in counts}, "other_tables": {t: n for t, n in counts.items() if t not in DURABLE_TABLES},
                "record_types": dict(sorted(types.items()))}
    finally:
        con.close()


def checkpoint(path):
    """Fold the log into the main file and truncate it, on a connection of the runner's own; returns {busy, log, checkpointed}. Run it after the arm closed the store: the last
    connection to close removes -wal and -shm, so `inspect` afterwards sees the main file alone."""
    con = sqlite3.connect(os.path.abspath(path))
    try:
        busy, log, done = con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    finally:
        con.close()
    return {"busy": busy, "log": log, "checkpointed": done}


# ---------------------------------------------------------------------------------------------------- JSON deltas (documents)

def _resolve(value, path):
    for seg in path:
        value = value[seg]
    return value


def apply_ops(value, ops):
    """Apply a stored document revision (a list of `chord/delta` operations) to `value`: `r` replace the root, `s` set, `d` delete, `a` append to a string, `t` drop the first n
    characters of a string, `p` splice an array (path, start, remove, items), `m` permute an array. Mutates and returns the value."""
    for op in ops:
        kind = op[0]
        if kind == "r":
            value = op[1]
        elif kind == "p":
            target = _resolve(value, op[1])
            target[op[2]:op[2] + op[3]] = op[4]
        elif kind == "m":
            target = _resolve(value, op[1])
            target[:] = [target[i] for i in op[2]]
        else:
            parent, key = _resolve(value, op[1][:-1]), op[1][-1]
            if kind == "s":
                if isinstance(parent, list) and key == len(parent):
                    parent.append(op[2])
                else:
                    parent[key] = op[2]
            elif kind == "d":
                if isinstance(parent, list):
                    del parent[key]
                else:
                    parent.pop(key, None)
            elif kind == "a":
                parent[key] = parent[key] + op[2]
            elif kind == "t":
                parent[key] = parent[key][op[2]:]
            else:
                raise ValueError(f"unknown delta operation {kind!r}")
    return value


# ---------------------------------------------------------------------------------------------------- scrubbing

MESSAGE_ROW_DROP = frozenset({"api", "provider", "model", "responseId"})   # row identity keeps usage, stop reasons and details; only the adapter's own names go


def scrub(value, rows=False):
    """A copy of `value` without the volatile fields at any depth. A dict with a `role` is a message: it also loses MESSAGE_DROP (the semantic export) or, when `rows`, only
    MESSAGE_ROW_DROP (row identity)."""
    if isinstance(value, dict):
        drop = (MESSAGE_ROW_DROP if rows else MESSAGE_DROP) if "role" in value else ()
        return {k: scrub(v, rows) for k, v in value.items() if k not in VOLATILE_KEYS and k not in drop}
    if isinstance(value, list):
        return [scrub(v, rows) for v in value]
    return value


def _mask_document(kind, value):
    """`pi.provider`-style documents: the volatile fields of `value` replaced by MASKED (a base revision or a stored delta)."""
    names = DOCUMENT_VOLATILE.get(kind)
    if not names:
        return value
    if isinstance(value, dict):
        return {k: (MASKED if k in names else v) for k, v in value.items()}
    if isinstance(value, list):   # a delta: operations
        out = []
        for op in value:
            if op[0] == "s" and op[1] and op[1][-1] in names:
                op = [op[0], op[1], MASKED]
            elif op[0] == "r":
                op = [op[0], _mask_document(kind, op[1])]
            out.append(op)
        return out
    return value


# ---------------------------------------------------------------------------------------------------- the semantic export

class _Index:
    """Structural references: database ids to `c<k>`, `e<k>.<i>`, `t<k>.<i>`, `s<k>.<i>`."""

    def __init__(self, con):
        self.conv = {cid: k for k, (cid,) in enumerate(con.execute("SELECT id FROM conversations ORDER BY id"))}
        self.ids = {}   # kind -> {conversation id: [ids ascending]}
        self.owner = {}   # kind -> {id: conversation id}
        for kind, table in (("entry", "entries"), ("task", "tasks"), ("submission", "submissions")):
            per, owner = {}, {}
            for rid, cid in con.execute(f"SELECT id, conversation_id FROM {table} ORDER BY id"):
                per.setdefault(cid, []).append(rid)
                owner[rid] = cid
            self.ids[kind], self.owner[kind] = per, owner

    def ref(self, kind, rid):
        if kind == "conversation":
            return f"c{self.conv[rid]}" if rid in self.conv else rid
        cid = self.owner[kind].get(rid)
        if cid is None:
            return rid
        return f"{kind[0]}{self.conv[cid]}.{bisect.bisect_left(self.ids[kind][cid], rid)}"

    def remap(self, value):
        """`value` with every integer under an ID_FIELDS name replaced by its reference (a copy)."""
        if isinstance(value, dict):
            return {k: self.ref(ID_FIELDS[k], v) if k in ID_FIELDS and isinstance(v, int) and not isinstance(v, bool) else self.remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.remap(v) for v in value]
        return value


def _chain(con, conversation):
    """[(conversation id, inclusive upper entry id or None)] from the conversation to the root of its fork chain."""
    out, upper = [], None
    while True:
        out.append((conversation, upper))
        row = con.execute("SELECT record FROM conversations WHERE id = ?", (conversation,)).fetchone()
        parent = json.loads(row[0]).get("parent")
        if parent is None:
            return out
        upper = parent["at"] if upper is None else min(upper, parent["at"])
        conversation = parent["conversationId"]


def _segment_sql(upper):
    return " AND id <= ?" if upper is not None else ""


def _marker(con, chain):
    """The newest entry with a head across the fork chain, as (id, head), or None."""
    best = None
    for cid, upper in chain:
        args = (cid,) + ((upper,) if upper is not None else ())
        row = con.execute(f"SELECT id, head FROM entries WHERE conversation_id = ? AND head IS NOT NULL{_segment_sql(upper)} ORDER BY id DESC LIMIT 1", args).fetchone()
        if row and (best is None or row[0] > best[0]):
            best = row
    return best


def _markers(con, chain):
    """Every head marker of the visible history, ascending: [(entry id, head, kind)]. A compaction boundary is one of these, whether or not the active range still holds it."""
    out = []
    for cid, upper in chain:
        args = (cid,) + ((upper,) if upper is not None else ())
        out += [(rid, head, json.loads(rec)["kind"]) for rid, head, rec in
                con.execute(f"SELECT id, head, record FROM entries WHERE conversation_id = ? AND head IS NOT NULL{_segment_sql(upper)} ORDER BY id", args)]
    return sorted(out)


def _range(con, chain, first):
    """The records of the visible entries from `first` (or the start) on, ascending: [(id, record)]."""
    out = []
    for cid, upper in chain:
        args = [cid] + ([first] if first is not None else []) + ([upper] if upper is not None else [])
        sql = f"SELECT id, record FROM entries WHERE conversation_id = ?{' AND id >= ?' if first is not None else ''}{_segment_sql(upper)}"
        out += [(rid, json.loads(rec)) for rid, rec in con.execute(sql, args)]
    out.sort(key=lambda r: r[0])
    return out


def _messages(rec, edit):
    """The messages an entry contributes to the model context after its edit and the exclusion of aborted, errored and deferred assistant messages."""
    if edit is not None and edit["action"] == "omit":
        return []
    messages = edit["messages"] if edit is not None and edit["action"] == "replace" else rec.get("model") or []
    return [m for m in messages if m["role"] != "assistant" or m.get("stopReason") not in EXCLUDED_STOP_REASONS]


def _entry_item(index, rec, edit, usage):
    shown = _messages(rec, edit)
    original = rec.get("model") or []
    assistant = next((m for m in original if m["role"] == "assistant"), None)
    content = [scrub(m) for m in shown]
    calls = [c["id"] for m in shown if m["role"] == "assistant" and isinstance(m.get("content"), list) for c in m["content"] if c.get("type") == "toolCall"]
    item = {"kind": rec["kind"], "role": "/".join(m["role"] for m in original) or None, "digest": _sha(content) if shown else None, "calls": calls,
            "stop": assistant.get("stopReason") if assistant else None, "data": _sha(scrub(rec["data"])) if "data" in rec else None,
            "by_task": index.ref("task", rec["byTaskId"]) if "byTaskId" in rec else None, "visible": bool(shown) or not original}
    if usage:
        got = assistant.get("usage") if assistant else None
        item["usage"] = {f: got[f] for f in USAGE_FIELDS if f in got} if got else None
    if "edits" in rec:
        item["edits"] = [{"target": index.ref("entry", e["target"]), "action": e["action"], "digest": _sha([scrub(m) for m in e.get("messages", [])])} for e in rec["edits"]]
    return item


def _active(con, index, conversation, usage):
    chain = _chain(con, conversation)
    marker = _marker(con, chain)
    entries = _range(con, chain, marker[1] if marker else None)
    edits = {}
    for _, rec in entries:   # an edit of any entry of the range counts, as in the runtime
        for e in rec.get("edits", ()):
            edits[e["target"]] = e
    active = [(rid, rec) for rid, rec in entries if rec.get("head") is None]
    if marker:
        active.insert(0, next((rid, rec) for rid, rec in entries if rid == marker[0]))
    items = [dict(_entry_item(index, rec, edits.get(rid), usage), ref=index.ref("entry", rid)) for rid, rec in active]   # `ref`: where the entry is in the conversation, so a comparison can follow it
    return items, [{"entry": index.ref("entry", rid), "head": index.ref("entry", head), "kind": kind} for rid, head, kind in _markers(con, chain)]


def _document_value(con, doc_id, kind):
    base = con.execute("SELECT seq, content FROM document_revisions WHERE document_id = ? AND kind = 'base' ORDER BY seq DESC LIMIT 1", (doc_id,)).fetchone()
    if base is None:
        raise ValueError(f"document {doc_id} has no base revision")
    value = json.loads(base[1])
    for (content,) in con.execute("SELECT content FROM document_revisions WHERE document_id = ? AND seq > ? ORDER BY seq", (doc_id, base[0])):
        value = apply_ops(value, json.loads(content))
    return _mask_document(kind, scrub(value))


def _documents(con, index, selected):
    out = []
    for doc_id, scope, owner, record in con.execute("SELECT id, scope_kind, owner_id, record FROM documents WHERE retired_at IS NULL ORDER BY id"):
        rec = json.loads(record)
        if scope == "conversation":
            conv = owner
            owner_ref = index.ref("conversation", owner)
        elif scope == "task":
            conv = index.owner["task"].get(owner)
            owner_ref = index.ref("task", owner)
        else:
            conv, owner_ref = None, None
        if conv is not None and selected is not None and conv not in selected:
            continue
        key = json.loads(con.execute("SELECT key_value FROM documents WHERE id = ?", (doc_id,)).fetchone()[0])
        out.append({"conversation": index.ref("conversation", conv) if conv is not None else None, "scope": scope, "owner": owner_ref, "kind": rec["kind"], "key": key,
                    "history": rec.get("history"), "fork": rec.get("fork"), "value": _document_value(con, doc_id, rec["kind"])})
    out.sort(key=lambda d: (d["kind"], canonical(d["key"]), d["scope"], str(d["owner"])))
    return out


def _tasks(con, index, conv_id):
    out = []
    for tid, record in con.execute("SELECT id, record FROM tasks WHERE conversation_id = ? ORDER BY id", (conv_id,)):
        rec = scrub(json.loads(record))
        for dropped in ("id", "conversationId"):
            rec.pop(dropped, None)
        out.append(dict(index.remap(rec), ref=index.ref("task", tid)))
    return out


def _submissions(con, index, conv_id):
    out = []
    for sid, record in con.execute("SELECT id, record FROM submissions WHERE conversation_id = ? ORDER BY id", (conv_id,)):
        rec = scrub(json.loads(record))
        for dropped in ("id", "conversationId"):
            rec.pop(dropped, None)
        item = index.remap(rec)
        match = SUBAGENT_REQUEST.match(item.get("requestId") or "")
        if match:   # a subagent's request id carries its owner task's database id
            item["requestId"] = f"subagent:{index.ref('task', int(match.group(1)))}"
        out.append(dict(item, ref=index.ref("submission", sid)))
    return out


def export_state(path, conversations=None, usage=True):
    """The semantic state of a store (module docstring): per conversation the active transcript, head markers, tasks and submissions; live documents; `compaction_ids`.
    `conversations` limits the export to those conversation ids (references still count every conversation); `usage=False` leaves the provider's token counts out."""
    con = _connect(path)
    try:
        index = _Index(con)
        selected = None if conversations is None else set(conversations)
        version = con.execute("SELECT version FROM durable_schema WHERE singleton = 1").fetchone()
        out, compaction = [], []
        for conv_id, record in con.execute("SELECT id, record FROM conversations ORDER BY id").fetchall():
            if selected is not None and conv_id not in selected:
                continue
            rec = json.loads(record)
            active, heads = _active(con, index, conv_id, usage)
            compaction += [dict(h, conversation=index.ref("conversation", conv_id)) for h in heads]
            out.append({"ref": index.ref("conversation", conv_id), "parent": index.remap(rec["parent"]) if "parent" in rec else None,
                        "owner": index.remap(rec["owner"]) if "owner" in rec else None, "entries": len(index.ids["entry"].get(conv_id, ())), "active": active, "head_markers": heads,
                        "tasks": _tasks(con, index, conv_id), "submissions": _submissions(con, index, conv_id)})
        retired = con.execute("SELECT count(*) FROM documents WHERE retired_at IS NOT NULL").fetchone()[0]
        return {"format": STATE_FORMAT, "schema_version": version[0] if version else None, "conversations": out, "documents": _documents(con, index, selected),
                "retired_documents": retired, "compaction_ids": compaction}
    finally:
        con.close()


def compaction_entry_ids(path):
    """The raw database ids of the entries that carry a head, ascending: the sample's `compaction_ids`. Ids are a descriptor of one store, not comparable across runtimes (the
    state's `compaction_ids` are structural references)."""
    con = _connect(path)
    try:
        return [r[0] for r in con.execute("SELECT id FROM entries WHERE head IS NOT NULL ORDER BY id")]
    finally:
        con.close()


def state_digest(state):
    """sha256 of a state's canonical JSON."""
    return _sha(state)


def diff_states(a, b, limit=50):
    """Human-readable paths at which two states (or any two JSON values) differ: `.conversations[0].active[12].digest: "ab…" != "cd…"`. Lists of unequal length are reported as
    a length difference plus the differences of the common prefix. At most `limit` lines; a last line counts the rest."""
    out = []
    _diff(a, b, "", out)
    return out[:limit] + ([f"... {len(out) - limit} more"] if len(out) > limit else [])


def _diff(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: {'absent' if k not in a else _clip(a[k])} != {'absent' if k not in b else _clip(b[k])}")
            else:
                _diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out)
    elif a != b or type(a) is not type(b):
        out.append(f"{path}: {_clip(a)} != {_clip(b)}")


def _clip(value):
    text = canonical(value)
    return text if len(text) <= 160 else text[:157] + "..."


# ---------------------------------------------------------------------------------------------------- row identity

def _pk(con, table):
    cols = sorted((r for r in con.execute(f"PRAGMA table_info({_quote(table)})") if r[5]), key=lambda r: r[5])
    return [r[1] for r in cols]


def _row_bytes(columns, row, kind_of, table, sort_keys):
    values = []
    for name, v in zip(columns, row):
        if name in ("record", "content") and isinstance(v, str):
            parsed = json.loads(v)
            if table == "document_revisions" and name == "content":
                parsed = _mask_document(kind_of.get(row[columns.index("document_id")]), parsed)
            v = json.dumps(scrub(parsed, rows=True), sort_keys=sort_keys, separators=(",", ":"), ensure_ascii=False)
        values.append(v)
    return json.dumps(values, separators=(",", ":"), ensure_ascii=False).encode()


def _rows(con, table, sort_keys, kind_of):
    columns = [r[1] for r in con.execute(f"PRAGMA table_info({_quote(table)})")]
    pk = _pk(con, table)
    order = ", ".join(_quote(c) for c in pk) if pk else "rowid"
    pk_at = [columns.index(c) for c in pk]
    for row in con.execute(f"SELECT * FROM {_quote(table)} ORDER BY {order}"):
        yield tuple(row[i] for i in pk_at) if pk_at else None, _row_bytes(columns, row, kind_of, table, sort_keys), columns


def _document_kinds(con, names):
    if "documents" not in names:
        return {}
    return {i: json.loads(k) for i, k in con.execute("SELECT id, kind FROM documents")}


def row_digest(path, tables=None, sort_keys=False):
    """{"tables": {table: {"rows": n, "sha256": hex}}, "sha256": hex}: the digest of every row of `tables` (default: the durable tables present) in primary-key order, JSON columns
    with the volatile fields removed (`scrub` with rows=True, the `pi.provider` session id masked) and re-serialised compactly with the stored key order (`sort_keys=True` ignores
    the order). Every other column and byte is compared as stored."""
    con = _connect(path)
    try:
        names = _tables(con)
        wanted = [t for t in (tables if tables is not None else DURABLE_TABLES) if t in names]
        kinds = _document_kinds(con, names)
        result = {}
        for table in wanted:
            h, n = hashlib.sha256(), 0
            for _, data, columns in _rows(con, table, sort_keys, kinds):
                if n == 0:
                    h.update(json.dumps([table] + columns).encode() + b"\n")
                h.update(data + b"\n")
                n += 1
            result[table] = {"rows": n, "sha256": h.hexdigest()}
        return {"tables": result, "sha256": _sha(result)}
    finally:
        con.close()


def rows_identical(a, b, tables=None, sort_keys=False):
    """True when the two stores' rows are identical under `row_digest` (the sample's `row_identical`)."""
    return row_digest(a, tables, sort_keys)["sha256"] == row_digest(b, tables, sort_keys)["sha256"]


def row_differences(a, b, tables=None, sort_keys=False):
    """Why two stores' rows differ, as text: the tables whose digests differ and the first differing primary key of each (empty when `rows_identical`)."""
    da, db = row_digest(a, tables, sort_keys)["tables"], row_digest(b, tables, sort_keys)["tables"]
    out = []
    ca, cb = _connect(a), _connect(b)
    try:
        ka, kb = _document_kinds(ca, _tables(ca)), _document_kinds(cb, _tables(cb))
        for table in sorted(set(da) | set(db)):
            if table not in da or table not in db:
                out.append(f"{table}: only in the {'second' if table not in da else 'first'} store")
            elif da[table]["sha256"] != db[table]["sha256"]:
                pairs = _zip_longest(_rows(ca, table, sort_keys, ka), _rows(cb, table, sort_keys, kb))
                at = next((x or y for x, y in pairs if (x and x[1]) != (y and y[1])), None)
                out.append(f"{table}: {da[table]['rows']} rows != {db[table]['rows']} rows, first difference at primary key {at[0] if at else None}")
    finally:
        ca.close()
        cb.close()
    return out


def _zip_longest(a, b):
    a, b = iter(a), iter(b)
    done = object()
    while True:
        x, y = next(a, done), next(b, done)
        if x is done and y is done:
            return
        yield (None if x is done else x), (None if y is done else y)
