# SPDX-License-Identifier: Apache-2.0
"""raw.json: the one raw format of a buffon run (docs/RAW-FORMAT.md). Validated when written and when read.

The shape is strict and current: there is no version field and no reader for any other shape.
"""
import json
import math
import os

IDENTITY = ("arm", "scenario", "api", "round", "warmup", "t_utc", "failure", "series", "twin_of")
KINDS = ("buffon-run", "arena-run")   # "arena-run" is what runs published before the project was renamed carry
TOP = ("kind", "run", "site", "hardware", "lock_sha256", "runner", "arms", "calibration", "egress", "isolation", "samples", "skipped", "ok")
DURABLE_NESTED = ("runtime_settings", "runtime_versions", "store_tables", "compaction_ids")   # dicts and a list on a durable sample (docs/RAW-FORMAT.md)


class RawError(ValueError):
    pass


SCHED_KEYS = ("run_ms", "wait_ms", "slices", "threads", "meters")


def _check_sched(value, where):
    """A sample's schedstat totals (docs/RAW-FORMAT.md): exactly SCHED_KEYS, each a finite number of at least 0."""
    if not isinstance(value, dict) or set(value) != set(SCHED_KEYS):
        raise RawError(f"{where}: want an object with exactly {', '.join(SCHED_KEYS)}")
    for k, v in value.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise RawError(f"{where}.{k}: want a finite number of at least 0")


HOME_KEYS = ("fresh", "pre_files", "pre_sha256", "post_files", "post_sha256", "written", "removed", "homes")


def _check_home(value, where):
    """A sample's home isolation proof (docs/RAW-FORMAT.md): exactly HOME_KEYS; `fresh` a bool, the digests 64 hex digits, the rest counts of at least 0."""
    if not isinstance(value, dict) or set(value) != set(HOME_KEYS):
        raise RawError(f"{where}: want an object with exactly {', '.join(HOME_KEYS)}")
    if not isinstance(value["fresh"], bool):
        raise RawError(f"{where}.fresh: want a bool")
    for k in ("pre_sha256", "post_sha256"):
        if not isinstance(value[k], str) or len(value[k]) != 64 or any(c not in "0123456789abcdef" for c in value[k]):
            raise RawError(f"{where}.{k}: want 64 hex digits")
    for k in ("pre_files", "post_files", "written", "removed", "homes"):
        if isinstance(value[k], bool) or not isinstance(value[k], int) or value[k] < 0:
            raise RawError(f"{where}.{k}: want a count of at least 0")


def _check_text_fs(value, where):
    """A sample's executable-mapping record (docs/RAW-FORMAT.md): `fs` maps a file system type to a file count, `bad` lists mapped files on tmpfs, ramfs or in shared memory."""
    if not isinstance(value, dict) or set(value) != {"fs", "bad"}:
        raise RawError(f"{where}: want an object with exactly fs and bad")
    if not isinstance(value["fs"], dict) or any(not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, int) or v < 0 for k, v in value["fs"].items()):
        raise RawError(f"{where}.fs: want file system names mapped to counts")
    if not isinstance(value["bad"], list) or any(not isinstance(x, str) for x in value["bad"]):
        raise RawError(f"{where}.bad: want a list of paths")


POD_KEYS = ("node", "cpuset", "qos")


def _check_pod(value, where):
    """A pod-guaranteed sample's pod facts (docs/RAW-FORMAT.md): exactly POD_KEYS, each a string or null."""
    if not isinstance(value, dict) or set(value) != set(POD_KEYS):
        raise RawError(f"{where}: want an object with exactly {', '.join(POD_KEYS)}")
    for k, v in value.items():
        if v is not None and not isinstance(v, str):
            raise RawError(f"{where}.{k}: want a string or null")


SWARM_KEYS = ("memory_mib", "cpus", "pids_max")


