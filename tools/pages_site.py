# SPDX-License-Identifier: Apache-2.0
"""The site GitHub Pages serves: `buffon dashboard` over every published run in results/ that nobody withdrew, oldest first, plus any run directories
given after the site directory (for example a run that is not in results/ yet), or, with neither, over the synthetic demo run, which every page then marks
as DEMO. `--publish REMOTE` then commits the site as the single commit of the `gh-pages` branch and force-pushes it there (GitHub Pages serves that branch;
the commit is made with your own git identity and signing settings).

    python3 tools/pages_site.py site/ [RUN_DIR ...] [--publish origin]"""
import argparse
import json
import os
import subprocess
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


def publish(site, remote):
    """Commit `site` as the only commit of a fresh `gh-pages` branch and force-push it to `remote` (a remote name of this checkout, or a URL)."""
    url = subprocess.run(["git", "-C", ROOT, "remote", "get-url", remote], capture_output=True, text=True).stdout.strip() or remote
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    open(os.path.join(site, ".nojekyll"), "w").close()   # serve the files as they are (no Jekyll)
    git = lambda *a: subprocess.run(["git", "-C", site, *a], check=True)   # noqa: E731
    git("init", "-q", "-b", "gh-pages")
    git("add", "-A")
    git("commit", "-q", "-s", "-m", f"site: buffon dashboard over the published runs, from {head}")
    git("push", "-q", "-f", url, "gh-pages")
    print(f"pages: pushed {site} to {url} gh-pages")


def main(argv):
    ap = argparse.ArgumentParser(prog="pages_site.py", description=__doc__.strip().splitlines()[0])
    ap.add_argument("site", help="the site directory to write: empty, or written by an earlier `buffon dashboard`")
    ap.add_argument("extra", nargs="*", help="run directories to add to the published ones")
    ap.add_argument("--publish", metavar="REMOTE", help="then force-push the site to REMOTE's gh-pages branch")
    args = ap.parse_args(argv[1:])
    runs = published() + [os.path.abspath(d) for d in args.extra]
    faith = []
    if not runs:
        run, f = demo_dirs()
        runs, faith = [run], [f]
        print("pages: results/ holds no published run; building the DEMO site")
    site, data = build.build(runs, args.site, faithfulness=faith)
    print(f"pages: the dashboard of {', '.join(os.path.basename(r) for r in runs)} ({len(data['harnesses'])} harnesses, {len(data['cells'])} cells) in {args.site}" + (" (DEMO)" if site["demo"] else ""))
    if args.publish:
        if site["demo"]:
            print("pages: refusing to publish the DEMO site", file=sys.stderr)
            return 1
        publish(args.site, args.publish)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
