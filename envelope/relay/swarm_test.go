package main

import (
	"bufio"
	"encoding/json"
	"io"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"testing"
	"time"
)

// swarmRelay starts `relay -swarm` and returns a way to send a command and to read the next event (with a deadline: a relay that stops answering fails the test, it does not hang it).
type swarmRelay struct {
	t      *testing.T
	cmd    *exec.Cmd
	in     io.WriteCloser
	events chan map[string]any
}

func startSwarm(t *testing.T) *swarmRelay {
	cmd := exec.Command(build(t), "-swarm", "-listen", "127.0.0.1:0", "-unix", "/nonexistent.sock")
	in, _ := cmd.StdinPipe()
	out, _ := cmd.StdoutPipe()
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	r := &swarmRelay{t: t, cmd: cmd, in: in, events: make(chan map[string]any, 1024)}
	go func() {
		sc := bufio.NewScanner(out)
		sc.Buffer(make([]byte, 1<<20), 1<<24)
		for sc.Scan() {
			var ev map[string]any
			if json.Unmarshal(sc.Bytes(), &ev) == nil {
				r.events <- ev
			}
		}
		close(r.events)
	}()
	t.Cleanup(func() { in.Close(); cmd.Process.Kill(); cmd.Wait() })
	return r
}

func (r *swarmRelay) send(c map[string]any) {
	data, _ := json.Marshal(c)
	r.in.Write(append(data, '\n'))
}

func (r *swarmRelay) next(kind string) map[string]any {
	deadline := time.After(10 * time.Second)
	for {
		select {
		case ev, ok := <-r.events:
			if !ok {
				r.t.Fatalf("the relay's output ended while waiting for %q", kind)
			}
			if ev["ev"] == kind {
				return ev
			}
		case <-deadline:
			r.t.Fatalf("no %q event within 10 s", kind)
		}
	}
}

// An RPC agent: the line it answers with is forwarded when it holds a `keep` string, the others are not; the latency clock is the relay's own: `sent` precedes `t`.
func TestSwarmForwardsKeptLinesWithTheSendTimeAndExitsWhenItsInputCloses(t *testing.T) {
	r := startSwarm(t)
	r.next("ready")
	script := `while read l; do echo noise; echo "{\"type\":\"agent_end\"}"; done`
	r.send(map[string]any{"op": "start", "id": 7, "argv": []string{"sh", "-c", script}, "env": map[string]string{"PATH": "/usr/bin:/bin"}, "cwd": "/", "stdin": true, "keep": []string{"agent_end"}})
	r.send(map[string]any{"op": "send", "id": 7, "data": "go\n"}) // sent at once: it waits in the agent's queue until the process exists
	ev := r.next("out")
	if ev["id"] != float64(7) || !strings.Contains(ev["line"].(string), "agent_end") {
		t.Fatalf("out event %v", ev)
	}
	if ev["sent"].(float64) <= 0 || ev["t"].(float64) < ev["sent"].(float64) {
		t.Errorf("sent %v must precede t %v", ev["sent"], ev["t"])
	}
	r.send(map[string]any{"op": "closestdin", "id": 7})
	exit := r.next("exit")
	if exit["code"] != float64(0) || exit["id"] != float64(7) || !strings.Contains(exit["stdout_tail"].(string), "noise") {
		t.Errorf("exit event %v", exit)
	}
}

// A print-mode agent has no input: its exit code and the end of its output come back in the exit event, and its environment is exactly what it was given.
func TestSwarmReportsExitCodeOutputTailAndAnExactEnvironment(t *testing.T) {
	r := startSwarm(t)
	r.next("ready")
	r.send(map[string]any{"op": "start", "id": 1, "argv": []string{"/bin/sh", "-c", "env | sort; echo done >&2; exit 3"}, "env": map[string]string{"ONLY": "this"}, "cwd": "/"})
	exit := r.next("exit")
	out := exit["stdout_tail"].(string)
	if exit["code"] != float64(3) || !strings.Contains(out, "ONLY=this") || strings.Contains(out, "BUFFON") || strings.Contains(out, "HOME=") {
		t.Errorf("exit %v", exit)
	}
	if !strings.Contains(exit["stderr_tail"].(string), "done") || exit["t_start"].(float64) <= 0 || exit["t"].(float64) < exit["t_start"].(float64) {
		t.Errorf("exit %v", exit)
	}
}

func TestSwarmReportsASignalAndAStartFailure(t *testing.T) {
	r := startSwarm(t)
	r.next("ready")
	r.send(map[string]any{"op": "start", "id": 2, "argv": []string{"sleep", "30"}, "env": map[string]string{"PATH": "/usr/bin:/bin"}, "cwd": "/"})
	time.Sleep(200 * time.Millisecond)
	r.send(map[string]any{"op": "kill", "id": 2, "sig": 9})
	exit := r.next("exit")
	if exit["signal"] != float64(9) {
		t.Errorf("a killed agent's exit %v", exit)
	}
	r.send(map[string]any{"op": "start", "id": 3, "argv": []string{"/no/such/binary"}, "env": map[string]string{}, "cwd": "/"})
	exit = r.next("exit")
	if exit["code"] != float64(127) || !strings.Contains(exit["err"].(string), "start") {
		t.Errorf("a start failure's exit %v", exit)
	}
}

