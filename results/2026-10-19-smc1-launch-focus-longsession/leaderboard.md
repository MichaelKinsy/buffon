# Buffon leaderboard: Pi Harness Score — PROVISIONAL

> **PROVISIONAL.** The run was not on quiet dedicated hardware by the runner's own detection. These grades are for reading, never for publication, and never a public leaderboard row.
>
> - run 1: adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge
> - run 1: 3 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting

**Trust: Dedicated** (host class A). 3 sample(s) waited for the host to quiet down (longest 2 s); adaptive stopping: 2 of 2 cells stopped with fewer than 12 rounds (8-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 3 samples waited for the host to quiet down (longest 2 s) and 0 gave up waiting; the run is not labelled quiet dedicated hardware

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 4.

## Pi-faithful entries (faithfulness 90 or more) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** PROVISIONAL | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

## Faithfulness not measured (ranked apart until it is) — PROVISIONAL

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pig-tip (PiG 0.5.0) | **90 (A-)** PROVISIONAL | not measured | 1/9 (8 not run) | source build; 70.2 MB; linux-x64 | 90-90 | 86-94, rank 1-2 |
| 2 | pibolt (Pi-Bolt) | **88 (B+)** PROVISIONAL | not measured | 1/9 (8 not run) | release archive; 267.5 MB; linux-x64 | 88-88 | 81-95, rank 1-3 |
| 3 | pig-0.4.1 (PiG 0.4.1) | **86 (B)** PROVISIONAL | not measured | 1/9 (8 not run) | release archive; 63.8 MB; linux-x64 | 86-86 | 84-87, rank 2-3 |
| 4 | pi-bun (Pi on Bun) | **65 (D)** PROVISIONAL | not measured | 1/9 (8 not run) | release archive; 114.5 MB; linux-x64 | 65-65 | 64-66, rank 4-4 |

## Below the reference — PROVISIONAL

- **pi-bun**: long-session 65 (D) at 1.39x the reference's cost

*PROVISIONAL: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*

