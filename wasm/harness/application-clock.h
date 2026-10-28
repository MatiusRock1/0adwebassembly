#pragma once
// Browser display pacing for the original main loop. The engine remains on
// its pthread and retains every native stack owner until normal shutdown.
#include <emscripten.h>
#include <emscripten/threading.h>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <string>
#include <SDL.h>
#include "gui/CGUI.h"
#include "gui/GUIManager.h"
#include "scriptinterface/Interface.h"
#include "application-frame-time.h"
#if defined(WASM_PRESENT_PACING)
#include <algorithm>
#include <climits>
#include <cmath>
#include "ps/Game.h"
#include "simulation2/helpers/TurnTiming.h"
#include "application-present-pacing.h"
#endif

// Operator decision (2026-10-24): the web version renders at most this many
// frames per second, independently of the game's adaptivefps settings. The
// display signal advances its deadline by one interval per frame, so the rate
// holds without drift on 60 Hz and faster displays.
#ifndef WASM_FRAME_RATE_CAP
#define WASM_FRAME_RATE_CAP 30
#endif

#if defined(WASM_PRESENT_PACING)
// With present pacing, the frames up to and including the one that runs the
// next simulation turn, this many of them, may start while earlier frames still
// wait to be shown: the n-th frame before the turn while TURN_LEAD - n frames
// wait, at most MAX_LEAD. Each waiting frame gives the turn frame one more
// display interval, and those frames up to as much more latency. Every other
// frame starts when the previous one is shown.
#ifndef WASM_PRESENT_PACING_TURN_LEAD
#define WASM_PRESENT_PACING_TURN_LEAD 2
#endif
#ifndef WASM_PRESENT_PACING_MAX_LEAD
#define WASM_PRESENT_PACING_MAX_LEAD 1
#endif
#endif

namespace WasmApplication
{
alignas(4) inline std::atomic<int> frameReady{0};
inline std::atomic<int> requestState{0};
inline std::atomic<unsigned> mousePosition{0};
inline char requestCode[65536];
inline std::string requestResult;

class DisplayClock
{
public:
    DisplayClock()
    {
        frameTime.Reset();
        MAIN_THREAD_EM_ASM({
            const clock = ({ running: true, address: $0, deadline: 0, timeSource: 'monotonic-elapsed' });
            Module.applicationClock = clock;
            const signal = () => {
                Atomics.store(HEAP32, clock.address >> 2, 1);
                Atomics.notify(HEAP32, clock.address >> 2);
            };
            const frame = timestamp => {
                if (!clock.running) return;
                if (timestamp >= clock.deadline - 1) {
                    clock.deadline = Math.max(clock.deadline + 1000 / $1, timestamp);
                    signal();
                }
                clock.raf = requestAnimationFrame(frame);
            };
            clock.raf = requestAnimationFrame(frame);
            clock.hiddenTimer = setInterval(() => { if (document.hidden) signal(); }, 250);
        }, &frameReady, WASM_FRAME_RATE_CAP);
    }
    ~DisplayClock()
    {
        MAIN_THREAD_EM_ASM({
            const clock = Module.applicationClock;
            if (clock) {
                clock.running = false;
                cancelAnimationFrame(clock.raf);
                clearInterval(clock.hiddenTimer);
            }
        });
    }
    void Wait()
    {
        // Rendering can consume the entire display interval. Even when RAF
        // has already signalled, service SDL's callbacks queued to this pthread
        // before the original event pump runs on the next frame.
        emscripten_current_thread_process_queued_calls();
#if defined(WASM_PRESENT_PACING)
        const bool paced = WaitForPresent();
#else
        const bool paced = false;
#endif
        // A turn held for the threaded AI also waits for the next display signal:
        // starting it earlier would add a frame between two capped frames.
        while (!paced && !frameReady.exchange(0))
        {
            emscripten_current_thread_process_queued_calls();
            emscripten_futex_wait(&frameReady, 0, 250);
        }
        int x, y;
        SDL_GetMouseState(&x, &y);
        mousePosition.store((unsigned(x) & 65535) | ((unsigned(y) & 65535) << 16));
    }
#if defined(WASM_PRESENT_PACING)
private:
    // Frames until the simulation runs its next turn, at one cap interval of
    // real time per frame; INT_MAX while no turn can run.
    static int FramesUntilTurn()
    {
        if (!g_Game || !g_Game->IsGameStarted() || g_Game->m_Paused)
            return INT_MAX;
        const double step = PresentPacing::kIntervalMs / 1000.0 * g_Game->GetSimRate();
        if (!(step > 0))
            return INT_MAX;
        // A millisecond of margin keeps a frame at the boundary on the early side.
        const double remaining = -static_cast<double>(TurnTiming::deltaSimTime) - 0.001;
        return remaining <= step ? 1 : static_cast<int>(std::ceil(remaining / step));
    }
    // Starts the next frame from the render worker's paced presents: when the
    // previous frame has been shown, or, for the frames that lead up to a turn,
    // as soon as few enough frames still wait to be shown. Returns false, so
    // that the display signal paces the frame, until the worker has paced a
    // present, after a frame that presented nothing, and if presents stop.
    bool WaitForPresent()
    {
        namespace Pacing = PresentPacing;
        const int32_t submitted = Pacing::submitted;
        const bool presentedLastFrame = submitted != m_LastSubmitted;
        m_LastSubmitted = submitted;
        if (!presentedLastFrame || Pacing::block.presented.load() <= 0)
            return false;
        const int framesUntilTurn = FramesUntilTurn();
        const int32_t lead = framesUntilTurn > WASM_PRESENT_PACING_TURN_LEAD ? 0 :
            std::min(WASM_PRESENT_PACING_MAX_LEAD, WASM_PRESENT_PACING_TURN_LEAD + 1 - framesUntilTurn);
        const double start = emscripten_get_now();
        int32_t presented;
        while (submitted - (presented = Pacing::block.presented.load()) > lead)
        {
            // Hidden pages still present from the worker's 250 ms fallback.
            if (emscripten_get_now() - start > 1000)
                return false;
            emscripten_current_thread_process_queued_calls();
            emscripten_futex_wait(&Pacing::block.presented, presented, 50);
        }
        // A frame that starts while another waits is shown one interval after it.
        frameTime.SetNominal((Pacing::block.presentedAt[presented & 1] +
            (submitted - presented) * Pacing::kIntervalMs) / 1000.0);
        frameReady.store(0);
        return true;
    }
    int32_t m_LastSubmitted = 0;
#endif
};

inline void ProcessTestRequest()
{
    if (requestState.load() != 2 || !g_GUI || !g_GUI->GetActiveGUI()) return;
    std::string result;
    const bool success = g_GUI->GetActiveGUI()->GetScriptInterface()->Eval(requestCode, result);
    requestResult = success ? result : "SCRIPT_EVALUATION_FAILED";
    requestState.store(3);
}
}

