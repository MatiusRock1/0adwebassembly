# Phase 4.5: continuation of 19 October 2026

**Historical: the operator paused again on 20 October.** See
[the new resume point](phase-4-5-pause-2026-10-20.md). Do not start
tests because of the historical instructions of this document.

The operator resumed the work with "continúa" after the pause of the
19th at **16:15 America/Bogota**. **Work active; phase open; performance
unresolved.** The [pause snapshot](phase-4-5-pause-2026-10-19.md) keeps
the historical state. The smoothness priority is kept: at least 30 physical FPS,
physical and engine p95 ≤33.4 ms, original graphics/load and a real-time
simulation. Do not advance gates unrelated to performance while it keeps failing.

The [snapshot of the 18th](phase-4-5-pause-2026-10-18.md) keeps the earlier packages and
results. The 15 hashes of its manifest matched when resuming.
The best package is still `wasm/dist/application-phase4-5-audio-error`:
37.20 physical FPS and p95 66.74 ms. Do not overwrite it with experiments.
The audio worker was tested, but its measurement of 34.33 FPS /66.85 ms did not
justify adopting it as a smoothness fix.

**Later instruction of the operator:** no more reviews nor tests
of the native build. Implement the browser improvements in **a single combined
candidate** and measure the set, without FPS campaigns per individual improvement.
The operator's observation is that the native game runs without stutter.
The current work and its limits are in
[combined performance candidate](phase-4-5-browser-performance-2026-10-19.md).
The earlier control stays intact and the phase stays open.

**Last run finished:** `application-phase4-5-browser-perf-2`,
24.54 physical FPS /p95 100.14 ms, 45.86 engine FPS. IndexedDB/IDBFS
persistence checked and ZIP cache bounded at 64 MiB; performance
unresolved. The [report for Gemini](phase-4-5-report-gemini-2026-10-19.md)
contains the full state, including a Present/rAF change of the
worker prepared after that measurement, still unverified. Do not overwrite
the measured package nor confuse the current tree with its snapshot.

## Current work: three pure CacheIR operations

A private copy of the VM was prepared with LoadUndefinedResult,
GuardMultipleShapes and GuardIndexIsNotDenseElement. The counters of the
earlier session observed them 839, 668 and 340 times respectively in the
32.78 s external window; those counts are not exclusive times nor do they
prove by themselves that the adaptation will improve FPS.

The semantics were checked against the original sources of SpiderMonkey 128.13.0
of the pinned SDK. **Correction with respect to the preliminary research of the 18th:**
ShapeListObject stores `PrivateValue(shape)` and traces those references weakly
through its own hook. It does not contain PrivateGCThingValue in this version.
`traceWeak` compacts the live shapes and updates the initialized length;
the list may end up empty. The new handler only compares the private
pointers, without dereferencing weak shapes, allocating memory nor introducing GC.
It changes neither the tracing hook nor the later guards.

`wasm/scripts/phase45_portable_guards.py` records the hashes of seven original
sources used as a reference. The build checks those hashes before
adapting the source. The file downloaded from master is not used as an input.
The full D224672 patch was not applied.

## Validation and build status

Three new semantic/GC cases are added to the probe only with
`PHASE45_PORTABLE_GUARDS_PROBE`:

- Missing properties that change through prototypes, accessors and proxies.
- Objects with eight shapes, changes of slots/prototypes, accessors and GC.
- Arrays with holes, negative/large indices, inherited properties and GC.

The reference VM `portable-switch-o3` passed **30 checks and 9,953
incremental GC yields**, in three independent contexts. Report:
`wasm/build/phase4-5/portable-vm-probe-portable-switch-o3-guards/report.json`.
This validates the cases against the original fallback; it does not directly prove the
coverage of each handler.

The initial compilation of `portable-guards-o3` was stopped by the operator's
pause. When resuming it was rebuilt with:

```powershell
.\wasm\scripts\docker-phase4-5.ps1 -Action scripting -ScriptingProfile portable-guards-o3
```

