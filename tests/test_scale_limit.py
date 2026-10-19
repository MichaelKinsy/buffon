# SPDX-License-Identifier: Apache-2.0
"""The exact limit of the scale family (buffon/workloads/scale.py `search` and `limit_sample`): doubling to the first failure, then bisecting to the exact integer, every probe recorded. The search is
tested against a fake swarm (a function of N), the sample against the fake container runtime of tests/fake_swarm.py, one container per probe."""
import os
import tempfile
import types
import unittest

from buffon import workloads
from buffon.runner import raw
from buffon.workloads import scale
from tests.fake_swarm import FakeCgroup, FakeMock, FakeRuntime
from tests.test_scale import Env, MIB


def fake_swarm(limit, flaky=(), cause="oom"):
    """A swarm that holds `limit` agents: a probe of N completes when N <= limit and N is not in `flaky` (a probe that fails once although the swarm would hold it). Returns (run, calls)."""
    calls = []

    def run(n, phase):
        calls.append((n, phase))
        if n <= limit and n not in flaky:
            return {"mem_per_agent_mib": 10.0 + n / 100}
        return {"failure": f"{n} agents did not fit", "stop_cause": cause}
    return run, calls


class Search(unittest.TestCase):
    def found(self, limit, **kw):
        run, calls = fake_swarm(limit, flaky=kw.pop("flaky", ()))
        out = scale.search(run, **kw)
        self.assertEqual([(p["n"], p["phase"]) for p in out["probes"]], calls)   # every probe is recorded, in order
        self.assertEqual(len({n for n, _ in calls}), len(calls), "an N was probed twice")
        return out, calls

    def test_the_search_finds_the_exact_limit(self):
        for limit in (1, 2, 3, 4, 5, 6, 7, 8, 9, 100, 255, 256, 257, 287, 1000, 4095, 8000):
            out, calls = self.found(limit)
            self.assertEqual((out["limit"], out["first_failure"], out["capped"]), (limit, limit + 1, False), limit)
            self.assertLessEqual(len(calls), 2 * limit.bit_length() + 1, limit)    # doubling and bisecting: about 2 log2(limit) probes, not limit of them

    def test_a_limit_of_287_doubles_to_512_and_bisects_between_256_and_512(self):
        out, calls = self.found(287)
        self.assertEqual([n for n, ph in calls if ph == "double"], [1, 2, 4, 8, 16, 32, 64, 128, 256, 512])
        bisect = [n for n, ph in calls if ph == "bisect"]
        self.assertEqual(bisect[:3], [384, 320, 288])
        self.assertTrue(all(256 < n < 512 for n in bisect))
        self.assertEqual(calls[-1], (287, "bisect"))
        self.assertEqual([p["ok"] for p in out["probes"] if p["n"] in (256, 287)], [True, True])
        self.assertEqual([p["ok"] for p in out["probes"] if p["n"] in (288, 512)], [False, False])

    def test_a_swarm_that_does_not_hold_one_agent_has_a_limit_of_zero_and_one_probe(self):
        out, calls = self.found(0)
        self.assertEqual((out["limit"], out["first_failure"], out["capped"]), (0, 1, False))
        self.assertEqual(calls, [(1, "double")])

    def test_a_swarm_that_holds_more_than_the_cap_says_at_least_the_cap(self):
        out, calls = self.found(10 ** 9, cap=8192)
        self.assertEqual((out["limit"], out["first_failure"], out["capped"]), (8192, None, True))
        self.assertEqual([n for n, _ in calls], [2 ** k for k in range(14)])
        self.assertTrue(all(p["ok"] for p in out["probes"]))

    def test_a_cap_that_is_not_a_power_of_two_is_the_last_step_of_the_doubling(self):
        out, calls = self.found(10 ** 9, cap=100)
        self.assertEqual([n for n, _ in calls], [1, 2, 4, 8, 16, 32, 64, 100])
        self.assertEqual((out["limit"], out["capped"]), (100, True))

    def test_a_limit_just_under_the_cap_is_exact_not_capped(self):
        out, _ = self.found(99, cap=100)
        self.assertEqual((out["limit"], out["first_failure"], out["capped"]), (99, 100, False))
        out, _ = self.found(100, cap=100)
        self.assertEqual((out["limit"], out["first_failure"], out["capped"]), (100, None, True))

    def test_the_default_cap_is_8192_so_that_no_envelope_of_4_gib_reaches_it(self):
        self.assertEqual(scale.MAX_AGENTS, 8192)
        self.assertEqual(scale.RESOLUTION, 1)

    def test_a_probe_that_fails_once_below_the_limit_moves_the_boundary_to_a_pass_with_a_failure_just_above_it(self):
        for limit, flaky in ((20, {4}), (287, {272}), (287, {256}), (50, {1})):
            out, _ = self.found(limit, flaky=flaky)
            seen = {p["n"]: p["ok"] for p in out["probes"]}
            if out["limit"]:
                self.assertTrue(seen[out["limit"]], "the limit is a probe that completed")
            self.assertFalse(seen[out["first_failure"]], "the failure above it is a probe that failed")
            self.assertEqual(out["first_failure"], out["limit"] + 1)
            self.assertLessEqual(out["limit"], limit)
        out, _ = self.found(20, flaky={4})
        self.assertEqual((out["limit"], out["first_failure"]), (3, 4))   # the flake ends the doubling at 4 and the bisection finds 3 below it

    def test_a_resolution_stops_the_bisection_early_and_the_limit_is_within_it(self):
        exact, calls_exact = self.found(287)
        coarse, calls = self.found(287, resolution=16)
        self.assertLessEqual(coarse["first_failure"] - coarse["limit"], 16)
        self.assertLessEqual(coarse["limit"], 287)
        self.assertLess(287, coarse["first_failure"])
        self.assertLess(len(calls), len(calls_exact))

    def test_every_probe_keeps_the_fields_its_run_returned_and_the_failure_words(self):
        out, _ = self.found(5)
        ok, bad = [p for p in out["probes"] if p["n"] == 4][0], [p for p in out["probes"] if p["n"] == 8][0]
        self.assertEqual((ok["ok"], ok["mem_per_agent_mib"]), (True, 10.04))
        self.assertEqual((bad["ok"], bad["stop_cause"], bad["failure"]), (False, "oom", "8 agents did not fit"))


