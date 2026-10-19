# The results dashboard

`buffon dashboard RUN_DIR... --out site/` writes a static site: one page (`index.html`), one script (`assets/app.js`), one stylesheet (`assets/app.css`)
and one data file (`data/site.js`). `index.html` is the only HTML file: every page, the repository documents included, is a view of the app. There is no server and no build step to view it. It opens
from the folder (file://) and from GitHub Pages (`.github/workflows/pages.yml`, built by `tools/pages_site.py`). Nothing is fetched when the site builds or when it is viewed. Every view has its own link, for example
`index.html#/r/prompts-and-tools?h=pig-tip,pibolt&v=values&base=pi-bun`, so any view can be shown to someone else and the back button works.

## What it is for

Buffon is a growing eval suite. Anyone can add a harness or a benchmark. It does not rank harnesses and it makes no assumption about them. It is one more
tool for people who work with Pi, or with Pi ideas in other harnesses, to choose, learn and build. So the site lines the numbers up and the reader decides.

1. **Sections, not a verdict.** The front page has one tile for each section. The reader filters the harnesses, picks a baseline and shows values or ratios to it; a section page lists that part's main metrics, with every other metric of the section folded. There is no overall score, no composite index, no grade, no "lowest" or "highest" mark or sentence. Every choice is in the URL.
2. **Only measured numbers.** A cell is the median of a harness's measured rounds, with its unit. Its hover shows the 95% interval of that median
   (`buffon.stats.bootstrap_ci`, same seed), the middle half, and the number of rounds. A ratio is the report's own (`buffon/report/cells.py`) when the baseline is
   Pi, and the ratio of medians over the rounds both harnesses ran, with a paired bootstrap interval computed in the page (same method, fixed seed), otherwise.
   The histogram of a ratio's bootstrap draws comes from the very draws behind the report's interval (the build fails if they do not give back that interval).
   `tests/test_numbers_from_raw.py` recomputes every shown number from `raw.json` alone with its own code.
3. **A missing value says why, and is never a row.** A chart, a tile or a table draws only the harnesses that have a value for what it shows. A selected harness with none is
   named in one line under it: "Can't run: A (no Pi-dialect RPC mode)" when the runner's manifest says it cannot (the reason is the one it recorded, `skipped` in `raw.json`), and
   one muted line "Not in this test: B, C" for the others. A harness is in one of the lines, never both and never an n/a row; a harness measured only on another wire API is in a third
   muted line, "Measured with another API: D (Messages API)", with a link that switches the API. If no selected harness has a value, the card says so in one line instead of an empty chart.
   A cell that is empty inside a table that has other values in its row is a dash with the reason as its tooltip.
4. **Say what the meter cannot see.** A run records its meter per sample (`meter`, `perf_scope`). When a cell's number comes from a reading the meter cannot make
   well (sampled instructions on macOS, a live CPU reading on the rusage meter), that cell carries a caveat (docs/METHODOLOGY.md, "Measurement caveats by platform").
5. **Tangible, then deeper.** Click a cell for its measurement page (both command lines, how sure the number is, the rerun command and every raw file, the math).
   Click the `i` of a column for its metric page. Click a harness for its page. Method, runs and the glossary are short and open to detail on request.
6. **Demo data can never pass for a result.** A run whose `raw.json` carries `run.synthetic` (only `tests/report_demo.py` writes it) puts a DEMO banner on every view.
7. **Plain words, for programmers.** Every sentence follows ASD-STE100 Simplified Technical English. CPU, API, RPC, JSON and the like carry no tooltip
   (`glossary.COMMON`); the glossary explains the benchmarking and statistics words. Each harness links to its own docs.

## Views

Navigation, in this order: Results, Harnesses, Method, About. The footer has "Add a harness" and "Submit a result". Buffon measures through Pi's lens and is not a ranking of agents; the site says so once on Home and once on About.

| View | Route | Answers | Main content |
|---|---|---|---|
| Results (home) | `#/?h=&base=&v=&api=` | What does each harness cost, in each part of Pi's use? | The hero (what Buffon is, the name, the trust line), the sticky control bar (harness chips, baseline, Values or Ratio, wire API where the open section has more than one), and one tile for each section with its headline metric and a dot plot of every selected harness (ratio to the baseline with its 95% interval, or values). No other cards |
| A section | `#/r/<section>?h=&base=&v=&api=&m=&view=&sort=` | How does each harness do on this part? | The explorer of that group. A rail of the sections and "All metrics" (a row of tabs on mobile); one sentence; metric chips grouped by kind (CPU, Time, Memory, Size, Wire) with All and None for each group, the headline metric chosen (`m`); one small chart for each chosen metric, harnesses in the site order, under one view switch (`view`): **Bars** (the median from zero, the dashed line at the baseline; the view a URL without `view` gets), **Dots** (ratio with its 95% interval, or values), **Rounds** (every round as a dot, a tick at the median) and, for the extension sweep only, **Line** (`view=dots` and the others in the URL always win); then the tables of every metric of the section, one for each workload (see "Tables" below), with one CSV (all metrics, one row for each harness). Sections in order: Start-up, Prompts and tools, Large writes, Streaming, Sessions, Durable, Extensions, Agent swarming, Reliability, Wire, Other suites; all are always listed, and one with no data is the next row. **Agent swarming** holds the exact limits (`scale/agents-limit`, `scale/print-limit`) without and with ten extensions as paired bars, memory per agent and turn rate against N, and a table; the ones of earlier runs read "P to F-1". **Reliability** holds the faults, passed or not, with a page for each fault (`#/fault/<id>/<harness>`) |
| All metrics | `#/all?h=&base=&v=&api=&s=&k=&sort=` | Every metric, organised | The tables of every section one under the other, each section with a heading that links to its page and one table for each workload (see "Tables" below), filtered by section (`s`) and by kind (`k`), sortable by any column, in values or ratios, one CSV for the whole page. A section with more than four workloads (Wire) folds all but its first |
| An empty section | `#/r/<section>` | What will this part measure? | Every section is in the rail and on Home, with data or without. One with no data is muted ("Not run yet"): the page says what it measures, which workloads of the launch rerun fill it and for which harnesses, and the command; it draws no number and has no control bar |
| Other suites | `#/r/other-suites` | What do other projects' own benchmarks say? | With external suite runs or imported results (`buffon dashboard ... --external-suites DIR... --external-results DIR...`, or such a directory among the run directories; docs/EXTERNAL.md); without them the section is listed and says "Not run yet". The last section of the rail before All metrics, with no control bar. One card for each suite, grouped by project: name and owner, pinned commit and source link, command, host and when it ran, "Their method, their numbers: not comparable with Buffon's rows", the suite's own table verbatim (targets with the same columns share one table with a column for each; a column of a target that is an arm of the site carries its colour, so the spotlight works), and the raw output one click away (open when the table did not parse, `buffon/dashboard/external_site.py`). None of it is in a tile, a ratio, the grade or #/all |
| A metric | `#/metric/<key>?api=&base=` | What is this metric, and how do all harnesses compare on it? | One sentence of what it measures; one chart with every harness in the site order; what runs, the formulas, and every round behind disclosures. Linked from the section tables |
| Harnesses | `#/harnesses` | What does each project say it is? | A card for each project with a profile, measured or not: its mark, its README head (title, first paragraphs), the source line, the versions measured here (or "Not measured yet"), maker and licence, and links. Cards are as tall as the tallest in their row |
| A harness | `#/harness/<slug>?api=&base=` | What does the project say, and how does it do here? | The same README head with the mark, and "From its README" (the README's wide picture) below it; a section strip with each section's headline ratio and interval; Scope; How it ran (settings, divergences, pins); the folded "Every measure". A harness with no data in the loaded runs shows its scope from the manifest and no number |
| A measurement | `#/cell/<cell>/<harness>` | Where does this one number come from? | The ratio and both medians; the interval and the noise floor beside the rerun command; what runs; the equivalence margin; the math collapsed. A cell with different work gives the reason and no derivation |
| A swarm probe | `#/swarm/<envelope>/<kind>/<harness>/<n>` | Where does this mark come from? | Every round that tried this N; the memory arithmetic; whether it completed and why not; the other N tried |
| Method | `#/method` | How is one number made, and how fair is it? | The six steps; Fairness (runtime settings, equivalence margins); Limits; "Runs and data" (`#/method/runs`, the old Runs page); links to the documents. The glossary (`#/glossary?t=`) is linked from here and from term tooltips, not from the nav |
| About | `#/about?at=` | Why "Buffon"? | The README as a page, landing at "Why Buffon" from the hero link |

Old addresses redirect: `#/scale` and `#/r/many-agents` (the section was called Many agents) to `#/r/agent-swarming`, `#/compare` and `#/?m=` to Results (a metric list opens the section that holds the first metric), `#/runs` to `#/method/runs`, `#/doc/README` to `#/about`.
A metric is a workload and a metric name whatever the wire API (`overhead-print.cpu_ms`). A section shows one API at a time (`api`, starting with the API most harnesses speak) when it has values for more than one, because the same workload costs differently on different wire formats. A harness that does not speak it is "can't run" with that reason.

## Tables

The metric tables of a section (`workloadTables`, `metricTable` in `app.js`), of `#/all` and of Agent swarming (`agentsTables`) follow these rules, so that a page never needs a horizontal scrollbar at 1280 px
and never shows an empty row:

- **One table for each workload** (the rows of the section's picker), titled with the workload; a section with more than four workloads folds all but the first (a `details.wl`).
- **Rows are the harnesses that have a value in it**, in the site order (or the reader's sort); **columns are the metrics that have a value for those harnesses**. No row and no column is empty
  for the harnesses shown; a harness with no value in the workload is named under the table (rule 3 of "What it is for"). Harnesses absent from every table of a page are named once above them.
- **At most six main columns** (`MAIN_MAX`). The main metrics of a workload are picked by name, in this order, as many as fit: CPU time per 1,000 tokens, CPU time until ready, CPU time, time until ready,
  time, time per turn, CPU time per turn, peak memory, peak memory of all processes, memory when ready, growth of the session file (`MAIN_WORDS`); a word that has variants brings all of them. Where no name matches (Wire), the first six.
- **A heading of at most two lines.** A column is headed by its short metric name; a variant shared by at least three metrics of the workload ("200 KB file", "short answer", "answer 10 times longer")
  is a group heading over its columns instead of being repeated in each; the full name is in the tooltip and in the CSV label. The workload is the table's title.
- **Everything else is under a closed "More metrics (N)"** in the same layout: one table for each kind (CPU, Time, Memory, ...), at most six columns each, the same rows.
- **Agent swarming** has one table for each workload (RPC, print mode, each with the ten extensions) with the six columns of its picker (agents that fit, CPU per turn or task, turns or tasks per
  second, 95th percentile, memory per agent, memory of the container); the row says at how many agents the per-agent metrics were measured. It has no "More metrics".
- Every value links to its derivation; a column has an `i` link to its metric page. **Download CSV** is one file with a column for every metric of the page and a row for each harness (Agent swarming:
  for each workload and harness).
- **The picker follows the same rule.** Its rows are the workloads (one for each variant: "Large file write, 200 KB file"), its columns the metric words without their variant, at most eight (`PICK_MAX`):
  the main words first, the others in a closed "More metrics (N)" under it, in pickers of one kind each (open when a chosen metric is in them). It never scrolls sideways at 1280 px.
- **One badge.** A table does not repeat PROVISIONAL in each value: its card has one badge in the head when a run behind a shown value is provisional (a derivation page has its own).
- **Mobile.** At 390 px each table (and each picker) is its own scroll region inside its card, with the harness column fixed (124 px, columns of 100 px); the page itself does not scroll sideways.
  The tables stay readable because they scroll rather than squeeze.

## Scope, fairness and the newer fields

These come from `report.json` and `raw.json`; the site computes none of them.

- **Scope.** Each harness has a `scope` (`model.scope_of`): the workloads it has a value in, and for the others the reason the runner recorded (the manifest's `cannot_run` text). A harness page has one "Scope" card: a "Measured in" line and a folded "Not measured" list with reasons, and a folded "Different work" list when the manifest has `[[divergence]]` entries. A chip of the harness bar says in its tooltip where the harness ran. A "can't run" cell shows the short reason on hover.
- **Runtime settings.** `raw.json` `arms[<id>].runtime_settings` (`env`, `left_default`, `source`). The Method page has one row for each harness; a harness page repeats its own row. A run that did not record it says so.
- **Different work.** A comparison with `not_compared` (a reason) shows the arm's median and the label "different work: not compared". It has no ratio, no bar and no mark; in a ratio view it sorts last. Its measurement page gives the reason and the source of the divergence and has no derivation. The brief counts these measures once. For a baseline other than Pi, a cell where either harness has `not_compared` is not compared.
- **Equivalence.** `comparisons[<arm>].equivalence` (margin, 90% interval of the ratio, p, result). The measurement page shows the margin, the interval and "within ±m%" or "not shown to be within ±m%", and one step in the math. The rule is on How it works, and the glossary has "equivalence margin" and "different work". A metric with no margin shows nothing.
- **Kinds.** Every metric belongs to exactly one section (`SECTIONS` in `app.js`); the kind "wire" (requests, request bytes) is the Wire section. A metric that fits no section is in "Other".
- **Slot.** The Runs card of a run says "slot 2 of 4, CPUs 4-7" and its calibration file when `run.slot` is present.
- `tests/report_demo.py` carries all of these fields (`contracts()` stands in for the report fields until `cells.py` writes them) so every element renders; `build_demo_site(out)` builds the demo site with them.

## Interaction

- **No blended headline, no ranking by opinion.** The site has no overall index, no mix, no grade and no faithfulness column. `buffon grade` and its files
  (`grade.json`, `leaderboard.md`, `report-card.md`) stay in the report directory; the site does not show them. Every filter and sort is in the URL.
- **Every control redraws from the URL.** `render(data, hash)` is a pure function; one delegated listener per event type turns a click or a select into a new
  hash. `toggle` and `stateOf` are pure too, so the tests draw every route and every choice without a browser.
- **Every chart has a table view** with sortable columns, a row filter and a CSV download of exactly the rows shown. The metric tables of a section, of `#/all` and of Agent swarming have one CSV each (`data-csv-group`).
- **Every abbreviation is explained.** `explain()` wraps each abbreviation in running text with its expansion as a tooltip; `tests/test_dashboard.py` fails on a
  view that shows an abbreviation the glossary does not define.
- **Every mark has a tooltip.**

## Profiles

The Harnesses index and a harness page show the head of each project's own README: its title, its first one or two paragraphs verbatim (clipped at 60 words on a card), and one source line, "README at <repo>@<ref>, read <date>". Every card leads with one square mark, the same 64 px tile for every project, then the title: a vector mark is fitted in the tile, a cropped picture fills it (nearest-neighbour, so pixel art stays sharp), and a project with no mark gets its initials in the mono face. Each mark has its source, its pinned ref and its sha256 (`mark_source`, `mark_ref`, `mark_sha256`); a crop adds `mark_crop = [x, y, side, side]` in pixels of the source, so it can be made again. PiG's mark is the owner's own file from a private repository: its `mark_source` is not a URL, `mark_note` says so, and nothing is fetched for it. The README's wide picture (a banner, a splash screen, a demo) is on the harness page only, below the head, as "From its README" with its source line. The site is offline: `tools/profiles_refresh.py <project>` fetches the README and the pictures at a pinned ref once, stores static copies, and the build checks each hash and fetches nothing. A harness with a profile and an arm in the registry that no loaded run has data for has its card, marked "Not measured yet", and a page that shows its scope from the manifest (what it can run, and "Can't run" with the manifest's reasons) and, when `campaigns/launch-rerun.toml` names it, its family in the launch rerun. It is in no chart, tile, table or `#/all` until it has data. No card has a coloured edge: a harness colour is a dot and a mark in charts.

Quotes stay in an element with the class `their-words`, which the banned-word scan of `tests/test_dashboard_profiles.py` leaves out: Buffon's own sentences on these pages pass the list in `tests/banned_words.py`, and a project's words are not ours to edit. A harness page has at most two generated sentences, and says "costs more", "costs less" and "within noise", never better or worse. A harness with no profile says "No profile yet" and links the homepage of its manifest. To fix a profile, edit `profiles/<project>.toml`; the build fails on a bad one and names every problem.

## Consistency rules

Each rule has a test (`tests/test_dashboard_consistency.py`) and the audit that found it (`docs/design/DASHBOARD-AUDIT.md`).

- **One formatter** (`app.js`: `sig`, `parts`, `val`, `span`, `ratioStr`, `pct`, `axisUnit`). Three significant digits, whole numbers with a thousands separator from 1,000.
  A time under one second is in ms and from one second in s; a memory under 1 GiB is in MiB and from 1 GiB in GiB; a ratio has three significant digits and keeps its zeros
  (1.50, 0.0163); an agent count is a plain integer. The tile, the table, the chart label, the tooltip, the derivation and the runner's own words (`restate`) all call it, so
  one value is one string. A column header names its two units ("ms or s"). An axis chooses one unit for the chart from its largest value.
- **One name for a metric**: the workload's title and the metric's word (`build.metric_word`), wherever it shows. The large-write card takes its column names from them.
  A swarm metric has the same title on the chart, the table and the derivation; the print kind says tasks where the RPC kind says agent-turns.
- **One order and one colour for each harness**: the site order (the baseline, then the run's order) in every chart, legend, table and tile, never by value. A reader's own sort of the grid or of a table view is the only exception. A harness has one colour for its whole life (`harness_list`).
- **One chart frame** (`CH`, `plotFrame`, `endLabels`, `barRows`, `chartWidth`): height 220 for every line chart and histogram, the unit at the top left, the label of the x axis at the bottom right, the name of each line at its end (pushed apart where two meet; no legend), and a width taken from the card, so text keeps its size at 390 px. Bars are one component: the name, the bar from zero with its number at the end of it, an optional whisker, chip and labelled axis.
- **A provisional badge belongs to a value, not to the frame.** A run's own trust label (`hardware.quiet_dedicated`, `runs[].provisional`) puts a Provisional badge on every cell, bar, chart and card that comes from it, with the reason in its tooltip, and nowhere else. A site whose runs were all quiet has none.
- **A control is there only if it works on the page.** The harness chips, the baseline, Values or Ratio and the wire API sit in one sticky bar on the Results pages and nowhere else. The baseline and Values or Ratio are absent where a count has no ratio (Agent swarming, Reliability), and Agent swarming has no Values or Ratio even for memory per agent: its numbers are counts and per-agent costs of one harness at a time, with no baseline run to divide by; the wire API is there only when the open section has more than one. Every metric stays reachable: each section is the explorer of its own metrics (chips, small charts, a table of all of them), and `#/all` holds every metric in one table. There is no flat list of every metric to pick from.
- **A page leads with its answer**: one sentence and one chart or table. The rest is behind a disclosure. A sentence does not repeat a heading, a legend or another page.
- **Mobile at 390 px**: no element makes the page wider. A table scrolls inside its card with its first column in place (the metric tables: one deliberate scroll region for each table, three columns visible at once), or (a key-value table) stacks. `tools/shotkit` checks it in a real browser.

## Checking the layout

`tools/shotkit/go.sh SITE OUT` serves SITE in the Playwright image on Docker (never Chrome on macOS) and shoots every page named in `$PAGES` (default `pages.txt`) at 1440 px and 390 px, light and dark, full page.
`shoot.js` also lists every element wider than the viewport that is not inside a scrolling box, and prints `OVERFLOW` for a mobile page that has one. Edit a pages file for the harness and run names of your site.
`tools/shotkit/measure.sh SITE` prints, for the pages of `pages-measure.txt`, the words, the visible controls (not inside a closed disclosure) and the page height at 390 and 1440 px.

## Decisions

- **No grade, no score.** The method's 0 to 100 score with letters (docs/GRADE.md) stays in the report. The site shows none of it: the owner's rule is that the
  data is accurate, explained and transparent, and readers draw their own conclusions. A test fails if a grade, a score or a "lowest/highest" verdict returns.
- **No mark on the lowest value.** The bar under each value shows the size in its column, and nothing says which is best. The interval and the number of rounds are in the hover.
- **The ratio is a ratio of medians** over the rounds both harnesses completed, not a median of per-round ratios. A cell in values mode is the median over all of
  the harness's own measured rounds; the two differ only when a round is missing, and the tooltips say which is which.
- **Round order is a rotation**, not a shuffle (`buffon/runner/engine.py: rotate`). How it works draws the actual rule.
- **Formulas are rendered at build time.** `buffon dashboard` runs the vendored KaTeX (0.19.0, MIT, `buffon/dashboard/vendor/katex/`) under Node once for the
  general formulas and for each metric's own formula. The page ships only KaTeX's CSS and fonts.
- **The documents travel with the site, in its frame.** CONTRIBUTING, SUBMITTING, METHODOLOGY, WHAT-WE-MEASURE, LIMITATIONS, HEALTH, GETTING-STARTED and
  RAW-FORMAT are converted at build time (`buffon/dashboard/markdown.py`) into `data/site.js` and drawn at `#/doc/<name>`, so they have the same header, fonts,
  colours and light or dark choice as every page, and every link works from a folder. A fenced block is a code block with a Copy button; a table scrolls
  inside its card; a link to a document the site does not carry is plain text. The run logs are listed at `#/logs/<run id>`. The report's own `report.html`,
  `plots/` and the grade files have another look, so the build leaves them out of the site (`build.py` OLD_LOOK); `buffon report` still writes them.
- **JavaScript is required.** The site is drawn by `app.js`; without it the page points at `data/report.md` and `data/report.json`.
- **The look.** Plain system sans-serif, cards on a quiet ground, tabular figures, light and dark themes, one colour per harness. Pi's blue is kept for the Pi
  series. The Pi credit is on How it works and the seed on Runs.

## Inspiration, and what each gave

| Source | Taken |
|---|---|
| LMArena | Rank as a range when intervals overlap; the sample size beside every estimate |
| Artificial Analysis | Metric, unit and direction in every chart's caption; one-line takeaways |
| Hugging Face Open LLM Leaderboard | Sort by any column; a raw/ratio toggle; the exact reproduction command |
| SWE-bench | Copy link on every view; a pinned harness version on every row |
| Terminal-Bench, Harbor | Harness and model kept apart; every row links to its trial and lock files |
| MLPerf | Provenance as a first-class view: system, software, meter |
| Grafana, Vercel | One filter bar whose state lives in the URL; quiet chrome, loud data; tabular figures |
| Our World in Data | Chart and Table for every chart; CSV of what is shown; the full view state in the link |
| Financial Times, Observable | Direct labels; a diverging scale pivoted at 1.00 on a log axis |
| Go perf dashboard, benchstat | `≈` for no clear difference; a noise band behind every comparison |
| Kay, Hullman, Wilke (uncertainty) | Show the distribution of the resamples |
| BetterExplained, Distill (math) | Symbolic formula, then the run's numbers, then the result |

## Code

| File | Role |
|---|---|
| `buffon/dashboard/model.py` | Reads the run directories and the report; every number the views draw; each harness's median and its interval; why a value is missing |
| `buffon/dashboard/build.py` | Writes the site: `data/site.js`, the shell, the assets, `docs/*.html`, the profiles' logos, copies of the run files; the metric list; per-cell caveats |
| `buffon/dashboard/markdown.py` | The repository documents as HTML in the site's components |
| `buffon/dashboard/glossary.py` | Every term and abbreviation, with formulas |
| `profiles/<project>.toml`, `profiles/assets/` | What a project says about itself: tagline, up to three quotes, links, maker, licence, and the head of its own README (`readme_url`, `readme_ref`, `readme_title`, `readme_head`, `retrieved`) with the README's wide picture (`logo`, `logo_source`, `logo_sha256`, `logo_alt`) and its square mark (`mark`, `mark_source`, `mark_ref`, `mark_sha256`, and optionally `mark_crop`, `mark_bg`, `mark_alt`, `mark_note`; or `monogram`, the initials shown when there is no mark). Read by `build.load_profiles` and checked against a schema: https URLs, a pinned ref (a tag or a commit, never a branch), at most 2 head paragraphs, at most 3 quotes of at most 40 words, the sha256 of each picture at every build. Outside `arms/`, because `arms.lock` hashes every file of an arm directory and a profile must not change a measurement's provenance |
| `buffon/dashboard/benchmarks.py` | What each suite, workload and metric is (sentence and formula), from `docs/WHAT-WE-MEASURE.md` and the workload code |
| `buffon/dashboard/formulas.py`, `mathtex.py`, `katex_render.js` | Formula sources and their build-time rendering |
| `buffon/dashboard/assets/app.js` | Routes, views, charts, and the event wiring; `render` and `routes` are exported for the tests |
| `buffon/dashboard/assets/app.css` | Layout, components and the two palettes |
| `tools/shotkit/` | Playwright screenshots of every page (light, dark, 1440 and 390 px) and the mobile overflow check; `pages-v2-real.txt` and `pages-v2-demo.txt` list the pages of the two sites |
| `tools/profiles_refresh.py` | The maintainer tool: fetches a project's README at a pinned ref, keeps its head and its first wide picture (a banner, a splash screen or a demo, never a badge; a GIF gives its first frame, scaled to at most 960 px with ffmpeg), and stores the project's square mark: a vector drawing or a square raster as published, a crop of a picture (`mark_crop`, cut with ffmpeg and scaled to 128 px with nearest-neighbour), or the owner's own file (a `mark_source` that is not an https URL, checked against `mark_sha256` and never fetched). It writes `profiles/<project>.toml` and `profiles/assets/` (the only place the network is used) |
| `buffon/dashboard/profiles_check.py` | The checks of a README head and its pictures: moving refs, badges, SVG sanitising (no script, no external reference, no foreignObject), a PNG or WebP of at most 250 KB and 960 px wide, and the kind of picture (a mark or a strip) |
| `buffon/dashboard/plans.py` | What an empty section will measure: the workloads and harnesses of `campaigns/launch-rerun.toml`, the Durable plan, and the scope of a harness with a profile and an arm but no data (from its manifest) |
| `buffon/dashboard/scale.py` | The swarm samples (`scale/agents-limit`, `scale/print-limit`, the ext10 pair, and the `scale/agents-N`, `scale/print-N` rung samples of earlier runs) as the Scale page draws them: the limit of each harness, its probes pooled per N, where and why the search stopped; the definition and direction (lower or higher is better) of each swarm metric |

## The Scale page

The scale samples are not cells of the grid: `model.without_swarms` keeps them out of the report's cells, and `scale.build` turns them into one entry per envelope
(memory limit and number of cores, read from each sample's `swarm`), kind (RPC or print, and `rpc-ext10`, `print-ext10` when the run has the ten-extension search) and harness.
A harness with no RPC mode, or one that does not load Pi extensions, is in the "Can't run" line under the chart with the runner's reason. A probe whose `mock_saturated` is true carries a
warning mark. A scale run has no A/A copy: the spread across rounds is its noise, and the page shows it as a whisker.

**Two shapes of run.** A run made with the search holds one sample for each harness and round (`scale/agents-limit`, `scale/print-limit`, `scale/agents-ext10`, `scale/print-ext10`):
`agents_limit` (the largest N that completed), `first_failure`, `limit_cause`, `limit_capped`, `limit_cap`, `limit_resolution` and every probe in `probes`.
`scale.search_arm` gives the arm `exact: true`, `limit` (the median over the measured rounds; for an even number the lower middle one, so that it is a number a round produced), `limits` (each round),
`range`, `capped`, `cap`, `resolution`, the `cause` and `first_failure` of the median round, and `rungs`: the probes of all measured rounds pooled for each N (different rounds probe different N in the bisection),
each with `rung_of`'s rules (the median of the rounds that tried it, a stop if any of them failed). `max_ok` is the limit, `or_more` is `capped`, and `stop` is the first failure, None where capped.
The ten-extension search is its own kind, so the derivation pages and routes are the same as for the other kinds.
A run made before the search holds one sample for each rung (`scale.ladder_arm`): the arm is `exact: false`, `max_ok` is the largest rung that completed in every round (P), the first stop is F
(a rung that failed, or the first `not reached: stopped at N agents (<cause>)` of `skipped`), and the true number is in `between` P and F-1. A ladder that never stopped has `at_least`, its top rung.
If a harness has both shapes in one envelope, the search is shown.

**The page.** `#/r/agent-swarming` has the skeleton of every section page: the head (title, one sentence, "How it works"; one PROVISIONAL badge when a shown run is provisional; a "Why do some bars show a range?" disclosure (`details.why`) for a run made before the search), the control bar (harness chips only), a picker card, the VIEW control, ONE primary chart card and the open "All metrics in this section (N)" card (one table for each workload, see "Tables"). The picker has a row for each workload (RPC agents, Print-mode agents, and each with 10 extensions when the run has them) and a column for each metric under its kind: Capacity (agents that fit), CPU (per turn or task), Time (turns or tasks per second; the 95th percentile of a turn's latency in RPC mode or of an agent's time to finish in print mode), Memory (per agent; the whole container). One cell is chosen, in `m` as `<kind>.<metric>` (`rpc.fit`, `print-ext10.mem_per_agent_mib`; the default is `rpc.fit`; a value that is not in the data is the default); `view` is **Bars** for the agents that fit and **Bars** (at the largest N that every drawn harness finished, with the range of the rounds as a whisker; the default) or **Line** (over N) for a per-N metric: only a view that works for the metric is offered. The tables have a row for each harness that ran the workload: the agents that fit and each metric at the largest N that finished (the row says which N), every value a link to the derivation (`#/swarm/...`); every N tried is a point of the line chart and a row of its derivation page. The envelope, the definitions and the runs are in a closed disclosure under the table. The Overview tile keeps its pairs (a second, lighter bar for the ten extensions); the section page draws one kind at a time on the same axis as its twin.

**The answer.** The page asks how many agents fit in the memory limit and answers with one bar chart for each kind: the exact number, on a log2 scale, on the bar. `oom` (the kernel killed agents) and `stall`
(the container sat at its limit, nothing killed) both read "did not fit in 4 GiB"; the detail ("the kernel killed 12 agents", "stalled at the limit, nothing was killed") is the second line of the tooltip
and of the derivation page. `timeout`, `pids` and `error` read as they are ("timed out", "hit the process limit", "failed") and show beside the bar. `scale.CAUSE_WORDS` holds the words.

**The costs.** Three line charts for each kind (chosen one at a time in the picker) against N on one log2 axis: memory per agent, turns per second (print: tasks per second), CPU per agent-turn (print: CPU per task). Only complete N are points;
the first failure is a cross on the axis at its size. The memory of the whole container and the 95th percentiles are cells of the picker too. The ten-extension kinds are rows of the picker with the same metrics.

**The CPU window.** `cpu_ms_per_agent_turn` covers the same window as `turns_per_s` (RPC: the turn phase; print: the whole sample over the tasks), and `start_cpu_ms_per_agent` is the RPC start-up.
An RPC sample without `start_cpu_ms_per_agent` took its CPU over the whole sample, start-up included: `scale.rung_of` drops its `cpu_ms_per_agent_turn`, the kind carries `cpu_legacy`,
the picker has no CPU cell for it and the page says why once in its closed details and once on each derivation page.

The direction of each swarm metric is declared in `scale.METRICS`: turns per second is higher-is-better, the rest are lower-is-better. The grade method does not score these.

## The hero, the tile line and the spotlight

The hero carries a drawing of needles dropped on parallel lines (`heroArt` in `app.js`): a fixed seed, so it is the same on every load, in the theme's colours (a needle that crosses a line is Pi's blue). Each overview tile ends with one factual line, "from X (harness) to Y (harness)", the lowest and the highest value of the selected harnesses (`tileRange`); it never says which is better. Hover, focus or a tap on a harness (a mark, a bar, a row or a chip) dims the other harnesses in every chart and table on the page (`spot`, class `dim`). The only motion is that fade, a change of state, and `prefers-reduced-motion` turns it off. A cell where a harness has no value on the open wire API, but has one on another, names that API (for example "Messages API") and links to it; "can't run" stays for a harness with a value on none.

## Palette

One colour for each harness on every view, in both themes: Pi (its blue) and `--h1` to `--h8` in the order of the site. A colour belongs to a slot, a slot to a harness, and the hue of a slot is the same in
the dark and the light theme (a test holds it within 25 degrees). `tests/test_dashboard_palette.py` fails when two harness colours come near each other: CIEDE2000 (the standard colour difference; CIE76 under-rates blues and
reds) of at least 15 between any two for normal vision and at least 9 under protanopia, deuteranopia and tritanopia (Machado et al. 2009 simulation), and 3:1 on the panel for every colour (text 4.5:1;
`tools/palette_check.py`). The old palette had Pi-Bolt and PiG 0.5.0 at 7.2 (CIEDE2000, dark theme) and rpi and OpenCode 2 near each other; the owner misread both.

How the colours were chosen: `tools/shotkit/palette_search.py` draws colours in OKLCH (chroma at least 0.115, so none is a grey or a brown), keeps those visible on the panel, rejects two with a hue within 38 degrees and a lightness within
0.12 of each other, and maximises the smallest weighted CIEDE2000 distance over the four kinds of vision (weights 1, 0.6, 0.6, 0.5). The light theme was searched first; the dark theme was searched with the hue of each slot held
within 12 degrees. The eight colours were then given to the slots so that the five Pi-family harnesses (Pi, Pi on Bun, Pi-Bolt, PiG 0.4.1, PiG 0.5.0), which readers compare most, are the furthest apart (21.5 or more in both themes).

| Slot | Harness (this run) | Dark | Light |
|---|---|---|---|
| pi | Pi on Node | `#6a9fcc` | `#3f6a8f` |
| h1 | Claude Code | `#d0afff` | `#8775cb` |
| h2 | GitHub Copilot CLI | `#76bb61` | `#456507` |
| h3 | OpenCode 2 | `#fa8ca0` | `#99073f` |
| h4 | Pi on Bun | `#b668a1` | `#711e70` |
| h5 | Pi-Bolt | `#21ebc9` | `#189b7c` |
| h6 | PiG 0.4.1 | `#d0615d` | `#c06060` |
| h7 | PiG 0.5.0 | `#e3cc49` | `#977d09` |
| h8 | rpi | `#8679e8` | `#5a3bc2` |

| Theme | Smallest CIEDE2000 distance between two of the nine | Contrast on the panel |
|---|---|---|
| dark | normal 15.7 (Pi, rpi), protanopia 9.3 (Pi, h1), deuteranopia 9.4 (h2, h6), tritanopia 9.7 (Pi, h2) | 4.6 to 11.5 |
| light | normal 16.6 (h4, rpi), protanopia 11.8 (Pi, rpi), deuteranopia 9.8 (Pi, h4), tritanopia 12.8 (h6, h7) | 3.3 to 9.5 |

A site with more than nine harnesses reuses colours, and every line chart then still names each line at its end, and every bar has its name beside it, so colour is never the only key.

## Screenshots

`docs/design/shots/<view>-<desktop|mobile>-<light|dark>.webp`, from the demo run. These predate the grid and show the earlier views; they are not regenerated here.

## Not done yet

- Share cards (1200×630) and README badges per harness.
- `docs/design/shots/` holds the earlier views; the v2 shots come from `tools/shotkit/pages-v2-real.txt` and `pages-v2-demo.txt` and are not stored in the repository.
