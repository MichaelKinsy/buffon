// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

package main

import (
	"archive/tar"
	"bufio"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// outcome is what the runner reports about one session on one node; the Python backend reads it as SessionResult.
type outcome struct {
	Run     string `json:"run"`
	Node    string `json:"node"`
	Pod     string `json:"pod"`
	RunDir  string `json:"runDir"`
	OK      bool   `json:"ok"`
	Message string `json:"message,omitempty"`
}

// runner runs sessions through one kube client.
type runner struct {
	k        kube
	st       site
	poll     time.Duration
	timeout  time.Duration
	keep     bool
	progress io.Writer
	now      func() time.Time
	// bundleTar and bundle describe the packed bundle in bundle mode.
	bundleTar string
	bundle    bundleRef
}

// podLine is one JSON line of a pod log.
type podLine struct {
	T       string `json:"t"`
	Message string `json:"message"`
	Path    string `json:"path"`
	SHA256  string `json:"sha256"`
	Bytes   int64  `json:"bytes"`
}

func podLines(log []byte) []podLine {
	var out []podLine
	sc := bufio.NewScanner(bytes.NewReader(log))
	sc.Buffer(make([]byte, 1<<20), 16<<20)
	for sc.Scan() {
		var l podLine
		if json.Unmarshal(sc.Bytes(), &l) == nil && l.T != "" {
			out = append(out, l)
		}
	}
	return out
}

// runOne runs se on node and fetches its run directory into dir. The pod's own error, when it reports one, is the
// outcome's message.
func (r *runner) runOne(ctx context.Context, se *session, node, dir string) (outcome, error) {
	o := outcome{Run: se.Run, RunDir: dir}
	manifest, err := renderJob(r.st, se, node, r.bundle)
	if err != nil {
		return o, err
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return o, err
	}
	if err := os.WriteFile(filepath.Join(dir, "job.yaml"), manifest, 0o644); err != nil {
		return o, err
	}
	var deliver func(context.Context, string) error
	if r.st.delivery() == deliveryBundle {
		deliver = func(ctx context.Context, pod string) error {
			return copyBundle(ctx, r.k, pod, r.bundleTar, r.progress, r.now)
		}
	}
	collect := func(ctx context.Context, pod string, log []byte) (bool, error) {
		for _, l := range podLines(log) {
			if l.T == lineOut {
				return true, r.fetch(ctx, pod, l, dir)
			}
		}
		return false, nil
	}
	job, err := runJob(ctx, r.k, manifest, se.Run, r.poll, r.timeout, r.keep, r.progress, r.now, deliver, collect)
	o.Node, o.Pod = job.node, job.pod
	if err != nil {
		return o, err
	}
	if err := os.WriteFile(filepath.Join(dir, "pod.log"), job.log, 0o644); err != nil {
		return o, err
	}
	// What the API server says about the node, where the account may read it: kernel, kubelet, CPU manager policy.
	facts := clusterFacts(ctx, r.k, job.node)
	facts.set("podQosClass", job.qosClass)
	facts.set("podImageID", job.imageID)
	if err := writeJSON(filepath.Join(dir, "node.json"), facts); err != nil {
		return o, err
	}
	lines := podLines(job.log)
	for _, l := range lines {
		if l.T == lineError {
			o.Message = l.Message
		}
	}
	switch {
	case !job.succeeded && o.Message == "":
		o.Message = "the pod failed: " + strings.TrimSpace(job.reason+" "+lastLine(job.log))
	case job.succeeded && (len(lines) == 0 || lines[len(lines)-1].T != lineDone):
		o.Message = "the pod finished without its done line"
	}
	o.OK = job.succeeded && o.Message == ""
	return o, nil
}

func lastLine(log []byte) string {
	lines := strings.Split(strings.TrimSpace(string(log)), "\n")
	return lines[len(lines)-1]
}

// fetch copies the pod's run archive out, checks its sha256 and size, unpacks it into dir, and leaves the FETCHED
// marker that lets the pod exit.
func (r *runner) fetch(ctx context.Context, pod string, l podLine, dir string) error {
	if !sha256Hex.MatchString(l.SHA256) || l.Path == "" {
		return fmt.Errorf("pod %s announced its results without a path and sha256", pod)
	}
	local := filepath.Join(dir, "out.tar.gz")
	if _, err := r.k.run(ctx, nil, "cp", pod+":"+l.Path, local, "-c", "buffon"); err != nil {
		return err
	}
	data, err := os.ReadFile(local)
	if err != nil {
		return err
	}
	sum := sha256.Sum256(data)
	if got := hex.EncodeToString(sum[:]); got != l.SHA256 || int64(len(data)) != l.Bytes {
		return fmt.Errorf("the results copied from pod %s have sha256 %s and %d bytes, the pod sent %s and %d", pod, got, len(data), l.SHA256, l.Bytes)
	}
	if err := unpack(data, dir); err != nil {
		return err
	}
	if err := os.Remove(local); err != nil {
		return err
	}
	marker := filepath.Join(dir, ".fetched")
	if err := os.WriteFile(marker, nil, 0o644); err != nil {
		return err
	}
	defer func() { _ = os.Remove(marker) }()
	_, err = r.k.run(ctx, nil, "cp", marker, pod+":/data/FETCHED", "-c", "buffon")
	return err
}

// unpack extracts a gzip tar of regular files and directories into dir, refusing any path that leaves it.
func unpack(data []byte, dir string) error {
	gz, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return err
	}
	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}
		name := filepath.FromSlash(hdr.Name)
		if !filepath.IsLocal(name) {
			return fmt.Errorf("the results archive holds %q, which leaves the run directory", hdr.Name)
		}
		path := filepath.Join(dir, name)
		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(path, 0o755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
				return err
			}
			f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
			if err != nil {
				return err
			}
			_, err = io.Copy(f, io.LimitReader(tr, hdr.Size))
			if err := errors.Join(err, f.Close()); err != nil {
				return err
			}
		default:
			return fmt.Errorf("the results archive holds %q of type %c; only files and directories come back", hdr.Name, hdr.Typeflag)
		}
	}
}

