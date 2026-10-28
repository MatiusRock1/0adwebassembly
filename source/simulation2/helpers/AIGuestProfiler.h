/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
// Diagnostic only. Cooperative interrupt samples identify guest source lines;
// they are not CPU timers and must never certify a performance capture.
#include <atomic>
#include <algorithm>
#include <memory>
#include <stdexcept>
#include <string>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <sstream>
#include <thread>
#include <unordered_map>
#include <js/CharacterEncoding.h>
#include <js/Interrupt.h>
#include <js/Stack.h>
#include <jsapi.h>
#include <emscripten.h>

namespace AIGuestSampling
{
struct Slot
{
    std::atomic<unsigned> ready{0}, hits{0};
    char filename[192]{};
    uint32_t line = 0;
};
inline Slot slots[512];
inline std::atomic<unsigned> next{0}, requests{0}, noCaller{0}, overflow{0}, late{0};
// A request made while C++ runs is only serviced at the next guest checkpoint,
// which attributes that C++ time to whatever guest code follows. When set,
// samples serviced later than this are dropped (counted as late); 0 keeps all.
#ifndef AI_GUEST_MAX_DELAY_US
#define AI_GUEST_MAX_DELAY_US 0
#endif
inline constexpr long long kMaxDelayUs = AI_GUEST_MAX_DELAY_US;
inline std::atomic<long long> requestedAtUs{0};
inline long long NowUs()
{
    return std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

// Short guest stacks per computation, merged at its end into the table of slow
// computations (>= kSlowMs) or of the others. Capturing allocates SavedFrames,
// which may shift GC timing; this build is diagnostic only.
#ifndef AI_GUEST_SLOW_MS
#define AI_GUEST_SLOW_MS 150
#endif
#ifndef AI_GUEST_PERIOD_MS
#define AI_GUEST_PERIOD_MS 10
#endif
inline constexpr double kSlowMs = AI_GUEST_SLOW_MS;
inline constexpr int kPeriodMs = AI_GUEST_PERIOD_MS;
inline constexpr uint32_t kStackFrames = 6;
inline std::mutex stacksMutex;
inline std::unordered_map<std::string, unsigned> slowStacks, otherStacks;
inline unsigned slowComputations = 0, otherComputations = 0;
inline double slowMilliseconds = 0, otherMilliseconds = 0;
inline thread_local std::unordered_map<std::string, unsigned> currentStacks;
// Wall time inside the current computation that waited on another thread
// (e.g. the threaded AI result barrier); excluded from the slow threshold.
inline thread_local double excludedMs = 0;

inline std::string ShortStack(JSContext* cx)
{
    JS::RootedObject stack(cx);
    JS::RootedString text(cx);
    if (!JS::CaptureCurrentStack(cx, &stack, JS::StackCapture(JS::MaxFrames(kStackFrames))) ||
        !JS::BuildStackString(cx, nullptr, stack, &text))
    {
        JS_ClearPendingException(cx);
        return {};
    }
    JS::UniqueChars utf8 = JS_EncodeStringToUTF8(cx, text);
    if (!utf8) { JS_ClearPendingException(cx); return {}; }
    // Each frame is "name@file:line:column"; drop the column so samples on the
    // same line aggregate, and join frames with " < ".
    std::istringstream lines(utf8.get());
    std::string frame, out;
    while (std::getline(lines, frame))
    {
        const std::size_t colon = frame.rfind(':');
        if (colon != std::string::npos && frame.find_first_not_of("0123456789", colon + 1) == std::string::npos)
            frame.resize(colon);
        if (frame.empty()) continue;
        if (!out.empty()) out += " < ";
        out += frame;
    }
    return out;
}

class Profiler
{
    inline static thread_local Profiler* current = nullptr;
    JSContext* cx;
    std::atomic<bool> computing{false}, requested{false};
    std::mutex mutex;
    std::condition_variable wake;
    bool stop = false, inCallback = false;
    std::thread sampler;
    static bool Interrupt(JSContext* cx)
    {
        auto* self = current;
        if (!self || self->inCallback || !self->requested.exchange(false) || !self->computing.load()) return true;
        if (kMaxDelayUs > 0 && NowUs() - requestedAtUs.load() > kMaxDelayUs) { ++late; return true; }
        self->inCallback = true;
        JS::AutoFilename filename;
        uint32_t line = 0;
        if (!JS::DescribeScriptedCaller(cx, &filename, &line) || !filename.get()) ++noCaller;
        else
        {
            const auto count = std::min(next.load(), 512u);
            unsigned index = 0;
            for (; index < count; ++index)
                if (slots[index].ready.load(std::memory_order_acquire) && slots[index].line == line &&
                    std::strncmp(slots[index].filename, filename.get(), sizeof(slots[index].filename)-1) == 0) break;
            if (index == count)
            {
                index = next.fetch_add(1);
                if (index < 512)
                {
                    std::snprintf(slots[index].filename, sizeof(slots[index].filename), "%s", filename.get());
                    slots[index].line = line;
                    slots[index].ready.store(1, std::memory_order_release);
                }
            }
            if (index < 512) ++slots[index].hits;
            else ++overflow;
            const std::string stack = ShortStack(cx);
            if (!stack.empty()) ++currentStacks[stack];
        }
        self->inCallback = false;
        return true;
    }
public:
    explicit Profiler(JSContext* context) : cx(context)
    {
        if (!JS_AddInterruptCallback(cx, Interrupt)) throw std::runtime_error("AI guest profiler registration failed");
        sampler = std::thread([this] {
            std::unique_lock lock(mutex);
            while (!wake.wait_for(lock, std::chrono::milliseconds(kPeriodMs), [this] { return stop; }))
                if (computing.load()) { ++requests; requestedAtUs.store(NowUs()); requested.store(true); JS_RequestInterruptCallback(cx); }
        });
        current = this;
    }
    ~Profiler()
    {
        { std::lock_guard lock(mutex); stop = true; }
        wake.notify_one(); sampler.join(); current = nullptr;
    }
    struct Computing
    {
        std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
        Computing() { currentStacks.clear(); excludedMs = 0; if (current) current->computing.store(true); }
        ~Computing()
        {
            if (current) current->computing.store(false);
            const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count() - excludedMs;
            std::lock_guard lock(stacksMutex);
            const bool slow = ms >= kSlowMs;
            auto& table = slow ? slowStacks : otherStacks;
            (slow ? slowComputations : otherComputations) += 1;
            (slow ? slowMilliseconds : otherMilliseconds) += ms;
            for (const auto& [stack, hits] : currentStacks) table[stack] += hits;
            currentStacks.clear();
        }
    };
};
inline thread_local std::unique_ptr<Profiler> owner;
}

// inline: the simulation profile includes this header from two units.
extern "C" EMSCRIPTEN_KEEPALIVE inline const char* Phase45AIGuestProfile()
{
    // Only read published immutable keys and atomic counters; never wait for
    // the actor or touch its context from the browser thread.
    using namespace AIGuestSampling;
    static std::string result;
    std::ostringstream out;
    out << "{\"diagnosticOnly\":true,\"periodMs\":" << kPeriodMs << ",\"requests\":" << requests.load()
        << ",\"noCaller\":" << noCaller.load() << ",\"overflow\":" << overflow.load()
        << ",\"late\":" << late.load() << ",\"maxDelayUs\":" << kMaxDelayUs << ",\"samples\":[";
    bool first = true;
    for (unsigned i=0; i<std::min(next.load(),512u); ++i)
    {
        const auto& slot = slots[i];
        if (!slot.ready.load(std::memory_order_acquire)) continue;
        if (!first) out << ',';
        first = false;
        out << "{\"file\":\"";
        for (const unsigned char* c = reinterpret_cast<const unsigned char*>(slot.filename); *c; ++c)
        {
            if (*c == '"' || *c == '\\') out << '\\';
            if (*c < 32) out << '?'; else out << char(*c);
        }
        out << "\",\"line\":" << slot.line << ",\"hits\":" << slot.hits.load() << '}';
    }
    const auto escape = [&out](const std::string& text) {
        for (const unsigned char c : text)
        {
            if (c == '"' || c == '\\') out << '\\';
            if (c < 32) out << '?'; else out << char(c);
        }
    };
    const auto table = [&](const char* name, const std::unordered_map<std::string, unsigned>& stacks) {
        out << ",\"" << name << "\":[";
        bool firstStack = true;
        for (const auto& [stack, hits] : stacks)
        {
            if (!firstStack) out << ',';
            firstStack = false;
            out << "{\"stack\":\"";
            escape(stack);
            out << "\",\"hits\":" << hits << '}';
        }
        out << ']';
    };
    out << ']';
    {
        std::lock_guard lock(stacksMutex);
        out << ",\"slowThresholdMs\":" << kSlowMs << ",\"slowComputations\":" << slowComputations
            << ",\"slowMilliseconds\":" << slowMilliseconds << ",\"otherComputations\":" << otherComputations
            << ",\"otherMilliseconds\":" << otherMilliseconds;
        table("slowStacks", slowStacks);
        table("otherStacks", otherStacks);
    }
    out << '}'; result = out.str(); return result.c_str();
}
