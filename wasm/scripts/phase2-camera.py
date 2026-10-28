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
sources = [root / relative for relative in [
 'graphics/GameView.cpp', 'graphics/HFTracer.cpp',
 'renderer/PostprocManager.cpp', 'renderer/SkyManager.cpp', 'lib/module_init.cpp']]
sources += [Path('/spike/wasm/harness/scene-platform.cpp')]

def compile_unit(source):
    name = 'camera_' + str(source.relative_to('/spike')).replace('/', '_')
    obj = out / 'objects' / (name + '.o')
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(flags + (['-DWSECURE_CRT'] if source.name == 'secure_crt.cpp' else []) + ['-c', str(source), '-o', str(obj)], stdout=log, stderr=subprocess.STDOUT)
    print(name, result.returncode, flush=True)
    return {'source': str(source), 'exitCode': result.returncode, 'object': str(obj)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(compile_unit, sources))
report['cameraCompile'] = results
(out / 'report.json').write_text(json.dumps(report, indent=2))
if all(r['exitCode'] == 0 for r in results):
    support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
    libraries = ['/spike/xml-wasm/lib/libxml2.a',str(sm / 'js/src/build/libjs_static.a'), str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
                 str(sm / 'build/pure_virtual/libpure_virtual.a')]
    objects_by_source = {(r['source'], 'wide' if 'terrain_' in r['object'] else 'narrow') if r['source'].endswith('/secure_crt.cpp') else r['source']: r['object'] for group in ['compile', 'foundationCompile', 'terrainCompile', 'servicesCompile', 'actorsCompile', 'supportCompile', 'closureCompile', 'mapCompile', 'cameraCompile'] for r in report[group] if r['source'] != '/spike/wasm/harness/map-link.cpp'}
    with (out / 'camera-link.log').open('w') as log:
        result = subprocess.run(['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '-Wl,--error-limit=0',
          '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-sUSE_SDL=2', *objects_by_source.values(), *libraries, *support,
          '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864', '-sSTACK_SIZE=5242880', '-sASSERTIONS=2', '-sEXIT_RUNTIME=1', '-sENVIRONMENT=node', '-lnodefs.js', '--pre-js', '/spike/wasm/harness/map-node-pre.js', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=8', '-o', str(out / 'map-replay.js')], stdout=log, stderr=subprocess.STDOUT)
    report['cameraLinkExitCode'] = result.returncode
report['cameraStatus'] = 'COMPILE_FAILED' if any(r['exitCode'] for r in results) else ('LINK_FAILED' if report.get('cameraLinkExitCode', 1) else 'LINK_PASSED_NOT_EXECUTED')
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(report['cameraStatus'])

