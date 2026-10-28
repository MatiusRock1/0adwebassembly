# Performance: research of web ports — 21 October 2026

> Later update: the reused helper has already been measured and profiled; the
> operator asked to apply timing and transfer improvements. See the
> [continuation and new evidence](phase-4-5-continuation-2026-10-21.md).

Requested by the operator after the AI diagnostic. **Phase 4.5 open.**
Native versions are neither run nor reviewed. Public repositories
and the code of their web layers were inspected; no external code was run nor were
ROMs or assets downloaded. The figures announced by those projects are not
our measurements and do not prove equivalent performance for an RTS.

## What just failed in our candidate

`application-phase4-5-ai-worker-2` keeps SIMD, rAF in the render worker,
asynchronous pipelines, block IndexedDB, IDBFS and JSPI. It passed the
sync/threaded equality at 10 and 30 s, including the bytes of `simulation.dat` and non-local debug.
Its diagnostic `performance-ai-worker-diagnostic-1` finished without errors,
simulation 0.992667×, backlog 0, ETW without losses, 306 units and a clean shutdown.

| Physical metric | Earlier rAF | Isolated AI -2 |
|---|---:|---:|
| FPS | 39.83 | 35.32 |
| p95 | 50.12 ms | 66.83 ms |
| Pauses >100 ms | 113 | 67 |

They are single runs. The mean and p95 got worse although the tail
of long pauses decreased. The analysis of the 599 turn updates of the
last capture gives a median of 39.97 ms, p95 51.85 ms, maximum 484.17 ms and eight
updates >100 ms. **590 updates exceed 33.4 ms.** Moving work to another thread has
not reduced the cost of the critical path enough.

**Environment change observed:** the inventory of the rAF run and of the AI
-1 diagnostic records NVIDIA `32.0.16.1742`; that of AI -2 records `32.0.16.2101`.
Chrome stays at `155.0.8059.85`. Do not attribute the whole difference
between those captures to the code without a WebAssembly control on the current driver. No
drivers were modified. The failures against the absolute p95 limit remain.

The separate profile `cpu-profile-ai-worker-2` passed, 30 s of sampling after
120 s of settling. The engine stack shows 9.430474 s under
`CGame::Update`, 2.615183 s under `UpdateGameState` (including 2.196261 s of
`Capture`) and 2.204277 s under the result barrier. The AI consumes 4.785127 s
inclusive on its thread. **Do not sum inclusive times nor confuse them with exclusive
CPU**; the two threads overlap. There was no profiling during PresentMon.

## Pinned sources and applicable findings

Trees, revision and provenance were saved in `wasm/research/2026-10-21/`.
`source-manifest.json` records the URL and SHA-256 of every downloaded file.
They are research references, not code incorporated into the engine.

### PSP Web Recomp

