# SPDX-License-Identifier: Apache-2.0
"""What each durable workload is (docs/design/DURABLE.md 3.2 to 3.5): one table, read by the workload registry, the fixture builder, the equivalence gate and the campaign estimate.

A workload has a *fixture*, the store it starts from (a history built by the reference runtime through its real loop), and a *measured part*: ten turns of one shape. Two workloads that
need the same store share one fixture; the fixture's key is its own fields, never the workload's name.

  lane        `compat` is durable-bench's shape (one conversation, compaction off, window 10^9 tokens, eight 256-byte tool calls per measured turn; the history repeats 1, 1, 0 tool turns); `mixed` is
              the realistic default (compaction on, 200,000-token window, Pi's shipped compaction settings, the turn mix of 3.3); the rest are named by what they stress.
  flavor      `timing` (open the store, ten turns), `cold-every-turn` (a new process before every measured turn), `many-conv`, `grow`, `crash`, `floor-host`, `floor-sql`.
"""
from dataclasses import dataclass, field, replace

SEED = 20261018
MEASURED_TURNS = 10
WINDOWS = {"32k": 32_000, "200k": 200_000, "1m": 1_000_000}
COMPAT_WINDOW = 1_000_000_000   # durable-bench's window: 10^9 tokens, so nothing is ever compacted
MANY_CONV_HISTORY = 50


@dataclass(frozen=True)
class Fixture:
    """A store: its history and the settings it was built under. Equal fields, equal store."""
    history_kind: str            # script kind of the history turns: compat | mixed
    history: int                 # turns in the store (per conversation)
    variant: str = "repeating"   # repeating | varied
    window_tokens: int = 200_000
    compaction: bool = True
    conversations: int = 1
    docs: int = 0                # application document edits after the history
    background_tokens: object = None

    @property
    def label(self):
        return (f"{self.history_kind}-{self.history}" + ("-varied" if self.variant == "varied" else "") + f"-w{self.window_tokens}" + ("" if self.compaction else "-nocompact")
                + (f"-c{self.conversations}" if self.conversations > 1 else "") + (f"-d{self.docs}" if self.docs else ""))


@dataclass(frozen=True)
class Spec:
    id: str
    description: str
    flavor: str = "timing"
    lane: str = "mixed"
    fixture: object = None                     # Fixture, or None (grow, floor-host: no stored history)
    shape: str = "mixed"                       # script kind of the measured turns
    measured: int = MEASURED_TURNS
    window_tokens: object = None               # the window the measured turns run with (None: the fixture's)
    stream: bool = False
    summary_fails: bool = False
    background_tokens: object = None
    tasks: int = 0                             # child tasks per measured turn (the `fanout` tool)
    subagent: bool = False
    partial_ms: object = None
    needs: tuple = ()                          # capabilities an arm must have: its adapter answers `unsupported` otherwise
    rounds: int = 0
    aa: bool = True
    params: dict = field(default_factory=dict)

    @property
    def window(self):
        return self.window_tokens or (self.fixture.window_tokens if self.fixture else 200_000)

    @property
    def compaction(self):
        return self.fixture.compaction if self.fixture else True

    @property
    def history(self):
        return self.fixture.history if self.fixture else 0


def _mixed(history, variant="repeating", window=200_000, **kw):
    return Fixture("mixed", history, variant, window, True, **kw)


def _compat(history):
    return Fixture("compat", history, "repeating", COMPAT_WINDOW, False)


