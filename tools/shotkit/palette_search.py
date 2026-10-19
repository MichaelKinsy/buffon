"""Finds the nine harness colours (Pi and eight others) of one theme: far apart for normal vision and for the three kinds of colour blindness
(CIEDE2000 after the Machado et al. 2009 simulation), and visible on the panel (WCAG 3:1). Pi's blue is fixed. A development tool: the colours it finds are pasted
into app.css, and tests/test_dashboard_palette.py checks them there.

    python3 tools/shotkit/palette_search.py dark|light [seed [the nine colours of the other theme, comma separated]]"""
import itertools
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools import palette_check as pc  # noqa: E402
from tests.test_dashboard_palette import ciede2000, to_lab  # noqa: E402

PANEL = {"dark": "#171a19", "light": "#fbfaf7"}
PI = {"dark": "#6a9fcc", "light": "#3f6a8f"}
VISIONS = [("normal", None, 1.0)] + [(k, m, w) for k, m, w in (("protanopia", pc.CVD["protanopia"], 0.6), ("deuteranopia", pc.CVD["deuteranopia"], 0.6), ("tritanopia", pc.CVD["tritanopia"], 0.5))]


def oklch_to_hex(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_, m_, s_ = L + 0.3963377774 * a + 0.2158037573 * b, L - 0.1055613458 * a - 0.0638541728 * b, L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    if any(c < 0 or c > 1 for c in rgb):
        return None
    enc = lambda c: 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return "#%02x%02x%02x" % tuple(round(enc(c) * 255) for c in rgb)


def hex_to_oklch(hex_colour):
    r, g, b = (pc.lin(c) for c in pc.rgb(hex_colour))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L, a, bb = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def near_hue(c1, c2):
    """Two colours with a colour (not grey) and a hue within 30 degrees and a lightness within 0.15 read as the same colour."""
    (L1, C1, h1), (L2, C2, h2) = hex_to_oklch(c1), hex_to_oklch(c2)
    d = abs(h1 - h2)
    return C1 > 0.05 and C2 > 0.05 and min(d, 360 - d) < 38 and abs(L1 - L2) < 0.12


def score(colours):
    """The smallest CIEDE2000 distance between two colours, over the visions, each weighted: higher is better."""
    worst = 1e9
    near = sum(near_hue(a, b) for a, b in itertools.combinations(colours, 2))
    if near:
        return -float(near)
    for name, matrix, weight in VISIONS:
        labs = [to_lab(c, matrix) for c in colours]
        for i in range(len(labs)):
            for j in range(i + 1, len(labs)):
                worst = min(worst, ciede2000(labs[i], labs[j]) / weight)
    return worst


def search(theme, seed=1, rounds=40000, hues=None):
    """`hues`: nine hues (degrees) the colours must stay within 12 degrees of, slot by slot: the other theme's, so a harness keeps its hue in both themes."""
    rnd = random.Random(seed)
    panel = PANEL[theme]
    lo, hi = (0.62, 0.86) if theme == "dark" else (0.40, 0.62)

    def draw(slot=None):
        while True:
            h = rnd.uniform(0, 360) if hues is None else (hues[slot] + rnd.uniform(-12, 12)) % 360
            c = oklch_to_hex(rnd.uniform(lo, hi), rnd.uniform(0.115, 0.20), h)
            if c and pc.contrast(c, panel) >= 3.3:
                return c
    cur = [PI[theme]] + [draw(i) for i in range(1, 9)]
    best, best_score = cur[:], score(cur)
    for step in range(rounds):
        cand = best[:]
        k = rnd.randrange(1, 9)
        cand[k] = draw(k)
        s = score(cand)
        if s > best_score:
            best, best_score = cand, s
    return best, best_score


if __name__ == "__main__":
    theme = sys.argv[1]
    hues = [hex_to_oklch(c)[2] for c in sys.argv[3].split(",")] if len(sys.argv) > 3 else None
    best, s = search(theme, int(sys.argv[2]) if len(sys.argv) > 2 else 1, hues=hues)
    print(theme, round(s, 1), " ".join(best))
