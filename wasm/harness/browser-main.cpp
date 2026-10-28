#include "ps/ThreadUtil.h"
#include <emscripten/threading.h>
#include <emscripten.h>
#include <cstdio>

int RunComponentFixture(int argc, char** argv);

int main(int argc, char** argv)
{
    // Engine main is the application pthread, distinct from the browser UI.
    if (emscripten_is_main_browser_thread())
    {
        std::fputs("Browser fixture must run on the application pthread\n", stderr);
        return 8;
    }
    Threading::SetMainThread();
    if (!Threading::IsMainThread())
        return 9;
    const int result = RunComponentFixture(argc, argv);
    EM_ASM({ out("0ad-browser-wasm-memory-bytes=" + wasmMemory.buffer.byteLength); });
    return result;
}
