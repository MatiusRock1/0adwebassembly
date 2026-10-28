"""Analyze committed draw samples. These are submissions, not display feedback."""
import argparse
import json
import math
from pathlib import Path
import statistics

def analyze(data, warmup_seconds=120, duration_seconds=900):
    frames = data.get('frames', [])
    if not frames:
        raise ValueError('No draw samples')
    start = frames[0]['timeMs'] + warmup_seconds * 1000
    selected = [f for f in frames if start <= f['timeMs'] <= start + duration_seconds * 1000]
    intervals = [b['timeMs'] - a['timeMs'] for a, b in zip(selected, selected[1:])]
    if not intervals or any(t <= 0 for t in intervals):
        raise ValueError('Insufficient samples or restarted/non-monotonic clock')
    def percentile(values, fraction):
        return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]
    elapsed = sum(intervals)
    worst = sorted(intervals, reverse=True)[:max(1, math.ceil(len(intervals) * .01))]
    result = {'samples': len(selected), 'measuredSeconds': elapsed / 1000,
              'submittedFps': len(intervals) * 1000 / elapsed,
              'medianFrameMs': statistics.median(intervals),
              'p95FrameMs': percentile(intervals, .95), 'p99FrameMs': percentile(intervals, .99),
              'onePercentLowFps': 1000 / statistics.mean(worst),
              'onePercentLowFormula': '1000 / mean(slowest ceil(N*0.01) frame intervals in ms)',
              'pausesOver100Ms': sum(t > 100 for t in intervals),
              'cpuMeanMs': {key: statistics.mean(f[key] for f in selected)
                            for key in ['tickMs', 'interpolateMs', 'uploadMs', 'rendererMs', 'presentMs']},
              'maxBacklogMs': max(f['backlogMs'] for f in selected),
              'hardware': data.get('hardware'), 'acceptance': 'PENDING',
              'performanceObjective': 'At least 30 displayed FPS sustained at 1080p; native parity remains an optimization objective',
              'nativePerformanceParity': 'PENDING',
              'thresholdPurpose': 'submissionGate30/60 measure submissions, not acceptance gates without display feedback',
              'limitations': ['No physical presentation feedback', 'GPU and GC timing unavailable',
                              'Hardware identity, parity and three repetitions require independent evidence',
                              'Native parity is an optimization objective; display feedback and three repetitions establish the accepted 30 FPS minimum']}
    full = elapsed >= duration_seconds * 1000 - 1000
    valid = full and all(f['width'] == 1920 and f['height'] == 1080 and not f['paused'] for f in selected)
    contiguous = all(b['frame'] == a['frame'] + 1 and b['tick'] >= a['tick'] for a, b in zip(selected, selected[1:]))
    result['submissionGate30'] = valid and contiguous and result['submittedFps'] >= 30 and result['p95FrameMs'] <= 33.4
    result['submissionGate60'] = valid and contiguous and result['submittedFps'] >= 60 and result['p95FrameMs'] <= 16.8
    result['tickRate'] = (selected[-1]['tick'] - selected[0]['tick']) * 1000 / elapsed
    result['simulationRateValid'] = 4.9 <= result['tickRate'] <= 5.1 and result['maxBacklogMs'] < 1000
    result['submissionGate30'] &= result['simulationRateValid']
    result['submissionGate60'] &= result['simulationRateValid']
    for field in ['scriptMs', 'gcMs', 'gpuProbeProxyMs', 'receiveCostMs', 'wasmHeapBytes']:
        values = [f[field] for f in selected if field in f and f[field] >= 0]
        if values:
            result[field + 'Mean'] = statistics.mean(values)
            result[field + 'Max'] = max(values)
    gpu = [f['gpuMs'] for f in selected if f.get('gpuMs', -1) >= 0]
    result['gpuSamples'] = len(gpu)
    if gpu:
        result['gpuMeanMs'] = statistics.mean(gpu)
        result['gpuP95Ms'] = percentile(gpu, .95)
    result['limitations'][1] = 'GPU optional/asynchronous; GC and inclusive script callback windows overlap CPU subsystem timings'
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', type=Path)
    parser.add_argument('--warmup-seconds', type=int, default=120)
    parser.add_argument('--duration-seconds', type=int, default=900)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.warmup_seconds < 0 or args.duration_seconds <= 0:
        parser.error('Invalid measurement window')
    result = analyze(json.loads(args.profile.read_text(encoding='utf-8')), args.warmup_seconds, args.duration_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
