# Phase 3: implementation and verification

Date: 2026-10-12 (America/Bogota). Status: completed for the phase 3 scene in Edge on Windows.

## Final validation passed

It was restarted from scratch at the operator's request. The three repetitions of
the corrected package pass: each includes 120 seconds of warmup and 900 seconds of
measurement, with native fullscreen, an effective 1920x1080 framebuffer, an RTX 3060
Laptop GPU, ANGLE/D3D11 and the simulation running at five ticks per second. The
identity of the build, resources, camera, browser and hardware matches between the
repetitions. Aggregate result: [acceptance.json](evidence/phase3/final-restart-release/acceptance.json).

| Repetition | Displayed FPS | p95 (ms) | p99 (ms) | 1% low (FPS) | Pauses >100 ms |
|---|---:|---:|---:|---:|---:|
| 1 | 60.00 | 27.7906 | 27.8131 | 35.78 | 0 |
| 2 | 60.00 | 27.7939 | 27.8203 | 35.67 | 0 |
| 3 | 60.00 | 27.7942 | 27.8229 | 35.65 | 0 |

Each window records 54000 displayed presents, zero drops and zero lost ETW
events. The WASM heap stays at 240582656 bytes in the three repetitions; there are
no fatal errors and the shutdown of each scene passes. The authorized minimum of
30 FPS and p95 <=33.4 ms is met. PresentMon identifies the presentation chain of the
dedicated window, but does not link each present to a simulation identifier.

The CPU profile of the third repetition records per-frame means of tick 0.055 ms,
interpolation 0.076 ms, upload 0.016 ms, renderer 0.618 ms and presentation 0.648 ms.
Inclusive scripting: 0.042 ms; maximum observed GC: 0.26 ms; JS reception: 0.011 ms.
The GPU probes stay disabled during acceptance; their corrected costs are
documented below as a separate diagnostic. The inclusive times overlap.

Controls and visual coverage are vouched for by
[Edge controls](evidence/phase3/edge-corrected-real-window-controls/msedge-acceptance.json)
and [corrected surface](evidence/phase3/corrected-surface-real-window/surface.json).
Firefox on Windows loads and passes resize/picking/restarts; its focus-loss run
remains inconclusive. This acceptance covers the original 37-entity scene, not the
full match nor sustained parity with the full native game. Those requirements
remain for the later phases. The cancelled attempts and those prior to the
framebuffer fix remain as historical, non-approved evidence.

## Changes

### Later fix: selection inside fullscreen

The operator noticed that left click did not select in fullscreen.
The failure was reproduced: SDL delivers positions in the dimensions of its logical
window, while the camera uses the framebuffer's dimensions. The input bridge now
converts those coordinates to the renderer's resolution both for left selection
and for right movement. It does not change the simulation.
The earlier test did picking after leaving fullscreen; it did not vouch for
selection inside fullscreen. The new regression tests both buttons inside
fullscreen at 100%, 75% and 50%, with a fresh selection after restarting each case:
[result](evidence/phase3/fullscreen-selection/result.json).
The broad check also passes in
[revalidated controls](evidence/phase3/fullscreen-selection-controls-recheck/msedge-acceptance.json):
ten fullscreen/resize cycles, three restarts, focus pause, context recovery and
shutdown without leftover workers. Its automation waits for the canvas to be
restored before changing the resolution when leaving fullscreen; the earlier
failed attempt is kept in `fullscreen-selection-controls`.

Ports 8082 and 8089 serve the fix; open tabs have to be reloaded.
The current manifest is kept in `evidence/phase3/build-release-selection.json`.
The three long measurements above belong to the build before this input
adjustment and are not presented as repeated on the new binary.

Basic water is also still pending: the original pass requires `g_Game`, which
this harness does not create, so it skips the whole water surface. The advanced
effects are also disabled. The performance results of this scene are without
visible water; adding water requires a new measurement and visual verification.