def _check_swarm(value, where):
    """A swarm sample's envelope (docs/RAW-FORMAT.md): exactly SWARM_KEYS; `memory_mib` and `pids_max` counts above 0, `cpus` a non-empty list of CPU numbers."""
    if not isinstance(value, dict) or set(value) != set(SWARM_KEYS):
        raise RawError(f"{where}: want an object with exactly {', '.join(SWARM_KEYS)}")
    for k in ("memory_mib", "pids_max"):
        if isinstance(value[k], bool) or not isinstance(value[k], int) or value[k] < 1:
            raise RawError(f"{where}.{k}: want a count of at least 1")
    cpus = value["cpus"]
    if not isinstance(cpus, list) or not cpus or any(isinstance(c, bool) or not isinstance(c, int) or c < 0 for c in cpus):
        raise RawError(f"{where}.cpus: want a non-empty list of CPU numbers")


def _check_probes(value, where):
    """A scale sample's probes (docs/RAW-FORMAT.md): every N the search tried, in order. Each is an object with `n` (a count of at least 1), `phase` (double or bisect) and `ok` (a bool); the rest is
    the metrics of that probe, nested and never compared as a sample's own."""
    if not isinstance(value, list):
        raise RawError(f"{where}: want a list of probes")
    for i, p in enumerate(value):
        at = f"{where}[{i}]"
        if not isinstance(p, dict):
            raise RawError(f"{at}: want an object")
        if isinstance(p.get("n"), bool) or not isinstance(p.get("n"), int) or p["n"] < 1:
            raise RawError(f"{at}.n: want a count of at least 1")
        if p.get("phase") not in ("double", "bisect"):
            raise RawError(f"{at}.phase: want double or bisect")
        if not isinstance(p.get("ok"), bool):
            raise RawError(f"{at}.ok: want a bool")
        _check_json(p, at)


