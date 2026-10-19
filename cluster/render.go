// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

package main

import (
	"bytes"
	_ "embed"
	"fmt"
	"maps"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"text/template"
)

//go:embed templates/job.yaml
var jobTemplate string

// session is what one pod runs: one whole buffon session (every arm, A/A copy and round, interleaved by Buffon's
// own runner) as one process on pinned cores. The Python backend writes it; the Job carries it as BUFFON_SESSION.
type session struct {
	// Run names the Job and the run directory; a DNS label.
	Run string `json:"run"`
	// Argv is the session command. {root} is Buffon install root, {out} the directory the session writes its run
	// directory to, {cpus} the pinned CPU list (empty when unpinned). argv[0] is looked up in {root}/bin, then PATH.
	Argv []string `json:"argv"`
	// Env is non-secret only; secrets come from the site's secretEnv references.
	Env map[string]string `json:"env,omitempty"`
	// CPUs is how many cores the session is pinned to with taskset; Pin is auto (exclusive cores when the pod has
	// them, else the quietest of the allowed cores), none, or an explicit list such as 4,5.
	CPUs           int    `json:"cpus"`
	Pin            string `json:"pin"`
	TimeoutSeconds int    `json:"timeoutSeconds"`
	// AllowFrequencyScaling runs on cores whose clock scales with load; the session is then reported, never judged.
	AllowFrequencyScaling bool `json:"allowFrequencyScaling,omitempty"`
}

var (
	sha256Hex = regexp.MustCompile(`^[0-9a-f]{64}$`)
	pinList   = regexp.MustCompile(`^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$`)
	// reservedEnv are set by the Job or the pod session itself.
	reservedEnv = []string{"BUFFON_SESSION", "BUFFON_ROOT", "BUFFON_OUT", "BUFFON_PINNED_CPUS", "NODE_NAME", "POD_NAME", "HOME", "TMPDIR", "PATH", "GOMAXPROCS"}
)

func (s *session) validate() error {
	var problems []string
	add := func(format string, args ...any) { problems = append(problems, fmt.Sprintf(format, args...)) }
	if !dnsLabel.MatchString(s.Run) || len(s.Run) > 52 {
		add("run %q is not a DNS label of at most 52 characters (the Job's pods add a suffix)", s.Run)
	}
	if len(s.Argv) == 0 || s.Argv[0] == "" {
		add("argv is empty")
	} else if !slices.ContainsFunc(s.Argv, func(a string) bool { return strings.Contains(a, "{out}") }) {
		add("argv never names {out}: the session's run directory would not come back")
	}
	for k := range s.Env {
		if !envName.MatchString(k) {
			add("env %q is not an environment variable name", k)
		}
		if slices.Contains(reservedEnv, k) {
			add("env %s is set by the pod", k)
		}
	}
	if s.CPUs < 1 {
		add("cpus must be at least 1")
	}
	if s.Pin != "auto" && s.Pin != "none" {
		if !pinList.MatchString(s.Pin) {
			add("pin %q is not auto, none or a CPU list", s.Pin)
		} else if cpus, err := parseCPUList(s.Pin); err != nil {
			add("pin %q: %v", s.Pin, err)
		} else if s.CPUs >= 1 && len(cpus) > s.CPUs {
			// More cores than the pod's CPU limit would only be throttled by its quota. The runner refuses it before a pod exists.
			add("pin list %s names %d CPUs, the pod has %d", s.Pin, len(cpus), s.CPUs)
		}
	}
	if s.TimeoutSeconds < 1 {
		add("timeoutSeconds must be positive")
	}
	if len(problems) > 0 {
		return fmt.Errorf("session: %s", strings.Join(problems, "; "))
	}
	return nil
}

type envVar struct{ Name, Value string }

type jobData struct {
	Name, Namespace, Image, CPU, Memory, ScratchSize, Node, PVC, ServiceAccountName string
	Command                                                                         []string
	Env                                                                             []envVar
	SecretEnv                                                                       []secretEnv
	Bundle                                                                          bool
	Labels, NodeSelector                                                            map[string]string
	Tolerations                                                                     []toleration
	ImagePullSecrets                                                                []map[string]string
	Session                                                                         string
	DeadlineSeconds, TTLSeconds                                                     int
}

// bundleRef is what the Job carries about a bundle: the packed file's sha256, which the pod checks the copy against,
// and its architecture, which the pod checks the node against.
type bundleRef struct{ sha256, arch string }

const (
	bundleDir = "/bundle"
	imageRoot = "/opt/buffon"
)

