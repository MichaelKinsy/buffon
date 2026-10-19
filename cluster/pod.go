// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

package main

import (
	"archive/tar"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"time"
)

// podEnv is what the in-pod session depends on outside the session spec.
type podEnv struct {
	sys system
	// root is Buffon install root ({root}; /opt/buffon in the image, the unpacked bundle in bundle mode).
	root string
	// data is the writable scratch directory (the pod's emptyDir); the run directory and its archive live there.
	data string
	// results, when it names a directory, receives a copy of the run archive (the optional PVC).
	results string
	node    string
	pod     string
	getenv  func(string) string
	// ensure lists directories the session creates before it runs anything (TMPDIR and HOME).
	ensure []string
	// pinWait waits between the two /proc/stat readings that find the quietest cores.
	pinWait func(context.Context) error
	// fetchWait waits for the runner to copy the run archive out; it returns once the FETCHED marker exists.
	fetchWait func(context.Context, string) error
	now       func() time.Time
	taskset   func() (string, error)
}

// fetchTimeout bounds how long a pod waits for the runner to copy its results out.
const fetchTimeout = 30 * time.Minute

func podEnvFromOS() podEnv {
	env := podEnv{sys: system{root: "/"}, root: imageRoot, data: "/data", results: "/results", node: os.Getenv("NODE_NAME"), pod: os.Getenv("POD_NAME"), now: time.Now, getenv: os.Getenv,
		pinWait:   func(ctx context.Context) error { return sleepCtx(ctx, time.Second) },
		fetchWait: waitForFile(time.Second, fetchTimeout),
		taskset:   func() (string, error) { return exec.LookPath("taskset") },
	}
	if s := os.Getenv("BUFFON_ROOT"); s != "" {
		env.root = s
	}
	// BUFFON_DATA and BUFFON_RESULTS move the scratch and results directories, for a pod session run by hand outside a
	// pod (the Job leaves them at /data and /results).
	if s := os.Getenv("BUFFON_DATA"); s != "" {
		env.data = s
	}
	if s, ok := os.LookupEnv("BUFFON_RESULTS"); ok {
		env.results = s
	}
	for _, name := range []string{"TMPDIR", "HOME"} {
		if dir := os.Getenv(name); dir != "" {
			env.ensure = append(env.ensure, dir)
		}
	}
	return env
}

func waitForFile(poll, limit time.Duration) func(context.Context, string) error {
	return func(ctx context.Context, path string) error {
		end := time.Now().Add(limit)
		for {
			if _, err := os.Stat(path); err == nil {
				return nil
			}
			if time.Now().After(end) {
				return fmt.Errorf("the runner did not fetch the results within %s", limit)
			}
			if err := sleepCtx(ctx, poll); err != nil {
				return err
			}
		}
	}
}

// podRun is one pod's run of a session. Every line it prints is one JSON object with a "t" field; the runner reads
// the pod log and ignores any other line.
type podRun struct {
	se      *session
	env     podEnv
	out     io.Writer
	pin     []int
	taskset string
	// gomaxprocs is the number of measured cores, at most the pod's CPUs (its limit). A Go arm otherwise derives it
	// from the node's CPUs or the quota, which differ between node types.
	gomaxprocs int
	outDir     string
	facts      *object
}

func (r *podRun) emit(o *object) error {
	line, err := o.MarshalJSON()
	if err != nil {
		return err
	}
	_, err = r.out.Write(append(line, '\n'))
	return err
}

// Pod log line types the runner reads.
const (
	lineError = "error"
	lineOut   = "out"
	lineDone  = "done"
)

