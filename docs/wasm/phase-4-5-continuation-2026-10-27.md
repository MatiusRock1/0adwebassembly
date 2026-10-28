# Phase 4.5 — continuation of 27 October

The phase is still open. Yesterday's record:
[26 October](phase-4-5-continuation-2026-10-26.md). This page covers only the
GPU work of the evening; the archive URL changes of earlier today are in
[the deploy README](../../wasm/deploy/README.md) and
[ARCHIVE-HOSTS.md](../../wasm/deploy/ARCHIVE-HOSTS.md).

## GPU techniques from the NFSU2 web port

Operator request: study how the browser port of Need for Speed: Underground 2
(nfsu2.xyz, a static x86 → C → WebAssembly recompilation with a Direct3D 9 →
WebGPU translator) uses the GPU, and apply the techniques that fit 0 A.D. Only
its published page and minified `main.js` were read; no code was copied.

### What our WebGPU backend already did

| NFSU2 technique | Our backend before today |
|---|---|
| Game in a worker, GPU calls elsewhere | Already further: the engine runs on a pthread and every GPU object lives in a dedicated render worker with an OffscreenCanvas. |
| Native BC (DXT) textures | `texture-compression-bc` is a required device feature; DDS data is uploaded compressed. Only textures whose size is not a multiple of 4 (1×1 defaults) are decoded, because WebGPU requires block-aligned sizes. |
| `alphaMode: 'opaque'` | Already set in `renderer-session.mjs`. |
| One large buffer, few uploads | A 16 MiB uniform arena with dynamic offsets, transient vertex/index arenas and a mapped upload belt (one staging copy per frame). |
| `createRenderPipelineAsync` | Already used by the render worker, with a suspended command resumed at the same draw. |

Missing were the persistent pipeline warm-up and a command path that does not
go through the window thread. Both are now implemented, plus measurements to
judge them.

### Persistent pipeline cache and warm-up

`webgpu-engine.mjs`:

- A render pipeline is now identified by a **content recipe**: catalog program
  and variant, vertex layout after the original stream filter, targets, sample
  count, fixed-function state and the border-sampling constants (plain JSON).
  The previous identity key (engine object ids) stays as the first-level cache.
  Engine objects with equal state share one GPU pipeline; recreated objects (a
  new match, reloaded materials) no longer recompile.
- Shader modules, bind group layouts and pipeline layouts are created once per
  catalog variant (`shaderResources`) and shared by every engine shader object
  of that variant and by the recipes.
- Compute (GPU skinning) and blit pipelines use the same mechanism.

`webgpu-pipeline-cache.mjs` and the render worker:

- Every recipe the engine compiles is stored in IndexedDB (`0ad-webgpu-pipelines`,
  in the worker), under a key made of the shader catalog's build fingerprint,
  the adapter and the canvas format; a new build, GPU or format starts a new
  list. At most 2,048 recipes; IndexedDB failures only lose the warm list.
- At the next start, right after the device is created, the worker compiles the
  stored recipes in their original use order, four at a time, with
  `createRenderPipelineAsync`, while the engine is still loading. A draw that
  needs a recipe still queued compiles it at once; a recipe that no longer
  compiles (stale catalog) is dropped from the list.
- `?pipelineCache=0` disables the list and the warm-up.

### Engine → render worker command ring (`WASM_WEBGPU_SHARED_RING`)

Before, every engine call went engine pthread → window (Emscripten
`MAIN_THREAD_ASYNC_EM_ASM`, which parsed the JSON arguments) → `postMessage` →
render worker. The window thread also serves Emscripten's file system calls,
input, audio and the page, so any busy moment there delayed GPU commands.

`Device.cpp` (only with `WASM_WEBGPU_RENDER_WORKER` and `WASM_WEBGPU_SHARED_RING`):

- A ring of 64 records in WASM memory. The engine thread is the only producer:
  it writes a record (method, JSON arguments, payload range, sequence, ready and
  result addresses, publication time) and wakes the head with
  `emscripten_futex_wake`. Payload ownership is unchanged: the queued call owns
  its strings and bytes until the worker writes its ready flag.
- The ring is attached once, after the device's first synchronous calls, through
  the bridge's `attachRing` (which receives the `WebAssembly.Memory`, so the
  worker follows memory growth). A page without `attachRing` (an older launcher,
  or `?commandRing=0`) keeps the relay; the same build serves both paths.