The target `phase3-scene-artifacts` recompiles the original engine closure in the
`debug`, `o2`, `o3` and `o3-lto` profiles. It keeps the phase 2 diagnostic target,
two jobs, an initial 8 GiB limit, exceptions and ASSERTIONS=2. It introduces no
fast-math nor changes to the RNG, commands or the 200 ms tick. SpiderMonkey and the
libraries stay in their phase 2 configuration: LTO only covers the recompiled
engine units. `build-profile.json` declares flags, limitations and hashes;
the linker exports symbols and separate DWARF. The executable WASM is about 14 MiB;
the debug file is kept apart. O2 and O3 compile and pass the seven
checkpoints and the restore against the native reference; O3+LTO also passes.

Fullscreen requires an explicit click. Esc leaves fullscreen and pauses;
Close scene uses a different command. Internal resolution and fullscreen scale are
visible. Resize uses DPR and the selected scale; the engine updates the viewport
and size-dependent resources. SDL keeps its canvas coordinate conversion; the
automated run checks picking after changing its size.

Startup checks isolation, shared memory and WebGL 2. Context loss pauses and
terminates the pool: Recover scene reloads the module and the map, losing unsaved
state. Transparent restore of the match is not claimed. The existing service keeps
COOP/COEP, MIME and the local origin, with a configurable port.

Each `SCENE_FRAME` is emitted after render and commit, with the tick,
interpolation, load/upload, renderer and presentation times. The browser keeps up
to 65000 samples and allows exporting them. They are CPU times and frame
submissions, not physical confirmation of presentation. GC slices and nursery
collections are observed, chaining the original callback. `scriptMs` measures the
outer C++ to JavaScript call and includes native callbacks and GC; these costs
overlap with the CPU subsystems. `?gpuTimer=1` enables asynchronous
EXT_disjoint_timer_query_webgl2 queries, discards disjoint results and bounds the
pending queries. Without the extension -1 is reported. `gpuProbeProxyMs` measures
the cost of the probes, not the whole GL proxy. The JS receiver records its
decoding cost and long tasks. Do not count callbacks as draws.

The proxied context is kept on the evidence. OffscreenCanvas starts in Edge and,
at the same 640x480 resolution, reduces the CPU presentation stretch from about
0.61 ms to 0.006 ms; both are around 60 submissions/s with pacing. However, its
resize fails with `Cannot resize canvas after call to transferControlToOffscreen()`.
This variant is experimental and is not used to approve 1080p nor fullscreen. The
improvement does not justify losing controls that were already verified. The full
original GUI belongs to phase 4.

## Historical Windows evidence

Recorded machine: Ryzen 7 5800H, 64 GiB of RAM, Windows 11 Pro; Edge
155.0.4283.45 used the integrated AMD Radeon in the historical runs. The final
package uses the RTX 3060 Laptop through ANGLE/D3D11, confirmed by the scene context. Screen 1920x1080, 60 Hz, DPR about 1 and the Silent
power plan. Details and driver in `evidence/phase3/windows-hardware.json`.

| Run | Result |
|---|---|
| Diagnostic O0, 30 s sample at 1080p | 3.74 submissions/s; mean CPU renderer 263 ms |
| O2 before pacing, 120 s + 900 s | 62.49 submissions/s; p95 17.32 ms; five ticks/s; shutdown 0 |
| O2 with pacing and optional GPU, 30 s sample | About 60 submissions/s; mean GPU 0.55 ms; maximum observed GC 1.98 ms |
| O2 and O3 parity | Seven checkpoints with identical bytes; restore and continuation equal |
| Instrumented O2 Edge controls | Ten fullscreen/resize/picking cycles; three restarts; focus pause; zero workers; context loss and reload pass |
| Firefox 142 Linux | Blocks WebGL 2 before creating workers; readable and recorded incompatibility |

The sustained run before pacing had a 130.29 ms pause: the `presentMs` stretch
recorded 114.9 ms, while the CPU renderer stayed around 0.62 ms. It is not
attributed to the GPU or GC without additional evidence. It was isolated; it is not
hidden from p99/1% low. Later costs need their own repetitions.

