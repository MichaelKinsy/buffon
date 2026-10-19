# SPDX-License-Identifier: Apache-2.0
"""The pieces the swarm benchmark stands on: the scripted model's work for one agent's turn, the raw-format check of the swarm field, the up wiring that selects a ladder by name, and the direction of the
swarm's metrics."""
import tempfile
import types
import unittest

from buffon.mock import REPLY, swarm_policy
from buffon.mock.server import Request, swarm_marker
from buffon.report import cells
from buffon.runner import raw
from buffon.up import selection
from buffon import workloads


def request(prompt_text, tools, rounds=0, protocol="openai-completions"):
    """A chat-completions request whose user message is `prompt_text`, after `rounds` tool results."""
    messages = [{"role": "system", "content": "a very long system prompt " * 50}, {"role": "user", "content": prompt_text}]
    for k in range(rounds):
        messages += [{"role": "assistant", "content": None, "tool_calls": [{"id": f"c{k}"}]}, {"role": "tool", "content": "result"}]
    body = {"messages": messages, "tools": [{"type": "function", "function": {"name": n, "parameters": p}} for n, p in tools.items()]}
    return Request(0, protocol, body, 100, 0)


PI_TOOLS = {"read": {"properties": {"path": {}}}, "write": {"properties": {"path": {}, "content": {}}}, "bash": {"properties": {"command": {"type": "string"}}}, "edit": {"properties": {"path": {}}}}


class Policy(unittest.TestCase):
    def test_a_turn_is_a_read_a_write_a_shell_command_and_then_the_answer(self):
        p = swarm_policy({3: "/w/a3/project", 4: "/w/a4/project"})
        prompt = "[agent 3 turn 1] do the work"
        steps = [p(request(prompt, PI_TOOLS, rounds=r)) for r in range(4)]
        names = [s.tool_calls[0][0] if s.tool_calls else None for s in steps]
        self.assertEqual(names, ["read", "write", "bash", None])
        self.assertEqual(steps[0].tool_calls[0][1], {"path": "/w/a3/project/README.md"})
        self.assertEqual(steps[1].tool_calls[0][1], {"path": "/w/a3/project/swarm-turn-1.txt", "content": "agent 3 turn 1\n"})
        self.assertEqual(steps[2].tool_calls[0][1], {"command": "wc -c /w/a3/project/README.md"})
        self.assertEqual(steps[3].text, REPLY)
        self.assertEqual(p.offered, {"read", "write", "shell"})

    def test_each_agent_is_sent_to_its_own_project_by_the_marker_in_its_prompt(self):
        p = swarm_policy({3: "/w/a3/project", 4: "/w/a4/project"})
        self.assertEqual(p(request("[agent 4 turn 0] go", PI_TOOLS)).tool_calls[0][1], {"path": "/w/a4/project/README.md"})
        self.assertEqual(swarm_marker(request("[agent 12 turn 2] go", PI_TOOLS)), (12, 2))
        self.assertIsNone(swarm_marker(request("no marker here", PI_TOOLS)))

    def test_a_request_without_tools_or_without_a_known_agent_gets_text(self):
        p = swarm_policy({1: "/w/a1/project"})
        self.assertIn("Summary", p(request("[agent 1 turn 0] x", {})).text)
        self.assertEqual(p(request("[agent 9 turn 0] x", PI_TOOLS)).text, REPLY)

    def test_the_policy_remembers_the_shortest_tool_list_any_request_declared_for_the_extension_check(self):
        p = swarm_policy({1: "/w/a1/project"})
        self.assertIsNone(p.fewest_tools[0])
        more = dict(PI_TOOLS, **{f"bench_tool_{k:02d}": {"properties": {}} for k in range(1, 11)})
        p(request("[agent 1 turn 0] x", more))
        p(request("[agent 1 turn 0] x", PI_TOOLS, rounds=1))
        p(request("[agent 1 turn 0] x", {}))                       # a summary request carries no tools and does not count
        self.assertEqual(p.fewest_tools[0], 4)
        self.assertEqual(swarm_policy({1: "/w/a1/project"}).fewest_tools[0], None)   # a new sample starts again

    def test_a_harness_without_a_write_tool_skips_that_step_and_the_policy_says_what_it_offered(self):
        p = swarm_policy({1: "/w/a1/project"})
        tools = {"Read": {"properties": {"file_path": {}}}, "Bash": {"properties": {"command": {"type": "string"}}}}
        names = [p(request("[agent 1 turn 0] x", tools, rounds=r)).tool_calls[0][0] if r < 2 else p(request("[agent 1 turn 0] x", tools, rounds=r)).text for r in range(3)]
        self.assertEqual(names, ["Read", "Bash", REPLY])
        self.assertEqual(p.offered, {"read", "shell"})

    def test_the_marker_is_found_in_the_anthropic_and_responses_shapes_too(self):
        body = {"messages": [{"role": "user", "content": [{"type": "text", "text": "<system-reminder>x</system-reminder>"}, {"type": "text", "text": "[agent 2 turn 0] go"}]}], "tools": []}
        self.assertEqual(swarm_marker(Request(0, "anthropic-messages", body, 1, 0)), (2, 0))
        body = {"input": [{"role": "user", "content": [{"type": "input_text", "text": "[agent 5 turn 1] go"}]}], "tools": []}
        self.assertEqual(swarm_marker(Request(0, "openai-responses", body, 1, 0)), (5, 1))