class Fixture(Env):
    """One fake container per probe: `Swarm` builds a new runtime and cgroup each time, so `oom_at` counts the agents of that container."""

    def containers(self, **knobs):
        self.rts = []

        def make(cfg):
            cg = FakeCgroup()
            cfg.cgroup_path = cg.dir
            rt = FakeRuntime(cg, **knobs)
            self.rts.append(rt)
            return self.Swarm(cfg, popen=rt.popen, poll_s=0.002)
        scale.swarmlib.Swarm = make

    def ctx(self, round_=0, **params):
        c = super().ctx(round_, **params)
        c.released, c.kwargs, harness = 0, [], c.harness
        c.server.context = {"arm": "a", "scenario": "scale/agents-limit", "api": None, "round": round_, "warmup": False}
        c.server.sink = None

        def release():
            c.released += 1
        c.release = release

        def recording(arm, scenario, **kw):
            c.kwargs.append(dict(kw))
            return harness(arm, scenario, **kw)
        c.harness = recording
        return c

    def ext_arm(self, pi_extensions="native", name="a"):
        outside = tempfile.mkdtemp(prefix="scale-ext-")   # a repository path the container does not mount
        paths = []
        for k in range(1, 11):
            p = os.path.join(outside, f"bench-ext-{k:02d}.ts")
            with open(p, "w") as f:
                f.write("export default function () {}\n")
            paths.append(p)
        arm = self.arm(name)
        arm.pi_extensions, arm.extension_spec = pi_extensions, {"paths": list(paths)}   # its own realization, outside the workspace
        arm.loads_template = lambda: False
        arm.extension_paths = lambda root=None: list(paths)
        arm.sources = paths
        return arm


