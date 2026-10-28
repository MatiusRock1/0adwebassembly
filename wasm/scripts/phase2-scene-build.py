"""Compile original terrain and task support after the foundation probe."""
import concurrent.futures
import json
import subprocess
from pathlib import Path
import shutil
shutil.copytree('/usr/include/enet', '/spike/headless/include/enet', dirs_exist_ok=True)
root = Path('/spike/phase2-source')
sm = Path('/spike/mozjs-128.13.0/build-wasm')
out = Path('/spike/phase2-link')
report = json.loads((out / 'report.json').read_text())
adapters = Path('/spike/phase2-adapters')
profiler = adapters / 'ps/Profiler2.h'
profile_text = profiler.read_text()
if 'RegisterCurrentThread' not in profile_text:
    profiler.write_text(profile_text.replace('struct HeadlessProfiler {', 'struct HeadlessProfiler {\n  template<typename T> void RegisterCurrentThread(const T&) {}'))
flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-O0', '-ffunction-sections', '-fdata-sections',
         '-ferror-limit=3', '-DFMT_HEADER_ONLY', '-DNDEBUG', '-DCONFIG_ENABLE_PCH=0',
         '-DCONFIG2_AUDIO=0', '-DCONFIG2_NVTT=0', '-DCONFIG2_LOBBY=0', '-DCONFIG2_FILE_ENABLE_AIO=0',
         '-DCONFIG2_GLES=1', '-sUSE_SDL=2', '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-I' + str(adapters),
         '-include', str(adapters / 'ps/Profiler2.h'), '-I' + str(root),
         '-I' + str(root / 'pch/scriptinterface'), '-I' + str(root / 'lib'),
         '-I/spike/headless/include', '-I' + str(sm / 'dist/include'),
         '-I' + str(root / 'third_party/glad/include')]
# Inject explicit presentation dependencies; existing native constructor delegates.
header = root / 'renderer/Renderer.h'
text = header.read_text()
text = text.replace('#include "ps/Singleton.h"', '#include "ps/Singleton.h"\n#include "ps/Input.h"')
text = text.replace('CRenderer(Renderer::Backend::IDevice* device);', 'CRenderer(Renderer::Backend::IDevice* device);\n CRenderer(Renderer::Backend::IDevice* device, Input::Manager& inputManager, uint32_t width, uint32_t height);')
header.write_text(text)
renderer = root / 'renderer/Renderer.cpp'
text = renderer.read_text()
old = 'Input::Handler<InputHandler> m_InputHandler{g_VideoMode.m_InputManager, Input::Slot::SCREENSHOT,\n\t\t{m_ScreenShotType}};'
assert old in text
text = text.replace(old, 'Input::Handler<InputHandler> m_InputHandler;')
text = text.replace('Internals(Renderer::Backend::IDevice* device) :', 'Internals(Renderer::Backend::IDevice* device, Input::Manager& inputManager) :')
text = text.replace('postprocManager(device), sceneRenderer(device), fontManager(device)', 'postprocManager(device), sceneRenderer(device), fontManager(device), m_InputHandler(inputManager, Input::Slot::SCREENSHOT, {m_ScreenShotType})')
text = text.replace('CRenderer::CRenderer(Renderer::Backend::IDevice* device)\n{', 'CRenderer::CRenderer(Renderer::Backend::IDevice* device) : CRenderer(device, g_VideoMode.m_InputManager, g_VideoMode.GetWindowWidth(), g_VideoMode.GetWindowHeight()) {}\n\nCRenderer::CRenderer(Renderer::Backend::IDevice* device, Input::Manager& inputManager, uint32_t width, uint32_t height)\n{')
text = text.replace('std::make_unique<Internals>(device);', 'std::make_unique<Internals>(device, inputManager);')
text = text.replace('g_ProfileViewer.AddRootTable(&m->profileTable);\n\tg_ProfileViewer.AddRootTable(&m->backendProfileTable);', 'if (CProfileViewer::IsInitialised()) {\n g_ProfileViewer.AddRootTable(&m->profileTable);\n g_ProfileViewer.AddRootTable(&m->backendProfileTable);\n }')
text = text.replace('Open(g_VideoMode.GetWindowWidth(), g_VideoMode.GetWindowHeight());', 'Open(width, height);')
renderer.write_text(text)
# Match the explicit render surface rather than the absent desktop VideoMode.
silhouette = root / 'renderer/SilhouetteRenderer.cpp'
silhouette.write_text(silhouette.read_text().replace('g_VideoMode.GetWindowHeight()', 'g_Renderer.GetHeight()').replace('g_VideoMode.GetWindowWidth()', 'g_Renderer.GetWidth()'))
# WebGL 2 requires sized depth texture formats (the upstream GLES path targets ES 2).
texture = root / 'renderer/backend/gl/Texture.cpp'
text = texture.read_text()
old = """case Format::D16_UNORM: [[fallthrough]];
		case Format::D24_UNORM: [[fallthrough]];
		case Format::D32_SFLOAT:
			internalFormat = GL_DEPTH_COMPONENT;
			pixelFormat = GL_DEPTH_COMPONENT;
			pixelType = GL_UNSIGNED_SHORT;
			break;"""
