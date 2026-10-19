# Math typesetting for "How a number is made"

A scratch demo built with KaTeX 0.19.0 was screenshotted in headless Chrome (light and dark), and a real hover was driven through CDP. Everything marked "measured" below comes from that run.

## Recommendations for pi-arena

1. **Pre-render at build time with KaTeX `renderToString` in Node. Ship zero KaTeX JS.** The Node docs say the client needs only the CSS and fonts, "you do not need to include `katex.js` on the client" (katex.org/docs/node). Measured: the whole demo page (4 derivations, SVG chart, CSS) is 31.7 KB raw, 4.3 KB gzipped. The page then works with JS off, has no flash of raw TeX, and the math cannot break at runtime.
2. **Keep `output: 'htmlAndMathml'` (the default).** Measured for the score equation: html-only 4.9 KB, mathml-only 1.7 KB, both 6.6 KB (1.0 KB gzipped). The MathML half is visually hidden and read by screen readers; the HTML half is `aria-hidden`. The LaTeX source is also embedded as `<annotation encoding="application/x-tex">`, so copy-paste tools can recover it.
3. **Do not use native-only MathML as the primary renderer.** MathML Core is interoperable in all major engines since Jan 2023 (web.dev, Igalia), and Igalia says CSS can "highlight or style various parts of an equation". But layout depends on installed math fonts: MDN says Cambria Math ships on Windows, STIX Two Math on macOS 13+, and Android and many Linux setups need extra fonts. For a page that publishes numbers and wants a polished look, KaTeX's pinned fonts win. [INFERENCE: the visual inconsistency across OSes is real but I did not test Firefox/Safari/Windows.]
4. **MathJax 4 is the wrong tool here.** v4 is Apache-2.0, npm unpacked 20 MB (`mathjax`) or 34 MB (`@mathjax/src`) vs KaTeX 4.0 MB unpacked. Its a11y wins (Explorer on by default) matter for large documents; assistive-MathML is off by default in v4 (docs.mathjax.org). This page has 5 formulas. [INFERENCE: MathJax Node pre-render works but I did not verify, the server docs URL 404'd.]
5. **One class per term drives colour on the KaTeX spans AND the chart marks.** Wrap operands with `\htmlClass{t t-x}{...}`, give the SVG mark the same classes, and colour both via `currentColor`. Hover/focus linking is then ~7 lines of CSS with `:has()`, no JS. Verified: hovering the `x` term set opacity 0.3 on the CI mark and 1 on the `x` mark.
6. **Add keyboard/touch chips for the linked terms** (buttons that carry the same `t t-x` class). KaTeX spans cannot be focusable (no way to inject `tabindex`), and Safari does not focus buttons on tap, so tap needs ~10 lines of JS toggling a `data-focus` attribute. Treat hover as enhancement; the page must read fully with no interaction.
7. **Do not hide derivation lines behind steps.** Show symbolic / substituted / result always. Use the dimming effect (Distill greys out whole equation parts; Victor: the text "can be read like normal text", reader "is not forced to interact") for emphasis, not for gating content.
8. **Vendor only what loads.** Measured via `document.fonts`: this page loads 4 woff2 files only (Main-Regular 26.3 KB, Main-Bold 25.3 KB, Math-Italic 16.4 KB, Size1-Regular 5.5 KB) = **73.5 KB**. Full `dist/fonts` is 1.2 MB (ttf+woff+woff2); woff2-only is 260 KB. Copy `katex.min.css` (24.8 KB, 3.6 KB gzipped) + `fonts/*.woff2`. The `@font-face` rules list woff2 first and browsers fetch lazily, so shipping all 20 woff2 (260 KB) costs nothing at load; trim only if repo size matters. MIT licence (LICENSE: "Copyright (c) 2013-2020 Khan Academy and other contributors"), keep the notice.

## Styling spec

**Type.** Body 17-18 px / 1.6, sans. KaTeX defaults to `font: normal 1.21em KaTeX_Main` with `line-height: 1.2` (katex.css; docs say 1.21x makes scripts readable). On a 17 px body that is 20.6 px, which looked too big next to sans text. Use `.katex { font-size: 1.1em }` (docs show this exact override): measured 18.7 px math, 22.4 px math line-height. Inline math stays 1.1em too, so `R`, `f`, `s` in prose match the display versions. Expect a serif/sans mix; KaTeX cannot use the page font because its glyph metrics are bound to its own fonts.

**Block layout, one `aligned` environment per formula so `=` stacks:**
```
R  = median(x) / median(y)      symbolic: ink, only operands coloured
   = 412.0 / 308.0              substituted: same structure, same colours
   = 1.338                      result: \mathbf, colour of its term (or ink for r)
```
- Left-align (`.katex-display > .katex { text-align:left }`), 3 px left rule in `--rule`, 1 rem padding-left. Left alignment keeps the three lines reading as a derivation; centred looks like a slide.
- Row gap `\\[1.1em]` when a row contains a fraction (default row gap was visibly tight; KaTeX docs on Common Issues say `\\[0.1em]` adjusts row spacing).
- Display margin `.6em 0` instead of default `1em 0`; `overflow-x:auto` on `.katex-display` (docs show `overflow: auto hidden`).
- Write the unit once in prose ("CPU ms"), not in every `\text{ms}`; the numbers carry the colour.
- Long lines: measured, the percentile-interval line is ~490 px wide at 18.7 px, so it overflows a 360 px phone. Split it into two `aligned` rows (definition, then numbers). KaTeX display mode never auto-breaks (options doc); the issues doc gives CSS to allow it, but manual `\\` is cleaner.
- Colour only operands, never `=` or `+` (wrapping a binary operator changes TeX spacing). Use the `\T{key}{...}` macro below so authors never type class strings.

**Colour tokens** (contrast computed by me with the WCAG formula against the bg; all pass 4.5:1):

| term | light on `#fbfaf7` | dark on `#16181d` | mark in chart |
|---|---|---|---|
| ink | `#1f2328` 15.1 | `#e6e8eb` 14.5 | |
| `x` candidate | `#0b6e8a` 5.6 | `#4fc3e0` 8.6 | dot / bar |
| `y` Pi | `#b4540a` 4.8 | `#f2a05a` 8.4 | dot / bar |
| interval `[L,U]` | `#6a3fb5` 6.7 | `#b79cf0` 7.6 | solid thick segment |
| floor `f` | `#8a6d00` 4.7 | `#e3c158` 10.2 | dashed band, 12-20% tint |
| score `s` | `#1a7f45` 4.8 | `#5fd08a` 9.2 | |

- Blue vs orange is the safe pair. Purple interval vs blue `x` can blur for some colour-blind readers [INFERENCE], so never rely on hue alone: the interval is a solid segment, the floor a dashed band, and the chips carry words. BetterExplained's own top feedback on colourised equations was "accessible versions for color blind readers" (betterexplained.com/articles/colorized-math-equations).
- Dark mode: KaTeX paints with `currentColor`, so set `color` via CSS variables under `@media (prefers-color-scheme: dark)` and nothing else changes. Do NOT use `\textcolor{var(--x)}`: measured, KaTeX throws `Invalid color: 'var(--c)'` and inline hex cannot flip with the theme. Verified the dark screenshot renders correctly.
- Use at most 5 hues in one block; BetterExplained and Riffle both colour each *meaning*, not each symbol.

## The colour-code + hover-link technique (tested)

Build script (Node, runs at build time):
```js
import katex from 'katex';
const opts = {
  displayMode: true, output: 'htmlAndMathml', throwOnError: true,
  // \htmlClass needs trust; allow only our own class pattern
  trust: c => c.command === '\\htmlClass' && /^t( t-[a-z]+)?$/.test(c.class),
  // \htmlClass trips the htmlExtension strictness warning; silence only that one
  strict: code => code === 'htmlExtension' ? 'ignore' : 'error',
  macros: { '\\T': '\\htmlClass{t t-#1}{#2}', '\\med': '\\operatorname{median}' },
};
katex.renderToString(String.raw`\begin{aligned}
  R &= \frac{\T{x}{\med(x)}}{\T{y}{\med(y)}} \\[1.1em]
    &= \frac{\T{x}{412.0}}{\T{y}{308.0}} \\[1em]
    &= \T{r}{\mathbf{1.338}} \end{aligned}`, opts);
```
Notes from running it: `\class` does not exist in KaTeX (parse error), the equivalent is `\htmlClass` (docs, Common Issues). With `strict:'error'` and no handler, `\htmlClass` fails with `[htmlExtension]`. `\htmlData{term=x}{...}` emits `<span class="enclosing" data-term="x">` on a wrapper span, not on the class span, so selectors mixing the two silently miss; use classes only. The class lands on the HTML half only; the MathML half keeps no class (class text appears only inside the `<annotation>`).

CSS (the same `.t-x` colours the KaTeX span and the SVG mark):
```css
:root { --c-x:#0b6e8a; --c-y:#b4540a; --c-ci:#6a3fb5; --c-f:#8a6d00; --c-s:#1a7f45; --c-r:var(--ink); }
@media (prefers-color-scheme: dark) { :root { --c-x:#4fc3e0; --c-y:#f2a05a; --c-ci:#b79cf0; --c-f:#e3c158; --c-s:#5fd08a; } }
.t-x{color:var(--c-x)} .t-y{color:var(--c-y)} .t-ci{color:var(--c-ci)} .t-f{color:var(--c-f)} .t-s{color:var(--c-s)} .t-r{color:var(--c-r)}
.t { transition: opacity .12s; border-radius:.2em }
svg .t { fill: currentColor; stroke: currentColor }          /* marks inherit the term colour */
svg .t-ci { fill:none } svg .t-f { fill-opacity:.12; stroke-dasharray:3 3 }
/* dim every linked thing except the hovered term; one line per term */
.how:has(.t-x:is(:hover,:focus-visible)) .t:not(.t-x),
.how:has(.t-y:is(:hover,:focus-visible)) .t:not(.t-y),
.how:has(.t-ci:is(:hover,:focus-visible)) .t:not(.t-ci),
.how:has(.t-f:is(:hover,:focus-visible)) .t:not(.t-f),
.how:has(.t-s:is(:hover,:focus-visible)) .t:not(.t-s) { opacity:.3 }
@media (prefers-reduced-motion: reduce) { .t { transition:none } }
.katex { font-size:1.1em }
```
```html
<section class="how">
  <div class="eq"><!-- pre-rendered KaTeX block --></div>
  <svg role="img" aria-label="Ratio 1.338, interval 1.29 to 1.39, floor 0.983 to 1.017">
    <rect class="t t-f" .../> <line class="t t-ci" .../> <circle class="t t-r" r="6" .../>
  </svg>
  <button class="chip t t-x">candidate x</button> <!-- keyboard/touch entry point -->
</section>
```
`:has()` scoping: put the `.how` wrapper per worked step, not around the whole page, so hovering `x` in step 1 does not dim step 4. [INFERENCE: I did not check `:has()` Baseline status; the MDN page I opened did not state it. Chrome headless handled it.]

## Substituting the run's real numbers

- Generate the substituted line from the same data that draws the chart (build script reads the JSON, formats once, feeds both TeX and SVG). Then the number in the equation and the mark cannot disagree.
- Keep the substituted line structurally identical to the symbolic line (same `\T` keys). Riffle's Fourier post pairs each prose clause with a highlighted part of the DFT; BetterExplained says the "colors, text, and equations are themselves a diagram. Our eyes bounce back and forth".
- Show intermediate numbers for `f` (`max(0.004, 0.017, 0.009)`), because that is the line that tells a reader why the floor is that size. For `s`, substitute `r` inside `\log_2` and then show the result.
- Print fewer digits in the equation than in the data table (3 sig figs), since the derivation is for understanding. [INFERENCE: design choice.]

## Pre-render vs client, decision table

| | build-time `renderToString` | client `auto-render` / `katex.render` |
|---|---|---|
| JS shipped | 0 KB | `katex.min.js` 272.9 KB raw, 76.5 KB gzip |
| works with JS off | yes | no |
| layout shift / FOUC | none (font-display: block avoids FOUT but can hide text briefly; use `katex-swap.min.css` if you prefer swap) | raw TeX flashes |
| hover link / dark mode | pure CSS | same |
| content in the HTML | math is real DOM text + MathML | TeX source until JS runs |
| downside | rebuild on change | |

Client-side wins only if readers edit equations live. They don't here. If a "live" slider is ever added, re-render only the substituted line client-side with the same macros (load `katex.min.mjs` lazily).

## Other prior art and what it supports

- **Riffle / BetterExplained:** colour each *meaning* across prose, diagram and formula (the "colorized math" approach). Riffle's post uses a coloured diagram derived from the DFT with the sinusoid-spinning picture. Math For Love's reaction: without colour "it would be really hard to parse that particular meaning inside the equation".
- **Distill, "Why Momentum Really Works":** formulas are baked KaTeX (MathML + `application/x-tex` annotation in the page I opened), live sliders sit in the text ("Step-size α = 0.02"), and at least one equation greys out context with `\color{#AAA}{\color{black}{R^{k}}...}`. That grey-out is the same dimming idea as the `:has()` rule above. I did not find explicit hover links from equation terms to figures in the part I read.
- **Bret Victor, Explorable Explanations:** the reader nudges the author's own numbers, the explanation reads as plain text without interacting, and "the explorable is integrated with the explanation". Maps to: static three-line derivation first, optional hover.
- **Seeing Theory (Brown):** has an Interval Estimation chapter and "The Bootstrap" section, built in D3. Site is marked archived. Precedent for explaining the bootstrap visually; I did not read the chapter's text or its math rendering.
- **3Blue1Brown / manim:** the idiom is `MathTex(..., tex_to_color_map=..., substrings_to_isolate=...)` and `TransformMatchingTex` to morph one equation into the next (docs.manim.community). The static-web analogue is: same term keeps the same colour across symbolic and substituted lines, so the eye tracks it. Animated morphs are not needed for a static dashboard.

## Accessibility checklist

- Keep MathML in the output (`htmlAndMathml`). Optional: `katex/contrib/copy-tex` (1.7 KB min) copies selected math as LaTeX; `contrib/render-a11y-string` (8.6 KB min) generates plain-English strings for `aria-label` fallbacks if you ever need them.
- Each chart `<svg>` gets `role="img"` and an `aria-label` that states the numbers; the equation block already carries its numbers in MathML.
- Chips are real `<button>`s with `aria-pressed` once JS toggling exists. Hover-only is not acceptable (touch, keyboard).
- Never encode meaning by colour alone (see palette notes). `prefers-reduced-motion` disables the opacity transition.
- DOCTYPE required: KaTeX docs warn quirks mode breaks rendering, even inside iframes.

## Sources actually opened

- KaTeX options (`trust`, `strict`, `output`, `displayMode`, `minRuleThickness`): https://katex.org/docs/options
- KaTeX Node usage: https://katex.org/docs/node
- KaTeX browser / self-hosting / font-display: https://katex.org/docs/browser
- KaTeX fonts (1.21x default, `.katex{font-size:1.1em}`): https://katex.org/docs/font
- KaTeX security (`trust`, `\htmlClass` gating): https://katex.org/docs/security
- KaTeX common issues (`\htmlClass` equivalents, scrollable display, line breaks): https://katex.org/docs/issues
- KaTeX supported functions (read first 95 of 667 lines only): https://katex.org/docs/supported
- Local `npm i katex@0.19.0` (sizes, LICENSE MIT, CSS defaults, fonts) and `npm view mathjax @mathjax/src` (versions, Apache-2.0, unpacked sizes)
- MathJax v4 what's new: https://docs.mathjax.org/en/latest/upgrading/whats-new-4.0.html and https://docs.mathjax.org/en/latest/upgrading/whats-new-4.0/output.html
- Igalia, MathML in Chrome 109: https://www.igalia.com/2023/01/10/Igalia-Brings-MathML-Back-to-Chromium.html
- web.dev January 2023 ("interoperable across all the major engines"): https://web.dev/blog/web-platform-01-2023
- MDN MathML overview: https://developer.mozilla.org/en-US/docs/Web/MathML ; fonts guide: https://developer.mozilla.org/en-US/docs/Web/MathML/Guides/Fonts
- W3C MathML Core editor's draft: https://w3c.github.io/mathml-core/ (first 300 of 6614 lines)
- Riffle, Understanding the Fourier transform (Wayback copy): https://web.archive.org/web/20130117032507/http://www.altdevblogaday.com/2011/05/17/understanding-the-fourier-transform/
- BetterExplained, Colorized Math Equations: https://betterexplained.com/articles/colorized-math-equations/
- Math For Love, Use Color!: http://moms4math.org/index-1567.html
- Distill, Why Momentum Really Works: https://distill.pub/2017/momentum/ ; Distill guide (says use MathJax or KaTeX): https://distill.pub/guide/
- Bret Victor, Explorable Explanations: https://worrydream.com/ExplorableExplanations/
- Seeing Theory: https://seeing-theory.brown.edu/
- manim MathTex: https://docs.manim.community/en/stable/reference/manim.mobject.text.tex_mobject.MathTex.html
- MDN `:has()`: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:has

Tried and failed: caniuse.com/mathml (HTTP 406), themathdoctors colour page (404), a guessed BetterExplained URL (404), docs.mathjax.org/en/latest/server (404). No browser-support table beyond web.dev/Igalia/MDN was consulted.
