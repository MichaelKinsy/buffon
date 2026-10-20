# SPDX-License-Identifier: Apache-2.0
"""The durable store inspector and semantic exporter. The primary tests build a small store by hand with the real schema of Pi Durable 1.3.0 (schema version 1) and records in the
shape that runtime writes, so they run on plain Python with no Node. A store written by a real runtime is checked only when BUFFON_DURABLE_PI_STORE names one."""
import json
import os
import sqlite3
import tempfile
import unittest

from buffon.durable import store as D

SCHEMA = """
CREATE TABLE durable_schema (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL CHECK (version >= 0)) STRICT;
CREATE TABLE durable_metadata (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), next_id TEXT NOT NULL, next_seq INTEGER NOT NULL) STRICT;
CREATE TABLE record_ids (id INTEGER PRIMARY KEY, record_type TEXT NOT NULL CHECK (record_type IN ('conversation', 'entry', 'task', 'submission', 'document'))) STRICT;
CREATE TABLE conversations (id INTEGER PRIMARY KEY, owner_conversation_id INTEGER, owner_task_id INTEGER, record TEXT NOT NULL CHECK (json_valid(record))) STRICT;
CREATE INDEX conversations_by_owner_task ON conversations (owner_task_id, id);
CREATE TABLE entries (id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL, head INTEGER, commit_seq INTEGER NOT NULL, record TEXT NOT NULL CHECK (json_valid(record))) STRICT;
CREATE INDEX entries_by_conversation ON entries (conversation_id, id DESC);
CREATE TABLE tasks (id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL, kind TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'waiting', 'completing', 'terminal')), abort_requested INTEGER NOT NULL, background INTEGER NOT NULL,
  record TEXT NOT NULL CHECK (json_valid(record))) STRICT;
CREATE TABLE submissions (id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL, request_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('queued', 'placed', 'done', 'unanswered')), record TEXT NOT NULL CHECK (json_valid(record))) STRICT;
CREATE TABLE documents (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, family INTEGER NOT NULL, key_value TEXT NOT NULL,
  scope_kind TEXT NOT NULL CHECK (scope_kind IN ('session', 'conversation', 'task')), owner_id INTEGER NOT NULL, created_at INTEGER NOT NULL, retired_at INTEGER,
  record TEXT NOT NULL CHECK (json_valid(record))) STRICT;
CREATE TABLE document_revisions (document_id INTEGER NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('base', 'delta')), version INTEGER NOT NULL,
  content TEXT NOT NULL CHECK (json_valid(content)), PRIMARY KEY (document_id, seq)) STRICT;
"""


def js(value):
    return json.dumps(value, separators=(",", ":"))


