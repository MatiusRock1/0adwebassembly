# Phase 4.5 — continuation of 25 October

Continued on [26 October](phase-4-5-continuation-2026-10-26.md) (automatic
graphics profile for weak GPUs, disk cleanup).

The phase is still open. Operator priority: performance. Yesterday's record:
[24 October](phase-4-5-continuation-2026-10-24.md).

## How to resume (state at the end of 25 October)

Read this section first; the rest of the document is the record that backs it.

### Operator goals and decisions of the day

- Lock the web build at 30 FPS for real, "even if it means modifying the game".
- Ignore the pause of the chained unit creation at the start of the test: it is
  setup, not gameplay.
- The turn cushion was approved knowing it adds latency before turns.
- Once the cushion worked: a landing page and a Docker image to publish the build.

### Current best candidate

`cushion-1` (package `wasm/dist/application-phase4-5-cushion-1`) =
`sim-kernels-3-30` + present pacing (`WASM_PRESENT_PACING`, early GPU submit in the
render worker) + asynchronous OpenAL (`WASM_AUDIO_ASYNC`) + turn cushion
(`TURN_LEAD` 4, `MAX_LEAD` 3, `WASM_WEBGPU_ASYNC_CALLS` 24). Parity
`cushion-1-parity-1` passed. Combat (`ab13`): 29.92 FPS, p95 33.41 ms, p99
50.0 ms, 1 % low 17.1 FPS, one pause over 100 ms per minute. Skirmish: 29.99 FPS,
no pause. The web copy `application-phase4-5-cushion-1-web` (same `.wasm`, plus
`?renderer=webgpu`) is what the Docker image serves.

### Decisions waiting for the operator

1. Decided (end of 25 October): the FPS gate is the 30 FPS lock, a displayed
   mean of ≥ 29.5 FPS and a physical p95 ≤ two refreshes (closure plan updated).
   `cushion-1` meets it in short combat and skirmish captures.
2. Whether the cushion's latency is acceptable in play (frames before a turn are
   shown up to ~107 ms after they start).

### Next steps, in order

1. The long acceptance battery with `cushion-1` (3 × 900 s per workload, ~1 h 45 min
   of captures; ask the operator for the time first).
2. The intermittent `GetPropIRGenerator::tryAttachStub` crash, a risk for that
   battery. New today: the `null function` trap matches a proxy whose handler
   pointer reads zeroed memory, so that `GetProxyStubType` takes the DOM-proxy
   path and calls the unset `GetDOMProxyShadowsCheck`: an object pointer that is
   stale or corrupt, not a fault of the IC itself (see "Intermittent crash").
3. Remaining slow turns (82–150 ms: reinforcement turns and AI waits such as the
   recurring turn 629), now the only source of pauses: unit creation, `CanAttack`,
   UnitAI state switches, Petra's planning spikes.
4. First-use loads at the start of a real battle (sound groups decoded on first
   play, animations): preload them during the loading screen.
5. Before publishing: third-party license texts in the image, the repository
   updated with these changes, HTTPS hosting.

### Commands

Docker runner and build scripts as on 24 October, plus:

```text
# Turn cushion on top of the audio build
wasm/scripts/phase4-5-turn-gate-build.py --base audio-async-1 --variant cushion-1 \
    --unit renderer/backend/webgpu/Device.cpp --recorded-unit main.cpp \
    --harness-header application-clock.h --harness-header application-frame-time.h \
    --harness-header application-present-pacing.h --define WASM_WEBGPU_ASYNC_CALLS=24 \
    --define WASM_PRESENT_PACING_TURN_LEAD=4 --define WASM_PRESENT_PACING_MAX_LEAD=3

# Asynchronous audio on top of present pacing
wasm/scripts/phase4-5-turn-gate-build.py --base present-pacing-1 --variant audio-async-1 \
    --unit soundmanager/SoundManager.cpp --js-library application-openal-async.js \
    --define WASM_AUDIO_ASYNC=1

# A paced capture has no single-refresh intervals: pass the refresh measured on a
# reference capture of the same display
wasm/scripts/analyze-presentation.py --output OUT/presentation-two-refresh.json \
    --refresh-ms 16.66955 --refresh-source "reference captures" OUT/webgpu-combat-1.json
wasm/scripts/summarize-phase4-5-abba.py --reference A1 A2 --candidate B1 B2 --output SUMMARY

# Diagnostic GUI notification log (off by default)
PHASE45_NOTIFICATION_LOG=1 wasm/scripts/benchmark-phase4-5-standalone.py ...

# Web deployment
python wasm/deploy/prepare-context.py --package wasm/dist/application-phase4-5-cushion-1-web \
    --output wasm/build/deploy-context
docker build -t 0ad-wasm-web wasm/build/deploy-context
docker run --rm -p 8080:8080 0ad-wasm-web
wasm/.venv-phase3/Scripts/python.exe wasm/deploy/smoke-test.py --base http://localhost:8080
```

