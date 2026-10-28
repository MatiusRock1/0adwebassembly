#pragma once
#include <cstdio>
#include <fmt/format.h>
// Terminal logging replaces the graphical logger in the headless harness.
struct CLogger {
  void WriteMessage(const char* message, bool = false) { std::puts(message); }
  void WriteWarning(const char* message) { std::fprintf(stderr, "WARNING: %s\n", message); }
  void WriteError(const char* message) { std::fprintf(stderr, "ERROR: %s\n", message); }
};
inline CLogger headlessLogger;
inline CLogger* g_Logger = &headlessLogger;
#define LOGMESSAGE(...) g_Logger->WriteMessage(fmt::format(__VA_ARGS__).c_str())
#define LOGMESSAGERENDER(...) LOGMESSAGE(__VA_ARGS__)
#define LOGWARNING(...) g_Logger->WriteWarning(fmt::format(__VA_ARGS__).c_str())
#define LOGERROR(...) g_Logger->WriteError(fmt::format(__VA_ARGS__).c_str())
