# SPDX-License-Identifier: Apache-2.0
"""The scale family: how many agents of one harness one container holds, found exactly (docs/design/SCALE.md).

Four workloads, each one sample per round that runs a whole search:

  scale/agents-limit   N long-lived RPC agents (Pi-dialect `--mode rpc`). All are started, every one must answer `get_state`, then `scale_turns` (default 3) turns run in lockstep (send to all, wait
                       for all). A turn is real agent work from the scripted model: read a file, write a file, run one shell command, then a final answer (buffon/mock `swarm_policy`).
  scale/print-limit    N concurrent one-shot print-mode agents (`-p`) doing the same task once.
  scale/agents-ext10   the RPC agents again, each loading the ten bench extensions (the ext10 fixture set), and ready only when all ten are listed.
  scale/print-ext10    the print agents again, each loading the ten bench extensions. Only arms that load Pi extensions (`pi_extensions` native or sidecar) take part.

The search (`search`): N doubles from 1, 2, 4 ... until the first probe that does not complete (the first failure F, the last pass P), then bisects between P and F down to the exact integer
(`scale_resolution`, default 1; a larger value stops when F and P are that close, and the sample says so). The limit is the largest N that completed. A probe completes when every agent is ready and
done (RPC: every turn answered; print: exit 0 with the final reply; and its file on disk when the harness has a write tool). The ceiling is the envelope, not a number: the kernel's OOM killer, the
pids limit or the clock stops the search. `swarm_max_agents` (default 8192) is a safety cap only: a harness that completes it reports "at least N (cap)" and says so.

All N agents of a probe run in one container (buffon/runner/swarm.py): the envelope's guarantees G1-G11, memory equal to memory-swap (`swarm_memory_gib`, default the run's memory tier, 4),
a cpuset (`swarm_cpus`, default the run's harness CPUs) with `--cpus` equal to its size, a pids limit of 64 per agent and 1,024 over (never the first limit), no network but the mock. The relay
inside the container launches the agents; the runner holds one `docker run -i` and reads the container's cgroup. There is no guard and no projection: the kernel decides. A probe ends as soon as
its cause is known, not at the timeout: at the first OOM kill (`oom`; the container is killed at once) or when the container sits at its memory limit with no agent making progress for
`scale_stall_s` and nothing was killed (`stall`). Both read as "did not fit". Every probe is recorded in the sample's `probes` with its N, its phase (double or bisect), its outcome, its cause
(oom, stall, timeout, pids, error) and its measurements (memory and CPU per agent, turns per second): the bisection adds points to the curves. CPU: `cpu_ms_per_agent_turn` is the container's CPU
over the same window as `turns_per_s` (RPC: the turn phase; print: the whole probe, one task per agent); `start_cpu_ms_per_agent` is the RPC start-up.

The scripted model is served by K worker processes (buffon/mock/prefork.py, `mock_workers`, default the number of mock CPUs) on one socket, so the Python interpreter's lock is not the ceiling. Parameters (--param KEY=VALUE, also `buffon up --param`): swarm_memory_gib, swarm_cpus, swarm_max_agents (8192), scale_resolution (1), mock_workers, scale_stage_timeout (120 s per stage), scale_stall_s (10 s), scale_turns (3), scale_batch (agents started per batch; 0, the
default, starts all at once), swarm_pids (override), swarm_sample_pss (agents whose PSS is read, 16).

Serial rule exception (docs/METHODOLOGY.md section 18): the agents of one probe run concurrently, by design; one probe runs at a time and nothing else runs on the host."""
import atexit
import os
import shutil
import time

from ..mock import REPLY, SWARM_FILE
from ..runner import cgroup
from ..runner import swarm as swarmlib
from . import Workload, register
from .overhead import Skip, prompt_command, skip_unless
from .streaming import param

