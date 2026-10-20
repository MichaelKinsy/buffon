# SPDX-License-Identifier: Apache-2.0
"""The rules of docs/DURABLE-ADAPTERS.md section 9 that a test can check.

Static (always run): the size cap of each adapter, the closed list of imports (no helper process, no worker thread, no non-public package of the runtime), the two copies of the Pi adapter are one
file set, and arms.lock hashes every adapter file. Live (opt in, `BUFFON_DURABLE_LIVE=1`; it installs the two arms, which needs Node and Go and the network, and for the Go arm
`BUFFON_SOURCE_REPO_PIG_TIP`): the protocol on a scripted conversation, no child process at ready, and the counting facade's conformance: one recorded statement stream replayed through both
adapters gives the same counters."""
import json
import os
import re
import subprocess
import tempfile
import unittest

from buffon.arms import lock, manifest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS_CAP, GO_CAP = 400, 1000   # code lines: blank lines and comment-only lines are not counted (docs/DURABLE-ADAPTERS.md section 9)
ARMS = ("pi-durable", "pig-durable", "pi-durable-main")


def adapter_dir(arm):
    return os.path.join(ROOT, "arms", arm, "adapter")


def sources(arm):
    out = []
    for base, _, files in os.walk(adapter_dir(arm)):
        out += [os.path.join(base, f) for f in sorted(files)]
    return sorted(out)


def code_lines(path):
    """Lines of code: not blank, not comment-only (`//`, `/* */` on one or many lines, `#`)."""
    count, in_block = 0, False
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if in_block:
                if "*/" in line:
                    in_block = False
                    line = line.split("*/", 1)[1].strip()
                else:
                    continue
            if not line or line.startswith(("//", "#")):
                continue
            if line.startswith("/*"):
                if "*/" in line:
                    line = line.split("*/", 1)[1].strip()
                    if not line:
                        continue
                else:
                    in_block = True
                    continue
            count += 1
    return count


def size(arm):
    suffix = ".go" if arm == "pig-durable" else ".ts"
    return {os.path.basename(p): code_lines(p) for p in sources(arm) if p.endswith(suffix)}


class Static(unittest.TestCase):
    def test_the_typescript_adapters_are_under_the_cap(self):
        for arm in ("pi-durable", "pi-durable-main"):
            parts = size(arm)
            self.assertLessEqual(sum(parts.values()), TS_CAP, f"{arm}: {parts}")

    def test_the_go_adapter_is_under_the_cap(self):
        parts = size("pig-durable")
        self.assertLessEqual(sum(parts.values()), GO_CAP, f"pig-durable: {parts}")

    def test_the_go_adapter_is_gofmt_clean_when_gofmt_is_here(self):
        try:
            done = subprocess.run(["gofmt", "-l", adapter_dir("pig-durable")], capture_output=True, text=True, timeout=60)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.skipTest("gofmt is not installed")
        self.assertEqual(done.stdout.strip(), "", "the cap counts gofmt'd lines: run gofmt -w on the adapter")

    def test_no_adapter_starts_a_helper_process_or_a_worker_thread(self):
        forbidden = {"ts": re.compile(r"child_process|worker_threads|node:cluster|\bfork\("), "go": re.compile(r'"os/exec"|exec\.Command|syscall\.ForkExec|os\.StartProcess')}
        for arm in ARMS:
            kind = "go" if arm == "pig-durable" else "ts"
            for path in sources(arm):
                if path.endswith((".ts", ".go")):
                    with open(path) as f:
                        self.assertIsNone(forbidden[kind].search(f.read()), f"{os.path.relpath(path, ROOT)} starts a process or a worker")

    def test_the_go_adapter_links_public_packages_only(self):
        for path in sources("pig-durable"):
            if path.endswith(".go"):
                with open(path) as f:
                    imports = re.findall(r'"([^"]+)"', f.read().split(")", 1)[0])
                bad = [i for i in imports if "/internal/" in i or i.startswith("internal/") or i.endswith("/internal")]
                self.assertEqual(bad, [], path)

    def test_the_two_copies_of_the_pi_adapter_are_one_file_set(self):
        a, b = sources("pi-durable"), sources("pi-durable-main")
        self.assertEqual([os.path.relpath(p, adapter_dir("pi-durable")) for p in a], [os.path.relpath(p, adapter_dir("pi-durable-main")) for p in b])
        for x, y in zip(a, b):
            with open(x, "rb") as f, open(y, "rb") as g:
                self.assertEqual(f.read(), g.read(), os.path.relpath(x, ROOT))

    def test_arms_lock_hashes_every_adapter_file(self):
        doc = lock.generate()
        for arm in ARMS:
            have = set(doc["arms"][arm]["files"])
            want = {os.path.relpath(p, os.path.join(ROOT, "arms", arm)).replace(os.sep, "/") for p in sources(arm)}
            self.assertTrue(want <= have, f"{arm}: {sorted(want - have)}")

    def test_an_adapter_arm_is_never_a_default_arm_and_the_informational_one_is_never_the_reference(self):
        arms = manifest.load_all()
        for arm in ARMS:
            self.assertFalse(arms[arm].runs_by_default)
        self.assertTrue(arms["pi-durable-main"].adapter.get("informational"))
        self.assertEqual([n for n, a in arms.items() if a.family == "pi-reference" and a.adapter], ["pi-durable"])

    def test_the_schema_versions_each_runtime_writes_and_reads_are_declared(self):
        arms = manifest.load_all()
        self.assertEqual((arms["pi-durable"].adapter.get("schema_writes", 1), arms["pi-durable"].adapter.get("schema_reads", [1])), (1, [1]))
        self.assertEqual(arms["pig-durable"].adapter["schema_writes"], 2)
        self.assertIn(1, arms["pig-durable"].adapter["schema_reads"])


