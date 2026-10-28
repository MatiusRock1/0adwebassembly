#!/usr/bin/env bash
set -euo pipefail
mkdir -p /spike/evidence
case "${1:?prepare o configure}" in
    prepare)
        archive=/build/0ad/libraries/source/spidermonkey/mozjs-128.13.0.tar.xz
        printf '6422e51b9e76586c3054127bf13f992ec2338bd2d6156dc430accfb0b5301f1d  %s\n' "$archive" | sha256sum -c -
        cp -a /build/0ad/libraries/source/spidermonkey/patches /spike/patches
        tar -xJf "$archive" -C /spike --exclude=js/src/tests/non262 --exclude=js/src/tests/test262 --exclude=js/src/jit-test --exclude=testing/web-platform
        cd /spike/mozjs-128.13.0
        bash ../patches/patch.sh > /spike/evidence/upstream-patches.log 2>&1
        git -C /build/0ad rev-parse HEAD > /spike/evidence/BASE_COMMIT.txt
        sha256sum "$archive" > /spike/evidence/source.sha256
        (em++ --version; em++ -dumpmachine; rustc --version; cbindgen --version; python3 --version) > /spike/evidence/toolchain.txt
        ;;
    configure)
        cd /spike/mozjs-128.13.0
        export MOZ_NOSPAM=1 MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=none
        export MOZBUILD_STATE_PATH=/spike/mozbuild-state
        export MOZCONFIG=/spike/mozconfig
        cat > "$MOZCONFIG" <<'EOF'
ac_add_options --enable-project=js
ac_add_options --target=wasm32-unknown-emscripten
ac_add_options --disable-shared-js
ac_add_options --disable-jit
ac_add_options --disable-jemalloc
ac_add_options --without-intl-api
ac_add_options --disable-js-shell
ac_add_options --disable-tests
mk_add_options MOZ_OBJDIR=/spike/mozjs-128.13.0/build-wasm
export CC=emcc
export CXX=em++
export AR=emar
export RANLIB=emranlib
export HOST_CC=/usr/bin/gcc
export HOST_CXX=/usr/bin/g++
export HOST_AR=/usr/bin/ar
EOF
        cp "$MOZCONFIG" /spike/evidence/mozconfig
        set +e
        ./mach configure > /spike/evidence/configure.log 2>&1
        result=$?
        set -e
        printf '%s\n' "$result" > /spike/evidence/configure-exit-code.txt
        if [[ "$result" == 0 ]]; then
            printf 'CONFIGURED_ONLY: compilation/runtime not tested\n' > /spike/evidence/status.txt
        else
            printf 'BLOCKED_CONFIGURE: not a successful SpiderMonkey WASM build\n' > /spike/evidence/status.txt
        fi
        cat /spike/evidence/status.txt
        tail -45 /spike/evidence/configure.log
        ;;
    *) exit 1 ;;
esac
