"""The launch rerun plan (campaigns/launch-rerun.toml): who runs what, and what its dry run and estimate say."""
import json
import os
import tempfile
import unittest
from unittest import mock

from buffon import campaign
from buffon import workloads
from buffon.up import estimate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "campaigns", "launch-rerun.toml")
CORE_ARMS = {"pi-node", "pi-bun", "pibolt", "pig-tip", "pig-0.4.1", "rpi", "octet", "opencode-v2", "codex", "claude-code", "copilot"}
FOCUS_ARMS = ["pi-node", "pi-bun", "pig-tip", "pig-0.4.1", "pibolt"]
FOCUS = {"overhead/pty", "streaming/tui-prose", "streaming/print-prose", "overhead/print-ext5", "overhead/rpc-ext5", "overhead/print-ext10", "overhead/rpc-ext10", "longsession/resume-n", "longsession/resume-n-varied", "overhead/print-write"}


def load():
    plan, _sha = campaign.load_plan(PLAN)
    return plan, {f["name"]: f for f in plan["family"]}


class Plan(unittest.TestCase):
    def test_core_is_every_launch_harness_on_the_four_core_workloads_and_two_apis(self):
        _plan, fams = load()
        core = fams["core"]
        self.assertEqual(set(core["arms"]), CORE_ARMS)
        self.assertEqual(set(core["workloads"]), {"overhead/version", "overhead/print", "overhead/print-tools", "overhead/rpc"})
        # no `apis` key: `buffon run` then takes Chat Completions and Messages and adds Responses for the arm that speaks nothing else
        self.assertNotIn("apis", core)

    def test_the_focus_families_cover_the_focus_workloads_for_the_five_focus_harnesses_only(self):
        _plan, fams = load()
        focus = [f for n, f in fams.items() if n.startswith("focus-")]
        self.assertEqual({w for f in focus for w in f["workloads"]}, FOCUS)
        for f in focus:
            self.assertEqual(f["arms"], FOCUS_ARMS)
        self.assertEqual(fams["focus-streaming"]["params"], {"stream_n": 6000})   # 6,000 and 10 x 6,000 = 60,000 characters

    def test_every_family_runs_the_full_rounds_with_the_a_a_copy_of_every_arm(self):
        plan, fams = load()
        for name, fam in fams.items():
            argv = campaign.family_argv("run", fam, "", "/out", "pi-node", None)
            self.assertEqual(argv[argv.index("--rounds") + 1], "12", name)
            self.assertNotIn("--aa", argv, name)   # `buffon run` copies every arm by default

    def test_the_focus_families_stop_a_cell_once_its_answer_is_clear_and_core_takes_every_round(self):
        _plan, fams = load()
        for name, fam in fams.items():
            argv = campaign.family_argv("run", fam, "", "/out", "pi-node", None)
            self.assertEqual("--adaptive" in argv, name.startswith("focus-"), name)

    def test_the_streaming_workloads_run_both_sizes(self):
        from buffon.workloads import streaming
        ctx = type("C", (), {"opts": type("O", (), {"params": load()[1]["focus-streaming"]["params"]})()})()
        self.assertEqual([size for _label, size in streaming.sizes(ctx)], [6000, 60000])

    def test_every_workload_of_the_plan_is_registered(self):
        plan, _ = load()
        reg = workloads.load_all()
        for fam in plan["family"]:
            for w in fam["workloads"]:
                self.assertIn(w, reg)


class Estimate(unittest.TestCase):
    def setUp(self):
        self.plan, _ = load()
        self.probe = {"speed": 1.0}

    def test_every_family_has_an_estimate_and_the_total_is_their_sum(self):
        est = estimate.estimate_campaign(self.plan, self.probe, {})
        self.assertEqual(set(est["families"]), {f["name"] for f in self.plan["family"]})
        self.assertTrue(all(v > 0 for v in est["families"].values()))
        self.assertAlmostEqual(est["total_s"], sum(est["families"].values()))

    def test_more_rounds_or_a_slower_machine_take_longer_and_a_measured_history_wins(self):
        base = estimate.estimate_campaign(self.plan, self.probe, {})["total_s"]
        slower = estimate.estimate_campaign(self.plan, {"speed": 2.0}, {})["total_s"]
        self.assertGreater(slower, 1.5 * base)
        more = json.loads(json.dumps(self.plan))
        for fam in more["family"]:
            fam["rounds"] = 24
        self.assertGreater(estimate.estimate_campaign(more, self.probe, {})["total_s"], 1.8 * base)
        measured = estimate.estimate_campaign(self.plan, self.probe, {"longsession/resume-n": 60.0})["families"]["focus-longsession"]
        self.assertGreater(measured, estimate.estimate_campaign(self.plan, self.probe, {})["families"]["focus-longsession"])

    def test_the_varied_twin_is_counted(self):
        plan = json.loads(json.dumps(self.plan))
        fam = next(f for f in plan["family"] if f["name"] == "focus-longsession")
        alone = estimate.estimate_campaign(dict(plan, family=[dict(fam, workloads=["longsession/resume-n"])]), self.probe, {})["total_s"]
        both = estimate.estimate_campaign(dict(plan, family=[fam]), self.probe, {})["total_s"]
        self.assertAlmostEqual(both, 2 * alone)


class DryRun(unittest.TestCase):
    def notes(self, accepted):
        with tempfile.TemporaryDirectory() as home:
            with open(os.path.join(home, "probe.json"), "w") as f:
                json.dump({"speed": 1.0}, f)   # fresh: the dry run does not spawn a probe
            env = {"BUFFON_HOME": home, "BUFFON_ACCEPT_TERMS": accepted}
            with mock.patch.dict(os.environ, env):
                return campaign.dry_run_notes(load()[0])

    def test_the_dry_run_names_the_vendor_terms_still_to_accept_and_gives_an_estimate_per_family(self):
        notes = self.notes("")
        self.assertIn("BUFFON_ACCEPT_TERMS=claude-code,copilot", notes[0])
        self.assertEqual(len(notes), 1 + 4 + 1)
        self.assertTrue(any(n.startswith("expected measuring time core:") for n in notes))

    def test_accepted_terms_are_not_asked_for_again(self):
        self.assertTrue(self.notes("claude-code,copilot")[0].endswith("accepted"))
        self.assertIn("set BUFFON_ACCEPT_TERMS=copilot ", self.notes("claude-code")[0] + " ")


if __name__ == "__main__":
    unittest.main()
