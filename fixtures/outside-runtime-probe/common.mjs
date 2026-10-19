import { readFileSync, existsSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

export const specs = JSON.parse(readFileSync(new URL("./exportmap.json", import.meta.url))).map((x) => x.spec);

export function identity() {
  const env = {};
  for (const [k, v] of Object.entries(process.env)) if (/^(PI_|PIG_|NODE_OPTIONS$)/.test(k)) env[k] = k.includes("KEY") || k.includes("TOKEN") ? "<set>" : v;
  return { argv: process.argv, execPath: process.execPath, execArgv: process.execArgv, node: process.versions.node, bun: process.versions.bun ?? null, env, hostRoot: hostRoot() };
}

// The package root of process.argv[1], as pi-subagents' resolveHostPeerAliases computes it.
export function hostRoot() {
  try {
    let dir = dirname(realpathSync(process.env.PROBE_HOST_ARGV1 ?? process.argv[1]));
    for (;;) {
      const pj = join(dir, "package.json");
      if (existsSync(pj)) {
        const p = JSON.parse(readFileSync(pj, "utf8"));
        if (p.name) return { dir, name: p.name, version: p.version ?? null };
      }
      const up = dirname(dir);
      if (up === dir) return null;
      dir = up;
    }
  } catch (e) { return { error: String(e) }; }
}

function pickTarget(t) {
  while (t && typeof t === "object" && !Array.isArray(t)) t = t.import ?? t.node ?? t.default ?? null;
  return typeof t === "string" ? t : null;
}

// Minimal ESM exports resolution of spec from the host package root (node_modules lookup upward, self-reference).
export function resolveFromHost(spec, root) {
  const parts = spec.split("/");
  const name = spec.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
  const sub = "." + spec.slice(name.length);
  let pkgDir = null;
  if (root.name === name) pkgDir = root.dir;
  for (let dir = root.dir; !pkgDir; ) {
    const cand = join(dir, "node_modules", name);
    if (existsSync(join(cand, "package.json"))) pkgDir = cand;
    const up = dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  if (!pkgDir) return { error: `no ${name} under ${root.dir}` };
  const pj = JSON.parse(readFileSync(join(pkgDir, "package.json"), "utf8"));
  let ex = pj.exports;
  if (ex === undefined) return sub === "." ? { file: join(pkgDir, pj.main ?? "index.js"), version: pj.version } : { error: "no exports" };
  if (typeof ex === "string" || !Object.keys(ex).some((k) => k.startsWith("."))) ex = { ".": ex };
  let target = sub in ex ? pickTarget(ex[sub]) : null;
  if (!target) for (const [k, v] of Object.entries(ex)) if (k.includes("*")) {
    const [pre, suf] = k.split("*");
    if (sub.startsWith(pre) && sub.endsWith(suf)) { const t = pickTarget(v); if (t) target = t.replace("*", sub.slice(pre.length, sub.length - suf.length)); }
  }
  if (!target) return { error: `${name} exports no ${sub}`, version: pj.version };
  return { file: join(pkgDir, target), version: pj.version };
}

function summarize(m) {
  const keys = Object.keys(m).sort();
  return { n: keys.length, hash: createHash("sha256").update(keys.join(",")).digest("hex").slice(0, 12) };
}

export async function importAll(how, imp = (s) => import(s)) {
  const out = {};
  const root = how === "host" ? hostRoot() : null;
  for (const spec of specs) {
    try {
      let target = spec;
      if (how === "host") {
        if (!root || root.error) throw new Error("no host root");
        const r = resolveFromHost(spec, root);
        if (r.error) throw new Error(r.error);
        target = pathToFileURL(r.file).href;
      }
      out[spec] = { ok: true, ...summarize(await (how === "host" ? import(target) : imp(target))) };
    } catch (e) {
      out[spec] = { ok: false, error: `${e?.code ?? ""} ${String(e?.message ?? e).split("\n")[0].slice(0, 160)}` };
    }
  }
  return out;
}

export async function selfFacts(mod) {
  const facts = {};
  for (const k of ["VERSION", "APP_NAME", "CONFIG_DIR_NAME", "ENV_AGENT_DIR"]) facts[k] = mod?.[k] ?? "<absent>";
  for (const f of ["getPackageDir", "getDocsPath", "getReadmePath", "getExamplesPath", "getAgentDir", "getCustomThemesDir", "getBinDir", "getPackageJsonPath"]) {
    try { facts[f] = typeof mod?.[f] === "function" ? mod[f]() : "<absent>"; } catch (e) { facts[f] = "throws: " + e.message; }
  }
  try { const d = facts.getPackageDir; if (typeof d === "string") { const pj = JSON.parse(readFileSync(join(d, "package.json"), "utf8")); facts.packageJson = { name: pj.name, version: pj.version, piConfig: pj.piConfig ?? null }; facts.docsExists = existsSync(join(d, "docs")); facts.readmeExists = existsSync(join(d, "README.md")); } } catch (e) { facts.packageJson = "error: " + e.message; }
  return facts;
}

export async function callAi(aiMod, port) {
  const fn = aiMod?.completeSimple ?? aiMod?.complete;
  if (typeof fn !== "function") return { error: "no completeSimple export" };
  const model = { id: "probe-model", name: "probe", api: "openai-completions", provider: "probe-provider", baseUrl: `http://127.0.0.1:${port}/v1`, reasoning: false, input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 1000, maxTokens: 100 };
  try {
    const r = await Promise.race([fn(model, { messages: [{ role: "user", content: "ping", timestamp: Date.now() }] }, { apiKey: "probe-key" }), new Promise((_, rej) => setTimeout(() => rej(new Error("timeout 15s")), 15000))]);
    return { stopReason: r.stopReason, text: (r.content ?? []).map((c) => c.text ?? "").join(""), errorMessage: r.errorMessage ?? null };
  } catch (e) { return { threw: String(e?.message ?? e).split("\n")[0].slice(0, 200) }; }
}
