package main

// The counting facade (protocol section 6): wraps Chord's Go node driver; counts, captures, injects crashes.

import (
	"cmp"
	"encoding/base64"
	"encoding/json"
	"os"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"

	sq "github.com/MichaelKinsy/PiG/chord/sqlite"
)

type facade struct {
	mu           sync.Mutex
	st, c        map[string]int64
	total, armed int64 // commits since open; commits left before the kill (0 = off)
	k            int64
	capture      *os.File
	txs, turn    atomic.Int64 // transaction numbers; script turn being driven (-1 outside one)
	off          atomic.Bool  // counting paused (a barrier's own statements)
}

var fc = &facade{}
var kinds = map[string]string{"SELECT": "select", "WITH": "select", "INSERT": "insert", "REPLACE": "insert", "UPDATE": "update", "DELETE": "delete", "CREATE": "ddl", "ALTER": "ddl", "DROP": "ddl", "PRAGMA": "pragma"}

func (f *facade) reset() {
	f.st = map[string]int64{"select": 0, "insert": 0, "update": 0, "delete": 0, "ddl": 0, "pragma": 0, "other": 0}
	f.c = map[string]int64{"commits": 0, "rollbacks": 0, "params_bytes": 0, "rows_returned": 0, "bytes_returned": 0}
}

// vb is the byte size of a bound or returned value (section 6.1).
func vb(v any) int64 {
	switch v := v.(type) {
	case nil:
		return 0
	case string:
		return int64(len(v))
	case []byte:
		return int64(len(v))
	}
	return 8
}

func (f *facade) add(k string, n int64) {
	if !f.off.Load() {
		f.mu.Lock()
		f.c[k] += n
		f.mu.Unlock()
	}
}

// read counts rows returned and their bytes.
func (f *facade) read(rs ...sq.SqliteRow) {
	var n int64
	for _, r := range rs {
		for _, v := range r {
			n += vb(v)
		}
	}
	f.add("rows_returned", int64(len(rs)))
	f.add("bytes_returned", n)
}

func kindOf(q string) string {
	q = strings.TrimLeft(q, " \t\r\n")
	w := strings.ToUpper(q[:min(len(q), 8)])
	return cmp.Or(kinds[w[:strings.IndexAny(w+" ", " \t\r\n(;")]], "other")
}

// note counts one statement and appends it to the capture file before it runs.
func (f *facade) note(q string, p []any, tx int64) string {
	k := kindOf(q)
	if f.off.Load() {
		return k
	}
	var n int64
	ps := make([]any, len(p))
	for i, v := range p {
		n += vb(v)
		ps[i] = v
		if b, ok := v.([]byte); ok {
			ps[i] = map[string]string{"b64": base64.StdEncoding.EncodeToString(b)}
		} else if i64, ok := v.(int64); ok && (i64 > 1<<53 || i64 < -1<<53) {
			ps[i] = map[string]string{"i": strconv.FormatInt(i64, 10)}
		}
	}
	f.mu.Lock()
	f.st[k]++
	f.c["params_bytes"] += n
	f.mu.Unlock()
	if f.capture != nil {
		var turn any
		if t := f.turn.Load(); t >= 0 {
			turn = t
		}
		line, _ := json.Marshal(map[string]any{"tx": tx, "turn": turn, "sql": q, "params": ps})
		f.capture.Write(append(line, '\n')) // one write per line: O_APPEND keeps lines whole
	}
	return k
}

// decodeParam reverses note's parameter encoding for a recorded stream: {"b64"}, {"i"}, whole numbers as int64.
func decodeParam(p any) any {
	if m, ok := p.(map[string]any); ok {
		if s, ok := m["b64"].(string); ok {
			b, _ := base64.StdEncoding.DecodeString(s)
			return b
		}
		v, _ := strconv.ParseInt(m["i"].(string), 10, 64)
		return v
	}
	if v, ok := p.(float64); ok && v == float64(int64(v)) {
		return int64(v)
	}
	return p
}

// commit counts a returned commit and kills the process after the armed k-th one.
func (f *facade) commit() {
	if f.off.Load() {
		return
	}
	f.mu.Lock()
	f.c["commits"]++
	f.total++
	total, fire := f.total, f.armed > 0
	if fire {
		f.armed--
		fire = f.armed == 0
	}
	f.mu.Unlock()
	if fire {
		emit(map[string]any{"event": "crashing", "commit": total, "k": f.k})
		syscall.Kill(os.Getpid(), syscall.SIGKILL)
	}
}

// wrap implements sq.SqliteDatabase (db set) and the transaction handle (tx set).
type wrap struct {
	in                sq.SqliteExecutor
	sq.SqliteDatabase // Close is the driver's
	tx                int64
}

func (w *wrap) write(k string, err error) error {
	if err == nil && w.tx == 0 && (k == "insert" || k == "update" || k == "delete" || k == "ddl") {
		fc.commit()
	}
	return err
}

func (w *wrap) Exec(q string) error { return w.write(fc.note(q, nil, w.tx), w.in.Exec(q)) }

func (w *wrap) Run(q string, p ...sq.SqliteValue) error {
	k := fc.note(q, p, w.tx)
	return w.write(k, w.in.Run(q, p...))
}

func (w *wrap) Get(q string, p ...sq.SqliteValue) (sq.SqliteRow, error) {
	fc.note(q, p, w.tx)
	r, err := w.in.Get(q, p...)
	if r != nil {
		fc.read(r)
	}
	return r, err
}

func (w *wrap) All(q string, p ...sq.SqliteValue) ([]sq.SqliteRow, error) {
	fc.note(q, p, w.tx)
	rs, err := w.in.All(q, p...)
	fc.read(rs...)
	return rs, err
}

// EachText forwards the driver's text fast path (sq.TextReader), counted as one select.
func (w *wrap) EachText(q string, p []sq.SqliteValue, fn func([]byte) error) error {
	fc.note(q, p, w.tx)
	return w.in.(sq.TextReader).EachText(q, p, func(t []byte) error {
		fc.add("rows_returned", 1)
		fc.add("bytes_returned", int64(len(t)))
		return fn(t)
	})
}

func (w *wrap) Transaction(cb func(sq.SqliteExecutor) error) error {
	id := fc.txs.Add(1)
	if err := w.SqliteDatabase.Transaction(func(x sq.SqliteExecutor) error { return cb(&wrap{in: x, tx: id}) }); err != nil {
		fc.add("rollbacks", 1)
		return err
	}
	fc.commit()
	return nil
}
