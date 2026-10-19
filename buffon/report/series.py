# SPDX-License-Identifier: Apache-2.0
"""Per-round time series: the data behind a drift plot, as CSV rows and as dependency-free SVG.

A run's cells are medians over rounds; a series shows the rounds themselves, so a host that warmed up, cooled down or got busy halfway through is visible instead of averaged away.
  rows(runs, data)     one row per measured sample of a scored metric: where it was in the run, its value, the telemetry around it and its flags
  cell_svg(cell)       the values of every arm in a cell by round (A/A copies dashed); the axis starts at zero
  aa_svg(cell, arms)   the ratio of an arm's A/A copy to the arm, by round, around 1
  host_svg(...)        pinned-CPU busy, clock and load over the samples in the order they ran
"""
import html
import math

from . import noise as noiselib

PALETTE = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#e377c2", "#17becf", "#7f7f7f", "#bcbd22")
HEADLINE = ("cpu_ms", "wall_ms", "peak_mem_mib", "peak_rss_mib")


def short_api(api):
    return {"openai-completions": "chat", "anthropic-messages": "anthropic", "openai-responses": "responses", None: "-"}.get(api, str(api))


def rows(runs, data):
    """Long-format rows for rounds.csv, in the order the samples ran. Only scored metrics, only measured samples (warm-up and failed excluded, as in the statistics)."""
    out = []
    scored = {(c.scenario, c.api, c.metric) for c in data["cells"]}
    for i, raw in enumerate(runs, 1):
        for n, d in enumerate(noiselib.derive(raw["samples"])):
            s, f, th = d.sample, d.flags, d.throttled_us
            if s["warmup"] or "failure" in s:
                continue
            t = noiselib.system(s) or {}
            cs, cg, dur = t.get("cpuset", {}), t.get("cgroup", {}), t.get("during", {})
            for metric, v in s.items():
                if (s["scenario"], s.get("api"), metric) in scored and isinstance(v, (int, float)) and not isinstance(v, bool):
                    out.append({"run": i, "order": n, "t_utc": s.get("t_utc"), "scenario": s["scenario"], "api": s.get("api"), "metric": metric, "arm": s["arm"], "round": s["round"], "value": v,
                                "quiet_wait_ms": s.get("quiet_wait_ms"), "pinned_busy_before": s.get("pinned_busy"), "host_load1": s.get("host_load1"),
                                "cpuset_busy_ms": cs.get("cpuset_busy_ms"), "cpuset_steal_ms": cs.get("cpuset_steal_ms"), "cpuset_iowait_ms": cs.get("cpuset_iowait_ms"),
                                "mhz_mean": dur.get("mhz_mean"), "mhz_min": dur.get("mhz_min"), "mhz_max": dur.get("mhz_max"), "throttled_us": th, "cgroup_cpu_ms": cg.get("cpu_usage_ms"),
                                "flags": " ".join(f) if f else ""})
    return out


CSV_COLUMNS = ["run", "order", "t_utc", "scenario", "api", "metric", "arm", "round", "value", "quiet_wait_ms", "pinned_busy_before", "host_load1", "cpuset_busy_ms", "cpuset_steal_ms",
               "cpuset_iowait_ms", "mhz_mean", "mhz_min", "mhz_max", "throttled_us", "cgroup_cpu_ms", "flags"]


def telemetry_rows(runs):
    """One row per sample with its flattened telemetry, for telemetry.csv."""
    out = []
    for i, raw in enumerate(runs, 1):
        for n, d in enumerate(noiselib.derive(raw["samples"])):
            s, f, th = d.sample, d.flags, d.throttled_us
            t = noiselib.system(s)
            if t is None:
                continue
            row = {"run": i, "order": n, "arm": s["arm"], "scenario": s["scenario"], "api": s.get("api"), "round": s["round"], "warmup": s["warmup"], "failure": s.get("failure", ""), "flags": " ".join(f or [])}
            for group in ("before", "after", "during", "cpuset", "cgroup", "gate", "collector"):
                for k, v in (t.get(group) or {}).items():
                    if isinstance(v, (int, float, str)) or v is None:
                        row[f"{group}.{k}"] = v
                    elif isinstance(v, dict):
                        row.update({f"{group}.{k}.{kk}": vv for kk, vv in v.items()})
            out.append(row)
    return out


# -- svg --------------------------------------------------------------------------------------------------------------------------------------

W, H, ML, MR, MT, MB = 560, 220, 56, 12, 26, 34


def _scale(lo, hi, a, b):
    span = (hi - lo) or 1.0
    return lambda v: a + (v - lo) / span * (b - a)


def _nice(hi):
    if hi <= 0 or hi != hi:
        return 1.0
    mag = 10 ** math.floor(math.log10(hi))
    for m in (1, 2, 2.5, 5, 10):
        if hi <= m * mag:
            return m * mag
    return 10 * mag


def _fmt(v):
    return f"{v:.3g}" if abs(v) < 1000 else f"{v:,.0f}"


