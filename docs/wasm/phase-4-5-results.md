# Phase 4.5: WebGPU integration

**Update 2026-10-26: phase still open, acceptance pending.** See the
[active continuation](phase-4-5-continuation-2026-10-26.md) (automatic low
graphics profile for weak GPUs) and
[25 October](phase-4-5-continuation-2026-10-25.md). Best candidate
`application-phase4-5-cushion-1` (present pacing, asynchronous OpenAL, turn
cushion): combat 29.92 physical FPS with the 30 FPS cap, p95 33.41 ms (two
refreshes), one pause over 100 ms per minute; short decision captures, not the
acceptance battery. Operator decision: the FPS gate is the 30 FPS lock (mean ≥
29.5 displayed FPS, physical p95 ≤ two refreshes); the candidate meets it in
short captures of both workloads. Next: the 3 × 900 s battery.

**Work resumed on 20 October by the operator.** See the
[active continuation](phase-4-5-continuation-2026-10-20.md). The rAF candidate
stood at 39.83 physical FPS /p95 50.12 ms. The fixed AI experiment passed
sync/threaded equivalence at 10 and 30 seconds; its physical diagnostic is
in progress. Phase acceptance is not declared.

Update: 2026-10-19 (America/Bogota). **Phase open: integrated implementation, acceptance pending.**
The operator resumed after the pause of the 19th at 16:15. The
[active continuation](phase-4-5-continuation-2026-10-19.md) records the
rebuild of the experimental VM: it compiled correctly and passed **30
CPU checks with 9,945 incremental GC yields**. Its 120+120 s fullscreen
diagnostic recorded **35.02 physical FPS / p95 66.78 ms**,
with simulation 0.99106, backlog 0, correct GPU probes and a clean shutdown.
It did not fix the stutter; the 37.20 FPS /66.74 ms control is kept.
The experiment and its evidence stay separate. The atomic replacement of the
clock mutex passed 10 CPU cases, but its diagnostic recorded **34.39 FPS
/66.80 ms**, also without fixing the stutter. The first render
bundle cache passed 14 CPU cases and 9 GPU cases (576 bytes), but recorded **29.97 FPS
/67.81 ms**. After profiling and fixing redundant bindings/allocations, the
second variant recorded **35.10 FPS /66.79 ms**, still without fixing it.
The third variant passed 15 GPU cases /960 bytes, but recorded **34.07 FPS
/66.84 ms** despite reusing 71.99 % of the draws. None is adopted
as a fix. The same fixed/switch source compiled at O2 passed the 30
CPU cases, but recorded **34.31 FPS /66.83 ms**; it did not fix the p95 either.
WebGL, with the same package as the best control, recorded **29.57 FPS
/83.38 ms**; it also shows simulation updates >100 ms.
The operator asked to **not review the native build any more** and to incorporate the
browser improvements into a single combined candidate. Its run finished:
[SIMD, workers, shaders and persistent resources](phase-4-5-browser-performance-2026-10-19.md).
The package `application-phase4-5-browser-perf-2` recorded **24.54 physical FPS
/ p95 100.14 ms**, with 45.86 engine FPS, 306 units, simulation
0.991456×, backlog 0, ETW without losses and a clean shutdown. The ZIP cache
stayed at 64 MiB and real IndexedDB/IDBFS persistence passed. Physical
presentation got worse against the control; the stutter remains open. The
[report for Gemini](phase-4-5-report-gemini-2026-10-19.md) distinguishes the
measured run from the later presentation adjustment still unverified.
The
[pause snapshot](phase-4-5-pause-2026-10-19.md) and the
[earlier snapshot](phase-4-5-pause-2026-10-18.md) keep the
identity of the packages; the real control and the counters VM stay separate.
Original pin: `40b8794eecb9618da69e10bacffa8814c561aa51`.

**Resume requested on 2026-10-18:** the 36 hashes of the pause snapshot
matched and the already linked asynchronous candidate was packaged. Its first
physical diagnostic is `performance-async-bridge-diagnostic-1`; it is not yet
considered approved. Current best diagnostic mean: 37.20 physical FPS, with stutter
still outside the limit (p95 of 66.74 ms). The
priority of reaching 30 FPS before tests unrelated to performance is kept.
The [continuity document of 2026-10-17](phase-4-5-pause-2026-10-17.md)
describes the historical state at the pause; linked/dist were already synchronized on resuming.
The [continuation point of 2026-10-18](phase-4-5-continuation-2026-10-18.md)
identifies the candidate and the current commands. The individual diagnostics
do not establish statistical significance nor fix the p95.

## Fullscreen and multiple monitors

The launcher captures the mouse with Pointer Lock when entering fullscreen.
SDL keeps its clamped absolute coordinates and the original camera does not change.
A fullscreen container shows the same cursor PNG and hotspot that SDL
delivers; no graphics resources are created nor replaced. The position is published from
the engine thread through an atomic value. Capture changes notify
SDL of the focus. Escape, loss of focus and exit/close release the mouse; a click
inside the game captures it again.

`verify-phase4-5-pointer.py` uses Windows relative input and checks the
four edges, the cursor, Escape and shutdown without workers. The machine has three
monitors (virtual desktop 4480 × 1949). The first trials verified
the four edges, but are kept as failed because of the Escape check;
they do not vouch for full approval. The final run
`evidence/phase4-5/multimonitor-pointer-7/report.json` approved the four edges
with sustained camera movement, original cursor visible, Escape and shutdown
without workers nor GPU errors. Escape was verified with trusted CDP keyboard input and
the page's explicit handler; the Windows keyboard injection did not
reach the page and does not vouch for Chromium's native unlock gesture.

`evidence/phase4-5/chrome-validation-pointer-3/original-input/report.json`
then approved pause, multiple selection, groups, rally point, keyboard
camera, minimap and contextual orders, without GPU errors nor orphaned workers.
The harness uses Windows movement and clicks while there is capture; mixing those
movements with absolute CDP clicks introduced artificial offsets.
After recalling a group, the same civic centre is located again in the
current view before checking its selection and its rally point.

The original menu and a Mainland match work with WebGPU on NVIDIA
Ampere. The technical load finishes without GPU errors. This does not approve a full
match, visual parity nor the required performance. WebGL stays the default.

The operator reported a grey window with audio in the Edge test session,
although the internal screenshots contained the scene. That physical presentation is not
considered approved (`physical-gray-presentation.json`). A clean Chrome
session on the same NVIDIA showed the menu, confirmed by the operator.
Work continues with Chrome 155.0.8059.80; no additional diagnostic clients
are connected while a window/focus test runs. Edge is not included as an
approved platform on the basis of internal screenshots.

## Visual comparison with the native executable

`evidence/phase4-5/visual-native-comparison-fixed-1.json` meets the original
numeric limits in the three captures: base scene, hard shadows and PCF.
The mean RGB difference is 0.219–0.224 and the fraction of pixels outside the
threshold is 0.00511–0.00523, against limits of 2 and 0.02. The
24 graphics settings, camera, match attributes and simulation state are matched.
This vouches for those captures; it does not replace the review of all effects
nor the pending performance and stability tests.

libc++'s distribution of visual variants chose different trees and minerals
than MSVC with the same seed. The Emscripten path now uses the same
sampling as MSVC 14.44; it keeps the original variants and resources and does not
touch the simulation RNG. The probe `visual-variant-random-msvc.json` compares
70,000 results and the generator's consumption against the native library.

Only for comparing images the original option
`-fixed-frame-frequency=60` is enabled: it avoids interpolation and wind differences
between captures of a paused match. The performance meters reject
that option and keep the normal clock. The historical WebGL reference stays
immutable; its defective F2 readback is kept as failed evidence.
The alternative comparison reads the original RGBA framebuffer at the end of a
frame and records any temporary substitution of the launcher or binary.

