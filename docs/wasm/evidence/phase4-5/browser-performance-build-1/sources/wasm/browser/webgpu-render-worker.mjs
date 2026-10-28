import {openRendererSession} from './renderer-session.mjs';
import {WebGPUEngine} from './webgpu-engine.mjs';
import {completeSharedRequest,validateSharedRequest} from './shared-request.mjs';

let engine,sequence=0,disposed=false,queue=Promise.resolve();
const emit=event=>{if(event.type!=='engine-frame')postMessage({type:'event',event});};
const snapshot=()=>({stats:{...engine.stats},uploadBelt:{...engine.uploadBelt.stats},asyncSequence:sequence});

async function control(message){
  if(message.type==='init'){
    if(engine)throw new Error('Render worker already initialized');
    const session=await openRendererSession({...message,backend:'webgpu',owner:'render-worker',report:emit});
    engine=new WebGPUEngine(session,message.canvas,message.catalog,emit);
    engine.asyncPipelines=true;
    return session.diagnostics;
  }
  if(!engine)throw new Error('Render worker not initialized');
  if(message.method==='barrier')return null;
  if(message.method==='snapshot')return snapshot();
  if(message.method==='surface')return {
    drawingBuffer:[engine.width,engine.height],
    proxiedDepthAttachment:[engine.depthTexture?.width,engine.depthTexture?.height],
    colorAttachment:[engine.presentationTexture?.width,engine.presentationTexture?.height],
    renderCanvas:[engine.canvas.width,engine.canvas.height],viewport:engine.viewportRect};
  if(message.method==='probeUploads'){
    const {verifyUploadBelt,verifyTextureCommands,verifyAsyncPipelines}=await import('./webgpu-upload-probe.mjs');
    return {...await verifyUploadBelt(engine.device),textureCommands:await verifyTextureCommands(engine.device),asyncPipelines:await verifyAsyncPipelines(engine.device)};
  }
  if(message.method==='dispose'){disposed=true;await engine.dispose();return {disposed:true};}
  throw new Error('Unknown render control: '+message.method);
}

async function consume(message){
  if(message.type!=='shared'){
    try{postMessage({id:message.id,value:await control(message)});}
    catch(error){postMessage({id:message.id,error:error.stack||String(error)});}
    return;
  }
  let validated=false;
  try{
    validateSharedRequest(message);validated=true;
    if(!engine||disposed)throw new Error('Render worker cannot consume commands');
    if(message.sequence!==undefined){
      if(((sequence+1)>>>0)!==message.sequence)throw new Error('Render worker command order changed');
      sequence=message.sequence;
    }
    const heap=new Uint8Array(message.buffer);
    engine.heap=()=>heap;
    const result=await engine.callAsync(message.method,message.args,heap.subarray(message.offset,message.offset+message.length));
    completeSharedRequest(message,true,result||0);
  }catch(error){
    if(validated)completeSharedRequest(message,false);
    postMessage({type:'fatal',message:error.stack||String(error)});
  }
}
self.addEventListener('message',({data})=>{
  queue=queue.then(()=>consume(data)).catch(error=>postMessage({type:'fatal',message:error.stack||String(error)}));
});
