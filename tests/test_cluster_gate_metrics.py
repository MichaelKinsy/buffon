# SPDX-License-Identifier: Apache-2.0
"""The cross-node gate (cluster/gate.go) judges the metrics the report scores (buffon/report/cells.py): the same descriptor list and the same name rules."""
import inspect
import os
import re
import unittest

from buffon.report import cells

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def go_source():
    with open(os.path.join(ROOT, "cluster", "gate.go")) as f:
        return f.read()


def go_block(src, start):
    i = src.index(start)
    return src[i:src.index("\n}", i)]


def go_list(src, name):
    m = re.search(r"\b" + name + r"\s*=\s*\[\]string\{([^}]*)\}", src)
    return re.findall(r'"([^"]+)"', m.group(1))


class GateMetrics(unittest.TestCase):
    def test_the_descriptors_are_the_reports(self):
        keys = set(re.findall(r'"([a-z0-9_]+)": true', go_block(go_source(), "var descriptors = map[string]bool{")))
        self.assertEqual(keys, set(cells.DESCRIPTORS))

    def test_the_name_rules_are_the_reports(self):
        src = go_source()
        body = go_block(src, "func scored(metric string) bool {")
        self.assertIn('strings.Contains(metric, "_ms_per_")', body)
        self.assertIn('strings.Contains(metric, "_mib_per_")', body)
        self.assertIn('metric == "turns_per_s"', body)
        self.assertIn('strings.HasPrefix(metric, "cpu_ms")', body)
        self.assertIn('strings.Contains(metric, "_instructions_per_")', body)
        self.assertIn('metric == "instructions" || metric == "cycles"', body)
        unscored, scored = go_list(src, "unscoredSuffixes"), go_list(src, "scoredSuffixes")
        py = inspect.getsource(cells.scored)
        tuples = [re.findall(r'"([^"]+)"', t) for t in re.findall(r"endswith\(\(([^)]*)\)\)", py)]
        self.assertEqual(tuples, [unscored, scored])
        # Every rule the Go lists state is one cells.scored applies.
        for suffix in unscored:
            self.assertFalse(cells.scored("x" + suffix), suffix)
            self.assertFalse(cells.scored("cpu_ms" + suffix), suffix)
        for suffix in scored:
            self.assertTrue(cells.scored("x" + suffix), suffix)
        # And the converse, on every metric name the runner writes in the workloads and their documentation.
        names = set()
        for dirpath, _, files in os.walk(os.path.join(ROOT, "buffon", "workloads")):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(dirpath, name)) as f:
                        names |= set(re.findall(r'"([a-z][a-z0-9_]*_(?:ms|mib|bytes|flat|median|spread|h|tokens|turn|tps|n10|n))"', f.read()))
        self.assertGreater(len(names), 20)

        from buffon.report import metrics as metricslib
        counts = set(re.findall(r'"([a-z0-9_]+)": true', go_block(src, "var countMetrics = map[string]bool{")))
        self.assertEqual(counts, set(metricslib.COUNT_METRICS))

        def go_scored(metric):
            if metric in counts:
                return True
            if metric in cells.DESCRIPTORS or metric.endswith(tuple(unscored)):
                return False
            return (metric.endswith(tuple(scored)) or "_ms_per_" in metric or "_mib_per_" in metric or "_bytes_per_" in metric or metric.startswith("bytes_") or metric == "mem_per_conv_mib"
                    or "_instructions_per_" in metric or metric.startswith("cpu_ms") or metric in ("instructions", "cycles", "turns_per_s"))

        for metric in sorted(names | {"bytes_returned_per_turn", "wchar_bytes_per_turn", "mem_per_conv_mib"} | counts):
            self.assertEqual(go_scored(metric), cells.scored(metric), metric)


if __name__ == "__main__":
    unittest.main()
