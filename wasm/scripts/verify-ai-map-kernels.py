"""Verify the pure numeric kernel against original JS; never runs the native game."""
from pathlib import Path
import subprocess
out=Path('/phase45-build/ai-map-kernels-probe');out.mkdir(exist_ok=True)
subprocess.run(['g++','-std=c++20','-O2','-ffp-contract=off','-I/workspace/source',
    '/workspace/wasm/probes/ai-map-kernels.cpp','-o',str(out/'probe')],check=True)
with (out/'cases.json').open('w') as stream:
    subprocess.run([str(out/'probe')],stdout=stream,check=True)
result=subprocess.run(['node','wasm/scripts/test-ai-map-kernels.mjs',str(out/'cases.json')],
    cwd='/workspace',capture_output=True,text=True,check=True)
(out/'report.json').write_text(result.stdout)
print(result.stdout)
with (out/'obstruction-cases.json').open('w') as stream:
    subprocess.run([str(out/'probe'),'obstruction'],stdout=stream,check=True)
result=subprocess.run(['node','wasm/scripts/test-ai-map-kernels.mjs',str(out/'obstruction-cases.json'),'obstruction'],
    cwd='/workspace',capture_output=True,text=True,check=True)
(out/'obstruction-report.json').write_text(result.stdout)
print(result.stdout)
