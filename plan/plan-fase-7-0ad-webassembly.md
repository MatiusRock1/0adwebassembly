# Phase 7: local delivery and overall completion

Status: pending. Depends on approved phases 3, 4, [4.5](plan-fase-4-5-0ad-webassembly.md), 5 and 6. This is the only phase that declares full completion.

## Objective

Deliver the game from a local port with fullscreen, agreed content and features, and demonstrated performance of at least 30 sustained FPS at 1080p in the contract scenarios; matching the original remains the optimization target.

## Ordered work

1. Create a reproducible build and release package with versions, hashes, licenses, attributions and separate symbols. Install/test in a clean folder. Record exact prerequisites, size and cold/warm startup times; do not require a toolchain to play an already built package.
2. Prepare a single local launcher that serves the package and starts the gateway if applicable. Proposed default web port: 8080; detect if occupied and allow configuration. Show URL and errors, COOP/COEP headers, WASM MIME type, same origin and process shutdown. External publication is outside this authorization.
3. Flow from URL -> original menu -> fullscreen action -> match -> save -> exit -> return -> load -> victory/defeat. Repeat on the operator's Windows, Chromium/Edge and a second available engine. Record incompatible capabilities; advertised platforms must pass.
4. Repeat the full functional, determinism and content suite and FPS/smoothness comparison with the original using the exact release in fullscreen. Three repetitions per workload and version, a 60-minute session and multiplayer. Keep raw evidence and a summary; no software GPU to establish the real machine's target.
5. Deliver a brief guide to usage, controls, quality settings, saving, multiplayer, troubleshooting and hardware limits. Obtain human review of changes and the matrix; do not create commits, PRs or publish.

## Mandatory final checklist

- [ ] Full local and multiplayer match with GUI, economy, combat, AI, audio and victory conditions.
- [ ] Agreed official content, persistent saves, replays and options verified.
- [ ] Real fullscreen with safe exit, correct resize/DPR/input and tested recovery.
- [ ] FPS and smoothness equivalent to the original at 1080p, contract percentiles and workloads passed on identified hardware under equivalent conditions.
- [ ] Parity preserved and simulation at the correct speed; stable memory and workers.
- [ ] Launcher, URL/port and package verified from a clean installation.
- [ ] Licenses/provenance resolved for redistribution if requested; no generated art.
- [ ] Functional matrix without essential blockers or results presented as verified without testing.
- [ ] Final report links evidence, existing commands, versions, limits and human review.

The final report must explicitly state whether the overall objective was achieved. A URL that loads, a screenshot or 60 FPS in a menu does not establish completion. If any gate is missing, identify it and keep the status pending; do not create another phase to hide incomplete work.

## Common rules

Keep the original engine, scripts and assets from the phase 2 pin; any pin change needs a recorded baseline and migration. Preserve parity, RNG and commands; do not replace systems with mocks. Use only original art with named human authors and provenance. Keep platform changes isolated and reviewable. Local work is authorized; no commits, issues, PRs or automatic publication. Human review is required before submitting changes to the project.

Reuse Docker layers, with two jobs and 8 GiB as the initial build limits. Record logs and progress. Do not install dependencies when starting the game. New script and report names in this plan are proposed deliverables, not commands that are already available. A gate closes only with evidence; do not hide a blocker by reducing scope.
