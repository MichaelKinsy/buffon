// SPDX-License-Identifier: MIT

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// calRun writes a calibration run directory: cluster facts and a raw.json whose samples alternate around each mean
// by ±spread (relative), n samples per arm.
func calRun(t *testing.T, node, cpuSet string, fixedClock bool, n int, cpuSpread, wallSpread float64) string {
	t.Helper()
	dir := filepath.Join(t.TempDir(), node)
	if err := os.MkdirAll(filepath.Join(dir, "run"), 0o755); err != nil {
		t.Fatal(err)
	}
	facts := fmt.Sprintf(`{"node":%q,"cpuSet":%q,"pin":{"fixedClock":%t},"session":{"exit":0}}`, node, cpuSet, fixedClock)
	if err := os.WriteFile(filepath.Join(dir, "cluster-facts.json"), []byte(facts), 0o644); err != nil {
		t.Fatal(err)
	}
	sample := func(i int) map[string]any {
		sign := float64(1 - 2*(i%2))
		return map[string]any{"cpu_ms": 100 * (1 + sign*cpuSpread), "wall_ms": 200 * (1 + sign*wallSpread), "note": "x"}
	}
	var list []map[string]any
	for _, arm := range []string{"pi-node", "pi-node-b"} {
		// A warm-up sample far off the mean, and a failed one, are not statistics.
		list = append(list, map[string]any{"arm": arm, "scenario": "print", "api": "openai-completions", "round": 0, "warmup": true, "cpu_ms": 900.0, "wall_ms": 900.0})
		list = append(list, map[string]any{"arm": arm, "scenario": "print", "api": "openai-completions", "round": 0, "warmup": false, "failure": "timeout"})
		for i := range n {
			s := sample(i)
			s["arm"], s["scenario"], s["api"], s["round"], s["warmup"], s["wall_s"] = arm, "print", "openai-completions", i+1, false, 0.5
			list = append(list, s)
		}
	}
	raw := map[string]any{"samples": list}
	data, _ := json.Marshal(raw)
	if err := os.WriteFile(filepath.Join(dir, "run", "raw.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

func TestCalibrationPassesAQuietFloor(t *testing.T) {
	{
		c, err := calibrate([]string{calRun(t, "node-a", "shared", true, 12, 0.02, 0.30)}, gateAuto, 0.05)
		if err != nil {
			t.Fatal(err)
		}
		if !c.Pass || !c.Judged || !c.Nodes[0].Pass || len(c.Nodes[0].Noise) != 4 {
			t.Errorf("%+v", c)
		}
		// On shared cores the wall time is information, not gated: its 30% spread does not refuse the floor.
		if m := c.Nodes[0].Noise["print@openai-completions/pi-node/wall_ms"]; m.Gate || m.CV < 0.25 {
			t.Errorf("wall on shared cores: %+v", m)
		}
		if m := c.Nodes[0].Noise["print@openai-completions/pi-node/cpu_ms"]; !m.Gate || m.N != 12 {
			t.Errorf("cpu: %+v", m)
		}
	}
}

func TestCalibrationGatesWallTimeOnExclusiveCores(t *testing.T) {
	c, err := calibrate([]string{calRun(t, "node-a", "exclusive", true, 12, 0.02, 0.30)}, gateAuto, 0.05)
	if err != nil {
		t.Fatal(err)
	}
	if c.Pass || !strings.Contains(strings.Join(c.Nodes[0].Problems, ";"), "print@openai-completions/pi-node/wall_ms CV") {
		t.Errorf("%+v", c)
	}
	// gate cpu judges only the CPU metrics, wherever the cores are.
	c, _ = calibrate([]string{calRun(t, "node-a", "exclusive", true, 12, 0.02, 0.30)}, gateCPU, 0.05)
	if !c.Pass {
		t.Errorf("gate cpu: %+v", c.Problems)
	}
}

func TestCalibrationRefusesNoiseAndSmokeTests(t *testing.T) {
	c, _ := calibrate([]string{calRun(t, "node-a", "shared", true, 12, 0.08, 0)}, gateAuto, 0.05)
	if c.Pass || !c.Judged || !strings.Contains(strings.Join(c.Problems, ";"), "cpu_ms CV") {
		t.Errorf("noisy: %+v", c)
	}
	c, _ = calibrate([]string{calRun(t, "node-a", "shared", true, 11, 0.01, 0)}, gateAuto, 0.05)
	if c.Pass || c.Judged || !strings.Contains(strings.Join(c.Nodes[0].Problems, ";"), "has 11 samples; a calibration judges from 12") {
		t.Errorf("smoke: %+v", c)
	}
	c, _ = calibrate([]string{calRun(t, "node-a", "shared", false, 12, 0.01, 0)}, gateAuto, 0.05)
	if c.Pass || c.Judged {
		t.Errorf("scaling clock: %+v", c)
	}
}

// The median over nodes judges the calibration; a node noisy on its own is named, and a comparison on it refused.
func TestSpreadCalibrationNamesANoisyNode(t *testing.T) {
	dirs := []string{calRun(t, "node-a", "shared", true, 12, 0.01, 0), calRun(t, "node-b", "shared", true, 12, 0.02, 0), calRun(t, "node-c", "shared", true, 12, 0.09, 0)}
	c, err := calibrate(dirs, gateAuto, 0.05)
	if err != nil {
		t.Fatal(err)
	}
	if !c.Pass || c.Nodes[2].Pass || !c.Nodes[0].Pass || c.Median["print@openai-completions/pi-node/cpu_ms"].N != 3 {
		t.Fatalf("%+v", c)
	}
	path := filepath.Join(t.TempDir(), "calibration.json")
	if err := writeJSONFile(path, c); err != nil {
		t.Fatal(err)
	}
	if p, _ := checkCalibration(path, []string{"node-a", "node-b"}); len(p) != 0 {
		t.Errorf("quiet nodes refused: %v", p)
	}
	if p, _ := checkCalibration(path, []string{"node-a", "node-c"}); len(p) != 1 || !strings.Contains(p[0], "node node-c did not pass") {
		t.Errorf("noisy node: %v", p)
	}
	if p, _ := checkCalibration(path, []string{"node-d"}); len(p) != 1 || !strings.Contains(p[0], "did not calibrate node node-d") {
		t.Errorf("uncalibrated node: %v", p)
	}
}

func TestCalibrateAndCheckCommands(t *testing.T) {
	out := filepath.Join(t.TempDir(), "calibration.json")
	var stdout bytes.Buffer
	noisy := calRun(t, "node-a", "shared", true, 12, 0.08, 0)
	if code := run(context.Background(), []string{"calibrate", "-o", out, noisy}, &stdout, io.Discard, os.Getenv); code != exitNoise {
		t.Errorf("noisy calibration: exit %d\n%s", code, stdout.String())
	}
	if code := run(context.Background(), []string{"check", "-calibration", out, "-nodes", "node-a"}, io.Discard, io.Discard, os.Getenv); code != exitNoise {
		t.Errorf("check of a noisy calibration: exit %d", code)
	}
	smoke := calRun(t, "node-a", "shared", true, 6, 0.08, 0)
	stdout.Reset()
	if code := run(context.Background(), []string{"calibrate", "-o", out, smoke}, &stdout, io.Discard, os.Getenv); code != exitOK || !strings.Contains(stdout.String(), "not judged") {
		t.Errorf("smoke calibration: exit %d\n%s", code, stdout.String())
	}
	if code := run(context.Background(), []string{"check", "-calibration", out}, io.Discard, io.Discard, os.Getenv); code != exitNoise {
		t.Errorf("check of a smoke test: exit %d", code)
	}
	quiet := calRun(t, "node-a", "shared", true, 12, 0.01, 0)
	if code := run(context.Background(), []string{"calibrate", "-o", out, quiet}, io.Discard, io.Discard, os.Getenv); code != exitOK {
		t.Errorf("quiet calibration: exit %d", code)
	}
	if code := run(context.Background(), []string{"check", "-calibration", out, "-nodes", "node-a"}, io.Discard, io.Discard, os.Getenv); code != exitOK {
		t.Errorf("check of a quiet calibration: exit %d", code)
	}
}

func TestReadSamplesRefusesUnknownShapes(t *testing.T) {
	dir := t.TempDir()
	for name, body := range map[string]string{"string": `{"samples":"x"}`, "nested": `{"samples":{"print":{"pi-node":[{"cpu_ms":1}]}}}`, "empty": `{"samples":[]}`, "armless": `{"samples":[{"scenario":"s","cpu_ms":1}]}`} {
		p := filepath.Join(dir, name+".json")
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
		if _, _, err := readSamples(p); err == nil {
			t.Errorf("%s: read", name)
		}
	}
}

// buffonRun writes a run directory whose raw.json has Buffon's own sample shape (docs/RAW-FORMAT.md): warm-up
// rounds first, every variant once per wire API, failed samples without metrics, and wall_s on every sample.
func buffonRun(t *testing.T, node string, warmup, rounds int, failures int) string {
	t.Helper()
	dir := filepath.Join(t.TempDir(), node)
	if err := os.MkdirAll(filepath.Join(dir, "run"), 0o755); err != nil {
		t.Fatal(err)
	}
	facts := fmt.Sprintf(`{"node":%q,"cpuSet":"exclusive","pin":{"fixedClock":true},"session":{"exit":0}}`, node)
	if err := os.WriteFile(filepath.Join(dir, "cluster-facts.json"), []byte(facts), 0o644); err != nil {
		t.Fatal(err)
	}
	var list []map[string]any
	for rnd := range warmup + rounds {
		for _, api := range []string{"openai-completions", "anthropic-messages"} {
			for _, arm := range []string{"pi-node", "pi-node-b"} {
				s := map[string]any{"arm": arm, "scenario": "overhead/print", "api": api, "round": rnd, "warmup": rnd < warmup, "t_utc": "2026-10-11T00:00:00Z"}
				base := 100.0
				if api == "anthropic-messages" {
					base = 200
				}
				sign := float64(1 - 2*(rnd%2))
				switch {
				case rnd < warmup:
					// A cold first round: far off the measured floor.
					s["cpu_ms"], s["wall_ms"] = 3*base, 6*base
				case failures > 0 && rnd == warmup+1 && arm == "pi-node":
					s["failure"] = "the harness exited 1"
					failures--
				default:
					s["cpu_ms"], s["wall_ms"] = base*(1+sign*0.01), 2*base*(1+sign*0.01)
				}
				s["wall_s"] = 1.5
				// The host readings the runner takes before every sample (docs/RAW-FORMAT.md): describe the host, not the arm, and
				// are often zero or swing widely on a quiet node. A workload parameter echoed into the sample is constant.
				s["pinned_busy"], s["pinned_steal"], s["cpuset_runnable"], s["throttled"] = 0.01*float64(rnd%3), 0.0, 0.0, false
				s["psi_cpu_some_avg10"], s["host_load1"], s["host_runnable"], s["quiet_wait_ms"] = 0.0, 40.0+30*float64(rnd%2), float64(rnd%5), 0.0
				s["turns"] = 20.0
				// schedstat totals: recorded beside the metrics, a nested object the gate never reads.
				s["sched"] = map[string]any{"run_ms": 90.0 * float64(1+rnd%4), "wait_ms": 0.0, "slices": 12.0, "threads": 9.0, "meters": 1.0}
				list = append(list, s)
			}
		}
	}
	data, _ := json.Marshal(map[string]any{"kind": "buffon-run", "samples": list})
	if err := os.WriteFile(filepath.Join(dir, "run", "raw.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

// Buffon drops warm-up samples from statistics, never pools two wire APIs into one series, and gives a failed
// sample no metrics: the gate judges the measured rounds of each (scenario, api, arm, metric) and counts failures.
func TestCalibrationJudgesBuffonsMeasuredSamples(t *testing.T) {
	c, err := calibrate([]string{buffonRun(t, "node-a", 1, 12, 0)}, gateAll, 0.05)
	if err != nil {
		t.Fatal(err)
	}
	if !c.Pass || !c.Nodes[0].Pass {
		t.Errorf("12 quiet measured rounds after a cold warm-up, two APIs: %v %v", c.Problems, c.Nodes[0].Problems)
	}
	// Only the metrics the report scores are judged: a host reading or a workload count is no series of its own.
	for k := range c.Nodes[0].Noise {
		if m := k[strings.LastIndex(k, "/")+1:]; m != "cpu_ms" && m != "wall_ms" {
			t.Errorf("judged %s", k)
		}
	}
	if m := c.Nodes[0].Noise["overhead/print@anthropic-messages/pi-node/cpu_ms"]; m.N != 12 || m.Mean != 200 {
		t.Errorf("anthropic-messages cpu_ms series = %+v, want the 12 measured samples around 200", m)
	}
	c, err = calibrate([]string{buffonRun(t, "node-a", 1, 11, 0)}, gateAll, 0.05)
	if err != nil {
		t.Fatal(err)
	}
	if c.Judged || c.Pass {
		t.Errorf("11 measured rounds and a warm-up were judged: %+v", c)
	}
	c, err = calibrate([]string{buffonRun(t, "node-a", 1, 13, 1)}, gateAll, 0.05)
	if err != nil {
		t.Fatal(err)
	}
	// A failed sample is counted, not a statistic: the 13 measured rounds still hold 12 good samples.
	if !c.Pass || c.Nodes[0].Failed["overhead/print@openai-completions/pi-node"] != 1 || len(c.Nodes[0].Failed) != 1 {
		t.Errorf("one failed sample: pass %t, failed %v, problems %v", c.Pass, c.Nodes[0].Failed, c.Problems)
	}
}

// A session that exited non-zero vouches for nothing, even when its samples are quiet.
func TestCalibrationFailsOnAFailedSession(t *testing.T) {
	dir := calRun(t, "node-a", "exclusive", true, 12, 0.01, 0.01)
	facts := `{"node":"node-a","cpuSet":"exclusive","pin":{"fixedClock":true},"session":{"exit":1}}`
	if err := os.WriteFile(filepath.Join(dir, "cluster-facts.json"), []byte(facts), 0o644); err != nil {
		t.Fatal(err)
	}
	c, err := calibrate([]string{dir}, gateAll, 0.05)
	if err != nil {
		t.Fatal(err)
	}
	if c.Pass {
		t.Errorf("a calibration whose session exited 1 passed: %+v", c.Problems)
	}
}
