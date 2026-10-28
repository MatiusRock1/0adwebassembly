"""Run the real browser fixture without automating the Windows desktop."""
import argparse
import json
import threading
from functools import partial
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from importlib.util import spec_from_file_location, module_from_spec

parser = argparse.ArgumentParser()
parser.add_argument('--browser', choices=['chromium', 'firefox'], default='chromium')
parser.add_argument('--directory', default='/browser')
parser.add_argument('--evidence', default='/evidence')
args = parser.parse_args()
spec = spec_from_file_location('isolated_server', '/opt/serve-phase2.py')
server_module = module_from_spec(spec)
spec.loader.exec_module(server_module)
server = ThreadingHTTPServer(('127.0.0.1', 8080), partial(server_module.IsolatedHandler, directory=args.directory))
threading.Thread(target=server.serve_forever, daemon=True).start()
out = Path(args.evidence)
out.mkdir(parents=True, exist_ok=True)
report = {'browser': args.browser, 'console': [], 'errors': [], 'workerEvents': [], 'cycleMetrics': []}
try:
    with sync_playwright() as p:
        browser = getattr(p, args.browser).launch(headless=True)
        report['version'] = browser.version
        page = browser.new_page()
        page.on('console', lambda msg: report['console'].append({'type': msg.type, 'text': msg.text}))
        page.on('pageerror', lambda error: report['errors'].append(str(error)))
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
        response = page.goto('http://localhost:8080/map.html')
        report['headers'] = response.all_headers()
        report['isolated'] = page.evaluate('crossOriginIsolated')
        page.wait_for_function("window.mapResult !== null", timeout=180000)
        report['mapResult'] = page.evaluate('window.mapResult')
        report['heartbeat'] = page.evaluate('window.__heartbeat')
        page.screenshot(path=str(out / (args.browser + '-map.png')), full_page=True)
        (out / (args.browser + '-map-report.json')).write_text(json.dumps(report, indent=2))
        if not report['mapResult']['passed']:
            raise RuntimeError('Map parity failed: ' + str(report['mapResult'].get('reason')))
        print('BROWSER_MAP_PARITY_PASSED', args.browser, flush=True)
        # CDP inventory confirms that detached documents have no live dedicated workers.
        if args.browser == 'chromium':
            cdp = browser.new_browser_cdp_session()
            targets = cdp.send('Target.getTargets')['targetInfos']
            report['remainingWorkerTargets'] = [t for t in targets if t['type'] == 'worker']
            if report['remainingWorkerTargets']:
                raise RuntimeError('Workers remained after ten cycles')
        report['workersClosedBeforeBrowserExit'] = sum(e['event'] == 'closed' for e in report['workerEvents'])
        (out / (args.browser + '-map-report.json')).write_text(json.dumps(report, indent=2))
        browser.close()
finally:
    server.shutdown()
    (out / (args.browser + '-map-report.json')).write_text(json.dumps(report, indent=2))
