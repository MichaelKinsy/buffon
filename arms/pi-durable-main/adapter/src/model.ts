// Script, scripted provider (protocol section 4) and the request log.
import { createHash } from "node:crypto";
import { appendFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import { createProvider, type Provider } from "@earendil-works/pi-ai/models";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai/utils/event-stream";
import type { AssistantMessage, AssistantMessageEvent, Message, Model, SimpleStreamOptions, Tool, TranscriptContext } from "@earendil-works/pi-ai";

export type Call = { id: string; name: string; args: Record<string, unknown>; result: string; sub?: { user: string; rounds: Round[] } };
export type Round = { text: string; calls: Call[] };
type Cfg = { chunks: number; total_ms: number };
export type Turn = { n: number; user: string; rounds: Round[]; stream: Cfg };
export type Script = { tool: Tool; summary: { text: string }; docs: string[]; turns: Turn[] };
export interface Scripted { model: Model<string>; provider: Provider; stream: typeof stream }

export const now = () => Number(process.hrtime.bigint());
export const S = {
	script: undefined as unknown as Script, turns: new Map<number, Turn>(), ledger: "", log: null as string | null, summaryFails: false,
	seq: 0, reqs: 0, modelNs: 0, cur: { first: null as number | null, delta: null as number | null, ns: 0, n: 0 }, sessions: new Map<string, { count: number; first: string; last: string; bytes: number }>(),
};
const ZERO = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
const SUMMARY = "You are a context summarization assistant."; // the runtime's own summarization system prompt opens with this
const B = Buffer.byteLength;
const sha = (t: string) => createHash("sha256").update(t).digest("hex");
const txt = (c: string | { type: string; text?: string }[]) => (typeof c === "string" ? c : c.map((b) => (b.type === "text" ? (b.text ?? "") : "")).join(""));

/** The scripted call with this id (`c<n>.<r>.<j>`). */
export function callOf(id: string) {
	const [n, r, j] = id.slice(1).split(".").map(Number);
	return S.turns.get(n)!.rounds[r].calls[j];
}

/** Section 4.3 bytes of one message. */
function bytes(m: Message) {
	let n = B(txt(m.content));
	if (m.role === "assistant") for (const b of m.content) if (b.type === "toolCall") n += B(b.name) + B(b.id);
	if (m.role === "system") for (const t of m.toolsAdded ?? []) n += B(t.name);
	return n;
}

/** Reduced form of a message (section 4.4). */
export function reduce(m: Message) {
	const t = txt(m.content), d = { n: B(t), h: sha(t), p: Array.from(t.slice(0, 48)).slice(0, 24).join("") };
	if (m.role === "user") return { r: "user", ...d };
	if (m.role === "toolResult") return { r: "tool", id: m.toolCallId, ...d, e: m.isError };
	if (m.role === "system") return { r: "system", ...d, add: (m.toolsAdded ?? []).map((x) => x.name), rem: (m.toolsRemoved ?? []).map((x) => x.name) };
	return { r: "assistant", ...d, c: m.content.flatMap((b) => (b.type === "toolCall" ? [{ id: b.id, n: b.name }] : [])), s: m.stopReason };
}

/** Section 4.3: extend the session's previous count when the context only grew, else walk it all. */
function usage(sid: string | undefined, ms: Message[], answer: number) {
	const s = sid ? S.sessions.get(sid) : undefined, key = (m: Message) => `${m.role}:${bytes(m)}`;
	const ok = s !== undefined && ms.length >= s.count && key(ms[s.count - 1]) === s.last && key(ms[0]) === s.first;
	let total = ok ? s.bytes : 0;
	for (let i = ok ? s.count : 0; i < ms.length; i++) total += bytes(ms[i]);
	if (sid) S.sessions.set(sid, { count: ms.length, first: key(ms[0]), last: key(ms[ms.length - 1]), bytes: total });
	const input = Math.ceil(total / 4), output = Math.ceil(answer / 4);
	return { ...ZERO, input, output, totalTokens: input + output };
}

/** Section 4.2: the answer from the last message alone. */
function pick(ms: Message[]): { r: Round; cfg: Cfg } | undefined {
	const m = ms[ms.length - 1];
	let t: Turn | undefined, r: Round | undefined;
	if (m.role === "user") {
		const s = txt(m.content);
		let x = /^\[t(\d+)\] /.exec(s);
		if (x) { t = S.turns.get(+x[1]); r = t?.rounds[0]; }
		else if ((x = /^\[s(\d+)\.(\d+)\.(\d+)\] /.exec(s))) { t = S.turns.get(+x[1]); r = t?.rounds[+x[2]]?.calls[+x[3]]?.sub?.rounds[0]; }
	} else if (m.role === "toolResult") {
		const [n, k] = m.toolCallId.slice(1).split(".").map(Number);
		t = S.turns.get(n); r = t?.rounds[k + 1];
	}
	return r && t ? { r, cfg: t.stream } : undefined;
}

function stream(_m: Model<string>, ctx: TranscriptContext, o?: SimpleStreamOptions) {
	const es = createAssistantMessageEventStream(), t0 = now();
	S.cur.first ??= t0;
	void (async () => {
		const ms = ctx.messages, summary = ms[0]?.role === "system" && txt(ms[0].content).startsWith(SUMMARY);
		const hit = summary ? (S.summaryFails ? undefined : { r: { text: S.script.summary.text, calls: [] as Call[] }, cfg: { chunks: 1, total_ms: 0 } }) : pick(ms);
		const content: AssistantMessage["content"] = hit?.r.text ? [{ type: "text", text: hit.r.text }] : [];
		for (const c of hit?.r.calls ?? []) content.push({ type: "toolCall", id: c.id, name: c.name, arguments: c.args as never });
		const msg: AssistantMessage = { role: "assistant", content, api: "scripted", provider: "bench", model: "scripted", timestamp: Date.now(), usage: ZERO,
			stopReason: !hit ? "error" : hit.r.calls.length ? "toolUse" : "stop" };
		if (!hit) msg.errorMessage = summary ? "scripted model: summary failed" : "scripted model: no script entry";
		msg.usage = usage(o?.sessionId, ms, bytes(msg));
		if (S.log) log(ms, summary, o);
		const part: AssistantMessage = { ...msg, content: [] };
		const ev = (type: string, i: number, more: object = {}) => es.push({ type, contentIndex: i, partial: { ...part }, ...more } as AssistantMessageEvent); // one helper for the many event shapes
		es.push({ type: "start", partial: { ...part } });
		for (const [i, b] of content.entries()) {
			if (b.type === "toolCall") { part.content[i] = { ...b, arguments: {} }; ev("toolcall_start", i); part.content[i] = b; ev("toolcall_end", i, { toolCall: b }); continue; }
			if (b.type !== "text") continue;
			const cps = Array.from(b.text), { chunks, total_ms } = hit!.cfg;
			let acc = "";
			part.content[i] = { type: "text", text: "" }; ev("text_start", i);
			for (let c = 0; c < chunks; c++) {
				if (c > 0 && total_ms > 0) await sleep(total_ms / (chunks - 1));
				const d = cps.slice(Math.floor((c * cps.length) / chunks), Math.floor(((c + 1) * cps.length) / chunks)).join("");
				part.content[i] = { type: "text", text: (acc += d) };
				S.cur.delta ??= now();
				ev("text_delta", i, { delta: d });
			}
			ev("text_end", i, { content: b.text });
		}
		es.push(msg.stopReason === "error" ? { type: "error", reason: "error", error: msg } : { type: "done", reason: msg.stopReason as "stop" | "toolUse", message: msg });
		es.end(msg);
		const dt = now() - t0; S.reqs++; S.modelNs += dt; S.cur.n++; S.cur.ns += dt;
	})();
	return es;
}

function log(ms: Message[], summary: boolean, o?: SimpleStreamOptions) {
	const tools = new Map<string, Tool>();
	for (const m of ms) if (m.role === "system") { for (const t of m.toolsRemoved ?? []) tools.delete(t.name); for (const t of m.toolsAdded ?? []) tools.set(t.name, t); }
	const list = [...tools.values()].sort((a, b) => (a.name < b.name ? -1 : 1)).map((t) => ({ name: t.name, description: t.description, parameters: t.parameters }));
	const opt = { max_tokens: o?.maxTokens, temperature: o?.temperature, reasoning: o?.reasoning, cache_retention: o?.cacheRetention };
	const options = { ...Object.fromEntries(Object.entries(opt).map(([k, v]) => [k, v ?? null])), has_session_id: !!o?.sessionId };
	appendFileSync(S.log!, JSON.stringify({ seq: S.seq++, kind: summary ? "summary" : "turn", system: { n: 0, h: sha("") }, messages: ms.map(reduce), tools: list, options }) + "\n");
}

export function makeProvider(windowTokens: number): Scripted {
	const model: Model<string> = { id: "scripted", name: "Scripted", api: "scripted", provider: "bench", baseUrl: "http://localhost:0", reasoning: false, input: ["text"],
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: windowTokens, maxTokens: 16384 };
	const provider = createProvider({ id: "bench", auth: { apiKey: { name: "Scripted", resolve: async () => ({ auth: {} }) } }, models: [model], api: { stream, streamSimple: stream } });
	return { model, provider, stream };
}
