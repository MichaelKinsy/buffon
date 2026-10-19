# SPDX-License-Identifier: Apache-2.0
"""M1: instructions are the headline CPU metric. The perf_event_open counters cannot be driven on every host (a hardened kernel refuses them), so the structure is tested with fake descriptors
and a fake kernel: the packed attribute, the scaling, the handshake that hands the child's counters to the runner, the fallback to user-only counts, and the way a sample carries the counts."""
import errno
import os
import struct
import tempfile
import unittest

from buffon.report import cells, metrics
from buffon.runner import cgroup, engine, perfcount


def counter_fd(value, enabled, running):
    """A readable descriptor holding what a perf counter returns with READ_FORMAT_TIMES."""
    r, w = os.pipe()
    os.write(w, struct.pack("<QQQ", value, enabled, running))
    os.close(w)
    return r


class Attr(unittest.TestCase):
    def test_the_attribute_is_the_documented_112_bytes_and_counts_the_tree_from_exec(self):
        raw = perfcount.attr_bytes(perfcount.HW_INSTRUCTIONS)
        self.assertEqual(len(raw), 112)
        fields = struct.unpack(perfcount.ATTR_FORMAT, raw)
        type_, size, config, period, sample_type, read_format, flags = fields[:7]
        self.assertEqual((type_, size, config, period, sample_type), (perfcount.PERF_TYPE_HARDWARE, 112, perfcount.HW_INSTRUCTIONS, 0, 0))
        self.assertEqual(read_format, 3)   # time enabled and time running, so multiplexing can be seen
        self.assertTrue(flags & perfcount.FLAG_INHERIT and flags & perfcount.FLAG_ENABLE_ON_EXEC and flags & perfcount.FLAG_DISABLED)
        self.assertFalse(flags & (perfcount.FLAG_EXCLUDE_KERNEL | perfcount.FLAG_EXCLUDE_USER))

    def test_user_only_excludes_kernel_and_hypervisor_and_a_probe_counter_does_not_wait_for_exec(self):
        flags = struct.unpack(perfcount.ATTR_FORMAT, perfcount.attr_bytes(perfcount.HW_CPU_CYCLES, kernel=False))[6]
        self.assertTrue(flags & perfcount.FLAG_EXCLUDE_KERNEL and flags & perfcount.FLAG_EXCLUDE_HV)
        probe = struct.unpack(perfcount.ATTR_FORMAT, perfcount.attr_bytes(perfcount.HW_INSTRUCTIONS, inherit=False, enable_on_exec=False))[6]
        self.assertEqual(probe & (perfcount.FLAG_DISABLED | perfcount.FLAG_INHERIT | perfcount.FLAG_ENABLE_ON_EXEC), 0)

    def test_scaling_and_the_multiplexing_flag(self):
        self.assertEqual(perfcount.scale(1000, 10, 10), (1000, False))
        self.assertEqual(perfcount.scale(1000, 20, 10), (2000, True))
        self.assertEqual(perfcount.scale(0, 5, 0), (0, True))
        self.assertEqual(perfcount.scale(7, 0, 0), (0, False))
        self.assertEqual(perfcount.parse_read(struct.pack("<QQQ", 1, 2, 3)), (1, 2, 3))
        with self.assertRaises(OSError):
            perfcount.parse_read(b"short")


class Probe(unittest.TestCase):
    def opener(self, allowed):
        def open_(event, pid=0, kernel=True, inherit=True, enable_on_exec=True):
            if (kernel and "kernel" not in allowed) or ("user" not in allowed and not kernel):
                raise OSError(errno.EACCES, "Permission denied")
            return os.open(os.devnull, os.O_RDONLY)
        return open_

    def test_user_and_kernel_when_allowed_user_only_when_not_and_none_with_the_reason(self):
        if not os.path.exists("/proc/self"):
            self.skipTest("Linux only")
        self.assertEqual(perfcount.probe(self.opener({"kernel", "user"}))["scope"], "user+kernel")
        only_user = perfcount.probe(self.opener({"user"}))
        self.assertEqual((only_user["available"], only_user["scope"]), (True, "user"))
        self.assertIn("kernel instructions are not counted", only_user["reason"])
        none = perfcount.probe(self.opener(set()))
        self.assertFalse(none["available"])
        self.assertIn("CPU time is the headline", none["reason"])
        self.assertIn("Permission denied", none["reason"])


