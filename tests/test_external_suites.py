# SPDX-License-Identifier: Apache-2.0
"""External suites as families: the import guard refuses an unpinned or modified suite, rows keep the suite's own names and units, a plan starts nothing, and a published import must match its table."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from buffon.external import guard, published, results, rows, runner, suites
from tests.test_external import FIXTURE_FILE_SHA, FIXTURE_ID, PUBLISHED, Done, fixture_suite, make_checkout, write

PI_MIRROR = os.environ.get("BUFFON_PI_MIRROR", "")       # Pi's checkout at its pin, with packages/ (the .upstream/current mirror)
PIG_CHECKOUT = os.environ.get("BUFFON_PIG_CHECKOUT", "")  # a PiG checkout at PIG pin, with durable/
PI_BOLT_CHECKOUT = os.environ.get("BUFFON_PI_BOLT_CHECKOUT", "")  # a checkout of github.com/opensec-git/Pi-Bolt at PI_BOLT_COMMIT
TABLE_ID = "fixture-table"
TABLE = """┌─────────┬──────────┬──────────────────┐
│ (index) │ backend  │ RSS after seed MiB │
├─────────┼──────────┼──────────────────┤
│    0    │ 'memory' │       12.5       │
│    1    │ 'sqlite' │        7         │
└─────────┴──────────┴──────────────────┘
"""
# The Metrics fields of Pi's tool-output bench at the pin (packages/durable/test/tool-output-bench.ts, type Metrics).
TOOL_OUTPUT_FIELDS = {"ms", "liveCommits", "liveOpKiB", "outputSets", "commitP50Ms", "commitP99Ms", "midRoundKiB", "replayMs", "finalKiB", "peakRssMiB", "heapAfterGcMiB"}


def tree(files):
    """Write {relpath: bytes} under a new root; return (root, manifest) where manifest pins each file's sha256."""
    root, manifest = tempfile.mkdtemp(), []
    for rel, data in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        manifest.append((rel, hashlib.sha256(data).hexdigest()))
    return root, tuple(manifest)


def flip_first_byte(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())
    data[0] ^= 0x01
    with open(path, "wb") as f:
        f.write(bytes(data))


class Guard(unittest.TestCase):
    def test_an_unpinned_suite_is_refused(self):
        root, _ = tree({"a.ts": b"x\n"})
        with self.assertRaises(guard.Refused) as caught:
            guard.verify(root, (), "some-suite")
        self.assertIn("unpinned", str(caught.exception))

    def test_a_pinned_file_changed_by_one_byte_is_refused_and_named(self):
        root, manifest = tree({"suite/run.ts": b"bench('x', () => 1)\n", "suite/config.ts": b"export default {}\n"})
        self.assertEqual(set(guard.verify(root, manifest, "s")), {"suite/run.ts", "suite/config.ts"})
        flip_first_byte(os.path.join(root, "suite/run.ts"))
        with self.assertRaises(guard.Refused) as caught:
            guard.verify(root, manifest, "s")
        self.assertIn("suite/run.ts is modified", str(caught.exception))

    def test_a_pinned_file_that_is_missing_is_refused(self):
        root, manifest = tree({"suite/run.ts": b"x\n"})
        os.remove(os.path.join(root, "suite/run.ts"))
        with self.assertRaises(guard.Refused) as caught:
            guard.verify(root, manifest, "s")
        self.assertIn("missing", str(caught.exception))

    def test_every_recorded_digest_is_sha256_and_every_pin_is_a_full_commit(self):
        for s in suites.SUITES.values():
            for t in s.targets.values():
                guard.check_entries(t.manifest, s.id)
            for pin in s.pins.values():
                self.assertTrue(pin is None or len(pin) == 40, s.id)

    def test_a_malformed_manifest_entry_is_refused_at_definition(self):
        with self.assertRaises(ValueError):
            guard.check_entries((("../escape.ts", "0" * 64),), "s")
        with self.assertRaises(ValueError):
            guard.check_entries((("ok.ts", "abc"),), "s")