It only recompiles PortableBaselineInterpret.o at O3 and replaces that member in
a private archive. It keeps the earlier fixed/switch patches, the rest
of the handlers, stacks, interrupts, fallbacks and headers. It contains no diagnostic
atomic counters. Output: `wasm/build/phase4-5/spidermonkey-portable-guards-o3`.
The container of our own was stopped at the pause. When resuming the
24 hashes of the two manifests were checked. The first resumed attempt lost the
connection with Docker at 17:11:52 (exit 125, `unexpected EOF`), without producing
a correct report nor a VM archive; there is no record of a compiler error.
The incident and the log were archived in
`evidence/phase4-5/vm-guards-build-1/`. Docker answered again and the
same compilation was restarted, with two CPUs and an 8 GiB limit, without restarting WSL nor deleting
data. The second attempt **compiled correctly in 315.81 s**. The VM has
SHA-256 `56b404574f6c70e9af84eed834ca2e30e449a06da99d32ed6c882bd75a8b077f`.

The CPU probe with `--profile portable-guards-o3` **passed the 30 cases and 9,945
incremental GC yields**, with exit code 0. The verifier enabled the cases
automatically because of the archive's provenance. The report and the adapted patch
are archived in `evidence/phase4-5/vm-guards-build-1/`. These cases exercise
semantics, invalidation and GC; they are neither an individual coverage probe of the
three handlers nor a performance acceptance.

The native closure verified and reused the 482 objects. Shared-AL-error and the
link passed with that same profile. It was packaged separately in
`wasm/dist/application-phase4-5-guards`; twelve static files of the renderer,
shaders, launcher and input matched the best control exactly.
Neither audio-worker nor after-present was mixed in.

## Physical diagnostic of the VM: completed, smoothness unresolved

`evidence/phase4-5/performance-guards-diagnostic-1/` keeps the
120+120 s diagnostic, real 2560×1080 fullscreen with the original 1920×1080 canvas,
306 units and Chrome 155.0.8059.80 (same version and surface as the control).
No screenshots, overlays, compilation nor simultaneous profiler were used.

| Measure | New VM | Best control kept |
| --- | ---: | ---: |
| Physical FPS | 35.01975 | 37.20328 |
| Engine FPS | 38.15808 | 43.62535 |
| Physical p95, ms | 66.7757 | 66.7388 |
| Engine p95, ms | 55.8800 | 51.8650 |
| Physical p99, ms | 150.1092 | 133.4801 |
| Pauses >100 ms | 128 | 116 |
| Simulation rate | 0.99106034 | 0.99144528 |

The run was valid: backlog 0, lost ETW events 0, exact GPU probes
of 1,536 bytes of buffers and 76 bytes of textures, empty errors and exit code 0
without workers. `passed:true` vouches for that run; `gate30:false` and
`eligibleForAcceptance:false` keep the acceptance open. The runner's exit code 1
belongs to its performance gate, not to a game failure.
The single sample does not establish statistical causality nor justify adopting
this VM as a fix. The control package stays intact.

The offline analysis found 600 frames with a turn advance: median
update 29.13 ms, p95 114.85 ms and 58 updates >100 ms. Between turns,
the median update was 1.19 ms and none exceeded 33.4 ms. They are durations
and correlations; they do not by themselves identify the exclusive cost of functions.

## Next hypothesis: monotonic maximum without a mutex

`lib/timer.cpp` uses a global mutex on every read to keep the maximum
observed time. An atomic maximum with the same clock source
and clamp semantics will be investigated, through a private copy and a concurrent test
before measuring. The waits without a resolved caller in the earlier profile have not been
attributed to this mutex. Do not change the simulation speed, tick, quality nor
clock to pass the gate. Use the best control's VM in this experiment,
without combining it with the guards VM nor the audio worker.

`wasm/experiments/timer-monotonic/application-timer-monotonic.h` was added,
outside `wasm/harness` to keep the base headers' fingerprint. It uses
a lock-free `atomic<double>` and a relaxed compare/exchange only on the
maximum; it publishes no data unrelated to the clock. It keeps `max(previous, observed)`,
including NaN and signed zero. `verify-phase4-5-timer-monotonic.py` passed
10 cases: seven exact sequences against the original algorithm and races
with 2, 4 and 8 threads, 5.6 million combined calls. The CPU times
of that probe are not FPS nor do they prove a smoothness improvement.

`phase4-5-timer-build.py` keeps 482 objects and recompiles only timer.cpp at
O2, with the original time source intact. The probe's header and source
are checked against its approved report before compiling. The wrapper accepts
`engine-timer-monotonic` and `link-timer-monotonic`. The base closure was
prepared again with `portable-switch-o3`, without the experimental guards VM.
The first link failed because runtime-browser had not been copied to the variant's
folder; the report/log were archived and the copy from the
frozen control was fixed. The fixed link passed. Evidence:
`evidence/phase4-5/timer-monotonic-build-1/`. It was checked that only the
timer.cpp object changed, that the time source stayed byte for byte intact and that
the VM, the AL-error library and twelve static files match the best control.
Isolated package: `wasm/dist/application-phase4-5-timer-monotonic`.

