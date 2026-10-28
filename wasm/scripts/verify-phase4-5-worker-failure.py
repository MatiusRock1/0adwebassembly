"""Controlled SDK worker-error cleanup and explicit reload; never FPS evidence."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import CDP_URL,start_application,new_test_page,enter_fullscreen,observe_shutdown
from phase45_benchmark_contract import fingerprint

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=False)
report=dict(passed=False,phase45Accepted=False,performanceAcceptance=False,
    scope='Controlled SDK worker error, not reproduction or resolution of the native null-function fault',errors=[],console=[],
    buildSHA256=fingerprint(Path('wasm/dist/application-phase4-5')))
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL)
    page=new_test_page(browser)
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.on('console',lambda message:report['console'].append(message.text))
    try:
        start_application(page)
        page.wait_for_function('window.application?.applicationState',timeout=180000)
        page.evaluate('window.application.resumeOriginalAudio()')
        report['fullscreen']=enter_fullscreen(page,browser)
        report['before']=page.evaluate('({audio:application.getOriginalAudioState(),workers:application.getApplicationWorkerState()})')
        assert report['before']['workers']['running']
        assert any(context['playingSources']>0 for context in report['before']['audio']['contexts'])
        page.evaluate('setTimeout(()=>application.triggerApplicationWorkerErrorForTest(),0)')
        page.wait_for_function('applicationResult?.error?.includes("Controlled SDK worker failure")',timeout=60000)
        page.evaluate('async()=>await applicationCleanup')
        report['fatalResult']=page.evaluate('applicationResult')
        report['shutdown']=observe_shutdown(page,browser)
        assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets']
        assert all(not report['shutdown']['sdk'][name] for name in ['running','pooled','pthreads'])
        report['after']=page.evaluate('({audio:application.getOriginalAudioState(),fullscreen:!!document.fullscreenElement,pointerLocked:!!document.pointerLockElement,gpuDisposed:webgpuBackend.disposed,status:document.getElementById("status").textContent})')
        assert not report['after']['audio']['contexts'] and not report['after']['audio']['decodedBuffers']
        assert not report['after']['fullscreen'] and not report['after']['pointerLocked']
        assert report['after']['gpuDisposed']
        assert 'Controlled SDK worker failure' in report['after']['status']
        assert not any('emscripten_proxy_async failed' in line for line in report['console'])
        assert all(error=='ErrorEvent' or 'Controlled SDK worker failure' in error for error in report['errors'])
        # A fresh module after explicit reload must retain the selected real
        # renderer and close through the original engine path with code zero.
        start_application(page)
        page.wait_for_function('window.application?.applicationState',timeout=180000)
        report['restartedRenderer']=page.evaluate('rendererDiagnostics')
        assert report['restartedRenderer']['backend']=='webgpu'
        page.locator('#close').click()
        page.wait_for_function('applicationResult!==null',timeout=60000)
        report['restartExitCode']=page.evaluate('applicationResult.code')
        report['restartShutdown']=observe_shutdown(page,browser)
        assert report['restartExitCode']==0
        assert not report['restartShutdown']['workers'] and not report['restartShutdown']['liveApplicationTargets']
        assert all(error=='ErrorEvent' or 'Controlled SDK worker failure' in error for error in report['errors'])
        report['passed']=True
    except Exception as error:
        import traceback
        report.update(failure=str(error),traceback=traceback.format_exc())
    finally:
        try:
            if page.evaluate('window.application && applicationResult===null'):
                page.evaluate('application.ccall("Phase4RequestClose",null,[],[])')
                page.wait_for_function('applicationResult!==null',timeout=60000)
            report['finalShutdown']=observe_shutdown(page,browser)
        except Exception as error:report.update(passed=False,teardownFailure=str(error))
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure','restartExitCode']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
