# SPDX-License-Identifier: Apache-2.0
"""`buffon harnesses` and `buffon benches`: every choice with what it needs, whether it is ready, and what it costs on this machine."""
import json
import os

from .. import workloads as workloadlib
from ..arms import manifest
from . import catalog, estimate, selection, tracks as trackslib


def installed_marks(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def mark_installed(path, arms):
    """Record that these arms installed from their current manifest (Buffon home's installed.json): `buffon harnesses` shows them as installed until the manifest changes."""
    marks = installed_marks(path)
    for a in arms:
        marks[a.id] = a.manifest_sha256
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(marks, f, indent=1, sort_keys=True)


def needs_of(arm, platform):
    if arm.held:
        return "held"
    kind, spec = arm.install_kind, arm.spec
    out = []
    if kind == "artifact":
        out.append("a pinned release download")
        if platform not in spec["artifact"]:
            out.append(f"NOT AVAILABLE for {platform}")
    elif kind == "npm":
        out.append(f"npm install on pinned {spec['npm']['runtime']}")
    elif kind == "source":
        s = spec["source"]
        out.append(f"git + pinned {s['toolchain']} toolchain, builds the pinned commit")
    elif kind == "derive":
        out.append(f"built from {arm.base}")
    for name in sorted(spec.get("runtime", {}) if kind != "npm" else []):
        out.append(f"{name} runtime")
    if arm.operator_terms:
        out.append(f"vendor terms you accept: --accept-terms {arm.id}")
    return ", ".join(out)


def available_here(arm, platform):
    if arm.held:
        return False
    return arm.install_kind != "artifact" or platform in arm.spec["artifact"]


def harness_rows(arms=None, marks=None, platform=None):
    arms = arms if arms is not None else manifest.load_all()
    marks = marks or {}
    platform = platform or manifest.host_platform()
    rows = []
    for name, a in arms.items():
        if a.held:
            state = "held"
        elif not available_here(a, platform):
            state = f"not on {platform}"
        else:
            state = "installed" if marks.get(name) == a.manifest_sha256 else "not installed"
        rows.append({"name": name, "label": a.label, "version": a.version, "needs": needs_of(a, platform), "state": state, "default": name in catalog.DEFAULT_HARNESSES,
                     "runs_by_default": bool(a.runs_by_default), "kind": a.relation if hasattr(a, "relation") else a.family, "available": available_here(a, platform)})
    return rows


def bench_rows(probe_result, history=None, harnesses=None, registry=None):
    """One row per workload plus the designed-not-run families: id, state, what it measures, expected time here (all default harnesses, standard settings)."""
    registry = registry if registry is not None else workloadlib.load_all()
    history = history or {}
    sel = selection.from_preset("standard", registry).clone(harnesses=list(harnesses or catalog.DEFAULT_HARNESSES))
    rows = []
    tracks = trackslib.load()
    for wid, w in registry.items():
        state, why = catalog.state_of(wid)
        seconds = estimate.workload_seconds(wid, sel, 2 * len(sel.harnesses), probe_result["speed"], history, registry)
        rows.append({"id": wid, "family": w.family, "state": state, "why": why, "measures": w.description, "seconds": seconds, "apis": [a for a in w.apis if a] if w.apis != (None,) else [],
                     "preset": [p for p, d in catalog.PRESETS.items() if wid in d["workloads"] or w.family in d["workloads"]],
                     "tracks": [t for t in ("common", "pi", "real-world") if wid in trackslib.workloads_of(tracks, t)]})
    for fam, what, why in catalog.NOT_RUN:
        rows.append({"id": fam, "family": fam, "state": "not run", "why": why, "measures": what, "seconds": None, "apis": [], "preset": [], "tracks": [t for t in ("common", "pi", "real-world") if fam in {c for c, _w, _s in trackslib.coming_of(tracks, t)}]})
    return rows


def table(rows, columns):
    """Plain aligned text: `columns` is [(header, key or function)]."""
    cells = [[h for h, _ in columns]] + [[str(f(r) if callable(f) else r.get(f, "")) for _, f in columns] for r in rows]
    widths = [max(len(c[i]) for c in cells) for i in range(len(columns))]
    return "\n".join("  ".join(c[i].ljust(widths[i]) for i in range(len(columns))).rstrip() for c in cells)


def harness_table(rows):
    return table(rows, [("HARNESS", lambda r: r["name"] + (" *" if r["default"] else "")), ("VERSION", "version"), ("STATE", "state"), ("NEEDS", "needs")]) + "\n\n* = in the default set"


def bench_table(rows):
    def when(r):
        return "-" if r["seconds"] is None else selection.format_duration(r["seconds"])
    return table(rows, [("BENCHMARK", "id"), ("STATE", "state"), ("TIME HERE", when), ("PRESETS", lambda r: ",".join(r["preset"])), ("TRACKS", lambda r: ",".join(t.replace("real-world", "real") for t in r["tracks"])), ("MEASURES", lambda r: (r["measures"] or r["why"])[:70])]) + \
        "\n\nTIME HERE = expected for the 3 default harnesses on two wire APIs, stopping early when a cell is clear, on this machine. An estimate: it improves as this machine runs them."
