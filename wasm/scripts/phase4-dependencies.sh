#!/usr/bin/env bash
set -euo pipefail
export EMCC_CORES=2 BINARYEN_CORES=2
mkdir -p /spike/phase4-deps/src /spike/phase4-deps/prefix
cd /spike/phase4-deps/src
fetch() {
  local dependency_url="$1" dependency_archive="$2" dependency_sha256="$3"
  curl --fail --location --retry 2 "$dependency_url" -o "$dependency_archive"
  printf '%s  %s\n' "$dependency_sha256" "$dependency_archive" | sha256sum --check -
  sha256sum "$dependency_archive" >> ../downloads.sha256
}
fetch https://curl.se/download/curl-8.5.0.tar.xz curl-8.5.0.tar.xz 42ab8db9e20d8290a3b633e7fbb3cec15db34df65fd1015ef8ac1e4723750eeb
tar xf curl-8.5.0.tar.xz
cd curl-8.5.0
emconfigure ./configure --host=wasm32-unknown-emscripten --prefix=/spike/phase4-deps/prefix \
  --disable-shared --enable-static --without-ssl --without-libidn2 --without-libpsl \
  --without-brotli --without-zstd --without-nghttp2 --disable-threaded-resolver \
  --disable-ldap --disable-ldaps CFLAGS='-O2 -pthread' CPPFLAGS='-pthread'
emmake make -j2
emmake make install
cd ..
fetch https://download.libsodium.org/libsodium/releases/old/libsodium-1.0.18.tar.gz libsodium-1.0.18.tar.gz 6f504490b342a4f8a4c4a02fc9b866cbef8622d5df4e5452b46be121e46636c1
tar xf libsodium-1.0.18.tar.gz
cd libsodium-1.0.18
emconfigure ./configure --host=wasm32-unknown-emscripten --prefix=/spike/phase4-deps/prefix \
  --disable-shared --enable-static --disable-asm CFLAGS='-O2 -pthread'
emmake make -j2
emmake make install
cd ..
fetch https://github.com/lsalzman/enet/archive/refs/tags/v1.3.17.tar.gz enet-1.3.17.tar.gz 1e0b4bc0b7127a2d779dd7928f0b31830f5b3dcb7ec9588c5de70033e8d2434a
tar xf enet-1.3.17.tar.gz
cmake -S enet-1.3.17 -B enet-build -DCMAKE_TOOLCHAIN_FILE=/emsdk/upstream/emscripten/cmake/Modules/Platform/Emscripten.cmake \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS='-O2 -pthread' -DCMAKE_INSTALL_PREFIX=/spike/phase4-deps/prefix
cmake --build enet-build -j2
cp enet-build/libenet.a /spike/phase4-deps/prefix/lib/
# Build the SDK's pinned, hash-checked original ICU and Vorbis/Ogg ports.
printf '#include <unicode/uclean.h>\nint main(){UErrorCode e=U_ZERO_ERROR;u_init(&e);return 0;}\n' > ports.cpp
em++ -pthread --use-port=icu --use-port=ogg --use-port=vorbis ports.cpp -o ports.js
echo PHASE4_DEPENDENCIES_BUILT
