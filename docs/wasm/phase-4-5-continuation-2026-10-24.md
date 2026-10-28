# Phase 4.5 — continuation of 24 October

Continued on [25 October](phase-4-5-continuation-2026-10-25.md) (pacing fix,
asynchronous audio, turn cushion, web deployment).

The phase is still open. Operator priority: performance.

## How to resume (state at the end of 24 October)

Read this section first; the rest of the document is the record that backs it.

### Operator goals for the next session

- Web build capped at 30 FPS, always (`WASM_FRAME_RATE_CAP`, see below).
- Cut the slow simulation turns by ~20–35 %, cut the number of pauses
  substantially, raise the average. No workload change, no sim/render decoupling.
- Short decision runs: one parity, a 30 s + 60 s verification run and one ABBA of
  four 60 s + 60 s captures (about 40 minutes per decision).

### Current best candidate

`sim-kernels-3-30` (package
`wasm/dist/application-phase4-5-sim-kernels-3-30`), built on `gate-memo-3` with the
30 FPS cap, all simulation kernels and the Petra `createObstructionMap` kernel.
Parity `sim-kernels-3-30-parity-1` passed. Reference with the same cap:
`gate-memo-3-30`. Results in "Results with the 30 FPS cap" below: turns over
100 ms −67 %, turns over 60 ms −45 %, pauses −18 %.

### Decisions waiting for the operator

1. Acceptance criterion under the 30 FPS cap. The written gates require a mean of
   ≥ 30 FPS and ≥ 30 engine FPS, which a hard 30 cap essentially cannot meet (one
   late frame puts the mean below 30). Proposed: mean ≥ 29.5 FPS and physical
   p95 ≤ 2 refreshes. Not changed; it is the operator's call.

### Next steps, in order

1. Fix the 30 FPS pacing (see "Pacing problem of the first 30 FPS cap"). Today's
   cap paces on fixed slots, so a late turn frame is followed by a 16.7 ms frame
   and 4-refresh gaps; p95 is 66.8 ms. Design for the fix is in that section.
2. Re-run the verification run of `sim-kernels-verify-3` (it crashed at game start
   with the intermittent VM crash, so the in-engine kernel counts for the second
   round are still missing). See "Commands".
3. Investigate the intermittent `GetPropIRGenerator::tryAttachStub` crash. It
   predates all kernels (18 October) and is a direct risk for the 3 × 900 s
   battery. Plan in its section.
4. Next turn-cost targets from the per-function timing: `CanAttack` (6.1 ms per
   slow turn, 2.2 ms per normal turn), UnitAI state switches
   (`SwitchToNextState`, 4.6 / 2.1 ms), unit creation (`createunits` 5.6 ms,
   `VisualActor.OnCreate` 4.9 ms), and render CPU (~59 % of the engine thread).
5. Only then the long acceptance battery; ask the operator how much time they
   have before starting it (~1 h 45 min of captures).

### Commands

PowerShell, from the repository root; Docker image `0ad-wasm-phase4-5:shaders`,
with the same mounts as the earlier build batches. `V` is a variant name, `N` a
repetition number and `OUT` an evidence directory.

```text
# Unit rebuild on a base candidate (inside the Docker runner)
wasm/scripts/phase4-5-turn-gate-build.py --base gate-memo-3 --variant V     --unit UNIT... [--header HEADER] --define NAME=VALUE...
#   30 FPS clock:  --recorded-unit main.cpp --harness-header application-clock.h
#   kernels:       --unit simulation2/Simulation2.cpp
#                  --unit simulation2/components/CCmpAIManager.cpp
#                  --unit scriptinterface/ModuleLoader.cpp
#                  --header scriptinterface/ModuleSourceKernels.h
#                  --define WASM_SIM_KERNELS=1 --define WASM_AI_MODULE_KERNELS=1
#   verification:  --diagnostic --define WASM_SIM_KERNEL_VERIFY=1
#                  --define WASM_AI_KERNEL_VERIFY=1

# Link (inside the Docker runner) and package
wasm/scripts/phase4-link.py --build /phase45-build/application-V     --output /phase45-build/linked-V --release --exception-mode wasm --jspi     --spidermonkey-library /phase45-build/spidermonkey-portable-switch-o3-runscript-timer/libjs_static.a
wasm/scripts/phase4-5-package.py --linked-directory wasm/build/phase4-5/linked-V     --target-directory wasm/dist/application-phase4-5-V

# Parity
wasm/scripts/verify-phase4-5-ai-parity.py --package wasm/dist/application-phase4-5-V     --output docs/wasm/evidence/phase4-5/V-parity-N

# Verification run (report fields simKernelStats and aiKernelStats; mismatches must be 0)
wasm/scripts/profile-phase4-5.py --workload combat --settle-seconds 30 --seconds 60     --webgpu-directory wasm/dist/application-phase4-5-sim-kernels-verify-3     --replenish-while-sampling --output docs/wasm/evidence/phase4-5/sim-kernels-verify-combat-3b

# Capture (run A/B in ABBA order)
wasm/scripts/benchmark-phase4-5-standalone.py --backends webgpu --workloads combat     --repetitions 1 --warmup-seconds 60 --duration-seconds 60     --webgpu-directory wasm/dist/application-phase4-5-V --output OUT
wasm/scripts/analyze-presentation.py --output OUT/presentation-two-refresh.json     OUT/webgpu-combat-1.json

# Kernel equivalence tests (node, no build needed); --fill-header after changing
# a hashed original or adding a placeholder
node wasm/scripts/test-sim-kernels.cjs REPO_ROOT
node wasm/scripts/test-obstruction-kernel.cjs REPO_ROOT
```

### Not committed

All changes of this session are in the working tree for the
operator to review (AGENTS.md: agents do not create commits).

## Environment

- Measurement scripts run with `wasm/.venv-phase3/Scripts/python.exe`. With the
  system `python` Playwright is missing and the run fails before measuring
  (`performance-render-replay-60hz-combat-reinforce10-0-wrong-python`, does not
  count).
- About 10,900 files deleted from the working tree
  (`binaries/data/mods/public/art`, `audio`, `maps` and others) were restored with
  `git restore`. The deletion was not intended.
- The workspace JavaScript files have CRLF line endings; the packaged `public.zip`
  has LF. Anything that hashes original sources must hash the LF text.

## Local cache between tests

Operator question: whether local model storage is invalidated before each test.
Each launcher opens Chrome with a `*-profile-<PID>` profile. FPS captures record
`initialArchiveWork`: in `performance-render-replay-60hz-1` and
`performance-render-replay-60hz-combat-reinforce10-1`, `persistentHits` is 0 and the
26 blocks (25.4 MB) come over the network. Those measurements started with an
empty cache.

