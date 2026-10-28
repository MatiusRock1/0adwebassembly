"""Read back real GPU results for legacy border addressing and mip filtering."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from benchmark_lock import BenchmarkLock
from phase4_browser import CDP_URL,APPLICATION_URL

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args();args.evidence.parent.mkdir(parents=True,exist_ok=True)
with BenchmarkLock(),sync_playwright() as p:
    browser=p.chromium.connect_over_cdp(CDP_URL);page=browser.contexts[0].new_page()
    try:
        page.goto(APPLICATION_URL)
        report=page.evaluate('''async()=>{
          const {adaptBorderSampling,borderConstants}=await import('./webgpu-border.mjs');
          const adapter=await navigator.gpu.requestAdapter({powerPreference:'high-performance'});
          if(!adapter)throw Error('No WebGPU adapter');
          const device=await adapter.requestDevice();
          const result={passed:false,phase45Accepted:false,adapter:{vendor:adapter.info.vendor,architecture:adapter.info.architecture},tests:[],errors:[]};
          device.addEventListener('uncapturederror',event=>result.errors.push(event.error.message));
          const resources=[];
          try {
            const texture=device.createTexture({size:[2,2],mipLevelCount:2,format:'rgba8unorm',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.COPY_DST});resources.push(texture);
            device.queue.writeTexture({texture},new Uint8Array([255,0,0,255,255,0,0,255,255,0,0,255,255,0,0,255]),{bytesPerRow:8},[2,2]);
            device.queue.writeTexture({texture,mipLevel:1},new Uint8Array([0,255,0,255]),{bytesPerRow:4},[1,1]);
            const layout=device.createBindGroupLayout({entries:[
              {binding:0,visibility:GPUShaderStage.FRAGMENT,texture:{sampleType:'float'}},
              {binding:1,visibility:GPUShaderStage.FRAGMENT,sampler:{type:'filtering'}}]});
            const pipelineLayout=device.createPipelineLayout({bindGroupLayouts:[layout]});
            const uvs=[-.25,0,.25,.5,.75,1,1.25];
            const vertex=device.createShaderModule({code:`@vertex fn main(@builtin(vertex_index) id:u32)->@builtin(position) vec4f {
              let positions=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(positions[id],0,1);}`});
            for(const mode of ['nearest','linear','trilinear','implicit'])for(const color of [0,1,2]){
              device.pushErrorScope('validation');
              const linear=mode!=='nearest';
              const code=`@group(0) @binding(0) var baseTex:texture_2d<f32>;
                @group(0) @binding(1) var baseTex_sampler:sampler;
                @fragment fn main(@builtin(position) position:vec4f)->@location(0) vec4f {
                  let coordinates=array<f32,7>(-.25,0,.25,.5,.75,1,1.25);
                  let uv=vec2f(${mode==='implicit'?'0.0':'coordinates[u32(position.x)]'},.5);
                  return ${mode==='trilinear'?'textureSampleLevel(baseTex,baseTex_sampler,uv,0.5)':mode==='implicit'?'textureSample(baseTex,baseTex_sampler,uv)':'textureSampleGrad(baseTex,baseTex_sampler,uv,vec2f(.01,0),vec2f(0,.01))'};
                }`;
              const adapted=adaptBorderSampling(code,[{name:'baseTex'}],'fragment');
              const fragment=device.createShaderModule({code:adapted.code});
              const state=[Number(linear),Number(linear),Number(linear),3,2,2,1,0,0,color,0];
              const pipeline=device.createRenderPipeline({layout:pipelineLayout,vertex:{module:vertex,entryPoint:'main'},
                fragment:{module:fragment,entryPoint:'main',constants:borderConstants(adapted.textures,()=>({samplerState:state})),targets:[{format:'rgba8unorm'}]},primitive:{topology:'triangle-list'}});
              const sampler=device.createSampler({magFilter:linear?'linear':'nearest',minFilter:linear?'linear':'nearest',mipmapFilter:linear?'linear':'nearest',lodMaxClamp:0});
              const group=device.createBindGroup({layout,entries:[{binding:0,resource:texture.createView()},{binding:1,resource:sampler}]});
              const target=device.createTexture({size:[7,1],format:'rgba8unorm',usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});resources.push(target);
              const buffer=device.createBuffer({size:256,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});resources.push(buffer);
              const encoder=device.createCommandEncoder();const pass=encoder.beginRenderPass({colorAttachments:[{view:target.createView(),loadOp:'clear',storeOp:'store',clearValue:[0,0,0,0]}]});
              pass.setPipeline(pipeline);pass.setBindGroup(0,group);pass.draw(3);pass.end();
              encoder.copyTextureToBuffer({texture:target},{buffer,bytesPerRow:256},[7,1]);device.queue.submit([encoder.finish()]);
              await buffer.mapAsync(GPUMapMode.READ);const pixels=[...new Uint8Array(buffer.getMappedRange()).slice(0,28)];buffer.unmap();
              const error=await device.popErrorScope();if(error)throw Error(error.message);
              const border=color===2?[1,1,1,1]:color===1?[0,0,0,1]:[0,0,0,0];
              const expected=uvs.flatMap(coordinate=>{
                const u=mode==='implicit'?0:coordinate;
                const weight=linear?Math.max(0,Math.min(1,u*2+.5,2.5-u*2)):(u>=0&&u<1?1:0);
                const mipWeight=Math.max(0,Math.min(1,u+.5,1.5-u));
                const red=[1,0,0,1].map((v,i)=>v*weight+border[i]*(1-weight));
                const green=[0,1,0,1].map((v,i)=>v*mipWeight+border[i]*(1-mipWeight));
                return red.map((v,i)=>Math.round(255*(mode==='trilinear'?(v+green[i])*.5:v)));
              });
              const passed=pixels.every((value,index)=>Math.abs(value-expected[index])<=1);
              result.tests.push({mode,color,passed,pixels,expected});
              if(!passed)throw Error('Border GPU readback differs: '+mode+' color '+color);
            }
            await device.queue.onSubmittedWorkDone();result.passed=result.errors.length===0;return result;
          } catch(error) {result.failure=error.message;return result;}
          finally {for(const resource of resources)resource.destroy();device.destroy();}
        }''')
    finally:page.close()
args.evidence.write_text(json.dumps(report,indent=2))
print(json.dumps(dict(passed=report['passed'],tests=len(report['tests']),errors=report['errors'],failure=report.get('failure')),indent=2))
raise SystemExit(0 if report['passed'] else 1)