TURNS = 3
MAX_AGENTS = 8192    # the safety cap (`swarm_max_agents`), not a design limit: the envelope's memory, pids and CPUs stop a harness first
RESOLUTION = 1       # the search ends when the limit and the first failure are this close: 1 is exact (`scale_resolution`)
EXT_COUNT = 10       # the extensions of the ext10 variants: the ten bench extensions (buffon/workloads/overhead.py `sweep_extensions`)
EXT_BASE_TOOLS = 4   # the tools a Pi-family harness declares without extensions: a request with the ten extensions declares at least 4 + 10 (the same check as overhead/print-ext10)
EXT_COMMAND = "bench-"   # the commands the bench extensions register; an RPC agent is ready with extensions when it lists EXT_COUNT of them
EXT_ASK_S = 0.5      # how often an agent that has not listed its extension commands yet is asked again
STAGE_TIMEOUT = 120.0
STALL_S = 10.0       # a probe at its memory limit with no agent making progress for this long has stalled (the kernel is reclaiming and killing nothing)
ROUNDS = 5           # the scale family measures this many rounds by default, and has no A/A copy: the spread across rounds is its noise (docs/METHODOLOGY.md section 18)
PSS_AGENTS = 16
MOCK_BUSY = 0.9      # the mock is saturated when its workers together kept this share of their K CPUs busy, or any one worker kept this share of its CPU busy
KINDS = {"agents": "rpc", "print": "print"}
VARIANTS = (("agents", "limit", 0), ("print", "limit", 0), ("agents", "ext10", EXT_COUNT), ("print", "ext10", EXT_COUNT))   # (kind, suffix of the workload id, extensions every agent loads)
STOP_CAUSES = ("oom", "stall", "timeout", "pids", "error")
PROMPT = "Read README.md, write a note, run one command, then tell me in one sentence what you did."


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def mib(nbytes):
    return None if nbytes is None else nbytes / 1048576


# -- parameters and the envelope ---------------------------------------------------------------------------------------------------------------------

def swarm_cpus(ctx):
    given = param(ctx, "swarm_cpus", None)
    if given is None or given == "":
        return sorted(int(c) for c in getattr(ctx.opts, "cpus", []) or [])
    if isinstance(given, (list, tuple)):
        return sorted(int(c) for c in given)
    from ..site import parse_cpus
    return sorted(parse_cpus(str(given)))


def swarm_memory_mib(ctx):
    explicit = param(ctx, "swarm_memory_gib", None)
    if explicit:
        return int(float(explicit) * 1024)
    return int(getattr(ctx.opts, "memory_mib", 4096))


def swarm_config(ctx, n, homes_dir):
    base = cgroup.CONTAINER
    if base is None:
        raise Skip("it needs the container envelope: pass --isolation container (a swarm is N agents in one container with a memory limit, a cpuset and a pids limit)")
    cpus = swarm_cpus(ctx) or list(base.cpuset_cpus)
    mock = set(getattr(ctx.opts, "mock_cpus", []) or [])
    if set(cpus) & mock:
        raise Skip(f"the swarm's CPUs {sorted(set(cpus) & mock)} are the mock's CPUs: the model would run on the agents' CPUs")
    pids = int(param(ctx, "swarm_pids", 0)) or swarmlib.pids_limit(n)
    return swarmlib.SwarmConfig(image=base.image, runtime=base.runtime, cpus=cpus, mems=base.cpuset_mems, memory_mib=swarm_memory_mib(ctx), pids=pids, ro_paths=list(base.ro_paths),
                                rw_dir=base.rw_dir, homes_dir=homes_dir, socket_path=base.socket_path, mock_port=base.mock_port, relay_dir=base.relay_dir)


# -- the search ---------------------------------------------------------------------------------------------------------------------------------

def search(run, cap=MAX_AGENTS, resolution=RESOLUTION):
    """The largest N whose probe completes, found by doubling and then bisecting. `run(n, phase)` runs one probe of n agents (phase "double" or "bisect") and returns its record: a dict that holds
    `failure` when the probe did not complete and nothing of the kind when it did. Returns {"limit", "first_failure", "capped", "probes"}.

    Doubling: N = 1, 2, 4, ... (the last step is the cap itself when the cap is not a power of two) until the first probe that fails, F, with the last pass P. Then the bisection: N = (P + F) // 2, a pass
    moves P up to it, a failure moves F down to it, until F - P is at most `resolution` (1: exact). The limit is P, a probe that was seen to complete, with F, a probe that was seen to fail, at most
    `resolution` above it. Every probe is kept in `probes` in the order it ran, as {"n", "phase", "ok", **record}; none is dropped or run twice. The harness may be flaky near its limit: the search never
    assumes the pass rule is monotonic, it reports the boundary it found (a pass with a failure just above it), and the rounds' range is what shows the flake.
    No pass at N = 1 is a limit of 0 and `first_failure` 1. A pass at the cap is `capped`: the limit is at least the cap, `first_failure` None."""
    resolution, cap = max(1, int(resolution)), max(1, int(cap))
    probes = []

    def probe(n, phase):
        rec = dict(run(n, phase) or {})
        ok = "failure" not in rec
        probes.append(dict(rec, n=n, phase=phase, ok=ok))
        return ok

    passed, failed, n = 0, None, 1
    while True:
        if not probe(n, "double"):
            failed = n
            break
        passed = n
        if passed >= cap:
            return {"limit": passed, "first_failure": None, "capped": True, "probes": probes}
        n = min(passed * 2, cap)
    while failed - passed > resolution:
        mid = (passed + failed) // 2
        if probe(mid, "bisect"):
            passed = mid
        else:
            failed = mid
    return {"limit": passed, "first_failure": failed, "capped": False, "probes": probes}


