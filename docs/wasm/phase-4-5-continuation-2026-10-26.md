# Phase 4.5 — continuation of 26 October

The phase is still open. Yesterday's record:
[25 October](phase-4-5-continuation-2026-10-25.md).

## How to resume (state at the end of 26 October)

- New: the launcher picks a low graphics profile for weak GPUs ("Automatic
  graphics profile" below), verified in Chrome on the integrated AMD GPU.
- **Windows GPU preference.** For that test the operator set the Windows
  per-app GPU preference of `chrome.exe` to power saving (`GpuPreference=1`,
  the AMD Radeon integrated GPU). With it Chrome renders WebGL and WebGPU on the
  integrated GPU even with `--force-high-performance-gpu` (checked with a probe
  page), so performance captures meant for the RTX 3060 are not comparable until
  it is set back. `verify-graphics-profile.py` records the value
  (`chromeGpuPreference`). Later the operator set it back to `GpuPreference=0`
  (Windows decides): the benchmark scripts, which pass
  `--force-high-performance-gpu`, get the RTX 3060 again ("Dedicated GPU guide").
- New: the launcher shows a guide to give the browser the dedicated GPU when it
  runs on an integrated one ("Dedicated GPU guide").
- Old builds and test browser profiles were deleted ("Disk cleanup"); the
  latest candidate and its whole build chain remain.
- The next steps of 25 October are unchanged: the long acceptance battery with
  `cushion-1`, the intermittent `tryAttachStub` crash, the remaining slow turns.

## Automatic graphics profile

Operator request: when the GPU is not powerful, start with textures, shadows
and every graphics option at low. Testing was in Chrome only (operator
decision).

### Detection

`wasm/browser/application-graphics.mjs` classifies the GPU from the unmasked
WebGL renderer string (`WEBGL_debug_renderer_info`), for example
`ANGLE (AMD, AMD Radeon(TM) Graphics (0x00001638) Direct3D11 vs_5_0 ps_5_0, D3D11)`:

| Category | Examples | Profile |
|---|---|---|
| `software` | SwiftShader, Microsoft Basic Render Driver, llvmpipe; WebGPU fallback adapter | low |
| `integrated` | Intel HD/UHD/Iris/Arc iGPUs, AMD APUs (`Radeon(TM) Graphics`, Vega N, 610M–890M), Adreno, Mali, Apple M1–M4 base | low |
| `entry` | GeForce MX/GT, GTX 400–960 and 1050 (Ti), RTX 2050/A500, T400–T550, small Quadros, Radeon 520–630, RX 540–560/640/6300, Arc A3xx | low |
| `capable` | every other recognized GPU (RTX 3060, GTX 1060+, RX 470+, Arc A5xx+, Apple Pro/Max, Radeon 8060S) | original |
| `unknown` | no renderer string | original |

WebGPU reports only vendor and architecture (`amd gcn-5`, `nvidia ampere`),
which integrated and dedicated GPUs share. On the WebGPU path the launcher
reads the name from a short-lived WebGL 2 context and uses it only if it names
the adapter's vendor; Chrome runs both APIs on the same adapter (the probe gave
the AMD GPU for WebGL and WebGPU under every `powerPreference`). Otherwise only
a fallback adapter or an Intel `gen-*` architecture is classified.

The lists are judgement calls (the line sits around a GTX 1050 Ti / RX 560), not
measurements; an unrecognized GPU keeps the original settings. A GPU benchmark
at startup would cover unknown names but needs calibration on both GPUs of the
test machine; not done.

### The low profile

| Setting | `default.cfg` | Low |
|---|---|---|
| `textures.quality` | 2 (high) | 0 (low) |
| `textures.maxanisotropy` | 2 | 1 |
| `shadowquality` | 0 (medium, 1024²) | -1 (low, 512²) |
| `shadowpcf` | true | false |
| `waterrealdepth`, `waterrefraction`, `waterreflection` | true | false |
| `waterfancyeffects` | false | false |
| `postproc` | true | false |
| `antialiasing`, `sharpening` | disabled | disabled |
| `smoothlos` | true | false |
| `max_actor_quality` | 200 (high) | 100 (low) |
| `materialmgr.quality` | 10 | 0 |

