// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

package main

import (
	"archive/tar"
	"bufio"
	"compress/gzip"
	"crypto/sha256"
	"debug/elf"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// bundleProgram is the program a bundle must carry: the pod session itself.
const bundleProgram = "bin/buffon-cluster"

// inspectBundle checks a bundle directory before it is sent: ARTIFACTS.sha256 lists bin/buffon-cluster, every listed
// file has its sha256, and every listed ELF program has the bundle's one architecture.
func inspectBundle(dir string) (arch string, err error) {
	f, err := os.Open(filepath.Join(dir, "ARTIFACTS.sha256"))
	if err != nil {
		return "", fmt.Errorf("bundle %s: %w", dir, err)
	}
	defer func() { _ = f.Close() }()
	listed := false
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		sum, rel, ok := strings.Cut(sc.Text(), "  ")
		if !ok || !sha256Hex.MatchString(sum) || !filepath.IsLocal(rel) {
			return "", fmt.Errorf("bundle %s: ARTIFACTS.sha256 line %q is not \"<sha256>  <relative path>\"", dir, sc.Text())
		}
		path := filepath.Join(dir, rel)
		got, err := fileSHA256(path)
		if err != nil {
			return "", fmt.Errorf("bundle %s: %w", dir, err)
		}
		if got != sum {
			return "", fmt.Errorf("bundle %s: %s has sha256 %s, ARTIFACTS.sha256 says %s", dir, rel, got, sum)
		}
		listed = listed || rel == bundleProgram
		if a, ok := elfArch(path); ok {
			if arch != "" && a != arch {
				return "", fmt.Errorf("bundle %s mixes architectures: %s is linux/%s, another program linux/%s", dir, rel, a, arch)
			}
			arch = a
		}
	}
	if err := sc.Err(); err != nil {
		return "", err
	}
	if !listed {
		return "", fmt.Errorf("bundle %s: ARTIFACTS.sha256 does not list %s", dir, bundleProgram)
	}
	if arch == "" {
		return "", fmt.Errorf("bundle %s: %s is not a Linux ELF program", dir, bundleProgram)
	}
	return arch, nil
}

func fileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer func() { _ = f.Close() }()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// elfArch reports the architecture of a Linux ELF executable.
func elfArch(path string) (string, bool) {
	f, err := elf.Open(path)
	if err != nil {
		return "", false
	}
	defer func() { _ = f.Close() }()
	switch f.Machine {
	case elf.EM_X86_64:
		return "amd64", true
	case elf.EM_AARCH64:
		return "arm64", true
	}
	return "", false
}

// packBundle writes the bundle directory as a gzip tar into tmp and returns the archive path and its sha256.
func packBundle(dir, tmp string) (string, string, error) {
	archive := filepath.Join(tmp, "bundle.tar.gz")
	f, err := os.Create(archive)
	if err != nil {
		return "", "", err
	}
	h := sha256.New()
	gz := gzip.NewWriter(io.MultiWriter(f, h))
	tw := tar.NewWriter(gz)
	walkErr := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(dir, path)
		if err != nil || rel == "." {
			return err
		}
		if !info.Mode().IsRegular() && !info.IsDir() && info.Mode()&os.ModeSymlink == 0 {
			return nil
		}
		link := ""
		if info.Mode()&os.ModeSymlink != 0 {
			if link, err = os.Readlink(path); err != nil {
				return err
			}
		}
		hdr, err := tar.FileInfoHeader(info, link)
		if err != nil {
			return err
		}
		hdr.Name = filepath.ToSlash(rel)
		hdr.Uid, hdr.Gid, hdr.Uname, hdr.Gname = 0, 0, "", ""
		if err := tw.WriteHeader(hdr); err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
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
		return "", "", err
	}
	return archive, hex.EncodeToString(h.Sum(nil)), nil
}
