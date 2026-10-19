# Inspiration for the pi-arena benchmark dashboard

Scope: all 13 sources listed in the assignment (the assignment said 12 but lists 13 items), patterns (not looks) mapped to our components. Component names used below: **KPI tiles** (Overview), **Ranked chart** (whiskers), **Forest plot** (Compare), **Filter bar** (URL state), **Table/chart toggle**, **Tooltips**, **Workload detail** (strips, distributions, drift, small multiples), **Drill-down** ("How a number is made"), **Runs/provenance**, **Glossary**, **Status badges**, **Theming**.

Access notes (honest): `arena.ai/leaderboard` (ex lmarena.ai) returned HTTP 403 to my fetcher, so LMArena UI facts come from the official ranking-method blog, the help center and a third-party walkthrough. tbench.ai and the MLCommons visualizer render their tables client-side (empty in my fetch), so those entries rely on docs and static pages. Anything not read directly is marked [INFERENCE].

## 1. LMArena / Chatbot Arena leaderboard
- **What:** Crowd-voted pairwise LLM ranking (Bradley-Terry score with bootstrap-style CIs), tabbed per arena.
- **Patterns:**
  - Rank is split in two: a unique **raw rank** (sorted by score) plus a **rank spread** interval. Best rank = 1 + #{models whose lower CI > my upper CI}; worst rank = 1 + #{models whose upper CI > my lower CI}. Ties = overlapping spreads. -> **Ranked chart**: show a rank range ("2 to 5") next to the bar, not a falsely precise #3.
  - Columns are Rank, Rank Spread, Score with a +/- CI, Votes, Price. "Votes" is the sample size shown beside every number. -> **Ranked chart / table**: always show n (rounds, paired samples) next to the estimate.
  - Filters live behind "Show Filters" with a Categories dropdown (default "Overall"); top tabs switch arenas. New models carry a "preliminary" tag. -> **Filter bar**, **Status badges** (preliminary = few rounds).
  - Overview tab is a "high-level snapshot" of each arena before drilling in. -> **KPI tiles** as entry points to detail pages.
- **Avoid:** Ranking by the optimistic bound. Arena's own post says the old "optimistic only" rank "naturally assigned high ranks to models whose scores have high uncertainty". Also, overlapping CIs are a weak tie test for us: our arms are paired, so test the CI of the paired ratio directly [INFERENCE].
- **URLs:** https://arena.ai/blog/ranking-method (read via r.jina.ai mirror), https://help.arena.ai/articles/7011479247-how-to-see-ai-rankings-in-arena-leaderboards-2-0-wip, https://github.com/lmarena/arena-rank (README), https://staituned.com/learn/expert/imarena-ai-benchmarking-platform

## 2. Artificial Analysis model comparison charts
- **What:** Dense model comparison page: ranked bars (intelligence, speed, cost) plus quality-vs-cost scatter, with a methodology site.
- **Patterns:**
  - Every chart subtitle states the metric, unit and polarity: "Output tokens per second · Higher is better", "Weighted average cost (USD) per task · Lower is better". -> **Ranked chart**, **Glossary**: polarity in the subtitle, every time (critical for our lower-is-better ratios).
  - Auto-written sentence above each section ("X and Y are the fastest, followed by Z"). -> **KPI tiles**: a generated one-line takeaway per chart.
  - Scatter with a labelled **Pareto line** and a shaded "Most attractive quadrant", plus "27 of 700 models" counter and "Add model from specific provider". -> **Filter bar** (visible "n of N shown"), future CPU-vs-memory scatter on **Workload detail**.
  - Status chips on evaluations ("Updated", "New", "Under review") and versioned index names (v4.3.2). Methodology page has a weights table with Repeats and Scoring columns and the pass@1 formula. -> **Status badges**, **Method** page: table of metrics with samples, aggregation, and version.
  - Some charts footnote "95% confidence interval bounds are clamped at 0". -> **Tooltips/footnotes**: state any clipping on whiskers.
- **Avoid:** A weighted composite "index" as the headline. It hides which component moved; our Overview should rank one metric at a time.
- **URLs:** https://artificialanalysis.ai/models, https://artificialanalysis.ai/methodology/intelligence-benchmarking