def build():
    """{workload id: Spec} for the whole family, in the order of the design's table (3.4)."""
    specs = []

    def add(**kw):
        specs.append(Spec(**kw))

    for n in (50, 250, 1000, 3500, 10000):
        add(id=f"durable/compat-{n}", lane="compat", fixture=_compat(n), shape="bench8", description=f"durable-bench's shape: open a {n}-turn store with compaction off and a 10^9-token window, then ten turns of eight 256-byte tool calls")
    for n in (1000, 3500, 10000):
        add(id=f"durable/mixed-{n}", fixture=_mixed(n), description=f"the default: open a {n}-turn store with compaction on and a 200k-token window, then ten turns of the mixed shape")
    for n in (1000, 3500, 10000):
        add(id=f"durable/mixed-varied-{n}", fixture=_mixed(n, "varied"), description=f"the varied twin of mixed-{n}: the same structure and sizes, every word replaced")
    for name, window in WINDOWS.items():
        add(id=f"durable/window-{name}-3500", fixture=_mixed(3500, window=window), description=f"mixed-3500 with a {name} token window: cost against the window, not the history")
    for n in (1000, 3500):
        add(id=f"durable/cold-every-turn-{n}", flavor="cold-every-turn", fixture=_mixed(n), description=f"reopen the {n}-turn store in a new process before every measured turn")
    for n in (50, 1000):
        add(id=f"durable/stream-{n}", fixture=_mixed(n), shape="stream", stream=True, description=f"ten turns whose answers stream 40 to 60 chunks over 1 to 2 s, on a {n}-turn store: write amplification and commit-before-show")
    for n in (50, 1000):
        add(id=f"durable/large-output-{n}", fixture=_mixed(n), shape="large", description=f"ten turns with one 32 KB tool result each, on a {n}-turn store")
    for n in (100, 1000):
        add(id=f"durable/docs-{n}", fixture=_mixed(1000, docs=n), description=f"the mixed turns after {n} application-document edits, one commit each, on a 1000-turn store", needs=("documents",))
    for n in (8, 64):
        add(id=f"durable/tasks-{n}", fixture=_mixed(1000), shape="tasks", tasks=n, description=f"ten turns in which one tool creates {n} child tasks and waits for them, on a 1000-turn store", needs=("tasks",))
    add(id="durable/subagent", fixture=_mixed(1000), shape="subagent", subagent=True, description="ten turns in which one tool owns a child conversation, on a 1000-turn store", needs=("subagents",))
    for n in (1, 8, 32, 128):
        add(id=f"durable/many-conv-{n}", flavor="many-conv", fixture=_mixed(MANY_CONV_HISTORY, conversations=n), measured=n,
            description=f"{n} conversations of {MANY_CONV_HISTORY} turns in one store, one turn each in round robin: memory per live conversation", rounds=0)
    for n in (1000, 3500):
        add(id=f"durable/grow-{n}", flavor="grow", lane="mixed", fixture=None, shape="mixed", measured=n, rounds=3, aa=False,
            description=f"build a {n}-turn history through the arm's own loop with compaction on, timing every turn: the cumulative cost and its growth")
    for n in (50, 1000, 3500):
        add(id=f"durable/crash-{n}", flavor="crash", fixture=_compat(n), shape="crash", rounds=1, aa=False,
            description=f"kill the process after the k-th commit of one turn on a {n}-turn store, reopen, resume, finish: the crash matrix over four orders of runtimes")
    add(id="durable/crash-stream", flavor="crash", fixture=_mixed(50), shape="stream", stream=True, rounds=1, aa=False,
        description="the crash matrix over every partial commit of one streamed turn")
    add(id="durable/compaction-fail", fixture=_mixed(1000, window=32_000), window_tokens=32_000, summary_fails=True,
        description="ten turns on a 32k window while every summary request fails: the failure path of compaction")
    add(id="durable/floor-host", flavor="floor-host", lane="floor", fixture=None, shape="mixed", description="the adapter with no durable runtime: the cost of the process, the protocol, the scripted model and tool, and a fixed number of trivial statements")
    add(id="durable/floor-sql", flavor="floor-sql", lane="floor", fixture=_mixed(3500), description="the statement stream of ten measured turns, captured once from the reference, replayed through each side's own SQLite facade and driver")
    out = {s.id: s for s in specs}
    assert len(out) == len(specs)
    return out


SPECS = build()

# The minimal first run of docs/design/DURABLE.md section 10, steps 1 to 6, as workload ids.
MINIMAL = ("durable/compat-1000", "durable/compat-3500", "durable/mixed-1000", "durable/mixed-3500", "durable/floor-host", "durable/floor-sql", "durable/crash-50")


def fixtures_of(specs):
    """The distinct fixtures the given specs need, in first-use order."""
    seen, out = set(), []
    for s in specs:
        if s.fixture is not None and s.fixture not in seen:
            seen.add(s.fixture)
            out.append(s.fixture)
    return out


def with_window(fixture, window):
    return replace(fixture, window_tokens=window)
