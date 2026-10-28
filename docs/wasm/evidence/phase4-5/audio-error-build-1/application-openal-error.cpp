// Shared platform state; audio and its context remain in the SDK/browser.
#include <atomic>
#include <cstdint>
#include <emscripten.h>

namespace
{
alignas(4) std::atomic<int32_t> openALError{0};
}

extern "C" EMSCRIPTEN_KEEPALIVE uintptr_t Phase45OpenALErrorAddress()
{
    return reinterpret_cast<uintptr_t>(&openALError);
}
