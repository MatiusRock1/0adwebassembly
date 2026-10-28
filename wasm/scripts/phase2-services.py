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
for filename, structure, methods in [('Profile.h', 'struct CProfileManager {', 'void StructuralReset() {}'), ('CLogger.h', 'struct CLogger {', 'template<typename... T> void Render(T&&...) {}'), ('Profiler2.h', 'struct HeadlessProfiler {', 'template<typename... T> void RecordGPUFrameStart(T&&...) {}\n template<typename... T> void RecordGPUFrameEnd(T&&...) {}')]:
    header = adapters / 'ps' / filename
    header.write_text(header.read_text().replace(structure, structure + '\n ' + methods))
profiler.write_text(profiler.read_text() + '\n#define PROFILE3_GPU(...) ((void)0)\n')
flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-O0', '-ffunction-sections', '-fdata-sections',
         '-ferror-limit=3', '-DFMT_HEADER_ONLY', '-DNDEBUG', '-DCONFIG_ENABLE_PCH=0',
         '-DCONFIG2_AUDIO=0', '-DCONFIG2_NVTT=0', '-DCONFIG2_LOBBY=0', '-DCONFIG2_FILE_ENABLE_AIO=0',
         '-DCONFIG2_GLES=1', '-sUSE_SDL=2', '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-I' + str(adapters),
         '-include', str(adapters / 'ps/Profiler2.h'), '-I' + str(root),
         '-I' + str(root / 'pch/scriptinterface'), '-I' + str(root / 'lib'),
         '-I/spike/headless/include', '-I' + str(sm / 'dist/include'),
         '-I' + str(root / 'third_party/glad/include')]
sources = [root / relative for relative in [
 'graphics/Model.cpp', 'graphics/ModelAbstract.cpp', 'graphics/Decal.cpp',
 'graphics/Unit.cpp', 'graphics/UnitAnimation.cpp', 'graphics/UnitManager.cpp',
 'graphics/Overlay.cpp', 'graphics/ParticleManager.cpp', 'graphics/TextureManager.cpp',
 'renderer/TerrainOverlay.cpp', 'renderer/WaterManager.cpp',
 'renderer/Renderer.cpp', 'renderer/SceneRenderer.cpp', 'renderer/RenderingOptions.cpp',
 'ps/Util.cpp', 'ps/Pyrogenesis.cpp', 'ps/Game.cpp',
 'soundmanager/SoundManager.cpp', 'lib/tex/tex.cpp', 'lib/tex/tex_codec.cpp',
 'lib/tex/tex_bmp.cpp', 'lib/tex/tex_dds.cpp', 'lib/tex/tex_png.cpp', 'lib/tex/tex_tga.cpp']]

def compile_unit(source):
    name = 'services_' + str(source.relative_to('/spike')).replace('/', '_')
    obj = out / 'objects' / (name + '.o')
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(flags + (['-DWSECURE_CRT'] if source.name == 'secure_crt.cpp' else []) + ['-c', str(source), '-o', str(obj)], stdout=log, stderr=subprocess.STDOUT)
    print(name, result.returncode, flush=True)
    return {'source': str(source), 'exitCode': result.returncode, 'object': str(obj)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(compile_unit, sources))
report['servicesCompile'] = results
(out / 'report.json').write_text(json.dumps(report, indent=2))
if all(r['exitCode'] == 0 for r in results):
    support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
    libraries = [str(sm / 'js/src/build/libjs_static.a'), str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
                 str(sm / 'build/pure_virtual/libpure_virtual.a')]
    with (out / 'services-link.log').open('w') as log:
        result = subprocess.run(['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '-Wl,--error-limit=0',
          '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-sUSE_SDL=2', *[r['object'] for r in report['compile'] + report['foundationCompile'] + report['terrainCompile'] + results], *libraries, *support,
          '-o', str(out / 'map-link.js')], stdout=log, stderr=subprocess.STDOUT)
    report['servicesLinkExitCode'] = result.returncode
report['servicesStatus'] = 'COMPILE_FAILED' if any(r['exitCode'] for r in results) else ('LINK_FAILED' if report.get('servicesLinkExitCode', 1) else 'LINK_PASSED_NOT_EXECUTED')
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(report['servicesStatus'])

