# SPDX-License-Identifier: Apache-2.0
"""`buffon agentbench plan|result`: write the protocol and expected runs; turn observations into the paired result."""
import json
import os

from . import lift, protocol as protocollib


def plan(path, out):
    p = protocollib.load(path)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "protocol.json"), "w") as f:
        json.dump(dict(p.document(), digest=p.digest()), f, indent=1)
    with open(os.path.join(out, "expected-runs.json"), "w") as f:
        json.dump(protocollib.expected_runs(p), f, indent=1)
    return p


def result(path, observations, out):
    p = protocollib.load(path)
    res = lift.paired_result(p, lift.ingest(observations))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "result.json"), "w") as f:
        json.dump(res, f, indent=1)
    lines = [f"# Agent benchmark {p.benchmark}", "", f"protocol sha256 {res['protocol_digest']}; reference arm `{res['reference']}`.", ""]
    for arm, r in res["results"].items():
        h = r["headline"]
        if h is None:
            lines += [f"## {arm}: headline withheld", "", f"{len(r['blocked'])} blocked pair(s) of {r['pairs'] + len(r['blocked'])}:"] + [f"- {b['case']} / {b['model']} / run {b['run']}: {b['reason']}" for b in r["blocked"]] + [""]
        else:
            lines += [f"## {arm} against {res['reference']}", "",
                      f"{h['pairs']} paired runs: reference passes {h['reference_pass']} ({h['reference_rate']:.0%}, Wilson CI {h['reference_ci'][0]:.0%}-{h['reference_ci'][1]:.0%}), "
                      f"{arm} passes {h['arm_pass']} ({h['arm_rate']:.0%}, {h['arm_ci'][0]:.0%}-{h['arm_ci'][1]:.0%}); lift {h['lift']:+.1%}; "
                      f"discordant: {h['only_reference']} only the reference, {h['only_arm']} only {arm}; exact McNemar p = {h['mcnemar_p']:.3f}.", ""]
        lines += [f"Telemetry unavailable (null) in {', '.join(f'{k}: {v}' for k, v in r['unavailable'].items())} observations; not counted as zero.", ""]
    with open(os.path.join(out, "result.md"), "w") as f:
        f.write("\n".join(lines))
    return res
