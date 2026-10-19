# SPDX-License-Identifier: Apache-2.0
"""Upstream suites Buffon runs as they are. The registry names the repository, the licence, the command and the file digests for each target; Buffon adds nothing to a suite and removes nothing from it.

A target is one (repository checkout, working directory, command) triple. A suite that has no command for a harness has no entry for it: the report says "no equivalent at the pin", it never substitutes
a different benchmark. `{arm}` and `{command}` in an argv are filled with the arm id and the arm's command line.

A target's `manifest` lists (path, sha256) for the files the suite runs from. The import guard (guard.py) refuses a target with no manifest, and a target whose named file is missing or changed.
`table` names the parser for the suite's own console table (rows.py); `units` maps each printed metric name to the unit the suite's own type declares.
"""
from dataclasses import dataclass, field

PI_BOLT = "https://github.com/opensec-git/Pi-Bolt"
PI_BOLT_COMMIT = "13ccac32afb94366fb8d3e15aff1dd7bb234fefa"   # on origin/pi-bolt of the public repository (checked present at install time)
# The files the Pi-Bolt suites run at PI_BOLT_COMMIT, with their sha256. harness.py starts fake_model.py (large_write.py fake_model_stress.py, e2e_tools.py
# fake_model_tools.py) and copies fixtures/ into every run, so they are part of each suite; winproc.py is imported on Windows only. bench/floor/floor.c is
# used only with benchmark.py's opt-in --floor PATH, which Buffon does not pass.
PI_BOLT_FILES = (
    ("bench/benchmark.py", "0cb33122bcc47436a5f5f3b26cc162f061b1628117f8001dcd0af7e35f69025d"),
    ("bench/large_write.py", "1aeac1a6d3ec214b96a0532052c184d3a40ee588d573ff16604e72fef3aae5c8"),
    ("bench/long_session.py", "b881bcec1c4117e89d74f411cf21925b5401d908d1a36099f4ff76850b2e0f34"),
    ("bench/e2e_tools.py", "6b9aa64a82d830cf99355d7693717574e5b8da14f490fd77ed530a9723eafdf9"),
    ("bench/harness.py", "55b90941cb172f4da8df84063ca2c073797b98994ff88424090c1c4a0d576afd"),
    ("bench/fake_model.py", "c8dfd9b84a42bc92205904ae83a3e361b7fb99cbde27d74d7c0cfb59e2c6e9be"),
    ("bench/fake_model_stress.py", "a5ac0fdf03e3fc55f860dd241dca80b9a187b556930686686087cbddb3c737c0"),   # large_write.py's model (fake_model(script=...))
    ("bench/fake_model_tools.py", "8882d053533653dc131f514f9df0333f062ca0d2b5579e274fd633cfc708652d"),    # e2e_tools.py's model
    ("bench/winproc.py", "7bc394ddc607c75b438db075dbaeabaf80bf10653cf9fcf221650fd66af2d2cd"),
    ("bench/fixtures/openai-completions.ts", "a682245959c697d4f7a5ac54152f2db189099561b304725c651d6dbee22fd752"),
    ("bench/fixtures/agent-session.ts", "e5c020bced4ada5c5e116cbd160f66e111016fc717ae30d79994a45527e7f3d7"),
    ("bench/fixtures/interactive-mode.ts", "0af3d03d1af8bbe7672c704aa9414d14bd7f15b511320acc038af7148d214388"),
    ("bench/fixtures/tui.ts", "2ca47c56f4a4f24b8c6a4c9c9f2a06004bfc312d9dbcd0ac1921a2cae32bc675"),
)
PI_COMMIT = "abe508e1b89912adde45528136c3221eb69acdd7"        # Pi v1.1.0 (tag v1.1.0 of github.com/earendil-works/pi): the commit .upstream/pin names; the digests below were checked against that clone
PIG_COMMIT = "21cc2321a7b91bc8752b3a384d91afa2d64c1384"       # PiG tree at the lane's integrate-042 base (main), read-only checkout

PI_DURABLE = "packages/durable"
PI_EVALS = "packages/evals"


