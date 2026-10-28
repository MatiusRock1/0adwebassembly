import {openRendererSession} from './renderer-session.mjs';
import {WebGPUEngine} from './webgpu-engine.mjs';
import {completeSharedRequest,validateSharedRequest} from './shared-request.mjs';
import {WorkerPresentation} from './webgpu-worker-present.mjs';
import {CommandRing} from './webgpu-command-ring.mjs';
import {PipelineStore,PipelineWarmup,pipelineCacheKey} from './webgpu-pipeline-cache.mjs';

let engine,sequence=0,disposed=false,queue=Promise.resolve(),pacingViews=null;
let ring=null,ringExecuted=0,pipelineStore=null,warmup=null,current=null;
const ringBarriers=[];
const presentation=new WorkerPresentation();
const queueStats={pending:0,maxPending:0,consumed:0,totalWaitMilliseconds:0,maxWaitMilliseconds:0};
// Encoding time of this worker, without the waits for display signals and
// pipelines. frameHistogram counts frames under 2, 4, 8, 16, 33 ms and above.
const work={busyMilliseconds:0,frames:0,frameBusyMilliseconds:0,maxFrameBusyMilliseconds:0,frameHistogram:[0,0,0,0,0,0]};
// From the engine thread publishing a call to this worker receiving it; the
// histogram counts calls under 0.25, 0.5, 1, 2, 4, 8 ms and above.
const delivery={ring:0,relay:0,totalMilliseconds:0,minMilliseconds:Infinity,maxMilliseconds:0,histogram:[0,0,0,0,0,0,0]};
const emit=event=>{if(event.type!=='engine-frame')postMessage({type:'event',event});};
const snapshot=()=>({stats:{...engine.stats},uploadBelt:{...engine.uploadBelt.stats},asyncSequence:sequence,
  presentation:{...presentation.stats},commandQueue:{...queueStats},work:{...work,frameHistogram:[...work.frameHistogram]},
  delivery:{...delivery,histogram:[...delivery.histogram]},commandRing:ring?{attached:true,...ring.stats}:{attached:false},
  pipelineCache:pipelineStore?{...pipelineStore.stats,stored:pipelineStore.recipes.size,warmup:warmup?{...warmup.stats}:null}:null});

function busy(run){
  const started=performance.now();
  try{return run();}
  finally{const spent=performance.now()-started;work.busyMilliseconds+=spent;work.frameBusyMilliseconds+=spent;}
}
const FRAME_LIMITS=[2,4,8,16,33];
function frameDone(){
  const spent=work.frameBusyMilliseconds;work.frames++;work.frameBusyMilliseconds=0;
  work.maxFrameBusyMilliseconds=Math.max(work.maxFrameBusyMilliseconds,spent);
  const bin=FRAME_LIMITS.findIndex(limit=>spent<limit);
  work.frameHistogram[bin<0?FRAME_LIMITS.length:bin]++;
}
function recordDelivery(message,received){
  if(!(message.publishedAt>0))return;
  const latency=performance.timeOrigin+received-message.publishedAt;
  delivery[message.ringIndex===undefined?'relay':'ring']++;delivery.totalMilliseconds+=latency;
  delivery.minMilliseconds=Math.min(delivery.minMilliseconds,latency);delivery.maxMilliseconds=Math.max(delivery.maxMilliseconds,latency);
  delivery.histogram[latency<0.25?0:Math.min(6,Math.floor(Math.log2(latency/0.25))+1)]++;
}

// Pipelines of earlier sessions compile in the background; IndexedDB or
// compilation failures only cost the warm start, never the renderer.
async function startPipelineCache(catalog,diagnostics){
  pipelineStore=new PipelineStore({key:pipelineCacheKey(catalog,diagnostics),report:emit});
  engine.onPipelineRecipe=key=>pipelineStore.add(key);
  const recipes=await pipelineStore.load();
  if(disposed)return;
  warmup=new PipelineWarmup(engine,recipes,{onFailure:key=>pipelineStore.remove(key),report:emit});
  warmup.start();
}

// Frame samples wait for the records published up to their frame's present.
const reached=until=>((ringExecuted-until)|0)>=0;
function settleBarriers(){
  for(let i=0;i<ringBarriers.length;)
    if(reached(ringBarriers[i].until)){postMessage({id:ringBarriers[i].id,value:null});ringBarriers.splice(i,1);}else i++;
}

