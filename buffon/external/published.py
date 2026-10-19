# SPDX-License-Identifier: Apache-2.0
"""Published results with a family: the import writes the provenance and refuses any file set whose numbers differ from what the source published.

A family names one source (repository, commit, licence, versions measured) and the table the source prints. `import_family` refuses any file
whose sha256 is not the one pinned for the family, copies the files unchanged (results.import_files), then checks the CPU medians
of the file set against the published table. A mismatch removes the
import directory and refuses it, so no table a buffon reader could load contradicts its source.
"""
import os
import shutil

from . import guard, results

PI_BOLT_SOURCE = "https://github.com/opensec-git/Pi-Bolt/tree/13ccac32afb94366fb8d3e15aff1dd7bb234fefa/bench/results/2026-10-11-linux-x64-0.8.0"

FAMILIES = {
    "pi-bolt-published-headless": {
        "meta": {"id": "pi-bolt-2026-10-11-linux-x64-0.8.0", "title": "Pi-Bolt 0.8.0 benchmark, Linux x64 (Pi-Bolt, Pi-Bolt's PiG 0.4.1 build, omp, Pi on Bun, Pi on Node)",
                 "source_url": PI_BOLT_SOURCE, "repo": "https://github.com/opensec-git/Pi-Bolt", "commit": "13ccac32afb94366fb8d3e15aff1dd7bb234fefa",
                 "version": "pi-bolt 1.1.0 (Pi-Bolt 0.8.0, linux-x64, JIT off); pig 0.4.1+1.0.3; omp 18.8.7; bun: Pi 1.1.0 on Bun 1.4.2; node: Pi on Node v24.21.0",
                 "host": "AMD EPYC 7B13, Linux 7.0.0-1013-gcp x86_64, cpus 40-43 of a shared VM", "licence": "MIT (the repository's LICENSE, Copyright (c) 2025 Mario Zechner)",
                 "published": "2026-10-11"},
        # The README table's headless CPU medians (ms), each the median of 21 runs (R8 D1).
        "expect": {("benchmark.jsonl", "headless"): {"pi-bolt": 80, "pig": 261, "omp": 1752, "bun": 323, "node": 618}},
        "runs": 21,
        "tolerance_ms": 0.5,   # the table prints whole ms: a median more than half a ms away rounds to another number
        # sha256 of the published files at PI_BOLT_SOURCE (bench/results/2026-10-11-linux-x64-0.8.0/). An import takes only these names.
        "files": {
            "benchmark.jsonl": "5e9431e2eb8aa3f2296b66f886fda71210e9e0bba6dde16ce3c08011f2c8fbff",
            "environment.txt": "0217b63952031268819034022a44d687c0d2d799aa0bd5313a61f136e30aebe2",
            "large_write-1.txt": "382ed612d8528e8b97721e1b92413b9a8a805478723f1980a600eb7dd710cf87",
            "large_write-2.txt": "993ea9478c6b8007f394bd86e1ebaad980d9fdd2b03fd79a04e7197be8212ed3",
            "long_answer-1.txt": "7d8d9ea4e5ffe361a5932b87057bc2ec34bec5827b2ec00a22c3f1f69aaa3a19",
            "long_answer-2.txt": "081270b1658e5dedbd48080e5c0c6ac1bdffa90e2ff018d3fe30fea83fc3b56c",
            "long.jsonl": "39d1be3bd5b5df14d75b092ffac7489c1be2fc61fe772c39608c93dd5df04624",
            "tmux.jsonl": "2ee87fd5d688519b1db56124b396a4844cfa4e265c2fe9ade8c8a8d0cb48aef1",
        },
    },
}


def check_table(directory, doc, family):
    """Return the mismatches between the published table and the imported rows (empty when they agree)."""
    summary = results.summarise(directory, doc)
    problems = []
    for (name, scenario), builds in family["expect"].items():
        for build, published in builds.items():
            entry = summary.get((name, build, scenario))
            if entry is None:
                problems.append(f"{name}: no {scenario} rows for {build}")
                continue
            if entry["n"] != family["runs"]:
                problems.append(f"{build} {scenario}: {entry['n']} runs, the table has {family['runs']}")
            median = entry["cpu_ms"]["median"]
            if abs(median - published) > family["tolerance_ms"]:
                problems.append(f"{build} {scenario}: cpu_ms median {median} is not the published {published}")
    return problems


def import_family(family_id, files, out):
    """Import `files` for the family into `out`; refuse and remove `out` when the numbers differ from the published table."""
    if family_id not in FAMILIES:
        raise ValueError(f"unknown published family {family_id!r}; known: {', '.join(sorted(FAMILIES))}")
    family = FAMILIES[family_id]
    for path in files:
        name = os.path.basename(path)
        if name not in family["files"]:
            raise ValueError(f"{name} is not a published file of {family_id}")
        actual = guard.sha256_file(path)
        if actual != family["files"][name]:
            raise ValueError(f"{name} is not the file at the pin: sha256 {actual[:12]}, pinned {family['files'][name][:12]}")
    doc = results.import_files(files, out, dict(family["meta"]))
    problems = check_table(out, doc, family)
    if problems:
        shutil.rmtree(out, ignore_errors=True)
        raise ValueError("published table does not match the imported rows: " + "; ".join(problems))
    return doc
