// Original map scene: application services and presentation bridge only.
#include "lib/external_libraries/libsdl.h"
#include "lib/timer.h"
#include "ps/ConfigDB.h"
#include "ps/ThreadUtil.h"
#include "renderer/backend/gl/Device.h"
#include "renderer/backend/IDeviceCommandContext.h"
#include "renderer/backend/ISwapChain.h"
#include <emscripten/html5.h>
#include <emscripten/proxying.h>
#include <emscripten/threading.h>
#include <atomic>
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
#include "renderer/RenderModifiers.h"
#include "renderer/WaterManager.h"
#include "renderer/SkyManager.h"
#include "ps/TaskManager.h"
#include "ps/Loader.h"
#include <emscripten.h>
#include <emscripten/heap.h>
#include <js/GCAPI.h>
#include <fstream>
CLightEnv g_LightEnv;
extern thread_local std::shared_ptr<Script::Context> g_ScriptContext;
namespace {
JS::GCSliceCallback previousGCSliceCallback = nullptr;
double gcSliceStart=0, nurseryStart=0, gcFrameMs=0;
void SceneGCSlice(JSContext* cx, JS::GCProgress progress, const JS::GCDescription& description)
{
 if (progress==JS::GC_SLICE_BEGIN) gcSliceStart=emscripten_get_now();
 if (progress==JS::GC_SLICE_END) gcFrameMs+=emscripten_get_now()-gcSliceStart;
 if (previousGCSliceCallback) previousGCSliceCallback(cx,progress,description);
}
void SceneNurseryGC(JSContext*, JS::GCNurseryProgress progress, JS::GCReason, void*)
{
 if (progress==JS::GCNurseryProgress::GC_NURSERY_COLLECTION_START) nurseryStart=emscripten_get_now();
 else gcFrameMs+=emscripten_get_now()-nurseryStart;
}
}

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


#include "simulation2/helpers/Selection.h"
#include "simulation2/system/CmpPtr.h"
#include "simulation2/components/ICmpSelectable.h"
#include "simulation2/components/ICmpPosition.h"
#include "simulation2/components/ICmpPlayer.h"
#include "simulation2/components/ICmpPlayerManager.h"
#include "graphics/HFTracer.h"
#include "graphics/Color.h"
#include <algorithm>
#include <cmath>
#include <sstream>

// Own all services across browser callbacks; no stack references survive main.
struct SceneApplication
{
 Script::Engine engine;
 CXeromycesEngine xml;
 Threading::TaskManager tasks;
 Input::Manager input;
 SDL_Window* window = nullptr;
 EMSCRIPTEN_WEBGL_CONTEXT_HANDLE webgl = 0;
 std::unique_ptr<Renderer::Backend::IDevice> device;
 std::unique_ptr<CRenderer> renderer;
 CTerrain terrain;
 CUnitManager units;
 std::unique_ptr<CSimulation2> sim;
 std::unique_ptr<CColladaManager> collada;
 std::unique_ptr<CMeshManager> meshes;
 std::unique_ptr<CSkeletonAnimManager> animations;
 std::unique_ptr<CObjectManager> objects;
 std::unique_ptr<MapScene> scene;
 std::unique_ptr<Renderer::Backend::IDeviceCommandContext> context;
 std::unique_ptr<Renderer::Backend::ISwapChain> swapChain;
 CCamera camera;
 std::vector<SimulationCommand> commands;
 entity_id_t selected = INVALID_ENTITY;
 int width=640, height=480, frames=0, ticks=0, restarts=0;
 bool paused=false, step=false, stop=false;
 double previous=0, accumulator=0;
 double tickMs=0, interpolateMs=0, uploadMs=0, rendererMs=0, presentMs=0;
 double gpuMs=-1, gpuProbeProxyMs=0;
 double scriptMs=-1;
 int exitCode=0;
 bool gpuProfiling=false, nurseryObserved=false;
 bool benchmarkMode=false;
 float cameraX=155, cameraZ=245, elevation=120;
 bool ready=false;

