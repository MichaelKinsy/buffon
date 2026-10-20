# SPDX-License-Identifier: Apache-2.0
"""The durable family's script generator: a seeded, versioned writer of the conversation script the scripted model plays (docs/DURABLE-ADAPTERS.md, section 4.1;
design/DURABLE.md, sections 3.3 and 3.5).

A script is one JSON document: a tool definition, a summary text, a list of 88-byte document strings and a set of turns. A turn is the user text, the model's rounds (text and
tool calls with ids and results) and how the answer streams. An adapter looks a turn up by its number `n`.

Determinism. The content of turn `n` depends only on (GENERATOR, seed, n, shape, shape parameters): each turn draws from its own `random.Random`, seeded from a sha256 of
those inputs (never Python's `hash`, which is salted per process). So any subset of turns can be generated alone, a fixture's history turns and the measured turns that come
after agree whatever plan produced them, and a turn is the same inside a 3500-turn script as in a one-turn script. The mixed shape draws the concrete shape of turn `n` from
its own `Random` keyed the same way; the concrete shape is recorded in the turn's `shape` field, and the turn equals the one built by asking for that shape directly.

Variants. `repeating` is the base script: prose-like text drawn from a word list of about 240 words in sentences of 6 to 16 words (not `x` repeats: it does not compress to
nothing, though it compresses better than a real transcript, which is why the twin exists). `varied` is the twin (`vary`): the same ids, markers (`[t<n>] `, `[s<n>.<r>.<j>] `),
call ids, call names, arguments, structure, round counts, stream parameters and byte lengths; every run of letters and digits in free text (user text after the marker, round
text, tool results, the subagent's text, the summary and the document strings) is replaced by a seeded pseudo-word of the same length, the rule of buffon/fixtures/sessions.py
(`pseudo_word`). Each turn's pseudo-words come from the turn's own `Random`, so the twin of a subset is the subset of the twin. A report puts the two rows side by side, and a
gain that appears only on the repeating row is a deduplication gain.

Sizes (bytes of UTF-8 unless a name says characters). One token is four bytes (`BYTES_PER_TOKEN`, Buffon's mock rule).
- `bench8`: eight `lookup` calls in one round, then a final text round. A result is 256 bytes, except the call whose 1-based global number `n * 8 + j + 1` is a multiple of
  97: 8192 bytes. `bench1` and `bench0` are the history turns of durable-bench's shape (`COMPAT_PATTERN`: turns of 1, 1, 0 `lookup` calls, repeating with `n % 3`); they use
  the same global number, so a one-call turn's result is large exactly where the eight-call plan's would be.
- `tools`: 4 to 12 calls in rounds of at most 4 (a full round is 4; the last holds the rest); each result 512 to 8192 bytes; a round with calls carries a short narration
  (30 to 120 characters) in three turns out of ten; the final answer is 200 to 600 characters.
- `text`: no call, an answer of 300 to 1500 characters.
- `large`: one call whose result is 32768 bytes (`LARGE_BYTES`), a final answer of 100 to 300 characters.
- `light`: 1 to 3 calls in one round, each result 2560 to 5632 bytes (the 2.5 to 5.5 KB of the long session's base turn), a final answer of 100 to 400 characters.
- `mixed`: the per-turn draw `MIXED_WEIGHTS`: 50% light, 20% tools, 20% text, 10% large. The weights are the design's invented choice (not measured traffic).
- `stream`: a round with one 256-byte `lookup` call, then a text answer of 600 to 1800 characters streamed as 40 to 60 chunks over 1000 to 2000 ms. Other shapes are not
  streamed (`chunks` 1, `total_ms` 0).
- `crash`: a `lookup` call, then an `effect` call in its own round, then a text answer (the crash matrix's turn); 256-byte results.
- `fanout` (kind `tasks`): one `fanout` call with args `{"k": id, "n": fanout_n}` (`fanout_n` is a shape parameter, default 8), a 256-byte result, a final answer.
- `subagent`: one `subagent` call carrying `sub` (the child's user text with its `[s<n>.0.0] ` marker and one text-only round of 150 to 400 characters); the call's result is
  that text exactly, so the parent sees what the child said.
- Summary: one 2048-byte text in the shape of Pi's summary format (`SUMMARY_BYTES`). Documents: `docs` strings of exactly 88 bytes (`DOC_BYTES`).

Version rule. `GENERATOR` names the output format and the draws. Bump the number whenever the bytes of any script a given (seed, variant, plan, options) produced before
could change: a word, a size, a range, a weight, the order of draws, a header field, the canonical form. Adding a shape or an option that leaves every existing input's output
unchanged does not bump it. A fixture's identity is the sha256 of its script, so a bump shows up as new fixtures, never as a silent change; a store built from an older
generator is never reused for a newer script (the cache key holds GENERATOR).

Command line (history turns 0..history-1, then measured turns history..history+measured-1):

    python3 -m buffon.durable.script --kind mixed --history 5 --measured 3 --seed 20261018 --variant repeating > s.json
"""
import argparse
import copy
import hashlib
import json
import os
import random
import sys
from dataclasses import dataclass, field

