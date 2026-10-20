# SPDX-License-Identifier: Apache-2.0
"""The durable family's crash and resume grid (docs/design/DURABLE.md 4.4, docs/DURABLE-ADAPTERS.md).

A crash workload (`durable/crash-<size>`) is not a cell: it has one sample for each (order, kill point), so it is a pass or fail grid like the reliability faults. An order is
`<writer arm>><resumer arm>`: the writer is killed after commit k, the resumer reopens the store and finishes the turn. The reference order (`<ref>><ref>`) is the oracle: a point passes when

  * the sample did not fail and the resumed run says `resume_ok`,
  * no invariant failed (`invariant_failures` is empty) and the submission was not duplicated (`duplicated_submission`),
  * the outcome (`signature`) is the same on every repetition and, for an order other than the reference order, equals the reference order's outcome at the same k.

The pass rate of an order is its passed points over its points, with a Wilson 95% interval. A/A copies (`<arm>-b`) are left out: they would not add points. Nothing here ranks an order.

An order whose resumer cannot open the writer's store (a runtime that opens schema 1 reading a store written with schema 2) is not run. The gate records it with the reason (`run.durable.cross_open`: {fixture label:
{"<writer>><reader>": {"ok": false, "why": ...}}}), and the grid lists it as `not possible: <reason>`, never as a failure."""
from .. import stats

PREFIX = "durable/crash-"


def is_crash(scenario):
    return scenario.startswith(PREFIX)


def order_of(s):
    """`<writer>><resumer>` of a crash sample: the order the sample names, else the writer it names and the arm that resumed."""
    return s.get("order") or f"{s.get('crash_writer') or s['arm']}>{s['arm']}"


def _stable(runs):
    sigs = {r.get("signature") for r in runs}
    return next(iter(sigs)) if len(sigs) == 1 else None


def _point(runs, want, control, ref_order):
    """(ok, reasons) of the repetitions of one order at one kill point."""
    reasons = []
    for r in runs:
        if "failure" in r:
            reasons.append(f"the sample failed: {str(r['failure'])[:160]}")
        elif r.get("resume_ok") is not True:
            reasons.append("it did not resume")
        if r.get("invariant_failures"):
            reasons.append(str(r["invariant_failures"]))
        if r.get("duplicated_submission"):
            reasons.append("it duplicated the submission")
    sig = _stable(runs)
    if sig is None and len({r.get("signature") for r in runs}) > 1:
        reasons.append("the outcome differs between repetitions")
    if not control:
        if want is None:
            reasons.append(f"no stable outcome of {ref_order} at this point to compare with")
        elif sig is not None and sig != want:
            reasons.append(f"the outcome differs from {ref_order}'s")
    return not reasons, sorted(set(reasons))


def impossible(raws):
    """{order: reason} of the orders the gate found impossible, from the `run.durable.cross_open` of the runs: an entry that is not ok and says why (the resumer could not open the writer's store)."""
    out = {}
    for raw in raws:
        for orders in (((raw.get("run") or {}).get("durable") or {}).get("cross_open") or {}).values():
            for order, v in (orders or {}).items():
                if isinstance(v, dict) and v.get("ok") is False and v.get("why"):
                    out.setdefault(order, str(v["why"]))
    return out


