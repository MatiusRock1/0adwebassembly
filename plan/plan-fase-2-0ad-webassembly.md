# 0 A.D. → WebAssembly — Phase 2: browser and first interactive scene

Date: 2026-10-11.

**Status:** in implementation. Milestones A and B verified in Linux/Docker; WebGL 2 backend and renderer initialized. Milestone C pending interactive scene and sustained test. Current evidence: `docs/wasm/phase-2-results.md`.
**Working mode:** entirely local, in this folder, with Docker and browser. No commits, publication, external services or remote CI required.
**Final project objective:** run 0 A.D. in the browser while preserving its original engine, scripts and assets.
**Result of this phase:** open a localhost URL and run a 0 A.D. scene with map, terrain, units, camera, selection and a movement order processed by the original simulation.

## 1. Why we can proceed

Phase 1 succeeded for the tested technical scope:

| Existing evidence | Result |
|---|---|
| Linux baseline | 472 tests pass |
| Emscripten | 4.0.10 pinned; smoke and CMake executed |
| SpiderMonkey | Experimental 128.13.0+wfg5; JS/C++, GC and three contexts pass |
| Game integration | Original Engine, Context, Interface, bindings, JobQueue and promises |
| Simulation | 100 calls to the original CSimulation2Impl::UpdateComponents kernel |
| Native/WASM comparison | PARITY_PASSED; four exit codes of 0 |
| Final state | rng=1658515168, promise=9, entities with x=11100 and x=203500 |
| JSON SHA-256 | ce75b2c80f201e201bf8b8c283fc48d36ad18fbb26bcb2d801c0f7547df04f50 |
| Exported artifact | Also run with Node on Windows; checksums verified; about 27.5 MB |

Evidence sources: `docs/wasm/phase-1-results.md`, `docs/wasm/spidermonkey-decision.md` and `docs/wasm/evidence/spidermonkey/parity/`.

This demonstrates the selected component scenario, not a full match. The CSimulation2 facade, maps, renderer, pathfinding, AI and browser remain unvalidated. The existing harness must not be renamed as the complete game.

**Working decision:** continue with SpiderMonkey and pin `40b8794eecb9618da69e10bacffa8814c561aa51`. The operator's request authorizes local progress. For this work, it supersedes the initial plan's publication/remote CI requirements; it does not claim those actions occurred. The human review required by AGENTS.md before submitting changes still applies if submission is chosen in the future.

## 2. Scope and visible success

At completion, the operator must be able to:

1. Build or reuse artifacts through a PowerShell script.
2. Start a local server and open the indicated URL.
3. See loading progress and an understandable error if a browser capability is missing.
4. Load a small pinned map, with original terrain and units.
5. Move the camera, select a unit and order it to move.
6. See its position change through authentic game commands, movement and pathfinding.
7. Pause/resume and restart the scene without reloading dependencies or blocking the tab.
8. Consult the test summary and compare the same scenario with the native binary.

The scene will be a functional vertical slice of the engine. Full menus, economy, combat, opponent AI, full audio, saved games and multiplayer will be completed later; they are not needed to declare this scene complete. A static image, a WebGL cube or units moved from page JavaScript do not satisfy the result.

## 3. Implementation and resource rules

- Reuse the native image, SDK and already compiled SpiderMonkey layers. Change final layers before invalidating expensive dependencies.
- Downloads, dependency preparation, compilation and packaging happen during `docker build`. At container runtime, only serve files and run prepared checks. The browser loads assets from the local server.
- Keep two jobs and 8 GiB per build container as default limits. Do not automatically use all cores.
- Record duration, memory and disk. Show progress by stage and a heartbeat when a long build emits no lines; keep the full log in files.
- Preserve headless targets as regression tests. Browser changes must not change their reference JSON.
- Keep native and WASM on the same pin, dataset and functional changes. Do not modify or automatically repair the Windows checkout's Git index.
- Use original assets with licenses and provenance. Do not generate art or download a complete asset package when the minimal scenario suffices.
- Keep platform changes isolated; do not replace entity logic, scripting, RNG, commands, movement or pathfinding with mocks.
- Set timing targets after measuring the first real case. Do not promise cold build time or FPS before evidence exists.

