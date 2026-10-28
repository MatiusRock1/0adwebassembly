# Phase 4: start of the application integration

Initial date: 2026-10-12. Update: 2026-10-13. Status: in progress; cycle of three matches and shutdown approved, full acceptance pending.
Pin kept: `40b8794eecb9618da69e10bacffa8814c561aa51`.

## Operator rescheduling - 2026-10-14

The pending functional and performance validation items move to [phase 4.5](../../plan/plan-fase-4-5-0ad-webassembly.md), where they will run after integrating WebGPU. They include controls, combat/capture/victory, research/trade parity, final audio/persistence/three-match regressions, full measurements and a 60-minute session. This decision allows the migration to start without first approving those gates; it does not vouch that they are met. Keep the WebGL evidence, including the failed performance results, as a baseline.

## Prerequisite and scope

The evidence `evidence/phase3/final-restart-release/acceptance.json` records
`passed: true`, three 900-second measurements after 120 of warmup,
about 60 displayed FPS, p95 of 27.79 ms and five ticks/s.
This enables starting phase 4; it does not vouch for the performance of a match with AI.

The original entry point was inventoried and a compilation probe was run against
the cached image `0ad-wasm-phase3:o3-lto-cached`, without network, two jobs and an
8 GiB limit. The probe does not change the cached source nor the regression
objects. Temporary objects are deleted when the container closes.

## Inventory of the entry point and migration

| Area | Original path | Needed integration |
|---|---|---|
| Entry | `source/main.cpp`: `main`, `RunGameOrAtlas` | Keep the early initialization and owners; adapt the loop to RAF without losing state or destruction |
| VFS/configuration | `ps/GameSetup/GameSetup.cpp`: `InitVfs`, `Init`; `Config.cpp`, `Paths.cpp` | Mount the original mods and user paths; separate content from persistent configuration |
| Window and renderer | `InitGraphics`, `ps/VideoMode.cpp` | SDL/WebGL, effective framebuffer resize, fullscreen by gesture and scale to 1080p |
| GUI | `gui/GUIManager.cpp`, `gui/Scripting/JSInterface_GUIManager.cpp` | Keep `page_pregame.xml`, scripts, bindings, fonts, hotkeys and session pages |
| Localization | `i18n/L10n.cpp` | Integrate tinygettext, ICU and the original catalogues in the WASM target |
| Match | `ps/Game.cpp`, `simulation2/system/LocalTurnManager.cpp` | Use the original CGame and turn manager for commands, loading, update and interpolation |
| AI | `simulation2/components/CCmpAIManager.cpp` | Integrate the original scripts and tasks, seeds and checkpoints; compiling does not prove execution |
| Frame | `main.cpp`: `Frame` | Keep progressive loading, events, GUI, CGame, audio and RenderFrame in their original order |
| End of match | `GameSetup.cpp`: `EndGame` | Destroy network/CGame, close the match audio and reset the renderer before returning to the menu |
| Shutdown | `ShutdownNetworkAndUI`, `ShutdownConfigAndSubsequent` | Keep the order of GUI, renderer, SDL, services, L10n, JS context, audio and VFS; verify workers |
| Audio | `soundmanager/SoundManager.cpp` | Currently CONFIG2_AUDIO=0; needs the original backend and decoding with unlocking by gesture |

The original loop keeps `VisualData` and the handlers alive during the match.
A conversion to callbacks must keep those owners until shutdown;
leaving the initialization scope before running callbacks would destroy them.
Do not replace `CGame::Update` with manual harness ticks: the native owner
includes pause, turn manager, commands and interpolation.

## Initial probe and verified blockers

Evidence: `evidence/phase4/entry-probe/report.json` and one log per unit.
The probe reuses the scene's defines and includes and includes its instrumentation
header. It neither links nor runs an application; audio stays off.
Result: eight of eleven units compile, including GUIManager, its bindings,
CGame, LocalTurnManager and CCmpAIManager. Three units fail with the diagnostics
given below. The syntax of the Python and PowerShell scripts was checked.

Initial blockers observed:

- `main.cpp`: collision between the original `CLogger` and the harness's reduced adapter.
- `GameSetup.cpp`: `curl/curl.h` is missing in the current closure.
- `L10n.cpp`: `tinygettext/dictionary.hpp` is missing; the compilation does not
  yet reach all the localization dependencies.

Units that compile do not vouch for GUI, AI or a functional game. Include failures
do not prove either that those libraries are incompatible with WASM.
The next work is to separate the original services from the headless adapters
and widen the dependency closure before the application link.
Do not add empty implementations to make the link pass.

The checkout shows many earlier deletions of original resources.
They are kept untouched. The full packaging must check the content of the
pin and its provenance; the scene's selected package is not enough for full GUI,
AI, maps and audio.

## Reproduction

From PowerShell, with Docker available and the existing cached image:

```powershell
.\wasm\scripts\docker-phase4-entry.ps1
```

A compilation failure produces a non-successful exit and persistent logs. This
command does not install dependencies, download an image nor start the game.

## Pending acceptance

### Resume and verified asynchronous shutdown: 2026-10-13

