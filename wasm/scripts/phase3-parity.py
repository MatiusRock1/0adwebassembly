"""Replay and restore with the optimized engine objects, compared byte for byte."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
os.environ['EMCC_CORES'] = '2'
os.environ['BINARYEN_CORES'] = '2'

out = Path('/spike/phase2-link')
report = json.loads((out / 'report.json').read_text())
manifest = json.loads(Path('/spike/scene-browser/build-profile.json').read_text())
flags = manifest['compileFlags']
objects = {}
for group in ['compile', 'foundationCompile', 'terrainCompile', 'servicesCompile',
              'actorsCompile', 'supportCompile', 'closureCompile', 'mapCompile',
              'cameraCompile', 'glCompile', 'sceneCompile']:
    for unit in report[group]:
        if Path(unit['source']).name in ['map-link.cpp', 'map-main.cpp', 'gl-main.cpp', 'scene-main.cpp']:
            continue
        key = (unit['source'], 'wide' if 'terrain_' in unit['object'] else 'narrow') if unit['source'].endswith('/secure_crt.cpp') else unit['source']
        objects[key] = unit['object']
sm = Path('/spike/mozjs-128.13.0/build-wasm')
support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm / folder).rglob('*.o')]
libraries = ['/spike/xml-wasm/lib/libxml2.a', str(sm / 'js/src/build/libjs_static.a'),
             str(sm / 'wasm32-unknown-emscripten/release/libjsrust.a'), str(sm / 'build/pure_virtual/libpure_virtual.a')]
evidence = Path('/spike/phase3-parity')
evidence.mkdir(exist_ok=True)
for folder in ['/output', '/cache']:
    Path(folder).mkdir(exist_ok=True)
results = {}
for name, source in [('replay', 'map-main.cpp'), ('restore', 'map-restore-main.cpp')]:
    obj = str(evidence / (name + '.o'))
    with (evidence / (name + '-compile.log')).open('w') as log:
        subprocess.run(flags + ['-c', '/spike/wasm/harness/' + source, '-o', obj], stdout=log, stderr=subprocess.STDOUT, check=True)
    executable = str(evidence / (name + '.js'))
    with (evidence / (name + '-link.log')).open('w') as log:
        subprocess.run(['em++', *[f for f in flags if f in ['-O0', '-O2', '-O3', '-flto']],
                        '-pthread', '-fexceptions', '-Wl,--gc-sections', '-Wl,--threads=2', '--use-port=zlib',
                        '--use-port=libpng', '--use-port=freetype', '-sUSE_SDL=2',
                        *objects.values(), obj, *libraries, *support,
                        '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864', '-sSTACK_SIZE=5242880',
                        '-sASSERTIONS=2', '-sEXIT_RUNTIME=1', '-sENVIRONMENT=node', '-lnodefs.js',
                        '--pre-js', '/spike/wasm/harness/map-node-pre.js', '-sPROXY_TO_PTHREAD=1',
                        '-sPTHREAD_POOL_SIZE=8', '-o', executable], stdout=log, stderr=subprocess.STDOUT, check=True)
    with (evidence / (name + '-run.log')).open('w') as log:
        result = subprocess.run(['node', executable], stdout=log, stderr=subprocess.STDOUT, timeout=300)
    results[name + 'ExitCode'] = result.returncode
    if result.returncode:
        raise SystemExit(name + ' failed; inspect run log')
results['checkpoints'] = []
for reference in json.loads(Path('/reference/native-checkpoints.json').read_text()):
    tick = reference['tick']
    expected = Path(f'/reference/tick-{tick:04d}.dat').read_bytes()
    actual = Path(f'/output/tick-{tick}.dat').read_bytes()
    results['checkpoints'].append({'tick': tick, 'identicalBytes': actual == expected,
                                   'sha256': hashlib.sha256(actual).hexdigest()})
results['restorePassed'] = 'MAP_RESTORE_PASSED' in (evidence / 'restore-run.log').read_text()
results['profile'] = manifest['profile']
results['passed'] = results['restorePassed'] and all(c['identicalBytes'] for c in results['checkpoints'])
(evidence / 'result.json').write_text(json.dumps(results, indent=2))
print('PHASE3_PARITY_PASSED' if results['passed'] else 'PHASE3_PARITY_FAILED', flush=True)
if not results['passed']:
    raise SystemExit(1)
