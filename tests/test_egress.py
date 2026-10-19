# SPDX-License-Identifier: Apache-2.0
"""The egress audit end to end: a real child process that connects to a non-loopback address must fail its sample and the session.

The child connects a UDP socket to an RFC 5737 documentation address. A UDP connect sends no packet; it only sets the socket's remote address, which
/proc/net/udp then shows. So the test exercises the real audit path (meter sampler -> /proc scan -> egress.OBSERVED -> engine) without any traffic.
"""
import os
import subprocess
import sys
import time
import types
import unittest
from unittest import mock

from buffon import cli
from buffon.runner import cgroup, egress

CHILD = """
import socket, sys, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect((sys.argv[1], 9))
time.sleep(1.5)
"""

LINUX = sys.platform.startswith("linux") and os.path.isdir("/proc/net")
AUDITED = egress.has_proc() or bool(egress.lsof_path())    # /proc on Linux, lsof where there is none (macOS)


class ProcNet(unittest.TestCase):
    TABLE = (
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        "   0: 0100007F:1F90 0100007F:A1B2 01 00000000:00000000 00:00000000 00000000  1000        0 111 1 0 20 4 30 10 -1\n"
        "   1: 0A00000A:C350 097100CB:01BB 02 00000000:00000000 00:00000000 00000000  1000        0 222 1 0 20 4 30 10 -1\n"
        "   2: 00000000:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 333 1 0 20 4 30 10 -1\n")

    def test_parses_the_remote_address_not_the_local_one(self):
        table = egress.parse_proc_net(self.TABLE)
        self.assertEqual(table[111], ("127.0.0.1", 0xA1B2))
        self.assertEqual(table[222], ("203.0.113.9", 443))   # a SYN_SENT connect attempt (st 02) counts: the remote is set
        self.assertEqual(table[333], ("0.0.0.0", 0))

    def test_only_loopback_and_unconnected_are_local(self):
        for ip in ("127.0.0.1", "127.5.6.7", "::1", "0.0.0.0", "::", "::ffff:127.0.0.1"):
            self.assertTrue(egress.is_local(ip), ip)
        for ip in ("203.0.113.9", "198.51.100.7", "192.0.2.1", "2001:db8::1", "::ffff:203.0.113.9"):
            self.assertFalse(egress.is_local(ip), ip)

    def test_scan_reports_only_the_non_loopback_sockets_of_the_given_processes(self):
        saved = egress.socket_inodes
        egress.socket_inodes = lambda pid: {"p1": {111, 333}, "p2": {222}}.get(pid, set())
        try:
            read = lambda name: self.TABLE if name == "tcp" else "header\n"  # noqa: E731
            self.assertEqual(egress.scan(["p1", "p2"], read=read), {"203.0.113.9:443"})
            self.assertEqual(egress.scan(["p1"], read=read), set())
        finally:
            egress.socket_inodes = saved


LSOF_OUT = "p4242\nf5\nn127.0.0.1:50000->127.0.0.1:8080\nf6\nn[::1]:50001->[::1]:8080\nf7\nn*:8080\nf8\nn203.0.113.9:50002->198.51.100.7:443\nf9\nn[2001:db8::2]:50003->[2001:db8::1]:443\nf10\nn*:5353\n"