class Builder:
    """Writes the records of a small conversation the way a durable runtime does. `offset` shifts every database id (another commit grouping), `clock` every timestamp,
    `session` the provider session id and `api` the provider's api name: none of them is part of the semantic state."""

    def __init__(self, path, offset=0, clock=1000, session="s-1", api="scripted:a", wal=False):
        self.con = sqlite3.connect(path, isolation_level=None)
        if wal:
            self.con.execute("PRAGMA journal_mode = WAL")
        self.con.executescript(SCHEMA)
        self.con.execute("INSERT INTO durable_schema VALUES (1, 1)")
        self.next, self.seq, self.clock, self.session, self.api = offset + 1, 1, clock, session, api

    def tick(self):
        self.clock += 7
        return self.clock

    def id(self, kind):
        i, self.next = self.next, self.next + 1
        self.con.execute("INSERT INTO record_ids VALUES (?, ?)", (i, kind))
        return i

    def conversation(self, parent=None, owner=None):
        i = self.id("conversation")
        rec = {"id": i}
        if parent:
            rec["parent"] = {"conversationId": parent[0], "at": parent[1]}
        if owner:
            rec["owner"] = {"conversationId": owner[0], "taskId": owner[1]}
        self.con.execute("INSERT INTO conversations VALUES (?, ?, ?, ?)", (i, owner[0] if owner else None, owner[1] if owner else None, js(rec)))
        for kind, hist in (("pi.live", "latest"), ("pi.provider", "latest"), ("pi.agent", "rewindable")):
            d = self.doc(kind, i, {} if kind == "pi.live" else {"sessionId": self.session} if kind == "pi.provider" else {"model": {"provider": "scripted", "modelId": "m"}})
            self.con.execute("UPDATE documents SET record = ? WHERE id = ?", (js({"id": d, "kind": kind, "scope": {"kind": "conversation", "conversationId": i}, "history": hist,
                                                                                    "createdAt": self.seq}), d))
        return i

    def doc(self, kind, conv, base, history="latest", deltas=()):
        i = self.id("document")
        rec = {"id": i, "kind": kind, "scope": {"kind": "conversation", "conversationId": conv}, "history": history, "fork": "initial", "createdAt": self.seq}
        self.con.execute("INSERT INTO documents VALUES (?, ?, 0, ?, 'conversation', ?, ?, NULL, ?)", (i, js(kind), js(""), conv, self.seq, js(rec)))
        self.con.execute("INSERT INTO document_revisions VALUES (?, ?, 'base', 1, ?)", (i, self.seq, js(base)))
        for ops in deltas:
            self.seq += 1
            self.con.execute("INSERT INTO document_revisions VALUES (?, ?, 'delta', 1, ?)", (i, self.seq, js(ops)))
        return i

    def entry(self, conv, kind, model=None, head=None, task=None, data=None, edits=None, **message_extra):
        i = self.id("entry")
        rec = {}
        if model is not None:
            rec["model"] = [dict(m, timestamp=self.tick(), **message_extra) if isinstance(m, dict) else m for m in model]
        rec.update(kind=kind, id=i, conversationId=conv)
        if data is not None:
            rec["data"] = data
        if head is not None:
            rec["head"] = i if head == "self" else head
        if edits:
            rec["edits"] = edits
        if task:
            rec["byTaskId"] = task
        self.seq += 1
        self.con.execute("INSERT INTO entries VALUES (?, ?, ?, ?, ?)", (i, conv, rec.get("head"), self.seq, js(rec)))
        return i

    def task(self, conv, kind, state, owner=None, input=None):
        i = self.id("task")
        rec = {"id": i, "conversationId": conv, "kind": kind, "version": 1, "input": input or {}, "background": False, "abortRequested": False, "state": state,
               "startedAt": self.tick(), "endedAt": self.tick()}
        if owner:
            rec["owner"] = owner
        self.con.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, 0, 0, ?)", (i, conv, js(kind), state["status"], js(rec)))
        return i

    def submission(self, conv, request, entry, answer, status="done"):
        i = self.id("submission")
        rec = {"conversationId": conv, "requestId": request, "type": "input", "status": status, "entry": entry, "id": i}
        if answer:
            rec["answer"] = answer
        self.con.execute("INSERT INTO submissions VALUES (?, ?, ?, ?, ?)", (i, conv, js(request), status, js(rec)))
        return i

    def assistant(self, conv, text=None, call=None, task=None, out=4, stop=None):
        content = [{"type": "text", "text": text}] if text else [{"type": "toolCall", "id": call, "name": "lookup", "arguments": {"k": call}}]
        msg = {"role": "assistant", "content": content, "api": self.api, "provider": "scripted", "model": "m",
               "usage": {"input": 11, "output": out, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 11 + out, "cost": {"total": 0}},
               "stopReason": stop or ("stop" if text else "toolUse"), "durationMs": self.clock % 5}
        return self.entry(conv, "pi.assistant", [msg], task=task)

    def user(self, conv, text):
        return self.entry(conv, "pi.user", [{"role": "user", "content": text}])

    def turn(self, conv, n, result="r" * 40, with_call=True):
        """One scripted turn: user entry, generation task, system entry, a lookup call, its result and the answer. Returns (user entry id, answer entry id)."""
        user = self.user(conv, f"[t{n}] hello")
        gen = self.task(conv, "pi.generation", {"status": "terminal", "outcome": {"status": "completed", "result": {"entryId": 0}}})
        self.entry(conv, "pi.system", [{"role": "system", "content": "", "toolsAdded": [{"name": "lookup"}]}], task=gen)
        tool = None
        if with_call:
            self.assistant(conv, call=f"c{n}.0.0", task=gen)
            tool = self.task(conv, "pi.tool", {"status": "terminal", "outcome": {"status": "completed", "result": {"kind": "model", "entryId": 0}}}, owner=gen,
                             input={"kind": "model", "callId": f"c{n}.0.0"})
            self.entry(conv, "pi.tool-result", [{"role": "toolResult", "toolCallId": f"c{n}.0.0", "toolName": "lookup", "content": [{"type": "text", "text": result}], "isError": False,
                                                 "durationMs": 3}], task=tool, data={"diagnostics": []})
        answer = self.assistant(conv, text=f"answer {n}", task=gen, out=3)
        self.submission(conv, f"t{n}", user, answer)
        return user, answer, tool

    def finish(self):
        self.con.execute("INSERT INTO durable_metadata VALUES (1, ?, ?)", (str(self.next), self.seq + 1))
        self.con.close()


