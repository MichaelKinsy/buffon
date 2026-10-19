# SPDX-License-Identifier: Apache-2.0
"""The extension matrix: derived arms, the extension set each realization loads, the process census that proves a realization, and the warm PIG_HOME."""
import os
import re
import subprocess
import sys
import tempfile
import time
import types
import unittest

from buffon.arms import manifest
from buffon.runner import procs
from buffon.runner.harness import Harness
from buffon.workloads import overhead

MATRIX = ("pig-ts-node", "pig-ts-bun", "pig-ts-aot", "pig-ts-node-isolated-diag", "pig-go-packed", "pig-go-isolated", "pig-go-fused")


class DerivedArms(unittest.TestCase):
    def test_a_derived_arm_inherits_the_base_tables_key_by_key_and_runs_only_when_named(self):
        base = manifest.load_arm("pig-tip")
        for name in MATRIX:
            arm = manifest.load_arm(name)
            self.assertEqual(arm.install_kind, "derive", name)
            self.assertEqual(arm.base, "pig-tip", name)
            self.assertEqual(arm.modes, base.modes, name)
            self.assertEqual(arm.apis, base.apis, name)
            self.assertFalse(arm.runs_by_default, name)
            self.assertEqual(os.path.basename(arm.writer_path()), "writer.py", name)
            self.assertTrue(os.path.exists(arm.writer_path()), name)
        bun = manifest.load_arm("pig-ts-bun")
        self.assertEqual(bun.env["PIG_TS_RUNTIME"], "bun")
        self.assertEqual(bun.env["PIG_OFFLINE"], base.env["PIG_OFFLINE"])   # inherited next to the arm's own keys
        self.assertEqual(manifest.load_arm("pig-go-packed").spec["runtime"], {"node": "24.19.0", "go": "1.27.2"})

    def test_every_realization_loads_ten_extensions_and_the_ten_are_the_same_in_every_go_set(self):
        for name in MATRIX:
            arm = manifest.load_arm(name)
            paths = arm.extension_paths()
            if manifest.load_arm(name).loads_template():
                paths = overhead.sweep_extensions(types.SimpleNamespace(work=os.path.join(tempfile.mkdtemp(), "work")), arm, 10)
            self.assertEqual(len(paths), 0 if name == "pig-go-fused" else 10, name)
            self.assertEqual(len(set(paths)), len(paths), name)
            if name == "pig-go-fused":
                self.assertTrue(arm.extension_spec["embedded"])
        root = os.path.join(manifest.ROOT, "fixtures", "extensions-go")
        body = {}
        for kind, rel in (("factory", "extension.go"), ("standalone", "main.go")):
            for i in range(1, 11):
                text = open(os.path.join(root, kind, f"bench-ext-{i:02d}", rel)).read()
                body.setdefault(kind, set()).add(re.sub(rf"(?<=bench-ext-){i:02d}|(?<=ackage benchext){i:02d}|(?<=New\(\"){i:02d}", "NN", text))
        self.assertEqual({k: len(v) for k, v in body.items()}, {"factory": 1, "standalone": 1}, "the ten copies of a Go set differ in more than their number")
        piglet = open(os.path.join(root, "pig-ext10.yaml")).read()
        for i in range(1, 11):
            self.assertIn(f"local:factory/bench-ext-{i:02d}", piglet)

    def test_an_arm_without_an_extensions_table_takes_the_generated_ten(self):
        arm = manifest.load_arm("pi-node")
        ctx = types.SimpleNamespace(work=os.path.join(tempfile.mkdtemp(), "work"))
        self.assertEqual(len(overhead.sweep_extensions(ctx, arm, 10)), 10)
        self.assertTrue(arm.loads_template())
        self.assertEqual(arm.extension_paths(), [])


