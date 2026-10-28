"""Replace only Interpreter.o in the switch-dispatch archive with a private copy
of SM128 js::RunScript that does not read the clock for realm execution timers.

SM128 only writes realm()->timers.executionTime (Firefox telemetry); nothing in
the engine or 0 A.D. reads it. In the browser each TimeStamp::Now() is a
wasm-to-JS performance.now() call, made twice per outermost C++-to-JS call.
The measuring/executing flags are kept exactly as before.
"""
import difflib
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time

ROOT = Path('/phase45-build/spidermonkey-portable/build/js/src')
INPUT = Path('/phase45-build/spidermonkey-portable-switch-o3')
OUT = Path('/phase45-build/spidermonkey-portable-switch-o3-runscript-timer'); OUT.mkdir(parents=True, exist_ok=True)
SOURCE = Path('/spike/mozjs-128.13.0/js/src/vm/Interpreter.cpp')
TARGET = 'Interpreter.o'
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

ORIGINAL = '''  bool measuringTime = !cx->isMeasuringExecutionTime();
  mozilla::TimeStamp startTime;
  if (measuringTime) {
    cx->setIsMeasuringExecutionTime(true);
    cx->setIsExecuting(true);
    startTime = mozilla::TimeStamp::Now();
  }
  auto timerEnd = mozilla::MakeScopeExit([&]() {
    if (measuringTime) {
      mozilla::TimeDuration delta = mozilla::TimeStamp::Now() - startTime;
      cx->realm()->timers.executionTime += delta;
      cx->setIsMeasuringExecutionTime(false);
      cx->setIsExecuting(false);
    }
  });
'''
PATCHED = '''  bool measuringTime = !cx->isMeasuringExecutionTime();
  if (measuringTime) {
    cx->setIsMeasuringExecutionTime(true);
    cx->setIsExecuting(true);
  }
  auto timerEnd = mozilla::MakeScopeExit([&]() {
    if (measuringTime) {
      cx->setIsMeasuringExecutionTime(false);
      cx->setIsExecuting(false);
    }
  });
'''

report = dict(passed=False, phase45Accepted=False, target=TARGET,
    scope='Only Interpreter.o replaced; js::RunScript keeps its flags but no longer reads the clock '
          'for the write-only realm execution timer. Other members, headers and game content unchanged.')
try:
    input_report = json.loads((INPUT / 'report.json').read_text())
    archive = INPUT / 'libjs_static.a'
    assert input_report['passed'] and digest(archive) == input_report['archiveSHA256'], 'Input archive changed'
    report.update(originalArchiveSHA256=input_report['originalArchiveSHA256'],
        inputArchiveSHA256=input_report['archiveSHA256'], inputReport=str(INPUT / 'report.json'))
    members = subprocess.check_output(['emar', 't', str(archive)], text=True).splitlines()
    assert members.count(TARGET) == 1, 'Interpreter.o missing or duplicated'

    before = SOURCE.read_text()
    assert before.count(ORIGINAL) == 1, 'Unexpected js::RunScript'
    assert before.count('timers.executionTime') == 1, 'Execution timer has another writer'
    after = before.replace(ORIGINAL, PATCHED)
    patched = OUT / 'Interpreter.cpp'; patched.write_text(after)
    patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
        fromfile='a/js/src/vm/Interpreter.cpp', tofile='b/js/src/vm/Interpreter.cpp'))
    (OUT / 'runscript-timer.patch').write_text(patch)
    report.update(originalSourceSHA256=digest(SOURCE), patchedSourceSHA256=digest(patched), patch=patch)

    dry = subprocess.run(['make', '-n', '-B', TARGET], cwd=ROOT, capture_output=True, text=True, check=True)
    (OUT / (TARGET + '.make-dry-run.txt')).write_text(dry.stdout)
    candidates = [shlex.split(line) for line in dry.stdout.splitlines()
                  if line.startswith('/emsdk/upstream/emscripten/em++ ')]
    candidates = [c for c in candidates if c[c.index('-o') + 1] == TARGET]
    assert len(candidates) == 1, len(candidates)
    original_command = candidates[0]; command = list(original_command)
    assert '-ffp-contract=off' in command
    assert not any(flag in command for flag in ['-ffast-math', '-Ofast', '-funsafe-math-optimizations'])
    assert Path(command[-1]).name == 'Interpreter.cpp'
    command[command.index('-o') + 1] = str(OUT / TARGET)
    command[command.index('-MF') + 1] = str(OUT / (TARGET + '.d'))
    # The private copy lives elsewhere; keep the original directory first for quoted includes.
    command.insert(-1, '-iquote' + str(SOURCE.parent))
    command[-1] = str(patched)
    start = time.monotonic()
    with (OUT / (TARGET + '.log')).open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    report['unit'] = dict(command=command, originalCommand=original_command, exitCode=result.returncode,
                          seconds=time.monotonic() - start)
    assert result.returncode == 0, 'Compile failed; inspect log'
    report['unit']['objectSHA256'] = digest(OUT / TARGET)

    temporary = OUT / 'libjs_static.a.partial'
    shutil.copyfile(archive, temporary)
    subprocess.run(['emar', 'rcs', str(temporary), str(OUT / TARGET)], check=True)
    assert sorted(subprocess.check_output(['emar', 't', str(temporary)], text=True).splitlines()) == sorted(members), \
        'Archive membership changed'
    temporary.replace(OUT / 'libjs_static.a')
    report['archiveSHA256'] = digest(OUT / 'libjs_static.a')
    report['passed'] = True
except Exception as error:
    report['failure'] = str(error)
finally:
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))
print('SCRIPTING_RUNSCRIPT_TIMER_BUILT_NOT_ACCEPTED' if report['passed'] else 'SCRIPTING_BUILD_FAILED', flush=True)
raise SystemExit(0 if report['passed'] else 1)
