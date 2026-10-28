"""Browser acceptance on an existing isolated local server; no startup installs."""
import argparse
import os
os.environ["SCENE_REAL_WINDOW"] = "1"
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from scene_surface import assert_surface

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://localhost:8080/scene.html')
parser.add_argument('--channel', choices=['msedge', 'chrome', 'chromium', 'firefox'], default='msedge')
parser.add_argument('--high-performance-gpu', action='store_true')
parser.add_argument('--software', action='store_true', help='Diagnostic only; never hardware acceptance')
parser.add_argument('--duration-seconds', type=int, default=900)
parser.add_argument('--warmup-seconds', type=int, default=120)
parser.add_argument('--evidence', type=Path, default=Path('docs/wasm/evidence/phase3'))
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)
report = {'passed': False, 'errors': [], 'channel': args.channel, 'softwareRequested': args.software,
          'physicalPresentationVerified': False, 'gpuTiming': None, 'gcTiming': None}
with BenchmarkLock(), sync_playwright() as p:
    browser_type = p.firefox if args.channel == 'firefox' else p.chromium
    launch = {'headless': args.software}
    if args.channel in ['chrome', 'msedge']:
        launch['channel'] = args.channel
    if args.software and args.channel != 'firefox':
        launch['args'] = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
    if args.high_performance_gpu and args.channel != 'firefox':
        launch.setdefault('args', []).append('--force-high-performance-gpu')
    browser = browser_type.launch(**launch)
    page = browser.new_page(no_viewport=True)
    page.on('pageerror', lambda error: report['errors'].append(str(error)))
    try:
        response = page.goto(args.url)
        report['headers'] = response.all_headers()
        report['browserVersion'] = browser.version
        page.wait_for_function('window.sceneState?.ready || window.sceneResult', timeout=240000)
        assert page.evaluate('window.sceneState.ready && !window.sceneResult')
        report['hardware'] = page.evaluate('window.sceneHardware')
        for cycle in range(10):
            windowed = page.evaluate('({width: document.querySelector("#canvas").width, height: document.querySelector("#canvas").height})')
            page.locator('#fullscreen').click()
            page.wait_for_function('document.fullscreenElement !== null')
            page.keyboard.press('Escape')
            page.wait_for_function('document.fullscreenElement === null')
            page.wait_for_function('(size) => document.querySelector("#canvas").width === size.width && document.querySelector("#canvas").height === size.height', arg=windowed)
            page.wait_for_function('(size) => window.sceneFrames.at(-1)?.width === size.width && window.sceneFrames.at(-1)?.height === size.height', arg=windowed)
            assert page.evaluate('window.sceneResult === null')
            page.locator('#resolution').select_option('800,600' if cycle % 2 else '640,480')
            expected = 800 if cycle % 2 else 640
            page.wait_for_function('window.sceneState.metrics.width === ' + str(expected), timeout=60000)
            page.wait_for_function('window.sceneFrames.at(-1)?.width === ' + str(expected))
            assert_surface(page, expected, 600 if expected == 800 else 480)
            metrics = page.evaluate('window.sceneState.metrics')
            box = page.locator('#canvas').bounding_box()
            page.mouse.click(box['x'] + metrics['screenX'] * box['width'] / metrics['width'],
                             box['y'] + metrics['screenY'] * box['height'] / metrics['height'])
            page.wait_for_function('window.sceneState.metrics.selected === 8', timeout=60000)
        report['fullscreenResizePickingCycles'] = 10
        for restart in range(1, 4):
            page.locator('[data-key="KeyR"]').click()
            page.wait_for_function('window.sceneState.metrics.restarts === ' + str(restart), timeout=180000)
        report['restarts'] = 3
        other_context = browser.new_context()
        other = other_context.new_page()
        other.goto('about:blank'); other.bring_to_front()
        page.wait_for_function('!document.hasFocus()', timeout=15000)
        page.wait_for_function('window.sceneState.metrics.paused', timeout=60000)
        other_context.close(); page.bring_to_front()
        assert page.evaluate('window.sceneState.metrics.paused')
        report['focusPause'] = True
        page.locator('#resolution').select_option('1920,1080')
        page.wait_for_function('window.sceneState.metrics.width === 1920', timeout=60000)
        if page.evaluate('window.sceneState.metrics.paused'):
            page.locator('[data-key="Space"]').click()
        page.evaluate('window.sceneFrames.length = 0')
        deadline = time.monotonic() + args.warmup_seconds + args.duration_seconds + 2
        report['memorySamples'] = []
        while time.monotonic() < deadline:
            page.wait_for_timeout(15000)
            assert page.evaluate('window.sceneResult === null')
            report['memorySamples'].append(page.evaluate('({jsBytes: performance.memory?.usedJSHeapSize ?? null, wasmBytes: window.sceneFrames.at(-1)?.wasmHeapBytes ?? null, metrics: window.sceneState.metrics})'))
        profile = page.evaluate('({hardware: window.sceneHardware, frames: window.sceneFrames})')
        (args.evidence / (args.channel + '-profile.json')).write_text(json.dumps(profile))
        page.locator('[data-key="Escape"]').click()
        page.wait_for_function('window.sceneResult !== null', timeout=60000)
        assert page.evaluate('window.sceneResult.passed')
        if args.channel != 'firefox':
            cdp = browser.new_browser_cdp_session()
            for _ in range(100):
                workers = [t for t in cdp.send('Target.getTargets')['targetInfos'] if t['type'] == 'worker']
                if not workers:
                    break
                page.wait_for_timeout(100)
            report['remainingWorkerTargets'] = workers
            assert not workers
        else:
            report['remainingWorkerTargets'] = 'Not verified: CDP unavailable'
        page.reload()
        page.wait_for_function('window.sceneState?.ready || window.sceneResult', timeout=240000)
        assert page.evaluate('window.sceneState.ready && !window.sceneResult')
        lost = page.evaluate("""() => {
            const gl = document.querySelector('#canvas').getContext('webgl2');
            const extension = gl?.getExtension('WEBGL_lose_context');
            if (!extension) return false;
            extension.loseContext(); return true;
        }""")
        if lost:
            page.wait_for_function("window.sceneResult?.reason === 'WebGL context lost'", timeout=30000)
            page.locator('#recover').click()
            page.wait_for_function('window.sceneState?.ready || window.sceneResult', timeout=240000)
            assert page.evaluate('window.sceneState.ready && !window.sceneResult')
            page.locator('[data-key="Escape"]').click()
            page.wait_for_function('window.sceneResult !== null', timeout=60000)
            assert page.evaluate('window.sceneResult.passed')
            report['contextRecovery'] = 'Reloaded original map; unsaved state intentionally lost'
        else:
            report['contextRecovery'] = 'BLOCKED: WEBGL_lose_context unavailable'
        # Real malformed loader input in this disposable module; no mock simulation.
        page.reload()
        page.wait_for_function('window.sceneState?.ready || window.sceneResult', timeout=240000)
        assert page.evaluate('window.sceneState.ready && !window.sceneResult')
        page.evaluate("window.sceneModule.FS.writeFile('/scenario/commands.txt', 'start invalid\\n')")
        page.locator('[data-key="KeyR"]').click()
        page.wait_for_function('window.sceneResult !== null', timeout=60000)
        failed_load = page.evaluate('window.sceneResult')
        assert not failed_load['passed'] and failed_load.get('exitCode') == 31
        report['malformedReloadExitCode'] = failed_load['exitCode']
        if args.channel != 'firefox':
            for _ in range(100):
                workers = [t for t in cdp.send('Target.getTargets')['targetInfos'] if t['type'] == 'worker']
                if not workers:
                    break
                page.wait_for_timeout(100)
            report['remainingWorkersAfterReloadError'] = workers
            assert not workers
        report['passed'] = not report['errors']
    except Exception as error:
        report['failure'] = str(error)
        try:
            report['failureState'] = page.evaluate('({state: window.sceneState, fullscreen: Boolean(document.fullscreenElement), focused: document.hasFocus(), activeElement: document.activeElement?.id})')
        except Exception:
            pass
        raise
    finally:
        (args.evidence / (args.channel + '-acceptance.json')).write_text(json.dumps(report, indent=2))
        browser.close()
