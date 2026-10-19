# buffon report card

Family scores per entry (reference = 70, C-). Losses against the reference are listed first; a cell marked LOSS scores under 70.

## Losses first

- pi-bun / streaming: 66 (D), 1.34x the reference's cost

## Entry x family

| entry | core | ext10 | streaming | large-write | long-session | scale | search | reliability | devloop | overall |
|---|---|---|---|---|---|---|---|---|---|---|
| pi-node | not run | not run | 70 C- | not run | not run | not run | not run | not run | not run | **70 (C-)** |
| pi-bun | not run | not run | 66 D LOSS | not run | not run | not run | not run | not run | not run | **66 (D)** |
| pibolt | not run | not run | 93 A | not run | not run | not run | not run | not run | not run | **93 (A)** |
| pig-0.4.1 | not run | not run | 73 C | not run | not run | not run | not run | not run | not run | **73 (C)** |
| pig-tip | not run | not run | 92 A- | not run | not run | not run | not run | not run | not run | **92 (A-)** |

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
| pi-bun | core | not-run | the reference has no cells in this family in this run |
| pi-bun | ext10 | not-run | the reference has no cells in this family in this run |
| pi-bun | large-write | not-run | the method has no workload for this family yet |
| pi-bun | long-session | not-run | the reference has no cells in this family in this run |
| pi-bun | scale | not-run | the method has no workload for this family yet |
| pi-bun | search | not-run | the method has no workload for this family yet |
| pi-bun | reliability | not-run | the reference has no fault results in this run |
| pi-bun | devloop | not-run | the reference has no cells in this family in this run |
| pibolt | core | not-run | the reference has no cells in this family in this run |
| pibolt | ext10 | not-run | the reference has no cells in this family in this run |
| pibolt | large-write | not-run | the method has no workload for this family yet |
| pibolt | long-session | not-run | the reference has no cells in this family in this run |
| pibolt | scale | not-run | the method has no workload for this family yet |
| pibolt | search | not-run | the method has no workload for this family yet |
| pibolt | reliability | not-run | the reference has no fault results in this run |
| pibolt | devloop | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | core | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | ext10 | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | large-write | not-run | the method has no workload for this family yet |
| pig-0.4.1 | long-session | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | scale | not-run | the method has no workload for this family yet |
| pig-0.4.1 | search | not-run | the method has no workload for this family yet |
| pig-0.4.1 | reliability | not-run | the reference has no fault results in this run |
| pig-0.4.1 | devloop | not-run | the reference has no cells in this family in this run |
| pig-tip | core | not-run | the reference has no cells in this family in this run |
| pig-tip | ext10 | not-run | the reference has no cells in this family in this run |
| pig-tip | large-write | not-run | the method has no workload for this family yet |
| pig-tip | long-session | not-run | the reference has no cells in this family in this run |
| pig-tip | scale | not-run | the method has no workload for this family yet |
| pig-tip | search | not-run | the method has no workload for this family yet |
| pig-tip | reliability | not-run | the reference has no fault results in this run |
| pig-tip | devloop | not-run | the reference has no cells in this family in this run |

Classes (from the arm manifests and the run, never by hand): NA-scope is excluded from the mean and counts against coverage; NA-missing scores 0; NA-unmeasurable gives the entry no overall score until Buffon can drive it; NA-held is not listed; not-run is a family with no workload or no reference data in this run.

