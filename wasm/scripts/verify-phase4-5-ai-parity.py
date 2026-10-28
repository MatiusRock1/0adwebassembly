"""Compare original synchronous and threaded AI in the same WASM package.

Limited semantic checkpoints only: never a native-game or physical FPS test.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--checkpoints',type=int,nargs='+',default=[10000,30000])
    args=parser.parse_args()
    if args.checkpoints!=sorted(set(args.checkpoints)) or args.checkpoints[0]<=0:
        parser.error('Checkpoints must be positive, unique and increasing')
    package=args.package.resolve()
    if not json.loads((package/'link-report.json').read_text()).get('aiWorker'):
        parser.error('Explicit isolated AI package required')
    args.output.mkdir(parents=True,exist_ok=False)
    report=dict(passed=False,phase45Accepted=False,performanceAcceptance=False,
        scope='Same WASM package, sync versus threaded AI; exact original simulation serialization at limited checkpoints, no native executable.',runs=[],checks=[])
    try:
        runs=[]
        for mode in ['sync','threaded']:
            destination=args.output/mode
            command=[sys.executable,str(Path(__file__).with_name('profile-phase4-5.py')),
                '--webgpu-directory',str(package),'--ai-worker-mode',mode,
                '--seconds','1','--settle-seconds','0','--simulation-checkpoints',
                *map(str,args.checkpoints),'--output',str(destination)]
            entry=dict(mode=mode,command=command)
            report['runs'].append(entry)
            print('AI_PARITY_START',mode,flush=True)
            result=subprocess.run(command,timeout=900)
            entry['exitCode']=result.returncode
            path=destination/'report.json'
            if not path.exists():raise RuntimeError('Missing runtime report for '+mode)
            run=json.loads(path.read_text());runs.append(run)
            if result.returncode or not run['passed'] or run.get('engineErrors'):
                raise RuntimeError('Invalid runtime in '+mode+': '+str(run.get('failure')))
        first,last=runs
        assert first['buildSHA256']==last['buildSHA256'],'Packages changed between runs'
        assert first['attributes']==last['attributes'],'Original game attributes differ'
        assert len(first['checkpoints'])==len(last['checkpoints'])==len(args.checkpoints)
        for before,after,target in zip(first['checkpoints'],last['checkpoints'],args.checkpoints):
            check=dict(simulationMs=target,
                exactTimes=before['simulationMs']==after['simulationMs']==target,
                serializationMatches=(args.output/'sync'/f'state-{target}.bin').read_bytes()==(args.output/'threaded'/f'state-{target}.bin').read_bytes(),
                nonLocalDebugMatches=before['nonLocalDebugSHA256']==after['nonLocalDebugSHA256'],
                guiStateMatches=before['state']==after['state'],
                syncSHA256=before['serializedSHA256'],threadedSHA256=after['serializedSHA256'])
            report['checks'].append(check)
        report['passed']=all(all(c[k] for k in ['exactTimes','serializationMatches','nonLocalDebugMatches','guiStateMatches']) for c in report['checks'])
        if not report['passed']:report['failure']='Original simulation checkpoint divergence; do not adopt candidate'
    except Exception as error:
        report['failure']=str(error)
    finally:
        (args.output/'comparison.json').write_text(json.dumps(report,indent=2))
    print('AI_PARITY_RESULT',json.dumps(dict(passed=report['passed'],checks=report['checks'],failure=report.get('failure'))),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
