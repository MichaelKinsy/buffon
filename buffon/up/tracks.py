# SPDX-License-Identifier: Apache-2.0
"""The three tracks (docs/TRACKS.md): Common ground, Pi family, Real-world. Loaded from workloads/tracks.toml (tracks 1 and 2) and workloads/recipes/*.toml (track 3).

A track is a few plain questions. Each question names the benchmarks that answer it (`workloads`, wired and run), the evals it uses, and the benchmarks that are designed but not built
(`coming`: a screen shows a "coming" chip, never a number). A recipe is a fixed combination of existing benchmarks with parameters; it adds no metric of its own and says which it uses."""
import glob
import os
import tomllib

from ..arms import manifest

DIR = os.path.join(manifest.ROOT, "workloads")
TRACKS_FILE = os.path.join(DIR, "tracks.toml")
RECIPES_DIR = os.path.join(DIR, "recipes")
IDS = ("common", "pi", "real-world")
ALL = IDS + ("all",)
RECIPE_KEYS = {"id", "title", "sentence", "machine", "conditions", "uses", "coming", "apis", "isolation", "params", "reports"}
QUESTION_KEYS = {"id", "title", "sentence", "workloads", "evals", "coming", "chart", "steps", "rungs"}
MACHINES = ("laptop", "vps", "small-vps")
CONDITIONS = ("typical", "lab")
CHARTS = ("number", "line", "race")
NOT_BUILT = {"real-extensions": "a pinned set of real Pi extensions"}


class TrackError(ValueError):
    pass


def load(tracks_file=TRACKS_FILE, recipes_dir=RECIPES_DIR):
    """{"common": {...}, "pi": {...}, "real-world": {"title", "about", "recipes": [...]}}: each track with its questions (or recipes), in file order."""
    with open(tracks_file, "rb") as f:
        doc = tomllib.load(f)
    out = {}
    for tid in ("common", "pi"):
        t = dict(doc["track"][tid])
        t["id"] = tid
        t["questions"] = [dict(q) for q in t.pop("question", [])]
        out[tid] = t
    recipes = []
    for path in sorted(glob.glob(os.path.join(recipes_dir, "*.toml"))):
        with open(path, "rb") as f:
            r = tomllib.load(f)
        r["file"] = os.path.relpath(path, manifest.ROOT)
        recipes.append(r)
    order = ["day-of-work", "team-box", "heavy-setup", "cheap-machine"]
    recipes.sort(key=lambda r: order.index(r["id"]) if r["id"] in order else len(order))
    out["real-world"] = {"id": "real-world", "title": "Real-world", "about": "The obvious combinations of tracks 1 and 2, as a user lives them. Each scenario is a fixed recipe of existing benchmarks.", "recipes": recipes, "questions": []}
    return out


def check(tracks, registry, evals):
    """The problems of a track definition, as sentences: an unknown workload, eval, key or enumerated value; a recipe report that names a benchmark the recipe does not use."""
    problems = []
    for tid in ("common", "pi"):
        t = tracks[tid]
        for q in t["questions"]:
            where = f"track {tid} question {q.get('id')}"
            for k in set(q) - QUESTION_KEYS:
                problems.append(f"{where}: unknown key {k}")
            for w in q.get("workloads", []):
                if w not in registry:
                    problems.append(f"{where}: workload {w} is not registered")
            for e in q.get("evals", []):
                if e not in evals:
                    problems.append(f"{where}: eval {e} is unknown")
            for c in q.get("coming", []):
                if c not in NOT_BUILT:
                    problems.append(f"{where}: coming {c} is not a known unbuilt benchmark")
            for rung in q.get("rungs", []):
                if rung.get("workload") not in registry:
                    problems.append(f"{where}: rung {rung.get('at')!r} names workload {rung.get('workload')} which is not registered")
            if q.get("rungs") and [r["at"] for r in q["rungs"]] != [str(s) for s in q.get("steps", [])]:
                problems.append(f"{where}: the rungs do not match the steps")
            if q.get("chart", "number") not in CHARTS:
                problems.append(f"{where}: chart {q.get('chart')}")
            if not (q.get("workloads") or q.get("evals") or q.get("coming")):
                problems.append(f"{where}: answers nothing")
    for r in tracks["real-world"]["recipes"]:
        where = f"recipe {r.get('id')}"
        for k in set(r) - RECIPE_KEYS - {"file"}:
            problems.append(f"{where}: unknown key {k}")
        for w in r.get("uses", []):
            if w not in registry:
                problems.append(f"{where}: workload {w} is not registered")
        for c in r.get("coming", []):
            if c not in NOT_BUILT:
                problems.append(f"{where}: coming {c} is not a known unbuilt benchmark")
        if r.get("machine") not in MACHINES:
            problems.append(f"{where}: machine {r.get('machine')!r} is not one of {', '.join(MACHINES)}")
        if r.get("conditions") not in CONDITIONS:
            problems.append(f"{where}: conditions {r.get('conditions')!r} is not one of {', '.join(CONDITIONS)}")
        known = set(r.get("uses", [])) | set(r.get("coming", []))
        for rep in r.get("reports", []):
            if rep.get("from") not in known:
                problems.append(f"{where}: report {rep.get('label')!r} takes its number from {rep.get('from')!r}, which the recipe does not use")
        if not r.get("reports"):
            problems.append(f"{where}: says no number it reports")
    return problems


