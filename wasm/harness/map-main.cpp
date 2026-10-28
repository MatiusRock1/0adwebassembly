// Fixed scenario exercised through the original facade, loader and commands.
#include "scriptinterface/Engine.h"
#include "scriptinterface/Context.h"
#include "scriptinterface/Interface.h"
#include "scriptinterface/Request.h"
#include "scriptinterface/JSON.h"
#include "scriptinterface/Object.h"
#include "simulation2/Simulation2.h"
#include "graphics/MapReader.h"
#include "graphics/Terrain.h"
#include "graphics/UnitManager.h"
#include "lib/file/vfs/vfs.h"
#include "lib/timer.h"
#include "ps/Filesystem.h"
#include "ps/ThreadUtil.h"
#include "ps/TaskManager.h"
#include "ps/ConfigDB.h"
#include "ps/XML/Xeromyces.h"
#include "ps/Loader.h"
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <sstream>

extern thread_local std::shared_ptr<Script::Context> g_ScriptContext;

int main()
{
    Threading::SetMainThread();
    timer_Init();
    CConfigDB config;
    CXeromycesEngine xml;
    Threading::TaskManager tasks;
    Script::Engine engine;
    g_ScriptContext = std::make_shared<Script::Context>();
    g_VFS = CreateVfs();
    if (g_VFS->Mount(L"", OsPath("/data/mod/")) < 0 ||
        g_VFS->Mount(L"", OsPath("/data/public/"), 0, 1) < 0 ||
        g_VFS->Mount(L"cache/", OsPath("/cache/")) < 0) return 10;
    {
        CTerrain terrain;
        CUnitManager units;
        CSimulation2 sim{&units, *g_ScriptContext, &terrain, CSimulation2::DEFAULT_SCRIPTS};
        Script::Request rq(sim.GetScriptInterface());
        std::ifstream replay("/scenario/commands.txt");
        std::string attributes;
        std::getline(replay, attributes);
        JS::RootedValue attrs(rq.cx), settings(rq.cx);
        if (!Script::ParseJSON(rq, attributes.substr(6), &attrs) ||
            !Script::GetProperty(rq, attrs, "settings", &settings)) return 11;
        sim.SetInitAttributes(attrs);
        CMapReader reader;
        PS::Loader::BeginRegistering();
        PS::Loader::Register([&] { return sim.ProgressiveLoad(); }, L"Simulation init", 1000);
        reader.LoadMap(L"maps/scenarios/pathfinding_terrain_demo.pmp", *g_ScriptContext,
            settings, &terrain, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr,
            nullptr, &sim, &sim.GetSimContext(), 1, false);
        PS::Loader::EndRegistering();
        if (PS::Loader::NonprogressiveLoad() < 0) return 12;
        sim.PreInitGame();
        sim.InitGame();
        std::puts("MAP_LOADED");
        for (int tick = 0; tick < 1100; ++tick)
        {
            std::vector<SimulationCommand> commands;
            if (tick == 100)
            {
                JS::RootedValue cmd(rq.cx);
                if (!Script::ParseJSON(rq,
                    "{\"type\":\"walk\",\"entities\":[8],\"x\":160,\"z\":245,\"queued\":false}", &cmd)) return 13;
                commands.emplace_back(1, rq.cx, cmd);
            }
            sim.Update(200, commands);
            if (tick == 0 || tick == 99 || tick == 100 || tick == 109 ||
                tick == 199 || tick == 499 || tick == 1099)
            {
                std::string hash;
                if (!sim.ComputeStateHash(hash, false)) return 14;
                std::ostringstream hex;
                for (unsigned char c : hash) hex << std::hex << std::setw(2) << std::setfill('0') << int(c);
                std::printf("MAP_CHECKPOINT %d %s\n", tick + 1, hex.str().c_str());
                std::ofstream state("/output/tick-" + std::to_string(tick + 1) + ".dat", std::ios::binary);
                if (!sim.SerializeState(state)) return 15;
            }
        }
    }
    g_VFS.reset();
    g_ScriptContext.reset();
    std::puts("MAP_REPLAY_FINISHED");
    return 0;
}
