"""Read-only snapshots of the dedicated visible local test browser."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

output = Path('docs/wasm/evidence/phase4/live-inspection')
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9226')
    report = []
    for index, page in enumerate(browser.contexts[0].pages):
        if not page.url.startswith('http://localhost:8091'):
            continue
        state = page.evaluate(r'''({state:window.application?.applicationState,
          result:window.applicationResult,status:document.getElementById('status')?.textContent,
          clock:window.application?.applicationClock,hidden:document.hidden,focused:document.hasFocus(),
          log:document.getElementById('log')?.textContent.split('\n').slice(-12)})''')
        if state['result'] is None and state['status'].startswith('Inicializando'):
            state['engineLog'] = page.evaluate(r'''(()=>{try{return window.application.FS.readFile('/logs/mainlog.html',{encoding:'utf8'}).split('\n').slice(-12);}catch(error){return String(error);}})()''')
        report.append(dict(index=index, state=state))
        print(json.dumps(report[-1]), flush=True)
        (output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    (output / 'report.json').write_text(json.dumps(report, indent=2))
