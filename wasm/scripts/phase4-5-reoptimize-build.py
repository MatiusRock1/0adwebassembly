"""Recompile every engine unit of an existing candidate with another -O level.

Each unit reruns its recorded command unchanged except for the optimization flag
and output path, so sources, defines, SIMD, exception mode and FP flags stay as
compiled. No fast-math flags are added. Libraries and the dependency audit are
reused from the base candidate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', required=True, help='Existing /phase45-build/application-<base> directory name suffix.')
parser.add_argument('--variant', required=True, help='New output directory suffix; never reuse an existing candidate.')
parser.add_argument('--optimization', choices=['O2', 'O3'], default='O3')
parser.add_argument('--jobs', type=int, default=2)
args = parser.parse_args()
os.environ.update(EMCC_CORES='1', BINARYEN_CORES='1')
includes = Path('/tmp/phase4-includes'); includes.mkdir(exist_ok=True)
for name in ['boost', 'enet', 'libxml']:
    target = includes / name
    if not target.exists(): target.symlink_to(Path('/spike/headless/include') / name)
shutil.copytree('/spike/headless/include/fmt', includes / 'fmt', dirs_exist_ok=True)
fmt = includes / 'fmt/core.h'
fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))', 'parse_format_string<true>(str_, checker(str_, {}))'))

base = Path('/phase45-build') / ('application-' + args.base)
out = Path('/phase45-build') / ('application-' + args.variant)
assert not (out / 'compile-report.json').exists(), 'Refusing to overwrite an existing candidate'
out.mkdir(exist_ok=True)
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
report = json.loads((base / 'compile-report.json').read_text())
assert report['status'] == 'COMPILE_PASSED_NOT_LINKED'
for unit in report['results']:
    assert unit['exitCode'] == 0 and digest(unit['object']) == unit['objectSHA256']
shutil.copytree(base / 'runtime-browser', out / 'runtime-browser', dirs_exist_ok=True)


def compile_unit(unit):
    command = list(unit['command'])
    levels = [i for i, flag in enumerate(command) if flag.startswith('-O')]
    assert len(levels) == 1, (unit['source'], [command[i] for i in levels])
    assert not any(flag in command for flag in ['-ffast-math', '-Ofast', '-funsafe-math-optimizations'])
    command[levels[0]] = '-' + args.optimization
    target = out / (unit['source'].replace('/', '_') + '.o')
    command[command.index('-o') + 1] = str(target)
    log = out / (unit['source'].replace('/', '_') + '.log')
    start = time.monotonic()
    with log.open('w') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    updated = dict(unit, command=command, object=str(target), log=str(log), exitCode=result.returncode,
                   seconds=time.monotonic() - start, baseObjectSHA256=unit['objectSHA256'])
    updated['objectSHA256'] = digest(target) if result.returncode == 0 else None
    return updated


start = time.monotonic()
with ThreadPoolExecutor(args.jobs) as pool:
    results = []
    for index, unit in enumerate(pool.map(compile_unit, report['results'])):
        results.append(unit)
        if unit['exitCode']:
            print('FAILED', unit['source'], Path(unit['log']).read_text()[-4000:], flush=True)
        if index % 50 == 0:
            print('REOPTIMIZED', index + 1, len(report['results']), round(time.monotonic() - start), flush=True)
failed = [u['source'] for u in results if u['exitCode']]
report.update(results=results, status='COMPILE_FAILED' if failed else 'COMPILE_PASSED_NOT_LINKED',
    failed=failed, optimization=args.optimization, reoptimizedFrom=str(base), seconds=time.monotonic() - start,
    baseCompileReportSHA256=digest(base / 'compile-report.json'), buildScriptSHA256=digest(__file__),
    platformExperiment=report.get('platformExperiment', '') + '-' + args.optimization.lower(),
    scope=report.get('scope', '') + ' All engine units recompiled at -' + args.optimization +
        ' with otherwise identical commands; requires parity and independent physical validation.')
(out / 'compile-report.json').write_text(json.dumps(report, indent=2))
print(report['status'], flush=True)
raise SystemExit(1 if failed else 0)
