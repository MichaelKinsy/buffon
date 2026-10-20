# Running Buffon

The quickest way in is `buffon up` ([GETTING-STARTED.md](GETTING-STARTED.md)): one command from a fresh clone to a running Buffon and an open dashboard. This page is the detail behind it: site profiles, hosts, clusters, bundles and campaigns.

Buffon runs on any Linux or macOS machine, or in a Kubernetes pod, from a fresh clone. Everything specific to a machine or a cluster is in a **site profile**, a flag, or an `BUFFON_*` environment variable. Nothing in the code, the arm manifests or the tests names a host, a user, a home directory, a core number or a cluster.

Before you read a number, read [WHAT-WE-MEASURE.md](WHAT-WE-MEASURE.md) for what each family measures and [LIMITATIONS.md](LIMITATIONS.md) for what a number cannot tell you.

## Prerequisites

| needed | for |
|---|---|
| Python 3.11 or later (standard library only) | the runner, the mock, the report |
| `git`, `tar`, `xz` | installing arms and the pinned runtimes |
| network access to the artifact hosts, once | downloading arms into the cache; after that `--offline` runs need none |
| Linux with cgroup v2 and `systemd-run --user`, or a delegated cgroup | the exact CPU and memory meter. Without them the runner uses the `rusage` meter and says so |
| Linux for CPU pinning (`sched_setaffinity`) | a macOS run cannot pin and is labelled PROVISIONAL |
| `/proc` (Linux) or `lsof` (macOS) | the egress audit. On macOS `lsof -nP -i` lists each tree's sockets every 100 ms (`egress.source = "lsof"` in `raw.json`). With neither the run has no audit, is labelled PROVISIONAL and `buffon verify` refuses it |

### macOS

macOS has no CPU pinning, no cgroups and no `/proc`. Use `sites/example-macos.toml`: `pinning = "none"` and no `cpus` (a `cpus` list with `pinning = "none"` is refused). The run uses the `rusage` meter, reads the process tree with `ps`, and every output is labelled PROVISIONAL. A site that names `cpus` with `pinning = "required"` is refused on macOS; with `pinning = "preferred"` the CPUs are ignored and the run says so. Run the tests with `python3 -m unittest discover -s tests -t .` only.

#### macOS with `--isolation container`

Docker on macOS runs in a virtual machine (Docker Desktop, colima, a Podman machine), so a cpuset names the VM's CPUs. With `--isolation container`, `cpus` in the site profile are those VM CPU ids: the runner passes them to `docker run --cpuset-cpus` (with `--cpus` equal to their number and `--cpuset-mems 0`), which pins inside the VM, and the local backend accepts `cpus` and `pinning = "required"` on macOS for that run only. Use `sites/example-macos-container.toml` and size the VM with at least one CPU more than `cpus` names. The macOS host still cannot pin its own processes (the runner, the mock), so every output is labelled PROVISIONAL and the run's reasons say why. CPU ids are not checked against the host's cores; the runtime refuses an id the VM lacks. Without `--isolation container`, `cpus` on macOS is still refused. The unix-socket mount to the mock depends on the VM's file sharing; a runtime that cannot bind-mount a host socket refuses the run at its first sample.

Node and Go come from `runtimes.toml`, pinned by sha256 and unpacked into the run's throwaway directory. Buffon never uses the Node or Go on the host's `PATH` to run an arm or to build one. Arm releases are pinned in `arms/<name>/arm.toml`; `arms.lock` is generated from them (`python3 -m buffon lock`).

## Quick start: local backend

```sh
git clone <repository> buffon && cd buffon
cp sites/example-local.toml sites/mine.toml      # edit: cpus, mock_cpus, hardware
python3 -m buffon site check mine                 # validates the profile
python3 -m buffon arm verify pi-node --site mine  # install one arm, run every mode once against the mock
python3 -m buffon run overhead --site mine --out runs/first
python3 -m buffon report runs/first
```

