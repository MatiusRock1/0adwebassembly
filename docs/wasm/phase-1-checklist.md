> Scope update, 2026-10-11: the operator asks to continue exclusively locally, without commits or publication. The phase 1 technical test passed and allows the phase 2 plan to start. The publication/remote CI requirements mentioned below belong to the earlier scope and do not block local work. The review before submission only applies if it is later decided to submit changes. Current plan: [Phase 2](../../plan/plan-fase-2-0ad-webassembly.md).

# Phase 1 closure: operator review

Date: 2026-10-11. The local technical check passes. The plan requires publication and approval before declaring the phase complete.

| DoD item | Status and evidence |
|---|---|
| Clean fork and pin | Pin documented and Linux checkout validated. Windows checkout pending review: index missing, empty index.lock; not modified to avoid discarding work. |
| Native baseline | 472 tests OK; evidence/native-tests.log. |
| Dependencies and APIs in scope | dependencies.md and compatibility-matrix.md; adapters documented. |
| Toolchain and smoke | Emscripten 4.0.10 pinned; smoke and CMake scripts. |
| Real WASM module | hash_combine and the original scripting/simulation2 executed. |
| SpiderMonkey | Original JS/C++, GC and repeated contexts OK; integration with ScriptInterface and JobQueue OK. |
| Real ticks | 100 calls to the original kernel CSimulation2Impl::UpdateComponents; native and upstream JS component. |
| Deterministic parity | PARITY_PASSED; four exit codes 0 and identical JSON; evidence/spidermonkey/parity. |
| Publication and CI | Scripts, workflow and local artifacts prepared. Publication and remote execution pending. |
| Approved decision | Technical recommendation to continue with SpiderMonkey; human approval pending. |

The exported WASM binary also ran with Node on Windows, with exit code 0 and the same state. Every hash in wasm/dist/headless/SHA256SUMS was verified. Approximate package size: 27.5 MB. The __syscall_madvise warning persists and is recorded as a limitation; it does not invalidate the comparison of the verified scenario.

Concrete review: wasm/CMakeLists.txt, wasm/harness, wasm/scripts, wasm/docker/spidermonkey.Dockerfile, .gitea/workflows/wasm-phase1.yml and docs/wasm. Confirm that the scenario's scope meets the decision to move on; review the kernel adapter that includes Simulation2.cpp and the experimental SpiderMonkey/Rust patches.

AGENTS.md, rules 4 and 7: the agent does not create commits and changes must be reviewed by the operator before being submitted. That is why publishing the fork is up to the operator. After review: prepare the Windows checkout without losing changes, publish, run the manual workflow on a Linux runner with Docker and a persistent cache, and record the architectural approval. The DoD is not marked complete before those actions.