The short diagnostic Edge trace contains `Display::FrameDisplayed` and DXGI
presents, as well as `0ad-draw` marks. The feedback events do not expose an
identifier that links each native draw to its presentation: they are kept as
diagnostics, not as physical certification of each frame. The trace has overhead
and is kept out of the normal measurements. The historical timer-based pacing produced long intervals about
every 25 frames. The final package replaces it with RAF; 60 FPS is not the minimum
requested by the operator.

## Reproducible commands

```powershell
.\wasm\scripts\docker-phase3.ps1 -Profile o3-lto -VerifyParity
.\wasm\scripts\serve-phase2.ps1 -Directory wasm/dist/scene-o3-lto -Port 8089
.\wasm\scripts\record-phase3-hardware.ps1
# Use the Python of the local test environment that already contains Playwright.
python wasm/scripts/prepare-playwright-real-window.py
python wasm/scripts/verify-phase3-surface.py --url http://localhost:8089/scene.html
python wasm/scripts/verify-phase3-browser.py --url http://localhost:8089/scene.html --channel msedge --high-performance-gpu --duration-seconds 12 --warmup-seconds 0
python wasm/scripts/run-phase3-acceptance.py --url http://localhost:8089/scene.html --presentmon wasm/build/tools/PresentMon-2.6.0-x64.exe
python wasm/scripts/test-phase3-profile.py
python wasm/scripts/test-presentation.py
```

The final local package is in `wasm/dist/scene-release-resize`, served on ports 8082 and 8089. Its manifest and hashes are kept in `evidence/phase3/build-release-corrected.json`. The full recompilation produces `scene-o3-lto` from the same source; the measured package reuses the already compiled LTO closure and recompiles the application and the colour bridge. Do not confuse the earlier historical manifest with this final binary.

The hardware tests are serialized with an operating system lock to avoid competition between windows or GPUs. The operator's power plan is not changed. Three repetitions of the final profile, without DevTools nor GPU timer: 120 seconds of warmup and 900 of measurement. Initial camera frozen and no new orders during the benchmark; controls enabled in normal mode. Expected speed: five ticks per second. The analyses separate submissions from physical presentation. 1% low = 1000 / mean of the slowest 1% of intervals (rounded up). Only the aggregator can approve the three repetitions; a submission analyser does not certify presentation.

## Reconciliation of phase 2

There is parity and restore evidence, and the 900-second summary records
zero errors and three restarts. It also records a leftover worker at shutdown and
`closureRevalidationRequired: true`. The final file
`chromium-scene-focus-report.json` cited in the report is not present at the start
of this phase: focus and shutdown are not approved by that reference. The phase 2
test is adapted to use Close scene, keeping its CDP worker check.
The madvise/decommit warnings still apply; they are not hidden.
The phase 3 Windows check revalidates focus, pause, pool shutdown and context
reload; the historical headless failure is kept. The phase 2 run is not rewritten
as if it had closed correctly by itself.

The effective SpiderMonkey configuration keeps `MOZ_OPTIMIZE=1` and
`MOZ_OPTIMIZE_FLAGS=-O`, without JIT; libxml2 is built with -O2 and the Rust archive
uses the release profile. Rebuilding them with other levels is still pending. The
observed cost of the scripting boundary is small compared with the renderer/proxy of
this scene, and does not demonstrate the performance of the AI or large matches.

## Final acceptance status

- O3+LTO and its seven checkpoints/restore pass. SpiderMonkey/dependencies keep their original optimization; rebuilding them with other flags is ruled out for this scene because the scripting profile is small.
- The three full repetitions of the corrected package pass in `final-restart-release`: 60 FPS displayed at 1080p and five ticks/s. The authorized minimum of 30 FPS with p95 <=33.4 ms is met.
- The final package's controls pass in Edge, including invalid reload, exit code 31 and zero workers.
- The OffscreenCanvas variant keeps its resize blocker and stays experimental. Firefox on Windows loads the scene; its independent validation is recorded separately.
- The GPU probes and context comparisons measure partial costs; they do not represent the whole GL proxy.

