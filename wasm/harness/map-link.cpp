// Integration probe for the complete facade and original component registry.
// It is deliberately separate from the verified component fixture.
#include "scriptinterface/Engine.h"
#include "scriptinterface/Context.h"
#include "simulation2/Simulation2.h"
#include "lib/file/vfs/vfs.h"
#include "ps/Filesystem.h"
#include "ps/ThreadUtil.h"
#include <memory>

int main()
{
    Threading::SetMainThread();
    Script::Engine engine;
    auto context = std::make_shared<Script::Context>();
    g_VFS = CreateVfs();
    {
        CSimulation2 simulation{nullptr, *context, nullptr, {}};
    }
    g_VFS.reset();
    return 0;
}
