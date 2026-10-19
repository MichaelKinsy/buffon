# SPDX-License-Identifier: Apache-2.0
"""The files a report writes next to report.md, all from the same data: report.html (with the drift plots), rounds.csv (the per-round series), noise.csv, telemetry.csv,
health.json and plots/*.svg."""
import csv
import json
import os
import re

from . import cards as cardslib, html as htmllib
from . import series as serieslib


def slug(*parts):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", "-".join(str(p) for p in parts if p not in (None, ""))).strip("-")


def write_csv(path, columns, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)


def plots(runs, data):
    """([(cell, arms, cell svg, A/A svg)] for every cell, [host svgs])."""
    out = []
    for cell in data["cells"]:
        arms, svg = serieslib.cell_svg(cell)
        out.append((cell, arms, svg, serieslib.aa_svg(cell, data["base"])))
    return out, serieslib.host_svgs(runs)


def drift_html(cell_plots, host):
    body = ["<h2 id=\"drift\">Drift: per-round series</h2>",
            "<p>The rounds themselves, in the order they ran. Amount axes start at zero; the A/A ratio axis is centred on 1. A line that climbs or falls over the run is the host drifting; the data is in rounds.csv.</p>"]
    if host:
        body += ["<h3>Host during the run</h3>", "<div>" + "".join(host) + "</div>"]
    head = [(c, arms, svg, aa) for c, arms, svg, aa in cell_plots if c.metric in serieslib.HEADLINE and svg]
    for cell, arms, svg, aa in head:
        body.append(f"<details><summary>{cell.scenario} {serieslib.short_api(cell.api)} {cell.metric}</summary><div>{serieslib.legend(arms)}</div><div>{svg}{aa}</div></details>")
    rest = [(c, arms, svg, aa) for c, arms, svg, aa in cell_plots if c.metric not in serieslib.HEADLINE and svg]
    if rest:
        body.append(f"<p>{len(rest)} more cells have their series in plots/ (one SVG each) and in rounds.csv.</p>")
    return "\n".join(body)


def write_all(out_dir, runs, data, noise, health, md_lines, title, all_runs=None, view=None):
    """`runs` are the runs the statistics were built from (flagged rounds removed with --drop-flagged); `all_runs` are every sample as recorded, for telemetry.csv."""
    os.makedirs(os.path.join(out_dir, "plots"), exist_ok=True)
    cell_plots, host = plots(runs, data)
    for cell, arms, svg, aa in cell_plots:
        for kind, text in (("series", svg), ("aa", aa)):
            if text:
                with open(os.path.join(out_dir, "plots", slug(kind, cell.scenario.replace("/", "-"), serieslib.short_api(cell.api), cell.metric) + ".svg"), "w") as f:
                    f.write(text + "\n")
    for n, text in enumerate(host):
        with open(os.path.join(out_dir, "plots", f"host-{n + 1}.svg"), "w") as f:
            f.write(text + "\n")
    write_csv(os.path.join(out_dir, "rounds.csv"), serieslib.CSV_COLUMNS, serieslib.rows(runs, data))
    trows = serieslib.telemetry_rows(all_runs or runs)
    cols = []
    for r in trows:
        for k in r:
            if k not in cols:
                cols.append(k)
    write_csv(os.path.join(out_dir, "telemetry.csv"), cols, trows)
    write_csv(os.path.join(out_dir, "noise.csv"), ["scenario", "api", "metric", "arm", "n", "cv", "outliers", "drift", "aa_gap", "aa_floor"], noise["cells"])
    with open(os.path.join(out_dir, "health.json"), "w") as f:
        json.dump(health, f, indent=1, default=lambda x: None if isinstance(x, float) and x != x else x)
    with open(os.path.join(out_dir, "report.html"), "w") as f:
        f.write(cardslib.report_page(view, md_lines, drift_html(cell_plots, host)) if view else htmllib.page(title, md_lines, drift_html(cell_plots, host)))
