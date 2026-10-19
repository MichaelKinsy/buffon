#!/bin/bash
# run.sh <site dir> <out dir> route=name ...  (inside the playwright image)
cd /work/site && python3 -m http.server 8090 --bind 127.0.0.1 >/dev/null 2>&1 &
sleep 1; cd /kit && npm i -s playwright@1.56.0 >/dev/null 2>&1; node shoot.js /out "$@"
