"""Build a separate SIMD engine from the verified shared-AL control.

Keep the original optimization, floating point rules, scripts and resources.
SIMD is a compiler target feature, not a promise that every loop vectorizes.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from phase45_exception_audit import audit, dependencies

os.environ.update(EMCC_CORES='2', BINARYEN_CORES='2')
base = Path('/phase45-build/application-audio-error')
out = Path('/phase45-build/application-simd')
out.mkdir(exist_ok=True)
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
control = json.loads((base / 'compile-report.json').read_text())
assert control['status'] == 'COMPILE_PASSED_NOT_LINKED'
assert control['platformExperiment'] == 'shared-openal-error'
assert control['exceptionMode'] == 'wasm' and len(control['results']) == 483
roots = {'source': Path(control['frozenSourceRoot']), 'harness': Path(control['frozenHarnessRoot'])}
headers = json.loads(Path('/phase45-build/application-wasm-eh/header-hashes.json').read_text())
for relative, expected in headers.items():
    folder, name = relative.split('/', 1)
    assert digest(roots[folder] / name) == expected, 'Control header changed: ' + relative
for unit in control['results']:
    source = Path(unit.get('sourceFile', roots['source'] / unit['source']))
    assert unit['exitCode'] == 0 and digest(Path(unit['object'])) == unit['objectSHA256']
    assert digest(source) == unit['sourceSHA256'], 'Control source changed: ' + unit['source']

# The base directory may have last selected O2. Select and audit the immutable
# O3 reference explicitly instead of inheriting that unrelated VM experiment.
scripting = Path('/phase45-build/spidermonkey-portable-switch-o3/libjs_static.a')
assert digest(scripting) == 'dd057a4ea34a1a5028660d9992bef5b749c9116a3502828611a240c2df07b642'
dependency_audit = audit(dependencies(scripting, control['nativeCurl']['archive']))
assert dependency_audit['passed']
shutil.copytree(base / 'runtime-browser', out / 'runtime-browser', dirs_exist_ok=True)
includes = Path('/tmp/phase4-includes')
includes.mkdir(exist_ok=True)
for name in ['boost', 'enet', 'libxml']:
    target = includes / name
    if not target.exists():
        target.symlink_to(Path('/spike/headless/include') / name)
shutil.copytree('/spike/headless/include/fmt', includes / 'fmt', dirs_exist_ok=True)
fmt = includes / 'fmt/core.h'
fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))',
                                     'parse_format_string<true>(str_, checker(str_, {}))'))

previous_path = out / 'compile-report.json'
previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
cached = {unit['source']: unit for unit in previous.get('results', [])}
report = dict(control, status='IN_PROGRESS', results=[], failed=[], notAttempted=[],
              dependencyAudit=dependency_audit, jobs=2, platformExperiment='shared-openal-error-simd',
              simdEngine=True, phase45Accepted=False, buildScriptSHA256=digest(Path(__file__)),
              baseCompileReportSHA256=digest(base / 'compile-report.json'),
              scope='All 483 engine closure units target SIMD128 with original optimization/math. '
                    'Unchanged O3 portable VM and original resources. No fast-math or reduced workload.')
started = time.monotonic()
stop = threading.Event()

def compile_unit(unit):
    command = list(unit['command'])
    assert '-msimd128' not in command and '-O2' in command and '-fwasm-exceptions' in command
    assert not any(flag in command for flag in ['-ffast-math', '-Ofast', '-funsafe-math-optimizations'])
    obj = out / (unit['source'].replace('/', '_') + '.o')
    command[command.index('-o') + 1] = str(obj)
    command.insert(command.index('-c'), '-msimd128')
    identity = hashlib.sha256(json.dumps(dict(command=command, source=unit['sourceSHA256'],
                                             headers=control['sourceHeadersSHA256']), sort_keys=True).encode()).hexdigest()
    old = cached.get(unit['source'], {})
    if old.get('identity') == identity and old.get('exitCode') == 0 and obj.exists() and digest(obj) == old.get('objectSHA256'):
        return old
    if stop.is_set():
        return dict(source=unit['source'], exitCode=-1, skippedAfterFailure=True)
    log = obj.with_suffix('.log')
    begin = time.monotonic()
    with log.open('w') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    entry = dict(unit, command=command, object=str(obj), log=str(log), exitCode=result.returncode,
                 identity=identity, seconds=time.monotonic() - begin)
    if result.returncode:
        stop.set()
        print('SIMD_FAILED', unit['source'], flush=True)
    else:
        entry['objectSHA256'] = digest(obj)
    return entry

def save():
    report['seconds'] = time.monotonic() - started
    previous_path.write_text(json.dumps(report, indent=2))

save()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(compile_unit, control['results']):
        report['results'].append(result)
        if len(report['results']) % 10 == 0 or result['exitCode']:
            save()
            print('SIMD_BUILD', len(report['results']), '/', len(control['results']), round(report['seconds'], 1), flush=True)
report['failed'] = [unit['source'] for unit in report['results'] if unit['exitCode'] and not unit.get('skippedAfterFailure')]
report['notAttempted'] = [unit['source'] for unit in report['results'] if unit.get('skippedAfterFailure')]
report['status'] = 'COMPILE_FAILED' if report['failed'] or report['notAttempted'] else 'COMPILE_PASSED_NOT_LINKED'
save()
print(report['status'], len(report['results']), 'SIMD engine units', flush=True)
raise SystemExit(1 if report['failed'] or report['notAttempted'] else 0)
