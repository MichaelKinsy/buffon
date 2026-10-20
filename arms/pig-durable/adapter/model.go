package main

// The scripted model (protocol section 4) as a durable.Models, and the script it plays.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"maps"
	"os"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"time"
	_ "unsafe"

	"github.com/MichaelKinsy/PiG/ai"
)

//go:linkname nanotime runtime.nanotime
func nanotime() int64

var ctx, outMu, enc = context.Background(), sync.Mutex{}, json.NewEncoder(os.Stdout)

func emit(v any) {
	outMu.Lock()
	enc.Encode(v)
	outMu.Unlock()
}

type call struct {
	ID, Name, Result string
	Args             map[string]any
	Sub              *struct {
		User   string
		Rounds []round
	}
}
type round struct {
	Text  string
	Calls []call
}
type stream struct {
	Chunks   int
	Total_ms float64
}
type turn struct {
	N      int
	User   string
	Rounds []round
	Stream stream
}
type script struct {
	Tool    ai.ToolSchema
	Summary struct{ Text string }
	Docs    []string
	Turns   []turn
}
type ans struct {
	rd round
	st stream
}
type sess struct {
	count, bytes int
	first, last  [2]any // (role, message bytes) of the first and last message
}

// prov is the scripted model. ans holds every answer under its O(1) key: t<n>, c<n>.<r> (after round r's tools), s<n>.<r>.<j>.
type prov struct {
	sc                                                       *script
	turns                                                    map[int]*turn
	ans                                                      map[string]ans
	calls                                                    map[string]*call
	model                                                    *ai.Model
	fails                                                    bool
	mu                                                       sync.Mutex
	sess                                                     map[string]sess
	log                                                      *os.File
	seq, reqs, modelNs, tReqs, tModel, tFirst, tDelta, tSeen atomic.Int64 // totals, then the current turn's
	timed                                                    atomic.Bool
}

func newProv(sc *script) *prov {
	p := &prov{sc: sc, turns: map[int]*turn{}, ans: map[string]ans{}, calls: map[string]*call{}, sess: map[string]sess{}}
	for i := range sc.Turns {
		t := &sc.Turns[i]
		p.turns[t.N], p.ans[fmt.Sprint("t", t.N)] = t, ans{t.Rounds[0], t.Stream}
		for r := range t.Rounds {
			if len(t.Rounds[r].Calls) > 0 {
				p.ans[fmt.Sprintf("c%d.%d", t.N, r)] = ans{t.Rounds[r+1], t.Stream}
			}
			for j := range t.Rounds[r].Calls {
				c := &t.Rounds[r].Calls[j]
				p.calls[c.ID] = c
				if c.Sub != nil {
					p.ans[fmt.Sprintf("s%d.%d.%d", t.N, r, j)] = ans{rd: c.Sub.Rounds[0]}
				}
			}
		}
	}
	return p
}

func (p *prov) GetModel(provider, id string) *ai.Model {
	if provider == "bench" && id == "scripted" {
		return p.model
	}
	return nil
}
func (p *prov) CompleteSimple(c context.Context, m *ai.Model, r ai.Context, o ...ai.StreamOptions) *ai.AssistantMessage {
	return p.StreamSimple(c, m, r, o...).Result()
}
func (p *prov) FetchDeferred(context.Context, *ai.Model, ai.DeferredHandle, ...ai.DeferredFetchOptions) *ai.AssistantMessage {
	return nil
}
func (p *prov) CancelDeferred(context.Context, *ai.Model, ai.DeferredHandle, ...ai.DeferredCancelOptions) error {
	return nil
}

func cat[T any](bs []T) (s string) {
	for _, b := range bs {
		if t, ok := any(b).(ai.TextContent); ok {
			s += t.Text
		}
	}
	return
}

// body is a message's text and the extra bytes of section 4.3 (call names and ids, tool names added).
func body(m ai.Message) (t string, extra int) {
	switch m := m.(type) {
	case ai.UserMessage:
		if s, ok := m.Content.(ai.UserText); ok {
			return string(s), 0
		}
		return cat(m.Content.(ai.UserContentBlocks)), 0
	case ai.AssistantMessage:
		for _, b := range m.Content {
			if c, ok := b.(ai.ToolCall); ok {
				extra += len(c.Name) + len(c.ID)
			}
		}
		return cat(m.Content), extra
	case ai.ToolResultMessage:
		return cat(m.Content), 0
	case ai.SystemMessage:
		for _, x := range m.ToolsAdded {
			extra += len(x.Name)
		}
		if s, ok := m.Content.(ai.SystemText); ok {
			return string(s), extra
		}
		if b, ok := m.Content.(ai.SystemTextBlocks); ok {
			return cat(b), extra
		}
		return "", extra
	}
	return "", 0
}

