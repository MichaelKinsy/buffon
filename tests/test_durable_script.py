# SPDX-License-Identifier: Apache-2.0
"""The durable script generator: determinism, subsets, the varied twin, the sizes of every shape, the compat history pattern, the mixed weights, the cache and the command line."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zlib

from buffon.durable import script as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = S.DEFAULT_SEED
ALL = [("bench8", "bench8"), ("tools", "tools"), ("text", "text"), ("large", "large"), ("light", "light"), ("stream", "stream"), ("crash", "crash"), ("fanout", "fanout"),
       ("subagent", "subagent"), ("mixed", "mixed")]


def turn_of(shape, n=7, **options):
    return S.build(SEED, "repeating", [(n, shape)], **options).data["turns"][0]


def calls_of(turn):
    return [c for r in turn["rounds"] for c in r["calls"]]


def nbytes(text):
    return len(text.encode())


class Determinism(unittest.TestCase):
    def test_same_inputs_give_the_same_bytes_and_digest(self):
        plan = S.history_plan("mixed", 30) + S.measured_plan("mixed", 30, 5)
        a, b = S.build(SEED, "repeating", plan, docs=4), S.build(SEED, "repeating", plan, docs=4)
        self.assertEqual(a.dumps(), b.dumps())
        self.assertEqual(a.sha256, b.sha256)
        self.assertNotEqual(a.sha256, S.build(SEED + 1, "repeating", plan, docs=4).sha256)
        self.assertNotEqual(a.sha256, S.build(SEED, "varied", plan, docs=4).sha256)

    def test_a_turn_is_the_same_alone_and_inside_a_long_plan(self):
        long = S.build(SEED, "repeating", S.history_plan("mixed", 80) + S.measured_plan("mixed", 80, 5))
        for n in (0, 1, 13, 42, 79, 80, 84):
            shape = long.turn(n)["shape"]
            alone = S.build(SEED, "repeating", [(n, "mixed")]).data["turns"][0]
            self.assertEqual(alone, long.turn(n), n)
            self.assertEqual(S.build(SEED, "repeating", [(n, shape)]).data["turns"][0], long.turn(n), n)   # the concrete shape asked for directly builds the same turn

    def test_history_turns_and_measured_turns_agree_whatever_plan_produced_them(self):
        whole = S.build(SEED, "repeating", S.history_plan("compat", 50) + S.measured_plan("compat", 50, 3))
        history = S.build(SEED, "repeating", S.history_plan("compat", 50))
        measured = S.build(SEED, "repeating", S.measured_plan("compat", 50, 3))
        self.assertEqual(whole.data["turns"][:50], history.data["turns"])
        self.assertEqual(whole.data["turns"][50:], measured.data["turns"])

    def test_the_seed_of_a_turn_ignores_python_hash_randomisation(self):
        code = "from buffon.durable import script as S; print(S.build(20261018, 'repeating', [(3, 'mixed'), (4, 'tools')]).sha256)"
        outs = {subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED=h)).stdout for h in ("1", "2")}
        self.assertEqual(len(outs), 1)
        self.assertEqual(outs.pop().strip(), S.build(SEED, "repeating", [(3, "mixed"), (4, "tools")]).sha256)

    def test_the_shape_parameter_is_part_of_the_turns_seed(self):
        self.assertNotEqual(turn_of("fanout", fanout_n=8), turn_of("fanout", fanout_n=64))
        self.assertEqual(calls_of(turn_of("fanout", fanout_n=64))[0]["args"], {"k": "c7.0.0", "n": 64})
        self.assertEqual(turn_of("text", fanout_n=8), turn_of("text", fanout_n=64))   # a parameter another shape does not use changes nothing


class Format(unittest.TestCase):
    def test_canonical_bytes(self):
        s = S.build(SEED, "repeating", [(0, "text")], docs=1)
        raw = s.dumps()
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertEqual(raw.decode(), json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
        self.assertEqual(json.loads(raw), s.data)

    def test_header_and_tool_follow_the_protocol(self):
        d = S.build(SEED, "repeating", [(0, "text")]).data
        self.assertEqual((d["format"], d["generator"], d["seed"], d["variant"], d["shape"]), (S.GENERATOR, S.GENERATOR, SEED, "repeating", "text"))
        self.assertEqual(S.GENERATOR, "buffon-durable-script/1")
        self.assertEqual(d["tool"], {"name": "lookup", "description": "Look up a stored record by key.", "parameters": {
            "type": "object", "properties": {"k": {"type": "string"}}, "required": ["k"], "additionalProperties": False}})
        self.assertEqual(nbytes(d["summary"]["text"]), 2048)
        self.assertEqual(d["docs"], [])

    def test_every_turn_follows_the_turn_grammar(self):
        for shape, _ in ALL:
            for n in range(6):
                t = turn_of(shape, n)
                self.assertTrue(t["user"].startswith(f"[t{n}] "), t["user"])
                self.assertEqual(set(t), {"n", "user", "shape", "rounds", "stream"})
                self.assertEqual(t["rounds"][-1]["calls"], [])   # the last round has no calls and every other round has
                self.assertTrue(all(r["calls"] for r in t["rounds"][:-1]))
                for r, rnd in enumerate(t["rounds"]):
                    for j, c in enumerate(rnd["calls"]):
                        self.assertEqual(c["id"], f"c{n}.{r}.{j}")
                        self.assertEqual(c["args"]["k"], c["id"])
                        self.assertIn(c["name"], ("lookup", "effect", "fanout", "subagent"))

    def test_text_is_prose_not_a_repeated_filler(self):
        text = turn_of("large")["rounds"][0]["calls"][0]["result"].encode()
        self.assertGreater(len(zlib.compress(text, 9)) / len(text), 0.25)
        words = set(re.findall(r"[A-Za-z]+", text.decode()))
        self.assertGreater(len(words), 100)
        self.assertNotEqual(turn_of("light", 1)["rounds"][0]["calls"][0]["result"], turn_of("light", 2)["rounds"][0]["calls"][0]["result"])

    def test_text_has_multibyte_characters_so_chunk_boundaries_matter(self):
        s = S.build(SEED, "repeating", S.history_plan("mixed", 60))
        self.assertTrue(any(len(t.encode()) != len(t) for t in (r["text"] for tr in s.data["turns"] for r in tr["rounds"])))


class Subset(unittest.TestCase):
    def test_subset_keeps_header_and_selected_turns_in_script_order(self):
        s = S.build(SEED, "repeating", S.history_plan("mixed", 10) + S.measured_plan("mixed", 10, 3), docs=2)
        sub = s.subset([12, 3, 10])
        self.assertEqual([t["n"] for t in sub.data["turns"]], [3, 10, 12])
        self.assertEqual({k: v for k, v in sub.data.items() if k != "turns"}, {k: v for k, v in s.data.items() if k != "turns"})
        self.assertEqual(sub.turn(10), s.turn(10))
        with self.assertRaises(KeyError):
            s.subset([99])
        with self.assertRaises(KeyError):
            sub.turn(4)
        self.assertEqual(S.build(SEED, "repeating", [(3, "mixed"), (10, "mixed"), (12, "mixed")], docs=2).sha256, sub.sha256)

    def test_write_is_atomic_and_returns_the_digest(self):
        with tempfile.TemporaryDirectory() as d:
            s = S.build(SEED, "repeating", [(0, "text")])
            path = os.path.join(d, "s.json")
            self.assertEqual(s.write(path), s.sha256)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), s.dumps())
            self.assertEqual(os.listdir(d), ["s.json"])

    def test_plans_reject_repeated_turns_unknown_shapes_and_variants(self):
        for plan in ([(1, "text"), (1, "text")], [(0, "nope")], [(-1, "text")]):
            with self.assertRaises(ValueError):
                S.build(SEED, "repeating", plan)
        with self.assertRaises(ValueError):
            S.build(SEED, "other", [(0, "text")])
        with self.assertRaises(ValueError):
            S.history_plan("nope", 3)


class Twin(unittest.TestCase):
    def pair(self, plan=None, **options):
        plan = plan or S.history_plan("mixed", 40) + S.measured_plan("subagent", 40, 3) + S.measured_plan("crash", 43, 2) + S.measured_plan("stream", 45, 2) \
            + S.measured_plan("tasks", 47, 2) + S.measured_plan("compat", 49, 2)
        return S.build(SEED, "repeating", plan, **options), S.build(SEED, "varied", plan, **options)

    def test_the_twin_keeps_lengths_ids_markers_and_structure_and_changes_the_words(self):
        base, twin = self.pair(docs=5)
        self.assertEqual(twin.data["variant"], "varied")
        self.assertEqual({k: v for k, v in twin.data.items() if k not in ("variant", "turns", "summary", "docs")}, {k: v for k, v in base.data.items() if k not in ("variant", "turns", "summary", "docs")})
        changed = same_len = 0
        for a, b in zip(base.data["turns"], twin.data["turns"]):
            self.assertEqual((a["n"], a["shape"], a["stream"], len(a["rounds"])), (b["n"], b["shape"], b["stream"], len(b["rounds"])))
            marker = re.match(r"\[t\d+\] ", a["user"]).group()
            self.assertTrue(b["user"].startswith(marker))
            self.assertEqual(len(a["user"]), len(b["user"]))
            self.assertEqual(nbytes(a["user"]), nbytes(b["user"]))
            for ra, rb in zip(a["rounds"], b["rounds"]):
                self.assertEqual(nbytes(ra["text"]), nbytes(rb["text"]))
                self.assertEqual(len(ra["calls"]), len(rb["calls"]))
                for ca, cb in zip(ra["calls"], rb["calls"]):
                    self.assertEqual({k: v for k, v in ca.items() if k not in ("result", "sub")}, {k: v for k, v in cb.items() if k not in ("result", "sub")})   # id, name, args
                    self.assertEqual(nbytes(ca["result"]), nbytes(cb["result"]))
                    changed += ca["result"] != cb["result"]
                    same_len += 1
                    if "sub" in ca:
                        self.assertTrue(cb["sub"]["user"].startswith(re.match(r"\[s\d+\.\d+\.\d+\] ", ca["sub"]["user"]).group()))
                        self.assertEqual(nbytes(ca["sub"]["user"]), nbytes(cb["sub"]["user"]))
                        self.assertEqual(nbytes(ca["sub"]["rounds"][0]["text"]), nbytes(cb["sub"]["rounds"][0]["text"]))
                        self.assertEqual(cb["result"], cb["sub"]["rounds"][0]["text"])   # the parent still sees exactly what the child said
        self.assertGreater(same_len, 20)
        self.assertEqual(changed, same_len)
        self.assertEqual(nbytes(twin.data["summary"]["text"]), 2048)
        self.assertNotEqual(twin.data["summary"]["text"], base.data["summary"]["text"])
        self.assertEqual([nbytes(d) for d in twin.data["docs"]], [88] * 5)
        self.assertNotEqual(twin.data["docs"], base.data["docs"])

    def test_twin_digits_stay_digits_and_letters_stay_letters(self):
        base, twin = self.pair()
        for a, b in zip(base.data["turns"], twin.data["turns"]):
            x, y = a["rounds"][0]["calls"], b["rounds"][0]["calls"]
            for ca, cb in zip(x, y):
                self.assertEqual(re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "0", ca["result"])), re.sub(r"[A-Za-z]", "a", re.sub(r"\d", "0", cb["result"])))
                self.assertEqual(re.findall(r"[^A-Za-z0-9]", ca["result"]), re.findall(r"[^A-Za-z0-9]", cb["result"]))

    def test_vary_of_a_script_is_build_of_the_varied_variant_and_the_twin_is_per_turn(self):
        base, twin = self.pair(docs=3)
        self.assertEqual(S.vary(base).dumps(), twin.dumps())
        n = base.data["turns"][5]["n"]
        self.assertEqual(S.vary(base.subset([n])).data["turns"], [twin.turn(n)])   # the twin of a subset is the subset of the twin
        self.assertEqual(S.build(SEED, "varied", [(n, "mixed")]).data["turns"][0]["rounds"], twin.turn(n)["rounds"])
        with self.assertRaises(ValueError):
            S.vary(twin)

    def test_the_twin_is_deterministic(self):
        a, b = self.pair(plan=[(0, "tools"), (1, "light")])[1], S.build(SEED, "varied", [(0, "tools"), (1, "light")])
        self.assertEqual(a.sha256, b.sha256)


class Sizes(unittest.TestCase):
    def test_bench8_is_eight_lookups_in_one_round_then_text_and_every_97th_result_is_large(self):
        s = S.build(SEED, "repeating", [(n, "bench8") for n in range(60)])
        big = 0
        for t in s.data["turns"]:
            self.assertEqual([len(r["calls"]) for r in t["rounds"]], [8, 0])
            self.assertEqual(t["rounds"][0]["text"], "")
            for j, c in enumerate(t["rounds"][0]["calls"]):
                g = t["n"] * 8 + j   # the global call index
                self.assertEqual(nbytes(c["result"]), 8192 if (g + 1) % 97 == 0 else 256, (t["n"], j))
                big += nbytes(c["result"]) == 8192
        self.assertEqual(big, 60 * 8 // 97)   # 480 calls hold four multiples of 97
        self.assertEqual(nbytes(S.build(SEED, "repeating", [(12, "bench8")]).data["turns"][0]["rounds"][0]["calls"][0]["result"]), 8192)   # call number 97 = 12 * 8 + 0 + 1

    def test_compat_history_is_one_one_zero_lookup_calls_repeating(self):
        plan = S.history_plan("compat", 12)
        self.assertEqual([n for n, _ in plan], list(range(12)))
        s = S.build(SEED, "repeating", plan)
        self.assertEqual([len(calls_of(t)) for t in s.data["turns"]], [1, 1, 0] * 4)
        self.assertEqual(S.COMPAT_PATTERN, (1, 1, 0))
        self.assertTrue(all(nbytes(calls_of(t)[0]["result"]) in (256, 8192) for t in s.data["turns"] if calls_of(t)))
        self.assertEqual({s for _, s in S.measured_plan("compat", 12, 10)}, {"bench8"})
        # the single call of a history turn is large exactly where the global numbering puts a multiple of 97
        s2 = S.build(SEED, "repeating", [(96, "bench1")])
        self.assertEqual(nbytes(calls_of(s2.data["turns"][0])[0]["result"]), 8192 if (96 * 8 + 1) % 97 == 0 else 256)

    def test_tools_light_text_large(self):
        for n in range(40):
            t = turn_of("tools", n)
            calls = calls_of(t)
            self.assertTrue(4 <= len(calls) <= 12)
            self.assertTrue(all(0 < len(r["calls"]) <= 4 for r in t["rounds"][:-1]))
            self.assertEqual([len(r["calls"]) for r in t["rounds"][:-2]], [4] * (len(t["rounds"]) - 2))   # a full round is four; the last holds the rest
            self.assertTrue(all(512 <= nbytes(c["result"]) <= 8192 for c in calls))
            light = calls_of(turn_of("light", n))
            self.assertTrue(1 <= len(light) <= 3 and all(2560 <= nbytes(c["result"]) <= 5632 for c in light))
            self.assertEqual(len(turn_of("light", n)["rounds"]), 2)
            text = turn_of("text", n)
            self.assertEqual(len(text["rounds"]), 1)
            self.assertTrue(300 <= len(text["rounds"][0]["text"]) <= 1500)
            self.assertEqual([nbytes(c["result"]) for c in calls_of(turn_of("large", n))], [32768])
        self.assertEqual(len({len(calls_of(turn_of("tools", n))) for n in range(40)}), 9)   # every count 4..12 occurs

    def test_stream_crash_fanout_subagent(self):
        for n in range(30):
            t = turn_of("stream", n)
            self.assertEqual([len(r["calls"]) for r in t["rounds"]], [1, 0])
            self.assertEqual(t["rounds"][0]["calls"][0]["name"], "lookup")
            self.assertTrue(40 <= t["stream"]["chunks"] <= 60 and 1000 <= t["stream"]["total_ms"] <= 2000)
            self.assertTrue(len(t["rounds"][1]["text"]) >= t["stream"]["chunks"])
            self.assertEqual(turn_of("text", n)["stream"], {"chunks": 1, "total_ms": 0})
        c = turn_of("crash", 4)
        self.assertEqual([[x["name"] for x in r["calls"]] for r in c["rounds"]], [["lookup"], ["effect"], []])
        self.assertEqual([x["id"] for x in calls_of(c)], ["c4.0.0", "c4.1.0"])
        f = turn_of("fanout", 4)
        self.assertEqual(calls_of(f), [dict(calls_of(f)[0], name="fanout", args={"k": "c4.0.0", "n": 8})])
        sub = turn_of("subagent", 4)
        call = calls_of(sub)[0]
        self.assertEqual((call["name"], call["args"]), ("subagent", {"k": "c4.0.0"}))
        self.assertTrue(call["sub"]["user"].startswith("[s4.0.0] "))
        self.assertEqual([r["calls"] for r in call["sub"]["rounds"]], [[]])
        self.assertEqual(call["result"], call["sub"]["rounds"][0]["text"])

    def test_documents_are_fixed_88_byte_strings(self):
        d = S.build(SEED, "repeating", [(0, "text")], docs=300).data["docs"]
        self.assertEqual(len(d), 300)
        self.assertEqual({nbytes(x) for x in d}, {88})
        self.assertEqual(len(set(d)), 300)
        self.assertEqual(S.build(SEED, "repeating", [(0, "text")], docs=10).data["docs"], d[:10])   # string i does not depend on how many follow

    def test_summary_size_and_sections(self):
        text = S.build(SEED, "repeating", [(0, "text")]).data["summary"]["text"]
        self.assertEqual(nbytes(text), 2048)
        for heading in ("## Goal", "## Progress", "## Next Steps", "## Critical Context"):
            self.assertIn(heading, text)
        self.assertEqual(nbytes(S.build(SEED, "repeating", [(0, "text")], summary_bytes=512).data["summary"]["text"]), 512)

    def test_the_token_rule_is_four_bytes_per_token(self):
        self.assertEqual((S.tokens(0), S.tokens(1), S.tokens(4), S.tokens(5)), (0, 1, 1, 2))
        self.assertEqual(S.BYTES_PER_TOKEN, 4)


class Mixed(unittest.TestCase):
    def test_weights_over_many_turns(self):
        n = 20000
        counts = {}
        for i in range(n):
            shape = S.concrete_shape(SEED, i, "mixed")
            counts[shape] = counts.get(shape, 0) + 1
        want = dict(S.MIXED_WEIGHTS)
        self.assertEqual(sum(want.values()), 100)
        self.assertEqual(want, {"light": 50, "tools": 20, "text": 20, "large": 10})
        for shape, weight in want.items():
            self.assertAlmostEqual(counts[shape] / n * 100, weight, delta=1.0, msg=shape)

    def test_the_concrete_shape_is_recorded_and_does_not_depend_on_the_variant(self):
        plan = [(n, "mixed") for n in range(50)]
        a, b = S.build(SEED, "repeating", plan), S.build(SEED, "varied", plan)
        self.assertEqual([t["shape"] for t in a.data["turns"]], [t["shape"] for t in b.data["turns"]])
        self.assertTrue(set(t["shape"] for t in a.data["turns"]) <= {"light", "tools", "text", "large"})
        self.assertEqual(a.data["shape"], "mixed")

    def test_kinds_map_to_plans(self):
        self.assertEqual({s for _, s in S.history_plan("mixed", 5)}, {"mixed"})
        self.assertEqual({s for _, s in S.history_plan("large", 5)}, {"large"})
        for kind, shape in (("stream", "stream"), ("tasks", "fanout"), ("subagent", "subagent"), ("crash", "crash"), ("docs", "mixed"), ("large", "large")):
            self.assertEqual(S.measured_plan(kind, 7, 3), [(7, shape), (8, shape), (9, shape)])
        self.assertEqual({s for _, s in S.history_plan("tasks", 5)}, {"mixed"})


class Cache(unittest.TestCase):
    def test_written_once_under_its_digest(self):
        plan = S.history_plan("mixed", 6) + S.measured_plan("mixed", 6, 2)
        with tempfile.TemporaryDirectory() as d:
            path, facts = S.cached(d, SEED, "repeating", plan, docs=3)
            self.assertEqual(os.path.basename(path), facts["sha256"] + ".script.json")
            self.assertEqual(facts["sha256"], S.build(SEED, "repeating", plan, docs=3).sha256)
            before = os.stat(path).st_mtime_ns
            again, facts2 = S.cached(d, SEED, "repeating", plan, docs=3)
            self.assertEqual((again, facts2), (path, facts))
            self.assertEqual(os.stat(path).st_mtime_ns, before)
            twin_path, twin_facts = S.cached(d, SEED, "varied", plan, docs=3)
            self.assertNotEqual(twin_path, path)
            self.assertEqual(twin_facts["variant"], "varied")
            with open(path, "w") as f:   # a file that is not what its name says is rebuilt
                f.write("{}")
            rebuilt, _ = S.cached(d, SEED, "repeating", plan, docs=3)
            with open(rebuilt, "rb") as f:
                self.assertEqual(f.read(), S.build(SEED, "repeating", plan, docs=3).dumps())

    def test_facts(self):
        s = S.build(SEED, "repeating", S.history_plan("compat", 4) + S.measured_plan("compat", 4, 2), shape="bench8")
        f = S.facts(s)
        self.assertEqual((f["sha256"], f["seed"], f["variant"], f["turns"], f["bytes"], f["first_turn"], f["last_turn"]), (s.sha256, SEED, "repeating", 6, len(s.dumps()), 0, 5))
        self.assertEqual(f["shapes"], {"bench0": 1, "bench1": 3, "bench8": 2})
        self.assertEqual((f["calls"], f["shape"], f["generator"]), (3 + 16, "bench8", S.GENERATOR))
        self.assertGreater(f["approx_tokens"], 0)


class CommandLine(unittest.TestCase):
    def test_module_writes_history_then_measured_turns(self):
        run = subprocess.run([sys.executable, "-m", "buffon.durable.script", "--kind", "mixed", "--history", "5", "--measured", "3", "--seed", "20261018", "--variant", "repeating"],
                             cwd=ROOT, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        d = json.loads(run.stdout)
        self.assertEqual([t["n"] for t in d["turns"]], list(range(8)))
        self.assertEqual(run.stdout, S.build(SEED, "repeating", S.history_plan("mixed", 5) + S.measured_plan("mixed", 5, 3), shape="mixed").dumps())

    def test_options(self):
        with tempfile.TemporaryDirectory() as dirname:
            out = os.path.join(dirname, "s.json")
            S.main(["--kind", "tasks", "--history", "4", "--measured", "2", "--measured-only", "--fanout-n", "64", "--out", out])
            with open(out) as f:
                d = json.load(f)
            self.assertEqual([t["n"] for t in d["turns"]], [4, 5])
            self.assertEqual(d["shape"], "fanout")
            self.assertEqual(calls_of(d["turns"][0])[0]["args"]["n"], 64)
            S.main(["--kind", "docs", "--history", "2", "--measured", "1", "--out", out])
            with open(out) as f:
                self.assertEqual(len(json.load(f)["docs"]), 1000)
            S.main(["--kind", "compat", "--history", "3", "--measured", "1", "--variant", "varied", "--out", out])
            with open(out) as f:
                d = json.load(f)
            self.assertEqual((d["variant"], d["shape"], [len(calls_of(t)) for t in d["turns"]]), ("varied", "bench8", [1, 1, 0, 8]))


if __name__ == "__main__":
    unittest.main()
