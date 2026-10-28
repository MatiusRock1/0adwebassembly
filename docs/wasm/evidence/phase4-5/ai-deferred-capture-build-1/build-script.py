"""Rebuild candidate 2 with the AI state capture after the turn frame's Present."""
import hashlib
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
base=Path('/phase45-build/application-ai-map-kernels-2')
out=Path('/phase45-build/application-ai-deferred-capture-1');out.mkdir(exist_ok=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((base/'compile-report.json').read_text())
assert report['status']=='COMPILE_PASSED_NOT_LINKED' and report.get('aiMapKernels') and not report.get('denseAISnapshot')
for unit in report['results']:
    assert unit['exitCode']==0 and digest(Path(unit['object']))==unit['objectSHA256']
shutil.copytree(base/'runtime-browser',out/'runtime-browser',dirs_exist_ok=True)
private=out/'source'
headers=[]
for name in ['components/CCmpAIManager.cpp','Simulation2.cpp','helpers/AIDeferredStart.h','helpers/AIGuestProfiler.h',
             'helpers/AIMapKernels.h','helpers/AIWorkerMailbox.h','helpers/AIWorkerScript.h','helpers/DeferredCommands.h']:
    src=Path('/workspace/source/simulation2')/name
    dst=private/'simulation2'/name;dst.parent.mkdir(parents=True,exist_ok=True)
    # The Windows checkout may use CRLF; compile the same text the frozen tree used.
    dst.write_bytes(src.read_bytes().replace(b'\r\n',b'\n'))
    if dst.suffix=='.h':headers.append(dict(path=str(dst),SHA256=digest(dst)))
# The browser frame loop exists only in the frozen, patched main.cpp copy.
units={u['source']:u for u in report['results']}
main_unit=units['main.cpp']
main_source=Path(main_unit['sourceFile']).read_text()
assert digest(Path(main_unit['sourceFile']))==main_unit['sourceSHA256']
def edit(text,old,new):
    assert text.count(old)==1,'Unexpected main.cpp for '+old
    return text.replace(old,new)
main_source=edit(main_source,'#include "application-deferred-replay.h"\n',
    '#include "application-deferred-replay.h"\n#include "simulation2/helpers/AIDeferredStart.h"\n')
# Only Frame() renders before this point; NonVisualFrame relies on the turn hook.
main_source=edit(main_source,'\tg_Profiler.Frame();\n\n\tLimitFPS();',
    '\t// This frame\'s Present is already dispatched to the render worker.\n'
    '\tAIDeferredStart::Run();\n\n\tg_Profiler.Frame();\n\n\tLimitFPS();')
(private/'main.cpp').write_text(main_source)
frozen=Path(report['frozenSourceRoot'])
sources={'main.cpp':(private/'main.cpp',[]),
    'simulation2/Simulation2.cpp':(private/'simulation2/Simulation2.cpp',['-iquote',str(frozen/'simulation2')]),
    'simulation2/components/CCmpAIManager.cpp':(private/'simulation2/components/CCmpAIManager.cpp',[])}
failed=False
for relative,(source,extra) in sources.items():
    unit=units[relative]
    target=out/(relative.replace('/','_')+'.o')
    command=list(unit['command'])
    command[command.index('-c')+1]=str(source)
    command[command.index('-o')+1]=str(target)
    command[1:1]=['-DWASM_AI_DEFERRED_CAPTURE=1','-I'+str(private),*extra]
    log=out/(relative.replace('/','_')+'.log')
    with log.open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    unit.update(command=command,sourceFile=str(source),sourceSHA256=digest(source),object=str(target),log=str(log),exitCode=result.returncode)
    if result.returncode:failed=True;print(log.read_text()[-12000:],flush=True)
    else:unit['objectSHA256']=digest(target)
report.update(aiDeferredCapture=True,
    platformExperiment='ai-deferred-capture',
    status='COMPILE_FAILED' if failed else 'COMPILE_PASSED_NOT_LINKED',
    additionalHeaders=report.get('additionalHeaders',[])+headers,
    buildScriptSHA256=digest(Path(__file__)),
    baseCompileReportSHA256=digest(base/'compile-report.json'),
    scope='Candidate 2 objects; threaded AI game-state capture runs after the turn frame dispatches Present. '
        'Requires original-state sync/threaded parity and independent physical validation.')
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
print(report['status'],flush=True)
raise SystemExit(1 if failed else 0)