def mounted(path, roots):
    real = os.path.realpath(path)
    return any(real == os.path.realpath(r) or real.startswith(os.path.realpath(r) + os.sep) for r in roots)


def staged_extensions(ctx, arm, count=EXT_COUNT):
    """The extension sources every agent of an ext probe loads with `-e`: the arm's `count` bench extensions from the helper the extension sweep uses (buffon/workloads/overhead.py `sweep_extensions`), at paths the swarm container can read. The container mounts the
    workspace read-only and nothing else, so a source that lives in the repository is copied once into `<workspace>/fixtures/ext<count>-swarm/<arm>/`."""
    from .overhead import sweep_extensions
    paths = sweep_extensions(ctx, arm, count)
    roots = list(cgroup.CONTAINER.ro_paths) if cgroup.CONTAINER is not None else []
    out = []
    for path in paths:
        if mounted(path, roots):
            out.append(path)
            continue
        dest = os.path.join(os.path.dirname(ctx.work), "fixtures", f"ext{count}-swarm", arm.id, os.path.basename(path))
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.isdir(path):
                shutil.copytree(path, dest, symlinks=True)
            else:
                shutil.copy2(path, dest)
        out.append(dest)
    return out


# -- failure ------------------------------------------------------------------------------------------------------------------------------------

def exit_words(exits):
    """`3 agents exited (signal 9, exit 1)` from the relay's exit events."""
    if not exits:
        return ""
    kinds = sorted({f"signal {e['signal']}" if e.get("signal") else f"exit {e.get('code')}" for e in exits})
    killed = any(e.get("signal") == 9 for e in exits)
    return f"{len(exits)} agents exited ({', '.join(kinds)}{': killed, out of memory?' if killed else ''})"


def classify(oom_kills, pids_blocked, timed_out, stalled=False):
    """The stop cause: the kernel's own counters first (an OOM kill, a refused fork), then a stall at the memory limit, then the clock, else an error."""
    if oom_kills:
        return "oom"
    if pids_blocked:
        return "pids"
    if stalled:
        return "stall"
    if timed_out:
        return "timeout"
    return "error"


def failure_text(n, *, ready="answered get_state", never=0, lost=0, exits=(), unfinished=0, missing_files=0, oom_kills=0, peak_mib=None, limit_mib=None, pids_blocked=0, pids_peak=None, pids_max=None, memory_max_hits=0, first_error="", zero=None, stalled_s=None):
    """Why a probe stopped, in plain words: how many agents never answered, did not finish, exited (and how), and what the kernel's counters say."""
    parts = []
    if never:
        parts.append(f"{never} of {n} agents never {ready}")
    if lost:
        parts.append(f"{lost} of {n} agents did not answer a prompt" + (f" (first refusal: {first_error!r})" if first_error else ""))
    if unfinished:
        parts.append(f"{unfinished} of {n} agents did not finish")
    if exits:
        parts.append(exit_words(list(exits)))
    if zero:
        parts.append(zero)
    if missing_files:
        parts.append(f"{missing_files} of {n} agents did not write their file")
    if oom_kills:
        parts.append(f"out of memory: the kernel's OOM killer stopped {oom_kills} processes" + (f" (container peak {peak_mib:.0f} MiB of {limit_mib:.0f} MiB)" if peak_mib and limit_mib else ""))
    elif stalled_s is not None:
        parts.append(f"stalled at the limit, nothing killed: no agent made progress for {stalled_s:.0f} s at the {limit_mib:.0f} MiB memory limit ({memory_max_hits} limit hits)" if limit_mib else "stalled at the memory limit, nothing killed")
    elif memory_max_hits and (never or lost or unfinished):
        parts.append(f"the container hit its {limit_mib:.0f} MiB memory limit {memory_max_hits} times without an OOM kill (reclaim)" if limit_mib else "")
    if pids_blocked:
        parts.append(f"process limit: {pids_blocked} forks refused at {pids_peak} of {pids_max} processes")
    return "; ".join(p for p in parts if p)


