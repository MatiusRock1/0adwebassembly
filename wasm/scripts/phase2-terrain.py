"""Compile original terrain and task support after the foundation probe."""
import concurrent.futures
import json
import subprocess
from pathlib import Path
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
         '-DCONFIG2_GLES=1', '-sUSE_SDL=2', '--use-port=zlib', '-I' + str(adapters),
         '-include', str(adapters / 'ps/Profiler2.h'), '-I' + str(root),
         '-I' + str(root / 'pch/scriptinterface'), '-I' + str(root / 'lib'),
         '-I/spike/headless/include', '-I' + str(sm / 'dist/include'),
         '-I' + str(root / 'third_party/glad/include')]
sources = [root / relative for relative in [
  'graphics/Camera.cpp', 'graphics/Color.cpp', 'graphics/Terrain.cpp',
  'graphics/HeightMipmap.cpp', 'graphics/Patch.cpp', 'graphics/MiniPatch.cpp',
  'graphics/TerritoryBoundary.cpp', 'ps/TaskManager.cpp',
  'ps/XMB/XMBStorage.cpp', 'ps/XMB/XMBData.cpp',
  'lib/byte_order.cpp', 'lib/path.cpp', 'lib/fnv_hash.cpp',
  'lib/sysdep/os/unix/ufilesystem.cpp', 'lib/secure_crt.cpp']]
existing = {r['source'] for r in report['compile'] + report['foundationCompile']}
sources = [p for p in sources if str(p) not in existing or p.name == 'secure_crt.cpp']

def compile_unit(source):
    name = 'terrain_' + str(source.relative_to('/spike')).replace('/', '_')
    obj = out / 'objects' / (name + '.o')
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(flags + (['-DWSECURE_CRT'] if source.name == 'secure_crt.cpp' else []) + ['-c', str(source), '-o', str(obj)], stdout=log, stderr=subprocess.STDOUT)
    print(name, result.returncode, flush=True)
    return {'source': str(source), 'exitCode': result.returncode, 'object': str(obj)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(compile_unit, sources))
report['terrainCompile'] = results
(out / 'report.json').write_text(json.dumps(report, indent=2))
if all(r['exitCode'] == 0 for r in results):
    support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
    libraries = [str(sm / 'js/src/build/libjs_static.a'), str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
                 str(sm / 'build/pure_virtual/libpure_virtual.a')]
    with (out / 'terrain-link.log').open('w') as log:
        result = subprocess.run(['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '-Wl,--error-limit=0',
          '--use-port=zlib', '-sUSE_SDL=2', *[r['object'] for r in report['compile'] + report['foundationCompile'] + results], *libraries, *support,
          '-o', str(out / 'map-link.js')], stdout=log, stderr=subprocess.STDOUT)
    report['terrainLinkExitCode'] = result.returncode
report['terrainStatus'] = 'COMPILE_FAILED' if any(r['exitCode'] for r in results) else ('LINK_FAILED' if report.get('terrainLinkExitCode', 1) else 'LINK_PASSED_NOT_EXECUTED')
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(report['terrainStatus'])

