# Pi Faithfulness Score

How closely a harness behaves like Pi, as a number you can reproduce. Pi at the pinned release (Node) is the reference and scores 100 by definition. Every other harness, PiG included, scores below it by how its probes differ: faithfulness is graded, never pass/fail.

```bash
python3 -m buffon faithfulness run --arms pi-bun pibolt pig-0.4.1 --out faith/ --pi-source <a Pi source checkout>   # optional source tree: probes then cite Pi's own line numbers
python3 -m buffon faithfulness report faith/                                                                    # faithfulness.md (several run directories give a ladder across Pi releases)
python3 -m buffon faithfulness probes pi-help.txt --pi-source <dir>                                               # list the probes generated from a `pi --help` text
```

## Method

- **Graded, never binary** (probe set v0.2). A probe's class is decided by a deterministic comparator for its family (`buffon/faithfulness/grading.py`), never by hand:

  | class | credit | meaning |
  |---|---:|---|
  | identical | 1.0 | the normalised observations are equal |
  | equivalent-presentation | 0.9 | a human-facing surface (help wording, layout) differs but the same information is shown and the same actions are possible: F1 flag effect with the same exit, hang, request change and files but other words; usage text naming the same options |
  | equivalent-semantics | 0.6 | a machine-facing surface differs in form but carries the same meaning: key order, extra keys in a JSON event or session record, extra events between the reference's events in a JSON or RPC event sequence (the reference's events in the same order), the form of a tool result or print output (line endings, trailing spaces, trailing blank lines; never indentation, line breaks or inner spacing), tool-definition order and description prose, where a context marker lands in the prompt |
  | behaviour-differs | 0.0 | a different result: other tool parameters, other files left, a missing option, a lost key, other roles, another request |

  A probe with no comparator is identical or behaviour-differs. A dimension's percentage is the mean credit of its scored probes. Machine-facing dimensions (F2 wire, F4 session, F6 output modes, F7 extensions) weigh more than human-facing ones (F1 CLI text, F8 TUI) because scripts, extensions and resumed sessions break on them. A harness's recorded intentional divergences are listed by name beside the rows they explain; they never change a class.
- **Only correctness failures gate a performance family.** A tool probe (F3) whose files differ or whose result differs beyond its form, a crash, a hang, or data loss (a harness that claims Pi sessions writes no session file; F4 counts it as behaviour-differs, never as n/a) is a correctness failure (`correctness_failures` in `faithfulness.json`). It scores the tool-using families (core, ext10, long-session) as 0 in the grade (docs/GRADE.md). A presentation or semantics difference never gates; it is a deduction here. Below the faithfulness floor an entry is ranked in its own table.
- **Deterministic, black-box, no model.** A probe is a scripted situation. Buffon runs it on the reference and on the harness against its own mock model endpoint (scripted replies, fixed fixture tree, fresh HOME and project directory per probe), reduces what each did to a JSON observation, normalises it, and grades the harness by how the two observations differ. There is no threshold, no fuzzy matching and no AI scoring.
- **Normalisation** (`buffon/faithfulness/canon.py`): the harness's program name (`pi`, `pig`, `rpi`, written in the manifest as `[faithfulness] names`) becomes `<bin>`, as does its config directory (`.pi`, `.pig`, `[faithfulness] project_dir` names the project-local one); the run's temporary paths, the mock's port, call/message ids, UUIDs, dates and the harness version are masked. Nothing else is masked, so a difference in prompt wording, tool schema or field order is a mismatch.
- **Determinism check.** A second copy of Pi (`pi-node-b`, its own install root) runs every probe too. A probe where the two copies disagree is unstable and is left out of everybody's score and listed.
- **Not applicable is not zero.** A probe a harness cannot take part in because it does not speak the wire API (F2 per API) or has no Pi extension support (F7) is N/A and left out; the weights of the remaining dimensions are renormalised. A harness that lacks a mode, crashes or times out on an applicable probe has a mismatch.
- **Invalid probes.** If the reference's own observation shows that the probe could not exercise anything (Pi's grep and find need `rg` and `fd`, which the egress rule keeps Buffon from downloading), the probe is invalid, listed and never scored.
- **Intentional divergences.** `buffon/faithfulness/intentional.toml` maps probe patterns to a harness's recorded divergence (PiG's `D<N>` records). Those rows are listed by name in the report and **still count against the score** at their class: a harness gets no credit for its own fixes.

