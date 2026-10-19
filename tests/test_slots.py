# SPDX-License-Identifier: Apache-2.0
"""buffon/runner/slots.py and the slot mode of `buffon campaign`: the partition of a host into slots, the slot calibration gate, the fallback to serial, the lock a slot's
session takes, the trust reason, and a campaign dry run. The host is a fake topology and the sessions are fake run functions: nothing is measured."""
import argparse
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

from buffon import backend, campaign, site as sitelib, trust
from buffon.runner import quiet, slots
from tests import test_campaign as tc


def host(sockets=2, cores=16, threads=2, nodes_per_socket=1, housekeeping_node=None):
    """A fake host laid out like Linux numbers it: the first thread of every core, then the second threads. Cores are split evenly over the nodes of a socket."""
    total = sockets * cores
    rows, node_size = [], cores // nodes_per_socket
    for socket in range(sockets):
        for core in range(cores):
            first = socket * cores + core
            node = socket * nodes_per_socket + core // node_size
            rows.append(slots.Core(tuple(first + t * total for t in range(threads)), socket, node))
    return slots.Topology(rows)


class Partition(unittest.TestCase):
    def test_slots_are_whole_cores_with_their_smt_siblings_and_share_nothing(self):
        topo = host()
        made = slots.partition(topo, 8, 2, 4)
        seen = set()
        for s in made:
            mine = set(s.cpus) | set(s.mock_cpus)
            self.assertFalse(mine & seen, "a CPU is in two slots")
            seen |= mine
            self.assertEqual((len(s.cpus), len(s.mock_cpus)), (8, 2))
            for cpu in mine:   # every core is wholly in one slot, harness or mock, never split between them
                core = set(topo.core_of(cpu).cpus)
                self.assertTrue(core <= set(s.cpus) or core <= set(s.mock_cpus), (s.id, cpu))
        self.assertEqual(len(seen), 4 * 10)

    def test_the_lowest_core_stays_with_the_host(self):
        made = slots.partition(host(), 8, 2, 6)
        used = {c for s in made for c in (*s.cpus, *s.mock_cpus)}
        self.assertFalse(used & {0, 32})   # core 0 and its sibling

    def test_each_slot_sits_on_one_numa_node_and_the_nodes_share_the_slots(self):
        made = slots.partition(host(), 8, 2, 4)
        self.assertEqual([s.nodes for s in made], [(0,), (0,), (1,), (1,)])
        made = slots.partition(host(sockets=2, cores=16, nodes_per_socket=2), 4, 2, 6)   # four nodes of 8 cores, one of them 7 after the host's core
        self.assertTrue(all(len(s.nodes) == 1 for s in made))
        self.assertEqual(sorted(len([s for s in made if s.nodes == (n,)]) for n in range(4)), [1, 1, 2, 2])

    def test_two_slots_on_a_two_socket_host_take_one_socket_each(self):
        # the launch host's layout: 2 sockets of 32 cores, 2-way SMT, Linux numbering (first threads 0-63, siblings 64-127), one session of 8 harness and 2 mock CPUs
        made = slots.partition(host(sockets=2, cores=32), 8, 2, 2)
        self.assertEqual(sorted(s.nodes for s in made), [(0,), (1,)])
        socket_of = {cpu: c.package for c in host(sockets=2, cores=32).cores for cpu in c.cpus}
        for s in made:
            self.assertEqual(len({socket_of[c] for c in (*s.cpus, *s.mock_cpus)}), 1, s.describe())

    def test_a_slot_spans_nodes_only_when_no_node_has_room_for_it(self):
        topo = host(sockets=2, cores=7, threads=1)   # node 0 has 6 cores after the host's, node 1 has 7; a slot is 4 cores
        made = slots.partition(topo, 3, 1, 3)
        self.assertEqual(sorted(len(s.nodes) for s in made), [1, 1, 2])
        self.assertIn("spans nodes", [s for s in made if len(s.nodes) == 2][0].describe())

    def test_refusals(self):
        topo = host()
        cases = [
            ("one slot is today", lambda: slots.partition(topo, 8, 2, 1), "at least 2"),
            ("no mock", lambda: slots.partition(topo, 8, 0, 4), "mock CPUs"),
            ("no harness", lambda: slots.partition(topo, 0, 2, 4), "harness CPUs"),
            ("a session that does not fill whole cores", lambda: slots.partition(topo, 3, 2, 4), "share a core"),
            ("too many slots", lambda: slots.partition(topo, 8, 2, 7), "need 35 whole cores"),
            ("nothing allowed", lambda: slots.partition(topo, 8, 2, 4, allowed=[]), "no whole physical core"),
        ]
        for name, call, message in cases:
            with self.subTest(name), self.assertRaisesRegex(slots.SlotError, message):
                call()

    def test_a_core_the_runner_may_only_half_use_is_left_out(self):
        topo = host(sockets=1, cores=8)   # CPUs 0-7 and their siblings 8-15
        allowed = [c for c in range(16) if c != 9]   # core 1's second thread is not ours
        made = slots.partition(topo, 4, 2, 2, allowed=allowed)
        used = {c for s in made for c in (*s.cpus, *s.mock_cpus)}
        self.assertNotIn(1, used)
        self.assertNotIn(9, used)
        with self.assertRaisesRegex(slots.SlotError, "need 9 whole cores.*7 usable"):
            slots.partition(topo, 4, 2, 3, allowed=allowed)

    def test_a_cpu_set_that_shares_a_core_or_is_too_small_is_refused(self):
        topo = host(sockets=1, cores=8)
        S = slots.Slot
        with self.assertRaisesRegex(slots.SlotError, "share a core"):   # slot 2 holds CPU 1, whose sibling 9 is slot 1's
            slots.check_partition([S(1, (0, 8, 9), (2, 10)), S(2, (1, 3, 11), (4, 12))], topo, 2)
        with self.assertRaisesRegex(slots.SlotError, "slots share a core"):   # a CPU twice
            slots.check_partition([S(1, (0, 8), (2, 10)), S(2, (0, 8), (4, 12))], topo, 2)
        with self.assertRaisesRegex(slots.SlotError, "fewer than the 4"):
            slots.check_partition([S(1, (0, 8), (2, 10))], topo, 4)
        with self.assertRaisesRegex(slots.SlotError, "may not use"):
            slots.check_partition([S(1, (0, 8), (2, 10))], topo, 2, allowed=[0, 8, 2])
        slots.check_partition([S(1, (0, 8), (2, 10)), S(2, (1, 9), (3, 11))], topo, 2)

    def test_the_topology_is_read_from_sysfs(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)

        def put(path, text):
            os.makedirs(os.path.dirname(os.path.join(root, path)), exist_ok=True)
            with open(os.path.join(root, path), "w") as f:
                f.write(text)
        put("cpu/online", "0-3")
        for cpu, siblings in ((0, "0,2"), (1, "1,3"), (2, "0,2"), (3, "1,3")):
            put(f"cpu/cpu{cpu}/topology/thread_siblings_list", siblings)
            put(f"cpu/cpu{cpu}/topology/physical_package_id", str(cpu % 2))
        put("node/node0/cpulist", "0,2")
        put("node/node1/cpulist", "1,3")
        topo = slots.read_topology(root)
        self.assertEqual([(c.cpus, c.package, c.node) for c in topo.cores], [((0, 2), 0, 0), ((1, 3), 1, 1)])
        self.assertIsNone(slots.read_topology(os.path.join(root, "nowhere")))


