# Phase 4.5: combined browser performance candidate

**Run finished:** the package `application-phase4-5-browser-perf-2`
recorded **24.54 physical FPS / p95 100.14 ms**, against the control's
37.20 FPS /66.74 ms. The phase stays open. The ZIP cache stayed at 64 MiB
and real persistence through IndexedDB/IDBFS passed. The
[report for Gemini](phase-4-5-report-gemini-2026-10-19.md) gathers results,
evidence, limits and the later presentation adjustment still unverified.

Active work, requested by the operator on 2026-10-19. **No more
reviews nor tests of the native build.** The operator sees it as smooth. Add
the improvements together and measure a single candidate; no physical campaigns
separated per optimization. The integrity/semantic checks of the
code are still needed before running the set.

Immutable control: `wasm/dist/application-phase4-5-audio-error`, 37.20 physical
FPS and p95 66.74 ms. Phase open: the mean exceeds 30, but p95
stays outside the 33.4 ms limit. Keep the simulation within ±2 %, at least 200
units, 1920×1080 internal, original quality, non-growing backlog, real
focus, ETW without losses and shutdown without workers. That contract is not changed.

## Changes of the candidate

- SIMD128 in the engine's 483 objects, with the original O2 optimization and without
  fast-math. The fixed/switch-O3 VM of the best control is used explicitly,
  SHA-256 `dd057a4ea34a1a5028660d9992bef5b749c9116a3502828611a240c2df07b642`.
  The external libraries keep their builds; the flag does not imply that
  every loop is vectorized nor does it guarantee an FPS improvement.
- WebGPU and OffscreenCanvas in a dedicated worker. SDL keeps its input
  canvas; the presentation canvas is overlaid visually and belongs
  only to the worker. The shared buffers stay lent until the
  consumer's ACK. Synchronous queries wait only on the engine
  pthread. The window thread does not use Atomics.wait nor actively polls.
- createRenderPipelineAsync/createComputePipelineAsync in the worker. An
  internal marker suspends the package at the pending draw and resumes that
  same command when the compilation completes, without repeating uploads, skipping
  draws nor using substitute pipelines. The frame samples go through
  a barrier of the worker after Present, keeping the scope of the
  earlier observer.
- KHR_parallel_shader_compile for the WebGL selection: compile stages,
  link, poll COMPLETION_STATUS_KHR without blocking the window and then
  check the original link status. Without the extension, it keeps the
  synchronous check path. This extension does not belong to WebGPU.
- Original ZIPs read in 1 MiB blocks, with a SHA-256 per block generated
  at packaging time. File worker and IndexedDB with content keys,
  a 64 MiB LRU cache in RAM and one block being read at a time. HTTP Range
  fetches only the bytes requested by the original VFS. The full ZIP is neither
  loaded nor decompressed in JavaScript/Wasm. The implementation rejects
  a server that answers 200 to the range to avoid an accidental full
  download. IndexedDB errors allow the network with bounded memory and are
  reported; they are not presented as approved persistence.
- IDBFS for settings, keeping compatibility with the earlier settings
  in localStorage. Serialized write synchronization and flush on shutdown.
- Suspension through **JSPI**, replacing classic ASYNCIFY: Emscripten
  4.0.10 warned that ASYNCIFY=1 is not compatible with -fwasm-exceptions. Only
  that link container was stopped and its log is kept in
  `evidence/phase4-5/browser-performance-build-1/asyncify-incompatible/`.
  Its exit code 137 was caused by that stop; it does not prove an OOM.
  The combined link uses -sJSPI=1, keeping the Wasm exceptions, and
  records asyncSuspension=jspi and asyncify=false. The SDK marks it experimental;
  its execution passed in Chrome 155.0.8059.85. Do not introduce flags to hide
  a lack of support. No artificial yield per frame is added. The new
  reads already free the window through pthread/RPC; the suspension alone
  does not speed up the simulation computations.
- WebGL 2, pthreads, PROXY_TO_PTHREAD, a pool of eight workers and COOP/COEP already
  existed. They are kept, together with the explicit GPU selection.

The block cache serves selectively the resources used by the
match without removing civilizations nor changing the ZIPs. No assets are generated.
The disk cache and the RAM cache are different: IndexedDB alone
would not reduce RAM if the whole archive were read again.

## Build and validation done

