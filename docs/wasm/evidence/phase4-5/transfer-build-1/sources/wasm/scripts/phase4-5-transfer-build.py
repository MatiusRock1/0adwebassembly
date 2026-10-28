"""Separate combined candidate: uninstrumented JS boundaries and direct packet uploads."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

os.environ.update(EMCC_CORES='2',BINARYEN_CORES='2')
base=Path('/phase45-build/application-ai-worker')
out=Path('/phase45-build/application-transfer');out.mkdir(exist_ok=True)
private=out/'source';private.mkdir(exist_ok=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
control=json.loads((base/'compile-report.json').read_text())
assert control['status']=='COMPILE_PASSED_NOT_LINKED' and control['aiWorker'] and len(control['results'])==483
for unit in control['results']:
    assert unit['exitCode']==0 and digest(Path(unit['object']))==unit['objectSHA256']
shutil.copytree(base/'runtime-browser',out/'runtime-browser',dirs_exist_ok=True)
shutil.copytree('/workspace/source/renderer/backend/webgpu',private/'renderer/backend/webgpu',dirs_exist_ok=True)
timing=out/'scene-script-timing.h';shutil.copy2('/workspace/wasm/harness/scene-script-timing.h',timing)
headers=[dict(path=str(timing),SHA256=digest(timing))]+[
    dict(path=str(p),SHA256=digest(p)) for p in (private/'renderer/backend/webgpu').glob('*.h')]
header_identity=json.dumps(headers,sort_keys=True)
previous=out/'compile-report.json'
cached={u['source']:u for u in json.loads(previous.read_text()).get('results',[])} if previous.exists() else {}
report=dict(control,results=[],status='IN_PROGRESS',failed=[],notAttempted=[],
    fineScriptTiming=False,generatedBufferUploads=True,platformExperiment='combined-transfer-cost',
    additionalHeaders=control.get('additionalHeaders',[])+headers,
    baseCompileReportSHA256=digest(base/'compile-report.json'),buildScriptSHA256=digest(Path(__file__)),
    scope='All 483 SIMD engine units rebuilt with fine script timing disabled; actor, original simulation, assets and graphics retained; callback buffer uploads generated in owned packets.')
includes=Path('/tmp/phase4-includes');includes.mkdir(exist_ok=True)
for name in ['boost','enet','libxml']:
    target=includes/name
    if not target.exists():target.symlink_to(Path('/spike/headless/include')/name)
shutil.copytree('/spike/headless/include/fmt',includes/'fmt',dirs_exist_ok=True)
fmt=includes/'fmt/core.h';fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))','parse_format_string<true>(str_, checker(str_, {}))'))
started=time.monotonic();stop=threading.Event()
def compile_unit(unit):
    source=Path(unit.get('sourceFile',Path(control['frozenSourceRoot'])/unit['source']))
    assert digest(source)==unit['sourceSHA256'],'Control source changed: '+str(source)
    command=list(unit['command']);target=out/(unit['source'].replace('/','_')+'.o')
    command[command.index('-o')+1]=str(target)
    timings=[i for i,value in enumerate(command) if value.endswith('/scene-script-timing.h')]
    assert len(timings)==1,'Missing/ambiguous forced timing header'
    command[timings[0]]=str(timing)
    command[1:1]=['-DWASM_SCENE_SCRIPT_TIMING_ENABLED=0']
    if unit['source']=='renderer/backend/webgpu/Device.cpp':
        source=private/'renderer/backend/webgpu/Device.cpp'
        command[command.index('-c')+1]=str(source)
        command[1:1]=['-I'+str(private)]
    identity=hashlib.sha256((json.dumps(command)+digest(source)+header_identity).encode()).hexdigest()
    old=cached.get(unit['source'],{})
    if old.get('identity')==identity and old.get('exitCode')==0 and target.is_file() and digest(target)==old.get('objectSHA256'):return old
    if stop.is_set():return dict(source=unit['source'],exitCode=-1,skippedAfterFailure=True)
    log=target.with_suffix('.log')
    with log.open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    entry=dict(unit,command=command,sourceFile=str(source),sourceSHA256=digest(source),
        object=str(target),log=str(log),exitCode=result.returncode,identity=identity)
    if result.returncode:
        stop.set();print(log.read_text()[-10000:],flush=True)
    else:entry['objectSHA256']=digest(target)
    return entry
def save():
    report['seconds']=time.monotonic()-started;previous.write_text(json.dumps(report,indent=2))
save()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for entry in pool.map(compile_unit,control['results']):
        report['results'].append(entry)
        if len(report['results'])%10==0 or entry['exitCode']:
            save();print('TRANSFER_BUILD',len(report['results']),'/ 483',round(report['seconds'],1),flush=True)
report['failed']=[u['source'] for u in report['results'] if u['exitCode']]
report['status']='COMPILE_FAILED' if report['failed'] else 'COMPILE_PASSED_NOT_LINKED'
save();print(report['status'],flush=True)
raise SystemExit(bool(report['failed']))
