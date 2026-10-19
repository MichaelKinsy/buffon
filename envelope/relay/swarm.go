package main

// Swarm mode (`relay -swarm`): the relay is the launcher of N agents that share one container. The runner talks to it over the container's standard input and output, one JSON object
// per line, so the host runs one `docker run -i` process however many agents there are, and no agent ever starts outside the container's cgroup.
//
// Commands (standard input):
//   {"op":"start","id":3,"argv":[...],"env":{...},"cwd":"...","seed":"...","home":"...","stdin":true,"keep":["agent_end","response"]}
//   {"op":"send","id":3,"data":"{...}\n"}   write to the agent's standard input
//   {"op":"closestdin","id":3}
//   {"op":"kill","id":3,"sig":9}            signal the agent's process group
//   {"op":"stats","req":1}                  the relay's own CPU and the container's cgroup counters
//   {"op":"pss","req":2,"ids":[1,2]}        proportional memory of the agents' process groups (kB), read from /proc/<pid>/smaps_rollup
//   {"op":"quit"}                           kill every agent and exit (so does the end of standard input)
//
// Events (standard output), every `t` is CLOCK_MONOTONIC in nanoseconds, the host's clock:
//   {"ev":"ready","t":...}
//   {"ev":"started","id":3,"t":...,"pid":...,"oom_adj":true}  the instant the agent's process was started, and whether its oom_score_adj was raised to 500 (below)
//   {"ev":"out","id":3,"t":...,"sent":...,"line":"..."}   a line the agent wrote to its standard output that contains one of its `keep` strings; `sent` is when the runner's last
//                                                          `send` to this agent reached its standard input, so a latency is measured on one clock inside the container
//   {"ev":"exit","id":3,"t":...,"t_start":...,"code":0,"signal":0,"err":"","stdout_tail":"...","stderr_tail":"..."}
//   {"ev":"stats","req":1,...}, {"ev":"pss","req":2,...}, {"ev":"bye"}
//
// The agent's environment is exactly `env`: the relay's own is not passed on.

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

const tailBytes = 4096

// agentOOMScoreAdj is what each agent's oom_score_adj is raised to (the default is 0, the relay's own). When the container reaches its memory limit the kernel's OOM killer picks the process with
// the highest badness, so it kills an agent, which a real orchestrator tolerates, before the launcher, which would take the whole swarm with it. Raising one's own value needs no capability
// (only lowering it below the minimum does); a child inherits it, so the agent's tools are killed first too.
const agentOOMScoreAdj = "500"

// raiseOOMScore writes agentOOMScoreAdj to /proc/<pid>/oom_score_adj of a process the relay just started, and reports whether it took. It runs at once after the start, before the agent has
// forked anything of its own (a node or Go start-up takes milliseconds); a failure is reported in the `started` event, not fatal.
func raiseOOMScore(pid int) bool {
	f, err := os.OpenFile("/proc/"+strconv.Itoa(pid)+"/oom_score_adj", os.O_WRONLY, 0)
	if err != nil {
		return false
	}
	defer f.Close()
	_, err = f.WriteString(agentOOMScoreAdj)
	return err == nil
}

type swarmCmd struct {
	Op    string            `json:"op"`
	ID    int               `json:"id"`
	Req   int               `json:"req"`
	Argv  []string          `json:"argv"`
	Env   map[string]string `json:"env"`
	Cwd   string            `json:"cwd"`
	Seed  string            `json:"seed"`
	Home  string            `json:"home"`
	Stdin bool              `json:"stdin"`
	Keep  []string          `json:"keep"`
	Data  string            `json:"data"`
	Sig   int               `json:"sig"`
	IDs   []int             `json:"ids"`
}

// tail keeps the last tailBytes bytes written to it.
type tail struct {
	mu  sync.Mutex
	buf []byte
}

func (t *tail) Write(p []byte) (int, error) {
	t.mu.Lock()
	t.buf = append(t.buf, p...)
	if len(t.buf) > 2*tailBytes {
		t.buf = append([]byte(nil), t.buf[len(t.buf)-tailBytes:]...)
	}
	t.mu.Unlock()
	return len(p), nil
}

