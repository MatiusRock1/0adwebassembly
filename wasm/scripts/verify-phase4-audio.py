from phase4_browser import APPLICATION_URL, CDP_URL, EVIDENCE_ROOT, start_application, assert_renderer_clean
"""Visible original audio decoding, gain, mute and config persistence."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import observe_shutdown, enter_fullscreen, new_test_page

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,default=(Path(EVIDENCE_ROOT)/'original-audio-persistence'))
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
report=dict(passed=False,phase4Accepted=False,errors=[],console=[])
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL)
    report['browserVersion']=browser.version
    page=new_test_page(browser);page.bring_to_front()
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.on('console',lambda message:report['console'].append(message.text))
    gui=lambda code:page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    def start():
        start_application(page)
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult === null')
        gui('(()=>{const button=Engine.TryGetGUIObjectByName("btnOK");if(button)button.onPress();return "ok";})()')
        page.evaluate('window.application.resumeOriginalAudio()')
        page.wait_for_function('window.application.getOriginalAudioState().contexts.some(context=>context.state==="running")')
        report.setdefault('fullscreenChecks',[]).append(enter_fullscreen(page,browser))
    def close():
        if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
        page.locator('#close').click()
        page.wait_for_function('window.applicationResult !== null',timeout=60000)
        shutdown=observe_shutdown(page,browser)
        assert not shutdown['workers'] and not shutdown['liveApplicationTargets']
        assert page.evaluate('window.application.getOriginalAudioState().contexts.length')==0
        return shutdown
    try:
        start()
        page.wait_for_function('window.application.getOriginalAudioState().decodedBuffers.some(buffer=>buffer.nonzeroSamples>0) && window.application.getOriginalAudioState().contexts.some(context=>context.playingSources>0)',timeout=60000)
        report['originalAudio']=page.evaluate('window.application.getOriginalAudioState()')
        gui('Engine.SetMasterGain(0.4); Engine.ConfigDB_CreateValue("user","sound.mastergain","0.4"); Engine.ConfigDB_SaveChanges("user"); "saved"')
        page.wait_for_function('Math.abs(window.application.getOriginalAudioState().contexts[0].gain-0.4)<0.0001')
        report['savedConfig']=page.evaluate('localStorage.getItem("0ad-phase4-user-config")')
        assert 'sound.mastergain' in report['savedConfig'] and '0.4' in report['savedConfig']
        gui('Engine.SetMasterGain(0); "muted"')
        assert page.evaluate('window.application.getOriginalAudioState().contexts[0].gain')==0
        report['muteVerified']=True
        gui('Engine.SetMasterGain(0.4); "restored"')
        report['firstShutdown']=close()
        page.reload()
        start()
        report['reloadedGain']=page.evaluate('window.application.getOriginalAudioState().contexts[0].gain')
        assert abs(report['reloadedGain']-0.4)<0.0001,report['reloadedGain']
        report['secondShutdown']=close()
        report['engineErrors']=[line for line in report['console'] if 'ERROR:' in line]
        assert not report['engineErrors'] and not report['errors']
        assert_renderer_clean(page)
        report['passed']=True
    except Exception as error:
        report['failure']=str(error)
    finally:
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure','reloadedGain','muteVerified']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
