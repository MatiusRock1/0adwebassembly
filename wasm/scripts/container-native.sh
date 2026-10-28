#!/usr/bin/env bash
set -euo pipefail
mkdir -p /evidence
if [[ -f /evidence/native-container.log ]]; then
    cp /evidence/native-container.log "/evidence/native-container-$(date -u +%Y%m%dT%H%M%SZ).log"
fi
exec > >(tee /evidence/native-container.log) 2>&1
date -u
pin="$(cat /host/BASE_COMMIT.txt)"
if [[ ! -d /build/0ad/.git ]]; then
    # Checkout separado: el indice/lock del operador permanece intacto.
    GIT_LFS_SKIP_SMUDGE=1 git clone --no-hardlinks --no-checkout /host /build/0ad
    cd /build/0ad
    git lfs install --local
    GIT_LFS_SKIP_SMUDGE=1 git checkout --detach "$pin"
else
    cd /build/0ad
fi
[[ "$(git rev-parse HEAD)" == "$pin" ]] || { echo 'Pin diferente en volumen persistente' >&2; exit 1; }
mkdir -p /build/lfs/objects
if [[ ! -f /build/lfs/.host-cache-copied ]]; then
    echo 'Copiando cache LFS disponible al volumen Linux...'
    cp -a /host/.git/lfs/objects/. /build/lfs/objects/
    touch /build/lfs/.host-cache-copied
fi
git config lfs.storage /build/lfs
git config lfs.url https://gitea.wildfiregames.com/0ad/0ad.git/info/lfs
echo 'Descargando objetos LFS faltantes del pin...'
GIT_TERMINAL_PROMPT=0 git lfs fetch origin "$pin"
git lfs checkout
git lfs fsck
git lfs ls-files --json > /evidence/lfs-inventory-complete.json
git diff --quiet HEAD -- source libraries build || { echo 'Baseline modificado' >&2; exit 1; }
printf '%s\n' "$pin" > BASE_COMMIT.txt
uname -a
cat /etc/os-release
g++ --version
rustc --version
cargo --version
cbindgen --version
dpkg-query -W > /evidence/native-packages.tsv
jobs="${NATIVE_JOBS:-4}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'NATIVE_JOBS invalido' >&2; exit 1; }
# Baseline Linux del alcance headless; se conservan motor, renderer y tests.
# Flags inspeccionados en el Premake de BASE_COMMIT.
/usr/bin/time -v bash libraries/build-source-libs.sh --without-nvtt "-j$jobs"
find libraries/source -maxdepth 2 -type f \( -name '*.tar.xz' -o -name '*.tar.gz' \) -print0 | sort -z | xargs -0 -r sha256sum > /evidence/native-source-archives.sha256
bash build/workspaces/update-workspaces.sh --without-atlas --without-audio --without-lobby --without-miniupnpc --without-nvtt
/usr/bin/time -v make -C build/workspaces/gcc "-j$jobs" config=release
test -x binaries/system/pyrogenesis
test -x binaries/system/test
(cd binaries/system && /usr/bin/time -v ./test)
printf 'native-baseline: build and tests OK\n' | tee /evidence/native-success.txt
