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
PI_COMMIT = "71023aec1546d6d677a65669c5665c0927ce0dd0"        # Pi v1.3.0 (tag v1.3.0 of github.com/earendil-works/pi, a lightweight tag read with `git ls-remote` and the GitHub API 2026-10-20); the digests below are those of the files at this commit
PIG_COMMIT = "e84d2349aed2525a49337142ac2be18405ee8014"       # main of the public github.com/MichaelKinsy/PiG (tree 85056e6fdd4fba6f42a8edaf32444210cf6e0903) on 2026-10-20; the digest of durable/storage/storage_bench_test.go there equals the one recorded before
DURABLE_BENCH_COMMIT = "e9abffab0a1056cf00c71a34ce83c7f41a746098"   # main of github.com/badlogic/durable-bench (a fork of clavia-labs/durable-bench: it contains that repository's main 09bf9933 and adds the pi-head target and harness/); no licence

PI_DURABLE = "packages/durable"
PI_EVALS = "packages/evals"

# Where each checkout key's repository lives and who owns it (the dashboard's source link and credit for a key that has no site profile). durable-bench has no licence: it is cited and run from a clone, never copied.
REPOSITORIES = {
    "pi": {"url": "https://github.com/earendil-works/pi", "owner": "Earendil Inc.", "licence": "MIT"},
    "pig": {"url": "https://github.com/MichaelKinsy/PiG", "owner": "Michael Kinsy", "licence": "MIT"},
    "pi-bolt": {"url": PI_BOLT, "owner": "Mario Zechner", "licence": "MIT"},
    "durable-bench": {"url": "https://github.com/badlogic/durable-bench", "owner": "Mario Zechner (fork of clavia-labs/durable-bench)", "licence": "none"},
}

