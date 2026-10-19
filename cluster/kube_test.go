// SPDX-License-Identifier: MIT

package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"sync"
	"testing"
	"time"
)

// fakeCluster answers the kubectl calls of one or more Jobs. Each Job's pod runs on the node its manifest pins (or
// node-x), prints the pod lines of a session, offers archive as its run directory, and completes once the runner
// has left the FETCHED marker.
type fakeCluster struct {
	mu        sync.Mutex
	calls     []string
	manifests map[string]string
	fetched   map[string]bool
	bundles   map[string][]byte
	// archive is what every pod hands back; failNode makes the pod on that node fail before it hands back anything.
	archive  []byte
	failNode string
	// corrupt makes the copied archive differ from the one the pod announced.
	corrupt bool
	// noDone makes every pod complete without its done line; hangNode's pod runs until its context ends.
	noDone   bool
	hangNode string
	// configz is the kubelet configuration the node proxy answers with; empty makes the request fail as when the caller may not read it.
	configz string
}

func newFakeCluster(archive []byte) *fakeCluster {
	return &fakeCluster{manifests: map[string]string{}, fetched: map[string]bool{}, bundles: map[string][]byte{}, archive: archive}
}

func jobName(manifest string) string {
	for line := range strings.Lines(manifest) {
		if v, ok := strings.CutPrefix(strings.TrimSpace(line), "name: "); ok {
			var s string
			_ = json.Unmarshal([]byte(v), &s)
			return s
		}
	}
	return ""
}

func manifestNode(manifest string) string {
	_, after, ok := strings.Cut(manifest, "operator: In\n")
	if !ok {
		return "node-x"
	}
	_, v, _ := strings.Cut(strings.SplitN(after, "\n", 2)[0], "values: [")
	var s string
	_ = json.Unmarshal([]byte(strings.TrimSuffix(v, "]")), &s)
	return s
}

func (f *fakeCluster) podLog(job string) string {
	node := manifestNode(f.manifests[job])
	if node == f.failNode {
		return `{"t":"facts"}` + "\n" + `{"t":"error","message":"the measured cores scale their clock with load"}` + "\n"
	}
	if node == f.hangNode {
		return `{"t":"facts"}` + "\n"
	}
	sum := sha256.Sum256(f.archive)
	log := `{"t":"facts","node":"` + node + `"}` + "\nnot json\n" + fmt.Sprintf(`{"t":"out","path":"/data/out.tar.gz","sha256":%q,"bytes":%d}`, hex.EncodeToString(sum[:]), len(f.archive)) + "\n"
	if f.fetched[job] && !f.noDone {
		log += `{"t":"done"}` + "\n"
	}
	return log
}

func (f *fakeCluster) run(_ context.Context, stdin []byte, args ...string) ([]byte, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls = append(f.calls, strings.Join(args, " "))
	switch {
	case args[0] == "apply":
		f.manifests[jobName(string(stdin))] = string(stdin)
		return nil, nil
	case args[0] == "get" && args[1] == "pods":
		job := strings.TrimPrefix(args[3], "job-name=")
		phase := "Running"
		if f.fetched[job] || manifestNode(f.manifests[job]) == f.failNode {
			phase = map[bool]string{true: "Succeeded", false: "Failed"}[f.fetched[job]]
		}
		return fmt.Appendf(nil, `{"items":[{"metadata":{"name":%q},"spec":{"nodeName":%q},"status":{"phase":%q,"qosClass":"Guaranteed","containerStatuses":[{"imageID":"registry.example/buffon@sha256:%s"}]}}]}`,
			job+"-pod", manifestNode(f.manifests[job]), phase, strings.Repeat("b", 64)), nil
	case args[0] == "get" && args[1] == "job":
		job := args[2]
		switch {
		case f.fetched[job]:
			return []byte(`{"status":{"conditions":[{"type":"Complete","status":"True"}]}}`), nil
		case manifestNode(f.manifests[job]) == f.failNode:
			return []byte(`{"status":{"conditions":[{"type":"Failed","status":"True","reason":"BackoffLimitExceeded"}]}}`), nil
		}
		return []byte(`{"status":{}}`), nil
	case args[0] == "logs":
		return []byte(f.podLog(strings.TrimSuffix(strings.TrimPrefix(args[1], "pod/"), "-pod"))), nil
	case args[0] == "cp":
		src, dst := args[1], args[2]
		if pod, path, ok := strings.Cut(src, ":"); ok {
			if path != "/data/out.tar.gz" || !strings.HasSuffix(pod, "-pod") {
				return nil, errors.New("unexpected copy from " + src)
			}
			data := f.archive
			if f.corrupt {
				data = append(slices.Clone(data), 0)
			}
			return nil, os.WriteFile(dst, data, 0o644)
		}
		pod, path, _ := strings.Cut(dst, ":")
		job := strings.TrimSuffix(pod, "-pod")
		switch path {
		case "/data/FETCHED":
			f.fetched[job] = true
		case bundleDir + "/bundle.tar.gz", bundleDir + "/READY":
			data, err := os.ReadFile(src)
			if err != nil {
				return nil, err
			}
			f.bundles[job+path] = data
		default:
			return nil, errors.New("unexpected copy to " + dst)
		}
		return nil, nil
	case args[0] == "delete":
		return nil, nil
	case args[0] == "get" && args[1] == "node":
		return []byte(`{"status":{"nodeInfo":{"kernelVersion":"6.8.0-test","kubeletVersion":"v1.35.0"},"capacity":{"cpu":"64"},"allocatable":{"cpu":"63"}}}`), nil
	case args[0] == "get" && args[1] == "--raw":
		if f.configz != "" {
			return []byte(f.configz), nil
		}
		return nil, errors.New(`Error from server (Forbidden): nodes "node-b" is forbidden`)
	}
	return nil, errors.New("unexpected kubectl call: " + strings.Join(args, " "))
}

