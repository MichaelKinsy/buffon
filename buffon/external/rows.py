# SPDX-License-Identifier: Apache-2.0
"""Rows from a suite's own console table, with the names it prints.

Node's console.table draws a box: the first `│` line holds the column names and each later `│` line is one row. The
names are kept exactly as printed (a unit in a name, such as `RSS after seed MiB`, stays in the name). Cell text is
kept as printed; nothing is converted, renamed or averaged.
"""


def parse_console_table(text):
    """Return a list of dicts keyed by the printed column names. Empty when the output has no table."""
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("│")]
    if not lines:
        return []
    header = [cell.strip() for cell in lines[0].strip("│").split("│")]
    rows = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in line.strip("│").split("│")]
        if len(cells) != len(header):
            raise ValueError(f"console table row has {len(cells)} cells for {len(header)} columns: {line!r}")
        rows.append(dict(zip(header, cells)))
    return rows