Revision `37826ab881d9a593efb842fe47adfae2e9118b5d`, commit of 15 October.
The [GE worker](https://github.com/snuri00/psp-web-recomp/blob/37826ab881d9a593efb842fe47adfae2e9118b5d/profile/host/ge_worker.cpp)
separates asynchronous publication and a waiting call. It processes the queue in order
and returns control to the browser after presenting. The
[synchronization](https://github.com/snuri00/psp-web-recomp/blob/37826ab881d9a593efb842fe47adfae2e9118b5d/profile/host/ge_worker.hpp)
layer allows waiting for a specific finished work ID.

Application to 0 A.D.: group preparation with own data and wait only at
the boundary that needs the result. Our actor was making several
synchronous preparation calls per turn. The GPU queue already has payload
ownership and ACK; increasing its capacity without independent frame resources
does not demonstrate better overlap.

Its busy-wait and its per-frame guest clock are not copied. Our contract
requires the original simulation in real time. The swap tuning described in
its [notes](https://github.com/snuri00/psp-web-recomp/blob/37826ab881d9a593efb842fe47adfae2e9118b5d/docs/internals.md)
answers to PSP calls and is not a transferable WebGPU configuration.

### N64Recomp-browser / RT64 / plume

Revision `cabd2fe3e8e7c74091646f7d6299351fccfb6961`, commit of 21 October.
The [findings](https://github.com/amazingalek/N64Recomp-browser/blob/cabd2fe3e8e7c74091646f7d6299351fccfb6961/docs/findings.md)
document timing problems, overly broad waits and graphics
memory. The applicable lesson is to keep the lifetime of the data until its
consumption and to limit each barrier to the work it really protects. Its tests
of hidden tabs and rAF cadence do not vouch for our fullscreen FPS.

The [plume patch](https://github.com/amazingalek/N64Recomp-browser/blob/cabd2fe3e8e7c74091646f7d6299351fccfb6961/patches/plume.patch)
uses keys with resource identity and ranges to reuse bind groups and
contemplates asynchronous pipeline construction. This gives a concrete line
for auditing object churn and caches, keeping invalidation and ownership.
In our capture the pipelines went from 78 to 79 between snapshots, which
include the warmup: there is no evidence that their compilation explains the
recurring stutters of the interval. Do not prioritize another blind prewarm.

The exact forks of that revision are in
[`forks.txt`](https://github.com/amazingalek/N64Recomp-browser/blob/cabd2fe3e8e7c74091646f7d6299351fccfb6961/forks.txt).
Its [RT64 adapter](https://github.com/amazingalek/N64Recomp-browser/blob/cabd2fe3e8e7c74091646f7d6299351fccfb6961/renderer/rt64_web_renderer.cpp)
keeps WebGPU on the window and the game in pthreads. Therefore, the smoothness
cannot be universally attributed to moving WebGPU to OffscreenCanvas: it depends
on the cost and the dependencies of the engine.

There is no public web parameter equivalent to choosing FIFO/mailbox or the
number of swapchain buffers: the
[configuration exposed by Chromium](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/renderer/modules/webgpu/gpu_canvas_configuration.idl)
lists device, format, usage, views, colour space, alpha and tone mapping.
An engine's internal triple buffering must be solved with its own
resources and dependencies; it is not enabled by adding a flag to `configure()`.

### Conker and the limits of the examples

`amazingalek/CBFD-Recompiled-web` was pinned to
`b391ebfd21d42e6ff98d26dffa50b727a0e88111`, commit of 21 October.
Its [README](https://github.com/amazingalek/CBFD-Recompiled-web) describes audio
through AudioWorklet and shader lists by sections. It is a consumer of
N64Recomp-browser, not a second independent test of the same technique.
Its announced FPS is not used as a comparable target for 0 A.D.

### Flycast WASM: scope of dynamic recompilation

The [technical writeup](https://github.com/nasomers/flycast-wasm/blob/main/TECHNICAL_WRITEUP.md)
describes generating Wasm modules compiled by the browser, sharing
memory/table, and asynchronous promotion of blocks. It shows a different way of
writing executable code into linear memory. **It does not enable
SpiderMonkey's JIT with a flag**: it would require a new backend, invalidation, GC,
ABI and semantic verification. Its figures are the author's claims, not
our checks. That JIT is not incorporated into the current candidate.

### References that do not justify importing a solution

The documentation of [Dusk wasm](https://github.com/sh1ftmaker/dusk-wasm/blob/wasm-port/docs/wasm-port-notes.md)
and its README acknowledge an experimental state and loading/thread limitations;
it is not taken as proof of a full smooth match. The
[reVC web README](https://github.com/origami-ltd/wasm-revc) distinguishes the web
layer from the game code and presents itself as source-available; only its
description was consulted here, without copying code nor running its instructions.
No authors were contacted nor were issues, PRs or external records opened.

## Derived changes in our code, still to be measured

The first application relies both on the local profile and on the separation
between publication and waiting observed in PSP Web Recomp. It is our own
implementation, without copying external code:

1. `AIWorkerScript.h`: enumerate owners of UnitAI, ResourceSupply and
   ResourceGatherer instead of querying three interfaces on each AIProxy.
   Keep the set of proxies, fields and values; do not omit entities
   by distance, visibility or a frame budget.
2. `CAIWorkerClient`: group the turn's own inputs with its computation
   in one actor message; keep the updates in order. The number
   of players is obtained when creating/deserializing players, avoiding a
   request to the actor every turn for a stable value.
3. Keep the generation/sequence, the command order and the original
   flush/serialization barrier. Do not give the worker live access to the state.

Four Node snapshot cases passed, including the query count and the
exclusion of owners without AIProxy. The candidate's four units compiled
and the link finished. The first
build attempt found Docker without an available backend; once the
service was checked, the retry finished correctly.

`application-phase4-5-ai-worker-3` was packaged separately and
`ai-worker-parity-4/comparison.json` passed: bytes of `simulation.dat`, non-local
debug and GUI state identical sync/threaded at 10 and 30 seconds; both
shut down without errors nor remaining workers. They are limited checks.
The fullscreen measurement `performance-ai-worker-diagnostic-2`, 120+120 s,
**finished without fixing the smoothness: 34.69 physical FPS /p95 66.84 ms** and
37.43 engine FPS /p95 69.06 ms. There were 80 physical pauses >100 ms,
simulation 0.993967×, backlog 0, ETW without losses and a clean shutdown. There was no
presentation fallback, errors nor remaining workers. Candidate -3 is not adopted
as a fix. The 599 turn updates had a median of
45.09 ms and p95 66.31 ms; nine exceeded 100 ms.

The later, separate profile `cpu-profile-ai-worker-3` also finished
correctly: in about 30.95 s sampled, Update adds up to 10.081756 s,
Capture 2.854747 s and the barrier 2.180490 s inclusive. The actor accumulates
5.218825 s under PerformComputation. The capture did not improve in this run.
All that time is not attributed to a single getter nor is statistical significance
established between single runs.

## Next finding: helper compiled every turn

`CAIWorkerClient::Capture` was calling `Interface::Eval` with a new IIFE
every turn. `Interface.cpp` creates CompileOptions and SourceText and calls
`JS::Evaluate`. The profile under Capture records 2.519232 s inclusive in
Evaluate and 0.334019 s in WriteStructuredClone. **Evaluate includes running
the code; they are not 2.52 s of compilation.** The global compilation and
parsing stacks have much smaller and overlapping times.

A capture function installed once per context was prepared, called
through `Script::Function::Call` every turn. It reuses bytecode and its ICs,
but obtains new data on every call. Five Node cases passed,
including a state change between calls with the same function identity.
The new variant still has to finish build, equivalence and measurement: it is not
claimed that this change removes the dominant cost nor that it enables a JIT.
The earlier packages and the compiled sources of -2 were preserved in
`evidence/phase4-5/ai-worker-build-2/`.

If this does not reach the p95, the next decision must come from the times
of the new candidate: capture, AI barrier, remaining update work
and submission/render waits. A larger move of the simulation would require render
snapshots and explicit per-frame ownership; running render and
simulation at the same time over the same components would introduce races. Running
the AI in the browser's JavaScript would also require service,
serialization and determinism contracts; it is not a transparent replacement of the context.

No commits, commit messages, issues nor PRs were created. The modifications
require human review before being submitted to the project.
