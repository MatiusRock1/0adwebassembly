# Phase 4.6: advertising with Google AdSense and H5 Games Ads

Date: 2026-10-26. Status: planned, not started. Follows phase 4.5 and does not
replace or relax any of its gates. Apply the [performance and completion
contract](plan-cierre-0ad-webassembly.md): advertising must not reduce the
30 FPS lock achieved in phase 4.5.

Operator decision of 2026-10-26: monetize through advertising only, without
user accounts or a supporter tier for now. Ads appear only at natural breaks:
initial game load, match loading and match end. No ads during active play.

## Objective

Integrate Google AdSense display ads and the H5 Games Ads Ad Placement API into
the browser build so that:

1. **Initial load** (asset download and WASM startup) shows an H5 `preroll`
   and/or an AdSense display unit beside the progress indicator.
2. **Match loading** (the engine's `gui/loading` page) shows an AdSense display
   unit as an HTML overlay above the canvas.
3. **Match end** (transition to `gui/summary`) requests an H5 `next` interstitial
   ad break.

The game must remain fully playable when ads are blocked, refused, unfilled or
when the ad scripts fail to load.

## Constraints

- **Licensing and trademark.** The engine is GPL v2+ and assets are CC-BY-SA.
  Ads do not change those obligations: source for the deployed build stays
  public and attribution stays visible. Pages showing ads must not imply
  endorsement by Wildfire Games; show a non-affiliation notice.
- **AdSense policies.** No ads that imitate game UI, no encouragement to click,
  no accidental-click layouts, clear "Advertisement" labelling, no ads on
  pages without publisher content. H5 Games Ads requires a separate approval
  for the AdSense account; until approved, only test mode is used.
- **Consent.** Users in the EEA, UK and Switzerland require a Google-certified
  consent management platform (CMP). Use the AdSense "Privacy & messaging" CMP
  unless the operator chooses another certified CMP. Publish a privacy policy
  page and `ads.txt` at the domain root.
- **No ad code during matches.** Ad scripts, iframes and timers are removed
  from the DOM (not hidden) before the match simulation starts, and H5
  `adBreak` is never called during active play.
- **Generative assets.** No ad creatives, icons or UI graphics are produced by
  the agent ([AGENTS.md](../AGENTS.md)). Placeholders are plain CSS boxes with
  text.
- Local work only; no commits, commit messages, issues, PRs or automatic
  publication. Human review is required before deployment.

## Main technical risk: cross-origin isolation

The deployment sends `Cross-Origin-Opener-Policy: same-origin` and
`Cross-Origin-Embedder-Policy: require-corp`
([nginx.conf](../wasm/deploy/nginx.conf)) because WASM threads need
`SharedArrayBuffer`. Under `require-corp`, Google ad scripts and iframes are
expected to be blocked, and COOP may affect ad click-through windows. This must
be resolved first, through a spike, before any placement work:

1. Measure the behaviour of `adsbygoogle.js` and `adBreak` under the current
   headers in Chrome, recording console errors and blocked requests.
2. Evaluate `Cross-Origin-Embedder-Policy: credentialless`. Check whether ad
   iframes inserted by Google load; if not, check whether they can be marked
   `credentialless` (we do not control their creation, so this may fail).
3. Evaluate `Document-Isolation-Policy` (Chrome) as a replacement for
   COOP/COEP on the game document, verifying `crossOriginIsolated === true`,
   threads and WebGPU still work.
4. Fallback if none works: show the initial-load ad on a non-isolated loader
   page before navigating to the isolated game page, and treat in-game
   placements (match loading, match end) as blocked until a viable option
   exists. Report to the operator; do not weaken isolation silently.

Record header sets, Chrome version, `crossOriginIsolated`, thread startup and
ad load results in the evidence directory.

## Ordered work

1. **Isolation spike** (section above). Gate: a header configuration where the
   game keeps threads and WebGPU and at least one ad type loads in test mode.

2. **Ad host module.** Add `wasm/browser/application-ads.mjs`, owned by
   [application.mjs](../wasm/browser/application.mjs):
   - configuration from a deployment-time JSON or `data-` attributes:
     publisher ID, display slot IDs, `adsEnabled`, `testMode`; disabled by
     default so local benchmarks and tests run without ads;
   - lazy loading of `adsbygoogle.js` with `data-ad-client`,
     `data-adbreak-test="on"` in test mode and `data-ad-frequency-hint`;
   - `adConfig({ preloadAdBreaks: 'on', sound: 'on' })` and wrappers for
     `adBreak` with `beforeAd`/`afterAd`/`adBreakDone` callbacks;
   - a single timeout so that an unresponsive ad never blocks the game;
   - a no-op provider when disabled, blocked or unconsented, and a visible
     placeholder provider for manual layout review.

3. **Initial load placement.** In
   [application.html](../wasm/browser/application.html), add a labelled
   display slot next to `#loading`. Call `adBreak({ type: 'preroll' })` once
   per page load. The game continues loading in parallel; when it is ready,
   show a "Continue" control only if the ad has been visible for less than the
   chosen minimum (default 3 s). Remove the slot before entering the main menu.

4. **Engine → page bridge.** Add a narrow engine function callable from GUI
   scripts (for example `Engine.WebHostEvent(name)`) implemented with
   Emscripten `EM_JS`/`EM_ASYNC_JS`, a no-op in native builds. Events:
   `match-loading-start`, `match-loading-end`, `match-summary`. It carries no
   game state and must not affect simulation, RNG or replays. Call it from
   `binaries/data/mods/public/gui/loading/loading.js` and
   `binaries/data/mods/public/gui/summary/summary.js`.

5. **Match loading placement.** On `match-loading-start`, insert an AdSense
   display unit as an overlay above the canvas, outside the engine's GUI
   elements and clearly labelled. On `match-loading-end`, remove it from the
   DOM before the first simulation turn. The loading screen is not extended
   to show the ad.

6. **Match end placement.** On `match-summary`, call
   `adBreak({ type: 'next', name: 'match-end' })`. In `beforeAd`, mute game
   audio through the existing audio state and pause input to the canvas; in
   `afterAd`/`adBreakDone`, restore them. Skip the request when the match lasted
   less than 2 minutes. Google's own frequency capping decides whether an ad
   is shown; do not retry unfilled breaks.

7. **Consent, policy pages and deployment.** Configure the CMP, add the
   privacy policy and non-affiliation notice to
   [site/index.html](../wasm/deploy/site/index.html), serve `ads.txt`, and add
   the publisher configuration and chosen isolation headers to
   [nginx.conf](../wasm/deploy/nginx.conf), the
   [Dockerfile](../wasm/deploy/Dockerfile) context and
   [deploy README](../wasm/deploy/README.md). Keep ads disabled in the beta
   auth configuration unless the operator enables them.

8. **Performance verification.** Run
   [test-browser-performance.mjs](../wasm/scripts/test-browser-performance.mjs)
   with ads disabled and with ads enabled in test mode on the same build and
   workloads. During the measured match window there must be no ad iframes,
   ad scripts executing or ad timers. Results must stay within the phase 4.5
   gate (mean ≥ 29.5 displayed FPS, physical p95 ≤ two refreshes).

9. **Documentation.** Record results in `docs/wasm/phase-4-6-results.md` and
   evidence in `docs/wasm/evidence/phase4-6/`.

## Deliverables and acceptance

- [ ] Isolation spike documented; chosen header set keeps
      `crossOriginIsolated`, WASM threads and WebGPU working in Chrome.
- [ ] Ads disabled by default; enabling them requires explicit deployment
      configuration.
- [ ] Initial load: preroll and/or display unit in test mode, labelled, never
      delaying entry to the menu beyond the chosen minimum.
- [ ] Match loading: display overlay appears and is removed from the DOM before
      the match starts; loading time unchanged within measurement noise.
- [ ] Match end: `next` break requested once per qualifying match; audio muted
      and restored; summary and return to menu work afterwards.
- [ ] With an ad blocker, refused consent, script failure or no fill, the game
      loads and plays normally with no errors shown to the user.
- [ ] Native build unaffected; GUI bridge is a no-op outside the browser;
      checkpoints and command traces unchanged.
- [ ] Performance with ads enabled meets the phase 4.5 gate on the same
      workloads.
- [ ] CMP, privacy policy, non-affiliation notice and `ads.txt` deployed;
      AdSense policy checklist reviewed by the operator.
- [ ] Production publisher IDs enabled only after operator review and AdSense /
      H5 Games Ads approval.

## Operator decisions pending

- AdSense publisher ID, display slot IDs and H5 Games Ads approval status.
- CMP choice (default: AdSense Privacy & messaging).
- Minimum initial-load ad visibility (default 3 s) and minimum match length for
  the end-of-match break (default 2 minutes).
- Acceptance of the fallback if in-game placements cannot coexist with
  cross-origin isolation.

## Technical references

- [Ad Placement API (H5 Games Ads)](https://developers.google.com/ad-placement):
  `adConfig`, `adBreak`, placement types `preroll`, `start`, `pause`, `next`,
  `reward`, and test mode.
- [AdSense program policies](https://support.google.com/adsense/answer/48182).
- [COEP credentialless](https://developer.chrome.com/blog/coep-credentialless-origin-trial)
  and [Document-Isolation-Policy](https://developer.chrome.com/blog/document-isolation-policy).
- [Google consent requirements for the EEA, UK and Switzerland](https://support.google.com/adsense/answer/13554116).