class Limit(Fixture):
    def test_the_sample_is_the_exact_limit_with_every_probe_recorded(self):
        self.containers(oom_at=5, limit=1024 * MIB, mem_per_agent=300 * MIB)
        self.policy()
        out = scale.limit_sample(self.ctx(scale_turns=1), self.arm(), "agents", 0)
        self.assertEqual((out["agents_limit"], out["first_failure"], out["limit_capped"], out["limit_resolution"], out["limit_cap"]), (5, 6, False, 1, 8192))
        self.assertEqual(out["limit_cause"], "oom")
        self.assertIn("out of memory", out["limit_failure"])
        self.assertNotIn("failure", out)                                    # the harness held five agents: the sample is a result, not a failure
        self.assertEqual([(p["n"], p["phase"], p["ok"]) for p in out["probes"]], [(1, "double", True), (2, "double", True), (4, "double", True), (8, "double", False), (6, "bisect", False), (5, "bisect", True)])
        self.assertEqual(out["probe_count"], 6)
        self.assertEqual(out["extensions"], 0)
        for p in out["probes"]:
            self.assertEqual(p["pids_max"], scale.swarmlib.pids_limit(p["n"]))
            self.assertNotIn("swarm", p)
            self.assertNotIn("agents", p)
            self.assertIn("wall_s", p)
            self.assertEqual("stop_cause" in p, not p["ok"])
        passed = [p for p in out["probes"] if p["ok"]]
        self.assertTrue(all(p["agents_ok"] == p["n"] and p["mem_per_agent_mib"] > 0 and p["turns_per_s"] > 0 for p in passed))   # the curves keep their measurements at every N tried
        failed = [p for p in out["probes"] if not p["ok"]]
        self.assertTrue(all(p["stop_cause"] == "oom" and p["failure"] for p in failed))
        self.assertEqual(out["swarm"], {"memory_mib": 4096, "cpus": [2, 3, 4, 5], "pids_max": scale.swarmlib.pids_limit(8)})   # the largest probe's pids limit
        self.assertEqual(len(self.rts), 6)                                  # one container per probe

    def test_the_sample_passes_the_raw_format_check_and_a_malformed_probe_does_not(self):
        self.containers(oom_at=2, limit=1024 * MIB, mem_per_agent=300 * MIB)
        self.policy()
        out = scale.limit_sample(self.ctx(scale_turns=1), self.arm(), "agents", 0)
        rec = dict(out, arm="a", scenario="scale/agents-limit", api=None, round=0, warmup=False)
        raw.check_sample(rec, "sample")
        for bad in ({"n": 0, "phase": "double", "ok": True}, {"n": 2, "phase": "later", "ok": True}, {"n": 2, "phase": "double", "ok": "yes"}):
            with self.assertRaises(raw.RawError):
                raw.check_sample(dict(rec, probes=[bad]), "sample")

    def test_a_swarm_that_holds_not_even_one_agent_is_a_stop_with_its_cause(self):
        self.containers(oom_at=0, limit=1024 * MIB, mem_per_agent=300 * MIB)
        self.policy()
        out = scale.limit_sample(self.ctx(scale_turns=1), self.arm(), "agents", 0)
        self.assertEqual(out["agents_limit"], 0)
        self.assertEqual(out["stop_cause"], "oom")
        self.assertIn("out of memory", out["failure"])
        self.assertEqual([(p["n"], p["ok"]) for p in out["probes"]], [(1, False)])
        self.assertEqual(out["first_failure"], 1)

    def test_a_harness_that_completes_the_cap_is_at_least_the_cap(self):
        self.containers()
        self.policy()
        out = scale.limit_sample(self.ctx(scale_turns=1, swarm_max_agents=4), self.arm(), "agents", 0)
        self.assertEqual((out["agents_limit"], out["limit_capped"], out["limit_cap"]), (4, True, 4))
        self.assertNotIn("first_failure", out)
        self.assertNotIn("limit_cause", out)
        self.assertEqual([p["n"] for p in out["probes"]], [1, 2, 4])

    def test_a_coarser_resolution_is_a_parameter_and_is_recorded(self):
        self.containers(oom_at=11, limit=1024 * MIB, mem_per_agent=50 * MIB)
        self.policy()
        out = scale.limit_sample(self.ctx(scale_turns=1, scale_resolution=4), self.arm(), "print", 0)
        self.assertEqual(out["limit_resolution"], 4)
        self.assertLessEqual(out["first_failure"] - out["agents_limit"], 4)
        self.assertLessEqual(out["agents_limit"], 11)
        self.assertLess(11, out["first_failure"])

    def test_every_probe_starts_from_released_harnesses_and_hands_its_requests_to_the_log_with_its_n(self):
        self.containers(oom_at=3, limit=1024 * MIB, mem_per_agent=300 * MIB)
        self.policy()
        c = self.ctx(scale_turns=1)
        scale.limit_sample(c, self.arm(), "agents", 0)
        self.assertEqual(c.released, len(self.rts))
        self.assertEqual([ctx["probe"] for ctx, _sink in self.mock.flushed], [p for p in (1, 2, 4, 3)])
        self.assertTrue(all(ctx["scenario"] == "scale/agents-limit" and ctx["round"] == 0 for ctx, _sink in self.mock.flushed))