func size(m ai.Message) int { t, e := body(m); return len(t) + e }

func digest(t string) (string, string) {
	h, rs := sha256.Sum256([]byte(t)), []rune(t)
	return hex.EncodeToString(h[:]), string(rs[:min(24, len(rs))])
}

// red is the reduced form of a message (section 4.4).
func red(m ai.Message) map[string]any {
	t, _ := body(m)
	h, pre := digest(t)
	r := map[string]any{"n": len(t), "h": h, "p": pre, "r": "user"}
	switch m := m.(type) {
	case ai.AssistantMessage:
		cs := []map[string]string{}
		for _, b := range m.Content {
			if c, ok := b.(ai.ToolCall); ok {
				cs = append(cs, map[string]string{"id": c.ID, "n": c.Name})
			}
		}
		r["r"], r["c"], r["s"] = "assistant", cs, string(m.StopReason)
	case ai.ToolResultMessage:
		r["r"], r["id"], r["e"] = "tool", m.ToolCallID, m.IsError
	case ai.SystemMessage:
		add, rem := []string{}, []string{}
		for _, x := range m.ToolsAdded {
			add = append(add, x.Name)
		}
		for _, x := range m.ToolsRemoved {
			rem = append(rem, x.Name)
		}
		r["r"], r["add"], r["rem"] = "system", add, rem
	}
	return r
}

// find is the O(1) lookup of section 4.2 on the last message; a summary request is told by its system prompt.
func (p *prov) find(ms []ai.Message) (a ans, summary, ok bool) {
	if len(ms) == 0 {
		return
	}
	if t, _ := body(ms[0]); strings.HasPrefix(t, "You are a context summarization assistant.") {
		return ans{rd: round{Text: p.sc.Summary.Text}}, true, !p.fails
	}
	k := ""
	switch m := ms[len(ms)-1].(type) {
	case ai.ToolResultMessage:
		k = m.ToolCallID[:max(0, strings.LastIndexByte(m.ToolCallID, '.'))]
	case ai.UserMessage:
		if t, _ := body(m); strings.HasPrefix(t, "[") {
			k = t[1:max(1, strings.IndexByte(t, ']'))]
		}
	}
	a, ok = p.ans[k]
	return
}

// input is the incremental usage counter of section 4.3.
func (p *prov) input(sid string, ms []ai.Message) int {
	mk := func(m ai.Message) [2]any { return [2]any{m.MessageRole(), size(m)} }
	p.mu.Lock()
	defer p.mu.Unlock()
	st, start, bytes := p.sess[sid], 0, 0
	if sid != "" && st.count > 0 && len(ms) >= st.count && mk(ms[st.count-1]) == st.last && mk(ms[0]) == st.first {
		start, bytes = st.count, st.bytes
	}
	for _, m := range ms[start:] {
		bytes += size(m)
	}
	if sid != "" && len(ms) > 0 {
		p.sess[sid] = sess{len(ms), bytes, mk(ms[0]), mk(ms[len(ms)-1])}
	}
	return bytes
}

