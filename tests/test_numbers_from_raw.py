# SPDX-License-Identifier: Apache-2.0
"""Every number the report and the dashboard show, recomputed from the run's raw.json alone.

The recomputation below is this file's own code. It does not import buffon.report, buffon.stats or buffon.dashboard math: it reads raw.json (and workloads/grade.toml, which is
published method data), and restates the pipeline steps listed in ACCURACY.md (the audit of the numbers). It then compares the result with

  * report.json written by `python3 -m buffon report` (ratio, interval, floor, Holm p, verdict, n),
  * the dashboard's data (data/site.js): per-round values, the median of each harness's rounds, the ratio, its interval, floor and verdict. `buffon grade` (the report's
    grade.json) is restated here too; the site shows no grade.

Deterministic (seed 20261011, Buffon's). The demo run is synthetic (tests/report_demo.py)."""
import itertools
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
import tomllib
import unittest
from fnmatch import fnmatchcase

from buffon.dashboard import build as dashboard, model
from tests.report_demo import REFERENCE, demo_raw
from tests.telemetry_fixtures import write_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20261011
RESAMPLES = 4000
Z975 = statistics.NormalDist().inv_cdf(0.975)
Z80 = statistics.NormalDist().inv_cdf(0.8)
HOST_READINGS = {"quiet_wait_ms", "host_load1", "host_runnable", "pinned_busy", "pinned_iowait", "pinned_steal", "cpuset_runnable", "throttled", "psi_cpu_some_avg10"}
COST = re.compile(r"(_ms|_mib|_bytes|_instructions|_cycles)$|_ms_per_|_instructions_per_|^instructions$|^cycles$")


# -- the recomputation: raw.json -> cells -------------------------------------------------------------------------------------------------------------

def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


_IDX = {}


def resamples(n):
    """The 4000 index draws of a bootstrap over n rounds. A fresh random.Random(SEED) per call gives the same draws for every cell with n rounds, so they are made once."""
    if n not in _IDX:
        rng = __import__("random").Random(SEED)
        _IDX[n] = [[rng.randrange(n) for _ in range(n)] for _ in range(RESAMPLES)]
    return _IDX[n]


def ratio_of_medians(x, y):
    """(point ratio, [lo, hi]) of median(x)/median(y) over paired lists; the interval resamples pairs together, percentile indices int(a*(m-1)) and ceil((1-a)*(m-1))."""
    n = len(x)
    point = median(x) / median(y)
    draws = []
    for idx in resamples(n):
        mx, my = median([x[i] for i in idx]), median([y[i] for i in idx])
        if my:
            draws.append(mx / my)
        elif mx:
            draws.append(math.inf)
    draws.sort()
    a = 0.025
    return point, [draws[int(a * (len(draws) - 1))], draws[math.ceil((1 - a) * (len(draws) - 1))]]


def sign_flip_p(x, y):
    logs = [math.log(a / b) for a, b in zip(x, y) if a > 0 and b > 0]
    assert 0 < len(logs) <= 16, "the demo has few enough rounds for the exact test"
    obs = abs(sum(logs))
    hits = sum(abs(sum(s * d for s, d in zip(signs, logs))) >= obs - 1e-12 for signs in itertools.product((1, -1), repeat=len(logs)))
    return hits / 2 ** len(logs)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = run
    return out


def floor_of(twin, arm):
    """The A/A floor (natural-log units) of one arm from its copy: max(|ln R|, ln U, -ln L, 0) of median(copy)/median(arm)."""
    if len(twin) < 3 or not median(twin) or not median(arm):
        return None
    r, (lo, hi) = ratio_of_medians(twin, arm)
    if not r or not math.isfinite(r) or lo <= 0 or not math.isfinite(hi):
        return None
    return max(abs(math.log(r)), math.log(hi), -math.log(lo), 0.0)


def mde(twin, arm):
    logs = [math.log(a / b) for a, b in zip(twin, arm) if a > 0 and b > 0]
    if len(logs) < 3:
        return None
    return math.expm1((Z975 + Z80) * statistics.stdev(logs) / math.sqrt(len(logs)))


