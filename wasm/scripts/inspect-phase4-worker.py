"""Capture and immediately resume a diagnostic engine pthread stack."""
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright

output = Path('docs/wasm/evidence/phase4/startup-worker-stack')
output.mkdir(parents=True, exist_ok=True)
messages = []
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9226')
    cdp = browser.new_browser_cdp_session()
    targets = cdp.send('Target.getTargets')['targetInfos']
    worker = next(target for target in targets if target['type'] == 'worker' and target['title'] == 'em-pthread-8')
    cdp.on('Target.receivedMessageFromTarget', lambda event: messages.append(json.loads(event['message'])))
    session = cdp.send('Target.attachToTarget', dict(targetId=worker['targetId'], flatten=False))['sessionId']
    def send(identifier, method):
        cdp.send('Target.sendMessageToTarget', dict(sessionId=session,
            message=json.dumps(dict(id=identifier, method=method))))
    try:
        send(1, 'Debugger.enable')
        send(2, 'Debugger.pause')
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not any(item.get('method') == 'Debugger.paused' for item in messages):
            cdp.send('Browser.getVersion')
            time.sleep(0.05)
        paused = [item for item in messages if item.get('method') == 'Debugger.paused']
        (output / 'messages.json').write_text(json.dumps(messages, indent=2))
        (output / 'paused.json').write_text(json.dumps(paused, indent=2))
        print(json.dumps([[(frame['functionName'], frame['location']) for frame in event['params']['callFrames']]
                          for event in paused], indent=2))
    finally:
        send(3, 'Debugger.resume')
        send(4, 'Debugger.disable')
        cdp.send('Target.detachFromTarget', dict(sessionId=session))
