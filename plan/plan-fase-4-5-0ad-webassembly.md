# Phase 4.5: renderer migration to WebGPU

Date: 2026-10-14. Updated: 2026-10-25. Status: in progress; performance target reached in short captures, full acceptance pending. Operator decision of 2026-10-25: the FPS gate is the 30 FPS lock (mean ≥ 29.5 displayed FPS, physical p95 ≤ two refreshes; see the [closure plan](plan-cierre-0ad-webassembly.md)). Candidate `cushion-1` meets it in combat (29.92 FPS, p95 33.41 ms) and skirmish (29.99 FPS) in short captures; the 3 × 900 s battery per workload, which closes the gate, has not run yet ([continuation of 25 October](../docs/wasm/phase-4-5-continuation-2026-10-25.md)). See [results and limits](../docs/wasm/phase-4-5-results.md). Receives the phase 4 build and evidence, including pending work moved by the operator; does not require passing those items before migration. Precedes phase 5. Apply the [performance and completion contract](plan-cierre-0ad-webassembly.md); run the moved acceptance tests after WebGPU integration.

Operator instruction of 2026-10-15: avoid Computer Use and separate measurements from desktop screenshots. Operator update of 2026-10-17: run the tests and continue until finished. The standalone runners in `wasm/scripts/run-phase4-5-offline.ps1` run through the CLI; they automate the visible fullscreen button and verify the window, focus and presentation. The operator does not have to launch the tests. Plan mode does not open windows or use the GPU. Preparing runners does not approve gates: they remain pending until actual evidence is preserved and reviewed. Resolution, workload, duration and FPS requirements remain unchanged.

Operator update of 2026-10-17: prioritize resolving performance and
reaching at least 30 physical FPS before tests unrelated to that problem.
Later, the operator requested documentation and a pause to continue afterward. See the
[exact continuation point](../docs/wasm/phase-4-5-pause-2026-10-17.md).
Operator resumption of 2026-10-18: the snapshot was checked, the asynchronous
queue was run and deferred audio maintenance was measured. Best
current diagnostic: 37.20 physical FPS, but p95 of 66.74 ms and 116 pauses longer
than 100 ms: smoothness still fails. The measured candidate removes synchronous
per-frame queries through shared health and cached backbuffer metadata,
and defers replay flushing until after recording the frame
on the CPU. The Mozilla D224656 dispatch adaptation for the interpreter
is being prepared; its CPU probes pass, but it does not resolve p95. The mapped
upload pool does not improve presentation either (35.52 physical FPS, although 40.98 engine
FPS). Fragmented submission with FIFO consumption did not improve presentation either
(35.12 FPS). Direct copying into the packet reached 35.58 physical FPS / 41.56 engine
FPS with p95 of 66.79 ms; another attempt with the same binary aborted due to an
out-of-bounds memory access in SpiderMonkey and its cause remains unproven. Extended
property and GC probes pass; the switch variant also passes with active
incremental GC. Delivering each Present in a separate RAF callback worsened
the average to 32.20 FPS without resolving p95 and was withdrawn, keeping its code and
evidence. Skipping identical uniforms within the same packet passed 32,768
differential draws, but measured 35.50 FPS / p95 66.79 ms without physical improvement;
it was also withdrawn with its code preserved. Direct copying reduces the
self time of UploadBufferRegion from 3.84 to 1.17 s in separate profiles, but
stutters persist. The limited Mozilla D224676 adaptation for calls with
omitted arguments passed 21 CPU checks, including incremental GC, but
measured 34.83 physical FPS with p95 of 66.81 ms; it was withdrawn from the active candidate.
Asynchronous texture submission preserves order and bytes in CPU and GPU probes;
it measured 35.78 FPS without resolving pauses and remains experimental.
The application was rebuilt separately with native WASM exceptions and
compatible longjmp, without changing workload or graphics. CPU runtime probes,
the 482 C++ units, linking and the dependency audit passed;
its diagnostic measured 35.23 physical FPS and p95 of 66.79 ms, without improvement.
The subsequent profile points to audio waits; the next candidate shares
only the AL error word. 15 CPU checks per mode against the SDK pass;
it retains the 482 verified native objects and adds one platform object.
Its diagnostic measured 37.20 physical FPS / 43.63 engine FPS, with real audio active,
exact probes and clean shutdown, but physical p95 of 66.74 ms. The problem remains
open. Analysis associates stutters with simulation turns. The profile
confirmed the alGetError wait disappeared, but IsPlaying still waits.
Moving that maintenance after Present submission measured 32.97 FPS / p95
66.78 ms and was withdrawn. Private interpreter counters compiled
to identify slow paths; they will not be used for FPS acceptance.
Performance remains the priority and the phase stays open.
The experiment with audio checks in the worker passed its CPU checks and
real playback controls, but measured 34.33 FPS / p95 66.85 ms; it is not
adopted as a fix. The operator paused on the 18th at 23:04 America/Bogota:
no active tests or builds, and no new VM handlers implemented.
The [current pause snapshot](../docs/wasm/phase-4-5-pause-2026-10-18.md)
records package identity, evidence and the next investigation point.
On the 19th, three private VM handlers and focused probes were added: the control
passed 30 checks and incremental GC. The candidate build
stopped due to another operator pause at 16:15; it is not yet validated and there are
no new physical measurements. The [current snapshot from the 19th](../docs/wasm/phase-4-5-pause-2026-10-19.md)
records exactly how to continue; do not run while the pause remains in effect.
The pause document preserves the historical status from the 17th; the
[continuation point from the 18th](../docs/wasm/phase-4-5-continuation-2026-10-18.md)
and results record the current candidate and steps.

