# Chart inspiration for pi-arena

## Recommendations for pi-arena

Principle: every mark is a draw from the bootstrap or a real round, every number sits on its chart, and the only decoration is the uncertainty itself. Pi is the neutral ink baseline (1.00x, score 70), never a villain colour. No letter grades anywhere; the score scale is the only grade.

| View | Form | Number placement | Stunning but honest touch |
|---|---|---|---|
| (a) Overall ranking | Sorted dot + graded interval (50/80/95) rows, Pi reference line at 70, tails fading | Score inline at dot; rank range ("2 to 4") as the row's right-hand tag; caption holds profile and method once | Opt-in "Reshuffle" HOP: replays ~20 bootstrap draws re-ordering the rows |
| (b) Suite forest | Log-x dot + 95% CI rows, grouped by suite, A/A band shaded around 1.0 | Right gutter "0.62x [0.58, 0.67]" per row, tabular figures; caption holds n and CI type | Hollow dots when the CI sits inside the A/A band; clipped CIs end in an arrow |
| (c) Paired rounds | Per-harness 12-dot strip (no density) + word-sized drift sparkline with A/A band; click a row for Pi-to-harness arrow plot | Median ratio inline at strip end; sparkline end value coloured to match its endpoint dot | "Shuffle test": real round order beside 9 random orders (Tufte) so drift is not storytelling |
| (d) Four memory kinds | Small multiples: one shared-log-scale mini forest per kind, same row order | Point value at dot; Pi's absolute value in each panel header; CI on hover only | Same x range across panels; a kind that overflows gets a clipped arrow with its number |
| (e) One bootstrap ratio | Quantile dotplot (50 dots, 2% each), ratio=1 rule, A/A band, interval beneath | Frequency caption under the plot: "In 47 of 50 reruns Pi is ahead" | Dots fall in once on view (draws building a pile), then stay still |
| (f) KPI tiles | Big number + bullet-style interval strip (A/A band as the quiet range, Pi tick at 1.0) | Number is the tile's headline; interval strip carries the uncertainty; word delta ("a bit under Pi") | Strip draws outward from 1.00 on load; no count-up numbers |

Global rules at the bottom. Anti-redundancy rules after them. Evidence follows.

## Global rules

- Palette: grays for all non-data and for most data (Datawrapper: gray is the most important colour; grids lighter than axis labels, titles darker). One accent for the focal harness, one neutral for Pi, one hue ramp for the rest. No red/green good/bad; state direction in words ("cheaper than Pi"). Keep 3 to 7 hues max.
- Gridlines: none except the reference at 1.0 (70 for scores), plus faint ticks. The noise band replaces gridlines as the second landmark.
- Motion: entrance animation once, 300 to 600ms, structure only (intervals grow from the reference, dots drop in). User-triggered HOP frames at 400 to 500ms with hard cuts, not morphs. Respect `prefers-reduced-motion`. Never animate fake variation (see NYT needle jitter).
- Numbers: `font-variant-numeric: tabular-nums`, right-aligned in gutters, units in a lighter weight, one decimal convention (two decimals for ratios, `x` suffix). Geist uses tabular numerals for numbers in secondary labels; copy that habit.
- Dark mode: author colours as CSS custom properties on the SVG (`var(--ink)`, `var(--grid)`, `var(--band)`, `var(--accent)`), switch via `prefers-color-scheme`. Keep contrast per element constant between themes (Datawrapper) rather than inverting; define a separate dark accent because saturated dark blues turn muddy when lightened. Derive themes from three inputs (base, accent, contrast) in a perceptual space (Linear does this in LCH).
- Hover: one shared tooltip, event delegation, nearest-mark on pointer, also on `:focus-visible`. Tooltip shows only what is not already drawn (e.g., P(ratio<1), a hidden CI). Every row carries `aria-label` with the full numbers so DOM text exists without redundant pixels.

## Anti-redundancy rules

