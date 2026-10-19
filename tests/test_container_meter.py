"""ContainerMeter: the argv it runs, how the container's cgroup is found, and the exact final counters from the relay (the cgroup is gone when the container stops)."""
import json
import os
import subprocess
import tempfile
import unittest

from buffon.envelope import lint
from buffon.runner import cgroup, container

DIGEST = "debian@sha256:" + "b" * 64


def fast_clock():
    """A clock that advances 1 s per reading: the cgroup lookup's 10 s wait ends at once when no scope directory exists, instead of spinning for 10 real seconds."""
    now = {"t": 0.0}

    def clock():
        now["t"] += 1.0
        return now["t"]
    return clock


class FakeProc:
    def __init__(self, argv, **kw):
        self.argv, self.kw, self.returncode, self.pid = argv, kw, 0, 4242

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0


class Recorder:
    def __init__(self, cid="c" * 64):
        self.calls, self.cid = [], cid

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        if "--cidfile" in argv:
            with open(argv[argv.index("--cidfile") + 1], "w") as f:
                f.write(self.cid)
        return FakeProc(argv, **kw)


def config(tmp):
    return container.ContainerConfig(image=DIGEST, runtime="docker", cpuset_cpus=[192, 193], cpuset_mems="1", memory_mib=1024, ro_paths=["/opt/ws"], rw_dir=tmp,
                                     socket_path="/run/buffon/mock.sock", mock_port=34567, relay_dir="/opt/relay")


class Argv(unittest.TestCase):
    def test_the_arm_runs_behind_the_relay_inside_the_envelope_at_the_same_paths(self):
        tmp = tempfile.mkdtemp()
        run = Recorder()
        meter = container.ContainerMeter(config(tmp), run=run, sleep=lambda s: None, clock=fast_clock())
        meter.popen(["/opt/ws/arms/x/bin/arm", "--version"], env={"HOME": f"{tmp}/home", "LANG": "C"}, cwd=f"{tmp}/project", stdout=subprocess.PIPE)
        argv = run.calls[0]
        self.assertEqual(lint(argv), [])
        at = argv.index(DIGEST)
        self.assertEqual(argv[at + 1:at + 5], ["/buffon/bin/relay", "-listen", "127.0.0.1:34567", "-unix"])
        self.assertEqual(argv[argv.index("--") + 1:], ["/opt/ws/arms/x/bin/arm", "--version"])
        self.assertIn(f"type=bind,source=/opt/ws,target=/opt/ws,readonly", argv)
        self.assertIn(f"type=bind,source={tmp},target={tmp}", argv)
        self.assertEqual(argv[argv.index("--workdir") + 1], f"{tmp}/project")
        self.assertIn(f"HOME={tmp}/home", argv)
        self.assertNotIn("--tty", argv)

    def test_home_is_a_tmpfs_at_its_own_path_seeded_from_a_read_only_mount(self):
        tmp = tempfile.mkdtemp()
        run = Recorder()
        container.ContainerMeter(config(tmp), run=run, sleep=lambda s: None, clock=fast_clock()).popen(["arm"], env={"HOME": f"{tmp}/home"})
        argv = run.calls[0]
        self.assertTrue(any(a.startswith(f"{tmp}/home:rw,exec") for a in argv))
        self.assertIn(f"type=bind,source={tmp}/home,target=/buffon/seed,readonly", argv)
        self.assertEqual(argv[argv.index("-seed"):argv.index("--")], ["-seed", "/buffon/seed", "-home", f"{tmp}/home"])

    def test_the_arm_runs_as_the_invoking_user_and_owns_its_tmpfs_home(self):
        """R27: uid 65534 could not traverse the 0700 workspace, write the root-owned tmpfs HOME or the host-owned work dir; the arm now runs as the caller's uid:gid (still non-root, G8)."""
        tmp = tempfile.mkdtemp()
        run = Recorder()
        container.ContainerMeter(config(tmp), run=run, sleep=lambda s: None, clock=fast_clock()).popen(["arm"], env={"HOME": f"{tmp}/home"})
        argv = run.calls[0]
        want = f"{os.getuid()}:{os.getgid()}" if os.getuid() else "65534:65534"
        self.assertEqual(argv[argv.index("--user") + 1], want)
        uid, gid = want.split(":")
        self.assertTrue(all(f",uid={uid},gid={gid}" in a for a in argv if a.startswith("/") and ":rw,exec" in a), argv)
        self.assertEqual(lint(argv), [])

    def test_container_user_is_never_root(self):
        from unittest import mock
        with mock.patch("os.getuid", return_value=0):
            self.assertEqual(container.container_user(), "65534:65534")
        with mock.patch("os.getuid", return_value=4321), mock.patch("os.getgid", return_value=99):
            self.assertEqual(container.container_user(), "4321:99")

    def test_a_pty_gets_a_tty_and_a_pipe_gets_stdin_open(self):
        tmp = tempfile.mkdtemp()
        master, slave = os.openpty()
        try:
            run = Recorder()
            container.ContainerMeter(config(tmp), run=run, sleep=lambda s: None, clock=fast_clock()).popen(["a"], env={}, stdin=slave, stdout=slave, stderr=slave)
            self.assertIn("--tty", run.calls[0])
            self.assertIn("--interactive", run.calls[0])
            run = Recorder()
            container.ContainerMeter(config(tmp), run=run, sleep=lambda s: None, clock=fast_clock()).popen(["a"], env={}, stdin=subprocess.PIPE)
            self.assertIn("--interactive", run.calls[0])
            self.assertNotIn("--tty", run.calls[0])
        finally:
            os.close(master)
            os.close(slave)

    def test_the_cgroup_is_found_from_the_container_id_file(self):
        tmp = tempfile.mkdtemp()
        scope = tempfile.mkdtemp()
        saved = os.path.isdir
        meter = container.ContainerMeter(config(tmp), run=Recorder("d" * 64), sleep=lambda s: None, clock=fast_clock())
        container.os.path.isdir = lambda p: True if p.endswith("docker-" + "d" * 64 + ".scope") else saved(p)
        try:
            meter.popen(["a"], env={})
        finally:
            container.os.path.isdir = saved
        self.assertEqual(meter.cid, "d" * 64)
        self.assertTrue(meter.path.endswith("docker-" + "d" * 64 + ".scope"))
        meter._sampling = False