class RealSuiteFiles(unittest.TestCase):
    """The recorded digests equal the pinned upstream files, and one changed byte in a copy of a real suite file stops the guard. Runs when the pinned checkout is given by env."""

    @unittest.skipUnless(PI_MIRROR, "set BUFFON_PI_MIRROR to Pi's checkout at its pin (the .upstream/current mirror) to verify the recorded Pi digests")
    def test_the_recorded_pi_digests_equal_the_pinned_files(self):
        for name in ("durable-storage", "durable-storage-memory", "durable-tool-output", "pi-evals-offline"):
            target = suites.get(name).targets["pi-node"]
            guard.verify(PI_MIRROR, target.manifest, name)

    @unittest.skipUnless(PI_MIRROR, "set BUFFON_PI_MIRROR to Pi's checkout at its pin to run the one-byte mutation on a real suite file")
    def test_one_changed_byte_in_a_copy_of_the_pinned_storage_bench_fails_the_guard(self):
        target = suites.get("durable-storage").targets["pi-node"]
        root = tempfile.mkdtemp()
        for rel, _ in target.manifest:
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            shutil.copyfile(os.path.join(PI_MIRROR, rel), os.path.join(root, rel))
        guard.verify(root, target.manifest, "durable-storage")
        flip_first_byte(os.path.join(root, f"{target.cwd}/test/storage.bench.ts"))
        with self.assertRaises(guard.Refused) as caught:
            guard.verify(root, target.manifest, "durable-storage")
        self.assertIn("storage.bench.ts is modified", str(caught.exception))

    @unittest.skipUnless(PIG_CHECKOUT, "set BUFFON_PIG_CHECKOUT to a PiG checkout at PIG pin to verify the recorded PiG digest")
    def test_the_recorded_pig_digest_equals_the_pinned_file(self):
        guard.verify(PIG_CHECKOUT, suites.get("durable-storage").targets["pig-native"].manifest, "durable-storage")

    @unittest.skipUnless(PI_BOLT_CHECKOUT, "set BUFFON_PI_BOLT_CHECKOUT to a Pi-Bolt checkout at PI_BOLT_COMMIT to verify the recorded Pi-Bolt digests")
    def test_the_recorded_pi_bolt_digests_equal_the_pinned_files(self):
        manifest = suites.get("pi-bolt-benchmark").targets["build"].manifest
        self.assertEqual(len(manifest), len(suites.PI_BOLT_FILES))
        guard.verify(PI_BOLT_CHECKOUT, manifest, "pi-bolt-benchmark")

    @unittest.skipUnless(PI_BOLT_CHECKOUT, "set BUFFON_PI_BOLT_CHECKOUT to a Pi-Bolt checkout at PI_BOLT_COMMIT to check the pinned list is complete")
    def test_every_local_module_and_model_script_a_pi_bolt_suite_runs_is_pinned(self):
        # review: large_write.py starts fake_model_stress.py and e2e_tools.py fake_model_tools.py; neither was pinned, so a changed copy passed the guard
        import re
        pinned = {rel for rel, _ in suites.PI_BOLT_FILES}
        bench = os.path.join(PI_BOLT_CHECKOUT, "bench")
        local = {name[:-3] for name in os.listdir(bench) if name.endswith(".py")}
        todo, seen = ["bench/benchmark.py", "bench/large_write.py", "bench/long_session.py", "bench/e2e_tools.py"], set()
        while todo:
            rel = todo.pop()
            if rel in seen:
                continue
            seen.add(rel)
            with open(os.path.join(PI_BOLT_CHECKOUT, rel)) as f:
                text = f.read()
            for mod in re.findall(r"^(?:from|import) (\w+)", text, re.M):
                if mod in local:
                    todo.append(f"bench/{mod}.py")
            for script in re.findall(r"script=[\"'](\w+\.py)[\"']", text):
                todo.append(f"bench/{script}")
        self.assertEqual(sorted(seen - pinned), [])

    @unittest.skipUnless(PI_BOLT_CHECKOUT, "set BUFFON_PI_BOLT_CHECKOUT to a Pi-Bolt checkout at PI_BOLT_COMMIT to run the one-byte mutation on a real suite file")
    def test_one_changed_byte_in_a_copy_of_the_pinned_benchmark_fails_the_guard(self):
        manifest = suites.get("pi-bolt-benchmark").targets["build"].manifest
        root = tempfile.mkdtemp()
        for rel, _ in manifest:
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            shutil.copyfile(os.path.join(PI_BOLT_CHECKOUT, rel), os.path.join(root, rel))
        guard.verify(root, manifest, "pi-bolt-benchmark")
        flip_first_byte(os.path.join(root, "bench/benchmark.py"))
        with self.assertRaises(guard.Refused) as caught:
            guard.verify(root, manifest, "pi-bolt-benchmark")
        self.assertIn("bench/benchmark.py is modified", str(caught.exception))


