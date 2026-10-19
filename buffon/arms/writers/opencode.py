# SPDX-License-Identifier: Apache-2.0
"""OpenCode writers: one `opencode.json` in the global config directory ($XDG_CONFIG_HOME/opencode, inside the throwaway HOME).

OpenCode 1 and OpenCode 2 read the same file name but different provider and permission shapes, so each has its own function (arms/opencode/writer.py and
arms/opencode-v2/writer.py import one of them). Both point a custom provider at the mock's OpenAI Chat Completions endpoint, take the key from BENCH_API_KEY
(the arm manifest's [env]), allow every tool without asking (a headless `run` cannot answer a permission prompt, and OpenCode 1 then rejects the tool call),
turn session sharing off and turn the update check off. What the config cannot switch off (the models.dev catalog fetch, OpenCode 1's background install of
`@opencode-ai/plugin`) is switched off by the manifest's [env]."""
import json
import os

from . import ensure

PROVIDER = "bench"
MAX_OUTPUT_TOKENS = 8192   # OpenCode needs an output limit next to the context window; the scripted replies are far shorter


def _save(spec, config):
    directory = ensure(os.path.join(spec.home, ".config", "opencode"))
    with open(os.path.join(directory, "opencode.json"), "w") as f:
        json.dump(config, f, indent=2)
    return {}


def write(spec):
    """OpenCode 1 (`opencode-ai`): `provider` map with an AI SDK package, `permission` by tool, `autoupdate`, `share`."""
    return _save(spec, {
        "$schema": "https://opencode.ai/config.json",
        "autoupdate": False,
        "share": "disabled",
        "model": f"{PROVIDER}/{spec.model}",
        "permission": {"*": "allow"},
        "provider": {PROVIDER: {
            "npm": "@ai-sdk/openai-compatible",
            "name": PROVIDER,
            "options": {"baseURL": spec.endpoint(), "apiKey": "{env:BENCH_API_KEY}"},
            "models": {spec.model: {"name": spec.model, "tool_call": True, "limit": {"context": spec.context_window, "output": MAX_OUTPUT_TOKENS}}},
        }},
    })


def write_v2(spec):
    """OpenCode 2 (`@opencode/cli`): native `providers` map with a runtime package, ordered `permissions` rules, `update`, `share`."""
    return _save(spec, {
        "$schema": "https://opencode.ai/config.json",
        "update": "disable",
        "share": "disabled",
        "model": f"{PROVIDER}/{spec.model}",
        "permissions": [{"action": "*", "resource": "*", "effect": "allow"}],
        "providers": {PROVIDER: {
            "name": PROVIDER,
            "env": ["BENCH_API_KEY"],
            "package": "@opencode/ai/providers/openai-compatible",
            "settings": {"baseURL": spec.endpoint()},
            "models": {spec.model: {"name": spec.model, "capabilities": {"tools": True, "input": ["text"], "output": ["text"]},
                                    "limit": {"context": spec.context_window, "output": MAX_OUTPUT_TOKENS}}},
        }},
    })
