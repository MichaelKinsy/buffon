# SPDX-License-Identifier: MIT
# Cases ported from pigbench's tests (test_overhead_driver.py, test_reliability_report.py) where the code they test is vendored; new cases for Buffon's own workloads.
import http.client
import json
import os
import pathlib
import tempfile
import threading
import unittest
from buffon.arms import manifest  # noqa: E402

from buffon import mock, workloads
from buffon.fixtures import sessions
from buffon.workloads import longsession, overhead, reliability, soak, streaming


class FakeRpc:
    """Replays what Pi 1.1.0 emitted at the 365th turn of a long session: the next prompt arrives while automatic compaction runs."""

    def __init__(self, script):
        self.script, self.records, self.cursor, self.sent = list(script), [], 0, []

    def send(self, cmd):
        self.sent.append(cmd)
        for rec in self.script.pop(0):
            self.records.append((mock.now_ns(), rec))
        return 0, mock.now_ns()

    def wait_for(self, predicate, timeout, start=0):
        for i in range(start, len(self.records)):
            if predicate(self.records[i][1]):
                return self.records[i][0], self.records[i][1], i + 1
        return None


class Meter:
    def cpu_ms(self):
        return 0.0

    def max_proc_rss_mib(self):
        return 1.0


class Opts:
    timeout = 1


class Ctx:
    server = mock.MockServer.__new__(mock.MockServer)
    opts = Opts()


Ctx.server.requests = []
BUSY = {"type": "response", "command": "prompt", "success": False, "error": "Agent is already processing. Specify streamingBehavior ('steer' or 'followUp') to queue the message."}


class DriveTurns(unittest.TestCase):
    def test_prompt_refused_during_compaction_is_resent_after_it_ends(self):
        rpc = FakeRpc([[{"type": "agent_end"}], [{"type": "compaction_start"}, BUSY, {"type": "compaction_end"}, {"type": "agent_settled"}], [{"type": "agent_end"}]])
        rpc.records.append((0, {"type": "response"}))
        series = []
        self.assertIsNone(overhead.drive_turns(Ctx, rpc, Meter(), 2, series))
        self.assertEqual(len(series), 2)
        self.assertEqual([c["type"] for c in rpc.sent], ["prompt"] * 3)

    def test_the_compaction_in_progress_refusal_is_also_retried(self):
        busy = dict(BUSY, error="Cannot submit a prompt while compaction is in progress. Wait for compaction to finish and retry.")
        rpc = FakeRpc([[{"type": "agent_end"}], [busy, {"type": "compaction_end"}], [{"type": "agent_end"}]])
        rpc.records.append((0, {"type": "response"}))
        self.assertIsNone(overhead.drive_turns(Ctx, rpc, Meter(), 2, []))

    def test_a_harness_that_never_finishes_is_reported_with_its_last_events(self):
        bad = overhead.drive_turns(Ctx, FakeRpc([[{"type": "turn_end"}]]), Meter(), 1, [])
        self.assertIn("no agent_end", bad)
        self.assertIn("turn_end", bad)


class DialectRpc:
    def __init__(self, script, dialect=None):
        self.script, self.records, self.cursor, self.sent, self.n = list(script), [], 0, [], 0
        if dialect is not None:
            self.dialect = dialect

    def send(self, cmd):
        self.n += 1
        ident = f"b{self.n}"
        self.sent.append(dict(cmd, id=ident))
        for rec in self.script.pop(0):
            self.records.append((mock.now_ns(), {k: (ident if v == "<id>" else v) for k, v in rec.items()}))
        return ident, mock.now_ns()

    wait_for = FakeRpc.wait_for


