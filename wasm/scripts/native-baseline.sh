#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
[[ "$(uname -s)" == Linux ]] || { echo 'Se requiere Linux' >&2; exit 1; }
[[ "$root" != *[[:space:]]* ]] || { echo 'El build upstream rechaza espacios; montar como /src o usar ruta Linux sin espacios.' >&2; exit 1; }
[[ ! -e .git/index.lock && -f .git/index ]] || { echo 'Resolver checkout/indice Git antes del baseline; no eliminar locks automaticamente.' >&2; exit 1; }
[[ "$(git rev-parse HEAD)" == "$(cat BASE_COMMIT.txt)" ]] || { echo 'HEAD no coincide con BASE_COMMIT' >&2; exit 1; }
git diff --quiet HEAD -- source libraries build || { echo 'Fuentes nativas modificadas respecto al pin' >&2; exit 1; }
jobs="${JOBS:-2}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'JOBS debe ser entero positivo' >&2; exit 1; }
mkdir -p wasm/dist
exec > >(tee wasm/dist/native-baseline.log) 2>&1
date -u
uname -a
cat /etc/os-release
cat BASE_COMMIT.txt
c++ --version
python3 --version
git lfs fsck
bash libraries/build-source-libs.sh "-j$jobs"
bash build/workspaces/update-workspaces.sh
make -C build/workspaces/gcc "-j$jobs" config=release
test -x binaries/system/pyrogenesis
test -x binaries/system/test
(cd binaries/system && ./test)
printf 'native-baseline: build and tests OK\n'
