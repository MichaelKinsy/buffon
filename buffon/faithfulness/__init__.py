# SPDX-License-Identifier: Apache-2.0
"""The Pi Faithfulness Score: how closely a harness behaves like Pi, measured by deterministic black-box probes.

The reference is Pi at the release the run pins (Node), which scores 100 by definition. Every probe runs the same scripted situation against the reference and the harness on the
buffon's mock model endpoint, reduces what each did to a normalised observation (binary name, config directory, paths, ids and dates masked) and compares the two observations for
equality. No model judges anything. Dimensions F1-F8 and the weights are in `probes.DIMENSIONS`; `PROBE_SET_VERSION` names the probe set a score belongs to."""

PROBE_SET_VERSION = "v0.2"