The CPU bottleneck measured in the diagnostic is fixed by recompiling the engine
units with optimization. There is no evidence that justifies changing batching,
culling or skinning in this scene once the renderer and the GPU are around one
millisecond.

The phase 2 graphical differences remain open for phase 5: clamp-to-edge does not
emulate general border-colour; depth/sRGB formats need a test matrix; shadows,
advanced water, post-processing, GPU skinning and silhouettes are reduced.
The pin is not changed and no art is generated. Human review is mandatory before
submitting to the project. No commits, commit messages, issues, PRs nor publication.

## Authorized criterion and final package (2026-10-12)

The operator accepts a sustained 30 FPS at 1080p. Matching the original remains an optimization goal. The 59.2 native FPS cited come from a short sample, not from a full match. The final gate requires three 900-second measurements after 120 seconds of warmup, a presentation mean of >=30 FPS, p95 <=33.4 ms, ticks at the original speed and approved controls.

The final version uses an RAF display clock with a single pending task towards the engine worker. The benchmark scene freezes the camera and command input so that the tests are equivalent; normal mode keeps the controls. An access to a missing CGame in the harness was fixed: colours are read from the original player components and given explicitly to the renderer. It does not change the simulation.

O3+LTO keeps seven checkpoints identical to native and a correct restore (`parity-o3-lto-proxied/result.json`). SpiderMonkey is kept without JIT and with its original optimized flags: there is no evidence that it dominates this scene. An experimental rebuild of all its dependencies is not presented as verified.

PresentMon measures the swap chain of the dedicated window in fullscreen; it does not expose a link to each simulation frame identifier. CSV, submitted frames and drops are kept separately. The high-performance GPU is requested and the real renderer is recorded; a software run does not vouch for the gate.

The historical GPU timer sample prior to the framebuffer fix (30 s after 30 s of warmup) records 60.00 displayed FPS, p95 20.86 ms and zero pauses >100 ms. Mean CPU: tick 0.068 ms/frame, interpolation 0.086 ms, upload 0.017 ms, renderer 0.645 ms, presentation/proxy 0.686 ms; GPU 0.352 ms and probe 0.118 ms. Inclusive scripting 0.052 ms/frame; no GC was observed in that short window. Constant WASM heap at 240582656 bytes. This sample does not vouch for effective rendering at 1080p; the corrected costs are documented below.

The final native reference with a fixed camera measures 60.00 displayed FPS over 30 s, p95 18.15 ms and zero pauses >100 ms. Terrain/model triangles (3616/6998), the unit's coordinates and the player colours match the web package; 11 native draw calls and 10 WebGL ones reflect the backend difference. The resource reconciliation shows the same input files; the 96 extra native files are a derived cache and are excluded from the immutable identity. Evidence: `native-assets-reconciliation.json`, `native-final-camera-smoke*.json`, `edge-final-gpu-cost*.json`.

Firefox 142.0.1 on Windows with DPR 1.25 loads the module and passes ten fullscreen/resize/picking cycles and three restarts. Two attempts to induce focus loss through Playwright keep `document.hasFocus() === true`, so the pause test remains inconclusive, neither approved nor attributed to an engine failure. Its ANGLE renderer is anonymized and the GPU timer extension is not available. Full evidence in `firefox-final-raf-controls` and `firefox-final-window-focus`; the hardware gate is evaluated in Edge. The Firefox Linux WebGL 2 blocker remains historical.

## Fix after the operator's visual evidence

The operator's screenshots on 8082 and 8089 show a real failure: the HTML canvas and the engine metrics said 1920x1080, but Emscripten's proxied framebuffer kept 640x480. The earlier results do not vouch for full drawing at 1080p and are invalidated for acceptance. The first long repetition was cancelled and its CSV is kept as a diagnostic. It is fixed by using `emscripten_set_canvas_element_size` when a resize is detected, which also updates the runtime's FBO before recreating the renderer's targets.