func (t *tail) String() string {
	t.mu.Lock()
	defer t.mu.Unlock()
	b := t.buf
	if len(b) > tailBytes {
		b = b[len(b)-tailBytes:]
	}
	return strings.ToValidUTF8(string(b), "?")
}

type agent struct {
	id       int
	pid      atomic.Int64
	keep     [][]byte
	queue    chan []byte // nil closes the agent's standard input
	lastSend atomic.Int64
	out, err tail
	outBytes atomic.Int64 // bytes the agent wrote to its standard output that the relay has read
}

type swarm struct {
	events chan []byte
	mu     sync.Mutex
	agents map[int]*agent
}

func (s *swarm) emit(ev map[string]any) {
	data, err := json.Marshal(ev)
	if err != nil {
		return
	}
	s.events <- append(data, '\n')
}

func (s *swarm) writer(done chan<- struct{}) {
	w := bufio.NewWriterSize(os.Stdout, 1<<16)
	for data := range s.events {
		if data == nil { // the end: flush and stop; events from stragglers after this are dropped with the process
			break
		}
		w.Write(data)
		if len(s.events) == 0 {
			w.Flush()
		}
	}
	w.Flush()
	close(done)
}

func (s *swarm) get(id int) *agent {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.agents[id]
}

// register makes the agent known before its process exists, so a `send` that follows `start` at once finds it and waits in the queue.
func (s *swarm) register(c swarmCmd) *agent {
	a := &agent{id: c.ID}
	if c.Stdin {
		a.queue = make(chan []byte, 64)
	}
	for _, k := range c.Keep {
		a.keep = append(a.keep, []byte(k))
	}
	s.mu.Lock()
	s.agents[c.ID] = a
	s.mu.Unlock()
	return a
}

