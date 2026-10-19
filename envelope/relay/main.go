// Command relay runs inside a network-less container: it listens on a loopback TCP port, forwards every connection to a unix socket (Buffon's mock endpoint, bind-mounted
// into the container) and runs the arm's command line as its child with the standard streams inherited, so a terminal stays a terminal. The relay exits with the child's
// status. Its own CPU time is written to -stats so Buffon can report it apart from the arm's. With -swarm it launches many agents instead of one (swarm.go).
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

// dialUnix connects to the mock's socket, trying again for a few seconds: a burst of connections (a swarm of agents sending a request each at the same moment) can fill the listener's backlog,
// and a full backlog refuses with EAGAIN; the agent would see a reset for a connection that a moment later is accepted.
func dialUnix(socket string) (net.Conn, error) {
	var err error
	for i := 0; i < 200; i++ {
		var c net.Conn
		if c, err = net.Dial("unix", socket); err == nil {
			return c, nil
		}
		time.Sleep(20 * time.Millisecond)
	}
	return nil, err
}

func forward(client net.Conn, socket string) {
	defer client.Close()
	upstream, err := dialUnix(socket)
	if err != nil {
		return
	}
	defer upstream.Close()
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		io.Copy(upstream, client)
		if u, ok := upstream.(*net.UnixConn); ok {
			u.CloseWrite()
		}
	}()
	go func() {
		defer wg.Done()
		io.Copy(client, upstream)
		if c, ok := client.(*net.TCPConn); ok {
			c.CloseWrite()
		}
	}()
	wg.Wait()
}

// monotonicNs is CLOCK_MONOTONIC in nanoseconds. A container has no time namespace by default, so this is the host's clock: the runner measures every interval of a sample from the instant the
// arm starts, taken here, not from the instant it asked the runtime to create the container.
func monotonicNs() int64 {
	var ts syscall.Timespec
	syscall.Syscall(syscall.SYS_CLOCK_GETTIME, 1, uintptr(unsafe.Pointer(&ts)), 0)
	return int64(ts.Sec)*1_000_000_000 + int64(ts.Nsec)
}

// startPoint is what the container had used when the relay started the arm: the cgroup's CPU (the runtime's setup, the init process, the relay's start and HOME seeding) and the
// relay's own CPU. The arm's CPU is the cgroup's usage after this point minus the relay's after it.
type startPoint struct {
	cgroupUsec int64
	relayMs    float64
	ok         bool
}

func selfCPUms() (float64, bool) {
	var ru syscall.Rusage
	if syscall.Getrusage(syscall.RUSAGE_SELF, &ru) != nil {
		return 0, false
	}
	ms := func(t syscall.Timeval) float64 { return float64(t.Sec)*1000 + float64(t.Usec)/1000 }
	return ms(ru.Utime) + ms(ru.Stime), true
}

func takeStartPoint() startPoint {
	stat, ok := readCgroup()["cpu.stat"].(map[string]int64)
	relay, rok := selfCPUms()
	if !ok || !rok {
		return startPoint{}
	}
	usage, ok := stat["usage_usec"]
	return startPoint{cgroupUsec: usage, relayMs: relay, ok: ok}
}

func writeStats(path string, endNs int64, start startPoint) {
	if path == "" {
		return
	}
	var ru syscall.Rusage
	if syscall.Getrusage(syscall.RUSAGE_SELF, &ru) != nil {
		return
	}
	ms := func(t syscall.Timeval) float64 { return float64(t.Sec)*1000 + float64(t.Usec)/1000 }
	doc := map[string]any{"user_ms": ms(ru.Utime), "system_ms": ms(ru.Stime), "child_end_ns": endNs}
	if start.ok {
		doc["start_cgroup_usage_usec"], doc["start_relay_cpu_ms"] = start.cgroupUsec, start.relayMs
	}
	// The container's own cgroup, read the instant the child has exited: it is gone once the container stops, so this is the only exact final reading.
	if cg := readCgroup(); len(cg) > 0 {
		doc["cgroup"] = cg
	}
	data, _ := json.Marshal(doc)
	os.WriteFile(path, data, 0o644)
}

// copyTree copies src into dst (which exists, as a tmpfs): directories, regular files (mode kept) and symlinks.
func copyTree(src, dst string) error {
	return filepath.WalkDir(src, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(src, path)
		target := filepath.Join(dst, rel)
		info, err := d.Info()
		if err != nil {
			return err
		}
		switch {
		case d.IsDir():
			return os.MkdirAll(target, info.Mode().Perm())
		case info.Mode()&os.ModeSymlink != 0:
			link, err := os.Readlink(path)
			if err != nil {
				return err
			}
			return os.Symlink(link, target)
		default:
			in, err := os.Open(path)
			if err != nil {
				return err
			}
			defer in.Close()
			out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, info.Mode().Perm())
			if err != nil {
				return err
			}
			if _, err := io.Copy(out, in); err != nil {
				out.Close()
				return err
			}
			return out.Close()
		}
	})
}

