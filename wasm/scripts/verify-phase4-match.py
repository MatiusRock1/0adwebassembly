from phase4_browser import APPLICATION_URL, CDP_URL, EVIDENCE_ROOT, start_application, assert_renderer_clean
"""Exercise original menu/settings/loading/session; never substitute simulation."""
import argparse
import json
import os
from pathlib import Path
import time

os.environ['SCENE_REAL_WINDOW'] = '1'
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import observe_shutdown, enter_fullscreen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default=APPLICATION_URL)
parser.add_argument('--evidence', type=Path, default=(Path(EVIDENCE_ROOT)/'match-startup'))
parser.add_argument('--cdp', help='Attach to the visible dedicated Edge window; leave it open.')
parser.add_argument('--cycles', type=int, default=3)
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)
report = dict(passed=False, phase4Accepted=False, console=[], errors=[], steps=[])
with BenchmarkLock(), sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(args.cdp) if args.cdp else p.chromium.launch(
        channel='msedge', headless=False, args=['--force-high-performance-gpu'])
    page = browser.contexts[0].new_page() if args.cdp else browser.new_page(no_viewport=True)
    page.bring_to_front()
    report['browserVersion']=browser.version
    page.on('console', lambda message: report['console'].append(message.text))
    page.on('pageerror', lambda error: report['errors'].append(str(error)))

    def gui(code):
        return page.evaluate('(code) => window.evaluateOriginalGUI(code)', code)

    def wait_gui(code, seconds=60):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = gui(code)
            if result == 'true':
                return
            page.wait_for_timeout(250)
        raise TimeoutError('Original GUI condition: ' + code)

    def step(name, code):
        result = gui(code)
        report['steps'].append(dict(name=name, result=result))
        (args.evidence / 'progress.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(name, result[:500], flush=True)
        return result

    def play_match(cycle):
        prefix = f'match-{cycle}'
        step(prefix + '-single-player', 'Engine.GetGUIObjectByName("mainMenuButtons").children[2].onPress(); "ok"')
        step(prefix + '-matches', 'Engine.GetGUIObjectByName("submenuButtons").children[0].onPress(); "ok"')
        wait_gui('String(typeof g_GameSettings !== "undefined" && !!g_GameSettings && !!g_SetupWindow)')
        settings = dict(mapType='random', map='maps/random/mainland', settings=dict(
            Size=128, Biome='generic/temperate', PlayerPlacement='circle', Seed=12345,
            AISeed=54321, PopulationCap=200, StartingResources=300,
            VictoryConditions=['conquest'], PlayerData=[dict(Civ='athen'),
            dict(Civ='mace', AI='petra', AIDiff=3, AIBehavior='balanced')]))
        code = 'g_SetupWindow.controls.gameSettingsController.parseSettings(' + json.dumps(settings) + ',false); JSON.stringify(g_GameSettings.toInitAttributes())'
        match = dict(attributes=json.loads(step(prefix + '-settings', code)))
        page.screenshot(path=str(args.evidence / (prefix + '-gamesetup.png')))
        step(prefix + '-launch', 'g_SetupWindow.controls.gameSettingsController.launchGame(); "ok"')
        page.wait_for_function('window.applicationResult || (window.application.applicationState.gameStarted && window.application.applicationState.tick > 10)', timeout=300000)
        assert page.evaluate('window.applicationResult === null'), page.evaluate('window.applicationResult')
        wait_gui('String(typeof g_Selection !== "undefined")', seconds=120)
        match['simulation'] = json.loads(step(prefix + '-simulation', 'JSON.stringify(Engine.GuiInterfaceCall("GetSimulationState"))'))
        page.screenshot(path=str(args.evidence / (prefix + '-session.png')), timeout=60000)
        page.wait_for_timeout(3000)
        step(prefix + '-pause', 'Engine.SetPaused(true,false); String(Engine.IsPaused())')
        before = page.evaluate('window.application.applicationState.tick')
        page.wait_for_timeout(2000)
        assert page.evaluate('window.application.applicationState.tick') == before
        step(prefix + '-resume', 'Engine.SetPaused(false,false); String(Engine.IsPaused())')
        page.wait_for_function('(tick) => window.application.applicationState.tick > tick', arg=before)
        step(prefix + '-resign', 'Engine.PostNetworkCommand({type:"resign"}); "queued"')
        wait_gui('String(!!Engine.TryGetGUIObjectByName("mbTitleBar"))')
        match['defeatTitle'] = step(prefix + '-defeat', 'String(Engine.GetGUIObjectByName("mbTitleBar").caption)')
        assert 'DEFEATED' in match['defeatTitle'], match['defeatTitle']
        page.screenshot(path=str(args.evidence / (prefix + '-defeat.png')))
        page.wait_for_timeout(1000)
        step(prefix + '-summary', 'Engine.GetGUIObjectByName("mbButton2").onPress(); "ok"')
        wait_gui('String(!!Engine.TryGetGUIObjectByName("continueButton"))')
        page.screenshot(path=str(args.evidence / (prefix + '-summary.png')))
        step(prefix + '-return', 'Engine.GetGUIObjectByName("continueButton").onPress(); "ok"')
        wait_gui('String(!!Engine.TryGetGUIObjectByName("mainMenuButtons"))')
        match['workersAtMenu'] = page.evaluate('window.application.getApplicationWorkerState()')
        return match

    try:
        start_application(page,args.url)
        page.wait_for_function('window.application?.applicationState || window.applicationResult', timeout=600000)
        assert page.evaluate('window.applicationResult === null')
        step('dismiss-welcome', '(()=>{const button=Engine.TryGetGUIObjectByName("btnOK");if(button)button.onPress();return "ok";})()')
        wait_gui('String(!!Engine.TryGetGUIObjectByName("mainMenuButtons"))')
        report['matches'] = []
        page.evaluate('window.application.resumeOriginalAudio()')
        report['fullscreen']=enter_fullscreen(page,browser)
        for cycle in range(1, args.cycles + 1):
            report['matches'].append(play_match(cycle))
        page.evaluate('document.exitFullscreen()')
        page.wait_for_function('document.fullscreenElement === null')
        page.screenshot(path=str(args.evidence / 'returned-menu.png'))
        report['renderFrames'] = page.evaluate('window.application.applicationFrames')
        page.locator('#close').click()
        page.wait_for_function('window.applicationResult !== null', timeout=60000)
        page.wait_for_timeout(1000)
        report['exit'] = page.evaluate('window.applicationResult')
        report['audioAfterClose'] = page.evaluate('window.application.getOriginalAudioState()')
        report['shutdown'] = observe_shutdown(page, browser)
        report['workersAfterClose'] = len(report['shutdown']['workers'])
        assert report['exit'] == {'code': 0}, report['exit']
        assert report['workersAfterClose'] == 0, report['workersAfterClose']
        assert not report['shutdown']['liveApplicationTargets'], report['shutdown']
        assert report['audioAfterClose']['contexts'] == [], report['audioAfterClose']
        report['engineErrors'] = [line for line in report['console'] if 'ERROR:' in line]
        assert not report['errors'], report['errors']
        assert not report['engineErrors'], report['engineErrors']
        assert_renderer_clean(page)
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error)
        try:
            report['stateAtFailure'] = page.evaluate('({result:window.applicationResult,state:window.application?.applicationState})')
            page.screenshot(path=str(args.evidence / 'failure.png'), timeout=30000)
        except Exception:
            pass
    finally:
        (args.evidence / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if not args.cdp:
            browser.close()
print(json.dumps({key: report.get(key) for key in ['passed', 'failure', 'exit', 'workersAfterClose', 'engineErrors']}, indent=2))
raise SystemExit(0 if report['passed'] else 1)
