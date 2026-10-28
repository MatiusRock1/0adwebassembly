"""Analyze displayed swap-chain frames from a dedicated fullscreen benchmark.

PresentMon tracks the application window, not the simulation's native frame ID.
Keep that attribution limit explicit and retain raw CSV/drop data.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from phase45_benchmark_contract import assess_worker_presentation

def analyze(profile, rows, refresh_ms=None, refresh_source=None):
    start = profile['measurementStartQpcMs'] + profile['warmupSeconds'] * 1000
    end = start + profile['durationSeconds'] * 1000
    by_chain = {}
    for row in rows:
        if row.get('CPUStartQPCTimeInMs') in [None, 'NA']:
            continue
        qpc = float(row['CPUStartQPCTimeInMs'])
        if start <= qpc <= end and int(row['ProcessID']) == profile['presentationProcessId']:
            by_chain.setdefault(row['SwapChainAddress'], []).append(row)
    if not by_chain:
        raise ValueError('No presentation feedback in the requested measurement window')
    chain, selected = max(by_chain.items(), key=lambda pair: len(pair[1]))
    displayed = [r for r in selected if r.get('MsUntilDisplayed') not in [None, 'NA']]
    intervals = [float(r['MsBetweenDisplayChange']) for r in displayed
                 if r.get('MsBetweenDisplayChange') not in [None, 'NA'] and float(r['MsBetweenDisplayChange']) > 0]
    if not intervals:
        raise ValueError('Display tracking unavailable; submitted frames cannot substitute for it')
    def percentile(values, fraction):
        return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]
    qpcs = [float(r['CPUStartQPCTimeInMs']) for r in selected]
    full = min(qpcs) <= start + 1000 and max(qpcs) >= end - 1000
    valid_draws = bool(profile.get('frames')) and all(not f['paused'] and f['width'] == 1920 and f['height'] == 1080 for f in profile['frames'])
    # A compositor can present repeatedly without a new engine draw. Display
    # feedback alone must not approve duplicated game images.
    draws=profile.get('frames',[])
    draw_times=[frame['receivedMs'] for frame in draws if isinstance(frame.get('receivedMs'),(int,float))]
    rendered_fps=((len(draw_times)-1)*1000/(draw_times[-1]-draw_times[0])
                  if len(draw_times)>1 and draw_times[-1]>draw_times[0] else 0)
    draw_intervals=[later-earlier for earlier,later in zip(draw_times,draw_times[1:])]
    draw_p95=percentile(draw_intervals,.95) if draw_intervals and all(t>0 for t in draw_intervals) else None
    draw_start=profile.get('measurementStartBrowserMs',0)+profile['warmupSeconds']*1000
    draw_coverage=bool(draw_times) and draw_times[0]<=draw_start+1000 and draw_times[-1]>=draw_start+profile['durationSeconds']*1000-1000
    worst = sorted(intervals, reverse=True)[:max(1, math.ceil(len(intervals) * .01))]
    actual_surface = ('browserVersion' not in profile or
                      (profile.get('surface', {}).get('proxiedDepthAttachment') == [1920, 1080]
                       and profile.get('browserWindow', {}).get('bounds', {}).get('windowState') == 'fullscreen'))
    worker_presentation = assess_worker_presentation(profile)
    valid = actual_surface and profile.get('presentmonEventsLost', 0) == 0 and full and valid_draws and profile.get('fullscreen') is True and profile.get('presentmonExitCode') == 0 and worker_presentation['valid']
    gate30 = valid and draw_coverage and rendered_fps >= 30 and draw_p95 is not None and draw_p95 <= 33.4 and 1000 / statistics.mean(intervals) >= 30 and percentile(intervals, .95) <= 33.4
    # Operator clarification (2026-10-23): 33.4 ms means "at most two display
    # refreshes". Measure this display's refresh from single-refresh intervals;
    # half-percent tolerance covers PresentMon timestamp jitter only.
    single = [t for t in intervals if 12.0 <= t <= 21.0]
    refresh = statistics.median(single) if len(single) >= len(intervals) * .2 else None
    source = 'median single-refresh interval' if refresh else None
    # A paced capture shows almost no single-refresh intervals by design; its
    # refresh then comes from the same display measured in another capture.
    if refresh_ms:
        refresh, source = refresh_ms, refresh_source or 'explicit --refresh-ms'
    two_refresh_limit = 2 * refresh * 1.005 if refresh else None
    gate_two_refresh = (valid and draw_coverage and rendered_fps >= 30 and two_refresh_limit is not None
                        and 1000 / statistics.mean(intervals) >= 30 and percentile(intervals, .95) <= two_refresh_limit)
    return {'swapChain': chain, 'processId': profile['presentationProcessId'],
            'otherChains': {key: len(value) for key, value in by_chain.items() if key != chain},
            'presents': len(selected), 'displayedPresents': len(displayed),
            'notDisplayed': len(selected) - len(displayed), 'displayIntervals': len(intervals),
            'displayedFps': 1000 / statistics.mean(intervals),
            'engineRenderedFps':rendered_fps,'engineDrawWindowComplete':draw_coverage,'engineP95FrameMs':draw_p95,
            'medianFrameMs': statistics.median(intervals), 'p95FrameMs': percentile(intervals, .95),
            'p99FrameMs': percentile(intervals, .99), 'onePercentLowFps': 1000 / statistics.mean(worst),
            'pausesOver100Ms': sum(t > 100 for t in intervals),
            'measurementComplete': full,
            'actualSurfaceVerified': actual_surface,
            'presentmonEventsLost': profile.get('presentmonEventsLost', 0),
            'validFullscreen1080pRun': valid,
            'presentationGate30': gate30,
            'measuredRefreshMs': refresh,
            'refreshSource': source,
            'twoRefreshLimitMs': two_refresh_limit,
            'presentationGateTwoRefresh': gate_two_refresh,
            'engineP95WithinTwoRefresh': draw_p95 is not None and two_refresh_limit is not None and draw_p95 <= two_refresh_limit,
            'twoRefreshScope': 'Operator clarification: physical p95 <= two measured refreshes; engine draw p95 is reported separately and not relaxed here',
            'workerPresentation': worker_presentation,
            'attribution': 'Dedicated fullscreen window swap chain; native simulation frame IDs are not exposed by PresentMon',
            'acceptance': 'Individual 30 FPS gate; closure requires three complete 900-second repetitions and functional checks'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--refresh-ms', type=float,
                        help='Refresh of the same display measured elsewhere, for captures without single-refresh intervals.')
    parser.add_argument('--refresh-source', help='Where --refresh-ms was measured; recorded in the output.')
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    with Path(profile['presentmonCsv']).open(encoding='utf-8-sig', newline='') as stream:
        result = analyze(profile, list(csv.DictReader(stream)), args.refresh_ms, args.refresh_source)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