// run starts one agent and reports its exit. It runs in its own goroutine: seeding a HOME and starting a process of one agent never hold up another.
func (s *swarm) run(c swarmCmd, a *agent) {
	fail := func(code int, text string) {
		s.emit(map[string]any{"ev": "exit", "id": c.ID, "t": monotonicNs(), "t_start": 0, "code": code, "signal": 0, "err": text, "stdout_tail": "", "stderr_tail": ""})
	}
	if len(c.Argv) == 0 {
		fail(127, "no command")
		return
	}
	if c.Seed != "" && c.Home != "" {
		if err := copyTree(c.Seed, c.Home); err != nil {
			fail(126, "seeding HOME: "+err.Error())
			return
		}
	}
	cmd := exec.Command(c.Argv[0], c.Argv[1:]...)
	cmd.Dir = c.Cwd
	cmd.Env = make([]string, 0, len(c.Env))
	for k, v := range c.Env {
		cmd.Env = append(cmd.Env, k+"="+v)
	}
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	// An agent whose lines the runner does not stream (a print-mode agent: no `keep` strings) writes its output to anonymous files, and the end of each is read when it has exited: nothing
	// has to be read in time, so a launcher starved of CPU by a thousand agents cannot lose the end of an output. An agent whose lines are streamed (RPC) writes to pipes read as they come.
	files := len(a.keep) == 0
	var outR, outW, errR, errW *os.File
	var err error
	closeAll := func() {
		for _, f := range []*os.File{outR, outW, errR, errW} {
			if f != nil {
				f.Close()
			}
		}
	}
	if files {
		if outW, err = anonymousFile(); err == nil {
			errW, err = anonymousFile()
		}
	} else {
		if outR, outW, err = os.Pipe(); err == nil {
			errR, errW, err = os.Pipe()
		}
	}
	if err != nil {
		closeAll()
		fail(127, "output: "+err.Error())
		return
	}
	cmd.Stdout, cmd.Stderr = outW, errW
	var inR, inW *os.File
	if c.Stdin {
		r, w, err := os.Pipe()
		if err != nil {
			closeAll()
			fail(127, "pipe: "+err.Error())
			return
		}
		cmd.Stdin, inR, inW = r, r, w
	}
	startNs := monotonicNs()
	if err := cmd.Start(); err != nil {
		closeAll()
		if inW != nil {
			inW.Close()
			inR.Close()
		}
		fail(127, "start: "+err.Error())
		return
	}
	if !files { // the pipes' write ends belong to the agent now; the files are read back after it exits
		outW.Close()
		errW.Close()
	}
	if inR != nil {
		inR.Close()
	}
	a.pid.Store(int64(cmd.Process.Pid))
	s.emit(map[string]any{"ev": "started", "id": a.id, "t": startNs, "pid": cmd.Process.Pid, "oom_adj": raiseOOMScore(cmd.Process.Pid)})
	var readers sync.WaitGroup
	if !files {
		readers.Add(2)
	}
	go func() {
		if files {
			return
		}
		defer readers.Done()
		r := bufio.NewReaderSize(outR, 1<<14)
		for {
			line, err := r.ReadBytes('\n')
			if len(line) > 0 {
				a.outBytes.Add(int64(len(line)))
				a.out.Write(line)
				for _, k := range a.keep {
					if bytes.Contains(line, k) {
						s.emit(map[string]any{"ev": "out", "id": a.id, "t": monotonicNs(), "sent": a.lastSend.Load(), "line": strings.ToValidUTF8(string(bytes.TrimRight(line, "\r\n")), "?")})
						break
					}
				}
			}
			if err != nil {
				return
			}
		}
	}()
	go func() {
		if files {
			return
		}
		defer readers.Done()
		io.Copy(&a.err, errR)
	}()
	if inW != nil && a.queue != nil {
		go func() {
			for data := range a.queue {
				if data == nil {
					inW.Close()
					return
				}
				a.lastSend.Store(monotonicNs())
				if _, err := inW.Write(data); err != nil {
					inW.Close()
					return
				}
			}
		}()
	}
	waitErr := cmd.Wait()
	endNs := monotonicNs()
	drained := make(chan struct{})
	go func() { readers.Wait(); close(drained) }()
	complete := true
	select { // a descendant that kept the pipes open must not hold the exit event back
	case <-drained:
	case <-time.After(2 * time.Second):
		complete = false
	}
	if files {
		a.outBytes.Store(readBack(outW, &a.out))
		readBack(errW, &a.err)
	}
	closeAll()
	code, sig := 0, 0
	if waitErr != nil {
		if ee, ok := waitErr.(*exec.ExitError); ok {
			code = ee.ExitCode()
			if ws, ok := ee.Sys().(syscall.WaitStatus); ok && ws.Signaled() {
				sig = int(ws.Signal())
			}
		} else {
			code = 1
		}
	}
	s.emit(map[string]any{"ev": "exit", "id": a.id, "t": endNs, "t_start": startNs, "code": code, "signal": sig, "err": "", "stdout_tail": a.out.String(), "stderr_tail": a.err.String(), "drained": complete, "out_bytes": a.outBytes.Load()})
}

func (s *swarm) killAll() {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, a := range s.agents {
		if pid := int(a.pid.Load()); pid > 0 {
			syscall.Kill(-pid, syscall.SIGKILL)
		}
	}
}

func readInts(path string) map[string]int64 {
	out := map[string]int64{}
	text, err := os.ReadFile(path)
	if err != nil {
		return out
	}
	for _, line := range strings.Split(string(text), "\n") {
		if k, v, ok := strings.Cut(line, " "); ok {
			if n, err := strconv.ParseInt(strings.TrimSpace(v), 10, 64); err == nil {
				out[k] = n
			}
		}
	}
	return out
}

func (s *swarm) stats(req int) {
	cg := readCgroup()
	cg["memory.events"] = readInts("/sys/fs/cgroup/memory.events")
	cg["pids.events"] = readInts("/sys/fs/cgroup/pids.events")
	cpu, _ := selfCPUms()
	s.emit(map[string]any{"ev": "stats", "req": req, "t": monotonicNs(), "relay_cpu_ms": cpu, "cgroup": cg})
}

// pgrpOf is the process group of a pid, from /proc/<pid>/stat (the field after the command name, which may contain spaces and parentheses).
func pgrpOf(pid string) (int, bool) {
	data, err := os.ReadFile("/proc/" + pid + "/stat")
	if err != nil {
		return 0, false
	}
	i := bytes.LastIndexByte(data, ')')
	if i < 0 {
		return 0, false
	}
	f := strings.Fields(string(data[i+1:]))
	if len(f) < 3 {
		return 0, false
	}
	n, err := strconv.Atoi(f[2])
	return n, err == nil
}

