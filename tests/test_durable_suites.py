# SPDX-License-Identifier: Apache-2.0
"""The durable project suites in the registry: the Pi pin is v1.3.0 and every Pi durable benchmark script is registered under its own name, durable-bench is registered unchanged with no licence, and the
attribution line is in NOTICE. Digest checks against real checkouts run when the checkout is given by env (BUFFON_PI_MIRROR at PI_COMMIT, BUFFON_DURABLE_BENCH_CHECKOUT at DURABLE_BENCH_COMMIT)."""
import os
import unittest

from buffon.external import guard, suites

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PI_MIRROR = os.environ.get("BUFFON_PI_MIRROR", "")
DURABLE_BENCH_CHECKOUT = os.environ.get("BUFFON_DURABLE_BENCH_CHECKOUT", "")
PI_SCRIPTS = {"durable-storage": "bench:storage", "durable-storage-memory": "bench:storage:memory", "durable-tool-output": "bench:tool-output", "durable-nested-tools": "bench:nested-tools",
              "durable-nested-images": "bench:nested-images", "durable-scheduler-fanout": "bench:scheduler-fanout", "durable-scheduler-memory": "bench:scheduler-memory",
              "durable-document-cache": "bench:document-cache", "durable-document-append": "bench:document-append", "durable-codemode": "bench:codemode"}


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


class Pins(unittest.TestCase):
    def test_the_pins_are_pi_v1_3_0_public_pig_main_and_the_forks_main(self):
        self.assertEqual(suites.PI_COMMIT, "71023aec1546d6d677a65669c5665c0927ce0dd0")
        self.assertEqual(suites.PIG_COMMIT, "e84d2349aed2525a49337142ac2be18405ee8014")
        self.assertEqual(suites.DURABLE_BENCH_COMMIT, "e9abffab0a1056cf00c71a34ce83c7f41a746098")

    def test_the_docs_name_each_pin(self):
        text = read("docs/EXTERNAL.md")
        for pin in (suites.PI_COMMIT, suites.PIG_COMMIT, suites.DURABLE_BENCH_COMMIT):
            self.assertIn(pin, text)
        self.assertIn("v1.3.0", text)

    def test_every_repository_key_a_target_uses_has_a_pin_and_a_repository_entry(self):
        for s in suites.SUITES.values():
            for name, t in s.targets.items():
                self.assertIn(t.repo, s.pins, f"{s.id}/{name}")
                self.assertIn(t.repo, suites.REPOSITORIES, f"{s.id}/{name}")
                self.assertTrue(t.manifest, f"{s.id}/{name} has no digests")


class PiBenchmarks(unittest.TestCase):
    def test_each_pi_durable_script_is_registered_in_the_durable_section_under_its_own_name(self):
        for sid, script in PI_SCRIPTS.items():
            s = suites.get(sid)
            self.assertEqual((s.section, s.pins["pi"], s.licence), ("durable", suites.PI_COMMIT, "MIT"), sid)
            self.assertEqual(s.targets["pi-node"].argv, ("npm", "run", script), sid)
            self.assertEqual(s.targets["pi-node"].cwd, "packages/durable", sid)

    def test_each_script_is_a_script_of_the_pinned_package_manifest_digest(self):
        for sid in PI_SCRIPTS:
            paths = [rel for rel, _ in suites.get(sid).targets["pi-node"].manifest]
            self.assertIn("packages/durable/package.json", paths, sid)
        self.assertTrue(any(rel.endswith("test/nested-tools-bench.ts") for rel, _ in suites.get("durable-nested-tools").targets["pi-node"].manifest))
        for sid in ("durable-scheduler-memory", "durable-document-cache"):
            self.assertTrue(any(rel.endswith("test/heap-retained.ts") for rel, _ in suites.get(sid).targets["pi-node"].manifest), sid)   # the helper these two import by relative path

    def test_only_the_two_console_table_benchmarks_have_a_parser(self):
        self.assertEqual({sid for sid in PI_SCRIPTS if suites.get(sid).targets["pi-node"].table}, {"durable-storage-memory", "durable-tool-output"})

    def test_the_two_pig_targets_are_kept(self):
        self.assertEqual(sorted(suites.get("durable-storage").targets), ["pi-node", "pig-native", "pig-tinygo"])

    @unittest.skipUnless(PI_MIRROR, "set BUFFON_PI_MIRROR to Pi's checkout at PI_COMMIT to check every Pi durable digest against the files")
    def test_every_recorded_pi_digest_equals_the_file_at_the_pin(self):
        for sid in PI_SCRIPTS:
            guard.verify(PI_MIRROR, suites.get(sid).targets["pi-node"].manifest, sid)


