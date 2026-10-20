package main

// pig-durable adapter: speaks docs/DURABLE-ADAPTERS.md (protocol 1) and drives PiG's durable runtime through its public packages.

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"sync/atomic"
	"time"

	"github.com/MichaelKinsy/PiG/ai"
	"github.com/MichaelKinsy/PiG/chord/delta"
	sq "github.com/MichaelKinsy/PiG/chord/sqlite"
	chordnode "github.com/MichaelKinsy/PiG/chord/sqlite/node"
	"github.com/MichaelKinsy/PiG/durable"
	"github.com/MichaelKinsy/PiG/durable/harness"
	durablesqlite "github.com/MichaelKinsy/PiG/durable/storage/sqlite"
)

type notes struct {
	Items []string `json:"items"`
}

var notesDoc = durable.DefineDoc(durable.DocDefinition[notes]{
	CommonDocDefinition: durable.CommonDocDefinition[notes]{Kind: "bench.notes", Version: 1, Initial: func() notes { return notes{Items: []string{}} }},
	DocumentSemantics:   durable.DocumentSemantics{Scope: durable.ScopeConversation, History: durable.HistoryRewindable, Fork: durable.ForkAsOf},
})

type cs struct {
	Phase string `json:"phase"`
}
type cRT = durable.TaskRuntime[durable.JsonValue, cs, durable.JsonValue, any]
type cRun = durable.RunningTask[durable.JsonValue, cs, durable.JsonValue]

// settle ends a bench.child task, which completes in its first phase.
func settle(st durable.TaskOutcomeStatus) func(context.Context, cRun, cRT) error {
	return func(c context.Context, _ cRun, rt cRT) error {
		return rt.Commit(c, func(durable.Tx, cRun) (*durable.NextTaskState[cs, durable.JsonValue], error) {
			return &durable.NextTaskState[cs, durable.JsonValue]{Status: durable.TaskTerminal, Outcome: &durable.TaskOutcome[durable.JsonValue]{Status: st}}, nil
		})
	}
}

var child = durable.DefineTask(durable.TaskDefinition[durable.JsonValue, cs, durable.JsonValue, any]{
	Name: "bench.child", Version: 1, Initial: func(durable.JsonValue) cs { return cs{Phase: "done"} },
	Phases: map[string]durable.PhaseHandler[durable.JsonValue, cs, durable.JsonValue, any]{"done": settle(durable.OutcomeCompleted)}, Abort: settle(durable.OutcomeAborted),
})

var (
	sc      *script
	pv      *prov
	h       harness.Harness
	convs   []harness.Conversation
	floorDB *wrap
	ledger  string
	started bool
)

type toolFn func(c context.Context, cl *call, n int, api durable.ToolExecutionApi) (string, error)

// tool registers one scripted tool: it returns the script's result for the call named by its k argument.
func tool(s ai.ToolSchema, safe bool, f toolFn) *durable.ToolRegistration {
	r := &durable.ToolRegistration{ToolSchema: s, Execute: func(c context.Context, a any, api durable.ToolExecutionApi) (durable.ToolExecutionResult, error) {
		args := a.(map[string]any)
		n, _ := args["n"].(float64)
		out, err := f(c, pv.calls[args["k"].(string)], int(n), api)
		return durable.ToolExecutionResult{Output: []ai.ToolResultMessageContent{ai.TextContent{Text: out}}}, err
	}}
	if safe {
		r.Replay = durable.ReplaySafe
	}
	return r
}

// schema builds a tool declaration from constants, so the JSON is always valid.
func schema(name, desc string, fanout bool) ai.ToolSchema {
	props, req := `"k":{"type":"string"}`, `["k"]`
	if fanout {
		props, req = props+`,"n":{"type":"integer"}`, `["k","n"]`
	}
	var t ai.ToolSchema
	_ = json.Unmarshal(fmt.Appendf(nil, `{"name":%q,"description":%q,"parameters":{"type":"object","properties":{%s},"required":%s,"additionalProperties":false}}`, name, desc, props, req), &t)
	return t
}

func appendLedger(line string) {
	if f, err := os.OpenFile(ledger, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644); err == nil {
		f.WriteString(line + "\n")
		f.Close()
	}
}

