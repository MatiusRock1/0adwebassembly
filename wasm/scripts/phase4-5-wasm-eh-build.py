"""Rebuild the whole current application closure with native Wasm C++ EH.

Separate sources/objects/reports; never mix legacy-EH engine objects. Keep O2,
use matching Wasm longjmp, audit cached no-exceptions dependencies, preserve code.
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
import argparse
from phase45_exception_audit import audit,dependencies
from phase45_native_curl import prepare as prepare_curl

os.environ.update(EMCC_CORES='2',BINARYEN_CORES='2')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--spidermonkey-library',type=Path,required=True)
args=parser.parse_args()
native_curl=prepare_curl()
dependency_audit=audit(dependencies(args.spidermonkey_library,native_curl['archive']))
Path('/phase45-build/native-dependency-audit.json').write_text(json.dumps(dependency_audit,indent=2))
assert dependency_audit['passed'],'Legacy handlers remain in native-EH cached dependencies'
script=Path('/workspace/wasm/scripts/phase4-5-engine-build.py')
scope={}
setup=script.read_text();boundary="report=json.loads(Path('/phase4-build/compile-report.json')"
assert setup.count(boundary)==1,'Unexpected engine setup script'
exec(compile(setup.split(boundary)[0],str(script),'exec'),scope)
base=scope['out'];original_root=scope['root']
out=Path('/phase45-build/application-wasm-eh');out.mkdir(exist_ok=True)
root=out/'source';shutil.copytree(original_root,root,dirs_exist_ok=True)
harness=out/'harness';shutil.copytree('/phase4-harness',harness,dirs_exist_ok=True)
version=out/'build/build_version/build_version.txt';version.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2('/phase4-build/build/build_version/build_version.txt',version)
browser=out/'runtime-browser';browser.mkdir(exist_ok=True)
for name in ['application-openal.js','application-audio-state.js']:shutil.copy2(Path('/phase4-browser')/name,browser/name)
flags=[flag.replace(str(original_root),str(root)).replace('-I/phase4-harness','-I'+str(harness)) for flag in scope['flags']]
assert flags.count('-fexceptions')==1 and '-O2' in flags
flags[flags.index('-fexceptions')]='-fwasm-exceptions'
flags+=['-sSUPPORT_LONGJMP=wasm']
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
headers={folder.name+'/'+str(p.relative_to(folder)):digest(p) for folder in [root,harness] for p in folder.rglob('*') if p.is_file() and p.suffix in ['.h','.hpp','.inc']}
header_identity=hashlib.sha256(json.dumps(headers,sort_keys=True).encode()).hexdigest()
inputs=json.loads((base/'compile-report.json').read_text())
assert inputs['status']=='COMPILE_PASSED_NOT_LINKED' and inputs['audioEnabled']
report_path=out/'compile-report.json'
previous=json.loads(report_path.read_text()) if report_path.exists() else {}
old={r['source']:r for r in previous.get('results',[])};results={};stop=threading.Event();started=time.monotonic()
report=dict(status='IN_PROGRESS',jobs=2,audioEnabled=True,applicationLinked=False,headlessServiceAdapters=False,
    exceptionMode='wasm',longjmpMode='wasm',optimization='O2',phase45Accepted=False,
    inputCompileReportSHA256=digest(base/'compile-report.json'),sourceHeadersSHA256=header_identity,
    generatedFileSHA256={'build/build_version/build_version.txt':digest(version)},
    nativeCurl=native_curl,dependencyAudit=dependency_audit,
    frozenSourceRoot=str(root),frozenHarnessRoot=str(harness),
    scope='All engine closure objects recompiled with -fwasm-exceptions, O2 and matching Wasm longjmp. Cached dependencies built without C++ exceptions must not contain legacy setjmp handlers. Original source pin, scripts, assets, quality and simulation clock unchanged.',
    excludedNativePlatformUnits=inputs.get('excludedNativePlatformUnits',{}),results=[])
(out/'header-hashes.json').write_text(json.dumps(headers,indent=2))

def save():
    report.update(results=list(results.values()),seconds=time.monotonic()-started)
    report_path.write_text(json.dumps(report,indent=2))

def compile_unit(unit):
    relative=unit['source'];source=root/relative
    obj=out/(relative.replace('/','_')+'.o');log=obj.with_suffix('.log')
    extra=['-fno-rtti'] if relative=='gui/Scripting/JSInterface_GUIProxy.cpp' else []
    command=flags+extra+['-c',str(source),'-o',str(obj)]
    generated=version.read_bytes() if relative=='lib/build_version.cpp' else b''
    identity=hashlib.sha256(source.read_bytes()+header_identity.encode()+json.dumps(command).encode()+generated).hexdigest()
    cached=old.get(relative,{})
    if cached.get('identity')==identity and cached.get('exitCode')==0 and obj.is_file() and digest(obj)==cached.get('objectSHA256'):
        return cached
    if stop.is_set():return dict(source=relative,exitCode=-1,skippedAfterFailure=True)
    start=time.monotonic()
    with log.open('w') as stream:process=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    result=dict(source=relative,object=str(obj),log=str(log),exitCode=process.returncode,command=command,
        identity=identity,sourceSHA256=digest(source),seconds=time.monotonic()-start)
    if process.returncode:stop.set();print('WASM_EH_FAILED',relative,flush=True)
    else:result['objectSHA256']=digest(obj)
    return result

save()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(compile_unit,inputs['results']):
        results[result['source']]=result
        if len(results)%10==0 or result['exitCode'] and not result.get('skippedAfterFailure'):
            save();print('WASM_EH_BUILD',len(results),'/',len(inputs['results']),round(time.monotonic()-started,1),'seconds',flush=True)
failed=[r['source'] for r in results.values() if r['exitCode'] and not r.get('skippedAfterFailure')]
skipped=[r['source'] for r in results.values() if r.get('skippedAfterFailure')]
report.update(status='COMPILE_FAILED' if failed or skipped else 'COMPILE_PASSED_NOT_LINKED',failed=failed,notAttempted=skipped)
assert set(results)=={r['source'] for r in inputs['results']}
save();print(report['status'],len(results),'units',flush=True)
raise SystemExit(1 if failed or skipped else 0)