The historical comparison `visual-frozen-comparison-fixed-1.json` still
fails with that matched clock: mean RGB 2.084 and fraction 0.01910 in
base/PCF; 2.466 and 0.03902 with hard shadows. The archived binaries
are compared with the same old variant distribution. The thresholds are not
widened nor is that reference considered approved; locating the
shadow/presentation difference against WebGL remains pending.

## Implementation

### First full physical measurement: insufficient performance

`performance-webgpu-20261017-2/webgpu-skirmish-1.json` contains 120 s of
warmup and 900 s of measurement, Chrome/NVIDIA at 1920 × 1080, without screenshots
nor simultaneous profiles. PresentMon lost zero events. The result was
3.43 presented FPS, 3.63 engine FPS and a p95 of 867.56 ms. The simulation
advanced at 74.22 % of real time. The run fails and stops the remaining
repetitions: it does not vouch for performance nor simulation speed. The operator
also observed the jumps. The shutdown was normal (code 0), without GPU errors.

The earlier attempt was invalidated before measuring because Windows kept
another application in the foreground. The preparation now exclusively activates
the test browser window, once before fullscreen; during
the measurement only its real owner is checked every 30 s. Focus is not forced
during the intervals nor replaced by DOM emulation.

It is investigated through separate short profiles, explicitly identified
as diagnostics; those profiles do not count for performance acceptance.

`cpu-profile-workers-2/analysis.json` resolves the samples of the fourteen
workers with the archived symbol map. In the main loop worker,
`SetUniform` accumulated 10.58 s of a 31.12 s sample; converting the floats
to JSON was its main cost. The new transport keeps their float32 bits
in a binary block, together with the transient geometry bytes. The
frequent state/draw operations use uint32 words; the batches
keep the order with uploads, labels and remaining commands. The base
index offset is interpreted as int32 again. Each range is copied when
it is recorded and consumed before the synchronous call returns to the browser.

The uniform and geometry arenas are uploaded once before submitting the
command buffer, with distinct ranges per draw. The tests verify the
exact values, order, alignment, limits and reuse between frames.
The optimization does not modify shaders, match logic nor original resources.
`visual-native-comparison-binary-1.json` and
`visual-native-comparison-state-cache-1.json` pass the three original captures
against native without widening thresholds. The new cache skips redundant setters
only within the same render pass and keeps all changes of offsets,
buffers and groups. The final performance is still pending approval.

The short fullscreen trials, without profiler nor screenshots, record:

| Evidence | Presented FPS | Physical p95 | Simulation rate |
| --- | ---: | ---: | ---: |
| `performance-binary-diagnostic-1.json` | 17.13 | 133.44 ms | 82.44 % |
| `performance-state-cache-diagnostic-1.json` | 21.41 | 100.13 ms | 83.11 % |
| `performance-native-diagnostic-1.presentation.json` | 56.27 | 21.42 ms | 93.78 % |
| `performance-portable-diagnostic-1/webgpu-skirmish-1.json` | 8.35 | 333.62 ms | 84.17 % |
| `performance-portable-o2-diagnostic-2/webgpu-skirmish-1.json` | 10.93 | 250.24 ms | 95.42 % |
| `performance-o2-monotonic-diagnostic-2/webgpu-skirmish-1.json` | 10.58 | 266.95 ms | 91.33 % |
| `performance-portable-o3-diagnostic-1/webgpu-skirmish-1.json` | 19.14 | 116.79 ms | 100.00 % by the earlier calculation |
| `performance-portable-fixed-diagnostic-1/webgpu-skirmish-1.json` | 18.86 | 116.79 ms | 99.48 % with real intervals |
| `performance-renderer-cache-diagnostic-1/webgpu-skirmish-1.json` | 20.78 | 116.78 ms | 99.22 % with real intervals |
| `performance-buffer-arena-diagnostic-1/webgpu-skirmish-1.json` | 24.46 | 83.45 ms | 99.61 % with real intervals |
| `performance-shared-skinning-diagnostic-1/webgpu-skirmish-1.json` | 23.26 | 100.04 ms | 99.08 % with real intervals; variant withdrawn |
| `performance-async-bridge-diagnostic-1/webgpu-skirmish-1.json` | 24.47 | 83.45 ms | 99.30 % with real intervals |
| `performance-async-audio-diagnostic-1/webgpu-skirmish-1.json` | 25.07 | 83.47 ms | 99.42 % with real intervals |
| `performance-shared-health-diagnostic-1/webgpu-skirmish-1.json` | 32.52 | 83.44 ms | 99.44 % with real intervals |
| `performance-deferred-replay-diagnostic-1/webgpu-skirmish-1.json` | 35.08 | 66.79 ms | 99.26 % with real intervals |
| `performance-portable-switch-diagnostic-1/webgpu-skirmish-1.json` | 35.72 | 66.79 ms | 99.31 % with real intervals |
| `performance-mapped-upload-diagnostic-1/webgpu-skirmish-1.json` | 35.52 | 66.82 ms | 99.14 % with real intervals |
| `performance-streamed-dispatch-diagnostic-1/webgpu-skirmish-1.json` | 35.12 | 66.80 ms | 99.28 % with real intervals |
| `performance-direct-upload-diagnostic-2/webgpu-skirmish-1.json` | 35.58 | 66.79 ms | 99.16 % with real intervals |
| `performance-present-pacing-diagnostic-1/webgpu-skirmish-1.json` | 32.20 | 66.74 ms | 98.95 % with real intervals; variant withdrawn |
| `performance-uniform-cache-diagnostic-1/webgpu-skirmish-1.json` | 35.50 | 66.79 ms | 99.07 % with real intervals; variant withdrawn |
| `performance-portable-underflow-diagnostic-1/webgpu-skirmish-1.json` | 34.83 | 66.81 ms | 99.33 % with real intervals; variant withdrawn |
| `performance-async-texture-diagnostic-1/webgpu-skirmish-1.json` | 35.78 | 66.79 ms | 98.94 % with real intervals |
| `performance-wasm-eh-diagnostic-1/webgpu-skirmish-1.json` | 35.23 | 66.79 ms | 99.21 % with real intervals; does not improve smoothness |
| `performance-audio-error-diagnostic-1/webgpu-skirmish-1.json` | 37.20 | 66.74 ms | 99.14 % with real intervals; p95 still insufficient |
| `performance-audio-after-present-diagnostic-1/webgpu-skirmish-1.json` | 32.97 | 66.78 ms | 99.36 % with real intervals; variant withdrawn |

The first measurements are 60 s stretches after 30 s of warmup;
the portable variants and the recent optimizations use 120 + 120 s. All keep more than 200 units and
do not replace the long repetitions. The main native report fails on
simulation speed and keeps its CSV; the presentation is analysed separately,
without inventing observed C++ frames nor turning the failure into an approval.
The worst WASM frames of the first short trial include up to 808.96 ms in
`CGame::Update`; in normal frames its median is about 1.50 ms.
The visual state reported by the operator matches that stutter.

The portable O3 variant improves the short skirmish trial: 20.80 engine
FPS, engine p95 93.96 ms and zero observed backlog. It still fails the
presentation limits. The combat of that same trial failed with
`Uncaught RuntimeError: null function` in a worker; the later errors
`emscripten_proxy_async failed` are secondary. This candidate is not adopted
nor is its stability vouched for. The instrumented repetition
`combat-portable-o3-crash-diagnostic-1` aborted because the load dropped below 200,
without reproducing that exception. Each cause is kept separately.