@dataclass(frozen=True)
class Target:
    repo: str            # checkout key: "pi", "pig" or "pi-bolt"
    cwd: str             # relative to the checkout
    argv: tuple
    note: str = ""
    manifest: tuple = ()  # ((path relative to the checkout root, sha256), ...): the suite's own files at the pin
    table: str = ""       # "" (stdout kept, nothing parsed) or "console-table" (rows.py)
    units: tuple = ()     # ((printed metric name, unit), ...) as the suite's own types declare them
    title: str = ""       # what the dashboard calls this target's card, when the suite family's title does not fit it (PiG's Go benchmark is not Pi's vitest one); plain text, no markup


@dataclass(frozen=True)
class Suite:
    id: str
    title: str
    licence: str
    targets: dict = field(default_factory=dict)     # target name -> Target
    pins: dict = field(default_factory=dict)        # checkout key -> pinned commit (None: the caller passes --commit KEY=SHA, or the run is refused)
    live: bool = False                              # needs a real model: refused unless the caller opts in explicitly
    arm_command: bool = False                       # the argv takes the arm's command line ({arm}={command})
    notes: str = ""
    section: str = "other"                          # where the dashboard shows its runs: "durable" (the Durable section) or "other" (Other suites); the registry decides, never the name


def _bolt(tool, *extra):
    return Target("pi-bolt", ".", ("python3", f"bench/{tool}", "--build", "{arm}={command}", *extra), manifest=PI_BOLT_FILES)


DURABLE_PACKAGE = ((f"{PI_DURABLE}/package.json", "2fa2159d5a0ef8fa1cb1f09bc00806999d7cac445ac8f1ba960e00799d005b18"),)
EVALS_FILES = ((f"{PI_EVALS}/package.json", "d61eefc11e19009216dd1591a02e65c434c0d99cdc9bb0e0a8d3a7d964372db7"),
               (f"{PI_EVALS}/vitest.test.config.ts", "dc52a94f234488cbab9ad69e59791990d27b1a3182c84ce2e2cd8a067a04b89f"))

TOOL_OUTPUT_UNITS = (("ms", "ms"), ("liveCommits", "count"), ("liveOpKiB", "KiB"), ("outputSets", "count"), ("commitP50Ms", "ms"), ("commitP99Ms", "ms"),
                     ("midRoundKiB", "KiB"), ("replayMs", "ms"), ("finalKiB", "KiB"), ("peakRssMiB", "MiB"), ("heapAfterGcMiB", "MiB"))

