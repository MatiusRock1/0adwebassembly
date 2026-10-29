> Scope update, 2026-10-11: the operator asks to continue exclusively locally, without commits or publication. The phase 1 technical test passed and allows the phase 2 plan to start. The publication/remote CI requirements mentioned below belong to the earlier scope and do not block local work. The review before submission only applies if it is later decided to submit changes. Current plan: [Phase 2](../../plan/plan-fase-2-0ad-webassembly.md).

# Phase 1: headless evidence and closure status

Date: 2026-10-11. The local technical delivery demonstrates scripting and a real part of simulation2 in WebAssembly with native parity. The formal closure of the plan is still pending human review, publication of the changes and the remote CI run. It is not presented as a playable game nor as a port of the whole simulation.

## Verified results

| Requirement | Result | Evidence |
|---|---|---|
| Pinned baseline | 40b8794eecb9618da69e10bacffa8814c561aa51; separate Linux checkout hydrated with LFS | BASE_COMMIT.txt, evidence/lfs-inventory-complete.json, evidence/lfs-success.txt |
| Linux engine and tests | 472 tests, exit code 0 | evidence/native-build.log, evidence/native-tests.log |
| WASM toolchain | Emscripten 4.0.10, Node 22.16.0; direct and CMake smoke tests pass | toolchain.md; wasm/dist/smoke* |
| Real utility | hash_combine from source/lib/hash.h, four vectors normalized to 32 bits match | wasm/dist/hash-native.txt and hash-wasm.txt |
| SpiderMonkey | 128.13.0+wfg5 configures, compiles, links and evaluates JS; bindings, GC and three contexts pass | evidence/spidermonkey/runtime.log, runtime-status.txt |
| Game scripting | The nine scriptinterface units compile; the harness runs Engine, Context, Interface, conversions, bindings and JobQueue | evidence/spidermonkey/headless and parity |
| Real simulation2 | Original CComponentManager, CSimContext, C++ components and JS wrappers; 100 turns with the original kernel CSimulation2Impl::UpdateComponents | wasm/harness/simulation.cpp; parity/*state.json |
| Parity | Linux and WASM: builds and execution with exit code 0; identical JSON | parity/status.txt = PARITY_PASSED, state.sha256 |
| Automation | CMake, docker-phase1.ps1 and phase1.sh; manual GitHub Actions workflow prepared | wasm/CMakeLists.txt, .github/workflows/wasm-phase1.yml |

The final state fields are:

```json
{"scenario":"component-ticks-01","seed":12345,"ticks":100,"rng":1658515168,"promise":9,"entities":[{"id":2,"x":11100},{"id":3,"x":203500}]}
```

SHA-256 of both JSON files, including their final newline: ce75b2c80f201e201bf8b8c283fc48d36ad18fbb26bcb2d801c0f7547df04f50. It was pinned after running both binaries.

## What the scenario runs

The harness loads binaries/data/mods/_test.sim/simulation/components/test.js without rewriting it. CComponentManager registers only the selected test components; it keeps the original IDs. It creates entity 2 with CCmpTest1A and entity 3 with TestScript2A. Each turn calls the original kernel CSimulation2Impl::UpdateComponents with fixed::FromInt(25), through wasm/harness/simulation-update.cpp. Its TurnStart, Update, MotionFormation, MotionUnit and Final phases run, along with the cleanup of destroyed components and RunJobs. It runs RunJobs and MaybeIncrementalGC. It evaluates Math.random a hundred times with the RNG that Interface binds to the manager's boost::rand48, seeded with 12345, and compares an integer summary of those calls. It also checks Promise.resolve(9) through the game's JobQueue.

The test covers an authentic part of the component simulation, equivalent to the pattern of the upstream test test_script_basic. It runs the original update kernel; it does not instantiate the full CSimulation2::Update facade, does not load a map and does not run movement, pathfinding, combat, economy nor all the game components. Its parity demonstrates the defined scenario, not universal determinism of matches. This difference in scope must be accepted explicitly before closing every item of the original plan.

## Build and adapters

All costly steps happen during docker build. The CMake target pyrogenesis-wasm includes the real scripting and simulation2 sources; the native target pyrogenesis-headless uses the same sources, scenario and component selection. The full baseline of 472 tests stays separate and validated.

The experimental copy adds ARCH_WASM32 detection and limits component registration to the tests. Registration of the VFS JS APIs is excluded, because the harness loads the dataset from C++; the game's loaders and conversions are not replaced. The original file is added with --embed-file into the Emscripten FS. The original implementations of strings, UTF-8, errors, CRT, ParamNode, messages and serialization needed for the link are kept.

The adapters in wasm/harness/adapters replace only graphical profiles with empty operations and logging with the console. platform.cpp keeps the fatal assertions and detects the main thread through pthread. No entities, messages, RNG or component logic are simulated. Details of the SpiderMonkey patches are in spidermonkey-decision.md.

## Reproduction and delivery

From PowerShell, at the root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\wasm\scripts\docker-phase1.ps1
```

On Linux with Docker/BuildKit:

```bash
bash wasm/scripts/phase1.sh
```

Defaults: two jobs and 8 GiB per build container. The native image is built if missing; the cache avoids repeating SpiderMonkey and the engine. The runner checks PARITY_PASSED and the artifact export also requires that status. A stage that only exports failure logs does not equal success.

Local artifacts: wasm/dist/headless/pyrogenesis-wasm.js, .wasm, the Linux binary and its JS library, the original dataset, BASE_COMMIT.txt and SHA256SUMS. The CommonJS outputs are isolated from the root's ESM package.json. The artifacts are ignored by Git. The exported package takes about 27.5 MB after stripping debug symbols from the native copies. The build runs that copy again and compares its JSON before exporting it. SHA256SUMS excludes its own file.

The manual CI uses a dedicated Linux runner with Docker and a persistent cache. The workflow is prepared for GitHub Actions with a self-hosted runner; it has not been run remotely. The upload uses actions/upload-artifact. Review the runner and actions before enabling it.

## Limitations and decision

Technical recommendation: GO to keep developing the headless port and the bridge to the browser, keeping SpiderMonkey. It is not an automatic approval of phase 2 nor a closure of the full DoD. Still needed: review the scenario's scope and the facade adapters, review the patches, publish and run the CI, and approve the architectural decision.

The unsupported syscall: __syscall_madvise warning persists when the module starts; the test passes with ASSERTIONS=2. Browser/pthreads, modules/imports, long loads, consumption under large scenarios and determinism of other components have not been validated. The Rust toolchain uses an experimental rebuild of std with RUSTC_BOOTSTRAP=1.

The original Windows checkout keeps .git/index missing and an empty .git/index.lock; it was not repaired and the user's changes were not discarded. The validated baseline is the separate Linux checkout of the pin. AGENTS.md requires human review before submitting changes and forbids the agent from creating commits, issues or PRs. There was no automatic publication.

## Docker cleanup

The intermediate tags/images 0ad-spidermonkey-built:phase1, 0ad-spidermonkey-zlib:phase1, 0ad-spidermonkey-spike-tools:phase1 and 0ad-wasm-native-checkout:phase1 were removed. Total image size dropped from 28.38 to 24.75 GB according to docker system df. The native baseline and Emscripten are kept to reproduce the delivery, as well as MongoDB/Redis, unrelated to this project. No volumes nor the needed work cache were deleted.

## Final kernel check (2026-10-11)

BuildKit xtana81w4cbbefbqf8kimass7: parity stage completed in 129.7 seconds. The four compile and run exit codes are 0, PARITY_PASSED and the hash ce75b2c80f201e201bf8b8c283fc48d36ad18fbb26bcb2d801c0f7547df04f50 matches on both platforms. Packaging verified: chw1gr11k7urrz5veiq6kpkh7. CMake includes the original CmpPtr.cpp to resolve the kernel's queries. The old manual simulation-link stage was removed; the reproducible simulation link is done with CMake.