class Handshake(unittest.TestCase):
    def test_the_childs_counters_reach_the_runner_and_read_scaled(self):
        calls = []

        def opener(event, pid=0, kernel=True, **_):
            calls.append((event, kernel))
            return counter_fd(1000 * (event + 2), 20, 10) if event == perfcount.HW_INSTRUCTIONS else counter_fd(500, 10, 10)
        session = perfcount.Session(kernel=True, opener=opener)
        session.child_pre()
        self.assertTrue(session.collect())
        got = session.read()
        self.assertEqual(got["instructions"], 6000)    # 3000 scaled by 20/10
        self.assertEqual(got["cycles"], 500)
        self.assertEqual((got["perf_scope"], got["perf_multiplexed"]), ("user+kernel", True))
        self.assertEqual({e for e, _ in calls}, {perfcount.HW_INSTRUCTIONS, perfcount.HW_CPU_CYCLES})
        session.close()
        self.assertEqual(session.read(), {})

    def test_a_refused_open_gives_no_counts_and_never_raises_in_the_child(self):
        def opener(*_a, **_k):
            raise OSError(errno.EPERM, "Operation not permitted")
        session = perfcount.Session(opener=opener)
        session.child_pre()
        self.assertFalse(session.collect())
        self.assertEqual(session.read(), {})

    def test_a_real_child_process_hands_over_descriptors_through_popen(self):
        """The whole path with the real fork/exec: the counter is opened in the child between fork and exec and the runner receives it after Popen returned."""
        import subprocess
        import sys
        def opener(event, **_):
            return counter_fd(123456 if event == perfcount.HW_INSTRUCTIONS else 7, 4, 4)
        session = perfcount.Session(opener=opener)
        child = subprocess.Popen([sys.executable, "-c", "pass"], preexec_fn=session.child_pre)
        self.assertTrue(session.collect())
        child.wait()
        self.assertEqual(session.read(), {"instructions": 123456, "cycles": 7, "perf_scope": "user+kernel"})
        session.close()


class MeterIntegration(unittest.TestCase):
    def tearDown(self):
        cgroup.PERF = None

    def test_without_a_probe_result_a_meter_counts_nothing_and_a_unavailable_host_adds_no_cells(self):
        self.assertEqual(cgroup.RusageMeter().perf(), {})
        cgroup.PERF = {"available": False, "scope": None, "paranoid": 4, "reason": "refused"}
        self.assertIsNone(perfcount.start(cgroup.PERF))
        m = cgroup.RusageMeter()
        m.popen(["true"])
        m.wait(10)
        self.assertEqual(m.perf(), {})
        m.close()

    def test_popen_attaches_the_counters_the_child_opened_and_the_sample_carries_them(self):
        from unittest import mock

        def opener(event, **_):
            return counter_fd(2_000_000 if event == perfcount.HW_INSTRUCTIONS else 900_000, 1, 1)
        cgroup.PERF = {"available": True, "scope": "user+kernel", "paranoid": 1, "reason": None}
        with mock.patch.object(perfcount, "start", lambda info: perfcount.Session(kernel=True, opener=opener)):
            m = cgroup.RusageMeter()
            m.popen(["true"])
            m.wait(10)
            self.assertEqual(m.perf(), {"instructions": 2_000_000, "cycles": 900_000, "perf_scope": "user+kernel"})
            m.close()

    def test_a_meter_with_a_session_reports_its_counts(self):
        m = cgroup.RusageMeter()
        session = perfcount.Session()
        session.fds = {"instructions": counter_fd(9_000_000, 1, 1), "cycles": counter_fd(4_000_000, 1, 1)}
        m.perf_session = session
        self.assertEqual(m.perf(), {"instructions": 9_000_000, "cycles": 4_000_000, "perf_scope": "user+kernel"})

    def test_closing_a_meter_closes_its_counter_descriptors(self):
        # Each sample opens its own counters; a meter that kept them open ran a 1,000-sample session out of descriptors (EMFILE).
        m = cgroup.RusageMeter()
        session = perfcount.Session()
        session.fds = {"instructions": counter_fd(9_000_000, 1, 1), "cycles": counter_fd(4_000_000, 1, 1)}
        fds = list(session.fds.values())
        m.perf_session = session
        m.close()
        for fd in fds:
            with self.assertRaises(OSError):
                os.fstat(fd)
        self.assertEqual(m.perf(), {})

    def test_the_engine_records_what_the_host_allows_and_says_why_a_container_run_has_none(self):
        facts = engine.perf_facts("container")
        self.assertFalse(facts["available"])
        self.assertIn("CPU time is the headline", facts["reason"])
        self.assertIn("available", engine.perf_facts("none"))


class ReviewScaledCountsAreDisclosed(unittest.TestCase):
    def test_the_report_says_how_many_instruction_counts_were_scaled(self):
        # review: a multiplexed counter's value is scaled by enabled/running (an estimate); the report showed it as an exact count
        from buffon.report import render
        perf = {"available": True, "scope": "user+kernel", "reason": None}
        samples = [{"instructions": 10, "warmup": False}, {"instructions": 12, "warmup": False, "perf_multiplexed": True}, {"instructions": 9, "warmup": True, "perf_multiplexed": True}]
        self.assertIn("1 of 2 measured samples' counts were scaled", render.perf_text(perf, samples))
        self.assertNotIn("scaled", render.perf_text(perf, samples[:1]))

