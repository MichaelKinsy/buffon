# buffon report card

Family scores per entry (reference = 70, C-). Losses against the reference are listed first; a cell marked LOSS scores under 70.

## Losses first

- copilot / streaming: 51 (F), 3.80x the reference's cost

## Entry x family

| entry | core | ext10 | streaming | large-write | long-session | scale | search | reliability | devloop | overall |
|---|---|---|---|---|---|---|---|---|---|---|
| pi-node | not run | not run | 70 C- | not run | not run | not run | not run | not run | not run | **70 (C-)** |
| claude-code | not run | not run | N/A not yet measurable | not run | not run | not run | not run | not run | not run | no score |
| codex | not run | not run | N/A not yet measurable | not run | not run | not run | not run | not run | not run | no score |
| copilot | not run | not run | 51 F LOSS | not run | not run | not run | not run | not run | not run | **51 (F)** |
| octet | not run | not run | N/A not yet measurable | not run | not run | not run | not run | not run | not run | no score |
| opencode-v2 | not run | not run | N/A not yet measurable | not run | not run | not run | not run | not run | not run | no score |
| rpi | not run | not run | 97 A | not run | not run | not run | not run | not run | not run | **97 (A)** |

## Why a cell is not a score

| entry | family | class | reason |
|---|---|---|---|
| pi-node | core | not-run | the reference has no cells in this family in this run |
| pi-node | ext10 | not-run | the reference has no cells in this family in this run |
| pi-node | large-write | not-run | the method has no workload for this family yet |
| pi-node | long-session | not-run | the reference has no cells in this family in this run |
| pi-node | scale | not-run | the method has no workload for this family yet |
| pi-node | search | not-run | the method has no workload for this family yet |
| pi-node | reliability | not-run | the reference has no fault results in this run |
| pi-node | devloop | not-run | the reference has no cells in this family in this run |
| claude-code | core | not-run | the reference has no cells in this family in this run |
| claude-code | ext10 | not-run | the reference has no cells in this family in this run |
| claude-code | streaming | NA-unmeasurable | only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak openai-completions; it does not speak openai-responses |
| claude-code | large-write | not-run | the method has no workload for this family yet |
| claude-code | long-session | not-run | the reference has no cells in this family in this run |
| claude-code | scale | not-run | the method has no workload for this family yet |
| claude-code | search | not-run | the method has no workload for this family yet |
| claude-code | reliability | not-run | the reference has no fault results in this run |
| claude-code | devloop | not-run | the reference has no cells in this family in this run |
| codex | core | not-run | the reference has no cells in this family in this run |
| codex | ext10 | not-run | the reference has no cells in this family in this run |
| codex | streaming | NA-unmeasurable | only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-completions |
| codex | large-write | not-run | the method has no workload for this family yet |
| codex | long-session | not-run | the reference has no cells in this family in this run |
| codex | scale | not-run | the method has no workload for this family yet |
| codex | search | not-run | the method has no workload for this family yet |
| codex | reliability | not-run | the reference has no fault results in this run |
| codex | devloop | not-run | the reference has no cells in this family in this run |
| copilot | core | not-run | the reference has no cells in this family in this run |
| copilot | ext10 | not-run | the reference has no cells in this family in this run |
| copilot | large-write | not-run | the method has no workload for this family yet |
| copilot | long-session | not-run | the reference has no cells in this family in this run |
| copilot | scale | not-run | the method has no workload for this family yet |
| copilot | search | not-run | the method has no workload for this family yet |
| copilot | reliability | not-run | the reference has no fault results in this run |
| copilot | devloop | not-run | the reference has no cells in this family in this run |
| octet | core | not-run | the reference has no cells in this family in this run |
| octet | ext10 | not-run | the reference has no cells in this family in this run |
| octet | streaming | NA-unmeasurable | only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses |
| octet | large-write | not-run | the method has no workload for this family yet |
| octet | long-session | not-run | the reference has no cells in this family in this run |
| octet | scale | not-run | the method has no workload for this family yet |
| octet | search | not-run | the method has no workload for this family yet |
| octet | reliability | not-run | the reference has no fault results in this run |
| octet | devloop | not-run | the reference has no cells in this family in this run |
| opencode-v2 | core | not-run | the reference has no cells in this family in this run |
| opencode-v2 | ext10 | not-run | the reference has no cells in this family in this run |
| opencode-v2 | streaming | NA-unmeasurable | only 4 of the reference's 12 cells have a ratio: claims the capabilities but Buffon could not drive it: it does not speak anthropic-messages; it does not speak openai-responses |
| opencode-v2 | large-write | not-run | the method has no workload for this family yet |
| opencode-v2 | long-session | not-run | the reference has no cells in this family in this run |
| opencode-v2 | scale | not-run | the method has no workload for this family yet |
| opencode-v2 | search | not-run | the method has no workload for this family yet |
| opencode-v2 | reliability | not-run | the reference has no fault results in this run |
| opencode-v2 | devloop | not-run | the reference has no cells in this family in this run |
| rpi | core | not-run | the reference has no cells in this family in this run |
| rpi | ext10 | not-run | the reference has no cells in this family in this run |
| rpi | large-write | not-run | the method has no workload for this family yet |
| rpi | long-session | not-run | the reference has no cells in this family in this run |
| rpi | scale | not-run | the method has no workload for this family yet |
| rpi | search | not-run | the method has no workload for this family yet |
| rpi | reliability | not-run | the reference has no fault results in this run |
| rpi | devloop | not-run | the reference has no cells in this family in this run |

Classes (from the arm manifests and the run, never by hand): NA-scope is excluded from the mean and counts against coverage; NA-missing scores 0; NA-unmeasurable gives the entry no overall score until Buffon can drive it; NA-held is not listed; not-run is a family with no workload or no reference data in this run.

