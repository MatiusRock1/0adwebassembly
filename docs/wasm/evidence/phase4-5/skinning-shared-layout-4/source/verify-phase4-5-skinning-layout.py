"""Check bytes for a skinning performance optimization; never FPS evidence."""
import argparse
import hashlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import socket
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock

ROOT=Path(__file__).resolve().parents[2]

class ProbeHandler(SimpleHTTPRequestHandler):
    extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.mjs':'text/javascript'}

PROBE=r'''async variants=>{
  const {sharedSkinningCode}=await import('/webgpu-skinning.mjs');
  const {WebGPUEngine}=await import('/webgpu-engine.mjs');
  const adapter=await navigator.gpu.requestAdapter({powerPreference:'high-performance'});
  if(!adapter)throw new Error('No WebGPU adapter for skinning byte comparison');
  const device=await adapter.requestDevice(),results=[];
  try{
    for(const variant of variants){
      device.pushErrorScope('validation');
      const resources=[];
      const buffer=(bytes,usage)=>{
        const b=device.createBuffer({size:bytes.byteLength,usage:usage|GPUBufferUsage.COPY_DST});
        resources.push(b);device.queue.writeBuffer(b,0,bytes);return b;
      };
      try{
        const vertices=new Float32Array(36);
        vertices.set([1,0,0,1,0,1,0,0,1,2,3,1],12);
        vertices.set([0,1,0,-1,0,0,1,0,4,5,6,1],24);
        const skin=new Uint8Array([0,0,0,0,255,255,255,255,255,0,0,0,0,255,255,255,128,127,0,0,0,1,255,255]);
        const matrices=new Float32Array(variant.matrixBytes/4);
        matrices.set([1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1]);
        matrices.set([1,0,0,0,0,1,0,0,0,0,1,0,-1,2,.5,1],16);
        const draw=new Float32Array(8);draw[0]=2;draw.set([1,1,2,5],4);
        const original=new Uint8Array(128).fill(0xa5);
        const vertexBuffer=buffer(vertices,GPUBufferUsage.STORAGE),skinBuffer=buffer(skin,GPUBufferUsage.STORAGE);
        const matrixBuffer=buffer(matrices,GPUBufferUsage.UNIFORM),drawBuffer=buffer(draw,GPUBufferUsage.UNIFORM);
        const outputs=[0,1,2,3].map(()=>buffer(original,GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC));
        const mergedCode=sharedSkinningCode(variant.code);
        const encoder=device.createCommandEncoder();
        for(const merged of [false,true]){
          const module=device.createShaderModule({code:merged?mergedCode:variant.code});
          const messages=(await module.getCompilationInfo()).messages.filter(m=>m.type==='error');
          if(messages.length)throw new Error(JSON.stringify(messages));
          const pipeline=device.createComputePipeline({layout:'auto',compute:{module,entryPoint:'main'}});
          const group0=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:{buffer:matrixBuffer}},{binding:1,resource:{buffer:drawBuffer}}]});
          const bindings=[vertexBuffer,skinBuffer,merged?outputs[2]:outputs[0],...merged?[]:[outputs[1]]];
          const group1=device.createBindGroup({layout:pipeline.getBindGroupLayout(1),entries:bindings.map((b,binding)=>({binding,resource:{buffer:b}}))});
          const pass=encoder.beginComputePass();pass.setPipeline(pipeline);pass.setBindGroup(0,group0);pass.setBindGroup(1,group1);pass.dispatchWorkgroups(1);pass.end();
        }
        // Exercise the production dispatcher too, including its alternate
        // layout, original shared allocation and dynamic uniform snapshots.
        const key=JSON.stringify(variant.defines);
        const catalog={programs:{'glsl/compute_skinning':{defines:Object.keys(variant.defines),variants:{[key]:variant.definition}}}};
        const engine=new WebGPUEngine({device,dispose:async()=>{}},null,catalog);
        resources.push(engine.uniformBuffer);
        const id=engine.createShader('glsl/compute_skinning',variant.defines),shader=engine.get(id);
        const uniform=(name,values)=>engine.command('uniform',[shader.bindingSlots.get(name),values]);
        uniform('skinBlendMatrices',matrices);uniform('vertexCount',[2]);uniform('offset',[1,1,2,5]);
        for(const [name,b] of [['InputVertices',vertexBuffer],['SkinData',skinBuffer],['OutputPositions',outputs[3]],['OutputNormalsTangents',outputs[3]]]){
          const resource=engine.put({kind:'buffer',buffer:b,size:name==='InputVertices'?vertices.byteLength:name==='SkinData'?skin.byteLength:128});
          // Both output slots must refer to the exact same engine object ID.
          const value=name==='OutputNormalsTangents'?shader.storage.get('OutputPositions'):resource;
          engine.command('storageBuffer',[shader.bindingSlots.get(name),value]);
        }
        engine.currentCompute={shader};engine.command('beginCompute',[]);engine.command('dispatch',[1,1,1]);engine.command('endCompute',[]);engine.submit();
        if(!shader.sharedSkinningId)throw new Error('Production shared-allocation path was not exercised');
        const readback=device.createBuffer({size:512,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});resources.push(readback);
        outputs.forEach((b,i)=>encoder.copyBufferToBuffer(b,0,readback,i*128,128));
        device.queue.submit([encoder.finish()]);await readback.mapAsync(GPUMapMode.READ);
        const bytes=new Uint8Array(readback.getMappedRange()),expected=original.slice();
        expected.set(bytes.subarray(32,64),32);expected.set(bytes.subarray(128+80,128+112),80);
        const actual=bytes.slice(256,384),production=bytes.slice(384,512),positions=[...new Float32Array(bytes.buffer,32,4)];
        if(JSON.stringify(positions)!==JSON.stringify([3,5,7,0]))throw new Error('Original reference skinning did not produce the expected translated vertex');
        const mismatches=actual.reduce((count,value,i)=>count+Number(value!==expected[i]),0);
        const productionMismatches=production.reduce((count,value,i)=>count+Number(value!==expected[i]),0);
        readback.unmap();
        const validation=await device.popErrorScope();if(validation)throw new Error(validation.message);
        if(mismatches || productionMismatches)throw new Error('Merged skinning output differs: helper='+mismatches+', production='+productionMismatches);
        results.push({matrixBytes:variant.matrixBytes,mismatches,productionMismatches,positions,actual:[...actual],scope:'Two vertices, two weighted bones, nonzero input/output offsets and untouched sentinel bytes; original shader versus merged output binding and actual engine dispatcher'});
      }finally{for(const resource of resources)resource.destroy();}
    }
    return {adapterInfo:Object.fromEntries(['vendor','architecture','device','description'].map(key=>[key,adapter.info[key]])),results};
  }finally{device.destroy();}
}'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    catalog=ROOT/'wasm/build/phase4-5/shaders/webgpu-shaders.json'
    variants=json.loads(catalog.read_text())['programs']['glsl/compute_skinning']['variants']
    inputs=[dict(code=v['code']['compute'],defines=json.loads(key),definition=v,matrixBytes=next(b['size'] for b in v['uniforms'] if b['binding']==0)) for key,v in variants.items()]
    report=dict(passed=False,performanceAcceptance=False,scope='Byte validation required by the shared-output skinning optimization',
                helperSHA256=hashlib.sha256((ROOT/'wasm/browser/webgpu-skinning.mjs').read_bytes()).hexdigest(),
                engineSHA256=hashlib.sha256((ROOT/'wasm/browser/webgpu-engine.mjs').read_bytes()).hexdigest(),
                referenceSHA256=[hashlib.sha256(v['code'].encode()).hexdigest() for v in inputs])
    server=None
    try:
        with BenchmarkLock(),(args.output/'server.log').open('w') as log:
            with socket.socket() as available:available.bind(('127.0.0.1',8099))
            server=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--serve'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(100):
                try:
                    with urllib.request.urlopen('http://localhost:8099/webgpu-probe.html',timeout=1):break
                except OSError:
                    if server.poll() is not None:raise RuntimeError('Skinning probe server exited')
                    time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True,args=['--force-high-performance-gpu'])
                try:
                    page=browser.new_page();page.goto('http://localhost:8099/webgpu-probe.html')
                    report.update(page.evaluate(PROBE,inputs));report['passed']=True
                finally:browser.close()
    except Exception as error:report['failure']=str(error)
    finally:
        if server and server.poll() is None:server.terminate();server.wait(timeout=15)
        (args.output/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report.get(k) for k in ['passed','failure','adapterInfo']},indent=2))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    if sys.argv[1:]==['--serve']:
        with ThreadingHTTPServer(('127.0.0.1',8099),partial(ProbeHandler,directory=str(ROOT/'wasm/browser'))) as server:server.serve_forever()
    else:raise SystemExit(main())
