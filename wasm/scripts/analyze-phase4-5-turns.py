"""Group original Update wall timers by simulation-tick change; no CPU attribution."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def summarize(values):
    ordered=sorted(values)
    if not ordered:return dict(count=0)
    def quantile(fraction):
        index=(len(ordered)-1)*fraction
        low,high=math.floor(index),math.ceil(index)
        return ordered[low]+(ordered[high]-ordered[low])*(index-low)
    return dict(count=len(ordered),median=quantile(.5),p95=quantile(.95),maximum=ordered[-1],
        over33_4=sum(v>33.4 for v in ordered),over100=sum(v>100 for v in ordered))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    payload=args.report.read_bytes();report=json.loads(payload)
    groups={'turn':[],'betweenTurns':[]};previous=None
    for frame in report['frames']:
        if previous is not None:
            groups['turn' if frame['tick']!=previous else 'betweenTurns'].append(frame['updateMilliseconds'])
        previous=frame['tick']
    result=dict(sourceSHA256=hashlib.sha256(payload).hexdigest(),
        scope='Original Update wall timers grouped by changed simulation tick; first observation omitted; not CPU-exclusive cost.',
        groups={key:summarize(values) for key,values in groups.items()})
    args.report.with_name('stutter-analysis.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
