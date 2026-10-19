# SPDX-License-Identifier: Apache-2.0
"""External suites and external results: other people's benchmarks, run as-is or cited with provenance.

Nothing here feeds Buffon's cells, aggregates or verdicts. An external suite run is a directory with `external-suite.json` (no `raw.json`); an imported result set is a directory with `external.json`.
`buffon report` refuses both (`runner.raw.read`), and the report prints them in their own sections.
"""
KIND_SUITE = "external-suite"
KIND_RESULTS = "external-results"
