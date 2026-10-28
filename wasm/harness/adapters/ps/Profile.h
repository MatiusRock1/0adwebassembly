#pragma once
// Headless profiling adapter: measurements/UI are outside this harness.
struct CProfileManager {
  static bool IsInitialised() { return false; }
  void Start(const char*) {}
  void StartScript(const char*) {}
  void Stop() {}
};
inline CProfileManager g_Profiler;
#define PROFILE(...) ((void)0)
#define PROFILE3(...) ((void)0)
