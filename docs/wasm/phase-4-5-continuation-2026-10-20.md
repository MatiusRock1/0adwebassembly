# Phase 4.5 continuation — 20 October 2026

The operator resumed after the 17:58 pause with "porfa sigue" ("please continue").
**Active work; phase open.** Do not review nor test the native game.
Resolution, quality, units, speed and original criteria are kept.
The [pause snapshot](phase-4-5-pause-2026-10-20.md) is historical; its
**32 hashes matched** on resuming.

## AI equivalence completed at two checkpoints

The incomplete comparison was repeated in a new destination:
`evidence/phase4-5/ai-worker-parity-3/`. The same package
`wasm/dist/application-phase4-5-ai-worker-2` ran in `sync` and
`threaded` modes. Both reached the exact checkpoints and exited with code 0,
without engine errors nor remaining workers/pthreads.

| Simulation time | Original serialization | Non-local debug | GUI state |
|---|---|---|---|
| 10,000 ms | Identical bytes | Matches | Matches |
| 30,000 ms | Identical bytes | Matches | Matches |

SHA-256 of `simulation.dat`, equal in both modes and in the earlier sync:

```text
10000: e35b3f94c701f74e20833f81cad68c754b659dd7240028cb1b9d77afd112020a
30000: b218d9a3887a14fb8e1f33f5c99204afdd24379cb4b5be1da4bb24701e20c737
```

`comparison.json` records `passed=true`, `phase45Accepted=false` and
`performanceAcceptance=false`. It is a limited state equivalence with the
original deterministic match; it does not cover a full match, replay or
later save/load. It does not use the native executable nor measure physical FPS.
The Chrome shutdown of the earlier attempt did not happen again; its cause
remains unattributed and that evidence is not overwritten.

## Physical measurement of the AI candidate

`evidence/phase4-5/performance-ai-worker-diagnostic-1/` was started with the same
fixed package and all the combined improvements. One skirmish repetition,
120 s of warmup and 120 s of measurement, real fullscreen, GPU probes
before the warmup and PresentMon. No screenshots, overlays, Computer Use,
compilers nor concurrent profiles. **It finished: 35.32 physical FPS /p95
66.83 ms**, 43.40 engine FPS /p95 59.75 ms and 67 physical pauses >100 ms.
Simulation 0.992667×, backlog 0, ETW without losses, no errors and a clean shutdown.
It does not fix performance. The [research of the 21st](phase-4-5-web-ports-research-2026-10-21.md)
records the later profile, the repositories consulted and the derived changes.

Earlier reference of the rAF set:
`application-phase4-5-browser-perf-raf-1`, 39.83 physical FPS /p95 50.12 ms.
Neither that result nor a short test replaces the p95 limits or the
full repetitions required to accept the phase.

```powershell
.\wasm\.venv-phase3\Scripts\python.exe wasm/scripts/verify-phase4-5-ai-parity.py --package wasm/dist/application-phase4-5-ai-worker-2 --output docs/wasm/evidence/phase4-5/ai-worker-parity-3
.\wasm\.venv-phase3\Scripts\python.exe wasm/scripts/benchmark-phase4-5-standalone.py --webgpu-directory wasm/dist/application-phase4-5-ai-worker-2 --backends webgpu --workloads skirmish --repetitions 1 --warmup-seconds 120 --duration-seconds 120 --upload-probe --output docs/wasm/evidence/phase4-5/performance-ai-worker-diagnostic-1
```

Keep the existing destinations; use other names to repeat. No
commits, commit messages, issues nor PRs were created. Human review needed
before submitting changes to the project.
