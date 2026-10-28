# Phase 4.5 continuation — 2026-10-18

Status updated on 2026-10-18, 23:04 America/Bogota:
**work paused by the operator; phase open; performance unresolved**.
First see the [current pause snapshot](phase-4-5-pause-2026-10-18.md),
with processes closed, package identity and the exact research point.
Do not start tests until the operator resumes. Priority when resuming: fix the stutter and
reach at least 30 physical FPS before tests unrelated to performance.
The contract also keeps physical and engine p95 ≤ 33.4 ms, real-time
simulation, and the original load and quality. The [results report](phase-4-5-results.md)
contains the history; the [document of the 17th](phase-4-5-pause-2026-10-17.md)
is a historical snapshot, not the current state.

## Current evidence

- Legacy reference control: `performance-async-texture-diagnostic-1`, Chrome in
  physical fullscreen, 1920 × 1080, 306 units, 120 s of warmup
  and 120 s measured. 35.78 physical FPS / 39.97 engine; physical p95 66.79 ms,
  p99 141.03 ms and 117 intervals >100 ms. Simulation at 98.94 %, zero backlog,
  zero lost ETW events and exit code 0. **Does not pass performance**.
- Native exceptions diagnostic: `performance-wasm-eh-diagnostic-1`, same conditions.
  35.23 physical FPS / 39.31 engine, physical p95 66.79 ms and engine 56.78 ms;
  112 intervals >100 ms. Simulation at 99.21 %, zero backlog, zero ETW and a
  clean shutdown. **Native exceptions do not fix the smoothness**.
- The shared AL error change measured **37.20 physical FPS / 43.63
  engine**, physical p95 66.74 ms and engine 51.86 ms, 116 pauses >100 ms,
  simulation at 99.14 %, zero ETW and a clean shutdown. It kept one context and
  two audio sources playing. `performance-audio-error-diagnostic-1`
  does not pass smoothness. Its offline analysis associates 597/599 intervals with turns
  of durations >33.4 ms; between turns it is 33/4,634. It is a correlation between
  receipts and Game::Update, not a direct attribution of physical frames.
- The GPU transfer probes passed before warmup: 1,536 bytes of
  buffers and 76 bytes of R8/RGBA/BC1 textures, two ordered updates,
  mip 1 / layer 2. 36 Node tests and 200,464 differential buffer packing cases
  pass. They are not equivalent to a full visual approval.
- The profile shows less self cost in UploadBufferRegion (3.84 → 1.17 s
  in different windows of about 31 s), with no demonstrated smoothness improvement.
- The experiments of Present with an extra RAF, a uniform cache and VM calls
  with omitted arguments were removed: they did not fix p95.
  Their sources and results are kept in their evidence directories.
- An earlier attempt of the control aborted with an out-of-bounds access in
  SpiderMonkey's GetPropIRGenerator/PortableBaseline. Another run of the
  same binary finished. The cause is still not demonstrated; the VM probes
  with properties and incremental GC do not prove that failure is fixed.

## Native candidate

The official `-fwasm-exceptions` mode of the Emscripten 4.0.10 SDK is tested with
`-sSUPPORT_LONGJMP=wasm`. It recompiles all 482 C++ units at O2 in a
private directory, keeping the rest of the control: the `portable-switch-o3` VM,
the renderer with asynchronous transfers, scripts, quality, load and clock.
The release link keeps the link-time O3 optimization already used by the control.

The CPU probe `exception-runtime-probe-3.json` passes six checks in each
mode, including RAII, rethrow, crossing a unit without exceptions, transport
between pthreads and libpng's longjmp. The synthetic loop gave medians of 165.73
and 7.71 ms; **it is not an FPS prediction**. The SDK rejects JS longjmp with
native exceptions; that failed attempt is kept separately.

The audit detected JS longjmp in a single libcurl member. `hostip.o` was rebuilt
with the original flags plus the Wasm mode and replaced in a
private copy of libcurl. The original cached archive stays intact.
The private preparation and the dependency audit pass.

