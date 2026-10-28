# Verified compatibility matrix for the headless fixture

| API/service | Actual treatment | Result and scope |
|---|---|---|
| wasm32 triplet/OS/kernel | Emscripten recognition patch in Mozilla | Configure and build succeed |
| Engine ARCH_* | ARCH_WASM32 in a separate copy | Scripting and components compiled without faking another CPU |
| JIT/offthread | JS library compiled with --disable-jit | Script::Context runs its initialization; no native JIT code runs |
| GC/rooting/self-hosted | Initialization, collection and three contexts | Probe passes; the scenario uses MaybeIncrementalGC; does not test heavy loads |
| GC virtual memory | gc/Memory.cpp branches for aligned linear memory reservation | Fixes the MapAlignedPages abort; execution passes |
| JSONPrinter size_t | Upstream overload enabled for __EMSCRIPTEN__ | Build passes; the width of size_t is not changed |
| pthread and Rust | C++ -pthread; std/JSRust with atomics, bulk-memory and mutable-globals | Link and runtime pass; browser not yet validated |
| Thread names | emscripten_set_thread_name | Missing POSIX symbol resolved through a real API |
| abort | Avoid the Unix redefinition under Emscripten | Removes recursion; keeps the fatal diagnostic |
| Promises/JobQueue | RunJobs of the real context | Promise.resolve(9) returns 9 on both targets |
| Game RNG | seed 12345; original Math.random with boost::rand48 | A hundred calls; summary 1658515168 identical |
| Modules/imports | Real hooks and ModuleLoader linked | Imports not exercised; pending for the wider integration |
| Files | --embed-file and the Emscripten FS; reading of the original test.js | Minimal dataset loaded; JS VFS/hotreload not validated |
| Logging/assertions | Console; fatal abort for assertions | Errors are not hidden; diagnostic UI excluded |
| Profiler | Empty adapter for a fixture without UI | Does not measure performance; does not replace the clock or simulation logic |
| madvise | Unsupported syscall warning at start | The fixture passes; behaviour under other loads pending |
| Renderer/terrain/AI/pathfinding/combat/network | Not registered nor run in the component scenario | Out of the test; no compatibility is claimed |
| Final state | Defined snapshot of entities, RNG and promise | Identical JSON and SHA; does not prove universal determinism |

The concrete source graph is in wasm/CMakeLists.txt. Earlier errors and Mozilla patches are in evidence/spidermonkey; the parity native-build/wasm-build logs back the closure of the fixture's link.