class Extensions(Fixture):
    def test_an_arm_that_does_not_load_pi_extensions_is_skipped_with_the_reason(self):
        self.containers()
        for kind in ("none", "partial"):
            with self.assertRaises(scale.Skip) as why:
                scale.limit_sample(self.ctx(), self.ext_arm(kind), "agents", 10)
            self.assertIn("extensions", str(why.exception))
        self.assertIn("does not load", str(self._why("none")))
        self.assertIn("only part", str(self._why("partial")))

    def _why(self, kind):
        with self.assertRaises(scale.Skip) as why:
            scale.limit_sample(self.ctx(), self.ext_arm(kind), "print", 10)
        return why.exception

    def test_every_agent_loads_the_ten_sources_from_a_path_the_container_mounts(self):
        self.containers(oom_at=2, limit=1024 * MIB, mem_per_agent=300 * MIB)
        self.policy()
        arm = self.ext_arm()
        c = self.ctx(scale_turns=1)
        out = scale.limit_sample(c, arm, "agents", 10)
        self.assertEqual(out["extensions"], 10)
        self.assertEqual(out["agents_limit"], 2)
        sources = {tuple(kw["extensions"]) for kw in c.kwargs}
        self.assertEqual(len(sources), 1)                                   # the same ten for every agent of every probe
        staged = list(sources)[0]
        self.assertEqual(len(staged), 10)
        self.assertTrue(all(os.path.exists(p) and p.startswith(self.tmp) for p in staged))   # copied under the workspace, which the container mounts; the originals are not
        self.assertFalse(any(p.startswith(self.tmp) for p in arm.sources))

    def test_an_rpc_agent_is_ready_only_when_it_lists_the_ten_extension_commands(self):
        self.containers(commands_late=2)                                    # the first two asks list none: the extensions are not loaded yet
        self.policy()
        out = scale.limit_sample(self.ctx(scale_turns=1, swarm_max_agents=2), self.ext_arm(), "agents", 10)
        self.assertEqual(out["agents_limit"], 2)
        asks = [cmd for rt in self.rts for cmd in rt.commands if cmd["op"] == "send" and '"get_commands"' in cmd["data"]]
        self.assertGreaterEqual(len(asks), 6)                               # asked again until listed, every agent

    def test_agents_that_never_list_their_extensions_do_not_complete_the_probe(self):
        self.containers(commands=9)
        self.policy()
        out = scale.limit_sample(self.ctx(scale_turns=1, scale_stage_timeout=0.3, swarm_max_agents=2), self.ext_arm(), "agents", 10)
        self.assertEqual(out["agents_limit"], 0)
        self.assertEqual(out["stop_cause"], "timeout")
        self.assertIn("never answered", out["failure"])

    def test_a_probe_whose_requests_did_not_declare_the_extension_tools_fails_as_an_error(self):
        self.containers()
        self.policy(fewest=6)
        out = scale.limit_sample(self.ctx(scale_turns=1, swarm_max_agents=2), self.ext_arm(), "print", 10)
        self.assertEqual(out["agents_limit"], 0)
        self.assertEqual(out["stop_cause"], "error")
        self.assertIn("extensions did not load", out["failure"])

    def test_a_print_probe_with_the_extensions_declared_completes(self):
        self.containers()
        self.policy(fewest=14)
        out = scale.limit_sample(self.ctx(scale_turns=1, swarm_max_agents=2), self.ext_arm(), "print", 10)
        self.assertEqual((out["agents_limit"], out["limit_capped"], out["extensions"]), (2, True, 10))

    def test_an_arm_with_the_extensions_built_in_loads_no_sources_but_is_checked_all_the_same(self):
        self.containers()
        self.policy(fewest=14)
        arm = self.ext_arm()
        arm.extension_spec, arm.extension_paths = {"embedded": True}, lambda root=None: []
        c = self.ctx(scale_turns=1, swarm_max_agents=1)
        out = scale.limit_sample(c, arm, "print", 10)
        self.assertEqual(out["agents_limit"], 1)
        self.assertEqual(c.kwargs[0]["extensions"], [])


class Registered(unittest.TestCase):
    def test_four_workloads_one_sample_per_round_with_no_copy_and_five_rounds(self):
        reg = workloads.load_all()
        ids = sorted(k for k in reg if k.startswith("scale/"))
        self.assertEqual(ids, ["scale/agents-ext10", "scale/agents-limit", "scale/print-ext10", "scale/print-limit"])
        for k in ids:
            w = reg[k]
            self.assertEqual((w.family, w.apis, w.rounds, w.aa), ("scale", (None,), scale.ROUNDS, False))


if __name__ == "__main__":
    unittest.main()