# The files durable-bench's main benchmark runs at DURABLE_BENCH_COMMIT (`git show COMMIT:PATH | sha256sum`): the package manifest and lock, the compiler settings, bench/{seed,run,report,results,targets}.ts and the
# three targets' sources under src/. bench/chart.ts is not part of the command Buffon runs.
DURABLE_BENCH_FILES = (
    ("package.json", "a0b94fe5e2d1906dc93924f16cb911d0f3b25c51c6ad51f961fbd12ad48ec5d1"),
    ("bun.lock", "aa8aaaeab16c758fa9bce8d17af1de878bc2e49a2f29a06c01ca8bd5fa52f269"),
    ("tsconfig.json", "579094b451c2640d7e9bee922c36ad3ea593873d2b892f81e2c4f7da2c7ad7d7"),
    ("bench/tsconfig.json", "6ebb97e007c2c316e9bbab0fe445387e749080003ba81c94070eb16524c0856a"),
    ("bench/run.ts", "d0979126c8d776717e14c876e0937b3e8ce665d9f0fef0d4dbe0422dc40904d5"),
    ("bench/seed.ts", "64cc69c16a82acd3585287ad850d4ed5f75a215480ef6df39ebdf60d65de6bc5"),
    ("bench/targets.ts", "2935024175c5b12eb0585019961619e2f942ae7d74e73b96138ca6994a07e49f"),
    ("bench/report.ts", "9554abe27e8bb3d822414d559073c3a049c381cdcb324ba08e985592e63ebf5d"),
    ("bench/results.ts", "067f84f7f4821bc389f2b68937ebf6cdfa4cfe1efcd31082d938ccfbb75ea3eb"),
    ("src/pi.ts", "81ef83168411472bdcf59a59f02bd91a6c787fe8d900e0907c8014e74040717a"),
    ("src/pi-head.ts", "600f9205e499186265bbd656735d67ec18aa8d76b6c1d6055dea87d5d3d7b777"),
    ("src/plan.ts", "cc282e2ea3da1d286d0721eacda42906e104e5e7a976cb303587e850d8e6d335"),
    ("src/serve.ts", "5dcba3b8efe78d1d22bc77b7000976f827ac5d7668ecf360f1a537aa8870c0f4"),
    ("src/tardie.ts", "10c6d2024851db40330c2c2311a754bac360dddefdd7d0d020e9925ddc169b52"),
)
# The files of its harness/ benchmark that `npm run bench` runs (scripts/, src/, the npm manifest and lock, and the pinned Pi HEAD commit): bench.sh, run-suite.sh, build.mjs, build-bun.ts, pi-head.mjs,
# fetch-pi-head.sh (install time only), profsum.mjs and charts.mjs, the system-neutral driver and both adapters. slayer.sh is the dedicated-host wrapper and is not run.
DURABLE_BENCH_HARNESS_FILES = (
    ("harness/package.json", "ab357b860902ca22013a6e4a5064894d9c7b1f85023d2d92e6a6ead7bd83ee8a"),
    ("harness/package-lock.json", "08a5001662b25d0b1bceb58c35e2c6e24a31688e005d516fc321ade1adb0ae81"),
    ("harness/pi-head.sha", "c193190883cd4b162aca6a68852fbcd270111bffa732abe636588848a2769308"),
    ("harness/scripts/bench.sh", "300fd051156669526a193d717deb1475026a089818dc75ab4895928e45495a77"),
    ("harness/scripts/build-bun.ts", "f13c5661e452b5502c53a533ba347f5e32dc6dbc628498d88b19b64bddea780b"),
    ("harness/scripts/build.mjs", "b3c537d46b2e84dac1e17ed3e29001594086212c96e9006241add5ac895b84fb"),
    ("harness/scripts/charts.mjs", "f94abdd033aadafa0c1a51c223924928f36be179bd1050b45810073fad65ea92"),
    ("harness/scripts/fetch-pi-head.sh", "2a677720897af7cf662797a030408ce24dec651d403601b5babb9dc1a957e147"),
    ("harness/scripts/pi-head.mjs", "83f098405611c71b6ea03524ecc48238e16c3a0ad723a0bbf2d12ff932aacc46"),
    ("harness/scripts/profsum.mjs", "b271d73dfd9c924aaa01856a580d9f70bbe7ee63378000713bf8f14c33321dbc"),
    ("harness/scripts/run-suite.sh", "f802d4a25d11e05e74a90d78f2e6106a2ab16dd9c4d0a5a41ec1a68b60d5d1ef"),
    ("harness/src/cli.ts", "1b731a816b66ad39b5df2f70a0ebb3a3a40ae69f72fd9f48a81d2519ef7cbc81"),
    ("harness/src/common.ts", "8bc3f2720fedcd97221a6a8aeaa8dfaafd96fabc7302d3b6601373457cf49cf1"),
    ("harness/src/driver.ts", "a3d980d99c55a71b50107c389b831027a4f6f67797ee2b05b5b924e57f387b75"),
    ("harness/src/entry-bun.ts", "ceef8224b43acab5264ede0e918446a9b6d1f7ab3dc58fffbab25bc5edebc43e"),
    ("harness/src/entry-node.ts", "25e7d204251bf791fa7a9df33db2160d59e2246409b1a61073382a5ec3ad2d8a"),
    ("harness/src/pi/agent.ts", "56f4f058e90a3aead890a30d284b0a4f0f35c77c18bad5601ae5e36dded172fb"),
    ("harness/src/pi/sqlite-bun.ts", "5086af67dd799281b69bc6d788f5439dce90c0385c2877bebb0657ed5b5e2408"),
    ("harness/src/profile.ts", "a87cb41303fb8f3f367743ad6a10ede20950d7859606a0c346359904d4456888"),
    ("harness/src/records.ts", "cb3683e4c5737644e1141428809760a5f12b7f5446e1f73b49bd02588e2318b2"),
    ("harness/src/tardie/agent.ts", "76d91cb44159cc9d671e580e6938cdcd97e8dfbdad1e0abcca3467625951d872"),
    ("harness/src/tardie/sqlite-node.ts", "d001a3ff8570bef20cab73562f9292a43c4dc6b8f14f11ab94b2cedc9b9d2243"),
)


@dataclass(frozen=True)
class Target:
    repo: str            # checkout key: "pi", "pig", "pi-bolt" or "durable-bench"
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


DURABLE_PACKAGE = ((f"{PI_DURABLE}/package.json", "7877411c036932f74af4226563ff37f121013a9f69d4f9ceb55f5cdbcf6e5c54"),)
EVALS_FILES = ((f"{PI_EVALS}/package.json", "27b212ba5619d80476ea641b79e8363eaeac45435cbcebfdb6857e9314e197b0"),
               (f"{PI_EVALS}/vitest.test.config.ts", "dc52a94f234488cbab9ad69e59791990d27b1a3182c84ce2e2cd8a067a04b89f"))

TOOL_OUTPUT_UNITS = (("ms", "ms"), ("liveCommits", "count"), ("liveOpKiB", "KiB"), ("outputSets", "count"), ("commitP50Ms", "ms"), ("commitP99Ms", "ms"),
                     ("midRoundKiB", "KiB"), ("replayMs", "ms"), ("finalKiB", "KiB"), ("peakRssMiB", "MiB"), ("heapAfterGcMiB", "MiB"))

