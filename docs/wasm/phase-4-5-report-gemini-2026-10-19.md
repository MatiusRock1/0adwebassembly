# Report for Gemini: phase 4.5 of 0 A.D. WebAssembly

> Later update: the rAF patch has since been implemented, tested and measured in
> a new package. It recorded 39.83 physical FPS and a physical p95 of 50.12 ms; the phase
> stays open. See [implementation and evidence](phase-4-5-worker-raf-2026-10-19.md).
> The rest of this report keeps the historical cut of candidate `-2`.

Cut-off date: **19 October 2026, America/Bogota**. This document
describes the last finished run and distinguishes its package from the later changes
still unverified. It can be shared in full as context.

## Main result

**Phase 4.5 stays open. The combined improvements compiled and ran the
game, but did not fix performance.** The candidate recorded **24.54 physical
FPS**, a physical p95 of **100.14 ms** and **175 pauses longer than 100 ms**. The engine
recorded **45.86 FPS**; that figure does not equal distinct images shown
on the monitor. It must not be presented as meeting the 30 FPS goal.

The resource improvement was verified: keeping whole ZIPs in JavaScript was replaced
by selective reads, persisted in IndexedDB, with
a **block cache limited to 64 MiB**. That limit belongs to the ZIP
cache; **it is not the total RAM consumption of the game, the browser nor the GPU**.

## Operator's goal and constraints

- First fix the stutter and reach at least 30 physical and engine FPS,
  with the p95 of both frame intervals ≤33.4 ms.
- Keep the original simulation at real speed, within ±2 %; at least
  200 live units; internal resolution 1920×1080; the 24 original graphics
  settings; a turn backlog without sustained growth.
- Measure in real fullscreen, with verified physical focus, without ETW
  losses and with a shutdown without orphaned workers.
- **No more reviews nor tests of the native executable.** The operator
  says the native build runs without stutter. This run did not test it.
- Add the browser improvements to one combined candidate, without running
  independent physical campaigns per optimization.
- Do not reduce AI, units, quality or simulation speed to artificially
  improve the results. Do not advance tests unrelated to performance
  while this problem stays open.

The diagnostic was 120 s of warmup +120 s of measurement,
one skirmish repetition. **It does not replace the full acceptance**, which requires
three 900 s repetitions per load, plus the remaining requirements.

## Identity and environment of the run

| Item | Value |
|---|---|
| Game's original pin | `40b8794eecb9618da69e10bacffa8814c561aa51` |
| Measured package, kept separately | `wasm/dist/application-phase4-5-browser-perf-2` |
| Diagnostic evidence | `docs/wasm/evidence/phase4-5/performance-browser-perf-combined-2/` |
| Compiler | Emscripten 4.0.10 |
| Measured backend | WebGPU, owner `render-worker` |
| Browser | Chrome **155.0.8059.85** |
| WebGPU adapter | NVIDIA / Ampere, `high-performance` |
| NVIDIA GPU inventoried by Chrome | GeForce RTX 3060 Laptop GPU |
| Fullscreen window | 2560×1080, DPR 1, visible and focused |
| Internal colour/depth/canvas surfaces | 1920×1080 |
| Load | Mainland, Athenian human and Macedonian Petra; 306 units recorded |

CLI/CDP automation and PresentMon were used. There were no
screenshots, Computer Use, overlays, compilers nor simultaneous profilers
during the measurement. The GPU byte checks were done before the
warmup, on private resources.

The preparation uses the original `createunits` command to create/replenish the
load and original patrol orders. CGame, GUI, components and Petra are
the original ones. The functional tests with cheats disabled belong to
another scope and are not declared passed by this diagnostic.

## What was applied from Gemini's proposals

