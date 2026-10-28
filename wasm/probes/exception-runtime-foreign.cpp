#include <cstdint>
extern "C" __attribute__((noinline)) uint32_t Phase45ForeignValue(uint32_t x)
{ return (x*1664525u+1013904223u)^((x>>7)|(x<<25)); }
extern "C" __attribute__((noinline)) void Phase45ForeignCall(void (*callback)())
{ callback(); }