def verdict(ratio, ci, floor, p):
    lo, hi = ci
    if math.isnan(lo) or math.isnan(hi):
        return "too few rounds"
    if floor is not None and abs(math.log(ratio)) <= floor:
        return "no measurable difference"
    side = "loss" if lo > 1 else "win" if hi < 1 else None
    if side and not p < 0.05:
        return "inconclusive"
    return side or "inconclusive"


def recompute(raw, ref=REFERENCE):
    """{(scenario, api, metric): {"values": {arm: {round: v}}, "comparisons": {arm: {...}}, "mde": m}} from raw.json's samples."""
    values = {}
    for s in raw["samples"]:
        if s["warmup"] or "failure" in s or s["scenario"].split("/")[0] in ("reliability", "soak"):
            continue
        for k, v in s.items():
            if COST.search(k) and k not in HOST_READINGS and isinstance(v, (int, float)) and not isinstance(v, bool):
                values.setdefault((s["scenario"], s.get("api"), k), {}).setdefault(s["arm"], {})[s["round"]] = float(v)
    arms = sorted({a for cell in values.values() for a in cell})
    base = [a for a in arms if not a.endswith("-b")]
    out = {}
    for key, by_arm in values.items():
        def paired(a, b):
            rounds = sorted(set(by_arm.get(a, {})) & set(by_arm.get(b, {})))
            return [by_arm[a][r] for r in rounds], [by_arm[b][r] for r in rounds]
        if ref not in by_arm:
            out[key] = {"values": by_arm, "comparisons": {}, "mde": None}
            continue
        floors = {a: floor_of(*paired(a + "-b", a)) for a in base if a + "-b" in by_arm}
        comps = {}
        for a in base:
            if a == ref or a not in by_arm:
                continue
            x, y = paired(a, ref)
            if len(x) < 2 or not median(y):
                continue
            ratio, ci = ratio_of_medians(x, y)
            have = [f for f in (floors.get(ref), floors.get(a)) if f is not None]
            comps[a] = {"n": len(x), "arm_median": median(x), "ref_median": median(y), "ratio": ratio, "ci": ci, "floor": max(have) if have else None, "p": sign_flip_p(x, y)}
        adj = holm([c["p"] for c in comps.values()])
        for c, p in zip(comps.values(), adj):
            c["p_holm"] = p
            c["verdict"] = verdict(c["ratio"], c["ci"], c["floor"], p)
        m = mde(*paired(ref + "-b", ref)) if ref + "-b" in by_arm and floors.get(ref) is not None else None
        out[key] = {"values": by_arm, "comparisons": comps, "mde": m, "floors": floors}
    return out


# -- the grade, from the recomputed cells and workloads/grade.toml ----------------------------------------------------------------------------------

def load_method():
    with open(os.path.join(ROOT, "workloads", "grade.toml"), "rb") as f:
        return tomllib.load(f)


def spec_of(method, scenario, metric):
    for fam in method["family"]:
        for row in fam["metric"]:
            if fnmatchcase(scenario, row["scenario"]) and fnmatchcase(metric, row["metric"]):
                return fam["id"], row["kind"]
    return None


def twin_metric(metric):
    if metric == "cpu_ms":
        return "instructions"
    if metric.endswith("cpu_ms_per_1k_tokens"):
        return metric.replace("cpu_ms_per_1k_tokens", "instructions_per_1k_tokens")
    return None


def reliability_counts(raw, ref=REFERENCE):
    """{arm: (passed faults, faults)}: a fault passes when the arm's invariants held on every repetition and its stable signature equals the reference's."""
    groups = {}
    for s in raw["samples"]:
        if s["scenario"].startswith("reliability/"):
            groups.setdefault((s["scenario"], s.get("api")), {}).setdefault(s["arm"], []).append(s)
    counts = {}
    for by_arm in groups.values():
        sigs = {r.get("signature") for r in by_arm[ref]}
        want = next(iter(sigs)) if len(sigs) == 1 else None
        for arm, runs in by_arm.items():
            if arm.endswith("-b"):
                continue
            mine = {r.get("signature") for r in runs}
            ok = not any(r.get("invariant_failures") for r in runs) and len(mine) == 1 and (arm == ref or mine == {want})
            c = counts.setdefault(arm, [0, 0])
            c[0] += ok
            c[1] += 1
    return counts


