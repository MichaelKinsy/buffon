"""The envelope's guarantees (buffon/envelope, docs/ENVELOPE.md): one red test per guarantee, on the argv builder and on the lint that holds any tool's own argv to them."""
import os
import unittest

from buffon.envelope import GUARANTEES, EnvelopeError, Mount, Spec, build_argv, isolation_stamp, lint

DIGEST = "debian@sha256:" + "a" * 64


def spec(**kw):
    base = dict(image=DIGEST, cpuset_cpus=[192, 193, 194], cpuset_mems="1", memory_mib=2048, env={"LANG": "C"}, mounts=[Mount("/opt/arm", "/opt/arm")],
                output=Mount("/out", "/out", False), sockets=[("/run/mock.sock", "/run/buffon/mock.sock")])
    base.update(kw)
    return Spec(**base)


def argv(**kw):
    return build_argv(spec(**kw), ["/opt/arm/bin/x", "--version"])


def drop(a, flag, n=1):
    """argv without `flag` and its `n` values (n=0: a bare flag); every occurrence."""
    out, i = [], 0
    while i < len(a):
        if a[i] == flag:
            i += 1 + n
        else:
            out.append(a[i])
            i += 1
    return out


def replace(a, flag, value):
    out = list(a)
    out[out.index(flag) + 1] = value
    return out


def codes(problems):
    return {p.split(":")[0] for p in problems}


class Builder(unittest.TestCase):
    def test_the_built_argv_keeps_every_guarantee(self):
        a = argv()
        self.assertEqual(lint(a), [])
        self.assertEqual(a[:2], ["docker", "run"])
        self.assertEqual(a[a.index(DIGEST):], [DIGEST, "/opt/arm/bin/x", "--version"])
        self.assertIn("192-194", a)
        self.assertEqual(a[a.index("--cpus") + 1], "3")

    def test_every_guarantee_is_named_and_tested_below(self):
        self.assertEqual(set(GUARANTEES), {f"G{i}" for i in range(1, 12)})

    def test_detached_and_podman_variants_stay_inside_the_envelope(self):
        self.assertEqual(lint(build_argv(spec(), ["x"], runtime="podman", detach=True)), [])

    def test_the_cpuset_is_written_as_ranges(self):
        a = argv(cpuset_cpus=[5, 6, 7, 9, 12, 13])
        self.assertEqual(a[a.index("--cpuset-cpus") + 1], "5-7,9,12-13")
        self.assertEqual(a[a.index("--cpus") + 1], "6")


