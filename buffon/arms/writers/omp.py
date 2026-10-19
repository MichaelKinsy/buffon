# SPDX-License-Identifier: MIT
"""omp (oh-my-pi) writer: models.yml and config.yml (JSON is YAML). Adapted from the pigbench harness.

Without setupVersion 2 and the wizard off, omp waits at a first-run wizard. startup.checkUpdate and marketplace.autoUpdate are omp's own switches for its update checks
(settings schema in the 18.8.8 binary); omp reads no PI_OFFLINE-style variable."""
import json
import os

from . import DUMMY_KEY, ensure


def write(spec):
    ensure(spec.agent_dir)
    with open(os.path.join(spec.agent_dir, "models.yml"), "w") as f:
        json.dump({"providers": {"bench": {"baseUrl": spec.endpoint(), "api": spec.api, "apiKey": DUMMY_KEY,
                                           "models": [{"id": spec.model, "name": "Bench 1", "contextWindow": spec.context_window, "maxTokens": 4096}]}}}, f)
    with open(os.path.join(spec.agent_dir, "config.yml"), "w") as f:
        json.dump({"setupVersion": 2, "startup": {"setupWizard": False, "checkUpdate": False, "showSplash": False}, "marketplace": {"autoUpdate": "off"}}, f)
    return {}
