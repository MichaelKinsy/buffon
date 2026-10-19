import os

from buffon.arms.prepare_pig import fused_binary, source_dir


def prepare(ws, arm, base):
    """PiG Standard: the Piglet at piglets/standard/pig-standard.yaml of the base arm's own checkout, built into one binary with `pig piglet build --format binary`."""
    fused_binary(ws, arm, base, os.path.join(source_dir(ws, base), "piglets", "standard", "pig-standard.yaml"))
