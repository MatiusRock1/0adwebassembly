#include "graphics/VisualVariantRandom.h"
#include <array>
#include <cstdio>

int main()
{
    const std::array<uint32_t, 7> seeds{0,1,2,12345,54321,0x12345678,UINT32_MAX};
    const std::array<uint32_t, 10> ranges{1,2,3,7,31,100,200,1000,0x40000001,0x7fffffff};
    unsigned checks = 0;
    for (const uint32_t seed : seeds)
    {
        std::mt19937 reference(seed), portable(seed);
        for (unsigned iteration = 0; iteration < 1000; ++iteration)
            for (const uint32_t range : ranges)
            {
                const uint32_t expected = std::uniform_int_distribution<int>(0, int(range-1))(reference);
                const uint32_t actual = VisualVariantRandom::Index(portable,range);
                if (actual != expected)
                {
                    std::printf("FAIL seed=%u range=%u iteration=%u native=%u portable=%u\n",seed,range,iteration,expected,actual);
                    return 1;
                }
                ++checks;
            }
        if (reference() != portable()) return 2;
    }
    std::printf("PASS %u original MSVC distribution comparisons, including rejection and RNG consumption\n",checks);
}
