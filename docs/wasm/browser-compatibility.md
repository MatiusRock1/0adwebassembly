# Browsers: phase 2

| Environment | Fixture, ten cycles | Map, seven checkpoints | WebGL 2 backend | Interactive scene |
|---|---|---|---|---|
| Chromium 141.0.7390.37, Linux/Docker | Passes | Exact parity | Passes, SwiftShader | Pending |
| Firefox 142.0.1, Linux/Docker | Passes | Exact parity | Pending | Pending |
| Installed browsers, Windows | Pending | Pending | Pending | Pending |

Required: localhost HTTP, COOP/COEP, crossOriginIsolated, SharedArrayBuffer and WebAssembly. This binary has no fallback without threads.

Fixture: each instance uses a new iframe; when it is removed Chromium confirms zero dedicated workers through CDP. Map: exit code zero and seven serialization SHA-256 matching native; a heartbeat is also recorded. The pthread pool does not limit the engine's additional workers.

The tests use a pre-prepared Playwright, with the external network disabled. Reports, versions, headers and screenshots are in docs/wasm/evidence/phase2. The WebGL test uses a software GPU and does not vouch for the operator's hardware.

Computer Use on Windows does not support the environment's URL policy. No attempt was made to get around that restriction; the Windows check remains pending.