class Dialect(unittest.TestCase):
    def test_get_state_answered_with_only_the_request_id_is_ready(self):
        self.assertIsNotNone(overhead.wait_ready(DialectRpc([[{"type": "response", "id": "<id>", "success": True}]])))
        self.assertIsNone(overhead.wait_ready(DialectRpc([[{"type": "response", "id": "elsewhere", "success": True}]])))

    def test_prompt_field_follows_the_arm_dialect(self):
        self.assertEqual(overhead.prompt_command(DialectRpc([]), "hi"), {"type": "prompt", "message": "hi"})
        self.assertEqual(overhead.prompt_command(DialectRpc([], {"prompt_field": "content"}), "hi"), {"type": "prompt", "content": "hi"})

    def test_a_busy_harness_without_compaction_events_is_retried_until_it_accepts(self):
        busy = {"type": "response", "command": "prompt", "success": False, "error": "Agent is currently compacting"}
        rpc = DialectRpc([[busy], [busy], [busy], [{"type": "agent_end"}]])
        series = []
        self.assertIsNone(overhead.drive_turns(Ctx, rpc, Meter(), 1, series))
        self.assertEqual(len(rpc.sent), 4)
        self.assertEqual(series[0]["refused_while_busy"], "Agent is currently compacting")

    def test_the_manifest_dialect_of_rpi_names_the_content_field(self):
        from buffon.arms import manifest
        self.assertEqual(manifest.load_arm("rpi").rpc_dialect, {"prompt_field": "content"})
        self.assertEqual(manifest.load_arm("pi-node").rpc_dialect, {})


