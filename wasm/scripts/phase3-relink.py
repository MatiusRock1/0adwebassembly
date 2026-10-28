"""Refresh only application/platform instrumentation against a recorded closure."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
os.environ['EMCC_CORES'] = '2'
os.environ['BINARYEN_CORES'] = '2'

out = Path('/spike/phase2-link')
package_out = Path('/spike/scene-browser')
manifest = json.loads((package_out / 'build-profile.json').read_text())
owned = os.environ.get('SCENE_CONTEXT', 'proxied') == 'owned'
compile_flags = manifest['compileFlags'] + (['-DWASM_SCENE_OFFSCREEN=1'] if owned else [])
bridge_path = Path('/opt/scene-player-colors.py')
if bridge_path.exists():
    spec = importlib.util.spec_from_file_location('scene_player_colors', bridge_path)
    bridge = importlib.util.module_from_spec(spec); spec.loader.exec_module(bridge)
    patch = bridge.apply_bridge(Path('/spike/phase2-source'))
    (package_out / 'scene-player-colors.patch').write_text(patch)
    color_source = '/spike/phase2-source/renderer/RenderModifiers.cpp'
    color_obj = str(out / 'objects/phase3-player-colors.o')
    with (out / 'phase3-player-colors.log').open('w') as log:
        subprocess.run(compile_flags + ['-c', color_source, '-o', color_obj], stdout=log, stderr=subprocess.STDOUT, check=True)
    report = json.loads((out / 'report.json').read_text())
    report['sceneCompile'] = [r for r in report['sceneCompile'] if r['source'] != color_source] + [dict(source=color_source, object=color_obj, exitCode=0)]
    (out / 'report.json').write_text(json.dumps(report, indent=2))
source = '/spike/wasm/harness/scene-main.cpp'
obj = str(out / 'objects/phase3-runtime.o')
with (out / 'phase3-runtime.log').open('w') as log:
    subprocess.run(compile_flags + ['-c', source, '-o', obj],
                   stdout=log, stderr=subprocess.STDOUT, check=True)
report = json.loads((out / 'report.json').read_text())
report['sceneCompile'] = [r for r in report['sceneCompile'] if r['source'] != source] + [dict(source=source, object=obj, exitCode=0)]
(out / 'report.json').write_text(json.dumps(report, indent=2))
options = [f for f in manifest['compileFlags'] if f in ['-O0', '-O2', '-O3', '-g', '-flto']]
package = Path('/opt/phase2-scene-package.py').read_text()
package = package.replace("args = ['em++',", "args = ['em++', " + ', '.join(repr(x) for x in options) + ", '-Wl,--threads=2', '--emit-symbol-map', '-gseparate-dwarf',")
if owned:
    package = package.replace("'-sOFFSCREEN_FRAMEBUFFER=1'", "'-sOFFSCREENCANVAS_SUPPORT=1', '-sOFFSCREENCANVASES_TO_PTHREAD=#canvas'")
exec(compile(package, '/opt/phase2-scene-package.py', 'exec'), {})
manifest['applicationSourceSHA256'] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
manifest['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in package_out.iterdir()
                         if p.suffix in ['.wasm', '.mjs', '.data', '.html']}
manifest['gpuTiming'] = 'optional EXT_disjoint_timer_query_webgl2, ?gpuTimer=1; -1 if unavailable'
manifest['gcTiming'] = 'original slice callback chained; nursery callback added without changing policy'
manifest['contextOwnership'] = 'experimental OffscreenCanvas worker' if owned else 'proxied main-thread WebGL2'
manifest['applicationCompileFlags'] = compile_flags
manifest['frameClock'] = 'main-thread RAF, at most one queued worker draw; timer diagnostic via ?frameClock=timer'
manifest['playerColors'] = 'authentic ICmpPlayer displayed colors, cached as native CGame'
contract_path = Path('/opt/scene_benchmark_contract.py')
if contract_path.exists():
    spec = importlib.util.spec_from_file_location('scene_contract', contract_path)
    scene_contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(scene_contract)
    pin = subprocess.check_output(['git', '-C', '/build/0ad', 'rev-parse', 'HEAD'], text=True).strip()
    manifest['benchmarkContract'] = scene_contract.contract(Path('/spike/scene-data'), Path('/scenario/commands.txt'), pin)
(package_out / 'build-profile.json').write_text(json.dumps(manifest, indent=2))
print('PHASE3_RUNTIME_RELINK_PASSED', flush=True)