def svg(title, series, x_label="round", y_label="", zero=True, reference=None, y_range=None):
    """series: {name: (xs, ys, dashed, color index)}. Returns an SVG string (empty when there is nothing to draw). With `zero` the y axis starts at 0 (Buffon's rule for
    amounts); `reference` draws a horizontal line."""
    xs = [x for line in series.values() for x in line[0]]
    ys = [y for line in series.values() for y in line[1] if y == y]
    if not xs or not ys:
        return ""
    x0, x1 = min(xs), max(xs)
    if y_range:
        y0, y1 = y_range
    else:
        y0 = 0.0 if zero else min(ys)
        y1 = _nice(max(ys)) if zero else max(ys) + (max(ys) - min(ys)) * 0.1 + 1e-9
    sx, sy = _scale(x0, x1 if x1 > x0 else x0 + 1, ML, W - MR), _scale(y0, y1, H - MB, MT)
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{html.escape(title)}" font-family="sans-serif" font-size="11">',
         f'<text x="{ML}" y="15" font-size="12" font-weight="bold">{html.escape(title)}</text>']
    for k in range(5):
        v = y0 + (y1 - y0) * k / 4
        y = sy(v)
        p.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}" stroke="#ddd"/><text x="{ML - 4}" y="{y + 4:.1f}" text-anchor="end">{_fmt(v)}</text>')
    ticks = sorted(set(xs))
    for x in ticks:
        if len(ticks) <= 14 or x % 2 == 0:
            p.append(f'<text x="{sx(x):.1f}" y="{H - MB + 14}" text-anchor="middle">{x:g}</text>')
    p.append(f'<text x="{(ML + W - MR) / 2:.0f}" y="{H - 4}" text-anchor="middle">{html.escape(x_label)}</text>')
    if y_label:
        mid = (MT + H - MB) / 2
        p.append(f'<text x="10" y="{mid:.0f}" transform="rotate(-90 10 {mid:.0f})" text-anchor="middle">{html.escape(y_label)}</text>')
    if reference is not None:
        p.append(f'<line x1="{ML}" y1="{sy(reference):.1f}" x2="{W - MR}" y2="{sy(reference):.1f}" stroke="#444" stroke-dasharray="2 3"/>')
    for name, (xv, yv, dashed, ci) in series.items():
        color = PALETTE[ci % len(PALETTE)]
        pts = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in zip(xv, yv) if y == y)
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        p.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5"{dash} points="{pts}"><title>{html.escape(name)}</title></polyline>')
        p += [f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="2" fill="{color}"><title>{html.escape(name)} at {x:g}: {_fmt(y)}</title></circle>' for x, y in zip(xv, yv) if y == y]
    p.append("</svg>")
    return "\n".join(p)


def legend(names):
    """HTML legend: a swatch per arm in the colour its lines use, the A/A copy dashed."""
    base = sorted({n[:-2] if n.endswith("-b") else n for n in names})
    out = []
    for name in names:
        color = PALETTE[base.index(name[:-2] if name.endswith("-b") else name) % len(PALETTE)]
        style = "dashed" if name.endswith("-b") else "solid"
        out.append(f'<span style="margin-right:1em"><span style="display:inline-block;width:1.6em;border-top:2px {style} {color};vertical-align:middle"></span> {html.escape(name)}</span>')
    return "".join(out)


def cell_series(cell):
    """The cell's arms in a stable order with one colour per arm (its A/A copy shares it, dashed)."""
    order = sorted(cell.values, key=lambda a: (a[:-2] if a.endswith("-b") else a, a.endswith("-b")))
    base = sorted({a[:-2] if a.endswith("-b") else a for a in order})
    out = {}
    for a in order:
        r = sorted(cell.values[a])
        out[a] = ([noiselib.when(x) for x in r], [cell.values[a][x] for x in r], a.endswith("-b"), base.index(a[:-2] if a.endswith("-b") else a))
    return order, out


def cell_svg(cell):
    """(arms, svg) of the values of every arm in a cell by round."""
    order, s = cell_series(cell)
    return order, svg(f"{cell.scenario} {short_api(cell.api)} {cell.metric}", s, y_label=cell.metric)


def aa_svg(cell, arms):
    """Ratio copy / arm by round, for every arm that has a copy: a flat line at 1 means the host treated both alike."""
    s = {}
    for i, a in enumerate(arms):
        if a in cell.values and a + "-b" in cell.values:
            rounds = sorted(set(cell.values[a]) & set(cell.values[a + "-b"]))
            s[a] = ([noiselib.when(r) for r in rounds], [cell.values[a + "-b"][r] / cell.values[a][r] if cell.values[a][r] else math.nan for r in rounds], False, i)
    if not s:
        return ""
    ys = [y for line in s.values() for y in line[1] if y == y]
    spread = max([abs(y - 1) for y in ys] + [0.05]) * 1.15
    return svg(f"A/A ratio (copy / arm) {cell.scenario} {short_api(cell.api)} {cell.metric}", s, y_label="copy / arm", zero=False, reference=1.0, y_range=(1 - spread, 1 + spread))


def host_series(runs):
    """{"busy": ..., "mhz": ..., "load": ...} each ([order], [value], False): the pinned CPUs' busy share, their mean clock and the host's load, over the samples in run order."""
    busy, mhz, load = [], [], []
    for i, raw in enumerate(runs):
        for n, s in enumerate(raw["samples"]):
            t = noiselib.system(s)
            if not t:
                continue
            cs, dur = t.get("cpuset", {}), t.get("during", {})
            if cs.get("cpuset_cpus") and cs.get("window_ms"):
                busy.append((n, cs["cpuset_busy_ms"] / (cs["cpuset_cpus"] * cs["window_ms"]) * 100))
            if dur.get("mhz_mean"):
                mhz.append((n, dur["mhz_mean"]))
            if "host_load1" in s:
                load.append((n, s["host_load1"]))
    return busy, mhz, load


def host_svgs(runs):
    out = []
    busy, mhz, load = host_series(runs)
    for title, pts, label, zero in (("Pinned CPUs busy during each sample (%)", busy, "% busy", True), ("Pinned CPUs' mean clock during each sample (MHz)", mhz, "MHz", False),
                                    ("Host load average (1 min) before each sample", load, "load", True)):
        if pts:
            out.append(svg(title, {"samples": ([x for x, _ in pts], [y for _, y in pts], False, 0)}, x_label="sample, in the order they ran", y_label=label, zero=zero))
    return out
