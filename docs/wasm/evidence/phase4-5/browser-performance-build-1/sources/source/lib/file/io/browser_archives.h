/* Copyright (C) 2026 Wildfire Games. GPL-2.0-or-later. */
#ifndef INCLUDED_BROWSER_ARCHIVES
#define INCLUDED_BROWSER_ARCHIVES

#include <atomic>
#include <emscripten.h>
#include <emscripten/threading.h>

// -2 means an ordinary filesystem descriptor. Archive reads retain the
// original io::Operation offsets and decompression; only storage is external.
inline int ReadBrowserArchive(int fd, double position, void* destination, size_t length)
{
    alignas(4) std::atomic<int> ready{0};
    alignas(4) std::atomic<int> result{0};
    MAIN_THREAD_ASYNC_EM_ASM({
        const finish = value => {
            Atomics.store(HEAP32, $5 >>> 2, value | 0);
            Atomics.store(HEAP32, $4 >>> 2, 1); Atomics.notify(HEAP32, $4 >>> 2);
        };
        try {
            const archive = Module.FS.getStream($0)?.node.phase45Archive;
            if (archive === undefined) { finish(-2); return; }
            if (!Module.archiveService) throw new Error('Missing persistent archive service');
            Module.archiveService.readShared(archive, $1, HEAPU8.buffer, $2 >>> 0, $3 >>> 0, $4 >>> 0, $5 >>> 0);
        } catch (error) {
            Atomics.store(HEAP32, $4 >>> 2, 2); Atomics.notify(HEAP32, $4 >>> 2);
            err(error.stack || String(error)); abort(String(error));
        }
    }, fd, position, destination, length, &ready, &result);
    while (!ready.load())
    {
        emscripten_current_thread_process_queued_calls();
        emscripten_futex_wait(&ready, 0, 100);
    }
    return ready.load() == 1 ? result.load() : -1;
}

#endif
