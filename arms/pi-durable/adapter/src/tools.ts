// The four tools (protocol section 5), the child task and the notes document, through the runtime's own definition APIs.
import { appendFileSync } from "node:fs";
import { Type } from "@earendil-works/pi-ai";
import { defineDoc, defineExtension, defineTask, defineTool } from "@earendil-works/pi-durable";
import { callOf, S } from "./model.ts";

export const Notes = defineDoc<{ items: string[] }>({ kind: "bench.notes", version: 1, scope: "conversation", history: "rewindable", fork: "asOf", initial: () => ({ items: [] }) });

const Child = defineTask({
	name: "bench.child", version: 1, initial: () => ({ phase: "run" as const }),
	phases: { run: (_t, rt, c) => rt.commit(() => ({ status: "terminal", outcome: { status: "completed", result: null } }), c) }, abort: (_t, rt, c) => rt.commit(() => ({ status: "terminal", outcome: { status: "aborted" } }), c),
});

/** Run a leaf tool: append to the ledger (lookup, effect) and return the scripted result. */
export function leaf(name: string, id: string) {
	if (name === "lookup" || name === "effect") appendFileSync(S.ledger, `${name} ${id}\n`);
	return callOf(id).result;
}
const text = (s: string) => ({ output: [{ type: "text" as const, text: s }] });
const schema = (extra: Record<string, unknown> = {}) =>
	Type.Unsafe<{ k: string; n: number }>({ type: "object", properties: { k: { type: "string" }, ...extra }, required: ["k", ...Object.keys(extra)], additionalProperties: false });

export function extension() {
	const lookup = defineTool({ ...S.script.tool, parameters: Type.Unsafe<{ k: string }>(S.script.tool.parameters), replay: "safe", execute: async (a) => text(leaf("lookup", a.k)) });
	const effect = defineTool({ name: "effect", description: "Apply an effect.", parameters: schema(), execute: async (a) => text(leaf("effect", a.k)) });
	const fanout = defineTool({
		name: "fanout", description: "Run child tasks.", parameters: schema({ n: { type: "integer" } }), replay: "safe",
		execute: async (a, api, c) => {
			const ids = [];
			for (let i = 0; i < a.n; i++) ids.push(await api.createTask(Child, { i }, { ownership: { kind: "task", taskId: api.taskId } }, c));
			await Promise.allSettled(ids.map((id) => api.waitForTask(id, c)));
			return text(leaf("fanout", a.k));
		},
	});
	const subagent = defineTool({
		name: "subagent", description: "Delegate to a subagent.", parameters: schema(), replay: "safe",
		execute: async (a, api, c) => {
			const id = await api.commit(async (tx) => {
				const own = (await tx.scanConversations({ ownerTaskId: api.taskId }, 1)).items[0];
				return own?.id ?? (await tx.createConversation({ ownership: { kind: "task", taskId: api.taskId } })).id;
			}, c);
			const sub = await (await api.conversation(id, c))!.submit({ type: "input", content: callOf(a.k).sub!.user, requestId: `subagent:${api.taskId}` }, c);
			await sub.wait(c);
			return text(leaf("subagent", a.k));
		},
	});
	return defineExtension({ name: "bench", tools: [lookup, effect, fanout, subagent], tasks: [Child] });
}
