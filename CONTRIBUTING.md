# Adding or updating a harness

This page is for harness authors. It explains what Buffon needs from your harness, how to add it, and what happens to your results.

## What your harness needs

1. **A pinnable artifact.** A release archive, binary or package version that never changes once published, with a checksum (`SHA256SUMS` or a per-asset `.sha256`). A signature is welcome. A source-only harness is accepted at a commit hash, with its toolchain version and build command.
2. **A way to talk to a local endpoint.** A config file or environment variables that point the harness at `http://127.0.0.1:<port>` speaking OpenAI Chat Completions, OpenAI Responses or Anthropic Messages, with a dummy key. No login, account or vendor service may be needed.
3. **A way to turn off network traffic** other than model requests: telemetry, update checks, crash reporting, install reporting.
4. **A way to run headless**, at least one of: a print mode (prompt in, answer out), a JSON or RPC mode, or an HTTP API. An interactive-only harness can still be measured through the PTY driver, but it gets "cannot run" for the headless workloads.
5. **State directories you can redirect** into a fresh HOME (environment variables or flags), so runs do not share state.
6. **A licence and terms that allow the run.** Buffon runs and publishes results for your harness, operated by people and sometimes by automated agents. If your licence or terms restrict benchmarking, publication, or who may run your software, say so in the manifest; the arm stays held until that is resolved.

## How to add it

