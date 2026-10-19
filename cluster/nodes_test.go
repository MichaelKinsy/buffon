// SPDX-License-Identifier: MIT

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"slices"
	"strings"
	"testing"
)

func TestParseQuantity(t *testing.T) {
	for in, want := range map[string]float64{
		"48": 48, "47500m": 47.5, "0.5": 0.5, "100m": 0.1, "1e3": 1000,
		"380Gi": 380 << 30, "395000000Ki": 395000000 << 10, "512M": 512e6, "2k": 2000, "1Ti": 1 << 40,
	} {
		got, err := parseQuantity(in)
		if err != nil || got != want {
			t.Errorf("%s: %v %v, want %v", in, got, err, want)
		}
	}
	for _, in := range []string{"", "Gi", "1Xi", "1.2.3", "ten"} {
		if _, err := parseQuantity(in); err == nil {
			t.Errorf("%q accepted", in)
		}
	}
}

func podOf(t *testing.T, text string) k8sPod {
	t.Helper()
	var p k8sPod
	if err := jsonUnmarshal(text, &p); err != nil {
		t.Fatal(err)
	}
	return p
}

// A pod reserves its containers' summed requests or, when larger, its largest init container's, plus its overhead.
func TestPodRequests(t *testing.T) {
	p := podOf(t, `{"spec":{"containers":[{"resources":{"requests":{"cpu":"500m","memory":"1Gi"}}},{"resources":{"requests":{"cpu":"1"}}}],
		"initContainers":[{"resources":{"requests":{"cpu":"2","memory":"512Mi"}}}],"overhead":{"cpu":"250m"}}}`)
	if got := podRequests(p, "cpu"); got != 2.25 {
		t.Errorf("cpu %v", got)
	}
	if got := podRequests(p, "memory"); got != 1<<30 {
		t.Errorf("memory %v", got)
	}
	if got := podRequests(k8sPod{}, "cpu"); got != 0 {
		t.Errorf("a pod without requests reserves nothing: %v", got)
	}

	// Sidecars (init containers with restartPolicy Always) run beside the app containers, so their requests add to
	// the sum, and a later init container runs beside the sidecars started before it.
	p = podOf(t, `{"spec":{"containers":[{"resources":{"requests":{"cpu":"1"}}}],
		"initContainers":[{"restartPolicy":"Always","resources":{"requests":{"cpu":"500m"}}},{"resources":{"requests":{"cpu":"2"}}}]}}`)
	if got := podRequests(p, "cpu"); got != 2.5 {
		t.Errorf("sidecar then init: cpu %v, want max(1+0.5, 2+0.5)", got)
	}
	p = podOf(t, `{"spec":{"containers":[{"resources":{"requests":{"cpu":"1"}}}],
		"initContainers":[{"restartPolicy":"Always","resources":{"requests":{"cpu":"1"}}},{"resources":{"requests":{"cpu":"500m"}}}]}}`)
	if got := podRequests(p, "cpu"); got != 2 {
		t.Errorf("sidecar beside the app: cpu %v, want 1+1", got)
	}
	// Pod-level requests replace the containers' aggregate for the resources they set.
	p = podOf(t, `{"spec":{"resources":{"requests":{"cpu":"3"}},"containers":[{"resources":{"requests":{"cpu":"1","memory":"1Gi"}}}],"overhead":{"cpu":"250m"}}}`)
	if got := podRequests(p, "cpu"); got != 3.25 {
		t.Errorf("pod-level cpu %v", got)
	}
	if got := podRequests(p, "memory"); got != 1<<30 {
		t.Errorf("memory without a pod-level request %v", got)
	}
}

func TestTolerates(t *testing.T) {
	ts := []toleration{{Key: "dedicated", Operator: "Equal", Value: "bench", Effect: "NoSchedule"}, {Key: "gpu", Operator: "Exists"}}
	for _, c := range []struct {
		key, value, effect string
		want               bool
	}{
		{"dedicated", "bench", "NoSchedule", true},
		{"dedicated", "bench", "NoExecute", false},
		{"dedicated", "other", "NoSchedule", false},
		{"gpu", "any", "NoExecute", true},
		{"other", "", "NoSchedule", false},
	} {
		if got := tolerates(ts, c.key, c.value, c.effect); got != c.want {
			t.Errorf("%+v: %v", c, got)
		}
	}
	if !tolerates([]toleration{{Operator: "Exists"}}, "anything", "x", "NoSchedule") {
		t.Error("an empty key with Exists tolerates every taint")
	}
}

