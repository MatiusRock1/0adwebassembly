#pragma once
#include <utility>

namespace WasmApplication
{
// The original renderer thread owns this work. WebGPU runs the frame's audio
// maintenance after CPU recording, before posting GPU commands. Other backends
// retain immediate execution; the main loop runs any pending fallback when no
// render pass is produced (for example, while minimized).
inline bool deferAudioIdle = false;
inline void (*pendingAudioIdle)() = nullptr;

inline void RunDeferredAudioIdle()
{
    const auto work = std::exchange(pendingAudioIdle,nullptr);
    if (work) work();
}

inline void ScheduleAudioIdle(void (*work)())
{
    if (!deferAudioIdle) { work(); return; }
    // Preserve every scheduled update, even if a caller schedules twice.
    RunDeferredAudioIdle();
    pendingAudioIdle = work;
}
}
