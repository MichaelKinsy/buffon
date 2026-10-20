# SPDX-License-Identifier: Apache-2.0
"""The runner's side of the durable family against a fake adapter (tests/fake_durable_adapter.py): the protocol client, the turn loop and its fields, the equivalence gate (it passes on equal
state and fails on a planted difference, cross-open and the schema rule), fixtures, and the crash matrix driver."""
import json
import os
import stat
import sys
import tempfile
import unittest
from types import SimpleNamespace

from buffon.durable import crash, driver, fixtures, gate, kio, prepare, specs
from buffon.durable.host import DurableHost
from buffon.durable.protocol import Adapter, Died, Unsupported
from buffon.runner import cgroup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE = os.path.join(ROOT, "tests", "fake_durable_adapter.py")


class FakeArm:
    """What the durable code reads of an installed arm."""

    def __init__(self, base, name, env=None, writes=1, reads=(1,), twin_of=None):
        self.id, self.version, self.record, self.twin_of = name, "0.0", {}, twin_of
        self.binary = os.path.join(base, f"{name}.sh")
        with open(self.binary, "w") as f:
            f.write(f"#!/bin/sh\nexec {sys.executable} {FAKE} \"$@\"\n")
        os.chmod(self.binary, os.stat(self.binary).st_mode | stat.S_IXUSR)
        self.adapter = {"protocol": 1, "envs": ["native"], "storage": "sqlite", "source": "adapter", "schema_writes": writes, "schema_reads": list(reads)}
        self.path_dirs, self.vars, self.install_dir, self.divergences = [], {}, None, []
        self.env = dict(env or {}, FAKE_ARM=name)
        self.apis = []


