# What the web needs

What a recomp's code and RT64 need to run as a page: WebGPU and the shaders, prebuilt shader lists, building with
Emscripten, and mods. Read it before porting a game or changing a fork; the README's Using it in a recomp has the steps
a port takes, `docs/game-forks.md` what each port found, and `docs/findings.md` the measurements.

## WebGPU and the shaders

Shaders go HLSL → SPIR-V (dxc, without `-fvk-invert-y`: WebGPU's clip space is D3D's) → WGSL (naga
`--keep-coordinate-space`, `cargo install naga-cli`); spec constants become `override`s and push constants a uniform
buffer at `@group(3) @binding(999)`. `node tests/wgsl_check.mjs <dir>` checks every `.wgsl` against core WebGPU in
headless Chrome. CI's `wgsl` job does it on SwiftShader (`CHROME_FLAGS` in the checker), which has no dual-source
blending, so the 6 `*DualSource` variants are validated by naga only there. plume's examples and
`plume_webgpu_checks.html` (each piece RT64 needs, read back, PASS or FAIL in the console) build with
`emcmake cmake -S <rt64>/src/contrib/plume -B <dir> -DPLUME_BUILD_EXAMPLES=ON
-DPLUME_DXC_EXECUTABLE=<rt64>/src/contrib/dxc/bin/x64/dxc.exe -DPLUME_NAGA_EXECUTABLE=<naga>`.

Read docs/findings.md (WebGPU in Chrome and Firefox) before changing plume's backend or how RT64 builds pipelines or
presents on the web.

- WebGPU checks a storage texture's format and access against every binding a shader declares, and a render pass's
  usage against every bound set: a texture can't be sampled and drawn into by one pass, and a pass samples its own
  depth target only read-only. So each decal RT64 draws reading the depth after a draw that wrote it ends the pass and
  begins another; Firefox's GPU process pays 25-70 us a pass and Chrome's ~7, so a game that does it often costs
  Firefox far more a present (rt64 0560318).
- Two web paths run natively on Vulkan too, to check them against the stock ones: configure a game with
  `-DRT64_PER_DRAW_TEXTURES=ON` (rt64-0007: a texture set per draw, TMEM in one buffer; to test that pool, make
  `TMEMHasher::requiresRawTMEM` return true) or `-DRT64_PACKED_RSP_INPUTS=ON` (rt64-0009).
- Still to do: no `rgba16unorm` (HDR) target on the web, and MSAA is off: WebGPU has no sample positions.

## Prebuilt shader lists

Without one a page is unplayable (docs/findings.md, WebGPU in Chrome and Firefox), so every web port records a list and
builds it: a game's `rt64_shaders.txt` (its header says what was played and what not) is specialized at build time
(`RT64_PREBUILT_SHADER_LIST`, rt64 0034023), in every browser and on every adapter (rt64 bfe07cb).

- In sections (rt64 657c222): `section <name>` lines, the first the boot, each name one word (rt64's specializer reads
  no further). A game with many levels has a section a level or an area (GoldenEye, Majora's Mask, Donkey Kong 64,
  Conker, Wave Race 64, Banjo-Tooie, Pilotwings 64, Mario Kart 64).
- Chrome builds the whole list behind the launcher and the game from a draw of nothing at setup (rt64 977ddca), and a
  frame that wants 4 or more unbuilt shaders of a section holds the game for those under "Preparing graphics" (rt64
  950188f). Firefox builds nothing behind the game: it waits for the boot section before the first frame and for a
  section when the game gets there. A shader the list misses draws with the ubershader in Chrome until it is built
  behind the game, while Firefox builds it before the next frame, the game waiting (0.2-0.3 s a shader, rt64
  b52d78f), and the page remembers it (`localStorage`) and builds it with its section next visit. `play_page.mjs`
  prints each miss and records them (`shaderMisses`), so a long play on a fresh profile counts what a list lacks
  (docs/findings.md, What the prebuilt lists miss).