| Proposal | Implementation and real scope |
|---|---|
| SIMD `-msimd128` | The **483 engine objects** compiled with SIMD and O2, without fast-math. The external libraries keep their builds. The flag does not guarantee vectorization of each loop. |
| ASYNCIFY | **Classic ASYNCIFY was not applied**: the SDK warned about an incompatibility with `-fwasm-exceptions`. It was linked with **`-sJSPI=1`** keeping the Wasm exceptions. The SDK marks it experimental; Chrome ran the package. No artificial yields per frame were added. |
| OffscreenCanvas | WebGPU, its objects and the command encoding were moved to a dedicated worker with OffscreenCanvas. SDL keeps an input canvas and the worker presents through another canvas with the same geometry. |
| Asynchronous shader/pipeline compilation | WebGPU uses `createRenderPipelineAsync` / `createComputePipelineAsync`; while pending, it resumes the same command, without repeating uploads nor skipping draws. |
| `KHR_parallel_shader_compile` | Implemented and compiled for the **WebGL** path. It was not exercised at runtime in this **WebGPU** measurement; they are different mechanisms. |
| WebGL 2 / instancing | WebGL 2 and the instancing capabilities already existed. They were kept; the current diagnostic uses WebGPU. |
| Pthreads / SharedArrayBuffer | `-pthread`, `PROXY_TO_PTHREAD=1` and a pool of eight workers already existed. The engine was already on a pthread; now the GPU has its own worker. |
| COOP / COEP | They already existed and were kept. If isolation is missing, startup fails explicitly; there is no silent degradation to a single thread. |
| IndexedDB / IDBFS | **IndexedDB for compressed ZIP blocks**; **IDBFS for settings**. Persistence and the equality of the configuration bytes were checked after restarting the menu. |
| Selective preloading | Only the required blocks of the ZIP are read through HTTP Range. The original ZIPs and all their civilizations/resources are kept; no reduced `.data` packages were created. |

The disk/network file operations happen in a worker. The engine's
pthread waits for the answer when it needs an original synchronous read;
the window does not run `Atomics.wait`. The engine keeps the original analysis and
decompression of the ZIP. JSPI does not by itself turn the simulation cost
into parallel work nor guarantee more FPS.

The best control's `portable-switch-o3` VM was kept explicitly:
SHA-256 `dd057a4ea34a1a5028660d9992bef5b749c9116a3502828611a240c2df07b642`.
This port's SpiderMonkey 128.13.0 is compiled **without JIT**. SIMD on the
C++ engine does not add a JIT to the guest JavaScript. It is a relevant limit for
interpreting the proposals, not a demonstrated attribution of all the stutter.

The whole audio was **not** moved to a new dedicated thread in this candidate.
The control's audio solution is kept. An earlier audio
worker experiment had not fixed the smoothness and was not adopted as a fix.

## Physical and engine results

| Metric | Best earlier control | Combined candidate |
|---|---:|---:|
| Package | `application-phase4-5-audio-error` | `application-phase4-5-browser-perf-2` |
| Physical FPS, PresentMon | **37.20** | **24.54** |
| Engine FPS | 43.63 | 45.86 |
| Physical interval median | 16.70 ms | 33.34 ms |
| Physical interval p95 | 66.74 ms | **100.14 ms** |
| Engine interval p95 | 51.86 ms | 49.41 ms |
| Physical interval p99 | 133.48 ms | 166.86 ms |
| Physical pauses >100 ms | 116 | **175** |
| Simulation rate | 0.99145× | 0.99146× |
| Units | 306 | 306 |
| Maximum observed backlog | 0 | 0 |
| Lost ETW events | 0 | 0 |
| Clean shutdown | Yes | Yes |

**Physical presentation got worse in this diagnostic**, although the engine
counter rose slightly. They are single runs, without a paired
statistical test. In addition, the control used Chrome **155.0.8059.80** and the
candidate **155.0.8059.85**. Several improvements changed at once: these figures
do not allow attributing the regression to a single one of them.

PresentMon recorded 2,950 presents, 2,945 displayed and 5 not displayed. Those
five do not explain the whole difference between the engine and physical FPS.
The engine's observer confirms ordered processing after Present;
it does not confirm that each frame produces a distinct image on the monitor. There is
no exact correspondence between its IDs and PresentMon's physical frames.

