# SPDX-License-Identifier: Apache-2.0
"""The site GitHub Pages publishes (.github/workflows/pages.yml): `buffon dashboard` over every published run in results/ that nobody withdrew,
oldest first, or, while results/ holds none, over the synthetic demo run, which every page then marks as DEMO.

    python3 tools/pages_site.py site/"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from buffon.dashboard import build  # noqa: E402


def published(results=os.path.join(ROOT, "results")):
    """The run directories to publish, oldest first: every run in the index that is not withdrawn (empty when there is none)."""
    try:
        with open(os.path.join(results, "index.json")) as f:
            rows = [r for r in json.load(f)["results"] if r.get("withdrawn") is None and os.path.isdir(os.path.join(results, r["id"]))]
    except (OSError, KeyError, ValueError):
        return []
    rows.sort(key=lambda r: (r.get("finished_utc") or "", r["id"]))
    return [os.path.join(results, r["id"]) for r in rows]


def demo_dirs():
    from tests.report_demo import demo_faithfulness_dir, demo_raw
    from tests.telemetry_fixtures import write_dir
    tmp = tempfile.mkdtemp(prefix="buffon-demo-")
    return write_dir(os.path.join(tmp, "demo-run"), demo_raw()), demo_faithfulness_dir(os.path.join(tmp, "faithfulness"))


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    runs = published()
    faith = []
    if not runs:
        run, f = demo_dirs()
        runs, faith = [run], [f]
        print("pages: results/ holds no published run; building the DEMO site")
    site, data = build.build(runs, argv[1], faithfulness=faith)
    print(f"pages: the dashboard of {', '.join(os.path.basename(r) for r in runs)} ({len(data['harnesses'])} harnesses, {len(data['cells'])} cells) in {argv[1]}" + (" (DEMO)" if site["demo"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