class Soak(unittest.TestCase):
    def series(self, f, n=40, step=60):
        return [{"t_s": i * step, "fds": f(i), "rss_mib": 100 + f(i)} for i in range(n)]

    def test_flat_series_passes_and_a_leak_fails(self):
        self.assertTrue(soak.judge(self.series(lambda i: 20 + (i % 2)), "fds")["flat"])
        leak = soak.judge(self.series(lambda i: 20 + i), "fds")
        self.assertFalse(leak["flat"])
        self.assertAlmostEqual(leak["slope_per_h"], 60.0, places=3)

    def test_warm_up_growth_in_the_first_half_is_ignored(self):
        self.assertTrue(soak.judge(self.series(lambda i: min(i, 10) * 3 + 20), "fds")["flat"])

    def test_memory_band_is_relative(self):
        self.assertTrue(soak.judge([{"t_s": i * 60, "rss_mib": 200 + (8 if i % 2 else 0)} for i in range(30)], "rss_mib")["flat"])
        self.assertFalse(soak.judge([{"t_s": i * 60, "rss_mib": 200 + i * 2} for i in range(30)], "rss_mib")["flat"])

    def test_too_few_samples_is_undecided_not_flat(self):
        self.assertIsNone(soak.judge([{"t_s": 0, "fds": 1}, {"t_s": 60, "fds": 1}], "fds")["flat"])
        s = [{"t_s": 0, "processes": 1, "threads": 5, "fds": 10, "rss_mib": 50.0}, {"t_s": 60, "processes": 1, "threads": 5, "fds": 900, "rss_mib": 500.0}]
        self.assertIsNone(soak.summarize({"series": s, "turns": 3})["flat"])
        self.assertFalse(soak.summarize({"series": s, "turns": 3, "failure": "boom"})["flat"])

    def test_a_flat_run_without_pss_is_flat_and_one_growing_series_is_not(self):
        flat = [{"t_s": i * 60, "processes": 1, "threads": 9, "fds": 10 + i % 2, "rss_mib": 100.0} for i in range(20)]
        self.assertTrue(soak.summarize({"series": flat})["flat"])
        self.assertFalse(soak.summarize({"series": [dict(r, fds=10 + i) for i, r in enumerate(flat)]})["flat"])

    def test_small_counts_use_the_absolute_floor(self):
        self.assertTrue(soak.judge([{"t_s": i * 60, "fds": 10 + (2 if i % 2 else 0)} for i in range(20)], "fds")["flat"])

    def test_the_raw_sample_is_flat_metrics_with_the_series_under_its_own_key(self):
        flat = [{"t_s": i * 60, "processes": 1, "threads": 9, "fds": 10, "rss_mib": 100.0} for i in range(20)]
        rec = soak.sample_of("a", {"series": flat, "turns": 7})
        self.assertEqual((rec["flat"], rec["undecided"], rec["turns"], rec["fds_flat"]), (True, False, 7, True))
        self.assertEqual(rec["rss_mib_slope_per_h"], 0.0)
        self.assertEqual(len(rec["series"]["samples"]), 20)
        leak = soak.sample_of("a", {"series": [dict(r, fds=10 + i) for i, r in enumerate(flat)], "turns": 7})
        self.assertFalse(leak["flat"])
        self.assertEqual(soak.sample_of("a", {"series": flat, "failure": "boom"})["failure"], "boom")
        from buffon.runner import raw
        raw.check_sample(dict(rec, arm="a", scenario="soak/stress", api=None, round=0, warmup=False))

    def test_each_arm_reports_its_own_egress_and_others_keep_running(self):
        class M:
            mode = "cgroup-direct"

            def __init__(self, remote):
                self.egress = {remote} if remote else set()

            def snapshot(self):
                return {"processes": 1, "threads": 1, "fds": 1, "rss_mib": 1.0, "pss_mib": None, "cpu_ms": 0}

            def close(self):
                pass

        class R:
            def __init__(self):
                self.cond, self.records, self.cursor = threading.Condition(), [], 0
                self.proc = type("P", (), {"poll": lambda self: 0})()

            def close(self, grace=10):
                pass

        class O:
            interval, think_ms, seconds, timeout = 0.05, 0, 0.3, 1

        meters = {"x": M("192.0.2.1:443"), "y": M(None)}
        saved = (soak.start_rpc, soak.wait_ready, soak.drive_turns)
        soak.start_rpc = lambda ctx, arm, *a: (None, meters[arm.id], R())
        soak.wait_ready = lambda rpc: (0, {}, 1)
        soak.drive_turns = lambda ctx, rpc, meter, n, rows: ("boom" if meter is meters["x"] else None)
        try:
            class C:
                _harnesses = {}

                def harness(self, arm, scenario, **kw):
                    self._harnesses[(arm.id, scenario)] = type("H", (), {"cwd": "/tmp"})()

            outs, threads, shared = {}, [], threading.Event()
            for aid in ("x", "y"):
                arm = type("A", (), {"id": aid})()
                outs[aid] = {}
                threads.append(threading.Thread(target=soak.run_arm, args=(arm, C(), type("S", (), {"reset": lambda self, **kw: None})(), O, shared, outs[aid])))
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        finally:
            soak.start_rpc, soak.wait_ready, soak.drive_turns = saved
        self.assertEqual(outs["x"].get("egress"), ["192.0.2.1:443"])
        self.assertNotIn("egress", outs["y"])
        self.assertEqual(outs["x"]["failure"], "boom")
        self.assertGreater(outs["y"]["turns"], 1)
        self.assertFalse(shared.is_set())


