# 0 A.D. → WebAssembly — Phase 1: feasibility and headless build

> **Status:** technical plan, not yet executed.
> **Project objective:** port **the entire 0 A.D. game** to the browser, without rewriting it from scratch.
> **Scope of this phase:** demonstrate that a Pyrogenesis foundation can be built for WebAssembly and a real portion of simulation/scripting can run without a graphical interface. **This phase does not yet deliver a playable game.**

## 1. Desired result

At the end of phase 1 we must have:

1. A reproducible 0 A.D. checkout, pinned to a commit (`BASE_COMMIT`).
2. A **native Linux** build of the engine and its tests, as a baseline that must not break.
3. A verified inventory of dependencies, operating-system APIs and Emscripten blockers.
4. An experimental `pyrogenesis-wasm` target that generates at least a `.wasm` module and its startup JavaScript. **Compiling an isolated example is not equivalent to porting Pyrogenesis.**
5. A documented SpiderMonkey experiment: a real Emscripten build if viable; otherwise, a reproducible blocker and evaluated alternatives.
6. A *headless* test running real engine code (ideally scripting initialization and deterministic simulation advancement), with verifiable output.
7. Scripts and CI to repeat the results, plus a **GO / NO-GO / PIVOT** decision.

### Out of scope

WebGL/WebGPU rendering, window and full UI, audio, progressive asset downloads, match persistence and multiplayer. These will be addressed in later phases.

## 2. Implementation principles

- **Fork and minimal changes:** maintain an upstream that can be updated; avoid modifying game logic until inevitable.
- **Native baseline before WASM:** compare every WASM result with an equivalent native run.
- **Highest risk first:** SpiderMonkey and its `ScriptInterface` integration may be an architectural blocker.
- **Do not assume API equivalence:** sockets, threads, POSIX calls, dynamic loading and file paths require case-by-case validation.
- **Do not migrate the entire build prematurely:** a small experimental CMake build may be useful while Premake continues producing native binaries. Decide final Premake integration based on evidence.
- **Measure, do not guess:** record toolchain, commit, flags, commands, logs and execution time.

## 3. Recommended environment

Initial host: **Ubuntu Linux x86_64** (native or VM/WSL2). Plenty of free space (tens of GB) and enough RAM to compile large C++ dependencies are recommended; confirm actual usage during the build.

Base tools:

```bash
sudo apt update
sudo apt install -y \
  git git-lfs build-essential cmake ninja-build \
  python3 python3-venv pkg-config curl unzip zip \
  autoconf automake libtool

git lfs install
```

> The list of additional development packages for the **native 0 A.D. build** depends on the revision and distribution. Follow current dependencies in the official wiki before running scripts; the block above **is not a guaranteed complete list**.

### Install Emscripten

```bash
mkdir -p "$HOME/dev" && cd "$HOME/dev"
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk
./emsdk install latest
./emsdk activate latest
source ./emsdk_env.sh

emcc --version
em++ --version
emcmake --help
```

For reproducible builds, replace `latest` with a **specific tested tag** and record it in `docs/toolchain.md`. Each new terminal must run `source ~/dev/emsdk/emsdk_env.sh` (adjusting the path).

## 4. Step 1 — Obtain and pin the 0 A.D. code

```bash
cd "$HOME/dev"
git clone https://gitea.wildfiregames.com/0ad/0ad.git
cd 0ad
git lfs pull

git rev-parse HEAD | tee BASE_COMMIT.txt
git status --short
```

Create a fork on your preferred Git service and a working branch:

```bash
git switch -c feature/wasm-phase-1
```

**Checks:**

- Assets managed through Git LFS downloaded correctly.
- A full SHA hash exists in `BASE_COMMIT.txt`.
- The branch/tag, code license and third-party asset licenses are preserved.
- Do not mix upstream updates into experiments without recording a new baseline.

### Proposed structure for new files

```text
0ad/
├── wasm/
│   ├── CMakeLists.txt                  # experimental build, not yet implemented
│   ├── probes/
│   │   ├── smoke.cpp
│   │   └── spidermonkey/               # integration tests
│   ├── harness/                       # headless entry point
│   └── scripts/
│       ├── build-smoke.sh
│       └── run-smoke.sh
├── docs/wasm/
│   ├── dependencies.md
│   ├── toolchain.md
│   ├── compatibility-matrix.md
│   ├── spidermonkey-decision.md
│   └── phase-1-results.md
└── .github/workflows/wasm-smoke.yml   # if the fork uses GitHub
```