# The test-directory helpers a bench imports by relative path (the rest of what it runs is under src/, covered by the commit pin and the clean-tree check).
HARNESS_SUPPORT = (f"{PI_DURABLE}/test/harness-support.ts", "f9951297d5920e93aa38aca211537eb19c23a13a4fadf311e53afedb3b66bbc9")
HEAP_RETAINED = (f"{PI_DURABLE}/test/heap-retained.ts", "d545b3abb3c3bf6033df2f91a8bfd987635b596216723b0252925e1e0b355360")


def _pi_bench(script, file, digest, *helpers):
    """A Pi durable benchmark that runs a script of packages/durable/test/ with `npm run bench:SCRIPT`; the output is plain text, which Buffon keeps as printed."""
    return {"pi-node": Target("pi", PI_DURABLE, ("npm", "run", f"bench:{script}"), title=f"Pi durable {script.replace('-', ' ')} benchmark (npm run bench:{script})",
                              manifest=DURABLE_PACKAGE + ((f"{PI_DURABLE}/test/{file}", digest), *helpers))}


# One shell line for each durable-bench target. The arguments are the suite's own commands (`bun run seed`, `bun run bench`, `bun run report`); `cat results/results.jsonl` puts the JSONL the benchmark appends into
# stdout.txt, and `rm -rf results fixtures` starts from an empty results file as the fork's own run script does. The pi-head target builds Pi from the checkout in ../pi (the suite's default PI_SOURCE), so that
# checkout is first required to be at PI_COMMIT with no tracked change. No braces: argv entries containing one are passed through str.format.
DURABLE_BENCH_PI = (f'(test "$(git -C ../pi rev-parse HEAD)" = {PI_COMMIT} || (echo "../pi is not at Pi {PI_COMMIT[:12]} (v1.3.0)" >&2; exit 2)) && '
                    '(test -z "$(git -C ../pi status --porcelain --untracked-files=no)" || (echo "../pi has tracked changes" >&2; exit 2)) && '
                    'export PI_HEAD_VERSION=v1.3.0 && rm -rf results fixtures && bun run seed pi-head && bun run bench pi-head && bun run report && cat results/results.jsonl')
