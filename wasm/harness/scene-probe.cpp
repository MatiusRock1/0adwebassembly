// Original map scene: application services and presentation bridge only.
#include "lib/external_libraries/libsdl.h"
#include "lib/timer.h"
#include "ps/ConfigDB.h"
#include "ps/ThreadUtil.h"
#include "renderer/backend/gl/Device.h"
#include "renderer/backend/IDeviceCommandContext.h"
#include "renderer/backend/ISwapChain.h"
#include <emscripten/html5.h>
#include <cstdio>
#include "renderer/Renderer.h"
#include "renderer/RenderingOptions.h"
#include "graphics/LightEnv.h"
#include "ps/Input.h"
#include "lib/file/vfs/vfs.h"
#include "ps/Filesystem.h"
#include "ps/XML/Xeromyces.h"
#include "scriptinterface/Engine.h"
#include "scriptinterface/Context.h"
#include "scriptinterface/Interface.h"
#include "scriptinterface/Request.h"
#include "scriptinterface/JSON.h"
#include "scriptinterface/Object.h"
#include "simulation2/Simulation2.h"
#include "graphics/MapReader.h"
#include "graphics/Terrain.h"
#include "graphics/Patch.h"
#include "graphics/UnitManager.h"
#include "graphics/ColladaManager.h"
#include "graphics/MeshManager.h"
#include "graphics/SkeletonAnimManager.h"
#include "graphics/ObjectManager.h"
#include "graphics/LOSTexture.h"
#include "graphics/TerritoryTexture.h"
#include "graphics/MiniMapTexture.h"
#include "graphics/TerrainTextureManager.h"
#include "graphics/TextureManager.h"
#include "renderer/SceneRenderer.h"
#include "renderer/WaterManager.h"
#include "renderer/SkyManager.h"
#include "ps/TaskManager.h"
#include "ps/Loader.h"
#include <emscripten.h>
#include <fstream>
CLightEnv g_LightEnv;
extern thread_local std::shared_ptr<Script::Context> g_ScriptContext;

class MapScene final : public Scene
{
public:
 CTerrain& terrain; CSimulation2& sim;
 CLOSTexture los; CTerritoryTexture territory; CMiniMapTexture minimap;
 MapScene(CTerrain& t, CSimulation2& s, Renderer::Backend::IDevice* d)
 : terrain(t), sim(s), los(s), territory(s), minimap(d,s) {}
 void EnumerateObjects(const CFrustum& f, SceneCollector* c) override {
  for (ssize_t z=0; z<terrain.GetPatchesPerSide(); ++z)
   for (ssize_t x=0; x<terrain.GetPatchesPerSide(); ++x) {
    auto* p=terrain.GetPatch(x,z);
    if (f.IsBoxVisible(p->GetWorldBounds())) c->Submit(p);
   }
  sim.RenderSubmit(*c,f,true);
 }
 CLOSTexture& GetLOSTexture() override {return los;}
 CTerritoryTexture& GetTerritoryTexture() override {return territory;}
 CMiniMapTexture& GetMiniMapTexture() override {return minimap;}
};