This is a **proposed structure**; it does not exist in the original repository until we create it.

## 5. Step 2 — Build and test the native version

From the checkout root:

```bash
./libraries/build-source-libs.sh -j"$(nproc)"
./build/workspaces/update-workspaces.sh -j"$(nproc)"
make -C build/workspaces/gcc -j"$(nproc)" config=release
```

> Adjust flags according to `--help` and the pinned commit's wiki. For CxxTest, system library or permission problems, consult official instructions and **do not** download arbitrary binaries to conceal errors.

Check available binaries:

```bash
ls -lh binaries/system/pyrogenesis binaries/system/test
```

Try the integrated tests:

```bash
./binaries/system/test
```

And run the native game if data is available:

```bash
./binaries/system/pyrogenesis
```

Record in `docs/wasm/phase-1-results.md`:

- OS and architecture, compiler and dependency versions.
- Commit SHA.
- Exact commands run and test results.
- Reproducible errors or warnings.
- How to start a minimal native simulation test for comparison.

**Exit criterion:** Linux build and relevant tests pass. Without a reliable baseline, do not start WASM integration.

## 6. Step 3 — Audit dependencies and coupling

Review at least these code areas, confirming their actual checkout paths:

| Area | Questions | Result to record |
|---|---|---|
| `source/scriptinterface` | Which SpiderMonkey APIs are called? Which version is used? | API and blocker matrix |
| `source/simulation2` | What is needed to advance a tick without rendering? | Minimal dependency graph |
| `source/ps` | Which services are global/mandatory? | Initializers to isolate |
| `source/lib` | What uses POSIX/Win32, threads, timers, files? | Adapter list |
| `source/network` | Can sockets be excluded from the headless build? | Flags/conditionals |
| `source/graphics` and `source/renderer` | Are there transitive graphics dependencies in simulation? | Possible exclusions |
| `libraries` and `build/workspaces` | How are libraries selected and targets generated? | Linking plan |

Reconnaissance commands (not a substitute for reading files):

```bash
find source -maxdepth 2 -type d | sort
find libraries -maxdepth 3 -type d | sort
rg -n 'SpiderMonkey|mozjs|JS_Init|JS_NewContext|ScriptInterface' source libraries build || true
rg -n '#include <(windows.h|pthread.h|sys/socket.h|dlfcn.h)>' source || true
rg -n 'dlopen|fork\(|socket\(|std::thread|pthread_' source || true
```

Install `ripgrep` (`sudo apt install ripgrep`) if unavailable.

### Mandatory classification

For each dependency: `NATIVA`, `PORTABLE`, `REQUIERE_SHIM`, `EXCLUIBLE_EN_HEADLESS` or `BLOQUEANTE` (native, portable, requires shim, excludable in headless, or blocking). Add version, location, license and a link to the error/test supporting the classification.

**Deliverable:** `docs/wasm/dependencies.md` and `compatibility-matrix.md`, not just a library list.

## 7. Step 4 — Test the Emscripten toolchain with minimal WASM

Before compiling Pyrogenesis, create `wasm/probes/smoke.cpp`:

```cpp
#include <cstdio>

int main() {
    std::puts("0ad-wasm: smoke OK");
    return 0;
}
```

Compile an artifact usable from both browser and Node.js (with a configured environment):

```bash
mkdir -p wasm/dist
em++ wasm/probes/smoke.cpp \
  -O0 -g \
  -sENVIRONMENT=web,node \
  -o wasm/dist/smoke.js
```

Test with Node.js, if installed:

```bash
node wasm/dist/smoke.js
```

Check that `smoke.js` and `smoke.wasm` exist and output includes `0ad-wasm: smoke OK`.

> This is exclusively an **Emscripten smoke test**, not a build of 0 A.D. code. From this point, add real sources and dependencies incrementally.

### Experimental modular build

1. Choose a self-contained game C++ utility that compiles without OS services.
2. Add real sources to the test target.
3. Build with `em++` and record which symbols prevent linking.
4. Introduce *stubs* only where legitimate (logging, clock, simulated files). Document every stub so it does not become a fake implementation of business logic.
5. Repeat until identifying the minimal dependency closure of `simulation2` and `scriptinterface`.