def scenario(path, **kw):
    """Root conversation: three turns, a compaction that keeps the last two, a fourth turn. A fork of the root at the first turn's answer with a turn of its own, a subagent's
    child conversation owned by the third turn's tool task, a document with three edits. Returns the ids the tests need."""
    b = Builder(path, **kw)
    root = b.conversation()
    turns = [b.turn(root, n, result=("lookup result %d " % n) * 4) for n in range(3)]
    fork = b.conversation(parent=(root, turns[0][1]))
    b.turn(fork, 90, with_call=False)
    child = b.conversation(owner=(root, turns[2][2]))
    cu = b.user(child, "[s2.0.0] do it")
    ca = b.assistant(child, text="child answer")
    b.submission(child, f"subagent:{turns[2][2]}", cu, ca)
    notes = b.doc("bench.notes", root, {"items": ["n0"]}, "rewindable", deltas=[[["p", ["items"], 1, 0, ["n1"]]], [["p", ["items"], 2, 0, ["n2"]]], [["s", ["count"], 3]]])
    compaction = b.entry(root, "pi.compaction", [{"role": "user", "content": [{"type": "text", "text": "summary text"}]}], head=turns[1][0], data={"reason": "threshold"},
                         task=b.task(root, "pi.compaction", {"status": "terminal", "outcome": {"status": "completed", "result": {"entryId": 0}}}))
    last = b.turn(root, 3, result="result after compaction")
    b.finish()
    return {"root": root, "fork": fork, "child": child, "turns": turns, "last": last, "compaction": compaction, "notes": notes}


def ids_of(path, table, conv):
    con = sqlite3.connect(path)
    try:
        return [r[0] for r in con.execute(f"SELECT id FROM {table} WHERE conversation_id = ? ORDER BY id", (conv,))]
    finally:
        con.close()


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def path(self, name):
        return os.path.join(self.dir, name)


class Inspect(Files):
    def test_counts_sizes_and_schema_of_a_closed_store(self):
        p = self.path("s.sqlite")
        scenario(p)
        before = sorted(os.listdir(self.dir))
        info = D.inspect(p)
        self.assertEqual(sorted(os.listdir(self.dir)), before)   # reading leaves nothing behind
        self.assertEqual(info["main_bytes"], os.path.getsize(p))
        self.assertEqual((info["wal_bytes"], info["shm_bytes"]), (0, 0))
        self.assertEqual(info["store_bytes"], info["main_bytes"])
        self.assertEqual(info["page_count"] * info["page_size"], info["main_bytes"])
        self.assertEqual((info["schema_version"], info["freelist_count"], info["journal_mode"], info["other_tables"]), (1, 0, "delete", {}))
        self.assertEqual(list(info["store_tables"]), list(D.DURABLE_TABLES))
        t = info["store_tables"]
        self.assertEqual((t["conversations"], t["durable_schema"], t["durable_metadata"], t["submissions"], t["entries"], t["tasks"], t["documents"]), (3, 1, 1, 6, 26, 10, 10))
        self.assertEqual(t["document_revisions"], 9 + 4)
        self.assertEqual(t["record_ids"], sum(info["record_types"].values()))
        self.assertEqual(info["record_types"], {"conversation": 3, "document": 10, "entry": 26, "submission": 6, "task": 10})

    def test_a_wal_store_adds_the_log_and_shm_and_checkpoint_removes_them(self):
        p = self.path("w.sqlite")
        Builder(p, wal=True).con.close()
        hold = sqlite3.connect(p, isolation_level=None)   # a second connection keeps -wal and -shm alive
        hold.execute("PRAGMA journal_mode = WAL")
        hold.execute("PRAGMA wal_autocheckpoint = 0")
        hold.execute("DELETE FROM durable_schema")
        hold.execute("CREATE TABLE extra (x)")
        hold.execute("INSERT INTO extra VALUES (1)")
        info = D.inspect(p)
        self.assertEqual(info["journal_mode"], "wal")
        self.assertGreater(info["wal_bytes"], 0)
        self.assertGreater(info["shm_bytes"], 0)
        self.assertEqual(info["store_bytes"], info["main_bytes"] + info["wal_bytes"] + info["shm_bytes"])
        self.assertEqual(info["other_tables"], {"extra": 1})
        self.assertEqual(info["store_tables"]["durable_schema"], 0)
        self.assertIsNone(info["schema_version"])   # no row: reported as absent, not as zero
        hold.close()
        self.assertEqual(D.checkpoint(p)["busy"], 0)
        self.assertEqual(sorted(os.listdir(self.dir)), ["w.sqlite"])
        after = D.inspect(p)
        self.assertEqual((after["wal_bytes"], after["shm_bytes"], after["journal_mode"]), (0, 0, "wal"))
        self.assertEqual(after["store_bytes"], os.path.getsize(p))
        self.assertEqual(after["other_tables"], {"extra": 1})

    def test_a_missing_file_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            D.inspect(self.path("none.sqlite"))


