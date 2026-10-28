#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
test -s wasm/dist/smoke.js
test -s wasm/dist/smoke.wasm
node wasm/dist/smoke.js | tee wasm/dist/smoke-run.log
grep -Fx '0ad-wasm: smoke OK' wasm/dist/smoke-run.log >/dev/null