## Mandatory order: migration, then phase 4 pending work

Operator update: 2026-10-14. Pending items listed in phase 4 move to this phase and stop being prerequisites for starting WebGPU. The move does not approve them.

First integrate the WebGPU backend and shaders needed to run menus and the original match. During integration, technical startup, resource, shader and error checks are allowed. **After completing that integration**, run the following functional and performance acceptance on WebGPU, before adopting the backend and closing phase 4.5:

- [x] Verify single/multiple selection, groups, camera, minimap, rally points and mouse/keyboard orders in the visible browser. Evidence: `docs/wasm/evidence/phase4-5/chrome-validation-pointer-3/original-input/report.json`; capture across three monitors: `multimonitor-pointer-7/report.json`.
- [ ] Complete combat with casualties, building capture and ownership changes, victory/defeat, summary and return to menu; check relevant animations and effects.
- [x] Compare research and trade with the native game using complete checkpoints and original command traces. Evidence: `native-advanced-serialized-1/report.json` and `webgpu-advanced-serialized-o2-1/report.json`, ten complete checkpoints up to 780,000 ms and original trade. Revalidate if another VM variant is adopted; historical WebGL gaps remain in the results.
- [ ] Repeat final visible tests of gesture-enabled audio, volume/mute and persistent settings; complete three consecutive matches, pause/resume and shutdown without abandoned resources or workers.
- [ ] Resolve the performance blocker preserved from the WebGL baseline: skirmish and combat with fixed workloads, three 900-second measurements per workload after 120 seconds of warmup, at least 30 displayed FPS and p95 <= 33.4 ms in each repetition, without simulation slowdown or growing backlog. Compare with native on the same machine and conditions.
- [ ] Complete a continuous 60-minute session and record stability, memory, input and workers.

These items complement the gates below; they do not duplicate runs when a single test provides sufficient evidence for both. The WebGL baseline may retain failed results: it does not have to pass before migration or repeat full acceptance as a prerequisite. Keep hashes, settings, manifests and evidence limitations so the comparison is traceable.

## Objective

Run the original match through a WebGPU backend integrated into the engine renderer, preserving GUI, content, simulation, AI, audio and behavior. Adopt WebGPU as the main browser backend when it passes this phase's gates; keep WebGL as a reference and explicit compatibility alternative.

