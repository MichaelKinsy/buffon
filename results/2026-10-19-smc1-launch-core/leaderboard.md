# Buffon leaderboard: Pi Harness Score

**Trust: Dedicated** (host class A). uncontained: the arms were not run in the container envelope; not yet reproduced (buffon reproduce / compare)

Method version 1 (`c585418aa131`), weights profile `default`, reference `pi-node` = 70 (C-) in every family. A score of 70 is the reference's; each halving of cost in a family is +10 points and each doubling -10. A letter is the school band of the rounded score (A 90, B 80, C 70, D 60, F below; + and - at the top and bottom 3 points). Run notes: 3.

## Pi-faithful entries (faithfulness 90 or more)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 | pi-node (Pi on Node) | **70 (C-)** | 100 | 1/9 (8 not run) | npm ci --ignore-scripts; 110.6 MB + node 199 MB; linux-x64 | 70-70 | 70-70, rank 1-1 |

## Faithfulness not measured (ranked apart until it is)

| rank (range) | entry | Pi Harness Score | Pi-faithful | coverage | cost | interval | across weight profiles |
|---|---|---|---:|---|---|---|---|
| 1 (1-2) | pig-tip (PiG 0.5.0) | **100 (A+)** | not measured | 1/9 (8 not run) | source build; 70.2 MB; linux-x64 | 100-100 | 100-100, rank 1-1 |
| 1 (1-2) | rpi (rpi (Rust port of Pi)) | **100 (A+)** | not measured | 1/9 (8 not run) | release archive; 28.6 MB; linux-x64 | 100-100 | 100-100, rank 1-1 |
| 3 | pibolt (Pi-Bolt) | **91 (A-)** | not measured | 1/9 (8 not run) | release archive; 267.5 MB; linux-x64 | 91-91 | 83-98, rank 3-4 |
| 4 | pig-0.4.1 (PiG 0.4.1) | **87 (B+)** | not measured | 1/9 (8 not run) | release archive; 63.8 MB; linux-x64 | 87-87 | 86-89, rank 3-4 |
| 5 | pi-bun (Pi on Bun) | **67 (D+)** | not measured | 1/9 (8 not run) | release archive; 114.5 MB; linux-x64 | 67-67 | 66-68, rank 5-5 |
| 6 | copilot (GitHub Copilot CLI) | **53 (F)** | not measured | 1/9 (8 not run) | npm ci --ignore-scripts; 183.8 MB + node 199 MB; linux-x64 | 53-53 | 51-55, rank 6-6 |

Entries whose 95% intervals overlap are tied in rank: a range in brackets is the best and worst rank the interval allows. If the rank changes across the four weight profiles (equal, cpu-heavy, memory-heavy, extension-heavy) the last column says so.

## No overall score

| entry | coverage | why there is no overall score | faithfulness |
|---|---|---|---|
| claude-code (Claude Code) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak openai-completions; it does not speak openai-responses; no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC); e | not measured |
| codex (Codex CLI) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-completions; no Pi-dialect RPC mode); ext10 (the reference has no cells in this family in this run); streaming (the reference h | not measured |
| octet (Octet) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 6 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses); ext10 (the reference has no cells in this family in this run); streaming (the reference has no cells in this family | not measured |
| opencode-v2 (OpenCode 2) | 0/9 (1 not yet measurable, 8 not run) | no family has a score yet: core (only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses; no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL  | not measured |

## Below the reference

- **copilot**: core 53 (F) at 3.21x the reference's cost
- **pi-bun**: core 67 (D+) at 1.23x the reference's cost

*Quiet dedicated hardware: Pi Harness Score method 1; recompute with `buffon grade --weights FILE` from report.json.*

