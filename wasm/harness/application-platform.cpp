// Browser platform services for the original application. Game, GUI, logging,
// profiling, simulation and audio implementations remain the original engine.
#include "lib/debug.h"
#include "lib/sysdep/dir_watch.h"
#include "lib/sysdep/os_cpu.h"
#include "lib/sysdep/sysdep.h"
#include "lib/sysdep/vm.h"
#include "lib/utf8.h"
#include <emscripten.h>
#include <emscripten/heap.h>
#include <emscripten/threading.h>
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>

Status dir_watch_Add(const OsPath&, PDirWatch&) { return ERR::NOT_SUPPORTED; }
Status dir_watch_Poll(DirWatchNotifications&) { return ERR::NOT_SUPPORTED; }
void debug_break() { std::abort(); }
void debug_puts(const char* text) { std::fputs(text, stdout); std::fflush(stdout); }
Status debug_CaptureContext(void*) { return ERR::NOT_SUPPORTED; }
Status debug_DumpStack(wchar_t*, size_t, void*, const wchar_t*) { return ERR::NOT_SUPPORTED; }
Status debug_ResolveSymbol(void*, wchar_t*, wchar_t*, int*) { return ERR::NOT_SUPPORTED; }
void* debug_GetCaller(void*, const wchar_t*) { return nullptr; }
void debug_SetThreadName(const char*) {} // browser supplies worker identities
bool sys_IsDebuggerPresent() { return false; }
std::wstring sys_WideFromArgv(const char* value) { return wstring_from_utf8(value); }
void sys_display_msg(const wchar_t* caption, const wchar_t* text)
{
    std::fprintf(stderr, "%ls: %ls\n", caption, text);
}
ErrorReactionInternal sys_display_error(const wchar_t* text, size_t)
{
    std::fprintf(stderr, "%ls\n", text);
    std::abort(); // do not suppress fatal engine errors
}
Status sys_StatusDescription(int, wchar_t*, size_t) { return ERR::FAIL; }
Status sys_get_module_filename(void*, OsPath&) { return ERR::NOT_SUPPORTED; }
OsPath sys_ExecutablePathname() { return OsPath("/data/system/pyrogenesis"); }
std::wstring sys_get_user_name() { return L"Local player"; }
Status sys_pick_directory(OsPath&) { return ERR::NOT_SUPPORTED; }
Status sys_open_url(const std::string&) { return ERR::NOT_SUPPORTED; }
Status sys_get_proxy_config(const std::wstring&, std::wstring&) { return INFO::SKIPPED; }
size_t sys_max_sector_size() { return g_PageSize; }
FILE* sys_OpenFile(const OsPath& path, const char* mode) { return std::fopen(path.string8().c_str(), mode); }
Status sys_generate_random_bytes(std::uint8_t* buffer, size_t count)
{
    // Emscripten's /dev/urandom is backed by the browser's cryptographic RNG.
    // This service is not the deterministic simulation RNG.
    FILE* file = std::fopen("/dev/urandom", "rb");
    if (!file) return ERR::FAIL;
    const size_t read = std::fread(buffer, 1, count, file);
    std::fclose(file);
    return read == count ? INFO::OK : ERR::FAIL;
}
const char* cpu_IdentifierString() { return "WebAssembly; host CPU identity unavailable"; }
size_t os_cpu_NumProcessors() { return std::min<size_t>(emscripten_num_logical_cores(), os_cpu_MaxProcessors); }
uintptr_t os_cpu_ProcessorMask()
{
    const size_t count = os_cpu_NumProcessors();
    return count == os_cpu_MaxProcessors ? ~uintptr_t{0} : (uintptr_t{1} << count) - 1;
}
size_t os_cpu_PageSize() { return g_PageSize; }
size_t os_cpu_LargePageSize() { return 0; }
size_t os_cpu_QueryMemorySize()
{
    return MAIN_THREAD_EM_ASM_INT({ return navigator.deviceMemory ? navigator.deviceMemory * 1024 : 0; });
}
size_t os_cpu_MemoryAvailable() { return 0; } // browser does not expose host free RAM
uintptr_t os_cpu_SetThreadAffinityMask(uintptr_t) { return os_cpu_ProcessorMask(); }
Status os_cpu_CallByEachCPU(OsCpuCallback, uintptr_t) { return ERR::NOT_SUPPORTED; }

namespace vm
{
namespace
{
std::mutex allocationMutex;
std::map<uintptr_t, size_t> allocations;
bool Contains(uintptr_t address, size_t size)
{
    auto it = allocations.upper_bound(address);
    if (it == allocations.begin()) return false;
    --it;
    return address - it->first <= it->second && size <= it->second - (address - it->first);
}
}
void* ReserveAddressSpace(size_t size, size_t, PageType, int protection)
{
    if (!size || protection != (PROT_READ | PROT_WRITE)) return nullptr;
    void* pointer = nullptr;
    if (posix_memalign(&pointer, g_PageSize, size)) return nullptr;
    std::memset(pointer, 0, size);
    std::lock_guard lock(allocationMutex);
    allocations.emplace(reinterpret_cast<uintptr_t>(pointer), size);
    return pointer;
}
void ReleaseAddressSpace(void* pointer, size_t)
{
    std::lock_guard lock(allocationMutex);
    if (allocations.erase(reinterpret_cast<uintptr_t>(pointer))) std::free(pointer);
}
bool Commit(uintptr_t address, size_t size, PageType, int protection)
{
    std::lock_guard lock(allocationMutex);
    return protection == (PROT_READ | PROT_WRITE) && Contains(address, size);
}
bool Decommit(uintptr_t address, size_t size)
{
    std::lock_guard lock(allocationMutex);
    if (!Contains(address, size)) return false;
    std::memset(reinterpret_cast<void*>(address), 0, size);
    return true;
}
bool Protect(uintptr_t, size_t, int) { return false; }
void* Allocate(size_t size, PageType type, int protection)
{
    return ReserveAddressSpace(size, size, type, protection);
}
void Free(void* pointer, size_t size) { ReleaseAddressSpace(pointer, size); }
void BeginOnDemandCommits() {} // all linear memory is committed eagerly
void EndOnDemandCommits() {}
void DumpStatistics()
{
    std::lock_guard lock(allocationMutex);
    std::fprintf(stderr, "Browser VM: %zu retained allocations\n", allocations.size());
}
}
