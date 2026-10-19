# pi-arena: Pi brand cues, viral benchmark patterns, recommendations

Legend: **[V]** verified in a fetched source (URL in section 4). **[INFERENCE]** my guess. **[GAP]** could not be fetched.

---

## PART 1: pi.dev brand (all hex values read from https://pi.dev/style.css)

### 1.1 Palette
Dark is the default: `:root` sets `color-scheme: dark`; `:root[data-theme="light"]` overrides it. An inline script picks light/dark/system from `localStorage["pi:theme"]` and the `prefers-color-scheme` query. The footer has an Auto / Light / Dark switch. **[V]**

Named brand colours (defined once, used in both themes):

| token | hex | role |
|---|---|---|
| parchment | `#dacbc2` | light page bg (deep) |
| moonstone | `#ebe7e4` | light canvas, dark-mode text |
| driftwood | `#5c5752` | light muted text |
| evening-blue | `#252f3d` | light text, dark panel-soft |
| tidal-blue (thread-blue) | `#4b607c` | light accent |
| accent-blue | `#6a9fcc` | dark accent, hero subtitle accent |
| terracotta | `#844f3b` | warm accent |
| terracotta-light | `#b86b52` | light 2nd chart series |
| sunkissed | `#e1b06e` | warm highlight |
| sage | `#a3a473` | tertiary |
| warm-black / warm-white / cool-white | `#13110f` / `#f3f2f0` / `#f0f2f3` | neutrals |
| success / warning / error (dark stops) | `#5db87a` / `#e8993a` / `#e8704f` | status |

Dark theme tokens: bg-deep `#0d1116`, bg-canvas `#161d27`, panel `#212730` (panel-base), panel-soft `#252f3d`, line `#495059` at 50% alpha, line-strong `#757d89`, text `#ebe7e4`, copy `#ebe7e4` at 75%, text-base `#d5d8db`, muted `#9fa4ab`, accent `#6a9fcc`, 2nd chart series `#8f3222` (rust).
Light theme tokens: bg-deep `#dacbc2`, bg-canvas `#ebe7e4`, panel `#f4f2f0`, panel-soft `#eef1f3`, line `#8b847d` at 35%, text `#252f3d`, copy `#384251`, muted `#5c5752`, accent `#4b607c`, 2nd chart series `#b86b52`.
Charts: `--chart-series-1: var(--accent)`, `--chart-series-2: var(--accent-rust)`, gridlines are the text colour at about 10-12% alpha. **[V]**
The accent is a blue-grey "thread" (an active-stripe gradient is 62% accent, 38% thread-blue). It is calm, not neon. Warm parchment/moonstone grounds the light theme. **[V]**

### 1.2 Fonts
- Serif display + body: **"Plantin MT Pro"** (variable woff2, weight axis 200-800, upright + italic), fallbacks `"Plantin MT Std", Plantin, Georgia, serif`. Body copy weight 440-450, size 1rem, line-height 1.45-1.55. `font-display: block`. **[V]**
- Mono: **"Commit Mono"** (OTF weights 300 / 400 / 700), stack `"SFMono-Regular", ui-monospace, Menlo, Monaco, Consolas, monospace`. **[V]**
- Accent mono: **"Departure Mono"** (400, a pixel-style font, woff2). Used via `--accent-mono` for labels, form labels, nav-ish and "Fig. 01 | DOOM EXTENSION" style captions. **[V]**
- Labels are uppercase with wide tracking (`letter-spacing` 0.08em, 0.12em, 0.14em; 43 uppercase rules in the CSS). **[V]**
- Title size: `clamp(2.5rem, 5vw, 4.25rem)` desktop, `clamp(2.15rem, 10vw, 3rem)` mobile. Hero subtitle `clamp(2rem, 10.5vw, 2.65rem)` at line-height 1.02. **[V]**

