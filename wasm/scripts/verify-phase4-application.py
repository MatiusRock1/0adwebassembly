"""Run the real original-GUI application on Edge; startup smoke is not phase acceptance."""
import argparse
import json
import os
from pathlib import Path
import time

os.environ['SCENE_REAL_WINDOW'] = '1'
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://localhost:8090/application.html?automation=1')
parser.add_argument('--evidence', type=Path, default=Path('docs/wasm/evidence/phase4/startup'))
parser.add_argument('--timeout-seconds', type=int, default=600)
parser.add_argument('--cdp', help='Attach to the visible dedicated Edge window; leave it open.')
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)
report = dict(passed=False, phase4Accepted=False, errors=[], console=[],
              physicalPresentationVerified=False, originalGUIExecuted=False)
with BenchmarkLock(), sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(args.cdp) if args.cdp else p.chromium.launch(
        channel='msedge', headless=False, args=['--force-high-performance-gpu'])
    page = browser.contexts[0].new_page() if args.cdp else browser.new_page(no_viewport=True)
    page.bring_to_front()
    page.on('pageerror', lambda error: report['errors'].append(str(error)))
    page.on('console', lambda message: report['console'].append(message.text))
    try:
        response = page.goto(args.url)
        report['headers'] = response.all_headers()
        report['browserVersion'] = browser.version
        page.locator('#start').click()
        page.wait_for_function('window.application?.applicationState || window.applicationResult',
                               timeout=args.timeout_seconds * 1000)
        assert page.evaluate('window.applicationResult === null'), page.evaluate('window.applicationResult')
        report['originalGUIExecuted'] = True
        report['initialState'] = page.evaluate('window.application.applicationState')
        page.screenshot(path=str(args.evidence / 'original-menu.png'), timeout=60000)
        report['guiObjects'] = page.evaluate("window.evaluateOriginalGUI('JSON.stringify({hasEngine:typeof Engine,hasGUI:typeof Engine.GetGUIObjectByName})')")
        page.evaluate('window.application.resumeOriginalAudio()')
        page.wait_for_function('window.application.getOriginalAudioState().contexts.some(context => context.state === "running")', timeout=30000)
        report['audio'] = page.evaluate('window.application.getOriginalAudioState()')
        page.locator('#fullscreen').click()
        page.wait_for_function('document.fullscreenElement !== null')
        page.wait_for_function('document.querySelector("#canvas").width === 1920 && document.querySelector("#canvas").height === 1080', timeout=30000)
        page.wait_for_timeout(2000)
        report['surface'] = page.evaluate('''() => {
          const canvas = document.querySelector('#canvas');
          const gl = canvas.getContext('webgl2');
          const debug = gl.getExtension('WEBGL_debug_renderer_info');
          return {canvasWidth:canvas.width, canvasHeight:canvas.height,
            drawingBufferWidth:gl.drawingBufferWidth,drawingBufferHeight:gl.drawingBufferHeight,
            renderer:debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
            dpr:devicePixelRatio,fullscreen:document.fullscreenElement === canvas};
        }''')
        assert report['surface']['canvasWidth'] == report['surface']['drawingBufferWidth'] == 1920, report['surface']
        assert report['surface']['canvasHeight'] == report['surface']['drawingBufferHeight'] == 1080, report['surface']
        page.screenshot(path=str(args.evidence / 'original-menu-fullscreen.png'), timeout=60000)
        page.evaluate('document.exitFullscreen()')
        page.wait_for_function('document.fullscreenElement === null')
        page.locator('#close').click()
        page.wait_for_function('window.applicationResult !== null', timeout=60000)
        report['exit'] = page.evaluate('window.applicationResult')
        page.wait_for_timeout(1000)
        report['audioAfterClose'] = page.evaluate('window.application.getOriginalAudioState()')
        report['workerCountAfterClose'] = len(page.workers)
        report['workerURLsAfterClose'] = [worker.url for worker in page.workers]
        report['sdkWorkersAfterClose'] = page.evaluate('window.application.getApplicationWorkerState()')
        resource_errors = [line for line in report['console'] if 'ERROR:' in line]
        report['engineErrors'] = resource_errors
        assert not resource_errors, resource_errors
        assert not report['errors'], report['errors']
        assert report['exit'] == {'code': 0}, report['exit']
        assert report['workerCountAfterClose'] == 0, report['workerCountAfterClose']
        assert report['audioAfterClose']['contexts'] == [], report['audioAfterClose']
        assert all(c['state'] == 'closed' and not c['closing'] and not c.get('error')
                   for c in report['audioAfterClose']['closed']), report['audioAfterClose']
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error)
        try:
            report['stateAtFailure'] = page.evaluate('({status:document.querySelector("#status").textContent,result:window.applicationResult,state:window.application?.applicationState,canvas:{width:document.querySelector("#canvas").width,height:document.querySelector("#canvas").height,style:document.querySelector("#canvas").style.cssText}})')
            page.screenshot(path=str(args.evidence / 'failure.png'), timeout=30000)
        except Exception:
            pass
    finally:
        (args.evidence / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if not args.cdp:
            browser.close()
print(json.dumps({key: value for key, value in report.items() if key != 'console'}, indent=2))
raise SystemExit(0 if report['passed'] else 1)
