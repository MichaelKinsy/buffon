# Buffon design

Status: draft for the owner's review. Private. Nothing here is published, and no harness author has been contacted.

## 1. Purpose

Buffon measures coding-agent **harnesses**: the program between a person and a model. It does not rank models. Every harness in a run talks to the same scripted mock model, so the measured differences come from the harness alone: how fast it starts, what it costs to stream, how it scales with a long session, whether it survives faults, which Pi extensions it runs, and how closely it matches Pi.

Buffon centres on Pi and the harnesses built from it or modelled on it. It also includes a small set of well-known terminal coding agents as reference points.

Out of scope:

- Model quality, task success rates and leaderboards of models. An optional task-completion track (section 8) exists only to check that harness overhead does not change outcomes. It never produces a model ranking.
- Hosted-service latency. The mock is local, so network and provider behaviour are not part of any score.
- Any number from a harness Buffon may not run under its licence or terms (section 9).

## 2. Principles

1. **Neutral.** Buffon belongs to no harness. Its name, repository, documentation and reports carry no harness branding. Every maintainer states which harnesses they work on in `MAINTAINERS.md`, and a result that favours a maintainer's own harness needs an independent reproduction before it is marked final (section 10).
2. **Reproducible.** Every arm is pinned to an exact artifact with a checksum. Every run records the host, kernel, CPU, governor, cgroup limits, mock version, lockfile hash and seed. A third party with the same hardware class can rerun any cell from the published run directory.
3. **Honest.** Raw samples are published with every summary. Losses are reported as plainly as wins. An arm that cannot run a scenario gets a "cannot run" row with the reason, never a blank or a silent skip. Every comparison states its noise floor.
4. **Harness-only.** No live model, no vendor login, no network egress. The egress audit fails a run that connects anywhere but the mock.
5. **Licence-clean.** An arm is included only when its licence and terms permit the run, the publication of results and the people running it (section 9).

## 3. Harnesses

The survey in `HARNESS-SURVEY.md` (snapshot 2026-10-10, with sources) lists 24 candidates. The initial roster:

