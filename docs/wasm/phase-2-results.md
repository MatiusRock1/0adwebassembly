# Phase 2: local interactive scene

Date: 2026-10-12 (America/Bogota).

The original scene works and the 900-second sustained session passed. The final focus and worker-shutdown check is recorded separately.

## Opening the result

Active server: **http://localhost:8080/scene.html**. It is also served from http://localhost:8080/.

Controls: arrow keys for the camera; Q/E or the wheel for zoom; click to select; right click to walk; Space to pause; N for one turn while paused; R to restart; Esc to close. The buttons offer the same actions. Switching tabs pauses; Space resumes.

The first load prepares the engine, scripts, models and textures. The loading status shows the stage. If the page was already open during the updates, reload it.

```powershell
# Build using the phase 1 images already prepared.
.\wasm\scripts\docker-phase2.ps1 -Scene
# Full acceptance: fixture, parity, 900-second scene and focus/shutdown.
.\wasm\scripts\docker-phase2.ps1 -Scene -Verify
# Serve the prepared package. It does not install dependencies at start.
.\wasm\scripts\serve-phase2.ps1 -Port 8080
# Or leave the server hidden in the background if the port is free.
.\wasm\scripts\serve-phase2.ps1 -Port 8080 -Background
```

## Evidence

| Check | Result |
|---|---|
| Original fixture | Ten cycles in Chromium 141.0.7390.37 and Firefox 142.0.1; parity and worker shutdown |
| Original map | CSimulation2, full registration, VFS and CMapReader; seven native/Node/Chromium/Firefox checkpoints equal |
| Restore | Identical bytes and hash; the same continuation after another original turn; exit code 0 |
| Visible image | Original terrain and models; screenshot during execution, 128 quantized colours and real RGB variation |
| Movement | Unit 8 selected by the original picking; original walk command; displacement observed |
| Controls | Camera, pause, one turn, 800x600 resolution and back to 640x480 |
| Restart | Three map reloads in the same module, keeping the loaded dependencies |
| Sustained session | 900 seconds, 60 samples, zero runtime errors and native exit code 0 |

The map is `maps/scenarios/pathfinding_terrain_demo`, seed 12345, with 37 initial entities. The final original hash of the 1100-tick reference is `d745fdb2637775d5495b66a9f6395d54`. The interactive test sends its own walk order and does not change positions from JavaScript.

Reports: `evidence/phase2/map-parity.json`, `restore/restore-result.json`, `chromium-scene-sustained-report.json`, `scene-sustained-summary.json` and `chromium-scene-focus-report.json`. The screenshot is `chromium-scene-canvas.png`. Earlier experiments are not the final acceptance evidence.

## Performance and limits

The tests use Chromium Linux/Docker, ANGLE SwiftShader, two CPUs and a 4 GiB limit. The RSS sum of the container's processes stayed roughly between 1.15 and 1.20 GiB; it includes the browser, the Playwright driver and Python, and may count shared pages more than once. The final stretch stabilized. The SDK logs show a WASM heap grown up to 288751616 bytes. The observed rendering is around two frames per second with a software GPU and a diagnostic build; it is not a measurement of the operator's Windows hardware.

The initial shutdown of the long run left a main-thread worker. An explicit termination of the pool through the pinned SDK's API was added, and shutdown is revalidated in the short test. It is not considered passed just because the program prints a PASSED marker.

The installed Windows browser could not be automated because of a URL policy not supported by Computer Use. The local URL lets the operator check it directly. Firefox passes the simulation and the fixture; its interactive renderer is outside the current graphical validation.

## Resources and changes

The resources come from the pin `40b8794eecb9618da69e10bacffa8814c561aa51`. The original native archive builder converts meshes, animations and textures. `asset-provenance.json` records 993 source files, hashes, Collada author metadata and human Git contributors. No new art was generated.

The original licences are in `evidence/phase2/licences/`. The art keeps its attribution to Wildfire Games and CC-BY-SA 3.0. The map's specific licence needs review before redistribution: the pinned LICENSE.md refers to a missing maps/LICENSE.txt. That uncertainty is recorded; no licence is invented. The scope of this delivery is local evaluation.

The adaptations can be reviewed in `evidence/phase2/scene/scene-platform.patch`: explicitly injected surface and input, terrain for water without the desktop CGame, WebGL 2 depth/sRGB, buffers through staging and BufferSubData, the original RGB fallback and compatible border sampling. In this scene the transparent margins use clamp-to-edge; general border-colour support is not claimed. Shadows, advanced water, post-processing, GPU skinning and silhouettes are reduced/disabled. The madvise warning is still visible. The VM implements neither page protection nor physical release on decommit; file watching is not supported for the immutable package.

This scene has no full menus, economy, combat, opposing AI, audio, saved games nor multiplayer. The tested restore belongs to the simulation state and does not vouch for full saved games. The Git index is kept; no commits, issues or PRs were created. Human review is required before submitting changes to the project.