// renderJob renders the Job that runs one session on node (empty: the site's node, if any). Every cluster-specific
// value comes from the site; b describes the bundle in bundle mode.
func renderJob(st site, se *session, node string, b bundleRef) ([]byte, error) {
	if err := se.validate(); err != nil {
		return nil, err
	}
	if se.CPUs != st.CPUs {
		return nil, fmt.Errorf("the session pins %d cores but the pod requests %d CPUs", se.CPUs, st.CPUs)
	}
	encoded, err := marshalPlain(se)
	if err != nil {
		return nil, err
	}
	if node == "" {
		node = st.Node
	}
	name := se.Run
	data := jobData{
		Name:               name,
		Namespace:          st.Namespace,
		Image:              st.podImage(),
		CPU:                strconv.Itoa(st.CPUs),
		Memory:             st.Memory,
		ScratchSize:        st.ScratchSize,
		Node:               node,
		PVC:                st.PVC,
		ServiceAccountName: st.ServiceAccountName,
		Labels:             map[string]string{"app.kubernetes.io/name": "buffon", "app.kubernetes.io/managed-by": "buffon-cluster", "buffon/run": name},
		NodeSelector:       st.NodeSelector,
		Tolerations:        st.Tolerations,
		Session:            string(encoded),
		DeadlineSeconds:    st.DeadlineSeconds,
		TTLSeconds:         st.TTLSeconds,
	}
	data.Env = []envVar{{"BUFFON_DELIVERY", st.delivery()}, {"BUFFON_IMAGE_REF", st.podImage()}}
	if st.delivery() == deliveryBundle {
		if !sha256Hex.MatchString(b.sha256) || (b.arch != "amd64" && b.arch != "arm64") {
			return nil, fmt.Errorf("bundle mode needs the bundle's sha256 and architecture, got %q and %q", b.sha256, b.arch)
		}
		data.Bundle = true
		data.Command = []string{"sh", "-c", podBundleScript}
		data.Env = append(data.Env,
			envVar{"BUFFON_BUNDLE_SHA256", b.sha256},
			envVar{"BUFFON_BUNDLE_ARCH", b.arch},
			envVar{"BUFFON_ROOT", bundleDir + "/buffon"},
			envVar{"PATH", bundleDir + "/buffon/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
		)
	} else {
		data.Command = []string{imageRoot + "/bin/buffon-cluster", "pod"}
		data.Env = append(data.Env, envVar{"BUFFON_ROOT", imageRoot})
	}
	data.SecretEnv = st.SecretEnv
	for _, s := range slices.Sorted(slices.Values(st.ImagePullSecrets)) {
		data.ImagePullSecrets = append(data.ImagePullSecrets, map[string]string{"name": s})
	}
	tmpl, err := template.New("job.yaml").Option("missingkey=error").Funcs(template.FuncMap{
		"json": func(value any) (string, error) {
			b, err := marshalPlain(value)
			return string(b), err
		},
	}).Parse(jobTemplate)
	if err != nil {
		return nil, err
	}
	var out bytes.Buffer
	if err := tmpl.Execute(&out, data); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}

// sessionEnv returns the session's own environment in a stable order.
func sessionEnv(se *session) []string {
	var out []string
	for _, k := range slices.Sorted(maps.Keys(se.Env)) {
		out = append(out, k+"="+se.Env[k])
	}
	return out
}

// podBundleScript runs in the base image: it checks that the node has the bundle's architecture, waits for the
// runner's copy, checks the bundle's sha256 against the one in the Job, unpacks it, checks every artifact against
// ARTIFACTS.sha256, and starts the pod session. A failure prints an error line, which the runner reports.
const podBundleScript = `set -eu
b=${BUFFON_BUNDLE_DIR:-/bundle}
fail() { printf '{"t":"error","message":"%s"}\n' "$1"; exit 1; }
case "$(uname -m)" in x86_64) arch=amd64 ;; aarch64 | arm64) arch=arm64 ;; *) arch=$(uname -m) ;; esac
[ "$arch" = "$BUFFON_BUNDLE_ARCH" ] || fail "the bundle is linux/$BUFFON_BUNDLE_ARCH but the node is linux/$arch"
wait=${BUFFON_DELIVERY_TIMEOUT:-1800}
end=$(( $(date +%s) + wait ))
while [ ! -f "$b/READY" ]; do
	[ "$(date +%s)" -lt "$end" ] || fail "no bundle arrived within $wait s"
	sleep 1
done
echo "$BUFFON_BUNDLE_SHA256  $b/bundle.tar.gz" | sha256sum -c --status - || fail "bundle.tar.gz does not have the sha256 $BUFFON_BUNDLE_SHA256 the runner sent"
mkdir -p "$b/buffon"
tar -xzf "$b/bundle.tar.gz" -C "$b/buffon" --no-same-owner || fail "bundle.tar.gz does not unpack"
rm -f "$b/bundle.tar.gz"
(cd "$b/buffon" && sha256sum -c --status --strict ARTIFACTS.sha256) || fail "an artifact does not match ARTIFACTS.sha256"
exec "$b/buffon/bin/buffon-cluster" pod
`
