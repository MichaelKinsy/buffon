# SPDX-License-Identifier: Apache-2.0
"""Runtime-tuning variables and what a run records about them (docs/METHODOLOGY.md section 15, docs/RAW-FORMAT.md `arms[<id>].runtime_settings`).

Buffon leaves runtime tuning at each harness's shipped default. It pins CPUs (taskset, cpuset), but it never sets GOMAXPROCS, GOGC, GOMEMLIMIT or any other variable
below, for any arm. A variable is set only by an arm's manifest `[env]`, and then the run records it with source "manifest"."""

KNOWN = ("GOMAXPROCS", "GOGC", "GOMEMLIMIT", "GODEBUG", "NODE_OPTIONS", "NODE_COMPILE_CACHE", "UV_THREADPOOL_SIZE", "BUN_GARBAGE_COLLECTOR_LEVEL")
PREFIXES = ("BUN_",)
SOURCES = ("manifest", "buffon")


def is_tuning(name):
    return name in KNOWN or name.startswith(PREFIXES)


def settings(manifest_env):
    """The record of one arm: the tuning variables its manifest sets (as written, placeholders unexpanded, so the record does not hold a host path), the known ones left at the
    harness's own default, and where each set variable came from. Buffon sets none of its own, so every source is "manifest"."""
    env = {k: v for k, v in sorted(manifest_env.items()) if is_tuning(k)}
    return {"env": env, "left_default": [k for k in KNOWN if k not in env], "source": {k: "manifest" for k in env}}
