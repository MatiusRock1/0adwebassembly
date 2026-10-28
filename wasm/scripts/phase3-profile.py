"""Recompile the measured original closure; never label O0 objects as release."""
import concurrent.futures
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

profile = os.environ.get('SCENE_PROFILE', 'debug')
context = os.environ.get('SCENE_CONTEXT', 'proxied')
if context not in ['proxied', 'owned']:
    raise SystemExit('Unknown context owner')
options = {'debug': ['-O0', '-g'], 'o2': ['-O2', '-g'],
           'o3': ['-O3', '-g'], 'o3-lto': ['-O3', '-g', '-flto']}
if profile not in options:
    raise SystemExit('Unknown profile: ' + profile)
os.environ['EMCC_CORES'] = '2'
os.environ['BINARYEN_CORES'] = '2'
out = Path('/spike/phase2-link')
report = json.loads((out / 'report.json').read_text())
# Reuse the exact platform includes and feature defines of the runtime build.
scope = {}
exec(Path('/opt/phase2-scene-runtime.py').read_text().split('report = json.loads')[0], scope)
flags = [flag for flag in scope['flags'] if flag != '-O0'] + options[profile]
flags += ['-DWASM_SCENE_SCRIPT_TIMING_ENABLED=1', '-include', '/spike/wasm/harness/scene-script-timing.h']
# Observe the original boundary, with nesting protection and no changes to JS calls.
wrapper = Path('/spike/phase2-source/scriptinterface/FunctionWrapper.h')
original_wrapper = wrapper.read_text()
needle = '\t\tbool success;\n\t\tif constexpr (std::is_same_v<R, JS::MutableHandleValue>)'
assert original_wrapper.count(needle) == 1
adapted_wrapper = original_wrapper.replace(needle, '\t\tWasmSceneProfile::ScriptCallTimer wasmScriptTimer;\n' + needle)
wrapper.write_text(adapted_wrapper)
script_patch = ''.join(difflib.unified_diff(original_wrapper.splitlines(True), adapted_wrapper.splitlines(True),
                      fromfile='a/source/scriptinterface/FunctionWrapper.h', tofile='b/source/scriptinterface/FunctionWrapper.h'))
if context == 'owned':
    flags += ['-DWASM_SCENE_OFFSCREEN=1']
units = {}
for group in ['compile', 'foundationCompile', 'terrainCompile', 'servicesCompile',
              'actorsCompile', 'supportCompile', 'closureCompile', 'mapCompile',
              'cameraCompile', 'glCompile', 'sceneCompile']:
    for unit in report[group]:
        if Path(unit['source']).name in ['map-link.cpp', 'map-main.cpp', 'gl-main.cpp']:
            continue
        key = (unit['source'], 'wide' if 'terrain_' in unit['object'] else 'narrow') if unit['source'].endswith('/secure_crt.cpp') else unit['source']
        units[key] = unit

def compile_unit(unit):
    extra = ['-DWSECURE_CRT'] if unit['source'].endswith('/secure_crt.cpp') and 'terrain_' in unit['object'] else []
    with Path(unit['object'] + '.phase3.log').open('w') as log:
        subprocess.run(flags + extra + ['-c', unit['source'], '-o', unit['object']],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    print('COMPILED ' + unit['source'], flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(compile_unit, units.values()))

# Preserve assertions and numeric semantics, including in optimized profiles.
package = Path('/opt/phase2-scene-package.py').read_text()
package = package.replace("args = ['em++',", "args = ['em++', " + ', '.join(repr(x) for x in options[profile]) + ", '-Wl,--threads=2', '--emit-symbol-map', '-gseparate-dwarf',")
if context == 'owned':
    package = package.replace("'-sOFFSCREEN_FRAMEBUFFER=1'", "'-sOFFSCREENCANVAS_SUPPORT=1', '-sOFFSCREENCANVASES_TO_PTHREAD=#canvas'")
exec(compile(package, '/opt/phase2-scene-package.py', 'exec'), {})
package_out = Path('/spike/scene-browser')
(package_out / 'script-timing.patch').write_text(script_patch)
(package_out / 'scene-player-colors.patch').write_text(Path('/spike/scene-player-colors.patch').read_text())
manifest = {'profile': profile, 'compileFlags': flags, 'jobs': 2,
            'linkerThreads': 2, 'binaryenCores': 2,
            'engineUnitsRecompiled': len(units), 'assertions': 2,
            'spidermonkey': 'cached phase2 library; optimization unchanged, not LTO rebuilt',
            'dependencies': 'cached phase2 libraries; optimization unchanged',
            'contextOwnership': 'experimental OffscreenCanvas worker' if context == 'owned' else 'proxied main-thread WebGL2',
            'gpuTiming': 'optional ?gpuTimer=1; unavailable for experimental worker context',
            'frameClock': 'main-thread RAF proxies at most one draw to the original worker; timer diagnostic via ?frameClock=timer',
            'playerColors': 'authentic ICmpPlayer displayed colors cached as in native CGame; explicit scene provider avoids null desktop owner',
            'scriptTiming': 'inclusive outer native-to-JS Function::Call boundary; native callbacks and GC included, not exclusive VM time',
            'applicationSourceSHA256': hashlib.sha256(Path('/spike/wasm/harness/scene-main.cpp').read_bytes()).hexdigest(),
            'artifacts': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in package_out.iterdir() if p.suffix in ['.wasm', '.mjs', '.data', '.html']}}
spec = importlib.util.spec_from_file_location('scene_contract', '/opt/scene_benchmark_contract.py')
scene_contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(scene_contract)
pin = subprocess.check_output(['git', '-C', '/build/0ad', 'rev-parse', 'HEAD'], text=True).strip()
manifest['benchmarkContract'] = scene_contract.contract(Path('/spike/scene-data'), Path('/scenario/commands.txt'), pin)
(package_out / 'build-profile.json').write_text(json.dumps(manifest, indent=2))
print('PHASE3_PROFILE_BUILD_PASSED', flush=True)
