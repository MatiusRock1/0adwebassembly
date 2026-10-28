"""Run three serialized, complete hardware/display acceptance measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:8089/scene.html')
parser.add_argument('--channel', choices=['msedge', 'chrome'], default='msedge')
parser.add_argument('--presentmon', type=Path, required=True)
parser.add_argument('--output-directory', type=Path, default=Path('docs/wasm/evidence/phase3/final-release'))
args = parser.parse_args()
scripts = Path(__file__).resolve().parent
root = scripts.parents[1]
args.output_directory.mkdir(parents=True, exist_ok=True)
report = {'passed': False, 'minimumDisplayedFps': 30, 'maximumP95FrameMs': 33.4,
          'warmupSeconds': 120, 'durationSeconds': 900, 'runs': [],
          'scope': 'Phase 3 original 37-entity scene; full game performance requires phase 4',
          'nativeParity': 'Optimization objective, not the operator-authorized minimum'}
try:
    for number in range(1, 4):
        profile = args.output_directory / f'{args.channel}-{number}.json'
        print(f'ACCEPTANCE_REPETITION {number}/3', flush=True)
        subprocess.run([sys.executable, '-u', str(scripts / 'benchmark-phase3.py'),
                        '--url', args.url, '--channel', args.channel,
                        '--high-performance-gpu', '--angle', 'd3d11',
                        '--presentmon', str(args.presentmon), '--output', str(profile)], check=True)
        draw_path = profile.with_name(profile.stem + '-draw-analysis.json')
        display_path = profile.with_name(profile.stem + '-display-analysis.json')
        for script, destination in [('analyze-scene-profile.py', draw_path),
                                    ('analyze-presentation.py', display_path)]:
            subprocess.run([sys.executable, str(scripts / script), str(profile),
                            '--output', str(destination)], check=True, stdout=subprocess.DEVNULL)
        data = json.loads(profile.read_text())
        draw = json.loads(draw_path.read_text())
        display = json.loads(display_path.read_text())
        source_hash = hashlib.sha256((root / 'wasm/harness/scene-main.cpp').read_bytes()).hexdigest()
        assert data['build']['applicationSourceSHA256'] == source_hash, 'Obsolete application binary'
        assert data.get('benchmarkContract'), 'Missing fixed scene identity'
        assert data['browserWindow']['bounds']['windowState'] == 'fullscreen', 'Native fullscreen missing'
        assert data['surface']['proxiedDepthAttachment'] == [1920, 1080], 'Actual framebuffer is not 1080p'
        assert not data.get('errors') and not data.get('failure') and data['exit']['passed'], 'Runtime failure'
        assert draw['submissionGate30'] and draw['simulationRateValid'], 'Draw or simulation gate failed'
        assert display['presentationGate30'], 'Physical display gate failed'
        identity = {'contract': data['benchmarkContract'], 'applicationSourceSHA256': source_hash,
                    'artifacts': data['build']['artifacts'],
                    'hardware': {k: v for k, v in data['hardware'].items() if k != 'timeOriginMs'},
                    'browserVersion': data['browserVersion'], 'playerColors': data['playerColors']}
        if 'identity' in report:
            assert identity == report['identity'], 'Build/hardware/scene changed between repetitions'
        else:
            report['identity'] = identity
        heap = [sample['wasmBytes'] for sample in data['memorySamples'] if sample['wasmBytes'] is not None]
        report['runs'].append({'profile': str(profile), 'drawAnalysis': str(draw_path),
                               'displayAnalysis': str(display_path),
                               'displayedFps': display['displayedFps'], 'p95FrameMs': display['p95FrameMs'],
                               'p99FrameMs': display['p99FrameMs'], 'onePercentLowFps': display['onePercentLowFps'],
                               'pausesOver100Ms': display['pausesOver100Ms'], 'tickRate': draw['tickRate'],
                               'wasmHeapMinBytes': min(heap), 'wasmHeapMaxBytes': max(heap)})
        print(f"ACCEPTANCE_RUN_PASSED {number}: {display['displayedFps']:.2f} displayed FPS; "
              f"p95 {display['p95FrameMs']:.2f} ms; ticks {draw['tickRate']:.3f}/s", flush=True)
    report['passed'] = True
except BaseException as error:
    report['failure'] = str(error)
    raise
finally:
    (args.output_directory / 'acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