// runPod runs the session: node facts, pinning (refusing cores whose clock scales unless allowed), the session
// command on the pinned cores with the cgroup's CPU counters around it, then the run directory packed for the runner,
// which copies it out and leaves a FETCHED marker. A failed session still hands back its run directory.
func runPod(ctx context.Context, se *session, env podEnv, out io.Writer) error {
	if err := se.validate(); err != nil {
		return err
	}
	r := &podRun{se: se, env: env, out: out, outDir: filepath.Join(env.data, "out", se.Run)}
	for _, dir := range append([]string{r.outDir}, env.ensure...) {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	if err := r.collectFacts(); err != nil {
		return err
	}
	pinErr := r.choosePin(ctx)
	var runErr error
	if pinErr == nil {
		runErr = r.runSession(ctx)
	}
	if err := writeJSON(filepath.Join(r.outDir, "cluster-facts.json"), r.facts); err != nil {
		return err
	}
	if err := r.handBack(ctx); err != nil {
		return errors.Join(pinErr, runErr, err)
	}
	if err := errors.Join(pinErr, runErr); err != nil {
		return err
	}
	done := newObject()
	done.set("t", lineDone)
	done.set("at", env.now().UTC().Format(time.RFC3339))
	return r.emit(done)
}

func (r *podRun) collectFacts() error {
	sys := r.env.sys
	o := newObject()
	o.set("t", "facts")
	o.set("run", r.se.Run)
	o.set("node", r.env.node)
	o.set("pod", r.env.pod)
	kernel, _ := sys.read("proc/sys/kernel/osrelease")
	o.set("kernel", kernel)
	o.set("cpuModel", sys.cpuModel())
	o.set("cpuFeatures", strings.Join(sys.cpuFeatures(), " "))
	online, _ := sys.read("sys/devices/system/cpu/online")
	o.set("cpusOnline", online)
	allowed, err := sys.cpusAllowed()
	if err != nil {
		return err
	}
	o.set("cpusAllowed", formatCPUList(allowed))
	o.set("requestedCpus", r.se.CPUs)
	// With the static CPU manager policy a Guaranteed pod with integer CPUs gets exactly that many cores; any other
	// policy leaves it on the shared pool, limited only by its CFS quota.
	cpuSet := "shared"
	if len(allowed) == r.se.CPUs {
		cpuSet = "exclusive"
	}
	o.set("cpuSet", cpuSet)
	o.set("cgroup", sys.cgroupVersion())
	o.set("cpuMax", sys.cpuMax())
	o.set("memoryMax", sys.memoryMax())
	load, _ := sys.read("proc/loadavg")
	o.set("loadavg", load)
	o.set("helperGo", runtime.Version())
	o.set("delivery", r.env.getenv("BUFFON_DELIVERY"))
	if ref := r.env.getenv("BUFFON_IMAGE_REF"); ref != "" {
		o.set("image", ref)
	}
	if sum := r.env.getenv("BUFFON_BUNDLE_SHA256"); sum != "" {
		o.set("bundleSha256", sum)
	}
	if text, err := os.ReadFile(filepath.Join(r.env.root, "ARTIFACTS.sha256")); err == nil {
		sum := sha256.Sum256(text)
		o.set("artifactsSha256", hex.EncodeToString(sum[:]))
	}
	o.set("at", r.env.now().UTC().Format(time.RFC3339))
	r.facts = o
	return r.emit(o)
}

// choosePin picks the cores the session runs on and refuses cores whose clock scales with load: CPU times would
// then follow the clock, not the work.
func (r *podRun) choosePin(ctx context.Context) error {
	pinLine := newObject()
	pinLine.set("t", "pin")
	sys := r.env.sys
	allowed, err := sys.cpusAllowed()
	if err != nil {
		return err
	}
	method := r.se.Pin
	switch {
	case r.se.Pin == "none":
		r.pin = nil
	case r.se.Pin != "auto":
		r.pin, err = parseCPUList(r.se.Pin)
		if err != nil {
			return err
		}
		for _, c := range r.pin {
			if !slices.Contains(allowed, c) {
				return fmt.Errorf("pin list %s names CPU %d, which the pod may not use (allowed %s)", r.se.Pin, c, formatCPUList(allowed))
			}
		}
		method = "list"
	case len(allowed) <= r.se.CPUs:
		r.pin = allowed
		method = "all-allowed"
	default:
		before, err := sys.idleTicks()
		if err != nil {
			return err
		}
		if err := r.env.pinWait(ctx); err != nil {
			return err
		}
		after, err := sys.idleTicks()
		if err != nil {
			return err
		}
		var idle map[int]float64
		r.pin, idle = quietest(allowed, before, after, r.se.CPUs)
		method = "quietest"
		shares := newObject()
		for _, c := range r.pin {
			shares.set(strconv.Itoa(c), roundTo(idle[c], 3))
		}
		pinLine.set("idle", shares)
	}
	pinLine.set("method", method)
	pinLine.set("cpus", formatCPUList(r.pin))
	if len(r.pin) > 0 {
		r.taskset, err = r.env.taskset()
		if err != nil {
			return fmt.Errorf("pinning needs taskset (util-linux): %w", err)
		}
	}
	measured := r.pin
	if len(measured) == 0 {
		measured = allowed
	}
	r.gomaxprocs = min(len(measured), r.se.CPUs)
	pinLine.set("gomaxprocs", r.gomaxprocs)
	governors := newObject()
	var scaling []string
	for _, c := range measured {
		g := sys.governor(c)
		if g != "" {
			governors.set(strconv.Itoa(c), g)
		}
		if !fixedClock(g) {
			scaling = append(scaling, fmt.Sprintf("%d (%s)", c, g))
		}
	}
	pinLine.set("governors", governors)
	pinLine.set("fixedClock", len(scaling) == 0)
	r.facts.set("pin", pinLine)
	if err := r.emit(pinLine); err != nil {
		return err
	}
	if len(scaling) > 0 && !r.se.AllowFrequencyScaling {
		return fmt.Errorf("the measured cores scale their clock with load: CPU %s; CPU times would follow the clock, not the work, so this node is refused: run on a node whose cores have a fixed clock (no cpufreq governor, or performance), or allow frequency scaling for a run that is reported but never judged", strings.Join(scaling, ", "))
	}
	return nil
}

// expand substitutes {root}, {out} and {cpus} in one argument.
func (r *podRun) expand(arg string) string {
	return strings.NewReplacer("{root}", r.env.root, "{out}", r.outDir, "{cpus}", formatCPUList(r.pin)).Replace(arg)
}

// command resolves argv[0] in {root}/bin, then PATH.
func (r *podRun) command() []string {
	argv := make([]string, len(r.se.Argv))
	for i, a := range r.se.Argv {
		argv[i] = r.expand(a)
	}
	if !strings.Contains(argv[0], "/") {
		if p := filepath.Join(r.env.root, "bin", argv[0]); isExecutable(p) {
			argv[0] = p
		}
	}
	if len(r.pin) > 0 {
		argv = append([]string{r.taskset, "-c", formatCPUList(r.pin)}, argv...)
	}
	return argv
}

func isExecutable(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.Mode().IsRegular() && info.Mode()&0o111 != 0
}

// runSession runs the session command with the cgroup CPU counters and the clock sampled around it. Its stdout and
// stderr go to session.log in the run directory.
func (r *podRun) runSession(ctx context.Context) error {
	argv := r.command()
	ctx, cancel := context.WithTimeout(ctx, time.Duration(r.se.TimeoutSeconds)*time.Second)
	defer cancel()
	logPath := filepath.Join(r.outDir, "session.log")
	logFile, err := os.Create(logPath)
	if err != nil {
		return err
	}
	defer func() { _ = logFile.Close() }()
	cmd := exec.CommandContext(ctx, argv[0], argv[1:]...)
	cmd.Stdout, cmd.Stderr = logFile, logFile
	cmd.WaitDelay = 10 * time.Second
	cmd.Dir = r.env.root
	cmd.Env = append(os.Environ(), sessionEnv(r.se)...)
	// The session reads the pod's facts (buffon/envelope/pod.py) to decide whether the pod is its envelope.
	factsPath := filepath.Join(r.env.data, "pod-facts.json")
	if err := writeJSON(factsPath, r.facts); err != nil {
		return err
	}
	cmd.Env = append(cmd.Env, "BUFFON_OUT="+r.outDir, "BUFFON_PINNED_CPUS="+formatCPUList(r.pin), "GOMAXPROCS="+strconv.Itoa(r.gomaxprocs), "BUFFON_POD_FACTS="+factsPath)
	before, haveStat := r.env.sys.cpuStat()
	clock := r.sampleClock(50 * time.Millisecond)
	started := r.env.now()
	runErr := cmd.Run()
	wall := r.env.now().Sub(started)
	mhz, mhzLo, mhzHi, haveClock := clock.finish()
	after, _ := r.env.sys.cpuStat()
	line := newObject()
	line.set("t", "cpu")
	line.set("argv", argv)
	line.set("wallMs", roundTo(float64(wall.Microseconds())/1000, 3))
	exit := 0
	if runErr != nil {
		exit = -1
		if ee, ok := errors.AsType[*exec.ExitError](runErr); ok {
			exit = ee.ExitCode()
		}
	}
	line.set("exit", exit)
	if haveStat {
		d := after.minus(before)
		if d.HaveUsage {
			line.set("usageUsec", d.UsageUsec)
		}
		line.set("nrPeriods", d.NrPeriods)
		line.set("nrThrottled", d.NrThrottled)
		line.set("throttledUsec", d.ThrottledUsec)
	}
	if haveClock {
		line.set("mhz", roundTo(mhz, 1))
		line.set("mhzMin", roundTo(mhzLo, 1))
		line.set("mhzMax", roundTo(mhzHi, 1))
	}
	r.facts.set("session", line)
	if err := r.emit(line); err != nil {
		return err
	}
	if runErr != nil {
		return fmt.Errorf("session %s: %w; session.log ends: %s", r.se.Run, runErr, tail(logPath, 2048))
	}
	return nil
}

// handBack packs the run directory, announces it with its sha256 for the runner to copy out, and waits for the
// runner's FETCHED marker. The optional results volume receives a copy of the archive.
func (r *podRun) handBack(ctx context.Context) error {
	archive := filepath.Join(r.env.data, "out.tar.gz")
	sum, size, err := packDir(r.outDir, archive)
	if err != nil {
		return err
	}
	if r.env.results != "" {
		if info, err := os.Stat(r.env.results); err == nil && info.IsDir() {
			if err := copyFile(archive, filepath.Join(r.env.results, r.se.Run+".tar.gz")); err != nil {
				return err
			}
		}
	}
	o := newObject()
	o.set("t", lineOut)
	o.set("path", archive)
	o.set("sha256", sum)
	o.set("bytes", size)
	if err := r.emit(o); err != nil {
		return err
	}
	return r.env.fetchWait(ctx, filepath.Join(r.env.data, "FETCHED"))
}

// clockSampler samples the measured cores' clock while the session runs: every interval, the highest current clock
// among the cores (the busy core runs at it; an idle core's clock says nothing about the work).
type clockSampler struct {
	stop chan struct{}
	done chan struct{}
	mhz  []float64
}

func (r *podRun) sampleClock(interval time.Duration) *clockSampler {
	cores := r.pin
	if len(cores) == 0 {
		return nil
	}
	if _, ok := r.env.sys.curMHz(cores[0]); !ok {
		return nil
	}
	c := &clockSampler{stop: make(chan struct{}), done: make(chan struct{})}
	go func() {
		defer close(c.done)
		t := time.NewTicker(interval)
		defer t.Stop()
		for {
			top := 0.0
			for _, cpu := range cores {
				if v, ok := r.env.sys.curMHz(cpu); ok {
					top = max(top, v)
				}
			}
			if top > 0 {
				c.mhz = append(c.mhz, top)
			}
			select {
			case <-c.stop:
				return
			case <-t.C:
			}
		}
	}()
	return c
}

// finish stops the sampler and returns the mean, lowest and highest sampled clock.
func (c *clockSampler) finish() (mean, lo, hi float64, ok bool) {
	if c == nil {
		return 0, 0, 0, false
	}
	close(c.stop)
	<-c.done
	if len(c.mhz) == 0 {
		return 0, 0, 0, false
	}
	lo, hi = c.mhz[0], c.mhz[0]
	for _, v := range c.mhz {
		mean += v
		lo, hi = min(lo, v), max(hi, v)
	}
	return mean / float64(len(c.mhz)), lo, hi, true
}

func tail(path string, n int64) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	if int64(len(data)) > n {
		data = data[int64(len(data))-n:]
	}
	return strings.TrimSpace(strings.ReplaceAll(string(data), "\r", "\n"))
}

