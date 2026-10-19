# Buffon leaderboard: Pi Harness Score

**Trust: Dedicated** (host class A). adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-9) because their answer was clear; the 12-round minimum applies to the Verified badge; 8 measured rounds in the thinnest cell (the minimum for a headline is 12); uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare)

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 7.

## Pi-faithful entries (faithfulness 90 or more)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

## Faithfulness not measured (ranked apart until it is)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pibolt (Pi-Bolt) | **93 (A)** | not measured | 1/9 (8 not run) | release archive; 267.5 MB; linux-x64 | 93-93 | 93-95, rank 1-2 |
| 2 | pig-tip (PiG 0.5.0) | **92 (A-)** | not measured | 1/9 (8 not run) | source build; 70.2 MB; linux-x64 | 91-92 | 92-97, rank 1-2 |
| 3 | pig-0.4.1 (PiG 0.4.1) | **73 (C)** | not measured | 1/9 (8 not run) | release archive; 63.8 MB; linux-x64 | 72-73 | 73-73, rank 3-3 |
| 4 | pi-bun (Pi on Bun) | **66 (D)** | not measured | 1/9 (8 not run) | release archive; 114.5 MB; linux-x64 | 65-66 | 62-66, rank 4-4 |

## Below the reference

- **pi-bun**: streaming 66 (D) at 1.34x the reference's cost

*Quiet dedicated hardware: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*