def samples(ref, copy, rounds=12, warmup=1):
    """The measured samples of the reference arm and its copy: one overhead/print cell, cpu_ms and wall_ms from the two lists (one value per round)."""
    out = []
    for arm, values in (("pi-node", ref), ("pi-node-b", copy)):
        for r in range(warmup + rounds):
            v = values[max(0, r - warmup)]
            out.append({"arm": arm, "scenario": "overhead/print", "api": "openai-completions", "round": max(0, r - warmup), "warmup": r < warmup, "cpu_ms": v, "wall_ms": v * 1.5})
    return out


STEADY = [100 * (1 + d) for d in (0, 0.01, -0.01, 0.005, -0.005, 0.008, -0.008, 0.002, -0.002, 0.006, -0.006, 0.0)]
OTHER = [100 * (1 + d) for d in (0.004, -0.004, 0.009, -0.009, 0, 0.003, -0.003, 0.007, -0.007, 0.001, -0.001, 0.0)]


def scaled(values, k):
    return [v * k for v in values]


class Gate(unittest.TestCase):
    def verdict(self, **concurrent):
        solo = samples(STEADY, OTHER)
        return slots.judge(solo, {int(k[1:]): v for k, v in concurrent.items()}, "pi-node", 0.05, 12, overlap=1.0)

    def test_a_slot_the_concurrency_does_not_move_passes(self):
        v = self.verdict(s1=samples(STEADY, OTHER), s2=samples(OTHER, STEADY))
        self.assertEqual(v["usable"], [1, 2], [r["problems"] for r in v["slots"]])

    def test_a_slot_whose_concurrent_median_moves_past_the_solo_floor_fails_and_the_others_still_pass(self):
        v = self.verdict(s1=samples(STEADY, OTHER), s2=samples(scaled(STEADY, 1.10), scaled(OTHER, 1.10)))
        self.assertEqual(v["usable"], [1])
        bad = next(r for r in v["slots"] if r["id"] == 2)
        self.assertFalse(bad["pass"])
        self.assertTrue(any("median moved +10.0%" in p and "A/A floor" in p for p in bad["problems"]), bad["problems"])
        self.assertFalse(next(c for c in bad["cells"] if c["metric"] == "cpu_ms")["within"])

    def test_the_move_is_judged_in_both_directions(self):
        v = self.verdict(s1=samples(scaled(STEADY, 0.9), scaled(OTHER, 0.9)))
        self.assertEqual(v["usable"], [])

    def test_a_slot_above_the_cv_gate_fails_even_when_its_median_holds(self):
        noisy = [100, 140, 70, 100, 130, 80, 100, 100, 120, 85, 100, 100]
        solo = samples(STEADY, OTHER)
        v = slots.judge(solo, {1: samples(noisy, noisy[::-1])}, "pi-node", 0.05, 12, overlap=1.0)
        self.assertEqual(v["usable"], [])
        self.assertTrue(any("CV of cpu_ms" in p and "above the gate" in p for p in v["slots"][0]["problems"]))

    def test_a_solo_run_that_is_itself_noisy_judges_nothing(self):
        noisy = [100, 140, 70, 100, 130, 80, 100, 100, 120, 85, 100, 100]
        v = slots.judge(samples(noisy, noisy[::-1]), {1: samples(noisy, noisy[::-1])}, "pi-node", 0.05, 12, overlap=1.0)
        self.assertEqual(v["usable"], [])
        self.assertTrue(any("solo run's CV" in p for p in v["solo"]["problems"]))

    def test_sessions_that_did_not_run_together_are_not_a_concurrent_measurement(self):
        v = slots.judge(samples(STEADY, OTHER), {1: samples(STEADY, OTHER)}, "pi-node", 0.05, 12, overlap=0.2)
        self.assertEqual(v["usable"], [])
        self.assertTrue(any("ran together for only 20%" in p for p in v["slots"][0]["problems"]))

    def test_a_slot_with_too_few_good_rounds_or_no_samples_fails(self):
        few = [s for s in samples(STEADY, OTHER) if s["round"] < 6]
        v = self.verdict(s1=few, s2=None)
        self.assertEqual(v["usable"], [])
        self.assertTrue(any("usable rounds of 12" in p for p in v["slots"][0]["problems"]))
        self.assertIn("the session left no samples", v["slots"][1]["problems"])


