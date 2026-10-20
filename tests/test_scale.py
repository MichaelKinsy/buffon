# SPDX-License-Identifier: Apache-2.0
"""The scale family (buffon/workloads/scale.py, buffon/runner/swarm.py): the swarm container's command line, the sample's fields, the stop of a probe that does not complete, OOM, timeout and
pids classification, the mock's saturation flag, and the run defaults. The search itself is in tests/test_scale_limit.py. A fake container runtime stands in for docker and the relay (tests/fake_swarm.py): no process starts."""
import os
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

from buffon import race, workloads
from buffon.envelope import lint
from buffon.mock import SWARM_FILE
from buffon.runner import cgroup, engine, swarm as swarmlib
from buffon.runner.container import ContainerConfig
from buffon.workloads import scale
from tests.fake_swarm import DIGEST, FakeCgroup, FakeMock, FakeRuntime
from tests.test_engine import FakeCtx

MIB = 1048576


class Env(unittest.TestCase):
    """One fake container runtime per test, the workload patched to use it, and a ctx that creates agents without starting any harness."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scale-test-")
        self.cg = FakeCgroup()
        self.rt = None
        self.saved = (scale.swarmlib.Swarm, cgroup.CONTAINER, scale.skip_unless)
        self.Swarm = scale.swarmlib.Swarm
        cgroup.CONTAINER = ContainerConfig(image=DIGEST, runtime="docker", cpuset_cpus=[2, 3, 4, 5], cpuset_mems="0", memory_mib=1024, ro_paths=[self.tmp], rw_dir=self.tmp,
                                           socket_path=os.path.join(self.tmp, "mock.sock"), mock_port=4321, relay_dir=self.tmp)
        scale.skip_unless = lambda ctx, arm, mode: None
        self.mock = FakeMock()
        self.addCleanup(self.restore)

    def restore(self):
        scale.swarmlib.Swarm, cgroup.CONTAINER, scale.skip_unless = self.saved

    def runtime(self, **kw):
        self.rt = FakeRuntime(self.cg, **kw)

        def make(cfg):
            cfg.cgroup_path = self.cg.dir
            return self.Swarm(cfg, popen=self.rt.popen, poll_s=0.002)
        scale.swarmlib.Swarm = make
        return self.rt

    def ctx(self, round_=0, **params):
        work = os.path.join(self.tmp, "work")
        os.makedirs(work, exist_ok=True)
        made = {}

        def harness(arm, scenario, home_root=None, **kw):
            name = f"{arm.id}-{scenario}"
            h = types.SimpleNamespace(cwd=os.path.join(work, name, "project"), home=os.path.join(home_root, name, "home"), env={"HOME": os.path.join(home_root, name, "home")},
                                      rpc_argv=lambda: ["agent", "--mode", "rpc"], print_argv=lambda prompt: ["agent", "-p", prompt])
            os.makedirs(h.cwd, exist_ok=True)
            os.makedirs(h.home, exist_ok=True)
            made[scenario] = h
            return h
        server = types.SimpleNamespace(reset=lambda policy=None: None, context={"round": round_})
        opts = types.SimpleNamespace(params={"scale_stage_timeout": 5, **params}, cpus=[2, 3, 4, 5], mock_cpus=[6, 7], memory_mib=4096, isolation="container")
        return types.SimpleNamespace(harness=harness, server=server, opts=opts, work=work, made=made, swarm_mock=self.mock, release=lambda: None)

    def arm(self, name="a"):
        return types.SimpleNamespace(id=name, rpc_dialect={}, apis=["openai-completions"])

    def policy(self, offered=(), **kw):
        self.mock = FakeMock(offered=offered, **kw)


class Argv(unittest.TestCase):
    def cfg(self, **kw):
        base = dict(image=DIGEST, runtime="docker", cpus=[8, 9, 10, 11], mems="1", memory_mib=1024, pids=64 * 8 + 1024, ro_paths=["/ws"], rw_dir="/ws/work", homes_dir="/ws/work/swarm-homes",
                    socket_path="/ws/mock.sock", mock_port=4321, relay_dir="/ws/relay")
        return swarmlib.SwarmConfig(**dict(base, **kw))

    def test_the_swarm_container_command_line_keeps_the_envelope_guarantees(self):
        argv = swarmlib.swarm_argv(self.cfg(), "buffon-swarm-x", "/ws/work/cid")
        self.assertEqual(lint(argv), [])
        flags = " ".join(argv)
        for want in ("--memory 1024m", "--memory-swap 1024m", "--cpuset-cpus 8-11", "--cpus 4", "--pids-limit 1536", "--network none", "--interactive", "--read-only", "--init", "-swarm"):
            self.assertIn(want, flags)
        self.assertEqual(sum(1 for a in argv if a == "--mount" and False), 0)
        tmpfs = [a for a in argv if a.startswith("/ws/work/swarm-homes:") or a.startswith("/tmp:")]
        self.assertEqual(len(tmpfs), 2)                                        # HOME's parent and /tmp are memory-backed; code and caches are on the disk mount
        self.assertEqual(len([a for a in argv if "source=/ws/mock.sock" in a]), 1)   # the mock's one socket

    def test_a_swarm_command_line_that_loses_a_guarantee_is_named_by_the_lint(self):
        argv = swarmlib.swarm_argv(self.cfg(), "n", "/c")
        i = argv.index("--pids-limit")
        self.assertTrue(any("G4" in p for p in lint(argv[:i] + argv[i + 2:])))
        i = argv.index("--cpus")
        broken = argv[:i + 1] + ["3"] + argv[i + 2:]
        self.assertTrue(any("G3" in p for p in lint(broken)))
        swap = argv.index("--memory-swap")
        self.assertTrue(any("G4" in p for p in lint(argv[:swap + 1] + ["2048m"] + argv[swap + 2:])))

    def test_the_pids_limit_is_64_per_agent_and_1024_over_and_the_record_is_the_sample_field(self):
        self.assertEqual((swarmlib.pids_limit(1), swarmlib.pids_limit(1024)), (1088, 66560))
        self.assertEqual(self.cfg().record(), {"memory_mib": 1024, "cpus": [8, 9, 10, 11], "pids_max": 1536})

    def test_the_ulimits_are_explicit_and_the_hard_descriptor_limit_is_above_the_soft(self):
        flags = " ".join(swarmlib.swarm_argv(self.cfg(), "n", "/c"))
        self.assertIn("nofile=4096:1048576", flags)
        for key in ("nproc", "core"):
            self.assertIn(f"--ulimit {key}=", flags)


class Parts(unittest.TestCase):
    def test_cgroup_counters_are_read_from_the_files(self):
        cg = FakeCgroup()
        cg.set(memory_current=7 * MIB, memory_peak=9 * MIB, oom_kill=2, usage_usec=1234, throttled=3, pids_peak=44)
        got = swarmlib.read_cgroup(cg.dir)
        self.assertEqual((got["memory.current"], got["memory.peak"], got["pids.peak"]), (7 * MIB, 9 * MIB, 44))
        self.assertEqual((got["memory.events"]["oom_kill"], got["cpu.stat"]["usage_usec"], got["cpu.stat"]["nr_throttled"]), (2, 1234, 3))
        self.assertIsNone(swarmlib.read_cgroup("/no/such/cgroup"))

    def test_the_cause_comes_from_the_kernels_counters_first(self):
        self.assertEqual(scale.classify(2, 5, True), "oom")
        self.assertEqual(scale.classify(0, 5, True), "pids")
        self.assertEqual(scale.classify(0, 0, True), "timeout")
        self.assertEqual(scale.classify(0, 0, False), "error")

    def test_failure_text_says_what_the_kernel_did_and_the_race_reads_it_as_an_oom(self):
        text = scale.failure_text(16, never=3, exits=[{"signal": 9}] * 3, oom_kills=3, peak_mib=1024.0, limit_mib=1024.0)
        self.assertIn("3 of 16 agents never answered get_state", text)
        self.assertIn("3 agents exited (signal 9: killed, out of memory?)", text)
        self.assertIn("out of memory: the kernel's OOM killer stopped 3 processes (container peak 1024 MiB of 1024 MiB)", text)
        self.assertEqual(race.stop_cause({"failure": text})["cause"], race.OOM)
        pids = scale.failure_text(8, never=1, pids_blocked=7, pids_peak=1152, pids_max=1152)
        self.assertIn("process limit: 7 forks refused at 1152 of 1152 processes", pids)

    def test_the_race_trusts_the_samples_own_cause(self):
        for cause in ("oom", "timeout", "pids", "error"):
            self.assertEqual(race.stop_cause({"failure": "words that say nothing", "stop_cause": cause})["cause"], cause)
        self.assertEqual(race.stop_cause({"failure": "x", "stop_cause": "oom", "mem_peak_mib": 1000.0})["peak_mib"], 1000.0)

    def test_the_mock_is_saturated_at_90_percent_of_its_workers_cpus_or_when_one_worker_is_full(self):
        self.assertFalse(scale.mock_flag(2.0, 0.5, 8))        # 2 of 8 CPUs, no worker near its limit
        self.assertTrue(scale.mock_flag(7.3, 0.95, 8))        # 7.3 of 8 CPUs is over 90%
        self.assertTrue(scale.mock_flag(1.0, 0.95, 8))        # one worker full: its connections wait whatever the others do
        self.assertFalse(scale.mock_flag(3.5, 0.89, 4))
        self.assertTrue(scale.mock_flag(3.7, 0.5, 4))
        self.assertFalse(scale.mock_flag(None, None, 4))

    def test_percentiles(self):
        self.assertEqual((scale.percentile([5, 1, 3, 2, 4], 0.5), scale.percentile([5, 1, 3, 2, 4], 1.0), scale.percentile([], 0.5)), (3, 5, None))
        self.assertEqual(scale.percentile(list(range(1, 101)), 0.95), 95)

    def test_the_agent_prompt_carries_the_marker_the_scripted_model_reads(self):
        from buffon.mock import server
        self.assertTrue(server.SWARM_MARKER.search(scale.agent_prompt(17, 2)))
        self.assertEqual(server.SWARM_MARKER.search(scale.agent_prompt(17, 2)).groups(), ("17", "2"))


class Swarm(Env):
    def test_a_clean_rpc_probe_has_every_field_the_contract_names(self):
        self.runtime()
        self.policy()
        out = scale.probe(self.ctx(scale_turns=2), self.arm(), 4, "agents")
        self.assertNotIn("failure", out)
        self.assertEqual((out["agents"], out["agents_ok"]), (4, 4))
        self.assertEqual(out["swarm"], {"memory_mib": 4096, "cpus": [2, 3, 4, 5], "pids_max": swarmlib.pids_limit(4)})   # the ctx's container tier: 4 GiB, the run's harness CPUs
        for key in ("mem_baseline_mib", "mem_peak_mib", "mem_per_agent_mib", "pss_mib_per_agent", "cpu_ms", "cpu_ms_per_agent_turn", "turns_per_s", "latency_ms_p50", "latency_ms_p95", "latency_ms_max",
                    "ready_ms", "oom_kills", "pids_peak", "throttled_periods", "mock_cpu_ms", "mock_saturated"):
            self.assertIn(key, out)
            self.assertIsNotNone(out[key], key)
        self.assertEqual(out["mem_baseline_mib"], 3.0)
        self.assertEqual(out["mem_peak_mib"], 3 + 4 * 50)
        self.assertAlmostEqual(out["mem_per_agent_mib"], 50.0)                        # (peak - baseline) / N
        self.assertEqual(out["pss_mib_per_agent"], 100.0)
        self.assertEqual(out["oom_kills"], 0)
        self.assertFalse(out["mock_saturated"])
        # CPU: the container's delta minus the launcher's: 4 starts x 300 ms + 8 prompts x 20 ms, less the relay's 0 (it reads 10 ms both times)
        self.assertAlmostEqual(out["cpu_ms"], 4 * 300 + 8 * 20)
        self.assertAlmostEqual(out["cpu_ms_per_agent_turn"], 20.0)       # the turn phase only: 8 agent-turns of 20 ms, the start-up not in it (the window of turns_per_s)
        self.assertAlmostEqual(out["start_cpu_ms_per_agent"], 300.0)     # first start to last ready, per agent
        self.assertGreater(out["turns_per_s"], 0)
        self.assertTrue(out["latency_ms_p50"] <= out["latency_ms_p95"] <= out["latency_ms_max"])
        self.assertNotIn("stop_cause", out)

    def test_start_up_cpu_is_not_in_the_cpu_per_agent_turn_and_is_its_own_field(self):
        self.runtime(cpu_usec=2_000_000, cpu_per_prompt_usec=30_000)       # a heavy start (2 s of CPU per agent), light turns (30 ms)
        self.policy()
        out = scale.probe(self.ctx(scale_turns=3), self.arm(), 4, "agents")
        self.assertAlmostEqual(out["cpu_ms"], 4 * 2000 + 12 * 30)                         # the whole sample still holds both
        self.assertAlmostEqual(out["cpu_ms_per_agent_turn"], 30.0)                        # the same window as turns_per_s: the turn phase
        self.assertAlmostEqual(out["start_cpu_ms_per_agent"], 2000.0)

    def test_a_print_sample_has_no_start_up_field_and_its_cpu_per_task_is_the_whole_sample(self):
        self.runtime(cpu_usec=500_000)
        self.policy()
        out = scale.probe(self.ctx(), self.arm(), 4, "print")
        self.assertNotIn("start_cpu_ms_per_agent", out)
        self.assertAlmostEqual(out["cpu_ms_per_agent_turn"], out["cpu_ms"] / 4)            # one task per agent
        self.assertAlmostEqual(out["cpu_ms_per_agent_turn"], 500.0)

    def test_the_mock_workers_cpu_is_recorded_and_the_flag_follows_their_capacity(self):
        self.runtime()
        self.policy(busy=0.1, k=4)
        out = scale.probe(self.ctx(scale_turns=2), self.arm(), 3, "agents")
        self.assertEqual((out["mock_workers"], out["mock_saturated"]), (4, False))
        self.assertAlmostEqual(out["mock_cores"], 0.4, delta=0.05)                    # 4 workers at 10% of a CPU each
        self.assertAlmostEqual(out["mock_worker_max"], 0.1, delta=0.02)
        self.assertGreater(out["mock_cpu_ms"], 0)
        self.assertIn("runner_cpu_ms", out)
        self.runtime()
        self.policy(busy=0.95, k=4)
        self.assertTrue(scale.probe(self.ctx(scale_turns=1), self.arm(), 2, "agents")["mock_saturated"])      # 3.8 of 4 CPUs
        self.runtime()
        self.policy(busy=0.1, hot=0.97, k=4)
        out = scale.probe(self.ctx(scale_turns=1), self.arm(), 2, "agents")
        self.assertTrue(out["mock_saturated"])                                           # one worker full, the others idle
        self.assertLess(out["mock_cores"], 0.9 * 4)

    def test_the_sample_starts_the_mock_on_its_own_socket_and_hands_its_requests_to_the_log_after_the_container_is_gone(self):
        rt = self.runtime()
        self.policy()
        ctx = self.ctx(scale_turns=1)
        ctx.server.sink = object()
        scale.probe(ctx, self.arm(), 2, "agents")
        self.assertEqual(sorted(self.mock.policies[0]), [0, 1])                           # the projects of the two agents
        self.assertIn(f"source={self.mock.path}", " ".join(rt.argvs[0]))                  # the container's one socket is the workers'
        self.assertEqual(len(self.mock.flushed), 1)
        self.assertIs(self.mock.flushed[0][1], ctx.server.sink)

    def test_the_stage_timeout_defaults_to_120_seconds(self):
        self.assertEqual(scale.STAGE_TIMEOUT, 120.0)

    def test_the_launchers_cpu_is_subtracted_from_the_containers(self):
        rt = self.runtime()
        self.policy()
        replies = iter([10.0, 20.0, 35.0])   # before the first start, when the last agent is ready, at the end
        orig = self.Swarm.relay_cpu_ms
        self.Swarm.relay_cpu_ms = lambda self, timeout=20: next(replies)
        self.addCleanup(setattr, self.Swarm, "relay_cpu_ms", orig)
        out = scale.probe(self.ctx(scale_turns=1), self.arm(), 1, "agents")
        self.assertAlmostEqual(out["launcher_cpu_ms"], 25.0)
        self.assertAlmostEqual(out["cpu_ms"], 300 + 20 - 25.0)
        self.assertAlmostEqual(out["start_cpu_ms_per_agent"], 300 - 10.0)                  # each window loses the launcher's own CPU of that window
        self.assertAlmostEqual(out["cpu_ms_per_agent_turn"], 20 - 15.0)
        self.assertGreaterEqual(len(rt.argvs), 1)

    def test_every_agent_gets_its_own_start_and_the_work_is_checked_on_disk(self):
        rt = self.runtime()
        self.policy(offered={"read", "write", "shell"})
        ctx = self.ctx(scale_turns=2)

        def write(agent, turn):
            for i, h in ctx.made.items():   # the agent's project directory, from its argv's id
                pass
            cwd = agent["cwd"]
            with open(os.path.join(cwd, SWARM_FILE.format(turn=turn)), "w") as f:
                f.write("x")
        rt.k["write_files"] = write
        out = scale.probe(ctx, self.arm(), 3, "agents")
        self.assertEqual((out["agents_ok"], "failure" in out), (3, False))
        starts = [c for c in rt.commands if c["op"] == "start"]
        self.assertEqual(sorted(c["id"] for c in starts), [0, 1, 2])
        self.assertEqual(len({c["cwd"] for c in starts}), 3)                         # a project directory each
        self.assertEqual(len({c["home"] for c in starts}), 3)
        self.assertTrue(all(c["seed"].startswith(swarmlib.SEED_IN_CONTAINER + "/") for c in starts))
        prompts = [c for c in rt.commands if c["op"] == "send" and '"prompt"' in c["data"]]
        self.assertEqual(len(prompts), 6)                                            # 3 agents x 2 turns

    def test_an_agent_that_did_not_write_its_file_fails_the_probe_as_an_error(self):
        self.runtime()
        self.policy(offered={"write"})
        out = scale.probe(self.ctx(scale_turns=1), self.arm(), 2, "agents")
        self.assertEqual((out["agents_ok"], out["stop_cause"]), (0, "error"))
        self.assertIn("2 of 2 agents did not write their file", out["failure"])

    def test_a_clean_print_probe_reports_makespan_and_wall_percentiles(self):
        self.runtime()
        self.policy()
        out = scale.probe(self.ctx(), self.arm(), 4, "print")
        self.assertNotIn("failure", out)
        self.assertEqual((out["agents"], out["agents_ok"]), (4, 4))
        for key in ("makespan_ms", "wall_ms_p50", "wall_ms_p95", "turns_per_s", "cpu_ms_per_agent_turn", "mem_per_agent_mib", "mem_peak_mib"):
            self.assertIsNotNone(out[key], key)
        self.assertAlmostEqual(out["wall_ms_p50"], 20.0)
        self.assertNotIn("latency_ms_p50", out)
        self.assertNotIn("ready_ms", out)

    def test_print_agents_that_exit_zero_without_the_reply_fail_the_probe_and_the_text_says_what_the_mock_saw(self):
        self.runtime(no_reply={1, 2}, undrained={3})
        self.policy(offered={"read", "shell"})                      # no write step: no file to look for
        self.mock.requests_seen = {0: 3, 1: 3, 2: 3, 3: 3}
        out = scale.probe(self.ctx(), self.arm(), 4, "print")
        self.assertEqual((out["agents_ok"], out["stop_cause"]), (1, "error"))
        self.assertIn("3 agents exited 0 without finishing the task: no final reply on their output (2 wrote nothing to their output, 1 had output the launcher had not finished reading); "
                      "the mock saw 3 requests from each of them (a whole task is 3)", out["failure"])
        self.assertNotIn("exit 0", out["failure"].replace("exited 0", ""))     # not reported twice as a plain exit
        self.assertEqual(race.stop_cause(out)["cause"], race.ERROR)

    def test_exit_zero_agents_the_mock_saw_part_of_are_reported_with_the_range(self):
        self.runtime(no_reply={0, 1})
        self.policy(offered={"read", "write", "shell"})
        self.mock.requests_seen = {0: 1, 1: 3}
        out = scale.probe(self.ctx(), self.arm(), 2, "print")
        self.assertIn("the mock saw 1 to 3 requests from them (a whole task is 4)", out["failure"])

    def test_the_kernels_oom_kill_stops_the_probe_and_names_the_cause(self):
        self.runtime(oom_at=5, limit=1024 * MIB, mem_per_agent=300 * MIB)
        self.policy()
        out = scale.probe(self.ctx(scale_turns=1), self.arm(), 8, "agents")
        self.assertEqual(out["stop_cause"], "oom")
        self.assertIn(out["oom_kills"], (1, 2, 3))   # agents 5, 6 and 7 are killed; the probe stops at the first kill it sees, so how many are counted depends on how far the fake runtime got by then
        self.assertEqual(out["agents_ok"], 0)
        self.assertIn(f"out of memory: the kernel's OOM killer stopped {out['oom_kills']} processes", out["failure"])
        self.assertIn("3 agents exited (signal 9", out["failure"])
        self.assertEqual(race.stop_cause(out)["cause"], race.OOM)
        self.assertEqual(out["mem_peak_mib"], 1024.0)

    def test_a_probe_ends_at_the_first_oom_kill_without_waiting_for_the_timeout_and_the_container_is_killed(self):
        rt = self.runtime(kill_at=3, no_ready={2, 3, 4, 5}, limit=1024 * MIB, mem_per_agent=200 * MIB)   # the survivors would wait for the 30 s stage timeout
        self.policy()
        t0 = time.monotonic()
        out = scale.probe(self.ctx(scale_stage_timeout=30, scale_turns=1, swarm_memory_gib=1), self.arm(), 6, "agents")
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual(out["stop_cause"], "oom")
        self.assertEqual(out["oom_kills"], 1)
        self.assertEqual(len(rt.killed), 1)                                                              # `docker kill <name>` (the fake runtime writes no container id)
        self.assertEqual(rt.killed[0][:2], ["docker", "kill"])
        self.assertNotIn("never answered", out["failure"])                                               # agents that were not given the time are not counted against the rung
        self.assertIn("the kernel's OOM killer stopped 1 processes", out["failure"])
        self.assertNotIn("the swarm container exited", out["failure"])                                   # we killed it: it did not exit by itself
        self.assertEqual(race.stop_cause(out)["cause"], race.OOM)
        self.assertGreater(out["mem_peak_mib"], 0)                                                       # the readings were taken before the kill

    def test_an_oom_kill_ends_a_print_probe_at_once_too(self):
        rt = self.runtime(kill_at=2, hang={0, 1, 2}, limit=1024 * MIB)                                   # three agents that would run to the timeout
        self.policy()
        t0 = time.monotonic()
        out = scale.probe(self.ctx(scale_stage_timeout=30, swarm_memory_gib=1), self.arm(), 3, "print")
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual((out["stop_cause"], out["oom_kills"]), ("oom", 1))
        self.assertEqual(len(rt.killed), 1)

    def test_a_container_at_its_limit_with_no_progress_and_nothing_killed_is_a_stall(self):
        rt = self.runtime(thrash_after=3, no_ready={2, 3, 4, 5}, limit=1024 * MIB, mem_per_agent=400 * MIB)
        self.policy()
        t0 = time.monotonic()
        out = scale.probe(self.ctx(scale_stage_timeout=30, scale_stall_s=0.4, scale_turns=1, swarm_memory_gib=1), self.arm(), 6, "agents")
        took = time.monotonic() - t0
        self.assertGreaterEqual(took, 0.4)
        self.assertLess(took, 5)                                                                         # not the 30 s timeout
        self.assertEqual(out["stop_cause"], "stall")
        self.assertEqual(out["oom_kills"], 0)
        self.assertIn("stalled at the limit, nothing killed", out["failure"])
        self.assertNotIn("never answered", out["failure"])
        self.assertEqual(race.stop_cause(out)["cause"], race.STALL)
        self.assertEqual(len(rt.killed), 1)

    def test_hits_at_the_limit_while_agents_make_progress_are_not_a_stall(self):
        self.runtime(thrash_after=1, limit=1024 * MIB, mem_per_agent=100 * MIB)
        self.policy()
        out = scale.probe(self.ctx(scale_stage_timeout=30, scale_stall_s=0.3, scale_turns=1, swarm_memory_gib=1), self.arm(), 4, "agents")
        self.assertNotIn("failure", out)

    def test_idle_time_below_the_limit_is_not_a_stall(self):
        self.runtime(thrash_after=1, no_ready={0}, mem_per_agent=10 * MIB)                          # counters rise, but the container is far from its limit
        self.policy()
        out = scale.probe(self.ctx(scale_stage_timeout=1.5, scale_stall_s=0.3, scale_turns=1, swarm_memory_gib=1), self.arm(), 2, "agents")
        self.assertEqual(out["stop_cause"], "timeout")

    def test_the_stall_time_defaults_to_10_seconds(self):
        self.assertEqual(scale.STALL_S, 10.0)
        self.assertIn("stall", scale.STOP_CAUSES)
        self.assertEqual(scale.classify(0, 0, False, True), "stall")
        self.assertEqual(scale.classify(2, 0, False, True), "oom")                                       # a kill that landed while the stall was being seen wins

    def test_a_container_the_kernel_killed_with_its_cgroup_is_an_oom_from_the_last_reading(self):
        seen, read = threading.Event(), swarmlib.read_cgroup

        def watch(path):   # the monitor's read: the container dies only after a reading whose peak is at its limit, as a real kill follows the counters reaching it
            got = read(path)
            if got and (got.get("memory.peak") or 0) >= 1024 * MIB:   # the peak, not memory.current: the fake writes the two files one after the other
                seen.set()
            return got
        patcher = mock.patch.object(swarmlib, "read_cgroup", watch)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.runtime(die_at=3, die_when=seen, limit=1024 * MIB, mem_per_agent=400 * MIB)
        self.policy()
        out = scale.probe(self.ctx(scale_turns=1, swarm_memory_gib=1), self.arm(), 8, "agents")
        self.assertEqual(out["stop_cause"], "oom")
        self.assertEqual(out["mem_peak_mib"], 1024.0)               # the newest reading before the cgroup went with the container
        self.assertIn("the swarm container exited (exit 137): killed at 1024 of 1024 MiB, out of memory", out["failure"])
        self.assertEqual(race.stop_cause(out)["cause"], race.OOM)

    def test_an_oom_in_print_mode_is_an_oom_too(self):
        self.runtime(oom_at=2, limit=1024 * MIB)
        self.policy()
        out = scale.probe(self.ctx(), self.arm(), 4, "print")
        self.assertEqual((out["stop_cause"], out["agents_ok"]), ("oom", 2))
        self.assertGreaterEqual(out["oom_kills"], 1)

    def test_agents_that_never_answer_are_a_timeout_when_the_kernel_counted_nothing(self):
        self.runtime(no_ready={1, 2})
        self.policy()
        out = scale.probe(self.ctx(scale_stage_timeout=0.3), self.arm(), 4, "agents")
        self.assertEqual(out["stop_cause"], "timeout")
        self.assertIn("2 of 4 agents never answered get_state", out["failure"])
        self.assertEqual((out["agents_ok"], out["oom_kills"]), (0, 0))

    def test_silent_agents_in_a_turn_are_a_timeout(self):
        self.runtime(mute={0})
        self.policy()
        out = scale.probe(self.ctx(scale_stage_timeout=0.3, scale_turns=2), self.arm(), 3, "agents")
        self.assertEqual(out["stop_cause"], "timeout")
        self.assertIn("1 of 3 agents did not answer a prompt", out["failure"])

    def test_refused_forks_are_a_pids_stop(self):
        self.runtime(pids_block=True)
        self.policy()
        out = scale.probe(self.ctx(scale_stage_timeout=0.5), self.arm(), 2, "agents")
        self.assertEqual(out["stop_cause"], "pids")
        self.assertIn("process limit", out["failure"])

    def test_a_container_that_does_not_start_is_an_error_with_the_runtimes_words(self):
        self.runtime(dont_start=True)
        self.policy()
        scale.swarmlib.Swarm = lambda cfg: self.Swarm(cfg, popen=self.rt.popen, poll_s=0.002, sleep=lambda s: None)
        out = scale.probe(self.ctx(), self.arm(), 1, "agents")
        self.assertEqual(out["stop_cause"], "error")
        self.assertIn("did not start", out["failure"])

    def test_the_container_is_removed_after_the_sample_and_no_agent_ran_outside_it(self):
        rt = self.runtime()
        self.policy()
        scale.probe(self.ctx(scale_turns=1), self.arm(), 2, "agents")
        self.assertTrue(any(a[:3] == ["docker", "rm", "-f"] for a in rt.removed))
        self.assertEqual(len(rt.argvs), 1)    # one container; every agent was a command to its relay, never a process of the runner

    def test_the_swarm_needs_the_container_envelope_and_its_cpus_never_overlap_the_mocks(self):
        self.runtime()
        self.policy()
        cgroup.CONTAINER = None
        with self.assertRaises(scale.Skip) as why:
            scale.probe(self.ctx(), self.arm(), 1, "agents")
        self.assertIn("--isolation container", str(why.exception))
        cgroup.CONTAINER = self.saved[1] or ContainerConfig(image=DIGEST, runtime="docker", cpuset_cpus=[2], cpuset_mems="0", memory_mib=1024, ro_paths=[], rw_dir=self.tmp, socket_path="s.sock", mock_port=1, relay_dir=self.tmp)
        with self.assertRaises(scale.Skip) as why:
            scale.probe(self.ctx(swarm_cpus="5-6"), self.arm(), 1, "agents")
        self.assertIn("mock's CPUs", str(why.exception))

    def test_the_parameters_set_the_envelope(self):
        self.runtime()
        self.policy()
        out = scale.probe(self.ctx(scale_turns=1, swarm_memory_gib=2, swarm_cpus="2-3"), self.arm(), 1, "agents")
        self.assertEqual(out["swarm"], {"memory_mib": 2048, "cpus": [2, 3], "pids_max": swarmlib.pids_limit(1)})
        out = scale.probe(self.ctx(scale_turns=1, swarm_pids=500), self.arm(), 1, "agents")
        self.assertEqual(out["swarm"]["pids_max"], 500)

    def test_the_samples_pass_the_raw_format_check(self):
        from buffon.runner import raw
        self.runtime()
        self.policy()
        out = scale.probe(self.ctx(scale_turns=1), self.arm(), 2, "agents")
        raw.check_sample(dict(out, arm="a", scenario="scale/agents-limit", api=None, round=0, warmup=False), "sample")


class Defaults(unittest.TestCase):
    """The scale family takes 5 rounds and has no A/A copy unless the operator says otherwise; every other workload keeps the run's rounds and the copies."""

    def run_plan(self, **kw):
        ws = [workloads.Workload(id=f"scale/{k}-limit", family="scale", fn=lambda ctx, arm: {"agents_limit": 1}, apis=(None,), rounds=scale.ROUNDS, aa=False) for k in ("agents", "print")]
        ws.append(workloads.Workload(id="x/one", family="x", fn=lambda ctx, arm: {"v": 1}, apis=(None,)))
        plan = engine.Plan(workloads=ws, arms=[], out=tempfile.mkdtemp(), warmup=0, allow_short=True, **kw)
        r = engine.Runner(plan, log=lambda *_: None)
        r.isolation = {}
        mk = lambda i, twin=None: types.SimpleNamespace(id=i, twin_of=twin, apis=["openai-completions"], label=i, supports_api=lambda api: True)
        r.measure(FakeCtx(), [mk("a"), mk("a-b", "a")])
        counts = {}
        for x in r.samples:
            counts[(x["scenario"], x["arm"])] = counts.get((x["scenario"], x["arm"]), 0) + 1
        return plan, counts

    def test_scale_gets_5_rounds_and_no_copy_while_a_serial_workload_keeps_12_and_its_copy(self):
        plan, counts = self.run_plan(rounds=12, rounds_set=False, aa="all", aa_set=False)
        self.assertEqual(counts, {("scale/agents-limit", "a"): 5, ("scale/print-limit", "a"): 5, ("x/one", "a"): 12, ("x/one", "a-b"): 12})
        self.assertEqual(plan.aa_effective, "all")

    def test_an_explicit_rounds_and_an_explicit_aa_win(self):
        _plan, counts = self.run_plan(rounds=8, rounds_set=True, aa="all", aa_set=True)
        self.assertEqual(counts, {("scale/agents-limit", "a"): 8, ("scale/agents-limit", "a-b"): 8, ("scale/print-limit", "a"): 8, ("scale/print-limit", "a-b"): 8, ("x/one", "a"): 8, ("x/one", "a-b"): 8})

    def test_fewer_rounds_than_5_are_honoured_without_the_flag_being_explicit(self):
        _plan, counts = self.run_plan(rounds=3, rounds_set=False, aa="all", aa_set=False)
        self.assertEqual(counts[("scale/agents-limit", "a")], 3)

    def test_a_scale_only_plan_installs_no_copy_and_is_not_provisional_for_it(self):
        reg = workloads.load_all()
        ws = [reg["scale/agents-limit"]]
        plan = engine.Plan(workloads=ws, arms=[], aa="all", aa_set=False)
        self.assertEqual(plan.aa_effective, "none")
        a = types.SimpleNamespace(id="a", twin_of=None)
        self.assertEqual([r for r in engine.run_reasons(plan, [a], [a], {"mode": "proc"}, {}) if "A/A" in r], [])
        explicit = engine.Plan(workloads=ws, arms=[], aa="none", aa_set=True)
        self.assertTrue([r for r in engine.run_reasons(explicit, [a], [a], {"mode": "proc"}, {}) if "A/A" in r])   # --aa none by hand still says so

    def test_the_scale_workloads_carry_the_defaults(self):
        for wid, w in workloads.load_all().items():
            if wid.startswith("scale/"):
                self.assertEqual((w.rounds, w.aa), (5, False), wid)
            elif wid.startswith("durable/"):   # the durable family declares its own rounds and A/A defaults in buffon/durable/specs.py
                continue
            else:
                self.assertEqual((w.rounds, w.aa), (0, True), wid)

    def test_the_command_line_leaves_rounds_and_aa_open_until_given(self):
        from buffon import cli
        parsed = cli.build_parser().parse_args(["run", "scale"])
        self.assertEqual((parsed.rounds, parsed.aa), (None, None))
        given = cli.build_parser().parse_args(["run", "scale", "--rounds", "12", "--aa", "all"])
        self.assertEqual((given.rounds, given.aa), (12, "all"))

    def test_the_realised_rounds_of_a_run_leave_the_scale_searches_out(self):
        from buffon import trust
        samples = [{"scenario": "x/one", "api": None, "round": r} for r in range(12)] + [{"scenario": "scale/agents-limit", "api": None, "round": r} for r in range(5)]
        self.assertEqual(trust.realised_rounds({"samples": samples}), 12)


