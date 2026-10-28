# Phase 4.5 — continuation of 23 October

The phase stays open. The most recent measured reference is
`application-phase4-5-ai-map-kernels-2`. It passed sync/threaded parity at the
original 10 and 30 second checkpoints, with a clean shutdown:
`evidence/phase4-5/ai-map-kernels-2-parity-1`.

## Result of the obstruction sweep

Independent 120 second capture after 120 of warmup, without
concurrent builds nor profilers, in 1920×1080 fullscreen:

| Metric | Influence only | Influence + obstructions |
|---|---:|---:|
| Physical FPS | 40.7312 | 41.6171 |
| Physical p95, ms | 60.3574 | 50.2157 |
| Physical pauses >100 ms | 40 | 36 |
| Engine FPS | 45.2553 | 45.5579 |
| Engine p95, ms | 54.3400 | 54.6350 |
| Simulation rate | 0.99390 | 0.99949 |

Evidence: `evidence/phase4-5/performance-ai-map-kernels-2-diagnostic-1`.
306 units, without ETW losses, without presentation fallback and a clean shutdown.
The physical improvement of this short capture is not enough to accept the phase: the
engine p95 did not improve and both p95 values stay above 33.4 ms.

Of 600 turn updates: median 37.2925 ms, p95 47.1963 ms,
maximum 126.1804 ms; 553 exceeded 33.4 ms and one exceeded 100 ms.
Between turns, p95 1.5153 ms. The grouping is reproducible with
`wasm/scripts/analyze-phase4-5-turns.py`; they are wall-clock times, not exclusive CPU.

## Compact snapshot

The earlier profile puts about 16.9 ms/turn in AI setup, mostly
capture. An optional private format is being prepared that keeps the capture
point and the order of the queries, but uses:

- a cloned Float64Array for resource amount and gatherers;
- a numeric index per entity, without a nested object per resource;
- entity records only for the interfaces that contain data;
- the earlier object format as a fallback for non-numeric values.

No mutable views are shared between contexts. The binary64 numbers are kept,
including Infinity, NaN and -0; the tests also verify the absence
of interfaces, the exclusion of owners without AIProxy and later mutations
by the producer. Seven snapshot tests passed.

The earlier variant 3 does not count as approved parity: during the
threaded mode the page context was destroyed and WebGL errors appeared.
Its 10 second checkpoint matched, but the full run was invalid.
That result is not attributed to snapshot divergence without a reproduction.

Variant 4 keeps those artifacts and is built separately. The first
parity failed in threaded after the 10 second checkpoint with an
out-of-bounds memory access. The resolved stack starts at
`js::jit::GetPropIRGenerator::tryAttachStub`; it is in
`ai-map-kernels-4-parity-1/threaded/resolved-worker-error.json`.
There is an equivalent stack from before the compact snapshot in
`performance-direct-upload-diagnostic-1` (see the results history).
The match of functions does not prove the original cause of the invalid access.

The repetition of the same binary passed: `ai-map-kernels-4-parity-2`, with the
original 10/30 second hashes, both modes and a clean shutdown. It does not erase the failure.

The exploratory capture `performance-ai-map-kernels-4-diagnostic-1` finished
with 306 units, rate 0.99954, zero engine/ETW/fallback errors and a clean
shutdown. Same Chrome 155.0.8059.85. Short comparison:

| Metric | Native maps, earlier format | Compact snapshot |
|---|---:|---:|
| Physical FPS | 41.6171 | 41.4640 |
| Physical p95, ms | 50.2157 | 50.1177 |
| Engine FPS | 45.5579 | 45.9637 |
| Engine p95, ms | 54.6350 | 49.0800 |
| Physical pauses >100 ms | 36 | 36 |
| Turn Update median, ms | 37.2925 | 32.5152 |
| Turn Update p95, ms | 47.1963 | 41.7408 |
| Turn Update maximum, ms | 126.1804 | 98.7548 |

Of 600 turns, 232 exceeded 33.4 ms and none exceeded 100 ms. The improvement of the
turn timer did not translate into a noticeable physical improvement in this capture.
The variant stays experimental because of the intermittent failure; it is not adopted as a
solution nor does it replace long tests and human review.