### Measurement display

Captures must land on the 2560×1080 Parsec virtual display (primary, 60.00 Hz
since today; `foregroundWindow.clientSize` = [2560, 1080]). The laptop panel runs
at 144 Hz and is not comparable.

### Not committed

All changes of this session are in the working tree for the operator to review
(AGENTS.md: agents do not create commits).

## Present pacing (`WASM_PRESENT_PACING`)

First step of yesterday's list: fix the pacing of the 30 FPS cap (see "Pacing
problem of the first 30 FPS cap" on 24 October).

### What a turn frame costs

The frame log of `performance-ab8-sim-kernels-3-30-combat-60s-1/2` (frames grouped
by tick change) gives the cost that the pacing has to absorb:

| Combat, 60 s | turn frames | other frames |
|---|---:|---:|
| `CGame::Update`, median / p90 / p95, ms | 25.6 / 44.8 / 53 | 1.3 / 1.6 / 1.7 |
| Start of this frame to start of the next, median / p90, ms | 52.6 / 72.8 | 33.3 / 33.5 |

A turn frame keeps the engine thread busy for ~53 ms (the turn, rendering, the
GUI simulation update and the deferred AI capture after `Present`), not the
~38 ms assumed yesterday. One frame in six carries a turn. Yesterday's design
(start a turn frame early on the engine side, presenter unchanged) gives it
~37 ms and cannot keep a frame that finishes early from being shown early, so it
was not implemented.

### Design

- **The render worker paces the presents.** `WorkerPresentation`
  (`wasm/browser/webgpu-worker-present.mjs`) presents a paced frame at the first
  display signal (worker rAF) at least one cap interval after the previous paced
  present, with 2 ms of tolerance for timestamp jitter (below every refresh
  period up to 240 Hz, so a signal one refresh too early never passes). A frame
  ready early is held; a late frame moves the cadence (the next deadline is the
  late signal plus one interval) instead of letting the next frame follow one
  refresh later. On 60 Hz this is exactly every second refresh.
- **The worker publishes every paced present** into a small shared block
  (`wasm/harness/application-present-pacing.h`): a count, stored last and
  notified, and the signal time of the present in one of two alternating slots.
  `Device.cpp` passes the block address and the cap interval with each
  `present` call; a present without those arguments (any earlier engine build)
  keeps the original behaviour.
- **The engine starts frames from the presents** (`DisplayClock::Wait` in
  `wasm/harness/application-clock.h`): a frame starts when the previous one has
  been shown, so its whole interval is available. The frame that will run the
  next simulation turn and the one before it (`WASM_PRESENT_PACING_TURN_LEAD`,
  default 2) start as soon as the engine is free while one frame still waits to
  be shown, which gives the turn frame two display intervals. The turn is
  predicted from the turn manager's remaining time, published read-only after
  every update (`source/simulation2/helpers/TurnTiming.h`, written in
  `TurnManager.cpp`), at one cap interval per frame, with 1 ms of margin towards
  starting early. A wrong prediction only changes timing.
- **Frame time follows the display.** `FrameTime::SetNominal`
  (`application-frame-time.h`): a paced frame advances the game by the time
  between the display signals of its own and the previous frame, so a frame that
  starts early still moves the scene by one display interval, and the sum stays
  equal to the elapsed display time. Without a signal for both frames it uses the
  real elapsed time as before.
