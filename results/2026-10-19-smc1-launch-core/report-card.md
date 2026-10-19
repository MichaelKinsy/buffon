# buffon report card

Family scores per entry (reference = 70, C-). Losses against the reference are listed first; a cell marked LOSS scores under 70.

## Losses first

- copilot / core: 53 (F), 3.21x the reference's cost
- pi-bun / core: 67 (D+), 1.23x the reference's cost

## Entry x family

| entry | core | ext10 | streaming | large-write | long-session | scale | search | reliability | devloop | overall |
|---|---|---|---|---|---|---|---|---|---|---|
| pi-node | 70 C- | not run | not run | not run | not run | not run | not run | not run | not run | **70 (C-)** |
| claude-code | N/A not yet measurable | not run | not run | not run | not run | not run | not run | not run | not run | no score |
| codex | N/A not yet measurable | not run | not run | not run | not run | not run | not run | not run | not run | no score |
| copilot | 53 F LOSS | not run | not run | not run | not run | not run | not run | not run | not run | **53 (F)** |
| octet | N/A not yet measurable | not run | not run | not run | not run | not run | not run | not run | not run | no score |
| opencode-v2 | N/A not yet measurable | not run | not run | not run | not run | not run | not run | not run | not run | no score |
| pi-bun | 67 D+ LOSS | not run | not run | not run | not run | not run | not run | not run | not run | **67 (D+)** |
| pibolt | 91 A- | not run | not run | not run | not run | not run | not run | not run | not run | **91 (A-)** |
| pig-0.4.1 | 87 B+ | not run | not run | not run | not run | not run | not run | not run | not run | **87 (B+)** |
| pig-tip | 100 A+ | not run | not run | not run | not run | not run | not run | not run | not run | **100 (A+)** |
| rpi | 100 A+ | not run | not run | not run | not run | not run | not run | not run | not run | **100 (A+)** |

## Why a cell is not a score

