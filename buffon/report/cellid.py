# SPDX-License-Identifier: Apache-2.0
"""Cell ids: the stable name of one cell of a report and the exact command that measures it again (`buffon rerun <cell id>`).

A cell id is `<run id>::<workload>@<api>#<metric>`: the run directory's name, the workload id, the wire API (`-` when the workload does not depend on one) and the metric. It is made from the
data only, so the same run directory always gives the same ids; the report generator is the only writer of them."""

SEP = "::"
RUN_COMMAND = "python3 -m buffon rerun"


class CellIdError(ValueError):
    pass


def make(run_id, scenario, api, metric):
    return f"{run_id}{SEP}{scenario}@{api or '-'}#{metric}"


def parse(cell_id):
    """(run id, workload, api or None, metric), or CellIdError."""
    run_id, sep, rest = cell_id.partition(SEP)
    scenario, at, rest = rest.partition("@")
    api, hash_, metric = rest.partition("#")
    if not (sep and at and hash_ and run_id and scenario and api and metric) or "/" in run_id or "/" not in scenario:
        raise CellIdError(f"{cell_id!r} is not a cell id: expected <run id>{SEP}<workload>@<api>#<metric>, for example my-run{SEP}overhead/print@openai-completions#cpu_ms")
    return run_id, scenario, None if api == "-" else api, metric


def rerun_command(cell_id):
    return f"{RUN_COMMAND} {cell_id}"
