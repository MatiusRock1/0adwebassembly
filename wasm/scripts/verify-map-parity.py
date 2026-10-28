"""Compare original serialized bytes and every browser checkpoint with native."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
evidence = root / 'docs/wasm/evidence/phase2'
native = evidence / 'native-map'
node = evidence / 'map-run'
references = json.loads((native / 'native-checkpoints.json').read_text())
report = {'nodeExitCode': int((node / 'map-run-exit.txt').read_text()), 'checkpoints': [], 'browsers': {}}
for reference in references:
    tick = reference['tick']
    expected = (native / f'tick-{tick:04d}.dat').read_bytes()
    actual = (node / 'states' / f'tick-{tick}.dat').read_bytes()
    report['checkpoints'].append({'tick': tick, 'bytes': len(actual),
        'nativeSHA256': hashlib.sha256(expected).hexdigest(),
        'nodeSHA256': hashlib.sha256(actual).hexdigest(), 'identicalBytes': actual == expected})
for browser in ['chromium', 'firefox']:
    result = json.loads((evidence / f'{browser}-map-report.json').read_text())
    checkpoints = result['mapResult']['checkpoints']
    report['browsers'][browser] = {'version': result['version'],
        'exitCode': result['mapResult']['exitCode'], 'isolated': result['isolated'],
        'heartbeat': result['heartbeat'], 'checkpoints': checkpoints,
        'passed': result['mapResult']['passed'] and
            [c['tick'] for c in checkpoints] == [r['tick'] for r in references] and
            all(c['sha256'] == r['serializedStateSHA256'] for c, r in zip(checkpoints, references))}
report['passed'] = report['nodeExitCode'] == 0 and all(c['identicalBytes'] for c in report['checkpoints']) and all(b['passed'] for b in report['browsers'].values())
(evidence / 'map-parity.json').write_text(json.dumps(report, indent=2))
print('MAP_PARITY_PASSED' if report['passed'] else 'MAP_PARITY_FAILED')
raise SystemExit(0 if report['passed'] else 1)
