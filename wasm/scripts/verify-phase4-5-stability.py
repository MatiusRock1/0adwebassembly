"""Continuous original-game WebGPU soak; no screenshots or desktop automation.

This records stability, not a displayed-FPS performance result. Short diagnostic
runs are allowed but can never satisfy the 60-minute stability gate.
"""
import argparse
import json
from pathlib import Path
import time
import traceback
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import (CDP_URL,EVIDENCE_ROOT,start_application,new_test_page,
    enter_fullscreen,observe_shutdown,assert_renderer_clean,renderer_diagnostics,move_original_pointer)
from phase4_flow import open_original_match
from phase4_workload import MANIFEST,populate,observe,observe_counts,live_units,graphics_settings,apply_graphics_profile
from scene_surface import assert_surface

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds',type=int,default=3600)
parser.add_argument('--evidence',type=Path,default=Path(EVIDENCE_ROOT)/'stability-60min')
args=parser.parse_args()
if args.seconds<1:parser.error('--seconds must be positive')
args.evidence.mkdir(parents=True,exist_ok=True)
report=dict(passed=False,stabilityGate60Minutes=False,phase45Accepted=False,
    durationSeconds=args.seconds,samples=[],inputChecks=[],errors=[],console=[],
    screenshots=False,computerUse=False,performanceMeasurement=False)
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL)
    report['browserVersion']=browser.version
    page=new_test_page(browser)
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.on('console',lambda message:report['console'].append(message.text))
    gui=lambda code:page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    try:
        start_application(page)
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult===null')
        report['renderer']=renderer_diagnostics(page)
        assert report['renderer']['backend']=='webgpu'
        page.evaluate('window.application.resumeOriginalAudio()')
        apply_graphics_profile(gui,MANIFEST['graphicsProfile'])
        report['attributes']=open_original_match(gui,MANIFEST['settings'])
        report['graphicsSettings']=graphics_settings(gui)
        report['setup']=populate(gui,page.wait_for_timeout,'skirmish')
        report['fullscreen']=enter_fullscreen(page,browser)
        box=page.locator('#canvas').bounding_box()
        move_original_pointer(page,960,540)
        before=observe(gui);started=time.monotonic();deadline=started+args.seconds
        while time.monotonic()<deadline:
            page.wait_for_timeout(min(30000,max(1,(deadline-time.monotonic())*1000)))
            assert page.evaluate('window.applicationResult===null')
            surface=assert_surface(page,1920,1080)
            assert surface['focused'] and not surface['hidden'] and surface['fullscreen'],surface
            state=observe_counts(gui)
            assert state['rate']==1 and not state['paused'],state
            units=live_units(state)
            assert units>=MANIFEST['minimumLiveUnits'],units
            memory=page.evaluate('''()=>({wasmBytes:window.application.HEAPU8.buffer.byteLength,
              jsHeap:performance.memory?{used:performance.memory.usedJSHeapSize,total:performance.memory.totalJSHeapSize}:null,
              objects:window.webgpuBackend.objects.size,pipelines:window.webgpuBackend.pipelines.size,
              retired:window.webgpuBackend.retired.size,stats:{...window.webgpuBackend.stats},
              frameObserverSamples:window.application.applicationFrames.length,
              workers:window.application.getApplicationWorkerState()})''')
            report['samples'].append(dict(elapsedSeconds=time.monotonic()-started,
                liveUnits=units,state=state,surface=surface,resources=memory))
            # Keep test-only frame telemetry bounded during the hour. This
            # changes no game state, resources, workers or renderer caches.
            page.evaluate('window.application.applicationFrames.length=0')
            if len(report['samples'])%10==0:
                page.keyboard.press('Shift+Space');page.wait_for_timeout(300)
                assert gui('String(Engine.IsPaused())')=='true'
                page.keyboard.press('Shift+Space');page.wait_for_timeout(300)
                assert gui('String(Engine.IsPaused())')=='false'
                camera=gui('JSON.stringify(Engine.GetCameraPosition())')
                page.keyboard.down('ArrowRight');page.wait_for_timeout(300);page.keyboard.up('ArrowRight')
                assert gui('JSON.stringify(Engine.GetCameraPosition())')!=camera
                report['inputChecks'].append(dict(elapsedSeconds=time.monotonic()-started,pauseResume=True,camera=True))
            populate(gui,page.wait_for_timeout,'skirmish',initial=False)
            assert_renderer_clean(page)
            assert not report['errors'] and not any('ERROR:' in line for line in report['console'])
            (args.evidence/'progress.json').write_text(json.dumps(report,indent=2))
            print('WEBGPU_STABILITY',round(time.monotonic()-started),'seconds',units,'units',flush=True)
        report['elapsedSeconds']=time.monotonic()-started
        report['simulationRate']=(state['simulation']['timeElapsed']-before['simulation']['timeElapsed'])/(1000*report['elapsedSeconds'])
        assert abs(report['simulationRate']-1)<.02,report['simulationRate']
        report['passed']=True
    except Exception as error:
        report['failure']=str(error);report['traceback']=traceback.format_exc()
    finally:
        try:
            if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
            if page.evaluate('window.application?.applicationState && window.applicationResult===null'):
                page.locator('#close').click();page.wait_for_function('window.applicationResult!==null',timeout=60000)
                report['shutdown']=observe_shutdown(page,browser)
                assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets']
                assert page.evaluate('window.applicationResult.code')==0
            assert not report['errors']
        except Exception as error:
            report['teardownFailure']=str(error);report['passed']=False
        report['stabilityGate60Minutes']=bool(report['passed'] and args.seconds>=3600 and
            report.get('elapsedSeconds',0)>=3600 and len(report['inputChecks'])>=10 and report.get('shutdown'))
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ('passed','failure','stabilityGate60Minutes')},indent=2))
raise SystemExit(0 if report['passed'] else 1)