Shadows stay on at low quality. Unchanged: silhouettes, particles and fog (they
show game information) and `watereffects` (off is the fixed-pipeline water).
On WebGL 2, PCF is the software filter of phase 4 (16 shadow-map reads per
pixel), so `shadowpcf=false` matters there. The WebGPU shader catalog already
contains the variants without PCF and with every water combination.

### How it is applied

The launcher writes the profile to `/data/config/local.cfg`, which the engine
loads as `CFG_SYSTEM`: above `default.cfg` and mods, below `CFG_HWDETECT` and
`user.cfg`. Settings the player saves in the in-game options therefore win.
`hwdetect.js` changes nothing on the web (WebGL reports `OpenGL ES 3.0`; WebGPU
returns early). The file is written on every start, so a GPU change is picked
up; the original profile writes no `local.cfg`.

The page has a "Calidad gráfica" selector (Automática / Baja / Original del
juego, stored like the other selectors), `?graphics=auto|low|original`
overrides it, `#gpu-info` shows the GPU and the decision, and
`window.graphicsProfile` holds `{mode, profile, gpu, settings}`. The benchmark
harness applies its own profile in the `user` namespace, so captures are not
affected.

### Tests

- `node --test wasm/scripts/test-application-graphics.mjs`: 7 pass (categories
  of 46 renderer strings including both GPUs of the test laptop, the WebGPU
  vendor check, display names, mode selection, `local.cfg` syntax, the WebGL
  probe). `test_phase45_benchmark_contract`: 14 pass.
- Chrome verification `evidence/phase4-5/graphics-profile-1` (Chrome 156,
  `GpuPreference=1`, integrated AMD GPU, 2560×1080 display at 60 Hz). Package
  `application-phase4-5-cushion-1-graphics-1`: the `.wasm`, data and shaders of
  `cushion-1-web` (hard links) plus the current `wasm/browser` launcher.

```text
wasm/.venv-phase3/Scripts/python.exe wasm/scripts/verify-graphics-profile.py \
    --package wasm/dist/application-phase4-5-cushion-1-graphics-1 \
    --runs webgpu:auto gl:auto webgpu:original:measure webgpu:auto:measure \
    --expect-profile low --check-user-override --warmup-seconds 30 --measure-seconds 60 \
    --workload skirmish --output docs/wasm/evidence/phase4-5/graphics-profile-1
```

| Run | Detected | Profile | Settings in the engine | Notes |
|---|---|---|---|---|
| WebGPU, auto | AMD Radeon(TM) Graphics, integrated (WebGL name, vendor `amd` matches) | low | all as `local.cfg` | `textures.quality=2` saved to `user.cfg`, restart: 2 wins, `shadowquality` stays -1 |
| WebGL 2, auto | same | low | all as `local.cfg` | |
| WebGPU, original | same | original | all as `default.cfg`, no `local.cfg` | measured |
| WebGPU, auto | same | low | all as `local.cfg` | measured |

No renderer error (`missing-shader-variant`, uncaptured or validation errors),
no engine `ERROR:` line, exit code 0 and no live workers after every run.

Measured runs: skirmish, 153 units per side, fullscreen 1920×1080 internal,
30 s warmup + 60 s. Engine frames (`applicationFrames`), not PresentMon; 3D
engine use of Chrome's GPU process from the Windows GPU counters. One capture
each:

| WebGPU, integrated AMD GPU | original | low |
|---|---:|---:|
| Engine FPS | 29.97 | 30.00 |
| Frame interval p50 / p95 / p99, ms | 33.34 / 33.62 / 34.91 | 33.34 / 33.60 / 34.30 |
| Longest interval, ms | 110.4 | 43.9 |
| Intervals over 50 ms | 1 | 0 |
| GPU 3D engine use, mean (p95) | 43.7 % (45.7 %) | 25.9 % (26.7 %) |
| `CGame::Update` median, ms | 1.03 | 0.96 |

In this scene the integrated GPU holds the 30 FPS cap with the original
settings too; the low profile cuts its 3D load by ~40 %, headroom for bigger
battles, water maps or weaker GPUs. Not measured: combat, WebGL frame rates,
displayed frames. The single 110 ms interval of the original run is one event
in one capture. The screenshots (`3-webgpu-original.png`,
`4-webgpu-auto.png`) show the low profile renders without missing textures:
softer shadows, flatter lighting, no normal or specular maps on buildings.

The RTX 3060 was not run live (Chrome is bound to the integrated GPU by the
Windows preference); its renderer string from earlier evidence classifies as
`capable` in the unit tests.

