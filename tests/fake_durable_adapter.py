# SPDX-License-Identifier: Apache-2.0
"""A fake durable adapter for the tests of the runner's side (docs/DURABLE-ADAPTERS.md): it speaks the protocol and writes a real-schema store with the helper of tests/test_durable_store.py.

A turn is four commits (the user entry, the generation and the tool call, the tool result, the answer and the submission). A resumed turn finds what is already stored and does the rest, so a
kill after any commit and a resubmission of the same request id give the uncrashed store: the exactly-once behaviour a real runtime has. Knobs, by environment variable:
  FAKE_DIVERGE=1   the tool result's text differs (a planted difference of work)
  FAKE_SCHEMA=2    the store it writes is schema version 2; FAKE_READS="1" refuses a store of another version
  FAKE_NODOCS=1    `doc_edit` answers `unsupported`
  FAKE_DUP=1       a resumed turn writes its answer twice (a duplicated model answer)"""
import json
import os
import signal
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_durable_store import Builder  # noqa: E402

ARM = os.environ.get("FAKE_ARM", "fake")


class Attached(Builder):
    def __init__(self, path):
        self.con = sqlite3.connect(path, isolation_level=None)
        self.next = self.con.execute("SELECT coalesce(max(id), 0) + 1 FROM record_ids").fetchone()[0]
        self.seq = self.con.execute("SELECT coalesce(max(commit_seq), 0) + 1 FROM entries").fetchone()[0]
        self.clock, self.session, self.api = 5000, "s-1", "scripted:a"


class Fake:
    def __init__(self):
        self.commits = 0
        self.armed = None
        self.b = None

    def commit(self):
        self.commits += 1
        if self.armed is not None:
            self.armed -= 1
            if self.armed == 0:
                sys.stdout.write(json.dumps({"event": "crashing", "commit": self.commits, "k": self.k}) + "\n")
                sys.stdout.flush()
                os.kill(os.getpid(), signal.SIGKILL)

    def stage(self, conv, n):
        c = self.b.con
        have = lambda sql, *a: c.execute(sql, a).fetchone()[0]   # noqa: E731
        call = f"c{n}.0.0"
        user = have("SELECT count(*) FROM entries WHERE json_extract(record,'$.model[0].content') = ?", f"[t{n}] hello")
        done = have("SELECT count(*) FROM submissions WHERE request_id = ?", json.dumps(f"t{n}"))
        return user, have("SELECT count(*) FROM entries WHERE record LIKE ?", f'%"toolCallId":"{call}"%'), done

    def turn(self, conv, n, resumed):
        b = self.b
        user_n, tool_n, done = self.stage(conv, n)
        if done:
            return
        text = "r" * 40 + ("X" if os.environ.get("FAKE_DIVERGE") else "")
        if not user_n:
            user = b.user(conv, f"[t{n}] hello")
            self.commit()
        else:
            user = b.con.execute("SELECT id FROM entries WHERE json_extract(record,'$.model[0].content') = ?", (f"[t{n}] hello",)).fetchone()[0]
        if not tool_n:
            gen = b.task(conv, "pi.generation", {"status": "terminal", "outcome": {"status": "completed", "result": {"entryId": 0}}})
            b.entry(conv, "pi.system", [{"role": "system", "content": "", "toolsAdded": [{"name": "lookup"}]}], task=gen)
            b.assistant(conv, call=f"c{n}.0.0", task=gen)
            self.commit()
            tool = b.task(conv, "pi.tool", {"status": "terminal", "outcome": {"status": "completed", "result": {"kind": "model", "entryId": 0}}}, owner=gen, input={"kind": "model", "callId": f"c{n}.0.0"})
            with open(self.ledger, "a") as f:
                f.write(f"lookup c{n}.0.0\n")
            b.entry(conv, "pi.tool-result", [{"role": "toolResult", "toolCallId": f"c{n}.0.0", "toolName": "lookup", "content": [{"type": "text", "text": text}], "isError": False, "durationMs": 3}],
                    task=tool, data={"diagnostics": []})
            self.commit()
        answer = b.assistant(conv, text=f"answer {n}", out=3)
        if resumed and os.environ.get("FAKE_DUP"):
            b.assistant(conv, text=f"answer {n}", out=3)
        b.submission(conv, f"t{n}", user, answer)
        self.commit()