class Calibrate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.slots = slots.partition(host(), 8, 2, 4)
        self.calls = []

    def fake(self, scale=None, exits=None, times=("2026-10-17T10:00:00Z", "2026-10-17T10:10:00Z")):
        """A run function that leaves a raw.json in the argv's --out: values scaled per slot (scale {slot: factor}), a session exit per slot."""
        scale, exits = scale or {}, exits or {}

        def run(argv, log_path=None):
            self.calls.append(argv)
            out = argv[argv.index("--out") + 1]
            slot = int(argv[argv.index("--slot") + 1])
            concurrent = os.path.basename(out) != "solo"
            k = scale.get(slot, 1.0) if concurrent else 1.0
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "raw.json"), "w") as f:
                json.dump({"run": {"started_utc": times[0], "finished_utc": times[1]}, "samples": samples(scaled(STEADY, k), scaled(OTHER, k))}, f)
            return exits.get(slot, 0) if concurrent else 0
        return run

    def go(self, run):
        return slots.calibrate(self.slots, run, lambda slot, d: ["run", "--out", d, "--slot", str(slot)], self.tmp, "pi-node", 12, 0.05, log=lambda *_: None)

    def test_solo_first_in_the_first_slot_then_every_slot_at_once_and_the_verdict_is_written(self):
        v = self.go(self.fake())
        outs = [os.path.basename(a[a.index("--out") + 1]) for a in self.calls]
        self.assertEqual((outs[0], sorted(outs[1:])), ("solo", ["slot-1", "slot-2", "slot-3", "slot-4"]))
        self.assertEqual(self.calls[0][self.calls[0].index("--slot") + 1], "1")
        with open(os.path.join(self.tmp, slots.FILE)) as f:
            doc = json.load(f)
        self.assertEqual((doc["usable"], doc["fallback"]), ([1, 2, 3, 4], None))
        self.assertEqual([s["cpus"] for s in doc["slots"]], [slots.format_cpus(s.cpus) for s in self.slots])
        for s in self.slots:
            self.assertTrue(slots.passed(os.path.join(self.tmp, slots.FILE), s.id))

    def test_a_slot_that_moves_or_whose_session_fails_is_not_used(self):
        v = self.go(self.fake(scale={2: 1.2}, exits={3: 1}))
        self.assertEqual(v["usable"], [1, 4])
        self.assertFalse(slots.passed(os.path.join(self.tmp, slots.FILE), 2))
        self.assertFalse(slots.passed(os.path.join(self.tmp, slots.FILE), 3))
        self.assertIn("the session exited 1", next(r for r in v["slots"] if r["id"] == 3)["problems"][0])

    def test_no_passing_slot_means_serial(self):
        v = self.go(self.fake(scale={1: 1.3, 2: 1.3, 3: 1.3, 4: 1.3}))
        self.assertEqual((v["usable"], v["fallback"]), ([], "serial"))
        self.assertIsNone(slots.reusable(self.tmp, self.slots))   # a calibration that passed no slot is run again on resume

    def test_a_passed_calibration_is_reused_only_for_the_same_slots(self):
        self.go(self.fake())
        self.assertEqual(slots.reusable(self.tmp, self.slots)["usable"], [1, 2, 3, 4])
        self.assertIsNone(slots.reusable(self.tmp, slots.partition(host(), 8, 2, 3)))

    def test_sessions_that_barely_overlapped_are_refused(self):
        starts = iter(["2026-10-17T10:00:00Z", "2026-10-17T10:00:00Z", "2026-10-17T10:09:00Z", "2026-10-17T10:00:00Z", "2026-10-17T10:00:00Z"])
        run = self.fake()

        def staggered(argv, log_path=None):
            code = run(argv, log_path)
            out = argv[argv.index("--out") + 1]
            path = os.path.join(out, "raw.json")
            with open(path) as f:
                doc = json.load(f)
            if os.path.basename(out) == "slot-3":
                doc["run"]["started_utc"], doc["run"]["finished_utc"] = "2026-10-17T10:08:00Z", "2026-10-17T10:18:00Z"
            with open(path, "w") as f:
                json.dump(doc, f)
            return code
        v = self.go(staggered)
        self.assertEqual(v["usable"], [])
        self.assertLess(v["overlap"], slots.MIN_OVERLAP)


