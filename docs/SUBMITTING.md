# Submitting and reproducing results

A result enters the public index only after the same recomputation CI runs on every pull request. This page is the path from a run to a row in `results/INDEX.md`, and the path from that row to someone else's reproduction.

## 1. Run, report, verify

Start from a clean checkout. The run records the runner's commit, and `buffon verify` rejects a run whose checkout had uncommitted changes (`git status` must show nothing before `buffon run` starts; commit or stash first).

```sh
python3 -m buffon run overhead --site mine --out runs/2026-10-12-mine     # a session seals its run directory: MANIFEST.sha256
python3 -m buffon report runs/2026-10-12-mine                              # report.md, report.html, report.json, rounds.csv, noise.csv, telemetry.csv, health.json, plots/
```

Write `submission.toml` in the run directory (the example is below the check tables), then verify. `--submission` rejects a run with no `submission.toml`.

```sh
python3 -m buffon verify runs/2026-10-12-mine --submission                 # what CI will do
```

`buffon verify` recomputes every check from the sealed files and the repository; nothing the submitter wrote next to the run is believed, only compared with the recomputation.

| check | what it rejects |
|---|---|
| `seal` | a file changed, removed or added after the run (`MANIFEST.sha256`) |
| `rules-isolation`, `rules-raw`, `rules-host-disclosure`, `rules-host-class`, `rules-provenance` | Run Rules v1 (METHODOLOGY section 11): the isolation stamp, a complete `host.json` platform specification, the host class and preflight result, the arms.lock digest, a clean runner checkout and the recorded host lock |
| `raw`, `facts` | a raw.json that does not validate, a missing facts.json |
| `run`, `egress` | a refused run, an executable that changed during the run, a run with no egress audit |
| `flags` | a run made without telemetry (`--no-telemetry`) or without every A/A copy (`--aa` other than `all`): these switch off what makes numbers comparable at all |
| `lock`, `arms`, `runner` | pins that are not the lock at the runner's commit: arm version, manifest, artifact sha256, source commit and tree; a runner checkout with uncommitted changes |
| `telemetry` | a measured sample without telemetry |
| `health.json`, `report.json` | a report that differs from the recomputation: edited, or made with other usual ranges |
| `submission` | a missing or invalid `submission.toml` |

Run notes are listed as warnings and never reject a run:

| check | what it lists |
|---|---|
| `health` and one line per note | every run-health check outside its usual range (docs/HEALTH.md) |
| `rounds` | fewer than 12 measured rounds |
| `gates` | a noise gate switched off or loosened on the command line (`--allow-noisy`, `--allow-short`, `--no-calibrate`, `--no-quiet-gate`, `--allow-frequency-scaling`) |
| `quiet_gate` | a quiet-host gate that was off, looser than the default, or gave up on a sample |
| `hardware` | anything but quiet dedicated hardware by the runner's own detection |

`submission.toml` (written by you, after the run, not sealed):

```toml
operator = "A. Person"
hardware = "bare metal, 16 cores dedicated to benchmarks; nothing else runs on it; shell access: me only"
independent = true          # I neither maintain nor work on any arm in this run
organisation = ""           # optional
reproduces = ""             # optional: the results id this run reproduces
notes = ""                  # optional
```

## 2. The pull request

Copy the whole run directory to `results/<id>/` (the id is the directory name: date, then a short site name), check it there, regenerate the index and commit both. Do not run `buffon promote`: CI does that after the merge, and a pull request that carries a `promotion.json` fails.

```sh
cp -r runs/2026-10-12-mine results/2026-10-12-mine
python3 -m buffon verify results/2026-10-12-mine --submission    # the same check CI runs on your copy
python3 -m buffon index results                                  # rewrites results/index.json and INDEX.md; CI fails when they differ from the committed ones
git add results && git commit -s -m "results: 2026-10-12-mine"
```

Push the branch and open the pull request with the results template. The repository keeps its templates in a folder, so GitHub shows this one only when the URL names it: `https://github.com/<owner>/<repo>/compare/main...<branch>?expand=1&template=results.md`. The pull request changes `results/<id>/`, `results/index.json` and `results/INDEX.md` and nothing else. A pull request is the only way a result enters the index: nothing is uploaded, and no code from a submission runs. CI (`.github/workflows/results.yml`) checks the change with the base branch's code. It runs on `pull_request_target`, so the workflow file is the base branch's too. It checks out the pull request into `pr/` as data, with no credentials, and runs every `buffon` command from the base branch checkout. Then it:

1. fails if any file outside `results/` changed, or anything but a new file inside a new run directory (`buffon index results --immutable-against <base>`); a change to code, workflows or arms goes in its own pull request and gets a code review;
2. runs `buffon verify --submission` on every added directory;
3. fails if the committed `index.json` and `INDEX.md` differ from the regenerated ones (`buffon index results --check`).

A maintainer reviews and merges; CODEOWNERS names a maintainer for every file, so no pull request merges without one. The merge job runs `buffon promote results/<id>` to write `promotion.json` (the manifest digest CI verified, the number of run notes it recomputed, the CI run), `buffon index results` to regenerate the index, and attests the sealed manifests (GitHub artifact attestations: the workflow, the commit and the manifest digest). A run directory is never modified afterwards. A pull request that carries a `promotion.json` fails the immutability check: only CI promotes a run.

## 3. Trust tiers

| tier | meaning |
|---|---|
| self-reported | the operator's own run; the index lists it, it is never a headline |
| ci-revalidated | `promotion.json` names the directory's manifest digest: CI recomputed everything above from the raw data. It stops counting if the directory changes |
| maintainer-reproduced | a ci-revalidated run by an operator listed in `results/MAINTAINERS.toml` states `reproduces = "<id>"` and its `reproduction.json` shows every comparison reproduced |

In ACM's vocabulary: *reproduced* means obtained without the original's artifacts (a fresh run on another host from the same pins); a run that reuses the original's run directory is at most replicated.

## 4. What the run notes do to a result

Nothing. Run notes describe the conditions of a run (docs/HEALTH.md). They are never a reason to reject a run, and no row is removed for them. `buffon verify --submission` lists them. The index has a `run notes` column with the number of notes, and its last column names the checks that have a note. Only integrity decides whether a run is accepted: the seal, raw.json, the pins and provenance, the executables, `submission.toml`, and a run made without telemetry or without its A/A copies.

A row is a site headline when it is ci-revalidated, on quiet dedicated hardware, and not withdrawn. The reader judges the notes.

Every accepted run stays listed. A run found wrong is added to `results/WITHDRAWN.toml` (`[[withdrawn]]` with `id` and `reason`); the row stays, marked withdrawn, and is never a headline. A methodology error is corrected in a new report that links the old one (METHODOLOGY section 10).

### Workflows and governance files

- `.github/workflows/results.yml` re-validates a pull request that adds run directories (the immutability rule over the whole tree, `buffon verify --submission`, the index check), with the base branch's code only.
- `.github/workflows/results-merge.yml` runs after the merge: `buffon promote` writes `promotion.json` into each run directory that has none (the ci-revalidated tier), `buffon index results` regenerates the index, and the job attests the sealed manifests. The bot commit only adds files.
- A change to `results/MAINTAINERS.toml` or `results/WITHDRAWN.toml` carries no run directory. Only the `governance` job of `results.yml` passes `buffon index --allow-governance`, and it runs in the `results-maintainers` environment, which the repository settings must protect with required reviewers. `.github/CODEOWNERS` names a maintainer for every file, the governance files and the workflows included. Without `--allow-governance` the immutability check rejects any change to those files.
- Mark only the `result` job of `results.yml` as the required status check, and require code-owner review in branch protection. GitHub counts a skipped required job as passed, so `revalidate` or `governance` alone would let the other path merge; `result` passes only when the job the change needs passed. Without code-owner review CODEOWNERS is advisory.
- Repository settings: under Actions, "Require approval for all external contributors", so a first-time contributor's workflow run waits for a maintainer; branch protection on `main` with "Require a pull request", "Require review from Code Owners" and the `result` check.

## 5. Reproducing a published run

```sh
git checkout <runner commit of the run>           # the pins must be the run's: buffon reproduce refuses otherwise
python3 -m buffon reproduce results/<id> --site mine --out runs/repro
```

`buffon reproduce` repeats the original's plan (arms, workloads, APIs, rounds, warm-up, A/A copies, reference, seed, parameters) on your site profile, then writes `reproduction.md` and `reproduction.json` into your run directory. `buffon compare <original> <yours>` makes the same comparison for two existing directories.

- A comparison is **consistent** when the two 95% intervals of the ratio overlap or the ratios differ by less than the larger of the two A/A floors; it **reproduces** when it is consistent and both runs reach the same verdict.
- The telemetry section says whether your host was **noisier**, **quieter** or **similar** (by the median A/A floor: more than 1.5 times the other's and at least 0.5 percentage points apart), with the calibration CV, flagged samples, throttling, steal, foreign CPU, clock and the number of run notes of both runs side by side. A difference that is smaller than the noisier host's floor is not a failure to reproduce.
- Pin and plan differences are listed first; with them the two runs are not the same experiment.
