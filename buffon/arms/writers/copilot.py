# SPDX-License-Identifier: Apache-2.0
"""GitHub Copilot CLI writer: the CLI's bring-your-own-key mode, set with environment variables only (`copilot help providers`).

A custom provider needs no GitHub sign-in, and COPILOT_OFFLINE=true (the manifest's [env]) stops its GitHub, telemetry and update traffic. The wire API picks the provider type:
OpenAI Chat Completions (`openai`, the default wire API), OpenAI Responses (`openai` with COPILOT_PROVIDER_WIRE_API=responses) or Anthropic Messages (`anthropic`, base URL without /v1)."""
import os

from . import ensure

WIRE = {"openai-completions": ("openai", "completions"), "openai-responses": ("openai", "responses"), "anthropic-messages": ("anthropic", None)}


def write(spec):
    ensure(os.path.join(spec.home, ".copilot"))
    kind, wire = WIRE[spec.api]
    env = {"COPILOT_PROVIDER_BASE_URL": spec.endpoint(), "COPILOT_PROVIDER_TYPE": kind, "COPILOT_MODEL": spec.model,
           "COPILOT_PROVIDER_MAX_PROMPT_TOKENS": str(spec.context_window), "COPILOT_PROVIDER_MAX_OUTPUT_TOKENS": "8192"}
    if wire:
        env["COPILOT_PROVIDER_WIRE_API"] = wire
    return env