`buffon run` builds a session and hands it to the site's backend. The local backend starts `python3 -m buffon session ...` as a child process. The session installs the selected arms, runs the **calibration**, then measures interleaved rounds. A run is refused (exit code 3) only for what makes it impossible to measure: `pinning = "required"` that cannot be met, CPUs the machine does not give the runner, a work directory on tmpfs, another measurement holding the host lock. A noisy calibration, a pinned CPU that scales its clock, a shared host, fewer than 12 rounds and a host that never quiets down are not refusals: the run records every measurement and the trust badge says what counts against it (METHODOLOGY section 18). `--require-class A` restores the old refusals.

## Read a result and rerun one cell

`buffon report` writes `report.md`, `report.json`, `summary.csv` and the grade files next to the run. Each row of `report.md` is one metric of one workload and API, with its kind (wall, CPU, memory, size or wire) and its unit. The columns give the number of repetitions, the median of the reference and of the arm, their ratio with a 95% interval, the A/A floor and the spread. A ratio inside the A/A floor means "no measurable difference". Every row ends with a cell id.

To measure one cell again on your machine and compare it with the original:

```sh
python3 -m buffon rerun <cell id> --site mine
```

The command uses the arms, rounds, seed and parameters of the run that holds the cell. `--print` shows the `buffon run` command without running it. If your result differs, `reproduction.md` says whether your host was noisier than the original's and which comparisons agree. See [Provenance](#provenance-pins-cell-ids-and-rerunning-one-cell) for the details.

## Quick start: Kubernetes backend

```sh
cp sites/example-kubernetes.toml sites/bench-pool.toml   # edit every <placeholder>
python3 -m buffon site check bench-pool
python3 -m buffon run overhead --site bench-pool --out runs/pod
```

One session is one pod (a Job with one pod, `backoffLimit: 0`): requests equal limits and the CPU count is an integer, so the pod has Guaranteed QoS and a static CPU manager gives it exclusive cores. The pod runs a non-root, read-only-root container from an image **pinned by digest** (a tag is refused). The session inside the pod pins the quietest or the listed cores, refuses a node whose measured cores scale their clock (unless `allow_frequency_scaling`), records the node's facts, and writes the same run directory as a local run. The backend copies it back. Credentials reach a pod only through Kubernetes secret references named in the profile (`[kubernetes] secret_env`, each entry a variable name, a Secret in the namespace and a key, rendered as a `secretKeyRef`); a profile entry with a value is refused, and the session's environment is non-secret.

On Kubernetes the session's pod is its container envelope: isolation `pod-guaranteed` (docs/ENVELOPE.md, "The pod envelope"). The session checks that the pod has Guaranteed QoS with exclusive cores, an image pinned by digest, a read-only root, a non-root user and no network but the mock (each Job comes with a NetworkPolicy that allows no traffic, so the account needs `create` and `delete` on networkpolicies). It records the node, cpuset and QoS in every sample. A pod short of any of these is stamped "uncontained, not comparable", with the reasons. `--isolation none` asks for an uncontained run.

The cluster side is the Go module in `cluster/` (binary `buffon-cluster`), vendored from PiG's `bench/k8s` with its MIT header. Tests for it use a fake Kubernetes client, so `python3 -m unittest` and `go test ./cluster/...` need no cluster. A real run needs a cluster you configured in the profile; without one the Kubernetes tests that talk to a cluster are skipped with a message that says so.

### Several nodes and cross-node calibration

`[kubernetes] nodes` runs the same session at once on each listed node, one pod each; `spread = N` runs it on the N nodes with the most free CPU (of `nodes` when given). The run directory then holds one run directory per node, named after the node, with `spread.json` and the cluster's outcomes beside them; `buffon run` prints each node's exit and the report command over the node directories. The session fails when it fails on any node.

Each session still gates itself on the reference arm's A/A copy. Before a comparison across nodes, judge the nodes' own noise floor:

```sh
python3 -m buffon calibrate overhead --site bench-pool --out runs/cal          # the reference arm against its A/A copy on every node, 12 rounds or more
python3 -m buffon run overhead --site bench-pool --calibration runs/cal/calibration.json --out runs/compare
```