Risk found: profile folders were not deleted (there were 126). If Windows reuses
a PID, the profile would inherit another build's IndexedDB. Now
`benchmark-phase4-5-standalone.py`, `profile-phase4-5.py` (parity too) and
`verify-phase4-5-standalone.py` delete the profile before opening Chrome.

## Combat load below 200 units

Cause: the script checked the minimum every 30 s, before reinforcing. With the
simulation at a rate of ~1.0, 30 s of combat kill ~100 units (306 → 190). In
earlier captures the rate was lower (~17 s of game per 30 real seconds) and it
went unnoticed. The manifest's `reinforcementSeconds` was not read anywhere.

Operator decision: reinforce every 10 s in combat (skirmish stays at 30 s).
`phase4-workloads.json` sets `combat.reinforcementSeconds = 10`; it is read by
`benchmark-phase4.py`, `benchmark-native-phase4.py` and `profile-phase4-5.py`.
The 200 minimum does not change. The manifest SHA-256 changes.

`performance-render-replay-60hz-combat-reinforce10-1` (60 s + 60 s,
`render-replay-1`): 243–276 units, rate 0.99985, no backlog, zero errors.

## Combat performance

| Combat 60 s + 60 s | render-replay-1 | kernel-args-1 |
|---|---:|---:|
| Physical FPS | 35.75 | 36.02 |
| Physical p95, ms | 66.73 | 66.78 |
| Physical p99, ms | 183.29 | 150.18 |
| 1 % low, FPS | 3.98 | 4.22 |
| Pauses >100 ms | 68 | 65 |
| Engine FPS / p95 | 37.02 / 67.22 | 36.51 / 68.50 |
| Units | 243–276 | 227–296 |

Skirmish with `render-replay-1` gave 50.10 FPS and 11 pauses. Combat is far from
the goal.

Side finding: in skirmish, 6 of the 8 engine frames over 100 ms fall within
400 ms of a script observation or reinforcement (maximum Update 558 ms). In
combat it is 10 of 60. It is part of the protocol, the same on web and native.
Not changed.

### Combat CPU profile

`cpu-profile-combat-render-replay-1` (60 s settle + 30 s, diagnostic). The engine
thread is ~100 % busy:

- Render ~17.5 s: `PrepareSubmissions` 5.9, `ModelRenderer::Render` 5.7 (2.8 self)
  and unit `RenderSubmit` 5.6.
- Turn 7.9 s: `BroadcastMessage` 4.9, `FlushTurn` 1.9 (Petra and script
  commands), `FlushDestroyedComponents` 0.9.
- `CCmpVisualActor::SetVariant` → `CUnit::ReloadObject` 1.4 s: actor reloads on
  variant changes in combat.
- 1.42 s waiting for the AI result (`CAIWorkerClient::DeferredResult`) in 31 of
  169 turns. AI computation has spikes: median 27.8 ms, p90 112.8 ms, maximum
  259.8 ms. With the deferred capture it has ~150 ms per turn.

Applying the AI commands later is not an option: it would change the semantics.

### AI JS sampling

`phase4-5-deferred-capture-build.py` now accepts `--guest-profile` (adds
`WASM_AI_GUEST_PROFILE`, marks `diagnosticOnly`) and `--variant`. Diagnostic
package `application-phase4-5-ai-deferred-capture-guest-1`: link identical to
`deferred-capture-2` except object paths.

- Without kernels (`ai-guest-profile-combat-1`): ~87 % in `common-api/map-module.js`.
- With kernels (`ai-guest-profile-combat-kernels-1`): 705 interrupts. ~31 % in the
  JS wrapper of `addInfluence` (`AIMapKernels.h`, entry, `Number.isInteger` and
  `[...].every(...)`).

### Candidate 3: native validation for `addInfluence`

The JS wrapper only checks `this.set`/`this.runLoop` and passes the values
unconverted. `CAIWorker::AIMapAddInfluence` receives `JS::HandleValue` and makes
the former checks in C++: `isNumber()` (equivalent to `typeof`), integer `width`
and `height`, `width*height === length`. If they do not hold, the original JS
function runs. Same kernel and same order of operations.

Build `application-ai-deferred-capture-3`, package
`application-phase4-5-ai-kernel-args-1` (same browser modules as
`render-replay-1`). Parity `ai-kernel-args-parity-1` passed: hashes `e35b3f94…`
(10 s) and `b218d9a3…` (30 s) in both modes.

The cooperative sampling (`ai-guest-profile-combat-kernel-args-1`, 808 interrupts)
cannot measure the change: it charges code without checkpoints to the function
entry. The CPU profile can:

| Combat, 30 s profile | render-replay-1 | kernel-args-1 |
|---|---:|---:|
| Total AI | 8.09 s | 6.04 s |
| AI median / p90 | 27.8 / 112.8 ms | 17.8 / 70.3 ms |
| Waits for the AI | 31 turns, 1.43 s | 13 turns, 0.68 s |
| Turn p90 / p95 | 88.4 / 110.2 ms | 68.1 / 85.4 ms |
| Render | 17.5 s | 18.4 s |

One run each; combat varies between runs. The AI improvement does not show in
FPS (table above): the engine thread is still saturated by rendering. Needs human
review before being submitted to the project.

## Clock cost on the engine thread

In wasm every clock read is a call to `performance.now()` in JS. In
`cpu-profile-combat-kernel-args-1` the clock takes 7.4 % of the engine thread
(2.33 s of 31.4): SpiderMonkey `js::RunScript` 1.05 s, classic profiler 0.66 s,
`Profiler2` 0.33 s. On the AI worker it is negligible.

### Candidate 4: `RunScript` without the clock

SM128 calls `TimeStamp::Now()` twice on every top-level C++→JS call, only for
`realm()->timers.executionTime`, which nothing reads (single writer and no reader
in SM128). `isExecuting` is used only by Ion, absent from the portable build.
`wasm/scripts/phase4-5-runscript-timer-build.py` replaces only `Interpreter.o` in
the `portable-switch-o3` archive: it keeps the flags and removes the clock reads
and the sum. Archive membership verified.
`phase4-5-deferred-capture-build.py --spidermonkey-library` repeats the dependency
audit on the new archive.

Package `application-phase4-5-runscript-timer-1`; parity `runscript-timer-parity-1`
passed. Clock on the engine thread: 7.4 % → 4.6 %.

### Candidate 5: cached `performance.timeOrigin`

With pthreads, Emscripten 4.0.10's `emscripten_get_now` is
`performance.timeOrigin + performance.now()`. The origin is constant per global
(page or worker). `wasm/browser/application-time-origin.js` reads it once per
global; returned values are identical. Option `--cached-time-origin`. Package
`application-phase4-5-time-origin-1`; parity `time-origin-parity-1` passed. Clock:
4.6 % → 3.0 %.

