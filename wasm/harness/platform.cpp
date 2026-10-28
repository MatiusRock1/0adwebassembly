#include "lib/debug.h"
#include "ps/ThreadUtil.h"
#include <cstdio>
#include <cstdlib>
#include <cstdarg>
#include <pthread.h>

// Assertions stay fatal, without a graphical assertion dialog.
void debug_break() { std::abort(); }
ErrorReaction debug_OnAssertionFailure(const wchar_t* expr, std::atomic<bool>*,
    const wchar_t* file, int line, const char* func) {
  std::fprintf(stderr, "Assertion at %ls:%d (%s): %ls\n", file, line, func, expr);
  std::abort();
}
ErrorReaction debug_OnError(Status status, std::atomic<bool>*, const wchar_t* file,
    int line, const char* func) {
  std::fprintf(stderr, "Status %lld at %ls:%d (%s)\n", static_cast<long long>(status), file, line, func);
  std::abort();
}
void debug_printf(const char* format, ...) {
  va_list args;
  va_start(args, format);
  std::vfprintf(stderr, format, args);
  va_end(args);
}
namespace Threading {
static pthread_t mainThread = pthread_self();
bool IsMainThread() { return pthread_equal(mainThread, pthread_self()); }
void SetMainThread() { mainThread = pthread_self(); }
}
