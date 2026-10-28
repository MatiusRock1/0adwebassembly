// Platform-only inclusive timing of outer native-to-JS calls, not VM replacement.
#pragma once
#include <emscripten.h>
#ifndef WASM_SCENE_SCRIPT_TIMING_ENABLED
#define WASM_SCENE_SCRIPT_TIMING_ENABLED 0
#endif
#if WASM_SCENE_SCRIPT_TIMING_ENABLED
#define WASM_SCENE_SCRIPT_TIMING 1
#endif
namespace WasmSceneProfile {
inline thread_local unsigned scriptDepth=0;
inline thread_local double scriptStart=0, scriptMs=0;
struct ScriptCallTimer {
 ScriptCallTimer() { if constexpr (WASM_SCENE_SCRIPT_TIMING_ENABLED) { if (scriptDepth++==0) scriptStart=emscripten_get_now(); } }
 ~ScriptCallTimer() { if constexpr (WASM_SCENE_SCRIPT_TIMING_ENABLED) { if (--scriptDepth==0) scriptMs+=emscripten_get_now()-scriptStart; } }
 ScriptCallTimer(const ScriptCallTimer&)=delete;
 ScriptCallTimer& operator=(const ScriptCallTimer&)=delete;
};
}
