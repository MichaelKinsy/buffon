# The Pi Harness Score

One number per entry, one leaderboard, one report card. The method is fixed in `workloads/grade.toml` (method version 1) before any run it judges. `buffon report` writes `grade.json`, `leaderboard.md`, `report-card.md` (and HTML) next to `report.md`; `buffon grade DIR --weights FILE` recomputes the grade from `report.json` alone, and refuses a `report.json` written with another `grade.toml` (method version and sha256 differ): run `buffon report` again.

## Entries
An entry is an arm: a configuration someone can install and run. Every entry runs every family. A family an entry has no score in carries one N/A class (below), never "not configured".

## Families
| family | scored from | direction |
|---|---|---|
| core | `overhead/print`, `print-tools`, `rpc`, `pty`: `cpu_ms`, `peak_rss_mib` | lower |
| ext10 | `overhead/*-ext10`: `cpu_ms`, `peak_rss_mib` | lower |
| streaming | `streaming/*`: CPU per 1k tokens, wall to the final frame | lower |
| long-session | `longsession/grow-*`: turn CPU, peak RSS; `resume-n`, `resume-n10`, `resume-4m2`: ready CPU and RSS (the varied twins are not graded) | lower |
| reliability | fraction of fault scenarios passed (reference's fraction over the entry's); not run when the reference passed none | higher |
| devloop | `devloop/*`: wall | lower |
| large-write, scale, search | no workload yet: listed, never scored, counted against coverage | |

## From ratios to the number
Where a cell has an instruction twin (`instructions` for `cpu_ms`, `*instructions_per_1k_tokens` for `*cpu_ms_per_1k_tokens`), the grade uses the instruction cell and leaves the CPU-time cell out, so one CPU cost is never counted twice and instructions are never mixed with CPU time in one number (`workloads/grade.toml`). The table above lists the metrics each family scores; read `cpu_ms` there as the fallback where a host has no counters.

1. A cell's ratio is the entry's median over the reference's, paired by round (`report.json` carries every ratio, interval and A/A floor). A ratio inside the A/A floor of the comparison counts as exactly 1 ("no measurable difference"). The tie is applied per cell. A cell the entry's manifest declares as different work (`[[divergence]]`, METHODOLOGY.md section 15) has no ratio and is left out for that entry only; it also comes out of the reference's cell count the entry's share is taken against.
2. A family's cost ratio is the geometric mean of its cells' ratios, weighted by the metric kind (`cpu`, `memory`, `time`).
3. Family score = clamp(70 - 10 log2 r, 0, 100). The reference scores 70 in every family. Each halving of cost is +10, each doubling -10: 100 is 8x cheaper, 0 is 128x costlier.
4. Overall = weighted mean of the family scores the entry has, rounded half up. Default weights: core 2, ext10 2, streaming 2, reliability 2, large-write 1, long-session 1, scale 1, search 1, devloop 1.
5. Letter: A 90, B 80, C 70, D 60, F below; `+` for the top 3 points of a band, `-` for the bottom 3 (A+ is 98 or more; F has neither). The reference is 70, C-.

## Gates
- **Correctness**: a family in which any measured sample of the entry failed (`gate_max_failed_fraction = 0`) scores 0. The reference is never gated, and an entry's failed sample does not count when the reference failed a measured sample of the same scenario and API (the workload does not run there; it says nothing about the entry). A failed sample is never dropped from `raw.json`.
- **Coverage floor**: fewer than 6 families scored is a *partial grade*: the score is computed from the families that have one and the entry's `caveats` say it is under the floor. `buffon grade --strict` gives no overall score instead (the card still shows the family scores). Families without a workload count against coverage, so with the workloads of method version 1 an entry must score every family that has one.
- **Cell share**: a family is covered when the entry has a usable ratio (positive and finite) in at least half of the reference's cells in it.
- **Run notes**: the run's notes (docs/HEALTH.md) never change a score and never remove one. `grade.json` records how many there are.
- **Missing facts**: a family that could not be measured, or a missing reference manifest, no longer stops the grade: it is computed from what there is, the grade's `missing` list and each entry's `caveats` name the gap, and the grade carries the run's trust badge (METHODOLOGY section 18). `--strict` refuses instead.
- **Correctness**: a faithfulness correctness failure (a tool that leaves wrong files or a wrong result, a crash, a hang; docs/FAITHFULNESS.md) scores `core`, `ext10` and `long-session` as 0 for that entry (`[gate] correctness_families`). Presentation and semantics differences never gate.
- **Faithfulness** is never a weight. Under 90 the entry is ranked in its own table (`not Pi-equivalent`); without a faithfulness run it is ranked apart (`faithfulness not measured`). Pi (the reference arm) is 100 by definition; every other arm, including another `pi-reference` arm such as Pi on Bun, has the score its faithfulness run measured. Give scores with `buffon report --faithfulness DIR...` or `buffon grade --faithfulness DIR...`.
- **Provisional**: a run that is not on quiet dedicated hardware prints every score with PROVISIONAL and is never a public leaderboard row.

## N/A classes
Chosen from the arm manifest and the run, never by hand. A manifest declares `claims` (a list of `pi-extensions`, `pi-sessions`, `pi-rpc`); without the key they are derived from `capabilities` and `modes`/`cannot_run`.

| class | when | effect on the overall |
|---|---|---|
| NA-scope | the entry does not claim a capability the family needs (`ext10` needs `pi-extensions`, `long-session` needs `pi-rpc` and `pi-sessions`) | left out of the mean, counts against coverage |
| NA-missing | a Pi port, fork or compatible harness lacks `pi-rpc`, a core capability it cannot declare out of scope | scored 0 in the mean, counts against coverage |
| NA-unmeasurable | the entry claims the capability but Buffon produced no (or too few) samples (no base-URL setting, no headless mode, egress at start), or the run carries no claims | no overall score; shown as not yet measurable with the reason; never ranked |
| NA-held | licence or terms block running it | not listed |
| not-run | the method has no workload for the family, the reference has no cells in it in this run, or the entry declares different work in every cell of it | left out of the mean, counts against coverage |

Coverage prints as `7/9 (1 out of scope, 1 not run)`.

## Weights and robustness
`--weights FILE` is TOML with `[families]` and/or `[kinds]` tables of non-negative numbers; it overrides the chosen `--profile` key by key. Bands, gates and the family list are the method's: a file that names them is refused, and changing them is a new method version. Every leaderboard row prints the score and rank range across the four published profiles (`equal`, `cpu-heavy`, `memory-heavy`, `extension-heavy`).

The interval is a 95% percentile bootstrap of the overall score over rounds (one draw of rounds shared by every cell, seeded). Gates, NA classes, reliability and the A/A floors stay as measured. Entries whose intervals overlap share a rank range.

## Honesty rules
Every entry is scored by the same code, ours included. Losses are listed first in the card and under the leaderboard. The method version and the hash of `grade.toml` are on every output.
