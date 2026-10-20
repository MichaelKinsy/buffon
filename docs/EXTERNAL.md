# External suites and external results

Other projects publish benchmarks, and Pi ships some of its own. Buffon treats them in two ways and keeps both out of its aggregates.

## Families and the import guard

A family is one upstream suite at one pin. `buffon/external/suites.py` records, for each target, the repository key, the command, the sha256 of each file the suite runs (`manifest`), the parser for the suite's own console table (`table`) and the unit of each printed metric (`units`).

Pins:

- Pi: `71023aec1546d6d677a65669c5665c0927ce0dd0` (`PI_COMMIT` in `buffon/external/suites.py`, tag `v1.3.0` in `github.com/earendil-works/pi`, the version of the `pi-node` reference arm; the tag is lightweight and was read with `git ls-remote` and the GitHub API on 2026-10-20). Every digest was taken from the file at that commit (`git show v1.3.0:PATH | sha256sum`) and checked with the guard against a checkout of it, and the test `test_the_recorded_pi_digests_equal_the_pinned_files` checks them against any checkout at the pin. Against the previous pin (v1.1.0) the bench scripts and `vitest.benchmark.config.ts` are byte-identical; only `packages/durable/package.json` (new scripts) and `packages/evals/package.json` changed. Tool-output's `Metrics` type is unchanged, so its unit table is too.
- PiG: `e84d2349aed2525a49337142ac2be18405ee8014`, `main` of the public `github.com/MichaelKinsy/PiG` (tree `85056e6fdd4fba6f42a8edaf32444210cf6e0903`, read with `git ls-remote` on 2026-10-20). The sha256 of `durable/storage/storage_bench_test.go` at that commit equals the one recorded for the earlier pin, so the digest is unchanged. The targets are `pig-native` and `pig-tinygo`.
- durable-bench: `e9abffab0a1056cf00c71a34ce83c7f41a746098` (`DURABLE_BENCH_COMMIT`), `main` of `github.com/badlogic/durable-bench`, the fork that holds the `pi-head` target and `harness/` (pushed 2026-10-06; it contains `main` of `github.com/clavia-labs/durable-bench`, `09bf99332bb9385e35ef5507c8f16fcbf3a875a7`). Neither repository has a licence (the GitHub API reports none), so it is cited and run from a clone, never copied. The digests (`DURABLE_BENCH_FILES`, `DURABLE_BENCH_HARNESS_FILES`) are of the files at that commit.
- Pi-Bolt: `13ccac32afb94366fb8d3e15aff1dd7bb234fefa`, a commit on the `pi-bolt` branch of the public repository `github.com/opensec-git/Pi-Bolt` (MIT). The digests of the thirteen files its suites run (`bench/benchmark.py`, `large_write.py`, `long_session.py`, `e2e_tools.py`, `harness.py`, `fake_model.py`, `fake_model_stress.py` (large_write's model), `fake_model_tools.py` (e2e_tools's model), `winproc.py`, and the four `bench/fixtures/*.ts`) are in `PI_BOLT_FILES`. `bench/floor/floor.c` is used only with `benchmark.py --floor`, which Buffon does not pass. Fetch the clone once at install time, never during a run:

```
git clone --filter=blob:none https://github.com/opensec-git/Pi-Bolt.git "${XDG_CACHE_HOME:-$HOME/.cache}/buffon/external/Pi-Bolt"
git -C "${XDG_CACHE_HOME:-$HOME/.cache}/buffon/external/Pi-Bolt" checkout 13ccac32afb94366fb8d3e15aff1dd7bb234fefa
```

The import guard (`buffon/external/guard.py`) refuses a run in these cases, before any process starts:

