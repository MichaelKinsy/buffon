# Buffon harness survey

Status: research input for the Buffon design doc. Snapshot date: 2026-10-10. Read-only web research: nothing was installed or executed, no credentials were read, nothing was posted, no accounts were created. (Some npm tarballs were downloaded and grepped as text for omp and OpenCode; none were run.)

Conventions: `UNVERIFIED` = not confirmed from a primary source; `[INFERENCE]` = reasoned, not observed. Dates are YYYY-MM-DD. Many commit dates come from GitHub Atom feeds because the unauthenticated GitHub REST API rate-limited during research. "Benchmarking restriction" means a licence or ToS clause that restricts benchmarking, publishing results, use by AI agents or named companies, competitive use, or reverse engineering.

Canonical home moves to note: Pi moved from `badlogic/pi-mono` to [earendil-works/pi](https://github.com/earendil-works/pi), and the npm package moved from `@mariozechner/pi-coding-agent` (deprecated, last 0.73.1) to [`@earendil-works/pi-coding-agent`](https://registry.npmjs.org/@earendil-works/pi-coding-agent/latest). OpenCode moved from `sst/opencode` to [anomalyco/opencode](https://github.com/anomalyco/opencode). Goose moved from `block/goose` to [aaif-goose/goose](https://github.com/aaif-goose/goose).

Versions newer than the lead's `bench/compare/arms.lock` (2026-10-10): Pi-Bolt `bolt-v0.8.0` (2026-10-10; arms.lock has `bolt-v0.7.4`) and omp 18.8.9 (npm 2026-10-10; arms.lock has v18.8.8).

Follow-up additions (retrieved 2026-10-10, from the W3 harness sweep): six harnesses added to the summary table (Prime Agent, jcode, Antigravity CLI, Cursor CLI, Factory Droid CLI, Hermes Agent) with entries in §4, plus Zed as an ACP host and a brief list of other ACP registry and Harbor agents. Updated facts: OpenCode v1.19.0, Gemini CLI's consumer-tier retirement, Amp's BYOK changes, Harbor's adapter list, Terminal-Bench 4.0, SWE-Bench Pro V2 and Anthropic's infrastructure-noise study. New methodological lessons 15 to 18 (§5).

## 1. Summary table

| harness | relation to Pi | version + date | licence (SPDX) | benchmarking restriction | pin method | custom endpoint | headless mode |
|---|---|---|---|---|---|---|---|
| **Pi on Node** | upstream reference | 1.1.0, 2026-10-07 | MIT | N | `npm ci --ignore-scripts` using the release's `pi-coding-agent-install-package-lock.json` (in `SHA256SUMS`); or `npm i -g --ignore-scripts @earendil-works/pi-coding-agent@1.1.0` (transitive deps not pinned); or Nix `github:earendil-works/pi/v1.1.0` | Y (`models.json`) | `-p`, `--mode json`, `--mode rpc` |
| **Pi on Bun** | same source; official `bun build --compile` standalone binaries (Bun 1.3.14) | 1.1.0, 2026-10-07 | MIT | N | release `pi-<os>-<arch>.tar.gz` + `SHA256SUMS` for tag `v1.1.0` | Y (`models.json`) | same as Pi |
| **PiG** | independent Go port, not endorsed by Pi; tracks Pi 1.0.3 | 0.4.1, 2026-10-05 | MIT | N | `PIG_VERSION=0.4.1` installer (SHA256-checked); `go install github.com/MichaelKinsy/PiG/cmd/pig@v0.4.1`; `npm i -g @pi-in-go/pig@0.4.1` | Y (Pi-compatible `models.json`) | `--print`, `--mode json`, `--mode rpc` |
| **Pi-Bolt** | fork of Pi; same TS compiled AOT on Bun/JavaScriptCore | 0.8.0 (`bolt-v0.8.0`), 2026-10-10; based on Pi 1.1.0 | MIT | N | `PIBOLT_VERSION=bolt-v0.8.0` install.sh (SHA256SUMS + Ed25519 sig); release tarball; `npm i -g pi-bolt@0.8.0` | Y (Pi `models.json`, inherited) | Pi's `-p`; `--mode json/rpc` [INFERENCE] |
| **gi** (rcarmo/gi) | Go agent informed by Pi; reads Pi config; built on go-ai (Go port of pi-ai 1.1.0) | no release; commit `7078df0d59bf`, 2026-10-10 | MIT | N | `git checkout 7078df0d59bf` + `make build` | UNVERIFIED (no `models.json`) | no print mode; `gi -web` REST + SSE |
| **omp** (oh-my-pi) | fork of Pi (Bun + Rust N-API core) | 18.8.9 (npm), 2026-10-10 | MIT | N | `bun install -g @oh-my-pi/pi-coding-agent@18.8.9`; `curl -fsSL https://omp.sh/install \| sh -s -- --binary --ref v18.8.9` (SHA-256) | Y (`~/.omp/agent/models.yml`) | `-p`, `--mode json\|rpc\|acp` |
| **pi_agent_rust** | from-scratch Rust port ("with his blessing"), diverging toward omp | v0.7.1, 2026-10-03 | LicenseRef (MIT + OpenAI/Anthropic Rider) | **Y** | `install.sh --version v0.7.1 --no-agent-skills` (per-asset `.sha256` + `.minisig`) | Y (`~/.pi/agent/models.json`) | `-p`, `--mode text\|json\|rpc`, `--acp` |
| **OpenCode** | unrelated reference | v1.19.0, 2026-10-11T01:39Z (v1.18.35, 2026-10-06, at the first snapshot) | MIT | N | `npm i -g opencode-ai@1.19.0`; `VERSION=1.19.0` install script; release digests | Y (`opencode.json` + `@ai-sdk/openai-compatible`) | `opencode run --format json`, `opencode serve` |
| **GitHub Copilot CLI** | unrelated closed reference | 1.0.95, 2026-10-09 | NOASSERTION (proprietary) | **Y** (Competitive Benchmarking; pre-release reverse-engineering ban) | `npm i -g @github/copilot@1.0.95`; `VERSION=v1.0.95` install script (SHA256SUMS.txt) | Y (BYOK `COPILOT_PROVIDER_*`, `COPILOT_OFFLINE=true`) | `copilot -p … --allow-all-tools --output-format json` |
| **Octet** | unrelated reference (Rust; mentions Pi as a design influence) | v0.9.4, 2026-10-15 (the repository is at 0.9.5, which has no release) | MIT | N | `octet-0.9.4-<target>.tar.gz` pinned by sha256 from the Sigstore-signed `OCTET_SHA256SUMS` | Y (custom registry `~/.octet/credentials/custom.json`, OpenAI Chat Completions only) | `octet -p`, `--mode json`, `--mode rpc` (Pi-framed JSONL) |
| nowa/gi | Go rebuild of Pi packages (Pi v0.82.1 parity); same binary name as rcarmo/gi | v0.82.2, 2026-07-27 | MIT | N | source build at tag | Y (`~/.gi/agent/models.json`) | `-p` |
| pie (c4pt0r) | Rust rewrite of Pi | no release; 2026-08-06 | MIT | N | source build at commit | Y (`--base-url`, `~/.pie/models.json`) | none documented |
| rpi (revpidev) | Rust port derived from Pi (v1.0.0 parity) | v0.1.6, 2026-10-09 | MIT | N | release archive + `.sha256` | UNVERIFIED | `--print`, `--mode json\|rpc` |
| sky-valley/pi | pure-Go port (pi 0.99.2) | v0.99.26, 2026-10-01 | MIT | N | source build at tag | UNVERIFIED | print only |
| nktkt/pi (crate `pi-coding-agent`) | Rust port of core loop | 1.0.0, 2026-05-12 | MIT | N | `cargo install pi-coding-agent --version 1.0.0 --locked` | library only; CLI UNVERIFIED | `-p`, `-p --json` |
| pi-mono-python | Python port (pi-mono v0.84.3) | no release; 2026-08-25 | **none (no LICENSE)** | N, but no licence grant | source + `uv.lock` | UNVERIFIED | `--print` |
| OpenAI Codex CLI | unrelated reference | 0.162.1, 2026-10-09 | Apache-2.0 | N | `npm i -g @openai/codex@0.162.1`; release binaries | Y (OpenAI **Responses** only) | `codex exec --json` |
| Claude Code | unrelated closed reference | 2.1.296, 2026-10-09 | proprietary | **Y** (competing-product, reverse-engineering, no-modification) | `install.sh` with version arg (GPG-signed manifest); npm `@2.1.296` | Y (Anthropic Messages, `ANTHROPIC_BASE_URL`) | `claude -p --output-format stream-json --verbose --bare` |
| Gemini CLI | unrelated reference; stopped serving consumer tiers 2026-06-18 (Antigravity CLI replaces it there) | 0.63.0, 2026-10-06 | Apache-2.0 | N | `npm i -g @google/gemini-cli@0.63.0` | Partial (Gemini API only, `GOOGLE_GEMINI_BASE_URL`) | `gemini -p --output-format json\|stream-json` |
| Qwen Code | unrelated (Gemini CLI fork) | 0.25.0, 2026-10-05 | Apache-2.0 | N | `npm i -g @qwen-code/qwen-code@0.25.0` | Y (OpenAI, Anthropic, Gemini) | `qwen -p --output-format json\|stream-json` |
| Crush | unrelated reference | v0.98.1, 2026-10-09 | FSL-1.1-MIT | **Y** (Competing Use; research use permitted) | `go install …@v0.98.1`; npm; `checksums.txt` | Y (OpenAI-compat, Anthropic) | `crush run -q` (text only) |
| Goose | unrelated reference | v1.54.0, 2026-10-08 | Apache-2.0 | N | `download_cli.sh` with `GOOSE_VERSION=v1.54.0` | Y | `goose run --output-format json\|stream-json` |
| Kimi Code CLI | uses Pi's `pi-tui` library (not a fork) | 2.1.1, 2026-09-24 | MIT | N | `npm i -g @moonshot-ai/kimi-code@2.1.1`; binaries + `.sha256` | Y (`openai`, `openai_responses`, `anthropic`) | `kimi -p --output-format stream-json` |
| Aider | unrelated reference (edit-format, not tool-calling) | 0.86.2 (PyPI), 2026-02-12 | Apache-2.0 | N | `pip install aider-chat==0.86.2` | Y (OpenAI-compat via LiteLLM) | `aider --message … --yes-always` (text only) |
| Amp (brief) | unrelated closed reference | npm 0.0.1791662459-g6be10b, 2026-10-10 | proprietary | Partial (anti-automation AUP) | npm exact version + `amp.updates.mode: "disabled"` | needs Amp account; local endpoint UNVERIFIED | `amp -x --stream-json` |
| Prime Agent | unrelated reference (Rust rewrite of a TypeScript agent) | v0.10.1-beta.6, 2026-10-10 (pre-release; nightly builds also published) | MIT | UNVERIFIED (terms not reviewed) | install script `app.primeintellect.ai/prime-agent/install.sh`; version pin UNVERIFIED | UNVERIFIED | UNVERIFIED (daemon-backed sessions, `prime-agent attach`) |
| jcode | unrelated reference (Rust) | v0.94.0, 2026-10-10 | MIT | N in LICENSE; terms not reviewed | release tag `v0.94.0`; install script `jcode.sh/install`; checksums UNVERIFIED | Y (OpenAI-compatible profile, `base_url` in `~/.jcode/config.toml`) | UNVERIFIED (headless daemon sessions per README) |
| Antigravity CLI (`agy`) | unrelated closed reference; Google's successor to Gemini CLI for consumer tiers | ACP registry entry `antigravity-acp` 1.3.0 (retrieved 2026-10-10) | proprietary | UNVERIFIED (terms not reviewed) | `antigravity.google/cli/install.sh`; version pin UNVERIFIED | Partial (Gemini API, `GOOGLE_GEMINI_BASE_URL`) | `agy --prompt` |
| Cursor CLI | unrelated closed reference | v2026.10.08 | proprietary | UNVERIFIED (terms not reviewed) | `cursor.com/install` script; version pin UNVERIFIED | UNVERIFIED (needs `CURSOR_API_KEY`) | `cursor-agent --print --output-format=stream-json`; ACP mode |
| Factory Droid CLI | unrelated closed reference | npm `droid` 0.238.0, 2026-10-10 | proprietary (npm `UNLICENSED`) | UNVERIFIED (terms not reviewed) | `npm i -g droid@0.238.0` | UNVERIFIED (BYOK custom models; needs `FACTORY_API_KEY`) | `droid exec -o json`; `--output-format acp-daemon` |
| Hermes Agent | unrelated reference | v0.21.7 release candidates (rc.9, 2026-10-09); daily canaries | MIT | UNVERIFIED (terms not reviewed) | repo install script (`scripts/install.sh`); version pin UNVERIFIED | Y (`OPENAI_BASE_URL`, per the Harbor adapter) | `hermes --yolo chat -q "<prompt>" -Q` |

Sources for every row are in the per-harness sections below.

### Key takeaways for Buffon

- **Mock wire protocols needed:** OpenAI Chat Completions covers the Pi family, OpenCode, Copilot BYOK, Goose, Crush, Aider, Qwen and Kimi. Codex needs the OpenAI **Responses** API. Claude Code needs **Anthropic Messages**. Gemini CLI needs Gemini **generateContent**. See §4 cross-cutting findings.
- **Shared state directory:** Pi, Pi-Bolt, pi_agent_rust and sky-valley/pi all use `~/.pi/agent`, and rcarmo/gi falls back to and creates files there. Use a fresh HOME plus the per-harness dir env vars on every run.
- **Phone-home defaults to turn off:** Pi/Pi-Bolt (`PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0`), PiG (`PIG_OFFLINE=1`, same `PI_*`), omp Auto QA (`PI_AUTO_QA`), OpenCode autoupdate, Copilot (`COPILOT_OFFLINE=true`, `COPILOT_AUTO_UPDATE=false`), Claude Code (`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`), Codex `[analytics] enabled=false`, Gemini/Qwen usage statistics, Crush metrics, rpi (`RPI_OFFLINE=1`).
- **Pi extension compatibility:** native in Pi (Node and Bun) and Pi-Bolt; PiG through a Node sidecar; omp through a legacy-Pi shim layer (completeness UNVERIFIED); pi_agent_rust through embedded QuickJS (partial). gi, the other ports and all reference agents have none.
- **Headless gaps:** rcarmo/gi has no print/JSON mode (needs a REST/SSE or tmux driver). pie has none documented. Crush and Aider have no JSON output.
- **ACP as a common driver:** the [ACP registry](https://github.com/agentclientprotocol/registry) lists 42 agents (retrieved 2026-10-10), and Harbor now ships a generic ACP runner beside its named adapters (§5). An arm that speaks ACP can be driven without a PTY. Pi is listed through the third-party `pi-acp` adapter, which runs `pi --mode rpc`.
- **Newly listed arms and their wire APIs:** Antigravity CLI needs the Gemini API, as Gemini CLI does. jcode and Hermes Agent take an OpenAI-compatible endpoint. Cursor CLI and Factory Droid need a vendor API key, so a local-mock run is UNVERIFIED. Prime Agent's endpoint configuration is UNVERIFIED.

## 2. Licence flags

Only the clauses below restrict benchmarking or related use. All other harnesses in the summary table use plain MIT or Apache-2.0 with no such clause found. This is not legal advice.

### 2.1 pi_agent_rust: OpenAI/Anthropic rider (benchmarking is expressly "use")

Source: [LICENSE](https://raw.githubusercontent.com/Dicklesworthstone/pi_agent_rust/main/LICENSE) (rechecked 2026-10-10). Key sentences, verbatim:

> "Restricted Parties" means OpenAI, L.L.C.; Anthropic, PBC; any of their respective Affiliates; and any person or entity acting directly or indirectly on behalf of, for the benefit of, or under the direction of any of the foregoing (including any officer, director, employee, contractor, agent, consultant, service provider, or representative).

> Notwithstanding any other provision of this License, no rights are granted to any Restricted Party. Any purported license, sublicense, assignment, transfer, or other permission to any Restricted Party is null and void absent the express prior written permission of Jeffrey Emanuel.

> For purposes of this rider, "use" includes, without limitation: copying, modifying, merging, publishing, distributing, sublicensing, selling, transferring, making available, hosting, deploying, executing, benchmarking, testing, analyzing, indexing, or incorporating the Software or any Derivative Works into any dataset, training corpus, evaluation harness, or pipeline for machine learning or other automated systems.

> You may not provide, disclose, distribute, sublicense, sell, lease, lend, host, make available, or otherwise permit access to the Software or any derivative work of the Software (as defined in applicable copyright law) (collectively, "Derivative Works") to or for any Restricted Party.

The full rider, including the termination and injunctive-relief paragraphs, is quoted in §3 under pi_agent_rust. Implications [INFERENCE]: the restriction depends on who runs the benchmark and for whom, not on output. Anyone acting for or on behalf of OpenAI or Anthropic (including contractors and AI agents operated for them) has no licence to execute or benchmark it. Buffon must not redistribute the binary (for example in a published container image), so that it is never "made available" to a Restricted Party, and any copy must carry the rider unmodified. **Note for this project:** if Buffon runs are carried out by an Anthropic- or OpenAI-hosted coding agent on someone's behalf, whether that counts as "acting … on behalf of" a Restricted Party is an open legal question. Resolve it before including this arm.

### 2.2 GitHub Copilot CLI

- [GitHub Terms for Additional Products and Features, "Competitive Benchmarking"](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#competitive-benchmarking), verbatim (reciprocal DeWitt-style):
  > "If you offer a product or service competitive to any GitHub product or service, by using that GitHub product or service, you agree to and hereby waive any restrictions as to GitHub on competitive use and benchmark testing in the terms governing your competitive product or service. If you do not intend to waive such restrictions in your terms of use, you are not allowed to use that GitHub product or service."
- [GitHub Pre-release License Terms §3](https://docs.github.com/en/site-policy/github-terms/github-pre-release-license-terms), which apply to prerelease builds such as 1.0.96-2 (pin a stable build), verbatim:
  > "You may not: a. work around any technical limitations in the software; b. reverse engineer, decompile, or disassemble the software, or otherwise attempt to derive the source code for the software, … d. share, publish, or lease the software;"
- [Copilot CLI LICENSE.md §3](https://github.com/github/copilot-cli/blob/main/LICENSE.md), verbatim: "This License does not grant you the right to: Modify, adapt, translate, or create derivative works of the Software; Redistribute the Software except as expressly permitted in Section 2; …"
- [GitHub Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies) prohibit "using our servers for any form of excessive automated bulk activity". This matters only if runs reach GitHub; `COPILOT_OFFLINE=true` is meant to prevent that.

### 2.3 Claude Code

- [LICENSE.md](https://github.com/anthropics/claude-code/blob/main/LICENSE.md): "© Anthropic PBC. All rights reserved. Use is subject to Anthropic's Commercial Terms of Service."
- [Commercial Terms D.4](https://www.anthropic.com/legal/commercial-terms), verbatim: "D.4. Use Restrictions. Customer may not and must not attempt to (a) access the Services to build a competing product or service, including to train competing AI models or resell the Services except as expressly approved by Anthropic; (b) reverse engineer or duplicate the Services; or (c) support any third party's attempt at any of the conduct restricted in this sentence."
- [Consumer Terms](https://www.anthropic.com/legal/consumer-terms), verbatim:
  - "To develop any products or services that compete with our Services, including to develop or train any artificial intelligence or machine learning algorithms or models or resell the Services."
  - "To decompile, reverse engineer, disassemble, or otherwise reduce our Services to human-readable form, except when these restrictions are prohibited by applicable law."
  - "Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise."
- [Claude Code legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance), verbatim: "The Claude Code binary must not be modified. Claude Code must be installed and run as published by Anthropic, and customers may not remove, disable, or restrict any authentication method built into it."
- No explicit "no benchmarking / no publishing results" clause was found. Whether benchmarking Pi-family harnesses against it counts as "build a competing product" is a legal review item.

### 2.4 Crush: FSL-1.1-MIT

[LICENSE.md](https://github.com/charmbracelet/crush/blob/main/LICENSE.md), verbatim: "A Permitted Purpose is any purpose other than a Competing Use. A Competing Use means making the Software available to others in a commercial product or service that: 1. substitutes for the Software; 2. substitutes for any other product or service we offer using the Software that exists as of the date we make the Software available; or 3. offers the same or substantially similar functionality as the Software." It also says: "Permitted Purposes specifically include using the Software: 1. for your internal use and access; 2. for non-commercial education; 3. for non-commercial research; …" Benchmarking is not restricted. Redistributing Crush inside a commercial product would be.

### 2.5 Amp (Acceptable Use Policy)

[AUP](https://ampcode.com/terms/aup), verbatim: "Only humans may create accounts. You must be a human to create an account. Accounts registered by bots or by other automated methods are not allowed." and "You may not use Amp to engage in automatic or excessive bulk activity or coordinated inauthentic activity, …". No benchmark or reverse-engineering clause was found in the [Terms](https://ampcode.com/terms). Amp also requires an account, which this project's rules forbid creating, so it cannot be run as an arm.

### 2.6 Other notes

- Gemini CLI [tos-privacy.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/resources/tos-privacy.md), verbatim: "Directly accessing the services powering Gemini CLI … using third-party software, tools, or services … is a violation of applicable terms and policies." This governs Google services only and does not apply with a local mock.
- [openxjarvis/pi-mono-python](https://github.com/openxjarvis/pi-mono-python) has no LICENSE file, so no rights are granted. Exclude it.
- The author of "The Harness Problem" ([Stencil, 2026-02-12](https://stencil.so/blog/the-harness-problem)) reports a vendor account being disabled during benchmarking. This shows the ToS risk of benchmarking against real hosted models. A local mock avoids it.
- No ToS pages were found for pi.dev or pi-in-go.dev (HTTP 404). See §3.

## 3. Pi family and required harnesses (per-harness detail)

Each section follows the same 8 items: identity/relation, release, licence, install and pinning, custom endpoint, headless modes, state/telemetry, and extensions.

### Pi on Node

1. **Identity**
   - Repo: https://github.com/earendil-works/pi (`packages/coding-agent`). Site and docs: https://pi.dev, https://pi.dev/docs/latest.
   - TypeScript, ESM. npm `bin` is `pi -> dist/bundle/cli.js`. Requires `engines.node >=22.19.0` ([npm](https://registry.npmjs.org/@earendil-works/pi-coding-agent/latest)).
   - This is the upstream reference implementation.
   - The old package `@mariozechner/pi-coding-agent` is deprecated. Its last version is 0.73.1 (2026-05-07). Every version carries `deprecated: "please use @earendil-works/pi-coding-agent instead going forward"` ([npm](https://registry.npmjs.org/@mariozechner/pi-coding-agent)).
2. **Release**
   - Latest release: v1.1.0, published 2026-10-07 ([release API](https://api.github.com/repos/earendil-works/pi/releases/latest)). npm 1.1.0 was published 2026-10-07 with SLSA provenance and trusted publishing ([npm](https://registry.npmjs.org/@earendil-works/pi-coding-agent/latest)).
   - Latest `main` commit: 2026-10-10, `ea448f4` ([commits](https://api.github.com/repos/earendil-works/pi/commits?per_page=1)).
3. **Licence**
   - MIT, © 2025 Mario Zechner ([LICENSE](https://raw.githubusercontent.com/earendil-works/pi/main/LICENSE)). It has no benchmarking, competitive-use, or AI-use clauses.
   - `pi.dev/terms`, `/tos`, and `/privacy` return HTTP 404, so no ToS was found. Benchmarking restriction: **N**.
4. **Install and pinning**
   - **npm:** `npm install -g --ignore-scripts @earendil-works/pi-coding-agent@1.1.0` ([quickstart](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/quickstart.md)).
     - The docs say plain npm "does not pin transitive dependencies".
     - Dependencies use `^1.1.0` for sibling `@earendil-works/*` packages, and `_hasShrinkwrap: false` ([npm](https://registry.npmjs.org/@earendil-works/pi-coding-agent/latest)).
     - The installer comment claims "Pi publishes npm-shrinkwrap.json", which contradicts registry metadata. Treat it as UNVERIFIED.
   - **Lockfile pin (recommended):** each release ships `pi-coding-agent-install-package.json` and `pi-coding-agent-install-package-lock.json` (lockfileVersion 3). Use them with `npm ci --ignore-scripts`. They are covered by `SHA256SUMS`, and each asset also has a `sha256:` digest in the API ([release](https://github.com/earendil-works/pi/releases/tag/v1.1.0), [build-binaries.yml](https://raw.githubusercontent.com/earendil-works/pi/main/.github/workflows/build-binaries.yml)).
   - **Installer** (`curl -fsSL https://pi.dev/install.sh | sh`):
     - It always resolves `$PI_INSTALLER_API_BASE/latest`, then downloads that version's `package.json` and `package-lock.json`.
     - It has no version env var. The only override is `PI_INSTALLER_API_BASE` ([install.sh](https://pi.dev/install.sh)).
     - It is interactive: it may install Node and prompts on `/dev/tty`. Not suitable for pinning.
   - **Nix:** `nix profile add github:earendil-works/pi/v1.1.0` builds from source ([quickstart](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/quickstart.md)).
   - **Self-update:** `pi update` updates Pi itself. `pi update --models` refreshes catalogs. `pi update` cannot update Nix installs ([cli.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/cli.md)).
     - No automatic self-replace is documented. A startup `pi.dev` latest-version request exists; disable it with `PI_SKIP_VERSION_CHECK` ([env vars](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/environment-variables.md)).
5. **Custom endpoint**
   - Add the endpoint to `<agent-dir>/models.json` under `providers.<name>`, with `baseUrl`, `api`, `apiKey` (supports `$ENV`/`!cmd`), and `models:[{id}]`. The docs cover "OpenAI-, Anthropic-, or Google-compatible endpoint[s]" ([models.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/models.md)).
   - Documented `api` ids include `openai-completions` and `openai-responses` ([models.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/models.md)). The exact Anthropic `api` id (likely `anthropic-messages`) is UNVERIFIED.
   - CLI flags: `--provider`, `--model provider/id`, `--api-key`.
6. **Headless modes** ([cli.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/cli.md), [json.md](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/json.md), [rpc.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/rpc.md))

   | Mode | Flag | Behaviour |
   |---|---|---|
   | Print | `-p` / `--print` | Prints the final assistant text, then exits. Redirected stdio defaults to print mode. |
   | JSON | `--mode json` | Writes a JSONL event stream, then exits. |
   | RPC | `--mode rpc` | JSONL commands on stdin, e.g. `pi --mode rpc --no-session`. |

   Useful benchmark flags:
   - `--no-session`, `--session-dir`
   - `--offline`
   - `-ne` / `--no-extensions`, `--no-mcp`, `-ns`, `-np`, `-nc`
   - `-na` / `--no-approve`
   - `--tools`, `--thinking`
7. **State and telemetry** ([configuration.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/configuration.md), [environment-variables.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/environment-variables.md), [settings.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/settings.md))
   - **State directories:**
     - `~/.pi/agent` contains `settings.json`, `models.json`, `auth.json`, `mcp.json`, `keybindings.json`, `extensions/`, `skills/`, `prompts/`, `themes/`, and sessions.
     - Each project has a `.pi/` directory.
     - The installer's managed install also lives under the agent directory ([install.sh](https://pi.dev/install.sh)).
   - **Relocation env vars:**
     - `PI_CODING_AGENT_DIR` moves the agent directory.
     - `PI_CODING_AGENT_SESSION_DIR` moves session storage.
     - `PI_PACKAGE_DIR` overrides the package directory.
   - **Network to disable for isolation:**
     - Model catalog: Pi "can overlay newer catalog data from pi.dev" ([models.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/models.md)). `PI_OFFLINE=1` / `--offline` disables "automatic network activity, including model catalog refreshes".
     - Version check: `PI_SKIP_VERSION_CHECK=1` disables the `pi.dev` latest-version request.
   - **Telemetry:**
     - `enableInstallTelemetry` defaults to **`true`**: "anonymous install/update reporting and selected provider attribution headers". Disable with `PI_TELEMETRY=0` or the setting.
     - `enableAnalytics` defaults to `false`.
     - `@earendil-works/pi-telemetry` 1.1.0 is described as "Vendor-neutral telemetry contracts and typed schema utilities" ([npm](https://registry.npmjs.org/@earendil-works/pi-telemetry/latest)). It is not a runtime dependency of coding-agent 1.1.0, but it is built into the binary build (`build:binary` script). Whether it emits anything by default is UNVERIFIED.
   - **Process markers:** Pi sets `AI_AGENT=pi` and `PI_CODING_AGENT=true` for children.
   - **Recommended isolation env:** `PI_CODING_AGENT_DIR=<tmp> PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0`.
8. **Extensions**
   - Extensions are TypeScript/JS modules (`export default function (pi: ExtensionAPI)`), loaded via `jiti` with no build step.
   - Sources: `~/.pi/agent/extensions/`, `.pi/extensions/`, `-e`, and Pi packages (`pi install npm:…`) ([extensions.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/extensions.md)).
   - This is the reference Pi extension API.

### Pi on Bun

1. **Identity**
   - Pi ships official standalone binaries compiled with Bun. `scripts/build-binaries.sh` runs `bun build --compile --no-compile-autoload-bunfig --no-compile-autoload-dotenv --target=$bun_target ./dist/bun/cli.js …` ([build-binaries.sh](https://raw.githubusercontent.com/earendil-works/pi/main/scripts/build-binaries.sh)).
   - CI uses `oven-sh/setup-bun` with `bun-version: 1.3.14` ([build-binaries.yml](https://raw.githubusercontent.com/earendil-works/pi/main/.github/workflows/build-binaries.yml)).
   - The npm package also has a `build:binary` script with the same `bun build --compile` command ([npm](https://registry.npmjs.org/@earendil-works/pi-coding-agent/latest)).
   - The source has a Bun-specific entry, `dist/bun/cli.js` / `src/bun` (search: [mirror listing](https://wehub.plus/github-featured/earendil-works--pi/src/branch/main/packages/coding-agent/src/bun)). It is the same codebase, not a fork.
2. **Release**
   - Same release as Pi: v1.1.0 (2026-10-07).
   - Binary assets: `pi-darwin-arm64.tar.gz`, `pi-darwin-x64.tar.gz`, `pi-linux-x64.tar.gz`, `pi-linux-arm64.tar.gz`, `pi-windows-x64.zip`, `pi-windows-arm64.zip` ([release](https://api.github.com/repos/earendil-works/pi/releases/latest)).
3. **Licence:** MIT, same as Pi ([LICENSE](https://raw.githubusercontent.com/earendil-works/pi/main/LICENSE)). Benchmarking restriction: **N**.
4. **Install and pinning**
   - **Binary:** download `https://github.com/earendil-works/pi/releases/download/v1.1.0/pi-<os>-<arch>.tar.gz` and check it with `sha256sum -c` against that release's `SHA256SUMS`.
     - CI generates `SHA256SUMS` and verifies it before publishing ([build-binaries.yml](https://raw.githubusercontent.com/earendil-works/pi/main/.github/workflows/build-binaries.yml)).
     - Example: darwin-arm64 = `sha256:3455b13d…63c7` ([release API](https://api.github.com/repos/earendil-works/pi/releases/latest)).
     - The binary embeds the Bun runtime and model data hydrated offline (`--offline-model-data`). The Bun version is fixed by CI (1.3.14).
   - **Bun package manager:** pi.dev's install tabs list `bun add -g --ignore-scripts @earendil-works/pi-coding-agent` and `pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent` (from https://pi.dev/ HTML). `bunx` is not documented.
     - Reproducible variant (my inference): pin `bun@<x>` and run `bun add -g --ignore-scripts @earendil-works/pi-coding-agent@1.1.0`.
     - Note the npm `bin` has a node shebang (`dist/bundle/cli.js`). Whether `bun add -g` runs it under Bun or Node depends on Bun's shebang handling. Force Bun with `bun run --bun $(which pi)` (UNVERIFIED whether Pi supports this path; the official Bun target is the compiled binary).
   - **Self-update:** behaviour of `pi update` inside compiled binaries is UNVERIFIED. Use `PI_SKIP_VERSION_CHECK=1`.
5. **Custom endpoint:** same `models.json` as Pi ([models.md](https://raw.githubusercontent.com/earendil-works/pi/main/packages/coding-agent/docs/models.md)).
6. **Headless modes:** same flags as Pi. CI smoke-tests binaries with `--help`, `--version`, and a codemode script ([build-binaries.yml](https://raw.githubusercontent.com/earendil-works/pi/main/.github/workflows/build-binaries.yml)).
7. **State and telemetry:** same as Pi (`PI_CODING_AGENT_DIR`, `PI_OFFLINE`, `PI_SKIP_VERSION_CHECK`, `PI_TELEMETRY=0`). The `--no-compile-autoload-dotenv`/`bunfig` flags mean the binary does not auto-read `.env`/`bunfig.toml` from the cwd ([build-binaries.sh](https://raw.githubusercontent.com/earendil-works/pi/main/scripts/build-binaries.sh)).
8. **Extensions:** same Pi extension API via jiti, assumed. Support for extensions with native or npm dependencies inside the compiled binary is UNVERIFIED.

### PiG (Pi in Go)

1. **Identity**
   - Repo: https://github.com/MichaelKinsy/PiG. Site: https://pi-in-go.dev.
   - Go module `github.com/MichaelKinsy/PiG`, binary `pig`, built with Go 1.27.2 ([README](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/README.md)).
   - "Pi … rebuilt in Go as one native binary … runs Pi's TypeScript extensions unchanged."
   - Relationship: an independent reimplementation/port that tracks a pinned Pi release as its "behavior oracle". "PiG is not an official Pi release. The Pi maintainers do not endorse PiG." Created by Michael Kinsy at Hewlett Packard Enterprise ([README](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/README.md)).
   - Pi pin inconsistency:
     - The README badge and docs say Pi 1.0.3 ([docs](https://pi-in-go.dev/docs/latest/)).
     - The README's "Compatibility philosophy" paragraph still says "0.99.1 at commit d86654a…" (stale text).
     - NOTICE references Pi 0.87.1 runtime dependencies.
2. **Release**
   - Latest release: v0.4.1, published 2026-10-05. It is marked `immutable: true` ([release API](https://api.github.com/repos/MichaelKinsy/PiG/releases/latest)). Release notes: "PiG 0.4.1 follows Pi 1.0.3."
   - npm `@pi-in-go/pig` 0.4.1 was published 2026-10-05 ([npm](https://registry.npmjs.org/@pi-in-go/pig)).
   - Latest `main` commit: 2026-10-10, `74f806c` (signed) ([commits](https://api.github.com/repos/MichaelKinsy/PiG/commits?per_page=1)).
3. **Licence**
   - MIT, © Hewlett Packard Enterprise Development LP ([LICENSE](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/LICENSE)). The repo is REUSE/SPDX-annotated.
   - [NOTICE](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/NOTICE) preserves Pi's MIT notice and lists embedded third-party JS (highlight.js, marked, jiti, undici, …). Some entries are BSD-3-Clause, ISC, or BlueOak-1.0.0.
   - No ToS found (`pi-in-go.dev/terms` returns 404). Benchmarking restriction: **N**.
4. **Install and pinning** ([README](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/README.md), [install.sh](https://pi-in-go.dev/install.sh))
   - **Installer:** `curl -fsSL https://pi-in-go.dev/install.sh | PIG_VERSION=0.4.1 sh`.
     - It verifies the archive against the release `SHA256SUMS` and refuses if it is missing.
     - Other env vars: `PIG_INSTALL_DIR`, `PIG_DOWNLOAD_BASE`, `PIG_API_BASE`, `PIG_UPDATE_URL`, `PIG_HOME`.
     - It writes an install receipt under `PIG_HOME`.
   - **Go:** `go install github.com/MichaelKinsy/PiG/cmd/pig@v0.4.1`. The README says to use an exact tag; the root module and `extensions/sdk/vX` are tagged on the same commit.
   - **npm:** `npm install -g @pi-in-go/pig@0.4.1`.
     - npm pulls the native binary from optional dependency `@pi-in-go/pig-<os>-<cpu>@0.4.1`, so don't use `--omit=optional`.
     - Node runs only a launcher.
   - **Release assets:** per-platform tarballs, `SHA256SUMS`, `EVIDENCE-SHA256SUMS`, SPDX/CycloneDX SBOMs, Grype SARIF, and license CSVs ([release API](https://api.github.com/repos/MichaelKinsy/PiG/releases/latest)).
   - **Self-update:** `pig update` updates standalone installs via a signed `update.json` manifest (`PIG_UPDATE_URL`, `PIG_UPDATE_TRUST_ROOT`). It does not replace npm installs ([cli.md](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/cli.md), [env vars](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/environment-variables.md)).
   - **Disable checks:** `PI_SKIP_VERSION_CHECK=1` stops the startup release check. `PIG_OFFLINE=1` stops package-update checks. The docs warn: "Set `PIG_OFFLINE` in CI. Without it, every run checks for updates and fails slowly when the network is blocked."
5. **Custom endpoint**
   - Declared in `~/.pig/agent/models.json`, with the same schema as Pi (`providers.<name>.baseUrl/api/apiKey/models`, e.g. `"api": "openai-completions"`) ([providers](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/providers.md), [custom-provider](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/custom-provider.md)).
   - "PiG and Pi 1.0.3 use compatible settings, auth and session formats" ([configuration](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/configuration.md)).
   - PiG's own eval mock speaks OpenAI Chat Completions, OpenAI Responses, and Anthropic Messages ([evals.md](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/evals.md)).
6. **Headless modes**
   - `pig --print <prompt>`, `pig --mode json --model <p/m> "prompt"` (JSONL), and `pig --mode rpc` (JSONL on stdin/stdout, compatible with Pi's TS `RpcClient`) ([cli.md](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/cli.md), [json.md](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/json.md), [rpc.md](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/rpc.md)).
   - Other benchmark flags: `--offline`, `--no-extensions`, `--no-session`, `--session-id`.
   - `pig --version` prints `<PiG>+<Pi>`, e.g. `0.4.1+1.0.3`.
7. **State and telemetry** ([environment-variables.md](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/environment-variables.md), [configuration](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/configuration.md), [settings](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/settings.md))
   - **Directories:**
     - Root is `~/.pig`, overridable by `PIG_HOME`, or `$XDG_CONFIG_HOME/pig` when `PIG_HOME` is unset.
     - The agent directory is `~/.pig/agent` (`PIG_CODING_AGENT_DIR`).
     - Sessions follow `PIG_CODING_AGENT_SESSION_DIR`.
     - Docs are materialized into `~/.pig/docs/`.
     - PiG does not touch `~/.pi` unless `PIG_USE_PI_DIRS=1`. In that shared mode it uses `PI_CODING_AGENT_DIR`.
     - Diagnostics go to `exit.log` and `crashes.json` in the agent directory, and to `pig-debug.log` in `$TMPDIR`.
   - **Telemetry:**
     - `enableInstallTelemetry` defaults to **`true`**. It sends one GET to `https://pi-in-go.dev/api/report-install?version=…` after a fresh install or an update with new changelog entries, and it gates OpenRouter/NVIDIA/Cloudflare attribution headers.
     - Opt out with `PI_TELEMETRY=0`. `PI_OFFLINE=1` also stops it. `PIG_INSTALL_TELEMETRY_URL` redirects it.
     - `enableAnalytics` defaults to `false`; "nothing sends data".
   - **Other network:** the Radius model-list fetch only happens with Radius credentials, and offline mode disables it.
   - **Process marker:** PiG sets `AI_AGENT=pig` (divergence D26).
   - **Recommended isolation env:** `PIG_HOME=<tmp> PIG_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0`.
8. **Extensions**
   - PiG supports Go, Rust, Python, and Node extensions through a subprocess host ([extensions](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/extensions.md)).
   - Node/TS: "Export one Pi-compatible default extension function. Pig runs each Node factory in an isolated Node subprocess. Import … `@earendil-works/pi-coding-agent`. Pig supplies the compatible runtime module" ([extension-authoring](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/extension-authoring.md)).
     - So the mechanism is a **Node sidecar, not an embedded JS engine**. Sources are loaded through jiti, and Node cells may be "packed" ([runtime cells](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/extension-runtime-cells.md)).
     - A system Node.js is presumably required for TS extensions, but no explicit version requirement was found (UNVERIFIED). The runtime-cells doc's phrase "embedded Node runtime" seems to mean embedded runtime modules (see [NOTICE](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/NOTICE)).
   - Documented known gaps: D78 (Provider objects), D82 (partial messages), D83 (cross-process event-bus ordering).
   - **Piglets:** a YAML composition of extensions, skills, tools, prompts, and model preferences (`pig --piglet x.yaml`). It can be built into a native binary with `pig piglet build … --format binary` ([docs](https://pi-in-go.dev/docs/latest/)).
   - **Published PiG-vs-Pi benchmark:** [docs/site/docs/evals.md](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/docs/site/docs/evals.md), produced by `make evals` (`pigeval overhead`). The harness registry is `test/evals/harnesses.toml`; budgets are `test/evals/budgets.toml`; `make release-check` includes `parity-perf` ([Makefile](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/Makefile)).
     - Setup: measured 2026-09-23 on Linux x86_64 with 1 CPU, against a local mock model, 1 warm-up plus 10 runs, both at 0.87.1.
     - The page says PiG's `--version` output at the time printed only the pinned Pi release.

     | Scenario | PiG median / peak RSS | Pi median / peak RSS |
     |---|---|---|
     | Startup (`--version`) | 21.5 ms / 24.6 MiB | 300.3 ms / 101.5 MiB |
     | One prompt | 29.1 ms | 439.8 ms |
     | Resume a 2,000-exchange session | 128.7 ms | 614.6 ms |

     - No `.github/workflows/{bench,benchmark,startup,perf,performance}.yml` exists (HTTP 404). Benchmarks run via the Makefile, not a dedicated workflow. Other workflow names are UNVERIFIED because the GitHub tree API was rate-limited.
     - Related upstream issue: "Setup a Pi startup benchmark" ([pi#7639](https://github.com/earendil-works/pi/issues/7639)).

### omp (oh-my-pi)

1. **Identity**
   - Repo: https://github.com/can1357/oh-my-pi; homepage: https://omp.sh. Not marked as a GitHub fork. Description: "Coding agent with the IDE wired in. Built by Stencil Labs." (https://api.github.com/repos/can1357/oh-my-pi)
   - Languages: TypeScript on Bun, plus a Rust N-API core of about 80k lines. The npm package requires `"engines": {"bun": ">=1.3.14"}`. (README: https://github.com/can1357/oh-my-pi#readme; npm: https://registry.npmjs.org/@oh-my-pi/pi-coding-agent/latest)
   - Relationship to Pi: a **fork**. The README says "Fork of Pi by @mariozechner" and "omp is a fork of pi-mono by Mario Zechner" (https://raw.githubusercontent.com/can1357/oh-my-pi/main/README.md).
   - The npm author field is "Stencil Labs, Inc."; early 1.337.x versions list "Mario Zechner" as author (https://registry.npmjs.org/@oh-my-pi/pi-coding-agent).
   - Binary name: `omp`. The 1.337.x versions shipped the binary as `pi`.
2. **Release**
   - npm `latest` = 18.8.9, published 2026-10-10T17:21:47Z (https://registry.npmjs.org/@oh-my-pi/pi-coding-agent).
   - Default branch `main`; last push 2026-10-10T23:34:53Z (`pushed_at`, https://api.github.com/repos/can1357/oh-my-pi).
   - Changelog: https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/CHANGELOG.md
3. **Licence**
   - MIT: https://github.com/can1357/oh-my-pi/blob/main/LICENSE. Copyright holders: Mario Zechner, Can Bölük and Stencil Labs.
   - Vendored code keeps its upstream licence (`crates/vendor/brush-core`, `crates/pi-builtins/LICENSE`, `THIRD-PARTY-NOTICES.txt`; see the README).
   - No clauses restricting benchmarking or competitive use were found. Note that the README itself publishes benchmark claims ("benchmaxxed").
4. **Install / pin**
   - `bun install -g @oh-my-pi/pi-coding-agent@18.8.9`
   - Checksums: npm provides `integrity` (sha512), signatures and SLSA provenance attestations (https://registry.npmjs.org/@oh-my-pi/pi-coding-agent/latest). `_hasShrinkwrap: false` was observed on 1.337.x; it is not checked for 18.8.9 (UNVERIFIED).
   - Binary: `curl -fsSL https://omp.sh/install | sh -s -- --binary --ref v<version>`. The script downloads from `build.stencil.so` and "check[s] its SHA-256 before installing it" (README).
   - Other installs: Homebrew `brew install can1357/tap/omp`, Nix flake `nix run github:can1357/oh-my-pi`, and `mise use -g github:can1357/oh-my-pi` (README).
   - Self-update: there is no auto-install of omp itself; `omp update` is manual. A startup update *check* exists (setting `startup.checkUpdate`, default `true`). According to the npm tarball source (`src/main.ts`), `checkForNewVersion` is only called on the interactive branch, not for print/RPC modes.
   - Plugin auto-update: `marketplace.autoUpdate` defaults to `notify`; set it to `off` to disable (`src/modes/settings.ts` in the 18.8.9 tarball).
5. **Custom endpoint**
   - Define providers in `~/.omp/agent/models.yml` with `baseUrl`, `api: openai-completions | openai-responses | anthropic-messages | …`, `apiKey` and `models` (README section "Custom OpenAI-compatible providers").
   - Select the default model with `modelRoles.default: <provider>/<model>` in `~/.omp/agent/config.yml`, or with `--model`.
   - Documentation: https://omp.sh/docs/providers
6. **Headless modes** (README section "Four entry points")
   - `omp -p` / `--print`: one-shot.
   - `--mode text|json|rpc|rpc-ui|acp`: the mode enum is in `src/cli/args.ts` of the tarball.
   - `omp --mode rpc --no-session`: NDJSON commands in, event frames out; `--no-ui` suppresses extension dialogs.
   - `omp acp`: Agent Client Protocol.
   - SDK: `createAgentSession`.
   - `--no-extensions` and `--trusted-extension <path>` narrow ambient discovery.
7. **Config/state dirs + telemetry**
   - Default dir: `~/.omp/agent`, holding `models.yml`, `config.yml`, `sessions/` and more.
   - `PI_CODING_AGENT_DIR` = "Session storage directory (default: ~/.omp/agent)". Also `PI_CODING_AGENT_SESSION_DIR`, `OMP_PROFILE` / `--profile` ("Named profile for isolated agent state"), and `PI_PACKAGE_DIR` (source: `src/cli/help-extra.ts` in the tarball).
   - Other paths written under `~/.omp`: `~/.omp/plugins`, `~/.omp/logs`, `~/.omp/cache/github-cache.db`, `~/.omp/autoqa.db` (or `$XDG_DATA_HOME/omp/autoqa.db`) (tarball source). **Isolating HOME covers all of these.**
   - Reads other tools' configs: on first run omp inherits `.claude`, `.cursor`, `.codex`, `.gemini` and `.github/copilot` rules, skills and MCP configs (README "Discovery"). An isolated HOME and clean workdir avoid this.
   - Telemetry, part 1 (OTLP): export is registered only "when an `OTEL_*` endpoint is" configured; setting `telemetry.otlpExportEnabled` (`src/telemetry-export-otlp.ts`, `src/main.ts`).
   - Telemetry, part 2 (Auto QA): `dev.autoqa` defaults to `true` (env `PI_AUTO_QA`). The first report asks for consent and pushes to `https://qa.omp.sh/v1/grievances` (`src/tools/settings.ts`). Disable with `PI_AUTO_QA=0`; the exact accepted value is UNVERIFIED.
   - Inference: this telemetry source information comes from reading the npm tarball's TS source; omp was not executed.
8. **Extensions / Pi compatibility**
   - Extensions are TypeScript modules using the same tool API, slash-command registry and TUI primitives as built-ins. Plugins come from a marketplace or npm; reload with `/reload-plugins` (README).
   - **Explicit Pi-extension compatibility layer**: the `src/extensibility/plugins/legacy-pi-compat.ts` file defines `PI_SCOPE_ALIASES = ["oh-my-pi", "mariozechner", "earendil-works"]`.
   - The same directory has shims re-exporting the upstream API: `legacy-pi-coding-agent-shim.ts`, `legacy-pi-ai-shim.ts` and `legacy-pi-tui-shim.ts` ("@earendil-works/pi-coding-agent or @mariozechner/pi-coding-agent").
   - So Pi extensions importing `@mariozechner/*` or `@earendil-works/*` are remapped. How complete this coverage is: UNVERIFIED.

### OpenCode

1. **Identity**
   - Canonical repo: https://github.com/anomalyco/opencode (formerly sst/opencode; the `sst` redirect is not verified). Default branch `dev`. Docs: https://opencode.ai/docs/ (https://api.github.com/repos/anomalyco/opencode)
   - Runtime: TypeScript/Bun, distributed as compiled per-platform binaries via npm optionalDependencies (`opencode-darwin-arm64`, etc.) (https://registry.npmjs.org/opencode-ai/1.18.35).
   - Relationship to Pi: **unrelated**; included only as a comparison point.
2. **Release**
   - v1.18.35, published 2026-10-06T20:18:39Z. The release is marked `immutable: true` (https://github.com/anomalyco/opencode/releases/tag/v1.18.35).
   - npm `opencode-ai@1.18.35` published 2026-10-06T20:21:30Z.
   - Newer: v1.19.0, npm `opencode-ai@1.19.0` published 2026-10-11T01:38:53Z, GitHub release dated 2026-10-11T01:39:22Z (https://registry.npmjs.org/opencode-ai, https://opencode.ai/changelog). Its notes include "Made session compaction keep complete recent turns" and "Surface resumable subagent failures".
   - Last push to the repo: 2026-10-10T23:19:17Z.
   - **OpenCode v2 is released and is a separate npm package.** `@opencode/cli` has npm `latest` = 2.0.29 (published 2026-10-14T09:03:04Z); 2.0.0 was published 2026-09-11T23:44:52Z and 2.0.0 to 2.0.29 are all on the registry; `beta` and `dev` tags carry `0.0.0-beta-*` / `0.0.0-dev-*` builds (https://registry.npmjs.org/@opencode/cli). The docs home (https://opencode.ai/docs) shows "New OpenCode v2 is now available", https://opencode.ai/v2 is the v2 docs and install page, and https://opencode.ai/changelog lists v2.0.29 (2026-10-14) at its head. Source is the same repo (`repository` in the package is `anomalyco/opencode`); `v2.0.0` and `v2.0.29` git tags exist, but GitHub Releases still lists v1.19.0 as Latest and has no v2 release (`gh release view v2.0.29` finds none), so v2 ships through npm, `https://opencode.ai/v2/install`, Homebrew `anomalyco/tap/opencode-v2`, the zip/tar downloads at `opencode.ai/update/api/latest/cli/...` and `ghcr.io/anomalyco/opencode:2.0.0`-style Docker tags.
   - v2 is a different CLI, not a flag: the command is still `opencode` (V1 and V2 "are no longer installed side by side by default"; the npm package also installs a `opencode2` bin), and the V2 npm package is `@opencode/cli` with platform packages `@opencode/cli-<os>-<arch>[-baseline][-musl]` and the same stub-plus-postinstall layout as `opencode-ai` (https://opencode.ai/v2/docs/migrate-v1/, https://opencode.ai/v2/docs). Breaking changes the docs list: a new plugin API, new server API and client contracts, and terminal config moved to a single global `cli.json`. Supported V1 server config keeps loading, but the native V2 shape differs: `providers` (not `provider`) with `package = "@opencode/ai/providers/openai-compatible"` and `settings.baseURL` (https://opencode.ai/v2/docs/providers/), ordered `permissions` rules `{action, resource, effect}` (not `permission`/`bash`), `update: "disable"` (not `autoupdate`), `share` `manual|auto|disabled`. Headless mode is `opencode run [message]` with `--model provider/model#variant`, `--format default|json`, `--auto`, `--continue/--session`, `--file`, `--agent`; the CLI talks to a shared background service by default, and `--standalone` runs a private server in the process instead (https://opencode.ai/v2/docs/cli/, https://opencode.ai/v2/docs/cli/commands/; checked against `opencode run --help` of 2.0.29). Network settings and `OPENCODE_DISABLE_MODELS_FETCH` / `OPENCODE_DISABLE_AUTOUPDATE` are read by 2.0.29 (strings of the binary; with them set no outbound connection was seen).
   - **Buffon arms**: `opencode` pins `opencode-ai` 1.19.0 and `opencode-v2` pins `@opencode/cli` 2.0.29, both by integrity and package-lock; observed with HTTPS_PROXY pointed at a local sink and a mock endpoint: without `OPENCODE_DISABLE_MODELS_FETCH` both versions connect to `models.opencode.ai:443`, and 1.19.0 additionally asks the npm registry for `@opencode-ai/plugin` on every start in a fresh HOME (a detached background install of the config directory's dependencies; `npm_config_offline=true` stops it, `--pure` and `OPENCODE_DISABLE_DEFAULT_PLUGINS` do not). A 1.19.0 `run` without an allow rule fails with "The user rejected permission to use this specific tool call"; the arms write an allow-all permission rule into `opencode.json`. Both print and pty modes completed against the mock with no egress (`python3 -m buffon arm verify`), each sending a tool-less title request before the scripted turn.
3. **Licence**
   - MIT (https://github.com/anomalyco/opencode/blob/dev/LICENSE; the npm package also contains LICENSE).
   - No benchmarking or competitive-use clauses found in the repo licence.
   - The hosted "Zen"/"Go" service ToS was not reviewed (UNVERIFIED); it is not needed when using a local mock model.
4. **Install / pin**
   - npm: `npm i -g opencode-ai@1.18.35`. The npm package runs a `postinstall` script (`node ./postinstall.mjs`).
   - Script: `curl -fsSL https://opencode.ai/install | VERSION=1.18.35 bash`. It reads `requested_version=${VERSION:-}`, installs to `$HOME/.opencode/bin` and edits shell rc files (https://opencode.ai/install). The script does no checksum check (none found when grepping it).
   - Release zips carry GitHub `digest: sha256:…` values, e.g. `opencode-darwin-arm64.zip` sha256:80b05124… (https://api.github.com/repos/anomalyco/opencode/releases/latest).
   - Brew availability is not verified here.
   - Upgrade: `opencode upgrade [target]` (https://opencode.ai/docs/cli/).
   - Autoupdate: on by default. The docs say: "OpenCode will automatically download any new updates when it starts up. You can disable this with the `autoupdate` option". Set `"autoupdate": false` or `"notify"` (https://opencode.ai/docs/config/#autoupdate).
   - Env alternative: `OPENCODE_DISABLE_AUTOUPDATE=true` (https://opencode.ai/docs/cli/).
   - Also set `OPENCODE_DISABLE_MODELS_FETCH` (stops fetching models from models.dev) and `OPENCODE_DISABLE_LSP_DOWNLOAD`.
5. **Custom endpoint**
   - Add a `provider.<id>` entry in `opencode.json` with `"npm": "@ai-sdk/openai-compatible"`, `"options": {"baseURL": "http://127.0.0.1:PORT/v1"}` and `"models": {...}` (https://opencode.ai/docs/providers/).
   - Inline config: `OPENCODE_CONFIG_CONTENT`. Custom config file: `OPENCODE_CONFIG`.
   - Anthropic-compatible endpoints: likely possible via `@ai-sdk/anthropic` with `options.baseURL` (UNVERIFIED).
6. **Headless modes**
   - `opencode run "<prompt>" --format json` gives raw JSON events. `--auto` auto-approves permissions that are not explicitly denied. Other flags: `-m provider/model`, `--dir`, `--attach`.
   - `opencode serve` starts a headless HTTP server.
   - Source: https://opencode.ai/docs/cli/
7. **Dirs + telemetry**
   - Config: `~/.config/opencode/opencode.json`, `tui.json` and `plugins/`.
   - Data: `~/.local/share/opencode/`, including `auth.json`, `log/` and `storage` (https://opencode.ai/docs/troubleshooting/).
   - Plugin cache: `~/.cache/opencode/node_modules/` (https://opencode.ai/docs/plugins/).
   - Other paths: install dir `~/.opencode/bin`; project config `opencode.json` and `.opencode/`.
   - Managed config: `/Library/Application Support/opencode/` and `/etc/opencode/`. These are outside HOME, so isolating HOME does not cover them.
   - Remote config: fetched from `.well-known/opencode` (https://opencode.ai/docs/config/).
   - Env relocation: `OPENCODE_CONFIG_DIR`. Whether `XDG_CONFIG_HOME`/`XDG_DATA_HOME` are honoured is UNVERIFIED; set them anyway.
   - Claude Code files: OpenCode reads `.claude` files; disable with `OPENCODE_DISABLE_CLAUDE_CODE=1`.
   - Telemetry: no product telemetry setting found in the config or CLI docs (UNVERIFIED).
   - Sharing defaults to `"manual"`; `"share": "disabled"` turns it off. Auto-share is enabled by `OPENCODE_AUTO_SHARE` (https://opencode.ai/docs/config/).
8. **Plugins**
   - JS/TS plugins load from `.opencode/plugins/`, `~/.config/opencode/plugins/`, or npm packages listed in config. npm plugins are auto-installed with Bun at startup (https://opencode.ai/docs/plugins/).
   - `OPENCODE_DISABLE_DEFAULT_PLUGINS` disables the defaults. MCP is supported.
   - Cannot load Pi extensions (different API).

### GitHub Copilot CLI (closed-source comparison point)

1. **Identity**
   - Repo: https://github.com/github/copilot-cli. It holds docs, issues, the changelog and the install script; it is not the source code. npm package: `@github/copilot` (https://registry.npmjs.org/@github/copilot/latest).
   - Built from a private `copilot-agent-runtime` repo (`_resolved` path in the npm metadata). Ships native per-platform packages such as `@github/copilot-darwin-arm64`.
   - Relationship to Pi: **unrelated**, closed source.
2. **Release**
   - npm `latest` 1.0.95, published 2026-10-09T16:04:52Z; there is also `prerelease` 1.0.96-2.
   - Changelog entry: "## 1.0.95 - 2026-10-09" (https://github.com/github/copilot-cli/blob/main/changelog.md).
   - Repo last push: 2026-10-10T02:13:47Z.
3. **Licence**
   - SPDX `NOASSERTION`; npm declares `"SEE LICENSE IN LICENSE.md"` (https://github.com/github/copilot-cli/blob/main/LICENSE.md).
   - Licence text, verbatim:
     - §3: "This License does not grant you the right to: Modify, adapt, translate, or create derivative works of the Software; Redistribute the Software except as expressly permitted in Section 2; …"
     - §8: "Your use of each service is subject to the terms, agreements, and privacy notices applicable to that service".
   - **FLAG: GitHub Terms for Additional Products and Features, "Competitive Benchmarking"** (https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#competitive-benchmarking), verbatim:
     > "If you offer a product or service competitive to any GitHub product or service, by using that GitHub product or service, you agree to and hereby waive any restrictions as to GitHub on competitive use and benchmark testing in the terms governing your competitive product or service. If you do not intend to waive such restrictions in your terms of use, you are not allowed to use that GitHub product or service."

     This is a reciprocal DeWitt-style clause. It does not ban publishing benchmark results, but it binds anyone offering a competing product.
   - **Copilot terms routing** (same page, "GitHub Copilot" section): "For all other GitHub Copilot users, your use of GitHub Copilot is governed by [Section J (AI Features) of the GitHub Terms of Service]". Business/Enterprise users who buy directly are governed by the GitHub Generative AI Services Terms; Microsoft purchases by Microsoft Product Terms (not reviewed, UNVERIFIED).
   - **FLAG: GitHub Pre-release License Terms §3** (https://docs.github.com/en/site-policy/github-terms/github-pre-release-license-terms) apply to prerelease builds such as 1.0.96-2. Verbatim: "You may not: a. work around any technical limitations in the software; b. reverse engineer, decompile, or disassemble the software, or otherwise attempt to derive the source code for the software, … d. share, publish, or lease the software;"
   - The same pre-release terms state: "The software will collect data and usage information about events generated when interacting with it."
   - **GitHub ToS, automation**: "Accounts registered by "bots" or other automated methods are not permitted. We do permit machine accounts" (https://docs.github.com/en/site-policy/github-terms/github-terms-of-service).
   - **Acceptable Use Policies**: prohibit "using our servers for any form of excessive automated bulk activity" (https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies).
   - **ToS §J**: Inputs and Outputs may be used for training "unless (a) you opt out through your account settings" (ToS link above).
   - No ban on publishing benchmark results specifically was found.
4. **Install / pin**
   - npm: `npm i -g @github/copilot@1.0.95`. Platform binaries come via optionalDependencies; `_hasShrinkwrap: false`.
   - Script: `curl -fsSL https://gh.io/copilot-install | VERSION="v1.0.95" PREFIX="$HOME/x" bash`. It downloads `releases/download/${VERSION}/SHA256SUMS.txt` and validates the download against it (https://gh.io/copilot-install; README https://github.com/github/copilot-cli#readme).
   - Other installs: `brew install copilot-cli`, `winget install GitHub.Copilot`.
   - Auto-update: on by default. Disable with `--no-auto-update` or `COPILOT_AUTO_UPDATE=false`; the latter also covers first-party plugins.
   - The changelog says "auto-update is disabled in CI environments by default" (https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference; changelog).
5. **Custom endpoint: YES (BYOK)**
   - Required env vars: `COPILOT_PROVIDER_BASE_URL` and `COPILOT_MODEL`.
   - Optional: `COPILOT_PROVIDER_TYPE=openai|azure|anthropic` (default `openai` Chat Completions), `COPILOT_PROVIDER_API_KEY`, `COPILOT_PROVIDER_WIRE_API`, `COPILOT_PROVIDER_MAX_PROMPT_TOKENS`, and others. Source: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-byok-models
   - Requirement: models must support tool calling and streaming.
   - `COPILOT_OFFLINE=true` is meant "to prevent it from contacting GitHub's servers" (same page).
   - Alternatively, a JSON registry file via `COPILOT_PROVIDERS_CONFIG` (default `<COPILOT_HOME>/providers.json`) (CLI reference).
   - Whether GitHub login is still required with BYOK + offline: inferred to be no; UNVERIFIED.
6. **Headless modes**
   - `copilot -p "<prompt>" --allow-all-tools --output-format json -s`. `--output-format json` gives JSONL; `--allow-all-tools` is "Required when using the CLI programmatically" (env `COPILOT_ALLOW_ALL`).
   - `--allow-all` / `--yolo` grant all permissions.
   - ACP server mode exists (changelog). CLI reference: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
   - In `-p` mode, project extensions, workspace MCP and repo hooks are disabled by default. Enable them with `GITHUB_COPILOT_PROMPT_MODE_EXTENSIONS` / `_WORKSPACE_MCP` / `_REPO_HOOKS`.
7. **Dirs + telemetry**
   - Main dir: `~/.copilot`, overridden by `COPILOT_HOME`; `--config-dir` is deprecated. It contains `settings.json`, `config.json` (auth/state), `logs/`, `session-state/`, `extensions/`, `installed-plugins/` and `plugin-data/` (https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference).
   - Old XDG locations are "migrated to `~/.copilot` at startup".
   - Cache: `~/Library/Caches/copilot` on macOS, `$XDG_CACHE_HOME/copilot` on Linux. It is **not** covered by `COPILOT_HOME`; use `COPILOT_CACHE_HOME`.
   - Token: stored in the OS keychain, falling back to `~/.copilot`.
   - Telemetry: OpenTelemetry export is opt-in. The pre-release terms state that usage data is collected, and the changelog mentions "flushes pending telemetry before exit".
   - No documented opt-out for product telemetry was found (UNVERIFIED). `COPILOT_OFFLINE=true` is the documented way to stop GitHub contact.
8. **Plugins/extensions**
   - Plugins and marketplaces (`copilot plugin`), MCP servers, skills, hooks, custom agents, and `~/.copilot/extensions/` (CLI reference / config-dir reference).
   - Cannot load Pi extensions.

### Other Pi ports, forks and derivatives (incl. Pi-Bolt, gi, pi_agent_rust)

#### Pi-Bolt

1. **Repo/runtime/relation**: https://github.com/opensec-git/Pi-Bolt (GitHub-flagged fork of `earendil-works/pi`, default branch `pi-bolt`), site https://pi-bolt.opensec.in. Pi's TypeScript bundled by Bun to JavaScriptCore bytecode, then "every function" compiled AOT to x86-64/ARM64 machine code via JSC's B3 backend, plus a prebuilt heap mapped at launch; builds on oven-sh/WebKit#743. "Pi-Bolt is an independent fork of Pi, not affiliated with Pi's authors or with Oven." `packages/` = the Pi release named in `sources.json` plus Pi-Bolt changes; engine changes in `patches/`. Source: https://github.com/opensec-git/Pi-Bolt (README "How it works"). 226 stars at time of reading.
   - Searches that found it: npm search `text=pi-bolt` → package `pi-bolt` (https://registry.npmjs.org/-/v1/search?text=pi-bolt&size=10). `pibolt` npm search: 0 results; web searches for "pi-bolt"/"pibolt"/"Pi Bolt" returned nothing relevant.
2. **Release**: release `bolt-v0.8.0` "Pi-Bolt 0.8.0", 2026-10-10, "with Pi 1.1.0 on all three [platforms]" (https://github.com/opensec-git/Pi-Bolt/releases.atom) — newer than `bolt-v0.7.4`/`bolt-v0.7.3`. npm `pi-bolt@0.8.0` published 2026-10-10 (https://registry.npmjs.org/-/v1/search?text=pi-bolt&size=10). Latest commit on `pi-bolt` branch 2026-10-10T20:38:23Z (https://github.com/opensec-git/Pi-Bolt/commits/pi-bolt.atom). Repo has a `bench/` suite; method in https://github.com/opensec-git/Pi-Bolt/blob/pi-bolt/docs/BENCHMARKS.md.
3. **Licence**: MIT; `Copyright (c) 2025 Mario Zechner` / `Copyright (c) 2026 OpenSec (Pi-Bolt)` — https://raw.githubusercontent.com/opensec-git/Pi-Bolt/pi-bolt/LICENSE. Release executables also bundle Bun (MIT), JavaScriptCore (LGPL-2.0 and BSD), ICU (Unicode License) — README "License". No benchmarking/company restrictions found. Note: README publishes its own benchmark vs PiG and oh-my-pi.
4. **Install & pin**:
   - `curl -fsSL https://pi-bolt.opensec.in/install.sh | PIBOLT_VERSION=bolt-v0.8.0 PIBOLT_VARIANT=x64 PIBOLT_YES=1 PIBOLT_EXTENSIONS=no PIBOLT_INSTALL=<dir> PIBOLT_BIN_DIR=<dir> sh` — env vars from install.sh header (https://raw.githubusercontent.com/opensec-git/Pi-Bolt/pi-bolt/install.sh). Installer verifies `SHA256SUMS` and, from 0.6.0, an Ed25519 signature `SHA256SUMS.sig` against an embedded public key (OpenSSL 3 needed; otherwise checksum-only) and checks the first line `# pi-bolt <version>`.
   - Manual: download `pi-bolt-<platform>.tar.xz` from GitHub release, check `SHA256SUMS` (README "Manual download").
   - npm: `npm install -g --allow-scripts=pi-bolt pi-bolt@0.8.0` — npm package is a 6-file launcher with `postinstall: node install.cjs` that fetches the per-platform package `pi-bolt-<platform>-<variant>@0.8.0`; `_hasShrinkwrap: false` (https://registry.npmjs.org/pi-bolt/latest).
   - Variants: `linux-x64` (AVX2), `linux-x64-baseline`, `linux-x64-jit`, `darwin-arm64`, `darwin-arm64-jit`, `win32-x64`. No Linux ARM64. Requires glibc ≥2.17 (README "Requirements").
   - Self-update: `pi-bolt update` installs latest release (README "Install"). How to disable automatic update notices: Pi's own env vars apply (below); explicit Pi-Bolt switch UNVERIFIED.
   - Installer may offer OpenSec extensions `opensec-pi-subagents`, `opensec-pi-todo` → set `PIBOLT_EXTENSIONS=no` (install.sh).
5. **Custom endpoint**: "Pi-Bolt is the Pi you already use, with the same … settings, providers and extensions"; uses `~/.pi/agent` as is (README). So Pi's `models.json` custom providers apply [INFERENCE from README claim; see Pi core survey].
6. **Headless**: README benchmarks run "one prompt (`pi -p`)". `--mode json` / `--mode rpc` inherited from Pi [INFERENCE].
7. **State/telemetry**: reads/writes Pi's `~/.pi/agent`; "Pi's own variables (`PI_CODING_AGENT_DIR`, `PI_OFFLINE`, ...) work as documented by Pi" (https://raw.githubusercontent.com/opensec-git/Pi-Bolt/pi-bolt/docs/TROUBLESHOOTING.md). Installer default install dir `~/.pi-bolt`, link in `~/.local/bin`. Runtime extension transpile cache in `cache/jiti` under agent dir (`JITI_FS_CACHE=false` disables). Does **not** read `.env` from cwd (from 0.6.0). Crash: prints a `https://pi-bolt.opensec.in/crash/...` link with encoded stack trace for the user to report (not stated to be auto-uploaded) (TROUBLESHOOTING.md). `BUN_AOT=0` forces bytecode (useful A/B control).
8. **Extensions**: "Pi extensions work unchanged." Default build has no JIT → runtime-loaded extensions are interpreted; `-jit` builds for heavy/`bun:ffi` extensions; extensions can be compiled in via `scripts/build-pi.sh --plugins …` (README "Plugins", https://github.com/opensec-git/Pi-Bolt/blob/pi-bolt/docs/PLUGINS.md). Benchmark note: extension performance differs strongly by variant.

#### gi (canonical: rcarmo/gi)

1. **Repo/runtime/relation**: https://github.com/rcarmo/gi — "An elegant Go coding agent, for more civilized times"; "A coding agent built on `go-ai`, informed by lessons learned from Pi, Piclaw, and Vibes"; "If you like `pi`, you should feel very much at home … The goal was not to achieve full parity". Pure-Go single binary with TUI (default) and web UI (`gi -web`), SQLite-backed sessions; "The terminal targets Pi 1.1.0 workflows and keybindings". Inference via https://github.com/rcarmo/go-ai, "A Go port of `@earendil-works/pi-ai`", baseline pi-ai v1.1.0, pinned `e8fe159110e2`. Relation: independent Go reimplementation/port-in-spirit, not a fork. 21 stars. Sources: https://github.com/rcarmo/gi README; https://github.com/rcarmo/go-ai README.
2. **Release**: no tags/releases (https://github.com/rcarmo/gi/tags.atom empty). Latest commit `7078df0d59bf` "Refresh go-ai pin and verify Pi 1.1.0 TUI references", 2026-10-10T07:12:35Z (https://github.com/rcarmo/gi/commits/main.atom). go-ai has release v1.1.0 with CycloneDX SBOM + `.sha256` (go-ai README).
3. **Licence**: MIT, "Copyright (c) 2026 Rui Carmo" — https://raw.githubusercontent.com/rcarmo/gi/main/LICENSE. go-ai: MIT (README badge). No restrictive clauses.
4. **Install & pin**: source only: `git clone https://github.com/rcarmo/gi && git checkout 7078df0d59bf4e763c9d5c80a38f309860c930de && git submodule update --init && make build` (needs Go 1.27.1 per `go.mod`; Bun only to bundle web assets; `bun.lock` + `go.sum` shipped) (README "Development"). `make bootstrap` also installs Playwright — avoid in benchmark builds. Release CI builds cross-platform binaries but no published release found. `gi --version` prints version. Self-update: none documented. Startup background refresh (Copilot creds, `models-store.json` when `modelCatalogUrl` set) is skipped with `PI_OFFLINE=1` (https://raw.githubusercontent.com/rcarmo/gi/main/docs/internal/config-files.md).
5. **Custom endpoint**: providers via go-ai: OpenAI (completions + responses), Anthropic, GitHub Copilot (README "Inference"). gi reads `settings.json`, `auth.json`, `models-store.json`, `mcp.json` — **not** Pi's `models.json` (config-files.md). Models = go-ai catalogue + entries in `models-store.json` ("go-ai's definitions are never replaced"). How to set a custom `baseUrl` for a local mock: UNVERIFIED; possible routes [INFERENCE]: a `models-store.json` entry with Pi store schema incl. `baseUrl`, or go-ai env/base-URL override. Needs source check before adoption.
6. **Headless**: no `-p`/print/JSON/RPC CLI mode documented; CLI flags are UI/server flags (README "CLI flags"). Headless option: `gi -web -bind 127.0.0.1 -port <p> -db <path> -workspace <dir>` and drive via REST API + Piclaw-compatible SSE `/sse/stream?chat_jid=...` (events `agent_status`, `agent_draft_delta`, `agent_response`, …) (README "SSE streaming"). Warning: "The application permits access before enrolment" — keep on loopback. Alternatively drive the TUI via tmux (repo's own `make test-tui-smoke` does this).
7. **State/telemetry**: SQLite DB `-db`, default `$XDG_STATE_HOME/gi/gi.db` (else `~/.local/state/gi/gi.db`); user config `$GI_CODING_AGENT_DIR` (default `~/.gi/agent`) then `$PI_CODING_AGENT_DIR` (default `~/.pi/agent`) — first existing file wins, and new files are created in **Pi's** location, i.e. shared with Pi; project `.gi/` then `.pi/`; `.piclaw/config.json` read; `mcp-auth.json` shared with Pi (README "Configuration files", config-files.md). Telemetry: none documented; `PI_OFFLINE=1` disables startup refreshes. Set `HOME`, `XDG_STATE_HOME`, `GI_CODING_AGENT_DIR`, `PI_CODING_AGENT_DIR` per run.
8. **Extensions**: tools/extensions via Go, embedded Joker (Clojure)/JavaScript (Goja/QuickJS), subprocess "process extensions and hooks"; directories `skills/`, `tools/`, `extensions/` scanned in `.gi/` then `.pi/`. Feature matrix: "No general Pi or Piclaw package compatibility"; "Piclaw extensions do not run in Gi" (https://raw.githubusercontent.com/rcarmo/gi/main/docs/feature-parity.md). → Pi TS extension API not supported.

#### gi-alt (nowa/gi) — same name, different project

1. **Repo/runtime/relation**: https://github.com/nowa/gi ("A golang implementation of Pi"), Go 1.26. "Go rebuild of selected Pi agent harness packages … goal is Pi-compatible behavior at the package boundary, not a direct TypeScript line port." Coding-agent scope "closed against the immutable Pi `v0.82.1` release at `b4f29368`". `pi-web-ui` not ported. Uses `.gi` (not `.pi`) for project-local settings. 8 stars. NOTICE: "No endorsement by the Pi authors is implied." Sources: README and https://raw.githubusercontent.com/nowa/gi/main/NOTICE.
   - Found via searches "gi port of pi coding agent", `site:github.com gi coding agent Go port of pi-mono`; rcarmo/gi was identified by the survey lead. Name collision: both install a `gi` binary.
2. **Release**: tags `v0.82.2` (2026-07-27), `v0.82.1` (2026-07-26), `v0.82.0`, `v0.0.3` (https://github.com/nowa/gi/tags.atom). Latest commit "Set Gi version to 0.82.2" 2026-07-27T11:35:42Z (https://github.com/nowa/gi/commits/main.atom). No binary release assets found (UNVERIFIED; GitHub API rate-limited).
3. **Licence**: MIT, "Copyright (c) 2026 Nowa Zhu and contributors / Portions Copyright (c) 2025 Mario Zechner" — https://raw.githubusercontent.com/nowa/gi/main/LICENSE. No restrictive clauses.
4. **Install & pin**: source only: `git clone https://github.com/nowa/gi && git checkout v0.82.2 && go build -o gi ./cmd/gi` (README shows `go run ./cmd/gi`). Go modules give `go.sum` checksums [INFERENCE]. No checksums/binaries published. Self-update: has `internal/versioncheck` and shows "release-update, and package-update notices" in TUI; disable switch UNVERIFIED (`--offline` flag exists).
5. **Custom endpoint**: Y — "Custom provider credentials and model definitions are configured through `~/.gi/agent/models.json`" (https://raw.githubusercontent.com/nowa/gi/main/docs/models.md); OpenAI-compatible transports supported (README). Exact schema assumed Pi-compatible [INFERENCE].
6. **Headless**: `-p` print mode; `--offline --no-session` uses a local deterministic responder (useful as harness smoke test); non-TTY falls back to single-turn host (README). JSON/RPC CLI flags UNVERIFIED (package `internal/rpcwire` exists).
7. **State/telemetry**: `~/.gi/agent/` (`auth.json`, `models.json`, `trust.json`), project `.gi/` (README). Env var to relocate agent dir UNVERIFIED (likely `GI_CODING_AGENT_DIR` [INFERENCE]). Analytics "defaults to disabled"; opt-in only under `GI_EXPERIMENTAL=1` first-run setup (README). Non-interactive modes resolve project trust to untrusted unless `--approve`/`-a`.
8. **Extensions**: TypeScript in-process extensions are **not** loaded directly: "TypeScript in-process extensions and Node/npm lifecycle behavior remain explicit Go protocol/runtime replacements"; cross-language package/extension protocol in `protocol/README.md`; `gi install official:gi-plan-mode` (README). → Pi extensions not drop-in compatible.

#### pi_agent_rust

1. **Repo/runtime/relation**: https://github.com/Dicklesworthstone/pi_agent_rust, Rust (2024 edition), binary `pi`. "from-scratch Rust port of Pi Agent by Mario Zechner (made with his blessing!)"; FAQ: "an authorized Rust port". Current direction: "no longer trying to be a strict drop-in replacement … OMP is the closer reference". 1,872 stars. Crate: `pi_agent_rust` on crates.io (https://docs.rs/crate/pi_agent_rust/latest).
2. **Release**: GitHub release v0.7.1 published 2026-10-03 (https://api.github.com/repos/Dicklesworthstone/pi_agent_rust/releases?per_page=3). crates.io index lists versions up to 0.7.1 (https://index.crates.io/pi/_a/pi_agent_rust) — note README says crates.io publication is "currently HOLD", contradicting the index; treat crates.io as secondary. Latest commit 2026-10-10T13:11:20Z (https://api.github.com/repos/Dicklesworthstone/pi_agent_rust/commits?per_page=1).
3. **Licence**: "MIT License (with OpenAI/Anthropic Rider)" → SPDX: no standard id; use `LicenseRef-MIT-with-OpenAI-Anthropic-Rider` (GitHub reports "Other"). **FLAG — restrictive.** Verbatim from https://raw.githubusercontent.com/Dicklesworthstone/pi_agent_rust/main/LICENSE :

   > ADDITIONAL RIDER / RESTRICTION (OpenAI / Anthropic):
   >
   > This rider is part of the "conditions" of this License. In the event of any
   > conflict between this rider and any other portion of this License, this rider
   > controls.
   >
   > "Restricted Parties" means OpenAI, L.L.C.; Anthropic, PBC; any of their
   > respective Affiliates; and any person or entity acting directly or indirectly
   > on behalf of, for the benefit of, or under the direction of any of the
   > foregoing (including any officer, director, employee, contractor, agent,
   > consultant, service provider, or representative).
   >
   > Notwithstanding any other provision of this License, no rights are granted to
   > any Restricted Party. Any purported license, sublicense, assignment, transfer,
   > or other permission to any Restricted Party is null and void absent the
   > express prior written permission of Jeffrey Emanuel.
   >
   > You may not provide, disclose, distribute, sublicense, sell, lease, lend,
   > host, make available, or otherwise permit access to the Software or any
   > derivative work of the Software (as defined in applicable copyright law)
   > (collectively, "Derivative Works") to or for any Restricted Party.
   >
   > For purposes of this rider, "use" includes, without limitation: copying,
   > modifying, merging, publishing, distributing, sublicensing, selling,
   > transferring, making available, hosting, deploying, executing, benchmarking,
   > testing, analyzing, indexing, or incorporating the Software or any Derivative
   > Works into any dataset, training corpus, evaluation harness, or pipeline for
   > machine learning or other automated systems.
   >
   > This rider applies to the Software and all Derivative Works. As a condition of
   > use, you agree that this rider is a precondition to exercising any rights
   > under this License, and you agree that any distribution of the Software or any
   > Derivative Works must include this rider provision unmodified.
   >
   > Any breach of this rider automatically and immediately terminates the
   > permissions granted by this License. Upon termination, you must immediately
   > cease all use and distribution of the Software and any Derivative Works and
   > destroy all copies under your control.
   >
   > You agree that a breach of this rider would cause irreparable harm and that
   > Jeffrey Emanuel may seek injunctive or other equitable relief to enforce this
   > rider, in addition to any other remedies available at law. To the maximum
   > extent permitted by applicable law, the prevailing party in any action to
   > enforce this rider shall be entitled to recover reasonable attorneys' fees and
   > costs.
   >
   > For purposes of this rider, "Affiliate" means any entity that directly or
   > indirectly controls, is controlled by, or is under common control with the
   > specified party. "Control" means ownership of more than 50% of the voting
   > securities or other ownership interest, or the power to direct management or
   > policies by contract or otherwise.

   - README: badge "License: MIT + Rider"; section "License": "MIT License (with OpenAI/Anthropic Rider). See [LICENSE](LICENSE) for details." (https://github.com/Dicklesworthstone/pi_agent_rust). No further README statements on benchmarking found.
   - Implications for Buffon [INFERENCE, not legal advice]: (a) anyone running the benchmark on behalf of / for the benefit of / under direction of OpenAI or Anthropic (incl. contractors) has no licence, and "executing, benchmarking, testing" and incorporation into an "evaluation harness" are expressly within "use"; (b) Buffon must not "make available" the binary or derivatives to Restricted Parties (e.g. a published container image bundling it); (c) the rider must be redistributed unmodified with any copy. Publishing results is not explicitly prohibited, but Buffon itself counts as an "evaluation harness". Also note the Anthropic/OpenAI mock-model naming does not trigger it; the identity of the operator/beneficiary does. Recommend: do not vendor/redistribute the binary; fetch at run time from upstream; document operator eligibility.
4. **Install & pin**:
   - `curl -fsSL "https://raw.githubusercontent.com/Dicklesworthstone/pi_agent_rust/v0.7.1/install.sh" | bash -s -- --version v0.7.1 --yes --no-completions --no-agent-skills` (flags from README "Installation"; example in README uses v0.3.0).
   - Assets per platform: `pi-<os>-<arch>.tar.xz` + `.sha256` + `.minisig` (v0.7.1 release assets, GitHub-API `digest: sha256:…` also present). v0.3.0 used aggregate `SHA256SUMS`. Optional cosign verification via `--sigstore-bundle-url`. Explicit `--artifact-url`/`--checksum-url` mode. Ships `Cargo.lock`.
   - **HOME side effects**: installer by default writes a skill to `~/.claude/skills/pi-agent-rust/SKILL.md` and `~/.codex/skills/…` (disable `--no-agent-skills`); may migrate an existing TS `pi` to `legacy-pi`; creates an `rpi` launcher if none exists (name clash with revpidev/rpi) (README). Use `--artifact-url` or manual tarball extraction in a sandbox.
   - Self-update: `pi update` updates packages, not the binary; README says requests include "update checks" — mechanism and disable switch UNVERIFIED.
5. **Custom endpoint**: Y — add provider to `~/.pi/agent/models.json` (or `.pi/models.json`) with `"api": "openai-completions"`, `"baseUrl": "http://127.0.0.1:11000/v1"`, `"apiKey"`, `"models": [...]`; run `pi --provider <name> --model <id>`. Native modules include `anthropic`, `openai`, `openai_responses` (README "Configuration", docs/models.md). Anthropic-compatible custom base URL via `models.json` `api` field [INFERENCE].
6. **Headless**: `-p/--print`; `--mode text|json|rpc` (json streams one event per line, delta-only `message_update`; fatal errors emit one `{"type":"error",…}` record); `--acp` (JSON-RPC 2.0 ACP); `--approval-mode yolo`/`--yolo` needed for tools in non-interactive runs, else exit code 3; `--no-session`; `--no-context-files`, `--no-skills`, `--no-extensions` for isolation (README "Options", "Modes").
7. **State/telemetry**: `~/.pi/agent/` (`settings.json`, `models.json`, `models.fetched.json`, `sessions/`, `session-index.sqlite`, `agents/`, `skills/`, `prompts/`, `packages/`); project `.pi/`. Relocate: `PI_CODING_AGENT_DIR`, `PI_CONFIG_PATH` (single file, skips merge), `PI_PACKAGE_DIR`; `PI_NO_CONTEXT_FILES=1`; `PI_WORKSPACE_TRUST`/`--trust` for non-interactive project trust (README). **Shares `~/.pi/agent` with TS Pi** — isolate HOME per harness. "Hostcall telemetry" is local runtime instrumentation (README); no remote analytics found (UNVERIFIED absence).
8. **Extensions**: JS/TS Pi extensions run in embedded QuickJS (no Node/Bun) with Node API shims and capability-gated hostcalls; `*.native.json` native descriptors; claims 206/208 must-pass and 95.6% pass over 226 tested extensions (historical snapshot) (README "Extensions"). Partial Pi extension API compatibility; policy profiles `safe|balanced|permissive` may block extension behaviour.

#### pie

1. **Repo/runtime/relation**: https://github.com/c4pt0r/pie — "Rust rewrite of the original pi project (pi-coding-agent)"; "most of the code in this project was written by AI". Focus on local models (DS4), cron/loops/triggers, MCP. 165 stars, 302 commits.
2. **Release**: no tags/releases (https://github.com/c4pt0r/pie/tags.atom empty). Latest commit 2026-08-06T22:08:45Z (https://github.com/c4pt0r/pie/commits/main.atom).
3. **Licence**: MIT, "Copyright (c) 2026 c4pt0r" — https://raw.githubusercontent.com/c4pt0r/pie/main/LICENSE. No restrictions.
4. **Install & pin**: `git clone https://github.com/c4pt0r/pie && git checkout <sha> && cargo build --release` → `target/release/pie` (README). Cargo.lock presence UNVERIFIED (not in top-level listing). No checksums, no self-update.
5. **Custom endpoint**: Y — `~/.pie/models.json` / `<project>/.pie/models.json` with `"api": "openai-responses"` or chat completions, `"baseUrl"`; or CLI `--provider ds4 --model … --base-url http://127.0.0.1:8000/v1`; env `DS4_BASE_URL`/`DS4_URL` (README "Local OpenAI-compatible models"). Anthropic-compatible custom URL UNVERIFIED.
6. **Headless**: none documented; README shows only REPL plus `--list-sessions`, `--image`, `--resume` (README; CHANGELOG grep for print/json/headless found nothing). Not benchmark-ready without driving a PTY. UNVERIFIED.
7. **State/telemetry**: `~/.pie/` (`sessions/<cwd-hash>/*.jsonl`, `memory/*.md`, `auth.json`, `models.json`, `history`, `mcp.toml`, `hooks.toml`, `config.toml`, `inbox.jsonl`); relocate with `PIE_DIR` (README "Files and storage"). Telemetry: none documented. Cross-session memory injected into future sessions — must reset between runs.
8. **Extensions**: skills, MCP, hooks (command/webhook); no Pi TS extension support documented.

#### rpi

1. **Repo/runtime/relation**: https://github.com/revpidev/rpi, Rust, "derived from Pi"; "early behavior is kept in parity with upstream — but rpi is an independent project"; `external/pi` submodule pins upstream baseline (`UPSTREAM.md`). Single static binary. 2 stars, 676 commits. Site https://revpi.dev.
2. **Release**: v0.1.6 (2026-10-09) "upstream parity to v1.0.0 (behavioral gold standard `a13d35a74`)" (https://github.com/revpidev/rpi/releases.atom). Latest commit 2026-10-09T01:32:29Z (https://github.com/revpidev/rpi/commits/main.atom).
3. **Licence**: MIT, "Copyright (c) 2026 Rpi contributors" — https://raw.githubusercontent.com/revpidev/rpi/main/LICENSE. No restrictions.
4. **Install & pin**: `curl -fsSL https://revpi.dev/install.sh | sh` (verifies SHA-256; `--prefix <dir>`); manual `rpi-<version>-<target>.tar.gz` + `.sha256` sidecar from GitHub Releases; source build with `Cargo.lock` (README). Installer version-pin flag UNVERIFIED → use manual archive. Self-update `rpi update --self`; startup update check disabled by `RPI_SKIP_VERSION_CHECK` or `RPI_VERSION_CHECK_URL=off`.
5. **Custom endpoint**: 41 built-in providers + remote catalog from revpi.dev; custom `baseUrl`/`models.json` not documented in README — UNVERIFIED (Pi parity suggests `models.json` [INFERENCE]).
6. **Headless**: `--print`, `rpi <message>` one-shot; `--mode json` / `--mode rpc` per https://github.com/revpidev/rpi/blob/main/docs/json-rpc.md (README).
7. **State/telemetry**: `~/.rpi/` (or `RPI_CODING_AGENT_DIR`); sessions `RPI_CODING_AGENT_SESSION_DIR` (default `~/.rpi/agent/sessions`). **Default network endpoints**: version check `https://revpi.dev/api/latest-version`, model catalog `https://revpi.dev`, **install-count telemetry** `POST https://revpi.dev/api/report-install`, share viewer. Disable all: `RPI_OFFLINE=1` or `--offline`; individually `RPI_TELEMETRY_URL=off`, `RPI_MODEL_CATALOG_URL=off`, `RPI_VERSION_CHECK_URL=off` (README "Configuration").
8. **Extensions**: own plugin ABI — Wasm (L1) or native dynamic libraries (L0), `crates/rpi-ext-sdk`; `rpi install <source>` (README). Pi TS extensions not supported (no JS runtime documented).

#### pi (Go) — sky-valley/pi

1. **Repo/runtime/relation**: https://github.com/sky-valley/pi — "pure-Go port of pi … no Node.js runtime"; `difftest/` captures and diffs HTTP request bodies of real pi vs the port ("pi is ground truth"). 72 stars. Not ported: interactive TUI, host/mode layer, **extensions runtime**, Bedrock, Codex WS (README "Fidelity notes").
2. **Release**: tag v0.99.26 "tracking pi 0.99.2", 2026-10-01; latest commit 2026-10-01T11:00:43Z (https://github.com/sky-valley/pi/tags.atom, https://github.com/sky-valley/pi/commits/main.atom).
3. **Licence**: MIT ("MIT, matching upstream pi", README; GitHub "MIT License"). LICENSE text not fetched — restrictive clauses UNVERIFIED but none indicated.
4. **Install & pin**: `git checkout v0.99.26 && go build -o pi ./cmd/pi` (README). No binaries/checksums documented.
5. **Custom endpoint**: providers Anthropic Messages, OpenAI Chat Completions/Responses, Google; `base_url_test.go` present; CLI config for a custom base URL UNVERIFIED (CLI keys from env only per README).
6. **Headless**: `pi "<prompt>"` = print mode; REPL otherwise; no JSON/RPC mode documented.
7. **State/telemetry**: sessions `~/.pi/agent/sessions/--<cwd>--/` (Pi format; shares dir with Pi); attribution headers to OpenRouter/NVIDIA/Cloudflare/Vercel/OpenCode by default, disable with `PI_TELEMETRY=0` (README).
8. **Extensions**: none (unported).

#### pi (Rust) — nktkt/pi, crate `pi-coding-agent`

1. **Repo/runtime/relation**: https://github.com/nktkt/pi — "Rust port of earendil-works/pi … focused on the core coding-agent loop"; crates `pi-ai`, `pi-agent`, `pi-coding-agent` (binary `pi`); TUI not ported. Crate metadata links to earendil-works/pi as repository (misleading) (https://docs.rs/crate/pi-coding-agent/latest). 14 stars.
2. **Release**: crate `pi-coding-agent` 1.0.0 published 2026-05-12 (https://index.crates.io/pi/-c/pi-coding-agent); latest commit 2026-05-12T14:19:33Z (https://github.com/nktkt/pi/commits/main.atom). README refers to `pi-ai = "1.2"` (newer library versions; UNVERIFIED).
3. **Licence**: MIT (README, docs.rs). LICENSE text not fetched.
4. **Install & pin**: `cargo install pi-coding-agent --version 1.0.0 --locked` (crates.io checksum `8e116e3a…` in index). Repo ships `Cargo.lock`.
5. **Custom endpoint**: library `Model::openai_compat(…, base_url, …)` / `StreamOptions::base_url`; CLI flag/env for base URL UNVERIFIED (CLI uses `PI_MODEL` env + provider API key env).
6. **Headless**: `pi -p "<prompt>"`, `pi -p "…" --json` (JSON-lines events), `--yolo` to skip permission prompts.
7. **State/telemetry**: sessions `$XDG_CONFIG_HOME/pi/sessions/<id>.json`; reads AGENTS.md/CLAUDE.md/`.pi/instructions.md` up the tree. No telemetry documented.
8. **Extensions**: none.

#### pi-mono-python — openxjarvis

1. **Repo/runtime/relation**: https://github.com/openxjarvis/pi-mono-python — Python 3.11+ port "aligned to pi-mono TypeScript v0.84.3 (2026-08-24)", includes `pi_tui`, `pi_coding_agent`, etc. 28 stars, 17 commits.
2. **Release**: none; latest commit 2026-08-25T14:59:27Z (https://github.com/openxjarvis/pi-mono-python/commits/main.atom).
3. **Licence**: **no LICENSE file in repo root and none detected by GitHub** (repo page "Resources" lists no licence) → default all-rights-reserved; FLAG: no grant to run/redistribute. No explicit restrictive clause.
4. **Install & pin**: `git checkout <sha> && uv sync` (ships `uv.lock`); run `uv run --package pi-coding-agent pi`.
5. **Custom endpoint**: UNVERIFIED. Note it auto-loads `.env` from project root (README) — isolation hazard.
6. **Headless**: `pi --print "<prompt>"`.
7. **State/telemetry**: UNVERIFIED; includes a `pi_telemetry` package ("in-memory recorder").
8. **Extensions**: UNVERIFIED.

#### Other Pi-derived/Pi-named projects (brief)

- **guanshan/pi-go** — Go port "with compatible session format and tools"; 1 star; last commit 2026-06-08 (https://github.com/guanshan/pi-go, https://github.com/guanshan/pi-go/commits/main.atom). Licence UNVERIFIED.
- **mauromedda/pi-coding-agent-go** — Go module, pseudo-version only, licence "Unknown" on pkg.go.dev (https://pkg.go.dev/github.com/mauromedda/pi-coding-agent-go).
- **amit-timalsina/pi-agent-go** — Go agent framework named after pi; library, not a CLI harness (https://github.com/amit-timalsina/pi-agent-go).
- **PyPI `pi-coding-agent` 0.6.0** (Ashutosh0428/pi-agent) — *not a port*; "Inspired by the Pi philosophy"; Python, MIT; `pi "<prompt>"` one-shot; Ollama/OpenAI-compatible providers; uploaded 2026-06-12 (https://pypi.org/pypi/pi-coding-agent/json). Name collision risk only.
- **PyPI `pi-coding-agent-python-sdk`** — SDK wrapper, not a harness (https://pypi.org/project/pi-coding-agent-python-sdk/0.4.3).
- **dnouri/pi-coding-agent** — Emacs front-end for Pi (https://github.com/dnouri/pi-coding-agent).
- **AUR `pi-coding-agent` 0.85.1-1** — Arch distribution package of upstream Pi (https://aur.archlinux.org/packages/pi-coding-agent).
- Many plain GitHub forks/mirrors of earendil-works/pi (e.g. rbrtbn/pi, stefanmohl/pi-mono, Gitea mirrors) with no own releases — ignored.
- No Zig, C#, or Swift ports found in searches (UNVERIFIED absence).
- PiG (MichaelKinsy/PiG, Go port) and oh-my-pi are covered in other sections of this survey; Pi-Bolt's README benchmarks against both (https://github.com/opensec-git/Pi-Bolt).

#### Notes for Buffon design
- Only **pi_agent_rust** carries a benchmarking-relevant licence restriction (operator/beneficiary-based, not output-based).
- Shared state dir collision: Pi-Bolt, pi_agent_rust and sky-valley/pi all use `~/.pi/agent`; rcarmo/gi falls back to and creates files in `~/.pi/agent` too → separate HOME per harness mandatory.
- Phone-home defaults to neutralise: rpi (`RPI_OFFLINE=1`), sky-valley attribution headers (`PI_TELEMETRY=0`), Pi-Bolt/pi_agent_rust inherit Pi update checks (`PI_OFFLINE` per Pi-Bolt docs; pi_agent_rust UNVERIFIED).
- Benchmark-ready headless + custom endpoint: Pi-Bolt, pi_agent_rust, nowa/gi (print only), rpi (endpoint UNVERIFIED). rcarmo/gi (canonical gi) has no print mode — needs a web-API/SSE or tmux driver, and its custom-endpoint route is UNVERIFIED. pie lacks a documented headless mode.
- GitHub REST API was rate-limited mid-research; dates for gi, pie, rpi, sky-valley, Pi-Bolt come from GitHub Atom feeds.

## 4. Reference (non-Pi) terminal coding agents

**Selection rationale.** These are the most-used non-Pi terminal agents, picked so the benchmark covers each wire protocol a mock model must speak: OpenAI Responses (Codex), Anthropic Messages (Claude Code), Gemini generateContent (Gemini CLI), OpenAI Chat Completions (Goose, Crush, Aider, Qwen, Kimi). The set also spans closed and open tools and Rust, Go, TS and Python runtimes. Kimi Code is included because its TUI is built on Pi's `pi-tui`. Amp is a closed reference: there is a ToS check below but no full runnability profile.

### Reference selection notes

**Dropped:**
- Kimi CLI (Python, `MoonshotAI/kimi-cli`): archived. GitHub API shows `archived: true`. The PyPI 1.52.0 README says "replaced by Kimi Code CLI" and that existing installs "will stop working" ([PyPI](https://pypi.org/project/kimi-cli/)).
- OpenCode and GitHub Copilot CLI: covered in §2 of this survey.
- Profiled briefly in this section after the first snapshot: Antigravity CLI, Cursor CLI, Factory Droid CLI, Hermes Agent, jcode, Prime Agent, and Zed as an ACP host. Still not researched, so all UNVERIFIED as candidates: OpenHands CLI, Plandex, Warp. Cline and others appear only in the brief ACP and Harbor list at the end of this section.

#### Cross-cutting findings for mock-model design

- A mock that only speaks OpenAI Chat Completions can run Goose, Crush, Aider, Qwen and Kimi.
- Codex needs the **OpenAI Responses API**. Its config reference says: "`responses` is the only supported value" ([config-reference](https://developers.openai.com/codex/config-reference.md)).
- Claude Code needs **Anthropic Messages**.
- Gemini CLI needs the **Gemini generateContent** protocol.
- Aider doesn't use tool calls. It expects edit-format text such as SEARCH/REPLACE blocks [INFERENCE from Aider docs/architecture; UNVERIFIED here], so mock scripts must be written per harness.
- None of the harnesses documents loading Pi extensions. Pi-extension compatibility is "No" for all of them.

### OpenAI Codex CLI

1. **Identity.**
   - Repo: https://github.com/openai/codex. Docs: https://developers.openai.com/codex.
   - Written in Rust (GitHub language field); also distributed as the npm package `@openai/codex`.
   - Relation to Pi: none (independent reference).
2. **Release.**
   - Latest release `rust-v0.162.1`, published 2026-10-09 ([release](https://github.com/openai/codex/releases/tag/rust-v0.162.1)). npm `@openai/codex@0.162.1` published 2026-10-09.
   - Latest `main` commit: 2026-10-10.
   - ~128.5k stars.
3. **Licence.**
   - Apache-2.0 ([LICENSE](https://github.com/openai/codex/blob/main/LICENSE)).
   - No benchmark or competitive-use clause in the licence. With a local mock no OpenAI service is used, so OpenAI's service terms don't come into play [INFERENCE].
4. **Install / pin.**
   - npm: `npm i -g @openai/codex@0.162.1`. The npm metadata shows `_hasShrinkwrap: false` and no runtime dependencies.
   - GitHub release binaries: each asset has a GitHub sha256 `digest`, and Linux musl builds ship `.sigstore` bundles (release API).
   - A DotSlash file named `codex` in the release pins per-platform binaries ([docs/install.md](https://github.com/openai/codex/blob/main/docs/install.md)).
   - Can build from source with `cargo build` (same doc).
   - Update check: set `check_for_update_on_startup = false` ([config-reference](https://developers.openai.com/codex/config-reference.md)).
5. **Custom endpoint.**
   - Simplest: set `openai_base_url = "http://127.0.0.1:PORT/v1"` in `config.toml` to point the built-in `openai` provider at a proxy.
   - Or define a custom provider: `[model_providers.mock] base_url=… env_key=… wire_api="responses"`, then `model_provider="mock"` ([config-advanced](https://developers.openai.com/codex/config-advanced.md)).
   - `wire_api`: "`responses` is the only supported value". **Chat Completions isn't supported** ([config-reference](https://developers.openai.com/codex/config-reference.md)).
   - Built-in provider IDs can't be overridden.
   - Auth: `CODEX_API_KEY` for `codex exec` ([noninteractive](https://developers.openai.com/codex/noninteractive.md)).
   - Anthropic endpoint: not supported [INFERENCE from wire_api].
6. **Headless.**
   - `codex exec "<task>"` prints the final message to stdout and progress to stderr.
   - `--json` turns stdout into JSONL events: `thread.started`, `turn.started`, `turn.completed` (with `usage`), `turn.failed`, `item.*`, `error`.
   - Other useful flags:
     - `--ephemeral`: don't persist rollout files.
     - `-o/--output-last-message <path>`
     - `--sandbox workspace-write|danger-full-access`. `--full-auto` is deprecated.
     - `--ignore-user-config`
     - `--ignore-rules`
   - Source: [noninteractive](https://developers.openai.com/codex/noninteractive.md).
7. **State / telemetry.**
   - State lives under `CODEX_HOME` (default `~/.codex`): `config.toml`, `hooks.json`, profiles, `log/`.
   - `sqlite_home` holds runtime state and `log_dir` defaults to `$CODEX_HOME/log` ([config-advanced](https://developers.openai.com/codex/config-advanced.md), [config-reference](https://developers.openai.com/codex/config-reference.md)).
   - Analytics are on by default: "By default, Codex periodically sends a small amount of anonymous usage and health data back to OpenAI". Disable with `[analytics] enabled = false`.
   - OTel export is opt-in and off by default (`[otel] exporter = "none"`).
   - Also set `feedback.enabled = false` (default true).
   - Sources: [config-advanced](https://developers.openai.com/codex/config-advanced.md), [config-reference](https://developers.openai.com/codex/config-reference.md).
8. **Extensions.**
   - Supports lifecycle hooks (`hooks.json` / `[hooks]`), skills (`skills.config`), MCP servers (`mcp_servers.<id>`) and subagent roles ([config-advanced](https://developers.openai.com/codex/config-advanced.md), [config-reference](https://developers.openai.com/codex/config-reference.md)).
   - No Pi extension support.

### Anthropic Claude Code (closed)

1. **Identity.**
   - Public issues/plugins repo: https://github.com/anthropics/claude-code. Docs: https://code.claude.com/docs.
   - npm `@anthropic-ai/claude-code`. The 2.1.296 package is now a thin wrapper: `bin/claude.exe`, platform `optionalDependencies` and a `postinstall` script ([npm](https://registry.npmjs.org/@anthropic-ai/claude-code/latest)).
   - Closed source; the source repo is `anthropics/claude-cli-internal` per older npm metadata.
   - Relation to Pi: none.
2. **Release.**
   - npm `latest` = 2.1.296, published 2026-10-09; `stable` = 2.1.287.
   - GitHub release v2.1.296 (2026-10-09) ships `SHASUMS256.txt` and `SHASUMS256.txt.sig`.
   - Latest `main` commit of the public repo: 2026-10-09.
3. **Licence / ToS.**
   - [LICENSE.md](https://github.com/anthropics/claude-code/blob/main/LICENSE.md), verbatim: "© Anthropic PBC. All rights reserved. Use is subject to Anthropic's [Commercial Terms of Service](https://www.anthropic.com/legal/commercial-terms)."
   - Legal page: "Your use of Claude Code is subject to: Commercial Terms of Service … Consumer Terms of Service" ([legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance)).
   - **Flag**, [Commercial Terms D.4](https://www.anthropic.com/legal/commercial-terms), verbatim: "D.4. Use Restrictions. Customer may not and must not attempt to (a) access the Services to build a competing product or service, including to train competing AI models or resell the Services except as expressly approved by Anthropic; (b) reverse engineer or duplicate the Services; or (c) support any third party's attempt at any of the conduct restricted in this sentence."
   - **Flag**, [Consumer Terms](https://www.anthropic.com/legal/consumer-terms), verbatim:
     - "To develop any products or services that compete with our Services, including to develop or train any artificial intelligence or machine learning algorithms or models or resell the Services."
     - "To decompile, reverse engineer, disassemble, or otherwise reduce our Services to human-readable form, except when these restrictions are prohibited by applicable law."
     - "Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise."
   - **Flag**, [legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance), verbatim:
     - "**The Claude Code binary must not be modified.** Claude Code must be installed and run as published by Anthropic, and customers may not remove, disable, or restrict any authentication method built into it"
     - "you can't use the Claude Code or Anthropic names or logos as part of your own product … or in a way that suggests Anthropic built, endorses, or is partnered with your product."
   - No explicit "no benchmarking / no publishing results" clause was found in either Terms page. A text search for "benchmark" returned no hits.
   - Risk: whether benchmarking against a mock counts as "build a competing product" (relevant if Buffon is used to develop competing harnesses) is a legal question. Treat it as a review item.
4. **Install / pin.**
   - Native installer for an exact version: `curl -fsSL https://claude.ai/install.sh | bash -s 2.1.296`.
   - Each release publishes a GPG-signed `manifest.json` with SHA256 for every binary at `https://downloads.claude.ai/claude-code-releases/<VERSION>/manifest.json(.sig)`. Key fingerprint: `31DD DE24 DDFA B679 F42D 7BD2 BAA9 29FF 1A7E CACE`.
   - Native installs auto-update in the background. Disable with `DISABLE_AUTOUPDATER=1`, or `DISABLE_UPDATES=1` to also block manual `claude update`/`install`.
   - Homebrew, WinGet and apt/dnf/apk installs don't auto-update.
   - Sources: [setup](https://code.claude.com/docs/en/setup.md), [env-vars](https://code.claude.com/docs/en/env-vars.md).
   - npm: `npm i -g @anthropic-ai/claude-code@2.1.296` (no shrinkwrap; platform binary via optionalDependencies).
5. **Custom endpoint (Anthropic Messages only).**
   - `ANTHROPIC_BASE_URL`, with `ANTHROPIC_API_KEY` (sent as `X-Api-Key`) or `ANTHROPIC_AUTH_TOKEN` (`Authorization: Bearer`) ([env-vars](https://code.claude.com/docs/en/env-vars.md)).
   - Notes when the endpoint is non-first-party:
     - MCP tool search is disabled.
     - `CLAUDE_CODE_MAX_CONTEXT_TOKENS` corrects the assumed context window.
     - `ANTHROPIC_MODEL` selects the model.
   - Not OpenAI-compatible [INFERENCE: no OpenAI option in the env-vars doc].
6. **Headless.**
   - Base command: `claude -p "<prompt>"` with `--output-format text|json|stream-json`.
   - Streaming: `stream-json` with `--verbose` and `--include-partial-messages` streams tokens.
   - Input and structured output: `--input-format stream-json`; `--json-schema` with `json` output.
   - `--allowedTools` controls tool access.
   - `--bare` (or `CLAUDE_CODE_SIMPLE=1`) skips hooks, skills, plugins, MCP, memory and CLAUDE.md, and is "the recommended mode for scripted and SDK calls". Without `--bare`, `-p` runs project hooks and `.mcp.json` servers with no trust prompt.
   - Sources: [headless](https://code.claude.com/docs/en/headless.md), [env-vars](https://code.claude.com/docs/en/env-vars.md).
7. **State / telemetry.**
   - Files:
     - `~/.claude/` (settings.json, sessions, plugins, backups).
     - `~/.claude.json` (sign-in, MCP, per-project trust, global config).
     - Native install: launcher `~/.local/bin/claude` and versions in `~/.local/share/claude/versions/`.
     - Sources: [settings](https://code.claude.com/docs/en/settings.md), [setup](https://code.claude.com/docs/en/setup.md).
   - `CLAUDE_CONFIG_DIR` relocates "All settings, session history, and plugins". UNVERIFIED whether `~/.claude.json` moves with it, so isolate HOME as well.
   - `CLAUDE_CODE_SKIP_PROMPT_HISTORY=1` skips transcripts.
   - Telemetry and nonessential traffic:
     - `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` turns off auto-updates, telemetry, error reporting, feedback, release notes and availability checks.
     - The individual switches are `DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING`, `DO_NOT_TRACK=1` and `DISABLE_GROWTHBOOK` (feature flags).
     - Note: "Setting it to `0` or `false` still opts out".
     - Source: [env-vars](https://code.claude.com/docs/en/env-vars.md).
8. **Extensions.**
   - Plugins (marketplaces), hooks, skills, subagents, custom commands and MCP ([headless](https://code.claude.com/docs/en/headless.md), [settings](https://code.claude.com/docs/en/settings.md)).
   - No Pi extension support.

### Gemini CLI

1. **Identity.**
   - https://github.com/google-gemini/gemini-cli, written in TypeScript on Node.
   - npm `@google/gemini-cli`.
   - Relation to Pi: none.
2. **Release.**
   - npm `latest` 0.63.0, published 2026-10-06. GitHub release v0.63.0, 2026-10-06.
   - Other tags: `preview` 0.64.0-preview.1, `nightly` 0.65.0-nightly.20261010.
   - Latest `main` commit: 2026-10-09.
   - Status: on 2026-06-18 Gemini CLI stopped serving Google AI Pro and Ultra users and those using it free of charge. Paid Gemini API keys and Gemini Code Assist Standard and Enterprise licences keep working. Antigravity CLI replaces it for consumer tiers ([Google Developers Blog, 2026-05-19](https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)). An arm run against a local mock with an API key is unaffected [INFERENCE].
3. **Licence.**
   - Apache-2.0 ([LICENSE](https://github.com/google-gemini/gemini-cli/blob/main/LICENSE)).
   - [tos-privacy.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/resources/tos-privacy.md), verbatim: "Directly accessing the services powering Gemini CLI (for example, the Gemini Code Assist service) using third-party software, tools, or services (for example, using OpenClaw with Gemini CLI OAuth) is a violation of applicable terms and policies."
   - That restricts access to Google services, not benchmarking. No benchmark clause found.
4. **Install / pin.**
   - `npm i -g @google/gemini-cli@0.63.0` (`_hasShrinkwrap: false`).
   - Release assets include `gemini-darwin-*-unsigned.zip`; no checksum file was observed in the release asset list.
   - Auto-update: set `general.enableAutoUpdate: false` and `general.enableAutoUpdateNotification: false`, both default true ([configuration](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md)).
5. **Custom endpoint.**
   - `GOOGLE_GEMINI_BASE_URL`: "Overrides the default base URL for Gemini API requests (when using `gemini-api-key` authentication)… must use HTTPS unless pointing to `localhost`" (same doc).
   - The mock must speak the **Gemini API**. OpenAI and Anthropic aren't supported (UNVERIFIED that no such option exists; none appears in the configuration reference).
6. **Headless.**
   - `-p/--prompt` or a non-TTY stdin triggers headless mode.
   - `--output-format json`: `{response, stats, error}`.
   - `--output-format stream-json`: events `init`, `message`, `tool_use`, `tool_result`, `error`, `result`.
   - Exit codes: 0, 1, 42 (input error), 53 (turn limit).
   - `--yolo` / `--approval-mode=yolo`. **Sandbox is enabled by default with yolo** (Docker image).
   - Sources: [headless](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/headless.md), [configuration](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md).
7. **State / telemetry.**
   - Files: `~/.gemini/settings.json`, `~/.gemini/tmp/<project_hash>/…`, `~/.gemini/GEMINI.md`.
   - `GEMINI_CLI_HOME` sets the root under which `.gemini` is created.
   - Usage statistics are on by default (`privacy.usageStatisticsEnabled`, default `true`). Opt out with `{"privacy":{"usageStatisticsEnabled":false}}`.
   - OTel telemetry is controlled by `telemetry.enabled` / `GEMINI_TELEMETRY_ENABLED`.
   - Source: [configuration](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md).
8. **Extensions.**
   - Extensions bundle prompts, MCP servers, commands, themes, hooks, sub-agents and skills ([extensions](https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/index.md)).
   - No Pi extension support.

### Qwen Code

1. **Identity.**
   - https://github.com/QwenLM/qwen-code, written in TypeScript on Node. npm `@qwen-code/qwen-code`.
   - "originally based on Google Gemini CLI v0.8.2 … Starting from Qwen Code v0.1, we stopped syncing with upstream" ([README](https://github.com/QwenLM/qwen-code/blob/main/README.md)).
   - Relation to Pi: none.
2. **Release.**
   - npm `latest` 0.25.0, published 2026-10-05. Also `preview` 0.25.1-preview.2 and `nightly` tags.
   - Latest `main` commit: 2026-10-10.
   - The GitHub "latest release" is an SDK tag (`sdk-typescript-v0.1.18`), so pin via npm.
3. **Licence.**
   - Apache-2.0 per the GitHub API ([LICENSE](https://github.com/QwenLM/qwen-code/blob/main/LICENSE)). The npm `license` field is empty.
   - The [ToS/Privacy doc](https://github.com/QwenLM/qwen-code/blob/main/docs/users/support/tos-privacy.md) only maps auth methods to provider terms.
   - No benchmark, competition or reverse-engineering clause found (text search).
4. **Install / pin.**
   - `npm i -g @qwen-code/qwen-code@0.25.0` (no shrinkwrap).
   - Auto-update: set `general.enableAutoUpdate: false` ([settings](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/settings.md)).
5. **Custom endpoint.** `modelProviders` keyed by protocol (`openai`, `anthropic`, `gemini`), with `baseUrl`, `envKey` and an optional `wireApi` of `chat-completions|responses`. Env vars per protocol:

   | Protocol | Env vars |
   |---|---|
   | OpenAI | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
   | Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` |

   Select the protocol at startup with `security.auth.selectedType` ([auth](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/auth.md)).
6. **Headless.**
   - `qwen -p "…" --output-format json|stream-json`, plus `--include-partial-messages` and `--input-format`.
   - `--system-prompt` and `--append-system-prompt` are available.
   - Source: [headless](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/headless.md).
7. **State / telemetry.**
   - `~/.qwen/` (settings.json, tmp, file-history, plans).
   - `QWEN_HOME` relocates it; `QWEN_RUNTIME_DIR` sets the runtime output directory.
   - Usage statistics are on by default (`privacy.usageStatisticsEnabled`, default `true`). `QWEN_USAGE_STATISTICS_ENABLED`: any value other than `true`/`1` disables them.
   - `QWEN_TELEMETRY_ENABLED` controls OTel.
   - Source: [settings](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/settings.md).
8. **Extensions.**
   - Extensions bundle MCP servers, subagents, skills and commands.
   - It can install Gemini CLI extensions, Claude Code Marketplace plugins and the "Agent Plugins v1" format ([extensions](https://github.com/QwenLM/qwen-code/blob/main/docs/users/extension/introduction.md)).
   - No Pi extension support.

### Crush (Charm)

1. **Identity.**
   - https://github.com/charmbracelet/crush, written in Go. npm `@charmland/crush`.
   - Relation to Pi: none.
2. **Release.**
   - v0.98.1, published 2026-10-09 ([release](https://github.com/charmbracelet/crush/releases/tag/v0.98.1)). npm 0.98.1, 2026-10-09.
   - Latest `main` commit: 2026-10-10.
3. **Licence: FSL-1.1-MIT** (source-available; GitHub reports NOASSERTION) ([LICENSE.md](https://github.com/charmbracelet/crush/blob/main/LICENSE.md)).
   - **Flag**, verbatim: "A Permitted Purpose is any purpose other than a Competing Use. A Competing Use means making the Software available to others in a commercial product or service that: 1. substitutes for the Software; 2. substitutes for any other product or service we offer using the Software that exists as of the date we make the Software available; or 3. offers the same or substantially similar functionality as the Software."
   - Explicitly permitted, verbatim: "Permitted Purposes specifically include using the Software: 1. for your internal use and access; 2. for non-commercial education; 3. for non-commercial research; and 4. in connection with professional services…"
   - Each version converts to MIT on "the second anniversary of the date we make the Software available".
   - Benchmarking or publishing results isn't restricted. Redistributing Crush inside a commercial harness product would be.
4. **Install / pin.**
   - Exact-version options: `go install github.com/charmbracelet/crush@v0.98.1`, `npm i -g @charmland/crush@0.98.1`, or a release archive verified against `checksums.txt` (sigstore-signed `checksums.txt.sigstore.json`).
   - Crush also refreshes its provider catalog from Catwalk (`https://catwalk.charm.land`). Disable with `CRUSH_DISABLE_PROVIDER_AUTO_UPDATE=1` or `option provider-auto-update false`; `CATWALK_URL` overrides the source ([README](https://github.com/charmbracelet/crush/blob/main/README.md), [provider.go](https://github.com/charmbracelet/crush/blob/main/internal/config/provider.go)).
   - Binary self-update: none found (UNVERIFIED).
5. **Custom endpoint.** In `crushrc` (Bash-based config):
   - OpenAI-compatible: `provider add mock --type openai-compat --base-url http://127.0.0.1:PORT/v1 --api-key …`
   - Anthropic-compatible: `--type anthropic`
   - Then `model add mock/<id> --context-window … --default-max-tokens …`
   - The legacy JSON config is deprecated but still supported ([README](https://github.com/charmbracelet/crush/blob/main/README.md)).
6. **Headless.**
   - `crush run [-q] [-m provider/model] "<prompt>"`, or piped stdin.
   - **No JSON output flag** ([run.go](https://github.com/charmbracelet/crush/blob/main/internal/cmd/run.go)).
   - Root flags: `-y/--yolo` (auto-accept permissions), `-c/--cwd`, `-D/--data-dir` ([root.go](https://github.com/charmbracelet/crush/blob/main/internal/cmd/root.go)).
7. **State / telemetry.**
   - Files: `~/.config/crush/crushrc` (XDG), `~/.local/share/crush/` (JSON state), plus `./.crushrc` and `./crushrc` in the project.
   - Relocate with `CRUSH_GLOBAL_CONFIG`, `CRUSH_GLOBAL_DATA` and `XDG_CONFIG_HOME`.
   - Pseudonymous metrics are on by default. Opt out with `CRUSH_DISABLE_METRICS=1` or `DO_NOT_TRACK=1`.
   - Source: [README](https://github.com/charmbracelet/crush/blob/main/README.md).
   - Security: `crushrc` and `crush.json` are executable/trusted code.
8. **Extensions.**
   - Agent Skills (`$CRUSH_SKILLS_DIR`, `~/.config/agents/skills/`), preliminary hooks, MCP and LSP ([README](https://github.com/charmbracelet/crush/blob/main/README.md)).
   - No Pi extension support.

### Goose

1. **Identity.**
   - https://github.com/aaif-goose/goose: `block/goose` now redirects to org `aaif-goose` (GitHub API `full_name`). Docs: https://goose-docs.ai.
   - Written in Rust; CLI plus desktop app.
   - Relation to Pi: none.
2. **Release.**
   - v1.54.0, published 2026-10-08 ([release](https://github.com/aaif-goose/goose/releases/tag/v1.54.0)).
   - Latest `main` commit: 2026-10-09.
   - ~55.1k stars.
3. **Licence.** Apache-2.0 ([LICENSE](https://github.com/aaif-goose/goose/blob/main/LICENSE)). No restrictive clauses.
4. **Install / pin.**
   - Command: `curl -fsSL https://github.com/aaif-goose/goose/releases/download/v1.54.0/download_cli.sh | GOOSE_VERSION=v1.54.0 CONFIGURE=false GOOSE_BIN_DIR=… bash` ([download_cli.sh](https://github.com/aaif-goose/goose/blob/main/download_cli.sh), [installation](https://github.com/aaif-goose/goose/blob/main/documentation/docs/getting-started/installation.md)).
   - No SUMS file. Release assets carry GitHub sha256 `digest` fields.
   - Updates are manual (`goose update`) ([CLI commands](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/goose-cli-commands.md)). No background auto-update is documented (UNVERIFIED).
5. **Custom endpoint.**
   - Built-in OpenAI provider: `GOOSE_PROVIDER=openai`, `OPENAI_HOST=http://127.0.0.1:PORT`, `OPENAI_BASE_PATH=v1/chat/completions`, `OPENAI_API_KEY`.
   - Anthropic: `ANTHROPIC_HOST`.
   - Or JSON "custom providers" (OpenAI, Anthropic or Ollama formats).
   - Set `GOOSE_MODEL`.
   - Sources: [providers](https://github.com/aaif-goose/goose/blob/main/documentation/docs/getting-started/providers.md), [env vars](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/environment-variables.md).
6. **Headless.**
   - `goose run -t "<text>" | -i <file|-> [--no-session] [-q] [--max-turns N] [--with-extension …] --output-format text|json|stream-json` ([CLI commands](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/goose-cli-commands.md)).
   - Set `GOOSE_MODE=auto` and `GOOSE_DISABLE_SESSION_NAMING=true` (avoids an extra model call).
7. **State / telemetry.**
   - Files: `~/.config/goose/config.yaml`, `secrets.yaml` (when the keyring is disabled), data under `~/.local/share/goose/`.
   - **`GOOSE_PATH_ROOT`** overrides the root for all data, config and state.
   - Set `GOOSE_DISABLE_KEYRING=1` for file secrets.
   - `GOOSE_TELEMETRY_ENABLED` defaults to `false`. Set `OTEL_SDK_DISABLED=true` for OTel.
   - Sources: [env vars](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/environment-variables.md), [config files](https://github.com/aaif-goose/goose/blob/main/documentation/docs/guides/config-files.md).
8. **Extensions.**
   - Extensions are MCP servers. There are also recipes and goosehints ([llms.txt](https://goose-docs.ai/llms.txt)).
   - No Pi extension support.

### Kimi Code CLI (successor to archived Kimi CLI)

1. **Identity.**
   - https://github.com/MoonshotAI/kimi-code, written in TypeScript on Node; single-binary releases. npm `@moonshot-ai/kimi-code`.
   - **Relation to Pi:** "Our TUI is built on top of [`pi-tui`](https://github.com/earendil-works/pi-mono/tree/main/packages/tui)" ([README](https://github.com/MoonshotAI/kimi-code/blob/main/README.md)). It's a library consumer, not a Pi fork or distribution.
   - The old Python `MoonshotAI/kimi-cli` (Apache-2.0, last release 1.52.0 on 2026-09-22) is archived.
2. **Release.**
   - `@moonshot-ai/kimi-code@2.1.1`, npm 2026-09-24. GitHub release tag `@moonshot-ai/kimi-code@2.1.1`, 2026-09-24.
   - Latest `main` commit: 2026-10-10.
3. **Licence.** MIT ([LICENSE](https://github.com/MoonshotAI/kimi-code/blob/main/LICENSE)). No restrictive clauses.
4. **Install / pin.**
   - `npm i -g @moonshot-ai/kimi-code@2.1.1`, or release binaries with per-file `.sha256` assets.
   - The install script is `https://code.kimi.com/kimi-code/install.sh`; its version parameter is UNVERIFIED.
   - Disable the update preflight with `KIMI_CODE_NO_AUTO_UPDATE=1` ([env-vars](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/configuration/env-vars.md)).
5. **Custom endpoint.**
   - In `config.toml` `[providers.<name>]`, `type` = `openai` (Chat Completions), `openai_responses`, `anthropic` or `kimi`, with `base_url` ([providers](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/configuration/providers.md)).
   - Temporary override without editing config: `KIMI_MODEL_BASE_URL` and related `KIMI_MODEL_*` env vars.
   - Note: `OPENAI_BASE_URL` etc. are read only from `[providers.<name>.env]` in the config, not from the shell ([env-vars](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/configuration/env-vars.md)).
6. **Headless.**
   - `kimi -p "<prompt>" --output-format text|stream-json`. Non-interactive mode defaults to `auto` permission. `-p` can't be combined with `--yolo` or `--auto` ([kimi-command](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/reference/kimi-command.md)).
   - It also exposes an ACP server (legacy CLI: `kimi acp`; UNVERIFIED for Kimi Code).
7. **State / telemetry.**
   - All data lives under `~/.kimi-code/` (config, sessions, logs, OAuth, skills, AGENTS.md, mcp.json). **`KIMI_CODE_HOME`** relocates it.
   - Generic `~/.agents/` resources stay in the real HOME ([data-locations](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/configuration/data-locations.md)).
   - Anonymous telemetry: disable with `KIMI_DISABLE_TELEMETRY=1` (default on [INFERENCE]).
   - The "known provider" flow fetches from models.dev.
8. **Extensions.**
   - Plugins (`kimi.plugin.json` / `.kimi-plugin/plugin.json`) bundle skills, MCP servers and system-prompt fragments; there's also a marketplace ([plugins](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/customization/plugins.md)).
   - It shares `pi-tui` with Pi, but there's **no documented Pi extension API compatibility**.

### Aider

1. **Identity.**
   - https://github.com/Aider-AI/aider, written in Python. PyPI `aider-chat`; uses LiteLLM.
   - Relation to Pi: none.
   - It's an edit-format pair programmer rather than a tool-calling agent loop [INFERENCE].
2. **Release.**
   - PyPI 0.86.2, uploaded 2026-02-12. The GitHub "latest release" is v0.86.0 (2025-08-09).
   - Latest `main` commit: 2026-05-22. Activity is slowing.
3. **Licence.** Apache-2.0 ([LICENSE.txt](https://github.com/Aider-AI/aider/blob/main/LICENSE.txt)). No restrictive clauses.
4. **Install / pin.**
   - `pip install aider-chat==0.86.2` or `uv tool install aider-chat==0.86.2`. The 0.86.2 wheel's `requires_dist` pins every dependency with `==`, which works as a lockfile ([PyPI JSON](https://pypi.org/pypi/aider-chat/json)). PyPI publishes sha256 per file.
   - Update check: `--no-check-update` / `AIDER_CHECK_UPDATE=false` (default True) ([options](https://github.com/Aider-AI/aider/blob/main/aider/website/docs/config/options.md)).
5. **Custom endpoint.**
   - `OPENAI_API_BASE=<endpoint> OPENAI_API_KEY=… aider --model openai/<name>` ([openai-compat](https://github.com/Aider-AI/aider/blob/main/aider/website/docs/llms/openai-compat.md)).
   - Also `--openai-api-base`, plus `--model-settings-file` and `--model-metadata-file` for unknown models.
   - Anthropic via LiteLLM's `anthropic/` model prefix [INFERENCE].
6. **Headless.**
   - `aider --message "…" | --message-file F --yes-always --no-auto-commits [--no-pretty] [--no-stream] <files>`.
   - Python scripting API (`Coder.create`) ([scripting](https://github.com/Aider-AI/aider/blob/main/aider/website/docs/scripting.md)).
   - No JSON event stream.
7. **State / telemetry.**
   - Files: `~/.aider/` (e.g. `analytics.json`, per [analytics.py](https://github.com/Aider-AI/aider/blob/main/aider/analytics.py)) and `~/.aider.conf.yml`.
   - Repo-local files: `.aider.chat.history.md`, `.aider.input.history`, `.aider.tags.cache.*` (UNVERIFIED list).
   - Analytics are opt-in, but "aider will enable analytics for a random subset of users" who are then asked. Use `--no-analytics` per run or `--analytics-disable` / `AIDER_ANALYTICS_DISABLE` permanently ([analytics](https://github.com/Aider-AI/aider/blob/main/aider/website/docs/more/analytics.md)). Uses PostHog/Mixpanel (pinned deps).
8. **Extensions.**
   - No plugin API. Customization is through config files, model settings and `/load` command files.
   - No Pi extension support.

### Amp (closed; brief)

1. **Identity.**
   - https://ampcode.com, npm `@sourcegraph/amp`. Closed source.
   - The Terms name "AMP FRONTIER CORPORATION (“AMP”)" ([terms](https://ampcode.com/terms)). The npm LICENSE.md still says Sourcegraph.
   - Relation to Pi: none.
2. **Release.**
   - npm `latest` 0.0.1791662459-g6be10b, published 2026-10-10 (continuous builds). No public repo, so no commit date.
   - "Free Agent" (2026-09-13): Amp is free to use with your own model subscriptions or keys, with no monthly plan and no BYOK token fees. More BYOK providers, including "Custom endpoint URLs", reached every tier on 2026-09-30 ([news](https://ampcode.com/news/free-agent)). An account is still required (the tiers start with "Sign Up").
3. **Licence / ToS.**
   - npm [LICENSE.md](https://unpkg.com/@sourcegraph/amp@latest/LICENSE.md), verbatim: "© Sourcegraph Inc. All rights reserved. Use of Amp is subject to Amp's [Terms of Service](https://ampcode.com/terms), or separate Amp terms that you have signed with Sourcegraph Inc."
   - Terms licence grant, verbatim: "Amp grants you a limited, revocable, non-exclusive, non-transferable, non-sublicensable license to access and use Amp".
   - Text searches of the [terms](https://ampcode.com/terms) and the [AUP](https://ampcode.com/terms/aup) (last updated 2026-09-10) found no "benchmark" or "reverse engineer" hits; the "compet…" hits were only boilerplate.
   - **Flag (automation)**, [AUP](https://ampcode.com/terms/aup), verbatim:
     - "Only humans may create accounts. You must be a human to create an account. Accounts registered by bots or by other automated methods are not allowed."
     - "You may not use Amp to engage in automatic or excessive bulk activity or coordinated inauthentic activity, including but not limited to spamming, fake accounts …"
     - "If You use Amp in conjunction with another product, you must also follow that product’s AUP."
4. **Install / pin.**
   - `npm i -g @sourcegraph/amp@0.0.1791662459-g6be10b`.
   - Amp "automatically checks and installs new versions in the background" ([cli](https://ampcode.com/docs/markdown/cli)). Disable with `amp.updates.mode: "disabled"` or `AMP_SKIP_UPDATE_CHECK=1` ([settings](https://ampcode.com/docs/markdown/cli/settings)).
5. **Custom endpoint.**
   - "Custom URL" connections can speak `chat-completions`, `responses`, `anthropic-messages` or `google-genai` ([model-routing](https://ampcode.com/docs/markdown/customize/model-routing)).
   - They're managed in the Amp account settings or with `amp config model-providers`, and need an Amp login (`amp login` / `AMP_API_KEY`).
   - UNVERIFIED whether inference requests originate locally (so they can reach `127.0.0.1`) or from Amp servers. The 2026-09-30 update configures custom endpoint URLs in "Model Routing" in personal or workspace settings ([news](https://ampcode.com/news/free-agent)), which does not settle where the requests come from.
6. **Headless.** `amp -x "<prompt>" [--stream-json] [--stream-json-input] [--stream-json-thinking]` ([execute-mode](https://ampcode.com/docs/markdown/cli/execute-mode), [streaming-json](https://ampcode.com/docs/markdown/cli/streaming-json)).
7. **State / telemetry.**
   - Settings: `~/.config/amp/settings.json(c)`, workspace `.amp/settings.json`, and managed settings at `/Library/Application Support/ampcode/` or `/etc/ampcode/` ([settings](https://ampcode.com/docs/markdown/cli/settings)).
   - Threads are stored server-side [INFERENCE from the threads/sharing docs].
   - Telemetry opt-out: UNVERIFIED.
8. **Extensions.**
   - TS/JS plugins (`.amp/plugins/`, `@ampcode/plugin` `PluginAPI`), skills (it also reads `~/.claude/skills/`), MCP and AGENTS.md ([plugins](https://ampcode.com/docs/markdown/customize/plugins), [settings](https://ampcode.com/docs/markdown/cli/settings)).
   - The plugin concept is similar to Pi extensions, but there's no documented compatibility.
   - **Recommendation:** treat Amp as a reference only. Its mandatory account, server-side threads and anti-automation AUP make reproducible offline runs impractical.

### Antigravity CLI (closed; brief)

1. **Identity.**
   - Google's terminal client for Antigravity agents. It shares one agent harness and its settings with the Antigravity 2.0 desktop app ([Antigravity blog, 2026-05-19](https://antigravity.google/blog/introducing-google-antigravity-cli/)).
   - "Built in Go" ([Google Developers Blog, 2026-05-19](https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)). Binary `agy` (Harbor adapter [antigravity_cli.py](https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/installed/antigravity_cli.py)).
   - Relation to Pi: none. It replaced Gemini CLI for consumer tiers on 2026-06-18 (same Google post).
2. **Release.** The ACP registry entry `antigravity-acp` is version 1.3.0 ([agent.json](https://raw.githubusercontent.com/agentclientprotocol/registry/main/antigravity-acp/agent.json), retrieved 2026-10-10). A CLI release feed was not found (UNVERIFIED).
3. **Licence / ToS.** "proprietary" in the registry entry. Terms not reviewed (UNVERIFIED).
4. **Install / pin.** `curl -fsSL https://antigravity.google/cli/install.sh | bash` installs to `$HOME/.local/bin/agy` (Harbor adapter). How to pin a version is UNVERIFIED.
5. **Custom endpoint.** The Harbor adapter documents `GEMINI_API_KEY` with `"modelProvider": "gemini"` in `~/.gemini/antigravity-cli/settings.json`, and says `GOOGLE_GEMINI_BASE_URL` "optionally points model requests at a Gemini-compatible endpoint". Harbor requires https unless `HARBOR_ALLOW_INSECURE_MODEL_BASE_URL=true` ([antigravity_base_url.py](https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/installed/antigravity_base_url.py)). So a mock must speak the Gemini API.
6. **Headless.** `agy --prompt …`. The adapter notes that headless agy "gives up on a --prompt run after 5 minutes by default".
7. **State / telemetry.** Settings under `~/.gemini/antigravity-cli/` (Harbor adapter). Telemetry opt-out: UNVERIFIED.
8. **Extensions.** Agent Skills, Hooks, Subagents, and Extensions as "Antigravity plugins" (Google Developers Blog above). No Pi extension support.

### Cursor CLI (closed; brief)

1. **Identity.** Cursor's terminal agent, binary `cursor-agent` (also `agent`) ([CLI changelog](https://cursor.com/docs/cli/changelog); Harbor [cursor_cli.py](https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/installed/cursor_cli.py)). Closed source. Relation to Pi: none.
2. **Release.** v2026.10.08 is the newest changelog entry. The ACP registry entry `cursor` is 2026.10.01 ([agent.json](https://raw.githubusercontent.com/agentclientprotocol/registry/main/cursor/agent.json)).
3. **Licence / ToS.** "proprietary" in the registry entry. Terms not reviewed (UNVERIFIED).
4. **Install / pin.** `curl https://cursor.com/install -fsS | bash`, into `$HOME/.local/bin` (Harbor adapter). Updates in place with `agent update` (changelog). How to pin a version is UNVERIFIED.
5. **Custom endpoint.** The Harbor adapter passes `CURSOR_API_KEY`, so a Cursor account is needed [INFERENCE]. BYOK through AWS Bedrock with `agent bedrock` (changelog, v2026.10.08). A local mock endpoint: UNVERIFIED.
6. **Headless.** `cursor-agent --yolo --print --output-format=stream-json --model=<m> -- "<task>"` (Harbor adapter). ACP mode ([docs](https://cursor.com/docs/cli/acp.md)). Persistent sessions with `agent persist` and `agent persist attach` (changelog, v2026.08.26).
7. **State / telemetry.** MCP config `~/.cursor/mcp.json`, skills `~/.cursor/skills` (Harbor adapter), CLI config `cli-config.json` (changelog, v2026.07.06). Telemetry opt-out: UNVERIFIED.
8. **Extensions.** Plugins with hooks, skills, MCP, subagents (changelog). No Pi extension support.

### Factory Droid CLI (closed; brief)

1. **Identity.** Factory's terminal agent, binary `droid` ([Droid Exec docs](https://docs.factory.ai/cli/droid-exec/overview.md)). Closed source. Relation to Pi: none.
2. **Release.** npm `droid@0.238.0`, published 2026-10-10T00:40:58Z ([npm](https://registry.npmjs.org/droid)). Factory's release notes listed CLI v0.229.0 on 2026-09-29 ([release notes](https://docs.factory.ai/changelog/release-notes)).
3. **Licence / ToS.** npm `license: UNLICENSED`; registry entry "proprietary" ([agent.json](https://raw.githubusercontent.com/agentclientprotocol/registry/main/factory-droid/agent.json)). Terms not reviewed (UNVERIFIED).
4. **Install / pin.** `npm install -g droid` or `curl -fsSL https://app.factory.ai/cli | sh` (docs). Exact pin: `npm i -g droid@0.238.0`. The ACP entry sets `DROID_DISABLE_AUTO_UPDATE=true` and `FACTORY_DROID_AUTO_UPDATE_ENABLED=false`.
5. **Custom endpoint.** Needs `FACTORY_API_KEY` (docs). Custom models through BYOK (docs link "Custom Models (BYOK)"). A local mock endpoint: UNVERIFIED.
6. **Headless.** `droid exec "<prompt>"` with `-o text|json`. `--input-format stream-jsonrpc --output-format stream-jsonrpc` for multi-turn. `--auto low|medium|high` or `--skip-permissions-unsafe` (docs). ACP: `droid exec --output-format acp-daemon` (registry entry).
7. **State / telemetry.** UNVERIFIED.
8. **Extensions.** MCP, hooks, plugins with commands, droids and skills ([Droid CLI overview](https://docs.factory.ai/droid-cli/overview)). No Pi extension support.

### Hermes Agent

1. **Identity.** https://github.com/NousResearch/hermes-agent. Relation to Pi: none.
2. **Release.** Release candidates `rc.9-v0.21.7` (2026-10-09T20:33Z) and daily canaries such as `v0.21.6+canary.20261010T070026Z` ([releases.atom](https://github.com/NousResearch/hermes-agent/releases.atom)). Prime's runtime table measured v0.21.5 (§5).
3. **Licence.** MIT ([LICENSE](https://github.com/NousResearch/hermes-agent/blob/main/LICENSE), "Copyright (c) 2025 Nous Research"). No benchmark clause in the licence; other terms not reviewed.
4. **Install / pin.** `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --skip-setup` (Harbor [hermes.py](https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/installed/hermes.py)). The adapter can pin a version; the mechanism is UNVERIFIED here.
5. **Custom endpoint.** The Harbor adapter forwards `OPENAI_BASE_URL` with `OPENAI_API_KEY`, so an OpenAI-compatible mock should work [INFERENCE].
6. **Headless.** `hermes --yolo chat -q "<prompt>" -Q --model <m>`, with `--resume <id|latest>` (Harbor adapter).
7. **State / telemetry.** `HERMES_HOME` (the adapter uses `/tmp/hermes`) with `sessions/`, `skills/` and `memories/`. Telemetry opt-out: UNVERIFIED.
8. **Extensions.** Skills (adapter copies skills into `$HERMES_HOME/skills`). No Pi extension support.

### jcode

1. **Identity.** https://github.com/1jehuang/jcode, written in Rust. Relation to Pi: none. Its README lists pi among the harnesses it measures (§5).
2. **Release.** v0.94.0, 2026-10-10T13:19Z ([releases.atom](https://github.com/1jehuang/jcode/releases.atom)). 20,388 stars at retrieval.
3. **Licence.** MIT ([LICENSE](https://github.com/1jehuang/jcode/blob/master/LICENSE)). No benchmark clause in the licence; other terms not reviewed.
4. **Install / pin.** `curl -fsSL https://jcode.sh/install | bash`; Homebrew and source builds are also documented ([README](https://github.com/1jehuang/jcode)). Release checksums: UNVERIFIED.
5. **Custom endpoint.** An OpenAI-compatible provider profile in `~/.jcode/config.toml` (`type = "openai-compatible"`, `base_url = …`), set up with `jcode login --provider openai-compatible` or `jcode provider add`. Local servers work "without requiring an API key" (README).
6. **Headless.** Headless sessions run behind a shared daemon (README, "Headless sessions (swarm workers)"). The exact command and output format: UNVERIFIED.
7. **State / telemetry.** `~/.jcode/config.toml`; a `TELEMETRY.md` exists in the repo (contents not reviewed, UNVERIFIED).
8. **Extensions.** MCP and skills (README). No Pi extension support.

### Prime Agent

1. **Identity.** https://github.com/PrimeIntellect-ai/prime-agent. Rewritten in Rust from TypeScript ([blog, 2026-10-09](https://www.primeintellect.ai/blog/prime-agent-rust)). Relation to Pi: none. Its parity method diffs terminal frames, model requests and session transcripts against the TypeScript build (same blog).
2. **Release.** Pre-release `v0.10.1-beta.6`, 2026-10-10T12:07Z, plus nightly builds ([releases.atom](https://github.com/PrimeIntellect-ai/prime-agent/releases.atom)).
3. **Licence.** MIT ([LICENSE](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/LICENSE), "Copyright (c) 2025-2026 Prime Intellect Ltd."). Other terms not reviewed.
4. **Install / pin.** `curl -fsSL https://app.primeintellect.ai/prime-agent/install.sh | sh` ([README](https://github.com/PrimeIntellect-ai/prime-agent)). The Windows installer verifies a checksum (README). How to pin a version is UNVERIFIED.
5. **Custom endpoint.** UNVERIFIED. Model and MCP lists are "a separate catalog fetched at runtime" (blog), so an offline run must also block or mock that fetch [INFERENCE].
6. **Headless.** Daemon-backed sessions: `prime-agent agents`, `prime-agent attach <agent>`, `prime-agent --resume`, `prime-agent status` (README). The blog names an ACP and daemon protocol. A print or JSON mode is UNVERIFIED.
7. **State / telemetry.** Sessions persist on disk so clients can reattach after a restart (blog). Paths and telemetry opt-out: UNVERIFIED.
8. **Extensions.** UNVERIFIED. No Pi extension support documented.

### Octet

1. **Identity.** https://github.com/skaft-software/octet, written in Rust. Relation to Pi: none in code. Its README names Pi as an influence on some design choices, and an optional `octet-pi-compat` adapter that runs some Pi extensions is "experimental and unstable", source-only and "does not ship in v0.9.4" (README).
2. **Release.** v0.9.4, published 2026-10-15T17:44Z (GitHub releases API). The docs on the default branch describe 0.9.5, which has no release or tag yet (retrieved 2026-10-18), so the arm pins 0.9.4.
3. **Licence.** MIT ([LICENSE](https://github.com/skaft-software/octet/blob/v0.9.4/LICENSE)). No benchmark clause.
4. **Install / pin.** `install-octet.sh` (version-pinned release asset) downloads `octet-0.9.4-<target>.tar.gz` for `aarch64-apple-darwin`, `x86_64-apple-darwin` or `x86_64-unknown-linux-gnu`, and checks it against `OCTET_SHA256SUMS`. That file carries a Sigstore bundle (`OCTET_SHA256SUMS.sigstore.json`). The installer downloads cosign 3.1.3 (its own sha256 per platform is in the script), then runs `verify-blob` with the GitHub Actions OIDC issuer, the identity `release-octet.yml@refs/tags/v0.9.4` or `octet-binaries-v0.9.4`, the workflow name `octet binary release`, the repository and the source commit 7d31ad64ea5f7116f7c735425e50767b4d3944f6. The signature was checked the same way by hand (`Verified OK`) and the three archive hashes in the arm are the ones in that file.
5. **Custom endpoint.** `~/.octet/credentials/custom.json` (mode 0600), a versioned registry of providers with `base_url`, `auth` (`none` or an environment variable), `auto_discover` and a model list with limits ([docs/providers.md](https://github.com/skaft-software/octet/blob/v0.9.4/docs/providers.md#custom-registry)). The wire is OpenAI Chat Completions only. The built-in OpenAI and Anthropic providers have fixed hosts, so Responses and Messages cannot be pointed at a mock. Models are addressed `custom/<provider>/<model>`.
6. **Headless.** `octet -p PROMPT` (print; `--no-session` discards the transcript), `--mode json` (session events) and `--mode rpc` (JSONL with Pi's framing: `prompt`, `get_state`, `get_commands`, `agent_end`; the docs say it is not tested against a pinned Pi release). The TUI is fullscreen by default (`--tui-mode fullscreen|inline`); a first start without a saved theme opens a "Choose terminal appearance" picker.
7. **State / telemetry.** Everything under `~/.octet` (`config.toml`, `credentials/`, `sessions/`, `cache/`, `extensions/`), resolved from `$HOME`. Telemetry is off unless `--telemetry PATH` is given. `OCTET_OFFLINE=true` (or `--offline`) skips model discovery, the models.dev metadata refresh and the interactive start-up release check; it is documented as "not network isolation".
8. **Extensions.** Subprocess extensions over JSON-RPC (API 0.4, `extension.toml` per directory, `--extension-dir`, `--enable-extension`; Python, JS/TS, Rust, C/C++ SDKs). Tool results carry text and optional structured content; the RPC mode reports only the text of a tool result. Pi's TypeScript extensions do not load in the release.

### Zed (ACP host and built-in agent; brief)

- Zed hosts "External Agents" through ACP and installs them from the ACP registry. Its "Common Agents" list includes Claude, Codex, OpenCode, Copilot, Cursor and "Pi Coding Agent" ([External Agents docs](https://zed.dev/docs/ai/external-agents), [Pi on Zed](https://zed.dev/acp/agent/pi)).
- Latest stable v1.23.2 (2026-10-07). A nightly on 2026-10-09 notes "agent: Use ACP v2 content for native prompts" ([releases.atom](https://github.com/zed-industries/zed/releases.atom)).
- Relevance to Buffon: Zed gives an interactive path that drives an arm over ACP instead of a PTY. It is a client, not an arm.

### Other agents in the ACP registry or Harbor (brief, not profiled)

All UNVERIFIED as Buffon candidates. Versions and licences come from each [ACP registry](https://github.com/agentclientprotocol/registry) `agent.json` (retrieved 2026-10-10) unless noted.

- Cline 3.0.70, Apache-2.0 (https://github.com/cline/cline); Harbor has a `cline` adapter.
- Kilo 7.8.8, MIT (https://github.com/Kilo-Org/kilocode).
- Junie 3579.5.0, proprietary (JetBrains); Harbor `junie` adapter.
- Mistral Vibe 2.26.1, Apache-2.0 (https://github.com/mistralai/mistral-vibe); Harbor `vibe` adapter.
- Grok Build 1.0.51, proprietary; Harbor `grok_build` adapter.
- Devin 3000.11.3, proprietary (https://github.com/CognitionAI/devin-cli); Harbor `devin` adapter.
- Qoder CLI 0.2.14, proprietary. Auggie CLI 0.36.0, proprietary (https://github.com/augmentcode/auggie).
- Kimi CLI 1.52.0, MIT: still in the registry and in Harbor (`kimi_cli`), although the repository is archived (see "Dropped" above).
- Harbor-only: `openclaw`, `trae_agent`, `rovodev_cli`, `muse_code`, `cortex_code`, `code_puppy` ([agents/installed](https://github.com/harbor-framework/harbor/tree/main/src/harbor/agents/installed)).

## 5. Prior benchmarks of coding-agent harnesses

Classification key (last column): **Q** = task quality only (pass rate); **Q+E** = quality plus model-side efficiency (tokens / cost / wall time incl. inference); **O** = harness overhead isolated from the model (startup latency, RSS, install/binary size, CPU) using a scripted/mock/faux model or no model turn.

### Summary table

| item | date | what's measured | model held fixed? | mock/scripted model? | reps | overhead vs quality |
|---|---|---|---|---|---|---|
| [Terminal-Bench 2.0](https://arxiv.org/abs/2601.11868) + [Harbor](https://pypi.org/project/harbor/) leaderboard | TB2 released ~2025-11 (UNVERIFIED exact day); paper 2026-01-17; Harbor 0.24.0 2026-10-05 | pass rate per (agent, agent version, model, effort); tokens, cost, avg trial duration | no — rows are harness×model pairs | no | ≥5 trials/task | Q+E |
| [Terminal-Bench 4.0](https://www.tbench.ai/news/terminal-bench-4-0) on Harbor Hub | [v4.0.0](https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0) published 2026-08-26 | pass rate per (agent, model); 66 tasks; calibrated task resources; flat 8 h agent timeout | no | no | UNVERIFIED for 4.0 | Q+E |
| [SWE-bench Verified "Bash Only"](https://www.swebench.com/verified.html) (mini-SWE-agent) | ongoing; full refresh 2026-02 ([Willison](https://simonwillison.net/2026/Feb/19/swe-bench/)) | % resolved, cost, steps | harness fixed, model varies (inverse of Buffon) | no | 1 run (UNVERIFIED) | Q (+cost/steps) |
| [SWE-Bench Pro V2](https://labs.scale.com/leaderboard/swe_bench_pro_public_v2) (Scale Labs) | 2026-09-22 | resolve rate; 642 tasks; rows name model and harness (Claude Code, Codex, mini-swe-agent) | no | no | UNVERIFIED | Q |
| [Quantifying infrastructure noise in agentic coding evals](https://www.anthropic.com/engineering/infrastructure-noise) (Anthropic) | 2026-02-05 | TB 2.0 pass rate and infra error rate across six resource configurations, same model and harness | yes | no | UNVERIFIED for TB; SWE-bench crossover 227 problems × 10 samples | Q (methodology) |
| [The Scaffold Effect (arXiv 2607.22585)](https://arxiv.org/abs/2607.22585v1) | 2026-06-08 | pass rate, tokens/solved task, turns, idle turns, failure modes; Goose/OpenCode/OpenHands-SDK | yes (2 models) | no | 1 trial × 50 tasks × 6 cells = 300 trials | Q+E |
| [Same Model, Different Harness (arXiv 2608.26218)](https://arxiv.org/abs/2608.26218) | 2026-08-26 | F2P fraction, full solves, prompt tokens/turn; two configs of one harness | yes | no | UNVERIFIED | Q+E |
| [Harness Problem / hashline (Stencil)](https://stencil.so/blog/the-harness-problem) | 2026-02-12 | edit-task pass rate, output tokens; 3 edit tools × 16 models | yes (per model) | no | 3 runs × 180 tasks | Q+E (edit tool only) |
| [Aider polyglot leaderboard](https://aider.chat/docs/leaderboards/) | last updated 2025-11-20 | % correct, cost, "correct edit format" %, edit format | harness fixed (aider), format per model | no | UNVERIFIED | Q |
| [OpenHands Index](https://www.openhands.dev/blog/introducing-the-openhands-index) | 2026-01-29 | 5 task categories, accuracy, cost, runtime | harness fixed (OpenHands SDK), model varies | no | UNVERIFIED | Q+E |
| [Artificial Analysis Coding Agent Index](https://artificialanalysis.ai/methodology/coding-agents-benchmarking) | v1.5 since 2026-09 | pass@1 on DeepSWE/TB4/SWE-Atlas-QnA, tokens, cost, wall time per "agent variant" | no — rows are agent variants | no | 3 attempts/task | Q+E |
| [GSO](https://gso-bench.github.io/index.html) | changelog to 2026-09-27 | Opt@1 (speedup vs expert), wall time, turns | harness fixed (OpenHands) | no | estimator from multiple samples (UNVERIFIED count) | Q+E |
| [Databricks internal benchmark](https://www.databricks.com/blog/benchmarking-coding-agents-databricks-multi-million-line-codebase) | 2026-07-08 | pass rate, cost/task, context re-fed per turn; incl. Pi vs Claude Code/Codex | yes (same model+effort across harnesses) | no | UNVERIFIED | Q+E |
| [Composio 8-harness DeepSeek V4 Flash](https://composio.dev/content/best-agent-harness-deepseek-v4-flash) / [Pi vs OMP](https://composio.dev/content/pi-vs-omp) | 2026-08-11 / 2026-09-01 | pass rate, median time, tokens, cost/success; Pi, OMP, Claude Code, Codex, OpenCode, … | yes (but Pi ran different reasoning setting + provider) | no | 1 × 30 tasks per harness | Q+E |
| [aarora79/agentic-coding-harness-benchmarks](https://github.com/aarora79/agentic-coding-harness-benchmarks) | live, 2026 (latest commit UNVERIFIED) | LLM-judge score, tokens, cost, wall-clock; Claude Code vs pi vs omp (+kiro, codex, strands) | yes (per model) | no | small N (5 or 21 tasks; 3 identical runs for router study) | Q+E |
| [kenhia/harness-eval](https://github.com/kenhia/harness-eval) | runs 2026-07-17 / 2026-07-23 | AI-reviewer scores, acceptance tests, wall clock for 5 "harness" setups on Copilot CLI / Claude Code | yes | no | N=1 per cell (explicitly preliminary) | Q (+wall clock) |
| [AgentBench-Live](https://github.com/jackjin1997/AgentBench-Live) | 2026 (UNVERIFIED) | per-domain score, run-to-run variance | no (each CLI's own model) | no | ≥3 target | Q |
| [rawtreedb/harness-benchmark](https://github.com/rawtreedb/harness-benchmark) | UNVERIFIED | steps, tool calls, tokens, duration, pass | configurable | no | UNVERIFIED | Q+E |
| [Prime Agent Rust runtime suite](https://www.primeintellect.ai/blog/prime-agent-rust) | 2026-10-09 | first paint, time-to-type cold/warm, installed size, process-tree RSS; incl. **Pi v1.0.3** | n/a (no inference) | **yes, scripted model** | ± stdev reported; count UNVERIFIED | **O** |
| [jcode README benchmarks](https://github.com/1jehuang/jcode) | headless table measured 2026-09-29; memory rerun on older versions (pi 0.62.0, Claude Code 2.1.86) | PSS for 1 and 10 sessions, extra PSS per added session, time to first frame and to first input; jcode, pi, Codex, OpenCode, Copilot CLI, Cursor Agent, Claude Code, Antigravity CLI | headless table: same model (`claude-sonnet-4-6`) | no for the PTY tables (launch only); headless table uses real model turns | 10 PTY launches per tool | **O** |
| [PiG startup-performance workflow](https://github.com/MichaelKinsy/PiG/blob/main/.github/workflows/startup-performance.yml) | ongoing (weekly cron + every PR) | time to first assistant `message_start` in `--mode json -p`; PiG vs PiG v0.2.0 vs pinned Pi; none/TS-ext/package cases; cold/warm | n/a | **yes, faux provider** | 25 per cell, no retries | **O** |
| [pi_agent_rust perf evidence](https://github.com/Dicklesworthstone/pi_agent_rust) | historical 2026-02-19; README says v0.3.0 claims NOT authorized | `--help`/`--version` latency, RSS, long-session (1M/5M token) resume/append, extension hostcall µbench, binary size | n/a | no provider calls in core tables | "repeated runs per cell" (hyperfine) | **O** |
| [rpi (bigfish1913/pi-rust) bench-vs-pi](https://github.com/bigfish1913/pi-rust) / [HN](https://news.ycombinator.com/item?id=49920411) | 2026-10-01 | `--version`, cold start, RSS at ready, install size vs Node Pi | n/a | offline, isolated config dirs | median (count UNVERIFIED) | **O** |
| [KISS performance section](https://github.com/racetozero/kiss#performance) / [Show HN](https://news.ycombinator.com/item?id=49851739) | 2026-09-26 / measured 2026-10-10 | visible-screen startup (pty+pyte), RSS, long-session memory, p95/p99 | n/a | no model turn | 20 launches, 1000 cold+1000 warm, 3 memory trials | **O** |
| [Pi-Bolt bench/ suite](https://github.com/opensec-git/Pi-Bolt/blob/pi-bolt/bench/README.md) + [docs/BENCHMARKS.md](https://github.com/opensec-git/Pi-Bolt/blob/pi-bolt/docs/BENCHMARKS.md) | results dirs dated 2026-10-10/11 (Pi-Bolt 0.8.0 per docs) | wall, CPU, peak/own memory for `--version`, `-p`, TUI ready-to-type, 75-prompt (~4.2M-token) session, streaming long answers, 200 KB tool-call write, tmux/ConPTY; **Pi-Bolt vs PiG 0.4.1 vs oh-my-pi 18.8.7 vs Pi 1.1.0 on Bun/Node** | n/a (scripted); plus one older real-model run | **yes, scripted OpenAI-compatible fake model** | 21 runs + 3 warm-up per scenario (Linux/macOS), 11+2 Windows, 3 long sessions, 5 tmux rounds; interleaved round-robin; Linux pinned to 4 cores | **O** (+ real-model CPU run) |
| [gi (rcarmo/gi)](https://github.com/rcarmo/gi) | — | no cross-harness benchmark found in README (Pi 1.1.0 TUI parity goldens only) | — | — | — | n/a |
| PiG/pi_agent_rust head-to-head with Pi-Bolt/omp outside Pi-Bolt's suite | — | none found besides items above | — | — | — | — |

### Terminal-Bench 2.0 / Harbor

- Links: [tbench.ai](https://www.tbench.ai/), [TB2 announcement](https://www.tbench.ai/news/announcement-2-0), [paper arXiv 2601.11868](https://arxiv.org/abs/2601.11868) (published 2026-01-17; ICLR 2026), [harbor-framework/terminal-bench](https://github.com/harbor-framework/terminal-bench), [Harbor on PyPI](https://pypi.org/project/harbor/) (0.24.0 uploaded 2026-10-05, Apache-2.0).
- Date: TB2+Harbor announced Nov 2025 ([VentureBeat headline via search](https://venturebeat.com/ai/terminal-bench-2-0-launches-alongside-harbor-a-new-framework-for-testing); exact day UNVERIFIED, page 429). Harbor 0.1.0 uploaded 2025-11-02 ([PyPI](https://pypi.org/pypi/harbor/json)).
- **Terminal-Bench 4.0** ([announcement](https://www.tbench.ai/news/terminal-bench-4-0); [release v4.0.0](https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0), published 2026-08-26):
  - It removes 8 tasks and fixes 19, which leaves 66 tasks. It calibrates task resources with Anthropic's infrastructure-noise method and sets a flat 8 h agent timeout.
  - Terminal-Bench is now "a continuous benchmark" with semantic versioning: a major bump means rerun, a minor bump means regrade, a patch means reuse.
  - Run with `harbor run -d terminal-bench/terminal-bench@4.0.0`. The 4.1 milestone targets "tamper-resistant verifiers".
  - [Artificial Analysis](https://artificialanalysis.ai/evaluations/terminalbench-4-0) runs all 66 tasks with the mini-swe-agent harness and reports pass@1 averaged over three repeats.
- What: 89 hard terminal tasks with unique environments, human solutions, tests ([paper](https://arxiv.org/abs/2601.11868)). Site now headlines TB 4.0; leaderboard columns RANK/MODEL/AGENT/RESOLUTION RATE/COST/TOKENS ([tbench.ai](https://www.tbench.ai/)). Rows are harness+model pairs, e.g. "Gemini CLI, Gemini 3 Flash … 47.4% ± 3.0" ([TB2 leaderboard, search snippet](https://www.tbench.ai/leaderboard/terminal-bench/2.0); page is client-rendered, rows not fetchable).
- Methodology ([SUBMIT.md](https://github.com/harbor-framework/terminal-bench/blob/main/leaderboard/SUBMIT.md)):
  - pinned dataset version; default execution settings; no timeout/resource overrides (CI rejects).
  - all tasks, ≥5 trials per task; errored trials count as reward 0.
  - one submission per (agent, agent version, model, reasoning effort).
  - ATIF trajectory required for every rewarded trial; LLM judge audits reward hacking / "harness cheating".
  - metrics: accuracy ± 95% CI, pass@k, total tokens & cost, average trial duration.
  - community submissions closed for TB 4.0 (maintainer-run only).
- Integrity: documented cheating (modified timeouts, encrypted solutions in agent binary, uploaded tests) and reward hacking (curling solutions) ([Leaderboard Integrity Update](https://www.tbench.ai/news/leaderboard-integrity-update)).
- Harness effect evidence: the TB2 paper reports Claude Opus 4.5 at 52.1% vs 57.8% with two harnesses using 256.9M vs 3.9M input tokens (as cited by [Scaffold Effect §1](https://arxiv.org/html/2607.22585v1); original table not directly verified — UNVERIFIED).
- Harbor ships a Pi adapter: installs `@earendil-works/pi-coding-agent@<version>` (legacy `@mariozechner/...` below 0.74.0) via `npm install -g --ignore-scripts`, writes `models.json` under `PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent` with a custom provider `baseUrl`/`api`, emits ATIF trajectories, supports `max_turns` via an extension ([pi.py](https://raw.githubusercontent.com/harbor-framework/harbor/main/src/harbor/agents/installed/pi.py)). Other adapters include claude_code, codex, opencode, openhands, goose, mini_swe_agent, hermes ([agents/installed](https://github.com/harbor-framework/harbor/tree/main/src/harbor/agents/installed)). No oh-my-pi/PiG/pi_agent_rust adapter seen in that listing.
- Harbor adapter list, rechecked 2026-10-10 ([agents/installed](https://github.com/harbor-framework/harbor/tree/main/src/harbor/agents/installed)):
  - It also has a generic ACP runner (`acp.py`, `acp_registry.py`) that resolves `acp:<id>` registry shorthands or takes an inline registry entry.
  - Newer named adapters: `cursor_cli`, `antigravity_cli`, `copilot_cli`, `devin`, `junie`, `kimi_code`, `qwen_code`, `cline`, `vibe`, `grok_build`, `trae_agent`, `rovodev_cli`, `swe_agent` and `openclaw`.
  - With the generic runner, an arm that speaks ACP can run under Harbor without its own adapter: omp (`--mode acp`), pi_agent_rust (`--acp`), and Pi or PiG through `pi-acp` [INFERENCE: not run].
  - Harbor 0.24.0 is still the latest stable release on PyPI; a `0.24.1.dev` build was uploaded 2026-10-10 ([PyPI JSON](https://pypi.org/pypi/harbor/json)).
- Overhead vs quality: **Q+E**. Duration includes inference; no startup/RSS isolation; real models only.

### SWE-bench harness comparisons

- [SWE-bench Verified page](https://www.swebench.com/verified.html): full leaderboard compares arbitrary systems; **Bash Only** runs every LM in [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) with one [config](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/config/extra/swebench.yaml), "No tools, no special scaffold"; version numbers = mini-SWE-agent tags; 1.x vs 2.x not comparable (tool-calling vs string parsing); temperature 0 for 1.x, unset for 2.x; maintainers "do not aim to tune the configuration".
- Leaderboard has an **Agent** dropdown separating mini-SWE-agent from all agents, and charts for cost, step limits, step distributions ([swebench.com](https://www.swebench.com/)).
- Feb 2026 full re-run of Bash Only by the SWE-bench team; Willison notes it "does mean that the quality of the different harnesses … is not being measured" ([Simon Willison, 2026-02-19](https://simonwillison.net/2026/Feb/19/swe-bench/)).
- **SWE-Bench Pro V2** ([Scale Labs](https://labs.scale.com/leaderboard/swe_bench_pro_public_v2), 2026-09-22, co-developed with Reflection):
  - 642 tasks across 11 repositories, down from 731. A "locked evaluation protocol".
  - "The agent phase now reaches only the model endpoint". Every agent diff is regraded on a pristine image, and both grades are published.
  - A two-sided gate: every task must pass with the reference patch and fail with the empty patch.
  - Leaderboard rows name the harness, for example "(Claude Code)", "(Codex)", "(mini-swe-agent)". Uncapped cost, 250-turn limit.
  - **Q**, harness not held fixed.
- Overhead vs quality: **Q** (+cost/steps). Harness fixed, model varies, so it does not measure harnesses at all; useful only as a neutral-baseline pattern.

### Fixed-model scaffold studies

- **Scaffold Effect** ([arXiv 2607.22585](https://arxiv.org/abs/2607.22585v1), 2026-06-08, Sentient Labs): Qwen 3.6 Plus & MiniMax M2.5 via OpenRouter × Goose/OpenCode/OpenHands-SDK on 50 stratified Terminal-Bench Pro tasks; Daytona sandbox; 900 s cap; near-identical system prompt; run through Harbor. Up to 40× difference in tokens per solved task; paired pass-rate differences 0–8 pp, mostly CIs include zero; harness failure fingerprints replicate across models. Recommends reporting tokens, latency and full harness spec ([HTML §3](https://arxiv.org/html/2607.22585v1)). **Q+E**.
- **Same Model, Different Harness** ([arXiv 2608.26218](https://arxiv.org/abs/2608.26218), 2026-08-26): ablation of context-management inside one harness; tight 20,480-token window, 480 s endpoint, 169 Verified tasks: F2PF 28%→49%, full solves 43→72; fewer prompt tokens/turn. **Q+E**.
- **Anthropic infrastructure noise** ([post, 2026-02-05](https://www.anthropic.com/engineering/infrastructure-noise)): same Claude model and harness on TB 2.0 across six resource configurations, from strict 1x enforcement to uncapped.
  - Infra errors fell from 5.8% to 0.5%. Success rose by 6 pp at uncapped (p < 0.01).
  - Up to about 3x headroom, the gain is mostly fewer infra errors (p = 0.40 for score); above that, success "climb[s] faster".
  - It recommends specifying a guaranteed allocation and a separate kill threshold per task, and calibrating the band so that floor and ceiling scores fall within noise. It also says that "leaderboard differences below 3 percentage points deserve skepticism until the eval configuration is documented and matched".
  - A SWE-bench crossover (227 problems, 10 samples) showed +1.54 pp at 5x RAM. **Q** (methodology).
- **The Harness Problem / hashline** ([Stencil, 2026-02-12](https://stencil.so/blog/the-harness-problem), also [blog.can.ac](http://blog.can.ac/2026/02/12/the-harness-problem)): only the edit tool varied (patch / str_replace / hashline); 16 models, 3 runs × 180 mutated-React-file tasks, fresh session each; Grok Code Fast 1 6.7%→68.3%; code in omp [react-edit-benchmark](https://github.com/can1357/omp/tree/main/packages/react-edit-benchmark). Follow-up [nwyin/edit-bench](https://github.com/nwyin/edit-bench) (date UNVERIFIED). Author reports a Gemini account disabled while benchmarking (vendor ToS risk). **Q+E** (output tokens), no overhead.
- **Aider leaderboards** ([leaderboards](https://aider.chat/docs/leaderboards/), updated 2025-11-20): 225 Exercism exercises; reports per-model edit format (diff/whole/architect) and "correct edit format" %. Harness fixed; format is a harness knob. **Q**.
- **OpenHands Index** ([blog 2026-01-29](https://www.openhands.dev/blog/introducing-the-openhands-index), [site](https://index.openhands.dev/home)): OpenHands Software Agent SDK fixed; SWE-bench Verified, commit0, SWE-bench Multimodal (verified), SWT-Bench, GAIA; ability, cost, runtime; code in [OpenHands/benchmarks](https://github.com/OpenHands/benchmarks). **Q+E**, model comparison not harness comparison.
- **Artificial Analysis Coding Agent Index** ([methodology](https://artificialanalysis.ai/methodology/coding-agents-benchmarking), [page](https://artificialanalysis.ai/agents/coding-agents)): v1.5 (Sept 2026) = DeepSWE v1.1 (113) + Terminal-Bench 4.0 (66) + SWE-Atlas-QnA (124); 3 attempts/task, pass@1; each row an "agent variant, not a model"; reasoning settings are separate rows; cost incl. cache pricing; reward-hack judge via `harbor analyze`; internet blocked for DeepSWE agent phase. Numbers "Not publicly available" on the fetched page. **Q+E**.
- **GSO** ([site](https://gso-bench.github.io/index.html), [repo](https://github.com/gso-bench/gso), MIT per search): 102 optimization tasks; "All models are run with the OpenHands scaffold unless otherwise specified"; Hack Detector; network isolation added 2026-07-12; reports median wall-clock & turns. **Q+E**, harness fixed.
- **LiveSWEBench** ([liveswebench.ai](https://liveswebench.ai/)): page body not renderable; methodology UNVERIFIED.
- **Vals AI**: [methodology](https://www.vals.ai/methodology) and [Vibe Code Bench](https://www.vals.ai/benchmarks/vibe-code) are model-centric; no harness-held-fixed study found (UNVERIFIED).
- **Databricks** ([blog 2026-07-08](https://www.databricks.com/blog/benchmarking-coding-agents-databricks-multi-million-line-codebase)): tasks from own merged PRs, hand-reviewed; harnesses run "standard, out of the box"; same model + same thinking effort through Claude Code/Codex vs Pi gave >2× cost difference at equal quality; Pi sent ~3× less context per turn. Private tasks; reps/hardware UNVERIFIED. **Q+E**.
- **Composio** ([8 harnesses on DeepSeek V4 Flash, 2026-08-11](https://composio.dev/content/best-agent-harness-deepseek-v4-flash); [Pi vs OMP, 2026-09-01](https://composio.dev/content/pi-vs-omp)): 30 MCP/SaaS workflows, programmatic verifier, 900 s cap, binary pass. Pi 20/30, 132.2 s median, ~559k tokens/task, $0.028/success; OMP 17/30, 272.4 s, ~742k, $0.103. Caveat stated by authors: Pi ran high (not max) reasoning and 24/30 trials via DeepSeek API instead of OpenRouter; harnesses count tokens differently. Single run per task. **Q+E**; not coding tasks.
- **aarora79/agentic-coding-harness-benchmarks** ([repo](https://github.com/aarora79/agentic-coding-harness-benchmarks), MIT-0): harness × model on real repo issues; harnesses claude, pi, omp, kiro, codex, strands; LLM judge 0–100; tokens, latency, turns; Bedrock / LiteLLM / vLLM hosting. Claims pi wins wall-clock 10/12 models vs Claude Code and ties/wins cost & quality ([comparison doc](https://raw.githubusercontent.com/aarora79/agentic-coding-harness-benchmarks/main/docs/agentic-coding-swe-comparison-swe3.md)). README warns numbers "still moving". Small N (5 tasks in that table). **Q+E**.
- **kenhia/harness-eval** ([repo](https://github.com/kenhia/harness-eval)): same model (Opus 4.8 / Haiku 4.5), 5 harness setups + bare controls; explicitly "N = 1 per cell"; a duplicated cell spread 44% in wall clock. **Q**.
- **AgentBench-Live** ([repo](https://github.com/jackjin1997/AgentBench-Live)): Claude Code vs Gemini CLI, 10 tasks, Docker; reports run-to-run spread (tool-001: 0.0 vs 0.7). **Q**.
- **rawtreedb/harness-benchmark** ([repo](https://github.com/rawtreedb/harness-benchmark)): web UI, one scenario, records steps/tool calls/tokens/duration. **Q+E**.

### Pi-family comparisons (Pi / Pi-Bolt / PiG / oh-my-pi / pi_agent_rust)

Note: the rpi benchmark below links [bigfish1913/pi-rust](https://github.com/bigfish1913/pi-rust), while §3 profiles [revpidev/rpi](https://github.com/revpidev/rpi). Whether these are the same project (for example a rename or mirror) is UNVERIFIED.

- **Prime Agent runtime suite** ([blog 2026-10-09](https://www.primeintellect.ai/blog/prime-agent-rust)): fresh 4-core / 8 GB Prime Sandbox per benchmark; real terminal via screen emulator; scripted model; inference excluded; noise checks withhold unstable results. Pi v1.0.3: first paint 306.3 ± 6.7 ms, cold time-to-type 317.7 ± 8.0 ms, warm 240.4 ± 5.9 ms, installed 456.0 MB, process-tree RSS 138.1 ± 0.7 MB (vs Claude Code 2.1.289, Codex 0.160.0, Hermes 0.21.5, Prime TS/Rust). Authors caution: "Without a common benchmark standard, comparisons should be interpreted with caution." Not harness-neutral (vendor's own suite). **O**.
- **PiG startup timing (MichaelKinsy/PiG)** ([workflow](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/.github/workflows/startup-performance.yml), [script](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/automation/perf/startup_timing.py), [budgets](https://raw.githubusercontent.com/MichaelKinsy/PiG/main/automation/perf/startup-budgets.json)):
  - ubuntu-24.04 GitHub runner; advisory (`continue-on-error: true`); on PR, push to main, weekly cron.
  - builds current PiG and v0.2.0 baseline with `-trimpath -ldflags='-s -w'`; Pi oracle from npm lockfile; asserts Pi version equals PiG's pinned upstream version.
  - isolated HOME per trial (`HOME`, `PIG_HOME`, `PIG_CODING_AGENT_DIR`, `PI_CODING_AGENT_DIR`, `XDG_*`, `TMPDIR`), `PI_OFFLINE=1`, `PI_TELEMETRY=0`, faux provider (`PIG_TEST_FAUX`, Pi gets `-e test-faux-provider.ts`), `--offline --no-session --mode json -p "What is 20+22?"`.
  - metric = ms until first assistant `message_start` event; validity requires answer "42", `agent_end`, clean stderr; cases none / TS extension / package; cold (fresh home) vs warm; 25 runs per cell, rotated order, no retries; records SHA-256 of binaries, node/go versions.
  - budgets: PiG no-extension ≤1.05× baseline, extension cases ≤1.15× Pi; runtime archive ≤12 MiB.
  - Published numeric results: only as CI artifacts/step summaries (not fetched — UNVERIFIED). **O**.
- **pi_agent_rust** ([README](https://raw.githubusercontent.com/Dicklesworthstone/pi_agent_rust/main/README.md), [historical report](https://raw.githubusercontent.com/Dicklesworthstone/pi_agent_rust/main/docs/planning/BENCHMARK_COMPARISON_BETWEEN_RUST_VERSION_AND_ORIGINAL__GPT.md)): README now omits comparative numbers ("v0.3.0 performance-claim status: NOT authorized"; "Fresh comparative measurement pending"). Historical 2026-02-19 report: Rust `--help`/`--version` means ~3.02/2.77 ms vs prior legacy ~1.0 s (Node) / ~0.73 s (Bun) — legacy reruns were blocked, so values come from older artifacts; methodology: hyperfine, `/usr/bin/time` footprints, matched-state 1M/5M-token session workloads, release binaries, provider costs excluded. Third-party summary claims "10x startup / 70% memory" ([techbytes](https://techbytes.app/posts/rpi-rust-rewrite-pi-agent-harness-delivers-10x-startup-speedup) — appears to concern rpi, not pi_agent_rust; UNVERIFIED). **O**.
- **rpi / bigfish1913/pi-rust** ([README](https://github.com/bigfish1913/pi-rust), [HN 2026-10-01](https://news.ycombinator.com/item?id=49920411)): Windows 11 x86_64; `node scripts/bench-vs-pi.mjs`; both offline with fresh isolated config dirs. rpi 17.5 ms `--version`, 17.7 ms cold start, 12.0 MiB RSS at ready, 21.8 MiB install vs Pi 169.5 ms / 189.5 ms / 91.5 MiB / ~385 MiB. README warns rpi silently loads global plugins unless `RPI_CODING_AGENT_DIR`/`RPI_OFFLINE` are set (Pi: `PI_CODING_AGENT_DIR`/`PI_OFFLINE`). HN critique: no Pi-extension support, so "apples to oranges"; real Pi startup dominated by extensions/skills. **O**.
- **KISS** ([README perf](https://github.com/racetozero/kiss#performance)): Apple M4/macOS; pty 160×40 + pyte; timing from before process creation to visible screen cells; 1000 cold + 1000 warm launches; RSS via `ps` over 20 launches; explicitly declines direct comparison with Prime's suite because hardware/observer differ. Tracks Pi v0.99.1 but no Pi extension runtime. **O**.
- **oh-my-pi**: Composio Pi vs OMP (above, **Q+E**); aarora79 includes omp (**Q+E**); omp's own "metaharness" benchmark harness documented on [DeepWiki](https://deepwiki.com/can1357/oh-my-pi/12.8-benchmark-harness-(metaharness)) (HTTP 429; contents UNVERIFIED). No public startup/RSS comparison of omp vs Pi found.
- **PiG vs Pi publicly posted numbers**: none found outside CI artifacts. r/PiGCodingAgent and X @PiGCodingAgent searched ([search](https://www.reddit.com/r/PiGCodingAgent/)); no benchmark posts surfaced (UNVERIFIED — Reddit blocked fetch with JS challenge).
- **Reddit r/LocalLLaMA**: thread "According to Databricks, pi-coding-agent is 2x…" ([link](https://www.reddit.com/r/LocalLLaMA/comments/1usrek0/according_to_databricks_picodingagent_is_2x)) — fetch blocked; it summarises the Databricks post above.
- **Pi-Bolt** ([repo](https://github.com/opensec-git/Pi-Bolt), MIT; AOT-compiled Pi on a Bun/JavaScriptCore runtime; latest release `bolt-v0.8.0`, 2026-10-10, per [releases.atom](https://github.com/opensec-git/Pi-Bolt/releases.atom)). Its `bench/` suite is the **only public head-to-head of Pi, PiG and oh-my-pi under one methodology** found:
  - Tools ([bench/README.md](https://raw.githubusercontent.com/opensec-git/Pi-Bolt/pi-bolt/bench/README.md)): `benchmark.py` (`--version`, `-p`, interactive TUI on a pty; fresh processes, interleaved round-robin; wall, CPU, peak memory), `long_session.py` (40–75 prompts ≈4.2M tokens; per-prompt time/CPU, memory, request size), `large_write.py` (tool-call args streamed 16 chars at a time, 50/200 KB), `long_answer.py` (CPU to stream 5k–60k-char Markdown), `tmux_check.py`/`conpty_check.py` (time to interactive, keystroke latency, idle CPU, frames), `pauses.py` (stalls, p99 frame time, GC pauses), `plugin_bench.py` (extension compiled-in vs runtime-loaded), `stress.py`, `e2e_tools.py` (tool transcripts byte-identical to reference build), `floor.c` process-floor baseline (subtracts OS process-creation cost, important on Windows).
  - Model: local `fake_model.py` speaking OpenAI chat-completions; per prompt four `read` tool calls on Pi source fixtures then an answer; "no network and no model latency, so the figures measure Pi and its runtime" ([BENCHMARKS.md](https://raw.githubusercontent.com/opensec-git/Pi-Bolt/pi-bolt/docs/BENCHMARKS.md)).
  - Isolation: each run gets a throwaway Pi home with only the fake model; env cleared of `BUN_*`, `NODE_*`, `PI_*`; PiG gets `PIG_HOME`/`PIG_CODING_AGENT_DIR`/`PIG_OFFLINE`, oh-my-pi a `models.yml` (same docs).
  - Reps/hardware: Linux AMD EPYC 7B13 cloud VM pinned to 4 cores (`--cpus`, taskset), macOS Apple M5 MacBook Air (no pinning; "differences under about 10% are within its noise"), Windows i5-1335U; medians of 21 runs after 3 warm-ups; 3 long sessions; 5 tmux rounds; mean of two rounds for long answers/large files; heavy-load sessions discarded and re-run; speed only measured on builds passing correctness checks.
  - Results (Linux, medians; [README](https://github.com/opensec-git/Pi-Bolt)): ready-to-type Pi-Bolt 45 ms / PiG 38 / omp 988 / Pi-Bun 128 / Pi-Node24 316; CPU one prompt `-p` 80 / 261 / 1,752 / 323 / 618 ms; peak memory `-p` 124 / 55 / 468 / 133 / 135 MB; 200 KB tool write 0.8 / 92 / 3.7 / 26.9 / 37.2 s; memory after 4.2M-token session 187 / 311 / – / 275 / 576 MB (omp excluded: auto-compacts and stops answering the scripted session).
  - Real-model run (older, Pi-Bolt 0.6.1 vs Pi 1.0.0, 10 rounds of a tool prompt): wall time not distinguishable (permutation test), Pi's own CPU 0.20 s vs 0.49 (Bun) / 0.76–0.77 s (Node) — shows harness CPU is measurable even under real inference.
  - Caveat: vendor-run (Pi-Bolt authors) suite; not neutral. **O**.
- **gi** ([rcarmo/gi](https://github.com/rcarmo/gi), Go, MIT): Pi-inspired, targets Pi 1.1.0 TUI workflows; README shows parity/golden tests vs published Pi 1.1.0 but no overhead or quality benchmark vs other harnesses.
- Apart from Pi-Bolt's vendor suite, no neutral head-to-head of Pi vs Pi-Bolt vs PiG vs oh-my-pi vs pi_agent_rust exists as of 2026-10-10 (based on the searches above); pi_agent_rust appears in none of the multi-harness suites.

### Methodological lessons for Buffon

1. **Separate the two axes.** Every public harness leaderboard (TB, AA, Composio, Databricks, aarora79) mixes harness overhead with inference time. Only Prime's suite, Pi-Bolt's `bench/`, PiG's CI workflow, rpi, KISS and pi_agent_rust isolate overhead, and all of them use scripted/faux models. Buffon's mock endpoint should own the **O** axis; quality comparisons belong elsewhere or must hold the model fixed.
2. **Define the end-point event precisely.** PiG: first assistant `message_start` in JSON mode with answer validation; Prime/KISS: visible screen cells via pty emulator; rpi: answer to first command. `--version` timing alone is misleading (HN critique). Report several end-points (version, first JSON event, first token rendered, agent_end).
3. **Measure with and without extensions/packages.** Pi startup is extension-dominated per users ([HN](https://news.ycombinator.com/item?id=49920411)); PiG budgets cases none/TS/package. Ports lacking Pi-extension support (KISS, rpi) must be flagged, not ranked like-for-like.
4. **Isolate HOME and every config env var per harness.** rpi warns of silently loading global plugins; PiG sets `HOME`, `XDG_*`, `TMPDIR`, `*_CODING_AGENT_DIR`, offline + telemetry-off flags. Cold = fresh HOME per trial; warm = reused HOME after seeding.
5. **Repetitions, ordering, no retries.** PiG: 25 runs, rotated order, failure aborts; KISS: 1000+1000 launches, alternating versions; TB: ≥5 trials, errors count as 0. Report median + p90/p95 + spread; single-run comparisons (Composio, kenhia N=1) showed large variance (kenhia: 44% wall-clock spread on an identical cell).
6. **Record provenance.** Binary SHA-256, exact version, runtime (Node/Bun/Go/Rust) versions, hardware/cgroup limits (pi_agent_rust `env_fingerprint.json`; Prime fixed 4-core/8 GB sandbox). Don't compare numbers across hardware/observers (KISS explicitly refuses).
7. **Pin settings and forbid overrides.** TB rejects timeout/resource changes; AA makes reasoning effort a separate row; Composio's Pi row was confounded by a different reasoning level and provider. Buffon should key results on (harness, version, model, effort, config hash).
8. **Count tokens at the mock endpoint, not from harness self-reports.** Composio notes harnesses count runtime tokens differently; Databricks/Scaffold Effect show context-per-turn is the main harness cost driver. A mock server can log exact request bytes/tokens per turn — a harness-neutral "token overhead" metric (system prompt + tool schema size).
9. **Guard against gaming.** TB and GSO needed cheating/reward-hack detection (solutions in binaries, curl-ing answers). For overhead benchmarks: verify the answer, forbid benchmark-specific fast paths, check stderr, keep trajectories.
10. **Fixed-harness baselines are the inverse problem.** SWE-bench Bash Only / OpenHands Index / GSO fix the harness to compare models; Buffon fixes the (mock) model to compare harnesses — cite them as precedent for "neutral configuration, no tuning", not as harness rankings.
11. **Vendor-run suites need a neutral standard.** Prime explicitly says comparisons need caution "without a common benchmark standard" — Buffon's neutral branding and published harness adapters address exactly that gap.
12. **Subtract a process floor and gate on correctness.** Pi-Bolt runs a minimal native `floor` program each round to remove OS process-creation cost (10–25 ms on Windows) and only times builds that pass byte-identical tool-transcript checks; Buffon should do both.
13. **Scripted conversations must suit every harness.** In Pi-Bolt's long-session test oh-my-pi auto-compacted and stopped answering the script, so it was left out; Buffon's mock model must cope with harness-specific compaction, tool names and edit formats, or report "not comparable" instead of a number.
14. **Measure CPU and memory, not just wall time.** With a real model Pi-Bolt found wall time indistinguishable across runtimes while harness CPU differed 2–4×; per-process CPU time (rusage/cgroup) and own/private memory are the stable overhead signals.
15. **Pin the renderer mode per arm.** Pi's `tuiMode` defaults to `"fullscreen"` ([settings-manager.ts at v1.1.0](https://github.com/earendil-works/pi/blob/v1.1.0/packages/coding-agent/src/core/settings-manager.ts), line 184). Claude Code starts new installs in its fullscreen renderer and switches with `/tui` or `CLAUDE_CODE_NO_FLICKER`. That renderer "only renders messages that are currently visible" and sends "only the cells that changed between frames" ([fullscreen rendering](https://code.claude.com/docs/en/fullscreen)). PTY metrics (bytes written, CPU per frame, memory) are not comparable across renderer modes, so the mode belongs in the arm manifest and in every row.
16. **Report resource floor and ceiling separately.** Following [Anthropic's infrastructure-noise study](https://www.anthropic.com/engineering/infrastructure-noise) (2026-02-05) and [TB 4.0's calibration](https://www.tbench.ai/news/terminal-bench-4-0), a run states the guaranteed allocation and the kill limit, not one pinned value.
17. **Memory scaling: PSS per added session, and RSS with a large session loaded.** [jcode's README](https://github.com/1jehuang/jcode) reports PSS for 1 and 10 sessions and "Extra PSS per added session" (pi at about 76.5 MB per added session, measured on pi 0.62.0). [Prime's suite](https://www.primeintellect.ai/blog/prime-agent-rust) reports process-tree RSS with a 10 MiB session. Both separate per-session cost from the binary pages that processes share, which RSS at one session cannot do.
18. **Record protocol versions per arm.** MCP 2026-07-28 removes the `initialize` handshake and protocol sessions ([changelog](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/changelog.mdx)), while Pi 1.1.0 requests 2025-11-25 (`LATEST_PROTOCOL_VERSION` in [types.ts at v1.1.0](https://github.com/earendil-works/pi/blob/v1.1.0/packages/mcp/src/protocol/types.ts)). ACP v2 is published as draft beside v1 ([v2 migration](https://agentclientprotocol.com/protocol/v2/migration)). An MCP or ACP workload must state which version each arm negotiated.
