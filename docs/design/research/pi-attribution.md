# Pi visual identity, licensing, and attribution for pi-arena

## Recommendations for pi-arena

1. **Be a cousin, not a clone.** Borrow Pi's *ingredients* (warm off-white text `#ebe7e4`, evening-blue text `#252f3d`, hairline panels, status colors, Pi blue only as "this is Pi" data color). Change the *ground hue* (green-slate instead of Pi's navy/parchment) and the *chrome accent* (sage, not Pi blue). Details in section 4.
2. **Do not borrow the distinctive marks.** No Pi logo in the header, no Plantin files, no "crooked mode", no copying pi.dev's `style.css`. Do borrow the *idea* of Fig. NN caption bars and uppercase mono labels, in a different mono (Commit Mono is OFL, Departure Mono is OFL, both fine; see 2).
3. **Say "Pi" in text, always as the reference.** Nominative use ("compared against Pi", "Pi is the reference") needs no permission under normal trademark practice. No trademark policy exists for Pi that I could find, so ask once by email (`rfc@earendil.com`, the press-kit contact) if you want the logo anywhere. Until you hear back, text only.
4. **Put a one-line attribution in the page header strip and a two-sentence non-affiliation notice in the footer.** Wording in section 3. Keep it plain; the Rust, Python, and CNCF policies all ask for exactly this shape.
5. **Give props once, in the reference legend, not in a grade.** Pi is always `1.00x`; the score line can say so in Pi's dry voice. Five candidate lines in section 5.
6. **Credit the fonts you do use** in the footer in 6 words ("Type: Commit Mono, Departure Mono, OFL"). Not required by OFL for plain use (Commit Mono FAQ says credit is needed only when making a derived font), but costs nothing.

## 1. Pi's visual identity (compact spec)

Source: `https://pi.dev/` raw HTML and `https://pi.dev/style.css` (opened, 8066 lines; tokens in `@layer tokens`, lines ~66-440).

### Palette

| Role | Dark | Light | Token |
|---|---|---|---|
| Deep ground | `#0d1116` | `#dacbc2` parchment | `--bg-deep` |
| Page canvas | `#161d27` | `#ebe7e4` moonstone | `--bg-canvas` |
| Panel | `#212730` (90% alpha) | `#f4f2f0` | `--panel` |
| Soft panel / caption bar | `#252f3d` (evening blue) | `#eef1f3` | `--panel-soft` |
| Hairline | `#495059` at 50% | `#8b847d` at ~35% | `--line` |
| Text | `#ebe7e4` | `#252f3d` | `--text` |
| Muted text | `#9fa4ab` at ~68% | `#5c5752` (driftwood) at ~77% | `--muted` |
| Accent (links, focus, label rule) | `#6a9fcc` | `#4b607c` (tidal/thread blue) | `--accent` |
| Secondary series ("rust") | `#8f3222` | `#b86b52` | `--accent-rust` |
| Success / warning / error | `#5db87a` / `#e8993a` / `#e8704f` | n/a (same stops) | `--color-*-dark-stop` |
| Named extras | sunkissed `#e1b06e`, sage `#a3a473`, terracotta `#844f3b` | same | `--color-*` |
| Logo mark (brand) | `#F09082` coral, `#4D9ABF` blue, `#F1BE58` yellow | same | `logo.svg` |
| Header wordmark | `#ffffff` | `#09090b` | `--pi-logo-color` |
| Favicon badge | `#f6f6f6` | `#111111` | `favicon.svg` |

Pi's own chart tokens: series 1 is the accent blue, series 2 is the rust (`--chart-series-1/2`), grid lines are white 12% / evening-blue 10%.

### Typography, layout, voice