async function control(message){
  if(message.type==='init'){
    if(engine)throw new Error('Render worker already initialized');
    const session=await openRendererSession({...message,backend:'webgpu',owner:'render-worker',report:emit});
    engine=new WebGPUEngine(session,message.canvas,message.catalog,emit);
    engine.asyncPipelines=true;
    if(message.pipelineCache!==false)startPipelineCache(message.catalog,session.diagnostics)
      .catch(error=>emit({type:'pipeline-cache-error',message:error.message}));
    return session.diagnostics;
  }
  if(!engine)throw new Error('Render worker not initialized');
  if(message.method==='barrier')return null;
  if(message.method==='snapshot')return snapshot();
  if(message.method==='attachRing'){
    const {memory,address,capacity}=message.args;
    if(ring)throw new Error('Shared command ring already attached');
    if(!(memory instanceof WebAssembly.Memory))throw new Error('Shared command ring needs the WASM memory');
    ring=new CommandRing(memory,address,capacity);
    ring.run(record=>schedule({type:'shared',...record,buffer:ring.buffer}))
      .catch(error=>postMessage({type:'fatal',message:error.stack||String(error)}));
    return {attached:true};
  }
  if(message.method==='surface')return {
    drawingBuffer:[engine.width,engine.height],
    proxiedDepthAttachment:[engine.depthTexture?.width,engine.depthTexture?.height],
    colorAttachment:[engine.presentationTexture?.width,engine.presentationTexture?.height],
    renderCanvas:[engine.canvas.width,engine.canvas.height],viewport:engine.viewportRect};
  if(message.method==='probeUploads'){
    const {verifyUploadBelt,verifyTextureCommands,verifyAsyncPipelines}=await import('./webgpu-upload-probe.mjs');
    return {...await verifyUploadBelt(engine.device),textureCommands:await verifyTextureCommands(engine.device),asyncPipelines:await verifyAsyncPipelines(engine.device)};
  }
  if(message.method==='dispose'){
    disposed=true;ring?.close();warmup?.stop();presentation.dispose();
    await pipelineStore?.close();await engine.dispose();return {disposed:true};
  }
  throw new Error('Unknown render control: '+message.method);
}

// An engine built with WASM_PRESENT_PACING passes [pacing block address, cap
// interval in ms] with each present (application-present-pacing.h).
function presentPacing({args,buffer}){
  if(!Array.isArray(args)||!args.length)return null;
  const [address,intervalMs]=args;
  if(!Number.isSafeInteger(address)||address<=0||address%8||address+24>buffer.byteLength||!(intervalMs>=4&&intervalMs<=1000))
    throw new Error('Invalid present pacing arguments');
  if(pacingViews?.buffer!==buffer)pacingViews={buffer,words:new Int32Array(buffer),times:new Float64Array(buffer)};
  return {words:pacingViews.words,times:pacingViews.times,address,intervalMs};
}

async function consume(message){
  if(message.type!=='shared'){
    if(message.method==='barrier'&&ring&&Number.isSafeInteger(message.args?.until)&&!reached(message.args.until)){
      ringBarriers.push({id:message.id,until:message.args.until});return;
    }
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
    const payload=heap.subarray(message.offset,message.offset+message.length);
    const pacing=message.method==='present'?presentPacing(message):null;
    // A paced frame waits for its display signal. Submit its GPU work now, so
    // that only the copy to the canvas is left for that signal and the GPU has
    // the wait to finish the frame before the browser composites it.
    if(pacing)busy(()=>engine.submit());
    let result;
    if(message.method==='present'){
      result=await presentation.present(()=>busy(()=>engine.call('present',message.args,payload)),pacing);
      frameDone();
    }else result=await busy(()=>engine.callAsync(message.method,message.args,payload));
    completeSharedRequest(message,true,result||0);
  }catch(error){
    if(validated)completeSharedRequest(message,false);
    postMessage({type:'fatal',message:error.stack||String(error)});
  }
}
// Relayed messages and ring records share one ordered queue.
function schedule(data,received=performance.now()){
  if(data.type==='shared')recordDelivery(data,received);
  queueStats.pending++;queueStats.maxPending=Math.max(queueStats.maxPending,queueStats.pending);
  queue=queue.then(async()=>{
    const wait=performance.now()-received;
    queueStats.totalWaitMilliseconds+=wait;
    queueStats.maxWaitMilliseconds=Math.max(queueStats.maxWaitMilliseconds,wait);
    current={method:data.method??data.type,sequence:data.sequence,started:performance.now()};
    try{await consume(data);}
    finally{
      current=null;queueStats.pending--;queueStats.consumed++;
      if(data.ringIndex!==undefined){ringExecuted=data.ringIndex;settleBarriers();}
    }
  }).catch(error=>postMessage({type:'fatal',message:error.stack||String(error)}));
}
// peek answers at once, outside the queue, so it also works while the queue
// waits (a display signal, a pipeline); snapshot keeps its place in the queue.
self.addEventListener('message',({data})=>{
  if(data.type==='rpc'&&data.method==='peek'){
    const pending=[...(engine?.contentPipelines?.values()??[])].filter(entry=>entry.promise).length;
    postMessage({id:data.id,value:engine?{...snapshot(),pendingPipelines:pending,
      suspendedMilliseconds:engine.suspendedAt===undefined?null:performance.now()-engine.suspendedAt,
      current:current&&{...current,elapsedMilliseconds:performance.now()-current.started,command:engine.lastCommand},
      ringRead:ring?.read??null,ringExecuted}:null});
    return;
  }
  schedule(data);
});
