#!/usr/bin/env bash
set -euo pipefail
root=/spike/0ad-source
sm=/spike/mozjs-128.13.0/build-wasm
native_sm=/build/0ad/libraries/source/spidermonkey
evidence=/spike/evidence/parity
mkdir -p "$evidence"
echo BUILD_FAILED > "$evidence/status.txt"
common=(-S /spike/wasm -DHEADLESS_SOURCE_ROOT="$root"
  -DHEADLESS_DEPENDENCY_INCLUDE_DIR=/spike/headless/include
  -DHEADLESS_TEST_SCRIPT=/build/0ad/binaries/data/mods/_test.sim/simulation/components/test.js
  -DCMAKE_BUILD_TYPE=Release)
set +e
cmake "${common[@]}" -B /spike/parity-native \
  -DSPIDERMONKEY_INCLUDE_DIR="$native_sm/include-release" \
  -DSPIDERMONKEY_LIBRARY="$native_sm/lib/libmozjs128-release.so" \
  > "$evidence/native-build.log" 2>&1 && \
  cmake --build /spike/parity-native --target pyrogenesis-headless -j2 >> "$evidence/native-build.log" 2>&1
native_build=$?
echo "$native_build" > "$evidence/native-build-exit-code.txt"
if [[ "$native_build" != 0 ]]; then tail -45 "$evidence/native-build.log"; exit 0; fi
timeout 120s /spike/parity-native/pyrogenesis-headless \
  /build/0ad/binaries/data/mods/_test.sim/simulation/components/test.js \
  > "$evidence/native-state.json" 2> "$evidence/native-runtime.log"
native_run=$?
echo "$native_run" > "$evidence/native-run-exit-code.txt"
emcmake cmake "${common[@]}" -B /spike/parity-wasm \
  -DSPIDERMONKEY_INCLUDE_DIR="$sm/dist/include" \
  -DSPIDERMONKEY_LIBRARY="$sm/js/src/build/libjs_static.a" \
  -DSPIDERMONKEY_WASM_OBJECT_ROOT="$sm" \
  > "$evidence/wasm-build.log" 2>&1 && \
  cmake --build /spike/parity-wasm --target pyrogenesis-wasm -j2 >> "$evidence/wasm-build.log" 2>&1
wasm_build=$?
echo "$wasm_build" > "$evidence/wasm-build-exit-code.txt"
if [[ "$wasm_build" != 0 ]]; then tail -45 "$evidence/wasm-build.log"; exit 0; fi
timeout 120s node /spike/parity-wasm/pyrogenesis-wasm.js \
  > "$evidence/wasm-runtime.log" 2>&1
wasm_run=$?
echo "$wasm_run" > "$evidence/wasm-run-exit-code.txt"
sed -n '/^{"scenario":/p' "$evidence/wasm-runtime.log" > "$evidence/wasm-state.json"
if [[ "$native_run" == 0 && "$wasm_run" == 0 ]] && \
    cmp -s "$evidence/native-state.json" "$evidence/wasm-state.json" && \
    [[ -s "$evidence/native-state.json" ]]; then
  echo PARITY_PASSED > "$evidence/status.txt"
  sha256sum "$evidence/native-state.json" "$evidence/wasm-state.json" > "$evidence/state.sha256"
  cat "$evidence/native-state.json" "$evidence/state.sha256"
else
  echo PARITY_FAILED > "$evidence/status.txt"
  tail -25 "$evidence/wasm-runtime.log"
  cat "$evidence/native-runtime.log"
fi
cat "$evidence/status.txt"
exit 0
