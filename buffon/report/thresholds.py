# SPDX-License-Identifier: Apache-2.0
"""The flag rules of the noise report and the usual range of every run-health check, read from workloads/health.toml (docs/HEALTH.md is generated from it; a test fails when they differ).

The usual range is published before the run it describes: a change of the file is a change of method, and every health.json carries the file's sha256."""
import hashlib
import os
import tomllib

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "workloads", "health.toml")

with open(PATH, "rb") as _f:
    _raw = _f.read()
SHA256 = hashlib.sha256(_raw).hexdigest()
_doc = tomllib.loads(_raw.decode())

_flags, _outliers, _cp, _aa = _doc["flags"], _doc["outliers"], _doc["changepoint"], _doc["aa"]

THROTTLE_PERIODS = _flags["throttled_periods"]
FOREIGN_FRAC = _flags["foreign_frac"]
FOREIGN_TICKS = _flags["foreign_ticks"]
STEAL_FRAC = _flags["steal_frac"]
CLOCK_MOVE = _flags["clock_move"]
SWAP_PAGES = _flags["swap_pages"]
THERMAL_EVENTS = _flags["thermal_events"]
MAD_K = _outliers["mad_k"]
OUTLIER_MIN_N = _outliers["min_n"]
CP_ALPHA, CP_MIN_SEGMENT, CP_PERMUTATIONS = _cp["alpha"], _cp["min_segment"], _cp["permutations"]
AA_MIN_GAP = _aa["min_gap"]

FLAGS = {
    "throttled": f"CFS throttled the sample's cgroup, an ancestor or the session ({THROTTLE_PERIODS} period or more)",
    "foreign_busy": f"the pinned CPUs were busy beyond the sample's own CPU time by more than {FOREIGN_FRAC:.0%} of their capacity (and {FOREIGN_TICKS:g} clock ticks per sqrt(CPU))",
    "steal": f"a hypervisor took more than {STEAL_FRAC:.1%} of the pinned CPUs' capacity",
    "clock_moved": f"the pinned CPUs' clock moved by more than {CLOCK_MOVE:.0%} during the sample",
    "gate_waited": "the quiet-host gate needed more than one reading before the sample started",
    "swap": f"the host swapped {SWAP_PAGES} page or more during the sample",
    "thermal": f"the pinned CPUs were thermally throttled {THERMAL_EVENTS} time or more during the sample",
    "memory_events": "the kernel reported a memory.high, memory.max or OOM event for the sample's cgroup",
}

OUTLIER_RULE = (f"a measured value is an outlier when |x - median| > {MAD_K:g} x 1.4826 x MAD of its arm's values in that cell (needs {OUTLIER_MIN_N} values; with MAD 0, any different value). "
                "Outliers are counted, never removed.")

# (id, title, unit, usual: a value above it is a note, meaning)
HEALTH = [(c["id"], c["title"], c["unit"], c["usual"], c["meaning"]) for c in _doc["check"]]
CHECKS = [(c["id"], c["title"], c["meaning"]) for c in _doc["pass"]]