def exited_zero(pool, agents, kind):
    """The sentence for agents that exited 0, the normal end of a print agent, without the final reply on their output: what the relay read of their output and what the mock saw of them. Empty for none."""
    agents = list(agents) if kind == "print" else []
    if not agents:
        return ""
    silent = sum(1 for a in agents if not a.exit.get("out_bytes"))
    unread = sum(1 for a in agents if a.exit.get("drained") is False)
    try:
        seen = pool.seen()
        counts = [seen.get(a.id, 0) for a in agents]
        full = 1 + len(pool.offered())          # one request per scripted step, and the answer
        mock = (f"; the mock saw {min(counts)} to {max(counts)} requests from them (a whole task is {full})" if min(counts) != max(counts) else f"; the mock saw {counts[0]} requests from each of them (a whole task is {full})")
    except (RuntimeError, ValueError):
        mock = ""
    words = [f"{silent} wrote nothing to their output" if silent else "", f"{unread} had output the launcher had not finished reading" if unread else ""]
    detail = ", ".join(w for w in words if w)
    return f"{len(agents)} agents exited 0 without finishing the task: no final reply on their output" + (f" ({detail})" if detail else "") + mock


def mock_flag(cores, worker_max, workers):
    """True when the mock was saturated: its K workers together kept `MOCK_BUSY` of K CPUs busy, or one worker kept `MOCK_BUSY` of its CPU busy (a worker is one Python process and cannot use more than about
    one CPU, so a connection that is stuck with a worker that is full waits whatever the others do). `cores` and `worker_max` are the busiest turn's CPU over its wall time, in CPUs."""
    if cores is None:
        return False
    return cores >= MOCK_BUSY * max(1, workers) or (worker_max or 0.0) >= MOCK_BUSY


# -- one sample ---------------------------------------------------------------------------------------------------------------------------------

def scan(a, match):
    """The first record of agent `a` at or after its cursor for which match(record) is true: (t, sent, record); the cursor moves past it."""
    while a.cursor < len(a.records):
        t, sent, rec = a.records[a.cursor]
        a.cursor += 1
        if match(rec):
            return t, sent, rec
    return None


class Run:
    """What one swarm sample reads of the host while the agents work: the mock workers' CPU (and the runner's own, which reads the container's events), per window."""

    def __init__(self, sw, pool, n):
        self.sw, self.pool, self.n = sw, pool, n
        self.mock_cpu_ms = self.runner_cpu_ms = 0.0
        self.mock_cores = self.mock_worker_max = None

    def mock_window(self, fn):
        """Run fn() and add the CPU the mock's workers used during it: `mock_cores` and `mock_worker_max` keep the busiest window's (CPU over wall time), so a saturated turn is not averaged away."""
        w0, p0, t0 = self.pool.cpu_ms(), time.process_time(), time.monotonic()
        try:
            return fn()
        finally:
            wall = (time.monotonic() - t0) * 1000.0
            self.runner_cpu_ms += (time.process_time() - p0) * 1000.0
            try:
                used = [b - a for a, b in zip(w0, self.pool.cpu_ms())]
            except RuntimeError:   # a worker is gone: the window has no reading
                used = []
            if used:
                self.mock_cpu_ms += sum(used)
                if wall > 0:
                    self.mock_cores = max(self.mock_cores or 0.0, sum(used) / wall)
                    self.mock_worker_max = max(self.mock_worker_max or 0.0, max(used) / wall)


def mock_pool(ctx, base):
    """The run's mock workers (buffon/mock/prefork.py): started on the first swarm sample, kept for the run, stopped at exit. K is `mock_workers`, default the number of mock CPUs."""
    pool = ctx.__dict__.get("swarm_mock")
    if pool is None:
        from ..mock.prefork import PreforkMock
        k = int(param(ctx, "mock_workers", 0)) or len(getattr(ctx.opts, "mock_cpus", []) or []) or 4
        pool = PreforkMock(os.path.join(os.path.dirname(base.socket_path), "swarm-mock.sock"), k).start()
        atexit.register(pool.close)
        ctx.swarm_mock = pool
    return pool


def agent_prompt(i, turn):
    return f"[agent {i} turn {turn}] {PROMPT}"