- the target has no recorded digests (an unpinned suite);
- a named file is missing or has a different sha256 (the error names the file);
- the checkout is not at the pin, has tracked changes, or has untracked files (an added file can join a suite: Pi's bench config includes `test/**/*.bench.ts`). Ignored files such as `node_modules` are not checked.

`buffon external plan --suite ID --target T --checkout DIR [--commit SHA]` prints the argv, the pin, the state of each named file, and every refusal. It starts nothing and takes no host lock. `buffon external run` applies the same guard, then runs the suite. The run record keeps `pins`, `pin_source` (`suite` or `caller`), `manifest` (each file's sha256) and `units`. The report's External suites row marks a commit the caller chose as "caller's commit, not the suite's pin".

A `console-table` target (`durable-tool-output`, `durable-storage-memory`) writes `rows.jsonl`. Each row keeps the column names the suite prints, and cell text is kept as printed. When the parser cannot read the table, the run is still recorded: `rows` is null, `rows_error` gives the reason and the report row says "table not parsed". The unit comes from the suite's own type, or from the column name when the name carries it (`RSS after seed MiB`). `bench:storage` runs vitest with the verbose reporter. Its output is kept in `stdout.txt` and no rows are parsed. The Go storage benchmark keeps its `go test -bench` output the same way.

Published results have families too. `buffon external import --family pi-bolt-published-headless --out DIR FILES` checks each file's sha256 against the published files at the pin (`PI_BOLT_SOURCE`, `bench/results/2026-10-11-linux-x64-0.8.0/`) and refuses an unknown or changed file before it copies anything. It then refuses the import (removing the directory) when a CPU median is more than 0.5 ms from the whole-ms value Pi-Bolt published, or when a build has another number of runs than the table.

The tests in `tests/test_external_suites.py` check the digests against real files when `BUFFON_PI_MIRROR` (Pi's checkout at the pin), `BUFFON_PIG_CHECKOUT` (a PiG checkout at its pin) and `BUFFON_PI_BOLT_CHECKOUT` (the Pi-Bolt clone at its pin) are set. They skip otherwise. With each set, a one-byte change to a copy of the pinned file must fail the guard (`storage.bench.ts`, `bench/benchmark.py`).

## External suites: run as they are

`buffon external suites` lists the registry (`buffon/external/suites.py`): Pi's durable benchmarks (`bench:storage`, `bench:storage:memory`, `bench:tool-output`, and the seven that Pi 1.2.0 added to `packages/durable`: `bench:nested-tools`, `bench:nested-images`, `bench:scheduler-fanout`, `bench:scheduler-memory`, `bench:document-cache`, `bench:document-append`, `bench:codemode`; registered as `durable-nested-tools` and so on, with the script's own file and the test-directory helper it imports pinned by digest), durable-bench and its `harness/` benchmark, Pi's `packages/evals` (offline self tests; the host evals need a real model and run only through `buffon agentbench` with `--live`), and Pi-Bolt's `benchmark.py`, `large_write.py`, `long_session.py` and `e2e_tools.py` (the byte-identical tool-output gate). A target is a repository checkout, a working directory and the upstream command. PiG's storage benchmark is `BenchmarkStorage*` in `durable/storage/storage_bench_test.go` (native Go, and TinyGo where the package builds). Pi's durable benchmarks have pins now (see Families above). PiG's storage benchmark is pinned at its own commit. The seven benchmarks of Pi 1.2.0 print plain text, which `stdout.txt` keeps as printed (no table is parsed, no unit is assigned). A suite with no command for a harness (for example the storage memory benchmark for PiG) has no entry: the report says there is no equivalent at the pin; Buffon never substitutes another benchmark.

```
python3 -m buffon external run --suite durable-storage --target pi-node \
    --checkout /path/to/pi --commit pi=<sha> --out runs/ext/durable-storage-pi-node --cpus 192-195
```

The run takes the host lock, refuses a checkout that is not at the pin or has tracked changes or untracked files, refuses a live suite without `--live`, gives the suite only `PATH`, the locale, `TZ`, `TERM`, a `HOME` inside the run directory and the variables named with `--env NAME=VALUE` (none of the operator's `PI_*`, `PIG_*`, agent directories, credentials or HOME), runs the suite's command unchanged in the checkout under the socket audit (a connection outside loopback is recorded in `egress`, shown in the report and fails the command with exit 4), and writes `external-suite.json` (command, commit, exit, times, host.json) with the suite's `stdout.txt` and `stderr.txt`. Pi and PiG are pinned in the registry (see Families above); a caller may pass `--commit KEY=SHA` to run another commit, and the digests are still checked. Pi-Bolt's suite is pinned to `13ccac32afb94366fb8d3e15aff1dd7bb234fefa`. A suite that compares builds takes `--arm ID --command LINE`.

A measured run needs the dedicated host like any other: it takes the host lock.

### Install steps (done once, never during a run)

A run makes no network connection, so everything a suite needs is installed first. For Pi's durable benchmarks the checkout needs its dependencies and the workspace packages `chord` and `pi-ai` built:

```
git clone --filter=blob:none https://github.com/earendil-works/pi.git "$CACHE/pi" && git -C "$CACHE/pi" checkout 71023aec1546d6d677a65669c5665c0927ce0dd0
(cd "$CACHE/pi" && npm ci --ignore-scripts && npm run build --workspace=@earendil-works/chord && npm run build --workspace=@earendil-works/pi-ai)
```

`pi-ai`'s build calls its model-data step, which needs the network; in a checkout tried for this change it exited non-zero while still writing the `dist/` the benchmarks import, and all ten `bench:*` scripts then ran. Treat that step's exit status as unverified.

### durable-bench (no licence: cited, run unchanged)

`buffon external run --suite durable-bench` runs the main benchmark of `github.com/badlogic/durable-bench` as the repository ships it: Miniflare workerd, one Durable Object, a scripted model and one tool, three samples at each of 50, 250, 1,000 and 3,500 turns, each sample in a fresh runtime. Nothing of it is copied into Buffon; the suite's files are checked by digest, like Pi-Bolt's. Both targets run on Bun and keep the suite's own output: `bun run report` prints its table to `stdout.txt`, and `cat results/results.jsonl` appends the JSONL the benchmark wrote.

- Install (Bun required; the lock is `bun.lock`): `git clone https://github.com/badlogic/durable-bench.git "$CACHE/durable-bench" && git -C "$CACHE/durable-bench" checkout e9abffab0a1056cf00c71a34ce83c7f41a746098 && (cd "$CACHE/durable-bench" && bun install --frozen-lockfile)`.
- `pi-node` is the suite's `pi-head` target: pi-durable built from the Pi sources in `../pi` (a Pi checkout beside the durable-bench one, at `PI_COMMIT` and installed as above) through Pi's own Durable Object adapter, labelled `v1.3.0`. The command first refuses a `../pi` that is not at the Pi pin or has tracked changes. It is `rm -rf results fixtures && bun run seed pi-head && bun run bench pi-head && bun run report && cat results/results.jsonl` with `PI_HEAD_VERSION=v1.3.0` exported; the argv is in `buffon/external/suites.py` (`DURABLE_BENCH_PI`).
- `pi-node-npm` is the suite's `pi` target, which uses the `@earendil-works/pi-durable` package that the repository's lock names (1.0.4) and its own hand-written storage facade: `rm -rf results fixtures && bun run seed pi && bun run bench pi && bun run report && cat results/results.jsonl`. It is the target the published Pi figures describe.
- Calibration line: the published figures below are for another machine. Our unchanged `pi-node-npm` run against them gives one host factor per size (our cold or warm median over the published one); the registry's `notes` says so, and the factor is the only link between the published numbers and Buffon's. It is computed by the reader from the run record; Buffon stores no factor.
- Cannot run: a host without Bun or workerd, or without the `../pi` checkout, records the failed command (exit status and stderr in the run record) as the run; Buffon never substitutes another benchmark. The suite waits for CPU use below 8% before each sample, so on a busy host it can run long: the run's `--timeout` (default 2,700 s) records a timeout as such, and a full run needs a larger one.
- Published numbers, cited and not imported: the `README` of `clavia-labs/durable-bench` (the same text is in the fork at the pin) gives, for 3,500 turns on a MacBook Air (Apple M5, 10 cores, 32 GB, macOS 26.6.2), Pi cold 365 ms and warm 313 ms, Tardigrade cold 880 ms and warm 123 ms (repository pushed 2026-10-06). `pi-vs-tardigrade/README.md` of the fork gives, for Pi `main` at `da866ada` on two performance-core threads of an i9-13900 (Docker, Bun 1.4.2), cold 183 ms and warm 82 ms at 3,500 turns (pushed 2026-10-06). They are text here, with their source, host and date; no file of theirs is imported.

`durable-bench-harness` is the second benchmark of the same repository, `harness/`, which runs outside Durable Objects on Node and Bun (commit latency, reopen, memory, disk, a versioning matrix). Install: in `harness/`, `npm ci --ignore-scripts && bash scripts/fetch-pi-head.sh` (this fetches Pi at the commit in `harness/pi-head.sha`, `da866ada…`, which is not Pi v1.3.0, so the suite says what it measures in its title and notes). The command is `rm -rf results && SYSTEMS='pi pi-head' npm run bench; code=$?; cat results/results.jsonl; exit $code`, run in `harness/`. It measures Pi 1.0.4 (npm) and Pi at its pinned HEAD; Tardigrade is left out unless asked. It takes hours (its own deadline is three hours for most steps): pass `--timeout`. Its last step, `scripts/charts.mjs`, rewrites `harness/README.md` and writes `charts/` and `report.html`, so the checkout must be reset (`git checkout -- harness/README.md`, remove `harness/charts` and `harness/report.html`) before another run, or the guard refuses the dirty tree. Its published results (`pi-vs-tardigrade/data/harness-pi-head-vs-tardie.jsonl`) are cited, not imported.

## External results: published numbers, imported with provenance

`buffon external import FILES --meta meta.json --out DIR` copies the files unchanged and writes `external.json` with the source URL, repository, commit, the versions the source measured, the source's host, licence and publication date, and a sha256 for every file. A result set without any of those is refused; a file changed after import is refused when it is loaded. `external/results/pi-bolt-2026-10-11-linux-x64-0.8.0/` holds Pi-Bolt's published Linux data (MIT); its headless CPU medians equal the README table (80, 261, 1752, 323, 618 ms), and `tests/test_external.py` checks that. The source's `pig` build is PiG 0.4.1 on Pi 1.0.3, against Pi 1.1.0: the versions are skewed, which the section shows.

Sources whose licence is unclear or whose data is not machine-readable are cited, not imported (the survey is `R8-pi-benchmarks.md`).

## Where they appear

`buffon report RUN... --external-results DIR... --external-suites DIR...` appends `External results` and `External suites` sections after everything Buffon measured, each labelled as not measured by the Buffon. They are never part of a cell, an A/A floor, a tally, an aggregate or a verdict:

- `buffon/runner/raw.py` refuses a directory that holds `external.json` or `external-suite.json`, so no run reader can load one by mistake.
- Report cells are built from the raw runs only; a test builds the report with and without the external sections and requires the rest to be byte-identical.
- `buffon dashboard RUN... [--external-suites DIR...] [--external-results DIR...]` draws them in one section of the site, "Other suites" (`#/r/other-suites`), the last section before "All metrics" and there only when the arguments hold any. A directory with `external-suite.json` or `external.json` among the run directories counts as an external one. The section keeps them out of every tile, ratio, grade and the all-metrics table (a test compares the data Buffon's views draw with and without them). Each suite is one card, grouped by project (Pi's durable suites, PiG's storage benchmark, Pi-Bolt's suites): its name and owner, the pinned commit and its source link, the command, the host and when it ran, the line "Their method, their numbers: not comparable with Buffon's rows", the suite's own table as printed from `rows.jsonl` (column names, units and cell text unchanged), and the raw stdout one click away. A table that did not parse says "table not parsed" and shows stdout; a suite with no parser shows its stdout. Runs of one suite whose columns match share one table with a column for each target; otherwise each target has its own table. An imported result set is a card with its provenance, its files unchanged (with their sha256) and a table of medians over the source's rows. The site holds its own copies of the files under `external/`.

An external claim becomes a Buffon result only when the same workload is reproduced under Buffon's rules (the interleaved, serial, A/A-floored procedure in METHODOLOGY).