func extension() *durable.Extension {
	led := func(verb string) toolFn {
		return func(_ context.Context, c *call, _ int, _ durable.ToolExecutionApi) (string, error) {
			appendLedger(verb + " " + c.ID)
			return c.Result, nil
		}
	}
	fanout := func(c context.Context, cl *call, n int, api durable.ToolExecutionApi) (string, error) {
		ids := []durable.TaskId{}
		for i := range n {
			id, err := api.CreateTaskErased(c, child.Erased(), map[string]any{"i": float64(i)}, durable.TaskOptions{Ownership: durable.TaskOwnership{Kind: durable.TaskOwnedByTask, TaskId: api.TaskId()}})
			if err != nil {
				return "", err
			}
			ids = append(ids, id)
		}
		for _, id := range ids {
			if _, err := api.WaitForTask(c, id); err != nil {
				return "", err
			}
		}
		return cl.Result, nil
	}
	subagent := func(c context.Context, cl *call, _ int, api durable.ToolExecutionApi) (string, error) {
		made, err := api.Commit(c, func(tx durable.Tx) (any, error) { // a rerun finds the child it made
			tid := api.TaskId()
			if ex, err := tx.ScanConversations(durable.ConversationQuery{OwnerTaskId: &tid}, 1, nil); err != nil || len(ex.Items) > 0 {
				return ex.Items[0].Id, err
			}
			cv, err := tx.CreateConversation(durable.CreateConversationOptions{Ownership: durable.ConversationOwnership{Kind: durable.ConversationOwnedByTask, TaskId: tid}})
			return cv.Id, err
		})
		if err != nil {
			return "", err
		}
		hd, err := api.Conversation(c, made.(durable.ConversationId))
		if err != nil {
			return "", err
		}
		sub, err := hd.Submit(c, durable.SubmissionDraft{Type: durable.SubmissionTypeInput, Content: ai.UserText(cl.Sub.User), RequestId: new(fmt.Sprintf("subagent:%d", api.TaskId()))})
		if err != nil {
			return "", err
		}
		rec, err := sub.Wait(c)
		if err == nil && rec.Status != durable.SubmissionDone {
			err = fmt.Errorf("subagent submission %s", rec.Status)
		}
		return cl.Result, err
	}
	return &durable.Extension{Name: "bench", Tasks: []durable.AnyTask{child.Erased()}, Tools: []*durable.ToolRegistration{
		tool(sc.Tool, true, led("lookup")), tool(schema("effect", "Apply an effect.", false), false, led("effect")),
		tool(schema("fanout", "Run child tasks.", true), true, fanout), tool(schema("subagent", "Delegate to a subagent.", false), true, subagent)}}
}

type req struct {
	ID                        int64
	Op, Store, Script, Ledger string
	Mode                      string
	Request_id                string
	Conversations, Conv, N    int
	Create, Summary_fails     bool
	Stream                    bool
	Stream_file               string
	Window_tokens             int
	Compaction                struct {
		Enabled           bool
		Background_tokens *int
	}
	Partial_interval_ms *float64
	Request_log         *string
	Capture             *string
	Count, From, K      int
	Reset               bool
	From_turn, Turns    int
}

// barrier waits for the harness to be idle; the statements it issues are not counted.
func barrier() (map[string]any, error) {
	fc.off.Store(true)
	defer fc.off.Store(false)
	commits := map[string]any{"commits": fc.total}
	if !started || h == nil { // nothing to wait for before a first turn, or in floor mode
		return commits, nil
	}
	if err := h.WaitForIdle(ctx); err != nil {
		return nil, err
	}
	for {
		in, err := h.Inspect(ctx)
		if err != nil {
			return nil, err
		}
		live := len(in.Submissions)
		for _, t := range in.Tasks {
			if t.State.Kind != harness.TaskInspectionBlocked {
				live++
			}
		}
		if live == 0 {
			return map[string]any{"commits": fc.total}, nil
		}
		time.Sleep(time.Millisecond)
	}
}

func stats(reset bool) map[string]any {
	fc.mu.Lock()
	defer fc.mu.Unlock()
	sql := map[string]any{"stmts": fc.st}
	for k, v := range fc.c {
		sql[k] = v
	}
	out := map[string]any{"sql": sql, "provider": map[string]any{"requests": pv.reqs.Load(), "model_ns": pv.modelNs.Load()}}
	if reset {
		fc.reset()
		pv.reqs.Store(0)
		pv.modelNs.Store(0)
	}
	return out
}