DURABLE_BENCH_NPM = "rm -rf results fixtures && bun run seed pi && bun run bench pi && bun run report && cat results/results.jsonl"
# `npm run bench` ends with scripts/charts.mjs, which rewrites harness/README.md and writes charts/ and report.html: the checkout has a tracked change and untracked files afterwards and the next run is refused until
# it is cleaned (docs/EXTERNAL.md). The exit status of the benchmark is kept across `cat`.
DURABLE_BENCH_HARNESS = "rm -rf results && SYSTEMS='pi pi-head' npm run bench; code=$?; cat results/results.jsonl; exit $code"

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
                                     manifest=DURABLE_PACKAGE + ((f"{PI_DURABLE}/test/tool-output-bench.ts", "0f5c085e4e52066a627e0ac970c87c57bae1bc1b4a6f29428cc52b88f70960be"),
                                                                 HARNESS_SUPPORT))},
          pins={"pi": PI_COMMIT}, section="durable",
          notes="no PiG equivalent found at the pin"),
    Suite("durable-nested-tools", "Durable nested-tools benchmark", "MIT", targets=_pi_bench("nested-tools", "nested-tools-bench.ts", "34e586071550ee1c90e110b93e0adabd01e1107da2483534f85845b742d5c1ed"),
          pins={"pi": PI_COMMIT}, section="durable", notes="added to packages/durable by Pi 1.2.0; plain-text output, kept as printed; no PiG equivalent found at the pin"),
    Suite("durable-nested-images", "Durable nested-images benchmark", "MIT", targets=_pi_bench("nested-images", "nested-images-bench.ts", "438c7fccd9b052ab65bb8ccb2f75498e77c96f203cec0dabc9f0cc16a21c1cd5"),
          pins={"pi": PI_COMMIT}, section="durable", notes="added to packages/durable by Pi 1.2.0; plain-text output, kept as printed; no PiG equivalent found at the pin"),
    Suite("durable-scheduler-fanout", "Durable scheduler fan-out benchmark", "MIT", targets=_pi_bench("scheduler-fanout", "scheduler-fanout-bench.ts", "8ac5993e126ffef3571d85f3e47c7186238f2087592d70e7c5d2d8220b580968"),
          pins={"pi": PI_COMMIT}, section="durable", notes="added to packages/durable by Pi 1.2.0; plain-text output, kept as printed; no PiG equivalent found at the pin"),
    Suite("durable-scheduler-memory", "Durable scheduler memory benchmark", "MIT", targets=_pi_bench("scheduler-memory", "scheduler-memory-bench.ts", "973d12fc936737122b0922c95391b40520001a9ca998550fc02e2b30c7eb39fb", HEAP_RETAINED),
          pins={"pi": PI_COMMIT}, section="durable", notes="added to packages/durable by Pi 1.2.0; plain-text output, kept as printed; no PiG equivalent found at the pin"),
    Suite("durable-document-cache", "Durable document-cache benchmark", "MIT", targets=_pi_bench("document-cache", "session-document-cache-bench.ts", "0ace49b9449f567da137d5ce4a02f37f6ea59d7fb4984add51dc2df0fb5586c9", HEAP_RETAINED),
          pins={"pi": PI_COMMIT}, section="durable", notes="added to packages/durable by Pi 1.2.0; plain-text output, kept as printed; no PiG equivalent found at the pin"),
    Suite("durable-document-append", "Durable document-append benchmark", "MIT", targets=_pi_bench("document-append", "document-append-bench.ts", "f7cf7590db6711bdc3eb71fc82fcf590579b8da4e8c6a6a2f062c89aca43f94f"),
          pins={"pi": PI_COMMIT}, section="durable", notes="added to packages/durable by Pi 1.2.0; plain-text output, kept as printed; no PiG equivalent found at the pin"),
    Suite("durable-codemode", "Durable codemode benchmark", "MIT", targets=_pi_bench("codemode", "codemode-bench.ts", "64244d9dc00d088f91db82500da28e697098d8c1808579c2fcb6cf69174d9089"),
          pins={"pi": PI_COMMIT}, section="durable", notes="added to packages/durable by Pi 1.2.0; plain-text output, kept as printed; no PiG equivalent found at the pin"),
    Suite("durable-bench", "durable-bench: cold and warm turns of a Pi conversation in a Miniflare Durable Object", "none",
          targets={"pi-node": Target("durable-bench", ".", ("sh", "-c", DURABLE_BENCH_PI), manifest=DURABLE_BENCH_FILES,
                                     title="durable-bench, pi-head target on Pi v1.3.0 (bun run seed, bench, report), unchanged"),
                   "pi-node-npm": Target("durable-bench", ".", ("sh", "-c", DURABLE_BENCH_NPM), manifest=DURABLE_BENCH_FILES,
                                         title="durable-bench, pi target on the Pi 1.0.4 npm package its lock names (bun run seed, bench, report), unchanged")},
          pins={"durable-bench": DURABLE_BENCH_COMMIT}, section="durable",
          notes="no licence (the GitHub API reports none for clavia-labs/durable-bench and badlogic/durable-bench): run from a clone at the pin, never copied into Buffon. Needs Bun, `bun install --frozen-lockfile` at install time "
                "and Miniflare's workerd; pi-node also needs a Pi checkout at the Pi pin as ../pi with its dependencies installed. A host without them records the failed run. Its published numbers (Apple M5; an i9-13900 core) "
                "are cited text with source and date, not imported. The pi-node-npm target is the one the published Pi 1.0.4 figures describe: our unchanged run of it against those figures gives the host factor; "
                "that factor is the only link between the published numbers and Buffon's"),
    Suite("durable-bench-harness", "durable-bench harness/: commit latency, reopen, memory, disk and versioning outside Durable Objects", "none",
          targets={"pi-node": Target("durable-bench", "harness", ("sh", "-c", DURABLE_BENCH_HARNESS), manifest=DURABLE_BENCH_HARNESS_FILES,
                                     title="durable-bench harness/ on Node and Bun, Pi 1.0.4 and Pi at its pinned HEAD (npm run bench), unchanged")},
          pins={"durable-bench": DURABLE_BENCH_COMMIT}, section="durable",
          notes="no licence: run from a clone at the pin, never copied into Buffon. A suite of hours (pass a long --timeout). Needs Node 24, Bun, `npm ci --ignore-scripts` and `bash scripts/fetch-pi-head.sh` at install time "
                "(the Pi HEAD it measures is the commit in harness/pi-head.sha, not Pi v1.3.0). Runs `SYSTEMS='pi pi-head'`: Tardigrade is not run unless asked. The run rewrites harness/README.md and writes charts/: "
                "clean the checkout before the next run"),
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