- Frame samples: `main.cpp` queues each frame's diagnostic sample through the
  window right after Present, and the sample must not be published before the
  worker has executed that present (the engine frame times of the benchmark
  depend on it). After each present the engine now tells the window how many
  records it had published (`ringPublished`, in the same order as the sample);
  the sample's barrier asks the worker to answer only after executing that many
  records. This keeps the previous semantics exactly.
- `webgpu-command-ring.mjs` reads the ring in the render worker with
  `Atomics.waitAsync`; records and window messages enter one ordered queue, and
  the existing sequence check still verifies the order.

Built as `ring-1` = `cushion-1` + `Device.cpp` with `WASM_WEBGPU_SHARED_RING=1`
(all other objects reused):

```text
wasm/scripts/phase4-5-turn-gate-build.py --base cushion-1 --variant ring-1 \
    --unit renderer/backend/webgpu/Device.cpp --define WASM_WEBGPU_SHARED_RING=1
wasm/scripts/phase4-link.py --build /phase45-build/application-ring-1 \
    --output /phase45-build/linked-ring-1 --release --exception-mode wasm --jspi \
    --spidermonkey-library /phase45-build/spidermonkey-portable-switch-o3-runscript-timer/libjs_static.a
wasm/scripts/phase4-5-package.py --linked-directory wasm/build/phase4-5/linked-ring-1 \
    --target-directory wasm/dist/application-phase4-5-ring-1
```

### New measurements in the render worker snapshot

`snapshot()` (and therefore every benchmark report's `initialRendererWork` /
`finalRendererWork`) now also contains:

- `work`: the worker's busy time (encoding and submitting, without the waits for
  display signals and pipelines), per frame, with a histogram of frames under 2,
  4, 8, 16, 33 ms and above.
- `delivery`: time from the engine thread publishing a call to the worker
  receiving it, by path (`ring`, `relay`), with a histogram under 0.25, 0.5, 1,
  2, 4, 8 ms and above. The engine thread's clock is `timeOrigin + now()`; the
  minimum stayed positive in every run, so the clocks agree.
- `stats`: `pipelineWaits` and `pipelineWaitMilliseconds` (command batches
  suspended for a pipeline), compile times, warm compiles and hits, content
  hits, and `stageMilliseconds` (copying the arenas into the upload belt at
  submit).
- `commandRing` and `pipelineCache` state.

`wasm/scripts/verify-render-transport.py` runs a sequence of transports and cache
modes in one Chrome profile (so a run's stored pipelines are the next run's warm
list), opens the benchmark match in fullscreen and reports these counters for
the menu, the match setup and a measured window.

### Freeze at match start (found and fixed)

The first verification (`evidence/phase4-5/render-transport-1`, run
`relay:nocache`) froze right after "GAME STARTED": the loading screen stayed on
screen and the original GUI stopped answering. The operator saw it too. Two
diagnostics (`peek`, below) with a fresh profile and the benchmark match:

