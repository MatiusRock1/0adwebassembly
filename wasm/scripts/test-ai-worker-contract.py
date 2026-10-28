"""CPU transport probe only; this is not the native game or a WASM runtime test."""
from pathlib import Path
import shutil
import subprocess

root=Path('/workspace')
output=Path('/phase45-build/ai-worker-contract');output.mkdir(exist_ok=True)
compiler=shutil.which('g++') or shutil.which('clang++')
if not compiler:raise SystemExit('C++ compiler unavailable')
subprocess.run([compiler,'-std=c++20','-O2','-pthread','-I'+str(root/'source'),
    str(root/'wasm/harness/ai-worker-contract.cpp'),'-o',str(output/'probe')],check=True)
result=subprocess.run([str(output/'probe')],capture_output=True,text=True,timeout=30)
(output/'result.txt').write_text(result.stdout+result.stderr)
print(result.stdout+result.stderr,flush=True)
raise SystemExit(result.returncode)