### Files

- `wasm/browser/application-graphics.mjs` (new), `application.mjs`,
  `application.html`.
- `wasm/scripts/phase4-5-package.py` copies the new module;
  `phase45_benchmark_contract.py` fingerprints it.
- `wasm/scripts/test-application-graphics.mjs` (new, 7 tests, 46 renderer
  strings), `wasm/scripts/verify-graphics-profile.py` (new).
- `wasm/deploy/README.md`: one paragraph.

## Dedicated GPU guide

Operator request: test whether the Windows GPU preference makes Chrome use the
dedicated GPU; if the dedicated GPU is not used by default, show the player a
guide for the main operating systems (Windows, macOS, Linux).

### What decides the GPU (Windows, tested)

A probe page in the installed Chrome 156 (a fresh profile per run, no other
Chrome running) read the WebGL 2 renderer string and the WebGPU adapter, each
with `powerPreference` default, `high-performance` and `low-power`:

| `chrome.exe` in `UserGpuPreferences` | Chrome flag | WebGL 2 and WebGPU, every `powerPreference` |
|---|---|---|
| `GpuPreference=0` (Windows decides) | none | AMD Radeon integrated |
| `GpuPreference=0` | `--force-high-performance-gpu` | RTX 3060 |
| `GpuPreference=2` (high performance), set for the test | none | RTX 3060 |
| `GpuPreference=1` (power saving), earlier today | `--force-high-performance-gpu` | AMD Radeon integrated |

The page cannot choose the GPU: Chrome runs every page on the adapter its GPU
process started on and ignores `powerPreference` on Windows (Chrome's own
console warning, crbug.com/369219127). With the default preference a player of
a laptop with two GPUs gets the integrated one. The preference was restored to
`GpuPreference=0;SwapEffectUpgradeEnable=1;` after the test.

