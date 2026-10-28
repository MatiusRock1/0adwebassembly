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
# Recompile only these two platform units after explicit browser adaptations.
task = root / 'ps/TaskManager.cpp'
task_text = task.read_text()
task_text = task_text.replace('const size_t hardware_concurrency = std::thread::hardware_concurrency();', '#if defined(__EMSCRIPTEN__)\n return MIN_WORKERS;\n#else\n const size_t hardware_concurrency = std::thread::hardware_concurrency();').replace('return hardware_concurrency ? Clamp(hardware_concurrency - 1, MIN_WORKERS, MAX_WORKERS) : MIN_WORKERS;', 'return hardware_concurrency ? Clamp(hardware_concurrency - 1, MIN_WORKERS, MAX_WORKERS) : MIN_WORKERS;\n#endif')
task.write_text(task_text)
vfs = root / 'lib/file/vfs/vfs.cpp'
vfs.write_text('#include <cstdio>\n' + vfs.read_text().replace('m_trace->NotifyLoad(pathname, size);', 'm_trace->NotifyLoad(pathname, size);\n std::printf("VFS_READ %s\\n", pathname.string8().c_str());'))
sources = [root / relative for relative in [
 'renderer/backend/CompareOp.cpp', 'ps/DllLoader.cpp', 'graphics/MapReader.cpp',
 'graphics/MapIO.cpp', 'graphics/LightEnv.cpp', 'graphics/TerrainTextureManager.cpp',
 'graphics/TerrainTextureEntry.cpp', 'graphics/TerrainProperties.cpp',
 'ps/Loader.cpp', 'lib/timer.cpp', 'ps/TaskManager.cpp', 'lib/file/vfs/vfs.cpp']]
sources += [Path('/spike/wasm/harness/map-main.cpp')]

def compile_unit(source):
    name = 'map_' + str(source.relative_to('/spike')).replace('/', '_')
    obj = out / 'objects' / (name + '.o')
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(flags + (['-DWSECURE_CRT'] if source.name == 'secure_crt.cpp' else []) + ['-c', str(source), '-o', str(obj)], stdout=log, stderr=subprocess.STDOUT)
    print(name, result.returncode, flush=True)
    return {'source': str(source), 'exitCode': result.returncode, 'object': str(obj)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(compile_unit, sources))
report['mapCompile'] = results
(out / 'report.json').write_text(json.dumps(report, indent=2))
if all(r['exitCode'] == 0 for r in results):
    support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
    libraries = ['/spike/xml-wasm/lib/libxml2.a',str(sm / 'js/src/build/libjs_static.a'), str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
                 str(sm / 'build/pure_virtual/libpure_virtual.a')]
    with (out / 'map-link.log').open('w') as log:
        result = subprocess.run(['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '-Wl,--error-limit=0',
          '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-sUSE_SDL=2', *[r['object'] for r in report['compile'] + report['foundationCompile'] + report['terrainCompile'] + report['servicesCompile'] + report['actorsCompile'] + report['supportCompile'] + report['closureCompile'] + results if r in results or r['source'] not in [str(p) for p in sources] + ['/spike/wasm/harness/map-link.cpp']], *libraries, *support,
          '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864', '-sSTACK_SIZE=5242880', '-sASSERTIONS=2', '-sEXIT_RUNTIME=1', '-sENVIRONMENT=node', '-o', str(out / 'map-replay.js')], stdout=log, stderr=subprocess.STDOUT)
    report['mapLinkExitCode'] = result.returncode
report['mapStatus'] = 'COMPILE_FAILED' if any(r['exitCode'] for r in results) else ('LINK_FAILED' if report.get('mapLinkExitCode', 1) else 'LINK_PASSED_NOT_EXECUTED')
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(report['mapStatus'])

