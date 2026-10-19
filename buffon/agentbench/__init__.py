# SPDX-License-Identifier: Apache-2.0
"""Agent benchmarks: task pass rates of two arms on the same tasks, with real models (docs/AGENT-BENCHMARKS.md).

The bookkeeping follows the design of Pi's packages/evals (paired arms, identical cohorts, alternating order, a blocked pair withholds the headline, unavailable telemetry is not zero)
and Harbor's reporting (mean +- SEM overlap). Nothing here calls a model or Harbor: it declares the protocol, ingests observations and computes the paired result."""
from .lift import ingest, paired_result, sem_overlap  # noqa: F401
from .protocol import Protocol, expected_runs  # noqa: F401
