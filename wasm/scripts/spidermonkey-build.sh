#!/usr/bin/env bash
set -euo pipefail
cd /spike/mozjs-128.13.0
if [[ "$(cat /spike/evidence/configure-exit-code.txt)" != 0 ]]; then
    echo 'SKIPPED_BUILD: configure failed' > /spike/evidence/build-status.txt
    exit 0
fi
export MOZ_NOSPAM=1 MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=none
export MOZBUILD_STATE_PATH=/spike/mozbuild-state MOZCONFIG=/spike/mozconfig
set +e
timeout --kill-after=30s 30m ./mach build -j2 > /spike/evidence/build.log 2>&1 &
build_pid=$!
while kill -0 "$build_pid" 2>/dev/null; do
    sleep 30
    printf 'SpiderMonkey build: log bytes=%s; last line: ' "$(wc -c < /spike/evidence/build.log)"
    tail -1 /spike/evidence/build.log | cut -c1-180
done
wait "$build_pid"
result=$?
set -e
printf '%s\n' "$result" > /spike/evidence/build-exit-code.txt
if [[ "$result" == 0 ]]; then
    echo 'BUILT_ONLY: linking and JS runtime not yet tested' > /spike/evidence/build-status.txt
    find build-wasm -type f -name '*.a' -print > /spike/evidence/static-archives.txt
else
    echo 'BLOCKED_BUILD: not a successful SpiderMonkey WASM build' > /spike/evidence/build-status.txt
fi
cat /spike/evidence/build-status.txt
tail -60 /spike/evidence/build.log