// The test cluster: four nodes that can take a 2-CPU, 8 GiB pod with different room, and one each that is not Ready,
// cordoned, outside the pool, tainted, or full.
const testNodes = `{"items":[
 {"metadata":{"name":"busy","labels":{"pool":"bench"}},"status":{"allocatable":{"cpu":"48","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"idle","labels":{"pool":"bench"}},"status":{"allocatable":{"cpu":"48","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"half","labels":{"pool":"bench"}},"status":{"allocatable":{"cpu":"47500m","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"tainted-ok","labels":{"pool":"bench"}},"spec":{"taints":[{"key":"dedicated","value":"bench","effect":"NoSchedule"},{"key":"note","effect":"PreferNoSchedule"}]},"status":{"allocatable":{"cpu":"48","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"down","labels":{"pool":"bench"}},"status":{"allocatable":{"cpu":"48","memory":"380Gi"},"conditions":[{"type":"Ready","status":"False"}]}},
 {"metadata":{"name":"cordoned","labels":{"pool":"bench"}},"spec":{"unschedulable":true},"status":{"allocatable":{"cpu":"48","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"other-pool","labels":{"pool":"web"}},"status":{"allocatable":{"cpu":"64","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"gpu","labels":{"pool":"bench"}},"spec":{"taints":[{"key":"gpu","effect":"NoExecute"}]},"status":{"allocatable":{"cpu":"64","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"full","labels":{"pool":"bench"}},"status":{"allocatable":{"cpu":"48","memory":"380Gi"},"conditions":[{"type":"Ready","status":"True"}]}},
 {"metadata":{"name":"no-memory","labels":{"pool":"bench"}},"status":{"allocatable":{"cpu":"48","memory":"6Gi"},"conditions":[{"type":"Ready","status":"True"}]}}
]}`

const testPods = `{"items":[
 {"spec":{"nodeName":"busy","containers":[{"resources":{"requests":{"cpu":"40"}}}]},"status":{"phase":"Running"}},
 {"spec":{"nodeName":"half","containers":[{"resources":{"requests":{"cpu":"20","memory":"10Gi"}}}]},"status":{"phase":"Running"}},
 {"spec":{"nodeName":"half","containers":[{"resources":{"requests":{"cpu":"40"}}}]},"status":{"phase":"Succeeded"}},
 {"spec":{"nodeName":"tainted-ok","containers":[{"resources":{"requests":{"cpu":"10"}}}]},"status":{"phase":"Pending"}},
 {"spec":{"nodeName":"full","containers":[{"resources":{"requests":{"cpu":"46500m"}}}]},"status":{"phase":"Running"}},
 {"spec":{"nodeName":"idle"},"status":{"phase":"Running"}},
 {"spec":{"containers":[{"resources":{"requests":{"cpu":"48"}}}]},"status":{"phase":"Pending"}}
]}`

func testRoomValues() site {
	return site{CPUs: 2, Memory: "8Gi", NodeSelector: map[string]string{"pool": "bench"}, Tolerations: []toleration{{Key: "dedicated", Operator: "Equal", Value: "bench", Effect: "NoSchedule"}}}
}

// Nodes rank by free CPU (allocatable minus the requests of the pods bound to them, finished pods excluded); nodes
// that cannot take the pod follow with the reason.
func TestRankNodes(t *testing.T) {
	var nodes struct{ Items []k8sNode }
	var pods struct{ Items []k8sPod }
	if err := jsonUnmarshal(testNodes, &nodes); err != nil {
		t.Fatal(err)
	}
	if err := jsonUnmarshal(testPods, &pods); err != nil {
		t.Fatal(err)
	}
	rooms, err := rankNodes(nodes.Items, pods.Items, testRoomValues())
	if err != nil {
		t.Fatal(err)
	}
	var order []string
	skip := map[string]string{}
	for _, r := range rooms {
		order = append(order, r.Name)
		skip[r.Name] = r.Skip
	}
	if want := []string{"idle", "tainted-ok", "half", "busy"}; !slices.Equal(order[:4], want) {
		t.Errorf("order %v, want %v first", order, want)
	}
	for name, why := range map[string]string{
		"down": "not Ready", "cordoned": "cordoned", "other-pool": "node selector", "gpu": "taint gpu:NoExecute",
		"full": "1.50 CPUs free, the pod needs 2", "no-memory": "6.0 GiB free, the pod needs 8Gi",
	} {
		if !strings.Contains(skip[name], why) {
			t.Errorf("%s skipped for %q, want %q", name, skip[name], why)
		}
	}
	for _, r := range rooms {
		if r.Name == "half" && (r.FreeCPU != 27.5 || r.Pods != 1 || r.FreeMem != 370<<30) {
			t.Errorf("half: %+v", r)
		}
	}
}

