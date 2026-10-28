#!/usr/bin/env bash
set -euo pipefail
root=/spike/0ad-source
obj=/spike/mozjs-128.13.0/build-wasm
evidence=/spike/evidence/headless
mapfile -t support < <(find "$obj/mozglue" "$obj/memory" "$obj/mfbt" -name '*.o' | sort)
asset_flags=()
if [[ -d /spike/simulation/objects ]]; then
  asset_flags=(--embed-file /build/0ad/binaries/data/mods/_test.sim/simulation/components/test.js@/scenario/test.js)
fi
set +e
em++ -std=c++20 -pthread -g -DFMT_HEADER_ONLY -DNDEBUG \
  -I/spike/headless/adapters -I"$root" -I/spike/headless/include -I"$obj/dist/include" \
  /spike/headless-main.cpp /spike/headless/objects/*.o \
  "$obj/js/src/build/libjs_static.a" \
  "$obj/wasm32-unknown-emscripten/release/libjsrust.a" \
  "$obj/build/pure_virtual/libpure_virtual.a" "${support[@]}" \
  "${asset_flags[@]}" --use-port=zlib -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=5242880 \
  -sASSERTIONS=2 -Wl,--error-limit=100 -o /spike/pyrogenesis-wasm.js \
  > "$evidence/link.log" 2>&1
result=$?
echo "$result" > "$evidence/link-exit-code.txt"
if [[ "$result" == 0 ]]; then
  timeout 120s node /spike/pyrogenesis-wasm.js > "$evidence/runtime.log" 2>&1
  echo "$?" > "$evidence/runtime-exit-code.txt"
  tail -30 "$evidence/runtime.log"
fi
tail -15 "$evidence/link.log"
exit 0