WebGPU allows requesting a high-performance adapter, but does not guarantee selecting the dedicated GPU. Migration alone does not demonstrate an FPS improvement either: both matters require adapter information and actual measurements.

## Baseline and initial decisions

- Keep pin `40b8794eecb9618da69e10bacffa8814c561aa51`, original assets and match manifests. Record any toolchain change separately from the game pin.
- Freeze a reproducible phase 4 WebGL build, with hashes, settings, screenshots, commands, checkpoints and performance. Maintain an equivalent native baseline on the same machine.
- Inventory `source/renderer/backend`: device interfaces, command context, buffers, textures, framebuffer, shaders, pipelines and swap chain. Reuse the existing abstraction and study the Vulkan backend as a reference for explicit resources and commands; Vulkan does not run directly inside the page.
- Pin Emscripten, WebGPU bindings and shader tool versions. Evaluate Emdawnwebgpu against the existing toolchain through verifiable compilation and execution; do not assume compatibility from matching API names.
- Define the matrix of browsers, adapters, limits, formats and required features. Optional capabilities must have a verified equivalent path or an explicit limitation.

## Ordered work

1. **Startup and backend selection.** Detect WebGPU in a secure context and keep COOP/COEP for WASM threads. Request adapter and device asynchronously, query features/limits and present understandable errors. Offer WebGPU/WebGL and a high-performance preference before creating the context. The current launcher creates WebGL on startup: separate that path to avoid creating a WebGL context on the canvas intended for WebGPU. Switching backend requires a controlled restart or recreation of the canvas and its resources. Show the backend and adapter information the browser permits, without claiming that the preference guarantees a dedicated GPU.

2. **Device ownership and threads.** Test where adapter, device, canvas and queue reside in the current pthread architecture. Evaluate worker/OffscreenCanvas use according to actual support. Maintain clear ownership and batch commands and transfers; measure WASM/JS and thread crossings. Preserve the original CGame loop, events, GUI and audio, with orderly initialization and destruction. A minimal probe establishes only API access.

3. **Engine backend.** Implement WebGPU through existing interfaces: resources and usages, partial uploads, alignment, uniform/storage buffers, bind groups, samplers, pipelines and render passes. Resolve lifetimes of in-flight resources, resize and attachment reconstruction; configure presentation, color, depth and stencil. Integrate selection into the build and device creation, without introducing dummy GL calls to fake compatibility.

4. **Original shaders.** Inventory effects, defines, variants and bindings used by GUI, terrain, models, animation, shadows, water, particles, silhouettes and postprocessing. Prepare a reproducible path to WGSL, through validated offline translation or shader code adaptation. Pin tool versions, licenses and hashes; record unconverted variants. Check layouts, precision, matrices, orientation, depth, blending, alpha and color spaces. Restore shadow filtering and comparison equivalent to the original, with screenshots where shadows exist and look as expected; compiling without errors is insufficient. Keep original artistic assets and their provenance intact.

5. **Visual and functional integration.** Walk through menu, options, loading, HUD and full match. Test selection, groups, minimap, rally points, commands, animations and effects with the new renderer. Compare paired screenshots with WebGL and native using identical seeds, camera, tick, quality and resolution. Define tolerances per effect before evaluating differences; review shadow edges, transparency, fog/LOS, text and colors. Repeat complete checkpoints and command traces to confirm that changing the renderer does not alter simulation or RNG.

6. **Errors and recovery.** Record validation and memory errors, error scopes, device loss and exit reason. Test resize/DPR, fullscreen, minimize/restore, suspension, device loss and startup without WebGPU. Recover resources from the original VFS where feasible; if restart is required, preserve persistent data and communicate it. Do not silently substitute WebGL for WebGPU during an acceptance test. Verifiably close resources, pending jobs and workers.

