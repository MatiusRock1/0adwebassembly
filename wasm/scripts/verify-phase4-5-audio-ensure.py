"""CPU verification of the actual bounded audio check queue in Wasm pthreads."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

os.environ.update(EMCC_CORES='2', BINARYEN_CORES='2')
root = Path('/workspace')
out = Path('/phase45-build/audio-ensure-probe')
out.mkdir(exist_ok=True)
source = root/'wasm/probes/application-audio-ensure.cpp'
header = root/'wasm/experiments/audio-worker/application-audio-ensure.h'
command = ['em++', '-O2', '-std=c++20', '-pthread', '-fwasm-exceptions',
           '-sSUPPORT_LONGJMP=wasm', '-I'+str(header.parent), str(source),
           '-sPROXY_TO_PTHREAD=1', '-sPTHREAD_POOL_SIZE=4', '-sENVIRONMENT=node',
           '-sEXIT_RUNTIME=1', '-sASSERTIONS=2', '-o', str(out/'probe.js')]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
report = dict(passed=False, diagnosticOnly=True, performanceAcceptance=False,
              command=command, inputs={str(p): digest(p) for p in [source, header]})
try:
    with (out/'build.log').open('w') as log:
        build = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    report['compileExitCode'] = build.returncode
    assert build.returncode == 0, 'Inspect build.log'
    run = subprocess.run(['node', str(out/'probe.js')], capture_output=True, text=True, timeout=40)
    report.update(exitCode=run.returncode, stdout=run.stdout, stderr=run.stderr)
    assert run.returncode == 0, 'Queue probe failed'
    report['result'] = json.loads(run.stdout.strip().splitlines()[-1])
    assert report['result']['passed'] and report['result']['checks'] == 10
    report['passed'] = True
except Exception as error:
    report['failure'] = str(error)
finally:
    (out/'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k: report.get(k) for k in ['passed', 'failure', 'result']}, indent=2), flush=True)
raise SystemExit(0 if report['passed'] else 1)