class FinalCounters(unittest.TestCase):
    def meter(self, doc):
        tmp = tempfile.mkdtemp()
        meter = container.ContainerMeter(config(tmp), run=Recorder(), sleep=lambda s: None, clock=fast_clock())
        meter.path = ""
        with open(meter._stats, "w") as f:
            json.dump(doc, f)
        return meter

    def test_the_relays_own_cpu_is_subtracted_from_the_container_total(self):
        m = self.meter({"user_ms": 20.0, "system_ms": 10.0, "cgroup": {"cpu.stat": {"usage_usec": 530000, "nr_throttled": 0}, "memory.peak": 52428800, "pids.peak": 9}})
        self.assertAlmostEqual(m.cpu_ms(), 500.0)
        self.assertEqual((m.peak_mem_mib(), m.pids_peak()), (50.0, 9))
        self.assertFalse(m.throttled())

    def test_the_containers_cpu_before_the_arm_started_is_not_the_arms(self):
        """Review: runtime setup, init, the relay's start and HOME seeding added ~80 ms to every sample's cpu_ms (pig-0.4.1 --version 104 ms contained vs 23-35 ms uncontained)."""
        m = self.meter({"user_ms": 20.0, "system_ms": 10.0, "start_cgroup_usage_usec": 80000, "start_relay_cpu_ms": 12.0,
                        "cgroup": {"cpu.stat": {"usage_usec": 530000, "nr_throttled": 0}}})
        self.assertAlmostEqual(m.cpu_ms(), 530.0 - 80.0 - (30.0 - 12.0))

    def test_a_throttled_container_is_flagged_so_the_sample_can_be_invalidated(self):
        m = self.meter({"user_ms": 1, "system_ms": 1, "cgroup": {"cpu.stat": {"usage_usec": 10000, "nr_throttled": 3}}})
        self.assertTrue(m.throttled())

    def test_without_a_final_reading_nothing_is_invented(self):
        tmp = tempfile.mkdtemp()
        m = container.ContainerMeter(config(tmp), run=Recorder(), sleep=lambda s: None, clock=fast_clock())
        self.assertEqual(m.cpu_ms(), 0.0)
        self.assertIsNone(m.peak_mem_mib())

    def test_close_kills_and_removes_the_container(self):
        tmp = tempfile.mkdtemp()
        run = Recorder("e" * 64)
        m = container.ContainerMeter(config(tmp), run=run, sleep=lambda s: None, clock=fast_clock())
        m.popen(["a"], env={})
        m.close()
        verbs = [c[1] for c in run.calls if c[0] == "docker" and c[1] in ("kill", "rm")]
        self.assertEqual(verbs, ["kill", "rm"])

    def test_new_meter_returns_a_container_meter_only_when_a_config_is_set(self):
        self.assertNotIsInstance(cgroup.new_meter(force="rusage"), container.ContainerMeter)
        tmp = tempfile.mkdtemp()
        cgroup.CONTAINER = config(tmp)
        try:
            self.assertIsInstance(cgroup.new_meter(), container.ContainerMeter)
        finally:
            cgroup.CONTAINER = None