The earlier reports compute the rate with the plan's nominal
duration. It was detected that the last read or replenishment can exceed the deadline:
the new measurements use monotonic intervals that frame each original
simulation read. The whole uncertainty interval must stay within
±2 %; the limits are not raised nor are historical reports rewritten.
Observation and maintenance times are recorded per sample.
The last two measurements pass the real simulation intervals, keep
306 units, zero backlog, physical focus/fullscreen, zero lost ETW events and
normal shutdown. They stay below 30 FPS; they do not close the performance problem.
The profile `cpu-profile-portable-fixed-o3-1` attributes 11.35 s of 31.18 s of the
engine thread to waiting, and 9.53 s to `Context::Flush` with its calls to the main
thread. The main thread consumes 3.00 s self in `command` and 1.63 s in
`bindShader`. Those paths are optimized keeping the bytes and the draw order.
The transfer arena removes the synchronous `stageBuffer` calls of each
upload and keeps the copies at their original position between draws. 15
specific tests of ranges, std140, snapshots, order, reuse and retirement pass.
The unified skinning output experiment passed a GPU byte comparison
on NVIDIA Ampere with 64/192 bones (`skinning-shared-layout-4`), but showed no
improvement in the physical trial and was withdrawn from the engine. Its code stays archived in
the evidence; it is not selected as a proven optimization.
The compiled and linked asynchronous queue passes 10 checks of its production
header, with input copies, confirmed consumption, order, memory limits,
reads from another thread and failure propagation (`command-queue-probe-1.json`).
At the pause of 17 October it was neither packaged nor run; that state
did not vouch for its FPS nor its integrated operation.

On resuming, `performance-async-bridge-diagnostic-1` ran that queue: it passed
simulation, backlog, load, shutdown and physical validation, but did not improve FPS
against the buffer arena. The asynchronous sequence advanced from 5,411 to 23,195,
with 5,925 additional frames/submissions and without order errors. It still does not
meet 30 FPS. This run replaces the historical "not run" state.

`cpu-profile-async-bridge-1` attributes about 8.26 s of waiting in 30.70 s to
OpenAL queries from `CSoundManager::IdleTask`, and about 2.72 s to writing the
replay from `CReplayLogger::Turn`. The audio queries impose again
a wait on the previous frame. Their execution was moved to after recording
the draw on the CPU and before the WebGPU submission, with a fallback when nothing is drawn;
GL keeps the immediate execution. The helper's six CPU checks
pass (`deferred-audio-probe-1.json`). The physical diagnostic
`performance-async-audio-diagnostic-1` obtained 25.07 presented FPS and 26.69
engine, with a physical p95 of 83.47 ms and 140 intervals longer than 100 ms. It kept
306 units, simulation at 99.42 %, zero backlog, zero lost ETW events,
physical fullscreen/focus and exit 0. After the measurement finished there were two audio
sources playing and 108 non-empty decoded buffers. It still does not
meet the required performance.

The next candidate publishes the device health in a shared
atomic and keeps the backbuffer metadata during the swapchain's lifetime.
It avoids synchronously querying the browser at the start of each frame; the
real acquisition of the presentation texture stays in `Present`. The
queue is bounded to six calls / 32 MiB. The 17 Node transport,
state and resource lifetime tests pass, including device loss, removal of the
observer and absence of late writes to the freed address. The
C++ build passed. `performance-shared-health-diagnostic-1` measures the candidate
in physical fullscreen: 32.52 presented FPS, 34.98 engine, physical p95 of
83.44 ms, p99 of 133.51 ms and 131 pauses longer than 100 ms. There are 306 units,
simulation at 99.44 %, zero backlog, zero lost ETW events and exit 0 without
orphaned runtime resources. The mean exceeds 30 in this short diagnostic,
but the smoothness gate fails and performance is not approved. Work continues with
a separate profile of the pauses before tests unrelated to performance;
the full integrated lifecycle is still pending.

`cpu-profile-shared-health-1` confirms the absence of `valid`, `acquire` and
`backbuffer` in the measured calls. In 30.63 s of the engine thread, the
waits are split mainly between replay (2.89 s) and audio (2.56 s).
The analysis of the earlier physical stretch (`stutter-analysis.json`) records
589 game updates longer than 33.4 ms; the 33 GC slices add up to
155.57 ms and none exceeds 7.98 ms. The stutter is not attributed mainly
to GC. The separate profile is diagnostic and does not vouch for FPS.

The deferred replay flush keeps the original formation and appending of
records, but moves the explicit `flush` of each turn to after
recording the frame on the CPU, before submitting its GPU commands. GL keeps its
immediate execution. All requests and a bounded queue are kept;
the logger's destructor and the metadata publication drain its stream. The
main loop fallback drains when nothing is drawn. Until that drain,
the last bytes may stay in the stream's buffer within the frame.
The eight CPU checks (`deferred-replay-probe-1.json`) pass content,
order, multiplicity, destruction, error, reentrancy and queue limit.
`performance-deferred-replay-diagnostic-1` keeps 306 units, simulation at
99.26 %, zero backlog, zero ETW losses and a clean exit 0. It obtains 35.08 physical
FPS and 37.59 engine; p95 of 66.79 ms, p99 of 133.53 ms and 116 pauses
longer than 100 ms. It improves smoothness, but does not meet its gate.

