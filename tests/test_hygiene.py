# SPDX-License-Identifier: Apache-2.0
"""The repository is host-independent: no machine, user, home directory, cluster or private address appears in a tracked file.

Machine-specific values live in site profiles (sites/<name>.toml, gitignored apart from the examples), flags and BUFFON_* variables.
"""
import ipaddress
import os
import re
import subprocess
import unittest

from tests.banned_words import pattern

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "runs", ".cache"}
SKIP_FILES = {"package-lock.json", "install-package-lock.json", "arms.lock"}  # vendor lockfiles carry registry URLs and integrity hashes, not our hosts
HOME_PATH = re.compile(r"(?<![\w.$~])/(?:home|Users|root)/[\w.-]+")
IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.])")
SVG_PATH_DATA = re.compile(r'\bd="[MmLlHhVvCcSsQqTtAaZz\d\s.,-]+"')   # minified path data packs numbers as `1.23.82.72` (1.23, .82, .72): coordinates, not an address
# Words that name a machine, an account or an internal system of the people who built this; a public repository has no use for them.
# The generic words are in tests/banned_words.py. A private list can add to them: it is read from BUFFON_FORBIDDEN_WORDS (a regular expression)
# or a file named by BUFFON_FORBIDDEN_WORDS_FILE; without either, only the generic words apply.
_PRIVATE_WORDS = os.environ.get("BUFFON_FORBIDDEN_WORDS") or (
    open(os.environ["BUFFON_FORBIDDEN_WORDS_FILE"]).read().strip() if os.environ.get("BUFFON_FORBIDDEN_WORDS_FILE") else "")
FORBIDDEN_WORDS = pattern("machine", _PRIVATE_WORDS)
# Files that state the machine words they ban: the scanner's own test, the one list of banned words, and the page that tells authors about them.
RULE_FILES = {"tests/test_hygiene.py", "tests/banned_words.py", "CONTRIBUTING.md"}
# Files that may name the project's creator or its upstream repositories: licence, notices, contribution and survey documents, and manifests that
# link to public repositories of the harnesses they pin.
NAME_ALLOWED = {"LICENSE", "LICENSES/MIT.txt", "NOTICE", "README.md", "CONTRIBUTING.md", "docs/DESIGN.md", "docs/HARNESS-SURVEY.md", "docs/METHODOLOGY.md"}
PUBLIC_URL = re.compile(r"(?:https://)?github\.com/MichaelKinsy/PiG[^\s\"']*", re.I)   # a URL, or the Go module path of the PiG SDK the extension fixtures import


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    return [f for f in out if f and os.path.isfile(os.path.join(ROOT, f)) and os.path.basename(f) not in SKIP_FILES and not any(p in SKIP_DIRS for p in f.split("/"))]


def is_text(path):
    with open(path, "rb") as f:
        return b"\0" not in f.read(4096)


def allowed_ip(text):
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return True  # a version number such as 1.2.3.4 is not an address
    return ip.is_loopback or ip.is_unspecified or text.startswith(("192.0.2.", "198.51.100.", "203.0.113."))  # loopback and RFC 5737 documentation ranges


class Hygiene(unittest.TestCase):
    def scan(self):
        for rel in tracked_files():
            path = os.path.join(ROOT, rel)
            if not is_text(path):
                continue
            with open(path, errors="replace") as f:
                for n, line in enumerate(f, 1):
                    yield rel, n, line

    def test_no_absolute_home_paths(self):
        hits = [f"{rel}:{n}: {m.group(0)}" for rel, n, line in self.scan() for m in HOME_PATH.finditer(line) if rel != "tests/test_hygiene.py"]
        self.assertEqual(hits, [], "a home directory is machine-specific: use a site profile, a flag or an environment variable")

    def test_no_non_loopback_addresses(self):
        hits = [f"{rel}:{n}: {m.group(1)}" for rel, n, line in self.scan() for m in IPV4.finditer(SVG_PATH_DATA.sub('d=""', line)) if not allowed_ip(m.group(1)) and rel != "tests/test_hygiene.py"]
        self.assertEqual(hits, [])

    def test_no_machine_account_or_internal_names(self):
        hits = []
        for rel, n, line in self.scan():
            if rel in RULE_FILES:
                continue
            for m in FORBIDDEN_WORDS.finditer(PUBLIC_URL.sub("", line)):
                if rel in NAME_ALLOWED and m.group(0).lower() == "kinsy":
                    continue
                hits.append(f"{rel}:{n}: {m.group(0)}")
        self.assertEqual(hits, [])

    def test_the_scanner_itself_catches_what_it_should(self):
        self.assertTrue(HOME_PATH.search("cache = /home/alice/.cache"))
        self.assertTrue(HOME_PATH.search("/Users/bob/x"))
        self.assertIsNone(HOME_PATH.search("$HOME/.agent and ~/x and ${HOME}/y"))
        self.assertFalse(allowed_ip("10.1.2.3"))
        self.assertFalse(allowed_ip("192.168.1.9"))
        self.assertTrue(allowed_ip("127.0.0.1"))
        self.assertTrue(allowed_ip("203.0.113.9"))
        self.assertTrue(FORBIDDEN_WORDS.search("host.internal"))

    def test_the_example_profiles_hold_placeholders_only(self):
        for name in ("example-local.toml", "example-macos.toml", "example-kubernetes.toml"):
            with open(os.path.join(ROOT, "sites", name)) as f:
                text = f.read()
            self.assertNotRegex(text, r"@sha256:[0-9a-f]{64}")


if __name__ == "__main__":
    unittest.main()
