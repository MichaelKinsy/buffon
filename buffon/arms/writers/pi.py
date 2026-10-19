# SPDX-License-Identifier: MIT
"""Pi-family writer (Pi, PiG, Pi-Bolt, rpi): models.json and settings.json in the agent directory. Adapted from the pigbench harness."""
import json
import os

from . import DUMMY_KEY, ensure


def write(spec):
    ensure(spec.agent_dir)
    with open(os.path.join(spec.agent_dir, "models.json"), "w") as f:
        json.dump({"providers": {"bench": {"baseUrl": spec.endpoint(), "api": spec.api, "apiKey": DUMMY_KEY,
                                           "models": [{"id": spec.model, "name": "Bench 1", "contextWindow": spec.context_window, "maxTokens": 4096}]}}}, f)
    settings = {"defaultProvider": "bench", "defaultModel": spec.model, "retry": {"enabled": True, "maxRetries": 3, "baseDelayMs": spec.retry_base_ms},
                "quietStartup": True, "collapseChangelog": True}
    pin = spec.tui_mode or spec.arm.renderer.get("pty")
    if pin and pin != "default":
        settings["tuiMode"] = pin
    if spec.compaction:
        settings["compaction"] = spec.compaction
    settings.update(spec.settings_extra)
    with open(os.path.join(spec.agent_dir, "settings.json"), "w") as f:
        json.dump(settings, f)
    return {}
