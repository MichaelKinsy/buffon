# SPDX-License-Identifier: Apache-2.0
"""The harness colours of the dashboard (buffon/dashboard/assets/app.css): nine fixed colours, Pi and eight others, one for each harness on every view in both themes.
No two may be near each other: CIEDE2000 (the standard colour difference, better than CIE76 for hue and for blues) for normal vision and for protanopia, deuteranopia and
tritanopia (Machado et al. 2009 simulation). Each must be visible on the panel (WCAG 3:1). The values and the way they were chosen are in docs/design/DASHBOARD.md."""
import itertools
import math
import unittest

from tools import palette_check as pc

SERIES = pc.SERIES   # pi, h1 to h8
# the smallest CIEDE2000 distance allowed between two harness colours
MIN_NORMAL = 15.0
MIN_CVD = 9.0


def to_lab(hex_colour, matrix=None):
    return pc.lab(pc.simulate(hex_colour, matrix) if matrix else tuple(pc.lin(c) for c in pc.rgb(hex_colour)))


def ciede2000(lab1, lab2):
    """CIEDE2000 of Sharma, Wu and Dalal (2005), with kL = kC = kH = 1."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if C1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if C2p else 0.0
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        dhp = dhp - 360 if dhp > 180 else dhp + 360 if dhp < -180 else dhp
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lp, Cp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp = (h1p + h2p) / 2
    else:
        hp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = 1 - 0.17 * math.cos(math.radians(hp - 30)) + 0.24 * math.cos(math.radians(2 * hp)) + 0.32 * math.cos(math.radians(3 * hp + 6)) - 0.20 * math.cos(math.radians(4 * hp - 63))
    dTheta = 30 * math.exp(-(((hp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cp ** 7 / (Cp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lp - 50) ** 2 / math.sqrt(20 + (Lp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cp, 1 + 0.015 * Cp * T
    Rt = -math.sin(math.radians(2 * dTheta)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def distances(theme_colours):
    """{vision: (smallest CIEDE2000 distance between two harness colours, the pair)}."""
    out = {}
    for vision, matrix in [("normal", None)] + list(pc.CVD.items()):
        labs = {k: to_lab(theme_colours[k], matrix) for k in SERIES}
        pair = min(itertools.combinations(SERIES, 2), key=lambda p: ciede2000(labs[p[0]], labs[p[1]]))
        out[vision] = (ciede2000(labs[pair[0]], labs[pair[1]]), pair)
    return out


class HarnessColours(unittest.TestCase):
    def test_the_published_sample_of_ciede2000_is_matched(self):
        # Sharma, Wu and Dalal (2005), table 1, pairs 1 and 17
        self.assertAlmostEqual(ciede2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)), 2.0425, places=3)
        self.assertAlmostEqual(ciede2000((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387)), 1.2644, places=3)

    def test_every_harness_has_its_own_colour_in_each_theme_and_no_two_are_near_each_other_for_any_reader(self):
        for theme, colours in pc.themes().items():
            self.assertEqual(len({colours[k] for k in SERIES}), len(SERIES), theme)
            for vision, (d, pair) in distances(colours).items():
                self.assertGreaterEqual(d, MIN_NORMAL if vision == "normal" else MIN_CVD, f"{theme} {vision}: {pair}")

    def test_every_harness_colour_is_visible_on_the_panel_in_each_theme(self):
        for theme, colours in pc.themes().items():
            for k in SERIES:
                self.assertGreaterEqual(pc.contrast(colours[k], colours["panel"]), 3.0, f"{theme} {k}")

    def test_a_harness_keeps_the_same_hue_in_both_themes(self):
        themes = pc.themes()
        for k in SERIES:
            h = [math.degrees(math.atan2(to_lab(themes[t][k])[2], to_lab(themes[t][k])[1])) % 360 for t in ("dark", "light")]
            d = abs(h[0] - h[1])
            self.assertLessEqual(min(d, 360 - d), 25, k)


if __name__ == "__main__":
    unittest.main()
