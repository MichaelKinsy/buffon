# SPDX-License-Identifier: Apache-2.0
"""The declared protocol of an agent-benchmark run and the runs it expects."""
import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class Protocol:
    benchmark: str                      # for example "terminal-bench@2.0": the task set and its version
    arms: list                          # arm ids; the first is the reference
    cases: list                         # task ids: every arm runs exactly these
    models: list                        # model ids: every arm runs every model
    runs: int = 1                       # repetitions of each (case, arm, model)
    seed: int = 0                       # order seed
    params: dict = field(default_factory=dict)   # thinking level, max turns, timeouts: identical across arms

    def validate(self):
        if len(self.arms) < 2 or len(set(self.arms)) != len(self.arms):
            raise ValueError("a paired benchmark needs at least two distinct arms")
        for name in ("cases", "models"):
            values = getattr(self, name)
            if not values or len(set(values)) != len(values):
                raise ValueError(f"{name} must be non-empty and free of duplicates")
        if self.runs < 1:
            raise ValueError("runs must be at least 1")
        return self

    def document(self):
        return {"benchmark": self.benchmark, "arms": self.arms, "cases": sorted(self.cases), "models": sorted(self.models), "runs": self.runs, "seed": self.seed, "params": self.params}

    def digest(self):
        """sha256 of the canonical protocol document: two result sets are comparable only when their digests are equal."""
        return hashlib.sha256(json.dumps(self.document(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def expected_runs(protocol):
    """Every (case, model, run) with the arm order for it. The arm order alternates run by run (and by case) so a systematic order effect cancels."""
    protocol.validate()
    out = []
    for ci, case in enumerate(sorted(protocol.cases)):
        for model in sorted(protocol.models):
            for run in range(protocol.runs):
                k = (ci + run + protocol.seed) % len(protocol.arms)
                order = protocol.arms[k:] + protocol.arms[:k]
                out.append({"case": case, "model": model, "run": run, "order": order})
    return out


def load(path):
    with open(path) as f:
        doc = json.load(f)
    return Protocol(benchmark=doc["benchmark"], arms=doc["arms"], cases=doc["cases"], models=doc["models"], runs=doc.get("runs", 1), seed=doc.get("seed", 0), params=doc.get("params", {})).validate()
