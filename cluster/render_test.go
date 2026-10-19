// SPDX-License-Identifier: MIT

package main

import (
	"bytes"
	"context"
	"flag"
	"io"
	"net"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strings"
	"testing"
	"time"
)

func testSite() site {
	st := defaultSite()
	st.Namespace = "buffon"
	st.Image = "registry.example/buffon@sha256:" + strings.Repeat("a", 64)
	return st
}

func testSession() *session {
	return &session{Run: "buffon-overhead-20261011t120000", Argv: []string{"python3", "-m", "buffon", "overhead", "--out", "{out}"}, CPUs: 2, Pin: "auto", TimeoutSeconds: 3600}
}

// testBundle is a bundle directory whose buffon-cluster is this test binary (a Linux ELF program on Linux).
func testBundle(t *testing.T) string {
	t.Helper()
	if runtime.GOOS != "linux" {
		t.Skip("a bundle carries Linux ELF programs")
	}
	self, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "bin"), 0o755); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(self)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, bundleProgram), data, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "buffon.py"), []byte("print()\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	writeArtifacts(t, dir, bundleProgram, "buffon.py")
	return dir
}

func writeArtifacts(t *testing.T, dir string, names ...string) {
	t.Helper()
	var b strings.Builder
	for _, n := range names {
		sum, err := fileSHA256(filepath.Join(dir, n))
		if err != nil {
			t.Fatal(err)
		}
		b.WriteString(sum + "  " + n + "\n")
	}
	if err := os.WriteFile(filepath.Join(dir, "ARTIFACTS.sha256"), []byte(b.String()), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestRenderGuaranteedQoSAndPinning(t *testing.T) {
	for _, cpus := range []int{1, 2, 8} {
		st := testSite()
		st.CPUs, st.Memory = cpus, "16Gi"
		se := testSession()
		se.CPUs = cpus
		out, err := renderJob(st, se, "node-a", bundleRef{})
		if err != nil {
			t.Fatal(err)
		}
		text := string(out)
		want := []string{
			"requests:\n              cpu: \"" + itoa(cpus) + "\"\n              memory: \"16Gi\"",
			"limits:\n              cpu: \"" + itoa(cpus) + "\"\n              memory: \"16Gi\"",
			"key: metadata.name\n                    operator: In\n                    values: [\"node-a\"]",
			"runAsNonRoot: true", "readOnlyRootFilesystem: true", `drop: ["ALL"]`, "type: RuntimeDefault", "backoffLimit: 0",
			`command: ["/opt/buffon/bin/buffon-cluster","pod"]`,
		}
		for _, w := range want {
			if !strings.Contains(text, w) {
				t.Errorf("%d CPUs: manifest lacks %q:\n%s", cpus, w, text)
			}
		}
	}
	// The session the pod runs is the one rendered, exactly.
	out, _ := renderJob(testSite(), testSession(), "", bundleRef{})
	if strings.Contains(string(out), "affinity") {
		t.Error("an unpinned session names a node")
	}
	m := regexp.MustCompile(`name: BUFFON_SESSION\n\s+value: (".*")`).FindSubmatch(out)
	if m == nil {
		t.Fatalf("no session in:\n%s", out)
	}
	var encoded string
	if err := jsonUnmarshal(string(m[1]), &encoded); err != nil {
		t.Fatal(err)
	}
	got, err := decodeSession([]byte(encoded))
	if err != nil || !slices.Equal(got.Argv, testSession().Argv) || got.Run != testSession().Run {
		t.Errorf("session round trip %+v %v", got, err)
	}
}

// Each Job comes with a NetworkPolicy of the same name that selects only its pod and allows no traffic in or out:
// the pod-guaranteed envelope has no network but the mock, which runs on loopback inside the pod.
func TestRenderDeniesThePodsNetwork(t *testing.T) {
	se := testSession()
	out, err := renderJob(testSite(), se, "node-a", bundleRef{})
	if err != nil {
		t.Fatal(err)
	}
	docs := strings.Split(string(out), "\n---\n")
	if len(docs) != 2 || !strings.Contains(docs[0], "kind: Job") {
		t.Fatalf("want a Job and a NetworkPolicy:\n%s", out)
	}
	policy := docs[1]
	labels := `{"app.kubernetes.io/managed-by":"buffon-cluster","app.kubernetes.io/name":"buffon","buffon/run":"` + se.Run + `"}`
	for _, w := range []string{"kind: NetworkPolicy", "name: \"" + se.Run + "\"", "namespace: \"" + testSite().Namespace + "\"", "matchLabels: " + labels, `policyTypes: ["Ingress", "Egress"]`} {
		if !strings.Contains(policy, w) {
			t.Errorf("the policy lacks %q:\n%s", w, policy)
		}
	}
	for _, rule := range []string{"ingress:", "egress:"} {
		if strings.Contains(policy, rule) {
			t.Errorf("the policy allows traffic (%s):\n%s", rule, policy)
		}
	}
	if !strings.Contains(docs[0], "labels: "+labels) {
		t.Errorf("the pod does not carry the labels the policy selects:\n%s", docs[0])
	}
}

func TestRenderPoolSecretsAndOptionalValues(t *testing.T) {
	st := testSite()
	st.NodeSelector = map[string]string{"pool": "bench"}
	st.Tolerations = []toleration{{Key: "dedicated", Operator: "Equal", Value: "bench", Effect: "NoSchedule"}}
	st.PVC, st.ServiceAccountName, st.ImagePullSecrets = "buffon-results", "buffon-runner", []string{"pull-b", "pull-a"}
	st.SecretEnv = []secretEnv{{Name: "BUFFON_TOKEN", Secret: "buffon-secrets", Key: "token"}}
	out, err := renderJob(st, testSession(), "", bundleRef{})
	if err != nil {
		t.Fatal(err)
	}
	text := string(out)
	for _, w := range []string{
		`nodeSelector: {"pool":"bench"}`, `tolerations: [{"key":"dedicated","operator":"Equal","value":"bench","effect":"NoSchedule"}]`,
		`claimName: "buffon-results"`, `serviceAccountName: "buffon-runner"`, `imagePullSecrets: [{"name":"pull-a"},{"name":"pull-b"}]`,
		"name: \"BUFFON_TOKEN\"\n              valueFrom:\n                secretKeyRef:\n                  name: \"buffon-secrets\"\n                  key: \"token\"",
	} {
		if !strings.Contains(text, w) {
			t.Errorf("manifest lacks %q:\n%s", w, text)
		}
	}
	// Unset optional values leave no key behind.
	out, _ = renderJob(testSite(), testSession(), "", bundleRef{})
	for _, absent := range []string{"nodeSelector", "tolerations", "claimName", "serviceAccountName", "imagePullSecrets", "secretKeyRef", "mountPath: /bundle"} {
		if strings.Contains(string(out), absent) {
			t.Errorf("unset value %s rendered", absent)
		}
	}
}

func TestRenderRefusals(t *testing.T) {
	cases := []struct {
		edit func(*site, *session)
		want string
	}{
		{func(_ *site, se *session) { se.CPUs = 3 }, "the session pins 3 cores but the pod requests 2 CPUs"},
		{func(_ *site, se *session) { se.Argv = []string{"python3", "-m", "buffon"} }, "argv never names {out}"},
		{func(_ *site, se *session) { se.Env = map[string]string{"HOME": "/x"} }, "env HOME is set by the pod"},
		{func(_ *site, se *session) { se.Run = "Buffon_Run" }, "is not a DNS label"},
		{func(_ *site, se *session) { se.Pin = "fast" }, "pin \"fast\" is not auto, none or a CPU list"},
		// Refused before a pod is scheduled, not only by the pod session.
		{func(_ *site, se *session) { se.Pin = "4-6" }, "pin list 4-6 names 3 CPUs, the pod has 2"},
		{func(st *site, _ *session) {
			st.Image, st.Bundle, st.BaseImage = "", "/b", "python@sha256:"+strings.Repeat("b", 64)
		}, "bundle mode needs the bundle's sha256"},
	}
	for _, c := range cases {
		st, se := testSite(), testSession()
		c.edit(&st, se)
		if _, err := renderJob(st, se, "", bundleRef{}); err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("err %v, want %q", err, c.want)
		}
	}
}

// Every value in a manifest is a template constant or a configured value: the committed sources name no cluster,
// host or address.
func TestCommittedFilesNameNoHostOrCluster(t *testing.T) {
	var files []string
	for _, pattern := range []string{"*.go", "*.md", "*.json", "templates/*"} {
		m, _ := filepath.Glob(pattern)
		files = append(files, m...)
	}
	ip := regexp.MustCompile(`\b(?:\d{1,3}\.){3}\d{1,3}\b`)
	hostish := regexp.MustCompile(`(?i)\b[a-z0-9-]+\.(?:internal|local|lan|corp|cluster\.local)\b|kubeconfig\s*[:=]\s*"?[~/]`)
	for _, f := range files {
		if strings.HasSuffix(f, "_test.go") || f == "go.mod" {
			continue
		}
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		for _, m := range ip.FindAllString(string(data), -1) {
			if net.ParseIP(m) != nil && m != "0.0.0.0" && m != "127.0.0.1" {
				t.Errorf("%s names address %s", f, m)
			}
		}
		if m := hostish.FindString(strings.ReplaceAll(string(data), "site.local.json", "")); m != "" {
			t.Errorf("%s names %q", f, m)
		}
	}
}

func TestSiteLayersAndValidates(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "site.json")
	if err := os.WriteFile(path, []byte(`{"namespace":"from-file","image":"registry.example/buffon@sha256:`+strings.Repeat("c", 64)+`","cpus":4,"nodeSelector":{"pool":"bench"}}`), 0o644); err != nil {
		t.Fatal(err)
	}
	env := map[string]string{"BUFFON_K8S_NAMESPACE": "from-env", "BUFFON_K8S_CPUS": "6"}
	fs := newFlagSet()
	apply := siteFlags(fs)
	if err := fs.Parse([]string{"-cpus", "8"}); err != nil {
		t.Fatal(err)
	}
	st, err := loadSite(path, apply, func(k string) string { return env[k] })
	if err != nil {
		t.Fatal(err)
	}
	if st.Namespace != "from-env" || st.CPUs != 8 || st.NodeSelector["pool"] != "bench" || st.Memory != "8Gi" {
		t.Errorf("site %+v", st)
	}
	bad := []struct{ json, want string }{
		{`{"namespace":"<namespace>","image":"x@sha256:` + strings.Repeat("c", 64) + `"}`, "still holds a placeholder"},
		{`{"namespace":"ns","image":"registry.example/buffon:latest"}`, "is not pinned by digest"},
		{`{"namespace":"ns","bundle":"/b"}`, "bundle mode needs a baseImage"},
		{`{"namespace":"ns","bundle":"/b","baseImage":"python:3.12"}`, "baseImage \"python:3.12\" is not pinned"},
		{`{"namespace":"ns"}`, "neither image nor bundle is set"},
		{`{"namespace":"ns","image":"x@sha256:` + strings.Repeat("c", 64) + `","cpus":0}`, "cpus must be a whole number"},
		{`{"namespace":"ns","image":"x@sha256:` + strings.Repeat("c", 64) + `","secretEnv":[{"name":"A B","secret":"s","key":"k"}]}`, "secretEnv"},
		{`{"namespace":"ns","image":"x@sha256:` + strings.Repeat("c", 64) + `","maxCv":2}`, "maxCv 2"},
		{`{"namespace":"ns","image":"x","kubeconfg":"y"}`, "unknown field"},
	}
	for _, b := range bad {
		if err := os.WriteFile(path, []byte(b.json), 0o644); err != nil {
			t.Fatal(err)
		}
		if _, err := loadSite(path, func(*site) error { return nil }, func(string) string { return "" }); err == nil || !strings.Contains(err.Error(), b.want) {
			t.Errorf("%s: err %v, want %q", b.json, err, b.want)
		}
	}
}

