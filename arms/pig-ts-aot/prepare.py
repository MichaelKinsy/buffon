from buffon.arms.prepare_pig import aot_slot

EXPECT_BUN = {"linux-x64": "a83d263767d839e4d2649ca8e35d07159c7afc99afdc96d731ced29e056dda0c"}


def prepare(ws, arm, base):
    aot_slot(ws, arm, base, EXPECT_BUN[ws.platform])
