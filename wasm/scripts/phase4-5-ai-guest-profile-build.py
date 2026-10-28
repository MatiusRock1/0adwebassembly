"""Build only the isolated AI actor with cooperative guest-source diagnostics."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

os.environ.update(EMCC_CORES='2', BINARYEN_CORES='2')
includes=Path('/tmp/phase4-includes');includes.mkdir(exist_ok=True)
for name in ['boost','enet','libxml']:
    target=includes/name
    if not target.exists():target.symlink_to(Path('/spike/headless/include')/name)
shutil.copytree('/spike/headless/include/fmt',includes/'fmt',dirs_exist_ok=True)
fmt=includes/'fmt/core.h'
fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))','parse_format_string<true>(str_, checker(str_, {}))'))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--map-kernels',action='store_true')
parser.add_argument('--variant-suffix',choices=['','2','3','4'],default='')
parser.add_argument('--dense-snapshot',action='store_true')
args=parser.parse_args()
base=Path('/phase45-build/application-transfer')
variant='ai-map-kernels' if args.map_kernels else 'ai-guest-profile'
if args.variant_suffix:variant+='-'+args.variant_suffix
out=Path('/phase45-build')/('application-'+variant);out.mkdir(exist_ok=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((base/'compile-report.json').read_text())
assert report['status']=='COMPILE_PASSED_NOT_LINKED'
for unit in report['results']:
    assert unit['exitCode']==0 and digest(Path(unit['object']))==unit['objectSHA256']
shutil.copytree(base/'runtime-browser',out/'runtime-browser',dirs_exist_ok=True)
private=out/'source'
headers=[]
for name in ['components/CCmpAIManager.cpp','helpers/AIGuestProfiler.h','helpers/AIMapKernels.h','helpers/AIWorkerMailbox.h','helpers/AIWorkerScript.h','helpers/DeferredCommands.h']:
    src=Path('/workspace/source/simulation2')/name
    dst=private/'simulation2'/name;dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
    if dst.suffix=='.h':headers.append(dict(path=str(dst),SHA256=digest(dst)))
unit=next(u for u in report['results'] if u['source']=='simulation2/components/CCmpAIManager.cpp')
source=private/unit['source'];target=out/'CCmpAIManager.o'
command=list(unit['command'])
command[command.index('-c')+1]=str(source)
command[command.index('-o')+1]=str(target)
command[1:1]=['-DWASM_AI_MAP_KERNELS=1' if args.map_kernels else '-DWASM_AI_GUEST_PROFILE=1','-I'+str(private),'-ffp-contract=off']
if args.dense_snapshot:command.insert(1,'-DWASM_AI_DENSE_SNAPSHOT=1')
log=out/'compile.log'
with log.open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
unit.update(command=command,sourceFile=str(source),sourceSHA256=digest(source),object=str(target),log=str(log),exitCode=result.returncode)
if result.returncode:print(log.read_text()[-12000:],flush=True)
else:unit['objectSHA256']=digest(target)
report.update(diagnosticOnly=not args.map_kernels,aiGuestProfiler=not args.map_kernels,aiMapKernels=args.map_kernels,
    denseAISnapshot=args.dense_snapshot,
    platformExperiment=variant,
    status='COMPILE_FAILED' if result.returncode else 'COMPILE_PASSED_NOT_LINKED',
    additionalHeaders=report.get('additionalHeaders',[])+headers,
    buildScriptSHA256=digest(Path(__file__)),
    baseCompileReportSHA256=digest(base/'compile-report.json'),
    scope=('Opt-in native influence and obstruction kernels; compact owned snapshot='+str(args.dense_snapshot)+'; requires original-state parity and independent physical validation.' if args.map_kernels else
        'Cooperative guest-source interrupt sampling; not FPS acceptance or exclusive CPU attribution.'))
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
print(report['status'],flush=True)
raise SystemExit(result.returncode)
