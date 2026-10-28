"""Local Docker orchestration with persistent logs and a quiet-build heartbeat."""
import argparse
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--memory-gib', type=int, default=8)
parser.add_argument('--verify', action='store_true')
parser.add_argument('--native-map', action='store_true')
parser.add_argument('--audit', action='store_true')
parser.add_argument('--link-probe', action='store_true')
parser.add_argument('--map', action='store_true', help='Build and verify original scenario parity')
parser.add_argument('--scene', action='store_true', help='Build original interactive scene')
parser.add_argument('--scene-duration-seconds', type=int, default=900)
args = parser.parse_args()
if args.memory_gib < 1:
    parser.error('memory must be positive')
evidence = root / 'docs/wasm/evidence/phase2'
evidence.mkdir(parents=True, exist_ok=True)
metrics = []

def stage(name, command):
    print(f'[{name}] starting', flush=True)
    started = time.monotonic()
    lines = queue.Queue()
    process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace')
    def collect():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
    threading.Thread(target=collect, daemon=True).start()
    with (evidence / f'{name}.log').open('w', encoding='utf-8') as log:
        while True:
            try:
                line = lines.get(timeout=20)
            except queue.Empty:
                print(f'[{name}] still running: {time.monotonic()-started:.0f}s; log: {log.name}', flush=True)
                continue
            if line is None:
                break
            log.write(line)
            log.flush()
            if 'DONE' in line or 'ERROR' in line or 'PASSED' in line or 'FAILED' in line:
                print(line.rstrip(), flush=True)
    code = process.wait()
    metrics.append({'stage': name, 'durationSeconds': time.monotonic()-started, 'exitCode': code})
    (evidence / 'build-metrics.json').write_text(json.dumps({
        'stages': metrics, 'jobs': 2, 'memoryLimitGiB': args.memory_gib,
        'artifactBytes': sum(p.stat().st_size for p in (root / 'wasm/dist/browser').rglob('*') if p.is_file())
    }, indent=2))
    if code:
        raise SystemExit(f'{name} failed ({code}); see {log.name}')

stage('browser-build', ['docker', 'buildx', 'build', '--resource', f'memory={args.memory_gib}g',
      '--progress', 'plain', '--target', 'browser-artifacts', '--output', 'type=local,dest=wasm/dist/browser',
      '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm'])
if args.verify:
    stage('verify-image', ['docker', 'buildx', 'build', '--load', '--progress', 'plain',
          '--build-context', 'browser=wasm/dist/browser', '-t', '0ad-browser-verify:phase2',
          '-f', 'wasm/docker/browser-verify.Dockerfile', 'wasm'])
    for browser in ['chromium', 'firefox']:
        stage(f'verify-{browser}', ['docker', 'run', '--rm', '--network', 'none', '--memory', '2g',
              '--cpus', '2', '--shm-size', '512m', '--mount', f'type=bind,source={evidence},target=/evidence',
              '0ad-browser-verify:phase2', '--browser', browser])
print('Package: wasm/dist/browser. Serve: wasm/scripts/serve-phase2.ps1', flush=True)

for requested, target, folder in [(args.native_map, 'native-map-artifacts', 'native-map'),
                                  (args.audit, 'phase2-audit-evidence', 'compile-audit'),
                                  (args.link_probe, 'phase2-link-evidence', 'link-probe')]:
    if not requested:
        continue
    stage(folder, ['docker', 'buildx', 'build', '--resource', f'memory={args.memory_gib}g',
          '--progress', 'plain', '--target', target, '--output', f'type=local,dest={evidence / folder}',
          '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm'])
    if folder == 'native-map' and (evidence / folder / 'status.txt').read_text().strip() != 'NATIVE_MAP_REPLAY_PASSED':
        raise SystemExit('Native map failed; inspect exported evidence')
    if folder == 'compile-audit':
        report = json.loads((evidence / folder / 'compile-audit.json').read_text())
        if any(unit['exitCode'] != 0 for unit in report['units']):
            raise SystemExit('Compilation audit failed; inspect exported evidence')
    if folder == 'link-probe':
        report = json.loads((evidence / folder / 'report.json').read_text())
        if report['status'] != 'LINK_PASSED_NOT_EXECUTED':
            raise SystemExit(f"Full simulation integration: {report['status']}; inspect exported evidence")