 ~SceneApplication()
 {
  commands.clear(); scene.reset(); sim.reset();
  // Free patch render data while the renderer still owns its vertex buffers.
  terrain.Initialize(0,nullptr);
  objects.reset(); animations.reset(); meshes.reset(); collada.reset();
  swapChain.reset(); context.reset(); renderer.reset(); device.reset();
  if (webgl > 0) emscripten_webgl_destroy_context(webgl);
  if (window) SDL_DestroyWindow(window);
  SDL_Quit(); g_VFS.reset();
  if (g_ScriptContext) {
   auto* cx=g_ScriptContext->GetGeneralJSContext();
   JS::SetGCSliceCallback(cx,previousGCSliceCallback);
   if (nurseryObserved) JS::RemoveGCNurseryCollectionCallback(cx,SceneNurseryGC,nullptr);
  }
  g_ScriptContext.reset();
 }

 void UpdateCamera()
 {
  camera.SetViewPort({0,0,width,height});
  camera.SetPerspectiveProjection(1.0f,1000.0f,0.785398f);
  camera.LookAt(CVector3D(cameraX,elevation,cameraZ+elevation*0.8f),
   CVector3D(cameraX,0,cameraZ),CVector3D(0,1,0));
  camera.UpdateFrustum();
 }

 bool LoadMap()
 {
  std::puts("SCENE_MAP_LOAD_BEGIN");
  commands.clear(); selected=INVALID_ENTITY; scene.reset();
  renderer->GetSceneRenderer().ResetState();
  Script::Request rq(sim->GetScriptInterface());
  std::ifstream replay("/scenario/commands.txt");
  std::string attributes; std::getline(replay,attributes);
  JS::RootedValue attrs(rq.cx), settings(rq.cx);
  if (!Script::ParseJSON(rq,attributes.substr(6),&attrs) ||
      !Script::GetProperty(rq,attrs,"settings",&settings)) return false;
  sim->SetInitAttributes(attrs);
  CMapReader reader;
  PS::Loader::BeginRegistering();
  PS::Loader::Register([&]{return g_TexMan.LoadTerrainTextures();},L"Terrain textures",1000);
  PS::Loader::Register([&]{return sim->ProgressiveLoad();},L"Simulation",1000);
  reader.LoadMap(L"maps/scenarios/pathfinding_terrain_demo.pmp",*g_ScriptContext,settings,
   &terrain,&renderer->GetSceneRenderer().GetWaterManager(),nullptr,&g_LightEnv,
   nullptr,nullptr,nullptr,nullptr,sim.get(),&sim->GetSimContext(),1,false);
  PS::Loader::EndRegistering();
  if (PS::Loader::NonprogressiveLoad()<0) return false;
  std::puts("SCENE_LOADER_FINISHED");
  sim->PreInitGame(); sim->InitGame();
  // Match CGame::CachePlayerColors using the authentic player components.
  CmpPtr<ICmpPlayerManager> players(*sim,SYSTEM_ENTITY);
  if (!players || players->GetNumPlayers()<=0) return false;
  std::vector<CColor> playerColors(players->GetNumPlayers(),CColor(1,0,1,1));
  std::printf("SCENE_PLAYER_COLORS [");
  for (int i=0; i<players->GetNumPlayers(); ++i) {
   CmpPtr<ICmpPlayer> player(*sim,players->GetPlayerByID(i));
   if (player) playerColors[i]=player->GetDisplayedColor();
   const auto& color=playerColors[i];
   std::printf("%s[%.6f,%.6f,%.6f,%.6f]",i?",":"",color.r,color.g,color.b,color.a);
  }
  std::puts("]"); SetScenePlayerColors(playerColors);
  std::puts("SCENE_GAME_INITIALIZED");
  scene=std::make_unique<MapScene>(terrain,*sim,device.get());
  renderer->GetSceneRenderer().SetSimulation(sim.get());
  renderer->GetSceneRenderer().SetLightEnv(&g_LightEnv);
  accumulator=0; ticks=0; previous=emscripten_get_now();
  std::printf("SCENE_MAP_LOADED %d\n",restarts);
  return true;
 }