class Export(Files):
    def setUp(self):
        super().setUp()
        self.p = self.path("a.sqlite")
        self.ids = scenario(self.p)
        self.state = D.export_state(self.p)
        self.root, self.fork, self.child = self.state["conversations"]

    def test_shape_of_the_state(self):
        self.assertEqual((self.state["format"], self.state["schema_version"], self.state["retired_documents"]), (D.STATE_FORMAT, 1, 0))
        self.assertEqual([c["ref"] for c in self.state["conversations"]], ["c0", "c1", "c2"])
        self.assertEqual((self.root["entries"], self.fork["entries"], self.child["entries"]), (21, 3, 2))
        json.dumps(self.state)

    def test_the_active_transcript_starts_at_the_newest_head_marker(self):
        # entries of the root by position: turn 0 is 0-4, turn 1 is 5-9, turn 2 is 10-14, the compaction is 15 (it keeps from entry 5), turn 3 is 16-20
        kinds = [(a["kind"], a["role"]) for a in self.root["active"]]
        turn = [("pi.user", "user"), ("pi.system", "system"), ("pi.assistant", "assistant"), ("pi.tool-result", "toolResult"), ("pi.assistant", "assistant")]
        self.assertEqual(kinds, [("pi.compaction", "user")] + turn * 3)
        self.assertEqual(self.root["head_markers"], [{"entry": "e0.15", "head": "e0.5", "kind": "pi.compaction"}])
        self.assertEqual(self.state["compaction_ids"], [{"entry": "e0.15", "head": "e0.5", "kind": "pi.compaction", "conversation": "c0"}])
        self.assertEqual(D.compaction_entry_ids(self.p), [self.ids["compaction"]])

    def test_entry_items_carry_calls_stop_reason_usage_and_a_content_digest(self):
        call = self.root["active"][3]
        self.assertEqual((call["kind"], call["calls"], call["stop"], call["usage"]), ("pi.assistant", ["c1.0.0"], "toolUse", {"input": 11, "output": 4, "cacheRead": 0, "cacheWrite": 0}))
        answer = self.root["active"][5]
        self.assertEqual((answer["calls"], answer["stop"], answer["usage"]["output"], answer["visible"]), ([], "stop", 3, True))
        self.assertEqual(answer["by_task"], "t0.2")
        self.assertEqual(self.root["active"][4]["by_task"], "t0.3")
        user = self.root["active"][1]
        self.assertEqual((user["calls"], user["stop"], user["usage"], user["by_task"], user["data"]), ([], None, None, None, None))
        self.assertTrue(all(len(a["digest"]) == 64 for a in self.root["active"]))
        self.assertEqual(len({a["digest"] for a in self.root["active"]}), 14)   # equal content, equal digest: the three turns share only their system entry
        self.assertIsNotNone(self.root["active"][4]["data"])   # the tool result's diagnostics

    def test_the_fork_sees_its_parents_history_up_to_the_fork_point_only(self):
        self.assertEqual(self.fork["parent"], {"conversationId": "c0", "at": "e0.4"})
        turn = ["pi.user", "pi.system", "pi.assistant", "pi.tool-result", "pi.assistant"]
        self.assertEqual([a["kind"] for a in self.fork["active"]], turn + ["pi.user", "pi.system", "pi.assistant"])   # the root's later compaction is not part of the fork
        self.assertEqual(self.fork["head_markers"], [])

    def test_a_child_conversation_is_exported_with_its_owner(self):
        self.assertEqual(self.child["owner"], {"conversationId": "c0", "taskId": "t0.5"})
        self.assertEqual([a["role"] for a in self.child["active"]], ["user", "assistant"])
        self.assertEqual([s["requestId"] for s in self.child["submissions"]], ["subagent:t0.5"])   # the database id inside the request id is gone

    def test_tasks_and_submissions(self):
        self.assertEqual([t["kind"] for t in self.root["tasks"]], ["pi.generation", "pi.tool"] * 3 + ["pi.compaction", "pi.generation", "pi.tool"])
        tool = self.root["tasks"][1]
        self.assertEqual(tool["state"], {"status": "terminal", "outcome": {"status": "completed", "result": {"kind": "model", "entryId": 0}}})   # entry 0 names no entry: left as stored
        self.assertEqual((tool["owner"], tool["ref"], tool["input"]), ("t0.0", "t0.1", {"kind": "model", "callId": "c0.0.0"}))
        for t in self.root["tasks"]:
            for gone in ("startedAt", "endedAt", "id", "conversationId"):
                self.assertNotIn(gone, t)
        self.assertEqual([(s["requestId"], s["status"]) for s in self.root["submissions"]], [(f"t{n}", "done") for n in range(4)])
        self.assertEqual([(s["entry"], s["answer"]) for s in self.root["submissions"]], [("e0.0", "e0.4"), ("e0.5", "e0.9"), ("e0.10", "e0.14"), ("e0.16", "e0.20")])

    def test_documents_are_materialised_from_the_base_and_its_deltas_with_volatile_fields_masked(self):
        docs = {(d["conversation"], d["kind"]): d for d in self.state["documents"]}
        self.assertEqual(docs[("c0", "bench.notes")]["value"], {"items": ["n0", "n1", "n2"], "count": 3})
        self.assertEqual(docs[("c0", "bench.notes")]["history"], "rewindable")
        for conv in ("c0", "c1", "c2"):
            self.assertEqual(docs[(conv, "pi.provider")]["value"], {"sessionId": D.MASKED})
        self.assertEqual(len(self.state["documents"]), 1 + 3 * 3)

    def test_database_ids_do_not_appear_in_the_state(self):
        self.assertNotIn('"id"', json.dumps(self.state))

    def test_limit_to_some_conversations(self):
        one = D.export_state(self.p, conversations=[self.ids["child"]])
        self.assertEqual([c["ref"] for c in one["conversations"]], ["c2"])   # references still count every conversation
        self.assertEqual({d["conversation"] for d in one["documents"]}, {"c2"})
        self.assertEqual(one["conversations"][0]["owner"], self.child["owner"])
        self.assertEqual(one["compaction_ids"], [])


