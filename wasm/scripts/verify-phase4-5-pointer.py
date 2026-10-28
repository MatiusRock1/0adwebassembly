"""Real Windows mouse input: fullscreen edge scroll across monitor boundaries."""
from phase4_browser import (APPLICATION_URL, CDP_URL, start_application,
    new_test_page, enter_fullscreen, observe_shutdown, assert_renderer_clean, move_original_pointer)
from phase4_flow import open_original_match, parity_settings
from benchmark_lock import BenchmarkLock
from playwright.sync_api import sync_playwright
import argparse
import ctypes
import json
import math
import traceback
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', type=Path, required=True)
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)
report = dict(passed=False, phase45Accepted=False, edges={}, errors=[])
user32 = ctypes.windll.user32

with BenchmarkLock(), sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    page = new_test_page(browser)
    page.on('pageerror', lambda error: report['errors'].append(str(error)))
    gui = lambda code: page.evaluate('(code)=>window.evaluateOriginalGUI(code)', code)
    def position():
        packed = page.evaluate('application.ccall("Phase4MousePosition","number",[],[])')
        return [packed & 65535, (packed >> 16) & 65535]
    def move(dx, dy):
        # Trusted OS relative input, not synthesized DOM events or screenshots.
        user32.mouse_event(1, int(dx), int(dy), 0, 0)
        page.wait_for_timeout(120)
    def centre():
        move_original_pointer(page,960,540)
    try:
        start_application(page)
        page.wait_for_function('window.application?.applicationState', timeout=180000)
        report['attributes'] = open_original_match(gui, parity_settings())
        # Intentionally do not hover the canvas: capture must establish SDL
        # mouse focus even when entered directly from the external button.
        report['fullscreen'] = enter_fullscreen(page, browser)
        page.wait_for_function('document.pointerLockElement===document.getElementById("canvas")', timeout=15000)
        report['browserVersion'] = browser.version
        report['desktop'] = dict(monitors=user32.GetSystemMetrics(80),
            virtualWidth=user32.GetSystemMetrics(78), virtualHeight=user32.GetSystemMetrics(79))
        if gui('String(Engine.IsPaused())') == 'true': page.keyboard.press('Shift+Space')
        for name, dx, dy in [('right',500,0),('bottom',0,500),('left',-500,0),('top',0,-500)]:
            centre()
            for unused in range(20):
                move(dx,dy)
                x,y=position()
                if (x==1919 if name=='right' else y==1079 if name=='bottom' else x==0 if name=='left' else y==0): break
            at_edge = position()
            assert (at_edge[0] == 1919 if name=='right' else at_edge[1] == 1079 if name=='bottom'
                    else at_edge[0] == 0 if name=='left' else at_edge[1] == 0), (name,at_edge)
            before = json.loads(gui('JSON.stringify(Engine.GetCameraPosition())'))
            # Continue pushing well beyond the display into adjacent monitors.
            for unused in range(8): move(dx,dy)
            after = json.loads(gui('JSON.stringify(Engine.GetCameraPosition())'))
            delta = math.sqrt(sum((after[k]-before[k])**2 for k in ['x','y','z']))
            assert delta > 1, (name,before,after)
            assert page.evaluate('document.pointerLockElement===document.getElementById("canvas") && document.hasFocus()')
            report['edges'][name] = dict(position=at_edge,before=before,after=after,cameraDistance=delta)
            print('POINTER_EDGE_PASSED',name,at_edge,delta,flush=True)
        centre()
        page.wait_for_function('!document.querySelector(".original-pointer").hidden && document.querySelector(".original-pointer").naturalWidth>0')
        report['originalCursorVisible'] = True
        # Exercise the page's explicit Escape handler with trusted browser
        # input. OS keyboard injection was not delivered in this environment;
        # retained failed reports must not be relabelled as successful tests
        # of Chromium's privileged native unlock gesture.
        page.evaluate('window.pointerEscapeEvents=[];document.addEventListener("keydown",e=>pointerEscapeEvents.push({key:e.key,code:e.code,trusted:e.isTrusted}),true)')
        page.keyboard.press('Escape')
        page.wait_for_function('document.pointerLockElement===null')
        report['escapeReleasedPointer'] = True
        report['escapeInput'] = 'trusted browser keyboard dispatch (CDP), explicit page handler'
        assert_renderer_clean(page)
        assert not report['errors'], report['errors']
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error)
        report['traceback'] = traceback.format_exc()
        try: report['diagnostic'] = page.evaluate('({locked:document.pointerLockElement?.id,full:document.fullscreenElement?.id,keys:window.pointerEscapeEvents,status:document.querySelector("#status").textContent,cursor:canvas.style.cursor,position:window.application?.ccall("Phase4MousePosition","number",[],[])})')
        except Exception: pass
    finally:
        try:
            page.evaluate('()=>{document.exitPointerLock();if(document.fullscreenElement)return document.exitFullscreen();}')
            if page.evaluate('window.application && window.applicationResult===null'):
                page.locator('#close').click()
                page.wait_for_function('window.applicationResult!==null',timeout=60000)
                report['shutdown'] = observe_shutdown(page,browser)
                assert page.evaluate('window.applicationResult.code') == 0
                assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets']
            assert not report['errors'], report['errors']
        except Exception as error:
            report['passed'] = False
            report['teardownFailure'] = str(error)
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:report.get(k) for k in ['passed','failure','edges']},indent=2))
raise SystemExit(not report['passed'])