LIVE = os.environ.get("BUFFON_DURABLE_LIVE") == "1"


@unittest.skipUnless(LIVE, "set BUFFON_DURABLE_LIVE=1 to install the durable arms and drive their adapters")
class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from buffon.arms import install
        cls.tmp = tempfile.TemporaryDirectory()
        cache = os.environ.get("BUFFON_DURABLE_CACHE") or os.path.join(cls.tmp.name, "cache")
        cls.ws = install.Workspace(install.Cache(cache), work_dir=cls.tmp.name)
        cls.arms = {}
        for name in ("pi-durable", "pig-durable"):
            arm = manifest.load_arm(name)
            cls.ws.install(arm)
            if arm.skip:
                raise unittest.SkipTest(f"{name} cannot run here: {arm.skip}")
            cls.arms[name] = arm

    @classmethod
    def tearDownClass(cls):
        cls.ws.__exit__()
        cls.tmp.cleanup()

    def start(self, arm, tag):
        from buffon.durable import driver
        from buffon.durable.host import DurableHost
        host = DurableHost(arm, self.ws.work, tag)
        proc = driver.Process(host, arm, 120)
        self.addCleanup(proc.release)
        proc.wait_ready()
        return proc, host

    def script(self, plan, **kw):
        from buffon.durable import script
        path, _ = script.cached(os.path.join(self.tmp.name, "scripts"), 20261018, "repeating", plan, **kw)
        return path

    def open(self, proc, host, script, create=True, mode="runtime", **extra):
        fields = {"store": host.store, "script": script, "ledger": host.ledger, "mode": mode, "conversations": 1, "create": create, "window_tokens": 200000, "compaction": {"enabled": True, "background_tokens": None},
                  "partial_interval_ms": None, "summary_fails": False, "request_log": None, "capture": None}
        fields.update(extra)
        return proc.adapter.call("open", **fields)

    def test_no_child_process_at_ready(self):
        for name, arm in self.arms.items():
            proc, _ = self.start(arm, "children")
            done = subprocess.run(["pgrep", "-P", str(proc.adapter.proc.pid)], capture_output=True, text=True)
            self.assertEqual(done.stdout.strip(), "", f"{name} has child processes at ready")

    def test_a_scripted_conversation(self):
        plan = [(0, "bench1"), (1, "bench1"), (2, "bench8")]
        for name, arm in self.arms.items():
            proc, host = self.start(arm, "conv")
            self.open(proc, host, self.script(plan), request_log=host.request_log)
            ad = proc.adapter
            for n in range(3):
                ex = ad.call("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
                self.assertEqual(ex["status"], "done", name)
            self.assertGreater(ad.call("barrier")["commits"], 3)
            st = ad.call("stats", reset=False)
            self.assertGreater(st["sql"]["commits"], 3)
            self.assertGreater(sum(st["sql"]["stmts"].values()), 20)
            self.assertTrue(ad.call("transcript", conv=0)["messages"])
            again = ad.call("turn", conv=0, n=1, request_id="t1", stream=False)   # the same request id: the existing submission, no new work
            self.assertEqual(again["status"], "done")
            ad.call("close")
            proc.close()
            self.assertEqual(ad.proc.returncode, 0, name)
            with open(host.request_log) as f:
                self.assertEqual(len(f.readlines()), 6, name)   # three turns of one round with calls and a final round each: two requests per turn

    def test_the_counting_facade_gives_the_same_counters_on_one_statement_stream(self):
        """One stream recorded from the reference, replayed through each adapter's facade and driver on a copy of the same store: the statement kinds, commits, bytes bound, rows and bytes returned agree."""
        from buffon.durable import driver
        ref = self.arms["pi-durable"]
        plan = [(n, "bench1" if n % 3 < 2 else "bench0") for n in range(5)] + [(5, "bench8"), (6, "bench8")]
        sp = self.script(plan)
        proc, host = self.start(ref, "build")
        self.open(proc, host, sp)
        for n in range(5):
            proc.adapter.call("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
        proc.adapter.call("close")
        proc.close()
        from buffon.durable import store
        store.checkpoint(host.store)
        base = os.path.join(self.tmp.name, "base.sqlite")
        with open(host.store, "rb") as f, open(base, "wb") as g:
            g.write(f.read())
        proc, host = self.start(ref, "capture")
        with open(base, "rb") as f, open(host.store, "wb") as g:
            g.write(f.read())
        self.open(proc, host, sp, create=False, capture=host.capture)
        for n in (5, 6):
            proc.adapter.call("turn", conv=0, n=n, request_id=f"t{n}", stream=False)
        proc.adapter.call("close")
        proc.close()
        counters = {}
        for name, arm in self.arms.items():
            proc, h = self.start(arm, "replay")
            with open(base, "rb") as f, open(h.store, "wb") as g:
                g.write(f.read())
            self.open(proc, h, sp, create=False, mode="floor")
            proc.adapter.call("floor_sql", stream_file=host.capture, from_turn=5, turns=2)
            st = proc.adapter.call("stats", reset=False)["sql"]
            counters[name] = {"stmts": driver.sql_kinds({"sql": st}), "commits": st["commits"], "params_bytes": st["params_bytes"], "rows_returned": st["rows_returned"], "bytes_returned": st["bytes_returned"]}
            proc.adapter.call("close")
            proc.close()
        a, b = counters["pi-durable"], counters["pig-durable"]
        self.assertEqual({k: v for k, v in a.items() if k != "stmts"}, {k: v for k, v in b.items() if k != "stmts"}, json.dumps(counters))
        self.assertEqual(a["stmts"], b["stmts"], json.dumps(counters))


if __name__ == "__main__":
    unittest.main()
