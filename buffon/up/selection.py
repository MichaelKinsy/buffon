# SPDX-License-Identifier: Apache-2.0
"""A selection: which harnesses, which benchmarks, which evals and options. Parsed from flags, saved to and loaded from a TOML file, and turned back into the exact `buffon up` command."""
import difflib
import fnmatch
import json
import os
import re
import shlex
import tomllib
from dataclasses import dataclass, field

from .. import workloads as workloadlib
from ..arms import manifest
from . import catalog


class SelectionError(ValueError):
    pass


@dataclass
class Selection:
    harnesses: list = field(default_factory=lambda: list(catalog.DEFAULT_HARNESSES))
    accept_terms: list = field(default_factory=list)    # the selected harnesses whose vendor terms the operator accepted (--accept-terms, BUFFON_ACCEPT_TERMS, or the saved file)
    workloads: list = field(default_factory=list)      # workload ids, in run order
    preset: str = ""                                    # the preset the workloads came from, when they are exactly a preset's
    track: str = ""                                     # common, pi, real-world or all: the workloads, evals and recipes came from the tracks (buffon/up/tracks.py)
    recipes: list = field(default_factory=list)         # real-world recipe ids that run as their own groups (a recipe with parameters)
    spec: str = ""                                      # what the person typed for --bench when it was a list (families, globs, aliases), so the saved file and the command say it as they did
    apis: list = field(default_factory=list)
    rounds: int = 12                                    # the most a cell takes
    rounds_set: bool = field(default=False, compare=False)                            # the operator chose the rounds (--rounds, or `rounds` in a file): they apply to every workload, the scale family's default of 5 included
    adaptive: bool = True
    calibration_rounds: int = 8
    evals: list = field(default_factory=list)
    offline: bool = False
    isolation: str = ""                                 # "", "container", "none" or "auto" (a track's default: container where there is a runtime and pinned CPUs)
    memory_tier_gib: int = 4                            # the memory limit of every harness container: a fixed tier (1, 2, 4 or 8)
    time_budget_s: float = 0.0
    seed: int = 20261011
    params: dict = field(default_factory=dict)          # workload parameters (--param KEY=VALUE), passed to every run of the selection

    def clone(self, **changes):
        out = Selection(**{**self.__dict__, **changes})
        return out