def main():
    if "--version" in sys.argv:
        print(json.dumps({"adapter": ARM, "protocol": 1, "version": "0.0", "runtime_versions": {ARM: "0.0"}}))
        return
    fake = Fake()
    out = sys.stdout
    out.write(json.dumps({"event": "ready", "protocol": 1, "adapter": ARM, "env": "native", "pid": os.getpid(), "mono_ns": time.perf_counter_ns(), "runtime_versions": {ARM: "0.0"}}) + "\n")
    out.flush()
    resumed = False
    for line in sys.stdin:
        req = json.loads(line)
        op, rid = req["op"], req["id"]
        res = {"ok": True}
        if op == "open":
            fake.ledger = req["ledger"]
            if req["create"]:
                b = Builder(req["store"])
                b.con.execute("UPDATE durable_schema SET version = ?", (int(os.environ.get("FAKE_SCHEMA", "1")),))
                b.conversation()
                b.finish()
            else:
                version = sqlite3.connect(req["store"]).execute("SELECT version FROM durable_schema").fetchone()[0]
                reads = [int(v) for v in os.environ.get("FAKE_READS", "1").split(",")]
                if os.environ.get("FAKE_SCHEMA") and int(os.environ["FAKE_SCHEMA"]) in reads:   # a runtime that migrates a store it opens to its own schema version
                    sqlite3.connect(req["store"]).execute("UPDATE durable_schema SET version = ?", (int(os.environ["FAKE_SCHEMA"]),)).connection.commit()
                    version = int(os.environ["FAKE_SCHEMA"])
                if version not in reads:
                    out.write(json.dumps({"id": rid, "ok": False, "error": f"Durable SQLite schema version {version} is newer than supported version {max(reads)}"}) + "\n")
                    out.flush()
                    continue
            fake.b = Attached(req["store"])
            fake.root = fake.b.con.execute("SELECT min(id) FROM conversations").fetchone()[0]
            fake.request_log = req.get("request_log")
            res["conversations"] = [fake.root]
            res["settings"] = {"window_tokens": req["window_tokens"]}
        elif op == "turn":
            fake.turn(fake.root, req["n"], resumed)
            if fake.request_log:
                with open(fake.request_log, "a") as f:
                    f.write(json.dumps({"seq": req["n"], "kind": "turn", "messages": [{"r": "user", "n": 10, "h": "x", "p": f"[t{req['n']}] hello"}]}) + "\n")
            res.update(status="done", reason=None, submission=1, adapter_ms=0.1, first_request_mono_ns=time.perf_counter_ns(), model_ns=1000, requests=2)
        elif op == "barrier" or op == "resume":
            resumed = resumed or op == "resume"
            res["commits"] = fake.commits
        elif op == "stats":
            res.update(sql={"stmts": {"select": 3, "insert": 2, "update": 1, "delete": 0, "ddl": 0, "pragma": 1, "other": 0}, "commits": 4, "rollbacks": 0, "params_bytes": 10, "rows_returned": 5, "bytes_returned": 50},
                       provider={"requests": 2, "model_ns": 1000})
        elif op == "transcript":
            rows = fake.b.con.execute("SELECT record FROM entries WHERE conversation_id = ? ORDER BY id", (fake.root,)).fetchall()
            res["messages"] = [{"r": "user" if json.loads(r[0])["kind"] == "pi.user" else "other", "n": 1, "h": str(len(r[0])), "p": ""} for r in rows]
        elif op == "doc_edit" and os.environ.get("FAKE_NODOCS"):
            res = {"ok": False, "unsupported": "the fake has no documents"}
        elif op == "crash_after":
            fake.armed, fake.k = req["k"], req["k"]
        elif op == "close":
            fake.b.con.close()
        res["id"] = rid
        out.write(json.dumps(res) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
