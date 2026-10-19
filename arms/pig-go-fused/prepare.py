import os

from buffon.arms.prepare_pig import fused_binary
from buffon.arms.manifest import ROOT


def prepare(ws, arm, base):
    fused_binary(ws, arm, base, os.path.join(ROOT, "fixtures", "extensions-go", "pig-ext10.yaml"))
