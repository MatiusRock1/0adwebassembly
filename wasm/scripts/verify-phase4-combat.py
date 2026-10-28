from phase4_browser import APPLICATION_URL, CDP_URL, EVIDENCE_ROOT, start_application, assert_renderer_clean
"""Original combat scenario, original Petra and victory/defeat GUI."""
import argparse
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match
from phase4_browser import observe_shutdown, enter_fullscreen, new_test_page

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,default=(Path(EVIDENCE_ROOT)/'original-combat-victory'))
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
report=dict(passed=False,phase4Accepted=False,errors=[],console=[])
settings=dict(mapType='scenario',map='maps/scenarios/combat_demo',settings=dict(
    Seed=12345,AISeed=54321,StartingResources=10000,VictoryConditions=['conquest'],
    PlayerData=[dict(Civ='athen',Name='Phase4Human',Team=-1,AI=''),dict(Civ='athen',Name='Phase4Petra',Team=-1,AI='petra',AIDiff=3,AIBehavior='balanced')]))
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL)
    report['browserVersion']=browser.version
    page=new_test_page(browser);page.bring_to_front()
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.on('console',lambda message:report['console'].append(message.text))
    def gui(code):
        assert_renderer_clean(page)
        return page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    try:
        start_application(page)
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult === null')
        page.evaluate('window.application.resumeOriginalAudio()')
        report['attributes']=open_original_match(gui,settings)
        report['initial']=json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetSimulationState",{}))'))
        report['order']=json.loads(gui('''(()=>{
          const own=Engine.GuiInterfaceCall("GetPlayerEntities",{}).map(id=>Engine.GuiInterfaceCall("GetEntityState",id));
          const enemies=Engine.PickPlayerEntitiesOnScreen(2).map(id=>Engine.GuiInterfaceCall("GetEntityState",id)).filter(entity=>entity.position);
          if(!enemies.length)throw new Error("Original opposing army not visible");
          const command={type:"attack-walk",entities:own.filter(entity=>entity.unitAI).map(entity=>entity.id),x:enemies[0].position.x,z:enemies[0].position.z,queued:false,allowCapture:false};
          Engine.PostNetworkCommand(command);return JSON.stringify(command);
        })()'''))
        report['fullscreen']=enter_fullscreen(page,browser)
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            state=json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetSimulationState",{}))'))
            report['lastState']=state
            (args.evidence/'progress.json').write_text(json.dumps(report,indent=2))
            if state['players'][1]['state']!='active':
                break
            page.wait_for_timeout(1000)
        assert report['lastState']['players'][1]['state'] in ['won','defeated']
        report['statistics']=json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetExtendedSimulationState",{}))'))
        # The pinned StatisticsTracker uses its "Unit" class counter; the
        # legacy "total" entry remains zero even after actual infantry losses.
        casualties=sum(report['statistics']['players'][player]['sequences']['unitsLost']['Unit'][-1] for player in [1,2])
        assert casualties>0,'Victory/defeat must follow actual original combat casualties'
        report['casualties']=casualties
        page.screenshot(path=str(args.evidence/'original-result.png'))
        report['audio']=page.evaluate('window.application.getOriginalAudioState()')
        report['engineErrors']=[line for line in report['console'] if 'ERROR:' in line]
        assert not report['engineErrors'] and not report['errors']
        assert_renderer_clean(page)
        report['passed']=True
    except Exception as error:
        report['failure']=str(error)
    finally:
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
        try:
            if page.evaluate('document.fullscreenElement !== null'):page.evaluate('document.exitFullscreen()')
            if page.evaluate('window.application?.applicationState && window.applicationResult===null'):
                page.locator('#close').click()
                page.wait_for_function('window.applicationResult !== null',timeout=60000)
                report['shutdown']=observe_shutdown(page,browser)
                assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets'],report['shutdown']
                assert page.evaluate('window.applicationResult.code')==0
        except Exception as error:
            report['teardownFailure']=str(error);report['passed']=False
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure','casualties']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
