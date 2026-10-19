# SPDX-License-Identifier: Apache-2.0
"""Declared divergences: work an arm does differently by its own account (`[[divergence]]` in arm.toml, docs/METHODOLOGY.md section 15).

A divergence names workloads (globs of workload ids) and, optionally, metrics (globs of metric names; none means every metric) where the arm does different work
from the reference. The report prints the arm's own median there and does not compare it: no ratio, no interval, no test, and the grade leaves the cell out.
Selection is by these manifest fields only, never by an arm's name."""
from fnmatch import fnmatchcase

KEYS = {"workloads", "metrics", "reason", "source"}


def reason_for(entries, workload, metric):
    """The reason of the first entry that covers (workload, metric), or None. `entries` are the manifest's tables (also what raw.json carries under `arms[<id>].divergences`)."""
    for e in entries or ():
        if any(fnmatchcase(workload, g) for g in e["workloads"]) and (not e.get("metrics") or any(fnmatchcase(metric, g) for g in e["metrics"])):
            return e["reason"]
    return None