The game ended without engine nor harness errors, exit code 0 and
without remaining pthreads nor workers. `passed: true` in the individual JSON
expresses a successful run, **not a performance nor phase approval**.
The summary records `gate30: false` and `phase45Accepted: false`. Exit code 1
of the diagnostic launcher does not mean that the game crashed either.

## ZIP and IndexedDB: checks and limits

The original ZIPs weigh 62,959,007 bytes (`mod`) and 1,914,886,590 bytes
(`public`): about **1.98 decimal GB** in total. The SHA-256 of `public.zip` is
`b8729bbc2f66cd66c5779ed1fcce78e60dad753e74134da6be700f2419558515`.

The new path uses 1 MiB blocks, verified by SHA-256, a 64 MiB LRU RAM cache
and content-addressed persistent storage. It deduplicates pending
requests, uses HTTP 206 responses and rejects a 200 that would download the whole
ZIP. If IndexedDB fails it can continue over the network with a bounded cache, but that
is not declared approved persistence.

| Real check | Result |
|---|---|
| First menu startup | 24,348,509 network bytes; 25 blocks; 0 persistent hits |
| Second startup, same profile | 2,097,152 network bytes; 2 new blocks; **24 persistent hits** |
| IDBFS configuration after restart | Identical bytes; check passed |
| Cache at the end of the match | Residency and peak **67,108,864 bytes =64 MiB** |
| Accumulated counters of the second run | 334,495,744 network bytes (319 MiB); 319 blocks; 139 persistent hits; 19,952 RAM hits |

The final counters include loading, preparation, warmup and measurement;
**they do not represent only the 120 s measured**. The second menu still requested
two new blocks; full operation without the network has not been demonstrated.
The reduction of the total process consumption has not been measured here either.

## Evidence about the stutter

The later analysis of the original logs grouped the frames with
a turn update and those between turns:

| `CGame::Update` | With a turn | Between turns |
|---|---:|---:|
| Samples | 599 | 4,903 |
| Median | 25.92 ms | 0.87 ms |
| p95 | **108.32 ms** | 1.45 ms |
| Maximum | **585.04 ms** | 2.80 ms |
| Updates >33.4 ms | 116 | 0 |
| Updates >100 ms | 52 | 0 |

There is a strong correlation between original turns and pauses. They are wall-clock
durations of `CGame::Update`, not exclusive CPU times nor an
exact attribution to AI, pathfinding, GC or rendering. The historical profiles pointed at
the cost of the AI and of SpiderMonkey interpretation; no other profiler was run
during this physical diagnostic.

The pipeline counter went from **78 to 78** between the snapshots before
the warmup and at the end. This run does not support continuous pipeline
compilation as the explanation of the recurring stutter in that interval.

Besides the cost of turns, the divergence between the engine and physical
presentation remains to be explained. A possible accumulation/coalescing of presentations
before the swapchain is **a hypothesis**, still without a demonstrated mechanism.

## Verification completed and failures kept

- The 483 SIMD objects, the three candidate-specific objects
  and the combined link with JSPI/IDBFS compiled. The dependency and
  Wasm exceptions audit passed.
- 36 existing CPU cases of the backend and eight of `renderer-session` passed;
  the new blocks/continuations suite passed ten cases after fixing
  `fetch`; 12 cases of the contract and four of HTTP Range also passed.
  They are suites run at their respective moments, not a new joint run
  of all of them after the last pending adjustment.
- GPU probes before the warmup: 1,536 exact bytes of buffers,
  76 of textures and 64 of a private destination of asynchronous pipelines. They verify
  those integrity cases, not the full visual parity of the game.
- First GL compilation attempt: a JavaScript comma inside `EM_ASM`
  was interpreted as a macro argument; it was fixed and recompiled. The
  evidence is kept, including the associated compiler failure.
- Attempt with classic ASYNCIFY: stopped on purpose after the
  incompatibility warning. Its exit code 137 does not prove a lack of memory.
