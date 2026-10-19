# SPDX-License-Identifier: Apache-2.0
"""The extension sweep (0, 5, 10, 50, 100) and the 4.2M-token rung of the session-size ladder."""
import hashlib
import os
import tempfile
import types
import unittest

from buffon import workloads
from buffon.arms import manifest
from buffon.fixtures import benchext, sessions
from buffon.workloads import longsession, overhead


class Sources(unittest.TestCase):
    def test_n_files_differ_only_in_their_number_and_match_the_templates_sha256(self):
        template = hashlib.sha256(open(benchext.TEMPLATE_PATH, "rb").read()).hexdigest()
        self.assertEqual(benchext.template_sha256(), template)
        for count in (5, 10, 50, 100):
            paths = benchext.make(tempfile.mkdtemp(), count)
            self.assertEqual(len(paths), count)
            self.assertEqual(len({open(p).read() for p in paths}), count)   # every one is its own tool and command
            for n, path in enumerate(paths, 1):
                text = open(path).read()
                self.assertIn(f'name: "bench_tool_{n:02d}"', text)
                self.assertIn(f'registerCommand("bench-{n:02d}"', text)
                self.assertEqual(hashlib.sha256(text.replace(f"{n:02d}", benchext.MARK).encode()).hexdigest(), template, path)

    def test_the_five_are_the_first_five_of_the_ten(self):
        five, ten = benchext.make(tempfile.mkdtemp(), 5), benchext.make(tempfile.mkdtemp(), 10)
        self.assertEqual([open(p).read() for p in five], [open(p).read() for p in ten[:5]])
        self.assertEqual([os.path.basename(p) for p in five], [os.path.basename(p) for p in ten[:5]])

    def test_the_same_count_gives_the_same_bytes(self):
        a, b = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.assertEqual([open(p).read() for p in benchext.make(a, 12)], [open(p).read() for p in benchext.make(b, 12)])

    def test_the_body_is_the_api_surface_the_hosts_are_checked_against(self):
        text = open(benchext.make(tempfile.mkdtemp(), 1)[0]).read()
        self.assertEqual(text.count("pi.registerTool("), 1)
        self.assertEqual(text.count("pi.registerCommand("), 1)
        self.assertEqual(text.count("pi.on("), 1)   # in a loop over the four events
        self.assertIn('["session_start", "before_agent_start", "tool_call", "turn_end"]', text)
        self.assertNotIn("import ", text)

    def test_the_commands_start_with_bench_so_the_rpc_poll_counts_them(self):
        self.assertTrue(all('registerCommand("bench-' in open(p).read() for p in benchext.make(tempfile.mkdtemp(), 3)))

    def test_no_numbered_copy_is_checked_in(self):
        self.assertEqual(sorted(os.listdir(os.path.dirname(benchext.TEMPLATE_PATH))), ["bench-ext.template.ts"])


