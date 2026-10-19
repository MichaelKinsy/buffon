# Buffon leaderboard: Pi Harness Score — PROVISIONAL

> **PROVISIONAL.** The run was not on quiet dedicated hardware by the runner's own detection. These grades are for reading, never for publication, and never a public leaderboard row.
>
> - run 1: adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge
> - run 1: 1 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting

**Trust: Dedicated** (host class A). 1 sample(s) waited for the host to quiet down (longest 2 s); adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 1 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting; the run is not labelled quiet dedicated hardware

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 4.

## Pi-faithful entries (faithfulness 90 or more) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** PROVISIONAL | 100 | 2/9 (7 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

## Faithfulness not measured (ranked apart until it is) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pibolt (Pi-Bolt) | **89 (B+)** PROVISIONAL | not measured | 2/9 (7 not run) | release archive; 267.5 MB; linux-x64 | 89-89 | 82-96, rank 1-1 |
| 2 | pig-tip (PiG 0.5.0) | **76 (C)** PROVISIONAL | not measured | 2/9 (7 not run) | source build; 70.2 MB; linux-x64 | 76-77 | 69-79, rank 2-2 |
| 3 | pi-bun (Pi on Bun) | **67 (D+)** PROVISIONAL | not measured | 2/9 (7 not run) | release archive; 114.5 MB; linux-x64 | 67-67 | 66-68, rank 3-3 |
| 4 | pig-0.4.1 (PiG 0.4.1) | **66 (D)** PROVISIONAL | not measured | 2/9 (7 not run) | release archive; 63.8 MB; linux-x64 | 66-66 | 57-66, rank 4-4 |

## Below the reference — PROVISIONAL

- **pi-bun**: core 66 (D) at 1.28x the reference's cost, ext10 68 (D+) at 1.15x the reference's cost
- **pig-0.4.1**: ext10 47 (F) at 4.89x the reference's cost
- **pig-tip**: ext10 61 (D-) at 1.82x the reference's cost

*PROVISIONAL: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*

