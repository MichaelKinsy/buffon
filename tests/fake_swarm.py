# SPDX-License-Identifier: Apache-2.0
"""A fake container runtime for the swarm tests: `docker run -i` is a thread that speaks the relay's JSON-lines protocol (envelope/relay/swarm.go) with scripted agents, and the container's cgroup is a
temporary directory of counter files. No process is started, no container exists."""
import json
import os
import tempfile
import threading
import time

from buffon.mock import REPLY

DIGEST = "debian@sha256:" + "7c7b2c96" * 8


class FakeProc:
    def __init__(self, stdin, stdout):
        self.stdin, self.stdout, self.returncode = stdin, stdout, None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.returncode = -9


class Done:
    """What `docker rm -f` returns."""
    returncode = 0

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


class FakeCgroup:
    """The counter files of the container's cgroup, in a directory."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="fake-cg-")
        self.lock = threading.Lock()
        self.set(memory_current=3 * 1048576, memory_peak=4 * 1048576, usage_usec=10_000, throttled=0, oom_kill=0, mem_max=0, pids_peak=5, pids_max_events=0)

    def set(self, **kw):
        with self.lock:
            self._set(**kw)

    def bump(self, **kw):
        """Add to counters under the lock (a thread of the fake runtime raises them while the serving thread sets others)."""
        with self.lock:
            self._set(**{k: self.values[k] + n for k, n in kw.items()})

    def _set(self, **kw):
        v = self.values = dict(getattr(self, "values", {}), **kw)
        files = {"memory.current": f"{v['memory_current']}\n", "memory.peak": f"{v['memory_peak']}\n", "pids.current": "3\n", "pids.peak": f"{v['pids_peak']}\n",
                 "cpu.stat": f"usage_usec {v['usage_usec']}\nuser_usec 1\nsystem_usec 1\nnr_periods 100\nnr_throttled {v['throttled']}\nthrottled_usec 0\n",
                 "memory.events": f"low 0\nhigh 0\nmax {v['mem_max']}\noom 0\noom_kill {v['oom_kill']}\n", "pids.events": f"max {v['pids_max_events']}\n"}
        for name, text in files.items():
            with open(os.path.join(self.dir, name), "w") as f:
                f.write(text)


class FakeRuntime:
    """popen() for a Swarm. Knobs: `mem_per_agent` (bytes added to memory.current per started agent), `oom_at` (the agent index from which the kernel kills agents and counts an OOM kill), `mute`
    (agents that never answer a prompt), `limit` (memory.max in bytes, the peak never passes it), `exit_code` (a print agent's exit status), `pids_block` (forks refused), `cpu_usec` (CPU per started agent),
    `cpu_per_prompt_usec`, `latency_ns`, `no_ready` (agents that never answer get_state), `dont_start` (the container itself does not come up), `write_files` (what an agent's prompts create), `die_at` (the container is killed, exit 137, with its cgroup, when this many agents have started), `no_reply` (print agents that exit 0 with nothing on their output), `undrained` (print agents that exit 0 whose output the relay had not finished reading), `hang` (print agents that never exit), `kill_at` (the kernel counts one OOM kill when this many agents have started; the agents that
    follow live on), `thrash_after` (once this many agents have started the container sits at its limit: `memory.events max` rises every 10 ms), `commands` (the bench extension commands an agent lists for get_commands) and `commands_late` (the first asks of each agent list none, as before the extensions are loaded)."""

    def __init__(self, cgroup, mem_per_agent=50 * 1048576, oom_at=None, mute=(), limit=None, exit_code=0, pids_block=False, cpu_usec=300_000, cpu_per_prompt_usec=20_000, latency_ns=5_000_000,
                 no_ready=(), dont_start=False, write_files=None, relay_cpu_ms=10.0, die_at=None, no_reply=(), undrained=(), kill_at=None, thrash_after=None, hang=(), commands=10, commands_late=0):
        self.cg = cgroup
        self.k = dict(mem_per_agent=mem_per_agent, oom_at=oom_at, mute=set(mute), limit=limit, exit_code=exit_code, pids_block=pids_block, cpu_usec=cpu_usec, cpu_per_prompt_usec=cpu_per_prompt_usec,
                      latency_ns=latency_ns, no_ready=set(no_ready), dont_start=dont_start, write_files=write_files, relay_cpu_ms=relay_cpu_ms, die_at=die_at, no_reply=set(no_reply), undrained=set(undrained), kill_at=kill_at, thrash_after=thrash_after, hang=set(hang), commands=commands, commands_late=commands_late)
        self.argvs, self.commands, self.started, self.removed, self.killed = [], [], 0, [], []
        self.thrashing = False
        self.t = 1_000_000_000
        self.lock = threading.Lock()

    def tick(self, ns=1_000_000):
        with self.lock:
            self.t += ns
            return self.t

    def popen(self, argv, **kw):
        if "rm" in argv[:3]:
            self.removed.append(argv)
            self.thrashing = False
            return Done()
        if "kill" in argv[:3]:
            self.killed.append(argv)
            self.thrashing = False
            return Done()
        self.argvs.append(argv)
        if self.k["dont_start"]:
            p = FakeProc(open(os.devnull, "wb"), iter(()))
            p.returncode = 125
            return p
        in_r, in_w = os.pipe()
        out_r, out_w = os.pipe()
        proc = FakeProc(os.fdopen(in_w, "wb"), os.fdopen(out_r, "rb"))
        threading.Thread(target=self.serve, args=(proc, os.fdopen(in_r, "rb"), os.fdopen(out_w, "wb")), daemon=True).start()
        return proc

    def emit(self, out, **ev):
        out.write((json.dumps(ev) + "\n").encode())
        out.flush()

    def serve(self, proc, inp, out):
        self.emit(out, ev="ready", t=self.tick())
        agents = {}
        for line in inp:
            cmd = json.loads(line)
            self.commands.append(cmd)
            op = cmd["op"]
            if op == "start":
                i = cmd["id"]
                agents[i] = dict(cmd, n=self.started)
                self.started += 1
                self.start(out, cmd, agents[i])
                if self.k["die_at"] is not None and self.started >= self.k["die_at"]:
                    time.sleep(0.2)   # the runner's monitor reads the counters every 50 ms: the last reading is what it has once the cgroup is gone
                    import shutil
                    shutil.rmtree(self.cg.dir, ignore_errors=True)
                    proc.returncode = 137
                    out.close()
                    return
            elif op == "send":
                self.send(out, cmd, agents)
            elif op == "stats":
                self.emit(out, ev="stats", req=cmd["req"], t=self.tick(), relay_cpu_ms=self.k["relay_cpu_ms"], cgroup=self.snapshot())
            elif op == "pss":
                self.emit(out, ev="pss", req=cmd["req"], kb={str(i): 100 * 1024 for i in cmd["ids"]}, unreadable=0)
            elif op == "quit":
                break
        self.thrashing = False
        self.emit(out, ev="bye", t=self.tick())
        proc.returncode = 0
        out.close()
        inp.close()

    def thrash(self):
        while self.thrashing:
            self.cg.bump(mem_max=1000)
            time.sleep(0.01)

    def snapshot(self):
        from buffon.runner.swarm import read_cgroup
        return read_cgroup(self.cg.dir)

    def grow(self, agent_n):
        v = self.cg.values
        mem = v["memory_current"] + self.k["mem_per_agent"]
        peak = max(v["memory_peak"], mem)
        if self.k["limit"]:
            peak = min(peak, self.k["limit"])
        self.cg.set(memory_current=min(mem, self.k["limit"] or mem), memory_peak=peak, usage_usec=v["usage_usec"] + self.k["cpu_usec"])

    def start(self, out, cmd, agent):
        n, i = agent["n"], cmd["id"]
        self.grow(n)
        if self.k["kill_at"] is not None and n + 1 == self.k["kill_at"]:
            self.cg.bump(oom_kill=1, mem_max=40)
        if self.k["thrash_after"] is not None and n + 1 >= self.k["thrash_after"] and not self.thrashing:
            self.thrashing = True
            threading.Thread(target=self.thrash, daemon=True).start()
        t = self.tick()
        if self.k["oom_at"] is not None and n >= self.k["oom_at"]:
            self.cg.set(oom_kill=self.cg.values["oom_kill"] + 1, mem_max=self.cg.values["mem_max"] + 40)
            self.emit(out, ev="exit", id=i, t=t, t_start=t - 1, code=-1, signal=9, err="", stdout_tail="", stderr_tail="")
            agent["dead"] = True
            return
        if self.k["pids_block"]:
            self.cg.set(pids_max_events=7, pids_peak=1152)
            self.emit(out, ev="exit", id=i, t=t, t_start=0, code=127, signal=0, err="start: fork/exec: resource temporarily unavailable", stdout_tail="", stderr_tail="")
            agent["dead"] = True
            return
        self.emit(out, ev="started", id=i, t=t, pid=1000 + i)
        if not cmd.get("stdin") and i not in self.k["hang"]:   # a print agent: does its work and exits
            if self.k["write_files"]:
                self.k["write_files"](cmd, 0)
            code = self.k["exit_code"]
            silent, unread = i in self.k["no_reply"], i in self.k["undrained"]
            tail = "" if silent or unread else (REPLY + "\n" if code == 0 else "boom")
            self.emit(out, ev="exit", id=i, t=t + 20_000_000, t_start=t, code=code, signal=0, err="", stdout_tail=tail, stderr_tail="", drained=not unread, out_bytes=0 if silent else 40)

    def send(self, out, cmd, agents):
        i = cmd["id"]
        agent = agents.get(i)
        if agent is None or agent.get("dead"):
            return
        msg = json.loads(cmd["data"])
        sent = self.tick()
        if msg.get("type") == "get_state":
            if i in self.k["no_ready"]:
                return
            self.emit(out, ev="out", id=i, t=sent + 3_000_000, sent=sent, line=json.dumps({"type": "response", "command": "get_state", "success": True}))
        elif msg.get("type") == "get_commands":
            agent["asked"] = agent.get("asked", 0) + 1
            listed = self.k["commands"] if agent["asked"] > self.k["commands_late"] else 0   # `commands_late`: the first asks come before the extensions are loaded and list none
            names = [{"name": f"bench-{k:02d}", "source": "extension"} for k in range(1, listed + 1)] + [{"name": "compact", "source": "builtin"}]
            self.emit(out, ev="out", id=i, t=sent + 3_000_000, sent=sent, line=json.dumps({"type": "response", "command": "get_commands", "success": True, "data": {"commands": names}}))
        elif msg.get("type") == "prompt":
            if i in self.k["mute"]:
                return
            turn = int(msg["message"].split("turn ")[1].split("]")[0])
            if self.k["write_files"]:
                self.k["write_files"](agent, turn)
            self.cg.set(usage_usec=self.cg.values["usage_usec"] + self.k["cpu_per_prompt_usec"])
            self.emit(out, ev="out", id=i, t=sent + self.k["latency_ns"] * (1 + i), sent=sent, line=json.dumps({"type": "agent_end"}))


class FakeMock:
    """The prefork mock's parent side (buffon/mock/prefork.py) without workers: it records what the swarm asks of it. `busy` is the share of a CPU each worker uses (CPU grows with wall time);
    `hot` makes worker 0 use `hot` of a CPU instead."""

    def __init__(self, path="/tmp/fake-swarm-mock.sock", k=4, offered=(), busy=0.1, hot=None, fewest=14):
        self.path, self.k, self._offered, self.busy, self.hot, self.fewest = path, k, set(offered), busy, hot, fewest
        self.policies, self.flushed, self.t0 = [], [], time.monotonic()

    def set_policy(self, projects, reply=None):
        self.policies.append(dict(projects))

    def cpu_ms(self):
        wall = (time.monotonic() - self.t0) * 1000.0
        return [wall * (self.hot if (i == 0 and self.hot is not None) else self.busy) for i in range(self.k)]

    def offered(self):
        return set(self._offered)

    def seen(self):
        return dict(getattr(self, "requests_seen", {}))

    def fewest_tools(self):
        return self.fewest

    def flush(self, context, sink):
        self.flushed.append((context, sink))
        return 0
