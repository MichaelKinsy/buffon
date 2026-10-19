import os

from buffon.arms.prepare_pig import patched_build, warm_cache


def prepare(ws, arm, base):
    patched_build(ws, arm, base, os.path.join(os.path.dirname(os.path.abspath(__file__)), "isolate-node-factories.patch"))
    warm_cache(ws, arm)