class NullRunIsSubtracted(unittest.TestCase):
    """R29: a container's wall time includes `docker run`; the figure measured the way an arm runs is taken off every measured interval."""

    def test_the_null_run_is_measured_through_the_same_meter_and_is_the_median(self):
        tmp = tempfile.mkdtemp()
        run = Recorder()
        now = {"t": 0.0}

        def clock():
            now["t"] += 0.35
            return now["t"]
        value = container.measure_null_run(config(tmp), runs=3, run=run, clock=clock)
        starts = [c for c in run.calls if c[1] == "run"]   # the others remove the container
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(c[c.index("--") + 1:] == ["/bin/true"] for c in starts))
        self.assertTrue(all("--read-only" in c and "--network" in c for c in starts))
        self.assertGreater(value, 0)

    def test_intervals_run_from_the_relays_stamp_of_the_arms_start_and_end_not_from_the_container_creation(self):
        """Finding 34: one configure-time null-run median made wall times negative (container start varies per sample by more than the arm's own time): the relay's CLOCK_MONOTONIC stamps are the interval's ends."""
        import types
        from buffon.runner import procio
        tmp = tempfile.mkdtemp()
        meter = container.ContainerMeter(config(tmp), run=Recorder(), sleep=lambda s: None, clock=fast_clock())
        self.assertIsNone(meter.start_ns())
        self.assertIsNone(meter.end_ns())
        with open(meter._stats + ".start", "w") as f:
            f.write("5000000000")
        self.assertEqual(meter.start_ns(), 5_000_000_000)
        with open(meter._stats, "w") as f:
            json.dump({"child_end_ns": 5_250_000_000}, f)
        self.assertEqual(meter.end_ns(), 5_250_000_000)
        fake = types.SimpleNamespace(start_ns=meter.start_ns, end_ns=meter.end_ns, cpu_ms=lambda: 1.0, peak_mem_mib=lambda: 2.0, max_proc_rss_mib=lambda: 3.0, mode="container")
        batch = procio.Batch(["x"], {}, tmp, fake, timeout=1)
        batch.proc, batch.t_spawn, batch.t_exit = types.SimpleNamespace(returncode=0), 1, 1 + 900_000_000   # the host saw 900 ms: 650 ms of it was creating the container
        result = batch.collect()
        self.assertEqual((result["t_spawn"], result["t_exit"], result["wall_ms"]), (5_000_000_000, 5_250_000_000, 250.0))
        rpc = procio.Rpc.__new__(procio.Rpc)
        rpc.meter, rpc._t_spawn = fake, 7
        self.assertEqual(rpc.t_spawn, 5_000_000_000)

    def test_without_a_stamp_the_host_instants_are_used_and_an_uncontained_meter_has_none(self):
        import types
        from buffon.runner import procio
        rpc = procio.Rpc.__new__(procio.Rpc)
        rpc.meter, rpc._t_spawn = cgroup.RusageMeter(), 7
        self.assertEqual(rpc.t_spawn, 7)
        rpc.meter = types.SimpleNamespace(start_ns=lambda: None)
        self.assertEqual(rpc.t_spawn, 7)
        self.assertIsNone(procio.exit_instant(types.SimpleNamespace()))


