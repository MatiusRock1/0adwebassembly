# Web deployment

A container that serves a built browser package: the landing page at `/` and the
game at `/play/`. It does not build the game; the phase 4.5 pipeline does (see
`docs/wasm/phase-4-5-continuation-2026-10-25.md`).

The Docker launcher is temporarily restricted to **WebGL 2**. WebGPU is disabled
even for old `?renderer=webgpu` links and saved preferences. The experimental
backend remains in the development sources. Rebuild the context and image to apply this policy.

## Build and run

```text
python wasm/deploy/prepare-context.py --package wasm/dist/application-phase4-5-<name> --output wasm/build/deploy-context
docker build -t 0ad-wasm-web wasm/build/deploy-context
docker run --rm -p 8080:8080 0ad-wasm-web
```

Then open `http://localhost:8080/`. The context hard-links the package files when
the output is on the same volume, so preparing it does not copy the 2 GB archives.
The context retains the ZIP archives for uploading to the archive hosts, but `.dockerignore`
excludes `play/public.zip` and `play/mod.zip` from the Docker build context and
image layers. Debug symbols (`*.symbols`) are left out. At startup the container
writes `PUBLIC_ARCHIVE_URL` and `MOD_ARCHIVE_URL` (full HTTPS URLs of `public.zip`
and `mod.zip`) into the launcher pages (`<meta name="archive-public">` and
`<meta name="archive-mod">`), and the browser downloads the archives from those
hosts (see `ARCHIVE-HOSTS.md`); these per-archive URLs win over an `assets` query
parameter. The container refuses to
start if the package's launcher lacks those placeholders.

The main menu's Multiplayer button is disabled
(`binaries/data/mods/public/gui/pregame/MainMenuItems.js`): a browser cannot
open the network connections that multiplayer games use. The packaging script
ships that file loose next to the archives; the engine prefers it over the
older copy inside `public.zip`, so the change needs a new image but no new
archives on the archive hosts.

The launcher starts with low graphics settings (textures, shadows, water,
post-processing, models) when the browser reports an integrated, entry-level or
software GPU; settings saved in the in-game options take precedence. The page's
"Calidad gráfica" selector or `?graphics=auto|low|original` overrides the
choice (see `wasm/browser/application-graphics.mjs`). When the browser runs on an
integrated GPU, or renders in software, the page also shows a collapsed guide
with the steps for Windows, macOS and Linux to give the browser the dedicated
GPU or hardware acceleration; a page cannot choose the GPU itself.

To publish it, tag and push the image to a registry, for example
`docker tag 0ad-wasm-web <registry>/<user>/0ad-wasm-web:<version>` and
`docker push <registry>/<user>/0ad-wasm-web:<version>`.

## Requirements of the host

- **HTTPS.** The game uses threads, which need `SharedArrayBuffer`; browsers
  allow it only in a secure context (HTTPS, or `localhost`) that is cross-origin
  isolated. Put the container behind a TLS reverse proxy or a platform that
  terminates TLS.
- **Keep the isolation headers.** Every response must carry
  `Cross-Origin-Opener-Policy: same-origin` and
  `Cross-Origin-Embedder-Policy: require-corp`; `nginx.conf` sets them. A proxy
  or CDN in front must not drop them, and must pass `Range` requests and `206`
  responses through: the archives are read in blocks.
- **Do not let a CDN recompress or transform** `.zip` files.

## Licenses

0 A.D. is developed by Wildfire Games. Its code is GPL-2.0-or-later and its art
and audio CC BY-SA 3.0 (`LICENSE.md` gives the details per directory); the image
serves those texts under `/licenses/`. Publishing the build means distributing
GPL binaries, so the exact source used to build them, including every change in
this repository, must stay available: the landing page links to the
repository, which therefore has to contain those changes. The build also
includes third-party libraries (SpiderMonkey under MPL-2.0, and the Emscripten
ports of SDL2, zlib, libpng, FreeType, ICU, Ogg and Vorbis, with ENet,
libsodium and curl); their license texts should be added under `licenses/`
before a public release.

The landing page states that the port is unofficial and not endorsed by
Wildfire Games. It uses no 0 A.D. logo or other artwork.
