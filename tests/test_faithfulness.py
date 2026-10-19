# SPDX-License-Identifier: Apache-2.0
import http.client
import json
import os
import sys
import tempfile
import types
import unittest

from buffon import mock
from buffon.faithfulness import canon, lab as labmod, probes, report, score, wire

HELP = """pi - AI coding assistant

Usage:
  pi [options] [--] [@files...] [messages...]

Commands:
  pi install <source> [-l]     Install extension source
  pi list                      List installed extensions
  pi <command> --help          Show help

Options:
  --provider <name>              Provider to search for --model
  --print, -p                    Non-interactive mode
  --name, -n <name>              Set session display name
  --list-models [search]         List available models
  --no-tools, -nt                Disable all tools
  --                             End option parsing
  --help, -h                     Show this help
"""


class Normalizing(unittest.TestCase):
    def norm(self):
        return canon.Normalizer([("/tmp/buffon-x/work/proj", "<cwd>"), ("/tmp/buffon-x/work/home/.agent", "<agent>"), ("/tmp/buffon-x/work/home", "<home>")], ["pig", "PiG"], "0.4.1", 4242)

    def test_paths_names_ids_dates_and_ports_become_placeholders(self):
        n = self.norm()
        text = "pig 0.4.1 at /tmp/buffon-x/work/proj/.pig/x, agent /tmp/buffon-x/work/home/.agent, http://127.0.0.1:4242/v1, PiG docs, 2026-10-11T18:00:00Z id call_80_0 uuid 123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(n.text(text), "<bin> <version> at <cwd>/.<bin>/x, agent <agent>, http://127.0.0.1:<port>/v1, <bin> docs, <date> id <id> uuid <uuid>")

    def test_a_longer_path_wins_over_its_prefix_and_words_inside_other_words_are_kept(self):
        n = self.norm()
        self.assertEqual(n.text("/tmp/buffon-x/work/home/.agent/a and /tmp/buffon-x/work/home/b"), "<agent>/a and <home>/b")
        self.assertEqual(n.text("pigment piggy pig-tool"), "pigment piggy pig-tool")

    def test_value_walks_keys_and_nested_values(self):
        self.assertEqual(self.norm().value({"pig": ["/tmp/buffon-x/work/proj"], "n": 3}), {"<bin>": ["<cwd>"], "n": 3})

    def test_key_paths_orders_and_scalars(self):
        body = {"model": "m", "stream": True, "messages": [{"role": "user", "content": "long free text"}, {"role": "assistant", "content": "x", "n": 1}], "tools": [{"type": "function", "function": {"name": "read"}}]}
        self.assertEqual(sorted(canon.key_paths(body)), ["messages", "messages[].content", "messages[].n", "messages[].role", "model", "stream", "tools", "tools[].function", "tools[].function.name", "tools[].type"])
        self.assertEqual(canon.key_orders(body)["messages[]"], [("role", "content"), ("role", "content", "n")])
        sc = dict(canon.scalars(body, canon.Normalizer()))
        self.assertEqual(sc["model"], "m")
        self.assertEqual(sc["messages[].n"], 1)
        self.assertNotIn("messages[].content", sc)
        self.assertEqual(sc["tools[].function.name"], "read")

    def test_key_order_is_observable(self):
        self.assertNotEqual(canon.key_orders({"a": 1, "b": 2}), canon.key_orders({"b": 2, "a": 1}))
        self.assertEqual(canon.canonical({"a": 1, "b": 2}), canon.canonical({"b": 2, "a": 1}))


class WireViews(unittest.TestCase):
    def test_the_same_situation_reads_the_same_on_each_api(self):
        chat = {"messages": [{"role": "system", "content": "S"}, {"role": "user", "content": "q"}, {"role": "assistant", "content": None, "tool_calls": [{"function": {"name": "read", "arguments": "{\"path\":\"a\"}"}}]},
                             {"role": "tool", "content": "R"}], "tools": [{"type": "function", "function": {"name": "read", "description": "d", "parameters": {"p": 1}}}]}
        resp = {"instructions": "S", "input": [{"role": "user", "content": [{"type": "input_text", "text": "q"}]}, {"type": "function_call", "name": "read", "arguments": "{\"path\":\"a\"}"},
                                              {"type": "function_call_output", "output": "R"}], "tools": [{"type": "function", "name": "read", "description": "d", "parameters": {"p": 1}}]}
        anth = {"system": [{"type": "text", "text": "S"}], "messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": [{"type": "tool_use", "name": "read", "input": {"path": "a"}}]},
                                                                      {"role": "user", "content": [{"type": "tool_result", "content": "R"}]}], "tools": [{"name": "read", "description": "d", "input_schema": {"p": 1}}]}
        views = [(wire.system_text(p, b), wire.tool_defs(p, b), wire.messages(p, b)) for p, b in (("openai-completions", chat), ("openai-responses", resp), ("anthropic-messages", anth))]
        self.assertEqual(views[0][0], "S")
        self.assertEqual(views[0], views[1])
        self.assertEqual(views[0], views[2])
        self.assertEqual(views[0][2], [("user", "text", "q"), ("assistant", "call", ("read", {"path": "a"})), ("tool", "result", "R")])