@unittest.skipUnless(os.environ.get("BUFFON_E2E_CONTAINER"), "a real container run through the meter: set BUFFON_E2E_CONTAINER=<cpus>:<mem node> and run it inside the host's bench slot")
class RealMeter(unittest.TestCase):
    """One print-style sample through ContainerMeter as the engine runs it (R27): the arm, as the invoking user behind the relay, writes its HOME, its project directory and the output mount, and the failure text carries the relay's words."""

    def setUp(self):
        import types
        from buffon.mock import MockServer
        from buffon.site import parse_cpus
        cpus, _, mems = os.environ["BUFFON_E2E_CONTAINER"].partition(":")
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "work", "home"))
        os.makedirs(os.path.join(self.root, "work", "project"))
        self.ws = types.SimpleNamespace(root=self.root, work=os.path.join(self.root, "work"), base_env=lambda tools: dict(os.environ))
        self.server = MockServer(unix_path=os.path.join(self.root, "mock.sock"))
        self.server.__enter__()   # MockServer starts as a context manager; it has no start()
        self.addCleanup(self.server.__exit__, None, None, None)
        relay_dir, _ = container.build_relay(self.ws, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.cfg = container.ContainerConfig(image=os.environ.get("BUFFON_E2E_IMAGE") or container._image_for(), runtime="docker",
                                             cpuset_cpus=parse_cpus(cpus), cpuset_mems=mems or "0", memory_mib=512, ro_paths=[self.root], rw_dir=self.ws.work,
                                             socket_path=os.path.join(self.root, "mock.sock"), mock_port=self.server.port, relay_dir=relay_dir)

    def run_arm(self, script):
        meter = container.ContainerMeter(self.cfg)
        try:
            proc = meter.popen(["/bin/sh", "-c", script], env={"HOME": os.path.join(self.ws.work, "home"), "PATH": "/usr/bin:/bin"}, cwd=os.path.join(self.ws.work, "project"),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate(timeout=120)
            return proc.returncode, out.decode(), err.decode()
        finally:
            meter.close()

    def test_the_arm_writes_its_home_project_and_the_output_mount_and_its_exit_is_reported(self):
        code, out, err = self.run_arm('echo h > "$HOME/h.txt" && echo p > ./p.txt && echo ok; exit 3')
        self.assertEqual((code, out.strip()), (3, "ok"), err)


class Telemetry(unittest.TestCase):
    """A container sample's cgroup totals reach the telemetry observer: the meter notifies its close listeners with the relay's final reading (T10)."""

    def meter(self, doc):
        tmp = tempfile.mkdtemp()
        meter = container.ContainerMeter(config(tmp), run=Recorder(), sleep=lambda s: None, clock=fast_clock())
        meter.path = ""
        with open(meter._stats, "w") as f:
            json.dump(doc, f)
        return meter

    DOC = {"user_ms": 20.0, "system_ms": 10.0, "start_cgroup_usage_usec": 80000, "start_relay_cpu_ms": 12.0,
           "cgroup": {"cpu.stat": {"usage_usec": 630000, "nr_throttled": 2, "throttled_usec": 4000, "nr_periods": 40}, "memory.peak": 52428800, "memory.current": 1048576, "pids.peak": 9}}

    def test_close_notifies_the_listeners_and_the_collector_records_a_container_final(self):
        from buffon.telemetry import collector, probes
        m = self.meter(self.DOC)
        finals = []
        listener = collector.MeterListener(probes.Sources(), finals)
        saved = list(cgroup.CLOSE_LISTENERS)
        cgroup.CLOSE_LISTENERS[:] = [listener]
        try:
            m.close()
        finally:
            cgroup.CLOSE_LISTENERS[:] = saved
        self.assertEqual(len(finals), 1)
        f = finals[0]
        self.assertEqual((f["mode"], f["throttled_periods"], f["throttled_us"], f["periods"]), ("container", 2, 4000, 40))
        self.assertEqual((f["memory_peak_mib"], f["memory_current_mib"], f["pids_peak"]), (50.0, 1.0, 9))
        self.assertAlmostEqual(f["cpu_usage_ms"], m.cpu_ms(), places=3)      # the same arm CPU the sample reports: start-of-arm usage and the relay's own CPU are out
        self.assertAlmostEqual(f["cpu_usage_ms"], (630000 - 80000) / 1000 - (30.0 - 12.0), places=3)

    def test_a_container_without_a_relay_reading_leaves_a_gap_not_a_failure(self):
        from buffon.telemetry import probes
        self.assertEqual(probes.container_final({}), {"mode": "container"})
        self.assertEqual(probes.container_final(None), {"mode": "container"})