1. One fact, one place: a number is either an inline label or in the caption, never both, and never in a separate table of the same data.
2. Each drill-down level shows a different quantity: score (a) > suite ratio (b) > per-round values (c) > resampling (e). Tiles (f) summarise the family level once.
3. Direct-label instead of legends (name at row start, ratio at row end). Legend only if colour encodes something not in the rows.
4. A caption is a single stat strip: n=12 rounds, 95% bootstrap interval, A/A floor value, weight profile. Stated once per chart; Wilke: error bars must say which quantity and level.
5. Order carries rank; do not add a rank column unless rank is uncertain (then show the range, which is new information).
6. No mirrored densities (raincloud paper calls the mirror redundant data-ink). With n=12 skip the density entirely.
7. If two panels share a scale, draw the axis once.

## Evidence and rendering notes

### (a) Ranked harnesses with intervals
- Why: Padilla, Kay, Hullman say interval-only displays push viewers toward categorical reading ("inside vs outside") and recommend adding a more representative display (gradient, quantile dotplot, HOP) when an interval is shown (UCMerced prepress, Visual Boundaries section and General Discussion). Wilke Ch.16: graded error bars (several levels, darker for lower confidence) reduce deterministic construal. ggdist's `stat_gradientinterval` maps density to opacity; Correll and Gleicher-style fading tails are a recipe in the same vignette.
- Static SVG: one `<g>` per row, a `<linearGradient>` per row (horizontal, stops from bootstrap density or from stacked 50/80/95 rects at 0.9/0.6/0.3 opacity), 6px-tall rounded bar, 10px dot on top. Vertical line at 70 labelled "Pi, by definition". Needs 50/80/95 intervals from the pipeline (only 95 is published today; same draws, free to compute).
- Numbers: score at the dot (above), rank range at right as a tag. Overlapping rows get a light bracket in the margin instead of a footnote.
- Hover/JS: highlight row, show P(rank = k) only if not drawn. HOP: Hullman et al. title is literally "...inferences about reliability of variable ordering"; HOPs beat error bars and violins for two or three quantities. "Reshuffle" plays draws at 400ms (their frame time); Padilla recommends 400 to 500ms. Caveat from Wilke: draws shown must be representative, so sample draws at fixed quantiles of the rank distribution or use all draws, not 10 random ones.
- Caution on profile switching: re-sort with a short slide (200ms) but keep intervals static; Wilke (citing Kale 2018) says smooth transitions make probability judgments harder.

### (b) Per-suite forest plot, ratios to 1.0, noise band
- Why: Wilke Fig 16.8 plots estimates relative to a reference with CIs of the difference and warns that overlap rules of thumb are unreliable; the CI of the ratio itself against 1.0 is the right object. FT Visual Vocabulary: deviation charts "emphasise variations from a fixed reference point"; dot plot "change or range across multiple categories". Datawrapper range plots label range ends directly inside the chart, which is the pattern for the right-gutter text.
- Static SVG: log x axis (0.5x and 2x equidistant), reference at 1.0, band `rect` from 1-A/A to 1+A/A at 8 to 12% ink. Rows grouped by suite with small caps suite headers; sorted by ratio within suite. Dot r=4, CI as 2px line with no caps (Wilke: caps are taste, omit in dense figures). Label "A/A noise" once, inside the band, top row only.
- Numbers: gutter text per row, `0.62x  0.58 to 0.67`, tabular. Caption: "95% bootstrap CI, 12 paired rounds, band is Pi vs Pi."
- Touch: dot filled if CI clears the band, hollow if inside it. Reading cost falls to "solid or hollow". Arrowhead where the CI is clipped by the axis.
- Hover: highlight row across suites; tooltip adds the per-round sparkline only if (c) is not on screen.

