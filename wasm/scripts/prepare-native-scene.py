"""Isolate the pinned sources and port only the scene harness to Win32/SDL.

No native engine source is changed. The generated main.cpp is a benchmark entry
point, not a replacement for the original game's GUI or a full-game benchmark.
"""
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

root = Path(__file__).resolve().parents[2]
out = root / 'wasm/build/native-windows'
evidence = root / 'docs/wasm/evidence/phase3'
pin = (root / 'BASE_COMMIT.txt').read_text().strip()
out.mkdir(parents=True, exist_ok=True)
archive = root / 'wasm/build/native-windows-source.tar'
if not (out / 'source/main.cpp').exists():
    with archive.open('wb') as stream:
        subprocess.run(['git', '-c', 'safe.directory=' + root.as_posix(), 'archive', pin,
                        'source', 'build', 'libraries'], cwd=root, stdout=stream, check=True,
                       env=dict(os.environ, GIT_LFS_SKIP_SMUDGE='1', GIT_TERMINAL_PROMPT='0'))
    with tarfile.open(archive) as tar:
        tar.extractall(out, filter='data')
    # Hydrate already-cached original resources without fetching credentials.
    for file in out.rglob('*'):
        if file.is_file() and file.stat().st_size < 256:
            payload = file.read_bytes()
            if payload.startswith(b'version https://git-lfs.github.com/spec/v1'):
                oid = payload.decode().split('oid sha256:')[1].splitlines()[0]
                cached = root / '.git/lfs/objects' / oid[:2] / oid[2:4] / oid
                if cached.is_file():
                    assert hashlib.sha256(cached.read_bytes()).hexdigest() == oid
                    shutil.copy2(cached, file)
libs = root / 'wasm/build/native-windows-libs'
assert (libs / 'premake-core/bin/premake5.exe').is_file(), 'Download pinned official Windows libs first'
if not (out / 'libraries/win64').exists():
    shutil.copytree(libs, out / 'libraries/win64')
for folder in libs.iterdir():
    if (folder / 'bin').is_dir():
        for file in (folder / 'bin').iterdir():
            if file.is_file():
                dest = out / ('build/bin' if folder.name in ['premake-core', 'cxxtest-4.4'] else 'binaries/system')
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest / file.name)

# Header-only build fixes needed by this pin with optional audio/lobby disabled.
# Keep these explicit: they do not alter native simulation or rendering behavior.
compatibility = []
sound = out / 'source/soundmanager/scripting/SoundGroup.cpp'
sound_text = sound.read_text()
if '#include "precompiled.h"\n#include <numbers>' not in sound_text:
    fixed = sound_text.replace('#include "precompiled.h"', '#include "precompiled.h"\n#include <numbers>')
    compatibility.extend(difflib.unified_diff(sound_text.splitlines(True), fixed.splitlines(True),
                         fromfile='a/source/soundmanager/scripting/SoundGroup.cpp',
                         tofile='b/source/soundmanager/scripting/SoundGroup.cpp'))
    sound.write_text(fixed)
premake = out / 'build/premake/premake5.lua'
premake_text = premake.read_text()
needle = '\t\tfiles { source_root.."lobby/Globals.cpp" }'
if '\t\tproject_add_extern_libs({"enet"}, "StaticLib")' not in premake_text:
    fixed = premake_text.replace(needle, '\t\tproject_add_extern_libs({"enet"}, "StaticLib")\n' + needle)
    assert fixed != premake_text
    compatibility.extend(difflib.unified_diff(premake_text.splitlines(True), fixed.splitlines(True),
                         fromfile='a/build/premake/premake5.lua', tofile='b/build/premake/premake5.lua'))
    premake.write_text(fixed)
if compatibility:
    (evidence / 'native-build-compatibility.patch').write_text(''.join(compatibility))

