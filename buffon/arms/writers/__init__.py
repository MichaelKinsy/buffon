# SPDX-License-Identifier: Apache-2.0
"""Config writers: put the mock endpoint, a dummy key and the workload's settings into an arm's isolated HOME.

A writer is `write(spec) -> dict` that creates files under spec.home and returns extra environment variables. It never touches the real HOME:
spec.home is a fresh directory for one run of one arm.
"""
import os
from dataclasses import dataclass, field

DUMMY_KEY = "bench-dummy-key-not-a-credential"
MODEL = "bench-1"


@dataclass
class WriteSpec:
    arm: object
    home: str
    agent_dir: str
    cwd: str
    base_url: str          # http://127.0.0.1:<port>/v1
    origin: str            # http://127.0.0.1:<port>
    api: str = "openai-completions"
    model: str = MODEL
    context_window: int = 128000
    compaction: dict = None
    retry_base_ms: int = 50
    settings_extra: dict = field(default_factory=dict)
    tui_mode: str = None   # the renderer pin for PTY workloads

    def endpoint(self):
        """The base URL the arm's SDK expects for this wire API: Anthropic's SDKs append /v1/messages themselves."""
        return self.origin if self.api == "anthropic-messages" else self.base_url


def ensure(path):
    os.makedirs(path, exist_ok=True)
    return path