7. **Profiling and optimization.** Compare WebGPU, WebGL and native on the same declared workloads and hardware. Measure CPU, command preparation/submission, transfers, pipeline compilation, memory, ticks, backlog and displayed frames. Measure GPU when the adapter supports the necessary queries, recording availability; GPU timestamps do not replace presentation measurements. Optimize the observed bottleneck. Evaluate batching, pipeline caching and compute skinning after preserving parity; keep an equivalent path where optional features are unavailable. Do not lower resolution, quality, population or simulation speed to pass.

8. **Adoption and documentation.** After passing the gates, set WebGPU as default on verified platforms and keep WebGL selectable. Document requirements, tested adapters, differences and recovery. Record results in `docs/wasm/phase-4-5-results.md`, evidence in `docs/wasm/evidence/phase4-5/` and a feature matrix per backend. These are proposed deliverables, not already implemented files or capabilities.

## Deliverables and acceptance

- [ ] Reproducible WebGPU build, pinned dependencies and actual backend selection; no need to install tools or download compilers when starting the game.
- [ ] Adapter, features/limits and effective backend recorded; WebGPU absence and GPU preference handled without false promises or hidden fallback.
- [ ] Original GUI and match against AI from menu through victory/defeat, summary and return to menu with correct audio and input.
- [ ] Shader and effect matrix covered for phase 4 scope; visual differences against WebGL/native justified and reviewed. No missing effect counts as an optimization.
- [ ] Matching complete checkpoints and commands between native, WebGL and WebGPU with the same seeds and simulation settings.
- [ ] Three consecutive matches, pause, real 1080p fullscreen through the visible button and shutdown without abandoned resources/workers. Verify window, canvas, attachments, DPR and input coordinates.
- [ ] Skirmish with AI and at least 200 active entities, and visible combat with at least 200 units, according to manifests fixed before measurement. Three 900-second repetitions after 120 seconds of warmup per workload: displayed average >= 30 FPS and p95 frame interval <= 33.4 ms in each repetition, without slowing simulation or accumulating backlog.
- [ ] WebGPU/WebGL/native comparison on the same machine, resolution and quality; presented FPS, p99, 1% low, stutters, memory and workers recorded. Any regression is quantified and resolved or explicitly accepted by the operator before closure; improvement is not assumed.
- [ ] 60-minute session and device loss, resize, suspension/restoration and error tests without corrupting persistent data.
- [ ] Main WebGPU backend enabled only on approved platforms; usage instructions and WebGL alternative verified.

Additional phase 5 features and workloads remain pending until their own tests. This phase does not establish save/replay, multiplayer or overall game completion.

## Test execution

Respect the operator's current preference: game tests must be visible on their desktop and use the fullscreen button. Check the Windows instance and session before measuring; `headless=false`, element fullscreen or an isolated 1080p framebuffer do not establish that the operator can see the window. If the operator takes over manual testing, deliver the build, steps and result capture without the agent starting matches on its own. Keep verifiable logs and measurements of tests actually performed.

## Common rules

Keep the original engine, scripts and assets; preserve parity, RNG and commands. Do not replace systems with mocks or generate artistic assets. Shader code changes are renderer adaptations, traceable to their original sources. Local work is authorized; no commits, commit messages, issues, PRs or automatic publication. Human review is required before submitting changes to the project.

Reuse Docker layers, with two jobs and 8 GiB as initial build limits. Record logs and progress. This phase's authorization allows planning the backend change without first requiring proof of a WebGL blocker; it does not authorize marking its results or those of phase 4 as passed.

## Technical references

- [WebGPU: adapters, devices, resources and device loss](https://www.w3.org/TR/webgpu/).
- [WGSL: WebGPU shader language](https://www.w3.org/TR/WGSL/).
- [Emscripten: WebGPU integration through Emdawnwebgpu](https://emscripten.org/docs/porting/multimedia_and_graphics/WebGPU-support.html). Check documentation for the pinned version before choosing bindings and build options.
