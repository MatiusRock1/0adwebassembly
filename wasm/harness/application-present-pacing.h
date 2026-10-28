#pragma once
// Optional browser candidate (WASM_PRESENT_PACING): display pacing driven by
// the render worker's presents. The worker shows at most one engine frame per
// cap interval, holds a frame that is ready early until the display signal of
// its interval, and publishes every paced present here. The engine frame clock
// (application-clock.h) starts frames from those presents, so that a frame is
// shown every second refresh on a 60 Hz display instead of on fixed 30 FPS
// slots that a late turn frame misses. Only wall-clock timing changes.
#include <atomic>
#include <cstdint>

// Operator decision (2026-10-24): the web version renders at most this many
// frames per second, independently of the game's adaptivefps settings.
#ifndef WASM_FRAME_RATE_CAP
#define WASM_FRAME_RATE_CAP 30
#endif

namespace WasmApplication::PresentPacing
{
inline constexpr double kIntervalMs = 1000.0 / WASM_FRAME_RATE_CAP;

// Shared with the render worker, which receives its address with each present.
struct alignas(8) Block
{
    // Paced presents so far; the worker stores it last and notifies it.
    alignas(4) std::atomic<int32_t> presented{0};
    int32_t reserved{0};
    // Display signal time of present n in milliseconds of the worker's clock,
    // at presentedAt[n & 1]. The worker writes the other slot before it
    // publishes the next count, so a reader never sees a slot being written.
    double presentedAt[2]{0, 0};
};
inline Block block;

// Engine thread only: paced presents dispatched to the render worker.
inline int32_t submitted = 0;
}