// routeKubectl answers kubectl calls by their leading arguments.
type routeKubectl struct {
	routes map[string]string
	calls  []string
}

func (k *routeKubectl) run(_ context.Context, _ []byte, args ...string) ([]byte, error) {
	key := strings.Join(args, " ")
	k.calls = append(k.calls, key)
	best := ""
	for prefix := range k.routes {
		if strings.HasPrefix(key, prefix) && len(prefix) > len(best) {
			best = prefix
		}
	}
	switch out := k.routes[best]; {
	case best == "":
		return nil, errors.New("unexpected kubectl call: " + key)
	case out == "forbidden":
		return nil, errors.New(`Error from server (Forbidden): User "u" cannot list the resource at the cluster scope`)
	case out == "unreachable":
		return nil, errors.New(`Unable to connect to the server: dial tcp: i/o timeout`)
	default:
		return []byte(out), nil
	}
}

func TestPickNodes(t *testing.T) {
	k := &routeKubectl{routes: map[string]string{"get nodes -o json": testNodes, "get pods --all-namespaces": testPods}}
	var progress bytes.Buffer
	picked, ranking, err := pickNodes(context.Background(), k, testRoomValues(), 3, nil, &progress)
	if err != nil || !slices.Equal(picked, []string{"idle", "tainted-ok", "half"}) || ranking.Basis != basisCluster || len(ranking.Nodes) != 10 {
		t.Fatalf("picked %v, %s, %v", picked, ranking.Basis, err)
	}
	if !slices.Contains(k.calls, "get pods --all-namespaces -o json --field-selector status.phase!=Succeeded,status.phase!=Failed") {
		t.Errorf("calls %v", k.calls)
	}
	if !strings.Contains(progress.String(), "* idle") || !strings.Contains(progress.String(), "cordoned") {
		t.Errorf("progress:\n%s", progress.String())
	}
	if _, _, err := pickNodes(context.Background(), k, testRoomValues(), 5, nil, &bytes.Buffer{}); err == nil || !strings.Contains(err.Error(), "4 nodes can take the pod, 5 wanted") {
		t.Errorf("too few nodes: %v", err)
	}
	// Candidates restrict the ranking to themselves.
	picked, ranking, err = pickNodes(context.Background(), k, testRoomValues(), 1, []string{"busy", "half", "cordoned"}, &bytes.Buffer{})
	if err != nil || !slices.Equal(picked, []string{"half"}) || len(ranking.Nodes) != 3 {
		t.Errorf("candidates: %v %+v %v", picked, ranking, err)
	}
	if _, _, err := pickNodes(context.Background(), k, testRoomValues(), 1, []string{"busy", "missing"}, &bytes.Buffer{}); err == nil || !strings.Contains(err.Error(), "the candidate list names missing, which is not a node of the cluster") {
		t.Errorf("unknown candidate: %v", err)
	}
}

// The session namespace's own pods, the only pods a namespace-scoped account can list.
const ownPods = `{"items":[
 {"spec":{"nodeName":"idle","containers":[{"resources":{"requests":{"cpu":"30"}}}]},"status":{"phase":"Running"}},
 {"spec":{"nodeName":"c1","containers":[{"resources":{"requests":{"cpu":"2"}}}]},"status":{"phase":"Running"}},
 {"spec":{"nodeName":"c2","containers":[{"resources":{"requests":{"cpu":"4"}}}]},"status":{"phase":"Succeeded"}}
]}`