func writeJSON(path string, o *object) error {
	data, err := o.MarshalJSON()
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer func() { _ = in.Close() }()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		_ = out.Close()
		return err
	}
	return out.Close()
}

// packDir writes dir's regular files and directories as a gzip tar (paths relative to dir, in walk order) and
// returns its sha256 and size.
func packDir(dir, archive string) (string, int64, error) {
	f, err := os.Create(archive)
	if err != nil {
		return "", 0, err
	}
	h := sha256.New()
	gz := gzip.NewWriter(io.MultiWriter(f, h))
	tw := tar.NewWriter(gz)
	walkErr := filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(dir, path)
		if err != nil || rel == "." {
			return err
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() && !info.IsDir() {
			return nil
		}
		hdr, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		hdr.Name = filepath.ToSlash(rel)
		hdr.Uid, hdr.Gid, hdr.Uname, hdr.Gname = 0, 0, "", ""
		if err := tw.WriteHeader(hdr); err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}
		src, err := os.Open(path)
		if err != nil {
			return err
		}
		_, err = io.Copy(tw, src)
		return errors.Join(err, src.Close())
	})
	err = errors.Join(walkErr, tw.Close(), gz.Close())
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		return "", 0, err
	}
	info, err := os.Stat(archive)
	if err != nil {
		return "", 0, err
	}
	return hex.EncodeToString(h.Sum(nil)), info.Size(), nil
}
