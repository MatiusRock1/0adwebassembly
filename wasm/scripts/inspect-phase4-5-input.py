"""Record browser keyboard events alongside the original engine hotkey state."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from phase4_browser import start_application
from phase4_flow import open_original_match,parity_settings

report={}
with sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://localhost:9227')
    page=browser.contexts[0].new_page();page.bring_to_front()
    page.add_init_script('''window.inputEvents=[];for(const type of ['keydown','keyup'])
      window.addEventListener(type,e=>inputEvents.push({type:e.type,key:e.key,code:e.code,
        keyCode:e.keyCode,shift:e.shiftKey,target:e.target.id,trusted:e.isTrusted}),true);''')
    gui=lambda code:page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    try:
        start_application(page,'http://localhost:8095/application.html?automation=1')
        page.wait_for_function('window.application?.applicationState?.frame>2',timeout=180000)
        report['attributes']=open_original_match(gui,parity_settings())
        report['pauseMap']=gui('JSON.stringify(Engine.GetHotkeyMap().pause)')
        report['steps']=[]
        for key in ['Shift','Space','Space','Shift','Pause','Pause']:
            action='down' if key in ['Shift','Space','Pause'] and not any(x['key']==key and x['action']=='down' for x in report['steps']) else 'up'
            getattr(page.keyboard,action)(key);page.wait_for_timeout(500)
            report['steps'].append(dict(key=key,action=action,state=gui('JSON.stringify({paused:Engine.IsPaused(),pauseHotkey:Engine.HotkeyIsPressed("pause"),selection:g_Selection.toList()})')))
        report['dom']=page.evaluate('window.inputEvents')
    finally:
        Path('docs/wasm/evidence/phase4-5/input-events.json').write_text(json.dumps(report,indent=2))
        if page.evaluate('window.application?.applicationState && !window.applicationResult'):
            page.locator('#close').click();page.wait_for_function('window.applicationResult',timeout=60000)
print(json.dumps(report,indent=2))
