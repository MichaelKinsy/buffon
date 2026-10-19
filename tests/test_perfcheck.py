# SPDX-License-Identifier: Apache-2.0
"""`buffon perfcheck`: whether a host (or each node of a cluster, one pod each) can count instructions, and what the campaign does with the answer."""
import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from buffon import backend, perfcheck
from buffon.runner import cgroup, perfcount


def info(available=True, scope="user+kernel", reason=None, paranoid=1):
    return {"available": available, "scope": scope if available else None, "paranoid": paranoid, "reason": reason}


class Collect(unittest.TestCase):
    def status(self, cap_eff=0, seccomp=0):
        return lambda: {"seccomp": seccomp, "cap_eff": cap_eff}

    def test_a_host_that_counts_says_so_and_a_user_only_host_keeps_its_reason(self):
        rec = perfcheck.collect(lambda: info(), lambda i: {"instructions": 900, "cycles": 400, "perf_scope": "user+kernel"}, self.status(1 << 38))
        self.assertEqual((rec["counted"], rec["headline"], rec["scope"], rec["instructions"], rec["cap_perfmon"]), (True, "instructions", "user+kernel", 900, True))
        self.assertIsNone(rec["reason"])
        user = perfcheck.collect(lambda: info(scope="user", reason="kernel instructions are not counted"), lambda i: {"instructions": 5, "cycles": 2, "perf_scope": "user"}, self.status())
        self.assertEqual((user["counted"], user["scope"], user["reason"]), (True, "user", "kernel instructions are not counted"))

    def test_a_refused_host_headlines_cpu_time_with_the_kernels_reason_and_never_runs_the_counted_process(self):
        calls = []
        rec = perfcheck.collect(lambda: info(False, reason="perf_event_open refused (Permission denied): perf_event_paranoid is 4", paranoid=4), lambda i: calls.append(1) or {}, self.status(0, 2))
        self.assertEqual((rec["counted"], rec["headline"], rec["paranoid"], rec["seccomp"], rec["cap_perfmon"], rec["cap_sys_admin"]), (False, "cpu time", 4, 2, False, False))
        self.assertIn("perf_event_paranoid is 4", rec["reason"])
        self.assertEqual(calls, [])

    def test_a_counter_that_opens_but_reads_nothing_is_not_counted(self):
        rec = perfcheck.collect(lambda: info(), lambda i: {}, self.status())
        self.assertFalse(rec["counted"])
        self.assertIn("read no instructions", rec["reason"])

    def test_the_record_names_no_host(self):
        rec = perfcheck.collect(lambda: info(False, reason="x"), lambda i: {}, self.status())
        self.assertEqual(set(rec), {"counted", "headline", "scope", "instructions", "cycles", "reason", "paranoid", "seccomp", "cap_perfmon", "cap_sys_admin", "kernel", "machine"})

    def test_the_capability_bits_are_perfmon_38_and_sys_admin_21(self):
        rec = perfcheck.collect(lambda: info(False, reason="x"), lambda i: {}, self.status(1 << 21))
        self.assertEqual((rec["cap_perfmon"], rec["cap_sys_admin"]), (False, True))
        self.assertEqual(perfcheck.status_fields("/nonexistent/status"), {"seccomp": None, "cap_eff": None})

    def test_the_status_file_is_parsed(self):
        with tempfile.NamedTemporaryFile("w", suffix=".status") as f:
            f.write("Name:\tx\nSeccomp:\t2\nCapEff:\t0000004000200000\n")
            f.flush()
            self.assertEqual(perfcheck.status_fields(f.name), {"seccomp": 2, "cap_eff": 0x4000200000})

    def test_count_once_restores_the_run_wide_probe_and_reads_a_real_childs_counters(self):
        saved = cgroup.PERF
        session_info = info()

        def start(i):
            def opener(event, **_):
                r, w = os.pipe()
                os.write(w, (1234 if event == perfcount.HW_INSTRUCTIONS else 55).to_bytes(8, "little") + (3).to_bytes(8, "little") + (3).to_bytes(8, "little"))
                os.close(w)
                return r
            return perfcount.Session(kernel=True, opener=opener)
        with mock.patch.object(perfcount, "start", start):
            got = perfcheck.count_once(session_info)
        self.assertEqual(got["instructions"], 1234)
        self.assertIs(cgroup.PERF, saved)


class Summary(unittest.TestCase):
    def test_one_line_per_node_with_the_reason_for_a_node_that_cannot_count(self):
        good = {"counted": True, "scope": "user+kernel", "paranoid": 1, "reason": None, "seccomp": 0, "cap_perfmon": False}
        bad = {"counted": False, "scope": None, "paranoid": 4, "reason": "refused", "seccomp": 2, "cap_perfmon": False}
        s = perfcheck.summarize([("node-a", good), ("node-b", bad)])
        self.assertFalse(s["all_counted"])
        self.assertEqual(s["text"].splitlines(), ["node-a: instructions counted (user+kernel), perf_event_paranoid 1",
                                                 "node-b: NO instruction counts, CPU time is the headline: refused (perf_event_paranoid 4, seccomp 2, CAP_PERFMON False)"])
        self.assertTrue(perfcheck.summarize([("a", good)])["all_counted"])
        self.assertFalse(perfcheck.summarize([])["all_counted"])

    def test_node_records_read_one_directory_per_node_and_name_nodes_from_the_clusters_facts(self):
        with tempfile.TemporaryDirectory() as out:
            for d, node in (("n1", "node-1"), ("n2", None)):
                os.makedirs(os.path.join(out, d))
                with open(os.path.join(out, d, "perfcheck.json"), "w") as f:
                    json.dump({"counted": d == "n1"}, f)
                if node:
                    with open(os.path.join(out, d, "cluster-facts.json"), "w") as f:
                        json.dump({"node": node}, f)
            with open(os.path.join(out, "cluster-outcome.json"), "w") as f:
                json.dump({"outcomes": [{"dir": "n1"}, {"dir": "n2"}, {"dir": "missing"}]}, f)
            self.assertEqual([(n, r["counted"]) for n, r in perfcheck.node_records(out)], [("node-1", True), ("n2", False)])
        with tempfile.TemporaryDirectory() as out:
            with open(os.path.join(out, "perfcheck.json"), "w") as f:
                json.dump({"counted": True}, f)
            self.assertEqual([n for n, _ in perfcheck.node_records(out)], [os.path.basename(out)])


