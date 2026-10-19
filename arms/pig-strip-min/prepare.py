import os

from buffon.arms.manifest import ROOT
from buffon.arms.prepare_pig import fused_binary


def prepare(ws, arm, base):
    """The opt-in strip Piglet: keep mode with nothing kept, so every optional built-in extension, extra provider API and feature is compiled out (fixtures/piglets/pig-min.yaml)."""
    fused_binary(ws, arm, base, os.path.join(ROOT, "fixtures", "piglets", "pig-min.yaml"))
