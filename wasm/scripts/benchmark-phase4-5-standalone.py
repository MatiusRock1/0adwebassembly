"""Independent serial benchmark on the real user's desktop.

No Computer Use, screenshots, video recording, overlays or automatic desktop
captures. The test clicks the game's visible fullscreen button and verifies
OS fullscreen and actual focus. PresentMon measures actual display feedback,
not timer callbacks.
"""
import argparse
import hashlib
from datetime import datetime,timezone
import json
import os
import platform
import shutil
from pathlib import Path
import subprocess
import socket
import sys
import time
from urllib.request import urlopen
from phase45_benchmark_contract import make_plan,fingerprint,summarize,PIN

ROOT=Path(__file__).resolve().parents[2]
SCRIPTS=ROOT/'wasm/scripts'

def wait_url(url,process,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('Child exited before becoming ready: '+url)
        try:
            with urlopen(url,timeout=1) as response:
                if response.status==200:return
        except OSError:pass
        time.sleep(.2)
    raise TimeoutError(url)

def close_browser(endpoint,process):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        connected=p.chromium.connect_over_cdp(endpoint)
        connected.new_browser_cdp_session().send('Browser.close')
    process.wait(timeout=15)

def require_free_port(port):
    if not 0<port<65536:raise ValueError('Invalid localhost port')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',port))

def hardware_inventory():
    command='''[pscustomobject]@{
      CPU=@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
      GPU=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,PNPDeviceID)
      RAM=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
      PowerPlan=(powercfg /getactivescheme)
    } | ConvertTo-Json -Depth 5'''
    result=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    return dict(platform=platform.platform(),inventory=json.loads(result.stdout) if result.returncode==0 else None,
        collectionError=result.stderr if result.returncode else None,
        externalGPUApplicationsClosed='Operator prerequisite; not automatically verified')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backends',nargs='+',choices=['webgpu','webgl','native'],default=['webgpu','webgl','native'])
    parser.add_argument('--workloads',nargs='+',choices=['skirmish','combat'],default=['skirmish','combat'])
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--warmup-seconds',type=int,default=120)
    parser.add_argument('--duration-seconds',type=int,default=900)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--browser','--edge',dest='edge',type=Path,help='Browser executable; defaults to Chrome. --edge remains a compatibility alias.')
    parser.add_argument('--webgl-reference',choices=['paired','frozen'],default='paired',help='Paired GL shares the current actor-variant mapping with WebGPU/native; frozen retains the historical phase-4 build.')
    parser.add_argument('--webgpu-directory',type=Path,default=ROOT/'wasm/dist/application-phase4-5',help='Explicit isolated candidate package; paired GL uses the same package.')
    parser.add_argument('--port',type=int,default=8097)
    parser.add_argument('--cdp-port',type=int,default=9229)
    parser.add_argument('--dry-run',action='store_true',help='Write the run plan only; do not start browsers, GPU work or PresentMon.')
    parser.add_argument('--upload-probe',action='store_true',help='Run GPU upload readback before the WebGPU warmup, never during measurement.')
    parser.add_argument('--verify-persistent-reload',action='store_true',help='Verify combined workers and real IndexedDB reuse on a menu restart before the performance window.')
    args=parser.parse_args()
    plan=make_plan(args.backends,args.repetitions,args.warmup_seconds,args.duration_seconds,args.workloads)
    output=(args.output or ROOT/'docs/wasm/evidence/phase4-5'/('standalone-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(dict(gamePin=PIN,runs=plan,screenshots=False,computerUse=False),indent=2))
    if args.dry_run:
        print('PLAN_ONLY_NO_GPU',output);return 0
    if os.name!='nt':raise RuntimeError('Displayed-frame acceptance requires the Windows/PresentMon test machine')
    if args.port==args.cdp_port:raise ValueError('HTTP and CDP require different ports')
    require_free_port(args.port);require_free_port(args.cdp_port)
    (output/'hardware.json').write_text(json.dumps(hardware_inventory(),indent=2))
    presentmon=ROOT/'wasm/build/tools/PresentMon-2.6.0-x64.exe'
    if not presentmon.is_file():raise FileNotFoundError(presentmon)
    directories={'webgpu':args.webgpu_directory.resolve(),'webgl':args.webgpu_directory.resolve() if args.webgl_reference=='paired' else ROOT/'wasm/dist/webgl-baseline-phase4-5'}
    (output/'reference-policy.json').write_text(json.dumps(dict(webglReference=args.webgl_reference,
        directories={key:str(value) for key,value in directories.items()},
        frozenWebGLBuildSHA256=fingerprint(ROOT/'wasm/dist/webgl-baseline-phase4-5'),
        reason='The paired current GL and WebGPU paths share original actors, full variant diversity and the MSVC-compatible visual sampling. The immutable historical baseline uses libc++ visual distribution and has a known F2 readback defect.'),indent=2))
    hashes={backend:fingerprint(path) for backend,path in directories.items() if backend in args.backends}
    for backend in hashes:
        link_path=directories[backend]/'link-report.json'
        if link_path.is_file():
            link=json.loads(link_path.read_text())
            provenance=(link.get('scriptingArchive') or {}).get('provenance') or {}
            if link.get('diagnosticOnly') or provenance.get('diagnosticOnly'):
                raise RuntimeError('Instrumented diagnostic VM cannot be used for FPS acceptance: '+str(link_path))
    for backend,files in hashes.items():
        if 'pyrogenesis-application.wasm' not in files:raise RuntimeError('Missing packaged backend: '+backend)
    (output/'builds.json').write_text(json.dumps(hashes,indent=2))
    diagnostics={}
    for backend in hashes:
        diagnostics[backend]={}
        for name in ['pyrogenesis-application.mjs.symbols','link-report.json']:
            source=directories[backend]/name
            if source.is_file():
                destination=output/(backend+'-'+name)
                shutil.copy2(source,destination)
                diagnostics[backend][destination.name]=hashlib.sha256(destination.read_bytes()).hexdigest()
    (output/'diagnostic-artifacts.json').write_text(json.dumps(diagnostics,indent=2))
    edge=args.edge or Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Google/Chrome/Application/chrome.exe'
    browser=None;server=None;results={};logs=[]
    env=dict(os.environ,SCENE_CDP_URL=f'http://localhost:{args.cdp_port}',
        SCENE_APPLICATION_URL=f'http://localhost:{args.port}/application.html?automation=1',
        SCENE_FULLSCREEN_TIMEOUT_MS='600000',SCENE_REAL_WINDOW='1',SCENE_AUTO_FULLSCREEN='1')
    print('Medicion sin capturas ni overlays. El juego debe conservar el foco y cubrir la pantalla; las comprobaciones rechazan una perdida de foco.',flush=True)
    try:
        for run in plan:
            backend=run['backend'];stem=f"{backend}-{run['workload']}-{run['repetition']}"
            destination=output/(stem+'.json')
            if backend!='native':
                if not edge.is_file():raise FileNotFoundError(edge)
                if server:
                    server.terminate();server.wait(timeout=10);server=None
                server_log=(output/(stem+'.server.log')).open('w');logs.append(server_log)
                server=subprocess.Popen([sys.executable,str(SCRIPTS/'serve-phase2.py'),'--port',str(args.port),
                    '--directory',str(directories[backend])],cwd=ROOT,stdout=server_log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                wait_url(f'http://localhost:{args.port}/application.html',server)
                if browser is None:
                    browser_log=(output/'browser.log').open('w');logs.append(browser_log)
                    profile=ROOT/'wasm/build/phase4-5'/('standalone-profile-'+str(os.getpid()))
                    # A reused PID must not inherit another build's IndexedDB archives or config.
                    if profile.exists():shutil.rmtree(profile)
                    browser=subprocess.Popen([str(edge),f'--user-data-dir={profile}',f'--remote-debugging-port={args.cdp_port}',
                        '--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check',
                        '--force-high-performance-gpu','--new-window',env['SCENE_APPLICATION_URL']],
                        stdout=browser_log,stderr=subprocess.STDOUT)
                    wait_url(f'http://localhost:{args.cdp_port}/json/version',browser)
                env['SCENE_RENDERER']='webgpu' if backend=='webgpu' else 'gl'
                print(stem+': pantalla completa automatica; la medicion comienza despues del calentamiento.',flush=True)
            elif browser is not None:
                # Close only this runner's browser through its own CDP endpoint.
                close_browser(env['SCENE_CDP_URL'],browser);browser=None
                if server:server.terminate();server.wait(timeout=10);server=None
            script='benchmark-native-phase4.py' if backend=='native' else 'benchmark-phase4.py'
            command=[sys.executable,str(SCRIPTS/script),'--workload',run['workload'],
                '--warmup-seconds',str(run['warmupSeconds']),'--duration-seconds',str(run['durationSeconds']),'--output',str(destination)]
            if backend!='native':command+=['--no-screenshots','--presentmon',str(presentmon)]
            else:command+=['--direct-desktop']
            if args.upload_probe and backend=='webgpu':command+=['--upload-probe']
            if args.verify_persistent_reload and backend=='webgpu':command+=['--verify-persistent-reload']
            with (output/(stem+'.runner.log')).open('w') as log:
                process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                status=process.wait()
            report=json.loads(destination.read_text()) if destination.exists() else dict(passed=False,failure='No measurement report; see runner log')
            report['runnerExitCode']=status
            results[(backend,run['workload'],run['repetition'])]=report
            summary=summarize(plan,results)
            current=next(item for item in summary['runs'] if all(item[key]==run[key] for key in ('backend','workload','repetition')))
            (output/'summary.json').write_text(json.dumps(summary,indent=2))
            print(stem, 'COMPLETE' if report.get('measurementCompleted') else 'FAILED',flush=True)
            if status:raise RuntimeError('Measurement failed; preserved evidence: '+str(output/(stem+'.runner.log')))
            if not current['complete']:
                raise RuntimeError('Measurement, simulation or shutdown invalid; inspect '+str(destination))
            if backend=='webgpu' and current['eligibleForAcceptance'] and not current['gate30']:
                raise RuntimeError('WebGPU displayed/draw 30 FPS or p95 gate failed; preserve this run and fix the bottleneck before further repetitions: '+str(destination))
        return 0 if summarize(plan,results)['webgpuPerformanceGate'] else 1
    finally:
        if server:
            server.terminate();server.wait(timeout=10)
        if browser:
            try:
                close_browser(env['SCENE_CDP_URL'],browser)
            except Exception:pass
        for log in logs:log.close()
        (output/'summary.json').write_text(json.dumps(summarize(plan,results),indent=2))
        print('EVIDENCE',output,flush=True)

if __name__=='__main__':raise SystemExit(main())
