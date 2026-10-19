// SPDX-License-Identifier: MIT

package main

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"maps"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

// fakeRoot writes a fake /proc and /sys under a temporary root.
func fakeRoot(t *testing.T, files map[string]string) string {
	t.Helper()
	root := t.TempDir()
	base := map[string]string{
		"proc/self/status":                 "Name:\tbuffon\nCpus_allowed:\tff\nCpus_allowed_list:\t0-7\n",
		"proc/cpuinfo":                     "processor\t: 0\nmodel name\t: Example CPU @ 2.00GHz\n\nprocessor\t: 1\nmodel name\t: Example CPU @ 2.00GHz\n",
		"proc/stat":                        "cpu  1 2 3 4 5 6 7 8 9 10\ncpu0 0 0 0 100 0 0 0 0 0 0\ncpu1 0 0 0 100 0 0 0 0 0 0\n",
		"proc/sys/kernel/osrelease":        "6.1.0-test\n",
		"proc/loadavg":                     "0.50 0.40 0.30 1/100 42\n",
		"sys/devices/system/cpu/online":    "0-7\n",
		"sys/fs/cgroup/cgroup.controllers": "cpu memory\n",
		"sys/fs/cgroup/cpu.stat":           "usage_usec 1000\nuser_usec 800\nsystem_usec 200\nnr_periods 10\nnr_throttled 2\nthrottled_usec 3000\n",
		"sys/fs/cgroup/cpu.max":            "200000 100000\n",
		"sys/fs/cgroup/memory.max":         "8589934592\n",
		"sys/devices/system/cpu/cpu2/cpufreq/scaling_governor": "performance\n",
	}
	maps.Copy(base, files)
	for path, content := range base {
		full := filepath.Join(root, path)
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return root
}

// procStat renders /proc/stat with the given user and idle ticks for CPUs 0..len(idle)-1.
func procStat(user, idle []int) string {
	var b strings.Builder
	b.WriteString("cpu  1 2 3 4 5 6 7 8 9 10\n")
	for i := range idle {
		b.WriteString("cpu" + itoa(i) + " " + itoa(user[i]) + " 0 0 " + itoa(idle[i]) + " 0 0 0 0 0 0\n")
	}
	return b.String()
}

func itoa(n int) string { return strconv.Itoa(n) }

// tarOf is a gzip tar holding one file named name.
func tarOf(t *testing.T, name string) []byte {
	t.Helper()
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gz)
	if err := tw.WriteHeader(&tar.Header{Name: name, Mode: 0o644, Size: 1, Typeflag: tar.TypeReg}); err != nil {
		t.Fatal(err)
	}
	_, _ = tw.Write([]byte("x"))
	if err := errors.Join(tw.Close(), gz.Close()); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

// testPod is a pod environment over a fake root, with a fake taskset that runs its command and a fetch that records
// the archive it was offered.
type testPod struct {
	env      podEnv
	root     string
	data     string
	archive  []byte
	fetched  bool
	stdout   bytes.Buffer
	appRoot  string
	pinWaits int
}

func newTestPod(t *testing.T, files map[string]string) *testPod {
	t.Helper()
	p := &testPod{root: fakeRoot(t, files), data: t.TempDir(), appRoot: t.TempDir()}
	taskset := filepath.Join(t.TempDir(), "taskset")
	// The fake taskset records the CPU list and runs the command.
	if err := os.WriteFile(taskset, []byte("#!/bin/sh\n[ \"$1\" = -c ] || exit 64\necho \"$2\" > \"$BUFFON_OUT/taskset-cpus\"\nshift 2\nexec \"$@\"\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	p.env = podEnv{
		sys: system{root: p.root}, root: p.appRoot, data: p.data, node: "node-a", pod: "pod-a",
		getenv: func(k string) string {
			return map[string]string{"BUFFON_DELIVERY": "image", "BUFFON_IMAGE_REF": "registry.example/buffon@sha256:" + strings.Repeat("a", 64)}[k]
		},
		pinWait: func(context.Context) error { p.pinWaits++; return nil },
		fetchWait: func(_ context.Context, marker string) error {
			if filepath.Base(marker) != "FETCHED" {
				t.Errorf("waits for %s", marker)
			}
			data, err := os.ReadFile(filepath.Join(p.data, "out.tar.gz"))
			p.archive, p.fetched = data, err == nil
			return err
		},
		now:     func() time.Time { return time.Date(2026, 10, 11, 12, 0, 0, 0, time.UTC) },
		taskset: func() (string, error) { return taskset, nil },
	}
	return p
}

func (p *testPod) lines(t *testing.T) []map[string]any {
	t.Helper()
	var out []map[string]any
	for line := range strings.Lines(p.stdout.String()) {
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			t.Fatalf("pod printed a line that is not JSON: %q", line)
		}
		out = append(out, m)
	}
	return out
}

func (p *testPod) types(t *testing.T) string {
	var ts []string
	for _, l := range p.lines(t) {
		ts = append(ts, l["t"].(string))
	}
	return strings.Join(ts, ",")
}

// unpacked unpacks the archive the pod handed back.
func (p *testPod) unpacked(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	if err := unpack(p.archive, dir); err != nil {
		t.Fatal(err)
	}
	return dir
}

// writerSession is a session whose command writes a raw.json and the environment it saw into {out}/run.
func writerSession(cpus int, pin string) *session {
	return &session{Run: "buffon-overhead-20261011t120000", CPUs: cpus, Pin: pin, TimeoutSeconds: 60,
		Env:  map[string]string{"BUFFON_WORKLOAD": "overhead"},
		Argv: []string{"sh", "-c", `mkdir -p "$1/run" && printf '{"samples":{}}' > "$1/run/raw.json" && env | grep -E '^(BUFFON_|GOMAXPROCS=)' | sort > "$1/run/env.txt" && echo "{root}" > "$1/run/root.txt" && echo session-output`, "sh", "{out}"}}
}

func TestPodRunsTheSessionOnTheQuietestCoresAndHandsBackItsRunDirectory(t *testing.T) {
	flat := []int{100, 100, 100, 100, 100, 100, 100, 100}
	p := newTestPod(t, map[string]string{"proc/stat": procStat(flat, flat)})
	// Between the two readings cores 3 and 5 stay idle; the rest are busy. Before it, core 0 was the idlest.
	p.env.pinWait = func(context.Context) error {
		p.pinWaits++
		return os.WriteFile(filepath.Join(p.root, "proc/stat"), []byte(procStat([]int{190, 180, 190, 100, 190, 101, 190, 190}, []int{110, 120, 110, 200, 110, 199, 110, 110})), 0o644)
	}
	if err := runPod(context.Background(), writerSession(2, "auto"), p.env, &p.stdout); err != nil {
		t.Fatal(err)
	}
	if got := p.types(t); got != "facts,pin,cpu,out,done" {
		t.Fatalf("lines %s:\n%s", got, p.stdout.String())
	}
	pin := p.lines(t)[1]
	if pin["method"] != "quietest" || pin["cpus"] != "3,5" || pin["gomaxprocs"] != float64(2) || pin["fixedClock"] != true || p.pinWaits != 1 {
		t.Errorf("pin %v", pin)
	}
	if !p.fetched {
		t.Fatal("the pod never waited for the runner's fetch")
	}
	dir := p.unpacked(t)
	for _, name := range []string{"run/raw.json", "session.log", "cluster-facts.json", "taskset-cpus"} {
		if _, err := os.Stat(filepath.Join(dir, name)); err != nil {
			t.Errorf("the hand-back lacks %s", name)
		}
	}
	env, _ := os.ReadFile(filepath.Join(dir, "run/env.txt"))
	for _, want := range []string{"BUFFON_PINNED_CPUS=3,5", "GOMAXPROCS=2", "BUFFON_WORKLOAD=overhead", "BUFFON_OUT=" + filepath.Join(p.data, "out", "buffon-overhead-20261011t120000")} {
		if !strings.Contains(string(env), want) {
			t.Errorf("session environment lacks %s:\n%s", want, env)
		}
	}
	// The session reads the pod's facts from the file BUFFON_POD_FACTS names (buffon/envelope/pod.py).
	podFacts := filepath.Join(p.data, "pod-facts.json")
	if !strings.Contains(string(env), "BUFFON_POD_FACTS="+podFacts) {
		t.Errorf("session environment lacks BUFFON_POD_FACTS:\n%s", env)
	}
	if data, err := os.ReadFile(podFacts); err != nil || !strings.Contains(string(data), `"requestedCpus":2`) || !strings.Contains(string(data), `"cpuSet":"shared"`) {
		t.Errorf("pod facts %s %v", data, err)
	}
	if cpus, _ := os.ReadFile(filepath.Join(dir, "taskset-cpus")); strings.TrimSpace(string(cpus)) != "3,5" {
		t.Errorf("taskset got %q", cpus)
	}
	if root, _ := os.ReadFile(filepath.Join(dir, "run/root.txt")); strings.TrimSpace(string(root)) != p.appRoot {
		t.Errorf("{root} became %q", root)
	}
	var facts map[string]any
	data, _ := os.ReadFile(filepath.Join(dir, "cluster-facts.json"))
	if err := json.Unmarshal(data, &facts); err != nil {
		t.Fatal(err)
	}
	sess := facts["session"].(map[string]any)
	if facts["node"] != "node-a" || facts["cpuSet"] != "shared" || facts["kernel"] != "6.1.0-test" || facts["cpuModel"] != "Example CPU @ 2.00GHz" || sess["exit"] != float64(0) || facts["pin"].(map[string]any)["cpus"] != "3,5" {
		t.Errorf("facts %s", data)
	}
	// The cgroup counters did not move in the fake root: the delta is zero, and it is recorded.
	if sess["usageUsec"] != float64(0) || sess["nrThrottled"] != float64(0) {
		t.Errorf("session counters %v", sess)
	}
}

func TestPodRefusesCoresWhoseClockScalesButHandsBackTheFacts(t *testing.T) {
	p := newTestPod(t, map[string]string{
		"proc/self/status": "Cpus_allowed_list:\t2-3\n",
		"sys/devices/system/cpu/cpu3/cpufreq/scaling_governor": "schedutil\n",
	})
	err := runPod(context.Background(), writerSession(2, "auto"), p.env, &p.stdout)
	if err == nil || !strings.Contains(err.Error(), "CPU 3 (schedutil)") {
		t.Fatalf("err %v", err)
	}
	if got := p.types(t); got != "facts,pin,out" {
		t.Errorf("lines %s", got)
	}
	dir := p.unpacked(t)
	if _, err := os.Stat(filepath.Join(dir, "run/raw.json")); err == nil {
		t.Error("the session ran on a scaling clock")
	}
	data, _ := os.ReadFile(filepath.Join(dir, "cluster-facts.json"))
	if !strings.Contains(string(data), `"fixedClock":false`) || !strings.Contains(string(data), `"cpuSet":"exclusive"`) {
		t.Errorf("facts %s", data)
	}
	// Allowed, the session runs and says so in its facts.
	p = newTestPod(t, map[string]string{
		"proc/self/status": "Cpus_allowed_list:\t2-3\n",
		"sys/devices/system/cpu/cpu3/cpufreq/scaling_governor": "schedutil\n",
	})
	se := writerSession(2, "auto")
	se.AllowFrequencyScaling = true
	if err := runPod(context.Background(), se, p.env, &p.stdout); err != nil {
		t.Fatal(err)
	}
	if got := p.types(t); got != "facts,pin,cpu,out,done" {
		t.Errorf("allowed: lines %s", got)
	}
}

func TestPodHandsBackAFailedSession(t *testing.T) {
	p := newTestPod(t, map[string]string{"proc/self/status": "Cpus_allowed_list:\t0-1\n"})
	se := writerSession(2, "auto")
	se.Argv = []string{"sh", "-c", `echo partial > "$1/partial.txt"; echo boom >&2; exit 7`, "sh", "{out}"}
	err := runPod(context.Background(), se, p.env, &p.stdout)
	if err == nil || !strings.Contains(err.Error(), "exit status 7") || !strings.Contains(err.Error(), "boom") {
		t.Fatalf("err %v", err)
	}
	if got := p.types(t); got != "facts,pin,cpu,out" {
		t.Errorf("lines %s", got)
	}
	dir := p.unpacked(t)
	if data, _ := os.ReadFile(filepath.Join(dir, "partial.txt")); string(data) != "partial\n" {
		t.Errorf("partial output %q", data)
	}
	if data, _ := os.ReadFile(filepath.Join(dir, "cluster-facts.json")); !strings.Contains(string(data), `"exit":7`) {
		t.Errorf("facts %s", data)
	}
}

func TestPodPinChoices(t *testing.T) {
	cases := []struct {
		name, allowed, pin string
		cpus               int
		want, err          string
		// gomaxprocs is the measured cores, at most the pod's CPUs: an unpinned session on a shared pool sees every core.
		gomaxprocs int
	}{
		{"exclusive cores are used as they are", "4-5", "auto", 2, "4,5", "", 2},
		{"an explicit list", "0-7", "6,7", 2, "6,7", "", 2},
		{"a list outside the cpuset is refused", "0-3", "6,7", 2, "", "names CPU 6, which the pod may not use", 0},
		{"none runs unpinned", "0-7", "none", 2, "", "", 2},
		{"a list longer than the pod's CPUs is refused", "0-7", "4,5,6", 2, "", "names 3 CPUs, the pod has 2", 0},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			p := newTestPod(t, map[string]string{"proc/self/status": "Cpus_allowed_list:\t" + c.allowed + "\n"})
			err := runPod(context.Background(), writerSession(c.cpus, c.pin), p.env, &p.stdout)
			if c.err != "" {
				if err == nil || !strings.Contains(err.Error(), c.err) {
					t.Fatalf("err %v, want %q", err, c.err)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if pin := p.lines(t)[1]; pin["cpus"] != c.want || pin["gomaxprocs"] != float64(c.gomaxprocs) {
				t.Errorf("pinned %v with GOMAXPROCS %v, want %q and %d", pin["cpus"], pin["gomaxprocs"], c.want, c.gomaxprocs)
			}
		})
	}
}

func TestPackAndUnpackRefuseEscapes(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "a/b"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "a/b/c.txt"), []byte("c"), 0o644); err != nil {
		t.Fatal(err)
	}
	archive := filepath.Join(t.TempDir(), "x.tar.gz")
	sum, size, err := packDir(dir, archive)
	if err != nil || len(sum) != 64 || size == 0 {
		t.Fatalf("%s %d %v", sum, size, err)
	}
	data, _ := os.ReadFile(archive)
	out := t.TempDir()
	if err := unpack(data, out); err != nil {
		t.Fatal(err)
	}
	if got, _ := os.ReadFile(filepath.Join(out, "a/b/c.txt")); string(got) != "c" {
		t.Errorf("round trip %q", got)
	}
	if err := unpack(tarOf(t, "../escape.txt"), t.TempDir()); err == nil || !strings.Contains(err.Error(), "leaves the run directory") {
		t.Errorf("escape: %v", err)
	}
}
