# SPDX-License-Identifier: Apache-2.0
"""The runner's enforced rules, exercised with fake arms and fake workloads: nothing here starts a harness."""
import copy
import os
import tempfile
import types
import unittest

from buffon.runner import cgroup, cpumon, detect, egress, engine, facts as factlib, raw as rawlib
from buffon.site import Site
from buffon.workloads import Workload
from buffon.workloads.overhead import Skip
from tests.nopin import without_affinity


def arm(name, **caps):
    return types.SimpleNamespace(id=name, label=name, twin_of=None, apis=["openai-completions", "anthropic-messages"], capabilities=caps, supports_mode=lambda m: True,
                                 supports_api=lambda a: True)


class FakeServer:
    """The parts of MockServer a sample touches: the log context and the flush."""

    def __init__(self):
        self.context, self.flushed = {}, []

    def flush_log(self):
        self.flushed.append(dict(self.context))


class FakeCtx:
    def __init__(self):
        self.opts = types.SimpleNamespace(api=None)
        self.released = 0
        self.server = FakeServer()

    def release(self):
        self.released += 1

    def harnesses_for(self, arm):
        return []


def runner(workloads, arms, **kw):
    out = tempfile.mkdtemp()
    plan = engine.Plan(workloads=workloads, arms=arms, out=out, **kw)
    r = engine.Runner(plan, log=lambda *_: None)
    r.isolation = {}
    return r


class Twins(unittest.TestCase):
    def test_every_arm_gets_an_ab_copy_by_default(self):
        out = engine.with_twins([arm("a"), arm("b")], "all")
        self.assertEqual([(x.id, x.twin_of) for x in out], [("a", None), ("b", None), ("a-b", "a"), ("b-b", "b")])

    def test_none_and_selected_lists(self):
        self.assertEqual([x.id for x in engine.with_twins([arm("a"), arm("b")], "none")], ["a", "b"])
        self.assertEqual([x.id for x in engine.with_twins([arm("a"), arm("b")], "b")], ["a", "b", "b-b"])
        with self.assertRaises(engine.Refused):
            engine.with_twins([arm("a")], "zzz")

    def test_the_copy_is_a_separate_object(self):
        a = arm("a")
        twin = engine.with_twins([a], "all")[1]
        self.assertIsNot(twin, a)
        self.assertIsNone(a.twin_of)


class Rules(unittest.TestCase):
    def test_fewer_than_twelve_rounds_is_refused_only_in_strict_mode_unless_allowed(self):
        with self.assertRaisesRegex(engine.Refused, "below the minimum of 12"):
            engine.Plan(workloads=[], arms=[], rounds=11, strict=True).validate()
        engine.Plan(workloads=[], arms=[], rounds=12, strict=True).validate()
        engine.Plan(workloads=[], arms=[], rounds=3, allow_short=True, strict=True).validate()
        engine.Plan(workloads=[], arms=[], rounds=3, adaptive=True, strict=True).validate()

    def test_without_strict_mode_a_short_run_is_recorded_not_refused(self):
        engine.Plan(workloads=[], arms=[], rounds=3).validate()

    def test_required_pinning_without_cpus_is_refused(self):
        with self.assertRaisesRegex(engine.Refused, "requires pinning"):
            engine.Plan(workloads=[], arms=[], pinning="required").validate()

    def test_cpus_the_machine_does_not_give_are_refused(self):
        with self.assertRaisesRegex(engine.Refused, "not available"):
            engine.Plan(workloads=[], arms=[], cpus=[10**6]).validate()

    def test_overlapping_harness_and_mock_cpus_are_refused(self):
        c = factlib.allowed_cpus()[0]
        with self.assertRaisesRegex(engine.Refused, "overlap"):
            engine.Plan(workloads=[], arms=[], cpus=[c], mock_cpus=[c]).validate()

    def test_rotation_shifts_the_first_arm_every_round(self):
        firsts = [engine.rotate(["a", "b", "c"], r)[0] for r in range(6)]
        self.assertEqual(firsts, ["a", "b", "c", "a", "b", "c"])
        self.assertEqual(engine.rotate([], 3), [])

    def test_variants_follow_the_workloads_apis(self):
        w = Workload(id="x/y", family="x", apis=("openai-completions",))
        v = Workload(id="x/z", family="x")
        self.assertEqual([(a.id, b) for a, b in engine.variants([w, v], ["openai-completions", "anthropic-messages"])],
                         [("x/y", "openai-completions"), ("x/z", "openai-completions"), ("x/z", "anthropic-messages")])


