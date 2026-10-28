from phase4_browser import APPLICATION_URL, CDP_URL, EVIDENCE_ROOT, start_application, assert_renderer_clean
"""Exercise real browser mouse and keyboard through the original SDL/GUI input."""
import json
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match, parity_settings
from phase4_browser import observe_shutdown,enter_fullscreen,new_test_page,move_original_pointer

out=(Path(EVIDENCE_ROOT)/'original-input');out.mkdir(parents=True,exist_ok=True)
report=dict(passed=False,phase4Accepted=False,assertions={},errors=[],console=[])
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL)
    report['browserVersion']=browser.version
    page=new_test_page(browser);page.bring_to_front()
    page.set_default_timeout(15000)
    def progress(stage):
        report['stage']=stage
        report['observedSurface']=page.evaluate('({fullscreen:!!document.fullscreenElement,focused:document.hasFocus(),canvas:[document.getElementById("canvas").width,document.getElementById("canvas").height]})')
        (out/'progress.json').write_text(json.dumps(report,indent=2))
        print('ORIGINAL_INPUT_STAGE',stage,report['observedSurface'],flush=True)
    page.add_init_script('''window.phase4Mouse=[];document.addEventListener('mousemove',event=>{
      const rect=document.getElementById('canvas')?.getBoundingClientRect();
      window.phase4Mouse.push({client:[event.clientX,event.clientY],rect:rect?.toJSON(),target:event.target.id});
      if(window.phase4Mouse.length>10)window.phase4Mouse.shift();
    },true);
    window.phase45FullscreenTrace=[];
    document.addEventListener('fullscreenchange',()=>{
      const event={full:!!document.fullscreenElement,time:performance.now(),inner:[innerWidth,innerHeight]};
      window.phase45FullscreenTrace.push(event);console.log('PHASE45_FULLSCREEN '+JSON.stringify(event));
    });''')
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.on('console',lambda message:report['console'].append(message.text))
    page.on('console',lambda message:print(message.text,flush=True) if message.text.startswith('PHASE45_FULLSCREEN ') else None)
    gui=lambda code:page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    selected=lambda:json.loads(gui('JSON.stringify(g_Selection.toList())'))
    def click(x,y,button='left'):
        box=page.locator('#canvas').bounding_box()
        move_original_pointer(page,x,y)
        page.wait_for_timeout(100)
        if page.evaluate('document.pointerLockElement===document.getElementById("canvas")'):
            # Mixing CDP's cached absolute mouse coordinates with OS relative
            # motion injects a spurious movement at button dispatch. Keep the
            # entire captured gesture on the real Windows input path.
            import ctypes
            down,up=(2,4) if button=='left' else (8,16)
            ctypes.windll.user32.mouse_event(down,0,0,0,0)
            page.wait_for_timeout(50)
            ctypes.windll.user32.mouse_event(up,0,0,0,0)
        else:
            page.mouse.down(button=button);page.wait_for_timeout(50);page.mouse.up(button=button)
        page.wait_for_timeout(400)
        report['nativeInputEvents']=json.loads(gui('JSON.stringify(globalThis.phase45InputTrace || [])'))
        report.setdefault('mouseEvents',[]).append(dict(requested=[x,y],button=button,
            canvasBox=box,dom=page.evaluate('window.phase4Mouse'),
            observed=json.loads(gui('JSON.stringify({x:mouseX,y:mouseY,selected:g_Selection.toList(),inputState,clickedEntity,picked:Engine.PickEntityAtPoint(mouseX,mouseY)})'))))
    try:
        start_application(page)
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult===null')
        page.evaluate('window.application.resumeOriginalAudio()');report['attributes']=open_original_match(gui,parity_settings())
        progress('match-loaded')
        report['fullscreen']=enter_fullscreen(page,browser)
        progress('fullscreen-verified')
        page.wait_for_timeout(1500)
        # Pause using the original configured keyboard shortcut.
        report['pausedBeforeKeyboard']=gui('String(Engine.IsPaused())')=='true'
        report['inputFocus']=page.evaluate('({focused:document.hasFocus(),element:document.activeElement?.id})')
        page.keyboard.press('Shift+Space');page.wait_for_timeout(400)
        paused=gui('String(Engine.IsPaused())')=='true'
        report['assertions']['keyboardPause']=paused!=report['pausedBeforeKeyboard']
        assert report['assertions']['keyboardPause']
        # The original pause overlay intentionally consumes world clicks to
        # resume. Test selection while running, and keep the pointer away from
        # screen edges so the original edge-scroll does not move the camera.
        box=page.locator('#canvas').bounding_box()
        move_original_pointer(page,960,540)
        if paused:page.keyboard.press('Shift+Space');page.wait_for_timeout(400)
        assert gui('String(Engine.IsPaused())')=='false'
        progress('pause-resume-verified')
        gui('''(()=>{
          globalThis.phase45InputTrace=[];
          for(const name of ["handleInputBeforeGui","handleInputAfterGui"]){
            const original=globalThis[name];
            globalThis[name]=function(ev,...args){
              const entry={handler:name,type:ev.type,x:ev.x,y:ev.y,clicks:ev.clicks,
                hovered:args[0]?.name,picked:ev.x===undefined?null:Engine.PickEntityAtPoint(ev.x,ev.y)};
              const result=original.call(this,ev,...args);
              Object.assign(entry,{clickedEntity,inputState,selected:g_Selection.toList()});
              phase45InputTrace.push(entry);if(phase45InputTrace.length>100)phase45InputTrace.shift();
              return result;
            };
          }
          return "input observation installed";
        })()''')
        report['points']=json.loads(gui('''(()=>{
          const regions=new Map();
          for(let y=170;y<820;y+=8)for(let x=280;x<1640;x+=8){
            const id=Engine.PickEntityAtPoint(x,y);if(!id)continue;
            const entity=GetEntityState(id);if(entity?.player!==1)continue;
            if(!entity.unitAI && !entity.trainer)continue;
            if(!regions.has(id))regions.set(id,{id,unit:!!entity.unitAI,template:entity.template,pixels:[]});
            regions.get(id).pixels.push({x,y});
          }
          const points=[];
          for(const region of regions.values()){
            const cx=region.pixels.reduce((sum,p)=>sum+p.x,0)/region.pixels.length;
            const cy=region.pixels.reduce((sum,p)=>sum+p.y,0)/region.pixels.length;
            region.pixels.sort((a,b)=>(a.x-cx)**2+(a.y-cy)**2-((b.x-cx)**2+(b.y-cy)**2));
            const point=region.pixels.find(p=>Engine.PickEntityAtPoint(p.x-3,p.y-3)===region.id && Engine.PickEntityAtPoint(p.x+3,p.y+3)===region.id);
            if(point)points.push({id:region.id,unit:region.unit,template:region.template,...point});
          }
          return JSON.stringify(points);
        })()'''))
        units=[point for point in report['points'] if point['unit']]
        progress('pickable-units-located')
        assert len(units)>=2,'Two original units must be pickable'
        click(units[0]['x'],units[0]['y']);assert units[0]['id'] in selected(),report['mouseEvents'][-1]
        page.keyboard.down('Shift');click(units[1]['x'],units[1]['y']);page.keyboard.up('Shift')
        chosen=selected();assert {units[0]['id'],units[1]['id']}<=set(chosen)
        report['assertions']['mouseMultipleSelection']=True
        progress('multiple-selection-verified')
        page.keyboard.press('Control+1');page.wait_for_timeout(400)
        # Browser security reserves Escape to release Pointer Lock. Release it
        # explicitly before exercising the original game's selection shortcut.
        page.evaluate('document.exitPointerLock()')
        page.wait_for_timeout(150)
        page.keyboard.press('Escape');page.wait_for_timeout(400);assert not selected()
        progress('selection-cleared')
        page.keyboard.press('1');page.wait_for_timeout(400);assert set(selected())==set(chosen)
        report['assertions']['keyboardControlGroup']=True
        # Exercise the original building rally action through a real right-click,
        # then inspect the simulation result rather than only the preview marker.
        centre=next(point for point in report['points'] if point['template'].endswith('/civil_centre'))
        # Group recall may centre the original camera. Locate the same building
        # in the current view rather than clicking a stale screen coordinate.
        report['cameraAfterGroupRecall']=json.loads(gui('JSON.stringify(Engine.GetCameraPosition())'))
        centre.update(json.loads(gui('''(()=>{
          const pixels=[];
          for(let y=170;y<820;y+=8)for(let x=280;x<1640;x+=8)
            if(Engine.PickEntityAtPoint(x,y)===CENTRE) pixels.push({x,y});
          if(!pixels.length)throw new Error("Original centre is not visible after group recall");
          const cx=pixels.reduce((s,p)=>s+p.x,0)/pixels.length,cy=pixels.reduce((s,p)=>s+p.y,0)/pixels.length;
          pixels.sort((a,b)=>(a.x-cx)**2+(a.y-cy)**2-((b.x-cx)**2+(b.y-cy)**2));
          return JSON.stringify(pixels[0]);
        })()'''.replace('CENTRE',str(centre['id'])))))
        click(centre['x'],centre['y']);assert selected()==[centre['id']]
        rally=json.loads(gui('''(()=>{
          const centre=Engine.GuiInterfaceCall("GetEntityState",CENTRE).position;
          for(let y=300;y<700;y+=30)for(let x=600;x<1450;x+=30){
            if(Engine.PickEntityAtPoint(x,y))continue;
            const world=Engine.GetTerrainAtScreenPoint(x,y);
            const distance=Math.hypot(world.x-centre.x,world.z-centre.z);
            if(distance>10 && distance<35)return JSON.stringify({x,y,world});
          }
          throw new Error("No original visible rally terrain found");
        })()'''.replace('CENTRE',str(centre['id']))))
        click(rally['x'],rally['y'],'right')
        page.wait_for_timeout(1200)
        actual=json.loads(gui('JSON.stringify(Engine.GuiInterfaceCall("GetEntityState",'+str(centre['id'])+').rallyPoint.position)'))
        assert abs(actual['x']-rally['world']['x'])<.5 and abs(actual['z']-rally['world']['z'])<.5,(rally,actual)
        report['rallyPoint']=dict(requested=rally,actual=actual)
        report['assertions']['mouseRallyPoint']=True
        page.keyboard.press('1');page.wait_for_timeout(400);assert set(selected())==set(chosen)
        before=json.loads(gui('JSON.stringify(Engine.GetCameraPosition())'))
        page.keyboard.down('ArrowRight');page.wait_for_timeout(750);page.keyboard.up('ArrowRight')
        after=json.loads(gui('JSON.stringify(Engine.GetCameraPosition())'))
        assert before!=after;report['assertions']['keyboardCamera']=True
        minimap=json.loads(gui('JSON.stringify(Engine.GetGUIObjectByName("minimap").getComputedSize())'))
        before=json.loads(gui('JSON.stringify(Engine.GetCameraPosition())'))
        click(minimap['left']+(minimap['right']-minimap['left'])*0.6,minimap['top']+(minimap['bottom']-minimap['top'])*0.6)
        page.wait_for_timeout(800)
        after=json.loads(gui('JSON.stringify(Engine.GetCameraPosition())'))
        assert before!=after;report['assertions']['mouseMinimap']=True
        # Right-click on actual terrain must produce original unit orders.
        click(1000,500,'right')
        page.wait_for_timeout(3000)
        orders=json.loads(gui('JSON.stringify(g_Selection.toList().map(id=>GetEntityState(id).unitAI))'))
        report['orders']=orders
        assert any(state['orders'] for state in orders);report['assertions']['contextualMovement']=True
        report['audio']=page.evaluate('window.application.getOriginalAudioState()')
        page.screenshot(path=str(out/'original-input.png'))
        report['engineErrors']=[line for line in report['console'] if 'ERROR:' in line]
        assert not report['errors'] and not report['engineErrors']
        assert_renderer_clean(page)
        report['passed']=True
    except Exception as error:
        report['failure']=str(error)
        report['traceback']=traceback.format_exc()
        page.screenshot(path=str(out/'failure.png'),timeout=10000)
    finally:
        try:report['fullscreenTrace']=page.evaluate('window.phase45FullscreenTrace || []')
        except Exception:pass
        try:
            if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
            if page.evaluate('window.application?.applicationState && window.applicationResult===null'):
                page.locator('#close').click();page.wait_for_function('window.applicationResult!==null',timeout=60000)
                report['shutdown']=observe_shutdown(page,browser)
                assert not report['shutdown']['workers'] and not report['shutdown']['liveApplicationTargets'],report['shutdown']
                assert page.evaluate('window.applicationResult.code')==0
        except Exception as error:
            report['teardownFailure']=str(error);report['passed']=False
        (out/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure','assertions']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
