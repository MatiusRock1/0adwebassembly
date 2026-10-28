"""Package the measured map closure and link the complete browser simulation."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
root = Path('/build/0ad')
out = Path('/spike/map-browser')
out.mkdir(exist_ok=True)
report = json.loads(Path('/spike/phase2-link/report.json').read_text())
assert report['cameraLinkExitCode'] == 0
assert Path('/spike/phase2-link/map-run-exit.txt').read_text().strip() == '0'
data = Path('/spike/minimum-data')
for mod in ['mod', 'public']:
    (data/mod).mkdir(parents=True, exist_ok=True)
paths = sorted({line[9:] for line in Path('/spike/phase2-link/map-run.log').read_text().splitlines() if line.startswith('VFS_READ ') and not line[9:].startswith('cache/')})
manifest = []
for relative in paths:
    for mod in ['public', 'mod']:
        source = root / 'binaries/data/mods' / mod / relative
        if not source.is_file():
            continue
        target = data / mod / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append({'path': str(target.relative_to(data)), 'source': str(source.relative_to(root)), 'bytes': source.stat().st_size, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        break
    else:
        raise RuntimeError('Original resource missing: ' + relative)
(out/'resources.json').write_text(json.dumps({'baseCommit': '40b8794eecb9618da69e10bacffa8814c561aa51', 'files': manifest, 'totalBytes': sum(f['bytes'] for f in manifest)}, indent=2))
shutil.copy2(root/'LICENSE.md', out/'upstream-LICENSE.md')
Path('/spike/map-pre.js').write_text("(Module['preRun'] ??= []).push(() => { FS.mkdir('/cache'); FS.mkdir('/output'); });\n")
objects = {(r['source'], 'wide' if 'terrain_' in r['object'] else 'narrow') if r['source'].endswith('/secure_crt.cpp') else r['source']: r['object'] for group in ['compile', 'foundationCompile', 'terrainCompile', 'servicesCompile', 'actorsCompile', 'supportCompile', 'closureCompile', 'mapCompile', 'cameraCompile'] for r in report[group] if r['source'] != '/spike/wasm/harness/map-link.cpp'}
sm = Path('/spike/mozjs-128.13.0/build-wasm')
support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm/folder).rglob('*.o')]
libraries = ['/spike/xml-wasm/lib/libxml2.a', str(sm/'js/src/build/libjs_static.a'), str(sm/'wasm32-unknown-emscripten/release/libjsrust.a'), str(sm/'build/pure_virtual/libpure_virtual.a')]
args = ['em++', '-pthread', '-fexceptions', '-Wl,--gc-sections', '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-sUSE_SDL=2', *objects.values(), *libraries, *support, '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864', '-sSTACK_SIZE=5242880', '-sASSERTIONS=2', '-sEXIT_RUNTIME=1', '-sENVIRONMENT=web,node,worker', '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sEXPORTED_RUNTIME_METHODS=FS', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=8', '--pre-js', '/spike/map-pre.js', '--preload-file', str(data)+'@/data', '--preload-file', '/scenario@/scenario', '-o', str(out/'pyrogenesis-map.mjs')]
with (out/'link.log').open('w') as log:
    subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True)
print('BROWSER_MAP_LINK_PASSED', flush=True)
