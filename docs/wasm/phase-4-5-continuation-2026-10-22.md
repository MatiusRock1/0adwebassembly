# Phase 4.5 — continuation of 22 October

Continuation and results of the second candidate:
[23 October](phase-4-5-continuation-2026-10-23.md).

The phase stays open. The candidate `application-phase4-5-transfer-1` does not
fix the stutter and is not adopted as a solution because of its mean FPS.

## Verification of the transfer candidate

Build, link and sync/threaded parity at the 10 and 30 second
checkpoints were completed. The serialized bytes also match the
original checkpoints. Evidence: `evidence/phase4-5/transfer-parity-1`.
This checks those specific states, not every match nor visual parity.

The independent physical capture, after 120 seconds of warmup and over
120 seconds, produced:

| Metric | Result |
|---|---:|
| Physical FPS | 34.8545 |
| Physical p95 | 66.7699 ms |
| Engine FPS | 41.0099 |
| Engine p95 | 57.325 ms |
| Physical pauses longer than 100 ms | 85 |
| Simulation rate | 0.99354 |
| Units | 306 |

There were no ETW losses, renderer errors/fallback nor pending workers at
shutdown. Evidence: `evidence/phase4-5/performance-transfer-diagnostic-1`.
It does not pass the 33.4 ms p95 target. It does not demonstrate a physical improvement over the
earlier candidate. It does not replace the full acceptance of loads/repetitions.

Of 599 turn updates, 591 exceeded 33.4 ms; median 39.665 ms,
p95 53.9003 ms and maximum 456.820 ms. Between turns, p95 1.720 ms.

## Locating the next cause

In the separate profile `cpu-profile-ai-worker-4`, the 1.983395 s sampled
in the result barrier belong to `CCmpCommandQueue::FlushTurn`.
The futex residency was 1.974074 s. There are contiguous groups of samples
of up to about 411 ms. They are residency samples, not exact call
durations nor exclusive CPU. It should not be attributed to saving
nor should the wait be removed by delivering commands on a different turn.

A strictly diagnostic variant is being prepared with SpiderMonkey cooperative
interrupts to record file and line while the actor
computes. The variant requests samples every 10 ms; its interrupts may
cluster and be biased by the VM's check points. Its counters
are not CPU times nor FPS evidence. It must be marked `diagnosticOnly` from
the build to the package, and not be mixed with the physical capture.

The probe passed in the browser: `evidence/phase4-5/ai-guest-profile-1`, with a clean
shutdown and 19 profiles. In the window there were 730 requests, zero samples without
a caller and zero overflows. The most frequent locations were:

| Location | Cooperative samples |
|---|---:|
| `common-api/map-module.js:195`, obstruction sweep | 120 |
| `common-api/map-module.js:58`, influence loop | 100 |
| `common-api/map-module.js:126`, clamped assignment | 72 |
| `common-api/shared.js:312` | 59 |
| `petra/mapModule.js:127` | 53 |
| `common-api/map-module.js:91`, constant influence | 43 |

These figures guide the research; they are not CPU percentages.

An optional candidate `WASM_AI_MAP_KERNELS` was implemented: the
`addInfluence` loop works directly on the owning context's Uint8Array,
without transferring state nor RNG. It keeps doubles, expression order, original
exclusive bounds, per-cell clamp and truncation. It does not use fast-math nor
FMA contraction. For parameters outside the validated domain, shared arrays,
another array type or custom methods, it uses the original JS function.
The original `public.zip` does not change; the link installs the wrapper on the prototype
of the already loaded module before creating the shared component.

Differential test: 5,000 cases and 1,370,712 bytes identical to the original JS module.
It includes fractional centres, clipping, fractional maxima and negative strengths.
Evidence: `evidence/phase4-5/ai-map-kernels-build-1/differential.json`.
It does not test all possible inputs nor the full behaviour of the game.

The candidate `application-phase4-5-ai-map-kernels-1` completed parity in
`evidence/phase4-5/ai-map-kernels-parity-2`: both modes keep the original
10 and 30 second hashes and a clean shutdown. The `parity-1` run also saved
those states, but the browser closed before finishing the threaded
diagnostic; it is kept as incomplete, not as an approved verification.

The capture `performance-ai-map-kernels-diagnostic-1` completed 120 seconds
after another 120 of warmup, without concurrent tools:

| Metric | Transfers, no kernel | Native influence |
|---|---:|---:|
| Physical FPS | 34.8545 | 40.7312 |
| Physical p95, ms | 66.7699 | 60.3574 |
| Physical pauses >100 ms | 85 | 40 |
| Engine FPS | 41.0099 | 45.2553 |
| Engine p95, ms | 57.325 | 54.340 |
| Turn Update median, ms | 39.665 | 37.675 |
| Turn Update p95, ms | 53.9003 | 46.6381 |
| Turn Update maximum, ms | 456.820 | 108.205 |

In the new candidate there were 600 turn updates; 569 exceeded
33.4 ms and one exceeded 100 ms. Between turns, p95 1.540 ms. Simulation 0.99390,
306 units, without ETW losses nor presentation fallback/error, and a clean shutdown.
It is a favourable short comparison, not a statistical demonstration nor the
phase acceptance. The p95 still misses the target.

The missing audio warning was dismissed by the operator, who confirmed
hearing it. In addition `ai-map-kernels-audio-1` passed: original commands for pausing,
resuming, stopping and restarting the music, with a clean shutdown. No
audio modification was applied because of that warning.

A second candidate is being prepared with the `isObstructedTile` sweep in C++.
It keeps the dy/dx order and the four original checks per cell,
returns the same first blocked coordinate and keeps the pattern in JS.
The differential test of 10,000 searches passed. The first link detected a
non-instantiated vector conversion; it was replaced by reading the needed
elements with the SpiderMonkey API. The failed log is kept in
`ai-map-kernels-build-2`.

Pending: verify the second candidate in the browser and measure it. The phase
stays open: a complete solution to the pauses has not yet been verified.