class Volatility(Files):
    def pair(self, **kw):
        a, b = self.path("a.sqlite"), self.path("b.sqlite")
        return a, b, scenario(a), scenario(b, **kw)

    def test_ids_timestamps_session_ids_and_provider_names_are_not_state(self):
        a, b, _, _ = self.pair(offset=500, clock=987654, session="another-session", api="scripted:b")
        sa, sb = D.export_state(a), D.export_state(b)
        self.assertEqual(D.diff_states(sa, sb), [])
        self.assertEqual(D.state_digest(sa), D.state_digest(sb))
        self.assertEqual(sa, sb)
        self.assertFalse(D.rows_identical(a, b))   # ids differ: row identity does not forgive them
        self.assertEqual(D.compaction_entry_ids(b)[0] - D.compaction_entry_ids(a)[0], 500)

    def test_rows_ignore_exactly_the_declared_volatile_fields(self):
        a, b, _, _ = self.pair(clock=555555, session="another-session", api="scripted:b")   # timestamps, durations, session id, api name
        self.assertTrue(D.rows_identical(a, b))
        self.assertEqual(D.row_differences(a, b), [])
        self.assertEqual(D.row_digest(a), D.row_digest(b))
        self.assertEqual(set(D.row_digest(a)["tables"]), set(D.DURABLE_TABLES))
        self.assertEqual(D.row_digest(a, ["entries"])["tables"]["entries"]["rows"], 26)
        self.assertEqual(list(D.row_digest(a, ["tasks", "nope"])["tables"]), ["tasks"])

    def edit(self, path, sql, *args):
        con = sqlite3.connect(path)
        con.execute(sql, args)
        con.commit()
        con.close()

    def test_a_changed_row_is_found_by_table_and_key(self):
        a, b, _, _ = self.pair()
        key = ids_of(a, "entries", 1)[3]
        self.edit(b, "UPDATE entries SET commit_seq = commit_seq + 1 WHERE id = ?", key)
        self.assertFalse(D.rows_identical(a, b))
        self.assertTrue(D.rows_identical(a, b, tables=["tasks", "submissions"]))
        found = D.row_differences(a, b)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("entries: 26 rows != 26 rows"), found)
        self.assertIn(f"primary key ({key},)", found[0])
        self.assertEqual(D.state_digest(D.export_state(a)), D.state_digest(D.export_state(b)))   # commit_seq is row identity, not state

    def test_key_order_is_a_row_difference_unless_sorted(self):
        a, b, ids, _ = self.pair()
        (rec,) = sqlite3.connect(b).execute("SELECT record FROM documents WHERE id = ?", (ids["notes"],)).fetchone()
        self.edit(b, "UPDATE documents SET record = ? WHERE id = ?", js(dict(reversed(list(json.loads(rec).items())))), ids["notes"])
        self.assertFalse(D.rows_identical(a, b))
        self.assertTrue(D.rows_identical(a, b, sort_keys=True))
        self.assertEqual(D.diff_states(D.export_state(a), D.export_state(b)), [])

    def test_usage_can_be_left_out_of_the_state(self):
        a, b, ids, _ = self.pair()
        call = ids_of(a, "entries", 1)[18]   # turn 3's lookup call
        self.edit(b, "UPDATE entries SET record = replace(record, '\"output\":4', '\"output\":5') WHERE id = ?", call)
        paths = D.diff_states(D.export_state(a), D.export_state(b))
        self.assertEqual(paths, [".conversations[0].active[13].usage.output: 4 != 5"])
        self.assertEqual(D.diff_states(D.export_state(a, usage=False), D.export_state(b, usage=False)), [])
        self.assertFalse(D.rows_identical(a, b))   # row identity keeps usage