def probe(ctx, arm, n, kind, extensions=None, count=0):
    """One probe: n agents of `arm` working at once in one fresh container. Returns the probe's fields, with `failure` and `stop_cause` when it did not complete. `extensions` is None for plain agents,
    else the list of extension sources (possibly empty: built into the harness) every agent loads, of which there are `count`: the probe checks they were loaded."""
    ctx.release()   # the previous probe's harnesses (the engine releases the last one after the sample)
    homes = os.path.join(ctx.work, "swarm-homes")
    os.makedirs(homes, exist_ok=True)
    cfg = swarm_config(ctx, n, homes)
    pool = mock_pool(ctx, cgroup.CONTAINER)
    cfg.socket_path = pool.path
    timeout = float(param(ctx, "scale_stage_timeout", STAGE_TIMEOUT))
    turns = int(param(ctx, "scale_turns", TURNS)) if kind == "agents" else 1
    t0 = time.monotonic()
    sw = None
    try:
        harnesses = [ctx.harness(arm, f"s{i}", compaction=None, context_window=128000, home_root=homes, **({} if extensions is None else {"extensions": extensions})) for i in range(n)]
        prep_s = time.monotonic() - t0
        pool.set_policy({i: h.cwd for i, h in enumerate(harnesses)})
        sw = swarmlib.Swarm(cfg)
        out = {"agents": n, "agents_ok": 0, "swarm": cfg.record()}
        try:
            sw.start()
        except RuntimeError as error:
            return stop(out, "error", f"the swarm container did not start: {error}")
        out.update(drive(ctx, arm, sw, harnesses, kind, n, turns, timeout, cfg, pool, count if extensions is not None else 0))
        out["prepare_s"] = round(prep_s, 2)
        return out
    finally:
        if sw is not None:
            sw.close()
        try:
            pool.flush(dict(ctx.server.context, probe=n), getattr(ctx.server, "sink", None))   # every request of the probe, from every worker, in arrival order: one file
        except RuntimeError:
            pass
        shutil.rmtree(homes, ignore_errors=True)


def stop(out, cause, failure):
    out["failure"], out["stop_cause"] = failure, cause
    return out


def seed_of(h, homes):
    return os.path.join(swarmlib.SEED_IN_CONTAINER, os.path.relpath(h.home, homes))