class Census(unittest.TestCase):
    def tree(self, n):
        """A shell with `n` sleeping children, in its own process group so the cleanup takes the children with it. Waits until all `n` exist (a loaded host may take long)."""
        import signal
        p = subprocess.Popen(["bash", "-c", f"{'sleep 30 & ' * n} wait"], start_new_session=True)
        self.addCleanup(lambda: (os.killpg(p.pid, signal.SIGKILL), p.wait()))
        deadline, children = time.monotonic() + 30, []
        while len(children) < n and time.monotonic() < deadline:
            children = [int(x) for x in subprocess.run(["pgrep", "-P", str(p.pid)], capture_output=True, text=True).stdout.split()]
        self.assertEqual(len(children), n, "the shell did not start its children")
        return p.pid, children

    def test_descendants_are_extension_processes_and_a_meter_holder_is_nobody_s(self):
        host, kids = self.tree(3)
        holder = subprocess.Popen(["sleep", "30"])   # in the meter's cgroup, not a descendant of the harness
        self.addCleanup(holder.kill)
        rows = procs.census(host, [host, *kids, holder.pid])
        self.assertEqual([r["role"] for r in rows].count("extension"), 3)
        self.assertEqual([r["role"] for r in rows].count("host"), 1)
        self.assertNotIn(holder.pid, [r["pid"] for r in rows])

    def test_check_names_the_realization_that_ran_instead_of_the_one_declared(self):
        host, kids = self.tree(3)
        rows = procs.census(host, [host, *kids])
        self.assertIsNone(procs.check(rows, {"processes": 3, "host": "sleep"}))
        self.assertIn("3 extension process(es)", procs.check(rows, {"processes": 1}))
        self.assertIn("does not run on bun", procs.check(rows, {"processes": 3, "host": "bun"}))
        self.assertIsNone(procs.check([r for r in rows if r["role"] == "host"], {"processes": 0}))   # fused: no extension process
        self.assertIn("0 extension", procs.check([r for r in rows if r["role"] == "host"], {"processes": 1}))

    def test_one_process_per_extension_scales_with_the_count_and_a_packed_set_does_not(self):
        self.assertEqual(procs.expected_processes({"processes": 10}, 5), 5)   # ten processes for ten extensions: five for five
        self.assertEqual(procs.expected_processes({"processes": 10}, 10), 10)
        self.assertEqual(procs.expected_processes({"processes": 1}, 5), 1)   # one packed process whatever the count
        self.assertEqual(procs.expected_processes({"processes": 0}, 5), 0)   # fused: none
        self.assertEqual(procs.expected_processes({"processes": 10}), 10)


class WarmHome(unittest.TestCase):
    def test_a_sample_starts_from_the_prepared_cache_at_one_fixed_pig_home(self):
        with tempfile.TemporaryDirectory() as root:
            arm = manifest.load_arm("pig-go-packed")
            arm.install_dir = os.path.join(root, "install")
            os.makedirs(os.path.join(arm.install_dir, "warm", "cache", "cells"))
            open(os.path.join(arm.install_dir, "warm", "cache", "cells", "marker"), "w").write("built")
            arm.vars = {"shared_dir": os.path.join(root, "shared"), "source_dir": os.path.join(root, "src")}
            arm.binary = sys.executable

            class Server:
                base_url, origin = "http://127.0.0.1:1/v1", "http://127.0.0.1:1"
            homes = []
            for n in range(2):
                h = Harness(arm, os.path.join(root, f"work{n}"), Server, extensions=())
                homes.append(h.pig_home)
                self.assertEqual(open(os.path.join(h.pig_home, "cache", "cells", "marker")).read(), "built")
                open(os.path.join(h.pig_home, "cache", "dirty"), "w").write("a sample's own writes")
                h.cleanup()
            self.assertEqual(homes[0], homes[1])                       # the cell's cache key includes this path, so it must not change between samples
            self.assertFalse(os.path.exists(homes[0]))                 # and nothing of one sample is left for the next
            self.assertEqual(h.env["PIG_SDK_GO_ROOT"], os.path.join(root, "src", "extensions", "sdk"))