class Guarantees(unittest.TestCase):
    def test_G1_a_tag_or_a_missing_digest_is_refused(self):
        for image in ("debian:bookworm", "debian", "debian@sha256:abc", ""):
            with self.assertRaisesRegex(EnvelopeError, "G1"):
                argv(image=image)
        a = argv()
        a[a.index(DIGEST)] = "debian:bookworm"
        self.assertEqual(codes(lint(a)), {"G1"})

    def test_G2_any_network_but_none_is_refused(self):
        for value in ("host", "bridge"):
            self.assertEqual(codes(lint(replace(argv(), "--network", value))), {"G2"})
        self.assertEqual(codes(lint(drop(argv(), "--network"))), {"G2"})
        self.assertEqual(codes(lint(drop(argv(), "--network") [:2] + ["--net=host"] + drop(argv(), "--network")[2:])), {"G2"})

    def test_G3_cpuset_mems_and_cpus_equal_to_the_cpuset_size(self):
        self.assertEqual(codes(lint(drop(argv(), "--cpuset-mems"))), {"G3"})
        self.assertEqual(codes(lint(drop(argv(), "--cpuset-cpus"))), {"G3"})
        self.assertIn("cpuset has 3 CPUs", lint(replace(argv(), "--cpus", "8"))[0])
        self.assertEqual(codes(lint(drop(argv(), "--cpus"))), {"G3"})
        with self.assertRaisesRegex(EnvelopeError, "G3"):
            argv(cpuset_cpus=[])
        with self.assertRaisesRegex(EnvelopeError, "G3"):
            argv(cpuset_mems="")

    def test_G4_memory_equals_swap_and_pids_are_limited(self):
        self.assertEqual(codes(lint(replace(argv(), "--memory-swap", "4096m"))), {"G4"})
        self.assertEqual(codes(lint(drop(argv(), "--memory-swap"))), {"G4"})
        self.assertEqual(codes(lint(drop(argv(), "--pids-limit"))), {"G4"})
        with self.assertRaisesRegex(EnvelopeError, "G4"):
            argv(pids=4)

    def test_tmpfs_is_owned_by_the_numeric_user_so_the_arm_can_write_its_home(self):
        a = argv(user="1000:1001")
        self.assertTrue(all(",uid=1000,gid=1001" in v for v in a if ":rw,exec" in v))
        self.assertTrue(any(":rw,exec" in v for v in a))
        self.assertTrue(all(",uid=65534,gid=65534" in v for v in argv() if ":rw,exec" in v))

    def test_G5_read_only_root_and_tmpfs_home_and_tmp(self):
        self.assertEqual(codes(lint(drop(argv(), "--read-only", 0))), {"G5"})
        self.assertEqual(codes(lint(drop(argv(), "--tmpfs"))), {"G5"})
        a = argv()
        a = drop(a, "--tmpfs")
        self.assertEqual(codes(lint(a)), {"G5"})

    def test_G6_an_init_process(self):
        self.assertEqual(codes(lint(drop(argv(), "--init", 0))), {"G6"})

    def test_G7_explicit_ulimits(self):
        a = argv()
        self.assertEqual(codes(lint(drop(a, "--ulimit"))), {"G7"})
        only_core, i = [], 0
        while i < len(a):
            if a[i] == "--ulimit" and not a[i + 1].startswith("core"):
                i += 2
                continue
            only_core.append(a[i])
            i += 1
        self.assertEqual(codes(lint(only_core)), {"G7"})
        with self.assertRaisesRegex(EnvelopeError, "G7"):
            argv(ulimits={"core": "0:0"})

    def test_G8_non_root_no_capabilities_no_new_privileges(self):
        self.assertEqual(codes(lint(replace(argv(), "--user", "0:0"))), {"G8"})
        self.assertEqual(codes(lint(replace(argv(), "--user", "root"))), {"G8"})
        self.assertEqual(codes(lint(drop(argv(), "--user"))), {"G8"})
        self.assertEqual(codes(lint(drop(argv(), "--cap-drop"))), {"G8"})
        self.assertEqual(codes(lint(drop(argv(), "--security-opt"))), {"G8"})
        with self.assertRaisesRegex(EnvelopeError, "G8"):
            argv(user="0:0")

    def test_G9_no_env_file(self):
        a = argv()
        a[a.index(DIGEST):a.index(DIGEST)] = ["--env-file", "/etc/env"]
        self.assertEqual(codes(lint(a)), {"G9"})
        self.assertIn("--env", argv())
        self.assertEqual(argv(env={})[argv(env={}).index(DIGEST) - 1].startswith("--env"), False)

    def test_G9_an_env_name_without_a_value_would_pass_the_hosts_variable_through(self):
        a = argv()
        at = a.index(DIGEST)
        self.assertEqual(codes(lint(a[:at] + ["--env", "AWS_SECRET"] + a[at:])), {"G9"})
        self.assertEqual(codes(lint(a[:at] + ["-e", "TOKEN"] + a[at:])), {"G9"})
        self.assertEqual(lint(a[:at] + ["--env", "NAME=value"] + a[at:]), [])

    def test_G11_a_second_socket_mount_is_not_a_free_writable_mount(self):
        a = argv()
        at = a.index(DIGEST)
        extra = ["--mount", "type=bind,source=/run/other.sock,target=/other.sock"]
        self.assertEqual(codes(lint(a[:at] + extra + a[at:])), {"G11"})

    def test_G10_nothing_privileged(self):
        for extra in (["--privileged"], ["--cap-add", "SYS_ADMIN"], ["--device", "/dev/kvm"], ["--sysctl", "vm.drop_caches=3"], ["--pid", "host"], ["--ipc=host"],
                      ["--security-opt", "seccomp=unconfined"], ["--userns=host"], ["--volumes-from", "other"], ["--gpus", "all"], ["--runtime", "runc"]):
            a = argv()
            at = a.index(DIGEST)
            self.assertEqual(codes(lint(a[:at] + extra + a[at:])), {"G10"}, extra)
        for src in ("/proc", "/sys/fs/cgroup", "/dev/shm", "/var/run/docker.sock"):
            with self.assertRaisesRegex(EnvelopeError, "G10"):
                argv(mounts=[Mount(src, "/x")])

    def test_G11_only_the_output_directory_is_writable(self):
        with self.assertRaisesRegex(EnvelopeError, "G11"):
            argv(mounts=[Mount("/opt/arm", "/opt/arm", ro=False)])
        a = argv()
        at = a.index(DIGEST)
        extra = ["--mount", "type=bind,source=/elsewhere,target=/elsewhere"]
        self.assertEqual(codes(lint(a[:at] + extra + a[at:])), {"G11"})
        a2 = a[:at] + ["-v", "/data:/data:ro"] + a[at:]
        self.assertEqual(lint(a2), [])


