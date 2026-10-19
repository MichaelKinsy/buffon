# SPDX-License-Identifier: Apache-2.0
"""What each Results section will measure when the loaded runs have nothing for it yet: the workloads the launch campaign names and the harnesses that take part, read from campaigns/launch-rerun.toml,
the arm manifests and the workload texts (benchmarks.py), plus the Durable family's own plan (docs/design/DURABLE.md, which the site carries). The site shows every section; one without data is muted and says this."""
import os
import re
import tomllib

from . import benchmarks

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAMPAIGN = "campaigns/launch-rerun.toml"
COMMAND = "python3 -m buffon campaign campaigns/launch-rerun.toml --site <your site> --out runs/launch-rerun"
# The Durable family is designed, not built (docs/design/DURABLE.md, "Owner decisions" and 3.4): its arms and the workloads the plan names.
DURABLE = {"arms": ["Pi Durable 1.3.0 (the reference)", "PiG Durable, native Go", "PiG Durable, Wasm core", "tardigrade"],
           "workloads": [("durable/compat-3500", "durable-bench's shape, compaction off, to set beside the published numbers"), ("durable/mixed-3500", "the default: open the fixture, then ten measured turns (the headline: warm_net_ms)"),
                         ("durable/cold-every-turn-3500", "reopen the store before every measured turn"), ("durable/stream-1000", "each response streams in chunks: write amplification"),
                         ("durable/many-conv-32", "many conversations at once: memory per live conversation"), ("durable/crash-k", "kill the process after a commit, reopen, finish")]}


def arm_labels():
    try:
        from ..arms import manifest
        return {name: arm.label for name, arm in manifest.load_all().items()}
    except Exception:   # the labels are a nicety: the arm ids say the same
        return {}


def requires(scenario):
    """(mode, needs Pi extensions) of a workload of the plan: the mode the harness must have and whether it must load Pi's extensions (the same split the workloads make: buffon/workloads/overhead.py)."""
    if scenario == "overhead/version":
        return "version", False
    if scenario.startswith("longsession/resume"):
        return "rpc_resume", False
    name = scenario.split("/", 1)[-1]
    ext = bool(re.search(r"-ext\d+$", name))
    if name.startswith("rpc"):
        return "rpc", ext
    if name == "pty" or scenario == "streaming/tui-prose":
        return "pty", False
    return "print", ext


def why_not(arm, scenario):
    """The manifest's reason that `arm` cannot run `scenario`, or None when it can: the text the workload itself raises as its skip (cannot_run, else what the manifest declares)."""
    mode, ext = requires(scenario)
    if scenario == "overhead/print-write" and arm.cannot_run.get("print-write"):
        return arm.cannot_run["print-write"]
    if not arm.supports_mode(mode):
        return arm.cannot_run.get(mode) or arm.cannot_run.get(mode.split("_")[0]) or f"it has no {mode} mode"
    if ext and arm.pi_extensions not in ("native", "sidecar"):
        return arm.cannot_run.get("extensions") or ("it does not load Pi extensions" if arm.pi_extensions == "none" else "it loads only part of Pi's extensions")
    return None


def campaign_families(arm_id, root=ROOT):
    """The families of the campaign that name `arm_id`, in the campaign's order."""
    try:
        with open(os.path.join(root, CAMPAIGN), "rb") as f:
            campaign = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return []
    return [fam.get("name", "") for fam in campaign.get("family", []) if arm_id in fam.get("arms", [])]


def unmeasured(profiles, measured_ids, root=ROOT):
    """The harnesses of the profiles none of whose arms any loaded run has data for, when the arm is in the registry and not held, for the Harnesses page: [{id, name, slug, profile, version, scope: {runs, cannot: [{scenario, title, reason}]}, families}].
    `runs` are the titles of the plan's workloads the manifest says it can run. The manifest, not a run, is the source: no number is read for it."""
    from ..arms import manifest
    try:
        arms = manifest.load_all()
    except Exception:
        return []
    out = []
    plan = load(root)["workloads"]
    for prof in profiles:
        if any(a in measured_ids for a in prof["harnesses"]):   # a project with a measured harness has its card already; its other arms are not listed
            continue
        for arm_id in prof["harnesses"]:
            arm = arms.get(arm_id)
            if arm is None or arm.held:
                continue
            seen, can, cannot = set(), [], []
            for w in plan:
                if w["scenario"] in seen:
                    continue
                seen.add(w["scenario"])
                reason = why_not(arm, w["scenario"])
                (cannot.append({"scenario": w["scenario"], "title": w["title"], "reason": reason}) if reason else can.append(w["title"]))
            out.append({"id": arm_id, "name": arm.label, "slug": re.sub(r"[^a-z0-9]+", "-", arm_id.lower()).strip("-"), "profile": prof["slug"], "version": arm.version,
                        "scope": {"runs": can, "cannot": cannot}, "families": campaign_families(arm_id, root)})
    return out


def load(root=ROOT):
    """{campaign, command, workloads: [{scenario, title, use, family, arms, rounds}], durable: {arms, workloads}} for the site. A campaign that is not on disk gives no workloads."""
    labels = arm_labels()
    workloads = []
    try:
        with open(os.path.join(root, CAMPAIGN), "rb") as f:
            campaign = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        campaign = {}
    for family in campaign.get("family", []):
        for scenario in family.get("workloads", []):
            w = benchmarks.workload_of(scenario)
            workloads.append({"scenario": scenario, "title": w["title"], "use": w["use"], "family": family.get("name", ""), "arms": [labels.get(a, a) for a in family.get("arms", [])], "rounds": family.get("rounds")})
    return {"campaign": CAMPAIGN, "command": COMMAND, "workloads": workloads,
            "durable": {"arms": DURABLE["arms"], "workloads": [{"scenario": s, "note": n} for s, n in DURABLE["workloads"]]}}
