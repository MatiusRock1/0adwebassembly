# Findings and measurements

What has been measured about the pages and about Chrome's and Firefox's WebGPU, and what each measurement explains.
Each run of a page is a line in `plays.jsonl`; this file keeps what a run's line doesn't: test pages and test builds,
GPU and CPU counters, traces, and the conclusions drawn. CLAUDE.md points here where a rule rests on one, and its
Ruled out lists what not to try again.


## A page's GPU time

Read with `tools/pass_probe.js` (docs/playing.md). Uncapped at 3840x2000 in Chrome 155 (RTX 2070, a busy
host), RT64 draws a canvas of that size at Auto's ceil(2000/240) = 9 times the N64's lines, 4224x2200 for Rush 2049 and
4148x2169 for Majora's Mask, and every interpolated present redraws the whole frame there. Rush 2049: ~12 passes a
present, 7.1 ms of GPU passes, 83% of it the draws of one 70 KB pixel shader, one with mip LOD whose tile is picked per
pixel (228 draws a present): without them 1.25 ms and 316 presents a second against 150. Majora's Mask: 32-35 passes a
present, 12-13 of the scene (~60 draws each, 2.7-3.3 ms) with as many of its decals between them (depth read-only, ~3
draws, 0.8 ms), 3.7-4.3 ms in all; with every draw skipped 0.10 ms and 315 presents a second against 210, and no one
shader's draws more than about a tenth of it. Render to RAM's 320x240 passes cost ~0.01 ms. So both pages' GPU time is
RT64's own pixel shaders at that resolution, as on a desktop build, not anything of the web's (CLAUDE.md, Ruled out).

