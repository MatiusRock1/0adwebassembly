# Completion roadmap: complete 0 A.D. in the browser

Date: 2026-10-12. Status: requested implementation plan; subsequent phases pending.

## Required final result

Open a local URL, enter fullscreen through a user action and play 0 A.D. with the original GUI, economy, construction, production, combat, AI, audio, maps and civilizations from the pinned official package, save/load, replays and multiplayer. Minimum performance accepted by the operator: 30 sustained FPS at 1080p, without slowing the simulation. Matching the original native game's FPS and smoothness remains the optimization target in equivalent scenarios. A scene, a menu or a partial match does not constitute delivery of the complete game.

## Actual starting point

[Phase 2 results](../docs/wasm/phase-2-results.md): original simulation with parity, a map with 37 entities, terrain/models, selection and movement, state restoration and a 900-second test. The final focus/worker shutdown check is listed separately and must be reconciled before expanding the target. There are differences between the historical phase 2 plan status and the report: verifiable evidence takes precedence; do not mark pending items as passed.

The approximately 2 FPS come from Linux/Docker with SwiftShader and a diagnostic build. They neither establish nor rule out 30–60 FPS with a real GPU. Full features are missing and several graphical capabilities are reduced. The specific test map license remains pending before redistribution.

## Sequence and dependencies

| Phase | Document | Result and gate |
|---|---|---|
| 3 | [Optimized foundation and fullscreen](plan-fase-3-0ad-webassembly.md) | Real hardware, reproducible measurements, stable renderer and fullscreen; scene with 30 sustained FPS at 1080p |
| 4 | [Full local match](plan-fase-4-0ad-webassembly.md) | Local WebGL integration and preserved evidence; pending functional and performance work moved to phase 4.5 by the operator |
| 4.5 | [Migration to WebGPU](plan-fase-4-5-0ad-webassembly.md) | Engine WebGPU backend, visual and simulation parity, stability and performance compared with WebGL/native |
| 5 | [Content, persistence and stability](plan-fase-5-0ad-webassembly.md) | Official content, save/load/replay, long sessions and performance under load |
| 6 | [Multiplayer and remaining features](plan-fase-6-0ad-webassembly.md) | Real transport, determinism between clients and completed feature matrix |
| 7 | [Delivery and overall completion](plan-fase-7-0ad-webassembly.md) | Clean installation, local port, fullscreen, functional audit and performance passed |

Follow 3 -> 4 -> 4.5 -> 5 -> 6 -> 7. Phase 4.5 was added at the operator's request on 2026-10-14; it does not close phase 4. Profiling and performance regressions continue throughout all phases, including the backend migration. Phase 3 does not establish match performance; later phases measure it again under real load. Do not set dates without measuring costs and resolving blockers from the previous phase.

Operator update of 2026-10-14: pending controls, combat/capture/victory, research/trade parity, audio/persistence/three-match regressions, performance and the 60-minute session move from phase 4 to phase 4.5. They run after WebGPU integration and before phase 4.5 closes. They do not block starting the migration; the acceptance contract remains and no pending test is considered passed.

## Common performance contract

Before optimizing, record CPU, GPU and driver, RAM, OS, browser/version, power, internal and display resolution, DPR, settings, pin and build hashes. Test on the operator's Windows with effective hardware acceleration; a software renderer is diagnostic only. Define minimum and recommended machines from measurements, without inventing specifications.

Compare each hardware profile with the original on that same machine: internal 1920x1080 and the same documented settings, GPU, driver, power plan and FPS/vsync limit. The pinned original configuration has adaptivefps.session = 60 and vsync = false; this defines the default limit, not actual FPS. If testing a different limit or resolution, apply it to both. Fullscreen at higher resolutions may use explicit scaling visible in settings; do not lower resolution, quality or entities to pass. The authorized minimum is 30 sustained FPS; the native comparison informs optimization opportunities.

Use a reproducible replay or command sequence and separately measure a real interactive run. Proposed suite: phase 2 scene; 2-player skirmish with AI and 200 active entities; 4-player match with 3 AI and 600 active entities; visible combat with 200 units; map with water/effects; late game and the most demanding supported map. Fix paths, seeds, population, total entities, commands and camera in manifests before measuring. These counts are proposed acceptance workloads, not already verified capabilities. If the official limit allows a larger load, include it and declare the supported limit; do not call the FPS target universal.

After two minutes of warmup, measure 15 minutes per scenario, three repetitions without DevTools and a 60-minute match session. Record frames actually presented, mean/median, p95/p99 percentiles of frame intervals, 1% low with a documented formula, pauses >100 ms, tick time, backlog, GC, input, memory and workers. Do not count timer callbacks as rendered frames; repeated frames without drawing do not count either.

Gate: at least 30 average FPS actually displayed and p95 frame interval <= 33.4 ms in each of three complete repetitions at 1080p. **Operator decision of 2026-10-25:** the web build is locked at 30 FPS, so the FPS gate is that lock: a displayed mean of at least 29.5 FPS (a hard 30 FPS cap cannot exceed 30.0, and one late frame puts the mean below it) and a physical p95 of at most two measured display refreshes (33.4 ms at 60 Hz). Record median, p99, 1% low, long pauses and variation between repetitions; these indicators describe smoothness without hiding stutters. Matching the original is an optimization target, not an acceptance blocker after the operator's decision of 2026-10-12. Do not sustain FPS by slowing the simulation: correct game speed, no growing tick backlog and preserved parity. A reduced scene does not establish full-match performance.

If the minimum is not reached, locate CPU/JS/GC, GPU, transfers or command submission costs; optimize the measured bottleneck and repeat. Migration to WebGPU is expressly authorized in phase 4.5 and retains this contract, without promising improvement or forcing the dedicated GPU. Other backend or runtime changes require a demonstrated blocker, a decision and compatibility tests.

## Completion without hidden pending work

Maintain a matrix for each native game feature: present, adapted and verified, or blocked. Local matches, multiplayer and official content are mandatory. Platform/mod/lobby features need an explicit decision with testing or operator acceptance; they must not disappear from the matrix because they are difficult. Each phase produces docs/wasm/phase-N-results.md and evidence under docs/wasm/evidence/phaseN/. Only phase 7 may declare the overall objective complete.
