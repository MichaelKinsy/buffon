# SPDX-License-Identifier: Apache-2.0
"""The import guard: an upstream suite runs only when every file it names still has the sha256 recorded at its pin.

A suite target records (path, sha256) pairs relative to the checkout root. A target with no pairs is
unpinned and does not run. A missing or changed file refuses the run and names the file. The commit pin
and the clean-tree check (runner.check_checkout) cover the rest of the checkout.
"""
import hashlib
import os

SHA256 = frozenset("0123456789abcdef")


class Refused(Exception):
    """The suite was not started, with the reason."""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_entries(manifest, suite_id):
    """Refuse a malformed manifest at definition time: relative paths and 64-hex digests only."""
    for rel, digest in manifest:
        if os.path.isabs(rel) or ".." in rel.split("/") or not rel:
            raise ValueError(f"{suite_id}: manifest path {rel!r} must be relative to the checkout root")
        if len(digest) != 64 or not set(digest) <= SHA256:
            raise ValueError(f"{suite_id}: manifest digest for {rel} is not a sha256")


def status(root, manifest):
    """{path: (state, pinned, actual)} where state is ok, modified or missing. Reads every named file once."""
    out = {}
    for rel, pinned in manifest:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            out[rel] = ("missing", pinned, None)
            continue
        actual = sha256_file(path)
        out[rel] = ("ok" if actual == pinned else "modified", pinned, actual)
    return out


def verify(root, manifest, suite_id):
    """Return {path: sha256} for the verified files, or raise Refused naming the first file that fails."""
    if not manifest:
        raise Refused(f"{suite_id} has no recorded file digests at its pin: an unpinned suite does not run (record the digests of its files at the pin)")
    for rel, (state, pinned, actual) in status(root, manifest).items():
        if state == "missing":
            raise Refused(f"{rel} is missing from the checkout: the suite is not the pinned suite")
        if state == "modified":
            raise Refused(f"{rel} is modified: sha256 {actual[:12]} is not the pinned {pinned[:12]}; the suite runs unchanged or not at all")
    return {rel: pinned for rel, pinned in manifest}
