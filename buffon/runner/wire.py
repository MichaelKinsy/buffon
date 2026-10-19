# SPDX-License-Identifier: Apache-2.0
"""What one sample put on the wire: the model requests the mock received between the sample's start and its end, and their body bytes (docs/WHAT-WE-MEASURE.md, wire efficiency).

The count is central, so every workload gets it. A workload that knows how many turns and requests it scripted says so with `declare`; the runner then adds the bytes per turn
and the side requests (beyond the scripted ones, such as a title request). An arm that declares `exact_requests` must send none."""

KEY = "_wire"


def declare(sample, turns, scripted, exact=True):
    """Mark `sample` with its turn count and the number of model requests the workload scripted. `exact` is False where the count of scripted requests is not fixed
    (a compaction the harness decides on), so an arm that promises exact requests is not failed on it."""
    sample[KEY] = {"turns": turns, "scripted": scripted, "exact": exact}
    return sample


def mark(server):
    """The server's counters before a sample, or None where it keeps none (a server whose requests are served elsewhere)."""
    wire_mark = getattr(server, "wire_mark", None)
    return wire_mark() if wire_mark else None


def apply(sample, server, before, arm):
    """Add the wire metrics of the sample that began at `before` to `sample`. Pops the workload's declaration. Nothing is added when the mock saw no request."""
    declared = sample.pop(KEY, None)
    if before is None:
        return
    count, size = (a - b for a, b in zip(server.wire_mark(), before))
    if not count:
        return
    sample["requests"], sample["request_bytes"] = count, size
    if declared is None:
        return
    if declared["turns"]:
        sample["request_bytes_per_turn"] = size / declared["turns"]
    side = max(0, count - declared["scripted"])
    sample["side_requests"] = side
    if side and declared["exact"] and arm.capabilities.get("exact_requests") and "failure" not in sample:
        sample["failure"] = f"the arm declares exact_requests, but the mock saw {count} requests for {declared['scripted']} scripted"