Do not create a target named `pyrogenesis-wasm` linking only `smoke.cpp` and present it as engine success: the deliverable name must match the code it actually includes.

## 8. Step 5 — Critical SpiderMonkey spike

**This is phase 1's highest-risk gate.** The game integrates simulation JavaScript through SpiderMonkey; do not promise that an alternative JS engine is a drop-in replacement.

### 8.1 Inventory

- Determine the exact SpiderMonkey version used by `BASE_COMMIT`.
- Identify the library build script inside `libraries/source/spidermonkey` (or its actual location).
- List build options, JIT dependencies, threading, GC, virtual memory and APIs unavailable in WASM.
- Count uses of `JS_*` APIs from `source/scriptinterface`.

### 8.2 Build experiment

Work in a copy or separate build directory. Attempt to configure and compile the **exact** SpiderMonkey version against Emscripten, starting with the most conservative options compatible with the project itself.

> **No fictitious command for compiling SpiderMonkey with `emconfigure` is provided here**: its configuration scripts vary by version and may reject wasm32. The required result is a reproducible script developed after inspecting the specific version.

### 8.3 Minimal functional test

If compilation succeeds, build a program that:

1. Initializes the runtime and a JS context.
2. Executes a simple expression or script.
3. Transfers data C++ → JS → C++.
4. Creates/destroys the context repeatedly without errors.
5. Passes a small real `ScriptInterface` test, if integration permits.

### 8.4 Decision if compilation fails

Evaluate with evidence and an impact estimate:

- **Option A:** minimal SpiderMonkey patches and disabling incompatible features, if technically sustainable.
- **Option B:** keep SpiderMonkey in an external service only as a temporary research tool; this **does not** satisfy the final objective of running the complete game locally in the browser.
- **Option C:** introduce an abstraction layer and investigate another JS runtime, recognizing the cost of adapting bindings, GC, serialization, determinism and game scripting.

**Gate:** a real JS/C++ integration test inside WASM, or a blocker report supporting `PIVOT / NO-GO`. Do not declare `GO` solely for compiling a static library.

## 9. Step 6 — Run a real headless simulation

Once viable scripting integration exists:

1. Build a `wasm/harness/main.cpp` entry point with minimal engine initialization.
2. Explicitly exclude audio, renderer, window and networking.
3. Mount only necessary script/configuration files through Emscripten FS for the first test.
4. Instantiate a minimal simulation using real `simulation2` APIs.
5. Load a deterministic unit or entity configuration/test.
6. Run **N ticks** with the same seed and controlled inputs.
7. Export a stable final-state summary (for example, entities/positions/resources) and calculate a hash.
8. Run the same scenario in the native binary; compare results and document floating-point, ordering and RNG divergences.

**Example protocol:**

```text
scenario: smoke-headless-01
seed: 12345
ticks: 100
expected: same canonical simulation state across native and wasm
```

Do not fix an expected hash until actually running both binaries and defining canonical state serialization.

### What counts as success

**Full success:** simulation ticks run through authentic 0 A.D. code, the involved script runs in WASM and the result matches the native baseline under a well-defined comparison.

**Partial success:** real modules compile or simple scripts run, but a tick is not yet completed. Label this as partial, not a completed phase.

## 10. Step 7 — Automate tests and preserve evidence

Recommended initial CI (GitHub Actions if the fork is on GitHub):

- Job `wasm-smoke`: install pinned emsdk, compile `smoke.cpp`, run with Node and save `.wasm`, `.js` and logs.
- Job `native-baseline`: build/test the game on a suitable runner; cache dependencies carefully to avoid masking changes.
- Job `spidermonkey-spike`: keep **experimental** until the process is reproducible.
- Job `headless-parity`: enable only when a real harness exists; compare native/WASM summaries.

Do not make a job mandatory when it is known to fail due to an unresolved limitation. Archive all errors alongside the commit, options and toolchain version.

## 11. Ordered work backlog

