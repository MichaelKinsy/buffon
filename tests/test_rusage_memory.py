# SPDX-License-Identifier: Apache-2.0
"""The rusage meter's all-processes peak memory for a command that is gone before a tree sample lands (macOS `ps` samples take longer than a start-up)."""
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

from buffon.runner import cgroup

MIB = 1024 * 1024


def finished_meter(rss_by_sample, ru_maxrss_bytes):
    """A meter whose tree samples read `rss_by_sample` (KiB sums; 0 is a sample that found no tree) and whose child has exited with the given wait4 ru_maxrss."""
    m = cgroup.RusageMeter()
    m.child = SimpleNamespace(pid=999999, returncode=0)
    m.rusage = SimpleNamespace(ru_maxrss=ru_maxrss_bytes, ru_utime=0.01, ru_stime=0.0)
    for kib in rss_by_sample:
        m._note_rss(kib)
    return m


class ShortLivedTree(unittest.TestCase):
    def test_no_sample_is_no_value_not_zero(self):
        for rss in ([], [0, 0]):
            m = finished_meter(rss, 15 * MIB)
            self.assertIsNone(m.peak_mem_mib(), rss)

    def test_a_sample_before_the_pages_were_touched_cannot_put_the_peak_under_the_largest_process(self):
        """The 2121x case: one sample caught the process at 32 KiB just after its exec; it then ran to 15 MiB and exited."""
        with mock.patch.object(sys, "platform", "darwin"):
            m = finished_meter([32], 15 * MIB)
            self.assertEqual(m.peak_mem_mib(), 15.0)
            self.assertEqual(m.max_proc_rss_mib(), 15.0)

    def test_a_sampled_sum_above_the_largest_process_is_kept(self):
        with mock.patch.object(sys, "platform", "darwin"):
            m = finished_meter([32, 40 * 1024, 12 * 1024], 15 * MIB)   # two processes: 40 MiB together at the peak, the largest 15 MiB
            self.assertEqual(m.peak_mem_mib(), 40.0)

    def test_the_largest_process_is_still_known_when_no_sample_landed(self):
        with mock.patch.object(sys, "platform", "darwin"):
            m = finished_meter([], 15 * MIB)
            self.assertIsNone(m.peak_mem_mib())
            self.assertEqual(m.max_proc_rss_mib(), 15.0)

    def test_on_linux_the_sampled_sum_stands_alone(self):
        """ru_maxrss of a forked child carries the runner's own resident set there (see max_proc_rss_mib), so it is not a floor for the sum."""
        with mock.patch.object(sys, "platform", "linux"):
            self.assertEqual(finished_meter([8 * 1024], 500 * 1024 * 1024 // 1024).peak_mem_mib(), 8.0)   # 500 MiB of ru_maxrss in KiB

    def test_a_running_tree_is_read_when_asked(self):
        m = cgroup.RusageMeter()
        m.child = SimpleNamespace(pid=1, returncode=None)
        with mock.patch.object(cgroup, "_tree_rows", return_value={1: (0, 2048, 0.0), 2: (1, 1024, 0.0)}):
            self.assertEqual(m.peak_mem_mib(), 3.0)
        with mock.patch.object(cgroup, "_tree_rows", return_value={}):   # the tree is gone: the earlier peak stands
            self.assertEqual(m.peak_mem_mib(), 3.0)


@unittest.skipUnless(sys.platform == "darwin", "the macOS sampler")
class RealShortCommand(unittest.TestCase):
    def test_a_real_short_command_never_reads_below_its_largest_process(self):
        m = cgroup.RusageMeter()
        m.popen(["/usr/bin/true"], stdout=subprocess.DEVNULL)
        m.wait(30)
        try:
            peak, largest = m.peak_mem_mib(), m.max_proc_rss_mib()
            self.assertGreater(largest, 0)
            self.assertTrue(peak is None or peak >= largest, (peak, largest))
        finally:
            m.close()


if __name__ == "__main__":
    unittest.main()
