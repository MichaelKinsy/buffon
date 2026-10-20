// pi-durable adapter: JSON-lines protocol v1 (docs/DURABLE-ADAPTERS.md) over @earendil-works/pi-durable.
import { readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { BACKGROUND_CONTEXT as C } from "@earendil-works/chord/context";
import { createModels } from "@earendil-works/pi-ai/models";
import type { Message, TranscriptContext } from "@earendil-works/pi-ai";
import { createRegistry, Harness, type Conversation, type LiveState } from "@earendil-works/pi-durable";
import pkg from "@earendil-works/pi-durable/package.json" with { type: "json" };
import { SqliteStorage } from "@earendil-works/pi-durable/storage/sqlite";
import { openNodeSqliteDatabase } from "@earendil-works/pi-durable/storage/sqlite/node";
import { F, Facade, out, resetSql } from "./facade.ts";
import { makeProvider, now, reduce, S, type Script, type Scripted } from "./model.ts";
import { extension, leaf, Notes } from "./tools.ts";

declare const ARM: string; // the arm id: the build defines it (--define:ARM)
const VERSIONS = { "pi-durable": pkg.version, node: process.version };
if (process.argv[2] === "--version") { out({ adapter: ARM, protocol: 1, version: pkg.version, runtime_versions: VERSIONS }); process.exit(0); }

interface Req {
	id: number; op: string; store: string; script: string; ledger: string; mode: string; conversations: number; create: boolean; window_tokens: number;
	compaction: { enabled: boolean; background_tokens: number | null }; partial_interval_ms: number | null; summary_fails: boolean;
	request_log: string | null; capture: string | null; conv: number; n: number; request_id: string; stream?: boolean; stream_file: string; reset?: boolean;
	count: number; from: number; k: number; from_turn: number; turns: number;
}
type Res = Record<string, unknown>;
type Rec = { turn: number | null; tx: number; sql: string; params: (string | number | null | { b64: string } | { i: string })[] };

let H: Harness | undefined, db: Facade, floor = false, live = false, convs: Conversation[] = [], P: Scripted;

/** The live tasks, read with the facade paused: the statements of this look are the barrier's own and are not counted. */
async function tasks() {
	F.paused = true;
	try { return (await H!.inspect(C)).tasks.filter((t) => t.state.kind !== "blocked"); } finally { F.paused = false; }
}
/** No submission in flight and no live task (a background compaction included). Before this process submits or resumes, scheduling is off and stays off. */
async function idle() {
	if (!H || !live) return;
	await H.waitForIdle(C);
	for (let w = await tasks(); w.length > 0; w = await tasks()) await Promise.allSettled(w.map((t) => H!.waitForTask(t.record.id, C)));
}

async function open(q: Req): Promise<Res> {
	S.script = JSON.parse(readFileSync(q.script, "utf8")) as Script;
	Object.assign(S, { turns: new Map(S.script.turns.map((t) => [t.n, t])), ledger: q.ledger, log: q.request_log, summaryFails: q.summary_fails, seq: 0, reqs: 0, modelNs: 0, sessions: new Map() });
	Object.assign(F, { capture: q.capture, total: 0, tx: 0, armed: 0 }); resetSql();
	db = new Facade(await openNodeSqliteDatabase(q.store));
	P = makeProvider(q.window_tokens);
	floor = q.mode === "floor"; live = false;
	const { enabled, background_tokens: bg } = q.compaction, ms = q.partial_interval_ms;
	const settings = { window_tokens: q.window_tokens, compaction_enabled: enabled, background_tokens: bg, partial_interval_ms: ms };
	if (floor) { await db.exec("CREATE TABLE IF NOT EXISTS floor_turns (turn INTEGER, round INTEGER, k INTEGER, payload TEXT)"); return { conversations: [], settings }; }
	const models = createModels(), registry = createRegistry();
	models.setProvider(P.provider);
	registry.install(extension());
	const opts = { compaction: { enabled, ...(bg === null ? {} : { backgroundTokens: bg }) }, ...(ms === null ? {} : { progress: { partialIntervalMs: ms, outputIntervalMs: ms } }) };
	H = await Harness.open(await SqliteStorage.open(db), { models, registry, settings: opts }, C);
	const agent = { model: { provider: "bench", modelId: "scripted" } };
	if (q.create) {
		convs = [await H.root(C, { agent })];
		while (convs.length < q.conversations) convs.push(await H.createConversation({ ownership: { kind: "ownerless" }, agent }, C));
	} else {
		const ids = await H.commit(async (tx) => (await tx.scanConversations({}, 1_000_000)).items.filter((r) => !r.owner).slice(0, q.conversations).map((r) => r.id), C); // no task-owned ones
		convs = await Promise.all(ids.map(async (id) => (await H!.conversation(id, C))!));
	}
	return { conversations: convs.map((c) => c.id), settings };
}

/** Section 8: the provider, the tools' effects and one four-statement transaction per round; no runtime. */
async function floorTurn(n: number) {
	const t = S.turns.get(n)!, msgs: Message[] = [{ role: "user", content: t.user, timestamp: Date.now() }];
	for (const [r, round] of t.rounds.entries()) {
		// The provider takes the transcript-context brand that only the runtime mints; the floor has no runtime.
		msgs.push(await P.stream(P.model, { messages: msgs } as unknown as TranscriptContext, { sessionId: "floor" }).result());
		for (const c of round.calls) msgs.push({ role: "toolResult", toolCallId: c.id, toolName: c.name, content: [{ type: "text", text: leaf(c.name, c.id) }], isError: false, timestamp: Date.now() });
		await db.transaction(async (tx) => {
			for (let k = 0; k < 3; k++) await tx.run("INSERT INTO floor_turns (turn, round, k, payload) VALUES (?, ?, ?, ?)", n, r, k, round.text);
			await tx.get("SELECT count(*) FROM floor_turns WHERE turn = ?", n);
		});
	}
	return { status: "done", reason: null, submission: null };
}

async function runtimeTurn(q: Req) {
	const c = convs[q.conv];
	let seen: number | null = null;
	live = true;
	const view = q.stream === true ? await c.viewState(C) : undefined;
	view?.subscribe((v) => {
		const doc = v.docs["pi.live"] as LiveState | undefined; // the view types its documents as plain JSON
		if (seen === null && doc?.generation?.message) seen = now();
	});
	const sub = await c.submit({ type: "input", content: S.turns.get(q.n)!.user, requestId: q.request_id }, C);
	const done = await sub.wait(C);
	await c.waitForIdle(C);
	view?.dispose();
	return { status: done.status, reason: done.status === "unanswered" ? [done.reason, done.detail].filter(Boolean).join(": ") : null, submission: sub.id, delta_seen_mono_ns: seen };
}

async function turn(q: Req): Promise<Res> {
	if (!S.turns.has(q.n)) return { ok: false, error: `script has no turn ${q.n}` };
	S.cur = { first: null, delta: null, ns: 0, n: 0 };
	F.turn = q.n;
	const t0 = now();
	try {
		const r = floor ? await floorTurn(q.n) : await runtimeTurn(q);
		return { delta_seen_mono_ns: null, ...r, adapter_ms: (now() - t0) / 1e6, first_request_mono_ns: S.cur.first, first_delta_mono_ns: q.stream === true ? S.cur.delta : null, model_ns: S.cur.ns, requests: S.cur.n };
	} finally { F.turn = null; }
}

/** Replay recorded statements of turns [from_turn, from_turn + turns) through the facade, one transaction per recorded transaction. */
async function floorSql(q: Req): Promise<Res> {
	const rows = readFileSync(q.stream_file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l) as Rec);
	const play = (g: Rec[]) => async (x: Pick<Facade, "run" | "all">) => {
		for (const r of g) {
			const p = r.params.map((v) => (v !== null && typeof v === "object" ? ("b64" in v ? Buffer.from(v.b64, "base64") : BigInt(v.i)) : v));
			await (/^\s*(select|with|pragma)/i.test(r.sql) ? x.all(r.sql, ...p) : x.run(r.sql, ...p));
		}
	};
	const per: number[] = [], c0 = F.total;
	let stmts = 0;
	for (let n = q.from_turn; n < q.from_turn + q.turns; n++) {
		const t0 = now(), groups: Rec[][] = [];
		for (const r of rows.filter((x) => x.turn === n)) { const g = groups.at(-1); if (r.tx !== 0 && g?.[0].tx === r.tx) g.push(r); else groups.push([r]); }
		for (const g of groups) { await (g[0].tx === 0 ? play(g)(db) : db.transaction(play(g))); stmts += g.length; }
		per.push(now() - t0);
	}
	return { stmts, commits: F.total - c0, per_turn_ns: per };
}