| ID | Task | Verifiable result | Priority |
|---|---|---|---|
| WASM-001 | Fork + commit pin + Git LFS | Clean checkout and saved SHA | P0 |
| WASM-002 | Native build and test baseline | Executed tests and log | P0 |
| WASM-003 | Dependency / OS call inventory | Matrix with blockers and sources | P0 |
| WASM-004 | Emscripten smoke test | `.wasm` executable under Node | P0 |
| WASM-005 | SpiderMonkey spike | JS/C++ WASM or reproducible blocker | P0 |
| WASM-006 | First real engine module in WASM | Build and test with 0 A.D. code | P1 |
| WASM-007 | Headless `simulation2` harness | Runs real ticks or records blocker | P1 |
| WASM-008 | Simulation parity | Documented native/WASM comparison | P1 |
| WASM-009 | CI and technical documentation | Reproducible pipeline and decisions | P1 |

Suggested dependency order:

```text
WASM-001 ─> WASM-002 ─┬─> WASM-003 ─> WASM-005 ─┐
                      └─> WASM-004 ─> WASM-006 ─┼─> WASM-007 ─> WASM-008
                                                └───────────────> WASM-009
```

## 12. Risks and mitigations

| Risk | Warning sign | Mitigation |
|---|---|---|
| SpiderMonkey does not support a useful wasm32 configuration | Configure/build or JS/GC runtime failure | Early spike; document A/B/C strategy |
| Cyclic dependencies between simulation and renderer | Linking pulls in GL/windows | Isolate interfaces and headless initialization |
| POSIX functions or dynamic loading | Unresolved symbols | Specific shims and subsystem exclusion |
| Nondeterministic behavior | Different native/WASM hashes | Fixed seed, tick logs and canonical serialization |
| Large asset volume | Excessive download or mounting | Use minimal dataset in phase 1 |
| Native platform regressions | Linux build/test fails after patches | Native CI and small commits |
| Hard-to-maintain fork | Patches too many core components | Adapters and upstream-friendly changes |

## 13. Definition of Done (DoD)

- [ ] Clean fork with documented upstream and fixed `BASE_COMMIT`.
- [ ] Reproducible native build and recorded tests.
- [ ] Complete inventory of dependencies and incompatible APIs for headless scope.
- [ ] Pinned Emscripten toolchain and automated smoke test.
- [ ] At least one **real** 0 A.D. module compiled to WASM and exercised in a test.
- [ ] SpiderMonkey spike resolved with an executable JS/C++ test, or **formal blocker with pivot decision**.
- [ ] Real simulation harness advancing ticks in WASM.
- [ ] Documented deterministic comparison with native baseline.
- [ ] Logs, scripts, artifacts and CI published in the fork.
- [ ] Architectural decision approved to start phase 2.

**Rule:** to declare **Phase 1 complete / GO**, all items must be satisfied, including real scripting and simulation. If there is a critical blocker, the valid result is a **partial feasibility report and change plan**, not false phase completion.

## 14. Final phase 1 delivery

A package containing:

```text
wasm/dist/                    # generated test binaries, not necessarily committed
wasm/harness/                 # executable harness
wasm/scripts/                 # reproducible commands
docs/wasm/dependencies.md
docs/wasm/compatibility-matrix.md
docs/wasm/spidermonkey-decision.md
docs/wasm/phase-1-results.md
docs/wasm/toolchain.md
```

The final report must answer with evidence:

1. What exact commit serves as the baseline?
2. What **real game code** compiles to WebAssembly today?
3. Does SpiderMonkey meet 0 A.D.'s requirements under WASM?
4. What actually runs (not just links)?
5. Is simulation determinism preserved?
6. Which dependencies block the next phase?
7. Is continuing with WebGL 2 recommended, or should part of the port be redesigned first?

## 15. Next phase (reference only)

**Phase 2:** browser bridge, Emscripten main loop, WebGL 2 renderer, keyboard/mouse input and minimal 3D scene. UI/audio/assets follow, and multiplayer comes last.

## References

- Official source code: https://gitea.wildfiregames.com/0ad/0ad
- Project build wiki: https://gitea.wildfiregames.com/0ad/0ad/wiki/BuildInstructions
- Emscripten SDK: https://emscripten.org/docs/getting_started/downloads.html
- Emscripten build system integration: https://emscripten.org/docs/compiling/Building-Projects.html
- Community guide with build commands (validate against the current commit): https://wildfiregames.com/forum/topic/123998-cxxtest-build-failed/

---

**Accuracy note:** native commands are based on the build flow documented by the community, but the plan does not claim they have been run or that SpiderMonkey is already compatible with Emscripten. The first real work is to verify the selected checkout and update instructions with reproducible results.