| tier | arm | relation to Pi | latest release seen in the survey (retrieved 2026-10-10; re-verified at each run's lock time) | headless modes | Pi extensions |
|---|---|---|---|---|---|
| reference | **Pi on Node** | upstream | `@earendil-works/pi-coding-agent`, release install lock (version in `arms/pi-node/arm.toml`) | print, json, rpc | native |
| Pi family | Pi on Bun | upstream, Bun runtime | release binary `pi-<os>-<arch>`, plus a `bun build --compile` arm on a pinned Bun (versions in `arms/`) | print, json, rpc | native |
| Pi family | PiG | Go port | release archive + `SHA256SUMS` (0.4.1 today; 0.5.0 when released) | print, json, rpc | Node sidecar |
| Pi family | Pi-Bolt | fork, AOT on Bun/JSC | `bolt-v0.8.0` archive + `SHA256SUMS` + Ed25519 signature | print, json, rpc | native |
| Pi family | omp (oh-my-pi) | fork, Bun + Rust core | v18.8.9 binary + `SHA256SUMS.txt` | print, json, rpc, acp | compatibility layer (partial) |
| Pi family | gi (rcarmo/gi) | Go agent on a Go port of pi-ai | source at a commit (no releases) | TUI by default and a REST/SSE web API (`-web`); no print or JSON mode, so headless workloads use the web API or the PTY driver | none |
| Pi family | rpi (revpidev/rpi) | Rust port | release archive + `.sha256` | print, json, rpc | none known |
| Pi family, held | pi_agent_rust | Rust port | v0.7.1 + `.sha256` + minisign | print, json, rpc, acp | QuickJS (partial) |
| reference | OpenCode 1 | unrelated | `opencode-ai` 1.19.0 npm package and its platform package, locked | `run --format json`, `serve` | none |
| reference | OpenCode 2 | unrelated | `@opencode/cli` 2.0.29 npm package and its platform package, locked (released; `latest` since 2.0.0, 2026-09-11) | `run --format json`, `serve` | none |
| reference | Codex CLI | unrelated | 0.162.1 npm platform package, locked | `exec --json` | none |
| reference, operator terms | GitHub Copilot CLI | unrelated, closed | 1.0.95 npm platform package, locked, installed from the vendor at run time; bring-your-own-key mode, no GitHub sign-in | `-p --allow-all-tools -s` | none |
| reference, operator terms | Claude Code | unrelated, closed | 2.1.296 npm platform package, locked, installed from the vendor at run time; Anthropic Messages against the mock, dummy key | `-p --dangerously-skip-permissions` | none |

The versions above are the latest releases the survey found, not the pins of any run: the existing benches pinned Pi-Bolt 0.7.4 and a Bun 1.4.2 `--compile` arm on the same day. A run's pins live only in its `arms.lock`, with the retrieval date of each artifact.

An "operator terms" arm (Claude Code, Copilot CLI) is never in the default set, `all` or a glob: it runs only when named in full and the operator accepts its vendor terms (`--accept-terms`, section 9), and raw.json records `operator_terms_accepted`. "Held" arms stay out of every published run until the licence questions in section 9 are settled. The owner of Buffon decides, on a written legal reading of the licence or terms. A held arm never appears in a published figure or table, not even greyed out. Candidates for later rounds are the other Pi ports (nowa/gi, sky-valley/pi, pie, nktkt/pi), Kimi Code CLI (built on Pi's TUI library), Gemini CLI, Qwen Code, Goose and Crush. Each enters through the contribution path in `CONTRIBUTING.md`.

**Pi on Node is the reference arm.** Every ratio in a report is relative to it, at the Pi version the run pins. When Pi releases, the reference moves with it, and earlier runs keep their own reference.

## 4. Scored axes

Each axis is a set of metrics, each with a unit, a workload and a direction. No metric is ever folded into another axis.

### A. Pi philosophy

Pi's stated design is a minimal core that users extend, and a small prompt. The axis measures that design, not a judgement of it.

| metric | unit | how |
|---|---|---|
| system prompt + tool schema tokens, first turn | tokens (wire bytes / 4 as the mock reports usage; no tokenizer is pinned: METHODOLOGY section 3) | the mock records every request body; default config, no project context files |
| steady-state tokens added per turn | tokens/turn | slope over turns 2-20 of the scripted read-and-answer policy |
| bytes sent per turn | bytes/turn | same requests, wire bytes |
| install footprint | MB on disk; files; runtime dependency count | size of the installed arm root; npm/cargo/go dependency count from the lock |
| idle resident memory | MB | RSS and PSS 5 s after the prompt is ready, no session |
| extension surface | count of Pi extension API members the arm exposes | the Pi extension conformance corpus (axis E) reports which members exist |

There is no composite "philosophy score". The axis is a profile.

### B. Head-to-head performance

| metric | unit | workload |
|---|---|---|
| startup | ms wall and ms CPU | `--version` exec to exit; exec to prompt-ready in a PTY; exec to the first answered RPC command; first frame; first request sent; each warm and cold (page cache dropped) |
| startup with a large agent directory | ms | 200 skills, 20 extensions, 500 stored sessions |
| streaming | CPU ms per 1,000 streamed tokens; first SSE byte to first painted character | the mock streams a 60,000-character answer at fixed token rates (100, 1,000, 10,000 tokens/s) into the interactive TUI and into print mode |
| large writes | wall and CPU for one tool call | a `write` tool call carrying 50 KB, 200 KB and 1 MB of content, streamed as arguments; and a 200-line `edit` |
| interactive CPU | CPU ms per keystroke; CPU per frame; idle CPU over 60 s | PTY driver types into the editor during a stream and while idle, at 80x24 and 240x60 |
| per-turn harness overhead | ms wall added per turn; CPU ms per turn | 20-turn tool loop, mock replies instantly; harness time = wall minus mock time |
| first-token latency added | ms from the model's first SSE byte to the first character the user sees | the same stream, interactive and print; also measured against a pinned local model (llama.cpp) to confirm the mock result holds on a real local path |

Every workload in axes B to D runs on at least two wire APIs (OpenAI Chat Completions and Anthropic Messages) and is reported per API, so no arm is judged only on the path it optimises least. An arm that speaks only one API is reported on that one, with the other marked "cannot run".

Every PTY workload pins each arm's renderer mode and records it beside the result, because a harness can draw on the main screen or on the alternate screen, and the two write very different byte streams to the terminal. Pi's `tuiMode` setting defaults to `"fullscreen"` ([settings-manager.ts at v1.1.0](https://github.com/earendil-works/pi/blob/v1.1.0/packages/coding-agent/src/core/settings-manager.ts), line 184). Claude Code starts new installs in its fullscreen renderer and switches with `/tui` or `CLAUDE_CODE_NO_FLICKER` ([fullscreen rendering](https://code.claude.com/docs/en/fullscreen), "Fullscreen by default"; retrieved 2026-10-10). An arm with two renderers is run in each, as two rows.

### C. Scaling

| metric | unit | workload |
|---|---|---|
| long session | resume wall and CPU; RSS after resume and after 5 and 50 prompts; CPU per prompt | synthetic Pi session files: 1,000 / 10,000 / 46,000 entries (the 46k shape: 299 MB, 63 compactions, 17 leaves) |
| large-session memory | MB RSS of the whole process tree | resume a 10 MiB session file and wait for prompt-ready; the method of [Prime Agent's runtime suite](https://www.primeintellect.ai/blog/prime-agent-rust) ("Process-tree RSS · 10 MiB session", 2026-10-09) |
| large context | RSS; CPU and wall per prompt | active context of 100k, 1M, 2M and 4M tokens |
| conversation growth | CPU per prompt at prompt 1, 15 and 75; slope | one session grown by 75 prompts with 50 KB tool results (the Pi-Bolt `long` workload) |
| sessions per host | sessions running before failure; memory per session; total CPU; p95 turn latency | 1, 10, 100 and 1,000 concurrent RPC sessions under a fixed memory limit |
| memory per added session | MB PSS per added session; total PSS | 1, 10 and 20 concurrent sessions (interactive and RPC), total PSS of every process the arm starts, slope over the session count; the method of [jcode's README](https://github.com/1jehuang/jcode) (PSS for 1 and 10 sessions and "Extra PSS per added session"; headless table measured 2026-09-29). PSS, not RSS, so pages shared between processes of the same binary are not counted twice |
| session storage growth | bytes on disk per 1,000 turns; files created | the 10,000-turn loop of axis D, measured on the arm's state directory |

A scaling result is a curve. Reports draw it and give the slope, so a harness that is fast at 1,000 entries and slow at 46,000 cannot hide behind a mean.

### D. Reliability

| metric | unit | workload |
|---|---|---|
| fault handling | pass/fail per fault, plus the error text the user sees | HTTP 429 and 500, a dropped stream before and after the first byte, a stream that sends only keepalives |
| crash and resume | pass/fail: the resumed session has every committed entry and continues | SIGKILL mid tool call, SIGTERM mid stream, kill during a session-file append; then resume |
| leaks | slope of RSS, threads, file descriptors and child processes per 1,000 turns; judged flat or growing | 10,000-turn RPC loop with compaction |
| soak | the same series over 24 h; "undecided" when the second half is too short to judge | scripted RPC turns with idle gaps |

### E. Extension compatibility

Pi's extension API is the contract. Buffon carries a corpus of Pi extensions: Pi's own examples and a set of public extensions whose licences allow it, each pinned by commit. The corpus manifest records each extension's licence; an extension whose licence forbids redistributing its test traces is not in the published corpus. Each extension has scripted interactions and the observable result Pi gives (events received, tool results, UI calls, session entries). An arm scores the fraction of corpus cases whose observable result equals Pi's, per extension and per API area (tools, events, commands, UI, session, providers). Arms with no Pi extension support get "cannot run", not zero.

Extension cost is reported here too: startup and per-turn CPU with 0, 1, 10 and 20 extensions loaded.

### F. Parity with Pi

For the arms that claim Pi compatibility, Buffon diffs observable behaviour against Pi at the pinned version:

- request bodies sent to the mock, byte for byte and parsed (member order included), per scenario;
- session files written, byte for byte;
- the RPC and JSON-mode event streams, byte for byte;
- tool results for a fixed corpus of read, write, edit, bash, grep, find and ls cases;
- error text for every fault in axis D.

The score is the fraction of cases equal to Pi, per surface. Each difference is published with its diff. A harness that documents a difference as intended (for example a numbered divergence) gets that note beside the row; the row still counts as different. Parity is a description, not a value judgement: a fork that changes behaviour on purpose is not "wrong".

## 5. Reports

A report covers one run: one host class, one lockfile, one seed.

- Per metric: the median and a 95% bootstrap interval for each arm, the ratio to the reference arm with its interval, and the A/A noise floor of the reference on the same host.
- A difference smaller than the noise floor is reported as "no measurable difference", whatever the medians say.
- Every arm's wins and losses are listed. The per-metric tables rank nothing and the results site shows no overall score. `buffon report` also writes the optional Pi Harness Score in its own section and files ([GRADE.md](GRADE.md)); it never replaces the per-metric numbers. If a summary is wanted, it is a count of metrics per arm where the arm is measurably better, equal or worse than the reference, by axis.
- A "cannot run" cell is never counted as a loss, a win or a tie. Each arm has a **coverage** column: the number of cells it could run out of the cells in the report, so readers see how much of the report an arm's summary rests on.
- Results from macOS (rusage meter) and Windows are reported in their own tables, never mixed with Linux cgroup results.
- The run directory holds every raw sample, every request the mock received, the mock's own log, host facts, the lockfile and the exact command lines. It is published with the report, never instead of it.

## 6. Architecture

```
buffon/
  arms/                one manifest per harness (arm.toml) + arms.lock (generated)
  mock/                scripted mock: OpenAI Chat Completions, OpenAI Responses, Anthropic Messages; fault injection; request log
  runner/              install, isolate, meter (cgroup v2), egress audit, PTY and RPC drivers, interleaving
  workloads/           one directory per axis; each workload is data plus a driver
  fixtures/            generators for session files and agent directories (seeded; never real user data)
  stats/               bootstrap, sign-flip, TOST, McNemar, A/A, Holm; seeded
  report/              run directory -> report.md, report.json, figures
  cluster/             Kubernetes runner: one pod per session, Guaranteed QoS, pinned cores, node facts
  results/             published run directories (later, in a separate repository or release assets)
  docs/
```

- **Arm manifest** (`arms/<arm>/arm.toml`): source, version, artifact URLs and checksums per platform, install steps, the config writer that points the arm at the mock, its state directories, the environment that turns off telemetry and updates, the modes it supports, and the renderer mode it runs in for PTY workloads (axis B). `CONTRIBUTING.md` defines the format.
- **One lockfile.** `arms.lock` is generated from the manifests by one command and its hash is in every report. There is exactly one lock, unlike today's two.
- **Runner language.** The runner, mock and stats stay in Python (the existing pigbench code). The session generator and the cluster runner stay in Go. Both run on Linux x64 and arm64; macOS is supported for local runs with the rusage meter, and its results are labelled as such.

## 7. Starting code

Buffon was started from four existing tool sets, consolidated rather than rewritten. The directories named in the first column are those tool sets' own repositories. They are not directories of this repository: the code now lives under `buffon/`, `cluster/` and `fixtures/`.

| existing | becomes | changes needed |
|---|---|---|
| `bench/evals` (pigbench): mock with three APIs, cgroup meter, egress audit, interleaving, statistics, A/A floor, locked arms, config writers | `mock/`, `runner/`, `stats/`, `report/`, axes B and D | drop the PiG-specific defaults (`pig-0.5` built from a checkout becomes an ordinary arm); add Pi on Bun, gi and omp writers; move arm data into manifests |
| `bench/compare`: Pi-Bolt's suite runner, arm adapters for the Pi family, `ctx_scale`, `agent_scale`, `interactive_n`, `ext_profiles`, `tokcost` | workloads for axes A, B, C and E | run on the pigbench meter and stats instead of medians-with-range; add the Anthropic and Responses paths to `tokcost`; merge its arms into the one lock |
| `bench/sessionscale` (Go): session generator in the 46k shape, resume runner, per-prompt CPU, soak | `fixtures/` and the axis C long-session workload | exact per-thread CPU (schedstat) instead of 10 ms ticks; repetitions and stats through the runner |
| `bench/k8s` (Go): one pod per session, Guaranteed QoS, pinned cores, governor refusal, calibration with a CV gate, node facts | `cluster/` | run any Buffon workload, not only the PiG-centred profiles; keep every cluster-specific value out of the repository |

Pi-Bolt's own suite (MIT) stays upstream: Buffon runs it from a pinned commit and never vendors it. The durable-bench method stays out of Buffon (it has no licence and measures a different product).

Two things the existing code does not do and Buffon needs:

1. A parity differ (axis F): a scenario runner that captures request bodies, session files and event streams from two arms and reports byte and parsed differences.
2. A Pi extension corpus runner (axis E) that drives the same extensions through each arm and compares observable results with Pi.

## 8. Optional task-completion track

Buffon may run a small task suite against one pinned open-weights model served locally (vLLM or llama.cpp, weights pinned by revision and sha256). It answers one question: does a harness's overhead or behaviour change the outcome with the same model? Results are reported as paired differences with McNemar and a declared equivalence margin, never as a leaderboard. The track needs GPUs and never uses a hosted model.

Task suites, both run through Harbor and pinned by version:

- **Terminal-Bench 4.0** (`terminal-bench/terminal-bench@4.0.0`, [release v4.0.0](https://github.com/harbor-framework/terminal-bench/releases/tag/v4.0.0), published 2026-08-26): 66 tasks, calibrated task resources and a flat 8 h agent timeout ([announcement](https://www.tbench.ai/news/terminal-bench-4-0)). Terminal-Bench is now a continuous benchmark with semantic versions: a major bump means rerun, a minor bump means regrade, a patch means the earlier trials can be reused. The track records the exact dataset version and follows the same rule when the version moves.
- **SWE-Bench Pro V2** ([leaderboard and protocol](https://labs.scale.com/leaderboard/swe_bench_pro_public_v2), released 2026-09-22): 642 tasks with a locked evaluation protocol. The agent phase reaches only the model endpoint, and every diff is regraded on a pristine image. The track uses the same protocol: the only egress allowed is the local model server.

**Resources: floor and ceiling.** Each task container gets a guaranteed allocation (floor) and a separate, higher kill limit (ceiling), and every report states both. A single pinned value makes the floor equal the kill limit, and transient spikes then kill containers that would otherwise succeed. Anthropic measured a 6 percentage point spread on Terminal-Bench 2.0 between strict and uncapped resources, and recommends calibrating the band so that scores at the floor and at the ceiling fall within noise of each other ([Quantifying infrastructure noise in agentic coding evals](https://www.anthropic.com/engineering/infrastructure-noise), 2026-02-05). Terminal-Bench 4.0 calibrated its task resources with that method. Buffon uses the benchmark's published per-task specs as the floor and states the ceiling multiplier it used.

## 9. Licences and terms

| harness | status | reason |
|---|---|---|
| Pi, PiG, Pi-Bolt, omp, gi, rpi, OpenCode, Codex, Gemini CLI, Qwen Code, Goose, Kimi Code | allowed | MIT or Apache-2.0, no restricting clause found |
| pi_agent_rust | **held** | its licence rider grants no rights to OpenAI, Anthropic or anyone acting "on behalf of" them, and defines use to include "executing, benchmarking, testing" and adding it to an "evaluation harness". A run operated by an AI agent working for either company, or a published image containing the binary, may fall inside that. Include it only after a legal reading, and only in runs operated by people outside the rider. Never redistribute the binary. |
| GitHub Copilot CLI | **operator terms** | GitHub's Competitive Benchmarking clause requires anyone offering a competing product to waive their own benchmark restrictions. Buffon's own licence restricts nothing, but each operator's employer terms matter. The CLI may not be redistributed or modified, so Buffon never ships it: it is installed from the vendor's npm package (pinned by lock file, integrity and per-platform sha256) at run time, in a throwaway root, and never enters a bundle. It runs only when named and accepted: `buffon up --harness copilot --accept-terms copilot` or `BUFFON_ACCEPT_TERMS=copilot`; a saved selection (`--save`) stores the acceptance and raw.json records it. It runs in its bring-your-own-key mode against the mock with a dummy key, so no GitHub account or service is used (`copilot help providers`). |
| Claude Code | **operator terms** | the terms forbid using the service to build a competing product, and the binary must run unmodified (https://code.claude.com/docs/en/legal-and-compliance). Buffon never ships it: it is installed from the vendor's npm package (pinned by lock file, integrity and per-platform sha256) at run time and never enters a bundle. It runs only when named and accepted: `--accept-terms claude-code` or `BUFFON_ACCEPT_TERMS=claude-code`. It talks to the mock on the Anthropic Messages API with a dummy key, so no Anthropic service or account is used. The operator, not Buffon, decides whether their terms allow that. |
| Crush | later, if at all | FSL-1.1-MIT bans commercial "Competing Use"; non-commercial research is allowed. |
| Amp | excluded | its acceptable-use policy allows only humans to create accounts and bans bulk automated activity, and it cannot run without an account. |
| pi-mono-python | excluded | no licence file, so no rights are granted. |

Every report states the licence of each arm and the terms under which it was run.

## 10. Governance

- Maintainers list their affiliations. A maintainer never reviews a change to an arm they maintain.
- Results are drafts until every arm author in the run has had a review window (proposed: 14 days) to report a methodology error. Corrections are published beside the result, never silently.
- A result that favours a maintainer's own harness is marked provisional until an independent operator reproduces it within the noise floor.
- Buffon is started by the author of one of its arms (PiG). Its first public report is released only after a person who neither maintains PiG nor works on it has reproduced every PiG cell, and that report lists PiG's losses first in PiG's section.
- Arm versions are refreshed on a schedule (proposed: monthly, plus each Pi release). An author may ask for an extra run when they release.

## 11. Open decisions for the owner

1. **Name and home.** `buffon` uses Pi's name. Ask Pi's maintainers for a blessing before any publication, or choose a name without "pi". Repository owner: a personal account, a new organisation, or a foundation.
2. **Licence of the starting code.** The existing bench code is MIT with a corporate copyright line. Moving it into an Apache-2.0 repository is permitted (MIT code may be included with its notice kept), but relicensing the files themselves needs the copyright holder's approval. Options: keep the files MIT inside the Apache-2.0 repository with a NOTICE entry, or get approval to relicense.
3. **Neutrality.** Buffon is started by PiG's author. Decide on independent co-maintainers before publication, and whether PiG results wait for independent reproduction.
4. **Held arms and operator terms.** A legal reading for pi_agent_rust, or exclude it. Copilot CLI and Claude Code run once an operator accepts their terms (section 9); decide whether published runs may include them.
5. **Who operates runs.** Runs operated by AI coding agents may matter for the pi_agent_rust rider and for vendor terms. Decide whether published runs are operated by a person.
6. **Hardware.** Which machines produce published numbers: dedicated bare metal, a Kubernetes pool with exclusive cores, or both. Shared build hosts never produce published numbers.
7. **Task-completion track.** In or out of the first release; GPU budget.