if args.map or args.scene:
    for target, folder in [('native-map-artifacts', 'native-map'), ('phase2-map-run-evidence', 'map-run')]:
        stage(folder, ['docker', 'buildx', 'build', '--resource', f'memory={args.memory_gib}g',
            '--progress', 'plain', '--target', target, '--output', f'type=local,dest={evidence / folder}',
            '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm'])
    if int((evidence / 'map-run/map-run-exit.txt').read_text()) != 0:
        raise SystemExit('Map runtime failed; inspect map-run evidence')
    stage('map-package', ['docker', 'buildx', 'build', '--resource', f'memory={args.memory_gib}g',
        '--progress', 'plain', '--target', 'phase2-browser-map-artifacts',
        '--output', 'type=local,dest=wasm/dist/map-browser', '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm'])
    if args.verify:
        for browser in ['chromium', 'firefox']:
            stage(f'map-{browser}', ['docker', 'run', '--rm', '--network', 'none', '--memory', '2g',
                '--cpus', '2', '--shm-size', '512m', '--mount', f'type=bind,source={root / "wasm/dist/map-browser"},target=/browser,readonly',
                '--mount', f'type=bind,source={root / "wasm/scripts"},target=/scripts,readonly',
                '--mount', f'type=bind,source={evidence},target=/evidence', '--entrypoint', 'python',
                '0ad-browser-verify:phase2', '/scripts/verify-map-browser.py', '--browser', browser])
        stage('map-parity', ['python', str(root / 'wasm/scripts/verify-map-parity.py')])
if args.scene:
    stage('scene-package', ['docker', 'buildx', 'build', '--resource', f'memory={args.memory_gib}g',
        '--progress', 'plain', '--target', 'phase2-scene-artifacts',
        '--output', 'type=local,dest=wasm/dist/scene-browser', '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm'])
    import shutil
    for name in ['scene.html', 'scene.mjs']:
        shutil.copy2(root / 'wasm/browser' / name, root / 'wasm/dist/scene-browser' / name)
    shutil.copy2(root / 'wasm/browser/scene.html', root / 'wasm/dist/scene-browser/index.html')
    stage('map-restore', ['docker', 'buildx', 'build', '--resource', f'memory={args.memory_gib}g',
        '--progress', 'plain', '--target', 'phase2-map-restore-evidence',
        '--output', f'type=local,dest={evidence / 'restore'}', '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm'])
    stage('asset-evidence', ['docker', 'buildx', 'build', '--progress', 'plain', '--target', 'phase2-native-assets-evidence',
        '--output', f'type=local,dest={evidence / 'assets'}', '-f', 'wasm/docker/spidermonkey.Dockerfile', 'wasm'])
    stage('asset-provenance', ['docker', 'run', '--rm', '--network', 'none', '--memory', '2g', '--cpus', '2',
        '--mount', f'type=bind,source={root / "wasm/scripts"},target=/scripts,readonly',
        '--mount', f'type=bind,source={evidence},target=/evidence', '--entrypoint', 'python3',
        '0ad-wasm-native-baseline:phase1', '/scripts/record-scene-provenance.py'])
    if args.verify:
        scene_command = ['docker', 'run', '--rm', '--network', 'none', '--memory', '4g', '--cpus', '2', '--shm-size', '512m',
            '--mount', f'type=bind,source={root / "wasm/dist/scene-browser"},target=/browser,readonly',
            '--mount', f'type=bind,source={root / "wasm/scripts"},target=/scripts,readonly',
            '--mount', f'type=bind,source={evidence},target=/evidence', '--entrypoint', 'python',
            '0ad-browser-verify:phase2', '/scripts/verify-scene-browser.py', '--browser', 'chromium']
        stage('scene-acceptance', scene_command + ['--duration-seconds', str(args.scene_duration_seconds)])
        shutil.copy2(evidence / 'chromium-scene-report.json', evidence / 'chromium-scene-sustained-report.json')
        stage('scene-focus', scene_command + ['--focus-only'])
        shutil.copy2(evidence / 'chromium-scene-report.json', evidence / 'chromium-scene-focus-report.json')
    print('Interactive scene: wasm/dist/scene-browser. Serve: wasm/scripts/serve-phase2.ps1', flush=True)