# Same owner-independent terrain bridge as the browser scene. Native default
# CGame behavior is retained when no explicit terrain is supplied.
water_h = out / 'source/renderer/WaterManager.h'
water_cpp = out / 'source/renderer/WaterManager.cpp'
if 'm_ExplicitTerrain' not in water_h.read_text():
    before_h, before_cpp = water_h.read_text(), water_cpp.read_text()
    fixed = before_h.replace('class WaterManager', 'class CTerrain;\n\nclass WaterManager', 1)
    fixed = fixed.replace('public:', 'public:\n void SetTerrain(const CTerrain* terrain) { m_ExplicitTerrain = terrain; }', 1)
    end = fixed.rfind('};')
    fixed = fixed[:end] + '\nprivate:\n const CTerrain* m_ExplicitTerrain = nullptr;\n' + fixed[end:]
    water_h.write_text(fixed)
    water_cpp.write_text(before_cpp.replace('g_Game->GetWorld()->GetTerrain()', '(m_ExplicitTerrain ? *m_ExplicitTerrain : g_Game->GetWorld()->GetTerrain())'))
    bridge = ''.join(difflib.unified_diff(before_h.splitlines(True), fixed.splitlines(True), fromfile='a/source/renderer/WaterManager.h', tofile='b/source/renderer/WaterManager.h'))
    bridge += ''.join(difflib.unified_diff(before_cpp.splitlines(True), water_cpp.read_text().splitlines(True), fromfile='a/source/renderer/WaterManager.cpp', tofile='b/source/renderer/WaterManager.cpp'))
    (evidence / 'native-scene-terrain-bridge.patch').write_text(bridge)

# Use the browser's explicit surface constructor, retaining desktop delegation.
renderer_h = out / 'source/renderer/Renderer.h'
renderer_cpp = out / 'source/renderer/Renderer.cpp'
if 'Input::Manager& inputManager' not in renderer_h.read_text():
    before_h, before_cpp = renderer_h.read_text(), renderer_cpp.read_text()
    header = before_h.replace('#include "ps/Singleton.h"', '#include "ps/Singleton.h"\n#include "ps/Input.h"')
    header = header.replace('CRenderer(Renderer::Backend::IDevice* device);', 'CRenderer(Renderer::Backend::IDevice* device);\n CRenderer(Renderer::Backend::IDevice* device, Input::Manager& inputManager, uint32_t width, uint32_t height);')
    cpp = before_cpp.replace('Input::Handler<InputHandler> m_InputHandler{g_VideoMode.m_InputManager, Input::Slot::SCREENSHOT,\n\t\t{m_ScreenShotType}};', 'Input::Handler<InputHandler> m_InputHandler;')
    cpp = cpp.replace('Internals(Renderer::Backend::IDevice* device) :', 'Internals(Renderer::Backend::IDevice* device, Input::Manager& inputManager) :')
    cpp = cpp.replace('postprocManager(device), sceneRenderer(device), fontManager(device)', 'postprocManager(device), sceneRenderer(device), fontManager(device), m_InputHandler(inputManager, Input::Slot::SCREENSHOT, {m_ScreenShotType})')
    cpp = cpp.replace('CRenderer::CRenderer(Renderer::Backend::IDevice* device)\n{', 'CRenderer::CRenderer(Renderer::Backend::IDevice* device) : CRenderer(device, g_VideoMode.m_InputManager, g_VideoMode.GetWindowWidth(), g_VideoMode.GetWindowHeight()) {}\n\nCRenderer::CRenderer(Renderer::Backend::IDevice* device, Input::Manager& inputManager, uint32_t width, uint32_t height)\n{')
    cpp = cpp.replace('std::make_unique<Internals>(device);', 'std::make_unique<Internals>(device, inputManager);')
    cpp = cpp.replace('g_ProfileViewer.AddRootTable(&m->profileTable);\n\tg_ProfileViewer.AddRootTable(&m->backendProfileTable);', 'if (CProfileViewer::IsInitialised()) {\n g_ProfileViewer.AddRootTable(&m->profileTable);\n g_ProfileViewer.AddRootTable(&m->backendProfileTable);\n }')
    cpp = cpp.replace('Open(g_VideoMode.GetWindowWidth(), g_VideoMode.GetWindowHeight());', 'Open(width, height);')
    renderer_h.write_text(header); renderer_cpp.write_text(cpp)
    patch = ''.join(difflib.unified_diff(before_h.splitlines(True), header.splitlines(True), fromfile='a/source/renderer/Renderer.h', tofile='b/source/renderer/Renderer.h'))
    patch += ''.join(difflib.unified_diff(before_cpp.splitlines(True), cpp.splitlines(True), fromfile='a/source/renderer/Renderer.cpp', tofile='b/source/renderer/Renderer.cpp'))
    (evidence / 'native-scene-surface-bridge.patch').write_text(patch)

