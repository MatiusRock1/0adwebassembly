"""Run original-game functional checks independently, without Computer Use.

Launch on the real user's desktop. The test clicks the visible fullscreen
button and verifies OS fullscreen, actual focus and render dimensions.
Functional screenshots are saved as evidence; this suite makes no performance
claim.
"""
import shutil
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
SCRIPTS=ROOT/'wasm/scripts'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--browser','--edge',dest='edge',type=Path,help='Browser executable; defaults to Chrome. --edge remains a compatibility alias.')
    parser.add_argument('--port',type=int,default=8097)
    parser.add_argument('--cdp-port',type=int,default=9229)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    output=(args.output or ROOT/'docs/wasm/evidence/phase4-5'/('functional-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    # Refresh both native references in the same run, rather than silently
    # relying on historical checkpoints produced with different test scripts.
    jobs=[('native-systems','verify-phase4-native.py',['--advanced']),
          ('native-capture','verify-phase4-native.py',['--capture']),
          ('gpu-border','verify-phase4-5-border.py',[]),
          ('wgsl-modules','verify-phase4-5-shaders.py',['--adapted']),
          ('original-input','verify-phase4-input.py',[]),
          ('multimonitor-pointer','verify-phase4-5-pointer.py',[]),
          ('original-combat-victory','verify-phase4-combat.py',[]),
          ('research-trade','verify-phase4-parity.py',['--advanced','--native',str(output/'native-systems')]),
          ('capture-parity','verify-phase4-parity.py',['--capture','--native',str(output/'native-capture')]),
          ('original-audio-persistence','verify-phase4-audio.py',[]),
          ('three-matches','verify-phase4-match.py',['--cdp',f'http://localhost:{args.cdp_port}','--cycles','3']),
          ('lifecycle','verify-phase4-5-lifecycle.py',[]),
          ('stability-60min','verify-phase4-5-stability.py',[])]
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(dict(jobs=jobs,computerUse=False,performanceMeasurement=False),indent=2))
    if args.dry_run:print('PLAN_ONLY_NO_GPU',output);return 0
    if os.name!='nt':raise RuntimeError('This suite needs the prepared original native Windows build')
    helpers=runpy.run_path(str(SCRIPTS/'benchmark-phase4-5-standalone.py'))
    if args.port==args.cdp_port:raise ValueError('HTTP and CDP require different ports')
    for port in (args.port,args.cdp_port):helpers['require_free_port'](port)
    edge=args.edge or Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Google/Chrome/Application/chrome.exe'
    if not edge.is_file():raise FileNotFoundError(edge)
    if not (ROOT/'wasm/build/native-phase4/binaries/system/pyrogenesis.exe').is_file():raise RuntimeError('Prepare the pinned native game before running parity checks')
    env=dict(os.environ,SCENE_CDP_URL=f'http://localhost:{args.cdp_port}',
        SCENE_APPLICATION_URL=f'http://localhost:{args.port}/application.html?automation=1',
        SCENE_RENDERER='webgpu',SCENE_EVIDENCE_ROOT=str(output),SCENE_FULLSCREEN_TIMEOUT_MS='600000',
        SCENE_AUTO_FULLSCREEN='1')
    browser=None;server=None;results=[];logs=[]
    try:
        for name,script,options in jobs:
            if not name.startswith('native-') and browser is None:
                server_log=(output/'server.log').open('w');logs.append(server_log)
                server=subprocess.Popen([sys.executable,str(SCRIPTS/'serve-phase2.py'),'--port',str(args.port),
                    '--directory',str(ROOT/'wasm/dist/application-phase4-5')],cwd=ROOT,stdout=server_log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                helpers['wait_url'](f'http://localhost:{args.port}/application.html',server)
                browser_log=(output/'browser.log').open('w');logs.append(browser_log)
                browser_profile=ROOT/'wasm/build/phase4-5'/('functional-profile-'+str(os.getpid()))
                # A reused PID must not inherit another build's IndexedDB archives or config.
                if browser_profile.exists():shutil.rmtree(browser_profile)
                browser=subprocess.Popen([str(edge),f'--user-data-dir={browser_profile}',
                    f'--remote-debugging-port={args.cdp_port}','--remote-debugging-address=127.0.0.1',
                    '--no-first-run','--no-default-browser-check','--force-high-performance-gpu','--new-window',env['SCENE_APPLICATION_URL']],
                    stdout=browser_log,stderr=subprocess.STDOUT)
                helpers['wait_url'](f'http://localhost:{args.cdp_port}/json/version',browser)
            command=[sys.executable,str(SCRIPTS/script),*options]
            if script!='verify-phase4-input.py':
                evidence=output/name
                if script in ('verify-phase4-5-border.py','verify-phase4-5-shaders.py'):evidence=evidence/'report.json'
                command+=['--evidence',str(evidence)]
            print('CHECK',name,'- pantalla completa y foco verificados por la prueba.',flush=True)
            with (output/(name+'.runner.log')).open('w') as log:
                result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            path=output/name/'report.json'
            report=json.loads(path.read_text()) if path.is_file() else {}
            passed=result.returncode==0 and report.get('passed') is True
            results.append(dict(name=name,passed=passed,exitCode=result.returncode,report=str(path)))
            (output/'summary.json').write_text(json.dumps(dict(phase45Accepted=False,performanceMeasured=False,checks=results),indent=2))
            if not passed:raise RuntimeError('Check failed; evidence preserved: '+str(path))
        return 0
    finally:
        if browser:
            try:helpers['close_browser'](env['SCENE_CDP_URL'],browser)
            except Exception:pass
        if server:server.terminate();server.wait(timeout=10)
        for log in logs:log.close()
        (output/'summary.json').write_text(json.dumps(dict(phase45Accepted=False,performanceMeasured=False,
            allPlannedChecksPassed=len(results)==len(jobs) and all(r['passed'] for r in results),checks=results),indent=2))
        print('EVIDENCE',output,flush=True)

if __name__=='__main__':raise SystemExit(main())
