# SPDX-License-Identifier: Apache-2.0
"""The README banner, docs/assets/buffon-banner.svg: the Buffon mark (needles on parallel boards, the ones that cross a board in Pi's blue) with the wordmark and the one-line promise.

Usage: python3 tools/readme_banner.py docs/assets/buffon-banner.svg && rsvg-convert -w 1966 -h 800 docs/assets/buffon-banner.svg -o docs/assets/buffon-banner.png"""
import math, random, sys

W, H = 1966, 800
BG, INK, MUTED, PI, LINE = "#0f1211", "#ebe7e4", "#969c98", "#6a9fcc", "#3a403d"
rnd = random.Random(7)
out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
       f'<rect width="{W}" height="{H}" fill="{BG}"/>',
       '<defs><pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.4" fill="#1f6b5c" opacity=".55"/></pattern></defs>',
       f'<rect width="{W}" height="{H}" fill="url(#dots)"/>',
       f'<rect x="58" y="58" width="{W - 116}" height="{H - 116}" fill="{BG}" stroke="{INK}" stroke-opacity=".85" stroke-width="3"/>']

# the mark, large, on the left: the favicon's three boards and three needles, drawn at 11x
mx, my, s = 300, 150, 8.2
out.append(f'<g transform="translate({mx},{my}) scale({s})" fill="none" stroke-linecap="round">')
out.append(f'<path d="M1 6H31M1 15H31M1 24H31" stroke="{INK}" stroke-opacity=".5" stroke-width="1.6"/>')
out.append(f'<path d="M4 20L12 18" stroke="{INK}" stroke-width="3.2"/>')
out.append(f'<path d="M7 11L12 2M20 19L26 29" stroke="{PI}" stroke-width="3.2"/>')   # the needles that cross a board, in Pi's blue, as on the site's hero
out.append("</g>")

# a field of needles on boards behind the wordmark: the same drop every time (seeded), crossing needles in Pi's blue
x0, x1, gap, top, n_lines, length = 610, 1700, 46, 170, 5, 30
for k in range(n_lines):
    y = top + k * gap
    out.append(f'<line x1="{x0}" x2="{x1}" y1="{y}" y2="{y}" stroke="{LINE}" stroke-width="2"/>')
for _ in range(40):
    cx, cy, a = x0 + 20 + rnd.random() * (x1 - x0 - 40), top - 20 + rnd.random() * (gap * (n_lines - 1) + 40), rnd.random() * math.pi
    dx, dy = math.cos(a) * length / 2, math.sin(a) * length / 2
    crosses = math.floor((cy - dy - top) / gap) != math.floor((cy + dy - top) / gap)
    colour, op = (PI, 1) if crosses else (MUTED, .55)
    out.append(f'<line x1="{cx - dx:.1f}" y1="{cy - dy:.1f}" x2="{cx + dx:.1f}" y2="{cy + dy:.1f}" stroke="{colour}" stroke-opacity="{op}" stroke-width="5" stroke-linecap="round"/>')

# the wordmark, over the field
out.append(f'<text x="{x0 + 60}" y="340" font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-weight="700" font-size="200" letter-spacing="2" fill="{INK}" '
           f'stroke="{BG}" stroke-width="14" paint-order="stroke">Buffon</text>')
# the promise
serif = 'font-family="Georgia, Times New Roman, serif" font-style="italic"'
out.append(f'<text x="{W / 2}" y="545" text-anchor="middle" {serif} font-size="64" fill="{INK}">Drop the same <tspan fill="{PI}">Pi use case</tspan> on every harness,</text>')
out.append(f'<text x="{W / 2}" y="628" text-anchor="middle" {serif} font-size="64" fill="{INK}">many times, and count what each one costs.</text>')
out.append("</svg>")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
