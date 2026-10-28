# Continuation: isolated AI and turn pauses — 20 October 2026

**Resumed after the pause:** see the
[active continuation](phase-4-5-continuation-2026-10-20.md). The comparison
`ai-worker-parity-3` passed at both checkpoints; physical measurement in progress.
The
[resume point](phase-4-5-pause-2026-10-20.md) records the fixed package,
the complete sync checkpoints and the loss of Chrome before checking
threaded in the earlier attempt, kept as history.

**Phase open. Do not do reviews nor tests of the native game.** The
combined rAF candidate, `application-phase4-5-browser-perf-raf-1`, is kept,
measured earlier at 39.83 physical FPS /p95 50.12 ms. Presentation
improved, but it does not meet p95 ≤33.4 ms. See the
[rAF diagnostic](phase-4-5-worker-raf-2026-10-19.md).

## Profile of the rAF candidate

`evidence/phase4-5/cpu-profile-worker-raf-1/` keeps 17 CDP profiles,
original symbols, package hashes and `original-profile.txt`.
60 s of settling and 30 s of sampling were run, in fullscreen with
real focus; exit 0, without workers nor errors. There was no simultaneous PresentMon;
these times are not FPS nor exclusive CPU.

In `cpu-15.cpuprofile`, about 30.86 s sampled include 9.034768 s under
`CGame::Update`; 4.115273 s have `CAIWorker::PerformComputation` in the
same stack and 4.919495 s correspond to other update stacks.
The PBL interpreter adds up to 3.520244 s of self samples under Update and
5.926827 s inclusive. Inclusive times overlap; they are not summed.
This justifies studying the AI, without attributing all the stutter to it.

`profile-phase4-5.py` was adapted: it recognizes the remote backend and obtains its
real snapshots. It does not try to instrument `backend.call` in the window if
the commands run in the worker. `analyze-phase4-5-profile.py` now
includes samples filtered by the `CGame::Update` stack.

## AI experiment found and checks

On resuming, the changes to `CAIWorkerClient`, mailbox, snapshots,
deferred commands and the objects/link `application-ai-worker` /
`linked-ai-worker` already existed. They are kept separate from the measured rAF package.

The design creates a SpiderMonkey context on the actor's owning thread,
clones inputs and returns command batches with generation/sequence. The
queue reserves its original position and materializes the result before flush
or serialization. It does not voluntarily delay the commands to another turn.
The `sync` mode keeps the original access to the simulation; `isolated-sync`
allows isolating the contract without concurrency and `threaded` uses the actor.
No mode implies a new JIT.

Three Node snapshot cases passed: isolation of reads, technology
requirements and initialization effects. The CPU transport probe also passed:
thread owner, copied inputs, 200 ordered turns with
test RNG, errors, repeated materialization and shutdown. That probe is not
a native match nor does it demonstrate full determinism of the game.

## First runtime: real failure the harness did not detect

Package `application-phase4-5-ai-worker-1`; evidence
`evidence/phase4-5/cpu-profile-ai-worker-1/`. The match started in fullscreen,
18 profiles were captured and it exited with code 0, but the engine logged:

```text
"__aiWorkerEffects" is read-only
Failed to apply AI initialization effects
```

The earlier harness only rejected page/GPU errors and wrote
`passed=true`. **That result is a false positive of execution**, kept
unmodified. `post-run-audit.json` invalidates it explicitly. Do not adopt
package -1, nor interpret its profiles as a valid improvement.

The cause is concrete: `Script::SetProperty(..., true)` uses `constant=true`,
which defines a read-only/permanent property; the script then tries to
empty it. It was fixed to `false` in `CCmpAIManager.cpp`. The helper's test
also verifies the emptying and a second empty application without duplicating
effects. The three cases passed after that change.

The harness now captures `engineErrors` and rejects engine `ERROR:` lines, even
if the game continues and exits with code 0. The errors are re-evaluated when saving
the final result.

## Next verification

The diagnostic script now accepts `--ai-worker-mode` and
`--simulation-checkpoints`. For those checkpoints it uses the original
deterministic match of `parity_settings()`, without the benchmark's population
commands; it pauses at an exact time, saves the dump and the original save and extracts the
bytes of `simulation.dat`. It is a semantic check, not FPS acceptance nor
a comparison with the native executable.

Sync and threaded of the same fixed package will be compared at 10,000 and
30,000 ms. Match attributes, serialized bytes,
GUI state and non-local debug must match. Any divergence will be kept; do not relax
the contract to accept the migration as valid. These limited checkpoints
do not replace replay, save/load and full-match coverage either.

The AI fix was recompiled with `engine-ai-worker`, explicit VM
`portable-switch-o3`; `link-ai-worker` finished and
`application-phase4-5-ai-worker-2` was packaged separately. `ai-worker-parity-2/sync` saved both
checkpoints without errors and shut down cleanly; the threaded mode lost the
Chrome page during loading, before the first checkpoint. Cause unattributed.
The comparison remains failed/incomplete and there is no new approved physical AI
measurement. Keep the earlier packages and
evidence. No commits, messages, issues nor PRs were created;
human review before submitting changes to the project.
