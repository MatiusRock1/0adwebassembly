// Window-side transport only. GPU objects and command encoding live in the
// render worker. Shared payloads remain borrowed until that worker signals C++.
import {validateSharedRequest,completeSharedRequest} from './shared-request.mjs';
export {validateSharedRequest,completeSharedRequest} from './shared-request.mjs';

export async function openRenderWorker({canvas,catalog,powerPreference,requiredFeatures=[],optionalFeatures=[],report=()=>{}}) {
  if(typeof canvas.transferControlToOffscreen!=='function')throw new Error('OffscreenCanvas is required by this build');
  // SDL retains its original input canvas and can resize it normally. The
  // separate visible surface is owned exclusively by the render worker.
  const display=document.createElement('canvas');
  display.id='render-canvas';display.width=canvas.width;display.height=canvas.height;
  display.setAttribute('aria-hidden','true');display.style.pointerEvents='none';
  canvas.parentElement.style.position='relative';canvas.before(display);
  canvas.classList.add('render-input');
  const worker=new Worker(new URL('./webgpu-render-worker.mjs',import.meta.url),{type:'module',name:'0ad-webgpu-render'});
  const pending=new Map();
  let nextId=1,closed=false,disposePromise;
  const bridge={stats:null,uploadBelt:{stats:null},live:true,remote:true,display,
    rpc(method,args={}) {
      if(closed)return Promise.reject(new Error('Render worker is closed'));
      const id=nextId++;
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`Render worker timed out: ${method}`));},30000);
        pending.set(id,{resolve,reject,timer});worker.postMessage({type:'rpc',id,method,args});
      });
    },
    sendShared(request) {
      validateSharedRequest(request);
      if(closed){completeSharedRequest(request,false);return;}
      request.id=nextId++;request.type='shared';
      try{worker.postMessage(request);}
      catch(error){completeSharedRequest(request,false);fail(error);}
    },
    dispatchShared(method,args,buffer,offset,length,sequence,ready) {
      this.sendShared({method,args,buffer,offset,length,sequence,ready});
    },
    requestShared(method,args,buffer,offset,length,ready,result) {
      this.sendShared({method,args,buffer,offset,length,ready,result});
    },
    async snapshot() {
      const state=await this.rpc('snapshot');this.stats=state.stats;this.uploadBelt.stats=state.uploadBelt;
      return state;
    },
    probeUploads(){return this.rpc('probeUploads');},
    dispose() {
      return disposePromise??=(async()=>{
        try{if(!closed)await this.rpc('dispose');}
        finally{
          closed=true;this.live=false;worker.terminate();
          rejectPending(new Error('Render worker closed'));
        }
      })();
    }
  };
  // Preserve the diagnostic frame receipt's position after its Present packet.
  // The callback runs in the window only after the worker passes that barrier.
  bridge.commandDispatcher={enqueue(run,ack=()=>{},onError=error=>{throw error;}){
    bridge.rpc('barrier').then(()=>{run();ack(true);},error=>{ack(false);onError(error);});
  }};
  function rejectPending(error){for(const p of pending.values()){clearTimeout(p.timer);p.reject(error);}pending.clear();}
  function fail(error){
    if(closed)return;closed=true;bridge.live=false;
    // An acknowledgement can let C++ reclaim its pointers before its message
    // reaches this window. Never write to stale shared pointers on failure;
    // the application boundary terminates the owned pthreads instead.
    rejectPending(error);worker.terminate();
    report({type:'engine-device-lost',expected:false,reason:'render-worker',message:error.message});
  }
  worker.addEventListener('error',event=>{event.preventDefault();fail(new Error(event.message||'Render worker failed'));});
  worker.addEventListener('messageerror',()=>fail(new Error('Render worker message could not be decoded')));
  worker.addEventListener('message',({data})=>{
    if(data.type==='consumed')return;
    if(data.type==='fatal'){fail(new Error(data.message));return;}
    if(data.type==='event'){if(data.event.type!=='engine-frame')report(data.event);return;}
    const request=pending.get(data.id);if(!request)return;
    pending.delete(data.id);clearTimeout(request.timer);
    if(data.error)request.reject(new Error(data.error));else request.resolve(data.value);
  });
  const id=nextId++,offscreen=display.transferControlToOffscreen();
  try{
    const diagnostics=await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Render worker initialization timed out'));},30000);
      pending.set(id,{resolve,reject,timer});
      worker.postMessage({type:'init',id,canvas:offscreen,catalog,powerPreference,requiredFeatures,optionalFeatures},[offscreen]);
    });
    bridge.diagnostics=diagnostics;
    return {bridge,diagnostics,dispose:()=>bridge.dispose()};
  }catch(error){fail(error);display.remove();canvas.classList.remove('render-input');throw error;}
}