 int Initialize()
 {
  g_ScriptContext=std::make_shared<Script::Context>();
  previousGCSliceCallback=JS::SetGCSliceCallback(g_ScriptContext->GetGeneralJSContext(),SceneGCSlice);
  nurseryObserved=JS::AddGCNurseryCollectionCallback(g_ScriptContext->GetGeneralJSContext(),SceneNurseryGC,nullptr);
  gpuProfiling=MAIN_THREAD_EM_ASM_INT({return new URL(location.href).searchParams.get('gpuTimer')==='1';});
  benchmarkMode=MAIN_THREAD_EM_ASM_INT({return new URL(location.href).searchParams.get('benchmark')==='1';});
  g_VFS=CreateVfs();
  if (g_VFS->Mount(L"",OsPath("/data/mod/"))<0 ||
      g_VFS->Mount(L"",OsPath("/data/public/"),0,1)<0 ||
      g_VFS->Mount(L"cache/",OsPath("/cache/"))<0) return 10;
  g_ConfigDB.SetValueString(CFG_COMMAND,"max_actor_quality","100");
  g_RenderingOptions.SetShadows(false);
  g_RenderingOptions.SetWaterEffects(false);
  g_RenderingOptions.SetWaterFancyEffects(false);
  g_RenderingOptions.SetWaterReflection(false);
  g_RenderingOptions.SetWaterRefraction(false);
  g_RenderingOptions.SetPostProc(false);
  g_RenderingOptions.SetGPUSkinning(false);
  g_RenderingOptions.SetSilhouettes(false);
  g_RenderingOptions.SetSmoothLOS(false);
  if (SDL_Init(SDL_INIT_VIDEO)<0) return 20;
  window=SDL_CreateWindow("0 A.D. WebGL 2",0,0,width,height,0);
  if (!window || SDL_GL_LoadLibrary(nullptr)<0) return 21;
  EmscriptenWebGLContextAttributes attributes;
  emscripten_webgl_init_context_attributes(&attributes);
  attributes.majorVersion=2; attributes.alpha=false; attributes.antialias=false;
  attributes.powerPreference=EM_WEBGL_POWER_PREFERENCE_HIGH_PERFORMANCE;
  attributes.explicitSwapControl=true; attributes.renderViaOffscreenBackBuffer=true;
  attributes.proxyContextToMainThread=EMSCRIPTEN_WEBGL_CONTEXT_PROXY_ALWAYS;
#if defined(WASM_SCENE_OFFSCREEN)
  // Experimental worker ownership requires the SDK's transferred canvas support.
  attributes.explicitSwapControl=false; attributes.renderViaOffscreenBackBuffer=false;
  attributes.proxyContextToMainThread=EMSCRIPTEN_WEBGL_CONTEXT_PROXY_DISALLOW;
  gpuProfiling=false; // The main-thread timer probe cannot access a transferred context.
#endif
  webgl=emscripten_webgl_create_context("#canvas",&attributes);
  if (webgl<=0 || emscripten_webgl_make_context_current(webgl)!=EMSCRIPTEN_RESULT_SUCCESS) return 25;
  device=Renderer::Backend::GL::CDevice::Create(nullptr);
  if (!device) return 22;
  renderer=std::make_unique<CRenderer>(device.get(),input,width,height);
  sim=std::make_unique<CSimulation2>(&units,*g_ScriptContext,&terrain,CSimulation2::DEFAULT_SCRIPTS);
  sim->ResetState();
  collada=std::make_unique<CColladaManager>(g_VFS);
  meshes=std::make_unique<CMeshManager>(*collada);
  animations=std::make_unique<CSkeletonAnimManager>(*collada);
  objects=std::make_unique<CObjectManager>(*meshes,*animations,*sim);
  units.SetObjectManager(*objects);
  renderer->GetSceneRenderer().GetWaterManager().SetTerrain(&terrain);
  renderer->GetSceneRenderer().GetSkyManager().SetSkySet(L"default");
  if (!LoadMap()) return 31;
  context=device->CreateCommandContext();
  swapChain=device->CreateSwapChain("browser",nullptr,width,height,false,nullptr);
  if (!context || !swapChain) return 23;
  UpdateCamera();
  return 0;
 }

