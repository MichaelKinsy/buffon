// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"math"
	"os"
	"path/filepath"
	"slices"
	"strings"
)

// minJudgedRuns is the fewest samples per metric that judge a noise floor; fewer make a smoke test.
const minJudgedRuns = 12

// Gate modes: which metrics the calibration judges. Wall times on shared cores follow the neighbours, so auto judges
// every metric on exclusive cores and only the CPU metrics on shared ones; the rest are reported as information.
const (
	gateAuto = "auto"
	gateAll  = "all"
	gateCPU  = "cpu"
)

// noise is one metric's spread over a session's samples.
type noise struct {
	N    int     `json:"n"`
	Mean float64 `json:"mean"`
	SD   float64 `json:"sd"`
	CV   float64 `json:"cv"`
	Gate bool    `json:"gate"`
}

func spread(xs []float64, gate bool) noise {
	m := noise{N: len(xs), Gate: gate}
	if m.N == 0 {
		return m
	}
	for _, x := range xs {
		m.Mean += x
	}
	m.Mean /= float64(m.N)
	if m.N > 1 {
		var ss float64
		for _, x := range xs {
			ss += (x - m.Mean) * (x - m.Mean)
		}
		m.SD = math.Sqrt(ss / float64(m.N-1))
	}
	if m.Mean != 0 {
		m.CV = m.SD / m.Mean
	}
	return m
}

func roundTo(v float64, digits int) float64 {
	scale := math.Pow(10, float64(digits))
	return math.Round(v*scale) / scale
}

func median(xs []float64) float64 {
	s := slices.Sorted(slices.Values(xs))
	n := len(s)
	if n%2 == 1 {
		return s[n/2]
	}
	return (s[n/2-1] + s[n/2]) / 2
}

// series is one (scenario and API variant, arm, metric) sample series of a run directory.
type series struct{ scenario, arm, metric string }

func (s series) String() string { return s.scenario + "/" + s.arm + "/" + s.metric }

// identityKeys are the samples[] keys that are not metrics (docs/RAW-FORMAT.md).
var identityKeys = map[string]bool{"arm": true, "scenario": true, "api": true, "round": true, "warmup": true, "t_utc": true, "wall_s": true, "failure": true, "series": true, "twin_of": true}

// descriptors are the numeric sample keys that describe the host or echo the workload's parameters, not the arm's cost:
// the host readings taken before every sample and the workload's own counts. buffon/report/cells.py DESCRIPTORS is the
// same list (tests/test_cluster_gate_metrics.py keeps them equal).
var descriptors = map[string]bool{
	"quiet_wait_ms": true, "host_load1": true, "host_runnable": true, "pinned_busy": true, "pinned_iowait": true, "pinned_steal": true,
	"cpuset_runnable": true, "throttled": true, "psi_cpu_some_avg10": true, "turns": true, "requests": true, "compactions": true,
	"soak_minutes": true, "think_ms": true, "stream_rate_tps": true, "history_bytes": true, "history_entries": true,
	"history_messages": true, "series_samples": true, "records_after_kill": true, "seconds_to_exit": true,
	"mem_baseline_mib": true, "mem_ready_mib": true, "mock_cpu_ms": true, "launcher_cpu_ms": true, "runner_cpu_ms": true,
	"commits_replayed": true, "commits_total": true, "compaction_failures": true, "conversations": true, "failed_requests": true, "failed_turns": true, "fixture_bytes": true, "fixture_seed": true, "fixture_turns": true, "k": true, "kill_event_commit": true, "measured_turns": true, "model_ms_per_turn": true, "stmts_replayed": true, "window_tokens": true,
}

// countMetrics are what a durable runtime did per turn (buffon/report/metrics.py COUNT_METRICS): scored.
var countMetrics = map[string]bool{
	"rows_read_per_turn": true, "rows_returned_per_turn": true, "rows_written_per_turn": true, "sql_commits_per_turn": true, "sql_ddl_stmts_per_turn": true, "sql_pragma_stmts_per_turn": true, "sql_read_stmts_per_turn": true, "sql_stmts_per_turn": true, "sql_write_stmts_per_turn": true,
}

// Name endings of derived summaries (not scored) and of cost metrics (scored), as buffon/report/cells.py scored.
var (
	unscoredSuffixes = []string{"_flat", "_median", "_spread", "_slope_per_h"}
	scoredSuffixes   = []string{"_ms", "_mib", "_bytes", "_instructions", "_cycles", "_ms_p50", "_ms_p95", "_ms_max"}
)