spec = importlib.util.spec_from_file_location('scene_player_colors', root / 'wasm/scripts/scene-player-colors.py')
color_bridge = importlib.util.module_from_spec(spec); spec.loader.exec_module(color_bridge)
color_patch = color_bridge.apply_bridge(out / 'source')
if color_patch:
    (evidence / 'native-scene-player-colors.patch').write_text(color_patch)
source = (root / 'wasm/harness/scene-main.cpp').read_text()
original = source
# Strip the two optional JS GPU probe blocks; CPU stages stay identical.
def remove_blocks(text, prefix):
    while prefix in text:
        start = text.index(prefix)
        brace = text.index('{', start)
        depth = 1
        end = brace + 1
        while depth:
            if text[end] == '{': depth += 1
            if text[end] == '}': depth -= 1
            end += 1
        text = text[:start] + text[end:]
    return text
source = remove_blocks(source, '  if (gpuProfiling) {')
source = source.replace('#include <emscripten/html5.h>', '#include "lib/precompiled.h"')
source = source.replace('#include <emscripten/proxying.h>', '').replace('#include <emscripten/threading.h>', '')
source = source.replace('#include <emscripten.h>', '#include "ps/GameSetup/GameSetup.h"\n#include "ps/Profiler2.h"\n#include "lib/sysdep/os/win/wutil.h"\n#include "lib/sysdep/filesystem.h"\n#include <chrono>\n#include <cstdlib>')
source = source.replace('#include <emscripten/heap.h>', '''
static double emscripten_get_now() { return timer_Time()*1000; }
// Native process memory is collected externally; this field is WASM-only.
static size_t emscripten_get_heap_size() { return 0; }
''')
source = source.replace('CLightEnv g_LightEnv;', 'extern CLightEnv g_LightEnv;')
source = source.replace('extern thread_local std::shared_ptr<Script::Context> g_ScriptContext;', '''extern thread_local std::shared_ptr<Script::Context> g_ScriptContext;
Status wutil_Init(); Status wutil_Shutdown();
Status wdir_watch_Init(); Status wdir_watch_Shutdown();
static bool nativeQuitRequested=false;
static int nativeExitStatus=0;
bool IsQuitRequested() { return nativeQuitRequested; }
void QuitEngine(int status) { nativeQuitRequested=true; nativeExitStatus=status; }
void RestartEngine() { std::puts("NATIVE_BENCHMARK_UNEXPECTED_RESTART"); QuitEngine(36); }
''')
source = source.replace('  if (!device) return 22;', '  if (!device) return 22;\n  std::printf("NATIVE_RENDERER %s\\nNATIVE_DRIVER %s\\n",device->GetName().c_str(),device->GetDriverInformation().c_str());')
source = source.replace("  gpuProfiling=MAIN_THREAD_EM_ASM_INT({return new URL(location.href).searchParams.get('gpuTimer')==='1';});", '  gpuProfiling=false;')
source = source.replace("  benchmarkMode=MAIN_THREAD_EM_ASM_INT({return new URL(location.href).searchParams.get('benchmark')==='1';});", '  benchmarkMode=true;')
for path in ['/data/mod/', '/data/public/', '/cache/', '/scenario/commands.txt']:
    source = source.replace(path, path[1:])