 void Select(int x,int y)
 {
  if (selected!=INVALID_ENTITY) {
   CmpPtr<ICmpSelectable> old(sim->GetSimContext(),selected);
   if (old) old->SetSelectionHighlight(CColor(0,0,0,0),false);
  }
  selected=EntitySelection::PickEntityAtPoint(*sim,camera,x,y,1,false);
  if (selected!=INVALID_ENTITY) {
   CmpPtr<ICmpSelectable> component(sim->GetSimContext(),selected);
   if (component) component->SetSelectionHighlight(CColor(1,1,1,1),true);
  }
  std::printf("SCENE_SELECTED %u\n",selected);
 }

 void Move(int x,int y)
 {
  if (selected==INVALID_ENTITY) return;
  const auto ray=camera.BuildCameraRay(x,y);
  CHFTracer tracer(terrain); int tx,tz; CVector3D target;
  if (!tracer.RayIntersect(ray.origin,ray.direction,tx,tz,target)) return;
  Script::Request rq(sim->GetScriptInterface());
  std::ostringstream json;
  json<<"{\"type\":\"walk\",\"entities\":["<<selected<<"],\"x\":"<<target.X
      <<",\"z\":"<<target.Z<<",\"queued\":false}";
  JS::RootedValue command(rq.cx);
  if (!Script::ParseJSON(rq,json.str(),&command)) {stop=true; exitCode=32; return;}
  commands.emplace_back(1,rq.cx,command);
  std::printf("SCENE_WALK_QUEUED %u %.5f %.5f\n",selected,target.X,target.Z);
 }

 void Tick()
 {
  const double start=emscripten_get_now();
  sim->Update(200,commands); commands.clear(); ++ticks;
  tickMs+=emscripten_get_now()-start;
 }

 void Metrics()
 {
  CmpPtr<ICmpPosition> position(sim->GetSimContext(),8);
  if (!position) return;
  const auto p=position->GetPosition();
  const CVector3D world(p.X.ToFloat(),p.Y.ToFloat(),p.Z.ToFloat());
  const auto screen=camera.GetScreenCoordinates(world);
  const auto& stats=renderer->GetStats();
  std::printf("SCENE_STATS {\"frame\":%d,\"tick\":%d,\"restarts\":%d,\"paused\":%s,\"selected\":%u,\"x\":%.5f,\"z\":%.5f,\"screenX\":%.3f,\"screenY\":%.3f,\"terrainTriangles\":%zu,\"modelTriangles\":%zu,\"drawCalls\":%zu,\"width\":%d,\"height\":%d}\n",
   frames,ticks,restarts,paused?"true":"false",selected,world.X,world.Z,
   screen.X,screen.Y,stats.m_TerrainTris,stats.m_ModelTris,stats.m_DrawCalls,width,height);
 }

