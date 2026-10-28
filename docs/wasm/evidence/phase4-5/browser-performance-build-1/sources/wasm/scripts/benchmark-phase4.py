from phase4_browser import APPLICATION_URL, CDP_URL, EVIDENCE_ROOT, start_application, assert_renderer_clean
"""Visible full-game measurement with original load and physical presentation."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match
from phase4_workload import MANIFEST, MANIFEST_PATH, populate, observe, issue_orders, graphics_settings,apply_graphics_profile
from phase4_browser import observe_shutdown, enter_fullscreen, new_test_page, renderer_diagnostics
from scene_surface import assert_surface
from phase45_benchmark_contract import assess_backlog,assess_simulation_rate
from phase45_window_focus import foreground_window,activate_browser_window

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workload', choices=['skirmish','combat'], required=True)
parser.add_argument('--warmup-seconds', type=int, default=120)
parser.add_argument('--duration-seconds', type=int, default=900)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--presentmon', type=Path, default=Path('wasm/build/tools/PresentMon-2.6.0-x64.exe'))
parser.add_argument('--no-screenshots',action='store_true',help='Record only counters/CSV; never capture the desktop or canvas.')
parser.add_argument('--upload-probe',action='store_true',help='Verify GPU upload bytes before creating the match or starting warmup.')
parser.add_argument('--verify-persistent-reload',action='store_true',help='Verify combined features and disk-cache reuse before the only FPS window.')
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
report = dict(passed=False, phase4Accepted=False, errors=[], console=[], frames=[],
              samples=[], commandTrace=[], workload=args.workload,
              warmupSeconds=args.warmup_seconds,durationSeconds=args.duration_seconds,
              manifest=MANIFEST,manifestSHA256=hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest())
report['harnessSHA256']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    for name in [Path(__file__).name,'phase4_workload.py','phase4_flow.py','phase4_browser.py','phase45_window_focus.py']}
capture = None
capture_log = args.output.with_suffix('.presentmon.log').open('w',encoding='utf-8')
with BenchmarkLock(), sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    page = new_test_page(browser)
    page.bring_to_front()
    page.add_init_script('''
      window.phase4LongTasks=[];window.phase4InputEvents=[];
      if(PerformanceObserver.supportedEntryTypes.includes('longtask'))
        new PerformanceObserver(list=>{for(const entry of list.getEntries())
          window.phase4LongTasks.push({startMs:entry.startTime,durationMs:entry.duration});
        }).observe({type:'longtask',buffered:true});
      for(const type of ['keydown','keyup','pointerdown','pointerup'])
        document.addEventListener(type,event=>window.phase4InputEvents.push({
          type,timeStamp:event.timeStamp,receivedMs:performance.now(),trusted:event.isTrusted}),true);
    ''')
    page.on('pageerror',lambda error:report['errors'].append(dict(message=str(error),stack=error.stack)))
    page.on('console',lambda message:report['console'].append(message.text))
    def gui(code):
        report['lastGUIRequest']=code
        return page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    try:
        assert 'functional-frame-frequency' not in APPLICATION_URL,'Functional fixed clocks are forbidden in performance measurements'
        start_application(page)
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult === null')
        if args.verify_persistent_reload:
            features=page.evaluate('window.applicationFeatures')
            assert all(features.get(key) is True for key in ('simdEngine','renderWorker','asyncPipelines','persistentArchives','persistentConfig')),features
            assert features.get('asyncSuspension') in ('jspi','asyncify'),features
            first=page.evaluate('async()=>await window.application.archiveService.snapshot()')
            assert first['persistent'] and first['reads']>0 and first['peakResidentBytes']<=first['maxMemoryBytes'],first
            assert page.evaluate('window.application.persistentConfig.available')
            assert gui("JSON.stringify(Engine.ConfigDB_SaveChanges('user'))")=='true'
            config_before=page.evaluate("async()=>{await window.application.persistentConfig.flush();return window.application.FS.readFile('/persistent-config/user.cfg',{encoding:'utf8'});}")
            page.locator('#close').click()
            page.wait_for_function('window.applicationResult !== null',timeout=30000)
            restart_shutdown=observe_shutdown(page,browser)
            assert restart_shutdown['workers']==[] and restart_shutdown['liveApplicationTargets']==[],restart_shutdown
            start_application(page)
            page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
            assert page.evaluate('window.applicationResult === null')
            second=page.evaluate('async()=>await window.application.archiveService.snapshot()')
            assert second['persistent'] and second['persistentHits']>0 and second['peakResidentBytes']<=second['maxMemoryBytes'],second
            assert page.evaluate('window.rendererDiagnostics.owner')=='render-worker'
            config_after=page.evaluate("window.application.FS.readFile('/persistent-config/user.cfg',{encoding:'utf8'})")
            assert config_before==config_after,'IDBFS settings bytes changed across restart'
            report['persistentReloadProbe']=dict(passed=True,first=first,second=second,shutdown=restart_shutdown,
                configBytesPreserved=True,configSHA256=hashlib.sha256(config_before.encode()).hexdigest(),
                scope='Real original-menu restart and IndexedDB block reuse before warmup; not a second FPS measurement')
        report['applicationArguments']=page.evaluate('window.application.arguments')
        report['frameTimeSource']=page.evaluate('window.application.applicationClock?.timeSource || "original-filtered-frequency"')
        assert not any(value.startswith('-fixed-frame-frequency') for value in report['applicationArguments']),'Fixed simulation clock is forbidden in performance measurements'
        report['renderer']=renderer_diagnostics(page)
        report['runtimeFeatures']=page.evaluate('window.applicationFeatures || {}')
        report['initialArchiveWork']=page.evaluate('async()=>await window.application.archiveService?.snapshot() || null')
        if args.upload_probe:
            report['uploadProbe']=page.evaluate('async()=>{const {verifyUploadBelt,verifyTextureCommands}=await import("./webgpu-upload-probe.mjs");const backend=window.application.webgpuBackend;if(backend.remote)return await backend.probeUploads();const device=backend.device;const buffers=await verifyUploadBelt(device);return {...buffers,textureCommands:await verifyTextureCommands(device)};}')
        apply_graphics_profile(gui,MANIFEST['graphicsProfile'])
        report['screenshotsEnabled']=not args.no_screenshots
        page.locator('#audio').click()
        report['attributes']=open_original_match(gui,MANIFEST['settings'])
        report['graphicsSettings']=graphics_settings(gui)
        report['setup']=populate(gui,page.wait_for_timeout,args.workload)
        report['commandTrace'].extend(report['setup']['trace'])
        processes=browser.new_browser_cdp_session().send('SystemInfo.getProcessInfo')['processInfo']
        owners=[process for process in processes if process['type'].lower()=='browser']
        assert len(owners)==1,owners
        try:report['preMeasurementActivation']=activate_browser_window(int(owners[0]['id']))
        except RuntimeError as error:report['preMeasurementActivationFailure']=str(error)
        # The real fullscreen-button activation can succeed even if Windows
        # refused the preceding programmatic activation. Actual ownership is
        # still mandatory below, before starting PresentMon or measurement.
        report['fullscreenVerification']=enter_fullscreen(page,browser)
        page.wait_for_timeout(2000)
        report['surface']=assert_surface(page,1920,1080)
        report['fullscreen']=True
        report['browserVersion']=browser.version
        cdp=browser.new_browser_cdp_session()
        target=page.context.new_cdp_session(page).send('Target.getTargetInfo')['targetInfo']['targetId']
        report['browserWindow']=cdp.send('Browser.getWindowForTarget',dict(targetId=target))
        assert report['browserWindow']['bounds']['windowState']=='fullscreen',report['browserWindow']
        report['systemInfo']=cdp.send('SystemInfo.getInfo')
        processes=cdp.send('SystemInfo.getProcessInfo')['processInfo']
        owners=[process for process in processes if process['type'].lower()=='browser']
        assert len(owners)==1,owners
        browser_process=int(owners[0]['id'])
        report['foregroundWindow']=foreground_window(browser_process)
        gpu=[process for process in processes if process['type'].lower()=='gpu']
        assert len(gpu)==1
        report['presentationProcessId']=gpu[0]['id']
        report['presentmonCsv']=str(args.output.with_suffix('.presentmon.csv').resolve())
        session='0ad-phase4-'+str(gpu[0]['id'])
        capture=subprocess.Popen([str(args.presentmon.resolve()),'--process_id',str(gpu[0]['id']),
          '--timed',str(args.warmup_seconds+args.duration_seconds+90),'--terminate_after_timed',
          '--no_console_stats','--session_name',session,'--output_file',report['presentmonCsv'],
          '--write_display_metadata','--qpc_time_ms'],stdout=capture_log,stderr=subprocess.STDOUT,
          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        page.wait_for_timeout(45000)
        if not args.no_screenshots:page.screenshot(path=str(args.output.with_suffix('.start.png')))
        # Preparation samples are outside the measured interval. Drop that
        # test-only history so a 1020-second run cannot hit the observer's
        # 65000-entry shifting limit because of time spent loading/preparing.
        page.evaluate('window.application.applicationFrames.length=0')
        report['initialRendererWork']=page.evaluate('async()=>{const backend=window.application.webgpuBackend;return backend?.remote?await backend.snapshot():{stats:backend?.stats || null,uploadBelt:backend?.uploadBelt?.stats || null,asyncSequence:window.application.webgpuAsyncSequence || 0};}')
        report['measurementStartQpcMs']=time.perf_counter()*1000
        report['measurementStartBrowserMs']=page.evaluate('performance.now()')
        initial_state_start=time.perf_counter()*1000
        report['initialState']=observe(gui)
        report['initialStateIntervalQpcMs']=[initial_state_start,time.perf_counter()*1000]
        deadline=time.monotonic()+args.warmup_seconds+args.duration_seconds
        while time.monotonic()<deadline:
            page.wait_for_timeout(min(30000,max(1,(deadline-time.monotonic())*1000)))
            assert_renderer_clean(page)
            assert page.evaluate('window.applicationResult === null')
            surface=assert_surface(page,1920,1080)
            assert surface['fullscreen']
            assert surface['focused'] and not surface['hidden'],'Browser lost actual foreground focus during measurement'
            actual_window=foreground_window(browser_process)
            observation_started=time.perf_counter()
            state=observe(gui)
            observation_ms=(time.perf_counter()-observation_started)*1000
            assert state['rate']==1 and not state['paused'],state
            units=sum(len(player['units']) for player in state['players'])
            report['samples'].append(dict(qpcMs=time.perf_counter()*1000,state=state,observationMilliseconds=observation_ms,
               liveUnits=units,foregroundWindow=actual_window,workers=page.evaluate('window.application.getApplicationWorkerState()')))
            if units<MANIFEST['minimumLiveUnits']:
                raise RuntimeError('Declared original unit load fell below 200')
            maintenance_started=time.perf_counter()
            prepared=populate(gui,page.wait_for_timeout,args.workload)
            report['samples'][-1]['workloadMaintenanceMilliseconds']=(time.perf_counter()-maintenance_started)*1000
            report['commandTrace'].extend(prepared['trace'])
            elapsed=round(args.warmup_seconds+args.duration_seconds-max(0,deadline-time.monotonic()))
            args.output.with_suffix('.progress.json').write_text(json.dumps(dict(elapsedSeconds=elapsed,liveUnits=units,state=state['simulation']['timeElapsed'])))
            print('FULL_GAME_BENCHMARK',args.workload,elapsed,'seconds',units,'units',flush=True)
        end=report['measurementStartBrowserMs']+(args.warmup_seconds+args.duration_seconds)*1000
        start=report['measurementStartBrowserMs']+args.warmup_seconds*1000
        frames=page.evaluate('window.application.applicationFrames')
        report['frames']=[frame for frame in frames if start<=frame['receivedMs']<=end and frame['gameStarted']]
        report['spiderMonkeyGC']=page.evaluate('window.application.applicationGC || []')
        report['browserLongTasks']=page.evaluate('window.phase4LongTasks')
        report['browserInputEvents']=page.evaluate('window.phase4InputEvents')
        report['finalRendererWork']=page.evaluate('async()=>{const backend=window.application.webgpuBackend;return backend?.remote?await backend.snapshot():{stats:backend?.stats || null,uploadBelt:backend?.uploadBelt?.stats || null,asyncSequence:window.application.webgpuAsyncSequence || 0};}')
        report['finalArchiveWork']=page.evaluate('async()=>await window.application.archiveService?.snapshot() || null')
        report['metricScope']='updateMilliseconds measures original CGame::Update; GC records original SpiderMonkey slice callbacks. Browser input events measure DOM receipt, not simulation command acknowledgement.'
        last_state_start=time.perf_counter()*1000
        report['lastState']=observe(gui)
        report['lastStateIntervalQpcMs']=[last_state_start,time.perf_counter()*1000]
        report['measurementCompleted']=True
        report['simulationTiming']=assess_simulation_rate(report)
        report['tickRate']=report['simulationTiming'].get('rate',0)
        assert report['simulationTiming']['withinTolerance'],report['simulationTiming']
        report['backlog']=assess_backlog(report)
        assert report['backlog']['nonGrowing'],report['backlog']
        report['engineErrors']=[line for line in report['console'] if 'ERROR:' in line]
        assert not report['engineErrors'] and not report['errors']
        assert_renderer_clean(page)
        report['passed']=True
    except Exception as error:
        report['failure']=str(error) or type(error).__name__
        report['failureType']=type(error).__name__
        report['runtimeFailure']=page.evaluate('window.applicationResult || null')
        if report['runtimeFailure'] and report['runtimeFailure'].get('error'):
            report['failure']=report['runtimeFailure']['error']
        report['failureFrames']=page.evaluate('window.application?.applicationFrames?.slice(-10) || []')
        report['failureClock']=page.evaluate('window.application?.applicationClock || null')
    finally:
        if capture:
            subprocess.run([str(args.presentmon.resolve()),'--session_name',session,'--terminate_existing_session'],stdout=capture_log,stderr=subprocess.STDOUT,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            report['presentmonExitCode']=capture.wait(timeout=30)
        capture_log.close()
        report['presentmonEventsLost']=sum(int(count) for count in re.findall(r'(\d+) ETW events were lost',args.output.with_suffix('.presentmon.log').read_text(errors='replace')))
        args.output.write_text(json.dumps(report,indent=2))
        try:
            if page.evaluate('document.fullscreenElement !== null'):
                page.evaluate('document.exitFullscreen()')
            if page.evaluate('window.application?.applicationState && window.applicationResult === null'):
                report['audioAfterMeasurement']=page.evaluate('window.application.getOriginalAudioState()')
                page.locator('#close').click()
                page.wait_for_function('window.applicationResult !== null',timeout=60000)
                report['shutdown']=observe_shutdown(page,browser)
                report['exitCode']=page.evaluate('window.applicationResult.code')
                assert report['exitCode']==0
                assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets']
        except Exception as error:
            report['teardownFailure']=str(error);report['passed']=False
        if capture and report.get('measurementCompleted'):
            spec=importlib.util.spec_from_file_location('presentation',Path(__file__).with_name('analyze-presentation.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with Path(report['presentmonCsv']).open(encoding='utf-8-sig',newline='') as stream:
                report['presentation']=module.analyze(report,list(csv.DictReader(stream)))
        args.output.write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure','presentation','tickRate']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
