# N64Recomp-browser

Web support for N64 static recompilations built on [N64Recomp](https://github.com/N64Recomp/N64Recomp),
[N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime), [RecompFrontend](https://github.com/N64Recomp/RecompFrontend)
and [RT64](https://github.com/rt64/rt64): the game, its menus and RT64 built with Emscripten into one page that draws
through WebGPU. It is game-agnostic. A recomp keeps its own submodules at the commits it pins and adds this repo
beside them, and its web build patches their checkouts (Using it in a recomp). It was written for San Francisco Rush
2049: Recompiled, and five more recomps build a page with it (Games).

> Written almost entirely by AI (Claude), like the recomp it came from.

## Games

Each game's repo builds its page with this repo; a page holds no ROM, the player loads their own. Rush 2049 aside,
the games are here to build out and test the web support on more than one game: what one of them or one browser turns
up is fixed in this repo or the forks unless it really is that game's own, so every game and both browsers get it.

| Game | Recomp | Repo | Page | Intel UHD, Chrome | Intel UHD, Firefox | Played |
|---|---|---|---|---|---|---|
| San Francisco Rush 2049 | this project's own recomp | [rush-2049-recomp](https://github.com/amazingalek/rush-2049-recomp) | [play](https://amazingalek.github.io/rush-2049-recomp/) | 57; 125* | 21; 133* | 2026-10-21, v0.80.0; laptop 2026-10-17, v0.58.0 |
| GoldenEye 007 | [GoldenEye64Recomp](https://github.com/podulator/GoldenEye64Recomp) by podulator, from cblock85's | [GoldenEye64Recomp-web](https://github.com/amazingalek/GoldenEye64Recomp-web) | [play](https://amazingalek.github.io/GoldenEye64Recomp-web/) | 60; 342* | 356* | 2026-10-21, v0.80.0; laptop 2026-10-18, v0.63.0 |
| The Legend of Zelda: Majora's Mask | [Zelda 64: Recompiled](https://github.com/Zelda64Recomp/Zelda64Recomp) by Zelda64Recomp | [Zelda64Recomp-web](https://github.com/amazingalek/Zelda64Recomp-web) | [play](https://amazingalek.github.io/Zelda64Recomp-web/) | 60; 209* | 37; 160* | 2026-10-21, v0.80.0; laptop 2026-10-17, v0.58.0 |
| Banjo-Kazooie | [Banjo: Recompiled](https://github.com/BanjoRecomp/BanjoRecomp) by BanjoRecomp | [BanjoRecomp-web](https://github.com/amazingalek/BanjoRecomp-web) | [play](https://amazingalek.github.io/BanjoRecomp-web/) | 60; 312* | 30†; 269* | 2026-10-21, v0.80.0; laptop 2026-10-17, v0.58.0 |
| Conker's Bad Fur Day | [CBFD-Recompiled](https://github.com/sciaschi/CBFD-Recompiled) by sciaschi | [CBFD-Recompiled-web](https://github.com/amazingalek/CBFD-Recompiled-web) | [play](https://amazingalek.github.io/CBFD-Recompiled-web/) | 53; 327* | 28; 266* | 2026-10-21, v0.82.0; laptop 2026-10-17, v0.58.0 |
| Donkey Kong 64 | [Donkey Kong 64: Recompiled](https://github.com/Rainchus/Donkey-Kong-64-Recompiled) by Rainchus | [Donkey-Kong-64-Recompiled-web](https://github.com/amazingalek/Donkey-Kong-64-Recompiled-web) | [play](https://amazingalek.github.io/Donkey-Kong-64-Recompiled-web/) | 60; 360* | 38; 337* | 2026-10-21, v0.80.0; laptop 2026-10-17, v0.58.0 |
| Wave Race 64 | [Wave Race 64: Recompiled](https://github.com/danielgomesvieira2000/wave-race-64-recomp) by danielgomesvieira2000 | [wave-race-64-recomp-web](https://github.com/amazingalek/wave-race-64-recomp-web) | [play](https://amazingalek.github.io/wave-race-64-recomp-web/) | 54; 312* | 20†; 294* | 2026-10-21, v0.80.0; laptop 2026-10-15, v0.46.0 |
| Pilotwings 64 | [Pilotwings 64: Recompiled](https://github.com/danielgomesvieira2000/pilotwings-64-recomp) by danielgomesvieira2000 | [pilotwings-64-recomp-web](https://github.com/amazingalek/pilotwings-64-recomp-web) | [play](https://amazingalek.github.io/pilotwings-64-recomp-web/) | 60; 254* | 37; 179* | 2026-10-21, v0.80.0; laptop 2026-10-17, v0.58.0 |
| Banjo-Tooie | [Banjo-Tooie: Recompiled](https://github.com/Vidanox/BanjoTooieRecompiled) by Vidanox | [BanjoTooieRecompiled-web](https://github.com/amazingalek/BanjoTooieRecompiled-web) | [play](https://amazingalek.github.io/BanjoTooieRecompiled-web/) | 59; 356* | 30†; 258* | 2026-10-21, v0.80.0; laptop 2026-10-17, v0.58.0 |
| Mario Kart 64 | [MarioKart64Recomp](https://github.com/sonicdcer/MarioKart64Recomp) by sonicdcer | [MarioKart64Recomp-web](https://github.com/amazingalek/MarioKart64Recomp-web) | [play](https://amazingalek.github.io/MarioKart64Recomp-web/) | 60; 358* | 43; 342* | 2026-10-21, v0.80.0; laptop 2026-10-18, v0.63.0 |
| Star Fox 64 | [Starfox64Recomp](https://github.com/sonicdcer/Starfox64Recomp) by sonicdcer | [Starfox64Recomp-web](https://github.com/amazingalek/Starfox64Recomp-web) | [play](https://amazingalek.github.io/Starfox64Recomp-web/) | 173* | 201* | 2026-10-21, v0.80.0 |
| The Legend of Zelda: Ocarina of Time | [OoT: Recompiled](https://github.com/JonB-Dev/oot-recompiled) by JonB-Dev | [oot-recompiled-web](https://github.com/amazingalek/oot-recompiled-web) | [play](https://amazingalek.github.io/oot-recompiled-web/) | 60; 320* | 37; 282* | 2026-10-21, v0.80.0; laptop 2026-10-18, v0.63.0 |
| Diddy Kong Racing | [DKR-R](https://github.com/ThatGuyMcd/DKR-R) by ThatGuyMcd | [DKR-R-web](https://github.com/amazingalek/DKR-R-web) | [play](https://amazingalek.github.io/DKR-R-web/) | 353* | 267* | 2026-10-21, v0.82.0 |
| Jet Force Gemini | [Jet Force Gemini: Recompiled](https://github.com/VibinToast/JetForceGemini-Recomp) by VibinToast | [JetForceGemini-Recomp-web](https://github.com/amazingalek/JetForceGemini-Recomp-web) | [play](https://amazingalek.github.io/JetForceGemini-Recomp-web/) | 58; 336* | 44; 311* | 2026-10-21, v0.80.0; laptop 2026-10-18, v0.63.0 |
| Pokémon Snap | [Snap64Recomp](https://github.com/JackandBeans/Snap64Recomp) by JackandBeans | [Snap64Recomp-web](https://github.com/amazingalek/Snap64Recomp-web) | [play](https://amazingalek.github.io/Snap64Recomp-web/) | 358* | 206* | 2026-10-21, v0.82.0 |
| Rush 2: Extreme Racing USA | [Rush 2 Recompiled](https://github.com/bryantmh/rush2recompiled) by bryantmh | [rush2recompiled-web](https://github.com/amazingalek/rush2recompiled-web) | [play](https://amazingalek.github.io/rush2recompiled-web/) | not yet | not yet | 2026-10-21, v0.82.0 |

Median presents a second after the shader waits on a laptop's Intel UHD, maximized on its screen; * on a stand-in, newer than
the laptop's: a desktop GPU at 3840x2000, uncapped from v0.47.0 (higher is a cheaper frame, 360 at most), Firefox's
animation frames held at 360 from v0.67.0 (a row on an older tag was played before the hold); † the game's own rate.
Goal: 60.

## Using it in a recomp

This is for a recomp built on RecompFrontend that already builds for the desktop. Its dependencies stay as they are:
`rt64`, `N64ModernRuntime` and `RecompFrontend` remain its own submodules at the commits it pins, this repo is added
beside them, and the web build patches their checkouts with `patches/`. The patches change nothing in a desktop build
(The forks), and the changes stay in the checkouts, uncommitted.

### 1. Add this repo

```bash
git submodule add https://github.com/amazingalek/N64Recomp-browser lib/N64Recomp-browser
git -C lib/N64Recomp-browser checkout <the newest v0.x.0 tag>   # forks.txt and the patches/ made from it
```

### 2. Patch the checkouts

From the recomp's folder, before building N64Recomp from its `N64ModernRuntime/N64Recomp` (the page needs the code
the patched one writes, step 5):

```bash
cmake -P lib/N64Recomp-browser/patches/apply.cmake lib     # the folder holding rt64, N64ModernRuntime, RecompFrontend
```

That patches rt64 with the plume and hlslpp inside it, N64ModernRuntime with its N64Recomp, and RecompFrontend, on
top of any changes the recomp makes to them itself, and leaves one that is patched already as it is. A project kept
somewhere else is patched by name: `cmake -P lib/N64Recomp-browser/patches/apply.cmake N64Recomp tools/N64Recomp`.
`apply.cmake`'s header says how to take a patch out again.

### 3. The web build in CMakeLists.txt

In the recomp's CMakeLists.txt, in an `if (EMSCRIPTEN)` block (the desktop build doesn't change):

```cmake
include(lib/N64Recomp-browser/patches/apply.cmake)       # patches the checkouts, if they aren't already
n64recomp_browser_apply_patches(${CMAKE_SOURCE_DIR}/lib)
add_compile_options(-pthread -fwasm-exceptions -msimd128 -mtail-call "-DXXH_HAS_INCLUDE(x)=0")
add_link_options(-pthread -fwasm-exceptions -mtail-call)
include(lib/N64Recomp-browser/frontend/build_speed.cmake)   # ccache, if it is on PATH
set(RT64_PREBUILT_SHADER_LIST ${CMAKE_SOURCE_DIR}/<the game's shader list>)   # required: step 4
# ... add rt64 (RT64_STATIC), N64ModernRuntime and RecompFrontend as for the desktop ...
add_subdirectory(lib/N64Recomp-browser/frontend ${CMAKE_BINARY_DIR}/web_frontend)
n64recomp_browser_frontend_page(<the recomp's executable>)
target_link_options(<the recomp's executable> PRIVATE -sINITIAL_MEMORY=2GB)   # if 1536MB, frontend/'s, isn't enough
```

Build with `emcmake cmake ... -DRT64_NAGA_EXECUTABLE=<naga>` (`cargo install naga-cli`), with `spirv-opt` on
`PATH` (SPIRV-Tools, `apt install spirv-tools`, which specializes the prebuilt shaders below), after `embuilder build sdl2-mt freetype-legacysjlj` once. With ccache on `PATH`, a new build dir, or another
checkout with its build dir at the same place in it, compiles nothing that was compiled before (`frontend/build_speed.cmake`
says how), and `-DN64RECOMP_BROWSER_FAST_LINK=ON` links a page to try something in seconds instead of minutes,
without Binaryen's whole-program optimizations (not for a page people play). The page needs a browser with WebGPU and
must be cross-origin isolated: served with `Cross-Origin-Opener-Policy: same-origin` and
`Cross-Origin-Embedder-Policy: require-corp`, or with `coi_serviceworker.js` beside it on a host that can't set
headers (GitHub Pages). Mods a player adds are off: the live recompiler emits machine code, which a page can't load.
A recomp's built-in mods work (step 5). BanjoRecomp-web's CMakeLists.txt and BUILDING.md are a whole port done this
way.

### 4. The recomp's own code

What changes in the game's own code (behind `__EMSCRIPTEN__`) and files:

- RT64's Framerate at Display and its resolution at Auto by default, so that every page presents at the display's rate
  (60 a second on a 60 Hz display, 144 on a 144 Hz one), RT64 interpolating between the game's frames, and draws at
  the canvas's size, whatever the recomp's desktop build defaults to. RecompFrontend's defaults are those. A recomp
  with settings of its own sets them with Emscripten (Ocarina of Time's `machine_defaults`, Jet Force Gemini's
  `rr_default`, which also moves a page's saved Original to Display once), and one that interpolates only in a profile
  of its own plays that profile on a page (DKR-R's Modern). The game's own frame rate setting stays as the game has it.
- A window made without `SDL_WINDOW_ALLOW_HIGHDPI`, so the canvas stays in CSS pixels. With it, a recomp that makes its
  own window gets a canvas at the device's pixels, which on a laptop at 200% draws four times the pixels and takes every
  click at the wrong spot: Wave Race 64's Load ROM opened nothing there (wave-race-64-recomp-web 9d3f621).
- Sound through `n64recomp_browser::audio` (`frontend/audio_output.h`: `open`, `queue`, `queued_frames`) in place of
  `SDL_QueueAudio` and `SDL_GetQueuedAudioSize`. SDL2's port plays from the page's thread, which WebGPU's work keeps
  busy, and its sound breaks up there (Rush 2049's music was choppy on a laptop in Chrome).
- No native file dialog (nfd: RecompFrontend asks the page; a recomp with menus of its own calls
  `n64recomp_browser::pick_files`, `frontend/file_picker.h`, and gets the picked files' paths) and no `SDL_INIT_HAPTIC`
  (Emscripten's SDL2 has no haptics, and `SDL_Init` fails as a whole when asked for them, gamepads with it).
- Input read whatever SDL's window focus says. On a page SDL's keyboard focus follows the canvas's window focus events,
  which a page opened behind another window, or driven by a script, never gets, though its tab gets the keys: DKR-R
  read the controller only while its window had focus, and its page took no input (DKR-R-web's `runtime_platform.cpp`).
- RT64's render to RAM costs a 5-6 ms wait per display list in a browser: turn it off with
  `recompui::renderer::set_render_to_ram(false)` if the game never reads its frames on the CPU (Banjo's frame reads
  are patched to sample RT64's framebuffer on the GPU, so it is off there too). Majora's Mask reads them: the
  Pictograph Box compresses the photo it took on the CPU, so it stays on there. Donkey Kong 64's code reads its
  framebuffers too (a Banana Fairy photo), and it is left on there (not tried off).
- A loop that waits by polling the count (`osGetCount`) or memory, with no OS call inside, holds every other game
  thread for as long as it spins: ultramodern runs one game thread at a time and switches only in an OS call.
  GoldenEye's main loop waited for its next frame that way, and its audio thread waited behind it: ~0.4 s of sound
  short at a time in Firefox, ~20% for ~40 s while Chrome built shaders. GoldenEye64Recomp-web's `patches/fps.c`
  yields in each poll (`recomp_yield_self_1ms`). A trace of count calls a second finds such a loop.
- A frame can take seconds on a page: the game waits while the browser builds the shaders it needs (Firefox's boot
  waits are 5-30 s). A scheduler that takes a frame that slow for a hung RCP and goes on without it, by sending
  itself the done message or resetting the RSP, then builds the next frames into display lists RT64 hasn't read yet,
  and RT64 reads a mix of two frames' commands. Pilotwings 64's scheduler did that after 50 retraces, and its page
  stopped soon after Firefox's boot wait (a palette load past the end of memory, a texture 8404 texels wide):
  pilotwings-64-recomp-web's `patches/sched.c` takes those timeouts out. Look for a retrace handler that counts
  retraces while the RSP or RDP is busy.
- A recomp's patches that move the display lists into a larger buffer of their own have to move every one, the boot's
  first included. Mario Kart 64's pointed every task at its larger pool but left the boot's first list in the game's
  pool, so RT64 read zeros on into the pool where the game was already writing the next frame, and about one boot in
  twenty on the page hung or crashed. MarioKart64Recomp-web's `patches/gfx_config.c` patches `rendering_init` too.
- A runtime that holds the game thread submitting a display list until the list is drawn holds the whole game through
  render to RAM's readback (ultramodern runs one game thread at a time). Jet Force Gemini's (its base's, not
  N64ModernRuntime's) did, and with the exact copy its page lost 250,000-300,000 sound frames in 160 s.
  JetForceGemini-Recomp-web lets the game go once RT64 reaches the list's last full sync (the list is all read by
  then), and sends the RSP's and the RDP's completion once the frame is drawn, as before. Running on, a scheduler that
  counts retraces while a task is current can then take a frame waiting for shaders for a hung RCP (above).
- Printing from the game's threads is cheap: `frontend/thread_stdio.js` hands each line a thread writes to stdout or
  stderr to the page's console from that thread. Emscripten runs every write on the page's thread and waits for it
  there (its file system lives there), and that thread is WebGPU's too, so each line held the thread that printed it
  for as long as a frame's work. Banjo-Tooie's upstream prints ~100 lines a second: on its title screen in headless
  Chrome its sound was 12,900-13,400 frames short of ~2.1 million without it, 235-1,325 with it. A write to a file
  still goes to the page's thread.
- If the game needs render to RAM but can take a frame one display list old, call
  `recompui::renderer::set_render_to_ram_late(true)` too (rt64-web's `renderToRAMLate`): a list's copy into RDRAM then
  lands when the next list starts, or at a VI once the GPU has it, and the list doesn't wait for it. Only the last copy
  of a list is late: one that a later part of the same list reads is still made in place. In headless Chrome, render
  to RAM on: Conker's Bad Fur Day in Windy 10.7-11.8 ms a list against 14.8-16.4 ms with the exact copy, GoldenEye in
  Dam 3.8-5.2 ms against 8.0-9.7. It is
  wrong for a game whose CPU reads a frame it has only just drawn: Majora's Mask flushes its task queue and then reads
  its pictograph and its pause menu's background at once, and would get the frame before, so it keeps the exact copy.
  The game runs while a late copy is pending, so the copy keeps every word the CPU wrote to the framebuffer before or
  while it lands (rt64-web cb75c5c) and the console reports each such write: run the page through the game's levels
  with it and read those lines. Conker's CPU writes to framebuffers with a pending copy in every chapter, 89 times
  over its shader plan, and the page plays the same; GoldenEye's never does. A word the CPU writes with the value it
  already held looks untouched, though, and gets the frame, so it is also wrong for a game that puts code or data in
  a framebuffer's memory once the RDP is done: Donkey Kong 64 inflates its main code and data over the framebuffers
  of its boot logos, the late copy crashed its boot now and then, and it keeps the exact copy too. Jet Force Gemini's CPU
  reworks its shadows' render targets once the RDP has drawn them, and keeps it as well.
- Give RT64 a list of the game's shaders, so the page builds them before the game draws with them.
  This is part of every port, not an optional extra: without it the page is unplayable on most machines. Until a
  shader is built RT64 draws with its ubershader, which costs several times as much a pixel: on a laptop's Intel
  graphics in Chrome that is a frame a second for minutes, and Firefox, which builds a pipeline in line with
  everything else, builds none during play, so it would draw everything with it. The list is a file of shader descriptions, five hex words a line (a line
  starting with `#` is a comment), in sections: those above the first line reading `section <name>` (one word) are the boot, and
  each section after it a level or a part of the game. In Chrome, which builds pipelines on threads of its own, the
  page builds the whole list behind the launcher and the game from when it starts, in the list's order, the boot and the section after
  it on half the cores and the rest one at a time, and the game waits only when a frame asks for at least 4 shaders of one section that aren't
  built, for those, holding its frame under a small "Preparing graphics" indicator in a corner; the rest of that
  section is built next. Rush 2049's page, cold, has its 75 pipelines built ~5 s after it opens, behind the
  launcher. Firefox waits instead, since anything built behind the game stalls its
  frames: for the boot before the game's first frame, and for a whole section when a frame first asks for 4 of its
  shaders. So a list's boot is what the game shows before its first level, and the rest goes in sections: Rush
  2049's boot (logos, title, menus) is 21 pipelines and 2 s in Firefox, against 75 and 9.8 s as one list, and its
  race section's 41 take 7 s when the first race starts. A boot that would still be long can end at the title, with
  the menus the next section: Pilotwings 64's title and menus were 80 pipelines and 24-37 s in Firefox before its
  first frame, and its title alone is 33 and 7-9 s, the menus' 47 built after Start; Chrome builds that second
  section on the boot's threads too, so it doesn't wait for it. A
  description can be in several sections. One the list missed, or a few at a time, is built
  behind the game, which draws with the ubershader meanwhile; Firefox builds it before the next frame instead, the game
  waiting, a fraction of a second a shader. The page remembers each
  one the list missed, with the section the game was in (the frontend's shell keeps them in `localStorage`), and on
  later visits builds it with that section as if the list had it, so what a recording didn't reach costs a player
  one visit, not every one. Set
  `RT64_PREBUILT_SHADER_LIST` to the file before adding rt64. Each one is specialized at build time by
  `spirv-opt` (rt64-web's CMakeLists.txt says how), its pixel shader both with dual-source blending and without,
  and they are built largest first, as many at once as the computer has cores, each pipeline once: descriptions that
  come out as the same shaders and the same pipeline state share one. A line reading `background` also
  starts a section of that name.
- Record that list by code, not by playing: `tools/record_shaders.mjs` (its header says how) serves a build, opens it
  in headless Chrome with `?record-shaders`, under which the page prebuilds nothing and prints an `rt64 shader:` line
  for each description the game asks for, and follows a plan of the game's own, a JSON file of steps that reach each
  level: keys, clicks, waits, and JavaScript that writes the game's memory. Each section is recorded from a fresh load
  of the page, so it has everything its level draws, and what the boot draws goes above the first section. A plan
  usually needs a small patch in the game that starts a level or shows a menu when the script asks, called once a
  frame: GoldenEye's is `patches/shader_survey.c`, `tools/shader_plan.json` and `tools/record_shaders.sh` in
  GoldenEye64Recomp-web. Why run the game at all: a shader is the RDP's state at a draw, the combiner and render
  mode, and the game's code sets much of it as it draws, so no table in the ROM lists them. Record each level's start,
  not the whole game: what a level draws later is mostly what its start drew, and the rest is built as it comes.
  Chrome keeps built pipelines for later visits in a cache of 6 MB per profile, for every site together: Rush 2049's
  105, about 4 MB, are then all built in 0.4-0.7 s and the indicator never shows; a game whose list doesn't fit waits on
  every visit, and sections keep each wait to what one level needs. Measured in Chrome 154 on an RTX 2070 (headless):
  Rush 2049's list, then without sections, took 6.3-7.2 s cold on 12 cores; 6 at a time it took 10.0-10.8 s optimized by
  `spirv-opt` against 16.1-17.7 s only specialized, and its WGSL is 5.9 MB against 17.5 MB, since many descriptions that
  differ only in what the shaders ignore come out the same. Rush 2049's list is
  `src/rt64_shaders.txt` in its repo.

### 5. What the build needs

The rest is what a link or a run of the page shows when it is missing:

- Generate the recompiled code with the N64Recomp built from the patched `N64ModernRuntime/N64Recomp` (or
  N64Recomp-web), and build it with `-Werror=implicit-function-declaration`. wasm-ld turns a call whose signature doesn't match the callee into a trap,
  and upstream's `funcs.h` leaves out some of what the C calls (the runtime's libultra replacements, ignored functions,
  `recomp_trigger_event`); N64Recomp-web's declares all of it, so only a hook's own calls are left to the recomp:
  a hook whose text calls the recomp's C declares it there (Donkey Kong 64's `load_dk64_overlay`, in `us.toml`).
  A patch's call to a libultra function goes to the runtime's `<name>_recomp`, as the game's own calls do
  (N64Recomp-web 9eb59c4; upstream calls `osInitialize(rdram, ctx)`, which reaches ultramodern's `osInitialize(void)`).
- A game function with a C library name clashes with the library's declaration once `funcs.h` declares it:
  GoldenEye has its own `strtol`, `strncmp`, `isalpha` and six more. List each in `[patches] renamed` in the game's
  config and the patches' config, and it becomes `<name>_recomp` in both (N64Recomp-web ec0748e renames the patches'
  calls to it too). N64Recomp-web also reads a jump table from the section that holds it, where upstream reads it at
  the function's own ROM offset: GoldenEye keeps them all in a `.rodata` section of their own, so upstream's read
  lands past the ROM's end.
- Build the recompiled code with `-mtail-call` (the `add_compile_options` above). The MIPS code leaves a function
  by jumping to another, a tail call, which the C writes as a call and a return. Natively clang makes that a jump; in
  wasm it stays a call, so code that chains them without returning grows the stack until the browser stops the page
  ("Maximum call stack size exceeded"): Conker's Bad Fur Day does, minutes in. With the tail call feature,
  N64Recomp-web's C forces each one to a `return_call` (`RECOMP_TAIL_CALL` in `recomp.h`, `musttail`); clang won't
  make one by itself, past the early return `RECOMP_FUNC_ENTRY` puts in every function. Without the flag the calls
  stay plain ones.
- A patch calls a native (a symbol at an address in the patches' `syms.ld`) as it calls a recompiled function, with
  `(uint8_t* rdram, recomp_context* ctx)`, so the native has to take that. One with its own arguments, or a runtime
  function the patches call by its name, happens to work on x86 and traps in wasm, and only the link says so: wasm-ld's
  `function signature mismatch`, which `frontend/` makes an error (`--fatal-warnings`). Donkey-Kong-64-Recompiled-web
  wraps `load_dk64_overlay` and ultramodern's `yield_self` in `dk64_load_overlay` and `dk64_yield_self`, and
  GoldenEye64Recomp-web `yield_self_1ms` in `recomp_yield_self_1ms`.
- The patches library's generated C is built like the recompiled code: with `-Werror=implicit-function-declaration`,
  and `funcs.h` included if it doesn't include it itself (Zelda64Recomp-web's `PatchesLib`).
- A built-in mod (`recomp::mods::register_embedded_mod`) is recompiled to C at build time and linked in:
  `n64recomp_browser_precompiled_mod(<target> <mod.nrm> <the recomp's syms.toml> <name>)`, with
  `N64RECOMP_BROWSER_OFFLINE_MOD_RECOMP` set to an OfflineModRecomp built from N64Recomp-web, adds the C (OfflineModRecomp
  `--static <name>`) to the target, and `recomp::mods::register_precompiled_mod(<name>)` beside
  `register_embedded_mod` makes the runtime use it for that mod. The runtime matches it by a hash of the mod's code,
  so another version of the mod the player installs isn't given the wrong code (it fails to load like any mod, with
  no live recompiler). wasm code can't be rewritten, so the functions a mod replaces or hooks are redirected at their
  entry instead: N64Recomp-web's C asks `RECOMP_FUNC_ENTRY` there, which is one byte read for a function nothing
  redirects. Hooks on a function in the patches library work the same way; hooks on a built-in mod's own functions
  don't load (`OfflineModHooked`).
- A mod that fails to load ends in an SDL message box, which calls `alert` from a worker. Workers have none, so the
  frontend's `worker_alert.js` sends it to the console as an error rather than letting the exception stop the page.
- RecompFrontend includes `patches/ui_funcs.h` from five directories above `recompui/src/api/`, so from
  `<recomp>/patches/` when it sits in `<recomp>/lib/`: the declaration of `recomp_run_ui_callbacks`, the patch
  function that runs UI callbacks (`tests/build/patches/ui_funcs.h` is a stand-in).
- RecompFrontend compiles recompui's shaders with the `DXC` and `DXC_*_OPTS` its parent sets, as on the desktop
  (`tests/build/CMakeLists.txt` sets the ones it needs).
- DXC for recompui's shaders is the build machine's, not one built for the target.
- fmt 11.1 (N64Recomp's) needs `target_compile_options(fmt PRIVATE -include cstdlib)` with Emscripten's libc++.
- Emscripten's `<limits.h>` defines `PAGESIZE`, so a source that includes RecompFrontend's `slot_map.h` after it
  needs `#undef PAGESIZE`.
- The page is 32-bit. Code that gets away with a length that wraps around in a 64-bit build doesn't here: Banjo's
  overlay decompression gave inflate `end - start` with `end` before `start`, and `next_in + avail_in` wrapped, so it
  never finished and the page hung at boot.

### When the recomp's commits are far from the patches'

The patches are made on the upstream commits in `patches/patches.txt`, the ones the forks are built on. On every push
CI applies them to the commits the recomps here pin (`patches/pins.txt`: Banjo-Kazooie, Majora's Mask, Donkey Kong 64
with Killklli's runtime and RecompFrontend, Conker's Bad Fur Day, and GoldenEye 007, whose upstream predates
RecompFrontend, so its web fork pins the commits the forks are built on), and over Diddy Kong Racing's web fork's own
patches to its runtime and rt64 (DKR-R-web's `scripts/build_web.sh --patches`), and builds every library of a page
from Banjo-Kazooie's. What to expect from a recomp's own commits:

- Near those: they apply. Where the code around a change differs too much for `git apply`, `apply.cmake` merges three
  ways against the commit the patch was made on, fetched from the fork, and says so (Donkey Kong 64's RecompFrontend
  needs that). On those very commits (Majora's Mask's `recomp-frontend` branch) every patch applies as it is, and the
  recomp's own code builds unchanged.
- Far from them, older or newer: a patch may not apply at all. `apply.cmake` then stops and names the files that
  conflict. rt64's, plume's and hlslpp's newest upstream commits don't take theirs today. Moving that one submodule
  to a commit nearer `patches.txt`'s (that commit itself always works), or pinning the forks (below), gets past it.
  The forks merge newer upstream commits in over time (Changing it), and each tag's patches move with them.
- On top of the recomp's own patches to the same lines: they conflict. The forks keep their changes off the lines a
  recomp's own patch is known to touch (Conker's Bad Fur Day adds includes to rt64 beside theirs). Where both make the
  same change their own way, the recomp leaves that file out, as a path in the project after its name:
  `cmake -P .../apply.cmake N64Recomp tools/N64Recomp src/analysis.cpp` (Conker's own patch already finds a jump table
  in another section, which N64Recomp's `src/analysis.cpp` change does for GoldenEye). A recomp that makes the web's
  change to a file left out its own way, merged by hand with its own, takes the forks' later changes to it with
  `cmake -P .../apply.cmake rt64 lib/rt64 --since <commit> <file>...`, run once its own change is in: what the web has
  changed in those files since this repo's `<commit>`, the one its merge was made from, merged three ways. Only a
  change that meets its own lines stops the build, for another merge by hand, which is then from the new commit.
- Applying isn't building. A patch that applies can meet an API that has moved, and then the recomp's own code
  changes: Banjo-Kazooie's runtime is older than the one the forks are on, and its `recomp::start` takes arguments,
  not a `recomp::Configuration`, so its `main.cpp` calls it its own way, as on the desktop. A recomp's own fork of a
  submodule can also want a library a page hasn't got: Donkey Kong 64's RecompFrontend (Killklli's) has a mod store
  that fetches with curl, found with `find_package(CURL REQUIRED)`. The store stays off on the page, so
  Donkey-Kong-64-Recompiled-web puts a `FindCURL.cmake` of its own first on `CMAKE_MODULE_PATH` with Emscripten, with a
  `curl/curl.h` whose every call fails (`web/curl`), rather than patching the store.

### Or pin the forks

A recomp can instead point its `rt64`, `N64ModernRuntime` and `RecompFrontend` submodules at the forks (The forks), at
the commits `forks.txt` names at a tag, and leave out the `apply.cmake` lines: the web support is then in the
submodules' history, not in their working trees. None of the games here does: it moves the recomp off upstream's
commits, and every new tag moves its submodules again.

## The forks

The changes to the upstream projects are commits on the `main` branch of a fork of each, on top of a commit upstream
(newer upstream commits are merged in, never rebased onto). They stay forks: RT64, plume, N64Recomp, N64ModernRuntime
and RecompFrontend don't take code written with an LLM (their CONTRIBUTING.md), so none of this is offered to them.

```
fork                                     upstream                 what the fork adds
amazingalek/plume-web                    renderbag/plume          a WebGPU backend, the display's rate timed from
                                                                  animation frames, 2 frames in flight (up to 4
                                                                  where the GPU reports them done late;
                                                                  ?presents-in-flight=<n>; ?present-stats prints
                                                                  what holds presents back every 5 s);
                                                                  any backend run on one thread; waits that
                                                                  don't end on Windows' 15.6 ms timer tick,
                                                                  as Firefox's timed waits do there
amazingalek/rt64-web                     rt64/rt64                RT64 on WebGPU: WGSL shaders, no descriptor
                                                                  indexing, background pipeline builds, frames
                                                                  interpolated to the display's rate (a game's
                                                                  offscreen pass in a display list of its own
                                                                  and frames of uneven VIs too) and paced
                                                                  evenly when the GPU falls behind, a game's
                                                                  shaders specialized at build time, their
                                                                  decals drawn without ending the render pass
                                                                  (a depth test and the stencil); tile copies
                                                                  reused from list to list (with render to RAM
                                                                  off, each one was a new texture)
amazingalek/N64Recomp-web                N64Recomp/N64Recomp      the FPU rounding mode on wasm; funcs.h
                                                                  declares every function the C calls; a mod
                                                                  recompiled to C ahead of time; functions a mod
                                                                  replaces or hooks, redirected at their entry;
                                                                  tail calls as wasm tail calls
amazingalek/N64ModernRuntime-web         N64Recomp/N64ModernRuntime  Emscripten: no live recompiler, RDRAM
                                                                  without a guard region; built-in mods linked
                                                                  in, their replacements and hooks as redirects;
                                                                  OSThread's context past libultra's thprof on
                                                                  a 32-bit host; game timers on time where a
                                                                  page's timed waits end late (Firefox on
                                                                  Windows); a ROM read in 4 MB pieces
amazingalek/RecompFrontend-web           N64Recomp/RecompFrontend recompui on WebGPU, the canvas as the window,
                                                                  a file picker on a thread of its own, render
                                                                  to RAM as an option and its copy a display
                                                                  list late as another
amazingalek/hlslpp-web                   redorav/hlslpp           fixes to the WebAssembly SIMD backend RT64's
                                                                  CPU-side matrices use with -msimd128
```

rt64-web's `src/contrib/plume` points at plume-web and its `src/contrib/hlslpp` at hlslpp-web, and
N64ModernRuntime-web's `N64Recomp` at N64Recomp-web. Every
change is behind `__EMSCRIPTEN__` or `__wasm__` (or a CMake option on by default with Emscripten), so a desktop build
of the forks is the upstream one, but for the declarations N64Recomp-web adds to `funcs.h` and plume-web's
`RenderSwapChain::isWaitReady()` (always true but on WebGPU) and `waitOnCaller()` (always false but on WebGPU), which
change nothing there. Each commit's message says what it does and why.

`patches/` holds each fork as one patch, everything its `main` adds to the upstream commit it is on, so a recomp can
take the web support without moving its submodules to the forks (Using it in a recomp).

## This repo

- `forks.txt`: the fork commits that work together. A tag here is a release: a recomp pins its submodules to the
  commits `forks.txt` names at that tag, or applies the patches at that tag.
- `patches/`: each fork at `forks.txt`'s commit as a patch on the upstream commit it is on (`patches.txt`), made by
  `tools/export_patches.sh`; `apply.cmake`, which patches a recomp's own checkouts with them (its header says how);
  and `pins.txt`, the upstream commits recomps pin, which CI patches.
- `frontend/`: what makes a recomp built on RecompFrontend a page, as link options and `n64recomp_browser_frontend_page()`
  (`recomp_web_frontend_page()` works too)
  (its header says what each part does): threads, the page, HOME kept in IndexedDB (a database a page, a ROM stored from a worker), a thread's prints without
  waiting for the page's thread, SDL2 audio from a thread, sound
  played on the browser's audio thread (`audio_output.h`), the browser's file picker for a recomp with menus of its own
  (`file_picker.h`), the WebGPU device, a notice in Firefox on Windows' Intel graphics naming its fixes, and `coi_serviceworker.js`.
- `renderer/`: RT64 as the runtime's renderer without RecompFrontend, for a test page with no menus.
- `tools/`: `fetch_forks.sh` checks out the forks at `forks.txt`'s commits (CI uses it), `fetch_pins.sh` a recomp's
  own commits in `patches/pins.txt`, patched, and `publish_page.sh` puts
  a recomp's built page on its repo's GitHub Pages, as the only commit on an orphan `gh-pages` branch (its header says
  how). A page holds the recompiled code, so it is built where the ROM is, never in CI. `publish_pages.sh` is the
  deploy after a change: it rebuilds every game's page in the Games table from its main on a build host, publishes
  only those whose files differ from what Pages serves (a commit builds the same bytes in any checkout), and boots
  each one it published from Pages in headless Chrome. `timer_tick.c`, linked into a test build, makes a desktop's
  timed waits end on Windows' default 15.6 ms tick, as Firefox's do on a laptop. `record_shaders.mjs` records a
  prebuilt shader list by a plan, and `play_page.mjs` plays a page, a build or one on Pages, by the same kind of plan in
  Chrome or Firefox and measures it: presents a second, sound frames short, WebGPU errors, the shader waits, the GPU's
  load and the browser's cores, a line every few seconds and a summary, for a game's notes and the Games table;
  `--record` appends the run to `plays.jsonl`, every page play kept, a JSON line each, so how each game's page plays
  can be followed day by day; `ab_pages.mjs` plays a new build and the page Pages serves interleaved in Chrome, says
  whether the build plays worse, and with `--smoke` plays the build once in Firefox for crashes and errors (the retest's
  checks). `pass_probe.js`, a preload for it, says what a page's presents spend the GPU on: its
  passes, their size, their draws by shader and the GPU time of each; `webgpu_census.js`, another, counts its WebGPU calls
  and bytes a second by kind, and `gpu_growth.mjs` plays those kinds one at a time in a test page, `gpu_growth.html`,
  reading Firefox's GPU process memory around each; `memory_scan.ps1` says whose code made what that process grows.
  `frame_lengths.js`, a preload too, logs how long the game's frames are against the page's presents, and
  `frame_lengths.mjs` counts from that what each guess at a frame's length would hold and cut. `wait_probe.js` logs
  whether a timed wait off the page's thread ends on time, each second of a play, and `heap_probe.js` how much of its
  heap the page has taken, and the request that ran it out.
  `page_driver.mjs` drives both browsers for them (each header says how), and in Chrome reports an exception on any
  of the page's threads with its stack, which the page itself gets only as an ErrorEvent without one. `wasm_offset.mjs`
  names the function of a page's wasm at the offset a trap gives.
- `tests/`: the plume device thread test, hlslpp's wasm SIMD backend against plain C++, the WGSL checker, and
  `build/`, every library of a page built with Emscripten from the forks. CI (`.github/workflows/ci.yml`) runs all
  four.
- `docs/`: notes for whoever changes this repo, beside `CLAUDE.md`: what the web needs from a recomp and RT64
  (`porting.md`), how a page is played and measured (`playing.md`), the retest and publishing (`publishing.md`), every
  fork commit (`forks.md`), what porting each game fork found (`game-forks.md`), and what has been measured about the
  pages in Chrome and Firefox (`findings.md`).

## Changing it

A change to a fork is a commit on its `main` branch, made on top of what is there (never a force-push: recomps and
tags pin those commits). Then bump `forks.txt` here to the new commit, and to the new rt64-web or
N64ModernRuntime-web commit too when the change was in plume-web, hlslpp-web or N64Recomp-web (their submodule pointer
moves with it). To move a fork to a newer upstream commit, merge that commit into `main` and say in the merge's message
what upstream brought, and move its upstream commit in `patches/patches.txt`. With every change to either, run
`tools/export_patches.sh` and commit the patches with it: CI checks that they match. A patch that stops applying to a
recomp's commits in `patches/pins.txt` means the fork has to change. Once a change to what a page is built from merges and passes CI, CI tags main with the
next release.

Licensed GPLv3 (`COPYING`), as the recomp it came from; the forks keep their upstream licenses.
