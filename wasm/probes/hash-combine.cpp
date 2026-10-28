#include "lib/hash.h"
#include <cstdint>
#include <cstdio>

int main()
{
    struct Vector { std::size_t seed; std::uint32_t value; std::uint32_t expected; };
    const Vector vectors[] = {
        {0, 0, 0x9e3779b9u},
        {1, 0, 0x9e3779f8u},
        {0, 42, 0x9e3779e3u},
        {0, 0xffffffffu, 0x9e3779b8u}
    };
    for (const auto& vector : vectors)
    {
        auto seed = vector.seed;
        hash_combine(seed, vector.value); // implementación original, sin copiarla
        const auto result = static_cast<std::uint32_t>(seed);
        if (result != vector.expected)
            return 1;
        std::printf("%08x\n", static_cast<unsigned>(result));
    }
    std::puts("0ad-hash-combine: OK (low 32 bits, single combine)");
    return 0;
}
