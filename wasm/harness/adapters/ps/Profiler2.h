#pragma once
// Headless profiling adapter; no simulation state or clock is replaced.
struct HeadlessProfiler {
  void RecordRegionEnter(const char*) {}
  void RecordRegionLeave() {}
  void RecordAttribute(const char*, ...) {}
};
inline HeadlessProfiler g_Profiler2;
#define PROFILE2(...) ((void)0)
#define PROFILE2_ATTR(...) ((void)0)
