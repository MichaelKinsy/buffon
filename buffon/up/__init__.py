# SPDX-License-Identifier: Apache-2.0
"""`buffon up`: one command from a fresh clone to a running buffon and an open dashboard (docs/GETTING-STARTED.md).

  machine.py    what this computer is (OS, CPUs, SMT, counters, container runtime) and the site profile `up` writes for it
  catalog.py    the presets (quick, standard, full), the tracks, the default harness set, what each benchmark measures and its state
  selection.py  parsing `--harness` / `--bench`, saving and loading a selection (TOML), the exact command that reproduces one
  estimate.py   a short probe of this machine and the time each choice is expected to take
  picker.py     the interactive picker (arrow keys and space on a terminal, plain input() otherwise)
  flow.py       the steps: install, measure, evaluate, report, dashboard, summary
"""
