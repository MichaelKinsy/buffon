# SPDX-License-Identifier: Apache-2.0
"""phi writer: ~/.phi/config.yaml with one model entry on the mock endpoint (JSON is YAML). The `api` field is explicit in phi's config: OpenAI is
chat-completions, OpenAIResponses the Responses API, Anthropic the Messages API (doc/models.md in the phi repository)."""
import json
import os

from . import DUMMY_KEY, ensure

API = {"openai-completions": "OpenAI", "openai-responses": "OpenAIResponses", "anthropic-messages": "Anthropic"}


def write(spec):
    config = os.path.join(spec.home, ".phi")
    ensure(config)
    entry = {"name": spec.model, "api": API[spec.api], "api_key": DUMMY_KEY, "base_url": spec.endpoint(), "context_window": spec.context_window, "default": True}
    with open(os.path.join(config, "config.yaml"), "w") as f:
        json.dump({"models": [entry]}, f)
    # phi downloads fd and rg from GitHub at startup when neither ~/.phi/bin nor PATH has them; that is egress. A stub that fails when called stands in for the missing
    # tools, as Pi's grep and find have no rg or fd on Buffon's PATH either.
    bin_dir = ensure(os.path.join(config, "bin"))
    for tool in ("fd", "rg"):
        path = os.path.join(bin_dir, tool)
        with open(path, "w") as f:
            f.write(f"#!/bin/sh\necho '{tool}: not available in Buffon (no network, no installed copy)' >&2\nexit 127\n")
        os.chmod(path, 0o755)
    return {}