class FakeBackend:
    def __init__(self, counted_by_node, exit_code=0):
        self.counted, self.exit, self.sessions = counted_by_node, exit_code, []

    def check(self, isolation="none"):
        pass

    def run(self, session):
        self.sessions.append(session)
        names = []
        for node, counted in self.counted.items():
            d = os.path.join(session.run_dir, node)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "perfcheck.json"), "w") as f:
                json.dump({"counted": counted, "scope": "user+kernel" if counted else None, "paranoid": 1 if counted else 4, "reason": None if counted else "refused", "seccomp": 0, "cap_perfmon": False}, f)
            names.append({"node": node, "dir": node})
        if names:
            with open(os.path.join(session.run_dir, "cluster-outcome.json"), "w") as f:
                json.dump({"outcomes": names}, f)
        return backend.SessionResult(session.run_dir, {}, [], 0, self.exit)


class Cli(unittest.TestCase):
    def site(self, tmp, bundle=False):
        path = os.path.join(tmp, "site.toml")
        with open(path, "w") as f:
            f.write(f'[site]\nbackend = "kubernetes"\n[local]\ncache_dir = "{tmp}/c"\n[kubernetes]\nnamespace = "n"\narch = "amd64"\n')
            f.write(f'bundle = true\nbase_image = "python@sha256:{"a" * 64}"\n' if bundle else f'image = "reg.example/buffon@sha256:{"a" * 64}"\n')
        return path

    def run_cli(self, fake, tmp, site, **kw):
        args = argparse.Namespace(site=site, out=os.path.join(tmp, "o"), bundle=kw.get("bundle"), nodes=kw.get("nodes"), json=False)
        out = io.StringIO()
        with mock.patch.object(backend, "get_backend", lambda s: fake), contextlib.redirect_stdout(out):
            return perfcheck.main(args), out.getvalue(), args

    def test_one_pod_session_per_target_runs_buffon_perfcheck_and_the_summary_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeBackend({"node-1": True, "node-2": True})
            code, text, args = self.run_cli(fake, tmp, self.site(tmp, bundle=True), bundle=os.path.join(tmp, "b"), nodes="node-1,node-2")
            self.assertEqual(code, 0)
            session = fake.sessions[0]
            self.assertEqual(session.argv[1:6], ["-m", "buffon", "perfcheck", "--out", args.out])
            self.assertEqual((session.nodes, session.bundle), (["node-1", "node-2"], os.path.join(tmp, "b")))
            summary = json.load(open(os.path.join(args.out, "perfcheck-summary.json")))
            self.assertTrue(summary["all_counted"])
            self.assertIn("node-2: instructions counted", text)

    def test_a_node_that_cannot_count_gives_exit_3_and_names_the_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, text, _ = self.run_cli(FakeBackend({"node-1": True, "node-2": False}), tmp, self.site(tmp))
            self.assertEqual(code, perfcheck.EXIT_NO_COUNTS)
            self.assertIn("node-2: NO instruction counts, CPU time is the headline: refused", text)

    def test_no_pod_output_is_a_failure_with_the_clusters_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, text, _ = self.run_cli(FakeBackend({}, exit_code=7), tmp, self.site(tmp))
            self.assertEqual(code, 7)
            self.assertIn("no pod handed back a perfcheck.json", text)

    def test_a_bundle_site_without_a_bundle_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(backend.BackendError):
                self.run_cli(FakeBackend({"n": True}), tmp, self.site(tmp, bundle=True))

    def test_a_local_run_writes_perfcheck_json_and_exits_by_whether_it_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = {"counted": False, "headline": "cpu time", "scope": None, "instructions": None, "cycles": None, "reason": "refused", "paranoid": 4, "seccomp": 0, "cap_perfmon": False, "cap_sys_admin": False}
            args = argparse.Namespace(site=None, out=os.path.join(tmp, "o"), bundle=None, nodes=None, json=False)
            with mock.patch.object(perfcheck, "collect", lambda: rec), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(perfcheck.main(args), perfcheck.EXIT_NO_COUNTS)
            self.assertEqual(json.load(open(os.path.join(tmp, "o", "perfcheck.json")))["headline"], "cpu time")
            with mock.patch.object(perfcheck, "collect", lambda: dict(rec, counted=True)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(perfcheck.main(args), 0)


if __name__ == "__main__":
    unittest.main()
