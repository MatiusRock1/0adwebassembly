"""Compare supported SDK exception modes on CPU before any game rebuild."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess

os.environ.update(EMCC_CORES='2',BINARYEN_CORES='2')
ROOT=Path('/workspace');OUT=Path('/phase45-build/exception-runtime-probe');OUT.mkdir(exist_ok=True)
sources=[ROOT/'wasm/probes'/name for name in ['exception-runtime.cpp','exception-runtime-foreign.cpp']]
report=dict(passed=False,diagnosticOnly=True,performanceAcceptance=False,phase45Accepted=False,
    sourceSHA256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},modes={},
    scope='CPU exception/RAII/foreign-call/pthread/PNG-longjmp correctness and synthetic indirect-call overhead. No prediction or acceptance of physical game FPS.')
try:
    foreign=OUT/'foreign.o'
    subprocess.run(['em++','-O2','-pthread','-fno-exceptions','-c',str(sources[1]),'-o',str(foreign)],check=True,capture_output=True,text=True)
    for mode,flag in [('legacy','-fexceptions'),('wasm','-fwasm-exceptions')]:
        command=['em++','-O2','-std=c++20','-pthread',flag,'-sSUPPORT_LONGJMP='+('wasm' if mode=='wasm' else 'emscripten'),'--use-port=libpng','--use-port=zlib',str(sources[0]),str(foreign),
            '-sINITIAL_MEMORY=134217728','-sALLOW_MEMORY_GROWTH=1','-sSTACK_SIZE=5242880','-sPROXY_TO_PTHREAD=1','-sPTHREAD_POOL_SIZE=4',
            '-sENVIRONMENT=node','-sEXIT_RUNTIME=1','-sASSERTIONS=2','-o',str(OUT/(mode+'.js'))]
        with (OUT/(mode+'-build.log')).open('w') as log:built=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        entry=report['modes'][mode]=dict(command=command,linkExitCode=built.returncode)
        assert built.returncode==0,'Inspect '+mode+'-build.log'
        run=subprocess.run(['node',str(OUT/(mode+'.js'))],capture_output=True,text=True,timeout=120)
        entry.update(exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr)
        (OUT/(mode+'-runtime.log')).write_text(run.stdout+run.stderr)
        assert run.returncode==0,'Inspect '+mode+'-runtime.log'
        entry['result']=json.loads(run.stdout.strip().splitlines()[-1])
        assert entry['result']['passed'] and entry['result']['checks']==6
        entry['medianMilliseconds']=statistics.median(entry['result']['milliseconds'])
        print(mode,entry['result'],flush=True)
    assert report['modes']['legacy']['result']['checksum']==report['modes']['wasm']['result']['checksum']
    report['syntheticMedianRatioWasmToLegacy']=report['modes']['wasm']['medianMilliseconds']/report['modes']['legacy']['medianMilliseconds']
    report['passed']=True
except Exception as error:report['failure']=str(error)
finally:(OUT/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:report.get(k) for k in ['passed','failure','syntheticMedianRatioWasmToLegacy']},indent=2),flush=True)
raise SystemExit(0 if report['passed'] else 1)
