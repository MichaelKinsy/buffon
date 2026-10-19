# SPDX-License-Identifier: Apache-2.0
"""Rule 9 against the footprint metric: code mapped from tmpfs or shared memory counts as the process's own memory, so every arm runs from disk and a sample that maps code from tmpfs fails."""
import os
import subprocess
import sys
import tempfile
import time
import unittest

from buffon.runner import cgroup, raw as rawlib, textmaps
from tests.test_engine import FakeCtx, arm, runner
from buffon.runner import engine
from buffon.workloads import Workload

MOUNTINFO = """22 1 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw
30 22 0:25 / /buffon/home rw,nosuid shared:2 - tmpfs tmpfs rw,size=524288k
31 22 0:26 / /dev/shm rw,nosuid,nodev shared:3 - tmpfs tmpfs rw
32 22 0:40 / /data/my\\040dir rw - overlay overlay rw,lowerdir=/x
33 22 8:1 /sub /bind rw - ext4 /dev/sda1 rw
"""
MAPS = """55d000000000-55d000100000 r-xp 00000000 08:01 1234 /usr/bin/node
7f0000000000-7f0000100000 r-xp 00000000 00:19 77 /buffon/home/.pig/aot/slot1.so
7f0000200000-7f0000300000 r-xp 00000000 00:1a 78 /dev/shm/pig-image
7f0000400000-7f0000500000 rw-p 00000000 08:01 1235 /usr/lib/libc.so
7f0000600000-7f0000700000 r-xp 00000000 00:00 0
7f0000800000-7f0000900000 r-xp 00000000 00:01 5 /memfd:jit (deleted)
7ffd00000000-7ffd00100000 r-xp 00000000 00:00 0 [vdso]
7f0000a00000-7f0000b00000 r-xp 00000000 00:28 9 /data/my dir/lib.so
7f0000c00000-7f0000d00000 r-xp 00000000 08:01 1234 /usr/bin/node
"""


class Parsing(unittest.TestCase):
    def test_mountinfo_gives_each_devices_file_system_and_mount_points_keep_every_mount(self):
        mounts = textmaps.parse_mountinfo(MOUNTINFO)
        self.assertEqual(mounts[(0, 25)][0], "tmpfs")
        self.assertEqual(mounts[(8, 1)][0], "ext4")
        self.assertEqual(textmaps.mount_type("/data/my dir/x", MOUNTINFO), "overlay")
        self.assertEqual(textmaps.mount_type("/buffon/home/.pig", MOUNTINFO), "tmpfs")
        self.assertEqual(textmaps.mount_type("/usr/bin", MOUNTINFO), "ext4")
        self.assertEqual(textmaps.mount_type("/dev/shm/x", MOUNTINFO), "tmpfs")

    def test_only_file_backed_executable_mappings_count_once_per_file(self):
        got = textmaps.parse_maps(MAPS)
        self.assertEqual([p for p, _, _ in got], ["/usr/bin/node", "/buffon/home/.pig/aot/slot1.so", "/dev/shm/pig-image", "/memfd:jit (deleted)", "/data/my dir/lib.so"])
        self.assertEqual(got[0][1], (8, 1))

    def test_tmpfs_ramfs_shm_and_memfd_text_is_bad_disk_and_overlay_is_not(self):
        mounts = textmaps.parse_mountinfo(MOUNTINFO)
        self.assertEqual(textmaps.classify("/usr/bin/node", (8, 1), mounts), ("ext4", False))
        self.assertEqual(textmaps.classify("/buffon/home/.pig/aot/slot1.so", (0, 25), mounts), ("tmpfs", True))
        self.assertEqual(textmaps.classify("/x", (0, 40), mounts), ("overlay", False))
        self.assertEqual(textmaps.classify("/dev/shm/x", (8, 1), mounts)[1], True)       # a path in /dev/shm is bad whatever the device says
        self.assertEqual(textmaps.classify("/memfd:jit (deleted)", (0, 1), mounts)[1], True)
        self.assertEqual(textmaps.classify("/y", (0, 99), mounts), ("unknown", False))
        self.assertTrue(textmaps.classify("/z", (0, 30), {(0, 30): ("ramfs", "/z")})[1])


class FakeProc(unittest.TestCase):
    def proc(self, pids):
        root = tempfile.mkdtemp()
        for pid, (mountinfo, maps) in pids.items():
            os.makedirs(os.path.join(root, str(pid)))
            for name, text in (("mountinfo", mountinfo), ("maps", maps)):
                with open(os.path.join(root, str(pid), name), "w") as f:
                    f.write(text)
        return root

    def test_a_tree_reports_the_file_systems_of_its_code_and_names_the_bad_files_without_the_work_dir(self):
        root = self.proc({10: (MOUNTINFO, MAPS), 11: (MOUNTINFO, "7f0000000000-7f0000100000 r-xp 00000000 08:01 9 /srv/work/arm/disk/runtime.node\n")})
        t = textmaps.TextMappings(root)
        t.observe([10, 11, 12])      # 12 does not exist: never an error
        got = t.totals(mask="/buffon/home")
        self.assertEqual(got["fs"], {"ext4": 2, "overlay": 1, "tmpfs": 2, "unknown": 1})
        self.assertEqual(sorted(got["bad"]), ["/dev/shm/pig-image", "/memfd:jit (deleted)", "<work>/.pig/aot/slot1.so"])

    def test_a_clean_tree_has_no_bad_files(self):
        root = self.proc({1: (MOUNTINFO, "55d000000000-55d000100000 r-xp 00000000 08:01 1234 /usr/bin/node\n")})
        t = textmaps.TextMappings(root)
        t.observe([1])
        self.assertEqual(t.totals(), {"fs": {"ext4": 1}, "bad": []})


