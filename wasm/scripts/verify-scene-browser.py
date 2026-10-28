"""Run the real browser fixture without automating the Windows desktop."""
import argparse
import json
import threading
import time
from functools import partial
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from importlib.util import spec_from_file_location, module_from_spec

parser = argparse.ArgumentParser()
parser.add_argument('--browser', choices=['chromium', 'firefox'], default='chromium')
parser.add_argument('--directory', default='/browser')
parser.add_argument('--evidence', default='/evidence')
parser.add_argument('--focus-only', action='store_true')
parser.add_argument('--headed', action='store_true', help='Use a real/virtual display for browser focus transitions')
parser.add_argument('--gpu-timer', action='store_true', help='Enable optional GPU queries in the phase3 application')
parser.add_argument('--duration-seconds', type=int, default=0, help='Sustained session after interaction checks; 900 for phase acceptance')
args = parser.parse_args()
spec = spec_from_file_location('isolated_server', '/opt/serve-phase2.py')
server_module = module_from_spec(spec)
spec.loader.exec_module(server_module)
server = ThreadingHTTPServer(('127.0.0.1', 8080), partial(server_module.IsolatedHandler, directory=args.directory))
threading.Thread(target=server.serve_forever, daemon=True).start()
out = Path(args.evidence)
out.mkdir(parents=True, exist_ok=True)
report = {'browser': args.browser, 'console': [], 'errors': [], 'workerEvents': [], 'cycleMetrics': []}
last_live_save = 0.0
def save_live():
    global last_live_save
    now = time.monotonic()
    if now - last_live_save < 0.5:
        return
    last_live_save = now
    path = out / (args.browser + '-scene-live.json')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2))
    try:
        temp.replace(path)
    except PermissionError:
        # Windows may hold the previous report open while inspecting it.
        # Keep the last complete report and retry on the next update.
        pass