### (c) Paired rounds: distribution and drift
- Why: raincloud paper (Allen et al.) wants raw points, density, and a summary with minimal redundancy, but also says rainclouds fit poorly when waves/points are extreme; with 12 points a density is overfit, so keep the "rain" and drop the "cloud". Tufte's sparklines are "word-sized" graphics with a grey normal-range band so deviations outside the band jump out (glucose example). The A/A band is exactly that band.
- Static SVG: row per harness. Left: strip of 12 dots on the shared log ratio axis (jittered vertically by round parity or a beeswarm), median tick, 95% CI line. Right: 120x24 sparkline, x = round 1..12, y = ratio, grey A/A band, first and last point accented; Tufte advises a roughly 45-degree "lumpy" aspect so slopes read.
- Pairing: hover a dot and its round lights up in every row (vertical guide through the sparklines); a click on the row expands a Datawrapper-style arrow plot (Pi value to harness value, one arrow per round) so the pairing is visible without a data table. Datawrapper: arrow plots emphasise change between values more than the values themselves.
- Numbers: median ratio inline at the row end; drift stat only if the pipeline computes one (otherwise let the eye do it, with the band).
- Touch: "Shuffle test". Tufte shows the real series next to ten randomly reordered ones: "Hard to see the difference between real and random", an "Interocular Trauma Test", and warns of perceptual streak bias. With only 12 rounds this guards against reading drift into noise. Render real row plus 9 shuffled sparklines on button press.

### (d) Four memory kinds per harness
- Why: small multiples with a shared scale (Tufte sparkline small multiples; FT dot strip). Shared log axis keeps lengths comparable across kinds; consistent row order lets the eye follow a harness across panels. Avoid lines across the four kinds (they imply ordered categories).
- Static SVG: 4 panels side by side, harness rows aligned, axis drawn once at the bottom, A/A band repeated per panel (thin). Panel header: kind name and Pi's absolute value ("Pi: 148 MB") as direct denominator context. [INFERENCE: denominator context helps readers; not tested here.]
- Numbers: point value beside the dot at 11px; CI is the bar; exact CI in hover to avoid 4 x H extra labels.
- Touch: identical x range in all panels; anything beyond range gets an arrow and its number so no panel quietly rescales.

### (e) Bootstrap distribution of one ratio
- Why: Kay et al. (CHI 2016) report quantile dotplots reduced variance of probability estimates by about 1.15x versus density plots. Wilke Ch.16: use a small to moderate number of dots; 50 dots (2% each) is accurate but harder to read, 10 dots conveys the answer fastest, so 20 is a reasonable middle. [INFERENCE: pick 20 for width fit; test with 50.] Padilla: frequency framing ("1 out of 10") beats percentages; Fernandes et al. found a hybrid of density and 50%/95% intervals gave better decisions after practice.
- Static SVG: dots at quantiles (i - 0.5)/N, greedy-binned and stacked so stacks fit the plot height (ggdist picks binwidth automatically). Dots left of 1.0 take the focal colour, right neutral, those inside the A/A band get a ring. Under it: 50/80/95 interval bars, median tick.
- Number: caption "In 19 of 20 reruns, Pi comes out ahead", computed by counting dots, so the sentence and the picture agree by construction.
- Touch: on first view the dots fall in one by one with a 25ms stagger (about 0.5s for 20), echoing Padilla's idea of each draw leaving a trace that builds a static display. Afterwards it is static. Because dots are quantiles not random draws, the pile is representative (Wilke's HOP caveat does not apply).

### (f) KPI tiles with a tiny chart
- Why: Tufte: a sparkline is a "dataword", a number made richer by context; his critique of a red dot beside a bar chart ("wastes space") argues for a tiny chart that adds information the number lacks. Few's bullet graph: one featured measure, a comparative tick, and 2 to 5 qualitative ranges in intensities of one hue, designed to replace gauges on dashboards.
- Tile: label (CPU, wall, memory, instructions), big ratio in tabular numerals, below it a 100x14 bullet-style strip: A/A band as the single quiet range, Pi tick at 1.00, point + 95% interval. Phrase the delta in words ("a bit under Pi"), not colour. Few's bullet default: dot instead of bar when the scale does not start at zero (log ratio does not).
- Anti-redundancy: tiles are the family-level summary only; suite-level ratios live in (b). Do not repeat the tile's number in a table.
- Touch: interval strip grows outward from 1.00 on load (300ms). No count-up numbers; The Verge on NYT needle jitter shows how invented motion reads as data.
- Style: Vercel Geist is the sleek baseline: 10-step gray scale with explicit roles (100 background, 400 border, 900 secondary text, 1000 primary text), one border per divider, Geist Mono/tabular for numbers. Linear: reduce chrome, raise contrast of content, LCH theme generation.

