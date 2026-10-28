"""Load an original match on the operator's visible WebGPU test browser.

Technical integration check; this alone accepts no gameplay/performance gate.
"""
import argparse
import json
from pathlib import Path
import os
import time
os.environ['SCENE_REAL_WINDOW']='1'
from playwright.sync_api import sync_playwright
from phase4_flow import open_original_match,parity_settings

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--hold-seconds',type=int,default=10)
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
report=dict(passed=False,phase45Accepted=False,console=[],errors=[],requests=[],gpuErrors=[])
with sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://localhost:9227')
    context=browser.contexts[0];previous=list(context.pages);page=context.new_page()
    for old in previous:
        if old.url.startswith('http://localhost:8095/application.html'):old.close()
    page.bring_to_front()
    def console(message):
        text=message.text
        try:
            event=json.loads(text)
            if isinstance(event,dict) and event.get('type')=='uncaptured-error':
                if event['message'] not in report['gpuErrors']:report['gpuErrors'].append(event['message'])
                if sum('uncaptured-error' in line for line in report['console'])>=30:return
        except (ValueError,TypeError):pass
        if len(report['console'])<3000:report['console'].append(text)
    page.on('console',console)
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    def save():
        report['requests']=[]
        for line in report['console']:
            try:
                event=json.loads(line)
                if isinstance(event,dict) and event.get('type')=='missing-shader-variant':report['requests'].append(dict(name=event['name'],defines=event['defines']))
            except (ValueError,TypeError):pass
        (args.evidence/'shader-requests.json').write_text(json.dumps(report['requests'],indent=2))
        (args.evidence/'runtime.json').write_text(json.dumps(report,indent=2))
    def gui(code):
        if report['gpuErrors']:raise RuntimeError(report['gpuErrors'][0])
        if page.evaluate('Boolean(window.applicationResult)'):raise RuntimeError(str(page.evaluate('window.applicationResult')))
        return page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    try:
        page.goto('http://localhost:8095/application.html?automation=1')
        page.locator('#renderer-backend').select_option('webgpu');page.locator('#start').click()
        page.wait_for_function('window.application?.applicationState?.frame>2 || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult===null'),page.evaluate('window.applicationResult')
        report['adapter']=page.evaluate('window.rendererDiagnostics')
        print('LOADING_ORIGINAL_MATCH',flush=True)
        report['attributes']=open_original_match(gui,parity_settings())
        page.wait_for_function('window.applicationResult || (window.application.applicationState.gameStarted && window.application.applicationState.tick>10)',timeout=300000)
        assert page.evaluate('window.applicationResult===null'),page.evaluate('window.applicationResult')
        page.wait_for_timeout(args.hold_seconds*1000)
        report['state']=page.evaluate('window.application.applicationState')
        report['stats']=page.evaluate('window.webgpuBackend.stats')
        report['simulation']=json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetSimulationState",{}))'))
        page.locator('#canvas').screenshot(path=str(args.evidence/'original-match.png'),timeout=60000)
        report['passed']=not report['errors'] and not any('uncaptured-error' in line for line in report['console'])
        print('ORIGINAL_WEBGPU_MATCH_LOADED',flush=True)
    except Exception as error:
        report['error']=str(error)
        try:report['state']=page.evaluate('window.application?.applicationState ?? null')
        except Exception:pass
    finally:save()
print(json.dumps({k:v for k,v in report.items() if k not in ['console','adapter','simulation']},indent=2))
raise SystemExit(not report['passed'])