## 3. Hugging Face Open LLM Leaderboard
- **What:** Table-first leaderboard of open models over 6 benchmarks, run on a fixed harness (lm-eval).
- **Patterns:**
  - **Raw/normalized toggle** ("table options" > "Score Display" > "Raw"). Normalization subtracts the random baseline then rescales to 0-100. -> **Table/chart toggle** and **Method**: let users flip to raw units; document the transform with a worked example.
  - Column visibility, pinned rows for side-by-side, real-time search with `@field:value`, regex and `;` union. -> **Filter bar** (search syntax), compare-selection.
  - Community "Flagged" models, a "request file" status per submission (pending, running, failed), details link per row, an exact reproduction command (`lm-eval --model_args=...`) in About. -> **Status badges**, **Runs/provenance**, **Drill-down** (copy-able rerun command).
  - Dark/light mode and virtualized table are listed as first-class features. -> **Theming**.
- **Avoid:** One averaged score as the ranking column; the docs I read describe no uncertainty or ties at all, so close scores look like real gaps.
- **URLs:** https://huggingface.co/docs/leaderboards/open_llm_leaderboard/about, https://huggingface.co/docs/leaderboards/open_llm_leaderboard/normalization.md, https://raw.githubusercontent.com/huggingface/leaderboards/main/docs/source/en/open_llm_leaderboard/faq.md, https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard (README)

## 4. SWE-bench leaderboards
- **What:** Coding-agent leaderboard with several dataset splits and a rich "compare results" analysis menu.
- **Patterns:**
  - Split tabs (Verified, Lite, Multilingual...) each state instance counts and link to a "Read the post". -> **Method/Glossary**: each workload shows its size and a link to what it measures.
  - **Bash Only** view runs every model in the same mini-SWE-agent environment "for apples-to-apples" and records the harness release number per row; page says they "do not aim to tune the configuration". -> **Runs/provenance**: show the pinned harness version beside each result, and say why the reference arm is fixed.
  - Row checkboxes + "Quick select: top 10 / top 20 / all", then a Compare menu with ~13 views (resolved by repo, cost scatter, cumulative cost and step distributions). Toolbar buttons: JSON, PNG, **Copy Link**. -> **Filter bar** (preset selection chips), **Forest plot** export, shareable state.
  - Icons marking "open-weights" and "run performed or directly checked by the SWE-bench team". -> **Status badges** (reproduced locally vs imported).
  - Per-model analysis page with "Load data" and breakdown tables. -> **Workload detail**.
- **Avoid:** Empty state ("No models selected") until the user ticks boxes; the headline "% Resolved" bar has no interval in what I read. Default our pages to a populated view.
- **URLs:** https://www.swebench.com/, https://www.swebench.com/verified.html, https://www.swebench.com/viewer.html

