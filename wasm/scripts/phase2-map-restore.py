"""Link and execute restoration through the original simulation serializer."""
import json
import subprocess
from pathlib import Path
root = Path('/spike/phase2-source')
sm = Path('/spike/mozjs-128.13.0/build-wasm')
out = Path('/spike/phase2-link')
adapters = Path('/spike/phase2-adapters')
flags = ['em++', '-std=c++20', '-pthread', '-fexceptions', '-O0', '-ffunction-sections', '-fdata-sections',
         '-ferror-limit=3', '-DFMT_HEADER_ONLY', '-DNDEBUG', '-DCONFIG_ENABLE_PCH=0',
         '-DCONFIG2_AUDIO=0', '-DCONFIG2_NVTT=0', '-DCONFIG2_LOBBY=0', '-DCONFIG2_FILE_ENABLE_AIO=0',
         '-DCONFIG2_GLES=1', '-sUSE_SDL=2', '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-I' + str(adapters),
         '-include', str(adapters / 'ps/Profiler2.h'), '-I' + str(root),
         '-I' + str(root / 'pch/scriptinterface'), '-I' + str(root / 'lib'),
         '-I/spike/headless/include', '-I' + str(sm / 'dist/include'),
         '-I' + str(root / 'third_party/glad/include')]

source = '/spike/wasm/harness/map-restore-main.cpp'
obj = str(out/'objects/map-restore-main.o')
with (out/'restore-compile.log').open('w') as log:
    subprocess.run(flags + ['-c', source, '-o', obj], stdout=log, stderr=subprocess.STDOUT, check=True)
report = json.loads((out/'report.json').read_text())
objects = {(r['source'], 'wide' if 'terrain_' in r['object'] else 'narrow') if r['source'].endswith('/secure_crt.cpp') else r['source']: r['object'] for group in ['compile', 'foundationCompile', 'terrainCompile', 'servicesCompile', 'actorsCompile', 'supportCompile', 'closureCompile', 'mapCompile', 'cameraCompile'] for r in report[group] if r['source'] not in ['/spike/wasm/harness/map-link.cpp', '/spike/wasm/harness/map-main.cpp']}
support = [str(p) for folder in ['mfbt','mozglue','memory'] for p in (sm/folder).rglob('*.o')]
libraries = ['/spike/xml-wasm/lib/libxml2.a',str(sm/'js/src/build/libjs_static.a'),str(sm/'wasm32-unknown-emscripten/release/libjsrust.a'),str(sm/'build/pure_virtual/libpure_virtual.a')]
with (out/'restore-link.log').open('w') as log:
    subprocess.run(['em++','-pthread','-fexceptions','-Wl,--gc-sections','--use-port=zlib','--use-port=libpng','--use-port=freetype','-sUSE_SDL=2',*objects.values(),obj,*libraries,*support,'-sALLOW_MEMORY_GROWTH=1','-sINITIAL_MEMORY=67108864','-sSTACK_SIZE=5242880','-sASSERTIONS=2','-sEXIT_RUNTIME=1','-sENVIRONMENT=node','-lnodefs.js','--pre-js','/spike/wasm/harness/map-node-pre.js','-sPROXY_TO_PTHREAD=1','-sPTHREAD_POOL_SIZE=8','-o',str(out/'map-restore.js')],stdout=log,stderr=subprocess.STDOUT,check=True)
with (out/'restore-run.log').open('w') as log:
    result = subprocess.run(['node',str(out/'map-restore.js')],stdout=log,stderr=subprocess.STDOUT,timeout=180)
passed = result.returncode == 0 and 'MAP_RESTORE_PASSED' in (out/'restore-run.log').read_text()
(out/'restore-result.json').write_text(json.dumps({'exitCode':result.returncode,'passed':passed,'checks':['exact serialized bytes after restore','original state hash after restore','same hash after one further original tick']},indent=2))
print('MAP_RESTORE_PASSED' if passed else 'MAP_RESTORE_FAILED', flush=True)
if not passed: raise SystemExit(1)