from ..fixtures.sessions import pseudo_word, RUN

GENERATOR = "buffon-durable-script/1"
DEFAULT_SEED = 20261018
REPEATING, VARIED = "repeating", "varied"
BYTES_PER_TOKEN = 4

RESULT_BYTES, BIG_RESULT_BYTES, BIG_EVERY = 256, 8192, 97
LARGE_BYTES = 32768
DOC_BYTES = 88
SUMMARY_BYTES = 2048
CALLS_PER_ROUND = 4
COMPAT_PATTERN = (1, 1, 0)   # lookup calls of a history turn n in compat's history: COMPAT_PATTERN[n % 3]
MIXED_WEIGHTS = (("light", 50), ("tools", 20), ("text", 20), ("large", 10))   # percent; the design's invented choice, not measured traffic

TOOL = {"name": "lookup", "description": "Look up a stored record by key.",
        "parameters": {"type": "object", "properties": {"k": {"type": "string"}}, "required": ["k"], "additionalProperties": False}}

WORDS = ("account address agent archive array audit batch binary branch buffer build bundle cache call channel chunk client cluster commit config connection context "
         "counter cursor dataset deadline delta digest directory disk document driver edge entry error event export field filter flag frame gateway graph handle header "
         "history index input journal kernel key label latency ledger limit lookup manifest memory message metric module mutex namespace network node offset output "
         "packet page parser path payload pipeline policy pool queue quota range record region registry release replica request resolver result retry revision route "
         "schema segment sequence server session shard signal slot snapshot socket source stage state storage stream summary table task thread timeout token trace "
         "transaction tuple update value version window worker workflow write check read open close list find merge split sort send fetch store load save apply plan "
         "review report verify confirm inspect compare record resolve schedule submit finish resume restart reopen compact rewind select filter project observe "
         "stable pending ready active quiet steady recent previous current final partial complete missing unused shared private public local remote simple careful "
         "small large short long first second third next last early late again always never often rarely before after during between across within beyond "
         "through under over near far above below inside outside cafe naive resume signal alpha beta gamma delta sigma omega north south east west red green blue "
         "amber violet orange silver copper cobalt granite harbor meadow orchard quarry ridge summit valley willow").split() + ["café", "naïve", "résumé", "señal"]

SHAPES = ("bench8", "bench1", "bench0", "tools", "text", "large", "light", "stream", "crash", "fanout", "subagent")
HISTORY_SHAPE = {"compat": None, "mixed": "mixed", "stream": "mixed", "large": "large", "tasks": "mixed", "subagent": "mixed", "crash": "mixed", "docs": "mixed"}
MEASURED_SHAPE = {"compat": "bench8", "mixed": "mixed", "stream": "stream", "large": "large", "tasks": "fanout", "subagent": "subagent", "crash": "crash", "docs": "mixed"}
KINDS = tuple(HISTORY_SHAPE)


