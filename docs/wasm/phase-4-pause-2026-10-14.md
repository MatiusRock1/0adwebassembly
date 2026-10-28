# Phase 4: pause requested on 2026-10-14

The operator asked to pause in order to attend classes. The active performance test was stopped and any phase 4 PresentMon capture of its own was asked to finish. Do not continue the tests until the operator resumes.

## Resume point

- The visible desktop window confirmed WebGL on an NVIDIA GeForce RTX 3060 Laptop GPU.
- The first load preparation failed: the original `cheat/createunits` command requires the `player` field. It was added in `wasm/scripts/phase4_workload.py`. This command is used exclusively to prepare the benchmark load, not to vouch for functional systems.
- The short repetition `performance-preflight/skirmish-funded.json` was interrupted; do not use it to close any gate. The full measurements are still missing.
- The observed desktop has a screen larger than 1080p. The fullscreen check now requires covering the real screen and keeping the internal 1920x1080 render; the scale is declared on the page. Element-only fullscreen or an isolated canvas size is not accepted.
- The tests target the open browser through `Phase4VisibleBrowser.exe`, CDP port 9226. The fullscreen button requires a real click through Computer Use after the test prints `WAITING_FOR_VISIBLE_FULLSCREEN_BUTTON`.
- Avoid opening additional Playwright sessions during a measurement: they can change the focus emulation. Use the test process's data and watch the desktop with Computer Use.
- When pausing, the CDP 9226 connection no longer answered. The final state of the match was not checked; check the browser and the server when resuming.

Keep the pending items: input, combat/capture/victory, research/trade parity in WASM, regressions and the full performance contract. Phase 4 stays open; phase 4.5 remains only planned.
