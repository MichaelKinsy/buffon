package main

import (
	"encoding/json"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func build(t *testing.T) string {
	bin := filepath.Join(t.TempDir(), "relay")
	if out, err := exec.Command("go", "build", "-o", bin, ".").CombinedOutput(); err != nil {
		t.Fatalf("build: %v\n%s", err, out)
	}
	return bin
}

// A connection to the relay's TCP port reaches the unix socket, the child's output passes through and its exit status is the relay's.
func TestForwardsToTheSocketAndExitsWithTheChild(t *testing.T) {
	sock := filepath.Join(t.TempDir(), "m.sock")
	ln, err := net.Listen("unix", sock)
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go func() {
				defer c.Close()
				buf := make([]byte, 5)
				io.ReadFull(c, buf)
				c.Write([]byte(strings.ToUpper(string(buf))))
			}()
		}
	}()
	// The relay binds port 0 itself and tells the child the address it got: probing for a free port and binding it later races with every other process asking the kernel for one.
	stats := filepath.Join(t.TempDir(), "stats.json")
	script := `addr=$BUFFON_RELAY_ADDR; exec 3<>/dev/tcp/${addr%:*}/${addr##*:}; printf hello >&3; head -c5 <&3; exit 7`
	cmd := exec.Command(build(t), "-listen", "127.0.0.1:0", "-export-addr", "-unix", sock, "-stats", stats, "--", "bash", "-c", script)
	out, err := cmd.Output()
	if string(out) != "HELLO" {
		t.Errorf("child read %q through the relay, want HELLO", out)
	}
	if ee, ok := err.(*exec.ExitError); !ok || ee.ExitCode() != 7 {
		t.Errorf("exit = %v, want the child's 7", err)
	}
	if data, err := os.ReadFile(stats); err != nil || !strings.Contains(string(data), "user_ms") {
		t.Errorf("stats file: %q %v", data, err)
	}
}

func TestASignalledChildExitsWith128PlusTheSignal(t *testing.T) {
	cmd := exec.Command(build(t), "-unix", "/nonexistent", "--", "sh", "-c", "kill -TERM $$")
	err := cmd.Run()
	if ee, ok := err.(*exec.ExitError); !ok || ee.ExitCode() != 143 {
		t.Errorf("exit = %v, want 143", err)
	}
}

func TestWithoutACommandOrSocketItIsAUsageError(t *testing.T) {
	err := exec.Command(build(t)).Run()
	if ee, ok := err.(*exec.ExitError); !ok || ee.ExitCode() != 2 {
		t.Errorf("exit = %v, want 2", err)
	}
}

// The seed directory is copied into HOME before the command starts: files with their modes, nested directories and symlinks.
func TestSeedIsCopiedIntoHomeBeforeTheCommandRuns(t *testing.T) {
	seed, home := t.TempDir(), t.TempDir()
	os.MkdirAll(filepath.Join(seed, "a", "b"), 0o755)
	os.WriteFile(filepath.Join(seed, "a", "b", "tool"), []byte("#!/bin/sh\necho seeded\n"), 0o755)
	os.Symlink("a/b/tool", filepath.Join(seed, "link"))
	cmd := exec.Command(build(t), "-unix", "/nonexistent", "-seed", seed, "-home", home, "--", "sh", "-c", "cd "+home+" && ./link && ls -l a/b/tool | cut -c1-10")
	out, err := cmd.Output()
	if err != nil || !strings.HasPrefix(string(out), "seeded\n-rwxr-xr-x") {
		t.Errorf("out %q err %v", out, err)
	}
}

func TestAFailedSeedStopsBeforeTheCommandWithStatus126(t *testing.T) {
	err := exec.Command(build(t), "-unix", "/nonexistent", "-seed", "/does/not/exist", "-home", t.TempDir(), "--", "true").Run()
	if ee, ok := err.(*exec.ExitError); !ok || ee.ExitCode() != 126 {
		t.Errorf("exit = %v, want 126", err)
	}
}

func TestTheArmsStartAndEndAreStampedOnTheMonotonicClock(t *testing.T) {
	stats := filepath.Join(t.TempDir(), "stats.json")
	sock := filepath.Join(t.TempDir(), "m.sock")
	before := monotonicNs()
	cmd := exec.Command(build(t), "-listen", "127.0.0.1:0", "-unix", sock, "-stats", stats, "--", "sleep", "0.2")
	if err := cmd.Run(); err != nil {
		t.Fatal(err)
	}
	after := monotonicNs()
	raw, err := os.ReadFile(stats + ".start")
	if err != nil {
		t.Fatal(err)
	}
	start, err := strconv.ParseInt(strings.TrimSpace(string(raw)), 10, 64)
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	data, _ := os.ReadFile(stats)
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	end := int64(doc["child_end_ns"].(float64))
	if !(before < start && start < end && end < after) {
		t.Errorf("not ordered: before %d start %d end %d after %d", before, start, end, after)
	}
	if end-start < 190_000_000 {
		t.Errorf("the child slept 200 ms but start..end is %d ns", end-start)
	}
}

// The relay records the cgroup's CPU and its own at the instant it starts the child, so the runner can leave out what the container used before the arm ran.
func TestStatsCarryTheStartPoint(t *testing.T) {
	if _, err := os.Stat("/sys/fs/cgroup/cpu.stat"); err != nil {
		t.Skip("no cgroup v2 cpu.stat at /sys/fs/cgroup")
	}
	stats := filepath.Join(t.TempDir(), "stats.json")
	if out, err := exec.Command(build(t), "-unix", "/nonexistent.sock", "-stats", stats, "--", "true").CombinedOutput(); err != nil {
		t.Fatalf("relay: %v\n%s", err, out)
	}
	var doc struct {
		Start  *int64   `json:"start_cgroup_usage_usec"`
		Relay  *float64 `json:"start_relay_cpu_ms"`
		Cgroup struct {
			Stat map[string]int64 `json:"cpu.stat"`
		} `json:"cgroup"`
	}
	data, _ := os.ReadFile(stats)
	if err := json.Unmarshal(data, &doc); err != nil || doc.Start == nil || doc.Relay == nil {
		t.Fatalf("stats lack the start point: %s (%v)", data, err)
	}
	if *doc.Start > doc.Cgroup.Stat["usage_usec"] {
		t.Errorf("start usage %d is after the final %d", *doc.Start, doc.Cgroup.Stat["usage_usec"])
	}
}

// The arm must not see a variable an uncontained arm does not: without -export-addr the child's environment is the relay's own.
func TestTheChildSeesNoRelayVariableUnlessAskedFor(t *testing.T) {
	sock := filepath.Join(t.TempDir(), "mock.sock")
	for _, c := range []struct {
		flags []string
		want  string
	}{{nil, ""}, {[]string{"-export-addr"}, "set"}} {
		args := append([]string{"-listen", "127.0.0.1:0", "-unix", sock}, c.flags...)
		args = append(args, "--", "sh", "-c", `[ -n "${BUFFON_RELAY_ADDR+x}" ] && printf set`)
		out, _ := exec.Command(build(t), args...).Output()
		if string(out) != c.want {
			t.Errorf("flags %v: child printed %q, want %q", c.flags, out, c.want)
		}
	}
}
