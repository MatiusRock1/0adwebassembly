#include "scriptinterface/Engine.h"
#include "scriptinterface/Context.h"
#include "simulation2/system/ComponentManager.h"
#include "simulation2/system/SimContext.h"
#include "simulation2/components/ICmpTest.h"
#include "simulation2/MessageTypes.h"
#include "lib/path.h"
#include <fstream>
#include <sstream>
#include <cstdio>

void HeadlessUpdateComponents(CSimContext&, fixed);

int RunComponentFixture(int argc, char** argv)
{
    std::ifstream input(argc > 1 ? argv[1] : "/scenario/test.js");
    if (!input) return 1;
    std::stringstream text;
    text << input.rdbuf();
    Script::Engine engine;
    auto context = std::make_shared<Script::Context>();
    CSimContext simContext;
    CComponentManager manager(simContext, *context);
    manager.SetRNGSeed(12345);
    manager.LoadComponentTypes();
    if (!manager.GetScriptInterface().LoadScript(L"simulation/components/test.js", text.str()))
        return 2;
    if (!manager.GetScriptInterface().LoadGlobalScript(L"promise-probe.js",
        "var promiseProbe = 0; Promise.resolve(9).then(v => promiseProbe = v);"))
        return 5;
    CParamNode params;
    auto nativeEntity = manager.LookupEntityHandle(2, true);
    auto scriptedEntity = manager.LookupEntityHandle(3, true);
    if (!manager.AddComponent(nativeEntity, CID_Test1A, params) ||
        !manager.AddComponent(scriptedEntity, manager.LookupCID("TestScript2A"), params))
        return 3;
    std::uint32_t rngSummary = 0;
    for (int tick = 0; tick < 100; ++tick)
    {
        HeadlessUpdateComponents(simContext, fixed::FromInt(25));
        context->RunJobs();
        context->MaybeIncrementalGC();
        double random = 0;
        if (!manager.GetScriptInterface().Eval("Math.random()", random)) return 6;
        rngSummary = rngSummary * 1664525u + static_cast<std::uint32_t>(random * 4294967296.0);
    }
    auto* native = static_cast<ICmpTest1*>(manager.QueryInterface(2, IID_Test1));
    auto* scripted = static_cast<ICmpTest2*>(manager.QueryInterface(3, IID_Test2));
    if (!native || !scripted || native->GetX() != 11100 || scripted->GetX() != 203500)
        return 4;
    int promiseResult = 0;
    if (!manager.GetScriptInterface().Eval("promiseProbe", promiseResult) || promiseResult != 9)
        return 7;
    std::printf("{\"scenario\":\"component-ticks-01\",\"seed\":12345,\"ticks\":100,\"rng\":%u,\"promise\":%d,\"entities\":[{\"id\":2,\"x\":%d},{\"id\":3,\"x\":%d}]}\n", rngSummary, promiseResult, native->GetX(), scripted->GetX());
    return 0;
}

#ifndef WASM_BROWSER_FIXTURE
int main(int argc, char** argv)
{
    return RunComponentFixture(argc, argv);
}
#endif