assert old in text
text = text.replace(old, """case Format::D16_UNORM:
            internalFormat = GL_DEPTH_COMPONENT16; pixelFormat = GL_DEPTH_COMPONENT; pixelType = GL_UNSIGNED_SHORT; break;
        case Format::D24_UNORM:
            internalFormat = 0x81A6 /* GL_DEPTH_COMPONENT24, GLES3 */; pixelFormat = GL_DEPTH_COMPONENT; pixelType = GL_UNSIGNED_INT; break;
        case Format::D32_SFLOAT:
            internalFormat = 0x8CAC /* GL_DEPTH_COMPONENT32F, GLES3 */; pixelFormat = GL_DEPTH_COMPONENT; pixelType = GL_FLOAT; break;""")
text = text.replace('internalFormat = GL_SRGB_ALPHA_EXT;', 'internalFormat = 0x8C43 /* GL_SRGB8_ALPHA8, WebGL 2 */;')
# WebGL has no CLAMP_TO_BORDER or texture border colour API.
# Edge sampling is sufficient for this scene's transparent selection/territory margins;
# general border-colour emulation remains a later renderer feature.
text = text.replace('case Sampler::AddressMode::CLAMP_TO_BORDER: return GL_CLAMP_TO_BORDER;', 'case Sampler::AddressMode::CLAMP_TO_BORDER: return GL_CLAMP_TO_EDGE;')
text = text.replace('glTexParameterfv(target, GL_TEXTURE_BORDER_COLOR, borderColor.AsFloatArray().data());', '(void)borderColor; // WebGL border colour is unsupported; edge fallback above.')
texture.write_text(text)
# Temporary diagnostics around native initialization, retained in the build snapshot.
objects_source = root / 'graphics/ObjectManager.cpp'
text = objects_source.read_text().replace('#include "ObjectManager.h"', '#include "ObjectManager.h"\n#include <cstdio>')
text = text.replace('m_QualityHook =', 'std::puts("SCENE_ACTOR_QUALITY_HOOK_BEGIN"); m_QualityHook =', 1)
text = text.replace('m_VariantDiversityHook =', 'std::puts("SCENE_ACTOR_QUALITY_HOOK_END"); m_VariantDiversityHook =', 1)
text = text.replace('if (!g_Xeromyces.AddValidator', 'std::puts("SCENE_ACTOR_VALIDATOR_BEGIN"); if (!g_Xeromyces.AddValidator', 1)
text = text.replace('CObjectManager::~CObjectManager()', 'CObjectManager::~CObjectManager()')
text = text.replace('const int quality{g_ConfigDB.Get("max_actor_quality", 0)};', 'std::puts("SCENE_QUALITY_GET_BEGIN"); const int quality{g_ConfigDB.Get("max_actor_quality", 0)}; std::printf("SCENE_QUALITY_GET_END %d %d\\n",quality,int(m_QualityLevel));')
text = text.replace('m_Simulation.Interpolate(0.f, 0.f, 0.f);', 'std::puts("SCENE_QUALITY_INTERPOLATE_BEGIN"); m_Simulation.Interpolate(0.f, 0.f, 0.f); std::puts("SCENE_QUALITY_INTERPOLATE_END");')
objects_source.write_text(text)
# Supply the authentic terrain to water rendering without requiring the desktop CGame owner.
water_header = root / 'renderer/WaterManager.h'
text = water_header.read_text()
text = text.replace('class WaterManager', 'class CTerrain;\n\nclass WaterManager', 1)
text = text.replace('public:', 'public:\n void SetTerrain(const CTerrain* terrain) { m_ExplicitTerrain = terrain; }', 1)
end = text.rfind('};')
text = text[:end] + '\nprivate:\n const CTerrain* m_ExplicitTerrain = nullptr;\n' + text[end:]
water_header.write_text(text)
water_source = root / 'renderer/WaterManager.cpp'
water_source.write_text(water_source.read_text().replace('g_Game->GetWorld()->GetTerrain()', '(m_ExplicitTerrain ? *m_ExplicitTerrain : g_Game->GetWorld()->GetTerrain())'))
# WebGL does not expose mapped buffer memory. Keep original vertex generation
# and orphaning, but upload the generated staging bytes with BufferSubData.
command_source = root / 'renderer/backend/gl/DeviceCommandContext.cpp'
text = command_source.read_text()
needle = '\tglBufferData(target, bufferSize, nullptr, GL_DYNAMIC_DRAW);'
assert needle in text
text = text.replace(needle, needle + """
#if defined(__EMSCRIPTEN__)
    ENSURE(dataOffset <= bufferSize && dataSize <= bufferSize - dataOffset);
    std::vector<std::uint8_t> staging(dataSize);
    uploadFunction(staging.data());
    glBufferSubData(target, dataOffset, dataSize, staging.data());
    return;
#endif
""", 1)
text = '#include <vector>\n' + text
command_source.write_text(text)
# The original 24-bit fallback asserts grey although this branch is RGB.
# Preserve the engine's DXT decompressor; expand RGB when an sRGB RGBA format is needed.
texture_manager = root / 'graphics/TextureManager.cpp'
text = texture_manager.read_text()
old = """case 24:
		ENSURE(grey);
		ENSURE(!alpha);
		ENSURE(!sRGB);"""
