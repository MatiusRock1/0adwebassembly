# Phase 3: optimized foundation and fullscreen

Status: completed for the phase 3 scene in Edge on Windows; three final repetitions passed. See [changes and verification](../docs/wasm/phase-3-results.md). Depends on phase 2 evidence. See the [completion and FPS contract](plan-cierre-0ad-webassembly.md). The full match and graphical differences remain assigned to later phases.

## Objective

Turn the existing scene into a stable production foundation and achieve at least 30 sustained FPS at 1080p; retain the same FPS and smoothness as the original 0 A.D. as the optimization target in an equivalent comparison with a real GPU: same machine, pin, scene, camera, resolution, settings, FPS limit and simulation speed. Record the native reference. The operator accepts 30 FPS as the minimum; apply the measurement contract and record the native comparison as a reference.

## Ordered work

1. Reconcile phase 2 reports: focus, exit, zero leftover workers, parity and memory warnings. Record anything still pending, including context loss. Keep the diagnostic build.
2. Create reproducible debug/release configurations. Measure -O2/-O3, LTO and optimization of SpiderMonkey and dependencies, without changing numeric semantics or enabling fast-math that breaks determinism. Keep separate symbols; do not disable checks to hide failures.
3. Instrument CPU by subsystem, ticks, scripting/GC, renderer, presentation and proxy cost. Measure GPU with available capabilities without relying on a mandatory extension. Compare proxied WebGL and context ownership/OffscreenCanvas in the real browser, respecting thread restrictions. Choose based on evidence.
4. Optimize the measured bottleneck: batching, culling, reused buffers, loading outside the frame and minimizing transfers. Evaluate compatible original skinning and shaders. Audit clamp-to-edge, depth/sRGB and reduced features; complete them or record differences for phase 5. Do not change game logic.
5. Integrate fullscreen entry/exit through an explicit gesture, understandable errors, resize, DPR and render scaling. Adapt the viewport, GUI and picking coordinates to the actual canvas. Do not rely on F11. Resolve Esc: it must exit fullscreen without inadvertently destroying the match; offer explicit shutdown. Recover focus and context loss in a controlled way.
6. Start with checks for WebGL 2, isolation/threads and memory; show readable incompatibility messages. Keep the service with correct headers and MIME types, same origin and configurable port.

## Deliverables and acceptance

- [x] Scene release target and repeatable benchmark, with debug/release comparison and identified hardware.
- [x] Fixture/map parity and restoration still pass; same simulation speed.
- [x] Chromium or Edge on Windows with a real GPU: the scene at 1080p sustains at least 30 FPS and p95 <= 33.4 ms under the contract. A second graphics engine is recorded and blockers are visible.
- [x] Ten fullscreen/exit/resize cycles, accurate selection and pause on focus loss; three restarts, zero leftover workers and tested context recovery.
- [x] Report on CPU/GPU/JS/proxy costs and memory; 15 stable minutes without fatal errors.

Performance parity for this scene does not complete the full-match requirement: the comparison with the original will be repeated under real load. If SpiderMonkey without JIT dominates the load, document microprofiles and a mitigation plan before expanding the simulation.

## Common rules

Keep the original engine, scripts and assets from the phase 2 pin; any pin change needs a recorded baseline and migration. Preserve parity, RNG and commands; do not replace systems with mocks. Use only original art with named human authors and provenance. Keep platform changes isolated and reviewable. Local work is authorized; no commits, issues, PRs or automatic publication. Human review is required before submitting changes to the project.

Reuse Docker layers, with two jobs and 8 GiB as the initial build limits. Record logs and progress. Do not install dependencies when starting the game. New script and report names in this plan are proposed deliverables, not commands that are already available. A gate closes only with evidence; do not hide a blocker by reducing scope.
