# Dependencies of the phase 1 headless harness

Scope: scripting, the component manager and the component-ticks-01 scenario. The classifications rest on compilation/link/execution; they do not extend to a full match. The general inventory of POSIX candidates remains in evidence/source-audit.json and is not a call graph.

| Dependency | Class | Version/licence | Evidence and limit |
|---|---|---|---|
| SpiderMonkey | NEEDS_SHIM | 128.13.0+wfg5; source with MPL-2.0 notices; index of upstream MPL/GPL/LGPL libraries | Compile, bindings, GC and contexts pass; exact patches in evidence/spidermonkey |
| ScriptInterface | NEEDS_SHIM | Pin BASE_COMMIT; GPL-2.0-or-later | Nine real units compiled; Engine/Context/Interface/conversions/JobQueue exercised; profiles and logging adapted |
| simulation2 | NEEDS_SHIM | Pin BASE_COMMIT; GPL-2.0-or-later | Selection of test components in ComponentManager; original messages and wrappers; the full set is not registered |
| Boost headers/random | PORTABLE | 1.83.0; Boost Software License 1.0 | The manager's rand48 and Math.random tested with a hundred calls; boost-filesystem is not linked |
| fmt | PORTABLE | 9.1.0; MIT | FMT_HEADER_ONLY; error and log formatting on native/WASM |
| zlib | PORTABLE | Version pinned by the emsdk 4.0.10 port; zlib licence | --use-port=zlib; zlib-port.log and successful link/runtime |
| Rust and std | NEEDS_SHIM | 1.85.1; licences per crate in rust-std-vendor.log, MIT/Apache-2.0 sources according to their manifests | std rebuilt for atomics/bulk-memory/mutable-globals; experimental build-std; checksum of the Mozilla package recorded |
| libxml2/ICU | EXCLUDABLE_IN_HEADLESS for this fixture | libxml2 2.9.14 MIT; ICU headers from the baseline | Headers are used for ParamNode; the fixture does not parse XML nor link the XML/ICU runtimes |
| Strings, UTF-8, CRT, errors | PORTABLE | MIT or GPL-2.0-or-later headers depending on the unit | Original sources CStr, utf8, secure_crt, status and Errors; narrow/wide CRT version |
| VFS/files | NEEDS_SHIM | Pin; licences per unit | Original test.js embedded in the Emscripten FS and read by C++; original loaders linked; JS VFS/hotreload APIs not exercised |
| CPU/OS | NEEDS_SHIM | lib/sysdep/arch.h MIT | ARCH_WASM32 added in the build copy; no x86 CPU or Linux is faked |
| Threads/GC/virtual memory | NEEDS_SHIM | SpiderMonkey/Emscripten | Thread name API adapted; the GC reservation uses linear memory branches; pthread in C++ and Rust compatible |
| Profiling and graphical logger | EXCLUDABLE_IN_HEADLESS | Harness adapters | Logging to the console; empty profiling; fatal assertions and main thread kept |
| Renderer, GL, window, audio, networking | EXCLUDABLE_IN_HEADLESS | Native versions in native-packages.tsv; licences in libraries/LICENSE.txt | Their implementations and match components are not included in the fixture target; this does not imply a port of these libraries |
| Atlas/FCollada/NVTT/gloox/ENet/SDL/curl/sodium | NATIVE or EXCLUDABLE_IN_HEADLESS | native-packages.tsv and libraries/LICENSE.txt | The baseline keeps what is needed for 472 tests; NVTT was compiled for TextureConverter. They are not part of the components selected for WASM |

The original test.js source is used unchanged. No artistic assets were generated. Binary delivery must keep the licences of the project and of SpiderMonkey/third parties; the aggregated licences do not replace the manifests of each Rust dependency.