- **Fallbacks:** the display-signal wait of the first cap (main-thread rAF) still
  paces frames until the worker has paced a present, after a frame that presented
  nothing, and if presents stop for 1 s. Hidden pages keep the worker's 250 ms
  fallback present. WebGL never uses present pacing.

Cost: frames are shown at most two intervals after they start. Most frames
start when the previous one is shown (about one refresh later than with the
first cap); the two frames before a turn start up to one interval earlier still.
Input is sampled at the start of the frame, so their latency grows by that much.

Turns, commands and their order do not change; only wall-clock timing does.

### Tests

- `node --test wasm/scripts/test-worker-presentation.mjs`: the 8 earlier cases
  and 5 new ones (published count and signal, hold of an early frame, a late
  frame moves the cadence, 120 frames with ±0.5 ms signal jitter all at two
  refreshes, hidden-page fallback, unpaced presents unchanged). 13 pass.
- `wasm/build/phase4-5/build-application-frame-time.cmd` (native probe
  `wasm/probes/application-frame-time.cpp`): 7 new checks of the nominal time
  (early frame, unpaced frame, transitions, reset, fixed frequency, conservation
  over 600 frames with early and late presents). 13 checks pass.

### Build

`present-pacing-1` on `sim-kernels-3-30` (Docker runner as on 24 October):

```text
wasm/scripts/phase4-5-turn-gate-build.py --base sim-kernels-3-30 --variant present-pacing-1 \
    --unit renderer/backend/webgpu/Device.cpp --unit simulation2/system/TurnManager.cpp \
    --recorded-unit main.cpp --harness-header application-clock.h \
    --harness-header application-frame-time.h --harness-header application-present-pacing.h \
    --header simulation2/helpers/TurnTiming.h --define WASM_PRESENT_PACING=1
wasm/scripts/phase4-link.py --build /phase45-build/application-present-pacing-1 \
    --output /phase45-build/linked-present-pacing-1 --release --exception-mode wasm --jspi \
    --spidermonkey-library /phase45-build/spidermonkey-portable-switch-o3-runscript-timer/libjs_static.a
wasm/scripts/phase4-5-package.py --linked-directory wasm/build/phase4-5/linked-present-pacing-1 \
    --target-directory wasm/dist/application-phase4-5-present-pacing-1
```

The workspace `Device.cpp` differs from the frozen copy of the base only by the
`WASM_WEBGPU_ASYNC_CALLS` macro (default 6, the same value). Only the three units
were recompiled; their private headers resolve to the candidate's copies.

Parity `present-pacing-1-parity-1` **passed** with the original hashes in both
modes: `e35b3f94…` at 10 s and `b218d9a3…` at 30 s.

## The display changed to 144 Hz

The first capture of the new build, `performance-present-pacing-1-combat-60s-1`,
ran on the laptop panel (1536×864 CSS pixels at DPR 1.25, 144 Hz, driven by the
integrated GPU): display intervals of 27.8, 34.7 and 41.7 ms are 4, 5 and 6
refreshes of 6.94 ms. On 24 October the captures ran on the 2560×1080 display at
59.95 Hz (`clientSize` 2560×1080). It is **not comparable** and does not count.
It shows what the pacing does at 144 Hz: frames every five refreshes (28.8 FPS),
no pause over 100 ms, p99 41.7 ms.

The operator then enabled the 2560×1080 display at ~60 Hz (Parsec virtual
display, primary). The batch below ran there.

At 144 Hz a hard 30 FPS cap cannot meet "p95 ≤ 33.4 ms" either: 33.3 ms is not a
multiple of 6.94 ms.

## Analyzer: refresh of paced captures

`analyze-presentation.py` measures the refresh from single-refresh intervals and
needs 20 % of them; a paced capture has almost none, so its
`presentationGateTwoRefresh` was always false. New options `--refresh-ms` and
`--refresh-source` take the refresh of the same display measured elsewhere and
record where it came from (`refreshSource`). Default behaviour unchanged; one new
unit test, 13 pass.

`wasm/scripts/summarize-phase4-5-abba.py` summarizes a batch with the refresh of
its reference captures. On `ab8` it reproduces yesterday's table exactly.