### 1.3 Logo and wordmark
- Mark is a blocky pixel "pi" built from three filled rectangles on a 560x560 viewBox (`/favicon.svg`): `M420 280H280V140H0V0H420V280Z`, `M560 560H420V280H560V560Z`, `M140 560H0V140H140V280H280V420H140V560Z`. **[V]**
- Fill is `#111111` on light and `#f6f6f6` on dark through an inline `prefers-color-scheme` media query. Monochrome only, no gradient. README uses `https://pi.dev/logo-auto.svg` at width 128. **[V]**
- Nav/footer offer "Copy SVG", "Download SVG", "Press Kit". **[V]**
- Home hero builds the logo from a pixel board: 8 columns x 9 rows of 20px cells. **[V]**
- Name is plain "Pi" in the serif. The `<title>` is just `Pi`. **[V]**

### 1.4 Layout
- `.page-shell` width `min(100%, 96rem)`, padding `1.5rem 2rem 4rem`, two-column grid `minmax(0, 1.4fr) minmax(22rem, 36rem)`, gap `clamp(2.5rem, 4vw, 5rem)`. Reading pages use 48rem; prose uses 44-46rem max-width. **[V]**
- Content shell padding `clamp(1rem, 3vw, 2rem) 2rem 4rem`; card grid gap 0.75-1rem; card padding `clamp(0.85rem, 1.4vw, 1.15rem)`. **[V]**
- Faint 20px page grid: `--page-grid-cell: 20px`, minor/major/cross lines at about 1%, 2.6%, 7.5% alpha (dark) and `#252f3d08 / 12 / 1d` (light). Looks like graph paper. **[V]**
- Radius is mostly 0 (17 of ~21 rules); only pills (999px) and one 4px. Square, flat, hairline borders. **[V]**
- Hover lift is 0 to -1px. Motion uses `cubic-bezier(0.22, 1, 0.36, 1)`, durations 280-1540ms. **[V]**
- Nav: sticky bar, 2.44rem menu toggle, bracketed buttons (`--bracket-button-*`, text like `[ Copy ]`), items Documentation, Changelog, Models, Packages, Radius, plus GitHub/npm/Discord/X. Mobile uses a bottom sheet (`nav-sheet`, max 36rem). Footer: "Earendil Inc. & Contributors", "MIT License", "pi.dev domain graciously donated by exe.dev". **[V]**
- "Crooked mode": a toggle that rotates the hero `1.3deg` (`--recording-crookedness`) with a "Revert" button. Playful, deliberately imperfect. **[V]**

### 1.5 Terminal / TUI aesthetic
Terminal frames on the home page show mono text, hairline rules above and below an editor line, a block cursor, a footer line like `~/your-project (main)` with `0.0%/1.0M (auto)` and `(anthropic) claude-opus-5-5 • medium`, slash commands (`/model`, `/tree`, `/reload`), `<kbd>` shortcuts. "Fig. 01 | DOOM EXTENSION" captions. A line reads `$ scroll to continue`. **[V]**
PiG's own terminal palette (pi-in-go.dev/_next CSS): text `#d4d4d4`, accent `#8abeb7`, border `#5f87ff`, dim `#666666`, success `#b5bd68`, warning `#ffff00`, user-bg `#343541`, tool-bg `#283228`, selected-bg `#3a3a4a`, editor rule `#505050`. **[V]**

### 1.6 Tone of voice (verbatim, https://pi.dev/)
- "There are many agent harnesses but this one is yours" (also the og:image alt text).
- "Pi is a minimal agent harness. Adapt Pi to your workflows, not the other way around."
- "Pi ships with powerful defaults but skips features like sub-agents and plan mode."
- "Primitives, not features." / "Change the harness, not your workflow" / "What we didn't build"
- "Pi isn't a sealed product."
- "No sub-agents / No permission popups / No plan mode / No built-in to-dos / No background bash" with a one-line alternative each, e.g. "Use tmux. Full observability, direct interaction."
- "Don't want to build it? Ask Pi to build it for you."
- Announcement bar: "People of Pi: We've shipped Pi 1.0 with Pi Durable. Go make them yours."
- Register: second person, short declarative sentences, plain nouns, no hype adjectives, no emoji, a dry joke allowed. Slash commands and flags are inline code. **[V]**

