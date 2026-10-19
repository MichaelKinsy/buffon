# Dashboard audit

The owner found that charts and metrics are inconsistent, that a page is not clean, simple and effective on a small screen, that text does not always earn its place,
and that the out-of-memory reporting of the Scale page is confusing. This is the audit of the site as it was (`~/buffon-live/dash-audit`, built from the three real runs
`up-33864551cd-measured`, `up-a4041fe52c-measured` and `up-3c5957b1c3-measured`), the fix of each finding, and what was kept on purpose.

Screenshots: every page (Compare, Compare in ratio mode, Scale, a swarm derivation for RPC and for print, How it works, Runs, a harness, a metric, a large-write metric, a measurement (a
grid cell), the Glossary and a document) at 1440 px and 390 px, light and dark.
Before: `~/buffon-live/shots/audit-before/`. After: `~/buffon-live/shots/audit-after/` (site `~/buffon-live/dash9`). Made with `tools/shotkit/go.sh`.

Status: **fixed** or **kept** (with the reason). The tests named are in `tests/test_dashboard_consistency.py` and `tests/test_dashboard_scale.py`.

## 1. Metric names, units and number formats

| # | Finding (where) | Status |
|---|---|---|
| N1 | `fmt` gave four significant digits with a decimal from 100 up (420.2) and three below; a ratio had three formats (`ratioStr` 3 decimals under 0.1, `fx(...,3)` on the harness page, `fx(...,2)` in intervals): the harness table showed "0.000×" for 0.0003. | Fixed: one formatter, three significant digits, ratios keep their zeros (1.50, 0.0163). |
| N2 | A time was in ms everywhere ("2,036 ms" in the grid, the metric page and the cell page) but in s on the large-write card ("36.0 s"). | Fixed: under 1 s in ms, from 1 s in s, on every view. |
| N3 | A memory was in MiB everywhere ("4,096 MiB" on the Scale charts) while the envelope said "4 GiB". | Fixed: under 1 GiB in MiB, from 1 GiB in GiB. |
| N4 | Unit labels differed: "ms of CPU time" in the unit text, "ms" in cells, "s, or ms under 1 s" in the write card header. | Fixed: a column header says "ms or s" or "MiB or GiB"; a value carries its own unit. |
| N5 | Axis ticks used three formatters (`fmtAxis`, a private `tick` on the Scale charts, the plain `fmt`), so one number read differently on the axis and in the tooltip. | Fixed: `plotFrame` labels every axis with the one formatter, in one unit chosen for the chart. |
| N6 | The large-write card named its columns "Time", "CPU time", "Peak memory"; the metric pages call the same metrics "time, 200 KB file", "CPU time, 200 KB file", "peak memory, all processes, 200 KB file". | Fixed: the card takes its column names from the metric's own word. |
| N7 | The workload `overhead/print-write` had no title, so the harness page and the metric pages showed the raw name in capitals. | Fixed: "Large file write" in `benchmarks.WORKLOADS`. |
| N8 | The tooltip, chip and table gave one ratio with 3, 2 and 2 decimals ("0.104×" and "0.10×"). | Fixed with N1. |
| N9 | The p-value was `fx(p,3)` ("0.003") but 0.0004 showed "0.000". | Fixed: "below 0.001". |
| N10 | The Scale metrics were named by the RPC kind for the print kind too ("Turns per second", "CPU per agent-turn" for a print agent that does one task). | Fixed: print says "Tasks per second" and "CPU per task". |
| N11 | **CPU per agent-turn covered the whole sample, start-up included, and turns per second covered the turn phase only**: the two charts could not be read together (Pi-Bolt faster and also costlier per turn than PiG 0.5.0). | Fixed in the model and the page: both cover the same window (the contract of `workloads/scale.py`); a run that predates the fields (envelope A) draws no RPC CPU chart and says why (see section 5). |
| N12 | The cell page gave "Each value is the median of 12 rounds" while the metric page gave the median of all rounds of the harness: two Pi medians for one metric, with no word on why. | Fixed: "the 12 rounds that both ran". The two medians differ only when a round is missing, as the design doc says. |
| N13 | The runner's own failure text on a derivation page carried raw numbers ("4096 MiB memory limit"). | Fixed: `restate` says them again in the site's format. |
| N14 | A count unit was never singular ("1 periods"). | Fixed. |

## 2. Charts