class Equivalence(unittest.TestCase):
    """The gate that refuses a run when arms that load the same bench extensions do different work."""

    def record(self, events=3, text="bench 01 ok", processes=1):
        return {"commands": [["bench-01", "Bench command 01"]], "declared": {"bench_tool_01": {"description": "d", "parameters": {"type": "object"}}},
                "results": [{"toolName": "bench_tool_01", "isError": False, "result": {"content": [{"type": "text", "text": text}], "details": {"events": events}}}],
                "carried": [text], "census": {"extension_processes": processes, "executables": ["x"]}}

    def run_gate(self, records, counts=(10,), cannot=(), seen=None):
        """Run the gate over arms named by `records` (the record every arm returns). `cannot`: (arm, count) pairs the arm's realization cannot take."""
        from types import SimpleNamespace
        from buffon.runner import equivalence

        arms = [SimpleNamespace(id=i, pi_extensions="sidecar", family="pi-reference" if i == "ref" else "pi-port", extension_spec={"embedded": True}, loads_template=lambda: False, apis=["openai-completions"]) for i in records]
        ctx = SimpleNamespace(opts=SimpleNamespace(api=None, timeout=1))
        runner = SimpleNamespace(log=lambda *_: None)

        def extensions_of(arm, count):
            if (arm.id, count) in cannot:
                raise overhead.Skip("it cannot")
            return []

        def record_of(_ctx, arm, paths, _t, count=10):
            if seen is not None:
                seen.append((arm.id, count))
            return records[arm.id]
        original = equivalence.record_of
        equivalence.record_of = record_of
        self.addCleanup(setattr, equivalence, "record_of", original)
        with tempfile.TemporaryDirectory() as out:
            doc = equivalence.run(runner, ctx, arms, extensions_of, out, counts)
            self.assertTrue(os.path.exists(os.path.join(out, "equivalence.json")))
        return doc

    def test_arms_with_equal_output_pass_whatever_their_process_census(self):
        doc = self.run_gate({"ref": self.record(processes=0), "a": self.record(processes=10), "b": self.record(processes=1)})
        self.assertTrue(doc["passed"], doc)
        self.assertEqual(len({a["digest"] for a in doc["counts"]["10"]["arms"].values()}), 1)

    def test_a_different_tool_result_or_event_count_names_the_arm_and_the_field(self):
        doc = self.run_gate({"ref": self.record(), "a": self.record(events=4), "b": self.record(text="bench 01 OK")})
        diffs = doc["counts"]["10"]["differences"]
        self.assertFalse(doc["passed"])
        self.assertIn(".results[0].result.details.events: 3 != 4", diffs["a"][0])
        self.assertTrue(any("bench 01" in d for d in diffs["b"]))
        self.assertNotIn("ref", diffs)

    def test_an_arm_that_could_not_be_recorded_refuses_the_run(self):
        doc = self.run_gate({"ref": self.record(), "a": {"failure": "no get_state response"}})
        self.assertFalse(doc["passed"])
        self.assertIn("could not record", doc["counts"]["10"]["differences"]["a"][0])

    def test_the_policy_calls_the_ten_tools_in_order_then_answers(self):
        from buffon.runner import equivalence
        from buffon.mock import Request
        tools = equivalence.tools_of(10)
        body = lambda rounds, names: {"messages": [{"role": "user", "content": "x"}] + [{"role": "tool", "content": "r"}] * rounds, "tools": [{"function": {"name": t, "parameters": {}}} for t in names]}   # noqa: E731
        policy = equivalence.policy_of(10)
        calls = [policy(Request(0, "openai-completions", body(k, tools), 1, 0)).tool_calls for k in range(11)]
        self.assertEqual([c[0][0] for c in calls[:10]], tools)
        self.assertEqual(calls[10], [])

    def test_the_ext5_gate_checks_five_tools(self):
        from buffon.runner import equivalence
        from buffon.mock import Request
        five = equivalence.tools_of(5)
        self.assertEqual(five, [f"bench_tool_{i:02d}" for i in range(1, 6)])
        self.assertEqual(equivalence.tools_of(5), equivalence.tools_of(10)[:5])
        body = lambda rounds: {"messages": [{"role": "user", "content": "x"}] + [{"role": "tool", "content": "r"}] * rounds, "tools": [{"function": {"name": t, "parameters": {}}} for t in equivalence.tools_of(10)]}   # noqa: E731
        policy = equivalence.policy_of(5)
        calls = [policy(Request(0, "openai-completions", body(k), 1, 0)).tool_calls for k in range(7)]
        self.assertEqual([c[0][0] for c in calls[:5]], five)
        self.assertEqual(calls[5:], [[], []])   # the sixth request is the answer even though the host declares ten tools
        request = Request(0, "openai-completions", body(0), 1, 0)
        request.schemas = {t: {"type": "object"} for t in equivalence.tools_of(10)}
        self.assertEqual(sorted(equivalence.declared_tools(request, 5)), five)

    def test_the_gate_runs_once_per_count_the_plan_loads(self):
        from types import SimpleNamespace
        from buffon.runner import equivalence
        plan = lambda *ids: SimpleNamespace(workloads=[SimpleNamespace(id=i) for i in ids])   # noqa: E731
        self.assertEqual(equivalence.counts(plan("overhead/print-ext5", "overhead/rpc-ext5")), [5])
        self.assertEqual(equivalence.counts(plan("overhead/rpc-ext10", "overhead/print-ext5", "overhead/print")), [5, 10])
        self.assertEqual(equivalence.counts(plan("overhead/print-ext50", "overhead/print")), [])
        seen = []
        doc = self.run_gate({"ref": self.record(), "a": self.record()}, counts=(5, 10), seen=seen)
        self.assertEqual(sorted(seen), [("a", 5), ("a", 10), ("ref", 5), ("ref", 10)])
        self.assertEqual(sorted(doc["counts"]), ["10", "5"])
        self.assertEqual(doc["counts"]["5"]["arms"]["a"]["extensions"], {"count": 5, "template_sha256": None})   # an arm with its own realization has no template

    def test_an_arm_that_cannot_take_five_is_left_out_of_the_ext5_gate_only(self):
        seen = []
        doc = self.run_gate({"ref": self.record(), "fused": self.record()}, counts=(5, 10), cannot={("fused", 5)}, seen=seen)
        self.assertEqual(sorted(seen), [("fused", 10), ("ref", 5), ("ref", 10)])
        self.assertEqual(sorted(doc["counts"]["5"]["arms"]), ["ref"])
        self.assertEqual(sorted(doc["counts"]["10"]["arms"]), ["fused", "ref"])

    def test_a_template_arm_records_the_templates_sha256(self):
        from types import SimpleNamespace
        from buffon.fixtures import benchext
        from buffon.runner import equivalence
        arm = SimpleNamespace(id="ref", pi_extensions="native", family="pi-reference", extension_spec={}, loads_template=lambda: True, apis=["openai-completions"])
        original = equivalence.record_of
        equivalence.record_of = lambda *_a, **_k: self.record()
        self.addCleanup(setattr, equivalence, "record_of", original)
        with tempfile.TemporaryDirectory() as out:
            doc = equivalence.run(SimpleNamespace(log=lambda *_: None), SimpleNamespace(opts=SimpleNamespace(api=None, timeout=1)), [arm], lambda a, n: [], out, (5,))
        self.assertEqual(doc["counts"]["5"]["arms"]["ref"]["extensions"], {"count": 5, "template_sha256": benchext.template_sha256()})
        self.assertEqual(doc["template_sha256"], benchext.template_sha256())

    def test_a_different_tool_declaration_or_carried_result_names_the_field(self):
        declared = self.record()
        declared["declared"]["bench_tool_01"]["parameters"] = {"type": "object", "properties": {"val": {"type": "string"}}}
        carried = self.record()
        carried["carried"] = ["bench 01 ok, as the model saw it"]
        doc = self.run_gate({"ref": self.record(), "a": declared, "b": carried})
        diffs = doc["counts"]["10"]["differences"]
        self.assertFalse(doc["passed"])
        self.assertTrue(diffs["a"][0].startswith(".declared.bench_tool_01.parameters"), diffs["a"])
        self.assertTrue(diffs["b"][0].startswith(".carried[0]"), diffs["b"])


