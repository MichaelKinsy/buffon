# buffon report card — PROVISIONAL

Family scores per entry (reference = 70, C-). Losses against the reference are listed first; a cell marked LOSS scores under 70.

## Losses first — PROVISIONAL

- pi-bun / core: 66 (D), 1.28x the reference's cost
- pi-bun / ext10: 68 (D+), 1.15x the reference's cost
- pig-0.4.1 / ext10: 47 (F), 4.89x the reference's cost
- pig-tip / ext10: 61 (D-), 1.82x the reference's cost

## Entry x family — PROVISIONAL

| entry | core | ext10 | streaming | large-write | long-session | scale | search | reliability | devloop | overall |
|---|---|---|---|---|---|---|---|---|---|---|
| pi-node | 70 C- | 70 C- | not run | not run | not run | not run | not run | not run | not run | **70 (C-)** PROVISIONAL |
| pi-bun | 66 D LOSS | 68 D+ LOSS | not run | not run | not run | not run | not run | not run | not run | **67 (D+)** PROVISIONAL |
| pibolt | 91 A- | 86 B | not run | not run | not run | not run | not run | not run | not run | **89 (B+)** PROVISIONAL |
| pig-0.4.1 | 85 B | 47 F LOSS | not run | not run | not run | not run | not run | not run | not run | **66 (D)** PROVISIONAL |
| pig-tip | 92 A- | 61 D- LOSS | not run | not run | not run | not run | not run | not run | not run | **76 (C)** PROVISIONAL |

## Why a cell is not a score

| entry | family | class | reason |
|---|---|---|---|
| pi-node | streaming | not-run | the reference has no cells in this family in this run |
| pi-node | large-write | not-run | the method has no workload for this family yet |
| pi-node | long-session | not-run | the reference has no cells in this family in this run |
| pi-node | scale | not-run | the method has no workload for this family yet |
| pi-node | search | not-run | the method has no workload for this family yet |
| pi-node | reliability | not-run | the reference has no fault results in this run |
| pi-node | devloop | not-run | the reference has no cells in this family in this run |
| pi-bun | streaming | not-run | the reference has no cells in this family in this run |
| pi-bun | large-write | not-run | the method has no workload for this family yet |
| pi-bun | long-session | not-run | the reference has no cells in this family in this run |
| pi-bun | scale | not-run | the method has no workload for this family yet |
| pi-bun | search | not-run | the method has no workload for this family yet |
| pi-bun | reliability | not-run | the reference has no fault results in this run |
| pi-bun | devloop | not-run | the reference has no cells in this family in this run |
| pibolt | streaming | not-run | the reference has no cells in this family in this run |
| pibolt | large-write | not-run | the method has no workload for this family yet |
| pibolt | long-session | not-run | the reference has no cells in this family in this run |
| pibolt | scale | not-run | the method has no workload for this family yet |
| pibolt | search | not-run | the method has no workload for this family yet |
| pibolt | reliability | not-run | the reference has no fault results in this run |
| pibolt | devloop | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | streaming | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | large-write | not-run | the method has no workload for this family yet |
| pig-0.4.1 | long-session | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | scale | not-run | the method has no workload for this family yet |
| pig-0.4.1 | search | not-run | the method has no workload for this family yet |
| pig-0.4.1 | reliability | not-run | the reference has no fault results in this run |
| pig-0.4.1 | devloop | not-run | the reference has no cells in this family in this run |
| pig-tip | streaming | not-run | the reference has no cells in this family in this run |
| pig-tip | large-write | not-run | the method has no workload for this family yet |
| pig-tip | long-session | not-run | the reference has no cells in this family in this run |
| pig-tip | scale | not-run | the method has no workload for this family yet |
| pig-tip | search | not-run | the method has no workload for this family yet |
| pig-tip | reliability | not-run | the reference has no fault results in this run |
| pig-tip | devloop | not-run | the reference has no cells in this family in this run |

Classes (from the arm manifests and the run, never by hand): NA-scope is excluded from the mean and counts against coverage; NA-missing scores 0; NA-unmeasurable gives the entry no overall score until Buffon can drive it; NA-held is not listed; not-run is a family with no workload or no reference data in this run.

