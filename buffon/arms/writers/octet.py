# SPDX-License-Identifier: Apache-2.0
"""Octet writer: one custom provider in the registry `~/.octet/credentials/custom.json`, which is where Octet keeps OpenAI-compatible endpoints it does not know.

The registry names one provider, `bench`, with the mock's Chat Completions endpoint, no authentication (the dummy key is never needed for a keyless custom provider) and one model
with its limits declared, so Octet makes no `GET /models` request at startup (`auto_discover = false`). The model is addressed as `custom/bench/<model>`. The file must be
owner-only (0600) or Octet refuses it. Next to it, `~/.octet/config.toml` fixes the terminal theme: without a saved theme the first interactive start opens a "Choose terminal appearance" picker that no
workload answers. Extra environment: none; the manifest's [env] turns the optional network traffic off.
"""
import json
import os

from . import ensure

PROVIDER = "bench"
MAX_OUTPUT_TOKENS = 8192   # Octet needs an output limit next to the context window; the scripted replies are far shorter


def write(spec):
    directory = ensure(os.path.join(spec.home, ".octet", "credentials"))
    path = os.path.join(directory, "custom.json")
    registry = {"version": 1, "providers": {PROVIDER: {
        "label": "Buffon mock",
        "base_url": spec.endpoint().rstrip("/") + "/",
        "auth": {"kind": "none"},
        "auto_discover": False,
        "models": [{"api_name": spec.model, "context_window": spec.context_window, "max_output_tokens": MAX_OUTPUT_TOKENS, "tools": True, "parallel_tool_calls": False,
                    "vision": False, "structured_output": False, "reasoning": False}],
    }}}
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(registry, f, indent=2)
    os.chmod(path, 0o600)
    with open(os.path.join(spec.home, ".octet", "config.toml"), "w") as f:
        f.write('theme = "dark"\n')
    return {}
