import {UploadBelt} from './webgpu-upload.mjs';
import {WebGPUEngine} from './webgpu-engine.mjs';

// Real asynchronous pipeline creation plus continuation of interleaved draws.
// Render a private 4x4 target, never the game canvas or a performance sample.
export async function verifyAsyncPipelines(device){
  const code={vertex:`@vertex fn main(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {
    let p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);}`,
    fragment:`struct Color { value:vec4f }; @group(0) @binding(0) var<uniform> color:Color;
      @fragment fn main()->@location(0) vec4f { return color.value; }`};
  const variant={code,uniforms:[{binding:0,size:16,visibility:2,members:[{name:'color',offset:0,columns:1,rows:4}]}],textures:[],inputs:[]};
  const session={device,context:{},diagnostics:{format:'rgba8unorm'},dispose:async()=>{}};
  const engine=new WebGPUEngine(session,{width:4,height:4},{programs:{probe:{defines:[],variants:{'{}':variant}}}});
  engine.asyncPipelines=true;
  const readback=device.createBuffer({size:1024,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  let timer;
  try{
    const work=async()=>{
      engine.call('resize',[4,4]);
      const shader=await engine.callAsync('createShader',['probe',{}],new Uint8Array());
      const color=engine.call('binding',[shader,'color']);
      // Blending one/zero leaves the source color: a second recipe, same bytes.
      // The third pipeline object repeats the first state and must reuse it.
      const pipelines=[0,1,0].map(blend=>engine.call('createPipeline',[shader,[0,7,0,0,255,255,0,[],[]],[blend,1,0,0,1,0,0,[0,0,0,0],15],[0,0,0,0,0,0]]));
      const layouts=[engine.call('createLayout',[]),engine.call('createLayout',[])];
      const target=engine.call('backbuffer',[1,1,1,1]);
      const words=new Uint32Array([8,0,3,0,1]),packet=new Uint8Array(words.buffer);
      await engine.callAsync('commands',[
        ['beginFramebuffer',[target]],['pipeline',[pipelines[0]]],['layout',[layouts[0]]],
        ['scissor',[0,0,2,4]],['uniform',[color,[1,0,0,1]]],['binaryCommands',[0,words.length]],
        ['pipeline',[pipelines[1]]],['layout',[layouts[1]]],['scissor',[2,0,2,4]],['uniform',[color,[0,0,1,1]]],
        ['binaryCommands',[0,words.length]],
        ['pipeline',[pipelines[2]]],['layout',[layouts[0]]],['scissor',[0,0,2,4]],['uniform',[color,[1,0,0,1]]],
        ['binaryCommands',[0,words.length]],['endFramebuffer',[]]],packet);
      engine.submit();
      const encoder=device.createCommandEncoder();
      encoder.copyTextureToBuffer({texture:engine.presentationTexture},{buffer:readback,bytesPerRow:256},[4,4,1]);
      device.queue.submit([encoder.finish()]);await readback.mapAsync(GPUMapMode.READ);
      const bytes=new Uint8Array(readback.getMappedRange());let comparedBytes=0;
      for(let y=0;y<4;y++)for(let x=0;x<4;x++){
        const expected=x<2?[255,0,0,255]:[0,0,255,255];
        for(let channel=0;channel<4;channel++){
          if(bytes[y*256+x*4+channel]!==expected[channel])throw new Error('Async pipeline continuation changed draw bytes');
          comparedBytes++;
        }
      }
      readback.unmap();
      if(engine.stats.draws!==3 || engine.stats.pipelineCompiles!==2 || engine.stats.pipelineContentHits!==1)
        throw new Error('Async pipeline probe did not execute the original draws, both pipelines and the reuse');
      return {passed:true,comparedBytes,draws:engine.stats.draws,pipelines:engine.stats.pipelineCompiles,contentHits:engine.stats.pipelineContentHits};
    };
    return await Promise.race([work(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Async pipeline GPU probe timed out')),15000);})]);
  }finally{clearTimeout(timer);readback.destroy();await engine.dispose();}
}

// Exercise the production binary texture decoder and staging/copy path on a
// private mip/array layer. Two updates are read back in command order. These
// diagnostic bytes are unrelated to the canvas and never enter an FPS window.
export async function verifyTextureCommands(device) {
  const formats=[{index:1,format:'r8unorm',width:3,height:2,stride:1},
    {index:5,format:'rgba8unorm',width:3,height:2,stride:4}];
  if(device.features.has('texture-compression-bc'))
    formats.push({index:32,format:'bc1-rgba-unorm',width:4,height:4,stride:0});
  let comparedBytes=0;
  for(const spec of formats){
    const rows=spec.stride?spec.height:1,rowBytes=spec.stride?spec.width*spec.stride:8;
    const texture=device.createTexture({size:[8,8,3],mipLevelCount:2,format:spec.format,usage:GPUTextureUsage.COPY_DST|GPUTextureUsage.COPY_SRC});
    const readback=device.createBuffer({size:256*rows*2,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
    const engine=Object.assign(Object.create(WebGPUEngine.prototype),{device,encoder:null,objects:new Map([[41,{texture,format:spec.format}]]),nextId:100,retired:new Set(),stats:{commandBatches:0,uploadBytes:0}});
    let timer;
    try {
      const expected=[];
      for(let update=0;update<2;update++){
        const bytes=Uint8Array.from({length:rowBytes*rows},(_,i)=>(i*37+update*83+spec.index)&255);expected.push(bytes.slice());
        const codeOffset=Math.ceil(bytes.length/4)*4;
        const words=[13,41,spec.index,0,0,spec.width,spec.height,1,2,0,bytes.length];
        const packet=new Uint8Array(codeOffset+words.length*4);packet.set(bytes);new Uint32Array(packet.buffer,codeOffset,words.length).set(words);
        engine.call('commands',[['binaryCommands',[codeOffset,words.length]]],packet);packet.fill(255);bytes.fill(0);
        engine.encoderForWork().copyTextureToBuffer({texture,mipLevel:1,origin:[0,0,2]},
          {buffer:readback,offset:update*256*rows,bytesPerRow:256,rowsPerImage:rows},[spec.width,spec.height,1]);
      }
      device.queue.submit([engine.encoder.finish()]);
      await Promise.race([readback.mapAsync(GPUMapMode.READ),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('GPU texture probe timed out')),15000);})]);
      const actual=new Uint8Array(readback.getMappedRange());
      for(let update=0;update<2;update++)for(let row=0;row<rows;row++)for(let column=0;column<rowBytes;column++){
        const index=row*rowBytes+column;
        if(actual[update*256*rows+row*256+column]!==expected[update][index])
          throw new Error(`GPU texture command mismatch: ${spec.format}, update ${update}, byte ${index}`);
        comparedBytes++;
      }
      readback.unmap();
    } finally {clearTimeout(timer);for(const object of engine.objects.values())object.buffer?.destroy();readback.destroy();texture.destroy();}
  }
  return {passed:true,formats:formats.map(x=>x.format),comparedBytes,mipLevel:1,arrayLayer:2,orderedUpdates:2,scope:'Exact private GPU texture bytes before warmup; not a canvas capture or FPS acceptance'};
}

// Small GPU readback, run only before a performance window when requested by
// the CLI. A one-chunk budget forces both mapped and writeBuffer paths.
export async function verifyUploadBelt(device) {
  const errors=[],belt=new UploadBelt(device,{chunkBytes:64,maxBytes:64,onError:e=>errors.push(e.message)});
  const targets=[0,1].map(()=>device.createBuffer({size:64,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.COPY_SRC}));
  const readback=device.createBuffer({size:128,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  let timer;
  try {
    const work=async()=>{
      for(let frame=0;frame<12;frame++) {
        const expected=[0,1].map(which=>Uint8Array.from({length:64},(_,i)=>(frame*17+which*113+i*31)&255));
        for(let i=0;i<2;i++){const input=expected[i].slice();belt.stage(targets[i],input);input.fill(255);}
        const uploads=belt.beforeFrame(),encoder=device.createCommandEncoder();
        for(let i=0;i<2;i++)encoder.copyBufferToBuffer(targets[i],0,readback,i*64,64);
        device.queue.submit(uploads?[uploads,encoder.finish()]:[encoder.finish()]);
        const pending=belt.afterSubmit();
        await Promise.all([readback.mapAsync(GPUMapMode.READ),...pending]);
        const actual=new Uint8Array(readback.getMappedRange());
        for(let i=0;i<128;i++)if(actual[i]!==expected[i>>6][i&63])throw new Error(`GPU upload byte mismatch at frame ${frame}, byte ${i}`);
        readback.unmap();
      }
      if(errors.length||belt.stats.createdBuffers!==1||belt.stats.reusedBuffers!==11||belt.stats.mappedBytes!==768||belt.stats.fallbackBytes!==768)
        throw new Error('Mapped upload pool did not exercise the expected reuse and fallback paths');
      return {passed:true,frames:12,comparedBytes:1536,stats:{...belt.stats},scope:'Exact GPU bytes before warmup; not FPS acceptance'};
    };
    return await Promise.race([work(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('GPU upload probe timed out')),15000);})]);
  } finally {clearTimeout(timer);belt.dispose();for(const target of targets)target.destroy();readback.destroy();}
}