`buffon calibrate` runs only the reference arm (`--reference`, default `pi-node`) and its copy, without the in-session gate, then `buffon-cluster calibrate` judges the coefficient of variation of every metric the report scores (times, memory, bytes, CPU; not the host readings or the workload's own counts) per node against `[kubernetes] max_cv` (default 0.05) and writes `calibration.json`. A node with fewer than 12 samples per gated metric, or whose cores scale their clock, is not judged; a node above the gate is named noisy; the calibration fails (exit 3) when the median over the nodes is above it. `buffon run --calibration` runs on the nodes that passed on their own, says which it left out, and refuses with exit 3 before any pod starts when `buffon-cluster check` does not vouch for them.

### Bundle mode

A pod's root file system is read-only; only its scratch directory (`/data`, with `TMPDIR` and `HOME` under it) is writable. The session keeps its host lock, its workspace and its caches there: the lock is `$BUFFON_LOCK_FILE`, else `/run/lock` or `/var/tmp` when they are writable, else `$TMPDIR/buffon.lock`. A site's `kubeconfig` path may start with `~` or contain `$VARs`; `buffon-cluster` expands them (it never reads the file).

With `[kubernetes] bundle = true` the pod runs the digest-pinned `base_image` (Python 3.11 or later, `sh`, `tar`, `sha256sum`) and the runner copies a **bundle** into it with `kubectl cp` instead of pulling a Buffon image. A bundle lets the session run with no network. `buffon run` builds the bundle for `[kubernetes] arch` (`amd64` or `arm64`, the nodes' architecture) in a temporary directory before the pod starts, hands it to the backend, and removes it when the session ends. Downloads for this machine's own Node and Go (which prefill the npm cache and build `buffon-cluster`) go to `[local] cache_dir`. To build or inspect one by hand:

```sh
python3 -m buffon.backend.bundle --out <dir> --arch amd64 --arms pi-node pig-0.4.1
```

The bundle carries the arms the session runs: the ones named with `--arms`, else every arm that runs by default. An arm the bundle cannot carry is reported with its reason; without `--arms` it is left out of the session, and a named one is refused before any pod starts. `buffon run --bundle <dir>` and `buffon calibrate --bundle <dir>` use a bundle built beforehand (it must be built for the site's `arch` and carry every named arm) and keep it afterwards.

It holds the repository's tracked files at HEAD (a modified tracked file is refused), `cache/` with every pinned artifact and runtime the selected arms need for `linux-<arch>`, `npm-cache/` prefilled for each npm arm with `npm ci --ignore-scripts` resolved for `linux-<arch>`, `bin/buffon-cluster` built with the pinned Go runtime, and `ARTIFACTS.sha256` over every file. `buffon-cluster` checks the list before it sends the bundle, the pod checks it again after unpacking, and a pod on a node of another architecture refuses to start. In a bundle pod the backend runs the session with `--offline --cache-dir {root}/cache --npm-cache {root}/npm-cache`, so an npm arm (`pi-node`, for example) installs with `npm ci --offline` from the bundle's prefilled cache.

A source arm whose toolchain is Go with `CGO_ENABLED=0` (`pig-tip` and the other Go ports) is built on this machine, at its pinned commit and tree, with the pinned Go, for `linux-<arch>`, into `cache/source/<arm>/<commit>/linux-<arch>/` with a `record.json` (commit, tree, build command, its environment, toolchain, platform, the binary's sha256). The builder needs the arm's repository as for a local run (`BUFFON_SOURCE_REPO_<ARM>` or the manifest's `repo_url`) and network for its Go modules. Offline, the pod installs that binary after checking its record against the manifest and its sha256; it never clones or builds. Its install method reads "source build (cross-built into the bundle)". Other source arms and derived arms (they prepare from their base's source checkout, which a bundle does not carry) are reported as skipped.

`bundle.json` names Buffon commit and tree the bundle was built from, and whether that checkout had uncommitted changes (`dirty`, with `diff_sha256`; only `--allow-dirty` builds such a bundle). A session in a bundle pod has no `.git`, so it records that commit and tree as the runner's, checks the checkout's files against `ARTIFACTS.sha256` (the run is dirty when the bundle was built dirty, or a file differs or is missing), and adds `runner.bundle_sha256` to raw.json (docs/RAW-FORMAT.md).

### Campaigns

A campaign is the whole measured part of a cluster window, written down as a plan file before the window opens, so that it starts as soon as the cluster answers. `campaigns/quiet-v1.toml` is the quiet cluster run.

```sh
python3 -m buffon campaign campaigns/quiet-v1.toml --site bench-pool --out runs/quiet-v1 --dry-run          # check the plan, the site and the bundle; print the steps
python3 -m buffon.backend.bundle --out runs/quiet-v1/bundle --arch amd64 --arms pi-node pi-bun pibolt pig-tip pig-0.4.1 rpi   # optional: build the bundle before the window
python3 -m buffon campaign campaigns/quiet-v1.toml --site bench-pool --out runs/quiet-v1 --wait-cluster 7200 --parallel
```

`buffon run --calibration FILE --nodes A,B` runs one session on the named calibrated nodes only; a node the calibration does not vouch for is refused (exit 3).

The campaign (1) checks the plan and the site, and on a bundle site builds the bundle for every arm of the plan once into `<out>/bundle` (or uses `--bundle <dir>`, or a finished `<out>/bundle`); (2) with `--wait-cluster SECONDS`, asks the cluster which nodes can take a session pod (`buffon-cluster nodes`) every 30 seconds until it answers, and exits 3 without starting a pod when it does not; (3) runs `buffon calibrate` on the plan's `[calibrate]` workloads into `<out>/calibrate`, and stops when the calibration does not pass; (4) runs each `[[family]]` as its own `buffon run --calibration <out>/calibrate/calibration.json --nodes A,B` into `<out>/<family>`: one session with every arm and A/A copy on node A, and the same session on node B as its reproduction (`<out>/<family>/A/`, `<out>/<family>/B/`); B is a calibrated node with another CPU model when one is free; (5) runs `buffon verify` on every run directory a family left and `buffon compare` on the pair, written to `<out>/<family>/reproduction.md`. A comparison is a headline only when it reproduces on both nodes (docs/METHODOLOGY.md, "On a cluster"). Families run one after the other; with `--parallel`, as many run at once as there are free node pairs, never two sessions on one node, each family's output in `<out>/<family>.log`. With one calibrated node a family runs on that node alone and no comparison is a headline. A family whose session fails or whose run directories `buffon verify` rejects counts as not finished; the other families still run, and the campaign exits with the first failure. `<out>/campaign.json` records the plan's sha256, the bundle (commit, tree, arms, sha256 of its `ARTIFACTS.sha256`) and each step's argv, times, exit, verdicts, nodes (node, CPU model, CPU set, QoS class, CPU manager policy, the node's calibration noise) and reproduction totals. At the end the campaign prints one `buffon report` command per node run. Running the same command again resumes: a step that finished with exit 0 is not run again, and a family's unfinished attempt is moved to `<out>/<family>.attempt-<k>` before it runs again, so each attempt is verified on what it wrote itself. A campaign directory belongs to one plan and, once a step has run, to one bundle: another plan, or another bundle (a different `ARTIFACTS.sha256`), is refused.

A plan file has three parts; every key not listed is refused:

| table | keys |
|---|---|
| `[campaign]` | `name` (lower-case letters, digits and dashes), `reference` (default `pi-node`), `description` |
| `[calibrate]` | `workloads`, `rounds` (12 or more), `apis`, `params` |
| `[[family]]` | `name` (as above; not `bundle` or `calibrate`), `workloads`, `arms`, `rounds` (12 or more, or 3 or more with `allow_short`), `apis`, `params`, `warmup`, `timeout`, `adaptive` (`true`: a cell stops once its answer is clear, and `rounds` is the most it takes; docs/METHODOLOGY.md section 18), `allow_short` (`true`: 3 or more rounds are accepted and the run is labelled not a measured run; the minimal first run of the durable family and its build-up workloads use it) |

Workloads are ids, families or `all`; arms must exist and must not be held; `params` are passed as `--param KEY=VALUE`.

#### Several sessions at once on one big host (slots)

A local site runs one measured session at a time, so a 48 or 128 core machine uses about 8 cores. `[local] slots = N` (opt-in, default 1) lets a campaign run N sessions at once on disjoint core sets of that host. `cpus` and `mock_cpus` then give the size of one slot (a session of 8 harness CPUs and 2 mock CPUs is a slot of that size), and `pinning` must be `required`. Linux only: the split reads `/sys/devices/system/cpu/cpuN/topology`.

```toml
[site]
backend = "local"
hardware = "dedicated"
[local]
pinning = "required"
cpus = "8-15"        # one slot's harness CPUs: 8 (4 whole cores with 2-way SMT)
mock_cpus = "6-7"    # one slot's mock CPUs: 2 (1 core)
slots = 4
```

```sh
python3 -m buffon campaign plan.toml --site big-host --out runs/big --dry-run   # prints the slots (CPUs and NUMA node of each) and the plan; runs nothing
python3 -m buffon campaign plan.toml --site big-host --out runs/big
```

The campaign runs the perf check, then the slot calibration (`slots-calibration.json`), then the families at once, one per slot that passed, each as `buffon run --slot N --slot-calibration <out>/slots-calibration.json` with its own lock file. A slot that fails the calibration is not used; with no passing slot the families run one after the other on the site's own `cpus`, and the campaign says so. `campaign.json` records `slots` (id, CPUs, mock CPUs) and the slot of each family. A slot can be run by hand: `buffon run overhead --site big-host --slot 2`; without a passing calibration the run is labelled slotted (METHODOLOGY section 5, "Slots on one big host").

### The launch rerun

`campaigns/launch-rerun.toml` measures the launch numbers again on one pinned Linux machine (class A), for example after a PiG fix. It is one command:

```sh
export BUFFON_ACCEPT_TERMS=claude-code,copilot      # their vendors' terms: read them with `python3 -m buffon harnesses`
python3 -m buffon campaign campaigns/launch-rerun.toml --site <your site profile> --out runs/launch-rerun
```

Add `--dry-run` first: it prints every step as the `buffon run` command it will start, the vendor terms still to accept, and an expected measuring time per family and in all. It measures nothing. Run the same command again after an interruption and the families that finished are not run again.

The plan has four families, each its own `buffon run` with an A/A copy of every harness. The core family takes 12 rounds. The focus families are adaptive (`adaptive = true`): a cell stops once its answer is clear, after at least the rounds Holm needs for the compared harnesses (8 for four), and takes 12 at most. Pi on Node and Bun take tens of seconds per sample on the 200 KB write and the 60,000-character answer, and a 100-fold gap is clear well before round 12.

| family | harnesses | workloads | wire APIs |
|---|---|---|---|
| `core` | pi-node, pi-bun, pibolt, pig-tip, pig-0.4.1, rpi, octet, opencode-v2, codex, claude-code, copilot | `overhead/version`, `print`, `print-tools`, `rpc` | Chat Completions and Messages; Responses too for Codex, which speaks nothing else |
| `focus-overhead` | pi-node, pi-bun, pig-tip, pig-0.4.1, pibolt | `overhead/pty`, `print-ext5`, `rpc-ext5`, `print-ext10`, `rpc-ext10`, `print-write` | Chat Completions |
| `focus-streaming` | the same five | `streaming/tui-prose`, `streaming/print-prose`, at 6,000 and 60,000 characters | Chat Completions |
| `focus-longsession` | the same five | `longsession/resume-n` and its varied twin `resume-n-varied` | Chat Completions |

A harness with no mode for a workload (Codex has no RPC) shows "cannot run" in that cell. The estimate counts every harness in every workload of its family at its most rounds, so it is an upper bound, and it uses the speed probe of the machine it runs on: on a busy machine the probe is slow and the estimate is long. Time per sample comes from earlier runs on the same machine when there are any. From the benchmark host timings of 2026-10-16 (core 18 minutes for nine harnesses, the 200 KB write about an hour at 12 rounds) the plan takes about 2 to 2.5 hours on a quiet benchmark host, and about 3.5 to 4 hours if every focus cell needed all 12 rounds. `buffon up --plan` cannot print it, because `buffon up` runs one harness list for all its workloads and this plan gives the focus workloads to five harnesses only.

With print-mode streaming unpaced (WHAT-WE-MEASURE, "Streaming render"), the plan takes about 1.5 hours on a quiet benchmark host. On a host with two sockets, a site with `[local] slots = 2` puts one slot on each socket, and the campaign runs two families at once after the slot calibration (the reference against its A/A copy alone, then in both slots at once). That brings it to about 1 to 1.25 hours, and with no passing slot it runs the families one after the other. Both sockets must be free and set up for measuring (governor, fixed clock, idle states, counters) for the run.

### The durable family

The `durable` workloads measure durable agent runtimes: Pi Durable 1.3.0 (the reference, `pi-durable`) and PiG Durable (native Go, `pig-durable`) on their native SQLite. Each arm is a runtime package plus a small adapter that speaks the protocol of [DURABLE-ADAPTERS.md](DURABLE-ADAPTERS.md); the design and what is built are in [design/DURABLE.md](design/DURABLE.md) (section 11). A durable run selects the adapter arms and `pi-durable` as the reference by itself:

```sh
export BUFFON_SOURCE_REPO_PIG_TIP=/path/to/PiG-clone        # the repository that holds the pinned PiG commit (or a URL)
python3 -m buffon run durable/compat-1000 durable/compat-3500 durable/mixed-1000 durable/mixed-3500 durable/floor-host durable/floor-sql durable/crash-50 \
    --rounds 6 --allow-short --out runs/durable-minimal          # the minimal first run (docs/design/DURABLE.md section 10): provisional
python3 -m buffon run durable --out runs/durable-full           # every durable workload, 12 rounds, A/A copies
python3 -m buffon report runs/durable-full                      # or: python3 -m buffon dashboard runs/durable-full --out site
```

`campaigns/durable-native.toml` holds the same plan as a campaign: the first family is the minimal run, the others are the full session. A local site runs one family per `buffon run`; a Kubernetes bundle does not carry the Go adapter yet.

What happens before the first sample: the runtimes are installed (Node and the esbuild bundle of the Pi adapter from the committed lock; the PiG checkout at its pinned commit and tree with the adapter built into it); each fixture the plan needs is built once by the reference through its real loop and kept under the site's cache directory (`durable/`, keyed by the script's sha256, the settings and the writer); every arm runs the equivalence scenarios on a copy of each fixture, and the runner compares the stores it reads itself. A difference in conversation state, model requests or cross-open refuses the run (exit 3) and `equivalence.json` in the run directory says which fields differ. A fixture the reference cannot build, or one where the reference disagrees with its own A/A copy, is not timed: its workloads are skipped with that reason. A capability an arm lacks is that adapter's own sentence in the cell's `cannot run` reason.

Parameters (`--param KEY=VALUE`): `crash_points` (default 20: kill points per crash workload, spaced from the first commit of the turn to the last, or `all`). `--envs native` is the only environment today; `miniflare` and `cloudflare` are refused. The crash workloads run once, not in rounds. The cold-start method is a warm page cache: every sample's store is a fresh copy that the runner reads once before timing.

Time: a fixture of 3,500 turns takes the reference minutes to build the first time (a 10,000-turn compat fixture about twenty minutes) and is reused afterwards; a measured sample takes seconds. The minimal first run is about one hour on a quiet host. On a shared machine every durable run is labelled PROVISIONAL like any other.

## Site profile reference

`sites/SCHEMA.md` is the complete, generated schema (`python3 -m buffon site schema`). A profile is a TOML file at any path, or a name resolved to `sites/<name>.toml`. Select it with `--site`, or with `BUFFON_SITE`. Unknown keys, wrong types, placeholders (`<...>`), overlapping `cpus` and `mock_cpus`, and a Kubernetes image without a digest are errors at start.

```toml
[site]
name = "my-workstation"
backend = "local"            # local | kubernetes
hardware = "shared"          # dedicated | shared: a claim, checked against detection

[local]
cpus = "2-5"                 # harness CPUs
mock_cpus = "1"              # runner and mock CPUs, not overlapping cpus
pinning = "preferred"        # required | preferred | none
cache_dir = "~/.cache/buffon"
work_dir = "/var/tmp"
```

Environment overrides: `BUFFON_SITE`, `BUFFON_CPUS`, `BUFFON_MOCK_CPUS`, `BUFFON_CACHE_DIR`, `BUFFON_WORK_DIR`, and `BUFFON_K8S_<KEY>` for each `[kubernetes]` key. A source-built arm takes its repository from `BUFFON_SOURCE_REPO_<ARM>` (for `pig-tip`: `BUFFON_SOURCE_REPO_PIG_TIP`), a URL or a local clone; the manifest pins only the commit and its tree.

Pinning on a local machine: with `cpus` set, every harness process (and its children) is pinned by `sched_setaffinity` before exec, the runner and mock are pinned to `mock_cpus`, and no runtime tuning is set: a Go arm keeps its own GOMAXPROCS default (Buffon sets none for any arm; an arm's manifest `[env]` may, and the run records it). With no `cpus` the run is unpinned and labelled PROVISIONAL; with `pinning = "required"` it is refused.

## What the runner enforces

| rule | how |
|---|---|
| interleaved rounds | each round runs every variant once; the arm order rotates each round |
| A/A copy of every arm | `<id>-b`: the same executable, run as its own arm in the same rounds (`--aa none` or a list changes it; the report then has no floor for the arms without a copy, and the run is PROVISIONAL) |
| at least 12 measured rounds for a headline | fewer rounds are recorded and labelled "not a measured run"; they cannot be Verified. `--adaptive` stops a cell early once its answer is clear (METHODOLOGY section 18). `--require-class A` refuses fewer than 12 |
| warm-up excluded | `--warmup` rounds (default 1) are kept in the raw data and dropped from statistics |
| fresh process per sample | each sample starts a new process in a new HOME and work directory, with the operator's environment scrubbed and `PATH` set to the arm's pinned runtime and `/usr/bin:/bin` only (the operator's `PATH` would change which helper programs, such as `fd` and `rg`, a harness finds) |
| calibration before measuring | the reference arm (`--reference`, default `pi-node`; the first arm that can print when it is not selected) against its A/A copy for 12 runs; the CV of its CPU time above 5% labels the run **Noisy** (every sample is still recorded and reported); with `--require-class A` it refuses the run instead |
| egress | the sockets of every harness tree are sampled every 25 ms; any connection to a non-loopback address fails the sample and the run (exit code 4) |
| facts | `facts.json`: CPU model, flags, cores, pinning, governors, SMT, kernel, cgroup limits, load and idle before and after, throttling |
| digests | `arms.lock` sha256, every executable's sha256 and a digest of its whole installed tree (both re-checked after the run), the artifact sha256, the source tree for built arms, the runner's commit and tree, and the sha256 of its uncommitted diff when the checkout is dirty |
| raw samples | `raw.json` keeps every sample, failures included (docs/RAW-FORMAT.md) |

### Hardware label

A run is labelled quiet dedicated hardware only when all of these hold; otherwise it is **PROVISIONAL** in every output and `hardware.reasons` lists what failed:

1. the site profile claims `hardware = "dedicated"`;
2. the harness is pinned (a local CPU list, or a pod whose cpuset is exactly the requested exclusive CPUs);
3. every pinned CPU has a fixed clock (governor `performance` or min = max frequency); an unknown clock policy fails this on a local machine;
4. the pinned CPUs and their SMT siblings were idle (3% busy or less) before and after the run, outside the runner's own processes;
5. no CFS throttling happened;
6. the calibration gate passed, and there were at least 12 measured rounds;
7. every arm has its A/A copy, the egress audit ran, and the runner's checkout had no uncommitted changes.

## Provenance: pins, cell ids and rerunning one cell

- **Pins.** Every arm is pinned by exact version, the source or archive it came from, its checksum(s) and how it was built (`arms/<arm>/arm.toml`, `arms.lock`). The report's Provenance section prints each pin in full as the run recorded it; a field the run did not record says "not recorded".
- **Cell ids.** Every cell of a report has an id, `<run id>::<workload>@<api>#<metric>` (the run directory's name, the workload, the wire API or `-`, the metric). The ids are in report.md ("Cell ids and rerun commands"), report.json (`cells[].id`, `cells[].rerun`) and summary.csv (`cell_id`, `rerun`).
- **Rerun one cell.** `python3 -m buffon rerun <cell id> --site <your site profile>` repeats the plan of the run that holds the cell (its arms, rounds, warm-up, A/A copies, seed and parameters) for that workload and API only, then compares your result with the original (`reproduction.md`). It finds the run directory under `results/`, `runs/` or a `--runs-dir`. It refuses when this checkout's `arms.lock` is not the one the run used. `--print` shows the `buffon run` command without running it.
- **Raw samples.** raw.json of every run ships with its results; it is the only input of the report.
- **Generated only.** `buffon verify` regenerates the report from raw.json and compares report.json, summary.csv, report.md, grade.json, leaderboard.md and report-card.md with the files next to the run (cell ids renamed to the directory's name). Any difference rejects the run ("a generated file was edited"). Nothing in a generated file switches the check off: a report made with `--drop-flagged` is regenerated with it (the flags are in raw.json), one made with `--faithfulness` is regenerated from the faithfulness scores and correctness failures report.json records (`buffon faithfulness` checks those values), and the External sections are cut from report.md before the comparison.

## A dedicated VPS

One dedicated virtual machine can be the judged site: no cluster, no second node. `sites/example-vps.toml` is the profile (4 vCPUs: CPU 0 for the operating system, CPU 1 for the mock and the runner, CPUs 2-3 for the harness). It claims `hardware = "dedicated"` and `host_claim = "A"`, and `clock_claim = "hypervisor"`: a VM shows no cpufreq or turbo interface, so the runner cannot read the clock policy, and only the site can say that the platform fixes it. The claim is not verified, is stated in the report header (`run N clock`) and is recorded in `run.clock_claim`; it is honoured only when the machine shows it is a virtual machine (the CPU's `hypervisor` flag, or `systemd-detect-virt` naming one), and otherwise `run.clock_claim_refused` says why; a governor the machine does show, and a readable turbo state, still count. Without the claim an unreadable clock keeps every run out of class A.

The run needs nothing from the network: build a bundle on another machine (`python3 -m buffon.backend.bundle --out <dir> --arch amd64 --arms ...`), copy the directory to the VPS, and from inside it:

```
python3 -m buffon preflight --site sites/vps.toml                      # class A, or the reasons it is not
python3 -m buffon campaign campaigns/ticket1.toml --site sites/vps.toml --bundle . --out runs/ticket1
```

On a local site the campaign runs the perf check, then each family one after the other (`buffon run ... --offline --cache-dir <bundle>/cache --npm-cache <bundle>/npm-cache`), every one with its own A/A gate; there is no calibration across nodes and no reproduction node, so a second boot or another machine is needed before a comparison is a headline (docs/METHODOLOGY.md). Binaries run from the bundle's cache on disk. Peak resident memory of the four ticket arms over every workload is under 400 MiB, so a 3 GB machine is enough.

## Telemetry, health and submission

Every sample is recorded with telemetry (docs/TELEMETRY.md); `buffon report` writes report.md, report.html, report.json, rounds.csv, noise.csv, telemetry.csv, health.json and plots/, lists the run notes (docs/HEALTH.md) and takes `--drop-flagged`. `buffon health DIR...` prints the notes; `buffon verify DIR [--submission]` re-validates a run directory as CI does. To publish, you run `buffon verify --submission` and `buffon index results` and open a pull request; CI runs `buffon promote` after the merge. `buffon reproduce` and `buffon compare` check a published run (docs/SUBMITTING.md).

### Telemetry cost

The collector's own thread CPU time is recorded in every sample. To check that it does not move a measurement, run the same plan three times on the same quiet host (`--telemetry-interval 0.25`, the default; `--telemetry-interval 0`; `--no-telemetry`), in alternating order, with at least 12 rounds, and compare them with `buffon compare <a> <b>`: the A/A floors and the ratios must agree within the floor. The first such experiment on a quiet host is still to be done (the 2026-10-12 run was on a loaded host).

## Exit codes

`0` success; `1` a check rejected its input or a command failed; `2` usage, input or site-profile error; `3` refused before measuring; `4` an egress violation.