// Test-only access goes through the real active GUI interface on the engine
// thread. It is unavailable unless the launcher explicitly enables automation.
extern "C" EMSCRIPTEN_KEEPALIVE int Phase4QueueScript(const char* code)
{
    if (!std::getenv("PHASE4_AUTOMATION") || !code || std::strlen(code) >= sizeof(WasmApplication::requestCode)) return 0;
    int empty = 0;
    if (!WasmApplication::requestState.compare_exchange_strong(empty, 1)) return 0;
    std::strcpy(WasmApplication::requestCode, code);
    WasmApplication::requestState.store(2);
    return 1;
}
extern "C" EMSCRIPTEN_KEEPALIVE const char* Phase4ScriptResult()
{
    return WasmApplication::requestState.load() == 3 ? WasmApplication::requestResult.c_str() : nullptr;
}
extern "C" EMSCRIPTEN_KEEPALIVE void Phase4ClearScriptResult()
{
    if (WasmApplication::requestState.load() == 3) WasmApplication::requestState.store(0);
}
extern "C" EMSCRIPTEN_KEEPALIVE void Phase4RequestClose()
{
    SDL_Event event{};
    event.type = SDL_QUIT;
    SDL_PushEvent(&event);
}
// Publish SDL's actual, clamped absolute position to the original cursor's
// browser overlay. Never read mutable SDL state from the browser thread.
extern "C" EMSCRIPTEN_KEEPALIVE unsigned Phase4MousePosition()
{
    return WasmApplication::mousePosition.load();
}
extern "C" EMSCRIPTEN_KEEPALIVE void Phase4Resize(int width, int height)
{
    if (width < 64 || height < 64 || width > 8192 || height > 8192) return;
    SDL_Event event{};
    event.type = SDL_WINDOWEVENT;
    // Distinguish framebuffer requests from SDL's CSS-sized browser events.
    event.window.event = 255;
    event.window.data1 = width;
    event.window.data2 = height;
    SDL_PushEvent(&event);
}
