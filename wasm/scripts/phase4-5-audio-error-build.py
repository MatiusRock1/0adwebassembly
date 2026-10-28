"""Extend the verified native-EH control with shared OpenAL error state only."""
import hashlib
import argparse
import difflib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

os.environ.update(EMCC_CORES='2',BINARYEN_CORES='2')
started=time.monotonic()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--after-present',action='store_true',help='Isolated audio maintenance after enqueueing Present and its ordered frame receipt.')
parser.add_argument('--worker-ensure',action='store_true',help='Move periodic playback checks onto the existing sound worker; preserve streaming cadence.')
args=parser.parse_args()
assert not (args.after_present and args.worker_ensure)
base=Path('/phase45-build/application-wasm-eh')
variant='audio-worker' if args.worker_ensure else 'audio-after-present' if args.after_present else 'audio-error'
out=Path('/phase45-build/application-'+variant);out.mkdir(exist_ok=True)
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
if (args.after_present or args.worker_ensure) and not compiled.returncode:
    # Reproduce the control compiler's container-local include preparation.
    # A fresh container has the same immutable dependencies but no /tmp links.
    includes=Path('/tmp/phase4-includes');includes.mkdir(exist_ok=True)
    for name in ['boost','enet','libxml']:
        target=includes/name
        if not target.exists():target.symlink_to(Path('/spike/headless/include')/name)
    shutil.copytree('/spike/headless/include/fmt',includes/'fmt',dirs_exist_ok=True)
    fmt=includes/'fmt/core.h'
    fmt.write_text(fmt.read_text().replace('parse_format_string<true>(str_, checker(s, {}))','parse_format_string<true>(str_, checker(str_, {}))'))
    private=out/'source';private.mkdir(exist_ok=True)
    if args.worker_ensure:
        from phase45_audio_worker import adapt,adapt_base
        shutil.copytree(roots['source']/'soundmanager',private/'soundmanager',dirs_exist_ok=True)
        queue_header=private/'soundmanager/application-audio-ensure.h'
        shutil.copy2('/workspace/wasm/experiments/audio-worker/application-audio-ensure.h',queue_header)
        report['additionalHeaders']=[dict(path=str(queue_header),SHA256=digest(queue_header))]
        changed=['soundmanager/SoundManager.cpp','soundmanager/items/CSoundBase.cpp']
    else:
        backend=private/'renderer/backend/webgpu'
        shutil.copytree(roots['source']/'renderer/backend/webgpu',backend,dirs_exist_ok=True)
        shutil.copy2(roots['source']/'main.cpp',private/'main.cpp')
        changed=['main.cpp','renderer/backend/webgpu/Device.cpp']
    patches=[]
    for relative in changed:
        path=private/relative;before=path.read_text();after=before
        if args.worker_ensure:
            after=(adapt if relative.endswith('/SoundManager.cpp') else adapt_base)(before)
        elif relative=='main.cpp':
            audio='\tWasmApplication::RunDeferredAudioIdle(); // fallback when rendering is skipped\n'
            assert after.count(audio)==1
            after=after.replace(audio,'',1)
            receipt='\t\tg_Game && g_Game->m_Paused, phase4UpdateMilliseconds, realTimeSinceLastFrame * 1000);\n'
            assert after.count(receipt)==1
            after=after.replace(receipt,receipt+'\n'+audio,1)
        else:
            flush='        WasmApplication::replayFlushes.Drain();\n        WasmApplication::RunDeferredAudioIdle();\n        FlushCommands();'
            assert after.count(flush)==1
            after=after.replace(flush,'        WasmApplication::replayFlushes.Drain();\n        FlushCommands();',1)
        path.write_text(after)
        patches.append(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative)))
        index=next(i for i,r in enumerate(report['results']) if r['source']==relative)
        command=list(report['results'][index]['command'])
        target=out/(relative.replace('/','_')+'.o')
        command[command.index('-c')+1]=str(path);command[command.index('-o')+1]=str(target)
        unit_log=target.with_suffix('.log')
        with unit_log.open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
        entry=dict(source=relative,sourceFile=str(path),sourceSHA256=digest(path),object=str(target),
            command=command,exitCode=result.returncode,log=str(unit_log))
        if not result.returncode:entry['objectSHA256']=digest(target)
        report['results'][index]=entry
        if result.returncode:break
    (out/('audio-worker.patch' if args.worker_ensure else 'audio-after-present.patch')).write_text(''.join(patches))
failed=[r['source'] for r in report['results'] if r['exitCode']]
base_seconds=report.pop('seconds',None)
report.update(status='COMPILE_FAILED' if failed else 'COMPILE_PASSED_NOT_LINKED',
    baseCompileSeconds=base_seconds,seconds=time.monotonic()-started,
    baseCompileReportSHA256=digest(base/'compile-report.json'),
    additionalJSLibraries=[dict(path=str(library),SHA256=digest(library))],
    platformExperiment='shared-openal-error-worker-ensure' if args.worker_ensure else 'shared-openal-error-after-present' if args.after_present else 'shared-openal-error',
    scope='Native-EH control plus shared AL-error cell. Private optional two-unit variants: after-Present maintenance (retired), or periodic EnsurePlay checks on the existing audio worker with generation-checked coalescing and original streaming cadence. Original scripts, quality, simulation, and explicit play/pause/stop API semantics preserved; worker variant synchronizes playback flags with item commands.',
    failed=failed,notAttempted=[],phase45Accepted=False)
(out/'compile-report.json').write_text(json.dumps(report,indent=2))
print(report['status'],len(report['results']),'units;',480 if args.after_present or args.worker_ensure else 482,'verified control objects retained',flush=True)
raise SystemExit(1 if failed else 0)
