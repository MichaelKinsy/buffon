# SPDX-License-Identifier: Apache-2.0
"""External suites and results: provenance is mandatory, nothing external reaches a buffon cell, and a suite runs only at its pin, unchanged."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest

from buffon.external import results, runner, suites
from buffon.report import cells, render
from buffon.runner import raw as rawlib
from tests.test_report import raw_of, series

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "external", "results", "pi-bolt-2026-10-11-linux-x64-0.8.0")
META = {"id": "x", "title": "X", "source_url": "https://example.org/x", "repo": "https://example.org/r", "commit": "c" * 40, "version": "x 1", "host": "a host", "licence": "MIT", "published": "2026-10-11"}


def write(directory, name, text):
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write(text)
    return path


class Import(unittest.TestCase):
    def test_import_copies_unchanged_records_hashes_and_loads_back(self):
        src, out = tempfile.mkdtemp(), os.path.join(tempfile.mkdtemp(), "o")
        p = write(src, "a.jsonl", '{"build": "b", "scenario": "s", "ok": true, "cpu_ms": 5}\n')
        doc = results.import_files([p], out, META)
        self.assertEqual(doc["files"]["a.jsonl"]["rows"], 1)
        self.assertEqual(results.load(out)["files"]["a.jsonl"]["sha256"], results.sha256_file(p))

    def test_a_result_set_without_provenance_or_licence_is_refused(self):
        for key in ("licence", "commit", "host", "version", "source_url"):
            meta = {k: v for k, v in META.items() if k != key}
            with self.assertRaises(ValueError, msg=key):
                results.import_files([], os.path.join(tempfile.mkdtemp(), "o"), meta)

    def test_a_file_edited_after_import_is_refused(self):
        src, out = tempfile.mkdtemp(), os.path.join(tempfile.mkdtemp(), "o")
        results.import_files([write(src, "a.jsonl", '{"build": "b", "scenario": "s"}\n')], out, META)
        write(os.path.join(out, "files"), "a.jsonl", '{"build": "b", "scenario": "s", "cpu_ms": 1}\n')
        with self.assertRaises(ValueError):
            results.load(out)

    def test_summary_counts_failures_but_keeps_them_out_of_the_statistics(self):
        src, out = tempfile.mkdtemp(), os.path.join(tempfile.mkdtemp(), "o")
        lines = [{"build": "b", "scenario": "s", "ok": True, "cpu_ms": v} for v in (1, 2, 9)] + [{"build": "b", "scenario": "s", "ok": False, "cpu_ms": 1000}]
        results.import_files([write(src, "a.jsonl", "".join(json.dumps(r) + "\n" for r in lines))], out, META)
        entry = results.summarise(out, results.load(out))[("a.jsonl", "b", "s")]
        self.assertEqual((entry["n"], entry["failed"], entry["cpu_ms"]["median"], entry["cpu_ms"]["max"]), (4, 1, 2.0, 9.0))


class PublishedPiBolt(unittest.TestCase):
    """The committed import equals the numbers Pi-Bolt prints in its README (R8 D1): headless `pi -p` CPU, medians of 21 runs."""

    def test_the_committed_import_is_intact_and_matches_the_published_table(self):
        doc = results.load(PUBLISHED)
        self.assertEqual((doc["commit"], doc["licence"].split()[0]), ("13ccac32afb94366fb8d3e15aff1dd7bb234fefa", "MIT"))
        table = results.summarise(PUBLISHED, doc)
        published_cpu = {"pi-bolt": 80, "pig": 261, "omp": 1752, "bun": 323, "node": 618}
        for build, ms in published_cpu.items():
            e = table[("benchmark.jsonl", build, "headless")]
            self.assertEqual(e["n"], 21)
            self.assertLess(abs(e["cpu_ms"]["median"] - ms), 1.0, build)


class NeverInAnAggregate(unittest.TestCase):
    """An external directory is not a buffon run: the loader refuses it, and the section it gets in the report leaves everything Buffon measured byte-identical."""

    def test_the_run_reader_and_the_report_refuse_external_directories(self):
        out = os.path.join(tempfile.mkdtemp(), "o")
        results.import_files([], out, META)
        for loader in (rawlib.read, lambda d: render.render([d], os.path.join(d, "r"))):
            with self.assertRaises(ValueError) as caught:
                loader(out)
            self.assertIn("external", str(caught.exception))
        suite = tempfile.mkdtemp()
        write(suite, "external-suite.json", json.dumps({"kind": "external-suite"}))
        with self.assertRaises(ValueError):
            rawlib.read(suite)

    def test_cell_building_is_a_function_of_the_raw_runs_alone(self):
        runs = [rawlib.validate(raw_of(series()))]
        before = cells.build(runs, None, 1)
        results.section([PUBLISHED])   # loading and summarising external rows cannot change anything computed from the runs
        self.assertEqual(json.dumps(before["base"], default=str), json.dumps(cells.build(runs, None, 1)["base"], default=str))

    def test_the_report_with_external_sections_equals_the_report_without_plus_those_sections(self):
        tmp = tempfile.mkdtemp()
        run = os.path.join(tmp, "run")
        rawlib.write(raw_of(series()), run)
        plain = open(render.render([run], os.path.join(tmp, "a"))).read()
        with_external = open(render.render([run], os.path.join(tmp, "b"), external_results=[PUBLISHED])).read()
        head, _, tail = plain.rpartition("\n---\n")
        self.assertTrue(with_external.startswith(head + "\n"))
        self.assertIn("## External results (published by others)", with_external)
        self.assertEqual(with_external.rpartition("\n---\n")[2], tail)
        before_external = with_external.split("## External results (published by others)")[0]
        self.assertEqual(before_external.rstrip("\n"), head.rstrip("\n"))


def make_checkout(dirty=False):
    d = tempfile.mkdtemp()
    for args in (["init", "-q"], ["config", "user.email", "t@example.org"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", d, *args], check=True)
    os.makedirs(os.path.join(d, "packages", "durable"))
    write(d, "packages/durable/f", "1\n")
    subprocess.run(["git", "-C", d, "add", "."], check=True)
    subprocess.run(["git", "-C", d, "commit", "-q", "-m", "c"], check=True)
    head = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        write(d, "packages/durable/f", "2\n")
    return d, head


FIXTURE_ID = "fixture-durable"
FIXTURE_FILE_SHA = hashlib.sha256(b"1\n").hexdigest()


def fixture_suite():
    """A suite whose one file is make_checkout's packages/durable/f: the runner tests exercise the guard on a file they control."""
    return suites.Suite(FIXTURE_ID, "fixture suite", "MIT", targets={"pi-node": suites.Target("pi", "packages/durable", ("npm", "run", "bench:storage"), manifest=(("packages/durable/f", FIXTURE_FILE_SHA),))},
                        pins={"pi": None})


