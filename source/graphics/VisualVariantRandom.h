#pragma once

#include <cassert>
#include <cstdint>
#include <random>

// Match the Windows reference's full actor variation without relying on the
// implementation-defined std::uniform_int_distribution mapping in libc++.
// This is Lemire's multiply/reject interval algorithm for a full 32-bit engine,
// as used by MSVC STL 14.44. No simulation RNG or original art is changed.
namespace VisualVariantRandom
{
inline uint32_t Index(std::mt19937& generator, const uint32_t range)
{
    static_assert(std::mt19937::min() == 0 && std::mt19937::max() == UINT32_MAX);
    assert(range > 0);
    uint64_t product = uint64_t(generator()) * range;
    uint32_t remainder = uint32_t(product);
    if (remainder < range)
    {
        const uint32_t threshold = uint32_t(0 - range) % range;
        while (remainder < threshold)
        {
            product = uint64_t(generator()) * range;
            remainder = uint32_t(product);
        }
    }
    return uint32_t(product >> 32);
}
}
