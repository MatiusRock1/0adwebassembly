// Browser platform services for the direct scene entry point.
// VFS content is immutable after preload; filesystem hotloading is unsupported.
#include "lib/sysdep/vm.h"
#include "lib/sysdep/dir_watch.h"
#include "lib/debug.h"
#include <cstdio>
#include "scriptinterface/Context.h"
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <memory>

// Original loop state stays inactive in the direct scene executable.
#include "tools/atlas/GameInterface/GameLoop.h"
static GameLoopState atlasState;
GameLoopState* g_AtlasGameLoop = &atlasState;
thread_local std::shared_ptr<Script::Context> g_ScriptContext;
void QuitEngine(int status) { std::exit(status); }
Status dir_watch_Add(const OsPath&, PDirWatch&) { return ERR::NOT_SUPPORTED; }
Status dir_watch_Poll(DirWatchNotifications&) { return ERR::NOT_SUPPORTED; }
Status debug_CaptureContext(void*) { return ERR::NOT_SUPPORTED; }
void debug_SetThreadName(const char*) {}
ErrorReaction debug_DisplayError(const wchar_t* description, size_t, void*,
    const wchar_t*, const wchar_t* file, int line, const char* func, std::atomic<bool>*)
{
    std::fprintf(stderr, "Engine error at %ls:%d (%s): %ls\n", file, line, func, description);
    std::abort();
}

namespace vm {
namespace {
std::mutex allocationsMutex;
std::map<uintptr_t, size_t> allocations;
bool Contains(uintptr_t address, size_t size)
{
    auto it = allocations.upper_bound(address);
    if (it == allocations.begin()) return false;
    --it;
    return address >= it->first && address - it->first <= it->second &&
        size <= it->second - (address - it->first);
}
}
// Linear memory cannot reserve inaccessible pages. Allocate the full region
// eagerly, retaining stable addresses and zero initialization for DynArray.
void* ReserveAddressSpace(size_t size, size_t, PageType, int prot)
{
    if (!size || prot != (PROT_READ | PROT_WRITE)) return nullptr;
    void* p = nullptr;
    if (posix_memalign(&p, g_PageSize, size)) return nullptr;
    std::memset(p, 0, size);
    std::lock_guard lock(allocationsMutex);
    allocations.emplace(reinterpret_cast<uintptr_t>(p), size);
    return p;
}
void ReleaseAddressSpace(void* p, size_t)
{
    std::lock_guard lock(allocationsMutex);
    if (allocations.erase(reinterpret_cast<uintptr_t>(p))) std::free(p);
}
bool Commit(uintptr_t address, size_t size, PageType, int prot)
{
    std::lock_guard lock(allocationsMutex);
    return prot == (PROT_READ | PROT_WRITE) && Contains(address, size);
}
bool Decommit(uintptr_t address, size_t size)
{
    std::lock_guard lock(allocationsMutex);
    if (!Contains(address, size)) return false;
    // No page reclamation/protection exists: clear the retained allocation.
    std::memset(reinterpret_cast<void*>(address), 0, size);
    return true;
}
bool Protect(uintptr_t, size_t, int) { return false; }
}
