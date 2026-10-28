"""Visible API/ABI probes only. Does not start or accept a game session."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
import shutil
import threading

from playwright.sync_api import sync_playwright


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.mjs': 'text/javascript', '.wasm': 'application/wasm'}

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *args):
        pass


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=root / 'wasm/build/phase4-5')
    parser.add_argument('--evidence', type=Path, default=root / 'docs/wasm/evidence/phase4-5/probes')
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    for name in ['renderer-session.mjs', 'webgpu-engine.mjs', 'webgpu-border.mjs', 'webgpu-upload.mjs', 'webgpu-dispatch.mjs', 'application-pointer.mjs', 'application-failure.mjs', 'webgpu-probe.mjs', 'webgpu-probe.html']:
        shutil.copy2(root / 'wasm/browser' / name, args.build / name)
    for name in ['application.html', 'application.mjs']:
        shutil.copy2(root / 'wasm/browser' / name, args.build / name)
    # Import the real factory to test the guard without starting it or a match.
    shutil.copy2(root / 'wasm/dist/application-phase4/pyrogenesis-application.mjs', args.build / 'pyrogenesis-application.mjs')
    (args.build / 'runner.html').write_text('<!doctype html><meta charset="utf-8"><title>0 A.D. WebGPU ABI probe</title><p>Technical API probe; no game acceptance.</p>')
    report = dict(scope='API_ABI_ONLY', phase45Accepted=False, engineBackendIntegrated=False,
                  physicalPresentationVerified=False, headless=False, results=[])
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(args.build.resolve())))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://localhost:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=False)
            report['browserVersion'] = browser.version
            try:
                page = browser.new_page()
                page.add_init_script('''window.contextRequests = [];
                  const original = HTMLCanvasElement.prototype.getContext;
                  HTMLCanvasElement.prototype.getContext = function(kind, ...args) {
                    window.contextRequests.push(kind);
                    return original.call(this, kind, ...args);
                  };''')
                page.goto(origin + '/application.html')
                page.locator('#renderer-backend').select_option('webgpu')
                page.locator('#start').click()
                page.wait_for_function('window.applicationResult?.error')
                report['launcherGuard'] = page.evaluate('''() => ({
                  result: window.applicationResult, contextRequests: window.contextRequests,
                  factoryStarted: Boolean(window.application),
                  selectionUnlocked: !document.querySelector('#renderer-backend').disabled
                })''')
                page.close()
                page = browser.new_page()
                page.goto(origin + '/webgpu-probe.html')
                page.locator('#probe').click()
                page.wait_for_function("window.webgpuProbeResult.events.some(e => ['empty-submission-completed','failed'].includes(e.type))")
                if page.locator('#dispose').is_enabled():
                    page.locator('#dispose').click()
                    page.wait_for_function("window.webgpuProbeResult.events.some(e => ['disposed','dispose-error'].includes(e.type))")
                report['javascriptProbe'] = page.evaluate('window.webgpuProbeResult')
                page.close()
                compile_report = json.loads((args.build / 'bindings-report.json').read_text())
                for row in compile_report['results']:
                    result = dict(target=row['target'], passed=False, console=[], errors=[])
                    report['results'].append(result)
                    if row['exitCode']:
                        result['errors'].append('Compile/link failed')
                        continue
                    result['artifacts'] = {suffix: hashlib.sha256((args.build / (row['target'] + suffix)).read_bytes()).hexdigest()
                                           for suffix in ['.mjs', '.wasm']}
                    page = browser.new_page()
                    page.on('console', lambda msg, r=result: r['console'].append(msg.text))
                    page.on('pageerror', lambda error, r=result: r['errors'].append(str(error)))
                    page.goto(origin + '/runner.html')
                    result['crossOriginIsolated'] = page.evaluate('crossOriginIsolated')
                    try:
                        page.evaluate('''target => {
                          window.probe = {output: [], errors: [], exit: null};
                          import('./' + target + '.mjs').then(({default: factory}) => factory({
                            print: text => window.probe.output.push(text),
                            printErr: text => window.probe.errors.push(text),
                            onExit: code => { window.probe.exit = code; },
                            onAbort: reason => window.probe.errors.push(String(reason))
                          })).catch(error => window.probe.errors.push(String(error)));
                        }''', row['target'])
                        token = 'WEBGPU_DEVICE_UPLOAD_DRAINED_NOT_ENGINE_INTEGRATED' if '-device-' in row['target'] else 'WEBGPU_INSTANCE_CREATED_NOT_ENGINE_INTEGRATED'
                        page.wait_for_function('(token) => window.probe.output.includes(token) || window.probe.errors.length > 0', arg=token, timeout=30000)
                        result['runtime'] = page.evaluate('window.probe')
                        result['passed'] = token in result['runtime']['output'] and not result['runtime']['errors'] and not result['errors']
                    except Exception as error:
                        result['errors'].append(str(error))
                        result['runtime'] = page.evaluate('window.probe')
                    finally:
                        page.close()
            finally:
                browser.close()
    except Exception as error:
        report['error'] = str(error)
    finally:
        server.shutdown()
        server.server_close()
        report['passed'] = (not report.get('error') and len(report['results']) == 6
                            and all(row['passed'] for row in report['results'])
                            and report.get('launcherGuard', {}).get('contextRequests') == []
                            and report.get('launcherGuard', {}).get('selectionUnlocked') is True
                            and report.get('launcherGuard', {}).get('factoryStarted') is False
                            and any(e['type'] == 'disposed' for e in report.get('javascriptProbe', {}).get('events', [])))
        (args.evidence / 'runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