def grade(method, cells, raw, weights, ref=REFERENCE):
    """{arm: {"families": {fid: {"ratio", "score"}}, "overall": exact score or None}} under `weights` ({"families": {...}, "kinds": {...}})."""
    m = method["method"]
    have = {k for k, c in cells.items() if ref in c["values"]}
    by_family = {}
    for (scenario, api, metric), c in cells.items():
        spec = spec_of(method, scenario, metric)
        if spec is None or (scenario, api, metric) not in have:
            continue
        twin = twin_metric(metric)
        if twin and (scenario, api, twin) in have and spec_of(method, scenario, twin):
            continue
        by_family.setdefault(spec[0], []).append((spec[1], c))
    rel = reliability_counts(raw, ref)
    arms = sorted({a for c in cells.values() for a in c["comparisons"]})
    out = {}
    for arm in arms:
        fams = {}
        for fam in method["family"]:
            fid = fam["id"]
            if fam.get("special") == "reliability":
                if not rel.get(ref) or not rel[ref][0]:
                    continue
                got = rel.get(arm)
                ratio = (rel[ref][0] / rel[ref][1]) / (got[0] / got[1]) if got and got[0] else None
            else:
                rows = by_family.get(fid, [])
                rs, ws = [], []
                for kind, c in rows:
                    comp = c["comparisons"].get(arm)
                    if comp is None:
                        continue
                    r = comp["ratio"]
                    if comp["floor"] is not None and abs(math.log(r)) <= comp["floor"]:
                        r = 1.0
                    rs.append(r)
                    ws.append(weights["kinds"][kind])
                if not rows or len(rs) < m["min_cell_fraction"] * len(rows) or not rs:
                    continue
                ratio = math.exp(sum(w * math.log(r) for r, w in zip(rs, ws)) / sum(ws))
            score = 0.0 if ratio is None else min(100.0, max(0.0, m["reference_score"] - m["points_per_halving"] * math.log2(ratio)))
            fams[fid] = {"ratio": ratio, "score": score}
        overall = None
        if len(fams) >= m["coverage_floor"]:
            tw = sum(weights["families"][f] for f in fams)
            overall = sum(weights["families"][f] * v["score"] for f, v in fams.items()) / tw
        out[arm] = {"families": fams, "overall": overall}
    return out


# -- the test ---------------------------------------------------------------------------------------------------------------------------------

def close(a, b, rel=1e-9):
    return a == b or abs(a - b) <= rel * max(abs(a), abs(b), 1e-300)