- Recording: `?record-shaders` prebuilds none and prints an `rt64 shader:` line per description, in the order the game
  asks; add the new ones. `tools/record_shaders.mjs` records from a plan. A game with many levels records by code: a
  survey in its patches library or in JavaScript reaches each level as its own code would (`patches/shader_survey.c` or
  `tools/shader_survey.js`, `tools/shader_plan.json`, `tools/record_shaders.sh` in the game forks).
- Chrome keeps built pipelines between visits only as far as its 6 MB `DawnWebGPUCache` per profile holds them, which
  a page can't change; Firefox keeps none, so every visit waits as long, set by the WGSL's size (docs/findings.md,
  Chrome's pipeline cache, WebGPU in Chrome and Firefox).

## Building with Emscripten

What a recomp's code needed for wasm, besides N64ModernRuntime-0003 and N64Recomp-0001:

- wasm-ld turns a call whose signature doesn't match the callee into a trap. Upstream N64Recomp's C calls a few
  functions its `funcs.h` never declares (N64Recomp 025cab9 declares them), and Emscripten makes an implicit
  declaration an error. A new one shows as that error or as `unreachable` at run time; `frontend/`'s link fails on any
  wasm-ld warning so a mismatch shows at build time.
- WebAssembly only rounds to nearest and `fesetround` silently does nothing; without N64Recomp-0001 a game's truncating
  float-to-int conversions round (Rush 2049's attract race walked off RDRAM after 40 s). Float to int out of range
  saturates in wasm and gives 0x80000000 on x86; nothing has hit it yet.
- RDRAM has no guard pages: a stray access corrupts memory rather than faulting, unless it lands past the heap.
- A tail call is a call and a return in the C, which natively becomes a jump and in wasm stays a call: N64Recomp
  8038212 forces a `return_call` with `-mtail-call` (Conker ran out of stack minutes in without it).
- A wait that polls memory or the clock without an OS call never ends, or starves every other game thread: ultramodern
  runs one game thread at a time and delivers interrupts only inside OS calls (GoldenEye, docs/game-forks.md).
- An interrupt's message to a queue the game leaves full (Jet Force Gemini's controller queue) waits in a list, tried
  first at each OS call and idle wait (N64ModernRuntime 66539ab). Put back into the external queue, which keeps no
  order, the idle thread took it again at once and spun on it while the messages behind it, an RDP completion among
  them, waited for a game thread's OS call.
- A page's files are in the page's thread's file system, and every file call from another thread waits for that
  thread, which presents nothing meanwhile. Read a large file with `read()` in 4 MB pieces and write it in one call,
  behind `__EMSCRIPTEN__` (N64ModernRuntime-web b79d63b, CBFD-Recompiled-web 8de429c), never with an
  istreambuf_iterator, an ifstream loop or libc++'s `std::filesystem::copy_file`, which take a 64 MB ROM in ~65,000
  round trips (docs/findings.md, Behind CLAUDE.md's rules). The same is why `thread_stdio.js` prints a thread's lines
  without the page's thread, and `persistent_home.js` stores a file of 1 MB or more (a ROM) from a worker.
- Emscripten's SDL2 port opens audio on the page's thread except one line that reads the audio context's rate on the
  calling thread, which fails from a pthread (`frontend/sdl_audio.js` works around it). It also plays on the page's
  thread, WebGPU's, 256 frames at a time, so its callbacks come late and a laptop's music was extremely choppy. A page
  plays through `n64recomp_browser::audio` (`frontend/audio_output.h`), an AudioWorklet reading a ring in wasm memory on
  the audio thread: 0 frames short, even with the page's thread blocked 150 ms of every 500.
- RmlUi's FreeType must be the `freetype-legacysjlj` build (setjmp with wasm exceptions); the plain one leaves
  `emscripten_longjmp` undefined.
- The `--pre-js` files and the shell are read at link time, so a page lists them in `LINK_DEPENDS`.
- Every library a page links is static: a shared one makes emcc link the page relocatable, with the `pic` system
  libraries, and wasm-ld then refuses an EM_JS function's address ("recompile with -fPIC"). A game whose CMake sets
  `BUILD_SHARED_LIBS OFF` as a normal variable before a subproject's `option(BUILD_SHARED_LIBS ... ON)` (lunasvg's)
  gets the shared one on a build dir's first configure only (CMP0077's old behaviour), so its page sets it in the cache
  (`FORCE`), as Jet Force Gemini's does; only a fresh build dir shows it.
