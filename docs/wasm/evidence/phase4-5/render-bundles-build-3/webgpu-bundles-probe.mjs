import {RenderBundleCache} from './webgpu-bundles.mjs';

// Diagnostic pixels on a private target, before warmup. Reused bundles must
// read current uniform data, keep dynamic offsets/baseVertex, and restore
// bindings when mixing bundled draws with directly encoded scissored draws.
export async function verifyRenderBundleCache(device){
  const cache=new RenderBundleCache(device),format='rgba8unorm',width=4,height=4;
  const descriptor={colorFormats:[format],sampleCount:1};
  const stride=device.limits.minUniformBufferOffsetAlignment;
  const uniform=device.createBuffer({size:stride+16,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});
  const indices=device.createBuffer({size:8,usage:GPUBufferUsage.INDEX|GPUBufferUsage.COPY_DST});
  const target=device.createTexture({size:[width,height],format,usage:GPUTextureUsage.RENDER_ATTACHMENT|GPUTextureUsage.COPY_SRC});
  const readback=device.createBuffer({size:256*height,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  const view=target.createView();
  let timer,comparedBytes=0;
  device.pushErrorScope('validation');
  try{
    const work=async()=>{
      const module=device.createShaderModule({code:`
        @group(0) @binding(0) var<uniform> color:vec4<f32>;
        @vertex fn vertexMain(@builtin(vertex_index) index:u32)->@builtin(position) vec4<f32>{
          var p=array<vec2<f32>,3>(vec2<f32>(-1,-1),vec2<f32>(3,-1),vec2<f32>(-1,3));
          return vec4<f32>(p[index],0,1);
        }
        @fragment fn fragmentMain()->@location(0) vec4<f32>{return color;}`});
      const groupLayout=device.createBindGroupLayout({entries:[{binding:0,visibility:GPUShaderStage.FRAGMENT,
        buffer:{type:'uniform',hasDynamicOffset:true,minBindingSize:16}}]});
      const layout=device.createPipelineLayout({bindGroupLayouts:[groupLayout]});
      const group=device.createBindGroup({layout:groupLayout,entries:[{binding:0,resource:{buffer:uniform,size:16}}]});
      const pipeline=additive=>device.createRenderPipeline({layout,vertex:{module,entryPoint:'vertexMain'},
        fragment:{module,entryPoint:'fragmentMain',targets:[{format,...(additive?{blend:{
          color:{srcFactor:'one',dstFactor:'one',operation:'add'},alpha:{srcFactor:'one',dstFactor:'one',operation:'add'}}}:{})}]},
        primitive:{topology:'triangle-list'}});
      const opaque=pipeline(false),additive=pipeline(true);
      device.queue.writeBuffer(indices,0,new Uint16Array([1,2,3,0]));
      const colors=[[1,0,0,1],[0,1,0,1],[0,0,1,1]];
      for(let frame=0;frame<15;frame++){
        const viewport=frame>=9&&frame<12,scissor=(frame>=6&&frame<9)||frame>=12;
        const first=scissor||viewport?colors[0]:colors[frame%3],second=scissor||viewport?colors[1]:colors[(frame+1)%3];
        device.queue.writeBuffer(uniform,0,new Float32Array(first));
        device.queue.writeBuffer(uniform,stride,new Float32Array(second));
        const encoder=device.createCommandEncoder();
        const raw=encoder.beginRenderPass({colorAttachments:[{view,loadOp:'clear',storeOp:'store',clearValue:[0,0,0,1]}]});
        const pass=cache.begin(raw,descriptor,width,height),offset=frame<3||scissor||viewport?0:stride;
        if(viewport)pass.setViewport(0,0,2,height,0,1);
        pass.setPipeline(scissor?additive:opaque);pass.setBindGroup(0,group,[offset]);pass.setIndexBuffer(indices,'uint16');
        const draw=(count=8)=>{for(let i=0;i<count;i++)pass.drawIndexed(3,1,0,-1,0);};
        draw();
        if(scissor){
          pass.setScissorRect(0,0,2,height);pass.setBindGroup(0,group,[stride]);draw(frame>=12?2:8);
          pass.setScissorRect(0,0,width,height);pass.setBindGroup(0,group,[0]);draw();
        }
        pass.end();
        encoder.copyTextureToBuffer({texture:target},{buffer:readback,bytesPerRow:256},[width,height]);
        device.queue.submit([encoder.finish()]);await readback.mapAsync(GPUMapMode.READ);
        const bytes=new Uint8Array(readback.getMappedRange());
        for(let y=0;y<height;y++)for(let x=0;x<width;x++)for(let c=0;c<4;c++){
          const color=scissor?(x<2?[1,1,0,1]:[1,0,0,1]):viewport&&x>=2?[0,0,0,1]:(offset?second:first);
          if(bytes[y*256+x*4+c]!==color[c]*255)throw new Error(`Bundle GPU byte mismatch: frame ${frame}, pixel ${x},${y}, channel ${c}`);
          comparedBytes++;
        }
        readback.unmap();
      }
      if(cache.stats.bundleCacheHits<2||cache.stats.bundleCacheCreates<2)
        throw new Error('GPU probe did not execute cached bundles');
      return {passed:true,checks:15,comparedBytes,stats:{...cache.stats},
        scope:'Private GPU bytes before warmup: live uniforms, dynamic offsets, negative baseVertex, inherited viewport/scissor and mixed direct/bundle binding restoration; not FPS acceptance'};
    };
    return await Promise.race([work(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Bundle GPU probe timed out')),15000);})]);
  }finally{
    clearTimeout(timer);cache.clear();uniform.destroy();indices.destroy();target.destroy();readback.destroy();
    const error=await device.popErrorScope();if(error)throw new Error('Bundle GPU validation: '+error.message);
  }
}
