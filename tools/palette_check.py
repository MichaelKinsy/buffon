# SPDX-License-Identifier: Apache-2.0
"""Checks the dashboard's palette (buffon/dashboard/assets/app.css) in both themes: WCAG contrast of text against the panel (4.5:1) and of every
harness and status colour against it (3:1, the bar for graphical marks), and how far apart the harness colours stay for readers with protanopia,
deuteranopia and tritanopia (Machado, Oliveira and Fernandes 2009 simulation, CIE76 colour difference in Lab).

    python3 tools/palette_check.py          prints the table docs/design/DASHBOARD.md quotes"""
import itertools
import os
import re
import sys

CSS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "buffon", "dashboard", "assets", "app.css")
TEXT = ("ink", "ink-2", "muted", "accent")
MARKS = ("pi", "h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8", "cool", "warm", "warn", "win", "loss", "same", "unclear")
SERIES = ("pi", "h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8")
# Machado et al. 2009, severity 1.0, linear RGB
CVD = {"protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
       "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
       "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900))}


def themes(path=CSS):
    """{"dark": {token: hex}, "light": {token: hex}} from the :root and [data-theme=light] blocks."""
    with open(path) as f:
        css = f.read()
    dark = css[css.index(":root {"):css.index("}", css.index(":root {"))]
    light = css[css.index(':root[data-theme="light"] {'):css.index("}", css.index(':root[data-theme="light"] {'))]
    get = lambda block: {k: v.lower() for k, v in re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", block)}
    return {"dark": get(dark), "light": get(light)}


def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(hex_colour):
    return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))


def luminance(hex_colour):
    r, g, b = (lin(c) for c in rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def lab(linear):
    r, g, b = linear
    x, y, z = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, 0.2126 * r + 0.7152 * g + 0.0722 * b, (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def simulate(hex_colour, matrix):
    v = [lin(c) for c in rgb(hex_colour)]
    return tuple(min(1.0, max(0.0, sum(m * c for m, c in zip(row, v)))) for row in matrix)


def delta(a, b):
    return sum((p - q) ** 2 for p, q in zip(a, b)) ** 0.5


def report(path=CSS):
    """{theme: {"text": {token: ratio}, "marks": {token: ratio}, "cvd": {vision: (smallest difference, pair)}}}."""
    out = {}
    for theme, t in themes(path).items():
        bg = t["panel"]
        out[theme] = {"text": {k: contrast(t[k], bg) for k in TEXT}, "marks": {k: contrast(t[k], bg) for k in MARKS}, "cvd": {}}
        for vision, matrix in [("normal", None)] + list(CVD.items()):
            labs = {k: lab(simulate(t[k], matrix) if matrix else tuple(lin(c) for c in rgb(t[k]))) for k in SERIES}
            pair = min(itertools.combinations(SERIES, 2), key=lambda p: delta(labs[p[0]], labs[p[1]]))
            out[theme]["cvd"][vision] = (delta(labs[pair[0]], labs[pair[1]]), pair)
    return out


def main():
    for theme, r in report().items():
        print(f"## {theme}")
        print("text on panel (needs 4.5): " + ", ".join(f"{k} {v:.1f}" for k, v in r["text"].items()))
        print("marks on panel (needs 3.0): " + ", ".join(f"{k} {v:.1f}" for k, v in r["marks"].items()))
        for vision, (d, pair) in r["cvd"].items():
            print(f"closest harness colours, {vision}: {pair[0]} and {pair[1]}, difference {d:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
