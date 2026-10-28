"""Compile and exercise the production queue's ownership/backpressure on CPU."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess

ROOT=Path('/workspace')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--probe',choices=['queue','deferred-audio','deferred-replay','command-data'],default='queue')
args=parser.parse_args()
name,source_name,header_name,checks={
    'queue':('command-queue','webgpu-command-queue.cpp','source/renderer/backend/webgpu/CommandQueue.h',10),
    'command-data':('command-data','webgpu-command-data.cpp','source/renderer/backend/webgpu/CommandData.h',8),
    'deferred-audio':('deferred-audio','application-deferred-audio.cpp','wasm/harness/application-deferred-audio.h',6),
    'deferred-replay':('deferred-replay','application-deferred-replay.cpp','wasm/harness/application-deferred-replay.h',8),
}[args.probe]
OUT=Path('/phase45-build/'+name+'-probe');OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'wasm/probes'/source_name
header=ROOT/header_name
executable=OUT/'probe'
command=['g++','-std=c++20','-pthread','-O2','-I'+str(ROOT/'source'),'-I'+str(ROOT/'wasm/harness'),str(source),'-o',str(executable)]
report=dict(passed=False,performanceAcceptance=False,phase45Accepted=False,command=command,
            sourceSHA256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,header]})
try:
    compiled=subprocess.run(command,capture_output=True,text=True)
    report.update(compileExitCode=compiled.returncode,compileOutput=compiled.stdout+compiled.stderr)
    assert compiled.returncode==0,'Queue probe did not compile'
    run=subprocess.run([str(executable)],capture_output=True,text=True,timeout=15)
    report.update(exitCode=run.returncode,stdout=run.stdout,stderr=run.stderr)
    assert run.returncode==0,'Queue probe failed'
    report['result']=json.loads(run.stdout)
    assert report['result']['passed'] and report['result']['checks']==checks
    report['executableSHA256']=hashlib.sha256(executable.read_bytes()).hexdigest()
    report['passed']=True
except Exception as error:report['failure']=str(error)
finally:(OUT/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:report.get(k) for k in ['passed','failure','result']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
