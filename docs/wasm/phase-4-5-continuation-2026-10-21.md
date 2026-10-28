# Phase 4.5 continuation — 21 October 2026

The operator asked to resume analysis/tests and then apply improvements based
on web recompilation projects. Phase open. Do not run nor review the
native game. Keep load, quality and speed; human review before
submitting changes to the project. No commits, commit messages, issues nor PRs.

## State checked on resuming

The pause documentation of the 20th is historical. The most recent comparison,
`ai-worker-parity-5`, had already passed with the package
`application-phase4-5-ai-worker-4`: equal bytes of `simulation.dat`,
non-local debug and GUI state at 10,000 and 30,000 ms. Its 23 package hashes
matched the runtime report before starting another test.

## Measurement of the reused capture helper

`performance-ai-worker-diagnostic-3`: same package -4; 120 s of warmup
+120 s measured, skirmish, 306 units, real fullscreen/focus, 1080p internal.
No simultaneous screenshots, overlays, profiles nor builds.

| Metric | AI -3, earlier diagnostic | AI -4, new diagnostic |
| --- | ---: | ---: |
| Physical FPS | 34.69 | 35.89 |
| Physical p95 | 66.84 ms | 66.77 ms |
| Engine FPS | 37.43 | 39.91 |
| Engine p95 | 69.06 ms | 61.56 ms |
| Physical pauses >100 ms | 80 | 50 |

Simulation 0.993348×; observed backlog zero; zero lost ETW events;
no presentation fallback/error/cancellation; exit 0 without remaining workers nor
pthreads. NVIDIA driver 32.0.16.2101. It still does not pass p95 ≤33.4 ms.
They are single runs: no statistical significance is attributed.

The later analysis found 600 turn updates: median 38.87 ms,
p95 56.65 ms, maximum 483.81 ms; 550 exceed 33.4 ms and eight exceed 100 ms.
Between turns, p95 1.55 ms. They are wall-clock durations, not exclusive attribution
to the interpreter. The [result](evidence/phase4-5/performance-ai-worker-diagnostic-3/webgpu-skirmish-1.json)
and the [turn analysis](evidence/phase4-5/performance-ai-worker-diagnostic-3/stutter-analysis.json) are kept.

## Separate profile of the same package

`cpu-profile-ai-worker-4`: settling 120 s, CDP sampling 30 s, original
profiler saved afterwards. It finished without errors, with fullscreen/focus and a clean
shutdown. There was no simultaneous PresentMon.

In `cpu-12.cpuprofile`, of 31.25 s sampled:

- `CGame::Update`: 9.546868 s inclusive.
- Snapshot capture: 2.302193 s inclusive.
- AI result barrier: 1.983395 s inclusive.
- Upload through callback: 7.206281 s inclusive, with 6.740669 s under the pointer
  overload; that overload has 4.748738 s of self samples.
- `AppendUploadBytes`: 0.983369 s of inclusive samples.
- `_emscripten_get_now`: 1.433389 s of self samples, spread across
  script calls, the general clock and other stacks; not all of it is instrumentation.

The actor, `cpu-16.cpuprofile`, has 4.558270 s inclusive under
`PerformComputation`. These times overlap between functions and threads;
do not sum them nor present them as exclusive CPU or physical FPS.
[Specific analysis and hashes](evidence/phase4-5/cpu-profile-ai-worker-4/hotpath-analysis.json).

## Applied research

The [earlier](phase-4-5-web-ports-research-2026-10-21.md) research was checked
against public documentation and code of the revisions pinned there:

- [PSP Web Recomp](https://github.com/snuri00/psp-web-recomp): separates submission and
  explicit waiting, documents rotating buffers and the cost of reading clocks on
  every primitive. Its guest timing does not carry over to our RTS.
- [N64Recomp-browser/plume](https://github.com/amazingalek/N64Recomp-browser/blob/cabd2fe3e8e7c74091646f7d6299351fccfb6961/patches/plume.patch): publishes readback states
  with generations and groups push constant data before submit. The
  cache keys include the identity of the resources. Here there already are
  an upload arena, caches and ACK; enlarging queues does not remove their copies.
- [Flycast WASM](https://github.com/nasomers/flycast-wasm/blob/main/TECHNICAL_WRITEUP.md):
  prioritizes reducing crossings and validating optimizations against the
  reference path. Its JIT of SH4 instructions does not enable SpiderMonkey's JIT;
  it is another backend. Its authors' figures are not measurements of 0 A.D.

No external code was run nor were ROMs or assets downloaded. No code
was imported from those projects. The following modifications are our own.

## Combined transfer candidate — under verification

- The harness's fine-grained `ScriptCallTimer` timer was active on every
  outer C++→JS call. It is now optional at compile time: disabled by default,
  enabled with `WASM_SCENE_SCRIPT_TIMING_ENABLED=1` for diagnostics.
  The simulation clock and the frame/turn metrics are kept.
- The upload through callback generates the bytes directly into the own package,
  preserves alignment neighbours and zeros for partial writers, and updates
  the CPU mirror after the callback finishes. It removes the temporary vector
  and one copy of its region. It keeps the package copy for the ACK: it is not
  a zero-copy path nor does it allow reusing memory while the worker reads it.
- On a callback exception, the helper restores the package size and does not
  modify the mirror. Commands and uploads keep their original order.
- `engine-transfer` rebuilds the 483 units in `application-transfer`,
  with two CPUs and 8 GiB; `link-transfer` produces an independent destination.
  The link and manifest flags identify both improvements.

200,464 differential cases of the new generator against the earlier
producer passed, plus 200,464 of the existing alignment helper (eight checks
added). The timer test confirms zero reads with the mode disabled
and two reads for a nested call with diagnostics enabled.
50 Node cases of snapshots, files, presentation, commands, session and resources passed.
These CPU tests do not by themselves prove visual parity nor GPU performance.

Update of the 22nd: build/link, parity and physical capture completed.
The candidate does not fix the pauses: 34.85 physical FPS with p95 66.77 ms.
Results and next diagnostic in
[the continuation of the 22nd](phase-4-5-continuation-2026-10-22.md).