// Without a cluster-wide pod list, the ranking falls back to the namespace's pods and says so.
func TestPickNodesWithoutClusterWidePods(t *testing.T) {
	v := testRoomValues()
	v.Namespace = "bench-ns"
	k := &routeKubectl{routes: map[string]string{"get nodes -o json": testNodes, "get pods --all-namespaces": "forbidden", "get pods -o json --field-selector status.phase!=Succeeded,status.phase!=Failed": ownPods}}
	var progress bytes.Buffer
	picked, ranking, err := pickNodes(context.Background(), k, v, 3, nil, &progress)
	// busy's 40 CPUs belong to another namespace and are invisible: it ranks with the idle nodes; idle's own 30 CPUs count.
	if err != nil || ranking.Basis != basisNamespace || !slices.Equal(picked, []string{"busy", "full", "tainted-ok"}) {
		t.Fatalf("picked %v, %s, %v", picked, ranking.Basis, err)
	}
	if !strings.Contains(progress.String(), "the ranking counts only the requests of namespace bench-ns, so free CPU is an upper bound") {
		t.Errorf("progress:\n%s", progress.String())
	}
	k.routes["get pods -o json --field-selector status.phase!=Succeeded,status.phase!=Failed"] = "forbidden"
	if _, _, err := pickNodes(context.Background(), k, v, 1, nil, &bytes.Buffer{}); err == nil || !strings.Contains(err.Error(), "picking a node needs list on pods, at least in the namespace") {
		t.Errorf("no pod list at all: %v", err)
	}
	// Only a Forbidden answer narrows the ranking: a failed cluster-wide list ends the pick instead of ranking a busy
	// node first under a warning that blames permissions.
	k.routes["get pods -o json --field-selector status.phase!=Succeeded,status.phase!=Failed"] = ownPods
	k.routes["get pods --all-namespaces"] = "unreachable"
	k.calls = nil
	if _, ranking, err := pickNodes(context.Background(), k, v, 1, nil, &bytes.Buffer{}); err == nil || !strings.Contains(err.Error(), "Unable to connect to the server") || ranking.Basis == basisNamespace || slices.ContainsFunc(k.calls, func(c string) bool { return strings.HasPrefix(c, "get pods -o json") }) {
		t.Errorf("unreachable cluster-wide pod list: %s, %v, calls %v", ranking.Basis, err, k.calls)
	}
}

// Without a node list, the ranking needs -nodes candidates and orders them by the namespace's own requests, then as
// given.
func TestPickNodesWithoutANodeList(t *testing.T) {
	v := testRoomValues()
	v.Namespace = "bench-ns"
	k := &routeKubectl{routes: map[string]string{"get nodes": "forbidden", "get pods --all-namespaces": "forbidden", "get pods -o json": ownPods}}
	var progress bytes.Buffer
	picked, ranking, err := pickNodes(context.Background(), k, v, 2, []string{"c1", "c2", "c3"}, &progress)
	if err != nil || ranking.Basis != basisCandidates || !slices.Equal(picked, []string{"c2", "c3"}) || ranking.Nodes[2].Name != "c1" || ranking.Nodes[2].Pods != 1 {
		t.Fatalf("picked %v, %+v, %v", picked, ranking, err)
	}
	if !strings.Contains(progress.String(), "nodes are not listable; ranking the candidate nodes") || !strings.Contains(progress.String(), "c1                                       allocatable unknown,   2.00 CPUs requested") {
		t.Errorf("progress:\n%s", progress.String())
	}
	if _, _, err := pickNodes(context.Background(), k, v, 1, nil, &bytes.Buffer{}); err == nil || !strings.Contains(err.Error(), "name the candidates with -nodes a,b,c") {
		t.Errorf("nothing to rank: %v", err)
	}
	// A node list that fails for another reason than permission ends the pick, candidates or not.
	k.routes["get nodes"] = "unreachable"
	if _, ranking, err := pickNodes(context.Background(), k, v, 1, []string{"c1", "c2"}, &bytes.Buffer{}); err == nil || !strings.Contains(err.Error(), "Unable to connect to the server") || ranking.Basis == basisCandidates {
		t.Errorf("unreachable node list: %s, %v", ranking.Basis, err)
	}
}
func jsonUnmarshal(text string, v any) error { return json.Unmarshal([]byte(text), v) }