// scored reports whether a sample key is a cost metric the report compares (buffon/report/cells.py scored): a time,
// memory, byte or CPU metric. Only those are judged for noise: a host reading such as pinned_steal is zero on a quiet
// node, and a zero series would refuse the node as unmeasured.
func scored(metric string) bool {
	if countMetrics[metric] {
		return true
	}
	if descriptors[metric] || slices.ContainsFunc(unscoredSuffixes, func(x string) bool { return strings.HasSuffix(metric, x) }) {
		return false
	}
	return slices.ContainsFunc(scoredSuffixes, func(x string) bool { return strings.HasSuffix(metric, x) }) ||
		strings.Contains(metric, "_ms_per_") || strings.Contains(metric, "_mib_per_") || strings.Contains(metric, "_bytes_per_") || strings.HasPrefix(metric, "bytes_") || metric == "mem_per_conv_mib" || strings.Contains(metric, "_instructions_per_") || strings.HasPrefix(metric, "cpu_ms") ||
		metric == "instructions" || metric == "cycles" || metric == "turns_per_s"
}

// readSamples reads raw.json's samples[] (docs/RAW-FORMAT.md): one flat record per process, identity keys then one key
// per metric. Warm-up samples are not statistics, and a failed sample carries no metric; each API variant is its own
// series, and only the metrics the report scores are read. failed counts the measured samples that failed, per
// "scenario@api/arm".
func readSamples(path string) (out map[series][]float64, failed map[string]int, err error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, nil, err
	}
	var raw struct {
		Samples []map[string]any `json:"samples"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, nil, fmt.Errorf("%s: samples is not a list of sample records: %w", path, err)
	}
	out, failed = map[series][]float64{}, map[string]int{}
	for _, sample := range raw.Samples {
		arm, _ := sample["arm"].(string)
		scenario, _ := sample["scenario"].(string)
		if arm == "" || scenario == "" {
			return nil, nil, fmt.Errorf("%s: a sample has no arm or scenario", path)
		}
		if warmup, _ := sample["warmup"].(bool); warmup {
			continue
		}
		if api, ok := sample["api"].(string); ok && api != "" {
			scenario += "@" + api
		}
		if _, ok := sample["failure"]; ok {
			failed[scenario+"/"+arm]++
			continue
		}
		for k, v := range sample {
			if f, ok := v.(float64); ok && !identityKeys[k] && scored(k) {
				s := series{scenario, arm, k}
				out[s] = append(out[s], f)
			}
		}
	}
	if len(out) == 0 {
		return nil, nil, fmt.Errorf("%s: no numeric samples", path)
	}
	return out, failed, nil
}

// clusterFacts is what the gate reads from a run directory's cluster-facts.json.
type podFacts struct {
	Node   string `json:"node"`
	CPUSet string `json:"cpuSet"`
	Pin    struct {
		FixedClock bool `json:"fixedClock"`
	} `json:"pin"`
	Session struct {
		Exit int `json:"exit"`
	} `json:"session"`
}

func gated(mode, cpuSet, metric string) (bool, error) {
	isCPU := strings.Contains(metric, "cpu")
	switch mode {
	case gateAll:
		return true, nil
	case gateCPU:
		return isCPU, nil
	case gateAuto:
		return cpuSet == "exclusive" || isCPU, nil
	}
	return false, fmt.Errorf("gate %q is not auto, all or cpu", mode)
}

// nodeCalibration is one run directory's noise floor.
type nodeCalibration struct {
	Node     string           `json:"node"`
	RunDir   string           `json:"runDir"`
	CPUSet   string           `json:"cpuSet"`
	Judged   bool             `json:"judged"`
	Pass     bool             `json:"pass"`
	Problems []string         `json:"problems,omitempty"`
	Noise    map[string]noise `json:"noise"`
	// Failed counts the measured samples that failed, per "scenario@api/arm".
	Failed map[string]int `json:"failed,omitempty"`
}

// calibration is the gate's verdict over every node of a calibration; compare refuses without a judged one.
type calibration struct {
	MaxCV    float64           `json:"maxCv"`
	Gate     string            `json:"gate"`
	Judged   bool              `json:"judged"`
	Pass     bool              `json:"pass"`
	Problems []string          `json:"problems,omitempty"`
	Median   map[string]noise  `json:"median"`
	Nodes    []nodeCalibration `json:"nodes"`
}

// calibrate judges the noise floor of run directories (one per node), from at least minJudgedRuns samples per gated
// metric on cores with a fixed clock. The calibration passes when the median over nodes of every gated metric's CV is
// within maxCV; each node also gets its own verdict, so a node noisy on its own is named even when the median passes,
// and a comparison on it is refused.
func calibrate(dirs []string, mode string, maxCV float64) (*calibration, error) {
	if !(maxCV > 0 && maxCV < 1) {
		return nil, fmt.Errorf("max-cv %v: want a coefficient of variation such as 0.05", maxCV)
	}
	c := &calibration{MaxCV: maxCV, Gate: mode, Judged: true, Median: map[string]noise{}}
	perSeries := map[string][]noise{}
	for _, dir := range dirs {
		var f podFacts
		data, err := os.ReadFile(filepath.Join(dir, "cluster-facts.json"))
		if err != nil {
			return nil, fmt.Errorf("%s is not a cluster run directory: %w", dir, err)
		}
		if err := json.Unmarshal(data, &f); err != nil {
			return nil, fmt.Errorf("%s/cluster-facts.json: %w", dir, err)
		}
		raw, err := findRaw(dir)
		if err != nil {
			return nil, err
		}
		samples, failed, err := readSamples(raw)
		if err != nil {
			return nil, err
		}
		n := nodeCalibration{Node: f.Node, RunDir: dir, CPUSet: f.CPUSet, Judged: true, Noise: map[string]noise{}}
		// A failed sample is not noise and is not a statistic; it is counted, never dropped silently (METHODOLOGY.md section 9).
		if len(failed) > 0 {
			n.Failed = failed
		}
		// A session that exited non-zero did not finish its calibration: the calibration as a whole cannot pass on it.
		if f.Session.Exit != 0 {
			broken := fmt.Sprintf("%s: the session exited %d", f.Node, f.Session.Exit)
			n.Problems = append(n.Problems, broken)
			c.Problems = append(c.Problems, broken)
		}
		if !f.Pin.FixedClock {
			n.Judged = false
			n.Problems = append(n.Problems, fmt.Sprintf("%s: the measured cores scale their clock; reported, not judged", f.Node))
		}
		keys := slices.SortedFunc(func(yield func(series) bool) {
			for k := range samples {
				if !yield(k) {
					return
				}
			}
		}, func(a, b series) int { return strings.Compare(a.String(), b.String()) })
		for _, k := range keys {
			g, err := gated(mode, f.CPUSet, k.metric)
			if err != nil {
				return nil, err
			}
			m := spread(samples[k], g)
			n.Noise[k.String()] = m
			perSeries[k.String()] = append(perSeries[k.String()], m)
			if !g {
				continue
			}
			switch {
			case m.N < minJudgedRuns:
				n.Judged = false
				n.Problems = append(n.Problems, fmt.Sprintf("%s: %s has %d samples; a calibration judges from %d", f.Node, k, m.N, minJudgedRuns))
			case m.Mean <= 0:
				n.Problems = append(n.Problems, fmt.Sprintf("%s: %s is zero in every sample; it was not measured", f.Node, k))
			case m.CV > maxCV:
				n.Problems = append(n.Problems, fmt.Sprintf("%s: %s CV %.2f%% exceeds %.1f%%", f.Node, k, 100*m.CV, 100*maxCV))
			}
		}
		n.Pass = n.Judged && len(n.Problems) == 0
		c.Judged = c.Judged && n.Judged
		c.Nodes = append(c.Nodes, n)
	}
	if len(c.Nodes) == 0 {
		return nil, errors.New("no run directories to calibrate")
	}
	for _, n := range c.Nodes {
		if !n.Judged {
			c.Problems = append(c.Problems, fmt.Sprintf("node %s is not judged", n.Node))
		}
	}
	for _, k := range slices.Sorted(maps.Keys(perSeries)) {
		ms := perSeries[k]
		var cvs, means []float64
		gate := false
		for _, m := range ms {
			cvs, means = append(cvs, m.CV), append(means, m.Mean)
			gate = gate || m.Gate
		}
		med := noise{N: len(ms), Mean: median(means), CV: median(cvs), Gate: gate}
		c.Median[k] = med
		if gate && med.CV > maxCV {
			c.Problems = append(c.Problems, fmt.Sprintf("median over %d nodes: %s CV %.2f%% exceeds %.1f%%", len(ms), k, 100*med.CV, 100*maxCV))
		}
	}
	c.Pass = c.Judged && len(c.Problems) == 0
	return c, nil
}

// findRaw finds the session's raw.json in a run directory: at its top, or one level down (Buffon's own run
// directory inside the session's output directory).
func findRaw(dir string) (string, error) {
	if p := filepath.Join(dir, "raw.json"); fileExists(p) {
		return p, nil
	}
	matches, err := filepath.Glob(filepath.Join(dir, "*", "raw.json"))
	if err != nil {
		return "", err
	}
	if len(matches) != 1 {
		return "", fmt.Errorf("%s holds %d raw.json files one level down; want exactly one", dir, len(matches))
	}
	return matches[0], nil
}

func fileExists(p string) bool { _, err := os.Stat(p); return err == nil }

// checkCalibration lists why a calibration cannot vouch for a comparison on nodes: one of the nodes was not
// calibrated, or did not pass on its own. Without nodes, the calibration as a whole must pass.
func checkCalibration(path string, nodes []string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var c calibration
	if err := json.Unmarshal(data, &c); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	var problems []string
	if len(nodes) == 0 {
		if !c.Pass {
			problems = append(problems, fmt.Sprintf("%s did not pass: %s", path, strings.Join(c.Problems, "; ")))
		}
		return problems, nil
	}
	for _, node := range nodes {
		i := slices.IndexFunc(c.Nodes, func(n nodeCalibration) bool { return n.Node == node })
		switch {
		case i < 0:
			problems = append(problems, fmt.Sprintf("%s did not calibrate node %s", path, node))
		case !c.Nodes[i].Pass:
			problems = append(problems, fmt.Sprintf("%s: node %s did not pass: %s", path, node, strings.Join(c.Nodes[i].Problems, "; ")))
		}
	}
	return problems, nil
}