The first compilation attempt stopped after 113 correct units:
`build/build_version/build_version.txt` was missing in the isolated directory.
It was a generated input of the control build. The builder now copies
exactly that input, records its hash and includes it in the identity of the
corresponding object. The compilation resumed keeping the objects
already verified. Neither the version string nor the game code was changed.
A later interruption left 360 units recorded and no active
container. `compile-report-interrupted-2026-10-18.json` was kept; the cause
was not demonstrated. The resume finished: **482 correct units**, with no
failed nor skipped ones, all in the native mode. The link passed with exit code 0;
the isolated package was verified and its first physical diagnostic finished,
without a performance improvement (see above).
The reports were archived in `evidence/phase4-5/native-exception-build-1`.

| Relative location | Use / status |
| --- | --- |
| `wasm/build/phase4-5/application-wasm-eh/compile-report.json` | `COMPILE_PASSED_NOT_LINKED`, 482 correct units |
| `wasm/build/phase4-5/application-wasm-eh/source` | Frozen sources of the candidate |
| `wasm/build/phase4-5/native-deps/curl-wasm-sjlj/report.json` | curl preparation approved |
| `wasm/build/phase4-5/native-dependency-audit.json` | Earlier audit approved |
| `wasm/build/phase4-5/linked-wasm-eh` | Correct link; native mode and Wasm longjmp |
| `wasm/dist/application-phase4-5-wasm-eh` | Native control measured; does not fix performance |
| `wasm/dist/application-phase4-5` | Legacy control, still served; not replaced by the candidate |

## Earlier research path (historical; current pause above)

The separate native profile (`cpu-profile-wasm-eh-1`) detected 4.08 s waiting on
`al_check` and 2.18 s waiting on `IsPlaying` in 31.35 s. A candidate is prepared
with only the shared OpenAL error; the other audio operations do not
change. It passed 15 CPU checks per mode against the SDK, without an audio
device, including races between readers/contexts and memory growth
(`audio-error-probe-1.json`). They are not a test of FPS nor of listening.

The `application-audio-error` build verifies the hashes of the control's sources,
headers and objects and keeps its 482 objects. It adds a single object
with the atomic cell and a frozen JS library; **483 correct units**.
The audio link and package passed and its diagnostic finished (see above).
The sources and reports are in `audio-error-build-1`; both earlier
controls are kept. The later profile `cpu-profile-audio-error-1` passed:
the wait for alGetError no longer appears, but IsPlaying waits 5.17 s in 31.32 s.
The interpreter has 5.33 s self; Game::Update 11.79 s inclusive.

The experiment **audio after submitting the frame** kept
480 verified objects and recompiles main.cpp and Device.cpp in a
private copy; it keeps the AL error cell. It removes the audio execution in
Context::Flush and uses the same main loop call after enqueuing the
Present and the frame's ordered receipt. No additional frames are produced and
the clock, turns, content and quality are not changed. The first attempt failed because of
Boost includes missing in a new container (kept in
`audio-after-present-prepare-failure-1`); reproducing the control's includes it
passed: 483 units, none failed. The diagnostic finished with
32.97 physical FPS / 36.36 engine, physical p95 66.78 ms and engine 53.36 ms,
109 pauses >100 ms, simulation at 99.36 %, zero ETW, audio active and a clean shutdown.
**Removed for not improving**. The patch, sources and reports are archived
in `audio-after-present-build-1`. Back to the shared-AL-error candidate
of 37.20 FPS; its binaries and sources were not changed by the experiment.

**Compiled and verified** `portable-cache-count-o3`: counters of unimplemented
CacheIR. It passes 21 CPU checks, 9,188 incremental GC yields
and the presence of the three counter exports. Archive SHA256
`d3dab64390a994b9fd83b9959bb06fadfc32f24089612393b859d5d16e76840c`.
Its isolated link and package passed: `application-phase4-5-cache-count`.
`cpu-profile-cache-count-1` passed (120 s of warmup and 30 s
instrumented, initial fullscreen/focus verified, 15 profiles and exit code 0).
It recorded 3,885 dispatches of unimplemented opcodes in a 32.78 s external
window: LoadUndefinedResult 839, GuardMultipleShapes 668 and
GuardIndexIsNotDenseElement 340. They are not exclusive costs nor do they include guard
failures. The engine thread had 4.95 s self of PortableBaseline and
5.60 s waiting on IsPlaying in 31.39 s. The counters do not justify applying
a broad backport as is. Isolating the audio checks gets priority.
They are diagnostic only; the physical
runner rejects instrumented libraries. Do not apply D224672 yet nor
assume that a specific opcode is the bottleneck without that data.