## Tone notes (light-hearted, Pi gets props)
Captions that fit the stat strip: "Pi sits at 1.00x by definition. The shaded band is Pi racing itself, so anything inside it is a tie." and "Hollow dots: too close to call." Keep jokes in captions and empty states, never in axis labels or numbers.

## Sources opened (all fetched in this session unless noted)
- ggdist slabinterval vignette (Kay): https://mjskay.github.io/ggdist/articles/slabinterval.html (gradient plots, quantile dotplots, rain clouds, CCDF).
- Wilke, Fundamentals of Data Visualization, Ch.16: https://clauswilke.com/dataviz/visualizing-uncertainty.html (frequency framing, graded error bars, deterministic construal, HOP, contrasts to a reference). Ridgeline and raincloud chapters themselves not opened; only the ridgeline mention inside Ch.16.
- Allen et al., raincloud plots: https://wellcomeopenresearch.org/articles/4-63 (Tufte data-ink as cited there).
- Kay et al. 2016 abstract: https://idl.uw.edu/papers/when-ish-is-my-bus (1.15x variance claim).
- Hullman, Resnick, Adar 2015: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0142444 (HOP; 400ms frames; 96 viewers, most underestimated Pr(B>A)).
- Padilla, Kay, Hullman prepress chapter: http://space.ucmerced.edu/Downloads/publications/Uncertainty_Visualization_Padilla_Kay_Hullman_2020.pdf (the Wiley URL returned 403).
- Datawrapper: arrow and range plots https://www.datawrapper.de/blog/new-arrow-and-range-plots; dark mode https://www.datawrapper.de/blog/dark-mode-for-embedded-visualizations (the /blog/dark-mode URL was 404); colour guide https://www.datawrapper.de/blog/colors-for-data-vis-style-guides (grays, opacity, dark-mode section; also quotes on NYT and Pudding palettes).
- FT Visual Vocabulary README: https://github.com/Financial-Times/chart-doctor/tree/main/visual-vocabulary
- Tufte, sparkline theory: https://www.edwardtufte.com/notebook/sparkline-theory-and-practice-edward-tufte/
- Few, Bullet Graph spec: https://www.perceptualedge.com/images/Bullet_Graph_Specification.pdf
- Observable Plot tip mark docs (via GitHub raw; the observablehq.com site returned 429): https://raw.githubusercontent.com/observablehq/plot/main/docs/marks/tip.md (tip + pointer for hover). Gallery not opened.
- Distill, Communicating with Interactive Articles: https://distill.pub/2020/communicating-with-interactive-articles (details-on-demand = tooltip; "not everything needs to be interactive"; animation suits uncertainty and state change).
- The Verge on NYT needle jitter: https://www.theverge.com/2016/11/8/13571216/new-york-times-election-forecast-jitter-needle
- Vercel Geist: https://vercel.com/geist/colors.md and https://vercel.com/geist/typography.md
- Linear redesign: https://linear.app/now/how-we-redesigned-the-linear-ui
- MDN font-variant-numeric: https://developer.mozilla.org/en-US/docs/Web/CSS/font-variant-numeric

Not opened: The Pudding and NYT Upshot pages themselves (cited only via Datawrapper, Padilla and The Verge), Stripe dashboards, Few's data-ink writings. Any claim about those is [INFERENCE] or second-hand as stated.