class Generation(unittest.TestCase):
    def test_help_is_parsed_into_flags_values_and_commands(self):
        flags, commands = probes.parse_help(HELP)
        self.assertEqual([f[0] for f in flags], [["--provider"], ["--print", "-p"], ["--name", "-n"], ["--list-models"], ["--no-tools", "-nt"], ["--help", "-h"]])
        self.assertEqual([f[1] for f in flags], [True, False, True, True, False, False])
        self.assertEqual(commands, ["install", "list"])

    def test_every_flag_and_command_gets_probes_that_cite_pi(self):
        with tempfile.TemporaryDirectory() as src:
            os.makedirs(os.path.join(src, probes.SRC, "cli"))
            with open(os.path.join(src, probes.SRC, "cli", "args.ts"), "w") as f:
                f.write('x\n} else if (arg === "--provider") {\n} else if (arg === "--print" || arg === "-p") {\n')
            ps = {p.id: p for p in probes.flag_probes(HELP, src)}
        self.assertEqual(ps["F1.advertised.provider"].cite, f"{probes.SRC}/cli/args.ts:2")
        self.assertEqual(ps["F1.advertised.print"].cite, f"{probes.SRC}/cli/args.ts:3")
        self.assertEqual(ps["F1.advertised.no-tools"].cite, "`pi --help` (--no-tools)")
        self.assertIn("F1.effect.provider", ps)
        self.assertNotIn("F1.effect.help", ps)   # informational flags have no effect probe
        self.assertNotIn("F1.effect.list-models", ps)
        self.assertIn("F1.command.install", ps)

    def test_the_whole_set_has_unique_ids_and_every_probe_cites_a_source(self):
        ps = probes.all_probes(HELP)
        self.assertEqual(len({p.id for p in ps}), len(ps))
        self.assertTrue(all(p.cite and p.dim in probes.DIMENSIONS for p in ps))
        self.assertEqual({p.dim for p in ps}, {"F1", "F2", "F3", "F4", "F5", "F6", "F7"})

    def test_tool_arguments_follow_the_schema_the_harness_advertises(self):
        schema = {"properties": {"file_path": {}, "old_string": {}, "new_string": {}}, "required": ["file_path", "old_string", "new_string"]}
        self.assertEqual(probes.tool_args("edit", schema), {"file_path": "README.md", "old_string": "Second line.", "new_string": "Replaced line."})
        self.assertEqual(probes.tool_args("read-range", {"properties": {"path": {}, "offset": {}, "limit": {}}}), {"path": "src/a.txt", "offset": 2, "limit": 1})
        self.assertEqual(probes.tool_args("bash-fail", {"properties": {"command": {}}, "required": ["command"]}), {"command": "echo out; echo err 1>&2; exit 3"})


def res(obs=None, status="ok", reason=""):
    r = {"status": status}
    if status == "ok":
        r.update(hash=score.digest(obs), obs=obs)
    else:
        r["reason"] = reason
    return r


def probe(pid, dim, **kw):
    return probes.Probe(pid, dim, "t", "c", None, **kw)


