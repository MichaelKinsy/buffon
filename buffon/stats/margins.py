# SPDX-License-Identifier: Apache-2.0
"""Equivalence margins: which metrics have one, and how wide it is, read from workloads/margins.toml (docs/METHODOLOGY.md section 7).

A margin is a fraction of the reference median. It is declared in a file before the run it judges; the report names no margin for a metric the file does not list."""
import fnmatch
import hashlib
import os
import tomllib

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "workloads", "margins.toml")


def load(path=PATH):
    """The entries of a margins file, in order: [{"metrics": [glob], "relative": float, "absolute": float or None}]. Raises ValueError on an entry that is not well formed."""
    with open(path, "rb") as f:
        doc = tomllib.loads(f.read().decode())
    out = []
    for i, e in enumerate(doc.get("margin", [])):
        metrics, rel, ab = e.get("metrics"), e.get("relative"), e.get("absolute")
        if not isinstance(metrics, list) or not metrics or not all(isinstance(m, str) for m in metrics):
            raise ValueError(f"{path}: margin {i + 1} needs `metrics`, a list of globs")
        if isinstance(rel, bool) or not isinstance(rel, (int, float)) or rel < 0:
            raise ValueError(f"{path}: margin {i + 1} needs `relative`, a number of at least 0")
        if ab is not None and (isinstance(ab, bool) or not isinstance(ab, (int, float)) or ab < 0):
            raise ValueError(f"{path}: margin {i + 1}: `absolute` is a number of at least 0")
        out.append({"metrics": metrics, "relative": float(rel), "absolute": None if ab is None else float(ab)})
    return out


def sha256(path=PATH):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


_cache = {}


def default():
    """The checkout's own table, read once."""
    if "table" not in _cache:
        _cache["table"] = load()
    return _cache["table"]


def margin_for(metric, ref_median, table=None):
    """The margin (a fraction) for `metric` against a reference median, or None where the table declares none. The first matching entry decides; with an `absolute` floor
    the margin is the larger of `relative` and absolute / |reference median|."""
    for e in default() if table is None else table:
        if any(fnmatch.fnmatchcase(metric, g) for g in e["metrics"]):
            m = e["relative"]
            if e["absolute"] and ref_median:
                m = max(m, e["absolute"] / abs(ref_median))
            return m
    return None
