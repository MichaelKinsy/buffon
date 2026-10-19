import { writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { identity, importAll, hostRoot, resolveFromHost, selfFacts, callAi } from "./common.mjs";
const isWorker = !!process.env.PROBE_WORKER;
let wt = null; try { wt = await import("node:worker_threads"); } catch {}
const data = wt?.workerData ?? {};
const out = data.out ?? process.env.PROBE_OUT, port = data.port ?? process.env.PROBE_PORT, mode = data.mode ?? process.env.PROBE_MODE;
if (data.hostArgv1) process.env.PROBE_HOST_ARGV1 = data.hostArgv1;
const res = { mode, identity: identity() };
res.bare = await importAll("bare");
res.host = await importAll("host");
const root = hostRoot();
async function load(spec) { try { const r = resolveFromHost(spec, root); if (r.file) return await import(pathToFileURL(r.file).href); } catch (e) { res.loadError = (res.loadError ?? "") + spec + ": " + e.message.split("\n")[0] + "; "; } try { return await import(spec); } catch { return null; } }
const ca = await load("@earendil-works/pi-coding-agent");
res.self = await selfFacts(ca);
const ai = await load("@earendil-works/pi-ai/compat");
res.aiCall = await callAi(ai, port);
writeFileSync(out, JSON.stringify(res, null, 1));
process.exit(0);