class Gates(unittest.TestCase):
    """The order of the checks before the first sample: a failed equivalence refuses the run and the calibration does not run; a failed calibration refuses it too."""

    def runner(self, equivalence, calibration, wanted=True, strict=True):
        from types import SimpleNamespace
        from buffon.runner import engine, equivalence as equivlib
        r = engine.Runner(engine.Plan(workloads=[], arms=[], out=tempfile.mkdtemp(), strict=strict), log=lambda *_: None)
        calls = []
        r.calibrate = lambda ctx, instances: calls.append("calibrate") or calibration
        for name, value in (("counts", lambda plan: [10] if wanted else []), ("run", lambda *a: calls.append("equivalence") or equivalence)):
            self.addCleanup(setattr, equivlib, name, getattr(equivlib, name))
            setattr(equivlib, name, value)
        return r.gates(SimpleNamespace(), [], []), calls

    def test_a_failed_equivalence_refuses_before_the_calibration(self):
        (eq, cal, refused), calls = self.runner({"passed": False, "counts": {"10": {"differences": {"pig-go-fused": [".results[0]: 1 != 2"]}}}}, {"passed": True})
        self.assertEqual(calls, ["equivalence"])
        self.assertIsNone(cal)
        self.assertIn("do not do the same work", refused)
        self.assertIn("pig-go-fused with 10 extensions: .results[0]: 1 != 2", refused)

    def test_a_passed_equivalence_goes_on_to_the_calibration(self):
        (eq, cal, refused), calls = self.runner({"passed": True, "counts": {}}, {"passed": True})
        self.assertEqual((calls, refused), (["equivalence", "calibrate"], None))
        (eq, cal, refused), calls = self.runner({"passed": True, "counts": {}}, {"passed": False, "max_cv": 0.2})
        self.assertIn("calibration gate failed", refused)

    def test_without_strict_mode_a_failed_calibration_is_a_label_not_a_refusal(self):
        (eq, cal, refused), calls = self.runner({"passed": True, "differences": {}}, {"passed": False, "max_cv": 0.2}, strict=False)
        self.assertIsNone(refused)
        self.assertFalse(cal["passed"])

    def test_without_a_ten_extension_scenario_only_the_calibration_runs(self):
        (eq, cal, refused), calls = self.runner({"passed": False, "differences": {"x": ["y"]}}, {"passed": True}, wanted=False)
        self.assertEqual((eq, calls, refused), (None, ["calibrate"], None))


if __name__ == "__main__":
    unittest.main()
