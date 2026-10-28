"""Compile and link the facade with the full original component registry.
Failures are exported as diagnostic evidence, never treated as a working map.
"""
import concurrent.futures
import json
import subprocess
import shutil
from pathlib import Path

root = Path('/spike/phase2-source')
sm = Path('/spike/mozjs-128.13.0/build-wasm')
out = Path('/spike/phase2-link')
objects = out / 'objects'
objects.mkdir(parents=True, exist_ok=True)
adapters = Path('/spike/phase2-adapters')
shutil.copytree('/spike/wasm/harness/adapters', adapters, dirs_exist_ok=True)
profile = adapters / 'ps/Profile.h'
profile.write_text(profile.read_text().replace('void Stop() {}', 'void Stop() {}\n  void Turn() {}'))
profiler2 = adapters / 'ps/Profiler2.h'
profiler2.write_text(profiler2.read_text() + '\n#define PROFILE2_EVENT(...) ((void)0)\n')

flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-O0', '-ffunction-sections', '-fdata-sections',
         '-ferror-limit=3', '-DFMT_HEADER_ONLY', '-DNDEBUG', '-DCONFIG_ENABLE_PCH=0',
         '-DCONFIG2_AUDIO=0', '-DCONFIG2_NVTT=0', '-DCONFIG2_LOBBY=0', '-DCONFIG2_FILE_ENABLE_AIO=0',
         '-DCONFIG2_GLES=1', '-sUSE_SDL=2', '-I' + str(adapters), '-include', str(adapters / 'ps/Profiler2.h'),
         '-I' + str(root), '-I' + str(root / 'pch/scriptinterface'), '-I' + str(root / 'lib'),
         '-I/spike/headless/include', '-I' + str(sm / 'dist/include'),
         '-I' + str(root / 'third_party/glad/include')]
sources = sorted(p for p in (root / 'simulation2').rglob('*.cpp') if not {'tests', 'docs'}.intersection(p.parts))
sources += list((root / 'scriptinterface').glob('*.cpp'))
sources += [root / 'ps/scripting/JSInterface_VFS.cpp', root / 'lib/file/vfs/vfs.cpp',
            root / 'lib/file/io/io.cpp', Path('/spike/wasm/harness/map-link.cpp'),
            Path('/spike/wasm/harness/platform.cpp')]

def compile_unit(source):
    name = str(source.relative_to('/spike')).replace('/', '_')
    obj = objects / (name + '.o')
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(flags + ['-c', str(source), '-o', str(obj)], stdout=log, stderr=subprocess.STDOUT)
    print(f'{name}: {result.returncode}', flush=True)
    return {'source': str(source), 'exitCode': result.returncode, 'object': str(obj)}

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(compile_unit, sources))
report = {'kind': 'integration-probe-not-a-map-runtime', 'jobs': 2, 'compile': results}
if all(r['exitCode'] == 0 for r in results):
    support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
    libraries = [str(sm / 'js/src/build/libjs_static.a'), str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'),
                 str(sm / 'build/pure_virtual/libpure_virtual.a')]
    with (out / 'link.log').open('w') as log:
        result = subprocess.run(['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '--use-port=zlib',
                    *[r['object'] for r in results], *libraries, *support, '-o', str(out / 'map-link.js')],
                    stdout=log, stderr=subprocess.STDOUT)
    report['linkExitCode'] = result.returncode
    report['status'] = 'LINK_PASSED_NOT_EXECUTED' if result.returncode == 0 else 'LINK_FAILED'
else:
    report['status'] = 'COMPILE_FAILED'
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(report['status'])
