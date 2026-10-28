"""Package the measured map closure and link the complete browser simulation."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
root = Path('/build/0ad')
out = Path('/spike/scene-browser')
out.mkdir(exist_ok=True)
if (out/'scene.html').exists(): shutil.copy2(out/'scene.html',out/'index.html')
report = json.loads(Path('/spike/phase2-link/report.json').read_text())
assert report['sceneLinkExitCode'] == 0
for mod in ['mod', 'public']:
    source = root/'binaries/data/mods'/mod/'shaders'
    if source.is_dir(): shutil.copytree(source, Path('/spike/scene-data')/mod/'shaders', dirs_exist_ok=True)
# Engine-base resources include original schemas, default sky and fallback materials.
shutil.copytree(root/'binaries/data/mods/mod/art', Path('/spike/scene-data/mod/art'), dirs_exist_ok=True)
Path('/spike/scene-pre.js').write_text("(Module['preRun'] ??= []).push(() => { FS.mkdir('/cache'); FS.mkdir('/output'); });\n")
objects = {(r['source'], 'wide' if 'terrain_' in r['object'] else 'narrow') if r['source'].endswith('/secure_crt.cpp') else r['source']: r['object'] for group in ['compile', 'foundationCompile', 'terrainCompile', 'servicesCompile', 'actorsCompile', 'supportCompile', 'closureCompile', 'mapCompile', 'cameraCompile', 'glCompile', 'sceneCompile'] for r in report[group] if r['source'] not in ['/spike/wasm/harness/map-link.cpp', '/spike/wasm/harness/map-main.cpp', '/spike/wasm/harness/gl-main.cpp']}
sm = Path('/spike/mozjs-128.13.0/build-wasm')
support = [str(p) for folder in ['mfbt', 'mozglue', 'memory'] for p in (sm/folder).rglob('*.o')]
libraries = ['/spike/xml-wasm/lib/libxml2.a', str(sm/'js/src/build/libjs_static.a'), str(sm/'wasm32-unknown-emscripten/release/libjsrust.a'), str(sm/'build/pure_virtual/libpure_virtual.a')]
args = ['em++', '--profiling-funcs', '-pthread', '-fexceptions', '-Wl,--gc-sections', '--use-port=zlib', '--use-port=libpng', '--use-port=freetype', '-sUSE_SDL=2', *objects.values(), *libraries, *support, '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864', '-sSTACK_SIZE=5242880', '-sASSERTIONS=2', '-sEXIT_RUNTIME=1', '-sENVIRONMENT=web,worker', '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sMIN_WEBGL_VERSION=2', '-sMAX_WEBGL_VERSION=2', '-sFULL_ES3=1', '-sOFFSCREEN_FRAMEBUFFER=1', '-sEXPORTED_RUNTIME_METHODS=FS,PThread', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=8', '--pre-js', '/spike/scene-pre.js', '--preload-file', '/spike/scene-data@/data', '--preload-file', '/scenario@/scenario', '-o', str(out/'pyrogenesis-scene.mjs')]
with (out/'link.log').open('w') as log:
    subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True)
print('BROWSER_SCENE_LINK_PASSED', flush=True)