A recipe, in order. The worked example is the OpenCode arms (`arms/opencode`, `arms/opencode-v2`; commit `8ceccb3`), an npm package with a platform executable. The npm, lock and verify commands below were run on macOS arm64 while writing this page. The full manifest reference is in [`arm.toml`](#armtoml) below.

1. **Pick the install form** from what you publish: a release archive (`[artifact.<platform>]`), an npm package (`[npm]`), a source build at a commit (`[source]`; Go with `CGO_ENABLED=0` can be cross-built into a bundle), or a variant of an arm that already installs (`[derive]`). OpenCode is an npm package, so `[npm]`.
2. **Create `arms/<name>/`.** The directory name must equal `name` in the manifest, and the name may not end in `-b` (that suffix is the A/A copy of an arm). `buffon/arms/manifest.py:validate` refuses an unknown key, a missing required key, a non-https artifact URL and a sha256 that is not 64 hex digits.
3. **Pin the package (npm form).** Make the lock file the way `buffon/arms/install.py:_npm` expects it: a package named `arena-arm-<name>` with your package as its one dependency. Then take the integrity and the lock's sha256:

   ```sh
   mkdir /tmp/lock && cd /tmp/lock
   echo '{"name":"arena-arm-opencode","version":"0.0.0","private":true,"dependencies":{"opencode-ai":"1.19.0"}}' > package.json
   npm install --package-lock-only --ignore-scripts     # writes package-lock.json
   npm view opencode-ai@1.19.0 dist.integrity           # the package's integrity, for arm.toml
   shasum -a 256 package-lock.json                      # package_lock_sha256, for arm.toml
   cp package-lock.json <repo>/arms/opencode/
   ```

   This reproduces `arms/opencode/package-lock.json` byte for byte (sha256 `b675d717...`). For an archive, copy the sha256 from the project's `SHA256SUMS`; `buffon lock --online` later compares every hash with the one the project publishes. For a source build, pin the full 40-hex commit and name the environment variable that tells the runner where the repository is (`repo_env = "BUFFON_SOURCE_REPO_<NAME>"`); a manifest never names a repository path.
4. **Write `arm.toml`.** Copy `arms/opencode/arm.toml` and change `name`, `label`, `version`, `[npm]`, `[env]`, `[modes]` and `[cannot_run]`. Things that matter:
   - `[env]` turns off every connection that is not a model request. OpenCode needs `OPENCODE_DISABLE_AUTOUPDATE`, `OPENCODE_DISABLE_MODELS_FETCH`, `OPENCODE_DISABLE_LSP_DOWNLOAD` and `npm_config_offline`. `{dummy_key}` expands to the dummy key.
   - `[modes]` needs `version` (the post-install check). Declare `print`, `rpc`, `pty` only when they work. Say why each missing one cannot run in `[cannot_run]`; the report prints that text.
   - `[capabilities]` and `claims` decide which grade families apply to the arm (`pi_extensions`, `pi_session_format`; [docs/GRADE.md](docs/GRADE.md) has the N/A classes). OpenCode is not Pi, so it declares none.
   - `relation` is `reference` for a harness unrelated to Pi, and `notes` says what a reader should know (OpenCode sends a title request before the scripted turn, so its request counts are not exact).
   - `[runtime] node = "..."` must equal the version in `runtimes.toml`; Buffon never uses your Node.
5. **Write the config writer, `arms/<name>/writer.py`.** It exposes `write(spec)`, called for every sample with a fresh HOME. It must point the harness at `spec.endpoint()`, use the dummy key, and return a dict of extra environment variables (or `{}`). `spec` is `buffon/arms/writers/__init__.py:WriteSpec` (`home`, `agent_dir`, `cwd`, `api`, `model`, `context_window`). If several arms share a format, put the code in `buffon/arms/writers/<family>.py` and keep `writer.py` a one-line import, as OpenCode does: `from buffon.arms.writers.opencode import write`. The OpenCode writer sets the provider, an allow-all permission rule (a headless run cannot answer a prompt), and update and share off.
6. **Write `arms/<name>/prepare.py` if the manifest cannot finish the install.** Declare `[prepare] script = "prepare.py"` and define `prepare(ws, arm, base)`; the runner calls it after the install (`install.Workspace._prepare`). OpenCode's npm package is a stub whose postinstall would copy the real executable, and Buffon installs with `--ignore-scripts`, so `prepare.py` points `arm.binary` at the platform package's executable after checking its sha256 against a table in the file (`buffon/arms/prepare_opencode.py:native_binary`). Get each platform's hash by unpacking its package, for example:

   ```sh
   npm pack opencode-darwin-arm64@1.19.0 && tar xzf opencode-darwin-arm64-1.19.0.tgz package/bin/opencode && shasum -a 256 package/bin/opencode
   ```
7. **Verify the arm.** `python3 -m buffon arm verify <name> --site <your site>` (`<name>` is the directory name or a short name such as `pig`, the same names `buffon up` takes). It installs into a fresh root, checks every pin, writes the config, starts the harness against the mock, runs `version`, `print`, `rpc` and `pty` once per declared wire API, and fails if the harness connects anywhere but the mock. A mode you did not declare prints `cannot run` with your reason. On OpenCode (15 s on macOS):

   ```
   installed opencode: 1.19.0
     version  openai-completions   ok
     print    openai-completions   ok
     rpc      openai-completions   cannot run: no Pi-dialect RPC mode: ...
     pty      openai-completions   ok
   ```
8. **Regenerate the lock.** `python3 -m buffon lock` rewrites `arms.lock` (it hashes every file in your arm directory, so run it again after any edit to `arm.toml`, `writer.py`, `prepare.py` or the lock file). `python3 -m buffon lock --check` fails when it is stale.
9. **Register the arm in the test.** `tests/test_arms.py` holds the closed set of arm names (`V0_ARMS`, `MATRIX_ARMS`, `HELD`); add yours, or `test_every_v0_arm_is_present_and_the_held_arms_are_held` fails. That is the only registration a test checks. Add a line to `CHANGELOG.md`. The roster in `docs/DESIGN.md` and the survey are records of the start of the project and need no row.
10. **Run the tests that cover arms**, not the whole suite: `python3 -m unittest tests.test_arms tests.test_armverify tests.test_hygiene tests.test_license_headers tests.test_docs`.
11. **Smoke-run one suite.** A short run proves the arm survives the interleaved runner, the A/A copy and the egress audit:

    ```sh
    python3 -m buffon run overhead/version overhead/print --arms pi-node opencode --apis openai-completions \
        --rounds 4 --allow-short --site <your site> --out runs/smoke
    python3 -m buffon report runs/smoke
    ```

    `--allow-short` marks the run "not a measured run"; it is for this check only. `pi-node` is the reference every other arm is compared with, so name it too.
12. **Open the pull request.** Commit with `git commit -s`. A maintainer who does not work on your harness reviews it.

### What you get after the merge

Nothing else needs registering after step 9. The report, the grade and the dashboard take the arm list from `raw.json`: `buffon report` writes one section per arm with its manifest's `label`, `relation` and pins; `buffon grade` scores it by the N/A classes its capabilities give; `buffon dashboard` adds a page for it under `harnesses/` ([docs/design/DASHBOARD.md](docs/design/DASHBOARD.md)). No file under `buffon/report/` or `buffon/dashboard/` names OpenCode. A new arm runs by default in `buffon run` (every runnable arm) unless it is held (`held = "<reason>"`, listed and never run) or sets `[extensions] default = false`. For the commands that get from a run to a dashboard, see [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md); for how the pieces fit, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### `arm.toml`

```toml
name = "example-agent"
label = "Example Agent"
homepage = "https://example.org/example-agent"
relation = "pi-fork"            # pi-reference | pi-fork | pi-port | pi-compatible | reference
licence = "MIT"
licence_url = "https://example.org/example-agent/LICENSE"
restrictions = ""               # quote any clause that limits benchmarking, publication or who may run it
version = "1.2.3"

[artifact.linux-x64]
url = "https://example.org/releases/v1.2.3/example-agent-linux-x64.tar.gz"
sha256 = "<64 hex>"
checksums = "https://example.org/releases/v1.2.3/SHA256SUMS"
exe = "example-agent-linux-x64/example-agent"

[runtime]                       # only if the harness starts a runtime itself; the version must equal runtimes.toml's pin, and its bin directory goes on the arm's PATH
node = "24.19.0"

[endpoint]
apis = ["openai-completions"]   # openai-completions | openai-responses | anthropic-messages
writer = "writer.py"            # writes config into $HOME for the mock URL and a dummy key

[env]                           # always set
EXAMPLE_TELEMETRY = "0"
EXAMPLE_NO_UPDATE = "1"

[state]
dirs = ["~/.example", "$XDG_CONFIG_HOME/example"]

[modes]                         # argv templates: {model} {prompt} {session} {session_dir} {extensions}
version = ["--version"]         # required: the post-install version check
print = ["-p", "{prompt}"]
rpc = ["--mode", "rpc"]
pty = []

[cannot_run]                    # a reason for each mode the harness lacks (printed as "cannot run")
# rpc = "no JSON RPC mode"


[capabilities]
pi_extensions = "native"        # native | sidecar | partial | none
pi_session_format = true        # reads and writes Pi session files (enables the long-session and parity workloads)
exact_requests = true           # sends exactly the scripted requests (no title or token-count side requests)

# Optional, written above the first [table] of the file: the Pi capabilities the arm claims, for the grade's N/A classes (docs/GRADE.md). Default: derived from the capabilities above and the modes.
# claims = ["pi-extensions", "pi-sessions", "pi-rpc"]

[renderer]
pty = "fullscreen"              # the renderer mode pinned for PTY workloads; "default" when the arm has one renderer
```

Other install forms, one per manifest instead of `[artifact.*]`:

- `[npm]`: a package installed with `npm ci --ignore-scripts` from a committed `package-lock.json` (and the vendor's `package.json` when it publishes the pair), on the Node pinned in `runtimes.toml`. Give `package`, `version`, `integrity`, `package_lock` with its `package_lock_sha256`, `bin` and `runtime` (all required by `buffon/arms/manifest.py:validate`).
- `[source]`: a build from a commit. Give the full 40-hex `commit` (and its `tree`), `toolchain` (a runtime pinned in `runtimes.toml`), the `build` argv and `repo_env`, the name of the environment variable that tells the runner where the repository is. A manifest never names a repository location.
- `[derive]`: `base = "<other arm>"`. The arm runs from a copy of that arm's install tree and inherits its scalar fields and tables key by key (`buffon/arms/manifest.py:INHERITED_*`). The base must be an arm that installs itself.
- `[prepare]`: `script = "prepare.py"`, an optional step after any install form. It defines `prepare(ws, arm, base)` and may set `arm.binary` or lay down a runtime slot or a warm cache (step 6 above).
- `held = "<reason>"`: the arm is listed and never run (docs/DESIGN.md section 9). A held manifest needs no install form.
- `operator_terms = "<which vendor terms apply, why the operator must accept them, and their URL>"`: the arm installs from the vendor at run time and is never redistributed (never in a bundle). It is never in the default set, `all` or a glob; it runs only when named in full with `--accept-terms <id>` (or `BUFFON_ACCEPT_TERMS`), and a refusal quotes this sentence. A saved selection records the acceptance and raw.json holds `operator_terms_accepted`. Not combined with `held`.
- `[npm] bin_native = { <platform> = "<path>" }`: for a package whose own `bin` is a stub that only its postinstall script replaces (Claude Code, Copilot CLI, OpenCode): the executable inside the platform's optional-dependency package, relative to the install root. `native_bin` pins that file's sha256 per platform.

## What happens to your results

- Your harness is run with exactly the pinned artifact, in the configuration your manifest gives, and nothing else. If a workload needs a setting Buffon does not apply to every arm, it is not used.
- Before any result that includes your harness is published, you get a review window (proposed: 14 days) with the full run directory. You can report a methodology error: a wrong configuration, a mock behaviour your harness handles differently from real providers, a measurement artefact. Valid errors are fixed and the run is repeated.
- You cannot ask for a result to be removed because it is unfavourable. You can ask for a rerun on a newer version; it appears as a new result, beside the old one.
- "Cannot run" rows say exactly why. If your harness gains the missing feature, update the manifest and the next run includes it.

## Updating a version

Change `version` and the artifact block in your manifest, run `python3 -m buffon arm verify` and `python3 -m buffon lock`, and open a pull request. Buffon refreshes every arm on its regular schedule anyway; a pull request gets your release into the next run.

## Reporting a problem with Buffon itself

Open an issue with the run directory name, the metric, and what you believe is wrong. Methodology issues are answered in public, and corrections link to the issue.

## Rules the tests check

Run every check named here with one command, before you push (the dashboard test needs Node 18 or later):

```sh
python3 -m unittest tests.test_docs tests.test_hygiene tests.test_license_headers tests.test_arms tests.test_health tests.test_dashboard
```

- **Banned words.** One list, `tests/banned_words.py`, read by three tests.
  - Claim words stay out of README, METHODOLOGY, RUNNING, WHAT-WE-MEASURE, FIELD and LIMITATIONS: fastest, slowest, best, winner, beat, beats, outperform, outperforms, outperformed, outperforming, blazing, blazingly, unmatched, state-of-the-art, world-class, superior, unbeaten, cutting-edge. Give a number with a unit and its spread instead.
  - Comparatives stay out of LIMITATIONS: better, worse, lighter, heavier, faster, slower, win, wins, lose, loses, superior, inferior, leaner.
  - Machine names stay out of every tracked file: .ts.net, .internal, k3d-. A private list can add to them (`BUFFON_FORBIDDEN_WORDS` or `BUFFON_FORBIDDEN_WORDS_FILE`; CI sets it). Absolute home paths (`/home/<user>`, `/Users/<user>`) and non-loopback IPv4 addresses are also refused in any tracked file: use a site profile, a flag or an `BUFFON_*` variable.
- **Em dashes.** No em dash (U+2014) on any page of the results site (`tests/test_dashboard.py`, `tests/test_dashboard_scale.py`) or in a run-note meaning in `workloads/health.toml` (`tests/test_health.py`). The Markdown documents are not checked; use a colon or a full stop there too.
- **Links.** Every relative link and anchor in README, CONTRIBUTING and `docs/*.md` must resolve (`tests/test_docs.py`).
- **Text copied from code.** `docs/HEALTH.md` between its THRESHOLDS markers is generated: run `python3 -m buffon health thresholds` and paste the tables. The faithfulness weights, credits and floor in `docs/WHAT-WE-MEASURE.md`, a heading for every grade family there, and the section headings of `docs/REPORT-TEMPLATE.md` must equal what the code has.
- **Glossary.** An abbreviation that a page shows must be in `ACRONYMS` or `COMMON` of `buffon/dashboard/glossary.py`.
- **Arm names.** The measurement code never names an arm, and a new arm is added to the closed set of `tests/test_arms.py` (step 9 above).
- **Licence headers.** New files carry `SPDX-License-Identifier: Apache-2.0` (`tests/test_license_headers.py`).

## Commits and merges

Every commit carries a `Signed-off-by` line (`git commit -s`), merge commits included (`git merge --signoff`). CI enforces it on every commit of a pull request (job `signoff` in `.github/workflows/tests.yml`). If it fails, add the line to the whole branch with `git rebase --signoff <base>` and push with `git push --force-with-lease`. New code carries `SPDX-License-Identifier: Apache-2.0`; an MIT header is only for files adapted from MIT-licensed vendored code, and the list of those files is closed (`tests/test_license_headers.py`).
