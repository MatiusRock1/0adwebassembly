"""Visible original-game PCF verification and matched hard/filtered captures."""
import hashlib
import argparse
import json
from pathlib import Path
import traceback
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_flow import open_original_match,parity_settings,checkpoint
from phase4_browser import enter_fullscreen
from scene_surface import assert_surface

out=Path('docs/wasm/evidence/phase4/visible-shadow-pcf');out.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reuse',action='store_true');args=parser.parse_args()
report=dict(passed=False,phase4Accepted=False,errors=[],console=[])
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://127.0.0.1:9226')
    page=next(page for page in browser.contexts[0].pages if 'localhost:8091' in page.url)
    page.bring_to_front()
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.on('console',lambda message:report['console'].append(message.text))
    page.add_init_script('''
      window.phase4ShadowShaders=[];
      const original=WebGL2RenderingContext.prototype.shaderSource;
      WebGL2RenderingContext.prototype.shaderSource=function(shader,source){
        if(source.includes('phase4BilinearShadow'))window.phase4ShadowShaders.push({gl:this,shader,source});
        return original.call(this,shader,source);
      };
    ''')
    gui=lambda code:page.evaluate('(code)=>window.evaluateOriginalGUI(code)',code)
    try:
        if not args.reuse:
            if page.evaluate('window.application?.applicationState && window.applicationResult===null'):
                if page.evaluate('document.fullscreenElement!==null'):page.evaluate('document.exitFullscreen()')
                page.locator('#close').click()
                page.wait_for_function('window.applicationResult!==null',timeout=60000)
            page.goto('http://localhost:8091/application.html?automation=1')
            page.locator('#start').click()
        page.wait_for_function('window.application?.applicationState || window.applicationResult',timeout=180000)
        assert page.evaluate('window.applicationResult===null')
        page.evaluate('''()=>{
          const original=WebGL2RenderingContext.prototype.compileShader;
          WebGL2RenderingContext.prototype.compileShader=function(shader){
            const result=original.call(this,shader);
            for(const record of window.phase4ShadowShaders)
              if(record.shader===shader){record.compiled=this.getShaderParameter(shader,this.COMPILE_STATUS);record.log=this.getShaderInfoLog(shader);}
            return result;
          };
        }''')
        if not args.reuse:page.evaluate('window.application.resumeOriginalAudio()')
        report['fullscreen']=enter_fullscreen(page,browser)
        report['attributes']=open_original_match(gui,parity_settings())
        report['state']=checkpoint(gui,10000)
        report['surface']=assert_surface(page,1920,1080)
        report['shadowQuality']=gui('Engine.ConfigDB_GetValue("user","shadowquality")')
        gui('Engine.ConfigDB_CreateValue("user","shadowpcf","false"); "hard"')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out/'original-hard-shadow.png'))
        gui('Engine.ConfigDB_CreateValue("user","shadowpcf","true"); "filtered"')
        page.wait_for_timeout(1500)
        report['shaderCompilation']=page.evaluate('''window.phase4ShadowShaders.map(record=>({
          compiled:record.compiled,
          log:record.log,
          softwarePCF:record.source.includes('float phase4BilinearShadow'),
          normalizedCoordinates:record.source.includes('shadowTexelCoordinates'),
          originalFourSampleWeights:record.source.includes('size.zxzx')
        }))''')
        assert report['shaderCompilation'],'PCF shader adaptation was not used'
        assert all(shader['compiled'] for shader in report['shaderCompilation']),report['shaderCompilation']
        assert any(shader['originalFourSampleWeights'] for shader in report['shaderCompilation'])
        assert all(shader['normalizedCoordinates'] for shader in report['shaderCompilation'])
        page.screenshot(path=str(out/'original-filtered-shadow.png'))
        report['shadowPCF']=gui('Engine.ConfigDB_GetValue("user","shadowpcf")')
        assert report['shadowPCF']=='true'
        report['engineErrors']=[line for line in report['console'] if 'ERROR:' in line]
        assert not report['errors'] and not report['engineErrors']
        report['buildSHA256']=hashlib.sha256(Path('wasm/dist/application-phase4/pyrogenesis-application.wasm').read_bytes()).hexdigest()
        report['passed']=True
    except Exception as error:
        report['failure']=str(error);report['traceback']=traceback.format_exc()
    finally:
        # Keep the tested original match visible, paused and filtered, for the
        # operator to inspect. No hidden run or automatic tab destruction.
        (out/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({key:report.get(key) for key in ['passed','failure','shadowQuality','shadowPCF','shaderCompilation']},indent=2))
raise SystemExit(0 if report['passed'] else 1)