def drive(ctx, arm, sw, harnesses, kind, n, turns, timeout, cfg, pool, ext_count=0):
    """Start the agents, run the work, read the container; returns the probe's fields (with `failure` and `stop_cause` when it did not complete). `ext_count` extensions are loaded by every agent: an RPC
    agent is ready when it lists them, and a probe that completes is checked to have declared their tools on every request."""
    homes = cfg.homes_dir
    run = Run(sw, pool, n)
    base = sw.cgroup() or {}
    base_events = base.get("memory.events") or {}
    base_pids = base.get("pids.events") or {}
    cpu0 = (base.get("cpu.stat") or {}).get("usage_usec")
    thr0 = (base.get("cpu.stat") or {}).get("nr_throttled", 0)
    relay0 = sw.relay_cpu_ms()
    out = {"mem_baseline_mib": mib(base.get("memory.current"))}
    sw.watch = swarmlib.Watch(base, cfg.memory_mib * 1048576, float(param(ctx, "scale_stall_s", STALL_S)))   # a probe ends at its first OOM kill or at a stall, not at the timeout
    cpu_ready = relay_ready = None
    dialect = getattr(arm, "rpc_dialect", {}) or {}
    turn_end = dialect.get("turn_end", "agent_end")
    shim = type("D", (), {"dialect": dialect})()
    timed_out = False
    never = unfinished = 0
    lost = set()
    lat, walls, ready_ms, makespan_ms, turn_s, errors = [], [], None, None, None, []
    batch = int(param(ctx, "scale_batch", 0)) or n

    def begin(i):
        h = harnesses[i]
        if kind == "agents":
            sw.start_agent(i, h.rpc_argv(), h.env, h.cwd, stdin=True, keep=[turn_end, "response"], seed=seed_of(h, homes), home=h.home)
            sw.send_line(i, {"type": "get_state", "id": "b1"})
        else:
            sw.start_agent(i, h.print_argv(agent_prompt(i, 0)), h.env, h.cwd, stdin=False, seed=seed_of(h, homes), home=h.home)

    def get_state_answered(a):
        return scan(a, lambda r: r.get("type") == "response" and (r.get("command") == "get_state" or r.get("id") == "b1"))

    # the agents: all at once, or in batches each of which must be ready (or done) before the next starts
    first_start = time.monotonic()
    if kind == "agents":
        ready = set()

        def settle(ids):
            pending, listing, asked = set(ids), set(), {}   # `listing`: answered get_state, its extension commands not all listed yet (Pi answers get_state before its extensions are loaded)

            def listed(r):
                found = [c for c in ((r.get("data") or {}).get("commands") or []) if str(c.get("name", "")).startswith(EXT_COMMAND)]
                return r.get("type") == "response" and r.get("command") == "get_commands" and len(found) >= ext_count

            def done():
                now = time.monotonic()
                for i in list(pending):
                    a = sw.agents[i]
                    if a.dead():
                        pending.discard(i)
                    elif i not in listing and get_state_answered(a):
                        if not ext_count:
                            a.ready = a.records[a.cursor - 1][0]
                            ready.add(i)
                            pending.discard(i)
                        else:
                            listing.add(i)
                    if i in listing:
                        if scan(a, listed):
                            a.ready = a.records[a.cursor - 1][0]
                            ready.add(i)
                            pending.discard(i)
                        elif now - asked.get(i, 0.0) >= EXT_ASK_S:
                            asked[i] = now
                            sw.send_line(i, {"type": "get_commands", "id": "b2"})
                return not pending
            return sw.wait_until(done, timeout), pending

        ok = True
        for lo in range(0, n, batch):
            ids = list(range(lo, min(n, lo + batch)))
            for i in ids:
                begin(i)
            reached, pending = settle(ids)
            if not reached and sw.verdict is None:
                timed_out = True
            if pending or len(ready.intersection(ids)) < len(ids):
                ok = False
                break
        never = n - len(ready)
        starts = [a.started for a in sw.agents.values() if a.started]
        stamps = [sw.agents[i].ready for i in ready]
        ready_ms = (max(stamps) - min(starts)) / 1e6 if stamps and starts else None
        out["ready_ms"] = ready_ms
        cg = sw.cgroup() or {}
        out["mem_ready_mib"] = mib(cg.get("memory.current"))
        live = sorted(i for i in ready if not sw.agents[i].dead())
        if ok and never == 0 and sw.verdict is None:
            cpu_ready = (cg.get("cpu.stat") or {}).get("usage_usec")   # the turn phase's CPU starts here: the start-up of the agents is its own figure
            relay_ready = sw.relay_cpu_ms(timeout=10)
            turn_s, lost, clock_out = lockstep(run, sw, live, turns, timeout, turn_end, shim, lat, errors)
            timed_out = timed_out or (clock_out and sw.verdict is None)
    else:
        for i in range(n):
            begin(i)
        run.mock_window(lambda: sw.wait_until(lambda: all(a.dead() for a in sw.agents.values()), timeout))
        timed_out = not all(a.dead() for a in sw.agents.values()) and sw.verdict is None
        unfinished = sum(1 for a in sw.agents.values() if not a.dead())
        exits = [a.exit for a in sw.agents.values() if a.exit]
        walls = [(e["t"] - e["t_start"]) / 1e6 for e in exits if e.get("t_start")]
        if exits:
            makespan_ms = (max(e["t"] for e in exits) - min(e["t_start"] for e in exits if e.get("t_start"))) / 1e6 if any(e.get("t_start") for e in exits) else None
        turn_s = makespan_ms / 1000 if makespan_ms else None
    work_s = time.monotonic() - first_start

    # what the container says
    end = sw.cgroup() or {}
    relay1 = sw.relay_cpu_ms(timeout=10)
    events = end.get("memory.events") or {}
    oom_kills = max(0, events.get("oom_kill", 0) - base_events.get("oom_kill", 0))
    max_hits = max(0, events.get("max", 0) - base_events.get("max", 0))
    pids_blocked = max(0, (end.get("pids.events") or {}).get("max", 0) - base_pids.get("max", 0))
    peak = mib(end.get("memory.peak"))
    base_mib = out["mem_baseline_mib"]
    cpu1 = (end.get("cpu.stat") or {}).get("usage_usec")
    launcher = None if relay0 is None or relay1 is None else max(0.0, relay1 - relay0)
    cpu_ms = None if cpu0 is None or cpu1 is None else max(0.0, (cpu1 - cpu0) / 1000 - (launcher or 0.0))
    turn_cpu_ms = start_cpu_ms = None   # RPC: the container's CPU (the relay's own taken off) over the turn phase, and over the start-up, from the first start to the last ready
    if kind == "agents" and cpu_ready is not None and relay_ready is not None:
        if cpu1 is not None and relay1 is not None:
            turn_cpu_ms = max(0.0, (cpu1 - cpu_ready) / 1000 - max(0.0, relay1 - relay_ready))
        if cpu0 is not None and relay0 is not None:
            start_cpu_ms = max(0.0, (cpu_ready - cpu0) / 1000 - max(0.0, relay_ready - relay0)) / n
    out.update({"mem_peak_mib": peak, "mem_per_agent_mib": None if peak is None or base_mib is None else max(0.0, (peak - base_mib) / n), "cpu_ms": cpu_ms, "launcher_cpu_ms": launcher,
                "oom_kills": oom_kills, "pids_peak": end.get("pids.peak"), "throttled_periods": max(0, (end.get("cpu.stat") or {}).get("nr_throttled", 0) - thr0),
                "mock_cpu_ms": run.mock_cpu_ms, "mock_cores": run.mock_cores, "mock_worker_max": run.mock_worker_max, "mock_workers": pool.k, "runner_cpu_ms": run.runner_cpu_ms,
                "mock_saturated": mock_flag(run.mock_cores, run.mock_worker_max, pool.k)})

    # which agents did what was asked
    zero = []
    if kind == "agents":
        done_agents = [a for a in sw.agents.values() if a.turns == turns and not a.dead()]
        exits = [a.exit for a in sw.agents.values() if a.dead()]
    else:
        done_agents = [a for a in sw.agents.values() if a.exit and a.exit.get("code") == 0 and not a.exit.get("signal") and REPLY.split()[0] in (a.exit.get("stdout_tail") or "")]
        exits = [a.exit for a in sw.agents.values() if a.exit and a not in done_agents]
        zero = [a for a in sw.agents.values() if a.exit and a not in done_agents and a.exit.get("code") == 0 and not a.exit.get("signal")]   # a print agent's normal end, without the reply
        exits = [e for e in exits if e.get("code") != 0 or e.get("signal")]
    missing = 0
    if "write" in pool.offered():
        for a in list(done_agents):
            if not all(os.path.exists(os.path.join(harnesses[a.id].cwd, SWARM_FILE.format(turn=t))) for t in range(turns)):
                missing += 1
                done_agents.remove(a)
    out["agents_ok"] = len(done_agents)
    completed = len(done_agents) == n
    if completed:
        pss = sw.pss_kb(pss_ids(ctx, n)) if kind == "agents" else {}
        out["pss_mib_per_agent"] = sum(pss.values()) / len(pss) / 1024 if pss else None
    agent_turns = n * turns if completed else max(1, sum(a.turns for a in sw.agents.values())) if kind == "agents" else max(1, len(done_agents))
    window_ms = turn_cpu_ms if kind == "agents" else cpu_ms   # the same window as turns_per_s: the turn phase (RPC), or the whole sample, which is the one task (print)
    out["cpu_ms_per_agent_turn"] = None if window_ms is None else window_ms / agent_turns
    if kind == "agents":
        out["start_cpu_ms_per_agent"] = start_cpu_ms
    out["turns_per_s"] = (agent_turns / turn_s) if turn_s else None
    if kind == "agents":
        out.update({"latency_ms_p50": percentile(lat, 0.5), "latency_ms_p95": percentile(lat, 0.95), "latency_ms_max": max(lat) if lat else None})
    else:
        out.update({"makespan_ms": makespan_ms, "wall_ms_p50": percentile(walls, 0.5), "wall_ms_p95": percentile(walls, 0.95)})
    out["work_s"] = round(work_s, 2)
    if completed and ext_count:
        fewest = pool.fewest_tools()
        if fewest is None or fewest < EXT_BASE_TOOLS + ext_count:
            return stop(out, "error", f"extensions did not load: the smallest tool list a request declared held {fewest} tools, and {EXT_BASE_TOOLS + ext_count} are expected with {ext_count} extensions")
    if completed:
        return out
    early = sw.verdict is not None   # the probe was cut at its cause: the agents that had not answered yet were not given the time, so they are not counted against it
    stalled = sw.verdict == "stall" and not oom_kills
    text = failure_text(n, ready="answered get_state" + (f" and listed their {ext_count} extension commands" if ext_count else ""), never=0 if early else never, lost=0 if early else len(lost), unfinished=0 if early else unfinished, exits=[e for e in exits if e], zero="" if early else exited_zero(pool, zero, kind),
                        missing_files=0 if early else missing, oom_kills=oom_kills, peak_mib=peak, limit_mib=cfg.memory_mib, pids_blocked=pids_blocked, pids_peak=end.get("pids.peak"), pids_max=cfg.pids,
                        memory_max_hits=max_hits, first_error=next((e for e in errors if e), ""), stalled_s=float(param(ctx, "scale_stall_s", STALL_S)) if stalled else None)
    if early:
        sw.kill()   # the cause is known and the readings are taken: stop the container now, not at the end of the stage
    gone = sw.exited()
    killed = gone in (137, -9) and peak is not None and peak >= 0.9 * cfg.memory_mib   # the kernel took the container's init or relay: its cgroup went with it, and the last reading may predate the kill
    if gone is not None:
        text = (text + "; " if text else "") + f"the swarm container exited (exit {gone})" + ("" if not killed else f": killed at {peak:.0f} of {cfg.memory_mib} MiB, out of memory")
    cause = classify(oom_kills or killed, pids_blocked, timed_out, stalled)
    return stop(out, cause, text or f"{len(done_agents)} of {n} agents finished")