func readCgroup() map[string]any {
	out := map[string]any{}
	if text, err := os.ReadFile("/sys/fs/cgroup/cpu.stat"); err == nil {
		stat := map[string]int64{}
		for _, line := range strings.Split(string(text), "\n") {
			if k, v, ok := strings.Cut(line, " "); ok {
				if n, err := strconv.ParseInt(strings.TrimSpace(v), 10, 64); err == nil {
					stat[k] = n
				}
			}
		}
		out["cpu.stat"] = stat
	}
	for _, name := range []string{"memory.peak", "memory.current", "pids.peak", "pids.current"} {
		if text, err := os.ReadFile("/sys/fs/cgroup/" + name); err == nil {
			if n, err := strconv.ParseInt(strings.TrimSpace(string(text)), 10, 64); err == nil {
				out[name] = n
			}
		}
	}
	return out
}

func main() {
	listen := flag.String("listen", "127.0.0.1:0", "loopback address the arm connects to")
	socket := flag.String("unix", "", "unix socket of the mock endpoint")
	stats := flag.String("stats", "", "file to write the relay's own CPU time to")
	seed := flag.String("seed", "", "directory copied into -home before the command starts (the arm's first-start state)")
	home := flag.String("home", "", "the tmpfs HOME the seed is copied into")
	swarmMode := flag.Bool("swarm", false, "launch many agents from commands on standard input (swarm.go): the container of a swarm sample; no command follows `--`")
	exportAddr := flag.Bool("export-addr", false, "tell the child the bound address in BUFFON_RELAY_ADDR (for a caller that asked for port 0; never set for an arm)")
	flag.Parse()
	args := flag.Args()
	if *swarmMode && *socket != "" && len(args) == 0 {
		runSwarm(*listen, *socket)
		os.Exit(0)
	}
	if *socket == "" || len(args) == 0 {
		fmt.Fprintln(os.Stderr, "usage: relay -listen 127.0.0.1:PORT -unix SOCKET [-stats FILE] -- command [args...]")
		os.Exit(2)
	}
	if *seed != "" && *home != "" {
		if err := copyTree(*seed, *home); err != nil {
			fmt.Fprintln(os.Stderr, "relay: seeding HOME:", err)
			os.Exit(126)
		}
	}
	ln, err := net.Listen("tcp", *listen)
	if err != nil {
		fmt.Fprintln(os.Stderr, "relay: listen:", err)
		os.Exit(2)
	}
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go forward(c, *socket)
		}
	}()
	cmd := exec.Command(args[0], args[1:]...)
	if *exportAddr { // the address actually bound: a caller that asked for port 0 learns it here, never by probing for a free port first. Off for an arm: it must see the environment an uncontained arm sees.
		cmd.Env = append(os.Environ(), "BUFFON_RELAY_ADDR="+ln.Addr().String())
	} else {
		cmd.Env = os.Environ()
	}
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
	start := takeStartPoint()
	startNs := monotonicNs()
	if *stats != "" {
		// written before the child starts, so a reader sees the start while the arm is still running; the whole file is replaced at once
		tmp := *stats + ".start.tmp"
		if os.WriteFile(tmp, []byte(strconv.FormatInt(startNs, 10)), 0o644) == nil {
			os.Rename(tmp, *stats+".start")
		}
	}
	if err := cmd.Start(); err != nil {
		fmt.Fprintln(os.Stderr, "relay: start:", err)
		os.Exit(127)
	}
	sigs := make(chan os.Signal, 8)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP, syscall.SIGQUIT, syscall.SIGWINCH)
	go func() {
		for s := range sigs {
			cmd.Process.Signal(s)
		}
	}()
	err = cmd.Wait()
	endNs := monotonicNs()
	ln.Close()
	writeStats(*stats, endNs, start)
	if err == nil {
		os.Exit(0)
	}
	if ee, ok := err.(*exec.ExitError); ok {
		if ws, ok := ee.Sys().(syscall.WaitStatus); ok && ws.Signaled() {
			os.Exit(128 + int(ws.Signal()))
		}
		os.Exit(ee.ExitCode())
	}
	os.Exit(1)
}