def verdicts(samples, ref, not_possible=None):
    """[{scenario, size, ref_order, ks, commits_total, orders: [{order, writer, resumer, control, points: {k: {ok, reasons, reps}}, passed, of, ci}]}] for every crash workload of `samples`,
    the workloads in name order and the reference order first among each one's orders. `ref` is the reference arm. `not_possible` is `impossible(raws)`: its orders are listed with `impossible` (the reason) and no points."""
    groups = {}
    for s in samples:
        if not is_crash(s["scenario"]) or s["warmup"] or s["arm"].endswith("-b") or s.get("twin_of"):
            continue
        groups.setdefault(s["scenario"], {}).setdefault(order_of(s), {}).setdefault(s.get("k"), []).append(s)
    out = []
    ref_order = f"{ref}>{ref}"
    for scenario in sorted(groups):
        by_order = groups[scenario]
        ks = sorted({k for pts in by_order.values() for k in pts if k is not None}, key=lambda k: (not isinstance(k, (int, float)), k if isinstance(k, (int, float)) else 0, str(k)))
        totals = {}
        for pts in by_order.values():
            for k, runs in pts.items():
                for r in runs:
                    if isinstance(r.get("commits_total"), (int, float)) and not isinstance(r["commits_total"], bool):
                        totals.setdefault(k, r["commits_total"])
        orders = []
        for order in sorted(by_order, key=lambda o: (o != ref_order, o)):
            writer, _, resumer = order.partition(">")
            points = {}
            for k in ks:
                runs = by_order[order].get(k)
                if not runs:
                    continue
                want = _stable(by_order[ref_order][k]) if ref_order in by_order and k in by_order[ref_order] else None
                ok, why = _point(runs, want, order == ref_order, ref_order)
                points[k] = {"ok": ok, "reasons": why, "reps": len(runs)}
            passed = sum(p["ok"] for p in points.values())
            lo, hi = stats.wilson(passed, len(points))
            orders.append({"order": order, "writer": writer, "resumer": resumer, "control": order == ref_order, "points": points, "passed": passed, "of": len(points),
                           "ci": [lo, hi] if len(points) else None, "impossible": None})
        for order in sorted(o for o in (not_possible or {}) if o not in by_order):
            writer, _, resumer = order.partition(">")
            orders.append({"order": order, "writer": writer, "resumer": resumer, "control": False, "points": {}, "passed": 0, "of": 0, "ci": None, "impossible": not_possible[order]})
        out.append({"scenario": scenario, "size": scenario[len(PREFIX):], "ref_order": ref_order, "ks": ks, "commits_total": totals, "orders": orders})
    return out


def lines(data, prov, not_possible=None):
    """The report's crash section: the pass rate of each order with its interval, the points that did not pass, and the orders that are not possible. [] when no crash workload ran."""
    grids = verdicts(data["samples"], data["reference"], not_possible)
    if not grids:
        return []
    tag = " — PROVISIONAL" if prov else ""
    out = [f"## Durable crash and resume{tag}", "", "Each point is one kill after commit k of one measured turn, then a reopen, a resume and the same request id again. A point passes when the run resumed, no invariant failed, "
           "the submission was not duplicated and the outcome equals the reference order's at the same point. The reference order is the oracle: it passes on invariants and a stable outcome. "
           "An order is writer then resumer. The interval is the Wilson 95% interval of the passed share of its points.", ""]
    for g in grids:
        out += [f"### {g['scenario']}", "", "| order | points | passed | share | 95% interval |", "|---|---:|---:|---:|---|"]
        fails = []
        for o in g["orders"]:
            if o["impossible"]:
                out.append(f"| {o['order']} | not possible: {str(o['impossible']).replace('|', '/')} | | | |".replace("\n", " "))
                continue
            share = o["passed"] / o["of"] if o["of"] else float("nan")
            ci = f"{o['ci'][0]:.1%} to {o['ci'][1]:.1%}" if o["ci"] else "n/a"
            out.append(f"| {o['order']}{' (reference)' if o['control'] else ''} | {o['of']} | {o['passed']} | {share:.1%} | {ci} |")
            fails += [f"- {o['order']} at k={k}: {'; '.join(p['reasons'])}" for k, p in o["points"].items() if not p["ok"]]
        if fails:
            out += ["", "Points that did not pass:"] + fails[:30] + ([f"- and {len(fails) - 30} more"] if len(fails) > 30 else [])
        out.append("")
    return out


def notes(data, prov):
    """What a reader of the durable cells must know, as the report's short section; [] when the run has no durable cell."""
    envs = sorted({c.env for c in data["cells"] if c.scenario.startswith("durable/") and c.env})
    if not envs:
        return []
    tag = " — PROVISIONAL" if prov else ""
    return [f"## Durable notes{tag}", "", f"- Environment: the durable cells of this report ran in {', '.join(envs)}. Every environment is its own cell and none is mixed with another; native SQLite is not a Durable Object.",
            "- `warm_net_ms` is the warm turn less the warm turn of `durable/floor-host` of the same arm and round, and is never applied to a cold start; the gross `warm_turn_ms` is always beside it.",
            "- Statements are counted by a wrapper on the public SQLite facade. `sql_pragma_stmts_per_turn` lists the pragma statements apart; they are part of `sql_stmts_per_turn`.",
            "- `sql_commits_per_turn`, `rows_written_per_turn`, `store_bytes` and `store_bytes_per_turn` have an exact equivalence margin: they are equivalent only when every paired round has the same value.",
            "- A metric an environment cannot produce is absent, never zero (the kernel's byte counters exist on Linux only; the platform's rows read and written on Miniflare and Cloudflare only).", ""]