def pss_ids(ctx, n):
    k = max(1, int(param(ctx, "swarm_sample_pss", PSS_AGENTS)))
    return sorted({int(i * (n - 1) / max(1, k - 1)) for i in range(k)}) if n > k else list(range(n))


def lockstep(run, sw, live, turns, timeout, turn_end, shim, lat, errors):
    """`turns` turns on every live agent: send to all, wait for all. Fills `lat` with each agent turn's latency (ms, on the relay's clock) and `errors` with what a refused prompt said. Returns (seconds of the turn phase, the agents that did
    not answer a turn, whether a wait ran out of time). The phase stops at the first turn that is not answered by every agent."""
    lost, edge, clock_out = set(), {"first": None, "last": None}, False
    for t in range(turns):
        sending = [i for i in live if i not in lost and not sw.agents[i].dead()]
        for i in sending:
            sw.send_line(i, prompt_command(shim, agent_prompt(i, t)))
        pending = set(sending)

        def done():
            for i in list(pending):
                a = sw.agents[i]
                got = scan(a, lambda r: r.get("type") == turn_end or (r.get("type") == "response" and r.get("command") == "prompt" and r.get("success") is False))
                if got:
                    t_end, sent, rec = got
                    pending.discard(i)
                    if rec.get("type") != turn_end:
                        lost.add(i)
                        errors.append(str(rec.get("error") or "")[:160])
                        continue
                    a.turns += 1
                    edge["last"] = max(edge["last"] or 0, t_end)
                    if sent:
                        lat.append((t_end - sent) / 1e6)
                        edge["first"] = min(edge["first"] or sent, sent)
                elif a.dead():
                    pending.discard(i)
                    lost.add(i)
            return not pending

        if not run.mock_window(lambda: sw.wait_until(done, timeout)):
            clock_out = True
        lost |= pending
        if lost:
            break
    first, last = edge["first"], edge["last"]
    return ((last - first) / 1e9 if first and last and last > first else None), lost, clock_out


