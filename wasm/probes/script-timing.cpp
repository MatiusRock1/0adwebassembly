#include "scene-script-timing.h"
#include <cassert>
#include <iostream>
static unsigned reads = 0;
double emscripten_get_now() { return ++reads; }
int main()
{
    {
        WasmSceneProfile::ScriptCallTimer outer;
        { WasmSceneProfile::ScriptCallTimer inner; }
    }
    assert(WasmSceneProfile::scriptDepth == 0);
#if WASM_SCENE_SCRIPT_TIMING_ENABLED
    assert(reads == 2 && WasmSceneProfile::scriptMs == 1);
#else
    assert(reads == 0 && WasmSceneProfile::scriptMs == 0);
#endif
    std::cout << "{\"enabled\":" << WASM_SCENE_SCRIPT_TIMING_ENABLED
        << ",\"clockReads\":" << reads << ",\"passed\":true}\n";
}