macOS and Linux, from documentation only: Chrome on macOS honours
`high-performance` for WebGL on Intel Macs with two GPUs (the default has been
the integrated GPU since Chrome 80); Apple silicon has a single GPU. Chrome on
Linux uses the GPU it was started on (PRIME offload variables, `DRI_PRIME`,
the desktop's "dedicated GPU" launcher).

### The guide

`application-graphics.mjs`:

- `detectOS()` reads `navigator.userAgentData.platform`, `navigator.platform`
  and the user agent: `windows`, `macos`, `linux`, or `other` (Android,
  ChromeOS, iOS, unknown).
- `gpuGuide(gpu, os)`: `dedicated` for an integrated GPU on Windows, macOS or
  Linux, except GPUs that are the only one of their device (Apple silicon,
  Adreno, Mali, PowerVR, VideoCore); `acceleration` for software rendering on
  any system; otherwise none (dedicated GPUs, entry-level ones included, and
  unknown GPUs).

`application.mjs` checks on page load (a short-lived WebGL 2 context with the
"Gráfica" preference), again when that selector changes, and with the GPU of
the started game. `#gpu-guide` in `application.html` is a collapsed
`<details>` under the selectors; the steps of the detected system open first:

- Windows: Settings › System › Display › Graphics › the browser › High
  performance; or `chrome://flags/#force-high-performance-gpu` (Edge:
  `edge://flags/...`) when Windows has no preference for the browser; vendor
  MUX / dedicated-only modes.
- macOS: Apple silicon has one GPU; on Intel Macs with two, the "Alto
  rendimiento" preference of the page, or turning off automatic graphics
  switching.
- Linux: the desktop's "launch with the dedicated GPU" entry; `prime-run` or the
  NVIDIA PRIME offload variables; `DRI_PRIME=1` for Mesa.
- Software rendering: Chrome's hardware acceleration setting, then
  `chrome://gpu` and the GPU driver.

Each path ends with: close the browser completely, reopen it, reload the page.
`chrome://` addresses are shown as text to copy, since a page cannot open them.

Not covered: when no WebGL 2 context can be created at all (acceleration off
and no software fallback), the GPU is `unknown` and no guide appears; the start
fails with the existing error. The macOS and Linux steps were not tested on
those systems, and the Windows/macOS menu names are written from documentation.

### Tests

- `node --test wasm/scripts/test-application-graphics.mjs`: 9 pass (new: OS
  detection, guide choice). `test_phase45_benchmark_contract`: 14 pass.
- `verify-graphics-profile.py` has two new options: `--expect-guide
  dedicated|acceleration|none` (checked on load and after the start; recorded
  as `gpuGuideAtLoad` and `gpuGuide`) and `--force-high-performance-gpu`.
- Package `application-phase4-5-cushion-1-graphics-2`: hard links to
  `cushion-1-graphics-1` plus the current `wasm/browser` launcher. Chrome 156,
  `GpuPreference=0`:

| Evidence | Chrome flag | GPU | Runs | Auto profile | Guide on load / after start |
|---|---|---|---|---|---|
| `evidence/phase4-5/gpu-guide-integrated-1` | none | AMD Radeon(TM) Graphics, integrated | `gl:auto`, `webgpu:auto` | low | `dedicated`, Windows steps open / same |
| `evidence/phase4-5/gpu-guide-dedicated-1` | `--force-high-performance-gpu` | RTX 3060 Laptop GPU, capable | `gl:auto`, `webgpu:auto` | original | none / none |

No page error, no renderer or engine error, exit code 0 in every run. The
second row is also the first live run of the automatic profile on the RTX 3060
(it chooses the original settings, as the unit tests expected).
`gpu-guide-integrated-1/guide-collapsed.png` and `guide-expanded.png` show the
guide on the page.

```text
wasm/.venv-phase3/Scripts/python.exe wasm/scripts/verify-graphics-profile.py \
    --package wasm/dist/application-phase4-5-cushion-1-graphics-2 \
    --runs gl:auto webgpu:auto --expect-profile low --expect-guide dedicated \
    --output docs/wasm/evidence/phase4-5/gpu-guide-integrated-1
wasm/.venv-phase3/Scripts/python.exe wasm/scripts/verify-graphics-profile.py \
    --package wasm/dist/application-phase4-5-cushion-1-graphics-2 \
    --runs gl:auto webgpu:auto --expect-profile original --expect-guide none \
    --force-high-performance-gpu --output docs/wasm/evidence/phase4-5/gpu-guide-dedicated-1
```

### Files

- `wasm/browser/application-graphics.mjs` (`detectOS`, `gpuGuide`),
  `application.mjs`, `application.html`.
- `wasm/scripts/test-application-graphics.mjs` (2 new tests),
  `wasm/scripts/verify-graphics-profile.py` (guide checks, flag option).
- `wasm/deploy/README.md`: two sentences.

## Disk cleanup

Operator request: delete old builds and keep only the latest. C: had 71 GiB
free and has 203 GiB free after the cleanup.

- 286 test browser profiles left by benchmark and verification runs
  (`wasm/build/phase4-5/standalone-profile-*`, `profile-*`, `chrome-*`,
  `focus-probe-*`, `wasm/build/phase4-visible-profile`,
  `wasm/build/raw-browser-*`), each with a ~0.5 GiB copy of the archive cache:
  110.0 GiB. The runners create a new profile per run.
- 200 old builds, 21.3 GiB: every `wasm/dist/application-phase4-5*` package
  except `cushion-1`, `cushion-1-web` and the test package `cushion-1-graphics-1`;
  `application-diagnostic`; the scene builds except `scene-release-resize`;
  `wasm/build/phase4-assets` (intermediate archives; the packaged ZIPs are the
  ones in `webgl-baseline-phase4-5`); the phase 3 native build
  (`wasm/build/native-windows`, `native-windows-run`, its source tar); and in
  `wasm/build/phase4-5` the `application-*`, `linked-*` and `spidermonkey-*`
  directories outside the build chain of `cushion-1`.
- Kept: the chain of `cushion-1`, computed as the closure of the
  `/phase45-build/<dir>` references in its `compile-report.json` and
  `link-report.json` (16 `application-*`/`native-deps` directories,
  `linked-cushion-1`, four SpiderMonkey builds), `shaders`, the packaging
  baseline `webgl-baseline-phase4-5`, `application-phase4`, the phase 1–2 builds,
  `native-phase4` and `native-windows-libs`, `playwright`, `tools`,
  `deploy-context`.
- Not touched: Docker's `docker_data.vhdx` (112 GiB; Docker Desktop was not
  running). Evidence under `docs/wasm/evidence` names deleted packages; their
  reports and hashes remain.

Packages share `mod.zip` and `public.zip` as hard links, so one package costs
~50 MB; the profiles were the bulk.
