"""Exercise WebGPU surface changes and explicit restart after device loss.

Browser lifecycle freezing is tested separately from OS sleep; it does not
claim to test suspending the physical computer. No desktop captures are used.
"""
import argparse
import json
from pathlib import Path
import traceback
import base64
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import (APPLICATION_URL, CDP_URL, EVIDENCE_ROOT,
    start_application, new_test_page, enter_fullscreen, observe_shutdown,
    assert_renderer_clean)
from phase4_flow import open_original_match, parity_settings
from scene_surface import assert_surface
from phase45_benchmark_contract import fingerprint
from phase45_physical_capture import capture_foreground_canvas

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,default=Path(EVIDENCE_ROOT)/'lifecycle')
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
report=dict(passed=False,phase45Accepted=False,checks={},errors=[],console=[],
    scope='Real OS fullscreen/minimize; browser lifecycle freeze; intentional GPUDevice.destroy. Physical OS sleep is not tested.')
report['buildSHA256']=fingerprint(Path('wasm/dist/application-phase4-5'))
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL)
    report['browserVersion']=browser.version
    page=new_test_page(browser)
    target=None
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.on('console',lambda message:report['console'].append(message.text))
    gui=lambda code:page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    try:
        start_application(page)
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult===null')
        report['attributes']=open_original_match(gui,parity_settings())
        report['savedConfig']=page.evaluate('localStorage.getItem("0ad-phase4-user-config")')
        report['surfaces']=[]
        for _ in range(2):
            enter_fullscreen(page,browser)
            report['surfaces'].append(assert_surface(page,1920,1080))
            page.evaluate('document.exitFullscreen()')
            page.wait_for_timeout(2000)
            report['surfaces'].append(assert_surface(page,1280,720))
        report['checks']['fullscreenResize']=True
        enter_fullscreen(page,browser)
        target=page.context.new_cdp_session(page)
        metrics=page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})')
        report['dprScope']='CDP device-scale-factor emulation while the real OS window remains fullscreen; physical movement between monitors with different DPI is not asserted'
        report['dprSurfaces']=[]
        try:
            for dpr in [1.25,2]:
                before=page.evaluate('application.applicationState.frame')
                target.send('Emulation.setDeviceMetricsOverride',dict(width=metrics['width'],height=metrics['height'],
                    screenWidth=metrics['width'],screenHeight=metrics['height'],deviceScaleFactor=dpr,mobile=False,dontSetVisibleSize=True))
                page.wait_for_function('dpr=>devicePixelRatio===dpr',arg=dpr,timeout=10000)
                page.wait_for_function('frame=>application.applicationState.frame>frame+3',arg=before,timeout=30000)
                surface=assert_surface(page,1920,1080)
                assert surface['fullscreen'] and surface['dpr']==dpr
                report['dprSurfaces'].append(surface)
        finally:
            target.send('Emulation.clearDeviceMetricsOverride')
        page.wait_for_function('dpr=>devicePixelRatio===dpr',arg=metrics['dpr'],timeout=10000)
        report['checks']['emulatedDPR']=True
        target_id=target.send('Target.getTargetInfo')['targetInfo']['targetId']
        session=browser.new_browser_cdp_session()
        window_id=session.send('Browser.getWindowForTarget',dict(targetId=target_id))['windowId']
        page.evaluate('document.exitFullscreen()')
        page.wait_for_timeout(1000)
        session.send('Browser.setWindowBounds',dict(windowId=window_id,bounds=dict(windowState='minimized')))
        page.wait_for_timeout(5000)
        report['minimized']=session.send('Browser.getWindowBounds',dict(windowId=window_id))
        assert report['minimized']['bounds']['windowState']=='minimized'
        session.send('Browser.setWindowBounds',dict(windowId=window_id,bounds=dict(windowState='normal')))
        page.bring_to_front();enter_fullscreen(page,browser)
        report['surfaces'].append(assert_surface(page,1920,1080))
        report['checks']['minimizeRestore']=True
        before=page.evaluate('window.application.applicationState.frame')
        # Freeze a genuinely backgrounded tab. Freezing the selected fullscreen
        # tab leaves Chromium's visibility hidden without a real tab activation
        # transition on resume, an artificial state Page.bringToFront alone
        # cannot repair. Returning to the tab follows normal browser behavior.
        resume_tab=page.context.new_page()
        resume_tab.bring_to_front()
        page.wait_for_function('document.hidden',polling=100,timeout=10000)
        try:
            target.send('Page.setWebLifecycleState',dict(state='frozen'))
            # The page cannot answer while frozen; use host time, not a page timer.
            import time
            time.sleep(5)
        finally:
            target.send('Page.setWebLifecycleState',dict(state='active'))
            page.bring_to_front()
            resume_tab.close()
        page.wait_for_function('!document.hidden && document.hasFocus()',polling=100,timeout=30000)
        enter_fullscreen(page,browser)
        page.wait_for_function('(before)=>window.application.applicationState.frame>before+3',arg=before,polling=100,timeout=30000)
        report['resumeSurface']=assert_surface(page,1920,1080)
        assert report['resumeSurface']['focused'] and not report['resumeSurface']['hidden']
        resumed_image=args.evidence/'resumed-original-game.png'
        png=page.locator('#canvas').screenshot(path=str(resumed_image),timeout=10000)
        report['resumePixelDeviation']=page.evaluate('''async(encoded)=>{
          const bytes=Uint8Array.from(atob(encoded),value=>value.charCodeAt(0));
          const bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}));
          try {
            const canvas=new OffscreenCanvas(bitmap.width,bitmap.height),ctx=canvas.getContext('2d');
            ctx.drawImage(bitmap,0,0);const pixels=ctx.getImageData(0,0,bitmap.width,bitmap.height).data;
            const sum=[0,0,0],square=[0,0,0];let count=0;
            for(let index=0;index<pixels.length;index+=256){count++;for(let channel=0;channel<3;channel++){
              const value=pixels[index+channel];sum[channel]+=value;square[channel]+=value*value;
            }}
            return sum.map((value,index)=>Math.sqrt(Math.max(0,square[index]/count-(value/count)**2)));
          } finally {bitmap.close();}
        }''',base64.b64encode(png).decode('ascii'))
        assert max(report['resumePixelDeviation'])>10,'Resume produced a uniform/blank image'
        owners=[process for process in session.send('SystemInfo.getProcessInfo')['processInfo'] if process['type']=='browser']
        assert len(owners)==1
        bounds=page.evaluate('''()=>{const r=document.getElementById('canvas').getBoundingClientRect();
          return {x:r.x,y:r.y,width:r.width,height:r.height,viewportWidth:innerWidth,viewportHeight:innerHeight};}''')
        report['physicalResumeCapture']=capture_foreground_canvas(int(owners[0]['id']),bounds,args.evidence/'resumed-physical-canvas.png')
        assert max(report['physicalResumeCapture']['deviationRGB'])>10,'The real foreground canvas is uniform/gray after resume'
        assert gui('String(Engine.GetSimRate())')=='1'
        report['checks']['browserFreezeResume']=True
        assert_renderer_clean(page)
        assert not report['errors'] and not any('ERROR:' in line for line in report['console'])
        report['beforeLossConfig']=page.evaluate('localStorage.getItem("0ad-phase4-user-config")')
        page.evaluate('window.webgpuBackend.device.destroy()')
        page.wait_for_function('window.applicationResult!==null',timeout=60000)
        report['lossResult']=page.evaluate('window.applicationResult')
        report['lossStatus']=page.locator('#status').inner_text()
        assert 'reinicia' in report['lossStatus'].lower(),'Device-loss restart instruction did not persist'
        report['lossShutdown']=observe_shutdown(page,browser)
        assert not report['lossShutdown']['workers'] and not report['lossShutdown']['liveApplicationTargets']
        assert page.evaluate('window.webgpuBackend.disposed===true')
        assert page.evaluate('localStorage.getItem("0ad-phase4-user-config")')==report['beforeLossConfig']
        report['checks']['lossCleanupAndPersistence']=True
        if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
        page.reload();start_application(page)
        page.wait_for_function('window.application?.applicationState?.frame>3 || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult===null')
        assert page.evaluate('window.rendererDiagnostics.backend')=='webgpu'
        assert page.evaluate('localStorage.getItem("0ad-phase4-user-config")')==report['beforeLossConfig']
        report['checks']['explicitRestartSameBackend']=True
        page.locator('#close').click();page.wait_for_function('window.applicationResult!==null',timeout=60000)
        report['restartShutdown']=observe_shutdown(page,browser)
        assert not report['restartShutdown']['workers'] and not report['restartShutdown']['liveApplicationTargets']
        report['passed']=True
    except Exception as error:
        report['failure']=str(error);report['traceback']=traceback.format_exc()
    finally:
        try:
            if target:
                target.send('Emulation.clearDeviceMetricsOverride')
                target.send('Page.setWebLifecycleState',dict(state='active'))
                target.send('Page.bringToFront')
            if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
            if page.evaluate('window.application?.applicationState && window.applicationResult===null'):
                page.evaluate('application.ccall("Phase4RequestClose",null,[],[])')
                page.wait_for_function('window.applicationResult!==null',polling=100,timeout=60000)
                report['shutdown']=observe_shutdown(page,browser)
                assert page.evaluate('window.applicationResult.code')==0
                assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets']
            assert not report['errors']
        except Exception as error:
            report['teardownFailure']=str(error);report['passed']=False
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ('passed','failure','checks')},indent=2))
raise SystemExit(0 if report['passed'] else 1)
