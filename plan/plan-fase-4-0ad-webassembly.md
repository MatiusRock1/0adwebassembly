# Phase 4: full local match with GUI and audio

Status: WebGL integration with partial evidence. Operator update of 2026-10-14: remaining functional validation, final regressions and performance acceptance moved to phase 4.5, after WebGPU integration. See [phase 4 results](../docs/wasm/phase-4-results.md). This move does not establish full original acceptance.

## Rescheduling pending work — 2026-10-14

At the operator's request, pending validation and performance work moves to [phase 4.5](plan-fase-4-5-0ad-webassembly.md), to run **after integrating the WebGPU migration**. It no longer blocks the start of that migration. This move changes phase 4's completion scope; it does not approve pending tests or turn failed results into passes.

| Moved pending item | Execution in phase 4.5 |
|---|---|
| Selection, groups, camera, minimap, rally points and mouse/keyboard orders | Functional validation after migration |
| Combat, building capture, ownership changes and victory | Full scenarios after migration |
| Research and trade: comparison with the native game | Native/WebGPU checkpoints and commands; keep available WebGL evidence |
| Audio, persistence and three consecutive matches regression | Final visible tests with WebGPU |
| Skirmish and combat performance, native comparison and no simulation lag | Three 900-second repetitions per workload, after 120 seconds of warmup |
| Long-term stability | 60-minute session with the migrated backend |

Keep the WebGL build, manifests and evidence, including performance failures. The original gates below remain as a record of evidence and initial scope: those still pending will be accepted in phase 4.5. Administrative closure of phase 4 must distinguish the completed integration from this deferred acceptance.

## Objective

Enter a skirmish against AI from the original menus and finish it with victory or defeat in fullscreen, with the original game behavior.

## Ordered work

1. Inventory the native entry point and migrate from the harness to the real application flow: initialization, CGame, turn managers, configuration, VFS, services and destruction. The scene remains a regression test, not a substitute for the full executable.
2. Integrate the original GUI, fonts, localization, menus, options, map/civilization selection, loading and HUD. Keep scripts/bindings; avoid recreating the interface as an alternative page. Support keyboard, mouse, hotkeys, multiple selection, groups, minimap, rally points and contextual commands.
3. Enable players, diplomacy, fog/LOS, economy, gathering, construction, production, research, trade, garrisons and combat through original components and scripts. Verify relevant effects and animations.
4. Integrate the AI manager, scripts and their jobs/threads; test original random generation with fixed seeds. Compare matches and commands against native; locate divergences by tick before expanding.
5. Adapt original audio to the browser: backend, decoding and loading, music and effects, volume/mute. Unlock audio from a user gesture, pause/resume and close devices correctly; keep original authors/licenses.
6. Connect pause, defeat/victory, summary and return to menu; start a new match without leaks. Continuously measure and optimize full matches.

## Deliverables and acceptance

- [ ] Match from menu to victory/defeat with original opponent AI and usable GUI in fullscreen 1080p.
- [ ] Scenarios testing all systems above, including combat, ownership changes and victory conditions; matching original commands and native/WASM checkpoints.
- [ ] Gesture-enabled audio, persistent settings and no missing-resource errors.
- [x] Three consecutive matches, pause, fullscreen, return to menu and shutdown without abandoned workers: `visible-three-matches-recheck/report.json`.
- [ ] Manifest skirmish and combat workloads sustain at least 30 FPS at 1080p; matching the original remains the optimization target on the same machines and conditions, under the contract; no growing simulation lag.

Do not declare the complete game here: general content, save/replay and multiplayer still have gates to close.

After closing this phase, continue with [phase 4.5: migration to WebGPU](plan-fase-4-5-0ad-webassembly.md) before phase 5. Keep the WebGL build and its evidence as the migration baseline.

## Common rules

Keep the original engine, scripts and assets from the phase 2 pin; any pin change needs a recorded baseline and migration. Preserve parity, RNG and commands; do not replace systems with mocks. Use only original art with named human authors and provenance. Keep platform changes isolated and reviewable. Local work is authorized; no commits, issues, PRs or automatic publication. Human review is required before submitting changes to the project.

Reuse Docker layers, with two jobs and 8 GiB as the initial build limits. Record logs and progress. Do not install dependencies when starting the game. New script and report names in this plan are proposed deliverables, not commands that are already available. A gate closes only with evidence; do not hide a blocker by reducing scope.
