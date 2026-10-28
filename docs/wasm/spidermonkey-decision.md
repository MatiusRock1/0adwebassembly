> Current status: the integration with ScriptInterface, JobQueue, promises, RNG and 100 ticks of the original kernel has passed the native/WASM comparison. The first sections keep the history; the current result is at the end.

# SpiderMonkey: headless integration and parity verified

Actual version: `128.13.0`, library `mozjs128`, patches `wfg5`, according to `libraries/source/spidermonkey/build.sh`. Its comment about Firefox 115.16.1 is outdated with respect to PV; use PV and verify the downloaded file.

The current `mozconfig` configures a shared library, without jemalloc, Intl, shell or tests. The build runs `mach`, uses vendored packages and also copies `jsrust`. Do not replace this flow with a made-up emconfigure command.

`source/scriptinterface/Context.cpp` explicitly enables Ion, Baseline and off-thread Ion compilation. It also uses incremental GC, self-hosted code, JobQueue and module/promise hooks. `Engine.h` initializes JS; `Interface.cpp` keeps JIT code and bindings. Disabling the JIT in the library also requires reviewing this integration.

Status: configure finished successfully for wasm32-unknown-emscripten with the experimental adjustments described below. The compilation finished with exit code 0 and produced js/src/build/libjs_static.a; the later probe also linked and ran JavaScript in Node, with C++/JS bindings, GC and three contexts. Still to validate: the browser and the 0 A.D. integration. The GO/PIVOT/NO-GO decision is still pending.

## Inspection of the exact package

Downloaded from `https://releases.wildfiregames.com/libs/mozjs-128.13.0.tar.xz`. SHA-256: `6422e51b9e76586c3054127bf13f992ec2338bd2d6156dc430accfb0b5301f1d`. Listing and matches in `evidence/spidermonkey-source-files.txt` and `evidence/spidermonkey-configure-candidates.txt`.

`build/moz.configure/init.configure:606` accepts the wasm32 CPU only when `allow_wasi` is enabled. `toolchain.configure:982` uses that permission for a WASI toolchain. The existence of wasm32 references does not prove general Emscripten support for the JS library.

`js/moz.configure:273` offers `--enable-jit`/`--disable-jit`; `jit_default` enables the JIT by default on a set of native CPUs, without wasm32. The old `--disable-ion`/`--enable-ion` options are explicitly rejected; the spike must use this version's options.

The official wiki consulted from Docker requires Rust >=1.76 and recommends cbindgen 0.29.0. The initial Ubuntu image shipped Rust 1.75.0; it was replaced before the baseline by Rust 1.85.1 and cbindgen 0.29.0. The native toolchain problem is not classified as a WASM architectural blocker.

The native baseline has already passed 472 tests. The configuration experiment without JIT ran as described below. If it compiles, the next step is to evaluate the C++/JS round trip and repeated contexts before deciding GO/PIVOT/NO-GO.

## Configuration experiment that was run

The Dockerfile `wasm/docker/spidermonkey.Dockerfile` uses the exact package and the upstream patches, Emscripten 4.0.10 and Rust 1.85.1. The experimental source is separate from the native checkout. Download, configuration and compilation happen during docker build.

The unchanged configuration rejected the emscripten operating system. The experimental patch adds Emscripten to the OS/kernel constants, to the triplet recognition and to detection through __EMSCRIPTEN__. It does not implement operating system API compatibility.

The target compilers (emcc/em++) were separated from the host compilers (gcc/g++), the Rust target wasm32-unknown-emscripten was installed and the objects directory was placed inside the package, as this configuration flow requires. Configure finished with exit code 0 and Configure complete!.

The evidence is in `evidence/spidermonkey/`: mozconfig, configure.log, configure-exit-code.txt, the package checksum and emscripten-target-recognition.patch. The unmodified and before-rust-target folders keep the earlier failures. The compilation uses two jobs, an 8 GiB memory limit and a 30-minute timeout; its result is recorded separately from the configuration.

Even if a library is produced, it still has to be linked and tested for initialization, JavaScript evaluation, the C++/JS round trip and repeated contexts. A successful configuration alone does not prove the engine's viability in the browser.


## First compilation blockers

The first attempt ended with a non-zero exit code after about seven minutes: zlib.h was missing in vm/Compression.cpp. The spike-zlib stage prepares the official port with emcc --use-port=zlib and checks a minimal executable in Node, during docker build. It keeps the earlier evidence in before-zlib and reuses the compiled objects.

The next attempt hit an ambiguity of JSONPrinter::property for size_t. The upstream implementation already has a size_t overload conditioned on Darwin, OpenBSD and WASI. The experimental patch emscripten-json-size.patch adds __EMSCRIPTEN__ to that guard in JSONPrinter.h and JSONPrinter.cpp. Its compilation result is recorded in build-exit-code.txt and build-status.txt; before-json-size keeps the failure without this adjustment.

