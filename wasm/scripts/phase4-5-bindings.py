"""Compare actual compile/link support; never infer engine or runtime parity."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

os.environ['EMCC_CORES'] = '2'
os.environ['BINARYEN_CORES'] = '2'
output = Path('/phase45-build')
output.mkdir(parents=True, exist_ok=True)
sdk = Path('/emsdk/upstream/emscripten')
port = sdk / 'tools/ports/emdawnwebgpu.py'
lock = json.loads(Path('/phase45-config/phase4-5-toolchain.lock.json').read_text())
if hashlib.sha256(port.read_bytes()).hexdigest() != lock['emdawnSDKPortSHA256']:
    raise SystemExit('SDK port definition differs from the toolchain lock')
report = {
    'scope': 'BINDINGS_COMPILE_LINK_ONLY', 'engineBackendIntegrated': False,
    'phase45Accepted': False,
    'emscripten': subprocess.check_output(['em++', '--version'], text=True),
    'sourceSHA256': hashlib.sha256(Path('/phase45-probes/webgpu-bindings.cpp').read_bytes()).hexdigest(),
    'emdawnPortSHA256': hashlib.sha256(port.read_bytes()).hexdigest(),
    'results': [],
}
(output / 'emdawnwebgpu.port-definition.txt').write_bytes(port.read_bytes())
license_root = sdk / 'cache/ports/emdawnwebgpu/emdawnwebgpu_pkg'
report['licenses'] = {}
for source in sorted(license_root.rglob('LICENSE')):
    relative = source.relative_to(license_root)
    destination = output / 'licenses' / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    report['licenses'][relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
for name, binding in [('legacy', '-sUSE_WEBGPU=1'), ('emdawn', '--use-port=emdawnwebgpu')]:
    for threaded in [False, True]:
        target = name + ('-pthread' if threaded else '-main')
        command = ['em++', '/phase45-probes/webgpu-bindings.cpp', binding, '-O2',
                   '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sENVIRONMENT=web,worker',
                   '-o', str(output / (target + '.mjs'))]
        if threaded:
            command += ['-pthread', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=1', '-sEXIT_RUNTIME=1']
        with (output / (target + '.log')).open('w') as log:
            run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        report['results'].append(dict(target=target, command=command, exitCode=run.returncode,
                                      runtimeVerified=False))
for threaded in [False, True]:
    target = 'emdawn-device' + ('-pthread' if threaded else '-main')
    command = ['em++', '/phase45-probes/webgpu-device.cpp', '--use-port=emdawnwebgpu', '-O2',
               '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sENVIRONMENT=web,worker', '-sEXIT_RUNTIME=1',
               '-sASSERTIONS=1', '-o', str(output / (target + '.mjs'))]
    if threaded:
        command += ['-pthread', '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=1']
    with (output / (target + '.log')).open('w') as log:
        run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    report['results'].append(dict(target=target, command=command, exitCode=run.returncode,
                                  runtimeVerified=False))
report['deviceSourceSHA256'] = hashlib.sha256(Path('/phase45-probes/webgpu-device.cpp').read_bytes()).hexdigest()
report['artifacts'] = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(output.iterdir()) if p.name.startswith(('legacy-', 'emdawn-'))
    and p.suffix in ['.mjs', '.wasm', '.log']
}
(output / 'bindings-report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
raise SystemExit(any(row['exitCode'] for row in report['results']))
