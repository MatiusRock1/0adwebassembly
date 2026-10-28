"""Private shared-AL control with only its monotonic maximum made lock-free."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

started = time.monotonic()
base = Path('/phase45-build/application-audio-error')
out = Path('/phase45-build/application-timer-monotonic')
out.mkdir(exist_ok=True)
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = json.loads((base / 'compile-report.json').read_text())
assert report['status'] == 'COMPILE_PASSED_NOT_LINKED' and report['exceptionMode'] == 'wasm'
assert report['platformExperiment'] == 'shared-openal-error'
assert len(report['results']) == 483 and report['dependencyAudit']['passed']
roots = {'source': Path(report['frozenSourceRoot']), 'harness': Path(report['frozenHarnessRoot'])}
headers = json.loads((Path('/phase45-build/application-wasm-eh') / 'header-hashes.json').read_text())
for relative, expected in headers.items():
    folder, name = relative.split('/', 1)
    assert digest(roots[folder] / name) == expected, 'Control header changed: ' + relative
for unit in report['results']:
    assert unit['exitCode'] == 0 and '-fwasm-exceptions' in unit['command']
    assert digest(Path(unit['object'])) == unit['objectSHA256'], 'Control object changed: ' + unit['source']
    path = Path(unit['sourceFile']) if unit.get('sourceFile') else roots['source'] / unit['source']
    assert digest(path) == unit['sourceSHA256'], 'Control source changed: ' + unit['source']

original = roots['source'] / 'lib/timer.cpp'
before = original.read_text()
old = '''static std::mutex ensure_monotonic_mutex;
// NB: does not guarantee strict monotonicity - callers must avoid
// dividing by the difference of two equal times.
static void EnsureMonotonic(double& newTime)
{
	std::lock_guard<std::mutex> lock(ensure_monotonic_mutex);
	static double maxTime;
	maxTime = std::max(maxTime, newTime);
	newTime = maxTime;
}'''
new = '''static WasmApplication::MonotonicClock monotonicClock;
// Same non-strict global maximum as the original; the time source is unchanged.
static void EnsureMonotonic(double& newTime)
{
	newTime = monotonicClock.Publish(newTime);
}'''
assert before.count(old) == 1 and before.count('#include <mutex>') == 1
after = before.replace('#include <mutex>', '#include "application-timer-monotonic.h"', 1).replace(old, new, 1)
private = out / 'source/lib'
private.mkdir(parents=True, exist_ok=True)
source = private / 'timer.cpp'
source.write_text(after)
header = private / 'application-timer-monotonic.h'
shutil.copy2('/workspace/wasm/experiments/timer-monotonic/application-timer-monotonic.h', header)
probe = json.loads(Path('/phase45-build/timer-monotonic-probe/report.json').read_text())
assert probe['passed'] and probe['result']['checks'] == 10 and probe['headerSHA256'] == digest(header)

# Reproduce the immutable control's container-local include preparation.
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
index = next(i for i, unit in enumerate(report['results']) if unit['source'] == 'lib/timer.cpp')
command = list(report['results'][index]['command'])
assert '-O2' in command and '-sSUPPORT_LONGJMP=wasm' in command
target = out / 'timer.o'
command[command.index('-c') + 1] = str(source)
command[command.index('-o') + 1] = str(target)
# Preserve the resolution of unchanged sibling headers such as timer.h.
command[command.index('-c'):command.index('-c')] = ['-iquote', str(original.parent)]
log = out / 'timer.log'
with log.open('w') as stream:
    result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
unit = dict(source='lib/timer.cpp', sourceFile=str(source), sourceSHA256=digest(source),
            object=str(target), command=command, exitCode=result.returncode, log=str(log))
if result.returncode == 0:
    unit['objectSHA256'] = digest(target)
report['results'][index] = unit
report.setdefault('additionalHeaders', []).append(dict(path=str(header), SHA256=digest(header)))
base_seconds = report.pop('seconds', None)
report.update(status='COMPILE_FAILED' if result.returncode else 'COMPILE_PASSED_NOT_LINKED',
              baseCompileSeconds=base_seconds, seconds=time.monotonic() - started,
              baseCompileReportSHA256=digest(base / 'compile-report.json'),
              timerProbeReportSHA256=digest(Path('/phase45-build/timer-monotonic-probe/report.json')),
              platformExperiment='shared-openal-error-atomic-monotonic',
              scope='One private timer.cpp replacement: lock-free atomic maximum with the original time source and non-strict clamp. Other 482 objects, audio order, VM, simulation, scripts and graphics retained.',
              failed=['lib/timer.cpp'] if result.returncode else [], notAttempted=[], phase45Accepted=False)
(out / 'timer-monotonic.patch').write_text(''.join(difflib.unified_diff(
    before.splitlines(True), after.splitlines(True), fromfile='a/lib/timer.cpp', tofile='b/lib/timer.cpp')))
(out / 'compile-report.json').write_text(json.dumps(report, indent=2))
print(report['status'], '483 units; 482 verified control objects retained', flush=True)
raise SystemExit(1 if result.returncode else 0)