### 1.7 What Pi says it values
- README: "Pi is a minimal, extensible agent harness that you can make your own." **[V]**
- Mario Zechner, 2025-11-30: "My philosophy in all of this was: if I don't need it, it won't be built." **[V]**
- Same post: "I'm a simple boy who likes simple, predictable tools." and "context engineering is paramount." and "I want to inspect every aspect of my interactions with the model." and "a cleanly documented session format I can post-process automatically". **[V]**
- On dislikes: "The system prompt and tools also change on every release, which breaks my workflows." "Also, it flickers." **[V]**
- Values to echo: observability, stable and predictable behaviour, small surface, no hidden injection, token efficiency ("very token efficient due to its minimal system prompt" on pi.dev), honesty about limits ("best-effort ... not for accurate billing" in his post). **[V]**

### 1.8 PiG (pi-in-go.dev) cues, for the ecosystem link
- Light `#FFFFFF` bg, ink `#18302C`, brand green `#127560` (buttons, borders, icon fill; `--primary` `#008567`). Dark: page `#101C1A`, surface `#172824`, line `#30463E`, ink `#E8F4F0`, green `#25C99B`, subtle `#A0B5AC`. **[V]**
- Pixel-art pig logo (`pig-pixel-green-display.png`, 222x180), wordmark "PiG" with a green period ("logo-period"). **[V]**
- Tagline "A faithful Go implementation of Pi." Eyebrow "THE PI ECOSYSTEM, IN GO". "Compatibility is a feature." "Tracks Pi behavior through explicit parity evidence." Section labels like "01 / WHY PIG EXISTS". Arial body, monospace terminal blocks. **[V]**
- Not Pi's serif: PiG's own site uses green + Arial. The arena should sit between them: Pi's dark neutrals and type, with the PiG green only as a "PiG" series colour. **[INFERENCE]**

---

## PART 2: what makes benchmark leaderboards spread