## Results of `present-pacing-1` (`performance-ab9-*`)

ABBA order, 60 s + 60 s, 2560×1080 display at 59.94 Hz (refresh 16.683 ms,
measured on the reference captures), all four captures valid. Summary:
`evidence/phase4-5/performance-ab9-summary.json`.

| Combat 60 s + 60 s | sim-kernels-3-30 | present-pacing-1 | change |
|---|---:|---:|---:|
| Pauses >100 ms | 19.0 | 5.5 | −71 % |
| Physical p99, ms | 100.10 | 58.43 | −42 % |
| 1 % low, FPS | 8.16 | 11.51 | +41 % |
| Physical FPS | 28.85 | 29.50 | +2.3 % |
| Physical p95, ms | 66.77 | 50.07 | 4 → 3 refreshes |
| Display intervals of 1 / 2 / 3 / 4+ refreshes | 28 / 52 / 11 / 9 % | 10 / 80 / 10 / 1 % | |
| Turn median, ms | 25.4 | 25.1 | = |
| Turns >60 ms / >100 ms | 11.0 / 2.5 | 16.5 / 3.5 | |
| Rate | 1.0000 | 0.9989 | |

The worker presented 97.8 % of its frames exactly two refreshes apart
(`pacedIntervals`, warmup included: 0 / 3,485 / 42 / 17 / 20 of 3,564). The
remaining 3-refresh display intervals come in 3-then-1 pairs: frames presented on
time but shown one refresh late. PresentMon shows why: from Chrome's `Present` to
display took 17–43 ms (median 25), and frames with long GPU work were the late
ones (GPU busy median 10 ms, p90 19 ms).

Cause: the render worker records a whole frame into one command encoder and
submits it in `present`. With the pacing hold, the GPU only started the frame at
its display signal, and a frame with more than ~12 ms of GPU work missed the
next refresh.

More turns over 60 ms with the pacing: not explained yet. A turn frame that
starts early reaches the AI turn gate earlier, so waits for the AI may move into
`CGame::Update`; not verified.

## Early GPU submit (`present-pacing-2`)

`webgpu-render-worker.mjs`: when a paced `present` arrives, the worker submits
the frame's GPU work at once; at the display signal only the copy to the canvas
and a small second submit remain. Browser-only change: the package
`application-phase4-5-present-pacing-2` has the same `.wasm` as
`present-pacing-1` and differs only in that module.

First capture, `performance-present-pacing-2-combat-60s-1` (same display):

| Combat 60 s + 60 s | present-pacing-1 (mean of 2) | present-pacing-2 |
|---|---:|---:|
| Display intervals of 2 refreshes | 80.0 % | 87.7 % |
| `MsUntilDisplayed` median / p90, ms | 25.1 / 34.7 | 15.4 / 15.6 |
| Pauses >100 ms | 5.5 | 6 |
| Physical FPS | 29.50 | 29.63 |
| Physical p95, ms | 50.07 | 50.02 |

Frames are now shown one refresh after Chrome presents them, except ~8 %. Of
the 108 intervals of 3 or more refreshes, 75 are frames presented on time but
shown late and 33 are frames the worker presented late. Frames with ≥ 18 ms of
GPU work are still late 35–50 % of the time; those with 10–15 ms, 5–6 %. The
p95 needs fewer than 5 % of intervals over two refreshes; this capture has 6.1 %.

ABBA `performance-ab10-*` (same display, 59.94 Hz), means of 2 against 2,
summary `evidence/phase4-5/performance-ab10-summary.json`:

| Combat 60 s + 60 s | sim-kernels-3-30 | present-pacing-2 | change |
|---|---:|---:|---:|
| Pauses >100 ms | 27.5 | 6.0 | −78 % |
| Physical p99, ms | 116.78 | 53.85 | −54 % |
| 1 % low, FPS | 7.19 | 10.62 | +48 % |
| Physical FPS | 28.32 | 29.63 | +4.6 % |
| Physical p95, ms | 66.77 | 42.81 | |
| Display intervals of 2 refreshes | 50.5 % | 89.1 % | |
| Turns >100 ms | 6.5 | 1.5 | |
| Rate | 1.0006 | 1.0004 | |