class Scoring(unittest.TestCase):
    def test_equal_observations_match_and_different_ones_do_not(self):
        ps = [probe("F1.a", "F1"), probe("F1.b", "F1")]
        ref = {"F1.a": res({"x": 1}), "F1.b": res([1, 2])}
        got = {"F1.a": res({"x": 1}), "F1.b": res([1, 3])}
        sc = score.score_arm(ps, got, ref)
        self.assertEqual((sc["dimensions"]["F1"]["match"], sc["dimensions"]["F1"]["mismatch"]), (1, 1))
        self.assertEqual(sc["dimensions"]["F1"]["pct"], 50.0)
        self.assertEqual(score.score_arm(ps, ref, ref)["overall"], 100.0)

    def test_failures_skips_and_missing_results_are_mismatches_but_an_unspoken_api_is_not_applicable(self):
        ps = [probe(f"F2.{i}", "F2") for i in range(4)]
        ref = {p.id: res({"v": 1}) for p in ps}
        got = {"F2.0": res(status="error", reason="boom"), "F2.1": res(status="skip", reason="it has no print_session mode"), "F2.2": res(status="skip", reason="it does not speak openai-responses")}
        sc = score.score_arm(ps, got, ref)["dimensions"]["F2"]
        self.assertEqual((sc["match"], sc["mismatch"], sc["na"], sc["scored"]), (0, 3, 1, 3))

    def test_not_applicable_dimensions_are_dropped_and_the_weights_renormalised_never_zeroed(self):
        ps = [probe("F1.a", "F1"), probe("F7.a", "F7", applies=lambda a: "no extensions")]
        ref = {"F1.a": res(1), "F7.a": res(1)}
        got = {"F1.a": res(1), "F7.a": {"status": "na", "reason": "no extensions"}}
        sc = score.score_arm(ps, got, ref)
        self.assertIsNone(sc["dimensions"]["F7"]["pct"])
        self.assertEqual(sc["overall"], 100.0)
        self.assertEqual(sc["weights_used"], {"F1": 5})
        got["F1.a"] = res(2)
        self.assertEqual(score.score_arm(ps, got, ref)["overall"], 0.0)

    def test_overall_is_the_weighted_mean_of_the_dimensions_that_apply(self):
        ps = [probe("F1.a", "F1"), probe("F2.a", "F2")]
        ref = {"F1.a": res(1), "F2.a": res(1)}
        got = {"F1.a": res(1), "F2.a": res(2)}
        self.assertAlmostEqual(score.score_arm(ps, got, ref)["overall"], 100.0 * 5 / 30)

    def test_unstable_and_invalid_probes_are_left_out_of_everyones_score(self):
        ps = [probe("F3.a", "F3"), probe("F3.b", "F3"), probe("F3.c", "F3", ref_ok=lambda o: "missing helper" not in o["r"])]
        ref = {"F3.a": res({"r": "x"}), "F3.b": res({"r": "y"}), "F3.c": res({"r": "missing helper"})}
        got = {"F3.a": res({"r": "x"}), "F3.b": res({"r": "z"}), "F3.c": res({"r": "real output"})}
        d = score.score_arm(ps, got, ref, unstable={"F3.b"})["dimensions"]["F3"]
        self.assertEqual((d["match"], d["mismatch"], d["unstable"], d["invalid"]), (1, 0, 1, 1))

    def test_an_intentional_divergence_is_listed_but_still_counts_against_the_score(self):
        ps = [probe("F2.hello.completions.system", "F2")]
        ref = {"F2.hello.completions.system": res("Pi prompt")}
        got = {"F2.hello.completions.system": res("PiG prompt")}
        rules = [{"arms": ["pig-*"], "probes": ["F2.*.system"], "divergence": "D12"}]
        sc = score.score_arm(ps, got, ref, rules=rules, arm_id="pig-0.4.1")
        self.assertEqual(sc["dimensions"]["F2"]["pct"], 0.0)
        self.assertEqual(sc["dimensions"]["F2"]["intentional"], 1)
        self.assertEqual(sc["rows"], [("F2.hello.completions.system", "mismatch", "D12")])
        self.assertIsNone(score.score_arm(ps, got, ref, rules=rules, arm_id="other")["rows"][0][2])

    def test_the_digest_ignores_key_order_but_not_values(self):
        self.assertEqual(score.digest({"a": 1, "b": [1, 2]}), score.digest({"b": [1, 2], "a": 1}))
        self.assertNotEqual(score.digest({"a": 1}), score.digest({"a": 2}))


class LabRun(unittest.TestCase):
    def test_a_run_captures_exit_streams_requests_changed_files_and_sessions(self):
        tmp = tempfile.mkdtemp()
        h = types.SimpleNamespace(cwd=os.path.join(tmp, "p"), home=os.path.join(tmp, "h"), agent_dir=os.path.join(tmp, "h", ".agent"), sessions=os.path.join(tmp, "s"), env=dict(os.environ))
        for d in (h.cwd, h.home, h.sessions):
            os.makedirs(d)
        with open(os.path.join(h.cwd, "keep.txt"), "w") as f:
            f.write("same")
        with mock.MockServer() as srv:
            lab = labmod.Lab(types.SimpleNamespace(root=tmp), srv, tmp)
            setup = labmod.Setup(h)
            script = ("import http.client,json,sys;c=http.client.HTTPConnection('127.0.0.1',%d);c.request('POST','/v1/chat/completions',json.dumps({'stream':False,'messages':[{'role':'user','content':'q'}]}));"
                      "c.getresponse().read();open('new.txt','w').write('n');open(sys.argv[1]+'/a.jsonl','w').write('{}');print('out');sys.stderr.write('err');sys.exit(3)" % srv.port)
            obs = lab.run(types.SimpleNamespace(id="x"), setup, [sys.executable, "-c", script, h.sessions], steps=[mock.Step(text="ok")])
        self.assertEqual((obs.exit, obs.stdout.strip(), obs.stderr, obs.timed_out), (3, "out", "err", False))
        self.assertEqual(len(obs.requests), 1)
        self.assertEqual(obs.files, {"new.txt": "n"})
        self.assertEqual(obs.sessions, {"a.jsonl": "{}"})

    def test_a_hung_process_is_a_timeout_not_a_hang(self):
        tmp = tempfile.mkdtemp()
        h = types.SimpleNamespace(cwd=tmp, home=tmp, agent_dir=tmp, sessions=tmp, env=dict(os.environ))
        with mock.MockServer() as srv:
            obs = labmod.Lab(types.SimpleNamespace(root=tmp), srv, tmp).run(types.SimpleNamespace(id="x"), labmod.Setup(h), [sys.executable, "-c", "import time;time.sleep(30)"], timeout=0.5)
        self.assertTrue(obs.timed_out)
        self.assertIsNone(obs.exit)