 void Frame()
 {
  tickMs=0;
  gcFrameMs=0;
#if defined(WASM_SCENE_SCRIPT_TIMING)
  WasmSceneProfile::scriptMs=0;
#endif
  for (const SDL_Event& event : input.PollEvents()) {
   input.DispatchEvent(event);
   if (event.type==SDL_QUIT) stop=true;
   if (event.type==SDL_WINDOWEVENT && event.window.event==SDL_WINDOWEVENT_FOCUS_LOST) {
    paused=true; accumulator=0; std::puts("SCENE_FOCUS_PAUSED");
   }
   if (event.type==SDL_KEYDOWN && !event.key.repeat) {
    const auto key=event.key.keysym.sym;
    if (benchmarkMode && (key==SDLK_LEFT || key==SDLK_RIGHT || key==SDLK_UP || key==SDLK_DOWN || key==SDLK_q || key==SDLK_e)) continue;
    switch (event.key.keysym.sym) {
     case SDLK_SPACE: paused=!paused; accumulator=0; std::printf("SCENE_PAUSED %d\n",int(paused)); break;
     case SDLK_p: paused=true; accumulator=0; std::puts("SCENE_FOCUS_PAUSED"); break;
     case SDLK_n: if (paused) step=true; break;
     case SDLK_r: ++restarts; if (!LoadMap()) {stop=true; exitCode=31;} break;
     case SDLK_ESCAPE: paused=true; accumulator=0; break;
     case SDLK_x: stop=true; break;
     case SDLK_LEFT: cameraX-=10; break;
     case SDLK_RIGHT: cameraX+=10; break;
     case SDLK_UP: cameraZ-=10; break;
     case SDLK_DOWN: cameraZ+=10; break;
     case SDLK_q: elevation=std::max(30.0f,elevation-10); break;
     case SDLK_e: elevation=std::min(400.0f,elevation+10); break;
    }
   }
   if (!benchmarkMode && event.type==SDL_MOUSEWHEEL) elevation=std::clamp(elevation-event.wheel.y*10.0f,30.0f,400.0f);
   if (!benchmarkMode && event.type==SDL_MOUSEBUTTONDOWN) {
    // SDL reports coordinates in its logical window, which remains independent
    // of the canvas backing resolution when DOM fullscreen/DPR scales it.
    int inputWidth,inputHeight;
    SDL_GetWindowSize(window,&inputWidth,&inputHeight);
    if (inputWidth<=0 || inputHeight<=0) continue;
    const int x=std::lround(double(event.button.x)*width/inputWidth);
    const int y=std::lround(double(event.button.y)*height/inputHeight);
    if (event.button.button==SDL_BUTTON_LEFT) Select(x,y);
    if (event.button.button==SDL_BUTTON_RIGHT) Move(x,y);
   }
  }
  // LoadMap can clear the scene before reporting an error. Never draw after stop.
  if (stop) return;
  int w,h;
  if (emscripten_get_canvas_element_size("#canvas",&w,&h)==EMSCRIPTEN_RESULT_SUCCESS &&
      w>0 && h>0 && (w!=width || h!=height)) {
   // A DOM canvas resize does not resize Emscripten's proxied default FBO.
   // Update it through the runtime API before recreating renderer targets.
   if (emscripten_set_canvas_element_size("#canvas",w,h)!=EMSCRIPTEN_RESULT_SUCCESS) {
    std::puts("SCENE_RESIZE_FAILED"); stop=true; exitCode=36; return;
   }
   width=w; height=h;
   renderer->DestroyViewSizeDependentObjects();
   renderer->CreateViewSizeDependentObjects(width,height);
   swapChain=device->CreateSwapChain("browser",nullptr,width,height,false,nullptr);
   std::printf("SCENE_RESIZED %d %d\n",width,height);
  }
  UpdateCamera();
  const double now=emscripten_get_now();
  const double elapsed=std::clamp(now-previous,0.0,1000.0); previous=now;
  if (!paused) accumulator+=elapsed;
  for (int catchup=0; !paused && accumulator>=200 && catchup<5; ++catchup) {Tick(); accumulator-=200;}
  if (step) {Tick(); step=false;}
  double stageStart=emscripten_get_now();
  sim->Interpolate(0.2f,paused?0.0f:float(accumulator/200),float(elapsed/1000));
  interpolateMs=emscripten_get_now()-stageStart; stageStart=emscripten_get_now();
  renderer->GetTextureManager().MakeProgress();
  renderer->GetTextureManager().MakeUploadProgress(context.get());
  uploadMs=emscripten_get_now()-stageStart; stageStart=emscripten_get_now();
  gpuProbeProxyMs=0;
  if (gpuProfiling) {
   const double probeStart=emscripten_get_now();
   gpuMs=MAIN_THREAD_EM_ASM_DOUBLE({
    const gl=Module['canvas'].getContext('webgl2');
    const state=Module['sceneGpuTimer'] ??= ({gl, ext:gl.getExtension('EXT_disjoint_timer_query_webgl2'), pending:[], active:null});
    if (!state.ext) return -1;
    let value=-1;
    const disjoint=gl.getParameter(state.ext.GPU_DISJOINT_EXT);
    while (state.pending.length && (disjoint || gl.getQueryParameter(state.pending[0],gl.QUERY_RESULT_AVAILABLE))) {
     const q=state.pending.shift();
     if (!disjoint) {
      const ns=gl.getQueryParameter(q,gl.QUERY_RESULT);
      if (Number.isFinite(ns)) value=ns/1000000;
     }
     gl.deleteQuery(q);
    }
    if (state.pending.length<8) {
     state.active=gl.createQuery();
     if (state.active) gl.beginQuery(state.ext.TIME_ELAPSED_EXT,state.active);
    }
    return value;
   });
   gpuProbeProxyMs+=emscripten_get_now()-probeStart;
  }
  stageStart=emscripten_get_now();
  renderer->BeginFrame();
  auto& sr=renderer->GetSceneRenderer();
  sr.SetSceneCamera(camera,camera); sr.EnumerateSceneObjects(*scene); sr.PrepareSubmissions(context.get());
  using namespace Renderer::Backend;
  if (!swapChain->AcquireNextBackbuffer()) {stop=true; exitCode=33; return;}
  context->BeginFramebufferPass(swapChain->GetCurrentBackbuffer(
   AttachmentLoadOp::CLEAR,AttachmentStoreOp::STORE,AttachmentLoadOp::CLEAR,AttachmentStoreOp::STORE));
  IDeviceCommandContext::Rect viewport{0,0,width,height}; context->SetViewports(1,&viewport);
  sr.RenderSubmissions(context.get()); sr.RenderSceneOverlays(context.get());
  context->EndFramebufferPass(); context->Flush();
  rendererMs=emscripten_get_now()-stageStart; stageStart=emscripten_get_now();
  swapChain->Present();
#if !defined(WASM_SCENE_OFFSCREEN)
  if (emscripten_webgl_commit_frame()!=EMSCRIPTEN_RESULT_SUCCESS) {stop=true; exitCode=34; return;}
#endif
  presentMs=emscripten_get_now()-stageStart;
  if (gpuProfiling) {
   const double probeStart=emscripten_get_now();
   MAIN_THREAD_EM_ASM({
    const state=Module['sceneGpuTimer'];
    if (state?.active) {
     state.gl.endQuery(state.ext.TIME_ELAPSED_EXT);
     state.pending.push(state.active); state.active=null;
    }
   });
   gpuProbeProxyMs+=emscripten_get_now()-probeStart;
  }
  ++frames;
#if defined(WASM_SCENE_SCRIPT_TIMING)
  scriptMs=WasmSceneProfile::scriptMs;
#endif
  // Submission timing includes synchronous proxy waits, not GPU completion.
  std::printf("SCENE_FRAME {\"frame\":%d,\"timeMs\":%.3f,\"tick\":%d,\"backlogMs\":%.3f,\"tickMs\":%.3f,\"interpolateMs\":%.3f,\"uploadMs\":%.3f,\"rendererMs\":%.3f,\"presentMs\":%.3f,\"scriptMs\":%.3f,\"gcMs\":%.3f,\"gpuMs\":%.3f,\"gpuProbeProxyMs\":%.3f,\"wasmHeapBytes\":%zu,\"paused\":%s,\"width\":%d,\"height\":%d}\n",frames,emscripten_get_now(),ticks,accumulator,tickMs,interpolateMs,uploadMs,rendererMs,presentMs,scriptMs,gcFrameMs,gpuMs,gpuProbeProxyMs,emscripten_get_heap_size(),paused?"true":"false",width,height);
  const auto& stats=renderer->GetStats();
  if (!ready && frames>=30 && stats.m_TerrainTris>0 && stats.m_ModelTris>0) {
   ready=true; std::puts("SCENE_READY"); Metrics();
  }
  if (frames%30==0) Metrics();
  renderer->EndFrame();
 }
};