class DurableBench(unittest.TestCase):
    def test_durable_bench_is_registered_with_no_licence_in_the_durable_section_at_the_forks_commit(self):
        for sid in ("durable-bench", "durable-bench-harness"):
            s = suites.get(sid)
            self.assertEqual((s.licence, s.section, s.live, s.pins), ("none", "durable", False, {"durable-bench": suites.DURABLE_BENCH_COMMIT}), sid)
            self.assertIn("no licence", s.notes)
            self.assertEqual(suites.REPOSITORIES["durable-bench"]["url"], "https://github.com/badlogic/durable-bench")
            self.assertEqual(suites.REPOSITORIES["durable-bench"]["licence"], "none")

    def test_the_main_benchmark_runs_the_suites_own_commands_for_pi(self):
        s = suites.get("durable-bench")
        self.assertEqual(sorted(s.targets), ["pi-node", "pi-node-npm"])
        _, head = suites.argv_for(s, "pi-node")
        _, npm = suites.argv_for(s, "pi-node-npm")
        self.assertEqual(head[:2], ["sh", "-c"])
        self.assertIn("bun run seed pi-head && bun run bench pi-head && bun run report && cat results/results.jsonl", head[2])
        self.assertIn(suites.PI_COMMIT, head[2])   # the ../pi checkout the pi-head target builds from must be the Pi pin
        self.assertEqual(npm[2], "rm -rf results fixtures && bun run seed pi && bun run bench pi && bun run report && cat results/results.jsonl")
        self.assertNotIn("{", head[2] + npm[2])   # argv entries with a brace go through str.format

    def test_the_main_benchmark_pins_its_lock_its_sources_and_every_target_file(self):
        paths = {rel for rel, _ in suites.get("durable-bench").targets["pi-node"].manifest}
        for needed in ("package.json", "bun.lock", "bench/run.ts", "bench/seed.ts", "bench/targets.ts", "bench/report.ts", "src/pi.ts", "src/pi-head.ts", "src/plan.ts", "src/serve.ts"):
            self.assertIn(needed, paths)
        guard.check_entries(suites.get("durable-bench").targets["pi-node"].manifest, "durable-bench")

    def test_the_harness_benchmark_runs_npm_run_bench_in_harness_for_pi_only(self):
        t = suites.get("durable-bench-harness").targets["pi-node"]
        self.assertEqual((t.cwd, t.argv[:2]), ("harness", ("sh", "-c")))
        self.assertIn("SYSTEMS='pi pi-head' npm run bench", t.argv[2])
        self.assertTrue(all(rel.startswith("harness/") for rel, _ in t.manifest))
        self.assertIn(("harness/pi-head.sha", "c193190883cd4b162aca6a68852fbcd270111bffa732abe636588848a2769308"), t.manifest)

    def test_the_notes_carry_the_calibration_line(self):
        self.assertIn("host factor", suites.get("durable-bench").notes)

    @unittest.skipUnless(DURABLE_BENCH_CHECKOUT, "set BUFFON_DURABLE_BENCH_CHECKOUT to a clone of github.com/badlogic/durable-bench at DURABLE_BENCH_COMMIT")
    def test_every_recorded_durable_bench_digest_equals_the_file_at_the_pin(self):
        for sid in ("durable-bench", "durable-bench-harness"):
            for target in suites.get(sid).targets.values():
                guard.verify(DURABLE_BENCH_CHECKOUT, target.manifest, sid)


class Attribution(unittest.TestCase):
    def test_notice_has_the_compat_lane_line_exactly(self):
        self.assertIn("The compat lane is adapted from durable-bench (github.com/clavia-labs/durable-bench), used with permission.", read("NOTICE"))

    def test_the_docs_cite_the_published_figures_as_text_with_their_hosts(self):
        text = read("docs/EXTERNAL.md")
        for cited in ("365 ms", "313 ms", "Apple M5", "i9-13900", "2026-10-06"):
            self.assertIn(cited, text)
