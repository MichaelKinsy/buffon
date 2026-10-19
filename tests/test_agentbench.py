import unittest

from buffon.agentbench import Protocol, expected_runs, paired_result, sem_overlap


def proto(**kw):
    return Protocol(benchmark="tb@2", arms=["pi", "pig"], cases=["a", "b", "c", "d"], models=["m1"], runs=2, **kw)


def obs(arm, case, run, passed, **kw):
    return {"arm": arm, "case": case, "model": "m1", "run": run, "passed": passed, "error": None, "tokens": 10, "cost_usd": 0.1, "wall_s": 3.0, **kw}


def full(pass_pi, pass_pig):
    out = []
    for case in "abcd":
        for run in range(2):
            out.append(obs("pi", case, run, (case, run) in pass_pi))
            out.append(obs("pig", case, run, (case, run) in pass_pig))
    return out


class Protocols(unittest.TestCase):
    def test_the_digest_changes_with_any_declared_input_and_not_with_listing_order(self):
        base = proto().digest()
        self.assertEqual(Protocol("tb@2", ["pi", "pig"], ["d", "c", "b", "a"], ["m1"], runs=2).digest(), base)
        self.assertNotEqual(proto(params={"max_turns": 50}).digest(), base)
        self.assertNotEqual(Protocol("tb@2", ["pi", "pig"], ["a", "b", "c", "d"], ["m1"], runs=3).digest(), base)

    def test_the_arm_order_alternates_across_runs_and_cases(self):
        orders = [r["order"][0] for r in expected_runs(proto())]
        self.assertEqual(set(orders), {"pi", "pig"})
        self.assertEqual(len(expected_runs(proto())), 4 * 1 * 2)

    def test_a_degenerate_protocol_is_refused(self):
        for bad in (Protocol("x", ["pi"], ["a"], ["m"]), Protocol("x", ["pi", "pi"], ["a"], ["m"]), Protocol("x", ["pi", "pig"], [], ["m"]), Protocol("x", ["pi", "pig"], ["a", "a"], ["m"])):
            with self.assertRaises(ValueError):
                bad.validate()


class Lift(unittest.TestCase):
    def test_the_headline_is_the_paired_difference_and_counts_discordant_pairs(self):
        every = {(c, r) for c in "abcd" for r in range(2)}
        result = paired_result(proto(), full(every, every - {("a", 0), ("b", 1)}))
        h = result["results"]["pig"]["headline"]
        self.assertEqual((h["pairs"], h["reference_pass"], h["arm_pass"], h["only_reference"], h["only_arm"]), (8, 8, 6, 2, 0))
        self.assertAlmostEqual(h["lift"], -0.25)
        self.assertEqual(h["mcnemar_p"], 0.5)      # two discordant pairs, both for the reference: exact McNemar p = 2 * (1/4)

    def test_one_blocked_pair_withholds_the_headline(self):
        data = full({("a", 0)}, {("a", 0)})
        data = [o for o in data if not (o["arm"] == "pig" and o["case"] == "c" and o["run"] == 1)]    # a missing arm
        result = paired_result(proto(), data)["results"]["pig"]
        self.assertIsNone(result["headline"])
        self.assertEqual(result["blocked"], [{"case": "c", "model": "m1", "run": 1, "reason": "pig has no observation"}])

    def test_an_errored_or_duplicate_arm_blocks_and_an_error_is_not_a_failure(self):
        data = full({("a", 0)}, {("a", 0)})
        data[0]["error"] = "container died"
        data.append(dict(data[3]))
        reasons = {b["reason"] for b in paired_result(proto(), data)["results"]["pig"]["blocked"]}
        self.assertIn("pi errored: container died", reasons)
        self.assertIn("pig has 2 observations", reasons)

    def test_unavailable_telemetry_is_counted_not_zeroed(self):
        data = full(set(), set())
        data[1]["tokens"] = None
        data[2]["cost_usd"] = None
        u = paired_result(proto(), data)["results"]["pig"]["unavailable"]
        self.assertEqual((u["tokens"], u["cost_usd"], u["wall_s"]), (1, 1, 0))


class Sem(unittest.TestCase):
    def test_intervals_that_overlap_and_that_do_not(self):
        self.assertTrue(sem_overlap([10, 12, 11, 13], [11, 12, 13, 12]))
        self.assertFalse(sem_overlap([10, 10.1, 9.9, 10], [20, 20.1, 19.9, 20]))

    def test_a_single_value_is_unknown_not_overlap(self):
        self.assertIsNone(sem_overlap([1.0], [1.0, 2.0]))


class Cli(unittest.TestCase):
    def test_plan_and_result_write_the_files_and_the_markdown_says_when_the_headline_is_withheld(self):
        import json
        import os
        import tempfile
        from buffon.agentbench import cli
        d = tempfile.mkdtemp()
        pf = os.path.join(d, "p.json")
        with open(pf, "w") as f:
            json.dump({"benchmark": "tb@2", "arms": ["pi", "pig"], "cases": ["a", "b"], "models": ["m1"], "runs": 1}, f)
        p = cli.plan(pf, os.path.join(d, "o"))
        self.assertEqual(json.load(open(os.path.join(d, "o", "protocol.json")))["digest"], p.digest())
        self.assertEqual(len(json.load(open(os.path.join(d, "o", "expected-runs.json")))), 2)
        ob = os.path.join(d, "obs.jsonl")
        with open(ob, "w") as f:
            f.write(json.dumps({"arm": "pi", "case": "a", "model": "m1", "run": 0, "passed": True}) + "\n")
        cli.result(pf, ob, os.path.join(d, "r"))
        text = open(os.path.join(d, "r", "result.md")).read()
        self.assertIn("headline withheld", text)
        self.assertIn("pig has no observation", text)