## Next experiment: allocator across pthreads

`mimalloc` is compared using exactly the objects of candidate 2, without the
compact snapshot. The only functional link change is
`-sMALLOC=mimalloc`. The allocator is recorded in the report and the manifest.
The official documentation describes dlmalloc's global lock and
mimalloc's per-thread allocation contexts; this justifies the experiment,
it does not demonstrate that there is relevant contention in this match.
[Emscripten: allocator performance](https://emscripten.org/docs/porting/pthreads).

Link: `evidence/phase4-5/mimalloc-build-1`, package
`application-phase4-5-ai-map-kernels-mimalloc-1` (`allocator: mimalloc` in
the runtime). Sync/threaded parity approved with the original 10 and
30 second hashes: `evidence/phase4-5/mimalloc-parity-1`.

Independent capture `performance-mimalloc-diagnostic-1`: 120 s of
warmup + 120 s, 1920×1080 fullscreen, 306 units, rate 0.99979,
zero lost ETW events, without presentation fallback, clean shutdown.

| Metric | dlmalloc (candidate 2) | mimalloc |
|---|---:|---:|
| Physical FPS | 41.6171 | 41.7120 |
| Physical p95, ms | 50.2157 | 66.6769 |
| Physical p99, ms | 83.4361 | 83.4414 |
| Physical 1% low, FPS | 8.30 | 8.73 |
| Physical pauses >100 ms | 36 | 34 |
| Engine FPS | 45.5579 | 45.3302 |
| Engine p95, ms | 54.6350 | 53.1650 |
| Turn Update median, ms | 37.2925 | 35.1598 |
| Turn Update p95, ms | 47.1963 | 48.9224 |
| Turn Update maximum, ms | 126.1804 | 84.9751 |
| Turns >33.4 ms (of 600) | 553 | 407 |

mimalloc brings no physical improvement: equivalent FPS and a worse physical p95
(it falls on the next vblank multiple). The turn median drops ~2 ms,
which is compatible with some allocation cost, but a single
short capture is not enough. **It is not adopted**; dlmalloc is kept.

## Time split per frame (both captures)

Grouping the engine intervals of the measured window:

- Frames without a turn: median interval 16.7 ms, Update ~0.9 ms.
- Frames with a turn: median interval 52–54 ms = turn Update (~35 ms)
  plus ~15 ms of render/wait until the next vblank.
- The rest of the interval (interval − Update) is a median of ~15.6–15.9 ms
  both with and without a turn.

With vsync at 60 Hz, a turn frame only fits in 2 vblanks (33.4 ms) if
Update + the frame's render ≲ 33 ms. Today it falls into 3 vblanks (~50 ms), and with
~5 turns/s that means ~11 % of the frames, above the 5 % that the
p95 marks. To pass the gate the turn frame has to be cut roughly in half,
splitting the work between turn cost and render cost.

## CPU profile of candidate 2

`cpu-profile-ai-map-kernels-2-1`: separate profile (diagnostic, not FPS),
120 s of settling and 30 s of CDP sampling, threaded, correct shutdown.
On the engine thread (`cpu-15.cpuprofile`), ~150 turns:

- `CSimulation2Impl::UpdateComponents`: 5.735 s inclusive (~38 ms/turn).
- `CCmpAIManager::StartComputation`: 2.587 s (~17 ms/turn), of which
  `CAIWorkerClient::Capture` (JS snapshot + clone) is 2.412 s.
- The AI result barrier no longer appears among the top 30
  functions: the actor finishes within the interval between turns.

They are inclusive samples with profiler overhead; they are not summed nor
presented as exclusive CPU.

## Candidate: AI capture after the turn frame's Present

`WASM_AI_DEFERRED_CAPTURE` (opt-in, threaded mode only). At the end of the turn
the C++ copies of pathfinder and territory are still read at the original point,
and the position of the AI commands is reserved at the same place.
Only the JS part (`GetRepresentation` + snapshot + clone, ~16 ms) runs
right after the turn frame has sent its Present to the render
worker, and the state update is placed before the grid updates, as
in the original order. This way the turn frame fits in 2 vblanks and the capture
runs while it is shown.

Safeguards: the pending task runs before any observer:
a hook in `Frame()` after the render, the start of the next turn
(`CSimulation2Impl::Update`, which covers several turns in one frame), any
control message to the AI (including its serialization) and the result
barrier. `Init` and the destructor cancel the task and fail its result.

Semantic risk: between the end of the turn and the capture,
`UpdateGrid`, `StartProcessingMoves(false)`, `RunJobs`, `Interpolate` and the
render run. If any of them modified state that the AI reads, the AI's input
would change. Parity would detect it at the measured checkpoints, but it does not
prove every match. It requires human review.

Sources: `source/simulation2/helpers/AIDeferredStart.h`,
`CCmpAIManager.cpp`, `Simulation2.cpp`, and an edit of the frozen `main.cpp`
in `wasm/scripts/phase4-5-deferred-capture-build.py`. It recompiles
only those 3 units over the objects of candidate 2; dlmalloc.
Evidence: `evidence/phase4-5/ai-deferred-capture-build-1`.

Parity: `evidence/phase4-5/ai-deferred-capture-parity-1` approved. Both
modes reproduce the original hashes `e35b3f94…` (10 s) and `b218d9a3…`
(30 s) in serialization, non-local debug and GUI state.

### Physical capture

The first capture (`performance-ai-deferred-capture-diagnostic-1-closed`)
was interrupted at ~90 s because the operator closed the browser; there is no
engine error. It does not count as a measurement.

At the operator's request the capture was shortened to 2 minutes: 60 s of
warmup + 60 s measured: `performance-ai-deferred-capture-diagnostic-2`.
306 units, rate 0.99931, zero lost ETW events, without presentation
fallback, clean shutdown. The script marks `passed: false` only because the
backlog criterion needs more samples than a 60 s window provides
(the 6 samples are 0).

To compare, the references were recomputed with the same analyzer over the
same match window (60–120 s), which PresentMon recorded during their
warmup, and over their two measured halves:

| Capture, window | Physical FPS | Physical p95, ms | p99, ms | 1% low | Pauses >100 ms |
|---|---:|---:|---:|---:|---:|
| Candidate 2, 60–120 s | 41.13 | 50.26 | 83.53 | 6.87 | 24 |
| Candidate 2, 120–180 s | 41.31 | 56.42 | 83.46 | 7.53 | 21 |
| Candidate 2, 180–240 s | 41.93 | 50.13 | 83.41 | 9.34 | 15 |
| mimalloc, 60–120 s | 40.37 | 50.12 | 83.49 | 6.26 | 22 |
| **Deferred capture, 60–120 s** | **47.34** | **33.42** | **66.75** | **9.20** | **12** |

Engine FPS 47.91, engine p95 40.31 ms. Turn Update median 18.47 ms
(before ~37 ms); 13 of 299 turns exceed 33.4 ms (before 272–281 of 300). The
Update no longer includes the capture, so that metric is not directly
comparable; the physical figures are.

The physical p95 is exactly 2 vblanks. On this screen the vblank
interval measures ~16.71 ms, so 2 vblanks = 33.42 ms, just above
the 33.4 ms threshold. There are still 12 pauses >100 ms per minute.

It is a short, single capture; it is not the acceptance (3×900 s per load,
combat, native/WebGL comparison). It is the biggest physical advance so far.

Pending:

1. Human review of the semantic change.
2. Long and repeated capture of the candidate, plus the combat load.
3. Investigate the remaining pauses >100 ms (not explained by the turn
   Update: the engine maximum reaches 100 ms in almost no turn).
4. Decide what to do with the 33.4 ms threshold versus 2 vblanks (33.42 ms)
   on this screen. It is the operator's decision; the criterion is not changed.

There is no verified complete solution yet.

## Operator's manual test and WebGL fix

When testing the package manually, the operator saw black models and
`Failed to link program 'shaders/glsl/model_common.xml': Fragment shader is
not compiled`. The page starts with WebGL 2 by default, not WebGPU.

Cause: the `browser-perf` build copied `ShaderProgram.cpp` from the workspace without the
GLES adaptations that `phase4-application-patch.py` applies in the frozen
tree (parallax loop with a constant bound and bilinear PCF shadows
for ES). Since then all candidates compiled that file without them.
With parallel compilation, the real error was hidden. A diagnostic
script, only on a copy of the package, showed the log:
`ERROR: 0:41: 'i' : Loop index cannot be compared with non-constant
expression`, which is the parallax loop of `model_common.fs`
(`evidence/phase4-5/gl-shader-diagnostic-1`, 13 error lines). None of
the other 13 files with GLES patches was affected. WebGPU does not use that
file, so the WebGPU measurements do not change.

Fix:

- `wasm/scripts/phase45_shader_program_source.py` inserts the
  `WASM_PARALLEL_SHADER_COMPILE` blocks over the already patched GLES source, and fails if
  the adaptations are missing.
- It is used by `phase4-5-browser-perf-build.py` and `phase4-5-deferred-capture-build.py`.
- `ShaderProgram.cpp` now reports each shader's compile log
  when the link fails with parallel compilation.

Package `application-phase4-5-ai-deferred-capture-2`: the same objects
of the deferred capture candidate plus that `ShaderProgram.cpp`. The WebGL
repetition `gl-shader-diagnostic-2` finished without shader errors. Only two
warnings that already existed remain: the SDL WM info query and the 404 of `favicon.ico`.
The ES PCF shadows also use the original filtering again.

## Operator's decision on the deferred capture

The operator delegated the decision: keep it if it does not affect the gameplay
experience. It is kept, for these reasons:

- No simulation tick advances between the end of the turn and the capture.
  What runs in between (visual interpolation, render, `UpdateGrid`
  and `RunJobs`) does not provide new data to the AI in the measured cases.
- The grids the AI receives are still copied at the original point.
- The sync/threaded parity reproduces the original hashes at both
  checkpoints.
- For the player, the only visible effect is that the 3 vblank turn
  frames disappear.

Limitation: parity covers specific checkpoints of one match. If
an AI divergence appears in other matches, this change is the first
suspect. Human review of the code is still needed before
submitting it to the project.

The operator chose to close the phases by running the acceptance tests as
they are written, and to mark only what passes with evidence.

## Command replay in the render worker

Profile `cpu-profile-ai-map-kernels-2-1`, `cpu-2.cpuprofile` (render
worker): 23.7 s busy out of 31.8 s, about 17 ms of JS per frame. With that it
does not reach 60 Hz even if the engine finishes on time. On the engine thread, ~12 %
of the time is waiting on the worker's full queue and ~2 % waiting in `Present`.

Optimizations in `wasm/browser/webgpu-engine.mjs`, without changing the GPU
commands emitted nor their order:

- cache of the compiled pipeline per pipeline object/layout/target;
- uniform alignment read only once;
- dynamic offsets in a reused `Uint32Array`, with the typed overload
  of `setBindGroup` (the saved pass state copies the values);
- copy of small uniforms without `subarray`;
- current pass state cached;
- no closures per draw.

The 56 WebGPU Node tests passed, including two new ones: the reused
offsets do not alter the saved state and the cache separates render
targets. Package `application-phase4-5-render-replay-1`.
2 minute capture `performance-render-replay-diagnostic-1`, window
60–120 s: 48.44 FPS, p95 33.42 ms, p99 66.73 ms, 10 pauses >100 ms (before
47.34 / 33.42 / 66.75 / 12). The improvement is within the noise of a short
capture.

## Origin of the remaining pauses

Profile `cpu-profile-render-replay-1` (diagnostic, not FPS). The timeline
of the engine thread was split into frames separated by the wait on the
display clock:

- Normal turn cycle: Update ~20–25 ms, deferred capture ~15 ms and render
  of two frames ~12–17 ms each (with profiler overhead).
- Frames longer than 100 ms coincide with render peaks of 75–110 ms.
  `CCmpUnitRenderer::RenderSubmit` dominates them: after each `TurnStart`
  it recomputes the visibility of all units (`GetAlwaysVisible` in JS
  plus `GetLosVisibility`) and the bounds. Add to that JS GC slices
  inside the render and, in one case, ~51 ms of GUI tick.
- Caching `GetAlwaysVisible` is not safe:
  `maps/scripts/TriggerHelper.js` changes it at runtime. It is
  discarded.

## p95 threshold versus this screen's refresh

The measured median interval is 16.695–16.699 ms (~59.9 Hz), so two
vblanks measure 33.39–33.42 ms. A frame that exactly meets the
30 FPS rhythm (2 vblanks) can measure more than 33.4 ms on this screen. With about 10
2-vblank frames per second (turn and the following frame) against ~48 FPS,
about 20 % of the frames take 2 vblanks. For the p95 to drop to
1 vblank, full turns of less than ~16 ms would be needed, out of current
reach. The operator is informed before launching hours of tests that would fail
the criterion only because of this difference.

**Operator's clarification (2026-10-23):** "p95 ≤ 33.4 ms" is evaluated as
"physical p95 ≤ 2 measured refreshes of the screen", that is, sustained 30 FPS.
`analyze-presentation.py` keeps `presentationGate30`
unchanged and adds:

- `measuredRefreshMs`: median of the one-refresh intervals (12–21 ms).
- `twoRefreshLimitMs`: 2 × refresh × 1.005; the tolerance only covers
  PresentMon jitter.
- `presentationGateTwoRefresh`: the gate with the clarification. It keeps the
  capture validity, the coverage and engine FPS ≥ 30 against
  duplicated images.
- `engineP95WithinTwoRefresh`: p95 of the engine frames, informational only.
  It is not relaxed here: it is the operator's decision.

Check over existing captures:

- Candidate 2: does not pass (p95 50.22 ms).
- Deferred capture and `render-replay-1`: pass (p95 33.42 ms; measured limit
  33.54 ms).
- In all three cases the engine p95 (36.5–54.6 ms) exceeds that limit. Its
  timestamp is the reception in the window after the render worker's
  barrier, so it includes the main thread's latency.

The 12 tests of `test-presentation.py` still pass.

## Screen at 60 Hz and short tests (end of day)

The operator set the screen to exactly 60 Hz. The long battery already launched was
interrupted before measuring and was saved as
`acceptance-webgpu-render-replay-1-aborted-refresh-change`. It was relaunched and the
operator stopped it for lack of time:
`acceptance-webgpu-render-replay-2-stopped-by-operator`. Neither of the two
counts as a measurement.

Short tests (maximum 10 minutes, at the operator's request) with
`application-phase4-5-render-replay-1`, 60 s + 60 s:

- Skirmish, `performance-render-replay-60hz-1`: 50.10 physical FPS and 50.82
  engine. Physical p95 33.36 ms, below the literal 33.4 ms threshold.
  Engine p95 33.47 ms, which is why `presentationGate30` stays false.
  Measured refresh 16.668 ms; `presentationGateTwoRefresh` true. p99 66.65 ms,
  1 % low 9.69 FPS, 11 pauses >100 ms, rate 1.00003. Valid capture
  (1080p fullscreen, no lost ETW events). Detail in
  `presentation-two-refresh.json`. The series stopped after it because the
  script stops at the first `passed: false`, which in 60 s always appears because of
  missing backlog samples.
- Combat, `performance-render-replay-60hz-combat-1`: invalid.
  `Declared original unit load fell below 200` in the first sample.
  Before, combat was around 224–262 units
  (`performance-portable-o3-diagnostic-1`), close to the minimum of 200. The
  stability of that load has to be reviewed before acceptance. The
  200 unit criterion was not changed.

## Pending for the next session

1. Ask the operator how much time they have before launching the long battery
   (~1 h 45 min for WebGPU alone).
2. Investigate why the combat load drops below 200 units
   (`phase4_workload.py`) without lowering the minimum.
3. Operator's decision on the p95 of the engine frames (33.47 ms at
   60 Hz, 0.07 ms from the limit).
4. Operator's decision on the native comparison: on 21 October they
   said not to run it.
5. Keep reducing the pauses longer than 100 ms: render peaks after
   `TurnStart` (unit visibility), JS GC and GUI tick.
