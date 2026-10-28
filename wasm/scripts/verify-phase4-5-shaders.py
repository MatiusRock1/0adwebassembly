"""Validate every packaged WGSL module with the real visible-browser adapter."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from phase4_browser import CDP_URL,APPLICATION_URL
from benchmark_lock import BenchmarkLock

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--adapted',action='store_true',help='Validate the renderer sampler adaptation as actually submitted to WebGPU.')
args=parser.parse_args()
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL)
    page=browser.contexts[0].new_page()
    try:
        page.goto(APPLICATION_URL)
        report=page.evaluate('''async(adapted)=>{
          const adapt=adapted?(await import('./webgpu-border.mjs')).adaptBorderSampling:(code)=>({code});
          const adapter=await navigator.gpu.requestAdapter({powerPreference:'high-performance'});
          if(!adapter)throw new Error('No WebGPU adapter');
          const device=await adapter.requestDevice();
          const catalog=await (await fetch('webgpu-shaders.json')).json();
          const result={passed:false,adapter:{vendor:adapter.info.vendor,architecture:adapter.info.architecture},
            fingerprint:catalog.provenance.buildFingerprint,samplerAdaptation:adapted,modules:0,errors:[]};
          try {
            for(const [name,program] of Object.entries(catalog.programs))
              for(const [defines,variant] of Object.entries(program.variants))
                for(const [stage,code] of Object.entries(variant.code)){
                  const module=device.createShaderModule({label:name+' '+stage,code:adapt(code,variant.textures,stage).code});
                  const info=await module.getCompilationInfo();result.modules++;
                  for(const message of info.messages)if(message.type==='error')
                    result.errors.push({name,defines,stage,line:message.lineNum,message:message.message});
                }
            result.passed=result.errors.length===0;
            return result;
          } finally {device.destroy();}
        }''',args.adapted)
    finally:page.close()
args.evidence.parent.mkdir(parents=True,exist_ok=True)
args.evidence.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
raise SystemExit(not report['passed'])
