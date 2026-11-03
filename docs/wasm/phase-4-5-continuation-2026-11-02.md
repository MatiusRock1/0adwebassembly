# Phase 4.5 — continuation of 2 November

`wasm/browser/application.mjs` now sets `JIT_OPTION_portableBaselineInterpreter=false`
before the engine starts, so the launcher runs SpiderMonkey's C++ interpreter instead
of the portable baseline interpreter (PBL). The engine binary does not change.

Why: the [intermittent crash](phase-4-5-continuation-2026-10-24.md#intermittent-crash-in-getpropirgeneratortryattachstub-open)
stays open in PBL. The Kingdoms and Mare Nostrum launchers have used this override
since 29 October. The plain 0 A.D. launcher did not, and a player reported
`memory access out of bounds` followed by `unreachable` during a match. The analysis
and what it does not establish are in `Risk-Demo/evidence/engine-crashes.md` of the
DemosGames repository.

Effect on this repository's measurements: every performance result in these documents
was taken with PBL, so a new run is not comparable with them. `skirmish` and `combat`
have not been measured again with the C++ interpreter. To compare, remove that line
from the launcher. PBL's defect itself is not fixed.