SUITES = {s.id: s for s in (
    Suite("durable-storage", "Durable storage benchmark", "MIT",
          targets={"pi-node": Target("pi", PI_DURABLE, ("npm", "run", "bench:storage"), title="Pi durable storage benchmark (npm run bench:storage, vitest bench)",
                                     manifest=DURABLE_PACKAGE + ((f"{PI_DURABLE}/vitest.benchmark.config.ts", "cd3db4912045a366a1549c854c3c30c487ae18bdf26d147440ab8987e8dd5230"),
                                                                 (f"{PI_DURABLE}/test/storage.bench.ts", "cac1b9e824538f9bbf470a63c130f9cbd3841daf5477592e19b574d590faf113"))),
                   "pig-native": Target("pig", ".", ("go", "test", "-run", "^$", "-bench", "BenchmarkStorage", "-benchmem", "./durable/storage/"), "storage_bench_test.go", title="PiG durable storage benchmark (go test -bench BenchmarkStorage)",
                                        manifest=(("durable/storage/storage_bench_test.go", "6e1f0c429cf870165b606182df36f21c27bad7ab2df5c33772353405e6ac910e"),)),
                   "pig-tinygo": Target("pig", ".", ("tinygo", "test", "-run", "^$", "-bench", "BenchmarkStorage", "./durable/storage/"), "cannot run if the package does not build under TinyGo: recorded as such",
                                        title="PiG durable storage benchmark under TinyGo (tinygo test -bench BenchmarkStorage)",
                                        manifest=(("durable/storage/storage_bench_test.go", "6e1f0c429cf870165b606182df36f21c27bad7ab2df5c33772353405e6ac910e"),))},
          pins={"pi": PI_COMMIT, "pig": PIG_COMMIT}, section="durable"),
    Suite("durable-storage-memory", "Durable storage memory benchmark", "MIT",
          targets={"pi-node": Target("pi", PI_DURABLE, ("npm", "run", "bench:storage:memory"), table="console-table", title="Pi durable storage memory benchmark (npm run bench:storage:memory)",
                                     manifest=DURABLE_PACKAGE + ((f"{PI_DURABLE}/test/storage-memory.ts", "fe3bd4560fb90efbd84d9c4110a3734c859cb071c5029acf7b3eb8b1946654a7"),))},
          pins={"pi": PI_COMMIT}, section="durable",
          notes="no PiG equivalent found at the pin: the report says so instead of substituting a benchmark"),
    Suite("durable-tool-output", "Durable tool-output benchmark", "MIT",
          targets={"pi-node": Target("pi", PI_DURABLE, ("npm", "run", "bench:tool-output"), table="console-table", units=TOOL_OUTPUT_UNITS, title="Pi durable tool-output benchmark (npm run bench:tool-output)",
                                     manifest=DURABLE_PACKAGE + ((f"{PI_DURABLE}/test/tool-output-bench.ts", "0f5c085e4e52066a627e0ac970c87c57bae1bc1b4a6f29428cc52b88f70960be"),))},
          pins={"pi": PI_COMMIT}, section="durable",
          notes="no PiG equivalent found at the pin"),
    Suite("pi-evals-offline", "Pi packages/evals self tests (npm test, no model)", "MIT",
          targets={"pi-node": Target("pi", PI_EVALS, ("npm", "test"), manifest=EVALS_FILES)}, pins={"pi": PI_COMMIT}),
    Suite("pi-evals", "Pi packages/evals host evals (npm run eval:host, real model)", "MIT",
          targets={"pi-node": Target("pi", PI_EVALS, ("npm", "run", "eval:host"), manifest=EVALS_FILES)}, pins={"pi": PI_COMMIT}, live=True,
          notes="spends money: only through `buffon agentbench` bookkeeping and an explicit --live"),
    Suite("pi-bolt-benchmark", "Pi-Bolt benchmark.py: startup, headless and interactive scenarios", "MIT", targets={"build": _bolt("benchmark.py")},
          pins={"pi-bolt": PI_BOLT_COMMIT}, arm_command=True),
    Suite("pi-bolt-large-write", "Pi-Bolt large_write.py: a 50 and 200 KB file through a streamed tool call", "MIT", targets={"build": _bolt("large_write.py")},
          pins={"pi-bolt": PI_BOLT_COMMIT}, arm_command=True),
    Suite("pi-bolt-long-session", "Pi-Bolt long_session.py: one process, many prompts", "MIT", targets={"build": _bolt("long_session.py")},
          pins={"pi-bolt": PI_BOLT_COMMIT}, arm_command=True),
    Suite("pi-bolt-e2e-tools", "Pi-Bolt e2e_tools.py: every core tool's transcript and files byte-identical to a reference build", "MIT",
          targets={"build": _bolt("e2e_tools.py")}, pins={"pi-bolt": PI_BOLT_COMMIT}, arm_command=True,
          notes="a correctness gate: a build that fails it has no timing worth reading"),
)}


def get(suite_id):
    try:
        return SUITES[suite_id]
    except KeyError:
        raise ValueError(f"unknown external suite {suite_id!r}; known: {', '.join(sorted(SUITES))}") from None


def argv_for(suite, target, arm=None, command=None):
    """The suite's argv for a target with `{arm}` and `{command}` filled in. Raises ValueError when the suite has no such target."""
    t = suite.targets.get(target)
    if t is None:
        raise ValueError(f"{suite.id} has no equivalent for {target!r} (targets: {', '.join(sorted(suite.targets))})")
    if suite.arm_command and not (arm and command):
        raise ValueError(f"{suite.id} compares builds: pass --arm ID and --command LINE")
    return t, [a.format(arm=arm, command=command) if "{" in a else a for a in t.argv]