## 4. Milestone A — The verified scenario runs in the browser

**Highest priority:** resolve browser/pthreads before expanding the renderer.

### A1. Export and local server

- Create a separate browser target from the existing Node/CommonJS target. Do not directly load Node output as an ES module.
- Prepare a small HTML/JS bootstrap that initializes the module, shows logs and receives the result. Do not create an alternative game UI.
- Serve `.wasm` with `application/wasm`; serve JS, workers and data from the same origin.
- The server must send `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp`.
- Check `crossOriginIsolated` and `SharedArrayBuffer` at startup. Do not open through `file://` or use a simple server that omits those headers.

The current library requires pthreads. Emscripten documentation requires COOP/COEP isolation to use them in the browser: [Pthreads support](https://emscripten.org/docs/porting/pthreads.html). Do not assume one binary can fall back to execution without threads.

### A2. Threads, startup and loop

- Validate a small worker pool, initially two; measure actual need before expanding it.
- Test the current scenario with the application thread separated from the UI through `PROXY_TO_PTHREAD`, if engine calls permit.
- Verify engine main-thread initialization, JS/GC and destruction. Do not confuse the application's main thread with the page thread.
- Avoid blocking waits on the UI. Investigate callbacks and browser operation proxies before adding Asyncify or changing architecture.
- Keep assertions and record the `__syscall_madvise` warning. Determine whether it needs a legitimate adaptation or is an optional optimization; do not silence it to pass the milestone.
- Run the 100 ticks with seed 12345 and obtain exactly the phase 1 JSON/hash.
- Repeat load/run/destruction ten times and check for abandoned workers and sustained memory growth.

**Gate A:** identical native/Node/browser comparison; responsive browser; ten cycles without fatal failures. Archive browser version, headers, console and results. Validate installed Chromium/Edge first and then a second available browser engine; record anything untested.

## 5. Milestone B — Simulation of a real map

### B1. Replace the test component selection

- Audit dependencies for constructing a real CSimulation2 and its initialization sequence.
- Compile the original interfaces/components required by a minimal map, preserving IDs and registration order.
- Restore VFS and JS reading APIs currently excluded by the harness. Mount configuration, scripts, templates and map files before starting simulation.
- Use the existing dummy backend where appropriate for the native/headless case; isolate visual services without replacing game logic.
- Remove direct inclusion of `Simulation2.cpp` from the adapter when integrating that unit and the facade through the normal build. Avoid compiling it twice.
- Test modules/imports if loaded scripts use them, JS roots, conversions and real serialization. ModuleLoader linking today does not demonstrate working imports.

### B2. Small, reproducible dataset

- Select an existing scenario map in the pin, small and with simple terrain; do not initially rely on random generation.
- Fix name/path, checksum, seed, players and initial entities in a manifest. Choose the specific map after inspecting available assets.
- Obtain the file dependency closure required by its scripts/templates and record missing files with their original paths. Do not patch data to hide dependencies.
- Create a minimal package with a manifest of files, sizes, hashes and licenses. Preload it before entering synchronous VFS flow.
- Separate scripts/templates from textures/models so the headless case does not need to download visual assets.
- Prepare necessary textures and caches during the build using original tools where compatible. Do not require NVTT in the browser if content can be prepared beforehand.

### B3. Commands and parity

- Run an initial 100 ticks and then 1,000 ticks on the same map with fixed seed and inputs.
- Inject a valid movement order through the original command queue for a unit defined in the manifest and at a specific tick.
- Enable the movement/pathfinding needed to execute that order. Do not change positions manually in the harness.
- Define a canonical state with sorted IDs, positions represented without rounding that hides differences, owner and relevant simulation fields. Document which state is compared and what is excluded.
- Compare native, Node and browser at checkpoints, not just at the end. If they differ, locate the first tick and component before expanding the scenario.
- Review original serialization/deserialization and compare state after restoration when the subsystem is available; do not claim saved-game support based only on that test.

**Gate B:** map loaded through original APIs, order processed and real movement; compared states match. Keep the small phase 1 test alongside this new reference. Fix a new hash only after the runs.

## 6. Milestone C — Original renderer and interactive scene

### C1. Chosen graphics path

The pin contains `source/renderer/backend/gl/Device.cpp`, SDL context creation and `CONFIG2_GLES` branches, in addition to the dummy backend. Premake also supports `CONFIG2_GLES=1`. This offers a path to investigate OpenGL ES → WebGL 2; it does not prove full renderer compatibility.

- Audit SDL, GLAD, extensions, shaders, texture formats, framebuffer, buffers and queries used by the scenario.
- Create a WebGL 2 context through the chosen real integration and test the original GL/GLES backend.
- Verify the pin's SDL version and compatibility with the port available in Emscripten 4.0.10 before choosing flags. Do not replace libraries with arbitrary versions.
- Test link options requiring WebGL 2 and the GLES path, after checking their behavior in the pinned SDK.
- Compile game shaders through that path and record every failure. Do not assume desktop OpenGL translates automatically.
- Keep Vulkan out of the initial browser target. Evaluate a new WebGPU backend only if WebGL 2 shows a specific blocker, with documented cost.

Emscripten distinguishes the portable OpenGL ES subset from emulation paths: [OpenGL support](https://emscripten.org/docs/porting/multimedia_and_graphics/OpenGL-support.html). Validate effective browser capabilities and use original assets prepared for them.

### C2. Scene and assets

- First graphics step: clear and basic drawing through the engine backend, only as a diagnostic.
- Then load original terrain, camera, a model and textures through the game's graphics/renderer classes.
- Expand to the milestone B map and units, with water, shadows and advanced effects disabled through legitimate options until the basic path is validated.
- Add each capability separately and maintain an inventory of reduced options. A reduced visual option must not change the simulation result.
- Manage resize, canvas size and display scale; handle context loss with a diagnostic and recovery or controlled restart.

### C3. Main loop and interaction

- Adapt the loop to browser callbacks and allow returning control between frames; separate simulation ticks from rendering/interpolation.
- Keep a fixed simulation step, per-frame catch-up limit and explicit pause/hidden-tab policy.
- Resolve where the GL context resides relative to the simulation worker; verify actual proxy or OffscreenCanvas support before choosing that integration.
- Integrate keyboard/mouse through engine paths: camera, picking/selection and movement orders to the game queue.
- Use a direct startup scene and minimal controls for this milestone; the full GUI remains for the next phase.

The blocking native loop must adapt to the browser environment: [Emscripten Runtime Environment](https://emscripten.org/docs/porting/emscripten-runtime-environment.html). Specific flags and functions will be validated against 4.0.10; consulted documentation pages may describe later versions.

**Gate C:** original terrain and units visible, working camera and selection, movement click changes state through the original simulation and the tab stays responsive. Pause and restart work. Save screenshot, console and command/position check; a screenshot alone does not validate interaction.

## 7. Proposed structure and local execution

Proposed new paths; this plan does not create them:

```text
wasm/browser/                       # bootstrap and local page
wasm/harness/browser-main.cpp       # incremental engine integration
wasm/scenarios/                     # reproducible manifests and inputs
wasm/scripts/docker-phase2.ps1      # build/export, two jobs and 8 GiB
wasm/scripts/serve-phase2.ps1       # serves package with correct headers
wasm/scripts/phase2.sh              # local Linux equivalent
wasm/docker/phase2.Dockerfile       # final layers over existing dependencies
wasm/dist/browser/                 # generated output, ignored by Git
docs/wasm/phase-2-results.md
docs/wasm/browser-compatibility.md
docs/wasm/renderer-webgl2.md
docs/wasm/evidence/phase2/           # logs, states, metrics and screenshots
```

Do not promise command names that have not been implemented. Once available, document the exact build command, server command and URL. Separate persistent logs from the IDE's limited output.

## 8. Ordered backlog

| ID | Work | Depends on | Exit criterion |
|---|---|---|---|
| WASM-201 | Reconfirm reference and package browser target | Phase 1 | Current test preserved and browser package generated |
| WASM-202 | Local server, headers and workers | 201 | Correct isolation and loading |
| WASM-203 | SpiderMonkey and 100 ticks in browser | 202 | Gate A |
| WASM-204 | VFS, scripts/templates and CSimulation2 | 203 | Real initialization without test-only selection |
| WASM-205 | Minimal map dataset | 204 | Complete manifest, native and WASM loading |
| WASM-206 | Movement/pathfinding and expanded parity | 205 | Gate B |
| WASM-207 | SDL/GLAD/GLES and shaders | 203 | Original backend initializes in WebGL 2 |
| WASM-208 | Terrain, models and camera | 206, 207 | Real scene visible |
| WASM-209 | Loop, inputs, selection and commands | 208 | Gate C |
| WASM-210 | Restarts, metrics and local delivery | 209 | DoD and reproducible report |

Follow this order by default. Do not start another heavy build simultaneously if the current one already consumes the machine's budget.

## 9. Verification, performance and blockers

- Milestone A: ten fixture cycles and parity with phase 1.
- Milestone B: canonical states at documented intervals, movement test and equivalent native reference.
- Milestone C: fifteen-minute interactive session, three restarts, pause/resume, resize and focus loss; no crash or unexplained sustained memory growth.
- Measure time to usable scene, loaded bytes, peak WASM memory, workers, tick and frame time on the operator's machine. Report graphics capabilities and visual configuration.
- If there is a functional regression, repeat relevant native tests. The full baseline already passed 472 tests; do not rebuild it for every HTML change.
- Validate at least the operator's primary browser; record a second browser as verified or pending with its reason.

| Risk | Response before continuing |
|---|---|
| Pthreads/UI deadlock | Reduce to a small reproduction; review pool/proxy and waits; keep logs |
| GC or madvise fails under load | Validate memory contract; compare with native; do not hide aborts |
| VFS waits for assets that have not arrived | Explicit preload and manifest; do not return dummy files |
| Unsupported shader/extension | Identify usage and a portable renderer alternative; document reduced option |
| Parity diverges | Stop expansion; locate first differing tick/field |
| Excessive memory or disk | Limit dataset, jobs and workers; reuse layers; clean only replaceable project artifacts |
| WebGL 2 blocks an essential feature | Record reproducible blocker and evaluate adaptation/backend; do not declare the scene achieved |

There is no fixed duration estimate: the dependency closure of the full simulation and renderer still needs measurement. Every blocker ends in a verifiable fix or a concrete report with options, not a declaration of success.

## 10. Local Definition of Done

- [ ] Gate A: original fixture passes in the browser with pthreads and parity.
- [ ] Gate B: minimal map, original commands and movement pass in native/WASM.
- [ ] Gate C: WebGL 2 scene with terrain/units, camera, selection and movement.
- [ ] Responsive loop, pause and restart verified.
- [ ] Minimal assets, licenses and hashes recorded.
- [ ] Repeatable build and server through local scripts; no dependency installation at startup.
- [ ] Phase 1 tests retain their result.
- [ ] Metrics, versions, reduced options and limitations documented.
- [ ] Operator can open and test the local scene following the report.

No commit, fork publication or remote CI required. **Successful phase 2** means the engine runs the defined interactive scene in the browser; it does not mean all 0 A.D. features have been ported.

## 11. Path to a 0 A.D. match

| Stage | Expected result | Evidence to proceed |
|---|---|---|
| Phase 1 — technically achieved | Real headless scripting and ticks | Existing fixture parity |
| Phase 2 — this plan | Interactive map and units in browser | Gates A, B and C |
| Phase 3 — first local match | Game GUI, match loading, resources, construction, production, combat, basic AI and audio | Play a small skirmish through victory/defeat with original logic |
| Phase 4 — sustained use | Save/load, asset packages, performance and more maps/civilizations | Restore match and long sessions without regressions |
| Phase 5 — remaining features | Multiplayer and completion of platform differences | Compatible transport, synchronization and validated feature matrix |

The first objective of “playable 0 A.D.” is reached by verifying the phase 3 skirmish. Porting the entire game also requires completing remaining features; multiplayer will need transport and original protocol compatibility investigation. It will be planned with evidence when local mode works.

**First implementation action:** create the milestone A browser target and isolated server, running the already known test before adding map and renderer.