- The web builds compile with `-msimd128` (hlslpp's wasm backend, the auto-vectorizer) and `-DXXH_HAS_INCLUDE(x)=0`
  (xxHash's NEON path through Emscripten's `arm_neon.h` doesn't compile in C++, so XXH3 stays scalar): small (~5% off a
  Rush 2049 race display list: its `CMakeLists.txt`) but free, since every browser with WebGPU has wasm SIMD.
- hlslpp's wasm SIMD backend had movehl, dot4, load3 of int3 and per-lane shifts wrong, so transpose, inverse and some
  mul shapes too, which RT64 builds its view and projection matrices with (Banjo drew a polygon over the whole screen).
  hlslpp-web fixes them and CI checks the backend against plain C++. `HLSLPP_SCALAR` is no way out: its `frac` is wrong
  for negative numbers.
- Every page's canvas is CSS-sized: a window made with `SDL_WINDOW_ALLOW_HIGHDPI` goes to device pixels on the web,
  draws four times the pixels at 200% and takes every click at the wrong spot, so Load ROM opens nothing (Wave Race
  64's did, wave-race-64-recomp-web 9d3f621), which only a laptop's screen or a run at `--scale 2`
  (`tools/page_driver.mjs`) shows. A new port clears the flag with Emscripten.
- Gamepads (no `SDL_INIT_HAPTIC` on Emscripten: README) were checked with a stand-in `navigator.getGamepads()` (a
  standard-mapping pad set from CDP, `vibrationActuator.playEffect` logged): launcher, menus, a race, rumble. No real
  pad has been tried. Exit is hidden on a page (RecompFrontend-0005): it left a black canvas, and the next input
  aborted the program (`emscripten_proxy_async failed`).
- A script in the page (a preload, a survey) waits on a timer (`setTimeout`, 4 ms at the shortest), never on a loop of
  messages to itself (`MessageChannel`, a promise that resolves at once): in Chrome ~10,000 tasks a second starve the
  tasks that carry the device thread's WebGPU work, and presents stop for seconds while the thread looks free
  (docs/findings.md, Behind CLAUDE.md's rules).
- A page's build is hundreds of compiles, each starting emcc's Python (about a second on Windows), and a link whose
  Binaryen pass at -O3 runs on one core. ccache in front of emcc (`frontend/build_speed.cmake`, ccache on `PATH`) hits
  every compile of a fresh build dir of sources built before, though little carries from one game to another; a build
  dir outside the checkout gets half the hits (ccache makes paths relative only inside `CCACHE_BASEDIR`).
  `-DN64RECOMP_BROWSER_FAST_LINK=ON` links at -O1; a page people play links at -O3. Timings: docs/findings.md, Behind
  CLAUDE.md's rules.

## Mods

Mods a player adds stay off on the web: the live recompiler (sljit) emits machine code, and a wasm port would have to
emit and load wasm modules instead. A recomp's built-in mods work (README): recompiled to C at build time, and what a
mod replaces or hooks redirected at each function's entry, since wasm code can't be rewritten. Clang folds a function's
address used as an array index into the load's offset, where the linker fills in the function's index in the module,
not its table index, which hung the page at boot until `recomp.h` hid the address behind an empty `asm`: a function
pointer is safe in wasm as a value, not as arithmetic. No other N64 recomp running in a browser was found to learn from.