assert old in text
text = text.replace(old, """case 24:
        ENSURE(!grey);
        ENSURE(!alpha);
        if (sRGB) {
            ENSURE(textureData.transform_to(textureData.m_Flags | TEX_ALPHA) >= 0);
            return Renderer::Backend::Format::R8G8B8A8_SRGB;
        }""")
texture_manager.write_text(text)
# Snapshot the platform adaptation for human review.
(out / 'renderer-explicit-surface.h').write_text(header.read_text())
(out / 'renderer-explicit-surface.cpp').write_text(renderer.read_text())
import difflib
patch = []
for relative in ['renderer/Renderer.h', 'renderer/Renderer.cpp', 'renderer/SilhouetteRenderer.cpp', 'renderer/backend/gl/Texture.cpp', 'renderer/backend/gl/DeviceCommandContext.cpp', 'renderer/WaterManager.h', 'renderer/WaterManager.cpp', 'graphics/ObjectManager.cpp', 'graphics/TextureManager.cpp']:
    original = Path('/build/0ad/source') / relative
    adapted = root / relative
    patch.extend(difflib.unified_diff(original.read_text().splitlines(True), adapted.read_text().splitlines(True), fromfile='a/source/' + relative, tofile='b/source/' + relative))
(out / 'scene-platform.patch').write_text(''.join(patch))
existing = {r['source'] for group in report.values() if isinstance(group, list) for r in group if isinstance(r, dict) and 'source' in r}
sources = [p for folder in ['renderer', 'graphics'] for p in (root/folder).glob('*.cpp') if str(p) not in existing and p.name not in ['CameraController.cpp', 'CinemaManager.cpp', 'MapGenerator.cpp', 'MapWriter.cpp', 'ICameraController.cpp']]
sources += [root/'renderer/Renderer.cpp', root/'ps/Input.cpp', root/'ps/ProfileViewer.cpp', root/'third_party/mikktspace/mikktspace.cpp', root/'third_party/mikktspace/weldmesh.cpp']
sources += [root/'graphics/TextureManager.cpp', root/'renderer/backend/gl/DeviceCommandContext.cpp', root/'renderer/WaterManager.cpp', root/'graphics/ObjectManager.cpp', root/'renderer/backend/gl/Texture.cpp', Path('/spike/wasm/harness/scene-main.cpp')]

def compile_unit(source):
    name = 'scene_' + str(source.relative_to('/spike')).replace('/', '_')
    obj = out / 'objects' / (name + '.o')
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(flags + (['-DWSECURE_CRT'] if source.name == 'secure_crt.cpp' else []) + ['-c', str(source), '-o', str(obj)], stdout=log, stderr=subprocess.STDOUT)
    print(name, result.returncode, flush=True)
    return {'source': str(source), 'exitCode': result.returncode, 'object': str(obj)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(compile_unit, sources))
report['sceneCompile'] = results
(out / 'report.json').write_text(json.dumps(report, indent=2))
if all(r['exitCode'] == 0 for r in results):
    support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
    libraries = ['/spike/xml-wasm/lib/libxml2.a',str(sm / 'js/src/build/libjs_static.a'), str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
                 str(sm / 'build/pure_virtual/libpure_virtual.a')]
    objects_by_source = {(r['source'], 'wide' if 'terrain_' in r['object'] else 'narrow') if r['source'].endswith('/secure_crt.cpp') else r['source']: r['object'] for group in ['compile', 'foundationCompile', 'terrainCompile', 'servicesCompile', 'actorsCompile', 'supportCompile', 'closureCompile', 'mapCompile', 'cameraCompile', 'glCompile', 'sceneCompile'] for r in report[group] if r['source'] not in ['/spike/wasm/harness/map-link.cpp', '/spike/wasm/harness/map-main.cpp', '/spike/wasm/harness/gl-main.cpp']}
    with (out / 'scene-link.log').open('w') as log:
        result = subprocess.run(['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '-Wl,--error-limit=0',
          '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-sUSE_SDL=2', *objects_by_source.values(), *libraries, *support,
          '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864', '-sSTACK_SIZE=5242880', '-sASSERTIONS=2', '-sEXIT_RUNTIME=1', '-sENVIRONMENT=web,worker', '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sMIN_WEBGL_VERSION=2', '-sMAX_WEBGL_VERSION=2', '-sFULL_ES3=1', '-sOFFSCREEN_FRAMEBUFFER=1',  '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=8', '-o', str(out / 'pyrogenesis-scene.mjs')], stdout=log, stderr=subprocess.STDOUT)
    report['sceneLinkExitCode'] = result.returncode
report['sceneStatus'] = 'COMPILE_FAILED' if any(r['exitCode'] for r in results) else ('LINK_FAILED' if report.get('sceneLinkExitCode', 1) else 'LINK_PASSED_NOT_EXECUTED')
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(report['sceneStatus'])

