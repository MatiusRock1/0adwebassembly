#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
command -v em++ >/dev/null || { echo 'Emscripten no disponible' >&2; exit 1; }
command -v node >/dev/null || { echo 'Node no disponible' >&2; exit 1; }
mkdir -p wasm/dist
# El glue predeterminado de Emscripten es CommonJS en Node. Mantener el
# package.json upstream (type=module) y limitar la excepción a los artefactos.
printf '{"type":"commonjs"}\n' > wasm/dist/package.json
exec > >(tee wasm/dist/smoke-build.log) 2>&1
date -u
cat BASE_COMMIT.txt
em++ --version
node --version
em++ wasm/probes/smoke.cpp -O0 -g -sENVIRONMENT=web,node -sASSERTIONS=1 -o wasm/dist/smoke.js
bash wasm/scripts/run-smoke.sh
sha256sum wasm/dist/smoke.js wasm/dist/smoke.wasm > wasm/dist/smoke-sha256.txt