class MacOS(unittest.TestCase):
    def test_the_rusage_info_offsets_follow_the_v4_layout(self):
        self.assertEqual(perfcount.MAC_OFFSETS, {"phys_footprint": 72, "instructions": 248, "cycles": 256})
        self.assertGreaterEqual(perfcount.MAC_RUSAGE_SIZE, perfcount.MAC_OFFSETS["cycles"] + 8)

    def test_a_tree_sums_each_processs_last_reading_and_keeps_an_exited_one(self):
        readings = {1: {"instructions": 100, "cycles": 50, "phys_footprint": 1}, 2: {"instructions": 40, "cycles": 20, "phys_footprint": 1}}
        tree = perfcount.MacTree(reader=lambda pid: readings.get(pid))
        tree.observe([1, 2])
        readings[1] = {"instructions": 150, "cycles": 70, "phys_footprint": 1}
        del readings[2]    # exited between samples
        tree.observe([1, 2])
        self.assertEqual(tree.read(), {"instructions": 190, "cycles": 90, "perf_scope": "sampled"})
        self.assertEqual(perfcount.MacTree(reader=lambda pid: None).read(), {})

    def test_mac_read_unpacks_the_struct_at_the_offsets(self):
        class Lib:
            def proc_pid_rusage(self, pid, flavor, buf):
                struct.pack_into("<Q", buf, perfcount.MAC_OFFSETS["instructions"], 777)
                struct.pack_into("<Q", buf, perfcount.MAC_OFFSETS["cycles"], 333)
                return 0
        self.assertEqual(perfcount.mac_read(5, Lib()), {"instructions": 777, "cycles": 333, "phys_footprint": 0})


class Describe(unittest.TestCase):
    def test_every_metric_has_a_kind_and_a_unit_and_instructions_are_cpu_not_time(self):
        want = {"instructions": ("CPU", "instructions"), "cycles": ("CPU", "cycles"), "cpu_ms": ("CPU", "ms of CPU time"), "wall_ms": ("wall", "ms"), "peak_rss_mib": ("memory", "MiB"),
                "prose_cpu_ms_per_1k_tokens": ("CPU", "ms of CPU time per 1k tokens"), "prose_instructions_per_1k_tokens": ("CPU", "instructions per 1k tokens"),
                "prose_wall_ms": ("wall", "ms"), "ready_cpu_ms": ("CPU", "ms of CPU time"), "request_bytes": ("wire", "bytes")}
        for metric, kind_unit in want.items():
            self.assertEqual(metrics.describe(metric), kind_unit, metric)
        self.assertEqual(metrics.headline_cpu({"cpu_ms", "instructions", "wall_ms"}), "instructions")
        self.assertEqual(metrics.headline_cpu({"cpu_ms"}), "cpu_ms")
        self.assertIsNone(metrics.headline_cpu({"wall_ms"}))

    def test_instruction_metrics_are_scored_lower_is_better_and_the_scope_flag_is_not(self):
        for m in ("instructions", "cycles", "prose_instructions_per_1k_tokens"):
            self.assertTrue(cells.scored(m), m)
        self.assertFalse(cells.scored("perf_scope"))


class GradeUsesInstructions(unittest.TestCase):
    """Instructions supersede CPU time as the CPU cost of a workload in the grade; a workload without them keeps its CPU time."""

    def data(self, with_instructions):
        from tests.test_report import raw_of, sample, wobble
        out = []
        for r in range(12):
            for name, base, shift in (("pi-node", 100.0, 0), ("pi-node-b", 100.0, 3), ("other", 50.0, 1), ("other-b", 50.0, 5)):
                m = {"cpu_ms": base + wobble(r + shift), "peak_rss_mib": 50.0 + wobble(r + shift) / 10}
                if with_instructions:
                    m["instructions"] = (base + wobble(r + shift)) * 1e6
                out.append(sample(name, "overhead/print", r, **m))
        return cells.build([raw_of(out)], seed=3)

    def inputs(self, with_instructions):
        from buffon.report import grade_inputs
        data = self.data(with_instructions)
        health = {"notes": 2}
        return grade_inputs.build(data, [{"arms": {}, "skipped": []}], health, True, [])

    def test_with_instruction_cells_the_cpu_time_cell_is_left_out_of_the_grade(self):
        self.assertEqual(sorted(c["metric"] for c in self.inputs(True)["cells"]), ["instructions", "peak_rss_mib"])
        self.assertEqual(sorted(c["metric"] for c in self.inputs(False)["cells"]), ["cpu_ms", "peak_rss_mib"])

    def test_the_twin_of_a_per_token_cpu_metric_is_its_instruction_metric(self):
        from buffon.report import grade_inputs
        self.assertEqual(grade_inputs.instruction_twin("prose_cpu_ms_per_1k_tokens"), "prose_instructions_per_1k_tokens")
        self.assertEqual(grade_inputs.instruction_twin("cpu_ms"), "instructions")
        self.assertIsNone(grade_inputs.instruction_twin("peak_rss_mib"))


if __name__ == "__main__":
    unittest.main()
