# SPDX-License-Identifier: MIT
"""Codex CLI writer: config.toml in CODEX_HOME. Adapted from the pigbench harness.

With a custom model provider Codex 0.162 still contacts chatgpt.com (cloud config, plugin catalog) and github.com (plugin marketplace) at startup, so
the features that do that are switched off; with them on, the egress audit fails the run."""
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


def write(spec):
    home = ensure(os.path.join(spec.home, ".codex"))
    with open(os.path.join(home, "config.toml"), "w") as f:
        f.write(f'model = "{spec.model}"\nmodel_provider = "bench"\nmodel_context_window = {spec.context_window}\ncheck_for_update_on_startup = false\n'
                f'cli_auth_credentials_store = "file"\n\n{NO_EGRESS}\n[projects."{spec.cwd}"]\ntrust_level = "trusted"\n\n[model_providers.bench]\nname = "bench"\n'
                f'base_url = "{spec.base_url}"\nenv_key = "BENCH_API_KEY"\nwire_api = "responses"\n')
    return {}
