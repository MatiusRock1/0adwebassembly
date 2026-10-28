"""Verify optional boundary timers without running the native game."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path('/workspace');out=Path('/phase45-build/script-timing-probe');out.mkdir(exist_ok=True)
stub=out/'emscripten.h';stub.write_text('double emscripten_get_now();\n')
results=[]
for enabled in [0,1]:
    executable=out/('timing-'+str(enabled))
    subprocess.run(['g++','-std=c++20','-O2','-I'+str(out),'-I'+str(root/'wasm/harness'),
        '-DWASM_SCENE_SCRIPT_TIMING_ENABLED='+str(enabled),str(root/'wasm/probes/script-timing.cpp'),
        '-o',str(executable)],check=True)
    result=subprocess.run([str(executable)],capture_output=True,text=True,check=True,timeout=10)
    results.append(json.loads(result.stdout))
report=dict(passed=all(r['passed'] for r in results),results=results,performanceAcceptance=False,
    headerSHA256=hashlib.sha256((root/'wasm/harness/scene-script-timing.h').read_bytes()).hexdigest())
(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
