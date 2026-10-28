"""GPU readback regression for the original Canvas2D shader and vertex winding."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.connect_over_cdp('http://localhost:9227')
    page=browser.contexts[0].new_page()
    page.goto('http://localhost:8095/webgpu-probe.html')
    result=page.evaluate('''async () => {
      const {openRendererSession}=await import('./renderer-session.mjs');
      const {WebGPUEngine}=await import('./webgpu-engine.mjs');
      const catalog=await (await fetch('./webgpu-shaders.json')).json();
      const canvas=document.querySelector('canvas');canvas.hidden=false;
      const errors=[];
      const session=await openRendererSession({canvas,backend:'webgpu',report:event=>{if(event.type.includes('error'))errors.push(event);}});
      const engine=new WebGPUEngine(session,canvas,catalog);
      engine.call('resize',[64,64]);
      const shader=engine.call('createShader',['glsl/canvas2d',{}]);
      const layout=engine.call('createLayout',[[0,23,0,8,0,0],[3,23,0,8,0,1]]);
      const pipeline=engine.call('createPipeline',[shader,[0,3,0,0,255,255,0,[0,0,0,7],[0,0,0,7]],
        [0,1,0,0,1,0,0,[0,0,0,0],15],[0,2,0,0,0,0]]);
      const texture=engine.call('createTexture',['readback texel',0,6,5,1,1,[0,0,0,2,2,2,1,0,0],1,1]);
      const upload=engine.call('stageTexture',[texture,5,0,0,1,1,0,0],new Uint8Array([255,0,0,255]));
      const framebuffer=engine.call('backbuffer',[1,0,1,0]);
      const bytes=values=>Array.from(new Uint8Array(new Float32Array(values).buffer));
      const uniform=(name,values)=>['uniform',[engine.call('binding',[shader,name]),values]];
      engine.call('commands',[
        ['uploadTexture',[upload]],['beginFramebuffer',[framebuffer]],['pipeline',[pipeline]],['layout',[layout]],
        uniform('transform',[2/64,0,0,-2/64]),uniform('translation',[-1,1]),
        uniform('colorAdd',[0,0,0,0]),uniform('colorMul',[1,1,1,1]),uniform('grayscaleFactor',[0]),
        ['texture',[engine.call('binding',[shader,'tex']),texture]],
        // Exactly the original Canvas2D rectangle vertex order.
        ['vertexData',[0,bytes([0,32,32,32,32,0,0,32,32,0,0,0])]],
        ['vertexData',[1,bytes([0,1,1,1,1,0,0,1,1,0,0,0])]],['draw',[0,6,0,1]],['endFramebuffer',[]]
      ]);
      engine.call('present',[]);
      await session.device.queue.onSubmittedWorkDone();
      // The staging resource may now be retired. Its destination must remain
      // usable; exercise fully clipped rectangles on every side as well.
      engine.call('commands',[
        ['beginFramebuffer',[framebuffer]],
        ...[[100,10,20,20],[-100,10,20,20],[10,100,20,20],[10,-100,20,20]].flatMap(rect=>[['scissor',rect],['draw',[0,6,0,1]]]),
        ['scissor',[]],['draw',[0,6,0,1]],['endFramebuffer',[]]
      ]);
      engine.call('present',[]);
      const buffer=session.device.createBuffer({size:64*256,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
      const encoder=session.device.createCommandEncoder();encoder.copyTextureToBuffer({texture:engine.presentationTexture},{buffer,bytesPerRow:256},[64,64,1]);
      session.device.queue.submit([encoder.finish()]);await buffer.mapAsync(GPUMapMode.READ);
      const pixels=new Uint8Array(buffer.getMappedRange());
      const at=(x,y)=>Array.from(pixels.subarray(y*256+x*4,y*256+x*4+4));
      const result={topLeft:at(16,16),bottomLeft:at(16,48),topRight:at(48,16),errors,format:session.diagnostics.format};
      buffer.unmap();buffer.destroy();await engine.dispose();return result;
    }''')
    page.close()
expected=[0,0,255,255] if result['format'].startswith('bgra') else [255,0,0,255]
result['passed']=result['topLeft']==expected and result['bottomLeft'][:3]==[0,0,0] and result['topRight'][:3]==[0,0,0] and not result['errors']
output=Path('docs/wasm/evidence/phase4-5/canvas-readback.json');output.write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
raise SystemExit(not result['passed'])
