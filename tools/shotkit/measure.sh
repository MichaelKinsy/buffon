#!/bin/bash
# measure.sh SITE: words, visible controls and height of the main pages (pages-measure.txt) at 390 and 1440 px
K="$(cd "$(dirname "$0")" && pwd)"
ARGS=(); while IFS= read -r l; do [ -n "$l" ] && ARGS+=("$l"); done < "${PAGES:-$K/pages-measure.txt}"
docker run --rm --ipc=host -v "$K":/kit -v "$1":/work/site:ro mcr.microsoft.com/playwright:v1.56.0-noble bash -c 'cd /work/site && python3 -m http.server 8090 --bind 127.0.0.1 >/dev/null 2>&1 & sleep 1; cd /kit && npm i -s playwright@1.56.0 >/dev/null 2>&1; node measure.js "$@"' _ "${ARGS[@]}"
