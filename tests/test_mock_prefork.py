# SPDX-License-Identifier: Apache-2.0
"""The prefork mock (buffon/mock/prefork.py) with two real worker processes: both serve one unix socket, the policy is the swarm's, the requests of both come back in arrival order as one log file."""
import http.client
import json
import os
import socket
import tempfile
import unittest

from buffon.mock import REPLY, reqlog
from buffon.mock.prefork import PreforkMock


class Unix(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost")
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)


def ask(path, agent, turn=0, tool_results=0, stream=False):
    """POST a chat completion whose prompt carries the agent's marker; returns the decoded reply."""
    messages = [{"role": "user", "content": f"[agent {agent} turn {turn}] go"}]
    for k in range(tool_results):
        messages += [{"role": "assistant", "content": None, "tool_calls": [{"id": f"c{k}"}]}, {"role": "tool", "content": "x"}]
    tools = [{"type": "function", "function": {"name": n, "parameters": {"properties": p}}} for n, p in
             (("read", {"path": {}}), ("write", {"path": {}, "content": {}}), ("bash", {"command": {"type": "string"}}))]
    conn = Unix(path)
    conn.request("POST", "/v1/chat/completions", json.dumps({"messages": messages, "tools": tools, "stream": stream}), {"Content-Type": "application/json"})
    resp = conn.getresponse()
    body = json.loads(resp.read())
    conn.close()
    return resp.status, body


class Prefork(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="prefork-")
        self.mock = PreforkMock(os.path.join(self.dir, "m.sock"), 2).start()
        self.addCleanup(self.mock.close)
        self.mock.set_policy({0: "/w/a0/project", 1: "/w/a1/project"})

    def test_workers_answer_by_the_marker_in_the_prompt_whichever_worker_takes_the_connection(self):
        for i in range(8):
            status, body = ask(self.mock.path, i % 2)
            self.assertEqual(status, 200)
            call = body["choices"][0]["message"]["tool_calls"][0]["function"]
            self.assertEqual(json.loads(call["arguments"]), {"path": f"/w/a{i % 2}/project/README.md"})
        status, body = ask(self.mock.path, 1, tool_results=3)
        self.assertEqual(body["choices"][0]["message"]["content"], REPLY)
        self.assertEqual(self.mock.offered(), {"read", "write", "shell"})

    def test_the_requests_of_every_worker_are_one_log_file_in_arrival_order_numbered_from_zero(self):
        for i in range(6):
            ask(self.mock.path, i % 2, turn=i)
        sink = reqlog.RequestLog(os.path.join(self.dir, "log"))
        self.assertEqual(self.mock.flush({"arm": "a", "scenario": "scale/agents-2", "api": None, "round": 0}, sink), 6)
        files = os.listdir(os.path.join(self.dir, "log"))
        self.assertEqual(len(files), 1)
        rows = reqlog.read(os.path.join(self.dir, "log", files[0]))
        self.assertEqual([r["index"] for r in rows], list(range(6)))
        self.assertEqual([r["t_recv_ns"] for r in rows], sorted(r["t_recv_ns"] for r in rows))
        self.assertEqual([r["body"]["messages"][0]["content"] for r in rows], [f"[agent {i % 2} turn {i}] go" for i in range(6)])
        self.assertTrue(all(r["t_reply_end_ns"] for r in rows))
        self.assertEqual(self.mock.flush({}, sink), 0)                                  # flushed: the next sample starts empty

    def test_a_new_policy_clears_the_workers_requests_and_cpu_is_reported_per_worker(self):
        ask(self.mock.path, 0)
        self.mock.set_policy({0: "/w/b0/project"})
        self.assertEqual(self.mock.flush({}, None), 0)
        status, body = ask(self.mock.path, 0)
        self.assertIn("/w/b0/project", body["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
        cpu = self.mock.cpu_ms()
        self.assertEqual(len(cpu), 2)
        self.assertTrue(all(c > 0 for c in cpu))

    def test_seen_counts_each_agents_requests_over_the_workers(self):
        for turn in range(3):
            ask(self.mock.path, 0, turn=turn)
        ask(self.mock.path, 1)
        self.assertEqual(self.mock.seen(), {0: 3, 1: 1})

    def test_streamed_replies_work_over_the_shared_socket_too(self):
        conn = Unix(self.mock.path)
        conn.request("POST", "/v1/chat/completions", json.dumps({"messages": [{"role": "user", "content": "[agent 0 turn 0] go"}], "tools": [], "stream": True}))
        raw = conn.getresponse().read().decode()
        self.assertIn("data: [DONE]", raw)

    def test_close_stops_the_workers_and_removes_the_socket(self):
        procs = [w.proc for w in self.mock.workers]
        self.mock.close()
        self.assertTrue(all(p.poll() is not None for p in procs))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "m.sock")))


if __name__ == "__main__":
    unittest.main()
