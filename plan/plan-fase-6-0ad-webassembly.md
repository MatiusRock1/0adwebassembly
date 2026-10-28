# Phase 6: multiplayer and completion of remaining features

Status: pending. Depends on phase 5. Apply the [completion roadmap](plan-cierre-0ad-webassembly.md).

## Objective

Complete multiplayer and remaining platform differences without omitting them from the meaning of the complete game.

## Ordered work

1. Audit original transport, synchronization, lobby, authentication and discovery. Define compatibility: do not assume a browser can use native UDP/ENet directly. Specify and build a local adapter/gateway if needed, respecting original messages and commands. WebSocket/WebRTC are candidates to evaluate, not solutions approved by this plan.
2. Implement create/join from the GUI, handshake/versions, loading, readiness, turns and original chat. Handle limits, timeouts, disconnection/reconnection and desync diagnostics. The server/gateway will have configurable ports and clear startup/shutdown.
3. Test two and four real clients, native/browser if that compatibility is offered, with state hashes at checkpoints. Test 50/100/200 ms latency, jitter, loss where applicable and client failure. Verify that no order is applied twice and no divergence occurs.
4. Audit all features of the pin: online lobby, observer, multiplayer replays, mods, editor and development tools, accessibility, localization, screenshots and file/platform differences. Classify each one; implement mandatory features. An exclusion requires an explicit operator decision and prevents claiming full equivalence if it affects scope.
5. If the lobby requires an external service, prepare integration and local tests without publishing or using anyone else's credentials. Request specific instructions only when an external action is necessary; do not invent validation for untested services.

## Deliverables and acceptance

- [ ] Real multiplayer match through victory/defeat with 2 and 4 clients and zero desync, with compared states.
- [ ] Adverse connectivity, shutdown and resource tests; documented and verified reconnection policy.
- [ ] Native compatibility demonstrated if claimed; browser-only alternatives clearly identified and accepted for scope.
- [ ] Each client matches the original's FPS and smoothness under the same hardware and load, without hiding network wait as simulation lag.
- [ ] Complete feature matrix: no essential pending items; visible and reviewable decisions on differences.

A gateway without a verified match does not complete multiplayer. If an essential requirement cannot be completed, record the blocker and keep the overall delivery open.

## Common rules

Keep the original engine, scripts and assets from the phase 2 pin; any pin change needs a recorded baseline and migration. Preserve parity, RNG and commands; do not replace systems with mocks. Use only original art with named human authors and provenance. Keep platform changes isolated and reviewable. Local work is authorized; no commits, issues, PRs or automatic publication. Human review is required before submitting changes to the project.

Reuse Docker layers, with two jobs and 8 GiB as the initial build limits. Record logs and progress. Do not install dependencies when starting the game. New script and report names in this plan are proposed deliverables, not commands that are already available. A gate closes only with evidence; do not hide a blocker by reducing scope.