The p95 of 42.8 ms lies between two and three refreshes: on this virtual
display, display times are not strictly quantized to the refresh.

## Partial GPU submits (`present-pacing-3`, not adopted)

Submitting each command packet of a paced frame as it arrives, so the GPU works
while the engine records the rest (pass split and resumed with its contents
loaded; arena bytes uploaded at their offsets). One capture,
`performance-present-pacing-3-combat-60s-1`: 3.4 partial submits per frame, no
errors, but 5.4 % of intervals over two refreshes against 5.2–5.4 % for
`present-pacing-2`. No measurable gain, so the code was removed; the patch is kept
in `evidence/phase4-5/present-pacing-3-partial-submit.patch`.

## Where the remaining late frames and pauses come from

- **Harness maintenance.** Every ~6 s the harness reads the state and reinforces
  (1.2–1.3 s per sample). Those windows cover 27 % of the time but hold 40–71 %
  of the pauses over 100 ms and ~58 % of the 60–100 ms intervals with present
  pacing (`performance-ab10-present-pacing-2-*`, notification capture).
- **GUI notifications** (operator's observation). A diagnostic switch,
  `PHASE45_NOTIFICATION_LOG=1` for `benchmark-phase4.py`, logs each session
  notification with its simulation time (`guiNotifications` in the report; off
  by default). In `performance-present-pacing-2-combat-60s-notifications-1`:
  3,377 `playercommand` notifications from Petra (one per command; the GUI
  drops them at once outside observer follow mode) and 2 phase notifications.
  Petra reached the town phase during the warmup, with a 116.8 ms interval
  right at that moment. "You have been attacked" appears only when combat
  starts: `AttackDetection` suppresses further notifications while fighting
  continues nearby, and in the benchmark the first engagement happens during
  setup. No attack notification falls in a measured window.
- **Audio.** With `-nosound` (diagnostic package
  `application-phase4-5-present-pacing-2-nosound`, ABBA `performance-ab11-*` on
  the display now at 60.00 Hz) intervals of 3 or more refreshes drop from 5.75 %
  to 4.5 % and p95 from 46.1 to 35.9 ms (one capture at 33.52 ms); pauses over
  100 ms stay at ~4 per minute. Every OpenAL call from a pthread waits for the
  browser's main thread (all 93 SDK functions are proxied synchronously), and
  playing one sound takes ~14 of them.
- **Slow turns.** Every pause over 100 ms left in `performance-ab11-*` and
  `performance-audio-async-1-*` is a turn frame whose `CGame::Update` took
  82–150 ms; none is a garbage collection. Most fall in the harness's
  reinforcement windows; one recurs at turn 629 (an AI wait).
- **Main thread.** No browser long task (>50 ms) on the main thread in any of
  these captures, so it is not what delays presents.

## Asynchronous OpenAL (`WASM_AUDIO_ASYNC`, `audio-async-1`)

- `wasm/browser/application-openal-async.js`: AL calls that only set source or
  listener state, or start, stop or pause a source, are proxied without waiting
  (`__proxy: 'async'`); `alSourcefv`/`alListenerfv` read their values on the
  calling thread and send them by value. Queries, buffer uploads, buffer queues
  and deletions stay synchronous. The main thread's proxy queue is first in,
  first out, so the order of calls does not change. `alGetError` was already
  answered from shared memory (`application-openal-error.js`).
- `SoundManager.cpp`: a new sound no longer waits for the sound worker's pass
  over its items (which queries every source on the main thread): it goes to an
  incoming list that the pass takes first.
- `phase4-5-turn-gate-build.py`: new `--js-library` option, and a frozen
  transform that reapplies `phase4-application-patch.py`'s two Web Audio edits to
  `SoundManager.cpp` (verified byte for byte against the frozen copy).

Build on `present-pacing-1` (`--unit soundmanager/SoundManager.cpp --js-library
application-openal-async.js --define WASM_AUDIO_ASYNC=1`); the linked output shows
the setters proxied asynchronously and the queries synchronously. The operator
listened during `performance-audio-async-1-combat-60s-1` and confirmed the
sounds play normally. Frames ready before their display signal: 3,232 against
~3,110 with synchronous audio and ~3,340 without sound; intervals of 3 or more
refreshes 6.1 % (single capture). No AI parity: audio is not simulation state.

## Turn cushion (`cushion-1`)

Operator decision: give turn frames more time, accepting more latency on the
frames before a turn. `application-clock.h` now takes two parameters:
`WASM_PRESENT_PACING_TURN_LEAD` (how many frames up to and including the turn
frame may start early) and `WASM_PRESENT_PACING_MAX_LEAD` (how many frames may
wait to be shown when one starts); the n-th frame before the turn may start while
`TURN_LEAD - n` frames wait, at most `MAX_LEAD`. The defaults (2, 1) keep
`present-pacing-1`'s behaviour exactly.

A timeline model (light frames of 15 ms, 30 FPS) gives the turn frame, from its
start to its display signal:

| `TURN_LEAD`, `MAX_LEAD` | Turn frame time | Mean start-to-present latency over a turn |
|---|---:|---:|
| 2, 1 (present pacing) | 66.7 ms | ~42 ms |
| 3, 2 | 88.3 ms | ~52 ms |
| 4, 3 (`cushion-1`) | 106.7 ms | ~64 ms |

`cushion-1` = `audio-async-1` + (4, 3) + `WASM_WEBGPU_ASYNC_CALLS=24` (four frames
in flight need ~18 asynchronous calls; with 6 the engine would block on the
queue). Units recompiled: `main.cpp` (recorded) and `Device.cpp`.

First capture, `performance-cushion-1-combat-60s-1`: 29.92 FPS, p95 **33.40 ms**
(two refreshes), p99 50.0 ms, 1 % low 16.5 FPS, **one** pause over 100 ms, worker
presents 99.7 % two refreshes apart, rate 0.9994, no errors. It fails only
`presentationGateTwoRefresh`'s mean ≥ 30 FPS, which a hard 30 FPS cap cannot meet.
The remaining pause (150 ms at 55.8 s) is not a turn: updates of 1–2 ms around a
147 ms gap in frame receipts; cause not identified.

**Harness fix.** The ABBA `performance-ab12-*` lost both `cushion-1` captures in
the setup step "Original locked cursor did not reach (960, 540)". The step moves
the mouse and waited for two presented frames before reading SDL's cursor; with
up to four frames in flight those frames can predate the move, so it read stale
positions, over-corrected and oscillated. `move_original_pointer`
(`phase4_browser.py`) now waits for SDL's published position itself to change
(two-frame wait as fallback). This is the latency of the cushion showing up in a
test tool, not a game failure.

ABBA `performance-ab13-*` with the fixed step, 60.00 Hz display, all four
captures valid, summary `evidence/phase4-5/performance-ab13-summary.json`:

| Combat 60 s + 60 s | present-pacing-2 | cushion-1 | change |
|---|---:|---:|---:|
| Physical FPS | 29.70 | 29.92 | +0.7 % (cap 30) |
| Physical p95, ms | 49.98 | **33.41** | two refreshes in both captures |
| Physical p99, ms | 66.64 | 50.01 | −25 % |
| 1 % low, FPS | 10.79 | 17.09 | +58 % |
| Pauses >100 ms | 5.0 | 1.0 (0 and 2) | −80 % |
| Display intervals of 2 / 3+ refreshes | 85.7 / 7.0 % | 94.4 / 2.8 % | |
| Worker presents two refreshes apart | 98.0 % | 99.6 % | |
| Turns >60 ms / >100 ms | 11.0 / 2.5 | 13.0 / 1.5 | |
| Rate | 0.9998 | 1.0001 | |

Both `cushion-1` captures meet "physical p95 ≤ two measured refreshes"; they fail
`presentationGateTwoRefresh` only on its mean ≥ 30 FPS. Against yesterday's best
(`sim-kernels-3-30` in `ab10`): pauses 27.5 → 1, p99 116.8 → 50.0 ms, 1 % low
7.2 → 17.1 FPS, FPS 28.32 → 29.92.

- Parity `cushion-1-parity-1` **passed** with the original hashes in both modes
  (`e35b3f94…` at 10 s, `b218d9a3…` at 30 s).
- Skirmish `performance-cushion-1-skirmish-120s-1` (60 s + 120 s): 29.99 FPS,
  p95 36.09 ms, p99 50.01 ms, 1 % low 18.57 FPS, **no** pause over 100 ms, rate
  1.000; the worker presented 5,423 of 5,428 frames two refreshes apart, so the
  p95 above two refreshes comes from display timing on the virtual display.
  Single capture.
- Latency: the frames before a turn start up to three intervals before they are
  shown (model above: ~64 ms mean from frame start to present, against ~42 ms
  with `present-pacing-2` and ~22 ms with the first 30 FPS cap). Not measured with
  input; the operator should judge it in play.

## In-engine verification of the second-round kernels

Step 2 of yesterday's list. `sim-kernels-verify-combat-3b` (30 s + 60 s,
`sim-kernels-verify-3`, combat with reinforcement while sampling) passed:
`simKernelStats` installed 127, AI 33, verified 432,442 / 2,729 / 74 / 2,440 /
33,505 / 106,585 / 501 calls with **0 mismatches** in every kernel;
`aiKernelStats` 1,209 checks (18 `findBestTile`, 1,106 `addEnt`, 65
`updateTerritories`, 20 `createObstructionMap`), no mismatch and no fallback. This
run is a diagnostic build (each kernel also runs the original), not a performance
measurement.