// runArchive is a session run directory as a pod hands it back.
func runArchive(t *testing.T, files map[string]string) []byte {
	t.Helper()
	dir := t.TempDir()
	for name, content := range files {
		p := filepath.Join(dir, name)
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	archive := filepath.Join(t.TempDir(), "out.tar.gz")
	if _, _, err := packDir(dir, archive); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(archive)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func testRunner(k kube, st site) *runner {
	return &runner{k: k, st: st, poll: time.Millisecond, timeout: time.Minute, progress: &bytes.Buffer{}, now: time.Now}
}

func TestRunOneFetchesTheRunDirectoryAndLetsThePodExit(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"run/raw.json": `{"samples":{}}`, "cluster-facts.json": `{"node":"node-b"}`}))
	st := testSite()
	se := testSession()
	dir := filepath.Join(t.TempDir(), se.Run)
	o, err := testRunner(k, st).runOne(context.Background(), se, "node-b", dir)
	if err != nil {
		t.Fatal(err)
	}
	if !o.OK || o.Node != "node-b" || o.Pod != se.Run+"-pod" || o.Message != "" {
		t.Errorf("outcome %+v", o)
	}
	for _, name := range []string{"run/raw.json", "cluster-facts.json", "job.yaml", "pod.log"} {
		if _, err := os.Stat(filepath.Join(dir, name)); err != nil {
			t.Errorf("run directory lacks %s", name)
		}
	}
	if _, err := os.Stat(filepath.Join(dir, "out.tar.gz")); err == nil {
		t.Error("the archive stays in the run directory after unpacking")
	}
	// The out archive is copied before the marker, and the marker before the Job completes.
	order := func(prefix string) int {
		return slices.IndexFunc(k.calls, func(c string) bool { return strings.HasPrefix(c, prefix) })
	}
	cpOut := order("cp " + se.Run + "-pod:/data/out.tar.gz")
	cpMarker := slices.IndexFunc(k.calls, func(c string) bool { return strings.HasSuffix(c, se.Run+"-pod:/data/FETCHED -c buffon") })
	if cpOut < 0 || cpMarker < cpOut {
		t.Errorf("calls %v", k.calls)
	}
	if del := order("delete job,networkpolicy " + se.Run); del < cpMarker {
		t.Errorf("the Job is deleted before its results came back: %v", k.calls)
	}
	node, _ := os.ReadFile(filepath.Join(dir, "node.json"))
	if !strings.Contains(string(node), `"kernelVersion":"6.8.0-test"`) || !strings.Contains(string(node), `"cpuManagerPolicy":"unreadable"`) {
		t.Errorf("node.json %s", node)
	}
	// The API server's view of the pod while it ran: its QoS class and the digest of the image it runs.
	if !strings.Contains(string(node), `"podQosClass":"Guaranteed"`) || !strings.Contains(string(node), `"podImageID":"registry.example/buffon@sha256:`+strings.Repeat("b", 64)+`"`) {
		t.Errorf("node.json %s", node)
	}
}

