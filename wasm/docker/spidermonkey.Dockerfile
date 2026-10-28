FROM emscripten/emsdk:4.0.10@sha256:90b757eb11fa9a0e3ce4d2d9f76d932a56018e4accc37b5a28b2783751e60eb7 AS sdk
FROM 0ad-wasm-native-baseline:phase1 AS spike-tools
COPY --from=sdk /emsdk/ /emsdk/
ENV EMSDK=/emsdk EM_CONFIG=/emsdk/.emscripten
ENV PATH="/emsdk/upstream/emscripten:/emsdk/node/22.16.0_64bit/bin:${PATH}"
WORKDIR /spike
COPY scripts/spidermonkey-spike.sh /opt/wasm/spidermonkey-spike.sh
RUN bash /opt/wasm/spidermonkey-spike.sh prepare

FROM spike-tools AS spike-experiment
# Los fallos experimentales quedan registrados, no son exito de SpiderMonkey.
RUN bash /opt/wasm/spidermonkey-spike.sh configure

FROM spike-experiment AS spike-target-recognition
COPY scripts/spidermonkey-target-patch.py /opt/wasm/spidermonkey-target-patch.py
RUN mkdir -p /spike/evidence/unmodified \
    && cp /spike/evidence/configure.log /spike/evidence/configure-exit-code.txt /spike/evidence/status.txt /spike/evidence/unmodified/ \
    && python3 /opt/wasm/spidermonkey-target-patch.py \
    && bash /opt/wasm/spidermonkey-spike.sh configure

FROM spike-target-recognition AS spike-rust-target
RUN mkdir -p /spike/evidence/before-rust-target \
    && cp /spike/evidence/configure.log /spike/evidence/configure-exit-code.txt /spike/evidence/status.txt /spike/evidence/before-rust-target/ \
    && rustup target add --toolchain 1.85.1 wasm32-unknown-emscripten \
    && bash /opt/wasm/spidermonkey-spike.sh configure

FROM spike-rust-target AS spike-build
COPY scripts/spidermonkey-build.sh /opt/wasm/spidermonkey-build.sh
RUN bash /opt/wasm/spidermonkey-build.sh

FROM spike-build AS spike-zlib
RUN mkdir -p /spike/evidence/before-zlib \
    && cp /spike/evidence/build.log /spike/evidence/build-exit-code.txt /spike/evidence/build-status.txt /spike/evidence/before-zlib/ \
    && printf '#include <zlib.h>\nint main(void) { return ZLIB_VERSION[0] == 0; }\n' > /spike/zlib-probe.c \
    && emcc --use-port=zlib /spike/zlib-probe.c -o /spike/zlib-probe.js > /spike/evidence/zlib-port.log 2>&1 \
    && node /spike/zlib-probe.js \
    && bash /opt/wasm/spidermonkey-build.sh

FROM spike-zlib AS spike-json-size
COPY scripts/spidermonkey-json-patch.py /opt/wasm/spidermonkey-json-patch.py
RUN mkdir -p /spike/evidence/before-json-size \
    && cp /spike/evidence/build.log /spike/evidence/build-exit-code.txt /spike/evidence/build-status.txt /spike/evidence/before-json-size/ \
    && python3 /opt/wasm/spidermonkey-json-patch.py \
    && bash /opt/wasm/spidermonkey-build.sh

FROM scratch AS spike-evidence
COPY --from=spike-json-size /spike/evidence/ /

FROM scratch AS spike-configure-evidence
COPY --from=spike-rust-target /spike/evidence/ /

FROM scratch AS spike-unmodified-evidence
COPY --from=spike-experiment /spike/evidence/ /



FROM spike-json-size AS spike-threads
COPY scripts/spidermonkey-thread-patch.py /opt/wasm/spidermonkey-thread-patch.py
RUN python3 /opt/wasm/spidermonkey-thread-patch.py \
    && RUSTFLAGS="-Ctarget-feature=+atomics -Ctarget-feature=+bulk-memory -Ctarget-feature=+mutable-globals -Cpanic=abort" bash /opt/wasm/spidermonkey-build.sh

