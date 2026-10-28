"""Sequential short WebAssembly diagnostics; never full phase acceptance.

Preserve both raw runs and check browser/driver/workload comparability rather
than attributing performance differences across different environments.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def nvidia_drivers(hardware):
    return sorted((gpu['Name'],gpu['DriverVersion']) for gpu in hardware['inventory']['GPU'] if 'NVIDIA' in gpu['Name'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    report=dict(diagnosticOnly=True,phase45Accepted=False,complete=False,runs=[],
        scope='Two sequential fullscreen WASM diagnostics, 120+120 s each; not statistical significance or full phase acceptance')
    try:
        raw=[];hardware=[]
        for label,package in [('reference',args.reference),('candidate',args.candidate)]:
            out=args.output/label
            command=[sys.executable,str(Path(__file__).with_name('benchmark-phase4-5-standalone.py')),
                '--webgpu-directory',str(package.resolve()),'--backends','webgpu',
                '--workloads','skirmish','--repetitions','1','--warmup-seconds','120',
                '--duration-seconds','120','--upload-probe','--output',str(out)]
            entry=dict(label=label,package=str(package.resolve()),command=command)
            report['runs'].append(entry)
            (args.output/'comparison.json').write_text(json.dumps(report,indent=2))
            print('SEQUENTIAL_WASM_DIAGNOSTIC',label,flush=True)
            result=subprocess.run(command,timeout=900)
            entry['runnerExitCode']=result.returncode
            data=json.loads((out/'webgpu-skirmish-1.json').read_text())
            if not data.get('passed') or not data.get('measurementCompleted'):
                raise RuntimeError('Invalid runtime capture for '+label+': '+str(data.get('failure')))
            presentation=data['presentation']
            if not all(presentation.get(key) for key in ['measurementComplete','actualSurfaceVerified','validFullscreen1080pRun']) or presentation.get('presentmonEventsLost')!=0:
                raise RuntimeError('Invalid physical presentation capture for '+label)
            # A standalone runner exits 1 on a failed performance gate too.
            entry.update(runtimePassed=True,presentation=data['presentation'],
                browserVersion=data['browserVersion'],simulationTiming=data['simulationTiming'])
            raw.append(data);hardware.append(json.loads((out/'hardware.json').read_text()))
        before,after=raw
        checks=dict(browser=before['browserVersion']==after['browserVersion'],
            nvidiaDriver=bool(nvidia_drivers(hardware[0])) and nvidia_drivers(hardware[0])==nvidia_drivers(hardware[1]),
            manifest=before['manifestSHA256']==after['manifestSHA256'],
            graphics=before['graphicsSettings']==after['graphicsSettings'],
            adapter=before['renderer']['adapter']==after['renderer']['adapter'])
        report.update(complete=True,comparability=checks,comparable=all(checks.values()))
        if not report['comparable']:report['limitation']='Environment/workload checks differ; do not attribute a difference to the candidate'
    except Exception as error:
        report['failure']=str(error)
    finally:
        (args.output/'comparison.json').write_text(json.dumps(report,indent=2))
    print('SEQUENTIAL_WASM_RESULT',json.dumps(report),flush=True)
    return 0 if report['complete'] and report.get('comparable') else 1


if __name__=='__main__':raise SystemExit(main())