# ---------------------------------------------------------------------------------------------------- randomness and text

def _rng(*parts):
    """A `random.Random` seeded from a sha256 of GENERATOR and `parts`: the same on every host and every run."""
    digest = hashlib.sha256(json.dumps([GENERATOR, *parts], separators=(",", ":"), ensure_ascii=True).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def tokens(nbytes):
    """Tokens of `nbytes` bytes under the one-token-per-four-bytes rule."""
    return -(-nbytes // BYTES_PER_TOKEN)


def _prose(rng, chars, lines=False):
    """Prose-like text of exactly `chars` characters: sentences of 6 to 16 words drawn from WORDS, in paragraphs, or one sentence to a line when `lines`."""
    out, size, par = [], 0, rng.randint(3, 6)
    while size < chars:
        s = " ".join(rng.choices(WORDS, k=rng.randint(6, 16)))
        s = s[0].upper() + s[1:] + "."
        if lines:
            tail = "\n"
        else:
            par -= 1
            tail = " " if par else "\n\n"
            if not par:
                par = rng.randint(3, 6)
        out.append(s + tail)
        size += len(s) + len(tail)
    text = "".join(out)[:chars]
    return text[:-1] + "." if text and text[-1] in " \n" else text


def _fit_bytes(text, nbytes):
    """`text` cut to exactly `nbytes` bytes of UTF-8 (a cut inside a character drops it and pads with periods). `text` must be at least that long."""
    cut = text.encode()[:nbytes].decode("utf-8", "ignore")
    return cut + "." * (nbytes - len(cut.encode()))


def _result_text(rng, key, nbytes):
    return _fit_bytes(f"k={key}\n" + _prose(rng, nbytes, lines=True), nbytes)


# ---------------------------------------------------------------------------------------------------- shapes

def _call(n, r, j, name, result, extra=None, sub=None):
    cid = f"c{n}.{r}.{j}"
    call = {"id": cid, "name": name, "args": dict({"k": cid}, **(extra or {})), "result": result}
    if sub is not None:
        call["sub"] = sub
    return call


def _round(text, calls=()):
    return {"text": text, "calls": list(calls)}


def _bench_size(n, j):
    return BIG_RESULT_BYTES if (n * 8 + j + 1) % BIG_EVERY == 0 else RESULT_BYTES


def _chunked(items):
    return [items[i:i + CALLS_PER_ROUND] for i in range(0, len(items), CALLS_PER_ROUND)]


def _user(rng, n):
    return f"[t{n}] " + _prose(rng, rng.randint(40, 160))


def _shape_bench(count):
    def build(rng, n, params):
        user = _user(rng, n)
        rounds = [_round("", [_call(n, 0, j, "lookup", _result_text(rng, f"c{n}.0.{j}", _bench_size(n, j))) for j in range(count)])] if count else []
        return user, rounds + [_round(_prose(rng, rng.randint(60, 160)))], None
    return build


def _shape_tools(rng, n, params):
    user = _user(rng, n)
    sizes = [rng.randint(512, 8192) for _ in range(rng.randint(4, 12))]
    rounds = []
    for r, group in enumerate(_chunked(sizes)):
        narration = _prose(rng, rng.randint(30, 120)) if rng.random() < 0.3 else ""
        rounds.append(_round(narration, [_call(n, r, j, "lookup", _result_text(rng, f"c{n}.{r}.{j}", size)) for j, size in enumerate(group)]))
    return user, rounds + [_round(_prose(rng, rng.randint(200, 600)))], None


def _shape_text(rng, n, params):
    return _user(rng, n), [_round(_prose(rng, rng.randint(300, 1500)))], None


def _shape_large(rng, n, params):
    user = _user(rng, n)
    return user, [_round("", [_call(n, 0, 0, "lookup", _result_text(rng, f"c{n}.0.0", LARGE_BYTES))]), _round(_prose(rng, rng.randint(100, 300)))], None


def _shape_light(rng, n, params):
    user = _user(rng, n)
    calls = [_call(n, 0, j, "lookup", _result_text(rng, f"c{n}.0.{j}", rng.randint(2560, 5632))) for j in range(rng.randint(1, 3))]
    return user, [_round("", calls), _round(_prose(rng, rng.randint(100, 400)))], None


def _shape_stream(rng, n, params):
    user = _user(rng, n)
    rounds = [_round("", [_call(n, 0, 0, "lookup", _result_text(rng, f"c{n}.0.0", RESULT_BYTES))]), _round(_prose(rng, rng.randint(600, 1800)))]
    return user, rounds, {"chunks": rng.randint(40, 60), "total_ms": rng.randint(1000, 2000)}


def _shape_crash(rng, n, params):
    user = _user(rng, n)
    rounds = [_round("", [_call(n, 0, 0, "lookup", _result_text(rng, f"c{n}.0.0", RESULT_BYTES))]),
              _round("", [_call(n, 1, 0, "effect", _result_text(rng, f"c{n}.1.0", RESULT_BYTES))]), _round(_prose(rng, rng.randint(100, 300)))]
    return user, rounds, None


def _shape_fanout(rng, n, params):
    user = _user(rng, n)
    call = _call(n, 0, 0, "fanout", _result_text(rng, f"c{n}.0.0", RESULT_BYTES), extra={"n": params["fanout_n"]})
    return user, [_round("", [call]), _round(_prose(rng, rng.randint(100, 300)))], None


def _shape_subagent(rng, n, params):
    user = _user(rng, n)
    answer = _prose(rng, rng.randint(150, 400))
    sub = {"user": f"[s{n}.0.0] " + _prose(rng, rng.randint(40, 160)), "rounds": [_round(answer)]}
    return user, [_round("", [_call(n, 0, 0, "subagent", answer, sub=sub)]), _round(_prose(rng, rng.randint(100, 300)))], None


BUILDERS = {"bench8": _shape_bench(8), "bench1": _shape_bench(1), "bench0": _shape_bench(0), "tools": _shape_tools, "text": _shape_text, "large": _shape_large,
            "light": _shape_light, "stream": _shape_stream, "crash": _shape_crash, "fanout": _shape_fanout, "subagent": _shape_subagent}
DEFAULTS = {"fanout_n": 8}   # shape parameters and their defaults
SHAPE_PARAMS = {"fanout": ("fanout_n",)}   # the options a shape's content depends on; they are part of its seed


def concrete_shape(seed, n, shape):
    """The shape turn `n` has: `shape` itself, or for `mixed` the draw of MIXED_WEIGHTS, made from (seed, n) alone."""
    if shape != "mixed":
        return shape
    pick = _rng("mixed", seed, n).randrange(sum(w for _, w in MIXED_WEIGHTS))
    for name, weight in MIXED_WEIGHTS:
        if pick < weight:
            return name
        pick -= weight
    raise AssertionError("unreachable")


def make_turn(seed, n, shape, **options):
    """Turn `n` of the repeating script, from (seed, n, shape, the shape's parameters) alone."""
    shape = concrete_shape(seed, n, shape)
    if shape not in BUILDERS:
        raise ValueError(f"unknown shape {shape!r}")
    params = {k: options.get(k, DEFAULTS[k]) for k in SHAPE_PARAMS.get(shape, ())}
    user, rounds, stream = BUILDERS[shape](_rng("turn", seed, n, shape, params), n, dict(DEFAULTS, **params))
    return {"n": n, "user": user, "shape": shape, "rounds": rounds, "stream": stream or {"chunks": 1, "total_ms": 0}}



# ---------------------------------------------------------------------------------------------------- summary and documents

def make_summary(seed, nbytes=SUMMARY_BYTES):
    """A realistic summary of exactly `nbytes` bytes, in the section layout of Pi's compaction summaries."""
    rng = _rng("summary", seed)
    bullet = lambda mark: f"- {mark}{_prose(rng, rng.randint(60, 140))}"
    parts = ["## Goal\n" + _prose(rng, rng.randint(120, 240)), "## Constraints & Preferences\n" + "\n".join(bullet("") for _ in range(3)),
             "## Progress\n### Done\n" + "\n".join(bullet("[x] ") for _ in range(4)) + "\n\n### In Progress\n" + bullet("[ ] ") + "\n\n### Blocked\n- (none)",
             "## Key Decisions\n" + "\n".join(f"- **{' '.join(rng.choices(WORDS, k=2)).capitalize()}**: {_prose(rng, rng.randint(60, 120))}" for _ in range(3)),
             "## Next Steps\n" + "\n".join(f"{i}. {_prose(rng, rng.randint(50, 110))}" for i in (1, 2, 3)), "## Critical Context\n"]
    text = "\n\n".join(parts)
    while len(text.encode()) < nbytes:
        text += bullet("") + "\n"
    return _fit_bytes(text, nbytes)


def make_doc(seed, i):
    """The i-th document string: exactly DOC_BYTES bytes."""
    return _fit_bytes(_prose(_rng("doc", seed, i), DOC_BYTES + 16), DOC_BYTES)


# ---------------------------------------------------------------------------------------------------- the script

@dataclass(eq=False)
class Script:
    """A script in the format of docs/DURABLE-ADAPTERS.md 4.1. Treat `data` as immutable: the serialised form and its digest are computed once."""
    data: dict
    _dump: bytes = field(default=None, init=False, repr=False)

    def dumps(self):
        """The canonical bytes: sorted keys, compact separators, UTF-8 without escapes, one trailing newline."""
        if self._dump is None:
            self._dump = (json.dumps(self.data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        return self._dump

    @property
    def sha256(self):
        return hashlib.sha256(self.dumps()).hexdigest()

    def turn(self, n):
        for t in self.data["turns"]:
            if t["n"] == n:
                return t
        raise KeyError(f"script has no turn {n}")

    def subset(self, ns):
        """The script with only the turns numbered in `ns` (in script order); the tool, summary and documents stay."""
        wanted = set(ns)
        have = {t["n"] for t in self.data["turns"]}
        if wanted - have:
            raise KeyError(f"script has no turn {sorted(wanted - have)[0]}")
        return Script(dict(self.data, turns=[t for t in self.data["turns"] if t["n"] in wanted]))

    def write(self, path):
        """Write the canonical bytes to `path` (atomically: a reader never sees half a file); returns the sha256."""
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "wb") as f:
            f.write(self.dumps())
        os.replace(tmp, path)
        return self.sha256


def _check_plan(plan):
    out, seen = [], set()
    for n, shape in plan:
        n = int(n)
        if n < 0 or n in seen:
            raise ValueError(f"turn {n}: negative or listed twice")
        if shape != "mixed" and shape not in BUILDERS:
            raise ValueError(f"unknown shape {shape!r}")
        seen.add(n)
        out.append((n, shape))
    return out


def build(seed, variant, plan, *, docs=0, summary_bytes=SUMMARY_BYTES, fanout_n=DEFAULTS["fanout_n"], shape=None):
    """The script of `plan` (a list of (n, shape), `shape` may be "mixed"): `variant` is "repeating" or "varied" (the twin of the repeating script). `shape` is the header's
    shape (the workload's measured shape); by default the plan's one shape, or "mixed" when it holds several."""
    if variant not in (REPEATING, VARIED):
        raise ValueError(f"unknown script variant {variant!r}")
    plan = _check_plan(plan)
    if shape is None:
        shapes = {s for _, s in plan}
        shape = shapes.pop() if len(shapes) == 1 else "mixed"
    base = Script({"format": GENERATOR, "generator": GENERATOR, "seed": seed, "variant": REPEATING, "shape": shape, "tool": copy.deepcopy(TOOL),
                   "summary": {"text": make_summary(seed, summary_bytes)}, "docs": [make_doc(seed, i) for i in range(docs)],
                   "turns": [make_turn(seed, n, s, fanout_n=fanout_n) for n, s in plan]})
    return vary(base) if variant == VARIED else base


def history_plan(kind, count):
    """[(n, shape)] for history turns 0..count-1 of a workload `kind`. compat: durable-bench's 1, 1, 0 pattern; large: large; every other kind: the mixed draw."""
    if kind not in HISTORY_SHAPE:
        raise ValueError(f"unknown kind {kind!r}: one of {', '.join(KINDS)}")
    shape = HISTORY_SHAPE[kind]
    if shape is None:
        return [(n, ("bench1", "bench1", "bench0")[n % 3]) for n in range(count)]
    return [(n, shape) for n in range(count)]


def measured_plan(kind, first, count):
    """[(n, shape)] for measured turns first..first+count-1 of a workload `kind`."""
    if kind not in MEASURED_SHAPE:
        raise ValueError(f"unknown kind {kind!r}: one of {', '.join(KINDS)}")
    return [(n, MEASURED_SHAPE[kind]) for n in range(first, first + count)]


# ---------------------------------------------------------------------------------------------------- the varied twin

def _vary_with(rng, memo):
    def vary_text(text):
        if text not in memo:   # one text varies one way within a turn: a subagent's result stays the text its child said
            memo[text] = RUN.sub(lambda m: pseudo_word(rng, m.group()), text)
        return memo[text]
    return vary_text


def _vary_marked(vary_text, text):
    marker, sep, rest = text.partition("] ")
    return marker + sep + vary_text(rest)


def _vary_rounds(vary_text, rounds):
    for r in rounds:
        r["text"] = vary_text(r["text"])


def vary(script):
    """The varied twin of a repeating script: same ids, markers, structure, round counts and byte lengths; every run of letters and digits in free text replaced by a seeded
    pseudo-word of the same length. Turn n's words come from a `Random` seeded by (seed, n) alone."""
    if script.data["variant"] != REPEATING:
        raise ValueError("only a repeating script has a twin")
    data = copy.deepcopy(script.data)
    seed = data["seed"]
    for turn in data["turns"]:
        v = _vary_with(_rng("vary", seed, turn["n"]), {})
        turn["user"] = _vary_marked(v, turn["user"])
        for r in turn["rounds"]:
            r["text"] = v(r["text"])
            for call in r["calls"]:
                call["result"] = v(call["result"])
                if "sub" in call:
                    call["sub"]["user"] = _vary_marked(v, call["sub"]["user"])
                    _vary_rounds(v, call["sub"]["rounds"])
    data["summary"]["text"] = _vary_with(_rng("vary-summary", seed), {})(data["summary"]["text"])
    data["docs"] = [_vary_with(_rng("vary-doc", seed, i), {})(d) for i, d in enumerate(data["docs"])]
    data["variant"] = VARIED
    return Script(data)


# ---------------------------------------------------------------------------------------------------- facts and the cache

def turn_bytes(turn):
    """Bytes a turn adds to the parent's context: the user text, every round's text and every call's name, id and result."""
    total = len(turn["user"].encode())
    for r in turn["rounds"]:
        total += len(r["text"].encode())
        for c in r["calls"]:
            total += len(c["name"].encode()) + len(c["id"].encode()) + len(c["result"].encode())
    return total


def facts(script):
    """What a report prints about a script: {sha256, seed, variant, turns, bytes, ...}. `approx_tokens` is the turns' content under the one-token-per-four-bytes rule."""
    d = script.data
    turns = d["turns"]
    shapes = {}
    for t in turns:
        shapes[t["shape"]] = shapes.get(t["shape"], 0) + 1
    calls = [c for t in turns for r in t["rounds"] for c in r["calls"]]
    return {"sha256": script.sha256, "generator": d["generator"], "seed": d["seed"], "variant": d["variant"], "shape": d["shape"], "turns": len(turns),
            "first_turn": min((t["n"] for t in turns), default=None), "last_turn": max((t["n"] for t in turns), default=None), "bytes": len(script.dumps()),
            "shapes": dict(sorted(shapes.items())), "calls": len(calls), "result_bytes": sum(len(c["result"].encode()) for c in calls), "docs": len(d["docs"]),
            "summary_bytes": len(d["summary"]["text"].encode()), "approx_tokens": sum(tokens(turn_bytes(t)) for t in turns)}


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cached(cache_dir, seed, variant, plan, **options):
    """Build the script of (seed, variant, plan, options) or reuse the one built before; returns (path, facts). The file is `<cache_dir>/<sha256>.script.json`, written once;
    `by-inputs/<key>` maps the inputs (with GENERATOR) to that digest so a hit does not generate; a file whose digest is not its name is rebuilt."""
    plan = _check_plan(plan)
    key = hashlib.sha256(json.dumps([GENERATOR, seed, variant, plan, options], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    index = os.path.join(cache_dir, "by-inputs", key)
    os.makedirs(os.path.dirname(index), exist_ok=True)
    if os.path.exists(index):
        with open(index) as f:
            digest = f.read().strip()
        path, facts_path = (os.path.join(cache_dir, f"{digest}.script.json"), os.path.join(cache_dir, f"{digest}.facts.json"))
        if os.path.exists(path) and os.path.exists(facts_path) and _file_sha256(path) == digest:
            with open(facts_path) as f:
                return path, json.load(f)
    script = build(seed, variant, plan, **options)
    digest = script.sha256
    path, facts_path = (os.path.join(cache_dir, f"{digest}.script.json"), os.path.join(cache_dir, f"{digest}.facts.json"))
    if not (os.path.exists(path) and _file_sha256(path) == digest):
        script.write(path)
    result = facts(script)
    with open(facts_path, "w") as f:
        json.dump(result, f, sort_keys=True)
    with open(index, "w") as f:
        f.write(digest + "\n")
    return path, result


# ---------------------------------------------------------------------------------------------------- command line

def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m buffon.durable.script", description="Write a durable script: history turns 0..history-1, then measured turns.")
    p.add_argument("--kind", default="mixed", choices=KINDS)
    p.add_argument("--history", type=int, default=0, help="history turns (0..history-1)")
    p.add_argument("--measured", type=int, default=10, help="measured turns (history..history+measured-1)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--variant", default=REPEATING, choices=(REPEATING, VARIED))
    p.add_argument("--docs", type=int, default=None, help="document strings (default 0; 1000 for kind docs)")
    p.add_argument("--fanout-n", type=int, default=DEFAULTS["fanout_n"], help="child tasks of a fanout call")
    p.add_argument("--summary-bytes", type=int, default=SUMMARY_BYTES)
    p.add_argument("--measured-only", action="store_true", help="leave the history turns out: the script an adapter drives against an existing fixture")
    p.add_argument("--out", help="write here instead of stdout")
    p.add_argument("--facts", action="store_true", help="print the script's facts as JSON on stderr")
    a = p.parse_args(argv)
    plan = ([] if a.measured_only else history_plan(a.kind, a.history)) + measured_plan(a.kind, a.history, a.measured)
    docs = a.docs if a.docs is not None else (1000 if a.kind == "docs" else 0)
    script = build(a.seed, a.variant, plan, docs=docs, summary_bytes=a.summary_bytes, fanout_n=a.fanout_n, shape=MEASURED_SHAPE[a.kind])
    if a.out:
        script.write(a.out)
    else:
        sys.stdout.buffer.write(script.dumps())
        sys.stdout.buffer.flush()
    if a.facts:
        print(json.dumps(facts(script), sort_keys=True), file=sys.stderr)


if __name__ == "__main__":
    main()