Conker's at a laptop's on-screen canvas, 1920x889 (v0.63.0's page from Pages, Windy by its plan, headless Chrome 155
uncapped on an RTX 2070, a busy host, ten 5 s readings a run): Auto draws 5 times Conker's 216 lines, 2334x1080,
48% more pixels than the canvas. 1.0-1.5 ms of GPU passes a present, ~21 passes: 5-6 of the scene at 2334x1080 (~43
draws each, median ~1.2 ms), 6 compute passes (~0.05 ms), one 1920x889 draw into the canvas (0.036 ms), and ~38
buffer copies and one copy of the whole canvas (plume's device thread, WebGPU in Chrome and Firefox), untimed. Its
draws a present by fragment shader: 13 KB ~140, 10 KB 20-44, 29 KB 22, 25 KB 16, 73 KB 15, 1 KB 8, 14 KB 6.5, 4 KB 5.5.
With `?probe-skip` the scene passes' median came to ~1.12 ms without the 13 KB draws, ~1.17 without the 10 KB ones,
0.79 without the 29, 25, 73 and 14 KB ones together and 0.09-0.2 with every draw left out. So Conker's GPU frame is
RT64's own pixel shaders spread over its draws, as Majora's Mask's is, at Auto's rounded-up size; the 13 KB shader's
many draws are small and cheap.

GoldenEye's Dam at a laptop window's 1920x945 (v0.63.0's page from Pages, its plan, headless Chrome 155 uncapped on an
RTX 2070, the host 39% busy, which held it at the 360 cap): Auto draws 4 times its 330 lines, 2682x1320. 0.66-0.77 ms of
GPU passes a present, ~7.4 passes: one scene pass at 2682x1320 (100-275 draws, 0.58-0.69 ms), its depth pass (0.01),
~2.7 compute passes (0.02), one 1920x945 draw into the canvas (0.04), render to RAM's 440x330 passes every other
present (0.01), and ~39 buffer copies and a copy of the canvas, untimed. The draws are spread over many fragment
shaders (25, 10, 70, 60, 21, 24 and 73 KB the most), their mix changing with the view and repeating with the plan's
16 s walk, and the time a present stayed within that range from 50 s to 128 s: no part of the walk costs more and
nothing builds up. So Dam's GPU frame is RT64's own, as the others are; on the laptop below Chrome draws it at 60.

## Memory

Read as docs/playing.md says. Rush 2049's page from Pages, 10 minutes of its attract demo, Firefox 158 on an
RTX 2070 (a busy host): after the first minute the GPU process's private bytes went 1.1 → 1.6 GB at 1920x945 and 1.7 →
2.1 GB at 3840x2000, a step of ~210 MB some 4 minutes in (GPU memory moving to shared) and then 0.2-0.4 MB a second;
from minute 1 to 10 Firefox's heap +4 MB, the system heap +207 MB, GPU committed +245 MB (shared +179). Chrome 155 on
the same page: 718 → 791 MB, levelling off. The page's WebGPU objects don't pile up: a preload counting what it made
and what JavaScript collected held ~2,000 textures, ~5,000 bind groups (plume 97f4e64's 4,096 among them) and ~1,800
command buffers alive over 6 minutes, making ~120 textures and ~250 command buffers a second. On a laptop's Intel UHD
(Firefox 158, 1920x945) it grew a steady 3.5 MB a second, 2.1 GB in 10 minutes, the graphics' shared memory +740 MB:
there every GPU allocation is system memory. 600 s there on v0.58.0's page went 466 → 3142 MB, 4.47 MB a second and
not levelling off: Firefox's heap 29 → 75, the system heap 50 → 1193, GPU committed 343 → 1699, shared 427 → 1688
(Chrome headed 508 → 864 MB, flat after the first minutes).

What the page does a second (`tools/webgpu_census.js`, Firefox 158, 1920x945, its attract race at 60 presents a
second): 1,800-2,400 writeBuffers of 40-82 MB, 2,200-3,400 copyBufferToBuffer of 83-169 MB, one copyTextureToTexture
of the 1920x945 scene a present (~420 MB), 30-230 textures made (mostly 4096x1 r8uint, TMEM, and tiles of 32x16 and
smaller) and as many destroyed, 75-230 compute passes, ~240 render passes of 15,000-30,000 indexed draws, ~250
command buffers each submitted alone and ~60 empty submits, 30-170 bind groups made, and no writeTexture, mapAsync or
createBuffer. `tools/gpu_growth.mjs` plays each kind alone in a test page at those rates: on the RTX 2070 (a busy
host, then a quiet one) none grew the GPU process more than 0.71 MB a second over 60 s, all of them at once 0.45, the
canvas alone 0.27, Firefox's own heap nearly all of it, and leaving the page gave it back. So on a desktop GPU no kind
grows it; the laptop, where the page grows 4.47 MB a second, is where a kind would show.

On the laptop (Firefox 158, Intel UHD, 1920x945, v0.58.0's page) no kind grew it either, nor all at once (0.65 MB a
second); with Rush's ~20 texture sizes (1x2 to 128x64, 2,000 alive) and its writes spread over 200 buffers it grew
2.01, nearly all GPU committed, and the system heap not at all, against the page's 4.3 (60 to 300 s: GPU committed
+529 MB, the system heap +461; +587 MB of write-combined commit in 15 segments, on an integrated GPU likely the same
memory as GPU committed; of Firefox's own reports only WebRender's texture hosts grew, +14). What does grow it there
comes with the attract race's scene changes, which the test page has none of. Every ~35 s the page draws 2,000-6,800
non-indexed draws a second for a few seconds, and every second time its live textures fall from ~2,000 to ~180 and fill
again in 10-20 s; the GPU process stepped 80-230 MB at five of six of them, 723 of the 1,008 MB it grew from 60 to
320 s. Banjo-Kazooie's plan, which changed no scene in its 300 s, held 180-600 textures and grew 0.18 MB a second; a test
page that fills 2,200 textures in 4 s and destroys all but 200 every 20 s grew 0.34. Neither page creates a pipeline,
shader module, sampler or layout after its first minute.

Whose code made what grows: `tools/memory_scan.ps1` (its header) reads the GPU process's pages committed since a
snapshot and counts what in them points into each loaded module. Rush 2049's page from Pages in Firefox 158 on the RTX
2070, uncapped at 1920x945, 60 to 540 s of its attract (a quiet host; about:memory start to end: the system heap 23 →
232 MB, Firefox's heap 53 → 150, GPU committed 483 → 1176): +131 MB of Windows' heap, whose pointers go into d3d12.dll
(69,849), NVIDIA's D3D12 driver nvwgf2umx.dll (37,796) and dxcompiler.dll (17,275) and 92 into Firefox's xul.dll, with
12 DXBC shader containers; +120 MB write-combined in four 32 MB blocks, all of them by 240 s; 3 MB in mozjemalloc's
1 MB chunks. So the system heap that grows is made by the D3D12 runtime, the driver and DXC, not by Firefox's own
code. A pointer names who made a block, not who keeps it: whether wgpu holds the D3D12 objects behind it, and what
the Intel driver's share is on the laptop, is still open.

What did grow a page's video memory was RT64's interpolated frames, before rt64 8a2c6a7: a color target per display
frame of a game frame, kept for the rest of the visit, so as many as the slowest game frame so far took display frames.
GoldenEye's page from Pages (v0.58.0), Firefox 158, uncapped at 3840x2000 on an RTX 2070 (a quiet host), its plan into
Dam: a preload counting the large textures alive saw its 5702x2970 rgba8unorm targets (68 MB, the game's framebuffer at
Auto's scale) go 31 → 35 → 37 → 42 as Dam's frame rate fell to ~8 (2.0 → 2.8 GB), the GPU process 3.1 → 4.4 GB; in 2 of
10 runs that day and the run played beside the fix the device was lost to "Out of Memory" at 45-55 s. With the targets
taken in turn, 8 of them, three runs of a test build held 15 of that size at the end and the GPU process 2.5-2.7 GB,
none failed, and presented more: Firefox 175-181 a second (133-150 before), Chrome 219 (166-169). Majora's Mask (20
fps, so uncapped it reuses the targets every game frame), its plan, played in the same hour beside its page from Pages
(v0.58.0): Firefox 236 (165), the GPU process ending at 2.1 GB (2.7); Chrome 308 (228); no WebGPU errors either way.

A worker that traps in `free()` has found the heap already corrupt (`tools/wasm_offset.mjs` names it: dlmalloc
unlinking a chunk whose links were overwritten). Mario Kart 64's page from Pages (v0.67.0) did that once in 5 runs on a
laptop (Intel UHD, Firefox 158 on screen, a 1920x947 canvas), at the title screen, 0.3 s after RT64 asked for a texture
of 16384 a side, past the device's 8192. Neither caused the other:
- RDRAM doesn't run into the heap past the console's 8 MB: N64ModernRuntime-0003 allocates the whole `mem_size`, 512
  MB, only without the guard region above it. What leaves it is an address a desktop build's guard pages would stop:
  KSEG1 (0xA0000000 up, RDRAM + 512 MB, right after it) or KUSEG, which wasm32's 32-bit pointers wrap to anywhere in
  the heap.
- A texture past the device's limit leaves nothing wrong on the CPU's side: plume logs WebGPU's errors, and the
  failed texture is still a handle. The same page in headless Chrome at 7000x1201 failed an 8394-wide target every
  frame for 25 s, ~2,700 errors, and played on at 60.
- Nothing sizes 16384 there from Mario Kart 64's 320x240 framebuffer. Auto at 1920x947 is 4 x 6.08, a target 1946
  wide, a 16-bit tile reinterpreted as 4-bit 7,784; a VI cut to RT64's 60-line floor gives 16 x 16, a target 5,120
  wide, and only a full-width tile reinterpreted from 16 to 4 bits there (20,480) passes 16384. So it took a bad value:
  a VI that short or a few pixels wide, or a framebuffer over 2,690 wide, a game's display list read while it was being
  rewritten, or the same corruption reaching RT64's own state.

It was a framebuffer, from a display list that was already garbage. A test build of the page that logs every change of
VI size, window and Auto's scale, every framebuffer over 1024 a side and every target or tile past 8192 played 21 times
on the same laptop (Firefox 158 on screen, MK64's plan) and trapped once, at the same menu. In the 20 clean plays it
logged only the VI at boot: 320x240, 1920x947, 6.082 x 4.000. In the trapping one the VI stayed 320x240 throughout, and
0.1 s after the plan reached the menu RT64 was handed color images 3072 wide and 108-112 high at 0x00D41BFF and
0x00D117FF (not 8-byte aligned, past the console's 8 MB) and at 0x002F9F80, over 100 of them (the log's cap) in 0.8 s.
Their targets, 3072 x 6.08 clamped to RenderTarget::MaxDimension, are the 16384 x 440 the device refused; no tile copy
or reinterpreted tile passed 8192. The worker trapped 0.8 s after the first, in `free()` again, with an "indirect call
signature mismatch" beside it: a function pointer overwritten too. So the corruption reached what RT64 reads the
display list from before it reached the heap: RT64 read a list that no longer held commands (below), not the VI sizing
anything wrong.

A desktop doesn't make them, even with the laptop's slow RT64 thread put in by hand. A checked test build of the page
(v0.72.0's forks plus checks) traps at the first address out of RDRAM's 512 MB in every recompiled load and store, the
PI DMAs and ultramodern's TO_PTR, logs the stack of every NULL TO_PTR makes into a pointer, and, at the first color
image over 1024 wide, prints the 16 commands each side of it, the frame's list and the segment table, reads those
words again 5 ms later and traps. Its RT64 thread waits 0-30 ms between sp_complete and reading the list, so the game
is told its task is done long before RT64 has read it. On an RTX 5080 (the host 10-21% busy, no other GPU work),
Mario Kart 64's plan played it 21 times through the menu into a race: 11 in Firefox 158 on screen, 10 in headless
Chrome at 3840x2000 with the CPU throttled 3 times. None of them trapped or logged anything (WebGPU errors 0), so in
those plays neither the game, the runtime nor the DMAs reached past RDRAM, the runtime made no pointer of NULL, and no
list RT64 read held a wide color image. Each check reads its address once: a TO_PTR that evaluated its argument three
times popped ultramodern's running queue as often and crashed at boot, which reads like a race between game threads
and isn't one. The laptop trapped once in 21 plays, so 21 clean ones here rule out a likely cause, not every cause.

On the laptop (Firefox 158 on screen, MK64's plan) the same checked build trapped in 3 of 4 plays, every time at its
wide color image check and never at an address check: the game wrote nothing out of RDRAM. Each dump read alike: a
G_SETCIMG 1792 wide at 0xF7B005FF, the command (`FFD716FF F7B005FF`) in segment 6's data 0x9438 in, the 16 words each
side of it RGBA32 texture pixels and none of them changed 5 ms later. RDRAM held what RT64 read, and it was a texture
where the logos' model had been: the game loads its title screen's textures (one PI DMA from its loader thread) over
segment 6 the frame after the logos' last list, which on a console the RSP read within a few ms of its sending. RT64
reads a list on its graphics thread, a frame or more behind the game on the laptop's Intel UHD, and read that one after
the load. Telling the game sp_complete only after RT64 had read the list (the checked build's 0-30 ms delay moved
after the read) trapped 1 in 2: the load comes from another thread and waits on no task. Making every PI DMA from ROM
wait until RT64 had read every list sent before it played 10 of 10 clean through the same menu (6 of them at the
players-0 menu where the traps came), and so did the same wait without the checks and delay, 5 of 5 (presents 56-58
from the second play on), but it cost the sound: 3.4% of the frames short (71,000-78,000 of 2.2 million a play), where
main's page played 0-307 short in the same minutes. The audio thread's sample loads waited behind the graphics too.
Holding only the thread that sends the lists trapped 2 of 2 (the loader sends none), and the threads don't separate by
task either (the video thread sends both kinds; the audio thread only loads). What separates them is where a load
lands: N64ModernRuntime bf96a62 (`ULTRAMODERN_LOADS_WAIT_FOR_DISPLAY_LISTS`, on with Emscripten, with rt64 02f0a7c and
RecompFrontend ab544ca) has RT64 mark the RDRAM it reads each list's commands from, and only a load onto commands one
of the last 8 lists ran waits, at most 2 s; a sound's samples go at once. On a desktop GPU RT64 reads a list in a few
ms, so a load rarely waits at all. On the laptop that wait played 5 of 5 clean, taking turns with main's page in the
same minutes: presents 58.5-58.8 from its second play on against main's 58.2-58.8, and 549 frames short over its 5
plays against main's 120, where waiting on every load cost 71,000 a play. Without the checked build's delay the trap
is rarer there: main's page played 8 of 8 clean that day, and v0.67.0's trapped 1 in 5.

A page that runs out of heap does so in a burst after a stall, not by leaking. Banjo-Kazooie's page aborted with
`Aborted(OOM)` in Firefox 158 in 3 of 6 runs of a retest (2026-10-19 21:11-21:56 UTC, uncapped at 3840x2000 on an RTX
5080, the page from Pages, v0.67.0, and a v0.71.0 build both), at 70, 72 and 123 s; Chrome (throttled 6 times) played
on, and no other game's page aborted. Banjo's heap is fixed (INITIAL_MEMORY, no growth), so that is a malloc past its 1536 MB: the
resize import aborts, and the trap names only abort(). `tools/heap_probe.js` read the heap's break at 843.9 MB from
2 s in to the end of 15 plays of the same page in Firefox the next morning, one of them 5 minutes long: the page takes
what it uses at boot (RDRAM's 512 MB among it) and nothing after. In each aborting run the sound and the presents
stopped together 0-4 s before the abort (the 123 s one: 160,000 frames short and presents 151 → 53 in the 5 s before
it), with nothing on the console. None of the 15 plays aborted: 8 on a quiet host, 3 with 12 busy loops on the host's
16 cores, 3 with a second page (headless Chrome) beside it. A 20-minute soak of the page from Pages (2026-10-20 07:33
UTC, the same RTX 5080 about 20% busy) did, with the probe on: the break held at 843.9 MB for 9 minutes, at 546 s the
presents fell 215 → 45 → 0 and the sound starved, and only then did the break climb, 843.9 → 987.9 → 1179.9 MB in 2 s,
to the abort at 549.8 s. So a thread stalls first and then allocates in a loop, about 170 MB a second, a list
interpreter walking a garbage display list say (Mario Kart 64's above); it needs neither a busy host nor a second page,
only a long enough play. A 17-minute soak on an RTX 2070 played to the end (break 838.9 MB throughout). The request's
size and the stack that made it, heap_probe.js's `heapoom`, haven't been caught yet: they name the loop. Nor does
slowing RT64 bring it on: Banjo built with RT64's thread waiting 0-30 ms after each sp_complete, as Mario Kart 64's
checked build did, played 8 Firefox soaks on the same RTX 5080 (about 95 minutes, one of them 1,046 s) with no abort and
the break at 843.9 MB throughout. v0.77.0's load wait (Mario Kart 64's fix above) ends it. An RTX 2070 doesn't bring it
on: 16 Firefox soaks of 978-1,116 s there (2026-10-20 17:53-22:37 UTC, a shared host), the page from Pages (main
eafae14, v0.71.0) and a v0.77.0 build of the same main in turn, 8 each, played to the end with the break at 838.9 and
839.0 MB throughout. On the RTX 5080 the same pairs (2026-10-21 06:41-08:42 UTC, 11-23% of the GPU busy, the host 12-50%
with others' shared turns beside them) split: the page from Pages aborted in 3 of its 4 soaks, at 96, 516 and 793 s,
and the v0.77.0 build played all 4 to the end (974-1,203 s, about 69 minutes), its break at 844.0 MB throughout. Each
abort went as the first soak's: presents ~210 → 2-85 → 0 and the sound starved within a second, then the break
843.9 → 891.9 or 987.9 → 1179.9 MB over 2 s, where it held ~18 s to the abort. heap_probe.js logged no `heapoom` in
any of them, so the request that ran it out still isn't named. The soaks are 17-20 minutes, not a usual play's 2-5,
since the abort comes anywhere from 70 to 793 s in and most come past 5 minutes. Banjo moved to v0.77.0 on that, as a
critical fix.

No other page leaks or aborts in a soak (docs/playing.md, Soaks). Thirteen games' pages from Pages were soaked in
Firefox 158 and ten of them in Chrome, 2026-10-20 and 21 on an RTX 5080 (the host otherwise idle, other cards' GPU
turns between plays), 21-23 minutes each, with no crash, no abort and no WebGPU error but Banjo-Kazooie's Firefox OOM
above; Pokémon Snap's, Rush 2's and Rush 2049's weren't. dlmalloc's break takes what a page uses in its first minutes,
then holds or steps up a few MB and stops. From the first minute to the last it is flat on Donkey Kong 64 (763.8 and
766.9 MB), Pilotwings 64, Diddy Kong Racing, Banjo-Kazooie in Chrome, and Banjo-Tooie, Ocarina of Time and Jet Force
Gemini from minute 3, and climbs +4.6-4.9 MB on GoldenEye, +8.6 on Mario Kart 64, +9.4 on Star Fox 64 (Firefox),
+6.9-10.2 on Wave Race 64 and +7.2 on Majora's Mask in Firefox (its last step at minute 18; flat in Chrome). At the
fastest of those the 1536 MB heap lasts two days. Chrome's GPU process holds 1.3-2.3 GB through a play. Firefox's,
1.6-2.9 GB, climbs about 100 MB every 6-10 minutes and drifts back down between, on every page, so it churns rather
than grows. Presents hold all through, about 350 a second in Chrome and 180-200 in Firefox. Conker's page alone grows
its heap (-sALLOW_MEMORY_GROWTH, in its own link options); heap_probe.js reads its length too, but Conker's soaks ran
before it could find that page's sbrk, so its heap's curve is still unread.

## A page that stops answering

Firefox drops play_page's connection at its 4,098th message when page_driver.mjs speaks WebSocket with Node's own
client: Node 22.23 (undici 6.28) masks every frame after its 4,096th with zeros (its pool of masks, 16,386 bytes, isn't
a whole number of them), Firefox 158 closes the socket at the first such frame with no close frame (1006), and Chrome
takes them. At play_page's 1 s sampling, about 5.5 messages a second, that is 12.4 minutes into any Firefox play: four
of Banjo-Kazooie's soaks on an RTX 5080 ended at 744-746 s with the page playing normally up to the drop, a blank page
asked 5 times a second at 823 s, and one asked as fast as it answers at the 4,098th, while one asked once a second
lived past 1,000 s. GoldenEye's page from Pages (v0.67.0) in a Firefox soak on the same desktop gave no more answers at
774 s (120-135 presents a second, its tab still busy 2.5 hours on, the browser's process idle): the same count at its
rate, and five replays of it on an RTX 2070 host played to the end (1336 s). page_driver.mjs has a client of its own,
which took 6,000 requests in a row, a 70 kB request and a 1 MB answer in Firefox and in Chrome.

A heartbeat from inside the page can't tell a blocked page from a gone one: in Firefox a worker's
console lines pass through the page's main thread (a worker's beat each second stopped while a blank page's main
thread was held 60 s), and in Chrome page_driver.mjs hears no worker's own console lines at all. play_page.mjs reads the
threads from outside instead: a run that stops answering ends with each process's main thread, the tab's busiest
threads by name, and `main threads: the tab's 1.05 cores, running; the browser's 0.21, waiting (UserRequest)` (the
blank page held, in Firefox; Chrome's read the same) in its failure.

A page also stops answering in Firefox 158 at a level load, rarely and unexplained: GoldenEye's page twice in a row on
an RTX 2070 on a busy host (a build of v0.71.0 with the #gpu notice changed and Pages' v0.71.0 page, both with a
preload, `--play 25`, at 3840x2000), 1-2 s after a section of prebuilt shaders built, its tab's main thread running at
0.7 cores, and Mario Kart 64's v0.80.0-based test build once on a host at 26% CPU, 2 s after its section built.
GoldenEye's two had reached their first shader wait at 91-165 s, where its page reaches it in 21-34 s. The next plays didn't: Mario Kart's two,
and GoldenEye's page from Pages (v0.80.0) in eight with the fork's whole plan through Dam's load and a minute on foot,
three on the busy RTX 2070 host and five on an idle host with an RTX 5080, no WebGPU errors, exceptions or misses. A
run that stops there again is replayed with `--gecko-profile`, which records which of Firefox's threads holds the page.

## Two pages at once

With two Firefox windows each playing a page, one window's animation frames came in bursts (a quarter of the intervals
under 5 ms, up to 20 presents between two frames), which plume's displayTiming read as a display of hundreds of Hz
before plume 16e608a, so RT64 interpolated to it: 80-150 presents a second on a 59 Hz display, the pacing switching on
and off. Bursts didn't come again on a quiet host (one window or two, 1256x645 or 3840x2000), so to test that path, a
preload replaces `requestAnimationFrame` with one that delivers some callbacks 0.1-5 ms after the last frame: with 30%
of them early (83-91 a second), Rush 2049's page on the old rule presented 101-139 a second in Firefox 158, the pacing
switching on and off, and on 16e608a 59-60, as without them (Chrome 155 headless: 56-60). Rush 2049 and Banjo played
alone in Firefox 158 kept 57-62 presents a second at 1256x645 and 3840x2000, the memory flat.

## Chrome with no display

Chrome on Windows times its animation frames by the display's vblank (DXGI's `WaitForVBlank` on the primary output).
With no display to give one, a monitor switched off, that call fails at once (`DXGI_ERROR_INVALID_CALL`) and Chrome
sleeps between frames instead, 17 ms and then up to a tick of the system timer: 17.9 ms at a 1 ms timer resolution
(55.6 frames a second), 17.4 at 0.5, on a blank page as on a game's, headless or in a window. plume reads the
display's rate from those frames, so then every page whose game runs below 60 presents ~55.6, and Pilotwings 64 and
Rush 2049, games at 60, present 60. That was the 55.6 of 8 of the 11 pages in the v0.50.0 retest (frames every 17.9
ms), and main with rt64 c89ced0 read 58.6-60 while the display was there (an hour of 2026-10-16's morning, frames every
16.7 ms) and 55.3-56.0 again once it wasn't: the 55.6 → 60.0 once put down to c89ced0 was the display. Nor did c89ced0
cost anything uncapped: Conker's page on v0.51.0 presented 339-341 a second against v0.50.0's 330 (headless Chrome
155, 3840x2000, both served from one port, interleaved).

## A page in a hidden tab

In a tab behind another, headless Chrome 155 runs a page's timers about once a second and its animation frames not at
all, and calls its GPU work back late. On a bare page whose worker has the page's thread submit nothing and wait for
`onSubmittedWorkDone` before it answers, 74-81 round trips a second while visible fell to 0-28 for the first 20 s
hidden in one visit (one 3 s late) and to 50-62 in another; with a copy and `mapAsync` in place of the empty
submission, 12-37 against 54. A message to the page's thread (`postMessage`, `Atomics.waitAsync`) still came within
40-214 ms. The page's own thread stalled up to 57-73 ms while hidden, against 13 ms at most while visible.

RT64's present thread waited in wait() for those callbacks whenever 2 presents were in flight, and the game waited
behind it. Mario Kart 64's page from Pages, hidden 30 s (`play_page.mjs --fault hidden`, an RTX 2070 on a busy host),
came up 9,699-18,505 sound frames short each 5 s, or 437,906 over the 30 s with a 9 s stretch of almost no sound, and
twice fell to a present a second with its sound gone (up to 347,148 short in 5 s); Star Fox 64's about 20,000 over the
30 s. Chrome's `--disable-renderer-backgrounding` and `--disable-background-timer-throttling` left it short. Its dropped
presents read to pace() as the GPU falling behind: on a 240 Hz display (headless Chrome on an RTX 5080 desktop) Mario
Kart 64's page went from 114 presents a second to 60 while hidden, and each try of the number above fell straight back
while the tab was still hidden, so it stayed at 60 for 80 s after it came back (Star Fox 64's, 20 s).

So a hidden page presents nothing, and pace() counts no presents while it is hidden or for a second after (plume
08f9327, rt64 52ec88f; the test builds played below carried the same change on main's commits before those). On the
same busy host, Mario Kart 64's test build came up 2,541 short over the 30 s and was back at 60 within 5 s; Star Fox
64's lost 7,232 in the first 5 s and none after, then 40,328 in one 5 s after it came back. A page's thread still runs
the game's WebGPU calls, and the game waits for it each frame, so a hidden page on a busy host can still stall: another
Mario Kart 64 run lost 149,016 in one 5 s while hidden, and another Star Fox 64 run came back presenting 25-31 a
second for the 30 s it was played after, its presents done 60-650 ms late with the GPU 9-21% busy and 7.5 of its 8 GB
in use by other pages (Pages' build under the same load came back at 60). On an idle host Pages' kept 60 presents a
second while hidden, and with a preload that times animation frames at 240 a second both came back at 221-225. Firefox
158 plays through it either way, its sound never short.

What stalls it is Chrome's priority, not the page's work. On Windows, within 2 s of a tab going hidden, Chrome 155
lowers its renderer process from normal priority (8) to idle (4), unless the tab plays sound;
`--disable-renderer-backgrounding` doesn't keep it at 8. `play_page.mjs` started Chrome with `--mute-audio`, which
zeroes a tab's sound before Chrome listens for it, so every hidden tab it played counted as silent. On a busy host stood
in by 10 CPU spinner threads and a headless page holding 6,000 MB of an RTX 2070's 8 GB and copying 64 MB a frame
(headless Chrome 155, 3840x2000, uncapped, a whole GPU turn), every muted play of Mario Kart 64's and Star Fox 64's
pages, Pages' v0.71.0 and v0.80.0's builds interleaved (12, three with `--disable-renderer-backgrounding`), stopped its
game while hidden: 214,011 sound frames short or more in a 5 s, about all of them, and 0-2 presents a second, against
4,421-78,380 short in the 5 s before. Played with `--chrome-flag --disable-audio-output`, which sends the sound to no
device and leaves Chrome hearing it, the renderer stayed at 8 in all 8 plays and the game played on: 30,425-58,200
short in a hidden 5 s (102,488 once) against 27,409-59,386 before, what that output costs a visible page too, and
Pages' v0.71.0 kept presenting 179-212 a second hidden. Nor did any come back slow: in the 30 s after, each presented
56-109% of its rate in the 30 s before (97-239 a second), v0.80.0's as Pages', not the 25-31 a second above. An idle
host lowers a muted page too: on Mario Kart 64's page a probe build of v0.80.0, below, made its workloads at the
visible rate for the first 10 s hidden and then at a third of it, 77,710 and 107,621 frames short in two of its hidden
5 s, and was back at 357 presents a second within 5 s of coming back; on Star Fox 64's it lost 7,144 once.

Skipping or batching the device thread's round trips wouldn't help either. The probe build times each call the page's
thread runs for the device thread, from the call to its return. On Mario Kart 64's page on an idle host, visible, at
about 350 presents a second, in each 5 s the workload thread made 1,700-1,800 round trips each of waitForCommandFence,
queryResults and getResults (WebGPU's query pool does nothing in the last two, but each is still a trip), waiting
0.7-1.0 s, 0.09-0.15 s and 0.04-0.07 s in them; the present thread made about 1,750 fence waits (0.4-0.6 s), the game's
RDP thread 150 (0.13-0.16 s) and the texture uploader about 230 (0.03 s). Hidden and lowered, each trip took longer
(a fence wait 1.4-2.0 ms against 0.4-0.6 ms), but the game made fewer of them: the workload thread 560-660 a 5 s,
waiting about as long in all (0.9-1.3 s), and the game's thread fenced 82-122 frames against 150, waiting 0.16-0.29 s
of the 5 s. What the game lost was the rest of its time, in a process Windows ran at idle priority. Star Fox 64's
probe, lowered on the same idle host, waited longer and lost nothing: its workload thread waited 1.0-2.8 s of each
hidden 5 s against 0.4-0.5 s, its game's thread up to 0.74 s against 0.02-0.03 s, and the game still fenced all its 150
frames. On the busy host the page's thread barely ran while hidden, and single trips took up to 1.3-2.7 s. The visible
page's trips cost something too, and are work of their own. rt64 5249040 drops the two that do nothing, the
query pool's, and no page measured the difference: on an idle host with a desktop GPU, uncapped at 3840x2000, Mario
Kart 64 presented 356 a second from Pages (v0.80.0, main's pins but this) and 353 on the build, Star Fox 64 314 and 297
from Pages against 298 and 307, and Mario Kart 64 with Chrome's CPU throttled 4 times 135 from Pages against 153 and
136 (the build's two runs as far apart as the pair). Each fence wait, which stays, is a trip too.

So a play that hides a page in Chrome sends its sound to no device (`--chrome-flag --disable-audio-output`). Muted,
it measures Chrome idling a silent tab. A player's page plays its game's sound, so Chrome keeps it at normal priority
and its game plays on.

## A host that holds Chrome's presents

For half an hour of 2026-10-19 (11:25-11:50 UTC) an RTX 5080 desktop held headless Chrome 155's pages uncapped at
3840x2000 to far less than its GPU could draw, and the page's own runs read it as the page's. Star Fox 64's (its
fork's web-wip faeef4a on v0.69.0, its play plan, a fresh profile) presented 78 and 70.7 a second, its launcher at 77-81
from the first sample, as many animation frames (71.4, 71.7), frame gaps a steady 15.5 ms (the system timer's tick),
the GPU 13% busy; Conker's from Pages, minutes later, 198 with 125 animation frames, where it read 322-340 there that
morning, and its start measured a timed wait of 100 us off the page's thread at 8.7 ms, so plume and the VI thread took
the animation frames instead (as in Firefox: Uncapped in Firefox). Half an hour later the same Star Fox build presented
346.6 a second, 348.2 and 350.8 with `tools/wait_probe.js` (12:02-12:15 UTC, a whole GPU turn each, the host 11-26%
busy), held by the uncapped 360, with 120 animation frames, frame gaps of 2.8 ms and every one of the probe's waits
1-1.2 ms; one of them with the host idle past its display's 10 minutes, so a display that Windows switched off isn't
what held them, though nothing says whether it had. Firefox 158 read what it read in that half hour, 198.4 against
200.6 (about 350 in the menus, 197 in Corneria; its waits late, as always there, 11.8 ms), so only Chrome's was the host.

What the host was doing then isn't known: Chrome's version was the same, and no other session held the GPU. So a Chrome
run uncapped well below a game's other runs on that host, its presents no more than its animation frames, is played
again before it is read as the page's, with `tools/wait_probe.js` to say whether its timed waits ended late. plume's
`timedWaitsEndLate()` and the VI thread's measure them once as a page starts, so a host whose waits turn late after that
shows only in the probe.

It came back from 12:19 UTC that day. Pokémon Snap's page (Snap64Recomp-web on v0.70.0) presented 358 a second at
11:54, held by the uncapped 360. From 12:19 to 12:45 it read 68 (71.6 animation frames), then 172 and, from Pages, 174
(120 animation frames, the GPU 15% busy, the browser on half the cores it had). Its 11:54 build read 176 in the same
minutes, and Mario Kart 64's page, 358* in its row, read 171. Firefox read Snap at 203-206 throughout. Snap's Chrome
cell is its 11:54 run, and Star Fox 64's 173*, from Pages at 12:28-12:31, was played in that state.

## Uncapped in Firefox

`layout.frame_rate` 0, which `play_page.mjs --uncapped` gave Firefox until it gave 360, makes Firefox's animation frames
as fast as it can whether anything was drawn or not: 1,500-11,900 a second on the stand-in (the v0.63.0 retest, Rush
2049 11,493), 3,700-8,600 on a laptop's Intel UHD (Tiger Lake GT1, 1920x945 off the desktop, Firefox 158, Pages
v0.58.0) and 17,000-30,000 there with `gfx.webrender.dcomp-texture-overlay-win`. Chrome headless with
`--disable-frame-rate-limit` makes one when the last was drawn: ~120 a second on the stand-in, 83-102 on the laptop.

- On the laptop WebRender composited for every one of those frames on the GPU the page draws with, and presents
  uncapped were Firefox's GPU's minus that: Rush 2049 39.4 a second by default against 62.3 with the overlay pref
  (Chrome headless 44.9), Banjo 66.1 against 79.4. With the pref the loop crowded the page's thread instead: Conker
  drew 41.4 with the Intel GPU 24-88% busy, against 50.0 at ~90% without it. The round's uncapped Firefox numbers (A
  laptop, measured) understate its GPU that way.
- Replayed at 360 on the same laptop (2026-10-18, Pages v0.63.0, 1920x945 off the desktop, cold, `?present-stats`,
  the host 16-32% busy before each run; plays.jsonl's runs noted "frame_rate 360 replay"), Firefox's animation frames
  ran at 63-154 a second, and its presents uncapped, default / with the overlay pref / Chrome headless, were: Rush 2049
  48.9 and 59.2 / 55.4 and 61.8 / 52.2, Banjo 69.5 and 64.4 / 67.9 and 78.9 / 90.4, Conker 55.4 / 65.0 / 65.0,
  Banjo-Tooie 39.0 / 45.8 / 50.0, the Intel GPU 82-97% busy in Firefox and 88-100% in Chrome, no WebGPU errors.
  - With the pref, 360 reads what the pref read at 0 (Rush 2049 62.3, Banjo 79.4); by default it reads less, so the
    pref still adds presents where WebRender composites each animation frame on the page's GPU: 3-10 a run in Rush
    2049, Conker and Banjo-Tooie, -2 and +15 in Banjo's two pairs.
  - Firefox with the pref draws what Chrome headless does in Rush 2049 and Conker and 4 fewer in Banjo-Tooie. Banjo is
    12-23 short: Chrome holds the Intel GPU at 99-100% there, Firefox at 89-94% with about as many animation frames
    (68-72) as presents.
  - Chrome headless drew 4-22 more than on v0.58.0 (Rush 2049 44.9, Banjo 67.9, Conker 61.1, Banjo-Tooie 41.1), so
    the build is part of Firefox's rise from the round's numbers too; set Firefox beside Chrome on one build.
  - Two runs alike differ by up to 11 a second in Firefox (Rush 2049 48.9 and 59.2, Banjo with the pref 67.9 and 78.9)
    and its p10s are its shader waits, so a single Firefox run says little: compare runs interleaved, several each.
- On the stand-in it cost the browser's process a core and the page nothing a run can see. Rush 2049 and Banjo from
  Pages (v0.63.0, Firefox 158, 3840x2000, cold, a quiet host), interleaved, presents a second (animation frames):
  Rush 2049 134.0 (11,892) and 120.4 (11,433) at 0 against 149.7, 121.2, 145.2, 128.6 and 134.4 (270-345) at 360,
  Banjo 279.6 (3,290) and 286.5 (3,795) against 281.8 and 272.4 (~300); the browser's process 4.1-4.4 cores at 0,
  2.4-3.4 at 360. So the stand-in's earlier Firefox cells stand, though `play_page.mjs` compares a Firefox run with
  none from before (it records `uncapped` as 360).
- At 360 the animation frames fall to 190-300 where the page's thread is busy (Rush 2049's race), still above its
  presents: they hold presents back only on a page that presents near 360, which is the ceiling anyway.
- A laptop's headroom in Firefox is read either way: uncapped at 360, or at the display's rate with the GPU's load
  beside the presents (at 60 off the desktop, Firefox and Chrome loaded the Intel GPU about equally in most games).

## Chrome's pipeline cache

Chrome keeps built pipelines for the next visit, if they fit: the cache (`DawnWebGPUCache` in the profile) is one per
profile for every site, 6 MB (`GetDefaultGpuDiskCacheSize`), and the GPU process reads it into a memory cache of 6 MB
when it starts, so only that much can hit. Dawn keeps the parse, each stage's DXIL and the D3D12 pipeline (PSO) of
each: about 4 MB for Rush 2049's 105 (its big entries 27 KB a pipeline), 16 MB for GoldenEye's 340 (41 KB); Rush
2049's 105 took 16.5 s on a first visit and 0.6-0.7 s on each later one, GoldenEye's 83, 70 and 69 s (headless Chrome
154, before spirv-opt). A second set of keys, which a Chrome or driver update makes (tried with
`--enable-dawn-features=disable_symbol_renaming`), missed twice in a row while the old set still hit: after an update
the wait can come on every visit, until Chrome trims the cache. A page can't change any of it: WebGPU gives it no
pipeline binaries to keep in IndexedDB, and `--gpu-disk-cache-size-kb` only grows the disk side.

How full that cache is: the `index` in `DawnWebGPUCache` holds its bytes as the int64 at offset 48 and its entries as
the int32 at 8. A page whose shaders changed (a build with new ones over a warm profile) left the old entries beside
the new, 10.7 MB on disk, and its visits stayed cold until Chrome trimmed it: cold on the three visits after, the
third open for 5 minutes, in which it fell to 5.3 MB, then 0.7 and 0.4 s. A rebuild with the same WGSL still added 59
entries and took 2.0 s once. The page shows its indicator only after a second, so a warm visit shows nothing.

## What the prebuilt lists miss

Each list was recorded from a plan that reaches a level's start and plays a few seconds of it (its header says what
it left out). How many shaders a longer play asks for that a list lacks, counted by `play_page.mjs` (docs/porting.md,
Prebuilt shader lists): one play of 6-10 minutes a game from Pages on v0.63.0 (2026-10-18, a busy host), cold, headless
Chrome 155 uncapped at 1256x645 (RTX 2070), past level starts into what the recordings left out, reached by each game
fork's survey or warps, memory pokes and inputs: bosses, later rooms, items and weapons in use, minigames, endings.
Each run is in `plays.jsonl` with its misses (`shaderMisses`), its note naming the places.

    game               misses  where the most were
    Banjo-Kazooie        33    every world a few; Furnace Fun 4, the ending 5
    Banjo-Tooie          24    Davy Jones' Locker 17
    GoldenEye            18    Jungle 6, Control 7, Caverns 3 (6 missions)
    Majora's Mask        16    items and masks in Termina Field, the shooting
                               gallery 5, Deku bubbles 4
    Jet Force Gemini      9    bosses, 1-3 each
    Conker                7    Poovarotti, the War boss, the Alien
    Pilotwings 64         7    pilot-class gyrocopter, rocket belt, birdman
    Diddy Kong Racing     6    Wizpig, Darkmoon Caverns, cutscenes

Ocarina of Time 20 (Hyrule Field 8, its dungeons' bosses 1-4 each), Donkey Kong 64 18 in the first 225 s of its
bosses (Aztec's Dogadon 5, the llama temple 4, the lighthouse 4) and Mario Kart 64 5 (mirror Bowser's Castle 2, Banshee
Boardwalk's finish 3) came from plays that didn't get through. Rush 2049 then drove its second track ~6 min (2 missed)
and Wave Race 64 its first three championship races (10 missed); neither plan gets further (Rush 2049 never leaves its
first race, Wave Race 64 fails qualification after the third).

Every one of those misses is now in its game's list, in the section of the place it was met (a boss, a later room,
an item in use in its level's; new sections only for Banjo-Kazooie's later worlds and its ending), and each game
fork's shader plan reaches those places in that section, so a re-recording keeps them. The same long plans replayed
on local builds of those lists (2026-10-18, a busy host, cold, uncapped, 1256x645, both browsers), Rush 2049's and Wave
Race 64's too:

    game               Chrome  Firefox   Firefox's waits under 1 s, all told
    Banjo-Kazooie         0       0         1.5 s
    Banjo-Tooie           0       0         1.2 s
    GoldenEye             0       4         0.8 s
    Majora's Mask         0       3         1.6 s
    Jet Force Gemini      0       0         1.7 s
    Conker                2       0         1.0 s
    Pilotwings 64         0       0         3.6 s
    Diddy Kong Racing     0       0         2.9 s
    Ocarina of Time       0       0         4.0 s
    Donkey Kong 64        5       6         3.3 s
    Mario Kart 64         1       0         2.4 s
    Rush 2049             0       0         0.2 s
    Wave Race 64          0       0         0.8 s

What the replays still missed is in the lists too (Donkey Kong 64's replay got further into its bosses than the first
play). No WebGPU errors. Firefox's waits stay what they were: a few seconds a section where the game enters one, as
before, and the added shaders come as waits of 0.1-0.3 s for 1-3 shaders where the play meets them, 1-4 s all told
over a 6-10 minute play (Banjo-Tooie 6.3 s of waits before, 6.5 s after; Diddy Kong Racing 5.1 s, 5.4 s).

So a long play finds tens of shaders a list lacks, not hundreds: a few a place, the most where a recording never went
(Davy Jones' Locker, GoldenEye's Jungle and Control past their starts, Hyrule Field). They are the same shaders in
both browsers, timing aside (Diddy Kong Racing 5 of Chrome's 6 in Firefox, Banjo-Tooie Firefox's 25 all but one of
Chrome's 24), so what differs is their cost: Chrome builds each behind the game and draws it with the ubershader only
until then, while Firefox, which builds nothing behind the game, holds the game while it builds one (below). The page
remembers each and builds it with its section the next visit, in either browser.

The section a miss is put in is RT64's, not the place: Chrome builds the list behind the game and moves on from a
section only when a frame waits for 4 of the next, so it put nearly every miss in the boot; a miss's time against
its plan says where it was.

Firefox builds a miss before the next frame, the game waiting, as it does a stray of the list (rt64 b52d78f). Drawn
with the ubershader instead, as before, a miss stayed so for the rest of the visit, which on a laptop's Intel UHD costs
most of the frame rate where it covers much of the screen: GoldenEye from Pages (v0.63.0, Firefox 158 off the desktop
at 1920x945) drew Dam at 62-63 presents a second until it met 6 shaders its list lacks, then 18-23 for the rest of the
level, its 2682x1320 scene pass 22.7-33.0 ms against 5.5-5.8, where the runs that didn't meet them drew Dam at 64 for
minutes. A miss is built from the ubershader's WGSL with its spec constants as overrides, as a learned one is: 22
learned shaders added 4.9-5.5 s to Banjo-Kazooie's boot wait in Firefox 158 (7.8-8.3 s against 2.7-3.0, three runs
each from Pages, interleaved, RTX 2070, a host 12-20% busy), 0.22-0.25 s a shader.

Long plays of Banjo-Tooie and GoldenEye built with their lists from before the long plays' misses were added, on main
and with each miss built at once, two or three runs each, interleaved (2026-10-19, a busy host, Firefox 158 uncapped at
3840x2000, RTX 2070, cold): Banjo-Tooie's shader plan's sections one after another (14 minutes), and GoldenEye's
Jungle, Control, Caverns, Cradle, Aztec and Egypt played further in (7 minutes).

    game          build     misses  their waits      presents a s  gaps over 50 ms  over 250
    Banjo-Tooie   main        28    -                 168-172         226-266        18-20
                  at once     28    10, 6.3-6.5 s     169-171         106-114        27-29
    GoldenEye     main        5-11  -                 103-110         460-651         1-2
                  at once     7-10  6-8, 1.2-2.2 s    105-115         326-488         3-14

The longest wait was Davy Jones' Locker's 16 misses at once, 3.4-3.5 s under the page's "Preparing graphics"; the
others are 0.1-0.8 s for 1-3 shaders. On the RTX 2070 the ubershader hardly shows in presents a second, but
Banjo-Tooie's gaps over 50 ms halve once its misses are built.

Putting the builds off was measured too, and doesn't reach them. Built where the game sends no frame for 100 ms (a
screen change, a load), the same plays built 5-6 of Banjo-Tooie's 27-29, the first 6-7 minutes in, and none of
GoldenEye's 5-7, in two runs each, and 2-4 of those builds came as the game's next frame did, holding it ~0.2 s: a
recomp's loads are short, so the game seldom stops sending frames. Nor is there a section's wait to build them in: the
misses come once every section of the list has been reached (Banjo-Tooie's at 640-880 s, its last section's wait at
~600 s; GoldenEye's after its last level's start).

Settings: the flags word (rt64-web `src/shared/rt64_render_flags.h`) changes with RT64's Upscale 2D mode, texture LOD
scaling, MSAA and HDR, and with a rect's own scale, not with the resolution or the canvas: RecompFrontend sets LOD
scaling on and never changes Upscale 2D, and the web has no MSAA or HDR. Pilotwings 64's play plan missed the same 1
shader at 1256x645 and 3840x2000, and none at 960x720 (4:3), where nothing else missed either. A recomp's own settings
can still change a flag: DKR-R's Modern profile's extended culling changed one of its list's in the culling bit.

## The stand-in, measured

On 2026-10-14, every page built on N64Recomp-browser ed8764a (v0.36.0: rt64 58fc4e4's pacing, the CPU hot paths), Rush
2049's, Banjo's, Majora's Mask's and Donkey Kong 64's from Pages, Chrome 155 and Firefox 158, RTX 2070, an idle host,
one page at a time, a cold profile each, over 90 s of the game playing by itself (`play_page.mjs --size 3840x2000
--play 90`). The boot's shader waits and the presents a second after them are plays.jsonl's runs of that date at
3840x2000 (the 90 s ones; GoldenEye's and Conker's local builds on v0.36.0), but for Rush 2049's: Chrome 55-60, Firefox
a 9.6 s wait and then 58-60. What plays.jsonl lacks, GPU busy and watts and the GPU process's cores (medians):

```
                 GPU busy, W         GPU process
               Chrome    Firefox    Chrome  Fx
Rush 2049      32% 57   34% 64      0.26  0.44
Banjo          30% 54   36% 55      0.20  0.27
GoldenEye      29% 48   26% 50      1.14  0.37
Majora's Mask  35% 58   36% 60      1.22  0.41
Conker         29% 52   34% 53      0.30  0.41
Donkey Kong 64 26% 47   27% 48      0.20  0.37
```

Chrome builds a page's whole list behind the game (rt64 950188f), so its GPU process takes ~1.2 cores while
GoldenEye's and Majora's Mask's build, and GoldenEye draws 45-55 until all 202 are built (65 s). Not all of that is
the builds: from Pages in Chrome 155 with a window (`--headed`) on 2026-10-15 it drew 52-58 while they built, 59-60
in the title and credits once all were built (88 s), and then 48-55 in the attract demo's levels with nothing left
to build and the GPU 75-78% busy, so at that size a level's own drawing is the rest. Firefox holds about 60
after every wait. Before rt64 58fc4e4 it didn't: rt64's pacing judged drops on the first few dozen presents after a
wait longer than its 2 s window, or after each try of the number above, and held Donkey Kong 64 at its 30 for 70 s
after the boot's wait and Majora's Mask at its 20 nearly throughout (on from the launcher, at about the display's rate).
Banjo in Chrome is still paced to its 30 for 10 s after its 1.5 s wait, a wait shorter than the window. Sound is short
only in the waits and the first seconds after Start, except in GoldenEye (its README).

What the canvas format changed: Firefox presents a canvas through a texture shared with its compositor only when it is
`bgra8unorm` (`wgpu_client_use_shared_texture_in_swapChain`), and the pages were `rgba8unorm`, so every present was
read back through the CPU. Rush 2049's page at 3840x2000 (a local build, the same GPU, an idle host, attract race, two
runs each interleaved): Firefox's GPU process 0.47-0.52 cores, the GPU 40-46% busy at 93-101 W and 59.3-60.2 presents
a second in `bgra8unorm`, against 1.21-1.24, 78-82%, 104 W and 53.7-58.9 in `rgba8unorm`; Chrome 0.29-0.45, 34-43% and
78-90 W, the same in either format.

Every page again from Pages on b1c35d1 (plume 16e608a and 97f4e64), one page at a time, the same GPU, an idle host, at
3840x2000, 25-60 s after the boot's wait, is plays.jsonl's runs of 2026-10-14 16:24-16:43 UTC from Pages. In Firefox
Majora's Mask and Donkey Kong 64 are held at their game's 20 and 30 by rt64's pacing, which switches on just after the
wait with the GPU ~48 W, not working hard (Banjo's 10 s at 20-30 are the same); the others hold 58-60, the GPU's memory
flat at ~2 GB. GoldenEye's sound was ~8% short in both browsers, ~6% on 59dc8e8 and none from Pages on 7f40089. The
presents above the display's rate and the memory climbing are gone.

Every page again on 2efc795 (rt64 9ed449d), cold, the same GPU and canvas, a quiet host, 25 s after the waits, is
plays.jsonl's 25 s runs of 2026-10-14 for the five forks from Pages. Rush 2049, from a local build of the same commit,
isn't there: Firefox 158 waited 2.2 and 7.3 s for its two sections and then drew 57-60. rt64's pacing switched on in
none of the twelve runs, where on ed8764a Banjo in Chrome was paced to 20-30 for 10 s straight after its wait; no sound
short after the waits, no WebGPU errors.

Every page again on d3b9031 (N64ModernRuntime f0e0884, RecompFrontend 75fe596, rt64 f34b19c), cold, 1256x645, RTX 2070,
a host with every core busy with other work, is plays.jsonl's runs of 2026-10-15 03:37-04:11 UTC (the six forks'
gh-pages files served locally, Rush 2049 a local build of the same commit): Majora's Mask through its plan's whole
clock-town section, pause menu included, where before f0e0884 it stopped ~35 s in; the others through their boots and
25-60 s of play; no WebGPU errors or exceptions.

## A laptop, measured

On 2026-10-15, nine pages from Pages, all built on v0.46.0, on a laptop's Intel UHD (Tiger Lake GT1, 32 EU; Windows 11
in its best power efficiency mode; a 3840x2160 display at 200%), every run on that adapter: Chrome 155 in a window and
headless, Firefox 158, 1920x945 off the desktop, cold, `?present-stats`, each game's play plan (`--play 90` after the
start for those without one). The runs are plays.jsonl's 42 of that date on v0.46.0 at 1920x945 noted "laptop report",
their `gpu.busy` the Intel GPU's 3D engine (~12% of it the idle desktop); those noted "part A, the table" give the
README's cells, the presents a second after the waits. Headless Chrome read within a present of the window, and no run
had a WebGPU error or exception. Firefox's longest gaps were its shader waits, and in GoldenEye's intro it had many
times Chrome's gaps over 100 ms.

- Firefox's 20-30 is RT64's pacing, its done callbacks 25-45 ms late; with 1 ms timers it drew 59 (WebGPU in Chrome
  and Firefox).
- Chrome sat at 51-55 in six games with the Intel GPU at most 70% busy and the browser and the host far from busy, so a
  slow CPU isn't what holds it, and Chrome's 3x CPU throttling (docs/playing.md, A cell of the Games table) doesn't stand in for it: Conker drew
  more that way on the desktop than on the laptop. RT64 paced Conker in Chrome 3 times; the other 54s are unexplained.
  On v0.58.0 it drew 58-60 there (below).
- Maximized on the desktop at its 200% (the runs noted "part C"), instead of off it, Firefox's Intel load rose ~30
  points, its GPU process's CPU 1.4-4.6 times, and Conker's presents fell and its boot wait doubled; Chrome stayed
  within 2 presents. So an off-desktop Firefox run on a laptop reads better than a player's visit. On screen Firefox
  redraws the canvas into its window at device pixels each frame (WebGPU in Chrome and Firefox, below). Chrome maximized
  there had a viewport of 1920x889, Firefox 1920x947: a plan's clicks at another `--size` missed Load ROM.
- In 10 minutes of Rush 2049 Firefox held 55-60, its callbacks ~20 ms late (30-42 where the Intel GPU reached ~97%),
  the cap moving to 3 at 106 s and 4 at 140 s, while its GPU process's private memory grew from 1.05 to 3.14 GB, near
  linearly, and the adapter's shared memory by 740 MB.

On 2026-10-17, the same laptop played nine pages from Pages, all built on v0.58.0 (Chrome 155, Firefox 158, plugged
in, best power efficiency, Windows' global timer at 1 ms set by something already running, the host 1-13% busy before
each run), cold, each game's play plan: plays.jsonl's 79 runs of that date noted "laptop report", failed ones
included, those noted "onscreen" giving the README's cells. No run that played had a WebGPU error or exception.

- Off the desktop (1920x945) Chrome headed drew 58.2-60.1 in all nine and headless the same within a present, where on
  v0.46.0 it sat at 51-55. Firefox drew 59.7-59.9 in Banjo, Majora's Mask, Donkey Kong 64 and Wave Race 64 (20-30 on
  v0.46.0), 58.0 in Pilotwings 64, 55.6 in Rush 2049, 51.4 and 51.5 in Conker, 42.6 in Banjo-Tooie, and 64.0 in
  GoldenEye, above the 60 Hz display, with 60 animation frames a second.
- On screen (maximized at 200%, ~3840x1780 device pixels) Chrome drew 53-60 (Conker 53.4, Rush 2049 57.4, Banjo-Tooie
  59.2, the rest 59.9-60.1) with the Intel GPU 65-95% busy, and Firefox 21-38 with it 97-100% busy (Banjo 85%, paced
  to its 30): Firefox is GPU-bound there on frames Chrome draws within the GPU's time.
- What Chrome loses on screen isn't RT64's pixels. A page's canvas is CSS-sized (no `SDL_WINDOW_ALLOW_HIGHDPI`), so at
  200% its drawing buffer is the viewport's 1920x889, not its device pixels (headless Chrome at device scale 2 and 1
  read back the same buffer), and Auto draws the same multiple of the game's lines there as at 1920x945: Conker's
  2334x1080, 5 times its 216 (`pass_probe.js` on the stand-in at 1920x889, uncapped: 1.51 ms of GPU passes a present,
  90% of it the scene's 6 passes at that size). What is new on screen is the composition, Chrome scaling the canvas to
  the window's device pixels and Windows compositing the 3840x2160 desktop, on the same GPU: the Intel GPU was 3-14
  points busier on screen than headed off the desktop (Rush 2049 84 to 95%, GoldenEye 68 to 81, Majora's Mask 63 to
  77, Donkey Kong 64 57 to 65). The pages with room to spare stayed at 60. Conker, 87% busy off the desktop, fell to
  49-58, and Rush 2049's race, already 98-100% busy off the desktop at 53-58, to 39-46 (its median, 57.4, is mostly
  the stretches at 60). Banjo-Tooie drew no worse on screen (59.2 against 58.8 headed and 58.4 headless); its 20-30
  are the same part of its plan in every run, uncapped too.
- Firefox waited 4-22 s a play for shaders, which make nearly all its gaps of seconds; Chrome waited for none at the
  display's rate.
- plume's probe of a timed wait of 100 us read 6-14 ms in every Firefox run with Windows' global timer at 1 ms: neither
  1 ms nor the 15.6 ms tick, and different from run to run.
- Firefox on screen held Banjo at 29.9-30.1 in six runs, RT64 pacing it while plume's done callbacks came back in 9-15
  ms (median), the GPU was 66-80% busy and plume waited 0 ms a second at 2 in flight (with
  `gfx.webrender.dcomp-texture-overlay-win` and a kick of empty submits): each try at the display's rate fell back
  within ~2 s. What pace() counts is the present thread coming to a game frame's present with the next one already
  queued, and on a desktop GPU (Firefox 158 at the display's rate, 1920x945, `?timer-tick=15.625`, an idle host)
  rt64 f262d56's lines say that thread has no time to spare at a 30 fps game's two presents a frame: once 341 game
  frames in a row came to 33.3 ms each, 32.5 of it asleep to the slots, without a wait for the next one, and one
  present dropped. Most of the other drops there were held by wait() (14-55 ms a game frame), which plume's count of
  time waiting leaves out: on a page it is a loop of trips to the device thread, the page's own (plume_device_thread's
  wait(), runSync of isWaitReady()), each queued behind whatever that thread is doing, with a 1 ms sleep between,
  a timed wait. On the
  laptop's screen the same lines put it on wait(), then on late sleeps (a test build of Banjo's main on v0.66.0,
  Firefox 158 maximized at 200%, cold, `?present-stats`): 30.0 presents a second with default prefs (Intel 86% busy,
  214 drops, paced at 29.5, 41.5, 63.5 and 105.5 s, each try at the display's rate back within ~2 s) and 30.0 with the
  overlay pref (75%, 161 drops). Over the drops leading up to each pace, a game frame took 73.4 / 62.7 ms (median,
  default / overlay) against its 33.3: wait() 32.8 / 38.2, asleep 31.0 / 19.8 of which past the slots 11.5 / 3.3,
  workload 3.5 / 2.5, draw 1.1 / 1.2, interpolation and present() ~0, mostly one game frame a drop. So wait() costs
  two or three animation frames a game frame however cheap the composite, which looked like those trips to the page's
  thread and the sleeps between them (it isn't them, below); the late sleeps to the slots are plume's 6-14 ms timed waits, shorter when the
  overlay takes the composite off the page's thread. Chrome on that screen paced Banjo to 30 too, twice for 10 s in a
  play otherwise at 60, in a build without the lines; on the test build (Chrome 155, 37 drops) the drops before its
  two paces had the same make-up, wait() 33.5 ms a game frame (median) and asleep 30.6, but only 2.0 past the slots.
  plume bf417cf (rt64 0c5ba5d) takes wait()'s trips out: the present thread blocks on a futex the done callbacks wake.
  On a desktop GPU that changes nothing measurable (Banjo in Firefox at `?timer-tick=15.625` 60.0 before and after,
  its drops there the level loads; GoldenEye uncapped in Firefox 174.0 and 177.6 on a busy host), and on the laptop's
  screen it doesn't stop the paces either. That evening's runs there (plays.jsonl's 15 noted "test-v0.66.0" or
  "test-wait": the test build and the same build with only that change, served locally, interleaved, cold, two runs a
  setup and a third overlay pair) paced to 30 the same: with default prefs 29.9-30.0 presents a second in all four
  runs, 4-5 paces and 205-232 drops each, the Intel GPU 85-86% busy, wait() 25.7-26.5 ms a game frame (median over a
  run's drops) with the change against 28.5-37.4 without, and 0-7 ms past the slots; Chrome 59.9-60.0 in all four,
  each with two 10 s paces at the same moments. The wait() that is left is plume's cap on presents in flight, waiting
  on the GPU for earlier presents: plume tried 3 and 4 in flight as the drops began and mostly went back to 2, since
  by then RT64 had paced and the try compared 30 with 30. What decides 60 against 30 there is how much of the GPU
  Windows' compositor (DWM) takes, by each process's use of the 3D engine: with default prefs Firefox's GPU process
  had ~55 of the 85-86%, the rest composing the page; with the overlay pref in the before build's first two runs the
  GPU was 59-61% busy, nearly all Firefox's, and Banjo held 60.0; in the other four overlay runs (all three with the
  change and the before build's third) Banjo paced to 30, Firefox's GPU process had ~26 of 72-73% where measured and
  DWM took 45-54% of the GPU through the third pair. So Banjo's 30 on that screen is the composition's, whichever
  build, not wait()'s trips or Firefox's late sleeps.
- Uncapped at 1920x945, the Intel GPU 94-99% busy in each run, Chrome headless / Firefox presented: Donkey Kong 64
  88.9/63.8, Pilotwings 64 84.5/56.2, Wave Race 64 83.8/74.8, GoldenEye 81.2/69.1, Majora's Mask 68.0/51.9, Banjo
  67.9/60.0, Conker 61.1/48.2, Rush 2049 44.9/27.0, Banjo-Tooie 41.1/31.6. So at a laptop window's size Rush 2049 and
  Banjo-Tooie take more than 1/60 s of this GPU a frame in Chrome. Firefox's are too low to set beside Chrome's: its
  animation frames ran at 3,700-8,600 a second (`layout.frame_rate` 0), and WebRender composited for them on the same
  GPU (Uncapped in Firefox, which has four of them replayed at 360).
- Over 600 s of Rush 2049 Firefox's GPU process grew from 466 to 3142 MB, still near linearly (about:memory:
  systemHeap +1143 MB, gpuShared +1261, heap +46), and Chrome's from 508 to 864, most of it in the first minutes.

That evening the same laptop played four pages in Firefox on screen with `gfx.webrender.dcomp-texture-overlay-win` on
(`play_page.mjs --firefox-pref`) and with the default prefs, one run each, interleaved game by game, cold, nothing else
running (the runs noted "Firefox composition"; the pref couldn't be read back, since the driver can't script
about:support). Presents a second and the Intel GPU's median, default / pref: Banjo 30.0 at 86% / 30.1 at 75%, Conker
29.7 at 99% (paced to 30) / 41.5 at 95% (Windy 39-48, its shader waits halved), GoldenEye 24.7 at 99% / 22.6 at 94%,
Rush 2049 25.7 at 100% / 27.8 at 100%.

- Where a page left the GPU room the overlay took 25-35 points off it: Banjo's intro 57.6-53.7 at 93-96% against
  59.9-57.9 at 64-65%, GoldenEye's 59 at 91-99% against 60-64 at 60-67%, Rush 2049's 55 at 93% against 58.9 at 62%.
  So most of Firefox's on-screen cost is its composition (WebGPU in Chrome and Firefox, below).
- Rush 2049's race (20-37) stayed GPU-bound with it, as Chrome's race is off the desktop: what it draws is more than
  this GPU's 1/60 s, whoever composites it. GoldenEye's Dam (about 20) stayed GPU-bound too, but not on what it draws:
  Chrome drew Dam at 60 on this laptop with the Intel GPU 68% busy off the desktop and 81% on screen, and 81 uncapped
  (~12 ms of the GPU a present), and Dam's frame costs the same all through the plan (A page's GPU time).
- GoldenEye in Firefox off the desktop, that evening's six runs (with and without a preload that kicks plume's
  callbacks): four fell to 20.6-23.8 presents a second in Dam, the other two held 63.9-64.0. At ~20 presents the Intel
  GPU was 84-93% busy, ~45 ms of it a present where Chrome takes ~12, and the GPU process took 0.23-0.27 cores against
  0.52-0.58, so the GPU was busy with something other than the frames. The four ended with 3149-3200 MB of the
  adapter's shared memory in use, the two with 2311-2461. v0.58.0 kept a color target for every display frame of the
  slowest game frame so far (Memory, above; rt64 8a2c6a7 caps them at 8 from v0.63.0), and Dam's are 2682x1320, 14 MB:
  the 800 MB more is about 56 of them, one game frame of ~0.9 s. On v0.63.0 the collapse stayed and the memory didn't
  (next bullet), so it wasn't those targets.
- GoldenEye on v0.63.0 in Firefox, the next day (Pages, its plan, `?present-stats`, cold, interleaved with Chrome
  headless; plays.jsonl's 20 lines of 2026-10-18 noted "laptop report" for GoldenEye): 9 of 13 runs off the desktop at
  1920x945 and both on screen fell to 18-29 presents a second in Dam, starting 65-115 s in, most a few seconds after its
  one-shader wait, with the Intel GPU 91-100% busy; Chrome held 60.1-60.3 at 69-73%. The collapsing runs ended with
  2.0-2.2 GB of the adapter's shared memory in use (Chrome 1.6), not v0.58.0's 3.1-3.2. The GPU drew more power in the
  collapse, not less (6.3-6.8 W at 91-96% busy against 4.1-5.8 W at 71-75% at 60, by RAPL), and no thermal zone or
  limit throttled. `tools/memory_scan.ps1` found 27-37 MB of new driver heap and 7-54 MB of Firefox's own between 15 and
  55 s of play, too little to be it.
- `tools/pass_probe.js` in those runs (Firefox 158 gives it timestamps on this adapter): the scene pass, 2682x1320
  rgba8unorm with depth32float-stencil8, took 5.1-7.1 ms of GPU a present before the collapse and 33-56 ms in it, and
  Chrome's 5.3-6.8 all through Dam. Each pass took 25-35 ms instead of 5-6, with the same draws by fragment shader
  (100-350 a pass), at 1.3-1.9 passes a present instead of 1.0-1.3; every other pass stayed under 0.6 ms. Leaving out
  the 10, 25 or 70 KB fragment shaders' draws (`?probe-skip`) didn't stop it, each collapsing at ~85 s at least once,
  and no texture of 1M texels or more was made after Dam started (in two runs that didn't collapse). At 1280x630 the
  GPU was 58% busy and it never came. So the same draws into the same targets cost Firefox's GPU 5-7 times more, and
  Chrome's never: they were drawn with the ubershader (next bullet), and `?probe-skip` couldn't show it, since an
  ubershader draw carries the size of a shader already in the table.
- What it was, the next two nights (Pages on v0.63.0, GoldenEye's list at main 5967d94, `pass_probe.js`, Firefox off
  the desktop at 1920x945; plays.jsonl's 15 lines of 2026-10-18/19 noted "laptop report"): shaders GoldenEye's list
  lacked, which Firefox drew with the ubershader for the rest of the visit (What the prebuilt lists miss, above). On the
  plan with holds on the game's clock (5967d94) Dam held 64 until 214-360 s in all three runs, the scene pass at
  5.0-6.9 ms, as Chrome's 5.2-6.3 on that plan. On the plan before it, holds on the wall clock, 4 of 5 runs fell to
  16-23 in Dam, the build of the night before (main 0f30f97) as well as that day's, each just after Dam missed some of
  a family of `c8102078 …6f` shaders, about 80 s in: the scene pass went 6.0, 12.1, 22.6 ms a pass over 10 s at the
  same 110-270 draws. The one run that met none of them held 64. GoldenEye64Recomp-web 4681896 adds the 21 shaders
  these runs missed to Dam's section. Nothing in the other pages behaved like it: Rush 2049's race at 86-99% busy for
  300 s kept its main pass at 9-20 µs a draw, and Conker's and Majora's Mask's plans (69-75% busy) stayed flat.
- Banjo stayed at 30 with it: RT64 paced it to 30 with the GPU 70-78% busy until 123 s, and drew 58-60 after.

On 2026-10-18 and 19 the same laptop played Banjo's test build (its main on v0.66.0 with plume bf417cf) and Mario Kart
64 from Pages on v0.63.0 on screen (Firefox 158 maximized at 200%), cold, `?present-stats`, with each process's share
of the Intel GPU's 3D engine (dwm.exe, the browser) sampled every 5 s: plays.jsonl's 24 lines from 20:37 UTC on the 18th
to 00:17 on the 19th, after the 15 above. That night's first laptop runs of Mario Kart 64, Ocarina of Time and Jet
Force Gemini, from Pages on v0.63.0 (plays.jsonl's 17 lines from 22:58 to 23:48 UTC on the 18th, with Diddy Kong
Racing's two failed boots: its page plays the US 1.0 ROM and the laptop has Rev A), read the same split as Banjo (presents a second, then the Intel GPU / Firefox / DWM
in percent): Banjo 30.0 at 85-87 / 55-56 / 30-31, Mario Kart 64 42.6 at 99 / 61 / 38, Ocarina of Time 37.1 at 91 / 53 /
38, Jet Force Gemini 44.2 at 95 / 58 / 36. Chrome 155 on the same screen drew 58.4-60.0 with the GPU 62-73% busy and
DWM at 0. Off the desktop DWM is at 0 for both browsers, and Firefox draws these pages at 58-60 with 56-62% of the GPU.

- What holds Firefox below 60 on this screen is DWM compositing WebRender's native compositor's surfaces (WebGPU in
  Chrome and Firefox, below): Firefox's own share is the same on screen as off, and DWM adds 30-38 points. With
  `gfx.webrender.compositor` false, interleaved with the default prefs, Banjo drew 59.9 twice (p10 28.8 and 59.1, RT64
  pacing it to 30 once and then never, 4 and 2 gaps over 50 ms) at 73-76 / 73-76 / 0 against 29.9-30.0 (p10
  26.7-27.1, 4 paces, 21-23 gaps) at 87 / 56-57 / 30-31, and Mario Kart 64 59.9 (7 gaps) at 62 / 60 / 0. Firefox's
  own share rises 15-20 points when it composites itself, and the total falls 11-37.
- Nothing else tried there moved Banjo off 30 (2-3 runs each, DWM ~31): the canvas configured as the page asks (plume's
  `bgra8unorm`, `alphaMode` opaque, usage 18) or with `alphaMode` forced opaque by a preload, presents in flight fixed
  at 3 or 4 (`?presents-in-flight=`: with the GPU at 84-89% it is throughput, not latency), and the window fullscreen
  through WebDriver BiDi (`browser.setClientWindowState`; its toolbars kept 85 px). `canvas.requestFullscreen()` was
  denied every time under remote control, with the fullscreen prefs set, user activation and the window brought to
  the front (`document.hasFocus()` stayed false), so element fullscreen is untested.
  `gfx.webrender.dcomp-texture-overlay-win` holds 60 only when its overlay engages (above).
- None of it is a page setting: a page can't turn the native compositor off, so it is Firefox's to fix. One laptop,
  one GPU and a 200% panel: another scale or GPU may differ.
- Firefox there ignores plume's `powerPreference` 'high-performance' (nvidia-smi read 0% in every Firefox run), but set
  to High performance in Windows' per-app graphics settings it runs on the RTX A3000: Banjo and GoldenEye both 60.0,
  presents done 2-4 ms after them, the GPU 17% busy. Chrome on the Intel GPU holds 59.7-60.1. So the page's notice
  (`frontend/shell.html`, #gpu) shows in Firefox on Windows only, where its WebGL renderer, which Firefox generalizes
  but keeps the vendor in ("ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0), or similar"), names Intel and
  not Arc, and names the three fixes. Making that WebGL context and losing it took 37 ms once in Firefox on Windows.

On 2026-10-20 the same laptop played Banjo on screen in Firefox 158 with the default prefs and DWM at 0% in every run,
three interleaved rounds of four test pages, each its main eafae14 with N64Recomp-browser at main 92e85dc (v0.77.0+),
at one with RT64's present thread calling wait() before its slot sleep (rt64-web 4462e8e, not on main), at one with that
and pace() leaving the first 0.5 s after a try out of its count (c9908d6, not on main), and main's with
`?presents-in-flight=3` (plays.jsonl's 12 lines from 18:56 to 19:24 UTC): every run was paced to 30 at 28-31 s, and
nearly every try of 60 after fell back within 2-5 s, in all four. Presents a second (median): 30.0, 31.5, 32.6 on main,
30.0, 30.4, 30.0 with the wait first, 30.0, 30.0, 58.1 with the 0.5 s too (a try into a quiet moment), 30.0, 30.1, 30.1
with 3 in flight.

- At 60 the GPU doesn't keep up in Firefox's default path: the Intel GPU was 94-100% busy in every 5 s sample at 60 and
  54-74% at 30. At 30 plume had each present done 10-14 ms after it with no time at the cap; right after a try of 60,
  in the same scene, 18 ms (median, 82 at p90) and 181 ms a second at the cap even with 3 in flight, the present thread
  taking 40-60 ms a game frame, 17-40 of it in wait(). So pace() going to 30 is right there, and a run's GPU reads
  60-70% only because it spends most of its time at 30. With `gfx.webrender.compositor` false (above) the stretches
  held at 60 had each present done 8-13 ms after it: what a present costs in Firefox's own compositing decides it.
- The wait first can't change the rate: once the slots start again from a late present, the present goes out at the
  later of its slot and the done signal wait() waits for, which comes when the GPU is done whenever the wait starts, in
  either order. The sleep and wait() in present-stats' drop lines are the one interval split two ways.

## Laptop-like limits on a desktop, measured

On 2026-10-20, GoldenEye's and Banjo's pages from Pages (v0.67.0), each game's plan, Chrome 155 and Firefox 158 off
the desktop at a laptop window's 1920x945, cold, on a desktop GPU (RTX 5080, 8 cores of 16 threads), one page at a
time, at the display's rate (64 Hz): plays.jsonl's lines of that date noted "laptop-like limits", with play_page's
`--fallback-adapter` and `--affinity` (docs/playing.md, Laptop-like limits on a desktop).

- A software adapter is far slower than a laptop's Intel UHD, so it stands in for no laptop. Chrome on SwiftShader
  drew GoldenEye's logos at 33-65 presents a second and Dam at 0.2-3.8 (median 2.1), its GPU process taking 11.6
  cores, where the laptop's Chrome draws Dam at 60; the plan's holds, 3624 ticks of the game's clock asked, held 10467,
  since the game reads a key once a frame. Firefox on WARP drew the logos at 4-5 and then nothing for most of 280 s,
  its GPU process on 2 cores, and Dam at 0.5-0.6 (a game somebody played took the GPU and the host from 28 s on, but
  WARP draws on the CPU, and the logos before it were no faster). Both played with no WebGPU errors or exceptions,
  SwiftShader without `shader-f16`, and RT64 paced presents to the game's frames as the GPU fell behind, as on a laptop.
- `--affinity 4` (two cores) changed nothing at the display's rate: Banjo in Firefox 62.8 presents a second against
  63.0 on all 16, its browser at 0.5-0.6 cores; GoldenEye in Firefox held Dam at 63.6-64.2 against 63.5-64.0, its
  two shader waits 3.6 and 4.3 s against 3.0 and 3.5 (Firefox builds the pipelines on its GPU process, on the same
  cores), Bond's holds 3626 and 3628 ticks of 3624. Where the intros present faster than the display, one run each
  went either way (Banjo 112-159 on 4 against 92-220 on 16, GoldenEye 152-190 against 118-138). So neither Firefox's pacing to 30 on the laptop's screen nor
  GoldenEye's Dam collapse there is the laptop's CPU: the first was Windows' compositor's share of the GPU, the second
  shaders the list lacked drawn with the ubershader (A laptop, measured), which a desktop shows as `shader missed:`
  lines, not as a slower Dam.

## WebGPU in Chrome and Firefox


- The web swap chain is the browser's preferred canvas format (plume 1988176, `preferredSwapChainFormat`),
  `bgra8unorm` on Windows. Firefox (158, Windows) hands only a `bgra8unorm` canvas to its compositor as a shared
  texture and reads any other format's frames back through the CPU (The stand-in, measured, has what it cost); Chrome
  costs the same either way. Firefox 157 with a `bgra8unorm` canvas filled an 8 GB card and fell below a frame a
  second, which is why the pages were `rgba8unorm` before; Firefox 158 plays 55-60 frames a second at 3840x2000 in it
  for 15 minutes and more.
- How Firefox (its source, October 2026) puts that canvas on screen on Windows: wgpu draws into a D3D11 texture
  shared with WebRender, no copy, but WebRender then draws it every frame at device pixels into its native compositor's
  DirectComposition surfaces, which DWM composites (with `gfx.webrender.compositor` false, into one swap chain of its
  own, which costs a laptop's GPU far less on screen: A laptop, measured) (a 1920x947 canvas at 200% is 3840x1894 of it), blended over what is behind it: a WebGPU canvas is always
  treated as having alpha (`alphaMode` isn't applied to how it is shown, bug 1846605). Its own DirectComposition
  visual, which Windows scales and can put on a hardware overlay, comes only with
  `gfx.webrender.dcomp-texture-overlay-win` (Windows 11 22H2 and later, read at startup), on by default in 149 and
  off again on release since 2026-05 (bug 2036365, slow composites; bug 2038378 is to turn it back on). Nothing a page
  sets turns it on: `alphaMode`, the canvas's size against its CSS size and covering the window change nothing in
  that path; `image-rendering` other than `auto`, a filter, opacity, a blend mode or a 3D transform on the canvas
  or above it keep it off even with the pref. `play_page.mjs --firefox-pref` plays a page with one set.
- Chrome (Chromium's source, October 2026) has no such path for a WebGPU canvas on Windows, by any flag or anything a
  page sets: its frames are shared images for display reads only (`WebGPUSwapBufferProvider::
  GetSharedImageUsagesForDisplay` adds scanout on macOS and ChromeOS only), and Chrome's DirectComposition overlays
  take only video and low-latency canvases (`DCLayerOverlayProcessor`; a `desynchronized` 2D or WebGL canvas, which a
  WebGPU context has no option for). So its compositor draws the canvas into the window's own swap chain at device
  pixels each frame, opaque (plume sets `alphaMode` opaque), and Windows composites that. What Chrome loses on a
  laptop's screen (A laptop, measured) has no flag or page setting to win back.
- plume's device thread (plume-0002) adds a copy of the whole canvas a present: RT64 draws the present into a texture of
  plume's, and the device thread acquires the canvas's texture at present and copies it there (`present()` in
  `plume_device_thread.cpp`); a desktop swap chain is drawn into directly. At 1920x889 that is ~7 MB read and ~7 MB
  written a present, untimed (WebGPU times only passes): a few hundredths of a ms on a desktop GPU, on a laptop's shared
  memory perhaps 0.2-0.4 ms, 1-2% of a frame at 60.
- Chrome builds a pipeline made with `createRenderPipeline` on its GPU process's main thread, which does nothing
  else meanwhile: no frame, no readback, no screenshot, and the page's main thread blocks once its queue to the GPU
  process fills. A specialized RasterPS (1.15 MB of WGSL) takes 1.4-2.1 s there, 6-11 s cold beside another build,
  10-80 ms from Chrome's disk cache (per profile, `--user-data-dir`). `createRenderPipelineAsync` builds on threads
  of its own, so RT64 builds specialized pipelines with it and draws with the ubershader until they're ready
  (plume-0006, rt64-0011). None of them may be built the other way: before a draw has used a pipeline's layout
  there is no WebGPU layout to build it for, so it waits for one, and the spec constant shaders are created at
  setup, because a shader reading a binding from a new stage gives every pipeline a new layout. Without those two,
  boot ran at 17-20 display lists a second for ~10 s and about one run in fifteen froze for good. One compilation
  thread: six at once took ~9 cores and halved the frame rate. The wasm grew from 7.3 to 16.6 MB (the spec
  constant shaders), and since rt64 85a6ad5 links 4.4 MB less of them (GoldenEye's 17.2 → 12.8 MB).
- Chrome parses and validates a shader module (Tint) in `createShaderModule`, on that same main thread, even for a
  pipeline it then builds async, in a time that grows faster than the WGSL (0.16 ms a KB at 24 KB, 0.56 at 180 KB,
  1.07 at 713 KB) and with the variables of a function: that is what held a page's presents 100-160 ms per large
  RasterPS while its list built behind the game, until rt64 29f50e6. What is left there: the pipelines a draw
  wants before their background build is done, built in line (plume 54b3be7 builds every pipeline in the background
  once a draw resolves its layout): the boot's fixed ones and the RSP's compute shaders at the game's first frame
  (13-64 ms each, DXC on that thread; under 50 ms each in a trace of Banjo's Start); a
  `GPUDevice.prototype.createRenderPipeline` wrapped in a preload (`play_page.mjs --preload`) names each; and the spec constant
  shaders' module at setup, which held the launcher's first presents 1.1-1.8 s while there were two, and is done
  before the first present now (below, The launcher). The ubershader
  states (245 KB of WGSL, one per depth and coverage state) were built there too, as the first frames drew them:
  Banjo's page held 2.1 s after Start for 4. A draw of nothing at setup builds them behind the launcher now (rt64
  977ddca), one first and the rest from its compiled shader (plume 2950009): Chrome compiles a pipeline's shaders on
  its own for each, on its worker threads, and 8 at once beside the prebuilt list took every core for ~2 s and held
  the presents as long, though no task on the GPU process's main thread ran over 80 ms (a Perfetto trace,
  `--trace-startup`). The longest present gap after Load ROM, outside the boot and shader waits, against v0.51.0
  (headless Chrome 155, 3840x2000 uncapped, cold, RTX 2070, a quiet host, `plays.jsonl`): Banjo 2.08 → 0.30 s, Rush
  2049 1.35 → 0.25, Conker 2.97 → 0.61 (Load ROM's, on both), Ocarina of Time 2.27 → 0.44, Mario Kart 64 2.53 →
  0.67, GoldenEye 1.79 → 1.65 and Donkey Kong 64 1.78 → 1.54, their second gap gone; Firefox 158 the same on
  both. What is left over 100 ms after Start is not the GPU process (Present gaps after Start, below).
  Dawn reuses a module whose WGSL matches one still alive, but
  keeping a list's ~280 alive cost ~750 MB in the GPU process, and JavaScript only lets one go when it collects it.
- Firefox (157, Windows) builds a `createRenderPipelineAsync` pipeline on its GPU process in line with the device's
  other work: a specialized RasterPS took 2-8 s there (12 at worst), with the page queuing 60 frames a second and
  Firefox painting a handful in between, so menus and races sat below a frame a second for minutes, until every
  shader they use had been built. So in Firefox RT64 builds none behind the game (plume 9c69058, rt64 fcc6fe4, a user
  agent check), and what isn't prebuilt is built with the game waiting (rt64 b52d78f, What the prebuilt lists miss). Firefox 158 does all of a page's WebGPU on one thread
  of its GPU process (`CanvasRenderer`), so its prebuilt waits are each pipeline's build one after another: sampled
  through Rush 2049's boot wait (D3D12, RTX 2070), DXC ~36% of that thread, NVIDIA's shader compiler ~26%, heap and
  copies ~20%, the D3D12 driver ~8%, naga and wgpu ~7%. A pipeline takes ~100 ms there and the largest, pixel shaders
  with mip LOD (224 KB of WGSL), 1.2-2.4 s each. The WGSL's size is the page's lever: rt64 c6cf6c4 took Majora's Mask's
  Clock Town from 15.1-18.2 s to 9.3-10.4, its boot from 3.3-3.9 to 2.3-2.7, Conker's boot from 7.1-8.3 to 6.0-6.9 and
  Rush 2049's from 13.6-14.6 to 11.9-12.6 (Firefox 158, the same pipelines built by a test page, Rush 2049's by its
  page; a host 13-66% busy). In its LOD shaders the tile is picked per pixel, so a level's four taps are loaded in one
  switch of 8 slots (rt64 b052049), not one a tap: GoldenEye's largest RasterPS built in ~60% of the time in a test
  page (Firefox 158 and Chrome 155), and from its page Firefox waited 8.7-9.4 s for the boot and 14.0-21.7 s for Dam
  against 10.4-11.6 and 17.7-23.3 (three runs each, interleaved, a busy host). Rush 2049's waits barely moved: few of
  its shaders have mip LOD. Such a shader sampled two tiles of two levels of four taps, each written out by dxc;
  sampled in loops the shader keeps (two levels, and two tiles where the tile is picked per pixel), it is ~70 KB of
  WGSL instead of 185 (rt64 008f380). Firefox 158 built GoldenEye's Dam in a test page in 5.8-8.3 s against 14.8-19.1,
  Pilotwings 64's menus in 5.7-8.2 against 13.9-16.3, Conker's Windy in 4.1-4.4 against 6.3-8.4 and Majora's Mask's
  Clock Town as before, 4.1-5.4 against 4.5-5.0 (three runs each, interleaved, a busy host). From GoldenEye's page,
  cold, Firefox waited 8.3-9.3 s for the boot and 7.6-8.4 s for Dam against 13.2-14.6 and 17.9-22.0 (1256x645 and
  3840x2000, a busy host), then drew 59-60 presents a second as before, the GPU as busy. A loop over the tiles of a
  shader without LOD costs it: each tile's slot and clamp modes are no longer constants, and one of Majora's Mask's
  went from 10 KB to 60. A loop over the four taps as well made the WGSL smaller still, but Firefox built its
  mid-sized shaders slower (one of 43 KB in 205-265 ms against 157), so the taps stay written out.
- Firefox (157) never holds a WebGPU page back: it takes 60 frames a second whatever the GPU finishes, and Chrome
  throttles the page itself. On a laptop (Intel UHD, Tiger Lake, beside an RTX A3000) at 4K and 200% scaling, a present
  costs Firefox's GPU process and DWM about twice what it costs Chrome (up to 6 times in DWM), ~70% of the Intel chip
  at 60 presents against ~30%, so a race's passes at Auto resolution took it past 100%; then its queue grew past 8 s,
  the GPU process's memory climbed by gigabytes, and the canvas showed 1-2 frames a second with the sound and game on
  time. The passes themselves cost about the same in both browsers, and no WGSL construct was slow in Firefox. So
  plume keeps at most 2 presents in flight (plume 0ddac9b) and RT64 skips those the GPU falls behind on. On an RTX
  2070, with a 1024x1024 pass of 4000 `sin`s per pixel added to each present (a stand-in for a slow GPU), Firefox's
  attract race went from 59 accepted with the queue a second further behind every 10 s to 46 at ~32 ms, Chrome's
  from 54 at 150-190 ms to 53 at ~27 ms; one in flight gave 34-39 (Firefox calls back late), three 47-48 at ~50 ms.
  Without the extra pass both keep 59-60. The resolution stays as the player set it, so a GPU that can't draw it at
  60 shows fewer frames, not later ones. How late: with `?present-stats`, Rush 2049's attract race on the RTX 2070 at
  1256x645 had each present's onSubmittedWorkDone back 11-16 ms after it (median, 14-18 at p90) in Firefox 158 and 3
  ms in Chrome 155 headless, both at 60 a second. The cap leaves two presents ~33 ms, so a callback that comes back
  later than that costs presents while the GPU idles, which was the suspect for Firefox's 20-30 on a laptop's Intel
  graphics until a laptop run read the cap (below). The stand-in for it, on the same RTX 2070 (Firefox 158, 1256x645, a preload
  holding each `onSubmittedWorkDone` promise 20-40 ms past the browser's, in order): Banjo's intro drew ~50 presents a
  second with ~160 ms a second at the cap, and RT64's pacing then held it at the game's 20 for most of 90 s (median 20.0
  and 29.9 in two runs, the GPU ~35% busy), as on the laptop; with 3 in flight 58.3, with 4 59.4, each callback back
  ~35 ms after its present either way. Rush 2049's attract race held 54.6 with 2 (~800 ms a second at the cap; its
  game's 30 never paced), and on plume 009957c, which tries one more while the cap holds presents and keeps it if
  presents rise, went to 3 in 10 s and 4 at 63 s and drew 59.8; without the delay it stayed at 2 and drew 59.8. With plume 3c23b44,
  which tries only from a steady window held more than 10% of the time, Banjo with the delay went to 3 at 9 s (from 54
  a second, 817 ms a second at the cap) and drew 57-58, its waits then too short to try 4; cold without it GoldenEye and
  Banjo stayed at 2 in Chrome 155 headless and Firefox 158, where on 009957c GoldenEye went to 3 in its launcher from a
  window at 0.8 presents a second, and with 5% in place of 10% from one at 55 (58 ms a second at the cap) while Chrome
  built its shaders behind the game. A slow
  GPU gains nothing from one more (2 gave 46 and 3 47 above), so there the try goes back. A page thread kept 60% busy
  (a preload spinning 10 ms of every 16) left Banjo in Firefox at 57.7 with no time at the cap, so a slow page thread
  is not what holds Firefox there. On the laptop itself (Intel UHD, Firefox 158, `?present-stats`, A laptop, measured)
  neither its animation frames nor the cap held it: they stayed at 60, and no time was spent at the cap at 2, 3 or 4
  in flight. RT64's pacing did. Banjo's intro drew 30-35 with each callback back 25-31 ms after its present (p90
  33-45), RT64 paced it to the game's frames at 39 s, and from then it drew 20.0 with callbacks 44-46 ms late and the
  GPU ~40% busy, falling back each of the three times it tried the display's rate; Majora's Mask, Donkey Kong 64 and
  Wave Race 64 were paced the same. Conker drew 24-37 with callbacks 23 ms late (p90 42) and no pacing, which these
  lines don't explain. With the Gecko profiler sampling every 1 ms (`MOZ_PROFILER_STARTUP`), Banjo's callbacks came
  back 12-16 ms after a present, RT64 never paced, and Firefox drew 59.3 and 59.4 in two runs; sampling every 10 ms,
  44 ms, paced, 20.1. On Windows the profiler asks for 1 ms timers (`timeBeginPeriod`) only below 10 ms, so Firefox's
  callbacks look bound to Windows' default 15.6 ms timer. Its own timer resolution can't be read: it is per process
  since Windows 10 2004, and the global one read 1 ms already. A pthread of a test page timing its own waits there read
  it: a sleep of 100 us took 15.56 ms in Firefox and 1.95 ms in Chrome, and a futex wake from an animation frame
  reached the thread in 0.06-0.08 ms. So every timed wait off the page's thread ends on a tick in Firefox there. On
  rt64 c89ced0's fixed timeline, which keeps a late present sleep from pushing back the presents after it, the laptop
  drew Banjo at 59.1 in Firefox and GoldenEye at 59.3 (1 gap over 100 ms in 90 s, against 118 from Pages the day
  before), but Conker at 25-29 in every build: its frames are copied to RAM, each waited a tick or two for its
  readback's answer, and the game's timers, 0.4 ms or less, fired a tick late. A stand-in on a desktop
  (`tools/timer_tick.c`, which stretches each timed wait to a tick of its own) held Conker at 27.0 as the laptop did and
  Banjo at 58-59, and showed the waits one by one: a wait a page's speed hangs on is woken (a futex, the animation
  frame) or spun once a probe finds timed waits late (plume cabe1ac and the others with it), and one that only idles
  (the graphics thread's 1 ms, the thread cleaner's 10) stays timed. Under the stand-in a page's sound is short all
  through (Conker 77,000-81,000 frames in 60 s, main and the fix alike), which the laptop's Firefox runs don't show
  (0-232), so read presents from it, not sound.
- GoldenEye from Pages (v0.58.0) presented 63-64.5 a second in Firefox on a laptop at 60 Hz with 60 animation frames,
  and under the stand-in (`?timer-tick=15.625`, desktop Firefox 158 at the display's rate, a busy host) 63.4.
  ultramodern's VI thread waited for each VI's time with a timed wait, which ended on a tick, so VIs came 15.6 or
  31.2 ms apart, 58-60 a second. RT64 reads a game's rate from the VIs between its last three new frames, read
  GoldenEye's 60 as 30 for 10-13 frames a second, and interpolated each of those into two presents; with the VI
  thread exempt from the stand-in it drew 60.0. On N64ModernRuntime b81df43 and 30c60e5, where a probe finds timed waits late,
  the VI thread waits on a futex the page's animation frames wake and ends at the first frame within half a VI of
  its time. Only a count crosses the threads: the page's thread and a pthread read `emscripten_get_now()` apart in
  Firefox, and a version comparing the two clocks sent VIs 1,500-1,800 a second. Under the stand-in it drew VIs and
  presents 60.0 a second, a gap p50 of 16.6 ms against 15.7, frames read as 30 0.4-3.2 a second, the browser at
  1.28 cores against 1.71, and sound frames short 0 against 47,296 in a play: the audio messages go out with each
  VI, so GoldenEye's short sound under the stand-in was its VIs'.
- A launcher's first frame in Firefox 158 (Banjo's and Conker's from Pages, 3840x2000 uncapped, RTX 2070, a preload
  timing each WebGPU call): the page submits its first four presents within ~20 ms and gets their onSubmittedWorkDone
  back 79-290 ms later, all at once, and from then on no two presents are more than 80 ms apart. Nothing reaches the
  canvas before the first of them, so that wait is the launcher's first frame being made, not a pause in a launcher on
  screen. Firefox's `CanvasRenderer` does the page's setup in order ahead of them: the pipelines made just before (one
  compute, three render, ~100 ms each there, above), RT64's eight targets at Auto's resolution (4148x2169 at 2000
  lines: a depth target and seven colour targets, five of them uncapped's interpolated frames; 19-44 ms with their
  clears in a test page) and recompui's images. Banjo's background is an SVG rasterized at the window's width,
  4037x4000 with half its rows off screen, and its 62 MB took a test page 103-176 ms by every route tried: writeBuffer
  into a new buffer as recompui does, into one kept, in 4 MB pieces, writeTexture, a buffer mapped at creation (about
  1.7 ms a MB, half of it 84-104; Chrome 83). Conker's launcher uploads 4 MB and waited as long (223-290 ms, three
  runs). Firefox calls back only on a submission or its 100 ms timer (`WebGPUDevice::pollQueue`): a test page's empty
  submission came back in ~50 ms on the timer and in 2 ms with a `submit([])` every millisecond, which the swap chain's
  wait sends, so the timer is not this wait. `play_page.mjs`'s about:memory read (`gpuProcessMemory`) held Firefox's
  presents and animation frames 120-203 ms each time, at the play's start and end, and a settled launcher's play
  counted the first as its longest gap (136 and 202 ms, 13.5 and 14.7 without it), so a play's gaps start after it.
- Chrome on Windows gives a page the integrated GPU on a laptop that has two, since it ignores `powerPreference`
  (crbug.com/369219127); `chrome://flags/#force-high-performance-gpu` gives it the other. On that laptop's Intel UHD
  (D3D12) Rush 2049's page crawled until its specialized pipelines were built (~1 fps for minutes in menus, 20-30 in
  races), and its RTX A3000 played at once. That was the ubershader drawing meanwhile, not the builds: with the
  ubershader alone (plume f6d48d3) it still crawled, and at Resolution Original it ran well. Hence the prebuilt lists.
- Chrome's GPU process compiles them on the CPU, so rt64 de43acc builds the ones the game waits for largest first
  (WGSL size goes with build time), as many at once as the host has cores (2-16). Cold in Rush 2049's page, Chrome 154
  headless, RTX 2070, on a 12-core host fully busy with other work: all 105 took 10.2-11.0 s largest first at 6 at a
  time, 6.3-7.2 s at 12 (15.6-16.7 s 6 at a time in list order). With `spirv-opt -O` between re-spirv and naga (rt64
  a01b00f) Rush 2049's 105 are 144 different stages and 5.9 MB of WGSL instead of 210 and 17.5 MB (both pixel shaders
  counted), GoldenEye's 340 210 and 16 MB instead of 624 and 103 MB, the largest RasterPS 224 KB; the whole list took
  10.0-10.8 s instead of 16.1-17.7 s for Rush 2049 and 35-38 s instead of 87-91 s for GoldenEye, and Chrome's GPU
  process spent 47% less CPU on GoldenEye's. Stripping their indentation measured nothing. Checked with the adapter
  reported as Intel to the page (a CDP script overriding `GPUAdapter.prototype.info`): they build, and the game draws.
- RT64's render to RAM (on by default) draws each frame a second time at the N64's resolution and reads it back
  into RDRAM. In Chrome that readback makes the list wait 5-6 ms for the GPU process whatever its size (Rush 2049's
  `headless/main.cpp` header has the measurements), so a game that never reads its frames on the CPU turns it off
  (RecompFrontend-0004, `set_render_to_ram`), and one that does keeps it on. If it can take a frame one list old (a
  patch of the screen, a row of depth), `set_render_to_ram_late` (rt64 73e9ca0) makes the copy land when the next list
  starts instead, and the list stops waiting: Conker's, GoldenEye's and Donkey Kong 64's pages do. Majora's Mask can't:
  it flushes its task queue and reads the pictograph and the pause background at once, so it keeps the exact copy. Nor
  can a game that puts something in a framebuffer's memory once the RDP is done: the copy lands while the game runs,
  and though it keeps every word the CPU changed (rt64 cb75c5c), a word written with the value it held looks untouched
  and gets the frame. Jet Force Gemini's CPU reworks its shadows' render targets once the RDP has drawn them, and with
  the copy late they came out blurred or as dots, so its page keeps the exact copy too. The console reports each write
  it kept, so a page run through a game's levels with the late copy says whether its CPU touches a framebuffer with one
  pending. Through the device thread, the main thread checks a
  READBACK buffer at each replay and present once a copy into it is replayed, maps it when the browser has delivered
  the data, and publishes the answer, which `isMapReady()` reads and `map()` waits for without waiting behind the
  main thread's queue; a build without threads would need `-sJSPI` (or ASYNCIFY) to wait in place. A call that waits
  for the main thread costs 50-120 µs from a pthread in a race, behind whatever is queued before it (RT64 asking at
  each VI whether the late copy could land spent 2.3 s of 13 there in GoldenEye's Dam), a queued one ~0.4 µs, and a
  100 µs sleep there ~1.9 ms.

## A page's thread in Chrome, throttled

Banjo-Tooie's page is the slowest in Chrome with the CPU throttled 6 times (retest run 7, RTX 5080, uncapped at
3840x2000: 76-77 presents a second, the other pages 126-290), and plays like them in Firefox (210-214). From Pages
(built from main e8df837), its plan's boot and then Jinjo Village, the plan's first map, for 30 s, traced
(`play_page.mjs --chrome-trace`; an idle host, 12-23% busy, no other GPU context; tracing cost the page ~15%):

- Throttled 6 times, 72 presents a second, the page's thread is 92% busy. Two thirds of it is the WebGPU calls the
  render thread hands it (Emscripten's mailbox): `writeBuffer` 14% of the thread's time, `setBindGroup` 10%,
  `submit` 3%, `beginRenderPass`, `drawIndexed` and `setPipeline` 1-2% each, Emscripten's object lookup for each
  call 3.5%, and 22% native time V8 can't name (Blink's WebGPU bindings and their IPC). Printing is 1.4%. The game's
  threads, which Chrome's throttling doesn't slow, wait most of the time.
- Unthrottled it reaches the 360 cap with the same thread 55% busy, the same calls on top.

`--preload tools/webgpu_census.js`, throttled 6 times (87-95 presents a second, a shared GPU turn), counts what a
present asks of that thread: ~1,710 `drawIndexed`, ~2,940 `setBindGroup`, ~680 `setPipeline`, 27 `writeBuffer`s of
~1 MB, 39 `copyBufferToBuffer` and 11 render passes. Rush 2049's attract race makes 250-500 draws a present (Memory,
above). plume already skips a pipeline or a bind group the pass has bound (`setPassPipeline`, `bindGroups`), so what
is left is RT64's own per draw, as on a desktop build: the draw, its push constants (`renderIndex` changes every
draw, so each gets a 256-byte slot of plume's ring, `writeBuffer`'s bytes, and a `setBindGroup` at its offset), and
the texture set and pipeline where they change. So Banjo-Tooie is slow there because it draws ~1,700 batches a frame
and each costs the page's thread its calls: its own, not the web support's. On the laptop's Chrome it plays 59
(README, Games). The push constants' per-draw bind and 256 bytes are about a tenth of the throttled thread, the one
part of it shared code could take out.

rt64 cf8beb9 with plume 84b785f takes it out: a raster draw's index is its first instance, so its push constants stay
the same from draw to draw and plume binds them once a pass (docs/forks.md). Measured with the census on an RTX 2070,
Chrome 155, at 3840x2000 uncapped, builds of main and of the change from the same game commits (plays.jsonl, sets
`firstinst-*`):

- Banjo-Tooie, Jinjo Village: `setBindGroup` 1.70 a draw to 0.93, and `writeBuffer` 1.02 KB a draw to 0.72-0.81,
  throttled 6 times (0.52 to 0.39 unthrottled). Throttled 6 times this host's slower CPU is past what the page can
  take there: alone on the GPU, main presented 0.0 a second in both its runs and the change 24.8 and 9.5 (4-48 a
  sample), and beside another throttled page both read 0-0.2.
- Banjo-Kazooie, its plan's walk in Mumbo's Mountain, throttled 6 times: 710-745 draws a present in every run,
  `setBindGroup` 1,217-1,231 a present to 475-484, `writeBuffer` 871-917 KB to 577-635, and 41.4 and 45.2 presents
  a second to 52.2 alone on the GPU (50.9 and 52.5 with a throttled Banjo-Tooie beside it).

What is left a draw is the texture set and the pipeline where they change: RT64's own.

## Present gaps after Start

What each thread does in a gap over 100 ms with no shader wait, read from a CDP trace of every thread of every
process (Tracing at the browser's target: `toplevel`, `disabled-by-default-v8.cpu_profiler` and `blink.user_timing`,
with `gpu.dawn` for the GPU process's WebGPU work), on pages linked with `--profiling-funcs` for the wasm's names, a
preload marking each gap with `performance.mark` (headless Chrome 155, uncapped 3840x2000, RTX 2070, v0.56.0, a fresh
profile). The V8 profiler slows what it samples: a new worker took 130-240 ms traced and 30-115 ms without.

- Each pthread past `-sPTHREAD_POOL_SIZE` waits while the browser makes a worker and instantiates the wasm in it, and
  `osCreateThread` waits for its thread to start. With 32 workers GoldenEye and Donkey Kong 64 ran 45 and 46 threads
  on 12 cores (12 RT64 shader prebuild threads, 12 buffer uploaders, 3 texture stream threads, the runtime's and the
  game's), so the game threads started at Start each made one: GoldenEye's audio manager (195 ms traced) and three
  of Donkey Kong 64's boot (142, 126 and 243 ms). `frontend/CMakeLists.txt` sizes the pool from
  `navigator.hardwareConcurrency` now (55 at 12 cores). Untraced, three interleaved runs each: GoldenEye's Start gap
  1631-1651 ms with 32 and 1600-1619 with 55 (one run of 55 had none), Donkey Kong 64's two 1562-1596 and 1467-1478
  against 1481-1512 and 1444-1454; the renderer's private bytes 2040 MB against 2110, and the first present no later.
  In Firefox 158 (two rounds) no gap moved, GoldenEye's Start being its shader wait there (7.6-8.8 s either way), and
  GoldenEye's first present came 1325-1330 ms against 1120-1198 (Donkey Kong 64's 1665-1754 either way).
  `performance.measureUserAgentSpecificMemory` counts the shared heap once a worker (15-25 GB with 55): read the
  process's own counters.
- The launcher: 1.1-1.8 s after its first frame in Chrome (the page's first presents are queued behind it, so the
  launcher shows that much later), its GPU main thread parsing the spec constant shaders' modules, the flat and the
  smooth RasterPS, 670 KB of WGSL each (560-950 ms each, `DeviceBase::APICreateShaderModule`), after the ubershader's
  245 KB (140-190 ms). rt64 85a6ad5 draws every shading mode with the flat pair and keeps the ubershader's loops in its
  RasterPS, 250 KB (145-150 ms), which also builds its pipelines in about a third of the time (a test page, six of
  GoldenEye's shaders: 1.0-1.6 s each → 0.29-0.46). Two interleaved rounds each, cold profiles, uncapped 3840x2000, a
  quiet host: in headless Chrome 155 GoldenEye's gap 1643-1814 → 427-451 ms and its 300th present 4.4-4.6 s → 2.5-3.2
  s after navigation, Donkey Kong 64's 1092-1235 → none over 100 ms; in Firefox 158 GoldenEye's 319-362 → 127-175,
  Donkey Kong 64's 0-111 → none. What was left of GoldenEye's in Chrome: the two modules, a compute pipeline (56 ms)
  at the setup warm-up's first dispatch and four render pipelines its draws wanted (21-40 ms each), all in line and all
  asked for by setup. Since plume 2746484 and rt64 ba24420 setup returns once its warm-up is submitted and the first
  present waits until the GPU process has done all of it (`onSubmittedWorkDone`), so the launcher's first frame comes
  that much later and nothing follows it: GoldenEye's gap 403-450 → none over 100 ms in Chrome, 144-196 → none in
  Firefox, its first present 1.32-1.43 → 1.78-1.85 s and its 300th 2.84-2.99 → 2.86-3.00 s after navigation;
  Donkey Kong 64's 141-184 ms (one round of two) → none in Chrome. Chrome's module parses and pipelines can't be
  made async (no async `createShaderModule`; a compute pipeline's layout is known at its first dispatch, which is
  setup's), so holding the first frame is what keeps them off the presents.
- GoldenEye's Start (1.6 s): the boss thread's first retraces (~0.6 s), then on a profile with no save its first boot
  validating the EEPROM (`fileValidateSaves` → `fileResetSave` → `fileWriteSave`), 48 EEPROM calls, each between
  `joyDisablePoll` and `joyEnablePoll`, which wait a retrace for the controller thread (~0.77 s); a second visit, with the save, waits 1.05 s. The display list
  thread had the game's first lists and nothing after them until its first frame.
- Donkey Kong 64's two boot gaps (~1.5 s each): its main thread (`func_global_asm_805FBFF4`) waits on one message
  1.30 s and then 1.42 s, every other thread and the page's idle and no RSP task.
- Conker's Start (1.1 s): its first lists, each with render to RAM's copies, whose readback the display list thread
  waits for (`DTBuffer::map`, 3-38 ms each, ~0.5 s in all), while the game waits on them. Its Load ROM gap (0.6 s on
  v0.51.0) is 0.1 s.
- Mario Kart 64's loads (0.43-0.46 s before a race, 0.55 s at its start): the game thread in `audio_reset_session_eu`
  ~470 ms while the audio thread resets its session, the page's thread, the display list thread and the GPU process
  idle. The game's own, a console's too: its audio reset takes 29 audio frames, one a retrace, and every retrace reached
  the scheduler (MarioKart64Recomp-web's BUILDING.md, What porting it found). The profile's one long `osRecvMesg` on
  the scheduler and audio threads is each retrace's wake being shorter than a sample.

## A game's uneven frames

Jet Force Gemini's page presented 58.4-58.6 a second in Chrome on a laptop's Intel UHD (v0.63.0, headed, headless and
on screen) against 60 animation frames, with the GPU 56-64% busy, where Mario Kart 64 and Ocarina of Time drew 60. A
desktop does the same at the display's rate: headless Chrome 155 (60 animation frames a second at its screen's 60 Hz; headless runs the screen's rate, 240 on a 240 Hz one),
1920x945, JFG's page from Pages on v0.69.0, its play plan, `?present-stats`, a busy host. In two runs RT64 dropped
2-6 presents over the plan's ~190 s of play (~440 more in the launcher, before the game), so the presents missing there
are display frames with none, not drops, and not GPU load.

A preload counted, at each animation frame, the canvas textures acquired since the last and how far the game's own
clock (`0x800FD748`, in VIs) had moved. The game runs at 30 dropping to 20, and how often it drops varies from run to
run. In the first run 1339 of its 4916 frames took 3 VIs and 20 took 4-6, and play presented 58.8 a second; in the
second (plays.jsonl, its note names the preload) 525 of 5486 took 3 and 15 took 4-6, and play presented 59.2. In each
5 s whose frames all took 2 VIs, 300 animation frames got 300 presents, the second run's 17 such windows missing 19 in
all, at its loads. Those that mixed 2 and 3 missed 5-16 presents each, 161 in the second run's 22. That is what
RT64_UNEVEN_FRAME_RATES (rt64 179adb8) leaves. It interpolates frames whose last three took uneven VIs (the slowest at
most twice the fastest) at the fastest one's rate, so a 3-VI frame after 2-VI ones gets 2 presents and holds the last
through the third display frame. Counting those display frames from the clock alone (it moves at the game's frame, not
at its swap) gives 54-69% of the missing presents. Banjo-Tooie's 58.4-59.2 in Chrome on the laptop may be the same.

How many VIs a frame takes is known only at its swap, after RT64 has drawn its interpolated frames, so a page can't
fill those display frames without waiting another game frame. A rate guessed from the frame before (rather than the
fastest of three) would hold one display frame where the game slows from 30 to 20, not up to three, but would cut a
frame short where it speeds back up, for a skipped moment instead of a held one.

How each guess does is counting, not a build: from a play's order of 2- and 3-VI frames, `tools/frame_lengths.mjs`
counts what each would hold and cut (`tools/frame_lengths.js`, a preload, logs them; docs/playing.md). For a run of L
frames of 3 VIs among frames of 2, with what RT64 knows ending a frame before the one it times, the fastest of three
(RT64's) holds min(L, 3) display frames and cuts one frame where L is 3 or more. The last frame's holds 1 and cuts 1
every run: worse alone (L 1), even at L 2, two judders fewer a run of 3 or more. The most common of the last three or
five is late at both ends of a run, holding going in and cutting coming out (Ruled out, measured). RT64 counts a
frame's VIs at the screen's swap to it (`pushFactor`) but picks the rate as the next frame's display list ends, so what
it knows may end two frames back; at that lag the last frame's holds min(L, 2) and cuts up to 2.

An RTX 5080 desktop doesn't show the case (its screen at 240 Hz; the pages from Pages, Jet Force Gemini's main 7f730ba
and Banjo-Tooie's e8df837; 1920x945, their play plans; plays.jsonl). Headless Chrome 155 there runs the screen's 240
animation frames, and Jet Force Gemini seldom takes 3 VIs: in two Chrome runs 260 of 5578 frames and 438 of 5462 (a
quiet host), in Firefox held at 60 (`layout.frame_rate`, the host 82% busy at the start) 160 of 5439, nearly all in
runs of 13-74 frames where the game runs at 20 for a second or so, the rest in nine runs of 1-6. Over each ~3.5 min
of play, at a lag of 1 and 2, the fastest of three would hold 8-35 display frames and cut 5-22 frames, the last
frame's hold 4-19 and cut 7-22, never fewer frames cut and at most 2 more: about 0.1 display frames a second, where
the laptop misses 1.6. Too few to tell the lag from the animation frames with no present, most of them the launcher's
and the loads'. Banjo-Tooie's plan's clock
(`0x80127638`, its time in seconds) isn't a count of VIs: times 60 it moves by 1 and 3 where 2 is expected (81 moves of
1, 87 lone 3s), and its other 3-VI frames came in three runs at 20 (118, 137 and 514 frames), where all three match
and nothing is held. Its own VI count is still to find.

So what decides the last frame's guess is the order of the frames where 10-27% take 3 VIs (a laptop, or a 60 Hz desktop
that shows it, as above): a play there with the preload, read by the simulator. Runs mostly of 3 frames or more make a
test build worth trying, to look at the motion; runs mostly of one put the guess in Ruled out beside the most common.

## Faults

`play_page.mjs --fault resize,hidden,audio,device,reload` (its header), played from Pages on an RTX 5080 (headless
Chrome 155 at a 240 Hz animation-frame clock, Firefox 158 off the desktop at 60-63), Mario Kart 64 mid-race and Star
Fox 64 mid-Corneria, each fault in turn in one visit, every run in plays.jsonl:

- A resized window (60% as wide and high for 10 s): both pages in both browsers drew at the new canvas size
  (754x387) and back, no error, the rate unchanged.
- A suspended AudioContext (10 s): the game ran on, and once resumed the sound came up short for a few seconds
  (201-1,304 frames) and then played as before.
- A lost WebGPU device (`device.destroy()`): in both browsers both pages froze on their last frame and said nothing
  but the console's `WebGPU device lost` (plume's `device.lost` only logs), and never asked for a new device. They
  still call `getCurrentTexture` each frame, so a count of presents doesn't show it: the screenshots do. A reload
  brought each back.
- A hidden tab (30 s) in Chrome: the pages presented ~60 a second while hidden, but Star Fox 64's sound came up
  3,000-7,000 frames short every 5 s, and back in front both presented below their rate before (60, then 89 against
  147; 60 for ~80 s against 114), until plume 08f9327 and rt64 52ec88f (A page in a hidden tab). Firefox played both
  through it unchanged.
- A reload over a warm cache and service worker: the plan's load steps (to "Device Name" and 6 s more) took 6.4 s
  against 7.7-8.8 s cold, and the first present came 0.4-0.6 s after the navigation against 1.8-3.1 s.

## Behind CLAUDE.md's rules

The measurements behind rules CLAUDE.md and the other docs state without them.

- `thread_stdio.js`: Emscripten proxies every write to stdout or stderr to the page's thread, WebGPU's, and waits, so
  each line held its thread for up to a frame. Banjo-Tooie's upstream logs ~100 lines a second: its title screen's sound
  was 12,900-13,400 frames short of ~2.1 million before, 235-1,325 with it.
- Banjo-Tooie's play plan, 2.5 s on W a world, ended black in all three of a laptop's runs, after Cauldron Keep's walk,
  where the page draws the keep in both browsers at every size tried: the walks took Banjo off Hailfire Peaks' and
  Cloud Cuckooland's ledges or through an exit, and in one Chrome run, once the game had begun a change of map of its
  own (its jigsaw wipe) in Hailfire Peaks, every world warped to after it drew black, though each warp reached its map.
  Its plan now visits ten worlds and doesn't walk (Banjo jumps and attacks where he lands), and its survey's warp waits
  for a change the game began.
- Holds in ms of the browser's time: a laptop's six Firefox runs of GoldenEye's plan (Pages v0.63.0) ended in other
  places than its two Chrome runs, by a curb and deep in a tunnel six shots on, where Dam drew ~20 presents a second,
  so the browsers' Dam numbers weren't of the same views. On a desktop GPU, Chrome and Firefox ended 1,600 units
  apart in Dam by that plan; on its clock (`g_GlobalTimer`, 60ths), every hold held the 3,624 ticks it asked for in
  both browsers, and four runs, two each, ended within 750 units of each other facing the same barriers (two Chrome
  runs alone, 250 apart). Chrome's CPU throttling (4) slowed none of the game: a play under it took as long.
- Six more plans on their games' clocks (Pages, a desktop GPU, shared turns): a Chrome and a Firefox run of each held
  within 3% of the ticks asked, and ended Banjo-Tooie 2 units apart, Jet Force Gemini 15 (a second Firefox run 6 from
  the first), DK64 60, Majora's Mask 50 and Conker 450. Majora's Mask's 9 s after its warp were still the browser's
  time: Firefox's Link stood at the gate through the first ten steps; on the clock from the warp, both browsers walked
  him by the same steps to within 2 units. Banjo's Spiral Mountain was the same to the unit in each run; Mumbo's
  Mountain, after a 4 s wait, walked three ways in three runs, two of them Chrome's, and its walk by the Ticker termites
  on the mountain's path still varies run to run in either browser (three runs, 670 units). A run's position read
  after every step (a copy of the plan, not committed) shows the step two runs part at.
- A loop of messages to itself in a page's script: Ocarina of Time's survey waited for the file select's hand-over with
  one (`MessageChannel`), ~10,000 tasks a second on the page's thread, none of them long. In Chrome they starved the
  tasks that carry the device thread's WebGPU work to it, and its page held 3-8 s as the file loaded, only while the
  loop ran, the thread looking free and the GPU process idle.
- Reading a ROM through fstreams (a few KB a call on Emscripten, each a round trip to the page's thread): Conker's
  ROM-version check held its launcher 0.85 s in Chrome and 2.3 s in Firefox.
- Emscripten's SDL2 audio, a ScriptProcessorNode on the page's thread taking 256 frames (5 ms) at a time: in headless
  Chrome 368 of 7541 callbacks came more than two buffers late in 40 s of attract demo.
- Off the desktop or on it, on a laptop's Intel UHD (A laptop, measured): on screen Firefox's pages took ~30 more points
  of the Intel chip's 3D engine (Banjo 75% against 45, Conker 72 against 44) and 3-5 times its GPU process's CPU, and
  Conker fell from 31.5 presents a second to 25.1, its boot's shader wait doubled (11.4 s against 5.4); Chrome stayed
  within 2. The stand-in is gentler than a laptop: Banjo played 59-60 on it in Firefox and 20-30 on the laptop, where
  its done callbacks came back 25-45 ms late and RT64's pacing held it to the game's frames.
- Chrome's CPU throttling of the page (CDP `Emulation.setCPUThrottlingRate`, 3) found plume 6949d22's calls: Conker's
  page at 36-44 presents a second under it, 54-58 after.
- Clicks scaled to `--size` instead of the page's viewport: at 945, Load ROM's click landed between Load ROM and
  Controls (an on-screen Chrome at 200% has a 1920x889 viewport for a `--size` of 1920x945).
- A click scaled to the viewport reaches no launcher's Load ROM that sits below a list growing by whole rows: Ocarina of
  Time's bar is 67-102 CSS pixels from the bottom at 1256x645, 75-126 at 1920x945 and 268-378 at 3840x2000, and its
  plan's click missed it at 1920x945 and 1920x889. Its plan presses Enter on the launcher's focused Load ROM instead (a
  `rom` step with a key, `page_driver.mjs`). And a click while Chrome builds the shader list behind the launcher, a
  laptop's Intel UHD at 99% on screen, was not taken (Wave Race 64's 100, done at 11.1 s), nor on an RTX 5080
  headless (Pilotwings 64's, the game never started): their plans wait for `RT64: all <n> prebuilt shaders built`.
  Firefox builds none there, so its misses on screen there have another cause, not yet seen.
- A debugging port shared by two browsers: the second Chrome took `[::1]` and the tool drove the first one's page, which
  is why `page_driver.mjs` refuses a port another browser holds.
- Firefox's `\GPU Process Memory(*)\Dedicated Usage` climbs by a canvas a frame, past a terabyte in 15 minutes, while
  the adapter's counter and nvidia-smi hold flat and the page plays on. Conker's page filling video memory in Firefox
  beside another page showed as the other page's climb and its "Out of Memory".
- A pair of runs before and after a build is not enough to call it slower: the retest on v0.58.0 played Pilotwings 64
  in Firefox uncapped at 175-192 presents a second against 201-211 for Pages played beside it, one run before and one
  after, a quiet host, and the page was held back. The next morning 19 runs interleaved over 18 minutes, Pages, a local
  build of v0.56.0 (the same bytes), v0.58.0 and each of its two changes alone, read 159-193 with no build below
  another: v0.56.0 171-173, Pages 162-171, v0.58.0 159-185, the worker pool alone 166-193, the held messages alone
  160-175 (all of them some 15% under the night before), and v0.58.0 was published. The same
  page moves by 10% between runs minutes apart and by more over hours, so a build is compared with several runs of the
  old one taken in the same minutes, never one pair.
- Build times: for Rush 2049 the build went from 590-810 s to 382 s with ccache, and 116 s with the fast link (its
  `CMakeLists.txt`). A first build of Banjo's page hit 71 of 754 compiles and Donkey Kong 64's 4 of 674 (Majora's
  Mask's 150 of 932, with the other two building beside it), and a second fresh dir of the same game 753, 673 and 932.
  Their builds went from ~2050-2100 s to 480-650 s, of which the link was 250-330 s; configure took 230-590 s either
  way. On a 16-core Linux host `tests/build`'s libraries build in 47 s, and in 5 s from a second fresh dir.

## Ruled out, measured

What CLAUDE.md's Ruled out rests on.

- The most common of a game's last three or five frames' VIs as RT64_UNEVEN_FRAME_RATES's guess at a frame's length,
  in place of the fastest of three: late at both ends of a run of 3-VI frames, at no run's length does it judder less.
  At a lag of 1 the most common of three holds min(L, 2) display frames and cuts 2 frames after a run of 2 or more,
  against the fastest of three's min(L, 3) and 1 (A game's uneven frames). On an RTX 5080 desktop's two plays of Jet
  Force Gemini (Chrome, Firefox) it would hold 17 and 5 and cut 19 and 11, the most common of five hold 25 and 7 and cut
  29 and 17, where the fastest of three holds 26 and 8 and cuts 9 and 5 (`tools/frame_lengths.mjs`).

- Presents waiting for the animation frame in every browser: on a laptop's Intel UHD, Chrome 155 headed drew as many
  (Banjo 59.9 against 60.0, Conker 53.9 against 54.0), but the GPU went 71 → 86% busy for Banjo and 63 → 75% for
  Conker, the browser 1.02 → 1.47 and 1.36 → 1.95 cores, and Banjo's gaps over 50 ms 98 → 188 in 90 s (one run each).
- Firefox's GPU process growth: on a test page submitting after each batch, empty submissions (~650 a second),
  onSubmittedWorkDone (~600), 4 KB writeBuffers (~1,200), textures made, written and destroyed (~160) and ~70 new
  pipelines grew it by nothing over 45-85 s each, and a 1920x945 canvas presenting 60 a second ~1 KB a present (Firefox
  158, RTX 2070). With no submission, writeBuffer and writeTexture grow it ~90 KB a call until one comes (the writes
  wait for the next submit).
- coi_serviceworker.js: in ~100 cold Firefox 158 visits register() always resolved with the worker still installing
  ("updatefound" never fired before the listener, the worker never already activating), and the reload always came.
- Pilotwings 64's frame gaps of 85-180 ms as its screens change (file menu, test overview, vehicle select, a test's
  start) come in Firefox too, and a CPU profile of every thread (Chrome 155 headless) puts the game thread in all of
  each one. Its screen change stops the music with `uvaSeqStop`, which polls until the sequence player has stopped:
  libultra stops it only after its voices' 50 ms release (`KILL_TIME`), counted in audio frames, one a retrace, so it
  holds 42-75 ms on a console and natively too. Then it loads the next screen (`uvLevelAppend`, `uvMemLoadDS`,
  `mio0_decompress`), 10-33 ms, the recompiled code ~1.7 times native's (`mio0_decompress` 347 MB/s in V8 against 580
  natively, clang 18 -O3). RT64 waits 4-21 ms for the new screen's texture uploads (the upload thread's new buffers and
  descriptor sets, made through the page's thread), and its wait for the count of changed pixels is gone (rt64
  254dee3). Right after the boot's wait in Chrome, on a busy host, gaps of 200-480 ms come with every page thread idle
  and the prebuild threads waiting for Chrome's GPU process; on a quiet host 3 cold runs of 4 had none.
- Chrome's list build behind the game: on v0.50.0 it cost Conker's page at 3840x2000 a little (57.0-57.9 presents a
  second against 58.7-58.8 with nothing built behind it, the low after its intro's second scene 50-56 against 58-59),
  and on rt64 c89ced0's present timeline nothing: no present dropped while it built, and the page drew 58.6-60.0 either
  way, 278-292 uncapped, the same dip to 55-57 at that scene with no build behind it (Chrome 155 headless, RTX 2070,
  cold, a host 7-37% busy).
- Firefox's pipelines in parallel: Rush 2049's 75 took 15.5-16.7 s from three devices at once against 13.3-14.6 from
  one (Firefox 158). The same 75 built five times in fresh profiles took as long each time.
- Rush 2049's and Majora's Mask's GPU frame (A page's GPU time): the pass breaks (a decal's read-only depth, plume's
  barriers), render to RAM's passes and the copies cost ~0.1 ms of a 4-7 ms present. Rush 2049 built with rt64
  008f380's loops, without them (re-spirv then spirv-opt), with either one alone, and with neither as dxc writes it
  presented 122-154 a second uncapped at 3840x2000 in Chrome 155, all five within the runs' noise (GPU 91-98% busy,
  interleaved, one server), and in Firefox 158 112 with them against 123 without, the race section's wait 4.5 s
  against 7.0. The mip LOD shader takes two levels of two tiles, four taps each, by hand; Auto's rounding to a multiple
  of 240 lines is 18-21% more pixels at 2000 lines, 3% at a laptop's 945.
- Conker's GPU frame in the web's own parts (A page's GPU time): every draw left out, its scene passes cost 0.09-0.2 ms
  of ~1.2, and the compute passes 0.05 ms. Auto's rounding is 48% more pixels at a laptop's 889 lines (5 times its 216).
- A DirectComposition overlay for Chrome's WebGPU canvas on Windows: Chromium has no path for one (WebGPU in Chrome and
  Firefox).
- A fixed heap: Conker's 3 GB measured no faster than memory growth.
- Firefox's misses built where the game pauses, or with the next section's wait (What the prebuilt lists miss): in
  long plays a 100 ms pause after a miss came for 5-6 of Banjo-Tooie's 27-29 and none of GoldenEye's 5-7, and the
  misses come after the list's last section.
- The present thread's wait() before its slot sleep, pace() leaving a try's first 0.5 s out of its count, or 3
  presents in flight, as what holds Banjo at 30 in Firefox on a laptop's screen: each paced to 30 as often as main, with
  the GPU 94-100% busy at 60 (A laptop, measured).
- wait()'s trips to the page's thread, or Firefox's late timed waits, as what paces Banjo to 30 on a laptop's screen:
  with plume bf417cf it paced to 30 in every default-prefs Firefox run, as before, and what decided 60 against 30 was
  what each present cost the GPU in Firefox's compositing, Windows' compositor included, and with DWM at 0% Banjo
  was paced to 30 all the same (A laptop, measured).