func pssKB(pid string) (int64, bool) {
	data, err := os.ReadFile("/proc/" + pid + "/smaps_rollup")
	if err != nil {
		return 0, false
	}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "Pss:") {
			f := strings.Fields(line)
			if len(f) >= 2 {
				n, err := strconv.ParseInt(f[1], 10, 64)
				return n, err == nil
			}
		}
	}
	return 0, false
}

// pss sums the proportional set size of every process in the process groups of the asked agents.
func (s *swarm) pss(req int, ids []int) {
	want := map[int]int{} // process group -> agent id
	for _, id := range ids {
		if a := s.get(id); a != nil && a.pid.Load() > 0 {
			want[int(a.pid.Load())] = id
		}
	}
	kb := map[string]int64{}
	unreadable := 0
	entries, _ := os.ReadDir("/proc")
	for _, e := range entries {
		name := e.Name()
		if name[0] < '0' || name[0] > '9' {
			continue
		}
		pg, ok := pgrpOf(name)
		if !ok {
			continue
		}
		id, mine := want[pg]
		if !mine {
			continue
		}
		if n, ok := pssKB(name); ok {
			kb[strconv.Itoa(id)] += n
		} else {
			unreadable++
		}
	}
	s.emit(map[string]any{"ev": "pss", "req": req, "kb": kb, "unreadable": unreadable})
}

func runSwarm(listen, socket string) {
	ln, err := net.Listen("tcp", listen)
	if err != nil {
		fmt.Fprintln(os.Stderr, "relay: listen:", err)
		os.Exit(2)
	}
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go forward(c, socket)
		}
	}()
	s := &swarm{events: make(chan []byte, 1<<14), agents: map[int]*agent{}}
	done := make(chan struct{})
	go s.writer(done)
	s.emit(map[string]any{"ev": "ready", "t": monotonicNs(), "listen": ln.Addr().String()})
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	for {
		line, err := in.ReadBytes('\n')
		if len(bytes.TrimSpace(line)) > 0 {
			var c swarmCmd
			if json.Unmarshal(line, &c) != nil {
				fmt.Fprintln(os.Stderr, "relay: unreadable command:", strings.TrimSpace(string(line))[:min(200, len(strings.TrimSpace(string(line))))])
			} else {
				switch c.Op {
				case "start":
					go s.run(c, s.register(c))
				case "send":
					if a := s.get(c.ID); a != nil && a.queue != nil {
						select {
						case a.queue <- []byte(c.Data):
						default: // an agent that has not read 64 messages is not listening: the runner's wait for its answer ends in a timeout
						}
					}
				case "closestdin":
					if a := s.get(c.ID); a != nil && a.queue != nil {
						select {
						case a.queue <- nil:
						default:
						}
					}
				case "kill":
					if a := s.get(c.ID); a != nil && a.pid.Load() > 0 {
						syscall.Kill(-int(a.pid.Load()), syscall.Signal(c.Sig))
					}
				case "stats":
					go s.stats(c.Req)
				case "pss":
					go s.pss(c.Req, c.IDs)
				case "quit":
					err = io.EOF
				}
			}
		}
		if err != nil {
			break
		}
	}
	s.killAll()
	ln.Close()
	s.emit(map[string]any{"ev": "bye", "t": monotonicNs()})
	s.events <- nil
	<-done
}

// anonymousFile is a file in the temporary directory (a tmpfs in the swarm container) that is already unlinked: the agent writes to it, the relay reads it back, and nothing is left behind.
func anonymousFile() (*os.File, error) {
	f, err := os.CreateTemp("", "agent-out-")
	if err != nil {
		return nil, err
	}
	os.Remove(f.Name())
	return f, nil
}

// readBack puts the last tailBytes of f into t and returns the file's size.
func readBack(f *os.File, t *tail) int64 {
	st, err := f.Stat()
	if err != nil {
		return 0
	}
	from := st.Size() - tailBytes
	if from < 0 {
		from = 0
	}
	buf := make([]byte, st.Size()-from)
	n, _ := f.ReadAt(buf, from)
	t.Write(buf[:n])
	return st.Size()
}
