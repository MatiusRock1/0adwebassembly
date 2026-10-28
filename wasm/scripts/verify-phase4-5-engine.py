"""Exercise technical engine startup; gameplay gates must run separately."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import runpy
import threading
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--timeout',type=int,default=180)
parser.add_argument('--cdp')
parser.add_argument('--url')
parser.add_argument('--hold-seconds',type=int,default=0)
parser.add_argument('--evidence',type=Path,default=root/'docs/wasm/evidence/phase4-5/engine-startup')
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
Handler=runpy.run_path(str(Path(__file__).with_name('verify-phase4-5-probes.py')))['Handler']
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(root/'wasm/dist/application-phase4-5')))
threading.Thread(target=server.serve_forever,daemon=True).start()
report=dict(passed=False,phase45Accepted=False,physicalPresentationVerified=False,console=[],errors=[],requests=[])
try:
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp(args.cdp) if args.cdp else p.chromium.launch(channel='msedge',headless=False)
        report['browserVersion']=browser.version
        page=browser.contexts[0].new_page() if args.cdp else browser.new_page(no_viewport=True)
        page.on('console',lambda message:report['console'].append(message.text))
        page.on('pageerror',lambda error:report['errors'].append(str(error)))
        try:
            page.goto(args.url or f'http://localhost:{server.server_port}/application.html?automation=1')
            page.bring_to_front()
            page.locator('#renderer-backend').select_option('webgpu')
            page.locator('#start').click()
            page.wait_for_function('window.application?.applicationState?.frame > 1 || window.applicationResult',timeout=args.timeout*1000)
            report['result']=page.evaluate('window.applicationResult')
            report['state']=page.evaluate('window.application?.applicationState ?? null')
            report['diagnostics']=page.evaluate('window.rendererDiagnostics ?? null')
            report['stats']=page.evaluate('window.webgpuBackend?.stats ?? null')
            page.screenshot(path=str(args.evidence/'startup.png'))
            if report['state'] and not report['result']:
                if args.hold_seconds:page.wait_for_timeout(args.hold_seconds*1000)
                report['settledState']=page.evaluate('window.application?.applicationState ?? null')
                report['settledStats']=page.evaluate('window.webgpuBackend?.stats ?? null')
                page.locator('#canvas').screenshot(path=str(args.evidence/'canvas.png'))
                page.locator('#close').click()
                page.wait_for_function('window.applicationResult',timeout=30000)
                report['exit']=page.evaluate('window.applicationResult')
                report['passed']=report['exit'].get('code')==0 and not report['errors'] and not any('uncaptured-error' in line for line in report['console'])
        except Exception as error:report['error']=str(error)
        finally:
            for line in report['console']:
                try:
                    event=json.loads(line)
                    if isinstance(event,dict) and event.get('type')=='missing-shader-variant':report['requests'].append(dict(name=event['name'],defines=event['defines']))
                except (ValueError,TypeError):pass
            (args.evidence/'shader-requests.json').write_text(json.dumps(report['requests'],indent=2))
            (args.evidence/'runtime.json').write_text(json.dumps(report,indent=2))
            if not args.cdp:browser.close()
finally:server.shutdown();server.server_close()
print(json.dumps({k:v for k,v in report.items() if k not in ['console','diagnostics']},indent=2))
raise SystemExit(not report['passed'])