## Engine at `-O3`

The 483 engine units were compiled at `-O2` (the link's `-O3` only affects
Binaryen). `wasm/scripts/phase4-5-reoptimize-build.py` repeats each unit's recorded
command changing only the level and the output; no fast-math.
`application-phase4-5-engine-o3-1` (candidate 5 at `-O3`): parity
`engine-o3-parity-1` passed with the original hashes in both modes; wasm
14.68 → 14.82 MB.

| Combat 60 s + 60 s | render-replay-1 | time-origin-1 | engine-o3-1 |
|---|---:|---:|---:|
| Physical FPS | 35.75 | 38.14 | 39.45 |
| Physical p95, ms | 66.73 | 66.73 | 50.11 |
| Physical p99, ms | 183.29 | 150.24 | 137.18 |
| 1 % low, FPS | 3.98 | 4.26 | 4.46 |
| Pauses >100 ms | 68 | 62 | 52 |
| Engine FPS / p95 | 37.02 / 67.22 | 38.51 / 63.25 | 40.00 / 56.82 |

Short captures, all with an empty persistent cache at the start. 30 s CPU profiles
vary too much between combats to attribute per function.

Repeat `performance-engine-o3-60hz-combat-2` (same binary): 37.50 FPS, p95
50.21 ms, p99 166.88 ms, 59 pauses. The 3-refresh p95 repeats; FPS varies by ±1–2
between runs, so FPS differences under ~5 % cannot be attributed with 60 s
captures.

### 16-entry asynchronous queue (not adopted)

`WASM_WEBGPU_ASYNC_CALLS` (default 6, unchanged) and `--async-calls` in the
deferred-capture build. `application-phase4-5-queue16-o3-1` (engine-o3 + 16-entry
queue; only `Device.cpp` changes): 38.12 FPS, p95 66.70 ms, 65 pauses. The worker
waits for work ~18 ms per frame with both 6 and 16 entries: it is not the
bottleneck; the engine thread is. No AI parity (renderer-only change).

## Other combat observations

- Frame split (`performance-time-origin-60hz-combat-1`): 451 frames without a turn
  take 20–40 ms because rendering exceeds 16.7 ms (median 25 ms).
- Renderer: ~8,900 draws and ~5.3 MB uploaded per frame; ~4.5 calls to the
  asynchronous queue per frame with a limit of 6. `CommandQueue::Reclaim` blocks
  the engine 45 times in 30 s, median 17.6 ms, maximum 30.2 ms.
- OpenAL: sounds triggered by animations are forwarded synchronously to the main
  thread (423 waits, 0.91 s, maximum 14.2 ms). The earlier `audio-worker`
  experiment only covered music and ambient sound.

## Pauses caused by the measurement script

In `performance-engine-o3-60hz-combat-1/2`, 35 of 44 and 36 of 47 pauses ≥100 ms
fall within the observation/reinforcement window (in skirmish, 6 of 8). The full
observation asks `GetEntityState` for ~300 entities on the engine thread
(90–190 ms, 2–3 times per maintenance). In addition, `createunits` with
`parameter=200` refilled up to the population cap at once (≥75 units in one turn)
and `attack-walk` was re-sent to every unit.

Protocol v3 (`phase4-workloads.json` version 3, the same for web and native):

- Samples use `classCounts.Unit` from `GetSimulationState`. Setup checks that it
  matches the UnitAI count of the full observation (153/153 in the first run); if
  it does not, it fails.
- Reinforce the deficit up to `replenishToUnitsPerPlayer` (150 at first, then 125;
  see below) and send the original order (`attack-walk`, `allowCapture: false`)
  only to the new entities. Those already fighting keep their order.
- Combat: `reinforcementSeconds` 5. The 200 minimum does not change.
- The full observation remains only in setup and at the measurement boundaries.

`profile-phase4-5.py --replenish-while-sampling` keeps reinforcing during CDP
sampling.