## Intermittent crash: what the trap means

The failure of `sim-kernels-verify-combat-3` on 24 October surfaced in
`evaluateOriginalGUI` only because the launcher re-throws the engine worker's
recorded error (`application.mjs`, `window.applicationResult`); the trap itself was
in a worker. In SpiderMonkey 128, `GetProxyStubType` treats a proxy as a DOM proxy
when its handler's family equals `GetDOMProxyHandlerFamily()`, and then calls
`GetDOMProxyShadowsCheck()`. 0 A.D. registers neither, so both are null; 0 A.D.'s
own GUI proxies avoid that path on purpose (`JSInterface_GUIProxy.h`: "family
can't be nullptr because that's used for some DOM object and it crashes"). A
handler pointer that reads zeroed memory therefore produces exactly `RuntimeError:
null function` in that function. The object the IC sees is stale or corrupt; the
fault is earlier, not in the IC. Today's verification rerun did not reproduce it.

## Web deployment (`wasm/deploy/`)

Requested by the operator once the cushion worked: a landing page and a Docker
image to publish the build.

- `site/index.html`: landing page (English, text and CSS only, no artwork),
  stating that the port is unofficial; links to the port's repository
  (`github.com/MatiusRock1/0adwebassembly`), the original repository
  (`gitea.wildfiregames.com/0ad/0ad`) and play0ad.com; requirements (Chrome or
  Edge 137+ for WebGPU and JSPI), the measurements above and the licenses.
- `nginx.conf`: isolation headers on every response (needed for
  `SharedArrayBuffer`), the MIME types of `.wasm`/`.mjs`, compression only for
  text and `.wasm`, `Range` support for the archives, revalidation instead of
  long caching.
- `Dockerfile` (nginx 1.27 alpine), `prepare-context.py` (assembles the context
  with hard links, leaves out debug symbols), `smoke-test.py` (server checks plus
  a real Chrome run up to the original GUI), `README.md` (HTTPS requirement,
  proxy and CDN notes, license obligations).
- `application.mjs`: `?renderer=webgpu` preselects WebGPU (WebGL 2 stays the
  default); the landing page's Play button uses it.

Image `0ad-wasm-web` built from `application-phase4-5-cushion-1-web` (the measured
`cushion-1` with only that `application.mjs` change): 2.08 GB. Smoke test passed
against the running container: all server checks, `crossOriginIsolated`, WebGPU
preselected, the original GUI answering after 3.1 s, clean shutdown (code 0), no
page errors.

Before a public release: the repository must contain every change used for the
build (GPL), the third-party license texts (SpiderMonkey MPL-2.0, Emscripten
ports, ENet, libsodium, curl) should be added under `licenses/`, and the host
must serve HTTPS.