| # | Finding | Status |
|---|---|---|
| C1 | Chart sizes: 190 (histogram), 200 (cell rounds), 230 (Scale), 240 (rounds), strip plot by rows; widths clamped to 300 to 1100, and drawn smaller than the card on a phone, so text shrank with the SVG. | Fixed: height 220 for every line chart and the histogram; the width is taken from the card (`chartWidth`), so text stays 11 px at 390 px (`SmallScreen` test). The strip plot keeps its rows (it is a different chart: a row for each harness). |
| C2 | Axes differed: the unit at the top left in line charts but at the end of the axis in the strip plot; the x label "round →", "agents, each step doubles →" and "ms →". | Fixed: the unit at the top left, the x label at the bottom right, in one style. |
| C3 | The y axis of the rounds chart does not start at zero while the Scale charts do. | Kept for the rounds chart: it shows a change between rounds, not a size, and the card says so ("A line that goes up or down shows a change"). Every other line chart starts at zero. |
| C4 | Legends: a dot legend above the rounds and Scale charts, none on the histogram, names on the rows of the bar chart. | Fixed: one `legend()`; a bar chart names its rows, a line chart has the legend. |
| C5 | Harness order: the metric chart was sorted by value, the Overview tile by agents that fit, the write card by time, the Scale table by harness order. | Fixed: the site order everywhere (a reader's own sort is the only exception). Test: `OneOrder`. |
| C6 | Harness colour: assigned by position in the harness list (stable), but the Overview tile and the Scale legends reordered the harnesses, so the same colour moved around. | Fixed with C5; colours were already stable per harness (`harness_list`) and Pi keeps its own blue. Test: `test_a_harness_keeps_its_colour_in_every_view`. |
| C7 | The metric chart had its value in a separate column and bars from zero in one linear scale: 6.5 ms was a hairline next to 2,036 ms. | Fixed: the number is on the bar. Kept linear from zero: a bar from zero on a log scale would lie; the number on the bar and the ratio chip carry the small values. |
| C8 | Three scale conventions: linear bars (metric), log diverging bars (harness page), a log bar under the write time. | Harness page kept: it draws a ratio around 1 and says so on its axis. The write bar is removed (the table gives the numbers; the metric page has the chart). |
| C9 | The Scale page had six charts per kind, including the whole-container memory and the p95, as small multiples of 230 px; a stop was a cross on the top edge with no label and a point at the limit on the memory charts. | Fixed: three charts per kind (memory per agent, throughput, CPU), all on one log2 axis; a stop is a cross on the axis at its size, with its cause in the tooltip; the container memory and the p95 are in the table of every rung and in the derivation. |
| C10 | No spread across rounds anywhere on the Scale page, although the scale family now has no A/A copy. | Fixed: a whisker from the smallest to the largest round at each point, and the range in the tooltip and the derivation. |
| C11 | The Scale headline was a table of numbers and a sentence per harness ("stopped at 32 agents: out of memory, 3 OOM kills"). | Fixed: a bar chart of how many agents fit, the number on the bar, "1024 or more" for a ladder that never stopped. |

## 3. Layout, spacing and mobile

| # | Finding | Status |
|---|---|---|
| L1 | Card padding was 18/20 on cards, 6/0 on the grid card, 14/14 on the small multiples; gaps 18 and 14. | Fixed: 16/18 on every card (14 on a phone), a gap of 14. The grid card keeps edge-to-edge rows, with its header padded like the others. |
| L2 | Heading sizes: the hero h1 26 px, page h1 30 px, 21 px under 860 px, section 20 px against card 17 px. | Fixed: h1 30 px (24 px on a phone) for the hero and every page head; 19 px for a section, 17 px for a card. |
| L3 | **Scale at 390 px was 442 px wide**: the envelope table and its formula pushed the page sideways. | Fixed: key-value tables stack under 640 px; no element is wider than the screen (the shotkit checks all pages, both themes). |
| L4 | A table other than the grid scrolled sideways with its first column out of sight; the rung table has 12 round columns. | Fixed: every data table scrolls inside its card with the first column in place. |
| L5 | The bar rows of the metric chart had four columns that squeezed to nothing at 390 px. | Fixed: under 560 px the name goes above the bar. |
| L6 | The grid is wide on a phone. | Kept: it scrolls inside its card with the harness column in place; the cells keep their tooltips. A stacked layout would lose the one thing the grid is for, lining the harnesses up. |

## 4. Filters

| # | Finding | Status |
|---|---|---|
| F1 | The harness chips and the metric picker sat above the grid but under two cards (the large write, the Scale tiles) that ignored them: a chip off, and the harness was still in the write table. | Fixed: the filters sit directly above the grid and the other cards follow it; they say "the grid" by position. Test: `NoIdleControl`. |
| F2 | The baseline choice appeared only in ratio mode (correct), the wire API choice on every page that had two APIs, including pages with no API-dependent content (none found). | Kept: shown only where it works. Tests assert no `base` or `api` control on Scale, Runs, How it works, Glossary, documents and derivations. |
| F3 | "Filter rows" shows on a table of more than 10 rows. | Kept: it works, and is absent where there is nothing to filter. |
| F4 | A Chart/Table switch on every chart card. | Kept: the design rule is that every chart has a table view and a CSV. |
| F5 | A metric that has no value with the chosen API is greyed in the picker but can be chosen. | Kept: the column then says n/a with the reason; the tooltip of the chip says so first. |

## 5. Scale reporting (the confusing OOM text)

| # | Finding | Status |
|---|---|---|
| S1 | Four words for one thing: "out of memory", "OOM kills", "timeout", "stopped at 32 agents: out of memory, 3 OOM kills". A stall (the container sat at its limit, nothing killed) had no word. | Fixed: `oom` and `stall` both read "did not fit in 4 GiB"; the cause detail ("the kernel killed 12 agents", "stalled at the limit, nothing was killed") is the second line of the tooltip and of the derivation page. `timeout`, `pids`, `error` read "timed out", "hit the process limit", "failed". Test: `test_a_stall_reads_like_an_oom_kill...`. |
| S2 | The answer ("how many agents fit") was the third card, after the envelope, a lede and a table. | Fixed: the page title is "How many agents fit in 4 GiB?" and the first thing is the bars. |
| S3 | The envelope, the definition of every metric and a paragraph on rungs were open cards between the answer and the charts. | Fixed: behind one disclosure at the bottom. |
| S4 | A stopped rung's p95 and CPU were large numbers that the charts had to ignore by rule. | Fixed: only completed rungs are points; a stop is a cross. |
| S5 | Envelope A has `cpu_ms` over the whole sample and no `start_cpu_ms_per_agent`. | Fixed: the RPC CPU per agent-turn of such a sample is dropped in the model (`cpu_legacy`); the page says once, on the Scale page and on each derivation, why it is not drawn. Test: `test_a_run_that_predates_the_cpu_window...`. |
| S6 | 190 of 300 sample-minutes were spent waiting for the timeout, and 13 rounds of 2 copies. | Not a dashboard matter (runner and workload: `ScaleFix`); the page reads the new fields (`stall`, `start_cpu_ms_per_agent`) and shows the spread across rounds instead of an A/A pair. |

## 6. Text that does not earn its place

| # | Finding | Status |
|---|---|---|
| T1 | Compare: a two-sentence mission statement as the h1, a lede, and a trust line that repeated "Every number links to its raw samples" (also in the grid legend). | Fixed: one sentence ("9 harnesses, one scripted model, the same measurements."), one trust line; the invitation to add a harness moved to the footer. |
| T2 | Compare: two legend lines with four instructions that the tooltips and the headers already say. | Fixed: one line. |
| T3 | The metric page said what the metric is three times (lede, the formula card's sub, the grid's `i` tooltip), had a "Unit:" line that the table repeated, and a paragraph that repeated the glossary. | Fixed: once in the lede; the unit is in the table; the paragraph is gone. |
| T4 | The metric chart's sub had three sentences that restated the legend. | Fixed: one sentence. |
| T5 | The harness page: a sub that repeated the axis, a "Back to the grid" link that repeated the breadcrumb. | Fixed. |
| T6 | The cell page: "The gap: 9.4% less than Pi" under a 0.906× in 64 px type. | Fixed: row removed. |
| T7 | Scale: each small chart had "MiB. A lower value is better." and a foot that repeated the definition; the lede had five sentences. | Fixed: "MiB or GiB, lower is better"; the definitions are once, in the disclosure; the lede is one sentence. |
| T8 | How it works: "A few words" repeated seven entries of the Glossary. | Fixed: removed; the Glossary is in "Read more". |
| T9 | Runs: a lede, then in every run a paragraph saying that notes do not grade a run, then the long detail of each note inline. | Fixed: said once in the lede; the detail of a note is behind "Where". |
| T10 | The Glossary lede explained how a tooltip works. | Fixed: one short line. |
| T11 | The Overview Scale tile said "agents that all finished, one step is a doubling" under each kind. | Fixed: the tile is the Scale headline, with the same bars. |
| T12 | The write card carried a long sub and a legend line that repeated the grid's. | Fixed: one sentence and one line. |

## Not found in this audit

- Light and dark: contrast and the colour-blind separation are checked by `tools/palette_check.py` and `Palette` in `tests/test_dashboard.py`; the screenshots show no mark that is lost in either theme.
- Documents (`#/doc/...`): they are the repository's own markdown in the site's frame; a table scrolls inside its card. No change.
