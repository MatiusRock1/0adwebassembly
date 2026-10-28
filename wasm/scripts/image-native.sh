#!/usr/bin/env bash
set -euo pipefail
stage="${1:?Etapa requerida: dependencies o baseline}"
jobs="${2:-4}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'NATIVE_JOBS invalido' >&2; exit 1; }
cd /build/0ad
mkdir -p /evidence
exec > >(tee "/evidence/native-$stage.log") 2>&1
date -u
[[ "$(git rev-parse HEAD)" == "$(cat /evidence/BASE_COMMIT.txt)" ]]
test -s /evidence/lfs-success.txt
case "$stage" in
    dependencies)
        git diff --quiet HEAD -- source libraries build
        uname -a
        cat /etc/os-release
        g++ --version
        rustc --version
        cargo --version
        cbindgen --version
        dpkg-query -W > /evidence/native-packages.tsv
        /usr/bin/time -v bash libraries/build-source-libs.sh --without-nvtt "-j$jobs"
        find libraries/source -maxdepth 2 -type f \( -name '*.tar.xz' -o -name '*.tar.gz' \) -print0 | sort -z | xargs -0 -r sha256sum > /evidence/native-source-archives.sha256
        ;;
    baseline)
        bash build/workspaces/update-workspaces.sh --without-atlas --without-audio --without-lobby --without-miniupnpc --without-nvtt
        /usr/bin/time -v make -C build/workspaces/gcc "-j$jobs" config=release
        test -x binaries/system/pyrogenesis
        test -x binaries/system/test
        (cd binaries/system && /usr/bin/time -v ./test)
        printf 'native-baseline: build and tests OK\n' | tee /evidence/native-success.txt
        ;;
    *) echo "Etapa desconocida: $stage" >&2; exit 1 ;;
esac
