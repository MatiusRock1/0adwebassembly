# WebGPU presentation through rAF — 19 October 2026

**Resumed on 20 October by the operator.** See the
[active continuation](phase-4-5-continuation-2026-10-20.md). The phase stays open.

The [continuation of 20 October](phase-4-5-ai-worker-2026-10-20.md)
records the later CPU profile, the isolated AI experiment and an
initialization failure detected before adopting it. This document keeps the
earlier rAF measurement; do not attribute AI candidate results to it.

The candidate `wasm/dist/application-phase4-5-browser-perf-raf-1` implements
the final delivery to the canvas inside the render worker's native rAF. It reuses
the linked Wasm of `linked-browser-perf`; it does not change AI, rules, speed,
units nor quality. The earlier measured package `browser-perf-2` is kept.

## Implementation

- `webgpu-worker-present.mjs`: at most one pending presentation,
  callback cancellation, protection against late callbacks, error
  propagation and rejection of an asynchronous final function. It counts only
  deliveries that returned correctly; it does not vouch for physical presentation.
- The 250 ms fallback is kept to allow progress with rAF suspended.
  The harness rejects any fallback increment, errors, cancellations,
  restart or absence of the render worker's mandatory counters.
- The validation conservatively covers the whole interval between snapshots,
  including the warmup. It does not try to attribute a fallback to a
  PresentMon physical instant. Failures before the initial snapshot do not
  invalidate that interval by themselves.
- `webgpu-render-worker.mjs`: exposes accumulated/maximum wait and the number of
  pending messages, in addition to the times waiting for rAF. The maxima are
  historical since the worker started; they cannot be subtracted between snapshots.
  `lastFrameId` is a local counter, with no correspondence to PresentMon IDs.
- The strict command order and the own presentation texture are kept.
  Acquiring the canvas texture, copy and submit remain in a
  single synchronous task. No per-frame GPU wait was added.

The queue still waits for the presentation before consuming the next
message. No overlap through per-frame resources was implemented nor were
engine frames discarded. The helper's explicit cancellation is tested;
the normal shutdown RPC still goes through the queue and may wait for the fallback.

## Verification

45 Node tests passed: the eight new presentation ones and the existing
browser performance, session, command data, state
and resource lifetime suites. 14 benchmark contract tests and 12 of the
presentation analyzer passed (71 in total). They are CPU tests, not GPU evidence.

The packager verified the link hashes and generated a new destination.
The first physical attempt, in `performance-browser-perf-raf-1`, failed before
loading the game: Chrome closed because of GPU process failures with access denied
`0xC0000022` inside the sandbox. That folder is kept as a failed attempt.
The second attempt ran outside the sandbox, without disabling Chrome's own
sandbox.

## Physical diagnostic completed

Evidence: [full result](evidence/phase4-5/performance-browser-perf-raf-2/webgpu-skirmish-1.json),
[summary](evidence/phase4-5/performance-browser-perf-raf-2/summary.json),
[turn analysis](evidence/phase4-5/performance-browser-perf-raf-2/stutter-analysis.json).

Chrome 155.0.8059.85, NVIDIA/Ampere, WebGPU in the render worker, fullscreen,
1920×1080 internal, 306 units; 120 s of warmup + 120 s measured.
No screenshots, overlays, builds nor simultaneous profiles.

| Metric | Earlier `browser-perf-2` | New rAF |
| --- | ---: | ---: |
| Physical FPS | 24.54 | 39.83 |
| Engine FPS | 45.86 | 45.37 |
| Physical p95 | 100.14 ms | 50.12 ms |
| Engine p95 | 49.41 ms | 47.64 ms |
| Physical pauses >100 ms | 175 | 113 |
| Simulation rate | 0.99146× | 0.99251× |

The interval between snapshots recorded 10,648 deliveries through rAF, zero fallback,
zero errors and zero cancellations. It includes the warmup and does not represent only
the 120 s measured. There were zero lost ETW events, maximum observed backlog
zero and a shutdown with code 0, without remaining workers nor pthreads. Our own
ports 8097/9229 stopped listening at the end.

It is a comparison between single runs, without established statistical
significance. The observed improvement does not remove the difference between
engine and screen: PresentMon recorded 4,857 presents, 4,781 displayed and 76 not
displayed; there is still no direct correspondence with the engine's IDs.
The pipelines went from 78 to 79 between snapshots, an interval that includes the
warmup: it does not allow attributing a specific stutter to compilation.

## Pending limit: simulation

The later analysis found 600 turn updates: median 26.90 ms,
p95 104.84 ms and maximum 616.57 ms. Between turns, p95 1.50 ms and maximum
2.88 ms. They are wall-clock durations, without exclusive attribution to SpiderMonkey.

`CAIWorker` was not moved: it currently shares data from `Sim`/`SimEngine`
and runs `PerformComputation()` synchronously from
`WaitToFinishComputation()`. Moving it to another worker requires a contract of
snapshots and commands that keeps the original application boundary,
RNG, serialization and deterministic order. That migration is not presented as
implemented nor verified. The existing profile scopes separate setup,
state reading, shared component and player scripts; the next
diagnostic must quantify those costs and the waits without measuring physical FPS
at the same time.

**Phase 4.5 open:** it does not pass p95 ≤33.4 ms, nor does it replace the three 900 s
repetitions per load. `passed=true` indicates a correct run; the physical gate
and `phase45Accepted` remain false. No commits, commit
messages, issues nor PRs were created. It requires human review before submitting to the project.