class Measure(unittest.TestCase):
    def run_plan(self, fn, rounds=4, warmup=1, arms=("a", "b"), apis=("openai-completions",), **kw):
        w = Workload(id="t/w", family="t", fn=fn)
        r = runner([w], [arm(n) for n in arms], rounds=rounds, warmup=warmup, apis=list(apis), allow_short=True, **kw)
        r.measure(FakeCtx(), engine.with_twins(r.plan.arms, "all"))
        return r

    def test_every_variant_runs_every_arm_and_copy_each_round_with_the_first_round_marked_warmup(self):
        r = self.run_plan(lambda ctx, a: {"cpu_ms": 1.0})
        self.assertEqual(len(r.samples), 5 * 4)
        self.assertEqual({s["arm"] for s in r.samples}, {"a", "b", "a-b", "b-b"})
        for rnd in range(5):
            in_round = [s["arm"] for s in r.samples if s["round"] == rnd]
            self.assertEqual(sorted(in_round), ["a", "a-b", "b", "b-b"])
        self.assertTrue(all(s["warmup"] == (s["round"] < 1) for s in r.samples))
        self.assertEqual({s["twin_of"] for s in r.samples if s["arm"].endswith("-b")}, {"a", "b"})

    def test_arm_order_rotates_between_rounds(self):
        r = self.run_plan(lambda ctx, a: {"cpu_ms": 1.0})
        first = [next(s["arm"] for s in r.samples if s["round"] == rnd) for rnd in range(5)]
        self.assertGreater(len(set(first)), 1)

    def test_each_sample_releases_its_harness(self):
        w = Workload(id="t/w", family="t", fn=lambda ctx, a: {"x": 1})
        r = runner([w], [arm("a")], rounds=2, warmup=0, apis=["openai-completions"], allow_short=True)
        ctx = FakeCtx()
        r.measure(ctx, engine.with_twins(r.plan.arms, "all"))
        self.assertEqual(ctx.released, len(r.samples))

    def test_each_sample_labels_the_mock_log_and_flushes_it_before_the_next_sample(self):
        seen = []
        w = Workload(id="t/w", family="t", fn=lambda ctx, a: seen.append(dict(ctx.server.context)) or {"x": 1})
        r = runner([w], [arm("a")], rounds=2, warmup=1, apis=["openai-completions"], allow_short=True)
        ctx = FakeCtx()
        r.measure(ctx, engine.with_twins(r.plan.arms, "all"))
        self.assertEqual(len(ctx.server.flushed), len(r.samples))
        self.assertEqual(ctx.server.flushed, seen)
        self.assertEqual({(c["arm"], c["round"], c["warmup"]) for c in seen}, {("a", 0, True), ("a-b", 0, True), ("a", 1, False), ("a-b", 1, False), ("a", 2, False), ("a-b", 2, False)})
        self.assertTrue(all(c["scenario"] == "t/w" and c["api"] == "openai-completions" for c in seen))

    def test_failures_are_recorded_and_an_arm_gives_up_after_three_in_a_row(self):
        def fn(ctx, a):
            return {"failure": "boom"} if a.id == "b" else {"cpu_ms": 1.0}
        r = self.run_plan(fn, rounds=8, warmup=0)
        b = [s for s in r.samples if s["arm"] == "b"]
        self.assertEqual(len(b), engine.GIVE_UP_AFTER)
        self.assertTrue(all(s["failure"] == "boom" for s in b))
        self.assertEqual(len([s for s in r.samples if s["arm"] == "a"]), 8)

    def test_a_success_resets_the_failure_streak(self):
        calls = {"n": 0}

        def fn(ctx, a):
            if a.id != "a":
                return {"cpu_ms": 1.0}
            calls["n"] += 1
            return {"failure": "x"} if calls["n"] % 3 else {"cpu_ms": 1.0}
        r = self.run_plan(fn, rounds=9, warmup=0, arms=("a",))
        self.assertEqual(len([s for s in r.samples if s["arm"] == "a"]), 9)

    def test_a_workload_exception_is_a_recorded_failure_not_a_crash(self):
        def fn(ctx, a):
            raise ValueError("bad")
        r = self.run_plan(fn, rounds=1, warmup=0, arms=("a",))
        self.assertIn("runner error", r.samples[0]["failure"])

    def test_skip_is_recorded_with_its_reason_and_the_arm_sits_out(self):
        def fn(ctx, a):
            if a.id.startswith("b"):
                raise Skip("no such mode")
            return {"cpu_ms": 1.0}
        r = self.run_plan(fn, rounds=3, warmup=0)
        self.assertEqual({(s["arm"], s["reason"]) for s in r.skipped}, {("b", "no such mode"), ("b-b", "no such mode")})
        self.assertEqual({s["arm"] for s in r.samples}, {"a", "a-b"})

    def test_any_non_loopback_connect_fails_the_sample_and_the_run(self):
        def fn(ctx, a):
            if a.id == "a":
                egress.OBSERVED.add("203.0.113.9:443")
            return {"cpu_ms": 1.0}
        r = self.run_plan(fn, rounds=1, warmup=0, arms=("a",))
        bad = [s for s in r.samples if s["arm"] == "a"][0]
        self.assertIn("203.0.113.9:443", bad["failure"])
        self.assertEqual(r.violations[0]["remotes"], ["203.0.113.9:443"])
        self.assertEqual(r.violations[0]["arm"], "a")

    def test_series_is_kept_under_its_own_key(self):
        r = self.run_plan(lambda ctx, a: {"cpu_ms": 1.0, "_series": {"turns": [1, 2]}}, rounds=1, warmup=0, arms=("a",))
        self.assertEqual(r.samples[0]["series"], {"turns": [1, 2]})
        self.assertNotIn("_series", r.samples[0])

    def test_each_api_is_its_own_variant(self):
        r = self.run_plan(lambda ctx, a: {"cpu_ms": 1.0}, rounds=1, warmup=0, arms=("a",), apis=("openai-completions", "anthropic-messages"))
        self.assertEqual({s["api"] for s in r.samples}, {"openai-completions", "anthropic-messages"})