## 5. Terminal-Bench leaderboard
- **What:** Agent-on-terminal-tasks leaderboard (v4.0 page), backed by Harbor Hub.
- **Patterns:**
  - Column set is RANK, MODEL, AGENT, RESOLUTION RATE, COST, TOKENS: **agent (harness) and model are separate columns**, and cost/tokens sit beside the score. -> **Ranked chart/table**: harness vs arm identity separate from the metric, with resource cost adjacent to the headline.
  - Two primary calls to action: "Run the benchmark" and "View the tasks" (deep link to the dataset's task list). -> **Drill-down**, **Method**: always link to the exact task/workload definitions.
  - The site is a thin custom view over Hub data (Harbor docs: "custom visuals backed by Hub"). -> architecture: static site reading a JSON results file.
- **Avoid:** Client-rendered table with no server-side content (my fetch saw empty rows). Our static build should emit real HTML tables so the numbers are readable without JS.
- **URLs:** https://www.tbench.ai/, https://docs.harborframework.com/harbor-hub/leaderboards.md

## 6. Harbor (agent eval framework, harborframework)
- **What:** Runs any agent/model/task in sandboxes; ships a local results viewer and Hub leaderboards.
- **Patterns:**
  - Leaderboard is **config-defined**: `columns` (id, header, accessor, type, `display_accessor` vs sort `accessor`, align, description), `rank_by` rules "evaluated in order to break ties" with `nulls: last`. -> **Ranked chart/table**: separate sort value from display string; explicit tie-break chain.
  - Rows link to `trial_ids`; docs say links to trials and versioned datasets "let readers audit results and reproduce". Rows have `status: display|hide`. -> **Drill-down**, **Runs/provenance**.
  - Local viewer: landing page = job list with search and filters; trial page tabs **Agent / Verifier / Artifacts / Config / Lock** ("replayable trial lock"); keyboard `j`/`k`, `Enter`, `Esc`, arrows to move between trials. -> **Drill-down** (tabs for config, lock, artifacts), keyboard nav.
  - `regrade` re-runs an updated verifier on recorded outputs without rerunning the agent. -> **Method/Runs**: separate "collect" from "analyze" so stats can be recomputed from stored raw samples.
  - Machine-readable `--json` everywhere and a public read API for embedding. -> publish our `results.json` next to the page.
- **Avoid:** Docs state "Hub intentionally does not calculate row scores from linked trials". We should compute displayed numbers from the linked raw data so the drill-down can reproduce them.
- **URLs:** https://docs.harborframework.com/llms.txt, https://docs.harborframework.com/results/view-job-results.md, https://docs.harborframework.com/harbor-hub/leaderboards.md

## 7. MLPerf results browser (MLCommons)
- **What:** Hardware/software benchmark results as an embedded interactive table (Tableau) with tabs for visual views, plus a separate visualizer dashboard.
- **Patterns:**
  - Row = "a set of results produced by a single submitter using the same software stack and hardware platform", with Details and Code links per row. -> **Runs/provenance**: define precisely what one row/run is; link to config and code.
  - **Closed vs Open division** (apples-to-apples vs free to change the model) and Available / Preview / RDI availability categories. -> **Status badges**, **Method**: label comparability class on each result.
  - Progressive disclosure: hover "+" on System Name to expand more columns. -> **Table/chart toggle**: compact default, expandable detail columns.
  - A public **change log** for results "modified or invalidated" after publication, raw `.xlsx` download, supplemental PDF, and results-usage guidelines. Scenario + metric pairs state latency constraints. -> **Runs/provenance** (health/changes list), **Method**.
- **Avoid:** Tableau iframe: state is not linkable and nothing is static. Keep our filters in the URL and our tables in plain HTML.
- **URLs:** https://mlcommons.org/benchmarks/inference-datacenter/ (visualizer link target https://mlcommons.org/visualizer redirects to a Streamlit app that rendered no readable content)

## 8. Vercel dashboard / Speed Insights
- **What:** Web-vitals dashboard: Real Experience Score plus per-metric time series, route list and map.
- **Patterns:**
  - Fixed control strip: Device (mobile/desktop), Environment (preview/production/all), Time range, Metric. -> **Filter bar**: a short, stable set of facets.
  - Time-series defaults to **P75** with toggles for P90/P95/P99, and each metric page has three linked views (line, ranked "kanban" of worst routes, map) where clicking an item filters the others. -> **Workload detail**: default statistic is stated and switchable; ranked list drives the chart.
  - Threshold bands with explicit labels: 0-49 Poor (red), 50-89 Needs Improvement (orange), 90-100 Good (green); metrics table gives a "Target value" per metric. -> **Status badges** and **Glossary** (target column).
  - Rows below 0.5% of visits are hidden by default and the page says so. -> **Filter bar**: disclose any default row suppression.
  - Geist color system: 10 steps per hue, each step has a fixed role (100 bg, 200 hover, 400 border, 700 solid, 900 secondary text, 1000 text). -> **Theming**: map semantic tokens to steps; dark mode swaps the scale, not the component CSS.
- **Avoid:** Collapsing metrics into a 0-100 weighted score via a log-normal lookup (their own docs explain this) and hard red/orange/green bins. Bins hide magnitude and uncertainty, and the docs admit improvements inside a band "don't significantly impact" the outcome.
- **URLs:** https://vercel.com/docs/speed-insights, https://vercel.com/docs/speed-insights/metrics.md, https://vercel.com/geist/colors

## 9. Grafana dashboards and design system
- **What:** Open-source dashboard tool; Saga is its design system, with a stat panel and written dashboard best practices.
- **Patterns:**
  - **Stat panel**: single value, optional sparkline, percent change, threshold coloring, "Text mode" (value only, value+name), and name/value moved into the hover tooltip when space is tight. Sparkline auto-hides when the tile is small. -> **KPI tiles**.
  - Percent-change color mode offers **Standard** (green up) and **Inverted** (red up). -> **KPI tiles**: encode polarity per metric; for us ratio up = worse.
  - Best practices: "A dashboard should tell a story or answer a question", large to small / general to specific, hierarchical drill-downs, template variables plus **URL parameters instead of copying dashboards**, "normalizing axes", "blue means good, red means bad", descriptions in an `i` tooltip on each panel, a Text panel for purpose and instructions. -> **Overview -> Compare -> Detail** hierarchy, **Filter bar**, **Tooltips**, **Method** blurb on each page.
  - Saga principles (universal, accessible, coherent, defined). -> **Theming**: one token set, documented limits per component.
- **Avoid:** Dashboard sprawl and stacked graphs; the best-practices page warns stacking "can be misleading and hide important data". Keep one chart per question.
- **URLs:** https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/, https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/stat/, https://grafana.com/developers/saga/

## 10. Our World in Data grapher
- **What:** Embeddable interactive charts with a full data page; the best example of state-in-URL.
- **Patterns:**
  - Chart/Table/Map are **tabs of the same view** (`?tab=table`), plus overlays `?overlay=sources|download-data|download-vis`. -> **Table/chart toggle**, **Drill-down**.
  - Whole state is in the query: `country=A~B`, `time=2000..2020`, `focus=`, `facet=none|entity|metric`, `yScale=log`, `uniformYAxis=1`, `tableFilter=`, `tableSearch=`. -> **Filter bar**: serialize every control; `facet` + `uniformYAxis` for **small multiples**.
  - Download exactly what is shown: `csvType=filtered` honours the same URL params; `.csv`, `.metadata.json`, `.zip`, `.png`, `.svg` suffixes on the chart URL. -> publish per-chart CSV/JSON next to each chart.
  - Data page metadata block: Description, Data source, Unit, Date range, Last updated, Next expected update, Managed by; then per-source "Retrieved on / from", citation and "How to cite". -> **Runs/provenance**, **Method**.
  - "Show more / Show less" key takeaways under the chart. -> **KPI tiles**/chart captions.
- **Avoid:** Copying code: the grapher repo README says it is "no longer available under the MIT licence". Also avoid its very long scrolling data page; keep ours to named sections.
- **URLs:** https://docs.owid.io/projects/etl/api/chart-api/, https://ourworldindata.org/grapher/life-expectancy, https://ourworldindata.org/grapher/electoral-democracy-index?tab=table&time=1975..1976&country=CPV~COM~MOZ~PNG~STP~SUR, https://github.com/owid/owid-grapher

## 11. Financial Times Visual Vocabulary / Chart Doctor
- **What:** FT poster and repo that maps analytical intent to chart type (Deviation, Ranking, Distribution, Change over time, Correlation...).
- **Patterns:**
  - Intent-first chart choice. **Deviation** "emphasise variations from a fixed reference point" (diverging bar, surplus/deficit filled line). -> **Forest plot**: reference = 1.0 line, deviations left/right, shaded fill for the noise band.
  - **Ranking**: sorted ordered bar, **dot strip plot** and lollipop ("don't be afraid to highlight the points of interest"). -> **Ranked chart**: sorted, highlight the reference arm.
  - **Distribution**: dot strip / barcode "good for showing individual values", boxplot, violin, cumulative curve; reading list includes Weissgerber et al. "Beyond Bar and Line Graphs". -> **Workload detail** strip plots + distribution view of raw samples, never bars alone.
  - **Fan chart** shows uncertainty; line charts use markers when data are irregular. -> **Workload detail** drift over rounds (markers per round, band for noise).
  - Consistent colour order for non-designers (Datawrapper quotes FT's Caroline Nevitt; FT uses dark blue first, then magenta, green last). -> **Theming**: fixed arm-to-colour mapping on every page.
- **Avoid:** Stacked bars, pies and areas (the poster itself warns against reading components in them) and dual axes (reading list links "Be Careful with Dual Axis Charts"). One axis per chart.
- **URLs:** https://github.com/Financial-Times/chart-doctor/tree/main/visual-vocabulary (README), https://www.datawrapper.de/blog/colors-for-data-vis-style-guides

## 12. Observable Plot defaults
- **What:** Layered-marks charting library (JS/SVG) whose defaults encode good practice.
- **Patterns:**
  - Layered marks (`ruleX([1])`, `frame`, `dot`, `tickX`, error rules) sharing scales; **facets** `fx`/`fy` for small multiples. -> **Forest plot** (rule at 1 + band rect + dots + whisker rules), **Workload detail** small multiples.
  - Colours default to `currentColor` and system-ui font, so plots inherit the page theme. -> **Theming**: draw SVG with CSS variables/`currentColor`.
  - Built-in `title`, `subtitle`, `caption` options; docs say "Don't make the reader work to find what you already know." -> **Tooltips/captions**: lead with the finding as the chart title.
  - Diverging colour scale is **symmetric around a pivot**; `diverging-log` has pivot default **1** and default scheme `rdbu`; categorical default is `observable10`. -> **Forest plot** colour of ratio magnitude if used.
  - Log scale default base-10 ticks with SI prefixes; `tickFormat` overrides. -> **Forest plot** axis: log ratio with ticks like 0.5, 1, 2.
- **Avoid:** Default quantitative scheme is `turbo` (rainbow), and Plot does not auto-size margins for long labels (`marginLeft` must be set). Use a diverging scheme and measure label widths for long workload names.
- **URLs:** https://raw.githubusercontent.com/observablehq/plot/main/docs/features/plots.md, https://raw.githubusercontent.com/observablehq/plot/main/docs/features/scales.md (observablehq.com itself returned HTTP 429)

## 13. Go perf dashboard (perf.golang.org) and benchstat
- **What:** `benchstat` compares benchmark samples; perf.golang.org stores uploads and graphs commits against a baseline.
- **Patterns:**
  - Row format: `1.718µ ± 1%  1.423µ ± 1%  -17.20% (p=0.000 n=10)` and `~ (p=0.446 n=10)` when no significant difference at alpha 0.05; final **geomean** row. The doc says median plus 95% CI, "each benchmark should be run at least 10 times", and "statistically significant is not the same as large". -> **Forest plot** / **KPI tiles**: "~" or an explicit "no significant change" label when the CI includes 1.0 or sits inside the A/A band; show n; a geomean KPI tile.
  - Column header "vs base" names the reference; footnote warnings (`¹ benchmarks vary in .fullname`) flag lossy grouping. -> **Status badges**/footnotes: warn when rows aggregate different configs.
  - Flexible `-row`, `-col`, `-table`, `-filter` projections. -> **Filter bar** group-by controls.
  - perf.golang.org dashboard: each graph is relative to a baseline release commit, **95% CI drawn light gray**, hover shows the commit, click goes to a detail page "in context". Search lives in the URL (`/search?q=upload:20261014.90`). -> **Workload detail** drift chart, **Drill-down**.
  - Third-party guide: "Never rerun until significant", fix the count up front. -> **Method** page.
- **Avoid:** Showing only p-values/`~` and hiding magnitude; keep the CI whisker visible even when "no change", so a wide "no change" reads as "not enough data".
- **URLs:** https://raw.githubusercontent.com/golang/perf/master/cmd/benchstat/main.go (package docs), https://raw.githubusercontent.com/egonelbre/go-skills/main/skills/benchstat/benchstat.md, https://perf.golang.org/, https://perf.golang.org/dashboard/

## Palette guidance
1. **Categorical (arms): Okabe-Ito**, designed for colour-blind readers and recommended with redundant coding (shape, position, line type) rather than colour alone. Hex (see package doc, original yellow F0E442): orange `#E69F00`, sky blue `#56B4E9`, bluish green `#009E73`, yellow `#F0E442`, blue `#0072B2`, vermillion `#D55E00`, reddish purple `#CC79A7`, black `#000000`. Okabe-Ito's own advice: avoid pure `#FF0000`, prefer vermillion; thin lines need bold colours. Sources: https://jfly.uni-koeln.de/color/ (principles), https://easystats.github.io/see/reference/okabeito_colors.html (hex).
2. **Alternative categorical: Paul Tol "Bright"** `#4477AA #EE6677 #228833 #CCBB44 #66CCEE #AA3377 #BBBBBB` (main scheme for lines), or "Vibrant" `#EE7733 #0077BB #33BBEE #EE3377 #CC3311 #009988 #BBBBBB`. Tol also gives a "Dark" scheme where every colour has contrast ratio >= 4.5 with white (`#4477BB #CC4466 #228833 #2255AA #993366 #006644 #117788 #882288 #BB4488 #775500 #444444`) for text and thin lines on light backgrounds, and "Pale" colours for table-cell backgrounds. Tableau 10 (`#4e79a7 #f28e2c #e15759 #76b7b2 #59a14f #edc949 #af7aa1 #ff9da7 #9c755f #bab0ab`, from d3-scale-chromatic) is fine for 10+ series but one search snippet (vizcept.com) flags it as not colour-blind safe, so do not use it as the arm palette. Source: https://sronpersonalpages.nl/~pault/ ; https://raw.githubusercontent.com/d3/d3-scale-chromatic/main/src/categorical/Tableau10.js
3. **Diverging (forest plot, delta cells): Tol "BuRd"** = reversed ColorBrewer RdBu, 9 steps `#2166AC #4393C3 #92C5DE #D1E5F0 #F7F7F7 #FDDBC7 #F4A582 #D6604D #B2182B`. Tol also offers "Sunset" (11 steps, `#364B9A ... #EAECCC ... #A50026`) and notes the four diverging schemes look alike under colour blindness, so never flip direction between charts. For us: ratio < 1 (lower is better) = blue `#2166AC`, ratio > 1 = red `#B2182B`, noise band and "no significant change" = neutral grey `#BBBBBB`/`#F7F7F7`; always add a glyph or text ("slower", "faster", "~") so colour is never the only cue. Ratios should be diverging on a log scale pivoted at 1 (Plot's `diverging-log` default pivot is 1).
4. **Dark mode differs in three ways.** (a) Keep contrast constant, not hue: Datawrapper's dark mode algorithm keeps each element's contrast against the background the same, so colours very dark on white become very bright on black (https://www.datawrapper.de/blog/dark-mode-for-embedded-visualizations). Their style-guide post adds: when going darker increase saturation, when going lighter reduce it, and sometimes nudge hue (https://www.datawrapper.de/blog/colors-for-data-vis-style-guides). (b) Sequential ramps flip: Carbon says "in dark themes, the lightest color denotes the largest values", while its diverging palettes "do not differentiate between light and dark themes" (https://carbondesignsystem.com/data-visualization/color-palettes). (c) Tol's "Dark" scheme (>= 4.5 against white) is a light-mode choice; on a dark surface switch to Bright/Okabe-Ito mid-luminance colours and tint fills with low opacity [INFERENCE: verify >= 3:1 for chart marks against the chosen dark surface]. Implementation: one semantic token set (Geist-style roles, https://vercel.com/geist/colors) and SVG using `currentColor`/CSS variables as Plot does.

## Cross-cutting takeaways
- Pair every point estimate with an interval and n; show rank as a range (LMArena) and "~" for no change (benchstat), but keep the whisker.
- State polarity and reference in every chart subtitle (AA: "Lower is better"; benchstat: "vs base").
- URL holds all state; each chart has Chart/Table/Sources tabs and a download of exactly what is shown (OWID).
- Drill-down shows config, lock/versions, artifacts and a copy-able rerun command (Harbor, HF).
- Label comparability classes and changes after publication (MLPerf closed/open, change log; SWE-bench Bash Only).
- Avoid composite scores and hard colour bins (AA index, Vercel RES).