class NumbersFromRaw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.mkdtemp()
        cls.src = write_dir(os.path.join(tmp, "run"), demo_raw(wire=False, divergence=False))
        with open(os.path.join(cls.src, "raw.json")) as f:
            cls.raw = json.load(f)
        cls.report_dir = os.path.join(tmp, "report")
        done = subprocess.run([sys.executable, "-m", "buffon", "report", cls.src, "--out", cls.report_dir], cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, done.stderr
        with open(os.path.join(cls.report_dir, "report.json")) as f:
            cls.report = json.load(f)
        with open(os.path.join(cls.report_dir, "grade.json")) as f:
            cls.grade_json = json.load(f)
        cls.site_dir = os.path.join(tmp, "site")
        dashboard.build([cls.src], cls.site_dir)
        with open(os.path.join(cls.site_dir, "data", "site.js"), encoding="utf-8") as f:
            cls.site = json.loads(re.sub(r"^window\.BUFFON\s*=\s*", "", f.read().strip()).rstrip(";").strip())
        cls.cells = recompute(cls.raw)
        cls.method = load_method()

    # report.json -------------------------------------------------------------------------------------------------------------------------

    def test_the_set_of_cells_is_the_set_of_cost_metrics_in_raw_json(self):
        reported = {(c["scenario"], c["api"], c["metric"]) for c in self.report["cells"]}
        self.assertEqual(reported, set(self.cells))
        self.assertGreater(len(reported), 15)

    def test_every_ratio_interval_floor_p_and_verdict_is_what_raw_json_gives(self):
        checked = 0
        for c in self.report["cells"]:
            mine = self.cells[(c["scenario"], c["api"], c["metric"])]
            self.assertEqual(set(c["comparisons"]), set(mine["comparisons"]), c["id"])
            if mine["mde"] is not None:
                self.assertTrue(close(c["mde"], mine["mde"]), (c["id"], c["mde"], mine["mde"]))
            for arm, rep in c["comparisons"].items():
                m = mine["comparisons"][arm]
                where = (c["id"], arm)
                self.assertEqual(rep["n"], m["n"], where)
                self.assertTrue(close(rep["ratio"], m["ratio"]), (where, rep["ratio"], m["ratio"]))
                self.assertTrue(close(rep["ci"][0], m["ci"][0]) and close(rep["ci"][1], m["ci"][1]), (where, rep["ci"], m["ci"]))
                self.assertTrue(close(rep["p_holm"], m["p_holm"], 1e-9), (where, rep["p_holm"], m["p_holm"]))
                self.assertEqual(rep["floor"] is None, m["floor"] is None, where)
                if m["floor"] is not None:
                    self.assertTrue(close(rep["floor"], m["floor"]), (where, rep["floor"], m["floor"]))
                self.assertEqual(rep["verdict"], m["verdict"], where)
                checked += 1
        self.assertGreater(checked, 50)

    def test_the_interval_holds_the_point_estimate_and_the_verdict_agrees_with_interval_and_noise_band(self):
        words = set()
        for c in self.report["cells"]:
            for arm, rep in c["comparisons"].items():
                lo, hi = rep["ci"]
                r, f, v = rep["ratio"], rep["floor"], rep["verdict"].split(" (")[0]
                words.add(v)
                self.assertLessEqual(lo, r, (c["id"], arm))
                self.assertLessEqual(r, hi, (c["id"], arm))
                inside = f is not None and abs(math.log(r)) <= f
                if v == "no measurable difference":
                    self.assertTrue(inside, (c["id"], arm))
                else:
                    self.assertFalse(inside, (c["id"], arm))
                if v == "win":
                    self.assertLess(hi, 1)
                    self.assertLess(rep["p_holm"], 0.05)
                if v == "loss":
                    self.assertGreater(lo, 1)
                    self.assertLess(rep["p_holm"], 0.05)
                if v == "inconclusive":
                    self.assertTrue(lo <= 1 <= hi or rep["p_holm"] >= 0.05, (c["id"], arm))
        self.assertGreaterEqual(words, {"win", "loss", "no measurable difference"})

    # dashboard ---------------------------------------------------------------------------------------------------------------------------

    def test_the_dashboards_medians_ratios_intervals_and_rounds_are_the_recomputed_ones(self):
        seen = 0
        for c in self.site["cells"]:
            mine = self.cells[(c["scenario"], c["api"], c["metric"])]
            for arm, rounds in mine["values"].items():
                if arm in c["values"]:
                    self.assertEqual(c["values"][arm], [rounds[r] for r in sorted(rounds)], (c["scenario"], c["metric"], arm))
            for arm, st in c["stats"].items():   # the grid's cell: the median of the harness's own measured rounds, and the interval of that median around it
                values = [mine["values"][arm][r] for r in sorted(mine["values"][arm])]
                self.assertEqual(st["n"], len(values), (c["scenario"], c["metric"], arm))
                self.assertTrue(close(st["median"], statistics.median(values)), (c["scenario"], c["metric"], arm))
                self.assertEqual((st["min"], st["max"]), (min(values), max(values)))
                if st["ci"]:
                    self.assertLessEqual(st["ci"][0], st["median"] + 1e-9)
                    self.assertGreaterEqual(st["ci"][1], st["median"] - 1e-9)
            for arm, comp in c["comparisons"].items():
                m = mine["comparisons"][arm]
                where = (c["scenario"], c["metric"], arm)
                ci = comp.get("ci95") or comp["ci"]
                self.assertEqual(comp["n"], m["n"], where)
                for got, want in ((comp["arm_median"], m["arm_median"]), (comp["ref_median"], m["ref_median"]), (comp["ratio"], m["ratio"]), (ci[0], m["ci"][0]), (ci[1], m["ci"][1])):
                    self.assertTrue(close(got, want), (where, got, want))
                self.assertEqual(str(comp["verdict"]).split(" (")[0], m["verdict"], where)
                if m["floor"] is not None:
                    self.assertTrue(close(comp["floor"], math.expm1(m["floor"])) or close(comp.get("floor_log", comp["floor"]), m["floor"]), where)
                seen += 1
        self.assertEqual(seen, sum(len(c["comparisons"]) for c in self.report["cells"]))

    def test_the_report_cards_overall_scores_and_suite_scores_are_the_recomputed_ones(self):
        default = grade(self.method, self.cells, self.raw, {"families": self.method["weights"]["default"]["families"], "kinds": self.method["weights"]["default"]["kinds"]})
        for arm, g in default.items():
            self.assertIsNotNone(g["overall"], arm)
            gj = next(e for e in self.grade_json["entries"] if e["entry"] == arm)
            self.assertTrue(close(gj["overall_exact"], g["overall"]), (arm, gj["overall_exact"], g["overall"]))
            for fid, fam in g["families"].items():
                self.assertTrue(close(gj["families"][fid]["score"], fam["score"]), (arm, fid))
        self.assertEqual(len(default), 3)


class MissingRounds(unittest.TestCase):
    """An arm with a failed sample has fewer rounds than Pi. The comparison pairs rounds, so both medians are taken over the rounds the two share (the cell's n), not over each
    arm's own rounds: the figure a cell page shows for Pi can differ from the median of all of Pi's rounds."""

    def test_medians_and_ratio_are_over_the_shared_rounds_only(self):
        raw = demo_raw(rounds=6, wire=False, divergence=False)
        hit = next(s for s in raw["samples"] if s["arm"] == "demo-alpha" and s["scenario"] == "overhead/print" and s["round"] == 3)
        for key in [k for k in hit if k not in ("arm", "scenario", "api", "round", "warmup", "t_utc")]:
            del hit[key]
        hit["failure"] = "exit 1: a failed sample is kept in raw.json and left out of every median"
        tmp = tempfile.mkdtemp()
        src = write_dir(os.path.join(tmp, "run"), raw)
        site = model.build([src], os.path.join(tmp, "data"))
        mine = recompute(raw)
        cell = next(c for c in site["cells"] if c["scenario"] == "overhead/print" and c["metric"] == "cpu_ms")
        comp = cell["comparisons"]["demo-alpha"]
        key = ("overhead/print", "openai-completions", "cpu_ms")
        pi_all = mine[key]["values"][REFERENCE]
        shared = sorted(set(pi_all) - {3})
        self.assertEqual(comp["n"], 5)
        self.assertEqual(len(pi_all), 6)
        self.assertTrue(close(comp["ref_median"], median([pi_all[r] for r in shared])))
        self.assertTrue(close(comp["arm_median"], mine[key]["comparisons"]["demo-alpha"]["arm_median"]))
        self.assertTrue(close(comp["ratio"], mine[key]["comparisons"]["demo-alpha"]["ratio"]))
        self.assertEqual(len(cell["values"][REFERENCE]), 6)   # the raw-number charts keep every round of Pi
        self.assertEqual(len(cell["values"]["demo-alpha"]), 5)


if __name__ == "__main__":
    unittest.main()