class Rows(unittest.TestCase):
    def test_the_table_keeps_the_names_and_the_units_the_suite_prints(self):
        parsed = rows.parse_console_table(TABLE)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(set(parsed[0]), {"(index)", "backend", "RSS after seed MiB"})
        self.assertEqual(parsed[0]["backend"], "'memory'")
        self.assertEqual(parsed[1]["RSS after seed MiB"], "7")

    def test_a_row_with_the_wrong_cell_count_is_refused(self):
        with self.assertRaises(ValueError):
            rows.parse_console_table("│ a │ b │\n│ 1 │\n")

    def test_output_without_a_table_gives_no_rows(self):
        self.assertEqual(rows.parse_console_table("Storage footprint\nno table\n"), [])

    def test_tool_output_units_cover_exactly_the_fields_of_the_suites_metrics_type(self):
        self.assertEqual({name for name, _ in suites.get("durable-tool-output").targets["pi-node"].units}, TOOL_OUTPUT_FIELDS)


class TableDone:
    returncode, stdout, stderr = 0, TABLE, ""


class Runner(unittest.TestCase):
    def setUp(self):
        os.environ["BUFFON_LOCK_FILE"] = os.path.join(tempfile.mkdtemp(), "lock")
        self.addCleanup(os.environ.pop, "BUFFON_LOCK_FILE", None)
        suites.SUITES[FIXTURE_ID] = fixture_suite()
        self.addCleanup(suites.SUITES.pop, FIXTURE_ID, None)
        suites.SUITES[TABLE_ID] = suites.Suite(TABLE_ID, "fixture table suite", "MIT", targets={"pi-node": suites.Target("pi", "packages/durable", ("npm", "run", "x"), table="console-table",
                                               units=(("RSS after seed MiB", "MiB"),), manifest=(("packages/durable/f", FIXTURE_FILE_SHA),))}, pins={"pi": None})
        self.addCleanup(suites.SUITES.pop, TABLE_ID, None)

    def test_a_run_records_its_pin_manifest_units_and_rows_as_printed(self):
        d, head = make_checkout()
        out = tempfile.mkdtemp()
        doc = runner.run(TABLE_ID, "pi-node", d, out, commit=head, runner=lambda argv, **k: TableDone(), foreign_locks=())
        self.assertEqual(doc["pins"], {"pi": head})
        self.assertEqual((doc["pin_source"], doc["manifest"]), ("caller", {"packages/durable/f": FIXTURE_FILE_SHA}))
        self.assertEqual((doc["units"], doc["rows"]), ({"RSS after seed MiB": "MiB"}, 2))
        with open(os.path.join(out, "rows.jsonl")) as f:
            self.assertEqual(json.loads(f.readline())["RSS after seed MiB"], "12.5")

    def test_a_run_at_the_suites_own_pin_says_so(self):
        d, head = make_checkout()
        suites.SUITES[TABLE_ID] = suites.Suite(TABLE_ID, "x", "MIT", targets=suites.SUITES[TABLE_ID].targets, pins={"pi": head})
        doc = runner.run(TABLE_ID, "pi-node", d, tempfile.mkdtemp(), runner=lambda argv, **k: Done(), foreign_locks=())
        self.assertEqual(doc["pin_source"], "suite")

    def test_a_suite_committed_with_a_changed_byte_is_refused_even_at_its_own_head(self):
        d, _ = make_checkout()
        write(d, "packages/durable/f", "2\n")
        subprocess.run(["git", "-C", d, "commit", "-q", "-am", "changed"], check=True)
        head2 = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        calls = []
        with self.assertRaises(runner.Refused) as caught:
            runner.run(FIXTURE_ID, "pi-node", d, tempfile.mkdtemp(), commit=head2, runner=lambda argv, **k: calls.append(argv) or Done(), foreign_locks=())
        self.assertIn("is modified", str(caught.exception))
        self.assertEqual(calls, [])

    def test_a_plan_starts_nothing_and_takes_no_lock(self):
        d, head = make_checkout()
        doc = runner.plan(FIXTURE_ID, "pi-node", d, commit=head)
        self.assertEqual((doc["verdict"], doc["refusals"], doc["started"]), ("would run", [], False))
        self.assertEqual(doc["files"]["packages/durable/f"]["state"], "ok")
        self.assertFalse(os.path.exists(os.environ["BUFFON_LOCK_FILE"]))

    def test_a_pi_bolt_plan_without_its_files_names_the_missing_file_and_the_pin(self):
        d, _ = make_checkout()
        doc = runner.plan("pi-bolt-benchmark", "build", d, arm="pig", command="out/pig")
        self.assertEqual(doc["verdict"], "refused")
        self.assertTrue(any("bench/benchmark.py is missing" in r for r in doc["refusals"]), doc["refusals"])
        self.assertTrue(any("the pin is 13ccac32" in r for r in doc["refusals"]), doc["refusals"])
        self.assertFalse(doc["started"])

    def test_a_plan_for_a_live_suite_without_live_is_refused(self):
        d, head = make_checkout()
        doc = runner.plan("pi-evals", "pi-node", d, commit=head)
        self.assertEqual(doc["verdict"], "refused")
        self.assertTrue(any("--live" in r for r in doc["refusals"]))

    def test_an_untracked_file_in_the_checkout_refuses_the_run_but_an_ignored_one_does_not(self):
        # review: Pi's bench config includes test/**/*.bench.ts, so an untracked bench file would join the suite without touching a pinned file
        d, head = make_checkout()
        os.makedirs(os.path.join(d, "packages/durable/test"))
        write(d, "packages/durable/test/extra.bench.ts", "bench('x', () => 1)\n")
        calls = []
        with self.assertRaises(runner.Refused) as caught:
            runner.run(FIXTURE_ID, "pi-node", d, tempfile.mkdtemp(), commit=head, runner=lambda argv, **k: calls.append(argv) or Done(), foreign_locks=())
        self.assertIn("untracked", str(caught.exception))
        self.assertEqual(calls, [])
        self.assertTrue(any("untracked" in r for r in runner.plan(FIXTURE_ID, "pi-node", d, commit=head)["refusals"]))
        os.remove(os.path.join(d, "packages/durable/test/extra.bench.ts"))
        write(d, ".gitignore", "node_modules/\n")
        subprocess.run(["git", "-C", d, "add", ".gitignore"], check=True)
        subprocess.run(["git", "-C", d, "commit", "-q", "-m", "ignore"], check=True)
        head2 = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        os.makedirs(os.path.join(d, "node_modules/vitest"))
        write(d, "node_modules/vitest/package.json", "{}\n")
        runner.run(FIXTURE_ID, "pi-node", d, tempfile.mkdtemp(), commit=head2, runner=lambda argv, **k: Done(), foreign_locks=())

    def test_commit_given_as_key_equals_sha_is_the_sha(self):
        # review: docs/EXTERNAL.md and the refusal say `--commit pi=<sha>`; that string used to be compared with HEAD as it is
        d, head = make_checkout()
        self.assertEqual(runner.plan(FIXTURE_ID, "pi-node", d, commit=f"pi={head}")["verdict"], "would run")
        doc = runner.run(FIXTURE_ID, "pi-node", d, tempfile.mkdtemp(), commit=f"pi={head[:12]}", runner=lambda argv, **k: Done(), foreign_locks=())
        self.assertEqual((doc["commit"], doc["pin_source"]), (head, "caller"))
        with self.assertRaises(runner.Refused) as caught:
            runner.run(FIXTURE_ID, "pi-node", d, tempfile.mkdtemp(), commit=f"pig={head}", runner=lambda argv, **k: Done(), foreign_locks=())
        self.assertIn("not this target's repository", str(caught.exception))

    def test_a_table_the_parser_cannot_read_is_recorded_and_the_run_is_kept(self):
        class Broken:
            returncode, stdout, stderr = 0, "│ a │ b │\n│ 1 │\n", ""
        d, head = make_checkout()
        out = tempfile.mkdtemp()
        doc = runner.run(TABLE_ID, "pi-node", d, out, commit=head, runner=lambda argv, **k: Broken(), foreign_locks=())
        self.assertIsNone(doc["rows"])
        self.assertIn("cells", doc["rows_error"])
        with open(os.path.join(out, "external-suite.json")) as f:
            self.assertEqual(json.load(f)["exit"], 0)
        self.assertFalse(os.path.exists(os.path.join(out, "rows.jsonl")))
        self.assertIn("table not parsed", "\n".join(runner.section([out])))

    def test_the_report_says_when_the_commit_is_the_callers_and_not_the_suites_pin(self):
        d, head = make_checkout()
        caller = tempfile.mkdtemp()
        runner.run(TABLE_ID, "pi-node", d, caller, commit=head, runner=lambda argv, **k: TableDone(), foreign_locks=())
        suites.SUITES[TABLE_ID] = suites.Suite(TABLE_ID, "x", "MIT", targets=suites.SUITES[TABLE_ID].targets, pins={"pi": head})
        pinned = tempfile.mkdtemp()
        runner.run(TABLE_ID, "pi-node", d, pinned, runner=lambda argv, **k: TableDone(), foreign_locks=())
        lines = runner.section([caller, pinned])
        row = {line.rsplit("`", 2)[-2]: line for line in lines if line.startswith(f"| {TABLE_ID} ")}
        self.assertIn("caller's commit", row[os.path.basename(caller)])
        self.assertNotIn("caller's commit", row[os.path.basename(pinned)])


