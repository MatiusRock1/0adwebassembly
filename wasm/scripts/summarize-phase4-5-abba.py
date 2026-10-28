"""Summarize one batch of short combat decision captures; never phase acceptance.

Per capture: physical display intervals (PresentMon, in refreshes of the
display), turn-frame update times from the engine frame log, simulation rate,
units and the render worker's paced-present counters. A paced build shows
almost no single-refresh intervals, so the refresh is measured on the batch's
reference captures (same display, same session) and applied to all of them.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def quantile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def display_intervals(report):
    start = report['measurementStartQpcMs'] + report['warmupSeconds'] * 1000
    end = start + report['durationSeconds'] * 1000
    with Path(report['presentmonCsv']).open(encoding='utf-8-sig', newline='') as stream:
        rows = [row for row in csv.DictReader(stream)
                if row.get('CPUStartQPCTimeInMs') not in (None, 'NA')
                and start <= float(row['CPUStartQPCTimeInMs']) <= end
                and int(row['ProcessID']) == report['presentationProcessId']]
    chains = {}
    for row in rows:
        chains.setdefault(row['SwapChainAddress'], []).append(row)
    selected = max(chains.values(), key=len)
    return [float(row['MsBetweenDisplayChange']) for row in selected
            if row.get('MsUntilDisplayed') not in (None, 'NA')
            and row.get('MsBetweenDisplayChange') not in (None, 'NA') and float(row['MsBetweenDisplayChange']) > 0]


def capture(path):
    report = json.loads((path / 'webgpu-combat-1.json').read_text(encoding='utf-8'))
    presentation = json.loads((path / 'presentation-two-refresh.json').read_text(encoding='utf-8'))
    turns, previous = [], None
    for frame in report['frames']:
        if previous is not None and frame['tick'] != previous:
            turns.append(frame['updateMilliseconds'])
        previous = frame['tick']
    initial = (report.get('initialRendererWork') or {}).get('presentation') or {}
    final = (report.get('finalRendererWork') or {}).get('presentation') or {}
    paced = None
    if 'pacedPresents' in final:
        paced = dict(presents=final['pacedPresents'] - initial.get('pacedPresents', 0),
                     holds=final['pacedHolds'] - initial.get('pacedHolds', 0),
                     intervals=[b - a for a, b in zip(initial.get('pacedIntervals', [0] * 5), final['pacedIntervals'])])
    units = [sample['liveUnits'] for sample in report['samples'] if isinstance(sample.get('liveUnits'), int)]
    return dict(path=path.name, report=report, presentation=presentation, intervals=display_intervals(report),
                turns=turns, paced=paced, units=[min(units), max(units)] if units else None)


def summarize(entry, refresh):
    intervals, turns, presentation = entry['intervals'], entry['turns'], entry['presentation']
    refreshes = [max(1, round(value / refresh)) for value in intervals]
    histogram = [sum(r == n for r in refreshes) / len(refreshes) for n in (1, 2, 3)] + [sum(r >= 4 for r in refreshes) / len(refreshes)]
    two_refresh_limit = 2 * refresh * 1.005
    return dict(
        capture=entry['path'], valid=presentation['validFullscreen1080pRun'],
        displayedFps=presentation['displayedFps'], p95FrameMs=presentation['p95FrameMs'],
        p99FrameMs=presentation['p99FrameMs'], onePercentLowFps=presentation['onePercentLowFps'],
        pausesOver100Ms=presentation['pausesOver100Ms'],
        p95WithinTwoRefreshes=quantile(intervals, .95) <= two_refresh_limit if intervals else False,
        intervalShareByRefreshes=dict(zip(['1', '2', '3', '4+'], histogram)),
        turnFrames=len(turns), turnMedianMs=statistics.median(turns), turnP90Ms=quantile(turns, .9),
        turnsOver60Ms=sum(t > 60 for t in turns), turnsOver100Ms=sum(t > 100 for t in turns),
        rate=entry['report'].get('tickRate'),
        rateWithinTolerance=entry['report'].get('simulationTiming', {}).get('withinTolerance'),
        units=entry['units'], workerPacing=entry['paced'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, nargs='+', required=True, help='Reference capture directories.')
    parser.add_argument('--candidate', type=Path, nargs='+', required=True, help='Candidate capture directories.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = [capture(path) for path in args.reference]
    candidate = [capture(path) for path in args.candidate]
    single = [value for entry in reference for value in entry['intervals'] if 12.0 <= value <= 21.0]
    refresh = statistics.median(single)
    result = dict(
        diagnosticOnly=True, phase45Accepted=False,
        refreshMs=refresh, refreshSource='median single-refresh interval of the reference captures',
        reference=[summarize(entry, refresh) for entry in reference],
        candidate=[summarize(entry, refresh) for entry in candidate],
        scope='Short decision captures in alternating order; differences under the run-to-run spread are not attributed.')
    for side in ('reference', 'candidate'):
        rows = result[side]
        result[side + 'Mean'] = {key: statistics.mean(row[key] for row in rows) for key in
                                 ['displayedFps', 'p95FrameMs', 'p99FrameMs', 'onePercentLowFps', 'pausesOver100Ms',
                                  'turnMedianMs', 'turnP90Ms', 'turnsOver60Ms', 'turnsOver100Ms', 'rate']}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['refreshMs', 'referenceMean', 'candidateMean']}, indent=2))
    for row in result['reference'] + result['candidate']:
        print(row['capture'], 'valid' if row['valid'] else 'INVALID', 'p95<=2r' if row['p95WithinTwoRefreshes'] else 'p95>2r',
              {key: round(value, 3) for key, value in row['intervalShareByRefreshes'].items()}, 'units', row['units'],
              'pacing', row['workerPacing'])


if __name__ == '__main__':
    main()