class Done:
    returncode, stdout, stderr = 0, "suite output\n", ""


class Suites(unittest.TestCase):
    def test_argv_is_the_upstream_command_with_the_arm_filled_in(self):
        s = suites.get("pi-bolt-benchmark")
        _, argv = suites.argv_for(s, "build", arm="pig", command="out/pig")
        self.assertEqual(argv, ["python3", "bench/benchmark.py", "--build", "pig=out/pig"])
        _, argv = suites.argv_for(suites.get("durable-storage"), "pi-node")
        self.assertEqual(argv, ["npm", "run", "bench:storage"])

    def test_a_suite_with_no_equivalent_for_a_harness_says_so(self):
        with self.assertRaises(ValueError) as caught:
            suites.argv_for(suites.get("durable-tool-output"), "pig-native")
        self.assertIn("no equivalent", str(caught.exception))
        with self.assertRaises(ValueError):
            suites.argv_for(suites.get("pi-bolt-benchmark"), "build")   # a build comparison needs the arm

    def test_every_suite_names_a_licence_a_pin_slot_for_each_repository_and_the_bolt_pin_is_a_full_commit(self):
        for s in suites.SUITES.values():
            self.assertTrue(s.licence)
            for t in s.targets.values():
                self.assertIn(t.repo, s.pins, s.id)
        self.assertEqual(len(suites.PI_BOLT_COMMIT), 40)