func TestRunOneRefusesAnArchiveThatChangedOnTheWay(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"raw.json": "{}"}))
	k.corrupt = true
	_, err := testRunner(k, testSite()).runOne(context.Background(), testSession(), "", t.TempDir())
	if err == nil || !strings.Contains(err.Error(), "the pod sent") {
		t.Fatalf("err %v", err)
	}
	if slices.ContainsFunc(k.calls, func(c string) bool { return strings.Contains(c, "/data/FETCHED") }) {
		t.Error("a corrupt copy was acknowledged")
	}
}

func TestRunOneReportsThePodsOwnError(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"raw.json": "{}"}))
	k.failNode = "node-x"
	o, err := testRunner(k, testSite()).runOne(context.Background(), testSession(), "", t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if o.OK || !strings.Contains(o.Message, "scale their clock") {
		t.Errorf("outcome %+v", o)
	}
}

func TestRunOneCopiesTheBundleBeforeItCollects(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"raw.json": "{}"}))
	bundle := testBundle(t)
	st := testSite()
	st.Image, st.Bundle, st.BaseImage = "", bundle, "python@sha256:"+strings.Repeat("b", 64)
	arch, err := inspectBundle(bundle)
	if err != nil {
		t.Fatal(err)
	}
	tarPath, sum, err := packBundle(bundle, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	r := testRunner(k, st)
	r.bundleTar, r.bundle = tarPath, bundleRef{sha256: sum, arch: arch}
	se := testSession()
	o, err := r.runOne(context.Background(), se, "", t.TempDir())
	if err != nil || !o.OK {
		t.Fatalf("%+v %v", o, err)
	}
	copied := k.bundles[se.Run+bundleDir+"/bundle.tar.gz"]
	if got := sha256.Sum256(copied); hex.EncodeToString(got[:]) != sum {
		t.Errorf("the copied bundle is not the packed one")
	}
	bundleAt := slices.IndexFunc(k.calls, func(c string) bool { return strings.Contains(c, bundleDir+"/READY") })
	logsAt := slices.IndexFunc(k.calls, func(c string) bool { return strings.HasPrefix(c, "logs ") })
	if bundleAt < 0 || logsAt < bundleAt {
		t.Errorf("the READY marker must precede collecting: %v", k.calls)
	}
	if !strings.Contains(k.manifests[se.Run], sum) || !strings.Contains(k.manifests[se.Run], `"sh"`) {
		t.Errorf("the Job does not carry the bundle's sha256 and script")
	}
}

func TestRunSpreadRunsOneSessionPerNodeAndStopsOnAFailure(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"raw.json": "{}"}))
	se := testSession()
	dir := t.TempDir()
	outs, err := testRunner(k, testSite()).runSpread(context.Background(), se, []string{"node-a", "node-b"}, dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(outs) != 2 || outs[0].Node != "node-a" || outs[1].Node != "node-b" || !outs[0].OK || !outs[1].OK || outs[1].Run != se.Run+"-n2" {
		t.Errorf("outcomes %+v", outs)
	}
	var spread struct {
		Nodes []string `json:"nodes"`
	}
	data, _ := os.ReadFile(filepath.Join(dir, "spread.json"))
	if err := json.Unmarshal(data, &spread); err != nil || !slices.Equal(spread.Nodes, []string{"node-a", "node-b"}) {
		t.Errorf("spread.json %s %v", data, err)
	}
	k = newFakeCluster(runArchive(t, map[string]string{"raw.json": "{}"}))
	k.failNode = "node-a"
	outs, err = testRunner(k, testSite()).runSpread(context.Background(), se, []string{"node-a", "node-b"}, t.TempDir())
	if outs[0].OK || err == nil || !strings.Contains(err.Error(), "on node node-a: the measured cores scale their clock") {
		t.Errorf("a spread with a failed node passed: %+v %v", outs, err)
	}
}