## Dimensions (probe set v0)

| | dimension | weight | what is probed |
|---|---|---:|---|
| F1 | CLI surface | 5 | every flag in `pi --help` is listed in the harness's help, and is accepted with the same exit code, output and request; every command (`pi install --help`, …) exits and prints the same usage. Generated from the reference's help, so it grows with Pi. |
| F2 | Wire fidelity | 25 | for a text script and a tool-call script on each wire API (Chat Completions, Responses, Messages): the request's key set, key order, short values, system prompt, tool definitions and message sequence, each its own probe. |
| F3 | Tool behaviour | 15 | read (whole, range, missing), write, edit (match, no match), bash (ok, failing), grep, find, ls on a fixed tree: the result text the model receives and the files left behind. Tool arguments follow the schema the harness advertises. |
| F4 | Session format | 15 | the session file a harness writes (header, record types, record shapes); a Pi-written session resumed by the harness; a harness-written session resumed by Pi (the history each sends). |
| F5 | Config compatibility | 10 | AGENTS.md and CLAUDE.md (project and agent directory), `--no-context-files`, skills and prompt templates (agent directory, and project directory under `--approve`), `--system-prompt` / `--append-system-prompt`, the credential in `models.json`. |
| F6 | Output modes | 20 | print mode stdout and exit code (text, after a tool call), `--mode json` event type sequence and key sets, `--mode rpc` responses and event sequence. |
| F7 | Extension compatibility | 10 | small extensions using Pi's API: a registered tool (schema, execution, result), a `tool_call` handler that blocks, a `before_agent_start` system-prompt hook, a slash command. N/A for harnesses that load no Pi extensions. |
| F8 | TUI | 0 | not implemented in v0 (listed so the gap is visible): the same keystroke script on a PTY, screen grid compared after each key. |

The overall score is the weighted mean of the dimensions that apply to the harness. Each probe cites the Pi source it comes from (`path:line` when `--pi-source` is given, otherwise the file, or `pi --help`).

## Per Pi release

Run the command with the reference pinned to a Pi release (`arms/pi-node/arm.toml`). The report of several run directories shows a ladder, oldest release first. Regenerate the probe set from the new release's `--help`; new flags become probes, removed flags drop out, and the probe set version (`PROBE_SET_VERSION`) changes when probes are added by hand.

## Limits of v0

- One wire API per F3/F4/F5/F6/F7 probe (Chat Completions); F2 covers all three.
- Free-text prompt wording is judged once (F2 `system` probes); other probes reduce a prompt to the facts they test (is the marker present, which line precedes it).
- No compaction, fork or tree probes in F4 yet; no theme or MCP probes in F5/F1.
- Probes do not time anything, so the host does not matter. The results-integrity rules of Buffon still hold for identity: arm versions, executable and install-tree digests and the runner's commit are in the output.


## Methods borrowed, and what is still open

The score is a differential, black-box comparison with the pinned Pi release (the reference arm). Public work on other ports shaped it; the sources are cited, nothing was copied:

- **Request-body differential** (sky-valley/pi's difftest): the F2 probes compare the request body field by field, key order and scalars separately. Done.
- **Byte-identical tool output before timing** (Pi-Bolt): the F3 probes compare tool results byte for byte. Running them as a gate before a timed run (an arm that differs is flagged in the performance report) is open.
- **Per-test-case mapping** (nowa/gi's parity ledgers): a ledger from each Pi test case to the probe that covers it. Open; today the probes are written from Pi's behaviour, not mapped to its test files.
- **Reference-suite pass rate with reasoned exclusions** (uutils): run Pi's own test suite against an arm where the suite is language-independent. Open; Pi's tests are TypeScript unit tests that import Pi's modules, so only the black-box parts apply.
