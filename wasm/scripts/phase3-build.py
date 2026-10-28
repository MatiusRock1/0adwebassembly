"""Quiet-build heartbeat and durable logs for reproducible scene profiles."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

parser = argparse.ArgumentParser()
parser.add_argument('--profile', choices=['debug', 'o2', 'o3', 'o3-lto'], default='o2')
parser.add_argument('--context', choices=['proxied', 'owned'], default='proxied')
parser.add_argument('--memory-gib', type=int, default=8)
parser.add_argument('--verify-parity', action='store_true')
args = parser.parse_args()
if args.memory_gib < 1:
    parser.error('Memory must be positive')
root = Path(__file__).resolve().parents[2]
evidence = root / 'docs/wasm/evidence/phase3'
evidence.mkdir(parents=True, exist_ok=True)
package_name = 'scene-' + args.profile + ('-owned' if args.context == 'owned' else '')
metrics = []

def stage(name, target, destination):
    command = ['docker', 'buildx', 'build', '--resource', f'memory={args.memory_gib}g',
               '--progress', 'plain', '--target', target, '--build-arg', 'SCENE_PROFILE=' + args.profile,
               '--build-arg', 'SCENE_CONTEXT=' + args.context, '--output', 'type=local,dest=' + destination,
               '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm']
    started = time.monotonic()
    pending = queue.Queue()
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace')
    def collect():
        for line in process.stdout:
            pending.put(line)
        pending.put(None)
    threading.Thread(target=collect, daemon=True).start()
    print(name + ' starting', flush=True)
    with (evidence / (name + '.log')).open('w', encoding='utf-8') as log:
        while True:
            try:
                line = pending.get(timeout=20)
            except queue.Empty:
                print(f'{name}: {time.monotonic()-started:.0f}s; {log.name}', flush=True)
                continue
            if line is None:
                break
            log.write(line); log.flush()
            if 'PASSED' in line or 'ERROR' in line or 'FAILED' in line:
                print(line.rstrip(), flush=True)
    code = process.wait()
    metrics.append(dict(stage=name, exitCode=code, seconds=time.monotonic()-started))
    (evidence / ('build-metrics-' + args.profile + '-' + args.context + '.json')).write_text(
        json.dumps(dict(jobs=2, memoryLimitGiB=args.memory_gib, stages=metrics), indent=2))
    if code:
        raise SystemExit(f'{name} failed ({code}); inspect {log.name}')

stage('build-' + args.profile + '-' + args.context, 'phase3-scene-artifacts', 'wasm/dist/' + package_name)
package = root / 'wasm/dist' / package_name
for name in ['scene.html', 'scene.mjs']:
    shutil.copy2(root / 'wasm/browser' / name, package / name)
shutil.copy2(package / 'scene.html', package / 'index.html')
manifest_path = package / 'build-profile.json'
manifest = json.loads(manifest_path.read_text())
manifest['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in package.iterdir()
                         if p.suffix in ['.mjs', '.wasm', '.data', '.html']}
manifest_path.write_text(json.dumps(manifest, indent=2))
shutil.copy2(manifest_path, evidence / ('build-' + args.profile + '-' + args.context + '.json'))
if args.verify_parity:
    stage('parity-' + args.profile + '-' + args.context, 'phase3-parity-evidence',
          'docs/wasm/evidence/phase3/parity-' + args.profile + '-' + args.context)
print('Serve: serve-phase2.ps1 -Directory wasm/dist/' + package_name, flush=True)