The automation moves to a window without viewport emulation and requires Chromium to report a native fullscreen window state, in addition to DOM fullscreen. A visual check is added to verify the effective coverage of the drawing, not only the declared dimensions.

The corrected visual regression passes (`corrected-surface-real-window/surface.json`): canvas, drawing buffer, proxied depth renderbuffer and viewport match at 800x600, 1920x1080 and 640x480; native fullscreen reports 1536x864 CSS with DPR 1.25, equivalent to 1920x1080 physical pixels. The `fullscreen.png` capture fills the whole drawing and was inspected visually.

The difference between DOM and native fullscreen was isolated even on a minimal page: Playwright 1.56 enables emulated focus in its original CDP session. A private opt-in (`prepare-playwright-real-window.py`, `SCENE_REAL_WINDOW=1`) disables it and the same native buttons enter real fullscreen in Edge and Chrome. Fullscreen is not forced through CDP to approve the scene and the personal browser is not modified. The test environment without emulation allows testing real focus. Source for the fullscreen behaviour during capture: [Chromium FullscreenController](https://chromium.googlesource.com/chromium/src/+/main/chrome/browser/ui/exclusive_access/fullscreen_controller.cc); local implementation of the driver and hashes in `playwright-real-focus-patch.json`.

Ports 8082 and 8089 now serve the same corrected package. Previously loaded tabs need a reload. The scale selector only changes the render resolution in fullscreen; the Fullscreen button makes the entry request with `navigationUI: hide`.

The corrected real presentation sample passes: 60.01 displayed FPS, p95 20.87 ms, p99 27.80 ms, 1% low 35.93 FPS, zero pauses >100 ms, 1800 displayed presents and zero drops in 30 seconds. The effective framebuffer and the fullscreen window are verified. CSV and analysis in `edge-corrected-display-smoke*`. It is kept as a short sample; the sustained gate is vouched for exclusively by the three repetitions of `final-restart-release`.

The corrected controls pass in Edge (`edge-corrected-real-window-controls`), including checking the attachments after resize, ten cycles/picking, three restarts, real focus loss, context reload, exit code 31 with invalid input and zero workers. The corrected Firefox passes resize/picking and restarts again, but its driver does not produce the required focus loss; the test remains inconclusive in `firefox-corrected-real-window-controls`.

The first corrected long attempt was invalidated for leaving fullscreen during the measurement; it is kept in `final-corrected-release` without approval. An orphaned ETW session of our own from the earlier cancellation was detected, only that session was closed, and the PresentMon cleanup was fixed to stop its session by name on failure. A capture with lost ETW events cannot be approved either. `final-corrected-release-stable` keeps another interrupted attempt; the three final approved repetitions are stored in `final-restart-release`.

GPU probe costs with the corrected framebuffer (30 s): mean CPU per frame tick 0.065 ms, interpolation 0.079 ms, upload 0.016 ms, renderer 0.633 ms, presentation/proxy 0.692 ms; mean GPU 0.896 ms, p95 2.38 ms; proxy probe 0.112 ms and inclusive scripting 0.050 ms. The ETW capture of that sample lost events because of the orphaned session and does not certify physical presentation; the CPU/GPU profile is kept as a diagnostic. Do not mix it with the results prior to the resize fix, which were limited by the small FBO.

The operator confirms that they cancelled the run manually to pause everything and leave home. The fullscreen exit observed in the last diagnostic is not presented as a spontaneous engine failure. The later request to continue resumes the validation; the cancelled runs keep a non-approved status.

The first resumed 900-second measurement is invalidated, even though it ended without a fatal error: the events show a blur 116 seconds after entering fullscreen, the return of focus and another blur. The game paused as the normal flow requires and did not resume automatically. The 53990 draws of the measurement window have tickRate=0; the physical capture does not cover the 900 seconds either. They are not evidence of 60 FPS with an active simulation. The benchmark now aborts at the first check that finds a pause and publishes progress with tick/state. The runs require the window to stay visible and focused during the three repetitions. Non-approved evidence in `final-resumed-release`.
