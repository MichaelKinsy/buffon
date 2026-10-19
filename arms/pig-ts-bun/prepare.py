from buffon.arms.prepare_pig import bun_slot, warm_cache

# The sha256 of the bun executable inside bun-linux-x64.zip (Bun 1.4.2): the entry of PiG's runtime lock, coding/extension/host/tsruntime/lock.go.
EXPECT = {"linux-x64": "a83d263767d839e4d2649ca8e35d07159c7afc99afdc96d731ced29e056dda0c"}


def prepare(ws, arm, base):
    bun_slot(ws, arm, EXPECT[ws.platform])
    warm_cache(ws, arm)
