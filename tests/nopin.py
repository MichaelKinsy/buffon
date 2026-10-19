# SPDX-License-Identifier: Apache-2.0
"""Run a block as macOS would: the platform has no sched_setaffinity and no sched_getaffinity."""
import contextlib
import os


@contextlib.contextmanager
def without_affinity():
    saved = {n: getattr(os, n) for n in ("sched_setaffinity", "sched_getaffinity") if hasattr(os, n)}
    for n in saved:
        delattr(os, n)
    try:
        yield
    finally:
        for n, f in saved.items():
            setattr(os, n, f)