class Run(unittest.TestCase):
    def run_suite(self, checkout, commit, **kw):
        out = tempfile.mkdtemp()
        calls = []

        def fake(argv, **k):
            calls.append((argv, k))
            return Done()
        kw.setdefault("foreign_locks", ())
        doc = runner.run(FIXTURE_ID, "pi-node", checkout, out, commit=commit, runner=fake, **kw)
        return doc, out, calls

    def setUp(self):
        os.environ["BUFFON_LOCK_FILE"] = os.path.join(tempfile.mkdtemp(), "lock")
        self.addCleanup(os.environ.pop, "BUFFON_LOCK_FILE", None)
        suites.SUITES[FIXTURE_ID] = fixture_suite()
        self.addCleanup(suites.SUITES.pop, FIXTURE_ID, None)

    def test_runs_the_command_in_the_checkout_at_the_pin_and_writes_a_record_without_raw_json(self):
        d, head = make_checkout()
        doc, out, calls = self.run_suite(d, head)
        self.assertEqual(calls[0][0], ["npm", "run", "bench:storage"])
        self.assertEqual(calls[0][1]["cwd"], os.path.join(d, "packages", "durable"))
        self.assertEqual((doc["kind"], doc["commit"], doc["exit"]), ("external-suite", head, 0))
        self.assertTrue(os.path.exists(os.path.join(out, "external-suite.json")))
        self.assertFalse(os.path.exists(os.path.join(out, "raw.json")))
        self.assertEqual(open(os.path.join(out, "stdout.txt")).read(), "suite output\n")

    def test_refuses_without_a_pin_at_the_wrong_commit_with_tracked_changes_and_for_a_live_suite(self):
        d, head = make_checkout()
        with self.assertRaises(runner.Refused) as caught:
            self.run_suite(d, None)
        self.assertIn("pin", str(caught.exception))
        with self.assertRaises(runner.Refused):
            self.run_suite(d, "0" * 40)
        dirty, dhead = make_checkout(dirty=True)
        with self.assertRaises(runner.Refused) as caught:
            self.run_suite(dirty, dhead)
        self.assertIn("tracked changes", str(caught.exception))
        with self.assertRaises(runner.Refused) as caught:
            runner.run("pi-evals", "pi-node", d, tempfile.mkdtemp(), commit=head, runner=lambda *a, **k: Done())
        self.assertIn("--live", str(caught.exception))

    def test_a_directory_that_is_not_a_git_checkout_or_a_short_pin_is_refused(self):
        """Review: rev-parse in a plain directory prints nothing, and the empty head matched every pin."""
        with self.assertRaises(runner.Refused) as caught:
            self.run_suite(tempfile.mkdtemp(), "0123456789abcdef0123456789abcdef01234567")
        self.assertIn("not a git checkout", str(caught.exception))
        d, head = make_checkout()
        for pin in (head[:3], head + "0", "zzzzzzz"):
            with self.assertRaises(runner.Refused):
                self.run_suite(d, pin)
        self.assertEqual(self.run_suite(d, head[:7])[0]["commit"], head)

    def test_credentials_are_removed_from_the_environment_the_suite_sees(self):
        d, head = make_checkout()
        os.environ["SOME_API_KEY"] = "secret"
        self.addCleanup(os.environ.pop, "SOME_API_KEY", None)
        _, _, calls = self.run_suite(d, head)
        self.assertNotIn("SOME_API_KEY", calls[0][1]["env"])

    def test_the_suite_gets_only_an_allow_list_and_a_home_in_the_run_directory(self):
        """E2: PI_CODING_AGENT_DIR, PIG_*, the operator's HOME and any other variable never reach an upstream suite."""
        d, head = make_checkout()
        for k, v in (("PI_CODING_AGENT_DIR", "/real/agent"), ("PIG_HOME", "/real/pig"), ("HOME_MARK", "x"), ("NODE_OPTIONS", "--bad")):
            os.environ[k] = v
            self.addCleanup(os.environ.pop, k, None)
        _, out, calls = self.run_suite(d, head, env={"GOMODCACHE": "/cache/mod", "SOME_TOKEN": "t"})
        env = calls[0][1]["env"]
        self.assertEqual(env["HOME"], os.path.join(os.path.abspath(out), "home"))
        self.assertEqual(env["GOMODCACHE"], "/cache/mod")
        for k in ("PI_CODING_AGENT_DIR", "PIG_HOME", "HOME_MARK", "NODE_OPTIONS", "SOME_TOKEN"):
            self.assertNotIn(k, env)
        self.assertLessEqual(set(env), {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "HOME", "GOMODCACHE"})

    def test_a_suite_that_connects_outside_loopback_is_recorded_with_the_remote(self):
        d, head = make_checkout()
        import sys
        out = tempfile.mkdtemp()
        doc = runner.run(FIXTURE_ID, "pi-node", d, out, commit=head, runner=lambda argv, **k: runner.metered(
            [sys.executable, "-c", "import socket,time;s=socket.socket();s.setblocking(False);s.connect_ex(('192.0.2.1',9));time.sleep(3.0)"], **k))
        self.assertEqual(doc["egress"], ["192.0.2.1:9"])
        self.assertIn("EGRESS to 192.0.2.1:9", "\n".join(runner.section([out])))

    def test_a_suite_that_times_out_keeps_its_egress(self):
        """Review: the timeout path recorded egress [] and left the observation for the next run's take() to discard."""
        d, head = make_checkout()
        import sys
        out = tempfile.mkdtemp()
        doc = runner.run(FIXTURE_ID, "pi-node", d, out, commit=head, timeout=1.5, runner=lambda argv, **k: runner.metered(
            [sys.executable, "-c", "import socket,time;s=socket.socket();s.setblocking(False);s.connect_ex(('192.0.2.1',9));time.sleep(30)"], **k))
        self.assertTrue(doc["timed_out"])
        self.assertEqual(doc["egress"], ["192.0.2.1:9"])

    def test_a_clean_suite_has_no_egress(self):
        d, head = make_checkout()
        doc, _, _ = self.run_suite(d, head)
        self.assertEqual(doc["egress"], [])

    def test_the_run_takes_the_host_lock(self):
        d, head = make_checkout()
        import sys
        from buffon.runner import quiet
        holder = subprocess.Popen([sys.executable, "-c", "import os,time\nfrom buffon.runner import quiet\nwith quiet.HostLock(own=os.environ['BUFFON_LOCK_FILE']):\n    print('held', flush=True)\n    time.sleep(30)"],
                                  stdout=subprocess.PIPE, text=True, cwd=ROOT)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        with self.assertRaises(quiet.LockHeld):
            self.run_suite(d, head)

    def test_the_report_section_lists_the_run_and_never_computes_from_it(self):
        d, head = make_checkout()
        _, out, _ = self.run_suite(d, head)
        text = "\n".join(runner.section([out]))
        self.assertIn(f"| {FIXTURE_ID} | pi-node | - |", text)
        self.assertIn("in no cell, aggregate or verdict", text)


if __name__ == "__main__":
    unittest.main()
