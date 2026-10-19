# The container envelope

One library, `buffon/envelope`, is the only place that knows how to run a benchmarked process in a container. The runner (`buffon/runner/container.py`, `swarm.py`, `engine.py`) imports it; none keeps a copy. A local run is bare by default (`--isolation none` stamps the result "uncontained, not comparable", `isolation_stamp`). `--isolation container` puts every arm in the envelope; the scale family and the Pi-family and real-world tracks of `buffon up` choose it where the machine has docker or podman and pinned CPUs. On a Kubernetes site the pod is the envelope (below).

| # | Guarantee | Enforced by |
|---|---|---|
| G1 | the image is pinned by digest (`name@sha256:…`), never by a tag; `images/images.toml` names each arm's image, `images/base/Dockerfile` records the base | `Spec.validate`, `lint` |
| G2 | no network (`--network none`); the mock is a unix socket bind-mounted into the container | `lint` |
| G3 | `--cpuset-cpus` and `--cpuset-mems` set, `--cpus` equal to the cpuset size (so `nr_throttled > 0` is never the envelope's own doing; if it happens the sample is invalid) | `lint` |
| G4 | `--memory` equal to `--memory-swap` (an OOM kill, never swap), `--pids-limit` set | `lint` |
| G5 | `--read-only` root filesystem, tmpfs HOME and `/tmp` (mode `exec`). HOME holds config and state only: an arm's runtime code and caches (`PIG_HOME`, `TMPDIR`, `XDG_CACHE_HOME`, a seed's unpacked natives) are on the `disk/` directory of its harness under the writable work mount, because code mapped from tmpfs counts as the process's own memory (docs/METHODOLOGY.md, section 4) | `lint` |
| G6 | `--init` | `lint` |
| G7 | explicit ulimits (nofile, nproc, core) | `Spec.validate`, `lint` |
| G8 | non-root user (the invoking user's uid:gid, so the arm can traverse the workspace and write its tmpfs HOME and the one writable mount; 65534:65534 when the runner is root; the tmpfs mounts get that uid and gid), `--cap-drop ALL`, `no-new-privileges` | `Spec.validate`, `lint` |
| G9 | the environment is the `Spec.env` allow-list, passed with `--env`; no env file | `lint` |
| G10 | nothing privileged: no `--privileged`, `--cap-add`, `--device`, `--sysctl` (so no `drop_caches`), host pid/ipc/uts, unconfined seccomp or apparmor, no bind of `/proc`, `/sys`, `/dev` or a container socket. The report states that the shared host is never touched | `Spec.validate`, `lint` |
| G11 | bind mounts are read-only except the one declared output directory | `Spec.validate`, `lint` |

`lint(argv)` holds ANY `docker|podman run` command line to the same guarantees, so a tool that builds its own argv can be checked, and `Envelope.run` lints what it is about to run. `tests/test_envelope.py` has one red test per guarantee (each removes or breaks the guarantee in an argv and expects the lint, or the builder, to name it) and a real-container test (`BUFFON_E2E_CONTAINER=<cpus>:<node>`, run inside the bench slot) that checks what the kernel enforces: uid, read-only root, no interface but `lo`, ulimit, cgroup quota, OOM kill.

## The pod envelope (Kubernetes)

An unprivileged pod cannot run `docker`, so on Kubernetes the envelope is the session's own pod: isolation `pod-guaranteed`, the default for a Kubernetes site (`buffon/envelope/pod.py`). It is comparable when the pod holds, for the whole session:

| # | Guarantee | Checked by |
|---|---|---|
| P1 | Guaranteed QoS with exclusive cores: the container's cpuset has exactly the requested CPUs, fewer than the node has online (the static CPU manager gives exclusive CPUs only to a Guaranteed container with an integer CPU request), `cpu.max` is a limit of those CPUs or unlimited (the kubelet's DisableCPUQuotaWithExclusiveCPUs), `memory.max` is a limit | the session at the start and in every sample; the runner's `node.json` (`podQosClass` from the API server must be `Guaranteed`; `cpuManagerPolicy` must be `static` where the account may read it) |
| P2 | the image is pinned by digest (with a bundle: the base image, and the bundle matches its `ARTIFACTS.sha256`) | the session (`BUFFON_IMAGE_REF`); `node.json` `podImageID` must carry a digest |
| P3 | read-only root filesystem | the session (`/proc/self/mountinfo`); the Job sets `readOnlyRootFilesystem` |
| P4 | a non-root user, no capabilities, no privilege escalation | the session (uid); the Job's security context |
| P5 | no network but the mock, which listens on loopback in the pod | the Job comes with a NetworkPolicy of its name that allows no traffic in or out; the session checks that a connection to the cluster's API service does not get through, so a cluster that does not enforce NetworkPolicies fails P5 |

