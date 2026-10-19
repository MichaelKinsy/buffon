# The field track

The field track answers one question: does a harness make the same real model better, cheaper or faster on real work? Every other family in Buffon uses a scripted mock model and spends nothing. The field track calls a real model with your own API key, so it is separate from them in every way that matters: it is off by default, it costs money you set a limit on, and its results never enter the default leaderboard or the Harness Score.

State: **planned**. This page is the specification. What exists today is the statistics engine ([AGENT-BENCHMARKS.md](AGENT-BENCHMARKS.md)): a protocol, an expected-runs plan and a paired result from observations. The command, the task set, the budget enforcement and the wire-level measurement below do not exist yet, and each is marked.

## What it is not

- It does not rank models. One model runs for every harness, and a result says nothing about another model.
- It is not part of the Harness Score, the leaderboard or `grade.json`. [GRADE.md](GRADE.md) has no field family, and a test fails if one is added.
- It does not replace the mock families. They measure the harness without model variance. The field track measures the harness with it.
- It does not run unless you ask for it with a model, a key and a budget.

## Running it

```sh
python3 -m buffon field --model <model id> --budget-usd 2
```

The command is planned. It must behave as follows.

1. **Nothing starts without all three of a model, a key and a budget.** A missing one is a refusal with the reason.
2. **The plan comes first.** The command prints the harnesses, the tasks, the repeats, the model and its price, and the **estimated cost** before any request leaves the machine. If the estimate is above the budget, it refuses and prints both numbers.
3. **The budget is a hard cap.** See [Budget](#budget).
4. **The result is labelled FIELD** with the model id and the date, and it is written to its own run directory and report. It is never written into a run of the mock families.

## Your key

The track uses your own API key and nobody else's. Buffon ships no key and has no default key. The rules below are requirements for the planned command.

- The key is read from the environment variable that the harness itself reads for that provider, as the harness's manifest names it. Buffon does not accept a key as a command-line flag, because a flag appears in process listings and shell history.
- The key goes to the harness process through its environment and to nothing else. It is never written to `raw.json`, to a log, to a transcript, to a request log or to the report. The run directory's request log records the request without its authorization header.
- Before the run directory is sealed, Buffon searches it for the key's value and refuses to seal it if the value appears anywhere.
- Each sample runs with a fresh home, as in the other families, so a harness cannot keep the key in a file that the next sample reads. That proof is part of the sample's record.
- The only network destination a field sample may use is the model provider's endpoint. The egress audit, which on every other run fails a sample that touches any non-loopback address, is given that one address as an allowance and fails the sample on any other. [METHODOLOGY.md](METHODOLOGY.md) says that no real credential is ever present on a benchmark host. The field track is the single, explicit exception, and it does not run on a host while a measured run of another family is in progress.
- The key is never present in CI, and a field result is never produced there.

## Budget

- `--budget-usd` is required and is a ceiling, not a target.
- The estimate before the start is tasks x harnesses x repeats x the per-sample ceiling, priced from the model's entry in the price list (below). The per-sample ceiling comes from the turn cap and token limits of the protocol. A harness that sends more than the ceiling is stopped.
- During the run Buffon counts spend from the usage the provider returns, measured at the wire where Buffon can see it, so every harness is costed the same way and not by what the harness reports about itself. When usage is not available for a request, Buffon counts the request's tokens at the price list's rate and marks the sample as estimated.
- Buffon starts no sample whose worst-case cost would take the spend over the cap. When the cap stops a run, the run is written as INCOMPLETE with the samples it has. An incomplete result has no headline: a pair with a missing arm blocks, as in [AGENT-BENCHMARKS.md](AGENT-BENCHMARKS.md).
- The report prints the estimate, the cap, the spend and the number of estimated samples.

## The default model

The default is a rule and not a name: **the cheapest model on the declared list that supports tool calling and that your key can use.**

- The list is a data file with the model id, the provider, the price per million input, cached-input and output tokens, and the date the prices were recorded. A reviewed change edits it. Buffon does not look prices up while it runs.
- The plan prints the model it chose, its price and the price date. Pass `--model <id>` to choose another. Any model on the list is allowed, and a model that is not on the list is refused because it has no price to estimate from.
- The model, its settings and its price date are part of the protocol and of its sha256, so two results are comparable only when they match.

## What every harness gets

The same model and the same settings, declared once in the protocol: the model id, the thinking level, the turn cap, the timeouts and the seed. Everything else is the harness's own: its system prompt, its tools and its defaults. That is what the track compares, a harness's whole behaviour with one model.

The harnesses run in alternating order by task and repeat so that an order effect cancels. A wrong answer is a failed task. A sample that ends in an error, such as a harness that dies or a provider failure, blocks its pair, and any blocked pair withholds the headline ([AGENT-BENCHMARKS.md](AGENT-BENCHMARKS.md)). The report lists the blocked pairs with their errors.

## The task set

A fixed set of 8 to 12 tiny coding tasks. Each task has a fixture tree whose files carry sha256 digests, a prompt, a time limit, a turn cap and a **verifier that does not use a model**: a command whose exit status and output decide pass or fail. The set is versioned and is published with the results.

| kind of task | how it is checked |
|---|---|
| fix a failing test | the test suite passes |
| rename a symbol across files | a search finds no old name and the suite passes |
| add a command-line flag | the program's output with the flag equals the expected text |
| read and summarise, with a checked answer | the answer contains the planted facts and no others |
| a multi-file edit | the files equal the expected tree |
| a task that needs bash | a script's output and the files it leaves equal the expected ones |

The exact list is fixed in the task-set file before any run it judges. A change to a task is a new task-set version, and results from different versions are not compared.

## What it measures

For each harness, with the same model:

| metric | meaning |
|---|---|
| task success rate | passed tasks over all tasks and repeats, with a Wilson interval |
| turns to finish | the number of model requests of a finished task |
| tokens and cost | input, output and cached-input tokens, and dollars, from the provider's usage |
| prompt-cache hit rate | cached-input tokens over input tokens |
| request bytes | bytes sent to the provider |
| harness overhead, wall and CPU | time spent outside the network wait: wall time and CPU time of the harness, with the time it waited on the provider taken out |
| tool errors | tool calls that failed |

A metric the harness or provider cannot give is null and is counted as unavailable. It is never zero. The paired difference between two harnesses uses the exact McNemar test on tasks that passed in one and failed in the other ([AGENT-BENCHMARKS.md](AGENT-BENCHMARKS.md)).

## Limits

- **Few tasks give wide intervals.** With 8 to 12 tasks and a few repeats, a difference in success rate of one task is inside the interval. The report prints the interval and the McNemar p-value so that a small difference reads as noise.
- **A model is not deterministic.** The same prompt can give another answer on another run, even with settings that reduce it, and a provider can change a model behind the same id. A result applies to that model on that date.
- **The prompt cache depends on timing.** The hit rate depends on how soon requests follow each other and on the provider's cache rules, so it varies between runs.
- **Rate limits and outages are outside Buffon's control.** A sample that fails because of the provider is recorded with that error and is not counted as a failed task. It blocks its pair, so a run with such a sample has no headline until the pair is run again.
- **Prices change.** Cost is computed from the price list at its date, and the report prints the date.
- **Tiny tasks are not your project.** They are deterministic to check, and they are small enough to pay for. A harness that does well on them can still do badly on your work.

## What exists and what is planned

| part | state |
|---|---|
| protocol, expected-runs plan, paired result with Wilson and McNemar, nullable telemetry | exists (`buffon agentbench`) |
| the `buffon field` command, with the refusals above | planned |
| key handling: environment only, a scan before sealing | planned |
| the budget estimate, the hard cap and INCOMPLETE results | planned |
| the cost counted at the wire | planned |
| the price list and the default-model rule | planned |
| the fixed task set and its verifiers | planned |
| the FIELD label and the separate report | planned |