def workloads_of(tracks, which):
    """The wired workload ids of a track (or `all`), in order, once each."""
    ids = []
    for tid in (IDS if which == "all" else (which,)):
        t = tracks[tid]
        found = [w for q in t["questions"] for w in q.get("workloads", [])] + [w for r in t.get("recipes", []) if runnable(r) for w in r.get("uses", [])]
        for w in found:
            if w not in ids:
                ids.append(w)
    return ids


def evals_of(tracks, which):
    out = []
    for tid in (IDS if which == "all" else (which,)):
        out += [e for q in tracks[tid]["questions"] for e in q.get("evals", []) if e not in out]
    return out


def coming_of(tracks, which):
    """[(name, what, where)] of the designed-but-unbuilt benchmarks a track waits for."""
    out = []
    for tid in (IDS if which == "all" else (which,)):
        t = tracks[tid]
        for src, items in [(q["title"], q.get("coming", [])) for q in t["questions"]] + [(r["title"], r.get("coming", [])) for r in t.get("recipes", [])]:
            for c in items:
                if not any(o[0] == c and o[2] == src for o in out):
                    out.append((c, NOT_BUILT[c], src))
    return out


def recipes_of(tracks, which):
    return [r for tid in (IDS if which == "all" else (which,)) for r in tracks[tid].get("recipes", [])]


def runnable(recipe):
    """True when every benchmark the recipe needs is built: a recipe that still waits for one shows as coming."""
    return not recipe.get("coming")


def isolation_of(tracks, which):
    """The isolation a track asks for: container for the Pi family and the real-world scenarios (Track 1 may run bare)."""
    if which in ("pi", "real-world"):
        return "container"
    if which == "all":
        return ""
    return ""


def container_overhead(bare_raw, container_raw, arm, workload="overhead/print", metrics=("wall_ms", "cpu_ms")):
    """The cost of the container itself, from the same arm run bare and in a container (the A/A pair of the isolation): {"arm", "workload", "metrics": {m: {bare, container, ratio}}, "null_run_ms"}.
    Shown once in the method notes, so a reader can see that the container does not distort the speed numbers; None when either run lacks samples of the arm."""
    import statistics

    def med(raw, metric):
        v = [s[metric] for s in raw.get("samples", []) if s.get("arm") == arm and s.get("scenario") == workload and not s.get("warmup") and "failure" not in s and isinstance(s.get(metric), (int, float))]
        return statistics.median(v) if v else None
    out = {}
    for m in metrics:
        b, c = med(bare_raw, m), med(container_raw, m)
        if b and c is not None:
            out[m] = {"bare": round(b, 2), "container": round(c, 2), "ratio": round(c / b, 3)}
    if not out:
        return None
    env = ((container_raw.get("run") or {}).get("isolation") or {}).get("envelope") or {}
    return {"arm": arm, "workload": workload, "metrics": out, "null_run_ms": env.get("null_run_ms")}
