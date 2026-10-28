"""Extend the verified native-EH control with shared OpenAL error state only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

os.environ.update(EMCC_CORES='2',BINARYEN_CORES='2')
started=time.monotonic()
base=Path('/phase45-build/application-wasm-eh')
out=Path('/phase45-build/application-audio-error');out.mkdir(exist_ok=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((base/'compile-report.json').read_text())
assert report['status']=='COMPILE_PASSED_NOT_LINKED' and report['exceptionMode']=='wasm'
assert len(report['results'])==482 and report['dependencyAudit']['passed']
roots={'source':Path(report['frozenSourceRoot']),'harness':Path(report['frozenHarnessRoot'])}
headers=json.loads((base/'header-hashes.json').read_text())
for relative,expected in headers.items():
    folder,name=relative.split('/',1)
    assert digest(roots[folder]/name)==expected,'Control header changed: '+relative
for unit in report['results']:
    assert unit['exitCode']==0 and '-fwasm-exceptions' in unit['command']
    assert digest(Path(unit['object']))==unit['objectSHA256'],'Control object changed: '+unit['source']
    assert digest(roots['source']/unit['source'])==unit['sourceSHA256'],'Control source changed: '+unit['source']

source=out/'application-openal-error.cpp'
shutil.copy2('/workspace/wasm/harness/application-openal-error.cpp',source)
browser=out/'runtime-browser';browser.mkdir(exist_ok=True)
for name in ['application-openal.js','application-audio-state.js']:
    shutil.copy2(base/'runtime-browser'/name,browser/name)
library=browser/'application-openal-error.js'
shutil.copy2('/workspace/wasm/browser/application-openal-error.js',library)
flags=report['results'][0]['command']
flags=flags[:flags.index('-c')]
assert '-O2' in flags and '-sSUPPORT_LONGJMP=wasm' in flags
obj=out/'application-openal-error.o';log=out/'application-openal-error.log'
command=flags+['-c',str(source),'-o',str(obj)]
with log.open('w') as stream:compiled=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
unit=dict(source='application-openal-error.cpp',sourceFile=str(source),sourceSHA256=digest(source),
    object=str(obj),command=command,exitCode=compiled.returncode,log=str(log))
if not compiled.returncode:unit['objectSHA256']=digest(obj)
report['results'].append(unit)
base_seconds=report.pop('seconds',None)
report.update(status='COMPILE_FAILED' if compiled.returncode else 'COMPILE_PASSED_NOT_LINKED',
    baseCompileSeconds=base_seconds,seconds=time.monotonic()-started,
    baseCompileReportSHA256=digest(base/'compile-report.json'),
    additionalJSLibraries=[dict(path=str(library),SHA256=digest(library))],
    platformExperiment='shared-openal-error',
    scope='Verified unchanged 482-object native-EH control plus one shared atomic AL-error cell and isolated JS adapter. SDK audio creation, playback, parameters, timing, scripts, graphics and simulation remain unchanged.',
    failed=[unit['source']] if compiled.returncode else [],notAttempted=[],phase45Accepted=False)
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
print(report['status'],len(report['results']),'units; 482 verified control objects retained',flush=True)
raise SystemExit(compiled.returncode)