def parse_duration(text):
    """`90`, `90s`, `20m`, `1h30m`, `2h` -> seconds."""
    text = str(text).strip().lower()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    parts = re.findall(r"(\d+(?:\.\d+)?)([hms])", text)
    if not parts or "".join(n + u for n, u in parts) != text:
        raise SelectionError(f"{text!r} is not a duration (use 90s, 20m or 1h30m)")
    return sum(float(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in parts)


def format_duration(seconds):
    seconds = int(round(seconds))
    if seconds < 90:
        return f"{seconds} s"
    if seconds < 5400:
        return f"{seconds // 60} min" + (f" {seconds % 60} s" if seconds < 600 and seconds % 60 else "")
    return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"


def _split(text):
    return [t for t in re.split(r"[,\s]+", text.strip()) if t] if isinstance(text, str) else [t for item in text for t in _split(item)]


def parse_harnesses(text, arms=None, accept=None):
    """`pig,pi,pi-bolt`, globs and `all` -> arm ids, in the order named. A name matches an arm id exactly, else as a glob, else as the start of an id (`pig` -> every pig-*)
    only when it matches nothing else; `all` is every arm that runs by default and is not held. An unknown name lists the nearest ids.
    An arm with `operator_terms` is never matched by `all`, a glob or a prefix: it runs only when its id is named and `accept` (a set of arm ids; default: BUFFON_ACCEPT_TERMS) holds it,
    else the selection fails quoting the terms."""
    arms = arms if arms is not None else manifest.load_all()
    accept = manifest.accepted_terms() if accept is None else set(accept)
    usable = {n: a for n, a in arms.items() if not a.held and not a.operator_terms}
    gated = {n: a for n, a in arms.items() if not a.held and a.operator_terms}
    out = []
    for token in _split(text):
        if token == "all":
            found = [n for n, a in usable.items() if a.runs_by_default]
        elif token in gated:
            if token not in accept:
                raise SelectionError(manifest.terms_refusal(gated[token]))
            found = [token]
        elif token in usable:
            found = [token]
        elif token in catalog.SHORT_NAMES and catalog.SHORT_NAMES[token] in usable:
            found = [catalog.SHORT_NAMES[token]]
        elif any(c in token for c in "*?["):
            found = [n for n in usable if fnmatch.fnmatchcase(n, token)]
        else:
            found = [n for n in usable if n.startswith(token + "-")]
            exact_default = [n for n in found if usable[n].runs_by_default]
            found = exact_default or found
        if not found:
            held = [n for n, a in arms.items() if a.held and (n == token or fnmatch.fnmatchcase(n, token))]
            if held:
                raise SelectionError(f"harness {token!r} is held ({arms[held[0]].held[:80]}); `buffon harnesses` lists what can run")
            terms = [n for n in gated if fnmatch.fnmatchcase(n, token) or n.startswith(token + "-")]
            if terms:
                raise SelectionError(f"harness {token!r} matches {', '.join(terms)}, which run only when named in full and accepted: " + " ".join(manifest.terms_refusal(gated[n]) for n in terms))
            near = difflib.get_close_matches(token, list(usable), n=3)
            raise SelectionError(f"no harness matches {token!r}" + (f"; did you mean {', '.join(near)}?" if near else "") + ". `buffon harnesses` lists them")
        out += [n for n in found if n not in out]
    if not out:
        raise SelectionError("no harness selected")
    return out


def terms_of(harnesses, arms, accept):
    """The harnesses in the list that have operator terms and are accepted, in order: what a selection records."""
    return [h for h in harnesses if getattr(arms.get(h), "operator_terms", None) and h in accept]


def parse_benches(text, registry=None):
    """`quick`, `streaming,long-session,memory`, `overhead/print*` -> (workload ids in run order, the preset name when the list is exactly one preset's else "")."""
    registry = registry if registry is not None else workloadlib.load_all()
    tokens = _split(text)
    if not tokens:
        raise SelectionError("no benchmark selected")
    if len(tokens) == 1 and tokens[0] in catalog.PRESETS:
        return list(catalog.PRESETS[tokens[0]]["workloads"]) and _expand(catalog.PRESETS[tokens[0]]["workloads"], registry), tokens[0]
    out = []
    for token in tokens:
        names = catalog.PRESETS[token]["workloads"] if token in catalog.PRESETS else catalog.ALIASES.get(token, [token])
        for n in _expand(names, registry, token):
            if n not in out:
                out.append(n)
    return out, ""


def bench_spec(text):
    """The canonical text of a --bench list: tokens joined by commas."""
    return ",".join(_split(text))


def _expand(names, registry, label=None):
    out = []
    for name in names:
        if name in registry:
            found = [name]
        elif any(c in name for c in "*?["):
            found = [w for w in registry if fnmatch.fnmatchcase(w, name)]
        else:
            found = [w for w, x in registry.items() if x.family == name]
        if not found:
            known = sorted({w.family for w in registry.values()} | set(registry) | set(catalog.PRESETS) | set(catalog.ALIASES))
            near = difflib.get_close_matches(label or name, known, n=3)
            raise SelectionError(f"no benchmark matches {label or name!r}" + (f"; did you mean {', '.join(near)}?" if near else "") + ". `buffon benches` lists them")
        out += [f for f in found if f not in out]
    return out


def parse_evals(text):
    items = [e for e in _split(text) if e != "none"]
    for e in items:
        if e not in catalog.EVALS:
            raise SelectionError(f"unknown eval {e!r}; known: {', '.join(catalog.EVALS)}")
    return items


def from_track(which, registry=None, tracks=None):
    """The selection a track means: the wired workloads of its questions, its evals, and the runnable real-world recipes. A recipe with parameters runs as its own group; the track's
    isolation is `auto` (a container where there is a runtime and pinned CPUs, bare with a note otherwise) for the Pi family and the real-world scenarios."""
    from . import tracks as trackslib
    if which not in trackslib.ALL:
        raise SelectionError(f"unknown track {which!r}; known: {', '.join(trackslib.ALL)}")
    registry = registry if registry is not None else workloadlib.load_all()
    tracks = tracks if tracks is not None else trackslib.load()
    recipes = [r for r in trackslib.recipes_of(tracks, which) if trackslib.runnable(r)]
    own = [r["id"] for r in recipes if r.get("params")]
    ids = trackslib.workloads_of(tracks, which)
    own_uses = {w for r in recipes if r["id"] in own for w in r["uses"]}
    base = [w for w in ids if w not in own_uses or any(w in q.get("workloads", []) for t in (tracks["common"], tracks["pi"]) for q in t["questions"])]
    return Selection(workloads=base, track=which, recipes=own, apis=["openai-completions"], rounds=12, adaptive=True, calibration_rounds=8, evals=trackslib.evals_of(tracks, which),
                     isolation="auto" if which in ("pi", "real-world", "all") else "")


def from_preset(name, registry=None):
    p = catalog.PRESETS[name]
    return Selection(workloads=_expand(p["workloads"], registry if registry is not None else workloadlib.load_all()), preset=name, apis=list(p["apis"]), rounds=p["rounds"], adaptive=p["adaptive"],
                     calibration_rounds=p["calibration_rounds"], evals=list(p["evals"]))


# -- saving and loading -----------------------------------------------------------------------------------------------------------------------------

KEYS = {"harness", "accept_terms", "bench", "preset", "track", "memory_tier", "apis", "rounds", "adaptive", "calibration_rounds", "evals", "offline", "isolation", "time_budget", "seed", "params"}


def _q(items):
    return "[" + ", ".join('"' + str(i).replace('"', '\\"') + '"' for i in items) + "]"


def dumps(sel):
    lines = ["# A buffon selection: run it with `buffon up <this file>`.", "[up]", f"harness = {_q(sel.harnesses)}"]
    if sel.accept_terms:
        lines.append(f"accept_terms = {_q(sel.accept_terms)}   # the operator accepted these harnesses' vendor terms (`buffon harnesses` quotes them)")
    lines.append(f'track = "{sel.track}"' if sel.track else f'preset = "{sel.preset}"' if sel.preset else f"bench = {_q(_split(sel.spec) if sel.spec else sel.workloads)}")
    lines += [f"apis = {_q(sel.apis)}", *([f"rounds = {sel.rounds}"] if sel.rounds_set or sel.rounds != 12 else []), f"adaptive = {str(sel.adaptive).lower()}", f"calibration_rounds = {sel.calibration_rounds}", f"evals = {_q(sel.evals)}",
              f"offline = {str(sel.offline).lower()}"]
    if sel.isolation:
        lines.append(f'isolation = "{sel.isolation}"')
    if sel.memory_tier_gib != 4:
        lines.append(f"memory_tier = {sel.memory_tier_gib}")
    if sel.time_budget_s:
        lines.append(f'time_budget = "{int(sel.time_budget_s)}s"')
    lines.append(f"seed = {sel.seed}")
    if sel.params:
        lines.append("params = { " + ", ".join(f"{k} = {json.dumps(v)}" for k, v in sorted(sel.params.items())) + " }")
    return "\n".join(lines) + "\n"


def save(sel, path):
    with open(path, "w") as f:
        f.write(dumps(sel))


def loads(text, arms=None, registry=None, accept=None):
    """`accept` (a set of arm ids) adds to the terms the file itself records as accepted."""
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise SelectionError(f"not a valid selection file: {error}") from error
    body = doc.get("up", doc)
    unknown = sorted(set(body) - KEYS)
    if unknown:
        raise SelectionError(f"unknown key(s) in the selection: {', '.join(unknown)}; known: {', '.join(sorted(KEYS))}")
    registry = registry if registry is not None else workloadlib.load_all()
    if body.get("track"):
        base = from_track(body["track"], registry)
    else:
        base = from_preset(body["preset"], registry) if body.get("preset") else Selection()
    if body.get("preset") and body["preset"] not in catalog.PRESETS and not body.get("track"):
        raise SelectionError(f"unknown preset {body['preset']!r}")
    sel = base
    arms_all = arms if arms is not None else manifest.load_all()
    accepted = set(body.get("accept_terms", [])) | (manifest.accepted_terms() if accept is None else set(accept))
    if "harness" in body:
        sel.harnesses = parse_harnesses(body["harness"], arms_all, accepted)
    sel.accept_terms = terms_of(sel.harnesses, arms_all, accepted)
    if "bench" in body:
        sel.workloads, sel.preset = parse_benches(body["bench"], registry)
        sel.spec = "" if sel.preset else bench_spec(body["bench"])
    for key, attr in (("apis", "apis"), ("rounds", "rounds"), ("adaptive", "adaptive"), ("calibration_rounds", "calibration_rounds"), ("offline", "offline"), ("isolation", "isolation"), ("seed", "seed"), ("memory_tier", "memory_tier_gib")):
        if key in body:
            setattr(sel, attr, body[key])
    sel.rounds_set = "rounds" in body
    if "evals" in body:
        sel.evals = parse_evals(body["evals"])
    if "time_budget" in body:
        sel.time_budget_s = parse_duration(body["time_budget"])
    if "params" in body:
        if not isinstance(body["params"], dict):
            raise SelectionError("params must be a table: params = { swarm_max_agents = 64 }")
        sel.params = dict(body["params"])
    if not sel.workloads:
        raise SelectionError("the selection names no benchmark (bench = [...] or preset = \"quick\")")
    if not sel.apis:
        sel.apis = ["openai-completions"]
    return sel


def load(path, arms=None, registry=None, accept=None):
    try:
        with open(path) as f:
            return loads(f.read(), arms, registry, accept)
    except OSError as error:
        raise SelectionError(f"cannot read {path}: {error}") from error


def widen_apis(apis, harnesses, arms):
    """(apis, added): the wire APIs, plus the first API of each chosen harness that speaks none of them (Codex speaks only the Responses API), so every harness has
    something to run. Pi speaks every API, so each harness is still paired with Pi on the same API. `added` is [(harness, api)] in harness order."""
    out, added = list(apis), []
    for h in harnesses:
        own = list(getattr(arms.get(h), "apis", None) or [])
        if own and not any(a in own for a in out):
            out.append(own[0])
            added.append((h, own[0]))
    return out, added


def command(sel, program="python3 -m buffon", selection_file=None):
    """The exact command that repeats this selection: the saved file when there is one, else every choice as a flag."""
    if selection_file:
        return f"{program} up {shlex.quote(selection_file)}"
    parts = [program, "up", "--harness", ",".join(sel.harnesses)] + (["--track", sel.track] if sel.track else ["--bench", sel.preset or sel.spec or ",".join(sel.workloads)])
    defaults = ({"apis": ["openai-completions"], "rounds": 12, "adaptive": True, "evals": from_track(sel.track).evals} if sel.track else None) or catalog.PRESETS.get(sel.preset or "") or {"apis": ["openai-completions"], "rounds": 12, "adaptive": True, "evals": []}
    if sel.apis != defaults["apis"]:
        parts += ["--apis", ",".join(sel.apis)]
    if sel.rounds_set or sel.rounds != defaults["rounds"]:
        parts += ["--rounds", str(sel.rounds)]
    if sel.adaptive != defaults["adaptive"]:
        parts += ["--adaptive" if sel.adaptive else "--no-adaptive"]
    if sel.evals != defaults["evals"]:
        parts += ["--evals", ",".join(sel.evals) or "none"]
    if sel.accept_terms:
        parts += ["--accept-terms", ",".join(sel.accept_terms)]
    if sel.memory_tier_gib != 4:
        parts += ["--memory-tier", str(sel.memory_tier_gib)]
    if sel.offline:
        parts.append("--offline")
    for key, value in sorted(sel.params.items()):
        parts += ["--param", f"{key}={json.dumps(value) if not isinstance(value, str) else value}"]
    default = from_track(sel.track).isolation if sel.track else ("auto" if any(w.startswith("scale/") for w in sel.workloads) else "")   # a track's, or the swarm's: a container where the machine has one
    if sel.isolation and sel.isolation != default:
        parts += ["--isolation", sel.isolation]
    if sel.time_budget_s:
        parts += ["--time-budget", f"{int(sel.time_budget_s)}s"]
    return program + " " + " ".join(shlex.quote(p) for p in parts[1:])
