"""R11: new buffon code is Apache-2.0. An MIT header marks a file adapted from vendored code (pigbench, Pi-Bolt's bench/compare, both MIT); the list of such files is closed: a new file with an MIT
header, or without any SPDX header, fails here."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTED_MIT = {
    "buffon/arms/writers/codex.py", "buffon/arms/writers/omp.py", "buffon/arms/writers/pi.py", "buffon/fixtures/sessions.py", "buffon/mock/__init__.py", "buffon/mock/server.py", "buffon/mock/shapes.py",
    "buffon/runner/cgroup.py", "buffon/runner/checkpoint.py", "buffon/runner/egress.py", "buffon/runner/harness.py", "buffon/runner/procio.py", "buffon/runner/procs.py", "buffon/stats/core.py",
    "buffon/stats/__init__.py", "buffon/workloads/overhead.py", "buffon/workloads/reliability.py", "buffon/workloads/soak.py",
}


class Headers(unittest.TestCase):
    def sources(self):
        for base, dirs, files in os.walk(os.path.join(ROOT, "buffon")):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if name.endswith(".py"):
                    yield os.path.relpath(os.path.join(base, name), ROOT)

    def header(self, rel):
        with open(os.path.join(ROOT, rel)) as f:
            for line in f.read().splitlines()[:6]:
                if "SPDX-License-Identifier:" in line:
                    return line.split("SPDX-License-Identifier:")[1].strip()
        return None

    def test_every_non_empty_source_file_names_its_licence(self):
        missing = [r for r in self.sources() if os.path.getsize(os.path.join(ROOT, r)) and self.header(r) is None]
        self.assertEqual(missing, [])

    def test_mit_is_only_for_the_closed_list_of_adapted_files_everything_else_is_apache(self):
        wrong = [f"{r}: {self.header(r)}" for r in self.sources() if self.header(r) not in (None, "Apache-2.0") and r not in ADAPTED_MIT]
        self.assertEqual(wrong, [])
        gone = sorted(r for r in ADAPTED_MIT if not os.path.exists(os.path.join(ROOT, r)))
        self.assertEqual(gone, [], "a file left the adapted list: remove it here")