const stats = () => ({ sql: F.sql, provider: { requests: S.reqs, model_ns: S.modelNs } });
const OPS: Record<string, (q: Req) => Promise<Res>> = {
	open, turn, floor_sql: floorSql,
	barrier: async () => { await idle(); return { commits: F.total }; },
	stats: async (q) => { const r = stats(); if (q.reset) { resetSql(); S.reqs = S.modelNs = 0; } return r; },
	transcript: async (q) => ({ messages: (await convs[q.conv].context(C)).messages.map(reduce) }),
	doc_edit: async (q) => {
		const c = convs[q.conv];
		for (let i = 0; i < q.count; i++) await c.commit(async (tx) => { (await tx.doc(Notes, c.id)).items.push(S.script.docs[q.from + i]); }, C);
		return {};
	},
	close: async () => { await (H ? H.close(C) : db.close()); return stats(); },
	crash_after: async (q) => { F.armed = F.k = q.k; return {}; },
	resume: async () => { H!.resume(); live = true; await idle(); return { commits: F.total }; },
};

out({ event: "ready", protocol: 1, adapter: ARM, env: "native", pid: process.pid, mono_ns: now(), runtime_versions: VERSIONS });
for await (const line of createInterface({ input: process.stdin })) {
	if (!line.trim()) continue;
	const q = JSON.parse(line) as Req;
	try { out({ id: q.id, ok: true, ...((await OPS[q.op]?.(q)) ?? { ok: false, error: `unknown op ${q.op}` }) }); }
	catch (e) { out({ id: q.id, ok: false, error: e instanceof Error ? e.message : String(e) }); }
}
process.exit(0);
