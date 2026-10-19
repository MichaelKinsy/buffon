# SPDX-License-Identifier: Apache-2.0
"""Formulas for the dashboard, rendered once at build time by KaTeX under Node (katex_render.js). The build asks for a formula with Math.tex() and gets a
placeholder; build() renders every formula of the site in one Node process and swaps the placeholders in data/site.js for KaTeX's HTML and MathML.
The published site carries no math script."""
import json
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RENDERER = os.path.join(HERE, "katex_render.js")


class MathError(RuntimeError):
    pass


class Math:
    def __init__(self):
        self.items = []

    def tex(self, source, display=True):
        self.items.append({"tex": source, "display": display})
        return f"\x00MATH{len(self.items) - 1}\x00"

    def render(self):
        """[html] for every formula asked for, in order."""
        if not self.items:
            return []
        node = shutil.which("node")
        if not node:
            raise MathError("buffon dashboard renders its formulas with Node (KaTeX, vendored): install Node 18 or newer")
        res = subprocess.run([node, RENDERER], input=json.dumps(self.items), capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            raise MathError(f"KaTeX failed: {res.stderr.strip()[-2000:]}")
        return json.loads(res.stdout)