class Planted(Files):
    def setUp(self):
        super().setUp()
        self.a = self.path("a.sqlite")
        self.ids = scenario(self.a)
        self.state = D.export_state(self.a)
        self.root_entries = ids_of(self.a, "entries", self.ids["root"])

    def changed(self, sql, *args):
        b = self.path("b.sqlite")
        if os.path.exists(b):
            os.remove(b)
        scenario(b)
        con = sqlite3.connect(b)
        con.execute(sql, args)
        con.commit()
        con.close()
        return D.export_state(b)

    def test_a_tool_result_text(self):
        other = self.changed("UPDATE entries SET record = replace(record, 'result after compaction', 'result after compactioN') WHERE id = ?", self.root_entries[19])
        paths = D.diff_states(self.state, other)
        self.assertEqual(paths, [paths[0]])
        self.assertRegex(paths[0], r"^\.conversations\[0\]\.active\[14\]\.digest: ")
        self.assertNotEqual(D.state_digest(self.state), D.state_digest(other))

    def test_a_document_value(self):
        other = self.changed("UPDATE document_revisions SET content = ? WHERE content LIKE '%n2%'", js([["p", ["items"], 2, 0, ["n3"]]]))
        paths = D.diff_states(self.state, other)
        self.assertEqual(len(paths), 1)
        self.assertRegex(paths[0], r'^\.documents\[\d+\]\.value\.items\[2\]: "n2" != "n3"$')

    def test_a_submission_status_and_a_task_outcome(self):
        other = self.changed("""UPDATE submissions SET record = replace(record, '"status":"done"', '"status":"unanswered"'), status = 'unanswered' WHERE request_id = '"t1"'""")
        self.assertEqual(D.diff_states(self.state, other), ['.conversations[0].submissions[1].status: "done" != "unanswered"'])
        task = ids_of(self.a, "tasks", self.ids["root"])[0]
        other = self.changed("""UPDATE tasks SET record = replace(record, '"status":"completed"', '"status":"failed"') WHERE id = ?""", task)
        self.assertEqual(D.diff_states(self.state, other), ['.conversations[0].tasks[0].state.outcome.status: "completed" != "failed"'])

    def test_a_compaction_boundary_moves(self):
        keep = self.ids["turns"][2][0]   # keep from turn 2 instead of turn 1
        first = self.ids["turns"][1][0]
        other = self.changed("UPDATE entries SET head = ?, record = replace(record, ?, ?) WHERE id = ?", keep, f'"head":{first}', f'"head":{keep}', self.ids["compaction"])
        found = D.diff_states(self.state, other)
        self.assertIn('.compaction_ids[0].head: "e0.5" != "e0.10"', found)
        self.assertIn('.conversations[0].head_markers[0].head: "e0.5" != "e0.10"', found)
        self.assertTrue(any("length" in f for f in found), found)   # the active transcript is five entries shorter

    def test_a_missing_entry_shifts_lengths(self):
        other = self.changed("DELETE FROM entries WHERE id = ?", self.root_entries[7])
        found = D.diff_states(self.state, other, limit=500)
        self.assertIn(".conversations[0].active: length 16 != 15", found)
        self.assertIn(".conversations[0].entries: 21 != 20", found)

    def test_diff_reports_added_keys_lengths_types_and_clips(self):
        self.assertEqual(D.diff_states({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1], "c": 2}), [".b: length 2 != 1", ".c: absent != 2"])
        self.assertEqual(D.diff_states({"a": 1}, {"a": True}), [".a: 1 != true"])
        (clipped,) = D.diff_states({"a": "x" * 500}, {"a": "y"})
        self.assertEqual(clipped, '.a: "' + "x" * 156 + '... != "y"')
        many = D.diff_states({"v": list(range(100))}, {"v": list(range(1, 101))}, limit=5)
        self.assertEqual((len(many), many[-1]), (6, "... 95 more"))