// Each agent's HOME is seeded from its own directory before it starts, and an agent's process group is signalled as a whole.
func TestSwarmSeedsEachHomeAndKillsTheWholeGroup(t *testing.T) {
	seed, home := t.TempDir(), t.TempDir()
	writeFile(t, seed+"/f", "seeded")
	r := startSwarm(t)
	r.next("ready")
	r.send(map[string]any{"op": "start", "id": 4, "argv": []string{"/bin/sh", "-c", "cat " + home + "/f; (sleep 30 &) ; sleep 30"}, "env": map[string]string{"PATH": "/usr/bin:/bin"}, "cwd": "/", "seed": seed, "home": home})
	time.Sleep(300 * time.Millisecond)
	r.send(map[string]any{"op": "kill", "id": 4, "sig": 9})
	exit := r.next("exit")
	if !strings.Contains(exit["stdout_tail"].(string), "seeded") {
		t.Errorf("exit %v", exit)
	}
}

func TestSwarmAnswersStatsAndPSSAndSaysByeOnQuit(t *testing.T) {
	r := startSwarm(t)
	r.next("ready")
	r.send(map[string]any{"op": "start", "id": 5, "argv": []string{"sleep", "30"}, "env": map[string]string{"PATH": "/usr/bin:/bin"}, "cwd": "/"})
	time.Sleep(200 * time.Millisecond)
	r.send(map[string]any{"op": "stats", "req": 11})
	st := r.next("stats")
	if st["req"] != float64(11) || st["relay_cpu_ms"].(float64) < 0 || st["cgroup"] == nil {
		t.Errorf("stats %v", st)
	}
	r.send(map[string]any{"op": "pss", "req": 12, "ids": []int{5}})
	p := r.next("pss")
	if kb, _ := p["kb"].(map[string]any); p["req"] != float64(12) || (kb["5"] == nil && p["unreadable"] == float64(0)) {
		t.Errorf("pss %v", p)
	}
	r.send(map[string]any{"op": "quit"})
	r.next("bye")
}

func writeFile(t *testing.T, path, text string) {
	if err := os.WriteFile(path, []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}
}

// The kernel kills an agent before the launcher: every agent starts with oom_score_adj raised to 500 (no capability needed), its children inherit it, and the relay's own value is not raised.
func TestSwarmRaisesEachAgentsOOMScoreAboveTheLaunchers(t *testing.T) {
	if _, err := os.Stat("/proc/self/oom_score_adj"); err != nil {
		t.Skip("no /proc/<pid>/oom_score_adj")
	}
	r := startSwarm(t)
	r.next("ready")
	script := `sleep 0.4; cat /proc/$$/oom_score_adj; (cat /proc/self/oom_score_adj)`
	r.send(map[string]any{"op": "start", "id": 1, "argv": []string{"/bin/sh", "-c", script}, "env": map[string]string{"PATH": "/usr/bin:/bin"}, "cwd": "/"})
	started := r.next("started")
	if started["oom_adj"] != true {
		t.Fatalf("the relay could not raise the agent's oom_score_adj: %v", started)
	}
	exit := r.next("exit")
	if got := strings.Fields(exit["stdout_tail"].(string)); len(got) != 2 || got[0] != "500" || got[1] != "500" {
		t.Errorf("the agent and its child saw oom_score_adj %q, want 500 and 500", exit["stdout_tail"])
	}
	own, err := os.ReadFile("/proc/" + strconv.Itoa(r.cmd.Process.Pid) + "/oom_score_adj")
	if err != nil || strings.TrimSpace(string(own)) == "500" {
		t.Errorf("the relay's own oom_score_adj is %q (%v): the launcher must stay below its agents", own, err)
	}
}

// A print-mode agent's output is read back from a file when it has exited, not from a pipe a goroutine must have emptied in time: the end of a long output is there, and a descendant that
// still holds the output open does not hold the exit event back.
func TestSwarmReadsAPrintAgentsOutputBackFromAFileAtExit(t *testing.T) {
	r := startSwarm(t)
	r.next("ready")
	script := `i=0; while [ $i -lt 3000 ]; do echo "line $i of the agent's output"; i=$((i+1)); done; echo the-end; (sleep 5 &); exit 0`
	t0 := time.Now()
	r.send(map[string]any{"op": "start", "id": 9, "argv": []string{"/bin/sh", "-c", script}, "env": map[string]string{"PATH": "/usr/bin:/bin"}, "cwd": "/"})
	exit := r.next("exit")
	if took := time.Since(t0); took > 1500*time.Millisecond {
		t.Errorf("the exit event took %v: a descendant holding the output open held it back", took)
	}
	tailText := exit["stdout_tail"].(string)
	if !strings.HasSuffix(strings.TrimSpace(tailText), "the-end") || len(tailText) > 4096 || exit["drained"] != true {
		t.Errorf("tail %d bytes, drained %v, end %q", len(tailText), exit["drained"], tailText[max(0, len(tailText)-40):])
	}
	if exit["out_bytes"].(float64) < 90000 {
		t.Errorf("out_bytes %v: the whole output was %d+ bytes", exit["out_bytes"], 90000)
	}
}
