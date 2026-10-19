import { createServer } from "node:http";
import { spawn, fork } from "node:child_process";
import { Worker } from "node:worker_threads";
import { writeFileSync, existsSync, openSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { identity, importAll, selfFacts, callAi } from "./common.mjs";
import * as codingAgent from "@earendil-works/pi-coding-agent";
import * as piAi from "@earendil-works/pi-ai";

const OUT = process.env.PROBE_DIR;
const child = fileURLToPath(new URL("./child.mjs", import.meta.url));
const server = createServer((req, res) => {
  let body = ""; req.on("data", (d) => (body += d)); req.on("end", () => {
    res.writeHead(200, { "content-type": "text/event-stream" });
    const chunk = (o) => res.write(`data: ${JSON.stringify(o)}\n\n`);
    chunk({ id: "c", object: "chat.completion.chunk", created: 0, model: "probe-model", choices: [{ index: 0, delta: { role: "assistant", content: "pong" }, finish_reason: null }] });
    chunk({ id: "c", object: "chat.completion.chunk", created: 0, model: "probe-model", choices: [{ index: 0, delta: {}, finish_reason: "stop" }], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } });
    res.end("data: [DONE]\n\n");
  });
});
const port = await new Promise((r) => server.listen(0, "127.0.0.1", () => r(server.address().port)));
server.unref();

async function waitFile(p, ms) { const end = Date.now() + ms; while (Date.now() < end) { if (existsSync(p)) return true; await new Promise((r) => setTimeout(r, 200)); } return false; }

const res = { identity: identity(), staticImports: { codingAgentKeys: Object.keys(codingAgent).length, aiKeys: Object.keys(piAi).length } };
res.topLevelAiCall = await callAi(piAi, port);

export default async function (pi) {
  res.factoryAiCall = await callAi(piAi, port);
  res.dynamicImports = await importAll("bare", (s) => import(s));
  res.self = await selfFacts(codingAgent);
  pi.on("session_start", async () => {
    res.sessionAiCall = await callAi(piAi, port);
    const env = { ...process.env, PROBE_PORT: String(port), PROBE_HOST_ARGV1: process.argv[1] };
    for (const mode of ["spawn-detached", "fork", "worker"]) {
      const out = `${OUT}/child-${mode}.json`;
      const log = openSync(`${OUT}/child-${mode}.log`, "w");
      if (mode === "spawn-detached") spawn(process.execPath, [child], { detached: true, stdio: ["ignore", log, log], env: { ...env, PROBE_OUT: out, PROBE_MODE: mode } }).unref();
      if (mode === "fork") fork(child, [], { stdio: ["ignore", log, log, "ipc"], env: { ...env, PROBE_OUT: out, PROBE_MODE: mode } });
      if (mode === "worker") { try { const w = new Worker(child, { workerData: { out, port, mode, hostArgv1: process.argv[1] }, env: { ...env, PROBE_WORKER: "1" }, stdout: false, stderr: false }); w.on("error", (e) => writeFileSync(out, JSON.stringify({ mode, workerError: String(e?.stack ?? e).slice(0, 800) }))); } catch (e) { writeFileSync(out, JSON.stringify({ mode, workerError: String(e) })); } }
      res[`child-${mode}`] = (await waitFile(out, 60000)) ? "written" : "TIMEOUT";
    }
    writeFileSync(`${OUT}/ext.json`, JSON.stringify(res, null, 1));
  });
}
