"""Correlate original simulation updates with ordered engine-frame receipts.

Offline only. Receipt intervals include scheduling/encoding, not exclusive CPU
time, and PresentMon does not expose the original engine frame IDs.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('report',type=Path)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
source=json.loads(args.report.read_text())
frames=source['frames'];groups={'turn':[],'betweenTurns':[]};skipped=0
for previous,current in zip(frames,frames[1:]):
    interval=current['receivedMs']-previous['receivedMs']
    if current['frame']!=previous['frame']+1 or interval<=0 or current['tick']<previous['tick']:
        skipped+=1;continue
    group='turn' if current['tick']>previous['tick'] else 'betweenTurns'
    groups[group].append(dict(frame=current['frame'],tick=current['tick'],
        turns=current['tick']-previous['tick'],receiptIntervalMs=interval,
        updateMs=current['updateMilliseconds']))

def stats(values):
    if not values:return dict(count=0)
    ordered=sorted(values)
    quantile=lambda fraction:ordered[max(0,math.ceil(len(ordered)*fraction)-1)]
    return dict(count=len(values),totalSeconds=sum(values)/1000,medianMs=statistics.median(values),
        p95Ms=quantile(.95),p99Ms=quantile(.99),maximumMs=max(values),
        over33_4Ms=sum(x>33.4 for x in values),over100Ms=sum(x>100 for x in values))

all_rows=[row for rows in groups.values() for row in rows]
result=dict(diagnosticOnly=True,performanceAcceptance=False,phase45Accepted=False,
    inputSHA256=hashlib.sha256(args.report.read_bytes()).hexdigest(),frames=len(frames),skippedIntervals=skipped,
    groups={name:dict(updates=stats([r['updateMs'] for r in rows]),
                     receipts=stats([r['receiptIntervalMs'] for r in rows])) for name,rows in groups.items()},
    worstUpdates=sorted(all_rows,key=lambda r:r['updateMs'],reverse=True)[:20],
    worstReceipts=sorted(all_rows,key=lambda r:r['receiptIntervalMs'],reverse=True)[:20],
    scope='Correlation only: original Game::Update wall duration, turn IDs, and ordered post-encoding receipt times. No direct mapping to physical display frames or exclusive CPU attribution.')
args.output.write_text(json.dumps(result,indent=2))
print(json.dumps(dict(frames=result['frames'],skippedIntervals=skipped,groups=result['groups']),indent=2))