- `cushion-1-archive-urls-2` (the previous renderer with today's archive code):
  the frames stop ~14 s after `launchGame`, then the match starts at 26.0 s and
  runs at 30 FPS. Today's archive changes are not the cause.
- `ring-1` before the fix: 38 pipelines compile, then the render worker stays on
  one `createShader` for 212 s and more, with no pipeline pending; the engine
  waits for it. Cause: shader modules are now shared by every engine shader object
  of a variant, and each `createShader` asked its modules for
  `getCompilationInfo()` again. Chrome 156 never answered that second query for
  a module that pipelines already used. The menu did not show it because each of
  its variants is created once.
- Fix: the compilation of a variant's modules is queried once, when they are
  created (`shaderResources`); every `createShader` of the variant waits for that
  result, and a compilation error still fails it. Two regression tests
  (`test-webgpu-pipeline-cache.mjs`). After the fix the same run starts the
  match at 26.1 s and runs at 30 FPS; it compiled 63 content pipelines (the
  previous renderer compiles 78 for the same match), 2.6 s of compile time in
  total, while the frames stop for ~10 s at match start (the rest is the
  engine's map load).

`peek` (bridge `peek()`, worker) answers immediately, outside the worker's
ordered queue, with the snapshot plus the pending pipelines, the suspended time
and the message in progress (`current`); `snapshot` keeps its place in the queue.

### Verification after the fix (`render-transport-2`)

```text
wasm/scripts/verify-render-transport.py --package wasm/dist/application-phase4-5-ring-1 \
    --runs relay:nocache ring:cache ring:cache relay:cache --workload skirmish \
    --warmup-seconds 30 --measure-seconds 60 --output docs/wasm/evidence/phase4-5/render-transport-2
```

Chrome 156.0.8078.48, RTX 3060 (`GpuPreference=0` plus `--force-high-performance-gpu`),
skirmish, fullscreen 1920×1080 internal, one Chrome profile for the four runs;
single runs, engine frames (not PresentMon):

| | relay, no list | ring, cold list | ring, warm list |
|---|---:|---:|---:|
| Pipelines compiled during the match setup | 71 | 72 | **0** (70 warm hits) |
| Time command batches waited for pipelines | 2.67 s | 0.23 s | **0** |
| Engine FPS / p95 / p99, ms | 29.97 / 33.50 / 34.7 | 29.99 / 33.53 / 36.0 | 29.99 / 33.52 / 34.6 |
| Intervals over 100 ms | 1 | 0 | 0 |
| Delivery latency, mean | 1.69 ms | 1.42 ms | 0.71 ms |
| Calls delivered under 0.25 ms | 2.6 % | 67.5 % | 74.7 % |
| Calls delivered in 2 ms or more | 28.5 % | 24.1 % | 13.7 % |
| Worker busy time per frame | 9.94 ms | 10.99 ms | 9.71 ms |
| Draws per frame | 7,522 | 8,540 | 7,518 |

- The warm list works: in the third run the worker compiled the 77 stored
  recipes (menu, match, compute skinning, blit) in 99 ms while the menu started,
  and the match setup waited for no pipeline. The fourth run (relay with the
  warm list) also set up its match without a pipeline wait, then stopped in the
  fullscreen step because the browser closed (no engine or renderer error).
- The second run waited only 0.23 s with an empty list because Chrome's own
  shader cache in that profile was already filled by the first run. So the warm
  list saves the cold compile time once per Chrome profile, and afterwards moves
  the remaining compile work from the first match frames to the menu start.
- With the ring, two thirds to three quarters of the calls reach the worker in
  under 0.25 ms; through the window most took 0.25–1 ms. Calls of 2 ms and more
  are calls published while the worker was busy encoding (both paths). The
  engine frames are the same at the 30 FPS cap; any effect on pauses needs more
  than single runs.
- The clocks agree: the smallest measured latency is −0.005 ms (within the 5 µs
  timer resolution of an isolated page).

### Combat captures with PresentMon (single runs, operator request)

The operator asked to watch one combat run of `ring-1` on each GPU. Standard
harness, fresh Chrome profile (cold pipeline list), 2560×1080 display at 60 Hz,
fullscreen 1920×1080 internal, original quality, 153 units per side:

```text
wasm/scripts/benchmark-phase4-5-standalone.py --backends webgpu --workloads combat \
    --repetitions 1 --warmup-seconds 60 --duration-seconds 60 \
    --webgpu-directory wasm/dist/application-phase4-5-ring-1 --output OUT
```

For the integrated AMD GPU, `chrome.exe` was set to `GpuPreference=1` for the
run and restored to `GpuPreference=0;SwapEffectUpgradeEnable=1;` afterwards (the
report records adapter `amd gcn-5`).

| Combat 60 s + 60 s | AMD Radeon (integrated) | RTX 3060 |
|---|---:|---:|
| Displayed FPS | 29.99 | 29.84 |
| Physical p95 / p99, ms | 33.43 / 50.03 | **35.95** / 50.04 |
| 1 % low, FPS | 16.36 | 14.01 |
| Pauses over 100 ms | 2 | 2 |
| Engine FPS / engine p95, ms | 29.94 / 33.73 | 29.78 / 34.97 |
| Simulation rate / backlog | 1.0008 / 0 | 0.9998 / 0 |
| Worker presents two refreshes apart | 99.7 % (3,640 of 3,650) | 99.7 % (3,612 of 3,624) |
| Worker busy time per frame / draws per frame | 10.50 ms / 8,398 | 11.13 ms / 8,895 |
| Ring deliveries under 0.25 ms (mean) | 58 % (1.79 ms) | 58 % (1.92 ms) |

Evidence `evidence/phase4-5/performance-ring-1-amd-combat-60s-1` and
`performance-ring-1-combat-60s-1` (each with `presentation-two-refresh.json`). The
operator's gate (displayed mean ≥ 29.5 FPS and physical p95 ≤ two refreshes,
33.51 ms) holds on the integrated GPU and **fails on the RTX 3060 in its p95**;
`presentationGateTwoRefresh` is false in both also because of its mean ≥ 30
condition. There is no earlier combat capture on the integrated GPU; the worker
counters cover warmup and measurement.

Physical display intervals (last 1,800 of each capture):

| Combat capture | ≤ 20 ms (early) | 20–34 ms | ≥ 40 ms (a refresh late) | p95 |
|---|---:|---:|---:|---:|
| `ring-1`, RTX 3060 | 91 | 1,617 | 90 (5.0 %) | 35.95 ms |
| `ring-1`, AMD integrated | 72 | 1,656 | 67 (3.7 %) | 33.43 ms |
| `cushion-1`, RTX 3060, 25 October (3 captures) | 38–52 | 1,689–1,699 | 52–58 (2.9–3.2 %) | 33.40–33.42 ms |

The worker presented on its two-refresh cadence (its own rAF timestamps), so the
extra late frames on the RTX appeared after that, when the frame reached the
display. One capture cannot separate a regression from noise. Hypothesis, not
tested: work of the next frame already queued in the worker runs as microtasks
right after the presenting rAF callback and delays the commit of the canvas
frame; with the ring that work arrives earlier, so more of it can be queued at
that moment. An ABBA (`cushion-1-archive-urls-2` against `ring-1`, RTX, combat)
would decide; if confirmed, the fix to try is to return to the event loop after
the present before continuing with queued work.

### Deployment (`arm64-v14`)

Operator decision: publish `ring-1` as tested, with the ring on. The previous
image `arm64-v13` was the package `cushion-1-archive-urls-2` (files compared
after `docker cp`). The archives are unchanged: `archive-blocks.json` and
`application-data.json` are byte-identical (`mod.zip` SHA-256 `10eb081f…`,
`public.zip` `b8729bbc…`), so the per-archive hosts (`PUBLIC_ARCHIVE_URL`,
`MOD_ARCHIVE_URL`) need no new upload and players' IndexedDB block caches stay
valid.

```text
python wasm/deploy/prepare-context.py --package wasm/dist/application-phase4-5-ring-1 \
    --output wasm/build/deploy-context-v14
docker build -t 0ad-wasm-web:v14 wasm/build/deploy-context-v14
docker build --platform linux/arm64 -t matiusrock1/0ad-wasm-web:arm64-v14 wasm/build/deploy-context-v14
docker push matiusrock1/0ad-wasm-web:arm64-v14
```

Pushed digest `sha256:2f71bc4bea4c9bfca6c6c3d83af88cb00664ed2e1fe9d0962ab0b2cf129e6c1a`
(`linux/arm64`). Checked on a local amd64 container with both archive variables:
COOP/COEP on every response, `text/javascript` for the modules (including the two
new ones), `application/wasm`, the archive meta tags rewritten at start, no ZIP in
the image (404), and the served `.wasm` and modules equal to the package.
`wasm/deploy/smoke-test.py` was not run: it still expects `public.zip` on the
same origin.

### Upload path: measured, not changed

NFSU2 writes its geometry straight from WASM memory with `queue.writeBuffer`.
Our worker copies transient vertex/index data and uniforms into JavaScript arenas
during the frame and into a mapped upload belt at submit. The second copy
(`stageMilliseconds`) costs 0.72–0.75 ms per frame, about 7 % of the worker's
~10 ms per frame, on a thread that has 33 ms per frame at the cap. Removing it
needs one belt lane per arena and contiguous chunk allocation; not worth the risk
for at most ~0.7 ms on a thread that is not the bottleneck. Buffer uploads inside
a framebuffer pass are not expected (the engine's Vulkan backend forbids them with
`ENSURE(!m_InsideFramebufferPass)`), so the pass split in `uploadBufferRange`
should be a fallback; this was not counted.

### Not adopted

- **Rendering straight into the canvas texture** (NFSU2 does when the canvas
  format is `bgra8unorm`). Our engine records a frame over several worker tasks,
  and the canvas texture of an OffscreenCanvas expires at the end of a
  rendering opportunity, so the worker renders into its own image and copies it
  at present. Rendering directly would mean holding every backbuffer command
  until the present, which with present pacing moves that GPU work from before
  the display signal to after it (and, with the low graphics profile, that is
  the whole scene). The cost avoided would be one full-screen copy per frame.
