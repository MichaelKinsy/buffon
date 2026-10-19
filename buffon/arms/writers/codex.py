# SPDX-License-Identifier: MIT
"""Codex CLI writer: config.toml in CODEX_HOME. Adapted from the pigbench harness.

With a custom model provider Codex 0.162 still contacts chatgpt.com (cloud config, plugin catalog) and github.com (plugin marketplace) at startup, so
the features that do that are switched off; with them on, the egress audit fails the run."""
import json
import os

from . import DUMMY_KEY, ensure

NO_EGRESS = """[features]
plugins = false
recommended_plugins = false
remote_models = false
plugin_sharing = false
apps = false
remote_plugin = false

[analytics]
enabled = false

[otel]
exporter = "none"

[feedback]
enabled = false

[history]
persistence = "none"

[tui]
show_tooltips = false
"""


def catalog(slug):
    """A model catalog with one entry for the mock's model, as Codex's `model_catalog_json` documents. An unknown model gets Codex's fallback entry, which has no `apply_patch` tool and so no
    way to write a file; Codex's own models carry `apply_patch_tool_type = "freeform"`, and this entry differs from the fallback in nothing else. The large-write workload names the file
    in its `print_write` mode (arm.toml) and no other workload loads it."""
    return {"models": [{
        "slug": slug, "display_name": slug, "description": None, "supported_reasoning_levels": [], "shell_type": "unified_exec", "visibility": "none", "supported_in_api": True,
        "priority": 99, "availability_nux": None, "upgrade": None, "support_verbosity": False, "default_verbosity": None, "apply_patch_tool_type": "freeform",
        "truncation_policy": {"mode": "bytes", "limit": 10000}, "experimental_supported_tools": [], "base_instructions": BASE_INSTRUCTIONS}]}


# The fallback entry's instructions are a 20 KB prompt; the catalog entry carries a one-line one, so the large-write sample's requests differ from the other workloads' in that.
BASE_INSTRUCTIONS = "You are a coding agent running in the Codex CLI, a terminal-based coding assistant."


def write(spec):
    home = ensure(os.path.join(spec.home, ".codex"))
    with open(os.path.join(home, "write-catalog.json"), "w") as f:
        json.dump(catalog(spec.model), f)
    with open(os.path.join(home, "config.toml"), "w") as f:
        f.write(f'model = "{spec.model}"\nmodel_provider = "bench"\nmodel_context_window = {spec.context_window}\ncheck_for_update_on_startup = false\n'
                f'cli_auth_credentials_store = "file"\n\n{NO_EGRESS}\n[projects."{spec.cwd}"]\ntrust_level = "trusted"\n\n[model_providers.bench]\nname = "bench"\n'
                f'base_url = "{spec.base_url}"\nenv_key = "BENCH_API_KEY"\nwire_api = "responses"\n')
    return {}