func (p *prov) record(kind string, r ai.Context, o ai.StreamOptions) {
	// The runtime carries tools in system messages (toolsAdded/toolsRemoved); the tools in effect are their fold.
	set := map[string]ai.ToolSchema{}
	for _, m := range r.Messages {
		if s, ok := m.(ai.SystemMessage); ok {
			for _, x := range s.ToolsRemoved {
				delete(set, x.Name)
			}
			for _, x := range s.ToolsAdded {
				set[x.Name] = x
			}
		}
	}
	tools := []map[string]any{}
	for _, n := range slices.Sorted(maps.Keys(set)) {
		tools = append(tools, map[string]any{"name": n, "description": set[n].Description, "parameters": set[n].Parameters})
	}
	opt := func(set bool, v any) any {
		if set {
			return v
		}
		return nil
	}
	h, _ := digest(r.SystemPrompt)
	ms := []map[string]any{}
	for _, m := range r.Messages {
		ms = append(ms, red(m))
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	line, _ := json.Marshal(map[string]any{"seq": p.seq.Add(1) - 1, "kind": kind, "system": map[string]any{"n": len(r.SystemPrompt), "h": h}, "messages": ms, "tools": tools,
		"options": map[string]any{"max_tokens": opt(o.MaxTokens != 0, o.MaxTokens), "temperature": opt(o.TemperatureSet, o.Temperature), "reasoning": opt(o.Thinking != "", string(o.Thinking)),
			"cache_retention": opt(o.CacheRetention != "", string(o.CacheRetention)), "has_session_id": o.SessionID != ""}})
	p.log.Write(append(line, '\n'))
}

func (p *prov) StreamSimple(_ context.Context, m *ai.Model, r ai.Context, os ...ai.StreamOptions) *ai.AssistantMessageEventStream {
	t0 := nanotime()
	var o ai.StreamOptions
	if len(os) > 0 {
		o = os[0]
	}
	p.reqs.Add(1)
	p.tReqs.Add(1)
	p.tFirst.CompareAndSwap(0, t0)
	a, summary, ok := p.find(r.Messages)
	in := (p.input(o.SessionID, r.Messages)+3)/4 + (len(r.SystemPrompt)+3)/4
	use := func(out int) ai.Usage { return ai.Usage{Input: in, Output: (out + 3) / 4, TotalTokens: in + (out+3)/4} }
	if p.log != nil {
		p.record(map[bool]string{false: "turn", true: "summary"}[summary], r, o)
	}
	s := ai.NewAssistantMessageEventStream()
	go func() {
		defer func() { d := nanotime() - t0; p.modelNs.Add(d); p.tModel.Add(d) }()
		msg := ai.AssistantMessage{API: "bench", Provider: "bench", Model: m.ID, Content: []ai.AssistantContentBlock{}, StopReason: ai.StopReasonPending, Timestamp: time.Now().UnixMilli()}
		snap := func() *ai.AssistantMessage { c := msg; c.Content = slices.Clone(msg.Content); return &c }
		if !ok {
			msg.StopReason, msg.ErrorMessage = ai.StopReasonError, map[bool]string{false: "scripted model: no script entry", true: "scripted model: summary failed"}[summary]
			msg.Usage = use(len(msg.ErrorMessage))
			s.Push(ai.ErrorEvent{Reason: ai.StopReasonError, Error: &msg})
			return
		}
		s.Push(ai.StartEvent{Partial: snap()})
		out := len(a.rd.Text)
		if rs := []rune(a.rd.Text); len(rs) > 0 {
			n, acc := max(1, a.st.Chunks), ""
			msg.Content = append(msg.Content, ai.TextContent{})
			s.Push(ai.TextStartEvent{Partial: snap()})
			for i := range n {
				if i > 0 {
					time.Sleep(time.Duration(a.st.Total_ms / float64(n-1) * float64(time.Millisecond)))
				}
				d := string(rs[i*len(rs)/n : (i+1)*len(rs)/n])
				acc += d
				msg.Content[0] = ai.TextContent{Text: acc}
				if p.timed.Load() {
					p.tDelta.CompareAndSwap(0, nanotime())
				}
				s.Push(ai.TextDeltaEvent{Delta: d, Partial: snap()})
			}
			s.Push(ai.TextEndEvent{Content: acc, Partial: snap()})
		}
		for _, c := range a.rd.Calls {
			args, idx := ai.JsonObject{}, len(msg.Content)
			for k, v := range c.Args {
				args[k] = v
			}
			msg.Content = append(msg.Content, ai.ToolCall{ID: c.ID, Name: c.Name, Arguments: ai.JsonObject{}})
			s.Push(ai.ToolCallStartEvent{ContentIndex: idx, Partial: snap()})
			msg.Content[idx] = ai.ToolCall{ID: c.ID, Name: c.Name, Arguments: args}
			s.Push(ai.ToolCallEndEvent{ContentIndex: idx, ToolCall: msg.Content[idx].(ai.ToolCall), Partial: snap()})
			out += len(c.Name) + len(c.ID)
		}
		msg.StopReason = map[bool]ai.StopReason{false: ai.StopReasonStop, true: ai.StopReasonToolUse}[len(a.rd.Calls) > 0]
		msg.Usage, msg.Timestamp = use(out), time.Now().UnixMilli()
		s.Push(ai.DoneEvent{Reason: msg.StopReason, Message: &msg})
	}()
	return s
}
