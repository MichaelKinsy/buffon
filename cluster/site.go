// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// site is everything cluster-specific: a site profile file (cluster/site.example.json lists every field; keep the
// real one in the gitignored cluster/site.local.json), then BUFFON_K8S_* environment variables, then flags. Nothing
// cluster-specific has a default, and no code, test or document names a real cluster, namespace or host.
type site struct {
	Kubeconfig  string `json:"kubeconfig,omitempty"`
	KubeContext string `json:"kubeContext,omitempty"`
	Namespace   string `json:"namespace,omitempty"`
	// Image is an image holding Buffon at /opt/buffon, pinned by digest. Bundle, instead, names a local bundle
	// directory that the runner copies into a BaseImage pod, so no registry is needed.
	Image     string `json:"image,omitempty"`
	Bundle    string `json:"bundle,omitempty"`
	BaseImage string `json:"baseImage,omitempty"`
	// AllowUnpinnedImage accepts an image without a @sha256: digest; results then do not identify what they ran on.
	AllowUnpinnedImage bool              `json:"allowUnpinnedImage,omitempty"`
	CPUs               int               `json:"cpus,omitempty"`
	Memory             string            `json:"memory,omitempty"`
	ScratchSize        string            `json:"scratchSize,omitempty"`
	NodeSelector       map[string]string `json:"nodeSelector,omitempty"`
	Tolerations        []toleration      `json:"tolerations,omitempty"`
	// Node pins the pod to one node by name (a required node affinity on metadata.name, so the scheduler still
	// checks taints and resources).
	Node               string   `json:"node,omitempty"`
	PVC                string   `json:"pvc,omitempty"`
	ImagePullSecrets   []string `json:"imagePullSecrets,omitempty"`
	ServiceAccountName string   `json:"serviceAccountName,omitempty"`
	DeadlineSeconds    int      `json:"deadlineSeconds,omitempty"`
	TTLSeconds         int      `json:"ttlSecondsAfterFinished,omitempty"`
	// MaxCV is the calibration gate: a metric whose coefficient of variation exceeds it refuses a comparison.
	MaxCV float64 `json:"maxCv,omitempty"`
	// AllowFrequencyScaling runs on cores whose clock scales with load. Such a session is reported, never judged.
	AllowFrequencyScaling bool `json:"allowFrequencyScaling,omitempty"`
	// SecretEnv names environment variables the pod reads from Kubernetes Secrets. A secret value never passes
	// through the site profile, the session or the runner: only the reference does.
	SecretEnv []secretEnv `json:"secretEnv,omitempty"`
}

// secretEnv is one environment variable taken from a key of a Secret in the session namespace.
type secretEnv struct {
	Name   string `json:"name"`
	Secret string `json:"secret"`
	Key    string `json:"key"`
}

type toleration struct {
	Key               string `json:"key,omitempty"`
	Operator          string `json:"operator,omitempty"`
	Value             string `json:"value,omitempty"`
	Effect            string `json:"effect,omitempty"`
	TolerationSeconds *int64 `json:"tolerationSeconds,omitempty"`
}

// Delivery: how the pod gets the buffon.
const (
	deliveryImage  = "image"
	deliveryBundle = "bundle"
)

func defaultSite() site {
	return site{CPUs: 2, Memory: "8Gi", ScratchSize: "8Gi", DeadlineSeconds: 6 * 3600, TTLSeconds: 7 * 24 * 3600, MaxCV: 0.05}
}

func loadSiteFile(path string, s *site) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(s); err != nil {
		return fmt.Errorf("site profile %s: %w", path, err)
	}
	return nil
}

// applyEnv overrides the site from BUFFON_K8S_* variables. KUBECONFIG is read by kubectl itself.
func applyEnv(s *site, getenv func(string) string) error {
	for name, dst := range map[string]*string{
		"BUFFON_K8S_NAMESPACE":  &s.Namespace,
		"BUFFON_K8S_CONTEXT":    &s.KubeContext,
		"BUFFON_K8S_IMAGE":      &s.Image,
		"BUFFON_K8S_BUNDLE":     &s.Bundle,
		"BUFFON_K8S_BASE_IMAGE": &s.BaseImage,
		"BUFFON_K8S_NODE":       &s.Node,
		"BUFFON_K8S_PVC":        &s.PVC,
		"BUFFON_K8S_MEMORY":     &s.Memory,
	} {
		if v := getenv(name); v != "" {
			*dst = v
		}
	}
	if v := getenv("BUFFON_K8S_CPUS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return fmt.Errorf("BUFFON_K8S_CPUS=%q: %w", v, err)
		}
		s.CPUs = n
	}
	return nil
}

