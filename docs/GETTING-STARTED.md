# Getting started

This page takes you from a clone to a dashboard. It lists every way the command line can run an evaluation, what each one writes, and how long it takes where that is known. How the pieces fit together is in [ARCHITECTURE.md](ARCHITECTURE.md). The reference for site profiles, pinning and the run rules is [RUNNING.md](RUNNING.md).

Every command is `python3 -m buffon <command>`. `python3 -m buffon --help` lists them, and each has its own `--help`.

## The one command

```sh
git clone <repository-url> buffon && cd buffon     # note: there is no public URL yet; use the one you were given
./buffon.sh up
```

That is the whole setup. On a terminal, bare `buffon up` opens a picker for the harnesses and benchmarks; `./buffon.sh up --yes` skips it and uses the flags and defaults. It looks at the machine, writes a site profile for it, installs five harnesses (Pi, PiG, Pi-Bolt, OpenCode 2 and Codex, pinned by checksum), runs a quick suite against the scripted mock model, builds the dashboard and opens it in your browser. On a machine with no display it prints the path of the site instead. It needs Python 3.11 or later, Node 18 or later for the dashboard, and, the first time, network access to download the pinned releases. Without Node 18+, `buffon up` stops at once; `buffon up --no-dashboard` runs without it and writes the report and a summary page. Nothing is installed outside Buffon's own folder (`~/.local/share/buffon`, or `$BUFFON_HOME`).

One line per step says what it is doing and how long it is expected to take on this machine. It ends with a summary: the harnesses and benchmarks that ran, the trust badge of the run and why, where the run directory and the site are, and the exact command that repeats it. Run `buffon up` again and it reuses the installed harnesses and the finished runs.

`./buffon.sh up` is the same as `python3 -m buffon up`.

## Choose what runs

```sh
./buffon.sh harnesses          # every harness: version, what it needs, installed or not
./buffon.sh benches            # every benchmark: what it measures, its state, expected time on this machine
./buffon.sh up --harness pig,pi,pi-bolt --bench standard
./buffon.sh up --bench streaming,long-session,memory --time-budget 20m
./buffon.sh up --harness all --bench full --isolation container
./buffon.sh up --bench standard --save mine.toml   # save the selection ...
./buffon.sh up mine.toml                           # ... and run it later
```

- `--harness` takes names (`pi`, `pig`, `pi-bolt`, or any id from `buffon harnesses`), globs (`pig-*`) or `all`. The default is Pi, PiG, Pi-Bolt, OpenCode 2 and Codex; omp runs only when named. A harness that speaks none of the chosen wire APIs (Codex speaks only the Responses API) adds its API to the run, and Pi is measured on it too.
- `--accept-terms claude-code,copilot` (or `BUFFON_ACCEPT_TERMS=claude-code,copilot`; also on `buffon run`) adds Claude Code and GitHub Copilot CLI. They are installed from their vendors at run time (npm, pinned and hash-checked; Buffon never ships them), run against the mock with dummy keys and no account, and are never in the default set, `all` or a glob. Without the flag, naming one fails and prints the vendor terms you would be accepting; `--save` stores the acceptance and raw.json records `operator_terms_accepted`. Example: `./buffon.sh up --harness pi,claude-code,copilot --accept-terms claude-code,copilot`.
- `--bench` takes a preset or a list of families and workloads. **quick** (the default) is start-up and one turn on one wire API. **standard** adds tool calls, RPC, streaming, a long session and fault recovery. **full** is every wired family with 12 rounds in every cell, which is what the Verified badge needs; it takes hours. No preset runs the faithfulness probes; ask for them with `--evals`.
- `--track common|pi|real-world|all` picks benchmarks by question instead of by name ([TRACKS.md](TRACKS.md)).
- `--evals faithfulness|faithfulness-smoke|none`, `--rounds N`, `--apis ...`, `--offline` (never download; everything must be installed already), `--isolation container` (each harness in its own container; needs docker or podman).
- `--time-budget 20m` fits the choice into a time: it lowers the rounds per cell first, then drops the evals, then the last benchmarks, and says what it dropped.
- On a terminal with no selection flags, `buffon up` asks: arrow keys and space tick harnesses and benchmarks, enter runs. Without raw key support it falls back to a numbered list.
- `buffon up --plan` prints the selection and the expected time and runs nothing.

## Fast by default

