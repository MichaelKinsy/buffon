// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

// Command buffon-cluster runs buffon sessions on Kubernetes: one whole interleaved session per pod, with Guaranteed
// QoS, pinned cores, a refusal of cores whose clock scales, node facts, and a calibration gate on the coefficient of
// variation. Every cluster-specific value comes from a site profile. See cluster/README.md.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"maps"
	"os"
	"os/signal"
	"path/filepath"
	"slices"
	"strings"
	"syscall"
	"time"
)

// Exit codes.
const (
	exitOK    = 0
	exitError = 1
	exitUsage = 2
	// exitNoise refuses a calibration or comparison above the noise floor.
	exitNoise = 3
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	code := run(ctx, os.Args[1:], os.Stdout, os.Stderr, os.Getenv)
	stop()
	os.Exit(code)
}

const usage = `usage: buffon-cluster <command> [flags]

commands:
  render     print the Job manifest(s) for a session without contacting the cluster
  run        run a session on one node, or the same session on several nodes (-nodes, -spread)
  nodes      rank the nodes that can take a session pod
  calibrate  judge the noise floor of calibration run directories (one per node)
  check      check that a calibration vouches for a comparison on the given nodes
  pod        the in-pod session (the Job runs it)
`

func run(ctx context.Context, args []string, stdout, stderr io.Writer, getenv func(string) string) int {
	if len(args) == 0 {
		_, _ = fmt.Fprint(stderr, usage)
		return exitUsage
	}
	cmd, args := args[0], args[1:]
	var err error
	var code int
	switch cmd {
	case "render", "run", "nodes":
		code, err = runCluster(ctx, cmd, args, stdout, stderr, getenv)
	case "calibrate":
		code, err = runCalibrate(args, stdout, stderr)
	case "check":
		code, err = runCheck(args, stdout, stderr)
	case "pod":
		code, err = runPodCommand(ctx, stdout, getenv)
	case "-h", "-help", "--help", "help":
		_, _ = fmt.Fprint(stdout, usage)
		return exitOK
	default:
		_, _ = fmt.Fprintf(stderr, "buffon-cluster: unknown command %q\n%s", cmd, usage)
		return exitUsage
	}
	if err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return exitUsage
		}
		_, _ = fmt.Fprintf(stderr, "buffon-cluster %s: %v\n", cmd, err)
		if code == exitOK {
			code = exitError
		}
	}
	return code
}