CAN_PIN = hasattr(os, "sched_setaffinity")   # not on macOS


class Pinning(unittest.TestCase):
    def tearDown(self):
        cgroup.set_pinned_cpus(None)

    def test_a_platform_that_cannot_pin_is_unpinned_even_when_the_site_names_cpus(self):
        plan = engine.Plan(workloads=[], arms=[], cpus=[0], mock_cpus=[], pinning="preferred", out=tempfile.mkdtemp())
        with without_affinity():
            self.assertFalse(plan.can_pin)
            cgroup.set_pinned_cpus([0])
            engine.Runner.apply_pinning(types.SimpleNamespace(plan=plan))
            self.assertIsNone(cgroup.PINNED_CPUS)
            self.assertTrue(any("cannot pin" in r for r in engine.run_reasons(plan, [], [], {"mode": "socket-audit"}, {})))
            with self.assertRaisesRegex(engine.Refused, "cannot pin"):
                engine.Plan(workloads=[], arms=[], cpus=[0], pinning="required").validate()
        self.assertEqual(plan.can_pin, CAN_PIN)

    @unittest.skipUnless(CAN_PIN, "no sched_setaffinity on this platform")
    def test_pinned_children_run_on_the_pinned_cpus_only(self):
        import subprocess
        cpu = factlib.allowed_cpus()[0]
        cgroup.set_pinned_cpus([cpu])
        meter = cgroup.RusageMeter()
        proc = meter.popen(["python3", "-c", "import os;print(sorted(os.sched_getaffinity(0)))"], stdout=subprocess.PIPE, text=True)
        out = proc.communicate()[0]
        meter.close()
        self.assertEqual(out.strip(), f"[{cpu}]")

    @unittest.skipUnless(CAN_PIN, "no sched_getaffinity on this platform")
    def test_without_a_pin_the_child_inherits_the_affinity(self):
        import subprocess
        meter = cgroup.RusageMeter()
        proc = meter.popen(["python3", "-c", "import os;print(len(os.sched_getaffinity(0)))"], stdout=subprocess.PIPE, text=True)
        out = proc.communicate()[0]
        meter.close()
        self.assertEqual(int(out), len(os.sched_getaffinity(0)))


