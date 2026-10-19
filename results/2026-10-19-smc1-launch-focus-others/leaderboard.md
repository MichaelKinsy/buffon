# Buffon leaderboard: Pi Harness Score

**Trust: Dedicated** (host class A). adaptive stopping: 6 of 6 cells stopped with fewer than 12 rounds (7-8) because their answer was clear; the 12-round minimum applies to the Verified badge; 7 measured rounds in the thinnest cell (the minimum for a headline is 12); uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare)

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 4.

## Pi-faithful entries (faithfulness 90 or more)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

## Faithfulness not measured (ranked apart until it is)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | rpi (rpi (Rust port of Pi)) | **97 (A)** | not measured | 1/9 (8 not run) | release archive; 28.6 MB; linux-x64 | 97-97 | 97-99, rank 1-1 |
| 2 | copilot (GitHub Copilot CLI) | **51 (F)** | not measured | 1/9 (8 not run) | npm ci --ignore-scripts; 183.8 MB + node 199 MB; linux-x64 | 50-51 | 51-52, rank 2-2 |

## No overall score

| entry | coverage | why there is no overall score | faithfulness |
|---|---|---|---|
| claude-code (Claude Code) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak openai-completions; it does not speak open | not measured |
| codex (Codex CLI) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak open | not measured |
| octet (Octet) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak open | not measured |
| opencode-v2 (OpenCode 2) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (the reference has no cells in this family in this run); ext10 (the reference has no cells in this family in this run); streaming (only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak open | not measured |

## Below the reference

- **copilot**: streaming 51 (F) at 3.80x the reference's cost

*Quiet dedicated hardware: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*