class Published(unittest.TestCase):
    def files(self):
        return [os.path.join(PUBLISHED, "files", name) for name in sorted(os.listdir(os.path.join(PUBLISHED, "files")))]

    def test_the_committed_files_import_because_they_match_the_published_table(self):
        out = os.path.join(tempfile.mkdtemp(), "o")
        doc = published.import_family("pi-bolt-published-headless", self.files(), out)
        self.assertEqual((doc["commit"], doc["licence"].split()[0]), ("13ccac32afb94366fb8d3e15aff1dd7bb234fefa", "MIT"))

    def test_one_changed_published_row_refuses_the_import_and_leaves_nothing_behind(self):
        src = tempfile.mkdtemp()
        paths = []
        for path in self.files():
            dest = os.path.join(src, os.path.basename(path))
            shutil.copyfile(path, dest)
            paths.append(dest)
        lines = []
        with open(os.path.join(src, "benchmark.jsonl")) as f:
            for line in f:
                row = json.loads(line)
                if row.get("build") == "pi-bolt" and row.get("scenario") == "headless":
                    row["cpu_ms"] = row["cpu_ms"] + 100
                lines.append(json.dumps(row) + "\n")
        with open(os.path.join(src, "benchmark.jsonl"), "w") as f:
            f.writelines(lines)
        out = os.path.join(tempfile.mkdtemp(), "o")
        with self.assertRaises(ValueError) as caught:
            published.import_family("pi-bolt-published-headless", paths, out)
        self.assertIn("is not the file at the pin", str(caught.exception))
        self.assertFalse(os.path.exists(out))

    def copy_with(self, edit):
        src = tempfile.mkdtemp()
        paths = []
        for path in self.files():
            dest = os.path.join(src, os.path.basename(path))
            shutil.copyfile(path, dest)
            paths.append(dest)
        with open(os.path.join(src, "benchmark.jsonl")) as f:
            rows_in = [json.loads(line) for line in f]
        with open(os.path.join(src, "benchmark.jsonl"), "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in edit(rows_in))
        return paths

    def test_a_median_that_rounds_to_another_whole_ms_is_refused(self):
        # review: the table prints whole ms; pi-bolt's median 79.567 prints as 80, never as 79 (a 1 ms tolerance accepted 79)
        out = os.path.join(tempfile.mkdtemp(), "o")
        doc = published.import_family("pi-bolt-published-headless", self.files(), out)
        family = dict(published.FAMILIES["pi-bolt-published-headless"], expect={("benchmark.jsonl", "headless"): {"pi-bolt": 79}})
        self.assertTrue(any("not the published 79" in p for p in published.check_table(out, doc, family)))
        family["expect"] = {("benchmark.jsonl", "headless"): {"pi-bolt": 80}}
        self.assertEqual(published.check_table(out, doc, family), [])

    def test_a_run_count_other_than_the_tables_is_a_table_mismatch(self):
        # import_family refuses a changed file by digest before the table check, so this reads the directory results.import_files writes
        def add_median_twin(rows_in):
            hb = sorted((r for r in rows_in if r.get("build") == "pi-bolt" and r.get("scenario") == "headless"), key=lambda r: r["cpu_ms"])
            return rows_in + [dict(hb[len(hb) // 2])]
        out = os.path.join(tempfile.mkdtemp(), "o")
        family = published.FAMILIES["pi-bolt-published-headless"]
        doc = results.import_files(self.copy_with(add_median_twin), out, dict(family["meta"]))
        problems = published.check_table(out, doc, family)
        self.assertTrue(any("22 runs, the table has 21" in p for p in problems), problems)

    def test_a_changed_published_file_is_refused_by_digest_before_any_row_is_read(self):
        out = os.path.join(tempfile.mkdtemp(), "o")
        with self.assertRaises(ValueError) as caught:
            published.import_family("pi-bolt-published-headless", self.copy_with(lambda rows_in: rows_in + [dict(rows_in[0])]), out)
        self.assertIn("benchmark.jsonl is not the file at the pin", str(caught.exception))
        self.assertFalse(os.path.exists(out))

    def test_a_published_file_that_is_not_pinned_is_refused(self):
        src = tempfile.mkdtemp()
        extra = os.path.join(src, "notes.txt")
        with open(extra, "w") as f:
            f.write("hello\n")
        with self.assertRaises(ValueError) as caught:
            published.import_family("pi-bolt-published-headless", self.files() + [extra], os.path.join(tempfile.mkdtemp(), "o"))
        self.assertIn("notes.txt is not a published file", str(caught.exception))

    def test_an_unknown_family_is_refused(self):
        with self.assertRaises(ValueError):
            published.import_family("nope", [], os.path.join(tempfile.mkdtemp(), "o"))


if __name__ == "__main__":
    unittest.main()
