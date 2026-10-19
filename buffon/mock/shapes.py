# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Answer shapes for the streaming workload: prose, code blocks, tables, lists. Deterministic text of an exact length.

Adapted from bench/compare/stream_shapes.py of the PiG repository (same generators, same method as Pi-Bolt's long_answer: fixed-size chunks at a fixed pace)."""

WORDS = ("stream render buffer token layout width column cursor frame paint scroll cache parse chunk delta yield flush "
         "queue event handler session model prompt answer window terminal screen style border margin theme").split()


def sentence(n, k):
    w = [WORDS[(n * 7 + k * 3 + j * 5) % len(WORDS)] for j in range(9 + (n + k) % 6)]
    return f"{w[0].capitalize()} {' '.join(w[1:])} {n * 31 + k}."


def prose(n):
    return f"## Section {n}\n\n" + " ".join(sentence(n, k) for k in range(5)) + "\n\n" + " ".join(sentence(n + 1000, k) for k in range(4)) + "\n\n"


def code(n):
    return (f"### Function {n}\n\nThe helper below handles case {n}.\n\n```ts\nexport function parse{n}(input: string): number[] {{\n"
            f"\tconst out: number[] = [];\n\tfor (let i = 0; i < input.length; i++) {{\n\t\tif (input.charCodeAt(i) === {40 + n % 50}) out.push(i * {n});\n\t}}\n"
            f"\treturn out;\n}}\n```\n\nIt returns the offsets found.\n\n").replace("{n}", str(n))


def table(n):
    rows = "\n".join(f"| item{n}-{r} | {r * n % 997} | {sentence(n, r)[:40]} | {'yes' if r % 2 else 'no'} |" for r in range(8))
    return f"### Table {n}\n\n| name | value | note | flag |\n|---|---:|---|:---:|\n{rows}\n\n"


def lists(n):
    out = [f"### List {n}\n"]
    for i in range(5):
        out.append(f"- Item {n}.{i}: {sentence(n, i)[:50]}")
        out += [f"  - Sub {i}.{j}: {sentence(i, j)[:40]}" for j in range(3)]
    out += [f"{i + 1}. Step {i + 1} of {n}: {sentence(n, i + 9)[:45]}" for i in range(4)]
    return "\n".join(out) + "\n\n"


SHAPES = {"prose": prose, "code": code, "tables": table, "lists": lists}


def body(shape, size):
    """Exactly `size` characters of `shape`."""
    text, n = "", 0
    while len(text) < size:
        n += 1
        text += SHAPES[shape](n)
    return text[:size]


def source(size):
    """Exactly `size` characters of TypeScript source, one short function per line with no final newline: the file body of the large-write workload (the same text as Pi-Bolt's `write:N` scenario)."""
    lines, total = [], 0
    while total < size:
        n = len(lines)
        lines.append(f"export function step{n}(input: number[]): number {{ return input.reduce((a, b) => a + b * {n % 97}, {n}); }}")
        total += len(lines[-1]) + 1
    return "\n".join(lines)[:size]