func openFile(p *string) (*os.File, error) {
	if p == nil {
		return nil, nil
	}
	return os.OpenFile(*p, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
}

func open(r *req) (map[string]any, error) {
	raw, err := os.ReadFile(r.Script)
	if err != nil {
		return nil, err
	}
	sc = &script{}
	if err := json.Unmarshal(raw, sc); err != nil {
		return nil, err
	}
	pv, ledger = newProv(sc), r.Ledger
	pv.fails = r.Summary_fails
	if pv.log, err = openFile(r.Request_log); err == nil {
		fc.capture, err = openFile(r.Capture)
	}
	if err != nil {
		return nil, err
	}
	pv.model = &ai.Model{ID: "scripted", ProviderMeta: ai.ProviderMetadata{ProviderID: "bench", API: "bench"}, Input: []ai.ModelInputModality{"text"},
		Capabilities: ai.ModelCapabilities{ContextWindow: r.Window_tokens, MaxOutputTokens: 16384, SupportsToolUse: true}}
	fc.reset()
	fc.turn.Store(-1)
	db, err := chordnode.OpenNodeSqliteDatabase(r.Store, chordnode.NodeSqliteDatabaseOptions{})
	if err != nil {
		return nil, err
	}
	w := &wrap{in: db, SqliteDatabase: db}
	settings := map[string]any{"window_tokens": r.Window_tokens, "compaction_enabled": r.Compaction.Enabled, "background_tokens": r.Compaction.Background_tokens, "partial_interval_ms": r.Partial_interval_ms}
	if r.Mode == "floor" {
		floorDB = w
		return map[string]any{"conversations": []int{}, "settings": settings}, w.Exec("CREATE TABLE IF NOT EXISTS floor_turns (turn INTEGER, round INTEGER, k INTEGER, payload TEXT)")
	}
	store, err := durablesqlite.Open(w)
	if err != nil {
		return nil, err
	}
	st := &harness.HarnessSettings{Compaction: &harness.CompactionPolicyPatch{Enabled: &r.Compaction.Enabled, BackgroundTokens: r.Compaction.Background_tokens}}
	if r.Partial_interval_ms != nil {
		st.Progress = &harness.ProgressPolicyPatch{PartialIntervalMs: r.Partial_interval_ms, OutputIntervalMs: r.Partial_interval_ms}
	}
	reg := harness.CreateRegistry()
	if err := reg.Install(extension()); err != nil {
		return nil, err
	}
	if h, err = harness.OpenHarness(ctx, store, harness.HarnessOptions{Models: pv, Registry: reg, Settings: func() *harness.HarnessSettings { return st }}); err != nil {
		return nil, err
	}
	agent := &harness.AgentChange{Model: harness.SetTo(durable.ModelRef{Provider: "bench", ModelId: "scripted"})}
	root, err := h.Root(ctx, &harness.RootOptions{Agent: agent})
	if err != nil {
		return nil, err
	}
	if convs, err = conversations(r, root, agent); err != nil {
		return nil, err
	}
	ids := []int64{}
	for _, c := range convs {
		ids = append(ids, int64(c.Id()))
	}
	return map[string]any{"conversations": ids, "settings": settings}, nil
}

// conversations holds the root and the next r.Conversations-1 ownerless conversations: created, or (on an existing store) the first ones no task owns.
func conversations(r *req, root harness.Conversation, agent *harness.AgentChange) ([]harness.Conversation, error) {
	out := []harness.Conversation{root}
	if r.Create {
		for range r.Conversations - 1 {
			cv, err := h.CreateConversation(ctx, harness.ConversationCreateOptions{Ownership: durable.ConversationOwnership{Kind: durable.ConversationOwnerless}, Agent: agent})
			if err != nil {
				return nil, err
			}
			out = append(out, cv)
		}
		return out, nil
	}
	if r.Conversations <= 1 {
		return out, nil
	}
	page, err := durable.Commit(ctx, h, func(tx durable.Tx) (durable.Page[durable.ConversationRecord, durable.Cursor], error) {
		return tx.ScanConversations(durable.ConversationQuery{}, 1<<20, nil)
	})
	for _, c := range page.Items {
		if c.Id == root.Id() || c.Owner != nil || len(out) >= r.Conversations || err != nil {
			continue
		}
		var cv harness.Conversation
		if cv, err = h.Conversation(ctx, c.Id); err == nil {
			out = append(out, cv)
		}
	}
	return out, err
}

// liveText reports whether a conversation view's pi.live document holds streamed answer text.
func liveText(v harness.ConversationView) bool {
	o, ok := v.Docs.Get("pi.live")
	b, _ := json.Marshal(o)
	var l harness.LiveState
	return ok && json.Unmarshal(b, &l) == nil && l.Generation != nil && l.Generation.Message != nil && cat(l.Generation.Message.Content) != ""
}

func turnOut(out map[string]any, t0 time.Time) map[string]any {
	out["adapter_ms"] = float64(time.Since(t0).Microseconds()) / 1000
	out["model_ns"], out["requests"] = pv.tModel.Load(), pv.tReqs.Load()
	for k, a := range map[string]*atomic.Int64{"first_request_mono_ns": &pv.tFirst, "first_delta_mono_ns": &pv.tDelta, "delta_seen_mono_ns": &pv.tSeen} {
		out[k] = nil
		if v := a.Load(); v != 0 {
			out[k] = v
		}
	}
	return out
}

func doTurn(r *req) (map[string]any, error) {
	t := pv.turns[r.N]
	if t == nil {
		return nil, fmt.Errorf("script has no turn %d", r.N)
	}
	for _, a := range []*atomic.Int64{&pv.tReqs, &pv.tModel, &pv.tFirst, &pv.tDelta, &pv.tSeen} {
		a.Store(0)
	}
	started = true
	pv.timed.Store(r.Stream)
	fc.turn.Store(int64(r.N))
	defer fc.turn.Store(-1)
	t0, out := time.Now(), map[string]any{"status": "done", "reason": nil, "submission": 0}
	if floorDB != nil {
		if err := floorTurn(t); err != nil {
			return nil, err
		}
		return turnOut(out, t0), nil
	}
	cv := convs[r.Conv]
	if w, err := cv.Watch(ctx); r.Stream && err == nil {
		w.Start(func(_ context.Context, v harness.ConversationView, _ []delta.Op) error {
			if pv.tDelta.Load() != 0 && liveText(v) {
				pv.tSeen.CompareAndSwap(0, nanotime())
			}
			return nil
		})
		defer w.Stop()
	}
	sub, err := cv.Submit(ctx, durable.SubmissionDraft{Type: durable.SubmissionTypeInput, Content: ai.UserText(t.User), RequestId: &r.Request_id})
	if err != nil {
		return nil, err
	}
	rec, err := sub.Wait(ctx)
	if err != nil {
		return nil, err
	}
	out["submission"], out["reason"] = int64(sub.Id()), rec.Reason
	if rec.Status != durable.SubmissionDone {
		out["status"] = "unanswered"
	}
	if err := cv.WaitForIdle(ctx); err != nil {
		return nil, err
	}
	return turnOut(out, t0), nil
}

// floorTurn is section 8: provider, tools and four facade statements per round, no runtime.
func floorTurn(t *turn) error {
	ms := []ai.Message{ai.UserMessage{Content: ai.UserText(t.User)}}
	for ri, rd := range t.Rounds {
		ms = append(ms, *pv.CompleteSimple(ctx, pv.model, ai.Context{Messages: ms}, ai.StreamOptions{SessionID: "floor"}))
		for _, c := range rd.Calls {
			if c.Name == "lookup" || c.Name == "effect" {
				appendLedger(c.Name + " " + c.ID)
			}
			ms = append(ms, ai.ToolResultMessage{ToolCallID: c.ID, ToolName: c.Name, Content: []ai.ToolResultMessageContent{ai.TextContent{Text: c.Result}}})
		}
		err := floorDB.Transaction(func(x sq.SqliteExecutor) error {
			for k := range 3 {
				if err := x.Run("INSERT INTO floor_turns (turn, round, k, payload) VALUES (?, ?, ?, ?)", int64(t.N), int64(ri), int64(k), rd.Text); err != nil {
					return err
				}
			}
			_, err := x.Get("SELECT count(*) FROM floor_turns WHERE turn = ?", int64(t.N))
			return err
		})
		if err != nil {
			return err
		}
	}
	return nil
}

type rec struct {
	Tx, Turn int64
	Sql      string
	Params   []any
}

func replay(x sq.SqliteExecutor, q rec) (err error) {
	switch {
	case kindOf(q.Sql) == "select":
		_, err = x.All(q.Sql, q.Params...)
	case len(q.Params) == 0:
		err = x.Exec(q.Sql)
	default:
		err = x.Run(q.Sql, q.Params...)
	}
	return err
}

// floorSQL replays the captured statements of turns from_turn.. through the facade, one transaction per recorded one.
func floorSQL(r *req) (map[string]any, error) {
	f, err := os.Open(r.Stream_file)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var recs []rec
	sc := bufio.NewScanner(f)
	sc.Buffer(nil, 1<<28)
	for sc.Scan() {
		q := rec{Turn: -1}
		if err := json.Unmarshal(sc.Bytes(), &q); err != nil {
			return nil, err
		}
		if q.Turn >= int64(r.From_turn) && q.Turn < int64(r.From_turn+r.Turns) {
			for i, p := range q.Params {
				q.Params[i] = decodeParam(p)
			}
			recs = append(recs, q)
		}
	}
	per, c0 := make([]int64, r.Turns), fc.c["commits"]
	for i, j := 0, 0; i < len(recs); i = j {
		for j = i + 1; recs[i].Tx != 0 && j < len(recs) && recs[j].Tx == recs[i].Tx; j++ {
		}
		st, run := time.Now(), recs[i:j]
		if recs[i].Tx == 0 {
			err = replay(floorDB, recs[i])
		} else {
			err = floorDB.Transaction(func(x sq.SqliteExecutor) error {
				for _, q := range run {
					if err := replay(x, q); err != nil {
						return err
					}
				}
				return nil
			})
		}
		if err != nil {
			return nil, err
		}
		per[recs[i].Turn-int64(r.From_turn)] += time.Since(st).Nanoseconds()
	}
	return map[string]any{"stmts": len(recs), "commits": fc.c["commits"] - c0, "per_turn_ns": per}, sc.Err()
}

// arm is the arm id, set at build time (-X main.arm=...); the default is this arm.
var arm = "pig-durable"

func versions() map[string]string {
	return map[string]string{"pig-durable": ai.ProductVersion, "go": runtime.Version()}
}

func main() {
	if len(os.Args) > 1 && os.Args[1] == "--version" {
		emit(map[string]any{"adapter": arm, "protocol": 1, "version": ai.ProductVersion, "runtime_versions": versions()})
		return
	}
	emit(map[string]any{"event": "ready", "protocol": 1, "adapter": arm, "env": "native", "pid": os.Getpid(), "mono_ns": nanotime(), "runtime_versions": versions()})
	in := json.NewDecoder(os.Stdin)
	for {
		r := &req{}
		r.Compaction.Enabled = true
		if in.Decode(r) != nil {
			return
		}
		res, err := serve(r)
		if err != nil {
			res = map[string]any{"ok": false, "error": err.Error()}
		} else {
			res["ok"] = true
		}
		res["id"] = r.ID
		emit(res)
	}
}

func serve(r *req) (map[string]any, error) {
	if h == nil && (r.Op == "resume" || r.Op == "doc_edit" || r.Op == "transcript") {
		return nil, fmt.Errorf("%s: floor mode builds no runtime", r.Op)
	}
	switch r.Op {
	case "open":
		return open(r)
	case "turn":
		return doTurn(r)
	case "barrier":
		return barrier()
	case "resume":
		started = true
		h.Resume()
		return barrier()
	case "stats":
		return stats(r.Reset), nil
	case "close":
		res := stats(false)
		if h != nil {
			return res, h.Close(ctx)
		}
		return res, floorDB.Close()
	case "crash_after":
		fc.mu.Lock()
		fc.armed, fc.k = int64(r.K), int64(r.K)
		fc.mu.Unlock()
		return map[string]any{}, nil
	case "doc_edit":
		for i := range r.Count {
			_, err := convs[r.Conv].Commit(ctx, func(tx durable.Tx) (any, error) {
				d, err := durable.TxDoc[notes](tx, notesDoc, convs[r.Conv].Id())
				if err == nil {
					_, err = d.Array("items").Push(sc.Docs[r.From+i])
				}
				return nil, err
			})
			if err != nil {
				return nil, err
			}
		}
		return map[string]any{}, nil
	case "transcript":
		v, err := convs[r.Conv].Context(ctx, nil)
		ms := []map[string]any{}
		for _, m := range v.Messages {
			ms = append(ms, red(m))
		}
		return map[string]any{"messages": ms}, err
	case "floor_sql":
		return floorSQL(r)
	}
	return nil, fmt.Errorf("unknown op %s", r.Op)
}