class Deltas(unittest.TestCase):
    def test_every_operation(self):
        v = {"items": ["a", "b", "c"], "s": "hello", "o": {"x": 1, "y": 2}}
        D.apply_ops(v, [["s", ["o", "x"], 9], ["d", ["o", "y"]], ["a", ["s"], " world"], ["t", ["s"], 6], ["p", ["items"], 1, 1, ["B", "B2"]], ["d", ["items", 0]],
                        ["m", ["items"], [2, 0, 1]], ["s", ["items", 3], "z"]])
        self.assertEqual(v, {"items": ["c", "B", "B2", "z"], "s": "world", "o": {"x": 9}})
        self.assertEqual(D.apply_ops({"a": 1}, [["r", [1, 2]], ["p", [], 1, 0, [3]]]), [1, 3, 2])
        with self.assertRaises(ValueError):
            D.apply_ops({}, [["q", ["x"]]])


class RealStore(Files):
    @unittest.skipUnless(os.environ.get("BUFFON_DURABLE_PI_STORE"), "set BUFFON_DURABLE_PI_STORE to a store file written by Pi Durable 1.3.0 or by the Go port to check it")
    def test_a_store_written_by_a_real_runtime(self):
        p = os.environ["BUFFON_DURABLE_PI_STORE"]
        info = D.inspect(p)
        state = D.export_state(p)
        self.assertEqual(info["schema_version"], 1)
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(len(state["conversations"]), info["store_tables"]["conversations"])
        self.assertEqual(D.diff_states(state, D.export_state(p)), [])
        self.assertTrue(D.rows_identical(p, p))
        for c in state["conversations"]:
            self.assertEqual(len(c["submissions"]), len({s["ref"] for s in c["submissions"]}))


if __name__ == "__main__":
    unittest.main()
