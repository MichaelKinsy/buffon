// SPDX-License-Identifier: Apache-2.0
// Build-time math for the dashboard: reads [{tex, display}] as JSON on stdin, writes [html] as JSON on stdout.
// KaTeX (vendor/katex, MIT) renders HTML plus MathML, so the published page needs only katex.min.css and its fonts, no script.
// \T{key}{...} wraps a term in the class `t t-<key>`: the same class colours the matching chart mark and links the two on hover.
"use strict";
const path = require("path");
const katex = require(path.join(__dirname, "vendor", "katex", "katex.min.js"));

const TERM = /^t( t-[a-z0-9]+)?$/;
const options = (display) => ({
  displayMode: display,
  output: "htmlAndMathml",
  throwOnError: true,
  trust: (c) => c.command === "\\htmlClass" && TERM.test(c.class),
  strict: (code) => (code === "htmlExtension" ? "ignore" : "error"),
  macros: { "\\T": "\\htmlClass{t t-#1}{#2}", "\\med": "\\operatorname{median}" },
});

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  const items = JSON.parse(input);
  process.stdout.write(JSON.stringify(items.map((it) => katex.renderToString(it.tex, options(Boolean(it.display))))));
});