| entry | family | class | reason |
|---|---|---|---|
| pi-node | ext10 | not-run | the reference has no cells in this family in this run |
| pi-node | streaming | not-run | the reference has no cells in this family in this run |
| pi-node | large-write | not-run | the method has no workload for this family yet |
| pi-node | long-session | not-run | the reference has no cells in this family in this run |
| pi-node | scale | not-run | the method has no workload for this family yet |
| pi-node | search | not-run | the method has no workload for this family yet |
| pi-node | reliability | not-run | the reference has no fault results in this run |
| pi-node | devloop | not-run | the reference has no cells in this family in this run |
| claude-code | core | NA-unmeasurable | only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak openai-completions; it does not speak openai-responses; no Pi-dialect RPC mode: `--input-format stream-json` is Claude Code's own streaming protocol, not Pi's JSONL RPC |
| claude-code | ext10 | not-run | the reference has no cells in this family in this run |
| claude-code | streaming | not-run | the reference has no cells in this family in this run |
| claude-code | large-write | not-run | the method has no workload for this family yet |
| claude-code | long-session | not-run | the reference has no cells in this family in this run |
| claude-code | scale | not-run | the method has no workload for this family yet |
| claude-code | search | not-run | the method has no workload for this family yet |
| claude-code | reliability | not-run | the reference has no fault results in this run |
| claude-code | devloop | not-run | the reference has no cells in this family in this run |
| codex | core | NA-unmeasurable | only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-completions; no Pi-dialect RPC mode |
| codex | ext10 | not-run | the reference has no cells in this family in this run |
| codex | streaming | not-run | the reference has no cells in this family in this run |
| codex | large-write | not-run | the method has no workload for this family yet |
| codex | long-session | not-run | the reference has no cells in this family in this run |
| codex | scale | not-run | the method has no workload for this family yet |
| codex | search | not-run | the method has no workload for this family yet |
| codex | reliability | not-run | the reference has no fault results in this run |
| codex | devloop | not-run | the reference has no cells in this family in this run |
| copilot | ext10 | not-run | the reference has no cells in this family in this run |
| copilot | streaming | not-run | the reference has no cells in this family in this run |
| copilot | large-write | not-run | the method has no workload for this family yet |
| copilot | long-session | not-run | the reference has no cells in this family in this run |
| copilot | scale | not-run | the method has no workload for this family yet |
| copilot | search | not-run | the method has no workload for this family yet |
| copilot | reliability | not-run | the reference has no fault results in this run |
| copilot | devloop | not-run | the reference has no cells in this family in this run |
| octet | core | NA-unmeasurable | only 6 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses |
| octet | ext10 | not-run | the reference has no cells in this family in this run |
| octet | streaming | not-run | the reference has no cells in this family in this run |
| octet | large-write | not-run | the method has no workload for this family yet |
| octet | long-session | not-run | the reference has no cells in this family in this run |
| octet | scale | not-run | the method has no workload for this family yet |
| octet | search | not-run | the method has no workload for this family yet |
| octet | reliability | not-run | the reference has no fault results in this run |
| octet | devloop | not-run | the reference has no cells in this family in this run |
| opencode-v2 | core | NA-unmeasurable | only 4 of the reference's 18 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses; no Pi-dialect RPC mode: V2 has an HTTP server API (`opencode serve`, `opencode api`) and ACP, neither is Pi's JSONL RPC |
| opencode-v2 | ext10 | not-run | the reference has no cells in this family in this run |
| opencode-v2 | streaming | not-run | the reference has no cells in this family in this run |
| opencode-v2 | large-write | not-run | the method has no workload for this family yet |
| opencode-v2 | long-session | not-run | the reference has no cells in this family in this run |
| opencode-v2 | scale | not-run | the method has no workload for this family yet |
| opencode-v2 | search | not-run | the method has no workload for this family yet |
| opencode-v2 | reliability | not-run | the reference has no fault results in this run |
| opencode-v2 | devloop | not-run | the reference has no cells in this family in this run |
| pi-bun | ext10 | not-run | the reference has no cells in this family in this run |
| pi-bun | streaming | not-run | the reference has no cells in this family in this run |
| pi-bun | large-write | not-run | the method has no workload for this family yet |
| pi-bun | long-session | not-run | the reference has no cells in this family in this run |
| pi-bun | scale | not-run | the method has no workload for this family yet |
| pi-bun | search | not-run | the method has no workload for this family yet |
| pi-bun | reliability | not-run | the reference has no fault results in this run |
| pi-bun | devloop | not-run | the reference has no cells in this family in this run |
| pibolt | ext10 | not-run | the reference has no cells in this family in this run |
| pibolt | streaming | not-run | the reference has no cells in this family in this run |
| pibolt | large-write | not-run | the method has no workload for this family yet |
| pibolt | long-session | not-run | the reference has no cells in this family in this run |
| pibolt | scale | not-run | the method has no workload for this family yet |
| pibolt | search | not-run | the method has no workload for this family yet |
| pibolt | reliability | not-run | the reference has no fault results in this run |
| pibolt | devloop | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | ext10 | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | streaming | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | large-write | not-run | the method has no workload for this family yet |
| pig-0.4.1 | long-session | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | scale | not-run | the method has no workload for this family yet |
| pig-0.4.1 | search | not-run | the method has no workload for this family yet |
| pig-0.4.1 | reliability | not-run | the reference has no fault results in this run |
| pig-0.4.1 | devloop | not-run | the reference has no cells in this family in this run |
| pig-tip | ext10 | not-run | the reference has no cells in this family in this run |
| pig-tip | streaming | not-run | the reference has no cells in this family in this run |
| pig-tip | large-write | not-run | the method has no workload for this family yet |
| pig-tip | long-session | not-run | the reference has no cells in this family in this run |
| pig-tip | scale | not-run | the method has no workload for this family yet |
| pig-tip | search | not-run | the method has no workload for this family yet |
| pig-tip | reliability | not-run | the reference has no fault results in this run |
| pig-tip | devloop | not-run | the reference has no cells in this family in this run |
| rpi | ext10 | not-run | the reference has no cells in this family in this run |
| rpi | streaming | not-run | the reference has no cells in this family in this run |
| rpi | large-write | not-run | the method has no workload for this family yet |
| rpi | long-session | not-run | the reference has no cells in this family in this run |
| rpi | scale | not-run | the method has no workload for this family yet |
| rpi | search | not-run | the method has no workload for this family yet |
| rpi | reliability | not-run | the reference has no fault results in this run |
| rpi | devloop | not-run | the reference has no cells in this family in this run |

Classes (from the arm manifests and the run, never by hand): NA-scope is excluded from the mean and counts against coverage; NA-missing scores 0; NA-unmeasurable gives the entry no overall score until Buffon can drive it; NA-held is not listed; not-run is a family with no workload or no reference data in this run.

