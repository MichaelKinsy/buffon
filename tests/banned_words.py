# SPDX-License-Identifier: Apache-2.0
"""The words the tests ban, in one place. Three tests read this list: tests/test_docs.py (claim words in the documents a reader starts with,
comparatives in LIMITATIONS.md) and tests/test_hygiene.py (machine names in every tracked file). CONTRIBUTING.md, "Rules the tests check", names the
same words for authors, and tests/test_docs.py checks that the two agree."""
import re

# name -> (where the test looks, the words). A word that starts or ends with a letter or digit is matched as a whole word.
BANNED = {
    "claim": ("README.md, METHODOLOGY.md, RUNNING.md, WHAT-WE-MEASURE.md, FIELD.md, LIMITATIONS.md",
              ("fastest", "slowest", "best", "winner", "beat", "beats", "outperform", "outperforms", "outperformed", "outperforming", "blazing", "blazingly",
               "unmatched", "state-of-the-art", "world-class", "superior", "unbeaten", "cutting-edge")),
    "comparative": ("LIMITATIONS.md",
                    ("better", "worse", "lighter", "heavier", "faster", "slower", "win", "wins", "lose", "loses", "superior", "inferior", "leaner")),
    "machine": ("every tracked file",
                (".ts.net", ".internal", "k3d-")),
}


def pattern(name, extra=""):
    """A case-insensitive regex for the words of BANNED[name]; `extra` is one more regex alternative (the private list of tests/test_hygiene.py)."""
    parts = []
    for word in BANNED[name][1]:
        left = r"(?<!\w)" if re.match(r"\w", word) else ""
        right = r"(?!\w)" if re.search(r"\w$", word) else ""
        parts.append(left + re.escape(word) + right)
    if extra:
        parts.append(extra)
    return re.compile("|".join(parts), re.I)