### 2.1 Observed patterns (with source)
1. **Rank is an interval, not a point.** LMArena's open ranking lib outputs `ratings, rating_lower, rating_upper` from a Bradley-Terry fit with `significance_level=0.05` (95% CI); sample output shows e.g. gemini-2.5-pro 1124.07 [1117.61, 1130.53]. Artificial Analysis labels its image arena "with 95% confidence intervals". Terminal-Bench CI posts "accuracy ± 95% CI". **[V]** (arena-rank README, AA home, tbench SUBMIT.md). The arena.ai UI itself returned HTTP 403 / empty shell, so the "Rank (UB)" and "tie" column behaviour is **[GAP]**; my recollection is that rows within CI overlap share a rank. **[INFERENCE]**
2. **One headline number per row, then cost beside it.** Aider: "Percent correct" plus "Cost" plus exact "Command" column (`aider --model openai/gpt-5`), edit-format %, and "last updated November 20, 2025". Terminal-Bench columns: RANK, MODEL, AGENT, RESOLUTION RATE, COST, TOKENS. AA charts "Intelligence Index vs. Cost per Task". **[V]**
3. **Reproduction command on the row.** Aider shows the CLI per row; Terminal-Bench README gives `harbor run -d terminal-bench/terminal-bench@latest --agent ... --model ...`. **[V]**
4. **Share/export affordances in the page itself.** SWE-bench viewer has "Light", "Selection", "JSON", "PNG", "Copy Link" controls, a "Compare results" selection flow, quick-select buttons (top 10, top 20, all, open weights), and 13 chart views (bar, scatter, vs cost, vs release date, step distributions). **[V]**
5. **Provenance badges.** SWE-bench legend: "Open-weights model" and "Run performed or directly checked by the SWE-bench team". **[V]**
6. **Social cards are 1200x630.** tbench.ai ships separate `terminal-bench-og-1200x630.png` and `terminal-bench-twitter-1200x630.png` with `twitter:card: summary_large_image`. AA ships `opengraph-image.png` at 1200x630. pi.dev ships `/social.png` at 1200x630 with alt text equal to the tagline. **[V]**
7. **Dated, tagged, versioned.** Terminal-Bench submissions are files named `2026-08-26-<model>-<effort>-<agent>.json`; dataset has tagged releases ("4.0"). AA names "Coding Agent Index v1.5" with a Version History section. Aider has a "Scores by release date" page. SWE-bench keeps a dated News list. LMArena has a "Leaderboard Changelog" page (title confirmed; content **[GAP]**). **[V]**
8. **Methodology is a first-class page.** AA has a methodology tree (scope, definitions, "equal-weight average of DeepSWE v1.1, Terminal-Bench 4.0 and SWE-Atlas-QnA", internet isolation, reward-hacking, safety refusals). Aider has "Benchmark notes" (pricing is "best efforts"). Terminal-Bench: pinned dataset version, no timeout overrides, every task at least 5 trials, errored trials count as reward 0, an LLM judge audits trajectories for "Harness cheating" and "Reward hacking", public trajectories. **[V]**
9. **Open the maths.** LMArena published `arena-rank` (Apache-2.0) and a dataset `arena-human-preference-140k` on Hugging Face. **[V]**
10. **Continuous benchmark framing.** "Terminal-Bench is a continuous benchmark", a "roadmap is publicly visible", Discord badge in README. **[V]**
11. **Badges in READMEs.** shields.io endpoint badges take JSON `{"schemaVersion":1,"label":"hello","message":"sweet world","color":"orange"}` fetched from your URL (`/endpoint?url=...&style=...`). Terminal-Bench's own README uses shields badges. **[V]** for schema (shields.io/badges/endpoint-badge search snippet, badges.cucumberstudio.com/endpoint); the shields doc page itself returned a 404 SVG when fetched.
12. **Hugging Face Space with a copyable table** was the original LMArena distribution channel (5k likes shown on the Space page). **[V]**
13. **Compact tables read on a phone.** Aider and Terminal-Bench use 4-6 columns. A tweet screenshot survives if rank, name, one number and its interval fit in about 390px wide. **[INFERENCE]**
14. **Dark first** is the default for tbench.ai (black badges `color=000000`, `labelColor=000000` in its README) and for pi.dev. arena.ai is the exception: `theme-color #FCFAF7` (warm cream light). **[V]** (README badge params, arena.ai meta). Spread driver is the pairing of a quotable number with a screenshot that looks designed, not the theme. **[INFERENCE]**