var (
	dnsLabel     = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$`)
	dnsSubdomain = regexp.MustCompile(`^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$`)
	quantity     = regexp.MustCompile(`^[0-9]+(\.[0-9]+)?(Ki|Mi|Gi|Ti|k|M|G|T)?$`)
	labelKey     = regexp.MustCompile(`^([a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?/)?[A-Za-z0-9]([-A-Za-z0-9_.]{0,61}[A-Za-z0-9])?$`)
	labelValue   = regexp.MustCompile(`^([A-Za-z0-9]([-A-Za-z0-9_.]{0,61}[A-Za-z0-9])?)?$`)
	imageDigest  = regexp.MustCompile(`@sha256:[0-9a-f]{64}$`)
	placeholder  = regexp.MustCompile(`<[^>]*>`)
	envName      = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
	secretKey    = regexp.MustCompile(`^[-._a-zA-Z0-9]+$`)
)

func (s *site) validate() error {
	var problems []string
	add := func(format string, args ...any) { problems = append(problems, fmt.Sprintf(format, args...)) }
	for name, v := range map[string]string{"namespace": s.Namespace, "image": s.Image, "bundle": s.Bundle, "baseImage": s.BaseImage, "node": s.Node, "pvc": s.PVC, "kubeContext": s.KubeContext} {
		if placeholder.MatchString(v) {
			add("%s %q still holds a placeholder from site.example.json", name, v)
		}
	}
	if s.Namespace == "" {
		add("namespace is not set (site profile, BUFFON_K8S_NAMESPACE or -namespace)")
	} else if !dnsLabel.MatchString(s.Namespace) {
		add("namespace %q is not a DNS label", s.Namespace)
	}
	switch {
	case s.Image != "" && s.Bundle != "":
		add("both image (%s) and bundle (%s) are set; a session runs one of them", s.Image, s.Bundle)
	case s.Image == "" && s.Bundle == "":
		add("neither image nor bundle is set")
	case s.Bundle != "" && s.BaseImage == "":
		add("bundle mode needs a baseImage with python3 and coreutils, pinned by digest")
	case s.Image != "" && !s.AllowUnpinnedImage && !imageDigest.MatchString(s.Image):
		add("image %q is not pinned by digest (name@sha256:...)", s.Image)
	case s.Bundle != "" && !s.AllowUnpinnedImage && !imageDigest.MatchString(s.BaseImage):
		add("baseImage %q is not pinned by digest (name@sha256:...)", s.BaseImage)
	}
	if s.CPUs < 1 {
		add("cpus must be a whole number of at least 1 (Guaranteed QoS needs an integer CPU request for exclusive cores)")
	}
	if !quantity.MatchString(s.Memory) {
		add("memory %q is not a Kubernetes quantity", s.Memory)
	}
	if !quantity.MatchString(s.ScratchSize) {
		add("scratchSize %q is not a Kubernetes quantity", s.ScratchSize)
	}
	if s.Node != "" && !dnsSubdomain.MatchString(s.Node) {
		add("node %q is not a node name", s.Node)
	}
	if s.PVC != "" && !dnsSubdomain.MatchString(s.PVC) {
		add("pvc %q is not a claim name", s.PVC)
	}
	if s.ServiceAccountName != "" && !dnsSubdomain.MatchString(s.ServiceAccountName) {
		add("serviceAccountName %q is not a valid name", s.ServiceAccountName)
	}
	for _, v := range s.ImagePullSecrets {
		if !dnsSubdomain.MatchString(v) {
			add("imagePullSecrets entry %q is not a secret name", v)
		}
	}
	for k, v := range s.NodeSelector {
		if !labelKey.MatchString(k) || !labelValue.MatchString(v) {
			add("nodeSelector %q: %q is not a label selector", k, v)
		}
	}
	for _, t := range s.Tolerations {
		switch t.Operator {
		case "", "Equal", "Exists":
		default:
			add("toleration operator %q is not Equal or Exists", t.Operator)
		}
		switch t.Effect {
		case "", "NoSchedule", "PreferNoSchedule", "NoExecute":
		default:
			add("toleration effect %q is not NoSchedule, PreferNoSchedule or NoExecute", t.Effect)
		}
	}
	if s.DeadlineSeconds < 60 {
		add("deadlineSeconds must be at least 60")
	}
	if s.TTLSeconds < 0 {
		add("ttlSecondsAfterFinished must not be negative")
	}
	for _, e := range s.SecretEnv {
		if !envName.MatchString(e.Name) || !dnsSubdomain.MatchString(e.Secret) || !secretKey.MatchString(e.Key) {
			add("secretEnv %q from %q key %q: want an environment variable name, a Secret name and a key", e.Name, e.Secret, e.Key)
		}
	}
	if !(s.MaxCV > 0 && s.MaxCV < 1) {
		add("maxCv %v: want a coefficient of variation such as 0.05", s.MaxCV)
	}
	if len(problems) > 0 {
		return errors.New(strings.Join(problems, "\n  "))
	}
	return nil
}

func (s *site) delivery() string {
	if s.Bundle != "" {
		return deliveryBundle
	}
	return deliveryImage
}

// podImage is the image the pod runs: Buffon image, or in bundle mode the base image.
func (s *site) podImage() string {
	if s.Bundle != "" {
		return s.BaseImage
	}
	return s.Image
}

// siteFlags registers the flags that override the site and returns a function that applies those the user set.
func siteFlags(fs *flag.FlagSet) func(*site) error {
	kubeconfig := fs.String("kubeconfig", "", "kubeconfig file (default: kubectl's own, $KUBECONFIG)")
	kubeContext := fs.String("context", "", "kubectl context ($BUFFON_K8S_CONTEXT)")
	namespace := fs.String("namespace", "", "namespace for the Job ($BUFFON_K8S_NAMESPACE)")
	image := fs.String("image", "", "Buffon image, pinned by digest ($BUFFON_K8S_IMAGE)")
	bundle := fs.String("bundle", "", "bundle directory copied into a base-image pod ($BUFFON_K8S_BUNDLE)")
	cpus := fs.Int("cpus", 0, "whole CPUs the pod requests and is limited to, and the cores the session pins to")
	memory := fs.String("memory", "", "memory request and limit")
	node := fs.String("node", "", "pin the pod to this node by name ($BUFFON_K8S_NODE)")
	return func(s *site) error {
		fs.Visit(func(f *flag.Flag) {
			switch f.Name {
			case "kubeconfig":
				s.Kubeconfig = *kubeconfig
			case "context":
				s.KubeContext = *kubeContext
			case "namespace":
				s.Namespace = *namespace
			case "image":
				s.Image = *image
			case "bundle":
				s.Bundle = *bundle
			case "cpus":
				s.CPUs = *cpus
			case "memory":
				s.Memory = *memory
			case "node":
				s.Node = *node
			}
		})
		return nil
	}
}

// loadSite layers the defaults, the site profile, the environment and the flags, and validates the result.
func loadSite(path string, applyFlags func(*site) error, getenv func(string) string) (site, error) {
	s := defaultSite()
	if path == "" {
		path = getenv("BUFFON_K8S_SITE")
	}
	if path != "" {
		if err := loadSiteFile(path, &s); err != nil {
			return s, err
		}
	}
	if err := applyEnv(&s, getenv); err != nil {
		return s, err
	}
	if err := applyFlags(&s); err != nil {
		return s, err
	}
	s.Kubeconfig = expandPath(s.Kubeconfig, getenv)
	return s, s.validate()
}

// expandPath expands $VAR and a leading ~ the way the Python runner does for a site's paths (os.path.expandvars, then
// os.path.expanduser): kubectl gets a path its own process can open, however the profile spelled it. Only the current
// user's ~ is expanded; ~name is left alone. The file itself is never read here.
func expandPath(p string, getenv func(string) string) string {
	if p == "" {
		return p
	}
	p = os.Expand(p, getenv)
	if p == "~" || strings.HasPrefix(p, "~/") {
		if home := getenv("HOME"); home != "" {
			return filepath.Join(home, strings.TrimPrefix(p, "~"))
		}
		if home, err := os.UserHomeDir(); err == nil {
			return filepath.Join(home, strings.TrimPrefix(p, "~"))
		}
	}
	return p
}
