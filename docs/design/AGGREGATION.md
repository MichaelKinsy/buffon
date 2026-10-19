# Design: aggregation (parts, sessions, hosts, and external results)

Status: design; the multi-directory merge of `buffon report` exists, the rest is built after the launch gates and the flip.

## Why it matters

A published result comes from many run directories: workload parts that each fit one 45-minute bench-slot acquisition, at least two independent sessions, and possibly several hosts of one class. The report must combine them without hiding disagreement, and must never mix in numbers that did not come from Buffon's rules.

## Units

- **Part**: one run directory (one `buffon session`). It holds the reference arm, its A/A copy and the arms of its group, so every part is self-contained for paired analysis and passes `buffon verify` alone.
- **Session**: the set of parts taken on one boot (`host.json` `boot_id`) of one host. Two parts on one boot are one session.
- **Cell**: (arm, workload, api, metric). A cell's samples from several parts of the same session are pooled only when the parts share the protocol digest: `arms.lock` sha256, the workload set version, the mock version, the parameters (rounds, thinking times, session length), the host class and the isolation stamp. Parts that differ in any of them are never pooled.

## Combining

1. Within a session: pool the rounds of a cell across its parts (they are paired by round inside each part, so the pairing is computed per part and the per-round ratios are pooled). Report n, the pooled median ratio with a bootstrap CI over rounds, the A/A floor as the largest of the parts' floors (a pooled run is no quieter than its noisiest part).
2. Across sessions (rule 13: a headline needs at least two): report each session's ratio and CI side by side and the between-session spread. The run notes say when the sessions disagree beyond the margins (METHODOLOGY section 11), and a headline with one session says so. Sessions are never averaged into one number that hides their spread.
3. Across hosts of one class: the same as sessions, one more level; hosts of different classes are never combined (class B results are provisional and appear in their own table).
4. The report prints, per headline cell, which parts and sessions it used (run dir names and `boot_id`), so a reader can open the raw samples.

## What can never be combined

- Samples with different isolation stamps (container against uncontained).
- Samples from a part that `buffon verify` rejects.
- External results and external-suite output (below).

## External suites and external results

Two separate things, both kept out of every Buffon aggregate:

- **External suites** (family `external`): an upstream benchmark run as-is on an arm (durable's `bench:storage`, `bench:storage:memory`, `bench:tool-output` on Pi Node and PiG native or TinyGo; Pi's `packages/evals`; Pi-Bolt's suite). The suite is pinned by commit, its licence recorded, its command line and environment stored verbatim, its output stored raw next to `host.json` and the provenance; it runs inside a bench-slot acquisition like anything else. The result is shown in its own table, "External suites", labelled "run as-is by the upstream's own harness: not a Buffon workload". It enters a Buffon aggregate only when the same measurement is reproduced as a Buffon workload with a protocol digest and Buffon's rules; then Buffon workload is the number and the suite output is the cross-check.
- **External results**: published numbers imported for comparison (Pi-Bolt's BENCHMARKS.md raw JSONL, MIT). Each row carries source URL, commit or version, host description as published, licence, date and the import date; the rows live in `external/results/<source>/` with the original file's sha256, and the report prints them in an "External results" table that never joins a cell, a ratio or a floor. Sources whose licence forbids copying are linked, not imported (cite-only list in `docs/HARNESS-SURVEY.md`).

## Build order

1. `buffon aggregate` (or `buffon report` with a protocol-digest check): refuse to pool unequal digests, print the parts and sessions used. 2. Session grouping by `boot_id` and the between-session columns. 3. `external/results` importer and the two external tables, with the guard test that an imported row never reaches `cells`. 4. The suite runner (`buffon external run <suite> --arm ...`) with the provenance record. 5. `buffon verify` checks for the digest and session rules.
