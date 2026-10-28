"""Capture original browser renderers at the same simulation tick and camera.

This prepares reviewable visual evidence; producing images alone never accepts
visual parity. A reference report enforces matching scene, camera and quality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import traceback
import base64
import struct
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import (CDP_URL,APPLICATION_URL,start_application,new_test_page,enter_fullscreen,
    observe_shutdown,assert_renderer_clean,renderer_diagnostics,move_original_pointer)
from phase4_flow import open_original_match,parity_settings,checkpoint
from phase4_workload import graphics_settings
from scene_surface import assert_surface
from phase45_benchmark_contract import fingerprint
CONTRACT=json.loads((Path(__file__).resolve().parents[1]/'scenario/phase4-5-visual-contract.json').read_text())

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--reference',type=Path)
parser.add_argument('--build',type=Path,default=Path('wasm/dist/application-phase4-5'))
parser.add_argument('--presented-canvas',action='store_true',help='Capture the presented original canvas at 1:1 CSS size; works around the frozen WebGL F2 readback defect.')
parser.add_argument('--linked-artifacts',type=Path,help='Read-only archived linker outputs for a historical renderer comparison; record every overridden artifact hash.')
parser.add_argument('--functional-window',action='store_true',help='Read original 1080p render target without requiring OS foreground/fullscreen; does not verify physical presentation.')
args=parser.parse_args();args.evidence.mkdir(parents=True,exist_ok=True)
if args.presented_canvas:
    CONTRACT=json.loads((Path(__file__).resolve().parents[1]/'scenario/phase4-5-presented-visual-contract.json').read_text())
reference=json.loads(args.reference.read_text()) if args.reference else None
report=dict(passed=False,visualParityAccepted=False,phase45Accepted=False,errors=[],console=[],buildSHA256=fingerprint(args.build),visualContract=CONTRACT)
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL);page=new_test_page(browser)
    report['browserVersion']=browser.version
    page.on('console',lambda message:report['console'].append(message.text))
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    if args.linked_artifacts:
        overridden={}
        archived={}
        isolation={'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp','Cross-Origin-Resource-Policy':'same-origin','Cache-Control':'no-store'}
        def serve_archived(route):
            path,mime=archived[urlsplit(route.request.url).path.rsplit('/',1)[-1]]
            route.fulfill(path=str(path),content_type=mime,headers=isolation)
        for name,content_type in [('pyrogenesis-application.mjs','text/javascript'),('pyrogenesis-application.wasm','application/wasm')]:
            artifact=(args.linked_artifacts/name).resolve()
            assert artifact.is_file(),artifact
            archived[name]=(artifact,content_type)
            page.context.route('**/'+name,serve_archived)
            overridden[name]=hashlib.sha256(artifact.read_bytes()).hexdigest()
        report['archivedLinkerOverrides']=dict(directory=str(args.linked_artifacts),SHA256=overridden)
        report['buildSHA256'].update(overridden)
    launcher=args.build/'application.mjs'
    if CONTRACT.get('fixedFrameFrequency') and launcher.is_file():
        original=launcher.read_text()
        if 'functional-frame-frequency' not in original:
            assert original.count('arguments: [')==1,'Unknown historical launcher'
            adapted=original.replace('arguments: [',"arguments: ['-fixed-frame-frequency=60',",1)
            page.route('**/application.mjs',lambda route:route.fulfill(body=adapted,content_type='text/javascript'))
            report['functionalLauncherOverride']=dict(originalSHA256=hashlib.sha256(original.encode()).hexdigest(),
                overrideSHA256=hashlib.sha256(adapted.encode()).hexdigest(),change='Original -fixed-frame-frequency=60 CLI argument only; frozen files remain unchanged')
    gui=lambda code:page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    def capture(name):
        if args.presented_canvas:
            helper=Path(__file__).with_name('capture-original-framebuffer.js').read_text()
            captured=page.evaluate('async()=>{'+helper+';return await captureOriginalFramebuffer();}')
            png=base64.b64decode(captured.pop('png'))
            (args.evidence/name).write_bytes(png)
            assert struct.unpack('>II',png[16:24])==(1920,1080)
            report.setdefault('framebufferCaptures',[]).append(dict(file=name,helperSHA256=hashlib.sha256(helper.encode()).hexdigest(),**captured))
            report['captureMethod']='Original persistent render target RGBA readback at frame completion, original GUI included; no desktop capture or raster editing'
            return
        # Use the original renderer's F2 PNG so every backend contributes its
        # actual 1920x1080 image, independent of monitor letterboxing or CSS.
        page.evaluate('window.application.FS.mkdirTree("/data/screenshots")')
        before=page.evaluate('window.application.FS.readdir("/data/screenshots")')
        page.keyboard.press('F2')
        page.wait_for_function('''before=>application.FS.readdir('/data/screenshots').some(name=>{
          if(!name.endsWith('.png')||before.includes(name))return false;
          const bytes=application.FS.readFile('/data/screenshots/'+name);
          return bytes.length>20 && bytes[0]===137 && [73,69,78,68].every((value,i)=>bytes[bytes.length-8+i]===value);
        })''',arg=before,polling=100,timeout=30000)
        file=page.evaluate('(before)=>window.application.FS.readdir("/data/screenshots").find(name=>name.endsWith(".png")&&!before.includes(name))',before)
        encoded=page.evaluate('''name=>{
          const bytes=window.application.FS.readFile('/data/screenshots/'+name),parts=[];
          for(let index=0;index<bytes.length;index+=32768)parts.push(String.fromCharCode(...bytes.subarray(index,index+32768)));
          return btoa(parts.join(''));
        }''',file)
        (args.evidence/name).write_bytes(base64.b64decode(encoded))
        report['captureMethod']='Original F2 renderer PNG/readback; monitor presentation is checked separately'
    try:
        address=urlsplit(APPLICATION_URL);parameters=dict(parse_qsl(address.query))
        if CONTRACT.get('fixedFrameFrequency'):
            parameters['functional-frame-frequency']=str(CONTRACT['fixedFrameFrequency'])
        application_url=urlunsplit(address._replace(query=urlencode(parameters)))
        report['applicationURL']=application_url
        start_application(page,application_url)
        report['functionalFixedFrameFrequency']=CONTRACT.get('fixedFrameFrequency')
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult===null')
        if CONTRACT.get('fixedFrameFrequency'):
            assert page.evaluate('application.arguments.includes("-fixed-frame-frequency=60")'),'Original functional frame clock was not enabled'
        gui('''(()=>{for(const [key,value] of Object.entries(PROFILE))Engine.ConfigDB_CreateValue("user",key,value);return "temporary matched graphics";})()'''.replace('PROFILE',json.dumps(CONTRACT['graphicsProfile'])))
        report['attributes']=open_original_match(gui,parity_settings(),reference['attributes'] if reference else None)
        if args.functional_window:
            gui('Engine.PauseOnFocusLoss(false); "functional capture only"')
            page.evaluate('application.ccall("Phase4Resize",null,["number","number"],[1920,1080])')
            page.wait_for_function('application.applicationState.width===1920 && application.applicationState.height===1080',timeout=30000)
            report['physicalPresentationVerified']=False
            report['functionalWindow']=True
        else:
            report['fullscreen']=enter_fullscreen(page,browser)
        box=page.locator('#canvas').bounding_box()
        move_original_pointer(page,600,950)
        report['simulation']=checkpoint(gui,CONTRACT['simulationMs'])
        gui('g_Selection.reset();g_Selection.setHighlightList([]);"clear original selection and hover"')
        dump=page.evaluate('window.application.FS.readFile("/logs/sim_dump.txt",{encoding:"utf8"})').replace('\r\n','\n').encode()
        report['simulationSHA256']=hashlib.sha256(dump).hexdigest()
        report['graphicsSettings']=graphics_settings(gui)
        assert report['graphicsSettings']==CONTRACT['graphicsProfile'],('Graphics profile did not apply',report['graphicsSettings'])
        camera=reference['cameraRequest'] if reference else json.loads(gui('JSON.stringify({position:Engine.GetCameraPosition(),rotation:Engine.GetCameraRotation(),zoom:Engine.GetCameraZoom()})'))
        report['cameraRequest']=camera
        values=[camera['position'][key] for key in ('x','y','z')]+[camera['rotation'][key] for key in ('x','y')]+[camera['zoom']]
        # Both runs pass through the original fixed-point camera API, including
        # the first reference, so conversion precision is identical.
        gui('Engine.SetCameraData('+','.join(map(str,values))+'); "camera"')
        page.wait_for_timeout(2000)
        gui('g_Selection.reset();g_Selection.setHighlightList([]);"clear original selection and hover"')
        report['camera']=json.loads(gui('JSON.stringify({position:Engine.GetCameraPosition(),rotation:Engine.GetCameraRotation(),zoom:Engine.GetCameraZoom()})'))
        if reference:
            for key in ('attributes','simulationSHA256','graphicsSettings','camera'):
                assert report[key]==reference[key],('Visual reference mismatch',key,report[key],reference[key])
        report['surface']=assert_surface(page,1920,1080)
        report['renderer']=renderer_diagnostics(page)
        capture('original-matched.png')
        page.locator('#canvas').screenshot(path=str(args.evidence/'browser-original-matched.png'))
        for value,label in [('false','hard'),('true','pcf')]:
            gui('Engine.ConfigDB_CreateValue("user","shadowpcf","'+value+'"); "shadow"')
            page.wait_for_timeout(1500)
            capture('original-shadow-'+label+'.png')
        assert_renderer_clean(page)
        assert not report['errors'] and not any('ERROR:' in line for line in report['console'])
        report['passed']=True
    except Exception as error:
        report['failure']=str(error);report['traceback']=traceback.format_exc()
    finally:
        try:
            if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
            if page.evaluate('window.application?.applicationState && window.applicationResult===null'):
                page.locator('#close').click();page.wait_for_function('window.applicationResult!==null',timeout=60000)
                report['shutdown']=observe_shutdown(page,browser)
                assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets']
                assert page.evaluate('window.applicationResult.code')==0
            assert not report['errors']
        except Exception as error:
            report['teardownFailure']=str(error);report['passed']=False
        (args.evidence/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ('passed','failure','visualParityAccepted')},indent=2))
raise SystemExit(0 if report['passed'] else 1)
