# Original renderer: phase 2

WebGL 2 backend and original renderer initialized and run in Chromium Linux/Docker with ANGLE SwiftShader. The full interactive scene is still pending.

The context belongs to the application: Emscripten creates WebGL 2 and proxies it to the browser thread; the original backend receives an external context, a path also used by Atlas. The framebuffer is presented explicitly. SDL manages the window and events.

Adaptations isolated in the build copy:

- Remove GL self-aliases that hid the GLAD macros.
- Exclude desktop-only queries and accept GLES core framebuffers.
- Inject Input::Manager and dimensions into CRenderer, keeping its native constructor.
- Take the renderer's dimensions in SilhouetteRenderer.
- Use sized depth formats for WebGL 2: D16, D24 and D32F with the matching pixel types. The values that the GLES 2 loader does not declare come from the [official Khronos GLES 3 registry](https://github.com/KhronosGroup/OpenGL-Registry/blob/main/api/GLES3/gl3.h).

The map test connects the original CTerrain, CUnitManager, CSimulation2, CMapReader, CObjectManager, LOS/territory/minimap textures and CSceneRenderer. It does not draw stand-ins for terrain or units. Real terrain and model geometry is required before the result is accepted.

Resources are converted with the native archive builder: cached PMD/PSA/DDS. The browser does not run the Collada converter nor NVTT. Scripts and shaders keep their original sources.

The finite test passed with 5152 terrain triangles and 6998 model triangles. The persistent loop, original controls and restart already compile and are being verified. Still missing: the persistent loop, controls, sustained memory and the fifteen-minute validation. The errors of earlier experiments are kept as historical diagnostics, not as successful results.