class UpPlan(unittest.TestCase):
    """`buffon up`: the selection's rounds reach the run only when chosen, and the plan states a modelled time for the scale searches."""

    def test_rounds_are_passed_to_the_run_only_when_chosen(self):
        from buffon.up import flow, selection
        opts = types.SimpleNamespace(python="py", dedicated=False, require_class="")
        paths = {"site_profile": "s", "cache": "c", "npm_cache": "n"}
        sel = selection.Selection(harnesses=["pi-node"], workloads=["scale/agents-limit"], apis=["openai-completions"])
        arms = {}
        argv = flow.run_argv(opts, paths, sel, ["pi-node"], "pi-node", ["scale/agents-limit"], "out", arm_objs=arms)
        self.assertNotIn("--rounds", argv)
        argv = flow.run_argv(opts, paths, sel.clone(rounds=9, rounds_set=True), ["pi-node"], "pi-node", ["scale/agents-limit"], "out", arm_objs=arms)
        self.assertEqual(argv[argv.index("--rounds") + 1], "9")

    def test_a_saved_selection_keeps_the_rounds_only_when_chosen(self):
        from buffon.up import selection
        sel = selection.Selection(harnesses=["pi-node"], workloads=["scale/agents-limit"], spec="scale/agents-limit", apis=["openai-completions"])
        self.assertNotIn("\nrounds = ", selection.dumps(sel))
        self.assertFalse(selection.loads(selection.dumps(sel)).rounds_set)
        chosen = selection.loads(selection.dumps(sel.clone(rounds=7, rounds_set=True)))
        self.assertEqual((chosen.rounds, chosen.rounds_set), (7, True))

    def test_the_estimate_follows_the_model_and_the_note_says_what_it_is_made_of(self):
        from buffon.up import catalog, estimate, selection
        probe = {"speed": 1.0}
        nine = ["pi-node", "pig-tip", "pibolt", "pi-bun", "pig-0.4.1", "rpi", "opencode-v2", "copilot", "claude-code"]
        ids = [w for w in workloads.load_all() if w.startswith("scale/")]
        self.assertEqual(sorted(ids), sorted(catalog.SCALE_IDS))
        sel = selection.Selection(harnesses=nine, workloads=ids, spec="scale", apis=["openai-completions"], isolation="container")
        est = estimate.estimate(sel, probe)
        scale_s = sum(v for k, v in est["per_workload"].items() if k.startswith("scale/"))
        self.assertTrue(10 * 60 < scale_s < 6 * 3600, scale_s)   # a model: 9 harnesses, four searches, 6 rounds
        more = estimate.estimate(sel.clone(rounds=12, rounds_set=True), probe)
        self.assertGreater(sum(v for k, v in more["per_workload"].items() if k.startswith("scale/")), 1.2 * scale_s)   # an explicit --rounds 12 takes 7 expected (adaptive) instead of 5
        note = estimate.scale_note(sel, est)
        for text in ("a model", "4 GiB and 8 CPUs", "6 searches", "no A/A copy", "first OOM kill", "10 s", "bisects", "ten-extension searches use the plain timings"):
            self.assertIn(text, note)
        big = estimate.scale_note(sel.clone(memory_tier_gib=8, params={"swarm_cpus": "0-15"}), est)
        self.assertIn("8 GiB and 16 CPUs", big)
        self.assertIn("scaled to 8 GiB and 16 CPUs", big)
        self.assertEqual(estimate.scale_note(selection.from_preset("quick"), est), "")

    def test_only_harnesses_that_load_pi_extensions_and_have_the_mode_count_for_the_extension_searches(self):
        from buffon.up import catalog, estimate
        arms = estimate._arms()
        names = list(arms)
        plain = catalog.scale_harness_count("scale/print-limit", names, arms)
        ext = catalog.scale_harness_count("scale/print-ext10", names, arms)
        self.assertEqual(ext, sum(1 for n in names if arms[n].supports_mode("print") and arms[n].pi_extensions in ("native", "sidecar")))
        self.assertLess(ext, plain)

    def test_a_search_costs_more_with_a_finer_resolution_and_less_with_a_lower_cap(self):
        from buffon.up import catalog
        exact, coarse = catalog.scale_search("agents"), catalog.scale_search("agents", resolution=64)
        capped = catalog.scale_search("agents", cap=64)
        self.assertGreater(exact, coarse)
        self.assertGreater(coarse, capped)


if __name__ == "__main__":
    unittest.main()
