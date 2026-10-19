// SPDX-License-Identifier: MIT

package main

import (
	"encoding/binary"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// scriptBundle packs a bundle whose bin/buffon-cluster is a shell script that reports it started, with ARTIFACTS.sha256
// over it and buffon.py; tamper changes buffon.py after the list is written.
func scriptBundle(t *testing.T, tamper bool) (archive, sum string) {
	t.Helper()
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "bin"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, bundleProgram), []byte("#!/bin/sh\necho \"started $*\"\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "buffon.py"), []byte("print()\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	writeArtifacts(t, dir, bundleProgram, "buffon.py")
	if tamper {
		if err := os.WriteFile(filepath.Join(dir, "buffon.py"), []byte("changed\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	archive, sum, err := packBundle(dir, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	return archive, sum
}

// runBundleScript runs the pod's bundle script under sh with the bundle already copied in and returns its stdout.
func runBundleScript(t *testing.T, archive, sum, arch string) string {
	t.Helper()
	b := t.TempDir()
	data, err := os.ReadFile(archive)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(b, "bundle.tar.gz"), data, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(b, "READY"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command("sh", "-c", podBundleScript)
	cmd.Env = append(os.Environ(), "BUFFON_BUNDLE_DIR="+b, "BUFFON_BUNDLE_ARCH="+arch, "BUFFON_BUNDLE_SHA256="+sum, "BUFFON_DELIVERY_TIMEOUT=5")
	// The pod's lines go to stdout; tar's warnings (such as a timestamp a moment in the future) go to stderr.
	out, _ := cmd.Output()
	return string(out)
}

// The pod starts buffon-cluster only from a bundle with the sha256 the runner sent, on a node of the bundle's
// architecture, and with every artifact matching ARTIFACTS.sha256.
func TestPodBundleScriptChecksTheBundleBeforeItStarts(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("the bundle script runs in a Linux pod")
	}
	for _, tool := range []string{"sh", "sha256sum", "tar", "uname"} {
		if _, err := exec.LookPath(tool); err != nil {
			t.Skipf("the bundle script needs %s", tool)
		}
	}
	other := map[string]string{"amd64": "arm64", "arm64": "amd64"}[runtime.GOARCH]
	archive, sum := scriptBundle(t, false)
	if out := runBundleScript(t, archive, sum, runtime.GOARCH); strings.TrimSpace(out) != "started pod" {
		t.Errorf("a good bundle: %q", out)
	}
	if out := runBundleScript(t, archive, strings.Repeat("0", 64), runtime.GOARCH); !strings.Contains(out, `"t":"error"`) || !strings.Contains(out, "does not have the sha256") || strings.Contains(out, "started") {
		t.Errorf("a bundle with another sha256: %q", out)
	}
	if out := runBundleScript(t, archive, sum, other); !strings.Contains(out, "but the node is linux/"+runtime.GOARCH) || strings.Contains(out, "started") {
		t.Errorf("a bundle for linux/%s: %q", other, out)
	}
	tampered, tsum := scriptBundle(t, true)
	if out := runBundleScript(t, tampered, tsum, runtime.GOARCH); !strings.Contains(out, "does not match ARTIFACTS.sha256") || strings.Contains(out, "started") {
		t.Errorf("a bundle with a changed artifact: %q", out)
	}
}

// writeELFHeader writes the 64-byte header of a little-endian ELF64 executable for machine; debug/elf reads it as a
// file with no sections.
func writeELFHeader(t *testing.T, path string, machine uint16) {
	t.Helper()
	h := make([]byte, 64)
	copy(h, "\x7fELF")
	h[4], h[5], h[6] = 2, 1, 1               // ELFCLASS64, little-endian, EV_CURRENT
	binary.LittleEndian.PutUint16(h[16:], 2) // ET_EXEC
	binary.LittleEndian.PutUint16(h[18:], machine)
	binary.LittleEndian.PutUint32(h[20:], 1)
	binary.LittleEndian.PutUint16(h[52:], 64) // e_ehsize
	if err := os.WriteFile(path, h, 0o755); err != nil {
		t.Fatal(err)
	}
}

// A bundle runs on one architecture: an ELF program of another one beside buffon-cluster is refused.
func TestInspectBundleRefusesMixedArchitectures(t *testing.T) {
	dir := testBundle(t)
	machine := map[string]uint16{"amd64": 183, "arm64": 62}[runtime.GOARCH] // EM_AARCH64, EM_X86_64
	writeELFHeader(t, filepath.Join(dir, "bin", "helper"), machine)
	if a, ok := elfArch(filepath.Join(dir, "bin", "helper")); !ok || a == runtime.GOARCH {
		t.Fatalf("the helper reads as %q %t", a, ok)
	}
	writeArtifacts(t, dir, bundleProgram, "buffon.py", "bin/helper")
	if _, err := inspectBundle(dir); err == nil || !strings.Contains(err.Error(), "mixes architectures") {
		t.Errorf("mixed bundle: %v", err)
	}
}
