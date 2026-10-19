# Compatibility row: @ff-labs/pi-fff 0.11.0 on Pi and on PiG

`tools/compat_fff.py` loads the published, unmodified `@ff-labs/pi-fff@0.11.0` (MIT; `npm pack`, dependencies `@ff-labs/fff-node` 0.11.0 with its native binary) with `-e` into each implementation and compares what the user and the model can observe. It needs no bench slot and makes no timing claim.

Implementations: Pi 1.1.0 (the oracle of this row, a release named on the command line below), Pi 1.0.3, PiG on the Node host with the extension packed (the default) and PiG with every Node factory isolated (`pig-ts-node-isolated-diag`'s one-line patched build; a single extension is one process either way, so the isolated column only differs when other extensions load with it: variant E).

Every run is hermetic: HOME, the agent directory (the extension writes its LMDB frecency and history databases under it and prints their paths) and the project (a git repository of six files) sit at fixed paths under `/tmp/fffcompat` and are recreated before each run; the model is Buffon's scripted mock.

| variant | what is compared (every mode: `--fff-mode tools-and-ui`, `tools-only`, `override`) |
|---|---|
| A rpc | the `fff-*` commands (`get_commands`), the tools the model request declares (name, description, schema), `ffgrep` / `fffind` (or `grep` / `find` in `override`) results byte for byte, the notifications of `/fff-health`, `/fff-mode`, `/fff-mode nonsense`, `/fff-mode override`, `/fff-mode tools-and-ui`, `/fff-rescan`, the session-start notifications and status |
| B rpc, `PI_FFF_MULTIGREP=1` | as A with `fff-multi-grep` (`multi_grep` in `override`) registered and called |
| C rpc, flags | as A with `--fff-frecency-db`, `--fff-history-db`, `--fff-follow-symlinks=false`, `--fff-warn-home-scan=false`, `--fff-enable-root-scan=false` accepted |
| D rpc, cwd = $HOME | the home-scan warning and footer status at session start (tool output and `/fff-health` left out: the home directory holds each implementation's own cache files) |
| E rpc, with the ten bench extensions | as A with ten more Node extensions loaded next to it: one packed process on PiG, eleven isolated processes in the patched build |
| F interactive (tmux) | the `@alp` file completion popup, its Tab completion and the `/fff-` command menu, screen lines byte for byte |

Census (process count on PiG, outside the comparison): packed `node` ×1; isolated ×1 alone, ×11 with the ten bench extensions; Pi runs the extension in its own process.

`python3 tools/compat_fff.py --fff <dir>/node_modules/@ff-labs/pi-fff --impl pi110=<pi 1.1.0> --impl pi103=<pi 1.0.3> --impl pig-packed=<pig> --impl pig-isolated=<patched pig> [--env PI_FFF_MULTIGREP=1] [--extra-ext <path> ...] [--flag=... ] [--cwd home --skip results --skip ui.health] [--autocomplete]`; exit code 1 on a difference. The comparison was shown to see a difference: A against B on one implementation reports four.

## Compatibility row: nicobailon/pi-subagents (background and foreground agents)

`tools/compat_subagents.py` runs the frozen `pi-subagents@0.77.0` (`fixtures/external/pi-subagents`) on Pi 1.1.0, Pi 1.0.3 and PiG (packed; the isolated column uses the diagnostic patched build). A background agent (`async: true`) runs in a detached Node process that imports Pi's packages and calls the model from there; a foreground agent (`async: false`) runs in the extension process. Compared: the tool result the parent gets, the completion message that wakes it, parent and child model request counts, the run's terminal status. Before the fix PiG ended every background run with "Background children require the host npm package ... does not provide ..." (peer packages missing from the harness), then "pig TS runtime not initialized" (no provider path in a process with no extension runtime); after it the background run completes with the same output as Pi.

`tools/compat_outside_runtime.py` runs rev-issues-verify's probe (`fixtures/outside-runtime-probe`: programs B2 and B3): a detached `node` child, a `fork` child and a `worker_threads` worker import Pi's packages from the host package root and call a builtin pi-ai API. Pi answers `pong` from all three and resolves 192 of 196 published subpaths from the detached child; PiG answers `pong` from all three and resolves 179, the 13 it does not being listed in `KNOWN_GAPS` (a subpath that starts or stops resolving without a change to that list is a difference).

## Frozen external extensions

Every external extension a row runs is `fixtures/external/<name>/`: `package.json` with exact versions, `package-lock.json` with the integrity of every package, `.npmrc` with install scripts off and peers left to the host. `tools/external_ext.py` installs it with `npm ci --ignore-scripts --offline` from a local npm cache (one fetch step fills the cache from the registry; npm checks each tarball against the lockfile's integrity) and refuses a tree that differs from the lockfile. The rows print the installed package's version and integrity. A bump is an explicit commit changing the fixture. `pi-subagents@0.77.0` was published 2026-10-10 (under the seven-day bar) and is pinned because it is the version the repro ran; pin the version the user reported when it is known.