class Reliability(unittest.TestCase):
    def test_exhausted_retries_reported_as_success_break_the_invariant(self):
        res = {"timed_out": False, "code": 0, "stderr": ""}
        self.assertEqual(reliability.print_invariants("http-429-exhausted", res, 0, 120), ["reported success with no reply from the model"])
        self.assertEqual(reliability.print_invariants("http-429-exhausted", dict(res, code=1), 0, 120), [])
        self.assertEqual(reliability.print_invariants("http-429-retry", res, 1, 120), [])
        self.assertEqual(reliability.print_invariants("http-500-retry", dict(res, timed_out=True, stderr="panic: x"), 0, 120), ["hung: no exit within 120s", "crash trace on stderr"])

    def test_role_signature_marks_tool_errors_on_every_wire_api(self):
        chat = mock.Request(0, "openai-completions", {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}, {"role": "assistant", "tool_calls": [{}]},
                                                                  {"role": "tool", "content": "Error: aborted"}, {"role": "user", "content": "go on"}]}, 1, 0)
        self.assertEqual(reliability.role_signature(chat), ["user", "assistant", "tool:error", "user"])
        anth = mock.Request(0, "anthropic-messages", {"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": []},
                                                                  {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok fine"}]}]}, 1, 0)
        self.assertEqual(reliability.role_signature(anth), ["user", "assistant", "tool"])
        anth_err = mock.Request(0, "anthropic-messages", {"messages": [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "interrupted"}]}]}, 1, 0)
        self.assertEqual(reliability.role_signature(anth_err), ["tool:error"])

    def test_session_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, torn = os.path.join(tmp, "g.jsonl"), os.path.join(tmp, "t.jsonl")
            with open(good, "w") as f:
                f.write('{"type":"session"}\n{"type":"message"}\n')
            with open(torn, "w") as f:
                f.write('{"type":"session"}\n{"type":"mess')
            self.assertEqual(reliability.session_ok(good), (True, 2))
            self.assertFalse(reliability.session_ok(torn)[0])

    def test_every_fault_has_a_plan_or_is_a_host_fault(self):
        for name in reliability.FAULTS:
            if name in reliability.SESSION_FAULTS:
                self.assertEqual(reliability.fault_plan(name), {})
            else:
                self.assertTrue(reliability.fault_plan(name), name)
        self.assertEqual(reliability.fault_plan("keepalive-only")[0].keepalives, 25)


class Sessions(unittest.TestCase):
    def test_generation_is_deterministic_and_has_pis_session_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = sessions.generate_turns(os.path.join(tmp, "a.jsonl"), 12, 5)
            b = sessions.generate_turns(os.path.join(tmp, "b.jsonl"), 12, 5)
            c = sessions.generate_turns(os.path.join(tmp, "c.jsonl"), 12, 6)
            self.assertEqual(a["sha256"], b["sha256"])
            self.assertNotEqual(a["sha256"], c["sha256"])
            with open(os.path.join(tmp, "a.jsonl")) as f:
                records = [json.loads(line) for line in f]
        self.assertEqual((records[0]["type"], records[0]["version"], records[0]["cwd"]), ("session", 3, "{cwd}"))
        self.assertEqual(len(records) - 1, 4 * 12)
        self.assertEqual(a["messages"], 48)
        ids = {r["id"] for r in records[1:]}
        for r in records[1:]:
            self.assertTrue(r["parentId"] is None or r["parentId"] in ids)
        roles = [r["message"]["role"] for r in records[1:5]]
        self.assertEqual(roles, ["user", "assistant", "toolResult", "assistant"])

    def test_cache_reuses_and_regenerates_a_tampered_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, facts = sessions.cached(tmp, 5, 1)
            self.assertEqual(sessions.cached(tmp, 5, 1)[1], facts)
            with open(path, "a") as f:
                f.write("junk\n")
            self.assertEqual(sessions.cached(tmp, 5, 1)[1]["sha256"], facts["sha256"])

    def test_copy_replaces_only_the_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _ = sessions.cached(tmp, 3, 1)
            out = os.path.join(tmp, "o.jsonl")
            sessions.copy_with_cwd(path, out, "/project")
            with open(path) as fa, open(out) as fb:
                a, b = fa.read().split("\n", 1), fb.read().split("\n", 1)
        self.assertEqual(json.loads(b[0])["cwd"], "/project")
        self.assertEqual(a[1], b[1])