```powershell
.\wasm\scripts\docker-phase4-5.ps1 -Action engine-simd -ScriptingProfile portable-switch-o3
.\wasm\scripts\docker-phase4-5.ps1 -Action engine-browser-perf -ScriptingProfile portable-switch-o3
.\wasm\scripts\docker-phase4-5.ps1 -Action link-browser-perf -ScriptingProfile portable-switch-o3
.\wasm\.venv-phase3\Scripts\python.exe wasm/scripts/phase4-5-package.py --linked-directory wasm/build/phase4-5/linked-browser-perf --target-directory wasm/dist/application-phase4-5-browser-perf
```

The first command finished: **483 SIMD objects compiled**, in about 1,070 s.
The second correctly compiled Device.cpp, io.cpp and ShaderProgram.cpp,
reusing the other 480 objects, in a private copy. The first attempt
failed because of a JavaScript comma inside Emscripten's C++ macro; the
declarations were separated and it compiled. Initial evidence kept in
`evidence/phase4-5/browser-performance-build-1/initial-compile-failure/`.
The third command finished correctly with JSPI and IDBFS. The first package
`wasm/dist/application-phase4-5-browser-perf` is kept with its startup
failure: fetch was stored as a method of an instance and Chrome required
the global receiver. `performance-browser-perf-combined-1` did not get to measure
FPS and provides no performance figures. The receiver was fixed through a
function that calls globalThis.fetch, a regression check was added
and `wasm/dist/application-phase4-5-browser-perf-2` was packaged separately.
The binary is the same; only the JS loader changes.

`performance-browser-perf-combined-2` finished in Chrome 155.0.8059.85:
24.536999 physical FPS and 45.864702 engine; physical p95 100.1405 ms and engine
49.405 ms; 175 physical pauses >100 ms. The menu restart reused
24 persistent blocks; the IDBFS settings kept their bytes. The block cache
had a residency/peak of 64 MiB, which does not equal the total RAM.
The internal surface was 1920×1080 in a real 2560×1080 fullscreen,
306 units, simulation 0.991456×, backlog 0 and ETW without losses.
The game exited with code 0, without errors nor remaining workers. There were no
compilers, profilers nor screenshots during the measurement. The 120+120 s
diagnostic does not meet the acceptance duration and also fails performance.
Build and sources: `evidence/phase4-5/browser-performance-build-1/`; JS fix
and regression test: subdirectory `runtime-correction-2/`.

36 existing CPU cases of the backend, 12 of the measurement contract,
10 new ones of persistent blocks/continuations and 4 of HTTP Range passed. The
new cases check reads across blocks/EOF, offline reuse of the
cache, local and network corruption, a server without ranges, LRU, shared
requests, the order of uploads/draws when compiling asynchronously and propagation
of a shader failure. The eight existing renderer-session cases also
passed. The GPU probes before warmup passed as well: 1,536 bytes
of buffers, 76 of textures and 64 of asynchronous pipelines. This and the clean
shutdown do not vouch for full visual parity nor for the phase's acceptance.

The later analysis of `stutter-analysis.json` observed 599 turn updates,
p95 108.32 ms and maximum 585.04 ms, against p95 1.45 ms between turns.
The pipelines stayed at 78, with no new compilations in the observed
interval. They are wall-clock correlations, not exclusive CPU attribution.

After the measurement `webgpu-worker-present.mjs` was prepared for Present inside
the worker's rAF. **It is not in package -2 and has been neither verified nor
measured.** Its callbacks still have to be tested and the harness has to reject any capture
that uses its background timer. Keep package/evidence -2.

## Technical sources and scope

[Emscripten SIMD](https://emscripten.org/docs/porting/simd.html) requires
enabling the target at compile time. [Asyncify](https://emscripten.org/docs/porting/asyncify.html#optimizing-asyncify)
adds instrumentation and cost, so the combined result has to be measured.
[IDBFS](https://emscripten.org/docs/api_reference/Filesystem-API.html#idbfs)
persists through syncfs; it does not turn reads into streaming automatically.
The [KHR specification](https://registry.khronos.org/webgl/extensions/KHR_parallel_shader_compile/)
offers non-blocking polling; it does not guarantee a shorter total compilation time.

The earlier profile shows a high cost of PortableBaselineInterpret and the AI.
The port's SpiderMonkey is compiled without JIT; the native one has a JIT. This is
a relevant difference; it does not prove that these improvements alone remove
the stutter. Scripts, AI and simulation speed are not changed to improve
the figures. There are no commits, commit messages, issues nor PRs. Human review
is mandatory before submitting changes to the project.