- A cell **stops adding rounds** as soon as its answer is clear: the difference is outside the noise floor and the paired test supports it, or the whole interval sits inside the floor, so the honest answer is "no measurable difference". Every cell keeps at least six rounds. Twelve rounds in every cell is only needed for the Verified badge (`--no-adaptive`).
- Installs, the report and the dashboard run side by side. Measured samples never do: one harness process at a time.
- The time shown next to each choice comes from a short probe of this machine, and from the times earlier runs here took.

## What the numbers are worth: the trust badge

Every measurement is recorded and shown. How far to trust it is a label on the run, never a reason to throw it away:

| badge | meaning |
|---|---|
| Verified | a dedicated host, every strict rule held, and the run was reproduced |
| Dedicated | a dedicated host (nothing else on the benchmark's cores), not yet reproduced |
| Shared | other work shares the benchmark's cores, SMT siblings are not reserved, or the clock cannot be fixed |
| Noisy | the host's noise (the reference arm against its own copy) is above 5%, or the host never went quiet |

The badge lists every reason. A laptop run is Shared; that is expected and fine for a first look. A verdict is "faster" or "slower" only when the difference clears the noise floor of this very run; otherwise it says "no measurable difference". Instruction counts lead where the machine exposes counters; otherwise CPU time does, and the run says which. See [METHODOLOGY.md](METHODOLOGY.md) section 18 and [HEALTH.md](HEALTH.md).

`buffon up --require-class A` keeps the old behaviour for people who want it: refuse on a noisy or shared host instead of labelling it.


## Choose your path

| I want to | Use | Needs | Writes |
|---|---|---|---|
| see the dashboard with no run at all | [the demo site](#4-the-demo-dashboard-no-run) | Python, Node | `site/` with invented numbers |
| check that one harness installs and talks to the mock | [`buffon arm verify`](#21-check-one-arm) | Python, network once | nothing but the cache |
| run a quick local test on my laptop | [`buffon run` with a macOS or local site](#22-a-local-run-one-suite) | Python, network once | a run directory |
| get numbers I can defend | [a Linux host with pinned CPUs](#23-a-site-profile-on-linux) | Linux, a quiet machine | a run directory labelled quiet dedicated hardware |
| run every arm in a container | [`--isolation container`](#24-macos-with-container-isolation) | Docker or Podman | a run directory with an envelope stamp |
| use a cluster | [Kubernetes](#25-kubernetes) | a cluster, `kubectl`, Go | one run directory per node |
| run a fixed plan on a cluster or a VPS | [`buffon campaign`](#27-campaigns) | as above | a campaign directory |
| measure again one cell of a published report | [`buffon rerun`](#29-rerun-one-cell) | the original run directory | `reproduction.md` |
| run another project's benchmark as it is | [`buffon external`](#210-other-projects-benchmarks) | a checkout of that project | a suite directory, never in a score |
| score how like Pi a harness behaves | [`buffon faithfulness`](#211-faithfulness) | Python, network once | `faithfulness.json` |
| add a harness | [CONTRIBUTING.md](../CONTRIBUTING.md#how-to-add-it) | a pinned release | an `arms/<name>/` directory |

## 1. Clone and prerequisites

The repository is private for now. Ask the owner for its URL.

```sh
git clone <repo-url> buffon
cd buffon
```

The runner is the Python standard library only. There is nothing to `pip install`.

| need | for | where it is checked |
|---|---|---|
| Python 3.11 or later | everything (`tomllib` is 3.11) | `.github/workflows/tests.yml` tests 3.11 and 3.13 |
| `git`, `tar`, `xz` | installing arms and runtimes | docs/RUNNING.md |
| network, once | filling the download cache; later runs can use `--offline` | `buffon/arms/install.py` |
| Node 18 or later on your `PATH` | **only** `buffon dashboard` (it renders formulas with the vendored KaTeX, `buffon/dashboard/mathtex.py`) | the arms use their own pinned Node |
| `docker` or `podman` | only `--isolation container` (`buffon/envelope/run.py:find_runtime`) | |
| `kubectl`, Go | only the Kubernetes backend (Go builds `buffon-cluster`, `buffon/backend/k8s.py:cluster_binary`) | |

Buffon never uses the Node or Go on your `PATH` to run or build an arm. It downloads the versions `runtimes.toml` pins, checks their sha256 and unpacks them into a throwaway directory. Downloads are kept in `$XDG_CACHE_HOME/buffon` (`~/.cache/buffon` by default; `buffon/site.py`).

| platform | what you get |
|---|---|
| Linux, one machine | full path: CPU pinning, cgroup v2 meter (with `systemd-run --user` or a delegated cgroup), `/proc` egress audit. A run can be labelled quiet dedicated hardware |
| macOS | no pinning, no cgroups, no `/proc`. The runner uses the `rusage` meter and `lsof` for the egress audit. Every output is labelled PROVISIONAL |
| Linux or macOS with Docker or Podman | `--isolation container` |
| Kubernetes | one pod per session, Guaranteed QoS, digest-pinned image or a bundle |

Check the host before you measure anything:

```sh
python3 -m buffon preflight                 # host class A (dedicated) or B (shared) and why
python3 -m buffon perfcheck                 # can this host count instructions? exit 0 yes, 3 no (CPU time is then the headline)
```

## 2. Ways to run an evaluation

Every run starts from a site profile. A profile names the backend (local or Kubernetes), the CPUs and the cache. Copy an example, then check it:

```sh
cp sites/example-local.toml sites/mine.toml          # or example-macos.toml, example-vps.toml, ...
python3 -m buffon site check mine                     # prints the parsed profile; exit 2 on any error
python3 -m buffon site schema                         # every key, its type and default (same text as sites/SCHEMA.md)
```

`sites/mine.toml` is yours and is not tracked. With no `--site` and no `BUFFON_SITE`, `buffon run` uses a local, unpinned site (`buffon/cli.py:cmd_run` help text).

### 2.1 Check one arm

When: before you spend time on a long run, or after adding a harness.

```sh
python3 -m buffon arm verify pi-node --site mine
```

It installs the arm into a fresh root, writes its config, starts it against the mock and runs `version`, `print`, `rpc` and `pty` once per wire API, then fails if it connected anywhere but the mock (`buffon/armverify.py`). It writes nothing but the download cache. Rough time: about 20 s for `pi-node` with a warm cache on macOS (see the end of this page).

`python3 -m buffon arms` lists every manifest, its version, relation and install form, and marks held arms and arms that need `--accept-terms`.

### 2.2 A local run, one suite

When: a first run, or a smoke test of any change. This is the path to try first.

```sh
python3 -m buffon run overhead --site mine --out runs/first
python3 -m buffon report runs/first
```

`overhead` is a family. You can also name a workload (`overhead/print`) or `all`. The workloads are:

| family | workloads |
|---|---|
| overhead | `version`, `print`, `print-tools`, `print-write`, `pty`, `rpc`, `print-ext5`, `rpc-ext5`, `print-ext10`, `rpc-ext10` |
| streaming | `print-` and `tui-` of `prose`, `code`, `tables`, `lists` |
| longsession | `grow-n`, `grow-n10`, `resume-n`, `resume-n10`, `resume-n-varied`, `resume-n10-varied` |
| devloop | `install`, `first-run`, `build` |
| reliability | `faults` (pass or fail cells, one driver of its own) |
| soak | `realistic`, `stress` (12 minutes each by default, `soak_minutes`) |

The list comes from `buffon/workloads/*.py`. What each one measures is in [WHAT-WE-MEASURE.md](WHAT-WE-MEASURE.md).

What the run does: it installs the selected arms (every runnable arm unless you pass `--arms`), runs the calibration, then runs interleaved rounds. It refuses (exit 3) when the site profile cannot be met (for example `pinning = "required"` on a host that cannot pin, or CPUs the machine does not have) or when the arms that must do the same work do not. A noisy calibration, fewer than 12 rounds, a scaling clock or a shared host do not stop it: the run is recorded and labelled (the trust badge above). `--require-class A` makes them refuse instead. See [RUNNING.md](RUNNING.md#what-the-runner-enforces).

Useful flags:

| flag | effect |
|---|---|
| `--arms A B ...` | only these arms (each still gets its A/A copy). Full ids or the short names `buffon up` takes (`pig`, `pi`, `pi-bolt`, ...); `run`, `session` and `arm verify` accept both |
| `--apis ...` | wire APIs: `openai-completions`, `anthropic-messages`, `openai-responses` |
| `--rounds N` | measured rounds (at least 12) |
| `--allow-short` | smoke runs with fewer rounds; the run says "not a measured run" and `buffon verify` lists the round count as a note |
| `--aa none` | no A/A copies (PROVISIONAL, and no noise floor) |
| `--offline` | `buffon session` only: never download, use the cache |
| `--param KEY=VALUE` | a workload parameter |

Writes: the run directory `runs/first/` with `raw.json`, `facts.json`, `host.json`, `mock-requests/`, and `MANIFEST.sha256` (the seal). `raw.json` is the only input of the report ([RAW-FORMAT.md](RAW-FORMAT.md)).

Time: it is the number of samples times the time of one. Samples are `(warm-up + rounds) x (workload, API) variants x (arms x 2)`. On macOS with `pi-node` a `print` or `version` sample took about 0.3 s. `pty`, `rpc`, streaming and long-session samples are longer [INFERENCE: not timed here], and a soak takes minutes by design. Add the 12-round calibration.

A cheap smoke run, the one used to check this page:

```sh
python3 -m buffon run overhead/version overhead/print --arms pi-node --apis openai-completions \
    --rounds 4 --allow-short --site mine --out runs/smoke
```

### 2.3 A site profile on Linux

When: you want numbers you can publish. Use a Linux host that is otherwise idle.

```sh
python3 -m buffon preflight --site sites/vps.toml        # class A, or the reasons it is not
python3 -m buffon run overhead --site sites/vps.toml --out runs/vps
```

`sites/example-vps.toml` is a 4-vCPU single machine: CPU 0 for the OS, CPU 1 for the runner and mock, CPUs 2 and 3 for the harness. `sites/example-local.toml` is the general case. Set `hardware = "dedicated"` only when nothing else runs on the harness cores. A run is labelled quiet dedicated hardware only when all seven conditions in [RUNNING.md](RUNNING.md#hardware-label) hold. Everything else is PROVISIONAL.

### 2.4 macOS with container isolation

When: you want every arm in the shared container envelope on a Mac. Docker on macOS runs in a VM, so the profile's `cpus` are the VM's CPU ids.

```sh
cp sites/example-macos-container.toml sites/mac-container.toml
python3 -m buffon run overhead --site mac-container --isolation container --out runs/mac-container
```

Size the VM with at least one CPU more than `cpus` names. The host still cannot pin its own runner and mock, so the run stays PROVISIONAL. Images are pinned by digest in `images/images.toml`. Details: [RUNNING.md](RUNNING.md#macos-with---isolation-container) and [ENVELOPE.md](ENVELOPE.md). Not run on the host this page was written on [INFERENCE: it needs a Docker VM sized for it].

### 2.5 Kubernetes

When: you have a cluster with a static CPU manager and want exclusive cores per session.

```sh
cp sites/example-kubernetes.toml sites/bench-pool.toml      # replace every <placeholder>
(cd cluster && go build -o buffon-cluster .)                 # or set BUFFON_CLUSTER_BIN
python3 -m buffon site check bench-pool
python3 -m buffon run overhead --site bench-pool --out runs/pod
```

One session is one pod. The image must be pinned by digest. With `nodes = [...]` or `spread = N` in the profile the same session runs on several nodes at once and `runs/pod/` holds one run directory per node. `buffon run` then prints the report command for each. Details and RBAC: [RUNNING.md](RUNNING.md#quick-start-kubernetes-backend) and `cluster/README.md`.

Time: one session is the same as a local run, plus pod start and the copy back. [INFERENCE]

Not run on this host: there is no cluster.

### 2.6 Bundle mode (Kubernetes without a registry or a network)

When: the nodes have no network, or you do not want to build an image.

Set `bundle = true` and `base_image` in the profile (`sites/example-cluster-bundle.toml`). `buffon run` then builds a bundle (the repo at HEAD, every pinned artifact, a prefilled npm cache, `buffon-cluster`, `ARTIFACTS.sha256`) in a temporary directory and `kubectl cp`s it into the pod. To build one yourself and reuse it:

```sh
python3 -m buffon.backend.bundle --out /tmp/bundle --arch amd64 --arms pi-node pig-0.4.1
python3 -m buffon run overhead --site bench-pool --bundle /tmp/bundle --out runs/pod
```

The bundle is built for the nodes' architecture (`arch`), not yours. A modified tracked file is refused unless you pass `--allow-dirty` to the builder. The same bundle can run a local site offline, through a campaign (2.7). Details: [RUNNING.md](RUNNING.md#bundle-mode). Not run on this host (needs network and Go for the build, and a cluster to use it).

### 2.7 Campaigns

When: you want a fixed plan of runs, written before the window opens, that resumes after an interruption. `campaigns/quiet-v1.toml` and `campaigns/ticket1.toml` are examples; `campaigns/launch-rerun.toml` is the launch rerun on one pinned machine ([RUNNING.md](RUNNING.md#the-launch-rerun)).

```sh
python3 -m buffon campaign campaigns/ticket1.toml --site bench-pool --out runs/ticket1 --dry-run   # prints the steps, contacts no cluster
python3 -m buffon campaign campaigns/ticket1.toml --site bench-pool --out runs/ticket1 --wait-cluster 7200 --parallel
```

On a Kubernetes site the steps are: `perfcheck`, `calibrate` (noise floor of the nodes), then one `buffon run --calibration ... --nodes A,B` per `[[family]]`, then `buffon verify` of every run directory. Run the same command again with the same `--out` to resume. On a local site (a VPS) there is no cross-node calibration and no reproduction node: the families run one after the other, each with its own A/A gate. A local site can run a campaign offline with `--bundle <dir>`.

Writes: `<out>/campaign.json` (the plan hash, each step's exit and verdicts, rewritten after every step), `<out>/perfcheck/`, `<out>/calibrate/calibration.json` (Kubernetes only), and `<out>/<family>/` per family. `buffon campaign` prints the `buffon report` command for each. Time: as long as the sum of its families.

### 2.8 Calibrate the nodes

When: before comparing results across Kubernetes nodes.

```sh
python3 -m buffon calibrate overhead --site bench-pool --out runs/cal
python3 -m buffon run overhead --site bench-pool --calibration runs/cal/calibration.json --out runs/compare
```

It runs only the reference arm against its A/A copy on every node, judges each node's coefficient of variation against `[kubernetes] max_cv` (default 0.05) and writes `calibration.json`. Exit 3 means the nodes are too noisy. `buffon run --calibration` then runs only on the nodes that passed. It only works on a Kubernetes site (`buffon/cli.py:cmd_calibrate`). A local session calibrates itself.

### 2.9 Rerun one cell

When: you want to check one number of a report on your machine.

```sh
python3 -m buffon rerun '<run id>::overhead/print@openai-completions#cpu_ms' --site mine
python3 -m buffon rerun '<cell id>' --site mine --print      # only print Buffon run command
```

The cell id is the last column of `report.md`, and also in `report.json` and `summary.csv`. The command finds the run directory under `results/`, `runs/` or `--runs-dir`, runs its plan for that workload and API, and compares. It refuses when your `arms.lock` is not the one the run used. Writes `reproduction.md` and `reproduction.json` in your run directory. Related: `buffon reproduce <run dir>` repeats a whole run, and `buffon compare <original> <yours>` compares two directories.

### 2.10 Other projects' benchmarks

When: you want an upstream project's own benchmark, run as it is, beside Buffon's results. Its numbers are never part of a Buffon cell or score ([EXTERNAL.md](EXTERNAL.md)).

```sh
python3 -m buffon external suites                                    # id, licence, live or offline, targets
python3 -m buffon external plan --suite pi-evals-offline --target pi-node --checkout <path to the upstream checkout>
python3 -m buffon external run  --suite pi-evals-offline --target pi-node --checkout <path> --out runs/ext
python3 -m buffon external import --family <family> --out runs/imported <published files...> --meta meta.json
python3 -m buffon report runs/first --external-suites runs/ext --external-results runs/imported
```

`run` refuses a checkout that is not at the suite's pinned commit, and refuses a suite that needs a real model unless you pass `--live`. It writes `external-suite.json` and the suite's output, never a `raw.json`.

### 2.11 Faithfulness

When: you want to know how closely a harness behaves like the pinned Pi release. It is graded and never gates by itself ([FAITHFULNESS.md](FAITHFULNESS.md)).

```sh
python3 -m buffon faithfulness run --arms pi-bun pibolt pig-0.4.1 --out faith/
python3 -m buffon faithfulness report faith/
python3 -m buffon report runs/first --faithfulness faith/
```

`run` also writes `faithfulness.md` and exits 4 on an egress violation. `faithfulness probes <pi --help text file>` lists the probes. Pass `--faithfulness` to `buffon report`, `buffon grade` or `buffon dashboard` to put the score beside each entry's grade.

### 2.12 Agent benchmarks

When: you want task pass rates with a real model and a verifier. Buffon does not call the model. It plans the protocol and computes the paired result from your observations ([AGENT-BENCHMARKS.md](AGENT-BENCHMARKS.md)).

```sh
python3 -m buffon agentbench plan protocol.json --out runs/ab
python3 -m buffon agentbench result protocol.json --observations observations.jsonl --out runs/ab
```

`protocol.json` has `benchmark`, `arms`, `cases`, `models`, `runs`, `seed`, `params`.

### 2.13 Verify and submit

```sh
python3 -m buffon health runs/first                     # the run notes: each check ok or note
python3 -m buffon health thresholds                     # the published thresholds table
python3 -m buffon verify runs/first --submission        # exactly what CI runs on a pull request (needs submission.toml)
```

To publish a run, start from a clean checkout, copy the run directory to `results/<id>/`, run `buffon index results`, commit both and open a pull request. The steps, the pull request template link and what CI checks are in [SUBMITTING.md](SUBMITTING.md). Do not run `buffon promote`: CI does it after the merge. `buffon verify` lists a run made with `--allow-short`, `--allow-noisy`, `--no-calibrate` or `--no-quiet-gate` as a note and never rejects it for that. It rejects integrity problems, a dirty runner checkout, a run made with `--no-telemetry`, and a run without its A/A copies.

### 2.14 Debugging helpers

```sh
python3 -m buffon mock                                  # serve the mock; prints its URL (a free port; --port is not used by cmd_mock)
python3 -m buffon sysinfo --cpus 2-3 --out host.json    # the platform specification of the given CPUs
python3 -m buffon lock --check                          # arms.lock matches the manifests
```

## 3. Report, grade and dashboard

```sh
python3 -m buffon report runs/first                          # report.md and the files below, next to the run
python3 -m buffon grade runs/first --out runs/first          # grade.json, leaderboard.md, report-card.md (also written by report)
python3 -m buffon dashboard runs/first --out site            # the static site
```

`buffon report DIR...` takes one or more run directories (several runs of one plan pool as more rounds). It writes `report.md`, `report.html`, `report.json`, `summary.csv`, `rounds.csv`, `noise.csv`, `telemetry.csv`, `health.json`, `plots/`, and the grade files `grade.json`, `leaderboard.md`, `report-card.md` (and their HTML). It takes a second or two for a run of this size.

`buffon grade` is optional. It recomputes the Pi Harness Score from `report.json` alone with other weights: `--profile cpu-heavy` or `--weights my.toml` ([GRADE.md](GRADE.md)).

`buffon dashboard DIR... --out site/` writes the static site ([design/DASHBOARD.md](design/DASHBOARD.md)). The output directory must be empty or written by an earlier `buffon dashboard` (it holds a `.buffon-dashboard` marker); anything else is refused (`buffon/dashboard/build.py:prepare`). The build needs Node 18 or later.

The site is one page with one data file: every view has its own link (`index.html#/?h=opencode,pibolt&m=overhead-print.cpu_ms&sort=overhead-print.cpu_ms:asc`), so a view can be bookmarked or shared. Open it from the folder, or serve it:

```sh
open site/index.html                    # macOS; xdg-open on Linux. file:// works
python3 -m http.server -d site 8000     # then browse http://127.0.0.1:8000/
```

## 4. The demo dashboard (no run)

`tools/pages_site.py` builds the site from every published run in `results/` that is not withdrawn, and from a synthetic demo run when `results/` holds none. That is the shortest real command:

```sh
python3 tools/pages_site.py /tmp/demo-site
```

It prints `pages: the dashboard of demo-run (4 harnesses, 19 cells) in /tmp/demo-site (DEMO)` and takes about 7 s. Every view marks the data as DEMO. The numbers are invented and the harness names are fictional (`tests/report_demo.py:demo_raw`, flagged `run.synthetic`). To build the same thing by hand:

```python
import sys; sys.path.insert(0, ".")
from tests.report_demo import demo_raw, demo_faithfulness_dir
from tests.telemetry_fixtures import write_dir
from buffon.dashboard import build
run = write_dir("/tmp/demo/run", demo_raw())
build.build([run], "/tmp/demo-site", faithfulness=[demo_faithfulness_dir("/tmp/demo/faith")])
```

## 5. Publish with GitHub Pages

The live site is served from the `gh-pages` branch: a static build of `buffon dashboard` over the published runs, committed there. `.github/workflows/pages.yml` is the other way to publish, by manual dispatch only: it sets up Python 3.12 and Node 22, runs `python3 tools/pages_site.py site` (every run in `results/index.json` that is not withdrawn, or the DEMO site when there is none), uploads `site/` and deploys it, which replaces whatever Pages served before. It needs Pages' source set to "GitHub Actions".

To publish a real run, follow [SUBMITTING.md](SUBMITTING.md): `buffon verify --submission`, copy the run directory to `results/<id>/`, `buffon index results`, commit, and open a pull request. CI promotes it after the merge.

## Verified on

Written on macOS 26 (darwin arm64), Python 3.12.13, Node 24.19.0, no Docker VM sized for the run, no cluster. Commit `02ab859` plus the dashboard rebuild that follows it. What was run, and what happened:

| command | outcome |
|---|---|
| `python3 -m buffon --help` and `--help` of every subcommand | printed, exit 0 |
| `buffon site schema`, `buffon site check example-macos`, `buffon health thresholds`, `buffon arms`, `buffon lock --check`, `buffon external suites`, `buffon faithfulness probes </dev/null` | ran as shown; `lock --check` printed `arms.lock ok` |
| `buffon preflight --site <macOS profile>`, `buffon perfcheck --site <macOS profile>` | ran; host class B on this laptop; `perfcheck` exit 3 (it reported that this host cannot count instructions, so CPU time is its headline; the 4-round smoke run did record `instructions` and `cycles` through the macOS sampler, `perf_scope` sampled) |
| `buffon arm verify pi-node --site <macOS profile>` | installed `pi-node`, 10 of 10 mode and API checks `ok`, 19 s |
| `buffon run overhead/version overhead/print --arms pi-node --apis openai-completions --rounds 4 --allow-short --site <macOS profile> --out /tmp/docs-run` | exit 0, 20 samples, hardware PROVISIONAL, calibration CV 2.66% (passed), 41 s including the install |
| `buffon report`, `buffon grade --out`, `buffon health`, `buffon verify`, `buffon dashboard /tmp/docs-run --out /tmp/docs-run-site` on that run | report, grade and dashboard written; `health` lists notes as expected for a 4-round smoke run; `verify` REJECTED it for a `report.html` id bug, since fixed (`buffon/submit/check.py:run_id_in`) |
| `buffon arm verify opencode` and `buffon run overhead/version overhead/print --arms pi-node opencode --rounds 4 --allow-short` (the CONTRIBUTING worked example) | verify 15 s, all `ok` except rpc (`cannot run`, as declared); run exit 0, 40 samples, 67 s; `buffon report` listed `opencode` with its manifest label; `buffon dashboard /tmp/smoke2 --out /tmp/real-site` built the site (2 harnesses, 16 cells), and every view opened in a browser with the macOS caveats on the instruction cells |
| `buffon campaign campaigns/ticket1.toml --site <macOS profile> --dry-run` | printed the five steps (perfcheck and four families) |
| `buffon rerun '<cell id>' --print --site ... --runs-dir /tmp` | printed the `buffon run` command |
| `buffon agentbench plan`, `buffon mock` | wrote `protocol.json` and `expected-runs.json`; the mock printed its URL |
| `python3 tools/pages_site.py /tmp/demo-site` and `python3 -m http.server -d /tmp/demo-site` | 80 pages, 7.1 MB, 6.6 s; `index.html` answered HTTP 200 |

Not run on this host: a Linux pinned run, `--isolation container`, Kubernetes (`run`, `calibrate`, `campaign` without `--dry-run`), bundle builds, `buffon external run`, `buffon faithfulness run`, `buffon index`, and the GitHub Pages workflow.

## Choose your path (advanced use)

| you want | go to |
|---|---|
| to understand what a family measures, and where it stops being informative | [WHAT-WE-MEASURE.md](WHAT-WE-MEASURE.md), [LIMITATIONS.md](LIMITATIONS.md) |
| a site profile of your own, pinned cores, a dedicated host | [RUNNING.md](RUNNING.md) (site profiles, hardware label, a dedicated VPS) |
| to run on a Kubernetes cluster, with bundles and campaigns | [RUNNING.md](RUNNING.md), Kubernetes backend |
| to repeat one cell of a published result | [RUNNING.md](RUNNING.md), "Read a result and rerun one cell" |
| the grade, and how it is computed | [GRADE.md](GRADE.md) |
| to submit a run | [SUBMITTING.md](SUBMITTING.md) |
| to add a harness | [CONTRIBUTING.md](../CONTRIBUTING.md) |
