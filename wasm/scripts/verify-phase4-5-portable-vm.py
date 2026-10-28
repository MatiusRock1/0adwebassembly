"""Exercise original VM API semantics on CPU, independently of graphics/FPS."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile',choices=['portable-fixed-o3','portable-switch-o2','portable-switch-o3','portable-underflow-o3','portable-cache-count-o3','portable-guards-o3'],required=True)
parser.add_argument('--guard-checks',action='store_true',help='Add focused undefined/polymorphic-shape/sparse-index and GC cases; preserve the default probe report.')
args=parser.parse_args()
ROOT=Path('/workspace');BUILD=Path('/phase45-build')
BASE=Path('/spike/mozjs-128.13.0/build-wasm')
library=BUILD/('spidermonkey-'+args.profile)/'libjs_static.a'
provenance=json.loads(library.with_name('report.json').read_text())
args.guard_checks=args.guard_checks or bool(provenance.get('guardHandlers'))
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert provenance['passed'] and digest(library)==provenance['archiveSHA256']
OUT=BUILD/('portable-vm-probe-'+args.profile+('-guards' if args.guard_checks else ''));OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'wasm/probes/spidermonkey-portable.cpp'
support=sorted(str(p) for folder in ['mfbt','mozglue','memory'] for p in (BASE/folder).rglob('*.o'))
command=['em++','-O2','-std=c++20','-pthread','-I'+str(BASE/'dist/include'),str(source),str(library),
         str(BASE/'wasm32-unknown-emscripten/release/libjsrust.a'),str(BASE/'build/pure_virtual/libpure_virtual.a'),*support,
         '--use-port=zlib','-sALLOW_MEMORY_GROWTH=1','-sINITIAL_MEMORY=134217728','-sSTACK_SIZE=5242880',
         '-sPTHREAD_POOL_SIZE=8','-sENVIRONMENT=node','-sEXIT_RUNTIME=1','-sASSERTIONS=2','-o',str(OUT/'probe.js')]
report=dict(passed=False,diagnosticOnly=True,performanceAcceptance=False,phase45Accepted=False,
            profile=args.profile,archiveSHA256=digest(library),sourceSHA256=digest(source),command=command)
if args.guard_checks:
    command.insert(1,'-DPHASE45_PORTABLE_GUARDS_PROBE=1')
    report['guardCasesSHA256']=digest(source.with_name('spidermonkey-portable-guards.inc'))
    report['guardChecks']=True
try:
    with (OUT/'link.log').open('w') as log:compiled=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    report['linkExitCode']=compiled.returncode
    assert compiled.returncode==0,'VM probe link failed; inspect link.log'
    if provenance.get('missingCacheIROpCounts'):
        script='const fs=require("fs");const m=new WebAssembly.Module(fs.readFileSync(process.argv[1]));process.stdout.write(JSON.stringify(WebAssembly.Module.exports(m).map(x=>x.name)));'
        exports=json.loads(subprocess.check_output(['node','-e',script,str(OUT/'probe.wasm')],text=True))
        expected=['Phase45MissingCacheIRCounts','Phase45MissingCacheIRSize','Phase45MissingCacheIRName']
        assert all(name in exports for name in expected),'Diagnostic counter exports missing'
        report['counterExportsVerified']=expected
    run=subprocess.run(['node',str(OUT/'probe.js')],capture_output=True,text=True,timeout=120)
    report.update(exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr)
    (OUT/'runtime.log').write_text(run.stdout+run.stderr)
    assert run.returncode==0,'VM probe failed; inspect runtime.log'
    report['result']=json.loads(run.stdout.strip().splitlines()[-1])
    assert report['result']['passed'] and report['result']['checks']==(30 if args.guard_checks else 21) and report['result']['incrementalYields']>0
    report['artifacts']={p.name:digest(p) for p in OUT.glob('probe.*')}
    report['passed']=True
except Exception as error:report['failure']=str(error)
finally:(OUT/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:report.get(k) for k in ['passed','failure','profile','result']},indent=2),flush=True)
raise SystemExit(0 if report['passed'] else 1)
