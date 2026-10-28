"""Build the isolated AI actor without changing the measured rAF candidate."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

base=Path('/phase45-build/application-browser-perf')
out=Path('/phase45-build/application-ai-worker');out.mkdir(exist_ok=True)
private=out/'source';private.mkdir(exist_ok=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((base/'compile-report.json').read_text())
assert report['status']=='COMPILE_PASSED_NOT_LINKED' and report['browserPerformanceFeatures']
for unit in report['results']:
    assert unit['exitCode']==0 and digest(Path(unit['object']))==unit['objectSHA256']
shutil.copytree(base/'runtime-browser',out/'runtime-browser',dirs_exist_ok=True)
headers=['simulation2/helpers/AIWorkerMailbox.h','simulation2/helpers/AIWorkerScript.h',
         'simulation2/helpers/DeferredCommands.h','simulation2/components/ICmpCommandQueue.h','scriptinterface/Engine.h']
for relative in headers:
    target=private/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path('/workspace/source')/relative,target)
    report.setdefault('additionalHeaders',[]).append(dict(path=str(target),SHA256=digest(target)))

# Recompile the Engine owner too: its layout now includes a mutex. Preserve
# the frozen main/Context browser instrumentation rather than copying originals.
units=['simulation2/components/CCmpAIManager.cpp','simulation2/components/CCmpCommandQueue.cpp',
       'scriptinterface/Context.cpp','main.cpp']
includes=Path('/tmp/phase4-includes');includes.mkdir(exist_ok=True)
for name in ['boost','enet','libxml']:
    target=includes/name
    if not target.exists():target.symlink_to(Path('/spike/headless/include')/name)
shutil.copytree('/spike/headless/include/fmt',includes/'fmt',dirs_exist_ok=True)
fmt=includes/'fmt/core.h';fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))','parse_format_string<true>(str_, checker(str_, {}))'))
for relative in units:
    index=next(i for i,u in enumerate(report['results']) if u['source']==relative)
    old=report['results'][index]
    original=Path(old.get('sourceFile',Path(report['frozenSourceRoot'])/relative))
    source=private/relative;source.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path('/workspace/source')/relative if relative.startswith('simulation2/') else original,source)
    command=list(old['command']);target=out/(relative.replace('/','_')+'.o')
    command[command.index('-c')+1]=str(source);command[command.index('-o')+1]=str(target)
    command[1:1]=['-DWASM_AI_WORKER','-I'+str(private),'-iquote',str(original.parent)]
    log=target.with_suffix('.log')
    with log.open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    entry=dict(source=relative,sourceFile=str(source),sourceSHA256=digest(source),command=command,
               object=str(target),log=str(log),exitCode=result.returncode)
    if not result.returncode:entry['objectSHA256']=digest(target)
    report['results'][index]=entry
    print('AI_WORKER_COMPILE',relative,result.returncode,flush=True)
    if result.returncode:
        print(log.read_text()[-12000:],flush=True);break
report['failed']=[u['source'] for u in report['results'] if u['exitCode']]
report.update(status='COMPILE_FAILED' if report['failed'] else 'COMPILE_PASSED_NOT_LINKED',
    aiWorker=True,platformExperiment='isolated-ai-worker',phase45Accepted=False,
    scope='Experimental isolated AI with cloned inputs, owner-thread runtime and ordered deferred command batches.',
    buildScriptSHA256=digest(Path(__file__)),baseCompileReportSHA256=digest(base/'compile-report.json'))
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
raise SystemExit(bool(report['failed']))