def _check_json(value, where):
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise RawError(f"{where}: keys must be strings")
            _check_json(v, f"{where}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _check_json(v, f"{where}[{i}]")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise RawError(f"{where} is not finite")
    elif not (value is None or isinstance(value, (bool, int, str))):
        raise RawError(f"{where}: {type(value).__name__} is not JSON")


def check_sample(s, where="sample"):
    for key, kind in (("arm", str), ("scenario", str), ("round", int), ("warmup", bool)):
        if not isinstance(s.get(key), kind) or isinstance(s.get(key), bool) and kind is int:
            raise RawError(f"{where}: `{key}` must be {kind.__name__}")
    if s["round"] < 0:
        raise RawError(f"{where}: round is negative")
    if s.get("api") is not None and not isinstance(s["api"], str):
        raise RawError(f"{where}: `api` must be a string or null")
    if "failure" in s and not isinstance(s["failure"], str):
        raise RawError(f"{where}: `failure` must be a string")
    if "telemetry" in s:
        _check_json(s["telemetry"], f"{where}: telemetry")
    if "sched" in s:
        _check_sched(s["sched"], f"{where}: sched")
    if "pod" in s:
        _check_pod(s["pod"], f"{where}: pod")
    if "home" in s:
        _check_home(s["home"], f"{where}: home")
    if "text_fs" in s:
        _check_text_fs(s["text_fs"], f"{where}: text_fs")
    if "swarm" in s:
        _check_swarm(s["swarm"], f"{where}: swarm")
    if "probes" in s:
        _check_probes(s["probes"], f"{where}: probes")
    for key in DURABLE_NESTED:   # a durable sample's declared settings, versions, table row counts and compaction ids: JSON, shown by the Method page, never a metric
        if key in s:
            _check_json(s[key], f"{where}: {key}")
    for key, value in s.items():
        if key in IDENTITY or key in DURABLE_NESTED or key in ("telemetry", "sched", "pod", "home", "text_fs", "swarm", "probes"):   # pod: the node, cpuset and QoS a pod-guaranteed sample ran with   # telemetry: observers' data (docs/HOOKS.md); sched: schedstat counters. Nested, never a metric the report compares
            continue
        if isinstance(value, bool) or value is None or isinstance(value, str):
            continue
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise RawError(f"{where}: metric `{key}` is not finite")
            continue
        raise RawError(f"{where}: metric `{key}` must be a number, bool, string or null (a series goes under `series`)")


def _check_runtime_settings(value, where):
    """An arm's runtime-tuning record (docs/RAW-FORMAT.md): `env` maps tuning variables to the values its manifest sets, `left_default` lists the known tuning variables left at the
    harness's own default, `source` names where each `env` variable came from. A variable is in exactly one of `env` and `left_default`."""
    from . import tuning
    if not isinstance(value, dict) or set(value) != {"env", "left_default", "source"}:
        raise RawError(f"{where}: want an object with exactly env, left_default and source")
    env, left, source = value["env"], value["left_default"], value["source"]
    if not isinstance(env, dict) or any(not isinstance(k, str) or not tuning.is_tuning(k) or not isinstance(v, str) for k, v in env.items()):
        raise RawError(f"{where}.env: want runtime-tuning variable names mapped to string values")
    if not isinstance(left, list) or any(not isinstance(k, str) or not tuning.is_tuning(k) for k in left) or len(set(left)) != len(left):
        raise RawError(f"{where}.left_default: want a list of runtime-tuning variable names without repeats")
    if set(env) & set(left):
        raise RawError(f"{where}: {', '.join(sorted(set(env) & set(left)))} is both set and left at the default")
    if not isinstance(source, dict) or set(source) != set(env) or any(v not in tuning.SOURCES for v in source.values()):
        raise RawError(f"{where}.source: want exactly the variables of env, each {' or '.join(tuning.SOURCES)}")


def _check_divergences(value, where):
    """An arm's declared divergences (docs/RAW-FORMAT.md), the manifest's [[divergence]] tables as written."""
    from ..divergence import KEYS
    if not isinstance(value, list):
        raise RawError(f"{where}: want a list")
    for i, d in enumerate(value):
        at = f"{where}[{i}]"
        if not isinstance(d, dict) or not {"workloads", "reason", "source"} <= set(d) <= KEYS:
            raise RawError(f"{at}: want an object with workloads, reason and source, and optionally metrics")
        for key in ("workloads", "metrics"):
            if key in d and (not isinstance(d[key], list) or any(not isinstance(g, str) or not g for g in d[key])):
                raise RawError(f"{at}.{key}: want a list of glob strings")
        if not d["workloads"]:
            raise RawError(f"{at}.workloads: want at least one glob")
        for key in ("reason", "source"):
            if not isinstance(d[key], str) or not d[key].strip():
                raise RawError(f"{at}.{key}: want a non-empty string")


def validate(raw):
    for key in TOP:
        if key not in raw:
            raise RawError(f"raw.json lacks `{key}`")
    if raw["kind"] not in KINDS:
        raise RawError("raw.json `kind` must be buffon-run")
    if not isinstance(raw["samples"], list):
        raise RawError("`samples` must be a list")
    for i, s in enumerate(raw["samples"]):
        check_sample(s, f"samples[{i}]")
    for arm, info in (raw["arms"].items() if isinstance(raw["arms"], dict) else ()):
        if isinstance(info, dict) and not arm.startswith("_"):   # runs written before these fields have neither: the report reads them as no tuning record and no divergences
            if "runtime_settings" in info:
                _check_runtime_settings(info["runtime_settings"], f"arms[{arm}].runtime_settings")
            if "divergences" in info:
                _check_divergences(info["divergences"], f"arms[{arm}].divergences")
    for i, k in enumerate(raw["skipped"]):
        if not all(isinstance(k.get(x), str) for x in ("arm", "scenario", "reason")):
            raise RawError(f"skipped[{i}] needs arm, scenario and reason strings")
    return raw


def write(raw, out_dir, name="raw.json"):
    """Validate and write atomically."""
    validate(raw)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(raw, f, indent=1, allow_nan=False)
    os.replace(tmp, path)
    return path


def read(path):
    if os.path.isdir(path):
        for marker in ("external.json", "external-suite.json"):
            if os.path.exists(os.path.join(path, marker)):
                raise ValueError(f"{path} is an external result, not a buffon run: it never enters cells or aggregates (use --external-results / --external-suites)")
        path = os.path.join(path, "raw.json")
    with open(path) as f:
        return first_request_bytes(validate(json.load(f)))


def first_request_bytes(raw):
    """Runs made before the wire metrics recorded `request_bytes` as the size of the first request only. A sample written since always carries `requests` beside
    `request_bytes` (the sum of every request), so a sample with `request_bytes` and no `requests` is the old meaning: read it as `first_request_bytes`."""
    for s in raw.get("samples", []):
        if "request_bytes" in s and "requests" not in s:
            s["first_request_bytes"] = s.pop("request_bytes")
    return raw