start = source.index('  window=SDL_CreateWindow(')
end = source.index('  if (!device) return 22;', start)
source = source[:start] + '''  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION,3);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION,3);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK,SDL_GL_CONTEXT_PROFILE_COMPATIBILITY);
  SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER,1);
  SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE,24);
  SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE,8);
  window=SDL_CreateWindow("0 A.D. pinned native scene benchmark",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,width,height,SDL_WINDOW_OPENGL|SDL_WINDOW_FULLSCREEN_DESKTOP);
  if (!window) return 21;
  device=Renderer::Backend::GL::CDevice::Create(window);
''' + source[end:]
source = source.replace(' EMSCRIPTEN_WEBGL_CONTEXT_HANDLE webgl = 0;', '')
source = source.replace('  if (webgl > 0) emscripten_webgl_destroy_context(webgl);', '')
source = source.replace('"browser",nullptr,width,height', '"native",window,width,height')
source = remove_blocks(source, '  if (emscripten_get_canvas_element_size(')
source = source.replace('  int w,h;\n', '')
start = source.index('#if !defined(WASM_SCENE_OFFSCREEN)\n  if (emscripten_webgl_commit_frame')
end = source.index('#endif', start) + len('#endif')
source = source[:start] + source[end:]
source = source[:source.index('std::unique_ptr<SceneApplication> application;')] + '''
int main(int argc, char** argv)
{
 (void)argc; (void)argv;
 std::setvbuf(stdout,nullptr,_IONBF,0);
 std::puts("NATIVE_BENCHMARK_START");
 wutil_Init(); wdir_watch_Init();
 EarlyInit(); CConfigDB::Initialise();
 int code=0;
 {
  SceneApplication application;
  application.width=1920; application.height=1080;
  code=application.Initialize();
  if (!code) {
   const char* seconds=std::getenv("SCENE_BENCHMARK_SECONDS");
   const double duration=seconds ? std::strtod(seconds,nullptr) : 1022;
   double start=0, deadline=emscripten_get_now();
   while (!application.stop && !nativeQuitRequested) {
    application.Frame();
    const double now=emscripten_get_now();
    if (application.ready && !start) start=now;
    if (start && now-start>=duration*1000) application.stop=true;
    deadline+=1000.0/60.0;
    if (deadline<now) deadline=now;
    const double delay=deadline-emscripten_get_now();
    if (delay>0) SDL_Delay(static_cast<Uint32>(delay));
   }
   code=nativeQuitRequested ? nativeExitStatus : application.exitCode;
  }
 }
 CConfigDB::Shutdown();
 g_Profiler2.Shutdown();
 wdir_watch_Shutdown(); wutil_Shutdown();
 std::printf("NATIVE_SCENE_EXIT %d\\n",code);
 return code;
}
'''
# A precompiled header must precede all engine headers on MSVC.
source = '#define MINIMAL_PCH 2\n#include "lib/precompiled.h"\n' + source
(out / 'source/main.cpp').write_text(source)
patch = ''.join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                fromfile='wasm/harness/scene-main.cpp', tofile='native-benchmark/main.cpp'))
(evidence / 'native-scene-platform.patch').write_text(patch)
(evidence / 'native-scene-build.json').write_text(json.dumps({
    'baseCommit': pin, 'windowsLibrariesSvnRevision': 28278,
    'harnessSourceSHA256': hashlib.sha256(original.encode()).hexdigest(),
    'nativeEntrySHA256': hashlib.sha256(source.encode()).hexdigest(),
    'scope': 'Original scene engine, same 37 entities/camera/seed/settings/tick; native SDL/OpenGL presentation. Not full-game acceptance.',
    'nativeEngineCompatibility': 'Missing <numbers> include only; no simulation/rendering logic changes. ENet include path supplied for lobby-disabled build.',
    'compatibilityPatch': 'native-build-compatibility.patch',
    'terrainBridge': 'native-scene-terrain-bridge.patch; same bridge as browser, original CGame fallback retained',
    'surfaceBridge': 'native-scene-surface-bridge.patch; same constructor injection as browser, desktop default retained'}, indent=2))
print(out)