class HomeRoot(unittest.TestCase):
    def test_a_swarm_harness_keeps_its_home_under_the_homes_root_and_the_rest_under_the_work_directory(self):
        import os
        from buffon.runner.harness import Harness
        with tempfile.TemporaryDirectory() as work:
            homes = os.path.join(work, "swarm-homes")
            a = types.SimpleNamespace(id="x", env={"PI_OFFLINE": "1"}, spec={"state": {"dirs": []}}, path_dirs=[], writer_path=lambda: None)
            server = types.SimpleNamespace(base_url="http://127.0.0.1:1/v1", origin="http://127.0.0.1:1")
            saved = Harness.__init__.__globals__["load_writer"]
            Harness.__init__.__globals__["load_writer"] = lambda arm: (lambda spec: {})
            try:
                h = Harness(a, work, server, tag="a3", home_root=homes)
            finally:
                Harness.__init__.__globals__["load_writer"] = saved
            self.assertTrue(h.home.startswith(homes + os.sep))
            self.assertEqual(h.env["HOME"], h.home)
            self.assertTrue(h.disk.startswith(work + os.sep) and not h.disk.startswith(homes + os.sep))   # runtime code and caches stay on the disk mount
            self.assertTrue(os.path.isdir(h.cwd))
            h.cleanup()
            self.assertFalse(os.path.exists(os.path.dirname(h.home)) or os.path.exists(os.path.dirname(h.disk)))


class Raw(unittest.TestCase):
    base = {"arm": "a", "scenario": "scale/agents-limit", "api": None, "round": 0, "warmup": False}

    def test_the_swarm_field_is_a_nested_object_the_check_accepts(self):
        raw.check_sample(dict(self.base, swarm={"memory_mib": 1024, "cpus": [40, 41], "pids_max": 1152}, agents=2, mock_saturated=False), "s")

    def test_a_malformed_swarm_field_is_rejected(self):
        for bad in ({"memory_mib": 1024, "cpus": [40]}, {"memory_mib": 0, "cpus": [1], "pids_max": 5}, {"memory_mib": 1024, "cpus": [], "pids_max": 5}, {"memory_mib": 1024, "cpus": ["1"], "pids_max": 5}, "x"):
            with self.assertRaises(raw.RawError):
                raw.check_sample(dict(self.base, swarm=bad), "s")


class Wiring(unittest.TestCase):
    def test_the_family_name_selects_the_four_search_workloads_in_up_and_run(self):
        names, preset = selection.parse_benches("scale")
        self.assertEqual((sorted(names), preset), (["scale/agents-ext10", "scale/agents-limit", "scale/print-ext10", "scale/print-limit"], ""))
        self.assertEqual(sorted(w.id for w in workloads.resolve(["scale"])), sorted(names))
        self.assertEqual(selection.parse_benches("scale/agents-limit,scale/print-ext10")[0], ["scale/agents-limit", "scale/print-ext10"])

    def test_up_takes_params_and_passes_them_to_the_run_the_way_run_does(self):
        from buffon import cli
        from buffon.up import flow
        args = cli.build_parser().parse_args(["up", "--harness", "pi-node", "--bench", "scale/agents-limit", "--param", "swarm_max_agents=64", "--param", "swarm_cpus=40-47", "--param", "swarm_memory_gib=1", "--plan", "--yes"])
        sel = cli.build_selection(args)
        self.assertEqual(sel.params, {"swarm_max_agents": 64, "swarm_cpus": "40-47", "swarm_memory_gib": 1})
        text = selection.command(sel)
        self.assertIn("--param swarm_cpus=40-47 --param swarm_max_agents=64 --param swarm_memory_gib=1", text)
        again = selection.loads(selection.dumps(sel))                       # a saved selection keeps them
        self.assertEqual(again.params, sel.params)
        plans = [(n, ids, dict(sel.params), None) for n, ids in flow.groups(sel.workloads, workloads.load_all())]
        opts = types.SimpleNamespace(python="python3", dedicated=False, require_class=None)
        argv = flow.run_argv(opts, {"site_profile": "s.toml", "cache": "c", "npm_cache": "n"}, sel, ["pi-node"], "pi-node", plans[0][1], "out", plans[0][2], {})
        self.assertIn("swarm_max_agents=64", argv)
        self.assertIn('swarm_cpus="40-47"', argv)
        from buffon.cli import parse_params
        self.assertEqual(parse_params(['swarm_cpus="40-47"', "swarm_max_agents=64"]), {"swarm_cpus": "40-47", "swarm_max_agents": 64})

    def test_turns_per_second_is_scored_and_higher_is_better(self):
        self.assertTrue(cells.scored("turns_per_s"))
        self.assertEqual((cells.direction("turns_per_s"), cells.direction("latency_ms_p95")), ("higher", "lower"))
        for lower in ("mem_per_agent_mib", "mem_peak_mib", "pss_mib_per_agent", "cpu_ms_per_agent_turn", "latency_ms_p50", "latency_ms_p95", "latency_ms_max", "ready_ms", "makespan_ms", "wall_ms_p95"):
            self.assertTrue(cells.scored(lower), lower)
        for context in ("mock_cpu_ms", "mem_baseline_mib", "oom_kills", "pids_peak", "agents", "agents_ok", "throttled_periods"):
            self.assertFalse(cells.scored(context), context)

    def test_more_is_a_win_for_a_higher_is_better_metric(self):
        ci = (1.2, 1.6)
        self.assertTrue(cells.classify(1.4, ci, 0.05, 0.001, higher=True).startswith("win"))
        self.assertTrue(cells.classify(1.4, ci, 0.05, 0.001).startswith("loss"))


if __name__ == "__main__":
    unittest.main()
