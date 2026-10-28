# Phase 5: official content, persistence and long sessions

Status: pending. Depends on approved phases 4 and [4.5: migration to WebGPU](plan-fase-4-5-0ad-webassembly.md). Apply the [completion contract](plan-cierre-0ad-webassembly.md).

## Objective

Complete the game's content and local features, preserve matches and stabilize performance/memory during long sessions.

## Ordered work

1. Create a complete inventory of the pinned official package: civilizations, scenario/skirmish/random maps, biomes, templates, actors, sounds, GUI and translations. Prepare caches with original tools and manifests with hashes, sizes, authors and licenses. Resolve the phase 2 map's license before redistribution; if unresolved, exclude it from the distributable package and use an original replacement with a clear license, keeping historical evidence.
2. Package content by dependencies and load it before synchronous VFS accesses. Separate core and content without dummy files; test cold/warm cache, interrupted downloads, incorrect checksums and progress. Do not require downloading everything on first startup.
3. Integrate the real saved-game format, metadata and browser persistence. Evaluate IndexedDB/OPFS through actual capabilities; handle quotas, transactions, versioning and import/export. Phase 2 serialization does not satisfy this item.
4. Implement save/load from the GUI, tab closure and later reopening; compare checkpoints and continuation. Validate original replays and persistent configuration; protect files against incomplete writes.
5. Complete supported original water, shadows, particles, postprocessing, silhouettes, animations and graphics options. Each reduction needs a recorded difference and decision; offer configurable quality without removing match logic or content.
6. Test map families and every civilization with automated loading and representative matches. Exercise random generation, late game, high populations, GC, context loss, suspension and restoration. Resolve madvise/VM according to the actual contract; do not silence warnings without analysis.

## Deliverables and acceptance

- [ ] Official content inventory without missing dependencies; reviewable coverage and provenance/license matrix.
- [ ] Ten save/load cycles, browser reopening and identical continuation; quotas or storage errors do not corrupt the last valid match.
- [ ] Replays and settings work; explicit save compatibility policy.
- [ ] 60-minute session and five matches/restarts without unexplained memory growth; documented heap and resource limits.
- [ ] Suite of 2/4 players, combat and late game matches the original's FPS and smoothness under equivalent conditions; all internal resolutions and reductions declared.

Document actual population/map limits and required hardware. If the required workloads do not reach the original's performance, fix the bottleneck or revisit the architecture; do not close this phase using averages from an empty scene.

## Common rules

Keep the original engine, scripts and assets from the phase 2 pin; any pin change needs a recorded baseline and migration. Preserve parity, RNG and commands; do not replace systems with mocks. Use only original art with named human authors and provenance. Keep platform changes isolated and reviewable. Local work is authorized; no commits, issues, PRs or automatic publication. Human review is required before submitting changes to the project.

Reuse Docker layers, with two jobs and 8 GiB as the initial build limits. Record logs and progress. Do not install dependencies when starting the game. New script and report names in this plan are proposed deliverables, not commands that are already available. A gate closes only with evidence; do not hide a blocker by reducing scope.
