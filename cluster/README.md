# cluster: Buffon on Kubernetes

`buffon-cluster` runs Buffon sessions on Kubernetes. One pod runs one whole Buffon session: every arm, every A/A copy and every round, interleaved by Buffon's own runner, as one process on pinned cores. Spread comes from running the same session on several nodes. Each node is reported on its own, and the nodes are combined by the median, behind a calibration gate on the coefficient of variation (CV).

The Python runner reaches it through the `k8s` backend: it writes a session spec and calls `buffon-cluster run`. This directory is a Go module with no dependencies outside the standard library.

Provenance: vendored from PiG's `bench/k8s` (MIT; see NOTICE). Only the generic parts were kept: Job rendering, kubectl client, node ranking, in-pod session, pinning, governor refusal, node facts and the calibration gate. Every file keeps an MIT SPDX header.

## Requirements of the cluster

| requirement | why | how buffon-cluster handles it |
|---|---|---|
| Guaranteed QoS | requests equal limits with an integer CPU count, so a static CPU manager can give the pod exclusive cores | the Job always renders `requests == limits` from the site's `cpus` and `memory` |
| exclusive cores (recommended) | neighbours on shared cores move wall times | with the static CPU manager policy the pod gets exactly `cpus` cores; otherwise the session pins the quietest allowed cores (from two `/proc/stat` readings 1 s apart) and records `cpuSet: shared` |
| fixed CPU clock | a CPU time measured in nanoseconds follows the clock when a governor (schedutil, ondemand, powersave, …) scales it | the pod refuses cores whose cpufreq governor is not absent or `performance`; `allowFrequencyScaling` runs such a session, but it is never judged |
| a dedicated pool (recommended) | fewer neighbours | `nodeSelector` and `tolerations` in the site profile |
| no network but the mock | the pod-guaranteed envelope (docs/ENVELOPE.md, P5) | each Job comes with a NetworkPolicy of its name that selects only its pod and allows no traffic in or out; it is deleted with the Job. The session checks that the cluster enforces it (a CNI without NetworkPolicy support leaves the run uncontained) |
| RBAC | the runner needs `create`, `get`, `list`, `delete` on jobs, pods and networkpolicies, `get` on pods/log, and `create` on pods/exec (kubectl cp) in the namespace | `-pick-node` and `-spread` also read nodes and pods cluster-wide when allowed. Otherwise they fall back to the namespace's own pods, or to the candidates given with `-nodes` |

## Site profile

Everything cluster-specific comes from a site profile, then `BUFFON_K8S_*` variables, then flags. `site.example.json` lists every field with placeholders, and it refuses to run as it is. Keep the real profile in the gitignored `cluster/site.local.json`, or point `BUFFON_K8S_SITE` at it. No code, test or document names a real cluster, namespace or host; `TestCommittedFilesNameNoHostOrCluster` checks that.

Secrets reach the pod only as Kubernetes Secret references: `secretEnv: [{name, secret, key}]` renders `valueFrom.secretKeyRef`. The session's own `env` is for non-secret values only.

Delivery is one of two:
- `image`: an image holding Buffon at `/opt/buffon`, pinned by digest.
- `bundle`: a local directory that the runner packs and copies with `kubectl cp` into a `baseImage` pod. The base image must have python3, coreutils and util-linux, and be pinned by digest.

  A bundle carries `ARTIFACTS.sha256` (`<sha256>  <relative path>` lines), which must list `bin/buffon-cluster` for the node's architecture. The pod checks the archive's sha256 and every listed file before it starts.

## Session spec

```json
{"run": "buffon-overhead-20261011t120000", "argv": ["python3", "-m", "buffon", "overhead", "--out", "{out}"],
 "env": {"BUFFON_SEED": "20261009"}, "cpus": 2, "pin": "auto", "timeoutSeconds": 21600}
```

- `{root}` becomes Buffon root, `{out}` the directory the session writes its run directory to, and `{cpus}` the pinned CPU list.
- The pod sets `BUFFON_OUT`, `BUFFON_PINNED_CPUS` and `GOMAXPROCS` (the number of measured cores). It runs `argv` under `taskset`, reads the cgroup's `cpu.stat` and the cores' clock around it, and writes `cluster-facts.json`.
  - `cluster-facts.json` holds: kernel, CPU model and vector features, cpuset (`exclusive` or `shared`), `cpu.max`, `memory.max`, governors, pin method, throttling, MHz, exit code, and the image or bundle sha256.
- It packs `{out}` and announces its sha256, then waits for the runner. The runner copies the archive out, checks it, unpacks it into `<out>/<run>/`, and leaves the marker that lets the pod exit.
- A failed or refused session still hands back its facts and partial output.

## Commands

```sh
cd cluster && go build -o buffon-cluster .
export BUFFON_K8S_SITE=$PWD/site.local.json
./buffon-cluster render -session session.json                       # manifests only, no cluster contact
./buffon-cluster nodes -n 3                                          # ranking by allocatable minus requests
./buffon-cluster run -session session.json -out ../runs              # one node (the site's, or the scheduler's)
./buffon-cluster run -session session.json -out ../runs -spread 3    # the 3 nodes with the most free CPU
./buffon-cluster calibrate -o ../runs/calibration.json ../runs/<run>/<run>-n*   # A/A sessions, 12+ rounds
./buffon-cluster check -calibration ../runs/calibration.json -nodes a,b         # before a comparison
```

Exit codes: 0 ok, 1 error, 2 usage, 3 noise refusal.

## Calibration

A calibration session runs the reference arm against its A/A copy for at least 12 rounds on each node.

- `calibrate` reads each run directory's `raw.json` samples and `cluster-facts.json`. For every (scenario, wire API, arm, metric) it computes the CV per node and the median CV over the nodes. As in Buffon's statistics (docs/RAW-FORMAT.md), warm-up samples are dropped and each wire API is its own series.
- A failed sample is not a statistic: it is counted per (scenario, wire API, arm) in the node's `failed` and printed, never dropped silently. A session that exited non-zero fails the calibration as a whole: it did not finish, and the calibration cannot vouch for it.
- It reads the metrics Buffon's report scores (times, memory, bytes, CPU; buffon/report/cells.py `scored`); the host readings and the workload's own counts in a sample are not judged.
- `-gate auto` judges every such metric on exclusive cores, and only the CPU metrics on shared cores, where wall times are reported as information. `all` and `cpu` force either set.
- It passes when the median CV of every gated metric is within `maxCv` (default 0.05).
- Each node gets its own verdict, so a node that is noisy on its own is named even when the median passes, and `check` refuses a comparison on it.
- Fewer than 12 samples, or cores whose clock scales, make a smoke test: it is reported, not judged, and `check` refuses it.

## Tests

`go test ./...` needs no cluster. A fake kube client stands in for kubectl (`kube_test.go`): apply, pod status, bundle copy-in, result copy-out with its sha256 check, the release marker, and Job deletion. A fake `/proc` and `/sys` (`pod_test.go`) covers pinning, governor refusal and the hand-back.