1. The following compilation and probe already passed; do not duplicate them without
   new changes or failures. Report: `portable-vm-probe-portable-cache-count-o3/report.json`.

```powershell
# Inside the same test container used by the other probes:
python3 /workspace/wasm/scripts/verify-phase4-5-portable-vm.py --profile portable-cache-count-o3
```

   The probe requires 21 checks, incremental GC and the three counter
   exports. Do not link the game if it fails. Then prepare the native
   closure for that VM and the original audio extension (not after-present),
   link to an isolated package for a CPU profile with `--cacheir-counts`.
   Do not run compilers, profilers or other GPU consumers during
   a physical measurement.
2. Historical commands of the removed variant (do not repeat to continue):

```powershell
.\wasm\scripts\docker-phase4-5.ps1 -Action link-audio-after-present -ScriptingProfile portable-switch-o3
.\wasm\.venv-phase3\Scripts\python.exe wasm/scripts/phase4-5-package.py --linked-directory wasm/build/phase4-5/linked-audio-after-present --target-directory wasm/dist/application-phase4-5-audio-after-present
```

3. Diagnostic already finished of that removed variant:

```powershell
.\wasm\.venv-phase3\Scripts\python.exe wasm/scripts/benchmark-phase4-5-standalone.py --webgpu-directory wasm/dist/application-phase4-5-audio-after-present --backends webgpu --workloads skirmish --repetitions 1 --warmup-seconds 120 --duration-seconds 120 --upload-probe --output docs/wasm/evidence/phase4-5/performance-audio-after-present-diagnostic-1
```

The operator offered to give Chrome focus. The harness checks focus and fullscreen;
do not touch the window during the capture. Do not use Computer Use, screenshots,
overlays nor another GPU consumer during the measurement. If the evidence
directory already exists, keep it and use a new suffix; do not overwrite.

4. Check physical **and** engine FPS, their p95, the simulation over real
   observation intervals, load, errors, ETW and shutdown. A 120 s diagnostic
   does not replace the contractual 900 s repetitions. If it does not reduce the
   pauses, continue with the bottleneck; do not open other phase gates.
5. Only once performance is fixed, complete the contractual measurements
   and the functional, visual and stability items pending in the plan.

There are no commits nor submissions to the project. The changes require the
operator's review before being presented upstream. Do not restore the
pre-existing resource deletions in the working tree.

## Operator question: audio on another thread

The engine already creates `CSoundManagerWorker`, which keeps the sound items.
WebAudio mixing also has a browser audio render thread.
However, `CSoundManager::IdleTask` still runs from the game
thread: it calls `EnsurePlay` for music and ambient sound, checks the playlist and
cleans up items. `EnsurePlay` calls `IsPlaying`, which holds `m_ItemMutex`
while it does `alGetSourcei(AL_SOURCE_STATE)`; in the SDK that query waits
synchronously for the browser's main thread. The current profile attributes
5.17 s of waiting to IsPlaying in 31.32 s; they are not exclusive mixing seconds.

It is viable to isolate the maintenance through orders and results, with clear
ownership of the items and a bounded queue. Simply moving IdleTask to the
existing worker could keep blocking through the shared mutexes, introduce
races in the playlist/pointers or access an item after its destruction.
A state snapshot without a protocol can also go stale. In addition, SoundGroup queries
the simulation's camera and actor when positioning sounds: that data must be
captured on the owning thread before being sent, not read from the worker.
AudioContext and the control of the
graph still have operations on the window thread; AudioWorklet allows
its own processing on the audio thread, but replacing the whole OpenAL backend
would be a bigger modification. Primary reference:
https://www.w3.org/TR/webaudio/#control-thread-and-rendering-thread

The operator asked about that alternative; no measured improvement is attributed
to it and p95 is not considered closed. The research on turns and the VM
continues in logical parallel, without competing with physical measurements.

### Partial experiment: playback checks on the existing worker