| `-O3`, combat 60 s + 60 s | protocol v2 (#1 / #2) | protocol v3 |
|---|---:|---:|
| Units in samples | 226–296 / 229–270 | 270–291 |
| Physical FPS | 39.45 / 37.50 | 39.30 |
| Physical p95, ms | 50.11 / 50.21 | 50.13 |
| Physical p99, ms | 137.18 / 166.88 | 100.16 |
| Pauses >100 ms | 52 / 59 | 44 |

Skirmish `performance-engine-o3-harness3-skirmish-1` (60 s + 120 s, valid):
50.35 FPS, p95 33.40 ms, engine p95 33.36 ms, p99 50.06 ms, 1 % low 13.79 FPS,
5 pauses in 120 s (before: 11 in 60 s). `presentationGate30` and
`presentationGateTwoRefresh` pass. A single capture; not acceptance.

## Pauses left in combat: Petra spikes

With protocol v3, the 25 engine pauses (≥100 ms) of the combat capture are all
slow turns; none is GC.

- 90 s without reinforcement during sampling
  (`cpu-profile-combat-o3-harness3-90s-1`): 477 turns, maximum 206 ms. In turns
  ≥150 ms: 85.5 ms waiting for Petra's result and 43.3 ms executing its orders.
- 90 s with reinforcement (`cpu-profile-combat-o3-harness3-90s-replenish-1`): turns
  of 261 and 745 ms, with ~420 ms of waiting for Petra on average. On the AI worker,
  27 computations ≥150 ms (max. 445 ms), almost all interpreted JS; GC ~5 ms.

`AIGuestProfiler.h` (diagnostic only) now records 6-frame stacks and separates
computations ≥150 ms. `ai-stack-profile-combat-90s-1`: 36 slow computations (mean
217 ms, 36 % of AI time) against 442 normal ones (32 ms). The slow ones are
dominated by:

- building placement (`queueplanBuilding.start` → `findGoodPosition`,
  `createObstructionMap`, `getNonObstructedTile`, `findStrategicCCLocation`,
  `findEconomicCCLocation`);
- defence (`defenseManager.update` → `assignDefenders`, `defenseArmy.assignUnit`);
- events and metadata (`checkEvents` → `setMetadata` → `updateEntityCollections`);
- territory (`updateTerritories`, `getOwnerIndex`).

These are Petra's periodic plannings, which cost 200–450 ms in the interpreter
without a JIT.

## Exact kernels for Petra

Operator decision: exact kernels (do not run Petra on another JS engine).
Everything stays compiled in the same `.wasm` and runs in the browser.

- `InfoMap.findBestTile` (with `getNonObstructedTile`/`isObstructedTile` inlined)
  → `CAIWorker::AIMapBestTile`. Reproduces the `obstruction.pattern` side effect.
- `EntityCollection.addEnt`: if the map is already strictly sorted by numeric id
  (key === `e.id()`), insert at its position instead of re-sorting everything.
  Same order as the original stable sort; otherwise the original.
- `Headquarters.updateTerritories` → `CAIWorker::AIMapUpdateTerritories`: border
  masks in C++ and an ordered list of the base calls that have an effect, which
  the JS runs in the same order. Owner table obtained by probing `getOwnerIndex`
  (with its source checked); `Math.round` offsets computed in JS. Installed after
  loading the Petra module, without evaluating modules before their original
  order.

Each kernel falls back to the original JS if any precondition changes (types,
sizes, replaced methods). Diagnostic mode `--kernel-verify`
(`WASM_AI_KERNEL_VERIFY`): also runs the original and throws if they differ.
`kernel-verify-addent-combat-1`: 2,639 checks without differences;
`kernel-verify-territories-combat-1` and `-4-recheck` (threaded) without
differences; `kernel-verify-5-sync-debug-1`: 13 `findBestTile`, 763 `addEnt`, 33
`updateTerritories`, all equal.

Unexplained and pending: `kernel-verify-5` (diagnostic only) hung twice in
threaded combat after start (`kernel-verify-territories-combat-2/-3`); variant 4,
which differs only in counters, passes. It does not affect the candidate, which
does not include the verification mode, but it is not understood.

Candidate `application-phase4-5-petra-kernels-1` (the three kernels, `-O3`):
parity `petra-kernels-parity-1` passed in both modes.

`replenishToUnitsPerPlayer` was lowered from 150 to 125 (`targetUnitsPerPlayer`
declared): with 150 there were ~300 constant units and the simulation dropped to
0.981–0.983 (`performance-*-combat-120s-1`, the reference invalid by rate).

| Combat 60 s + 120 s, 125/side | engine-o3-1 | petra-kernels-1 |
|---|---:|---:|
| Units in samples | 220–276 | 220–274 |
| Physical FPS | 41.62 | 43.72 |
| Physical p95, ms | 50.06 | 50.04 |
| Physical p99, ms | 100.11 | 83.42 |
| 1 % low, FPS | 4.85 | 6.29 |
| Pauses >100 ms | 57 | 36 |
| Engine FPS / p95 | 42.42 / 47.04 | 44.49 / 45.29 |
| Rate | 0.9926 | 0.9959 |

## AI turn gate (`WASM_AI_TURN_GATE`, first version not adopted)

Standard technique of not blocking rendering while waiting for the simulation
(0 A.D. already does it for network lag). The turn manager does not start a turn
until the AI result it consumes is computed, and keeps rendering meanwhile.
Turns, commands and order do not change. Files, all under
`#if defined(WASM_AI_TURN_GATE)`:

- `source/simulation2/helpers/AITurnGate.h` (new)
- `AIDeferredStart.h` (`IsPending`)
- `CCmpAIManager.cpp` (`PublishReadiness`)
- `system/TurnManager.cpp`

`wasm/scripts/phase4-5-turn-gate-build.py` recompiles only those two units on top
of `ai-deferred-capture-9-o3`. Package `application-phase4-5-turn-gate-1`; parity
`turn-gate-parity-1` passed with the original hashes in both modes.

| Combat 60 s + 120 s | petra-kernels-1 (-2) | petra-kernels-1 (-3) | turn-gate-1 |
|---|---:|---:|---:|
| Physical FPS | 43.72 | 44.81 | 43.61 |
| Physical p99, ms | 83.42 | 83.43 | 83.46 |
| 1 % low, FPS | 6.29 | 6.47 | 8.73 |
| Pauses >100 ms | 36 | 40 | 43 |
| Maximum `CGame::Update` in a turn, ms | — | 1,297 | 240 |
| Rate | 0.9959 | 0.9955 | 0.9827 |

Finding: in `frames[]`, `tick` is the turn.

- **Origin of the pauses:** 39 of 40 frames over 100 ms (43 of 44 with the gate)
  follow a frame with a turn. That frame's `CGame::Update` has a median of ~30 ms
  and p95 72–79 ms. Without a turn, the median is 1.5 ms.
- **Effect of the gate:** removes the extreme wait for the AI, but not the pauses.
  The cost is the turn itself.
- **Correlation with reinforcement:** 2 to 3 s after each harness maintenance
  (`createunits` + `attack-walk`) there are 18–25 turns over 60 ms, against 4–8 in
  the other 1 s intervals.

Hang in `cpu-profile-combat-turn-gate-90s-1`: at the end of the 60 s settle, the
engine did not answer the GUI probe (30 s), and shutdown waited another 60 s.
Cause not established. It may be the gate, the intermittent hang already seen in
`kernel-verify-5`, or the frame loop no longer receiving `requestAnimationFrame`
(window hidden or covered).

External research:

- weval/AOT of the portable interpreter: 2.77× on average on Octane according to
  its author. Still in beta and designed for WASI/Wizer, not for Emscripten with
  pthreads and JSPI.
- `-sGROWABLE_ARRAYBUFFERS` (avoids the pthreads + memory growth cost when
  accessing from JS) does not exist in Emscripten 4.0.10.

## Turn cost in combat and exact variation cache (`WASM_UNIT_VARIATION_CACHE`)

`cpu-profile-combat-petra-kernels-90s-1` has 521 turns and 16 reinforcement turns
(identified by `CComponentManager::AddEntity` ≥ 8 ms). Within 0–0.5 s after
reinforcement, 17 of 55 turns exceed 60 ms without counting the AI wait. There
`FlushTurn` adds +21 ms (processing commands in JS, `SetOwner` from JS, global
messages). Inclusive, over turn time:

- Interpreted JS (PBL): 65.6 %
- `CUnit::ReloadObject`: 15.6 %, of which `CalculateRandomRemainingSelections` is
  11.6 % (almost all of it constructing and seeding `std::mt19937`)
- `CCmpOwnership::SetOwner`: 12.1 %

Simulation JS profile (`sim-guest-profile-combat-90s-1`, diagnostic build
`sim-guest-profile-1`): the cooperative sample lands on the first JS entry after a
stretch of C++. `Sound.GetSoundGroup` collects 13.5 % of the samples, but in the
real CPU profile it is 0.7 % of the turn. It cannot measure time per JS function.

Cache: every animation or variant change calls `FindObjectVariation(actor,
selections, seed)`, which redraws the whole variation. For a `CUnit` the actor and
the seed are fixed, so the result depends only on the selections while the object
manager's state does not change. Files, all under
`#if defined(WASM_UNIT_VARIATION_CACHE)`:

- `source/graphics/Unit.cpp`: up to 8 memoized results per unit, in a separate
  table so that `CUnit`'s layout does not change.
- `source/graphics/ObjectManager.cpp/.h`: generation counter incremented on
  unload, hot reload, quality or diversity changes, and when outdated actors or
  objects are replaced.

Build: `phase4-5-turn-gate-build.py --unit graphics/Unit.cpp --unit
graphics/ObjectManager.cpp --header graphics/ObjectManager.h --define
WASM_UNIT_VARIATION_CACHE=1`. It reapplies phase 2's `SCENE_*` traces to
`ObjectManager.cpp`; against the frozen copy there are only added lines.

- Verification (`variation-verify-1`, diagnostic only, compares each hit with the
  original lookup): `variation-verify-combat-1`, 34,553 hits checked, 0
  differences, 76 % hit rate.
- Parity `variation-memo-parity-1` passed with the original hashes in both modes
  (`CUnit` is visual only; parity does not cover it, verification does).

| CPU profile 90 s with reinforcement | petra-kernels-1 | variation-memo-1 |
|---|---:|---:|
| `CUnit::ReloadObject` | 3,550 ms (15.6 %) | 619 ms (3.8 %) |
| Turn without AI wait, ms/turn | 37.8 | 29.9 |

120 s physical captures of the same binary `variation-memo-1`: 27 and 52 pauses
(turn median 27.7 and 33.6 ms). Variation between runs dominates single captures,
so the physical comparison is an alternating A/B, 3 per build
(`performance-ab-<build>-combat-120s-1..3`):

| Combat 60 s + 120 s, alternating A/B | petra-kernels-1 (1/2/3) | variation-memo-1 (1/2/3) |
|---|---|---|
| Pauses >100 ms | 45 / 45 / 45 | 29 / 47 / 44* |
| Physical FPS | 43.74 / 41.28 / 42.33 | 43.84 / 41.80 / 41.71* |
| 1 % low, FPS | 5.72 / 5.07 / 5.06 | 6.46 / 5.00 / 4.55* |
| Turn median, ms | 29.5 / 29.9 / 31.4 | 28.0 / 28.7 / 27.3 |
| Turn p95, ms | 84.3 / 78.4 / 86.9 | 70.8 / 72.4 / 79.0 |
| Turns >60 ms | 69 / 64 / 65 | 41 / 50 / 46 |
| Turns >100 ms | 19 / 16 / 21 | 17 / 17 / 15 |
| Rate | 0.9929 / 0.9891 / 0.9903 | 0.9964 / 0.9881 / 0.9864 |

\* Capture 3 incomplete: the engine's last frame arrived 274 ms before the end of
the window (`engineDrawWindowComplete` false). The other metrics cover 119.7 s.

Result:

- The cache lowers the turn cost consistently: median −7 %, p95 −11 % and −30 %
  of turns over 60 ms.
- Pauses over 100 ms drop little (45 → 40 on average, with a lot of spread). They
  come from the peak turns: reinforcement and AI wait.
- The average FPS does not change.

## Where the pauses come from with the cache (`variation-memo-1`)

Engine thread split (`cpu-profile-combat-variation-memo-90s-1`, 93 s):

- Render: 59 %. `EnumerateObjects` 19.5 s (up to 4 passes per frame: scene,
  shadow, reflection, refraction), `PrepareSubmissions` 19.7 s,
  `RenderSubmissions` 10.5 s.
- Simulation turn: 17.5 %.
- Deferred AI capture after `Present`: 7.6 % (~14 ms per turn with the profiler).
  It is `__captureAIWorkerSnapshot` in JS plus the clone.

In the three A/B captures, every frame over 100 ms but one follows a frame with a
turn whose `Update` exceeded 40–70 ms; the rest of the frame adds ~30 ms.

AI JS profile (`ai-guest-profile-combat-memo-1`, 120 s): only 8 computations of
≥150 ms (336 ms on average), against 627 of 33 ms. The slow ones come from
`setMetadata` → collections, `findStrategic/EconomicCCLocation`,
`createObstructionMap` and `assignDefenders`.

The simulation JS profile stays biased even when samples served with more than
200 µs of delay are discarded (`AI_GUEST_MAX_DELAY_US`): C++ and JS alternate in
shorter stretches. It was replaced by exact dispatch timing, diagnostic only
(`WASM_SIM_SCRIPT_TIMING`, `source/simulation2/helpers/SimTiming.h`). It measures
exclusive time per component type and handler (in `CComponentManager`), per
command type (in `FlushTurn`) and the AI wait. `sim-timing-combat-memo-1`: 32 turns
of ≥70 ms (102 ms on average without the wait) against 592 of 29 ms.

| Row, ms per turn | slow | normal |
|---|---:|---:|
| AI wait (outside the turn, inside the frame) | 25.2 | 2.7 |
| `Timer.OnUpdate` (all timers) | 14.4 | 9.9 |
| `ModifiersManager.OnGlobalOwnershipChanged` (~1 ms per created unit) | 9.9 | 0.2 |
| `AIInterface.OnTemplateModification` (~17 ms per researched technology) | 8.4 | 0.1 |
| `VisualActor.OnCreate` (~0.8 ms per created unit) | 7.7 | 0.4 |
| `cheat.createunits` (harness reinforcement) | 7.3 | 0.0 |
| `AIInterface.OnGlobalValueModification` | 7.0 | 0.1 |
| Petra `attack` commands | 6.0 | 0.5 |
| `UnitMotionManager` | 3.5 | 3.7 |

Inside the turn, the JS VM is ~50 % of self time (the interpreter loop ~29 %) and
C++ ~47 %, widely spread. The spikes have concrete causes:

- the wait for the AI;
- unit creation: reinforcement and training, ~3.5 ms per unit adding up handlers;
- technology research: templates and the `ValueModification` cascade.

## Turn gate on top of the cache (`gate-memo-1`)

`variation-memo-1` plus `WASM_AI_TURN_GATE` (CCmpAIManager.cpp and
TurnManager.cpp). Parity `gate-memo-parity-1` passed with the original hashes in
both modes. Alternating A/B `performance-ab2-*`:

| Combat 60 s + 120 s | variation-memo-1 (1/2/3) | gate-memo-1 (1/2/3) |
|---|---|---|
| Pauses >100 ms | 22 / 29 / 28 | 13 / 15 / 13 |
| 1 % low, FPS | 7.28 / 7.42 / 6.17 | 11.50 / 11.25 / 10.97 |
| Physical FPS | 45.49 / 46.05 / 45.00 | 47.41 / 47.71 / 44.57 |
| Physical p95, ms | 33.52 / 33.70 / 33.45 | 33.46 / 33.43 / 50.01 |
| `presentationGateTwoRefresh` | yes / no / yes | yes / yes / no |
| Turns >100 ms | 16 / 18 / 18 | 7 / 8 / 9 |
| Rate | 0.9951 / 0.9973 / 0.9931 | 0.9889 / 0.9841 / **0.9779** |

- **First 120 s combat captures that pass the 2-refresh criterion:** four of six.
  They are at the limit (33.43–33.52 against 33.54 ms), so it is not robust.
- **The gate halves the pauses**, but lowers the simulation rate. Capture 3 falls
  outside the tolerance (0.978 < 0.98) and the bench marks it invalid
  (`withinTolerance` false; it is not a hang).
- **Cause of the rate:** when the AI finished during a held frame, the turn waited
  for the next refresh (about 10 ms on average), and the AI sets the pace.
- **Fix (`gate-memo-2`):** `AITurnGate::held` and an early exit in
  `WasmApplication::DisplayClock::Wait()` (`wasm/harness/application-clock.h`).
  While a turn is held, the wait polls the gate every 1 ms and starts the frame as
  soon as it opens. It is consumed once per hold, so a paused game returns to the
  vsync pace. `main.cpp` is recompiled from its recorded source
  (`--recorded-unit`) with the private harness header (`--harness-header`).

Result of `gate-memo-2`: parity `gate-memo-2-parity-1` passed; A/B
`performance-ab3-*`.

| Combat 60 s + 120 s | variation-memo-1 (1/2/3) | gate-memo-2 (1/2/3) |
|---|---|---|
| Pauses >100 ms | 27 / 22 / 29 | 10 / 15 / 17 |
| 1 % low, FPS | 6.65 / 6.93 / 5.15 | 12.15 / 11.04 / 10.27 |
| Physical FPS | 45.15 / 44.70 / 43.11 | 48.23 / 44.21 / 45.05 |
| Physical p95, ms | 50.00 / 49.99 / 50.02 | 33.42 / 50.03 / 50.04 |
| Rate | 0.9946 / 0.9950 / 0.9902 | 0.9890 / **0.9767** / 0.9822 |

The early exit does not fix the rate, so the cause was not the alignment with the
refresh:

- **How the rate is lost:** not gradually. There are holds of up to 1.8 s and
  stretches of ~25 s at 0.88–0.92: phases in which Petra takes longer than a turn.
- **It is not CPU contention on the AI:** the AI thread is busy only 17 % of the
  time (`cpu-profile-combat-variation-memo-90s-1`, `cpu-14`) and the allocator
  lock is negligible.
- **Gaps between turns:** both versions have a similar number of gaps over 400 ms,
  but with the gate they add up to more (3.4–6.5 s against 2.2–4.9 s).
- **Hypothesis:** rendering during a long wait slows the AI computation.
- **Next candidate (`gate-memo-3`):** hold at most 100 ms
  (`WASM_AI_TURN_GATE_MAX_HOLD_MS`). After that, the turn waits at the barrier as
  without the gate.

## Gate with a 100 ms limit (`gate-memo-3`)

Parity `gate-memo-3-parity-1` passed. A/B `performance-ab4-*`, with `gate-memo-3`
first in each pair:

| Combat 60 s + 120 s | gate-memo-3 (1/2/3) | variation-memo-1 (1/2/3) |
|---|---|---|
| Pauses >100 ms | 17 / 19 / 14 | 33 / 23 / 28 |
| 1 % low, FPS | 5.99 / 8.91 / 8.96 | 5.72 / 9.09 / 5.49 |
| Physical FPS | 43.73 / 45.89 / 44.95 | 43.81 / 47.02 / 43.08 |
| Physical p95, ms | 49.99 / 45.39 / 50.02 | 50.01 / 33.48 / 50.02 |
| Rate | 0.9889 / 0.9965 / 0.9981 | 0.9920 / 0.9994 / 0.9897 |

The limit brings the rate back into tolerance and keeps the reduction in pauses.
With the gate, the AI wait in normal turns drops from 4.3 to 1.1 ms
(`sim-timing-combat-kernels-1`); in slow turns it stays at 17.6 ms (holds over
100 ms). Provisional base for what follows. **Caveat:** see the position effect
below; this table does not correct for it.

## Per-timer split (`sim-timing-memo-2`)

Timing with `TimerPatch` splits `Timer.OnUpdate`. In normal turns (30.6 ms on
average): `Attack.Attack` 5.0 ms (~0.46 ms per hit), `UnitAI.TimerHandler` 2.6 ms,
`Timer.OnUpdate` itself 2.5 ms. In slow turns Petra's `attack` commands also stand
out (9.6 ms, ~0.38 ms each).

## Exact simulation kernels (`WASM_SIM_KERNELS`)

`source/simulation2/helpers/SimKernels.h`, installed in `Simulation2.cpp` after the
scripts are loaded and in the AI context (`CCmpAIManager.cpp`) after the global
scripts. Each kernel is installed only if the FNV-1a hash of the source of every
original it replaces or inlines matches:

- `MatchesClassList`: same tests in the same order; each string is split once
  (tables bounded at 4096 entries). Also on the AI worker.
- `ModifiersManager.OnGlobalOwnershipChanged`: deletes the entity's cache instead
  of replacing it by an empty `Map` (`cachedValues` is not serialized and is only
  read with `get`), and stops evaluating a property's modifiers once one applies.
- `AIInterface.OnTemplateModification` / `OnGlobalValueModification`: template
  index per component and memoized base values. A loaded template always returns
  the same frozen object (`CParamNode` caches its JS value and the loader never
  evicts); failed loads are not memoized.

`WASM_SIM_KERNEL_VERIFY` (diagnostic) also runs the original, keeps its result and
counts differences (`Phase45SimKernelStats`, `simKernelStats` in the profile
report). Node test against the original scripts: 300,000 `MatchesClassList` cases
and 60 random worlds × 400 operations identical in kernel and verification mode.

**First attempt (`sim-kernels-1`) not installed** (`installed: 0`): the hashes were
computed on the CRLF workspace and the packaged `public.zip` has LF (identical
after normalization). Fixed in `sim-kernels-2`.

`sim-kernels-2` (kernels in the simulation and in the AI context):

- Verification in combat (`sim-kernels-verify-combat-2`, 60 s + 120 s):
  `installed: 15`, `aiInstalled: 1`; checked 362,254 `MatchesClassList` calls,
  3,046 ownership changes, 91 template modifications and 3,821 value
  modifications, **0 differences**.
- Parity: `sim-kernels-2-parity-1` **failed** in sync mode with `memory access out
  of bounds` inside `evaluateOriginalGUI` (the verifier's call), after producing
  the 10 s checkpoint; no native stack. The repeats `sim-kernels-2-parity-2` and
  `-3` passed with the original hashes. `sim-kernels-dense-1-parity-1` (same
  kernels plus the compact snapshot) passed. Similar out-of-bounds crashes already
  appeared before these kernels (see 23 October); see "Intermittent crash" below.

A/B `performance-ab7-*` (ABBA ABBA order, no FPS cap). Capture 1 of
`sim-kernels-2` is invalid (`validFullscreen1080pRun` false: the window lost
fullscreen during the measurement) and is excluded. Means of 3 against 4:

| Combat 60 s + 120 s | gate-memo-3 | sim-kernels-2 |
|---|---:|---:|
| Pauses >100 ms | 20.0 | 18.3 |
| Turn median, ms | 29.1 | 26.3 |
| Turn p90, ms | 48.8 | 45.8 |
| Turns >60 ms | 34.2 | 29.3 |
| Turns >100 ms | 14.8 | 11.3 |
| Physical FPS | 44.48 | 46.19 |
| Rate | 0.9945 | 0.9926 |

Consistent turn improvement (−10 % median, −24 % of turns over 100 ms) and a modest
one in pauses (−8 %). The FPS difference is within the noise between binaries.

## Position effect in the A/B

Since `sim-kernels-1` installed nothing, `performance-ab5-*` was in practice an A/A
test (`sim-kernels-1` first in each pair):

| Combat 60 s + 120 s | first (1/2/3) | second (1/2/3) |
|---|---|---|
| Pauses >100 ms | 20 / 15 / 19 | 22 / 19 / 21 |
| Physical FPS | 47.56 / 46.92 / 46.05 | 44.47 / 44.21 / 43.79 |
| Physical p95, ms | 33.42 / 33.42 / 33.49 | 49.99 / 50.00 / 50.02 |
| `presentationGateTwoRefresh` | yes / yes / yes | no / no / no |
| Rate | 0.9974 / 0.9915 / 0.9937 | 0.9850 / 0.9844 / 0.9823 |

In `ab5` the first of each pair comes out better all three times, but in `ab` and
`ab4` the order has no systematic effect. `Update` is the same (turn median
26–29 ms in both). The difference is outside the simulation: in frames without a
turn the mean interval is 21.4 ms against 22.6 ms (median 16.67 in both), stable
over the three captures. Two binaries with the same logic (only the compilation of
`Simulation2.cpp` changes) differ by ~6 % in FPS. The most likely cause is code
layout; it is not proven. Consequences:

- Differences of ~3 FPS between builds do not prove an improvement.
- Pauses and turn times are the reliable metrics for simulation changes.
- From `ab6` on the order is ABBA ABBA, to also rule out the order.

## Focus agreed with the operator (24 October, evening)

Target of 30 FPS and three concrete improvements: cut the slow simulation turns by
20–35 %, cut the number of pauses substantially and raise the average. The
benchmark load does not change and the sim/render decoupling is not attempted.
(I had said that zero pauses over 100 ms in combat is unlikely without decoupling
the simulation from rendering.)

**30 FPS cap in the web version** (operator decision, "sí o sí"):
`WASM_FRAME_RATE_CAP` (30 by default) in `wasm/harness/application-clock.h`. The
`requestAnimationFrame` signal advances its deadline by 1000/30 ms per frame,
without drift, independently of `adaptivefps`. The AI gate's early exit from the
frame wait is removed: it would add frames between two slots. **Consequence for
acceptance:** the written criteria require a mean of ≥ 30 FPS and ≥ 30 engine FPS;
with an exact cap of 30 the mean never exceeds 30.0 and any late frame puts it
below. Changing the criterion is the operator's decision; it has not been touched.

## Per-function split (`sim-timing-combat-kernels-3`)

Diagnostic build with `fn:` rows per function (`SimTiming::FunctionPatch`,
wrappers that pass `this`, arguments, result and exceptions through) and a list of
the worst turns (`worstSinceStart`, ≥ 250 ms including waits). Slow turns (42,
107.5 ms with the measurement overhead): `ApplyModifiers` 7.6 ms (1,414 calls),
`MatchesClassList` 6.4 (846), `CanAttack` 6.1, `FetchModifiedProperty` 5.0,
`createunits` 5.6, `VisualActor.OnCreate` 4.9, `SwitchToNextState` 4.6,
`GetTechModifiedProperty` 3.4. The `AIInterface` kernels bring their rows down
from ~9 and 7 ms to 2.6 and 2.0. Worst turns: the initial creation ones (3, 4, 10)
and a first death (turn 222, `HandleDeath` 336 ms) fall in the warmup; turn 628
(499 ms) is an AI wait (459 ms) and matches the fixed spike at tick 629 in the
captures. In this build the `InvalidateCache` wrapper made the ownership kernel
fall back to the original; fixed (guards on the instance's own properties).

Classifying the long frames of `performance-ab5-*`: every engine interval over
100 ms but one per run follows a turn frame whose `Update` was ≥ 60 ms. Unit
creation accounts for ~48 of the 108 ms of a slow turn: ~29 ms of per-unit
handlers, ~11 ms of the `ValueModification` messages it posts, ~7.6 ms of
`createunits` itself. GC inside turns is negligible (29 ms of nursery collections
in 90 s); first-time archive reads in turns add up to 112 ms in 90 s.

## Second round of exact kernels

In `SimKernels.h`, with hashes of every original function they replace or inline
(including the `MultiKeyMap` methods):

- `GetTechModifiedProperty` with `DoesModificationApply` inlined (also on the AI).
- Versions per (property, secondary key) and per secondary key, incremented in
  `ModifiersChanged`, per storage object.
- `ApplyModifiers`: the player-wide part is reused across entities with the same
  class list while the version of that list holds; results that issued a warning
  are not reused. Precondition, which every producer in the mod meets:
  modifications are not mutated after being added.
- `OnGlobalOwnershipChanged`: list of applying properties per (owner, classes),
  reused while the owner's version holds.
- `Timer.OnUpdate`: a (time, id) heap instead of visiting every timer; the same ids
  in the same order; the run loop is the original's.

In `AIMapKernels.h` and `scriptinterface/ModuleSourceKernels.h`
(`WASM_AI_MODULE_KERNELS`): native kernel of the territory loop of Petra's
`createObstructionMap`. The guard is inserted on the loop's line only if the
module's hash matches (`0xeba24c7d`); the wrapper validates types, builds the ally
table with `isPlayerMutualAlly` (hash checked) and, if anything does not fit, lets
the original loop run.

Node tests with the packaged scripts (`wasm/scripts/test-sim-kernels.cjs`,
`wasm/scripts/test-obstruction-kernel.cjs`): the earlier cases, 60 stress worlds
with shared templates × 1,500 operations, 80 worlds × 400 timer turns (with
callbacks that schedule, cancel, change the repeat time, throw or lose their
target, and replacement of the `Map`), and 6,000 `createObstructionMap` cases (real
guard, real wrapper, JS mirror of the C++ kernel), all identical. Known difference:
the error text of a timer callback that throws names the kernel in its stack.

## Results with the 30 FPS cap (`performance-ab8-*`)

`gate-memo-3-30` (base + cap) against `sim-kernels-3-30` (all kernels + cap), ABBA
order, 60 s + 60 s, all four captures valid. Means of 2 against 2:

| Combat 60 s + 60 s | gate-memo-3-30 | sim-kernels-3-30 | change |
|---|---:|---:|---:|
| Turns >100 ms | 7.5 | 2.5 | −67 % |
| Turns >60 ms | 16.5 | 9.0 | −45 % |
| Pauses >100 ms | 20.0 | 16.5 | −18 % |
| 1 % low, FPS | 6.83 | 8.60 | +26 % |
| Physical FPS | 28.63 | 28.86 | (cap 30) |
| Physical p95, ms | 66.77 | 66.79 | = |
| Turn median, ms | 25.3 | 25.5 | = |
| Rate | 0.9996 | 0.9990 | |

The second-round kernels cut the slow turns sharply. The pacing, however, is worse
than without the cap; see the next section.

## Pacing problem of the first 30 FPS cap

Displayed intervals (PresentMon `MsBetweenDisplayChange`, in refreshes):

| Interval | capped (`ab8`) | uncapped (`ab7`) |
|---|---:|---:|
| 1 refresh (16.7 ms) | 28 % | 72 % |
| 2 refreshes (33.3 ms) | 50 % | 19 % |
| 3 refreshes | 11 % | 4 % |
| 4 or more | ~10 % | ~2 % |

Cause: the cap signals on fixed 33.3 ms slots. A turn frame (~25 ms of turn +
~13 ms of render ≈ 38 ms) misses its slot; the next slot's signal is already
pending, so the next frame starts at once and is shown one refresh later, and
frames fall into 4-refresh gaps. At 30 FPS one frame in six carries a turn, so
~17 % of the frames are late and p95 is 66.8 ms.

Design for the fix (not implemented):

- Count display signals (one per vsync, still throttled to ≤ 60 Hz) instead of
  signalling only on 30 FPS slots.
- Record the signal count when the frame is presented: a small header
  `source/renderer/backend/webgpu/PresentPacing.h` with atomics, written in
  `Device.cpp` `Present()`. The wait cannot use its own entry time, because the
  deferred AI capture runs after `Present`.
- A light frame starts on the second signal after the previous present, so frames
  are shown every 2 refreshes.
- A frame that will run a turn starts right after the previous frame, in the idle
  time the cap leaves, so its ~38 ms finish in time for its refresh. Predict it
  from `CTurnManager::Update`'s logic: a turn runs when `m_DeltaSimTime` plus the
  frame length reaches 0 (after the clamp to 2 turn lengths), and `AITurnGate`
  does not hold it. That needs a read-only accessor for `m_DeltaSimTime`. To make
  the turn run in that early frame, `WasmApplication::FrameTime` gets the slot
  time instead of the actual start, so the time accounting stays exact over
  frames.
- Expected result: turn frames up to ~35 ms of work keep the 2-refresh cadence;
  heavier ones show once for 3 refreshes (50 ms), never 1 + 4. For p95 ≤ 2
  refreshes about 70 % of turn frames must fit, i.e. a turn p70 of ~22 ms with
  the current ~13 ms render.
- Alternative: let the render worker present each frame on its 2-refresh vsync
  with one frame of queue (engine runs one frame ahead). More robust, but adds
  ~33 ms of latency.

## Intermittent crash in `GetPropIRGenerator::tryAttachStub` (open)

`sim-kernels-3-30-parity-1` passed. The verification run
`sim-kernels-verify-combat-3` (build with `WASM_SIM_KERNEL_VERIFY` and
`WASM_AI_KERNEL_VERIFY`) crashed at game start with `RuntimeError: null function`.
Resolved stack: `GetProxyStubType` ← `GetPropIRGenerator::tryAttachStub` ←
`TryAttachStub` ← `DoGetPropFallback` ← `PortableBaselineInterpret` … ←
`js::array_sort` (a comparator).

- The same chain as the out-of-bounds crash in `ai-map-kernels-4-parity-1`
  (23 October) and in `performance-direct-upload-diagnostic-1` (18 October,
  skirmish). The latter predates the Petra map kernels (22 October), so neither
  those nor today's kernels cause it. It goes back further: on 17 October combat
  with the portable O3 VM failed with the same `RuntimeError: null function` in
  `array_sort` (`combat-portable-o3-functional-stress-1/decoded-worker-error.json`,
  see `phase-4-5-pause-2026-10-17.md`); the D224659 backport adopted then did not
  fix it.
- An object that the IC treats as a proxy has a null handler: corrupted memory or
  a freed or moved object.
- Ruled out by reading the code: late writes from the browser into freed wasm
  memory. The WebGPU synchronous calls, the idle and readback signals and the
  archive reads all store the result before `ready` and the C++ side waits
  without a timeout.
- Most likely: a GC-rooting bug in SpiderMonkey 128's portable baseline
  interpreter (experimental in 128; the VM is 128.13.0 with two backported
  Mozilla patches, D224656 and D224659, and no own IC changes). A pointer to an
  object moved by a nursery collection would fit both symptoms.
- Next: reproduce more often with a SpiderMonkey build with assertions or
  `JS_GC_ZEAL` (generational verification), and try disabling generational GC as
  a diagnostic. It is a direct risk for the 3 × 900 s battery.

## Pending

1. 30 FPS pacing fix (design above).
2. Verification run of `sim-kernels-verify-3` (in-engine counts for the second
   round of kernels).
3. Intermittent VM crash (above).
4. Turn cost: `CanAttack`, UnitAI state switches, unit creation
   (`createunits`, `VisualActor.OnCreate`, first-time archive reads in
   `BuildVariation`), Petra's remaining spikes (`setMetadata` →
   `updateEntityCollections`, `findStrategic/EconomicCCLocation`,
   `getNonObstructedTile`, `defenseManager.assignDefenders`). Petra's
   `updateResourceMaps` rebuilds every resource map when any entity dies
   (`this.resources` holds every entity id); a rebuild cannot be skipped exactly
   (it refreshes moving resources and the 8-bit maps clamp), only made cheaper.
5. Render CPU on the engine thread (~59 %): `ModelRenderer::Render` self time,
   `CModel::GetWorldBoundsRec` per pass, WebGPU `AppendData` /
   `AppendGeneratedUpload`.
6. The compact AI snapshot (`WASM_AI_DENSE_SNAPSHOT`, `sim-kernels-dense-1`, parity
   passed) has not been measured with the kernels.
7. Explain the hang of `cpu-profile-combat-turn-gate-90s-1` and the
   `kernel-verify-5` hangs.
8. Long battery only when combat is close to the goal; skirmish has to be repeated
   on the final build.
