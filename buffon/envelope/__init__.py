# SPDX-License-Identifier: Apache-2.0
"""The one container envelope every benchmark tool shares (bench/compare, evals, sessionscale, the durable report, buffon).

An arm runs inside the same envelope as every other arm: a digest-pinned image, no network (the mock is a mounted unix socket), a cpuset on one NUMA node with `--cpus` equal to its size, memory equal
to memory-swap, a pids limit, a read-only root filesystem with tmpfs HOME and TMPDIR, an init process, explicit ulimits, a non-root user, no capabilities, an explicit environment. `build_argv` produces
the `docker run`/`podman run` argument vector from a `Spec`; `lint` checks ANY argv against the same guarantees, so a tool that builds its own command line is held to them too; `run.Envelope` executes it.

`--isolation=none` exists and is stamped "uncontained, not comparable" (`isolation_stamp`): a result without the envelope never ranks with one that has it.
"""
from .spec import GUARANTEES, EnvelopeError, Mount, Spec, build_argv, isolation_stamp, lint  # noqa: F401
from .run import Envelope, Result, find_runtime  # noqa: E402,F401
