#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
mkdir -p wasm/dist
case "${1:?native o wasm}" in
    native)
        g++ -std=c++20 -O0 -Isource wasm/probes/hash-combine.cpp -o wasm/dist/hash-native
        wasm/dist/hash-native > wasm/dist/hash-native.txt
        cat wasm/dist/hash-native.txt
        ;;
    wasm)
        printf '{"type":"commonjs"}\n' > wasm/dist/package.json
        em++ -std=c++20 -O0 -Isource wasm/probes/hash-combine.cpp -sENVIRONMENT=web,node -sASSERTIONS=1 -o wasm/dist/hash-wasm.js
        node wasm/dist/hash-wasm.js > wasm/dist/hash-wasm.txt
        diff -u wasm/dist/hash-native.txt wasm/dist/hash-wasm.txt
        cat wasm/dist/hash-wasm.txt
        sha256sum wasm/dist/hash-wasm.js wasm/dist/hash-wasm.wasm > wasm/dist/hash-wasm.sha256
        ;;
    *) exit 1 ;;
esac
