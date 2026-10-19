# SPDX-License-Identifier: Apache-2.0
"""The bench extensions: N copies of one checked-in template (fixtures/extensions/bench-ext.template.ts), numbered. Extension 1..N of any count are the same files, so five are the first
five of ten. Deterministic: the same template and count give the same bytes. The template's sha256 is the proof of what ran."""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_PATH = os.path.join(ROOT, "fixtures", "extensions", "bench-ext.template.ts")
MARK = "{{NN}}"


def template_bytes():
    with open(TEMPLATE_PATH, "rb") as f:
        return f.read()


def template_sha256():
    return hashlib.sha256(template_bytes()).hexdigest()


def number(n):
    """The extension's number as it appears in its tool name, label, result text and command: two digits, more where the count needs them."""
    return f"{n:02d}"


def read(path):
    with open(path) as f:
        return f.read()


def render(n):
    return template_bytes().decode().replace(MARK, number(n))


def make(directory, count):
    """Write extensions 1..count into directory (an identical file already there is left alone) and return their paths in order."""
    os.makedirs(directory, exist_ok=True)
    paths = []
    for n in range(1, count + 1):
        path = os.path.join(directory, f"bench-ext-{number(n)}.ts")
        text = render(n)
        if not os.path.exists(path) or read(path) != text:
            with open(path, "w", newline="\n") as f:
                f.write(text)
        paths.append(path)
    return paths
