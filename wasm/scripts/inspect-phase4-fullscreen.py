"""Keep the application visible after clicking its own fullscreen button."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock

out=Path('docs/wasm/evidence/phase4/fullscreen-button');out.mkdir(parents=True,exist_ok=True)
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://127.0.0.1:9226')
    page=browser.contexts[0].pages[0];page.bring_to_front()
    page.goto('http://localhost:8091/application.html?automation=1')
    page.locator('#start').click()
    page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
    page.evaluate('window.application.resumeOriginalAudio()')
    page.locator('#fullscreen').click()
    session=browser.new_browser_cdp_session()
    target=page.context.new_cdp_session(page).send('Target.getTargetInfo')['targetInfo']['targetId']
    samples=[]
    for delay in [0,1000,3000,5000]:
        page.wait_for_timeout(delay)
        sample=dict(window=session.send('Browser.getWindowForTarget',dict(targetId=target)),
            dom=page.evaluate('({inner:[innerWidth,innerHeight],screen:[screen.width,screen.height],dpr:devicePixelRatio,fullscreen:!!document.fullscreenElement,canvas:[canvas.width,canvas.height],focus:document.hasFocus()})'))
        samples.append(sample);print(json.dumps(sample),flush=True)
    page.screenshot(path=str(out/'fullscreen-button.png'))
    (out/'report.json').write_text(json.dumps(dict(samples=samples),indent=2))
