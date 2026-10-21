// SPDX-License-Identifier: Apache-2.0
// buffon dashboard. One page, one data file (data/site.js, written by `buffon dashboard`), every view drawn from it.
// The view is the URL hash (#/?m=a,b&h=x,y&sort=a:asc&v=ratio&base=z), so any view can be shared and the back button works, from file:// and from Pages alike.
// render(data, hash, ctx) is pure (data in, HTML out): tests/test_dashboard.py runs it under Node for every route. mount() wires the page:
// one delegated listener per event type, so a control drawn by any view works the same way.
// The front page is a grid: rows are harnesses, columns are metrics the reader picks. The site makes no grade, no score and no ranking: it lines the numbers up,
// marks the lowest value of each column, and leaves the call to the reader.
(function (root) {
  "use strict";

  // ------------------------------------------------------------------ text and numbers
  var ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return ESC[c]; }); }
  function ok(x) { return typeof x === "number" && isFinite(x); }
  // ONE formatter for every number on the site: the tile, the table, the chart, the tooltip and the derivation all call it, so one value is one string.
  // Three significant digits (a thousand and more: whole numbers with a thousands separator), a time of one second or more in s and a shorter one in ms,
  // a memory of one GiB or more in GiB and a smaller one in MiB, a ratio in three significant digits with its trailing zeros (1.00, 0.0165).
  function group(x) { return Math.round(x).toLocaleString("en-US"); }
  function sig(x, d) {
    if (!ok(x)) return "n/a";
    if (x === 0) return "0";
    if (Math.abs(x) >= 999.5) return group(x);
    var r = Number(x.toPrecision(d || 3));
    return Math.abs(r) < 1e-4 ? r.toExponential(1) : String(r);
  }
  function fmt(x) { return sig(x, 3); }
  // a number and the unit it is shown in: [text, unit]. ms and MiB switch to s and GiB at one thousand and one GiB; every other unit is shown as it is.
  var SINGULAR = { kills: "kill", periods: "period", processes: "process" };
  function parts(x, unit, ref) {
    if (!ok(x)) return ["n/a", ""];
    var u = String(unit || "");
    if (/^ms\b/.test(u)) return Math.abs(Number(x.toPrecision(3))) >= 1000 ? [sig(x / 1000), "s"] : [sig(x), "ms"];
    if (u === "MiB") return Math.abs(x) >= 1024 ? [sig(x / 1024), "GiB"] : [sig(x), "MiB"];
    var s = unitScale(u, ref == null ? x : ref);
    return [sig(x / s.div), x === 1 && SINGULAR[s.u] ? SINGULAR[s.u] : s.u];
  }
  function val(x, unit, ref) { var p = parts(x, unit, ref); return p[1] ? p[0] + " " + p[1] : p[0]; }
  function span(a, b, unit) { var p = parts(a, unit, b), q = parts(b, unit, b); return p[1] === q[1] || !p[1] ? p[0] + " to " + q[0] + (q[1] ? " " + q[1] : "") : p[0] + " " + p[1] + " to " + q[0] + " " + q[1]; }
  // the runner's own words carry numbers with a unit (4096 MiB, 1500 ms): said again in the site's format
  function restate(text) { return String(text || "").replace(/(\d[\d,]*(?:\.\d+)?) (MiB|ms)\b/g, function (all, n, u) { return val(Number(n.replace(/,/g, "")), u); }); }
  function ratioStr(x) { if (!ok(x)) return "n/a"; if (Math.abs(x) >= 1000) return group(x); var r = Number(x.toPrecision(3)); return Math.abs(r) < 1e-4 ? r.toExponential(1) : x.toPrecision(3); }
  function times(x) { return ok(x) ? ratioStr(x) + "×" : "n/a"; }
  function pct(x) { return ok(x) ? sig(x * 100, 3) + "%" : "n/a"; }
  function pval(x) { return !ok(x) ? "n/a" : x < 0.001 ? "below 0.001" : x.toFixed(3); }
  // the unit of an axis, chosen once for the chart from its largest value: {div, u}
  function axisUnit(unit, top) {
    var u = String(unit || "");
    if (/^ms\b/.test(u)) return top >= 1000 ? { div: 1000, u: "s" } : { div: 1, u: "ms" };
    if (u === "MiB") return top >= 1024 ? { div: 1024, u: "GiB" } : { div: 1, u: "MiB" };
    var s = unitScale(u, top);
    return s;
  }
  // an axis label is the same number formatter, with k, M and B for the large counts (18.5B rather than 18,500,000,000)
  function fmtAxis(x) {
    var a = Math.abs(x);
    if (a >= 1e9) return Number((x / 1e9).toPrecision(3)) + "B";
    if (a >= 1e6) return Number((x / 1e6).toPrecision(3)) + "M";
    if (a >= 1e4) return Number((x / 1e3).toPrecision(3)) + "k";
    return sig(x, 3);
  }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : (many || one + "s")); }
  function median(v) { var s = v.slice().sort(function (a, b) { return a - b; }); var n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : NaN; }
  // linear interpolation between the two nearest ranks, as the report's own percentile (buffon/stats/core.py percentile)
  function quantile(v, p) {
    var s = v.slice().sort(function (a, b) { return a - b; }); if (!s.length) return NaN;
    var pos = (s.length - 1) * p, lo = Math.floor(pos), hi = Math.min(lo + 1, s.length - 1);
    return s[lo] + (s[hi] - s[lo]) * (pos - lo);
  }


  // ------------------------------------------------------------------ routes: the view and its parameters live in the hash
  var HOME = "grid";
  var LISTS = { h: 1, m: 1 };
  function parse(hash) {
    var h = String(hash || "").replace(/^#/, "");
    var q = h.indexOf("?");
    var path = (q < 0 ? h : h.slice(0, q)).replace(/^\/+|\/+$/g, "");
    var params = {};
    if (q >= 0) new URLSearchParams(h.slice(q + 1)).forEach(function (v, k) { params[k] = LISTS[k] ? v.split(",").filter(Boolean) : v; });
    var parts = path ? path.split("/").map(decodeURIComponent) : [];
    return { view: parts[0] || HOME, args: parts.slice(1), params: params };
  }
  function serialize(route) {
    var path = "#/" + (route.view === HOME ? "" : [route.view].concat(route.args || []).map(encodeURIComponent).join("/"));
    var keys = Object.keys(route.params || {}).sort();
    var q = [];
    keys.forEach(function (k) {
      var v = route.params[k];
      if (v == null || v === "" || (Array.isArray(v) && !v.length && !LISTS[k])) return;
      var enc = function (x) { return encodeURIComponent(x).replace(/%3A/gi, ":"); };
      q.push(enc(k) + "=" + (Array.isArray(v) ? v.map(enc).join(",") : enc(v).replace(/%2C/gi, ",")));
    });
    return path + (q.length ? "?" + q.join("&") : "");
  }
  function link(view, args, params) { return serialize({ view: view || HOME, args: args || [], params: params || {} }); }
  function withParam(route, key, value) {
    var p = {}; Object.keys(route.params).forEach(function (k) { p[k] = route.params[k]; });
    if (value == null || value === "") delete p[key]; else p[key] = value;
    return serialize({ view: route.view, args: route.args, params: p });
  }

  // ------------------------------------------------------------------ the data, indexed once
  var API_NAME = { chat: "OpenAI Chat API", anthropic: "Anthropic API", responses: "OpenAI Responses API" };
  var API_ORDER = ["chat", "anthropic", "responses"];
  function apiName(a) { return API_NAME[a] || a; }
  var API_SHORT = { chat: "Chat API", anthropic: "Messages API", responses: "Responses API" };
  function apiShort(a) { return API_SHORT[a] || a; }
  // the other wire API on which a harness has a value for this metric (the first in the site order), or null: "can't run" is for a harness with a value on none
  function otherApi(I, key, h, api) {
    var by = I.cellOf[key] || {}, order = (I.apis || []).filter(function (a) { return a !== api; });
    for (var i = 0; i < order.length; i++) { var c = by[order[i]]; if (c && c.stats[h.id]) return order[i]; }
    return null;
  }
  function otherTip(h, a) { return shortName(h) + ": measured on " + apiName(a) + "; switch the API to compare."; }
  function naLabel(c) { return c.other ? apiShort(c.other) : c.cant ? "can't run" : "n/a"; }
  function Index(D) {
    var I = { D: D, harn: {}, bySlug: {}, fam: {}, metric: {}, cellOf: {}, glossary: {}, cellBySlug: {}, doc: {}, ref: null };
    I.order = {};   // the harnesses are in this order on every view and every chart: the baseline first, then the run's own order
    D.harnesses.forEach(function (h, i) { I.harn[h.id] = h; I.bySlug[h.slug] = h; I.order[h.id] = i; if (h.is_ref) I.ref = h; });
    D.families.forEach(function (f) { I.fam[f.id] = f; });
    D.metrics.forEach(function (m) { I.metric[m.key] = m; });
    D.glossary.forEach(function (g) { I.glossary[g.slug] = g; });
    D.docs.forEach(function (d) { I.doc[d.slug] = d; });
    I.profile = {}; (D.profiles || []).forEach(function (p) { I.profile[p.slug] = p; });
    I.unmeasured = (D.unmeasured || []).map(function (h) { return Object.assign({ unmeasured: true }, h); }); I.unBySlug = {}; I.unmeasured.forEach(function (h) { I.unBySlug[h.slug] = h; });
    D.cells.forEach(function (c) { I.cellBySlug[c.slug] = c; (I.cellOf[c.key] = I.cellOf[c.key] || {})[c.api_short] = c; });
    I.contenders = D.harnesses.filter(function (h) { return !h.is_ref; });
    // the wire APIs of the run, and the one most harnesses speak (the grid starts with it)
    var count = {}; I.envs = [];   // a variant that is an environment (a durable workload on Miniflare) is no wire API: it is chosen in the Durable section, and its cell never stands in for another's
    D.cells.forEach(function (c) {
      if (c.env_variant) { if (I.envs.indexOf(c.api_short) < 0) I.envs.push(c.api_short); }
      else if (c.api_short !== "-") { count[c.api_short] = count[c.api_short] || {}; Object.keys(c.stats).forEach(function (a) { count[c.api_short][a] = 1; }); }
    });
    I.apis = Object.keys(count).sort(function (a, b) {
      var d = Object.keys(count[b]).length - Object.keys(count[a]).length; if (d) return d;
      var x = API_ORDER.indexOf(a), y = API_ORDER.indexOf(b); return (x < 0 ? 99 : x) - (y < 0 ? 99 : y) || a.localeCompare(b);
    });
    I.defaultApi = I.apis[0] || "-";
    I.multiApi = I.apis.length > 1;
    I.famName = function (id) { return (I.fam[id] || {}).name || id; };
    I.abbr = D.glossary.filter(function (g) { return g.kind === "abbr"; });
    var auto = I.abbr.map(function (g) { return g.term; }).filter(function (t) { return /[A-Z]/.test(t) && t !== "MiB" && t !== "GiB"; });
    auto.sort(function (a, b) { return b.length - a.length; });
    I.abbrRe = auto.length ? new RegExp("(^|[^A-Za-z0-9_])(" + auto.map(function (t) { return t.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&"); }).join("|") + ")(?![A-Za-z0-9_])", "g") : null;
    I.abbrSlug = {}; I.abbr.forEach(function (g) { I.abbrSlug[g.term] = g.slug; });
    buildSections(I);
    return I;
  }

  // the trust label of a run is its own: a run that was not on quiet dedicated hardware is provisional. A value, a chart and a card carry the badge only when their run is.
  function runOf(I, id) { return (I.D.runs || []).filter(function (r) { return r.id === id; })[0] || null; }
  function provRuns(I, ids) { return (ids || []).map(function (id) { return runOf(I, id); }).filter(function (r) { return r && r.provisional; }); }
  function provWhy(runs) { var out = []; runs.forEach(function (r) { (r.provisional_reasons || ["not on quiet dedicated hardware"]).forEach(function (x) { if (out.indexOf(x) < 0) out.push(x); }); }); return out.join("; "); }
  function provBadge(runs) { return runs.length ? '<span class="prov" tabindex="0" data-tip="' + esc("Provisional: " + provWhy(runs)) + '">Provisional</span>' : ""; }
  function cellProv(I, cell) { return provRuns(I, [cell.run]); }

  // what the reader chose, read from the route: the harnesses (chips), the baseline, ratio or values, and the wire API
  function stateOf(I, route) {
    var P = route.params, D = I.D;
    var hs = P.h && P.h.length ? D.harnesses.filter(function (h) { return P.h.indexOf(h.slug) >= 0; }) : D.harnesses.slice();
    var sp = String(P.sort || "").split(":");
    return { hs: hs, base: I.bySlug[P.base] || I.ref, mode: P.v === "values" ? "values" : "ratio", api: I.apis.indexOf(P.api) >= 0 ? P.api : I.defaultApi, route: route,
             view: ["dots", "bars", "rounds", "line"].indexOf(P.view) >= 0 ? P.view : "bars", sort: sp[0] ? { key: sp[0], dir: sp[1] === "desc" ? "desc" : "asc" } : null };
  }
  // the hash that adds or removes one harness; a list equal to its starting list is left out of the URL, an empty one is written as `none`
  function toggle(I, route, value) {
    var st = stateOf(I, route), cur = st.hs.map(function (h) { return h.slug; }), i = cur.indexOf(value);
    if (i >= 0) cur.splice(i, 1); else cur.push(value);
    var start = I.D.harnesses.map(function (h) { return h.slug; });
    cur = start.filter(function (x) { return cur.indexOf(x) >= 0; });
    return withParam(route, "h", cur.length === start.length ? "" : (cur.length ? cur : ["none"]));
  }

  // explain(html): every abbreviation in running text gets its expansion as a tooltip and a link to the glossary. Text inside links, code,
  // formulas, charts and form options is left alone.
  var SKIP = { a: 1, abbr: 1, code: 1, pre: 1, svg: 1, script: 1, style: 1, option: 1, select: 1, textarea: 1, title: 1, kbd: 1 };
  var VOID = { br: 1, img: 1, input: 1, hr: 1, meta: 1, link: 1, wbr: 1, source: 1, col: 1 };
  function explain(I, html) {
    if (!I.abbrRe) return html;
    var parts = html.split(/(<[^>]+>)/);
    var stack = [];
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (!p) continue;
      if (p.charAt(0) === "<") {
        var m = /^<\/?([a-zA-Z][a-zA-Z0-9-]*)/.exec(p);
        if (!m) continue;
        var tag = m[1].toLowerCase();
        if (p.charAt(1) === "/") {
          for (var j = stack.length - 1; j >= 0; j--) if (stack[j].tag === tag) { stack.length = j; break; }
        } else if (!VOID[tag] && !/\/>$/.test(p)) {
          var parentSkip = stack.length ? stack[stack.length - 1].skip : false;
          stack.push({ tag: tag, skip: parentSkip || !!SKIP[tag] || /class="[^"]*\b(katex|raw)\b/.test(p) });
        }
      } else if (!(stack.length && stack[stack.length - 1].skip)) {
        parts[i] = p.replace(I.abbrRe, function (all, pre, t) {
          var g = I.glossary[I.abbrSlug[t]];
          return pre + '<abbr class="term" tabindex="0" data-term="' + g.slug + '">' + t + "</abbr>";
        });
      }
    }
    return parts.join("");
  }

  // ------------------------------------------------------------------ building blocks
  function term(I, slug, text) {
    var g = I.glossary[slug];
    return '<a class="term" href="' + link("glossary", [], { t: slug }) + '" data-term="' + esc(slug) + '">' + esc(text || (g && g.term) || slug) + "</a>";
  }
  function dot(h) { return '<i class="dot h-' + esc(h.colour) + '"></i>'; }
  // a harness's name links to its page; Pi, the reference, links to its own site
  function hname(h, href) {
    var inner = dot(h) + "<span>" + esc(shortName(h)) + "</span>";
    return href === false ? '<span class="hn">' + inner + "</span>" : '<a class="hn" href="' + (href || link("harness", [h.slug])) + '" title="' + esc(h.name) + '">' + inner + "</a>";
  }
  // prose from the method documents: escaped, and a file name (EXTERNAL.md, arm.toml) set as code
  function seg(options, current, attr) {
    return '<div class="seg" role="group">' + options.map(function (o) {
      return '<button type="button" ' + attr(o[0]) + ' aria-pressed="' + (String(o[0]) === String(current) ? "true" : "false") + '">' + esc(o[1]) + "</button>";
    }).join("") + "</div>";
  }
  function select(param, options, current, label) {
    return '<label class="ctl"><span>' + esc(label) + '</span><select data-param="' + esc(param) + '">' + options.map(function (o) {
      return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(current || "") ? " selected" : "") + ">" + esc(o[1]) + "</option>";
    }).join("") + "</select></label>";
  }
  // card: a titled block with an optional chart/table switch. ui.tables[id] remembers the switch across redraws.
  function card(ctx, o) {
    var hasTable = !!o.table;
    var asTable = hasTable && ctx.ui.tables[o.id];
    var head = '<header class="card-h"><div><h2>' + o.title + "</h2>" + (o.sub ? '<p class="sub">' + o.sub + "</p>" : "") + "</div>" + '<div class="card-tools">' + (o.tools || "") +
      (hasTable ? seg([["chart", "Chart"], ["table", "Table"]], asTable ? "table" : "chart", function (v) { return 'data-view-switch="' + esc(o.id) + '" data-value="' + v + '"'; }) : "") + "</div></header>";
    var body = hasTable ? '<div class="as-chart"' + (asTable ? " hidden" : "") + ">" + o.chart + '</div><div class="as-table"' + (asTable ? "" : " hidden") + ">" + o.table + "</div>" : (o.chart || o.body || "");
    return '<section class="card' + (o.cls ? " " + o.cls : "") + '" id="' + esc(o.id) + '" data-chart-card="' + (hasTable ? "1" : "") + '">' + head + body + (o.foot ? '<div class="card-f">' + o.foot + "</div>" : "") + "</section>";
  }

  // table: rows of cells {h: html, v: sort value, num: bool}; sortable by any column, the order kept in ui.sort[id]; a CSV of the same rows.
  function table(ctx, id, head, rows, opts) {
    opts = opts || {};
    var st = ctx.ui.sort[id];
    var order = rows.map(function (r, i) { return i; });
    if (st) {
      order.sort(function (a, b) {
        var x = rows[a][st.col].v, y = rows[b][st.col].v;
        var nx = x == null || x === "" || (typeof x === "number" && !isFinite(x)), ny = y == null || y === "" || (typeof y === "number" && !isFinite(y));
        if (nx !== ny) return nx ? 1 : -1;
        var d = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
        return (st.dir === "desc" ? -d : d) || a - b;
      });
    }
    var ths = head.map(function (hd, i) {
      var label = typeof hd === "string" ? hd : hd.h;
      var num = typeof hd === "object" && hd.num;
      var s = st && st.col === i ? (st.dir === "desc" ? "descending" : "ascending") : "none";
      return '<th scope="col" class="' + (num ? "num" : "") + '" aria-sort="' + s + '"><button type="button" data-sort-table="' + esc(id) + '" data-col="' + i + '">' + label +
        '<i class="arrow">' + (s === "ascending" ? "↑" : s === "descending" ? "↓" : "↕") + "</i></button></th>";
    }).join("");
    var body = order.map(function (i) {
      return "<tr" + (rows[i].attrs || "") + ">" + rows[i].map(function (c, j) { var num = typeof head[j] === "object" && head[j].num; return "<td" + (num ? ' class="num"' : "") + ">" + c.h + "</td>"; }).join("") + "</tr>";
    }).join("");
    var tools = opts.tools === false ? "" : '<div class="table-tools">' + (rows.length > 10 ? '<input type="search" class="find" placeholder="Filter rows" data-filter-table="' + esc(id) + '" aria-label="Filter rows">' : "") +
      '<button type="button" class="btn" data-csv="' + esc(id) + '">Download CSV</button></div>';
    return tools + '<div class="tablewrap"><table class="data" id="t-' + esc(id) + '"><thead><tr>' + ths + "</tr></thead><tbody>" + body + "</tbody></table></div>";
  }
  function td(h, v) { return { h: h, v: v === undefined ? String(h).replace(/<[^>]+>/g, "") : v }; }

  // ------------------------------------------------------------------ scales
  function niceTicks(lo, hi, n) {
    var span = hi - lo || Math.abs(hi) || 1, step = Math.pow(10, Math.floor(Math.log10(span / n))), err = span / n / step;
    step *= err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
    var out = [];
    for (var x = Math.ceil(lo / step) * step; x <= hi + step * 1e-9; x += step) out.push(Number(x.toPrecision(12)));
    return out;
  }

  // ------------------------------------------------------------------ charts: one frame (size, margins, axes, legend) for every chart, drawn in SVG at the real width so text stays crisp
  var CH = { H: 220, T: 18, B: 34, R: 16 };
  function svgOpen(w, h, label) { return '<svg class="chart" viewBox="0 0 ' + w + " " + h + '" width="' + w + '" height="' + h + '" role="img" aria-label="' + esc(label) + '">'; }
  // the width of a chart in a card: the page width less the card's padding, divided among `cols` columns
  function chartWidth(ctx, cols) { cols = cols || 1; var gap = 14; return Math.max(280, Math.floor(((ctx.avail || ctx.width) - (cols - 1) * gap) / cols) - 34); }
  // the frame of a line chart: y axis from lo to hi (linear, or logarithmic when `log`) in the unit chosen for the chart, the unit at the top left, the x label at the bottom right,
  // and room at the right for the name of each line (`labelW`)
  function logTicks(lo, hi) {
    var out = [], k0 = Math.floor(Math.log10(lo)), k1 = Math.ceil(Math.log10(hi)), mult = k1 - k0 <= 3 ? [1, 2, 5] : [1];
    for (var k = k0; k <= k1; k++) mult.forEach(function (m) { var t = m * Math.pow(10, k); if (t >= lo * 0.9999 && t <= hi * 1.0001) out.push(Number(t.toPrecision(12))); });
    return out.length >= 2 ? out : niceTicks(lo, hi, 3).filter(function (t) { return t > 0; });
  }
  // a name is never cut: on a narrow chart a long one is set on two lines (at the space nearest its middle), and the gutter at the right of the plot is as wide as the widest line
  function nameLines(name, narrow) {
    if (!narrow || name.length <= 11 || name.indexOf(" ") < 0) return [name];
    var mid = name.length / 2, best = -1;
    for (var i = 0; i < name.length; i++) if (name.charAt(i) === " " && (best < 0 || Math.abs(i - mid) < Math.abs(best - mid))) best = i;
    return [name.slice(0, best), name.slice(best + 1)];
  }
  function plotFrame(o) {
    var W = Math.max(280, Math.floor(o.width)), H = CH.H, T = CH.T, B = CH.B, narrow = W < 460, R, labelW = 0;
    if (o.names && o.names.length) labelW = 16 + Math.ceil(Math.max.apply(null, [].concat.apply([], o.names.map(function (n) { return nameLines(n, narrow); })).map(function (l) { return l.length; })) * 6.8);
    R = CH.R + labelW;
    var au = axisUnit(o.unit, o.hi), lo = o.lo, hi = o.hi, lg = !!o.log;
    var ticks = (lg ? logTicks(lo, hi) : niceTicks(lo, hi, 4)).filter(function (t) { return t >= lo - 1e-9 && t <= hi + 1e-9; });
    var labels = ticks.map(function (t) { return fmtAxis(t / au.div); });
    var L = 16 + 7 * Math.max.apply(null, labels.map(function (x) { return x.length; }).concat([2]));
    var tf = lg ? Math.log : function (v) { return v; }, a = tf(lo), b = tf(hi);
    var Y = function (v) { return T + (b - tf(v)) / (b - a) * (H - T - B); };
    var svg = svgOpen(W, H, o.label || "chart");
    ticks.forEach(function (t, i) { svg += '<line class="gl" x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(t).toFixed(1) + '" y2="' + Y(t).toFixed(1) + '"/><text class="yl" x="' + (L - 8) + '" y="' + (Y(t) + 4).toFixed(1) + '">' + esc(labels[i]) + "</text>"; });
    svg += '<text class="unit" x="4" y="10">' + esc(au.u + (lg ? ", log scale" : "")) + '</text><text class="axl" x="' + (W - CH.R) + '" y="' + (H - 4) + '">' + esc(o.xlabel || "") + "</text>";
    return { W: W, H: H, L: L, R: R, T: T, B: B, Y: Y, svg: svg, au: au, labelW: labelW, narrow: narrow };
  }
  // the name of each line in a gutter at the right of the plot, level with the line's last point, with a thin leader from that point. Names are pushed apart so that two do not overlap.
  function endLabels(items, f) {
    var gx = f.W - f.R + 8, top = f.T + 4, bottom = f.H - f.B + 2;
    items.forEach(function (it) { it.lines = nameLines(it.name, f.narrow); it.h = it.lines.length * 12; });
    var sorted = items.slice().sort(function (p, q) { return p.y - q.y; });
    var need = function (p, q) { return (p.h + q.h) / 2 + 1; };
    sorted.forEach(function (it, i) { it.ly = Math.max(it.y, i ? sorted[i - 1].ly + need(sorted[i - 1], it) : top + it.h / 2); });
    for (var i = sorted.length - 1; i >= 0; i--) sorted[i].ly = Math.min(sorted[i].ly, i === sorted.length - 1 ? bottom - sorted[i].h / 2 : sorted[i + 1].ly - need(sorted[i], sorted[i + 1]));
    return sorted.map(function (it) {
      var y0 = it.ly - (it.lines.length - 1) * 6 + 4;
      return '<g class="series h-' + esc(it.colour) + '"><line class="lead" x1="' + (it.x + 4).toFixed(1) + '" y1="' + it.y.toFixed(1) + '" x2="' + (gx - 3).toFixed(1) + '" y2="' + it.ly.toFixed(1) + '"/>' +
        '<text class="elabel" x="' + gx.toFixed(1) + '" y="' + y0.toFixed(1) + '"><title>' + esc(it.name) + "</title>" + it.lines.map(function (l, k) { return '<tspan x="' + gx.toFixed(1) + '"' + (k ? ' dy="12"' : "") + ">" + esc(l) + "</tspan>"; }).join("") + "</text></g>";
    }).join("");
  }

  // rounds: one line per series in the order the rounds ran; each round is a hover column listing every value. The y axis zooms in on the values: it shows a change, not a size.
  function linesChart(series, o) {
    var all = []; series.forEach(function (s) { all = all.concat(s.values); });
    if (!all.length) return "";
    var n = Math.max.apply(null, series.map(function (s) { return s.values.length; }));
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.12 || Math.abs(hi) * 0.05 || 1; lo -= pad; hi += pad;
    var f = plotFrame({ width: o.width, lo: lo, hi: hi, unit: o.unit, xlabel: "round →", label: o.label || "values per round", names: series.map(function (sr) { return sr.name; }) }), W = f.W, L = f.L, R = f.R, H = f.H, T = f.T, B = f.B, Y = f.Y, s = f.svg;
    var X = function (i) { return L + (n === 1 ? (W - L - R) / 2 : i * (W - L - R) / (n - 1)); };
    var step = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((W - L - R) / 48))));
    for (var i = 0; i < n; i += step) s += '<text class="xl" x="' + X(i).toFixed(1) + '" y="' + (H - 18) + '">' + (i + 1) + "</text>";
    series.forEach(function (sr) {
      var pts = sr.values.map(function (v, i) { return X(i).toFixed(1) + "," + Y(v).toFixed(1); });
      s += '<g class="series h-' + esc(sr.colour) + '"><polyline points="' + pts.join(" ") + '"/>' + sr.values.map(function (v, i) { return '<circle cx="' + X(i).toFixed(1) + '" cy="' + Y(v).toFixed(1) + '" r="3"/>'; }).join("") + "</g>";
    });
    s += endLabels(series.map(function (sr) { return { name: sr.name, colour: sr.colour, x: X(sr.values.length - 1), y: Y(sr.values[sr.values.length - 1]) }; }), f);
    var colw = n === 1 ? W - L - R : (W - L - R) / (n - 1);
    for (var k = 0; k < n; k++) {
      var tip = "Round " + (k + 1) + series.map(function (sr) { return k < sr.values.length ? "\n" + sr.name + ": " + val(sr.values[k], o.unit) : ""; }).join("");
      s += '<rect class="hit" x="' + (X(k) - colw / 2).toFixed(1) + '" y="' + T + '" width="' + colw.toFixed(1) + '" height="' + (H - T - B) + '" data-tip="' + esc(tip) + '"/>';
    }
    return '<div class="svgwrap">' + s + "</svg></div>";
  }

  // strip plot: every round of every harness as a dot on one shared scale, the median as a tick, so spread and outliers show at a glance
  function stripChart(rows, o) {
    var W = Math.max(280, Math.floor(o.width)), RH = 30, L = Math.min(150, W * 0.32), R = CH.R, T = 8, B = CH.B, H = T + B + rows.length * RH;
    var all = []; rows.forEach(function (r) { all = all.concat(r.values); });
    if (!all.length) return "";
    var lo = Math.min(0, Math.min.apply(null, all)), hi = Math.max.apply(null, all) * 1.05 || 1, au = axisUnit(o.unit, hi);
    var X = function (v) { return L + (v - lo) / (hi - lo) * (W - L - R); };
    var s = svgOpen(W, H, o.label || "every round");
    niceTicks(lo, hi, 4).filter(function (t) { return t <= hi; }).forEach(function (t) { s += '<line class="gl" x1="' + X(t).toFixed(1) + '" x2="' + X(t).toFixed(1) + '" y1="' + T + '" y2="' + (H - B) + '"/><text class="xl" x="' + X(t).toFixed(1) + '" y="' + (H - 18) + '">' + esc(fmtAxis(t / au.div)) + "</text>"; });
    s += '<text class="axl" x="' + (W - R) + '" y="' + (H - 4) + '">' + esc(au.u) + " →</text>";
    rows.forEach(function (r, i) {
      var y = T + i * RH + RH / 2, m = median(r.values);
      s += '<g class="series h-' + esc(r.colour) + '"><text class="rl" x="' + (L - 10) + '" y="' + (y + 4) + '">' + esc(r.name) + "</text>";
      r.values.forEach(function (v, k) { s += '<circle class="jit" cx="' + X(v).toFixed(1) + '" cy="' + (y + ((k * 7) % 11 - 5)).toFixed(1) + '" r="3.2" data-tip="' + esc(r.name + "\nround " + (k + 1) + ": " + val(v, o.unit)) + '"/>'; });
      s += '<line class="med" x1="' + X(m).toFixed(1) + '" x2="' + X(m).toFixed(1) + '" y1="' + (y - 11) + '" y2="' + (y + 11) + '" data-tip="' + esc(r.name + "\nmedian " + val(m, o.unit)) + '"/></g>';
    });
    return '<div class="svgwrap">' + s + "</svg></div>";
  }

  // histogram of the bootstrap ratios: where the resampled ratios land, the 95% interval, the noise band and 1.00
  function histChart(hist, c, o) {
    if (!hist || !hist.length) return "";
    var W = Math.max(280, Math.floor(o.width)), H = CH.H, L = 14, R = CH.R, T = 26, B = CH.B;
    var lo = Math.min(hist[0][0], c.ci95[0]), hi = Math.max(hist[hist.length - 1][1], c.ci95[1]);
    // 1.00 and the noise band are drawn when they are near the draws; when they are far away, drawing them would squash the draws into a sliver
    var span = Math.log(hi / lo), gap = 1 < lo ? Math.log(lo) : 1 > hi ? -Math.log(hi) : 0, withOne = gap <= Math.max(span * 2, 0.05);
    if (withOne) { lo = Math.min(lo, 1); hi = Math.max(hi, 1); if (ok(c.floor)) { lo = Math.min(lo, 1 / (1 + c.floor)); hi = Math.max(hi, 1 + c.floor); } }
    lo /= 1.01; hi *= 1.01;
    var a = Math.log(lo), b = Math.log(hi), X = function (v) { return L + (Math.log(v) - a) / (b - a) * (W - L - R); };
    var top = Math.max.apply(null, hist.map(function (x) { return x[2]; })) || 1, Y = function (n) { return H - B - n / top * (H - T - B); };
    var s = svgOpen(W, H, "where the resampled ratios land");
    if (withOne && ok(c.floor)) s += '<rect class="band" x="' + X(1 / (1 + c.floor)).toFixed(1) + '" y="' + T + '" width="' + (X(1 + c.floor) - X(1 / (1 + c.floor))).toFixed(1) + '" height="' + (H - T - B) + '"/>';
    hist.forEach(function (x) {
      var inside = x[0] >= c.ci95[0] && x[1] <= c.ci95[1];
      s += '<rect class="hb' + (inside ? " in" : "") + '" x="' + X(x[0]).toFixed(1) + '" y="' + Y(x[2]).toFixed(1) + '" width="' + Math.max(1, X(x[1]) - X(x[0]) - 1).toFixed(1) + '" height="' + (H - B - Y(x[2])).toFixed(1) + '" data-tip="' + esc(ratioStr(x[0]) + " to " + ratioStr(x[1]) + "×: " + x[2] + " resamples") + '"/>';
    });
    if (withOne) s += '<line class="one" x1="' + X(1).toFixed(1) + '" x2="' + X(1).toFixed(1) + '" y1="' + (T - 6) + '" y2="' + (H - B) + '"/><text class="xl" x="' + X(1).toFixed(1) + '" y="' + (T - 9) + '">1.00 (Pi)</text>';
    else s += '<text class="far ' + (1 > hi ? "fr" : "fl") + '" x="' + (1 > hi ? W - R : L) + '" y="' + (T - 9) + '">' + (1 > hi ? "1.00 (Pi) is far to the right →" : "← 1.00 (Pi) is far to the left") + "</text>";
    [[c.ci95[0], "L"], [c.ci95[1], "U"]].forEach(function (q) { s += '<line class="cil" x1="' + X(q[0]).toFixed(1) + '" x2="' + X(q[0]).toFixed(1) + '" y1="' + T + '" y2="' + (H - B) + '"/><text class="xl cit" x="' + X(q[0]).toFixed(1) + '" y="' + (H - 18) + '">' + q[1] + " " + ratioStr(q[0]) + "</text>"; });
    s += '<line class="rl2" x1="' + X(c.ratio).toFixed(1) + '" x2="' + X(c.ratio).toFixed(1) + '" y1="' + T + '" y2="' + (H - B) + '"/>';
    return '<div class="svgwrap">' + s + "</svg></div>";
  }

  // horizontal bars, one row per harness in the harness order: name, bar from zero with its number at the end of the bar, an optional whisker (a range) and an optional chip.
  // rows: {h, f (0 to 1 of the track), label, tip, href, whisker [f, f], chip html, note text, na text}. The track keeps room for the label, so a number never runs out of the chart.
  function barRows(rows, o) {
    o = o || {};
    var lw = Math.max(7.5, 1.5 + 0.66 * Math.max.apply(null, rows.map(function (r) { return String(r.label || "").length; }).concat([0])));
    var base = ' style="--lw:' + lw.toFixed(1) + "em" + (o.base == null ? "" : ";--pix:" + o.base.toFixed(4)) + '"';
    var grid = o.axis ? o.axis.ticks.map(function (t) { return '<i class="tk" style="--f:' + t.f.toFixed(4) + '"></i>'; }).join("") : "";
    var body = rows.map(function (r) {
      var name = '<span class="bn">' + (r.name != null ? r.name : hname(r.h, r.plain ? false : undefined)) + "</span>";
      var f = Math.max(0, Math.min(1, r.f || 0));
      return '<div class="brow h-' + esc(r.h.colour) + (r.cls ? " " + esc(r.cls) : "") + '"' + (r.tip ? ' data-tip="' + esc(r.tip) + '"' : "") + ">" + name + '<span class="bt" style="--f:' + f.toFixed(4) + ";--e:" + Math.max(f, r.whisker ? Math.min(1, r.whisker[1]) : 0).toFixed(4) + '">' + grid + (r.empty ? "" : '<i class="bf"></i>') +
        (r.whisker ? '<i class="bw" style="--a:' + Math.max(0, Math.min(1, r.whisker[0])).toFixed(4) + ";--b:" + Math.max(0, Math.min(1, r.whisker[1])).toFixed(4) + '"></i>' : "") +
        (r.href ? '<a class="bl" href="' + esc(r.href) + '"><b>' + esc(r.label) + "</b></a>" : '<span class="bl"><b>' + esc(r.label) + "</b></span>") + "</span>" +
        (r.chip ? '<span class="bc">' + r.chip + "</span>" : r.note ? '<span class="bc"><small class="bnote">' + esc(r.note) + "</small></span>" : "<span></span>") + "</div>";
    }).join("");
    var axis = o.axis ? '<div class="brow baxis"><span class="bn"></span><span class="bt">' + o.axis.ticks.map(function (t) { return '<span class="tl" style="--f:' + t.f.toFixed(4) + '">' + esc(t.label) + "</span>"; }).join("") + '</span><span class="bc"><small class="bnote">' + esc(o.axis.label) + "</small></span></div>" : "";
    return '<div class="bars' + (o.base == null ? "" : " has-base") + (o.axis ? " has-axis" : "") + '"' + base + ">" + body + axis + "</div>";
  }

  // ------------------------------------------------------------------ names, and the ratio of any harness to any other
  function shortName(h) { return h.name.replace(/\s*\([^)]*\)\s*$/, ""); }
  // a harness's own docs: Pi's site for Pi, else the manifest's homepage
  function docsOf(h) { return h.is_ref ? "https://pi.dev" : (h.command || {}).homepage; }
  function apiNote(I, cell) { return I.multiApi && cell.api_short !== "-" ? API_NAME[cell.api_short] || cell.api_short : ""; }
  function measureName(I, cell) { var w = I.D.workloads[cell.workload] || {}, a = apiNote(I, cell); return (w.title || cell.scenario) + ", " + cell.metric_word + (a ? " (" + a + ")" : ""); }
  // {round key: value} of one harness in one cell, from the paired rounds the report kept (Pi's are the y side of any comparison)
  function roundsOf(cell, h) {
    var out = {}, src = h.is_ref ? cell.comparisons[Object.keys(cell.comparisons)[0]] : cell.comparisons[h.id];
    if (!src) return null;
    src.rounds.forEach(function (k, i) { out[JSON.stringify(k)] = h.is_ref ? src.y[i] : src.x[i]; });
    return out;
  }
  function seeded(text) { var s = 2166136261; for (var i = 0; i < text.length; i++) s = Math.imul(s ^ text.charCodeAt(i), 16777619) >>> 0; return function () { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; }; }
  // a harness that did different work in a cell (its manifest has a divergence) has no ratio there: the report says so with `not_compared`, a reason
  var NOT_COMPARED = "different work: not compared";
  function notComparedOf(cell, h, base) {
    var a = cell.comparisons[h.id], b = base ? cell.comparisons[base.id] : null;
    return (a && a.not_compared) || (b && b.not_compared) || null;
  }
  function globRe(pat) { return new RegExp("^" + String(pat).replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$"); }
  // the divergences of a harness (copied from its manifest) that cover this cell: a workload glob, and a metric glob unless the list is empty
  function divergencesOf(h, cell) {
    return (h.divergences || []).filter(function (d) {
      return (d.workloads || []).some(function (w) { return globRe(w).test(cell.scenario); }) && (!(d.metrics || []).length || d.metrics.some(function (m) { return globRe(m).test(cell.metric); }));
    });
  }
  function versus(I, cell, h, base) {
    var key = cell.slug + "|" + h.id + "|" + base.id;
    I.vs = I.vs || {};
    if (key in I.vs) return I.vs[key];
    var out = null, nc = notComparedOf(cell, h, base);
    if (nc) {
      out = { notcmp: nc, med: cell.stats[h.id] ? cell.stats[h.id].median : null };
    } else if (base.is_ref && cell.comparisons[h.id]) {
      var c = cell.comparisons[h.id];
      out = { ratio: c.ratio, lo: c.ci95[0], hi: c.ci95[1], n: c.n, med: c.arm_median, bmed: c.ref_median, p: c.p_holm, floor: c.floor, mde: cell.mde };
    } else {
      var a = roundsOf(cell, h), b = roundsOf(cell, base);
      var keys = a && b ? Object.keys(a).filter(function (k) { return k in b; }) : [];
      if (keys.length >= 2) {
        var x = keys.map(function (k) { return a[k]; }), y = keys.map(function (k) { return b[k]; }), rnd = seeded(key), draws = [];
        for (var d = 0; d < 2000; d++) { var xs = [], ys = []; for (var j = 0; j < keys.length; j++) { var t = Math.floor(rnd() * keys.length); xs.push(x[t]); ys.push(y[t]); } var my = median(ys); if (my) draws.push(median(xs) / my); }
        draws.sort(function (p, q) { return p - q; });
        out = { ratio: median(x) / median(y), lo: quantile(draws, 0.025), hi: quantile(draws, 0.975), n: keys.length, med: median(x), bmed: median(y), p: null, floor: null, mde: null };
      }
    }
    I.vs[key] = out;
    return out;
  }

  // ------------------------------------------------------------------ units and values
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  // instructions and cycles run to billions: scale them by the size of `ref`, and name every other unit short
  function unitScale(unit, ref) {
    var u = String(unit || "");
    ref = ok(ref) ? ref : 1;
    if (/^(instructions|cycles)/.test(u)) {
      var a = Math.abs(ref), p = a >= 1e9 ? [1e9, "G"] : a >= 1e6 ? [1e6, "M"] : a >= 1e3 ? [1e3, "k"] : [1, ""];
      return { div: p[0], u: (p[1] ? p[1] + " " : "") + u.replace(/^instructions/, "instr") };
    }
    return { div: 1, u: u.replace(/^ms of CPU time/, "ms").replace(/^bytes/, "B") };
  }
  function unitOf(unit) { var u = String(unit || ""); return /^ms\b/.test(u) ? "ms or s" : u === "MiB" ? "MiB or GiB" : unitScale(u, 1).u; }

  // ------------------------------------------------------------------ one cell of the grid
  function metricCell(I, key, api) {
    var by = I.cellOf[key];
    if (!by) return null;
    if (api === "native") return by["-"] || null;                 // the Durable section's environment choice: each environment is its own cell and never stands in for another's
    if (I.envs.indexOf(api) >= 0) return by[api] || null;
    return by["-"] || by[api] || null;
  }
  // the reason a harness has no value, short: the runner's first words ("no Pi-dialect RPC mode"). The full reason is on the harness page.
  var GENERIC_NA = /^it (has no value for this measurement|was not run on this workload) in this run$/;
  function isCant(reason) { return !!reason && !GENERIC_NA.test(reason); }
  function naTip(h, reason) {
    var r = String(reason || "it has no value for this measurement in this run"), i = r.indexOf(": ");
    return shortName(h) + ": " + (i > 0 ? r.slice(0, i) : r);
  }
  // {value, text parts, tip, href} for one harness in one column, or {na: tip}
  function gridCell(I, st, mt, h) {
    var cell = metricCell(I, mt.key, st.api);
    if (!cell) { var o1 = otherApi(I, mt.key, h, st.api); return o1 ? { na: otherTip(h, o1), other: o1 } : { na: shortName(h) + ": this metric has no value " + (st.api === "native" || I.envs.indexOf(st.api) >= 0 ? "in the " + st.api + " environment." : "with the " + apiName(st.api) + ".") }; }
    var s = cell.stats[h.id];
    if (!s) { var o2 = otherApi(I, mt.key, h, st.api); return o2 ? { na: otherTip(h, o2), other: o2 } : { na: naTip(h, cell.na[h.id]), cant: isCant(cell.na[h.id]), why: cell.na[h.id] }; }
    var href = cellHref(cell, h, I), mid = s.q1 != null ? "\nmiddle half " + span(s.q1, s.q3, cell.unit) : "";
    var ownTip = shortName(h) + ": " + measureName(I, cell) + "\nmedian " + val(s.median, cell.unit) + " over " + plural(s.n, "round") +
      (s.ci ? "\n95% interval of the median " + span(s.ci[0], s.ci[1], cell.unit) : "") + mid;
    if (st.mode === "ratio") {
      if (h === st.base) return { value: 1, n: "1.00", u: "×", tip: ownTip + "\nThis is the baseline.", href: href, cell: cell, base: true, csv: 1, prov: cellProv(I, cell) };
      var bs = cell.stats[st.base.id];
      if (!bs) return { na: shortName(h) + ": " + shortName(st.base) + " has no value here, so there is no ratio to it.", noratio: true };
      var v = versus(I, cell, h, st.base);
      if (!v) return { na: shortName(h) + ": it shares no two rounds with " + shortName(st.base) + ", so there is no ratio.", noratio: true };
      if (v.notcmp) return notComparedCell(I, h, s, cell, v.notcmp, href);
      return { value: v.ratio, lo: v.lo, hi: v.hi, n: ratioStr(v.ratio), u: "×", tip: valueTip(I, h, st.base, cell, v), href: href, cell: cell, csv: v.ratio, prov: cellProv(I, cell) };
    }
    var ratio = "";
    if (h !== st.base) { var w = versus(I, cell, h, st.base); if (w && w.notcmp) ratio = "\n" + NOT_COMPARED + ": " + w.notcmp; else if (w) ratio = "\n" + times(w.ratio) + " " + shortName(st.base) + " (95% interval " + ratioStr(w.lo) + " to " + ratioStr(w.hi) + ")"; }
    var p = parts(s.median, cell.unit), own = cell.comparisons[h.id], ownNc = own && own.not_compared;
    return { value: s.median, n: p[0], u: p[1], lo: s.ci ? s.ci[0] : null, hi: s.ci ? s.ci[1] : null, tip: ownTip + ratio + "\nClick for how it was measured.", href: href, cell: cell, csv: s.median, prov: cellProv(I, cell), nobar: !!ownNc, label: ownNc ? NOT_COMPARED : "" };
  }
  // the arm's own median, the label, no ratio and no bar; a ratio sort puts it last (its value is null)
  function notComparedCell(I, h, s, cell, reason, href) {
    var p = parts(s.median, cell.unit);
    return { value: null, n: p[0], u: p[1], label: NOT_COMPARED, nobar: true, csv: "not compared", href: href, cell: cell, prov: cellProv(I, cell),
      tip: shortName(h) + ": " + measureName(I, cell) + "\nmedian " + val(s.median, cell.unit) + " over " + plural(s.n, "round") + "\n" + NOT_COMPARED + ": " + reason + "\nClick for how it was measured." };
  }

  // ------------------------------------------------------------------ the results: sections, each an explorer of its metrics, with one headline metric that starts chosen
  // A section holds the workloads that answer one question. `scen` says which workloads; `head` picks the headline metric key by pattern (the first match of each pattern, once, in order).
  // Every metric of the report is in exactly one section: those that match no section are in "Other".
  var SECTIONS = [
    { id: "start-up", title: "Start-up", kind: "metrics", scen: /^(overhead\/(version|pty)|devloop\/)/, about: "What it costs to start the harness: print its version, open it in a terminal, set it up.",
      what: "It runs the version command, opens the harness in a terminal and does a first run, and times each from the spawn until the harness has printed, drawn or exited.", head: [/^overhead-version\.cpu_ms$/] },
    { id: "prompts-and-tools", title: "Prompts and tools", kind: "metrics", scen: /^overhead\/(print|print-tools|rpc)$/, about: "What one prompt costs in print mode, in print mode with tool calls, and in an RPC session.",
      what: "One prompt in print mode, one prompt that makes eight tool calls, and an editor session over RPC, all against the same scripted model.", head: [/^overhead-print\.cpu_ms$/] },
    { id: "large-writes", title: "Large writes", kind: "metrics", scen: /^overhead\/print-write/, about: "What it costs to write one 200 KB file in a single tool call.",
      what: "One tool call writes a 200 KB file, streamed in small chunks. The clock covers the call and its result.", head: [/kb200_cpu_ms$/] },
    { id: "streaming", title: "Streaming", kind: "metrics", scen: /^streaming\//, about: "What it costs to show a long answer as it streams, in the terminal and in print mode.",
      what: "A long answer of 6,000 and then 60,000 characters streams into the terminal and to a script; the clock runs from the first byte to the final frame.", head: [/^streaming-tui.*cpu_ms_per_1k/, /^streaming-tui/, /^streaming-/] },
    { id: "sessions", title: "Sessions", kind: "metrics", scen: /^(longsession\/|overhead\/long-session)/, about: "How a long session behaves: resuming one, and one that keeps growing.",
      what: "A saved session of many turns is resumed and given one more prompt, and a session that keeps growing is timed turn by turn.", head: [/^longsession-resume.*ready_ms$/, /^longsession-resume/, /^longsession-/] },
    { id: "durable", title: "Durable", kind: "durable", ext: "durable", scen: /^durable\//, about: "", what: "Buffon's own durable workloads (open a stored conversation, warm and cold turns, store size, crash and resume) and each project's own durable suites.", head: [/^durable-mixed-3500\.warm_net_ms$/, /warm_net_ms$/, /warm_turn_ms$/, /cpu_ms$/, /^durable-/] },
    { id: "extensions", title: "Extensions", kind: "metrics", scen: /^overhead\/(print|rpc)-ext\d+$/, about: "What loading Pi extensions costs, from none to a hundred.",
      what: "The same prompt with 5, 10, 50 and 100 extensions loaded, in print mode and over RPC, beside the run with none.", head: [/^overhead-print-ext10\.cpu_ms$/, /^overhead-print-ext/] },
    { id: "agent-swarming", title: "Agent swarming", kind: "agents", about: "How many agents fit on one machine.", what: "How many agents run at once inside a fixed memory limit, found by doubling the count and then bisecting, with and without ten extensions loaded." },
    { id: "reliability", title: "Reliability", kind: "faults", about: "What each harness does when the provider fails or a program stops.", what: "The provider returns an error, a connection drops mid-stream or a program is stopped, and each harness is judged against Pi's outcome." },
    { id: "wire", title: "Wire", kind: "metrics", scen: null, plan: /^overhead\/(print|print-tools)$/, about: "What each harness sends to the scripted model: requests and bytes.",
      what: "It counts the requests and the bytes that each harness sends to the scripted model. It needs no run of its own: it is read from the prompt runs.", head: [/^overhead-print\.request_bytes$/, /request_bytes$/] },
    { id: "other", title: "Other", kind: "metrics", scen: /./, about: "Measures that no other section holds.", head: [], hideEmpty: true },
    { id: "other-suites", title: "Other suites", kind: "external", ext: "other", about: "Other projects' benchmarks, run as they are upstream or imported with their provenance. Buffon computes nothing from them.",
      what: "Other projects' own benchmarks, such as Pi-Bolt's suite, run unchanged from a pinned checkout and shown with their own tables." }
  ];
  function pickKeys(keys, pats, max) {
    var out = [];
    pats.forEach(function (p) { var k = keys.filter(function (x) { return p.test(x) && out.indexOf(x) < 0; })[0]; if (k) out.push(k); });
    keys.forEach(function (k) { if (out.length < 3 && out.indexOf(k) < 0) out.push(k); });
    return out.slice(0, max || 6);
  }
  // every section is in the rail, always, in this order. One the loaded runs have nothing for is muted ("not run yet") and its page says what it will measure and how to fill it (emptyBody).
  function buildSections(I) {
    var D = I.D, by = {};
    I.sections = []; I.sec = {}; I.secOf = {};
    D.metrics.forEach(function (mt) {
      var def = mt.lens === "wire" ? { id: "wire" } : SECTIONS.filter(function (x) { return x.scen && x.id !== "wire" && x.scen.test(mt.scenario); })[0];
      var id = def ? def.id : "other";
      (by[id] = by[id] || []).push(mt.key);
      I.secOf[mt.key] = id;
    });
    SECTIONS.forEach(function (def) {
      var keys = by[def.id] || [], s = {}, X = def.ext && D.external && D.external[def.ext], has;
      Object.keys(def).forEach(function (k) { s[k] = def[k]; });
      s.keys = keys;
      s.kind = def.kind === "durable" ? (keys.length ? "metrics" : "external") : def.kind;   // Durable is a section of Buffon's own metrics when there are any, and the project suites below them
      if (!X) s.ext = null;
      if (def.kind === "agents") has = !!(D.scale && D.scale.envelopes.length);
      else if (def.kind === "faults") has = !!(D.faults || []).length;
      else if (s.kind === "external") has = !!(X && X.groups && X.groups.length);
      else has = keys.length > 0;
      s.empty = !has;
      if (s.empty && def.hideEmpty) return;   // "Other" is a catch-all, not a place to look for
      if (s.kind === "metrics" && has) s.head = pickKeys(keys, def.head, 1)[0];
      if (def.kind === "durable" && keys.length && D.durable) s.defaults = [D.durable.headline].concat(D.durable.bars).filter(function (k) { return keys.indexOf(k) >= 0; });   // the headline, then the work a turn costs
      if (def.kind === "durable") s.about = keys.length ? "Buffon's own durable workloads, and below them each project's own durable suites, run as they are upstream." : "No durable run is in the results yet. Each project's own durable suites, run as they are upstream, are listed here when a run has them.";
      I.sections.push(s); I.sec[s.id] = s;
    });
  }
  // the wire APIs a section has values for, when more than one
  function secApis(I, s) {
    if (s.id === "durable") return durableEnvs(I);
    if (s.kind === "faults") { var f = faultApis(I); return f.length > 1 ? f : []; }
    if (s.kind === "agents" || s.kind === "external") return [];
    var out = I.apis.filter(function (a) { return s.keys.some(function (k) { return I.metric[k].apis.indexOf(a) >= 0; }); });
    return out.length > 1 ? out : [];
  }
  function secApi(I, st, sec) {
    if (sec && sec.id === "durable") { var envs = durableEnvs(I), p = st.route && st.route.params.api; return envs.length && envs.indexOf(p) >= 0 ? p : "native"; }
    var a = sec ? secApis(I, sec) : []; return a.length ? (a.indexOf(st.api) >= 0 ? st.api : a[0]) : st.api;
  }
  // the state that travels with a link between Results pages
  function keep(route) { var p = {}; ["h", "base", "v", "api"].forEach(function (k) { if (route.params[k] != null && route.params[k] !== "") p[k] = route.params[k]; }); return p; }
  function resultsCrumb(I, key) { var s = I.sec[I.secOf[key]]; return '<a href="' + link() + '">Results</a>' + (s ? ' › <a href="' + esc(link("r", [s.id])) + '">' + esc(s.title) + "</a>" : ""); }

  // rows of a chart for one metric: one for each selected harness, in the site order. A harness with no value is a row with `na`: no chart draws it (splitRows), and absentNote names it under the chart.
  function metricRows(I, st, mt) {
    return st.hs.map(function (h) {
      var c = gridCell(I, st, mt, h);
      if (c.na) return { h: h, na: true, none: naLabel(c), tip: c.na, cant: c.cant, why: c.why, other: c.other, noratio: c.noratio };
      if (c.value == null) return { h: h, none: "different work", tip: c.tip, href: c.href };
      return { h: h, v: c.value, lo: c.lo, hi: c.hi, tip: c.tip, href: c.href, prov: c.prov, nc: !!c.label };
    });
  }
  function splitRows(rows) {
    var have = [], absent = [];
    rows.forEach(function (r) { (r.na ? absent : have).push(r); });
    return { have: have, absent: absent };
  }
  // the harness a table or a chart has no row for: its cells (all without a value) say why
  function absentRow(h, cells) {
    var c = cells.filter(function (x) { return x.cant; })[0] || cells[0] || {};
    return { h: h, na: true, tip: c.na, cant: c.cant, why: c.why, other: c.other, noratio: c.noratio };
  }
  var NO_VALUE = "No selected harness has a value here.";
  // the lines under a chart, a tile or a table for the harnesses it has no row for. The runner's manifest says some cannot run the test: "Can't run: A (reason)". The others were not measured there: one muted line, "Not in this test: A, B".
  // A harness is in one line, never in both. o.quiet leaves the second line out (the card already says that no harness has a value), o.plain draws no link and no focus stop (a tile is one link).
  function absentNote(I, route, absent, o) {
    o = o || {};
    var cant = {}, why = [], miss = [], norat = [], others = [], out = "";
    var name = function (r) {
      var n = esc(shortName(r.h));
      if (r.other && route && !o.plain) return '<a href="' + esc(withParam(route, "api", r.other)) + '" data-tip="' + esc(r.tip) + '">' + n + "</a>";
      return r.tip ? "<span" + (o.plain ? "" : ' tabindex="0"') + ' data-tip="' + esc(r.tip) + '">' + n + "</span>" : n;
    };
    absent.forEach(function (r) {
      if (r.other) others.push(r);
      else if (r.cant) { var w = noteOf(r.why); if (!cant[w]) { cant[w] = []; why.push(w); } cant[w].push(r); }
      else if (r.noratio) norat.push(r);
      else miss.push(r);
    });
    if (why.length) out += '<p class="notrun cant">' + why.map(function (w) { return "Can't run: " + cant[w].map(name).join(", ") + " (" + esc(w) + ")."; }).join(" ") + "</p>";
    if (others.length) out += '<p class="notrun notin other">Measured with another API: ' + others.map(function (r) { return name(r) + " (" + esc(apiShort(r.other)) + ")"; }).join(", ") + ".</p>";
    if (miss.length && !o.quiet) out += '<p class="notrun notin">Not in this test: ' + miss.map(name).join(", ") + ".</p>";
    if (norat.length && !o.quiet && o.base) out += '<p class="notrun notin">No ratio to ' + esc(shortName(o.base)) + " for: " + norat.map(name).join(", ") + ".</p>";
    return out;
  }
  // where the baseline's line is drawn: 1 for a ratio, else the baseline's own median
  function baseAt(I, st, mt) {
    if (st.mode === "ratio") return 1;
    var cell = metricCell(I, mt.key, st.api), s = cell && cell.stats[st.base.id];
    return s ? s.median : null;
  }
  function wrapName(name, maxChars) {
    if (name.length <= maxChars || name.indexOf(" ") < 0) return [name];
    var mid = name.length / 2, best = -1;
    for (var i = 0; i < name.length; i++) if (name.charAt(i) === " " && (best < 0 || Math.abs(i - mid) < Math.abs(best - mid))) best = i;
    return [name.slice(0, best), name.slice(best + 1)];
  }
  // the one chart for a ratio or a value with its interval: a dot for each harness on a shared axis, lower cost to the left, the baseline as a dashed line
  // rows: {h, name, nameHref, v, lo, hi, tip, href, none, nc}; o: {width, ratio, unit, base, baseName, compact, label}
  function dotPlot(rows, o) {
    var compact = !!o.compact, W = Math.max(compact ? 220 : 280, Math.floor(o.width)), RH = compact ? 18 : 30, T = compact ? 6 : 12, B = compact ? 18 : 36, R = compact ? 10 : 20, cw = compact ? 7.1 : 7.4;
    var names = rows.map(function (r) { return r.name != null ? r.name : shortName(r.h); });
    var maxChars = Math.floor(Math.min(W * (compact ? 0.44 : 0.34), compact ? 150 : 190) / cw), L = Math.round(14 + Math.max.apply(null, names.map(function (n) { return Math.min(n.length, maxChars); }).concat([4])) * cw);
    // "can't run", "n/a" and the name of another API sit in a fixed column just right of the names, so that they never lie over the plot or the baseline
    var noneW = 0;
    rows.forEach(function (r) { if (r.none) noneW = Math.max(noneW, Math.ceil(String(r.none).length * (compact ? 6.2 : 6.8)) + 14); });
    var vals = [];
    rows.forEach(function (r) { [r.v, r.lo, r.hi].forEach(function (x) { if (ok(x) && (!o.ratio || x > 0)) vals.push(x); }); });
    if (ok(o.base)) vals.push(o.base);
    if (!vals.length) return '<p class="empty">' + (rows.length ? "No value to plot." : "Pick at least one harness.") + "</p>";
    var lg = !!o.ratio, lo, hi;
    if (lg) { lo = Math.min.apply(null, vals.concat([1])); hi = Math.max.apply(null, vals.concat([1])); var pad = Math.max(1.15, Math.pow(hi / lo, 0.06)); lo /= pad; hi *= pad; }
    else { lo = 0; hi = Math.max.apply(null, vals) * 1.06 || 1; }
    var au = lg ? { div: 1, u: "×" } : axisUnit(o.unit, hi), A = lg ? Math.log(lo) : lo, Z = lg ? Math.log(hi) : hi;
    var PL = L + noneW, X = function (v) { return PL + ((lg ? Math.log(v) : v) - A) / (Z - A) * (W - PL - R); };
    var ticks = (lg ? logTicks(lo, hi) : niceTicks(lo, hi, compact ? 3 : 5)).filter(function (t) { return t >= lo - 1e-9 && t <= hi + 1e-9; });
    if (compact && ticks.length > 4) ticks = ticks.filter(function (t, i) { return i % 2 === 0; });
    var lastX = -1e9;
    ticks = ticks.filter(function (t) { var x = X(t); if (x - lastX < 38) return false; lastX = x; return true; });   // a label never lies on its neighbour
    var H = T + rows.length * RH + B, s = svgOpen(W, H, o.label || "values by harness");
    ticks.forEach(function (t) { s += '<line class="gl" x1="' + X(t).toFixed(1) + '" x2="' + X(t).toFixed(1) + '" y1="' + (T - 4) + '" y2="' + (H - B) + '"/><text class="xl" x="' + X(t).toFixed(1) + '"' + (X(t) > W - 22 ? ' text-anchor="end"' : "") + ' y="' + (H - B + 14) + '">' + esc(lg ? fmtAxis(t) + "×" : fmtAxis(t / au.div)) + "</text>"; });
    if (!compact) s += '<text class="axl" x="' + (W - R) + '" y="' + (H - 4) + '">' + esc(lg ? "ratio to " + (o.baseName || "the baseline") + ", log scale" : au.u) + "</text>";
    if (ok(o.base) && o.base > 0) s += '<line class="one" x1="' + X(o.base).toFixed(1) + '" x2="' + X(o.base).toFixed(1) + '" y1="' + (T - 4) + '" y2="' + (H - B) + '"/>';
    rows.forEach(function (r, i) {
      var y = T + i * RH + RH / 2, lines = wrapName(names[i], maxChars), label = lines.map(function (l, k) { return '<tspan x="' + (L - 8) + '"' + (k ? ' dy="11"' : "") + ">" + esc(l) + "</tspan>"; }).join("");
      var text = '<text class="dl" x="' + (L - 8) + '" y="' + (y + 4 - (lines.length - 1) * 5.5).toFixed(1) + '">' + label + "</text>";
      s += '<g class="series h-' + esc(r.h.colour) + '">' + (r.nameHref ? '<a href="' + esc(r.nameHref) + '">' + text + "</a>" : text);
      if (r.none) s += '<text class="dn" x="' + (L + 6) + '" y="' + (y + 4) + '" data-tip="' + esc(r.tip || "") + '">' + esc(r.none) + "</text>";
      else {
        var mark = (ok(r.lo) && ok(r.hi) ? '<line class="ci" x1="' + X(r.lo).toFixed(1) + '" x2="' + X(r.hi).toFixed(1) + '" y1="' + y + '" y2="' + y + '"/><line class="ci" x1="' + X(r.lo).toFixed(1) + '" x2="' + X(r.lo).toFixed(1) + '" y1="' + (y - 4) + '" y2="' + (y + 4) + '"/><line class="ci" x1="' + X(r.hi).toFixed(1) + '" x2="' + X(r.hi).toFixed(1) + '" y1="' + (y - 4) + '" y2="' + (y + 4) + '"/>' : "") +
          '<circle' + (r.nc ? ' class="nc"' : "") + ' cx="' + X(r.v).toFixed(1) + '" cy="' + y + '" r="' + (compact ? 3.6 : 4.8) + '" data-tip="' + esc(r.tip || "") + '"/>';
        s += r.href ? '<a href="' + esc(r.href) + '" aria-label="' + esc(names[i]) + '">' + mark + "</a>" : mark;
      }
      s += "</g>";
    });
    return '<div class="svgwrap">' + s + "</svg></div>";
  }

  // the same cells as a table: harnesses down, metrics across, a bar under each value for its size in the column. A value links to its derivation.
  function sortHref(st, key) {
    var cur = st.sort && st.sort.key === key ? st.sort.dir : null;
    return withParam(st.route, "sort", cur === "asc" ? key + ":desc" : cur === "desc" ? "" : key + ":asc");
  }
  function sortOf(st, key) {
    var cur = st.sort && st.sort.key === key ? st.sort.dir : null;
    return { aria: cur === "asc" ? "ascending" : cur === "desc" ? "descending" : "none", arrow: cur === "asc" ? "↑" : cur === "desc" ? "↓" : "↕" };
  }
  // the tables of metrics: one table for each workload, a row for each harness that has a value in it, a column for each metric that has one. The main metrics (MAIN_MAX at most) are the table, the others are tables
  // in the closed "More metrics" under it, of the same layout. A harness with no value in a workload has no row: absentNote names it under the table.
  // o.vo: {metric key: {variant, base}}, so that a column is headed by its short word and the group row names the variant ("200 KB file"); o.cell(mt, h): the cell, memoised by the caller; o.group: the Download CSV that holds the table
  function metricTable(I, st, keys, id, o) {
    o = o || {};
    var cols = keys.map(function (k) { return I.metric[k]; }), vo = o.vo || {}, cellOf = o.cell || function (mt, h) { return gridCell(I, st, mt, h); };
    var rows = st.hs.map(function (h) { return { h: h, cells: cols.map(function (mt) { return cellOf(mt, h); }) }; }).filter(function (r) { return r.cells.some(function (c) { return !c.na; }); });
    if (!rows.length) return "";
    // the reader's sort, from the URL: a column of numbers (a cell with no number is last in both directions) or the harness name; a tie keeps the site order
    var order = rows.map(function (r, i) { return i; }), sk = st.sort && st.sort.key, ci = keys.indexOf(sk), dir = st.sort && st.sort.dir === "desc" ? -1 : 1;
    if (sk === "harness") order.sort(function (a, b) { return dir * rows[a].h.name.localeCompare(rows[b].h.name) || a - b; });
    else if (ci >= 0) order.sort(function (a, b) {
      var x = rows[a].cells[ci].value, y = rows[b].cells[ci].value, nx = !ok(x), ny = !ok(y);
      if (nx || ny) return nx === ny ? a - b : nx ? 1 : -1;
      return dir * (x - y) || a - b;
    });
    var top = cols.map(function (mt, j) { var vs = rows.map(function (r) { return r.cells[j].nobar ? null : r.cells[j].value; }).filter(ok); return vs.length ? Math.max.apply(null, vs) : null; });
    var hs = sortOf(st, "harness"), wordOf = function (mt) { return vo[mt.key] ? vo[mt.key].base : mt.word; };
    var head = '<th scope="col" class="hcol" aria-sort="' + hs.aria + '" data-csv-label="Harness"><button type="button" class="sortb lft" data-href="' + esc(sortHref(st, "harness")) + '">Harness <i class="arrow">' + hs.arrow + "</i></button></th>" + cols.map(function (mt) {
      var csvLabel = mt.title + ": " + mt.word + " (" + unitOf(mt.unit) + (st.mode === "ratio" ? ", ratio to " + shortName(st.base) : "") + ")", so = sortOf(st, mt.key);
      return '<th scope="col" class="num mcol" aria-sort="' + so.aria + '" data-csv-label="' + esc(csvLabel) + '" title="' + esc(mt.title + ": " + mt.word) + '"><div class="mh"><button type="button" class="sortb" data-href="' + esc(sortHref(st, mt.key)) + '"><span class="mw">' + esc(cap(wordOf(mt))) + ' <i class="arrow">' + so.arrow + "</i></span></button>" +
        '<a class="info" href="' + esc(link("metric", [mt.key], metricParams(I, st))) + '" aria-label="About ' + esc(mt.title + ": " + mt.word) + '" data-tip="' + esc(mt.about + "\nClick for the formula and every harness.") + '">i</a></div></th>';
    }).join("");
    var runs = [];
    cols.forEach(function (mt) { var v = vo[mt.key] ? vo[mt.key].variant : "", last = runs[runs.length - 1]; if (last && last.v === v) last.n++; else runs.push({ v: v, n: 1 }); });
    var groupRow = runs.some(function (r) { return r.v; }) ? '<tr class="grouprow" data-csv-skip><th class="hcol" scope="col"></th>' + runs.map(function (r) { return '<th scope="colgroup" colspan="' + r.n + '" class="grp">' + esc(cap(r.v)) + "</th>"; }).join("") + "</tr>" : "";
    var body = order.map(function (i) {
      var r = rows[i], h = r.h;
      return '<tr class="h-' + esc(h.colour) + (h === st.base && st.mode === "ratio" ? " isbase" : "") + '"><th scope="row" class="hn1" data-csv-value="' + esc(h.name) + '">' + hname(h) + '<small class="ver">' + esc(h.version || "") +
        (h === st.base ? (h.version ? " · " : "") + "baseline" : "") + "</small></th>" +
        r.cells.map(function (c, j) {
          if (c.na) return '<td class="num na" data-csv-value="' + (c.other ? naLabel(c) : "n/a") + '">' + (c.other && st.route ? '<a href="' + esc(withParam(st.route, "api", c.other)) + '" data-tip="' + esc(c.na) + '">' + naLabel(c) + "</a>" : '<span tabindex="0" data-tip="' + esc(c.na) + '">–</span>') + "</td>";
          var w = top[j] && !c.nobar ? Math.max(0.01, c.value / top[j]) : 0;
          return '<td class="num' + (c.label ? " nc" : "") + '" data-csv-value="' + esc(String(c.csv)) + '"><a href="' + esc(c.href) + '" data-tip="' + esc(c.tip) + '">' +
            (c.nobar ? "" : '<i class="cbar" style="width:calc((100% - 24px) * ' + w.toFixed(4) + ')"></i>') + (c.label ? '<small class="ncl">' + esc(c.label) + "</small>" : "") + '<span class="cv"><b>' + esc(c.n) + "</b>" + (c.u ? "<small>" + esc(c.u) + "</small>" : "") + "</span></a></td>";
        }).join("") + "</tr>";
    }).join("");
    return '<div class="tablewrap"><table class="data grid" id="t-' + esc(id) + '" data-csv-group="' + esc(o.group || id) + '" style="--n:' + cols.length + '"><thead>' + groupRow + "<tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table></div>";
  }
  function csvBtn(id) { return '<button type="button" class="btn" data-csv="' + esc(id) + '">Download CSV</button>'; }

  // which metrics are the table and which are behind "More metrics": by word, in this order, as many as fit in MAIN_MAX columns. A word that has variants ("200 KB file", "short answer") brings every variant.
  var MAIN_MAX = 6;
  var MAIN_WORDS = ["CPU time per 1,000 tokens", "CPU time until ready", "CPU time", "time until ready", "time", "time per turn", "CPU time per turn", "peak memory", "peak memory, all processes", "memory when ready", "growth of the session file"];
  MAIN_WORDS = MAIN_WORDS.concat(["warm turn net of the floor", "warm turn", "cold start", "statements per turn", "commits per turn"]);   // the durable family's own
  // a trailing ", variant" is a variant when at least three metrics of the workload end in it and the metric names before it ("CPU time", "time") also come with another variant: the file size of a write, the length of an answer.
  // The group row of the table says it, a column says the rest. ("time, extensions ready" is one metric, not a variant of "time".)
  function variantsOf(mts) {
    var n = {}, tails = {}, out = {}, tail = function (w) { var i = w.lastIndexOf(", "); return i > 0 ? [w.slice(0, i), w.slice(i + 2)] : [w, ""]; };
    mts.forEach(function (m) { var p = tail(m.word); if (p[1]) n[p[1]] = (n[p[1]] || 0) + 1; (tails[p[0]] = tails[p[0]] || {})[p[1]] = 1; });
    var shared = function (t) { return mts.filter(function (m) { var p = tail(m.word); return p[1] === t && Object.keys(tails[p[0]]).length > 1; }).length >= 2; };
    mts.forEach(function (m) { var p = tail(m.word); out[m.key] = p[1] && n[p[1]] >= 3 && shared(p[1]) ? { base: p[0], variant: p[1] } : { base: m.word, variant: "" }; });
    return out;
  }
  function pickMain(cols, vo) {
    var picked = [], n = 0;
    MAIN_WORDS.forEach(function (w) {
      var g = cols.filter(function (m) { return vo[m.key].base === w; });
      if (g.length && n + g.length <= MAIN_MAX) { picked = picked.concat(g); n += g.length; }
    });
    if (!n) picked = cols.slice(0, MAIN_MAX);
    else cols.forEach(function (m) { if (picked.length < 3 && picked.indexOf(m) < 0) picked.push(m); });
    return cols.filter(function (m) { return picked.indexOf(m) >= 0; });
  }
  // the title of each workload of a list of metrics. Two workloads that share a title (a session and its varied twin) tell themselves apart by what their ids add: "Resume a long session (varied)".
  function workloadTitles(I, keys) {
    var ids = [], titles = {}, out = {};
    keys.forEach(function (k) { var mt = I.metric[k]; if (ids.indexOf(mt.workload) < 0) { ids.push(mt.workload); titles[mt.workload] = mt.title; } });
    ids.forEach(function (w) {
      var same = ids.filter(function (x) { return titles[x] === titles[w]; }), base = same.slice().sort(function (a, b) { return a.length - b.length; })[0];
      out[w] = same.length > 1 && w !== base ? titles[w] + " (" + (w.indexOf(base) === 0 ? w.slice(base.length).replace(/^-/, "") : w).replace(/-/g, " ") + ")" : titles[w];
    });
    return out;
  }
  // a titled block for each table or group of tables: a heading, or a closed disclosure for all but the first when there are more than four. The harnesses that none of the blocks has a row for are named once, above them.
  // items: [{title, html, absent: [absentRow]}]
  function tableBlocks(I, st, items) {
    var many = items.length > 4, common = [];
    if (items.length > 1) common = items[0].absent.filter(function (r) { return items.every(function (it) { return it.absent.some(function (x) { return x.h === r.h; }); }); });
    var note = function (list) { return absentNote(I, st.route, list, { base: st.base }); };
    return note(common) + items.map(function (it, i) {
      var inner = it.html + note(it.absent.filter(function (r) { return !common.some(function (c) { return c.h === r.h; }); }));
      return many ? '<details class="wl"' + (i === 0 ? " open" : "") + "><summary>" + esc(it.title) + (it.chip || "") + "</summary>" + inner + "</details>" : '<section class="wl"><h3 class="wlh">' + esc(it.title) + (it.chip || "") + "</h3>" + inner + "</section>";
    }).join("");
  }
  // the tables of the metrics `keys`: {html, count: the metrics that have a column}
  function workloadTables(I, st, keys, id, o) {
    o = o || {};
    if (!st.hs.length) return { html: '<p class="empty">Pick at least one harness.</p>', count: 0, prov: [] };
    var memo = {}, cellOf = function (mt, h) { var k = mt.key + "|" + h.id; return memo[k] || (memo[k] = gridCell(I, st, mt, h)); };
    var titleOf = workloadTitles(I, keys), prov = {}, order = [], by = {}, items = [], count = 0, keyOf = function (list) { return list.map(function (mt) { return mt.key; }); };
    keys.forEach(function (k) { var mt = I.metric[k]; if (!by[mt.workload]) { by[mt.workload] = []; order.push(mt.workload); } by[mt.workload].push(mt); });
    order.forEach(function (w, wi) {
      var mts = by[w], vo = variantsOf(mts), ranks = { "": -1 }, n = 0, rank = function (mt) { return ranks[vo[mt.key].variant]; };
      mts.forEach(function (mt) { var v = vo[mt.key].variant; if (v && !(v in ranks)) ranks[v] = n++; });
      var live = mts.filter(function (mt) { return st.hs.some(function (h) { return !cellOf(mt, h).na; }); });
      if (!live.length) return;
      live = live.map(function (mt, i) { return { mt: mt, i: i }; }).sort(function (a, b) { return rank(a.mt) - rank(b.mt) || a.i - b.i; }).map(function (x) { return x.mt; });   // the columns of one variant side by side
      var main = pickMain(live, vo), more = live.filter(function (mt) { return main.indexOf(mt) < 0; }), topt = { vo: vo, cell: cellOf, group: o.group || id };
      var html = metricTable(I, st, keyOf(main), id + "-" + wi, topt);
      if (more.length) {
        var lenses = [], blocks = "", j = 0, lrank = function (l) { var i = LENS_ORDER.indexOf(l); return i < 0 ? LENS_ORDER.length : i; };
        more.forEach(function (mt) { if (lenses.indexOf(mt.lens) < 0) lenses.push(mt.lens); });
        lenses.sort(function (a, b) { return lrank(a) - lrank(b); });
        lenses.forEach(function (l) {
          var mine = more.filter(function (mt) { return mt.lens === l; });
          for (var s = 0; s < mine.length; s += MAIN_MAX) blocks += '<h4 class="lensh">' + esc(lensName(l)) + "</h4>" + metricTable(I, st, keyOf(mine.slice(s, s + MAIN_MAX)), id + "-" + wi + "-m" + (j++), topt);
        });
        html += '<details class="more"><summary>More metrics (' + more.length + ")</summary>" + blocks + "</details>";
      }
      var absent = st.hs.filter(function (h) { return !live.some(function (mt) { return !cellOf(mt, h).na; }); }).map(function (h) { return absentRow(h, mts.map(function (mt) { return cellOf(mt, h); })); });
      items.push({ title: titleOf[w], chip: envChip(metricCell(I, mts[0].key, st.api)), html: html, absent: absent });
      count += live.length;
      live.forEach(function (mt) { st.hs.forEach(function (h) { var c = cellOf(mt, h); if (!c.na) (c.prov || []).forEach(function (r) { prov[r.id] = r; }); }); });   // one badge for the card, not one for each value
    });
    if (!items.length) {
      var all = st.hs.map(function (h) { return absentRow(h, keys.map(function (k) { return cellOf(I.metric[k], h); })); });
      return { html: '<p class="empty">' + NO_VALUE + "</p>" + absentNote(I, st.route, all, { quiet: true }), count: 0, prov: [] };
    }
    return { html: tableBlocks(I, st, items), count: count, prov: Object.keys(prov).map(function (k) { return prov[k]; }) };
  }

  // the extension sweep: one line for each harness over the number of extensions loaded
  var SWEEPS = [["Print mode", "overhead-print", "cpu_ms"], ["RPC mode", "overhead-rpc", "ready_cpu_ms"]];
  var EXT_N = [0, 5, 10, 50, 100];
  function sweepKeys(I, base, metric) { return EXT_N.map(function (n) { return [n, (n ? base + "-ext" + n : base) + "." + metric]; }).filter(function (x) { return I.metric[x[1]]; }); }
  function sweepSeries(I, st, pts) {
    var out = [];
    st.hs.forEach(function (h) {
      var line = [], other = {};
      pts.forEach(function (p, i) { var c = gridCell(I, st, I.metric[p[1]], h); if (!c.na && c.label) other[i] = 1; else if (!c.na && ok(c.value)) line.push({ i: i, v: c.value, tip: c.tip, href: c.href }); });
      if (line.length) out.push({ h: h, line: line, other: other });
    });
    return out;
  }
  function sweepChart(I, st, pts, o) {
    var series = sweepSeries(I, st, pts), all = [], ratio = st.mode === "ratio";
    series.forEach(function (s) { s.line.forEach(function (p) { all.push(p.v); }); });
    if (!all.length) return "";
    var lo, hi;
    if (ratio) { lo = Math.min.apply(null, all.concat([1])) / 1.15; hi = Math.max.apply(null, all.concat([1])) * 1.15; } else { lo = 0; hi = Math.max.apply(null, all) * 1.08; }
    var f = plotFrame({ width: o.width, lo: lo, hi: hi, log: ratio, unit: ratio ? "×" : o.unit, xlabel: "extensions loaded →", label: o.label, names: series.map(function (s) { return shortName(s.h); }) });
    var W = f.W, L = f.L, R = f.R, H = f.H, n = pts.length, X = function (i) { return L + (n === 1 ? (W - L - R) / 2 : i * (W - L - R) / (n - 1)); }, s = f.svg;
    pts.forEach(function (p, i) { s += '<text class="xl" x="' + X(i).toFixed(1) + '" y="' + (H - 18) + '">' + p[0] + "</text>"; });
    if (ratio) s += '<line class="one" x1="' + L + '" x2="' + (W - R) + '" y1="' + f.Y(1).toFixed(1) + '" y2="' + f.Y(1).toFixed(1) + '"/>';
    series.forEach(function (sr) {
      s += '<g class="series h-' + esc(sr.h.colour) + '">' + (sr.line.length > 1 ? '<polyline points="' + sr.line.map(function (p) { return X(p.i).toFixed(1) + "," + f.Y(p.v).toFixed(1); }).join(" ") + '"/>' : "") +
        sr.line.map(function (p) { return '<a href="' + esc(p.href) + '" aria-label="' + esc(shortName(sr.h) + ", " + pts[p.i][0] + " extensions") + '"><circle cx="' + X(p.i).toFixed(1) + '" cy="' + f.Y(p.v).toFixed(1) + '" r="4" data-tip="' + esc(p.tip) + '"/></a>'; }).join("") + "</g>";
    });
    s += endLabels(series.map(function (sr) { var last = sr.line[sr.line.length - 1]; return { name: shortName(sr.h), colour: sr.h.colour, x: X(last.i), y: f.Y(last.v) }; }), f);
    return '<div class="svgwrap">' + s + "</svg></div>";
  }
  function sweepCards(ctx, I, st) {
    return SWEEPS.map(function (sw, j) {
      var pts = sweepKeys(I, sw[1], sw[2]);
      if (pts.length < 3) return "";
      var mt = I.metric[pts[0][1]], cell = metricCell(I, mt.key, st.api), ratio = st.mode === "ratio";
      var series = sweepSeries(I, st, pts);
      var absent = st.hs.filter(function (h) { return !series.some(function (s) { return s.h === h; }); }).map(function (h) { return absentRow(h, pts.map(function (p) { return gridCell(I, st, I.metric[p[1]], h); })); });
      var cols = pts.map(function (p, i) { return i; }).filter(function (i) { return series.some(function (s) { return s.line.some(function (p) { return p.i === i; }) || s.other[i]; }); });   // a number of extensions that no harness has is no column
      var trs = series.map(function (s) { var by = {}; s.line.forEach(function (p) { by[p.i] = p; }); return [td(esc(s.h.name))].concat(cols.map(function (i) { return by[i] ? td(ratio ? times(by[i].v) : esc(val(by[i].v, cell.unit)), by[i].v) : td(s.other[i] ? "different work: not compared" : "–", null); })); });
      return card(ctx, { id: "sweep-" + j, title: esc(sw[0] + ": " + cap(mt.word) + " by number of extensions"), sub: ratio ? "Ratio to " + esc(shortName(st.base)) + ". The dashed line is 1×." : "Median. Lower is to the bottom.",
        chart: series.length ? sweepChart(I, st, pts, { width: chartWidth(ctx, 1), unit: cell ? cell.unit : "", label: sw[0] + ": " + mt.word + " by number of extensions" }) : '<p class="empty">' + NO_VALUE + "</p>",
        table: table(ctx, "sweep-" + j, ["Harness"].concat(cols.map(function (i) { return { h: pts[i][0] + " ext", num: true }; })), trs),
        foot: absentNote(I, st.route, absent, { base: st.base, quiet: !series.length }) });
    }).join("");
  }

  // ---- the Durable section: the environment of a cell, its line charts over the history length, the crash grid, and the Method block
  var ENV_TIP = { native: "Native SQLite on this host (Node and Go). Not a Durable Object.", miniflare: "Miniflare: local workerd with Durable Object storage.", cloudflare: "Real Cloudflare Durable Objects." };
  // a small label with the environment a cell ran in; every environment is its own cell, never merged with another
  function envChip(cell) { return cell && cell.env ? '<span class="envchip" tabindex="0" data-tip="' + esc(ENV_TIP[cell.env] || "Environment: " + cell.env) + '">' + esc(cell.env) + "</span>" : ""; }
  // the environments the Durable section has cells for, when more than one ("native" first); the section's selector
  function durableEnvs(I) {
    var D = I.D.durable, out = D ? ["native"].concat(D.envs.filter(function (e) { return e !== "native"; })) : [];
    return out.length > 1 ? out : [];
  }
  function durableRuns(I) { var ids = {}; I.D.cells.forEach(function (c) { if (c.family === "durable") ids[c.run] = 1; }); return Object.keys(ids); }
  function durableProv(I) { return provRuns(I, durableRuns(I)); }
  function durableNote(I) {
    var D = I.D.durable;
    return '<p class="attrib">' + esc(D.attribution) + "</p>" + '<p class="muted">Every durable number on this page was measured on ' + esc(D.envs.join(" and ")) + ", not in a Durable Object unless the cell says so. Statements are counted at the SQLite facade; the pragma statements are listed apart and are part of the total. " +
      docLink(I, "WHAT-WE-MEASURE", "What each durable metric means") + ".</p>";
  }
  // how to fill the section when no durable run is in the results
  function durableNone(I) {
    var P = (I.D.plan || {}).durable || {};
    return '<div class="card"><h3 class="sech2">No durable run is in the results yet</h3><p>Buffon\'s own durable workloads have no samples in the loaded runs. Produce one and load its directory:</p><pre class="cmd">' + esc(P.command || "") +
      '</pre><p class="muted">The whole native plan is the campaign file <code>' + esc(P.campaign || "") + "</code>: <code>" + esc(P.campaign_command || "") + "</code>. " + docLink(I, "DURABLE", "The plan") + ".</p></div>";
  }
  // one line for each harness and series over the x axis of a chart (the history length), logarithmic. rows: {h, sr, line: [{x, v, tip, href}], other}
  function durableLines(I, st, ch) {
    var out = [];
    st.hs.forEach(function (h) {
      ch.series.forEach(function (sr) {
        var line = [], other = {};
        sr.rungs.forEach(function (r) {
          var mt = I.metric[r.key];
          if (!mt) return;
          var c = gridCell(I, st, mt, h);
          if (!c.na && c.label) other[r.at] = 1; else if (!c.na && ok(c.value)) line.push({ x: r.at, v: c.value, tip: c.tip, href: c.href });
        });
        if (line.length) out.push({ h: h, sr: sr, line: line, other: other });
      });
    });
    return out;
  }
  function lineName(rows, r) { return shortName(r.h) + (rows.filter(function (q) { return q.h === r.h; }).length > 1 ? ", " + r.sr.name : ""); }
  function durableChart(I, st, ch, rows, o) {
    var ratio = st.mode === "ratio", all = [], xs = [];
    rows.forEach(function (r) { r.line.forEach(function (p) { all.push(p.v); if (xs.indexOf(p.x) < 0) xs.push(p.x); }); });
    xs.sort(function (a, b) { return a - b; });
    var lo, hi;
    if (ratio) { lo = Math.min.apply(null, all.concat([1])) / 1.15; hi = Math.max.apply(null, all.concat([1])) * 1.15; } else { lo = 0; hi = Math.max.apply(null, all) * 1.08 || 1; }
    var names = rows.map(function (r) { return lineName(rows, r); });
    var f = plotFrame({ width: o.width, lo: lo, hi: hi, log: ratio, unit: ratio ? "×" : o.unit, xlabel: ch.xlabel, label: o.label, names: names });
    var W = f.W, L = f.L, R = f.R, H = f.H, a = Math.log(xs[0]), b = Math.log(xs[xs.length - 1]);
    var X = function (x) { return L + (b === a ? (W - L - R) / 2 : (Math.log(x) - a) / (b - a) * (W - L - R - 6) + 3); }, s = f.svg;
    xs.forEach(function (x) { s += '<line class="gl" x1="' + X(x).toFixed(1) + '" x2="' + X(x).toFixed(1) + '" y1="' + f.T + '" y2="' + (H - f.B) + '"/><text class="xl" x="' + X(x).toFixed(1) + '" y="' + (H - 18) + '">' + group(x) + "</text>"; });
    if (ratio) s += '<line class="one" x1="' + L + '" x2="' + (W - R) + '" y1="' + f.Y(1).toFixed(1) + '" y2="' + f.Y(1).toFixed(1) + '"/>';
    rows.forEach(function (r, i) {
      s += '<g class="series h-' + esc(r.h.colour) + (r.sr.id === "compat" ? " alt" : "") + '">' + (r.line.length > 1 ? '<polyline points="' + r.line.map(function (p) { return X(p.x).toFixed(1) + "," + f.Y(p.v).toFixed(1); }).join(" ") + '"/>' : "") +
        r.line.map(function (p) { return '<a href="' + esc(p.href) + '" aria-label="' + esc(names[i] + ", " + group(p.x)) + '"><circle cx="' + X(p.x).toFixed(1) + '" cy="' + f.Y(p.v).toFixed(1) + '" r="4" data-tip="' + esc(p.tip) + '"/></a>'; }).join("") + "</g>";
    });
    s += endLabels(rows.map(function (r, i) { var last = r.line[r.line.length - 1]; return { name: names[i], colour: r.h.colour, x: X(last.x), y: f.Y(last.v) }; }), f);
    return '<div class="svgwrap">' + s + "</svg></div>";
  }
  function durableLineCards(ctx, I, st, sec) {
    var D = I.D.durable, ratio = st.mode === "ratio", cards = "";
    (D ? D.lines : []).forEach(function (ch) {
      var rows = durableLines(I, st, ch);
      if (!rows.length) return;
      var mt = I.metric[ch.series[0].rungs.filter(function (r) { return I.metric[r.key]; }).map(function (r) { return r.key; })[0]], cell = metricCell(I, mt.key, secApi(I, st, sec)), xs = [];
      rows.forEach(function (r) { r.line.forEach(function (p) { if (xs.indexOf(p.x) < 0) xs.push(p.x); }); });
      xs.sort(function (a, b) { return a - b; });
      var absent = st.hs.filter(function (h) { return !rows.some(function (r) { return r.h === h; }); }).map(function (h) {
        return absentRow(h, ch.series[0].rungs.filter(function (r) { return I.metric[r.key]; }).map(function (r) { return gridCell(I, st, I.metric[r.key], h); }));
      });
      var names = rows.map(function (r) { return lineName(rows, r); });
      var trs = rows.map(function (r, i) {
        var by = {}; r.line.forEach(function (p) { by[p.x] = p; });
        return [td(esc(names[i]))].concat(xs.map(function (x) { return by[x] ? td(ratio ? times(by[x].v) : esc(val(by[x].v, cell ? cell.unit : mt.unit)), by[x].v) : td(r.other[x] ? "different work: not compared" : "–", null); }));
      });
      var slope = "";
      if (ch.slope_keys) {
        var sk = ch.slope_keys.filter(function (k) { return I.metric[k]; }).pop(), sm = sk && I.metric[sk], sc = sm && metricCell(I, sk, secApi(I, st, sec));
        var bits = sc ? st.hs.filter(function (h) { return sc.stats[h.id]; }).map(function (h) { return shortName(h) + " " + val(sc.stats[h.id].median, sc.unit); }) : [];
        if (bits.length) slope = '<p class="muted">Memory per live conversation, the slope of the line: ' + bits.map(esc).join(", ") + ".</p>";
      }
      cards += card(ctx, { id: "durable-" + ch.id, title: esc(ch.title), sub: esc((ratio ? "Ratio to " + shortName(st.base) + ", log scale. The dashed line is 1×. " : "Median. Lower is to the bottom. ") + "The x axis is logarithmic." + (ch.series.length > 1 ? " Dashed lines are the compat lane." : "")),
        tools: envChip(cell) + provBadge(cell ? cellProv(I, cell) : []),
        chart: durableChart(I, st, ch, rows, { width: chartWidth(ctx, 1), unit: cell ? cell.unit : mt.unit, label: ch.title }) + '<p class="muted">' + esc(ch.note) + "</p>" + slope,
        table: table(ctx, "durable-" + ch.id, ["Harness"].concat(xs.map(function (x) { return { h: group(x), num: true }; })), trs),
        foot: absentNote(I, st.route, absent, { base: st.base }) });
    });
    return cards || '<p class="empty">' + NO_VALUE + "</p>";
  }
  // the crash and resume grid: a row for each order (writer then resumer), a mark for each kill point, and the pass rate of the order with its Wilson interval
  function orderName(I, o) { var n = function (id) { return I.harn[id] ? shortName(I.harn[id]) : id; }; return n(o.writer) + " then " + n(o.resumer); }
  function crashCard(ctx, I, st, g) {
    var orders = g.orders.filter(function (o) { return st.hs.some(function (h) { return h.id === o.writer; }) && st.hs.some(function (h) { return h.id === o.resumer; }); });
    var absent = st.hs.filter(function (h) { return !g.orders.some(function (o) { return o.resumer === h.id; }); }).map(function (h) { var why = g.na[h.id] || ""; return { h: h, na: true, cant: isCant(why), why: why, tip: shortName(h) + ": " + (noteOf(why) || "it was not run on this workload") }; });
    if (!orders.length) return "";
    var pctw = function (x) { return Math.round(x * 1000) / 10 + "%"; };
    var rows = orders.map(function (o) {
      var h = I.harn[o.resumer] || I.ref, ci = o.ci ? pctw(o.ci[0]) + " to " + pctw(o.ci[1]) : "n/a";
      if (o.impossible) return { o: o, h: h, ci: "", html: '<div class="crow h-' + esc(h.colour) + '"><span class="cname">' + esc(orderName(I, o)) + '</span><span class="ccells nopos" data-tip="' + esc(o.impossible) + '">not possible: ' + esc(o.impossible) + '</span><span class="cscore"></span></div>' };
      var cells = g.ks.filter(function (k) { return o.points[String(k)]; }).map(function (k) {
        var p = o.points[String(k)];
        return '<i class="cc ' + (p.ok ? "ok" : "bad") + '" data-tip="' + esc(orderName(I, o) + ", killed after commit " + k + (g.commits_total[String(k)] != null ? " of " + g.commits_total[String(k)] : "") + "\n" + (p.ok ? "Passed." : "Did not pass: " + p.reasons.join("; "))) + '"></i>';
      }).join("");
      return { o: o, h: h, ci: ci, html: '<div class="crow h-' + esc(h.colour) + '"><span class="cname">' + esc(orderName(I, o)) + (o.control ? " <small>(the oracle)</small>" : "") + '</span><span class="ccells" role="img" aria-label="' + esc(orderName(I, o) + ": " + o.passed + " of " + o.of + " kill points passed") + '">' + cells +
        '</span><span class="cscore"><b>' + o.passed + " of " + o.of + "</b><small>95% interval " + esc(ci) + "</small></span></div>" };
    });
    var axis = '<div class="crow caxis"><span class="cname"></span><span class="ccells"><small>commit k at which the process is killed: ' + esc(String(g.ks[0])) + " to " + esc(String(g.ks[g.ks.length - 1])) + '</small></span><span class="cscore"></span></div>';
    var trs = rows.map(function (r) {
      if (r.o.impossible) return [td(esc(orderName(I, r.o))), td("–", null), td("–", null), td("–", null), td("not possible: " + esc(r.o.impossible)), td("")];
      var bad = Object.keys(r.o.points).filter(function (k) { return !r.o.points[k].ok; });
      return [td(esc(orderName(I, r.o))), td(String(r.o.of), r.o.of), td(String(r.o.passed), r.o.passed), td(r.o.of ? pctw(r.o.passed / r.o.of) : "n/a", r.o.of ? r.o.passed / r.o.of : null), td(esc(r.ci)), td(bad.length ? esc("k = " + bad.slice(0, 12).join(", ") + (bad.length > 12 ? " and " + (bad.length - 12) + " more" : "")) : "none")];
    });
    return card(ctx, { id: "crash-" + g.id, title: esc(g.title), sub: "Each mark is one kill after a commit, a reopen, a resume and the same request id again. The reference order is the oracle: another order passes a point when its outcome equals the oracle's at the same point.",
      tools: envChip({ env: "native" }) + provBadge(provRuns(I, [g.run])),
      chart: '<div class="crashgrid">' + rows.map(function (r) { return r.html; }).join("") + axis + '</div><p class="muted"><i class="cc ok"></i> passed <i class="cc bad"></i> did not pass</p>',
      table: table(ctx, "crash-" + g.id, ["Order", { h: "Points", num: true }, { h: "Passed", num: true }, { h: "Share", num: true }, "95% interval (Wilson)", "Did not pass at"], trs),
      foot: absentNote(I, st.route, absent, { quiet: true }) });
  }
  function crashBlock(ctx, I, st, sec) {
    var D = I.D.durable, out = D ? D.crash.map(function (g) { return crashCard(ctx, I, st, g); }).join("") : "";
    return out ? '<h2 class="sech">Crash and resume</h2>' + out : "";
  }
  // the Method page's Durable block: the settings each arm ran with, the gate's records, the fixtures' digests and the floors
  function durableMethod(ctx, I) {
    var D = I.D.durable;
    if (!D) return "";
    var M = D.method, out = '<h2 class="sech">Durable</h2><p class="muted">' + esc(D.attribution) + "</p>";
    var set = M.settings.map(function (a) {
      var h = I.harn[a.arm], versions = Object.keys(a.versions).map(function (k) { return k + " " + a.versions[k]; }).join(", "), settings = Object.keys(a.settings).map(function (k) { return k + " = " + (a.settings[k] === null ? "the runtime's own default" : a.settings[k]); }).join("<br>");
      return [td(h ? hname(h) : esc(a.arm), a.arm), td(esc(versions), versions), td(settings || "none", settings), td(esc(a.envs.join(", ")), a.envs.join(", "))];
    });
    if (set.length) out += card(ctx, { id: "durable-settings", title: "Runtime settings per arm", sub: "What each arm declared and the versions it ran. Nothing else is tuned: no Go or Node variable is set.", body: table(ctx, "durable-settings", ["Harness", "Versions", "Declared settings", "Environment"], set, { tools: false }) });
    M.gates.forEach(function (g, i) {
      var scen = g.scenarios.map(function (z) { var arms = Object.keys(z.arms).join(", "); return [td("<code>" + esc(z.label) + "</code>", z.label), td(esc(z.name), z.name), td(esc(arms), arms), td(esc(Object.keys(z.arms).map(function (a) { return a + ": " + z.arms[a].requests + " requests, " + z.arms[a].messages + " messages"; }).join("; ")))]; });
      var cross = g.cross_open.map(function (c) { return [td("<code>" + esc(c.label) + "</code>", c.label), td(esc(c.order), c.order), td(c.impossible ? "not possible: " + esc(c.impossible) : c.ok ? "same transcript" + (c.messages != null ? " (" + c.messages + " messages)" : "") : "differs", String(c.ok))]; });
      var notes = [["Rows identical", g.row_identical], ["Differences", g.differences], ["Flaky", g.flaky]].map(function (n) { return n[0] + ": " + n[1]; }).concat(g.different_work.map(function (d) { return "Different work, " + shortName(I.harn[d.arm] || { name: d.arm }) + " on " + d.label + ": " + d.reason; }),
        g.capabilities.filter(function (c) { return c.reason; }).map(function (c) { return "Cannot run, " + shortName(I.harn[c.arm] || { name: c.arm }) + ", " + c.capability + ": " + c.reason; }));
      out += card(ctx, { id: "durable-gate-" + i, title: "Equivalence gate" + (M.gates.length > 1 ? ": run " + esc(g.run) : ""), sub: esc("Nothing was timed until both arms left the same conversation state and sent the same model requests, and each opened the other's store where its runtime can. " + (g.passed ? "The gate passed" : "The gate did not pass") + (g.oracle ? " against " + g.oracle : "") + ". Source: " + g.source + "."),
        body: (g.failures.length ? '<ul class="plan">' + g.failures.map(function (f) { return "<li>" + esc(f) + "</li>"; }).join("") + "</ul>" : "") +
          (scen.length ? table(ctx, "durable-gate-" + i, ["Fixture", "Scenario", "Arms", "What each arm did"], scen, { tools: false }) : "") + (cross.length ? table(ctx, "durable-cross-" + i, ["Fixture", "Order (writer then reader)", "Cross-open"], cross, { tools: false }) : "") +
          '<p class="muted">' + notes.map(esc).join("<br>") + "</p>" });
    });
    if (M.fixtures.length) {
      var digest = function (list) { var d = (list || []).join(" "); return td('<code data-tip="' + esc(d) + '" tabindex="0">' + esc((list || []).map(function (x) { return x.slice(0, 12); }).join(" ")) + "</code>", d); };
      var fx = M.fixtures.map(function (f) { return [td("<code>" + esc(f.scenario) + "</code>", f.scenario), digest(f.sha256), digest(f.store_sha256), td(esc(f.writer || ""), f.writer || ""), td(esc(f.variant || ""), f.variant || ""), td(f.turns == null ? "" : String(f.turns), f.turns)]; });
      out += card(ctx, { id: "durable-fixtures", title: "Fixtures", sub: "The sha256 of each fixture's script and of the store built from it (the first 12 digits; hover for all), the arm that built the store and the kind of words. One digest per workload means every arm opened the same fixture.", body: table(ctx, "durable-fixtures", ["Workload", "Script sha256", "Store sha256", "Built by", "Words", { h: "Turns", num: true }], fx, { tools: false }) });
    }
    var floors = D.floors.filter(function (k) { return I.metric[k] && I.cellOf[k] && I.cellOf[k]["-"]; });
    if (floors.length) {
      var rows2 = []; floors.forEach(function (k) { var mt = I.metric[k], c = I.cellOf[k]["-"]; I.D.harnesses.forEach(function (h) { if (c.stats[h.id]) rows2.push([td(esc(mt.title), mt.title), td(esc(cap(mt.word)), mt.word), td(hname(h), h.name), td(esc(val(c.stats[h.id].median, c.unit)), c.stats[h.id].median)]); }); });
      out += card(ctx, { id: "durable-floors", title: "Floors", sub: "The adapter with no durable runtime (host floor) and the recorded statements replayed with no runtime (SQL floor). warm_net_ms is the warm turn less the host floor of the same arm and round.", body: table(ctx, "durable-floors", ["Floor", "Measure", "Harness", { h: "Median", num: true }], rows2, { tools: false }) });
    }
    return out;
  }

  // ---- a section is the explorer of its metrics: chips to choose them, one small chart for each under one view switch, and the whole table
  var VIEWS_OF_CHART = [["bars", "Bars"], ["dots", "Dots"], ["rounds", "Rounds"]];
  var LENS_WORDS = { fit: "Capacity", cpu: "CPU", wall: "Time", memory: "Memory", size: "Size", count: "Work per turn", wire: "Wire", other: "Other" };
  var LENS_ORDER = ["fit", "cpu", "wall", "memory", "size", "count", "wire", "other"];
  function lensName(l) { return LENS_WORDS[l] || cap(l); }
  // the metrics a reader chose on a section page: the `m` list of the URL, or the headline metric when there is none (`none` is an empty choice)
  function defaultKeys(sec) { return sec.defaults && sec.defaults.length ? sec.defaults : sec.head ? [sec.head] : []; }
  function chosenKeys(route, sec) {
    var m = route.params.m;
    if (!m || !m.length) return defaultKeys(sec);
    return sec.keys.filter(function (k) { return m.indexOf(k) >= 0; });
  }
  function keysHref(route, sec, keys) {
    keys = sec.keys.filter(function (k) { return keys.indexOf(k) >= 0; });
    var dflt = sec.keys.filter(function (k) { return defaultKeys(sec).indexOf(k) >= 0; }), same = keys.length === dflt.length && keys.every(function (k, i) { return k === dflt[i]; });
    return withParam(route, "m", same ? "" : keys.length ? keys : ["none"]);
  }
  // the hash that shows or hides one value of a list that filters a page (`s` sections, `k` kinds); the full list is no parameter, an empty one is `none`
  function listHref(route, key, all, cur, value) {
    var next = cur.indexOf(value) >= 0 ? cur.filter(function (x) { return x !== value; }) : cur.concat([value]);
    next = all.filter(function (x) { return next.indexOf(x) >= 0; });
    return withParam(route, key, next.length === all.length ? "" : next.length ? next : ["none"]);
  }
  function listOf(route, key, all) {
    var v = route.params[key];
    return !v || !v.length ? all.slice() : all.filter(function (x) { return v.indexOf(x) >= 0; });
  }
  // the metrics of a section as a matrix: a row for each workload, a column for each metric name under its kind. A cell toggles that metric (and is there only where the workload has it); a row or a column header toggles the whole row or column.
  // The rows of the picker are the workloads (a workload with variants, the 200 KB and the 50 KB file, has a row for each); the columns are the metric words (without their variant) that the tables of the page
  // have as main columns, and the other words are in a second picker under a closed "More metrics (N)" (open when a chosen metric is in it): the picker is never wider than the page.
  var PICK_MAX = 8;   // columns of a picker: eight 84 px columns and the row names fit the page at 1280 px
  function metricMatrix(I, route, sec, chosen) {
    var rows = [], rowOf = {}, cols = [], colOf = {}, cells = {}, vo = {}, byW = {}, titleOf = workloadTitles(I, sec.keys);
    sec.keys.forEach(function (k) { var mt = I.metric[k]; (byW[mt.workload] = byW[mt.workload] || []).push(mt); });
    Object.keys(byW).forEach(function (w) { var v = variantsOf(byW[w]); Object.keys(v).forEach(function (k) { vo[k] = v[k]; }); });
    sec.keys.forEach(function (k) {
      var mt = I.metric[k], v = vo[k], rk = mt.workload + "|" + v.variant, ck = mt.lens + "|" + v.base;
      if (!(rk in rowOf)) { rowOf[rk] = rows.length; rows.push({ id: rk, title: v.variant ? titleOf[mt.workload] + ", " + v.variant : titleOf[mt.workload], keys: [] }); }
      if (!(ck in colOf)) { colOf[ck] = cols.length; cols.push({ id: ck, lens: mt.lens, word: v.base, at: cols.length, keys: [], main: MAIN_WORDS.indexOf(v.base) >= 0 }); }
      var r = rows[rowOf[rk]], c = cols[colOf[ck]];
      r.keys.push(k); c.keys.push(k);
      (cells[r.id + "|" + c.id] = cells[r.id + "|" + c.id] || []).push(k);
    });
    var rank = function (l) { var i = LENS_ORDER.indexOf(l); return i < 0 ? LENS_ORDER.length : i; };
    cols.sort(function (a, b) { return rank(a.lens) - rank(b.lens) || a.at - b.at; });
    var allOn = function (ks) { return ks.every(function (k) { return chosen.indexOf(k) >= 0; }); };
    var href = function (ks) { return esc(keysHref(route, sec, allOn(ks) ? chosen.filter(function (k) { return ks.indexOf(k) < 0; }) : chosen.concat(ks))); };
    var card = function (cs) {
      var rs = rows.filter(function (r) { return cs.some(function (c) { return cells[r.id + "|" + c.id]; }); });
      return matrixCard({ rows: rs, cols: cs, on: allOn, href: href, all: esc(keysHref(route, sec, sec.keys)), none: esc(keysHref(route, sec, [])),
        cell: function (r, c) { var ks = cells[r.id + "|" + c.id], mt = ks && I.metric[ks[0]]; return ks ? { keys: ks, label: mt.title + ": " + cap(mt.word), tip: mt.title + ": " + cap(mt.word) + "\n" + mt.about } : null; } });
    };
    var main = cols.filter(function (c) { return c.main; }), more = cols.filter(function (c) { return !c.main; });
    if (!main.length) main = cols.slice(0, PICK_MAX), more = cols.slice(PICK_MAX);
    if (main.length > PICK_MAX) more = main.slice(PICK_MAX).concat(more), main = main.slice(0, PICK_MAX);
    more.sort(function (a, b) { return rank(a.lens) - rank(b.lens) || a.at - b.at; });
    var n = more.reduce(function (t, c) { return t + c.keys.length; }, 0), blocks = "", lenses = [];
    more.forEach(function (c) { if (lenses.indexOf(c.lens) < 0) lenses.push(c.lens); });
    lenses.forEach(function (l) { var mine = more.filter(function (c) { return c.lens === l; }); for (var i = 0; i < mine.length; i += PICK_MAX) blocks += card(mine.slice(i, i + PICK_MAX)); });
    return card(main) + (more.length ? '<details class="more mxmore"' + (more.some(function (c) { return c.keys.some(function (k) { return chosen.indexOf(k) >= 0; }); }) ? " open" : "") + "><summary>More metrics (" + n + ")</summary>" + blocks + "</details>" : "");
  }
  // the picker card of a section page: a row for each workload, a column for each metric word under its kind. o.cell(row, col) is null where the workload has no such metric, else {keys, label, tip};
  // o.on(keys) says whether it is chosen and o.href(keys) is the hash a click goes to. With o.all and o.none the row and column headers toggle a whole row or column; without them the picker chooses one metric.
  function matrixCard(o) {
    var multi = o.all != null, kinds = [];
    o.cols.forEach(function (c) { var last = kinds[kinds.length - 1]; if (last && last.lens === c.lens) last.n++; else kinds.push({ lens: c.lens, n: 1 }); });
    var head1 = '<tr><th class="rh" rowspan="2" scope="col">' + (multi ? '<span class="mall"><button type="button" class="lnk" data-href="' + o.all + '">All</button><button type="button" class="lnk" data-href="' + o.none + '">None</button></span>' : "") + "</th>" +
      kinds.map(function (g) { return '<th scope="colgroup" colspan="' + g.n + '" class="kind">' + esc(lensName(g.lens)) + "</th>"; }).join("") + "</tr>";
    var head2 = "<tr>" + o.cols.map(function (c) { return '<th scope="col">' + (multi ? '<button type="button" class="mxcol" aria-pressed="' + o.on(c.keys) + '" data-href="' + o.href(c.keys) + '">' + esc(cap(c.word)) + "</button>" : esc(cap(c.word))) + "</th>"; }).join("") + "</tr>";
    var body = o.rows.map(function (r) {
      return '<tr><th scope="row" class="rh">' + (multi ? '<button type="button" class="mxrow" aria-pressed="' + o.on(r.keys) + '" data-href="' + o.href(r.keys) + '">' + esc(r.title) + "</button>" : esc(r.title)) + "</th>" + o.cols.map(function (c) {
        var x = o.cell(r, c);
        if (!x) return '<td class="mnone"></td>';
        return '<td><button type="button" class="mcell" aria-pressed="' + o.on(x.keys) + '" aria-label="' + esc(x.label) + '" data-href="' + o.href(x.keys) + '" data-tip="' + esc(x.tip) + '"></button></td>';
      }).join("") + "</tr>";
    }).join("");
    return '<section class="card mxcard" aria-label="Metrics of this section"><div class="mscroll"><table class="mtx"><thead>' + head1 + head2 + "</thead><tbody>" + body + "</tbody></table></div></section>";
  }
  // a bar for each harness that has a value: its median from zero, the dashed line at the baseline's median, the 95% interval as a whisker. Bars are values, in ratio mode too (the tooltip has the ratio). rows: the rows with a value, in values (splitRows).
  // o.plain: no link (the tile of the overview is one link)
  function barsChart(I, st, mt, cell, rows, o) {
    o = o || {};
    var base = baseAt(I, st, mt), top = ok(base) ? base : 0;
    rows.forEach(function (r) { [r.v, r.hi].forEach(function (x) { if (ok(x)) top = Math.max(top, x); }); });
    if (!top) return '<p class="empty">No value to plot.</p>';
    top *= 1.04;
    return barRows(rows.map(function (r) {
      return { h: r.h, plain: o.plain, f: r.v / top, label: val(r.v, cell ? cell.unit : "") + (r.nc ? " (different work)" : ""), tip: r.tip, href: o.plain ? null : r.href, prov: r.prov,
        whisker: ok(r.lo) && ok(r.hi) ? [r.lo / top, r.hi / top] : null };
    }), { base: ok(base) && base > 0 ? base / top : null });
  }
  // every round of a harness as a dot on one axis, from zero, with a tick at the median: the spread shows. Rounds are values, in ratio mode too. rows: the rows with rounds, in values.
  function roundsChart(I, mt, cell, width, rows) {
    rows = rows.map(function (r) { return { h: r.h, vs: cell.values[r.h.id], med: cell.stats[r.h.id] ? cell.stats[r.h.id].median : null, href: r.href, tip: r.tip }; });
    var all = [];
    rows.forEach(function (r) { (r.vs || []).forEach(function (v) { if (ok(v)) all.push(v); }); });
    if (!all.length) return '<p class="empty">No round to plot.</p>';
    var W = Math.max(220, Math.floor(width)), RH = 20, T = 6, B = 20, R = 12, cw = 6.6;
    var names = rows.map(function (r) { return shortName(r.h); });
    var L = Math.round(10 + Math.max.apply(null, names.map(function (n) { return n.length; }).concat([4])) * cw);
    var PL = L, hi = Math.max.apply(null, all) * 1.06 || 1, au = axisUnit(cell ? cell.unit : "", hi), X = function (v) { return PL + v / hi * (W - PL - R); };
    var H = T + rows.length * RH + B, s = svgOpen(W, H, mt.title + ": " + mt.word + ", every round");
    var lastX = -1e9;
    niceTicks(0, hi, 3).filter(function (t) { var x = X(t); if (t > hi || x - lastX < 38) return false; lastX = x; return true; }).forEach(function (t) {
      s += '<line class="gl" x1="' + X(t).toFixed(1) + '" x2="' + X(t).toFixed(1) + '" y1="' + (T - 4) + '" y2="' + (H - B) + '"/><text class="xl" x="' + X(t).toFixed(1) + '"' + (X(t) > W - 22 ? ' text-anchor="end"' : "") + ' y="' + (H - B + 14) + '">' + esc(fmtAxis(t / au.div)) + "</text>";
    });
    s += '<text class="axl" x="' + (W - R) + '" y="' + (H - 4) + '">' + esc(au.u) + "</text>";
    rows.forEach(function (r, i) {
      var y = T + i * RH + RH / 2;
      s += '<g class="series h-' + esc(r.h.colour) + '"><text class="dl" x="' + (L - 8) + '" y="' + (y + 4) + '">' + esc(names[i]) + "</text>";
      var dots = r.vs.map(function (v, k) { return ok(v) ? '<circle class="rd" cx="' + X(v).toFixed(1) + '" cy="' + y + '" r="2.8" data-tip="' + esc(shortName(r.h) + ", round " + (k + 1) + ": " + val(v, cell.unit)) + '"/>' : ""; }).join("");
      var med = ok(r.med) ? '<line class="med" x1="' + X(r.med).toFixed(1) + '" x2="' + X(r.med).toFixed(1) + '" y1="' + (y - 7) + '" y2="' + (y + 7) + '"/>' : "";
      s += '<a href="' + esc(r.href) + '" aria-label="' + esc(names[i] + ", every round") + '">' + dots + med + "</a></g>";
    });
    return '<div class="svgwrap">' + s + "</svg></div>";
  }
  function metricCard(ctx, I, st, mt, view, width) {
    var cell = metricCell(I, mt.key, st.api), ratio = st.mode === "ratio";
    var sub = view === "bars" ? "Median, from zero, with the 95% interval of the median. The dashed line is " + shortName(st.base) + "." :
      view === "rounds" ? "Every round, in values. The tick is the median." : (ratio ? "Ratio to " + shortName(st.base) + ", with its 95% interval. The dashed line is 1×." : "Median, with the 95% interval of the median. The dashed line is " + shortName(st.base) + ".");
    // bars and rounds are values, dots follow the choice of values or ratio; only the harnesses that have a value are drawn, the others are named under the chart
    var vst = view === "dots" ? st : Object.assign({}, st, { mode: "values" }), sp = splitRows(metricRows(I, vst, mt)), have = sp.have, absent = sp.absent;
    if (view === "rounds") {
      have = sp.have.filter(function (r) { var vs = cell && cell.values && cell.values[r.h.id]; return vs && vs.length; });
      sp.have.forEach(function (r) { if (have.indexOf(r) < 0) absent.push({ h: r.h, na: true, tip: shortName(r.h) + ": no round was recorded for this measure." }); });
      absent.sort(function (a, b) { return I.order[a.h.id] - I.order[b.h.id]; });
    }
    var chart = !have.length ? '<p class="empty">' + NO_VALUE + "</p>" : view === "bars" ? barsChart(I, vst, mt, cell, have) : view === "rounds" ? roundsChart(I, mt, cell, width, have) :
      dotPlot(have, { width: width, compact: true, ratio: ratio, unit: cell ? cell.unit : "", base: baseAt(I, st, mt), baseName: shortName(st.base), label: mt.title + ": " + mt.word });
    return card(ctx, { id: "p-" + mt.key, cls: "small", title: esc(mt.title + ": " + cap(mt.word)), sub: esc(sub), chart: chart + absentNote(I, st.route, absent, { base: st.base, quiet: !have.length }),
      tools: envChip(cell) + provBadge(cell ? cellProv(I, cell) : []) + '<a class="info" href="' + esc(link("metric", [mt.key], metricParams(I, st))) + '" aria-label="About this metric" data-tip="' + esc(mt.about + "\nClick for the formula and every harness.") + '">i</a>' });
  }
  // one section page: a sentence, the metric chips, one chart for each chosen metric under one view switch, and the table of every metric of the section
  function sectionBody(ctx, I, route, st, sec) {
    if (sec.kind === "agents") return agentsBody(ctx, I, route, st, sec);
    var dur = sec.id === "durable" && I.D.durable;
    var head = '<div class="pagehead"><h1>' + esc(sec.title) + (dur ? " " + provBadge(durableProv(I)) : "") + '</h1><p class="lede">' + esc(sec.about) + ' <a class="how" href="' + esc(link("method")) + '">How it works</a></p>' + (dur ? durableNote(I) : "") + "</div>";
    if (sec.kind === "faults") return head + faultsBody(ctx, I, st, sec);
    var lined = sec.id === "extensions" || sec.id === "durable", chosen = chosenKeys(route, sec), view = st.view === "line" && !lined ? "bars" : st.view;
    var views = VIEWS_OF_CHART.concat(lined ? [["line", "Line"]] : []);
    var switcher = '<div class="viewbar"><span class="lbl">View</span>' + seg(views, view, function (v) { return 'data-href="' + esc(withParam(route, "view", v === "bars" ? "" : v)) + '"'; }) + "</div>";
    var charts;
    if (view === "line") charts = sec.id === "durable" ? durableLineCards(ctx, I, st, sec) : sweepCards(ctx, I, st);
    else if (!chosen.length) charts = '<p class="empty">Choose a metric ' + (dur ? "below" : "above") + " to see it here.</p>";
    else {
      var cols = Math.max(1, Math.min(chosen.length, ctx.avail > 700 ? 2 : 1)), w = chartWidth(ctx, cols);
      charts = '<div class="smalls" style="--n:' + cols + '">' + chosen.map(function (k) { return metricCard(ctx, I, st, I.metric[k], view, w); }).join("") + "</div>";
    }
    var tables = workloadTables(I, st, sec.keys, "all-" + sec.id), table = card(ctx, { id: "all-" + sec.id, title: "All metrics in this section (" + tables.count + ")", tools: provBadge(tables.prov) + csvBtn("all-" + sec.id), body: tables.html });
    var crashGrid = dur && secApi(I, st, sec) === "native" ? crashBlock(ctx, I, st, sec) : "";
    if (dur) return head + switcher + charts + crashGrid + metricMatrix(I, route, sec, chosen) + table + (sec.ext ? externalBlock(I, sec) : "");   // the Durable section has many workloads: its charts come first and the picker of metrics under them
    return head + metricMatrix(I, route, sec, chosen) + switcher + charts + table + (sec.ext ? externalBlock(I, sec) : "");
  }
  function railOf(I, route, current) {
    return '<nav class="rail' + (current === HOME ? " onhome" : "") + '" aria-label="Sections"><a href="' + esc(link(HOME, [], keep(route))) + '"' + (current === HOME ? ' aria-current="page"' : "") + '>Overview</a>' + I.sections.map(function (s) {
      return '<a' + (s.empty ? ' class="off"' : "") + ' href="' + esc(link("r", [s.id], keep(route))) + '"' + (s === current ? ' aria-current="page"' : "") + ">" + esc(s.title) + "</a>";
    }).join("") + '<a href="' + esc(link("all", [], keep(route))) + '"' + (current === "all" ? ' aria-current="page"' : "") + ">All metrics</a></nav>";
  }
  // ---- Other suites: other projects' benchmarks, run as they are upstream or imported with their provenance. Their method, their numbers: they are in no tile, ratio, grade or table of Buffon's own.
  function xStamp(t) { return t ? String(t).replace("T", " ").replace(/:\d\d(?:\.\d+)?Z$/, " UTC") : ""; }
  function xMark(I, harness, target) { var h = harness ? I.harn[harness] : null; return h ? '<span class="hn">' + dot(h) + "<span>" + esc(target) + "</span></span>" : '<span class="hn"><span>' + esc(target) + "</span></span>"; }
  // the suite's own table, as printed: its column names and its cell text. Targets that share the columns have one column each under every name.
  function xTable(I, tb, runs) {
    var colour = {}, multi = tb.targets.length > 1;
    runs.forEach(function (r) { var h = r.harness ? I.harn[r.harness] : null; if (h) colour[r.target] = h.colour; });
    var cls = function (t) { return t ? (colour[t] ? "tcol h-" + esc(colour[t]) : "tcol") : ""; }, head;
    if (!multi) head = "<tr>" + tb.head.map(function (c) { return '<th scope="col">' + esc(c.name) + "</th>"; }).join("") + "</tr>";
    else {
      var groups = [], rest = tb.head.slice(1);
      rest.forEach(function (c) { var g = groups[groups.length - 1]; if (g && g.name === c.name) g.n++; else groups.push({ name: c.name, n: 1 }); });
      head = '<tr><th scope="col" rowspan="2">' + esc(tb.head[0].name) + "</th>" + groups.map(function (g) { return '<th scope="colgroup" colspan="' + g.n + '">' + esc(g.name) + "</th>"; }).join("") + "</tr>" +
        "<tr>" + rest.map(function (c) { return '<th scope="col" class="' + cls(c.target) + '">' + xMark(I, (runs.filter(function (r) { return r.target === c.target; })[0] || {}).harness, c.target) + "</th>"; }).join("") + "</tr>";
    }
    var body = tb.rows.map(function (row) {
      return "<tr>" + row.map(function (cell, i) { var t = tb.head[i].target; return i === 0 ? '<th scope="row">' + esc(cell) + "</th>" : '<td class="' + cls(t) + '">' + esc(cell) + "</td>"; }).join("") + "</tr>";
    }).join("");
    return '<div class="tablewrap"><table class="data xtable"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div>";
  }
  function xRun(I, r) {
    var host = r.host ? [r.host.cpu_model, r.host.memory_gib ? r.host.memory_gib + " GiB" : "", r.host.kernel].filter(Boolean).join(", ") : "";
    var status = r.timed_out ? "timed out" : "exit " + r.exit;
    return '<li class="xrun">' + xMark(I, r.harness, r.target) + " <code>" + esc(r.command) + "</code><small>Ran " + esc(xStamp(r.started_utc)) + (host ? " on " + esc(host) : ", host not recorded") +
      (ok(r.wall_s) ? ", " + sig(r.wall_s) + " s" : "") + ", " + status + (r.egress.length ? ", connected outside this machine: " + esc(r.egress.join(", ")) : "") + ".</small></li>";
  }
  function xOutput(r, open) {
    var all = r.files && r.files.stdout ? '<a href="' + esc(r.files.stdout) + '">stdout.txt</a>' : "";
    return '<details class="more xout"' + (open ? " open" : "") + "><summary>Raw output of " + esc(r.target) + '</summary><pre class="xpre">' + esc(r.stdout || "(the suite printed nothing)") + "</pre>" +
      (r.stdout_cut ? '<p class="muted">The first ' + group(r.stdout.length) + " of " + group(r.stdout_chars) + " characters. " + all + " has all of it.</p>" : all ? '<p class="muted">' + all + "</p>" : "") + "</details>";
  }
  function xCardHead(c, sub, lvl) {
    return '<header class="card-h"><div><h' + lvl + ' class="xtitle">' + esc(c.title) + "</h" + lvl + '><p class="sub">' + sub + "</p></div></header>";
  }
  function suiteCard(I, c, note, lvl) {
    var repo = c.source_url ? '<a href="' + esc(c.source_url) + '">' + esc(c.source_url.replace(/^https:\/\/github\.com\//, "").replace(/\/tree\/.*$/, "")) + "@" + esc(c.commit.slice(0, 12)) + "</a>" : "<code>" + esc(c.commit.slice(0, 12)) + "</code>";
    var sub = [c.owner ? 'By <a href="' + esc(c.owner_url) + '">' + esc(c.owner) + "</a>" : "", c.licence ? esc(c.licence) : "", "pinned at " + repo + (c.caller_commit ? " (a commit the caller chose, not the suite's pin)" : "")].filter(Boolean).join(" · ");
    var unparsed = c.runs.filter(function (r) { return !r.parsed; });
    var notes = c.runs.map(function (r) {
      return r.has_parser && !r.parsed ? '<p class="xwarn">Table not parsed for ' + esc(r.target) + (r.table_error ? ": " + esc(r.table_error) : "") + ". Its output is below.</p>" :
        !r.has_parser ? '<p class="muted">The suite prints no table that Buffon reads. Its output, as printed, is below' + (c.runs.length > 1 ? " for " + esc(r.target) : "") + ".</p>" : "";
    }).join("");
    var tables = c.tables.map(function (tb) { return (c.tables.length > 1 ? '<h4 class="xt">' + tb.targets.map(esc).join(", ") + "</h4>" : "") + xTable(I, tb, c.runs); }).join("");
    return '<section class="card xsuite" id="x-' + esc(c.id) + '">' + xCardHead(c, sub, lvl) + '<p class="xnote">' + esc(note) + '.</p>' + (c.notes ? '<p class="muted">' + esc(c.notes) + "</p>" : "") +
      '<ul class="xruns">' + c.runs.map(function (r) { return xRun(I, r); }).join("") + "</ul>" + notes + tables + c.runs.map(function (r) { return xOutput(r, !r.parsed); }).join("") + "</section>";
  }
  function resultsCard(I, c, note, lvl) {
    var sub = [c.owner ? 'By <a href="' + esc(c.owner_url) + '">' + esc(c.owner) + "</a>" : "", esc(c.licence), 'source <a href="' + esc(c.source_url) + '">' + esc(c.repo) + "@" + esc(c.commit.slice(0, 12)) + "</a>", "published " + esc(c.published)].filter(Boolean).join(" · ");
    var files = '<details class="more xout"><summary>The files, unchanged (' + c.files.length + ')</summary><ul class="xfiles">' + c.files.map(function (f) {
      return '<li><a href="' + esc(f.href) + '">' + esc(f.name) + "</a> <small>sha256 " + esc(f.sha256.slice(0, 16)) + (f.rows != null ? ", " + f.rows + " rows" : "") + "</small></li>";
    }).join("") + '<li><a href="' + esc(c.record) + '">external.json</a> <small>the record of where they came from</small></li></ul></details>';
    return '<section class="card xsuite" id="x-' + esc(c.id) + '">' + xCardHead(c, sub, lvl) + '<p class="xnote">' + esc(note) + ".</p>" +
      '<ul class="xruns"><li class="xrun"><span>Imported, not run here. It measured ' + esc(c.version) + "</span><small>Source host: " + esc(c.host) + ". Imported " + esc(xStamp(c.imported_utc)) + ".</small></li></ul>" +
      (c.tables.length ? '<p class="muted">Medians over the source\'s own rows, by file, scenario and build.</p>' + xTable(I, c.tables[0], []) : '<p class="xwarn">Table not parsed: the files hold no rows with a build and a scenario.</p>') + files + "</section>";
  }
  // the cards of the suites a section shows (the registry decides which: docs/EXTERNAL.md), grouped by project
  function externalBlock(I, sec) {
    var X = I.D.external && I.D.external[sec.ext], note = I.D.external && I.D.external.note;
    if (!X) return "";
    var under = sec.kind === "metrics", lvl = under ? 3 : 2;   // under Buffon's own metrics the suites have a heading of their own; on a page of their own the page says it
    return '<div class="xblock">' + (under ? '<h2 class="xhead">Each project\'s own durable suites</h2>' : "") + X.groups.map(function (g) {
      return '<section class="xgroup"><h' + lvl + ' class="xlabel">' + esc(g.label) + "</h" + lvl + ">" + g.cards.map(function (c) { return c.kind === "results" ? resultsCard(I, c, note, lvl + 1) : suiteCard(I, c, note, lvl + 1); }).join("") + "</section>";
    }).join("") + "</div>";
  }
  function externalBody(ctx, I, route, sec) {
    var head = '<div class="pagehead"><h1>' + esc(sec.title) + '</h1><p class="lede">' + esc(sec.about) + ' <span class="how">' + docLink(I, "EXTERNAL", "How they are run") + "</span></p></div>";
    return head + (sec.id === "durable" ? durableNone(I) : "") + externalBlock(I, sec);
  }
  // a section the loaded runs have no data for: what it will measure, which workloads and harnesses of the launch rerun fill it, and the command. No number is drawn.
  function emptyBody(I, sec) {
    var P = I.D.plan || { workloads: [], durable: { arms: [], workloads: [] } }, rows = "", note = "";
    var match = function (w) { return (sec.plan || sec.scen) && (sec.plan || sec.scen).test(w.scenario) && sec.id !== "other"; };
    var ws = sec.kind === "metrics" || sec.kind === "external" ? P.workloads.filter(match) : [];
    if (sec.id === "durable") {
      rows = '<ul class="plan">' + P.durable.workloads.map(function (w) { return "<li><b><code>" + esc(w.scenario) + "</code></b> " + esc(w.note) + "</li>"; }).join("") + "</ul>" +
        '<p class="muted">Harnesses: ' + P.durable.arms.map(esc).join(", ") + ". " + docLink(I, "DURABLE", "The plan") + ".</p>";
    } else if (ws.length) {
      var seen = {}, arms = [];
      ws.forEach(function (w) { w.arms.forEach(function (a) { if (!seen[a]) { seen[a] = 1; arms.push(a); } }); });
      rows = '<ul class="plan">' + ws.map(function (w) { return "<li><b>" + esc(w.title) + "</b> " + esc(w.use) + "</li>"; }).join("") + "</ul>" +
        '<p class="muted">Harnesses in the launch rerun: ' + arms.map(esc).join(", ") + ".</p>";
    }
    if (sec.id === "durable") note = '<h3 class="sech2">To fill it</h3><p>No durable run is in the results yet. Run one, then build the site from its directory:</p><pre class="cmd">' + esc(P.durable.command) + '</pre><p class="muted">The whole native plan is the campaign file <code>' + esc(P.durable.campaign) + "</code>: <code>" + esc(P.durable.campaign_command) + "</code>.</p>";
    else if (ws.length) note = '<h3 class="sech2">To fill it</h3><pre class="cmd">' + esc(P.command) + "</pre>";
    else note = '<p class="muted">' + docLink(I, sec.kind === "external" ? "EXTERNAL" : "WHAT-WE-MEASURE", "How it is measured") + ".</p>";
    return '<div class="pagehead"><h1>' + esc(sec.title) + '</h1><p class="lede">' + esc(sec.about) + '</p></div><p class="empty"><span class="vchip off">Not run yet</span></p><div class="card">' +
      '<h3 class="sech2">What it measures</h3><p>' + esc(sec.what) + "</p>" + rows + note + "</div>";
  }
  function viewSection(ctx, I, route) {
    var sec = I.sec[route.args[0]];
    if (!sec) return notFound(I);
    var sctx = { index: ctx.index, ui: ctx.ui, width: ctx.width, avail: ctx.width > 860 ? ctx.width - 226 : ctx.width };
    if (sec.empty) return '<div class="results">' + railOf(I, route, sec) + '<div class="rbody">' + emptyBody(I, sec) + "</div></div>";
    if (sec.kind === "external") return '<div class="results">' + railOf(I, route, sec) + '<div class="rbody">' + externalBody(sctx, I, route, sec) + "</div></div>";   // nothing to filter or compare: no control bar
    var st = stateOf(I, route); st.api = secApi(I, st, sec);
    return controlBar(I, route, st, sec) + '<div class="results">' + railOf(I, route, sec) + '<div class="rbody">' + sectionBody(sctx, I, route, st, sec) + "</div></div>";
  }
  // every metric of every section: the tables of each section one under the other (a table for each workload, as on the section page), filtered by section and by kind, sortable, in values or ratios, one Download CSV
  function viewAll(ctx, I, route) {
    var secs = I.sections.filter(function (s) { return !s.empty && s.kind === "metrics"; }), allKeys = [].concat.apply([], secs.map(function (s) { return s.keys; }));
    var lenses = LENS_ORDER.filter(function (l) { return allKeys.some(function (k) { return I.metric[k].lens === l; }); });
    allKeys.forEach(function (k) { var l = I.metric[k].lens; if (lenses.indexOf(l) < 0) lenses.push(l); });
    var secIds = secs.map(function (s) { return s.id; }), curS = listOf(route, "s", secIds), curK = listOf(route, "k", lenses);
    var st = stateOf(I, route), pseudo = { id: "all", kind: "metrics", keys: allKeys }; st.api = secApi(I, st, pseudo);
    var groups = secs.filter(function (s) { return curS.indexOf(s.id) >= 0; }).map(function (s) { return { s: s, keys: s.keys.filter(function (k) { return curK.indexOf(I.metric[k].lens) >= 0; }) }; }).filter(function (g) { return g.keys.length; });
    var keys = [].concat.apply([], groups.map(function (g) { return g.keys; })), shownSecs = 0, shownKeys = 0;
    var chips = function (label, key, all, cur, name) {
      return '<div class="chips"><span class="lbl">' + esc(label) + "</span>" + all.map(function (x) {
        return '<button type="button" class="chip m" aria-pressed="' + (cur.indexOf(x) >= 0) + '" data-href="' + esc(listHref(route, key, all, cur, x)) + '">' + esc(name(x)) + "</button>";
      }).join("") + "</div>";
    };
    var head = '<div class="pagehead"><h1>All metrics</h1><p class="lede">Every metric, grouped by section. Sort a column, switch between values and ratios, filter by section or kind, or download the table.</p></div>';
    var filters = '<div class="filters">' + chips("Sections", "s", secIds, curS, function (id) { return I.sec[id].title; }) + chips("Kind", "k", lenses, curK, lensName) + "</div>";
    var provAll = {};
    var parts = groups.map(function (g) {
      var t = workloadTables(I, st, g.keys, "all-metrics-" + g.s.id, { group: "all-metrics" });
      if (!t.count) return "";
      shownSecs++; shownKeys += t.count;
      t.prov.forEach(function (r) { provAll[r.id] = r; });
      return '<section class="secg"><h2><a href="' + esc(link("r", [g.s.id], keep(route))) + '">' + esc(g.s.title) + "</a> <small>" + plural(t.count, "metric") + "</small></h2>" + t.html + "</section>";
    }).join("");
    var body = shownKeys ? card(ctx, { id: "all-metrics", title: plural(shownKeys, "metric") + " in " + plural(shownSecs, "section"), tools: provBadge(Object.keys(provAll).map(function (k) { return provAll[k]; })) + csvBtn("all-metrics"), body: parts }) :
      '<p class="empty">' + (keys.length ? NO_VALUE : "No metric matches these filters.") + "</p>";
    var sctx = { index: ctx.index, ui: ctx.ui, width: ctx.width, avail: ctx.width > 860 ? ctx.width - 226 : ctx.width };
    return controlBar(I, route, st, pseudo) + '<div class="results">' + railOf(I, route, "all") + '<div class="rbody">' + head + filters + body + "</div></div>";
  }

  // the overview: one tile for each section, its headline metric and a small plot of every selected harness
  // one factual line under a tile's chart: the lowest and the highest value of the selected harnesses, with their names. It says nothing about which is better.
  function tileRange(items) {
    if (items.length < 2) return "";
    var s = items.slice().sort(function (a, b) { return a.v - b.v; }), lo = s[0], hi = s[s.length - 1];
    if (lo.v === hi.v) return "";
    return '<p class="tile-r">from ' + esc(dashRange(lo.text)) + " (" + esc(shortName(lo.h)) + ") to " + esc(dashRange(hi.text)) + " (" + esc(shortName(hi.h)) + ")</p>";
  }
  function tile(ctx, I, route, st, sec) {
    var href = link("r", [sec.id], keep(route));
    if (sec.empty) return '<a class="card tile off" href="' + esc(href) + '"><h2>' + esc(sec.title) + '</h2><p class="tile-m">Not run yet</p><p class="tile-a">' + esc(sec.about) + "</p></a>";
    if (sec.kind === "agents") return agentsTile(ctx, I, st, href);
    if (sec.kind === "external") {   // the project suites of the Durable section: how many runs and the newest date, never a number of theirs
      var X = I.D.external[sec.ext];
      return '<a class="card tile" href="' + esc(href) + '"><h2>' + esc(sec.title) + '</h2><p class="tile-m">Project suites: ' + plural(X.runs, "run") + "</p>" + (X.newest ? '<p class="tile-r">newest run ' + esc(X.newest) + "</p>" : "") + "</a>";
    }
    var title = "<h2>" + esc(sec.title) + (sec.id === "durable" ? envChip(metricCell(I, sec.head, secApi(I, st, sec))) : "") + "</h2>";
    if (sec.kind === "faults") {
      var list = faultsOf(I, st);
      var fr = list.length ? st.hs.map(function (h) { var c = faultCount(list, h); return c.ran ? { h: h, v: c.passed, text: c.passed + " of " + c.of } : null; }).filter(Boolean) : [];
      return '<a class="card tile" href="' + esc(href) + '">' + title + '<p class="tile-m">Faults passed, of ' + list.length + "</p>" + faultBars(I, st, list, { plain: true }) + tileRange(fr) + "</a>";
    }
    var s2 = {}; Object.keys(st).forEach(function (k) { s2[k] = st[k]; }); s2.api = secApi(I, st, sec);
    var mt = I.metric[sec.head], cell = metricCell(I, mt.key, s2.api), ratio = s2.mode === "ratio", dots = st.view === "dots";
    // the tile draws the bars of the section page, compact (dots when the reader chose them); a harness with no value is named under it
    var vst = Object.assign({}, s2, { mode: "values" }), vsp = splitRows(metricRows(I, vst, mt)), sp = dots ? splitRows(metricRows(I, s2, mt)) : vsp;
    var chart = !sp.have.length ? '<p class="empty">' + NO_VALUE + "</p>" : dots ?
      dotPlot(sp.have, { width: chartWidth(ctx, ctx.width > 860 ? 2 : 1), compact: true, ratio: ratio, unit: cell ? cell.unit : "", base: baseAt(I, s2, mt), baseName: shortName(st.base), label: mt.title + ": " + mt.word }) :
      barsChart(I, vst, mt, cell, sp.have, { plain: true });
    return '<a class="card tile" href="' + esc(href) + '">' + title + '<p class="tile-m">' + esc(mt.title === sec.title ? cap(mt.word) : mt.title + ": " + cap(mt.word)) + " " + provBadge(cell ? cellProv(I, cell) : []) + "</p>" +
      chart + absentNote(I, st.route, sp.absent, { plain: true, base: st.base, quiet: !sp.have.length }) +
      tileRange(vsp.have.filter(function (r) { return ok(r.v); }).map(function (r) { return { h: r.h, v: r.v, text: val(r.v, cell ? cell.unit : "") }; })) + "</a>";
  }
  // the home page has the same two columns as a section page: the rail of the sections on the left, with Overview chosen, and the hero, the control bar and the tiles beside it
  function viewHome(ctx, I, route) {
    var st = stateOf(I, route), hctx = { index: ctx.index, ui: ctx.ui, width: ctx.width, avail: ctx.width > 860 ? ctx.width - 226 : ctx.width };
    var count = I.sections.reduce(function (n, s) { return n + (s.kind === "metrics" ? s.keys.length : 0); }, 0);
    var tiles = '<div class="tiles">' + I.sections.filter(function (s) { return s.empty || s.kind !== "external" || s.id === "durable"; }).map(function (s) { return tile(hctx, I, route, st, s); }).join("") + '</div><p class="allink"><a href="' + esc(link("all", [], keep(route))) + '">All ' + count + " metrics, by section</a></p>";
    return '<div class="results onhome">' + railOf(I, route, HOME) + '<div class="rbody">' + hero(I) + controlBar(I, route, st, null) + tiles + "</div></div>";
  }

  // the harness page: one row for each section with the headline ratio and its interval, on one axis
  function sectionStrip(ctx, I, st, h, tools) {
    var rst = { api: st.api, mode: "ratio", base: st.base, hs: [h] }, isBase = h === st.base, rows = [], lines = [], trs = [], count = { more: 0, less: 0, noise: 0 }, n = 0, D = I.D;
    I.sections.forEach(function (s) {
      if (s.empty || s.kind === "external") return;   // other projects' numbers are in no row of a harness's own results; a section with no data has no row
      var href = link("r", [s.id]);
      if (s.kind === "agents") {
        var e = scaleOf(I).envelopes[0], bits = KINDS.map(function (k) { var a = e.kinds[k].arms[h.id], x = e.kinds[k + "-ext10"] && e.kinds[k + "-ext10"].arms[h.id]; return a && a.rungs && a.rungs.length ? dashRange(fitLabel(a)) + " " + (k === "rpc" ? "RPC" : "print-mode") + (x && x.rungs && x.rungs.length ? " (" + dashRange(fitLabel(x)) + " with 10 extensions)" : "") : null; }).filter(Boolean);
        lines.push('<p class="srow"><a href="' + esc(href) + '">Agent swarming</a> ' + (bits.length ? "fit in " + esc(limitOf(e)) + ": " + esc(bits.join(", ")) + "." : "can't run.") + "</p>");
        return;
      }
      if (s.kind === "faults") {
        var list = faultsOf(I, st), c0 = faultCount(list, h);
        lines.push('<p class="srow"><a href="' + esc(href) + '">Reliability</a> ' + (c0.ran ? c0.passed + " of " + plural(c0.of, "fault") + " passed." : "can't run.") + "</p>");
        return;
      }
      var mt = I.metric[s.head], r2 = {}; Object.keys(rst).forEach(function (k) { r2[k] = rst[k]; }); r2.api = secApi(I, st, s);
      var c = gridCell(I, r2, mt, h), row = { h: h, name: s.title, nameHref: href };
      if (c.na) { row.none = naLabel(c); row.tip = c.na; }
      else if (c.value == null) { row.none = "different work"; row.tip = c.tip; row.href = c.href; }
      else { row.v = c.value; row.lo = c.lo; row.hi = c.hi; row.tip = c.tip; row.href = c.href; }
      rows.push(row);
      trs.push([td('<a href="' + esc(href) + '">' + esc(s.title) + "</a>", s.title), td(esc(mt.title + ": " + cap(mt.word)), mt.title), td(row.v != null ? (isBase ? "1.00×" : '<a href="' + esc(c.href) + '">' + ratioStr(row.v) + "×</a>") : esc(row.none || ""), row.v), td(ok(row.lo) ? ratioStr(row.lo) + " to " + ratioStr(row.hi) : "", row.lo)]);
    });
    if (!isBase) D.metrics.forEach(function (mt) {
      var cell = metricCell(I, mt.key, st.api), c = cell && cell.comparisons[h.id];
      if (!c || c.not_compared) return;
      n++; count[c.verdict === "loss" ? "more" : c.verdict === "win" ? "less" : "noise"]++;
    });
    var sub = isBase ? "This is the baseline: every ratio is relative to it." : n ? "Against " + esc(shortName(st.base)) + ", across " + plural(n, "measure") + ": " + count.more + " cost more, " + count.less + " cost less and " + count.noise + (count.noise === 1 ? " is" : " are") + " within noise." : "";
    var chart = isBase ? "" : dotPlot(rows, { width: chartWidth(ctx, 1), ratio: true, base: 1, baseName: shortName(st.base), label: "headline ratio of each section" });
    return card(ctx, { id: "strip-" + h.slug, title: "Results by section", sub: sub, tools: tools, chart: chart + lines.join(""), table: table(ctx, "strip-" + h.slug, ["Section", "Measure", { h: "Ratio to " + esc(shortName(st.base)), num: true }, { h: "95% interval", num: true }], trs) });
  }
  // the API and the baseline travel with a link into a metric page, so the page opens as the grid does
  function metricParams(I, st) { var p = {}; if (I.multiApi) p.api = st.api; if (!st.base.is_ref) p.base = st.base.slug; return p; }

  function docHref(d) { return d.slug === "README" ? link("about") : link("doc", [d.slug]); }
  function docLink(I, slug, text) { var d = I.doc[slug]; return d ? '<a href="' + esc(docHref(d)) + '">' + esc(text) + "</a>" : esc(text); }
  // the headline: what Buffon is, how the name ties to Pi, and where and when it was measured. The framing is said here and on About, nowhere else.
  function hero(I) {
    var D = I.D, r = D.runs[0] || {}, f = r.facts || {}, run = r.run || {}, site = r.site || {};
    var where = f.cpu_model || site.name || "", when = String(run.started_utc || f.generated_utc || "").slice(0, 10);
    var trust = [where ? "Measured on " + where : "Measured", when ? "on " + when : ""].filter(Boolean).join(" ") + (run.rounds ? ", " + plural(run.rounds, "round") : "") + ".";
    return '<section class="hero"><div class="htext"><h1>Buffon</h1><p class="lead">Benchmarks for coding agents built on Pi\'s use cases.</p>' +
      '<p class="lede">Pi is the foundation many coding agents build on. Buffon runs Pi and those agents through the same scripted tasks, and measures what each one costs your machine.</p>' +
      '<p class="name">Named for Buffon\'s needle: drop a needle on a floor of parallel boards, and the chance it crosses a line depends on π, so counting many drops estimates π. We drop the same Pi use case on every harness, many times, and count.</p>' +
      '<p class="name">A lens on Pi, not a ranking of agents. · <a href="' + esc(link("method")) + '">How it works</a> · <a href="' + esc(link("about", [], { at: "why-buffon" })) + '">Why "Buffon"</a></p>' +
      '<p class="trust">' + esc(trust) + "</p></div>" + heroArt() + "</section>";
  }
  // needles dropped on parallel lines, drawn once from a fixed seed in the theme's colours: a needle that crosses a line is in Pi's blue, the others are muted. It is the same drop on every load.
  function heroArt() {
    var W = 320, H = 150, gap = 30, len = 24, y0 = 15, s = 7, rnd = function () { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
    var out = '<svg class="hero-art" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Needles dropped on a floor of parallel lines. Some cross a line.">';
    for (var k = 0; k < 5; k++) out += '<line class="art-line" x1="0" x2="' + W + '" y1="' + (y0 + k * gap) + '" y2="' + (y0 + k * gap) + '"/>';
    for (var i = 0; i < 16; i++) {
      var cx = 22 + rnd() * (W - 44), cy = 14 + rnd() * (H - 28), a = rnd() * Math.PI, dx = Math.cos(a) * len / 2, dy = Math.sin(a) * len / 2;
      var crosses = Math.floor((cy - dy - y0) / gap) !== Math.floor((cy + dy - y0) / gap);
      out += '<line class="' + (crosses ? "art-x" : "art-n") + '" x1="' + (cx - dx).toFixed(1) + '" y1="' + (cy - dy).toFixed(1) + '" x2="' + (cx + dx).toFixed(1) + '" y2="' + (cy + dy).toFixed(1) + '"/>';
    }
    return out + "</svg>";
  }

  function scopeTip(h) {
    var m = h.scope.measured.length, n = h.scope.not_measured.map(cannotTitle).filter(function (t, i, a) { return a.indexOf(t) === i; });
    return "Took part in " + m + " of " + (m + h.scope.not_measured.filter(function (x) { return !/^scale\//.test(x.scenario); }).length) + " workloads." + (n.length ? "\nCan't run: " + n.join(", ") + "." : "");
  }
  // the control bar of every Results page: the harnesses, the baseline, values or ratio, and the wire API where the open section has more than one. Its state is in the URL.
  function controlBar(I, route, st, sec) {
    var all = I.D.harnesses;
    var chips = '<div class="chips">' + all.map(function (h) {
      return '<button type="button" class="chip h-' + esc(h.colour) + '" aria-pressed="' + (st.hs.indexOf(h) >= 0) + '" data-toggle-list="h" data-value="' + esc(h.slug) + '" data-tip="' + esc(scopeTip(h)) + '">' + dot(h) + esc(shortName(h)) + "</button>";
    }).join("") + "</div>";
    var ratio = !sec || (sec.kind !== "agents" && sec.kind !== "faults");
    var mode = ratio ? seg([["values", "Values"], ["ratio", "Ratio"]], st.mode, function (v) { return 'data-href="' + esc(withParam(route, "v", v === "values" ? "values" : "")) + '"'; }) : "";
    var bases = ratio ? select("base", all.map(function (h) { return [h.is_ref ? "" : h.slug, shortName(h)]; }), st.base.is_ref ? "" : st.base.slug, "Baseline") : "";
    var apis = sec ? secApis(I, sec) : [];
    var apiSel = apis.length ? select("api", apis.map(function (a) { return [a, sec && sec.id === "durable" ? a : apiName(a)]; }), secApi(I, st, sec), sec && sec.id === "durable" ? "Environment" : "Wire API") : "";
    return '<div class="ctlbar">' + chips + '<div class="ctlrow">' + mode + bases + apiSel + "</div></div>";
  }

  function valueTip(I, h, base, cell, c) {
    return shortName(h) + ": " + measureName(I, cell) + "\n" + times(c.ratio) + " " + shortName(base) + "'s result, 95% interval " + ratioStr(c.lo) + " to " + ratioStr(c.hi) +
      "\nmedian " + val(c.med, cell.unit) + " against " + val(c.bmed, cell.unit, c.med) + ", " + plural(c.n, "paired round") + (ok(c.floor) ? "\nnoise floor ±" + pct(c.floor) : "") + (ok(c.p) ? ", paired test p " + pval(c.p) : "") + "\nClick for how it was measured.";
  }
  // a cell's page is the comparison of a harness with Pi; the baseline row of the grid (Pi) opens the first harness that has one
  function cellHref(cell, h, I) {
    var who = h.is_ref ? I.contenders.filter(function (c) { return cell.comparisons[c.id]; })[0] : (cell.comparisons[h.id] ? h : null);
    return who ? link("cell", [cell.slug, who.slug]) : link("metric", [cell.key], { api: cell.api_short === "-" ? "" : cell.api_short });
  }

  // ------------------------------------------------------------------ one metric: what it is, how it is made, every harness
  function timeline(w) {
    return '<div class="timeline"><span class="line"></span>' + w.marks.map(function (m) { return '<span class="mk ' + esc(m[2]) + '" style="left:' + (m[0] * 100).toFixed(0) + '%"><i></i><em>' + esc(m[1]) + "</em></span>"; }).join("") + "</div>";
  }
  function terminal(w) {
    return '<figure class="termfig"><div class="screen">' + w.lines.map(function (l) { return "<div>" + esc(l) + "</div>"; }).join("") + "</div>" + timeline(w) + "<figcaption>What runs, and where the clock starts and stops</figcaption></figure>";
  }
  // bars from zero with the median of each harness at the end of its bar and the 95% interval of that median as a whisker; the dashed line is the baseline's median
  function intervalBars(I, cell, rows, base) {
    var top = Math.max.apply(null, rows.map(function (r) { return Math.max(r.s.median, r.s.ci ? r.s.ci[1] : 0); })) || 1, bs = cell.stats[base.id];
    var out = rows.map(function (r) {
      var h = r.h, s = r.s, v = h === base ? null : versus(I, cell, h, base);
      var tip = shortName(h) + ": median " + val(s.median, cell.unit) + " over " + plural(s.n, "round") + (s.ci ? "\n95% interval of the median " + span(s.ci[0], s.ci[1], cell.unit) : "") +
        "\nmiddle half " + span(s.q1, s.q3, cell.unit) + ", range " + span(s.min, s.max, cell.unit) + (v && v.notcmp ? "\n" + NOT_COMPARED + ": " + v.notcmp : v ? "\n" + times(v.ratio) + " " + shortName(base) : "");
      var chip = h === base ? '<span class="chip-r ruler">baseline</span>' : v && v.notcmp ? '<a class="chip-r nc" href="' + esc(cellHref(cell, h, I)) + '">different work</a>' : v ? '<a class="chip-r" href="' + esc(cellHref(cell, h, I)) + '">' + times(v.ratio) + "</a>" : "";
      return { h: h, f: s.median / top, label: val(s.median, cell.unit), tip: tip, whisker: s.ci ? [s.ci[0] / top, s.ci[1] / top] : null, chip: chip };
    });
    return barRows(out, { base: bs ? bs.median / top : null });
  }
  function viewMetric(ctx, I, route) {
    var mt = I.metric[route.args[0]];
    if (!mt) return notFound(I);
    var st = stateOf(I, route), base = st.base, D = I.D;
    var apis = I.apis.filter(function (a) { return mt.apis.indexOf(a) >= 0; });   // the order of Compare
    var envs = I.envs.filter(function (e) { return mt.apis.indexOf(e) >= 0; }), opts = envs.length ? (mt.apis.indexOf("-") >= 0 ? ["native"] : []).concat(envs) : apis;   // an environment is chosen like an API, and each is its own cell
    var api = envs.length ? (opts.indexOf(route.params.api) >= 0 ? route.params.api : opts[0]) : mt.apis.indexOf("-") >= 0 ? "-" : (apis.indexOf(st.api) >= 0 ? st.api : apis[0]);
    var cell = I.cellOf[mt.key][api === "native" ? "-" : api], w = D.workloads[mt.workload] || {};
    var rows = D.harnesses.filter(function (h) { return cell.stats[h.id]; }).map(function (h) { return { h: h, s: cell.stats[h.id] }; });
    var absent = D.harnesses.filter(function (h) { return !cell.stats[h.id]; });
    var apiSeg = opts.length > 1 ? seg(opts.map(function (a) { return [a, envs.length ? a : apiName(a)]; }), api, function (v) { return 'data-href="' + esc(withParam(route, "api", v)) + '"'; }) : "";
    var baseSel = select("base", D.harnesses.map(function (h) { return [h.is_ref ? "" : h.slug, shortName(h)]; }), base.is_ref ? "" : base.slug, "Ratio to");
    var head = ["Harness", { h: "Rounds", num: true }, { h: "Median", num: true }, { h: "95% interval of the median", num: true }, { h: term(I, "iqr", "Middle half"), num: true }, { h: "Range", num: true }, { h: "Ratio to " + esc(shortName(base)), num: true }];
    var trs = rows.map(function (r) {
      var v = r.h === base ? null : versus(I, cell, r.h, base);
      return [td(esc(r.h.name)), td(String(r.s.n), r.s.n), td(esc(val(r.s.median, cell.unit)), r.s.median), td(r.s.ci ? esc(span(r.s.ci[0], r.s.ci[1], cell.unit)) : "n/a", r.s.ci ? r.s.ci[0] : null),
        td(esc(span(r.s.q1, r.s.q3, cell.unit)), r.s.q1), td(esc(span(r.s.min, r.s.max, cell.unit)), r.s.min),
        td(v && v.notcmp ? NOT_COMPARED : v ? '<a href="' + esc(cellHref(cell, r.h, I)) + '">' + times(v.ratio) + "</a>" : r.h === base ? "1.00×" : "n/a", v && !v.notcmp ? v.ratio : r.h === base ? 1 : null)];
    });
    var series = rows.map(function (r) { return { name: r.h.name, colour: r.h.colour, values: cell.values[r.h.id] }; });
    var n = Math.max.apply(null, series.map(function (s) { return s.values.length; })), roundRows = [];
    for (var i = 0; i < n; i++) roundRows.push([td(String(i + 1), i + 1)].concat(series.map(function (s) { return td(i < s.values.length ? esc(val(s.values[i], cell.unit)) : "", s.values[i]); })));
    var roundTable = table(ctx, "rounds-" + mt.key, [{ h: "Round", num: true }].concat(series.map(function (s) { return { h: esc(s.name), num: true }; })), roundRows);
    var chart = card(ctx, { id: "metric-" + mt.key, title: "Every harness", tools: provBadge(cellProv(I, cell)) + apiSeg + baseSel,
      sub: "The median of each harness, with the 95% interval of that median as a line. The dashed line is " + esc(shortName(base)) + ".",
      chart: intervalBars(I, cell, rows, base), table: table(ctx, "metric-" + mt.key, head, trs),
      foot: absent.length ? "No value: " + absent.map(function (h) { var o = otherApi(I, mt.key, h, api); return o ? '<a href="' + esc(withParam(route, "api", o)) + '" data-tip="' + esc(otherTip(h, o)) + '">' + esc(shortName(h) + " (" + apiShort(o) + ")") + "</a>" : '<span data-tip="' + esc(naTip(h, cell.na[h.id])) + '" tabindex="0">' + esc(shortName(h)) + "</span>"; }).join(", ") + "." : "" });
    var formula = '<table class="kv"><tr><th>Unit</th><td>' + esc(unitOf(mt.unit)) + "</td></tr><tr><th>The task</th><td><code>" + esc(mt.scenario) + "</code> · " + esc(w.title || "") + "</td></tr><tr><th>The metric</th><td><code>" + esc(mt.metric) + "</code></td></tr>" +
      (I.multiApi && api !== "-" && !envs.length ? "<tr><th>Wire API</th><td>" + esc(apiName(api)) + "</td></tr>" : "") + (cell.env ? "<tr><th>Environment</th><td>" + esc(cell.env) + "</td></tr>" : "") + "</table>" +
      (mt.tex ? '<div class="eqrow"><span class="lbl">One sample</span><div class="eq">' + mt.tex + "</div></div>" : "") +
      '<div class="eqrow"><span class="lbl">Each value</span><div class="eq">' + D.tex.median + "</div></div>" +
      '<div class="eqrow"><span class="lbl">Ratio</span><div class="eq">' + D.tex.ratio + "</div></div>" +
      ((cell.caveats || []).length ? '<div class="caveat" role="note"><b>Measurement caveat</b>' + cell.caveats.map(function (c) { return "<p>" + esc(c) + "</p>"; }).join("") + "</div>" : "");
    var cw = chartWidth(ctx, ctx.width > 860 ? 2 : 1);
    return '<p class="crumbs">' + resultsCrumb(I, mt.key) + " › " + esc(mt.title) + "</p>" +
      '<div class="pagehead"><h1>' + esc(mt.title) + ": " + esc(mt.word) + '</h1><p class="lede">' + esc(mt.about) + "</p></div>" + chart +
      '<p class="muted note">Why it matters, and what this task does not show: ' + docLink(I, "WHAT-WE-MEASURE", "What we measure") + ".</p>" +
      '<details class="more"><summary>What runs, and how this metric is made</summary>' + (w.lines ? '<div class="card">' + terminal(w) + "</div>" : "") + '<section class="card" id="formula">' + formula + "</section></details>" +
      '<details class="more"><summary>Every round of every harness</summary><div class="grid2">' +
      card(ctx, { id: "lines-" + mt.key, title: "Each round, in the order it ran", sub: "A line that goes up or down shows a change during the run.", chart: linesChart(series, { width: cw, unit: cell.unit, label: "every round of " + mt.word }), table: roundTable }) +
      card(ctx, { id: "strip-" + mt.key, title: "Spread of the rounds", sub: "Each dot is one round, the tall mark the median.", chart: stripChart(series, { width: cw, unit: cell.unit }), table: "" }) + "</div></details>";
  }

  // ------------------------------------------------------------------ one harness: every metric as a small bar against the baseline, its build, what it cannot run
  var PIN_FIRST = ["version", "version_line", "relation", "install_method", "executable_sha256", "artifact_sha256", "install_tree_sha256", "manifest_sha256", "package_lock_sha256", "integrity", "commit", "tree", "source_url", "package", "platform"];
  // ---- what a project says about itself: the head of its own README, stored at a pinned ref by tools/profiles_refresh.py (profiles/<project>.toml). Nothing is fetched here.
  function sourceLabel(url) { var m = /\/([^\/?#]+\.(?:md|html|txt))(?:[?#].*)?$/.exec(url); var host = (/^https:\/\/([^\/]+)/.exec(url) || [])[1] || url; return (m ? m[1] + " at " : "") + host; }
  function from(url, retrieved) { return '<cite>from <a href="' + esc(url) + '">' + esc(sourceLabel(url)) + "</a>" + (retrieved ? ", read " + esc(retrieved) : "") + "</cite>"; }
  var LINK_NAMES = [["home", "Home"], ["repo", "Code"], ["docs", "Docs"]];
  var MORE_LINKS = [["releases", "Releases"], ["changelog", "Changelog"], ["issues", "Issues"], ["benchmarks", "Their benchmarks"]];
  function linkList(links, names) { return names.filter(function (n) { return links && links[n[0]]; }).map(function (n) { return '<a href="' + esc(links[n[0]]) + '">' + n[1] + "</a>"; }).join(" · "); }
  function linksRow(links) { return '<p class="links">' + linkList(links, LINK_NAMES) + "</p>"; }
  function moreLinks(links) { var t = linkList(links, MORE_LINKS); return t ? '<p class="links">' + t + "</p>" : ""; }
  function versionName(h) { var v = String(h.version || "").split("+")[0]; return !v || h.name.indexOf(v) >= 0 ? shortName(h) : shortName(h) + " " + h.version; }
  // the versions measured here, as small chips; the harness being looked at is marked
  function versionChips(I, prof, cur) {
    return '<p class="vers">' + I.D.harnesses.filter(function (x) { return prof ? x.profile === prof.slug : x === cur; }).map(function (x) {
      return '<a class="vchip' + (x === cur ? " cur" : "") + '" href="' + esc(link("harness", [x.slug])) + '">' + dot(x) + esc(versionName(x)) + "</a>";
    }).join("") + "</p>";
  }
  function licenceLine(prof) { return prof.links && prof.links.licence ? '<a href="' + esc(prof.links.licence) + '">' + esc(prof.licence) + "</a>" : esc(prof.licence); }
  function makerLine(prof) { return '<p class="meta">By <a href="' + esc(prof.maker_url) + '">' + esc(prof.maker) + "</a> · " + licenceLine(prof) + (prof.licence_note ? ". " + esc(prof.licence_note) : "") + "</p>"; }
  // the first words of the README head, whole paragraphs where they fit and the last one cut at a word with an ellipsis
  function clipHead(paras, max) {
    var out = [], left = max;
    (paras || []).forEach(function (p) {
      if (left <= 0) return;
      var words = String(p).split(/\s+/).filter(Boolean);
      if (words.length <= left) { out.push(words.join(" ")); left -= words.length; }
      else { out.push(words.slice(0, left).join(" ").replace(/[\s,;:.\-]+$/, "") + "…"); left = 0; }
    });
    return out;
  }
  function refShort(ref) { return /^[0-9a-f]{40}$/.test(ref) ? ref.slice(0, 7) : ref; }
  function headText(prof) {
    var r = prof.readme;
    return '<div class="phead">' + (r ? clipHead(r.head, 60) : [prof.tagline]).map(function (p) { return '<p class="their-words raw">' + esc(p) + "</p>"; }).join("") + "</div>";
  }
  function sourceLine(prof) {
    var r = prof.readme;
    return '<p class="src">' + (r ? 'README at <a href="' + esc(r.url) + '">' + esc(r.repo) + "@" + esc(refShort(r.ref)) + "</a>, read " + esc(r.retrieved) : from(prof.tagline_source, prof.retrieved)) + "</p>";
  }
  // the one square mark of a card or a page head, the same tile for every project: its mark (an SVG fitted in the tile, a cropped picture filling it) or, without one, its initials in the site's mono face
  function monogramOf(text) { var w = String(text || "").replace(/[^A-Za-z0-9]+/g, " ").trim().split(" "); return w.length > 1 ? w[0].charAt(0) + w[1].charAt(0) : w[0].slice(0, 2); }
  function markOf(prof, name, href) {
    var has = prof && prof.mark, kind = has ? (prof.mark_pixel ? "fill" : "fit") : "mono", label = (prof && prof.project) || name;
    var inner = has ? '<img src="' + esc(prof.mark) + '" alt="' + esc(prof.mark_alt || label + " logo") + '"' + (prof.mark_pixel ? ' class="px"' : "") + ">" : '<span aria-hidden="true">' + esc((prof && prof.monogram) || monogramOf(label)) + "</span>";
    return '<a class="pmark ' + kind + '"' + (prof && prof.mark_bg ? ' style="--mark-bg:' + esc(prof.mark_bg) + '"' : "") + ' href="' + esc(href) + '"' + (has ? "" : ' aria-label="' + esc(label) + '"') + ">" + inner + "</a>";
  }
  // the picture the README opens with (a banner, a splash screen, a demo), on the harness page only
  function readmeFigure(prof) {
    if (!prof || !prof.logo) return "";
    return '<figure class="pfig"><figcaption>From its README</figcaption><a href="' + esc(prof.links.repo || prof.links.home) + '"><img src="' + esc(prof.logo) + '" alt="' + esc(prof.logo_alt || prof.project + " README picture") + '"></a><p class="src">' + from(prof.logo_source, prof.retrieved) + "</p></figure>";
  }
  var NOT_YET = '<p class="vers"><span class="vchip off">Not measured yet</span></p>';
  // a project's own title, with a dash between its parts written as a colon: the site's own text has no em dash
  function plainTitle(t) { return String(t).replace(/\s+[\u2014\u2013]\s+/g, ": "); }
  function profileCard(I, prof, first) {
    var r = prof.readme, href = link("harness", [first.slug]);
    return '<article class="card prof"><div class="phd1">' + markOf(prof, prof.project, href) + '<h2 class="ptitle"><a href="' + esc(href) + '">' + esc(plainTitle((r && r.title) || prof.project)) + "</a></h2></div>" +
      headText(prof) + sourceLine(prof) + (first.unmeasured ? NOT_YET : versionChips(I, prof, null)) + makerLine(prof) + linksRow(prof.links) + "</article>";
  }
  function bareCard(I, h) {
    var home = (h.command || {}).homepage, href = link("harness", [h.slug]);
    return '<article class="card prof"><div class="phd1">' + markOf(null, h.name, href) + '<h2 class="ptitle"><a href="' + esc(href) + '">' + esc(h.name) + "</a></h2></div>" +
      '<div class="phead"><p class="muted">No profile yet.' + (home ? ' Home: <a href="' + esc(home) + '">' + esc(home) + "</a>" : "") + "</p></div>" + versionChips(I, null, h) + "</article>";
  }
  // the head of the harness page: the same README head as its card
  function harnessHead(I, h, prof) {
    if (!prof) {
      var home = (h.command || {}).homepage || docsOf(h);
      return '<div class="pagehead phd"><div class="phd1">' + markOf(null, h.name, home || "#") + '<h1>' + esc(h.name) + '</h1></div><p class="meta">No profile yet.' + (home ? ' Home: <a href="' + esc(home) + '">' + esc(home) + "</a>" : "") + "</p>" + versionChips(I, null, h) + "</div>";
    }
    var r = prof.readme;
    return '<div class="pagehead phd"><div class="phd1">' + markOf(prof, prof.project, prof.links.repo || prof.links.home || "#") + "<h1>" + esc(prof.project) + "</h1></div>" + (r && r.title && r.title.toLowerCase() !== prof.project.toLowerCase() ? '<p class="rtitle">' + esc(plainTitle(r.title)) + "</p>" : "") +
      headText(prof) + sourceLine(prof) + (h.unmeasured ? NOT_YET : versionChips(I, prof, h)) + makerLine(prof) + linksRow(prof.links) + "</div>" + readmeFigure(prof);
  }

  // the index: one card for each project measured here, in the order of the site's harnesses, then the projects with a profile and an arm that no loaded run has data for yet
  function viewHarnesses(ctx, I) {
    var done = {}, cards = [];
    I.D.harnesses.concat(I.unmeasured).forEach(function (h) {
      var prof = h.profile ? I.profile[h.profile] : null;
      if (prof) { if (!done[prof.slug]) { done[prof.slug] = 1; cards.push(profileCard(I, prof, h)); } }
      else cards.push(bareCard(I, h));
    });
    return '<div class="pagehead"><h1>Harnesses</h1><p class="lede">The projects measured here, as the top of their own README puts it.</p></div><div class="roster">' + cards.join("") + "</div>";
  }
  // a harness with a profile and an arm but no data in the loaded runs: its page says what its manifest can run and why it cannot run the rest. No number is drawn for it.
  function viewUnmeasured(ctx, I, h) {
    var prof = h.profile ? I.profile[h.profile] : null, groups = [];
    h.scope.cannot.forEach(function (c) {
      var g = groups.filter(function (x) { return x.reason === c.reason; })[0];
      if (!g) groups.push({ reason: c.reason, titles: [c.title] }); else if (g.titles.indexOf(c.title) < 0) g.titles.push(c.title);
    });
    var can = h.scope.runs.length ? '<p class="scope"><b>It can run</b> ' + h.scope.runs.map(esc).join(", ") + ".</p>" : '<p class="scope"><b>It can run</b> none of the planned workloads.</p>';
    var cannot = groups.length ? '<h3 class="sech2">Can\'t run (' + groups.reduce(function (n, g) { return n + g.titles.length; }, 0) + ")</h3><ul class=\"cannot\">" + groups.map(function (g) {
      var i = g.reason.indexOf(": ");
      return "<li><b>" + g.titles.map(esc).join(" · ") + "</b><br>" + esc(i > 0 ? g.reason.slice(0, i) : g.reason) + (i > 0 ? '<br><small class="muted">' + esc(g.reason.slice(i + 2).replace(/`/g, "")) + "</small>" : "") + "</li>";
    }).join("") + "</ul>" : "";
    var fams = h.families || [], fam = fams.length ? '<p class="scope">It is in the launch rerun\'s ' + fams.map(esc).join(" and ") + (fams.length > 1 ? " families." : " family.") + "</p>" : "";
    var fix = prof ? "Is something here wrong or out of date? Edit <code>" + esc(prof.file) + "</code> or open an issue." : "";
    return '<p class="crumbs"><a href="' + link("harnesses") + '">Harnesses</a> › ' + esc(prof ? prof.project : h.name) + "</p>" + harnessHead(I, h, prof) +
      card(ctx, { id: "scope-" + h.slug, title: "Scope", body: can + cannot + fam }) + (fix ? '<p class="muted fixit"><a href="' + esc(docHref(I.doc.CONTRIBUTING || { slug: "CONTRIBUTING" })) + '">' + fix + "</a></p>" : "");
  }

  // a workload it did not run: the probes of one swarm search (or the rungs of one earlier ladder) are one workload here, and the same search with the ten extensions is another
  function cannotTitle(c) { var m = /^scale\/(agents|print)-(\d+|limit|ext10)$/.exec(c.scenario); return m ? "Agent swarming, " + (m[1] === "agents" ? "RPC" : "print mode") + (m[2] === "ext10" ? ", 10 extensions" : "") : c.title; }
  // which workloads the harness took part in, and for the others the manifest's reason, one entry per title; the swarm searches count as workloads of their own
  function scopeOf(I, h) {
    var measured = h.scope.measured.map(function (m) { return m.title; });
    var S = scaleOf(I);
    if (S) ["rpc", "print", "rpc-ext10", "print-ext10"].forEach(function (k) {
      var t = cannotTitle({ scenario: "scale/" + (kindBase(k) === "rpc" ? "agents" : "print") + (k === kindBase(k) ? "-limit" : "-ext10") });
      if (S.envelopes.some(function (e) { var a = e.kinds[k] && e.kinds[k].arms[h.id]; return a && a.rungs && a.rungs.length; })) measured.push(t);
    });
    var groups = [];
    h.scope.not_measured.forEach(function (c) {
      var t = cannotTitle(c);
      if (measured.indexOf(t) < 0 && !groups.some(function (x) { return x.title === t; })) groups.push({ title: t, reason: c.reason });
    });
    return { measured: measured, not: groups };
  }
  function scopeCard(ctx, I, h) {
    var sc = scopeOf(I, h), measured = sc.measured, groups = sc.not;
    var not = groups.length ? '<details class="more"><summary>Not measured (' + groups.length + ')</summary><ul class="cannot">' + groups.map(function (g) {
      var i = g.reason.indexOf(": ");
      return "<li><b>" + esc(g.title) + "</b><br>" + esc(i > 0 ? g.reason.slice(0, i) : g.reason) + (i > 0 ? '<br><small class="muted">' + esc(g.reason.slice(i + 2).replace(/`/g, "")) + "</small>" : "") + "</li>";
    }).join("") + "</ul></details>" : "";
    var dv = (h.divergences || []).length ? '<details class="more"><summary>Different work (' + h.divergences.length + ')</summary><ul class="cannot">' + h.divergences.map(function (d) {
      var src = /^https?:/.test(d.source || "") ? '<a href="' + esc(d.source) + '">' + esc(d.source) + "</a>" : "<code>" + esc(d.source || "") + "</code>";
      return "<li><b>" + esc((d.workloads || []).join(", ")) + "</b>" + ((d.metrics || []).length ? " <small>" + esc(d.metrics.join(", ")) + "</small>" : "") + "<br>" + esc(d.reason || "") + '<br><small class="muted">Source: ' + src + "</small></li>";
    }).join("") + "</ul><p class=\"muted\">These cells show the median of " + esc(shortName(h)) + ", labelled \"" + NOT_COMPARED + "\".</p></details>" : "";
    return card(ctx, { id: "scope-" + h.slug, title: "Scope", body: '<p class="scope"><b>Measured in</b> ' + (measured.length ? measured.map(esc).join(", ") : "no workload") + ".</p>" + not + dv });
  }
  // the runtime-tuning variables Buffon or the manifest set, and the known ones left at the harness's own default
  function settingsLine(rs) {
    if (!rs) return null;
    var vars = Object.keys(rs.env || {}).sort();
    return { set: vars.map(function (k) { return "<code>" + esc(k + "=" + rs.env[k]) + "</code> <small>" + esc((rs.source || {})[k] || "") + "</small>"; }), left: (rs.left_default || []).map(function (k) { return "<code>" + esc(k) + "</code>"; }) };
  }
  function runtimeOf(h) {
    var r = settingsLine(h.runtime_settings);
    if (!r) return '<p class="muted">This run did not record runtime settings for ' + esc(shortName(h)) + ".</p>";
    return '<table class="kv"><tr><th>Set</th><td>' + (r.set.join("<br>") || "none") + "</td></tr><tr><th>Left at the default</th><td>" + (r.left.join(", ") || "none") + "</td></tr></table>";
  }
  function viewHarness(ctx, I, route) {
    var h = I.bySlug[route.args[0]];
    if (!h && I.unBySlug[route.args[0]]) return viewUnmeasured(ctx, I, I.unBySlug[route.args[0]]);
    if (!h) return notFound(I);
    var st = stateOf(I, route), base = st.base, D = I.D, isBase = h === base, prof = h.profile ? I.profile[h.profile] : null;
    var items = [];
    D.metrics.forEach(function (mt) {
      var cell = metricCell(I, mt.key, st.api);
      if (cell && cell.stats[h.id]) items.push({ mt: mt, cell: cell, s: cell.stats[h.id], v: isBase ? null : versus(I, cell, h, base) });
    });
    var rt = function (x) { return x.v && !x.v.notcmp ? x.v.ratio : 0; };
    items.sort(function (x, y) { return rt(y) - rt(x); });   // the measures where it costs more first; different work goes last
    var span2 = Math.max(2, Math.min(50, Math.max.apply(null, items.map(function (x) { return rt(x) ? Math.max(x.v.ratio, 1 / x.v.ratio) : 1; }))));
    var pos = function (r) { return 50 + 50 * Math.log(Math.max(1 / span2, Math.min(span2, r))) / Math.log(span2); };
    var bars = items.map(function (x) {
      var nc = x.v && x.v.notcmp;
      var tip = nc ? shortName(h) + ": " + measureName(I, x.cell) + "\nmedian " + val(x.s.median, x.cell.unit) + " over " + plural(x.s.n, "round") + "\n" + NOT_COMPARED + ": " + nc : x.v ? valueTip(I, h, base, x.cell, x.v) : shortName(h) + ": median " + val(x.s.median, x.cell.unit) + " over " + plural(x.s.n, "round") + (isBase ? "\nThis is the baseline." : "");
      var bar = x.v && !nc ? '<i class="hbar" style="left:' + Math.min(pos(x.v.ratio), 50).toFixed(2) + "%;width:" + Math.max(0.5, Math.abs(pos(x.v.ratio) - 50)).toFixed(2) + '%"></i>' : "";
      return '<a class="hrow" href="' + esc(cellHref(x.cell, h, I)) + '" data-tip="' + esc(tip) + '"><span class="hl">' + esc(x.mt.title + ": " + x.mt.word) + '</span><span class="ht"><i class="hz"></i>' + bar + '</span><span class="hvv"><b>' +
        (nc ? "not compared" : x.v ? times(x.v.ratio) : isBase ? "" : "n/a") + "</b> <small>" + esc(val(x.s.median, x.cell.unit)) + "</small> " + provBadge(cellProv(I, x.cell)) + "</span></a>";
    }).join("");
    var axis = isBase ? '<p class="hax">This is the baseline, so there is nothing to compare. Pick another baseline to see bars.</p>' :
      '<div class="hrow axis"><span class="hl"></span><span class="hax2"><span>◀ less than ' + esc(shortName(base)) + " (" + ratioStr(1 / span2) + '×)</span><span>more (' + ratioStr(span2) + "×) ▶</span></span><span></span></div>";
    var trs = items.map(function (x) {
      return [td(esc(x.mt.title)), td(esc(cap(x.mt.word))), td(esc(val(x.s.median, x.cell.unit)), x.s.median), td(rt(x) ? '<a href="' + esc(cellHref(x.cell, h, I)) + '">' + ratioStr(x.v.ratio) + "</a>" : x.v ? NOT_COMPARED : isBase ? "1" : "n/a", rt(x) ? x.v.ratio : null),
        td(rt(x) ? ratioStr(x.v.lo) + " to " + ratioStr(x.v.hi) : "n/a", rt(x) ? x.v.lo : null), td(String(x.s.n), x.s.n)];
    });
    var baseSel = select("base", D.harnesses.map(function (b) { return [b.is_ref ? "" : b.slug, shortName(b)]; }), base.is_ref ? "" : base.slug, "Against");
    var apiSeg = I.multiApi ? seg(I.apis.map(function (a) { return [a, apiName(a)]; }), st.api, function (v) { return 'data-href="' + esc(withParam(route, "api", v === I.defaultApi ? "" : v)) + '"'; }) : "";
    var every = card(ctx, { id: "bars-" + h.slug, title: "Every measure against " + esc(shortName(base)),
      sub: "The ratio of each median of " + esc(shortName(h)) + " to the median of " + esc(shortName(base)) + ", on a log scale, the measures where it costs more first. The number at the right is the median.",
      chart: items.length ? '<div class="hbars h-' + esc(h.colour) + '">' + axis + bars + "</div>" : '<p class="empty">' + (function () {
        var o = I.apis.filter(function (a) { return a !== st.api && D.cells.some(function (c) { return c.api_short === a && c.stats[h.id]; }); })[0];
        return o ? '<a href="' + esc(withParam(route, "api", o)) + '" data-tip="' + esc(otherTip(h, o)) + '">Measured on the ' + esc(apiName(o)) + "</a>, not on the " + esc(apiName(st.api)) + "." : "This harness has no value with the " + esc(apiName(st.api)) + ".";
      })() + "</p>",
      table: table(ctx, "bars-" + h.slug, ["Workload", "Metric", { h: "Median", num: true }, { h: "Ratio to " + esc(shortName(base)), num: true }, { h: "95% interval of the ratio", num: true }, { h: "Rounds", num: true }], trs) });
    var keys = Object.keys(h.pins || {}).sort(function (a, b) { var x = PIN_FIRST.indexOf(a), y = PIN_FIRST.indexOf(b); return (x < 0 ? 99 : x) - (y < 0 ? 99 : y) || a.localeCompare(b); });
    var notes = (h.command || {}).notes;
    var ran = card(ctx, { id: "ran-" + h.slug, title: "How it ran here",
      body: '<p class="meta">Version <code>' + esc(h.version || "not recorded") + "</code>" + (h.pins && h.pins.install_method ? ", installed by " + esc(String(h.pins.install_method).replace(/_/g, " ")) : "") + ".</p>" +
        (notes ? '<p class="notes raw">' + esc(notes).replace(/`([^`]+)`/g, "<code>$1</code>") + "</p>" : "") + (h.caveat ? '<p class="notes raw">' + esc(h.caveat) + "</p>" : "") +
        (h.terms ? '<h3 class="sech2">Vendor terms</h3><p class="muted">Buffon installs this harness from its vendor at run time. It ran under the vendor\'s terms, which the operator accepted:</p><p class="their-words raw terms">' + esc(h.terms) + "</p>" : "") +
        '<h3 class="sech2">Runtime settings</h3>' + runtimeOf(h) + '<details class="more"><summary>Version, pin and checksum</summary><table class="kv">' + keys.map(function (k) { return "<tr><th>" + esc(k.replace(/_/g, " ")) + "</th><td><code>" + esc(h.pins[k]) + "</code></td></tr>"; }).join("") + "</table></details>" +
        (prof ? moreLinks(prof.links) : "") });
    var scope = scopeCard(ctx, I, h);
    var strip = sectionStrip(ctx, I, st, h, baseSel + apiSeg);
    var fix = prof ? "Is something here wrong or out of date? Edit <code>" + esc(prof.file) + "</code> or open an issue." : "No profile yet? Add <code>profiles/" + esc(h.slug) + ".toml</code> or open an issue.";
    return '<p class="crumbs"><a href="' + link("harnesses") + '">Harnesses</a> › ' + esc(prof ? prof.project : h.name) + (prof && D.harnesses.some(function (x) { return x !== h && x.profile === prof.slug; }) ? " › " + esc(versionName(h)) : "") + "</p>" +
      harnessHead(I, h, prof, true) + strip + scope + ran + '<details class="more"><summary>Every measure</summary>' + every + "</details>" +
      '<p class="muted fixit"><a href="' + esc(docHref(I.doc.CONTRIBUTING || { slug: "CONTRIBUTING" })) + '">' + fix + "</a></p>";
  }
  function withBase(route) { var p = {}; if (route.params.base) p.base = route.params.base; if (route.params.api) p.api = route.params.api; return p; }

  // ------------------------------------------------------------------ what runs
  function modeOf(scenario) {
    if (scenario === "overhead/version") return "version";
    if (/^overhead\/(rpc|long-session)/.test(scenario)) return "rpc";
    if (/^longsession\/resume/.test(scenario)) return "rpc_resume";
    if (/^longsession\/grow/.test(scenario)) return "rpc_session";
    if (/^overhead\/pty|^streaming\/tui/.test(scenario)) return "pty";
    return "print";
  }
  function commandLine(I, h, cell) {
    var cmd = h.command, mode = modeOf(cell.scenario);
    var argv = cmd && (cmd.modes[mode] || cmd.modes[mode.split("_")[0]]);
    if (!argv) return null;
    var ext = /ext(\d+)/.exec(cell.scenario);
    var sub = { model: "mock", prompt: '"' + (/^overhead\//.test(cell.scenario) ? I.D.meta.prompt : "…") + '"', extensions: ext ? "<" + ext[1] + " extensions>" : "", session: "saved-session.jsonl", session_dir: "sessions/" };
    return "$ " + cmd.bin + " " + argv.map(function (a) { return a.replace(/\{(\w+)\}/g, function (all, k) { return k in sub ? sub[k] : all; }); }).filter(Boolean).join(" ");
  }
  function whatRuns(I, h, cell) {
    var w = I.D.workloads[cell.workload] || {}, mine = commandLine(I, h, cell), pi = commandLine(I, I.ref, cell);
    if (!mine || !pi) return terminal(w);
    var mode = modeOf(cell.scenario);
    var pane = function (who, line) {
      var out = mode === "version" ? [who.version || ""] : /^overhead\/print(-ext\d+)?$/.test(cell.scenario) ? [I.D.meta.reply] : w.lines.slice(1);
      return '<figure class="termfig"><figcaption class="who">' + dot(who) + esc(shortName(who)) + (docsOf(who) ? ' <a class="docs" href="' + esc(docsOf(who)) + '">docs ↗</a>' : "") + '</figcaption><div class="screen wrap">' + [line].concat(out).map(function (l) { return "<div>" + esc(l) + "</div>"; }).join("") + "</div></figure>";
    };
    return '<div class="runs2">' + pane(I.ref, pi) + pane(h, mine) + "</div>" + timeline(w) +
      '<p class="muted">Both commands come from <code>arms/</code>. The marks show where the clock starts and stops.</p>';
  }

  // ------------------------------------------------------------------ how a number is made
  function equivalenceWord(eq) { var m = "±" + pct(eq.margin); return eq.equivalent ? "within " + m : "not shown to be within " + m; }
  function equivalenceRows(I, c) {
    var eq = c.equivalence;
    if (!eq) return [];
    return [[term(I, "equivalence-margin", "Equivalence margin"), "±" + pct(eq.margin)], ["90% " + term(I, "ci", "interval") + " of the ratio", ratioStr(eq.low) + " to " + ratioStr(eq.high)], ["Result", esc(equivalenceWord(eq))]];
  }
  // a cell where the harness did different work: its own median, the reason, no ratio, no tests
  function viewNotCompared(ctx, I, cell, h, c) {
    var w = I.D.workloads[cell.workload] || {}, s = cell.stats[h.id], ds = divergencesOf(h, cell);
    var src = ds.map(function (d) { return /^https?:/.test(d.source || "") ? '<a href="' + esc(d.source) + '">' + esc(d.source) + "</a>" : "<code>" + esc(d.source || "") + "</code>"; }).join(", ");
    var facts = '<table class="kv facts"><tr><th>' + term(I, "different-work", "Status") + "</th><td>" + esc(NOT_COMPARED) + "</td></tr><tr><th>Reason</th><td>" + esc(c.not_compared) + "</td></tr>" + (src ? "<tr><th>Source</th><td>" + src + "</td></tr>" : "") +
      "<tr><th>Rounds</th><td>" + (s ? s.n : 0) + "</td></tr></table>";
    var p = parts(c.arm_median, cell.unit);
    var chart = linesChart([{ name: shortName(h), colour: h.colour, values: cell.values[h.id] || [] }], { width: chartWidth(ctx, 1) - 48, unit: cell.unit });
    return '<p class="crumbs">' + resultsCrumb(I, cell.key) + ' › <a href="' + link("harness", [h.slug]) + '">' + esc(shortName(h)) + '</a> › <a href="' + link("metric", [cell.key], cell.api_short === "-" ? {} : { api: cell.api_short }) + '">' + esc(w.title || cell.scenario) + "</a> › " + esc(cell.metric_word) + "</p>" +
      '<div class="answer h-' + esc(h.colour) + '"><div class="big">' + esc(p[0]) + "<small>" + esc(p[1]) + "</small></div><div><h1>" + esc(w.title || cell.scenario) + ": " + esc(cell.metric_word) + "</h1><p>" + esc(shortName(h)) + ": <b>" + esc(val(c.arm_median, cell.unit)) + "</b>, the median of " + plural(s ? s.n : 0, "round") +
      ". " + esc(NOT_COMPARED) + ". " + esc(cap(c.not_compared)) + '.</p><p class="meta">' + (cell.api_short !== "-" ? esc(API_NAME[cell.api_short] || cell.api_short) + " · " : "") + 'run <a href="' + link("method", ["runs"]) + '">' + esc(cell.run) + "</a> " + provBadge(cellProv(I, cell)) + "</p></div></div>" +
      '<div class="grid2">' + card(ctx, { id: "facts", title: "Why there is no ratio", body: facts }) +
      card(ctx, { id: "rerun", title: term(I, "rerun", "Measure it again"), body: '<pre class="cmd" id="cmd">' + esc(cell.rerun) + '</pre><button type="button" class="btn" data-copy="#cmd">Copy command</button><p class="files"><a href="' + link("method", ["runs"]) + '">Data files</a></p>' }) + "</div>" +
      '<details class="more"><summary>The rounds of ' + esc(shortName(h)) + "</summary>" + card(ctx, { id: "own-rounds", title: "Each round, in the order it ran", chart: chart }) + "</details>";
  }
  function viewCell(ctx, I, route) {
    var cell = I.cellBySlug[route.args[0]], h = I.bySlug[route.args[1]];
    if (!cell || !h || !cell.comparisons[h.id]) return notFound(I);
    var c = cell.comparisons[h.id], tex = I.D.tex;
    if (c.not_compared) return viewNotCompared(ctx, I, cell, h, c);
    var step = function (n, title, text, extra) { return '<section class="card step"><div class="sn">' + n + '</div><div class="sb"><h2>' + esc(title) + "</h2><p>" + text + "</p>" + (extra || "") + "</div></section>"; };
    var nums = function (rows) { return '<table class="kv calc">' + rows.map(function (r) { return "<tr><th>" + r[0] + "</th><td>" + r[1] + "</td></tr>"; }).join("") + "</table>"; };
    var refName = shortName(I.ref);
    var facts = '<table class="kv facts">' + [
      ["95% " + term(I, "ci", "interval"), ratioStr(c.ci95[0]) + " to " + ratioStr(c.ci95[1])],
      [term(I, "aa-floor", "Noise floor"), ok(c.floor_log) ? "±" + pct(c.floor) : "not measured"]].concat(equivalenceRows(I, c)).map(function (r) { return "<tr><th>" + r[0] + "</th><td>" + r[1] + "</td></tr>"; }).join("") + "</table>";
    var steps = step(1, "The rounds", "In each " + term(I, "round", "round") + ", both harnesses do the task once. The order changes in each round. Thus a slow moment on the machine affects both. The first round is a " + term(I, "warm-up", "warm-up") + " and does not count.",
      linesChart([{ name: shortName(h), colour: h.colour, values: c.x }, { name: refName, colour: I.ref.colour, values: c.y }], { width: chartWidth(ctx, 1) - 48, unit: cell.unit }));
    steps += step(2, "The ratio", "The ratio is the median of the harness divided by the median of " + esc(refName) + ". Both medians use the same rounds.", '<div class="eq">' + tex.ratio + "</div>");
    if (c.hist && c.hist.length) steps += step(3, "The interval", "The rounds are sampled again " + (c.resamples || 0).toLocaleString("en-US") + " times, and the ratio is calculated each time. The middle 95% of these ratios is the 95% interval.",
      '<div class="eq">' + tex.interval + "</div>" + histChart(c.hist, c, { width: chartWidth(ctx, 1) - 48 }));
    if (ok(c.floor_log)) steps += step(4, "The noise floor", "Each harness also runs against a copy of itself. The " + term(I, "aa-floor", "noise floor") + " is the larger of the two gaps between copies.",
      '<div class="eq">' + tex.floor + "</div>" + nums([[esc(refName) + " against its copy", sig((c.aa_floor || {})[I.ref.id])], [esc(shortName(h)) + " against its copy", sig((c.aa_floor || {})[h.id])]]));
    steps += step(ok(c.floor_log) ? 5 : 4, "Two tests", "The " + term(I, "paired-test", "paired test") + " and the smallest gap that this run can show, from the noise of the copies (" + term(I, "mde", "MDE") + ").",
      nums([["Paired rounds", String(c.n)], [term(I, "paired-test", "Paired test p"), ok(c.p_holm) ? pval(c.p_holm) : "n/a"], ["Smallest gap this run can show", ok(cell.mde) ? pct(cell.mde) : "n/a"]]));
    if (c.equivalence) steps += step((steps.match(/class="sn"/g) || []).length + 1, "Equivalence", "The " + term(I, "equivalence-margin", "equivalence margin") + " for this metric is ±" + pct(c.equivalence.margin) + ". The ratio is within it when the whole 90% interval of the ratio, found from the same paired rounds, is inside 1 ± " + pct(c.equivalence.margin) + ".",
      nums([["Margin", "±" + pct(c.equivalence.margin)], ["90% interval", ratioStr(c.equivalence.low) + " to " + ratioStr(c.equivalence.high)], ["p", ok(c.equivalence.p) ? pval(c.equivalence.p) : "n/a"], ["Result", equivalenceWord(c.equivalence)]]));
    var others = Object.keys(cell.comparisons).filter(function (a) { return a !== h.id; }).map(function (a) { var o = I.harn[a], oc = cell.comparisons[a]; return '<a class="chip-r" href="' + link("cell", [cell.slug, o.slug]) + '">' + dot(o) + esc(shortName(o)) + " " + (oc.not_compared ? "not compared" : times(oc.ratio)) + "</a>"; }).join(" ");
    var caveat = (cell.caveats || []).length ? '<div class="caveat" role="note"><b>Measurement caveat</b>' + cell.caveats.map(function (t) { return "<p>" + esc(t) + "</p>"; }).join("") + "</div>" : "";
    var w = I.D.workloads[cell.workload] || {};
    var sentence = esc(shortName(h)) + ": <b>" + esc(val(c.arm_median, cell.unit)) + "</b>. " + esc(refName) + ": <b>" + esc(val(c.ref_median, cell.unit, c.arm_median)) + "</b>. Each value is the median of the " + plural(c.n, "round") + " that both ran.";
    return '<p class="crumbs">' + resultsCrumb(I, cell.key) + ' › <a href="' + link("harness", [h.slug]) + '">' + esc(shortName(h)) + '</a> › <a href="' + link("metric", [cell.key], cell.api_short === "-" ? {} : { api: cell.api_short }) + '">' + esc(w.title || cell.scenario) + "</a> › " + esc(cell.metric_word) + "</p>" +
      '<div class="answer h-' + esc(h.colour) + '"><div class="big">' + ratioStr(c.ratio) + "<small>×</small></div><div><h1>" + esc(w.title || cell.scenario) + ": " + esc(cell.metric_word) + "</h1><p>" + sentence +
      '</p><p class="meta">' + envChip(cell) + (cell.env ? " " : "") + (cell.api_short !== "-" && !cell.env_variant ? esc(API_NAME[cell.api_short] || cell.api_short) + " · " : "") + 'run <a href="' + link("method", ["runs"]) + '">' + esc(cell.run) + "</a> " + provBadge(cellProv(I, cell)) + "</p></div></div>" + caveat +
      '<div class="grid2">' + card(ctx, { id: "facts", title: "How sure is this number?", body: facts }) +
      card(ctx, { id: "rerun", title: term(I, "rerun", "Measure it again"), body: '<pre class="cmd" id="cmd">' + esc(cell.rerun) + '</pre><button type="button" class="btn" data-copy="#cmd">Copy command</button><p class="files"><a href="' + link("method", ["runs"]) + '">Data files</a></p>' }) + "</div>" +
      card(ctx, { id: "runs-" + h.slug, title: "What runs", body: whatRuns(I, h, cell) }) +
      (others ? '<p class="others">The same measurement for other harnesses: ' + others + "</p>" : "") +
      '<details class="more"><summary>The math behind this number</summary><div class="steps">' + steps + "</div></details>";
  }

  // ------------------------------------------------------------------ runs
  function viewRuns(ctx, I) {
    var box = function (title, body) { return '<details class="more"><summary>' + title + "</summary>" + body + "</details>"; };
    var D = I.D, floors = D.cells.map(function (c) { var any = Object.keys(c.comparisons)[0]; var aa = any && c.comparisons[any].aa[I.ref.id]; return aa && ok(aa.floor_log) ? { cell: c, f: Math.expm1(aa.floor_log) } : null; }).filter(Boolean);
    var show = function (v, unit) { return unit === "fraction" ? pct(v) : String(v); };
    var checkValue = function (c) { return c.value == null ? "not measured" : c.kind === "pass" ? (c.value ? "yes" : "no") : show(c.value, c.unit); };
    // one table of the checks: a row for each check (its meaning once, its usual range once), a column for each run
    var ids = [], first = {};
    D.runs.forEach(function (r) { ((r.notes || {}).checks || []).forEach(function (c) { if (!first[c.id]) { first[c.id] = c; ids.push(c.id); } }); });
    var byRun = D.runs.map(function (r) { var m = {}; ((r.notes || {}).checks || []).forEach(function (c) { m[c.id] = c; }); return m; });
    var head = ["Check"].concat(D.runs.map(function (r) { return { h: esc(r.id.replace(/-measured$/, "")) + (r.provisional ? " " + provBadge([r]) : ""), num: true }; }));
    var flagged = function (id) { return byRun.some(function (m) { return m[id] && m[id].status === "note"; }); };
    var rowOf = function (id) {
      var c = first[id], usual = c.kind === "threshold" && ok(c.usual) ? " Usual range: up to " + show(c.usual, c.unit) + "." : "";
      return [td("<b>" + esc(c.title || id) + "</b><br><small>" + esc((c.meaning || "") + usual) + "</small>", c.title || id)].concat(byRun.map(function (m) {
        var x = m[id];
        if (!x) return td("", null);
        return td(x.status === "note" ? '<b class="flag"' + (x.detail ? ' tabindex="0" data-tip="' + esc(x.detail) + '"' : "") + ">" + esc(checkValue(x)) + "</b>" : esc(checkValue(x)), typeof x.value === "number" ? x.value : checkValue(x));
      }));
    };
    var noted = ids.filter(flagged), calm = ids.filter(function (id) { return !flagged(id); });
    var checks = ids.length ? card(ctx, { id: "run-checks", title: "Checks outside their usual range", sub: "A value in bold is outside the usual range" + (I.doc.HEALTH ? ' (<a href="' + esc(docHref(I.doc.HEALTH)) + '">what each check is</a>)' : "") + ". Point at it for where.",
      body: (noted.length ? table(ctx, "run-checks", head, noted.map(rowOf), { tools: false }) : '<p class="muted">Every check of every run is inside its usual range.</p>') +
        (calm.length ? box(esc(plural(calm.length, "check")) + " inside the usual range in every run", table(ctx, "run-checks-calm", head, calm.map(rowOf), { tools: false })) : "") }) : "";
    var cards = D.runs.map(function (r) {
      var f = r.facts || {}, run = r.run || {}, site = r.site || {}, hw = r.hardware || {}, rn = r.runner || {}, cal = r.calibration || {};
      var noted = ((r.notes || {}).checks || []).filter(function (c) { return c.status === "note"; });
      var kv = [["CPU", f.cpu_model], ["kernel", f.kernel], ["harness CPUs", f.pinned_cpus || (run.harness_cpus || []).join(",")], ["mock CPUs", f.mock_cpus || (run.mock_cpus || []).join(",")], ["fixed clock", f.fixed_clock], ["site", site.name], ["backend", site.backend],
        ["host class", hw.class], ["slot", run.slot ? run.slot.id + " of " + run.slot.of + ", CPUs " + (Array.isArray(run.slot.cpus) ? run.slot.cpus.join(",") : run.slot.cpus) : null],
        ["slot calibration", run.slot ? run.slot.calibration || "none: this slot was not calibrated" : null], ["rounds", run.rounds], ["warm-up", run.warmup], ["seed", run.seed], ["samples", r.samples], ["runner commit", rn.commit], ["runner dirty", rn.dirty], ["arms.lock SHA-256", r.lock_sha256], ["egress", (r.egress || {}).mode],
        ["calibration", ok(cal.max_cv) ? (cal.passed ? "passed" : "refused") + ", max CV " + pct(cal.max_cv) + " (gate " + pct(cal.gate) + ")" : null],
        ["meter", (r.meters || []).join(", ")], ["instruction counts", (r.perf_scopes || []).join(", ")]].filter(function (x) { return x[1] !== undefined && x[1] !== null && x[1] !== ""; });
      var arms = Object.keys(r.arms || {}).sort().map(function (a) { return "<tr><th>" + (I.harn[a] ? '<a href="' + esc(link("harness", [I.harn[a].slug])) + '">' + esc(a) + "</a>" : esc(a)) + "</th><td><code>" + esc(r.arms[a].version || "") + "</code></td><td>" + esc(r.arms[a].twin_of || "") + "</td></tr>"; }).join("");
      var files = r.files.map(function (x) { return '<a class="raw" href="runs/' + esc(r.id) + "/" + esc(x) + '">' + esc(x) + "</a>"; }).concat(r.logs ? ['<a class="raw" href="' + esc(link("logs", [r.id])) + '">logs/</a>'] : []).join(" · ");
      var feeds = [];
      if (D.cells.some(function (c) { return c.run === r.id; })) feeds.push('<a href="' + link() + '">Results</a>');
      if (D.scale && D.scale.envelopes.some(function (e) { return e.runs.indexOf(r.id) >= 0; })) feeds.push('<a href="' + esc(scaleHref()) + '">Agent swarming</a>');
      var line = [f.cpu_model, run.rounds ? plural(run.rounds, "round") : "", hw.class ? "host class " + hw.class : ""].filter(Boolean).join(" · ");
      return '<section class="card run"><header class="card-h"><div><h2>' + esc(r.id) + " " + provBadge(r.provisional ? [r] : []) + '</h2><p class="sub">' + esc(line) + '</p></div><div class="card-tools"><span class="muted">' + esc(plural(noted.length, "note")) + "</span></div></header>" +
        (feeds.length ? '<p class="feeds">Feeds: ' + feeds.join(" / ") + "</p>" : "") + (r.provisional ? '<p class="muted">Provisional: ' + esc(provWhy([r])) + ".</p>" : "") + '<p class="files">' + files + "</p>" +
        box("Host and run facts", '<table class="kv">' + kv.map(function (x) { return "<tr><th>" + esc(x[0]) + "</th><td><code>" + esc(x[1]) + "</code></td></tr>"; }).join("") + "</table>" + (r.caveats || []).map(function (t) { return '<div class="caveat" role="note"><p>' + esc(t) + "</p></div>"; }).join("")) +
        box("Harnesses and versions", '<table class="kv"><tr><th>arm</th><td>version</td><td>copy of</td></tr>' + arms + "</table>") +
        ((r.skipped || []).length ? box("What could not run (" + r.skipped.length + ")", "<ul>" + r.skipped.map(function (s) { return "<li><code>" + esc(s.arm) + "</code> " + esc(s.scenario) + ": " + esc(s.reason) + "</li>"; }).join("") + "</ul>") : "") + "</section>";
    }).join("");
    var data = card(ctx, { id: "data-files", title: "Data files", body: '<p class="files">' + D.meta.data_files.map(function (x) { return '<a class="raw" href="data/' + esc(x) + '">' + esc(x) + "</a>"; }).join(" · ") + "</p><p class=\"muted\">The seed of the resampling is " + esc(D.meta.seed) + ".</p>" });
    return '<div class="pagehead"><h1>Method</h1><p class="lede">Where each run happened and the conditions it ran in. A check outside its usual range does not change a number.</p>' + methodTabs("runs") + "</div>" + checks + cards + data +
      (floors.length ? box(esc(shortName(I.ref)) + " against a copy of itself, for each measurement", table(ctx, "pi-floors", ["Measurement", { h: "Noise ±", num: true }], floors.map(function (x) { return [td('<a href="' + link("metric", [x.cell.key], x.cell.api_short === "-" ? {} : { api: x.cell.api_short }) + '">' + esc(measureName(I, x.cell)) + "</a>", measureName(I, x.cell)), td(pct(x.f), x.f)]; }))) : "");
  }

  // the real schedule (buffon/runner/engine.py Runner.measure): in round k the arms run in the order rotate(arms, k + workload index), so the
  // first harness changes every round; the first `warmup` rounds are measured and dropped
  function diagramRounds(I) {
    var hs = I.D.harnesses.slice(0, 6), run = (I.D.runs[0] || {}).run || {}, warm = run.warmup || 1, R = Math.min(6, warm + 4), cw = Math.max(150, hs.length * 26 + 30);
    var W = 160 + R * cw, s = '<svg class="diagram" viewBox="0 0 ' + W + " " + (60 + hs.length * 34) + '" role="img" aria-label="The order of the harnesses in each round">';
    for (var r = 0; r < R; r++) {
      var x = 160 + r * cw;
      s += '<text class="nt" x="' + (x + hs.length * 13) + '" y="22">' + (r < warm ? "warm-up " + (r + 1) + " (dropped)" : "round " + (r - warm + 1)) + "</text>";
      hs.forEach(function (h, i) {
        var pos = (i - r % hs.length + hs.length) % hs.length, y = 36 + i * 34;
        s += '<g class="slot h-' + esc(h.colour) + (r < warm ? " warm" : "") + '"><rect x="' + (x + pos * 26) + '" y="' + y + '" width="22" height="24" rx="4"/><text class="ns" x="' + (x + pos * 26 + 11) + '" y="' + (y + 16) + '">' + (pos + 1) + "</text></g>";
      });
    }
    hs.forEach(function (h, i) { s += '<text class="rl" x="150" y="' + (52 + i * 34) + '">' + esc(h.name) + "</text>"; });
    return s + "</svg>";
  }

  // ------------------------------------------------------------------ method: one strip, details behind "more"; the runs and the data under it
  function methodTabs(active) {
    return '<div class="pagetools">' + seg([["", "How a number is made"], ["runs", "Runs and data"]], active, function (v) { return 'data-href="' + esc(link("method", v ? [v] : [])) + '"'; }) + "</div>";
  }
  // the margin of each metric that has one, from the comparisons the report holds
  function marginsOf(I) {
    var seen = {}, out = [];
    I.D.cells.forEach(function (c) {
      var m = null; Object.keys(c.comparisons).forEach(function (a) { var eq = c.comparisons[a].equivalence; if (eq && ok(eq.margin)) m = eq.margin; });
      if (m != null && !seen[c.key]) { seen[c.key] = 1; out.push({ mt: I.metric[c.key], margin: m }); }
    });
    return out;
  }
  function viewMethod(ctx, I, route) {
    if (route.args[0] === "runs") return viewRuns(ctx, I);
    var M = I.D.method;
    var steps = M.steps.map(function (s, i) {
      var more = "<p>" + s.more.map(esc).join("</p><p>") + "</p>" + (s.formulas || []).map(function (f) { return '<div class="eqrow"><span class="lbl">' + esc(f.name) + '</span><div class="eq">' + f.html + "</div></div>"; }).join("") +
        (i === 3 ? '<div class="diagwrap">' + diagramRounds(I) + '</div><p class="muted">The number in each box is the position of the harness in that round.</p>' : "");
      return '<li class="mstep"><span class="sn">' + (i + 1) + "</span><h2>" + esc(s.title) + "</h2><p>" + esc(s.line) + '</p><details class="why"><summary>More</summary><div>' + more + "</div></details></li>";
    }).join("");
    var docs = M.links.filter(function (k) { return I.doc[k]; }).map(function (k) { return '<li><a href="' + esc(docHref(I.doc[k])) + '">' + esc(I.doc[k].title) + "</a> <small>" + esc(I.doc[k].about) + "</small></li>"; }).join("") +
      '<li><a href="' + link("glossary") + '">Glossary</a> <small>Every term and abbreviation on the site.</small></li>';
    var rows = I.D.harnesses.map(function (h) {
      var r = settingsLine(h.runtime_settings);
      return [td(hname(h), h.name), r ? td(r.set.join("<br>") || "none", r.set.length) : td('<span class="muted">not recorded</span>', ""), r ? td(r.left.join(", ") || "none", r.left.length) : td("", "")];
    });
    var runtime = card(ctx, { id: "runtime-settings", title: "Runtime settings", sub: "The tuning variables Buffon or a manifest set for each harness, with who set them, and the known ones left at the harness's own default.",
      body: table(ctx, "runtime-settings", ["Harness", "Set (and by whom)", "Left at the default"], rows, { tools: false }) });
    var diverge = [];
    I.D.harnesses.forEach(function (h) { (h.divergences || []).forEach(function (d) { diverge.push([td(hname(h), h.name), td(esc((d.workloads || []).join(", "))), td(esc(d.reason || ""))]); }); });
    var different = diverge.length ? '<details class="more"><summary>Different work (' + diverge.length + ')</summary><section class="card">' + table(ctx, "different-work", ["Harness", "Workloads", "Reason"], diverge, { tools: false }) +
      '<p class="muted">These cells show the median of the harness, labelled "' + esc(NOT_COMPARED) + '".</p></section></details>' : "";
    var margins = marginsOf(I);
    var equiv = margins.length ? '<details class="more"><summary>Equivalence margins (' + margins.length + ')</summary><section class="card">' + table(ctx, "margins", ["Measure", { h: "Margin", num: true }],
      margins.map(function (x) { return [td('<a href="' + esc(link("metric", [x.mt.key])) + '">' + esc(x.mt.title + ": " + cap(x.mt.word)) + "</a>", x.mt.title), td("±" + pct(x.margin), x.margin)]; }), { tools: false }) +
      "<p class=\"muted\">A ratio is within the margin when the whole 90% interval of the ratio is inside 1 ± the margin.</p></section></details>" : "";
    return '<div class="pagehead"><h1>Method</h1><p class="lede">How one number is made, how the harnesses are kept fair, and where the numbers stop.</p>' + methodTabs("") + "</div>" +
      '<ol class="strip">' + steps + "</ol>" +
      '<h2 class="sech">Fairness</h2>' + runtime + different + equiv + durableMethod(ctx, I) +
      '<h2 class="sech">Limits</h2><section class="card"><p>The scripted model answers at once and has no network. A real session adds network time and model time. One machine gives one set of numbers. The site measures the cost of a harness, not the quality of its answers. ' +
      docLink(I, "LIMITATIONS", "Read the full list.") + "</p></section>" +
      '<section class="card"><header class="card-h"><div><h2>Read more</h2></div></header><ul class="doclist">' + docs + '</ul><p class="muted">Pi is by Mario Zechner and Earendil Inc. (MIT), <a href="https://pi.dev">pi.dev</a>.</p></section>';
  }
  function viewGlossary(ctx, I, route) {
    var t = route.params.t;
    var item = function (g) {
      return '<div class="gl' + (g.slug === t ? " hit" : "") + '" id="g-' + esc(g.slug) + '"><dt>' + (g.kind === "abbr" ? "<abbr>" + esc(g.term) + "</abbr> <span class=\"exp\">" + esc(g.expands) + "</span>" : esc(g.term)) + '</dt><dd><p>' + esc(g.text) + "</p>" +
        (g.see ? '<p class="muted">See <a href="' + link("glossary", [], { t: g.see }) + '">' + esc((I.glossary[g.see] || {}).term || g.see) + "</a>.</p>" : "") + (g.tex ? '<div class="eq">' + g.tex + "</div>" : "") + "</dd></div>";
    };
    var terms = I.D.glossary.filter(function (g) { return g.kind === "term"; }), abbr = I.D.glossary.filter(function (g) { return g.kind === "abbr"; }).sort(function (a, b) { return a.term.localeCompare(b.term); });
    var shown = function (list) { return list.filter(function (g) { return g.shown; }); }, other = function (list) { return list.filter(function (g) { return !g.shown; }); };
    var rest = other(terms).concat(other(abbr)), open = !!t && rest.some(function (g) { return g.slug === t; });
    return '<div class="pagehead"><h1>Glossary</h1><p class="lede">Every special term and abbreviation on the site.</p>' +
      '<input type="search" class="find" placeholder="Find a term" data-filter-glossary aria-label="Find a term"></div>' +
      card(ctx, { id: "terms", title: "Terms", body: '<dl class="glossary">' + shown(terms).map(item).join("") + "</dl>" }) + card(ctx, { id: "abbrs", title: "Abbreviations", body: '<dl class="glossary">' + shown(abbr).map(item).join("") + "</dl>" }) +
      (rest.length ? '<details class="more" id="other-terms"' + (open ? " open" : "") + "><summary>Other terms (" + rest.length + ')</summary><section class="card"><dl class="glossary">' + rest.map(item).join("") + "</dl></section></details>" : "");
  }
  function notFound(I) { return '<div class="pagehead"><h1>Not found</h1><p class="lede">This view does not exist in this build. <a href="' + link() + '">Back to Results</a>.</p></div>'; }

  // ------------------------------------------------------------------ the repository documents and the log files, in the same frame as every other view
  function viewDoc(ctx, I, route) {
    var d = I.doc[route.args[0]];
    if (!d) return notFound(I);
    var others = I.D.docs.filter(function (x) { return x !== d && x.slug !== "README"; }).map(function (x) { return '<li><a href="' + esc(docHref(x)) + '">' + esc(x.title) + "</a> <small>" + esc(x.about) + "</small></li>"; }).join("");
    return '<p class="crumbs"><a href="' + link("method") + '">Method</a> › ' + esc(d.title) + "</p>" +
      '<article class="card doc md raw" id="doc-' + esc(d.slug) + '">' + d.html + "</article>" +
      (others ? '<section class="card"><header class="card-h"><div><h2>Other documents</h2></div></header><ul class="doclist">' + others + "</ul></section>" : "");
  }
  // About: the README, as a document of the site
  function viewAbout(ctx, I) {
    var d = I.doc.README;
    return d ? '<article class="card doc md raw" id="doc-README">' + d.html + "</article>" : notFound(I);
  }
  function viewLogs(ctx, I, route) {
    var r = I.D.runs.filter(function (x) { return x.id === route.args[0]; })[0];
    if (!r || !r.logs) return notFound(I);
    return '<p class="crumbs"><a href="' + link("method") + '">Method</a> › <a href="' + link("method", ["runs"]) + '">Runs and data</a> › ' + esc(r.id) + " › logs</p>" +
      card(ctx, { id: "logs", title: "Log files", sub: "The logs of the run " + esc(r.id) + ". They are plain text files.",
        body: '<ul class="files">' + r.log_files.map(function (n) { return '<li><a class="raw" href="runs/' + esc(r.id) + "/logs/" + esc(n) + '">' + esc(n) + "</a></li>"; }).join("") + "</ul>" });
  }

  function noteOf(reason) { var r = String(reason || ""), i = r.indexOf(": "); return i > 0 ? r.slice(0, i) : r; }

  // ------------------------------------------------------------------ faults: what each harness did when the provider failed or a program stopped
  function faultName(f) { return cap(f.fault.replace(/-/g, " ")); }
  function faultApis(I) { var out = []; (I.D.faults || []).forEach(function (f) { if (out.indexOf(f.api_short) < 0) out.push(f.api_short); }); return out; }
  // the faults of the chosen wire API (all of them when the run has one API)
  function faultsOf(I, st) { var apis = faultApis(I), api = apis.indexOf(st.api) >= 0 ? st.api : apis[0]; return (I.D.faults || []).filter(function (f) { return apis.length < 2 || f.api_short === api; }); }
  function faultHref(f, h) { return link("fault", [f.id, h.slug]); }
  function faultProv(I, f) { return provRuns(I, [f.run]); }
  // {passed, ran, of} of one harness over a list of faults
  function faultCount(list, h) { var ran = list.filter(function (f) { return f.arms[h.id]; }); return { passed: ran.filter(function (f) { return f.arms[h.id].ok; }).length, ran: ran.length, of: list.length }; }
  // the harnesses that ran none of the faults: the runner's reason says whether they cannot (Can't run) or were not run (Not in this test)
  function faultAbsent(list, st) {
    return st.hs.filter(function (h) { return !faultCount(list, h).ran; }).map(function (h) {
      var why = (list[0] && list[0].na[h.id]) || "";
      return { h: h, na: true, cant: isCant(why), why: why, tip: shortName(h) + ": " + (noteOf(why) || "it was not run on these faults") };
    });
  }
  function faultBars(I, st, list, o) {
    o = o || {};
    var miss = faultAbsent(list, st);
    var rows = st.hs.filter(function (h) { return faultCount(list, h).ran; }).map(function (h) {
      var c = faultCount(list, h);
      var bad = list.filter(function (f) { return f.arms[h.id] && !f.arms[h.id].ok; }).map(faultName);
      return { h: h, plain: o.plain, f: c.passed / c.of, label: c.passed + " of " + c.of, tip: shortName(h) + ": " + c.passed + " of " + plural(c.of, "fault") + " passed" + (c.ran < c.of ? "\n" + (c.of - c.ran) + " not run" : "") + (bad.length ? "\nDid not pass: " + bad.join(", ") : ""),
               prov: faultProv(I, list[0]) };
    });
    var prov = list.length ? faultProv(I, list[0]) : [];
    if (!rows.length) return '<p class="empty">' + NO_VALUE + "</p>" + absentNote(I, st.route, miss, { plain: o.plain, quiet: true });
    return (prov.length ? '<p class="provline">' + provBadge(prov) + "</p>" : "") + barRows(rows, { axis: { ticks: [{ f: 0, label: "0" }, { f: 1, label: String(list.length) }], label: o.plain ? "" : "faults passed" } }) + absentNote(I, st.route, miss, { plain: o.plain });
  }
  function faultTable(ctx, I, st, list, id) {
    var head = '<th scope="col" class="hcol">Harness</th>' + list.map(function (f) { return '<th scope="col" class="num mcol" data-csv-label="' + esc(faultName(f)) + '"><div class="mh stack"><span class="wk">' + esc(I.multiApi && f.api_short !== "-" ? apiName(f.api_short) : "Fault") + '</span><span class="mw">' + esc(faultName(f)) + "</span></div></th>"; }).join("");
    var body = st.hs.filter(function (h) { return faultCount(list, h).ran; }).map(function (h) {
      return '<tr class="h-' + esc(h.colour) + '"><th scope="row" class="hn1" data-csv-value="' + esc(h.name) + '">' + hname(h) + '<small class="ver">' + esc(h.version || "") + "</small></th>" + list.map(function (f) {
        var a = f.arms[h.id];
        if (!a) return '<td class="num na" data-csv-value="can\'t run"><span tabindex="0" data-tip="' + esc(shortName(h) + ": " + noteOf(f.na[h.id])) + '">' + "can't run</span></td>";
        return '<td class="num" data-csv-value="' + (a.ok ? "passed" : "did not pass") + '"><a href="' + esc(faultHref(f, h)) + '" data-tip="' + esc(shortName(h) + ": " + faultName(f) + "\n" + (a.ok ? "Passed on " + plural(a.reps, "repetition") + "." : "Did not pass: " + a.reasons.join("; ")) + "\nClick for how it was judged.") + '"><span class="cv"><b>' + (a.ok ? "Passed" : "Did not pass") + "</b></span>" + provBadge(faultProv(I, f)) + "</a></td>";
      }).join("") + "</tr>";
    }).join("");
    return '<div class="tablewrap"><table class="data grid" id="t-' + esc(id) + '" data-csv-group="faults" style="--n:' + list.length + '"><thead><tr>' + head + "</tr></thead><tbody>" + body + "</tbody></table></div>";
  }
  // the faults as columns, at most MAIN_MAX in a table
  function faultTables(ctx, I, st, list) {
    var out = "";
    for (var i = 0; i < list.length || !i; i += MAIN_MAX) out += faultTable(ctx, I, st, list.slice(i, i + MAIN_MAX), i ? "faults-" + (i / MAIN_MAX + 1) : "faults");
    return out;
  }
  // the Reliability section: one bar for each harness (faults passed), then every fault as a column
  function faultsBody(ctx, I, st, sec) {
    var list = faultsOf(I, st);
    var chart = card(ctx, { id: "faults-chart", title: "Faults passed", sub: esc(plural(list.length, "fault")) + " injected. The same rules judge every harness.", chart: faultBars(I, st, list),
      table: table(ctx, "faults-chart", ["Harness", { h: "Passed", num: true }, { h: "Faults", num: true }], st.hs.filter(function (h) { return faultCount(list, h).ran; }).map(function (h) { var c = faultCount(list, h); return [td(esc(h.name)), td(String(c.passed), c.passed), td(String(c.ran), c.ran)]; })) });
    var main = card(ctx, { id: "faults-table", title: "Each fault", body: faultTables(ctx, I, st, list), tools: '<button type="button" class="btn" data-csv="faults">Download CSV</button>' });
    return chart + main;
  }
  function viewFault(ctx, I, route) {
    var f = (I.D.faults || []).filter(function (x) { return x.id === route.args[0]; })[0], h = I.bySlug[route.args[1]], a = f && h && f.arms[h.id];
    if (!a) return notFound(I);
    var ref = I.ref, refSig = f.ref_signature, mine = a.signature;
    var facts = '<table class="kv facts"><tr><th>Repetitions</th><td>' + a.reps + "</td></tr><tr><th>Outcome of " + esc(shortName(h)) + "</th><td><code>" + esc(mine == null ? "differs between repetitions" : mine) + "</code></td></tr>" +
      (h !== ref ? "<tr><th>Outcome of " + esc(shortName(ref)) + "</th><td><code>" + esc(refSig == null ? "no stable outcome" : refSig) + "</code></td></tr>" : "") +
      "<tr><th>Reasons</th><td>" + (a.reasons.length ? a.reasons.map(esc).join("<br>") : "none") + "</td></tr></table>";
    return '<p class="crumbs"><a href="' + link() + '">Results</a> › <a href="' + link("r", ["reliability"]) + '">Reliability</a> › ' + esc(faultName(f)) + " › " + esc(shortName(h)) + "</p>" +
      '<div class="answer"><div class="big">' + (a.ok ? "Passed" : "Did not pass") + "</div><div><h1>" + esc(faultName(f)) + ": " + esc(shortName(h)) + "</h1><p>" + (a.ok ? "The invariants held on every repetition" + (h === ref ? "." : " and the outcome equals " + esc(shortName(ref)) + "'s.") : "At least one rule did not hold.") +
      '</p><p class="meta">' + (I.multiApi && f.api_short !== "-" ? esc(apiName(f.api_short)) + " · " : "") + 'run <a href="' + link("method", ["runs"]) + '">' + esc(f.run) + "</a> " + provBadge(faultProv(I, f)) + "</p></div></div>" +
      card(ctx, { id: "fault-facts", title: "How it was judged", body: facts + '<p class="muted">A harness passes when the process ended, left no crash trace, did not report success falsely and kept a session file that parses, on every repetition, and its outcome equals the outcome of ' + esc(shortName(ref)) + ".</p>" });
  }

  // ------------------------------------------------------------------ the swarm samples (scale/agents-limit, print-limit, the ext10 pair, and the rung samples of earlier runs): the Scale page
  var KINDS = ["rpc", "print"];
  // the kinds of an envelope are rpc, print and, when the run loaded the ten extensions, rpc-ext10 and print-ext10: the same metrics as the kind without them
  function kindBase(kind) { return kind.replace(/-ext10$/, ""); }
  function scaleOf(I) { return I.D.scale || null; }
  function envOf(I, id) { var S = scaleOf(I); return S ? S.envelopes.filter(function (e) { return e.id === id; })[0] || S.envelopes[0] : null; }
  function smetrics(I, kind) { return scaleOf(I).metrics[kindBase(kind)] || []; }
  function smetric(I, kind, key) { return smetrics(I, kind).filter(function (m) { return m.key === key; })[0]; }
  function snote(I, kind, key) { var m = smetric(I, kind, key), n = ((scaleOf(I).notes || {})[kind] || {})[key]; return m && n ? n : ""; }
  function limitOf(e) { return ok(e.memory_mib) ? val(e.memory_mib, "MiB") : "its memory limit"; }
  function cores(n) { return n + (n === 1 ? " core" : " cores"); }
  function swarmHref(e, kind, h, n) { return link("swarm", [e.id, kind, h.slug, String(n)]); }
  function scaleHref(e) { return link("r", ["agent-swarming"], e && e.id ? { e: e.id } : {}); }
  function kindArms(I, e, kind, hs) { return (hs || I.D.harnesses).filter(function (h) { var a = e.kinds[kind].arms[h.id]; return a && a.rungs; }); }
  function agents(n) { return plural(n, "agent"); }
  // the words of a stop. An OOM kill and a stall both read "did not fit in <limit>"; the detail is the second line of a tooltip and the derivation page.
  function causeOf(I, c) { return (scaleOf(I).causes || {})[c] || { word: c, fit: false, detail: "" }; }
  function stopWord(I, e, cause) { var c = causeOf(I, cause); return c.fit ? c.word + " in " + limitOf(e) : c.word; }
  function stopDetail(I, stop) {
    if (stop.cause === "oom") return ok(stop.oom_kills) && stop.oom_kills > 0 ? "the kernel killed " + plural(Math.round(stop.oom_kills), "agent") : causeOf(I, "oom").detail;
    return causeOf(I, stop.cause).detail;
  }
  // an agent count is a plain integer: "287" for an exact limit, "at least 8192 (cap)" where the search completed its cap, and for a run made before the search the range its ladder leaves open:
  // "256 to 511" (the largest step that finished to the step before the first that did not), or "at least 256 (the ladder's top)" where no step stopped
  function fitLabel(a) {
    if (a.exact) return a.capped ? "at least " + a.limit + " (cap)" : a.between ? a.limit + " to " + a.between[1] : String(a.limit);
    if (a.between) return a.between[0] === a.between[1] ? String(a.between[0]) : a.between[0] + " to " + a.between[1];
    return "at least " + (a.at_least || 0) + " (the ladder's top)";
  }
  // a range inside a sentence is written with an en dash: 32–63
  function dashRange(t) { return String(t).replace(/(\d) to (\d)/g, "$1–$2"); }
  // where the bar ends (v) and the range of numbers the whisker covers (lo to hi): the rounds of an exact limit, the open range of a ladder
  function fitSpan(a) {
    if (a.exact) return { v: a.limit, lo: a.range[0], hi: Math.max(a.range[1], a.between ? a.between[1] : 0) };
    if (a.between) return { v: a.between[0], lo: a.between[0], hi: a.between[1] };
    return { v: a.at_least || 0, lo: a.at_least || 0, hi: a.at_least || 0 };
  }
  function stopTip(I, e, h, a, ext) {
    var who = shortName(h) + (ext ? " with 10 extensions" : "");
    if (a.cannot) return who + "\n" + a.cannot;
    var s = a.stop, sp = fitSpan(a), out = [who];
    if (a.exact) {
      out.push(!a.limit ? "Not even one agent finished." : a.capped ? "At least " + agents(a.limit) + " fit in " + limitOf(e) + ": the search stopped at its cap." : agents(a.limit) + " fit in " + limitOf(e) + ".");
      if (a.limits.length > 1) out.push(a.range[1] > a.range[0] ? a.range[0] + " to " + a.range[1] + " over " + plural(a.limits.length, "round") + "." : "The same in " + plural(a.limits.length, "round") + ".");
      if (a.between) out.push("The search stopped at steps of " + plural(a.resolution, "agent") + ": the limit is between " + a.between[0] + " and " + a.between[1] + ".");
    } else if (a.between) {
      out.push(!a.between[1] ? "Not even one agent finished." : (a.between[0] === a.between[1] ? agents(a.between[0]) + " fit" : "Between " + a.between[0] + " and " + agents(a.between[1]) + " fit") + " in " + limitOf(e) + ". This run doubled the number of agents and did not try the numbers in between.");
    } else out.push("At least " + agents(a.at_least || 0) + " fit in " + limitOf(e) + ": the ladder ended there.");
    if (s) out.push(agents(s.n) + " " + stopWord(I, e, s.cause) + ": " + stopDetail(I, s) + ".");
    if (a.skipped && a.skipped.length) out.push(plural(a.skipped.length, "larger step") + " not tried.");
    return out.join("\n");
  }

  // the runs of the probes of a harness, and the provisional ones among them: the badge of a chart, a bar or a row
  function rungRuns(r) { return r.runs || []; }
  function armProv(I, a) { return provRuns(I, [].concat.apply([], (a.rungs || []).map(rungRuns))); }
  function kindProv(I, e, kind, withExt) {
    var ids = []; [kind].concat(withExt && e.kinds[kind + "-ext10"] ? [kind + "-ext10"] : []).forEach(function (k) { Object.keys(e.kinds[k].arms).forEach(function (h) { (e.kinds[k].arms[h].rungs || []).forEach(function (r) { ids = ids.concat(rungRuns(r)); }); }); });
    return provRuns(I, ids);
  }
  // the ticks of the bar axis, at powers of 4: a bar has an exact length now, so the axis does not end at the largest number
  function powers(top) { var out = []; for (var n = 1; n <= top; n *= 4) out.push(n); return out; }

  // the answer of the page: one bar for each harness, the number of agents that all finished, on the bar. The length of a bar is proportional to log2 of the count, on a labelled axis.
  // The Overview tile draws a harness that was also run with the ten extensions as a second, lighter bar under its own on the same axis: the gap is what the extensions cost.
  // The section page draws one kind at a time (o.solo): the kind with the extensions has a chip with the difference from the kind without.
  function fitBars(I, e, kind, o) {
    o = o || {};
    var K = e.kinds[kind], xk = kind + "-ext10", X = o.solo ? null : e.kinds[xk], without = o.solo && kindBase(kind) !== kind ? e.kinds[kindBase(kind)] : null, twin = X || without || (o.solo ? e.kinds[xk] : null), top = 2;
    I.D.harnesses.forEach(function (h) { [K.arms[h.id], twin && twin.arms[h.id]].forEach(function (a) { if (a && a.rungs) top = Math.max(top, fitSpan(a).hi); }); });   // a kind and its twin with the extensions share one axis
    var pos = function (n) { return n > 1 ? Math.log2(n) / Math.log2(top) : 0; }, cannot = {}, xcannot = {}, rows = [];
    var note = function (into, h, why) { (into[noteOf(why)] = into[noteOf(why)] || []).push({ h: h, why: why }); };
    function row(h, a, ext, base) {
      var sp = fitSpan(a), c = a.stop ? causeOf(I, a.stop.cause) : null, sat = a.rungs.some(function (r) { return r.mock_saturated; }), prov = armProv(I, a), chip = "";
      if (c && !c.fit) chip += '<small class="bnote">' + esc(agents(a.stop.n) + " " + stopWord(I, e, a.stop.cause)) + "</small> ";
      if (base && base.exact && a.exact && !base.capped && !a.capped) { var d = a.limit - base.limit; chip += '<small class="bnote">' + (d ? Math.abs(d) + (d < 0 ? " fewer" : " more") : "no change") + "</small> "; }
      rows.push({ h: h, plain: o.plain, cls: ext ? "ext" : "", name: ext ? (base ? "" : hname(h, o.plain ? false : undefined) + " ") + '<small class="bnote">with 10 extensions</small>' : null, f: pos(sp.v), empty: !sp.v,
        whisker: sp.hi > sp.lo ? [pos(sp.lo), pos(sp.hi)] : null, label: fitLabel(a) + (sat ? " ⚠" : ""),
        tip: stopTip(I, e, h, a, ext || !!without) + (prov.length ? "\nProvisional: " + provWhy(prov) : "") + (o.plain || !sp.v ? "" : "\nClick the number for where it comes from."),
        href: !o.plain && sp.v ? swarmHref(e, ext ? xk : kind, h, a.max_ok) : null, prov: prov, chip: o.plain ? "" : chip });
    }
    var missing = [];
    (o.hs || I.D.harnesses).forEach(function (h) {
      var a = K.arms[h.id], x = X && X.arms[h.id];
      if (!a && !x) { missing.push({ h: h, na: true, tip: shortName(h) + ": it was not run on this workload in this run" }); return; }
      if (a && a.cannot) { note(cannot, h, a.cannot); return; }
      if (a) row(h, a, false, without && without.arms[h.id]);
      if (x && x.cannot) { if (a) note(xcannot, h, x.cannot); } else if (x) row(h, x, true, a);
    });
    var allProv = rows.length && rows.every(function (r) { return r.prov && r.prov.length; });
    var ticks = powers(top).map(function (n) { return { f: pos(n), label: String(n) }; }).filter(function (t, i) { return !o.plain || i % 2 === 0; });   // the tile has room for every other label
    var notRun = function (into, what) {
      return Object.keys(into).map(function (why) {
        return what + into[why].map(function (x) { return '<span tabindex="0" data-tip="' + esc(x.why) + '">' + esc(shortName(x.h)) + "</span>"; }).join(", ") + " (" + esc(why) + ").";
      }).join(" ");
    };
    var lines = [notRun(cannot, "Can't run: "), notRun(xcannot, "Can't run with 10 extensions: ")].filter(Boolean).join(" ");
    return (allProv && o.plain ? '<p class="provline">' + provBadge(kindProv(I, e, kind, true)) + "</p>" : "") + barRows(rows, { axis: { ticks: ticks, label: o.plain ? "" : "agents, log scale" } }) +
      (lines ? '<p class="notrun">' + lines + "</p>" : "") + absentNote(I, null, missing, { plain: o.plain });
  }

  // one line chart: a metric against the number of agents on a log2 axis, one line per harness with its name at its end, one point per rung that completed, the whisker the smallest to the
  // largest round. A rung that stopped has no value to draw: it is a cross on the axis at its size, and its tooltip says what happened. Memory and CPU are on a log scale, so that a harness
  // that costs a tenth of another one is not squashed on the axis.
  var LOG_KEYS = ["mem_per_agent_mib", "cpu_ms_per_agent_turn"];
  function scaleChart(I, e, kind, key, o) {
    var arms = kindArms(I, e, kind, o.hs), M = smetric(I, kind, key), ns = e.kinds[kind].ns, lo2 = Math.log2(Math.min.apply(null, ns)), hi2 = Math.log2(Math.max.apply(null, ns)), vals = [], lows = [];
    var lg = LOG_KEYS.indexOf(key) >= 0;
    if (hi2 <= lo2) hi2 = lo2 + 1;
    arms.forEach(function (h) { e.kinds[kind].arms[h.id].rungs.forEach(function (r) { if (r.status === "ok" && ok(r.med[key])) { var sp = r.spread && r.spread[key]; vals.push(sp ? sp[1] : r.med[key]); lows.push(sp ? sp[0] : r.med[key]); } }); });
    if (!vals.length) return "";
    var lo = 0, top = Math.max.apply(null, vals) * 1.08 || 1;
    if (lg) { lo = Math.min.apply(null, lows.filter(function (v) { return v > 0; })) * 0.8; top = Math.max.apply(null, vals) * 1.25; }
    var f = plotFrame({ width: o.width, lo: lo, hi: top, log: lg, unit: M.unit, xlabel: "agents →", label: M.title + " against the number of agents", names: arms.filter(function (h) { return e.kinds[kind].arms[h.id].rungs.some(function (r) { return r.status === "ok" && ok(r.med[key]); }); }).map(shortName) }), W = f.W, L = f.L, R = f.R, H = f.H, T = f.T, B = f.B, Y = f.Y, s = f.svg;
    var X = function (n) { return L + (Math.log2(n) - lo2) / (hi2 - lo2) * (W - L - R); };
    // the labels are at powers of two: the numbers of agents that a search probes are many, and the bisection puts them close together
    var marks = []; for (var p = 1; p <= Math.pow(2, hi2); p *= 2) if (p >= Math.pow(2, lo2) - 1e-9) marks.push(p);
    var every = Math.max(1, Math.ceil(marks.length / Math.max(2, Math.floor((W - L - R) / 34))));
    marks.forEach(function (n, i) { if (i % every === 0) s += '<text class="xl" x="' + X(n).toFixed(1) + '" y="' + (H - 18) + '">' + n + "</text>"; });
    // the level-off of the RPC swarm: past as many agents as there are cores, every CPU is busy and turns per second stop growing
    if (kind === "rpc" && key === "turns_per_s" && e.cores > 1 && e.cores < Math.max.apply(null, ns)) {
      var cx = X(e.cores), room = W - R - cx;
      s += '<line class="level" x1="' + cx.toFixed(1) + '" x2="' + cx.toFixed(1) + '" y1="' + T + '" y2="' + (H - B) + '"/><text class="levt" x="' + (cx + 5).toFixed(1) + '" y="' + (T + 10) + '">' + esc(room > 190 ? "turns per second with all CPUs busy" : "all CPUs busy") + "</text>";
    }
    var stops = {}, ends = [];
    arms.forEach(function (h) {
      var a = e.kinds[kind].arms[h.id], rungs = a.rungs, line = rungs.filter(function (r) { return r.status === "ok" && ok(r.med[key]); });
      s += '<g class="series h-' + esc(h.colour) + '">' + (line.length > 1 ? '<polyline points="' + line.map(function (r) { return X(r.n).toFixed(1) + "," + Y(r.med[key]).toFixed(1); }).join(" ") + '"/>' : "");
      line.forEach(function (r) {
        var sp = r.spread && r.spread[key], x = X(r.n), y = Y(r.med[key]), prov = provRuns(I, rungRuns(r));
        var tip = shortName(h) + ": " + agents(r.n) + "\n" + M.title + " " + val(r.med[key], M.unit) + (sp ? "\nrounds " + span(sp[0], sp[1], M.unit) : "") + " (median of " + plural(r.rounds.length, "round") + ")" +
          (prov.length ? "\nProvisional: " + provWhy(prov) : "") + (r.mock_saturated ? "\nThe CPUs of the scripted model were saturated: this number shows the model as well." : "") + "\nClick for where it comes from.";
        s += '<a href="' + esc(swarmHref(e, kind, h, r.n)) + '" aria-label="' + esc(shortName(h) + ", " + agents(r.n)) + '">' +
          (sp ? '<line class="whisker" x1="' + x.toFixed(1) + '" x2="' + x.toFixed(1) + '" y1="' + Y(sp[0]).toFixed(1) + '" y2="' + Y(sp[1]).toFixed(1) + '"/>' : "") +
          "<circle" + (r.mock_saturated ? ' class="sat"' : prov.length ? ' class="prov"' : "") + ' cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="4.2" data-tip="' + esc(tip) + '"/></a>';
      });
      if (line.length) { var last = line[line.length - 1]; ends.push({ name: shortName(h), colour: h.colour, x: X(last.n), y: Y(last.med[key]) }); }
      if (a.stop) (stops[a.stop.n] = stops[a.stop.n] || []).push({ h: h, a: a });
      s += "</g>";
    });
    Object.keys(stops).forEach(function (n) {
      stops[n].forEach(function (x, i, all) {
        var cx = X(Number(n)) + (i - (all.length - 1) / 2) * 7, cy = H - B, tip = shortName(x.h) + ": " + agents(x.a.stop.n) + " " + stopWord(I, e, x.a.stop.cause) + "\n" + stopDetail(I, x.a.stop) + ".\nClick for the rounds of this step.";
        s += '<g class="series h-' + esc(x.h.colour) + '"><a href="' + esc(swarmHref(e, kind, x.h, x.a.stop.n)) + '" aria-label="' + esc(shortName(x.h) + ", " + agents(x.a.stop.n) + ", stopped") + '"><path class="stopx" d="M' + (cx - 3.5).toFixed(1) + " " + (cy - 7) + "l7 7m0 -7l-7 7" + '"/><circle class="hitc" cx="' + cx.toFixed(1) + '" cy="' + (cy - 3.5) + '" r="7" data-tip="' + esc(tip) + '"/></a></g>';
      });
    });
    s += endLabels(ends, f);
    return '<div class="svgwrap">' + s + "</svg></div>";
  }
  // ---- the Agent swarming page: the same skeleton as every metrics section. A picker with a row for each workload (RPC or print mode, without and with the ten extensions) and a column for each
  // metric under its kind, one primary chart for the chosen cell, and the table of every metric. A cell is `<kind>.<metric>` in the `m` parameter of the URL; the default is the agents that fit in RPC mode.
  // The metric words are the same for the two modes: the 95th percentile is a turn's latency in RPC mode and an agent's time to finish in print mode.
  var AG_COLS = [
    { id: "fit", lens: "fit", word: "agents that fit", title: "Agents that fit", keys: { rpc: "fit", print: "fit" } },
    { id: "cpu", lens: "cpu", word: "per turn or task", title: "CPU per turn or task", keys: { rpc: "cpu_ms_per_agent_turn", print: "cpu_ms_per_agent_turn" } },
    { id: "rate", lens: "wall", word: "turns or tasks per second", title: "Turns or tasks per second", keys: { rpc: "turns_per_s", print: "turns_per_s" } },
    { id: "p95", lens: "wall", word: "95th percentile", title: "95th percentile of a turn or a task", keys: { rpc: "latency_ms_p95", print: "wall_ms_p95" } },
    { id: "mem", lens: "memory", word: "per agent", title: "Memory per agent", keys: { rpc: "mem_per_agent_mib", print: "mem_per_agent_mib" } },
    { id: "peak", lens: "memory", word: "whole container", title: "Memory of the whole container", keys: { rpc: "mem_peak_mib", print: "mem_peak_mib" } }];
  var AG_KINDS = ["rpc", "print", "rpc-ext10", "print-ext10"];
  var AG_FIT_ABOUT = "The most agents that all finished inside the memory limit. The search doubles the number of agents, then bisects between the last number that finished and the first that did not.";
  // the cells of the picker for one envelope: [{key, kind, metric, col}] in the order of the matrix
  function agentCells(I, e) {
    var S = scaleOf(I), out = [];
    AG_KINDS.filter(function (k) { return e.kinds[k] && kindArms(I, e, k).length; }).forEach(function (k) {
      AG_COLS.forEach(function (c) {
        var m = c.keys[kindBase(k)];
        if (m === "fit" || smetric(I, k, m) && kindArms(I, e, k).some(function (h) { return e.kinds[k].arms[h.id].rungs.some(function (r) { return r.status === "ok" && ok(r.med[m]); }); })) out.push({ key: k + "." + m, kind: k, metric: m, col: c });
      });
    });
    return out;
  }
  function agentTitle(I, c) { return c.metric === "fit" ? "Agents that fit" : smetric(I, c.kind, c.metric).title; }
  // the value of a metric at one number of agents for the harnesses that finished it, as bars from zero with the range of the rounds as a whisker
  function commonN(I, e, kind, key, hs) {
    var arms = kindArms(I, e, kind, hs).filter(function (h) { return e.kinds[kind].arms[h.id].rungs.some(function (r) { return r.status === "ok" && ok(r.med[key]); }); }), n = null;
    arms.forEach(function (h) {
      var ns = e.kinds[kind].arms[h.id].rungs.filter(function (r) { return r.status === "ok" && ok(r.med[key]); }).map(function (r) { return r.n; });
      n = n === null ? ns : n.filter(function (x) { return ns.indexOf(x) >= 0; });
    });
    return n && n.length ? { n: Math.max.apply(null, n), arms: arms } : null;
  }
  function scaleBars(I, e, kind, key, c) {
    var M = smetric(I, kind, key), top = 0, rows = c.arms.map(function (h) {
      var r = e.kinds[kind].arms[h.id].rungs.filter(function (x) { return x.n === c.n; })[0], sp = r.spread && r.spread[key];
      top = Math.max(top, sp ? sp[1] : r.med[key]);
      return { h: h, r: r, sp: sp };
    });
    top = top * 1.04 || 1;
    return barRows(rows.map(function (x) {
      var prov = provRuns(I, rungRuns(x.r));
      return { h: x.h, f: x.r.med[key] / top, label: val(x.r.med[key], M.unit), href: swarmHref(e, kind, x.h, c.n), whisker: x.sp ? [x.sp[0] / top, x.sp[1] / top] : null,
        tip: shortName(x.h) + ": " + agents(c.n) + "\n" + M.title + " " + val(x.r.med[key], M.unit) + (x.sp ? "\nrounds " + span(x.sp[0], x.sp[1], M.unit) : "") + " (median of " + plural(x.r.rounds.length, "round") + ")" +
          (prov.length ? "\nProvisional: " + provWhy(prov) : "") + "\nClick for where it comes from." };
    }), {});
  }
  // why a harness has no row for one kind of swarm: its manifest says it cannot run it (Can't run), or the run has no arm for it (Not in this test)
  function armAbsent(e, kind, h) {
    var a = e.kinds[kind].arms[h.id];
    if (a && a.cannot) return { h: h, na: true, cant: true, why: a.cannot, tip: shortName(h) + ": " + noteOf(a.cannot) };
    return { h: h, na: true, tip: shortName(h) + ": it was not run on this workload in this run" };
  }
  var AG_SHORT = { fit: "Agents that fit", cpu: "CPU per turn or task", rate: "Turns or tasks per second", p95: "95th percentile", mem: "Memory per agent", peak: "Container memory" };
  // the tables of every metric: one table for each workload (RPC or print mode, without and with the ten extensions), a row for each harness that ran it and a column for each metric that has a value:
  // the number of agents that fit and each per-agent metric at the largest number that finished (the row says which; every value is one click from its derivation). {html, count}
  function agentsTables(I, e, st, cells, id) {
    var items = [], count = 0;
    if (!st.hs.length) return { html: '<p class="empty">Pick at least one harness.</p>', count: 0 };
    AG_KINDS.filter(function (k) { return e.kinds[k]; }).forEach(function (k) {
      var mine = cells.filter(function (x) { return x.kind === k; }), rows = [], absent = [];
      st.hs.forEach(function (h) {
        var a = e.kinds[k].arms[h.id];
        if (!a || !a.rungs || a.cannot) { absent.push(armAbsent(e, k, h)); return; }
        var r = a.rungs.filter(function (x) { return x.n === a.max_ok && x.status === "ok"; })[0], v = {};
        mine.forEach(function (c) { v[c.col.id] = c.metric === "fit" ? fitSpan(a).v : r && ok(r.med[c.metric]) ? r.med[c.metric] : null; });
        rows.push({ h: h, a: a, r: r, v: v });
      });
      var cols = mine.filter(function (c) { return rows.some(function (rw) { return ok(rw.v[c.col.id]); }); });
      if (!rows.length || !cols.length) return;
      var head = '<th scope="col" class="hcol" data-csv-label="Harness">Harness</th>' + cols.map(function (c) {
        var m = c.metric === "fit" ? null : smetric(I, k, c.metric);
        return '<th scope="col" class="num mcol" data-csv-label="' + esc(AG_SHORT[c.col.id] + " (" + (m ? unitOf(m.unit) : "agents") + ")") + '" title="' + esc(c.col.title) + '"><div class="mh"><span class="mw">' + esc(AG_SHORT[c.col.id]) + "</span></div></th>";
      }).join("");
      var body = rows.map(function (rw) {
        var h = rw.h;
        return '<tr class="h-' + esc(h.colour) + '"><th scope="row" class="hn1" data-csv-value="' + esc(h.name) + '">' + hname(h) + (rw.r ? '<small class="ver">metrics at ' + esc(agents(rw.r.n)) + "</small>" : "") + "</th>" + cols.map(function (c) {
          var v = rw.v[c.col.id], m = c.metric === "fit" ? null : smetric(I, k, c.metric);
          if (!ok(v)) return '<td class="num na" data-csv-value="">–</td>';
          if (!m) return '<td class="num" data-csv-value="' + v + '">' + (rw.a.max_ok ? '<a href="' + esc(swarmHref(e, k, h, rw.a.max_ok)) + '"' : "<span") + ' data-tip="' + esc(stopTip(I, e, h, rw.a, k !== kindBase(k))) + '"><span class="cv"><b>' + esc(fitLabel(rw.a)) + "</b></span>" + (rw.a.max_ok ? "</a>" : "</span>") + "</td>";
          var sp = rw.r.spread && rw.r.spread[c.metric], p = parts(v, m.unit);
          return '<td class="num" data-csv-value="' + v + '"><a href="' + esc(swarmHref(e, k, h, rw.r.n)) + '" data-tip="' + esc(shortName(h) + ": " + m.title + " " + val(v, m.unit) + (sp ? "\nrounds " + span(sp[0], sp[1], m.unit) : "") + "\nClick for where it comes from.") + '"><span class="cv"><b>' + esc(p[0]) + "</b>" + (p[1] ? "<small>" + esc(p[1]) + "</small>" : "") + "</span></a></td>";
        }).join("") + "</tr>";
      }).join("");
      items.push({ title: e.kinds[k].title, absent: absent, html: '<div class="tablewrap"><table class="data grid" id="t-' + esc(id) + "-" + esc(k) + '" data-csv-group="' + esc(id) + '" data-csv-workload="' + esc(e.kinds[k].title) + '" style="--n:' + cols.length + '"><thead><tr>' + head + "</tr></thead><tbody>" + body + "</tbody></table></div>" });
      count += cols.length;
    });
    return items.length ? { html: tableBlocks(I, st, items), count: count } : { html: '<p class="empty">' + NO_VALUE + "</p>", count: 0 };
  }
  // what stands behind the numbers: the limits of the container, how each metric is made, the runs
  function agentsHow(I, e, kinds) {
    var S = scaleOf(I), seen = {}, defs = "";
    kinds.forEach(function (k) {
      smetrics(I, k).filter(function (m) { return S.charts[kindBase(k)].indexOf(m.key) >= 0 || m.key === "start_cpu_ms_per_agent"; }).forEach(function (m) {
        var id = m.title + "|" + m.about;
        if (seen[id]) return;
        seen[id] = 1;
        defs += "<tr><th>" + esc(m.title) + " <small>" + esc(unitOf(m.unit)) + "</small></th><td>" + esc(m.about) + (m.tex ? '<div class="eq">' + m.tex + "</div>" : "") + "</td></tr>";
      });
    });
    var legacy = e.kinds.rpc && e.kinds.rpc.cpu_legacy ? '<p class="muted">CPU per agent-turn is not drawn for RPC agents in this run. This run measured the CPU of the container over the whole sample, start-up included, while turns per second counts the turn phase only, so the two cannot be read together. A run made after the change measures both over the same phase.</p>' : "";
    return '<details class="more"><summary>The limits of the test and how each number is made</summary><section class="card" id="envelope"><table class="kv"><tr><th>' + term(I, "envelope", "Memory limit") + "</th><td>" + esc(limitOf(e)) + ". Memory and swap are the same number, so the container cannot swap.</td></tr>" +
      "<tr><th>" + term(I, "cpuset", "Cores") + "</th><td>" + esc(cores(e.cores)) + (e.cpus.length ? ": <code>" + esc(e.cpus.join(",")) + "</code>" : "") + ". The CPU quota is the same number of cores.</td></tr>" +
      "<tr><th>" + term(I, "pids-limit", "Process limit") + "</th><td>64 for each agent and 1,024 more, so that it is not the first limit a swarm meets" + (ok(e.pids_max) ? ". The largest probe set " + esc(group(e.pids_max)) + " processes." : ".") + "</td></tr>" +
      "<tr><th>Network</th><td>None, except the link to the scripted model.</td></tr><tr><th>Runs</th><td>" + e.runs.map(function (r) { return '<a href="runs/' + esc(r) + '/raw.json"><code>' + esc(r) + "</code></a>"; }).join(", ") + "</td></tr></table></section>" +
      '<section class="card" id="scale-how"><table class="kv">' + defs + "</table>" + legacy + '<p class="muted">A probe is ' + term(I, "rung", "complete") + " when every agent is ready and done. The " + term(I, "agent-turn", "agent-turns") + " run in " + term(I, "lockstep", "lockstep") + ". The " + term(I, "p95", "95th percentile") + " is taken over the turns of all agents.</p></section></details>";
  }

  // the body of the Agent swarming section
  function agentsBody(ctx, I, route, st, sec) {
    var S = scaleOf(I), e = envOf(I, route.params.e), cells = agentCells(I, e), kinds = AG_KINDS.filter(function (k) { return e.kinds[k] && kindArms(I, e, k).length; });
    var pick = S.envelopes.length > 1 ? seg(S.envelopes.map(function (x) { return [x.id, x.label]; }), e.id, function (v) { return 'data-href="' + esc(withParam(route, "e", v)) + '"'; }) : "";
    var old = false, sat = 0, ids = [];
    kinds.forEach(function (k) { kindArms(I, e, k, st.hs).forEach(function (h) { var a = e.kinds[k].arms[h.id]; if (!a.exact) old = true; a.rungs.forEach(function (r) { if (r.mock_saturated) sat++; ids = ids.concat(rungRuns(r)); }); }); });
    var prov = provRuns(I, ids);
    var warn = sat ? '<div class="caveat" role="note"><b>⚠ The scripted model was saturated</b><p>In ' + plural(sat, "probe") + ", its CPUs were fully used (" + term(I, "mock-saturated", "what this means") + "). Those numbers show the model as well as the harness.</p></div>" : "";
    var why = old ? '<details class="why"><summary>Why do some bars show a range?</summary><div>A run made before the search only doubled the number of agents. For it a bar starts at the largest number that finished and the whisker reaches the number before the first that did not: the true number is in between.</div></details>' : "";
    var head = '<div class="pagehead"><h1>' + esc(sec.title) + '</h1><p class="lede">' + esc(sec.about) + ' <a class="how" href="' + esc(link("method")) + '">How it works</a></p>' + (prov.length ? '<p class="provline">' + provBadge(prov) + "</p>" : "") + why +
      (pick ? '<div class="pagetools">' + pick + "</div>" : "") + "</div>";
    var cols = AG_COLS.filter(function (c) { return cells.some(function (x) { return x.col === c; }); });
    var dflt = cells.length ? cells[0].key : "", want = (route.params.m || [])[0], sel = cells.filter(function (x) { return x.key === want; })[0] || cells[0];
    var matrix = matrixCard({ rows: kinds.map(function (k) { return { id: k, title: e.kinds[k].title }; }), cols: cols.map(function (c) { return { id: c.id, lens: c.lens, word: c.word, col: c }; }),
      on: function (ks) { return ks[0] === sel.key; }, href: function (ks) { return esc(withParam(route, "m", ks[0] === dflt ? "" : ks[0])); },
      cell: function (r, c) {
        var x = cells.filter(function (y) { return y.kind === r.id && y.col === c.col; })[0];
        return x ? { keys: [x.key], label: e.kinds[x.kind].title + ": " + agentTitle(I, x), tip: e.kinds[x.kind].title + ": " + agentTitle(I, x) + "\n" + (x.metric === "fit" ? AG_FIT_ABOUT : smetric(I, x.kind, x.metric).about) } : null;
      } });
    var common = sel.metric === "fit" ? null : commonN(I, e, sel.kind, sel.metric, st.hs);
    var views = sel.metric === "fit" ? [["bars", "Bars"]] : (common ? [["bars", "Bars"]] : []).concat([["line", "Line"]]);
    var view = views.filter(function (v) { return v[0] === route.params.view; })[0] ? route.params.view : views[0][0];
    var switcher = '<div class="viewbar"><span class="lbl">View</span>' + seg(views, view, function (v) { return 'data-href="' + esc(withParam(route, "view", v === views[0][0] ? "" : v)) + '"'; }) + "</div>";
    var title = e.kinds[sel.kind].title + ": " + agentTitle(I, sel), sub, chart, about;
    if (sel.metric === "fit") {
      about = AG_FIT_ABOUT;
      sub = "The most agents that finished in " + limitOf(e) + " and " + cores(e.cores) + ". The whisker is the range the number is in. Bars are on a log scale.";
      chart = st.hs.length ? fitBars(I, e, sel.kind, { hs: st.hs, solo: true }) : '<p class="empty">Pick at least one harness.</p>';
    } else {
      var M = smetric(I, sel.kind, sel.metric), note = snote(I, sel.kind, sel.metric), lg = LOG_KEYS.indexOf(sel.metric) >= 0, level = sel.kind === "rpc" && sel.metric === "turns_per_s" && e.cores > 1 && e.cores < Math.max.apply(null, e.kinds.rpc.ns);
      about = M.about;
      sub = unitOf(M.unit) + (note ? ", " + note : "") + (M.direction === "higher" ? ", higher is better" : ", lower is better") + (view === "line" ? ", against the number of agents" + (lg ? ", log scale" : "") + (level ? ". Right of the dashed line: turns per second with all CPUs busy." : ".") :
        ". Median with the range of the rounds, at " + agents(common.n) + ", the most that every harness here finished.");
      chart = !st.hs.length ? '<p class="empty">Pick at least one harness.</p>' : (view === "line" ? scaleChart(I, e, sel.kind, sel.metric, { width: chartWidth(ctx, 1), hs: st.hs }) : scaleBars(I, e, sel.kind, sel.metric, common)) +
        absentNote(I, null, st.hs.filter(function (h) { var a = e.kinds[sel.kind].arms[h.id]; return !(a && a.rungs && !a.cannot && a.rungs.some(function (r) { return r.status === "ok" && ok(r.med[sel.metric]); })); }).map(function (h) { return armAbsent(e, sel.kind, h); }));
    }
    var primary = card(ctx, { id: "agents-main", cls: "small", title: esc(title), sub: esc(sub), chart: chart,
      tools: '<a class="info" href="' + esc(link("method")) + '" aria-label="About this metric" data-tip="' + esc(about + "\nClick for how the swarm is run.") + '">i</a>' });
    var tables = agentsTables(I, e, st, cells, "all-agent-swarming"), table = card(ctx, { id: "all-agent-swarming", title: "All metrics in this section (" + tables.count + ")", tools: csvBtn("all-agent-swarming"), body: tables.html });
    return head + warn + matrix + switcher + primary + table + agentsHow(I, e, kinds);
  }

  // a dot for each round on a line from the smallest to the largest value of the row
  function roundStrip(values, lo, hi, fmtv) {
    var W = 120, H = 18, X = function (v) { return hi > lo ? 6 + (v - lo) / (hi - lo) * (W - 12) : W / 2; };
    return '<svg class="mini" viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="one dot for each round"><line x1="6" x2="' + (W - 6) + '" y1="9" y2="9"/>' +
      values.map(function (v, i) { return '<circle cx="' + X(v).toFixed(1) + '" cy="9" r="3" data-tip="' + esc("Round " + (i + 1) + ": " + fmtv(v)) + '"/>'; }).join("") + "</svg>";
  }

  // where one mark comes from: one row for each value of one probed number of agents (median, range, a dot for each round that tried it) and one worked line
  function viewSwarm(ctx, I, route) {
    var S = scaleOf(I), e = S && envOf(I, route.args[0]), kind = route.args[1], h = I.bySlug[route.args[2]], n = Number(route.args[3]);
    var a = e && e.kinds[kind] && h && e.kinds[kind].arms[h.id], r = a && a.rungs && a.rungs.filter(function (x) { return x.n === n; })[0];
    if (!r) return notFound(I);
    var rounds = r.rounds, ms = smetrics(I, kind), keys = ms.map(function (m) { return m.key; }).filter(function (k) { return rounds.some(function (x) { return k in x.values; }); });
    var head = ["Value", { h: "Median", num: true }, { h: "Smallest to largest round", num: true }, "Each round"];
    var trs = keys.map(function (k) {
      var M = smetric(I, kind, k), vs = rounds.filter(function (x) { return k in x.values; }).map(function (x) { return x.values[k]; }), lo = Math.min.apply(null, vs), hi = Math.max.apply(null, vs);
      return [td(esc(M.title), M.title), td("<b>" + esc(val(r.med[k], M.unit)) + "</b>", r.med[k]), td(vs.length > 1 ? (hi > lo ? esc(span(lo, hi, M.unit)) : "the same") : "", lo),
        td(vs.length > 1 ? roundStrip(vs, lo, hi, function (v) { return val(v, M.unit); }) : "", null)];
    });
    var good = rounds.filter(function (x) { return x.ok; }).length;
    trs.push([td("Result", "Result"), td(r.status === "ok" ? "all finished" : esc(stopWord(I, e, r.cause)), r.status), td(plural(good, "round") + " of " + rounds.length + " finished", good), td("", null)]);
    // the worked line: the round whose memory per agent is the median one
    var per = rounds.filter(function (x) { return ok(x.values.mem_peak_mib) && ok(x.values.mem_baseline_mib); }).map(function (x) { return { x: x, v: (x.values.mem_peak_mib - x.values.mem_baseline_mib) / n }; });
    per.sort(function (p, q) { return p.v - q.v; });
    var mid = per.length ? per[Math.floor((per.length - 1) / 2)] : null, mem = smetric(I, kind, "mem_per_agent_mib");
    var arith = mid ? "<p>Round " + esc(mid.x.round) + " has the median value: (" + val(mid.x.values.mem_peak_mib, "MiB") + " - " + val(mid.x.values.mem_baseline_mib, "MiB") + ") / " + n + " = <b>" + val(mid.v, "MiB") + "</b> per agent.</p>" : "";
    var stop = r.status === "ok" ? null : { n: n, cause: r.cause, oom_kills: r.med.oom_kills };
    var total = a.exact ? a.limits.length : rounds.length, tried = a.exact ? (rounds.length === total ? " Every round tried this number." : " Rounds that tried this number: " + rounds.map(function (x) { return x.round; }).join(", ") + " of " + total + ".") : "";
    var sentence = r.status === "ok" ? "All " + agents(n) + " finished, in every one of " + plural(rounds.length, "round") + " that tried it." + tried :
      agents(n) + " " + esc(stopWord(I, e, r.cause)) + ": " + esc(stopDetail(I, stop)) + "." + (a.exact ? tried : " The larger steps were not tried.") + (r.failure ? '<br><small class="muted">' + esc(restate(r.failure)) + "</small>" : "");
    if (a.exact && n === a.limit) sentence += " This is the limit the page shows: the largest number that finished, in the median round.";
    var others = a.rungs.map(function (x) { return x.n === n ? "<b>" + x.n + "</b>" : '<a class="chip-r" href="' + esc(swarmHref(e, kind, h, x.n)) + '">' + x.n + (x.status === "ok" ? "" : " ✕") + "</a>"; }).join(" ");
    var skipped = (a.skipped || []).length ? '<p class="muted">Not tried: ' + a.skipped.map(function (x) { return x.n; }).join(", ") + ".</p>" : "";
    var prov = provRuns(I, rungRuns(r));
    return '<p class="crumbs"><a href="' + link() + '">Results</a> › <a href="' + esc(scaleHref(e)) + '">Agent swarming</a> › ' + esc(e.label) + " › " + esc(shortName(h)) + " › " + esc(agents(n)) + "</p>" +
      '<div class="answer h-' + esc(h.colour) + '"><div class="big">' + n + "<small>agents</small></div><div><h1>" + esc(shortName(h)) + ": " + esc(e.kinds[kind].title) + " in " + esc(limitOf(e)) + "</h1><p>" + sentence + '</p><p class="meta">workload <code>' + esc(a.exact ? a.scenario : a.scenario.replace(/N$/, n)) + "</code>" + (h.version ? " · " + esc(h.version) : "") + " " + provBadge(prov) + "</p></div></div>" +
      (r.mock_saturated ? '<div class="caveat" role="note"><b>⚠ The scripted model was saturated</b><p>Its CPUs were fully used in at least one round of this probe. The numbers show the model as well as the harness.</p></div>' : "") +
      card(ctx, { id: "swarm-rounds", title: "This number of agents, value by value", body: table(ctx, "swarm-" + e.id + "-" + kind + "-" + h.slug + "-" + n, head, trs, { tools: false }) }) +
      (arith ? card(ctx, { id: "swarm-arith", title: "Memory per agent, worked out", body: '<div class="eq">' + (mem.tex || "") + "</div>" + arith }) : "") +
      '<p class="others">Other numbers of agents tried for this harness: ' + others + "</p>" + skipped +
      '<p class="files"><a class="raw" href="runs/' + esc(e.runs[0]) + '/raw.json">raw.json</a> holds every field of every sample, and its probes, of this number of agents.</p>';
  }

  // the tile of the overview: the exact limits of the first memory limit, as the same paired bars
  function agentsTile(ctx, I, st, href) {
    var S = scaleOf(I), e = S.envelopes[0], k = KINDS.filter(function (x) { return kindArms(I, e, x).length; })[0];
    var rows = st.hs.map(function (h) { var a = e.kinds[k].arms[h.id]; return a && a.rungs && a.rungs.length ? { h: h, v: fitSpan(a).v, text: fitLabel(a) } : null; }).filter(Boolean);
    return '<a class="card tile" href="' + esc(href) + '"><h2>Agent swarming</h2><p class="tile-m">Agents that fit in ' + esc(limitOf(e)) + ", " + esc(k === "rpc" ? "RPC mode" : "print mode") + "</p>" + fitBars(I, e, k, { plain: true, hs: st.hs }) + tileRange(rows) + "</a>";
  }

  // ------------------------------------------------------------------ the frame around every view
  var NAV = [[HOME, "Results"], ["harnesses", "Harnesses"], ["method", "Method"], ["about", "About"]];
  var ACTIVE = { r: HOME, all: HOME, metric: HOME, cell: HOME, swarm: HOME, fault: HOME, harness: "harnesses", glossary: "method", doc: "method", logs: "method" };
  var VIEWS = { grid: viewHome, r: viewSection, all: viewAll, harnesses: viewHarnesses, harness: viewHarness, metric: viewMetric, cell: viewCell, swarm: viewSwarm, fault: viewFault, method: viewMethod, glossary: viewGlossary, doc: viewDoc, about: viewAbout, logs: viewLogs };
  var TITLES = { grid: "Results", all: "All metrics", harnesses: "Harnesses", harness: "Harness", metric: "Metric", cell: "How this number is made", swarm: "Where this swarm number comes from", fault: "Where this fault result comes from", method: "Method", glossary: "Glossary", doc: "Document", about: "About", logs: "Logs" };


  // the mark: a few short needles over parallel lines, some crossing a line (Buffon's needle), in the text colour
  var LOGO = '<svg class="logo" width="26" height="26" viewBox="0 0 32 32" aria-hidden="true"><g fill="none" stroke="currentColor"><g stroke-width="2"><path d="M1 6H31M1 15H31M1 24H31" opacity=".5"/></g><path d="M7 11L12 2M4 20L12 18M20 19L26 29" stroke-width="3.4" stroke-linecap="round"/></g></svg>';
  // the source repository, linked from the top right of every page
  var REPO = "https://github.com/MichaelKinsy/buffon";
  var GITHUB = '<svg width="17" height="17" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>';
  function frame(I, route, body) {
    var D = I.D, active = ACTIVE[route.view] || route.view;
    var demo = D.meta.demo ? '<div class="demo" role="note"><b>Demo data</b> · ' + esc(D.meta.demo) + ". Not a result of any harness.</div>" : "";
    var nav = NAV.map(function (n) { return '<a href="' + link(n[0]) + '"' + (n[0] === active ? ' aria-current="page"' : "") + ">" + esc(n[1]) + "</a>"; }).join("");
    return demo + '<header class="top"><div class="in"><a class="brand" href="' + link() + '">' + LOGO + "<span>Buffon</span></a>" +
      '<nav class="main" aria-label="Views">' + nav + '</nav><div class="right"><a class="btn icon" href="' + REPO + '" aria-label="Source code on GitHub" data-tip="Source code on GitHub">' + GITHUB + '</a><button class="btn icon" type="button" data-theme-toggle aria-label="Switch light or dark theme" data-tip="Light or dark">◐</button>' +
      '<button class="btn icon menu-btn" type="button" data-menu aria-label="Menu" aria-expanded="false">☰</button></div></div><nav class="mobile" hidden>' + nav + "</nav></header>" +
      '<main id="main">' + body + '</main><footer class="site"><div class="in">' +
      "<p>" + docLink(I, "CONTRIBUTING", "Add a harness") + " · " + docLink(I, "SUBMITTING", "Submit a result") + "</p></div></footer>";
  }

  // an address of the earlier site, and the page that took its place: a bookmark keeps working
  function redirectOf(I, route) {
    var P = route.params, v = route.view, keep = {};
    ["h", "base", "v", "api"].forEach(function (k) { if (P[k] != null && P[k] !== "" && !(Array.isArray(P[k]) && !P[k].length)) keep[k] = P[k]; });
    var has = function (id) { return I.sections.some(function (s) { return s.id === id; }); };
    if (v === "compare") return link(HOME, [], keep);
    if (v === HOME && (P.m || P.sort)) {
      var first = (P.m || []).filter(function (k) { return I.secOf[k]; })[0];
      return link(first ? "r" : HOME, first ? [I.secOf[first]] : [], keep);
    }
    if (v === "scale") return has("agent-swarming") ? link("r", ["agent-swarming"], P.e ? { e: P.e } : {}) : link(HOME, [], keep);
    if (v === "r" && route.args[0] === "many-agents") return serialize({ view: "r", args: ["agent-swarming"], params: P });   // the section's first name
    if (v === "runs") return link("method", ["runs"]);
    if (v === "doc" && route.args[0] === "README") return link("about", [], P.at ? { at: P.at } : {});
    return null;
  }

  function render(D, hash, ctx) {
    var I = ctx && ctx.index || Index(D);
    ctx = ctx || {};
    ctx.width = ctx.width || 1200;
    ctx.ui = ctx.ui || { tables: {}, sort: {} };
    var route = parse(hash), to = redirectOf(I, route);
    if (to && to !== serialize(route)) return { html: frame(I, route, '<div class="pagehead"><h1>This page moved</h1><p class="lede"><a href="' + esc(to) + '">Open its new place</a>.</p></div>'), title: "Buffon", route: route, redirect: to };
    var view = VIEWS[route.view];
    var body = view ? view(ctx, I, route) : notFound(I);
    var sec = route.view === "r" ? I.sec[route.args[0]] : null;
    return { html: explain(I, frame(I, route, body)), title: (sec ? sec.title + " · Results" : TITLES[route.view] || "Buffon") + " · Buffon", route: route };
  }

  // every route the site has: the tests render each one
  function routes(D) {
    var I = Index(D), out = ["#/", "#/?v=ratio", "#/method", "#/method/runs", "#/glossary", "#/about", "#/harnesses"], apis = {};
    D.cells.forEach(function (c) { if (c.api_short !== "-") apis[c.api_short] = 1; });
    Object.keys(apis).forEach(function (a) { out.push(link(HOME, [], { api: a }), link("all", [], { api: a })); });
    I.sections.forEach(function (s) {
      out.push(link("r", [s.id]), link("r", [s.id], { v: "ratio" }));
      if (s.empty) return;
      secApis(I, s).forEach(function (a) { out.push(link("r", [s.id], { api: a }), link("r", [s.id], { api: a, v: "ratio" })); });
      if (s.kind === "metrics") {
        ["dots", "rounds"].concat(s.id === "extensions" || s.id === "durable" ? ["line"] : []).forEach(function (v) { out.push(link("r", [s.id], { view: v })); });
        ["dots", "bars", "rounds"].forEach(function (v) { out.push(link("r", [s.id], { m: s.keys, view: v })); });   // every metric of the section, drawn in each view
        out.push(link("r", [s.id], { sort: s.keys[0] + ":desc", v: "values" }), link("r", [s.id], { m: ["none"] }));
      }
    });
    out.push(link("all"), link("all", [], { v: "values" }), link("all", [], { s: [I.sections.filter(function (s) { return !s.empty && s.kind === "metrics"; })[0].id], k: ["cpu"] }), link("all", [], { sort: "harness:desc" }));
    D.harnesses.concat(I.unmeasured).forEach(function (h) { out.push(link("harness", [h.slug])); });
    D.metrics.forEach(function (m) { out.push(link("metric", [m.key])); m.apis.forEach(function (a) { if (a !== "-") out.push(link("metric", [m.key], { api: a })); }); });
    D.docs.forEach(function (d) { if (d.slug !== "README") out.push(link("doc", [d.slug])); });
    D.runs.forEach(function (r) { if (r.logs) out.push(link("logs", [r.id])); });
    (D.faults || []).forEach(function (f) { Object.keys(f.arms).forEach(function (a) { out.push(link("fault", [f.id, I.harn[a].slug])); }); });
    if (D.scale) D.scale.envelopes.forEach(function (e) {
      out.push(scaleHref(e));
      Object.keys(e.kinds).forEach(function (k) { Object.keys(e.kinds[k].arms).forEach(function (a) { var h = D.harnesses.filter(function (x) { return x.id === a; })[0]; (e.kinds[k].arms[a].rungs || []).forEach(function (r) { out.push(swarmHref(e, k, h, r.n)); }); }); });
    });
    D.cells.forEach(function (c) {
      Object.keys(c.comparisons).forEach(function (a) { var h = D.harnesses.filter(function (x) { return x.id === a; })[0]; out.push(link("cell", [c.slug, h.slug])); });
    });
    return out;
  }

  var api = { MAIN_MAX: MAIN_MAX, render: render, routes: routes, parse: parse, serialize: serialize, Index: Index, stateOf: stateOf, toggle: toggle, explain: explain, fmt: fmt, median: median, val: val, parts: parts, span: span, sig: sig, ratioStr: ratioStr, times: times, pct: pct,
              redirectOf: function (D, hash) { var I = Index(D); return redirectOf(I, parse(hash)); } };
  if (typeof module === "object" && module.exports) { module.exports = api; return; }

  // ------------------------------------------------------------------ the browser: draw the view, wire the controls
  var D = root.BUFFON, app = document.getElementById("app"), tip = document.getElementById("tip");
  if (!D || !app) return;
  var ctx = { index: Index(D), ui: { tables: {}, sort: {} }, width: 1200 };
  var lastView = null;
  function width() { var m = document.getElementById("main"); return Math.max(320, Math.min(1180, (m ? m.clientWidth : window.innerWidth) - 48)); }
  function draw() {
    ctx.width = width();
    var out = render(D, location.hash || "#/", ctx);
    if (out.redirect) { history.replaceState(null, "", out.redirect); draw(); return; }
    var key = out.route.view + "/" + out.route.args.join("/");
    var y = window.scrollY, a = document.activeElement, keep = null;
    if (a && app.contains(a)) ["data-param", "data-sort-table", "data-view-switch"].some(function (k) {
      if (a.hasAttribute(k)) { keep = "[" + k + '="' + a.getAttribute(k) + '"]' + (a.hasAttribute("data-value") ? '[data-value="' + a.getAttribute("data-value") + '"]' : "") + (a.hasAttribute("data-col") ? '[data-col="' + a.getAttribute("data-col") + '"]' : ""); return true; }
      return false;
    });
    app.innerHTML = out.html;
    if (keep) { var again = app.querySelector(keep); if (again) again.focus({ preventScroll: true }); }
    document.title = out.title;
    if (key !== lastView) {
      window.scrollTo(0, 0);
      if (out.route.view === "glossary" && out.route.params.t) { var el = document.getElementById("g-" + out.route.params.t); if (el) el.scrollIntoView({ block: "center" }); }
    } else window.scrollTo(0, y);
    if ((out.route.view === "doc" || out.route.view === "about") && out.route.params.at) { var an = document.getElementById(out.route.params.at); if (an) an.scrollIntoView(); }
    lastView = key;
    hide();
  }
  function go(hash, replace) {
    if (replace) { history.replaceState(null, "", hash); draw(); }
    else if (location.hash === hash) draw();
    else location.hash = hash;
  }
  window.addEventListener("hashchange", draw);
  var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (Math.abs(width() - ctx.width) > 40) draw(); }, 150); });

  // theme: dark, light, or the system's, remembered
  function toggleTheme() {
    var cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    var next = cur === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("buffon:theme", next); } catch (e) {}
  }

  // tooltips: one element, for chart marks (data-tip) and terms (data-term)
  function tipText(el) {
    if (el.hasAttribute("data-tip")) return el.getAttribute("data-tip");
    var g = ctx.index.glossary[el.getAttribute("data-term")];
    return g ? (g.kind === "abbr" ? g.term + ": " + g.expands + "\n" + g.text : g.term + "\n" + g.text) : "";
  }
  function show(text, x, y) {
    tip.textContent = text; tip.classList.add("on");
    var r = tip.getBoundingClientRect(), W = window.innerWidth, H = window.innerHeight;
    tip.style.left = Math.max(8, Math.min(W - r.width - 8, x + 14)) + "px";
    tip.style.top = (y + 18 + r.height > H ? y - r.height - 12 : y + 18) + "px";
  }
  function hide() { tip.classList.remove("on"); }
  document.addEventListener("pointermove", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip],[data-term]");
    if (el) show(tipText(el), e.clientX, e.clientY); else hide();
  });
  document.addEventListener("focusin", function (e) { var el = e.target.closest && e.target.closest("[data-tip],[data-term]"); if (el) { var r = el.getBoundingClientRect(); show(tipText(el), r.left, r.bottom - 10); } });
  document.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, { passive: true });

  // spotlight: hover, focus or a tap on a harness (a mark, a bar, a row, a chip) keeps that harness at full strength and dims the others in every chart and table on the page
  var SPOT_SEL = ".series, .brow, tbody tr, .chip, .tcol", spotNow = null;
  function spotKey(el) { for (var i = 0; i < el.classList.length; i++) { var m = /^h-(\w+)$/.exec(el.classList[i]); if (m) return m[1]; } return null; }
  function spot(key) {
    if (key === spotNow) return;
    spotNow = key;
    Array.prototype.forEach.call(document.querySelectorAll(SPOT_SEL), function (el) { var k = spotKey(el); el.classList.toggle("dim", !!key && !!k && k !== key); });
  }
  function spotOf(target) { var el = target.closest && target.closest(SPOT_SEL); return el ? spotKey(el) : null; }
  document.addEventListener("pointerover", function (e) { if (e.pointerType !== "touch") spot(spotOf(e.target)); });
  document.addEventListener("focusin", function (e) { spot(spotOf(e.target)); });
  document.addEventListener("focusout", function () { spot(null); });
  document.addEventListener("pointerdown", function (e) { if (e.pointerType === "touch") spot(spotOf(e.target)); });
  window.addEventListener("hashchange", function () { spotNow = null; });

  function copy(text, button) {
    var done = function () { var old = button.textContent; button.textContent = "Copied"; setTimeout(function () { button.textContent = old; }, 1400); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); });
    else { fallback(text); done(); }
  }
  function fallback(text) { var t = document.createElement("textarea"); t.value = text; t.style.position = "fixed"; t.style.opacity = "0"; document.body.appendChild(t); t.select(); try { document.execCommand("copy"); } catch (e) {} document.body.removeChild(t); }
  // the CSV of every table of a group (`data-csv-group`): a row for each harness (for each workload, where the tables say `data-csv-workload`), a column for each column label, whatever table it is in
  function csv(id) {
    var ts = Array.prototype.slice.call(document.querySelectorAll('table[data-csv-group="' + id + '"]'));
    if (!ts.length) { var one = document.getElementById("t-" + id); if (one) ts = [one]; }
    if (!ts.length) return;
    var text = function (c) { return (c.getAttribute("data-csv-label") || c.getAttribute("data-csv-value") || c.textContent.replace(/[↑↓↕]/g, "")).trim(); };
    var quote = function (s) { return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    var labels = [], rows = [], rowOf = {}, byWorkload = ts.some(function (t) { return t.hasAttribute("data-csv-workload"); });
    ts.forEach(function (t) {
      var heads = Array.prototype.filter.call(t.querySelectorAll("thead tr"), function (tr) { return !tr.hasAttribute("data-csv-skip"); })[0].children, work = t.getAttribute("data-csv-workload") || "";
      Array.prototype.forEach.call(t.tBodies[0].rows, function (tr) {
        if (tr.hidden) return;
        var key = work + "|" + text(tr.children[0]), row = rowOf[key];
        if (!row) { row = rowOf[key] = { lead: [work, text(tr.children[0])], by: {} }; rows.push(row); }
        for (var i = 1; i < tr.children.length; i++) {
          var label = text(heads[i]);
          if (labels.indexOf(label) < 0) labels.push(label);
          row.by[label] = text(tr.children[i]);
        }
      });
    });
    var lines = [(byWorkload ? ["Workload", "Harness"] : ["Harness"]).concat(labels).map(quote).join(",")].concat(rows.map(function (r) { return (byWorkload ? r.lead : [r.lead[1]]).concat(labels.map(function (l) { return r.by[l] == null ? "" : r.by[l]; })).map(quote).join(","); }));
    var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" })); a.download = "buffon-" + id + ".csv"; document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }
  function route() { return parse(location.hash || "#/"); }

  document.addEventListener("click", function (e) {
    var b = e.target.closest("button, [data-href]");
    if (!b) {
      return;
    }
    if (b.hasAttribute("data-href")) { e.preventDefault(); go(b.getAttribute("data-href")); return; }
    if (b.hasAttribute("data-theme-toggle")) return toggleTheme();
    if (b.hasAttribute("data-menu")) { var m = app.querySelector("nav.mobile"); m.hidden = !m.hidden; b.setAttribute("aria-expanded", String(!m.hidden)); return; }
    if (b.hasAttribute("data-view-switch")) { ctx.ui.tables[b.getAttribute("data-view-switch")] = b.getAttribute("data-value") === "table"; draw(); return; }
    if (b.hasAttribute("data-sort-table")) {
      var id = b.getAttribute("data-sort-table"), col = Number(b.getAttribute("data-col")), st = ctx.ui.sort[id];
      ctx.ui.sort[id] = st && st.col === col ? { col: col, dir: st.dir === "asc" ? "desc" : "asc" } : { col: col, dir: "asc" };
      draw(); return;
    }
    if (b.hasAttribute("data-toggle-list")) {
      go(toggle(ctx.index, route(), b.getAttribute("data-value")));
      return;
    }
    if (b.hasAttribute("data-copy")) { var src = document.querySelector(b.getAttribute("data-copy")); copy(src ? src.textContent.trim() : "", b); return; }
    if (b.hasAttribute("data-copy-code")) { copy(b.parentNode.querySelector("code").textContent, b); return; }
    if (b.hasAttribute("data-csv")) { csv(b.getAttribute("data-csv")); return; }
  });
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t.hasAttribute("data-param")) go(withParam(route(), t.getAttribute("data-param"), t.value));
  });
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (t.hasAttribute("data-filter-table")) {
      var q = t.value.toLowerCase(), tb = document.getElementById("t-" + t.getAttribute("data-filter-table"));
      if (tb) Array.prototype.forEach.call(tb.tBodies[0].rows, function (row) { row.hidden = q && row.textContent.toLowerCase().indexOf(q) < 0; });
    } else if (t.hasAttribute("data-filter-glossary")) {
      var q2 = t.value.toLowerCase();
      Array.prototype.forEach.call(app.querySelectorAll(".gl"), function (g) { g.hidden = q2 && g.textContent.toLowerCase().indexOf(q2) < 0; });
      var other = document.getElementById("other-terms"); if (other && q2) other.open = true;
    }
  });
  draw();
})(this);

