#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# ./buffon.sh up: the one command from a fresh clone to a running buffon. Anything else: ./buffon.sh <command> (the same as python3 -m buffon <command>).
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    cd "$here" || exit 1
    BUFFON_PROGRAM=./buffon.sh exec "$py" -m buffon "$@"
  fi
done
echo "Buffon needs Python 3.11 or later (python3 --version)" >&2
exit 1
