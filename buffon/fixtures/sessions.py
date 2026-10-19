# SPDX-License-Identifier: MIT
# Adapted from pigbench's longhistory.py (bench/evals of the PiG repository): the session-file writer, by turns instead of by token budget.
"""Synthetic Pi session files: deterministic from a seed, in Pi's JSONL session format (header, then message entries linked by parentId).

A turn is a user question, a `read` tool call, a 2.5-5.5 KB tool result and a text answer (four entries). The file's header holds the working directory,
which is rewritten when the file is copied for a sample (`copy_with_cwd`), so the same generated history serves every arm's own project directory.

Two variants share one shape. The repeating session draws every word from a 70-word vocabulary and every code block from five template lines, so it compresses far better than
a real transcript and a harness that deduplicates or compresses repeated content gains from it. The varied twin (`generate_varied`) is made from the repeating session: the
same entries, ids, tool calls, usage and timestamps, and every run of letters and digits in a text replaced by a seeded pseudo-word of the same length, so no two turns share a
sentence and the file has the same byte size. A report puts the two rows side by side, and a gain that is only in the repeating row is a deduplication gain.
"""
import hashlib
import json
import os
import random
import re
import shutil
import time

from ..mock import MODEL

SESSION_VERSION = 3
REPEATING, VARIED = "repeating", "varied"
BYTES_PER_TOKEN = 4
VOCAB = ("session transcript entry render buffer stream token provider model harness compaction summary cursor viewport latency frame "
         "diff terminal width height scrollback markdown component cache append parse index branch leaf message tool result "
         "file read write edit search query reply request response header delta chunk window context budget reserve").split()
CODE = ["func {n}(ctx context.Context, in {t}) ({t}, error) {{", "\tif in == nil {{ return nil, errors.New(\"{n}: nil input\") }}",
        "\tfor i := range in.Items {{ total += in.Items[i].Size * {k} }}", "\treturn in, nil", "}}"]


def text_block(rng, chars):
    """Deterministic prose and code of about `chars` characters."""
    out, n = [], 0
    while n < chars:
        if rng.random() < 0.35:
            name = rng.choice(VOCAB) + str(rng.randrange(1000))
            block = "```go\n" + "\n".join(line.format(n=name, t=rng.choice(VOCAB).title(), k=rng.randrange(9)) for line in CODE) + "\n```\n"
        else:
            block = " ".join(rng.choice(VOCAB) for _ in range(rng.randrange(20, 60))).capitalize() + ".\n\n"
        out.append(block)
        n += len(block)
    return "".join(out)[:chars]