class Views(unittest.TestCase):
    def test_session_view_keeps_structure_not_text(self):
        header = json.dumps({"type": "session", "version": 3, "id": "x", "cwd": "/c", "timestamp": "t"})
        msg = json.dumps({"type": "message", "id": "1", "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]}})
        view = probes.session_view({"s.jsonl": header + "\n" + msg + "\nnot json\n", "other.txt": "ignored"}, canon.Normalizer())
        self.assertEqual(view, [["session", ["cwd", "id", "timestamp", "type", "version"]], ["message", ["id", "message", "type"], "user", ["content", "role"], ["text"]], ["<not json>"]])

    def test_collapse_merges_runs_of_equal_events(self):
        self.assertEqual(probes.collapse(["a", "a", "b", "a", "a"]), ["a", "b", "a"])


class Graded(unittest.TestCase):
    """M8: faithfulness is graded (identical 1.0, equivalent-presentation 0.9, equivalent-semantics 0.6, behaviour-differs 0.0), never pass/fail."""

    def grade(self, pid, obs, ref):
        from buffon.faithfulness import grading
        return grading.grade(pid, obs, ref)

    def test_a_human_facing_difference_with_the_same_effect_is_presentation_and_a_different_effect_is_not(self):
        ref = {"exit": 0, "timed_out": False, "stdout": "usage: pi", "stderr": "", "wire": None, "files": []}
        self.assertEqual(self.grade("F1.effect.verbose", dict(ref, stdout="Usage: omp (rendered differently)"), ref), "presentation")
        self.assertEqual(self.grade("F1.effect.verbose", dict(ref, wire={"added": [["x", 1]]}), ref), "mismatch")
        self.assertEqual(self.grade("F1.effect.verbose", dict(ref, exit=2), ref), "mismatch")
        self.assertEqual(self.grade("F1.effect.verbose", dict(ref), ref), "match")

    def test_usage_text_with_the_same_options_is_presentation_and_a_missing_option_is_not(self):
        ref = {"exit": 0, "stdout": ["pi install [options]", "--local  install here"]}
        self.assertEqual(self.grade("F1.command.install", {"exit": 0, "stdout": ["omp install  <- different words", "--local   put it here"]}, ref), "presentation")
        self.assertEqual(self.grade("F1.command.install", {"exit": 0, "stdout": ["pi install"]}, ref), "mismatch")

    def test_a_machine_facing_difference_in_form_only_is_semantics_and_in_meaning_is_behaviour_differs(self):
        self.assertEqual(self.grade("F2.hello.completions.order", {"": [["a", "b"]]}, {"": [["b", "a"]]}), "semantics")
        self.assertEqual(self.grade("F2.hello.completions.order", {"": [["a", "c"]]}, {"": [["b", "a"]]}), "mismatch")
        ref = [[["read", "Read a file", {"p": 1}], ["bash", "Run", {"c": 1}]]]
        self.assertEqual(self.grade("F2.tool.completions.tools", [[["bash", "Execute a command", {"c": 1}], ["read", "Read a file", {"p": 1}]]], ref), "semantics")
        self.assertEqual(self.grade("F2.tool.completions.tools", [[["read", "Read a file", {"p": 2}], ["bash", "Run", {"c": 1}]]], ref), "mismatch")

    def test_json_key_sets_may_gain_keys_but_not_lose_them(self):
        ref = {"agent_end": [["messages", "type"]]}
        self.assertEqual(self.grade("F6.json.keys", {"agent_end": [["messages", "type", "usage"]]}, ref), "semantics")
        self.assertEqual(self.grade("F6.json.keys", {"agent_end": [["type"]]}, ref), "mismatch")
        self.assertEqual(self.grade("F6.json.keys", {"other": [["type"]]}, ref), "mismatch")

    def test_session_records_with_extra_keys_are_semantics_and_other_roles_are_not(self):
        ref = [["session", ["id", "type"]], ["message", ["id", "message", "type"], "user", ["content", "role"], ["text"]]]
        extra = [["session", ["cwd", "id", "type"]], ["message", ["id", "message", "parentId", "type"], "user", ["content", "role"], ["text"]]]
        other = [["session", ["id", "type"]], ["message", ["id", "message", "type"], "assistant", ["content", "role"], ["text"]]]
        self.assertEqual(self.grade("F4.write.records", extra, ref), "semantics")
        self.assertEqual(self.grade("F4.write.records", other, ref), "mismatch")
        lost = [["session", ["id", "type"]], ["message", ["id", "type"], "user", ["content", "role"], ["text"]]]
        self.assertEqual(self.grade("F4.write.records", lost, ref), "mismatch")
        self.assertEqual(self.grade("F4.write.header", ["session", ["cwd", "id", "type"]], ["session", ["id", "type"]]), "semantics")
        self.assertEqual(self.grade("F4.write.header", ["session", ["type"]], ["session", ["id", "type"]]), "mismatch")

    def test_a_tool_result_differing_in_form_is_semantics_wrong_files_are_behaviour_differs(self):
        ref = {"tool_present": True, "result": "a\nb", "files": {"out/new.txt": "written\n"}}
        self.assertEqual(self.grade("F3.write", dict(ref, result="a \r\nb\n\n"), ref), "semantics")
        # review: line breaks and indentation are content: a file read back as "a  b" or with its indentation changed is a wrong tool result
        self.assertEqual(self.grade("F3.write", dict(ref, result="a  b"), ref), "mismatch")
        self.assertEqual(self.grade("F3.write", dict(ref, result="a\n  b"), ref), "mismatch")
        self.assertEqual(self.grade("F3.write", dict(ref, files={"out/new.txt": "WRONG"}), ref), "mismatch")
        self.assertEqual(self.grade("F3.write", dict(ref, result="a\nc"), ref), "mismatch")

    def test_print_output_differing_in_form_is_semantics_and_in_line_breaks_is_not(self):
        ref = {"exit": 0, "stdout": "Hello there.\nSecond line.\n"}
        self.assertEqual(self.grade("F6.print-text", dict(ref, stdout="Hello there.  \r\nSecond line.\n\n"), ref), "semantics")
        self.assertEqual(self.grade("F6.print-text", dict(ref, stdout="Hello there. Second line.\n"), ref), "mismatch")

    def test_an_event_sequence_may_gain_events_but_not_reorder_or_lose_them(self):
        # review: same_set compared the "event type sequence" probes as sets, so a reordered or thinned stream was "the same meaning"
        ref = ["agent_start", "message_start", "message_end", "agent_end"]
        for pid in ("F6.json.types", "F6.rpc.events"):
            self.assertEqual(self.grade(pid, ["agent_start", "turn_start", "message_start", "message_end", "agent_end"], ref), "semantics")
            self.assertEqual(self.grade(pid, ["agent_start", "message_end", "message_start", "agent_end"], ref), "mismatch")
            self.assertEqual(self.grade(pid, ["agent_start", "message_start", "agent_end"], ref), "mismatch")

    def test_the_semantics_credit_is_six_tenths_and_every_class_counts_in_the_percentage(self):
        ps = [probe("F6.json.keys", "F6"), probe("F6.print-text", "F6")]
        ref = {"F6.json.keys": res({"agent_end": [["type"]]}), "F6.print-text": res({"exit": 0, "stdout": "hi"})}
        got = {"F6.json.keys": res({"agent_end": [["type", "usage"]]}), "F6.print-text": res({"exit": 0, "stdout": "hi\n"})}
        d = score.score_arm(ps, got, ref)["dimensions"]["F6"]
        self.assertEqual((d["semantics"], d["scored"]), (2, 2))
        self.assertAlmostEqual(d["pct"], 60.0)

    def test_a_flag_whose_effect_leaves_other_files_is_behaviour_differs(self):
        ref = {"exit": 0, "timed_out": False, "stdout": "x", "stderr": "", "wire": None, "files": ["a.txt"]}
        self.assertEqual(self.grade("F1.effect.x", dict(ref, stdout="other words", files=["b.txt"]), ref), "mismatch")

    def test_a_harness_that_claims_pi_sessions_and_writes_none_lost_data(self):
        # review: "it wrote no session file" was a Skip (n/a): no deduction and no gate for a harness that claims Pi sessions
        ps = [probe("F4.write.records", "F4")]
        ref = {"F4.write.records": res([["session", ["id", "type"]]])}
        got = {"F4.write.records": res({"session_written": False, "exit": 0})}
        sc = score.score_arm(ps, got, ref)
        self.assertEqual((sc["dimensions"]["F4"]["mismatch"], sc["correctness_failures"]), (1, ["F4.write.records"]))

    def test_the_session_probe_reports_a_missing_session_only_for_a_harness_that_claims_pi_sessions(self):
        from types import SimpleNamespace
        from unittest import mock
        from buffon.faithfulness import lab
        run = next(p for p in probes.session_probes() if p.id == "F4.write.records").run
        empty = SimpleNamespace(sessions={}, exit=0)
        with mock.patch.object(probes, "written", lambda ctx, arm, pid: (empty, None)):
            self.assertEqual(run(None, SimpleNamespace(claims=["pi-sessions", "pi-rpc"])), {"session_written": False, "exit": 0})
            with self.assertRaises(lab.Skip):
                run(None, SimpleNamespace(claims=["pi-rpc"]))

    def test_probes_without_a_comparator_are_identical_or_behaviour_differs(self):
        self.assertEqual(self.grade("F2.hello.completions.system", "x", "y"), "mismatch")
        self.assertEqual(self.grade("F4.resume-pi-session", [1], [2]), "mismatch")

    def test_the_dimension_percentage_is_the_mean_credit_and_overall_weights_machine_dimensions_more(self):
        ps = [probe("F1.effect.a", "F1"), probe("F1.effect.b", "F1")]
        ref = {"F1.effect.a": res({"exit": 0, "timed_out": False, "stdout": "x", "stderr": "", "wire": None, "files": []}), "F1.effect.b": res({"exit": 0, "timed_out": False, "stdout": "x", "stderr": "", "wire": None, "files": []})}
        got = {"F1.effect.a": ref["F1.effect.a"], "F1.effect.b": res({"exit": 0, "timed_out": False, "stdout": "other words", "stderr": "", "wire": None, "files": []})}
        d = score.score_arm(ps, got, ref)["dimensions"]["F1"]
        self.assertEqual((d["match"], d["presentation"], d["mismatch"], d["scored"]), (1, 1, 0, 2))
        self.assertAlmostEqual(d["pct"], 95.0)
        w = {k: v[1] for k, v in probes.DIMENSIONS.items()}
        self.assertGreater(min(w[k] for k in ("F2", "F4", "F6", "F7")), max(w["F1"], w["F8"]))
        self.assertEqual(sum(w.values()), 100)

    def test_an_intentional_divergence_is_listed_by_name_and_does_not_change_the_class(self):
        ps = [probe("F1.effect.a", "F1")]
        base = {"exit": 0, "timed_out": False, "stdout": "x", "stderr": "", "wire": None, "files": []}
        ref, got = {"F1.effect.a": res(base)}, {"F1.effect.a": res(dict(base, stdout="y"))}
        rules = [{"arms": ["omp"], "probes": ["F1.effect.*"], "divergence": "D7"}]
        sc = score.score_arm(ps, got, ref, rules=rules, arm_id="omp")
        self.assertEqual(sc["rows"], [("F1.effect.a", "presentation", "D7")])
        self.assertAlmostEqual(sc["dimensions"]["F1"]["pct"], 90.0)

    def test_correctness_failures_are_wrong_tools_crashes_and_hangs_never_presentation(self):
        ps = [probe("F3.write", "F3"), probe("F3.read", "F3"), probe("F1.effect.a", "F1"), probe("F6.print-text", "F6")]
        tool = lambda files: res({"tool_present": True, "result": "ok", "files": files})
        ref = {"F3.write": tool({"a": "1"}), "F3.read": tool({}), "F1.effect.a": res({"exit": 0, "timed_out": False, "stdout": "x", "stderr": "", "wire": None, "files": []}), "F6.print-text": res({"exit": 0, "stdout": "hi"})}
        got = {"F3.write": tool({"a": "WRONG"}), "F3.read": tool({}), "F1.effect.a": res({"exit": 0, "timed_out": True, "stdout": "x", "stderr": "", "wire": None, "files": []}),
               "F6.print-text": {"status": "error", "reason": "crash"}}
        self.assertEqual(sorted(score.score_arm(ps, got, ref)["correctness_failures"]), ["F1.effect.a", "F3.write", "F6.print-text"])
        presentation = dict(ref, **{"F1.effect.a": res({"exit": 0, "timed_out": False, "stdout": "different", "stderr": "", "wire": None, "files": []})})
        self.assertEqual(score.score_arm(ps, presentation, ref)["correctness_failures"], [])

    def test_a_correctness_failure_zeroes_the_tool_families_of_the_grade_and_a_presentation_difference_does_not(self):
        from buffon.report import grade as G
        from tests.test_grade import make, run
        wrong = run(make({"x": {f: 0.5 for f in ("core", "ext10", "streaming", "long-session", "devloop")}}, correctness={"x": ["F3.write"]}))["x"]
        for fam in ("core", "ext10", "long-session"):
            self.assertEqual(wrong["families"][fam]["score"], 0.0, fam)
            self.assertIn("F3.write", wrong["families"][fam]["gate"])
        self.assertGreater(wrong["families"]["streaming"]["score"], 70)
        self.assertGreater(wrong["families"]["devloop"]["score"], 70)
        fine = run(make({"x": {f: 0.5 for f in ("core", "ext10", "streaming", "long-session", "devloop")}}, correctness={"x": []}))["x"]
        self.assertGreater(fine["families"]["core"]["score"], 70)
        ref = run(make({"x": {"core": 0.5}}, correctness={"pi-node": ["F3.write"]}))["pi-node"]
        self.assertEqual(ref["families"]["core"]["score"], 70)


class Report(unittest.TestCase):
    def doc(self, version="1.1.0", started="2026-10-11T00:00:00Z"):
        ps = [probe("F1.a", "F1"), probe("F2.a", "F2"), probe("F7.a", "F7", applies=lambda a: "no extensions")]
        ref = {"F1.a": res(1), "F2.a": res(1), "F7.a": res(1)}
        got = {"F1.a": res(1), "F2.a": res(2), "F7.a": {"status": "na", "reason": "it loads no Pi extensions"}}
        rules = [{"arms": ["x"], "probes": ["F2.*"], "divergence": "D9"}]
        info = {"pi-node-b": {"version": version, "executable_sha256": "a" * 64, "install_tree_sha256": "b" * 64}, "x": {"version": "0.1", "executable_sha256": "c" * 64, "install_tree_sha256": "d" * 64}}
        return {"kind": "buffon-faithfulness", "probe_set_version": "v0", "started_utc": started, "reference": {"arm": "pi-node", "version": version}, "arms": info, "probes": [{"id": p.id, "dim": p.dim, "title": "title " + p.id, "cite": "cite " + p.id} for p in ps],
                "unstable": [], "results": {"x": got, "pi-node-b": ref}, "twin": "pi-node-b", "scores": {"x": score.score_arm(ps, got, ref, rules=rules, arm_id="x"), "pi-node-b": score.score_arm(ps, ref, ref)},
                "reference_scores": score.score_arm(ps, ref, ref)}

    def render(self, docs):
        tmp = tempfile.mkdtemp()
        paths = []
        for i, d in enumerate(docs):
            os.makedirs(os.path.join(tmp, str(i)))
            with open(os.path.join(tmp, str(i), "faithfulness.json"), "w") as f:
                json.dump(d, f)
            paths.append(os.path.join(tmp, str(i)))
        with open(report.render(paths, os.path.join(tmp, "out.md"))) as f:
            return f.read()

    def test_pi_is_100_the_harness_is_below_and_intentional_mismatches_are_marked(self):
        text = self.render([self.doc()])
        self.assertIn("| **pi-node** (reference) | 1.1.0 | **100.0** |", text)
        self.assertRegex(text, r"\| x \| 0\.1 \| \*\*16\.7\*\* \|")   # F1 100 (weight 5), F2 0 (weight 25), F7 N/A dropped: 500/30
        self.assertIn("| `F2.a` | title F2.a | cite F2.a | D9 |", text)
        self.assertIn("Not applicable (never scored as a miss): it loads no Pi extensions.", text)

    def test_the_report_lists_graded_rows_by_class_and_correctness_failures(self):
        ps = [probe("F1.effect.a", "F1"), probe("F3.write", "F3")]
        eff = lambda out: res({"exit": 0, "timed_out": False, "stdout": out, "stderr": "", "wire": None, "files": []})
        tool = lambda f: res({"tool_present": True, "result": "ok", "files": f})
        ref = {"F1.effect.a": eff("x"), "F3.write": tool({"a": "1"})}
        got = {"F1.effect.a": eff("different words"), "F3.write": tool({"a": "WRONG"})}
        d = self.doc()
        d["probes"] = [{"id": p.id, "dim": p.dim, "title": "t " + p.id, "cite": "c"} for p in ps]
        d["results"] = {"x": got, "pi-node-b": ref}
        d["scores"] = {"x": score.score_arm(ps, got, ref, rules=[{"arms": ["x"], "probes": ["F1.*"], "divergence": "D4"}], arm_id="x"), "pi-node-b": score.score_arm(ps, ref, ref)}
        d["reference_scores"] = score.score_arm(ps, ref, ref)
        text = self.render([d])
        self.assertIn("| `F1.effect.a` | equivalent-presentation | D4 |", text)
        self.assertIn("Correctness failures (1)", text)
        self.assertIn("`F3.write`", text)
        self.assertIn("equivalent presentation (0.9)", text)

    def test_several_pi_releases_make_a_ladder_oldest_first_and_the_newest_detail_first(self):
        text = self.render([self.doc("1.1.0", "2026-10-11T00:00:00Z"), self.doc("1.0.0", "2026-09-01T00:00:00Z")])
        self.assertLess(text.index("| arm | Pi 1.0.0 | Pi 1.1.0 |"), text.index("## Pi 1.1.0"))
        self.assertIn("| x | 16.7 | 16.7 |", text)
        self.assertLess(text.index("## Pi 1.1.0"), text.index("## Pi 1.0.0"))


if __name__ == "__main__":
    unittest.main()


class FlagEffectIsRelativeToTheArmsOwnBaseline(unittest.TestCase):
    """An arm whose ordinary request differs from Pi's (max_tokens against max_completion_tokens) is charged for that once, in F2; a flag's F1 effect is only what the flag changed."""

    def req(self, **extra):
        body = {"model": "m", "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}], "stream": True}
        body.update(extra)
        return types.SimpleNamespace(protocol="openai-completions", body=body)

    def test_the_same_change_reads_the_same_whatever_the_baseline_looks_like(self):
        pi = probes.wire_delta(self.req(max_completion_tokens=4096, temperature=0.5), self.req(max_completion_tokens=4096))
        port = probes.wire_delta(self.req(max_tokens=4096, temperature=0.5), self.req(max_tokens=4096))
        self.assertEqual(pi, port)
        self.assertEqual(pi["added"], [["temperature", 0.5]])
        self.assertEqual((pi["removed"], pi["tools"], pi["roles"]), ([], [], None))

    def test_a_flag_that_changes_nothing_has_an_empty_delta_and_a_missing_request_is_visible(self):
        self.assertEqual(probes.wire_delta(self.req(), self.req())["added"], [])
        self.assertEqual(probes.wire_delta(None, self.req()), "no request")
        self.assertIsNone(probes.wire_delta(None, None))


class EveryProbeIsMetered(unittest.TestCase):
    """R10: a probe that connects outside loopback fails like a benchmark sample does (the socket audit reads the process tree while it runs)."""

    def lab_and_setup(self):
        tmp = tempfile.mkdtemp()
        h = types.SimpleNamespace(cwd=os.path.join(tmp, "p"), home=os.path.join(tmp, "h"), agent_dir=os.path.join(tmp, "h", ".agent"), sessions=os.path.join(tmp, "s"), env=dict(os.environ))
        for d in (h.cwd, h.home, h.sessions):
            os.makedirs(d)
        return labmod.Lab(types.SimpleNamespace(root=tmp), mock.MockServer().__enter__(), tmp), labmod.Setup(h)

    CONNECT_OUT = "import socket,time;s=socket.socket();s.setblocking(False);s.connect_ex(('192.0.2.1',9));time.sleep(3.0);print('done')"

    def test_a_probe_whose_arm_connects_outside_loopback_is_an_egress_violation(self):
        lab, setup = self.lab_and_setup()
        with self.assertRaises(labmod.EgressViolation) as caught:
            lab.run(types.SimpleNamespace(id="x"), setup, [sys.executable, "-c", self.CONNECT_OUT], steps=[mock.Step(text="ok")])
        self.assertEqual(caught.exception.remotes, ["192.0.2.1:9"])
        self.assertEqual(lab.violations, [{"arm": "x", "remotes": ["192.0.2.1:9"]}])

    def test_run_probe_records_the_failure_with_the_remotes_and_never_scores_it_ok(self):
        from buffon.faithfulness import runner as runnermod
        lab, setup = self.lab_and_setup()
        probe = probes.Probe("T.egress", "F1", "t", "cite", lambda ctx, arm: lab.run(arm, setup, [sys.executable, "-c", self.CONNECT_OUT], steps=[mock.Step(text="ok")]).stdout)
        result = runnermod.run_probe(None, probe, types.SimpleNamespace(id="x"))
        self.assertEqual((result["status"], result["egress"]), ("error", ["192.0.2.1:9"]))
        self.assertIn("egress: the arm connected to 192.0.2.1:9", result["reason"])

    def test_a_clean_probe_and_a_loopback_connection_pass(self):
        lab, setup = self.lab_and_setup()
        obs = lab.run(types.SimpleNamespace(id="x"), setup, [sys.executable, "-c", "print('quiet')"], steps=[mock.Step(text="ok")])
        self.assertEqual((obs.exit, obs.stdout.strip(), lab.violations), (0, "quiet", []))

    def test_an_observation_left_by_an_rpc_meter_is_reported_too(self):
        from buffon.runner import egress
        lab, _ = self.lab_and_setup()
        egress.OBSERVED.add("203.0.113.7:443")
        with self.assertRaises(labmod.EgressViolation):
            lab.check_egress(types.SimpleNamespace(id="y"))
        self.assertEqual(egress.take(), set())   # taken: the next probe starts clean


class ReviewEgressGuards(unittest.TestCase):
    """Two R10 mutants survived the builder's tests: run_rpc without its egress check, and `buffon faithfulness run` exiting 0 on a violation."""

    def test_an_rpc_probe_that_connects_outside_loopback_is_a_violation(self):
        lab, setup = EveryProbeIsMetered.lab_and_setup(None)
        lab.argv_for = lambda arm, setup, mode, extra=(): [sys.executable, "-c", EveryProbeIsMetered.CONNECT_OUT]
        with self.assertRaises(labmod.EgressViolation) as caught:
            lab.run_rpc(types.SimpleNamespace(id="r"), setup, [], timeout=1.5)
        self.assertEqual(caught.exception.remotes, ["192.0.2.1:9"])

    def test_the_faithfulness_command_exits_4_on_a_violation(self):
        from buffon import cli
        from buffon.faithfulness import runner as runnermod
        saved = runnermod.run, report.render
        args = types.SimpleNamespace(action="run", arms=["x"], reference="pi-node", out=tempfile.mkdtemp(), pi_source=None, only=None, cache_dir="", work_dir="", timeout=60, offline=False)
        try:
            report.render = lambda *a, **k: "report.md"
            for violations, code in (([{"arm": "x", "remotes": ["192.0.2.1:9"]}], 4), ([], 0)):
                runnermod.run = lambda *a, **k: {"scores": {}, "egress": {"violations": violations}}
                self.assertEqual(cli.cmd_faithfulness(args), code)
        finally:
            runnermod.run, report.render = saved