class Isolation(unittest.TestCase):
    def test_container_is_comparable_and_none_is_stamped_uncontained(self):
        self.assertEqual(isolation_stamp("container"), {"isolation": "container", "comparable": True})
        none = isolation_stamp("none")
        self.assertFalse(none["comparable"])
        self.assertEqual(none["stamp"], "uncontained, not comparable")
        with self.assertRaises(EnvelopeError):
            isolation_stamp("chroot")

    def test_a_command_that_is_not_a_run_is_not_an_envelope(self):
        self.assertEqual(lint(["docker", "ps"]), ["not a `run` command"])


@unittest.skipUnless(os.environ.get("BUFFON_E2E_CONTAINER"), "a real container run: set BUFFON_E2E_CONTAINER=<cpus>:<mem node> (for example 20-21:0) and run it inside the host's bench slot")
class RealContainer(unittest.TestCase):
    """The guarantees as the kernel enforces them, not as the argv states them."""

    def run_in(self, script):
        import tempfile
        from buffon.envelope import Envelope
        from buffon.site import parse_cpus
        cpus, _, mems = os.environ["BUFFON_E2E_CONTAINER"].partition(":")
        out = tempfile.mkdtemp()
        os.chmod(out, 0o777)
        s = spec(cpuset_cpus=parse_cpus(cpus), cpuset_mems=mems or "0", memory_mib=512, image=os.environ.get("BUFFON_E2E_IMAGE", "debian@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587"),
                 env={"HOME": "/buffon/home", "TMPDIR": "/tmp"}, mounts=[], sockets=[], output=Mount(out, "/out", False))
        return Envelope().run(s, ["/bin/sh", "-c", script]), out

    def test_the_process_is_not_root_cannot_write_the_root_fs_and_has_no_network(self):
        res, out = self.run_in("id -u; touch /x 2>&1; echo $(ls /sys/class/net); ulimit -n; cat /sys/fs/cgroup/cpu.max")
        self.assertEqual(res.exit, 0)
        lines = res.stdout.splitlines()
        self.assertEqual(lines[0], "65534")
        self.assertIn("Read-only file system", lines[1])
        self.assertEqual(lines[2].strip(), "lo")
        self.assertEqual(lines[3], "4096")
        self.assertRegex(lines[4], r"^\d+ 100000$")
        self.assertFalse(res.throttled())
        self.assertGreater(res.cgroup["memory.peak"], 0)

    def test_memory_beyond_the_limit_is_an_oom_kill_not_swap(self):
        res, _ = self.run_in("tail /dev/zero")
        self.assertTrue(res.oom_killed)


class Parsing(unittest.TestCase):
    def test_flags_with_values_the_runner_adds_do_not_hide_the_image(self):
        a = build_argv(spec(cidfile="/tmp/cid", interactive=True, tty=True, name="buffon-x"), ["x"])
        self.assertEqual(lint(a), [])
        self.assertIn("--cidfile", a)
        self.assertIn("--tty", a)
        at = a.index(DIGEST)
        self.assertEqual(lint(a[:at] + ["--pull", "always"] + a[at:]), [])