### 2.2 The LMArena credibility lesson (what to avoid)
- April 2025: Meta submitted "Llama-4-Maverick-03-26-Experimental", a chat-tuned non-public variant that ranked second; LMArena said "Meta should have made it clearer ... a customized model to optimize for human preference" and "style and model response tone was an important factor", released 2,000+ battles for review, updated policy, and added the public build. **[V]** (theregister.com 2025-04-08).
- "The Leaderboard Illusion" (arXiv 2504.20879): undisclosed private testing lets providers "test multiple variants before public release and retract scores"; Meta tested 27 private variants; closed models sampled at higher rates; Google/OpenAI get an estimated 19.2% / 20.4% of battles vs 29.7% for 83 open-weight models combined; "overfitting to Arena-specific dynamics rather than general model quality." **[V]**
- Lessons for pi-arena **[INFERENCE, derived from the above]**: (a) publish only builds that anyone can install, pinned by version and commit; (b) never allow private variants or retracted scores, so keep every run, including bad ones; (c) equal sampling budget per harness; (d) the owner of a harness (including PiG's author) is flagged as a conflict of interest, and results are reproducible from the repo; (e) tuning to the mock model or scenario set is the "style control" problem here, so state what the mock does and cannot measure; (f) A/A noise floors, because LMArena's own CI is what exposed over-claiming.
- Terminal-Bench shows the stricter model: unmodified dataset, errored trials = 0, judge for cheating, trajectories public. **[V]**

---

## PART 3: recommendations (static-site buildable, honest)

Priority order. Each item is plain HTML/CSS/vanilla JS, with SVG or PNG generated at build time.

1. **Hero = one measured sentence, one number, one interval.** Example: "PiG uses 0.xx x the CPU time of Pi (95% CI a to b)." Number in Departure Mono, large; sentence in Plantin. Always followed by the sample size and the DEMO/real state. Pre-rendered from the data file. This is the screenshot people tweet.
2. **Persistent DEMO ribbon until data is real.** A hairline-bordered `[ DEMO DATA ]` bar in warning `#e8993a`, repeated inside every OG card and badge (badge message `demo`, colour `orange`). Remove through one flag in the data JSON. Honesty is the brand: Pi's "best-effort, not for billing" tone.
3. **Rank ranges, not ranks.** Show rank as `1-2` when CIs overlap; draw each row's interval as an inline SVG whisker on a shared axis; grey-hatch the A/A noise floor band so differences inside it read as "no difference". Computed at build time; zero JS needed.
4. **Head-to-head permalinks** `/vs/pig-vs-pi/` (and `/vs/<a>-vs-<b>/` for every pair, generated). Page leads with the paired ratio for each metric, interval, "within noise floor" verdict, and a copyable repro command. Canonical URLs are stable forever; ordered alphabetically to avoid duplicates.
5. **Pre-generated 1200x630 OG card per page and per pair** (build script renders SVG to PNG, plus keep the SVG). Layout: dark bg `#0d1116`, `#6a9fcc` accent, big ratio, whisker, harness names, snapshot date, DEMO ribbon, pi-arena wordmark. `twitter:card=summary_large_image`, alt text = the headline sentence (as pi.dev does).
6. **Embeddable badges as static SVGs plus shields endpoint JSON.** Commit `badges/<harness>-cpu.svg` (flat, shields-like) and `badges/<harness>-cpu.json` with `schemaVersion/label/message/color`. Copy-paste Markdown on each harness page. Message includes the interval: `0.82x [0.79, 0.85]`. Colour only encodes "outside noise floor" vs not, never "good/bad".
7. **Dated immutable snapshots** `/snapshots/2026-10-14/` with a frozen copy of data + pages, plus `latest/`. Every page footer shows the snapshot id, harness versions, commit SHAs, machine, mock model script hash. Matches Terminal-Bench dated submissions and AA version history.
8. **"What changed" feed** `/changelog/` and `/changelog.xml` (Atom/RSS, as pi.dev already does): entries like "PiG 0.9.1 vs Pi 1.2.0: CPU ratio moved 0.84 to 0.80, outside noise floor." Auto-generated by diffing two snapshots. A text "rank moved" diff beats a vague "updated".
9. **Methodology page with a reproduce-it-yourself block.** Pinned versions, exact commands per row (Aider's Command column idea), mock model description, what it cannot measure (no model quality, no network), bootstrap settings (resamples, seed), A/A procedure, exclusion rules (errored run counts, never silently dropped). Link raw JSON and run logs.
10. **Copy-link, copy-image, download-JSON, download-PNG buttons** on each chart (SWE-bench viewer parity), styled as bracket buttons `[ Copy link ]` like pi.dev. Vanilla JS: Clipboard API, `canvas` from the inline SVG for PNG, `?metric=cpu&vs=pi` URL state so a filtered view is shareable.
11. **Pi look and feel, dark-first with a theme switch.** Reuse Pi tokens: `#0d1116`, `#161d27`, `#212730`, text `#ebe7e4`, muted `#9fa4ab`, accent `#6a9fcc`, series 2 `#8f3222` or `#b86b52`; Plantin MT Pro is commercial, so use Georgia/serif fallback or a free serif unless licensed **[INFERENCE: licence not checked]**; Commit Mono and Departure Mono need their own licences checked before bundling. Square corners, 20px graph-paper background, uppercase tracked labels `01 / PI vs PIG`. `PiG` series in `#25c99b` (dark) / `#127560` (light) to link to pi-in-go.dev.
12. **Terminal-style leaderboard row, mobile-first.** Each row is one tappable line: `1-2  PiG   0.82x  [0.79, 0.85]`, with the whisker beneath at 390px width. Test that a full-viewport phone screenshot shows the title, DEMO state, top rows and snapshot date. Hero numbers use `clamp()` like Pi.
13. **Provenance chips per row**: `run by pi-arena`, `third-party reproduction`, `version pinned`, `A/A passed`. Inspired by SWE-bench's "checked by the team" marker. Anything unverified shows no chip.
14. **Cost-of-harness scatter** (CPU time vs memory, or wall vs instructions) pre-rendered as SVG with crosshair intervals on both axes; the Aider/AA "score vs cost" idea applied to overhead. Pareto frontier line drawn in static SVG; hover via CSS `:hover` and `<title>`, no library.
15. **Conflict-of-interest and integrity box on the home page.** One short paragraph: who runs this, which harness the maintainer also builds, that every run is kept, no private variants, how to submit a harness (PR with config + pinned version), and that a failed or noisy run is shown, not removed. Directly answers the Leaderboard Illusion critique. **[INFERENCE: framing]**

### Suggested hero copy (Pi voice, no em dashes)
- Headline: "There are many agent harnesses. Here is what each one costs."
- Sub: "One scripted mock model. Same tasks, same machine. We measure the harness, not the model."
- Alt headline: "Measure the harness, not the model."
- Alt sub: "Paired ratios against a reference, 95% intervals, and an A/A noise floor. If it is inside the floor, we say so."
- Number line template: "PiG: 0.xx x the CPU of Pi [a, b]. DEMO data."
- Footer/ethos: "Every run is kept. Every number has an interval. Reproduce it with one command."
- Share button text: `[ Copy link ]`, `[ Copy card ]`, `[ Embed badge ]`.

---

## 4. URLs actually opened
Part 1: https://pi.dev/ (raw HTML), https://pi.dev/style.css, https://pi.dev/favicon.svg, https://pi.dev/changelog.xml, https://pi.dev/social.png (HEAD only, 200 image/png), https://mariozechner.at/posts/2025-11-30-pi-coding-agent/, https://raw.githubusercontent.com/badlogic/pi-mono/main/README.md (head), https://pi-in-go.dev/ (HTML + linked `_next` CSS). Not opened: pi.dev/docs pages beyond homepage copy and README. earendil-works/pi repo page itself not opened (README mirrors badlogic/pi-mono, which does show `nix run github:earendil-works/pi/stable`).
Part 2: https://aider.chat/docs/leaderboards/, https://aider.chat/docs/leaderboards/notes.html, https://www.tbench.ai/leaderboard (redirects to tbench.ai home; table empty because JS-rendered), https://github.com/harbor-framework/terminal-bench, https://raw.githubusercontent.com/harbor-framework/terminal-bench/main/leaderboard/SUBMIT.md, https://www.swebench.com/, https://artificialanalysis.ai/, https://artificialanalysis.ai/methodology, https://artificialanalysis.ai/methodology/coding-agents-benchmarking, https://github.com/lmarena/arena-rank, https://arxiv.org/abs/2504.20879, https://www.theregister.com/software/2025/04/08/meta-accused-of-llama-4-bait-n-switch-to-juice-lmarena-rank/1470166, search snippets for https://shields.io/badges/endpoint-badge and https://badges.cucumberstudio.com/endpoint.
Fetch failures (so unverified): arena.ai/lmarena.ai leaderboard (HTTP 403), arena.ai blog posts and changelog (JS shell, no content), designarena.ai/leaderboard (JS shell), shields.io docs page (returned a 404 badge SVG). Reddit/HN threads not opened; "how it spreads on X/HN/Reddit" is therefore based on page features and the Register/arXiv coverage, not on social metrics. **[GAP]**