class Locks(unittest.TestCase):
    def test_slots_run_together_but_not_beside_a_serial_run(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        host_lock = os.path.join(d, "buffon.lock")
        a = quiet.HostLock(slots.lock_path(host_lock, 1), shared=[host_lock])
        b = quiet.HostLock(slots.lock_path(host_lock, 2), shared=[host_lock])
        with a, b:
            with self.assertRaises(quiet.LockHeld):   # a serial run wants the host lock exclusively
                quiet.HostLock(host_lock).__enter__()
            with self.assertRaises(quiet.LockHeld):   # the same slot twice
                quiet.HostLock(slots.lock_path(host_lock, 1), shared=[host_lock]).__enter__()
        with quiet.HostLock(host_lock):
            with self.assertRaisesRegex(quiet.LockHeld, "serial run"):
                quiet.HostLock(slots.lock_path(host_lock, 1), shared=[host_lock]).__enter__()


class Trust(unittest.TestCase):
    def raw(self, slot):
        run = {"host_class": "A", "preflight": {"reasons": []}, "rounds": 12}
        if slot is not None:
            run["slot"] = slot
        return {"run": run, "hardware": {"quiet_dedicated": True}, "calibration": {"passed": True, "max_cv": 0.01, "gate": 0.05}, "samples": [], "preflight": {"class": "A"}}

    def test_a_slot_without_a_passing_calibration_is_slotted_and_cannot_be_verified(self):
        for slot in ({"id": 2, "of": 4, "cpus": "8-15", "calibration": None},):
            info = trust.badge(self.raw(slot), reproduced=True)
            self.assertTrue(any(r.startswith("slotted:") for r in info["reasons"]))
            self.assertNotEqual(info["badge"], "Verified")

    def test_a_passed_slot_calibration_adds_nothing(self):
        slotted = trust.badge(self.raw({"id": 2, "of": 4, "cpus": "8-15", "calibration": "/c/slots-calibration.json"}), reproduced=True)
        plain = trust.badge(self.raw(None), reproduced=True)
        self.assertEqual((slotted["badge"], slotted["reasons"]), (plain["badge"], plain["reasons"]))


class Select(unittest.TestCase):
    def site(self, **extra):
        data = {"site": {"backend": "local"}, "local": {"cpus": "2-9", "mock_cpus": "1", "pinning": "required", "slots": 4, **extra}}
        return sitelib.from_dict(data, env={})

    def test_a_slot_gets_its_own_cpus_and_the_others_are_named(self):
        s = self.site()
        slot = slots.select(s, 3, topology=host(), allowed=range(64))
        self.assertEqual((s.local.cpus, s.local.mock_cpus), (list(slot.cpus), list(slot.mock_cpus)))
        self.assertEqual(s.local.slot["of"], 4)
        self.assertFalse(set(s.local.slot["others"]) & (set(slot.cpus) | set(slot.mock_cpus)))
        self.assertEqual(len(s.local.slot["others"]), 30)
        self.assertEqual(s.describe()["local"]["slot"], {"id": 3, "of": 4})

    def test_a_slot_the_calibration_does_not_pass_is_refused(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, slots.FILE)
        with open(path, "w") as f:
            json.dump({"usable": [1, 2]}, f)
        slots.select(self.site(), 2, path, topology=host(), allowed=range(64))
        with self.assertRaisesRegex(slots.SlotError, "does not pass slot 3"):
            slots.select(self.site(), 3, path, topology=host(), allowed=range(64))
        with self.assertRaisesRegex(slots.SlotError, "slots 1 to 4"):
            slots.select(self.site(), 5, topology=host(), allowed=range(64))

    def test_the_site_profile_refuses_what_a_slot_cannot_be_built_from(self):
        for local, message in (({"cpus": "2-9", "pinning": "required", "slots": 2}, "needs `cpus` and `mock_cpus`"),
                               ({"cpus": "2-9", "mock_cpus": "1", "slots": 2}, "needs pinning"),
                               ({"cpus": "2-9", "mock_cpus": "1", "pinning": "required", "slots": 0}, "positive integer")):
            with self.subTest(message), self.assertRaisesRegex(sitelib.SiteError, message):
                sitelib.from_dict({"local": local}, env={})
        with self.assertRaisesRegex(sitelib.SiteError, "applies to a local site"):
            sitelib.from_dict({"site": {"backend": "kubernetes"}, "local": {"slots": 2, "cpus": "1", "mock_cpus": "0", "pinning": "required"},
                               "kubernetes": {"namespace": "n", "image": "r/a@sha256:" + "a" * 64}}, env={})
        self.assertEqual(sitelib.from_dict({}, env={}).local.slots, 1)


class CampaignSlots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plan = os.path.join(self.tmp, "plan.toml")
        with open(self.plan, "w") as f:
            f.write(tc.PLAN)
        self.out = os.path.join(self.tmp, "c")
        self.calls, self.scale = [], {}
        self.topology = host()

    def site(self, slots_n=4, cpus="2-9", mock="1"):
        path = os.path.join(self.tmp, "site.toml")
        with open(path, "w") as f:
            f.write(f'[site]\nbackend = "local"\n[local]\ncpus = "{cpus}"\nmock_cpus = "{mock}"\npinning = "required"\nslots = {slots_n}\n')
        return path

    def fake_run(self, argv, log_path=None):
        self.calls.append((argv, log_path))
        out = argv[argv.index("--out") + 1]
        os.makedirs(out, exist_ok=True)
        if argv[0] == "perfcheck":
            with open(os.path.join(out, "perfcheck-summary.json"), "w") as f:
                json.dump({"all_counted": True, "text": ""}, f)
            return 0
        doc = {}
        if "--no-calibrate" in argv:   # a slot calibration session
            k = self.scale.get(int(argv[argv.index("--slot") + 1]), 1.0) if os.path.basename(out) != "solo" else 1.0
            doc = {"run": {"started_utc": "2026-10-17T10:00:00Z", "finished_utc": "2026-10-17T10:10:00Z"}, "samples": samples(scaled(STEADY, k), scaled(OTHER, k))}
        with open(os.path.join(out, "raw.json"), "w") as f:
            json.dump(doc, f)
        return 0

    def go(self, site=None, **flags):
        args = argparse.Namespace(plan=self.plan, site=site or self.site(), out=self.out, bundle=None, wait_cluster=0, dry_run=False, parallel=False)
        for k, v in flags.items():
            setattr(args, k, v)
        lines = []
        verify = lambda dirs: {d: {"accepted": True, "errors": []} for d in dirs}
        with mock.patch.object(backend, "get_backend", lambda s: tc.FakeBackend()), mock.patch.object(campaign, "verify", verify), redirect_stderr(io.StringIO()) as err:
            code = campaign.main(args, run=self.fake_run, log=lines.append, topology=self.topology, allowed=range(64))
        self.err = err.getvalue()
        return code, lines

    def state(self):
        with open(os.path.join(self.out, campaign.STATE)) as f:
            return json.load(f)

    def runs(self):
        return [a for a, _ in self.calls if a[0] == "run" and "--no-calibrate" not in a]

    def test_a_dry_run_on_a_two_socket_32_core_host_prints_the_slots_and_the_plan_and_runs_nothing(self):
        code, lines = self.go(dry_run=True)
        text = "\n".join(lines)
        self.assertEqual((code, self.calls), (0, []))
        self.assertIn("slots: 4 on this host, each 8 harness CPUs and 2 mock CPUs", text)
        self.assertEqual(len([ln for ln in lines if "harness CPUs" in ln and "slot " in ln]), 4)
        self.assertIn("slot 1: harness CPUs 1-4,33-36, mock CPUs 5,37 (NUMA node 0)", text)
        self.assertIn("(NUMA node 1)", text)
        self.assertEqual([ln.split()[3] for ln in lines if ln.split()[2] in ("step", "done")], ["perfcheck:", "slots-calibration:", "ov:", "st:"])
        self.assertIn("--slot <slot> --slot-calibration " + os.path.join(self.out, "slots-calibration.json"), text)
        self.assertIn("one per slot that passes the slot calibration", text)
        self.assertFalse(os.path.exists(self.out))

    def test_every_session_runs_pinned_to_its_slot_in_its_own_process_and_the_state_records_the_slots(self):
        code, lines = self.go()
        self.assertEqual(code, 0, self.err)
        runs = self.runs()
        self.assertEqual(len(runs), 2)
        slot_ids = [int(a[a.index("--slot") + 1]) for a in runs]
        self.assertEqual(len(set(slot_ids)), 2)   # at once, so on two slots
        cal = os.path.join(self.out, slots.FILE)
        for a in runs:
            self.assertEqual(a[a.index("--slot-calibration") + 1], cal)
        self.assertTrue(all(log for argv, log in self.calls if argv[0] == "run"))   # a child process each: the pinning is per process
        st = self.state()
        self.assertEqual([s["id"] for s in st["slots"]], [1, 2, 3, 4])
        self.assertEqual(set(st["slots"][0]), {"id", "cpus", "mock_cpus"})
        ran_in = {os.path.basename(a[a.index("--out") + 1]): int(a[a.index("--slot") + 1]) for a in runs}
        self.assertEqual({k: v["slot"] for k, v in st["steps"].items() if k in ("ov", "st")}, ran_in)
        self.assertEqual(st["steps"]["slots-calibration"]["usable"], [1, 2, 3, 4])
        from buffon import cli
        for argv, _ in self.calls:
            cli.build_parser().parse_args(argv)   # the real parser takes every line the campaign issues

    def test_a_slot_that_fails_the_calibration_gets_no_family(self):
        self.scale = {1: 1.3}
        code, lines = self.go()
        self.assertEqual(code, 0)
        self.assertIn("slot(s) 1 failed the slot calibration and are not used", "\n".join(lines))
        self.assertNotIn(1, [int(a[a.index("--slot") + 1]) for a in self.runs()])

    def test_with_no_passing_slot_the_families_run_one_after_the_other_on_the_sites_own_cpus(self):
        self.scale = {1: 1.3, 2: 1.3, 3: 1.3, 4: 1.3}
        code, lines = self.go()
        self.assertEqual(code, 0)
        self.assertIn("falling back to serial", "\n".join(lines))
        runs = self.runs()
        self.assertEqual([os.path.basename(a[a.index("--out") + 1]) for a in runs], ["ov", "st"])
        for a in runs:
            self.assertNotIn("--slot", a)
            self.assertNotIn("--slot-calibration", a)
        self.assertEqual(self.state()["steps"]["slots-calibration"]["exit"], campaign.EXIT_REFUSED)
        self.assertIsNone(self.state()["steps"]["ov"]["slot"])

    def test_resuming_does_not_calibrate_again_and_a_finished_family_is_not_run_again(self):
        self.go()
        self.calls.clear()
        code, lines = self.go()
        self.assertEqual(code, 0)
        self.assertEqual(self.calls, [])
        self.assertIn("passed before", "\n".join(lines))

    def test_a_site_whose_slots_cannot_be_built_is_refused_before_anything_runs(self):
        code, _ = self.go(site=self.site(slots_n=9))
        self.assertEqual((code, self.calls), (campaign.EXIT_REFUSED, []))
        self.assertIn("need 45 whole cores", self.err)
        self.topology = None
        with mock.patch.object(slots, "read_topology", lambda: None):
            code, _ = self.go()
        self.assertEqual(code, campaign.EXIT_REFUSED)
        self.assertIn("CPU topology", self.err)

    def test_a_site_without_slots_still_runs_one_session_after_the_other(self):
        code, _ = self.go(site=self.site(slots_n=1))
        self.assertEqual(code, 0)
        self.assertEqual([a[0] for a, _ in self.calls], ["perfcheck", "run", "run"])
        self.assertTrue(all("--slot" not in a for a, _ in self.calls))
        self.assertNotIn("slots", self.state())


class SessionPlan(unittest.TestCase):
    def test_a_slot_session_takes_its_own_lock_records_its_slot_and_names_the_other_cpus(self):
        from buffon import cli
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        cal = os.path.join(d, slots.FILE)
        with open(cal, "w") as f:
            json.dump({"usable": [2]}, f)
        args = cli.build_parser().parse_args(["session", "overhead/print", "--cpus", "8-11", "--mock-cpus", "7", "--slot", "2/4", "--slot-others", "12-40", "--slot-calibration", cal, "--out", d])
        plan = cli.session_plan(args)
        self.assertEqual(plan.slot, {"id": 2, "of": 4, "cpus": "8-11", "calibration": cal})
        self.assertEqual(plan.lock_file, slots.lock_path(quiet.DEFAULT_LOCK, 2))
        self.assertEqual(plan.slot_others, list(range(12, 41)))
        args = cli.build_parser().parse_args(["session", "overhead/print", "--slot", "3/4", "--slot-calibration", cal, "--out", d])
        self.assertIsNone(cli.session_plan(args).slot["calibration"])   # slot 3 did not pass: no calibration is recorded for it
        args = cli.build_parser().parse_args(["session", "overhead/print", "--out", d])
        plan = cli.session_plan(args)
        self.assertEqual((plan.slot, plan.lock_file), (None, quiet.DEFAULT_LOCK))


class Housekeeping(unittest.TestCase):
    def test_the_cpus_of_other_slots_are_not_housekeeping(self):
        from buffon.runner import preflight
        kw = dict(online=range(8), isolated=range(8), siblings=lambda c: [c], node_of=lambda c: 0, quota=[], governors={2: "performance", 3: "performance"}, turbo_off=True, partition=True)
        alone = preflight.run([2, 3], [1], **kw)
        crowded = preflight.run([2, 3], [1], reserved=[0, 4, 5, 6, 7], **kw)
        self.assertEqual(alone["class"], "A")
        self.assertEqual(crowded["class"], "B")
        self.assertTrue(any("0 online CPUs are left" in c["detail"] for c in crowded["checks"] if c["name"] == "housekeeping"))


if __name__ == "__main__":
    unittest.main()