- First combined package: failed before measuring FPS with
  `TypeError: Illegal invocation`, because `fetch` was invoked with the wrong receiver.
  It was fixed by using `globalThis.fetch`, a regression case was added and
  package `-2` was generated. The first package provides no performance figures.

## Later change prepared, still unverified

After finishing run `-2`, `wasm/browser/webgpu-worker-present.mjs`
and its integration in the worker, packager and harness fingerprints were added
to the working tree. It tries to run Present exactly
once inside the worker's `requestAnimationFrame`.

It includes a 250 ms timer to allow progress/shutdown when a
hidden window stops receiving rAF. That path is counted separately and **cannot
vouch for foreground FPS**. The validation that invalidates
a measurement if it appears in its interval still has to be added.

**This adjustment was not in the measured package, has not been tested, packaged nor
measured and it cannot be claimed that it improves anything.** Do not overwrite package
`-2`. The next technical step would be to check single execution, cancellation,
late callbacks and error propagation, complete the harness
check and then generate a new package/evidence of the set. Even if
it improves presentation, the long turn updates still need a solution.

## Files and reproduction

The figures come from these local artifacts:

- [Full individual result](evidence/phase4-5/performance-browser-perf-combined-2/webgpu-skirmish-1.json).
- [Approval summary](evidence/phase4-5/performance-browser-perf-combined-2/summary.json).
- [Physical PresentMon CSV](evidence/phase4-5/performance-browser-perf-combined-2/webgpu-skirmish-1.presentmon.csv).
- [Later turn analysis](evidence/phase4-5/performance-browser-perf-combined-2/stutter-analysis.json).
- [Builds and hashes of the diagnostic](evidence/phase4-5/performance-browser-perf-combined-2/builds.json).
- [Compilation, patches, sources and hashes](evidence/phase4-5/browser-performance-build-1/).
- [Log of the combined candidate](phase-4-5-browser-performance-2026-10-19.md).

Main files modified/added: `wasm/browser/archive-blocks.mjs`,
`archive-worker.mjs`, `application-archives.mjs`, `webgpu-worker-bridge.mjs`,
`webgpu-render-worker.mjs`, `shared-request.mjs`, `webgpu-pipeline-pending.mjs`,
`webgpu-engine.mjs`; C++ integration in `source/lib/file/io/io.cpp`,
`browser_archives.h`, `source/renderer/backend/webgpu/Device.cpp` and the GL
path of `ShaderProgram.cpp`/`BrowserShaderCompile.h`; scripts for the SIMD build,
combined build, link, packaging, Range server and diagnostic.

Commands run to generate and measure the candidate; **the current tree
contains the later adjustment and does not by itself reproduce the exact JS of
package `-2`**. For a new run use new package and evidence
destinations, keeping the earlier ones:

```powershell
.\wasm\scripts\docker-phase4-5.ps1 -Action engine-simd -ScriptingProfile portable-switch-o3
.\wasm\scripts\docker-phase4-5.ps1 -Action engine-browser-perf -ScriptingProfile portable-switch-o3
.\wasm\scripts\docker-phase4-5.ps1 -Action link-browser-perf -ScriptingProfile portable-switch-o3
.\wasm\.venv-phase3\Scripts\python.exe wasm/scripts/phase4-5-package.py --linked-directory wasm/build/phase4-5/linked-browser-perf --target-directory wasm/dist/application-phase4-5-browser-perf-2
.\wasm\.venv-phase3\Scripts\python.exe wasm/scripts/benchmark-phase4-5-standalone.py --webgpu-directory wasm/dist/application-phase4-5-browser-perf-2 --backends webgpu --workloads skirmish --repetitions 1 --warmup-seconds 120 --duration-seconds 120 --upload-probe --verify-persistent-reload --output docs/wasm/evidence/phase4-5/performance-browser-perf-combined-2
```

For Gemini's next review it would help to explain, separately,
the long turn updates and the loss of physical presentations relative to
the engine, without assuming that enabling flags equals a measured improvement.
Block persistence already works; the smoothness is not fixed yet.

No commits, commit messages, issues nor PRs were created. The changes require
human review before being submitted to the project.