def probe_record(rec):
    """What a probe keeps in the sample's `probes`: everything the probe measured, its own pids limit instead of the envelope record (the pids limit depends on N), without the agent count (`n` says it)."""
    out = {k: v for k, v in rec.items() if k not in ("swarm", "agents")}
    if rec.get("swarm"):
        out["pids_max"] = rec["swarm"]["pids_max"]
    return out


def limit_sample(ctx, arm, kind, count):
    """One round's search for one harness: the whole doubling and bisection (`search`), one probe per N, every probe recorded. `count` is the number of extensions every agent loads (0: none)."""
    skip_unless(ctx, arm, "rpc" if kind == "agents" else "print")
    paths = None
    if count:
        if arm.pi_extensions not in ("native", "sidecar"):
            raise Skip("it does not load Pi extensions" if arm.pi_extensions == "none" else "it loads only part of Pi's extensions")
        paths = staged_extensions(ctx, arm, count)
    cap = int(param(ctx, "swarm_max_agents", MAX_AGENTS))
    resolution = max(1, int(param(ctx, "scale_resolution", RESOLUTION)))
    envelope = []   # the swarm record of each probe: the sample's own has the largest pids limit

    def run(n, phase):
        t0 = time.monotonic()
        rec = probe(ctx, arm, n, kind, paths, count)
        envelope.append(rec.get("swarm"))
        rec["wall_s"] = round(time.monotonic() - t0, 2)
        return rec

    found = search(run, cap, resolution)
    probes = [probe_record(p) for p in found["probes"]]
    swarm = max((e for e in envelope if e), key=lambda e: e["pids_max"])
    out = {"agents_limit": found["limit"], "limit_capped": found["capped"], "limit_cap": cap, "limit_resolution": resolution, "probe_count": len(probes), "extensions": count, "swarm": swarm, "probes": probes}
    if not found["capped"]:
        failed = next(p for p in probes if p["n"] == found["first_failure"] and not p["ok"])
        out.update({"first_failure": found["first_failure"], "limit_cause": failed.get("stop_cause", "error"), "limit_failure": failed.get("failure", "")})
    if found["limit"] == 0:
        out["failure"], out["stop_cause"] = out["limit_failure"], out["limit_cause"]   # not even one agent finished: the sample is a stop, as one failed probe was
    return out


for _kind, _suffix, _count in VARIANTS:
    register(Workload(id=f"scale/{_kind}-{_suffix}", family="scale", fn=lambda c, a, k=_kind, n=_count: limit_sample(c, a, k, n), apis=(None,), rounds=ROUNDS, aa=False,
                      description=f"the most {'long-lived RPC' if _kind == 'agents' else 'one-shot print-mode'} agents of one harness that one container holds{' with the ten bench extensions loaded in each' if _count else ''}: "
                                  "double N, then bisect to the exact limit; memory per agent, CPU per turn, turns per second and where the kernel stops it at every N tried"))