func TestSiteExampleIsAPlaceholder(t *testing.T) {
	_, err := loadSite("site.example.json", func(*site) error { return nil }, func(string) string { return "" })
	if err == nil || !strings.Contains(err.Error(), "still holds a placeholder") {
		t.Errorf("the example site must refuse to run as it is: %v", err)
	}
}

func TestInspectBundle(t *testing.T) {
	dir := testBundle(t)
	if arch, err := inspectBundle(dir); err != nil || arch != runtime.GOARCH {
		t.Fatalf("%s %v", arch, err)
	}
	if err := os.WriteFile(filepath.Join(dir, "buffon.py"), []byte("changed\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := inspectBundle(dir); err == nil || !strings.Contains(err.Error(), "buffon.py has sha256") {
		t.Errorf("tampered: %v", err)
	}
	writeArtifacts(t, dir, "buffon.py")
	if _, err := inspectBundle(dir); err == nil || !strings.Contains(err.Error(), "does not list bin/buffon-cluster") {
		t.Errorf("no program: %v", err)
	}
}

func TestRenderCommandPrintsOneManifestPerNode(t *testing.T) {
	dir := t.TempDir()
	sessionPath := filepath.Join(dir, "session.json")
	data, _ := marshalPlain(testSession())
	if err := os.WriteFile(sessionPath, data, 0o644); err != nil {
		t.Fatal(err)
	}
	env := map[string]string{"BUFFON_K8S_NAMESPACE": "buffon", "BUFFON_K8S_IMAGE": testSite().Image}
	var stdout, stderr bytes.Buffer
	missing := filepath.Join(dir, "no-kubectl")
	code := run(context.Background(), []string{"render", "-session", sessionPath, "-kubectl", missing, "-nodes", "node-a,node-b"}, &stdout, &stderr, func(k string) string { return env[k] })
	if code != 0 || strings.Count(stdout.String(), "kind: Job") != 2 || !strings.Contains(stdout.String(), "buffon-overhead-20261011t120000-n2") {
		t.Errorf("exit %d\n%s\n%s", code, stdout.String(), stderr.String())
	}
	code = run(context.Background(), []string{"render", "-session", sessionPath, "-nodes", "node-a,node-a"}, io.Discard, &stderr, func(k string) string { return env[k] })
	if code != exitUsage {
		t.Errorf("duplicate node: exit %d", code)
	}
}

// sleepCtx returns early when the context ends.
func TestSleepCtx(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := sleepCtx(ctx, time.Hour); err == nil {
		t.Error("slept through a cancelled context")
	}
}

func newFlagSet() *flag.FlagSet {
	fs := flag.NewFlagSet("test", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	return fs
}

func TestExpandPathExpandsTildeAndVariablesLikeThePythonRunner(t *testing.T) {
	env := map[string]string{"HOME": "/users/op", "KDIR": "/etc/k"}
	get := func(k string) string { return env[k] }
	for in, want := range map[string]string{
		"":                   "",
		"~/.kube/cfg":        "/users/op/.kube/cfg",
		"~":                  "/users/op",
		"$HOME/.kube/cfg":    "/users/op/.kube/cfg",
		"${KDIR}/cfg":        "/etc/k/cfg",
		"/abs/path":          "/abs/path",
		"~other/.kube":       "~other/.kube",
		"relative/cfg":       "relative/cfg",
		"/with~tilde/inside": "/with~tilde/inside",
	} {
		if got := expandPath(in, get); got != want {
			t.Errorf("expandPath(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestLoadSiteExpandsTheKubeconfigPath(t *testing.T) {
	path := filepath.Join(t.TempDir(), "site.json")
	body := `{"kubeconfig": "~/.kube/bench", "namespace": "ns", "image": "reg.example/buffon@sha256:` + strings.Repeat("a", 64) + `", "cpus": 2}`
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	st, err := loadSite(path, func(*site) error { return nil }, func(k string) string {
		if k == "HOME" {
			return "/users/op"
		}
		return ""
	})
	if err != nil {
		t.Fatal(err)
	}
	if st.Kubeconfig != "/users/op/.kube/bench" {
		t.Fatalf("kubeconfig = %q", st.Kubeconfig)
	}
}

func TestKubectlNamesAMissingKubeconfigInsteadOfLettingKubectlFail(t *testing.T) {
	k := execKubectl{bin: "/nonexistent/kubectl", kubeconfig: filepath.Join(t.TempDir(), "nope")}
	_, err := k.run(context.Background(), nil, "get", "nodes")
	if err == nil || !strings.Contains(err.Error(), "kubeconfig") || !strings.Contains(err.Error(), "cannot be opened") {
		t.Fatalf("err = %v", err)
	}
}
