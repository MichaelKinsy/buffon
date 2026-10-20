// Counting facade over Pi's own SQLite database object (protocol section 6) and crash injection (section 7).
import { appendFileSync, writeSync } from "node:fs";
import type { SqliteDatabase, SqliteExecutor, SqliteValue } from "@earendil-works/pi-durable/storage/sqlite";

const zero = () => ({ stmts: { select: 0, insert: 0, update: 0, delete: 0, ddl: 0, pragma: 0, other: 0 } as Record<string, number>, commits: 0, rollbacks: 0, params_bytes: 0, rows_returned: 0, bytes_returned: 0 });
export const F = { sql: zero(), paused: false, total: 0, armed: 0, k: 0, tx: 0, turn: null as number | null, capture: null as string | null };
export const resetSql = () => { F.sql = zero(); };

export function out(o: unknown) {
	const b = Buffer.from(JSON.stringify(o) + "\n");
	for (let i = 0; i < b.length; ) try { i += writeSync(1, b, i); } catch (e) { if ((e as NodeJS.ErrnoException).code !== "EAGAIN") throw e; }
}

const WORDS: Record<string, string> = { SELECT: "select", WITH: "select", INSERT: "insert", REPLACE: "insert", UPDATE: "update", DELETE: "delete", CREATE: "ddl", ALTER: "ddl", DROP: "ddl", PRAGMA: "pragma" };
const WRITES: Record<string, true> = { insert: true, update: true, delete: true, ddl: true };
const size = (v: unknown) => (typeof v === "string" ? Buffer.byteLength(v) : v == null ? 0 : v instanceof Uint8Array ? v.length : 8);
const LIMIT = 2n ** 53n;
const enc = (v: SqliteValue) => (v instanceof Uint8Array ? { b64: Buffer.from(v).toString("base64") } : typeof v === "bigint" ? (v > LIMIT || v < -LIMIT ? { i: String(v) } : Number(v)) : v);

function commit() {
	if (F.paused) return;
	F.sql.commits++; F.total++;
	if (F.armed && --F.armed === 0) {
		out({ event: "crashing", commit: F.total, k: F.k });
		process.kill(process.pid, "SIGKILL");
		Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 5000); // the kill lands first
	}
}

class Exec implements SqliteExecutor {
	constructor(protected d: SqliteExecutor, protected tx: number) {}
	private note(sql: string, p: SqliteValue[]) {
		if (F.paused) return false;
		const k = WORDS[/^\s*(\w+)/.exec(sql)?.[1]?.toUpperCase() ?? ""] ?? "other";
		F.sql.stmts[k]++;
		for (const v of p) F.sql.params_bytes += size(v);
		if (F.capture) appendFileSync(F.capture, JSON.stringify({ tx: this.tx, turn: F.turn, sql, params: p.map(enc) }) + "\n");
		return !this.tx && WRITES[k];
	}
	private rows<T extends object>(r: T[]) { if (!F.paused) { F.sql.rows_returned += r.length; for (const x of r) for (const v of Object.values(x)) F.sql.bytes_returned += size(v); } return r; }
	async exec(sql: string) { const w = this.note(sql, []); await this.d.exec(sql); if (w) commit(); }
	async run(sql: string, ...p: SqliteValue[]) { const w = this.note(sql, p); await this.d.run(sql, ...p); if (w) commit(); }
	async get<T extends object>(sql: string, ...p: SqliteValue[]) { this.note(sql, p); const r = await this.d.get<T>(sql, ...p); if (r) this.rows([r]); return r; }
	async all<T extends object>(sql: string, ...p: SqliteValue[]) { this.note(sql, p); return this.rows(await this.d.all<T>(sql, ...p)); }
}

export class Facade extends Exec implements SqliteDatabase {
	constructor(private db: SqliteDatabase) { super(db, 0); }
	async transaction<T>(cb: (t: SqliteExecutor) => Promise<T>): Promise<T> {
		const id = ++F.tx;
		let r: T;
		try { r = await this.db.transaction((t) => cb(new Exec(t, id))); } catch (e) { F.sql.rollbacks++; throw e; }
		commit();
		return r;
	}
	close() { return this.db.close(); }
}