class Lsof(unittest.TestCase):
    """The audit where there is no /proc (macOS): `lsof -F n` names a connected socket as local->remote."""

    def test_parses_the_remote_of_connected_sockets_only(self):
        self.assertEqual(egress.parse_lsof(LSOF_OUT), [("127.0.0.1", 8080), ("::1", 8080), ("198.51.100.7", 443), ("2001:db8::1", 443)])

    def test_scan_without_proc_runs_lsof_and_keeps_the_non_loopback_remotes(self):
        calls = []

        def run(argv, **kw):
            calls.append(argv)
            return types.SimpleNamespace(stdout=LSOF_OUT, returncode=0)
        with mock.patch.object(egress, "has_proc", lambda: False), mock.patch.object(egress, "lsof_path", lambda: "/x/lsof"), mock.patch.object(egress.subprocess, "run", run):
            self.assertEqual(egress.scan([7, 8]), {"198.51.100.7:443", "2001:db8::1:443"})
        self.assertEqual(calls[0][:7], ["/x/lsof", "-nP", "-b", "-w", "-a", "-p", "7,8"])

    def test_a_remote_that_is_not_an_address_counts_as_outside_the_loopback(self):
        # review: a name lsof did not resolve to a number (or a form is_local cannot parse) is not known to be local
        def run(argv, **kw):
            return types.SimpleNamespace(stdout="p1\nf3\nn127.0.0.1:5->relay.example.org:443\n", returncode=0)
        with mock.patch.object(egress, "has_proc", lambda: False), mock.patch.object(egress, "lsof_path", lambda: "/x/lsof"), mock.patch.object(egress.subprocess, "run", run):
            self.assertEqual(egress.scan([1]), {"relay.example.org:443"})

    def test_a_failing_lsof_is_an_unaudited_sample_and_a_missing_one_is_mode_none(self):
        def boom(*a, **k):
            raise OSError("no lsof")

        def slow(*a, **k):
            raise subprocess.TimeoutExpired("lsof", 15)
        # review: a failed audit used to read as a clean one (an empty set)
        for fail, name in ((boom, "OSError"), (slow, "TimeoutExpired")):
            with mock.patch.object(egress, "has_proc", lambda: False), mock.patch.object(egress, "lsof_path", lambda: "/x/lsof"), mock.patch.object(egress.subprocess, "run", fail):
                self.assertEqual(egress.scan([1]), {f"unaudited(lsof {name})"})
        with mock.patch.object(egress, "has_proc", lambda: False), mock.patch.object(egress, "lsof_path", lambda: None), mock.patch.object(egress, "netns_isolated", lambda: False):
            self.assertEqual(egress.scan([1]), set())
            self.assertEqual(egress.describe()["mode"], "none")
            self.assertIn("unavailable", egress.describe()["note"])
            self.assertEqual(egress.sample_interval(), egress.SAMPLE_INTERVAL_S)
        with mock.patch.object(egress, "has_proc", lambda: False), mock.patch.object(egress, "lsof_path", lambda: "/x/lsof"), mock.patch.object(egress, "netns_isolated", lambda: False):
            self.assertEqual((egress.describe()["mode"], egress.describe()["source"]), ("socket-audit", "lsof"))
            self.assertEqual(egress.sample_interval(), egress.LSOF_INTERVAL_S)

    @unittest.skipUnless(egress.lsof_path(), "lsof is not installed")
    def test_real_lsof_sees_a_connected_udp_socket_of_a_child(self):
        child = subprocess.Popen([sys.executable, "-c", CHILD.replace("1.5", "300"), "203.0.113.9"])
        try:
            found, deadline = set(), time.monotonic() + 240
            while not found and time.monotonic() < deadline:
                found = egress.scan_lsof([child.pid])
                time.sleep(0.05)
            self.assertEqual(found, {"203.0.113.9:9"})
        finally:
            child.kill()
            child.wait()


@unittest.skipUnless(AUDITED, "no /proc and no lsof: this platform has no socket audit")
class RealConnect(unittest.TestCase):
    def setUp(self):
        egress.take()

    def run_child(self, meter, target):
        proc = meter.popen([sys.executable, "-c", CHILD, target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if isinstance(meter, cgroup.RusageMeter):
            meter.wait(10)
        else:
            proc.wait(10)
        meter.close()
        return egress.take()

    def meters(self):
        yield cgroup.RusageMeter()
        meter = cgroup.new_meter()
        if not isinstance(meter, cgroup.RusageMeter):
            yield meter
        else:
            meter.close()

    def test_a_non_loopback_connect_is_observed_by_every_meter(self):
        for meter in self.meters():
            with self.subTest(meter=meter.mode):
                self.assertEqual(self.run_child(meter, "203.0.113.9"), {"203.0.113.9:9"})

    def test_a_loopback_connect_is_not_a_violation(self):
        for meter in self.meters():
            with self.subTest(meter=meter.mode):
                self.assertEqual(self.run_child(meter, "127.0.0.1"), set())


class SessionExit(unittest.TestCase):
    def run_session(self, violations):
        raw = {"samples": [], "hardware": {"class": "provisional"}, "egress": {"violations": violations}}
        from buffon.runner import engine
        saved_run, saved_plan = engine.run_session, cli.session_plan
        engine.run_session = lambda plan: raw
        cli.session_plan = lambda args: types.SimpleNamespace(out="x")
        try:
            return cli.cmd_session(types.SimpleNamespace())
        finally:
            engine.run_session, cli.session_plan = saved_run, saved_plan

    def test_an_egress_violation_is_exit_code_4(self):
        self.assertEqual(self.run_session([{"arm": "a", "remotes": ["203.0.113.9:443"]}]), cli.EXIT_EGRESS)
        self.assertEqual(self.run_session([]), 0)


if __name__ == "__main__":
    unittest.main()