Reference for the zlib port: https://emscripten.org/docs/tools_reference/settings_reference.html#use-zlib. The minimal zlib test does not prove that SpiderMonkey runs.

## Verified result

With the zlib port and the size_t overload enabled, mach build finished with exit code 0 and Your build was successful!. BuildKit: 9nz6kfazut0y4ff4kbcrceayb. The last incremental stage took about two minutes. build-status.txt records BUILT_ONLY: linking and JS runtime not yet tested; static-archives.txt lists the produced archives, including js/src/build/libjs_static.a. 62 compiler warnings were kept; they were not suppressed to declare success.

This satisfies the compilation of the experimental library, not the full gate. The next step is to link a probe with JS_Init/JS_NewContext, initialize self-hosted code and evaluate JavaScript with a checkable result; then check bindings and repeated contexts. The game does not yet run its simulation in WebAssembly.

## Execution validation (2026-10-11)

The probe wasm/probes/spidermonkey.cpp initializes JS_Init, JS_NewContext and JS::InitSelfHostedCode, creates a realm and its standard classes and evaluates JavaScript. The JavaScript computes 30 and calls cppDouble, a C++ binding that validates the argument and returns 60. That result is required before and after JS_GC. The cycle repeats with three contexts created and destroyed, followed by JS_ShutDown. The three iterations finished correctly on Node 22.16.0.

To link, the real objects of mfbt, mozglue and memory were added, together with libjsrust and libpure_virtual; libjs_static.a alone does not bring all these supports. C++ had already been compiled with pthread. Rust and its standard library were rebuilt with atomics, bulk-memory, mutable-globals and panic=abort. Rust 1.85.1 is used with rust-src and RUSTC_BOOTSTRAP=1 for the -Zbuild-std=std,panic_abort experiment; its dependencies are obtained with cargo vendor --locked. It is an experimental toolchain, not a statement of upstream support.

The patch emscripten-thread-name.patch uses emscripten_set_thread_name. emscripten-abort.patch avoids redefining abort on Emscripten: that redefinition caused recursion and hid the initial GC failure. emscripten-gc-memory.patch extends the WASI memory branches of gc/Memory.cpp to Emscripten, using aligned reservation and release compatible with linear memory. These changes stay limited to the experimental package inside Docker.

Evidence: runtime-link-exit-code.txt = 0, rust-std-build-exit-code.txt = 0, runtime-exit-code.txt = 0, runtime.log contains three results of 60 and 3 contexts passed. The runtime keeps ASSERTIONS=2. An unsupported syscall: __syscall_madvise warning persists at start; the described test passes, but that warning needs follow-up under real loads.

Reproduction from the project root: powershell -NoProfile -ExecutionPolicy Bypass -File .\wasm\scripts\docker-spidermonkey.ps1. The wrapper requires RUNTIME_PROBE_PASSED; exporting evidence of a failed attempt does not count as success. Downloads, compilation, link and probe execution happen during docker build.

Decision: continue the experimental SpiderMonkey integration, without replacing the runtime yet. This probe does not run ScriptInterface, modules, JobQueue, promises nor 0 A.D. simulation ticks; nor does it validate the browser or prove parity or determinism. Phase 1 stays open.

## Game integration and current decision (2026-10-11)

The CMake target pyrogenesis-wasm compiles the nine original scriptinterface units and the selected component subsystem. The scenario uses Engine, Context, Interface, C++/JS bindings, JobQueue and Promise.resolve(9). CComponentManager sets seed 12345 and evaluates a hundred calls to Math.random.

The simulation calls the original CSimulation2Impl::UpdateComponents through simulation-update.cpp; it includes all its message phases, FlushDestroyedComponents and RunJobs. It uses CCmpTest1A and TestScript2A, loading the upstream test.js without rewriting it. Neither the full game facade nor a map is instantiated; this scenario has no active AI, movement, economy or pathfinding components.

Both builds and runs finished with exit code 0. PARITY_PASSED for a hundred ticks. The final JSON has rng=1658515168, promise=9 and entity values 11100 and 203500. Common SHA-256: ce75b2c80f201e201bf8b8c283fc48d36ad18fbb26bcb2d801c0f7547df04f50. Current evidence: evidence/spidermonkey/parity. Reproduction: wasm/scripts/docker-phase1.ps1 or bash wasm/scripts/phase1.sh; the tests run during docker build.

Technical recommendation: continue with SpiderMonkey for the headless development. The evidence allows moving on, but the architectural approval is up to the operator. Still pending: browser/pthreads, larger loads, modules/imports and the __syscall_madvise warning. The rebuild of Rust std with RUSTC_BOOTSTRAP is still experimental. The remote CI is prepared, not published nor run. The formal closure requires human review and acceptance of the scope, according to the plan and AGENTS.md.