`portable-switch-o3` is prepared separately, an adaptation of the `switch`
dispatch of [Mozilla D224656](https://phabricator.services.mozilla.com/D224656) (part 5
of the same bug 1922981), keeping D224659. The full patch is archived with
SHA-256, author and reviewer. The bodies of all opcodes, the interrupts,
the coverage, the public headers and the original scripts are kept;
the address tables unused in that variant are omitted. The motivation is
to check the inlining of the IC interpreter described in the
[PBL design](https://github.com/mozilla-firefox/firefox/blob/main/js/src/vm/PortableBaselineInterpret.h),
since the profile still shows both functions separately. The build of the
object passed in 306.32 s; the library archive is
`dd057a4ea34a1a5028660d9992bef5b749c9116a3502828611a240c2df07b642`
(`portable-switch-build-1.json`). The same 12 CPU checks of the original
API pass on fixed and switch: hot properties and calls, unwind and
finally, typed array bits, live roots during GC and sort with a native
callback, in three contexts (`portable-vm-probe-{fixed,switch}-1.json`). They are not
simulation checkpoints nor FPS evidence. The game was linked/packaged;
its final map no longer contains `ICInterpretOps` as a separate function. The
physical measurement `performance-portable-switch-diagnostic-1` obtained 35.72 presented
FPS and 38.57 engine; physical p95 of 66.79 ms, p99 of 133.52 ms and 114
pauses longer than 100 ms. It kept 306 units, simulation at 99.31 %, zero
backlog, zero ETW losses and a clean exit 0. One diagnostic does not vouch for a
statistical improvement over 35.08 FPS; the median of turn updates
stayed near 29.9 ms. Smoothness is not considered fixed.

`cpu-profile-portable-switch-1` confirms that the replay wait disappeared.
In 31.05 s of the engine thread, the unified interpreter consumes 4.01 s self,
similar to the two earlier interpreters added together. The audio waits add up to
about 4.67 s. The browser thread attributes 5.31 s self to `writeBuffer` in
a 31.91 s window. It is an instrumented diagnostic, not an FPS test.

The next candidate uses `webgpu-upload.mjs`: reusable `MAP_WRITE | COPY_SRC`
buffers, GPU copies before the original command buffer and remapping after
submission. The pool is bounded to 64 MiB; when it is busy the original
`writeBuffer` is used. Destruction ignores late completions and frees
the buffers. 22 Node checks pass (17 existing and 5 new), including
exact snapshots, order, reuse, saturation, mapping failure and shutdown.
An optional 12 frame probe compares 1,536 bytes through readback on the real
GPU, forcing both paths with a 64 byte pool. It runs before loading
the match and its warmup; it is not used within the FPS stretch.
`performance-mapped-upload-diagnostic-1` passed that GPU probe (1,536 exact bytes,
11 reuses and both paths active). In the game, the pool kept four
buffers / 64 MiB, without mapping failures; it transferred about 82.71 GB
additional through the mapped path between the initial/final observations and 8.57 MB
through fallback. That observation covers warmup and the measured stretch. The diagnostic
obtained 35.52 physical FPS against 40.98 engine; p95 of 66.82 ms, p99 of
133.60 ms and 127 pauses longer than 100 ms. It kept 306 units, simulation at
99.14 %, zero backlog, zero ETW losses and a clean exit 0. The improvement of the
engine counter does not vouch for a presentation improvement; this candidate does not
fix the smoothness. Gates unrelated to performance have not been resumed.

The next candidate fragments the stream after complete commands
(threshold of 1 MiB of data or 32,768 binary words), without changing order,
draws nor bytes. The browser consumes the FIFO queue in tasks with a budget
of 4 ms; each task may finish the current package before yielding. C++
keeps its snapshot until consumption is confirmed, including failure and
cancellation. The frame sample follows its `Present` in the same queue so as
not to advance the telemetry. 28 Node checks pass, including order,
cancellation without freeing an active payload, propagation of the first error and
state/binaries split across packages. `Device.cpp` and `main.cpp` compiled.
The idempotence of the preparation patch with the replay fallback was fixed;
a second preparation produced no changes nor recompilations. The
candidate was linked and measured in `performance-streamed-dispatch-diagnostic-1`:
35.12 physical FPS against 38.93 engine; p95 of 66.80 ms, p99 of 133.56 ms
and 121 pauses longer than 100 ms. It kept 306 units, simulation at 99.28 %,
zero backlog, zero ETW losses and a clean exit 0. In the
warmup/measurement observations it added 27,961 batches and 9,172 frames/submissions, about
3.05 batches per frame. There were no mapping failures nor new fallback bytes in
that interval. It still does not improve smoothness; the queue wait is profiled
separately before tuning its granularity. It is not a performance approval.

`cpu-profile-streamed-dispatch-1` changes the diagnosis: the total wait of the
engine thread drops to 0.69 s in 31.10 s (main audio, about 0.41 s). No
dominant queue wait is observed. The interpreter takes 4.66 s self and
`Context::UploadBufferRegion` 3.84 s; the next change targets that copy,
without blindly tuning the queue limit. The browser thread has 14.19 s
idle out of 31.79 s; `commands` accumulates 14.90 s / 3,045 calls and `present`
0.88 s / 995 calls. The profiles do not vouch for FPS.

`CommandData.h` copies the aligned neighbours directly from the buffer's
mirror into the owning package. It removes the temporary vector that was
zero-initialized and copied before being copied again into the package. It keeps
the padding, offsets and independent snapshot. `command-data-probe-1.json`
passes five checks, including 200,464 differential comparisons with
the earlier producer for all buffer ranges from 0 to 65 bytes and the
four prefix alignments. It includes empty ranges, neighbours and rejection of
invalid limits. The C++ compiled, linked with exit 0 and was packaged;
it also passed the Node syntax check of the modified modules.
The first launch of the measurement did not run because the automatic
permission review hit a usage limit. When the operator resumed,
the same launch through the normal approval path did run:
`performance-direct-upload-diagnostic-1` passed the GPU probe, but aborted before
finishing the warmup with `memory access out of bounds` in the worker.
The resolved stack is kept in `resolved-worker-error.json`: it starts at
`js::jit::GetPropIRGenerator::tryAttachStub`, followed by `TryAttachStub`,
`DoGetPropFallback` and `PortableBaselineInterpret`. The last sample was
frame 3,562 / tick 419. There were zero ETW losses, but no valid FPS measurement
nor normal shutdown. The stack does not by itself demonstrate the cause of the invalid access.
The repetition of the same binary, without introducing another optimization,
`performance-direct-upload-diagnostic-2`, finished with exit 0: 35.58 physical
FPS against 41.56 engine, physical p95 66.79 ms, p99 133.54 ms and 113
pauses longer than 100 ms. It kept 306 units, simulation at 99.16 %, zero
backlog, zero ETW losses and a clean shutdown; it passed again the 1,536 bytes of the
GPU probe. The intermittent failure of the first attempt still has no demonstrated cause.
The increase of the engine counter does not vouch for an improvement in physical smoothness.

The VM CPU probe was extended with getters that force GC, changes between
own/inherited properties and proxies at the same callsite. The 15
checks pass in three contexts on both fixed and switch
(`portable-vm-probe-{fixed,switch}-2.json`). It does not reproduce the match's
exception nor declare it fixed. The analysis of the streamed profile attributes
5.54 s of the 11.19 s of `CGame::Update` to `CAIWorker::PerformComputation`:
the original AI runs on the same thread, despite the name worker.

The next candidate aligns each `Present` with a distinct RAF callback.
The FIFO keeps commands, resources and the telemetry sample behind their
presentation; it does not repeat images nor skip game frames. The C++ payload
stays alive until its consumption. If the window loses visibility, it is drained without
waiting for RAF; cancelling a callback rejects its pending work only once.
37 Node checks pass, including the three new ones for order, cancellation
and visibility (`present-pacing-cpu-1.json`). It compiled and linked with exit 0;
the package passed the Node syntax check. Its fullscreen measurement
`performance-present-pacing-diagnostic-1` obtained 32.20 physical FPS against
34.17 engine, p95 66.74 ms, p99 116.94 ms and 113 pauses longer than 100 ms.
It kept 306 units, simulation at 98.95 %, zero backlog, zero ETW losses
and a clean exit 0. It is withdrawn for worsening the mean without fixing the p95;
the exact code and hashes stay in its `source` directory. The
earlier FIFO consumption was restored, without an additional Present wait.

The VM probe now adds properties/prototypes changing during an active
incremental GC. `portable-vm-probe-switch-3.json` passes 18 checks
in three contexts and records 6,211 incremental yields. It does not reproduce nor
declare fixed the match's intermittent failure.

The next candidate skips uniforms only when their bytes are
identical to the last write of the same slot in the same package. The cache
is cleared when each package is submitted; another context may modify the shader
between packages without invalidating this premise. The data limit is 2 MiB and a
write that does not fit is still sent. `uniform-cache-probe-1.json` passes
eight checks, including 32,768 differential draws, partial
writes, kept neighbours, -0, NaN payloads, length changes and the
boundaries between packages/contexts. 1,110 identical writes were skipped
in that probe; it is not a hit rate of the game. The 34 Node checks
of the restored path pass. It compiled and linked with exit 0; the measurement
`performance-uniform-cache-diagnostic-1` finished with 35.50 physical FPS against
39.77 engine, p95 66.79 ms, p99 133.59 ms and 113 pauses longer than 100 ms.
It kept 306 units, simulation at 99.07 %, zero backlog, zero ETW losses,
exact GPU probe and a clean exit 0. It does not demonstrate a presentation improvement.
The separate profile `cpu-profile-uniform-cache-1` finished with 15 profiles,
physical focus/fullscreen, original hierarchical snapshot `/logs/profile.txt`
saved after the CDP sampling, without opening the overlay, and a clean exit 0.
The engine thread accumulates 30.89 s: 11.24 s in `CGame::Update`, 18.46 s in
`RenderFrame` and 1.66 s of waiting (main audio 0.84 s, checks 0.35 s).
`UploadBufferRegion` drops from 3.84 s to 1.17 s self after the direct copy;
that saving is not attributed to the uniform cache. `SetUniform` self is
0.60 s, and 1.56 s in the browser; `commands` adds up to 15.77 s / 3,039 calls
for 993 frames. It does not demonstrate an improvement from the cache: it is withdrawn, keeping
code, header, probe and hashes in its `source` directory. Work returns to the
direct copy producer without that cache for the next VM experiment.
These profiles do not measure nor vouch for FPS.

`portable-underflow-o3` is prepared, a limited adaptation of Mozilla D224676
with patch, author and provenance archived. It only fills with `undefined`
the omitted formal arguments of scripted calls and lets the
native functions receive their real short argc; it keeps the argc descriptor,
the fallback for constructors/cross-realm/spread, the other opcodes and the
public headers. The control VM archive passes the 21 checks,
including optional arguments, `arguments.length`, root identity,
exceptions/finally with GC and native calls with a declared arity greater than
the real one (`portable-vm-probe-switch-4.json`, 9,212 incremental yields).
The new VM compiled in 312.90 s, with archive SHA-256
`eb50702e3870c6f37a163671ac4617771067f1b5ef013ea7a9b19b69d8058a82`
(`portable-underflow-build-1.json`). It passes the same 21 checks, with
9,207 incremental yields (`portable-vm-probe-underflow-1.json`). The restored
renderer C++ compiled, linked and was packaged with this VM. Its
fullscreen measurement `performance-portable-underflow-diagnostic-1` finished
with 34.83 physical FPS against 39.24 engine, p95 66.81 ms, p99 150.11 ms
and 117 pauses longer than 100 ms. It kept 306 units, simulation at 99.33 %,
zero backlog, zero ETW losses, exact GPU probe and a clean exit 0. It is withdrawn
for not demonstrating a physical improvement; its compiled code and provenance stay
in the `source` directory, plus the builder's optional profile. The
next test returns to `portable-switch-o3`. The new measurements also archive
their symbols and the link report before opening Chrome, in addition
to the runtime hashes, to resolve an exception with its exact binary.

The next candidate removes the synchronous result of `stageTexture` in
C++. A binary opcode keeps id, format, region, mip, layer and bytes in the
owning package; when it is consumed, JS uses the same aligned staging and the
same ordered `copyBufferToTexture` as before. This way there is no need to drain the
previous frame's queue just to obtain the temporary staging id. It is a
performance hypothesis, not yet a measured improvement. 36 Node tests pass
(`texture-command-cpu-1.json`), including the differential comparison of
the seven formats/paths, independent snapshots, order between two uploads
and draws and rejection of ranges before creating resources. A small GPU probe
will check two ordered updates in mip 1 / layer 2 through readback
of private textures, before creating the match/warmup; it includes R8, RGBA and
BC1 if enabled. The C++ compiled, linked and was packaged with the control
VM. `performance-async-texture-diagnostic-1` passed the GPU probe: 76 bytes
of exact texture data in R8, RGBA and BC1, two updates, mip 1 / layer 2,
plus the 1,536 bytes of the buffer pool. It measured 35.78 physical FPS against
39.97 engine FPS, p95 66.79 ms, p99 141.03 ms and 117 pauses longer than 100 ms.
It kept 306 units, simulation at 98.94 %, zero backlog, zero ETW losses
and clean exit 0. It does not demonstrate a smoothness improvement over the direct
copy control. It is kept as an experimental candidate while the cost of the
exception runtime is checked; performance is not considered solved.

The CPU-only comparison between the SDK's `-fexceptions` and `-fwasm-exceptions`
passed six checks per mode: catch/rethrow/RAII, propagation
through a unit without exceptions, `exception_ptr` between pthreads,
libpng longjmp and an indirect-call checksum. The reproducible report
`exception-runtime-probe-3.json` explicitly uses the matching longjmp
mode: `emscripten` in the control and `wasm` with native exceptions.
The median of three synthetic loops of two million calls was
165.73 ms against 7.71 ms. It does not represent the game's FPS nor allow
predicting a speedup of that magnitude in the match. The earlier attempt
to combine native exceptions with JS longjmp was rejected by the SDK and
is kept as failed (`exception-runtime-probe-2-incompatible.json`).

An isolated rebuild of the application's 482 C++ units was started
with `-fwasm-exceptions -sSUPPORT_LONGJMP=wasm`, keeping `-O2`, the
`portable-switch-o3` VM, and the original scripts, graphics and clock. No engine
objects compiled with the earlier mode are reused. A symbol audit
rejects cached dependencies with incompatible handlers before compiling
and before linking. It detected a single libcurl `hostip.o` object with JS
longjmp; it was recompiled separately with the same configuration and O2 flags, replacing
only that member in a private copy of the archive. The original library
stays intact. The native copy has SHA-256
`b539fb0badf6ca077bfeac1f0893f912e792798afd7020cf55e7bc61d0872b92`.
The corrected audit and the curl preparation pass; the native tag
`__c_longjmp` is a weak defined symbol and must not be searched for only among the
undefined symbols.

The compilation passed all 482 units, with no skipped or failed objects, in
`application-wasm-eh/compile-report.json`. All its commands include the
native exception mode; the cached dependencies pass the audit.
Its first attempt detected a generated input missing from the isolated tree
(`build/build_version/build_version.txt`), after 113 correct units.
The preparation was fixed by copying the same file from the control, with its hash
recorded, and it was resumed using the verified objects. A later
process stopped being active with 360 units recorded; its
interrupted report was kept and it was completed from those objects, without attributing an
unproven cause to the interruption.
The link finished with code 0 and the package was verified against its hashes.
The generated runtime no longer contains the control's 115 JS `invoke_*` wrappers;
this verifies the mode selection, it does not vouch for performance. The module is
14,585,115 bytes against 15,571,358 for the control. The compilation,
audit and link evidence is in `native-exception-build-1`. The link and the package
have separate directories (`linked-wasm-eh` and `application-phase4-5-wasm-eh`).
The control package keeps the earlier runtime. The diagnostic
`performance-wasm-eh-diagnostic-1` completed 120 s of warmup and 120 s
measured: 35.23 physical FPS / 39.31 engine, physical p95 66.79 ms and engine
56.78 ms, physical p99 136.84 ms and 112 intervals >100 ms. It kept 306 units,
simulation at 99.21 %, zero backlog, zero ETW losses, both
transfer probes exact and exit 0 without workers or errors. **It does not fix the
stutters and is not adopted as a performance improvement**. There were no compilers or
profilers during the capture. SDK references:
[exceptions](https://emscripten.org/docs/porting/exceptions.html) and
[setjmp/longjmp](https://emscripten.org/docs/porting/setjmp-longjmp.html).

The separate profile `cpu-profile-wasm-eh-1` passes with fullscreen/focus and a clean
shutdown. The engine thread is `cpu-5.cpuprofile`, window of 31.35 s: 4.38 s
self in PortableBaseline, 1.41 s of clock and 6.66 s of futex wait. Of the
latter, 4.08 s belong to `CSoundManager::al_check` and 2.18 s to
`CSoundBase::IsPlaying`. Game::Update accumulates 10.37 s and RenderFrame 19.66 s
inclusive; RenderFrameImpl 12.85 s (they are nested scopes, not to be summed).
In the browser, the commands consumed 18.47 s for 1,167 frames in
33.79 s instrumented. They are diagnostic times, not accepted FPS.

The next candidate shares only the AL error word. The SDK's `alGetError`
reads and clears the current error; it does not query a device nor modify
audio. An atomic cell holds the error and the presence of a context; the
errors of inactive contexts are retained by object identity. A single
exchange publishes each context change and keeps any error not yet
consumed. The query can run on the pthread without waiting for
the browser to finish encoding WebGPU commands. The other audio
calls, parameters, playback and clock keep the SDK paths.

`audio-error-probe-1.json` passes **15 checks per mode** against the
real SDK functions in Node: missing context, codes/reset, inactive
errors, two readers, repeated selection, concurrent context changes,
memory growth and ID reuse. It uses synthetic context records
without opening audio: it does not vouch for hearing nor match performance.
The median of 10,000 reads was 510.62 ms in the control and 1.24 ms with the
shared cell; it does not predict FPS either. The new build keeps by hash the
482 native objects and adds a platform unit; correct compilation
of 483 units and verified link/packaging. The physical diagnostic
`performance-audio-error-diagnostic-1` finished without other simultaneous tests:
37.20 physical FPS / 43.63 engine, physical p95 66.74 ms and engine 51.86 ms,
physical p99 133.48 ms and 116 intervals >100 ms. It kept 306 units,
simulation at 99.14 %, zero backlog, zero ETW, exact GPU probes and exit 0.
Real audio kept one context and two sources playing at the end of
the capture. There were no engine or GPU errors. The mean is higher in this
stretch, but **smoothness still fails**; it does not pass the gate nor the phase.
The sources and reports were kept in
`audio-error-build-1`. Reference implementation:
[OpenAL of SDK 4.0.10](https://github.com/emscripten-core/emscripten/blob/4.0.10/src/lib/libopenal.js).

The offline analysis `stutter-analysis.json` of that diagnostic separates 599
frames with turns and 4,634 between turns, with no ID gaps. Game::Update has
medians of 26.90 and 1.09 ms respectively; the p95 of the turns is 104.59 ms.
597/599 receive intervals with turns exceed 33.4 ms, against 33/4,634
between turns. They are correlations between original duration and ordered receipt,
not a direct mapping of IDs to PresentMon nor exclusive CPU time.
The profile `cpu-profile-audio-error-1` passed. Engine thread `cpu-6.cpuprofile`,
31.32 s: there is no longer wait attributed to alGetError; IsPlaying waits 5.17 s,
PortableBaseline has 5.33 s self, Game::Update 11.79 s inclusive and
AI PerformComputation 6.22 s inclusive (nested scopes). The browser
encoded commands for 17.60 s for 977 frames / 34.03 s instrumented.
The next candidate places the same audio maintenance call
after enqueueing Present and the ordered frame notification. The
private copy of main/Device passed after reproducing the includes of the control
container; the first preparation failure due to missing Boost was kept.
The isolated audio-after-present link and package passed. Its measurement
`performance-audio-after-present-diagnostic-1` finished with 32.97 physical FPS /
36.36 engine, physical p95 66.78 ms and engine 53.36 ms, physical p99 133.46 ms
and 109 intervals >100 ms. It kept 306 units, simulation at 99.36 %, zero ETW,
both GPU probes exact, audio playing and a clean shutdown. It is withdrawn:
the mean was lower and it did not fix the pauses. Its sources, patch and reports
are kept in `audio-after-present-build-1`; the reference candidate is still
shared-al-error at 37.20 FPS, with audio before the final Flush.
The private VM with counters of unimplemented CacheIR compiled and passed
21 CPU checks, 9,188 incremental GC yields and its three exports.
They do not change the handlers and are not eligible for accepting FPS. The isolated link and package
passed and `cpu-profile-cache-count-1` finished: 3,885 unimplemented
dispatches / 32.78 s external; largest counters LoadUndefinedResult 839 and
GuardMultipleShapes 668. They are not exclusive costs nor guard failures.
Engine: 4.95 s self in the interpreter and 5.60 s of IsPlaying wait / 31.39 s.
The broad backport was not applied. The
physical runner rejects packages with `diagnosticOnly` VM provenance.

On moving audio to another thread: `CSoundManagerWorker` already exists, but
music/ambient maintenance still queries IsPlaying from the game
thread. Isolating it requires a queue and lifetime control of the items; moving the
call as-is keeps shared mutexes and may introduce races.
A private partial experiment was implemented: `audio-worker` sends those
checks to the existing worker, with per-generation tickets and batching;
it keeps the stream maintenance deadlines. It passes 10 checks of
the queue in Wasm pthreads and compiled 483 units (480 objects kept,
two audio units and the AL cell); link and package passed.
`cpu-profile-audio-worker-1` passes: on the engine thread there are no
IsPlaying wait samples (before 5.17–5.60 s / about 31 s); total futex 3.71 s / 30.80 s,
including command backpressure. The original music pause/resume and stop/
restart passed, checked after the profile against real
SDK states, and a clean shutdown. The 120+120 s physical diagnostic finished:
34.33 physical FPS / 37.90 engine, physical p95 66.85 ms and engine 59.36 ms,
132 pauses >100 ms, 306 units, simulation at 98.95 %, zero backlog and ETW,
exact probes, empty errors and exit 0. It does not improve on the control in this sample;
it is not adopted as a performance solution nor is causality shown by a
single run. The offline analysis again associates the pauses with turns:
Game::Update median 31.81 ms and p95 117.11 ms. The 37.20 FPS control is kept.
See the continuation document for changes, preparation and WebAudio limits.

The fixed candidate keeps the same SpiderMonkey version and adapts only
the enum assignment of Mozilla D224659, with patch and provenance archived in
`wasm/patches/upstream`. Its compilation does not demonstrate that it solved the
combat exception. By instruction of the operator, tests unrelated to performance
are paused until at least 30 real FPS is reached.

`cpu-validation-6.json` passes 50 CPU tests: 24 renderer, 15
contracts/security/snapshots and 11 presentation. It includes the real duration,
uncertainty and refusal to accept two loads from an isolated diagnostic.

The portable row corresponds to 120 s measured after 120 s of warmup,
306 units, valid physical fullscreen/focus, zero lost ETW events and
shutdown without workers. It fails: 8.97 engine FPS and engine p95 294.81 ms.
It is not adopted as an improvement nor is the difference attributed only to the interpreter:
this candidate also includes the new clock and a longer stretch.

The portable O2 variant recompiles only `PortableBaselineInterpret.o`;
it keeps the rest of the archive and records the full provenance. It uses the
same 120 + 120 s stretch. It improves over portable O1, but still fails:
12.11 engine FPS, engine p95 236.41 ms and 384 physical intervals longer
than 100 ms. The first O2 attempt aborted before measuring due to foreign physical focus;
the second verified fullscreen/focus, zero lost events and a normal shutdown.

`cpu-profile-portable-2` confirmed physical focus and effective execution of
`js::pbl::PortableBaselineInterpret`: 12.33 s self and 20.19 s inclusive
in a window of 32.38 s; `CGame::Update` accumulated 24.08 s. The first profile
failed before collecting data because Windows did not activate the browser. The
harness now verifies the physical foreground before moving the mouse. The
automatic activation attempts hit access denied when attaching the
process input to the foreground window. The experimental click/topmost
fallback was removed: the operator offered to activate Chrome and the harness
waits for that real activation before entering fullscreen. It never regains focus
during a measurement. Profiles are not FPS evidence.

The control `performance-o2-monotonic-diagnostic-2` uses the earlier hot O2
interpreter and the same corrected clock, 120 + 120 s and 306 units. It also fails:
11.49 engine FPS, engine p95 251.01 ms and 378 physical intervals longer
than 100 ms. Valid fullscreen/focus, zero lost ETW events and exit 0.
The first attempt aborted before measuring due to foreign focus. One stretch of each
variant does not allow concluding statistical significance between 10.58 and 10.93 FPS;
both are far from the contract. The earlier clock is not restored to
artificially raise the frame count at the cost of simulation time.

The original SpiderMonkey library keeps `MOZ_OPTIMIZE_FLAGS=-O`.
`phase4-5-scripting-build.py` allows recompiling five original hot units
at `-O2` or `-O3`, without code changes, JIT, fast-math or
floating-point contraction. It keeps the base archive and records commands, hashes
and archive membership. The trial `performance-scripting-o3-diagnostic-1.json`
regressed to 11.76 presented FPS, p95 233.60 ms and simulation at 74.67 %;
O3 is not adopted. The O2 variant passed the ten advanced checkpoints up to
780,000 ms, including research and trade, against the original native:
`webgpu-advanced-serialized-o2-1/report.json`. The original simulation bytes,
the full debug, the non-local debug, the GUI and the commands match.

The official Portable Baseline Interpreter option of the
same SpiderMonkey version is also being prepared, without changing scripts or simulation. The build
runs on a case-sensitive Linux volume to keep distinct
`String.h` and `string.h`. The linker requires provenance hashes and the script
rejects changes to the public headers. `spidermonkey-portable/report.json`
recorded a correct compilation in 743 s, with no public header differences.
The compilation does not vouch for parity nor performance: both must be repeated
if this variant is selected.
Project reference: [Mozilla, Portable Baseline Interpreter](https://bugzilla.mozilla.org/show_bug.cgi?id=1855321).

The prepared WASM clock uses monotonic elapsed time instead of
inverting the smoothed frequency: the latter loses time on slow frames.
The native test `application-frame-time-probe-1.json` passes six cases,
including an 800 ms jump and conservation of 902 s with mixed intervals.
The fixed-frequency mode is kept only for functional comparisons.
In the portable diagnostic the browser confirmed `monotonic-elapsed` and the
deltas add up to 119,967.92 ms in an observed window of 119,936.40 ms. The clock
conserves time, but does not fix the slowness: the original TurnManager limits
catch-up to two turns and discards backlog on very long frames. That
original behaviour is kept. The physical measurement still fails.

`visual-native-comparison-portable-1.json` passes the three images, with
mean difference 0.190–0.192 and out-of-threshold fraction 0.00431–0.00440.
This visual parity at 10,000 ms does not replace the advanced simulation
checkpoints of the final candidate.

The diagnostic `cpu-profile-binary-arenas-fullscreen-1` did confirm fullscreen,
real Windows focus and internal 1920 × 1080 rendering on the physical
2560 × 1080 screen. It recorded approximately 8.7 engine frames/s in the short stretch,
still insufficient and with no acceptance value. The profiles marked
`backgroundFunctional` ran without requiring foreground and do not vouch for
physical presentation nor FPS. Fullscreen tests are resumed at the request
of the operator.

### Scope of the simulation checkpoints

`Engine.DumpSimState()` includes local rendering entities. In the territorial
capture at 400,000 ms, twelve corpses differ only in their visual sinking;
`CCmpDecay` updates that state through `MT_Interpolate`. All non-local
components of the dump match exactly. The trial keeps its failed
result and both full dumps; the engine is not altered to match that effect.

The new check also keeps each original `.0adsave` and its
`simulation.dat` unmodified. It compares the SHA-256 of the full original
serialization, the dump of all non-local components, the GUI state and the
commands. `CComponentManager::SerializeState` and `ComputeStateHash` exclude
`ENTITY_IS_LOCAL` entities in the original code. The local and full debug
hashes are recorded separately, even when they differ. This separation
does not approve the visual parity of the animations: that requires its own review.

### Backend and shaders

- `source/renderer/backend/webgpu` implements the original interfaces for
  device, context, buffers, textures, framebuffer, shaders, pipelines and
  swap chain. It does not inherit from the dummy backend nor emulate GL calls.
- The engine keeps its loop on the pthread. The device belongs to the main
  thread and receives batched commands. There are uniform/geometry arenas,
  pipeline/binding caches, ordered staging and retirement after the queue completes.
- Presentation uses its own image. Acquiring the canvas texture,
  copying and submitting happen in the same task to avoid its expiry.
- WebGPU selection requests adapter/device asynchronously, requires
  COOP/COEP and records the effective backend, adapter, features and limits.
  It does not silently replace WebGPU with GL.
- GLSL is adapted in a copy and converted offline with glslc,
  SPIR-V validation/reflection and Naga. The catalogue keeps defines, bindings
  and hashes. The package excludes old variants; it does not download compilers
  at startup. GL depth, positive-Y NDC and top origin
  of framebuffer textures are kept. Shadows run the original alpha discard.
- Parallax computes explicit gradients before its per-fragment branch.
  Water selects the invisible result after sampling to keep
  valid derivatives. Lighting and reflection are not removed.
- Skinning restores the reflected readonly access. If two outputs share
  an original buffer, it uses independent outputs and copies their exact ranges.
- Small BC textures incompatible with WebGPU are decoded to RGBA in
  memory, keeping logical dimensions, mipmaps, alpha and original files.
  The palette is rounded to 8-bit precision and has specific tests.
- The clock services the pthread's SDL callbacks every frame, even if RAF
  has already signalled: before, they could go unserviced when the whole interval was consumed.
- Release finishes even if draining fails; it cleans up resources,
  bindings and retired caches after the submitted work.

Simulation, AI and art assets are not modified. The frozen WebGL build
stays in `wasm/dist/webgl-baseline-phase4-5`, with initial hashes in
`evidence/phase4-5/baseline/webgl-baseline.json`.

## Toolchain and reproduction

Emscripten 4.0.10 and the phase 4 base image are kept. The probes use
Emdawnwebgpu `v20250531.224602`, with SHA-512/SHA-256 pinned in
`wasm/docker/phase4-5-toolchain.lock.json`. Recorded toolchain image:
`sha256:c7ccd7e877e731f3beadfd6fa9a73d823a96cc2ff74d1723d4e5832cb7835ffb`.
Shader versions/hashes: `Dockerfile.phase4-5-shaders` and
`wasm/build/phase4-5/shaders/tools`.

Incremental reproduction requires the prepared image, objects and sources
of phase 4; it is not yet a clean build independent of them.
The link writes separately and packaging verifies hashes before serving it.

From the root, in PowerShell:

```powershell
./wasm/scripts/docker-phase4-5.ps1 -Action all
node --test wasm/scripts/test-renderer-session.mjs wasm/scripts/test-webgpu-textures.mjs wasm/scripts/test-webgpu-lifetime.mjs wasm/scripts/test-webgpu-formats.mjs
./wasm/.venv-phase3/Scripts/python.exe -m unittest discover -s wasm/scripts -p 'test_phase45_*.py'
```

Builds: two CPUs, up to 8 GiB and reuse of phase 4 objects.
Engine/shaders and prepared probes compile without network. The engine backend
uses the WebGPU JS API; the Emdawn probes only vouch for API/ABI and callbacks.

## Verified evidence

| Check | Result and scope |
|---|---|
| Six legacy/Emdawn C++ probes, main/pthread | Compile and pass; API/ABI, not the game |
| `engine-startup-visible-6/runtime.json` | Menu visible on NVIDIA, 475 frames after settling, normal shutdown without GPU errors |
| `canvas-readback.json` | Orientation, scissor outside the target and staging lifetime approved with GPU readback |
| `engine-load-visible-11/runtime.json` | Mainland, 797 frames, tick 55, 64 pipelines, original capture and zero GPU errors |
| `shader-modules-2.json` | 1,116 WGSL modules validated by a real browser, zero errors |
| `shader-modules-3.json` | 2,118 WGSL modules validated on NVIDIA Ampere, zero errors; catalogue before the water extension |
| `shader-modules-4.json` | 2,259 modules of the extended catalogue, including the sampler adaptation; validated on NVIDIA, zero errors |
| `border-readback-1.json` | 12 GPU readbacks: nearest, bilinear, trilinear and implicit gradients; transparent, opaque black and opaque white borders |
| `input-events.json` | Original keyboard events and hotkeys consistent: Shift+Space pauses; Pause resumes |
| Node | 16 tests pass: session, formats, BC and lifetime |
| Benchmark contract | 7 tests pass: rejects partial data, short duration, duplicate repetitions, different backend/adapter, errors, slow simulation, growing backlog and dirty shutdown |
| Runner safety | 2 tests pass: Plan mode creates no processes; busy ports are rejected before launching a browser |
| `cpu-validation-2.json` | 35 tests pass; includes 10 presentation tests and rejection of a fast compositor with a slow renderer |
| `cpu-validation-3.json` | 38 tests pass: 17 Node, 11 contracts/security/snapshots and 10 presentation. CPU validation only |
| `cpu-validation-5.json` | 46 tests pass: 24 Node, 11 contracts/security/snapshots and 11 presentation; includes binary transport, arenas and state cache |
| `automated-native-systems-1/report.json` | Original research, town phase, two markets and trade income; all checkpoints up to 780,000 ms and exit 0. Does not validate audio: the native device reported disconnection |
| `automated-native-capture-2/report.json` | Original diplomacy, infantry production and effective capture of the market; checkpoints up to 400,000 ms and exit 0 |
| `capture-local-decay-diagnosis.json` | The dump difference at 400,000 ms affects 12 local corpses; all non-local components match exactly. Diagnosis, not approval of binary parity |
| `native-capture-serialized-1/report.json` and `webgpu-capture-serialized-1/report.json` | Capture approved: `simulation.dat`, all non-local components, GUI and commands match at 10,000, 200,000 and 400,000 ms; correct final owner and clean exit. The local visual dump differs, as recorded separately |
| `automated-validation-5/original-input/report.json` | Pause, multiple selection, groups, click rally, camera, minimap, movement; exit 0 and zero orphan workers |
| `automated-validation-6/original-audio-persistence/report.json` | Original audio decoded/playing, mute, volume 0.4, persistence and two clean shutdowns |
| `automated-validation-6/three-matches/report.json` | Three original matches: load, pause/resume, defeat, summary, menu; exit 0, without errors or orphan workers |
| `chrome-validation-2/original-input/report.json` | Full input walkthrough in Chrome: 1080p fullscreen, selection, groups, rally, camera, minimap and orders; clean shutdown |
| `chrome-validation-2/original-combat-victory/report.json` | Original combat against Petra, 50 casualties, defeat/victory and zero GPU errors |
| `chrome-validation-2/original-audio-persistence/report.json` | Playback, mute, persisted volume and two clean shutdowns in Chrome |
| `chrome-validation-2/three-matches/report.json` | Three full walkthroughs in Chrome, exit 0 and zero orphan workers |
| Standalone runners | Plans/syntax checked without windows or GPU work; full execution pending |

Earlier failures are kept: missing variants, scissor, BC dimensions,
inactive resources, derivatives and aliasing. The initial AMD `gcn-5` probes
were not verified on the operator's desktop and are not compared with
NVIDIA. Earlier technical counters are not presented as displayed FPS.

The full input test passes in `automated-validation-5`. The first
selection attempts were blocked by the
original pause overlay: the test now resumes before selecting, without
modifying that game behaviour. While testing the rally point a missing
`IGNORE_LOS=1` variant appeared. The catalogue was extended: 669 scene variants
compile without failures and the full walkthrough passed with the updated package.
Fatal aborts now stop the clock, workers, audio and GPU resources.
The later combat test detected another missing advanced water combination.
The original `RenderFancyWater` options are extended, keeping
reflection, refraction and depth. The demo scenarios require selecting
the original «All Maps» filter before importing settings; the harness now does so
and requires that the GUI does not replace the requested map.

## Standalone execution, without controlling the desktop

By instruction of the operator, Computer Use is not used and the performance
measurements are separated from the captures. The tests run from processes in the user's real session,
with Playwright/CDP and checks of the focus and of the physical window. The agent
runs the tests; no manual intervention is required for each match.
The same runners can be reproduced from the terminal:

```powershell
./wasm/scripts/run-phase4-5-offline.ps1 -Mode Functional
./wasm/scripts/run-phase4-5-offline.ps1 -Mode Performance
```

`-Mode Plan` checks plans without windows, matches or GPU. `-Mode All`
runs the functional tests first and only continues if they pass.

The functional suite generates new native research/trade
and capture references, compares full checkpoints and WebGPU commands, and walks through input,
combat, audio/settings and three matches with shutdown. It uses APIs from code
and a programmatic click on the visible fullscreen button, without a Computer Use helper. It saves functional
captures; it does not measure performance nor approve visual parity on its own.

The benchmark runs three backends, two loads and three repetitions in series:
18 measurements with 120 seconds of warmup and 900 of capture, about 5 h 6 min
plus preparation. To measure only WebGPU first (six measurements):

```powershell
./wasm/scripts/run-phase4-5-offline.ps1 -Mode Performance -Backends webgpu
```

The runner presses Fullscreen and requires system fullscreen state,
monitor coverage, real focus and 1920×1080 attachments.
During measurements there are no captures, video, overlays, parallel builds
nor desktop automation. PresentMon CSVs, hashes,
hardware inventory, settings, simulation, workers and summary are kept. Observed focus
loss, incomplete execution, growing backlog or dirty shutdown are rejected. Do not switch
applications during a measurement. Closing applications that compete for the GPU is
an operator requirement that the script does not guarantee automatically.

Results: `docs/wasm/evidence/phase4-5/functional-*` and `standalone-*`.
The check plans contain only `plan.json`: they do not vouch for executions.
The summary never marks `phase45Accepted=true`, even if it passes the FPS gate.

The comparative profile keeps `vsync=true`, set by the frozen WebGL
launcher, and applies it to the native build. It is a declared profile different from the
contract's default `vsync=false` and is not mixed with results of another
configuration. Check equality of settings and the active native GPU before accepting
the comparison: a GPU inventory does not prove which one each process uses.
The continuous 60-minute session is still pending.

The paired captures use the original renderer's F2 PNG output, not an
image of the desktop. The pixel contract was fixed before capturing them in
`wasm/scenario/phase4-5-visual-contract.json`: same tick, camera, settings and
1920×1080, maximum mean RGB difference 2 and at most 2 % of pixels with a
channel difference greater than 8. Images and metrics are kept; the thresholds
do not replace reviewing shadows and sampler borders.

The functional walkthrough now includes `verify-phase4-5-lifecycle.py` and
`verify-phase4-5-stability.py`: minimize/restore, resize, page
freezing, deliberate device loss and explicit restart, plus one
continuous hour with memory, resources, workers and periodic input. Freezing
a page is not equivalent to physically suspending the machine. Preparing these
walkthroughs does not vouch for having passed them.

`lifecycle-chrome-binary-2/report.json` passed fullscreen resize, emulated DPR
1.25/2, minimize/restore, freezing of a tab that was really in the
background and reactivation, deliberate GPUDevice loss, settings preservation
and explicit restart in WebGPU, without remaining workers. The first attempt
failed when artificially freezing the selected fullscreen tab: Chromium
stayed `hidden=true` despite having focus. The failure is kept and the real
walkthrough of returning to a background tab is now reproduced; focus is not emulated.

Only in that functional trial was the physical rectangle of the canvas read once,
with the foreground owner verified before and after. The image
`resumed-physical-canvas.png` showed the game, not grey. This readback is not
used nor imported in the performance meters. It also made it possible to detect
the stretching on ultrawide screens: the fullscreen container now
centres the canvas keeping 16:9, instead of distorting it. The internal image
is still 1920 × 1080. Physical suspension of the machine and physically moving
between monitors of different DPI are not vouched for through CDP emulation.

`multimonitor-pointer-aspect-1/report.json` passed the four edges again
with three monitors and a fullscreen canvas with corrected aspect ratio. It keeps
the original cursor, release with Escape and shutdown without remaining workers.

## Differences and pending limits

- `CLAMP_TO_BORDER` uses the renderer's portable filtering, with original colours,
  interpolation and mipmaps. The remaining textures keep hardware sampling.
  There are 12 GPU readback tests and offline validation of 851 adapted modules.
  Portable anisotropic filtering still needs the visual comparison of
  decals/overlays against GL hardware; it is not considered identical just because it compiles.
- MSAA 2 requests are converted to 4 and recorded. Compare equal effective
  values and their cost; this path uses MSAA 1/4.
- GPU timestamps are not supported and are reported as such. They are not equivalent to PresentMon.
- Optional formats depend on the device's enabled features.
  Float32 blending fails explicitly without its feature; Norm16 is not advertised.
- The cited lifecycle passes in Chrome; it must be revalidated in the final build.
  The one-hour memory test and the final repeated shutdown are still pending.
- A paired visual comparison of effects is missing, including shadows, shader
  coverage of those walkthroughs and full parity with native/WebGL.

## Status matrix

| Feature | WebGL | WebGPU |
|---|---|---|
| Original menu | Frozen baseline | Technically verified |
| Original Mainland | Earlier evidence with pending items | Load and simulation verified |
| Selection | Default | Experimental, without hidden fallback |
| Resources/presentation | Original backend | Integrated; technical tests approved |
| Shaders | Original path | Offline conversion and validated modules; functional coverage pending |
| Input | Pending items carried over | Full walkthrough approved |
| Matches/parity/audio | Pending items carried over | Audio, three matches, combat and advanced parity approved on recorded builds; repeat what is needed for the final candidate |
| Performance/stability | Reference with limits | Insufficient physical measurements; long acceptance and one-hour stability pending |

To close, the listed tests, sampler equivalence and review
of the results are missing. Only then can WebGPU be adopted as the default on
approved platforms. Human review is required before submitting changes;
no commits, issues or PRs are created.