class Detection(unittest.TestCase):
    def facts(self, **kw):
        f = {"pinned_cpus": "2-3", "governors": {"2": "performance", "3": "performance"}, "fixed_clock": True, "container": None, "cpus_allowed": "0-7"}
        f.update(kw)
        return f

    def site(self, hw="dedicated"):
        return Site(name="s", hardware=hw)

    CAL = {"passed": True, "max_cv": 0.01, "gate": 0.05}

    def test_all_conditions_met_is_quiet_dedicated(self):
        ok, why = detect.assess(self.site(), self.facts(), {2: 0.0, 3: 0.01}, {2: 0.0, 3: 0.0}, 0, self.CAL)
        self.assertEqual((ok, why), (True, []))

    def test_a_hypervisor_clock_claim_is_honoured_only_on_a_machine_that_shows_it_is_a_virtual_machine(self):
        # review: bare metal without a cpufreq driver also reads as "nothing readable" and may run with turbo on; the claim needs the machine's own sign of a VM
        from buffon.runner import facts as factlib
        self.assertEqual(engine.effective_clock_claim("hypervisor", vm=lambda: "cpu flag hypervisor"), ("hypervisor", None))
        claim, why = engine.effective_clock_claim("hypervisor", vm=lambda: None)
        self.assertEqual(claim, "")
        self.assertIn("no sign of one", why)
        self.assertEqual(engine.effective_clock_claim("", vm=lambda: None), ("", None))
        self.assertEqual(factlib.virtual_machine(flags=["fpu", "hypervisor"], detect=lambda: None), "cpu flag hypervisor")
        self.assertEqual(factlib.virtual_machine(flags=["fpu"], detect=lambda: "kvm"), "systemd-detect-virt: kvm")
        self.assertIsNone(factlib.virtual_machine(flags=["fpu"], detect=lambda: "none"))
        self.assertIsNone(factlib.virtual_machine(flags=["fpu"], detect=lambda: None))

    def test_the_runner_resolves_the_clock_claim_before_preflight_and_passes_the_result_on(self):
        import inspect
        src = inspect.getsource(engine.Runner)
        self.assertIn("self.clock_claim, self.clock_claim_refused = effective_clock_claim(p.clock_claim)", src)
        self.assertNotIn("clock_claim=p.clock_claim", src)

    def test_a_hypervisor_clock_claim_accepts_an_unreadable_clock_but_never_a_scaling_governor(self):
        no_interface = self.facts(governors={"2": None, "3": None})
        args = (self.site(), no_interface, {2: 0.0}, {2: 0.0}, 0, self.CAL)
        self.assertFalse(detect.assess(*args)[0])
        self.assertEqual(detect.assess(*args, clock_claim="hypervisor"), (True, []))
        scaling = self.facts(fixed_clock=False, governors={"2": "ondemand", "3": "ondemand"})
        ok, why = detect.assess(self.site(), scaling, {2: 0.0}, {2: 0.0}, 0, self.CAL, clock_claim="hypervisor")
        self.assertFalse(ok)
        self.assertIn("scales its clock", " ".join(why))

    def test_each_failed_condition_is_named(self):
        cases = [
            (dict(site=self.site("shared")), "does not claim dedicated"),
            (dict(facts=self.facts(pinned_cpus=None)), "not pinned"),
            (dict(facts=self.facts(fixed_clock=False, governors={"2": "ondemand"})), "scales its clock"),
            (dict(facts=self.facts(governors={"2": None, "3": None})), "unknown"),
            (dict(idle_before={2: 0.5}), "busy with other work before"),
            (dict(idle_after={3: 0.2}), "busy with other work after"),
            (dict(throttled=500), "throttled"),
            (dict(calibration=None), "no calibration"),
            (dict(calibration={"passed": False, "max_cv": 0.2, "gate": 0.05}), "gate failed"),
        ]
        for override, text in cases:
            args = dict(site=self.site(), facts=self.facts(), idle_before={2: 0.0}, idle_after={2: 0.0}, throttled=0, calibration=self.CAL)
            args.update(override)
            ok, why = detect.assess(**args)
            self.assertFalse(ok, text)
            self.assertTrue(any(text in w for w in why), (text, why))

    def test_a_pod_whose_cpuset_is_not_the_requested_count_is_not_exclusive(self):
        f = self.facts(container="kubernetes", cpus_allowed="0-15", governors={"2": None, "3": None})
        ok, why = detect.assess(self.site(), f, {2: 0}, {2: 0}, 0, self.CAL, requested_cpus=4)
        self.assertFalse(ok)
        self.assertTrue(any("exclusive" in w for w in why))
        f["cpus_allowed"] = "2-5"
        self.assertTrue(detect.assess(self.site(), f, {2: 0}, {2: 0}, 0, self.CAL, requested_cpus=4)[0])


