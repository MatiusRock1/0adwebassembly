"""Compare original monotonic-clamp semantics and concurrent maxima on Wasm CPU."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path('/workspace')
out = Path('/phase45-build/timer-monotonic-probe')
out.mkdir(exist_ok=True)
source = root / 'wasm/probes/timer-monotonic.cpp'
header = root / 'wasm/experiments/timer-monotonic/application-timer-monotonic.h'
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
command = ['em++', str(source), '-std=c++20', '-O2', '-pthread', '-fwasm-exceptions',
           '-sSUPPORT_LONGJMP=wasm', '-sPTHREAD_POOL_SIZE=8', '-sENVIRONMENT=node',
           '-sINITIAL_MEMORY=134217728', '-sALLOW_MEMORY_GROWTH=1', '-sEXIT_RUNTIME=1',
           '-sASSERTIONS=2', '-o', str(out / 'probe.js')]
report = dict(passed=False, diagnosticOnly=True, performanceAcceptance=False,
              phase45Accepted=False, sourceSHA256=digest(source), headerSHA256=digest(header),
              scope='Exact sequential clamp outputs and concurrent maximum invariants; CPU timings are not game FPS evidence.',
              command=command)
try:
    with (out / 'compile.log').open('w') as log:
        compiled = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    report['compileExitCode'] = compiled.returncode
    assert compiled.returncode == 0, 'Timer probe compile failed; inspect compile.log'
    result = subprocess.run(['node', str(out / 'probe.js')], capture_output=True, text=True, timeout=120)
    report.update(exitCode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    (out / 'runtime.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, 'Timer probe failed; inspect runtime.log'
    report['result'] = json.loads(result.stdout.strip().splitlines()[-1])
    assert report['result']['passed'] and report['result']['checks'] == 10 and report['result']['lockFree']
    report['artifacts'] = {p.name: digest(p) for p in out.glob('probe.*')}
    report['passed'] = True
except Exception as error:
    report['failure'] = str(error)
finally:
    (out / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k: report.get(k) for k in ['passed', 'failure', 'result']}, indent=2), flush=True)
raise SystemExit(0 if report['passed'] else 1)