int main()
{
    Threading::SetMainThread();
    timer_Init();
    CConfigDB::Initialise();
    CConfigDB& config = g_ConfigDB;
 config.SetValueString(CFG_COMMAND,"max_actor_quality","100");
 CXeromycesEngine xml;
 Threading::TaskManager tasks;
 Script::Engine engine;
 g_ScriptContext = std::make_shared<Script::Context>();
 g_VFS = CreateVfs();
 g_VFS->Mount(L"", OsPath("/data/mod/"));
 g_VFS->Mount(L"", OsPath("/data/public/"), 0, 1);
 g_VFS->Mount(L"cache/", OsPath("/cache/"));
 Input::Manager inputManager;
 g_RenderingOptions.SetShadows(false);
 g_RenderingOptions.SetWaterEffects(false);
 g_RenderingOptions.SetWaterFancyEffects(false);
 g_RenderingOptions.SetWaterReflection(false);
 g_RenderingOptions.SetWaterRefraction(false);
 g_RenderingOptions.SetPostProc(false);
 g_RenderingOptions.SetGPUSkinning(false);
 g_RenderingOptions.SetSilhouettes(false);
 g_RenderingOptions.SetSmoothLOS(false);
    if (SDL_Init(SDL_INIT_VIDEO) < 0) return 20;
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
    SDL_Window* window = SDL_CreateWindow("0 A.D. WebGL 2", 0, 0, 640, 480, 0);
    if (!window) { std::fprintf(stderr, "SDL window: %s\n", SDL_GetError()); return 21; }
    if (SDL_GL_LoadLibrary(nullptr) < 0) return 24;
    EmscriptenWebGLContextAttributes attributes;
    emscripten_webgl_init_context_attributes(&attributes);
    attributes.majorVersion = 2;
    attributes.alpha = false;
    attributes.antialias = false;
    attributes.explicitSwapControl = true;
    attributes.renderViaOffscreenBackBuffer = true;
    attributes.proxyContextToMainThread = EMSCRIPTEN_WEBGL_CONTEXT_PROXY_ALWAYS;
    const auto webgl = emscripten_webgl_create_context("#canvas", &attributes);
    if (webgl <= 0 || emscripten_webgl_make_context_current(webgl) != EMSCRIPTEN_RESULT_SUCCESS) return 25;
    {
        // The backend supports an externally owned context (also used by Atlas).
        auto device = Renderer::Backend::GL::CDevice::Create(nullptr);
        if (!device) return 22;
 CRenderer renderer(device.get(), inputManager, 640, 480);
 std::puts("SCENE_RENDERER_INITIALIZED");
 CTerrain terrain;
 CUnitManager units;
 CSimulation2 sim{&units,*g_ScriptContext,&terrain,CSimulation2::DEFAULT_SCRIPTS};
 sim.ResetState();
 std::puts("SCENE_SIM_CREATED");
 CColladaManager collada(g_VFS);
 std::puts("SCENE_COLLADA_CREATED");
 CMeshManager meshes(collada);
 CSkeletonAnimManager animations(collada);
 std::puts("SCENE_MESH_SERVICES_CREATED");
 CObjectManager objects(meshes,animations,sim);
 std::puts("SCENE_OBJECTS_CREATED");
 units.SetObjectManager(objects);
 Script::Request rq(sim.GetScriptInterface());
 std::ifstream replay("/scenario/commands.txt");
 std::string attributes; std::getline(replay,attributes);
 JS::RootedValue attrs(rq.cx), settings(rq.cx);
 if (!Script::ParseJSON(rq,attributes.substr(6),&attrs) ||
     !Script::GetProperty(rq,attrs,"settings",&settings)) return 30;
 sim.SetInitAttributes(attrs);
 renderer.GetSceneRenderer().GetWaterManager().SetTerrain(&terrain);
 renderer.GetSceneRenderer().GetSkyManager().SetSkySet(L"default");
 CMapReader reader;
 std::puts("SCENE_ATTRIBUTES_PARSED");
 PS::Loader::BeginRegistering();
 PS::Loader::Register([&]{return g_TexMan.LoadTerrainTextures();},L"Terrain textures",1000);
 PS::Loader::Register([&]{return sim.ProgressiveLoad();},L"Simulation",1000);
 reader.LoadMap(L"maps/scenarios/pathfinding_terrain_demo.pmp",*g_ScriptContext,settings,
   &terrain,&renderer.GetSceneRenderer().GetWaterManager(),nullptr,&g_LightEnv,
   nullptr,nullptr,nullptr,nullptr,&sim,&sim.GetSimContext(),1,false);
 PS::Loader::EndRegistering();
 if (PS::Loader::NonprogressiveLoad()<0) return 31;
 sim.PreInitGame(); sim.InitGame();
 MapScene scene(terrain,sim,device.get());
 auto& sr=renderer.GetSceneRenderer();
 sr.SetSimulation(&sim); sr.SetLightEnv(&g_LightEnv);
 CCamera camera;
 camera.SetViewPort({0,0,640,480});
 camera.SetPerspectiveProjection(1.0f,1000.0f,0.785398f);
 camera.LookAt(CVector3D(155,310,390),CVector3D(155,0,245),CVector3D(0,1,0));
 camera.UpdateFrustum();
 auto context=device->CreateCommandContext();
 auto swapChain=device->CreateSwapChain("browser",nullptr,640,480,false,nullptr);
 for (int frame=0; frame<120; ++frame) {
  if (frame%12==0) sim.Update(200,{});
  sim.Interpolate(0.2f,float(frame%12)/12.0f,1.0f/60.0f);
  renderer.GetTextureManager().MakeProgress();
  renderer.GetTextureManager().MakeUploadProgress(context.get());
  renderer.BeginFrame();
  sr.SetSceneCamera(camera,camera); sr.EnumerateSceneObjects(scene);
  sr.PrepareSubmissions(context.get());
  using namespace Renderer::Backend;
  if (!swapChain->AcquireNextBackbuffer()) return 32;
  context->BeginFramebufferPass(swapChain->GetCurrentBackbuffer(
   AttachmentLoadOp::CLEAR,AttachmentStoreOp::STORE,
   AttachmentLoadOp::CLEAR,AttachmentStoreOp::STORE));
  IDeviceCommandContext::Rect viewport{0,0,640,480};
  context->SetViewports(1,&viewport);
  sr.RenderSubmissions(context.get()); sr.RenderSceneOverlays(context.get());
  context->EndFramebufferPass(); context->Flush(); swapChain->Present();
  if (emscripten_webgl_commit_frame()!=EMSCRIPTEN_RESULT_SUCCESS) return 33;
  auto stats=renderer.GetStats();
  if (frame==119) std::printf("SCENE_GEOMETRY %zu %zu %zu\n",stats.m_TerrainTris,stats.m_ModelTris,stats.m_DrawCalls);
  renderer.EndFrame();

 }
 device->WaitUntilIdle();
 std::puts("SCENE_RENDERER_MAP_PASSED");
    }

    emscripten_webgl_destroy_context(webgl);
    SDL_DestroyWindow(window);
    SDL_Quit();
    g_VFS.reset();
    g_ScriptContext.reset();
    CConfigDB::Shutdown();
    return 0;
}
