# SPDX-License-Identifier: Apache-2.0
"""An arm and its A/A copy must look the same to the harness: every path, env value and argv element that carries the arm id has one length, and the copies take turns going first."""
import http.server
import json
import os
import tempfile
import threading
import types
import unittest
import urllib.request

from buffon.arms import install
from buffon.runner import engine
from buffon.runner.harness import Harness
from tests.test_arms import CloneTest
from tests.test_engine import FakeCtx, arm, runner
from buffon.workloads import Workload


class Parity(unittest.TestCase):
    def prepare(self):
        helper = CloneTest()
        tmp = tempfile.mkdtemp()
        ws = install.Workspace(install.Cache(os.path.join(tmp, "cache"), offline=True), work_dir=os.path.join(tmp, "w"))
        ws.__enter__()
        self.addCleanup(ws.__exit__, None, None, None)
        a = helper.arm(ws)
        b = ws.clone(a, "pi-node-b")
        b.twin_of = a.id
        b.label = a.label + " (A/A copy)"
        a.modes = dict(a.modes, print=["-p", "{prompt}"])
        b.modes = a.modes
        return ws, a, b

    def harnesses(self, a, b, work, server):
        saved = Harness.__init__.__globals__["load_writer"]
        Harness.__init__.__globals__["load_writer"] = lambda arm_: (lambda spec: {})
        try:
            return Harness(a, work, server, tag="t", extensions=()), Harness(b, work, server, tag="t", extensions=())
        finally:
            Harness.__init__.__globals__["load_writer"] = saved

    def test_paths_env_and_argv_have_one_length_and_differ_only_in_the_copy_letter(self):
        ws, a, b = self.prepare()
        server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
        with tempfile.TemporaryDirectory() as work:
            ha, hb = self.harnesses(a, b, work, server)
            self.assertEqual(os.path.basename(a.install_dir), "pi-node-a")
            self.assertEqual(os.path.basename(b.install_dir), "pi-node-b")
            pairs = [(ha.cwd, hb.cwd), (ha.home, hb.home), (ha.agent_dir, hb.agent_dir), (ha.sessions, hb.sessions), (ha.disk, hb.disk), (a.binary, b.binary)]
            pairs += [(ha.env[k], hb.env[k]) for k in sorted(set(ha.env) | set(hb.env))]
            pairs += list(zip(ha.print_argv("hi"), hb.print_argv("hi")))
            self.assertEqual(sorted(ha.env), sorted(hb.env))
            self.assertEqual(len(ha.print_argv("hi")), len(hb.print_argv("hi")))
            for x, y in pairs:
                self.assertEqual(len(x), len(y), (x, y))
                self.assertEqual(x.replace("pi-node-a", "pi-node-X").replace(work, ""), y.replace("pi-node-b", "pi-node-X").replace(work, ""), (x, y))

    def test_the_request_body_a_harness_sends_is_as_long_for_the_copy(self):
        ws, a, b = self.prepare()
        sizes = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                sizes.append(len(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        port = httpd.server_address[1]
        server = types.SimpleNamespace(base_url=f"http://127.0.0.1:{port}/v1", origin=f"http://127.0.0.1:{port}")
        with tempfile.TemporaryDirectory() as work:
            for h in self.harnesses(a, b, work, server):
                body = json.dumps({"system": "HOME is " + h.env["HOME"] + " in " + h.cwd, "argv0": h.arm.binary}).encode()
                req = urllib.request.Request(h.base_url, body, {"Content-Type": "application/json"})
                urllib.request.urlopen(req).read()
        self.assertEqual(len(sizes), 2)
        self.assertEqual(sizes[0], sizes[1])


class Order(unittest.TestCase):
    def test_over_a_run_each_copy_goes_first_in_half_the_rounds(self):
        w = Workload(id="t/w", family="t", fn=lambda ctx, a: {"cpu_ms": 1.0})
        r = runner([w], [arm("a"), arm("b")], rounds=11, warmup=1, apis=["openai-completions"], allow_short=True)
        r.measure(FakeCtx(), engine.with_twins(r.plan.arms, "all"))
        for base in ("a", "b"):
            a_first = 0
            for rnd in range(12):
                seq = [s["arm"] for s in r.samples if s["round"] == rnd and s["arm"] in (base, base + "-b")]
                a_first += seq[0] == base
            self.assertLessEqual(abs(a_first - 6), 1, base)

    def test_a_pair_stays_adjacent_and_every_arm_runs_once(self):
        arms = engine.with_twins([arm("a"), arm("b"), arm("c")], "all")
        for rnd in range(8):
            order = [x.id for x in engine.arm_order(arms, rnd, rnd)]
            self.assertEqual(sorted(order), sorted(x.id for x in arms))
            for base in "abc":
                self.assertEqual(abs(order.index(base) - order.index(base + "-b")), 1)


if __name__ == "__main__":
    unittest.main()
