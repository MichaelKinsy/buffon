# SPDX-License-Identifier: Apache-2.0
"""What a metric is: its kind (wall time, CPU work, memory, size, wire) and its unit. Every cell of a report names both, and a row never mixes kinds: instructions, CPU time and wall time are separate cells.

Instructions are the headline CPU metric where the host can count them (docs/METHODOLOGY.md section 4); CPU time (user + system, from wait4 or the cgroup) and wall time sit beside them."""

WALL, CPU, MEMORY, SIZE, WIRE, OTHER = "wall", "CPU", "memory", "size", "wire", "other"
WIRE_METRICS = {"requests": "count", "side_requests": "count", "request_bytes": "bytes", "request_bytes_per_turn": "bytes per turn",
                "first_request_bytes": "bytes"}   # what a sample put on the wire; never in the grade. first_request_bytes: runs from before the wire metrics (raw.first_request_bytes)


def describe(metric):
    """(kind, unit) of a metric by its name; the names are Buffon's own (docs/RAW-FORMAT.md)."""
    per = " per 1k tokens" if "_per_1k_tokens" in metric else " per turn" if metric.endswith("_per_turn") else " per agent-turn" if metric.endswith("_per_agent_turn") else ""
    if metric in WIRE_METRICS:
        return WIRE, WIRE_METRICS[metric]
    if metric == "instructions" or "_instructions" in metric:
        return CPU, "instructions" + per
    if metric == "cycles" or "_cycles" in metric:
        return CPU, "cycles" + per
    if "cpu_ms" in metric:
        return CPU, "ms of CPU time" + per
    if metric == "turns_per_s":
        return OTHER, "agent-turns per second (higher is better)"
    if metric.endswith("_mib") or "_mib_per_" in metric:
        return MEMORY, "MiB" + (" per agent" if metric.endswith("_per_agent") else "")
    if metric.endswith("_bytes") or "_bytes_" in metric:
        return SIZE, "bytes" + per
    if metric.endswith("_ms") or "_ms_" in metric:
        return WALL, "ms" + per
    return OTHER, ""


def headline_cpu(metrics):
    """The CPU metric a report leads with among `metrics` of one workload: instructions when present, else CPU time."""
    for name in ("instructions", "cpu_ms"):
        if name in metrics:
            return name
    return None
