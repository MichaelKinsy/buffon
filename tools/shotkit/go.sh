#!/bin/bash
# go.sh <site> <out>: shoot every page in pages.txt (playwright in colima docker)
K="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$2"
ARGS=(); while IFS= read -r l; do [ -n "$l" ] && ARGS+=("$l"); done < "${PAGES:-$K/pages.txt}"
docker run --rm --ipc=host -v "$K":/kit -v "$1":/work/site:ro -v "$2":/out mcr.microsoft.com/playwright:v1.56.0-noble /kit/run.sh "${ARGS[@]}"