func runCluster(ctx context.Context, cmd string, args []string, stdout, stderr io.Writer, getenv func(string) string) (int, error) {
	fs := flag.NewFlagSet(cmd, flag.ContinueOnError)
	fs.SetOutput(stderr)
	sitePath := fs.String("site", "", "site profile (JSON; default $BUFFON_K8S_SITE)")
	sessionPath := fs.String("session", "", "session spec (JSON) the Python backend wrote")
	out := fs.String("out", "", "directory the run directories are written to")
	kubectlBin := fs.String("kubectl", "kubectl", "kubectl binary")
	nodesFlag := fs.String("nodes", "", "comma-separated nodes: run the session on each, or the candidates for -spread and -pick-node")
	spreadN := fs.Int("spread", 0, "run the session on the N nodes with the most free CPU (of -nodes, when given)")
	pickNode := fs.Bool("pick-node", false, "run on the node with the most free CPU (of -nodes, when given)")
	count := fs.Int("n", 1, "nodes to pick (nodes command)")
	poll := fs.Duration("poll", 5*time.Second, "how often the runner polls the Job")
	keep := fs.Bool("keep", false, "keep the Job after it finishes")
	applyFlags := siteFlags(fs)
	if err := fs.Parse(args); err != nil {
		return exitUsage, err
	}
	st, err := loadSite(*sitePath, applyFlags, getenv)
	if err != nil {
		return exitUsage, err
	}
	k := newKube(execKubectl{bin: *kubectlBin, kubeconfig: st.Kubeconfig, context: st.KubeContext, namespace: st.Namespace})
	var candidates []string
	if *nodesFlag != "" {
		candidates = strings.Split(*nodesFlag, ",")
		for _, n := range candidates {
			if !dnsSubdomain.MatchString(n) {
				return exitUsage, fmt.Errorf("-nodes entry %q is not a node name", n)
			}
		}
		if len(slices.Compact(slices.Sorted(slices.Values(candidates)))) != len(candidates) {
			return exitUsage, fmt.Errorf("-nodes names a node twice: %s", *nodesFlag)
		}
	}
	if cmd == "nodes" {
		_, ranking, err := pickNodes(ctx, k, st, *count, candidates, stderr)
		if err != nil {
			return exitError, err
		}
		return exitOK, writeJSONTo(stdout, ranking)
	}
	se, err := readSession(*sessionPath)
	if err != nil {
		return exitUsage, err
	}
	if se.Pin == "" {
		se.Pin = "auto"
	}
	if se.CPUs == 0 {
		se.CPUs = st.CPUs
	}
	se.AllowFrequencyScaling = se.AllowFrequencyScaling || st.AllowFrequencyScaling
	// Which nodes: one (the site's or none), the given list, or a pick among candidates.
	if (*spreadN > 0 || *pickNode) && st.Node != "" {
		return exitUsage, errors.New("-spread and -pick-node choose the node; the site also pins one")
	}
	if *spreadN > 0 && *pickNode {
		return exitUsage, errors.New("-spread and -pick-node are exclusive")
	}
	nodes := candidates
	if len(nodes) == 0 {
		nodes = []string{st.Node}
	}
	r := &runner{k: k, st: st, poll: *poll, timeout: time.Duration(st.DeadlineSeconds)*time.Second + 10*time.Minute, keep: *keep, progress: stderr, now: time.Now}
	if st.delivery() == deliveryBundle {
		arch, err := inspectBundle(st.Bundle)
		if err != nil {
			return exitError, err
		}
		tmp, err := os.MkdirTemp("", "buffon-bundle-")
		if err != nil {
			return exitError, err
		}
		defer func() { _ = os.RemoveAll(tmp) }()
		tarPath, sum, err := packBundle(st.Bundle, tmp)
		if err != nil {
			return exitError, err
		}
		r.bundleTar, r.bundle = tarPath, bundleRef{sha256: sum, arch: arch}
	}
	if cmd == "render" {
		if *spreadN > 0 || *pickNode {
			_, _ = fmt.Fprintln(stderr, "buffon-cluster: -spread and -pick-node choose nodes when the session runs; the manifests below pin none")
			nodes = []string{""}
		}
		for i, node := range nodes {
			child := *se
			if len(nodes) > 1 {
				child.Run = fmt.Sprintf("%s-n%d", se.Run, i+1)
			}
			manifest, err := renderJob(st, &child, node, r.bundle)
			if err != nil {
				return exitUsage, err
			}
			if i > 0 {
				_, _ = fmt.Fprintln(stdout, "---")
			}
			_, _ = stdout.Write(manifest)
		}
		return exitOK, nil
	}
	if *out == "" {
		return exitUsage, errors.New("-out is not set")
	}
	if *spreadN > 0 || *pickNode {
		n := max(*spreadN, 1)
		picked, ranking, err := pickNodes(ctx, k, st, n, candidates, stderr)
		if err != nil {
			return exitError, err
		}
		if err := writeJSONFile(filepath.Join(*out, se.Run+"-nodes.json"), ranking); err != nil {
			return exitError, err
		}
		nodes = picked
	}
	// The outcomes go to stdout even when a session failed: the backend reports every node's result.
	var outs []outcome
	var runErr error
	if len(nodes) == 1 {
		var o outcome
		o, runErr = r.runOne(ctx, se, nodes[0], filepath.Join(*out, se.Run))
		if runErr == nil && !o.OK {
			runErr = fmt.Errorf("session %s on node %s: %s", o.Run, o.Node, o.Message)
		}
		if runErr != nil && o.Message == "" {
			o.Message = runErr.Error()
		}
		outs = []outcome{o}
	} else {
		outs, runErr = r.runSpread(ctx, se, nodes, filepath.Join(*out, se.Run))
	}
	if err := writeJSONTo(stdout, outs); err != nil {
		return exitError, err
	}
	if runErr != nil {
		return exitError, runErr
	}
	return exitOK, nil
}

// newKube wraps the kubectl client; tests replace it with a fake cluster.
var newKube = func(k execKubectl) kube { return k }

