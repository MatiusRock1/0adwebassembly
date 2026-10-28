"""Differential CPU check of SDK AL error semantics, without an audio device."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess

os.environ.update(EMCC_CORES='2',BINARYEN_CORES='2')
root=Path('/workspace');out=Path('/phase45-build/audio-error-probe');out.mkdir(exist_ok=True)
source=root/'wasm/probes/application-openal-error.cpp'
helper=root/'wasm/harness/application-openal-error.cpp'
library=root/'wasm/browser/application-openal-error.js'
sdk=Path('/emsdk/upstream/emscripten/src/lib/libopenal.js')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(passed=False,diagnosticOnly=True,performanceAcceptance=False,phase45Accepted=False,
    sourceSHA256={str(p):digest(p) for p in [source,helper,library,sdk]},modes={},
    scope='Real SDK AL functions and synthetic internal context records in Node/pthreads. Error values/reset, inactive contexts, concurrent readers, concurrent context switches, heap growth and id reuse. No audio device or game-FPS claim.')
try:
    for mode in ['sdk','shared']:
        command=['em++','-O2','-std=c++20','-pthread','-fwasm-exceptions','-sSUPPORT_LONGJMP=wasm',
            str(source),str(helper),'-lopenal','-sINITIAL_MEMORY=134217728','-sALLOW_MEMORY_GROWTH=1',
            '-sSTACK_SIZE=5242880','-sPROXY_TO_PTHREAD=1','-sPTHREAD_POOL_SIZE=4',
            '-sENVIRONMENT=node','-sEXIT_RUNTIME=1','-sASSERTIONS=2']
        if mode=='shared':command+=['--js-library',str(library)]
        command+=['-o',str(out/(mode+'.js'))]
        with (out/(mode+'-build.log')).open('w') as log:build=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        entry=report['modes'][mode]=dict(command=command,compileExitCode=build.returncode)
        assert build.returncode==0,'Inspect '+mode+'-build.log'
        run=subprocess.run(['node',str(out/(mode+'.js'))],capture_output=True,text=True,timeout=120)
        entry.update(exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr)
        (out/(mode+'-runtime.log')).write_text(run.stdout+run.stderr)
        assert run.returncode==0,'Inspect '+mode+'-runtime.log'
        entry['result']=json.loads(run.stdout.strip().splitlines()[-1])
        assert entry['result']['passed'] and entry['result']['checks']==15
        entry['medianMilliseconds']=statistics.median(entry['result']['milliseconds'])
        print(mode,entry['result'],flush=True)
    report['passed']=True
except Exception as error:report['failure']=str(error)
finally:(out/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure']},indent=2),flush=True)
raise SystemExit(0 if report['passed'] else 1)
