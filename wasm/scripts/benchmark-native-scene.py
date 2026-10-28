"""Capture the equivalent native scene; serialize runs with browser benchmarks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from benchmark_lock import BenchmarkLock
from scene_benchmark_contract import contract

parser = argparse.ArgumentParser()
parser.add_argument('--executable', type=Path, default=Path('wasm/build/native-windows/binaries/system/pyrogenesis.exe'))
parser.add_argument('--assets', type=Path, default=Path('wasm/build/native-windows-run'))
parser.add_argument('--warmup-seconds', type=int, default=120)
parser.add_argument('--duration-seconds', type=int, default=900)
parser.add_argument('--presentmon', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.warmup_seconds < 0 or args.duration_seconds <= 0:
    parser.error('Invalid measurement window')
args.output.parent.mkdir(parents=True, exist_ok=True)
executable = args.executable.resolve()
result = {'frames': [], 'errors': [], 'acceptance': 'PENDING', 'fullscreen': True,
          'warmupSeconds': args.warmup_seconds, 'durationSeconds': args.duration_seconds,
          'executableSHA256': hashlib.sha256(executable.read_bytes()).hexdigest(),
          'build': json.loads(Path('docs/wasm/evidence/phase3/native-scene-build.json').read_text())}
result['benchmarkContract'] = contract(args.assets / 'data', args.assets / 'scenario/commands.txt', result['build']['baseCommit'])
pending = queue.Queue()
benchmark_lock = BenchmarkLock()
process = subprocess.Popen([str(executable)], cwd=args.assets.resolve(),
    env=dict(os.environ, SCENE_BENCHMARK_SECONDS=str(args.warmup_seconds + args.duration_seconds + 2)),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
def collect():
    for line in process.stdout:
        pending.put(line)
    pending.put(None)
threading.Thread(target=collect, daemon=True).start()
presentmon = None
capture_log = None
ready = False
started = time.monotonic()
last_progress = started
try:
    with args.output.with_suffix('.log').open('w', encoding='utf-8') as log:
        while True:
            if time.monotonic() - started > args.warmup_seconds + args.duration_seconds + 242:
                raise TimeoutError('Native scene exceeded startup/measurement deadline')
            try:
                line = pending.get(timeout=1)
            except queue.Empty:
                line = ''
            if line is None:
                break
            log.write(line)
            if line.startswith('SCENE_FRAME ') and ready:
                result['frames'].append(json.loads(line[12:]))
            elif line.startswith('SCENE_READY') and not ready:
                ready = True
                result['measurementStartQpcMs'] = time.perf_counter() * 1000
                if args.presentmon:
                    result['presentmonCsv'] = str(args.output.with_suffix('.presentmon.csv'))
                    result['presentationProcessId'] = process.pid
                    capture_log = args.output.with_suffix('.presentmon.log').open('w', encoding='utf-8')
                    presentmon = subprocess.Popen([str(args.presentmon.resolve()), '--process_id', str(process.pid),
                        '--timed', str(args.warmup_seconds + args.duration_seconds + 2), '--terminate_after_timed',
                        '--no_console_stats', '--session_name', '0ad-native-' + str(process.pid),
                        '--output_file', str(args.output.with_suffix('.presentmon.csv').resolve()),
                        '--write_display_metadata', '--qpc_time_ms'], stdout=capture_log, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            elif line.startswith('NATIVE_RENDERER '):
                result.setdefault('hardware', {})['renderer'] = line.strip()[16:]
                print(line.strip(), flush=True)
            elif line.startswith('NATIVE_DRIVER '):
                result.setdefault('hardware', {})['driver'] = line.strip()[14:]
            elif line.startswith('SCENE_STATS '):
                result['lastStats'] = json.loads(line[12:])
            elif line.startswith('SCENE_PLAYER_COLORS '):
                result['playerColors'] = json.loads(line[20:])
            if time.monotonic() - last_progress >= 15:
                print(f'NATIVE_PROGRESS {time.monotonic()-started:.0f}s; {len(result["frames"])} draws', flush=True)
                last_progress = time.monotonic(); log.flush()
    result['exitCode'] = process.wait(timeout=30)
    assert ready and result['exitCode'] == 0 and result['frames'], 'Native startup or exit failed'
    assert all(not frame['paused'] for frame in result['frames']), 'Focus loss invalidated the native benchmark'
    result['passed'] = True
except BaseException as error:
    result['failure'] = str(error)
    if process.poll() is None:
        process.terminate(); process.wait(timeout=15)
    raise
finally:
    if presentmon:
        try:
            result['presentmonExitCode'] = presentmon.wait(timeout=30)
        except subprocess.TimeoutExpired:
            presentmon.terminate(); presentmon.wait(timeout=10)
            result['presentmonFailure'] = 'Capture did not stop within deadline'
        capture_log.close()
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    benchmark_lock.close()