| Aspect | Spec | Distinctive or generic? |
|---|---|---|
| Body and headings | Plantin MT Pro (variable, upright and italic), 18px root, weight 450, line-height 1.55-1.6, Georgia fallback | **Distinctive.** Plantin is a commercial Monotype face [INFERENCE: licensing not checked; do not hotlink or copy pi.dev's woff2] |
| Captions, labels, nav, tables | Departure Mono (pixel mono, SIL OFL per `https://departuremono.com/`), uppercase, tracking 0.12-0.18em, 11-15px | **Distinctive in pairing** (serif body plus pixel mono labels). The font alone is generic and free |
| Code and inputs | Commit Mono 300/400/700 (SIL OFL per `https://commitmono.com/`) | Generic |
| Fig. NN captions | Bar above the media: `FIG. 01 | DOOM EXTENSION`, Departure Mono 0.68rem, 2px accent left rule, soft panel fill, blinking square-ish dot | **Distinctive.** Also used in the press kit (`FIG. 01 | TREE VIEW`) |
| Section label | Boxed uppercase mono, 1px hairline, 2px accent left border | **Distinctive in combination** |
| Page grid | 20px cell, faint minor/major/cross lines (`--page-grid-cell`) | Semi-distinctive |
| Radii | Mostly 0; 4px and 999px (dot) only | Generic (square corners) |
| Active stripe | 62% accent, 38% thread blue split | Distinctive, tiny |
| Theme | Auto / Light / Dark footer toggle, `data-theme`, key `pi:theme` | Generic |
| Crooked mode | Toggle rotates the whole page 1.3deg, ground `#24103a`, subtitle `#ff4fa1`, Comic Sans stack; reset callout | **Very distinctive, an in-joke.** Do not copy |
| Logo | Three blocky pieces forming a pi glyph, coral/blue/yellow (`/logo.svg`), mono badge for favicon | **Distinctive, the brand** |
| Dark ground, hairlines, uppercase small labels, blue accent | | Generic |
| Voice | Short declarative, mildly contrarian, owns omissions: "There are many agent harnesses, but this one is yours." "What we didn't build." "No MCP. Now with MCP+Codemode. Why we changed our minds." "Pi isn't a sealed product." "Go make them yours." "$ scroll to continue." | Distinctive, dry, kind to the reader |

Earendil's company pages share Plantin, Departure Mono, and a paper texture (`https://earendil.com/`: `paper.png`, `paper-dark.png`), so the serif-plus-pixel-mono look is the house style of the whole Earendil family, not only Pi (stylesheet and font links seen in earendil.com HTML).

## 2. What the license and brand guidance allow

| Finding | Evidence |
|---|---|
| Code is MIT, "Copyright (c) 2025 Mario Zechner". Permits use, copy, modify, publish, with the copyright notice kept in copies. Says nothing on names, logos, or fonts. | `https://raw.githubusercontent.com/earendil-works/pi/main/LICENSE`; GitHub reports "MIT License" (`https://github.com/earendil-works/pi`) |
| Site footer reads "Earendil Inc. & Contributors", "Press Kit", "MIT License". README ends "MIT". So the site and repo are open, the company is Earendil Inc. | `https://pi.dev/` footer; repo README |
| **No trademark or brand-usage policy found.** Grepped README, CONTRIBUTING, AGENTS, SECURITY: no "trademark", "brand", "affiliat", "endorse". Only hit in the repo is an issue-template checkbox "Trademark / TOS Violations" for reported packages (`.github/ISSUE_TEMPLATE/package-report.yml`). | repo files fetched via raw.githubusercontent.com; `gh search code trademark --repo earendil-works/pi` |
| Press kit offers "Brand files": Primary logo SVG (`/logo.svg`), Badge SVG (`/favicon.svg`), two screenshots (ZIP) for "articles, videos, and conference slides", an editorial summary, and `rfc@earendil.com` for press. **No usage terms.** pi.dev also has a "Copy SVG / Download SVG" logo menu. | `https://pi.dev/press-kit` |
| Nothing on "compatible with" language. Third parties already name things after Pi freely (`pi-gpt-voice`, `@bdsqqq/pi`, `pi-wechat-assistant`) in the official package catalog. | `https://pi.dev/packages` |
| Reading: the press kit invites editorial and coverage use of the logo and screenshots. A benchmark page is editorial coverage. Still, absence of a policy is not a grant for look-alike branding. | [INFERENCE] |
| Earendil's stated values lean generous ("Reach first for generosity", "Assuming grace leads to grace"), which fits a friendly benchmark. | `https://earendil.com/values/` |

**Practical rule for pi-arena:** use the word "Pi" nominatively and accurately; link to pi.dev; do not use "official", "certified", "powered by Pi"; do not put the logo in your header or favicon; do not mimic the crooked toggle or Fig. captions pixel for pixel; email once if you want the logo.

## 3. Norms for attribution and non-affiliation

| Source | What it says | URL (opened) |
|---|---|---|
| Rust Foundation | Marks "cannot be used in ways that appear (to a casual observer) official, affiliated, or endorsed" (applies even to uses needing no approval). Accurate statements of compatibility with Rust are allowed without approval. "Official", "original", "only" are called out as likely to imply endorsement. | https://rustfoundation.org/policy/rust-trademark-policy/ |
| Python Software Foundation | "Nominative use": stating accurately that software is compatible with Python is always allowed, in a way "that is minimal and does not imply a sponsorship relationship". Suggested legal-page statement: "'Python' and the Python logos are trademarks ... used by ___ with permission". Not applicable to us, we are not licensed; do not copy it. Logos: use unaltered or not at all; derived logos "must always be sufficiently different". | https://www.python.org/psf/trademarks/ |
| Linux Foundation (also governs Kubernetes marks) | Fair use allowed for true factual statements, but not to "state or imply that the owner of a mark produces, endorses, or supports your company, products, or services". Approved patterns: "<your product> compatible with <mark>", "for use with", "plug-in for". Disallowed: "<mark> <your product>" and "<mark> - <your product>". | https://www.linuxfoundation.org/legal/trademark-usage |
| CNCF brand guidelines | Your name must be more prominent than theirs. Don't edit their logo. Template statement: "[Title] is not affiliated with or otherwise sponsored by CNCF." | https://www.cncf.io/brand-guidelines/ |
| Node / OpenJS | Page fetched (`https://trademark-policy.openjsf.org/`) but my keyword search found no non-affiliation wording; not cited as evidence. | n/a |

Common shape: (a) accurate nominative naming, (b) one plain sentence "not affiliated with / not endorsed by", (c) name your own project first and more prominently, (d) no look-alike logo.

### Proposed wording

Attribution (header strip or "about" line, serif italic like Pi's announcement bar):

> pi-arena measures how much a coding agent harness costs before the model says a word, using Pi as the reference. Pi is by Mario Zechner and Earendil Inc., MIT licensed, at pi.dev.

Non-affiliation (footer, small mono caps or plain serif):

> pi-arena is an independent project. It is not affiliated with, endorsed by, or sponsored by Earendil Inc., the Pi project, or any harness it measures. Pi and other names belong to their owners.

Short variant for chart exports and screenshots:

> Independent benchmark. Not affiliated with Pi. Reference: pi.dev

Where they go: attribution in the top strip beside the site name (once); non-affiliation in the footer on every page and embedded in any exported PNG or SVG (short variant); both on the "Method" page; a "Type" credit line for fonts at the footer end. Do not repeat them next to every chart.

## 4. Cousin palette proposal

Principle: same warm-white-on-cool-ground *family feel*, different ground hue, different accent role, Pi blue reserved as the "Pi series" data color (so the reference is always visibly Pi, which is also the props gesture).

Borrow from Pi (generic or already-neutral tokens): text `#ebe7e4`, light text `#252f3d`, hairline-on-panel construction, ~18px base size, 20px grid idea (as a very faint background, optional), square corners, status colors, Auto/Light/Dark toggle.
Change: ground hue (green-slate), accent (sage), caption pattern (no blinking dot, no 2px left rule: use a 1px top rule), serif (not Plantin), no logo, no crooked mode.

| Token | Dark | Light | Notes (contrast vs ground, computed WCAG) |
|---|---|---|---|
| `--ground` | `#0e1412` | `#eceae3` | Green-slate vs Pi navy `#0d1116` and Pi parchment `#dacbc2`. Distinct at a glance, same temperature |
| `--panel` | `#18201d` | `#f6f5f0` | Table and card fill |
| `--line` | `#3f4a45` | `#c9c6bb` | Hairlines, 1px |
| `--text` | `#ebe7e4` (borrowed) | `#252f3d` (borrowed) | 15.2:1 dark, 11.2:1 light |
| `--muted` | `#9fa6a1` | `#566058` | 7.5:1 / 5.4:1 |
| `--accent` (chrome: links, focus, rules) | `#a3a473` sage | `#6b6c3e` deep sage | 7.2:1 / 4.5:1. Pi's palette has sage but never uses it as accent, so it is cousin, not copy |
| `--pi` (the reference series, 1.00x line and label) | `#6a9fcc` | `#3f6a8f` | Pi blue. 6.6:1 / 4.8:1. Deliberate nod |
| `--series-2` | `#e1b06e` sunkissed | `#8a5a14` | 9.4:1 / 4.9:1 |
| `--series-3` | `#b86b52` | `#a8432c` | 4.7:1 / 5.0:1 (dark is marginal, use for fills and thick lines only) |
| `--better` (ratio < 1) | `#5db87a` | `#2a7345` | 7.6:1 / 4.8:1 |
| `--worse` (ratio > 1) | `#e8704f` | `#a8432c` | 6.1:1 / 5.0:1 |
| `--noise-band` (A/A floor) | `#ebe7e4` at 8% | `#252f3d` at 8% | Same trick as Pi's `--chart-area-muted` |

Never use coral `#F09082` plus blue `#4D9ABF` plus yellow `#F1BE58` together; that triple *is* the logo.

Type: body in a free serif with similar warmth (suggest Source Serif 4 or Newsreader, both OFL) [INFERENCE: license and availability from memory, verify before shipping], Georgia fallback; labels in Commit Mono uppercase 0.12em (not Departure Mono, so the pairing is not identical); numbers in Commit Mono with tabular figures. Captions: `FIG. 3 · CPU TIME RATIO` is fine as a generic scientific convention, but without the left accent rule and cursor dot.

## 5. Props lines (Pi's dry voice, kind, no em dashes)

Pick one for the reference legend, one for the score card, others as hover text or empty states.

1. "Pi is 1.00x everywhere. It wrote the ruler, so it gets to stand at zero."
2. "C by definition, A for being the goalpost." (owner's line; if grades are dropped, use: "70 by definition, full marks for being the goalpost.")
3. "Everyone else is measured against Pi. Pi is measured against Pi, and still passes."
4. "Minimal on purpose. Still the one the rest of us have to beat."
5. "This page exists because Pi gave us something worth comparing to."
6. A/A noise-floor caption: "Pi against itself: any gap smaller than this is just Pi being Pi."
7. Empty-state for a harness that beats Pi: "Faster than Pi. Pi would say: go make it yours."

Tone checks: self-contained, short, no all-caps, no "beats", "crushes", or "loses" framing, and none of them say the harnesses compared are worse people for being slower.

## Sources opened

- https://pi.dev/ (raw HTML), https://pi.dev/style.css, https://pi.dev/press-kit, https://pi.dev/logo.svg, https://pi.dev/logo-auto.svg, https://pi.dev/favicon.svg, https://pi.dev/packages
- https://github.com/earendil-works/pi (README), https://raw.githubusercontent.com/earendil-works/pi/main/LICENSE (also CONTRIBUTING, AGENTS, SECURITY, grepped)
- https://earendil.com/, https://earendil.com/values/, https://earendil.com/purpose/
- https://rustfoundation.org/policy/rust-trademark-policy/, https://www.python.org/psf/trademarks/, https://www.linuxfoundation.org/legal/trademark-usage, https://www.cncf.io/brand-guidelines/
- https://departuremono.com/, https://commitmono.com/ (font licenses)
