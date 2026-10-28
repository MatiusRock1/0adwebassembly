#!/usr/bin/env bash
set -euo pipefail
sm=/spike/mozjs-128.13.0/build-wasm
emcmake cmake -S /spike/wasm -B /spike/browser-build \
 -DHEADLESS_BROWSER=ON -DHEADLESS_SOURCE_ROOT=/spike/0ad-source \
 -DHEADLESS_DEPENDENCY_INCLUDE_DIR=/spike/headless/include \
 -DHEADLESS_TEST_SCRIPT=/build/0ad/binaries/data/mods/_test.sim/simulation/components/test.js \
 -DSPIDERMONKEY_INCLUDE_DIR="$sm/dist/include" \
 -DSPIDERMONKEY_LIBRARY="$sm/js/src/build/libjs_static.a" \
 -DSPIDERMONKEY_WASM_OBJECT_ROOT="$sm" -DCMAKE_BUILD_TYPE=Release
cmake --build /spike/browser-build --target pyrogenesis-browser -j2
mkdir -p /spike/browser
cp /spike/browser-build/pyrogenesis-browser* /spike/browser/
cp /spike/evidence/parity/native-state.json /spike/browser/
mkdir -p /spike/browser/evidence
cp /spike/evidence/parity/* /spike/browser/evidence/
# Source locations of advice calls are diagnostic evidence, not a syscall override.
grep -R -n -B 8 -A 12 'madvise(' /spike/mozjs-128.13.0/mfbt /spike/mozjs-128.13.0/memory /spike/mozjs-128.13.0/js/src/gc > /spike/browser/evidence/madvise-source.txt || test "$?" = 1

cd /spike/browser
find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