class VariedSession(unittest.TestCase):
    """The varied twin of the generated session: the same size and structure, other words in every turn."""

    def pair(self, tmp, turns=40, seed=1):
        base, base_facts = sessions.cached(tmp, turns, seed)
        varied, facts = sessions.cached(tmp, turns, seed, sessions.VARIED)
        return base, base_facts, varied, facts

    @staticmethod
    def records(path):
        with open(path) as f:
            return [json.loads(line) for line in f]

    @staticmethod
    def texts(records):
        return [b["text"] for r in records[1:] for b in r["message"]["content"] if b["type"] == "text"]

    def test_same_size_and_the_same_message_and_tool_call_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, base_facts, varied, facts = self.pair(tmp)
            a, b = self.records(base), self.records(varied)
            self.assertLessEqual(abs(facts["bytes"] - base_facts["bytes"]) / base_facts["bytes"], 0.01)
            self.assertEqual(os.path.getsize(varied), facts["bytes"])
        self.assertEqual((facts["messages"], facts["entries"], facts["context_tokens"]), (base_facts["messages"], base_facts["entries"], base_facts["context_tokens"]))
        self.assertEqual(len(a), len(b))
        for x, y in zip(a[1:], b[1:]):
            self.assertEqual((x["id"], x["parentId"], x["message"]["role"]), (y["id"], y["parentId"], y["message"]["role"]))
            self.assertEqual([(c["type"], c.get("id"), c.get("name"), c.get("arguments")) for c in x["message"]["content"] if c["type"] != "text"],
                             [(c["type"], c.get("id"), c.get("name"), c.get("arguments")) for c in y["message"]["content"] if c["type"] != "text"])
            self.assertEqual(x["message"].get("toolCallId"), y["message"].get("toolCallId"))
            self.assertEqual([len(t) for t in self.texts([x])], [len(t) for t in self.texts([y])])   # every text keeps its length, so the token estimates stay

    def test_no_two_turns_share_a_body_and_none_keeps_the_repeating_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, _bf, varied, _f = self.pair(tmp, turns=60)
            a, b = self.texts(self.records(base)), self.texts(self.records(varied))
        self.assertEqual(len(b), 3 * 60)   # a question, a tool result and an answer; the tool call has no text
        self.assertEqual(len(set(b)), len(b))
        self.assertFalse(set(a) & set(b))
        words = lambda texts: {w for t in texts for w in t.split()}
        self.assertLess(len(words(a)), 5000)
        self.assertGreater(len(words(b)), 5 * len(words(a)))   # the repeating session has a small vocabulary; the twin does not

    def test_the_twin_is_less_compressible_than_the_repeating_session(self):
        import zlib
        with tempfile.TemporaryDirectory() as tmp:
            base, _bf, varied, _f = self.pair(tmp)
            sizes = [len(zlib.compress(pathlib.Path(p).read_bytes())) for p in (base, varied)]
        self.assertGreater(sizes[1], 2 * sizes[0])

    def test_seeded_and_the_same_bytes_every_time(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2, tempfile.TemporaryDirectory() as t3:
            _b, _bf, v1, f1 = self.pair(t1, seed=7)
            _b, _bf, v2, f2 = self.pair(t2, seed=7)
            _b, _bf, v3, f3 = self.pair(t3, seed=8)
            self.assertEqual(pathlib.Path(v1).read_bytes(), pathlib.Path(v2).read_bytes())
        self.assertEqual(f1["sha256"], f2["sha256"])
        self.assertNotEqual(f1["sha256"], f3["sha256"])

    def test_facts_name_the_seed_and_the_digest_of_the_file(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            base, base_facts, varied, facts = self.pair(tmp, seed=3)
            digest = hashlib.sha256(pathlib.Path(varied).read_bytes()).hexdigest()
            self.assertEqual(sessions.cached(tmp, 40, 3, sessions.VARIED)[1], facts)   # a second call reuses the file and says the same
        self.assertEqual((facts["seed"], facts["sha256"], facts["variant"]), (3, digest, "varied"))
        self.assertEqual((base_facts["variant"], facts["source_sha256"]), ("repeating", base_facts["sha256"]))
        self.assertNotEqual(facts["sha256"], base_facts["sha256"])

    def test_a_facts_file_from_before_the_variants_reads_as_repeating(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, facts = sessions.cached(tmp, 4, 1)
            old = {k: v for k, v in facts.items() if k != "variant"}
            with open(path + ".json", "w") as f:
                json.dump(old, f)
            self.assertEqual(sessions.cached(tmp, 4, 1)[1]["variant"], "repeating")

    def test_only_the_cwd_differs_between_two_copies_for_two_harnesses(self):
        with tempfile.TemporaryDirectory() as tmp:
            _b, _bf, varied, _f = self.pair(tmp, turns=5)
            sessions.copy_with_cwd(varied, os.path.join(tmp, "x.jsonl"), "/a/project")
            sessions.copy_with_cwd(varied, os.path.join(tmp, "y.jsonl"), "/b/project")
            x, y = (open(os.path.join(tmp, n)).read().split("\n", 1) for n in ("x.jsonl", "y.jsonl"))
        self.assertEqual(x[1], y[1])

    def test_both_twins_are_registered_beside_their_originals(self):
        reg = workloads.load_all()
        for wid in ("longsession/resume-n-varied", "longsession/resume-n10-varied"):
            self.assertIn(wid, reg)
            self.assertEqual(reg[wid].family, "longsession")
        self.assertEqual(len([w for w in reg if w.startswith("longsession/resume-")]), 5)   # n, n10, their twins and 4m2


class Streaming(unittest.TestCase):
    def ctx(self, **params):
        return type("C", (), {"opts": type("O", (), {"params": params})()})()

    def test_event_delay_follows_the_requested_token_rate_and_zero_is_unpaced(self):
        step = streaming.answer_step("prose", 600, "n", self.ctx(stream_chunk=24), 1000)
        self.assertAlmostEqual(step.event_delay_ms, 6.0)  # 24 chars = 6 tokens at 1,000 tokens/s
        self.assertEqual(step.chunk_chars, 24)
        self.assertTrue(step.text.endswith("END-OF-ANSWER-N"))
        self.assertAlmostEqual(streaming.answer_step("prose", 600, "n", self.ctx(), 100).event_delay_ms, 60.0)
        self.assertEqual(streaming.answer_step("prose", 600, "n", self.ctx(), 0).event_delay_ms, 0)

    def test_the_tui_is_paced_and_print_mode_is_not_unless_asked(self):
        self.assertEqual((streaming.rate_of(self.ctx(), "tui"), streaming.rate_of(self.ctx(), "print")), (1000.0, 0.0))
        ctx = self.ctx(stream_rate_tps=500, print_stream_rate_tps=2000)
        self.assertEqual((streaming.rate_of(ctx, "tui"), streaming.rate_of(ctx, "print")), (500.0, 2000.0))

    def test_a_size_that_cuts_a_code_block_short_still_closes_the_fence_before_the_marker(self):
        for size in (400, 1500, 6000):
            text = streaming.answer_step("code", size, "n", self.ctx(), 1000).text
            self.assertEqual(text.count("```") % 2, 0, size)
            self.assertTrue(text.endswith("\n\nEND-OF-ANSWER-N"))

    def test_the_marker_is_found_through_colour_codes_only_when_asked_for_visible_text(self):
        from buffon.runner import procio

        class Term:
            cond = threading.Condition()
            chunks = [(1, b"\x1b[38;5;3mEND\x1b[0m"), (2, b"\x1b[2m-OF-ANSWER\x1b[0m-N")]
        self.assertEqual(procio.Pty.wait_text(Term, "END-OF-ANSWER-N", 0.2, visible=True), 2)
        self.assertIsNone(procio.Pty.wait_text(Term, "END-OF-ANSWER-N", 0.2))

    def test_the_answer_timeout_scales_with_the_streaming_time(self):
        ctx = self.ctx()
        ctx.opts.timeout = 120
        self.assertEqual(streaming.answer_timeout(ctx, 6000, 10), 20 * 1500 / 10)
        self.assertEqual(streaming.answer_timeout(ctx, 6000, 10000), 120)
        self.assertEqual(streaming.answer_timeout(ctx, 6000, 0), 120, "unpaced: the per-process timeout")

    def test_sizes_are_n_and_ten_n(self):
        self.assertEqual(streaming.sizes(self.ctx()), (("n", 6000), ("n10", 60000)))
        self.assertEqual(streaming.sizes(self.ctx(stream_n=500)), (("n", 500), ("n10", 5000)))

    def test_the_needle_is_the_first_visible_heading_of_each_shape(self):
        self.assertEqual(streaming.needle("prose", 100), "Section 1")
        self.assertEqual(streaming.needle("code", 100), "Function 1")
        self.assertEqual(streaming.needle("tables", 100), "Table 1")
        self.assertEqual(streaming.needle("lists", 100), "List 1")

    def test_every_shape_registers_a_tui_and_a_print_workload(self):
        reg = workloads.load_all()
        for shape in ("prose", "code", "tables", "lists"):
            self.assertIn(f"streaming/tui-{shape}", reg)
            self.assertIn(f"streaming/print-{shape}", reg)


class Registry(unittest.TestCase):
    def test_the_v0_workloads_are_registered(self):
        reg = workloads.load_all()
        for wid in ("overhead/print", "overhead/rpc", "overhead/pty", "longsession/resume-n", "longsession/resume-n10", "longsession/grow-n", "longsession/grow-n10",
                    "soak/realistic", "soak/stress", "reliability/faults"):
            self.assertIn(wid, reg)
        self.assertTrue(reg["soak/stress"].special and reg["reliability/faults"].special)
        self.assertFalse(reg["overhead/print"].special)

    def test_resolve_by_id_family_and_all(self):
        self.assertEqual([w.id for w in workloads.resolve(["overhead/print"])], ["overhead/print"])
        self.assertGreater(len(workloads.resolve(["streaming"])), 7)
        self.assertEqual(len(workloads.resolve(["all"])), len(workloads.REGISTRY))
        self.assertEqual(len(workloads.resolve(["overhead/print", "overhead"])), len(workloads.resolve(["overhead"])))
        with self.assertRaisesRegex(KeyError, "unknown workload"):
            workloads.resolve(["nope"])

    def test_the_session_length_parameter_scales_the_ten_n_workloads(self):
        ctx = type("C", (), {"opts": type("O", (), {"params": {"session_n": 30}})()})()
        self.assertEqual((longsession.turns_for(ctx, "n"), longsession.turns_for(ctx, "n10")), (30, 300))

    def test_the_ten_extensions_resolve(self):
        ctx = type("C", (), {"work": os.path.join(tempfile.mkdtemp(), "work")})()
        self.assertEqual(len(overhead.sweep_extensions(ctx, manifest.load_arm("pi-node"), 10)), 10)


class MockRetain(unittest.TestCase):
    def test_retain_keeps_the_last_requests_and_counts_all(self):
        with mock.MockServer(retain=2) as srv:
            for _ in range(3):
                conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
                conn.request("POST", "/v1/chat/completions", json.dumps({"messages": [{"role": "user", "content": "x"}]}))
                conn.getresponse().read()
                conn.close()
        self.assertEqual(srv.total, 3)
        self.assertEqual([r.index for r in srv.requests], [1, 2])


if __name__ == "__main__":
    unittest.main()


class CompactionCount(unittest.TestCase):
    def req(self, tools=(), body=None, fault=None):
        r = mock.Request(0, "openai-completions", body or {"messages": []}, 1, 0)
        r.tools, r.fault = list(tools), fault
        return r

    def test_summarisation_requests_are_counted_whatever_events_the_arm_emits(self):
        """rpi 0.3.19 compacts (tool-less requests carrying <conversation>) but never emits compaction_end, which made grow-n/grow-n10 fail as 'no compaction happened'."""
        server = type("S", (), {})()
        summary = {"messages": [{"role": "system", "content": "You are a context summarization assistant."}, {"role": "user", "content": [{"type": "text", "text": "<conversation>\n[User]: hi"}]}]}
        server.requests = [self.req(["read"]), self.req(body=summary), self.req(body=summary), self.req(["read"], body=summary), self.req(body=summary, fault="429"), self.req(body={"messages": []})]
        self.assertEqual(overhead.count_compaction_requests(server), 2)
        server.requests = [self.req(["read"]), self.req()]
        self.assertEqual(overhead.count_compaction_requests(server), 0)