class RealProcess(unittest.TestCase):
    """The whole path on a real process: a child maps a file as code and the meter's sampler reads it."""

    CHILD = "import mmap,os,sys,time\nf=open(sys.argv[1],'r+b')\nm=mmap.mmap(f.fileno(),4096,prot=mmap.PROT_READ|mmap.PROT_EXEC)\nprint('ready',flush=True)\ntime.sleep(float(sys.argv[2]))\n"

    def run_child(self, directory):
        path = os.path.join(directory, "code.bin")
        with open(path, "wb") as f:
            f.write(b"\0" * 4096)
        meter = cgroup.RusageMeter()
        cgroup.TEXT_CLOSED.clear()
        proc = meter.popen([sys.executable, "-c", self.CHILD, path, "1.5"], stdout=subprocess.PIPE, text=True)
        proc.stdout.readline()
        time.sleep(0.6)
        meter.wait(10)
        meter.close()
        return path, cgroup.take_text(None)

    def test_code_mapped_from_dev_shm_is_flagged_and_the_same_from_disk_is_not(self):
        if not os.path.isdir("/proc/self") or textmaps.mount_type("/dev/shm") not in textmaps.BAD_FS:
            self.skipTest("needs Linux /proc and a tmpfs /dev/shm")
        with tempfile.TemporaryDirectory(dir="/dev/shm") as shm:
            path, got = self.run_child(shm)
        self.assertIn(path, got["bad"])
        self.assertIn("tmpfs", got["fs"])
        with tempfile.TemporaryDirectory() as disk:
            if textmaps.mount_type(disk) in textmaps.BAD_FS:
                self.skipTest("the temporary directory is itself on tmpfs")
            path, got = self.run_child(disk)
        self.assertNotIn(path, got["bad"])
        self.assertEqual(got["bad"], [])


class CgroupMeterReadsTheTree(unittest.TestCase):
    def test_the_cgroup_meter_observes_the_mappings_of_the_trees_processes_and_hands_them_over_on_close(self):
        if not os.path.isdir("/proc/self"):
            self.skipTest("Linux only")
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "cgroup.procs"), "w") as f:
                f.write(f"{os.getpid()}\n")
            m = cgroup.CgroupMeter(d)
            cgroup.TEXT_CLOSED.clear()
            m._sample_rss()
            self.assertTrue(m.text.files)
            m._text_at = time.monotonic()        # inside the interval: not read again
            m.text.files.clear()
            m._sample_rss()
            self.assertFalse(m.text.files)
            m.text.files[("/usr/bin/x", (8, 1))] = ("ext4", False)
            m._text_at = time.monotonic() + 1000     # close() reads the tree once more: not inside this test
            m._sampling = False
            m.close()
            self.assertEqual(cgroup.take_text(None), {"fs": {"ext4": 1}, "bad": []})


class EngineFailsTheSample(unittest.TestCase):
    def test_a_sample_whose_tree_ran_code_from_tmpfs_fails_with_the_paths_and_keeps_the_record(self):
        def fn(ctx, a):
            t = textmaps.TextMappings()
            t.files[("/dev/shm/pig-image", (0, 26))] = ("tmpfs", True)
            t.files[("/usr/bin/pig", (8, 1))] = ("ext4", False)
            cgroup.TEXT_CLOSED.append(t)
            return {"cpu_ms": 1.0}
        r = runner([Workload(id="t/w", family="t", fn=fn)], [arm("a")], rounds=1, warmup=0, apis=["openai-completions"], allow_short=True)
        r.measure(FakeCtx(), engine.with_twins(r.plan.arms, "none"))
        s = r.samples[0]
        self.assertIn("shared-memory text", s["failure"])
        self.assertIn("/dev/shm/pig-image", s["failure"])
        self.assertNotIn("cpu_ms", s)
        self.assertEqual(s["text_fs"], {"fs": {"ext4": 1, "tmpfs": 1}, "bad": ["/dev/shm/pig-image"]})

    def test_a_clean_tree_keeps_its_sample_and_records_the_file_systems(self):
        def fn(ctx, a):
            t = textmaps.TextMappings()
            t.files[("/usr/bin/pig", (8, 1))] = ("ext4", False)
            cgroup.TEXT_CLOSED.append(t)
            return {"cpu_ms": 1.0}
        r = runner([Workload(id="t/w", family="t", fn=fn)], [arm("a")], rounds=1, warmup=0, apis=["openai-completions"], allow_short=True)
        r.measure(FakeCtx(), engine.with_twins(r.plan.arms, "none"))
        s = r.samples[0]
        self.assertNotIn("failure", s)
        self.assertEqual(s["text_fs"], {"fs": {"ext4": 1}, "bad": []})

    def test_raw_validation_accepts_the_record_and_rejects_a_malformed_one(self):
        rawlib._check_text_fs({"fs": {"ext4": 2}, "bad": []}, "s")
        for bad in ({"fs": {"ext4": 2}}, {"fs": {"ext4": -1}, "bad": []}, {"fs": {}, "bad": [1]}, "x", {"fs": {"a": True}, "bad": []}):
            with self.assertRaises(rawlib.RawError):
                rawlib._check_text_fs(bad, "s")


if __name__ == "__main__":
    unittest.main()