class CpuMon(unittest.TestCase):
    def test_busy_fraction_from_two_readings(self):
        before = {None: (100, 1000), 0: (10, 100), 1: (0, 100)}
        after = {None: (150, 1100), 0: (60, 200), 1: (0, 200)}
        self.assertEqual(cpumon.busy_fractions(before, after, [0, 1]), {0: 0.5, 1: 0.0})
        self.assertEqual(cpumon.busy_fractions(before, after, [None]), {None: 0.5})

    def test_idle_check_uses_the_readings_around_the_wait(self):
        reads = iter([{3: (0, 100)}, {3: (30, 200)}])
        slept = []
        got = cpumon.idle_check([3], 2.0, read=lambda: next(reads), sleep=slept.append)
        self.assertEqual((got, slept), ({3: 0.3}, [2.0]))

    @unittest.skipUnless(os.path.exists("/proc/stat"), "no /proc/stat on this platform")
    def test_proc_stat_parses_here(self):
        stat = cpumon.read_stat()
        self.assertIn(None, stat)
        self.assertTrue(all(b <= t for b, t in stat.values()))


class RawFormat(unittest.TestCase):
    def good(self):
        return {"kind": "buffon-run", "run": {}, "site": {}, "hardware": {}, "lock_sha256": None, "runner": {}, "arms": {}, "calibration": None, "egress": {}, "isolation": {},
                "samples": [{"arm": "a", "scenario": "x/y", "api": None, "round": 0, "warmup": False, "cpu_ms": 1.5, "meter": "rusage", "series": {"t": [1]}}], "skipped": [], "ok": True}

    def test_a_good_document_validates_and_round_trips(self):
        d = tempfile.mkdtemp()
        rawlib.write(self.good(), d)
        self.assertEqual(rawlib.read(d)["samples"][0]["cpu_ms"], 1.5)

    def test_runs_published_before_the_rename_still_validate(self):
        r = self.good()
        r["kind"] = "arena-run"
        rawlib.validate(r)

    def test_rejects_malformed_documents(self):
        for mutate, msg in [(lambda r: r.pop("samples"), "lacks"), (lambda r: r.update(kind="other"), "kind"),
                            (lambda r: r["samples"][0].update(round="0"), "round"), (lambda r: r["samples"][0].update(round=True), "round"),
                            (lambda r: r["samples"][0].update(cpu_ms=float("nan")), "finite"), (lambda r: r["samples"][0].update(extra=[1]), "series"),
                            (lambda r: r["samples"][0].pop("arm"), "arm"), (lambda r: r["skipped"].append({"arm": "a"}), "skipped")]:
            r = self.good()
            mutate(r)
            with self.assertRaisesRegex(rawlib.RawError, msg):
                rawlib.validate(r)

    def test_no_version_field_is_required_or_accepted_as_a_shape_switch(self):
        self.assertNotIn("version", rawlib.TOP)


if __name__ == "__main__":
    unittest.main()


class EffectiveApis(unittest.TestCase):
    def arms(self, *names):
        from buffon.arms import manifest
        return [manifest.load_arm(n) for n in names]

    def plan(self, **kw):
        from buffon.runner import engine
        return engine.Plan(workloads=[], arms=[], **kw)

    def test_responses_is_added_only_when_an_arm_speaks_nothing_else(self):
        from buffon.runner import engine
        self.assertEqual(engine.effective_apis(self.plan(), self.arms("pi-node", "pig-0.4.1")), ["openai-completions", "anthropic-messages"])
        self.assertEqual(engine.effective_apis(self.plan(), self.arms("pi-node", "codex")), ["openai-completions", "anthropic-messages", "openai-responses"])

    def test_named_apis_are_run_exactly(self):
        from buffon.runner import engine
        plan = self.plan(apis=["openai-completions"], apis_explicit=True)
        self.assertEqual(engine.effective_apis(plan, self.arms("pi-node", "codex")), ["openai-completions"])

    def test_an_api_independent_workload_runs_once_whatever_the_apis(self):
        from buffon import workloads
        from buffon.runner import engine
        version = workloads.REGISTRY["overhead/version"]
        self.assertEqual(engine.variants([version], ["openai-completions", "anthropic-messages", "openai-responses"]), [(version, None)])
        self.assertEqual(len(engine.variants([workloads.REGISTRY["overhead/print"]], ["openai-completions", "openai-responses"])), 2)
