"""Count only unsupported CacheIR dispatches in an isolated diagnostic VM."""


def instrument(source):
    assert 'Phase45MissingCacheIRCounts' not in source
    include='#include <algorithm>\n'
    assert source.count(include)==1
    source=source.replace(include,include+'#include <atomic>\n#include <emscripten.h>\n',1)
    marker='using namespace js::jit;\n'
    assert source.count(marker)==1
    counters=r'''
// Diagnostic only: atomics permit inspection from the browser thread while
// the original VM mutator runs. No handler, fallback, stack or GC rule changes.
static std::atomic<uint32_t> phase45MissingCacheIR[unsigned(CacheOp::NumOpcodes)]{};
static_assert(sizeof(std::atomic<uint32_t>) == 4);
extern "C" EMSCRIPTEN_KEEPALIVE uintptr_t Phase45MissingCacheIRCounts() {
  return reinterpret_cast<uintptr_t>(phase45MissingCacheIR);
}
extern "C" EMSCRIPTEN_KEEPALIVE unsigned Phase45MissingCacheIRSize() {
  return unsigned(CacheOp::NumOpcodes);
}
extern "C" EMSCRIPTEN_KEEPALIVE const char* Phase45MissingCacheIRName(unsigned op) {
#define PHASE45_CACHEIR_NAME(name, ...) #name,
  static constexpr const char* names[] = { CACHE_IR_OPS(PHASE45_CACHEIR_NAME) };
#undef PHASE45_CACHEIR_NAME
  static_assert(sizeof(names)/sizeof(names[0]) == unsigned(CacheOp::NumOpcodes));
  return op < unsigned(CacheOp::NumOpcodes) ? names[op] : "";
}
'''
    source=source.replace(marker,marker+counters,1)
    dispatch='    TRACE_PRINTF("unknown CacheOp: %s\\n", CacheIROpNames[int(cacheop)]);'
    assert source.count(dispatch)==1
    source=source.replace(dispatch,
        '    phase45MissingCacheIR[unsigned(cacheop)].fetch_add(1, std::memory_order_relaxed);\n'+dispatch,1)
    return source