func readSession(path string) (*session, error) {
	if path == "" {
		return nil, errors.New("-session is not set")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return decodeSession(data)
}

func decodeSession(data []byte) (*session, error) {
	var se session
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&se); err != nil {
		return nil, fmt.Errorf("session: %w", err)
	}
	return &se, nil
}

func runCalibrate(args []string, stdout, stderr io.Writer) (int, error) {
	fs := flag.NewFlagSet("calibrate", flag.ContinueOnError)
	fs.SetOutput(stderr)
	maxCV := fs.Float64("max-cv", 0.05, "largest coefficient of variation a gated metric may have")
	gate := fs.String("gate", gateAuto, "metrics judged: auto (all on exclusive cores, CPU metrics on shared), all, or cpu")
	outPath := fs.String("o", "", "write calibration.json here")
	if err := fs.Parse(args); err != nil {
		return exitUsage, err
	}
	if fs.NArg() == 0 {
		return exitUsage, errors.New("name the calibration run directories (one per node)")
	}
	c, err := calibrate(fs.Args(), *gate, *maxCV)
	if err != nil {
		return exitError, err
	}
	if *outPath != "" {
		if err := writeJSONFile(*outPath, c); err != nil {
			return exitError, err
		}
	}
	for _, n := range c.Nodes {
		verdict := "pass"
		switch {
		case !n.Judged:
			verdict = "not judged"
		case !n.Pass:
			verdict = "noisy"
		}
		_, _ = fmt.Fprintf(stdout, "node %s (%s cores): %s\n", n.Node, n.CPUSet, verdict)
		for _, p := range n.Problems {
			_, _ = fmt.Fprintf(stdout, "  %s\n", p)
		}
		for _, k := range slices.Sorted(maps.Keys(n.Failed)) {
			_, _ = fmt.Fprintf(stdout, "  %s: %d failed samples (counted, not statistics)\n", k, n.Failed[k])
		}
	}
	switch {
	case !c.Judged:
		_, _ = fmt.Fprintf(stdout, "not judged: a calibration judges from %d samples per gated metric on cores with a fixed clock; this was a smoke test\n", minJudgedRuns)
		return exitOK, nil
	case !c.Pass:
		return exitNoise, fmt.Errorf("the calibration fails (max CV %.1f%%): %s", 100**maxCV, strings.Join(c.Problems, "; "))
	}
	_, _ = fmt.Fprintf(stdout, "pass: every gated metric's median CV over %d node(s) is within %.1f%%\n", len(c.Nodes), 100**maxCV)
	return exitOK, nil
}

func runCheck(args []string, stdout, stderr io.Writer) (int, error) {
	fs := flag.NewFlagSet("check", flag.ContinueOnError)
	fs.SetOutput(stderr)
	cal := fs.String("calibration", "", "calibration.json from buffon-cluster calibrate")
	nodes := fs.String("nodes", "", "comma-separated nodes the comparison runs on")
	if err := fs.Parse(args); err != nil {
		return exitUsage, err
	}
	if *cal == "" {
		return exitUsage, errors.New("-calibration is not set")
	}
	var list []string
	if *nodes != "" {
		list = strings.Split(*nodes, ",")
	}
	problems, err := checkCalibration(*cal, list)
	if err != nil {
		return exitError, err
	}
	if len(problems) > 0 {
		return exitNoise, errors.New(strings.Join(problems, "\n  "))
	}
	_, _ = fmt.Fprintln(stdout, "the calibration vouches for this comparison")
	return exitOK, nil
}

func runPodCommand(ctx context.Context, stdout io.Writer, getenv func(string) string) (int, error) {
	se, err := decodeSession([]byte(getenv("BUFFON_SESSION")))
	if err == nil {
		err = runPod(ctx, se, podEnvFromOS(), stdout)
	}
	if err != nil {
		o := newObject()
		o.set("t", lineError)
		o.set("message", err.Error())
		line, _ := o.MarshalJSON()
		_, _ = stdout.Write(append(line, '\n'))
		return exitError, err
	}
	return exitOK, nil
}

func writeJSONTo(w io.Writer, v any) error {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	_, err = w.Write(append(data, '\n'))
	return err
}

func writeJSONFile(path string, v any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	return errors.Join(writeJSONTo(f, v), f.Close())
}