`evidence/phase4/visible-three-matches-recheck/report.json` passes three consecutive
visible matches at 1080p against Petra: menu, settings, loading, pause,
resume, defeat by resign, summary and return to the menu. The number of workers
is stable between matches. After shutdown, the SDK has no pthreads left and the
browser's last worker event takes about one more second to
disappear. The test waits for the asynchronous shutdown and confirms zero
application worker targets with Chromium's inventory. Audio closed, exit 0 and
zero engine errors. This resolves the observation failure of the earlier report.

The original native application with audio compiles and links in
`wasm/build/native-phase4`; it uses an isolated copy of the pin, a test mailbox
in the original GUI and the same prepared files. It does not replace simulation
components. `native-parity-numbered-mailbox/report.json` and
`full-game-parity-restart/report.json` pass the 10, 12 and 14 second checkpoints:
original full dump and GUI state identical between native and WASM.

`native-original-commands-visible-resources/report.json` and
`original-commands-parity/report.json` pass movement, gathering,
construction, production, diplomacy, rally point, garrison and unload.
The full dumps and GUI states match at 10, 70, 80 and 90 seconds.
The functional tests keep cheats disabled.

The operator observed a native crash during an earlier version of the mailbox.
The crashlog and dump were kept in `native-parity-dump-probe`. The current
protocol uses numbered requests, validates the read and a non-empty code, and
publishes a marker after closing the response. Later runs close with exit 0.
The exact cause of the initial exception is not proven.

One browser run stopped before the first frame; `live-inspection` and
`startup-worker-stack` were kept. The new repetition of the full test passed. The
cause of the stopped startup has still not been found.

Research and trade: the initial scenario sent two 300-wood markets with only 210
available; the engine rejected the constructions. The corrected test waits for
resources obtained through the original gathering. This correction of the test
does not change game costs or components.

The new browser link includes the VFS trace only if `traceVFS=1` is requested.
The launcher status was updated. The first short matches show about
50 draws/s, but do NOT vouch for presented FPS, a 200-entity load nor the
contract's full measurement windows.

### Pause requested by the operator: 2026-10-13

The operator asked to pause. The phase is not approved. Resume point:

- `evidence/phase4/visible-startup-close/report.json`: approved test of GUI,
  real WebGL 1920x1080 on NVIDIA, audio running and shutdown with the context
  closed, zero workers and zero engine errors.
- `evidence/phase4/visible-three-matches/report.json`: three consecutive matches
  against Petra from the menu, pause/resume, defeat by the original resign command,
  summary and return to the menu. Stable count of 14 workers between matches.
  The global report fails because Playwright counts one worker after shutdown;
  its URL, the SDK state and whether it is a late notification remain to diagnose.
- The GUI corruption, the change of the framebuffer to CSS dimensions and the
  original parallax shader are fixed. OpenAL is detached before destroying
  its context. These changes live in the isolated copy and the patch script.
- The last executed link includes these fixes. The optional VFS trace
  and the launcher status already compile, but need a new link/copy of the
  launcher before being used in tests. Do not confuse objects with the served binary.
- `wasm/build/native-phase4` was prepared with the original entry and the test
  mailbox, original resources and audio. The native compilation was interrupted by
  this pause; continue incrementally with MSBuild Release x64, two jobs.
- Missing: full system scenarios and native/WASM checkpoints, persistent audio
  settings and the contract's full performance measurements.
  Defeats by resign do not prove victory by combat nor economic progress.

The tests must be seen in the persistent Edge window. The verifiers
accept `--cdp http://127.0.0.1:9224` and leave the external browser open.
Do not use windows that disappear when the runner ends again. Application
port: `http://localhost:8091/application.html`. Reopen the server/Edge if
they are no longer active when resuming. No commits, PRs nor publication.

### Progress after the initial probe

The full closure contains 481 units compiled with audio, without the scene's
headless adapters. The strict link passes with the original GUI, CGame,
turn managers, AI, localization and managers. The blockers of the initial
probe were resolved with real dependencies and explicit platform services. The
fmt consteval fix keeps the format check: `fmt-check.json` tests a valid format
and the rejection of an incompatible format.

The original native packaging was recovered in batches after an external
interruption of the first process. The final public archive contains 38108 entries,
with no missing source entries; the distribution compression compares the hash
of each prepared resource. See `evidence/phase4/assets-report.json` and the
manifests of `wasm/dist/application-phase4`. No artistic resources were generated.

`evidence/phase4/startup-complete/report.json` vouches for the startup of the
original GUI and an OpenAL/Web Audio context running at 48000 Hz with 64 sources.
It does not vouch for acceptance: the screenshots show GUI geometry corruption,
and the 1920x1080 fullscreen canvas check fails. The GL backend's path for
temporary arrays is being adapted to upload them to WebGL buffers before
drawing. The compilation of this fix passes; its visual test is still
pending. The audio and worker shutdown have not been verified yet either.

Still pending: menu to victory/defeat with AI, system and parity scenarios,
audio by gesture and persistent settings, three matches with a clean shutdown,
and three full measurements at 1080p under a real load. The phase 3 scene remains
as a regression. Human review before submitting changes to the project.