A private `audio-worker` variant was implemented. `IdleTask` requests the music and
ambient checks without waiting for OpenAL. The existing worker runs them, grouping
repeated requests per item. The original maintenance period of
streams/fades (500/100/50 ms) is kept; waking up for a check does not bring
that maintenance forward. The tickets use generations: they are cancelled when an
item is removed and a reused address does not validate an earlier ticket. Shutdown
wakes the wait and discards pending ones.

The check and the Play/Pause/Stop orders coordinate their flags through
the item's mutex; the IsPlaying/Play locks are not nested. The path keeps
the SDK's real queries, without an AL_SOURCE_STATE cache. Playlist,
item destruction and explicit orders stay at their original points;
neither the whole audio nor the camera/simulation access has been moved.

Sources of the adaptation: `wasm/scripts/phase45_audio_worker.py` and
`wasm/experiments/audio-worker/application-audio-ensure.h`. The probe
`audio-ensure-probe/report.json` passes 10 checks in Wasm pthreads:
grouping, order, cancellation, reused addresses, a producer that keeps
making progress while the consumer is stopped, deadline and shutdown.
The build passed with 483 units (480 kept by hash, two audio ones
recompiled and the shared AL cell); the isolated link and package passed.

The initial preparation copied the experimental header into the control harness and
invalidated its global fingerprint. That rebuild of our own was stopped,
its report was saved in `audio-worker-prepare-1`, only the identical header created
by the experiment was removed and all objects were audited: 481 identical; Font.cpp
had been left incomplete. That object was rebuilt and the 482
control units were revalidated with the portable-switch-o3 VM. The experimental header
now lives outside the common harness. No operator sources were restored.

Sources, patch and reports archived in `audio-worker-build-1`.
`cpu-profile-audio-worker-1` passed: 15 profiles, initial focus/fullscreen and
exit code 0. Engine `cpu-13.cpuprofile`, 30.80 s: there are no samples waiting on
IsPlaying; total futex 3.71 s (2.08 others, 1.27 FlushCommands, 0.23 Present).
PortableBaseline 4.69 s self; Game::Update 10.55 s and RenderFrame 17.04 s
inclusive. Do not add nested scopes nor turn this capture into FPS.
After stopping the sampling, the original orders to pause/
resume the match and stop/restart music passed: active sources 2→1→2→1→2,
with the pause/stop persisting for 1.5 s. An original asset from the ZIP
is played through PlayMusic; the GUI's directory read restrictions are not
bypassed. They are real SDK states, not subjective listening.

`performance-audio-worker-diagnostic-1` finished: 120 s of warmup and
120 s measured, physical fullscreen 1920×1080, 306 units, PresentMon without
lost events, exact GPU probes and shutdown 0. It measured **34.33 physical FPS /
37.90 engine**, physical p95 **66.85 ms** and engine 59.36 ms, physical p99
150.16 ms and 132 pauses >100 ms. Simulation at 98.95 %, zero backlog and empty
errors. No compilers nor profilers ran at the same time.
**It does not improve on the control**; one sample does not prove causality
nor significance, but it does not allow adopting the variant as a smoothness fix.
Keep the 37.20 FPS shared-AL-error control and the isolated experiment.

The offline analysis keeps 4,548 frames without ID gaps. 599 contain
turns: Game::Update median 31.81 ms, p95 117.11 ms and maximum 598.48 ms;
597 receipts with a turn >33.4 ms, against 68/3,948 between turns. Correlation,
not direct attribution of physical frames. The audio worker does appear in
`cpu-7.cpuprofile`: 12.09 s waiting on EnsurePlay; it is no longer the game thread.
On the engine, 1.98 s of waiting appear directly under main (without a resolvable
intermediate caller) and 1.26 s resolve to Reclaim/FlushCommands, when
the GPU queue fills up. Do not attribute the 1.98 s to an unproven origin.
The browser main thread keeps a cost of bindShader 3.16 s, draw 2.93 s and
setBindGroup 2.23 s in 31.82 s. There is already a bind group state cache; do not
assume it is missing nor duplicate it. The phase stays open. The operator paused
before changing the investigated VM handlers; see the current snapshot.