The diagnostic `performance-timer-monotonic-diagnostic-1` completed 120+120 s
in fullscreen with 306 units: **34.39343 physical FPS, 37.66391 engine FPS,
physical p95 66.8031 ms, engine p95 57.7450 ms, physical p99 150.2006 ms and
117 pauses >100 ms**. Rate 0.98955965, backlog 0, lost ETW 0, exact GPU
probes, empty errors and exit code 0 without workers. The run was valid;
it did not fix the smoothness nor justify adopting the change as a fix. The
37.20 FPS /66.74 ms control is kept. Do not confuse the synthetic probe's speedup
with an improvement of the game. It was not combined with the guards nor with audio-worker.

## Next research: reuse of WebGPU commands

The profiles already show the cost of bindShader/draw/setBindGroup in Window.
A bounded cache of render bundles will be evaluated in a private JS package,
with the best control's binary and VM. The backend already has pipeline,
bind group and state caches; do not duplicate those optimizations. The additional goal
is to reuse identical command sequences, keeping the current data
of uniforms and buffers. State equivalence and a
GPU probe must be checked before measuring.
Primary reference: [WebGPU API: executeBundles](https://gpuweb.github.io/types/interfaces/GPURenderPassEncoder.html#executebundles),
which requires restoring the bindings explicitly after running a bundle.

The first variant uses `wasm/experiments/render-bundles/webgpu-bundles.mjs`
and `phase4-5-bundles-package.py`; the base browser code stays intact. The
package `wasm/dist/application-phase4-5-bundles` keeps exactly the
best control's binary and changes only JS/probes in its private folder.
The cache compares all the words of the signature after the hash, keeps the current
buffer data, restores all bindings per segment, respects barriers
of viewport/scissor/blend/stencil and labels, and limits signatures to 16 MiB /24
entries and segments of 131,072 numbers. The bundles are created at the second
exact appearance; the first is replayed directly. It only accepts the default
dynamic state; the rest is replayed directly. No draws are removed.

14 CPU cases of state/draw equivalence, 12 tests of the measurement contract
and 9 GPU cases with 576 exact bytes passed. The GPU probe checked updated
uniform data, dynamic offsets, a negative baseVertex and a mix
of draws with scissor and bundles. The fingerprint includes both new modules.
Sources, patch and hashes: `evidence/phase4-5/render-bundles-build-1/`.

The diagnostic `performance-bundles-diagnostic-1` was valid but worse:
**29.96929 physical FPS /32.30960 engine; physical p95 67.8113 ms,
engine p95 57.9050 ms, physical p99 150.1317 ms, 120 pauses >100 ms**.
Simulation 0.99409530, backlog 0, lost ETW 0, empty errors, correct
probes and exit code 0 without workers. Not adopted as a fix nor is the phase accepted.

Between the initial/final snapshots (warmup and capture) 57,456,182
draws were submitted: 17,202,122 reused (29.94 %), 3,714,458 encoded when creating
bundles and 36,539,602 direct. The cache ended with 24 entries and 794,984 bytes
of signatures, well below the byte limit. The equality of the sum of the
draws supports that no work was skipped; it does not replace the visual review.
`cpu-profile-bundles-1` passed with 15 profiles, initial focus and a clean shutdown,
without a simultaneous physical capture. In Window: replay self 2.7355 s,
aggregate setBindGroup self 5.0708 s and GC 1.7600 s. The cache's `submit`
only added 0.3937 s self; it did not justify optimizing the hash first. The
replay re-sent all bindings when starting direct segments,
even if they were still active, and passed temporary Float64 views
to the iterable overload of setBindGroup. This added work compared with the
original state cache. The instrumented times are not acceptance FPS.

### Second bundles variant: diagnostic completed

A cache of the state actually sent to the pass was added for the direct
replay. It is cleared explicitly after executeBundles and keeps the
mandatory restores; it only removes redundant native setters.
The offsets use the Uint32Array overload with a reused scratch and are
validated before copying, to prevent wrapping of values outside uint32.
The logical offsets also reuse storage, keeping their
ownership against mutations by the caller. 16 CPU cases passed.

The maximum was raised to 512 entries keeping 16 MiB of signatures and
eviction and direct-replay-cause counters were added. The scope of the
dynamic state was not widened yet. The hash was not changed.
`phase4-5-bundles-package.py --iteration 2` keeps the earlier
package/evidence and prepares `wasm/dist/application-phase4-5-bundles-2`, with the
same binary as the best control. Build evidence:
`evidence/phase4-5/render-bundles-build-2/`. The 120+120 s fullscreen measurement
of `performance-bundles-diagnostic-2` completed with **35.09961 physical FPS,
38.56304 engine, physical p95 66.7863 ms, engine p95 58.8250 ms,
physical p99 150.0701 ms and 119 pauses >100 ms**. Simulation 0.99053622,
backlog 0, lost ETW 0, empty errors, exit code 0 without workers and the
9 GPU cases /576 bytes correct. The smoothness is still unresolved.

Between the initial/final snapshots there were 68,493,435 draws: 31,283,738 reused,
98,024 encoded in bundles and 37,111,673 direct. Of the latter,
36,710,797 were excluded because of dynamic state (53.60 % of the total),
238,660 because of short segments and 162,216 because of first appearance. It ended at
512 entries /4,623,840 bytes, with 2,952 evictions in that window. Most
of the allowed work is already reused; widening the scope requires
checking the inherited state, not removing draws nor lowering quality.

### Third variant: inherited viewport/scissor, performance unresolved

The viewport/scissor barriers are kept and bundles are allowed to be reused
under those states of the parent pass. Non-default blend constants and stencil references
still go to direct replay. The native replay state,
the Uint32Array overload and the limits of the second variant are kept.
The GPU probe was widened to 15 cases /960 expected bytes: reuse under
partial viewport, partial scissor and a direct/bundle mix. The
16 CPU cases and the 15 GPU cases passed with **960 exact bytes**.

Package: `wasm/dist/application-phase4-5-bundles-3`. Build evidence:
`evidence/phase4-5/render-bundles-build-3/`. The 120+120 s fullscreen diagnostic
`performance-bundles-diagnostic-3` was valid: **34.06849 physical
FPS /38.05997 engine, physical p95 66.8414 ms, engine p95 60.0500 ms,
physical p99 150.1964 ms and 130 pauses >100 ms**. Simulation 0.98944083,
backlog 0, lost ETW 0, empty errors and exit code 0 without workers. The probes
ran before the warmup, without a simultaneous profiler nor compiler.
Between the snapshots there were 68,024,361 draws: 48,969,023 reused (71.99 %),
140,089 encoded when creating bundles and 18,915,249 direct. 18,367,504
were excluded because of blend/stencil, 354,848 short and 192,897 at first
appearance. It ended with 512 entries /7,463,040 bytes. The sum keeps the
original draws, but this larger coverage did not fix p95 either.
The best control package stays intact; no bundles variant
is adopted as a fix nor is the phase accepted. They are kept separate and
this cache is not widened further as a supposed fix without another
demonstrated bottleneck. The base backend of `wasm/browser` was not modified.

## Current work: the same switch interpreter compiled at O2

The profiles still show an important cost of the portable interpreter in
the frames with simulation. A comparison of the optimization of the
PortableBaselineInterpret object at **O2** was started, with exactly the fixed/switch source
of the O3 control, without the guards, underflow, counters, timer nor bundles.
The SHA-256 of both sources matches:
`209d3290877f0ebef415a4b349547b74ea32020f1072de8ede499a25aa792885`.
The JS logic, the clock, scripts, quality and simulation are not changed.
This fixed/switch-O2 combination had not been measured; the earlier hot-O2
profiles did not include the same dispatch adaptation.

The wrapper accepts `portable-switch-o2` and so does the verifier. The compilation
ran through:

```powershell
.\wasm\scripts\docker-phase4-5.ps1 -Action scripting -ScriptingProfile portable-switch-o2
```

Output: `wasm/build/phase4-5/spidermonkey-portable-switch-o2`. It compiled in
295.4 s and passed the probe with `--profile portable-switch-o2 --guard-checks`:
**30 cases, 9,933 incremental GC yields, exit code 0**. No handlers are added.
VM SHA-256: `609d1d7829dcad020b29a94a4182e0efb24d42fd9d95a9db2b7fc063c1a9100d`.
The O2 object takes 767,964 bytes against 766,676 for the O3; no
reduction of that size was observed nor is an FPS improvement deduced from compiling.
The source and the base input archive match the control. Evidence:
`evidence/phase4-5/vm-switch-o2-build-1/`.

engine-wasm-eh verified/reused 482 objects and engine-audio-error approved
483 objects. The link passed and it was packaged separately in
`wasm/dist/application-phase4-5-switch-o2`. It was checked that the 483 hashes
of the engine objects and the twelve static files match the control;
only the VM object changes. No bundles nor other experiments were combined.

`performance-switch-o2-diagnostic-1` completed 120+120 s with **34.30655 physical
FPS /37.53100 engine, physical p95 66.8263 ms, engine p95 59.0450 ms,
physical p99 150.1294 ms and 121 pauses >100 ms**. Rate 0.98972432, backlog 0,
lost ETW 0, correct GPU probes, empty errors and exit code 0 without workers.
The run was valid, but O2 did not fix the smoothness either. Not adopted.

The possibility that the harness enabled Wasm debugging was also reviewed:
the [V8 documentation](https://v8.dev/docs/wasm-compilation-pipeline) distinguishes
the tier-down for debugging from the tier-up when profiling. The measurement path does not
call Debugger.enable; the installed driver only uses it in crCoverage and the
separate inspector inspect-phase4-worker.py disables it when finishing.
This does not prove the effective tier of each function, but it does not demonstrate a debugging
bug in the measurements. Neither the Chrome flags nor the harness were changed
based on that hypothesis.

## Diagnostic WebGL comparison with the same binary: completed

Before changing more VM dispatch the references were reviewed. No
physical WebGL measurement with the current best package was found in the phase 4.5
summaries. `performance-gl-paired-diagnostic-1` was started with 120+120 s,
fullscreen and the same `wasm/dist/application-phase4-5-audio-error`, O3 VM,
load and quality. Only the real backend selection changes to GL. No screenshots,
overlays nor simultaneous compilation/profiling. It is a performance diagnostic
to isolate the renderer, not a parity test nor a phase acceptance.

The run ended valid: **29.57347 physical FPS /32.88529 engine,
physical p95 83.3784 ms, engine p95 62.6550 ms, physical p99 150.1329 ms
and 126 pauses >100 ms**. Simulation rate 0.99341841, 306 units,
backlog 0, lost ETW 0, empty errors, exit code 0 and no workers.
The real renderer was WebGL 2, ANGLE/D3D11 on the NVIDIA RTX 3060 Laptop GPU.
The offline analysis of 599 turns records a median update of 24.65485 ms,
p95 102.89485 ms and 35 updates >100 ms. The frames between turns have a
median update of 0.86502 ms. The simulation stutter also appears
with GL; this isolated run does not prove an exclusive cause nor replace
the acceptance repetitions. The best WebGPU control stays intact.

## Current work: diagnostic native reference

The normalized identity of six main simulation,
AI and ScriptInterface sources was checked against the existing native tree. The first report looked for
loose scripts that do not exist: the native build uses public.zip. The second report
checked the 43 AI scripts and the whole archive, identical byte for byte
to the browser's: SHA-256
`b8729bbc2f66cd66c5779ed1fcce78e60dad753e74134da6be700f2419558515`.
Evidence: `evidence/phase4-5/native-performance-preparation-1/identity-review.json`
and `resource-review.json`. This enables a diagnostic comparison; it does not
vouch by itself for the full reproducibility of the native build.

The native executable has SHA-256
`21dce2c8f275ec5975cb403a67083494a1ee4b538d2570bce1d9b106df87d330`.
`performance-native-diagnostic-1` was discarded before capturing for lack of
real Windows focus; it closed with exit code 0 and provides no performance figures.
The native harness now reuses the existing activation by PID, only
once during preparation, and includes the hash of that helper. It does not recover
focus during warmup nor measurement: any loss still invalidates
the run. `performance-native-diagnostic-2` was also left incomplete:
the process ended with exit code 0 before getting the first sample; there
are no valid performance figures nor an attributed cause for that shutdown.
On the operator's later instruction this line of review is abandoned.

It was also checked in public.zip that the original AI contains real
references to Sim/SimEngine: requirements, QueryInterface, orders, resources and
modifiers. Do not assume it can be sent entirely to another thread by
just cloning gameState; the current shared context is part of its API.
No AI thread was implemented nor were those accesses replaced by mocks.

Docker was closed or not available at the first attempt. Its
processes/logs were reviewed and Docker Desktop was started hidden; the daemon answered again.
WSL was not restarted, no data was deleted nor were unrelated containers restarted.

There are no commits, issues nor PRs. The changes require the operator's review
before submitting to the project. Keep the pre-existing asset deletions.
