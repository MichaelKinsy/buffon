"""The runner's observer hooks (docs/HOOKS.md): order, data placement, isolation of a failing observer, and loading."""
import types
import unittest

from buffon.runner import engine, hooks
from buffon.workloads.overhead import Skip
from tests.test_quiet import FakeCtx, runner


class Recorder(hooks.Observer):
    name = "rec"

    def __init__(self, log):
        self.log = log

    def run_start(self, run):
        self.log.append(("run_start", run.backend))
        return {"cpus": run.cpus}

    def sample_begin(self, window):
        self.log.append(("begin", window.arm, window.scenario, window.round, window.host["host_load1"]))
        return {"t": 1}

    def sample_end(self, window, state, record):
        self.log.append(("end", state, record.get("cpu_ms"), record.get("host_load1")))
        return {"seen_state": state["t"]}

    def run_end(self, run, raw):
        self.log.append(("run_end", len(raw["samples"])))
        return {"samples": len(raw["samples"])}


class Exploding(hooks.Observer):
    name = "boom"

    def sample_begin(self, window):
        raise RuntimeError("begin broke")

    def sample_end(self, window, state, record):
        raise RuntimeError("end broke")


def with_gate(r):
    r.gate = types.SimpleNamespace(window_s=0.25, wait=lambda: ({"host_load1": 2.0, "host_runnable": 1, "pinned_busy": 0.0}, 0, True))
    r.run_info = hooks.RunInfo(r.plan, {})
    return r


class Hooks(unittest.TestCase):
    def test_begin_precedes_the_workload_and_end_sees_the_finished_record(self):
        log = []
        r, w = runner(observers=[Recorder(log)])
        w.fn = lambda ctx, a: log.append(("workload",)) or {"cpu_ms": 5.0}
        r = with_gate(r)
        r.measure(FakeCtx(), [r.plan.arms[0]])
        self.assertEqual([e[0] for e in log], ["begin", "workload", "end"])
        self.assertEqual(log[0][4], 2.0)                       # the gate's reading is in the window
        self.assertEqual(log[2][1:], ({"t": 1}, 5.0, 2.0))     # the record already holds the workload's data and the host reading
        self.assertEqual(r.samples[0]["telemetry"], {"rec": {"seen_state": 1}})

    def test_a_failing_observer_never_changes_the_measurement_and_is_recorded(self):
        r, w = runner(observers=[Exploding(), Recorder([])])
        r = with_gate(r)
        r.measure(FakeCtx(), [r.plan.arms[0]])
        s = r.samples[0]
        self.assertEqual(s["cpu_ms"], 1.0)
        self.assertNotIn("failure", s)
        self.assertEqual(s["telemetry"], {"rec": {"seen_state": 1}})   # the healthy observer still delivered
        self.assertEqual({(e["observer"], e["hook"]) for e in r.obs.errors}, {("boom", "sample_begin"), ("boom", "sample_end")})

    def test_a_skipped_sample_still_closes_the_window(self):
        log = []
        r, w = runner(observers=[Recorder(log)])
        def skip(ctx, a):
            raise Skip("no")
        w.fn = skip
        r = with_gate(r)
        r.measure(FakeCtx(), [r.plan.arms[0]])
        self.assertEqual([e[0] for e in log], ["begin", "end"])

    def test_no_observers_means_no_telemetry_key(self):
        r, _ = runner()
        r = with_gate(r)
        r.measure(FakeCtx(), [r.plan.arms[0]])
        self.assertNotIn("telemetry", r.samples[0])

    def test_load_accepts_only_observers(self):
        self.assertIsInstance(hooks.load(f"{__name__}:make_recorder"), Recorder)
        with self.assertRaises(TypeError):
            hooks.load(f"{__name__}:not_an_observer")
        with self.assertRaises(ValueError):
            hooks.load("nocolon")


def make_recorder():
    return Recorder([])


def not_an_observer():
    return object()