FROM spike-threads AS spike-rust-std
RUN rustup component add --toolchain 1.85.1 rust-src \
    && cd /tmp \
    && RUSTC_BOOTSTRAP=1 cargo vendor --locked --versioned-dirs --manifest-path /opt/rustup/toolchains/1.85.1-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/library/Cargo.toml /spike/rust-std-vendor > /spike/evidence/rust-std-vendor.log 2>&1 || { cat /spike/evidence/rust-std-vendor.log; exit 1; } \
    && cp -a /spike/rust-std-vendor/. /spike/mozjs-128.13.0/third_party/rust/ \
    && cd /spike/mozjs-128.13.0/build-wasm \
    && (RUSTC_BOOTSTRAP=1 gmake -C js/src/rust force-cargo-library-build -j2 CARGOFLAGS="-Zbuild-std=std,panic_abort" RUSTFLAGS="-Cembed-bitcode=yes -Ctarget-feature=+atomics -Ctarget-feature=+bulk-memory -Ctarget-feature=+mutable-globals -Cpanic=abort" > /spike/evidence/rust-std-build.log 2>&1; echo $? > /spike/evidence/rust-std-build-exit-code.txt) \
    && tail -40 /spike/evidence/rust-std-build.log

FROM spike-rust-std AS spike-abort
COPY scripts/spidermonkey-abort-patch.py /opt/wasm/spidermonkey-abort-patch.py
RUN python3 /opt/wasm/spidermonkey-abort-patch.py \
    && gmake -C /spike/mozjs-128.13.0/build-wasm/memory/mozalloc -j2 > /spike/evidence/abort-build.log 2>&1

FROM spike-abort AS spike-gc-memory
COPY scripts/spidermonkey-memory-patch.py /opt/wasm/spidermonkey-memory-patch.py
RUN python3 /opt/wasm/spidermonkey-memory-patch.py \
    && gmake -C /spike/mozjs-128.13.0/build-wasm/js/src/gc -j2 > /spike/evidence/gc-memory-build.log 2>&1 \
    && gmake -C /spike/mozjs-128.13.0/build-wasm/js/src/build -j2 >> /spike/evidence/gc-memory-build.log 2>&1

FROM spike-gc-memory AS spike-runtime
COPY probes/spidermonkey.cpp /spike/spidermonkey.cpp
COPY scripts/spidermonkey-runtime.sh /opt/wasm/spidermonkey-runtime.sh
RUN bash /opt/wasm/spidermonkey-runtime.sh

FROM scratch AS spike-runtime-evidence
COPY --from=spike-runtime /spike/evidence/ /












FROM spike-gc-memory AS headless-build
COPY scripts/headless-build.sh /opt/wasm/headless-build.sh
COPY harness/adapters /spike/headless/adapters
COPY harness/platform.cpp /spike/headless-platform.cpp
RUN bash /opt/wasm/headless-build.sh

FROM scratch AS headless-evidence
COPY --from=headless-build /spike/evidence/ /


FROM headless-build AS headless-link
COPY harness/main.cpp /spike/headless-main.cpp
COPY scripts/headless-link.sh /opt/wasm/headless-link.sh
RUN bash /opt/wasm/headless-link.sh

FROM scratch AS headless-link-evidence
COPY --from=headless-link /spike/evidence/ /



FROM headless-build AS simulation-build
COPY scripts/simulation-build.sh /opt/wasm/simulation-build.sh
RUN bash /opt/wasm/simulation-build.sh

FROM scratch AS simulation-evidence
COPY --from=simulation-build /spike/evidence/ /


FROM simulation-build AS headless-parity
COPY CMakeLists.txt /spike/wasm/CMakeLists.txt
COPY probes /spike/wasm/probes
COPY harness/simulation.cpp harness/simulation-update.cpp harness/platform.cpp /spike/wasm/harness/
COPY harness/adapters /spike/wasm/harness/adapters
COPY scripts/headless-parity.sh /opt/wasm/headless-parity.sh
RUN bash /opt/wasm/headless-parity.sh

FROM scratch AS phase1-evidence
COPY --from=headless-parity /spike/evidence/ /


FROM headless-parity AS phase1-package
RUN test "$(cat /spike/evidence/parity/status.txt)" = PARITY_PASSED \
    && mkdir -p /spike/artifacts/native /spike/artifacts/scenario \
    && cp /spike/parity-wasm/pyrogenesis-wasm* /spike/artifacts/ \
    && cp /spike/parity-native/pyrogenesis-headless /spike/artifacts/native/ \
    && cp /build/0ad/libraries/source/spidermonkey/lib/libmozjs128-release.so /spike/artifacts/native/ \
    && cp /build/0ad/binaries/data/mods/_test.sim/simulation/components/test.js /spike/artifacts/scenario/ \
    && strip --strip-debug /spike/artifacts/native/pyrogenesis-headless /spike/artifacts/native/libmozjs128-release.so \
    && LD_LIBRARY_PATH=/spike/artifacts/native /spike/artifacts/native/pyrogenesis-headless /spike/artifacts/scenario/test.js > /spike/artifacts/native-state.json \
    && cmp /spike/artifacts/native-state.json /spike/evidence/parity/native-state.json \
    && cp /spike/evidence/BASE_COMMIT.txt /spike/artifacts/ \
    && printf '{"type":"commonjs"}\n' > /spike/artifacts/package.json \
    && cd /spike/artifacts && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS

