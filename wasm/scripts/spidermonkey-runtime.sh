#!/usr/bin/env bash
set -euo pipefail
evidence=/spike/evidence
obj=/spike/mozjs-128.13.0/build-wasm
rm -f "$evidence/runtime-exit-code.txt" "$evidence/runtime.log"
if [[ "$(cat "$evidence/rust-std-build-exit-code.txt")" != 0 ]]; then
  echo SKIPPED_RUST_BUILD_FAILED > "$evidence/runtime-status.txt"
  exit 0
fi
mapfile -t support_objects < <(find "$obj/mozglue" "$obj/memory" "$obj/mfbt" -name '*.o' | sort)
set +e
em++ /spike/spidermonkey.cpp -g3 -std=c++17 -I"$obj/dist/include" \
  "$obj/js/src/build/libjs_static.a" "$obj/wasm32-unknown-emscripten/release/libjsrust.a" \
  "$obj/build/pure_virtual/libpure_virtual.a" "${support_objects[@]}" \
  -pthread --use-port=zlib -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=5242880 \
  -sASSERTIONS=2 -o /spike/runtime.js > "$evidence/runtime-link.log" 2>&1
link_result=$?
printf '%s\n' "$link_result" > "$evidence/runtime-link-exit-code.txt"
if [[ "$link_result" == 0 ]]; then
  timeout 120s node /spike/runtime.js > "$evidence/runtime.log" 2>&1
  run_result=$?
  printf '%s\n' "$run_result" > "$evidence/runtime-exit-code.txt"
  if [[ "$run_result" == 0 ]]; then
    echo RUNTIME_PROBE_PASSED > "$evidence/runtime-status.txt"
    sha256sum /spike/runtime.js /spike/runtime.wasm > "$evidence/runtime.sha256"
  else
    echo RUNTIME_PROBE_FAILED > "$evidence/runtime-status.txt"
  fi
  tail -40 "$evidence/runtime.log"
else
  echo LINK_FAILED > "$evidence/runtime-status.txt"
  tail -60 "$evidence/runtime-link.log"
fi
cat "$evidence/runtime-status.txt"
exit 0
