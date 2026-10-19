# buffon report card — PROVISIONAL

Family scores per entry (reference = 70, C-). Losses against the reference are listed first; a cell marked LOSS scores under 70.

## Losses first — PROVISIONAL

- pi-bun / long-session: 65 (D), 1.39x the reference's cost

## Entry x family — PROVISIONAL

| entry | core | ext10 | streaming | large-write | long-session | scale | search | reliability | devloop | overall |
|---|---|---|---|---|---|---|---|---|---|---|
| pi-node | not run | not run | not run | not run | 70 C- | not run | not run | not run | not run | **70 (C-)** PROVISIONAL |
| pi-bun | not run | not run | not run | not run | 65 D LOSS | not run | not run | not run | not run | **65 (D)** PROVISIONAL |
| pibolt | not run | not run | not run | not run | 88 B+ | not run | not run | not run | not run | **88 (B+)** PROVISIONAL |
| pig-0.4.1 | not run | not run | not run | not run | 86 B | not run | not run | not run | not run | **86 (B)** PROVISIONAL |
| pig-tip | not run | not run | not run | not run | 90 A- | not run | not run | not run | not run | **90 (A-)** PROVISIONAL |

## Why a cell is not a score

| entry | family | class | reason |
|---|---|---|---|
| pi-node | core | not-run | the reference has no cells in this family in this run |
| pi-node | ext10 | not-run | the reference has no cells in this family in this run |
| pi-node | streaming | not-run | the reference has no cells in this family in this run |
| pi-node | large-write | not-run | the method has no workload for this family yet |
| pi-node | scale | not-run | the method has no workload for this family yet |
| pi-node | search | not-run | the method has no workload for this family yet |
| pi-node | reliability | not-run | the reference has no fault results in this run |
| pi-node | devloop | not-run | the reference has no cells in this family in this run |
| pi-bun | core | not-run | the reference has no cells in this family in this run |
| pi-bun | ext10 | not-run | the reference has no cells in this family in this run |
| pi-bun | streaming | not-run | the reference has no cells in this family in this run |
| pi-bun | large-write | not-run | the method has no workload for this family yet |
| pi-bun | scale | not-run | the method has no workload for this family yet |
| pi-bun | search | not-run | the method has no workload for this family yet |
| pi-bun | reliability | not-run | the reference has no fault results in this run |
| pi-bun | devloop | not-run | the reference has no cells in this family in this run |
| pibolt | core | not-run | the reference has no cells in this family in this run |
| pibolt | ext10 | not-run | the reference has no cells in this family in this run |
| pibolt | streaming | not-run | the reference has no cells in this family in this run |
| pibolt | large-write | not-run | the method has no workload for this family yet |
| pibolt | scale | not-run | the method has no workload for this family yet |
| pibolt | search | not-run | the method has no workload for this family yet |
| pibolt | reliability | not-run | the reference has no fault results in this run |
| pibolt | devloop | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | core | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | ext10 | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | streaming | not-run | the reference has no cells in this family in this run |
| pig-0.4.1 | large-write | not-run | the method has no workload for this family yet |
| pig-0.4.1 | scale | not-run | the method has no workload for this family yet |
| pig-0.4.1 | search | not-run | the method has no workload for this family yet |
| pig-0.4.1 | reliability | not-run | the reference has no fault results in this run |
| pig-0.4.1 | devloop | not-run | the reference has no cells in this family in this run |
| pig-tip | core | not-run | the reference has no cells in this family in this run |
| pig-tip | ext10 | not-run | the reference has no cells in this family in this run |
| pig-tip | streaming | not-run | the reference has no cells in this family in this run |
| pig-tip | large-write | not-run | the method has no workload for this family yet |
| pig-tip | scale | not-run | the method has no workload for this family yet |
| pig-tip | search | not-run | the method has no workload for this family yet |
| pig-tip | reliability | not-run | the reference has no fault results in this run |
| pig-tip | devloop | not-run | the reference has no cells in this family in this run |

Classes (from the arm manifests and the run, never by hand): NA-scope is excluded from the mean and counts against coverage; NA-missing scores 0; NA-unmeasurable gives the entry no overall score until Buffon can drive it; NA-held is not listed; not-run is a family with no workload or no reference data in this run.