FROM scratch AS phase1-artifacts
COPY --from=phase1-package /spike/artifacts/ /

# Browser remains separate from the Node/CommonJS regression target.
FROM headless-parity AS browser-build
COPY harness/browser-main.cpp /spike/wasm/harness/
COPY scripts/browser-build.sh /opt/wasm/browser-build.sh
RUN test "$(cat /spike/evidence/parity/status.txt)" = PARITY_PASSED \
    && bash /opt/wasm/browser-build.sh

FROM browser-build AS browser-package
COPY browser /spike/browser/
RUN cd /spike/browser && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS

FROM scratch AS browser-artifacts
COPY --from=browser-package /spike/browser/ /

FROM 0ad-wasm-native-baseline:phase1 AS native-map-reference
COPY scenarios/pathfinding-terrain-01.json /opt/scenario.json
COPY scripts/native-map-reference.py /opt/native-map-reference.py
RUN python3 /opt/native-map-reference.py || { test -f /spike/native-map/status.txt || echo NATIVE_MAP_FAILED > /spike/native-map/status.txt; }

FROM scratch AS native-map-artifacts
COPY --from=native-map-reference /spike/native-map/ /

FROM headless-parity AS phase2-audit
COPY scripts/phase2-audit.py /opt/phase2-audit.py
RUN python3 /opt/phase2-audit.py

FROM scratch AS phase2-audit-evidence
COPY --from=phase2-audit /spike/phase2-audit/ /

FROM phase2-audit AS phase2-link-probe
COPY harness/map-link.cpp /spike/wasm/harness/map-link.cpp
COPY scripts/phase2-link-probe.py /opt/phase2-link-probe.py
RUN python3 /opt/phase2-link-probe.py

FROM phase2-link-probe AS phase2-link-details
COPY scripts/phase2-link-details.py /opt/phase2-link-details.py
RUN python3 /opt/phase2-link-details.py

