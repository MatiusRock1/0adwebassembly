# Validated toolchain

Code: BASE_COMMIT 40b8794eecb9618da69e10bacffa8814c561aa51. Builds run in Linux directories without spaces inside Docker; Windows/PowerShell host.

| Component | Tested value |
|---|---|
| Ubuntu | 24.04; digest 534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55 |
| SDK image | emscripten/emsdk:4.0.10; digest 90b757eb11fa9a0e3ce4d2d9f76d932a56018e4accc37b5a28b2783751e60eb7 |
| Emscripten | 4.0.10; wasm32-unknown-emscripten |
| Node | 22.16.0 |
| Rust | 1.85.1; target wasm32-unknown-emscripten and rust-src |
| cbindgen | 0.29.0 |
| Python in the image | 3.12.3 |
| Engine C++ | C++20; detailed flags and commands in the parity logs |
| Resources | Two jobs; 8 GiB limit per build container |

The std rebuild uses RUSTC_BOOTSTRAP=1, cargo -Zbuild-std=std,panic_abort, -Cembed-bitcode=yes, atomics/bulk-memory/mutable-globals and panic=abort. It is an experimental configuration of this port. CMake enables C++ exceptions for the final target; failures to export evidence are not mistaken for a successful run.

The evidence files native-packages.tsv, native-source-archives.sha256 and spidermonkey/toolchain.txt record exact versions and checksums. The baseline's local tag is 0ad-wasm-native-baseline:phase1; its original validated image has ID ce7b365c62ba2d732a6cdd1ad38d5ea30dd6edc2d5f3669f594c0c6b4aea2a06.

Recommended runner: docker-phase1.ps1 on Windows or phase1.sh on Linux. The build completes during docker build and the scratch targets export evidence and artifacts; there is no need to run a container to download or compile when the module starts. CommonJS is declared in the output directories to isolate them from type=module at the root.
