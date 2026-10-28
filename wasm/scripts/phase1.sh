#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$project_root"
memory=${WASM_BUILD_MEMORY:-8g}
if ! docker image inspect 0ad-wasm-native-baseline:phase1 >/dev/null 2>&1; then
  docker buildx build --resource "memory=$memory" --build-arg NATIVE_JOBS=2 \
    --target native-final --load -t 0ad-wasm-native-baseline:phase1 \
    -f wasm/docker/native.Dockerfile wasm
fi
docker buildx build --resource "memory=$memory" --build-arg NATIVE_JOBS=2 --target native-evidence \
  --output "type=local,dest=$project_root/docs/wasm/evidence" \
  -f wasm/docker/native.Dockerfile wasm
docker buildx build --resource "memory=$memory" --target phase1-evidence \
  --output "type=local,dest=$project_root/docs/wasm/evidence/spidermonkey" \
  -f wasm/docker/spidermonkey.Dockerfile wasm
test "$(cat docs/wasm/evidence/spidermonkey/parity/status.txt)" = PARITY_PASSED
docker buildx build --resource "memory=$memory" --target phase1-artifacts \
  --output "type=local,dest=$project_root/wasm/dist/headless" \
  -f wasm/docker/spidermonkey.Dockerfile wasm
printf 'Phase 1 headless fixture: native/WASM parity passed.\n'