FROM scratch AS phase2-link-evidence
COPY --from=phase2-link-details /spike/phase2-link/*.log /
COPY --from=phase2-link-details /spike/phase2-link/*.txt /
COPY --from=phase2-link-details /spike/phase2-link/report.json /

FROM phase2-link-details AS phase2-foundation
COPY scripts/phase2-foundation.py /opt/phase2-foundation.py
RUN python3 /opt/phase2-foundation.py

FROM scratch AS phase2-foundation-evidence
COPY --from=phase2-foundation /spike/phase2-link/*.log /
COPY --from=phase2-foundation /spike/phase2-link/report.json /

FROM phase2-foundation AS phase2-terrain
COPY scripts/phase2-terrain.py /opt/phase2-terrain.py
RUN python3 /opt/phase2-terrain.py

FROM scratch AS phase2-terrain-evidence
COPY --from=phase2-terrain /spike/phase2-link/*.log /
COPY --from=phase2-terrain /spike/phase2-link/report.json /

FROM phase2-terrain AS phase2-services
COPY scripts/phase2-services.py /opt/phase2-services.py
RUN python3 /opt/phase2-services.py

FROM scratch AS phase2-services-evidence
COPY --from=phase2-services /spike/phase2-link/*.log /
COPY --from=phase2-services /spike/phase2-link/report.json /

FROM phase2-services AS phase2-actors
COPY scripts/phase2-actors.py /opt/phase2-actors.py
RUN python3 /opt/phase2-actors.py

FROM scratch AS phase2-actors-evidence
COPY --from=phase2-actors /spike/phase2-link/*.log /
COPY --from=phase2-actors /spike/phase2-link/report.json /

# Match the baseline libxml2 API; verify upstream archive before compiling.
FROM phase2-actors AS phase2-xml
RUN curl --fail --location --retry 2 --connect-timeout 15 --max-time 90 https://deb.debian.org/debian/pool/main/libx/libxml2/libxml2_2.9.14+dfsg.orig.tar.xz -o /spike/libxml2.tar.xz \
 && echo '4fe913dec8b1ab89d13b489b419a8203176ea39e931eaa0d25b17eafb9c279e9  /spike/libxml2.tar.xz' | sha256sum -c - \
 && tar -xf /spike/libxml2.tar.xz -C /spike \
 && cd /spike/libxml2-2.9.14 \
 && cp /usr/share/misc/config.sub ./config.sub \
 && CFLAGS='-O2 -pthread -fexceptions' emconfigure ./configure --host=wasm32-unknown-emscripten --prefix=/spike/xml-wasm --disable-shared --enable-static --without-python --without-http --without-ftp --without-lzma --without-iconv --without-readline --without-zlib > /spike/xml-configure.log 2>&1 || { cat /spike/xml-configure.log; exit 1; } \
 && emmake make -j2 > /spike/xml-build.log 2>&1 || { tail -50 /spike/xml-build.log; exit 1; } \
 && emmake make install > /spike/xml-install.log 2>&1

FROM phase2-xml AS phase2-support
COPY harness/scene-platform.cpp /spike/wasm/harness/
COPY scripts/phase2-support.py /opt/phase2-support.py
RUN python3 /opt/phase2-support.py

FROM scratch AS phase2-support-evidence
COPY --from=phase2-support /spike/phase2-link/*.log /
COPY --from=phase2-support /spike/phase2-link/report.json /
COPY --from=phase2-support /spike/xml-*.log /

FROM phase2-support AS phase2-closure
COPY scripts/phase2-closure.py /opt/phase2-closure.py
RUN python3 /opt/phase2-closure.py

FROM scratch AS phase2-closure-evidence
COPY --from=phase2-closure /spike/phase2-link/*.log /
COPY --from=phase2-closure /spike/phase2-link/report.json /

FROM phase2-closure AS phase2-map
COPY harness/map-main.cpp /spike/wasm/harness/
COPY scripts/phase2-map.py /opt/phase2-map.py
RUN python3 /opt/phase2-map.py

FROM scratch AS phase2-map-evidence
COPY --from=phase2-map /spike/phase2-link/*.log /
COPY --from=phase2-map /spike/phase2-link/report.json /

FROM phase2-map AS phase2-camera
COPY harness/map-node-pre.js /spike/wasm/harness/
COPY harness/scene-platform.cpp /spike/wasm/harness/
COPY scripts/phase2-camera.py /opt/phase2-camera.py
RUN python3 /opt/phase2-camera.py

FROM scratch AS phase2-camera-evidence
COPY --from=phase2-camera /spike/phase2-link/*.log /
COPY --from=phase2-camera /spike/phase2-link/report.json /

FROM phase2-camera AS phase2-map-run
COPY --from=native-map-reference /spike/native-map/commands.txt /scenario/commands.txt
RUN mkdir -p /output /cache /data \
 && ln -s /build/0ad/binaries/data/mods/mod /data/mod \
 && ln -s /build/0ad/binaries/data/mods/public /data/public \
 && test -f /spike/phase2-link/map-replay.js \
 && (timeout 180 node /spike/phase2-link/map-replay.js > /spike/phase2-link/map-run.log 2>&1; echo $? > /spike/phase2-link/map-run-exit.txt)

FROM scratch AS phase2-map-run-evidence
COPY --from=phase2-map-run /spike/phase2-link/*.log /
COPY --from=phase2-map-run /spike/phase2-link/*.txt /
COPY --from=phase2-map-run /spike/phase2-link/report.json /
COPY --from=phase2-map-run /output/ /states/

FROM phase2-map-run AS phase2-browser-map
COPY scripts/phase2-browser-map.py /opt/phase2-browser-map.py
RUN python3 /opt/phase2-browser-map.py

FROM phase2-browser-map AS phase2-browser-map-package
COPY browser/map.html browser/map.mjs /spike/map-browser/
COPY --from=native-map-reference /spike/native-map/native-checkpoints.json /spike/map-browser/native-checkpoints.json

FROM scratch AS phase2-browser-map-artifacts
COPY --from=phase2-browser-map-package /spike/map-browser/ /

FROM phase2-camera AS phase2-gl
COPY harness/gl-main.cpp /spike/wasm/harness/
COPY scripts/phase2-gl.py /opt/phase2-gl.py
RUN python3 /opt/phase2-gl.py

FROM scratch AS phase2-gl-evidence
COPY --from=phase2-gl /spike/phase2-link/*.log /
COPY --from=phase2-gl /spike/phase2-link/report.json /

FROM scratch AS phase2-gl-artifacts
COPY --from=phase2-gl /spike/phase2-link/pyrogenesis-gl.mjs /
COPY --from=phase2-gl /spike/phase2-link/pyrogenesis-gl.wasm /

FROM phase2-gl AS phase2-scene-build
COPY harness/scene-probe.cpp /spike/wasm/harness/scene-main.cpp
COPY scripts/phase2-scene-build.py /opt/phase2-scene-build.py
RUN python3 /opt/phase2-scene-build.py

FROM phase2-scene-build AS phase2-scene-runtime
COPY harness/scene-main.cpp /spike/wasm/harness/
COPY scripts/phase2-scene-runtime.py /opt/phase2-scene-runtime.py
COPY scripts/scene-player-colors.py /opt/scene-player-colors.py
RUN python3 /opt/scene-player-colors.py /spike/phase2-source /spike/scene-player-colors.patch \
    && python3 /opt/phase2-scene-runtime.py

FROM scratch AS phase2-scene-evidence
COPY --from=phase2-scene-runtime /spike/phase2-link/*.log /
COPY --from=phase2-scene-runtime /spike/phase2-link/report.json /
COPY --from=phase2-scene-runtime /spike/phase2-link/renderer-explicit-* /
COPY --from=phase2-scene-runtime /spike/phase2-link/scene-platform.patch /

FROM 0ad-wasm-native-baseline:phase1 AS phase2-native-assets
COPY scripts/prepare-scene-assets.py /opt/prepare-scene-assets.py
RUN python3 /opt/prepare-scene-assets.py || { cat /spike/scene-assets/missing.json; test ! -f /spike/scene-assets/native-conversion.log || tail -40 /spike/scene-assets/native-conversion.log; exit 1; }

FROM scratch AS phase2-native-assets-evidence
COPY --from=phase2-native-assets /spike/scene-assets/input-manifest.json /
COPY --from=phase2-native-assets /spike/scene-assets/missing.json /
COPY --from=phase2-native-assets /spike/scene-assets/native-conversion.log /
COPY --from=phase2-native-assets /spike/scene-assets/conversion-exit.txt /

FROM phase2-scene-runtime AS phase2-scene-package
COPY browser/scene.html browser/scene.mjs /spike/scene-browser/
COPY --from=phase2-browser-map /spike/minimum-data/ /spike/scene-data/
COPY --from=phase2-native-assets /spike/scene-assets/prepared/ /spike/scene-data/public/
COPY --from=native-map-reference /spike/native-map/commands.txt /scenario/commands.txt
COPY scripts/phase2-scene-package.py /opt/phase2-scene-package.py
RUN python3 /opt/phase2-scene-package.py

FROM scratch AS phase2-scene-artifacts
COPY --from=phase2-scene-package /spike/scene-browser/ /


FROM phase2-map-run AS phase2-map-restore
COPY harness/map-restore-main.cpp /spike/wasm/harness/
COPY scripts/phase2-map-restore.py /opt/phase2-map-restore.py
RUN python3 /opt/phase2-map-restore.py

FROM scratch AS phase2-map-restore-evidence
COPY --from=phase2-map-restore /spike/phase2-link/restore-*.log /
COPY --from=phase2-map-restore /spike/phase2-link/restore-result.json /

# Isolated profile rebuilds retain the diagnostic phase2 target and cached assets.
FROM phase2-scene-package AS phase3-profile
ARG SCENE_PROFILE=debug
ARG SCENE_CONTEXT=proxied
ENV SCENE_PROFILE=${SCENE_PROFILE}
ENV SCENE_CONTEXT=${SCENE_CONTEXT}
COPY scripts/phase3-profile.py /opt/phase3-profile.py
COPY scripts/scene_benchmark_contract.py /opt/scene_benchmark_contract.py
COPY harness/scene-script-timing.h /spike/wasm/harness/
RUN python3 /opt/phase3-profile.py

FROM scratch AS phase3-scene-artifacts
COPY --from=phase3-profile /spike/scene-browser/ /

FROM phase3-profile AS phase3-parity
COPY harness/map-main.cpp harness/map-restore-main.cpp /spike/wasm/harness/
COPY --from=native-map-reference /spike/native-map/ /reference/
COPY scripts/phase3-parity.py /opt/phase3-parity.py
RUN python3 /opt/phase3-parity.py || { cat /spike/phase3-parity/*.log; exit 1; }

FROM scratch AS phase3-parity-evidence
COPY --from=phase3-parity /spike/phase3-parity/*.log /
COPY --from=phase3-parity /spike/phase3-parity/result.json /