try:
    with sync_playwright() as p:
        browser = getattr(p, args.browser).launch(headless=not args.headed, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] if args.browser == 'chromium' else [])
        report['version'] = browser.version
        browser_context = browser.new_context()
        page = browser_context.new_page()
        def record_console(msg):
            report['console'].append({'type': msg.type, 'text': msg.text})
            save_live()
        page.on('console', record_console)
        def record_error(error):
            report['errors'].append(str(error))
            save_live()
        page.on('pageerror', record_error)
        def worker_created(worker):
            report['workerEvents'].append({'event': 'created', 'url': worker.url})
            worker.on('close', lambda: report['workerEvents'].append({'event': 'closed', 'url': worker.url}))
        page.on('worker', worker_created)
        page.expose_function('recordCycleMetrics', lambda data: report['cycleMetrics'].append(data))
        page.add_init_script("""
          if (window === window.top) {
            window.__heartbeat = 0;
            setInterval(() => { window.__heartbeat++; }, 10);
            window.addEventListener('message', event => {
              if (event.data?.type !== 'fixture-result') return;
              queueMicrotask(() => window.recordCycleMetrics({heartbeat: window.__heartbeat,
                jsHeapUsedBytes: performance.memory?.usedJSHeapSize ?? null}));
            });
          }
        """)
        response = page.goto('http://localhost:8080/scene.html' + ('?gpuTimer=1' if args.gpu_timer else ''))
        report['headers'] = response.all_headers()
        report['isolated'] = page.evaluate('crossOriginIsolated')
        try:
            page.wait_for_function("window.sceneState?.ready || window.sceneResult", timeout=180000)
            if page.evaluate('Boolean(window.sceneResult && !window.sceneResult.passed)'):
                raise RuntimeError(str(page.evaluate('window.sceneResult')))
            canvas_image = out / (args.browser + '-scene-canvas.png')
            page.locator('#canvas').screenshot(path=str(canvas_image))
            from PIL import Image, ImageStat
            pixels = Image.open(canvas_image).convert('RGB')
            report['imageMetrics'] = {'size': list(pixels.size), 'channelStdDev': ImageStat.Stat(pixels).stddev,
                'quantizedColors': len(pixels.resize((160,120)).quantize(colors=128).getcolors())}
            assert max(report['imageMetrics']['channelStdDev']) > 10 and report['imageMetrics']['quantizedColors'] > 32

            report['readyState'] = page.evaluate('window.sceneState')
            if args.focus_only:
                page.locator('#canvas').click(position={'x': 5, 'y': 5})
                focus_page = page.context.new_page()
                focus_page.goto('about:blank')
                focus_page.bring_to_front()
                page.wait_for_function('window.sceneState.metrics?.paused', timeout=30000)
                report['focusLostState'] = page.evaluate('window.sceneState')
                focus_page.close()
                page.bring_to_front()
                page.locator('#canvas').click(position={'x': 5, 'y': 5})
                page.keyboard.press('Space')
                page.wait_for_function('window.sceneState.metrics && !window.sceneState.metrics.paused', timeout=30000)
                report['focusRestoredState'] = page.evaluate('window.sceneState')
            else:
                metrics = report['readyState']['metrics']
                assert metrics['terrainTriangles'] > 0 and metrics['modelTriangles'] > 0
                box = page.locator('#canvas').bounding_box()
                page.mouse.click(box['x'] + metrics['screenX'], box['y'] + metrics['screenY'])
                page.wait_for_function("window.sceneState.metrics?.selected === 8", timeout=20000)
                page.mouse.click(box['x'] + metrics['screenX'] + 70, box['y'] + metrics['screenY'], button='right')
                page.wait_for_function("Math.abs(window.sceneState.metrics.x - %s) > 1 || Math.abs(window.sceneState.metrics.z - %s) > 1" % (metrics['x'],metrics['z']), timeout=60000)
                report['movementState'] = page.evaluate('window.sceneState')
                page.keyboard.press('Space')
                page.wait_for_function("window.sceneState.metrics?.paused", timeout=20000)
                report['pausedState'] = page.evaluate('window.sceneState')
                paused_tick = report['pausedState']['metrics']['tick']
                page.keyboard.press('n')
                page.wait_for_function('window.sceneState.metrics.tick === %d' % (paused_tick + 1), timeout=30000)
                report['singleStepState'] = page.evaluate('window.sceneState')
                page.keyboard.press('ArrowRight')
                previous_screen_x = report['singleStepState']['metrics']['screenX']
                page.wait_for_function('Math.abs(window.sceneState.metrics.screenX - %s) > 1' % previous_screen_x, timeout=30000)
                report['cameraState'] = page.evaluate('window.sceneState')
                page.locator('#resolution').select_option('800,600')
                page.wait_for_function('window.sceneState.metrics.width === 800 && window.sceneState.metrics.height === 600', timeout=30000)
                report['resizeState'] = page.evaluate('window.sceneState')
                page.locator('#resolution').select_option('640,480')
                page.locator('#canvas').click(position={'x': 5, 'y': 5})
    
                for restart in range(1,4):
                    page.keyboard.press('r')
                    page.wait_for_function("window.sceneState.metrics?.restarts === %d" % restart, timeout=60000)
                report['restartState'] = page.evaluate('window.sceneState')
                if args.duration_seconds:
                    page.keyboard.press('Space')
                    report['sustainedSamples'] = []
                    deadline = time.monotonic() + args.duration_seconds
                    while time.monotonic() < deadline:
                        page.wait_for_timeout(min(15000, max(1, (deadline-time.monotonic())*1000)))
                        sample = page.evaluate('({state: window.sceneState.metrics, result: window.sceneResult, heartbeat: window.__heartbeat})')
                        memory_file = Path('/sys/fs/cgroup/memory.current')
                        sample['containerMemoryBytes'] = int(memory_file.read_text()) if memory_file.exists() else None
                        rss = 0
                        for process_status in Path('/proc').glob('[0-9]*/status'):
                            try:
                                rss += sum(int(line.split()[1])*1024 for line in process_status.read_text().splitlines() if line.startswith('VmRSS:'))
                            except FileNotFoundError:
                                pass
                        sample['processRSSBytes'] = rss
                        sample['sampleTime'] = time.monotonic()
                        report['sustainedSamples'].append(sample)
                        if sample['result']:
                            raise RuntimeError('Scene exited during sustained verification')
                        save_live()
                    report['sustainedSeconds'] = args.duration_seconds
                    assert report['sustainedSamples'][-1]['state']['tick'] > report['sustainedSamples'][0]['state']['tick']
            report['profileFrames'] = page.evaluate('window.sceneFrames?.slice(-600) ?? []')
            page.locator('[data-key="Escape"]').click()
            page.wait_for_function("window.sceneResult !== null", timeout=30000)
        except Exception:
            try:
                report['lastLog'] = page.locator('#log').inner_text(timeout=3000)
                report['lastState'] = page.evaluate('window.sceneState')
                page.screenshot(path=str(out / (args.browser + '-scene-failed.png')), full_page=True)
            except Exception as error:
                report['diagnosticError'] = str(error)
            raise
        report['sceneResult'] = page.evaluate('window.sceneResult')
        report['heartbeat'] = page.evaluate('window.__heartbeat')
        page.screenshot(path=str(out / (args.browser + '-scene.png')), full_page=True)
        (out / (args.browser + '-scene-report.json')).write_text(json.dumps(report, indent=2))
        if not report['sceneResult']['passed']:
            raise RuntimeError('Scene renderer initialization failed: ' + str(report['sceneResult'].get('reason')))
        # CDP inventory confirms that detached documents have no live dedicated workers.
        if args.browser == 'chromium':
            cdp = browser.new_browser_cdp_session()
            deadline = time.monotonic() + 10
            while True:
                targets = cdp.send('Target.getTargets')['targetInfos']
                if not any(t['type'] == 'worker' for t in targets) or time.monotonic() > deadline:
                    break
                page.wait_for_timeout(100)
            report['remainingWorkerTargets'] = [t for t in targets if t['type'] == 'worker']
            if report['remainingWorkerTargets']:
                raise RuntimeError('Workers remained after scene exit')
        report['workersClosedBeforeBrowserExit'] = sum(e['event'] == 'closed' for e in report['workerEvents'])
        (out / (args.browser + '-scene-report.json')).write_text(json.dumps(report, indent=2))
        browser.close()
        report['passed'] = True
        print('BROWSER_SCENE_MAP_PASSED', args.browser, flush=True)
except Exception as error:
    report['passed'] = False
    report['failure'] = str(error)
    raise
finally:
    server.shutdown()
    (out / (args.browser + '-scene-report.json')).write_text(json.dumps(report, indent=2))