class Writer:
    def __init__(self, path, seed):
        self.f = open(path, "w", newline="\n")  # JSONL as Pi writes it on every host, so a seed gives the same bytes on Windows
        self.rng = random.Random(seed)
        self.parent = None
        self.n = 0
        self.tokens = 0  # context tokens so far (since the last compaction, summary included)
        self.entries = []  # (id, role, tokens) of message entries since the last compaction
        self.clock = 1_790_000_000_000
        self.total_tokens = 0

    def _id(self):
        self.n += 1
        return f"{self.n:08x}"

    def _emit(self, entry):
        self.f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def header(self, cwd):
        self._emit({"type": "session", "version": SESSION_VERSION, "id": f"bench-{self.rng.randrange(10**9):09d}", "timestamp": "2026-10-01T00:00:00.000Z", "cwd": cwd})

    def message(self, message, tokens):
        eid = self._id()
        self.clock += 1500
        message["timestamp"] = self.clock
        self._emit({"type": "message", "id": eid, "parentId": self.parent, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(self.clock / 1000)), "message": message})
        self.parent = eid
        self.tokens += tokens
        self.total_tokens += tokens
        self.entries.append((eid, message["role"], tokens))
        return eid

    def usage(self):
        return {"input": self.tokens, "output": 300, "cacheRead": 0, "cacheWrite": 0, "totalTokens": self.tokens + 300,
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0}}

    def turn(self):
        """One user turn: a question, a read tool call and its result, and a text answer."""
        rng = self.rng
        question = text_block(rng, rng.randrange(120, 400))
        self.message({"role": "user", "content": [{"type": "text", "text": question}]}, len(question) // BYTES_PER_TOKEN)
        call_id = f"call_{self.n:08x}"
        path = f"src/{rng.choice(VOCAB)}/{rng.choice(VOCAB)}{rng.randrange(100)}.go"
        self.message({"role": "assistant", "content": [{"type": "toolCall", "id": call_id, "name": "read", "arguments": {"path": path}}], "api": "openai-completions",
                      "provider": "bench", "model": MODEL, "usage": self.usage(), "stopReason": "toolUse"}, 40)
        body = text_block(rng, rng.randrange(2500, 5500))
        self.message({"role": "toolResult", "toolCallId": call_id, "toolName": "read", "content": [{"type": "text", "text": body}], "isError": False}, len(body) // BYTES_PER_TOKEN)
        answer = text_block(rng, rng.randrange(600, 1600))
        self.message({"role": "assistant", "content": [{"type": "text", "text": answer}], "api": "openai-completions", "provider": "bench", "model": MODEL,
                      "usage": self.usage(), "stopReason": "stop"}, len(answer) // BYTES_PER_TOKEN)

    def close(self):
        self.f.close()


CWD_PLACEHOLDER = "{cwd}"


def generate_turns(path, turns, seed):
    """Write a session file of `turns` turns and return its facts. The header's cwd is a placeholder."""
    w = Writer(path, seed)
    w.header(CWD_PLACEHOLDER)
    for _ in range(turns):
        w.turn()
    w.close()
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return {"turns": turns, "seed": seed, "bytes": os.path.getsize(path), "entries": w.n, "messages": 4 * turns, "context_tokens": w.tokens, "sha256": digest, "variant": REPEATING}


CONSONANTS, VOWELS = "bcdfghjklmnprstvwz", "aeiou"
RUN = re.compile(r"[A-Za-z0-9]+")


def pseudo_word(rng, run):
    """A word of the same length and character classes as `run`: digits stay digits, an upper-case letter stays upper case, letters alternate consonant and vowel."""
    out, vowel = [], rng.random() < 0.3
    for c in run:
        if c.isdigit():
            out.append(str(rng.randrange(10)))
            continue
        letter = rng.choice(VOWELS if vowel else CONSONANTS)
        out.append(letter.upper() if c.isupper() else letter)
        vowel = not vowel
    return "".join(out)


def vary_text(rng, text):
    """`text` with every run of letters and digits replaced by a pseudo-word of the same length: the same layout, the same escaped size, other words."""
    return RUN.sub(lambda m: pseudo_word(rng, m.group()), text)


def variation_seed(seed):
    """The seed of the varied twin's words, derived from the session seed so that one number names both sessions. The string keeps the project's old name: changing it would change every varied session of every published seed."""
    return int.from_bytes(hashlib.sha256(f"pi-arena varied session {seed}".encode()).digest()[:8], "big")


def generate_varied(path, source, base_facts):
    """Write the varied twin of the session file `source` (made by `generate_turns`, described by `base_facts`) and return its facts. Only the text of user questions, tool results and
    answers changes; ids, links, tool calls, usage, timestamps and every length stay, so message count, tool-call structure and byte size are those of the source."""
    rng = random.Random(variation_seed(base_facts["seed"]))
    with open(source, newline="\n") as fin, open(path, "w", newline="\n") as fout:
        fout.write(fin.readline())
        for line in fin:
            entry = json.loads(line)
            for block in entry["message"]["content"]:
                if block["type"] == "text":
                    block["text"] = vary_text(rng, block["text"])
            fout.write(json.dumps(entry, separators=(",", ":")) + "\n")
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return dict(base_facts, bytes=os.path.getsize(path), sha256=digest, variant=VARIED, variation_seed=variation_seed(base_facts["seed"]), source_sha256=base_facts["sha256"])


def cached(cache_dir, turns, seed, variant=REPEATING):
    """Generate (or reuse) the session file for `turns` turns; returns (path, facts). The facts file records the digest the report prints. `variant` is `repeating` or `varied` (the twin)."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"session-{turns}t-seed{seed}" + ("-varied" if variant == VARIED else "") + ".jsonl")
    facts_path = path + ".json"
    if os.path.exists(path) and os.path.exists(facts_path):
        with open(facts_path) as f:
            facts = json.load(f)
        with open(path, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == facts["sha256"]:
                return path, dict(facts, variant=variant)   # a facts file written before the variants existed has none
    if variant == VARIED:
        source, base_facts = cached(cache_dir, turns, seed)
        facts = generate_varied(path, source, base_facts)
    elif variant == REPEATING:
        facts = generate_turns(path, turns, seed)
    else:
        raise ValueError(f"unknown session variant {variant!r}")
    with open(facts_path, "w") as f:
        json.dump(facts, f)
    return path, facts


def copy_with_cwd(src, dst, cwd):
    """Copy a generated session file, replacing the header's cwd placeholder."""
    with open(src, newline="\n") as fin, open(dst, "w", newline="\n") as fout:
        header = json.loads(fin.readline())
        header["cwd"] = cwd
        fout.write(json.dumps(header, separators=(",", ":")) + "\n")
        shutil.copyfileobj(fin, fout)