// runSpread runs se once per node, concurrently, each in dir/<run>-n<i>, and writes dir/spread.json. One failed
// session cancels the others: a spread is judged only whole.
func (r *runner) runSpread(ctx context.Context, se *session, nodes []string, dir string) ([]outcome, error) {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	shared := *r
	shared.progress = &lockedWriter{w: r.progress}
	r = &shared
	outs := make([]outcome, len(nodes))
	errs := make([]error, len(nodes))
	var wg sync.WaitGroup
	for i, node := range nodes {
		child := *se
		child.Run = fmt.Sprintf("%s-n%d", se.Run, i+1)
		wg.Go(func() {
			outs[i], errs[i] = r.runOne(ctx, &child, node, filepath.Join(dir, child.Run))
			if errs[i] != nil || !outs[i].OK {
				cancel()
			}
		})
	}
	wg.Wait()
	for i, o := range outs {
		if errs[i] == nil && !o.OK {
			errs[i] = fmt.Errorf("session %s on node %s: %s", o.Run, nodes[i], o.Message)
		}
	}
	data, err := json.MarshalIndent(map[string]any{"run": se.Run, "nodes": nodes, "sessions": outs}, "", "  ")
	if err != nil {
		return outs, err
	}
	if err := os.WriteFile(filepath.Join(dir, "spread.json"), append(data, '\n'), 0o644); err != nil {
		return outs, err
	}
	return outs, errors.Join(errs...)
}

// lockedWriter serialises the progress lines of concurrent sessions.
type lockedWriter struct {
	mu sync.Mutex
	w  io.Writer
}

func (l *lockedWriter) Write(p []byte) (int, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.w.Write(p)
}
