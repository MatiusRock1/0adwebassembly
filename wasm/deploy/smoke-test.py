"""Smoke-test a running web deployment; not a benchmark.

Checks the server's isolation headers, types and Range support, then opens the
game in a separate Chrome profile with WebGL 2, requires cross-origin isolation
and waits until the original GUI answers. Needs the deployment's Playwright
environment (wasm/.venv-phase3).
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from playwright.sync_api import sync_playwright


def fetch(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read(1024)
            return response.status, {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as error:
        return error.code, {key.lower(): value for key, value in error.headers.items()}


def check_server(base):
    checks = {}
    def expect(name, url, status, content_type, headers=None, extra=None):
        code, received = fetch(base + url, headers)
        ok = code == status and received.get('content-type', '').startswith(content_type)
        ok = ok and received.get('cross-origin-opener-policy') == 'same-origin'
        ok = ok and received.get('cross-origin-embedder-policy') == 'require-corp'
        if extra: ok = ok and extra(received)
        checks[name] = dict(passed=ok, status=code, contentType=received.get('content-type'))
    expect('landing', '/', 200, 'text/html')
    expect('launcher', '/play/application.html', 200, 'text/html')
    expect('module', '/play/pyrogenesis-application.mjs', 200, 'text/javascript')
    expect('wasm', '/play/pyrogenesis-application.wasm', 200, 'application/wasm', {'Accept-Encoding': 'gzip'})
    expect('archiveRange', '/play/public.zip', 206, 'application/zip', {'Range': 'bytes=0-1023'},
           lambda h: h.get('content-range', '').startswith('bytes 0-1023/'))
    expect('licenses', '/licenses/LICENSE.md', 200, 'text/plain')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://localhost:8080', help='Deployment origin.')
    parser.add_argument('--chrome', type=Path,
        default=Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe')
    parser.add_argument('--port', type=int, default=9333, help='Chrome remote debugging port.')
    parser.add_argument('--timeout', type=int, default=300, help='Seconds to reach the original GUI.')
    args = parser.parse_args()
    report = dict(base=args.base, server=check_server(args.base))
    print(json.dumps(report['server'], indent=2), flush=True)
    profile = Path(tempfile.mkdtemp(prefix='0ad-deploy-smoke-'))
    chrome = subprocess.Popen([str(args.chrome), f'--user-data-dir={profile}', f'--remote-debugging-port={args.port}',
        '--remote-debugging-address=127.0.0.1', '--no-first-run', '--no-default-browser-check',
        '--force-high-performance-gpu', '--new-window', 'about:blank'])
    try:
        for _ in range(100):
            try:
                fetch(f'http://127.0.0.1:{args.port}/json/version'); break
            except OSError:
                time.sleep(0.2)
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{args.port}')
            page = browser.contexts[0].new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script("localStorage.setItem('0ad-renderer-backend', 'webgpu')")
            page.goto(args.base + '/play/application.html?renderer=webgpu&automation=1')
            report['crossOriginIsolated'] = page.evaluate('crossOriginIsolated')
            report['renderer'] = page.locator('#renderer-backend').input_value()
            assert page.locator('#renderer-backend option').count() == 1
            assert page.locator('#renderer-backend').is_disabled()
            started = time.monotonic()
            page.locator('#start').click()
            report['gui'] = None
            while time.monotonic() - started < args.timeout:
                if page.evaluate('Boolean(window.applicationResult)'):
                    report['applicationResult'] = page.evaluate('window.applicationResult'); break
                try:
                    report['gui'] = page.evaluate('code=>window.evaluateOriginalGUI(code)', 'String(typeof Engine)')
                    break
                except Exception:
                    page.wait_for_timeout(1000)
            report['secondsToGUI'] = round(time.monotonic() - started, 1)
            report['pageErrors'] = errors
            if report['gui'] == 'object':
                page.locator('#close').click()
                page.wait_for_function('Boolean(window.applicationResult)', timeout=60000)
                report['applicationResult'] = page.evaluate('window.applicationResult')
            browser.close()
    finally:
        chrome.terminate()
        try: chrome.wait(timeout=20)
        except subprocess.TimeoutExpired: chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)
    report['passed'] = (all(check['passed'] for check in report['server'].values()) and report['crossOriginIsolated']
        and report['renderer'] == 'webgl' and report['gui'] == 'object' and not report['pageErrors'])
    print(json.dumps({key: report[key] for key in report if key != 'server'}, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