P1 reads the container's cgroup v2 files (`cpuset.cpus.effective`, `cpu.max`, `memory.max` at the root of its cgroup namespace); on a node with cgroup v1 they are absent, so P1 fails and the run is uncontained. Every sample records the node, the cpuset and the QoS it ran with (raw.json `samples[].pod`). When a guarantee fails at the start, or a sample ran on another node or cpuset or without Guaranteed QoS, the run is stamped "uncontained, not comparable" with the reasons. `buffon verify` rejects a pod-guaranteed run whose samples or `node.json` contradict its stamp. What differs from the container envelope: one container for the whole session, not one per sample, so a sample's wall time includes no container start.

## The swarm container

The scale family (`scale/agents-limit`, `scale/print-limit`, `scale/agents-ext10`, `scale/print-ext10`) puts N agents of one harness in ONE container, started once per probe of a search (many probes in a sample) (`buffon/runner/swarm.py`, docs/design/SCALE.md). It is built by `build_argv` and keeps G1-G11. What differs: memory = memory-swap is `swarm_memory_gib`; the cpuset is `swarm_cpus` with `--cpus` equal to its size; `--pids-limit` is 64 per agent and 1,024 over, so it is never the first limit; `--ulimit nofile=4096:1048576` (the hard limit above the soft one) because the relay holds a few descriptors per agent; the command is `relay -swarm`, which launches the agents on commands from the runner's `docker run -i` channel; one tmpfs holds every agent's HOME. The one writable mount and the one socket are the same as for a single arm. No agent runs outside the container's cgroup.

## What a run records

`Envelope.run` returns the exit code, stdout, stderr, the wall time from `docker run` to exit (which includes the container start), whether the kernel OOM-killed it, and the cgroup counters read every 20 ms while it lived (`cpu.stat`, `memory.peak`, `memory.current`, `pids.peak`; the last reading before exit, at most one poll stale). `throttled()` is true when `nr_throttled` is above zero. `Envelope.null_run` runs `/bin/true` in the identical envelope and returns the median wall time: the container start is reported as its own number and a command's wall time is reported net of it.

## Checked on a real run (benchmark host, 2026-10-16)

The same five harnesses (pi-node, pi-bun, pig-tip, pibolt, claude-code) and benchmarks (overhead/version, overhead/print, overhead/print-tools; 6 rounds; clock fixed at 2.8 GHz with deep idle states off) ran bare and then in the envelope, back to back on the same cores (runs `up-33df8f3934-measured` and `up-4b178b2ecb-measured`).

- CPU time agrees within 2% in every cell, in both directions (pi-node `overhead/version` 279.8 ms bare, 278.2 ms contained; pig-tip 5.2 ms and 5.3 ms).
- Wall time is the same or up to 5% longer contained (pi-node `overhead/print` 310 ms and 325 ms): the relay sits between the harness and the mock.
- Peak memory is about 3 MiB higher contained for every harness (pig-tip 7.2 MiB and 10.5 MiB; pi-node 64.6 MiB and 66.5 MiB): the container's cgroup also holds the init process, the relay and the tmpfs HOME. Compare memory between runs of the same isolation only.
- Instruction and cycle counts are not taken in the envelope (no counter is attached to a process the container runtime starts).
- A run without a fixed clock is not a check: the first contained smoke, on the default governor, read pi-node `overhead/version` at 453 ms of CPU against 279 ms bare, all of it the clock.

## Not in the envelope

The envelope never uses `--privileged`, `sysctl` or `drop_caches` on the shared host. A cold start in a container is a cold start of the container, not of the page cache (METHODOLOGY section 11, rule 10). The host class (A or B) is a property of the machine and its preflight, not of the envelope.
