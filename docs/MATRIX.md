# The extension matrix: one set of extensions, every way PiG can run it

The overhead scenarios `print-ext10` and `rpc-ext10` load ten identical trivial extensions, and `print-ext5` and `rpc-ext5` the first five of them (generated from `fixtures/extensions/bench-ext.template.ts`: a tool, a command and four event handlers). An arm with its own realization lists the files itself and loads the first five of its list for the ext5 scenarios; an arm with its extensions built into its executable cannot load five. The matrix arms run those ten extensions in each realization PiG supports, from one PiG build (`pig-tip`), so a difference between two arms is the realization and nothing else.

| arm | the ten extensions as | PiG runs them in |
|---|---|---|
| `pi-node`, `pibolt` | the TypeScript files | Pi's own process (Node, or Pi-Bolt's Bun/JSC build); reference rows, no extension process |
| `pig-ts-node` | the TypeScript files, Pi-compatible factories | one Node process (a packed cell: PiG's default for TypeScript factories) |
| `pig-ts-bun` | the same files | one stock Bun 1.4.2 process through the runtime slot (`PIG_TS_RUNTIME=bun`) |
| `pig-ts-aot` | the same files | one process of the ahead-of-time compiled host (`PIG_TS_RUNTIME=aot`), the aot Piglet's image built for this set |
| `pig-go-packed` | `fixtures/extensions-go/factory/bench-ext-NN`, Go SDK factories | one generated Go runner process |
| `pig-go-isolated` | `fixtures/extensions-go/standalone/bench-ext-NN`, exact standalone modules | ten Go processes |
| `pig-go-fused` | the same factories, `pig piglet build --format binary` of `fixtures/extensions-go/pig-ext10.yaml` | the PiG executable itself: no extension process, no IPC |

## Piglet arms

The Piglet arms measure Piglet Binaries built from the Pigpen commit that `[piglet] pigpen_commit` names. Each one is `pig piglet build --format binary` of one Pigpen manifest, staged the way Pigpen's `npm run stage` does, for the host target. The arm pins the manifest's sha256, the release version and the build record's component-plan digest. A build whose manifest bytes or pinned identity differs is refused. The resolution, graph, closure and artifact digests are recorded in the arm's record, next to the report's view of the Piglet, but not pinned: they differ between builds of one commit, because PiG writes the build's wall-clock time into the resolution record that the Binary embeds (`createdAt`; `coding/pigletbuild/records.go` at the pig-tip commit calls `time.Now()`), and the resolution digest covers it. Staging installs the Pigpen commit's own `package-lock.json` with `npm ci`, in the workspace's npm cache.

| arm | Piglet | state |
|---|---|---|
| `piglet-bench-lean` | `bench-lean`: every built-in extension, extra API and feature stripped (keep mode) | runs; the extension workloads do not apply (no extension runtime) |
| `piglet-bench-ext10` | `bench-ext10`: the ten Go factories fused | runs |
| `piglet-bench-ext10-split` | `bench-ext10-split`: five Go fused, five TypeScript through the aot runtime | held: the aot image step is not wired for Piglets |
| `piglet-bench-ext10-aot` | `bench-ext10-aot`: ten TypeScript through the aot runtime | held: the same |
| `piglet-combined` | no manifest at the pinned commit | held: waits for the combined Go-fused and aot shape |

Arms derived from `pig-tip` inherit its modes, endpoint, environment and capabilities, so every Piglet arm runs the same families, inputs and metering.

No setting isolates a TypeScript or Go *factory*, so there is no user-reachable "TypeScript, one process each" arm. Matrix arms run only when a run names them (`[extensions] default = false`).

## How an arm is built

`[derive] base = "pig-tip"` runs the arm from its own copy of the base's install tree (the A/A copy is a third copy) and inherits the base's tables key by key. `[extensions]` names the sources passed with `-e` (`paths`), whether they are built into the executable (`embedded`), and what the process census must show (`processes`: extension processes; `host`: a substring of their executable). `[prepare]` finishes the install: a Bun runtime slot, a built Piglet Binary, the aot image, and the warm cache.

The **warm cache** is the state a user's second start has and the first does not: compiled Go cells, the materialized Node runtime. `prepare` starts the arm once, keeps `PIG_HOME/cache` and `state`, and every sample starts from a copy of it. PiG keys a generated cell on the cache root's path, the SDK path and the Go toolchain it finds, so a matrix arm sets `PIG_HOME` to one fixed path (`{shared_dir}/pig-home`, emptied before each sample), `PIG_SDK_GO_ROOT` to the base's checkout and has the pinned Go on `PATH`. Without them a fresh HOME misses the cache and the sample compiles (and the egress audit fails it).

## Equivalence before timing

Before the first sample (`buffon/runner/equivalence.py`) every arm with a ten-extension scenario runs one `rpc` session against a scripted model that calls `bench_tool_01` .. `bench_tool_10` in turn. When the plan has an ext5 scenario, the gate also runs a session with five extensions that calls `bench_tool_01` .. `bench_tool_05`; an arm that cannot load five is left out of that one. It records the commands, the tool declarations in the model request, the result of every tool call as the RPC stream reports it (content and details, including how many handler events each extension had counted) and the tool results the next request carries. Any difference from the oracle (Pi on Node) refuses the run (exit 3); `equivalence.json` in the run directory holds the records, the digests and the extension process census of every arm.

## What a ten-extension rpc sample reports besides the usual metrics

`extension_processes` and `extension_exes` (the census at ready, checked against the arm's declaration), `turn_host_cpu_ms` and `turn_extension_cpu_ms` (CPU per turn of the harness process and of its extension processes, from /proc), and the usual `ready_ms`, `extensions_ready_ms`, RSS and PSS at ready.

**Process-boundary share.** The fused arm runs the same Go extensions with no process boundary, so for a Go arm `1 - turn_cpu(fused) / turn_cpu(arm)` is the share of the per-turn cost that the boundary (serialization, IPC, the extension process's own work) adds. TypeScript arms are a different language and are compared with each other, not with fused.