class Eligibility(unittest.TestCase):
    def ctx(self):
        return types.SimpleNamespace(work=os.path.join(tempfile.mkdtemp(), "work"))

    def test_an_arm_without_its_own_realization_gets_the_generated_set_of_any_count(self):
        arm = manifest.load_arm("pi-node")
        for count in (5, 10, 100):
            self.assertEqual(len(overhead.sweep_extensions(self.ctx(), arm, count)), count)

    def test_ext5_is_a_strict_prefix_of_ext10(self):
        arm, ctx = manifest.load_arm("pi-node"), self.ctx()
        five, ten = overhead.sweep_extensions(ctx, arm, 5), overhead.sweep_extensions(ctx, arm, 10)
        self.assertEqual([open(p).read() for p in five], [open(p).read() for p in ten[:5]])
        self.assertLess(len(five), len(ten))

    def test_an_arm_with_its_own_realization_gets_the_prefix_of_its_list(self):
        for name in ("pig-go-packed", "pig-go-isolated"):
            arm = manifest.load_arm(name)
            own = arm.extension_paths()
            self.assertEqual(len(own), 10, name)
            self.assertEqual(overhead.sweep_extensions(self.ctx(), arm, 5), own[:5], name)
            self.assertEqual(overhead.sweep_extensions(self.ctx(), arm, 10), own, name)
            self.assertEqual([os.path.basename(p) for p in own[:5]], [f"bench-ext-{n:02d}" for n in range(1, 6)], name)
            with self.assertRaisesRegex(overhead.Skip, "lists 10 extensions: it cannot load 50"):
                overhead.sweep_extensions(self.ctx(), arm, 50)

    def test_an_arm_with_its_extensions_built_in_takes_only_the_count_it_was_built_with(self):
        arm = manifest.load_arm("pig-go-fused")
        self.assertEqual(overhead.sweep_extensions(self.ctx(), arm, 10), [])
        for count in (5, 50):
            with self.assertRaisesRegex(overhead.Skip, f"built into the binary, 10 of them: it cannot load {count}"):
                overhead.sweep_extensions(self.ctx(), arm, count)

    def test_a_sample_says_which_extensions_it_loaded(self):
        generated = overhead.extension_facts(manifest.load_arm("pi-node"), 5)
        self.assertEqual(generated, {"extensions_count": 5, "extensions_template_sha256": benchext.template_sha256()})
        own = overhead.extension_facts(manifest.load_arm("pig-go-packed"), 5)
        self.assertEqual(own, {"extensions_count": 5})

    def test_an_arm_that_cannot_load_extensions_is_skipped_with_its_own_reason_when_the_manifest_gives_one(self):
        for runner in ("print-ext5", "rpc-ext5", "print-ext10", "rpc-ext10", "print-ext50"):
            own = types.SimpleNamespace(pi_extensions="none", cannot_run={"extensions": "it has its own plugin API"})
            with self.assertRaisesRegex(overhead.Skip, "^it has its own plugin API$"):
                overhead.RUNNERS[runner](None, own)
            bare = types.SimpleNamespace(pi_extensions="none", cannot_run={})
            with self.assertRaisesRegex(overhead.Skip, "^it does not load Pi extensions$"):
                overhead.RUNNERS[runner](None, bare)
            partial = types.SimpleNamespace(pi_extensions="partial", cannot_run={})
            with self.assertRaisesRegex(overhead.Skip, "^it loads only part of Pi's extensions$"):
                overhead.RUNNERS[runner](None, partial)

    def test_every_sweep_workload_is_registered_with_a_state_and_a_cost(self):
        from buffon.up import catalog
        registry = workloads.load_all()
        self.assertEqual(overhead.SWEEP, (5, 50, 100))
        for kind in ("print", "rpc"):
            for n in overhead.SWEEP:
                wid = f"overhead/{kind}-ext{n}"
                self.assertIn(wid, registry)
                self.assertEqual(catalog.state_of(wid)[0], "partly wired")
                self.assertGreater(catalog.cost_of(wid), catalog.cost_of(f"overhead/{kind}"))

    def test_the_count_reaches_the_driver_through_the_registry(self):
        calls = []
        saved = overhead.one_print
        overhead.one_print = lambda ctx, arm, tools, ext, scenario, count=10: calls.append((tools, ext, scenario, count)) or {}
        try:
            overhead.RUNNERS["print-ext50"](None, None)
            overhead.RUNNERS["print-ext5"](None, None)
            overhead.RUNNERS["print-ext10"](None, None)
        finally:
            overhead.one_print = saved
        self.assertEqual(calls, [(0, True, "print-ext50", 50), (0, True, "print-ext5", 5), (0, True, "print-ext10", 10)])


class Rung(unittest.TestCase):
    def test_the_top_rung_is_about_4_2_million_tokens_by_the_mocks_own_count(self):
        d = tempfile.mkdtemp()
        turns = longsession.turns_for_tokens(d, longsession.LADDER_TOKENS, 1)
        _p, facts = sessions.cached(d, 100, 1)
        tokens = turns * facts["bytes"] / 100 / sessions.BYTES_PER_TOKEN
        self.assertAlmostEqual(tokens / longsession.LADDER_TOKENS, 1.0, delta=0.01)

    def test_the_declared_window_is_above_the_rung_so_nothing_compacts_before_it(self):
        self.assertGreater(longsession.LADDER_CONTEXT["context_window"], longsession.LADDER_TOKENS)
        self.assertEqual(longsession.LADDER_CONTEXT["compaction"], {"enabled": False})

    def test_the_rung_is_registered_and_is_a_resume_workload(self):
        w = workloads.load_all()["longsession/resume-4m2"]
        self.assertEqual(w.family, "longsession")
        self.assertIn("4.2M", w.description)


if __name__ == "__main__":
    unittest.main()