// The run command end to end through a fake cluster: picks the nodes, runs one session per node, prints every
// outcome, and leaves the run directories under -out.
func TestRunCommandSpreadsOverPickedNodes(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"run/raw.json": `{"samples":{}}`}))
	routes := &routeKubectl{routes: map[string]string{"get nodes -o json": testNodes, "get pods --all-namespaces": testPods}}
	newKube = func(execKubectl) kube { return kubeMux{nodes: routes, jobs: k} }
	t.Cleanup(func() { newKube = func(k execKubectl) kube { return k } })
	dir := t.TempDir()
	sessionPath := filepath.Join(dir, "session.json")
	data, _ := marshalPlain(testSession())
	if err := os.WriteFile(sessionPath, data, 0o644); err != nil {
		t.Fatal(err)
	}
	st := testRoomValues()
	st.Namespace, st.Image = "buffon", testSite().Image
	sitePath := filepath.Join(dir, "site.json")
	data, _ = json.Marshal(st)
	if err := os.WriteFile(sitePath, data, 0o644); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	out := filepath.Join(dir, "out")
	code := run(context.Background(), []string{"run", "-site", sitePath, "-session", sessionPath, "-out", out, "-spread", "2", "-poll", "1ms"}, &stdout, &stderr, func(string) string { return "" })
	if code != exitOK {
		t.Fatalf("exit %d\n%s", code, stderr.String())
	}
	var outs []outcome
	if err := json.Unmarshal(stdout.Bytes(), &outs); err != nil || len(outs) != 2 || outs[0].Node != "idle" || outs[1].Node != "tainted-ok" {
		t.Fatalf("outcomes %s %v", stdout.String(), err)
	}
	for _, o := range outs {
		if _, err := os.Stat(filepath.Join(o.RunDir, "run", "raw.json")); err != nil || !strings.HasPrefix(o.RunDir, out) {
			t.Errorf("run directory %s: %v", o.RunDir, err)
		}
	}
	if _, err := os.Stat(filepath.Join(out, testSession().Run+"-nodes.json")); err != nil {
		t.Error("no node ranking recorded")
	}
}

// kubeMux sends node and pod listings to one fake and Job traffic to another.
type kubeMux struct {
	nodes *routeKubectl
	jobs  *fakeCluster
}

func (m kubeMux) run(ctx context.Context, stdin []byte, args ...string) ([]byte, error) {
	if len(args) > 1 && args[0] == "get" && (args[1] == "nodes" || (args[1] == "pods" && len(args) > 2 && args[2] != "-l")) {
		return m.nodes.run(ctx, stdin, args...)
	}
	return m.jobs.run(ctx, stdin, args...)
}

// A pod that completes without its done line did not finish its session cleanly; the outcome is not OK.
func TestRunOneRefusesAPodWithoutItsDoneLine(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"raw.json": "{}"}))
	k.noDone = true
	o, err := testRunner(k, testSite()).runOne(context.Background(), testSession(), "", t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if o.OK || !strings.Contains(o.Message, "without its done line") {
		t.Errorf("outcome %+v", o)
	}
}

// One failed session cancels the spread: the session still running on another node stops at once instead of
// running to its timeout.
func TestRunSpreadCancelsTheOtherNodesOnAFailure(t *testing.T) {
	k := newFakeCluster(runArchive(t, map[string]string{"raw.json": "{}"}))
	k.failNode, k.hangNode = "node-a", "node-b"
	r := testRunner(k, testSite())
	r.timeout = 30 * time.Second
	started := time.Now()
	_, err := r.runSpread(context.Background(), testSession(), []string{"node-a", "node-b"}, t.TempDir())
	if elapsed := time.Since(started); elapsed > 10*time.Second {
		t.Fatalf("the spread ran %s after node-a failed", elapsed)
	}
	if err == nil || !strings.Contains(err.Error(), context.Canceled.Error()) {
		t.Errorf("err %v, want node-b cancelled", err)
	}
}

func TestNodeFactsRecordTheCPUManagerPolicyAndItsOptions(t *testing.T) {
	k := &fakeCluster{configz: `{"kubeletconfig":{"cpuManagerPolicy":"static","cpuManagerPolicyOptions":{"full-pcpus-only":"true"},"topologyManagerPolicy":"single-numa-node"}}`}
	facts := clusterFacts(context.Background(), k, "node-b")
	data, _ := json.Marshal(facts)
	for _, want := range []string{`"cpuManagerPolicy":"static"`, `"full-pcpus-only":"true"`, `"topologyManagerPolicy":"single-numa-node"`} {
		if !strings.Contains(string(data), want) {
			t.Errorf("node facts lack %s: %s", want, data)
		}
	}
}