std::unique_ptr<SceneApplication> application;
long frameInterval = 0;
double nextFrameTime=0;
em_proxying_queue* frameQueue=nullptr;
pthread_t sceneThread;
std::atomic<bool> frameClockRunning{false}, framePending{false};
bool useDisplayClock=false;
extern "C" EMSCRIPTEN_KEEPALIVE void StopSceneFrameClock()
{
 frameClockRunning=false;
}
void FrameCallback(void*)
{
 const double now=emscripten_get_now();
 if (!nextFrameTime) nextFrameTime=now;
 if (!useDisplayClock && now<nextFrameTime) {
  frameInterval=emscripten_set_timeout(FrameCallback,std::max(1.0,nextFrameTime-now),nullptr);
  return;
 }
 application->Frame();
 if (application->stop) {
  const int code=application->exitCode;
  frameClockRunning=false;
  if (useDisplayClock) emscripten_clear_interval(frameInterval);
  application.reset(); CConfigDB::Shutdown();
  std::puts("SCENE_STOPPED"); emscripten_force_exit(code);
  return;
 }
 framePending=false;
 if (useDisplayClock) return;
 nextFrameTime+=1000.0/60.0;
 const double afterFrame=emscripten_get_now();
 if (nextFrameTime<afterFrame) nextFrameTime=afterFrame+1000.0/60.0;
 frameInterval=emscripten_set_timeout(FrameCallback,std::max(1.0,nextFrameTime-afterFrame),nullptr);
}
bool DisplayFrame(double timestamp,void*)
{
 if (!frameClockRunning) return false;
 // Keep the original default 60 FPS cap on faster displays. The one-ms
 // scheduling allowance absorbs RAF timestamp jitter, not acceptance error.
 static double deadline=0;
 if (timestamp<deadline-1.0) return true;
 deadline=std::max(deadline+1000.0/60.0,timestamp);
 if (!framePending.exchange(true) &&
     !emscripten_proxy_async(frameQueue,sceneThread,FrameCallback,nullptr))
  framePending=false;
 return true;
}
void StartDisplayClock(void*)
{
 emscripten_request_animation_frame_loop(DisplayFrame,nullptr);
}
void PollHiddenWindow(void*)
{
 // RAF is suspended in hidden tabs. Process focus/close events at low rate so
 // a hidden game can still pause or terminate; hidden frames never pass gates.
 if (frameClockRunning && MAIN_THREAD_EM_ASM_INT({return document.hidden;}) &&
     !framePending.exchange(true)) FrameCallback(nullptr);
}
int main()
{
 Threading::SetMainThread(); timer_Init(); CConfigDB::Initialise();
 application=std::make_unique<SceneApplication>();
 const int result=application->Initialize();
 if (result) {application.reset(); CConfigDB::Shutdown(); return result;}
 useDisplayClock=MAIN_THREAD_EM_ASM_INT({return new URL(location.href).searchParams.get('frameClock')!=='timer';});
 if (useDisplayClock) {
  sceneThread=pthread_self(); frameQueue=em_proxying_queue_create();
  frameClockRunning=true;
  if (!frameQueue || !emscripten_proxy_sync(frameQueue,emscripten_main_runtime_thread_id(),StartDisplayClock,nullptr)) {
   application.reset(); CConfigDB::Shutdown(); return 35;
  }
  frameInterval=emscripten_set_interval(PollHiddenWindow,250,nullptr);
 } else frameInterval = emscripten_set_timeout(FrameCallback,0,nullptr);
 emscripten_exit_with_live_runtime();
 return 0;
}
