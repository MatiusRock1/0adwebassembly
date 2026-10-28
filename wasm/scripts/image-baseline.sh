#!/usr/bin/env bash
set -euo pipefail
stage="${1:?Etapa requerida: build o tests}"
cd /build/0ad
exec > >(tee "/evidence/native-$stage.log") 2>&1
date -u
case "$stage" in
    build)
        jobs="${2:-2}"
        [[ "$jobs" =~ ^[1-9][0-9]*$ ]] || exit 1
        # NVTT se mantiene para que la suite de texturas tenga su dependencia.
        bash build/workspaces/update-workspaces.sh --without-atlas --without-audio --without-lobby --without-miniupnpc
        /usr/bin/time -v make -C build/workspaces/gcc "-j$jobs" config=release
        test -x binaries/system/pyrogenesis
        test -x binaries/system/test
        ;;
    tests)
        cd binaries/system
        # Una asercion interactiva no debe dejar el build esperando indefinidamente.
        /usr/bin/time -v timeout --kill-after=30s 20m ./test
        printf 'native-baseline: build and tests OK\n' | tee /evidence/native-success.txt
        ;;
    *) echo "Etapa desconocida: $stage" >&2; exit 1 ;;
esac
