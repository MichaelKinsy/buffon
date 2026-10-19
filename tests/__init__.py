# SPDX-License-Identifier: Apache-2.0
"""Shared test conditions. Run the suite one way: `python -m unittest discover -s tests -t .` (a test module imported under two names, tests.x and x, registers its hooks twice)."""
import os
import shutil
import unittest

requires_audit = unittest.skipUnless(os.path.isdir("/proc/net"), "the socket audit reads /proc/net (Linux): on this OS the run is refused for publication")
requires_pinning = unittest.skipUnless(hasattr(os, "sched_setaffinity"), "this OS cannot pin processes: the run is labelled PROVISIONAL")
TRUE = shutil.which("true") or "/bin/true"