class World(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        self.work = os.path.join(self.base, "work")
        os.makedirs(self.work)
        self.opts = SimpleNamespace(cache_dir=os.path.join(self.base, "cache"), timeout=60, env="native", out=os.path.join(self.base, "out"), reference="ref", workloads=[], quiet_timeout_s=1)

    def ctx(self):
        return SimpleNamespace(work=self.work, opts=self.opts, _harnesses={}, server=SimpleNamespace(context=None))

    def runner(self):
        log = []
        r = SimpleNamespace(plan=self.opts, log=log.append, skipped=[], samples=[], checkpoint=lambda: None, quiet_wait=lambda: ({}, True), logged=log)
        return r

    def arm(self, name, **kw):
        return FakeArm(self.base, name, **kw)

    def prepared(self, arms, twin=None, workloads=("durable/compat-50",)):
        self.opts.workloads = [SimpleNamespace(id=w, envs=("native",)) for w in workloads]
        ctx, runner = self.ctx(), self.runner()
        instances = list(arms) + ([twin] if twin else [])
        out, refusal = prepare.run(runner, ctx, arms, instances)
        return ctx, runner, out, refusal


class Protocol(World):
    def start(self, **env):
        arm = self.arm("ref", env=env)
        host = DurableHost(arm, self.work, "p")
        meter = cgroup.new_meter()
        self.addCleanup(meter.close)
        ad = Adapter(host.argv(), host.env, host.cwd, meter, timeout=30)
        self.addCleanup(ad.close)
        ad.wait_ready()
        return ad, host

    def test_ready_event_carries_the_protocol_and_the_start_time(self):
        ad, _ = self.start()
        self.assertEqual(ad.ready["protocol"], 1)
        self.assertGreater(ad.proc_start_ms, 0)
        self.assertTrue(ad.clock_ok)

    def test_a_turn_is_timed_by_the_runners_clock_and_the_adapters_stamp_is_converted(self):
        ad, host = self.start()
        ad.call("open", store=host.store, script="x", ledger=host.ledger, mode="runtime", conversations=1, create=True, window_tokens=1000, compaction={"enabled": True}, request_log=None)
        ex = ad.call("turn", conv=0, n=0, request_id="t0", stream=False)
        self.assertEqual(ex["status"], "done")
        self.assertGreater(ex.ms, 0)
        self.assertGreaterEqual(ad.to_runner_clock(ex["first_request_mono_ns"]), ex.t_send)

    def test_unsupported_is_its_own_error_with_the_adapters_sentence(self):
        ad, host = self.start(FAKE_NODOCS="1")
        ad.call("open", store=host.store, script="x", ledger=host.ledger, mode="runtime", conversations=1, create=True, window_tokens=1000, compaction={"enabled": True}, request_log=None)
        with self.assertRaises(Unsupported) as why:
            ad.call("doc_edit", conv=0, count=1, payload_bytes=88)
        self.assertIn("no documents", str(why.exception))

    def test_an_adapter_that_dies_mid_request_is_reported_with_its_events(self):
        ad, host = self.start()
        ad.call("open", store=host.store, script="x", ledger=host.ledger, mode="runtime", conversations=1, create=True, window_tokens=1000, compaction={"enabled": True}, request_log=None)
        ad.call("crash_after", k=2)
        with self.assertRaises(Died) as died:
            ad.call("turn", conv=0, n=0, request_id="t0", stream=False)
        self.assertEqual(died.exception.events[-1]["event"], "crashing")
        self.assertEqual(died.exception.events[-1]["commit"], 2)
        self.assertEqual(died.exception.code, -9)


class Turns(World):
    def test_fields_of_a_run_of_turns_follow_the_definitions(self):
        arm = self.arm("ref")
        host = DurableHost(arm, self.work, "t")
        proc = driver.Process(host, arm, 30)
        self.addCleanup(proc.release)
        proc.wait_ready()
        opened, rows, cold = driver.open_and_turns(proc, {"store": host.store, "script": "x", "ledger": host.ledger, "mode": "runtime", "conversations": 1, "create": True, "window_tokens": 1000,
                                                          "compaction": {"enabled": True}, "request_log": None}, [(0, n) for n in range(4)])
        self.assertEqual(len(rows), 4)
        f = driver.turn_fields(rows, opened.ms, cold)
        self.assertAlmostEqual(f["cold_ms"], opened.ms + rows[0]["turn_ms"])
        self.assertEqual(f["warm_turn_ms"], sorted(r["turn_ms"] for r in rows[1:])[1])   # the median of three
        self.assertEqual(f["sql_stmts_per_turn"], 7)
        self.assertEqual(f["sql_commits_per_turn"], 4)
        self.assertEqual(f["sql_read_stmts_per_turn"], 3)
        self.assertEqual(f["sql_write_stmts_per_turn"], 3)
        self.assertEqual(f["sql_pragma_stmts_per_turn"], 1)
        self.assertEqual(len(f["series"]["turn_ms"]), 4)
        proc.adapter.call("close")
        proc.close()
        pf = driver.process_fields(proc)
        self.assertIn("cpu_ms", pf)
        self.assertGreater(pf["proc_start_ms"], 0)

    def test_a_field_the_host_cannot_produce_is_absent_not_zero(self):
        rows = [{"n": i, "turn_ms": 1.0, "adapter_ms": 1.0, "ttfr_ms": None, "first_delta_ms": None, "model_ms": None, "cpu_ms": 1.0, "stmts": 1, "kinds": {"read": 1, "write": 0, "ddl": 0, "pragma": 0, "other": 0},
                 "commits": 1, "rows_returned": 1, "bytes_returned": 1, "instructions": None, "cycles": None, "wchar": None, "rchar": None} for i in range(3)]
        f = driver.turn_fields(rows)
        for k in ("ttfr_ms", "first_delta_ms", "warm_instructions", "wchar_bytes_per_turn", "rchar_bytes_per_turn"):
            self.assertNotIn(k, f)

    def test_kernel_counters_are_empty_where_the_host_has_no_proc(self):
        self.assertEqual(kio.delta({}, {"rchar": 1}), {})
        self.assertEqual(kio.delta({"rchar": 5, "wchar": 7}, {"rchar": 2, "wchar": 1}), {"rchar": 3, "wchar": 6})


class Fixtures(World):
    def test_a_fixture_is_built_once_cached_by_what_it_is_built_from_and_copied_per_sample(self):
        writer = self.arm("ref")
        fx = specs.Fixture("compat", 6, "repeating", 1000, False)
        a = fixtures.ensure(self.ctx(), fx, writer, log=lambda *_: None)
        self.assertFalse(a.facts["cached"])
        b = fixtures.ensure(self.ctx(), fx, writer, log=lambda *_: None)
        self.assertTrue(b.facts["cached"])
        self.assertEqual(a.path, b.path)
        self.assertEqual(a.sample_fields["fixture_writer"], "ref")
        other = fixtures.ensure(self.ctx(), specs.Fixture("compat", 7, "repeating", 1000, False), writer, log=lambda *_: None)
        self.assertNotEqual(other.path, a.path)
        host = DurableHost(writer, self.work, "s")
        self.assertGreater(fixtures.stage(a, host), 0)
        self.assertEqual(os.path.getsize(host.store), a.facts["store_bytes"])


class Gate(World):
    def run_gate(self, other, twin=True):
        ref = self.arm("ref")
        twin_arm = self.arm("ref-b", twin_of="ref") if twin else None
        return self.prepared([ref, other], twin_arm)

    def test_the_gate_passes_when_the_arms_leave_the_same_state(self):
        ctx, runner, out, refusal = self.run_gate(self.arm("other"))
        self.assertIsNone(refusal, out["gate"]["failures"])
        self.assertTrue(out["gate"]["passed"])
        self.assertTrue(os.path.exists(os.path.join(self.opts.out, "equivalence.json")))
        cross = list(out["gate"]["cross_open"].values())[0]
        self.assertTrue(cross["ref>other"]["ok"] and cross["other>ref"]["ok"])

    def test_the_gate_refuses_a_planted_difference_and_names_it(self):
        ctx, runner, out, refusal = self.run_gate(self.arm("other", env={"FAKE_DIVERGE": "1"}))
        self.assertIsNotNone(refusal)
        self.assertIn("other differs from the oracle", refusal)
        self.assertIn("equivalence.json", refusal)
        with open(os.path.join(self.opts.out, "equivalence.json")) as f:
            doc = json.load(f)
        self.assertFalse(doc["passed"])
        self.assertTrue(doc["differences"])

    def test_a_reference_that_disagrees_with_its_own_copy_is_flaky_and_its_fixture_is_excluded(self):
        ref = self.arm("ref")
        twin = self.arm("ref-b", twin_of="ref", env={"FAKE_DIVERGE": "1"})
        ctx, runner, out, refusal = self.prepared([ref, self.arm("other")], twin)
        state = ctx.durable
        self.assertTrue(out["gate"]["flaky"])
        spec = specs.SPECS["durable/compat-50"]
        self.assertIn("excluded", state.skip_reason(ref, spec))

    def test_a_store_the_readers_runtime_cannot_open_is_not_possible_and_not_a_failure(self):
        new = self.arm("new", env={"FAKE_SCHEMA": "2", "FAKE_READS": "1,2"}, writes=2, reads=(1, 2))
        ctx, runner, out, refusal = self.run_gate(new)
        self.assertIsNone(refusal, out["gate"]["failures"])
        cross = list(out["gate"]["cross_open"].values())[0]
        self.assertFalse(cross["new>ref"]["possible"])
        self.assertIn("schema version", cross["new>ref"]["why"])
        self.assertTrue(cross["ref>new"]["ok"])

    def test_a_capability_an_arm_lacks_is_its_own_sentence_and_the_workload_skips_with_it(self):
        ctx, runner, out, refusal = self.run_gate(self.arm("other", env={"FAKE_NODOCS": "1"}))
        self.assertIsNone(refusal)
        why = ctx.durable.skip_reason(ctx.durable.arms[1], specs.SPECS["durable/docs-100"])
        self.assertIn("no documents", why)

    def test_results_of_parallel_tool_calls_are_the_same_work_in_any_order(self):
        def item(i, ref, task):
            return {"kind": "pi.tool-result", "digest": f"d{i}", "by_task": f"t0.{task}", "ref": ref}
        a = {"schema_version": 1, "conversations": [{"active": [{"kind": "pi.assistant", "digest": "a", "ref": "e0.0"}, item(1, "e0.1", 5), item(2, "e0.2", 6)], "tasks": [{"entryId": "e0.1"}, {"entryId": "e0.2"}], "submissions": [], "head_markers": []}],
             "documents": [], "compaction_ids": []}
        b = {"schema_version": 2, "conversations": [{"active": [{"kind": "pi.assistant", "digest": "a", "ref": "e0.0"}, item(2, "e0.1", 6), item(1, "e0.2", 5)], "tasks": [{"entryId": "e0.2"}, {"entryId": "e0.1"}], "submissions": [], "head_markers": []}],
             "documents": [], "compaction_ids": []}
        self.assertEqual(gate.comparable_state(a)["conversations"][0]["active"], gate.comparable_state(b)["conversations"][0]["active"])
        self.assertEqual(gate.comparable_state(a)["conversations"][0]["tasks"], gate.comparable_state(b)["conversations"][0]["tasks"])
        c = json.loads(json.dumps(b))
        c["conversations"][0]["active"][1]["digest"] = "different"
        self.assertNotEqual(gate.comparable_state(a)["conversations"][0]["active"], gate.comparable_state(c)["conversations"][0]["active"])


class Crash(World):
    def run_matrix(self, arms, twin=None, points=3):
        spec = specs.SPECS["durable/crash-50"]
        small = specs.Spec(id="durable/crash-50", description="", flavor="crash", fixture=specs.Fixture("compat", 5, "repeating", 1000, False), shape="crash", rounds=1, aa=False)
        specs.SPECS["durable/crash-test"] = small
        self.addCleanup(specs.SPECS.pop, "durable/crash-test", None)
        ctx, runner, out, refusal = self.prepared(arms, twin, workloads=("durable/crash-test",))
        self.assertIsNone(refusal)
        ctx.opts.crash_points = points
        ctx.opts.params = {"crash_points": points}
        crash.run(runner, ctx, arms, small)
        return runner

    def test_every_order_and_kill_point_is_a_sample_and_a_resumable_runtime_passes_them_all(self):
        ref, other = self.arm("ref"), self.arm("other")
        runner = self.run_matrix([ref, other])
        self.assertEqual(len(runner.samples), 4 * 3)
        self.assertTrue(all(s.get("resume_ok") for s in runner.samples), [s.get("invariant_failures") or s.get("failure") for s in runner.samples if not s.get("resume_ok")])
        self.assertEqual({s["order"] for s in runner.samples}, {"ref>ref", "ref>other", "other>ref", "other>other"})
        self.assertTrue(all(s["kill_event_commit"] == s["k"] for s in runner.samples))

    def test_a_duplicated_answer_after_resume_fails_its_sample_and_only_its_sample(self):
        ref, bad = self.arm("ref"), self.arm("bad", env={"FAKE_DUP": "1"})
        runner = self.run_matrix([ref, bad])
        failed = [s for s in runner.samples if not s.get("resume_ok")]
        self.assertTrue(failed)
        self.assertTrue(all(s["arm"] == "bad" for s in failed))
        self.assertIn("duplicated model answer", failed[0]["invariant_failures"])

    def test_an_order_the_storage_schemas_forbid_is_listed_with_its_reason_not_run(self):
        ref = self.arm("ref")
        new = self.arm("new", env={"FAKE_SCHEMA": "2", "FAKE_READS": "1,2"}, writes=2, reads=(1, 2))
        runner = self.run_matrix([ref, new])
        self.assertEqual({s["order"] for s in runner.samples}, {"ref>ref", "ref>new", "new>new"})
        skipped = [s for s in runner.skipped if s.get("order")]
        self.assertEqual([s["order"] for s in skipped], ["new>ref"])
        self.assertIn("not possible", skipped[0]["reason"])

    def test_kill_points_are_every_commit_or_evenly_spaced_including_the_first_and_last(self):
        self.assertEqual(crash.points(5, "all"), [1, 2, 3, 4, 5])
        self.assertEqual(crash.points(28, 4), [1, 10, 19, 28])
        self.assertEqual(crash.points(3, 20), [1, 2, 3])


class RawAndPlan(unittest.TestCase):
    def test_a_durable_sample_may_carry_its_settings_versions_and_table_counts_as_nested_json(self):
        from buffon.runner import raw
        s = {"arm": "a", "scenario": "durable/mixed-3500", "round": 0, "warmup": False, "api": None, "env": "native", "cold_ms": 1.0, "runtime_settings": {"compaction": {"enabled": True}},
             "runtime_versions": {"node": "v24"}, "store_tables": {"entries": 3}, "compaction_ids": [4, 9], "series": {"turn_ms": [1.0]}}
        raw.check_sample(s)
        with self.assertRaises(raw.RawError):
            raw.check_sample(dict(s, other_nested={"x": 1}))

    def test_the_durable_campaign_has_a_minimal_family_that_may_be_short_and_a_full_session(self):
        from buffon import campaign
        plan, _ = campaign.load_plan(os.path.join(ROOT, "campaigns", "durable-native.toml"))
        names = [f["name"] for f in plan["family"]]
        self.assertEqual(names[0], "minimal")
        self.assertEqual(set(plan["family"][0]["workloads"]), set(specs.MINIMAL))
        self.assertEqual(plan["campaign"]["reference"], "pi-durable")
        argv = campaign.family_argv("run", plan["family"][0], None, "out", "pi-durable", None)
        self.assertIn("--allow-short", argv)
        short = dict(plan, family=[dict(plan["family"][1], rounds=6)])
        with self.assertRaises(campaign.PlanError):
            campaign.check_plan(short)

    def test_a_durable_run_selects_the_adapter_arms_and_the_pi_durable_reference_by_itself(self):
        from buffon import cli
        parser = cli.build_parser()
        args = parser.parse_args(["session", "durable/compat-50", "--out", "x"])
        plan = cli.session_plan(args)
        self.assertEqual([a.id for a in plan.arms], ["pi-durable", "pig-durable"])
        self.assertEqual(plan.reference, "pi-durable")
        self.assertEqual(plan.envs, ["native"])
        from buffon.runner import engine
        plan.envs = ["miniflare"]
        with self.assertRaises(engine.Refused):
            plan.validate()

    def test_the_variant_axis_of_a_durable_workload_is_its_environment_not_a_wire_api(self):
        from buffon import workloads
        from buffon.runner import engine
        w = workloads.REGISTRY["durable/mixed-3500"]
        self.assertEqual(engine.variants([w], ["openai-completions", "anthropic-messages"], ["native"]), [(w, None)])
        self.assertEqual(engine.variants([w], ["openai-completions"], ["native", "miniflare"]), [(w, None)])   # the workload runs in native only until its envs name more
        o = workloads.REGISTRY["overhead/print"]
        self.assertEqual([a for _, a in engine.variants([o], ["openai-completions"], ["native"])], ["openai-completions"])


if __name__ == "__main__":
    unittest.main()
