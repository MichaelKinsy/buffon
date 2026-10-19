# SPDX-License-Identifier: Apache-2.0
"""Claude Code writer: points the CLI at the mock's Anthropic Messages endpoint with environment variables only (it needs no config file).

ANTHROPIC_BASE_URL is the origin (the CLI appends /v1/messages itself). The key is Buffon's dummy; CLAUDE_CONFIG_DIR keeps its state in the throwaway HOME. The model id
`bench-1` is not in the CLI's catalog, so it is given the window Buffon configures (CLAUDE_CODE_MAX_CONTEXT_TOKENS), which silences the unknown-model notice."""
import os

from . import ensure


def write(spec):
    ensure(os.path.join(spec.home, ".claude"))
    return {"ANTHROPIC_BASE_URL": spec.origin, "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(spec.context_window)}
