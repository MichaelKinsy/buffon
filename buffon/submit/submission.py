# SPDX-License-Identifier: Apache-2.0
"""submission.toml: what the person who submits a run directory says about it. Validated strictly; unknown keys are errors."""
import os
import tomllib

NAME = "submission.toml"
REQUIRED = {"operator": str, "hardware": str, "independent": bool}
OPTIONAL = {"organisation": str, "notes": str, "reproduces": str}


def load(run_dir):
    """(dict, problems). `operator` names who ran it, `hardware` describes the machine in words (what else ran on it, who else had access), `independent` says the operator
    neither maintains nor works on any arm in the run (docs/DESIGN.md section 10), `reproduces` names the results directory this run reproduces."""
    path = os.path.join(run_dir, NAME)
    if not os.path.exists(path):
        return {}, [f"{NAME} is missing (docs/SUBMITTING.md describes it)"]
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as error:
        return {}, [f"{NAME} is not valid TOML: {error}"]
    problems = []
    for key, kind in {**REQUIRED, **OPTIONAL}.items():
        if key in data and not isinstance(data[key], kind):
            problems.append(f"{NAME}: `{key}` must be {kind.__name__}")
    problems += [f"{NAME}: `{k}` is required" for k in REQUIRED if k not in data]
    problems += [f"{NAME}: unknown key `{k}`" for k in data if k not in REQUIRED and k not in OPTIONAL]
    for key in ("operator", "hardware"):
        if isinstance(data.get(key), str) and len(data[key].strip()) < 3:
            problems.append(f"{NAME}: `{key}` is empty")
    return data, problems
