#include "scriptinterface/Engine.h"
#include "scriptinterface/Context.h"
#include "scriptinterface/Interface.h"
#include "lib/path.h"
#include <cstdio>

int main()
{
    Script::Engine engine;
    auto context = std::make_shared<Script::Context>();
    Script::Interface interface("Engine", "wasm-headless", context);
    int result = 0;
    if (!interface.LoadGlobalScript(L"headless.js", "var phaseOneValue = 6 * 7;") ||
        !interface.Eval("phaseOneValue", result) || result != 42)
        return 1;
    context->ShrinkingGC();
    std::puts("0ad Script::Interface: result=42; GC passed");
    return 0;
}
